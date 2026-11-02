"""Registro del server, senza servizi esterni.

- `errori.log`: una riga per ogni risposta 5xx (quando, metodo, rotta, stato, tipo di errore). Mai indirizzi, nomi, password, valori
  ricevuti né tracce: la rotta è quella «di modello» (`/api/giocatore/{id}`), non l'indirizzo scritto da chi chiede.
- `sicurezza.log`: gli eventi di sicurezza (vedi `account.evento`); qui c'è solo la scrittura con rotazione, in comune.
- Contatori semplici in memoria (richieste, errori, tempi) dall'ultimo riavvio: li vede solo l'amministratore.
Tutti i file hanno la rotazione (`.1`, `.2`, `.3`): il registro non cresce senza fine. In più le righe più vecchie di
GIORNI_REGISTRI (30 giorni) si tolgono (al massimo un controllo all'ora per file), e gli indirizzi di rete si scrivono
accorciati (`accorcia_ip`).
"""
from __future__ import annotations

import ipaddress
import logging
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import percorsi

MAX_FILE, COPIE = 512 * 1024, 3
FILE_ERRORI = "errori.log"
FILE_SICUREZZA = "sicurezza.log"
GIORNI_REGISTRI = 30                 # dopo, una riga del registro si cancella
POTA_OGNI = 3600                     # secondi tra due controlli delle righe vecchie dello stesso file
_blocco_file = threading.Lock()
_ultima_potatura: dict[str, float] = {}


def accorcia_ip(ip) -> str:
    """L'indirizzo da scrivere nei registri, senza la parte che indica il singolo apparecchio: IPv4 senza l'ultimo numero
    (`1.2.3.x`), IPv6 solo la rete /64. Basta per vedere un attacco da una rete, non per riconoscere una persona."""
    try:
        ind = ipaddress.ip_address(str(ip).split("/")[0].strip("[]"))
    except ValueError:
        return "?"
    if isinstance(ind, ipaddress.IPv6Address) and ind.ipv4_mapped:
        ind = ind.ipv4_mapped
    if ind.version == 4:
        return ".".join(str(ind).split(".")[:3]) + ".x"
    return str(ipaddress.IPv6Network((ind, 64), strict=False))


def _riga_recente(riga: str, limite: datetime) -> bool:
    try:
        quando = datetime.fromisoformat(riga.split(" ", 1)[0])
    except ValueError:
        return True                      # riga senza data (non dovrebbe esserci): non si butta niente che non si capisce
    if quando.tzinfo is None:
        quando = quando.replace(tzinfo=timezone.utc)
    return quando >= limite


def pota(file: Path, giorni: int = GIORNI_REGISTRI) -> None:
    """Toglie dal file e dalle sue copie ruotate le righe più vecchie di `giorni`; una copia senza più righe si cancella.
    Chi chiama tiene `_blocco_file`. Se qualcosa non va, il registro resta com'è."""
    limite = datetime.now(timezone.utc) - timedelta(days=giorni)
    for f in [file] + [file.with_name(f"{file.name}.{i}") for i in range(1, COPIE + 1)]:
        try:
            if not f.exists():
                continue
            righe = f.read_text(encoding="utf-8", errors="replace").splitlines()
            tenute = [r for r in righe if _riga_recente(r, limite)]
            if len(tenute) == len(righe):
                continue
            if not tenute and f != file:
                f.unlink()
                continue
            nuovo = f.with_name(f.name + ".nuovo")
            descrittore = os.open(nuovo, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descrittore, "w", encoding="utf-8") as g:
                g.write("".join(r + "\n" for r in tenute))
            os.replace(nuovo, f)
        except OSError:
            continue


def pulito(v) -> str:
    """Un valore da scrivere nel registro: niente a capo né caratteri strani (nessuno può inventarsi righe finte), corto."""
    return re.sub(r"[^\w.:@/+{}-]", "?", str(v), flags=re.ASCII)[:64]


def adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scrivi(file: Path, riga: str, massimo: int | None = None) -> None:
    """Aggiunge una riga e fa ruotare il file se è troppo grande; ogni tanto toglie le righe più vecchie di GIORNI_REGISTRI.
    Se non si riesce a scrivere, l'app va avanti lo stesso."""
    massimo = MAX_FILE if massimo is None else massimo
    with _blocco_file:
        try:
            percorsi.cartella_privata(file.parent)
            adesso_s = time.monotonic()
            if adesso_s - _ultima_potatura.get(str(file), -POTA_OGNI) >= POTA_OGNI:
                _ultima_potatura[str(file)] = adesso_s
                pota(file)
            if file.exists() and file.stat().st_size > massimo:
                for i in range(COPIE, 0, -1):
                    vecchio = file.with_name(f"{file.name}.{i}")
                    precedente = file if i == 1 else file.with_name(f"{file.name}.{i - 1}")
                    if precedente.exists():
                        os.replace(precedente, vecchio)
            # leggibile solo dall'utente del servizio (chmod 600): dentro ci sono indirizzi accorciati e nomi utente
            descrittore = os.open(file, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(descrittore, "a", encoding="utf-8") as f:
                if os.name == "posix" and os.fstat(descrittore).st_mode & 0o077:
                    os.fchmod(descrittore, 0o600)            # un file creato da una versione vecchia
                f.write(riga + "\n")
        except OSError:
            pass


FILE_POSTA = "posta.log"
REGISTRI = (FILE_ERRORI, FILE_SICUREZZA, FILE_POSTA)
POTA_REGISTRI_OGNI = 24 * 3600       # secondi tra due pulizie di tutti i registri fatte dal servizio


def pota_registri() -> None:
    """Toglie le righe vecchie da tutti i registri, anche se nessuno ci scrive da tempo (all'avvio e una volta al giorno)."""
    cartella = percorsi.cartella_account()
    for nome in REGISTRI:
        with _blocco_file:
            pota(cartella / nome)


def sorveglia(fermo: threading.Event, ogni: float = POTA_REGISTRI_OGNI) -> None:
    """Thread del servizio: pulizia dei registri subito e poi ogni `ogni` secondi, finché `fermo` non si accende."""
    while True:
        try:
            pota_registri()
        except Exception:  # noqa: BLE001 - la pulizia non deve mai fermare il servizio
            pass
        if fermo.wait(ogni):
            return


class FiltroIndirizzi(logging.Filter):
    """Per il registro delle richieste di uvicorn (`uvicorn.access`): l'indirizzo di chi chiede si scrive accorciato come negli
    altri registri (IPv4 senza l'ultimo numero, IPv6 solo /64), senza porta."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and args and isinstance(args[0], str):
            host = args[0].rpartition(":")[0] or args[0]
            record.args = (accorcia_ip(host),) + args[1:]
        return True


FILTRO_INDIRIZZI = FiltroIndirizzi()


def accorcia_registro_richieste() -> None:
    """Mette il filtro sul registro delle richieste di uvicorn (una volta sola)."""
    registro_richieste = logging.getLogger("uvicorn.access")
    if FILTRO_INDIRIZZI not in registro_richieste.filters:
        registro_richieste.addFilter(FILTRO_INDIRIZZI)


def errore(metodo: str, rotta: str, stato: int, tipo: str | None = None) -> None:
    """Una risposta 5xx nel registro degli errori."""
    campi = {"metodo": metodo, "rotta": rotta or "(sconosciuta)", "stato": stato, "errore": tipo}
    scrivi(percorsi.cartella_account() / FILE_ERRORI,
           " ".join([adesso(), "errore"] + [f"{k}={pulito(v)}" for k, v in campi.items() if v is not None]))


def ultimi(nome: str, quanti: int = 30, nascondi_indirizzi: bool = False) -> list[dict]:
    """Le ultime righe di un registro (dalla più recente), già divise in campi. Gli indirizzi di rete si possono nascondere."""
    cartella = percorsi.cartella_account()
    righe: list[str] = []
    for file in (cartella / nome, cartella / f"{nome}.1"):
        try:
            righe = file.read_text(encoding="utf-8", errors="replace").splitlines()[-quanti:] + righe
        except OSError:
            continue
        if len(righe) >= quanti:
            break
    risultato = []
    for r in reversed(righe[-quanti:]):
        parti = r.split(" ")
        if len(parti) < 2:
            continue
        campi = dict(p.split("=", 1) for p in parti[2:] if "=" in p)
        if nascondi_indirizzi and "ip" in campi:
            campi["ip"] = _mascherato(campi["ip"])
        risultato.append({"quando": parti[0], "tipo": parti[1], **campi})
    return risultato


def _mascherato(ip: str) -> str:
    """192.168.1.20 -> 192.168.1.x ; indirizzi lunghi (IPv6) tagliati a metà. Quelli già accorciati (`1.2.3.x`) restano così."""
    if re.fullmatch(r"\d+\.\d+\.\d+\.x", ip):
        return ip
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip):
        return ip.rsplit(".", 1)[0] + ".x"
    return ip[: len(ip) // 2] + "…" if len(ip) > 6 else "?"


# ---------------------------------------------------------------- contatori (in memoria, da ultimo riavvio)
class Contatori:
    def __init__(self) -> None:
        self.blocco = threading.Lock()
        self.azzera()

    def azzera(self) -> None:
        with self.blocco:
            self.da = adesso()
            self.totale = self.ok = self.client = self.server = 0
            self.somma_ms = 0.0
            self.max_ms = 0.0
            self.recenti: deque[float] = deque(maxlen=500)
            self.per_rotta: dict[str, list[float]] = {}          # rotta di modello -> [richieste, somma ms, massimo ms]

    def conta(self, rotta: str, stato: int, ms: float) -> None:
        with self.blocco:
            self.totale += 1
            if stato >= 500:
                self.server += 1
            elif stato >= 400:
                self.client += 1
            else:
                self.ok += 1
            self.somma_ms += ms
            self.max_ms = max(self.max_ms, ms)
            self.recenti.append(ms)
            r = self.per_rotta.setdefault(rotta, [0, 0.0, 0.0])
            r[0] += 1
            r[1] += ms
            r[2] = max(r[2], ms)

    def riepilogo(self) -> dict:
        with self.blocco:
            ordinati = sorted(self.recenti)
            p95 = ordinati[min(len(ordinati) - 1, int(len(ordinati) * 0.95))] if ordinati else 0.0
            lente = sorted(self.per_rotta.items(), key=lambda kv: kv[1][1] / kv[1][0], reverse=True)[:5]
            return {"da": self.da, "richieste": self.totale, "riuscite": self.ok, "rifiutate": self.client, "errori": self.server,
                    "tempo_medio_ms": round(self.somma_ms / self.totale, 1) if self.totale else 0.0,
                    "tempo_p95_ms": round(p95, 1), "tempo_max_ms": round(self.max_ms, 1),
                    "piu_lente": [{"rotta": k, "richieste": int(v[0]), "medio_ms": round(v[1] / v[0], 1), "max_ms": round(v[2], 1)} for k, v in lente]}


contatori = Contatori()


def rotta_di_modello(request) -> str:
    """«/api/giocatore/{id}» invece dell'indirizzo vero: pochi valori possibili e nessun dato di chi chiede."""
    rotta = request.scope.get("route")
    return getattr(rotta, "path", None) or ("(file dell'app)" if not request.url.path.startswith("/api/") else "(sconosciuta)")
