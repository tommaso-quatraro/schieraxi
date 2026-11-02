"""Invio email: spento (predefinito), log senza codici, smtp con TLS e resend con finti server; modelli; nessuna chiave nei registri.
Password SMTP da file con permessi 600, tetto di invii all'ora, intestazioni Date e Message-ID; prova vera con un server SMTP
finto in locale (STARTTLS con certificato autofirmato, AUTH PLAIN)."""
import base64
import os
import socket
import ssl
import threading
from collections import deque

import pytest

from fanta import posta


@pytest.fixture(autouse=True)
def _sincrona(monkeypatch, tmp_path):
    monkeypatch.setattr(posta, "IN_BACKGROUND", False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "dati"))
    for v in ("FANTA_MAIL", "FANTA_MAIL_DA", "FANTA_SMTP_HOST", "FANTA_SMTP_PORT", "FANTA_SMTP_UTENTE", "FANTA_SMTP_PASSWORD",
              "FANTA_RESEND_KEY", "FANTA_SMTP_PASSWORD_FILE", "FANTA_MAIL_MAX_ORA", "FANTA_MULTIUTENTE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(posta, "_invii", deque())


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


# ---------------------------------------------------------------- password da file e tetto orario
def _finto_smtp(monkeypatch):
    chiamate = []

    class Finto:
        def __init__(self, host, porta, timeout=None, context=None): chiamate.append(("conn", host, porta, timeout))
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, context=None): chiamate.append(("tls",))
        def login(self, u, p): chiamate.append(("login", u, p))
        def send_message(self, e): chiamate.append(("invio", e))
    monkeypatch.setattr(posta.smtplib, "SMTP", Finto)
    monkeypatch.setattr(posta.smtplib, "SMTP_SSL", Finto)
    monkeypatch.setenv("FANTA_MAIL", "smtp")
    monkeypatch.setenv("FANTA_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("FANTA_SMTP_UTENTE", "contatti@example.com")
    monkeypatch.setenv("FANTA_MAIL_DA", "SchieraXI <contatti@example.com>")
    return chiamate


def _file_password(tmp_path, testo="dal-file-Segreta\n", nome="smtp.password"):
    f = tmp_path / nome
    f.write_text(testo, encoding="utf-8")
    os.chmod(f, 0o600)
    return f


def test_password_dal_file_vince_sull_ambiente_e_porta_465_usa_tls_subito(monkeypatch, tmp_path):
    chiamate = _finto_smtp(monkeypatch)
    monkeypatch.setenv("FANTA_SMTP_PORT", "465")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD", "vecchia")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path)))
    assert posta.invia(M)
    assert chiamate[0] == ("conn", "smtp.example.com", 465, posta.TIMEOUT)
    assert ("tls",) not in chiamate and ("login", "contatti@example.com", "dal-file-Segreta") in chiamate
    e = chiamate[-1][1]
    assert e["Date"] and e["Message-ID"].endswith("@example.com>")       # niente nome del server nell'intestazione


def test_file_password_leggibile_da_altri_non_si_usa(monkeypatch, tmp_path):
    chiamate = _finto_smtp(monkeypatch)
    monkeypatch.setattr(posta, "_PERMESSI_UNIX", True)              # su Windows chmod 644 lascia comunque 0o666: rifiutato uguale
    f = _file_password(tmp_path)
    os.chmod(f, 0o644)
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(f))
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    assert not posta.invia(M) and chiamate == []
    testo = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "dati").glob("*.log*"))
    assert "PasswordNonSicura" in testo and "dal-file-Segreta" not in testo


def test_file_password_mancante_vuoto_o_enorme_non_alza_e_non_accede(monkeypatch, tmp_path):
    chiamate = _finto_smtp(monkeypatch)
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(tmp_path / "non-ce"))
    assert not posta.invia(M)
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path, "", "vuoto")))
    assert not posta.invia(M)
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path, "x" * (posta.MAX_FILE_PASSWORD + 1), "grande")))
    assert not posta.invia(M)
    assert not [c for c in chiamate if c[0] in ("login", "invio")]


def test_tetto_di_invii_all_ora(monkeypatch, tmp_path):
    chiamate = _finto_smtp(monkeypatch)
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path)))
    monkeypatch.setenv("FANTA_MAIL_MAX_ORA", "3")
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    adesso = [1000.0]
    monkeypatch.setattr(posta, "_orologio", lambda: adesso[0])
    assert all(posta.invia(M) for _ in range(3))
    assert not posta.invia(M)                                            # il quarto nella stessa ora non parte
    assert len([c for c in chiamate if c[0] == "invio"]) == 3
    testo = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "dati").glob("*.log*"))
    assert "posta_tetto_ora" in testo
    adesso[0] += 3600                                                    # un'ora dopo si riparte
    assert posta.invia(M)
    monkeypatch.setenv("FANTA_MAIL", "log")                              # le prove senza invio non contano
    adesso[0] += 1
    assert all(posta.invia(M) for _ in range(5))


def test_tetto_valori_strani(monkeypatch):
    assert posta.tetto_ora() == posta.MAX_ALL_ORA
    for v, atteso in (("boh", posta.MAX_ALL_ORA), ("-4", 0), ("0", 0), (" 12 ", 12)):
        monkeypatch.setenv("FANTA_MAIL_MAX_ORA", v)
        assert posta.tetto_ora() == atteso


# ---------------------------------------------------------------- prova vera con un server SMTP finto in locale
def _certificato(cartella):
    """Certificato autofirmato per 127.0.0.1 (libreria cryptography; se manca il test si salta)."""
    x509 = pytest.importorskip("cryptography.x509")
    from datetime import datetime, timedelta, timezone
    from ipaddress import ip_address
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    chiave = ec.generate_private_key(ec.SECP256R1())
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    ora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chiave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ora - timedelta(minutes=5))
            .not_valid_after(ora + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(chiave, hashes.SHA256()))
    c, k = cartella / "cert.pem", cartella / "chiave.pem"
    c.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    k.write_bytes(chiave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    return c, k


class ServerSmtpFinto(threading.Thread):
    """Un server SMTP minimo su 127.0.0.1: EHLO, STARTTLS obbligatorio prima di AUTH PLAIN, MAIL/RCPT/DATA. Ricorda cosa ha ricevuto."""

    def __init__(self, cert, chiave):
        super().__init__(daemon=True)
        self.contesto = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.contesto.load_cert_chain(cert, chiave)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.sock.settimeout(10)
        self.porta = self.sock.getsockname()[1]
        self.ricevuto = {"comandi": []}

    def run(self):
        conn, _ = self.sock.accept()
        conn.settimeout(10)
        f = conn.makefile("rwb")

        def scrivi(riga):
            f.write(riga.encode() + b"\r\n")
            f.flush()
        scrivi("220 finto ESMTP")
        tls = False
        while True:
            riga = f.readline().decode().rstrip("\r\n")
            if not riga:
                break
            verbo = riga.split(" ")[0].upper()
            self.ricevuto["comandi"].append(verbo)
            if verbo == "EHLO":
                for r in ("250-finto", "250-AUTH PLAIN" if tls else "250-STARTTLS", "250 8BITMIME"):
                    scrivi(r)
            elif verbo == "STARTTLS":
                scrivi("220 vai")
                f.close()
                conn = self.contesto.wrap_socket(conn, server_side=True)
                f = conn.makefile("rwb")
                tls = True
            elif verbo == "AUTH" and tls:
                self.ricevuto["auth"] = base64.b64decode(riga.split(" ")[2]).split(b"\0")
                scrivi("235 ok")
            elif verbo in ("MAIL", "RCPT"):
                self.ricevuto.setdefault(verbo, []).append(riga)
                scrivi("250 ok")
            elif verbo == "DATA":
                scrivi("354 manda")
                corpo = []
                while (r := f.readline()) not in (b".\r\n", b""):
                    corpo.append(r)
                self.ricevuto["messaggio"] = b"".join(corpo).decode()
                scrivi("250 accodato")
            elif verbo == "QUIT":
                scrivi("221 ciao")
                break
            else:
                scrivi("530 prima STARTTLS")
        conn.close()
        self.sock.close()


def test_invio_vero_a_un_server_smtp_finto_con_starttls(monkeypatch, tmp_path):
    cert, chiave = _certificato(tmp_path)
    server = ServerSmtpFinto(cert, chiave)
    server.start()
    contesto_vero = ssl.create_default_context

    def contesto_di_prova(*a, **k):                    # come in produzione (certificato controllato), ma si fida del finto
        c = contesto_vero(*a, **k)
        c.load_verify_locations(cafile=str(cert))
        return c
    monkeypatch.setattr(posta.ssl, "create_default_context", contesto_di_prova)
    monkeypatch.setenv("FANTA_MAIL", "smtp")
    monkeypatch.setenv("FANTA_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("FANTA_SMTP_PORT", str(server.porta))
    monkeypatch.setenv("FANTA_SMTP_UTENTE", "contatti@example.com")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path)))
    monkeypatch.setenv("FANTA_MAIL_DA", "SchieraXI <contatti@example.com>")
    assert posta.invia(posta.modello_recupero("anna@example.com", "482913", 15))
    server.join(10)
    r = server.ricevuto
    assert r["comandi"][:4] == ["EHLO", "STARTTLS", "EHLO", "AUTH"]          # la password passa solo dentro TLS
    assert r["auth"][1:] == [b"contatti@example.com", b"dal-file-Segreta"]
    assert r["MAIL"][0].upper().startswith("MAIL FROM:<CONTATTI@EXAMPLE.COM>")         # mittente della busta = casella (SPF allineato)
    assert [x.upper() for x in r["RCPT"]] == ["RCPT TO:<ANNA@EXAMPLE.COM>"]
    assert "482913" in r["messaggio"] and "Message-ID: <" in r["messaggio"] and "Date: " in r["messaggio"]


def test_server_senza_starttls_non_riceve_la_password(monkeypatch, tmp_path):
    """Attacco: qualcuno in mezzo toglie STARTTLS dalla risposta. L'app non manda la password in chiaro."""
    class SenzaTls(ServerSmtpFinto):
        def run(self):
            conn, _ = self.sock.accept()
            conn.settimeout(10)
            f = conn.makefile("rwb")
            f.write(b"220 finto\r\n")
            f.flush()
            while riga := f.readline():
                self.ricevuto["comandi"].append(riga.decode().split(" ")[0].strip().upper())
                f.write(b"250 finto\r\n" if riga.upper().startswith(b"EHLO") else b"221 ciao\r\n")
                f.flush()
                if riga.upper().startswith(b"QUIT"):
                    break
            conn.close()
            self.sock.close()
    cert, chiave = _certificato(tmp_path)
    server = SenzaTls(cert, chiave)
    server.start()
    monkeypatch.setenv("FANTA_MAIL", "smtp")
    monkeypatch.setenv("FANTA_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("FANTA_SMTP_PORT", str(server.porta))
    monkeypatch.setenv("FANTA_SMTP_UTENTE", "contatti@example.com")
    monkeypatch.setenv("FANTA_SMTP_PASSWORD_FILE", str(_file_password(tmp_path)))
    monkeypatch.setenv("FANTA_MAIL_DA", "contatti@example.com")
    assert not posta.invia(M)
    server.join(10)
    assert "AUTH" not in server.ricevuto["comandi"] and "MAIL" not in server.ricevuto["comandi"]
