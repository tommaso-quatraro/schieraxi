"""Account sulla web, collaudo del 26/11 (#940): le parti che stanno sul server.

- La password sbagliata si dice con le parole del campo: «La password attuale non è giusta» solo nel cambio della password (il
  campo si chiama «Password attuale»); altrove (elimina l'account, nuovo codice, email) il campo è «La tua password».
- «Elimina l'account» controlla la password PRIMA della conferma: `POST /api/account/elimina/controlla` dice se la password è
  giusta e non tocca niente.
- «Chi sono» chiesto dalla pagina d'accesso (`?anche_senza_accesso=1`) risponde 200 senza utente invece di 401: niente errore
  rosso nella console del browser. Senza il parametro resta il 401 di sempre (iPhone, versioni di prima della web).
- Nel registro di sicurezza «Uscita da tutti i dispositivi» dice di chi è.
Dati inventati, cartelle temporanee.
"""
import pytest

from fanta import registro

from test_account_http import PASSWORD, cliente, registra

SBAGLIATA = "non-e-la-password-giusta"


@pytest.fixture
def marco(multiutente, dati_isolati):
    c = cliente()
    r = registra(c, "marco")
    assert r.status_code == 200, r.text
    return c


def eventi(tipo: str) -> list[dict]:
    return [e for e in registro.ultimi(registro.FILE_SICUREZZA, 200) if e["tipo"] == tipo]


# ---------------------------------------------------------------- il messaggio della password sbagliata
@pytest.mark.parametrize("rotta, corpo", [
    ("/api/account/elimina", {"password": SBAGLIATA}),
    ("/api/account/elimina/controlla", {"password": SBAGLIATA}),
    ("/api/account/codice-recupero", {"password": SBAGLIATA}),
    ("/api/account/email/togli", {"password": SBAGLIATA}),
], ids=["elimina", "controlla", "codice", "email"])
def test_fuori_dal_cambio_password_niente_attuale(marco, rotta, corpo):
    r = marco.post(rotta, json=corpo)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "La password non è giusta"


def test_nel_cambio_password_il_campo_e_la_password_attuale(marco):
    r = marco.post("/api/account/cambia-password", json={"attuale": SBAGLIATA, "nuova": "nuova-password-lunga"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "La password attuale non è giusta"


# ---------------------------------------------------------------- prima la password, poi la conferma
def test_controlla_la_password_senza_eliminare(marco):
    r = marco.post("/api/account/elimina/controlla", json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert marco.get("/api/account/me").json()["utente"]["nome_utente"] == "marco"      # la sessione vale ancora
    assert eventi("account_eliminato") == []
    assert marco.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200
    assert marco.get("/api/account/me").status_code == 401


def test_controlla_vuole_la_sessione(multiutente, dati_isolati):
    assert cliente().post("/api/account/elimina/controlla", json={"password": PASSWORD}).status_code == 401


def test_controlla_conta_fra_i_tentativi_della_password(marco):
    """Non è una porta per provare password all'infinito: vale lo stesso tetto delle altre conferme (10 all'ora per account)."""
    esiti = [marco.post("/api/account/elimina/controlla", json={"password": f"{SBAGLIATA}-{i}"}).status_code for i in range(11)]
    assert esiti[:10] == [403] * 10 and esiti[10] == 429, esiti


# ---------------------------------------------------------------- chi sono, dalla pagina d'accesso
def test_chi_sono_dalla_pagina_d_accesso_risponde_200_senza_utente(multiutente, dati_isolati):
    r = cliente().get("/api/account/me", params={"anche_senza_accesso": "1"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["multiutente"] is True and corpo["utente"] is None
    assert {"registrazione", "social", "email_attiva"} <= corpo.keys(), corpo
    assert "detail" not in corpo


def test_chi_sono_senza_il_parametro_resta_401(multiutente, dati_isolati):
    r = cliente().get("/api/account/me")
    assert r.status_code == 401
    assert r.json()["multiutente"] is True and r.json()["detail"] == "Accesso richiesto"


def test_chi_sono_con_il_parametro_e_la_sessione_e_quello_di_sempre(marco):
    assert marco.get("/api/account/me", params={"anche_senza_accesso": "1"}).json()["utente"]["nome_utente"] == "marco"


def test_il_parametro_vale_solo_per_chi_sono(multiutente, dati_isolati):
    assert cliente().get("/api/regole", params={"anche_senza_accesso": "1"}).status_code == 401


# ---------------------------------------------------------------- registro di sicurezza
def test_uscita_da_tutti_i_dispositivi_dice_di_chi(marco):
    assert marco.post("/api/account/esci-da-tutti").status_code == 200
    righe = eventi("esci_da_tutti")
    assert len(righe) == 1 and righe[0].get("nome") == "marco", righe
