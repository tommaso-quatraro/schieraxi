"""Promemoria e spunta «L'ho messa» (#639): il promemoria prima della scadenza tace solo se la formazione è segnata come messa
nell'app della lega. La web salva da sola a ogni tocco: una scelta salvata dalla web ma non segnata riceve il promemoria, con una
frase che chiede proprio questo.

L'app per iPhone di oggi non ha la spunta: per le scelte salvate dall'iPhone (e per quelle di cui non si sa da dove vengono, per
esempio salvate prima di questa versione) il promemoria resta com'era, cioè tace con una scelta salvata. Per saperlo la scelta
salvata ricorda da dove arriva (`da`: «web» o «app»), un campo in più che i client di prima ignorano.
Mai l'orologio vero: `adesso` è un argomento. Dati inventati e cartelle temporanee."""
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import calcolo, fasi, scelte, server

from test_account_http import PASSWORD
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_server import client  # noqa: F401 (fixture: un solo utente, senza account)

ST = "2026-27"
TITOLARI = list(range(1, 12))
ROSE_TESTO = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"


# ---------------------------------------------------------------- da dove arriva la scelta salvata
def test_la_scelta_ricorda_da_dove_arriva_solo_se_si_sa(tmp_path):
    f = tmp_path / "scelte.json"
    assert scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="web")["da"] == "web"
    assert scelte.leggi(ST, 9, f)["da"] == "web"
    assert scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="app")["da"] == "app"          # l'ultimo che salva decide
    assert "da" not in scelte.salva(ST, 9, TITOLARI, "4-3-3", f)                       # non si sa: il campo non c'è
    assert "da" not in scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="altro")           # solo i due valori previsti


def _finti(monkeypatch):
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": giornata or 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()
    monkeypatch.setattr(fasi.avvisi, "prima_partita", lambda db, stagione, g: datetime.now() + timedelta(hours=2) if g == 9 else None)


@pytest.fixture
def prova(ambiente, monkeypatch):  # noqa: F811 (la fixture importata arriva come parametro con lo stesso nome)
    _finti(monkeypatch)
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE_TESTO})
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    return a


def _salva(c, **altro):
    return c.post("/api/formazione/valuta", json={"titolari": TITOLARI, "giornata": 9, "salva": True, **altro})


def _scelta(c):
    return c.get("/api/scelta", params={"giornata": 9}).json()


def test_dalla_web_la_scelta_e_della_web(prova):
    """La web ha il cookie della sessione (l'iPhone no): la scelta salvata da lì ha `da: "web"`."""
    assert _salva(prova).status_code == 200
    assert _scelta(prova)["da"] == "web"


def test_dall_app_la_scelta_e_dell_app(prova):
    """L'app nativa manda il token come «Bearer» (la stessa regola delle rotte degli account): `da: "app"`, anche se la stessa
    giornata era stata salvata prima dalla web. La spunta già messa resta finché gli 11 sono gli stessi."""
    _salva(prova, messa=True)
    iphone = TestClient(server.app, headers={"X-Fanta": "1"})
    r = iphone.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD, "nativo": True})
    iphone.headers["Authorization"] = f"Bearer {r.json()['token']}"
    assert _salva(iphone).status_code == 200
    scelta = _scelta(prova)
    assert scelta["da"] == "app" and scelta["messa"] is True


def test_senza_account_la_web_si_riconosce_dalle_intestazioni_del_browser(client, monkeypatch):  # noqa: F811
    """Senza account non c'è il cookie: un browser recente manda `Sec-Fetch-Mode` (l'app nativa no). Senza nessuno dei due
    segni non si sa da dove arriva: il campo non si scrive."""
    _finti(monkeypatch)
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: ST)
    client.post("/api/rose/testo", json={"testo": ROSE_TESTO})
    client.put("/api/mia-squadra", json={"nome": "Mia"})
    r = client.post("/api/formazione/valuta", json={"titolari": TITOLARI, "giornata": 9, "salva": True}, headers={"Sec-Fetch-Mode": "cors"})
    assert r.status_code == 200
    assert _scelta(client)["da"] == "web"
    assert _salva(client).status_code == 200
    assert "da" not in _scelta(client)
