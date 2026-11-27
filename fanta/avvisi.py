"""Quando si chiude la formazione di una giornata: la prima partita che conta (regola unica in turno.py) meno i minuti della regola
della lega. La usano avvisi, Oggi, Formazione, Diario, copia alla scadenza e controlli.

(Qui c'era anche l'avviso «formazione pronta», che non parte più dalla #693.)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import turno


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


def turni_vicini(db: sqlite3.Connection, stagione: str, giornata: int) -> tuple[datetime | None, datetime | None]:
    """(inizio del turno della giornata prima, inizio del turno della giornata dopo), per riconoscere gli anticipi lontani
    (turno.lontano). None dove la giornata non c'è o non ha date."""
    return turno.inizio(d for d, _ in _date(db, stagione, giornata - 1)), turno_dopo(db, stagione, giornata)


def turno_dopo(db: sqlite3.Connection, stagione: str, giornata: int) -> datetime | None:
    """L'inizio del turno della giornata dopo (`prossimo` di turno.inizio: un turno non comincia dopo la giornata dopo, #698).
    None se la giornata dopo non c'è o non ha date."""
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
    # settimane prima, entro la giornata precedente, con il turno che comincia prima della giornata dopo, #659): regola in
    # turno.conta_per_scadenza. Il turno non comincia dopo la giornata dopo (#698): con 4 partite nel fine settimana e 6 recuperi già
    # in calendario settimane dopo, la scadenza è il fine settimana anche prima che le 4 partite si giochino.
    # La regola è una sola, `turno.prima_che_conta`: la usa anche il modello (`modello.inizio_giornata`).
    return turno.prima_che_conta(date, (d for d, _ in _date(db, stagione, giornata - 1)),
                                 (d for d, _ in _date(db, stagione, giornata + 1)))


def scadenza(inizio: datetime | None, regole) -> datetime | None:
    """Quando si chiude la formazione: l'inizio della prima partita meno i minuti della regola della lega (`scadenza_minuti`,
    0 se la regola non c'è)."""
    if inizio is None:
        return None
    return inizio - timedelta(minutes=getattr(regole, "scadenza_minuti", 0) or 0)
