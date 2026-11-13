"""Test della web in un browser vero (issue #619): Chrome senza finestra, con le risposte registrate delle tre fasi della giornata.

Il server di prova è il server finto di script/ci/server_finto.py (lo stesso della regressione visiva): serve `fanta/web/` e
risponde alle `/api/...` con uno scenario registrato di ios/fotografie/ (nomi inventati). Niente server vero, niente rete,
nessun segreto. Ogni test che chiede `web` gira tre volte, una per fase: `prima` (prima della scadenza), `in-corso`, `finita`.

Si lanciano a parte, con l'ambiente di Playwright (tests/browser/LEGGIMI.md):
    <venv-playwright>/python -m pytest -m browser --confcutdir tests/browser tests/browser
Ogni test di questa cartella ha da solo il segno `browser`. Nella suite normale (senza `-m browser`) si saltano. Senza la
libreria Playwright o senza Chrome si saltano; con la variabile BROWSER_OBBLIGATORIO=1 (il job «browser» dei controlli)
invece falliscono: lì un test saltato sarebbe un verde finto.
"""
from __future__ import annotations

import http.client
import http.server
import importlib.util
import json
import os
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

CARTELLA = Path(__file__).resolve().parent
RADICE = CARTELLA.parents[1]
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

# Patti con ogni versione della web (tests/browser/LEGGIMI.md), senza selettori di una schermata:
# - il contenuto della schermata sta nell'area principale, `<main>` (o un elemento con role="main");
# - mentre una schermata carica, l'area principale (o il suo contenitore del caricamento) ha aria-busy="true" (la web lo
#   mette dal 12/11/2026, #615; si guardano ancora anche le classi `caricamento` e `scheletro`);
# - un errore mostrato all'utente ha role="alert" (la web di oggi usa anche la classe `errore`); un avviso normale ha
#   role="status". Gli avvisi con la classe `attenzione` non contano come errori (fino al 12/11/2026, #618, la schermata di
#   accesso li metteva in un role="alert").
AREA_PRINCIPALE = "main, [role=main]"
TESTO_PRINCIPALE = """(area) => { const m = document.querySelector(area);
  return m ? (m.innerText || '').trim() : ''; }"""
IN_CARICAMENTO = """(area) => { const m = document.querySelector(area);
  if (!m) return false;
  if (m.getAttribute('aria-busy') === 'true') return true;
  return [...m.querySelectorAll('[aria-busy=true], .caricamento, .scheletro')].some(e => e.getClientRects().length > 0); }"""
PRONTA = f"(area) => ({TESTO_PRINCIPALE})(area).length > 0 && !({IN_CARICAMENTO})(area)"
ERRORI_MOSTRATI = """(area) => { const m = document.querySelector(area);
  if (!m) return [];
  const visto = e => e.getClientRects().length > 0 && (e.innerText || '').trim();
  const avviso = e => e.matches('.attenzione')
    || (!!e.querySelector('.attenzione') && !e.matches('.errore') && !e.querySelector('.errore'));
  const trovati = [...m.querySelectorAll('[role=alert], .errore')].filter(e => visto(e) && !avviso(e));
  return trovati.filter(e => !trovati.some(a => a !== e && a.contains(e)))
    .map(e => e.innerText.trim().replace(/\\s+/g, ' ').slice(0, 200)); }"""
# Attesa: prima un segnale preciso (area principale con testo e senza caricamento, al massimo 10 s), poi la rete ferma (al
# massimo 2 s) e il DOM fermo per 300 ms (al massimo 3 s). Una richiesta che resta aperta costa così pochi secondi.
LIMITE_AREA_MS, LIMITE_RETE_MS = 10000, 2000
DOM_FERMO = """() => new Promise(fatto => {
  let ultimo = performance.now();
  const inizio = ultimo;
  const osservatore = new MutationObserver(() => { ultimo = performance.now(); });
  osservatore.observe(document, {subtree: true, childList: true, attributes: true, characterData: true});
  const giro = () => {
    const ora = performance.now();
    if (ora - ultimo >= 300 || ora - inizio >= 3000) { osservatore.disconnect(); fatto(); } else setTimeout(giro, 50);
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


@pytest.hookimpl(tryfirst=True)              # prima della scelta di `-m`: un test senza segno sarebbe escluso
def pytest_collection_modifyitems(config, items):
    """Ogni test di tests/browser/ ha il segno `browser` (anche se chi lo scrive se ne dimentica), e i test del browser
    girano solo se scelti con `-m browser`: la suite normale non apre Chrome."""
    for item in items:
        if CARTELLA in Path(str(item.path)).resolve().parents:
            item.add_marker(pytest.mark.browser)
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


def _server_finto():
    """script/ci/server_finto.py come modulo (script/ci non è un pacchetto)."""
    spec = importlib.util.spec_from_file_location("server_finto_per_browser", RADICE / "script" / "ci" / "server_finto.py")
    modulo = importlib.util.module_from_spec(spec)
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
    sf = _server_finto()
    scenario = scenario_completo(request.param, tmp_path_factory.mktemp(f"scenario-{request.param}"))
    host = sf.host_per(sf.porta_libera("127.0.0.1") + list(FASI).index(request.param))
    with sf.ServerFinto(WEB, scenario, sf.porta_libera(host), host=host) as s:
        yield ServerFase(request.param, s.indirizzo, s.adesso)


@dataclass
class Web:
    """Una scheda di Chrome sulla web di una fase. Raccoglie da sola gli errori della console (anche quelli del codice) e le
    richieste fallite (risposta 4xx o 5xx, o richiesta che non arriva): i test li leggono dopo `apri`.
    La scheda si apre alla prima richiesta di `pagina` (con `apre_scheda`): un test che vale per un'altra fase si salta
    leggendo solo `fase`, senza aprirla (issue #680: più di metà dei test)."""
    server: ServerFase
    apre_scheda: Callable[[Web], object] | None = None
    errori_console: list[str] = field(default_factory=list)
    richieste_fallite: list[str] = field(default_factory=list)
    richieste: list[str] = field(default_factory=list)          # le /api/... chieste dalla pagina (percorso e query), in ordine
    _pagina: object = field(default=None, repr=False)

    @property
    def pagina(self):
        """La pagina di Playwright; la prima volta apre la scheda."""
        if self._pagina is None and self.apre_scheda is not None:
            self._pagina = self.apre_scheda(self)
        return self._pagina

    @property
    def fase(self) -> str:
        return self.server.fase

    def risposta(self, rotta: str, corpo, stato: int = 200) -> None:
        """Prima di `apri` (o di un clic): da qui la rotta risponde con `corpo` (un oggetto JSON) e `stato`, al posto della
        risposta registrata. `rotta` si scrive come nello scenario: con la query («/api/scelta?giornata=9») vale per
        quell'indirizzo, senza («/api/oggi») per ogni query. Serve per un dato che lo scenario non ha o per una rotta che
        fallisce (`stato=500`). La richiesta non arriva al server finto: risponde il browser."""
        testo = json.dumps(corpo, ensure_ascii=False)

        def e_la_rotta(indirizzo: str) -> bool:
            parti = urlsplit(indirizzo)
            return rotta in (unquote(parti.path + ("?" + parti.query if parti.query else "")), unquote(parti.path))

        self.pagina.route(e_la_rotta, lambda r: r.fulfill(status=stato, content_type="application/json; charset=utf-8", body=testo))

    def registrata(self, rotta: str):
        """La risposta registrata di una rotta in questa fase, come oggetto: per cambiarne un pezzo e ridarla con `risposta`."""
        testo = json.loads((SCENARI / FASI[self.fase]).read_text(encoding="utf-8"))["risposte"][rotta]
        return json.loads(testo) if isinstance(testo, str) else testo

    def memoria(self, valori: dict[str, str]) -> None:
        """Prima di `apri`: valori già salvati nel browser (localStorage), come li ha lasciati una versione di prima della web.
        Si scrivono una volta sola, alla prima pagina della scheda: dopo resta ciò che scrive l'app."""
        scrivi = "".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(v)}); " for k, v in valori.items())
        self.pagina.add_init_script("try { if (!sessionStorage.getItem('memoria-di-prova')) { "
                                    "sessionStorage.setItem('memoria-di-prova', '1'); " + scrivi + "} } catch (e) {}")

    def apri(self, percorso: str = "/", larghezza: int = 390, tema: str = "chiaro") -> None:
        """Apre un indirizzo della web alla larghezza e nel tema dati e aspetta che la pagina sia ferma."""
        self.pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
        self.pagina.emulate_media(color_scheme=TEMI[tema], reduced_motion="reduce")
        self.pagina.goto(self.server.indirizzo + percorso, wait_until="load")
        self.aspetta()

    def aspetta(self) -> None:
        """Dopo l'apertura, un clic o un cambio: area principale con testo e senza caricamento, rete ferma, DOM fermo,
        animazioni portate alla fine. Un'attesa scaduta non ferma il test: lo dicono i controlli dopo (per esempio
        «ferma sul caricamento»); in quel caso non si aspetta anche la rete."""
        from playwright.sync_api import TimeoutError as AttesaScaduta
        try:
            self.pagina.wait_for_function(PRONTA, arg=AREA_PRINCIPALE, timeout=LIMITE_AREA_MS)
            pronta = True
        except AttesaScaduta:
            pronta = False
        if pronta:
            try:
                self.pagina.wait_for_load_state("networkidle", timeout=LIMITE_RETE_MS)
            except AttesaScaduta:            # una richiesta che resta aperta: il DOM fermo basta
                pass
        self.pagina.evaluate(DOM_FERMO)
        self.pagina.evaluate(FINISCI_ANIMAZIONI)

    def testo_principale(self) -> str:
        """Il testo dell'area principale (`<main>` o role="main"); vuoto se l'area non c'è."""
        return self.pagina.evaluate(TESTO_PRINCIPALE, AREA_PRINCIPALE)

    def in_caricamento(self) -> bool:
        """L'area principale sta ancora caricando: aria-busy="true" (o, nella web di oggi, le classi `caricamento` e
        `scheletro`) visibile."""
        return self.pagina.evaluate(IN_CARICAMENTO, AREA_PRINCIPALE)

    def errori_mostrati(self) -> list[str]:
        """I messaggi d'errore visibili nell'area principale: elementi con role="alert" (o, nella web di oggi, con la classe
        `errore`) che hanno del testo; non gli avvisi con la classe `attenzione`."""
        return self.pagina.evaluate(ERRORI_MOSTRATI, AREA_PRINCIPALE)

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
    scenario, in italiano, ora italiana, movimento ridotto, service worker bloccato. Si apre al primo uso di `web.pagina`."""
    contesti = []

    def apre_scheda(w: Web):
        ctx = chrome.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, locale="it-IT",
                                 timezone_id=FUSO, service_workers="block", reduced_motion="reduce")
        contesti.append(ctx)
        pagina = ctx.new_page()
        istante = pagina.evaluate("(s) => new Date(s).getTime()", server_fase.adesso)     # letto con il fuso italiano
        ctx.clock.set_fixed_time(istante / 1000)
        pagina.on("console", lambda m: m.type == "error" and w.errori_console.append(
            f"{m.text} ({_breve(m.location.get('url') or '')})"))
        pagina.on("pageerror", lambda e: w.errori_console.append(f"errore nel codice: {e}"))
        pagina.on("request", lambda r: urlsplit(r.url).path.startswith("/api/") and w.richieste.append(_breve(r.url)))
        pagina.on("requestfailed", lambda r: _richiesta_non_arrivata(w, r))
        pagina.on("response", lambda r: r.status >= 400 and w.richieste_fallite.append(
            f"{r.request.method} {_breve(r.url)}: risposta {r.status}"))
        return pagina

    try:
        yield Web(server_fase, apre_scheda)
    finally:
        for ctx in contesti:
            ctx.close()


# ---------------------------------------------------------------- l'app installata, con il service worker (#654)
PAGINA_502 = (b"<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n<center><h1>502 Bad Gateway</h1></center>\r\n"
              b"<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n")
NON_INOLTRATE = {"connection", "keep-alive", "transfer-encoding", "host", "proxy-connection", "upgrade", "content-length"}


class Proxy:
    """Fa la parte di nginx davanti al server finto, su 127.0.0.1 (senza https la web registra il service worker solo lì e su
    localhost). `modo`: "ok" inoltra; "502" risponde 502 Bad Gateway a tutto, come mentre il servizio dietro riparte;
    "spento" chiude la connessione senza rispondere, come senza rete. `lenti`: percorso -> secondi di ritardo (una rete debole
    sui file grossi). `risposte`: percorso -> oggetto JSON dato al posto del server finto quando il modo è "ok" (per esempio
    `/api/account/me` del server con gli account)."""

    def __init__(self, dietro: str, server_finto):
        parti = urlsplit(dietro)
        self.host_dietro, self.porta_dietro = parti.hostname, parti.port
        self.modo = "ok"
        self.lenti: dict[str, float] = {}
        self.risposte: dict[str, object] = {}
        self._sf = server_finto
        self._server = None

    @property
    def indirizzo(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self):
        proxy = self

        class Gestore(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *argomenti):
                pass

            def _inoltra(self) -> None:
                lunghezza = int(self.headers.get("Content-Length") or 0)
                corpo = self.rfile.read(lunghezza) if lunghezza else None
                if proxy.modo == "spento":
                    self.close_connection = True
                    return
                if proxy.modo == "502":
                    self.send_response(502)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(PAGINA_502)))
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(PAGINA_502)
                    return
                percorso = self.path.split("?", 1)[0]
                if percorso in proxy.risposte:
                    dati = json.dumps(proxy.risposte[percorso]).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(dati)))
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(dati)
                    return
                ritardo = proxy.lenti.get(percorso)
                if ritardo:
                    time.sleep(ritardo)
                dietro = http.client.HTTPConnection(proxy.host_dietro, proxy.porta_dietro, timeout=30)
                try:
                    dietro.request(self.command, self.path, body=corpo,
                                   headers={k: v for k, v in self.headers.items() if k.lower() not in NON_INOLTRATE})
                    risposta = dietro.getresponse()
                    dati = risposta.read()
                finally:
                    dietro.close()
                self.send_response(risposta.status)
                for k, v in risposta.getheaders():
                    if k.lower() not in NON_INOLTRATE:
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(dati)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(dati)

            do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = _inoltra

        self._server = self._sf._ServerSenzaNome(("127.0.0.1", 0), Gestore)
        threading.Thread(target=self._server.serve_forever, name="proxy-finto", daemon=True).start()
        return self

    def __exit__(self, *errore):
        self._server.shutdown()
        self._server.server_close()
        return False


@dataclass
class Installata:
    """La web come app installata: Chrome con il service worker acceso, davanti il proxy (`proxy`), dietro il server finto della
    fase «prima» che serve una copia di fanta/web (`web`), da cambiare per un rilascio finto. `errori`: errori del codice."""
    contesto: object
    proxy: Proxy
    web: Path
    errori: list[str] = field(default_factory=list)

    def scheda(self, percorso: str = "/"):
        """Una scheda nuova sull'indirizzo, come riaprire l'app dalla schermata Home; aspetta il caricamento della pagina."""
        pagina = self.contesto.new_page()
        pagina.on("pageerror", lambda e: self.errori.append(f"{pagina.url}: {e}"))
        pagina.goto(self.proxy.indirizzo + percorso, wait_until="load")
        return pagina

    def aspetta(self, pagina) -> None:
        """Come `Web.aspetta`, senza la rete ferma: area principale con del testo e senza caricamento (al massimo 10 s), poi
        DOM fermo. Un'attesa scaduta non ferma il test: lo dicono i controlli dopo."""
        from playwright.sync_api import TimeoutError as AttesaScaduta
        try:
            pagina.wait_for_function(PRONTA, arg=AREA_PRINCIPALE, timeout=LIMITE_AREA_MS)
        except AttesaScaduta:
            pass
        pagina.evaluate(DOM_FERMO)

    def installa(self) -> None:
        """Prima apertura con la rete buona: il service worker si installa (salva la scocca) e prende la pagina."""
        pagina = self.scheda("/")
        pagina.wait_for_function("() => !!navigator.serviceWorker.controller", timeout=20000)
        pagina.close()


@pytest.fixture
def installata(chrome, tmp_path):
    """L'app installata (`Installata`), una per test, con l'orologio fermo su «adesso» della fase «prima»."""
    sf = _server_finto()
    web = tmp_path / "web"
    shutil.copytree(WEB, web)
    scenario = scenario_completo("prima", tmp_path)
    with sf.ServerFinto(web, scenario, 0) as finto, Proxy(finto.indirizzo, sf) as proxy:
        ctx = chrome.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, locale="it-IT",
                                 timezone_id=FUSO, service_workers="allow", reduced_motion="reduce")
        try:
            vuota = ctx.new_page()
            ctx.clock.set_fixed_time(vuota.evaluate("(s) => new Date(s).getTime()", finto.adesso) / 1000)
            vuota.close()
            yield Installata(ctx, proxy, web)
        finally:
            ctx.close()
