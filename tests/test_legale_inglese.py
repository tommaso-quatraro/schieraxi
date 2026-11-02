"""Privacy, Termini, Crediti ed Elimina-account in inglese (?lingua=en): stessa struttura dell'italiano, nota «traduzione», link all'italiano."""
import pytest
from fastapi.testclient import TestClient

from fanta import server
from fanta import testi_legali as tl


def cliente() -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_l_inglese_ha_le_stesse_chiavi_e_la_stessa_struttura_dell_italiano():
    it, en = tl.TESTI["it"], tl.TESTI["en"]
    assert set(en) - {"traduzione_nota", "versione_italiana"} == set(it)             # solo in inglese: la nota «traduzione» e il rimando
    for pagina in tl.PAGINE:
        assert [b[0] for b in en[pagina]] == [b[0] for b in it[pagina]], pagina       # stessi blocchi, nello stesso ordine
        for bi, be in zip(it[pagina], en[pagina]):
            if bi[0] == "li":
                assert len(bi[1]) == len(be[1]), pagina
    segnaposto = ("{contatto}", "{titolare}", "{eta}", "{backup}", "{iscrizione}", "{email}")
    for pagina in tl.PAGINE:
        assert all(s in str(en[pagina]) for s in segnaposto if s in str(it[pagina])), pagina


@pytest.mark.parametrize("percorso", ["/privacy", "/termini", "/crediti", "/elimina-account"])
def test_pagine_in_inglese(percorso, multiutente, dati_isolati):
    r = cliente().get(percorso + "?lingua=en")
    assert r.status_code == 200 and 'lang="en"' in r.text
    assert "English translation" in r.text and f'href="{percorso}"' in r.text         # nota e rimando alla versione italiana
    assert "?lingua=en" in r.text                                                     # i link agli altri documenti restano in inglese
    assert "<script>" not in r.text


def test_senza_lingua_o_con_una_sconosciuta_resta_italiano(multiutente, dati_isolati):
    for q in ("", "?lingua=de", "?lingua=<x>"):
        r = cliente().get("/privacy" + q)
        assert 'lang="it"' in r.text and "English translation" not in r.text
