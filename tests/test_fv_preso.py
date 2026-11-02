"""A giornata iniziata ogni scheda della Formazione porta `fv_preso` (il fantavoto preso, solo con stato «fatto»): così la
Formazione mostra il voto o «Voto in arrivo» invece di «gioca N%» per chi ha già giocato."""
import sqlite3
from datetime import datetime

from fanta import archivio, fasi
from fanta.punteggio import fantavoto
from fanta.regole import Regole

ST = "2026-27"


def test_fv_preso_solo_per_chi_ha_il_voto():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(archivio.SCHEMA)
    db.execute("INSERT INTO partite (stagione, giornata, data, casa, trasferta, giocata) VALUES (?,?,?,?,?,?)",
               (ST, 9, "2026-10-31 15:00", "inter", "milan", 1))
    db.execute("INSERT INTO partite (stagione, giornata, data, casa, trasferta, giocata) VALUES (?,?,?,?,?,?)",
               (ST, 9, "2026-11-02 20:45", "napoli", "juventus", 0))
    db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, fv_red, voto_stat, fv_stat, "
               "voto_ita, fv_ita, gol, assist) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (ST, 9, 1, "Uno", "inter", "A", 6.5, 9.5, 6.5, 9.5, 6.5, 9.5, 1, 0))
    schede = [{"id": 1, "ruolo": "A", "squadra": "inter", "titolarita": "titolare", "motivi": []},
              {"id": 2, "ruolo": "D", "squadra": "milan", "titolarita": "titolare", "motivi": []},       # stessa partita, senza voto
              {"id": 3, "ruolo": "C", "squadra": "napoli", "titolarita": "titolare", "motivi": []}]     # deve ancora giocare
    reg = Regole()
    nuove = fasi.schede_a_giornata_iniziata(schede, db, reg, ST, 9, datetime(2026, 11, 2, 13, 0))
    riga = fasi.voti_giornata(db, ST, 9, [1], reg)[0][1]
    atteso = round(fantavoto(riga, "A", reg), 2)
    assert atteso > 6.5                                                   # il gol conta: è il fantavoto, non il voto
    assert nuove[1]["stato_partita"] == "fatto" and nuove[1]["fv_preso"] == atteso
    assert nuove[2]["fv_preso"] is None and nuove[3]["stato_partita"] == "da_giocare" and nuove[3]["fv_preso"] is None
