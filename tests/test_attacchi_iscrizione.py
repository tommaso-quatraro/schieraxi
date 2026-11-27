"""Attacchi all'iscrizione con email (codice per posta prima che l'account nasca: dal 26/11/2026 solo il modo `email`, prima anche
`aperta`): ogni test riproduce un attacco trovato in revisione. Ogni iscrizione porta un invito suo. Tutto su cartelle temporanee,
posta finta. In fondo il tetto di account nuovi al giorno della registrazione aperta di adesso."""
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
def con_email(multiutente, dati_isolati, posta_finta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "email")
    return posta_finta


def iscrivi(ip, nome, email, password=PASSWORD, **extra):
    c = cliente(**{"X-Forwarded-For": ip})
    corpo = {"nome_utente": nome, "password": password, "email": email} | extra
    if account_email.modo_registrazione() == "email" and "invito" not in extra:
        corpo["invito"] = invito()
    r = c.post("/api/account/registra", json=corpo)
    return c, r


def utenti() -> list[str]:
    with contextlib.closing(account.apri()) as db:
        return [u["nome_utente"] for u in account.elenco(db)]


# ---------------------------------------------------------------- (1) seconda iscrizione con la stessa email
def test_seconda_iscrizione_con_la_stessa_email_non_ruba_l_account(con_email):
    """prova1: la vittima si iscrive, l'attaccante ripete con la stessa email e un nome suo; la vittima usa l'ultimo codice
    arrivato. Prima: nasceva l'account dell'ATTACCANTE (con la sua password) sull'email della vittima. Il codice è legato alla
    richiesta che l'ha fatto partire: quello dell'attaccante con il segreto della vittima non vale. Le email non dicono il nome
    scelto (lo scrive chiunque: sarebbe un testo suo spedito a un indirizzo a caso)."""
    vittima, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    attaccante, r2 = iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    assert r1.status_code == r2.status_code == 200
    assert r1.json().keys() == r2.json().keys()                                  # risposta della stessa forma
    codice_vittima, codice_attaccante = (codice_di(m) for m in ultimi(con_email, "v@esempio.it"))
    for m in ultimi(con_email, "v@esempio.it"):
        assert "vittima" not in m.testo and "attaccante" not in m.testo
    ultimo = vittima.post("/api/account/registra/conferma",
                          json={"email": "v@esempio.it", "codice": codice_attaccante, "iscrizione": r1.json()["iscrizione"]})
    assert ultimo.status_code == 403 and utenti() == []
    ok = vittima.post("/api/account/registra/conferma",
                      json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r1.json()["iscrizione"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["utente"]["nome_utente"] == "vittima" and utenti() == ["vittima"]
    entra = cliente(**{"X-Forwarded-For": "2.2.2.2"}).post("/api/account/accedi", json={"nome_utente": "attaccante", "password": ALTRA})
    assert entra.status_code == 401
    assert cliente().post("/api/account/accedi", json={"nome_utente": "vittima", "password": PASSWORD}).status_code == 200


def test_il_codice_della_vittima_non_vale_con_il_segreto_dell_attaccante(con_email):
    """Anche se l'attaccante indovinasse o leggesse il codice della vittima, gli serve il SUO segreto: il codice è legato
    all'iscrizione che l'ha generato."""
    _, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    attaccante, r2 = iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    codice_vittima = codice_di(ultimi(con_email, "v@esempio.it")[0])
    r = attaccante.post("/api/account/registra/conferma",
                        json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r2.json()["iscrizione"]})
    assert r.status_code == 403 and utenti() == []


def test_senza_segreto_o_con_segreto_inventato_non_si_conferma(con_email):
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    codice = codice_di(con_email[-1])
    for segreto in (None, "", "x" * 40):
        corpo = {"email": "anna@example.com", "codice": codice} | ({"iscrizione": segreto} if segreto is not None else {})
        assert c.post("/api/account/registra/conferma", json=corpo).status_code == 403
    assert utenti() == []


def test_una_nuova_richiesta_non_annulla_l_iscrizione_in_attesa_di_un_altro(con_email):
    _, r1 = iscrivi("1.1.1.1", "vittima", "v@esempio.it")
    codice_vittima = codice_di(con_email[-1])
    iscrivi("2.2.2.2", "attaccante", "v@esempio.it", ALTRA)
    ok = cliente().post("/api/account/registra/conferma",
                        json={"email": "v@esempio.it", "codice": codice_vittima, "iscrizione": r1.json()["iscrizione"]})
    assert ok.status_code == 200 and utenti() == ["vittima"]


def test_email_gia_registrata_risposta_con_segreto_finto(con_email):
    """Anche quando non parte nessun codice la risposta ha il segreto: dalla risposta non si capisce se l'indirizzo è libero."""
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    c.post("/api/account/registra/conferma", json={"email": "anna@example.com", "codice": codice_di(con_email[-1]),
                                                   "iscrizione": r.json()["iscrizione"]})
    _, gia = iscrivi("1.1.1.2", "bruno", "anna@example.com")
    _, libera = iscrivi("1.1.1.3", "carla", "carla@example.com")
    assert gia.json().keys() == libera.json().keys()
    assert len(gia.json()["iscrizione"]) == len(libera.json()["iscrizione"])


# ---------------------------------------------------------------- (5) indirizzi con +etichetta, tetto al giorno
def test_nome_piu_etichetta_vale_come_l_indirizzo_base(con_email):
    c, r = iscrivi("1.1.1.1", "anna", "anna@example.com")
    c.post("/api/account/registra/conferma", json={"email": "anna@example.com", "codice": codice_di(con_email[-1]),
                                                   "iscrizione": r.json()["iscrizione"]})
    con_email.clear()
    _, r2 = iscrivi("1.1.1.2", "anna2", "Anna+secondo@example.com")
    assert r2.status_code == 200
    assert con_email and "già un account" in con_email[-1].oggetto                     # nessun codice: l'indirizzo base ha già un account


def test_le_varianti_piu_etichetta_condividono_il_limite_di_invii(con_email):
    for i in range(account_email.INVII_PER_EMAIL[0] + 2):
        iscrivi(f"1.1.2.{i}", f"nome{i}", f"base+t{i}@example.com")
    assert len([m for m in con_email if re.search(r"\b\d{6}\b", m.testo)]) == account_email.INVII_PER_EMAIL[0]


def test_aperta_tetto_giornaliero_di_account_nuovi(multiutente, dati_isolati, posta_finta, monkeypatch):
    """Registrazione aperta di adesso (account subito, l'email facoltativa): al massimo FANTA_ISCRIZIONI_GIORNO account nuovi in 24 ore."""
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "2")
    for i in range(2):
        assert iscrivi(f"1.1.3.{i}", f"nuovo{i}", f"n{i}@example.com")[1].status_code == 200
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
