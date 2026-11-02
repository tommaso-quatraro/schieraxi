"""Collaudo del 2/11/2026 (giro 5): con la posta spenta (FANTA_MAIL=spento, il predefinito) «Mandami il codice» e
«Password dimenticata» via email rispondevano «il codice sta arrivando», ma nessuna email poteva partire.
Ora il server lo dice (503 `posta_spenta`, `email_attiva: false`) e il web non propone moduli che non possono funzionare."""
import pytest

from fanta import posta, server

from test_account_http import PASSWORD, cliente, registra

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")


@pytest.fixture
def inviati(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    return messaggi


@pytest.fixture
def spenta(monkeypatch, multiutente, dati_isolati, inviati):
    monkeypatch.setenv("FANTA_MAIL", "spento")
    return inviati


@pytest.mark.parametrize("modo, attesa", [("spento", False), ("", False), ("boh", False), ("log", True), ("smtp", True), ("resend", True)])
def test_posta_attiva_solo_se_qualcosa_parte(monkeypatch, modo, attesa):
    monkeypatch.setenv("FANTA_MAIL", modo)
    assert posta.attiva() is attesa


def test_il_server_dice_se_le_email_partono(spenta, monkeypatch):
    anonimo = cliente()
    assert anonimo.get("/api/account/me").json()["email_attiva"] is False          # schermata di accesso: lo sa prima di entrare
    c = cliente()
    registra(c, "giulia")
    assert c.get("/api/account/me").json()["email_attiva"] is False
    monkeypatch.setenv("FANTA_MAIL", "log")
    assert c.get("/api/account/me").json()["email_attiva"] is True


def test_collegare_un_email_con_la_posta_spenta(spenta):
    c = cliente()
    registra(c, "giulia")
    r = c.post("/api/account/email", json={"email": "giulia@example.com", "password": PASSWORD})
    assert r.status_code == 503 and r.json()["codice"] == "posta_spenta"
    assert "codice di recupero" in r.json()["detail"]
    assert spenta == []                                                             # niente messaggi «in partenza»
    assert c.get("/api/account/me").json().get("email_in_attesa") is None          # nessuna email «in attesa» che non arriverà mai


def test_password_dimenticata_con_la_posta_spenta_uguale_per_tutti(spenta):
    c = cliente()
    registra(c, "giulia")
    anonimo = cliente()
    risposte = [anonimo.post("/api/account/recupero-email", json={"email": e}) for e in ("giulia@example.com", "nessuno@example.com")]
    assert [r.status_code for r in risposte] == [503, 503]
    assert risposte[0].json() == risposte[1].json()                                 # non dice se l'indirizzo ha un account
    assert spenta == []


def test_web_non_propone_l_email_se_non_parte():
    assert "stato.emailAttiva = !(dati && dati.email_attiva === false);" in APP      # server vecchio senza il campo: come prima
    assert 'if (stato.emailAttiva === false && !e.email) return `<div class="debole piccolo">${t("account.email_spenta")}</div>`;' in APP
    assert 'stato.emailAttiva !== false && (extra.sub === "email" || extra.sub === "codice")' in APP     # recupero: niente scheda «email»
    assert '(stato.emailAttiva === false && modo === "invito" ? "" : CAMPO_EMAIL("ac-email", modo === "invito"))' in APP
    assert 'const email = $("#ac-email") ? v("#ac-email").trim() : "";' in APP      # registrazione senza il campo: nessun errore
