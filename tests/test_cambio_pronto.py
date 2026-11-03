"""Avviso «cambio pronto»: un tuo titolare è fuori o in panchina e l'avviso dice con chi sostituirlo."""
import sqlite3
from datetime import datetime

import pandas as pd

from fanta import consigli, da_fare, lega, notifiche, scelte
from fanta.regole import Regole

ST = "2026-27"
ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10), lega.GiocatoreRosa(2, "Bonny", "A", "PAR", 8)])], "Mia")
ADESSO = datetime(2026, 10, 27, 9, 0)


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, "2026-10-28 18:30", 0), (ST, 9, "2026-10-29 20:45", 0)])
    return db


def _scena(monkeypatch, stato="infortunato", con_alternativa=True):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [{"id": 1, "nome": "Castro", "titolarita": "titolare", "dubbio": False}]})
    prev = pd.DataFrame([{"nome": "Castro", "stato": stato, "percentuale": 0.0, "dubbio": False, "atteso": 1.0},
                         {"nome": "Bonny", "stato": "titolare", "percentuale": 80.0, "dubbio": False, "atteso": 6.2}], index=[1, 2])
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    voce = {"giocatore": {"id": 1, "nome": "Castro"}}
    if con_alternativa:
        voce["alternativa"] = {"id": 2, "nome": "Bonny", "ruolo": "A", "punti_attesi": 6.2}
    monkeypatch.setattr(da_fare, "_dubbi", lambda *a, **k: [voce])
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo, tag)) or True    # noqa: E731
    return prev, mandati, manda


def test_titolare_fuori_avvisa_con_il_sostituto_e_non_si_ripete(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch)
    f, db = tmp_path / "n.json", _db()
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1
    titolo, testo, tag = mandati[0]
    assert titolo == "SchieraXI · cambio pronto" and tag == "rotating_light"            # il tocco apre la Formazione
    assert "Il tuo Castro è infortunato. Meglio Bonny (+5,2 punti attesi)." in testo
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1                                                          # stesso cambio: una notifica sola


def test_se_c_e_gia_la_riga_dei_cambi_il_consiglio_ci_sta_dentro(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch, stato="titolare")
    f, db = tmp_path / "n.json", _db()
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")      # primo controllo: memorizza
    assert mandati == []
    prev.loc[1, "stato"] = "squalificato"
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1 and mandati[0][0] != "SchieraXI · cambio pronto"
    assert "Castro: ora squalificato Meglio Bonny" in mandati[0][1]
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1


def test_panchina_e_scelta_salvata(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch, stato="panchina")
    fs = tmp_path / "s.json"
    scelte.salva(ST, 9, [2], "4-3-3", fs)                 # hai scelto solo Bonny: Castro in panchina non ti riguarda
    notifiche.cambi(_db(), Regole(), ROSE, ADESSO, tmp_path / "n.json", manda, file_scelte=fs)
    assert mandati == []
    scelte.salva(ST, 9, [1], "4-3-3", fs)
    notifiche.cambi(_db(), Regole(), ROSE, ADESSO, tmp_path / "n.json", manda, file_scelte=fs)
    assert len(mandati) == 1 and "Il tuo Castro parte dalla panchina. Meglio Bonny" in mandati[0][1]


def test_senza_sostituto_o_con_cambi_spenti_non_manda(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch, con_alternativa=False)
    notifiche.cambi(_db(), Regole(), ROSE, ADESSO, tmp_path / "n.json", manda, file_scelte=tmp_path / "s.json")
    assert mandati == []
    prev, mandati, manda = _scena(monkeypatch)
    notifiche.cambi(_db(), Regole(), ROSE, ADESSO, tmp_path / "m.json", manda, {"cambi": False}, file_scelte=tmp_path / "s.json")
    assert mandati == []


def test_se_parte_l_avviso_dei_cambi_e_fallisce_il_cambio_pronto_i_cambi_non_si_rimandano(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch)                       # Castro è già infortunato fin dall'inizio
    voce_castro = {"giocatore": {"id": 1, "nome": "Castro"}, "alternativa": {"id": 2, "nome": "Bonny", "ruolo": "A", "punti_attesi": 6.2}}
    dubbi = []
    monkeypatch.setattr(da_fare, "_dubbi", lambda *a, **k: dubbi)
    f, db = tmp_path / "n.json", _db()
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")          # primo controllo: memorizza
    prev.loc[2, "stato"] = "infortunato"                                                          # cambio per Bonny (avviso dei cambi)
    dubbi.append(voce_castro)                                                                     # e un cambio pronto che non c'entra con quella riga
    solo_cambi = lambda titolo, testo, priorita=3, tag="x": (mandati.append(titolo) or True) if "cambio pronto" not in titolo else False     # noqa: E731
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, solo_cambi, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1 and "cambi nelle probabili" in mandati[0]
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")         # al giro dopo: solo il cambio pronto
    assert len(mandati) == 2 and mandati[1][0] == "SchieraXI · cambio pronto"
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 2


def test_nelle_ore_tranquille_riprova_dopo(tmp_path, monkeypatch):
    prev, mandati, manda = _scena(monkeypatch)
    f, db = tmp_path / "n.json", _db()
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, lambda *a, **k: False, file_scelte=tmp_path / "s.json")     # invio bloccato
    assert mandati == []
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1
    notifiche.cambi(db, Regole(), ROSE, ADESSO, f, manda, file_scelte=tmp_path / "s.json")
    assert len(mandati) == 1
