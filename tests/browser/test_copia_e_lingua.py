"""La copia dei dati tenuta nel browser e la lingua (#854).

La web tiene nel browser una copia delle ultime risposte del server, per mostrarle subito all'apertura e quando il server non
risponde. Alcune parole di quelle risposte le scrive il server nella lingua chiesta: le etichette di stato dei giocatori
(«In dubbio · gioca 19%», in inglese «Doubtful · plays 19%»). Una copia presa in italiano non va mostrata con la web in inglese:
dopo il cambio di lingua le etichette restavano in italiano, per un attimo con la rete buona e per sempre senza rete.

Il server finto risponde sempre con le parole registrate, in italiano. Qui le /api/ rispondono come il server vero: con
`Accept-Language: en` le etichette passano in inglese con `traduci_dati` di fanta/etichette.py, la funzione del server.
"""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ETICHETTE_PY = Path(__file__).resolve().parents[2] / "fanta" / "etichette.py"


def _etichette():
    """fanta/etichette.py come modulo (solo libreria standard): le parole del server nelle due lingue."""
    spec = importlib.util.spec_from_file_location("etichette_per_browser", ETICHETTE_PY)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def principale(web):
    return web.pagina.locator("main")


def _testo(web) -> str:
    return " ".join(web.testo_principale().split())


def _server_che_parla_la_lingua_chiesta(web) -> dict:
    """Le /api/ con le etichette nella lingua di `Accept-Language`, come il server vero. Restituisce l'interruttore della rete:
    con `rete["giu"] = True` le /api/ non arrivano (il server non risponde), la pagina e i suoi file sì."""
    traduci = _etichette().traduci_dati
    rete = {"giu": False}

    def rispondi(route):
        if rete["giu"]:
            route.abort("internetdisconnected")
            return
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

    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), rispondi)
    return rete


def test_passata_all_inglese_la_formazione_non_mostra_la_copia_con_le_etichette_in_italiano(web):
    """Lingua italiana e Formazione caricata; poi «English» in Impostazioni con il server che non risponde. La copia salvata in
    italiano non compare in inglese: la pagina dice che il server non risponde e ha «Try again»; tornata la rete, le etichette
    arrivano in inglese."""
    if web.fase != "prima":
        pytest.skip("la lingua della copia non dipende dalla fase")
    rete = _server_che_parla_la_lingua_chiesta(web)
    web.apri("/")
    formazione = web.registrata("/api/formazione")
    parole = {s["etichetta"]["testo"].split(" · ")[0] for s in formazione["schede"].values() if s.get("etichetta")}
    italiane = sorted(p for p in parole if p in _testo(web))
    assert "In dubbio" in italiane, f"nella Formazione in italiano non si vede «In dubbio» ({italiane}): il test non proverebbe niente"

    web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Impostazioni").click(timeout=10000)
    web.aspetta()
    rete["giu"] = True
    with web.pagina.expect_navigation():                 # la scelta della lingua ricarica la pagina
        principale(web).get_by_role("button", name="English").click(timeout=10000)
    web.aspetta()
    web.pagina.get_by_role("navigation", name="Sections").get_by_role("link", name="Lineup").click(timeout=10000)
    web.aspetta()
    assert web.pagina.evaluate("document.documentElement.lang") == "en"
    testo = _testo(web)
    rimaste = [p for p in italiane if p in testo]
    assert not rimaste, f"la Formazione in inglese mostra la copia con le etichette in italiano {rimaste}: {testo[:300]}"
    assert not web.in_caricamento(), "senza copia nella lingua scelta la Formazione resta ferma sul caricamento"
    riprova = principale(web).get_by_role("button", name="Try again")
    assert riprova.count() == 1 and riprova.is_visible(), testo[:300]

    rete["giu"] = False
    riprova.click(timeout=10000)
    web.aspetta()
    testo = _testo(web)
    assert "Doubtful" in testo, testo[:300]
    assert not [p for p in italiane if p in testo], testo[:300]
