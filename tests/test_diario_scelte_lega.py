"""«Le tue scelte» del Diario con il numero della giornata della lega (docs/COERENZA-WEB-IPHONE.md, «Giornata 7»): le voci di
`scelte_tue.per_giornata` non avevano `giornata_lega` e la web scriveva «Giornata 6» (Serie A) per la giornata 3 di una lega
partita alla 4 (collaudo 6, 2/11/2026)."""
import json

from fanta import consigli, diario
from fanta.regole import Regole


def _voce(g, tue, cons):
    riga = lambda ids, reale: {"modulo": "4-4-2", "atteso": 60.0, "reale": reale, "dev_simulata": 5.0,
                               "titolari": [{"id": i, "nome": f"G{i}", "ruolo": "C"} for i in ids]}
    return {"stagione": "2026-27", "giornata": g, "consigliata": riga(cons, 50.0) | {"origine": "mostrata"}, "schierata": {**riga(tue, 48.0), "tipo": "manuale"},
            "automatica": None}


def test_scelte_tue_porta_giornata_lega(tmp_path, monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2026-27")
    f = tmp_path / "diario.json"
    f.write_text(json.dumps({"giornate": {"2026-27/6": _voce(6, range(1, 12), range(2, 13))}}), encoding="utf-8")
    r = diario.elenco(f, Regole(moduli=["4-4-2"], prima_giornata_lega=4))
    riga = r["scelte_tue"]["per_giornata"][0]
    assert riga["giornata"] == 6 and riga["giornata_lega"] == 3


def test_scelte_tue_senza_regole_giornata_lega_nulla(tmp_path):
    f = tmp_path / "diario.json"
    f.write_text(json.dumps({"giornate": {"2025-26/6": _voce(6, range(1, 12), range(2, 13))}}), encoding="utf-8")
    assert diario.elenco(f)["scelte_tue"]["per_giornata"][0]["giornata_lega"] is None
