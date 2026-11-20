"""La copia dei dati tenuta nel browser e la lingua (#854).

La web tiene nel browser una copia delle ultime risposte del server, per mostrarle subito all'apertura e quando il server non
risponde. Alcune parole di quelle risposte le scrive il server nella lingua chiesta: le etichette di stato dei giocatori
(«In dubbio · gioca 19%», in inglese «Doubtful · plays 19%»). Giocatori e numeri invece sono gli stessi in ogni lingua.
- Con la rete, dopo il cambio di lingua la copia della lingua di prima non si mostra: si aspettano i dati nuovi (prima per un
  attimo comparivano le etichette in italiano con la pagina in inglese).
- Se i dati nuovi non arrivano, meglio la copia della lingua di prima, con la nota e «Riprova», che una pagina vuota: per
  decidere chi schierare servono giocatori e numeri. Lo stesso per una copia senza lingua, salvata da una versione di prima.

Il server finto risponde sempre con le parole registrate, in italiano. Qui le /api/ rispondono come il server vero: con
`Accept-Language: en` le etichette passano in inglese con `traduci_dati` di fanta/etichette.py, la funzione del server.
"""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ETICHETTE_PY = Path(__file__).resolve().parents[2] / "fanta" / "etichette.py"
# Toglie la lingua da ogni copia dei dati nel browser: come le ha lasciate una versione della web di prima del #854.
COPIE_SENZA_LINGUA = """() => Object.keys(localStorage).filter(k => k.startsWith('cache:')).map(k => {
  const x = JSON.parse(localStorage.getItem(k)); delete x.lingua; localStorage.setItem(k, JSON.stringify(x)); return k; })"""


def _etichette():
    """fanta/etichette.py come modulo (solo libreria standard): le parole del server nelle due lingue."""
    spec = importlib.util.spec_from_file_location("etichette_per_browser", ETICHETTE_PY)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("la lingua della copia non dipende dalla fase")


def principale(web):
    return web.pagina.locator("main")


def campo(web):
    """Il campo con gli 11: ogni titolare è un pulsante."""
    return principale(web).locator("#campo-formazione").get_by_role("button")


def _testo(web) -> str:
    return " ".join(web.testo_principale().split())


def _server_che_parla_la_lingua_chiesta(web) -> dict:
    """Le /api/ con le etichette nella lingua di `Accept-Language`, come il server vero. Restituisce gli interruttori della rete:
    - `rete["giu"] = True`: le /api/ non arrivano (il server non risponde); la pagina e i suoi file sì;
    - `rete["trattieni"] = True`: le /api/ restano in volo in `rete["ferme"]` finché il test non le lascia andare con
      `rete["rispondi"](route)` (la rete lenta)."""
    traduci = _etichette().traduci_dati
    rete = {"giu": False, "trattieni": False, "ferme": []}

    def rispondi(route):
        if not route.request.headers.get("accept-language", "").startswith("en"):
            route.fallback()
            return
        risposta = route.fetch()
        try:
            dati = risposta.json()
        except Exception:                    # noqa: BLE001 - una risposta che non è JSON passa com'è
            route.fulfill(response=risposta)
            return
        route.fulfill(response=risposta, body=json.dumps(traduci(dati, "en"), ensure_ascii=False))

    def smista(route):
        if rete["giu"]:
            route.abort("internetdisconnected")
        elif rete["trattieni"]:
            rete["ferme"].append(route)
        else:
            rispondi(route)

    rete["rispondi"] = rispondi
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), smista)
    return rete


def _formazione_in_italiano(web) -> None:
    """La Formazione in italiano, dal server: il browser ne tiene la copia. «In dubbio» si vede (la riserva in dubbio dello
    scenario): è l'etichetta che il server scrive nella lingua chiesta."""
    web.apri("/")
    assert "In dubbio" in _testo(web), "nella Formazione in italiano non si vede «In dubbio»: il test non proverebbe niente"


def _in_inglese(web, rete: dict, giu: bool) -> None:
    """«English» in Impostazioni (la pagina si ricarica), con il server che risponde o no (`giu`)."""
    web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Impostazioni").click(timeout=10000)
    web.aspetta()
    rete["giu"] = giu
    with web.pagina.expect_navigation():                 # la scelta della lingua ricarica la pagina
        principale(web).get_by_role("button", name="English").click(timeout=10000)
    web.aspetta()
    assert web.pagina.evaluate("document.documentElement.lang") == "en"


def _lineup(web):
    return web.pagina.get_by_role("navigation", name="Sections").get_by_role("link", name="Lineup")


def _riprova_con_la_rete(web, rete: dict, nome: str) -> None:
    """La rete torna e si tocca «Riprova» della nota: arrivano i dati nuovi e la nota sparisce."""
    rete["giu"] = False
    principale(web).get_by_role("button", name=nome).click(timeout=10000)
    web.aspetta()
    assert principale(web).get_by_role("button", name=nome).count() == 0, _testo(web)[:300]


def test_passata_all_inglese_con_la_rete_lenta_non_si_vede_la_copia_in_italiano(web):
    """Con la rete, mentre arrivano i dati in inglese la Formazione non mostra la copia italiana: si aspetta, poi «Doubtful»."""
    solo_prima(web)
    rete = _server_che_parla_la_lingua_chiesta(web)
    _formazione_in_italiano(web)
    _in_inglese(web, rete, giu=False)
    rete["trattieni"] = True
    with web.pagina.expect_request(lambda r: urlsplit(r.url).path == "/api/formazione"):
        _lineup(web).click(timeout=10000)
    testo = _testo(web)
    assert "In dubbio" not in testo, f"mentre arrivano i dati in inglese si vede la copia in italiano: {testo[:300]}"
    assert web.in_caricamento(), f"mentre arrivano i dati nuovi la Formazione dice che sta caricando: {testo[:300]}"
    rete["trattieni"] = False
    while rete["ferme"]:
        rete["rispondi"](rete["ferme"].pop(0))
    web.aspetta()
    testo = _testo(web)
    assert "Doubtful" in testo and "In dubbio" not in testo, testo[:300]


def test_passata_all_inglese_senza_rete_la_formazione_resta_con_la_copia_di_prima(web):
    """Senza rete dopo il cambio di lingua la Formazione mostra la copia presa in italiano (stessi giocatori e numeri), con la
    nota e «Try again»; tornata la rete, i dati in inglese prendono il suo posto."""
    solo_prima(web)
    rete = _server_che_parla_la_lingua_chiesta(web)
    _formazione_in_italiano(web)
    _in_inglese(web, rete, giu=True)
    _lineup(web).click(timeout=10000)
    web.aspetta()
    testo = _testo(web)
    assert campo(web).count() == 11, f"senza rete la Formazione non mostra la copia: {testo[:300]}"
    riprova = principale(web).get_by_role("button", name="Try again")
    assert riprova.count() == 1 and riprova.is_visible(), testo[:300]
    assert principale(web).get_by_label("Formation", exact=True).is_disabled(), "sulla copia i comandi che scrivono sono spenti"
    _riprova_con_la_rete(web, rete, "Try again")
    testo = _testo(web)
    assert campo(web).count() == 11 and "Doubtful" in testo and "In dubbio" not in testo, testo[:300]


def test_una_copia_senza_lingua_di_una_versione_di_prima_si_vede_senza_rete(web):
    """Dopo il rilascio le copie nel browser non hanno la lingua: senza rete la Formazione le mostra lo stesso, con la nota."""
    solo_prima(web)
    rete = _server_che_parla_la_lingua_chiesta(web)
    _formazione_in_italiano(web)
    assert web.pagina.evaluate(COPIE_SENZA_LINGUA), "nessuna copia dei dati nel browser"
    rete["giu"] = True
    web.pagina.reload(wait_until="load")
    web.aspetta()
    testo = _testo(web)
    assert campo(web).count() == 11, f"senza rete la Formazione non mostra la copia senza lingua: {testo[:300]}"
    assert principale(web).get_by_role("button", name="Riprova").count() == 1, testo[:300]
    _riprova_con_la_rete(web, rete, "Riprova")
    assert campo(web).count() == 11, _testo(web)[:300]
