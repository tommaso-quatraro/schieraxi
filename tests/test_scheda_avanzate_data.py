"""Scheda del giocatore: le statistiche avanzate dicono fino a quale giorno arrivano i dati della fonte (#862).

Con la fonte ferma (Understat dal 12/11/2026, #756) i numeri restavano quelli dell'ultima partita letta, senza una data: il server
manda il giorno dell'ultima partita della stagione di cui l'archivio ha le statistiche, e web e iPhone lo scrivono. Dati inventati.
"""
import pytest

from fanta import archivio, scheda

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


def test_giocatore_senza_abbinamento_niente_statistiche_avanzate(db):
    db.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug) VALUES (9, 'Neri', 'D', 'Genoa', 'genoa')")
    _partita(db, 1, "2026-10-26 20:45:00", ST, 1, 70)
    assert scheda.scheda(db, 9, ST)["avanzate"] is None
