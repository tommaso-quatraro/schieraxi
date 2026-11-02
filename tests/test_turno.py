"""Inizio del turno: una regola sola (fanta/turno.py) per scadenza della formazione, giornata da giocare, «Rinviata» e fine della
giornata. Prima era scritta tre volte con piccole differenze (bordo dei 5 giorni, ripiego, punto di partenza). Dati finti."""
import sqlite3
from datetime import datetime, timedelta

from fanta import avvisi, consigli, fasi, turno

ST = "2026-27"


def d(testo):
    return datetime.fromisoformat(testo)


def test_inizio_del_turno():
    turno_vero = [d("2026-11-07 15:00"), d("2026-11-08 15:00"), d("2026-11-08 18:00"), d("2026-11-09 20:45")]
    assert turno.inizio(turno_vero + [d("2026-12-03 18:30"), d("2026-10-01 18:30"), None]) == d("2026-11-07 15:00")
    # Supercoppa (giornata 16 del 2025-26): sei partite il 20-21 dicembre, quattro recuperi a gennaio
    supercoppa = [d("2025-12-20 15:00")] * 3 + [d("2025-12-21 18:00")] * 3 + [d("2026-01-14 20:45")] * 4
    assert turno.inizio(supercoppa) == d("2025-12-20 15:00")
    # date sparse, nessun gruppo con metà delle partite: il gruppo più grande
    sparse = [d("2026-09-01 15:00"), d("2026-09-10 15:00"), d("2026-09-11 15:00"), d("2026-09-20 15:00"), d("2026-09-30 15:00"),
              d("2026-10-10 15:00")]
    assert turno.inizio(sparse) == d("2026-09-10 15:00")
    assert turno.inizio([]) is None and turno.inizio([None]) is None
    # bordo: da `inizio` compreso a `inizio + 5 giorni` escluso
    t = d("2026-11-07 15:00")
    assert turno.nel_turno(t, t) and turno.nel_turno(t + turno.FINESTRA - timedelta(minutes=1), t)
    assert not turno.nel_turno(t + turno.FINESTRA, t) and not turno.nel_turno(t - timedelta(minutes=1), t)
    assert consigli.FINESTRA_TURNO == fasi.FINESTRA_TURNO == turno.FINESTRA


def _db(righe):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, data, giocata) for data, giocata in righe])
    return db


def test_scadenza_rinviata_e_giornata_aperta_coerenti():
    """La partita con la data vecchia (rinviata, prima del turno) e il recupero a 5 giorni esatti: per tutti fuori dal turno."""
    righe = [("2026-10-31 15:00", 0),                                       # rinviata, data vecchia mai aggiornata
             ("2026-11-07 15:00", 0), ("2026-11-08 15:00", 0), ("2026-11-08 18:00", 0), ("2026-11-09 20:45", 0),
             ("2026-11-12 15:00", 0)]                                       # recupero esattamente 5 giorni dopo l'inizio
    db = _db(righe)
    partite = [{"data": data, "giocata": bool(g)} for data, g in righe]
    inizio = fasi.inizio_turno(partite)
    assert inizio == d("2026-11-07 15:00")
    adesso = d("2026-11-06 12:00")
    stati = [fasi.stato_partita(p, adesso, turno=inizio) for p in partite]
    assert stati == ["rinviata", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "rinviata"]
    # la scadenza è la prima partita NON rinviata
    da_giocare = [d(p["data"]) for p, s in zip(partite, stati) if s != "rinviata"]
    assert avvisi.prima_partita(db, ST, 9) == min(da_giocare)
    # a turno finito (tutte giocate tranne le due fuori dal turno) la giornata non resta aperta per loro
    db = _db([(data, 0 if data in ("2026-10-31 15:00", "2026-11-12 15:00") else 1) for data, _ in righe])
    assert consigli.prossima_giornata(db, ST, d("2026-11-11 12:00")) is None
    # ma una partita del turno ancora da giocare (posticipo del lunedì) la tiene aperta
    db = _db([(data, 0 if data in ("2026-10-31 15:00", "2026-11-09 20:45") else 1) for data, _ in righe])
    assert consigli.prossima_giornata(db, ST, d("2026-11-09 21:00")) == 9


def test_fine_della_giornata_dal_turno():
    db = _db([("2026-10-31 15:00", 1), ("2026-11-07 15:00", 1), ("2026-11-08 15:00", 1), ("2026-11-09 20:45", 1),
              ("2026-11-30 20:45", 1)])                                     # recupero giocato settimane dopo: non conta
    assert fasi.fine_giornata(db, ST, 9) == d("2026-11-09 20:45") + fasi.DURATA_PARTITA
