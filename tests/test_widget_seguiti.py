"""/api/widget: ogni giocatore seguito (`osservati`) porta anche «gioca N%» (`p_voto`), come la rosa del widget e come Oggi.

Campo nuovo e facoltativo: i widget già installati continuano a leggere gli stessi campi di prima (`percentuale` compresa).
"""
from fanta import widget as w
from test_widget_tua_scelta import _prepara, _s


def test_seguiti_del_widget_con_gioca_percentuale(monkeypatch):
    db, rose = _prepara(monkeypatch)

    def scheda(i, x):
        s = _s(i)
        if i == 5:                                          # in dubbio, gioca al 42%
            s |= {"stato": "dubbio", "dubbio": True, "percentuale": 50.0, "p_voto": 0.42}
        return s
    monkeypatch.setattr(w.consigli, "scheda_previsione", scheda)
    monkeypatch.setattr(w.osservati, "leggi", lambda *a, **k: [5, 7])

    c = w.costruisci(db, object(), rose, None, None)

    seguiti = {g["id"]: g for g in c["osservati"]}
    assert set(seguiti) == {5, 7}
    assert (seguiti[5]["p_voto"], seguiti[7]["p_voto"]) == (0.42, 0.9)
    # la stessa fonte della rosa del widget (e di Oggi): lo stesso numero per lo stesso giocatore
    rosa = {g["id"]: g for g in c["rosa"]}
    assert all(seguiti[i]["p_voto"] == rosa[i]["p_voto"] for i in seguiti)
    assert seguiti[5]["percentuale"] == 50.0                # il campo di prima resta (widget già installati)


def test_seguito_senza_p_voto_non_manda_il_campo(monkeypatch):
    db, rose = _prepara(monkeypatch)
    monkeypatch.setattr(w.consigli, "scheda_previsione", lambda i, x: {k: v for k, v in _s(i).items() if k != "p_voto"})
    monkeypatch.setattr(w.osservati, "leggi", lambda *a, **k: [5, 7])

    c = w.costruisci(db, object(), rose, None, None)

    assert len(c["osservati"]) == 2 and all("p_voto" not in g for g in c["osservati"])   # facoltativo: se non c'è, manca (mai null)
