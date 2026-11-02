"""Controlli di coerenza dei dati: dati finti in un archivio temporaneo."""
import pytest

from fanta import archivio, controlli, stato_dati

ST = "2026-27"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _giornata(db, g, n=10, giocata=1, prima_id=0):
    for i in range(n):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (prima_id + g * 100 + i, ST, g, f"2026-09-{g:02d} 15:00", f"c{i}", f"t{i}", giocata))


def _esiti(db):
    return {r["nome"]: r for r in controlli.esegui(db)}


def test_giornate_complete_e_incomplete(db):
    _giornata(db, 1)
    _giornata(db, 2, n=9)
    e = _esiti(db)["partite_per_giornata"]
    assert e["esito"] == "errore" and "g2: 9" in e["dettaglio"]
    db.execute("DELETE FROM partite WHERE giornata = 2")
    assert _esiti(db)["partite_per_giornata"]["esito"] == "ok"


def test_voti_mancanti_in_giornata_finita(db):
    _giornata(db, 1)
    _giornata(db, 2, giocata=0)                   # non finita: non si controlla
    assert _esiti(db)["voti_per_giornata"]["esito"] == "avviso"
    for i in range(200):
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, voto_red) VALUES (?, 1, ?, 6.0)", (ST, i))
    assert _esiti(db)["voti_per_giornata"]["esito"] == "ok"


def test_somma_xg(db):
    _giornata(db, 1)
    db.execute("INSERT INTO partite_understat (id, stagione, casa, trasferta, xg_casa, xg_trasferta, giocata, scaricata) "
               "VALUES (1, ?, 'a', 'b', 1.5, 0.8, 1, 1)", (ST,))
    for sq, xg in (("a", 1.4), ("b", 0.9)):
        db.execute("INSERT INTO prestazioni (understat_partita, understat_giocatore, squadra, xg) VALUES (1, ?, ?, ?)",
                   (1 if sq == "a" else 2, sq, xg))
    assert _esiti(db)["somma_xg"]["esito"] == "ok"
    db.execute("UPDATE prestazioni SET xg = 4.0 WHERE squadra = 'a'")           # 4,0 contro 1,5: non torna
    e = _esiti(db)["somma_xg"]
    assert e["esito"] == "avviso" and e["valore"] == 1.0


def test_titolari_per_squadra(db):
    _giornata(db, 1, n=1, giocata=0)
    for sq in ("c0", "t0"):
        for i in range(11):
            db.execute("INSERT INTO probabili (stagione, giornata, fonte, calciatore_id, squadra, partita_id, stato) "
                       "VALUES (?, 1, 'fantacalcio', ?, ?, 100, 'titolare')", (ST, i + (0 if sq == "c0" else 50), sq))
    assert _esiti(db)["titolari_per_squadra"]["esito"] == "ok"
    db.execute("DELETE FROM probabili WHERE calciatore_id = 3")
    e = _esiti(db)["titolari_per_squadra"]
    assert e["esito"] == "avviso" and "c0: 10" in e["dettaglio"]


def test_senza_dati_non_scrive_righe_e_riesegue_senza_duplicati(db):
    assert controlli.esegui(db) == []
    _giornata(db, 1)
    controlli.esegui(db)
    controlli.esegui(db)
    assert db.execute("SELECT COUNT(*) FROM controlli WHERE nome = 'partite_per_giornata'").fetchone()[0] == 1


def test_un_controllo_rotto_diventa_avviso(db, monkeypatch):
    _giornata(db, 1)
    monkeypatch.setitem(controlli.CONTROLLI, "rotto", lambda d, s: 1 / 0)
    e = _esiti(db)["rotto"]
    assert e["esito"] == "avviso" and "ZeroDivisionError" in e["dettaglio"]


def test_nello_stato_dei_dati(db):
    _giornata(db, 1)
    controlli.esegui(db)
    r = stato_dati.riepilogo(db, ST)
    assert any(c["nome"] == "partite_per_giornata" and c["esito"] == "ok" for c in r["controlli"])


def test_passo_dell_aggiornamento_scrive_e_non_conta_come_errore(db):
    from fanta import aggiorna
    _giornata(db, 1, n=9)                                        # giornata storta: errore dei dati, ma non passo fallito
    righe = []
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=righe.append)
    a._passo("controlli", a.controlli)
    assert a.errori == [] and any("partite_per_giornata" in r for r in righe)
    assert db.execute("SELECT esito FROM controlli WHERE nome = 'partite_per_giornata'").fetchone()[0] == "errore"
