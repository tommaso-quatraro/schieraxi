"""File delle rose con una forma inattesa (prove avversarie del 1/11/2026, giro di stabilità del server).

Un rose.json che è JSON valido ma non ha la forma giusta (una lista, `{}`, `squadre: null`) o con un campo in più
(scritto da una versione più nuova, poi tornata indietro) dava «Errore interno del server» su ogni schermata e fermava
gli avvisi degli altri utenti (che saltano solo le rose che danno ValueError)."""
import json

import pytest

from fanta import lega


def _rose_dict():
    return {"squadre": [{"nome": "A", "giocatori": [{"id": 1, "nome": "Uno", "ruolo": "P", "squadra": "INT"}], "crediti_residui": 3}],
            "mia_squadra": "A", "aggiornato": ""}


def test_campo_sconosciuto_nel_giocatore_si_ignora(tmp_path):
    """Un campo in più (rose salvate da una versione più nuova, poi tornata indietro) non deve rompere la lettura."""
    d = _rose_dict()
    d["squadre"][0]["giocatori"][0]["campo_nuovo"] = 1
    d["squadre"][0]["altro_campo"] = "x"
    f = tmp_path / "rose.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    r = lega.carica(f)
    assert r.squadre[0].giocatori[0].nome == "Uno" and r.squadre[0].crediti_residui == 3


@pytest.mark.parametrize("contenuto", [[], {}, {"squadre": None}, {"squadre": [1]}, {"squadre": [{"giocatori": []}]},
                                       {"squadre": [{"nome": "A", "giocatori": [{"nome": "x"}]}]},
                                       {"squadre": [{"nome": "A", "giocatori": None}]}])
def test_forma_sbagliata_da_un_messaggio_chiaro(tmp_path, contenuto):
    f = tmp_path / "rose.json"
    f.write_text(json.dumps(contenuto), encoding="utf-8")
    with pytest.raises(ValueError, match="rose.json"):
        lega.carica(f)


def test_server_con_rose_di_forma_sbagliata_risponde_400_chiaro(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from fanta import server
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    (tmp_path / "rose.json").write_text("[]", encoding="utf-8")
    c = TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)
    r = c.get("/api/rosa")
    assert r.status_code == 400, r.text
    assert "rose.json" in r.json()["detail"] and "id_errore" not in r.json()
