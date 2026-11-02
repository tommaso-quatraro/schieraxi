"""Registrazione configurabile (FANTA_REGISTRAZIONE = invito | aperta | email): ogni modo, con i suoi limiti e i suoi attacchi."""
import contextlib
import re

import pytest

from fanta import account, account_email, posta

from test_account_http import PASSWORD, cliente, invito, registra
from test_account_email import codice_di, ultimi


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    return messaggi


@pytest.fixture
def web(multiutente, dati_isolati, posta_finta):
    return cliente(**{"X-Forwarded-For": "4.4.4.4"})


def modo(monkeypatch, m):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", m)


_segreti: dict = {}        # l'ultimo segreto di iscrizione ricevuto per ogni indirizzo (come fa l'app)


def iscrivi(c, nome="anna", email="anna@example.com", **extra):
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "email": email} | extra)
    if r.status_code == 200 and "iscrizione" in r.json():
        _segreti[(email or "").lower()] = r.json()["iscrizione"]
    return r


def conferma(c, email, codice, **extra):
    corpo = {"email": email, "codice": codice, "iscrizione": _segreti.get(email.lower(), "")}
    return c.post("/api/account/registra/conferma", json=corpo | extra)


def utenti() -> list[str]:
    with contextlib.closing(account.apri()) as db:
        return [u["nome_utente"] for u in account.elenco(db)]


# ---------------------------------------------------------------- invito (predefinito)
def test_predefinito_e_invito(monkeypatch):
    monkeypatch.delenv("FANTA_REGISTRAZIONE", raising=False)
    assert account_email.modo_registrazione() == "invito"
    modo(monkeypatch, "boh")
    assert account_email.modo_registrazione() == "invito"


def test_invito_senza_invito_si_viene_respinti(web, posta_finta):
    r = iscrivi(web)
    assert r.status_code == 403 and r.json()["detail"] == account.INVITO_NON_VALIDO and utenti() == [] and not posta_finta
    ok = web.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()})
    assert ok.status_code == 200 and utenti() == ["marco"]


def test_il_modo_si_legge_dalla_risposta_401(web, monkeypatch):
    assert web.get("/api/regole").json()["registrazione"] == "invito"
    modo(monkeypatch, "aperta")
    assert web.get("/api/regole").json()["registrazione"] == "aperta"


# ---------------------------------------------------------------- aperta
def test_aperta_iscrizione_in_due_tempi(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    r = iscrivi(web)
    assert r.status_code == 200 and r.json()["verifica_email"] is True and "codice_recupero" not in r.json()
    assert utenti() == [] and web.get("/api/account/me").status_code == 401                 # finché non conferma, l'account non c'è
    codice = codice_di(ultimi(posta_finta, "anna@example.com")[-1])
    sbagliato = conferma(web, "anna@example.com", "000000" if codice != "000000" else "000001")
    assert sbagliato.status_code == 403
    ok = conferma(web, "ANNA@example.com", codice)
    assert ok.status_code == 200 and len(ok.json()["codice_recupero"].replace("-", "")) == 20
    me = web.get("/api/account/me").json()
    assert me["utente"]["nome_utente"] == "anna" and me["utente"]["ruolo"] == "utente" and me["email"] == "anna@example.com"
    assert conferma(cliente(), "anna@example.com", codice).status_code == 403              # monouso
    assert cliente().post("/api/account/accedi", json={"nome_utente": "anna", "password": PASSWORD}).status_code == 200


def test_aperta_app_nativa_riceve_il_token(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web)
    r = conferma(web, "anna@example.com", codice_di(posta_finta[-1]), nativo=True)
    token = r.json()["token"]
    assert cliente(Authorization=f"Bearer {token}").get("/api/account/me").json()["utente"]["nome_utente"] == "anna"


def test_aperta_richiede_email_e_controlla_nome_password(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    assert iscrivi(web, email=None).status_code == 400
    assert iscrivi(web, email="").status_code == 400
    assert iscrivi(web, email="anna@mailinator.com").status_code == 400
    assert iscrivi(web, nome="a b").status_code == 400
    assert web.post("/api/account/registra", json={"nome_utente": "anna", "password": "password", "email": "a@example.com"}).status_code == 400
    assert not posta_finta and utenti() == []


def test_aperta_stessa_risposta_se_l_email_e_gia_registrata(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web, "anna", "anna@example.com")
    conferma(web, "anna@example.com", codice_di(posta_finta[-1]))
    posta_finta.clear()
    nuova = iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.5"}), "bruno", "anna@example.com")        # email già di Anna
    libera = iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.6"}), "carla", "carla@example.com")
    senza_segreto = lambda r: {k: v for k, v in r.json().items() if k != "iscrizione"}           # il segreto è casuale ogni volta
    assert (nuova.status_code, senza_segreto(nuova)) == (libera.status_code, senza_segreto(libera))
    assert len(nuova.json()["iscrizione"]) == len(libera.json()["iscrizione"])
    assert "già un account" in posta_finta[0].oggetto and not re.search(r"\b\d{6}\b", posta_finta[0].testo)
    assert conferma(cliente(), "anna@example.com", "123456").status_code == 403
    assert utenti() == ["anna"]


def test_aperta_nome_gia_preso_e_tetto_utenti(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web, "anna", "anna@example.com")
    conferma(web, "anna@example.com", codice_di(posta_finta[-1]))
    # il nome già preso non si rivela al primo passo (anti-enumerazione): lo si dice quando l'email è provata
    duplicato = cliente(**{"X-Forwarded-For": "4.4.4.5"})
    assert iscrivi(duplicato, "anna", "altra@example.com").status_code == 200
    rifiuto = conferma(duplicato, "altra@example.com", codice_di(posta_finta[-1]))
    assert rifiuto.status_code == 400 and "già preso" in rifiuto.json()["detail"] and utenti() == ["anna"]
    monkeypatch.setenv("MAX_UTENTI", "1")
    chiusa = iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.6"}), "bruno", "bruno@example.com")
    assert chiusa.status_code == 403 and "numero massimo" in chiusa.json()["detail"]


def test_aperta_tetto_riverificato_alla_conferma(web, posta_finta, monkeypatch):
    """Due persone iniziano insieme con un posto solo: il tetto si ricontrolla quando nasce l'account."""
    modo(monkeypatch, "aperta")
    monkeypatch.setenv("MAX_UTENTI", "1")
    iscrivi(web, "anna", "anna@example.com")
    iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.5"}), "bruno", "bruno@example.com")
    assert conferma(web, "anna@example.com", codice_di(ultimi(posta_finta, "anna@example.com")[-1])).status_code == 200
    r = conferma(web, "bruno@example.com", codice_di(ultimi(posta_finta, "bruno@example.com")[-1]))
    assert r.status_code == 403 and utenti() == ["anna"]


def test_aperta_limiti_per_indirizzo_ip(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    stati = [iscrivi(web, f"utente{i}", f"u{i}@example.com").status_code for i in range(account_email.ISCRIZIONI_PER_IP[0] + 2)]
    assert stati[:account_email.ISCRIZIONI_PER_IP[0]] == [200] * account_email.ISCRIZIONI_PER_IP[0] and stati[-1] == 429
    altro = iscrivi(cliente(**{"X-Forwarded-For": "5.5.5.5"}), "diverso", "diverso@example.com")
    assert altro.status_code == 200                                                         # un altro indirizzo non è toccato


def test_aperta_forza_bruta_sul_codice_di_iscrizione(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web, "anna", "anna@example.com")
    giusto = codice_di(posta_finta[-1])
    stati = []
    for i in range(60):
        c = f"{(int(giusto) + 1 + i) % 10 ** 6:06d}"
        stati.append(conferma(web, "anna@example.com", c).status_code)
    assert stati.count(403) <= 31 and 429 in stati
    assert conferma(web, "anna@example.com", giusto).status_code in (403, 429)             # dopo 5 errori il codice è bruciato
    assert utenti() == []


def test_aperta_email_sconosciuta_o_malformata_stessa_risposta(web, monkeypatch):
    modo(monkeypatch, "aperta")
    r = [conferma(cliente(**{"X-Forwarded-For": f"4.4.8.{i}"}), e, "123456") for i, e in enumerate(["x@example.com", "non-email", ""])]
    assert len({(x.status_code, x.text) for x in r}) == 1 and r[0].status_code == 403


def test_aperta_un_invito_valido_funziona_come_prima(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    r = web.post("/api/account/registra", json={"nome_utente": "capo", "password": PASSWORD, "invito": invito(True)})
    assert r.status_code == 200 and r.json()["utente"]["ruolo"] == "amministratore" and utenti() == ["capo"]


def test_aperta_scaduta_iscrizione_dopo_15_minuti(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE codici_email SET scade = '2000-01-01T00:00:00+00:00'")
        db.commit()
    assert conferma(web, "anna@example.com", codice_di(posta_finta[-1])).status_code == 403


def test_aperta_nel_database_non_c_e_la_password_in_chiaro(web, posta_finta, monkeypatch):
    modo(monkeypatch, "aperta")
    iscrivi(web)
    with contextlib.closing(account.apri()) as db:
        dati = db.execute("SELECT dati, codice_hash FROM codici_email").fetchone()
    assert PASSWORD not in dati["dati"] and codice_di(posta_finta[-1]) not in dati["codice_hash"] and "scrypt$" in dati["dati"]


# ---------------------------------------------------------------- email: invito + email obbligatoria
def test_email_serve_l_invito_e_l_email(web, posta_finta, monkeypatch):
    modo(monkeypatch, "email")
    assert iscrivi(web).status_code == 403                                                  # senza invito
    codice_inv = invito()
    assert iscrivi(web, invito=codice_inv, email=None).status_code == 400                   # senza email
    r = iscrivi(web, invito=codice_inv)
    assert r.status_code == 200 and r.json()["verifica_email"] is True and utenti() == []
    ok = conferma(web, "anna@example.com", codice_di(posta_finta[-1]))
    assert ok.status_code == 200 and utenti() == ["anna"]
    again = iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.7"}), "bruno", "bruno@example.com", invito=codice_inv)
    assert again.status_code == 403                                                          # l'invito è stato usato alla conferma


def test_email_invito_sbagliato_conta_nei_limiti(web, monkeypatch):
    modo(monkeypatch, "email")
    stati = [iscrivi(web, invito=f"SBAGL-IATO{i}-AAAAA-BBBBB").status_code for i in range(account.INVITI_SBAGLIATI_PER_IP[0] + 2)]
    assert set(stati[:5]) == {403} and stati[-1] == 429


def test_email_invito_da_amministratore_da_il_ruolo_alla_conferma(web, posta_finta, monkeypatch):
    modo(monkeypatch, "email")
    iscrivi(web, "capo", "capo@example.com", invito=invito(True))
    conferma(web, "capo@example.com", codice_di(posta_finta[-1]))
    assert web.get("/api/account/me").json()["utente"]["ruolo"] == "amministratore"


def test_email_due_iscrizioni_con_lo_stesso_invito_vince_la_prima(web, posta_finta, monkeypatch):
    modo(monkeypatch, "email")
    inv = invito()
    iscrivi(web, "anna", "anna@example.com", invito=inv)
    iscrivi(cliente(**{"X-Forwarded-For": "4.4.4.9"}), "bruno", "bruno@example.com", invito=inv)
    assert conferma(web, "anna@example.com", codice_di(ultimi(posta_finta, "anna@example.com")[-1])).status_code == 200
    r = conferma(web, "bruno@example.com", codice_di(ultimi(posta_finta, "bruno@example.com")[-1]))
    assert r.status_code == 403 and utenti() == ["anna"]


def test_termini_nel_giro_con_email(web, monkeypatch, posta_finta):
    """I termini accettati alla richiesta si registrano quando nasce l'account; il «no» ferma subito."""
    modo(monkeypatch, "aperta")
    assert iscrivi(web, "bruno", "bruno@example.com", accetto_termini=False).status_code == 400
    assert iscrivi(web, "bruno", "bruno@example.com", accetto_termini=True).status_code == 200
    assert conferma(web, "bruno@example.com", codice_di(ultimi(posta_finta, "bruno@example.com")[-1])).status_code == 200
    with contextlib.closing(account.apri()) as db:
        r = db.execute("SELECT termini_accettati, termini_versione FROM utenti WHERE nome_utente = 'bruno'").fetchone()
    assert r["termini_accettati"] and r["termini_versione"] == account.VERSIONE_TERMINI
