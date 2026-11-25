"""Letture ripetute a ogni richiesta tenute in memoria (#907): stesso risultato di prima, rifatte da sole quando i dati cambiano,
con un tetto. Dati inventati."""
import sqlite3
from datetime import datetime, timedelta

from fanta import consigli

ST = "2031-32"          # una stagione che nessun'altra prova usa: le righe del calendario sono solo di queste prove


def _calendario(giornate: int = 6, inizio: datetime = datetime(2031, 9, 5, 15, 0), giocate_fino_a: int = 0):
    """Un calendario inventato: 10 partite per giornata, una giornata a settimana dal venerdì al lunedì."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    righe = []
    for g in range(1, giornate + 1):
        venerdi = inizio + timedelta(days=7 * (g - 1))
        for i in range(10):
            quando = venerdi + timedelta(days=i // 3, hours=3 * (i % 3))
            righe.append((ST, g, quando.strftime("%Y-%m-%d %H:%M"), f"casa{g}{i}", f"fuori{g}{i}", int(g <= giocate_fino_a)))
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)", righe)
    return db


def _conta_date(monkeypatch) -> list:
    lette = []
    vera = consigli._data
    monkeypatch.setattr(consigli, "_data", lambda testo: lette.append(testo) or vera(testo))
    return lette


def test_prossima_giornata_converte_le_date_una_volta_sola(monkeypatch):
    db = _calendario(giocate_fino_a=2)
    lette = _conta_date(monkeypatch)
    assert consigli.prossima_giornata(db, ST, datetime(2031, 9, 10, 12, 0)) == 3
    prima = len(lette)
    # altre richieste, anche con un'altra ora: il calendario è lo stesso, le date non si rileggono
    assert consigli.prossima_giornata(db, ST, datetime(2031, 9, 20, 12, 0)) == 3
    assert consigli.giornata_da_giocare(db, ST, None, datetime(2031, 9, 20, 12, 0)) == 3
    assert len(lette) == prima


def test_prossima_giornata_vede_subito_il_calendario_cambiato(monkeypatch):
    db = _calendario(giocate_fino_a=2)
    adesso = datetime(2031, 9, 23, 12, 0)                     # giornata 3 passata da giorni ma non ancora segnata giocata
    assert consigli.prossima_giornata(db, ST, adesso) == 4
    db.execute("UPDATE partite SET data = '2031-09-23 20:45' WHERE giornata = 3 AND casa = 'casa30'")   # spostata a stasera
    assert consigli.prossima_giornata(db, ST, adesso) == 3
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata <= 3")
    assert consigli.prossima_giornata(db, ST, adesso) == 4
    db.execute("DELETE FROM partite WHERE giornata >= 4")
    assert consigli.prossima_giornata(db, ST, adesso) is None


def test_prossima_giornata_a_freddo_e_a_caldo_uguale():
    """Per ogni ora della stagione inventata (con anticipi, recuperi e una giornata senza date) il risultato con la memoria vuota e
    con la memoria piena è lo stesso."""
    db = _calendario(giornate=8, giocate_fino_a=3)
    db.execute("UPDATE partite SET data = '2031-08-28 20:45' WHERE giornata = 2 AND casa = 'casa20'")      # anticipo lontano
    db.execute("UPDATE partite SET data = '2031-11-12 20:45', giocata = 0 WHERE giornata = 3 AND casa = 'casa31'")   # recupero
    db.execute("UPDATE partite SET data = NULL WHERE giornata = 8")                                          # ancora senza date
    ore = [datetime(2031, 8, 25) + timedelta(hours=7 * k) for k in range(300)]
    a_caldo = [consigli.prossima_giornata(db, ST, t) for t in ore]
    a_freddo = []
    for t in ore:
        consigli._giornate_lette.clear()
        a_freddo.append(consigli.prossima_giornata(db, ST, t))
    assert a_caldo == a_freddo
    assert len(set(a_caldo)) >= 5                  # la prova attraversa davvero più giornate


def test_le_giornate_lette_hanno_un_tetto():
    for k in range(consigli.MAX_GIORNATE_LETTE + 5):
        consigli.prossima_giornata(_calendario(giornate=2, inizio=datetime(2031, 9, 5, 15, 0) + timedelta(minutes=k)), ST,
                                   datetime(2031, 9, 1))
    assert len(consigli._giornate_lette) <= consigli.MAX_GIORNATE_LETTE
