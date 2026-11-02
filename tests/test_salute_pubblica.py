"""/api/salute: rotta pubblica per il monitoraggio. Cartelle temporanee e dati finti."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fanta import percorsi, server
from test_account_http import registra


@pytest.fixture(autouse=True)
def pulito():
    server._salute_orari.clear()
    yield
    server._salute_orari.clear()


def cliente(**intestazioni) -> TestClient:
    return TestClient(server.app, headers=intestazioni)


def _db_con_aggiornamento(quando="2026-11-01T10:00:00"):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE aggiornamenti (cosa TEXT, quando TEXT, dettaglio TEXT)")
    db.execute("INSERT INTO aggiornamenti VALUES ('aggiornamento', ?, NULL)", (quando,))
    return db


def test_salute_risponde_200_senza_login_con_gli_account_accesi(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    c = cliente()
    r = c.get("/api/salute")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "ultimo_aggiornamento": "2026-11-01T10:00:00"}      # nessun altro campo
    assert r.headers["cache-control"] == "no-store" and "etag" not in r.headers
    assert c.get("/api/stato").status_code == 401                                    # le rotte private restano private
    assert c.get("/api/stato-dati").status_code == 401


def test_salute_con_database_dei_dati_rotto_da_ok_falso(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "_db", lambda: sqlite3.connect(":memory:"))          # nessuna tabella
    r = cliente().get("/api/salute")
    assert r.status_code == 503 and r.json() == {"ok": False, "ultimo_aggiornamento": None}

    def rotto():
        raise sqlite3.DatabaseError("file is not a database")
    monkeypatch.setattr(server, "_db", rotto)
    assert cliente().get("/api/salute").status_code == 503


def test_salute_senza_nessun_aggiornamento_ha_null(multiutente, dati_isolati, monkeypatch):
    def vuoto():
        db = _db_con_aggiornamento()
        db.execute("DELETE FROM aggiornamenti")
        return db
    monkeypatch.setattr(server, "_db", vuoto)
    r = cliente().get("/api/salute")
    assert r.status_code == 200 and r.json() == {"ok": True, "ultimo_aggiornamento": None}


def test_salute_ha_un_limite_per_indirizzo(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "SALUTE_PER_IP", (3, 3600))
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    a, b = cliente(**{"X-Forwarded-For": "1.1.1.1"}), cliente(**{"X-Forwarded-For": "2.2.2.2"})
    assert [a.get("/api/salute").status_code for _ in range(3)] == [200, 200, 200]
    r = a.get("/api/salute")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert b.get("/api/salute").status_code == 200


def test_limite_in_memoria_si_libera_e_si_pulisce(monkeypatch):
    monkeypatch.setattr(server, "SALUTE_PER_IP", (2, 100))
    server._salute_pulizia[0] = 0.0
    assert server._salute_troppe("9.9.9.9", 0) == 0 and server._salute_troppe("9.9.9.9", 1) == 0
    assert server._salute_troppe("9.9.9.9", 2) > 0
    assert server._salute_troppe("9.9.9.9", 150) == 0                                # la finestra e' passata
    server._salute_troppe("8.8.8.8", 151)
    server._salute_troppe("7.7.7.7", 1000)                                           # pulizia: gli indirizzi fermi spariscono
    assert "9.9.9.9" not in server._salute_orari and "8.8.8.8" not in server._salute_orari


def test_senza_indirizzo_visibile_nessun_limite_e_nessuna_scrittura(multiutente, dati_isolati, monkeypatch):
    """Dal proprio computer (indirizzo non visibile) non si conta niente, nemmeno in memoria; e non si scrive su nessun database."""
    monkeypatch.setattr(server, "SALUTE_PER_IP", (1, 3600))
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    monkeypatch.setattr(server.rotte_account, "ip_reale", lambda request: None)
    assert [cliente().get("/api/salute").status_code for _ in range(5)] == [200] * 5
    assert server._salute_orari == {}
    assert not (percorsi.cartella_account() / "account.sqlite").exists()


def test_head_ha_gli_stessi_header_e_nessun_corpo(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    r = cliente().head("/api/salute")
    assert r.status_code == 200 and r.content == b"" and r.headers["cache-control"] == "no-store"


def test_con_gli_account_spenti_non_nasce_il_database_degli_account(dati_isolati, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    r = cliente().get("/api/salute")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert cliente(**{"X-Forwarded-For": "3.3.3.3"}).get("/api/salute").status_code == 403     # senza account: solo da questo computer
    assert not (percorsi.cartella_account() / "account.sqlite").exists()


def test_il_token_del_widget_valido_non_vale_per_salute(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "_db", _db_con_aggiornamento)
    c = cliente(**{"X-Fanta": "1"})
    registra(c, "marco")
    token = c.post("/api/account/token-widget").json()["token"]
    r = cliente(Authorization=f"Bearer {token}").get("/api/salute")
    assert r.status_code == 403
    assert cliente().get("/api/salute").status_code == 200                           # senza token resta pubblica
