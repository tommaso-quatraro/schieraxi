"""La copia salvata nel browser quando il server risponde con un errore (#845): la nota in cima alla pagina dice il motivo e
anche di quando è la copia, con la data della copia e non quella di adesso.

Prima diceva solo «(dati salvati, potrebbero non essere aggiornati)»: con una copia di tre giorni prima e il server che
risponde 502 o 429, nessun punto della schermata diceva l'età dei dati. La stessa frase, per lo stesso istante, la prova
l'iPhone (`DatiVecchiTests.testIlMotivoVaInTestaComeSullaWeb`): «17 nov alle 10:05».

Si guarda ciò che vede chi usa l'app (il testo dell'area principale e il pulsante), non il sorgente.
"""
import pytest

GIORNATE = "/?vista=giornate"           # una pagina che si apre dalla copia salvata (come Formazione)
SALVATA = "2026-11-17T10:05:00"         # quando la pagina arriva dal server e se ne salva la copia (ora italiana)
DOPO = "2026-11-20T09:30:00"            # tre giorni dopo: si riapre e il server non risponde
FRASE = "Il server non risponde: riprova fra poco (dati salvati il 17 nov alle 10:05, potrebbero non essere aggiornati)"


def test_con_un_errore_del_server_la_nota_dice_di_quando_e_la_copia(web):
    if web.fase != "prima":
        pytest.skip("una fase basta: la nota non dipende dal momento della giornata")
    web.orologio(SALVATA)
    web.apri(GIORNATE)
    assert "potrebbero non essere aggiornati" not in web.testo_principale(), "la prima volta i dati arrivano dal server"

    web.orologio(DOPO)
    web.risposta("/api/diario", None, stato=502)         # la pagina d'errore del proxy, senza il JSON del server
    web.apri(GIORNATE)
    testo = " ".join(web.testo_principale().split())
    assert FRASE in testo, testo[:400]
    assert "20 nov" not in testo, "la data è quella della copia, non quella di adesso"
    assert web.pagina.locator("main").get_by_role("button", name="Riprova").first.is_visible()
