"""Il turno di una giornata di Serie A: quando comincia e quali partite ne fanno parte. Una regola sola, usata da scadenza della
formazione (`avvisi.prima_partita`), giornata da giocare (`consigli.prossima_giornata`), stato «rinviata» e fine della giornata
(`fasi`): così scadenza, «Rinviata» e giornata aperta non si contraddicono.

Il turno è il primo gruppo di FINESTRA giorni con almeno metà delle partite (se le date sono sparse e nessun gruppo arriva a metà:
il gruppo più grande). Né una partita rinviata con la vecchia data mai aggiornata (prima del turno) né i recuperi già in
calendario settimane dopo (Supercoppa: giornata 16 del 2025-26, sei partite il 20-21 dicembre e quattro il 14-15 gennaio)
spostano il turno. Una partita è del turno se comincia da `inizio` (compreso) a `inizio + FINESTRA` (escluso).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

FINESTRA = timedelta(days=5)        # un turno di Serie A dura al massimo da venerdì a lunedì: oltre è un recupero


def nel_turno(quando: datetime, inizio: datetime) -> bool:
    return inizio <= quando < inizio + FINESTRA


def inizio(date: Iterable[datetime | None]) -> datetime | None:
    """Quando comincia il turno, dalle date delle partite della giornata (quelle senza data si ignorano). None se non ce n'è."""
    ordinate = sorted(d for d in date if d is not None)
    if not ordinate:
        return None
    conta = [sum(1 for x in ordinate if nel_turno(x, d)) for d in ordinate]
    return next((d for d, n in zip(ordinate, conta) if 2 * n >= len(ordinate)),
                ordinate[conta.index(max(conta))])
