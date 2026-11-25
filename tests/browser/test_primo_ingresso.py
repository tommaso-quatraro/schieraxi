"""Il percorso di un amico nuovo sulla web (#873): primo avvio, Giornate senza rose, ore tranquille, rientro dopo un'uscita.

Il collaudo del 25/11 aveva trovato cose che confondono (nessun passo bloccato): i fantavoti attesi usano i punteggi più comuni e
nessuno lo dice; con una sola squadra un avviso prometteva gli scambi e copriva la Formazione; il passo delle rose non diceva da dove
prenderle; l'anteprima di dieci squadre al telefono era lunga quattro schermi; il passo evidenziato non era quello della domanda; su PC
il pannello si allargava e cambiava la grandezza del testo; Giornate senza rose chiedeva il diario (409) e prometteva consigli; le ore
tranquille spente sembravano accese; dopo un nuovo accesso si tornava su «Il tuo account». Girano solo prima della scadenza: conta il
percorso, non la fase della giornata. Le rose le dà il test (account senza rose finché non si confermano).
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

SENZA_ROSE = {"detail": "Nessuna rosa importata: importa le rose della tua lega."}
# L'avviso del server con una sola squadra: il testo vero, dal catalogo (srv.* è parola per parola il messaggio del server,
# tests/test_testi.py), non uno scritto qui.
UNA_SQUADRA = json.loads((Path(__file__).resolve().parents[2] / "fanta" / "testi" / "srv.json").read_text(encoding="utf-8"))[
    "srv.una_sola_squadra"]["it"]
UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
SENZA_SESSIONE = {"detail": "Accesso richiesto", "multiutente": True, "registrazione": "invito", "social": [], "email_attiva": True}


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("conta il percorso, non la fase della giornata")


def _rispondi(route, corpo, stato=200):
    route.fulfill(status=stato, content_type="application/json; charset=utf-8", body=json.dumps(corpo, ensure_ascii=False))


def _rotta(percorso):
    return lambda u: urlsplit(u).path == percorso


def account_senza_rose(web) -> dict:
    """Prima di `apri`: un account appena nato, senza rose, con il primo avvio cominciato (si apre da solo). Quando si confermano le
    rose (`POST /api/rose/testo`) `lega["salvate"]` diventa vero e stato, squadre, Formazione e Giornate rispondono come lo scenario
    registrato. Il primo avvio ricorda i passi come il server."""
    lega = {"salvate": False, "primo": {"fatti": ["server", "accesso"], "saltati": [], "chiuso": False}}
    stato, oggi, squadre = web.registrata("/api/stato"), web.registrata("/api/oggi"), web.registrata("/api/squadre")

    def primo_avvio(route):
        if route.request.method == "PUT":
            lega["primo"].update(json.loads(route.request.post_data))
        _rispondi(route, {"primo_avvio": lega["primo"]})

    def senza_finche_non_salvate(route):                     # formazione e diario: 409 come il server, finché non ci sono le rose
        if lega["salvate"]:
            route.fallback()
        else:
            _rispondi(route, SENZA_ROSE, 409)

    web.pagina.route(_rotta("/api/primo-avvio"), primo_avvio)
    web.pagina.route(_rotta("/api/stato"), lambda r: _rispondi(r, stato if lega["salvate"] else {**stato, "rose_importate": False, "mia_squadra": None}))
    web.pagina.route(_rotta("/api/squadre"), lambda r: _rispondi(r, squadre if lega["salvate"] else []))
    web.pagina.route(_rotta("/api/oggi"), lambda r: _rispondi(r, oggi if lega["salvate"] else {**oggi, "senza_rose": True, "da_fare": []}))
    web.pagina.route(_rotta("/api/formazione"), senza_finche_non_salvate)
    web.pagina.route(_rotta("/api/diario"), senza_finche_non_salvate)
    return lega


def anteprima_finta(web, lega: dict, squadre: int, rifiuto: tuple[int, dict] | None = None) -> None:
    """L'anteprima di `squadre` squadre complete, tutte riconosciute, alla prima importazione; la conferma salva le rose (con
    `rifiuto` = (stato, corpo) il salvataggio non riesce)."""
    elenco = [{"nome": f"Squadra di prova {i + 1}", "nuova": True, "totale": 25, "attesi": 25, "mancano": {}, "in_piu": {}, "senza_ruolo": 0,
               "crediti_residui": None, "avvisi": [],
               "giocatori": [{"testo": f"Giocatore {i}-{j}", "nome": f"Giocatore {i}-{j}", "stato": "sicuro", "id": 9000 + 100 * i + j, "riga": j}
                             for j in range(25)]} for i in range(squadre)]
    avvisi = [UNA_SQUADRA] if squadre == 1 else []
    risposta = {"squadre": elenco, "avvisi": avvisi, "avvisi_frasi": [None] * len(avvisi), "mia_squadra": None, "totale_squadre": squadre,
                "sicuri": 25 * squadre, "da_controllare": 0, "non_trovati": 0,
                "differenze": {"prima_importazione": True, "nessuna_differenza": False, "testo": ""}, "riepilogo": ""}

    def salva(route):
        if rifiuto:
            _rispondi(route, rifiuto[1], rifiuto[0])
            return
        lega["salvate"] = True
        _rispondi(route, {"totale_squadre": squadre, "squadre_importate": [s["nome"] for s in elenco], "avvisi": avvisi,
                          "differenze": risposta["differenze"]})

    web.pagina.route(_rotta("/api/rose/anteprima"), lambda r: _rispondi(r, risposta))
    web.pagina.route(_rotta("/api/rose/testo"), salva)


def guida(web):
    return web.pagina.get_by_role("dialog")


def titolo_della_guida(web, nome: str) -> None:
    guida(web).get_by_role("heading", name=nome, exact=True).wait_for(timeout=10000)


def controlla_le_rose(web) -> None:
    guida(web).get_by_label("Testo delle rose").fill("Squadra di prova 1\nP;Giocatore;JUV;1\n")
    guida(web).get_by_role("button", name="Controlla le rose").click(timeout=10000)
    titolo_della_guida(web, "Controlla prima di salvare")
    web.aspetta()


def passo_evidenziato(web) -> str:
    return " ".join(guida(web).locator('[aria-current="step"]').inner_text().split())


def in_vista_e_toccabile(web, bersaglio) -> bool:
    """Il pulsante sta tutto nella finestra e un tocco al suo centro arriva a lui (non a ciò che gli passa sopra)."""
    b = bersaglio.bounding_box()
    alto = web.pagina.viewport_size["height"]
    if not b or b["y"] < 0 or b["y"] + b["height"] > alto:
        return False
    return bersaglio.evaluate("(el, p) => el.contains(document.elementFromPoint(p.x, p.y))",
                              {"x": b["x"] + b["width"] / 2, "y": b["y"] + b["height"] / 2})


def misura_del_passo(web) -> tuple[float, str]:
    """Larghezza del pannello della guida e grandezza del testo del primo paragrafo che si vede (la spiegazione del passo)."""
    return guida(web).evaluate("""el => {
      const p = [...el.querySelectorAll('p')].find(x => x.offsetParent !== null && x.textContent.trim());
      return [Math.round(el.getBoundingClientRect().width), p ? getComputedStyle(p).fontSize : ''];
    }""")


# ---------------------------------------------------------------- primo avvio al telefono
def test_primo_avvio_al_telefono_dice_da_dove_prendere_le_rose_e_la_conferma_si_raggiunge(web):
    """Passo «Le rose»: dice di esportarle da Leghe e che basta la propria squadra. L'anteprima di dieci squadre: «Conferma e salva»
    si tocca senza scorrere, «Nuova» non si ripete alla prima importazione e il passo evidenziato è «La tua squadra», la domanda in
    cima. Confermate le rose, la Formazione dietro la guida non chiede più di importarle."""
    solo_prima(web)
    lega = account_senza_rose(web)
    anteprima_finta(web, lega, 10)
    web.apri("/", larghezza=390)
    titolo_della_guida(web, "Le rose")
    testo = " ".join(guida(web).inner_text().split())
    assert "Esporta le rose da Leghe" in testo and "basta anche solo la tua squadra" in testo, testo[:400]
    controlla_le_rose(web)
    assert guida(web).get_by_text("Qual è la tua squadra?").is_visible()
    assert passo_evidenziato(web).startswith("La tua squadra"), passo_evidenziato(web)
    assert guida(web).get_by_text("Nuova", exact=True).count() == 0, "«Nuova» ripetuto su ogni squadra alla prima importazione"
    conferma = guida(web).get_by_role("button", name="Conferma e salva")
    assert in_vista_e_toccabile(web, conferma), "«Conferma e salva» non si tocca senza scorrere"
    guida(web).get_by_role("radio", name="Squadra di prova 3").check()
    conferma.click(timeout=10000)
    titolo_della_guida(web, "I tempi della lega")
    web.aspetta()
    assert passo_evidenziato(web).startswith("I tempi della lega")
    assert "Importa le rose" not in web.testo_principale(), web.testo_principale()[:300]
    assert not web.errori_console, web.errori_console


def test_con_una_sola_squadra_niente_avviso_sopra_la_formazione_e_le_regole_si_trovano(web):
    """Una sola squadra: l'anteprima lo dice senza promettere gli scambi, e dopo la conferma nessun avviso copre la pagina. A «Tutto
    pronto» una frase dice che i fantavoti attesi usano i punteggi più comuni, con il collegamento a Regole e scadenza."""
    solo_prima(web)
    lega = account_senza_rose(web)
    anteprima_finta(web, lega, 1)
    web.apri("/", larghezza=390)
    titolo_della_guida(web, "Le rose")
    controlla_le_rose(web)
    testo = " ".join(guida(web).inner_text().split())
    assert UNA_SQUADRA in testo and "scambi" not in testo, testo
    guida(web).get_by_role("radio", name="Squadra di prova 1").check()
    guida(web).get_by_role("button", name="Conferma e salva").click(timeout=10000)
    titolo_della_guida(web, "I tempi della lega")
    assert not web.pagina.locator("#avviso").is_visible(), web.pagina.locator("#avviso").inner_text()
    guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    titolo_della_guida(web, "Tutto pronto, Mister")
    testo = " ".join(guida(web).inner_text().split())
    assert "punteggi più comuni" in testo, testo
    regole = guida(web).get_by_role("link", name="Regole e scadenza")
    assert min(r["height"] for r in regole.evaluate("a => [...a.getClientRects()].map(r => ({height: r.height}))")) >= 44, \
        "il collegamento si tocca male: meno di 44 px"
    regole.click(timeout=10000)
    web.aspetta()
    assert guida(web).count() == 0 or not guida(web).is_visible()
    assert "gruppo=regole" in web.pagina.url
    assert web.pagina.locator("main").get_by_role("heading", level=1).inner_text().strip() == "Regole e scadenza"
    assert lega["primo"].get("chiuso") is True, lega["primo"]


@pytest.mark.parametrize("rifiuto", [(429, {"detail": "Hai fatto troppe importazioni oggi: riprova domani."}),
                                     (500, {"detail": "Errore interno del server"}), ("rete", None)])
def test_al_telefono_un_salvataggio_che_non_riesce_si_vede_sopra_conferma(web, rifiuto):
    """«Conferma e salva» resta fermo in fondo al foglio: anche il messaggio del salvataggio non riuscito (troppe importazioni, guasto
    del server, niente rete) sta lì, sopra i pulsanti, in vista. Prima restava in fondo all'elenco, a due schermi di distanza."""
    solo_prima(web)
    lega = account_senza_rose(web)
    anteprima_finta(web, lega, 10, rifiuto if rifiuto[0] != "rete" else None)
    if rifiuto[0] == "rete":
        web.pagina.route(_rotta("/api/rose/testo"), lambda r: r.abort())
    web.apri("/", larghezza=390)
    titolo_della_guida(web, "Le rose")
    controlla_le_rose(web)
    guida(web).get_by_role("button", name="Conferma e salva").click(timeout=10000)
    errore = guida(web).locator('[role="alert"]:not(:empty)')
    errore.wait_for(timeout=10000)
    web.aspetta()
    assert in_vista_e_toccabile(web, errore), f"il messaggio non si vede: {errore.bounding_box()} - {errore.inner_text()}"
    assert in_vista_e_toccabile(web, guida(web).get_by_role("button", name="Conferma e salva"))


def test_al_telefono_con_il_tasto_tab_nessuna_squadra_finisce_sotto_la_barra(web):
    """Con la tastiera (Tab) ogni riga delle squadre che prende il fuoco sta sopra la barra ferma di «Conferma e salva»."""
    solo_prima(web)
    lega = account_senza_rose(web)
    anteprima_finta(web, lega, 10)
    web.apri("/", larghezza=390)
    titolo_della_guida(web, "Le rose")
    controlla_le_rose(web)
    coperte = []
    for _ in range(30):
        web.pagina.keyboard.press("Tab")
        m = web.pagina.evaluate("""() => {
          const a = document.activeElement, barra = document.querySelector('#foglio-contenuto .ar-piede, #foglio-contenuto .ar > .pulsanti');
          if (!a || !a.closest('.ar-squadre') || !barra) return null;
          return {testo: a.textContent.trim().slice(0, 40), sotto: a.getBoundingClientRect().bottom, barra: barra.getBoundingClientRect().top};
        }""")
        if m and m["sotto"] > m["barra"] + 1:
            coperte.append(m)
    assert not coperte, f"righe con il fuoco sotto la barra: {coperte}"


# ---------------------------------------------------------------- primo avvio su PC
def test_primo_avvio_su_pc_stessa_larghezza_e_testo_in_ogni_passo(web):
    """A 1440 px il pannello della guida resta largo uguale e la spiegazione di ogni passo ha la stessa grandezza: le rose,
    l'anteprima, i tempi, «Tutto pronto»."""
    solo_prima(web)
    lega = account_senza_rose(web)
    anteprima_finta(web, lega, 3)
    web.apri("/", larghezza=1440)
    titolo_della_guida(web, "Le rose")
    misure = {"rose": misura_del_passo(web)}
    controlla_le_rose(web)
    misure["anteprima"] = misura_del_passo(web)
    guida(web).get_by_role("radio", name="Squadra di prova 2").check()
    guida(web).get_by_role("button", name="Conferma e salva").click(timeout=10000)
    titolo_della_guida(web, "I tempi della lega")
    misure["tempi"] = misura_del_passo(web)
    guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    titolo_della_guida(web, "Tutto pronto, Mister")
    misure["fine"] = misura_del_passo(web)
    assert len({m[0] for m in misure.values()}) == 1, f"il pannello cambia larghezza: {misure}"
    assert len({m[1] for m in misure.values()}) == 1, f"il testo cambia grandezza: {misure}"


# ---------------------------------------------------------------- Giornate senza rose
@pytest.mark.parametrize("larghezza", [390, 1440])
def test_giornate_senza_rose_non_chiede_il_diario_e_non_promette_consigli(web, larghezza):
    """Senza rose (lo dice /api/stato all'avvio) Giornate non chiede il diario, che il server rifiuterebbe con 409 (resta fra gli
    errori del browser), e non promette «consigli» qui: Giornate è com'è andata."""
    solo_prima(web)
    lega = account_senza_rose(web)
    lega["primo"].update({"saltati": ["rose", "squadra", "tempi"], "chiuso": True})          # la guida non si apre da sola
    web.apri("/?vista=giornate", larghezza=larghezza)
    principale = web.pagina.locator("main")
    assert principale.get_by_role("button", name="Importa le rose").is_visible()
    assert "consigli" not in web.testo_principale(), web.testo_principale()
    assert not [r for r in web.richieste if r.startswith("/api/diario")], web.richieste
    assert not web.richieste_fallite and not web.errori_console and not web.errori_mostrati()


def test_giornate_rilegge_lo_stato_se_le_rose_arrivano_da_un_altro_dispositivo(web):
    """All'avvio non c'erano rose; poi arrivano da un altro dispositivo (l'iPhone, un'altra scheda) senza ricaricare la pagina.
    Giornate non si fida dello stato letto all'avvio: lo rilegge e mostra il diario, non «Prima le tue rose»."""
    solo_prima(web)
    lega = account_senza_rose(web)
    lega["primo"].update({"saltati": ["rose", "squadra", "tempi"], "chiuso": True})
    web.apri("/?vista=formazione")
    assert "Importa le rose" in web.testo_principale()
    lega["salvate"] = True                                   # importate altrove: il server ora ha le rose
    web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Giornate").click(timeout=10000)
    web.aspetta()
    assert "Prima le tue rose" not in web.testo_principale(), web.testo_principale()[:300]
    assert [r for r in web.richieste if r.startswith("/api/diario")], web.richieste
    assert not web.errori_mostrati() and not web.errori_console


# ---------------------------------------------------------------- ore tranquille
def riga_ore_tranquille(web):
    return web.pagina.locator("label", has=web.pagina.locator("#av_silenzio"))


def test_le_ore_tranquille_spente_dicono_che_sono_spente(web):
    """Con l'interruttore spento la riga non dice «Niente avvisi dalle 23 alle 7», come se fossero accese: dice che sono spente e
    l'orario che varrebbe; accese, l'orario."""
    solo_prima(web)
    avvisi = web.registrata("/api/avvisi")
    web.risposta("/api/avvisi", {**avvisi, "impostazioni": {**avvisi["impostazioni"], "silenzio": False}})
    web.apri("/?vista=impostazioni")
    riga = riga_ore_tranquille(web)
    riga.wait_for(timeout=10000)
    spente = " ".join(riga.locator("small").inner_text().split())               # la riga sotto il nome
    assert spente.lower().startswith("spente") and "dalle 23 alle 7" in spente, spente
    riga.click()
    web.aspetta()
    accese = " ".join(riga.locator("small").inner_text().split())
    assert web.pagina.locator("#av_silenzio").is_checked()
    assert accese == "Niente avvisi dalle 23 alle 7", accese


# ---------------------------------------------------------------- rientro
@pytest.mark.parametrize("ultima, attesa", [(None, "Formazione"), ("giornate", "Giornate")])
def test_dopo_un_accesso_si_apre_formazione_o_giornate_non_il_tuo_account(web, ultima, attesa):
    """Uscito da «Il tuo account», la pagina d'accesso resta su quell'indirizzo: dopo un nuovo accesso si apre l'ultima schermata fra
    Formazione e Giornate, come dice la guida, non di nuovo «Il tuo account»."""
    solo_prima(web)
    if ultima:
        web.memoria({"vista": ultima})
    web.risposta("/api/account/me", SENZA_SESSIONE, stato=401)
    web.pagina.set_viewport_size({"width": 390, "height": 844})
    web.pagina.goto(web.server.indirizzo + "/?vista=impostazioni&gruppo=account", wait_until="load")
    web.pagina.locator("#accesso-form").wait_for(timeout=10000)
    web.pagina.locator("#ac-nome").fill("amico")
    web.pagina.locator("#ac-pw").fill("password-di-prova")
    web.risposta("/api/account/accedi", {"utente": UTENTE["utente"]})
    web.risposta("/api/account/me", UTENTE)
    with web.pagina.expect_navigation(timeout=10000):
        web.pagina.locator("#accesso-invia").click()
    web.aspetta()
    titolo = web.pagina.locator("main").get_by_role("heading", level=1).inner_text().strip()
    assert titolo == attesa, f"dopo l'accesso si apre «{titolo}» ({web.pagina.url})"
