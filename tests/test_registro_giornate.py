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


# ---------------------------------------------------------------- compito 2: misura a giornata finita
def _gioca(db, *partite):
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(p,) for p in partite])


@pytest.fixture
def finita(giornata10):
    """Giornata 10 salvata con cinque giocatori, una partita rinviata a dicembre, poi giocata con i voti (numeri da fare a mano)."""
    db = giornata10
    _partita(db, 4, 10, "2026-12-20 15:00", "Eta", "Theta")                    # rinviata: fuori dal turno
    prev = _prev([
        {**PREV_10[0]},                                                         # P, p 0,95, mu 5,8, fantamedia 6,25
        {**PREV_10[1]},                                                         # D, p 0,42, mu 6,4, fantamedia 7
        {"id": 104, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.15, "mu": 6.3},   # senza fantamedia
        {"id": 105, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.05, "mu": 6.0},
        {"id": 106, "ruolo": "A", "partita": 4, "data_partita": "2026-12-20 15:00", "p_voto": 0.9, "mu": 7.0},    # partita rinviata
    ])
    assert rg.salva(db, ST, 10, prev, True, ORA(7, 18, 22)) == 5
    _gioca(db, 1, 2)
    _voto(db, 10, 101, "Alfa", "P", 6.0, gol_subiti=2)                         # 4
    _voto(db, 10, 102, "Gamma", "D", 7.0, gol=1)                               # 10
    _voto(db, 10, 104, "Alfa", "C", 5.5)                                       # 5,5
    _voto(db, 10, 900, "Beta", "C", 6.0)                                       # altre squadre: fuori dal registro
    _voto(db, 10, 901, "Delta", "C", 6.0)
    db.commit()
    return db


def test_misura_errore_brier_e_fasce_a_mano(finita):
    m = rg.misura_giornata(finita, ST, 10)
    assert m["voti"] == 3 and m["presenze"] == 4                               # il rinviato non conta
    assert m["sq_modello"] == pytest.approx(1.8 ** 2 + 3.6 ** 2 + 0.8 ** 2)     # (5,8-4)² + (6,4-10)² + (6,3-5,5)²
    assert m["brier_somma"] == pytest.approx(0.05 ** 2 + 0.58 ** 2 + 0.85 ** 2 + 0.05 ** 2)
    fasce = m["fasce"]
    assert len(fasce) == 10 and fasce[9] == [1, 0.95, 1] and fasce[4] == [1, 0.42, 1]
    assert fasce[1] == [1, 0.15, 1] and fasce[0] == [1, 0.05, 0] and fasce[5] == [0, 0, 0]


def test_senza_fantamedia_vale_sei(finita):
    m = rg.misura_giornata(finita, ST, 10)
    assert m["sq_fantamedia"] == pytest.approx(2.25 ** 2 + 3.0 ** 2 + 0.5 ** 2)  # (6,25-4)² + (7-10)² + (6-5,5)²


def test_partita_rinviata_non_tiene_aperta_la_giornata(finita):
    assert rg.da_misurare(finita, ORA(8, 22, 35)) == [(ST, 10)]


def test_si_misura_solo_a_giornata_finita_e_con_i_voti(finita):
    db = finita
    # ultima partita del turno sabato 20:45, finita 22:35: si misura dopo 24 ore
    assert rg.da_misurare(db, ORA(8, 22, 34)) == []
    assert rg.da_misurare(db, ORA(8, 22, 35)) == [(ST, 10)]
    db.execute("DELETE FROM voti WHERE squadra = 'Delta'")                     # una squadra senza voti: si aspetta fino a 72 ore
    assert rg.da_misurare(db, ORA(8, 22, 35)) == []
    assert rg.da_misurare(db, ORA(10, 22, 35)) == [(ST, 10)]
    m = rg.misura_giornata(db, ST, 10)
    assert m["presenze"] == 3 and m["voti"] == 2                               # la partita senza voti non conta
    db.execute("UPDATE partite SET giocata = 0 WHERE id = 2")                  # turno non finito: mai
    assert rg.da_misurare(db, ORA(20, 12)) == []


def _rosa_intera(db, delta: float):
    """25 giocatori (3 P, 8 D, 8 C, 6 A) che giocano di sicuro, nelle partite 1 e 2: fantavoto vero = atteso + `delta`."""
    righe, n = [], 200
    for ruolo, quanti in (("P", 3), ("D", 8), ("C", 8), ("A", 6)):
        for k in range(quanti):
            n += 1
            partita, squadra = (1, "Alfa") if k % 2 else (2, "Gamma")
            righe.append({"id": n, "ruolo": ruolo, "partita": partita, "data_partita": "2026-11-07 18:30", "p_voto": 1.0,
                          "mu": 6.0 + k / 10, "mu_voto": 6.0 + k / 10})
            # i portieri prendono un gol: niente bonus d'imbattibilità, fantavoto = voto - 1
            _voto(db, 10, n, squadra, ruolo, 6.0 + k / 10 + delta + (1 if ruolo == "P" else 0), gol_subiti=1 if ruolo == "P" else 0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    assert rg.salva(db, ST, 10, _prev(righe), True, ORA(7, 18, 22)) == 25
    _gioca(db, 1, 2)
    db.commit()


def test_fascia_su_rose_estratte_a_sorte_e_ripetibile(giornata10):
    db = giornata10
    _rosa_intera(db, 0.0)
    m = rg.misura_giornata(db, ST, 10)
    assert m["fascia_casi"] == 20 and m["fascia_dentro"] == 20                 # punti veri vicini agli attesi: sempre dentro
    assert rg.misura_giornata(db, ST, 10) == m                                 # stesso seme, stessi numeri


def test_fascia_mancata_se_i_punti_veri_sono_lontani(giornata10):
    db = giornata10
    _rosa_intera(db, 3.0)                                                      # 3 punti in più a testa: 33 sopra gli attesi
    m = rg.misura_giornata(db, ST, 10)
    assert m["fascia_casi"] == 20 and m["fascia_dentro"] == 0
