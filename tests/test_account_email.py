"""Email degli account: aggiunta con verifica, recupero password, nessuna enumerazione, forza bruta dei codici, limiti, compatibilità.
Tutto su cartelle temporanee; la posta è finta (i messaggi si raccolgono in una lista, niente file e niente rete)."""
import contextlib
import re
import sqlite3
import statistics
import time

import pytest

from fanta import account, account_email, posta

from test_account_http import PASSWORD, cliente, registra


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)                # le email «partono» (le raccoglie la lista qui sopra)
    return messaggi


@pytest.fixture
def web(multiutente, dati_isolati, posta_finta):
    return cliente()


def codice_di(m) -> str:
    return re.search(r"\b(\d{6})\b", m.testo).group(1)


def ultimi(posta_finta, a):
    return [m for m in posta_finta if m.a == a]


def imposta(c, email, password=PASSWORD):
    return c.post("/api/account/email", json={"email": email, "password": password})


def utente_con_email(web, posta_finta, nome="marco", email="marco@example.com", **intest):
    c = cliente(**intest)
    registra(c, nome)
    assert imposta(c, email).status_code == 200
    assert c.post("/api/account/email/conferma", json={"codice": codice_di(ultimi(posta_finta, email)[-1])}).status_code == 200
    return c


# ---------------------------------------------------------------- migrazione e retrocompatibilità
def test_migrazione_non_distruttiva(multiutente):
    percorso = account.percorsi.cartella_account() / "account.sqlite"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(percorso)
    for m in account.MIGRAZIONI[:4]:
        db.executescript(m)
    db.execute("PRAGMA user_version = 4")
    db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('vecchio', 'x', 'y', 'z')")
    db.commit()
    db.close()
    with contextlib.closing(account.apri()) as d:
        r = d.execute("SELECT nome_utente, password_hash, email FROM utenti").fetchone()
        assert tuple(r) == ("vecchio", "x", None)
        d.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('altro', 'x', 'y', 'z')")   # NULL multipli ok


def test_registrazione_senza_email_come_prima(web, posta_finta):
    r = registra(web)
    assert r.status_code == 200 and set(r.json()) == {"multiutente", "utente", "codice_recupero"} and not posta_finta
    me = web.get("/api/account/me").json()
    assert me["email"] is None and me["email_in_attesa"] is None and me["utente"]["nome_utente"] == "marco"


def test_registrazione_con_email_facoltativa(web, posta_finta):
    r = registra(web, email="  Marco@Example.COM ")
    assert r.status_code == 200 and len(posta_finta) == 1 and posta_finta[0].a == "marco@example.com"
    assert web.get("/api/account/me").json()["email_in_attesa"] == "marco@example.com"      # in attesa, non ancora verificata
    sbagliata = registra(cliente(), "luca", email="non-una-email")
    assert sbagliata.status_code == 400
    assert cliente().post("/api/account/accedi", json={"nome_utente": "luca", "password": PASSWORD}).status_code == 401   # niente account a metà


# ---------------------------------------------------------------- aggiungere e cambiare l'email
def test_verifica_email_completa_e_monouso(web, posta_finta):
    registra(web)
    assert imposta(web, "a@example.com", "password-sbagliata").status_code == 403 and not posta_finta
    r = imposta(web, "A@Example.com")
    assert r.status_code == 200 and r.json()["scade_minuti"] == 15
    codice = codice_di(posta_finta[-1])
    assert web.post("/api/account/email/conferma", json={"codice": codice}).json()["email"] == "a@example.com"
    assert web.get("/api/account/me").json()["email"] == "a@example.com"
    assert web.post("/api/account/email/conferma", json={"codice": codice}).status_code == 403          # uso singolo


def test_codice_scaduto(web, posta_finta):
    registra(web)
    imposta(web, "a@example.com")
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE codici_email SET scade = '2000-01-01T00:00:00+00:00'")
        db.commit()
    assert web.post("/api/account/email/conferma", json={"codice": codice_di(posta_finta[-1])}).status_code == 403


def test_email_unica_e_nessuna_enumerazione(web, posta_finta):
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    posta_finta.clear()
    altro = cliente()
    registra(altro, "luca")
    esiste = imposta(altro, "marco@example.com")                 # già di Marco
    libero = imposta(altro, "libero@example.com")
    assert (esiste.status_code, esiste.json()) == (libero.status_code, libero.json())          # stessa risposta
    assert [m.a for m in posta_finta] == ["marco@example.com", "libero@example.com"]
    assert "già un account" in posta_finta[0].oggetto and not any(re.search(r"\b\d{6}\b", posta_finta[0].testo) for _ in [0])
    # niente codice per l'indirizzo occupato: non c'è modo di verificarlo
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM codici_email WHERE email = 'marco@example.com' AND utente_id = 2").fetchone()[0] == 0
    assert altro.post("/api/account/email/conferma", json={"codice": "000000"}).status_code == 403
    assert altro.get("/api/account/me").json()["email"] is None


def test_chi_occupa_un_indirizzo_non_verificato_non_blocca_il_proprietario(web, posta_finta):
    """Un indirizzo vale solo dopo la verifica: scriverlo non lo toglie a nessuno."""
    squatter = cliente()
    registra(squatter, "furbo")
    imposta(squatter, "vittima@example.com")                     # mai verificata
    vittima = utente_con_email(web, posta_finta, "vittima", "vittima@example.com")
    assert vittima.get("/api/account/me").json()["email"] == "vittima@example.com"


def test_cambio_email_avvisa_la_vecchia_e_serve_la_password(web, posta_finta):
    c = utente_con_email(web, posta_finta, "marco", "vecchia@example.com")
    posta_finta.clear()
    imposta(c, "nuova@example.com")
    assert c.get("/api/account/me").json()["email"] == "vecchia@example.com"                  # finché non conferma, vale la vecchia
    c.post("/api/account/email/conferma", json={"codice": codice_di(posta_finta[-1])})
    assert c.get("/api/account/me").json()["email"] == "nuova@example.com"
    assert any(m.a == "vecchia@example.com" and "cambiata" in m.oggetto for m in posta_finta)


def test_togli_email(web, posta_finta):
    c = utente_con_email(web, posta_finta)
    assert c.post("/api/account/email/togli", json={"password": "sbagliata-sbagliata"}).status_code == 403
    assert c.post("/api/account/email/togli", json={"password": PASSWORD}).status_code == 200
    assert c.get("/api/account/me").json()["email"] is None


def test_email_malformate_e_usa_e_getta(web, posta_finta):
    registra(web)
    for brutta in ("", "x", "a@b", "a@example.com\nBcc: x@y.it", "a b@example.com", "<a@example.com>", "a@@example.com", "a@mailinator.com",
                   "x" * 400 + "@example.com"):
        assert imposta(web, brutta).status_code in (400, 422), brutta
    assert not posta_finta
    assert account_email.normalizza_email("ＭＡＲＣＯ＠example.com") == "marco@example.com"        # NFKC


def test_eliminando_l_account_spariscono_anche_i_codici(web, posta_finta):
    registra(web)
    imposta(web, "a@example.com")
    assert web.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM codici_email").fetchone()[0] == 0


# ---------------------------------------------------------------- forza bruta e limiti
def test_un_codice_ha_5_tentativi_poi_si_brucia(web, posta_finta):
    registra(web)
    imposta(web, "a@example.com")
    giusto = codice_di(posta_finta[-1])
    sbagliato = "000000" if giusto != "000000" else "000001"
    for _ in range(account_email.TENTATIVI_PER_CODICE):
        assert web.post("/api/account/email/conferma", json={"codice": sbagliato}).status_code == 403
    assert web.post("/api/account/email/conferma", json={"codice": giusto}).status_code == 403          # ormai è bruciato
    imposta(web, "a@example.com")                                                                       # se ne chiede uno nuovo
    assert web.post("/api/account/email/conferma", json={"codice": codice_di(posta_finta[-1])}).status_code == 200


def test_tetto_di_prove_per_indirizzo_ip(web, posta_finta):
    c = cliente(**{"X-Forwarded-For": "8.8.8.8"})
    registra(c)
    imposta(c, "a@example.com")
    stati = [c.post("/api/account/email/conferma", json={"codice": f"{i:06d}"}).status_code for i in range(40)]
    assert stati.count(403) >= 5 and 429 in stati and stati.index(429) <= 30


def test_invii_limitati_per_indirizzo_senza_rivelarlo(web, posta_finta):
    c = cliente(**{"X-Forwarded-For": "7.7.7.7"})
    registra(c)
    risposte = [imposta(c, "a@example.com") for _ in range(account_email.INVII_PER_EMAIL[0] + 2)]
    assert all(r.status_code == 200 and r.json() == risposte[0].json() for r in risposte)               # nessun errore a rivelare il limite
    assert len(ultimi(posta_finta, "a@example.com")) == account_email.INVII_PER_EMAIL[0]


def test_invii_limitati_per_ip_con_429(web, posta_finta):
    lista = []
    for i in range(account_email.INVII_PER_IP[0] + 3):
        r = web.post("/api/account/recupero-email", json={"email": f"x{i}@example.com"}, headers={"X-Forwarded-For": "6.6.6.6"})
        lista.append(r.status_code)
    assert lista[:account_email.INVII_PER_IP[0]] == [200] * account_email.INVII_PER_IP[0] and lista[-1] == 429
    altro = web.post("/api/account/recupero-email", json={"email": "y@example.com"}, headers={"X-Forwarded-For": "5.5.5.5"})
    assert altro.status_code == 200                                                                      # un altro indirizzo non è toccato


# ---------------------------------------------------------------- recupero della password via email
def test_recupero_via_email_completo(web, posta_finta):
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    resto = cliente()
    resto.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    posta_finta.clear()
    anonimo = cliente()
    assert anonimo.post("/api/account/recupero-email", json={"email": "Marco@example.com"}).status_code == 200
    m = ultimi(posta_finta, "marco@example.com")[-1]
    codice = codice_di(m)
    corpo = {"email": "marco@example.com", "codice": codice, "nuova": "una-nuova-password-9"}
    debole = anonimo.post("/api/account/recupero-email/conferma", json=corpo | {"nuova": "password"})
    assert debole.status_code == 400                                                                     # la password debole non brucia il codice
    r = anonimo.post("/api/account/recupero-email/conferma", json=corpo)
    assert r.status_code == 200 and len(r.json()["codice_recupero"].replace("-", "")) == 20
    assert anonimo.post("/api/account/recupero-email/conferma", json=corpo).status_code == 403          # monouso
    assert resto.get("/api/account/me").status_code == 401                                               # le altre sessioni sono chiuse
    assert cliente().post("/api/account/accedi", json={"nome_utente": "marco", "password": "una-nuova-password-9"}).status_code == 200
    assert cliente().post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}).status_code == 401


def test_recupero_email_stessa_risposta_per_tutti(web, posta_finta):
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    posta_finta.clear()
    risposte = [cliente().post("/api/account/recupero-email", json={"email": e}) for e in
                ("marco@example.com", "nessuno@example.com", "non-una-email", "", "a@mailinator.com")]
    assert len({(r.status_code, r.text) for r in risposte}) == 1 and risposte[0].status_code == 200
    assert [m.a for m in posta_finta] == ["marco@example.com"]
    conferme = [cliente().post("/api/account/recupero-email/conferma", json={"email": e, "codice": "123456", "nuova": "una-nuova-password-9"})
                for e in ("marco@example.com", "nessuno@example.com", "non-una-email")]
    assert len({(r.status_code, r.text) for r in conferme}) == 1 and conferme[0].status_code == 403


def test_recupero_email_forza_bruta_dei_codici(web, posta_finta):
    """Attacco: chi conosce l'email della vittima prova i codici uno dopo l'altro. Dopo 5 errori il codice è bruciato; chiederne
    altri è limitato; i tentativi dello stesso indirizzo IP sono limitati: in un'ora non si arriva a una probabilità apprezzabile."""
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    posta_finta.clear()
    attaccante = cliente(**{"X-Forwarded-For": "9.9.9.9"})
    attaccante.post("/api/account/recupero-email", json={"email": "marco@example.com"})
    giusto = codice_di(posta_finta[-1])
    prove = 0
    for i in range(200):
        c = f"{(int(giusto) + 1 + i) % 10 ** 6:06d}"                                                    # tutti sbagliati
        r = attaccante.post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": c, "nuova": "una-nuova-password-9"})
        prove += r.status_code == 403
        if r.status_code == 429:
            break
    assert 5 <= prove <= 31
    # anche il codice giusto, dopo i 5 errori, non vale più (bruciato) né dallo stesso indirizzo (bloccato)
    r = attaccante.post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": giusto, "nuova": "una-nuova-password-9"})
    assert r.status_code in (403, 429)
    assert cliente().post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}).status_code == 200


def test_recupero_email_codice_di_un_altro_account_non_vale(web, posta_finta):
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    utente_con_email(web, posta_finta, "luca", "luca@example.com")
    posta_finta.clear()
    a = cliente()
    a.post("/api/account/recupero-email", json={"email": "luca@example.com"})
    codice_luca = codice_di(posta_finta[-1])
    r = a.post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": codice_luca, "nuova": "una-nuova-password-9"})
    assert r.status_code == 403


def test_codice_di_verifica_non_serve_per_il_recupero(web, posta_finta):
    c = cliente()
    registra(c)
    imposta(c, "marco@example.com")                          # codice di VERIFICA, mai confermato
    codice = codice_di(posta_finta[-1])
    r = cliente().post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": codice, "nuova": "una-nuova-password-9"})
    assert r.status_code == 403                              # l'indirizzo non è verificato e non è di nessuno


# ---------------------------------------------------------------- tempi
def _operazioni_del_recupero(email, i, monkeypatch):
    """Le operazioni lente di una richiesta «password dimenticata»: scritture sul database, commit, calcoli scrypt."""
    scritture, commit, scrypt = [], [0], [0]
    apri_vera, scrypt_vero = account.apri, account.hashlib.scrypt

    def apri_contando():
        db = apri_vera()
        db.set_trace_callback(lambda q: (scritture.append(q.strip()) if q.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")) and not q.strip().startswith("DELETE FROM tentativi") else None,
                                         commit.__setitem__(0, commit[0] + (q.strip().upper() == "COMMIT")))[0])
        return db

    def scrypt_contato(*a, **k):
        scrypt[0] += 1
        return scrypt_vero(*a, **k)
    with monkeypatch.context() as m:
        m.setattr(account, "apri", apri_contando)
        m.setattr(account.hashlib, "scrypt", scrypt_contato)
        c = cliente(**{"X-Forwarded-For": f"10.0.{len(email)}.{i + 1}"})       # un indirizzo diverso per prova: niente limiti di mezzo
        assert c.post("/api/account/recupero-email", json={"email": email}).status_code == 200
    return len(scritture), commit[0], scrypt[0]


def test_stesse_operazioni_con_email_esistente_o_no(web, posta_finta, monkeypatch):
    """Attacco: misurare il tempo di «password dimenticata» per capire se l'email è registrata. Invece dei secondi (instabili sui
    controlli di GitHub) si confrontano le OPERAZIONI: stesse scritture e commit sul database, stessi calcoli scrypt. Se un'email esiste
    davvero deve anche partire un messaggio (così si sa che il caso «esistente» ha percorso la strada lunga)."""
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    posta_finta.clear()
    esistente = _operazioni_del_recupero("marco@example.com", 0, monkeypatch)
    assert len(posta_finta) == 1                                  # strada lunga davvero percorsa
    inesistente = _operazioni_del_recupero("nessuno@example.com", 0, monkeypatch)
    assert len(posta_finta) == 1                                  # niente messaggio, e nessuna differenza di operazioni:
    # commit e scrypt identici; le scritture possono differire di una al massimo (il «finto invio» è un'approssimazione voluta)
    assert esistente[1:] == inesistente[1:], (esistente, inesistente)
    assert abs(esistente[0] - inesistente[0]) <= 1, (esistente, inesistente)


def test_tempi_simili_con_email_esistente_o_no(web, posta_finta):
    """Misura dei tempi, robusta: tempo di CPU del processo (non quello a muro, che soffre il carico di altri processi),
    mediana di molte prove, margine ampio. La prova vera è quella sulle operazioni qui sopra."""
    utente_con_email(web, posta_finta, "marco", "marco@example.com")

    def misura(email, i):
        c = cliente(**{"X-Forwarded-For": f"10.0.{len(email)}.{i + 1}"})
        t = time.process_time()
        c.post("/api/account/recupero-email", json={"email": email})
        return time.process_time() - t
    tempi_a, tempi_b = [], []
    for i in range(25):
        tempi_a.append(misura("marco@example.com", i))
        tempi_b.append(misura("nessuno@example.com", i))
    a, b = statistics.median(tempi_a), statistics.median(tempi_b)
    assert abs(a - b) < max(0.05, 0.5 * max(a, b)), (a, b)


def test_la_posta_parte_in_un_thread_a_parte(monkeypatch):
    """Il tempo di invio (SMTP lento) non deve cambiare il tempo di risposta: `invia` torna subito."""
    import threading
    monkeypatch.setattr(posta, "IN_BACKGROUND", True)
    fermo = threading.Event()
    monkeypatch.setattr(posta, "_invia_ora", lambda m: fermo.wait(5))
    t = time.perf_counter()
    assert posta.invia(posta.Messaggio("a@example.com", "x", "y"))
    assert time.perf_counter() - t < 0.5
    fermo.set()


# ---------------------------------------------------------------- avviso di accesso da un dispositivo nuovo
def test_avviso_accesso_nuovo_solo_con_email_verificata(web, posta_finta):
    primo = cliente(**{"X-Forwarded-For": "1.1.1.1"})
    registra(primo, "senza")
    primo.post("/api/account/accedi", json={"nome_utente": "senza", "password": PASSWORD})
    assert not posta_finta                                                       # niente email: niente avviso
    utente_con_email(web, posta_finta, "marco", "marco@example.com", **{"X-Forwarded-For": "2.2.2.2"})
    posta_finta.clear()
    cliente(**{"X-Forwarded-For": "2.2.2.2"}).post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert not posta_finta                                                       # stesso indirizzo di prima: nessun avviso
    cliente(**{"X-Forwarded-For": "3.3.3.3"}).post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert len(posta_finta) == 1 and "dispositivo nuovo" in posta_finta[0].oggetto and posta_finta[0].a == "marco@example.com"
    assert PASSWORD not in posta_finta[0].testo


def test_niente_email_o_codici_nei_registri_di_sicurezza(web, posta_finta):
    utente_con_email(web, posta_finta, "marco", "marco@example.com")
    cliente().post("/api/account/recupero-email", json={"email": "marco@example.com"})
    codice = codice_di(posta_finta[-1])
    cliente().post("/api/account/recupero-email/conferma", json={"email": "marco@example.com", "codice": codice, "nuova": "una-nuova-password-9"})
    testo = (account.percorsi.cartella_account() / "sicurezza.log").read_text(encoding="utf-8")
    assert "marco@example.com" not in testo and codice not in testo and "una-nuova-password" not in testo
