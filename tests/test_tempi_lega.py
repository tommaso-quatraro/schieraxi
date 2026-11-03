"""Tempi della lega: scadenza della formazione (minuti prima della prima partita) e prima giornata della lega."""
import dataclasses
import json
import sqlite3
from datetime import datetime

import pytest

from fanta import avvisi, consigli, diario, gestione, lega, notifiche, regole
from fanta.regole import Regole

ST = "2026-27"
ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10)])], "Mia")


def _db(prima="2026-11-07 18:30"):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)",
                   [(ST, 10, prima, "A", "B", 0), (ST, 10, "2026-11-08 20:45", "C", "D", 0)])
    return db


def test_valori_di_partenza_e_controlli():
    r = Regole()
    assert (r.scadenza_minuti, r.prima_giornata_lega) == (0, 1)
    for chiave, valore in (("scadenza_minuti", -1), ("scadenza_minuti", 9999), ("prima_giornata_lega", 0), ("prima_giornata_lega", 39)):
        with pytest.raises(ValueError):
            regole.da_dict({**dataclasses.asdict(r), chiave: valore})
    assert regole.imposta(r, "scadenza_minuti", "10").scadenza_minuti == 10


def test_messaggi_dei_tempi_parlano_italiano_semplice():
    """Chi sbaglia nell'app legge una frase, non il nome interno del campo."""
    r = dataclasses.asdict(Regole())
    for chiave, valore, atteso in (("scadenza_minuti", 9999, "la scadenza della formazione"), ("prima_giornata_lega", 0, "la prima giornata della lega")):
        with pytest.raises(ValueError) as e:
            regole.da_dict({**r, chiave: valore})
        assert atteso in str(e.value) and chiave not in str(e.value)


def test_conversione_giornate_lega_e_serie_a():
    r = regole.imposta(Regole(), "prima_giornata_lega", "4")
    assert regole.lega_a_serie_a(1, r) == 4 and regole.lega_a_serie_a(7, r) == 10 and regole.lega_a_serie_a(35, r) == 38
    assert regole.serie_a_a_lega(10, r) == 7 and regole.serie_a_a_lega(4, r) == 1 and regole.serie_a_a_lega(3, r) is None
    assert regole.serie_a_a_lega(10, Regole()) == 10


def test_scadenza_e_inizio_meno_i_minuti():
    r = regole.imposta(Regole(), "scadenza_minuti", "10")
    assert avvisi.scadenza(datetime(2026, 11, 7, 18, 30), r) == datetime(2026, 11, 7, 18, 20)
    assert avvisi.scadenza(datetime(2026, 11, 7, 18, 30), Regole()) == datetime(2026, 11, 7, 18, 30)
    assert avvisi.scadenza(None, r) is None


def test_giornata_da_giocare_non_prima_della_lega(monkeypatch):
    r4 = regole.imposta(Regole(), "prima_giornata_lega", "4")
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 2)
    assert consigli.giornata_da_giocare(None, ST, Regole()) == 2
    assert consigli.giornata_da_giocare(None, ST, r4) == 4
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 10)
    assert consigli.giornata_da_giocare(None, ST, r4) == 10
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: None)
    assert consigli.giornata_da_giocare(None, ST, r4) is None


def test_oggi_senza_rose_ha_scadenza_e_conto(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 10)
    r = regole.imposta(regole.imposta(Regole(), "scadenza_minuti", "10"), "prima_giornata_lega", "4")
    o = gestione.oggi_senza_rose(_db(), datetime(2026, 11, 7, 17, 20), r)
    assert o["inizio"] == "2026-11-07 18:30" and o["scadenza"] == "2026-11-07 18:20" and o["minuti_scadenza"] == 10
    assert o["giornata"] == 10 and o["giornata_lega"] == 7
    assert o["ore_mancanti"] == 1.0 and o["iniziata"] is False
    chiusa = gestione.oggi_senza_rose(_db(), datetime(2026, 11, 7, 18, 25), r)
    assert chiusa["iniziata"] is True and chiusa["ore_mancanti"] < 0
    vecchio = gestione.oggi_senza_rose(_db(), datetime(2026, 11, 7, 18, 25))       # senza regole: come prima
    assert vecchio["scadenza"] == vecchio["inizio"] and vecchio["iniziata"] is False and vecchio["giornata_lega"] is None


def _scena(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 10)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {"modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": []})
    mandati = []
    return mandati, lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo)) or True


def test_promemoria_conta_dalla_scadenza_non_dalla_partita(tmp_path, monkeypatch):
    mandati, manda = _scena(monkeypatch)
    r = regole.imposta(Regole(), "scadenza_minuti", "10")
    opz = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
    f, s = tmp_path / "a.json", tmp_path / "s.json"
    # 17:35: alla scadenza (18:20) mancano 45 minuti, alla partita 55: il «tra un'ora» non è ancora partito
    assert notifiche.promemoria(_db(), r, ROSE, datetime(2026, 11, 7, 17, 35), f, manda, opz, s) == []
    # 17:20: alla scadenza 60 minuti: parte e dice l'orario della scadenza
    out = notifiche.promemoria(_db(), r, ROSE, datetime(2026, 11, 7, 17, 20), f, manda, opz, s)
    assert len(out) == 1 and "18:20" in out[0] and "18:30" not in out[0]
    # tra la scadenza e la partita non si manda più niente
    assert notifiche.promemoria(_db(), r, ROSE, datetime(2026, 11, 7, 18, 25), tmp_path / "b.json", manda, opz, s) == []


def test_diario_conta_solo_dalla_prima_giornata_della_lega(tmp_path, monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    voce = lambda g: {"stagione": ST, "giornata": g, "consigliata": {"atteso": 1, "reale": 1, "titolari": []}, "schierata": None}  # noqa: E731
    f = tmp_path / "diario.json"
    f.write_text(json.dumps({"giornate": {f"{ST}/{g}": voce(g) for g in (2, 4, 5)}}), encoding="utf-8")
    e = diario.elenco(f, regole.imposta(Regole(), "prima_giornata_lega", "4"))
    assert [v["giornata"] for v in e["giornate"]] == [5, 4]
    assert [v["giornata_lega"] for v in e["giornate"]] == [2, 1]
    assert len(diario.elenco(f)["giornate"]) == 3             # senza regole come prima


def test_formazione_ha_la_giornata_della_lega(monkeypatch):
    """`giornata_lega` e' facoltativo: con prima_giornata_lega = 4 la Serie A 10 e' la 7; prima della lega e' None."""
    import pandas as pd
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {"id": i, "punti_attesi": 6.0})
    ruoli = "P" * 3 + "D" * 8 + "C" * 8 + "A" * 6
    prev = pd.DataFrame({"nome": [f"g{i}" for i in range(25)], "ruolo": list(ruoli), "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.5,
                         "punti_attesi": 6.0}, index=range(1, 26))
    squadra = lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"g{i-1}", ruoli[i - 1], "ROM", 1) for i in range(1, 26)])
    r4 = regole.imposta(Regole(), "prima_giornata_lega", "4")
    for g, atteso in ((10, 7), (2, None)):
        f = consigli._calcola_formazione(squadra, prev, g, True, r4, 20)
        assert f["giornata"] == g and f["giornata_lega"] == atteso
