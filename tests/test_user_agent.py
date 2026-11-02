"""Le fonti si presentano con un User-Agent onesto (nome, versione, contatto), mai come un browser."""
import pytest

from fanta import listone, live, rete


def test_agente_onesto_con_versione_e_contatto(monkeypatch):
    monkeypatch.delenv("FANTA_CONTATTO", raising=False)
    ua = rete.agente_onesto()
    assert ua.startswith("SchieraXI/") and "(+contatti@schieraxi.it)" in ua and "Mozilla" not in ua
    assert rete._versione() != "0"


def test_contatto_dall_ambiente_ripulito(monkeypatch):
    monkeypatch.setenv("FANTA_CONTATTO", "aiuto@example.org\r\nX-Altro: 1")
    ua = rete.agente_onesto()
    assert "\n" not in ua and "\r" not in ua
    assert "aiuto@example.org" in ua


def test_tutte_le_fonti_usano_lo_stesso_agente():
    assert rete._sessione.headers["User-Agent"] == rete.UA
    assert listone.UA["User-Agent"] == rete.UA
    assert live.UA == rete.UA
    foto = pytest.importorskip("fanta.foto")               # nella versione pubblica le foto non ci sono
    assert foto.IDENTITA["User-Agent"] == rete.UA
