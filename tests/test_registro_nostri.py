"""Registro dei numeri «nostri» (Fase D del piano 2026-11-06-gol-attesi-nostri, I4 dal vivo): accanto ai numeri mostrati, prima della
prima partita, si salvano anche quelli «solo Fantacalcio.it»; a giornata finita si misurano contro i mostrati (errore, punti, gol
attesi per fasce); con 8 giornate della stessa versione entro soglia, un avviso solo. Dati inventati, archivi in cartelle temporanee."""
import json
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import archivio, calcolo, consigli, nostri, registro_giornate as rg, registro_nostri as rn
from fanta import formazione as fz
from fanta.modello import Parametri

ST = "2026-27"
ORA = lambda giorno, ora, minuto=0: datetime(2026, 11, giorno, ora, minuto)  # noqa: E731


@pytest.fixture(autouse=True)
def _da_zero():
    """Motivi dei salvataggi non riusciti (in memoria) e calcoli in cache: ogni prova riparte da zero."""
    rg._tentativi.clear()
    rn._tentativi.clear()
    calcolo.cache.clear()
    yield
    rg._tentativi.clear()
    rn._tentativi.clear()
    calcolo.cache.clear()


def _partita(db, id_, giornata, data, casa, trasferta, giocata=0):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (id_, ST, giornata, data, casa, trasferta, giocata))


def _voto(db, giornata, cid, squadra, ruolo, voto, **altro):
    campi = {"stagione": ST, "giornata": giornata, "calciatore_id": cid, "nome": f"finto{cid}", "squadra": squadra, "ruolo": ruolo,
             "voto_red": voto, "gol": 0, "gol_subiti": 0, "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0,
             "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0} | altro
    db.execute(f"INSERT INTO voti ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})", tuple(campi.values()))


def _prev(righe):
    """Come la tabella di `consigli.previsioni` (e dei numeri nostri): una riga per giocatore, indice = id."""
    base = {"nome": "Finto", "squadra": "alfa", "mu_voto": 6.0, "e_gol": 0.1, "e_rigori": 0.0, "e_assist": 0.05, "minuti": 80.0,
            "stato": None, "percentuale": float("nan"), "dubbio": False}
    return pd.DataFrame([base | r for r in righe]).set_index("id")


@pytest.fixture
def giornata10(tmp_path, monkeypatch):
    """Giornata 10: due partite sabato alle 18:30 e 20:45 e un anticipo giovedì (già giocato sabato)."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    db = archivio.apri(tmp_path / "a.sqlite")
    _partita(db, 1, 10, "2026-11-07 18:30", "Alfa", "Beta")
    _partita(db, 2, 10, "2026-11-07 20:45", "Gamma", "Delta")
    _partita(db, 3, 10, "2026-11-05 20:45", "Epsilon", "Zeta", giocata=1)
    db.commit()
    return db


PREV_10 = [
    {"id": 101, "ruolo": "P", "squadra": "alfa", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.95, "mu": 5.8,
     "e_rigori": 0.0},
    {"id": 102, "ruolo": "D", "squadra": "gamma", "partita": 2, "data_partita": "2026-11-07 20:45", "p_voto": 0.42, "mu": 6.4,
     "e_rigori": 0.3},
    {"id": 103, "ruolo": "A", "squadra": "epsilon", "partita": 3, "data_partita": "2026-11-05 20:45", "p_voto": 0.9, "mu": 7.5},
]
# i numeri nostri degli stessi giocatori (più uno che il registro non ha)
NOSTRI_10 = [{**x, "mu": x["mu"] + 0.5, "e_gol": 0.2, "e_rigori": 0.1} for x in PREV_10] + [
    {"id": 199, "ruolo": "C", "squadra": "beta", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.8, "mu": 6.0}]


def _mostrate(db, regole, giornata):
    return _prev(PREV_10), giornata, True


def _nostre_righe(db, giornata=10):
    return {r["calciatore_id"]: dict(r) for r in db.execute("SELECT * FROM registro_nostri WHERE stagione = ? AND giornata = ?",
                                                            (ST, giornata))}


# ---------------------------------------------------------------- tabelle nuove negli archivi che ci sono già
def test_archivio_vecchio_col_registro_riceve_le_tabelle_nuove_senza_perdere_niente(tmp_path):
    """Gli archivi del server hanno già il registro (con dati): all'apertura ricevono le due tabelle nuove e il registro resta com'era."""
    percorso = tmp_path / "server.sqlite"
    vecchio = sqlite3.connect(percorso)
    vecchio.executescript("""
        CREATE TABLE registro_giocatori (stagione TEXT, giornata INTEGER, calciatore_id INTEGER, ruolo TEXT, squadra TEXT,
            partita_id INTEGER, p_voto REAL, mu REAL, mu_voto REAL, e_gol REAL, e_assist REAL, minuti REAL, stato TEXT,
            percentuale REAL, dubbio INTEGER, fantamedia REAL, PRIMARY KEY (stagione, giornata, calciatore_id));
        CREATE TABLE registro_giornate (stagione TEXT, giornata INTEGER, salvato TEXT, giocatori INTEGER, con_probabili INTEGER,
            misurato TEXT, voti INTEGER, sq_modello REAL, sq_fantamedia REAL, presenze INTEGER, brier_somma REAL, fasce TEXT,
            fascia_casi INTEGER, fascia_dentro INTEGER, fuori TEXT, da_avvisare TEXT, avvisati TEXT, persa TEXT,
            PRIMARY KEY (stagione, giornata));
        INSERT INTO registro_giocatori VALUES ('2026-27', 9, 101, 'A', 'alfa', 1, 0.9, 6.5, 6.1, 0.4, 0.1, 80, 'titolare', 90, 0, 7);
        INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES ('2026-27', 9, '2026-11-01T14:50:00', 1, 1);
    """)
    vecchio.commit()
    vecchio.close()
    db = archivio.apri(percorso)
    tabelle = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"registro_nostri", "registro_i4"} <= tabelle
    assert db.execute("SELECT mu FROM registro_giocatori WHERE calciatore_id = 101").fetchone()[0] == 6.5
    assert db.execute("SELECT salvato FROM registro_giornate WHERE giornata = 9").fetchone()[0] == "2026-11-01T14:50:00"
    colonne = {t: [r[1] for r in db.execute(f"PRAGMA table_info({t})")] for t in ("registro_nostri", "registro_i4")}
    assert colonne["registro_nostri"] == ["stagione", "giornata", "calciatore_id", "versione", "p_voto", "mu", "mu_voto", "e_gol",
                                          "e_rigori", "e_assist", "minuti", "e_rigori_mostrati"]
    assert colonne["registro_i4"] == ["stagione", "giornata", "versione", "misurato", "voti", "sq_nostri", "sq_mostrati", "rose",
                                      "punti_nostri", "punti_mostrati", "fasce", "fasce_mostrati", "persa", "avvisato"]
    db.close()
    db = archivio.apri(percorso)                                               # riaprire non cambia niente
    assert db.execute("SELECT COUNT(*) FROM registro_giocatori").fetchone()[0] == 1
    db.close()


# ---------------------------------------------------------------- salvataggio
def test_salva_i_nostri_numeri_insieme_ai_mostrati(giornata10, monkeypatch):
    db = giornata10
    chiamate = []

    def dal_vivo(db, giornata):
        chiamate.append(giornata)
        return _prev(NOSTRI_10)

    monkeypatch.setattr(consigli, "previsioni", _mostrate)
    monkeypatch.setattr(rn, "previsioni_dal_vivo", dal_vivo)
    rg.giro(ORA(7, 18, 21), db, lambda t, x: True)                             # dieci minuti prima: salva tutti e due
    assert db.execute("SELECT giocatori FROM registro_giornate WHERE giornata = 10").fetchone()[0] == 2
    righe = _nostre_righe(db)
    assert set(righe) == {101, 102}                         # gli stessi giocatori del registro: né l'anticipo né chi non c'è
    assert righe[102]["versione"] == nostri.VERSIONE and righe[102]["mu"] == pytest.approx(6.9) and righe[102]["p_voto"] == 0.42
    assert righe[102]["e_gol"] == 0.2 and righe[102]["e_rigori"] == 0.1 and righe[102]["e_assist"] == 0.05
    assert righe[102]["minuti"] == 80.0 and righe[102]["mu_voto"] == 6.0
    assert righe[102]["e_rigori_mostrati"] == 0.3 and righe[101]["e_rigori_mostrati"] == 0.0   # dai numeri mostrati
    assert "nome" not in righe[101]                                            # solo id e numeri
    assert chiamate == [10]
    rg.giro(ORA(7, 18, 22), db, lambda t, x: True)
    assert chiamate == [10]                                                    # una volta sola


def test_non_salva_prima_dei_mostrati_ne_dopo_l_inizio_della_prima_partita(giornata10):
    db = giornata10
    chiamate = []

    def dal_vivo(db, giornata):
        chiamate.append(giornata)
        return _prev(NOSTRI_10)

    assert rn.salva_se_serve(db, ORA(7, 18, 21), dal_vivo, _mostrate) == 0 and chiamate == []   # i mostrati non ci sono ancora
    assert rg.salva(db, ST, 10, _prev(PREV_10), True, ORA(7, 18, 22)) == 2
    assert rn.salva_se_serve(db, ORA(7, 18, 30), dal_vivo, _mostrate) == 0 and chiamate == []   # la prima partita è iniziata
    assert _nostre_righe(db) == {}
    assert rn.salva_se_serve(db, ORA(7, 18, 29), dal_vivo, _mostrate) == 2 and chiamate == [10]


def test_senza_i_mostrati_dei_rigori_salva_lo_stesso(giornata10, caplog):
    db = giornata10
    rg.salva(db, ST, 10, _prev(PREV_10), True, ORA(7, 18, 22))

    def rotte(db, regole, giornata):
        raise RuntimeError("rete")

    with caplog.at_level("WARNING"):
        assert rn.salva_se_serve(db, ORA(7, 18, 23), lambda db, g: _prev(NOSTRI_10), rotte) == 2
    assert {r["e_rigori_mostrati"] for r in _nostre_righe(db).values()} == {None}
    assert "RuntimeError" in caplog.text and "rigori" in caplog.text


# ---------------------------------------------------------------- un errore dei nostri non ferma mai il registro
def test_errore_dei_nostri_non_ferma_il_registro(giornata10, monkeypatch, caplog):
    """I numeri nostri vanno in errore per tutta la finestra: i mostrati si salvano lo stesso, nessuna eccezione esce da `giro`, il
    motivo va nel log (senza il messaggio); quando inizia la prima partita la giornata dei nostri è «persa» (non conta) e parte un
    avviso solo. La giornata si misura lo stesso per il registro dei mostrati."""
    def rotte(db, giornata):
        raise ValueError("dati segreti di un giocatore")

    monkeypatch.setattr(consigli, "previsioni", _mostrate)
    monkeypatch.setattr(rn, "previsioni_dal_vivo", rotte)
    inviati, esito = [], {"riesce": False}

    def manda(titolo, testo):
        if esito["riesce"]:
            inviati.append((titolo, testo))
        return esito["riesce"]

    db = giornata10
    with caplog.at_level("WARNING"):
        for minuto in (21, 25, 29):
            rg.giro(ORA(7, 18, minuto), db, manda)
    assert db.execute("SELECT giocatori FROM registro_giornate WHERE giornata = 10").fetchone()[0] == 2    # i mostrati ci sono
    assert _nostre_righe(db) == {}
    assert "numeri nostri" in caplog.text and "ValueError" in caplog.text and "dati segreti" not in caplog.text
    assert "test_registro_nostri.py:" in caplog.text                            # dove: file e riga
    with caplog.at_level("WARNING"):
        rg.giro(ORA(7, 18, 30), db, manda)                                      # inizia la prima partita: persa per i nostri
    riga = dict(db.execute("SELECT * FROM registro_i4 WHERE stagione = ? AND giornata = 10", (ST,)).fetchone())
    assert "ValueError" in riga["persa"] and riga["voti"] == 0 and riga["versione"] == nostri.VERSIONE
    assert db.execute("SELECT persa FROM registro_giornate WHERE giornata = 10").fetchone()[0] is None    # i mostrati non sono persi
    assert inviati == []
    esito["riesce"] = True
    for minuto in (31, 32):
        rg.giro(ORA(7, 18, minuto), db, manda)
    assert len(inviati) == 1                                                    # un avviso solo
    assert inviati[0][0] == "SchieraXI: gol attesi nostri" and "giornata 10" in inviati[0][1] and "segreti" not in inviati[0][1]
    # a giornata finita i mostrati si misurano; i nostri di quella giornata non contano
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(1,), (2,)])
    _voto(db, 10, 101, "Alfa", "P", 6.0)
    _voto(db, 10, 102, "Gamma", "D", 6.0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    db.commit()
    rg.giro(ORA(8, 22, 35), db, manda)
    assert db.execute("SELECT misurato FROM registro_giornate WHERE giornata = 10").fetchone()[0] is not None
    assert db.execute("SELECT misurato FROM registro_i4 WHERE giornata = 10").fetchone()[0] is None
    r = rn.riepilogo(db)
    assert r["giornate"] == 0 and r["per_giornata"][0]["giornata"] == 10 and "ValueError" in r["per_giornata"][0]["persa"]


def test_modulo_dei_nostri_che_non_si_carica_non_ferma_i_mostrati(giornata10, monkeypatch, caplog):
    """Anche se il modulo dei nostri non si carica (un errore nel rilascio), i mostrati si salvano e l'errore va nel log."""
    import sys

    import fanta
    monkeypatch.setattr(consigli, "previsioni", _mostrate)
    monkeypatch.delattr(fanta, "registro_nostri")
    monkeypatch.setitem(sys.modules, "fanta.registro_nostri", None)            # `import` alza ImportError
    db = giornata10
    with caplog.at_level("WARNING"):
        rg.giro(ORA(7, 18, 21), db, lambda t, x: True)
    assert db.execute("SELECT giocatori FROM registro_giornate WHERE giornata = 10").fetchone()[0] == 2
    assert "salvataggio dei numeri nostri non riuscito (ModuleNotFoundError)" in caplog.text


def test_errore_nella_misura_dei_nostri_non_ferma_la_misura_dei_mostrati(giornata10, monkeypatch, caplog):
    db = giornata10
    monkeypatch.setattr(consigli, "previsioni", _mostrate)
    monkeypatch.setattr(rn, "previsioni_dal_vivo", lambda db, g: _prev(NOSTRI_10))
    rg.giro(ORA(7, 18, 21), db, lambda t, x: True)
    assert len(_nostre_righe(db)) == 2

    def rotta(db, stagione, giornata):
        raise KeyError("x")

    monkeypatch.setattr(rn, "misura_giornata", rotta)
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(1,), (2,)])
    for cid, sq in ((101, "Alfa"), (102, "Gamma"), (900, "Beta"), (901, "Delta")):
        _voto(db, 10, cid, sq, "C", 6.0)
    db.commit()
    with caplog.at_level("WARNING"):
        rg.giro(ORA(8, 22, 35), db, lambda t, x: True)
    assert db.execute("SELECT misurato FROM registro_giornate WHERE giornata = 10").fetchone()[0] is not None
    assert "misura dei numeri nostri" in caplog.text and "KeyError" in caplog.text
    assert db.execute("SELECT COUNT(*) FROM registro_i4").fetchone()[0] == 0        # si riprova al giro dopo


# ---------------------------------------------------------------- misura a giornata finita
@pytest.fixture
def finita(giornata10):
    """Giornata 10 con mostrati e nostri salvati a mano, una partita rinviata, poi giocata con i voti (numeri da fare a mano)."""
    db = giornata10
    _partita(db, 4, 10, "2026-12-20 15:00", "Eta", "Theta")                    # rinviata: fuori dal turno
    mostrati = _prev([
        {"id": 101, "ruolo": "P", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.95, "mu": 5.8, "e_gol": 0.0},
        {"id": 102, "ruolo": "D", "partita": 2, "data_partita": "2026-11-07 20:45", "p_voto": 0.42, "mu": 6.4, "e_gol": 0.1},
        {"id": 104, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.15, "mu": 6.3, "e_gol": 0.1},
        {"id": 105, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.05, "mu": 6.0},   # senza voto
        {"id": 106, "ruolo": "A", "partita": 4, "data_partita": "2026-12-20 15:00", "p_voto": 0.9, "mu": 7.0},    # rinviata
        {"id": 107, "ruolo": "A", "partita": 2, "data_partita": "2026-11-07 20:45", "p_voto": 0.9, "mu": 7.0},    # senza nostri
    ])
    assert rg.salva(db, ST, 10, mostrati, True, ORA(7, 18, 22)) == 6
    nostri_ = [
        {"calciatore_id": 101, "mu": 6.0, "e_gol": 0.0, "e_rigori": 0.0, "e_rigori_mostrati": 0.0},
        {"calciatore_id": 102, "mu": 7.0, "e_gol": 0.08, "e_rigori": 0.0, "e_rigori_mostrati": 0.0},
        {"calciatore_id": 104, "mu": 6.0, "e_gol": 0.2, "e_rigori": 0.5, "e_rigori_mostrati": 0.2},
        {"calciatore_id": 105, "mu": 6.0, "e_gol": 0.0, "e_rigori": 0.0, "e_rigori_mostrati": 0.0},
        {"calciatore_id": 106, "mu": 7.0, "e_gol": 0.5, "e_rigori": 0.0, "e_rigori_mostrati": 0.0},
    ]
    archivio.inserisci(db, "registro_nostri", [{"stagione": ST, "giornata": 10, "versione": nostri.VERSIONE, "p_voto": 0.5,
                                                "mu_voto": 6.0, "e_assist": 0.0, "minuti": 80.0} | r for r in nostri_])
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(1,), (2,)])
    _voto(db, 10, 101, "Alfa", "P", 6.0, gol_subiti=2)                         # 4
    _voto(db, 10, 102, "Gamma", "D", 7.0, gol=1)                               # 10, un gol
    _voto(db, 10, 104, "Alfa", "C", 5.5, rig_segnati=1)                        # 8,5, un gol su rigore
    _voto(db, 10, 107, "Gamma", "A", 6.0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    db.commit()
    return db


def test_misura_errore_punti_e_fasce_a_mano(finita):
    m = rn.misura_giornata(finita, ST, 10)
    assert m["voti"] == 3                                    # chi ha preso voto e ha tutti e due i numeri: 101, 102, 104
    assert m["sq_nostri"] == pytest.approx(2.0 ** 2 + 3.0 ** 2 + 2.5 ** 2)     # (6-4)² + (7-10)² + (6-8,5)²
    assert m["sq_mostrati"] == pytest.approx(1.8 ** 2 + 3.6 ** 2 + 2.2 ** 2)   # (5,8-4)² + (6,4-10)² + (6,3-8,5)²
    # fasce dei gol attesi (rigori compresi: e_gol + 0,78 × e_rigori) contro gol veri (azione + rigori segnati)
    f = m["fasce"]
    assert len(f) == 6 and f[0] == [1, 0.0, 0] and f[1] == [1, pytest.approx(0.08), 1] and f[5] == [1, pytest.approx(0.59), 1]
    assert f[2] == f[3] == f[4] == [0, 0.0, 0]
    fm = m["fasce_mostrati"]                                 # 0,1 sta nella fascia 0,10-0,20; 0,1 + 0,78 × 0,2 = 0,256
    assert fm[0] == [1, 0.0, 0] and fm[2] == [1, pytest.approx(0.1), 1] and fm[3] == [1, pytest.approx(0.256), 1]
    assert m["rose"] == 0 and m["punti_nostri"] == 0 and m["punti_mostrati"] == 0   # giocatori troppo pochi per una rosa


def test_misura_usa_la_definizione_unica_dei_gol_attesi(finita, monkeypatch):
    """I gol attesi vengono da `nostri.gol_attesi` (con la conversione dei rigori dei parametri di ciascuno), non da un conto a parte."""
    monkeypatch.setattr(nostri, "parametri", lambda par=None: Parametri(conversione_rigori=0.1))
    m = rn.misura_giornata(finita, ST, 10)
    assert m["fasce"][3] == [1, pytest.approx(0.25), 1] and m["fasce"][5] == [0, 0.0, 0]     # 0,2 + 0,1 × 0,5 = 0,25
    assert m["fasce_mostrati"][3] == [1, pytest.approx(0.256), 1]              # i mostrati con i parametri di sempre


def _rosa_grande(db, p_portieri=3):
    """Giocatori che giocano di sicuro nelle partite 1 e 2 (p_portieri P, 10 D, 10 C, 8 A), mostrati e nostri uguali; voti veri."""
    righe, n = [], 200
    for ruolo, quanti in (("P", p_portieri), ("D", 10), ("C", 10), ("A", 8)):
        for k in range(quanti):
            n += 1
            partita, squadra = (1, "Alfa") if k % 2 else (2, "Gamma")
            righe.append({"id": n, "ruolo": ruolo, "partita": partita, "data_partita": "2026-11-07 18:30", "p_voto": 1.0,
                          "mu": 6.0 + k / 10, "mu_voto": 6.0 + k / 10})
            _voto(db, 10, n, squadra, ruolo, 6.0 + (k % 3) / 2 + (1 if ruolo == "P" else 0), gol_subiti=1 if ruolo == "P" else 0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    assert rg.salva(db, ST, 10, _prev(righe), True, ORA(7, 18, 22)) == len(righe)
    archivio.inserisci(db, "registro_nostri", [
        {"stagione": ST, "giornata": 10, "calciatore_id": r["id"], "versione": nostri.VERSIONE, "p_voto": r["p_voto"], "mu": r["mu"],
         "mu_voto": r["mu_voto"], "e_gol": 0.1, "e_rigori": 0.0, "e_assist": 0.05, "minuti": 90.0, "e_rigori_mostrati": 0.0}
        for r in righe])
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(1,), (2,)])
    db.commit()
    return [r["id"] for r in righe]


def test_punti_sulle_stesse_rose_di_i3(giornata10, monkeypatch):
    """Stesse 20 rose di I3 (stesso seme, stesso gruppo): per ognuna la migliore con i mostrati e con i nostri, punti veri di tutte e
    due. Con numeri uguali i punti sono uguali."""
    db = giornata10
    _rosa_grande(db, p_portieri=4)
    viste, vera = [], fz.migliore

    def spia(rosa, regole, simulazioni=600, **altro):
        viste.append((tuple(sorted(g.id for g in rosa)), tuple(g.mu for g in sorted(rosa, key=lambda g: g.id))))
        return vera(rosa, regole, simulazioni, **altro)

    monkeypatch.setattr(fz, "migliore", spia)
    assert rg.misura_giornata(db, ST, 10)["fascia_casi"] == 20
    i3 = [ids for ids, _ in viste]
    viste.clear()
    m = rn.misura_giornata(db, ST, 10)
    assert m["rose"] == 20 and len(viste) == 40
    assert [ids for ids, _ in viste[0::2]] == i3 and [ids for ids, _ in viste[1::2]] == i3     # mostrati, poi nostri: stesse rose
    assert len(set(i3)) > 1                                                    # rose diverse fra loro
    assert m["punti_nostri"] == pytest.approx(m["punti_mostrati"]) and m["punti_mostrati"] > 20 * 50


def test_punti_con_i_numeri_nostri(giornata10):
    """I nostri numeri cambiano la formazione: chi i nostri danno più alto va in campo, e i punti veri sono i suoi."""
    db = giornata10
    ids = _rosa_grande(db)
    # per i nostri gli attaccanti col fantavoto atteso più basso diventano i migliori: cambia chi gioca, quindi i punti veri
    db.execute("UPDATE registro_nostri SET mu = 20 - mu WHERE calciatore_id IN (SELECT calciatore_id FROM registro_giocatori "
               "WHERE ruolo = 'A')")
    db.commit()
    m = rn.misura_giornata(db, ST, 10)
    assert m["rose"] == 20 and m["punti_nostri"] != pytest.approx(m["punti_mostrati"])
    # un giocatore della rosa senza numeri nostri: quella rosa non si confronta (con 3 portieri sono in tutte le rose)
    db.execute("DELETE FROM registro_nostri WHERE calciatore_id = ?", (ids[0],))
    db.commit()
    assert rn.misura_giornata(db, ST, 10)["rose"] == 0


def test_chiude_solo_le_giornate_misurate_dal_registro_e_con_i_nostri(finita):
    db = finita
    assert rn.chiudi_giornate(db, ORA(8, 22, 35)) == []                        # il registro non l'ha ancora misurata
    rg.chiudi_giornate(db, ORA(8, 22, 35))
    assert rn.chiudi_giornate(db, ORA(8, 22, 36)) == [(ST, 10)]
    riga = dict(db.execute("SELECT * FROM registro_i4 WHERE giornata = 10").fetchone())
    assert riga["versione"] == nostri.VERSIONE and riga["misurato"] == "2026-11-08T22:36:00" and riga["voti"] == 3
    assert json.loads(riga["fasce"])[5] == [1, pytest.approx(0.59), 1] and riga["avvisato"] == 0 and riga["persa"] is None
    assert rn.chiudi_giornate(db, ORA(8, 22, 37)) == []                        # una volta sola


# ---------------------------------------------------------------- medie, verdetto, avviso
def _fasce(**per_fascia):
    f = [[0, 0.0, 0] for _ in range(6)]
    for k, v in per_fascia.items():
        f[int(k[1:])] = v
    return f


V = nostri.VERSIONE
R1 = {"versione": V, "voti": 2, "sq_nostri": 1.21, "sq_mostrati": 1.0, "rose": 20, "punti_nostri": 1300.0, "punti_mostrati": 1306.0,
      "fasce": _fasce(f0=[40, 0.8, 1], f2=[30, 4.5, 6], f5=[10, 5.0, 1]), "fasce_mostrati": _fasce(f0=[80, 2.0, 8])}
R2 = {"versione": V, "voti": 2, "sq_nostri": 2.42, "sq_mostrati": 2.0, "rose": 10, "punti_nostri": 650.0, "punti_mostrati": 647.0,
      "fasce": _fasce(f0=[20, 0.4, 3], f2=[30, 4.5, 3]), "fasce_mostrati": _fasce(f0=[40, 1.0, 4])}


def test_medie_a_mano():
    m = rn.medie([R1, R2])
    assert m["giornate"] == 2 and m["versione"] == V and m["voti"] == 4 and m["rose"] == 30
    assert m["errore_pct"] == pytest.approx(0.1)                               # radice di 3,63 / 3 meno 1
    assert m["punti"] == pytest.approx(-0.1)                                   # (1950 - 1953) / 30
    assert m["scarto_gol"] == pytest.approx(0.047, abs=1e-3)                   # fascia 0: |4 - 1,2| / 60; la 5 ha pochi casi
    assert m["gol_su_veri"] == pytest.approx(15.2 / 14, abs=1e-3)              # tutte le fasce
    assert m["scarto_gol_mostrati"] == pytest.approx(0.075, abs=1e-3) and m["gol_su_veri_mostrati"] == pytest.approx(0.25, abs=1e-3)
    assert not m["verdetto"] and m["regge"] == {"errore": None, "punti": None, "gol": None} and not m["regge_tutto"]
    vuote = rn.medie([])
    assert vuote["giornate"] == 0 and vuote["errore_pct"] is None and vuote["punti"] is None and vuote["scarto_gol"] is None


BUONA = {"versione": V, "voti": 200, "sq_nostri": 100.0, "sq_mostrati": 100.0, "rose": 20, "punti_nostri": 1300.0,
         "punti_mostrati": 1301.0, "fasce": _fasce(f0=[100, 5.0, 5], f2=[100, 15.0, 16]), "fasce_mostrati": _fasce(f0=[200, 20.0, 21])}
CATTIVA = {**BUONA, "sq_nostri": 150.0}                                         # errore del fantavoto +22%


def test_verdetto_solo_con_otto_giornate_della_stessa_versione(monkeypatch):
    monkeypatch.setattr(nostri, "VERSIONE", "3")
    tre, due = {**BUONA, "versione": "3"}, {**BUONA, "versione": "2"}
    m = rn.medie([due] + [tre] * 7)                                            # 7 della versione di oggi e 1 di prima
    assert m["giornate"] == 7 and m["versione"] == "3" and not m["verdetto"] and not m["regge_tutto"]
    m = rn.medie([due] + [tre] * 8)
    assert m["giornate"] == 8 and m["verdetto"] and m["regge"] == {"errore": True, "punti": True, "gol": True} and m["regge_tutto"]
    assert m["errore_pct"] == 0 and m["punti"] == pytest.approx(-0.05) and m["scarto_gol"] == pytest.approx(0.01)
    fuori = rn.medie([{**CATTIVA, "versione": "3"}] * 8)
    assert fuori["verdetto"] and fuori["regge"]["errore"] is False and fuori["regge"]["punti"] is True and not fuori["regge_tutto"]


def _misurata(db, g, riga, versione=None):
    db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, misurato, voti, sq_nostri, sq_mostrati, rose, punti_nostri, "
               "punti_mostrati, fasce, fasce_mostrati, avvisato) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
               (ST, g, versione or riga["versione"], f"2026-11-{g:02d}T12:00:00", riga["voti"], riga["sq_nostri"], riga["sq_mostrati"],
                riga["rose"], riga["punti_nostri"], riga["punti_mostrati"], json.dumps(riga["fasce"]), json.dumps(riga["fasce_mostrati"])))
    db.commit()


def test_verdetto_dall_archivio_riparte_con_la_versione_nuova(tmp_path, monkeypatch):
    db = archivio.apri(tmp_path / "r.sqlite")
    monkeypatch.setattr(nostri, "VERSIONE", "3")
    _misurata(db, 1, BUONA, "2")
    for g in range(2, 9):
        _misurata(db, g, BUONA, "3")
    r = rn.riepilogo(db)
    assert r["versione"] == "3" and r["giornate"] == 7 and not r["verdetto"]
    _misurata(db, 9, BUONA, "3")
    assert rn.riepilogo(db)["regge_tutto"]
    monkeypatch.setattr(nostri, "VERSIONE", "4")                               # versione nuova: si riparte da zero giornate
    assert rn.riepilogo(db)["giornate"] == 0


def test_avviso_una_volta_quando_regge(tmp_path):
    db = archivio.apri(tmp_path / "r.sqlite")
    inviati, esito = [], {"riesce": True}

    def manda(titolo, testo):
        if esito["riesce"]:
            inviati.append((titolo, testo))
        return esito["riesce"]

    for g in range(1, 8):
        _misurata(db, g, BUONA)
        assert rn.avvisa(db, manda) is False                                   # meno di 8 giornate: niente
    for g in range(8, 16):
        _misurata(db, g, CATTIVA)
    assert rn.avvisa(db, manda) is False and inviati == []                     # fuori soglia: non avvisa
    for g in range(16, 24):
        _misurata(db, g, BUONA)
    esito["riesce"] = False
    assert rn.avvisa(db, manda) is False and inviati == []                     # non partito: si riprova
    esito["riesce"] = True
    assert rn.avvisa(db, manda) is True and len(inviati) == 1
    titolo, testo = inviati[0]
    assert titolo == "SchieraXI: gol attesi nostri"
    assert f"versione {V}" in testo and "Fase G1" in testo and "2026-11-06-gol-attesi-nostri" in testo
    assert "0,0%" in testo and "−0,05" in testo and "0,010" in testo and "finto" not in testo
    assert rn.avvisa(db, manda) is False                                       # una volta sola
    _misurata(db, 24, BUONA)
    assert rn.avvisa(db, manda) is False and len(inviati) == 1                 # anche se continua a reggere


def test_avviso_di_nuovo_con_una_versione_nuova(tmp_path, monkeypatch):
    db = archivio.apri(tmp_path / "r.sqlite")
    for g in range(1, 9):
        _misurata(db, g, BUONA)
    assert rn.avvisa(db, lambda t, x: True) is True
    monkeypatch.setattr(nostri, "VERSIONE", V + "-nuova")
    for g in range(9, 17):
        _misurata(db, g, BUONA, V + "-nuova")
    assert rn.avvisa(db, lambda t, x: True) is True


# ---------------------------------------------------------------- Stato dei dati
def test_riepilogo_senza_nomi(finita):
    db = finita
    rg.chiudi_giornate(db, ORA(8, 22, 35))
    rn.chiudi_giornate(db, ORA(8, 22, 36))
    _partita(db, 11, 11, "2026-11-14 18:30", "Alfa", "Gamma")
    archivio.inserisci(db, "registro_nostri", [{"stagione": ST, "giornata": 11, "calciatore_id": 101, "versione": V, "p_voto": 0.9,
                                                "mu": 6.0, "mu_voto": 6.0, "e_gol": 0.0, "e_rigori": 0.0, "e_assist": 0.0,
                                                "minuti": 90.0, "e_rigori_mostrati": 0.0}])
    db.commit()
    r = rn.riepilogo(db)
    assert r["versione"] == V and r["finestra"] == 8 and r["soglie"] == {"errore": 0.01, "punti": -0.3, "scarto_gol": 0.03}
    assert [(g["giornata"], g["giocatori"]) for g in r["per_giornata"]] == [(11, 1), (10, 5)]       # dalla più recente
    g11, g10 = r["per_giornata"]
    assert g11["misurato"] is None and g11["errore_pct"] is None and g11["persa"] is None              # salvata, non ancora misurata
    assert g10["misurato"] is not None and g10["voti"] == 3 and g10["versione"] == V
    assert g10["errore_pct"] == pytest.approx((19.25 / 21.04) ** 0.5 - 1, abs=1e-4)
    assert r["giornate"] == 1 and not r["verdetto"]
    testo = json.dumps(r)
    assert "finto" not in testo and "Finto" not in testo and "calciatore" not in testo and "nome" not in testo
    assert "101" not in testo                                                  # nessun id di giocatore


# ---------------------------------------------------------------- con le previsioni VERE dei due modelli
SQUADRE = ("alfa", "beta", "gamma", "delta")
TURNI = ((("alfa", "beta"), ("gamma", "delta")), (("alfa", "gamma"), ("beta", "delta")), (("alfa", "delta"), ("beta", "gamma")),
         (("beta", "alfa"), ("delta", "gamma")), (("gamma", "alfa"), ("delta", "beta")))
RUOLI_SQUADRA = ("P", "D", "D", "C", "C", "A")


@pytest.fixture
def campionato_finto(tmp_path, monkeypatch):
    """Un campionato inventato: 4 squadre da 6 giocatori, giornate 1-4 giocate con i voti (anche rigori), la 5 sabato 7/11 alle
    18:30 e alle 20:45 con le probabili formazioni. Nessun dato vero, nessuna sostituzione delle previsioni."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    db = archivio.apri(tmp_path / "campionato.sqlite")
    giocatori = [(100 * (s + 1) + k, squadra, ruolo) for s, squadra in enumerate(SQUADRE) for k, ruolo in enumerate(RUOLI_SQUADRA)]
    archivio.inserisci(db, "calciatori", [{"id": i, "nome": f"Finto {i}", "ruolo": r, "squadra": sq[:3].upper(), "squadra_slug": sq,
                                           "quotazione": 10} for i, sq, r in giocatori])
    for g, turno in enumerate(TURNI, start=1):
        giocata = g <= 4
        for k, (casa, trasferta) in enumerate(turno):
            data = f"2026-10-{3 + 7 * (g - 1):02d} 15:00" if giocata else f"2026-11-07 {('18:30', '20:45')[k]}"
            archivio.inserisci(db, "partite", [{"id": 10 * g + k, "stagione": ST, "giornata": g, "data": data, "casa": casa,
                                                "trasferta": trasferta, "gol_casa": 1 + g % 2 if giocata else None,
                                                "gol_trasferta": 1 if giocata else None, "giocata": int(giocata), "understat_id": None}])
        if giocata:
            for i, sq, r in giocatori:
                _voto(db, g, i, sq, r, 6.0 + (i % 3) / 2, gol=int(r == "A" and g % 2 == 1), rig_segnati=int(r == "C" and g == 2))
    archivio.inserisci(db, "probabili", [{"stagione": ST, "giornata": 5, "fonte": "fantacalcio", "calciatore_id": i, "squadra": sq,
                                          "partita_id": None, "stato": "titolare", "percentuale": 80.0, "in_dubbio": 0, "diffidato": 0,
                                          "nota": None, "rilevato": "2026-11-07T17:00:00"} for i, sq, _ in giocatori])
    db.commit()
    return db, {i for i, _, _ in giocatori}


def test_giro_salva_i_due_numeri_con_le_previsioni_vere(campionato_finto, caplog):
    db, ids = campionato_finto
    with caplog.at_level("WARNING"):
        rg.giro(ORA(7, 18, 22), db, lambda t, x: True)
    assert "non riuscito" not in caplog.text and "mancano" not in caplog.text
    righe = _nostre_righe(db, 5)
    assert set(righe) == ids
    for r in righe.values():
        assert {k for k, v in r.items() if v is None} == set(), r                # ogni colonna ha un valore
        assert r["versione"] == nostri.VERSIONE and 0 < r["p_voto"] <= 1 and 2 < r["mu"] < 15 and 4 < r["mu_voto"] < 9
        assert r["e_gol"] >= 0 and r["e_rigori"] >= 0 and r["e_assist"] >= 0 and 0 < r["minuti"] <= 95
        assert r["e_rigori_mostrati"] >= 0
    mostrati = {r["calciatore_id"]: r["mu"] for r in db.execute("SELECT calciatore_id, mu FROM registro_giocatori WHERE giornata = 5")}
    assert set(mostrati) == ids
