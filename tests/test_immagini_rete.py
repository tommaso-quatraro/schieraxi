"""Stemma e maglia: rotta da indirizzo web, rimozione, condivisione dal telefono (share_target). Su cartelle temporanee."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fanta import immagini, limiti, server

PNG_P = b"\x89PNG\r\n\x1a\n" + b"0" * 50
CORPO = {"squadra": "Real Esempio", "tipo": "stemma", "url": "https://img.example.com/m.png"}


@pytest.fixture
def con_rose(tmp_path, monkeypatch, calciatori):
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(immagini, "CARTELLA", tmp_path / "immagini")
    monkeypatch.setattr(limiti, "PAUSA_IMMAGINI_URL", 0)
    limiti._ultimo_download.clear()
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    c.post("/api/rose/testo", json={"testo": "Real Esempio\nP\tSommer\t10\n"})
    return c


def test_da_url_salva_l_immagine(con_rose, monkeypatch):
    chiamate = []
    monkeypatch.setattr(server.scarica_immagine, "scarica", lambda url, **k: (chiamate.append(url), (PNG_P, ".png"))[1])
    r = con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "squadra": "real", "tipo": "maglia"})
    assert r.status_code == 200 and r.json() == {"squadra": "Real Esempio", "tipo": "maglia", "immagini": {"stemma": False, "maglia": True}}
    assert chiamate == [CORPO["url"]]
    assert con_rose.get("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "maglia"}).content == PNG_P


def test_da_url_errori_chiari(con_rose):
    r = con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "url": "http://img.example.com/m.png"})
    assert r.status_code == 400 and "https" in r.json()["detail"]
    r = con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "url": "https://127.0.0.1/x.png"})
    assert r.status_code == 400 and "privata" in r.json()["detail"]
    r = con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "url": "https://169.254.169.254/latest/meta-data/"})
    assert r.status_code == 400 and "privata" in r.json()["detail"]
    assert con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "squadra": "Nessuna"}).status_code == 404
    assert con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "tipo": "scudo"}).status_code == 400
    assert con_rose.post("/api/squadre/immagine/da-url", json={**CORPO, "url": "https://x.example.com/" + "a" * 3000}).status_code == 422
    assert con_rose.post("/api/squadre/immagine/da-url", json={"squadra": "Real Esempio"}).status_code == 422
    assert con_rose.get("/api/squadre").json()[0]["immagini"] == {"stemma": False, "maglia": False}     # niente salvato


def test_da_url_serve_x_fanta_e_non_accetta_altri_siti(con_rose):
    senza = TestClient(server.app)
    assert senza.post("/api/squadre/immagine/da-url", json=CORPO).status_code == 403
    assert senza.post("/api/squadre/immagine/da-url", json=CORPO, headers={"X-Fanta": "1", "Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_da_url_frequenza_limitata(con_rose, monkeypatch):
    monkeypatch.setattr(limiti, "PAUSA_IMMAGINI_URL", 30)
    monkeypatch.setattr(server.scarica_immagine, "scarica", lambda url, **k: (PNG_P, ".png"))
    assert con_rose.post("/api/squadre/immagine/da-url", json=CORPO).status_code == 200
    r = con_rose.post("/api/squadre/immagine/da-url", json=CORPO)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "aspetta" in r.json()["detail"]


def test_da_url_troppi_download_insieme(con_rose, monkeypatch):
    monkeypatch.setattr(limiti, "_scarichi_insieme", limiti.threading.BoundedSemaphore(0))
    assert con_rose.post("/api/squadre/immagine/da-url", json=CORPO).status_code == 429


def test_rimuovi_stemma(con_rose):
    con_rose.post("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"}, files={"file": ("s.png", PNG_P, "image/png")})
    r = con_rose.delete("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"})
    assert r.status_code == 200 and r.json()["immagini"] == {"stemma": False, "maglia": False}
    assert con_rose.delete("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"}).status_code == 200      # già tolto
    assert con_rose.delete("/api/squadre/immagine", params={"squadra": "Nessuna", "tipo": "stemma"}).status_code == 404
    assert con_rose.delete("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "scudo"}).status_code == 400


def test_manifest_ha_il_share_target():
    m = json.loads((Path(server.__file__).parent / "web" / "manifest.webmanifest").read_text(encoding="utf-8"))
    t = m["share_target"]
    assert t["action"] == server.PERCORSO_CONDIVISIONE and t["method"] == "POST" and t["enctype"] == "multipart/form-data"
    assert t["params"]["files"][0]["name"] == "immagine" and t["action"].startswith(m["scope"])


def test_condivisione_dal_telefono(con_rose):
    r = con_rose.post(server.PERCORSO_CONDIVISIONE, files={"immagine": ("foto.png", PNG_P, "image/png")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?condivisa=1"
    g = con_rose.get("/api/squadre/immagine/in-attesa")
    assert g.status_code == 200 and g.content == PNG_P and g.headers["content-type"] == "image/png"
    assert con_rose.get("/api/squadre").json()[0]["immagini"] == {"stemma": False, "maglia": False}       # non è ancora di nessuna squadra
    assert con_rose.delete("/api/squadre/immagine/in-attesa").status_code == 200
    assert con_rose.get("/api/squadre/immagine/in-attesa").status_code == 404


def test_condivisione_senza_x_fanta_ma_non_da_un_altro_sito(con_rose):
    """Il sistema operativo non manda X-Fanta: la rotta di ricezione è l'unica eccezione, ma un altro sito resta bloccato."""
    senza = TestClient(server.app)
    f = {"immagine": ("foto.png", PNG_P, "image/png")}
    assert senza.post(server.PERCORSO_CONDIVISIONE, files=f, follow_redirects=False).status_code == 303
    assert senza.post(server.PERCORSO_CONDIVISIONE, files=f, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert senza.post(server.PERCORSO_CONDIVISIONE, files=f, headers={"Origin": "https://cattivo.example"}).status_code == 403
    assert senza.delete("/api/squadre/immagine/in-attesa").status_code == 403          # le altre rotte chiedono ancora X-Fanta


def test_condivisione_rifiuta_file_non_immagine_e_troppo_grandi(con_rose):
    r = con_rose.post(server.PERCORSO_CONDIVISIONE, files={"immagine": ("x.png", b"<html>", "image/png")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?condivisa=no"
    r = con_rose.post(server.PERCORSO_CONDIVISIONE, files={"immagine": ("x.png", PNG_P + b"0" * (6 * 1024 * 1024), "image/png")}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?condivisa=no"          # oltre 4 MB: scartata
    r = con_rose.post(server.PERCORSO_CONDIVISIONE, files={"immagine": ("x.png", PNG_P + b"0" * (server.LIMITE_RICHIESTA + 10), "image/png")}, follow_redirects=False)
    assert r.status_code == 413                                                         # enorme: si ferma il tetto della richiesta
    assert con_rose.get("/api/squadre/immagine/in-attesa").status_code == 404
