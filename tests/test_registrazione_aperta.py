"""Registrazione aperta (decisione del proprietario del 26/11/2026), accesa con FANTA_REGISTRAZIONE=aperta: chi vuole si registra
dalla schermata d'accesso con nome utente e password, l'email è facoltativa e l'account nasce subito, anche con la posta del server
spenta. Restano il tetto di utenti (MAX_UTENTI), il tetto di account nuovi al giorno (FANTA_ISCRIZIONI_GIORNO), i limiti per indirizzo
e una trappola per i programmi che compilano i moduli da soli. Senza la variabile (o con `invito`) si entra solo con un invito, come
prima: le iscrizioni non si aprono da sole quando il server si aggiorna."""
import contextlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from fanta import account, account_email, posta, rotte_account

from test_account_http import PASSWORD, cliente, invito
from test_account_email import codice_di, ultimi

AL_COMPLETO = "Iscrizioni chiuse: siamo al completo."
# I domini di Google si scrivono a pezzi: nel repository pubblico niente indirizzi interi con il dominio di un fornitore vero (vedi
# tests/test_profilo_email_nome.py). Le prove ne hanno bisogno: solo per Gmail i punti non contano.
GMAIL, GOOGLEMAIL = "gmail" + ".com", "googlemail" + ".com"


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    monkeypatch.setattr(posta, "attiva", lambda: True)
    return messaggi


@pytest.fixture
def aperta(multiutente, dati_isolati, monkeypatch):
    """Un server con le iscrizioni aperte (FANTA_REGISTRAZIONE=aperta) e la posta spenta, come oggi."""
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    monkeypatch.delenv("FANTA_ISCRIZIONI_GIORNO", raising=False)
    monkeypatch.setattr(posta, "attiva", lambda: False)
    return multiutente


def registrati(ip="4.4.4.4", nome="anna", **extra):
    c = cliente(**{"X-Forwarded-For": ip})
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "accetto_termini": True} | extra)
    return c, r


def utenti() -> list[str]:
    with contextlib.closing(account.apri()) as db:
        return [u["nome_utente"] for u in account.elenco(db)]


def invecchia_gli_account(giorni=2):
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET creato = ?", ((datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat(timespec="seconds"),))
        db.commit()


# ---------------------------------------------------------------- l'interruttore
@pytest.mark.parametrize("valore, atteso", [(None, "invito"), ("", "invito"), ("  Aperta ", "aperta"), ("invito", "invito"),
                                            ("inviti", "invito"), ("INVITO", "invito"), ("email", "email"), ("boh", "invito"),
                                            ("chiusa", "invito")])
def test_senza_la_variabile_si_entra_con_l_invito_e_un_valore_sbagliato_non_apre(monkeypatch, valore, atteso):
    """Senza la variabile vale `invito`, come prima: aggiornato il server, le iscrizioni non si aprono da sole. Si aprono solo con
    FANTA_REGISTRAZIONE=aperta; un valore scritto male vale come `invito`."""
    if valore is None:
        monkeypatch.delenv("FANTA_REGISTRAZIONE", raising=False)
    else:
        monkeypatch.setenv("FANTA_REGISTRAZIONE", valore)
    assert account_email.modo_registrazione() == atteso


def test_la_risposta_senza_accesso_dice_aperta(aperta):
    assert cliente().get("/api/regole").json()["registrazione"] == "aperta"


def test_senza_la_variabile_le_iscrizioni_restano_chiuse(aperta, monkeypatch):
    """Il server di oggi non ha FANTA_REGISTRAZIONE: dopo l'aggiornamento chi non ha un invito resta fuori."""
    monkeypatch.delenv("FANTA_REGISTRAZIONE")
    assert cliente().get("/api/regole").json()["registrazione"] == "invito"
    _, r = registrati()
    assert r.status_code == 403 and r.json()["detail"] == rotte_account.INVITO_DA_CHIEDERE and utenti() == []


def test_chi_e_entrato_legge_il_modo_dal_suo_account(aperta, monkeypatch):
    """`GET /api/account/me` dice il modo anche a chi è già dentro: Gestione mostra gli inviti solo quando servono."""
    c, _ = registrati()
    assert c.get("/api/account/me").json()["registrazione"] == "aperta"
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "invito")
    assert c.get("/api/account/me").json()["registrazione"] == "invito"


# ---------------------------------------------------------------- registrazione senza invito
def test_senza_invito_ne_email_l_account_nasce_subito(aperta):
    c, r = registrati()
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["utente"]["nome_utente"] == "anna" and corpo["utente"]["ruolo"] == "utente"
    assert len(corpo["codice_recupero"].replace("-", "")) == 20 and "verifica_email" not in corpo
    me = c.get("/api/account/me").json()
    assert me["utente"]["nome_utente"] == "anna" and me["email"] is None
    assert cliente().post("/api/account/accedi", json={"nome_utente": "anna", "password": PASSWORD}).status_code == 200


def test_app_nativa_riceve_il_token(aperta):
    _, r = registrati(nativo=True)
    token = r.json()["token"]
    assert cliente(Authorization=f"Bearer {token}").get("/api/account/me").json()["utente"]["nome_utente"] == "anna"


def test_con_l_email_e_la_posta_spenta_l_account_nasce_e_lo_dice(aperta):
    c, r = registrati(email="anna@example.com")
    assert r.status_code == 200 and r.json()["email_non_salvata"] is True
    assert c.get("/api/account/me").json().get("email_in_attesa") is None


def test_con_l_email_e_la_posta_accesa_parte_la_verifica_senza_il_nome_scelto(aperta, posta_finta):
    """L'email di conferma non contiene il nome scritto da chi si registra: altrimenti chiunque potrebbe mandare un testo suo a
    un indirizzo a caso."""
    c, r = registrati(nome="Compra_Qui", email="anna@example.com")
    assert r.status_code == 200 and "email_non_salvata" not in r.json()
    assert c.get("/api/account/me").json()["email_in_attesa"] == "anna@example.com"
    (messaggio,) = ultimi(posta_finta, "anna@example.com")
    assert re.search(r"\b\d{6}\b", messaggio.testo) and "compra" not in messaggio.testo.lower()


def test_controlla_nome_password_e_termini_senza_creare_niente(aperta):
    assert registrati(nome="a b")[1].status_code == 400
    assert registrati(nome="anna", password="password")[1].status_code == 400
    assert registrati(accetto_termini=False)[1].status_code == 400
    assert registrati(email="non-email")[1].status_code == 400
    assert utenti() == []


def test_nome_gia_preso(aperta):
    registrati()
    _, r = registrati(ip="4.4.4.5", nome="ANNA")
    assert r.status_code == 400 and "già preso" in r.json()["detail"] and utenti() == ["anna"]


def test_un_invito_valido_da_ancora_il_suo_ruolo(aperta):
    _, r = registrati(nome="capo", invito=invito(True))
    assert r.status_code == 200 and r.json()["utente"]["ruolo"] == "amministratore"


# ---------------------------------------------------------------- tetti
def test_oltre_il_tetto_iscrizioni_chiuse_siamo_al_completo(aperta, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "1")
    assert registrati()[1].status_code == 200
    _, r = registrati(ip="4.4.4.5", nome="bruno")
    assert r.status_code == 403 and r.json()["detail"] == AL_COMPLETO and utenti() == ["anna"]


def test_tetti_predefiniti_stretti(monkeypatch):
    """Con la registrazione aperta chiunque trovi il sito può provare: 15 utenti e 5 account nuovi al giorno, se il server non
    dice altro."""
    monkeypatch.delenv("MAX_UTENTI", raising=False)
    monkeypatch.delenv("FANTA_ISCRIZIONI_GIORNO", raising=False)
    assert account.max_utenti() == 15 and account.iscrizioni_al_giorno() == 5


def test_tetto_di_account_nuovi_al_giorno(aperta, monkeypatch):
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "2")
    assert [registrati(ip=f"4.4.5.{i}", nome=f"nuovo{i}")[1].status_code for i in range(2)] == [200, 200]
    _, terzo = registrati(ip="4.4.5.9", nome="nuovo9")
    assert terzo.status_code == 403 and "domani" in terzo.json()["detail"] and len(utenti()) == 2
    invecchia_gli_account()
    assert registrati(ip="4.4.5.9", nome="nuovo9")[1].status_code == 200


def test_tentativi_non_riusciti_da_un_indirizzo(aperta):
    """Chi prova un nome dopo l'altro dallo stesso indirizzo si ferma: i tentativi che non creano un account sono contati."""
    registrati(ip="9.9.9.9", nome="anna")
    stati = [registrati(nome="anna")[1].status_code for _ in range(account.REGISTRAZIONI_PER_IP[0] + 1)]
    assert set(stati[:-1]) == {400} and stati[-1] == 429
    assert registrati(ip="5.5.5.5", nome="bruno")[1].status_code == 200      # un altro indirizzo non è toccato


def test_i_posti_si_ricontrollano_quando_nasce_l_account(aperta, monkeypatch):
    """Due iscrizioni insieme con un posto solo: tutte e due passano il primo controllo (prima di scrypt). Vale quello dentro la
    transazione che crea l'account: se intanto un altro ha preso l'ultimo posto, «siamo al completo» e il secondo account non nasce."""
    monkeypatch.setenv("MAX_UTENTI", "1")
    vero = account.hash_password

    def un_altro_entra_intanto(password):                 # fra il primo controllo e la transazione (scrypt sta in mezzo)
        with contextlib.closing(account.apri()) as altro:
            altro.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, ruolo, creato) "
                          "VALUES ('svelto', 'x', 'y', 'utente', '2026-11-26T08:00:00+00:00')")
            altro.commit()
        return vero(password)

    monkeypatch.setattr(account, "hash_password", un_altro_entra_intanto)
    _, r = registrati()
    assert r.status_code == 403 and r.json()["detail"] == AL_COMPLETO, r.text
    assert utenti() == ["svelto"]


def test_account_nati_da_un_indirizzo(aperta, monkeypatch):
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "100")
    monkeypatch.setenv("MAX_UTENTI", "100")
    stati = [registrati(nome=f"amico{i:02d}")[1].status_code for i in range(account.ACCOUNT_PER_IP[0] + 1)]
    assert stati == [200] * account.ACCOUNT_PER_IP[0] + [429]


# ---------------------------------------------------------------- trappola per i programmi
def test_la_trappola_ferma_chi_compila_tutti_i_campi(aperta):
    """Il modulo della web ha un campo «Sito web» che una persona non vede: se arriva pieno l'ha compilato un programma."""
    _, r = registrati(sito="https://esempio.test")
    assert r.status_code == 400 and utenti() == []
    assert "riprova" in r.json()["detail"]
    assert registrati(sito="")[1].status_code == 200                       # vuoto (o assente, come dall'iPhone): si entra


def test_la_trappola_conta_fra_i_tentativi_dell_indirizzo(aperta):
    stati = [registrati(nome=f"robot{i}", sito="x")[1].status_code for i in range(account.REGISTRAZIONI_PER_IP[0] + 1)]
    assert stati[-1] == 429


# ---------------------------------------------------------------- interruttore chiuso
def test_con_invito_senza_invito_si_resta_fuori(aperta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "invito")
    assert cliente().get("/api/regole").json()["registrazione"] == "invito"
    _, r = registrati()
    assert r.status_code == 403 and r.json()["detail"] == rotte_account.INVITO_DA_CHIEDERE and utenti() == []
    assert registrati(invito=invito())[1].status_code == 200


def test_con_invito_il_tetto_del_giorno_non_conta(aperta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "invito")
    monkeypatch.setenv("FANTA_ISCRIZIONI_GIORNO", "1")
    assert [registrati(nome=n, invito=invito())[1].status_code for n in ("uno", "due", "tre")] == [200] * 3


# ---------------------------------------------------------------- Gestione: l'avviso dei posti parla di iscrizioni, non di inviti
def test_gestione_con_i_posti_pieni_parla_di_iscrizioni(aperta, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "2")
    c, _ = registrati(nome="capo", invito=invito(True))
    r = c.get("/api/admin/utenti").json()
    assert r["avviso"] is None
    registrati(ip="4.4.4.5", nome="luca")
    r = c.get("/api/admin/utenti").json()
    assert r["avviso_frase"] == {"chiave": "admin.posti_pieni_aperta", "param": {"n": 2, "massimo": 2}}, r
    assert r["avviso"].startswith("Posti pieni: 2 utenti su 2.") and "invito" not in r["avviso"], r["avviso"]
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "invito")
    assert c.get("/api/admin/utenti").json()["avviso_frase"]["chiave"] == "admin.posti_pieni"


# ---------------------------------------------------------------- Gmail: punti e +etichetta non fanno un indirizzo nuovo
@pytest.mark.parametrize("scritto, base", [(f"a.n.n.a+lega@{GMAIL}", f"anna@{GMAIL}"), (f"anna@{GOOGLEMAIL}", f"anna@{GMAIL}"),
                                           ("a.n.n.a@example.com", "a.n.n.a@example.com"), ("anna+x@example.com", "anna@example.com")])
def test_l_indirizzo_base_di_gmail_ignora_i_punti(scritto, base):
    assert account_email.indirizzo_base(scritto) == base


def test_una_variante_gmail_di_un_indirizzo_gia_usato_non_riceve_codici(aperta, posta_finta):
    anna, _ = registrati(nome="anna", email=f"anna@{GMAIL}")
    conferma = anna.post("/api/account/email/conferma", json={"codice": codice_di(posta_finta[-1])})
    assert conferma.status_code == 200 and conferma.json()["email"] == f"anna@{GMAIL}"
    posta_finta.clear()
    _, r = registrati(ip="4.4.4.5", nome="bruno", email=f"a.n.n.a+due@{GMAIL}")
    assert r.status_code == 200
    assert posta_finta and all(not re.search(r"\b\d{6}\b", m.testo) for m in posta_finta)      # nessun codice: l'indirizzo è già usato
    assert "già un account" in posta_finta[-1].oggetto


# ---------------------------------------------------------------- iscrizione con l'email obbligatoria (modo `email`)
def test_l_email_di_iscrizione_non_contiene_il_nome_scelto(aperta, posta_finta, monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "email")
    _, r = registrati(nome="Vinci_Subito", email="anna@example.com", invito=invito())
    assert r.status_code == 200 and r.json()["verifica_email"] is True
    (messaggio,) = ultimi(posta_finta, "anna@example.com")
    assert codice_di(messaggio) and "vinci" not in messaggio.testo.lower()
