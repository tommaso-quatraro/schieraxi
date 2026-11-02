"""Lingua dei testi del server: italiano di default, inglese con ?lingua=en o Accept-Language."""
from types import SimpleNamespace

import pytest

from fanta import lingua


def _richiesta(query=None, accept=None):
    return SimpleNamespace(query_params=query or {}, headers={"accept-language": accept} if accept else {})


@pytest.mark.parametrize("valore,atteso", [
    (None, "it"), ("", "it"), ("it-IT,it;q=0.9", "it"), ("en", "en"), ("en-US,en;q=0.9", "en"),
    ("fr, en;q=0.5", "it"), ("fr;q=0.2, en;q=0.8", "en"), ("*", "it"), ("en;q=0", "it"), ("en;q=abc", "it"), ("english", "it"),
])
def test_intestazione(valore, atteso):
    assert lingua.da_intestazione(valore) == atteso


def test_parametro_vince_sull_intestazione():
    assert lingua.della_richiesta(_richiesta({"lingua": "it"}, "en")) == "it"
    assert lingua.della_richiesta(_richiesta({"lingua": "en"}, "it")) == "en"
    assert lingua.della_richiesta(_richiesta({"lingua": "xx"}, "en")) == "en"      # parametro sconosciuto: si guarda l'intestazione
    assert lingua.della_richiesta(_richiesta()) == "it"
