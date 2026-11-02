r"""Prova di carico di SchieraXI in LOCALE: N utenti finti contro un server avviato dallo script (mai un server in uso, mai servizi altrui).

Esempio (dalla radice, col .venv della cartella principale):
    .venv\Scripts\python.exe prove\carico.py --utenti 10 25 50 100 --regole uguali diverse --uscita carico.json

Cosa fa, per ogni prova: crea una cartella temporanea con account.sqlite e N utenti (password uguale, hash calcolato una volta),
dà a ognuno regole e rose (copia di lega/; con `diverse` ogni utente ha regole e mia squadra propri, quindi nessuna cache in comune),
avvia il server (multiutente, FANTA_LIVE=0, FANTA_PIANIFICATORE=0, nessuna fonte esterna) e fa partire gli utenti sfalsati nella
`rampa`. Ogni utente: accesso, Oggi, widget, formazione, mercato, scambi, diario, scelta e osservati (scritture), poi qualche giro
di riletture con pause. Una risposta 202 («sto calcolando») si riprova ogni 3 secondi come fa l'app: la latenza che si registra
è quella percepita (fino alla risposta utile). L'archivio dati (dati/fanta.sqlite) va copiato prima nella cartella dati/ del
repository (è ignorato da git).
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# Password degli utenti finti: nuova a ogni lancio (vivono in una cartella temporanea e spariscono con lei), oppure da
# FANTA_CARICO_PASSWORD per ripetere una prova identica. Mai una password fissa scritta nel codice.
PASSWORD = os.environ.get("FANTA_CARICO_PASSWORD") or secrets.token_urlsafe(18)
PORTA = 18765
SQUADRE = [s["nome"] for s in json.loads((RADICE / "lega" / "rose.json").read_text(encoding="utf-8"))["squadre"]]
CON_SQUADRA = False        # True = scambi con una squadra precisa (più calcoli); False = «trova per me» su tutte


# ---------- misure del processo (solo Windows, senza librerie in più) ----------
class _Mem(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


class Processo:
    def __init__(self, pid: int):
        self.h = ctypes.windll.kernel32.OpenProcess(0x1410, False, pid)

    def cpu_secondi(self) -> float:
        t = [wintypes.FILETIME() for _ in range(4)]
        ctypes.windll.kernel32.GetProcessTimes(self.h, *[ctypes.byref(x) for x in t])
        f = lambda x: ((x.dwHighDateTime << 32) | x.dwLowDateTime) / 1e7
        return f(t[2]) + f(t[3])

    def memoria_mb(self) -> tuple[float, float]:
        m = _Mem()
        m.cb = ctypes.sizeof(m)
        ctypes.windll.psapi.GetProcessMemoryInfo(self.h, ctypes.byref(m), m.cb)
        return m.WorkingSetSize / 2**20, m.PeakWorkingSetSize / 2**20


# ---------- preparazione ----------
def prepara(cartella: Path, n: int, diverse: bool, codice: Path) -> None:
    os.environ["FANTA_DATI_UTENTI"] = str(cartella)
    sys.path.insert(0, str(codice))
    from fanta import account, contesto
    hash_ = account.hash_password(PASSWORD)
    regole0 = json.loads((codice / "lega" / "regole.json").read_text(encoding="utf-8"))
    rose0 = json.loads((codice / "lega" / "rose.json").read_text(encoding="utf-8"))
    squadre = [s["nome"] for s in rose0["squadre"]]
    db = account.apri()
    for i in range(n):
        nome = f"prova{i:03d}"
        cur = db.execute("INSERT INTO utenti (nome_utente, nome_visualizzato, password_hash, recupero_hash, ruolo, creato) "
                         "VALUES (?, ?, ?, ?, 'utente', '2026-10-31T10:00:00')", (nome, nome, hash_, "x"))
        db.commit()
        c = contesto.cartella_utente(cur.lastrowid)
        c.mkdir(parents=True, exist_ok=True)
        regole, rose = json.loads(json.dumps(regole0)), json.loads(json.dumps(rose0))
        if diverse:
            regole["bonus"]["assist"] = round(1.0 + (i % 40) * 0.05, 2)                # regole diverse: impronta diversa
            rose["mia_squadra"] = squadre[i % len(squadre)]
        (c / "regole.json").write_text(json.dumps(regole), encoding="utf-8")
        (c / "rose.json").write_text(json.dumps(rose), encoding="utf-8")
    db.close()


def dimensione(percorso: Path) -> int:
    return sum(f.stat().st_size for f in percorso.rglob("*") if f.is_file()) if percorso.exists() else 0


# ---------- utenti finti ----------
class Registro:
    def __init__(self):
        self.lat: dict[str, list[float]] = {}        # latenza percepita (fino alla risposta utile), ms
        self.grezze: dict[str, list[float]] = {}     # latenza della singola richiesta HTTP
        self.codici: dict[str, int] = {}
        self.errori: list[str] = []
        self.n202 = 0

    def codice(self, c):
        self.codici[str(c)] = self.codici.get(str(c), 0) + 1


async def chiedi(cl, reg: Registro, nome: str, metodo: str, url: str, ip: str, token: str | None, **kw):
    """Una richiesta come la fa l'app: su 202/429/503 riprova dopo l'attesa indicata (al massimo 3 s) per al massimo 150 s."""
    import httpx
    h = {"X-Forwarded-For": ip, "X-Fanta": "1"} | kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    inizio = time.perf_counter()
    while True:
        t0 = time.perf_counter()
        try:
            r = await cl.request(metodo, url, headers=h, timeout=170, **kw)
        except httpx.HTTPError as e:
            reg.codice("eccezione")
            reg.errori.append(f"{nome}: {type(e).__name__}")
            return None
        reg.grezze.setdefault(nome, []).append((time.perf_counter() - t0) * 1000)
        reg.codice(r.status_code)
        if r.status_code in (202, 429, 503) and time.perf_counter() - inizio < 150:
            reg.n202 += r.status_code == 202
            await asyncio.sleep(min(float(r.headers.get("retry-after", 3)), 3))
            continue
        break
    reg.lat.setdefault(nome, []).append((time.perf_counter() - inizio) * 1000)
    if r.status_code >= 400 and r.status_code != 304:
        reg.errori.append(f"{nome}: {r.status_code} {r.text[:80]}")
    return r


async def utente(cl, reg: Registro, i: int, nome: str, partenza: float, giri: int):
    await asyncio.sleep(partenza)
    ip = f"10.{i // 250}.{i % 250}.7"
    q = lambda *a, **k: chiedi(cl, reg, *a, ip=ip, **k)
    r = await q("accedi", "POST", "/api/account/accedi", token=None, json={"nome_utente": nome, "password": PASSWORD, "nativo": True})
    if r is None or r.status_code != 200:
        return
    tk = r.json()["token"]
    await q("oggi", "GET", "/api/oggi", token=tk)
    r = await q("widget", "GET", "/api/widget", token=tk)
    etag = r.headers.get("etag") if r is not None and r.status_code == 200 else None
    f = await q("formazione", "GET", "/api/formazione", token=tk)
    await q("mercato", "GET", "/api/mercato", token=tk)
    await q("rosa", "GET", "/api/rosa", token=tk)
    await q("scambi", "GET", "/api/scambi/proposte", params={"con": SQUADRE[(i + 1) % len(SQUADRE)]} if CON_SQUADRA else None, token=tk)
    await q("diario", "GET", "/api/diario", token=tk)
    if etag:
        await q("widget_304", "GET", "/api/widget", token=tk, headers={"If-None-Match": etag})
    # scritture: la scelta della giornata e un osservato
    try:
        corpo = f.json()
        ids = [t["id"] for t in corpo["titolari"]]
        await q("scelta_scrivi", "POST", "/api/formazione/valuta", token=tk, json={"titolari": ids, "salva": True})
        await q("scelta_leggi", "GET", f"/api/scelta?giornata={corpo['giornata']}", token=tk)
    except Exception:  # noqa: BLE001
        pass
    await q("osservati_scrivi", "PUT", "/api/osservati/5116", token=tk)
    await q("osservati_leggi", "GET", "/api/osservati", token=tk)
    await q("osservati_togli", "DELETE", "/api/osservati/5116", token=tk)
    for _ in range(giri):                                   # riletture, come chi riapre l'app durante la giornata
        await asyncio.sleep(random.uniform(1, 3))
        await q("oggi", "GET", "/api/oggi", token=tk)
        await q("formazione", "GET", "/api/formazione", token=tk)
        await q("widget_304", "GET", "/api/widget", token=tk, headers={"If-None-Match": etag} if etag else {})
        await q("mercato", "GET", "/api/mercato", token=tk)


def pct(v: list[float], p: float) -> float:
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else float("nan")


def riassunto(v: list[float]) -> dict:
    return {"n": len(v), "p50": round(pct(v, 50)), "p95": round(pct(v, 95)), "p99": round(pct(v, 99)), "max": round(max(v)) if v else 0}


async def carico(n: int, rampa: float, giri: int, base: str) -> Registro:
    import httpx
    reg = Registro()
    limiti = httpx.Limits(max_connections=400, max_keepalive_connections=400)
    async with httpx.AsyncClient(base_url=base, limits=limiti) as cl:
        await asyncio.gather(*[utente(cl, reg, i, f"prova{i:03d}", random.uniform(0, rampa), giri) for i in range(n)])
    return reg


def una_prova(n: int, diverse: bool, rampa: float, giri: int, porta: int, codice: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="carico-"))
    prepara(tmp, n, diverse, codice)
    env = os.environ | {"FANTA_MULTIUTENTE": "1", "FANTA_DATI_UTENTI": str(tmp), "FANTA_PROXY": "1", "MAX_UTENTI": "1000",
                        "FANTA_LIVE": "0", "FANTA_PIANIFICATORE": "0", "FANTA_MAIL": "log", "PYTHONPATH": str(codice)}
    log = open(tmp / "server.log", "w", encoding="utf-8")
    srv = subprocess.Popen([sys.executable, "-c", f"import os; open(r'{tmp / 'pid.txt'}', 'w').write(str(os.getpid())); import uvicorn; from fanta import server; uvicorn.run(server.app, host='127.0.0.1', port={porta}, log_level='warning')"],
                           cwd=codice, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        import httpx
        for _ in range(100):
            try:
                if httpx.get(f"http://127.0.0.1:{porta}/api/novita", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.3)
        pid = int((tmp / "pid.txt").read_text())          # il vero processo del server (su Windows il .venv ne lancia un altro)
        p = Processo(pid)
        ram_inizio, cpu0, t0 = p.memoria_mb()[0], p.cpu_secondi(), time.perf_counter()
        campioni, fermo = [], threading.Event()

        def campiona():
            while not fermo.is_set():
                campioni.append(p.memoria_mb()[0])
                fermo.wait(0.5)
        th = threading.Thread(target=campiona, daemon=True)
        th.start()
        reg = asyncio.run(carico(n, rampa, giri, f"http://127.0.0.1:{porta}"))
        durata, cpu = time.perf_counter() - t0, p.cpu_secondi() - cpu0
        fermo.set()
        th.join()
        ram_fine, ram_picco = p.memoria_mb()
        utili = [x for k, v in reg.lat.items() if k != "accedi" for x in v]
        out = {"utenti": n, "regole": "diverse" if diverse else "uguali", "durata_s": round(durata, 1), "richieste_http": sum(reg.codici.values()),
               "codici": reg.codici, "n_202": reg.n202, "cpu_s": round(cpu, 1), "cpu_media_pct_di_un_core": round(100 * cpu / durata),
               "ram_inizio_mb": round(ram_inizio), "ram_fine_mb": round(ram_fine), "ram_picco_mb": round(ram_picco),
               "latenza_percepita_ms": riassunto(utili), "latenza_accesso_ms": riassunto(reg.lat.get("accedi", [])),
               "latenza_singola_http_ms": riassunto([x for k, v in reg.grezze.items() if k != "accedi" for x in v]),
               "per_rotta": {k: riassunto(v) for k, v in sorted(reg.lat.items())},
               "errori": sorted(set(reg.errori))[:15], "n_errori": len(reg.errori),
               "archivio_comune_kb": round((codice / "dati" / "fanta.sqlite").stat().st_size / 1024),
               "account_sqlite_kb": round(sum(f.stat().st_size for f in tmp.glob("account.sqlite*")) / 1024),
               "cartelle_utenti_kb": round(dimensione(tmp / "utenti") / 1024)}
        log.flush()
        testo = (tmp / "server.log").read_text(encoding="utf-8", errors="replace")
        out["traceback_nel_log"] = testo.count("Traceback")
        out["locked_nel_log"] = testo.lower().count("locked")
        return out
    finally:
        try:
            os.kill(int((tmp / "pid.txt").read_text()), 15)      # per PID, mai taskkill generico
        except (OSError, ValueError):
            pass
        srv.terminate()
        try:
            srv.wait(10)
        except subprocess.TimeoutExpired:
            srv.kill()
        log.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--utenti", type=int, nargs="+", default=[10, 25, 50, 100])
    a.add_argument("--regole", nargs="+", choices=["uguali", "diverse"], default=["uguali", "diverse"])
    a.add_argument("--rampa", type=float, default=20.0, help="secondi su cui sfalsare l'arrivo degli utenti")
    a.add_argument("--giri", type=int, default=3)
    a.add_argument("--porta", type=int, default=PORTA)
    a.add_argument("--codice", type=Path, default=RADICE, help="cartella con il codice da provare (per confrontare prima/dopo)")
    a.add_argument("--uscita", type=Path)
    a = a.parse_args()
    risultati = []
    for modo in a.regole:
        for n in a.utenti:
            r = una_prova(n, modo == "diverse", a.rampa, a.giri, a.porta + len(risultati), a.codice)
            risultati.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    if a.uscita:
        a.uscita.write_text(json.dumps(risultati, indent=1, ensure_ascii=False), encoding="utf-8")
