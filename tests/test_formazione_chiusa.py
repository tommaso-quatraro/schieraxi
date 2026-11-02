"""Dopo la scadenza della lega la scelta della giornata non si cambia più: salvare o tornare alla consigliata risponde 409 con
`codice: "formazione_chiusa"` (per tutti, amministratore compreso). Valutare senza salvare resta possibile; la copia automatica
alla scadenza (`copia_scadenza.py`) scrive prima della scadenza e non passa dalle rotte."""
import contextlib
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import account, calcolo, copia_scadenza, fasi, scelte, server

from fanta.contesto import Contesto
from test_account_http import PASSWORD
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

ROSE = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"


@pytest.fixture
def prova(ambiente, monkeypatch):
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": giornata or 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()
    inizio = {"quando": None}                   # inizio della prima partita della giornata 9 (None = calendario senza date)
    monkeypatch.setattr(fasi.avvisi, "prima_partita", lambda db, stagione, g: inizio["quando"] if g == 9 else None)
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    a.put("/api/regole", json=a.get("/api/regole").json() | {"scadenza_minuti": 10})
    return a, inizio


def _salva(a, titolari, giornata=9):
    return a.post("/api/formazione/valuta", json={"titolari": titolari, "giornata": giornata, "salva": True})


def test_prima_della_scadenza_si_salva_e_si_torna_alla_consigliata(prova):
    a, inizio = prova
    inizio["quando"] = datetime.now() + timedelta(hours=2)
    assert _salva(a, [1, 2, 3]).status_code == 200
    assert a.get("/api/scelta", params={"giornata": 9}).json()["titolari"] == [1, 2, 3]
    assert a.delete("/api/scelta", params={"giornata": 9}).status_code == 200
    assert a.get("/api/scelta", params={"giornata": 9}).json() is None


def test_dopo_la_scadenza_niente_salvataggi_ne_cancellazioni(prova):
    a, inizio = prova
    inizio["quando"] = datetime.now() + timedelta(hours=2)
    assert _salva(a, [1, 2, 3]).status_code == 200
    # la partita comincia fra 5 minuti ma la lega chiude 10 minuti prima: già chiusa
    inizio["quando"] = datetime.now() + timedelta(minutes=5)
    r = _salva(a, [4, 5, 6])
    assert r.status_code == 409
    assert r.json() == {"detail": server.FORMAZIONE_CHIUSA, "codice": "formazione_chiusa"}
    r = a.delete("/api/scelta", params={"giornata": 9})
    assert r.status_code == 409 and r.json()["codice"] == "formazione_chiusa"
    assert a.get("/api/scelta", params={"giornata": 9}).json()["titolari"] == [1, 2, 3]      # la scelta di prima resta
    # valutare senza salvare non scrive niente: si può ancora
    assert a.post("/api/formazione/valuta", json={"titolari": [4, 5, 6], "giornata": 9}).status_code == 200
    # un'altra giornata (ancora senza date) resta aperta
    assert _salva(a, [4, 5, 6], giornata=10).status_code == 200


def test_anche_l_amministratore_non_forza(prova):
    a, inizio = prova
    inizio["quando"] = datetime.now() - timedelta(hours=1)
    with contextlib.closing(account.apri()) as db:
        account.imposta_ruolo(db, "utentea", "amministratore")
    assert a.get("/api/account/me").json()["utente"]["ruolo"] == "amministratore"
    assert _salva(a, [1, 2, 3]).status_code == 409
    assert a.get("/api/scelta", params={"giornata": 9}).json() is None


def test_la_copia_alla_scadenza_scrive_ancora(tmp_path):
    """La copia automatica scrive negli ultimi minuti PRIMA della scadenza, senza passare dalla rotta chiusa."""
    scad = datetime(2026, 11, 8, 15, 0)
    assert copia_scadenza.dovuta(scad - timedelta(minutes=5), scad)
    assert not copia_scadenza.dovuta(scad, scad)
    file = tmp_path / "scelte.json"
    f = {"giornata": 9, "modulo": "4-3-3", "titolari": [{"id": i} for i in range(1, 12)]}
    copia_scadenza.salva(f, "2026-27", file, tmp_path / "diario.json")
    assert scelte.leggi("2026-27", 9, file, anche_automatica=True)["titolari"] == list(range(1, 12))


@pytest.mark.parametrize("prima", ["salvata", "copia_automatica"])
def test_caso_reale_iphone_salva_dopo_la_scadenza(prova, prima):
    """Produzione, 2/11/2026: l'iPhone ha salvato alle 13:09 la formazione di una giornata chiusa il sabato prima. Con il token
    dell'app (Bearer, senza cookie) il server deve rispondere 409 e lasciare intatta la scelta salvata o la copia della scadenza."""
    a, inizio = prova
    uid = a.get("/api/account/me").json()["utente"]["id"]
    file_scelte = Contesto.per_utente(uid).scelte
    inizio["quando"] = datetime.now() + timedelta(hours=2)
    if prima == "salvata":
        assert _salva(a, [1, 2, 3]).status_code == 200
    else:
        scelte.salva_automatica("2026-27", 9, [1, 2, 3], "4-3-3", file_scelte)
    atteso = scelte.leggi("2026-27", 9, file_scelte, anche_automatica=True)
    inizio["quando"] = datetime.now() - timedelta(days=2)             # giornata chiusa da due giorni
    iphone = TestClient(server.app, headers={"X-Fanta": "1"})
    r = iphone.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD, "nativo": True})
    bearer = {"Authorization": f"Bearer {r.json()['token']}"}
    for giornata in (9, None):                                         # anche senza giornata: vale la giornata da giocare del server
        r = iphone.post("/api/formazione/valuta", json={"titolari": [4, 5, 6], "giornata": giornata, "salva": True}, headers=bearer)
        assert r.status_code == 409 and r.json()["codice"] == "formazione_chiusa", r.text
    assert iphone.delete("/api/scelta", params={"giornata": 9}, headers=bearer).status_code == 409
    assert scelte.leggi("2026-27", 9, file_scelte, anche_automatica=True) == atteso
