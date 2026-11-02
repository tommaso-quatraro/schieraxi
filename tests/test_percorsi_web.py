"""I testi che indicano dove trovare le cose devono dire il posto giusto: configurazione guidata e avvisi stanno in Impostazioni, non in Lega."""
from fanta import server
from testi_it import espandi


def _js(nome):
    return espandi((server.WEB / nome).read_text(encoding="utf-8"))


def test_configurazione_guidata_e_avvisi_rimandano_a_impostazioni():
    pa = _js("primoavvio.js")
    assert "quando vuoi da Lega" not in pa
    assert "in Impostazioni" in pa
