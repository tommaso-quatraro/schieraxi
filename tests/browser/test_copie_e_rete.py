"""Le copie dei dati nel browser con la rete lenta o assente, e con più schede aperte (collaudo del 26/11/2026).

La web tiene nel browser una copia delle ultime risposte, per aprirsi subito e per quando il server non risponde. Difetti visti
nel collaudo, ognuno con il suo test:
- una sola lettura non riuscita della formazione salvata (503) prendeva il posto della copia buona: riaperta senza rete, la
  Formazione mostrava gli 11 consigliati come se fossero i tuoi;
- con la rete lenta la prima schermata restava vuota finché non rispondevano «chi sono», lo stato, le squadre, i volti e le
  funzioni, nessuna con un tempo massimo;
- la prima scheda di un giocatore mostrava le prossime partite della copia del calendario, di qualunque età;
- un'altra scheda che esce, o entra con un altro account: questa salvava i dati del secondo sotto la chiave del primo.
La versione nuova della web installata sta in test_web_installata.py.

Qui la rete la governa il test (`Rete`): le /api/ si fermano finché il test non le lascia andare (la rete lenta), non arrivano
(senza rete) o rispondono con un errore. Si guarda ciò che vede chi usa l'app.
"""
import json
import re
from urllib.parse import urlsplit

import pytest

# /api/account/me del server con gli account (com'è in produzione), per due utenti normali inventati
UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
ALTRO = {"id": 8, "nome_utente": "altro", "nome_visualizzato": "Altro di prova", "ruolo": "utente", "creato": "2026-10-02T10:00:00"}
# il 401 del server con gli account (rotte_account.py): dice anche come ci si registra e con quali servizi si entra
SCADUTA = {"detail": "Accesso richiesto", "multiutente": True, "registrazione": "email", "social": ["google"], "email_attiva": True}
TITOLARI = "() => [...document.querySelectorAll('main #campo-formazione [data-giocatore]')].map(e => Number(e.dataset.giocatore))"
CAMPO_PIENO = "() => document.querySelectorAll('main #campo-formazione [data-giocatore]').length === 11"


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("le copie e la rete non dipendono dalla fase: basta prima della scadenza, con una formazione salvata")


class Rete:
    """Le /api/ di una pagina come le vuole il test.
    - `giu = True`: non arrivano (senza rete);
    - `guasti[percorso] = stato`: rispondono con quell'errore;
    - `risposte[percorso] = (stato, corpo)`: rispondono con quel JSON al posto del server finto;
    - `ferme`: i percorsi trattenuti («*»: tutti, la rete lenta), finché il test non li lascia andare con `lascia()`."""

    def __init__(self, pagina):
        self.giu = False
        self.guasti: dict[str, int] = {}
        self.risposte: dict[str, tuple[int, object]] = {}
        self.ferme: set[str] = set()
        self.trattenute = []
        pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), self._smista)

    def _smista(self, route):
        percorso = urlsplit(route.request.url).path
        if self.giu:
            route.abort("internetdisconnected")
        elif "*" in self.ferme or percorso in self.ferme:
            self.trattenute.append(route)
        else:
            self._rispondi(route)

    def _rispondi(self, route):
        percorso = urlsplit(route.request.url).path
        try:
            if self.giu:
                route.abort("internetdisconnected")
            elif percorso in self.guasti:
                route.fulfill(status=self.guasti[percorso], content_type="application/json",
                              body=json.dumps({"detail": "Servizio non disponibile"}))
            elif percorso in self.risposte:
                stato, corpo = self.risposte[percorso]
                route.fulfill(status=stato, content_type="application/json; charset=utf-8", body=json.dumps(corpo))
            else:
                route.fallback()
        except Exception:                    # noqa: BLE001 - la pagina nel frattempo si è ricaricata: la richiesta non c'è più
            pass

    def lascia(self, percorso: str = "*") -> None:
        """Le richieste trattenute di `percorso` («*»: tutte) partono; quelle dopo non si fermano più."""
        if percorso == "*":
            self.ferme.clear()
        self.ferme.discard(percorso)
        restano = []
        for route in self.trattenute:
            if percorso == "*" or urlsplit(route.request.url).path == percorso:
                self._rispondi(route)
            else:
                restano.append(route)
        self.trattenute = restano


def _testo(web) -> str:
    return " ".join(web.testo_principale().split())


def _titolari(web) -> list[int]:
    return sorted(web.pagina.evaluate(TITOLARI))


def _ricarica(web) -> None:
    web.pagina.reload(wait_until="load")
    web.aspetta()


def _aspetta_il_campo(web, secondi: float, perche: str) -> None:
    """Gli 11 sul campo entro `secondi`; se no il test fallisce con `perche` e ciò che si vede."""
    from playwright.sync_api import TimeoutError as AttesaScaduta
    try:
        web.pagina.wait_for_function(CAMPO_PIENO, timeout=secondi * 1000)
    except AttesaScaduta:
        pytest.fail(f"{perche}: dopo {secondi} s l'area principale dice {_testo(web)[:300]!r}")


# ---------------------------------------------------------------- 1. la copia della Formazione
def test_una_lettura_non_riuscita_della_scelta_non_prende_il_posto_della_copia(web):
    """Una sola lettura della formazione salvata non riuscita (503): la schermata lo dice, ma la copia buona resta. Riaperta
    senza rete, la Formazione mostra i tuoi 11, non gli 11 consigliati."""
    solo_prima(web)
    rete = Rete(web.pagina)
    giornata = web.registrata("/api/formazione")["giornata"]
    salvati = sorted(web.registrata(f"/api/scelta?giornata={giornata}")["titolari"])
    web.apri("/")
    assert _titolari(web) == salvati, "il test parte dalla formazione salvata"

    rete.guasti["/api/scelta"] = 503
    _ricarica(web)
    assert "Non riesco a leggere la formazione che hai salvato" in _testo(web), _testo(web)[:300]

    rete.giu = True
    _ricarica(web)
    assert _titolari(web) == salvati, ("senza rete la Formazione mostra gli 11 consigliati come se fossero i tuoi: "
                                       f"{_titolari(web)} invece di {salvati}")


# ---------------------------------------------------------------- 2. la prima schermata con la rete lenta
def test_con_la_rete_ferma_la_copia_compare_e_poi_si_aggiorna_senza_saltare(web):
    """Con la rete ferma (nessuna /api/ risponde, nemmeno «chi sono») la Formazione salvata compare entro pochi secondi, con i
    comandi spenti; quando i dati arrivano i comandi si accendono e la pagina resta quella (niente ridisegno)."""
    solo_prima(web)
    rete = Rete(web.pagina)
    web.apri("/")
    salvati = _titolari(web)
    rete.ferme.add("*")
    web.pagina.reload(wait_until="load")
    _aspetta_il_campo(web, 7, "con la rete ferma la Formazione salvata non compare")
    assert _titolari(web) == salvati
    modulo = web.pagina.locator("main #modulo")
    assert modulo.is_disabled(), "sulla copia, finché non arrivano i dati, il modulo non si cambia"
    web.pagina.evaluate("() => { document.querySelector('#campo-formazione').dataset.prova = 'prima'; }")

    rete.lascia()
    web.pagina.wait_for_function("() => { const m = document.querySelector('main #modulo'); return m && !m.disabled; }", timeout=10000)
    web.aspetta()
    assert web.pagina.evaluate("() => document.querySelector('#campo-formazione').dataset.prova") == "prima", \
        "all'arrivo dei dati (uguali alla copia) la Formazione si è ridisegnata"
    assert _titolari(web) == salvati
    assert not web.errori_mostrati(), web.errori_mostrati()
    assert not web.errori_console, web.errori_console


def test_volti_e_funzioni_lenti_non_fermano_la_prima_schermata(web):
    """Prima apertura (nessuna copia), con i volti (/api/avatar) e le funzioni (/api/funzioni) che non arrivano: la Formazione si
    disegna lo stesso. Quando i tratti dei volti arrivano, il volto cambia al suo posto, senza ridisegnare la pagina."""
    solo_prima(web)
    rete = Rete(web.pagina)
    rete.ferme.update({"/api/avatar", "/api/funzioni"})
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    _aspetta_il_campo(web, 7, "con volti e funzioni lenti la Formazione non si disegna")
    web.aspetta()
    # il primo volto della pagina (in panchina: sul campo ci sono i dischi, senza volto)
    primo = web.pagina.evaluate("() => document.querySelector('main [data-giocatore] .avatar').closest('[data-giocatore]').dataset.giocatore")
    volto = f"main [data-giocatore='{primo}'] .avatar"
    prima = web.pagina.locator(volto).first.inner_html()
    web.pagina.evaluate("() => { document.querySelector('#campo-formazione').dataset.prova = 'prima'; }")

    rete.risposte["/api/avatar"] = (200, {"versione": 3, "tratti": {str(primo): {"p": 6, "c": 7, "a": "I", "b": 1, "f": 1}}})
    rete.lascia("/api/avatar")
    web.pagina.wait_for_function("([s, h]) => document.querySelector(s).innerHTML !== h", arg=[volto, prima], timeout=10000)
    rete.lascia("/api/funzioni")
    web.aspetta()
    assert web.pagina.evaluate("() => document.querySelector('#campo-formazione').dataset.prova") == "prima", \
        "all'arrivo dei volti la Formazione si è ridisegnata"
    assert not web.errori_console, web.errori_console


def _chi_sono_lento(web) -> Rete:
    """Con gli account e la rete ferma (anche «chi sono»): dopo circa 4 secondi la Formazione salvata dell'account 7 compare. La
    copia sta sotto il suo account: senza l'account salvato non si troverebbe."""
    rete = Rete(web.pagina)
    rete.risposte["/api/account/me"] = (200, UTENTE)
    web.apri("/")
    salvati = _titolari(web)
    rete.ferme.add("*")
    web.pagina.reload(wait_until="load")
    _aspetta_il_campo(web, 7, "con «chi sono» lento la Formazione salvata dell'account non compare")
    assert _titolari(web) == salvati
    return rete


def test_chi_sono_lento_e_poi_sessione_finita_apre_l_accesso_completo(web):
    """La risposta di «chi sono» arriva dopo e dice che la sessione è finita: compare la schermata di accesso, senza dati in vista,
    con ciò che il server ha detto nella stessa risposta: «Continua con Google» e la registrazione con l'email (revisione #948)."""
    solo_prima(web)
    rete = _chi_sono_lento(web)
    rete.risposte["/api/account/me"] = (401, SCADUTA)
    rete.lascia("/api/account/me")
    accesso = web.pagina.get_by_role("dialog", name="Accesso a SchieraXI")
    accesso.wait_for(timeout=10000)
    assert web.pagina.evaluate(TITOLARI) == [], "con la sessione finita la Formazione resta in vista"
    assert accesso.get_by_role("button", name="Continua con Google").is_visible(), "l'accesso non ha «Continua con Google»"
    accesso.get_by_role("button", name="Registrati").click(timeout=10000)
    assert accesso.get_by_text("Serve un codice d'invito e un indirizzo email").is_visible(), \
        f"la registrazione non è quella del server (con l'email): {accesso.inner_text()[:300]!r}"


def test_chi_sono_lento_e_poi_un_altro_account_ricarica_con_quello(web):
    """La risposta di «chi sono» arriva dopo con un altro account (entrato da un'altra scheda): la pagina, che mostrava la copia
    dell'account di prima, si ricarica e riparte con quello nuovo."""
    solo_prima(web)
    rete = _chi_sono_lento(web)
    rete.risposte["/api/account/me"] = (200, {"multiutente": True, "utente": ALTRO})
    try:
        with web.pagina.expect_navigation(timeout=10000):
            rete.lascia("/api/account/me")
    except Exception:                        # noqa: BLE001 - si dice cosa non è successo
        pytest.fail("«chi sono» arrivato dopo con un altro account, e la pagina resta con la copia di quello di prima")
    salvato = web.pagina.evaluate("() => JSON.parse(localStorage.getItem('account') || 'null')")
    assert salvato and salvato["id"] == ALTRO["id"], f"dopo la ricarica l'account salvato è {salvato}"


def test_impostazioni_aperta_prima_dello_stato_d_avvio_si_completa_quando_arriva(web):
    """Con lo stato d'avvio e le squadre lenti, si passa dalla Formazione a Impostazioni prima che arrivino: quando arrivano, la
    pagina mostra «La mia squadra» e «Le altre squadre» (revisione #948: restavano assenti fino a un'altra apertura)."""
    solo_prima(web)
    rete = Rete(web.pagina)
    rete.ferme.update({"/api/stato", "/api/squadre"})
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Impostazioni").click(timeout=10000)
    principale = web.pagina.locator("main")
    principale.get_by_role("heading", level=1, name="Impostazioni").wait_for(timeout=10000)
    rete.lascia("/api/stato")
    rete.lascia("/api/squadre")
    for nome in ("La mia squadra", "Le altre squadre"):
        riga = principale.get_by_role("button", name=re.compile(rf"^\s*{re.escape(nome)}"))
        try:
            riga.first.wait_for(timeout=8000)
        except Exception:                    # noqa: BLE001 - si dice cosa manca
            pytest.fail(f"arrivati stato e squadre, Impostazioni non ha «{nome}»: {_testo(web)[:300]!r}")


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_senza_rete_impostazioni_tiene_la_mia_squadra_spenta_con_una_frase(web, larghezza):
    """Collaudo d'insieme del 26/11: riaperta senza rete, Impostazioni perdeva la riga «La mia squadra» (dipendeva dall'elenco
    delle squadre, che non arriva) e lasciava un buco in «La mia lega». Ora la riga resta, spenta, con la frase che dice quando
    si apre; tornata la rete, si riaccende da sola."""
    solo_prima(web)
    rete = Rete(web.pagina)
    web.apri("/?vista=impostazioni", larghezza=larghezza)
    riga = web.pagina.locator("main").get_by_role("button", name=re.compile(r"^\s*La mia squadra"))
    assert riga.count() == 1 and riga.is_enabled()
    rete.giu = True
    web.pagina.reload(wait_until="load")
    web.aspetta()
    try:
        riga.wait_for(timeout=10000)
    except Exception:                        # noqa: BLE001 - si dice cosa manca
        pytest.fail(f"senza rete Impostazioni non ha «La mia squadra»: {_testo(web)[:300]!r}")
    assert riga.is_disabled(), "senza rete la riga si tocca, ma la pagina non si aprirebbe"
    assert "Si apre quando il server torna raggiungibile" in riga.inner_text(), riga.inner_text()
    voci = web.pagina.locator("#imp-lega li").all_inner_texts()
    assert [v.split("\n")[0].strip() for v in voci][:3] == ["Aggiorna le rose", "La mia squadra", "Regole e scadenza"], voci
    assert not web.scorre_di_lato()
    rete.giu = False
    web.pagina.evaluate("() => window.dispatchEvent(new Event('online'))")
    try:
        web.pagina.wait_for_function("""() => [...document.querySelectorAll('main button')].some(b =>
          b.innerText.trim().startsWith('La mia squadra') && !b.disabled)""", timeout=10000)
    except Exception:                        # noqa: BLE001
        pytest.fail(f"tornata la rete «La mia squadra» resta spenta: {_testo(web)[:300]!r}")


# ---------------------------------------------------------------- 3. le prossime partite nella scheda
def _calendario_vecchio(web) -> dict:
    """Il calendario registrato con le partite cambiate: tutte contro lo Spezia (che nel calendario registrato non c'è), «Molto
    dura». Come una copia di settimane prima."""
    cal = web.registrata("/api/calendario")
    for s in cal["squadre"]:
        s["partite"] = [{**p, "avversario": "spezia", "difficolta": 5} for p in s["partite"]]
    return cal


AVVERSARI = """() => [...document.querySelectorAll('[role="dialog"] .prossime > *')]
  .map(c => (c.querySelector('[aria-hidden]') || c).textContent.trim())"""


def _apri_tutti_i_numeri(web) -> tuple[str, list[str]]:
    """La Formazione, poi la scheda del primo titolare con «Tutti i numeri» aperto. Restituisce il giocatore e gli avversari
    delle sue prossime partite nel calendario registrato («vs CAG», «@ UDI»…)."""
    web.apri("/")
    pedina = web.pagina.locator("main #campo-formazione").get_by_role("button").first
    id_giocatore = pedina.get_attribute("data-giocatore")
    pedina.click(timeout=10000)
    web.pagina.get_by_role("dialog").get_by_text("Tutti i numeri").click(timeout=10000)
    squadra = web.registrata(f"/api/giocatore/{id_giocatore}")["previsione"]["squadra"]
    partite = next(s for s in web.registrata("/api/calendario")["squadre"] if s["squadra"] == squadra)["partite"]
    assert partite and all(p["avversario"] != "spezia" for p in partite), "il calendario registrato deve essere diverso dalla copia"
    return squadra, [f"{'vs' if p['in_casa'] else '@'} {web.pagina.evaluate('(s) => sigla(s)', p['avversario'])}" for p in partite]


def _con_la_copia_del_calendario(web) -> None:
    """Nel browser la copia di un calendario vecchio, salvata da una sessione di prima."""
    copia = {"quando": 0, "lingua": "it", "dati": _calendario_vecchio(web)}
    web.memoria({"cache:3:calendario": json.dumps(copia)})


def test_la_prima_scheda_mostra_le_prossime_partite_del_calendario_nuovo(web):
    """La prima scheda della sessione, con una copia vecchia del calendario nel browser e il calendario che arriva tardi: le
    prossime partite sono quelle nuove (arrivate dopo), non quelle della copia."""
    solo_prima(web)
    rete = Rete(web.pagina)
    _con_la_copia_del_calendario(web)
    rete.ferme.add("/api/calendario")
    _, attese = _apri_tutti_i_numeri(web)
    # intanto, passata la breve attesa, le partite della copia (revisione #948: così si prova il ridisegno)
    web.pagina.wait_for_function(f"() => {{ const v = ({AVVERSARI})(); return v.length > 0 && v.every(x => x.endsWith('SPE')); }}",
                                 timeout=8000)
    rete.lascia("/api/calendario")
    try:
        web.pagina.wait_for_function(f"(attese) => JSON.stringify(({AVVERSARI})()) === JSON.stringify(attese)", arg=attese, timeout=8000)
    except Exception:                        # noqa: BLE001 - si dice cosa si vede
        pytest.fail(f"le prossime partite non sono quelle del calendario nuovo: {web.pagina.evaluate(AVVERSARI)} invece di {attese}")


def test_senza_calendario_la_scheda_usa_la_copia(web):
    """Se il calendario non arriva (errore del server), le prossime partite vengono dalla copia: meglio di niente."""
    solo_prima(web)
    rete = Rete(web.pagina)
    _con_la_copia_del_calendario(web)
    rete.guasti["/api/calendario"] = 503
    _apri_tutti_i_numeri(web)
    web.pagina.get_by_role("dialog").get_by_role("heading", name="Prossime partite").wait_for(timeout=10000)
    visti = web.pagina.evaluate(AVVERSARI)
    assert visti and all(v.endswith("SPE") for v in visti), visti


# ---------------------------------------------------------------- 4. un'altra scheda, un altro account
SEGNI = """() => { window.__ricarica = false; window.__eventi = 0;
  addEventListener('beforeunload', () => { window.__ricarica = true; });
  addEventListener('storage', () => { window.__eventi++; }); }"""


def _due_schede(web):
    """La web aperta con un account (id 7) e un'altra scheda dello stesso sito, che cambia la memoria del browser come fanno
    «Esci» o un altro accesso."""
    rete = Rete(web.pagina)
    rete.risposte["/api/account/me"] = (200, UTENTE)
    web.apri("/")
    altra = web.pagina.context.new_page()
    altra.goto(web.server.indirizzo + "/icona.svg", wait_until="load")          # stesso sito, stessa memoria
    web.pagina.evaluate(SEGNI)
    return altra


@pytest.mark.parametrize("cosa", ["esce", "entra un altro"])
def test_un_altra_scheda_che_cambia_account_fa_ricaricare_questa(web, cosa):
    solo_prima(web)
    altra = _due_schede(web)
    cambia = ("() => localStorage.removeItem('account')" if cosa == "esce"
              else f"() => localStorage.setItem('account', {json.dumps(json.dumps(ALTRO))})")
    try:
        with web.pagina.expect_navigation(timeout=5000):
            altra.evaluate(cambia)
    except Exception:                        # noqa: BLE001 - si dice cosa non è successo
        pytest.fail(f"l'altra scheda {cosa}, e questa non si ricarica: salverebbe i dati sotto l'account di prima")


def test_un_altra_scheda_con_lo_stesso_account_non_fa_ricaricare(web):
    """L'altra scheda riscrive lo stesso account (all'apertura, con il nome cambiato): questa non si ricarica."""
    solo_prima(web)
    altra = _due_schede(web)
    stesso = {**UTENTE["utente"], "nome_visualizzato": "Amico con un nome nuovo"}
    altra.evaluate(f"() => localStorage.setItem('account', {json.dumps(json.dumps(stesso))})")
    web.pagina.wait_for_function("() => window.__eventi >= 1", timeout=5000)
    assert web.pagina.evaluate("() => window.__ricarica") is False, "lo stesso account riscritto da un'altra scheda la ricarica"
