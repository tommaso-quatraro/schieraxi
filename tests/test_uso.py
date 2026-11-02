"""Conteggio d'uso anonimo: per rotta e per funzione, 28 giorni, nessun dato di chi chiede."""
import json
from datetime import date, timedelta

from fastapi.testclient import TestClient

from fanta import server, uso


def _giorno(delta=0):
    return (date.today() - timedelta(days=delta)).isoformat()


def test_conta_per_rotta_e_per_funzione():
    uso.conta("GET", "/api/asta", 200)
    uso.conta("GET", "/api/asta", 409)
    uso.conta("GET", "/api/scambi/proposte", 200)
    uso.conta("GET", "/api/oggi", 200)
    r = uso.riepilogo()
    assert r["richieste"] == 4
    assert {x["funzione"]: x["richieste"] for x in r["per_funzione"]} == {"asta": 2, "scambi_trova": 1}
    assert {x["rotta"]: x["richieste"] for x in r["per_rotta"]}["GET /api/asta"] == 2
    assert [g["richieste"] for g in r["per_giorno"]] == [4]


def test_non_conta_file_dell_app_rotte_sconosciute_ed_errori_del_server():
    uso.conta("GET", "(file dell'app)", 200)
    uso.conta("GET", "(sconosciuta)", 404)
    uso.conta("GET", "/api/oggi", 500)
    assert uso.riepilogo()["richieste"] == 0


def test_tiene_28_giorni_e_somma_ai_giorni_gia_scritti():
    uso.FILE.write_text(json.dumps({"giorni": {
        _giorno(40): {"rotte": {"GET /api/vecchia": 9}, "funzioni": {}},
        _giorno(27): {"rotte": {"GET /api/oggi": 5}, "funzioni": {}},
        "non-una-data": {"rotte": {"x": 1}, "funzioni": {}}}}), encoding="utf-8")
    uso.conta("GET", "/api/oggi", 200)
    r = uso.riepilogo()
    assert r["richieste"] == 6 and r["dal"] == _giorno(27) and r["al"] == _giorno(0)
    assert "vecchia" not in json.dumps(json.loads(uso.FILE.read_text(encoding="utf-8")))


def test_file_rovinato_non_rompe_niente():
    uso.FILE.write_text("{{{ non json", encoding="utf-8")
    uso.conta("GET", "/api/oggi", 200)
    assert uso.riepilogo()["richieste"] == 1
    uso.FILE.write_text(json.dumps({"giorni": {_giorno(): {"rotte": "boh", "funzioni": {"a": "x", "b": True, "c": -1, "d": 2}}}}), encoding="utf-8")
    assert uso.riepilogo(percorso=uso.FILE)["per_funzione"] == [{"funzione": "d", "richieste": 2}]


def test_tetto_di_rotte_diverse_al_giorno(monkeypatch):
    monkeypatch.setattr(uso, "MAX_VOCI", 3)
    for i in range(10):
        uso.conta("GET", f"/api/x{i}", 200)
    assert len(uso.riepilogo()["per_rotta"]) == 3


def test_il_server_conta_senza_identificare_nessuno(dati_isolati):
    # senza account il server risponde solo da questo computer: l'indirizzo «di chi chiede» arriva come nome del dispositivo
    c = TestClient(server.app, headers={"X-Fanta": "1", "User-Agent": "203.0.113.77"})
    c.get("/api/live")
    c.get("/api/giocatore/12345")
    c.get("/api/asta")
    testo = json.dumps(uso.riepilogo())
    assert "GET /api/giocatore/{calciatore_id}" in testo and "12345" not in testo and "203.0.113.77" not in testo
    assert {"live", "asta"} <= {x["funzione"] for x in uso.riepilogo()["per_funzione"]}
    # sul disco: solo giorni, rotte di modello e numeri
    grezzo = uso.FILE.read_text(encoding="utf-8")
    assert "203.0.113.77" not in grezzo and "12345" not in grezzo


def test_nello_stato_dei_dati_solo_amministratore(multiutente, dati_isolati):
    import contextlib
    from fanta import account
    from test_account_http import cliente
    uso.conta("GET", "/api/oggi", 200)
    clienti = []
    for nome in ("primo", "secondo"):                       # il primo account è l'amministratore
        with contextlib.closing(account.apri()) as db:
            inv = account.crea_invito(db, nome, nome == "primo")
        c = cliente()
        assert c.post("/api/account/registra", json={"nome_utente": nome, "password": "una-password-lunga-9", "invito": inv}).status_code == 200
        clienti.append(c)
    admin, semplice = clienti
    r = semplice.get("/api/stato-dati")
    assert r.status_code == 403 and "uso" not in r.text
    assert semplice.get("/api/account/me").status_code == 200
    r = admin.get("/api/stato-dati")
    assert r.status_code == 200 and r.json()["uso"]["richieste"] >= 1
