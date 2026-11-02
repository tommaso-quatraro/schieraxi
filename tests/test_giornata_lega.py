"""`giornata_lega` (il numero della giornata nel calendario della lega) accanto a `giornata` (Serie A) anche nella scheda del
giocatore e nel confronto: web e iPhone mostrano «Giornata 7» ovunque (docs/COERENZA-WEB-IPHONE.md, riga 4 e 28)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, fasi, scheda, server
from fanta.regole import Regole

LEGA_DA_4 = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3}, prima_giornata_lega=4)


def _prev():
    base = {"ruolo": "A", "squadra": "a", "avversario": "b", "in_casa": True, "mu_voto": 6.3, "e_gol": 0.3, "e_assist": 0.1,
            "e_rigori": 0.0, "gol_subiti": 0.0, "p_imbattuto": 0.0}
    return pd.DataFrame([base | {"nome": "Uno", "p_voto": 0.9, "mu": 7.0}, base | {"nome": "Due", "p_voto": 0.6, "mu": 6.5}],
                        index=[1, 2])


def _scheda_finta(i, x):
    return {"id": int(i), "nome": x["nome"], "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2)}


@pytest.fixture
def finto(monkeypatch):
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None, *a, **k: (_prev(), 10, None))
    monkeypatch.setattr(consigli, "scheda_previsione", _scheda_finta)


def test_confronto_porta_giornata_lega(finto):
    r = consigli.confronto(None, LEGA_DA_4, 1, 2)
    assert r["giornata"] == 10 and r["giornata_lega"] == 7          # Serie A 10 = giornata 7 della lega partita alla 4
    assert consigli.confronto(None, Regole(moduli=["4-4-2"]), 1, 2)["giornata_lega"] == 10   # lega dall'inizio: stesso numero


def test_confronto_prima_che_la_lega_parta_giornata_lega_nulla(finto):
    r = consigli.confronto(None, Regole(moduli=["4-4-2"], prima_giornata_lega=12), 1, 2)
    assert r["giornata"] == 10 and r["giornata_lega"] is None


def test_scheda_del_giocatore_porta_giornata_lega(tmp_path, monkeypatch, finto):
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(server, "_regole", lambda ctx: LEGA_DA_4)
    monkeypatch.setattr(scheda, "scheda", lambda *a, **k: {"calciatore": {"ruolo": "A"}, "avanzate": {}, "stagione": {"con_voto": 0}})
    monkeypatch.setattr(scheda, "rendimento", lambda *a, **k: None)
    monkeypatch.setattr(fasi, "iniziata", lambda *a, **k: False)
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    p = c.get("/api/giocatore/1").json()["previsione"]
    assert p["giornata"] == 10 and p["giornata_lega"] == 7
    # dopo la scadenza la scheda passa da fasi.schede_a_giornata_iniziata: il numero della lega resta
    monkeypatch.setattr(fasi, "iniziata", lambda *a, **k: True)
    monkeypatch.setattr(fasi, "schede_a_giornata_iniziata", lambda schede, *a, **k: {s["id"]: s | {"stato_partita": "da_giocare"} for s in schede})
    p = c.get("/api/giocatore/1").json()["previsione"]
    assert p["giornata_lega"] == 7 and p["stato_partita"] == "da_giocare"


def test_rotta_confronto_porta_giornata_lega(tmp_path, monkeypatch, finto):
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(server, "_regole", lambda ctx: LEGA_DA_4)
    r = TestClient(server.app, headers={"X-Fanta": "1"}).get("/api/confronto?a=1&b=2").json()
    assert r["giornata"] == 10 and r["giornata_lega"] == 7
