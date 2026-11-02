"""Avviso "formazione pronta": una volta sola, solo vicino alla giornata."""
import sqlite3
from datetime import datetime

from fanta import avvisi

ST = "2026-27"


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [
        (ST, 9, "2026-10-28 18:30", 0), (ST, 9, "2026-10-29 20:45", 0), (ST, 10, "2026-11-04 20:45", 0),
        (ST, 8, "2026-10-21 20:45", 1)])
    return db


def test_avvisa_solo_vicino_e_una_volta(tmp_path):
    db, f = _db(), tmp_path / "avvisi.json"
    lontano = datetime(2026, 10, 26, 10, 0)           # 56 ore prima
    assert avvisi.da_mandare(db, ST, 9, lontano, f) is None
    vicino = datetime(2026, 10, 27, 20, 0)            # 22 ore prima
    a = avvisi.da_mandare(db, ST, 9, vicino, f)
    assert a and "Giornata 9" in a["testo"]
    assert avvisi.da_mandare(db, ST, 9, vicino, f) is None          # già avvisato
    assert avvisi.da_mandare(db, ST, 10, datetime(2026, 11, 3, 18, 0), f)   # la giornata dopo sì


def test_non_avvisa_a_giornata_iniziata_o_senza_dati(tmp_path):
    db, f = _db(), tmp_path / "avvisi.json"
    assert avvisi.da_mandare(db, ST, 9, datetime(2026, 10, 28, 19, 0), f) is None   # prima partita già iniziata
    assert avvisi.da_mandare(db, ST, None, datetime(2026, 10, 27, 20, 0), f) is None
    assert avvisi.da_mandare(db, ST, 30, datetime(2026, 10, 27, 20, 0), f) is None
    f.write_text("non è json", encoding="utf-8")                     # file di stato rovinato: si riparte
    assert avvisi.da_mandare(db, ST, 9, datetime(2026, 10, 27, 20, 0), f)
