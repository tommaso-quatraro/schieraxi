"""Account via HTTP: cookie e Bearer, divieto di default su tutte le rotte, ruolo amministratore, interruttore spento."""
import contextlib
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount

from fanta import account, rotte_account, server

PASSWORD = "una-password-lunga-9"


def cliente(**intestazioni) -> TestClient:
    """Un dispositivo: ha i suoi cookie (e l'intestazione che l'app manda sulle richieste che modificano)."""
    return TestClient(server.app, headers={"X-Fanta": "1"} | intestazioni)


def invito(amministratore=False) -> str:
    with contextlib.closing(account.apri()) as db:
        return account.crea_invito(db, "prova", amministratore)


def registra(c: TestClient, nome="marco", amministratore=False, **extra):
    return c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": invito(amministratore)} | extra)


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


# ---------------------------------------------------------------- interruttore spento: l'app di sempre
def test_spento_nessun_accesso_richiesto(monkeypatch, tmp_path):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "non-deve-esistere"))
    c = cliente()
    assert c.get("/api/regole").status_code == 200
    assert c.get("/api/novita").status_code == 200
    me = c.get("/api/account/me").json()
    assert me["multiutente"] is False and me["utente"]["ruolo"] == "amministratore" and me["utente"]["nome_utente"] == "locale"
    for p in ("accedi", "registra", "recupero"):
        assert c.post(f"/api/account/{p}", json={}).status_code == 404
    assert c.post("/api/admin/inviti", json={"etichetta": "x"}).status_code == 404
    assert not (tmp_path / "non-deve-esistere").exists()          # nemmeno il database: a interruttore spento non si crea niente


def test_robots_e_niente_motori_di_ricerca(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    c = cliente()
    r = c.get("/robots.txt")
    assert r.status_code == 200 and "Disallow: /" in r.text
    assert "noindex" in r.headers["x-robots-tag"]
    assert "noindex" in c.get("/api/novita").headers["x-robots-tag"]


# ---------------------------------------------------------------- registrazione, cookie, Bearer
def test_registrazione_e_cookie(web):
    r = registra(web)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["utente"]["nome_utente"] == "marco" and len(corpo["codice_recupero"].replace("-", "")) == 20
    assert "token" not in corpo                                           # nel web il token sta solo nel cookie HttpOnly
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" not in cookie       # http: niente Secure
    assert "no-store" in r.headers["cache-control"]
    assert web.get("/api/account/me").json()["utente"]["nome_utente"] == "marco"             # il cookie basta


def test_cookie_secure_solo_su_https(web):
    c = cliente(**{"X-Forwarded-Proto": "https"})
    r = registra(c, "uno")
    assert "secure" in r.headers["set-cookie"].lower()


def test_accesso_nativo_con_bearer(web):
    registra(web)
    nativo = cliente()
    r = nativo.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD, "nativo": True})
    assert r.status_code == 200 and "set-cookie" not in r.headers
    token = r.json()["token"]
    assert nativo.get("/api/account/me").status_code == 401               # senza cookie e senza Bearer
    ok = nativo.get("/api/account/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200 and ok.json()["utente"]["nome_utente"] == "marco"
    assert nativo.get("/api/account/me", headers={"Authorization": "Bearer sbagliato"}).status_code == 401
    # il Bearer ha la precedenza: un Bearer sbagliato non si salva con un cookie giusto
    assert web.get("/api/account/me", headers={"Authorization": "Bearer sbagliato"}).status_code == 401


def test_accesso_sbagliato_e_limiti(web):
    registra(web)
    senza = cliente()
    r = senza.post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
    assert r.status_code == 401 and "set-cookie" not in r.headers
    for _ in range(4):
        senza.post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
    bloccato = senza.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert bloccato.status_code == 429 and int(bloccato.headers["retry-after"]) >= 1


def test_indirizzo_dietro_proxy(web):
    """Con FANTA_PROXY=1 conta l'ultimo valore di X-Forwarded-For (quello messo dal proxy), non quelli scritti da chi chiede."""
    for i in range(5):
        c = cliente(**{"X-Forwarded-For": f"10.0.0.{i}, 9.9.9.9"})
        assert c.post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 403
    c = cliente(**{"X-Forwarded-For": "1.1.1.1, 9.9.9.9"})
    assert c.post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 429
    altro = cliente(**{"X-Forwarded-For": "1.1.1.1, 8.8.8.8"})
    assert altro.post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 403


class _Finta:
    """Una richiesta finta, per provare come si ricava l'indirizzo."""
    def __init__(self, host, **intestazioni):
        self.client = type("C", (), {"host": host})() if host else None
        self.headers = {k.replace("_", "-").lower(): v for k, v in intestazioni.items()}


def test_senza_proxy_l_intestazione_si_ignora_e_il_locale_non_conta(multiutente, monkeypatch):
    monkeypatch.delenv("FANTA_PROXY")
    assert rotte_account.ip_reale(_Finta("203.0.113.5", x_forwarded_for="1.2.3.4")) == "203.0.113.5"      # l'intestazione la scrive chiunque
    for locale in ("127.0.0.1", "::1", "127.0.1.1", None):
        assert rotte_account.ip_reale(_Finta(locale, x_forwarded_for="1.2.3.4")) is None                  # proxy locale: l'indirizzo non dice niente
    monkeypatch.setenv("FANTA_PROXY", "1")
    assert rotte_account.ip_reale(_Finta("127.0.0.1", x_forwarded_for="6.6.6.6, 1.2.3.4")) == "1.2.3.4"
    assert rotte_account.ip_reale(_Finta("127.0.0.1")) is None
    assert rotte_account.e_https(_Finta("127.0.0.1", x_forwarded_proto="https"))
    c = cliente(**{"X-Forwarded-For": "1.2.3.4"})
    monkeypatch.delenv("FANTA_PROXY")
    for _ in range(5):
        assert c.post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 403
    altra = cliente(**{"X-Forwarded-For": "9.9.9.9"})            # stesso computer di prova: inventare l'intestazione non aggira il limite
    assert altra.post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 429


def test_esci_e_esci_da_tutti(web):
    registra(web)
    secondo = cliente()
    secondo.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert web.post("/api/account/esci").status_code == 200
    assert web.get("/api/account/me").status_code == 401
    assert secondo.get("/api/account/me").status_code == 200                  # l'altro dispositivo è ancora dentro
    assert secondo.post("/api/account/esci-da-tutti").json()["sessioni_chiuse"] == 1
    assert secondo.get("/api/account/me").status_code == 401


def test_cambia_password_e_recupero(web):
    codice = registra(web).json()["codice_recupero"]
    altro = cliente()
    altro.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    r = web.post("/api/account/cambia-password", json={"attuale": PASSWORD, "nuova": "nuova-password-lunga"})
    assert r.status_code == 200
    assert web.get("/api/account/me").status_code == 200 and altro.get("/api/account/me").status_code == 401   # cookie nuovo
    assert r.json()["codice_recupero"] != codice                    # anche il codice di recupero cambia
    codice = r.json()["codice_recupero"]
    anonimo = cliente()
    r = anonimo.post("/api/account/recupero", json={"nome_utente": "marco", "codice": codice, "nuova": "altra-password-lunga"})
    assert r.status_code == 200 and r.json()["codice_recupero"] != codice
    assert web.get("/api/account/me").status_code == 401
    assert anonimo.post("/api/account/accedi", json={"nome_utente": "marco", "password": "altra-password-lunga"}).status_code == 200
    nuovo = anonimo.post("/api/account/codice-recupero", json={"password": "altra-password-lunga"}).json()["codice_recupero"]
    assert nuovo and nuovo != r.json()["codice_recupero"]


def test_dati_malformati(web):
    assert web.post("/api/account/accedi", json={"nome_utente": "marco"}).status_code == 422
    assert web.post("/api/account/accedi", json={"nome_utente": "marco", "password": "x" * 501}).status_code == 422
    assert web.post("/api/account/accedi", content=b"non json", headers={"Content-Type": "application/json"}).status_code == 422


# ---------------------------------------------------------------- divieto di default
def test_senza_sessione_ogni_api_risponde_401(web):
    assert web.get("/api/regole").status_code == 401
    r = web.get("/api/formazione")
    assert r.status_code == 401 and r.json()["multiutente"] is True and "no-store" in r.headers["cache-control"]
    assert web.get("/api/account/me").status_code == 401
    assert web.get("/api/stato/").status_code == 401                          # anche con la barra finale
    assert web.get("/api/non-esiste").status_code == 401                      # nemmeno si capisce cosa esiste
    assert web.get("/docs").status_code == 401 and web.get("/openapi.json").status_code == 401


def test_il_minimo_statico_senza_sessione(web):
    for p in ("/", "/sw.js", "/manifest.webmanifest", "/app.js", "/avatar.js", "/impostazioni.js", "/stile.css", "/robots.txt", "/icona-180.png", "/icona-maskable-512.png", "/icona.svg"):
        assert web.get(p).status_code == 200, p
    assert web.get("/icone/verde-180.png").status_code == 200
    manifest = web.get("/manifest.webmanifest").json()
    assert "screenshots" not in manifest                                    # versione pubblica: niente schermate
    for s in manifest.get("screenshots", []):                                         # le schermate del manifest le chiede il browser senza sessione
        assert web.get("/" + s["src"]).status_code == 200, s["src"]
    assert manifest["orientation"] == "any"                                   # i tablet devono poter ruotare


def test_x_fanta_resta_obbligatorio(web):
    senza = TestClient(server.app)
    assert senza.post("/api/account/registra", json={}).status_code == 403
    assert senza.post("/api/account/accedi", json={}).status_code == 403


def _percorso(modello: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", modello)


def _tutte_le_rotte(rotte, prefisso=""):
    """Le rotte dell'app una per una, anche quelle dei router inclusi (FastAPI recente li tiene annidati)."""
    for r in rotte:
        if hasattr(r, "original_router"):
            yield from _tutte_le_rotte(r.original_router.routes, prefisso + r.include_context.prefix)
        else:
            yield prefisso, r


def test_tutte_le_rotte_sono_chiuse_senza_sessione(web):
    """Passa in rassegna OGNI rotta dell'app: sotto /api/ solo accesso, registrazione e recupero si aprono senza sessione.
    Una rotta nuova che non rispetta la regola fa fallire questo test."""
    provate, aperte, viste = 0, set(), set()
    statici_noti = {"/", "/sw.js", "/robots.txt", "/privacy", "/termini", "/crediti", "/elimina-account", "/icona-{dim}.png", "/icona-maskable-{dim}.png"}
    chiusi_noti = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    for prefisso, rotta in _tutte_le_rotte(server.app.routes):
        if isinstance(rotta, Mount):
            assert rotta.path == "" and rotta.name == "web", f"cartella montata che non conosco: {rotta.path}"
            continue                                                       # i file statici dell'app (codice e icone, niente dati)
        assert isinstance(rotta, APIRoute) or rotta.path in chiusi_noti, f"rotta che non conosco: {rotta.path}"
        percorso = prefisso + rotta.path
        if not percorso.startswith("/api/"):
            assert percorso in statici_noti | chiusi_noti, f"nuova rotta fuori da /api/: {percorso} (aggiungila alle pubbliche o spostala)"
            continue
        viste.add(percorso)
        for metodo in sorted(getattr(rotta, "methods", None) or []):
            if metodo in ("HEAD", "OPTIONS"):
                continue
            r = web.request(metodo, _percorso(percorso))            # senza corpo: se una rotta fosse aperta, non farebbe danni
            provate += 1
            if r.status_code != 401:
                aperte.add((metodo, percorso))
    assert provate > 50 and "/api/account/accedi" in viste and "/api/regole" in viste       # davvero tutte, anche quelle dei router inclusi
    ritorno = "/api/account/social/google/ritorno"          # pubbliche in GET: ci torna Google, da un altro sito; e /api/salute (monitoraggio)
    gets = {ritorno, "/api/salute"}
    assert aperte == {("POST", p) for p in rotte_account.PUBBLICI_API if p not in gets} | {("GET", p) for p in gets}, aperte
    # e le rotte fuori da /api/ che non servono alla pagina di accesso sono chiuse
    for p in chiusi_noti - {"/docs/oauth2-redirect"}:
        assert web.get(p).status_code == 401, p


def test_le_rotte_pubbliche_non_danno_dati(web):
    """Quelle aperte rispondono solo a chi sa fare la richiesta giusta: senza dati validi non c'è niente da leggere."""
    for p in rotte_account.PUBBLICI_API - {"/api/salute"}:
        assert web.get(p).status_code in (404, 405)
    assert web.get("/api/salute").json().keys() == {"ok", "ultimo_aggiornamento"}      # unica pubblica in lettura: solo «vivo» e l'ora


# ---------------------------------------------------------------- amministratore
def test_solo_l_amministratore(web):
    registra(web, "capo", amministratore=True)
    utente = cliente()
    registra(utente, "ospite")
    for metodo, p in (("POST", "/api/admin/inviti"), ("GET", "/api/admin/utenti"), ("POST", "/api/admin/reset-password"),
                      ("GET", "/api/stato-dati"), ("GET", "/api/aggiorna"), ("POST", "/api/aggiorna")):
        assert utente.request(metodo, p, json={} if metodo == "POST" else None).status_code == 403, p
    # l'amministratore passa (GET /api/aggiorna dice solo lo stato; non avviamo aggiornamenti veri)
    assert web.get("/api/aggiorna").status_code == 200
    assert web.get("/api/admin/utenti").json()["utenti"][0]["nome_utente"] == "capo"


def test_invito_e_reset_dall_amministratore(web):
    registra(web, "capo", amministratore=True)
    r = web.post("/api/admin/inviti", json={"etichetta": "Luca"})
    assert r.status_code == 200 and r.json()["valido_giorni"] == 7
    nuovo = cliente()
    ok = nuovo.post("/api/account/registra", json={"nome_utente": "luca", "password": PASSWORD, "invito": r.json()["codice"]})
    assert ok.status_code == 200 and ok.json()["utente"]["ruolo"] == "utente"
    assert web.post("/api/admin/inviti", json={"etichetta": ""}).status_code == 400
    # password dimenticata e codice di recupero perso: reset dell'amministratore
    reset = web.post("/api/admin/reset-password", json={"nome_utente": "luca"}).json()
    assert reset["valido_ore"] == 24
    assert web.post("/api/admin/reset-password", json={"nome_utente": "nessuno"}).status_code == 404
    anonimo = cliente()
    fatto = anonimo.post("/api/account/recupero", json={"nome_utente": "luca", "codice": reset["codice"], "nuova": "nuova-password-lunga"})
    assert fatto.status_code == 200
    assert nuovo.get("/api/account/me").status_code == 401                    # la sessione di prima è chiusa


def test_comando_invito(multiutente, capsys):
    from fanta.__main__ import main
    main(["invito", "--etichetta", "Luca", "--admin"])
    fuori = capsys.readouterr().out
    codice = re.search(r"([A-Z2-9]{5}(?:-[A-Z2-9]{5}){3})", fuori).group(1)
    assert "amministratore" in fuori and "7 giorni" in fuori
    with contextlib.closing(account.apri()) as db:
        utente, _, _ = account.registra(db, "luca", PASSWORD, codice)
    assert utente.amministratore
    with pytest.raises(SystemExit):
        main(["invito", "--etichetta", " "])


# ---------------------------------------------------------------- termini d'uso nella registrazione con password
def _termini(nome):
    with contextlib.closing(account.apri()) as db:
        r = db.execute("SELECT termini_accettati, termini_versione FROM utenti WHERE nome_utente = ?", (nome,)).fetchone()
        return r["termini_accettati"], r["termini_versione"]


def test_registra_con_termini_li_registra(web):
    assert registra(web, "anna", accetto_termini=True).status_code == 200
    quando, versione = _termini("anna")
    assert quando and versione == account.VERSIONE_TERMINI


def test_registra_senza_campo_funziona_ancora(web):
    """Web e app vecchie non mandano il campo: nessun errore, nessuna traccia."""
    assert registra(web, "vecchio").status_code == 200
    assert _termini("vecchio") == (None, None)


def test_registra_termini_rifiutati(web):
    r = registra(web, "no", accetto_termini=False)
    assert r.status_code == 400 and "Termini" in r.json()["detail"] and "Terms" in r.json()["detail"]
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT 1 FROM utenti WHERE nome_utente = 'no'").fetchone() is None


def test_termini_rifiutati_non_bruciano_l_invito(web):
    codice = invito()
    corpo = {"nome_utente": "luca", "password": PASSWORD, "invito": codice}
    assert web.post("/api/account/registra", json=corpo | {"accetto_termini": False}).status_code == 400
    assert web.post("/api/account/registra", json=corpo | {"accetto_termini": True}).status_code == 200


@pytest.mark.parametrize("valore, stato", [("false", 400), (0, 400), (2, 422)])
def test_termini_valori_strani(web, valore, stato):
    assert registra(web, "strano", accetto_termini=valore).status_code == stato
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT 1 FROM utenti WHERE nome_utente = 'strano'").fetchone() is None


def test_versione_termini_come_la_data_delle_pagine_legali():
    import re
    from fanta import testi_legali
    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    mesi_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    for lingua, mesi in (("it", mesi_it), ("en", mesi_en)):
        g, m, a = re.search(r"(\d+) (\w+) (\d{4})", testi_legali.t("aggiornato", lingua)).groups()
        assert f"{a}-{mesi.index(m) + 1:02d}-{int(g):02d}" == account.VERSIONE_TERMINI
