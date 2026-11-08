r"""Regressione visiva della web: le scene della PR confrontate con quelle di main, scattate nella stessa corsa (issue #503).

Uso (workflow «Aspetto della web», .github/workflows/aspetto-web.yml; in locale con un venv che ha Playwright e Pillow,
`.github/playwright-requisiti.txt`):
    python script/ci/aspetto_web.py --base <copia di main> --pr <copia della PR> --uscita <cartella>
        [--scenario ios/fotografie/vero-prima.json] [--scene oggi,rosa] [--larghezze 390,1440] [--temi chiaro,scuro]
        [--corpo <file con la descrizione della PR>]

Per ognuna delle due copie un server finto (solo libreria standard) serve `fanta/web/` e risponde alle `/api/...` con le risposte
registrate dello scenario (nomi inventati, le stesse delle foto dell'iPhone). Chrome di sistema senza finestra fotografa le scene
(11 scene x 2 larghezze x 2 temi) con l'orologio fermo sul momento della registrazione; poi si confrontano le foto.
Una scena è diversa se più dello 0,1% dei pixel cambia di oltre 16/255 su un canale, o se cambia la misura della pagina. Una
scena diversa si fotografa di nuovo su main: se cambia da sola è instabile (non è colpa della PR) e va in INSTABILI col motivo.

La PR dichiara le scene che cambiano con la riga `Aspetto: oggi, formazione` (o `Aspetto: nessuno`, o `Aspetto: tutte`);
la descrizione arriva dal file di --corpo o dalla variabile d'ambiente CORPO, mai dentro un comando.
Scrive in <uscita>: `base/`, `pr/` (foto), `diverse/` (per ogni foto diversa: base, PR e differenza in rosso), `riassunto.md`
(anche nel riassunto della corsa, se c'è GITHUB_STEP_SUMMARY).
Esce con 0 se non ci sono differenze non dichiarate, 1 se ce ne sono, 2 se una scena non si apre o è instabile, 3 se la
preparazione non riesce (copie, scenario, Playwright o Chrome mancanti). Per ora il workflow lo usa solo come avviso.
"""
from __future__ import annotations

import argparse
import http.server
import json
import mimetypes
import os
import re
import shutil
import socket
import sys
import threading
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

LARGHEZZE = (390, 1440)
TEMI = ("chiaro", "scuro")
TOLLERANZA = 16          # su 255, per canale: sotto questa differenza un pixel è «uguale» (sfumature dei caratteri)
SOGLIA = 0.001           # quota di pixel diversi oltre la quale la scena è diversa (0,1%)
ROSSO = (220, 0, 0)
FUSO = "Europe/Rome"     # il momento dello scenario («adesso») è l'ora italiana, come per il server
PEZZI_FOGLIO = 8         # tetto ai pezzi di un foglio che scorre (scheda, confronto, diario)
SOVRAPPOSIZIONE = 80     # px ripetuti fra un pezzo del foglio e il successivo
MAX_CORPO_RICHIESTA = 1_000_000


@dataclass(frozen=True)
class Scena:
    """Un indirizzo della web e, dopo, i clic sugli elementi indicati (selettori CSS, il primo che c'è). Mai funzioni
    interne di app.js: con la web divisa in moduli non sono più raggiungibili per nome, indirizzi ed elementi sì."""
    indirizzo: str
    clic: tuple[str, ...] = ()


SCENE: dict[str, Scena] = {
    "oggi": Scena("/?vista=oggi"),
    "formazione": Scena("/?vista=formazione"),
    "squadra": Scena("/?vista=squadra"),
    "rosa": Scena("/?vista=squadra&rosa="),                                        # la rosa della mia squadra
    "scheda": Scena("/?vista=formazione", ("#contenuto [data-giocatore]",)),        # scheda del primo titolare
    "confronto": Scena("/?vista=formazione", ("#contenuto [data-confronta]", "#foglio [data-scegli-confronto]")),
    "altro": Scena("/?vista=altro"),
    "diario": Scena("/?vista=altro&voce=diario", ("#apri-diario",)),               # il foglio del diario, non solo la voce
    "regole": Scena("/?vista=altro&voce=regole"),
    "scambi": Scena("/?vista=scambi"),
    "impostazioni": Scena("/?vista=impostazioni"),
}
# Scene che cambiano da sole (stessa pagina, foto diverse): scattate e mostrate, ma non contano. Nome -> motivo, finché la
# causa non si toglie.
INSTABILI: dict[str, str] = {}

# Tipi dei file della web scritti qui: su Windows `mimetypes` legge il registro, che può dire text/plain per .js.
TIPI = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".json": "application/json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml",
        ".png": "image/png", ".woff2": "font/woff2", ".ico": "image/x-icon"}

PRONTA = """() => {
  const c = document.querySelector('#contenuto');
  if (!c) return false;
  const foglio = document.querySelector('#foglio:not([hidden])');
  if (!c.children.length && !foglio) return false;
  return ![...document.querySelectorAll('#contenuto .caricamento, #foglio:not([hidden]) .caricamento')]
    .some(e => e.getClientRects().length);
}"""
FERMA = """async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].filter(i => !i.complete)
    .map(i => new Promise(r => { i.addEventListener('load', r); i.addEventListener('error', r); setTimeout(r, 3000); })));
}"""
FOGLIO_CHE_SCORRE = """() => { const c = document.querySelector('#foglio:not([hidden]) .foglio-corpo');
  return c && c.scrollHeight > c.clientHeight + 1 ? [c.scrollHeight, c.clientHeight] : null; }"""
STATO_INIZIALE = "try { localStorage.clear(); sessionStorage.clear(); localStorage.setItem('lingua', 'it'); } catch (e) {}"


# =========================== confronto delle immagini (Pillow) ===========================
@dataclass(frozen=True)
class Differenza:
    pixel: int
    quota: float
    misura_diversa: bool

    @property
    def diversa(self) -> bool:
        return self.quota > SOGLIA or self.misura_diversa


def _rgb(percorso):
    from PIL import Image                     # solo qui: il server finto e la riga «Aspetto:» non ne hanno bisogno
    with Image.open(percorso) as img:
        return img.convert("RGB")


def _maschera(a, b, tolleranza: int):
    """Immagine in scala di grigi: 255 dove almeno un canale cambia di più di `tolleranza`, 0 altrove (stessa misura)."""
    from PIL import ImageChops
    r, g, b_ = ImageChops.difference(a, b).split()
    massimo = ImageChops.lighter(ImageChops.lighter(r, g), b_)
    return massimo.point(lambda v: 255 if v > tolleranza else 0)


def confronta(a: Path, b: Path, tolleranza: int = TOLLERANZA) -> Differenza:
    """Quanti pixel cambiano fra le due foto (sulla parte in comune) e se cambia la misura. La quota è sull'area più grande."""
    ia, ib = _rgb(a), _rgb(b)
    w, h = min(ia.width, ib.width), min(ia.height, ib.height)
    pixel = _maschera(ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h)), tolleranza).histogram()[255]
    area = max(ia.width * ia.height, ib.width * ib.height, 1)
    return Differenza(pixel, pixel / area, ia.size != ib.size)


def immagine_differenza(a: Path, b: Path, uscita: Path, tolleranza: int = TOLLERANZA) -> Path:
    """La foto di main sbiadita, con in rosso i pixel cambiati e la parte che c'è in una foto sola."""
    from PIL import Image
    ia, ib = _rgb(a), _rgb(b)
    misura = (max(ia.width, ib.width), max(ia.height, ib.height))
    pa, pb = Image.new("RGB", misura, (255, 255, 255)), Image.new("RGB", misura, (255, 255, 255))
    pa.paste(ia), pb.paste(ib)
    maschera = _maschera(pa, pb, tolleranza)
    fuori = Image.new("L", misura, 255)                         # la parte fuori da una delle due foto conta come cambiata
    fuori.paste(0, (0, 0, min(ia.width, ib.width), min(ia.height, ib.height)))
    maschera.paste(255, mask=fuori)
    fondo = Image.blend(pa.convert("L").convert("RGB"), Image.new("RGB", misura, (255, 255, 255)), 0.6)
    fondo.paste(Image.new("RGB", misura, ROSSO), mask=maschera)
    Path(uscita).parent.mkdir(parents=True, exist_ok=True)
    fondo.save(uscita)
    return Path(uscita)


def pezzi(cartella: Path, nome: str) -> list[str]:
    """I file di una foto: `<nome>.png` e, per un foglio che scorre, `<nome>-2.png`, `<nome>-3.png`, ..."""
    trovati = [f"{nome}.png"] if (cartella / f"{nome}.png").is_file() else []
    i = 2
    while (cartella / f"{nome}-{i}.png").is_file():
        trovati.append(f"{nome}-{i}.png")
        i += 1
    return trovati


def confronta_scatti(base: Path, pr: Path, nomi: list[str]) -> dict[str, Differenza]:
    """Per ogni foto (`<scena>-<larghezza>-<tema>`) la differenza peggiore fra i suoi pezzi; un pezzo in più o in meno è una
    misura diversa (il foglio è più lungo o più corto)."""
    esiti = {}
    for nome in nomi:
        pa, pb = pezzi(base, nome), pezzi(pr, nome)
        misura = pa != pb or not pa
        pixel, quota = 0, 0.0
        for f in sorted(set(pa) & set(pb)):
            d = confronta(base / f, pr / f)
            misura = misura or d.misura_diversa
            if d.quota > quota:
                pixel, quota = d.pixel, d.quota
        esiti[nome] = Differenza(pixel, quota, misura)
    return esiti


# =========================== descrizione della PR ed esito ===========================
def aspetto_dichiarato(corpo: str | None) -> set[str] | None:
    """Le scene della riga «Aspetto: oggi, formazione» fuori dai commenti HTML (quelli del modello di PR). «nessuno» = nessuna,
    «tutte» = tutte; senza riga (o con il solo commento del modello) None."""
    testo = re.sub(r"<!--.*?-->", "", corpo or "", flags=re.S)
    m = re.search(r"^[ \t]*[*_]*aspetto[*_]*[ \t]*:[ \t]*[*_]*(.*?)[ \t\r]*$", testo, re.I | re.M)
    if not m:
        return None
    voci = {v.strip("`*_.").lower() for v in re.split(r"[,\s]+", m.group(1)) if v.strip("`*_.")}
    if not voci:
        return None
    if "tutte" in voci:
        return set(SCENE)
    return voci - {"nessuno", "nessuna"}


def esito(diverse: set[str], dichiarate: set[str] | None, problemi: set[str]) -> int:
    if problemi:
        return 2
    return 1 if set(diverse) - (dichiarate or set()) else 0


def riassunto(diverse: dict[str, list[str]], dichiarate: set[str] | None, problemi: dict[str, str], mancanti: list[str],
              instabili: dict[str, list[str]]) -> str:
    """Il testo per il riassunto della corsa (Markdown): cosa è cambiato, cosa non è dichiarato e come si dichiara."""
    righe = ["## Aspetto della web (solo avviso)", ""]
    non_dichiarate = sorted(set(diverse) - (dichiarate or set()))
    if not diverse and not problemi:
        righe.append("Nessuna scena diversa da main.")
    for nome in sorted(diverse):
        stato = "dichiarata" if nome not in non_dichiarate else "**non dichiarata**"
        righe.append(f"- `{nome}`: diversa da main, {stato} ({', '.join(diverse[nome])})")
    if non_dichiarate:
        righe += ["", "Se il cambiamento è voluto, scrivi nella descrizione della PR la riga "
                  f"`Aspetto: {', '.join(non_dichiarate)}` (o aggiungi le scene a quella che c'è). Se non è voluto, è un difetto "
                  "da correggere. Le immagini (main, PR e differenza in rosso) sono nell'artifact «aspetto-web»."]
    sconosciute = sorted((dichiarate or set()) - set(SCENE))
    if sconosciute:
        righe += ["", f"Scene dichiarate che non esistono: {', '.join(sconosciute)} (scene: {', '.join(SCENE)})."]
    for nome, motivo in sorted(problemi.items()):
        righe.append(f"- `{nome}`: {motivo}")
    if instabili:
        righe += ["", "Scene che cambiano da sole anche su main (non contano): "
                  + ", ".join(f"`{n}` ({', '.join(v)})" for n, v in sorted(instabili.items()))
                  + ". Se capita ancora, vanno in INSTABILI di script/ci/aspetto_web.py con il motivo."]
    if mancanti:
        righe += ["", "Rotte senza risposta registrata (la pagina le mostra vuote o con l'errore, uguale per main e PR): "
                  + ", ".join(f"`{m}`" for m in mancanti[:30]) + (" e altre" if len(mancanti) > 30 else "") + "."]
    return "\n".join(righe) + "\n"


# =========================== server finto ===========================
def leggi_scenario(percorso: Path) -> dict:
    """Lo scenario registrato (ios/fotografie/vero-*.json): `adesso` e `risposte` (indirizzo -> testo JSON)."""
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    risposte = dati.get("risposte") if isinstance(dati, dict) else None
    if not isinstance(risposte, dict) or not risposte or not all(isinstance(k, str) for k in risposte):
        raise ValueError(f"scenario senza risposte: {percorso}")
    if not isinstance(dati.get("adesso"), str) or not dati["adesso"]:
        raise ValueError(f"scenario senza «adesso»: {percorso}")
    return dati


class ServerFinto:
    """Serve i file di `cartella_web` (un percorso che esce dalla cartella dà 404) e risponde alle `/api/...` con le risposte
    dello scenario: prima l'indirizzo con la query, poi senza; altrimenti 404 {"detail": "rotta non registrata"} e l'indirizzo
    va in `mancanti`. Ogni metodo ha la stessa risposta: niente si scrive. Si ferma all'uscita dal `with`."""

    def __init__(self, cartella_web: Path, scenario: Path, porta: int, host: str = "127.0.0.1"):
        self.radice = Path(cartella_web).resolve()
        if not (self.radice / "index.html").is_file():
            raise FileNotFoundError(f"manca index.html in {self.radice}")
        dati = leggi_scenario(scenario)
        self.adesso = dati["adesso"]
        self.risposte = {urllib.parse.unquote(k): v if isinstance(v, str) else json.dumps(v)
                         for k, v in dati["risposte"].items()}
        self.host, self.porta = host, porta
        self._mancanti: set[str] = set()
        self._blocco = threading.Lock()
        self._server: http.server.ThreadingHTTPServer | None = None
        self._filo: threading.Thread | None = None

    @property
    def indirizzo(self) -> str:
        return f"http://{self.host}:{self.porta}"

    @property
    def mancanti(self) -> list[str]:
        with self._blocco:
            return sorted(self._mancanti)

    def risposta_api(self, percorso: str, query: str) -> str | None:
        completo = percorso + ("?" + query if query else "")
        for chiave in (urllib.parse.unquote(completo), urllib.parse.unquote(percorso)):
            if chiave in self.risposte:
                return self.risposte[chiave]
        with self._blocco:
            self._mancanti.add(completo)
        return None

    def file_statico(self, percorso: str) -> Path | None:
        relativo = urllib.parse.unquote(percorso).lstrip("/\\") or "index.html"
        if "\x00" in relativo:
            return None
        try:
            destinazione = (self.radice / relativo).resolve()
        except (OSError, ValueError):
            return None
        if not destinazione.is_relative_to(self.radice) or not destinazione.is_file():
            return None
        return destinazione

    def __enter__(self):
        finto = self

        class Gestore(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *argomenti):          # niente registro a ogni richiesta
                pass

            def _invia(self, stato: int, tipo: str, corpo: bytes) -> None:
                self.send_response(stato)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(corpo)

            def _rispondi(self) -> None:
                lunghezza = int(self.headers.get("Content-Length") or 0)
                if lunghezza > MAX_CORPO_RICHIESTA:
                    self.close_connection = True
                    return self._invia(413, "application/json", b'{"detail": "troppo grande"}')
                if lunghezza > 0:
                    self.rfile.read(lunghezza)              # il corpo non serve: la risposta è quella registrata
                # a mano, non con urlsplit: «//nome» sarebbe letto come un altro server e servirebbe index.html
                percorso, _, query = self.path.split("#", 1)[0].partition("?")
                if percorso.startswith("/api/"):
                    testo = finto.risposta_api(percorso, query)
                    if testo is None:
                        return self._invia(404, "application/json", b'{"detail": "rotta non registrata"}')
                    return self._invia(200, "application/json; charset=utf-8", testo.encode("utf-8"))
                file = finto.file_statico(percorso) if self.command in ("GET", "HEAD") else None
                if file is None:
                    return self._invia(404, "text/plain; charset=utf-8", "non trovato".encode())
                tipo = TIPI.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                return self._invia(200, tipo, file.read_bytes())

            do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = _rispondi

        self._server = http.server.ThreadingHTTPServer((self.host, self.porta), Gestore)
        self._server.daemon_threads = True
        self.porta = self._server.server_address[1]
        self._filo = threading.Thread(target=self._server.serve_forever, name="server-finto", daemon=True)
        self._filo.start()
        return self

    def __exit__(self, *errore):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        return False


def host_per(porta: int) -> str:
    """Un indirizzo di loopback diverso da 127.0.0.1 (come le foto della web): un altro collaudo non disturba questo."""
    return f"127.0.0.{20 + porta % 200}"


def porta_libera(host: str) -> int:
    with socket.socket() as s:
        s.bind((host, 0))
        return s.getsockname()[1]


# =========================== foto (Playwright) ===========================
def posizioni_foglio(altezza_contenuto: int, altezza_visibile: int) -> list[int]:
    fondo = max(0, altezza_contenuto - altezza_visibile)
    passo = max(1, altezza_visibile - SOVRAPPOSIZIONE)
    return sorted(set(list(range(0, fondo, passo))[:PEZZI_FOGLIO - 1] + [fondo]))


def _aspetta(pagina, limite_ms: int = 20000) -> None:
    pagina.wait_for_function(PRONTA, timeout=limite_ms)
    try:
        pagina.wait_for_load_state("networkidle", timeout=5000)
    except Exception:                                  # una richiesta lunga: si va avanti, la pagina è già pronta
        pass
    pagina.wait_for_function(PRONTA, timeout=limite_ms)
    pagina.evaluate(FERMA)


def _foto(pagina, cartella: Path, nome: str) -> None:
    misura = pagina.evaluate(FOGLIO_CHE_SCORRE)
    if not misura:
        pagina.screenshot(path=str(cartella / f"{nome}.png"), full_page=True, animations="disabled", caret="hide")
        return
    for i, y in enumerate(posizioni_foglio(*misura), start=1):
        pagina.evaluate("(y) => { document.querySelector('#foglio .foglio-corpo').scrollTop = y; }", y)
        pagina.evaluate(FERMA)
        pagina.screenshot(path=str(cartella / (f"{nome}.png" if i == 1 else f"{nome}-{i}.png")),
                          animations="disabled", caret="hide")


def scatta(indirizzo: str, cartella: Path, scene, larghezze=LARGHEZZE, temi=TEMI, adesso: str | None = None) -> dict[str, str]:
    """Le foto di ogni scena, larghezza e tema in `cartella` (`<scena>-<larghezza>-<tema>.png`). Chrome di sistema senza
    finestra, service worker bloccato, movimento ridotto e animazioni spente, orologio fermo su `adesso` (ora italiana),
    stato della pagina azzerato a ogni scena. Torna le foto non riuscite: nome -> errore."""
    from playwright.sync_api import sync_playwright          # solo qui: i test dello script girano senza Playwright

    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    errori: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            ctx = browser.new_context(viewport={"width": larghezze[0], "height": 844}, device_scale_factor=1,
                                      locale="it-IT", timezone_id=FUSO, service_workers="block", reduced_motion="reduce")
            pagina = ctx.new_page()
            if adesso:
                istante = pagina.evaluate("(s) => new Date(s).getTime()", adesso)      # «adesso» letto con il fuso italiano
                ctx.clock.set_fixed_time(istante / 1000)
            ctx.add_init_script(STATO_INIZIALE)
            for tema in temi:
                pagina.emulate_media(color_scheme="light" if tema == "chiaro" else "dark", reduced_motion="reduce")
                for larghezza in larghezze:
                    pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
                    for nome_scena in scene:
                        scena, nome = SCENE[nome_scena], f"{nome_scena}-{larghezza}-{tema}"
                        try:
                            pagina.goto(indirizzo.rstrip("/") + scena.indirizzo, wait_until="load")
                            _aspetta(pagina)
                            for selettore in scena.clic:
                                pagina.locator(selettore).first.click(timeout=10000)
                                _aspetta(pagina)
                            _foto(pagina, cartella, nome)
                        except Exception as e:              # una scena rotta non ferma le altre: va nel riassunto
                            errori[nome] = f"{type(e).__name__}: {(str(e).splitlines() or [''])[0][:160]}"
                        print(f"{nome}: {errori.get(nome, 'ok')}", flush=True)
        finally:
            browser.close()
    return errori


# =========================== comando ===========================
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
    p = argparse.ArgumentParser(prog="aspetto_web.py", description="Regressione visiva della web: scene della PR contro main.")
    p.add_argument("--base", required=True, help="copia del repository di riferimento (main)")
    p.add_argument("--pr", required=True, help="copia del repository della PR")
    p.add_argument("--uscita", required=True, help="cartella delle foto e del riassunto")
    p.add_argument("--scenario", default=None, help="risposte registrate (di norma ios/fotografie/vero-prima.json della PR)")
    p.add_argument("--scene", type=lambda s: _elenco(s, list(SCENE)), default=list(SCENE), help=f"di norma tutte: {','.join(SCENE)}")
    p.add_argument("--larghezze", type=lambda s: _elenco(s, numeri=True), default=list(LARGHEZZE))
    p.add_argument("--temi", type=lambda s: _elenco(s, list(TEMI)), default=list(TEMI))
    p.add_argument("--corpo", default=None, help="file con la descrizione della PR (di norma la variabile d'ambiente CORPO)")
    return p.parse_args(argv)


def _prepara(a) -> tuple[Path, Path, Path, str | None]:
    """Cartelle della web, scenario e descrizione della PR. Solleva un errore con un messaggio chiaro se manca qualcosa."""
    web_base, web_pr = Path(a.base) / "fanta" / "web", Path(a.pr) / "fanta" / "web"
    for web in (web_base, web_pr):
        if not (web / "index.html").is_file():
            raise FileNotFoundError(f"non trovo la web in {web}")
    scenario = Path(a.scenario) if a.scenario else Path(a.pr) / "ios" / "fotografie" / "vero-prima.json"
    leggi_scenario(scenario)
    corpo = Path(a.corpo).read_text(encoding="utf-8") if a.corpo else os.environ.get("CORPO")
    return web_base, web_pr, scenario, corpo


def copia_diverse(uscita: Path, nome: str) -> None:
    """In `diverse/` i pezzi di una foto diversa, di main e della PR, e la differenza dove ci sono tutti e due (per l'artifact)."""
    (uscita / "diverse").mkdir(parents=True, exist_ok=True)
    for f in sorted(set(pezzi(uscita / "base", nome)) | set(pezzi(uscita / "pr", nome))):
        for lato, etichetta in (("base", "main"), ("pr", "pr")):
            if (uscita / lato / f).is_file():
                shutil.copyfile(uscita / lato / f, uscita / "diverse" / f"{f[:-4]}-{etichetta}.png")
        if (uscita / "base" / f).is_file() and (uscita / "pr" / f).is_file():
            immagine_differenza(uscita / "base" / f, uscita / "pr" / f, uscita / "diverse" / f"{f[:-4]}-differenza.png")


def _avviso(testo: str) -> None:
    """Un avviso sui controlli della corsa (solo su GitHub Actions), con «%» e gli a capo protetti come vuole GitHub."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        protetto = testo.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::warning title=Aspetto della web::{protetto}", flush=True)


def main(argv=None) -> int:
    a = leggi_argomenti(argv)
    uscita = Path(a.uscita)
    try:
        web_base, web_pr, scenario, corpo = _prepara(a)
    except (OSError, ValueError) as e:
        print(f"Preparazione non riuscita: {e}", flush=True)
        _avviso(f"preparazione non riuscita: {e}")
        return 3
    dichiarate = aspetto_dichiarato(corpo)
    nomi = [f"{s}-{w}-{t}" for t in a.temi for w in a.larghezze for s in a.scene]
    for vecchia in ("base", "pr", "base-2", "diverse"):
        shutil.rmtree(uscita / vecchia, ignore_errors=True)
    try:
        caso = porta_libera("127.0.0.1")
        h1, h2 = host_per(caso), host_per(caso + 1)
        with ServerFinto(web_base, scenario, porta_libera(h1), host=h1) as sb, \
                ServerFinto(web_pr, scenario, porta_libera(h2), host=h2) as sp:
            print(f"Server finti: main {sb.indirizzo}, PR {sp.indirizzo}", flush=True)
            errori_base = scatta(sb.indirizzo, uscita / "base", a.scene, a.larghezze, a.temi, sb.adesso)
            errori_pr = scatta(sp.indirizzo, uscita / "pr", a.scene, a.larghezze, a.temi, sp.adesso)
            buone = [n for n in nomi if n not in errori_base and n not in errori_pr]
            diff = confronta_scatti(uscita / "base", uscita / "pr", buone)
            da_rifare = sorted({n.split("-")[0] for n in buone if diff[n].diversa})
            errori_bis, diff_bis = {}, {}
            if da_rifare:                                  # una scena diversa si rifà su main: se cambia da sola è instabile
                print(f"Scene diverse, di nuovo su main: {', '.join(da_rifare)}", flush=True)
                errori_bis = scatta(sb.indirizzo, uscita / "base-2", da_rifare, a.larghezze, a.temi, sb.adesso)
                rifatte = [n for n in buone if diff[n].diversa and n not in errori_bis]
                diff_bis = confronta_scatti(uscita / "base", uscita / "base-2", rifatte)
            mancanti = sorted(set(sb.mancanti) | set(sp.mancanti))
    except ImportError as e:
        print(f"Preparazione non riuscita: manca Playwright o Pillow ({e})", flush=True)
        _avviso("manca Playwright o Pillow")
        return 3
    except Exception as e:                                 # Chrome che non parte, porta occupata
        print(f"Preparazione non riuscita: {type(e).__name__}: {e}", flush=True)
        _avviso(f"preparazione non riuscita: {type(e).__name__}")
        return 3

    problemi: dict[str, str] = {}
    for lato, errori in (("in main", errori_base), ("nella PR", errori_pr), ("in main, seconda volta", errori_bis)):
        for nome, errore in errori.items():
            problemi.setdefault(nome.split("-")[0], f"{nome} non si apre {lato}: {errore}")
    diverse: dict[str, list[str]] = {}
    instabili: dict[str, list[str]] = {}
    for nome in buone:
        if not diff[nome].diversa:
            continue
        scena = nome.split("-")[0]
        if scena in INSTABILI or (nome in diff_bis and diff_bis[nome].diversa):
            instabili.setdefault(scena, []).append(nome)
            continue
        diverse.setdefault(scena, []).append(nome)
        copia_diverse(uscita, nome)
    for scena, variazioni in instabili.items():
        if scena not in INSTABILI:
            problemi.setdefault(scena, f"cambia da sola anche su main ({', '.join(variazioni)}): instabile")
    testo = riassunto(diverse, dichiarate, problemi, mancanti, instabili)
    (uscita / "riassunto.md").write_text(testo, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(testo)
    print(testo, flush=True)
    codice = esito(set(diverse), dichiarate, set(problemi))
    if codice == 1:
        _avviso("scene diverse da main non dichiarate nella riga «Aspetto:»: " + ", ".join(sorted(set(diverse) - (dichiarate or set()))))
    elif codice == 2:
        _avviso("scene che non si aprono o instabili: " + ", ".join(sorted(problemi)))
    return codice


if __name__ == "__main__":
    for flusso in (sys.stdout, sys.stderr):
        flusso.reconfigure(encoding="utf-8")          # «» e lettere accentate anche nella console di Windows
    sys.exit(main())
