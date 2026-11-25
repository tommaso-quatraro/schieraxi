"""Scheda del giocatore: le statistiche avanzate dicono fino a quale giorno arrivano i dati della fonte (#862).

Con la fonte ferma (Understat dal 12/11/2026, #756) i numeri restavano quelli dell'ultima partita letta, senza una data: il server
manda il giorno dell'ultima partita della stagione di cui l'archivio ha le statistiche, e web e iPhone lo scrivono. Dati inventati.
"""
import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, scheda, server
from fanta.regole import Regole

ST = "2026-27"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    d.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug) VALUES (7, 'Retalli', 'A', 'Genoa', 'genoa')")
    d.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug) VALUES (8, 'Gallo', 'C', 'Como', 'como')")
    d.execute("INSERT INTO understat_giocatori (id, nome, calciatore_id, abbinamento) VALUES (70, 'Mauro Retalli', 7, 'squadra')")
    d.execute("INSERT INTO understat_giocatori (id, nome, calciatore_id, abbinamento) VALUES (80, 'Piero Gallo', 8, 'squadra')")
    yield d
    d.close()


def _partita(db, pid, data, stagione=ST, giocata=1, *giocatori):
    db.execute("INSERT INTO partite_understat (id, stagione, data, casa, trasferta, giocata, scaricata) VALUES (?, ?, ?, 'genoa', 'como', ?, ?)",
               (pid, stagione, data, giocata, int(bool(giocatori))))
    for g in giocatori:
        db.execute("INSERT INTO prestazioni (understat_partita, understat_giocatore, squadra, minuti, xg, xa, gol, assist) "
                   "VALUES (?, ?, 'genoa', 90, 0.4, 0.1, 0, 0)", (pid, g))


def test_la_data_e_l_ultima_partita_letta_della_fonte_anche_se_lui_non_ha_giocato(db):
    _partita(db, 1, "2026-10-26 20:45:00", ST, 1, 70, 80)
    _partita(db, 2, "2026-11-09 15:00:00", ST, 1, 80)                 # lui è fermo, la fonte no: conta la partita degli altri
    _partita(db, 3, "2026-11-22 18:00:00", ST, 1)                     # giocata ma mai letta (fonte ferma): non conta
    _partita(db, 4, "2027-05-30 20:45:00", ST, 0)                     # da giocare
    _partita(db, 5, "2026-05-24 20:45:00", "2025-26", 1, 70)          # stagione passata
    s = scheda.scheda(db, 7, ST)
    assert s["avanzate"]["minuti"] == 90
    assert s["avanzate"]["dati_fino_al"] == "2026-11-09"


def test_senza_partite_lette_nella_stagione_la_data_e_vuota(db):
    _partita(db, 5, "2026-05-24 20:45:00", "2025-26", 1, 70)
    s = scheda.scheda(db, 7, ST)
    assert s["avanzate"]["dati_fino_al"] is None


def test_rendimento_conta_solo_le_partite_con_voto_fino_al_giorno_della_fonte(tmp_path, monkeypatch):
    """«Gol e assist rispetto alle occasioni» divide gol meno gol attesi (della fonte, fermi) per le partite con voto: con i voti
    che continuano ad arrivare il numero calava da solo (da «è probabile che cali» a «In linea») mentre la riga diceva sempre lo
    stesso giorno. Si contano solo le partite con voto giocate entro `dati_fino_al`, la finestra della fonte."""
    d = archivio.apri(tmp_path / "fanta.sqlite")
    d.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug) VALUES (7, 'Retalli', 'A', 'Genoa', 'genoa')")
    d.execute("INSERT INTO understat_giocatori (id, nome, calciatore_id, abbinamento) VALUES (70, 'Mauro Retalli', 7, 'squadra')")
    for g, giorno in ((1, "2026-10-25"), (2, "2026-11-01"), (3, "2026-11-08"), (4, "2026-11-22"), (5, "2026-11-29")):
        d.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, 'genoa', 'como', 1)",
                  (g, ST, g, f"{giorno} 15:00"))
        d.execute("INSERT INTO voti (stagione, giornata, calciatore_id, squadra, voto_red, fv_red, gol, assist, ammonizioni, espulsioni, "
                  "gol_subiti, rig_segnati, rig_sbagliati, rig_parati, autogol, subentrato, sostituito) "
                  "VALUES (?, ?, 7, 'genoa', 6.5, 6.5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)", (ST, g))
    for g, giorno in ((1, "2026-10-25"), (2, "2026-11-01"), (3, "2026-11-08")):     # la fonte si è fermata dopo la giornata 3
        d.execute("INSERT INTO partite_understat (id, stagione, data, casa, trasferta, giocata, scaricata) "
                  "VALUES (?, ?, ?, 'genoa', 'como', 1, 1)", (100 + g, ST, f"{giorno} 14:00:00"))
        d.execute("INSERT INTO prestazioni (understat_partita, understat_giocatore, squadra, minuti, xg, xa, gol, assist) "
                  "VALUES (?, 70, 'genoa', 90, 0.2, 0.0, 1, 0)", (100 + g,))
    d.commit()
    d.close()
    r = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3})
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(server, "_regole", lambda ctx: r)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda *a, **k: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda *a, **k: (_ for _ in ()).throw(ValueError("niente previsioni nel test")))
    s = TestClient(server.app, headers={"X-Fanta": "1"}).get("/api/giocatore/7").json()
    assert s["avanzate"]["dati_fino_al"] == "2026-11-08" and s["stagione"]["con_voto"] == 5
    atteso = round(r.bonus.gol["A"] * (3 - 0.6) / 3, 2)                     # 3 partite con voto entro l'8/11, non 5
    assert s["rendimento"]["sovra_rendimento"] == atteso
    assert s["rendimento"]["gol_meno_xg"] == 2.4


def test_giocatore_senza_abbinamento_niente_statistiche_avanzate(db):
    db.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug) VALUES (9, 'Neri', 'D', 'Genoa', 'genoa')")
    _partita(db, 1, "2026-10-26 20:45:00", ST, 1, 70)
    assert scheda.scheda(db, 9, ST)["avanzate"] is None
