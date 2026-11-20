"""La barra a tre voci e le Impostazioni uniche (#618): Formazione, Giornate, Impostazioni più la ricerca; «Squadra» e «Altro» non
sono più schede e ciò che restava di loro sta in Impostazioni > La mia lega. Un utente normale vede al massimo una decina di
controlli; «Gestione» solo chi gestisce il server. Ogni indirizzo di prima apre la voce giusta, e i valori salvati nel browser da
una versione di prima non rompono niente.

Si guarda ciò che vede chi usa l'app (ruoli, nomi, cosa succede a un tocco), non il sorgente. I test che non dipendono dalla fase
della giornata girano solo prima della scadenza (`solo`).
"""
import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest

PC = 1440
UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
AMMINISTRATORE = {**UTENTE, "utente": {**UTENTE["utente"], "ruolo": "amministratore"}}
# Un controllo è ciò che si tocca o si scrive; i pulsanti di un gruppo (il tema, la lingua) contano una volta sola.
CONTROLLI = """() => {
  const visto = e => { const r = (e.matches('input[type=checkbox], input[type=radio]') && e.closest('label')) || e;
    return r.getClientRects().length > 0 && getComputedStyle(r).visibility !== 'hidden'; };
  const tutti = [...document.querySelectorAll('main a[href], main button, main input:not([type=hidden]), main select, main textarea, main summary')]
    .filter(visto);
  const gruppi = new Set(), nomi = [];
  for (const e of tutti) {
    const g = e.closest('[role=group], [role=radiogroup]');
    if (g) { if (gruppi.has(g)) continue; gruppi.add(g); nomi.push(g.getAttribute('aria-label') || 'gruppo'); continue; }
    nomi.push((e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.innerText || e.tagName).trim().split('\\n')[0]);
  }
  return nomi;
}"""


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def titolo(web) -> str:
    return principale(web).get_by_role("heading", level=1).inner_text().strip()


def tocca(web, bersaglio) -> None:
    (web.pagina.locator(bersaglio).first if isinstance(bersaglio, str) else bersaglio).click(timeout=10000)
    web.aspetta()


def barra(web):
    return web.pagina.get_by_role("navigation", name="Sezioni")


def voce(web, nome: str):
    """Una riga di Impostazioni che apre una pagina: un pulsante il cui nome comincia con `nome`."""
    return principale(web).get_by_role("button", name=re.compile(rf"^\s*{re.escape(nome)}"))


def sezione(web, nome: str):
    return principale(web).get_by_role("region", name=nome, exact=True)


def nel_primo_schermo(web, locator) -> bool:
    b = locator.bounding_box()
    return b is not None and 0 <= b["y"] < web.pagina.viewport_size["height"]


def da_utente(web, chi=UTENTE) -> None:
    web.risposta("/api/account/me", chi)


# ---------------------------------------------------------------- la barra
@pytest.mark.parametrize("larghezza", [390, PC])
def test_la_barra_ha_tre_voci_e_la_ricerca(web, larghezza):
    web.apri("/", larghezza=larghezza)
    schede = [" ".join(v.split()) for v in barra(web).get_by_role("link").all_inner_texts()]
    assert schede == ["Formazione", "Giornate", "Impostazioni"], schede
    cerca = web.pagina.get_by_role("button", name="Cerca un giocatore").or_(web.pagina.get_by_role("searchbox", name="Cerca un giocatore"))
    assert cerca.first.is_visible()
    # le impostazioni sono una voce della barra: niente ingranaggio in testata, niente pulsante «Impostazioni» a parte
    assert web.pagina.get_by_role("button", name="Impostazioni", exact=True).count() == 0
    assert not web.scorre_di_lato() and not web.errori_console


def test_impostazioni_si_apre_con_un_tocco_dalla_barra(web):
    solo(web, "prima")
    web.apri("/")
    tocca(web, barra(web).get_by_role("link", name="Impostazioni"))
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith("/?vista=impostazioni")
    assert barra(web).get_by_role("link", name="Impostazioni").get_attribute("aria-current") == "page"
    for nome in ("Avvisi", "La mia lega", "Aspetto"):
        assert sezione(web, nome).is_visible(), nome
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


# ---------------------------------------------------------------- quanti controlli, e chi vede Gestione
def test_un_utente_normale_vede_al_massimo_dieci_controlli(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni")
    controlli = web.pagina.evaluate(CONTROLLI)
    assert len(controlli) <= 10, controlli
    for nome in ("Aggiorna le rose", "La mia squadra", "Regole e scadenza", "Il tuo account", "Informazioni"):
        assert voce(web, nome).is_visible(), nome
    assert voce(web, "Gestione").count() == 0
    assert "Notifiche" not in web.testo_principale()                     # gli avvisi si chiamano «Avvisi», come nella spec
    assert not web.errori_mostrati() and not web.errori_console


def test_gestione_solo_per_chi_gestisce_il_server(web):
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    web.apri("/?vista=impostazioni")
    tocca(web, voce(web, "Gestione"))
    assert titolo(web) == "Gestione"
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=gestione")
    testo = web.testo_principale()
    assert "Stato dei dati" in testo and "Nuovo invito" in testo
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_visible()   # le frecce della testata stanno qui


# ---------------------------------------------------------------- «Aggiorna i dati» mentre il server aggiorna da solo (#763)
FRASE_IN_CORSO = re.compile("occupato con un aggiornamento")


def stato_aggiornamento(web, in_corso: bool) -> None:
    """Da qui /api/stato risponde come quello registrato, con `aggiornamento_in_corso` scelto."""
    s = web.registrata("/api/stato")
    s["aggiornamento_in_corso"] = in_corso
    web.risposta("/api/stato", s)


def orologio_comandato(web) -> None:
    """Il tempo della pagina parte da «adesso» dello scenario, scorre da sé e si porta avanti con `clock.fast_forward`."""
    istante = web.pagina.evaluate("(s) => new Date(s).getTime()", web.server.adesso)
    web.pagina.clock.install(time=istante / 1000)


def letture_stato(web) -> int:
    return web.richieste.count("/api/stato")


def test_aggiorna_i_dati_spento_finche_il_server_aggiorna_da_solo(web):
    """L'aggiornamento programmato del server è in corso (`aggiornamento_in_corso` di /api/stato): in Gestione «Aggiorna i dati»
    è spento e una frase dice perché. Con la schermata aperta lo stato si rilegge ogni 15-20 secondi; quando l'aggiornamento è
    finito il pulsante si riaccende, la frase sparisce e le letture smettono."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    stato_aggiornamento(web, True)
    orologio_comandato(web)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    pulsante = principale(web).get_by_role("button", name="Aggiorna i dati")
    assert pulsante.is_disabled()
    assert principale(web).get_by_text(FRASE_IN_CORSO).is_visible()
    prima = letture_stato(web)
    web.pagina.clock.fast_forward(20_000)
    web.aspetta()
    assert letture_stato(web) == prima + 1                    # ancora in corso: spento, si rilegge ancora
    assert pulsante.is_disabled() and principale(web).get_by_text(FRASE_IN_CORSO).is_visible()
    stato_aggiornamento(web, False)
    web.pagina.clock.fast_forward(20_000)
    web.aspetta()
    assert letture_stato(web) == prima + 2
    assert pulsante.is_enabled()
    assert principale(web).get_by_text(FRASE_IN_CORSO).count() == 0
    web.pagina.clock.fast_forward(60_000)
    web.aspetta()
    assert letture_stato(web) == prima + 2                    # finito: niente altre letture
    # (inviti e utenti di Gestione non sono nello scenario registrato: le loro 404 qui non contano)
    assert not [e for e in web.errori_console if e.startswith("errore nel codice")], web.errori_console
    assert not [r for r in web.richieste_fallite if "/api/stato" in r], web.richieste_fallite


def test_gestione_rilegge_subito_lo_stato_letto_prima(web):
    """Lo stato letto prima, all'apertura dell'app, diceva «aggiornamento in corso»; nel frattempo è finito. Entrando in Gestione
    lo stato si rilegge subito, non dopo 15 secondi: il pulsante è già acceso e la frase non c'è."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    stato_aggiornamento(web, True)
    web.apri("/?vista=impostazioni")
    prima = letture_stato(web)
    stato_aggiornamento(web, False)
    tocca(web, voce(web, "Gestione"))
    assert letture_stato(web) == prima + 1
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_enabled()
    assert principale(web).get_by_text(FRASE_IN_CORSO).count() == 0


def test_fuori_da_gestione_lo_stato_non_si_rilegge(web):
    """Con l'aggiornamento in corso si esce da Gestione: lo stato non si rilegge più (la lettura serve solo al pulsante)."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    stato_aggiornamento(web, True)
    orologio_comandato(web)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_disabled()
    tocca(web, barra(web).get_by_role("link", name="Formazione"))
    prima = letture_stato(web)
    for _ in range(3):
        web.pagina.clock.fast_forward(20_000)
        web.aspetta()
    assert letture_stato(web) == prima


def test_una_lettura_dello_stato_alla_volta(web):
    """Una lettura dello stato che tarda non ne fa partire altre: la prossima si prepara solo quando la risposta è arrivata."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    stato_aggiornamento(web, True)
    orologio_comandato(web)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    ferme = []
    web.pagina.route("**/api/stato", lambda r: ferme.append(r))     # le letture da qui restano senza risposta finché non si sblocca
    for _ in range(4):
        web.pagina.clock.fast_forward(20_000)
        web.pagina.evaluate("() => new Promise(fatto => setTimeout(fatto, 0))")
    assert len(ferme) == 1, f"{len(ferme)} letture insieme"
    s = web.registrata("/api/stato")
    s["aggiornamento_in_corso"] = False
    ferme[0].fulfill(status=200, content_type="application/json; charset=utf-8", body=json.dumps(s))
    web.aspetta()
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_enabled()


def test_aggiorna_i_dati_con_il_server_gia_occupato_lo_dice(web):
    """Il pulsante acceso, ma il server risponde che un aggiornamento è già in corso: lo dice un avviso, come prima (#760)."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    stato_aggiornamento(web, False)
    web.risposta("/api/aggiorna", {"avviato": False, "messaggio": "Aggiornamento già in corso"})
    web.apri("/?vista=impostazioni&gruppo=gestione")
    principale(web).get_by_role("button", name="Aggiorna i dati").click(timeout=10000)
    web.pagina.get_by_role("status").filter(has_text="Aggiornamento già in corso").first.wait_for(timeout=5000)
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_enabled()
    assert principale(web).get_by_text(FRASE_IN_CORSO).count() == 0


@pytest.mark.parametrize("indirizzo", ["/?vista=impostazioni&gruppo=gestione", "/?vista=impostazioni&gruppo=avanzate"])
def test_chi_non_gestisce_il_server_non_apre_gestione_neanche_con_l_indirizzo(web, indirizzo):
    solo(web, "prima")
    da_utente(web)
    web.apri(indirizzo)
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith("/?vista=impostazioni")
    assert "Nuovo invito" not in web.testo_principale() and voce(web, "Gestione").count() == 0
    assert not web.errori_mostrati()


# ---------------------------------------------------------------- gli indirizzi di prima
@pytest.mark.parametrize("vecchio, nuovo, atteso", [
    ("/?vista=squadra", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=altro", "/?vista=impostazioni", None),
    ("/?vista=lega", "/?vista=impostazioni", None),
    ("/?vista=mercato", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=mercato&scheda=osservati", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=scambi", "/?vista=impostazioni", None),
    ("/?vista=altro&voce=movimenti", "/?vista=impostazioni", None),
    ("/?vista=altro&voce=stagione", "/?vista=impostazioni", None),
    ("/?vista=impostazioni&gruppo=avvisi", "/?vista=impostazioni", "Avvisi"),
    ("/?vista=impostazioni&gruppo=aspetto", "/?vista=impostazioni", "Aspetto"),
    ("/?vista=impostazioni&gruppo=sconosciuto", "/?vista=impostazioni", None),
])
def test_un_indirizzo_di_prima_apre_impostazioni(web, vecchio, nuovo, atteso):
    solo(web, "prima")
    web.apri(vecchio)
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith(nuovo), web.pagina.url
    if atteso:
        assert nel_primo_schermo(web, sezione(web, atteso).get_by_role("heading", name=atteso)), f"{vecchio}: «{atteso}» non si vede"
    assert barra(web).get_by_role("link", name="Impostazioni").get_attribute("aria-current") == "page"
    assert not web.errori_mostrati() and not web.errori_console


@pytest.mark.parametrize("vecchio, nuovo, atteso", [
    ("/?vista=squadra&voce=importa", "/?vista=impostazioni&gruppo=rose", "Aggiorna le rose"),
    ("/?vista=lega&voce=importa", "/?vista=impostazioni&gruppo=rose", "Aggiorna le rose"),
    ("/?vista=squadra&voce=squadre", "/?vista=impostazioni&gruppo=squadre", "Le altre squadre"),
    ("/?vista=altro&voce=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=lega&voce=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=altro&voce=novita", "/?vista=impostazioni&gruppo=informazioni", "Informazioni"),
    ("/?vista=impostazioni&gruppo=informazioni", "/?vista=impostazioni&gruppo=informazioni", "Informazioni"),
    ("/?vista=impostazioni&gruppo=avanzate", "/?vista=impostazioni&gruppo=gestione", "Gestione"),     # sul server senza account si gestisce
])
def test_un_indirizzo_di_prima_apre_la_sua_pagina(web, vecchio, nuovo, atteso):
    solo(web, "prima")
    web.risposta("/api/novita", [])                                      # Informazioni le chiede: lo scenario registrato non le ha
    web.apri(vecchio)
    assert titolo(web) == atteso
    assert web.pagina.url.endswith(nuovo), web.pagina.url
    assert principale(web).get_by_role("button", name="Impostazioni").is_visible()        # si torna indietro
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


@pytest.mark.parametrize("vecchio", ["/?vista=squadra&rosa=", "/?vista=rosa", "/?vista=squadra&rosa=Squadra%20Demo"])
def test_l_indirizzo_della_mia_rosa_apre_la_mia_squadra(web, vecchio):
    solo(web, "prima")
    mia = web.registrata("/api/rosa")["nome"]
    web.apri(vecchio)
    assert titolo(web) == mia
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadra")
    assert "Portieri" in web.testo_principale()
    assert not web.errori_mostrati() and not web.errori_console


def test_l_indirizzo_della_rosa_di_un_altra_squadra_la_apre(web):
    solo(web, "prima")
    web.apri("/?vista=squadra&rosa=Real%20Esempio")
    assert titolo(web) == "Real Esempio"
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadre&rosa=Real+Esempio")
    tocca(web, principale(web).get_by_role("button", name="Le altre squadre"))
    assert titolo(web) == "Le altre squadre"
    assert not web.errori_mostrati() and not web.errori_console


def test_l_indirizzo_di_un_account_senza_account_apre_impostazioni(web):
    """Sul server senza account la voce «Il tuo account» non c'è: il suo indirizzo apre Impostazioni, senza errori."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=account")
    assert titolo(web) == "Impostazioni" and web.pagina.url.endswith("/?vista=impostazioni")
    assert voce(web, "Il tuo account").count() == 0 and not web.errori_mostrati()


def test_con_un_account_l_indirizzo_dell_account_apre_l_account(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    assert titolo(web) == "Il tuo account"
    assert principale(web).get_by_role("button", name="Esci", exact=True).is_visible()


# ---------------------------------------------------------------- Esci da tutti i dispositivi (#765)
ESCI_TUTTI = "Esci da tutti i dispositivi"


def uscita_ovunque(web, stato: int | None = 200) -> list[str]:
    """Il server di «Esci da tutti»: la rotta risponde con `stato` (None: la richiesta non arriva). Se riesce, da lì ogni
    /api/... risponde 401 come il server vero a sessioni chiuse. Restituisce i metodi delle richieste arrivate alla rotta."""
    arrivate, uscito = [], []
    a_sessione_chiusa = json.dumps({"detail": "Serve l'accesso", "multiutente": True})

    def altre(route):
        if uscito:
            route.fulfill(status=401, content_type="application/json; charset=utf-8", body=a_sessione_chiusa)
        else:
            route.fallback()

    def esci(route):
        arrivate.append(route.request.method)
        if stato is None:
            route.abort()
            return
        if stato == 200:
            uscito.append(True)
        route.fulfill(status=stato, content_type="application/json; charset=utf-8",
                      body=json.dumps({"sessioni_chiuse": 3} if stato == 200 else {}))

    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), altre)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/esci-da-tutti", esci)
    return arrivate


def chiavi_salvate(web) -> list[str]:
    """Le copie dei dati e l'account lasciati nel browser (localStorage)."""
    return [k for k in web.pagina.evaluate("Object.keys(localStorage)") if k.startswith("cache:") or k == "account"]


def test_esci_da_tutti_chiede_conferma_ed_esce_ovunque(web):
    """Il pulsante consigliato dalle email di sicurezza c'è in Il tuo account. La conferma dice che si esce ovunque, anche da qui,
    e che si dovrà rientrare; dopo l'uscita si torna alla pagina d'accesso e nel browser non restano copie dei dati né l'account."""
    solo(web, "prima")
    da_utente(web)
    web.apri("/")                                              # la Formazione lascia nel browser le sue copie
    assert chiavi_salvate(web), "la prova vuole delle copie da togliere"
    web.apri("/?vista=impostazioni&gruppo=account")
    arrivate = uscita_ovunque(web)
    domande = []

    def rispondi(dialogo):
        domande.append(dialogo.message)
        dialogo.accept()

    web.pagina.on("dialog", rispondi)
    principale(web).get_by_role("button", name=ESCI_TUTTI).click(timeout=10000)
    web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI")).wait_for(timeout=10000)
    assert len(domande) == 1, domande
    assert all(parte in domande[0] for parte in ("tutti i dispositivi", "anche da questo", "accedere di nuovo")), domande
    assert arrivate == ["POST"]
    assert chiavi_salvate(web) == []


USCITO_OVUNQUE = "Sei fuori da tutti i dispositivi"


def test_dopo_esci_da_tutti_l_accesso_dice_che_l_uscita_e_riuscita(web):
    """Confermato «Esci da tutti i dispositivi» si tornava all'accesso senza una parola (#779): ora un avviso (`role="status"`, non
    un errore) dice che l'uscita è riuscita. Una volta sola: ricaricata la pagina, l'accesso torna quello di sempre."""
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    uscita_ovunque(web)
    web.pagina.on("dialog", lambda dialogo: dialogo.accept())
    principale(web).get_by_role("button", name=ESCI_TUTTI).click(timeout=10000)
    accesso = web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI"))
    accesso.get_by_role("status").filter(has_text=USCITO_OVUNQUE).wait_for(timeout=10000)
    allarmi = [t for t in web.pagina.locator('[role="alert"]').all_inner_texts() if t.strip()]
    assert allarmi == [], allarmi
    web.pagina.reload(wait_until="load")
    accesso.get_by_role("button", name="Accedi").first.wait_for(timeout=10000)
    assert USCITO_OVUNQUE not in accesso.inner_text()


def test_dopo_esci_normale_niente_frase_di_esci_da_tutti(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    uscito = []
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/esci",
                     lambda route: uscito.append(1) or route.fulfill(status=200, content_type="application/json", body='{"ok": true}'))
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/") and urlsplit(u).path != "/api/account/esci",
                     lambda route: route.fulfill(status=401, content_type="application/json",
                                                 body=json.dumps({"detail": "Serve l'accesso", "multiutente": True})) if uscito
                     else route.fallback())
    principale(web).get_by_role("button", name="Esci", exact=True).click(timeout=10000)
    accesso = web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI"))
    accesso.get_by_role("button", name="Accedi").first.wait_for(timeout=10000)
    web.aspetta()
    assert uscito and USCITO_OVUNQUE not in accesso.inner_text()


GOOGLE = [{"provider": "google", "email": "nome@example.invalid", "creata": "2026-10-01T10:00:00", "ultimo_uso": None}]


@pytest.mark.parametrize("password, social, dice_google", [(True, GOOGLE, True), (False, GOOGLE, False), (True, [], False)],
                         ids=["google-e-password", "solo-google", "senza-google"])
def test_esci_da_tutti_dice_di_google_solo_a_chi_perde_il_collegamento(web, password, social, dice_google):
    """Il server toglie il collegamento con Google a chi ha una password (dopo, «Continua con Google» non fa entrare finché non si
    ricollega); chi entra solo con Google lo tiene. La conferma lo dice solo a chi lo perde, leggendo `accessi` del server."""
    solo(web, "prima")
    da_utente(web, {**UTENTE, "social": ["google"], "accessi": {"password": password, "social": social, "disponibili": ["google"]}})
    web.apri("/?vista=impostazioni&gruppo=account")
    arrivate = uscita_ovunque(web)
    domande = []

    def rispondi(dialogo):
        domande.append(dialogo.message)
        dialogo.dismiss()

    web.pagina.on("dialog", rispondi)
    tocca(web, principale(web).get_by_role("button", name=ESCI_TUTTI))
    assert len(domande) == 1 and "anche da questo" in domande[0], domande
    assert ("Il collegamento con Google si toglie" in domande[0]) is dice_google, domande
    assert arrivate == []


def test_esci_da_tutti_annullato_non_fa_niente(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    arrivate = uscita_ovunque(web)
    web.pagina.on("dialog", lambda dialogo: dialogo.dismiss())
    tocca(web, principale(web).get_by_role("button", name=ESCI_TUTTI))
    assert arrivate == []
    assert titolo(web) == "Il tuo account"


@pytest.mark.parametrize("stato", [500, None], ids=["errore-del-server", "rete-giu"])
def test_esci_da_tutti_non_riuscito_lo_dice_e_resta_dentro(web, stato):
    """Se la richiesta non riesce gli altri dispositivi sono ancora dentro: un avviso lo dice, si resta nella pagina e le copie
    restano (come per «Esci» dal #800: test_esci_non_riuscito_lo_dice_e_resta_dentro)."""
    solo(web, "prima")
    da_utente(web)
    web.apri("/")
    web.apri("/?vista=impostazioni&gruppo=account")
    prima = chiavi_salvate(web)
    arrivate = uscita_ovunque(web, stato)
    web.pagina.on("dialog", lambda dialogo: dialogo.accept())
    tocca(web, principale(web).get_by_role("button", name=ESCI_TUTTI))
    web.pagina.get_by_role("status").filter(has_text="Non riesco a farti uscire da tutti i dispositivi").wait_for(timeout=10000)
    assert arrivate == ["POST"]
    assert titolo(web) == "Il tuo account"
    assert principale(web).get_by_role("button", name=ESCI_TUTTI).is_visible()
    assert chiavi_salvate(web) == prima


# ---------------------------------------------------------------- valori salvati da versioni di prima
@pytest.mark.parametrize("salvata, atteso", [("squadra", "Formazione"), ("altro", "Formazione"), ("oggi", "Formazione"),
                                             ("mercato", "Formazione"), ("lega", "Formazione"), ("impostazioni", "Formazione"),
                                             ("__proto__", "Formazione"), ("giornate", "Giornate")])
def test_la_schermata_salvata_da_una_versione_di_prima_non_rompe_l_avvio(web, salvata, atteso):
    """L'app si riapre sull'ultima schermata (Formazione o Giornate). Una scheda che non c'è più (Squadra, Altro...) salvata da una
    versione di prima apre la Formazione: si riapre per schierare, non sulle impostazioni."""
    solo(web, "prima")
    web.memoria({"vista": salvata})
    web.apri("/")
    assert titolo(web) == atteso
    assert not web.errori_mostrati() and not web.errori_console


def test_indietro_torna_alle_impostazioni_e_poi_alla_formazione(web):
    solo(web, "prima")
    web.apri("/")
    tocca(web, barra(web).get_by_role("link", name="Impostazioni"))
    tocca(web, voce(web, "Regole e scadenza"))
    assert titolo(web) == "Regole e scadenza"
    web.pagina.go_back()
    web.aspetta()
    assert titolo(web) == "Impostazioni"
    web.pagina.go_back()
    web.aspetta()
    assert titolo(web) == "Formazione"


def test_il_pulsante_impostazioni_di_una_pagina_torna_all_elenco(web):
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=regole")                       # aperta da un indirizzo: niente voce di prima
    tocca(web, principale(web).get_by_role("button", name="Impostazioni"))
    assert titolo(web) == "Impostazioni" and web.pagina.url.endswith("/?vista=impostazioni")


# ---------------------------------------------------------------- La mia lega
def test_la_mia_lega_porta_alla_mia_squadra_e_alle_altre(web):
    solo(web, "prima")
    mia = web.registrata("/api/rosa")["nome"]
    web.apri("/?vista=impostazioni")
    riga = voce(web, "La mia squadra")
    assert mia in riga.inner_text()                                      # la riga dice qual è
    tocca(web, riga)
    assert titolo(web) == mia and web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadra")
    assert "Portieri" in web.testo_principale()
    assert principale(web).get_by_role("button", name="Stemma e maglia").is_visible()   # senza immagini, solo il pulsante (#779)
    assert principale(web).get_by_text("Non è la tua squadra?").is_visible()
    tocca(web, principale(web).get_by_role("button", name="Impostazioni"))
    tocca(web, voce(web, "Le altre squadre"))
    assert titolo(web) == "Le altre squadre"
    tocca(web, principale(web).get_by_role("button", name=re.compile(r"^\s*Real Esempio")))
    assert titolo(web) == "Real Esempio"
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


def test_la_mia_squadra_senza_costo_ne_immagini_non_mostra_parole_vuote(web):
    """Una lega senza costi d'acquisto: ogni riga diceva «costo –» (#779). Senza costo la parola non c'è, la quotazione resta;
    un costo 0 è un costo e si mostra. Senza stemma né maglia non restano le due parole «Stemma» e «Maglia» in uno spazio vuoto:
    resta il pulsante «Stemma e maglia» per caricarli."""
    solo(web, "prima")
    rosa = web.registrata("/api/rosa")
    for g in rosa["giocatori"]:
        g["costo"] = None
    rosa["giocatori"][0]["costo"] = 0
    web.risposta("/api/rosa", rosa)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    testo = " ".join(web.testo_principale().split())
    assert "costo –" not in testo and len(re.findall(r"\bcosto\b", testo)) == 1 and "costo 0 · quotazione" in testo, testo[:600]
    assert len(re.findall(r"\bquotazione \d", testo)) == len(rosa["giocatori"])
    assert principale(web).get_by_text("Stemma", exact=True).count() == 0
    assert principale(web).get_by_text("Maglia", exact=True).count() == 0
    assert principale(web).get_by_role("button", name="Stemma e maglia").is_visible()


@pytest.mark.parametrize("scelta", [True, False], ids=["mia-scelta", "mia-non-scelta"])
def test_le_altre_squadre_contano_ed_elencano_solo_le_altre(web, scelta):
    """«Le altre squadre · 10 squadre» elencava anche la mia (#779): la mia sta già in «La mia squadra». Il numero della riga e
    l'elenco dicono le stesse squadre, senza la mia; finché la mia non è scelta sono tutte."""
    solo(web, "prima")
    squadre = web.registrata("/api/squadre")
    mia = next(s["nome"] for s in squadre if s["mia"])
    if not scelta:
        for s in squadre:
            s["mia"] = False
        web.risposta("/api/squadre", squadre)
    web.apri("/?vista=impostazioni")
    riga = voce(web, "Le altre squadre")
    quante = int(re.search(r"(\d+) squadr", riga.inner_text()).group(1))
    tocca(web, riga)
    assert titolo(web) == "Le altre squadre"
    nomi = [b.inner_text() for b in principale(web).get_by_role("listitem").get_by_role("button").all()]
    attese = len(squadre) - (1 if scelta else 0)
    assert quante == len(nomi) == attese, (quante, nomi)
    assert any(mia in n for n in nomi) is not scelta, nomi
    assert not any("la tua" in n for n in nomi), nomi


def test_le_altre_squadre_con_la_sola_mia_squadra_lo_dicono(web):
    """Con le rose della sola mia squadra la riga non c'è, ma la pagina si apre dal suo indirizzo: diceva «Importa prima le rose…»,
    falso perché le rose ci sono (#779). Ora dice che nella lega c'è solo la mia squadra e niente elenco."""
    solo(web, "prima")
    mia = next(s for s in web.registrata("/api/squadre") if s["mia"])
    web.risposta("/api/squadre", [mia])
    web.apri("/?vista=impostazioni&gruppo=squadre")
    assert titolo(web) == "Le altre squadre"
    testo = " ".join(web.testo_principale().split())
    assert "solo la tua squadra" in testo and "Importa prima" not in testo, testo
    assert principale(web).get_by_role("listitem").count() == 0
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


def _mia_con_stemma(web) -> str:
    """La mia squadra con lo stemma già caricato (la maglia no); dà il suo nome. Le immagini rispondono con un corpo finto: niente
    404 per l'anteprima, e la cancellazione riesce."""
    squadre = web.registrata("/api/squadre")
    mia = next(s for s in squadre if s["mia"])
    mia["immagini"] = {"stemma": True, "maglia": False}
    web.risposta("/api/squadre", squadre)
    web.risposta("/api/squadre/immagine", {"ok": True})
    return mia["nome"]


def test_lo_stemma_sbagliato_si_toglie_da_la_mia_squadra(web):
    """Uno stemma caricato per sbaglio si toglie da La mia squadra: «Stemma e maglia» apre il foglio con «Rimuovi». Il server finto
    ricorda la cancellazione (dopo, /api/squadre dice che lo stemma non c'è più): la rosa sotto il foglio si ridisegna senza."""
    solo(web, "prima")
    nome = _mia_con_stemma(web)
    squadre, tolte = web.registrata("/api/squadre"), []

    def immagine(rotta):
        if rotta.request.method == "DELETE":
            tolte.append(parse_qs(urlsplit(rotta.request.url).query))
        rotta.fulfill(status=200, content_type="application/json", body='{"ok": true}')

    def elenco(rotta):
        for s in squadre:
            s["immagini"] = {"stemma": s["mia"] and not tolte, "maglia": False}
        rotta.fulfill(status=200, content_type="application/json", body=json.dumps(squadre))

    web.pagina.route(lambda u: urlsplit(u).path == "/api/squadre/immagine", immagine)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/squadre", elenco)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    stemma_in_pagina = principale(web).locator("img[alt='Stemma']")
    assert stemma_in_pagina.count() == 1
    tocca(web, principale(web).get_by_role("button", name="Stemma e maglia"))
    foglio = web.pagina.get_by_role("dialog")
    assert foglio.get_by_role("combobox").input_value() == nome          # il foglio è sulla squadra della pagina
    rimuovi = foglio.get_by_role("button", name="Rimuovi")
    assert rimuovi.count() == 1                                          # solo lo stemma è caricato
    rimuovi.click()
    web.pagina.locator("#avviso").filter(has_text="Stemma rimosso").wait_for(timeout=10000)
    web.aspetta()
    assert tolte == [{"squadra": [nome], "tipo": ["stemma"]}]
    assert foglio.get_by_role("button", name="Rimuovi").count() == 0     # il foglio si ridisegna: niente più da togliere
    assert stemma_in_pagina.count() == 0, "la rosa sotto il foglio mostra ancora lo stemma tolto"
    assert foglio.is_visible() and titolo(web) == nome                   # il foglio resta aperto sulla rosa
    assert not web.errori_console and not web.richieste_fallite


def test_lo_stemma_si_prende_anche_da_un_indirizzo_web(web):
    """Con «Immagini da indirizzo web» acceso (lo scenario registrato ce l'ha) il foglio di La mia squadra lo offre."""
    solo(web, "prima")
    _mia_con_stemma(web)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    tocca(web, principale(web).get_by_role("button", name="Stemma e maglia"))
    foglio = web.pagina.get_by_role("dialog")
    assert foglio.get_by_role("button", name="Da indirizzo web").count() == 2           # stemma e maglia
    assert foglio.get_by_role("button", name="Da file o foto").count() == 2            # il pulsante che apre il campo del file (#801)


def test_un_altra_squadra_apre_il_foglio_sul_suo_nome(web):
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=squadre&rosa=Real%20Esempio")
    tocca(web, principale(web).get_by_role("button", name="Stemma e maglia"))
    assert web.pagina.get_by_role("dialog").get_by_role("combobox").input_value() == "Real Esempio"


def test_senza_le_rose_degli_altri_non_c_e_le_altre_squadre(web):
    solo(web, "prima")
    f = web.registrata("/api/funzioni")
    f["funzioni"]["squadre_altrui"] = False
    web.risposta("/api/funzioni", f)
    web.apri("/?vista=impostazioni")
    assert voce(web, "La mia squadra").is_visible() and voce(web, "Le altre squadre").count() == 0


def test_nuova_stagione_compare_in_la_mia_lega_quando_serve(web):
    solo(web, "prima")
    web.risposta("/api/stagione", {"corrente": "2027-28", "rose": "2026-27", "nuova": True})
    web.apri("/?vista=impostazioni")
    avviso = sezione(web, "La mia lega").get_by_role("button", name=re.compile("Nuova stagione 2027-28"))
    avviso.wait_for(timeout=10000)
    tocca(web, avviso)
    assert web.pagina.get_by_role("dialog").get_by_role("button", name="Archivia e riparti").is_visible()


def test_nuova_stagione_gia_archiviata_altrove_toglie_l_avviso(web):
    """Un altro dispositivo ha già archiviato e importato le rose nuove: il server risponde 409 senza scrivere niente (#657). Il
    foglio si chiude, l'avviso rimasto a schermo sparisce e si legge il messaggio del server."""
    solo(web, "prima")
    messaggio = "Le rose sono già della stagione in corso: non c'è niente da archiviare."
    web.risposta("/api/stagione", {"corrente": "2027-28", "rose": "2026-27", "nuova": True})
    web.risposta("/api/nuova-stagione", {"detail": messaggio}, stato=409)
    web.apri("/?vista=impostazioni")
    avviso = sezione(web, "La mia lega").get_by_role("button", name=re.compile("Nuova stagione 2027-28"))
    avviso.wait_for(timeout=10000)
    tocca(web, avviso)
    web.pagina.once("dialog", lambda d: d.accept())                     # «Archivio la stagione…?»: sì
    tocca(web, web.pagina.get_by_role("dialog").get_by_role("button", name="Archivia e riparti"))
    web.pagina.locator("#avviso").get_by_text(messaggio).wait_for(timeout=5000)
    web.pagina.locator("#foglio").wait_for(state="hidden", timeout=5000)
    assert avviso.count() == 0


# ---------------------------------------------------------------- Regole e scadenza
RICONOSCIUTE = {"modifiche": [{"chiave": "crediti_iniziali", "etichetta": "Crediti iniziali", "valore": 500, "riga": "Crediti: 500"},
                              {"chiave": "bonus.assist", "etichetta": "Assist", "valore": 1.5, "riga": "Assist +1,5"}],
                "non_riconosciute": [], "da_controllare": []}


def _scritture(web, rotta: str) -> list[dict]:
    """I corpi delle richieste che scrivono su `rotta` (PUT o POST), man mano che partono."""
    corpi = []
    web.pagina.on("request", lambda r: r.method in ("PUT", "POST") and r.url.split("?")[0].endswith(rotta)
                  and corpi.append(json.loads(r.post_data or "null")))
    return corpi


def test_il_regolamento_incollato_si_salva_con_un_tocco(web):
    solo(web, "prima")
    web.risposta("/api/regole/riconosci", RICONOSCIUTE)
    salvate = _scritture(web, "/api/regole")
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_role("textbox", name="Incolla qui il testo del regolamento").fill("Crediti: 500\nAssist +1,5")
    tocca(web, principale(web).get_by_role("button", name="Riconosci le regole"))
    assert "Crediti iniziali" in web.testo_principale()
    tocca(web, principale(web).get_by_role("button", name="Salva queste regole"))
    assert salvate, "le regole riconosciute non sono state salvate"
    assert salvate[-1]["crediti_iniziali"] == 500 and salvate[-1]["bonus"]["assist"] == 1.5
    assert not web.errori_mostrati()


def test_le_righe_da_controllare_a_mano_dicono_la_regola_e_seguono_il_testo(web):
    """Le righe non lette, anche quelle dubbie senza numeri, stanno sotto un titolo solo, nell'ordine del testo (lo dà il server),
    e quelle dubbie dicono quale regola impostare a mano (#684)."""
    solo(web, "prima")
    web.risposta("/api/regole/riconosci", {**RICONOSCIUTE, "non_riconosciute": ["Media 6-6,5: +1"], "da_controllare": [
        {"riga": "Non è vietato il cambio modulo",
         "regole": [{"chiave": "panchina.cambio_modulo", "etichetta": "Cambio modulo nelle sostituzioni"}]},
        {"riga": "Media 6-6,5: +1", "regole": []}]})
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_role("textbox", name="Incolla qui il testo del regolamento").fill("Regolamento di prova")
    tocca(web, principale(web).get_by_role("button", name="Riconosci le regole"))
    titolo = principale(web).get_by_text("Righe da controllare a mano (2)", exact=True)
    assert titolo.is_visible() and not principale(web).get_by_text("Non è vietato il cambio modulo").is_visible()
    tocca(web, titolo)
    elenco = principale(web).locator("details", has_text="Righe da controllare a mano (2)")
    regola = elenco.get_by_text("da impostare: Cambio modulo nelle sostituzioni", exact=True)
    assert regola.is_visible() and elenco.get_by_text("Media 6-6,5: +1", exact=True).is_visible()
    testo = elenco.inner_text()
    assert testo.index("Non è vietato il cambio modulo") < testo.index("Cambio modulo nelle sostituzioni") < testo.index("Media 6-6,5")
    assert not web.errori_mostrati()


def test_i_singoli_valori_stanno_dietro_modifica_i_valori(web):
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=regole")
    punteggi = principale(web).get_by_text("Punteggi", exact=True)
    assert not punteggi.is_visible()
    tocca(web, principale(web).get_by_text("Modifica i valori", exact=True))
    assert punteggi.is_visible()


def test_regole_e_scadenza_parla_di_giornate_non_del_diario(web):
    """La frase sotto la prima giornata nomina le pagine che ci sono: il Diario è diventato Giornate (#617)."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=regole")
    testo = web.testo_principale()
    assert "Diario" not in testo and "Giornate" in testo, testo[:400]


def test_la_frase_sulla_prima_giornata_non_cita_un_altra_giornata(web):
    """Sotto «Da quale giornata di Serie A è partita la lega?» la frase d'aiuto restava sull'esempio «Con la prima giornata a 4…»
    anche con un'altra giornata scelta (#779). Scelta la 6ª, la frase segue la scelta o non cita giornate: nessun numero tranne
    1 (la giornata 1 della lega) e 6."""
    solo(web, "prima")
    salvate = _scritture(web, "/api/regole")
    web.apri("/?vista=impostazioni&gruppo=regole")
    scelta = principale(web).get_by_label("Da quale giornata di Serie A è partita la lega?")
    scelta.select_option("6")
    web.aspetta()
    assert salvate and salvate[-1]["prima_giornata_lega"] == 6
    # il riquadro dei tempi senza i due menu, che elencano tutte le scelte
    aiuto = scelta.evaluate("""s => { const c = s.closest('.carta').cloneNode(true);
      c.querySelectorAll('select').forEach(x => x.remove()); return c.textContent; }""")
    assert "Giornate" in aiuto, aiuto
    assert set(re.findall(r"\d+", aiuto)) <= {"1", "6"}, aiuto


def test_la_scadenza_si_cambia_e_si_salva_subito(web):
    solo(web, "prima")
    salvate = _scritture(web, "/api/regole")
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_label("Quando si chiude la formazione?").select_option("30")
    web.aspetta()
    assert salvate and salvate[-1]["scadenza_minuti"] == 30


# ---------------------------------------------------------------- conflitto (412) su regole e rose (#667)
CONFLITTO = {"detail": "Questi dati sono stati cambiati da un altro dispositivo. Ho ricaricato la versione nuova: controlla e rifai la modifica."}


def risorsa_con_etag(web, letture: tuple[str, ...], scritture: tuple[str, ...]) -> dict:
    """Fa la parte del server vero su una risorsa con ETag (fanta/versioni.py): ogni lettura dà la risposta registrata con l'ETag
    di adesso; una scrittura con un If-Match vecchio è rifiutata (412), una senza If-Match è accettata, anche sopra ciò che ha
    salvato un altro dispositivo. `srv["cambia"]()`: un altro dispositivo salva; `srv["if_match"]`: l'If-Match di ogni scrittura."""
    srv = {"versione": 0, "if_match": []}
    js = "application/json"

    def etag() -> str:
        return f'"v{srv["versione"]}"'

    def cambia() -> None:
        srv["versione"] += 1

    def leggi(route):
        if route.request.method != "GET":
            return route.fallback()
        from playwright.sync_api import Error as ErrorePlaywright
        try:
            risposta = route.fetch()
            route.fulfill(response=risposta, headers={**risposta.headers, "etag": etag()})
        except ErrorePlaywright:                                       # la scheda si è chiusa (fine del test) a lettura in volo
            pass

    def scrivi(route):
        if route.request.method == "GET":
            return route.fallback()
        voluto = route.request.headers.get("if-match")
        srv["if_match"].append(voluto)
        if voluto is not None and voluto != etag():
            return route.fulfill(status=412, content_type=js, headers={"ETag": etag()}, body=json.dumps(CONFLITTO))
        cambia()
        route.fulfill(status=200, content_type=js, headers={"ETag": etag()}, body='{"ok": true}')

    srv["cambia"] = cambia
    web.pagina.route(lambda u: urlsplit(u).path in letture, leggi)
    web.pagina.route(lambda u: urlsplit(u).path in scritture, scrivi)
    return srv


@pytest.mark.parametrize("dove", ["regole", "rose"])
def test_dopo_un_412_la_modifica_rifatta_porta_l_if_match_riletto_e_mai_nessuno(web, dove):
    """Un altro dispositivo ha cambiato le regole (o le rose): la modifica fatta qui è rifiutata (412), l'avviso lo dice e la pagina
    si ricarica da sola. Rifatta prima della ricarica parte con l'If-Match vecchio ed è rifiutata ancora: mai senza If-Match, che il
    server accetterebbe sopra ciò che ha salvato l'altro dispositivo. Rifatta dopo la ricarica porta l'ETag riletto e passa."""
    solo(web, "prima")
    if dove == "regole":
        srv = risorsa_con_etag(web, ("/api/regole",), ("/api/regole",))
        indirizzo, valori = "/?vista=impostazioni&gruppo=regole", ("30", "60", "30")

        def modifica(valore):
            principale(web).get_by_label("Quando si chiude la formazione?").select_option(valore)
    else:
        srv = risorsa_con_etag(web, ("/api/squadre", "/api/rosa"), ("/api/crediti",))
        indirizzo, valori = "/?vista=impostazioni&gruppo=squadra", ("20", "21", "20")

        def modifica(valore):
            principale(web).get_by_label("Crediti residui").fill(valore)
            principale(web).get_by_role("button", name="Salva", exact=True).click()

    def scrive(r) -> bool:
        return r.request.method == "PUT" and urlsplit(r.url).path in ("/api/regole", "/api/crediti")

    web.apri(indirizzo)
    srv["cambia"]()                                                    # dall'altro dispositivo
    avviso = web.pagina.get_by_role("status").filter(has_text="cambiati da un altro dispositivo")
    with web.pagina.expect_event("load", timeout=10000):              # dopo il 412 la pagina si ricarica da sola
        with web.pagina.expect_response(scrive, timeout=10000) as prima:
            modifica(valori[0])
        assert prima.value.status == 412
        avviso.first.wait_for(timeout=10000)
        with web.pagina.expect_response(scrive, timeout=10000) as rifatta:
            modifica(valori[1])                                        # rifatta subito, prima della ricarica
        assert rifatta.value.status == 412, "la modifica rifatta prima della ricarica è passata sopra l'altro dispositivo"
    web.aspetta()
    with web.pagina.expect_response(scrive, timeout=10000) as dopo:
        modifica(valori[2])                                            # rifatta dopo la ricarica
    assert dopo.value.status == 200
    web.aspetta()
    assert srv["if_match"] == ['"v0"', '"v0"', '"v1"'], srv["if_match"]
    assert not web.errori_mostrati()


# ---------------------------------------------------------------- Avvisi
def test_avvisi_un_interruttore_e_le_ore_tranquille_senza_altri_controlli(web):
    solo(web, "prima")
    salvate = _scritture(web, "/api/avvisi")
    web.apri("/?vista=impostazioni")
    avvisi = sezione(web, "Avvisi")
    testo = avvisi.inner_text()
    for tolto in ("Promemoria 15 minuti prima", "Riepilogo a giornata finita", "Reparto della rosa scoperto", "Manda un avviso di prova",
                  "Cambi di formazione e probabili"):
        assert tolto not in testo, tolto
    ore = avvisi.get_by_role("checkbox", name=re.compile("^Ore tranquille"))
    assert "dalle 23 alle 7" in testo                                    # la fascia è già scelta
    ore.check()
    web.aspetta()
    assert salvate and salvate[-1] == {"silenzio": True}                 # solo ciò che si è cambiato: il resto resta com'è


def test_senza_notifiche_nel_browser_la_frase_dice_cosa_fare(web):
    """Il browser di prova non ha il service worker: al posto dell'interruttore una frase (non un riquadro vuoto che aspetta)."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni")
    frase = sezione(web, "Avvisi").get_by_text(re.compile("Le notifiche dell'app non sono disponibili su questo dispositivo"))
    frase.wait_for(timeout=10000)
    assert sezione(web, "Avvisi").get_by_role("checkbox", name=re.compile("^Avvisi su questo dispositivo")).count() == 0


def test_senza_service_worker_registrato_gli_avvisi_non_aspettano(web):
    """Il browser di prova non ha un service worker registrato: la sezione avvisi lo dice subito, senza aspettare i 4 secondi (che
    restano solo per una registrazione in attivazione). Prima ogni apertura di Impostazioni costava 4 s, anche ai controlli."""
    solo(web, "prima")
    web.pagina.goto(web.server.indirizzo + "/?vista=impostazioni", wait_until="load")
    avvisi = sezione(web, "Avvisi")
    avvisi.locator("label").filter(has_text="Ore tranquille").wait_for(timeout=10000)
    avvisi.get_by_text(re.compile("Le notifiche dell'app non sono disponibili")).wait_for(timeout=1500)
    assert avvisi.locator("[aria-busy=true]").count() == 0


# Un service worker registrato ma ancora in attivazione: `ready` non arriva (la web lo aspetta al massimo 4 secondi).
IN_ATTIVAZIONE = """(() => {
  const reg = { active: null, installing: {}, pushManager: { getSubscription: async () => null } };
  ServiceWorkerContainer.prototype.getRegistration = async () => reg;
  Object.defineProperty(ServiceWorkerContainer.prototype, 'ready', { get: () => new Promise(() => {}) });
})();"""


def test_mentre_cerca_le_notifiche_il_riquadro_lo_dice_e_la_pagina_non_salta(web):
    """Con un service worker registrato ma non ancora attivo la web lo aspetta fino a 4 secondi. Intanto il posto dell'interruttore
    dice che sta controllando (aria-busy), e quando arriva la frase la riga delle ore tranquille resta dov'era."""
    solo(web, "prima")
    web.pagina.add_init_script(IN_ATTIVAZIONE)
    web.pagina.goto(web.server.indirizzo + "/?vista=impostazioni", wait_until="load")
    avvisi = sezione(web, "Avvisi")
    ore = avvisi.locator("label").filter(has_text="Ore tranquille")
    ore.wait_for(timeout=10000)
    attesa = avvisi.locator("[aria-busy=true]")
    assert attesa.count() == 1, "mentre aspetta il service worker il riquadro non dice che sta caricando"
    assert "Controllo gli avvisi" in attesa.inner_text()
    prima = ore.bounding_box()["y"]
    avvisi.get_by_text(re.compile("Le notifiche dell'app non sono disponibili")).wait_for(timeout=10000)
    assert avvisi.locator("[aria-busy=true]").count() == 0
    assert abs(ore.bounding_box()["y"] - prima) <= 2, f"la riga delle ore tranquille si è spostata: {prima} → {ore.bounding_box()['y']}"


# Le notifiche del browser, finte (il browser di prova non ha il service worker): un service worker registrato e pronto, con un
# pushManager che iscrive solo per finta, e il permesso che risponde PERMESSO. Le rotte del server rispondono con `notifiche_finte`.
NOTIFICHE_FINTE = """(() => {
  const reg = { active: {}, pushManager: {
    getSubscription: async () => window.__iscrizione || null,
    subscribe: async () => (window.__iscrizione = { endpoint: 'https://push.example/prova',
      toJSON: () => ({ endpoint: 'https://push.example/prova', keys: { p256dh: 'a', auth: 'b' } }),
      unsubscribe: async () => { window.__iscrizione = null; return true; } }) } };
  ServiceWorkerContainer.prototype.getRegistration = async () => reg;
  Object.defineProperty(ServiceWorkerContainer.prototype, 'ready', { get: () => Promise.resolve(reg) });
  Notification.requestPermission = async () => PERMESSO;
})();"""


def notifiche_finte(web, permesso="granted", prova=({"inviato": True}, 200)) -> list:
    """Prima di `apri`. Dà l'elenco delle richieste di avviso di prova, che si riempie man mano."""
    web.pagina.add_init_script(NOTIFICHE_FINTE.replace("PERMESSO", json.dumps(permesso)))
    web.risposta("/api/push/chiave", {"chiave": "BElxQ2VaZ2pqT3Z6"})
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    web.risposta("/api/avvisi/prova", prova[0], stato=prova[1])
    return _scritture(web, "/api/avvisi/prova")


QUI = re.compile("^Avvisi su questo dispositivo")


def interruttore_qui(web):
    return sezione(web, "Avvisi").get_by_role("checkbox", name=QUI)


def riga_qui(web):
    """L'etichetta dell'interruttore (nome e frase sotto), che si tocca."""
    return sezione(web, "Avvisi").locator("label").filter(has=web.pagina.get_by_role("checkbox", name=QUI))


def accendi_qui(web) -> None:
    riga_qui(web).click()


def test_la_frase_dell_interruttore_dice_quali_avvisi_arrivano(web):
    """Dal #676 il server manda solo due avvisi, qualunque fossero le scelte di prima: la frase sotto l'interruttore dice quali
    (il promemoria, che tace con la spunta «L'ho messa», e il cambio della formazione) e non promette altro."""
    solo(web, "prima")
    notifiche_finte(web)
    web.apri("/?vista=impostazioni")
    frase = riga_qui(web).inner_text()
    assert "promemoria prima della scadenza" in frase and "«L'ho messa»" in frase, frase
    assert "cambia la formazione da schierare" in frase and "altri avvisi" not in frase, frase


def test_accendere_gli_avvisi_manda_un_avviso_di_prova(web):
    solo(web, "prima")
    prove = notifiche_finte(web)
    web.apri("/?vista=impostazioni")
    accendi_qui(web)
    web.pagina.locator("#avviso").filter(has_text="ti ho mandato un avviso di prova").wait_for(timeout=10000)
    assert len(prove) == 1 and interruttore_qui(web).is_checked()


@pytest.mark.parametrize("prova", [({"detail": "Hai fatto troppe richieste in quest'ora. Riprova tra 40 minuti."}, 429),
                                   ({"inviato": False}, 200)])
def test_se_l_avviso_di_prova_non_parte_lo_dice_e_gli_avvisi_restano_accesi(web, prova):
    solo(web, "prima")
    notifiche_finte(web, prova=prova)
    web.apri("/?vista=impostazioni")
    accendi_qui(web)
    web.pagina.locator("#avviso[role=status]").filter(has_text="l'avviso di prova non è partito").wait_for(timeout=10000)
    assert interruttore_qui(web).is_checked()                            # l'iscrizione è riuscita: resta accesa


def test_con_il_permesso_negato_niente_avviso_di_prova(web):
    solo(web, "prima")
    prove = notifiche_finte(web, permesso="denied")
    web.apri("/?vista=impostazioni")
    accendi_qui(web)
    web.pagina.locator("#avviso").filter(has_text="Permesso negato").wait_for(timeout=10000)
    assert prove == [] and not interruttore_qui(web).is_checked()


def test_le_ore_tranquille_rifiutate_dal_server_tornano_come_erano(web):
    solo(web, "prima")
    registrata = json.dumps(web.registrata("/api/avvisi"))
    rifiuto = json.dumps({"detail": "Le ore tranquille non possono iniziare e finire alla stessa ora: scegli due ore diverse "
                                    "(per esempio dalle 23 alle 7) oppure spegni l'interruttore"})
    web.pagina.route(lambda u: urlsplit(u).path == "/api/avvisi", lambda r: r.fulfill(
        status=422 if r.request.method == "PUT" else 200, content_type="application/json", body=rifiuto if r.request.method == "PUT" else registrata))
    web.apri("/?vista=impostazioni")
    ore = sezione(web, "Avvisi").get_by_role("checkbox", name=re.compile("^Ore tranquille"))
    assert not ore.is_checked()
    sezione(web, "Avvisi").locator("label").filter(has_text="Ore tranquille").click()
    web.pagina.locator("#avviso").filter(has_text="Le ore tranquille non possono").wait_for(timeout=10000)
    assert not ore.is_checked()                                          # resta scritto ciò che vale sul server


# ---------------------------------------------------------------- «Esci» e gli avvisi di questo dispositivo (#800)
# Un browser che ha già un'iscrizione agli avvisi, fatta in una visita di prima: service worker e permesso finti come in
# NOTIFICHE_FINTE, ma l'iscrizione sta in localStorage (la web non tocca quella chiave), così resta dopo una ricarica, e c'è già
# alla prima pagina della scheda (scritta una volta sola: dopo resta ciò che fa l'app). `__DI__`: il numero dell'account che l'ha
# fatta, come lo ricorda la web (`avvisi-di`, #804); `__INIZIALE__` vuoto: nessuna iscrizione all'inizio.
ENDPOINT = "https://push.example/prova"
ISCRIZIONE_GIA_QUI = """(() => {
  const CHIAVE = '__iscrizione-di-prova', ep = () => localStorage.getItem(CHIAVE);
  if (!localStorage.getItem('__iscrizione-iniziata')) {
    localStorage.setItem('__iscrizione-iniziata', '1');
    if (__INIZIALE__) localStorage.setItem(CHIAVE, __INIZIALE__);
    if (__DI__) localStorage.setItem('avvisi-di', __DI__);
  }
  const sub = () => ep() ? { endpoint: ep(), toJSON: () => ({ endpoint: ep(), keys: { p256dh: 'a', auth: 'b' } }),
    unsubscribe: async () => { localStorage.removeItem(CHIAVE); return true; } } : null;
  const reg = { active: {}, pushManager: { getSubscription: async () => sub(),
    subscribe: async () => { localStorage.setItem(CHIAVE, ENDPOINT); return sub(); } } };
  ServiceWorkerContainer.prototype.getRegistration = async () => reg;
  Object.defineProperty(ServiceWorkerContainer.prototype, 'ready', { get: () => Promise.resolve(reg) });
  Notification.requestPermission = async () => 'granted';
})();""".replace("ENDPOINT", json.dumps(ENDPOINT))
SENZA_SESSIONE = {"detail": "Accesso richiesto", "multiutente": True, "registrazione": "invito", "social": [], "email_attiva": True}


def iscrizione_gia_qui(web, di: str = "7", iniziale: bool = True) -> None:
    """Prima di `apri`: il browser ha già un'iscrizione agli avvisi, fatta dall'account numero `di` (7 è UTENTE); con
    `iniziale=False` le notifiche finte ci sono ma l'iscrizione no."""
    web.pagina.add_init_script(ISCRIZIONE_GIA_QUI.replace("__INIZIALE__", json.dumps(ENDPOINT if iniziale else ""))
                               .replace("__DI__", json.dumps(di)))


def iscrizione_nel_browser(web) -> str | None:
    return web.pagina.evaluate("localStorage.getItem('__iscrizione-di-prova')")


def iscrizione_mandata(richiesta) -> bool:
    return richiesta.method == "POST" and urlsplit(richiesta.url).path == "/api/push/iscrivi"


def json_200(route, corpo, stato=200) -> None:
    route.fulfill(status=stato, content_type="application/json; charset=utf-8", body=json.dumps(corpo))


@pytest.mark.parametrize("stato", [500, 502, None], ids=["errore-del-server", "server-che-riparte", "rete-giu"])
def test_esci_non_riuscito_lo_dice_e_resta_dentro(web, stato):
    """Il cookie della sessione lo toglie solo il server: se la richiesta di «Esci» non riesce (rete giù, server che riparte dopo
    un rilascio) non si è usciti davvero. Come «Esci da tutti i dispositivi», un avviso lo dice e la pagina resta com'è: copie dei
    dati e avvisi di questo dispositivo, nel browser e sul server (#800). Prima la web svuotava e ricaricava come se fosse uscita."""
    solo(web, "prima")
    da_utente(web)
    web.memoria({"account": json.dumps(UTENTE["utente"])})     # già dentro da prima: all'apertura niente da rimandare
    iscrizione_gia_qui(web)
    web.risposta("/api/push/disiscrivi", {"dispositivi": 0})
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    iscritte = _scritture(web, "/api/push/iscrivi")
    web.apri("/")                                              # la Formazione lascia nel browser le sue copie
    web.apri("/?vista=impostazioni&gruppo=account")
    prima = chiavi_salvate(web)
    assert prima, "la prova vuole delle copie da tenere"
    arrivate = []

    def esci(route):
        arrivate.append(route.request.method)
        if stato is None:
            route.abort()
        else:
            json_200(route, {"detail": "Il server non risponde"} if stato == 502 else {}, stato)

    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/esci", esci)
    ricariche = []
    web.pagina.on("framenavigated", lambda f: f == web.pagina.main_frame and ricariche.append(f.url))
    with web.pagina.expect_request(iscrizione_mandata):
        principale(web).get_by_role("button", name="Esci", exact=True).click(timeout=10000)
    web.pagina.locator("#avviso[role=status]").filter(has_text="Non riesco a farti uscire").wait_for(timeout=10000)
    web.aspetta()
    assert ricariche == [], f"la pagina si è ricaricata come dopo un'uscita riuscita: {ricariche}"
    assert arrivate == ["POST"]
    assert titolo(web) == "Il tuo account" and web.pagina.locator("#accesso").count() == 0
    assert chiavi_salvate(web) == prima
    assert iscrizione_nel_browser(web) == ENDPOINT, "gli avvisi di questo dispositivo si sono spenti con un'uscita non riuscita"
    assert [c["endpoint"] for c in iscritte] == [ENDPOINT], f"l'iscrizione tolta dal server non è stata rimandata: {iscritte}"


def test_esci_riuscito_toglie_gli_avvisi_di_questo_dispositivo(web):
    """Riuscito, «Esci» fa come prima: gli avvisi di questo dispositivo si tolgono dal server (mentre la sessione vale ancora) e dal
    browser, nel browser non restano copie e si torna all'accesso."""
    solo(web, "prima")
    da_utente(web)
    iscrizione_gia_qui(web)
    web.risposta("/api/push/disiscrivi", {"dispositivi": 0})
    disiscritte = _scritture(web, "/api/push/disiscrivi")
    web.apri("/?vista=impostazioni&gruppo=account")
    uscito = []
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/") and urlsplit(u).path != "/api/account/esci",
                     lambda route: json_200(route, SENZA_SESSIONE, 401) if uscito else route.fallback())
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/esci", lambda route: uscito.append(1) or json_200(route, {"ok": True}))
    with web.pagina.expect_navigation(wait_until="load"):            # la ricarica dopo l'uscita
        principale(web).get_by_role("button", name="Esci", exact=True).click(timeout=10000)
    web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI")).get_by_role("button", name="Accedi").first.wait_for(timeout=10000)
    assert uscito == [1]
    assert disiscritte == [{"endpoint": ENDPOINT}]
    assert iscrizione_nel_browser(web) is None
    assert chiavi_salvate(web) == []


def entra_con_la_password(web, rimanda: bool = True) -> list[dict]:
    """La sessione di questo browser è stata chiusa altrove («Esci da tutti», password cambiata o recuperata da un altro dispositivo:
    il server toglie anche la sua iscrizione agli avvisi). Si apre l'accesso, si entra con la password e la pagina si ricarica.
    Con `rimanda` aspetta che l'iscrizione parta. Restituisce le iscrizioni mandate al server."""
    entrato = []
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/me",
                     lambda route: json_200(route, UTENTE) if entrato else json_200(route, SENZA_SESSIONE, 401))
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/accedi",
                     lambda route: entrato.append(1) or json_200(route, UTENTE))
    iscritte = _scritture(web, "/api/push/iscrivi")
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    web.pagina.locator("#accesso-form").wait_for(timeout=10000)
    web.pagina.locator("#ac-nome").fill("amico")
    web.pagina.locator("#ac-pw").fill("Password-Finta-1")
    if rimanda:
        with web.pagina.expect_request(iscrizione_mandata), web.pagina.expect_navigation(wait_until="load"):
            web.pagina.locator("#accesso-invia").click()
    else:
        with web.pagina.expect_navigation(wait_until="load"):
            web.pagina.locator("#accesso-invia").click()
    web.aspetta()
    return iscritte


def test_gli_avvisi_accesi_da_un_account_tornano_al_suo_nuovo_accesso(web):
    """Stesso account (#804): accende gli avvisi qui, la sua sessione si chiude altrove e rientra: l'iscrizione torna al server.
    (Browser vuoto all'inizio: il numero dell'account lo ricorda l'accensione, non un passaggio di prima.)"""
    solo(web, "prima")
    da_utente(web)
    iscrizione_gia_qui(web, di="", iniziale=False)
    web.risposta("/api/push/chiave", {"chiave": "BElxQ2VaZ2pqT3Z6"})
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    web.risposta("/api/avvisi/prova", {"inviato": True})
    web.apri("/?vista=impostazioni")
    accendi_qui(web)
    web.pagina.locator("#avviso").filter(has_text="ti ho mandato un avviso di prova").wait_for(timeout=10000)
    iscritte = entra_con_la_password(web)
    assert [c["endpoint"] for c in iscritte] == [ENDPOINT], iscritte


def test_l_iscrizione_di_un_altro_account_non_si_rimanda(web):
    """Account diverso (#804): il browser ha l'iscrizione fatta dall'account 12 ed entra l'account 7. La web non la rimanda al
    server e «Avvisi su questo dispositivo» è spento, finché il nuovo utente non lo accende lui; acceso, l'iscrizione è sua."""
    solo(web, "prima")
    iscrizione_gia_qui(web, di="12")
    web.risposta("/api/push/chiave", {"chiave": "BElxQ2VaZ2pqT3Z6"})
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    web.risposta("/api/avvisi/prova", {"inviato": True})
    iscritte = entra_con_la_password(web, rimanda=False)
    assert iscritte == [], f"l'iscrizione di un altro account è stata rimandata: {iscritte}"
    web.apri("/?vista=impostazioni")
    assert not interruttore_qui(web).is_checked(), "l'interruttore è acceso con l'iscrizione di un altro account"
    with web.pagina.expect_request(iscrizione_mandata):
        accendi_qui(web)
    web.pagina.locator("#avviso").filter(has_text="ti ho mandato un avviso di prova").wait_for(timeout=10000)
    web.apri("/?vista=impostazioni")
    assert interruttore_qui(web).is_checked() and len(iscritte) == 1


def test_un_iscrizione_senza_numero_dopo_un_nuovo_accesso_non_diventa_del_nuovo_account(web):
    """Un'iscrizione fatta con la versione di prima (nessun numero d'account accanto) ed entra un account dopo un'uscita: non si sa
    di chi è, quindi non si rimanda e l'interruttore è spento. Anche alla seconda apertura e al prossimo accesso (#804, revisione):
    prima alla seconda apertura diventava del nuovo account, l'interruttore si accendeva senza iscrizione sul server e al prossimo
    accesso veniva mandata come sua."""
    solo(web, "prima")
    iscrizione_gia_qui(web, di="")
    iscritte = entra_con_la_password(web, rimanda=False)
    web.apri("/")                                                    # seconda apertura, con la sessione che continua
    web.apri("/?vista=impostazioni")
    assert not interruttore_qui(web).is_checked(), "alla seconda apertura l'iscrizione senza numero è diventata del nuovo account"
    iscritte += entra_con_la_password(web, rimanda=False)            # la sessione si chiude altrove e si rientra
    assert iscritte == [], f"l'iscrizione senza numero è stata mandata come del nuovo account: {iscritte}"


def test_un_iscrizione_senza_numero_con_la_sessione_gia_aperta_diventa_sua_e_si_rimanda_una_volta(web):
    """Un'iscrizione fatta con la versione di prima, con la sessione già aperta prima del rilascio: è di chi è dentro, l'interruttore
    resta acceso e l'iscrizione si rimanda una volta (il server può averla già tolta); alle aperture dopo non più."""
    solo(web, "prima")
    da_utente(web)
    web.memoria({"account": json.dumps(UTENTE["utente"])})
    iscrizione_gia_qui(web, di="")
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    iscritte = _scritture(web, "/api/push/iscrivi")
    with web.pagina.expect_request(iscrizione_mandata):
        web.apri("/?vista=impostazioni")
    assert interruttore_qui(web).is_checked()
    web.apri("/?vista=impostazioni")
    assert interruttore_qui(web).is_checked() and [c["endpoint"] for c in iscritte] == [ENDPOINT], iscritte


def test_esci_con_la_sessione_gia_finita_esce_senza_avviso(web):
    """«Esci» che riceve 401 (la sessione era già finita, per esempio chiusa da un altro dispositivo): si esce lo stesso, con la
    ricarica e la schermata d'accesso, senza l'avviso «Non riesco a farti uscire»."""
    solo(web, "prima")
    da_utente(web)
    web.memoria({"account": json.dumps(UTENTE["utente"])})
    web.apri("/?vista=impostazioni&gruppo=account")
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), lambda route: json_200(route, SENZA_SESSIONE, 401))
    avvisi = []
    web.pagina.expose_function("__avvisoDiProva", lambda testo: avvisi.append(testo))
    web.pagina.evaluate("""() => new MutationObserver(() => { const a = document.querySelector('#avviso');
        if (a && a.textContent.trim()) window.__avvisoDiProva(a.textContent); })
      .observe(document.body, { subtree: true, childList: true, characterData: true })""")
    with web.pagina.expect_navigation(wait_until="load"):           # la ricarica dopo l'uscita
        principale(web).get_by_role("button", name="Esci", exact=True).click(timeout=10000)
    web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI")).get_by_role("button", name="Accedi").first.wait_for(timeout=10000)
    assert not [a for a in avvisi if "Non riesco a farti uscire" in a], avvisi


def test_dopo_un_nuovo_accesso_l_iscrizione_del_browser_torna_sul_server(web):
    """Dopo un nuovo accesso, se il browser ha ancora un'iscrizione agli avvisi la web la rimanda al server, senza chiedere di nuovo
    il permesso: prima l'interruttore «Avvisi su questo dispositivo» restava acceso e i promemoria non arrivavano più (#800)."""
    solo(web, "prima")
    iscrizione_gia_qui(web)
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    iscritte = entra_con_la_password(web)
    assert [c["endpoint"] for c in iscritte] == [ENDPOINT], iscritte
    assert iscritte[0]["keys"] == {"p256dh": "a", "auth": "b"}


def test_riaprendo_l_app_gia_dentro_l_iscrizione_non_si_rimanda(web):
    """Una volta per accesso: riaprire l'app con la sessione che vale ancora non rimanda niente (ogni iscrizione conta nel tetto
    all'ora del server e costa un controllo in rete)."""
    solo(web, "prima")
    iscrizione_gia_qui(web)
    web.risposta("/api/push/iscrivi", {"dispositivi": 1})
    iscritte = entra_con_la_password(web)
    assert len(iscritte) == 1, iscritte
    web.apri("/")
    web.apri("/?vista=impostazioni")
    assert len(iscritte) == 1, f"l'iscrizione è stata rimandata a ogni apertura: {iscritte}"
    assert interruttore_qui(web).is_checked()


def test_l_iscrizione_che_non_arriva_si_rimanda_all_apertura_dopo(web):
    """Se l'iscrizione rimandata dopo l'accesso non arriva (server occupato, troppe richieste, rete giù) si riprova alla prossima
    apertura dell'app, finché il server non la prende; poi basta."""
    solo(web, "prima")
    iscrizione_gia_qui(web)
    risposte = [({"detail": "Il server sta attivando altre notifiche: riprova tra qualche secondo."}, 429)]
    web.pagina.route(lambda u: urlsplit(u).path == "/api/push/iscrivi",
                     lambda route: json_200(route, *(risposte.pop(0) if risposte else ({"dispositivi": 1}, 200))))
    iscritte = entra_con_la_password(web)
    assert len(iscritte) == 1, iscritte
    with web.pagina.expect_request(iscrizione_mandata):
        web.apri("/")
    assert len(iscritte) == 2, f"l'iscrizione non arrivata non è stata rimandata: {iscritte}"
    web.apri("/")
    assert len(iscritte) == 2, f"l'iscrizione arrivata è stata rimandata ancora: {iscritte}"


# ---------------------------------------------------------------- Stato dei dati: le etichette del server
def test_stato_dei_dati_usa_le_etichette_del_server(web):
    solo(web, "prima")
    s = web.registrata("/api/stato-dati")
    s["aggiornamenti"] = [{"cosa": "voti", "quando": "2026-10-26T23:55:13", "errori": [], "etichetta": "Voti e bonus dal server"}]
    s["controlli"] = [{"nome": "somma_xg", "esito": "errore", "dettaglio": "Qualcosa non torna", "etichetta": "Gol attesi dal server"}]
    web.risposta("/api/stato-dati", s)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    tocca(web, principale(web).get_by_role("button", name="Apri lo stato dei dati"))
    foglio = web.pagina.get_by_role("dialog")
    foglio.get_by_text("Voti e bonus dal server").wait_for(timeout=10000)
    assert foglio.get_by_text("Gol attesi dal server").is_visible()


# ---------------------------------------------------------------- Gestione: gli errori recenti in parole (#779)
REGISTRO = {"contatori": {"da": "2026-11-20T08:00:00+00:00", "richieste": 1, "riuscite": 0, "rifiutate": 1, "errori": 0,
                          "tempo_medio_ms": 7.3, "tempo_p95_ms": 7.3, "tempo_max_ms": 1234.5,
                          "piu_lente": [{"rotta": "/api/rotta-mai-vista", "richieste": 2, "medio_ms": 1234.5, "max_ms": 1234.5},
                                        {"rotta": "/api/stato", "richieste": 1, "medio_ms": 7.3, "max_ms": 7.3}]},
            "errori": [{"quando": "2026-11-20T09:10:00+00:00", "tipo": "errore", "metodo": "GET", "rotta": "/api/oggi", "stato": "500",
                        "errore": "KeyError"}],
            "sicurezza": [{"quando": "2026-11-20T09:05:00+00:00", "tipo": "ruolo_cambiato", "nome": "amico"},
                          {"quando": "2026-11-20T09:01:00+00:00", "tipo": "accesso_fallito", "nome": "amico", "ip": "192.0.2.x"},
                          {"quando": "2026-11-20T09:00:30+00:00", "tipo": "fonte-cambiata", "utente": "amico", "fonte": "understat"},
                          {"quando": "2026-11-20T09:00:00+00:00", "tipo": "evento_che_non_esiste_ancora"}]}


def test_gli_errori_recenti_sono_scritti_in_parole(web):
    """Impostazioni › Gestione, «Errori recenti» (solo chi gestisce il server, con gli account): plurali giusti («1 richiesta»,
    «1 rifiutata»), tempi con la virgola, ora italiana senza «UTC» e nomi degli eventi in parole, mai il nome interno
    (`ruolo_cambiato`); un evento che il catalogo non conosce ancora si legge senza trattini bassi. Dal #827 niente sigle:
    millisecondi e secondi in parole, il nome della parte dell'app accanto al percorso, «(amministratore)» fra gli utenti."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    web.risposta("/api/admin/utenti", {"utenti": [{"nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "amministratore"}],
                                       "massimo": 10})
    web.risposta("/api/admin/registro", REGISTRO)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    carta = principale(web).locator(".carta", has=web.pagina.get_by_role("heading", name="Errori recenti"))
    carta.get_by_text("Ruolo cambiato").wait_for(timeout=10000)
    testo = " ".join(carta.inner_text().split())
    assert "1 richiesta dall'ultimo riavvio" in testo and "1 rifiutata" in testo, testo
    assert "1 richieste" not in testo and "1 rifiutate" not in testo, testo
    # tempi in parole (#827): «7,3 millisecondi», sopra il secondo «1,2 secondi»; mai «ms» né la sigla «5xx»
    assert "Tempo medio 7,3 millisecondi" in testo and "massimo 1,2 secondi" in testo and "7.3" not in testo, testo
    assert not re.search(r"\bms\b|5xx", testo), testo
    # il percorso resta per chi gestisce, accanto al nome della parte dell'app; una rotta che l'app non conosce solo con il percorso
    assert "Apertura dell'app (/api/stato) · 1 richiesta, in media 7,3 millisecondi" in testo, testo
    assert "/api/rotta-mai-vista · 2 richieste, in media 1,2 secondi" in testo, testo
    assert "10:10 · Formazione (GET /api/oggi) · errore 500, KeyError" in testo, testo
    assert "10:05" in testo and "10:01" in testo and "UTC" not in testo, testo          # 9:05 UTC = 10:05 in Italia a novembre
    assert "Accesso non riuscito" in testo and "evento che non esiste ancora" in testo, testo
    assert "Fonte dei dati accesa o spenta" in testo and "fonte-cambiata" not in testo, testo     # tipo scritto con il trattino
    assert "_" not in testo, testo
    utenti = principale(web).locator("#adm-utenti")
    utenti.get_by_text("Amico di prova", exact=False).wait_for(timeout=10000)
    assert "Amico di prova (amministratore)" in utenti.inner_text() and "admin)" not in utenti.inner_text(), utenti.inner_text()
    assert not web.errori_console and not web.richieste_fallite


# ---------------------------------------------------------------- accesso: gli avvisi non sono errori
def test_nella_schermata_di_accesso_un_avviso_non_e_un_errore(web):
    """Sessione finita: la schermata di accesso lo dice con un avviso (`role="status"`), non con un errore (`role="alert"`)."""
    solo(web, "prima")
    da_utente(web)
    web.risposta("/api/stato", {"detail": "Serve l'accesso", "multiutente": True}, stato=401)
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    accesso = web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI"))
    accesso.get_by_role("status").filter(has_text=re.compile(r"\w")).first.wait_for(timeout=10000)
    allarmi = [t for t in web.pagina.locator('[role="alert"]').all_inner_texts() if t.strip()]
    assert allarmi == [], allarmi


# ---------------------------------------------------------------- ritocchi dalla revisione del 20/11 (#801)
def server_giu(web, modo="rete") -> list:
    """Da qui ogni /api/... non arriva («rete») o risponde 502 come il proxy mentre il servizio riparte («502»), finché la lista
    restituita non si svuota (`.clear()`): da lì le risposte tornano quelle di sempre."""
    giu = [modo]

    def rispondi(route):
        if not giu:
            route.fallback()
        elif giu[0] == "rete":
            route.abort()
        else:
            route.fulfill(status=502, content_type="text/html", body="<html>502 Bad Gateway</html>")

    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), rispondi)
    return giu


def riga_di_stato(web) -> str:
    return principale(web).locator(".stato-pagina").first.inner_text()


def test_lo_stato_d_avvio_si_rilegge_quando_torna_la_rete(web):
    """Aperta senza rete, l'app non sa delle rose: Impostazioni non ha «La mia squadra» né «Le altre squadre». Quando il browser dice
    che la rete è tornata lo stato d'avvio si rilegge e la pagina in vista si ridisegna con le voci giuste (#801)."""
    solo(web, "prima")
    giu = server_giu(web, "rete")
    web.apri("/?vista=impostazioni")
    assert voce(web, "La mia squadra").count() == 0, "la prova vuole l'avvio senza le rose"
    giu.clear()
    web.pagina.evaluate("window.dispatchEvent(new Event('online'))")
    voce(web, "La mia squadra").wait_for(timeout=10000)
    web.aspetta()
    assert voce(web, "Le altre squadre").count() == 1


def test_lo_stato_d_avvio_si_rilegge_al_primo_dato_fresco(web):
    """Aperta mentre il server riparte (502 del proxy: per il browser la rete c'è, e non dice niente), la riga di stato dice «Server
    non raggiungibile». Alla prima risposta buona del server (qui «Riprova» di Giornate, a server tornato) lo stato si rilegge: la
    riga torna quella di sempre e Impostazioni ha «La mia squadra» (#801). Prima restava «Server non raggiungibile» fino a ricaricare."""
    solo(web, "prima")
    giu = server_giu(web, "502")
    web.apri("/?vista=giornate")
    assert "Server non raggiungibile" in riga_di_stato(web)
    giu.clear()
    tocca(web, principale(web).get_by_role("button", name="Riprova"))
    web.pagina.wait_for_function(
        "() => { const r = document.querySelector('main .stato-pagina'); return r && r.innerText.trim() && !r.innerText.includes('Server non raggiungibile'); }",
        timeout=10000)
    assert "Giornata" in riga_di_stato(web), riga_di_stato(web)
    tocca(web, barra(web).get_by_role("link", name="Impostazioni"))
    assert voce(web, "La mia squadra").count() == 1


def test_un_rifiuto_del_server_non_fa_rileggere_lo_stato_d_avvio(web):
    """Lo stato d'avvio si rilegge solo dopo un guasto della rete o del server (5xx): un rifiuto (4xx) rileggendo non cambia, e
    farebbe ripartire le letture a ogni risposta buona."""
    solo(web, "prima")
    web.risposta("/api/squadre", {"detail": "Rose non trovate"}, stato=409)
    web.risposta("/api/primo-avvio", {"primo_avvio": {"fatti": [], "saltati": [], "chiuso": True}})   # senza squadre la guida rileggerebbe
    web.apri("/?vista=impostazioni")
    assert web.richieste.count("/api/squadre") == 1, web.richieste
    tocca(web, barra(web).get_by_role("link", name="Giornate"))
    tocca(web, barra(web).get_by_role("link", name="Formazione"))
    assert web.richieste.count("/api/squadre") == 1, f"lo stato d'avvio si è riletto dopo un rifiuto: {web.richieste}"


def elimina_l_account(web, stato: int):
    """In Il tuo account, «Elimina l'account» aperto, con la password scritta e la conferma accettata; la rotta risponde con
    `stato`. Restituisce le disiscrizioni dagli avvisi mandate al server e il pulsante da toccare."""
    da_utente(web)
    web.memoria({"account": json.dumps(UTENTE["utente"])})
    iscrizione_gia_qui(web)
    web.risposta("/api/push/disiscrivi", {"dispositivi": 0})
    disiscritte = _scritture(web, "/api/push/disiscrivi")
    web.risposta("/api/account/elimina", {"detail": "La password non va bene."} if stato == 403 else {"ok": True}, stato=stato)
    web.apri("/?vista=impostazioni&gruppo=account")
    tocca(web, principale(web).get_by_text("Elimina l'account", exact=True))
    principale(web).get_by_label("La tua password").last.fill("Password-Finta-1")
    web.pagina.on("dialog", lambda dialogo: dialogo.accept())
    return disiscritte, principale(web).get_by_role("button", name="Elimina il mio account")


def test_elimina_l_account_non_riuscito_lascia_gli_avvisi(web):
    """Con la password sbagliata il server non elimina niente: gli avvisi di questo dispositivo restano accesi, nel browser e sul
    server. Prima si toglievano prima che il server controllasse la password (#801)."""
    solo(web, "prima")
    disiscritte, elimina = elimina_l_account(web, 403)
    elimina.click(timeout=10000)
    web.pagina.locator("#avviso").filter(has_text="La password non va bene").wait_for(timeout=10000)
    web.aspetta()
    assert disiscritte == [], f"gli avvisi si sono tolti dal server con un'eliminazione non riuscita: {disiscritte}"
    assert iscrizione_nel_browser(web) == ENDPOINT
    assert titolo(web) == "Il tuo account"


def test_elimina_l_account_riuscito_toglie_gli_avvisi_dal_browser(web):
    """Riuscita, l'eliminazione cancella sul server anche gli avvisi: il browser toglie la sua iscrizione e la pagina si ricarica.
    (Il «chi sono» finto risponde sempre con l'utente: le copie le rimette l'avvio dopo la ricarica, qui non si guardano.)"""
    solo(web, "prima")
    _, elimina = elimina_l_account(web, 200)
    with web.pagina.expect_navigation(wait_until="load"):          # la ricarica dopo l'eliminazione, non l'apertura della pagina
        elimina.click(timeout=10000)
    assert iscrizione_nel_browser(web) is None


def con_tab_fino_a(web, bersaglio, massimo: int = 30) -> bool:
    """Avanti con Tab dal fuoco di adesso: si arriva su `bersaglio`?"""
    for _ in range(massimo):
        web.pagina.keyboard.press("Tab")
        if bersaglio.evaluate("e => e === document.activeElement"):
            return True
    return False


def selettore_intercettato(web) -> None:
    """Prima di aprire il selettore dei file con un tasto. Playwright intercetta il selettore solo da quando qualcuno ne ascolta
    l'evento, e lo chiede al browser senza aspettare risposta: un tasto è un messaggio solo e può arrivare prima, e allora il
    selettore vero si apre e si chiude senza evento (è successo una volta su GitHub). Un ascoltatore messo subito la tiene accesa."""
    web.pagina.on("filechooser", lambda _scelta: None)


# un'immagine PNG di 1×1 pixel
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005"
                    "0001ff5c6d2d6b0000000049454e44ae426082")


def test_scegli_il_file_delle_rose_si_raggiunge_con_tab_e_apre_il_selettore(web):
    """«Scegli il file» di Aggiorna le rose era un'etichetta di un campo nascosto: con Tab non ci si arrivava. Ora è un pulsante vero
    che apre il selettore dei file, come nel primo avvio; il file scelto va subito al controllo delle rose (#801)."""
    solo(web, "prima")
    selettore_intercettato(web)
    web.apri("/?vista=impostazioni&gruppo=rose")
    scegli = principale(web).get_by_role("button", name="Scegli il file (Excel o CSV)")
    assert scegli.count() == 1, "«Scegli il file» non è un pulsante"
    principale(web).get_by_role("button", name="Impostazioni").focus()            # «‹ Impostazioni», in cima alla pagina
    assert con_tab_fino_a(web, scegli), "con Tab non si arriva a «Scegli il file»"
    with web.pagina.expect_file_chooser() as scelta:
        web.pagina.keyboard.press("Enter")
    assert ".xlsx" in scelta.value.element.get_attribute("accept")
    with web.pagina.expect_request(lambda r: r.method == "POST" and urlsplit(r.url).path.startswith("/api/rose")) as mandata:
        scelta.value.set_files({"name": "rose.csv", "mimeType": "text/csv", "buffer": "Squadra;Ruolo;Calciatore\n".encode()})
    assert urlsplit(mandata.value.url).path == "/api/rose/anteprima/file"           # il controllo delle rose, con il file


def test_file_o_foto_di_stemma_e_maglia_si_raggiungono_con_tab_e_caricano(web):
    """«Da file o foto» del foglio di stemma e maglia era un'etichetta di un campo nascosto: con Tab non ci si arrivava. Ora sono
    due pulsanti veri; quello della maglia apre il selettore e l'immagine scelta si carica come maglia (#801)."""
    solo(web, "prima")
    selettore_intercettato(web)
    _mia_con_stemma(web)
    caricate = []
    web.pagina.route(lambda u: urlsplit(u).path == "/api/squadre/immagine",
                     lambda r: (r.request.method == "POST" and caricate.append(parse_qs(urlsplit(r.request.url).query)["tipo"]),
                                json_200(r, {"ok": True})))
    web.apri("/?vista=impostazioni&gruppo=squadra")
    tocca(web, principale(web).get_by_role("button", name="Stemma e maglia"))
    foglio = web.pagina.get_by_role("dialog")
    pulsanti = foglio.get_by_role("button", name="Da file o foto")
    assert pulsanti.count() == 2, "«Da file o foto» non è un pulsante"
    foglio.get_by_role("combobox").focus()                                       # la squadra, in cima al foglio
    assert con_tab_fino_a(web, pulsanti.nth(0)), "con Tab non si arriva a «Da file o foto» dello stemma"
    assert con_tab_fino_a(web, pulsanti.nth(1)), "con Tab non si arriva a «Da file o foto» della maglia"
    with web.pagina.expect_file_chooser() as scelta:
        web.pagina.keyboard.press("Enter")
    scelta.value.set_files({"name": "maglia.png", "mimeType": "image/png", "buffer": PNG})
    web.pagina.locator("#avviso").filter(has_text="Maglia aggiornata").wait_for(timeout=10000)
    assert caricate == [["maglia"]]


def test_le_regole_salvate_a_scheda_cambiata_non_ridisegnano_la_pagina_vecchia(web):
    """Il salvataggio delle Regole risponde quando si è già passati a un'altra scheda (rete lenta): la pagina in vista resta quella,
    e l'avviso dice comunque che le regole sono salvate. Prima le Regole si ridisegnavano sotto la barra della Formazione (#801)."""
    solo(web, "prima")
    web.risposta("/api/regole/riconosci", RICONOSCIUTE)
    tenute = []
    web.pagina.route(lambda u: urlsplit(u).path == "/api/regole",
                     lambda r: tenute.append(r) if r.request.method == "PUT" else r.fallback())
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_role("textbox", name="Incolla qui il testo del regolamento").fill("Crediti: 500\nAssist +1,5")
    tocca(web, principale(web).get_by_role("button", name="Riconosci le regole"))
    principale(web).get_by_role("button", name="Salva queste regole").click(timeout=10000)
    tocca(web, barra(web).get_by_role("link", name="Formazione"))
    assert len(tenute) == 1 and titolo(web) == "Formazione"
    tenute[0].fulfill(status=200, content_type="application/json", body=json.dumps(web.registrata("/api/regole")))
    web.pagina.locator("#avviso").filter(has_text="Regole salvate").wait_for(timeout=10000)
    web.aspetta()
    assert titolo(web) == "Formazione", f"dopo il salvataggio si vede «{titolo(web)}» sotto la barra della Formazione"
    assert web.pagina.url.endswith("/?vista=formazione")


@pytest.mark.parametrize("lingua, frase", [("it", "Non ho potuto usare l'immagine condivisa"), ("en", "I could not use the shared image")])
def test_l_immagine_condivisa_non_usata_si_dice_nella_lingua_dell_app(web, lingua, frase):
    """Dal menu Condividi del telefono con un'immagine che il server non prende (`?condivisa=no`) l'avviso viene dal catalogo, nella
    lingua dell'app: prima era scritto in italiano nel codice (#801)."""
    solo(web, "prima")
    web.memoria({"lingua": lingua})
    web.apri("/?condivisa=no")
    web.pagina.locator("#avviso").filter(has_text=frase).wait_for(timeout=10000)
    assert "PNG, JPEG" in web.pagina.locator("#avviso").inner_text()
