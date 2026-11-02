"""Nella copia pubblica ogni fonte di terzi e' spenta finche' non la si accende (FANTA_FONTE_<NOME>=1 o impostazione dell'amministratore);
c'e' un solo interruttore (fanta/fonti_attive.py) e l'agente e' onesto."""
import sqlite3

import pytest

from fanta import fonti_attive, listone, live, rete
from fanta.aggiorna import Aggiornamento, Stagione


@pytest.fixture
def spente(monkeypatch):
    for k in fonti_attive.FONTI:
        monkeypatch.delenv(f"FANTA_FONTE_{k.upper()}", raising=False)
    for v in ("FANTA_LIVE", "FANTA_FOTO"):
        monkeypatch.delenv(v, raising=False)


def test_predefinito_spento_per_tutte_le_fonti(spente):
    assert fonti_attive.PREDEFINITO_ACCESO is False
    assert not any(fonti_attive.acceso(k) for k in fonti_attive.FONTI)


def test_il_listone_senza_fonte_e_senza_copia_locale_si_ferma(spente, monkeypatch, tmp_path):
    monkeypatch.setattr(listone.requests, "get", lambda *a, **k: pytest.fail("rete usata"))
    with pytest.raises(fonti_attive.FonteSpenta):
        listone.carica(aggiorna=True, file_cache=tmp_path / "listone.json")


def test_il_live_senza_fonte_non_fa_richieste(spente, monkeypatch):
    monkeypatch.setattr(live.requests, "get", lambda *a, **k: pytest.fail("rete usata"))
    with pytest.raises(fonti_attive.FonteSpenta):
        live._scarica_http("https://example.org/")


def test_i_passi_di_aggiornamento_si_saltano(spente):
    righe = []
    a = Aggiornamento(sqlite3.connect(":memory:"), Stagione(2026), righe.append)
    a._passo("Understat", lambda: pytest.fail("eseguito"), "understat")
    assert not a.errori and "spenta" in righe[0]


def test_con_la_variabile_la_fonte_si_accende(spente, monkeypatch):
    monkeypatch.setenv("FANTA_FONTE_ESPN", "1")
    assert fonti_attive.acceso("espn") and not fonti_attive.acceso("understat")


def test_agente_onesto():
    for ua in (rete.UA, listone.UA["User-Agent"]):
        assert ua.startswith("SchieraXI/") and "Mozilla" not in ua
