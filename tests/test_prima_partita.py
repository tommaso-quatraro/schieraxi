"""Quando si chiude la formazione: la prima partita del TURNO della giornata, anche con recuperi già in calendario settimane dopo
(Supercoppa: in dicembre alcune partite della giornata si giocano a gennaio) o con una data vecchia mai aggiornata."""
import sqlite3
from datetime import datetime

from fanta import avvisi

ST = "2025-26"
# la giornata 16 del 2025-26, come nel calendario vero: 6 partite il 20-21 dicembre, 4 recuperi il 14-15 gennaio (Supercoppa)
G16 = ["2025-12-20 18:00", "2025-12-20 20:45", "2025-12-21 12:30", "2025-12-21 15:00", "2025-12-21 18:00", "2025-12-21 20:45",
       "2026-01-14 18:30", "2026-01-14 20:45", "2026-01-15 18:30", "2026-01-15 20:45"]


def _db(partite):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 16, d, g) for d, g in partite])
    return db


def test_recuperi_gia_in_calendario_non_spostano_la_scadenza():
    """Prima: prima del 20 dicembre la scadenza risultava il 14 gennaio (niente promemoria, niente giri delle probabili,
    la consigliata «congelata» si aggiornava a giornata già iniziata)."""
    assert avvisi.prima_partita(_db([(d, 0) for d in G16]), ST, 16) == datetime(2025, 12, 20, 18, 0)


def test_a_turno_giocato_resta_la_prima_partita():
    assert avvisi.prima_partita(_db([(d, int(d < "2026")) for d in G16]), ST, 16) == datetime(2025, 12, 20, 18, 0)


def test_una_partita_con_la_data_vecchia_non_anticipa_la_giornata():
    turno = ["2026-11-07 18:00", "2026-11-07 20:45", "2026-11-08 12:30", "2026-11-08 15:00", "2026-11-08 18:00", "2026-11-08 20:45",
             "2026-11-09 18:30", "2026-11-09 20:45", "2026-11-09 20:45"]
    db = _db([("2026-10-20 20:45", 0)] + [(d, 0) for d in turno])         # rinviata a ottobre, data mai aggiornata
    assert avvisi.prima_partita(db, ST, 16) == datetime(2026, 11, 7, 18, 0)


def test_partite_sparse_senza_un_gruppo_con_meta_delle_partite():
    sparse = ["2026-11-01 15:00", "2026-11-10 15:00", "2026-11-10 18:00", "2026-11-11 15:00", "2026-11-20 15:00", "2026-11-30 15:00",
              "2026-12-05 15:00"]
    assert avvisi.prima_partita(_db([(d, 0) for d in sparse]), ST, 16) == datetime(2026, 11, 10, 15, 0)     # il gruppo più grande


def test_turno_normale_e_giornata_senza_date():
    assert avvisi.prima_partita(_db([("2026-11-08 15:00", 0), ("2026-11-07 18:00", 0)]), ST, 16) == datetime(2026, 11, 7, 18, 0)
    assert avvisi.prima_partita(_db([]), ST, 16) is None
