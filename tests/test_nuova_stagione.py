"""Passaggio di stagione con più dispositivi dello stesso utente (#657): un secondo dispositivo rimasto indietro non svuota le rose
appena importate, le squadre rinominate tengono il nome di Leghe e le rose vuote valgono «senza rose». Utenti, squadre e rose
inventati, tutto in cartelle temporanee."""
import hashlib

import pandas as pd
import pytest

from fanta import calcolo, contesto, server

from test_account_http import PASSWORD, cliente
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

ROSE_VECCHIE = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"
ROSE_NUOVE = "Mia\nD\tBastoni\t12\nAltra\nC\tBarella\t25\n"
GIA_DELLA_STAGIONE = "Le rose sono già della stagione in corso: non c'è niente da archiviare."


@pytest.fixture
def luglio(ambiente, listone_in_archivio, monkeypatch):
    """Rose importate nella stagione 2026-27; il test sposta la stagione in corso scrivendo in `luglio[0]` (niente orologio vero)."""
    stagione = ["2026-27"]
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: stagione[0])
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()
    return stagione


def _file(cartella) -> dict[str, str]:
    """Ogni file della cartella dell'utente con la sua impronta: se cambia anche un byte, si vede."""
    return {p.relative_to(cartella).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(cartella.rglob("*")) if p.is_file()}


def _secondo_dispositivo(nome: str):
    c = cliente()
    assert c.post("/api/account/accedi", json={"nome_utente": nome, "password": PASSWORD}).status_code == 200
    return c


# ---------------------------------------------------------------- 1. il secondo dispositivo rimasto indietro
def test_il_secondo_dispositivo_non_svuota_le_rose_nuove(luglio):
    telefono, id_utente = nuovo_utente("utentea")
    pc = _secondo_dispositivo("utentea")
    assert telefono.post("/api/rose/testo", json={"testo": ROSE_VECCHIE}).status_code == 200
    luglio[0] = "2027-28"
    assert telefono.get("/api/stagione").json()["nuova"] and pc.get("/api/stagione").json()["nuova"]     # l'avviso su tutti e due
    assert telefono.post("/api/nuova-stagione").status_code == 200
    assert telefono.post("/api/rose/testo", json={"testo": ROSE_NUOVE}).status_code == 200
    assert telefono.put("/api/mia-squadra", json={"nome": "Mia"}).status_code == 200
    assert telefono.post("/api/formazione/valuta", json={"titolari": [3], "giornata": 9, "salva": True}).status_code == 200
    assert telefono.put("/api/osservati/12").status_code == 200
    cartella = contesto.cartella_utente(id_utente)
    prima = _file(cartella)
    r = pc.post("/api/nuova-stagione")                           # sul PC l'avviso era rimasto a schermo: lo tocca e conferma
    assert r.status_code == 409 and r.json()["detail"] == GIA_DELLA_STAGIONE, r.text
    assert _file(cartella) == prima                              # niente scritto: rose nuove, scelta, seguiti e archivio come prima
    assert pc.post("/api/nuova-stagione").status_code == 409 and _file(cartella) == prima      # nemmeno alla terza volta
    assert [s["giocatori"] for s in pc.get("/api/squadre").json()] == [1, 1]


def test_la_nuova_stagione_guarda_l_etag_delle_rose(luglio):
    a, id_utente = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE_VECCHIE}).status_code == 200
    vecchio = a.get("/api/squadre").headers["etag"]
    assert a.put("/api/crediti", json={"crediti": {"Mia": 7}}).status_code == 200          # le rose cambiano da un altro dispositivo
    luglio[0] = "2027-28"
    cartella = contesto.cartella_utente(id_utente)
    prima = _file(cartella)
    r = a.post("/api/nuova-stagione", headers={"If-Match": vecchio})
    assert r.status_code == 412 and "altro dispositivo" in r.json()["detail"] and _file(cartella) == prima
    r = a.post("/api/nuova-stagione", headers={"If-Match": a.get("/api/squadre").headers["etag"]})
    assert r.status_code == 200, r.text
    assert r.headers["etag"] == a.get("/api/squadre").headers["etag"]          # l'ETag delle rose ripartite, per la scrittura dopo
