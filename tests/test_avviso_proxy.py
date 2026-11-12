"""All'avvio, con gli account accesi e senza FANTA_PROXY=1, il registro del servizio dice chiaramente di impostarlo (il server
parte lo stesso). Niente rete, niente server vero."""
import pytest

from fanta import social

AVVISO = "FANTA_PROXY=1"


@pytest.fixture
def senza_google(monkeypatch):
    for nome in ("FANTA_GOOGLE_CLIENT_ID", "FANTA_GOOGLE_CLIENT_SECRET", "FANTA_GOOGLE_REDIRECT"):
        monkeypatch.delenv(nome, raising=False)


def test_avvio_multiutente_senza_proxy_scrive_un_avviso(senza_google, monkeypatch, caplog):
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.delenv("FANTA_PROXY", raising=False)
    with caplog.at_level("WARNING"):
        social.avvisa_se_manca_il_proxy()
    avvisi = [r for r in caplog.records if r.levelname == "WARNING" and AVVISO in r.getMessage()]
    assert len(avvisi) == 1


def test_avvio_multiutente_con_proxy_nessun_avviso(senza_google, monkeypatch, caplog):
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setenv("FANTA_PROXY", "1")
    with caplog.at_level("WARNING"):
        social.avvisa_se_manca_il_proxy()
    assert caplog.text == ""


def test_avvio_senza_account_nessun_avviso_sul_proxy(senza_google, monkeypatch, caplog):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.delenv("FANTA_PROXY", raising=False)
    with caplog.at_level("WARNING"):
        social.avvisa_se_manca_il_proxy()
    assert "FANTA_PROXY" not in caplog.text                  # senza account vale l'altro avviso (solo richieste da questo computer)
