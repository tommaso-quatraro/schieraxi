"""Il widget mostra la formazione salvata dall'utente (tua_scelta) e tiene la consigliata accanto."""
import sqlite3
from types import SimpleNamespace as NS

import pandas as pd

from fanta import calcolo, scelte, widget as w


def _s(i):
    return {"id": i, "nome": f"g{i}", "ruolo": "C", "squadra": "inter", "avversario": "XXX", "in_casa": True, "data_partita": None,
            "stato": "titolare", "percentuale": 90.0, "dubbio": False, "diffidato": False, "punti_attesi": float(i), "p_voto": 0.9,
            "rigori_attesi": 0.0}


def _prepara(monkeypatch):
    schede = {str(i): _s(i) for i in range(1, 15)}
    monkeypatch.setattr(w.gestione, "oggi", lambda *a, **k: {"giornata": 10, "inizio": "2026-11-01 18:00", "ore_mancanti": 3.0,
                                                             "iniziata": False, "con_probabili": True, "avvisi": [], "partite": []})
    monkeypatch.setattr(w.consigli, "formazione", lambda *a, **k: {
        "squadra": "X", "modulo": "5-3-2", "punteggio_atteso": 71.9, "schede": schede,
        "titolari": [schede[str(i)] for i in range(1, 12)], "panchina": [schede[str(i)] for i in range(12, 15)]})
    monkeypatch.setattr(w.consigli, "previsioni", lambda *a, **k: (pd.DataFrame(index=list(range(1, 15))), 10, True))
    monkeypatch.setattr(w.consigli, "scheda_previsione", lambda i, x: _s(i))
    monkeypatch.setattr(w.consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(w.consigli, "valuta", lambda *a, **k: {"modulo": "4-4-2", "punteggio_atteso": 71.7, "panchina": [11, 13, 14],
                                                               "intervallo": None})
    monkeypatch.setattr(w.consigli, "proposte_scambi", lambda *a, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    monkeypatch.setattr(w.consigli, "mercato", lambda *a, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    monkeypatch.setattr(w.avatar, "tutti", lambda: {})
    monkeypatch.setattr(w.diario, "elenco", lambda *a, **k: {"giornate": []})
    monkeypatch.setattr(w.osservati, "leggi", lambda *a, **k: [])
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aggiornamenti (quando TEXT, cosa TEXT, dettaglio TEXT)")
    squadra = NS(nome="X", crediti_residui=1, giocatori=[NS(id=i) for i in range(1, 15)])
    return db, NS(mia_squadra="X", squadra=lambda n: squadra)


def test_il_widget_riporta_la_scelta_salvata(monkeypatch, tmp_path):
    db, rose = _prepara(monkeypatch)
    f = tmp_path / "scelte.json"
    c = w.costruisci(db, object(), rose, None, None, file_scelte=f)
    assert c["formazione"]["modulo"] == "5-3-2" and "tua_scelta" not in c["formazione"]        # nessuna scelta: la consigliata
    scelte.salva("2026-27", 10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12], "4-4-2", f)
    c = w.costruisci(db, object(), rose, None, None, file_scelte=f)
    z = c["formazione"]
    assert (z["modulo"], z["punti_attesi"], z["tua_scelta"]) == ("4-4-2", 71.7, True)
    assert [t["id"] for t in z["titolari"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12] and z["panchina"] == [11, 13, 14]
    assert z["consigliata"] == {"modulo": "5-3-2", "punti_attesi": 71.9}
    assert {m["id"] for m in c["rosa"] if m["titolare"]} == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12}
