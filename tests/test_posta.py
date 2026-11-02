"""Invio email: spento (predefinito), log senza codici, smtp con TLS e resend con finti server; modelli; nessuna chiave nei registri."""
import pytest

from fanta import posta


@pytest.fixture(autouse=True)
def _sincrona(monkeypatch, tmp_path):
    monkeypatch.setattr(posta, "IN_BACKGROUND", False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "dati"))
    for v in ("FANTA_MAIL", "FANTA_MAIL_DA", "FANTA_SMTP_HOST", "FANTA_SMTP_PORT", "FANTA_SMTP_UTENTE", "FANTA_SMTP_PASSWORD",
              "FANTA_RESEND_KEY"):
        monkeypatch.delenv(v, raising=False)


M = posta.Messaggio("anna@example.com", "Ciao", "testo")


def test_predefinito_e_spento_non_invia_e_non_scrive_niente(tmp_path, monkeypatch):
    monkeypatch.setattr(posta.smtplib, "SMTP", lambda *a, **k: pytest.fail("non deve aprire connessioni"))
    assert posta.modo() == "spento" and not posta.invia(M)
    assert not (tmp_path / "dati" / posta.FILE_LOG).exists()


def test_modo_log_scrive_solo_che_e_partito_mai_il_codice(tmp_path, monkeypatch):
    """Attacco: leggere posta.log (copia di backup, file lasciato in giro) per entrare con i codici. Nel file non ci sono."""
    monkeypatch.setenv("FANTA_MAIL", "log")
    monkeypatch.setattr(posta.smtplib, "SMTP", lambda *a, **k: pytest.fail("non deve aprire connessioni"))
    codice = "482913"
    assert posta.invia(posta.modello_recupero("marco.rossi@example.com", codice, 15))
    assert posta.invia(posta.modello_verifica("anna@example.com", "771204", 15, "anna"))
    testo = (tmp_path / "dati" / posta.FILE_LOG).read_text(encoding="utf-8")
    assert codice not in testo and "771204" not in testo and "Ciao" not in testo
    assert "marco.rossi" not in testo and "m...@example.com" in testo and "non_inviata" in testo


def test_modo_sconosciuto_torna_a_spento(monkeypatch):
    monkeypatch.setenv("FANTA_MAIL", "boh")
    assert posta.modo() == "spento"


def test_indirizzi_e_intestazioni_pericolose():
    assert posta.indirizzo_valido("a.b+c@sub.example.com")
    for x in ("a@b", "a b@example.com", "a@example.com\nBcc: x@y.it", "<a@example.com>", "a@@example.com", "", None,
              "a@" + "b" * 300 + ".it"):
        assert not posta.indirizzo_valido(x)
    assert not posta.invia(posta.Messaggio("a@example.com", "x\nBcc: y@z.it", "t"))


def test_smtp_usa_starttls_e_login(monkeypatch):
    chiamate = []

    class Finto:
        def __init__(self, host, porta, timeout=None, context=None): chiamate.append(("conn", host, porta))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): chiamate.append(("tls", context is not None))
        def login(self, u, p): chiamate.append(("login", u, p))
        def send_message(self, e): chiamate.append(("invio", e["To"], e["From"]))
    monkeypatch.setattr(posta.smtplib, "SMTP", Finto)
    monkeypatch.setenv("FANTA_MAIL", "smtp")
    monkeypatch.setenv("FANTA_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("FANTA_SMTP_UTENTE", "u")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD", "segreta")
    monkeypatch.setenv("FANTA_MAIL_DA", "SchieraXI <noreply@example.com>")
    assert posta.invia(M)
    assert [c[0] for c in chiamate] == ["conn", "tls", "login", "invio"] and chiamate[1] == ("tls", True)


def test_smtp_senza_configurazione_o_con_errore_non_alza(monkeypatch):
    monkeypatch.setenv("FANTA_MAIL", "smtp")
    assert not posta.invia(M)                                         # manca tutto
    monkeypatch.setenv("FANTA_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("FANTA_MAIL_DA", "noreply@example.com")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD", "segretissima")
    monkeypatch.setattr(posta.smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(OSError("giù")))
    assert not posta.invia(M)


def test_resend_manda_chiave_nell_intestazione_e_non_nei_registri(monkeypatch, tmp_path):
    visto = {}

    class R:
        status_code = 200

    def finto(url, **k):
        visto.update(url=url, **k)
        return R()
    import requests
    monkeypatch.setattr(requests, "post", finto)
    monkeypatch.setenv("FANTA_MAIL", "resend")
    monkeypatch.setenv("FANTA_RESEND_KEY", "re_CHIAVE_SEGRETA")
    monkeypatch.setenv("FANTA_MAIL_DA", "noreply@example.com")
    assert posta.invia(M)
    assert visto["url"].startswith("https://") and visto["headers"]["Authorization"] == "Bearer re_CHIAVE_SEGRETA"
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("re_CHIAVE_SEGRETA")))
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    assert not posta.invia(M)
    for f in (tmp_path / "dati").glob("*.log*"):
        assert "re_CHIAVE_SEGRETA" not in f.read_text(encoding="utf-8")


def test_chiave_da_file(tmp_path):
    (tmp_path / "dati").mkdir()
    (tmp_path / "dati" / "chiave-resend.txt").write_text("re_dal_file\n", encoding="utf-8")
    assert posta.segreto("FANTA_RESEND_KEY", "chiave-resend.txt") == "re_dal_file"


def test_modelli_in_italiano_con_il_codice():
    for m in (posta.modello_verifica("a@example.com", "123456", 15), posta.modello_recupero("a@example.com", "654321", 15)):
        assert "SchieraXI" in m.oggetto and ("123456" in m.testo or "654321" in m.testo) and "15 minuti" in m.testo
    a = posta.modello_accesso_nuovo("a@example.com", "iPhone\nBcc: x", "oggi")
    assert "\n" not in a.oggetto and "password" in a.testo and "\nBcc: x" not in a.testo
