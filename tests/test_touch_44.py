"""Bersagli da tocco: i pulsanti di Regole (+/-, togli la fascia) e di Stemma (indirizzo web, rimuovi) sono almeno 44 px."""
import re

from fanta import server

CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def regola(selettore: str) -> str:
    m = re.search(r"^" + re.escape(selettore) + r"\s*\{([^}]*)\}", CSS, re.M)
    assert m, selettore
    return m.group(1)


def test_i_pulsanti_piu_meno_delle_regole_non_sono_piu_stretti():
    assert ".fascia .stepper button" not in CSS                                      # la riga con 30 px non c'è più
    assert re.search(r"width:\s*44px;\s*height:\s*44px", regola(".stepper button"))


def test_togli_la_fascia_e_i_pulsanti_stemma_sono_da_44():
    assert re.search(r"width:\s*44px;\s*height:\s*44px", regola(".rimuovi-fascia"))
    assert int(re.search(r"min-height:\s*(\d+)px", regola(".sm-pulsante")).group(1)) >= 44
