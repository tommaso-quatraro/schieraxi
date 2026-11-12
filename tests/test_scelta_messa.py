"""«L'ho messa» (#616): la scelta salvata della giornata ricorda se l'utente ha detto di averla messa nell'app della lega.

Campo facoltativo `messa` (vero) con `messa_il` (quando l'ha detto) nella voce di `fanta/scelte.py`, scritto solo se vero: i file
e i client di prima non vedono differenze. Lo scrive POST /api/formazione/valuta con `salva: true` e `messa: true|false`; lo
restituisce GET /api/scelta. Un client che salva senza `messa` (iPhone, web di prima) non lo perde finché gli 11 restano gli
stessi; se cambia un titolare la spunta cade da sola, perché nell'app della lega c'è un'altra formazione."""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import calcolo, fasi, scelte, server

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

STAGIONE = "2026-27"
TITOLARI = list(range(1, 12))
ALTRI = [*range(1, 11), 99]
ROSE = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"


# ---------------------------------------------------------------- il file delle scelte
def test_la_spunta_si_scrive_solo_se_vera(tmp_path):
    f = tmp_path / "scelte.json"
    senza = scelte.salva(STAGIONE, 8, TITOLARI, "4-3-3", f)
    assert "messa" not in senza and "messa_il" not in senza
    con = scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f, messa=True)
    assert con["messa"] is True and datetime.fromisoformat(con["messa_il"])
    assert scelte.leggi(STAGIONE, 9, f)["messa"] is True
    assert "messa" not in scelte.leggi(STAGIONE, 8, f)


def test_chi_salva_senza_dirlo_non_la_perde_se_i_titolari_sono_gli_stessi(tmp_path):
    f = tmp_path / "scelte.json"
    prima = scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f, messa=True)
    dopo = scelte.salva(STAGIONE, 9, list(reversed(TITOLARI)), "4-3-3", f)          # un client di prima: stessi 11, niente `messa`
    assert dopo["messa"] is True and dopo["messa_il"] == prima["messa_il"]


def test_con_un_titolare_diverso_la_spunta_cade(tmp_path):
    f = tmp_path / "scelte.json"
    scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f, messa=True)
    dopo = scelte.salva(STAGIONE, 9, ALTRI, "4-3-3", f)
    assert "messa" not in dopo and "messa_il" not in dopo
    assert "messa" not in scelte.leggi(STAGIONE, 9, f)


def test_si_puo_togliere_e_rimettere(tmp_path):
    f = tmp_path / "scelte.json"
    scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f, messa=True)
    assert "messa" not in scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f, messa=False)
    assert scelte.salva(STAGIONE, 9, ALTRI, "4-3-3", f, messa=True)["messa"] is True     # detto insieme al cambio: vale per i nuovi 11


def test_la_copia_automatica_non_e_una_formazione_messa(tmp_path):
    f = tmp_path / "scelte.json"
    assert scelte.salva_automatica(STAGIONE, 9, TITOLARI, "4-3-3", f)
    assert "messa" not in scelte.leggi(STAGIONE, 9, f, anche_automatica=True)
    # la prima scelta dell'utente, con gli stessi 11 della copia automatica, non eredita niente
    assert "messa" not in scelte.salva(STAGIONE, 9, TITOLARI, "4-3-3", f)


# ---------------------------------------------------------------- le rotte
@pytest.fixture
def prova(ambiente, monkeypatch):
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": giornata or 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()
    inizio = {"quando": datetime.now() + timedelta(hours=2)}          # prima partita della giornata 9: la formazione è aperta
    monkeypatch.setattr(fasi.avvisi, "prima_partita", lambda db, stagione, g: inizio["quando"] if g == 9 else None)
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    a.put("/api/regole", json=a.get("/api/regole").json() | {"scadenza_minuti": 10})
    return a, inizio


def _salva(a, titolari, **altro):
    return a.post("/api/formazione/valuta", json={"titolari": titolari, "giornata": 9, "salva": True, **altro})


def _scelta(a):
    return a.get("/api/scelta", params={"giornata": 9}).json()


def test_la_rotta_salva_la_spunta_e_la_scelta_la_restituisce(prova):
    a, _ = prova
    assert _salva(a, TITOLARI, messa=True).status_code == 200
    scelta = _scelta(a)
    assert scelta["titolari"] == TITOLARI and scelta["messa"] is True and datetime.fromisoformat(scelta["messa_il"])


def test_un_client_di_prima_salva_senza_il_campo_e_non_cambia_niente(prova):
    a, _ = prova
    assert _salva(a, TITOLARI).status_code == 200
    assert "messa" not in _scelta(a)                                    # senza dirlo non c'è
    _salva(a, TITOLARI, messa=True)
    assert _salva(a, TITOLARI).status_code == 200                         # di nuovo senza il campo, stessi 11: resta
    assert _scelta(a)["messa"] is True
    assert _salva(a, ALTRI).status_code == 200                          # un titolare diverso: cade
    assert "messa" not in _scelta(a)


def test_la_spunta_si_toglie(prova):
    a, _ = prova
    _salva(a, TITOLARI, messa=True)
    assert _salva(a, TITOLARI, messa=False).status_code == 200
    scelta = _scelta(a)
    assert scelta["titolari"] == TITOLARI and "messa" not in scelta and "messa_il" not in scelta


def test_senza_salvare_la_spunta_non_scrive_niente(prova):
    a, _ = prova
    assert a.post("/api/formazione/valuta", json={"titolari": TITOLARI, "giornata": 9, "messa": True}).status_code == 200
    assert _scelta(a) is None


def test_dopo_la_scadenza_la_spunta_non_si_cambia(prova):
    a, inizio = prova
    _salva(a, TITOLARI)
    inizio["quando"] = datetime.now() + timedelta(minutes=5)             # la lega chiude 10 minuti prima: già chiusa
    r = _salva(a, TITOLARI, messa=True)
    assert r.status_code == 409 and r.json()["codice"] == "formazione_chiusa"
    assert "messa" not in _scelta(a)


def test_la_spunta_deve_essere_vero_o_falso(prova):
    a, _ = prova
    assert _salva(a, TITOLARI, messa="forse").status_code == 422
    assert _scelta(a) is None
