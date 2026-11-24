"""La copia salvata nel browser quando il server risponde con un errore (#845): la nota in cima alla pagina dice il motivo e
anche di quando è la copia, con la data della copia e non quella di adesso.

Prima diceva solo «(dati salvati, potrebbero non essere aggiornati)»: con una copia di tre giorni prima e il server che
risponde 502 o 429, nessun punto della schermata diceva l'età dei dati. La stessa frase, per lo stesso istante, la prova
l'iPhone (`DatiVecchiTests.testIlMotivoVaInTestaComeSullaWeb`): «17 nov alle 10:05».

Si guarda ciò che vede chi usa l'app (il testo dell'area principale e il pulsante), non il sorgente.
"""
from urllib.parse import urlsplit

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


# ---------------------------------------------------------------- server spento o senza rete (#864)
OTTO = "2026-11-08T10:05:00"            # copia dell'8 novembre: in italiano «l'8 nov», con l'apostrofo
SENZA_RETE = {"it": "Non riesco a collegarmi: questi sono i dati salvati l'8 nov alle 10:05.",
              "en": "I cannot connect: this is the data saved on 8 Nov at 10:05."}
NOTA = "#nota-cache"
# Dove comincia il testo della nota e dove comincia il titolo (pixel da sinistra): allineati come il resto della pagina.
INIZI = """() => {
  const n = document.querySelector('#nota-cache > span'), h = document.querySelector('#titolo-pagina');
  const r = document.createRange(); r.selectNodeContents(n);
  return [r.getClientRects()[0].left, h.getBoundingClientRect().left];
}"""


def _solo_prima(web):
    if web.fase != "prima":
        pytest.skip("una fase basta: la nota non dipende dal momento della giornata")


def _server_giu(web, guasto: str) -> None:
    """Da qui ogni /api/ non arriva: il server spento («rifiuto», il collegamento è rifiutato) o fermo dietro il proxy
    («502», la sua pagina d'errore senza il JSON del server). La pagina e i suoi file arrivano."""
    def rispondi(route):
        if guasto == "502":
            route.fulfill(status=502, content_type="text/html", body="<html>502 Bad Gateway</html>")
        else:
            route.abort("connectionrefused")
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), rispondi)


def _riapri_dalla_copia(web, vista: str, guasto: str, larghezza: int = 390) -> None:
    """La copia si salva l'8 novembre alle 10:05; tre giorni dopo la pagina si riapre con il server giù."""
    web.orologio(OTTO)
    web.apri(vista, larghezza=larghezza)
    web.orologio(DOPO)
    _server_giu(web, guasto)
    web.apri(vista, larghezza=larghezza)
    web.pagina.locator(NOTA).get_by_role("button", name="Riprova").wait_for(timeout=10000)


@pytest.mark.parametrize("lingua", ["it", "en"])
@pytest.mark.parametrize("vista", ["/", GIORNATE])
def test_senza_rete_la_nota_dice_di_quando_e_la_copia(web, vista, lingua):
    """Con il server spento la nota diceva solo «Non riesco a collegarmi: questi sono gli ultimi dati salvati.», senza la data:
    con una copia di giorni prima nessun punto della pagina ne diceva l'età (l'iPhone la dice). Ora la data della copia, scritta
    come nella nota del 502 («l'8 nov alle 10:05»)."""
    _solo_prima(web)
    web.memoria({"lingua": lingua})
    _riapri_dalla_copia(web, vista, "rifiuto")
    nota = " ".join(web.pagina.locator(NOTA).inner_text().split())
    assert nota.startswith(SENZA_RETE[lingua]), nota


@pytest.mark.parametrize("larghezza", [390, 1440])
@pytest.mark.parametrize("guasto", ["rifiuto", "502"])
def test_con_il_server_giu_giornate_lo_dice_una_volta(web, guasto, larghezza):
    """Giornate con il server giù e la copia salvata: sotto il titolo la riga di stato diceva «Server non raggiungibile» e subito
    sotto la nota «Il server non risponde…» (o «Non riesco a collegarmi…»): lo stesso fatto due volte. Resta la nota, che dice
    anche di quando sono i dati e ha «Riprova»."""
    _solo_prima(web)
    _riapri_dalla_copia(web, GIORNATE, guasto, larghezza)
    testo = web.testo_principale()
    assert "Server non raggiungibile" not in testo, testo[:300]
    assert web.pagina.locator(NOTA).is_visible()


@pytest.mark.parametrize("vista", ["/", GIORNATE])
def test_senza_copia_e_con_il_server_giu_l_errore_si_dice_una_volta(web, vista):
    """Senza una copia salvata e con il server giù la pagina è l'errore con «Riprova» («Il server non risponde: riprova fra
    poco»): sopra, la riga di stato diceva anche «Server non raggiungibile». Resta l'errore."""
    _solo_prima(web)
    _server_giu(web, "rifiuto")
    web.apri(vista, larghezza=1440)
    assert web.errori_mostrati() == ["Il server non risponde: riprova fra poco"], web.errori_mostrati()
    assert "Server non raggiungibile" not in web.testo_principale(), web.testo_principale()[:300]


@pytest.mark.parametrize("larghezza", [390, 1440])
@pytest.mark.parametrize("vista", ["/", GIORNATE])
def test_la_nota_e_allineata_come_la_pagina(web, vista, larghezza):
    """La nota era centrata mentre titolo e contenuto sono allineati a sinistra: comincia dove comincia il titolo."""
    _solo_prima(web)
    _riapri_dalla_copia(web, vista, "502", larghezza)
    testo, titolo = web.pagina.evaluate(INIZI)
    assert abs(testo - titolo) <= 1, f"la nota comincia a {testo:.0f} px, il titolo a {titolo:.0f} px"
