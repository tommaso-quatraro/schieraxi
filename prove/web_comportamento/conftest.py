"""Test di comportamento della web app in un browser vero, senza finestra (vedi LEGGIMI.md).

Playwright non sta nei requisiti del progetto: senza, questi test si saltano da soli e la suite normale non cambia.
I pezzi comuni (server finto, attese, la `Schermata`) stanno in web_di_prova.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))          # web_di_prova, anche lanciando pytest dalla radice

from web_di_prova import FASI, RADICE, TELEFONO, WEB, Schermata, aspetto_web  # noqa: E402


@pytest.fixture(scope="session")
def chrome():
    """Chrome di sistema senza finestra, uno per tutta la corsa. Senza Playwright o senza Chrome i test si saltano."""
    api = pytest.importorskip("playwright.sync_api", reason="serve Playwright in un ambiente a parte (prove/web_comportamento/LEGGIMI.md)")
    with api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception as e:                           # Chrome non installato
            pytest.skip(f"Chrome di sistema non parte: {type(e).__name__}")
        yield browser
        browser.close()


@pytest.fixture
def apri(chrome, tmp_path):
    """`apri(indirizzo, fase="prima", misura=TELEFONO, risposte={...}, memoria={...})` -> Schermata.

    `fase`: prima, in-corso, finita (le risposte registrate di ios/fotografie/vero-*.json, con l'orologio fermo su quel momento).
    `risposte`: risposte in più o diverse da quelle registrate (rotta -> oggetto JSON; `...` = la rotta non risponde, il server
    finto dà 404). `memoria`: valori messi in localStorage prima che la pagina parta la prima volta (una preferenza salvata da
    una versione di prima).
    Alla fine del test: nessun errore del JavaScript in nessuna delle pagine aperte."""
    aspetto = aspetto_web()
    aperti, schermate = [], []

    def _apri(indirizzo: str = "/", fase: str = "prima", misura=TELEFONO, risposte=None, memoria=None) -> Schermata:
        scenario = RADICE / "ios" / "fotografie" / FASI[fase]
        if risposte:
            dati = json.loads(scenario.read_text(encoding="utf-8"))
            dati["risposte"].update({k: json.dumps(v) for k, v in risposte.items() if v is not ...})
            for rotta in [k for k, v in risposte.items() if v is ...]:
                dati["risposte"].pop(rotta, None)
            scenario = tmp_path / f"scenario-{len(aperti)}.json"
            scenario.write_text(json.dumps(dati), encoding="utf-8")
        host = aspetto.host_per(aspetto.porta_libera("127.0.0.1"))
        server = aspetto.ServerFinto(WEB, scenario, aspetto.porta_libera(host), host=host)
        server.__enter__()
        aperti.append(lambda: server.__exit__(None, None, None))
        ctx = chrome.new_context(viewport={"width": misura[0], "height": misura[1]}, device_scale_factor=1, locale="it-IT",
                                 timezone_id=aspetto.FUSO, service_workers="block", reduced_motion="reduce")
        aperti.append(ctx.close)
        pagina = ctx.new_page()
        ctx.clock.set_fixed_time(pagina.evaluate("(s) => new Date(s).getTime()", server.adesso) / 1000)
        memoria = {"lingua": "it", **(memoria or {})}
        # la memoria si prepara una volta sola per scheda: poi resta quella che l'app scrive, anche cambiando pagina
        ctx.add_init_script("try { if (!sessionStorage.getItem('prova-pronta')) { localStorage.clear(); sessionStorage.setItem('prova-pronta', '1'); "
                            + "".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(v)}); " for k, v in memoria.items())
                            + "} } catch (e) {}")
        s = Schermata(pagina, server.indirizzo)
        pagina.on("request", lambda r: s.richieste.append(r.url[len(s.base):]) if r.url.startswith(s.base + "/api/") else None)
        pagina.on("pageerror", lambda e: s.errori.append(str(e)))
        schermate.append(s)
        s.vai(indirizzo)
        return s

    yield _apri
    for chiudi in reversed(aperti):
        chiudi()
    assert [e for s in schermate for e in s.errori] == [], "errori del JavaScript nella pagina"
