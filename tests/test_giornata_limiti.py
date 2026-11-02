"""Revisione 2/11/2026: un numero di giornata enorme dava errore 500 (OverflowError di sqlite, per esempio
`DELETE /api/scelta?giornata=100000000000000000000`). Ogni rotta con un parametro `giornata` risponde 422, mai 500.
Le rotte si trovano da sole: una rotta nuova con `giornata` senza limiti fa fallire il test."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fanta import archivio, server
from fanta.regole import Regole
from fanta.regole import salva as salva_regole

ENORME = 10 ** 20


def _rotte_con_giornata() -> list[tuple[str, str, str]]:
    """(metodo, percorso, dove) per ogni rotta che ha `giornata` fra i parametri (query) o nel corpo JSON."""
    rotte = []
    for r in server.app.routes:
        d = getattr(r, "dependant", None)
        if d is None:
            continue
        for metodo in sorted(r.methods - {"HEAD"}):
            if any(p.name == "giornata" for p in d.query_params):
                rotte.append((metodo, r.path, "query"))
            if any("giornata" in getattr(p.field_info.annotation, "model_fields", {}) for p in d.body_params):
                rotte.append((metodo, r.path, "corpo"))
    return rotte


@pytest.fixture
def client(tmp_path, monkeypatch):
    salva_regole(Regole(), tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    return TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)


def test_le_rotte_con_giornata_ci_sono_tutte():
    trovate = {(m, p) for m, p, _ in _rotte_con_giornata()}
    assert {("GET", "/api/formazione"), ("POST", "/api/formazione/valuta"), ("GET", "/api/scelta"), ("DELETE", "/api/scelta"),
            ("POST", "/api/diario/schierata"), ("GET", "/api/confronto")} <= trovate


@pytest.mark.parametrize("valore", [ENORME, -ENORME, 0, -1, server.MAX_GIORNATA + 1])
def test_giornata_fuori_misura_422_mai_500(client, valore):
    for metodo, percorso, dove in _rotte_con_giornata():
        params = {"a": 1, "b": 2} if percorso == "/api/confronto" else {}
        if dove == "query":
            r = client.request(metodo, percorso, params=params | {"giornata": valore})
        else:
            r = client.request(metodo, percorso, json={"giornata": valore, "titolari": [1], "tipo": "consigliata", "modo": "aspetta"})
        assert r.status_code == 422, (metodo, percorso, valore, r.status_code)
        assert "giornata" in r.json()["campi"], (metodo, percorso, r.json())


def test_cancella_scelta_con_numero_enorme_non_e_piu_un_500(client):
    """Il caso trovato dalla revisione, e una giornata normale che passa come prima."""
    assert client.delete("/api/scelta", params={"giornata": "100000000000000000000"}).status_code == 422
    assert client.get("/api/scelta", params={"giornata": ENORME}).status_code == 422
    assert client.get("/api/scelta", params={"giornata": 9}).status_code == 200
    assert client.delete("/api/scelta", params={"giornata": 9}).status_code in (200, 409)


def test_sqlite_non_sa_cercare_numeri_enormi():
    """Perché serve il limite: sqlite alza OverflowError oltre i 64 bit (da qui il 500 di prima)."""
    with pytest.raises(OverflowError):
        sqlite3.connect(":memory:").execute("SELECT ?", (ENORME,))
