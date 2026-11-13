"""Accesso con Google: tutto con token finti firmati da una chiave RSA di prova e un elenco di chiavi (JWKS) finto. Nessuna rete."""
import contextlib
import json
import sqlite3
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from fanta import account, percorsi, registro, rotte_account, server, social

PASSWORD = "una-password-lunga-9"
CLIENT_ID = "id-di-prova.apps.googleusercontent.com"
VERIFICATORE = "v" * 50
SFIDA = social.sfida_di(VERIFICATORE)

CHIAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ALTRA_CHIAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(k):
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _jwks(chiave, kid="k1"):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(chiave.public_key()))
    return {"keys": [jwk | {"kid": kid, "alg": "RS256", "use": "sig"}]}


class Scena:
    """Cosa risponde il «Google» finto."""
    def __init__(self):
        self.token = None
        self.letture_chiavi = 0
        self.chiavi = _jwks(CHIAVE)


def claims(nonce, **extra):
    adesso = int(time.time())
    base = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1234567890", "email": "mario@gmail.com",
            "email_verified": True, "nonce": nonce, "iat": adesso, "exp": adesso + 3600}
    return base | extra


def firma(dati, chiave=CHIAVE, kid="k1", alg="RS256"):
    return jwt.encode(dati, _pem(chiave), algorithm=alg, headers={"kid": kid})


@pytest.fixture
def scena(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setenv("FANTA_GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("FANTA_GOOGLE_CLIENT_SECRET", "segreto-di-prova")
    monkeypatch.setenv("FANTA_GOOGLE_REDIRECT", "https://esempio.test/api/account/social/google/ritorno")
    monkeypatch.delenv("FANTA_GOOGLE_DOMINI", raising=False)
    monkeypatch.delenv("FANTA_REGISTRAZIONE", raising=False)
    s = Scena()

    def chiavi():
        s.letture_chiavi += 1
        return s.chiavi, 3600

    monkeypatch.setattr(social, "_scarica_chiavi", chiavi)
    monkeypatch.setattr(social, "_cambia_codice", lambda codice, verificatore, redirect: s.token)
    monkeypatch.setitem(social._cache_chiavi, "chiavi", {})
    monkeypatch.setitem(social._cache_chiavi, "scade", 0.0)
    monkeypatch.setitem(social._cache_chiavi, "letta", 0.0)
    return s


def cliente(ip="1.1.1.1") -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1", "X-Forwarded-For": ip}, follow_redirects=False)


def invito():
    with contextlib.closing(account.apri()) as db:
        return account.crea_invito(db, "prova")


def utente_con_password(c, nome="marco"):
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200, r.text
    return r


def avvia(c, scena, scopo="accedi", dati=None, modifica=None, piattaforma="web", password=None):
    """Fa il giro fino al ritorno. Restituisce la risposta del ritorno (302)."""
    r = c.post("/api/account/social/google/inizia", json={"scopo": scopo, "sfida": SFIDA, "piattaforma": piattaforma,
                                                                    "password": PASSWORD if password is None and scopo == "collega" else password or ""})
    assert r.status_code == 200, r.text
    q = parse_qs(urlparse(r.json()["url"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["scope"] == ["openid email"] and q["client_id"] == [CLIENT_ID]
    d = claims(q["nonce"][0], **(dati or {}))
    if modifica:
        d = modifica(d)
    if scena.token is None:
        scena.token = firma(d)
    return c.get("/api/account/social/google/ritorno", params={"code": "codice-google", "state": q["state"][0]})


def codice_di(r):
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    assert loc.startswith("/?social="), loc
    return loc.split("=", 1)[1]


def giro(c, scena, scopo="accedi", dati=None, verificatore=VERIFICATORE, **kw):
    scena.token = None
    codice = codice_di(avvia(c, scena, scopo, dati, **kw))
    return c.post("/api/account/social/scambio", json={"codice": codice, "verificatore": verificatore})


def iscrivi_con_google(c, scena, nome="mario", **dati):
    r = giro(c, scena, dati=dati or None)
    assert r.status_code == 200 and r.json()["stato"] == "nuovo", r.text
    return r.json()


# ---------------------------------------------------------------- spento senza le variabili
def test_senza_variabili_tutto_spento_404(multiutente, dati_isolati, monkeypatch):
    monkeypatch.delenv("FANTA_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("FANTA_GOOGLE_CLIENT_SECRET", raising=False)
    c = cliente()
    assert c.post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 404
    assert c.get("/api/account/social/google/ritorno", params={"code": "x", "state": "y"}).status_code == 404
    assert c.post("/api/account/social/scambio", json={"codice": "x" * 30, "verificatore": VERIFICATORE}).status_code == 404
    assert c.post("/api/account/social/completa", json={"iscrizione": "x" * 30, "nome_utente": "abc"}).status_code == 404
    assert c.get("/api/account/me").json()["detail"] == "Accesso richiesto"
    utente_con_password(c)
    me = c.get("/api/account/me").json()
    assert me["social"] == [] and "accessi" not in me
    assert c.get("/api/account/social/accessi").status_code == 404
    assert c.delete("/api/account/social/google").status_code == 404


def test_con_una_sola_variabile_resta_spento(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setenv("FANTA_GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.delenv("FANTA_GOOGLE_CLIENT_SECRET", raising=False)
    assert cliente().post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 404


def test_il_401_dice_che_google_c_e(scena):
    r = cliente().get("/api/account/me")
    assert r.status_code == 401 and r.json()["social"] == ["google"]


# ---------------------------------------------------------------- iscrizione e accesso
def test_iscrizione_su_invito_serve_il_codice_d_invito(scena):
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    assert nuovo["serve_invito"] is True and nuovo["nome_suggerito"] == "mario"
    corpo = {"iscrizione": nuovo["iscrizione"], "nome_utente": "Mario", "accetto_termini": True}
    assert c.post("/api/account/social/completa", json=corpo).status_code == 403                           # senza invito
    sbagliato = c.post("/api/account/social/completa", json=corpo | {"invito": "sbagliato"})
    assert sbagliato.status_code == 403 and sbagliato.json()["detail"] == rotte_account.INVITO_DA_CHIEDERE     # #580
    assert c.post("/api/account/social/completa", json=corpo | {"invito": invito(), "accetto_termini": False}).status_code == 400
    r = c.post("/api/account/social/completa", json=corpo | {"invito": invito()})
    assert r.status_code == 200 and r.json()["utente"]["nome_utente"] == "mario" and "codice_recupero" not in r.json()
    assert c.get("/api/account/me").json()["accessi"] == {
        "password": False, "social": [{"provider": "google", "email": "mario@gmail.com", "creata": mock_any(), "ultimo_uso": mock_any()}],
        "disponibili": ["google"]}


def mock_any():
    class Qualsiasi:
        def __eq__(self, altro):
            return True
    return Qualsiasi()


def test_secondo_accesso_con_google_entra_nello_stesso_account(scena):
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True})
    primo = c.get("/api/account/me").json()["utente"]["id"]
    altro = cliente("2.2.2.2")
    r = giro(altro, scena)
    assert r.status_code == 200 and r.json()["stato"] == "ok" and r.json()["utente"]["id"] == primo
    assert altro.get("/api/account/me").status_code == 200
    # nessuna password: l'accesso classico non è possibile nemmeno indovinando
    assert cliente("3.3.3.3").post("/api/account/accedi", json={"nome_utente": "mario", "password": PASSWORD}).status_code == 401


def test_app_nativa_riceve_il_token_e_ios_ha_il_suo_redirect(scena):
    c = cliente()
    scena.token = None
    r = avvia(c, scena, piattaforma="ios")
    assert r.status_code == 302 and r.headers["location"].startswith("schieraxi://social?codice=")
    assert r.headers["referrer-policy"] == "no-referrer"


def test_registrazione_aperta_senza_invito_con_gmail(scena, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    assert nuovo["serve_invito"] is False
    r = c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "accetto_termini": True})
    assert r.status_code == 200


def test_registrazione_aperta_rispetta_il_tetto_del_giorno(scena, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "1")
    c = cliente()
    utente_con_password(c, "primo")
    nuovo = iscrivi_con_google(cliente("4.4.4.4"), scena)
    r = cliente("4.4.4.4").post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "secondo", "accetto_termini": True})
    assert r.status_code == 403 and "chiuse" in r.json()["detail"]


def test_email_non_affidabile_non_si_iscrive_se_il_server_non_e_su_invito(scena, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    scena.token = None
    r = giro(cliente(), scena, dati={"email": "x@esempio.it"})                        # verificata ma non Gmail né Workspace
    assert r.status_code == 403 and r.json()["codice"] == "email_non_affidabile"
    r = giro(cliente(), scena, dati={"email_verified": False})
    assert r.status_code == 403 and r.json()["codice"] == "email_non_affidabile"


def test_email_non_verificata_su_invito_entra_ma_non_si_salva_l_email(scena):
    c = cliente()
    nuovo = iscrivi_con_google(c, scena, email_verified=False)
    r = c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True})
    assert r.status_code == 200
    assert c.get("/api/account/me").json()["email"] is None


def test_il_tetto_degli_utenti_vale_anche_con_google(scena, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "1")
    c = cliente()
    utente_con_password(c)
    nuovo = iscrivi_con_google(cliente("5.5.5.5"), scena)
    r = cliente("5.5.5.5").post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True})
    assert r.status_code == 403 and "massimo" in r.json()["detail"]


def test_l_account_nato_con_google_parte_da_una_cartella_vuota(scena):
    """Una cartella rimasta con il numero che l'account sta per ricevere va da parte, come per gli altri modi di iscriversi."""
    rimasta = percorsi.cartella_utenti() / "1"
    rimasta.mkdir(parents=True)
    (rimasta / "rose.json").write_text("{}", encoding="utf-8")
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    corpo = {"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True}
    r = c.post("/api/account/social/completa", json=corpo)
    assert r.status_code == 200 and c.get("/api/account/me").json()["utente"]["id"] == 1
    assert not (rimasta / "rose.json").exists()
    assert len(list((percorsi.cartella_account() / "utenti-da-parte").glob("*/rose.json"))) == 1


def test_completa_non_si_usa_due_volte(scena):
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    corpo = {"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True}
    assert c.post("/api/account/social/completa", json=corpo).status_code == 200
    assert cliente("6.6.6.6").post("/api/account/social/completa", json=corpo | {"nome_utente": "altro", "invito": invito()}).status_code == 403


def test_nome_preso_non_brucia_l_iscrizione(scena):
    c = cliente()
    utente_con_password(c, "mario")
    nuovo = iscrivi_con_google(cliente("7.7.7.7"), scena)
    c2 = cliente("7.7.7.7")
    corpo = {"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True}
    assert c2.post("/api/account/social/completa", json=corpo).status_code == 400
    assert c2.post("/api/account/social/completa", json=corpo | {"nome_utente": "mario2"}).status_code == 200


# ---------------------------------------------------------------- token da rifiutare
def _rifiutato(scena, c=None, **kw):
    scena.token = None
    r = avvia(c or cliente(), scena, **kw)
    assert r.status_code == 302 and r.headers["location"] == "/?social_errore=non_valido", r.headers["location"]


def test_nonce_sbagliato(scena):
    _rifiutato(scena, modifica=lambda d: d | {"nonce": "un-altro"})


def test_destinatario_sbagliato(scena):
    _rifiutato(scena, dati={"aud": "il-client-di-un-altro"})


def test_token_scaduto(scena):
    adesso = int(time.time())
    _rifiutato(scena, dati={"iat": adesso - 7200, "exp": adesso - 3600})


def test_emittente_sbagliato(scena):
    _rifiutato(scena, dati={"iss": "https://accounts.example.com"})


def test_firma_di_un_altra_chiave(scena):
    scena.token = None
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
    nonce = parse_qs(urlparse(r.json()["url"]).query)
    scena.token = firma(claims(nonce["nonce"][0]), chiave=ALTRA_CHIAVE)
    r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": nonce["state"][0]})
    assert r.headers["location"] == "/?social_errore=non_valido"


def test_algoritmo_none_e_hs256_con_la_chiave_pubblica(scena):
    c = cliente()
    for costruisci in (
        lambda d: jwt.encode(d, None, algorithm="none", headers={"kid": "k1"}),
        lambda d: jwt.encode(d, "segreto-qualsiasi-molto-lungo-per-hs256!", algorithm="HS256", headers={"kid": "k1"}),
    ):
        scena.token = None
        r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
        q = parse_qs(urlparse(r.json()["url"]).query)
        scena.token = costruisci(claims(q["nonce"][0]))
        r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
        assert r.headers["location"] == "/?social_errore=non_valido"


def test_chiave_sconosciuta_si_rilegge_al_massimo_una_volta_al_minuto(scena):
    c = cliente()
    for _ in range(3):
        scena.token = None
        r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
        q = parse_qs(urlparse(r.json()["url"]).query)
        scena.token = firma(claims(q["nonce"][0]), kid="sconosciuta")
        r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
        assert r.headers["location"] == "/?social_errore=non_valido"
    assert scena.letture_chiavi == 1


def test_stato_gia_usato_scaduto_o_inventato(scena):
    c = cliente()
    scena.token = None
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
    q = parse_qs(urlparse(r.json()["url"]).query)
    scena.token = firma(claims(q["nonce"][0]))
    prima = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
    assert prima.headers["location"].startswith("/?social=")
    seconda = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
    assert seconda.headers["location"].startswith("/?social_errore=")
    assert c.get("/api/account/social/google/ritorno", params={"code": "x", "state": "inventato" * 5}).headers["location"] == "/?social_errore=non_valido"
    assert c.get("/api/account/social/google/ritorno").headers["location"] == "/?social_errore=non_valido"
    # scaduto
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
    q = parse_qs(urlparse(r.json()["url"]).query)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE flussi_social SET scade = ?", (account._testo(account._ora(None) - __import__('datetime').timedelta(minutes=5)),))
        db.commit()
    r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
    assert r.headers["location"] == "/?social_errore=scaduto"


def test_utente_che_annulla_torna_senza_errori_rossi(scena):
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
    q = parse_qs(urlparse(r.json()["url"]).query)
    r = c.get("/api/account/social/google/ritorno", params={"error": "access_denied", "state": q["state"][0]})
    assert r.headers["location"] == "/?social_errore=annullato"


# ---------------------------------------------------------------- codice monouso
def test_il_codice_monouso_non_si_ripete(scena):
    c = cliente()
    scena.token = None
    codice = codice_di(avvia(c, scena))
    corpo = {"codice": codice, "verificatore": VERIFICATORE}
    assert c.post("/api/account/social/scambio", json=corpo).status_code == 200
    assert c.post("/api/account/social/scambio", json=corpo).status_code == 403


def test_verificatore_sbagliato_brucia_il_codice(scena):
    c = cliente()
    scena.token = None
    codice = codice_di(avvia(c, scena))
    assert c.post("/api/account/social/scambio", json={"codice": codice, "verificatore": "x" * 50}).status_code == 403
    assert c.post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).status_code == 403


def test_codice_scaduto_o_inventato(scena):
    c = cliente()
    scena.token = None
    codice = codice_di(avvia(c, scena))
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE flussi_social SET codice_scade = '2000-01-01T00:00:00+00:00'")
        db.commit()
    assert c.post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).status_code == 403
    assert c.post("/api/account/social/scambio", json={"codice": "z" * 43, "verificatore": VERIFICATORE}).status_code == 403


def test_sfida_non_valida_all_inizio(scena):
    c = cliente()
    for sfida in ("", "corta", "!" * 43):
        assert c.post("/api/account/social/google/inizia", json={"sfida": sfida}).status_code == 400
    assert c.post("/api/account/social/google/inizia", json={"sfida": SFIDA, "scopo": "altro"}).status_code == 400
    assert c.post("/api/account/social/google/inizia", json={"sfida": SFIDA, "piattaforma": "tv"}).status_code == 400


# ---------------------------------------------------------------- collegare Google a un account che c'è già
def test_collega_da_sessione_e_poi_si_entra_con_google(scena):
    c = cliente()
    utente_con_password(c)
    r = giro(c, scena, scopo="collega")
    assert r.status_code == 200 and r.json()["stato"] == "collegato"
    assert r.json()["accessi"]["password"] is True and r.json()["accessi"]["social"][0]["email"] == "mario@gmail.com"
    r = giro(cliente("8.8.8.8"), scena)
    assert r.json()["stato"] == "ok" and r.json()["utente"]["nome_utente"] == "marco"


def test_collega_senza_sessione_non_parte(scena):
    r = cliente().post("/api/account/social/google/inizia", json={"scopo": "collega", "sfida": SFIDA})
    assert r.status_code == 401


def test_collegamento_da_sessione_altrui_rifiutato(scena):
    a, b = cliente("1.1.1.1"), cliente("2.2.2.2")
    utente_con_password(a, "alice")
    utente_con_password(b, "bruno")
    scena.token = None
    codice = codice_di(avvia(a, scena, scopo="collega"))
    assert b.post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).status_code == 403
    assert a.get("/api/account/social/accessi").json()["social"] == []
    assert b.get("/api/account/social/accessi").json()["social"] == []
    # e senza sessione: nemmeno
    scena.token = None
    codice = codice_di(avvia(a, scena, scopo="collega"))
    assert cliente("9.9.9.9").post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).status_code == 403


def test_l_email_uguale_non_apre_un_account_esistente(scena):
    c = cliente()
    utente_con_password(c)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'mario@gmail.com'")
        db.commit()
    altro = cliente("2.2.2.2")
    r = giro(altro, scena)
    assert r.status_code == 409 and r.json()["codice"] == "email_gia_usata"
    assert altro.get("/api/account/me").status_code == 401


def test_stesso_google_non_sta_in_due_account(scena):
    a, b = cliente("1.1.1.1"), cliente("2.2.2.2")
    utente_con_password(a, "alice")
    utente_con_password(b, "bruno")
    assert giro(a, scena, scopo="collega").status_code == 200
    r = giro(b, scena, scopo="collega")
    assert r.status_code == 409 and r.json()["codice"] == "google_gia_collegato"


def test_scollegare_solo_se_resta_un_altro_accesso(scena):
    c = cliente()
    utente_con_password(c)
    giro(c, scena, scopo="collega")
    assert c.delete("/api/account/social/google").status_code == 200                 # c'è la password
    assert c.get("/api/account/social/accessi").json()["social"] == []
    assert c.delete("/api/account/social/google").status_code == 404
    # solo Google: l'ultimo accesso non si toglie
    s = cliente("3.3.3.3")
    scena.token = None
    nuovo = iscrivi_con_google(s, scena, sub="999")
    s.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "solo", "invito": invito(), "accetto_termini": True})
    r = s.delete("/api/account/social/google")
    assert r.status_code == 409 and r.json()["codice"] == "ultimo_accesso"
    assert s.get("/api/account/social/accessi").json()["social"] != []


# ---------------------------------------------------------------- chi è solo Google
def _solo_google(scena, ip="3.3.3.3"):
    s = cliente(ip)
    nuovo = iscrivi_con_google(s, scena)
    r = s.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "solo", "invito": invito(), "accetto_termini": True})
    assert r.status_code == 200
    return s


def test_imposta_password_serve_la_riconferma_con_google(scena):
    s = _solo_google(scena)
    r = s.post("/api/account/imposta-password", json={"password": PASSWORD})
    assert r.status_code == 403 and r.json()["codice"] == "serve_riconferma"
    assert giro(s, scena, scopo="riconferma").json()["stato"] == "riconfermato"
    r = s.post("/api/account/imposta-password", json={"password": PASSWORD})
    assert r.status_code == 200 and r.json()["codice_recupero"]
    assert cliente("4.4.4.4").post("/api/account/accedi", json={"nome_utente": "solo", "password": PASSWORD}).status_code == 200
    assert s.get("/api/account/social/accessi").json()["password"] is True
    assert s.delete("/api/account/social/google").status_code == 200                  # ora c'è la password


def test_riconferma_con_un_altro_google_non_vale(scena):
    s = _solo_google(scena)
    r = giro(s, scena, scopo="riconferma", dati={"sub": "un-altro"})
    assert r.status_code == 403 and r.json()["codice"] == "google_diverso"
    assert s.post("/api/account/imposta-password", json={"password": PASSWORD}).status_code == 403


def test_eliminare_l_account_solo_google_chiede_la_riconferma(scena):
    s = _solo_google(scena)
    assert s.post("/api/account/elimina", json={"password": ""}).status_code == 403
    assert giro(s, scena, scopo="riconferma").status_code == 200
    assert s.post("/api/account/elimina", json={"password": ""}).status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 0


def test_la_password_vuota_non_apre_un_account_solo_google(scena):
    _solo_google(scena)
    for password in ("", " ", "null"):
        assert cliente("5.5.5.5").post("/api/account/accedi", json={"nome_utente": "solo", "password": password}).status_code == 401


# ---------------------------------------------------------------- limiti, registro, database
def test_limite_di_avvii_per_indirizzo(scena):
    c = cliente("10.0.0.1")
    for _ in range(social.AVVII_PER_IP[0]):
        assert c.post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 200
    assert c.post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 429
    assert cliente("10.0.0.2").post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 200


def test_nel_registro_niente_token_codici_stato_ne_email(scena):
    c = cliente()
    scena.token = None
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})
    q = parse_qs(urlparse(r.json()["url"]).query)
    scena.token = firma(claims(q["nonce"][0]))
    codice = codice_di(c.get("/api/account/social/google/ritorno", params={"code": "codice-google-segreto", "state": q["state"][0]}))
    nuovo = c.post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).json()
    c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True})
    c.get("/api/account/social/google/ritorno", params={"code": "altro", "state": "x" * 40})
    testo = (percorsi.cartella_account() / registro.FILE_SICUREZZA).read_text(encoding="utf-8")
    assert "social_registrazione" in testo
    for segreto in (q["state"][0], q["nonce"][0], codice, nuovo["iscrizione"], "codice-google-segreto", "mario@gmail.com", scena.token,
                    "segreto-di-prova", VERIFICATORE):
        assert segreto not in testo


def test_la_migrazione_non_perde_i_dati_e_fa_la_copia(tmp_path):
    vecchio = tmp_path / "account.sqlite"
    db = sqlite3.connect(vecchio)
    for numero, m in enumerate(account.MIGRAZIONI[:7]):
        db.executescript("BEGIN IMMEDIATE;" + m + f"PRAGMA user_version = {numero + 1}; COMMIT;")
    db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('vecchio', 'h', 'r', '2026-01-01T00:00:00+00:00')")
    db.commit()
    db.close()
    with contextlib.closing(account.apri(vecchio)) as nuovo:
        assert nuovo.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        riga = nuovo.execute("SELECT nome_utente, senza_password FROM utenti").fetchone()
        assert tuple(riga) == ("vecchio", 0)
        assert nuovo.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 0
    assert (tmp_path / "backup" / "account-prima-della-migrazione-7.sqlite").exists()


def test_i_segreti_non_stanno_nel_repository():
    from pathlib import Path
    radice = Path(__file__).resolve().parents[1]
    for p in (radice / "fanta").rglob("*"):
        if p.suffix in (".py", ".js", ".json", ".md") and p.is_file():
            assert ".apps.googleusercontent.com" not in p.read_text(encoding="utf-8", errors="ignore") or p.name == "test_social.py", p


def test_il_log_degli_accessi_non_ha_code_e_state():
    import logging
    filtro = social._SenzaQuery()
    r = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                          ("1.2.3.4:5", "GET", "/api/account/social/google/ritorno?code=SEGRETO&state=ALTRO", "1.1", 302), None)
    assert filtro.filter(r) and "SEGRETO" not in r.getMessage() and "/ritorno" in r.getMessage()
    r2 = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", "/api/oggi?x=1", "1.1", 200), None)
    assert filtro.filter(r2) and "x=1" in r2.getMessage()


# ---------------------------------------------------------------- correzioni della revisione
def _due_dispositivi_solo_google(scena):
    a = _solo_google(scena, "3.3.3.3")
    b = cliente("4.4.4.4")
    assert giro(b, scena).json()["stato"] == "ok"                      # lo stesso Google su un secondo dispositivo
    return a, b


def test_la_riconferma_vale_solo_per_la_sessione_che_l_ha_fatta(scena):
    a, b = _due_dispositivi_solo_google(scena)
    assert giro(a, scena, scopo="riconferma").json()["stato"] == "riconfermato"
    r = b.post("/api/account/imposta-password", json={"password": PASSWORD})
    assert r.status_code == 403 and r.json()["codice"] == "serve_riconferma"
    assert b.post("/api/account/elimina", json={"password": ""}).status_code == 403
    assert a.post("/api/account/imposta-password", json={"password": PASSWORD}).status_code == 200


def test_il_giro_di_riconferma_non_si_riscatta_da_un_altra_sessione_dello_stesso_utente(scena):
    a, b = _due_dispositivi_solo_google(scena)
    scena.token = None
    codice = codice_di(avvia(a, scena, scopo="riconferma"))
    assert b.post("/api/account/social/scambio", json={"codice": codice, "verificatore": VERIFICATORE}).status_code == 403
    assert a.post("/api/account/imposta-password", json={"password": PASSWORD}).status_code == 403


def test_collegare_google_chiede_la_password(scena):
    c = cliente()
    utente_con_password(c)
    for password in ("", "sbagliata-sbagliata"):
        r = c.post("/api/account/social/google/inizia", json={"scopo": "collega", "sfida": SFIDA, "password": password})
        assert r.status_code == 403
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM flussi_social").fetchone()[0] == 0
    assert giro(c, scena, scopo="collega").status_code == 200


def test_collegare_google_avvisa_per_email(scena, monkeypatch):
    from fanta import posta
    mandate = []
    monkeypatch.setattr(posta, "invia", lambda m: mandate.append(m) or True)
    c = cliente()
    utente_con_password(c)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'marco@esempio.it'")
        db.commit()
    assert giro(c, scena, scopo="collega").status_code == 200
    assert [m.a for m in mandate] == ["marco@esempio.it"] and "Google collegato" in mandate[0].oggetto


def test_esci_da_tutti_scollega_google_a_chi_ha_la_password_ma_non_a_chi_e_solo_google(scena):
    c = cliente()
    utente_con_password(c)
    giro(c, scena, scopo="collega")
    assert c.post("/api/account/esci-da-tutti").status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 0
    s = _solo_google(scena, "6.6.6.6")
    assert s.post("/api/account/esci-da-tutti").status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 1


def test_il_recupero_della_password_scollega_google(scena):
    c = cliente()
    r = utente_con_password(c)
    giro(c, scena, scopo="collega")
    codice = r.json()["codice_recupero"]
    assert cliente("7.7.7.7").post("/api/account/recupero", json={"nome_utente": "marco", "codice": codice, "nuova": "un-altra-password-9"}).status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 0


def test_accesso_con_google_da_un_dispositivo_nuovo_avvisa_per_email(scena, monkeypatch):
    from fanta import posta
    mandate = []
    monkeypatch.setattr(posta, "invia", lambda m: mandate.append(m) or True)
    c = cliente("1.1.1.1")
    utente_con_password(c)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'marco@esempio.it'")
        db.commit()
    giro(c, scena, scopo="collega")
    mandate.clear()
    assert giro(cliente("1.1.1.1"), scena).json()["stato"] == "ok"             # indirizzo già noto: niente avviso
    assert not mandate
    assert giro(cliente("9.9.9.9"), scena).json()["stato"] == "ok"             # indirizzo nuovo
    assert len(mandate) == 1 and "dispositivo nuovo" in mandate[0].oggetto


def test_pochi_indirizzi_non_esauriscono_gli_avvii_di_tutti(scena):
    for i in range(25):
        for _ in range(social.AVVII_PER_IP[0]):
            assert cliente(f"20.0.0.{i}").post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 200
    assert cliente("30.0.0.1").post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 200


def test_il_tetto_globale_conta_solo_i_giri_riusciti(scena, monkeypatch):
    monkeypatch.setattr(social, "RITORNI_RIUSCITI_GLOBALI", (2, 3600))
    c = cliente()
    scena.token = None
    for _ in range(2):
        scena.token = None
        assert avvia(c, scena).headers["location"].startswith("/?social=")
    scena.token = None
    assert avvia(c, scena).headers["location"] == "/?social_errore=non_valido"


def test_senza_il_redirect_https_il_servizio_resta_spento(scena, monkeypatch):
    for valore in (None, "http://esempio.test/ritorno", ""):
        if valore is None:
            monkeypatch.delenv("FANTA_GOOGLE_REDIRECT")
        else:
            monkeypatch.setenv("FANTA_GOOGLE_REDIRECT", valore)
        assert cliente().post("/api/account/social/google/inizia", json={"sfida": SFIDA}).status_code == 404
        assert cliente().get("/api/account/me").json().get("social") == []


def test_l_url_di_ritorno_e_quello_configurato_non_l_host(scena):
    r = cliente().post("/api/account/social/google/inizia", json={"sfida": SFIDA}, headers={"Host": "evil.example"})
    assert parse_qs(urlparse(r.json()["url"]).query)["redirect_uri"] == ["https://esempio.test/api/account/social/google/ritorno"]


def test_l_email_in_chiaro_non_resta_oltre_la_scadenza(scena):
    c = cliente()
    scena.token = None
    codice_di(avvia(c, scena))
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT esito FROM flussi_social").fetchone()[0] is not None
        db.execute("UPDATE flussi_social SET codice_scade = '2000-01-01T00:00:00+00:00'")
        db.commit()
    c.post("/api/account/social/google/inizia", json={"sfida": SFIDA})                # una richiesta qualsiasi fa pulizia
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM flussi_social WHERE esito IS NOT NULL").fetchone()[0] == 0
    # e dopo l'iscrizione scaduta
    iscrivi_con_google(c, scena, sub="55")
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE flussi_social SET iscrizione_scade = '2000-01-01T00:00:00+00:00' WHERE iscrizione_hash IS NOT NULL")
        db.commit()
    c.get("/api/account/social/google/ritorno", params={"state": "x" * 40})            # anche il ritorno fa pulizia
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM flussi_social WHERE esito IS NOT NULL").fetchone()[0] == 0


def test_un_dominio_workspace_non_e_affidabile_se_non_e_indicato(scena, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    r = giro(cliente(), scena, dati={"email": "mario@azienda.it", "hd": "azienda.it"})
    assert r.status_code == 403 and r.json()["codice"] == "email_non_affidabile"
    monkeypatch.setenv("FANTA_GOOGLE_DOMINI", "scuola.it, azienda.it")
    assert giro(cliente("2.2.2.2"), scena, dati={"email": "mario@azienda.it", "hd": "azienda.it"}).json()["stato"] == "nuovo"


def test_il_log_non_ha_nemmeno_il_redirect_finale_con_il_codice():
    import logging
    filtro = social._SenzaQuery()
    for percorso in ("/?social=CODICESEGRETO", "/?vista=oggi&social_errore=annullato&x=1"):
        r = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", percorso, "1.1", 200), None)
        assert filtro.filter(r) and "?" not in r.getMessage() and "SEGRETO" not in r.getMessage()


def test_registro_della_pagina_principale_senza_parametri():
    """Il link d'invito apre la pagina principale con il codice nell'indirizzo: nel registro degli accessi solo il percorso."""
    import logging
    filtro = social._SenzaQuery()
    for percorso, atteso in (("/?invito=CODICEPROVA", "/"), ("/?vista=oggi&invito=CODICEPROVA", "/"), ("/?qualsiasi=1", "/"),
                             ("/index.html?invito=CODICEPROVA", "/index.html")):
        r = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", percorso, "1.1", 200), None)
        registro.FILTRO_INDIRIZZI.filter(r)
        assert filtro.filter(r) and "CODICEPROVA" not in r.getMessage() and "?" not in r.getMessage(), r.getMessage()
        assert f'"GET {atteso} HTTP/1.1"' in r.getMessage(), r.getMessage()


def test_registro_delle_richieste_vero_senza_parametri_della_pagina_principale():
    """Dal registro `uvicorn.access` com'è dopo `togli_query_dai_log()` (lo fa l'avvio del server), con il formato di uvicorn."""
    import logging
    registro_richieste = logging.getLogger("uvicorn.access")
    filtri_prima, livello_prima = list(registro_richieste.filters), registro_richieste.level
    righe = []

    class Raccogli(logging.Handler):
        def emit(self, record):
            righe.append(record.getMessage())
    raccogli = Raccogli()
    registro_richieste.addHandler(raccogli)
    registro_richieste.setLevel(logging.INFO)
    try:
        social.togli_query_dai_log()
        for percorso in ("/?invito=CODICEPROVA", "/?vista=oggi", "/api/oggi?x=1"):
            registro_richieste.info('%s - "%s %s HTTP/%s" %d', "1.2.3.4:5", "GET", percorso, "1.1", 200)
    finally:
        registro_richieste.removeHandler(raccogli)
        registro_richieste.filters[:] = filtri_prima
        registro_richieste.setLevel(livello_prima)
    assert len(righe) == 3, righe
    assert not [r for r in righe if "invito=" in r or "CODICEPROVA" in r or "vista=" in r], righe
    assert '"GET / HTTP/1.1"' in righe[0] and '"GET / HTTP/1.1"' in righe[1]
    assert '"GET /api/oggi?x=1 HTTP/1.1"' in righe[2]                    # le altre richieste restano come sono


def test_migrazione_gia_fatta_da_un_altro_processo(tmp_path):
    percorso = tmp_path / "account.sqlite"
    with contextlib.closing(account.apri(percorso)) as db:
        db.execute("PRAGMA user_version").fetchone()
    with contextlib.closing(sqlite3.connect(percorso)) as db2:               # una versione «vecchia» letta prima che l'altro finisse
        account._applica_migrazioni(db2, 7)
        assert db2.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        assert db2.execute("SELECT COUNT(*) FROM identita_esterne").fetchone()[0] == 0


def test_ios_scaduto_torna_all_app(scena):
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA, "piattaforma": "ios"})
    q = parse_qs(urlparse(r.json()["url"]).query)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE flussi_social SET scade = ?", (account._testo(account._ora(None) - __import__('datetime').timedelta(minutes=5)),))
        db.commit()
    r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
    assert r.headers["location"] == "schieraxi://social?errore=scaduto"


def test_ios_con_limite_superato_torna_all_app(scena, monkeypatch):
    c = cliente()
    r = c.post("/api/account/social/google/inizia", json={"sfida": SFIDA, "piattaforma": "ios"})
    q = parse_qs(urlparse(r.json()["url"]).query)
    monkeypatch.setattr(social, "RITORNI_PER_IP", (1, 3600))
    c.get("/api/account/social/google/ritorno", params={"code": "x", "state": "inventato" * 5})
    r = c.get("/api/account/social/google/ritorno", params={"code": "x", "state": q["state"][0]})
    assert r.headers["location"] == "schieraxi://social?errore=non_valido"


def test_email_con_etichetta_vale_come_quella_senza(scena):
    c = cliente()
    utente_con_password(c)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'anna@gmail.com'")
        db.commit()
    altro = cliente("2.2.2.2")
    r = giro(altro, scena, dati={"email": "anna+x@gmail.com"})
    assert r.status_code == 409 and r.json()["codice"] == "email_gia_usata"


def test_avviso_senza_proxy(scena, monkeypatch, caplog):
    monkeypatch.delenv("FANTA_PROXY", raising=False)
    with caplog.at_level("WARNING"):
        social.avvisa_se_manca_il_proxy()
    assert "FANTA_PROXY" in caplog.text
    caplog.clear()
    monkeypatch.setenv("FANTA_PROXY", "1")
    social.avvisa_se_manca_il_proxy()
    assert caplog.text == ""


def test_completa_salva_i_termini(scena):
    c = cliente()
    nuovo = iscrivi_con_google(c, scena)
    corpo = {"iscrizione": nuovo["iscrizione"], "nome_utente": "mario", "invito": invito(), "accetto_termini": True}
    assert c.post("/api/account/social/completa", json=corpo).status_code == 200
    with contextlib.closing(account.apri()) as db:
        r = db.execute("SELECT termini_accettati, termini_versione FROM utenti WHERE nome_utente = 'mario'").fetchone()
    assert r["termini_accettati"] and r["termini_versione"] == account.VERSIONE_TERMINI


def test_migrazione_dei_termini_su_utenti_esistenti(tmp_path):
    vecchio = tmp_path / "account.sqlite"
    db = sqlite3.connect(vecchio)
    for numero, m in enumerate(account.MIGRAZIONI[:-1]):
        db.executescript("BEGIN IMMEDIATE;" + m + f"PRAGMA user_version = {numero + 1}; COMMIT;")
    db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('vecchio', 'h', 'r', '2026-01-01T00:00:00+00:00')")
    db.commit()
    db.close()
    with contextlib.closing(account.apri(vecchio)) as nuovo:
        assert nuovo.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
        r = nuovo.execute("SELECT nome_utente, termini_accettati, termini_versione FROM utenti").fetchone()
        assert tuple(r) == ("vecchio", None, None)
