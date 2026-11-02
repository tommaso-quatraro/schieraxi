"""Rotte degli scambi: analisi N contro M con conguaglio, proposte più grandi, coda dei calcoli e tetto giornaliero.
Dati finti in cartelle temporanee: la lega vera non si tocca."""
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from fanta import calcolo, consigli, lega, limiti, server

from test_scambi import REGOLE, TAB, _rose, _valori

# gli svincolati (90, 91) servono a stimare quanto valgono i crediti sul mercato
TAB_SERVER = TAB | {90: ("C", 0.9, 9), 91: ("A", 0.9, 9)}
V = _valori(TAB_SERVER)


@pytest.fixture
def client(tmp_path, monkeypatch):
    calcolo.cache.clear()
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    import dataclasses
    import json
    (tmp_path / "regole.json").write_text(json.dumps(dataclasses.asdict(REGOLE)), encoding="utf-8")
    rose = _rose()
    rose.squadre[0].crediti_residui = 40
    rose.squadre[1].crediti_residui = 100
    lega.salva(rose, tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: sqlite3.connect(":memory:"))
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: V)
    monkeypatch.setattr(consigli, "_versione", lambda db: "v1")
    yield TestClient(server.app, headers={"X-Fanta": "1"})
    calcolo.cache.clear()


def test_le_regole_di_prova_sono_quelle_attese(client):
    assert client.get("/api/regole").json()["moduli"] == ["4-4-2"]


def test_analisi_di_sempre_invariata_e_ancora_severa_sui_ruoli(client):
    r = client.get("/api/scambi/analizza", params={"con": "B", "do": "12,9", "ricevo": "32,30"})
    assert r.status_code == 200
    d = r.json()
    assert "completo" not in d and "giudizio" not in d and d["guadagno_mio"] > 0            # i vecchi campi, come per l'app iOS
    assert d["formato"] == "2v2"                                                           # unico campo nuovo, facoltativo
    r = client.get("/api/scambi/analizza", params={"con": "B", "do": "12,9", "ricevo": "30"})
    assert r.status_code == 400 and "stesso numero" in r.json()["detail"]                  # il vecchio comportamento


def test_offerta_scritta_a_parole_con_completo_da_gli_id_e_lascia_l_analisi_alla_rotta_completa(client):
    corpo = {"testo": "Ti do g12 e g9, mi dai g30?"}
    vecchio = client.post("/api/scambi/da-testo", json=corpo)
    # 2 contro 1 senza `completo` (l'app iPhone): prima era un 400 e i nomi riconosciuti si perdevano; ora arriva l'analisi completa
    assert vecchio.status_code == 200
    v = vecchio.json()
    assert v["con"] == "B" and v["analisi"]["completo"] is True and v["analisi"]["formato"] == "2v1"
    assert v["analisi"]["guadagno_mio"] is not None and v["analisi"]["giudizio"]["spiegazione"]     # i campi di sempre ci sono ancora
    r = client.post("/api/scambi/da-testo", json=corpo | {"completo": True})
    assert r.status_code == 200
    d = r.json()
    assert d["con"] == "B" and d["analisi"] is None and sorted(d["ids"]["do"]) == [9, 12] and d["ids"]["ricevo"] == [30]
    uno = client.post("/api/scambi/da-testo", json={"testo": "Ti do g12, mi dai g32?"}).json()
    assert uno["analisi"] is not None and uno["ids"] == {"do": [12], "ricevo": [32]}         # senza `completo` tutto come prima, in più `ids`


def test_analisi_completa_in_inglese_con_parametro_o_intestazione(client):
    p = {"con": "B", "do": "12,9", "ricevo": "30", "completo": True}
    it = client.get("/api/scambi/analizza", params=p).json()["giudizio"]
    for r in (client.get("/api/scambi/analizza", params=p | {"lingua": "en"}),
              client.get("/api/scambi/analizza", params=p, headers={"Accept-Language": "en-US,en;q=0.9"})):
        en = r.json()["giudizio"]
        assert en["chi"] == it["chi"] and en["testo"] != it["testo"] and en["spiegazione"][0].startswith("For you the best line-up")
    assert client.get("/api/scambi/analizza", params=p | {"lingua": "it"}, headers={"Accept-Language": "en"}).json()["giudizio"] == it


def test_analisi_completa_due_contro_uno(client):
    r = client.get("/api/scambi/analizza", params={"con": "B", "do": "12,9", "ricevo": "30", "completo": True})
    assert r.status_code == 200
    d = r.json()
    assert d["completo"] is True and d["formato"] == "2v1" and d["valido"] is True
    assert d["giudizio"]["chi"] in {"entrambi", "te", "lui", "poco", "nessuno"} and d["giudizio"]["spiegazione"]
    assert d["conguaglio"]["crediti"] == 0 and d["conguaglio"]["chi_paga"] == "nessuno"
    assert set(d["valore_rosa"]) == {"mio", "loro"} and set(d["panchina"]) == {"mio", "loro"}


def test_conguaglio_con_i_fondi_e_valore_dei_crediti(client):
    p = {"con": "B", "do": "12,9", "ricevo": "32,30"}
    d = client.get("/api/scambi/analizza", params=p | {"conguaglio": -30}).json()                # pago io 30, ne ho 40
    assert d["completo"] is True and d["conguaglio"]["valido"] is True and d["conguaglio"]["dopo"] == {"mio": 10, "loro": 130}
    assert d["conguaglio"]["tasso_mio"] and d["conguaglio"]["valore_mio"] < 0                    # pagare costa punti
    assert d["netto_mio"] < d["guadagno_mio"] and d["netto_loro"] > d["guadagno_loro"]
    troppo = client.get("/api/scambi/analizza", params=p | {"conguaglio": -50}).json()           # ne ho solo 40
    assert troppo["valido"] is False and troppo["conguaglio"]["valido"] is False
    assert "non può pagarne 50" in troppo["conguaglio"]["problema"]
    assert "non si può fare" in troppo["giudizio"]["testo"]
    ricevo = client.get("/api/scambi/analizza", params=p | {"conguaglio": 60}).json()            # B ne ha 100
    assert ricevo["conguaglio"]["valido"] is True and ricevo["conguaglio"]["valore_mio"] > 0


def test_conguaglio_assurdo_o_non_numerico(client):
    p = {"con": "B", "do": "12", "ricevo": "32"}
    assert client.get("/api/scambi/analizza", params=p | {"conguaglio": 10 ** 8}).status_code == 400
    assert client.get("/api/scambi/analizza", params=p | {"conguaglio": "tanti"}).status_code == 422
    assert client.get("/api/scambi/analizza", params=p | {"completo": True, "ricevo": "1,2,3,4,5"}).status_code == 400


def test_proposte_piu_grandi_e_parametri(client):
    base = client.get("/api/scambi/proposte").json()
    assert "giornate" in base and all(p["formato"] == "1v1" for p in base["proposte"])         # senza parametri: 1 contro 1
    assert client.get("/api/scambi/proposte", params={"fino_a": 3}).status_code == 400         # serve la squadra
    assert client.get("/api/scambi/proposte", params={"con": "B", "fino_a": 9}).status_code == 400
    assert client.get("/api/scambi/proposte", params={"con": "B", "fino_a": 1}).status_code == 400
    due = client.get("/api/scambi/proposte", params={"con": "B", "due": True}).json()
    assert all(p["formato"] in {"1v1", "2v2"} for p in due["proposte"])
    grandi = client.get("/api/scambi/proposte", params={"con": "B", "fino_a": 3}).json()
    assert all(p["n_do"] <= 3 and p["n_ricevo"] <= 3 for p in grandi["proposte"])


def test_il_risultato_si_ricorda(client, monkeypatch):
    from fanta import scambi
    chiamate = []
    originale = scambi.proponi
    monkeypatch.setattr(scambi, "proponi", lambda *a, **k: chiamate.append(1) or originale(*a, **k))
    for _ in range(3):
        assert client.get("/api/scambi/proposte", params={"con": "B", "due": True}).status_code == 200
    assert len(chiamate) == 1
    client.get("/api/scambi/proposte", params={"con": "B", "fino_a": 3})
    assert len(chiamate) == 2


# ---------------------------------------------------------------- con gli account: coda dei calcoli e tetto giornaliero
@pytest.fixture
def con_account(multiutente, dati_isolati, calciatori, monkeypatch, tmp_path):
    from fanta import archivio
    calcolo.cache.clear()
    calcolo._errori.clear()
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(consigli, "_versione", lambda db: "v1")
    percorso = tmp_path / "prova.sqlite"
    archivio.apri(percorso).close()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(percorso))
    tab = {1: ("P", 0.9, 6), 2: ("P", 0.9, 6), 3: ("D", 0.9, 6), 4: ("D", 0.9, 5), 7: ("A", 0.9, 8), 14: ("A", 0.9, 5)}
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: _valori(tab))
    yield
    fine = time.monotonic() + 10
    while calcolo.in_corso() and time.monotonic() < fine:
        time.sleep(0.01)
    calcolo.cache.clear()
    calcolo.in_coda.set(False)


def test_gli_scambi_grandi_passano_dalla_coda_e_si_contano_a_calcolo_finito(con_account, monkeypatch):
    """Prima i 2 contro 2 giravano dentro la richiesta, senza coda né cache. Ora: 202, poi il risultato, e una ricerca sola."""
    from fanta import scambi
    from test_limiti import importa, nuovo_utente
    a, id_a = nuovo_utente("utentea")
    testo = "Mia\nP\tSommer\t10\nD\tBastoni\t8\nA\tThuram\t20\nLoro\nP\tCarnesecchi\t10\nD\tN'Dicka\t8\nA\tKean\t20\n"
    assert importa(a, testo).status_code == 200
    assert a.put("/api/mia-squadra", json={"nome": "Mia"}).status_code == 200
    chiamate = []
    originale = scambi.proponi

    def lenta(*args, **kw):
        chiamate.append(1)
        time.sleep(0.3)
        return originale(*args, **kw)
    monkeypatch.setattr(scambi, "proponi", lenta)
    r = a.get("/api/scambi/proposte", params={"con": "Loro", "fino_a": 2})
    assert r.status_code == 202 and r.json()["calcolo"] == "in_corso"
    assert limiti.usati_oggi(id_a, "scambi") == 0                      # il 202 non consuma una ricerca
    for _ in range(100):
        r = a.get("/api/scambi/proposte", params={"con": "Loro", "fino_a": 2})
        if r.status_code != 202:
            break
        time.sleep(0.1)
    assert r.status_code == 200 and "proposte" in r.json()
    assert limiti.usati_oggi(id_a, "scambi") == 1 and len(chiamate) == 1
    assert a.get("/api/scambi/proposte", params={"con": "Loro", "fino_a": 2}).status_code == 200      # dalla cache
    assert len(chiamate) == 1
    assert a.get("/api/scambi/proposte", params={"fino_a": 2}).status_code == 400                      # senza squadra: errore, niente conto
    assert limiti.usati_oggi(id_a, "scambi") == 1


def test_analisi_completa_con_gli_account_e_personale(con_account):
    from test_limiti import importa, nuovo_utente
    a, _ = nuovo_utente("utentea")
    importa(a, "Mia\nP\tSommer\t10\nD\tBastoni\t8\nA\tThuram\t20\nLoro\nP\tCarnesecchi\t10\nD\tN'Dicka\t8\nA\tKean\t20\n")
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    r = a.get("/api/scambi/analizza", params={"con": "Loro", "do": "7", "ricevo": "14", "completo": True})
    assert r.status_code == 200 and r.json()["formato"] == "1v1"
    assert TestClient(server.app, headers={"X-Fanta": "1"}).get(
        "/api/scambi/analizza", params={"con": "Loro", "do": "7", "ricevo": "14", "completo": True}).status_code == 401


def test_offerta_a_parole_con_numeri_diversi_e_in_inglese(client):
    """Collaudo 2/11: «ti do un attaccante e un centrocampista per un centrocampista» rispondeva 400 all'app senza `completo`."""
    r = client.post("/api/scambi/da-testo", json={"testo": "Ti do g12 e g9, mi dai g30?"}, headers={"Accept-Language": "en"})
    assert r.status_code == 200
    d = r.json()
    assert d["analisi"]["completo"] is True and d["analisi"]["giudizio"]["spiegazione"][0].startswith("For you")


def test_conguaglio_impossibile_non_vale_punti_e_non_va_sotto_zero(client):
    p = {"con": "B", "do": "12,9", "ricevo": "32,30"}
    d = client.get("/api/scambi/analizza", params=p | {"conguaglio": -500}).json()         # ne ho 40
    c = d["conguaglio"]
    assert c["valido"] is False and c["dopo"] == {"mio": None, "loro": None}               # prima: 40 -> -460
    assert c["valore_mio"] is None and c["valore_loro"] is None                           # prima: centinaia di punti inventati
    assert d["netto_mio"] == d["guadagno_mio"] and d["netto_loro"] == d["guadagno_loro"]
    assert "non si può (vedi sopra)" in d["giudizio"]["spiegazione"][-1]
    troppi = client.get("/api/scambi/analizza", params=p | {"conguaglio": 100000}).json()  # B ne ha 100
    assert troppi["conguaglio"]["valore_mio"] is None and troppi["conguaglio"]["dopo"] == {"mio": None, "loro": None}



def test_i_due_valori_dei_crediti_partono_insieme(monkeypatch):
    """Collaudo 2/11: con la coda il primo conguaglio aspettava due giri («sto calcolando» due volte, oltre 6 secondi)."""
    chieste = []

    def ottieni(chiave, calcola, db, **k):
        chieste.append(chiave[3])
        raise calcolo.InCalcolo()
    monkeypatch.setattr(calcolo, "ottieni", ottieni)
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: V)
    monkeypatch.setattr(consigli, "_versione", lambda db: "v1")
    with pytest.raises(calcolo.InCalcolo):
        consigli.analisi_scambio(sqlite3.connect(":memory:"), REGOLE, _rose(), "B", [12], [32], 10)
    assert chieste == ["A", "B"]


def test_offerta_a_parole_che_non_si_puo_fare_resta_un_errore_con_i_motivi(client):
    """L'app iPhone giudica l'offerta dai soli punti: uno scambio con rose non valide non deve arrivarle come «conviene»."""
    r = client.post("/api/scambi/da-testo", json={"testo": "Ti do g12, mi dai g31 e g32?"})        # A: 4 attaccanti su 3
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Così com'è lo scambio non si può fare: ") and "attaccanti su un massimo di 3" in r.json()["detail"]


def test_offerta_a_parole_rispetta_il_limite_delle_analisi(client, monkeypatch):
    """Revisione 2/11: l'analisi completa N contro M passava da `da-testo` senza il limite di `analizza` (analisi contemporanee)."""
    import contextlib
    import threading
    from types import SimpleNamespace
    monkeypatch.setattr(limiti, "_analisi_recenti", {})
    monkeypatch.setattr(limiti, "_analisi_in_corso", {})
    monkeypatch.setattr(limiti, "_analisi_insieme", threading.BoundedSemaphore(limiti.ANALISI_INSIEME))
    corpo = {"testo": "Ti do g12 e g9, mi dai g30?"}
    with contextlib.ExitStack() as pila:                    # il server è già pieno di analisi di altri utenti
        for i in range(limiti.ANALISI_INSIEME):
            pila.enter_context(limiti.analisi_scambio(SimpleNamespace(utente_id=100 + i), "x"))
        r = client.post("/api/scambi/da-testo", json=corpo)
        assert r.status_code == 429 and r.headers.get("Retry-After")
        solo_nomi = client.post("/api/scambi/da-testo", json=corpo | {"completo": True})
        assert solo_nomi.status_code == 200 and solo_nomi.json()["analisi"] is None    # riconoscere i nomi non è un'analisi
    assert client.post("/api/scambi/da-testo", json=corpo).status_code == 200          # finite le altre, si riparte
    assert limiti._analisi_in_corso == {}
