"""/api/widget: ogni titolare di `formazione` porta anche il fantavoto atteso (`fv_atteso`), lo stesso numero che l'app mostra
accanto al titolare (#240), dalla stessa scheda della Formazione. Campo nuovo e facoltativo: `punti_attesi` resta per i widget
già installati; se la scheda non ha `fv_atteso` il campo manca (mai null). Dati inventati."""
from fanta import scelte, widget as w
from test_widget_tua_scelta import _prepara, _s

MIE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]          # la scelta salvata: diversa dalla consigliata (12 al posto di 11)


def _fv(i: int) -> float:
    """Un fantavoto atteso inventato, diverso dai punti attesi della scheda (`_s`: i)."""
    return round(5.5 + i / 10, 2)


def _prepara_con_fantavoto(monkeypatch):
    """Come `_prepara`, ma le schede della Formazione hanno anche `fv_atteso`, come quelle vere (`consigli.scheda_previsione`)."""
    db, rose = _prepara(monkeypatch)
    schede = {str(i): _s(i) | {"fv_atteso": _fv(i)} for i in range(1, 15)}
    monkeypatch.setattr(w.consigli, "formazione", lambda *a, **k: {
        "squadra": "X", "modulo": "5-3-2", "punteggio_atteso": 71.9, "schede": schede,
        "titolari": [schede[str(i)] for i in range(1, 12)], "panchina": [schede[str(i)] for i in range(12, 15)]})
    return db, rose


def test_titolari_della_consigliata_con_fantavoto_atteso(monkeypatch):
    db, rose = _prepara_con_fantavoto(monkeypatch)

    tit = w.costruisci(db, object(), rose, None, None)["formazione"]["titolari"]

    assert [t["fv_atteso"] for t in tit] == [_fv(i) for i in range(1, 12)]       # la scheda della Formazione dell'app
    assert [t["punti_attesi"] for t in tit] == [float(i) for i in range(1, 12)]  # il campo di prima resta (widget già installati)


def test_titolari_della_tua_scelta_con_fantavoto_atteso(monkeypatch, tmp_path):
    db, rose = _prepara_con_fantavoto(monkeypatch)
    f = tmp_path / "scelte.json"
    scelte.salva("2026-27", 10, MIE, "4-4-2", f)

    z = w.costruisci(db, object(), rose, None, None, file_scelte=f)["formazione"]

    assert z["tua_scelta"] is True
    assert {t["id"]: t["fv_atteso"] for t in z["titolari"]} == {i: _fv(i) for i in MIE}


def test_titolare_senza_fantavoto_atteso_non_manda_il_campo(monkeypatch):
    db, rose = _prepara(monkeypatch)                     # schede senza `fv_atteso`

    tit = w.costruisci(db, object(), rose, None, None)["formazione"]["titolari"]

    assert len(tit) == 11 and all("fv_atteso" not in t for t in tit)
