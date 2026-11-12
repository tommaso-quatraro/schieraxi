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


def _partita_con_voti(db, pid=900, gol=(2, 1), giornata=11):
    """Casa 2 - 1 ospite: il primo gol di casa su azione, il secondo un'autorete dell'ospite; il gol dell'ospite su rigore. Due
    portieri di casa (cambio) che insieme ne prendono 1, il portiere ospite ne prende 2."""
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, gol_casa, gol_trasferta, giocata) "
               "VALUES (?, ?, ?, '2026-11-08 15:00', 'casa', 'ospite', ?, ?, 1)", (pid, ST, giornata, *gol))
    voti = [(1, "casa", "A", 1, 0, 0, 0), (2, "casa", "P", 0, 1, 0, 0), (3, "casa", "P", 0, 0, 0, 0),
            (4, "ospite", "D", 0, 0, 1, 0), (5, "ospite", "A", 0, 0, 0, 1), (6, "ospite", "P", 0, 2, 0, 0)]
    for cid, sq, ruolo, g, subiti, autogol, rigori in voti:
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, gol_subiti, autogol, "
                   "rig_segnati) VALUES (?, ?, ?, 'x', ?, ?, 6.0, ?, ?, ?, ?)", (ST, giornata, cid, sq, ruolo, g, subiti, autogol, rigori))


def test_gol_dei_voti_uguali_al_risultato(db):
    _partita_con_voti(db)
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, gol_casa, gol_trasferta, giocata) "
               "VALUES (901, ?, 11, '2026-11-08 18:00', 'x', 'y', 3, 0, 1)", (ST,))          # voti non ancora arrivati: non conta
    e = _esiti(db)["gol_dei_voti"]
    assert (e["esito"], e["valore"]) == ("ok", 0.0) and "1 partite" in e["dettaglio"]
    db.execute("UPDATE voti SET gol = 0 WHERE calciatore_id = 1")                               # un gol perso dalla pagina
    e = _esiti(db)["gol_dei_voti"]
    assert (e["esito"], e["valore"]) == ("errore", 1.0) and "g11 casa-ospite 2-1 (nei voti 1-1)" in e["dettaglio"]


def test_gol_subiti_dei_portieri_uguali_al_risultato(db):
    _partita_con_voti(db)
    e = _esiti(db)["gol_subiti_portieri"]
    assert (e["esito"], e["valore"]) == ("ok", 0.0)
    db.execute("UPDATE voti SET gol_subiti = 0 WHERE calciatore_id = 6")
    e = _esiti(db)["gol_subiti_portieri"]
    assert (e["esito"], e["valore"]) == ("errore", 1.0) and "g11 casa-ospite 2-1 (portieri 0-1)" in e["dettaglio"]


def test_i_controlli_nuovi_contano_come_errori_della_corsa(db):
    """Sui dati veri di oggi danno zero: un valore diverso è un errore del passo che ha scritto i dati, e la corsa lo conta (riga
    generale, registro, salute). Quelli di prima restano solo da guardare (test sopra)."""
    from fanta import aggiorna
    _partita_con_voti(db)
    db.execute("UPDATE voti SET gol = 0 WHERE calciatore_id = 1")
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)
    a._passo("controlli", a.controlli)
    assert len(a.errori) == 1 and a.errori[0].startswith("controlli: gol_dei_voti: 1 partite su 1")


def test_passo_dell_aggiornamento_scrive_e_non_conta_come_errore(db):
    from fanta import aggiorna
    _giornata(db, 1, n=9)                                        # giornata storta: errore dei dati, ma non passo fallito
    righe = []
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=righe.append)
    a._passo("controlli", a.controlli)
    assert a.errori == [] and any("partite_per_giornata" in r for r in righe)
    assert db.execute("SELECT esito FROM controlli WHERE nome = 'partite_per_giornata'").fetchone()[0] == "errore"
