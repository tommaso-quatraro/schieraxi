"""Affidabilità (#982): se i punti della formazione del modello battono quelli da fantamedia lo dice il server, nella `sintesi`
(`modello_batte_fantamedia`). Prima lo decidevano web e iPhone confrontando i due numeri: uno stato calcolato in due posti."""
import json

import pytest
from fastapi.testclient import TestClient

from fanta import affidabilita, server


def _riga(modello, fantamedia):
    return {"giornata": 1, "punti_modello": modello, "punti_fantamedia": fantamedia, "punti_perfetta": 80.0}


@pytest.mark.parametrize(("modello", "fantamedia", "batte"), [
    (71.7, 70.6, True),          # meglio
    (70.0, 70.0, True),          # pari: «almeno quelli da fantamedia», come il verde di prima
    (66.0, 68.3, False),         # peggio
    (70.01, 70.04, True),        # si mostrano tutti e due «70,0»: il verdetto segue i numeri che l'utente legge
    (70.04, 70.06, False),       # «70,0» contro «70,1»
    (70.0, None, False),         # senza uno dei due numeri, no
    (None, 70.0, False),
])
def test_la_sintesi_dice_se_il_modello_batte_la_fantamedia(modello, fantamedia, batte):
    assert affidabilita.sintesi([_riga(modello, fantamedia)])["modello_batte_fantamedia"] is batte


def test_senza_giornate_il_modello_non_batte_niente():
    assert affidabilita.sintesi([])["modello_batte_fantamedia"] is False


@pytest.fixture
def cliente(monkeypatch, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    return TestClient(server.app)


def _scrivi(sintesi: dict) -> None:
    affidabilita.FILE.parent.mkdir(parents=True, exist_ok=True)
    affidabilita.FILE.write_text(json.dumps({"ultima": "2026-27/8", "righe": [], "sintesi": sintesi}), encoding="utf-8")


def test_una_prova_scritta_prima_del_campo_lo_riceve_dalla_rotta(cliente):
    """La prova si rifà solo con una giornata nuova: un file di prima non ha il campo, e la rotta lo aggiunge."""
    _scrivi({"giornate": 8, "punti_modello": 70.6, "punti_fantamedia": 71.7})
    assert cliente.get("/api/affidabilita").json()["sintesi"]["modello_batte_fantamedia"] is False
    _scrivi({"giornate": 8, "punti_modello": 71.7, "punti_fantamedia": 70.6})
    assert cliente.get("/api/affidabilita").json()["sintesi"]["modello_batte_fantamedia"] is True


def test_la_rotta_non_ricalcola_il_verdetto_scritto_nella_prova(cliente):
    _scrivi({"giornate": 8, "punti_modello": 71.7, "punti_fantamedia": 70.6, "modello_batte_fantamedia": False})
    assert cliente.get("/api/affidabilita").json()["sintesi"]["modello_batte_fantamedia"] is False


def test_senza_prova_la_rotta_risponde_vuota(cliente):
    assert cliente.get("/api/affidabilita").json() == {"righe": [], "sintesi": None}
