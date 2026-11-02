"""Collaudo del 2/11/2026 (giro 5): a giornata iniziata Seguiti e l'elenco dei Giocatori dicevano ancora «In ballottaggio ·
gioca 72%» per partite già giocate, mentre Rosa, scheda e Formazione dicevano «Voto in arrivo»."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import server


@pytest.fixture
def client(tmp_path, monkeypatch, calciatori, listone_in_archivio):      # i Seguiti accettano solo codici del listone
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.osservati, "FILE_OSSERVATI", tmp_path / "oss.json")
    return TestClient(server.app, headers={"X-Fanta": "1"})


@pytest.fixture
def due_giocatori(monkeypatch):
    prev = pd.DataFrame({"nome": ["Sommer", "Kean"], "p_voto": [0.72, 0.9], "ruolo": ["P", "A"], "atteso": [3.0, 5.0]}, index=[2, 14])
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, False))
    monkeypatch.setattr(server.consigli, "scheda_previsione",
                        lambda i, x: {"id": int(i), "nome": x["nome"], "titolarita": "ballottaggio", "motivi": ["titolare"],
                                      "etichetta": {"codice": "ballottaggio", "testo": "In ballottaggio", "tono": "attenzione"}})
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {2: "attesa_voti", 14: "da_giocare"})


def _per_nome(risposta):
    assert risposta.status_code == 200, risposta.text
    return {g["nome"]: g for g in risposta.json()["giocatori"]}


def test_seguiti_dopo_la_scadenza_mostrano_lo_stato_della_giornata(client, monkeypatch, due_giocatori):
    for i in (2, 14):
        assert client.put(f"/api/osservati/{i}").status_code == 200
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    prima = _per_nome(client.get("/api/osservati"))
    assert prima["Sommer"]["etichetta"]["codice"] == "ballottaggio" and "stato_partita" not in prima["Sommer"]
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    dopo = _per_nome(client.get("/api/osservati"))
    assert dopo["Sommer"]["stato_partita"] == "attesa_voti" and dopo["Sommer"]["titolarita"] is None
    assert dopo["Sommer"]["etichetta"]["codice"] == "voto_in_arrivo" and dopo["Sommer"]["etichetta"]["tono"] == "neutro"
    assert dopo["Kean"]["stato_partita"] == "da_giocare" and dopo["Kean"]["motivi"] == []
    assert dopo["Sommer"]["proprietario"] is None                       # i campi aggiunti dalla rotta restano


def test_seguito_senza_partita_resta_com_era_dopo_la_scadenza(client, monkeypatch, due_giocatori, calciatori):
    altro = next(int(i) for i in (c.id for c in calciatori) if int(i) not in (2, 14))
    assert client.put(f"/api/osservati/{altro}").status_code == 200
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    g = client.get("/api/osservati").json()["giocatori"]
    assert len(g) == 1 and g[0]["assente"] is True and "stato_partita" not in g[0]


def test_elenco_dei_giocatori_dopo_la_scadenza(client, monkeypatch, due_giocatori):
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    assert _per_nome(client.get("/api/classifica"))["Kean"]["etichetta"]["codice"] == "ballottaggio"
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    dopo = _per_nome(client.get("/api/classifica"))
    assert dopo["Kean"]["stato_partita"] == "da_giocare" and dopo["Kean"]["etichetta"]["codice"] == "da_giocare"
    assert list(dopo) == ["Kean", "Sommer"]                              # l'ordine per punti attesi non cambia
