"""Listone dei calciatori di Serie A (nome, ruolo, squadra, quotazione) da Fantacalcio.it.

È l'"anagrafe" del programma: ogni giocatore è identificato dal codice di Fantacalcio.it.
Si scarica al massimo una volta al giorno e si tiene in dati/cache/listone.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from . import fonti_attive
from .percorsi import CACHE, scrivi_sicuro
from .rete import UA as _AGENTE

URL = "https://www.fantacalcio.it/quotazioni-fantacalcio/fantacalcio"


def url_stagione(stagione: str) -> str:
    """Quotazioni di una stagione passata, es. '2025-26' (stessa tabella della pagina attuale)."""
    return f"https://www.fantacalcio.it/quotazioni-fantacalcio/{stagione}"


UA = {"User-Agent": _AGENTE}
FILE_CACHE = CACHE / "listone.json"


@dataclass(frozen=True)
class Calciatore:
    id: int                 # codice Fantacalcio.it
    nome: str               # es. "Martinez L."
    ruolo: str              # P, D, C, A
    ruolo_mantra: str
    squadra: str            # sigla, es. "INT"
    squadra_slug: str       # es. "inter"
    quotazione: int
    quotazione_iniziale: int
    fvm: int                # fantavalore di mercato (su 1000)


def _intero(testo: str | None) -> int:
    try:
        return int(str(testo).strip())
    except (TypeError, ValueError):
        return 0


def analizza_html(html: str) -> list[Calciatore]:
    s = BeautifulSoup(html, "lxml")
    calciatori = []
    for r in s.select("tr.player-row"):
        a = r.select_one("a.player-link")
        m = re.search(r"/squadre/([^/]+)/[^/]+/(\d+)", a["href"]) if a else None
        if not m:
            continue
        celle = {td["data-col-key"]: td.get_text(strip=True) for td in r.select("td[data-col-key]")}
        calciatori.append(Calciatore(
            id=int(m.group(2)),
            nome=a.get_text(strip=True),
            ruolo=r.get("data-filter-role-classic", "").upper(),
            ruolo_mantra=r.get("data-filter-role-mantra", ""),
            squadra=celle.get("sq", ""),
            squadra_slug=m.group(1),
            quotazione=_intero(celle.get("c_qa")),
            quotazione_iniziale=_intero(celle.get("c_qi")),
            fvm=_intero(celle.get("c_fvm")),
        ))
    if len(calciatori) < 300:
        raise ValueError(f"Listone: trovati solo {len(calciatori)} giocatori, la pagina forse è cambiata")
    return calciatori


def dall_archivio(percorso: Path | None = None) -> tuple[list[Calciatore], str] | None:
    """Il listone di riserva: la tabella `calciatori` dell'archivio (dati/fanta.sqlite), scritta da ogni aggiornamento.
    None se l'archivio non c'è o è vuoto. Si apre in sola lettura: non crea mai il file."""
    import sqlite3

    from . import archivio
    p = Path(percorso or archivio.FILE)
    if not p.is_file():
        return None
    try:
        db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=30)
        try:
            righe = db.execute("SELECT id, nome, ruolo, ruolo_mantra, squadra, squadra_slug, quotazione, quotazione_iniziale, fvm, "
                               "aggiornato FROM calciatori WHERE id IS NOT NULL AND ruolo IN ('P','D','C','A')").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return None
    if not righe:
        return None
    calciatori = [Calciatore(int(r[0]), str(r[1] or ""), str(r[2]), str(r[3] or ""), str(r[4] or ""), str(r[5] or ""),
                             int(r[6] or 0), int(r[7] or 0), int(r[8] or 0)) for r in righe]
    quando = max((str(r[9]) for r in righe if r[9]), default="") or datetime.now().isoformat(timespec="seconds")
    return calciatori, quando


_COMPLETI: dict = {}


def nomi_completi(percorso: Path | None = None) -> dict[int, str]:
    """Nome e cognome per esteso dei giocatori già abbinati con sicurezza a un'altra fonte (Understat, stessa squadra o
    nome inequivocabile): {codice: "Lautaro Martínez"}. Facoltativo: {} se l'archivio non c'è o non ha la tabella.
    Sola lettura; si rilegge solo quando il file cambia."""
    import sqlite3

    from . import archivio
    p = Path(percorso or archivio.FILE)
    try:
        chiave = (str(p), p.stat().st_mtime_ns)
    except OSError:
        return {}
    if _COMPLETI.get("chiave") == chiave:
        return _COMPLETI["nomi"]
    try:
        db = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=30)
        try:
            righe = db.execute("SELECT calciatore_id, nome FROM understat_giocatori WHERE calciatore_id IS NOT NULL "
                               "AND abbinamento IN ('squadra', 'altra_squadra') ORDER BY id").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return {}
    nomi = {int(cid): str(nome) for cid, nome in righe if nome}
    _COMPLETI.update(chiave=chiave, nomi=nomi)
    return nomi


def carica(aggiorna: bool = False, max_eta: timedelta = timedelta(hours=24),
           file_cache: Path = FILE_CACHE, archivio_db: Path | None = None) -> tuple[list[Calciatore], str]:
    """Restituisce (calciatori, data di scaricamento). Usa la cache se è recente. Senza file e senza fonte (spenta o che non risponde)
    usa l'anagrafe già nell'archivio (`dall_archivio`), tranne quando si sta aggiornando (lì l'errore deve vedersi)."""
    cache = _leggi_cache(file_cache)
    if cache and not aggiorna and datetime.now() - datetime.fromisoformat(cache[1]) < max_eta:
        return cache
    if not fonti_attive.acceso("fantacalcio"):
        if cache:
            return cache                      # fonte spenta: si usa il listone già salvato
        riserva = None if aggiorna else dall_archivio(archivio_db)
        if riserva:
            return riserva                    # né file né fonte: l'anagrafe già nell'archivio (esempi e importazioni funzionano)
        fonti_attive.richiedi("fantacalcio")
    try:
        r = requests.get(URL, headers=UA, timeout=30)
        r.raise_for_status()
        calciatori = analizza_html(r.text)
    except Exception:
        if cache:  # meglio un listone di ieri che niente
            return cache
        riserva = None if aggiorna else dall_archivio(archivio_db)
        if riserva:
            return riserva
        raise
    scaricato = datetime.now().isoformat(timespec="seconds")
    scrivi_sicuro(file_cache, json.dumps({"scaricato": scaricato, "calciatori": [asdict(c) for c in calciatori]},
                                         ensure_ascii=False))
    return calciatori, scaricato


def _leggi_cache(file_cache: Path) -> tuple[list[Calciatore], str] | None:
    """La cache rovinata o di una versione vecchia del programma vale come assente (si riscarica)."""
    try:
        dati = json.loads(file_cache.read_text(encoding="utf-8"))
        datetime.fromisoformat(dati["scaricato"])
        return [Calciatore(**c) for c in dati["calciatori"]], dati["scaricato"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
