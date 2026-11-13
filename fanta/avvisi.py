"""Quando avvisare l'iPhone: "formazione pronta" poco prima di ogni giornata, una volta sola.

Il comando `python -m fanta avviso` stampa il testo da mandare (o niente) e ricorda su file a che giornata è già
arrivato l'avviso. L'invio vero (ntfy) lo fa lo script del server: qui solo la decisione. Testi generici.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import turno
from .frasi import F, nome_giornata
from .percorsi import RADICE, scrivi_sicuro
from .regole import Regole, serie_a_a_lega

FILE_STATO = RADICE / "dati" / "avvisi.json"
ANTICIPO = timedelta(hours=30)       # si avvisa quando mancano meno di 30 ore alla prima partita


def _date(db: sqlite3.Connection, stagione: str, giornata: int) -> list[tuple[datetime, bool]]:
    """[(data, giocata)] delle partite con una data leggibile della giornata."""
    date = []
    for (testo, giocata) in db.execute("SELECT data, giocata FROM partite WHERE stagione = ? AND giornata = ? AND data IS NOT NULL",
                                       (stagione, giornata)):
        try:
            date.append((datetime.fromisoformat(str(testo)[:16].replace("T", " ")), bool(giocata)))
        except ValueError:
            continue
    return date


def inizio_turno_dopo(db: sqlite3.Connection, stagione: str, giornata: int) -> datetime | None:
    """L'inizio del turno della giornata dopo (turno.inizio), per riconoscere gli anticipi lontani (turno.lontano). None se non c'è."""
    return turno.inizio(d for d, _ in _date(db, stagione, giornata + 1))


def prima_partita(db: sqlite3.Connection, stagione: str, giornata: int) -> datetime | None:
    """Data e ora della PRIMA partita della giornata (anche se già giocata): è quando si chiude la formazione."""
    date = _date(db, stagione, giornata)
    if not date:
        return None
    # Dall'inizio del turno (regola unica in turno.py): né una partita rinviata con la vecchia data mai aggiornata né i recuperi già
    # in calendario settimane dopo spostano la scadenza. Prima si contava dall'ULTIMA partita: con i recuperi già in calendario la
    # formazione risultava aperta fino a gennaio.
    # Un anticipo (da 36 ore a 7 giorni prima del gruppo principale) non la fissa, e nemmeno un anticipo lontano (partita giocata
    # settimane prima, con il turno che comincia prima della giornata dopo, #659): regola in turno.conta_per_scadenza.
    inizio_turno = turno.inizio(d for d, _ in date)
    prossimo = inizio_turno_dopo(db, stagione, giornata)
    valide = [d for d, giocata in date if turno.conta_per_scadenza(d, giocata, inizio_turno, prossimo)]
    return min(valide)


def scadenza(inizio: datetime | None, regole) -> datetime | None:
    """Quando si chiude la formazione: l'inizio della prima partita meno i minuti della regola della lega (`scadenza_minuti`,
    0 se la regola non c'è)."""
    if inizio is None:
        return None
    return inizio - timedelta(minutes=getattr(regole, "scadenza_minuti", 0) or 0)


def inizio_giornata(db: sqlite3.Connection, stagione: str, giornata: int) -> datetime | None:
    """Data e ora della prima partita non ancora giocata della giornata, dall'inizio del turno in poi (regola unica in turno.py,
    come `prima_partita`): una partita rinviata rimasta con la data vecchia non conta."""
    date = []
    for (testo, giocata) in db.execute("SELECT data, giocata FROM partite WHERE stagione = ? AND giornata = ? AND data IS NOT NULL",
                                       (stagione, giornata)):
        try:
            date.append((datetime.fromisoformat(str(testo)[:16].replace("T", " ")), bool(giocata)))
        except ValueError:
            continue
    inizio_turno = turno.inizio(d for d, _ in date)
    return min((d for d, giocata in date if not giocata and inizio_turno is not None and d >= inizio_turno), default=None)


def _letto(percorso: Path) -> dict:
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError):
        return {}


def segna(stagione: str, giornata: int, file_stato: Path = FILE_STATO) -> None:
    """Ricorda che l'avviso «formazione pronta» di questa giornata è partito (per chi lo segna dopo l'invio, non prima)."""
    stato = _letto(file_stato)
    stato["ultimo"] = f"{stagione}/{giornata}"
    scrivi_sicuro(file_stato, json.dumps(stato))


def da_mandare(db: sqlite3.Connection, stagione: str, giornata: int | None, adesso: datetime,
               file_stato: Path = FILE_STATO, segna: bool = True, regole: Regole | None = None) -> dict | None:
    """{"titolo", "testo", "scadenza"} se è il momento di avvisare per la prossima giornata, altrimenti None. Con le `regole` il testo dice
    anche la giornata della lega («Giornata 6 · 9ª di Serie A: …»); senza, solo quella di Serie A.
    Mai a formazione chiusa: dopo la scadenza (la regola di cambi e promemoria) niente avviso, anche se la prima partita è già
    segnata giocata e la finestra delle 30 ore, misurata dalla prima partita ancora da giocare, sembrerebbe aperta (#652)."""
    if giornata is None:
        return None
    chiusura = scadenza(prima_partita(db, stagione, giornata), regole)
    if chiusura is None or chiusura <= adesso:
        return None
    inizio = inizio_giornata(db, stagione, giornata)
    if inizio is None or not (timedelta(0) < inizio - adesso <= ANTICIPO):
        return None
    chiave = f"{stagione}/{giornata}"
    stato = _letto(file_stato)
    if stato.get("ultimo") == chiave:
        return None
    if segna:
        stato["ultimo"] = chiave
        scrivi_sicuro(file_stato, json.dumps(stato))
    lega = serie_a_a_lega(giornata, regole) if regole is not None else None
    return {"titolo": "SchieraXI", "testo": F("n.pronta", giornata=nome_giornata(giornata, lega, avviso=True)), "scadenza": chiusura}
