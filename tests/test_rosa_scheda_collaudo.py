"""Collaudo del 2/11/2026 su Rosa e scheda del giocatore: regressioni dei difetti trovati."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, osservati, server
from fanta.frasi import F
import codice_web

WEB = Path(server.__file__).parent / "web"
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")


@pytest.fixture
def client(tmp_path, monkeypatch, calciatori):
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.osservati, "FILE_OSSERVATI", tmp_path / "oss.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    return TestClient(server.app, headers={"X-Fanta": "1"})


# ---------------------------------------------------------------- testi
def test_apostrofo_davanti_ai_numeri_che_iniziano_con_vocale():
    """Prima: «gioca solo il 1%: improbabile»."""
    assert F("perche.gioca_improbabile", p=1) == "gioca solo l'1%: improbabile"
    assert F("perche.gioca_dubbio", p=85) == "gioca l'85%: dubbio"
    assert F("perche.gioca_dubbio", p=11) == "gioca l'11%: dubbio"
    assert F("perche.gioca_dubbio", p=18) == "gioca il 18%: dubbio"                      # «il diciotto»: niente apostrofo
    assert F("perche.gioca_dubbio", p=79) == "gioca il 79%: dubbio"
    assert F("perche.gioca_dubbio", p=100) == "gioca il 100%: dubbio"
    assert F("senso.esce_pagato", nome="X", costo=3, p=80).endswith("solo l'80%.")
    assert F("perche.gioca_dubbio", p=8).json() == {"chiave": "perche.gioca_dubbio", "param": {"p": 8}}   # il numero resta com'era


def test_motivo_del_gol_e_la_probabilita_di_segnare():
    """Prima: «gol atteso 59%» (0,59 gol attesi scritti come percentuale) accanto a «segna 46%» nella stessa scheda."""
    base = {"stato": None, "percentuale": None, "nota": None, "e_rigori": 0.0, "ruolo": "A", "p_imbattuto": 0.0,
            "e_gol": 0.59, "p_gol": 0.46, "gol_squadra": 1.0, "gol_avversario": 1.0}
    assert "46% di segnare" in consigli.motivi(pd.Series(base))
    senza = {k: v for k, v in base.items() if k != "p_gol"}                                  # previsioni vecchie: dai gol attesi
    assert "45% di segnare" in consigli.motivi(pd.Series(senza))


def test_scheda_senza_sigle_e_rosa_con_gioca():
    for chiave in ("mercato.xg_90", "mercato.xa_90", "mercato.stagione_prec", "mercato.gol_attesi_tot", "mercato.assist_attesi_tot"):
        for testo in re.findall(rf'"{re.escape(chiave)}": "([^"]+)"', TESTI):
            assert "xG" not in testo and "xA" not in testo, (chiave, testo)
    assert 'tile(num(av.xg, 2), "xG")' not in APP and 'tile(num(av.xa, 2), "xA")' not in APP
    corpo = APP[APP.index("async function vistaRosa"):APP.index("const NOME_IMMAGINE")]
    assert "valoreRosa(p, x)" in corpo                                                       # una sola percentuale, «gioca N%»
    valore = APP[APP.index("function valoreRosa"):APP.index("// ---------------------------------------------------------------- navigazione")]
    assert 't("giocatore.gioca", { p: perc(p.p_voto) })' in valore
    scheda = APP[APP.index("async function apriGiocatore"):APP.index("// Il posto in formazione a parole")]
    assert "motiviUtili(pr).filter(senzaPercentuale)" in scheda                               # niente doppioni delle caselle


# ---------------------------------------------------------------- rotte
def test_scheda_e_osserva_con_numeri_enormi_non_danno_errore_500(client):
    assert client.get("/api/giocatore/99999999999999999999999").status_code == 422
    assert client.put("/api/osservati/99999999999999999999").status_code == 422
    assert client.put("/api/osservati/0").status_code == 422
    assert client.put("/api/osservati/-3").status_code == 422
    assert client.put("/api/osservati/abc").status_code == 422


def test_osservati_salvati_fuori_misura_si_saltano(tmp_path):
    """Un elenco salvato prima della correzione (numero enorme dentro) non deve bloccare la lettura per sempre."""
    f = tmp_path / "oss.json"
    f.write_text(json.dumps([5, 99999999999999999999, -1, 7]), encoding="utf-8")
    assert osservati.leggi(f) == [5, 7]
    assert osservati.aggiungi(9, f) == [5, 7, 9]


def test_rosa_dopo_la_scadenza_mostra_lo_stato_della_giornata(client, monkeypatch):
    """Prima: a giornata iniziata la Rosa diceva ancora «In ballottaggio · 72%» per partite già finite (la scheda e la
    Formazione mostravano già «Voto in arrivo»)."""
    client.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\nA\tKean\t30\n"})
    client.put("/api/mia-squadra", json={"nome": "Mia"})
    prev = pd.DataFrame({"nome": ["Sommer", "Kean"]}, index=[2, 14])
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, False))
    monkeypatch.setattr(server.consigli, "scheda_previsione",
                        lambda i, x: {"id": int(i), "nome": x["nome"], "titolarita": "ballottaggio", "motivi": ["titolare"]})
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {2: "attesa_voti", 14: "da_giocare"})
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    prima = {g["nome"]: g["previsione"] for g in client.get("/api/rosa").json()["giocatori"]}
    assert prima["Sommer"]["titolarita"] == "ballottaggio" and "stato_partita" not in prima["Sommer"]
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    dopo = {g["nome"]: g["previsione"] for g in client.get("/api/rosa").json()["giocatori"]}
    assert dopo["Sommer"]["titolarita"] is None and dopo["Sommer"]["stato_partita"] == "attesa_voti"
    assert dopo["Kean"]["stato_partita"] == "da_giocare" and dopo["Kean"]["motivi"] == []


def test_seguiti_dopo_la_scadenza_mostrano_lo_stato_della_giornata(client, monkeypatch):
    """Revisione 2/11: l'elenco dei Seguiti a partita iniziata diceva ancora «Probabile titolare» (la Rosa no)."""
    client.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\nA\tKean\t30\n"})
    client.put("/api/mia-squadra", json={"nome": "Mia"})
    monkeypatch.setattr(server.osservati, "leggi", lambda *a, **k: [2, 14])
    prev = pd.DataFrame({"nome": ["Sommer", "Kean"]}, index=[2, 14])
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, False))
    monkeypatch.setattr(server.consigli, "scheda_previsione",
                        lambda i, x: {"id": int(i), "nome": x["nome"], "titolarita": "titolare", "motivi": ["titolare"]})
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {2: "in_corso", 14: "attesa_voti"})
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    prima = {g["id"]: g for g in client.get("/api/osservati").json()["giocatori"]}
    assert prima[2]["titolarita"] == "titolare" and "stato_partita" not in prima[2]
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    dopo = {g["id"]: g for g in client.get("/api/osservati").json()["giocatori"]}
    assert dopo[2]["titolarita"] is None and dopo[2]["stato_partita"] == "in_corso" and dopo[2]["motivi"] == []
    assert dopo[14]["stato_partita"] == "attesa_voti" and dopo[14]["etichetta"]["codice"] != "titolare"
    assert dopo[2]["proprietario"] == "Mia"                                   # il resto della voce resta
