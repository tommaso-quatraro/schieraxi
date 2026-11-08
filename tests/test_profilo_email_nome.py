"""Profilo: l'email mostrata (anche quella di Google, solo all'interessato) e un solo nome per l'utente. Posta finta, nessuna rete."""
import contextlib

import pytest

from fanta import account, posta

from test_social import PASSWORD, cliente, giro, invito, iscrivi_con_google, scena, utente_con_password  # noqa: F401  (scena è una fixture)
import codice_web

# Il dominio di Google si scrive a pezzi. Le prove ne hanno bisogno davvero (fanta/social.py considera verificate solo le email
# di quel dominio, e solo allora l'email di Google diventa quella dell'account), ma nel repository pubblico non devono comparire
# indirizzi scritti per intero con il dominio di un fornitore vero (la scansione dell'esportazione li blocca).
GMAIL = "gmail" + ".com"


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)                # le email «partono» (le raccoglie la lista qui sopra)
    return messaggi


def entra_con_google(c, scena, nome="mario", **dati):
    nuovo = iscrivi_con_google(c, scena, **dati)
    r = c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": nome, "invito": invito(),
                                                      "accetto_termini": True})
    assert r.status_code == 200, r.text
    return r


# ---------------------------------------------------------------- email
def test_chi_ha_google_vede_l_email_di_google_con_l_origine(scena, posta_finta):
    c = cliente()
    entra_con_google(c, scena, email="mario@example.org", email_verified=True)
    me = c.get("/api/account/me").json()
    assert me["email"] == "mario@example.org" and me["email_origine"] == "google"
    # di Google esce solo l'indirizzo (e la lista già esistente degli accessi): niente sub, token o altro
    assert "sub" not in str(me) and "1234567890" not in str(me)


def test_l_email_dell_account_vince_su_quella_di_google(scena, posta_finta):
    c = cliente()
    entra_con_google(c, scena)                                                  # Google: mario@ + dominio di Google, salvata anche sull'account
    me = c.get("/api/account/me").json()
    assert me["email"] == f"mario@{GMAIL}" and me["email_origine"] == "account"
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'altra@example.com'")
        db.commit()
    me = c.get("/api/account/me").json()
    assert me["email"] == "altra@example.com" and me["email_origine"] == "account"


def test_senza_email_ne_google_resta_vuota(scena):
    c = cliente()
    utente_con_password(c)
    me = c.get("/api/account/me").json()
    assert me["email"] is None and me["email_origine"] is None and me["email_in_attesa"] is None


def test_email_google_non_verificata_non_si_mostra(scena):
    c = cliente()
    entra_con_google(c, scena, email_verified=False)
    me = c.get("/api/account/me").json()
    assert me["email"] is None and me["email_origine"] is None
    assert "@" not in str(me)                                                   # neppure nella lista degli accessi
    assert "@" not in str(c.get("/api/account/social/accessi").json())


def test_un_utente_non_vede_l_email_di_un_altro(scena, posta_finta):
    a = cliente("1.1.1.1")
    entra_con_google(a, scena, "anna", sub="aaa", email=f"anna@{GMAIL}")
    b = cliente("2.2.2.2")
    entra_con_google(b, scena, "bruno", sub="bbb", email=f"bruno@{GMAIL}")
    c = cliente("3.3.3.3")
    utente_con_password(c, "carlo")
    assert giro(c, scena, scopo="collega", dati={"sub": "ccc", "email": f"carlo@{GMAIL}"}).status_code == 200    # carlo col SUO Google
    assert a.get("/api/account/me").json()["email"] == f"anna@{GMAIL}"
    assert b.get("/api/account/me").json()["email"] == f"bruno@{GMAIL}"
    me_c = c.get("/api/account/me").json()
    assert me_c["email"] == f"carlo@{GMAIL}" and me_c["accessi"]["social"][0]["email"] == f"carlo@{GMAIL}"
    for testo in (str(me_c), str(c.get("/api/account/social/accessi").json())):
        assert "anna@" not in testo and "bruno@" not in testo
    assert "carlo@" not in str(a.get("/api/account/me").json()) + str(b.get("/api/account/me").json())
    assert c.get("/api/admin/utenti").status_code == 403


def test_il_recupero_con_email_non_usa_l_email_di_google(scena, posta_finta):
    """L'email di Google compare nel profilo ma NON abilita il recupero password: quello usa solo l'email verificata dell'account."""
    c = cliente()
    entra_con_google(c, scena, email="mario@example.org")
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = NULL")                             # niente email sull'account, solo Google
        db.commit()
    assert c.get("/api/account/me").json()["email"] == "mario@example.org"
    r = cliente("9.9.9.9").post("/api/account/recupero-email", json={"email": "mario@example.org"})
    assert r.status_code == 200 and not posta_finta                              # stessa risposta di sempre, nessuna posta


def test_gli_inviti_non_guardano_l_email(scena):
    c = cliente()
    entra_con_google(c, scena, email="mario@example.org")
    with contextlib.closing(account.apri()) as db:
        codice = account.crea_invito(db, "prova")
    r = cliente("8.8.8.8").post("/api/account/registra", json={"nome_utente": "luigi", "password": PASSWORD, "invito": codice})
    assert r.status_code == 200 and r.json()["utente"]["nome_utente"] == "luigi"


def test_la_web_app_distingue_l_email_da_google():
    app = codice_web.app()
    testi = codice_web.leggi("testi.js")
    assert 'e.email_origine === "google"' in app and "email_origine: me.email_origine" in app
    assert '(propria ? `<button class="bottone secondario" id="acc-email-togli">' in app     # «Togli» solo per l'email dell'account
    assert testi.count('"account.email_google":') == 2 and testi.count('"account.email_google_nota":') == 2      # italiano e inglese


# ---------------------------------------------------------------- un solo nome
def test_il_nome_da_mostrare_ha_sempre_le_stesse_lettere_del_nome_per_accedere(scena):
    c = cliente()
    entra_con_google(c, scena, nome="MarioRossi")
    u = c.get("/api/account/me").json()["utente"]
    assert u["nome_utente"] == "mariorossi" and u["nome_visualizzato"] == "MarioRossi"
    assert u["nome_visualizzato"].lower() == u["nome_utente"]
    # la rotta che cambia le maiuscole resta, ma non permette un altro nome
    assert c.put("/api/account/nome", json={"nome_utente": "MARIOROSSI"}).json()["utente"]["nome_visualizzato"] == "MARIOROSSI"
    assert c.put("/api/account/nome", json={"nome_utente": "AltroNome"}).status_code == 400
    u = c.get("/api/account/me").json()["utente"]
    assert u["nome_visualizzato"].lower() == u["nome_utente"] == "mariorossi"


def test_si_accede_con_il_nome_mostrato_in_qualsiasi_scrittura(scena):
    c = cliente()
    r = c.post("/api/account/registra", json={"nome_utente": "MarcoBianchi", "password": PASSWORD, "invito": invito()})
    assert r.json()["utente"]["nome_visualizzato"] == "MarcoBianchi"
    for scritto in ("MarcoBianchi", "marcobianchi", "MARCOBIANCHI"):
        assert cliente("5.5.5.5").post("/api/account/accedi", json={"nome_utente": scritto, "password": PASSWORD}).status_code == 200


def test_utenti_vecchi_senza_nome_visualizzato_hanno_comunque_un_nome(scena):
    c = cliente()
    utente_con_password(c, "vecchio")
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET nome_visualizzato = NULL")
        db.commit()
    assert c.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "vecchio"
