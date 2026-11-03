"""Il promemoria sa se hai già schierato: non disturba chi ha già la formazione a posto, insiste se un titolare è saltato."""
import sqlite3
from datetime import datetime

import pandas as pd

from fanta import consigli, lega, notifiche, scelte
from fanta.regole import Regole

ST = "2026-27"
ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10)])], "Mia")
OPZ = {"cambi": True, "promemoria_60": True, "promemoria_15": True}


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, "2026-10-28 18:30", 0), (ST, 9, "2026-10-29 20:45", 0)])
    return db


def _scena(tmp_path, monkeypatch, stato="titolare", salva=True, tipo="manuale"):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [{"id": 1, "nome": "Castro", "titolarita": "titolare", "dubbio": False}]})
    prev = pd.DataFrame([{"nome": "Castro", "stato": stato, "percentuale": 80.0, "dubbio": False}], index=[1])
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    fs = tmp_path / "scelte.json"
    if salva:
        scelte.salva(ST, 9, [1], "4-3-3", fs, tipo)
    mandati = []
    return fs, mandati, (lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo)) or True), prev


def test_non_disturba_chi_ha_gia_schierato(tmp_path, monkeypatch):
    for tipo in ("manuale", "consigliata"):
        fs, mandati, manda, _ = _scena(tmp_path, monkeypatch, tipo=tipo)
        f, db = tmp_path / f"n-{tipo}.json", _db()
        assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 35), f, manda, OPZ, fs) == []
        assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 18, 20), f, manda, OPZ, fs) == []
        assert mandati == []


def test_normale_se_non_hai_schierato_o_c_e_solo_la_copia_automatica(tmp_path, monkeypatch):
    fs, mandati, manda, _ = _scena(tmp_path, monkeypatch, salva=False)
    assert len(notifiche.promemoria(_db(), Regole(), ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "a.json", manda, OPZ, fs)) == 1
    fs, mandati, manda, _ = _scena(tmp_path, monkeypatch, tipo="automatica")
    assert len(notifiche.promemoria(_db(), Regole(), ROSE, datetime(2026, 10, 28, 18, 20), tmp_path / "b.json", manda, OPZ, fs)) == 1
    assert "L'hai inserita su Leghe?" in mandati[0][1]


def test_insiste_se_dopo_aver_schierato_un_titolare_salta(tmp_path, monkeypatch):
    fs, mandati, manda, _ = _scena(tmp_path, monkeypatch, stato="infortunato")
    f, db = tmp_path / "n.json", _db()
    assert len(notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 35), f, manda, OPZ, fs)) == 1
    assert "Hai già schierato, ma Castro" in mandati[0][1] and "18:30" in mandati[0][1]
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 45), f, manda, OPZ, fs) == []   # non ripetuto nella finestra


def test_tace_e_poi_parla_se_cambia_qualcosa(tmp_path, monkeypatch):
    fs, mandati, manda, prev = _scena(tmp_path, monkeypatch)
    f, db = tmp_path / "n.json", _db()
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 35), f, manda, OPZ, fs) == []
    prev.loc[1, "stato"] = "squalificato"
    assert len(notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 40), f, manda, OPZ, fs)) == 1
    assert len(mandati) == 1


def test_nelle_ore_tranquille_resta_da_mandare(tmp_path, monkeypatch):
    fs, mandati, manda, _ = _scena(tmp_path, monkeypatch, stato="infortunato")
    f, db = tmp_path / "n.json", _db()
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 35), f, lambda *a, **k: False, OPZ, fs) == []
    assert len(notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 40), f, manda, OPZ, fs)) == 1
