"""Server finto della web: serve `fanta/web/` e risponde alle `/api/...` con le risposte registrate di uno scenario
(ios/fotografie/vero-*.json, nomi inventati). Solo libreria standard, solo indirizzi locali (127.x), niente si scrive.

Lo usano la regressione visiva (script/ci/aspetto_web.py) e i test della web nel browser (tests/browser/). Spostato da
aspetto_web.py senza cambiarne il comportamento (issue #619): i suoi test stanno in tests/test_aspetto_web.py.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socket
import socketserver
import threading
import urllib.parse
from pathlib import Path

MAX_CORPO_RICHIESTA = 1_000_000

# Tipi dei file della web scritti qui: su Windows `mimetypes` legge il registro, che può dire text/plain per .js.
TIPI = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".json": "application/json", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml",
        ".png": "image/png", ".woff2": "font/woff2", ".ico": "image/x-icon"}


def leggi_scenario(percorso: Path) -> dict:
    """Lo scenario registrato (ios/fotografie/vero-*.json): `adesso` e `risposte` (indirizzo -> testo JSON)."""
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    risposte = dati.get("risposte") if isinstance(dati, dict) else None
    if not isinstance(risposte, dict) or not risposte or not all(isinstance(k, str) for k in risposte):
        raise ValueError(f"scenario senza risposte: {percorso}")
    if not isinstance(dati.get("adesso"), str) or not dati["adesso"]:
        raise ValueError(f"scenario senza «adesso»: {percorso}")
    return dati


class _ServerSenzaNome(http.server.ThreadingHTTPServer):
    """HTTPServer chiede il nome dell'indirizzo (getfqdn) all'avvio: per 127.0.0.NN su Windows sono secondi di attesa, e il
    nome non serve a niente."""
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = str(self.server_address[0]), self.server_address[1]


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
        self.host, self.porta = solo_locale(host), porta
        self._mancanti: set[str] = set()
        self._blocco = threading.Lock()
        self._server: _ServerSenzaNome | None = None
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
        # realpath + startswith: la forma che anche CodeQL riconosce come controllo del percorso
        radice = os.path.realpath(self.radice)
        try:
            destinazione = os.path.realpath(os.path.join(radice, relativo))
        except (OSError, ValueError):
            return None
        if not destinazione.startswith(radice + os.sep) or not os.path.isfile(destinazione):
            return None
        return Path(destinazione)

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
                tipo = TIPI.get(file.suffix.lower(), "application/octet-stream")   # mai dal nome del file
                return self._invia(200, tipo, file.read_bytes())

            do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = _rispondi

        self._server = _ServerSenzaNome((self.host, self.porta), Gestore)
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


def solo_locale(host: str) -> str:
    """Il server finto e la ricerca della porta ascoltano solo su 127.x: mai su tutte le interfacce né sulla rete."""
    if not re.fullmatch(r"127\.\d{1,3}\.\d{1,3}\.\d{1,3}", host or ""):
        raise ValueError(f"indirizzo non locale: {host!r}")
    return host


def porta_libera(host: str) -> int:
    host = solo_locale(host)
    with socket.socket() as s:
        s.bind((host, 0))
        return s.getsockname()[1]
