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
    assert uso.riepilogo(percorso=uso.FILE)["per_funzione"] == [{"funzione": "d", "etichetta": "d", "etichetta_frase": None,
                                                                  "richieste": 2}]   # non è una funzione: resta col suo nome


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


def test_funzioni_e_parti_dell_app_hanno_un_nome_in_parole():
    """Prima «Quanto si usa l'app» mostrava nomi interni («scambi_valuta_o_costruisci», «GET /api/giocatore/{calciatore_id}»).
    Ora ogni funzione ha il suo nome (`funzioni.FUNZIONI`) e le richieste si contano anche per parte dell'app, con il nome della
    parte come in «Errori recenti» («Formazione»), già scritto dal server con la sua frase per tradurlo."""
    uso.conta("GET", "/api/scambi/analizza", 200)
    uso.conta("POST", "/api/scambi/da-testo", 200)
    uso.conta("GET", "/api/giocatore/{calciatore_id}", 200)
    uso.conta("GET", "/api/oggi", 200)
    uso.conta("GET", "/api/oggi", 200)
    uso.conta("GET", "/api/stato", 200)
    uso.conta("GET", "/api/nuova-di-zecca", 200)
    r = uso.riepilogo()
    assert r["per_funzione"] == [{"funzione": "scambi_costruisci", "etichetta": "Scambi: costruisci", "richieste": 2,
                                   "etichetta_frase": {"chiave": "uso.funzione_scambi_costruisci", "param": {}}}]
    parti = {p["parte"]: p for p in r["per_parte"]}
    assert parti["formazione"] == {"parte": "formazione", "etichetta": "Formazione", "richieste": 3,
                                   "etichetta_frase": {"chiave": "uso.parte_formazione", "param": {}}}
    assert (parti["lega"]["etichetta"], parti["lega"]["richieste"]) == ("La mia lega", 2)
    assert (parti["avvio"]["etichetta"], parti["altro"]["etichetta"]) == ("Apertura dell'app", "Altre richieste")
    assert [p["parte"] for p in r["per_parte"]][0] == "formazione"                  # dalla più usata
    assert all("/" not in x["etichetta"] and "_" not in x["etichetta"] for x in r["per_parte"] + r["per_funzione"])
    assert {x["rotta"] for x in r["per_rotta"]} >= {"GET /api/oggi", "GET /api/giocatore/{calciatore_id}"}   # campo di prima, uguale
    from fanta import frasi, funzioni
    assert set(uso.FUNZIONE_DI_ROTTA.values()) <= set(funzioni.FUNZIONI)            # mai più un nome che non è una funzione
    assert all(f"uso.parte_{k}" in frasi.CATALOGO for k in [*uso.PARTI, "altro"])


def test_il_vecchio_nome_di_valuta_un_offerta_si_somma_a_scambi_costruisci():
    """Fino al 26/11/2026 le rotte di «Valuta un'offerta» si contavano come «scambi_valuta_o_costruisci», che non è una funzione:
    i giorni già scritti nel file si sommano a «Scambi: costruisci», che tiene quelle rotte (funzioni.CON_ROTTE)."""
    uso.FILE.write_text(json.dumps({"giorni": {_giorno(1): {"rotte": {"GET /api/scambi/analizza": 3},
                                                            "funzioni": {"scambi_valuta_o_costruisci": 3}}}}), encoding="utf-8")
    uso.conta("GET", "/api/scambi/analizza", 200)
    assert [(f["funzione"], f["etichetta"], f["richieste"]) for f in uso.riepilogo()["per_funzione"]] == [("scambi_costruisci", "Scambi: costruisci", 4)]
