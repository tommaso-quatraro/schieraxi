"""Il turno di una giornata di Serie A: quando comincia e quali partite ne fanno parte. Una regola sola, usata da scadenza della
formazione (`avvisi.prima_partita`), giornata da giocare (`consigli.prossima_giornata`), stato «rinviata» e fine della giornata
(`fasi`): così scadenza, «Rinviata» e giornata aperta non si contraddicono.

Il turno è il primo gruppo di FINESTRA giorni con almeno metà delle partite (se le date sono sparse e nessun gruppo arriva a metà:
il gruppo più grande). Né una partita rinviata con la vecchia data mai aggiornata (prima del turno) né i recuperi già in
calendario settimane dopo (Supercoppa: giornata 16 del 2025-26, sei partite il 20-21 dicembre e quattro il 14-15 gennaio)
spostano il turno. Una partita è del turno se comincia da `inizio` (compreso) a `inizio + FINESTRA` (escluso).

ANTICIPI (decisione del 2/11/2026): il turno comincia dal GRUPPO PRINCIPALE, cioè il primo gruppo di partite vicine (fra una e
l'altra al massimo ANTICIPO_MIN) con almeno metà delle partite. Una partita da più di ANTICIPO_MIN a meno di ANTICIPO_MAX prima del
gruppo principale è un ANTICIPO: è della giornata (mai «Rinviata»), ma non fissa la scadenza della formazione. Una partita
giocata ancora prima (ANTICIPO_MAX o più) resta «prima del turno» e fissa la scadenza come sempre: è il caso della metà giornata
giocata e dell'altra metà rinviata a settimane dopo (`conta_per_scadenza`), riconoscibile perché il turno (il recupero) comincia
dopo la giornata dopo. Se invece il turno comincia prima della giornata dopo, quelle partite sono ANTICIPI LONTANI (Supercoppa,
coppe; `lontano`, #659), purché giocate prima della fine del turno della giornata precedente: non fissano la scadenza, non sono
«fuori dal turno» e i loro giocatori restano fermi come per un anticipo.
La finestra del turno si misura dal gruppo principale,
quindi un anticipo non fa uscire dal turno la partita del lunedì. Più di MAX_ANTICIPI partite così non sono anticipi ma un turno
diviso in due (per esempio a Pasqua: sabato e lunedì): allora vale la regola di sempre e il turno parte dalla prima.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

FINESTRA = timedelta(days=5)        # un turno di Serie A dura al massimo da venerdì a lunedì: oltre è un recupero
ANTICIPO_MIN = timedelta(hours=36)  # fra due partite dello stesso gruppo; più lontana prima del gruppo principale: anticipo
ANTICIPO_MAX = timedelta(days=7)    # da qui in poi prima del gruppo principale non è un anticipo: «prima del turno», come sempre
MAX_ANTICIPI = 2                    # di più non sono anticipi ma un turno diviso (Pasqua 2023-24: 5 il sabato, 5 il lunedì)


def nel_turno(quando: datetime, inizio: datetime) -> bool:
    return inizio <= quando < inizio + FINESTRA


def inizio(date: Iterable[datetime | None]) -> datetime | None:
    """Quando comincia il turno, dalle date delle partite della giornata (quelle senza data si ignorano). None se non ce n'è.
    Il primo gruppo principale (partite a meno di ANTICIPO_MIN l'una dall'altra, almeno metà del totale) se prima ha al massimo
    MAX_ANTICIPI anticipi; altrimenti il primo intervallo di FINESTRA con almeno metà delle partite, o quello più pieno, fra
    quelli che non lasciano prima più di MAX_ANTICIPI anticipi (issue #139: venerdì 3 partite e mercoledì dopo 4 → venerdì)."""
    ordinate = sorted(d for d in date if d is not None)
    if not ordinate:
        return None
    gruppi: list[list[datetime]] = [[ordinate[0]]]
    for prima, dopo in zip(ordinate, ordinate[1:]):
        if dopo - prima > ANTICIPO_MIN:
            gruppi.append([])
        gruppi[-1].append(dopo)
    principale = next((g for g in gruppi if 2 * len(g) >= len(ordinate)), None)
    if principale is not None and sum(1 for x in ordinate if anticipo(x, principale[0])) <= MAX_ANTICIPI:
        return principale[0]
    # mai un inizio con più di MAX_ANTICIPI anticipi prima (turno diviso: parte dalla prima); la prima partita va sempre bene
    candidati = [d for d in ordinate if sum(1 for x in ordinate if anticipo(x, d)) <= MAX_ANTICIPI]
    conta = [sum(1 for x in ordinate if nel_turno(x, d)) for d in candidati]
    return next((d for d, n in zip(candidati, conta) if 2 * n >= len(ordinate)),
                candidati[conta.index(max(conta))])


def anticipo(quando: datetime | None, inizio: datetime | None) -> bool:
    """Vero se la partita è un anticipo: più di ANTICIPO_MIN e meno di ANTICIPO_MAX prima dell'inizio del turno."""
    return quando is not None and inizio is not None and ANTICIPO_MIN < inizio - quando < ANTICIPO_MAX


def della_giornata(quando: datetime | None, inizio: datetime | None) -> bool:
    """Vero se la partita si gioca con la sua giornata (nel turno o in anticipo); falso se è rinviata (fuori o senza data)."""
    return quando is not None and inizio is not None and (nel_turno(quando, inizio) or anticipo(quando, inizio))


def lontano(quando: datetime | None, giocata: bool, inizio: datetime | None, precedente: datetime | None,
            prossimo: datetime | None) -> bool:
    """Vero se la partita è un ANTICIPO LONTANO (#659): già giocata, ANTICIPO_MAX o più prima dell'inizio del turno e prima della fine
    del turno della giornata precedente (`precedente` = il suo inizio, più FINESTRA), in una giornata il cui turno comincia prima di
    quello della giornata dopo (`prossimo`). È una partita anticipata di settimane (Supercoppa, coppe), quante che siano: è della
    giornata (mai «fuori dal turno»: chi l'ha giocata tiene il suo voto), non fissa la scadenza e i suoi giocatori restano fermi come
    per un anticipo. Altrimenti è metà giornata giocata e il resto rinviato (il turno è un recupero dopo la giornata dopo, oppure le
    partite sono state giocate dopo la giornata precedente, per esempio prima di una sosta): fissano la scadenza come sempre, e una
    scadenza passata non torna mai indietro. Si decide dalla posizione, non dal numero. Senza `precedente` o senza `prossimo` (prima o
    ultima giornata, calendario vicino senza date) mai."""
    return (bool(giocata) and quando is not None and inizio is not None and precedente is not None and prossimo is not None
            and inizio < prossimo and quando <= inizio - ANTICIPO_MAX and quando < precedente + FINESTRA)


def conta_per_scadenza(quando: datetime, giocata: bool, inizio: datetime | None, precedente: datetime | None = None,
                       prossimo: datetime | None = None) -> bool:
    """Se la partita conta per la scadenza della formazione (la prima che conta la fissa): dall'inizio del turno in poi, e le partite
    già giocate prima del turno (metà giornata giocata e il resto rinviato), ma mai un anticipo né un anticipo lontano (`lontano`,
    con `precedente` e `prossimo` = inizio del turno della giornata prima e di quella dopo)."""
    if inizio is None:
        return True
    return quando >= inizio or (giocata and not anticipo(quando, inizio)
                                and not lontano(quando, giocata, inizio, precedente, prossimo))
