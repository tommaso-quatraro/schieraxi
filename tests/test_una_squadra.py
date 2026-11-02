"""Si comincia anche con la sola propria rosa (decisione del 2/11/2026, piano «Ingresso facile» S4): niente blocco «almeno due
squadre», solo un avviso gentile; scambi e mercato non vanno in errore e il web mostra uno stato vuoto chiaro. Dati finti."""
import dataclasses
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fanta import calcolo, consigli, lega, onboarding, server
from fanta.regole import Regole

from test_scambi import REGOLE, _rose, _valori, TAB

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
PRIMO = (WEB / "primoavvio.js").read_text(encoding="utf-8")


def _sola(rose: lega.Rose) -> lega.Rose:
    return lega.Rose([rose.squadre[0]], rose.squadre[0].nome)


def _per_id(voci):
    return {v["id"]: v for v in voci}


def test_i_controlli_del_primo_avvio_accettano_una_squadra():
    c = _per_id(onboarding.controlli(Regole(), _sola(_rose()), True))
    assert c["rose"]["ok"] and c["rose"]["obbligatorio"]
    assert c["altre_squadre"]["ok"] is False and c["altre_squadre"]["obbligatorio"] is False      # solo un avviso
    assert c["altre_squadre"]["dettaglio"] == lega.UNA_SQUADRA and "scambi" in lega.UNA_SQUADRA
    assert all(v["ok"] for v in c.values() if v["obbligatorio"])                                  # si va avanti
    due = _per_id(onboarding.controlli(Regole(), _rose(), True))
    assert due["rose"]["ok"] and due["altre_squadre"]["ok"] and due["altre_squadre"]["dettaglio"] == ""
    nessuna = _per_id(onboarding.controlli(Regole(), None, True))
    assert not nessuna["rose"]["ok"] and nessuna["rose"]["dettaglio"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    calcolo.cache.clear()
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    (tmp_path / "regole.json").write_text(json.dumps(dataclasses.asdict(REGOLE)), encoding="utf-8")
    lega.salva(_sola(_rose()), tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: sqlite3.connect(":memory:"))
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: _valori(TAB))
    monkeypatch.setattr(consigli, "_versione", lambda db: "v1")
    yield TestClient(server.app, headers={"X-Fanta": "1"})
    calcolo.cache.clear()


def test_scambi_con_una_sola_squadra_rispondono_vuoti_senza_errori(client):
    assert [s["nome"] for s in client.get("/api/squadre").json()] == ["A"]
    r = client.get("/api/scambi/proposte")
    assert r.status_code == 200 and r.json()["proposte"] == []
    r = client.get("/api/scambi/analizza", params={"con": "B", "do": "10", "ricevo": "31"})
    assert r.status_code == 400 and "non trovata" in r.json()["detail"]                        # un messaggio, non un errore del server
    r = client.post("/api/scambi/da-testo", json={"testo": "Ti do g10, mi dai g31?"})
    assert r.status_code == 200 and r.json()["con"] is None and r.json()["analisi"] is None          # nessuno con cui scambiare


def test_l_anteprima_di_una_sola_squadra_avvisa_con_gentilezza(client, monkeypatch):
    from test_rose_csv import listone_finto
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_finto(range(1000, 1003)), "oggi"))
    a = client.post("/api/rose/anteprima", json={"testo": "Mia\nP\tGiocatore 1000\t1\n", "sostituisci_tutto": True}).json()
    assert a["totale_squadre"] == 1 and lega.UNA_SQUADRA in a["avvisi"] and a["mia_squadra"] == "Mia"


def test_il_web_non_blocca_e_spiega_cosa_manca():
    assert "servono_almeno_due" not in PRIMO and "totale_squadre < 2" not in PRIMO
    assert 'totale_squadre === 1) avviso(t("srv.una_sola_squadra")' in PRIMO
    # Scambi: con la sola tua rosa uno stato vuoto con il pulsante per aggiungere le altre (niente elenchi vuoti)
    assert 'squadre.length && !altre.length' in APP and 't("scambio.servono_altre")' in APP and 'vaiLega("importa")' in APP
    # Cambi consigliati: chi non è tuo risulta libero, ma potrebbe essere di un altro
    assert '(stato.squadre || []).length === 1 ? `<div class="attenzione">${t("mercato.senza_altre")}' in APP
