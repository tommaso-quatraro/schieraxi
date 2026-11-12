"""La prima schermata della web nelle tre fasi della giornata (prima della scadenza, in corso, finita), in Chrome vero.

Valgono per ogni versione della web: nessun selettore né testo di una schermata, solo ciò che una web sana fa sempre.
Ogni test gira una volta per fase (fixture `web`, tests/browser/conftest.py)."""
import pytest

pytestmark = pytest.mark.browser

LARGHEZZE = [390, 1440]
TEMI = ["chiaro", "scuro"]


def _elenco(voci) -> str:
    return "\n  " + "\n  ".join(voci)


@pytest.mark.parametrize("tema", TEMI)
@pytest.mark.parametrize("larghezza", LARGHEZZE)
def test_si_apre_senza_errori_della_console(web, larghezza, tema):
    web.apri("/", larghezza=larghezza, tema=tema)
    assert web.testo_visibile(), f"{web.fase}: la prima schermata è vuota"
    assert not web.errori_console, f"{web.fase}: errori nella console:{_elenco(web.errori_console)}"


@pytest.mark.parametrize("tema", TEMI)
@pytest.mark.parametrize("larghezza", LARGHEZZE)
def test_si_apre_senza_richieste_fallite(web, larghezza, tema):
    web.apri("/", larghezza=larghezza, tema=tema)
    assert not web.richieste_fallite, (f"{web.fase}: richieste fallite:{_elenco(web.richieste_fallite)}\n"
                                       "Una rotta che manca nello scenario registrato risponde 404: tests/browser/LEGGIMI.md")


@pytest.mark.parametrize("tema", TEMI)
def test_a_390_px_niente_scorrimento_di_lato(web, tema):
    web.apri("/", larghezza=390, tema=tema)
    assert not web.scorre_di_lato(), f"{web.fase}: a 390 px la pagina è più larga dello schermo"


@pytest.mark.parametrize("tema", TEMI)
@pytest.mark.parametrize("larghezza", LARGHEZZE)
def test_nessuna_violazione_grave_di_accessibilita(web, larghezza, tema):
    web.apri("/", larghezza=larghezza, tema=tema)
    gravi = web.violazioni_gravi()
    assert not gravi, f"{web.fase}: violazioni gravi di axe:" + _elenco(
        f"{v['impact']} {v['id']} ({v['help']}), {v['n']} elementi: {', '.join(v['nodi'])}" for v in gravi)
