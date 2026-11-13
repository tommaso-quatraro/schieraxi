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
    return (turno.inizio(d for d, _ in _date(db, stagione, giornata - 1)),
            turno.inizio(d for d, _ in _date(db, stagione, giornata + 1)))


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
    # turno.conta_per_scadenza.
    inizio_turno = turno.inizio(d for d, _ in date)
    precedente, prossimo = turni_vicini(db, stagione, giornata)
    valide = [d for d, giocata in date if turno.conta_per_scadenza(d, giocata, inizio_turno, precedente, prossimo)]
    return min(valide)


def scadenza(inizio: datetime | None, regole) -> datetime | None:
    """Quando si chiude la formazione: l'inizio della prima partita meno i minuti della regola della lega (`scadenza_minuti`,
    0 se la regola non c'è)."""
    if inizio is None:
        return None
    return inizio - timedelta(minutes=getattr(regole, "scadenza_minuti", 0) or 0)
