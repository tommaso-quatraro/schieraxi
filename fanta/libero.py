"""Momento libero per installare una versione nuova del server (`python -m fanta momento-libero`, usato da
`script/server/aggiorna-app.sh`).

Installare vuol dire riavviare il servizio: durante una partita di Serie A si interrompono i risultati in diretta, e nell'ora prima
della scadenza della formazione di una lega i giri delle probabili (a 60, 30 e 15 minuti, `pianificatore.py`). Quindi «occupato» se:
- una partita non ancora giocata per il calendario è nella sua finestra di gioco (da 10 minuti prima del calcio d'inizio a 20 minuti
  dopo la fine stimata, le stesse costanti di `live.py`), oppure la diretta salvata (`dati/live.json`) la dà ancora in gioco, al
  massimo fino a TETTO dal calcio d'inizio;
- per una lega attiva mancano al massimo PRIMA_SCADENZA minuti alla scadenza (stessa regola della scadenza di tutta l'app:
  `avvisi.prima_partita` e `avvisi.scadenza`, che si basano su `turno.py`).
Codici di uscita: 0 = libero, 3 = occupato (con il motivo su una riga). Ogni errore (archivio mancante, dati strani) = libero: un
controllo guasto non deve mai fermare gli aggiornamenti. Solo letture.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import avvisi, consigli, live
from .percorsi import CARTELLA_LEGA, RADICE
from .regole import Regole

OCCUPATO = 3
PRIMA_SCADENZA = timedelta(minutes=60)
TETTO = timedelta(hours=4)                  # una diretta ferma su «in gioco» non blocca oltre questo
FILE_LIVE = RADICE / "dati" / "live.json"


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " ")) if testo else None
    except ValueError:
        return None


def _in_gioco_nella_diretta(file_live: Path | None) -> set[tuple[str, str]]:
    """Le partite che la diretta salvata dà ancora in gioco (formato in docs/LIVE.md). File mancante o rotto: nessuna."""
    try:
        dati = json.loads(Path(file_live).read_text(encoding="utf-8"))
        partite = dati.get("partite") if isinstance(dati, dict) else None
        return {(p.get("casa"), p.get("trasferta")) for p in (partite or {}).values()
                if isinstance(p, dict) and p.get("stato") in live.IN_GIOCO}
    except (OSError, ValueError, TypeError, AttributeError):
        return set()


def partita_in_corso(db, adesso: datetime, file_live: Path | None = None) -> str | None:
    righe = db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE data >= ? AND data <= ? ORDER BY data",
                       ((adesso - TETTO).strftime("%Y-%m-%d %H:%M"), (adesso + live.PRIMA).strftime("%Y-%m-%d %H:%M"))).fetchall()
    in_gioco = None
    for data, casa, trasferta, giocata in righe:
        inizio = _data(data)
        if inizio is None or giocata:
            continue
        if live.in_finestra(str(data), adesso):
            return f"partita in corso: {casa}-{trasferta} (inizio {inizio:%H:%M})"
        if inizio + live.FINE_STIMATA + live.DOPO < adesso <= inizio + TETTO:
            in_gioco = _in_gioco_nella_diretta(file_live) if in_gioco is None else in_gioco
            if (casa, trasferta) in in_gioco:
                return f"partita ancora in corso secondo la diretta: {casa}-{trasferta} (inizio {inizio:%H:%M})"
    return None


def scadenza_vicina(db, leghe: list[Regole], adesso: datetime) -> str | None:
    stagione = consigli.stagione_corrente()
    viste = set()
    for r in leghe:
        try:
            chiave = (r.scadenza_minuti, r.prima_giornata_lega)
            if chiave in viste:
                continue
            viste.add(chiave)
            giornata = consigli.giornata_da_giocare(db, stagione, r, adesso)     # l'ora del controllo, non l'orologio vero
            scad = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), r) if giornata else None
        except Exception:  # noqa: BLE001 - una lega con dati strani non ferma il controllo delle altre
            continue
        if scad is not None and scad - PRIMA_SCADENZA <= adesso <= scad:
            return f"scadenza della formazione alle {scad:%H:%M}"
    return None


def motivo(db, leghe: list[Regole], adesso: datetime, file_live: Path | None = None) -> str | None:
    """Perché adesso non si installa (una riga), o None se è un momento libero."""
    return partita_in_corso(db, adesso, file_live) or scadenza_vicina(db, leghe, adesso)


def leghe_attive() -> list[Regole]:
    """Le regole delle leghe attive, come il riscaldamento del servizio: senza account la lega di `lega/`, con gli account quelle
    di chi ha usato l'app negli ultimi giorni."""
    from . import regole as reg
    from .riscaldamento import contesti_da_scaldare
    out = []
    for c in contesti_da_scaldare(lambda: None):
        try:
            out.append(reg.carica(CARTELLA_LEGA / "regole.json" if c is None else c.regole))
        except Exception:  # noqa: BLE001
            continue
    return out


def _apri_db() -> sqlite3.Connection:
    """L'archivio in sola lettura (mai crearlo né scriverci da qui)."""
    return sqlite3.connect(f"{(RADICE / 'dati' / 'fanta.sqlite').as_uri()}?mode=ro", uri=True, timeout=10)


def main(adesso: datetime | None = None) -> int:
    adesso = adesso or datetime.now()
    try:
        db = _apri_db()
        try:
            try:
                leghe = leghe_attive()
            except Exception:  # noqa: BLE001 - senza leghe si guardano almeno le partite
                leghe = []
            m = motivo(db, leghe, adesso, FILE_LIVE)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        print(f"controllo non riuscito ({type(e).__name__}): libero")
        return 0
    if m:
        print(m)
        return OCCUPATO
    print("libero")
    return 0
