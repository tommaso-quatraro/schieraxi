"""Collaudo del 2/11/2026 (giro 5): con l'app in inglese le letture tradotte hanno l'ETag con «-en» (server._etag_inglese).
Il web lo ricordava e lo rimandava in If-Match: ogni scrittura dopo (per esempio «This is mine» nel primo avvio, dopo che
l'app aveva letto le rose) riceveva 412 e la pagina si ricaricava. La copia inglese è la stessa versione dei dati."""
import pytest
from fastapi import HTTPException

from fanta import server, versioni

from test_etag import ROSE, etag, mondo  # noqa: F401 (fixture)
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)


class Richiesta:
    def __init__(self, valore):
        self.headers = {"if-match": valore}


def test_la_copia_inglese_vale_come_quella_italiana():
    versioni.controlla(Richiesta('"abc-en"'), '"abc"')
    versioni.controlla(Richiesta('W/"abc-en"'), '"abc"')
    versioni.controlla(Richiesta('"x", "abc-en"'), '"abc"')
    assert server._etag_inglese('"abc"') == '"abc-en"'                    # la forma che il server dà davvero


@pytest.mark.parametrize("vecchio", ['"vecchio-en"', '"abc-enx"', '"abcen"', '"abc-it"'])
def test_una_versione_vecchia_in_inglese_resta_un_conflitto(vecchio):
    with pytest.raises(HTTPException) as e:
        versioni.controlla(Richiesta(vecchio), '"abc"')
    assert e.value.status_code == 412


def test_scrivere_con_l_etag_inglese_delle_rose_e_dei_seguiti(mondo):
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    inglese = etag(a.get("/api/squadre"))[:-1] + '-en"'                  # come lo ricorda il web dopo una lettura tradotta
    assert a.put("/api/mia-squadra", json={"nome": "Altra"}, headers={"If-Match": inglese}).status_code == 200
    assert a.put("/api/mia-squadra", json={"nome": "Mia"}, headers={"If-Match": inglese}).status_code == 412   # ora è vecchio davvero
    seguiti = etag(a.get("/api/osservati"))[:-1] + '-en"'
    assert a.put("/api/osservati/1", headers={"If-Match": seguiti}).status_code == 200
