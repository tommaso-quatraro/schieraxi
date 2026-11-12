"""Test della web in un browser vero (issue #619): Chrome senza finestra, con le risposte registrate delle tre fasi della giornata.

Il server di prova è quello della regressione visiva (`ServerFinto` di script/ci/aspetto_web.py): serve `fanta/web/` e risponde
alle `/api/...` con uno scenario registrato di ios/fotografie/ (nomi inventati). Niente server vero, niente rete, nessun segreto.
Ogni test che chiede `web` gira tre volte, una per fase: `prima` (prima della scadenza), `in-corso`, `finita`.

Si lanciano a parte, con l'ambiente di Playwright (tests/browser/LEGGIMI.md):
    <venv-playwright>/python -m pytest -m browser --confcutdir tests/browser tests/browser
Nella suite normale (senza `-m browser`) si saltano. Senza la libreria Playwright o senza Chrome si saltano; con la variabile
BROWSER_OBBLIGATORIO=1 (il job «browser» dei controlli) invece falliscono: lì un test saltato sarebbe un verde finto.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RADICE = Path(__file__).resolve().parents[2]
WEB = RADICE / "fanta" / "web"
SCENARI = RADICE / "ios" / "fotografie"
AXE = RADICE / "tests" / "strumenti" / "axe" / "axe.min.js"
FASI = {"prima": "vero-prima.json", "in-corso": "vero-in-corso.json", "finita": "vero-finita.json"}
TEMI = {"chiaro": "light", "scuro": "dark"}
REGOLE_AXE = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]       # WCAG 2.0, 2.1 e 2.2, livelli A e AA
FUSO = "Europe/Rome"                                              # «adesso» dello scenario è l'ora italiana
# Rotte che le registrazioni tolgono apposta (prove/fotografie_dal_vero.py), con la risposta del server vero quando non ha dati.
# /api/avatar: i tratti dei volti vengono dalle foto vere dei calciatori; senza tratti l'app disegna i volti dal codice.
RISPOSTE_IN_PIU = {"/api/avatar": {"versione": 3, "tratti": {}}}

# La pagina è pronta quando la rete è ferma e poi il DOM non cambia per 300 ms (al massimo 8 s): vale per ogni versione della
# web, senza selettori di una schermata.
DOM_FERMO = """() => new Promise(fatto => {
  let ultimo = performance.now();
  const inizio = ultimo;
  const osservatore = new MutationObserver(() => { ultimo = performance.now(); });
  osservatore.observe(document, {subtree: true, childList: true, attributes: true, characterData: true});
  const giro = () => {
    const ora = performance.now();
    if (ora - ultimo >= 300 || ora - inizio >= 8000) { osservatore.disconnect(); fatto(); } else setTimeout(giro, 50);
  };
  setTimeout(giro, 50);
})"""
# Le schermate entrano sfumando: a metà animazione axe misurerebbe contrasti più bassi del vero. Le animazioni con una fine si
# portano alla fine (quelle senza fine, come le rotelle, restano).
FINISCI_ANIMAZIONI = """() => document.getAnimations().forEach(a => {
  try { if (a.effect && a.effect.getComputedTiming().endTime !== Infinity) a.finish(); } catch (e) {} })"""
SCORRE_DI_LATO = "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
LANCIA_AXE = """(regole) => axe.run(document, {runOnly: {type: 'tag', values: regole}, resultTypes: ['violations']})
  .then(r => r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, n: v.nodes.length,
    nodi: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))"""


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: test della web in Chrome senza finestra (tests/browser/LEGGIMI.md)")


def pytest_collection_modifyitems(config, items):
    """I test del browser girano solo se scelti con `-m browser`: la suite normale non apre Chrome."""
    if "browser" in (config.getoption("markexpr") or ""):
        return
    salta = pytest.mark.skip(reason="test del browser: si lanciano a parte con -m browser (tests/browser/LEGGIMI.md)")
    for item in items:
        if item.get_closest_marker("browser"):
            item.add_marker(salta)


def _manca(motivo: str):
    if os.environ.get("BROWSER_OBBLIGATORIO") == "1":
        pytest.fail(f"{motivo} (BROWSER_OBBLIGATORIO=1: qui un test saltato sarebbe un verde finto)", pytrace=False)
    pytest.skip(f"{motivo}: vedi tests/browser/LEGGIMI.md")


def _aspetto_web():
    """script/ci/aspetto_web.py come modulo (non è un pacchetto): il server finto e la scelta degli indirizzi locali."""
    spec = importlib.util.spec_from_file_location("aspetto_web_per_browser", RADICE / "script" / "ci" / "aspetto_web.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo          # le dataclass con `from __future__ import annotations` cercano qui il loro modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="session")
def chrome():
    """Chrome di sistema senza finestra (nessun browser scaricato da Playwright), uno per tutta la sessione."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _manca("manca la libreria Playwright")
    p = sync_playwright().start()
    try:
        browser = p.chromium.launch(channel="chrome", headless=True)
    except Exception as e:                   # Chrome non installato o che non parte
        p.stop()
        _manca(f"Chrome non parte ({type(e).__name__}: {(str(e).splitlines() or [''])[0][:160]})")
    yield browser
    browser.close()
    p.stop()


@dataclass
class ServerFase:
    fase: str
    indirizzo: str
    adesso: str


def scenario_completo(fase: str, cartella: Path) -> Path:
    """Lo scenario registrato della fase con le RISPOSTE_IN_PIU che mancano (quelle registrate restano come sono), scritto in
    `cartella`: il server finto lo legge come uno scenario qualsiasi."""
    dati = json.loads((SCENARI / FASI[fase]).read_text(encoding="utf-8"))
    for rotta, risposta in RISPOSTE_IN_PIU.items():
        dati["risposte"].setdefault(rotta, risposta)
    percorso = Path(cartella) / f"{fase}.json"
    percorso.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
    return percorso


@pytest.fixture(scope="session", params=list(FASI))
def server_fase(request, tmp_path_factory):
    """Il server di prova di una fase, su un indirizzo di loopback suo (127.0.0.NN) e una porta libera."""
    aw = _aspetto_web()
    scenario = scenario_completo(request.param, tmp_path_factory.mktemp(f"scenario-{request.param}"))
    host = aw.host_per(aw.porta_libera("127.0.0.1") + list(FASI).index(request.param))
    with aw.ServerFinto(WEB, scenario, aw.porta_libera(host), host=host) as s:
        yield ServerFase(request.param, s.indirizzo, s.adesso)


@dataclass
class Web:
    """Una scheda di Chrome sulla web di una fase. Raccoglie da sola gli errori della console (anche quelli del codice) e le
    richieste fallite (risposta 4xx o 5xx, o richiesta che non arriva): i test li leggono dopo `apri`."""
    pagina: object
    server: ServerFase
    errori_console: list[str] = field(default_factory=list)
    richieste_fallite: list[str] = field(default_factory=list)

    @property
    def fase(self) -> str:
        return self.server.fase

    def apri(self, percorso: str = "/", larghezza: int = 390, tema: str = "chiaro") -> None:
        """Apre un indirizzo della web alla larghezza e nel tema dati e aspetta che la pagina sia ferma."""
        self.pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
        self.pagina.emulate_media(color_scheme=TEMI[tema], reduced_motion="reduce")
        self.pagina.goto(self.server.indirizzo + percorso, wait_until="load")
        self.aspetta()

    def aspetta(self) -> None:
        """Dopo un clic o un cambio: rete ferma (al massimo 10 s), poi DOM fermo, poi animazioni portate alla fine."""
        try:
            self.pagina.wait_for_load_state("networkidle", timeout=10000)
        except Exception:                    # una richiesta lunga: si va avanti, il DOM fermo basta
            pass
        self.pagina.evaluate(DOM_FERMO)
        self.pagina.evaluate(FINISCI_ANIMAZIONI)

    def testo_visibile(self) -> str:
        return self.pagina.evaluate("() => (document.body && document.body.innerText || '').trim()")

    def scorre_di_lato(self) -> bool:
        return self.pagina.evaluate(SCORRE_DI_LATO)

    def violazioni_gravi(self) -> list[dict]:
        """Le violazioni di axe di gravità `critical` o `serious` nella pagina com'è adesso."""
        self.pagina.evaluate(AXE.read_text(encoding="utf-8"))     # come testo: un tag <script> lo fermerebbe la CSP dell'app
        return [v for v in self.pagina.evaluate(LANCIA_AXE, REGOLE_AXE) if v["impact"] in ("critical", "serious")]


def _breve(indirizzo: str) -> str:
    """Per il server finto solo percorso e query (l'indirizzo e la porta cambiano a ogni corsa); gli altri interi."""
    parti = urlsplit(indirizzo)
    if not (parti.hostname or "").startswith("127."):
        return indirizzo
    return parti.path + ("?" + parti.query if parti.query else "")


def _richiesta_non_arrivata(w: Web, richiesta) -> None:
    # Una richiesta annullata (la pagina cambia, o il codice la interrompe apposta) non è un guasto: Chrome dice ERR_ABORTED.
    if richiesta.failure and "ERR_ABORTED" in richiesta.failure:
        return
    w.richieste_fallite.append(f"{richiesta.method} {_breve(richiesta.url)}: {richiesta.failure or 'non arrivata'}")


@pytest.fixture
def web(chrome, server_fase):
    """Una scheda nuova (nessun dato salvato da un test prima) sulla web di una fase, con l'orologio fermo su «adesso» dello
    scenario, in italiano, ora italiana, movimento ridotto, service worker bloccato."""
    ctx = chrome.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, locale="it-IT",
                             timezone_id=FUSO, service_workers="block", reduced_motion="reduce")
    try:
        pagina = ctx.new_page()
        istante = pagina.evaluate("(s) => new Date(s).getTime()", server_fase.adesso)     # letto con il fuso italiano
        ctx.clock.set_fixed_time(istante / 1000)
        w = Web(pagina, server_fase)
        pagina.on("console", lambda m: m.type == "error" and w.errori_console.append(
            f"{m.text} ({_breve(m.location.get('url') or '')})"))
        pagina.on("pageerror", lambda e: w.errori_console.append(f"errore nel codice: {e}"))
        pagina.on("requestfailed", lambda r: _richiesta_non_arrivata(w, r))
        pagina.on("response", lambda r: r.status >= 400 and w.richieste_fallite.append(
            f"{r.request.method} {_breve(r.url)}: risposta {r.status}"))
        yield w
    finally:
        ctx.close()
