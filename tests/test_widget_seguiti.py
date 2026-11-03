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
    assert (seguiti[5]["dubbio"], seguiti[7]["dubbio"]) == (True, False)     # la riga è «In dubbio · gioca 42%»
    # la stessa fonte della rosa del widget (e di Oggi): gli stessi valori per lo stesso giocatore
    rosa = {g["id"]: g for g in c["rosa"]}
    assert all((seguiti[i]["p_voto"], seguiti[i]["dubbio"]) == (rosa[i]["p_voto"], rosa[i]["dubbio"]) for i in seguiti)
    assert seguiti[5]["percentuale"] == 50.0                # il campo di prima resta (widget già installati)


def test_seguito_senza_p_voto_ne_dubbio_non_manda_i_campi(monkeypatch):
    db, rose = _prepara(monkeypatch)
    monkeypatch.setattr(w.consigli, "scheda_previsione",
                        lambda i, x: {k: v for k, v in _s(i).items() if k not in ("p_voto", "dubbio")})
    monkeypatch.setattr(w.osservati, "leggi", lambda *a, **k: [5, 7])

    c = w.costruisci(db, object(), rose, None, None)

    assert len(c["osservati"]) == 2                          # facoltativi: se non ci sono, mancano (mai null)
    assert all("p_voto" not in g and "dubbio" not in g for g in c["osservati"])


def test_seguiti_del_widget_con_fantavoto_atteso(monkeypatch):
    """#225: il widget «Giocatore seguito» mostra il fantavoto atteso (`fv_atteso`), come i Seguiti nell'app, non il voto in pagella."""
    db, rose = _prepara(monkeypatch)
    monkeypatch.setattr(w.consigli, "scheda_previsione", lambda i, x: _s(i) | {"fv_atteso": 6.85, "voto_atteso": 6.1})
    monkeypatch.setattr(w.osservati, "leggi", lambda *a, **k: [5, 7])

    c = w.costruisci(db, object(), rose, None, None)

    assert [g["fv_atteso"] for g in c["osservati"]] == [6.85, 6.85]
    assert all(g["voto_atteso"] == 6.1 for g in c["osservati"])      # il campo di prima resta (widget già installati)
