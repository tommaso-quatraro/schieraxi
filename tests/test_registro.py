"""Registro del server: errori 5xx su file con rotazione, contatori, scheda per l'amministratore, niente dati personali."""
import contextlib

import pytest
from fastapi.testclient import TestClient

from fanta import account, percorsi, registro, server

PASSWORD = "una-password-lunga-9"


def cliente(**intestazioni) -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1"} | intestazioni, raise_server_exceptions=False)


def registra(c: TestClient, nome: str, amministratore=False):
    with contextlib.closing(account.apri()) as db:
        codice = account.crea_invito(db, "prova", amministratore)
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": codice})
    assert r.status_code == 200, r.text


@pytest.fixture
def admin(multiutente, dati_isolati):
    registro.contatori.azzera()
    c = cliente()
    registra(c, "capo", amministratore=True)
    return c


def test_errore_5xx_nel_registro_senza_dati_personali(admin, monkeypatch):
    monkeypatch.setattr(account, "accedi_ricordando", lambda *a, **k: 1 / 0)
    r = cliente(**{"X-Forwarded-For": "9.8.7.6"}).post("/api/account/accedi", json={"nome_utente": "marco", "password": "segretissima-1"})
    assert r.status_code == 500
    testo = (percorsi.cartella_account() / registro.FILE_ERRORI).read_text(encoding="utf-8")
    assert "stato=500" in testo and "errore=ZeroDivisionError" in testo and "rotta=/api/account/accedi" in testo and "metodo=POST" in testo
    for vietato in ("marco", "segretissima", "9.8.7.6", "Traceback"):
        assert vietato not in testo


def test_rotta_di_modello_non_l_indirizzo_scritto_da_chi_chiede(admin, monkeypatch):
    monkeypatch.setattr(server, "_db", lambda: 1 / 0)
    admin.get("/api/giocatore/12345")
    testo = (percorsi.cartella_account() / registro.FILE_ERRORI).read_text(encoding="utf-8")
    assert "12345" not in testo and "{" in testo


def test_scheda_admin_contatori_errori_e_eventi(admin, monkeypatch):
    monkeypatch.setattr(account, "accedi_ricordando", lambda *a, **k: 1 / 0)
    cliente().post("/api/account/accedi", json={"nome_utente": "x", "password": "y"})
    account.evento("accesso_fallito", nome="marco", ip="203.0.113.77")
    r = admin.get("/api/admin/registro")
    assert r.status_code == 200
    d = r.json()
    assert d["contatori"]["richieste"] >= 2 and d["contatori"]["errori"] >= 1 and d["contatori"]["tempo_max_ms"] >= 0
    assert d["errori"][0]["stato"] == "500" and d["errori"][0]["rotta"] == "/api/account/accedi"
    sic = [e for e in d["sicurezza"] if e["tipo"] == "accesso_fallito"][0]
    assert sic["ip"] == "203.0.113.x" and "203.0.113.77" not in r.text           # indirizzo nascosto a metà


def test_scheda_solo_per_l_amministratore(admin):
    semplice = cliente()
    registra(semplice, "pippo")
    assert semplice.get("/api/admin/registro").status_code == 403
    assert cliente().get("/api/admin/registro").status_code == 401


def test_errori_con_rotazione(multiutente, monkeypatch):
    monkeypatch.setattr(registro, "MAX_FILE", 1500)
    for i in range(200):
        registro.errore("GET", "/api/prova", 500, "Errore")
    cartella = percorsi.cartella_account()
    assert (cartella / "errori.log.1").exists() and not (cartella / "errori.log.4").exists()
    assert (cartella / "errori.log").stat().st_size <= 1700
    assert len(registro.ultimi(registro.FILE_ERRORI, 10)) == 10


def test_riga_inventata_non_si_puo_scrivere():
    assert "\n" not in registro.pulito("a\nb") and "\r" not in registro.pulito("a\rb")


def test_contatori_semplici():
    registro.contatori.azzera()
    for stato, ms in ((200, 10), (200, 30), (404, 5), (500, 100)):
        registro.contatori.conta("/api/x", stato, ms)
    r = registro.contatori.riepilogo()
    assert (r["richieste"], r["riuscite"], r["rifiutate"], r["errori"]) == (4, 2, 1, 1)
    assert r["tempo_max_ms"] == 100 and r["tempo_medio_ms"] == 36.2
    assert r["piu_lente"][0]["rotta"] == "/api/x"


def test_senza_account_l_errore_si_registra_lo_stesso(dati_isolati, monkeypatch):
    monkeypatch.setattr(server, "_db", lambda: 1 / 0)
    cliente().get("/api/giocatori")
    assert "stato=500" in (percorsi.cartella_account() / registro.FILE_ERRORI).read_text(encoding="utf-8")
