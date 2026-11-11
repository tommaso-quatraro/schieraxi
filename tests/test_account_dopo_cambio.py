"""Dopo un cambio di password, un recupero (codice, email, codice dell'amministratore) e «Esci da tutti»: codice di recupero nuovo,
notifiche web solo sul dispositivo che ha fatto il cambio, avviso all'email verificata. Cartelle temporanee e dati finti."""
import contextlib
import re

import pytest

from fanta import account, contesto, posta, push

from test_account_http import PASSWORD, cliente, invito

NUOVA = "nuova-password-lunga-7"
CHIAVI = {"p256dh": "P" * 40, "auth": "A" * 20}


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


def registra(c, nome="marco") -> dict:
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200, r.text
    return r.json()


def entra(nome="marco", password=PASSWORD):
    c = cliente()
    assert c.post("/api/account/accedi", json={"nome_utente": nome, "password": password}).status_code == 200
    return c


def iscrivi(c, sito: str) -> str:
    ep = f"https://{sito}.example.org/push/{sito}"
    r = c.post("/api/push/iscrivi", json={"endpoint": ep, "keys": CHIAVI})
    assert r.status_code == 200, r.text
    return ep


def notifiche_di(utente_id: int) -> list[str]:
    return [s["endpoint"] for s in push.iscrizioni(contesto.Contesto.per_utente(utente_id).iscrizioni_push)]


def codice_valido(codice) -> bool:
    return isinstance(codice, str) and len(codice.replace("-", "")) == 20


def recupera(codice, nuova=NUOVA, nome="marco", **extra):
    return cliente().post("/api/account/recupero", json={"nome_utente": nome, "codice": codice, "nuova": nuova} | extra)


def cambia(c, attuale=PASSWORD, nuova=NUOVA, **extra):
    return c.post("/api/account/cambia-password", json={"attuale": attuale, "nuova": nuova} | extra)


def codice_generato_altrove(c, password=PASSWORD) -> str:
    """Un codice di recupero generato da un altro dispositivo dello stesso account."""
    r = c.post("/api/account/codice-recupero", json={"password": password})
    assert r.status_code == 200, r.text
    return r.json()["codice_recupero"]


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)
    return messaggi


def con_email(c, posta_finta, email="marco@example.com"):
    assert c.post("/api/account/email", json={"email": email, "password": PASSWORD}).status_code == 200
    codice = re.search(r"\b(\d{6})\b", posta_finta[-1].testo).group(1)
    assert c.post("/api/account/email/conferma", json={"codice": codice}).status_code == 200
    posta_finta.clear()


# ================================================================ codice di recupero nuovo
def test_account_cambio_password_da_un_codice_di_recupero_nuovo(web):
    registra(web)
    altro = entra()
    vecchio = codice_generato_altrove(altro)
    r = cambia(web)
    assert r.status_code == 200, r.text
    nuovo = r.json().get("codice_recupero")
    assert codice_valido(nuovo) and nuovo != vecchio
    assert recupera(vecchio).status_code == 403                    # il codice di prima non vale più
    assert recupera(nuovo, "ancora-un-altra-pw-3").status_code == 200


def test_account_esci_da_tutti_cambia_il_codice_di_recupero(web):
    registra(web)
    vecchio = codice_generato_altrove(entra())
    r = web.post("/api/account/esci-da-tutti")                      # come prima: senza corpo
    assert r.status_code == 200, r.text
    assert "codice_recupero" not in r.json()                        # senza la password il codice nuovo non si mostra
    assert recupera(vecchio).status_code == 403


def test_account_esci_da_tutti_con_la_password_mostra_il_codice_nuovo(web):
    registra(web)
    vecchio = codice_generato_altrove(entra())
    r = web.post("/api/account/esci-da-tutti", json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    nuovo = r.json()["codice_recupero"]
    assert codice_valido(nuovo) and r.json()["sessioni_chiuse"] >= 1
    assert recupera(vecchio).status_code == 403
    assert recupera(nuovo).status_code == 200


def test_account_esci_da_tutti_con_la_password_sbagliata_non_chiude_niente(web):
    registra(web)
    altro = entra()
    r = web.post("/api/account/esci-da-tutti", json={"password": "sbagliata-sbagliata"})
    assert r.status_code == 403
    assert altro.get("/api/account/me").status_code == 200


# ================================================================ notifiche web
def test_account_cambio_password_tiene_solo_le_notifiche_di_questo_dispositivo(web):
    uid = registra(web)["utente"]["id"]
    mio = iscrivi(web, "telefono")
    iscrivi(entra(), "altro")
    assert len(notifiche_di(uid)) == 2
    assert cambia(web, endpoint_push=mio).status_code == 200
    assert notifiche_di(uid) == [mio]


def test_account_cambio_password_senza_dispositivo_toglie_tutte_le_notifiche(web):
    uid = registra(web)["utente"]["id"]
    iscrivi(web, "telefono")
    iscrivi(entra(), "altro")
    assert cambia(web).status_code == 200
    assert notifiche_di(uid) == []


def test_account_cambio_password_non_tiene_un_indirizzo_che_non_c_era(web):
    uid = registra(web)["utente"]["id"]
    iscrivi(entra(), "altro")
    assert cambia(web, endpoint_push="https://inventato.example.org/push/x").status_code == 200
    assert notifiche_di(uid) == []                                  # «tieni» non aggiunge niente


def test_account_esci_da_tutti_toglie_tutte_le_notifiche(web):
    uid = registra(web)["utente"]["id"]
    iscrivi(web, "telefono")
    iscrivi(entra(), "altro")
    assert web.post("/api/account/esci-da-tutti").status_code == 200
    assert notifiche_di(uid) == []


def test_account_recupero_con_codice_tiene_solo_le_notifiche_di_questo_dispositivo(web):
    corpo = registra(web)
    uid, codice = corpo["utente"]["id"], corpo["codice_recupero"]
    mio = iscrivi(web, "telefono")
    iscrivi(entra(), "altro")
    assert recupera(codice, endpoint_push=mio).status_code == 200
    assert notifiche_di(uid) == [mio]


def test_account_recupero_con_codice_dell_amministratore_toglie_le_notifiche(web):
    uid = registra(web)["utente"]["id"]
    iscrivi(entra(), "altro")
    with contextlib.closing(account.apri()) as db:
        reset = account.crea_reset(db, "marco")
    assert recupera(reset).status_code == 200
    assert notifiche_di(uid) == []


def test_account_recupero_con_email_tiene_solo_le_notifiche_di_questo_dispositivo(web, posta_finta):
    uid = registra(web)["utente"]["id"]
    con_email(web, posta_finta)
    mio = iscrivi(web, "telefono")
    iscrivi(entra(), "altro")
    anonimo = cliente()
    assert anonimo.post("/api/account/recupero-email", json={"email": "marco@example.com"}).status_code == 200
    codice = re.search(r"\b(\d{6})\b", posta_finta[-1].testo).group(1)
    r = anonimo.post("/api/account/recupero-email/conferma",
                     json={"email": "marco@example.com", "codice": codice, "nuova": NUOVA, "endpoint_push": mio})
    assert r.status_code == 200, r.text
    assert notifiche_di(uid) == [mio]


def test_account_le_notifiche_degli_altri_utenti_restano(web):
    registra(web)
    luca = cliente()
    uid_luca = registra(luca, "luca")["utente"]["id"]
    suo = iscrivi(luca, "luca")
    assert cambia(web).status_code == 200
    assert notifiche_di(uid_luca) == [suo]


def test_push_iscrizione_di_una_sessione_chiusa_nel_frattempo_non_resta(web, monkeypatch):
    """La sessione si chiude (cambio password altrove) mentre l'iscrizione controlla il nome del servizio: non resta niente."""
    uid = registra(web)["utente"]["id"]
    altro = entra()

    def risolvi_e_intanto_cambia(host):
        assert cambia(web).status_code == 200
        return ["93.184.216.34"]
    monkeypatch.setattr(push, "_risolvi_host", risolvi_e_intanto_cambia)
    altro.post("/api/push/iscrivi", json={"endpoint": "https://tardi.example.org/push/x", "keys": CHIAVI})
    assert notifiche_di(uid) == []


# ================================================================ avviso all'email verificata
def test_account_cambio_password_avvisa_l_email_verificata(web, posta_finta):
    registra(web)
    con_email(web, posta_finta)
    assert cambia(web).status_code == 200
    avvisi = [m for m in posta_finta if m.a == "marco@example.com"]
    assert len(avvisi) == 1 and "password" in avvisi[0].oggetto.lower()
    assert "email" in avvisi[0].testo and NUOVA not in avvisi[0].testo and PASSWORD not in avvisi[0].testo


def test_account_recupero_con_codice_avvisa_l_email_verificata(web, posta_finta):
    codice = registra(web)["codice_recupero"]
    con_email(web, posta_finta)
    r = recupera(codice)
    assert r.status_code == 200
    avvisi = [m for m in posta_finta if m.a == "marco@example.com"]
    assert len(avvisi) == 1 and "password" in avvisi[0].oggetto.lower()
    assert r.json()["codice_recupero"].replace("-", "") not in avvisi[0].testo.replace("-", "")


def test_account_recupero_con_email_avvisa_l_email_verificata(web, posta_finta):
    registra(web)
    con_email(web, posta_finta)
    anonimo = cliente()
    anonimo.post("/api/account/recupero-email", json={"email": "marco@example.com"})
    codice = re.search(r"\b(\d{6})\b", posta_finta[-1].testo).group(1)
    posta_finta.clear()
    r = anonimo.post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": codice, "nuova": NUOVA})
    assert r.status_code == 200
    assert len(posta_finta) == 1 and "password" in posta_finta[0].oggetto.lower()


def test_account_cambio_password_senza_email_non_manda_niente(web, posta_finta):
    registra(web)
    assert cambia(web).status_code == 200
    assert posta_finta == []


def test_account_cambio_password_con_la_posta_spenta_va_bene(web, monkeypatch):
    monkeypatch.setenv("FANTA_MAIL", "spento")
    registra(web)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'marco@example.com'")
        db.commit()
    r = cambia(web)
    assert r.status_code == 200 and codice_valido(r.json()["codice_recupero"])
