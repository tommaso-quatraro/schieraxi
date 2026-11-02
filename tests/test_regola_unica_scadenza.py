"""Una partita rinviata rimasta in calendario con la data vecchia (prima del turno: il caso di turno.py) non deve chiudere la
formazione in anticipo. Oggi, il widget e l'avviso «formazione pronta» usano la stessa regola di promemoria e copia automatica
(turno.py, avvisi.prima_partita). Trovato dalla sentinella (invariante `fase_incoerente`) il 2/11/2026."""
import sqlite3
from datetime import datetime
from types import SimpleNamespace as NS

import pandas as pd

from fanta import avvisi, consigli, gestione, regole, widget

ST = "2026-27"
G10 = ["2026-10-31 15:00", "2026-10-31 18:00", "2026-10-31 20:45", "2026-11-01 12:30", "2026-11-01 15:00", "2026-11-01 15:00",
       "2026-11-01 18:00", "2026-11-01 20:45", "2026-11-02 18:30", "2026-10-20 20:45"]      # l'ultima è rinviata, data mai aggiornata
GIOVEDI = datetime(2026, 10, 29, 12, 0)


def _db(date=G10, giocate=()):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)",
                   [(ST, 10, d, f"c{i}", f"t{i}", int(i in giocate)) for i, d in enumerate(date)])
    return db


def test_oggi_senza_rose_usa_la_regola_unica(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    db = _db()
    o = gestione.oggi_senza_rose(db, adesso=GIOVEDI, regole=regole.Regole())
    assert avvisi.scadenza(avvisi.prima_partita(db, ST, 10), regole.Regole()) == datetime(2026, 10, 31, 15, 0)
    assert o["inizio"] == o["scadenza"] == "2026-10-31 15:00"
    assert o["iniziata"] is False and o["fase"] == "prima" and o["ore_mancanti"] == 51.0
    assert next(p for p in o["partite"] if p["data"] == "2026-10-20 20:45")["stato"] == "rinviata"


def test_la_prima_partita_gia_giocata_chiude_ancora_la_formazione(monkeypatch):
    """Come prima della correzione: la formazione si chiude alla prima partita del turno anche se è già stata giocata."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(G10[:9] + ["2026-11-02 20:45"], giocate={0}), adesso=datetime(2026, 10, 31, 19, 0),
                                 regole=regole.Regole())
    assert o["scadenza"] == "2026-10-31 15:00" and o["iniziata"] is True


def test_avviso_formazione_pronta_non_si_perde_per_la_data_vecchia():
    db = _db()
    assert avvisi.inizio_giornata(db, ST, 10) == datetime(2026, 10, 31, 15, 0)
    venerdi = datetime(2026, 10, 30, 12, 0)                  # 27 ore prima: è il momento dell'avviso
    assert avvisi.da_mandare(db, ST, 10, venerdi, segna=False) is not None
    # partite del turno già giocate: conta la prima ancora da giocare; un recupero settimane dopo resta valido come prima
    db = _db(G10[:9] + ["2026-12-10 20:45"], giocate=set(range(9)))
    assert avvisi.inizio_giornata(db, ST, 10) == datetime(2026, 12, 10, 20, 45)
    assert avvisi.inizio_giornata(_db([]), ST, 10) is None


def test_widget_prima_partita_e_quella_del_turno(monkeypatch):
    oggi = {"giornata": 10, "giornata_lega": 10, "inizio": "2026-10-31 15:00", "scadenza": "2026-10-31 15:00", "ore_mancanti": 51.0,
            "iniziata": False, "con_probabili": False, "avvisi": [],
            "partite": [{"data": d, "casa": f"c{i}", "trasferta": f"t{i}", "giocata": False} for i, d in enumerate(G10)]}
    scheda = {"id": 1, "nome": "g1", "ruolo": "P", "punti_attesi": 6.0, "p_voto": 0.9}
    monkeypatch.setattr(widget.avatar, "tutti", lambda: {})
    monkeypatch.setattr(widget.gestione, "oggi", lambda *a, **k: oggi)
    monkeypatch.setattr(widget.consigli, "formazione", lambda *a, **k: {"squadra": "Mia", "modulo": "4-3-3", "punteggio_atteso": 70.0,
                                                                        "titolari": [scheda], "panchina": []})
    monkeypatch.setattr(widget.consigli, "previsioni", lambda *a, **k: (pd.DataFrame(index=[]), 10, False))
    monkeypatch.setattr(widget.diario, "elenco", lambda *a, **k: {"giornate": []})
    monkeypatch.setattr(widget.osservati, "leggi", lambda *a, **k: [])
    monkeypatch.setattr(widget.consigli, "proposte_scambi", lambda *a, **k: (None, []))
    monkeypatch.setattr(widget.consigli, "mercato", lambda *a, **k: {"proposte": []})
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aggiornamenti (cosa TEXT, quando TEXT, dettaglio TEXT)")
    rose = NS(mia_squadra="Mia", squadra=lambda n: NS(nome="Mia", giocatori=[], crediti_residui=None))
    corpo = widget.costruisci(db, regole.Regole(), rose, None, None)
    assert corpo["prima_partita"] == "2026-10-31 15:00"           # non la data vecchia della partita rinviata
