"""Attacchi ai limiti di tentativi (trovati in revisione): raffiche in parallelo, rotazione di indirizzi IPv6 nello stesso /64,
tetti globali che un attaccante esaurisce per bloccare tutti, scrypt saturato. Cartelle temporanee e posta finta."""
import collections
import contextlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from fanta import account, account_email, posta, rotte_account

from test_account_http import PASSWORD, cliente, invito, registra
from test_account_email import codice_di, ultimi


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)                # le email «partono» (le raccoglie la lista qui sopra)
    return messaggi


@pytest.fixture
def web(multiutente, dati_isolati, posta_finta):
    return cliente()


@pytest.fixture
def scrypt_contato(monkeypatch):
    """scrypt un po' lento (come sul server) e contato: quante password sono state davvero valutate."""
    vero, conti, blocco = account.hashlib.scrypt, collections.Counter(), threading.Lock()

    def lento(*a, **k):
        with blocco:
            conti["n"] += 1
        time.sleep(0.02)
        return vero(*a, **k)
    monkeypatch.setattr(account.hashlib, "scrypt", lento)
    return conti


def da(ip):
    return cliente(**{"X-Forwarded-For": ip})


def in_parallelo(funzione, quante, thread=40):
    with ThreadPoolExecutor(thread) as ex:
        return list(ex.map(funzione, range(quante)))


def utente_con_email(nome="marco", email="marco@example.com", ip="8.8.8.8", posta_finta=None):
    c = da(ip)
    assert registra(c, nome).status_code == 200
    assert c.post("/api/account/email", json={"email": email, "password": PASSWORD}).status_code == 200
    assert c.post("/api/account/email/conferma", json={"codice": codice_di(ultimi(posta_finta, email)[-1])}).status_code == 200
    return c


# ---------------------------------------------------------------- (2) controlla e conta insieme
def test_raffica_di_accessi_in_parallelo_da_un_indirizzo(web, scrypt_contato):
    """prova2/3: 80 accessi sbagliati insieme da un indirizzo. Prima: 76 password valutate (limite per indirizzo 30)."""
    account.apri().close()                                                        # il database c'è già (il caso nuovo è a parte)
    scrypt_contato.clear()
    risposte = in_parallelo(lambda i: da("5.5.5.5").post("/api/account/accedi",
                                                         json={"nome_utente": f"nessuno{i}", "password": "x" * 12}), 80)
    esiti = [r.status_code for r in risposte]
    assert 503 not in esiti, [r.text for r in risposte if r.status_code == 503][:2]
    assert collections.Counter(esiti)[401] <= account.FALLIMENTI_PER_IP[0]
    assert scrypt_contato["n"] <= account.FALLIMENTI_PER_IP[0]
    assert set(esiti) <= {401, 429}


def test_raffica_sullo_stesso_nome_si_ferma_dopo_cinque(web, scrypt_contato):
    registra(da("8.8.8.8"), "marco")
    scrypt_contato.clear()
    esiti = in_parallelo(lambda i: da("5.5.5.5").post("/api/account/accedi",
                                                      json={"nome_utente": "marco", "password": f"sbagliata-{i:04d}"}).status_code, 40)
    assert collections.Counter(esiti)[401] <= 5 and scrypt_contato["n"] <= 5


def test_un_accesso_riuscito_non_consuma_i_limiti(web, monkeypatch):
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (3, 900))
    registra(da("8.8.8.8"), "marco")
    for _ in range(10):                                                           # dieci accessi giusti: nessun blocco
        assert da("5.5.5.5").post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}).status_code == 200


def test_raffica_sul_codice_email_al_massimo_cinque_prove(web, posta_finta):
    """prova5: 39 codici sbagliati e quello giusto per ultimo, tutti insieme (IPv6 diversi). Prima: 8 prove, giusto accettato."""
    utente_con_email(posta_finta=posta_finta)
    for giro in range(3):
        da(f"9.9.{giro}.9").post("/api/account/recupero-email", json={"email": "marco@example.com"})
        giusto = codice_di(ultimi(posta_finta, "marco@example.com")[-1])
        prove = [f"{(int(giusto) + k + 1) % 10 ** 6:06d}" for k in range(39)] + [giusto]
        esiti = in_parallelo(lambda i: da(f"2001:db8:{giro}:{i}::1").post(  # noqa: B023 in_parallelo finisce prima del giro dopo
            "/api/account/recupero-email/conferma",
            json={"email": "marco@example.com", "codice": prove[i], "nuova": f"nuova password lunga {giro}"}).status_code, 40)  # noqa: B023 in_parallelo finisce prima del giro dopo
        with contextlib.closing(account.apri()) as db:
            tentativi = db.execute("SELECT tentativi FROM codici_email WHERE scopo = 'recupero' ORDER BY id DESC").fetchone()[0]
        assert tentativi <= account_email.TENTATIVI_PER_CODICE
        assert collections.Counter(esiti)[200] <= 1          # il giusto passa solo se capita fra le prime 5 prove (5 su 40)


# ---------------------------------------------------------------- (3) IPv6: un /64 è un indirizzo solo
def test_ipv6_stesso_prefisso_64_vale_come_un_indirizzo(web):
    """prova1: 7 inviti sbagliati da 7 indirizzi della stessa /64 passavano tutti (limite 5 per indirizzo)."""
    stati = [da(f"2001:db8::{i + 1}").post("/api/account/registra",
                                           json={"nome_utente": f"x{i}aa", "password": PASSWORD, "invito": "SBAGLIATO"}).status_code
             for i in range(account.INVITI_SBAGLIATI_PER_IP[0] + 2)]
    assert stati[-1] == 429
    altro = da("2001:db8:1::1").post("/api/account/registra", json={"nome_utente": "zzaa", "password": PASSWORD, "invito": "SBAGLIATO"})
    assert altro.status_code == 403                                              # un'altra /64 non è toccata


def test_ip_reale_ipv6_diventa_il_prefisso(monkeypatch):
    class Finta:
        def __init__(self, xff):
            self.client = type("C", (), {"host": "127.0.0.1"})()
            self.headers = {"x-forwarded-for": xff}
    monkeypatch.setenv("FANTA_PROXY", "1")
    assert rotte_account.ip_reale(Finta("2001:db8:aa:bb:1:2:3:4")) == rotte_account.ip_reale(Finta("2001:db8:aa:bb::9"))
    assert rotte_account.ip_reale(Finta("2001:db8:aa:bb::9")) == "2001:db8:aa:bb::/64"
    assert rotte_account.ip_reale(Finta("::ffff:1.2.3.4")) == "1.2.3.4"           # IPv4 scritto come IPv6
    assert rotte_account.ip_reale(Finta("1.2.3.4")) == "1.2.3.4"


# ---------------------------------------------------------------- (4) tetti globali: nessuno blocca tutti
def test_richieste_a_vuoto_non_esauriscono_il_tetto_globale_della_posta(web, posta_finta, monkeypatch):
    utente_con_email(posta_finta=posta_finta)
    monkeypatch.setattr(account_email, "INVII_GLOBALI", (3, account.ORA))
    for i in range(20):                                                           # indirizzi che non esistono: nessuna email parte
        assert da(f"7.7.{i}.1").post("/api/account/recupero-email", json={"email": f"nessuno{i}@example.com"}).status_code == 200
    posta_finta.clear()
    assert da("6.6.6.6").post("/api/account/recupero-email", json={"email": "marco@example.com"}).status_code == 200
    assert len(ultimi(posta_finta, "marco@example.com")) == 1


def test_recupero_al_massimo_sei_email_al_giorno_per_indirizzo(web, posta_finta, multiutente):
    utente_con_email(posta_finta=posta_finta)                                     # (la mail di verifica conta: 1 delle 6)
    for ora in range(12):                                                         # una richiesta ogni ora (oltre il limite orario)
        multiutente.t += account.ORA + 1
        da(f"7.7.{ora}.1").post("/api/account/recupero-email", json={"email": "marco@example.com"})
    assert len(ultimi(posta_finta, "marco@example.com")) == account_email.INVII_PER_EMAIL_GIORNO[0]


def test_dopo_tre_codici_bruciati_niente_altri_codici_per_un_giorno(web, posta_finta, multiutente):
    """Chi brucia 3 codici (5 errori ciascuno) non ne riceve altri per un giorno: il blocco è suo (il suo indirizzo IP), non
    dell'email a cui puntava, quindi la vittima continua a poter recuperare l'account."""
    utente_con_email(posta_finta=posta_finta)
    for _giro in range(account_email.CODICI_BRUCIATI[0]):
        multiutente.t += account.ORA + 1
        da("7.7.7.1").post("/api/account/recupero-email", json={"email": "marco@example.com"})
        giusto = codice_di(ultimi(posta_finta, "marco@example.com")[-1])
        for k in range(account_email.TENTATIVI_PER_CODICE):
            da("7.7.7.1").post("/api/account/recupero-email/conferma",
                               json={"email": "marco@example.com", "codice": f"{(int(giusto) + k + 1) % 10 ** 6:06d}",
                                     "nuova": "nuova password lunga"})
    posta_finta.clear()
    multiutente.t += account.ORA + 1
    assert da("7.7.7.1").post("/api/account/recupero-email", json={"email": "marco@example.com"}).status_code == 200
    assert not ultimi(posta_finta, "marco@example.com")                          # all'attaccante non parte niente
    assert da("8.8.8.8").post("/api/account/recupero-email", json={"email": "marco@example.com"}).status_code == 200
    assert len(ultimi(posta_finta, "marco@example.com")) == 1                    # il vero proprietario riceve il suo codice
    multiutente.t += 24 * account.ORA
    da("7.7.7.1").post("/api/account/recupero-email", json={"email": "marco@example.com"})
    assert len(ultimi(posta_finta, "marco@example.com")) == 2                    # dopo un giorno anche l'attaccante torna normale


def test_iscrizioni_a_vuoto_non_chiudono_le_iscrizioni_a_tutti(web, posta_finta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    monkeypatch.setattr(account_email, "ISCRIZIONI_GLOBALI", (3, 24 * account.ORA))
    for i in range(10):                                                           # richieste che non mandano niente (nome non valido)
        da(f"7.8.{i}.1").post("/api/account/registra", json={"nome_utente": "a b", "password": PASSWORD, "email": f"x{i}@example.com"})
    r = da("6.6.6.6").post("/api/account/registra", json={"nome_utente": "anna", "password": PASSWORD, "email": "anna@example.com"})
    assert r.status_code == 200 and ultimi(posta_finta, "anna@example.com")


def test_inviti_sbagliati_da_pochi_indirizzi_non_bloccano_tutti(web):
    """Con 10 indirizzi (5 inviti sbagliati ciascuno) prima si chiudeva la registrazione a tutti (tetto globale 50)."""
    for i in range(10):
        for k in range(account.INVITI_SBAGLIATI_PER_IP[0]):
            da(f"7.9.{i}.1").post("/api/account/registra", json={"nome_utente": "xyzz", "password": PASSWORD, "invito": f"NO{i}X{k}"})
    r = da("6.6.6.6").post("/api/account/registra", json={"nome_utente": "anna", "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200


def test_raffica_da_un_indirizzo_non_lascia_fuori_gli_altri(web, monkeypatch):
    """prova2: una raffica di accessi teneva occupato scrypt; ora chi esagera aspetta il suo turno (una richiesta alla volta per
    indirizzo) e un altro utente entra lo stesso, senza 503."""
    registra(da("8.8.8.8"), "marco")
    vero = account.hashlib.scrypt

    def lento(*a, **k):
        time.sleep(0.15)
        return vero(*a, **k)
    monkeypatch.setattr(account.hashlib, "scrypt", lento)
    esiti = []

    def raffica(i):
        esiti.append(da("5.5.5.5").post("/api/account/accedi", json={"nome_utente": f"n{i}", "password": "x" * 12}).status_code)
    with ThreadPoolExecutor(30) as ex:
        for i in range(30):
            ex.submit(raffica, i)
        time.sleep(0.1)
        t = time.monotonic()
        r = da("4.4.4.4").post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
        attesa = time.monotonic() - t           # soglia larga (da solo ~0,3 s): sotto carico non deve dare falsi allarmi
    assert r.status_code == 200 and attesa < 6.0
    assert 503 not in esiti and collections.Counter(esiti)[429] >= 20
