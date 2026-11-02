"""La giornata resta «in corso» finché non sono finite TUTTE le sue partite (domenica sera e posticipi del lunedì compresi).

Caso vero del 1/11/2026: giornata 10 di Serie A con 6 partite giocate e 4 da giocare (domenica 18:00 e 20:45, lunedì 18:30 e 20:45).
Prima della correzione la giornata «da giocare» era già la 11 (serviva metà delle partite ancora da giocare): Oggi diceva che la
giornata era finita e contava 5 giorni e 1 ora alla scadenza della successiva."""
import sqlite3
from datetime import datetime

from fanta import consigli, gestione, regole
from fanta.regole import Regole

ST = "2026-27"
G10 = [("2026-10-31 15:00", 1), ("2026-10-31 18:00", 1), ("2026-10-31 20:45", 1), ("2026-11-01 12:30", 1), ("2026-11-01 15:00", 1),
       ("2026-11-01 15:00", 1), ("2026-11-01 18:00", 0), ("2026-11-01 20:45", 0), ("2026-11-02 18:30", 0), ("2026-11-02 20:45", 0)]
G11 = [("2026-11-06 20:45", 0), ("2026-11-07 15:00", 0), ("2026-11-07 15:00", 0), ("2026-11-07 18:00", 0), ("2026-11-07 20:45", 0),
       ("2026-11-08 12:30", 0), ("2026-11-08 15:00", 0), ("2026-11-08 15:00", 0), ("2026-11-08 18:00", 0), ("2026-11-08 20:45", 0)]
DOMENICA_SERA = datetime(2026, 11, 1, 19, 35)


def _db(g10=G10, g11=G11):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)",
                   [(ST, g, d, f"c{g}{i}", f"t{g}{i}", gi) for g, partite in ((10, g10), (11, g11)) for i, (d, gi) in enumerate(partite)])
    return db


def _regole_scadenza_10():
    r = regole.imposta(Regole(), "scadenza_minuti", "10")
    return regole.imposta(r, "prima_giornata_lega", "4")


def test_domenica_sera_con_partite_in_corso_la_giornata_non_e_finita(monkeypatch):
    assert consigli.prossima_giornata(_db(), ST, DOMENICA_SERA) == 10
    monkeypatch.setattr(consigli, "_adesso", lambda: DOMENICA_SERA)     # senza «adesso» esplicito: l'ora del server
    assert consigli.prossima_giornata(_db(), ST) == 10
    assert consigli.giornata_da_giocare(_db(), ST, _regole_scadenza_10()) == 10


def test_oggi_dice_in_corso_e_non_conta_alla_giornata_dopo(monkeypatch):
    monkeypatch.setattr(consigli, "_adesso", lambda: DOMENICA_SERA)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(), adesso=DOMENICA_SERA, regole=_regole_scadenza_10())
    assert o["giornata"] == 10 and o["giornata_lega"] == 7
    assert o["iniziata"] is True                                   # «In corso», non un conto alla rovescia di 5 giorni
    assert len(o["partite"]) == 10 and sum(not p["giocata"] for p in o["partite"]) == 4


def test_lunedi_sera_i_posticipi_tengono_aperta_la_giornata():
    assert consigli.prossima_giornata(_db(), ST, datetime(2026, 11, 2, 23, 0)) == 10   # risultati non ancora scaricati


def test_finite_tutte_si_passa_alla_prossima_con_la_scadenza_giusta(monkeypatch):
    finite = [(d, 1) for d, _ in G10]
    martedi = datetime(2026, 11, 3, 10, 0)
    assert consigli.prossima_giornata(_db(finite), ST, martedi) == 11
    monkeypatch.setattr(consigli, "_adesso", lambda: martedi)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(finite), adesso=martedi, regole=_regole_scadenza_10())
    assert o["giornata"] == 11 and o["iniziata"] is False
    assert o["scadenza"] == "2026-11-06 20:35"                     # 10 minuti prima della prima partita della giornata 11


def test_se_i_risultati_tardano_dopo_mezza_giornata_si_passa_alla_prossima():
    assert consigli.prossima_giornata(_db(), ST, datetime(2026, 11, 3, 10, 0)) == 11


def test_recupero_isolato_non_tiene_ferma_la_giornata():
    rinviata_lontano = [(d, 1) for d, _ in G10[:-1]] + [("2026-12-10 20:45", 0)]   # rinviata a dicembre
    assert consigli.prossima_giornata(_db(rinviata_lontano), ST, datetime(2026, 11, 3, 10, 0)) == 11
    vecchia_data = [(d, 1) for d, _ in G10[:-1]] + [("2026-11-02 20:45", 0)]       # rinviata, data mai aggiornata
    assert consigli.prossima_giornata(_db(vecchia_data), ST, datetime(2026, 11, 4, 10, 0)) == 11


def test_giornata_ancora_quasi_tutta_da_giocare():
    sabato = [(d, 1 if i < 2 else 0) for i, (d, _) in enumerate(G10)]
    assert consigli.prossima_giornata(_db(sabato), ST, datetime(2026, 10, 31, 19, 0)) == 10
