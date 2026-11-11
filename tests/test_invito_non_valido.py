"""Invito non valido, scaduto, revocato o già usato (#580): chi si iscrive riceve un messaggio solo, che dice cosa fare
(chiederne uno nuovo a chi l'ha mandato) senza dire quale dei casi è (non si scopre se un codice esiste)."""
import contextlib
import json
from pathlib import Path

import pytest

from fanta import account, rotte_account

from test_account_http import PASSWORD, cliente, invito


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente(**{"X-Forwarded-For": "4.4.4.4"})


def registra(c, nome, codice):
    return c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": codice, "accetto_termini": True})


def test_il_messaggio_dice_di_chiedere_un_invito_nuovo():
    assert "chiedine uno nuovo a chi te l'ha mandato" in rotte_account.INVITO_DA_CHIEDERE
    assert "già usato" in rotte_account.INVITO_DA_CHIEDERE and "scaduto" in rotte_account.INVITO_DA_CHIEDERE


def test_il_messaggio_ha_la_sua_traduzione():
    """La web traduce i messaggi del server con le chiavi err.* (il testo italiano della chiave è il messaggio, parola per parola)."""
    catalogo = json.loads((Path(__file__).resolve().parent.parent / "fanta" / "testi" / "err.json").read_text(encoding="utf-8"))
    voci = [v for v in catalogo.values() if v["it"] == rotte_account.INVITO_DA_CHIEDERE]
    assert len(voci) == 1 and voci[0]["en"] and voci[0]["en"] != voci[0]["it"]


def test_invito_gia_usato(web):
    codice = invito()
    assert registra(web, "marco", codice).status_code == 200
    r = registra(cliente(**{"X-Forwarded-For": "5.5.5.5"}), "luca", codice)
    assert r.status_code == 403 and r.json() == {"detail": rotte_account.INVITO_DA_CHIEDERE}


def test_invito_che_non_esiste_stesso_messaggio(web):
    r = registra(web, "luca", "ABCDE-FGHIJ-KLMNO-PQRST")
    assert r.status_code == 403 and r.json() == {"detail": rotte_account.INVITO_DA_CHIEDERE}


def test_invito_revocato_stesso_messaggio(web):
    codice = invito()
    with contextlib.closing(account.apri()) as db:
        account.revoca_invito(db, account.elenco_inviti(db)[0]["id"])
    r = registra(web, "luca", codice)
    assert r.status_code == 403 and r.json() == {"detail": rotte_account.INVITO_DA_CHIEDERE}


def test_gli_altri_errori_restano_com_erano(web):
    """Solo l'invito cambia messaggio: il nome già preso si dice come sempre."""
    assert registra(web, "marco", invito()).status_code == 200
    r = registra(cliente(**{"X-Forwarded-For": "5.5.5.5"}), "marco", invito())
    assert r.status_code == 400 and "già preso" in r.json()["detail"]
