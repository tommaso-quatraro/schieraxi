"""Registro delle giornate (L1 di #165): numeri mostrati prima della prima partita, misura a giornata finita, medie e avviso.
Solo dati inventati: squadre e giocatori finti, archivio in una cartella temporanea."""
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import archivio, consigli, registro_giornate as rg
from fanta.regole import Regole

ST = "2026-27"
ORA = lambda giorno, ora, minuto=0: datetime(2026, 11, giorno, ora, minuto)  # noqa: E731


def _partita(db, id_, giornata, data, casa, trasferta, giocata=0):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (id_, ST, giornata, data, casa, trasferta, giocata))


def _voto(db, giornata, cid, squadra, ruolo, voto, **altro):
    campi = {"stagione": ST, "giornata": giornata, "calciatore_id": cid, "nome": f"finto{cid}", "squadra": squadra, "ruolo": ruolo,
             "voto_red": voto, "gol": 0, "gol_subiti": 0, "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0,
             "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0} | altro
    db.execute(f"INSERT INTO voti ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})", tuple(campi.values()))


def _prev(righe):
    """Come la tabella di `consigli.previsioni`: una riga per giocatore, indice = id."""
    base = {"nome": "Finto", "squadra": "alfa", "mu_voto": 6.0, "e_gol": 0.1, "e_assist": 0.05, "minuti": 80.0, "stato": None,
            "percentuale": float("nan"), "dubbio": False}
    return pd.DataFrame([base | r for r in righe]).set_index("id")


@pytest.fixture
def giornata10(tmp_path, monkeypatch):
    """Giornata 10: due partite sabato alle 18:30 e 20:45 e un anticipo giovedì (già giocato sabato). Voti finti delle giornate 8 e 9."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    db = archivio.apri(tmp_path / "a.sqlite")
    _partita(db, 1, 10, "2026-11-07 18:30", "Alfa", "Beta")
    _partita(db, 2, 10, "2026-11-07 20:45", "Gamma", "Delta")
    _partita(db, 3, 10, "2026-11-05 20:45", "Epsilon", "Zeta", giocata=1)
    _voto(db, 8, 101, "Alfa", "P", 6.0)                       # imbattuto: 6 + 1 = 7
    _voto(db, 9, 101, "Alfa", "P", 6.5, gol_subiti=1)          # 6,5 - 1 = 5,5  -> fantamedia 6,25
    _voto(db, 9, 102, "Gamma", "D", 6.0, assist=1)             # 7
    _voto(db, 9, 103, "Epsilon", "A", None)                    # senza voto: non conta
    db.commit()
    return db


PREV_10 = [
    {"id": 101, "ruolo": "P", "squadra": "alfa", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.95, "mu": 5.8,
     "stato": "titolare", "percentuale": 95.0},
    {"id": 102, "ruolo": "D", "squadra": "gamma", "partita": 2, "data_partita": "2026-11-07 20:45", "p_voto": 0.42, "mu": 6.4,
     "dubbio": True},
    {"id": 103, "ruolo": "A", "squadra": "epsilon", "partita": 3, "data_partita": "2026-11-05 20:45", "p_voto": 0.9, "mu": 7.5},
]


# ---------------------------------------------------------------- compito 1: tabelle e salvataggio
def test_archivio_vecchio_riceve_le_tabelle_senza_perdere_niente(tmp_path):
    vecchio = sqlite3.connect(tmp_path / "v.sqlite")
    vecchio.execute("CREATE TABLE calciatori (id INTEGER PRIMARY KEY, nome TEXT)")
    vecchio.execute("INSERT INTO calciatori VALUES (7, 'Giocatore Finto')")
    vecchio.commit()
    vecchio.close()
    db = archivio.apri(tmp_path / "v.sqlite")
    tabelle = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"registro_giocatori", "registro_giornate"} <= tabelle
    assert db.execute("SELECT nome FROM calciatori WHERE id = 7").fetchone()[0] == "Giocatore Finto"


def test_salva_i_numeri_mostrati_una_volta_sola(giornata10):
    db = giornata10
    adesso = ORA(7, 18, 22)
    assert rg.salva(db, ST, 10, _prev(PREV_10), True, adesso) == 2           # l'anticipo è già giocato: non si salva
    righe = {r["calciatore_id"]: dict(r) for r in db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = 10", (ST,))}
    assert set(righe) == {101, 102}
    assert righe[101]["p_voto"] == 0.95 and righe[101]["mu"] == 5.8 and righe[101]["fantamedia"] == 6.25
    assert righe[101]["stato"] == "titolare" and righe[101]["percentuale"] == 95.0 and righe[101]["partita_id"] == 1
    assert righe[102]["fantamedia"] == 7.0 and righe[102]["percentuale"] is None and righe[102]["dubbio"] == 1
    assert "nome" not in righe[101]                                            # solo numeri e id: niente nomi nel registro
    g = dict(db.execute("SELECT * FROM registro_giornate WHERE stagione = ? AND giornata = 10", (ST,)).fetchone())
    assert g["giocatori"] == 2 and g["con_probabili"] == 1 and g["salvato"] == "2026-11-07T18:22:00" and g["misurato"] is None
    altri = _prev([{**PREV_10[0], "p_voto": 0.1}])
    assert rg.salva(db, ST, 10, altri, True, ORA(7, 18, 25)) == 0              # già salvata: resta quella di prima
    assert db.execute("SELECT p_voto FROM registro_giocatori WHERE calciatore_id = 101").fetchone()[0] == 0.95


def test_fantamedia_solo_con_le_giornate_di_prima(giornata10):
    db = giornata10
    _voto(db, 10, 101, "Alfa", "P", 9.0)                                       # la giornata stessa non conta
    assert rg.fantamedie(db, ST, 10, Regole()) == {101: 6.25, 102: 7.0}


def test_salva_solo_negli_ultimi_dieci_minuti_prima_della_prima_partita(giornata10, tmp_path, monkeypatch):
    chiamate = []

    def previsioni(db, regole, giornata):
        chiamate.append((regole, giornata))
        return _prev(PREV_10), giornata, True

    db = giornata10
    assert rg.salva_se_serve(db, ORA(7, 18, 19), previsioni) == 0 and chiamate == []
    assert rg.salva_se_serve(db, ORA(7, 18, 20), previsioni) == 2
    assert chiamate == [(Regole(), 10)]                                        # regole classiche, mai quelle di una lega
    assert rg.salva_se_serve(db, ORA(7, 18, 21), previsioni) == 0 and len(chiamate) == 1
    # servizio fermo per tutta la finestra: dopo l'inizio non si salva più niente
    db.execute("DELETE FROM registro_giornate")
    db.execute("DELETE FROM registro_giocatori")
    assert rg.salva_se_serve(db, ORA(7, 18, 30), previsioni) == 0 and len(chiamate) == 1
