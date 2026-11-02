"""Partite delle coppe europee delle squadre di Serie A (date inserite a mano da UEFA e Wikipedia, al 21/10/2026).

Servono per il turnover: chi gioca in coppa a ridosso di una partita di campionato ha più probabilità di essere riposato.
Si usano solo per le giornate lontane, quando non ci sono ancora le probabili formazioni (che il turnover lo dicono già).
Da aggiornare a mano quando escono i turni successivi (Atalanta in Conference League non è inserita: date da verificare).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

# squadra (come nell'archivio) -> date delle partite di coppa
COPPE: dict[str, list[date]] = {
    "inter": [date(2026, 11, 3), date(2026, 11, 25), date(2026, 12, 9), date(2027, 1, 19), date(2027, 1, 27)],
    "napoli": [date(2026, 11, 4), date(2026, 11, 24), date(2026, 12, 8), date(2027, 1, 20), date(2027, 1, 27)],
    "roma": [date(2026, 11, 3), date(2026, 11, 25), date(2026, 12, 8), date(2027, 1, 19), date(2027, 1, 27)],
    "como": [date(2026, 11, 4), date(2026, 11, 24), date(2026, 12, 9), date(2027, 1, 20), date(2027, 1, 27)],
    "milan": [date(2026, 11, 5), date(2026, 11, 26), date(2026, 12, 10), date(2027, 1, 21), date(2027, 1, 28)],
    "juventus": [date(2026, 11, 5), date(2026, 11, 26), date(2026, 12, 10), date(2027, 1, 21), date(2027, 1, 28)],
}
FINESTRA = 3                 # giorni prima o dopo la coppa in cui il turnover è più probabile
FATTORE_TURNOVER = 0.93      # quanto si abbassa la probabilità di giocare in quelle partite


def aggiornate_fino() -> date:
    """L'ultima data di coppa inserita: dopo, il turnover per le coppe non si calcola più (vanno inseriti i turni nuovi)."""
    return max(d for date_ in COPPE.values() for d in date_)


def coppa_vicina(squadra: str, quando: str | datetime | None) -> bool:
    """True se la squadra gioca in coppa entro FINESTRA giorni dalla partita di campionato."""
    if not quando:
        return False
    try:
        giorno = (quando if isinstance(quando, datetime) else datetime.fromisoformat(str(quando)[:16].replace(" ", "T"))).date()
    except ValueError:
        return False
    return any(abs(giorno - d) <= timedelta(days=FINESTRA) for d in COPPE.get(squadra, []))


def fattore_turnover(squadra: str, quando: str | datetime | None) -> float:
    return FATTORE_TURNOVER if coppa_vicina(squadra, quando) else 1.0
