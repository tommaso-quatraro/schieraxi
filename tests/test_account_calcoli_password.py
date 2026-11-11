"""Il calcolo delle password (scrypt) ha pochi posti: chi li trova pieni aspetta, ma solo fino a un tetto di richieste in attesa;
oltre riceve subito «riprova» (429) senza tenere occupato un thread del server. Un accesso respinto perché il server è occupato
non conta come tentativo sbagliato. Cartelle temporanee e dati finti."""
import threading
import time

import pytest

from fanta import account

from test_account_http import PASSWORD, cliente, invito


def _aspetta(condizione, secondi: float) -> bool:
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        if condizione():
            return True
        time.sleep(0.01)
    return condizione()


def test_account_calcoli_password_oltre_le_attese_ammesse_rispondono_subito(monkeypatch):
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 4, "r": 8, "p": 1})
    monkeypatch.setattr(account, "ATTESE_MASSIME", 1, raising=False)
    posti = threading.BoundedSemaphore(1)
    monkeypatch.setattr(account, "_calcoli", posti)
    posti.acquire()                                          # l'unico posto è occupato da un calcolo lungo
    esiti = {}

    def calcola(nome):
        try:
            account.hash_password("una-password-lunga")
            esiti[nome] = "fatto"
        except account.ErroreAccount as e:
            esiti[nome] = (e.stato, e.riprova_tra)
    primo = threading.Thread(target=calcola, args=("primo",))
    secondo = threading.Thread(target=calcola, args=("secondo",))
    try:
        primo.start()
        _aspetta(lambda: getattr(account, "_attese", 0) >= 1, 2.0)          # il primo aspetta il posto
        secondo.start()
        secondo.join(3)
        finito_subito = not secondo.is_alive()
    finally:
        posti.release()
        primo.join(30)
        secondo.join(40)
    assert finito_subito, "la seconda richiesta è rimasta ad aspettare"
    assert esiti["secondo"][0] == 429 and esiti["secondo"][1] >= 1
    assert esiti["primo"] == "fatto"                          # chi era in attesa fa il suo calcolo appena il posto si libera
    assert account._attese == 0


def test_account_accesso_con_i_calcoli_occupati_non_conta_come_sbagliato(multiutente, dati_isolati, monkeypatch):
    c = cliente()
    assert c.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()}).status_code == 200
    vero = account._scrypt

    def occupato(*a, **k):
        raise account.ErroreAccount("Il server è molto occupato: riprova fra qualche secondo", 503, 5)
    monkeypatch.setattr(account, "_scrypt", occupato)
    for _ in range(6):
        r = cliente().post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
        assert r.status_code in (429, 503)
    monkeypatch.setattr(account, "_scrypt", vero)
    r = cliente().post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert r.status_code == 200, r.text                      # nessuna attesa crescente per colpa del server occupato


@pytest.mark.parametrize("attese", [0])
def test_account_registrazione_con_i_calcoli_pieni_risponde_429(multiutente, dati_isolati, monkeypatch, attese):
    monkeypatch.setattr(account, "ATTESE_MASSIME", attese, raising=False)
    posti = threading.BoundedSemaphore(1)
    monkeypatch.setattr(account, "_calcoli", posti)
    posti.acquire()
    try:
        inizio = time.monotonic()
        r = cliente().post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()})
        durata = time.monotonic() - inizio
    finally:
        posti.release()
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and durata < 5
    assert "riprova" in r.json()["detail"]
