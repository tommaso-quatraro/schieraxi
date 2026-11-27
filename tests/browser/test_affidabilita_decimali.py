"""Stato dei dati › «Quanto è affidabile il modello»: i numeri della stessa carta con le stesse cifre (collaudo del 27/11 sera).

«1,59» stava accanto a «1,6» e «63» accanto a «62,9»: la web scriveva il numero del server com'era e gli zeri in fondo sparivano.
Ora gli errori hanno sempre due cifre e i punti una, come sull'iPhone (`Formato.decimali`), con `num` (la regola di
`frasi.arrotonda`, che il server usa per la sintesi). La risposta qui sotto ha la forma di `affidabilita.sintesi`."""
import pytest

SINTESI = {"giornate": 8, "errore_modello": 1.59, "errore_fantamedia": 1.6, "errore_ruolo": 2.0, "errore_fantamedia_stagione": 1.7,
           "punti_modello": 63.0, "punti_fantamedia": 62.9, "punti_perfetta": 75.0}


def test_la_prova_del_modello_scrive_le_stesse_cifre_nella_carta(web):
    if web.fase != "prima":
        pytest.skip("una fase basta: Stato dei dati non dipende dal momento della giornata")
    web.risposta("/api/affidabilita", {"righe": [], "sintesi": SINTESI})
    web.apri("/?vista=impostazioni&gruppo=gestione")
    web.pagina.locator("main").get_by_role("button", name="Apri lo stato dei dati").click(timeout=10000)
    carta = web.pagina.get_by_role("dialog").locator(".carta", has=web.pagina.get_by_role("heading", name="Quanto è affidabile il modello"))
    carta.get_by_text("errore sui fantavoti (modello)").wait_for(timeout=10000)
    testo = " ".join(carta.inner_text().split())
    for atteso in ("1,59", "1,60", "63,0", "modello 63,0, da fantamedia 62,9, massimo possibile 75,0."):
        assert atteso in testo, (atteso, testo)
    assert "1,6 " not in testo and "63 " not in testo, testo
    assert not web.errori_console, web.errori_console
