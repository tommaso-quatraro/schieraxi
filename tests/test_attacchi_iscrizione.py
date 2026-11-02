"""Attacchi all'iscrizione con email (modi `aperta` ed `email`): ogni test riproduce un attacco trovato in revisione.
Tutto su cartelle temporanee, posta finta."""
import contextlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from fanta import account, account_email, posta

from test_account_http import PASSWORD, cliente, invito
from test_account_email import codice_di, ultimi

ALTRA = "lupo rosso monte"


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)                # le email «partono» (le raccoglie la lista qui sopra)
    return messaggi


@pytest.fixture
def aperta(multiutente, dati_isolati, posta_finta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    return posta_finta


def iscrivi(ip, nome, email, password=PASSWORD, **extra):
    c = cliente(**{"X-Forwarded-For": ip})
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": password, "email": email} | extra)
    return c, r


def utenti() -> list[str]:
    with contextlib.closing(account.apri()) as db:
        return [u["nome_utente"] for u in account.elenco(db)]


# ---------------------------------------------------------------- (1) seconda iscrizione con la stessa email
def test_seconda_iscrizione_con_la_stessa_email_non_ruba_l_account(aperta):
    """prova1: la vittima si iscrive, l'attaccante ripete con la stessa email e un nome suo; la vittima usa l'ultimo codice
    arrivato. Prima: nasceva l'account dell'ATTACCANTE (con la sua password) sull'email della vittima."""
    vittima, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    attaccante, r2 = iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    assert r1.status_code == r2.status_code == 200
    assert r1.json().keys() == r2.json().keys()                                  # risposta della stessa forma
    for m in ultimi(aperta, "v@esempio.it"):                                     # ogni email dice per quale nome è il codice
        assert re.search(r"«(vittima|attaccante)»", m.testo)
    codice_vittima = next(codice_di(m) for m in aperta if "«vittima»" in m.testo)
    ok = vittima.post("/api/account/registra/conferma",
                      json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r1.json()["iscrizione"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["utente"]["nome_utente"] == "vittima" and utenti() == ["vittima"]
    entra = cliente(**{"X-Forwarded-For": "2.2.2.2"}).post("/api/account/accedi", json={"nome_utente": "attaccante", "password": ALTRA})
    assert entra.status_code == 401
    assert cliente().post("/api/account/accedi", json={"nome_utente": "vittima", "password": PASSWORD}).status_code == 200


def test_il_codice_della_vittima_non_vale_con_il_segreto_dell_attaccante(aperta):
    """Anche se l'attaccante indovinasse o leggesse il codice della vittima, gli serve il SUO segreto: il codice è legato
    all'iscrizione che l'ha generato."""
    _, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    attaccante, r2 = iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    codice_vittima = next(codice_di(m) for m in aperta if "«vittima»" in m.testo)
    r = attaccante.post("/api/account/registra/conferma",
                        json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r2.json()["iscrizione"]})
    assert r.status_code == 403 and utenti() == []


def test_senza_segreto_o_con_segreto_inventato_non_si_conferma(aperta):
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    codice = codice_di(aperta[-1])
    for segreto in (None, "", "x" * 40):
        corpo = {"email": "anna@example.com", "codice": codice} | ({"iscrizione": segreto} if segreto is not None else {})
        assert c.post("/api/account/registra/conferma", json=corpo).status_code == 403
    assert utenti() == []


def test_una_nuova_richiesta_non_annulla_l_iscrizione_in_attesa_di_un_altro(aperta):
    _, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    codice_vittima = codice_di(aperta[-1])
    iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    ok = cliente().post("/api/account/registra/conferma",
                        json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r1.json()["iscrizione"]})
    assert ok.status_code == 200 and utenti() == ["vittima"]


def test_email_gia_registrata_risposta_con_segreto_finto(aperta):
    """Anche quando non parte nessun codice la risposta ha il segreto: dalla risposta non si capisce se l'indirizzo è libero."""
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    c.post("/api/account/registra/conferma", json={"email": "anna@example.com", "codice": codice_di(aperta[-1]),
                                                   "iscrizione": r.json()["iscrizione"]})
    _, gia = iscrivi("1.1.1.2", "bruno", "anna@example.com")
    _, libera = iscrivi("1.1.1.3", "carla", "carla@example.com")
    assert gia.json().keys() == libera.json().keys()
    assert len(gia.json()["iscrizione"]) == len(libera.json()["iscrizione"])


# ---------------------------------------------------------------- (5) modo aperta: indirizzi con +etichetta, tetto al giorno
def test_aperta_nome_piu_etichetta_vale_come_l_indirizzo_base(aperta):
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    c.post("/api/account/registra/conferma", json={"email": "anna@example.com", "codice": codice_di(aperta[-1]),
                                                   "iscrizione": r.json()["iscrizione"]})
    aperta.clear()
    _, r2 = iscrivi("1.1.1.2", "anna2", "Anna+secondo@example.com")
    assert r2.status_code == 200
    assert aperta and "già un account" in aperta[-1].oggetto                     # nessun codice: l'indirizzo base ha già un account


def test_aperta_le_varianti_piu_etichetta_condividono_il_limite_di_invii(aperta):
    for i in range(account_email.INVII_PER_EMAIL[0] + 2):
        iscrivi(f"1.1.2.{i}", f"nome{i}", f"base+t{i}@example.com")
    assert len([m for m in aperta if re.search(r"\b\d{6}\b", m.testo)]) == account_email.INVII_PER_EMAIL[0]


def test_aperta_tetto_giornaliero_di_account_nuovi(aperta, monkeypatch):
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "2")
    for i in range(2):
        c, r = iscrivi(f"1.1.3.{i}", f"nuovo{i}", f"n{i}@example.com")
        assert c.post("/api/account/registra/conferma", json={"email": f"n{i}@example.com", "codice": codice_di(aperta[-1]),
                                                              "iscrizione": r.json()["iscrizione"]}).status_code == 200
    _, terzo = iscrivi("1.1.3.9", "nuovo9", "n9@example.com")
    assert terzo.status_code == 403 and "domani" in terzo.json()["detail"]
    with contextlib.closing(account.apri()) as db:                               # passato un giorno si riapre
        ieri = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
        db.execute("UPDATE utenti SET creato = ?", (ieri,))
        db.commit()
    assert iscrivi("1.1.3.9", "nuovo9", "n9@example.com")[1].status_code == 200


def test_tetto_giornaliero_non_tocca_il_modo_invito(multiutente, dati_isolati, posta_finta, monkeypatch):
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "1")
    for nome in ("uno", "due", "tre"):
        r = cliente().post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": invito()})
        assert r.status_code == 200
