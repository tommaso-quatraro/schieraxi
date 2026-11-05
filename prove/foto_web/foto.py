r"""Foto e axe della web app, senza finestra: per vedere le schermate prima e dopo una modifica della grafica.

Uso (dalla radice del repository; il Python è quello di un venv con Playwright, vedi LEGGIMI.md):
    <venv-playwright>\Scripts\python.exe prove\foto_web\foto.py [indirizzo] <cartella>
        [--scene oggi,formazione] [--larghezze 390,768,1024,1440] [--temi chiaro,scuro] [--lingua it|en]

Senza indirizzo avvia da solo un server di prova: copia di `fanta/` di questa cartella, lega d'esempio, copia
dell'archivio dei dati di calcio (`dati/fanta.sqlite`, mai l'originale), su un indirizzo di loopback suo e una porta libera.
Lo ferma alla fine, anche se qualcosa va storto. Con un indirizzo usa quel server (già acceso da chi lancia).

Per ogni scena, larghezza e tema scrive nella cartella (che deve stare FUORI dal repository):
- `<scena>-<larghezza>-<tema>.png`, la pagina intera;
- `axe-<scena>-<larghezza>-<tema>.json`, le violazioni di axe (regole WCAG 2.0, 2.1 e 2.2, livelli A e AA);
- una riga in `riepilogo.txt`: `<scena> <larghezza> <tema> gravi=<n> scorrimento-di-lato=<sì|no> errori-console=<n>`
  (gravi = violazioni `critical` e `serious`). Esce con 1 se una scena ha violazioni gravi, con 2 se una scena non si apre.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import ExitStack
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
AXE = RADICE / "tests/strumenti/axe/axe.min.js"
LARGHEZZE = [390, 768, 1024, 1440]
TEMI = {"chiaro": "light", "scuro": "dark"}
REGOLE_AXE = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]

# Ogni scena è una lista di passi (JavaScript lanciato nella pagina); dopo ogni passo si aspetta che il caricamento finisca.
# I nomi delle funzioni sono quelli di fanta/web/app.js: se cambiano, la scena dà errore nel riepilogo invece di una foto sbagliata.
PRIMO_GIOCATORE = "Number(document.querySelector('#contenuto [data-giocatore]').dataset.giocatore)"
DUE_GIOCATORI = ("[...new Set([...document.querySelectorAll('#contenuto [data-giocatore]')]"
                 ".map(e => Number(e.dataset.giocatore)))].slice(0, 2)")
SCENE: dict[str, list[str]] = {
    "oggi": ["vai('oggi')"],
    "formazione": ["vai('formazione')"],
    "squadra": ["vai('squadra')"],
    "elenco": ["vaiMercato('giocatori')"],                          # Squadra > Elenco dei giocatori
    "rosa": ["vistaRosa()"],
    "scheda": ["vai('formazione')", f"apriGiocatore({PRIMO_GIOCATORE})"],          # scheda del primo titolare
    "confronto": ["vai('formazione')", f"apriConfronto(...{DUE_GIOCATORI})"],      # i primi due titolari a confronto
    "altro": ["vai('altro')"],
    "diario": ["apriDiario()"],
    "regole": ["vistaRegole()"],
    "scambi": ["vai('scambi')"],
    "impostazioni": ["vai('impostazioni')"],
}
PRONTA = """() => typeof vai === 'function' && !!document.querySelector('#contenuto')
  && ![...document.querySelectorAll('#contenuto .caricamento, #foglio:not([hidden]) .caricamento')].some(e => e.getClientRects().length)
  && (document.querySelector('#contenuto').children.length > 0 || !!document.querySelector('#foglio:not([hidden])'))"""
FOGLIO_APERTO = "() => !!document.querySelector('#foglio:not([hidden]) .foglio-corpo')"
MISURA_FOGLIO = "() => { const c = document.querySelector('#foglio .foglio-corpo'); return [c.scrollHeight, c.clientHeight]; }"
PEZZI_FOGLIO = 8                 # tetto alle foto di un foglio lungo
SOVRAPPOSIZIONE = 80             # px ripetuti tra un pezzo e il successivo: si vede dove si attacca
SCORRE_DI_LATO = "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
LANCIA_AXE = """(regole) => axe.run(document, {runOnly: {type: 'tag', values: regole}, resultTypes: ['violations']})
  .then(r => r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, n: v.nodes.length,
    nodi: v.nodes.slice(0, 5).map(n => ({target: n.target.join(' '), sommario: n.failureSummary}))})))"""


# =========================== parti senza browser ===========================
def fuori_dal_repository(cartella) -> Path:
    """La cartella delle foto, risolta. Esce se sta dentro il repository: le pagine mostrano nomi di calciatori veri e il
    repository è pubblico, quindi le foto restano fuori (scratchpad o cartella temporanea)."""
    c = Path(cartella).resolve()
    if c == RADICE or c.is_relative_to(RADICE):
        sys.exit(f"La cartella delle foto deve stare fuori dal repository ({RADICE}): {c}")
    return c


def _elenco(testo: str, validi=None, numeri=False) -> list:
    voci = [v.strip() for v in testo.split(",") if v.strip()]
    if numeri:
        try:
            return [int(v) for v in voci]
        except ValueError:
            raise argparse.ArgumentTypeError(f"servono numeri separati da virgole: {testo}") from None
    sbagliate = [v for v in voci if validi is not None and v not in validi]
    if sbagliate or not voci:
        raise argparse.ArgumentTypeError(f"valori sconosciuti: {', '.join(sbagliate) or testo} (validi: {', '.join(validi or [])})")
    return voci


def leggi_argomenti(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="foto.py", description="Foto e axe della web app senza finestra. Scrive le foto, i risultati di axe e riepilogo.txt.",
        epilog="riepilogo.txt: una riga per foto, «<scena> <larghezza> <tema> gravi=<n> scorrimento-di-lato=<sì|no> "
               "errori-console=<n>». Esce con 1 se ci sono violazioni gravi (critical o serious).")
    p.add_argument("posizionali", nargs="+", metavar="[indirizzo] cartella",
                   help="indirizzo del server (facoltativo: senza, ne avvia uno di prova) e cartella delle foto, fuori dal repository")
    p.add_argument("--scene", type=lambda s: _elenco(s, list(SCENE)), default=list(SCENE), help=f"di norma tutte: {','.join(SCENE)}")
    p.add_argument("--larghezze", type=lambda s: _elenco(s, numeri=True), default=list(LARGHEZZE), help="di norma 390,768,1024,1440")
    p.add_argument("--temi", type=lambda s: _elenco(s, list(TEMI)), default=list(TEMI), help="di norma chiaro,scuro")
    p.add_argument("--lingua", choices=["it", "en"], default="it")
    p.add_argument("--dati", default=None, help="cartella con fanta.sqlite (di norma dati/ del repository o della cartella principale)")
    p.add_argument("--python-server", default=None, help="Python con i pacchetti del server (di norma il .venv del repository)")
    a = p.parse_args(argv)
    if len(a.posizionali) > 2:
        p.error("al massimo due argomenti: indirizzo e cartella")
    a.indirizzo, a.cartella = (None, a.posizionali[0]) if len(a.posizionali) == 1 else a.posizionali
    return a


def gravi(violazioni: list[dict]) -> int:
    return sum(1 for v in violazioni if v.get("impact") in ("critical", "serious"))


def posizioni_foglio(altezza_contenuto: int, altezza_visibile: int) -> list[int]:
    """Dove far scorrere il foglio aperto (scheda, confronto, diario) per fotografarlo tutto, a pezzi che si sovrappongono."""
    fondo = max(0, altezza_contenuto - altezza_visibile)
    passo = max(1, altezza_visibile - SOVRAPPOSIZIONE)
    pos = list(range(0, fondo, passo))[:PEZZI_FOGLIO - 1] + [fondo]
    return sorted(set(pos))


def riga_riepilogo(scena: str, larghezza: int, tema: str, n_gravi: int, scorre: bool, errori_console: int) -> str:
    return f"{scena} {larghezza} {tema} gravi={n_gravi} scorrimento-di-lato={'sì' if scorre else 'no'} errori-console={errori_console}"


def _principale() -> Path | None:
    """La cartella principale del repository (quella con .venv e dati/), anche lanciando da una worktree."""
    try:
        r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=RADICE,
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(r.stdout.strip()).parent if r.returncode == 0 and r.stdout.strip() else None


def _cerca(relativo: str) -> Path | None:
    for base in (RADICE, _principale()):
        if base and (base / relativo).exists():
            return base / relativo
    return None


def python_server(scelto: str | None) -> str:
    if scelto:
        return scelto
    trovato = _cerca(".venv/Scripts/python.exe") or _cerca(".venv/bin/python")
    return str(trovato) if trovato else sys.executable


def cartella_dati(scelta: str | None) -> Path | None:
    if scelta:
        return Path(scelta)
    trovato = _cerca("dati/fanta.sqlite")
    return trovato.parent if trovato else None


def prepara_copia(dove: Path, dati: Path | None) -> Path:
    """Cartella di lavoro del server di prova: `fanta/` di questa cartella, la lega d'esempio come `lega/` e, se c'è, una copia
    dell'archivio dei dati di calcio. Nessun file personale (diario, scelte, account): gli originali non si toccano."""
    dove.mkdir(parents=True, exist_ok=True)
    shutil.copytree(RADICE / "fanta", dove / "fanta", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(RADICE / "lega" / "esempio", dove / "lega")
    (dove / "dati").mkdir()
    if dati and (dati / "fanta.sqlite").is_file():
        sorgente = sqlite3.connect(f"{(dati / 'fanta.sqlite').resolve().as_uri()}?mode=ro", uri=True, timeout=30)
        destinazione = sqlite3.connect(dove / "dati" / "fanta.sqlite")
        try:
            sorgente.backup(destinazione)          # copia coerente anche se l'archivio è aperto (giornale WAL)
        finally:
            destinazione.close()
            sorgente.close()
    return dove


def ambiente_server(copia: Path) -> dict:
    """Ambiente del server di prova: nessuna variabile FANTA_ di chi lancia (fonti, account, lega vera), niente lavori di sfondo."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("FANTA_")}
    env.update({"FANTA_LEGA": str(copia / "lega"), "FANTA_PIANIFICATORE": "0", "FANTA_COPIA_SCADENZA": "0",
                "FANTA_REGISTRO_GIORNATE": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def host_per(porta: int) -> str:
    """Un indirizzo di loopback diverso da 127.0.0.1: i cookie valgono per indirizzo, così un altro collaudo non fa cadere questo."""
    return f"127.0.0.{20 + porta % 200}"


def porta_libera(host: str) -> int:
    with socket.socket() as s:
        s.bind((host, 0))
        return s.getsockname()[1]


class ServerDiProva:
    """Processo del server: parte, aspetta che risponda (al massimo `attesa` secondi), si ferma all'uscita dal `with`
    anche dopo un errore. Ferma solo il SUO processo."""

    def __init__(self, comando: list[str], base: str, cwd: Path, env: dict | None, log: Path, attesa: float = 30):
        self.comando, self.base, self.cwd, self.env, self.log, self.attesa = comando, base, cwd, env, Path(log), attesa
        self.processo: subprocess.Popen | None = None
        self._file_log = None

    def __enter__(self):
        self._file_log = open(self.log, "w", encoding="utf-8")
        opzioni = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.processo = subprocess.Popen(self.comando, cwd=self.cwd, env=self.env, stdout=self._file_log,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **opzioni)
        fine = time.monotonic() + self.attesa
        while time.monotonic() < fine:
            if self.processo.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{self.base}/api/salute", timeout=2):
                    return self
            except urllib.error.HTTPError:
                return self                          # risponde (503 = senza archivio dei dati): è acceso
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        self.ferma()
        sys.exit(f"Il server di prova non risponde dopo {self.attesa:.0f} s: guarda {self.log}")

    def ferma(self) -> None:
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(10)
            except subprocess.TimeoutExpired:
                self.processo.kill()
                self.processo.wait(10)
        if self._file_log and not self._file_log.closed:
            self._file_log.close()

    def __exit__(self, *errore):
        self.ferma()
        return False


# =========================== foto e axe ===========================
def _aspetta_pronta(pagina, limite_ms: int = 20000) -> None:
    pagina.wait_for_function(PRONTA, timeout=limite_ms)
    try:
        pagina.wait_for_load_state("networkidle", timeout=5000)
    except Exception:                                # una richiesta lunga (diretta, immagini): si fotografa lo stesso
        pass
    pagina.wait_for_function(PRONTA, timeout=limite_ms)


def _foto(pagina, uscita: Path, nome: str) -> None:
    """La pagina intera; con un foglio aperto il foglio a pezzi (`<nome>.png`, `<nome>-2.png`, ...), perché scorre da sé."""
    if not pagina.evaluate(FOGLIO_APERTO):
        pagina.screenshot(path=str(uscita / f"{nome}.png"), full_page=True, animations="disabled")
        return
    for i, y in enumerate(posizioni_foglio(*pagina.evaluate(MISURA_FOGLIO)), start=1):
        pagina.evaluate("(y) => { document.querySelector('#foglio .foglio-corpo').scrollTop = y; }", y)
        pagina.wait_for_timeout(150)                  # il tempo di disegnare le immagini caricate in ritardo
        pagina.screenshot(path=str(uscita / (f"{nome}.png" if i == 1 else f"{nome}-{i}.png")), animations="disabled")
    pagina.evaluate("() => { document.querySelector('#foglio .foglio-corpo').scrollTop = 0; }")


def fotografa(base: str, uscita: Path, scene: list[str], larghezze: list[int], temi: list[str], lingua: str) -> tuple[list[str], int]:
    """Le foto e axe di ogni scena. Torna le righe del riepilogo e quante scene non si sono aperte."""
    from playwright.sync_api import sync_playwright          # solo qui: i test dello strumento girano senza Playwright

    axe = AXE.read_text(encoding="utf-8")
    righe, fallite = [], 0
    with tempfile.TemporaryDirectory(prefix="foto-web-profilo-", ignore_cleanup_errors=True) as profilo, sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profilo, channel="chrome", headless=True,
                                                   viewport={"width": larghezze[0], "height": 844}, locale="it-IT")
        try:
            ctx.add_init_script(f"try {{ localStorage.setItem('lingua', '{lingua}'); localStorage.removeItem('tema'); }} catch (e) {{}}")
            pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
            errori: list[str] = []
            pagina.on("console", lambda m: m.type == "error" and errori.append(m.text))
            pagina.on("pageerror", lambda e: errori.append(str(e)))
            for tema in temi:
                if tema == "chiaro":                          # il tema «auto» dell'app segue questo
                    pagina.emulate_media(color_scheme="light")
                else:
                    pagina.emulate_media(color_scheme="dark")
                for larghezza in larghezze:
                    pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
                    for scena in scene:
                        nome = f"{scena}-{larghezza}-{tema}"
                        errori.clear()
                        try:
                            pagina.goto(base + "/", wait_until="load")
                            _aspetta_pronta(pagina)
                            for passo in SCENE[scena]:
                                pagina.evaluate(f"() => {{ {passo}; }}")
                                _aspetta_pronta(pagina)
                            _foto(pagina, uscita, nome)
                            scorre = pagina.evaluate(SCORRE_DI_LATO)
                            pagina.evaluate(axe)          # come testo: un tag <script> lo bloccherebbe la CSP dell'app
                            violazioni = pagina.evaluate(LANCIA_AXE, REGOLE_AXE)
                        except Exception as e:          # una scena rotta non ferma le altre: si scrive nel riepilogo
                            fallite += 1
                            riga = f"{scena} {larghezza} {tema} errore={type(e).__name__}: {str(e).splitlines()[0][:160]}"
                        else:
                            (uscita / f"axe-{nome}.json").write_text(json.dumps(violazioni, ensure_ascii=False, indent=1), encoding="utf-8")
                            riga = riga_riepilogo(scena, larghezza, tema, gravi(violazioni), scorre, len(errori))
                        if errori:
                            (uscita / f"console-{nome}.txt").write_text("\n".join(errori), encoding="utf-8")
                        print(riga, flush=True)
                        righe.append(riga)
        finally:
            ctx.close()
    return righe, fallite


def main(argv=None) -> int:
    a = leggi_argomenti(argv)
    uscita = fuori_dal_repository(a.cartella)
    uscita.mkdir(parents=True, exist_ok=True)
    with ExitStack() as pila:
        base = a.indirizzo.rstrip("/") if a.indirizzo else None
        if not base:
            lavoro = Path(pila.enter_context(tempfile.TemporaryDirectory(prefix="foto-web-server-", ignore_cleanup_errors=True)))
            dati = cartella_dati(a.dati)
            if not dati:
                print("Nessun archivio dei dati (dati/fanta.sqlite): le schermate saranno vuote.", file=sys.stderr)
            copia = prepara_copia(lavoro / "app", dati)
            porta = porta_libera("127.0.0.1")
            host = host_per(porta)
            porta = porta_libera(host)
            comando = [python_server(a.python_server), "-m", "fanta", "server", "--host", host, "--porta", str(porta)]
            server = pila.enter_context(ServerDiProva(comando, f"http://{host}:{porta}", cwd=copia,
                                                      env=ambiente_server(copia), log=uscita / "server.log"))
            print(f"Server di prova su http://{host}:{porta} (PID {server.processo.pid})", flush=True)
            base = server.base
        righe, fallite = fotografa(base, uscita, a.scene, a.larghezze, a.temi, a.lingua)
    (uscita / "riepilogo.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")
    n_gravi = sum(1 for r in righe if "gravi=" in r and "gravi=0 " not in r)
    print(f"Foto e riepilogo in {uscita}: {len(righe)} foto, {n_gravi} con violazioni gravi, {fallite} scene non aperte.")
    return 2 if fallite else 1 if n_gravi else 0


if __name__ == "__main__":
    for flusso in (sys.stdout, sys.stderr):
        flusso.reconfigure(encoding="utf-8")          # «» e lettere accentate anche nella console di Windows
    sys.exit(main())
