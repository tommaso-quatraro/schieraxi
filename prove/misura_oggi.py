r"""Tempi di Oggi, del widget e di altre rotte con più utenti insieme, su un server di prova LOCALE (#907). Mai un server in uso.

Uso (dalla radice, col .venv della cartella principale):
    .venv\Scripts\python.exe prove\misura_oggi.py --codice <cartella> [--porta 18907] [--uscita risultati.json] [--cartella <nuova>]
        [--utenti 15] [--cpu 4]

`--cpu 4` (o `4,6`): come un server con un solo processore (o due). Server e Diario girano solo su quei processori logici, con le
librerie di calcolo numerico a un filo per processore; lo script di misura gira sugli altri, così non ruba tempo al server.

`<cartella>` è una COPIA del codice con il suo archivio in `dati\fanta.sqlite`: la prova del Diario (`fanta affidabilita`, come il
cron del server) e l'aggiornamento simulato scrivono in quell'archivio. Per prepararla: `git archive HEAD` estratto nella cartella,
più una copia di `dati\fanta.sqlite`. Per confrontare due versioni si prepara una cartella per ognuna dallo stesso archivio.

Cosa fa: in una cartella temporanea crea N account inventati (`amicoNN`, password nuova a ogni lancio) con regole e rose della lega
d'esempio (i primi 10 nella stessa lega, gli altri con regole proprie, quindi senza calcoli in comune), avvia il server (multiutente,
niente diretta, pianificatore né invii) e misura, in ordine: Oggi a freddo per un account con regole proprie; Oggi di tutti insieme
(riscaldamento); un utente in fila su 6 rotte; tutti insieme sulle 6 rotte, due giri; Oggi di tutti nello stesso istante, tre volte,
e poi il widget allo stesso modo; ETag; Oggi, widget e Diario di tutti mentre
il Diario si calcola in un altro processo; Oggi e widget di tutti subito dopo un aggiornamento dei dati simulato (una riga in
`aggiornamenti`, come il giro delle probabili). La latenza è quella percepita dall'app: su 202 («sto calcolando») si riprova dopo
al massimo 3 secondi. CPU e memoria del processo del server solo su Windows (senza librerie in più). Il server si ferma per numero
di processo. Il risultato (JSON) va a video e in `--uscita`."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROTTE = ["oggi", "stato", "diario", "giocatore", "widget", "regole"]


# ---------- misure del processo (solo Windows, senza librerie in più) ----------
class Processo:
    def __init__(self, pid: int):
        self.h = None
        if os.name == "nt":
            import ctypes
            self.h = ctypes.windll.kernel32.OpenProcess(0x1410, False, pid)

    def cpu(self) -> float:
        if not self.h:
            return 0.0
        import ctypes
        from ctypes import wintypes
        t = [wintypes.FILETIME() for _ in range(4)]
        ctypes.windll.kernel32.GetProcessTimes(self.h, *[ctypes.byref(x) for x in t])
        return sum(((x.dwHighDateTime << 32) | x.dwLowDateTime) / 1e7 for x in t[2:])

    def memoria_mb(self) -> tuple[float, float]:
        """(memoria in uso, picco), in MB."""
        if not self.h:
            return 0.0, 0.0
        import ctypes
        from ctypes import wintypes

        class Mem(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t)] + [(f"x{k}", ctypes.c_size_t) for k in range(6)]
        m = Mem()
        m.cb = ctypes.sizeof(m)
        ctypes.windll.psapi.GetProcessMemoryInfo(self.h, ctypes.byref(m), m.cb)
        return m.WorkingSetSize / 2**20, m.PeakWorkingSetSize / 2**20


class Fase:
    """CPU e memoria del processo del server durante una fase."""
    def __init__(self, processo: Processo, nome: str):
        self.p, self.nome, self.risultato = processo, nome, {}

    def __enter__(self):
        self.c0, self.t0, self.campioni, self.fermo = self.p.cpu(), time.perf_counter(), [], threading.Event()

        def giro():
            while not self.fermo.is_set():
                self.campioni.append(self.p.memoria_mb()[0])
                self.fermo.wait(0.2)
        self.filo = threading.Thread(target=giro, daemon=True)
        self.filo.start()
        return self

    def __exit__(self, *_):
        self.fermo.set()
        self.filo.join()
        durata, cpu = time.perf_counter() - self.t0, self.p.cpu() - self.c0
        self.risultato = {"durata_s": round(durata, 2), "cpu_s": round(cpu, 2), "cpu_pct_un_core": round(100 * cpu / durata) if durata else 0,
                          "ram_mb_max": round(max(self.campioni or [0])), "ram_mb_picco_processo": round(self.p.memoria_mb()[1])}
        print(f"[{self.nome}] {self.risultato}", flush=True)


def legame(cpu: list[int] | None) -> str:
    """Righe di Python che legano ai processori `cpu` il processo che le esegue (vanno prima di caricare numpy); '' senza limite."""
    if not cpu:
        return ""
    if os.name == "nt":
        maschera = sum(1 << c for c in cpu)
        return ("import ctypes; _k = ctypes.windll.kernel32; _k.GetCurrentProcess.restype = ctypes.c_void_p; "
                "_k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]; "
                f"_k.SetProcessAffinityMask(_k.GetCurrentProcess(), {maschera}) or exit('processori non impostati'); ")
    return f"import os; os.sched_setaffinity(0, {set(cpu)!r}); "


def lascia_processori(cpu: list[int] | None) -> None:
    """Lo script di misura (e chi lancia) gira sugli altri processori fra quelli che ha già: non ruba tempo al server legato a `cpu`."""
    if not cpu:
        return
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        mio, sistema = ctypes.c_size_t(), ctypes.c_size_t()
        k.GetProcessAffinityMask(k.GetCurrentProcess(), ctypes.byref(mio), ctypes.byref(sistema))
        if not k.SetProcessAffinityMask(k.GetCurrentProcess(), mio.value & ~sum(1 << c for c in cpu)):
            raise SystemExit("processori dello script di misura non impostati")
    else:
        os.sched_setaffinity(0, os.sched_getaffinity(0) - set(cpu))


def riassunto(v: list[float]) -> dict:
    v = sorted(v)
    pos = lambda p: v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]          # noqa: E731
    return {"n": len(v), "p50": round(pos(50), 1), "p95": round(pos(95), 1), "max": round(v[-1], 1)} if v else {"n": 0}


# ---------- preparazione ----------
def prepara(codice: Path, cartella: Path, n: int, password: str) -> None:
    """N account inventati con regole e rose della lega d'esempio (in un processo a parte: legge la cartella degli account dalle variabili)."""
    programma = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(codice)!r})
from fanta import account, contesto
codice, n, password = Path({str(codice)!r}), {n}, {password!r}
regole0 = json.loads((codice / "lega" / "esempio" / "regole.json").read_text(encoding="utf-8"))
rose0 = json.loads((codice / "lega" / "esempio" / "rose.json").read_text(encoding="utf-8"))
squadre = [s["nome"] for s in rose0["squadre"]]
h = account.hash_password(password)
db = account.apri()
for i in range(n):
    nome = f"amico{{i:02d}}"
    cur = db.execute("INSERT INTO utenti (nome_utente, nome_visualizzato, password_hash, recupero_hash, ruolo, creato) "
                     "VALUES (?, ?, ?, ?, ?, '2026-09-01T10:00:00+00:00')", (nome, nome, h, "x", "amministratore" if i == 0 else "utente"))
    db.commit()
    c = contesto.cartella_utente(cur.lastrowid)
    c.mkdir(parents=True, exist_ok=True)
    regole, rose = json.loads(json.dumps(regole0)), json.loads(json.dumps(rose0))
    rose["mia_squadra"] = squadre[i % len(squadre)]
    if i >= 10:
        regole["bonus"]["assist"] = round(1.0 + (i - 9) * 0.25, 2)
    (c / "regole.json").write_text(json.dumps(regole), encoding="utf-8")
    (c / "rose.json").write_text(json.dumps(rose), encoding="utf-8")
db.close()
"""
    subprocess.run([sys.executable, "-c", programma], env=os.environ | ambiente(codice, cartella), check=True, cwd=codice)


def ambiente(codice: Path, cartella: Path, cpu: list[int] | None = None) -> dict:
    fili = {k: str(len(cpu)) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")} if cpu else {}
    return {"FANTA_MULTIUTENTE": "1", "FANTA_DATI_UTENTI": str(cartella), "FANTA_LEGA": str(codice / "lega" / "esempio"),
            "FANTA_PROXY": "1", "FANTA_LIVE": "0", "FANTA_PIANIFICATORE": "0", "FANTA_MAIL": "spento",
            "SCHIERAXI_CANALE": str(cartella / "nessun-canale"), "SENTINELLA_NTFY_URL": "http://127.0.0.1:9/",
            "PYTHONIOENCODING": "utf-8"} | fili


# ---------- richieste ----------
async def chiedi(cl, token: str, ip: str, percorso: str, registro: dict, nome: str, codici: dict | None = None):
    """Come l'app: su 202 riprova (al massimo 3 s di attesa); la latenza è quella fino alla risposta utile."""
    h = {"X-Fanta": "1", "X-Forwarded-For": ip, "Authorization": f"Bearer {token}"}
    inizio = time.perf_counter()
    while True:
        r = await cl.get(percorso, headers=h, timeout=180)
        if codici is not None:
            codici[r.status_code] = codici.get(r.status_code, 0) + 1
        if r.status_code == 202 and time.perf_counter() - inizio < 170:
            await asyncio.sleep(min(float(r.json().get("riprova_tra", 3)), 3))
            continue
        break
    registro.setdefault(nome, []).append((time.perf_counter() - inizio) * 1000)
    if r.status_code not in (200, 304):
        print("  !", nome, r.status_code, r.text[:120], flush=True)
    return r


async def misura(base: str, processo: Processo, codice: Path, n: int, password: str, env: dict, cpu: list[int] | None = None) -> dict:
    import httpx
    uscita: dict = {}
    ids = [g["id"] for s in json.loads((codice / "lega" / "esempio" / "rose.json").read_text(encoding="utf-8"))["squadre"] for g in s["giocatori"]]
    url = lambda rotta, i: f"/api/giocatore/{ids[(i * 37) % len(ids)]}" if rotta == "giocatore" else f"/api/{rotta}"     # noqa: E731
    ip = lambda i: f"10.0.{i}.7"                                                                                           # noqa: E731
    async with httpx.AsyncClient(base_url=base, limits=httpx.Limits(max_connections=100, max_keepalive_connections=100)) as cl:
        tk = {}
        for i in range(n):                                   # in fila: l'hash della password è voluto lento
            r = await cl.post("/api/account/accedi", headers={"X-Fanta": "1", "X-Forwarded-For": ip(i)},
                              json={"nome_utente": f"amico{i:02d}", "password": password, "nativo": True}, timeout=60)
            r.raise_for_status()
            tk[i] = r.json()["token"]
        altra = min(n - 1, 12)                               # un account con regole proprie: nessun calcolo in comune
        uno, tre = min(n - 1, 1), min(n - 1, 3)              # gli account delle fasi «1 utente» ed ETag (con --utenti 1 c'è solo il primo)

        reg = {}
        with Fase(processo, "freddo") as f:
            await chiedi(cl, tk[altra], ip(altra), "/api/oggi", reg, "oggi")
        uscita["freddo"] = {"oggi_ms": round(reg["oggi"][0])} | f.risultato

        reg = {}
        with Fase(processo, "riscaldamento") as f:
            await asyncio.gather(*[chiedi(cl, tk[i], ip(i), "/api/oggi", reg, "oggi") for i in range(n)])
        uscita["riscaldamento"] = {"oggi_insieme_ms": riassunto(reg["oggi"])} | f.risultato

        reg = {}
        with Fase(processo, "1 utente") as f:
            for rotta in ROTTE:
                for k in range(15):
                    await chiedi(cl, tk[uno], ip(uno), url(rotta, k), reg, rotta)
        uscita["un_utente"] = {"rotte": {k: riassunto(v) for k, v in reg.items()}} | f.risultato

        reg, codici = {}, {}

        async def amico(i):
            for giro in range(2):
                for rotta in ROTTE:
                    await chiedi(cl, tk[i], ip(i), url(rotta, i + giro), reg, rotta, codici)
        with Fase(processo, f"{n} utenti insieme") as f:
            await asyncio.gather(*[amico(i) for i in range(n)])
        uscita["insieme"] = {"rotte": {k: riassunto(v) for k, v in reg.items()}, "codici": codici} | f.risultato

        for rotta in ("oggi", "widget"):                     # tutti aprono la stessa schermata nello stesso istante, tre volte
            reg, codici = {}, {}
            with Fase(processo, f"{rotta}: {n} nello stesso istante") as f:
                for _ in range(3):
                    await asyncio.gather(*[chiedi(cl, tk[i], ip(i), url(rotta, i), reg, rotta, codici) for i in range(n)])
            uscita[f"{rotta}_stesso_istante"] = {"ms": riassunto(reg[rotta]), "codici": codici} | f.risultato

        etag = {}
        for rotta in ROTTE:
            h = {"X-Fanta": "1", "X-Forwarded-For": ip(tre), "Authorization": f"Bearer {tk[tre]}"}
            r = await cl.get(url(rotta, tre), headers=h)
            e = r.headers.get("etag")
            etag[rotta] = {"codice": r.status_code, "byte": len(r.content),
                           "con_if_none_match": (await cl.get(url(rotta, tre), headers=h | {"If-None-Match": e})).status_code if e else None}
        uscita["etag"] = etag

        reg, codici = {}, {}
        t0 = time.perf_counter()
        diario = subprocess.Popen([sys.executable, "-c", f"{legame(cpu)}import runpy, sys; sys.argv = ['fanta', 'affidabilita', '--minuti', '5']; "
                                   "runpy.run_module('fanta', run_name='__main__', alter_sys=True)"], cwd=codice, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        with Fase(processo, f"{n} utenti durante il Diario") as f:
            await asyncio.sleep(1.0)
            giri = 0
            while diario.poll() is None and giri < 3:
                await asyncio.gather(*[chiedi(cl, tk[i], ip(i), url(rotta, i), reg, rotta, codici)
                                       for i in range(n) for rotta in ("oggi", "widget", "diario")])
                giri += 1
        diario.communicate(timeout=900)
        uscita["durante_diario"] = {"rotte": {k: riassunto(v) for k, v in reg.items()}, "codici": codici, "giri": giri,
                                    "diario_durata_s": round(time.perf_counter() - t0, 1)} | f.risultato

        db = sqlite3.connect(codice / "dati" / "fanta.sqlite")
        db.execute("INSERT OR REPLACE INTO aggiornamenti (cosa, quando) VALUES ('probabili', ?)", (datetime.now().isoformat(timespec="seconds"),))
        db.commit()
        db.close()
        reg, codici = {}, {}
        with Fase(processo, f"{n} utenti subito dopo un aggiornamento") as f:
            await asyncio.gather(*[chiedi(cl, tk[i], ip(i), url(rotta, i), reg, rotta, codici) for i in range(n) for rotta in ("oggi", "widget")])
        uscita["dopo_aggiornamento"] = {"rotte": {k: riassunto(v) for k, v in reg.items()}, "codici": codici} | f.risultato
    uscita["memoria_finale_mb"] = [round(x) for x in processo.memoria_mb()]
    return uscita


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--codice", type=Path, required=True, help="copia del codice con il suo archivio in dati/fanta.sqlite")
    a.add_argument("--porta", type=int, default=18907)
    a.add_argument("--utenti", type=int, default=15)
    a.add_argument("--uscita", type=Path)
    a.add_argument("--cartella", type=Path, help="dove creare gli account inventati (una cartella che non c'è ancora); senza, una "
                                                 "cartella temporanea nuova")
    a.add_argument("--cpu", type=lambda s: sorted({int(x) for x in s.split(",")}),
                   help="processori logici (numeri separati da virgole) per server e Diario, come un server con meno processori: "
                        "per esempio 4")
    arg = a.parse_args()
    codice = arg.codice.resolve()
    if not (codice / "dati" / "fanta.sqlite").is_file() or not (codice / "fanta").is_dir():
        raise SystemExit(f"{codice}: serve una copia del codice con dati/fanta.sqlite")
    import httpx
    if arg.cartella:
        arg.cartella.mkdir(parents=True)                     # errore se c'è già: mai account di prova in una cartella in uso
        cartella = arg.cartella.resolve()
    else:
        cartella = Path(tempfile.mkdtemp(prefix="misura-oggi-"))
    password = secrets.token_urlsafe(18)
    env = os.environ | ambiente(codice, cartella, arg.cpu)
    lascia_processori(arg.cpu)
    prepara(codice, cartella, arg.utenti, password)
    file_pid = cartella / "pid.txt"
    with open(cartella / "server.log", "w", encoding="utf-8") as log:
        srv = subprocess.Popen([sys.executable, "-c", f"{legame(arg.cpu)}import os; open(r'{file_pid}', 'w').write(str(os.getpid())); "
                                f"import uvicorn; from fanta import server; "
                                f"uvicorn.run(server.app, host='127.0.0.1', port={arg.porta}, log_level='warning')"],
                               cwd=codice, env=env, stdout=log, stderr=subprocess.STDOUT)
        pid = None
        try:
            for _ in range(200):
                try:
                    if httpx.get(f"http://127.0.0.1:{arg.porta}/api/novita", timeout=2).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.3)
            pid = int(file_pid.read_text())      # il vero processo del server (su Windows il .venv ne lancia un altro)
            risultato = {"utenti": arg.utenti, "cpu": arg.cpu} | asyncio.run(
                misura(f"http://127.0.0.1:{arg.porta}", Processo(pid), codice, arg.utenti, password, env, arg.cpu))
        finally:
            if pid:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                else:
                    os.kill(pid, 15)
            srv.wait(timeout=30)
    testo = json.dumps(risultato, indent=1, ensure_ascii=False)
    print(testo)
    if arg.uscita:
        arg.uscita.write_text(testo, encoding="utf-8")


if __name__ == "__main__":
    main()
