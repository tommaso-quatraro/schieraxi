"""L'apostrofo davanti all'8 e all'11 nelle date scritte con l'articolo (revisione della #852, #845): «dati dell'11 nov», «dati
salvati l'8 nov», mai «del 11» o «il 8» (in italiano si legge «dell'undici», «l'otto»). Le altre date restano («il 18 nov»).

Due frasi della web scrivono un giorno dopo l'articolo: la riga di stato sotto il titolo (`testata.dati_del`, dalla data dei dati
del server) e la nota della copia salvata quando il server risponde con un errore (`comune.cache_errore`). L'iPhone prova la
stessa forma nella sua frase (`DatiVecchiTests.testApostrofoDavantiAll8EAll11`).
"""
import pytest

GIORNATE = "/?vista=giornate"


def _solo_prima(web):
    if web.fase != "prima":
        pytest.skip("una fase basta: la data non dipende dal momento della giornata")


def _testo(web) -> str:
    return " ".join(web.testo_principale().split())


@pytest.mark.parametrize(("quando", "atteso"), [("2026-11-11T09:30:00", "dati dell'11 nov 09:30"),
                                                ("2026-11-08T21:05:00", "dati dell'8 nov 21:05"),
                                                ("2026-11-18T09:30:00", "dati del 18 nov 09:30")])
def test_la_riga_di_stato_mette_l_apostrofo_davanti_a_8_e_11(web, quando, atteso):
    _solo_prima(web)
    stato = web.registrata("/api/stato")
    stato["ultimo_aggiornamento"] = quando
    web.risposta("/api/stato", stato)
    web.apri(GIORNATE)
    testo = _testo(web)
    assert atteso in testo, testo[:300]


def test_la_nota_della_copia_mette_l_apostrofo_davanti_a_8(web):
    _solo_prima(web)
    web.orologio("2026-11-08T10:05:00")
    web.apri(GIORNATE)                                   # la copia si salva l'8 novembre alle 10:05
    web.orologio("2026-11-11T09:30:00")
    web.risposta("/api/diario", None, stato=502)
    web.apri(GIORNATE)
    testo = _testo(web)
    assert "(dati salvati l'8 nov alle 10:05, potrebbero non essere aggiornati)" in testo, testo[:400]
