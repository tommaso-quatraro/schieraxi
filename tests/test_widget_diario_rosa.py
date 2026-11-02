"""/api/widget: il diario porta il numero della giornata nella lega e la stagione (come /api/diario), la rosa porta «gioca N%».

Campi aggiunti, facoltativi: i widget già installati continuano a leggere gli stessi campi di prima.
"""
import json

from fanta import diario, widget as w
from fanta.regole import Regole
from test_widget_tua_scelta import _prepara, _s


def _diario_finto(tmp_path):
    """Una voce della stagione scorsa (giornata 38), una della stagione in corso dentro la lega (giornata 10 di Serie A) e una
    prima che la lega partisse (giornata 3 di Serie A, con la lega che parte dalla 4)."""
    f = tmp_path / "diario.json"
    voci = {
        "2025-26/38": {"stagione": "2025-26", "giornata": 38, "consigliata": {"atteso": 70.0, "reale": 65.0}},
        "2026-27/3": {"stagione": "2026-27", "giornata": 3, "consigliata": {"atteso": 60.0, "reale": 61.0}},
        "2026-27/10": {"stagione": "2026-27", "giornata": 10, "consigliata": {"atteso": 68.0, "reale": 72.0}},
    }
    f.write_text(json.dumps({"giornate": voci}), encoding="utf-8")
    return f


def test_diario_del_widget_con_giornata_della_lega_e_stagione(monkeypatch, tmp_path):
    elenco_vero = diario.elenco
    db, rose = _prepara(monkeypatch)                       # stagione in corso: 2026-27
    monkeypatch.setattr(w.diario, "elenco", elenco_vero)   # qui il diario vero, sul file finto
    regole = Regole(prima_giornata_lega=4)                 # giornata 10 di Serie A = giornata 7 della lega
    f = _diario_finto(tmp_path)

    c = w.costruisci(db, regole, rose, f, None)

    assert [(v["stagione"], v["giornata"], v["giornata_lega"]) for v in c["diario"]] == [
        ("2026-27", 10, 7),          # stagione in corso: il numero della lega
        ("2025-26", 38, None),       # stagione scorsa: niente numero della lega, il client scrive «Giornata 38 · 2025-26»
    ]
    # gli stessi numeri di /api/diario (web e app), voce per voce
    dal_diario = {(v["stagione"], v["giornata"]): v["giornata_lega"] for v in elenco_vero(f, regole)["giornate"]}
    assert all(dal_diario[(v["stagione"], v["giornata"])] == v["giornata_lega"] for v in c["diario"])
    # i campi di prima restano, con gli stessi valori
    assert [(v["attesi"], v["fatti"]) for v in c["diario"]] == [(68.0, 72.0), (70.0, 65.0)]
    assert all("intervallo" in v for v in c["diario"])


def test_rosa_del_widget_con_gioca_percentuale(monkeypatch):
    db, rose = _prepara(monkeypatch)

    def scheda(i, x):
        s = _s(i)
        if i == 3:                                          # in dubbio, gioca al 55%
            s |= {"stato": "dubbio", "dubbio": True, "percentuale": 50.0, "p_voto": 0.55}
        return s
    monkeypatch.setattr(w.consigli, "scheda_previsione", scheda)

    c = w.costruisci(db, object(), rose, None, None)

    g = next(m for m in c["rosa"] if m["id"] == 3)
    assert (g["dubbio"], g["p_voto"]) == (True, 0.55)
    assert g["percentuale"] == 50.0                         # il campo di prima resta
    assert all(m["p_voto"] == 0.9 for m in c["rosa"] if m["id"] != 3)


def test_rosa_senza_p_voto_non_manda_il_campo(monkeypatch):
    db, rose = _prepara(monkeypatch)
    monkeypatch.setattr(w.consigli, "scheda_previsione", lambda i, x: {k: v for k, v in _s(i).items() if k != "p_voto"})

    c = w.costruisci(db, object(), rose, None, None)

    assert c["rosa"] and all("p_voto" not in m for m in c["rosa"])   # facoltativo: se non c'è, manca (mai null)
