"""Email degli account: aggiungere/cambiare l'indirizzo con verifica, recupero della password via email, iscrizione con email.

Regole di fondo (vedi anche `account.py`):
- l'indirizzo in `utenti.email` è SEMPRE verificato (colonna facoltativa: NULL = nessuna email) ed è unico. Un indirizzo non ancora
  verificato vive solo in `codici_email`, quindi nessuno può «occupare» l'indirizzo di un altro e nessuna risposta rivela se un
  indirizzo è già registrato: la risposta è la stessa sia se l'indirizzo esiste sia se no (e il tempo anche: l'invio vero è in un
  thread a parte e per gli indirizzi sconosciuti si fa lo stesso numero di scritture);
- i codici sono 6 cifre casuali, durano 15 minuti, si usano una volta sola, ogni codice ammette 5 tentativi (poi si brucia) e
  ci sono limiti per indirizzo, per account e per indirizzo IP: la forza bruta (1 su 200 000 per codice) non è praticabile;
- limiti per indirizzo email o per account superati: nessun errore (non si deve capire niente), semplicemente non parte altra email;
  limiti per IP o globali: 429, che riguarda solo chi sta esagerando;
- negli eventi di sicurezza non finiscono mai indirizzi email né codici.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timedelta

from . import account, posta
from .account import ErroreAccount, _chiave, _hash_codice, _testo, _data, _ora, limite, evento

DURATA_CODICE = timedelta(minutes=15)
TENTATIVI_PER_CODICE = 5
INVII_PER_EMAIL = (3, account.ORA)           # email al massimo 3 all'ora allo stesso indirizzo
INVII_PER_ACCOUNT = (5, account.ORA)
INVII_PER_IP = (10, account.ORA)
INVII_PER_EMAIL_GIORNO = (6, 24 * account.ORA)   # e al massimo 6 al giorno
INVII_GLOBALI = (300, account.ORA)           # tetto sulla posta in uscita di tutta l'app: conta solo le email partite davvero
CODICI_BRUCIATI = (3, 24 * account.ORA)      # chi brucia 3 codici (5 errori ciascuno) non ne riceve altri per un giorno: conta chi sbaglia (IP/account), non l'email
PROVE_PER_IP = (30, account.QUARTO_D_ORA)    # codici provati (giusti o no) da un indirizzo IP
USA_E_GETTA = {"mailinator.com", "guerrillamail.com", "guerrillamail.net", "10minutemail.com", "yopmail.com", "tempmail.com",
               "temp-mail.org", "trashmail.com", "throwawaymail.com", "sharklasers.com", "getnada.com", "dispostable.com",
               "maildrop.cc", "fakeinbox.com", "mailnesia.com", "tempail.com"}
NON_VALIDO = "Codice non valido o scaduto"
EMAIL_NON_VALIDA = "Indirizzo email non valido"
RISPOSTA_INVIO = {"ok": True, "scade_minuti": int(DURATA_CODICE.total_seconds() // 60)}


# ---------------------------------------------------------------- indirizzi e codici
def normalizza_email(testo) -> str:
    """L'indirizzo come si confronta: NFKC, senza spazi ai lati, minuscolo. Alza ErroreAccount se non sembra un indirizzo o se è di
    un servizio usa-e-getta (indirizzi senza proprietario vero non servono a recuperare un account)."""
    if not isinstance(testo, str):
        raise ErroreAccount(EMAIL_NON_VALIDA)
    e = unicodedata.normalize("NFKC", testo[:300]).strip().casefold()
    if not posta.indirizzo_valido(e) or e.count("@") != 1:
        raise ErroreAccount(EMAIL_NON_VALIDA)
    if e.rsplit("@", 1)[1] in USA_E_GETTA:
        raise ErroreAccount("Questo servizio di email temporanee non è accettato: usa il tuo indirizzo vero")
    return e


def indirizzo_base(email: str) -> str:
    """L'indirizzo «base» per confronti e limiti: senza l'eventuale +etichetta prima della @ (anna+prova@x.it vale anna@x.it).
    Così con un solo indirizzo non si creano tanti account né si aggirano i limiti per indirizzo."""
    locale, dominio = email.rsplit("@", 1)
    return (locale.split("+", 1)[0] or locale) + "@" + dominio


def _gia_di_un_account(db: sqlite3.Connection, email: str, tranne: int | None = None) -> bool:
    """C'è già un account (diverso da `tranne`) con questo indirizzo o con una sua variante +etichetta? Gli indirizzi salvati sono
    già normalizzati (minuscolo, NFKC); gli account sono pochi, quindi si confrontano tutti."""
    base = indirizzo_base(email)
    return any(r["id"] != tranne and indirizzo_base(r["email"]) == base
               for r in db.execute("SELECT id, email FROM utenti WHERE email IS NOT NULL"))


def _email_o_none(testo) -> str | None:
    try:
        return normalizza_email(testo)
    except ErroreAccount:
        return None


def nuovo_codice_numerico() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def _h(codice) -> str:
    cifre = "".join(c for c in (codice if isinstance(codice, str) else "")[:20] if c.isdigit())
    return hashlib.sha256(("email-" + cifre).encode()).hexdigest()


def _puo(db: sqlite3.Connection, chiave: str, massimo: int, finestra: float) -> bool:
    """Conta un invio e dice se è ancora permesso, senza alzare errori (il chiamante non deve far capire niente)."""
    try:
        limite.consuma(db, chiave, massimo, finestra)
        return True
    except ErroreAccount:
        return False


def _tetti_ip(db: sqlite3.Connection, ip: str | None) -> None:
    """Limiti che riguardano chi sta chiedendo: 429 vero (non rivelano niente su altri). Il tetto globale qui si guarda soltanto:
    si conta in `_invia`, sulle email che partono davvero (le richieste a vuoto non lo esauriscono a danno di tutti)."""
    limite.troppi(db, _chiave("email-invii-globali"), *INVII_GLOBALI)
    if ip:
        limite.consuma(db, _chiave("email-invii-ip", ip), *INVII_PER_IP)


def _invia(db: sqlite3.Connection, messaggio) -> None:
    """Manda un'email contandola nel tetto globale (se è pieno non parte: nessun errore, come per gli altri limiti di invio)."""
    if _puo(db, _chiave("email-invii-globali"), *INVII_GLOBALI):
        posta.invia(messaggio)


def _chi_prova(ip: str | None, utente_id: int | None = None) -> str:
    """Di CHI si contano i codici bruciati: di chi li prova (il suo account se ha già fatto l'accesso, altrimenti il suo indirizzo
    IP), MAI dell'indirizzo email a cui sono diretti: così nessuno può bloccare l'email o il recupero di un altro."""
    return _chiave("email-bruciati", "account", utente_id) if utente_id is not None else _chiave("email-bruciati", "ip", ip or "-")


def _invio_consentito(db: sqlite3.Connection, email: str, chi: str) -> bool:
    """Si può mandare un altro codice a questo indirizzo? Al massimo 3 all'ora e 6 al giorno (le varianti +etichetta contano
    insieme), e niente a chi (`chi`: vedi `_chi_prova`) nell'ultimo giorno ha già bruciato CODICI_BRUCIATI codici.
    Conta l'invio solo se è consentito."""
    base = indirizzo_base(email)
    return (limite.sotto(db, chi, *CODICI_BRUCIATI)
            and limite.sotto(db, _chiave("email-invio-giorno", base), *INVII_PER_EMAIL_GIORNO)
            and _puo(db, _chiave("email-invio", base), *INVII_PER_EMAIL)
            and _puo(db, _chiave("email-invio-giorno", base), *INVII_PER_EMAIL_GIORNO))


def email_di(db: sqlite3.Connection, utente_id: int) -> dict:
    """Per «Il tuo account»: l'email verificata (o None) e quella in attesa di conferma (o None)."""
    riga = db.execute("SELECT email FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    attesa = db.execute("SELECT email FROM codici_email WHERE utente_id = ? AND scopo = 'verifica' AND usato = 0 AND scade > ? "
                        "ORDER BY id DESC LIMIT 1", (utente_id, _testo(_ora(None)))).fetchone()
    return {"email": riga["email"] if riga else None, "email_in_attesa": attesa["email"] if attesa else None}


def _nuovo_codice(db: sqlite3.Connection, scopo: str, email: str, utente_id: int | None, adesso: datetime,
                  dati: dict | None = None) -> str:
    """Salva un codice nuovo e lo restituisce. Per un account, i vecchi dello stesso tipo smettono di valere. Le iscrizioni (senza
    account) invece no: la richiesta di un altro con lo stesso indirizzo non deve annullare quella in attesa."""
    codice = nuovo_codice_numerico()
    if utente_id is not None:
        db.execute("UPDATE codici_email SET usato = 1 WHERE utente_id = ? AND scopo = ?", (utente_id, scopo))
    db.execute("INSERT INTO codici_email (scopo, utente_id, email, codice_hash, dati, creato, scade) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (scopo, utente_id, email, _h(codice), json.dumps(dati) if dati else None, _testo(adesso), _testo(adesso + DURATA_CODICE)))
    db.commit()
    return codice


def _prova_codice(db: sqlite3.Connection, riga: sqlite3.Row | None, codice, adesso: datetime, chi: str) -> bool:
    """Confronta a tempo costante con il codice vivo e conta il tentativo: dopo TENTATIVI_PER_CODICE errori il codice è bruciato.
    Il tentativo si conta PRIMA del confronto e nella stessa transazione (con 40 richieste insieme il codice ammette comunque
    al massimo TENTATIVI_PER_CODICE prove). Il confronto avviene anche se non c'è nessun codice (stesso lavoro)."""
    giusto = hmac.compare_digest(_h(codice), riga["codice_hash"] if riga else _h("-"))
    if riga is None:
        return False
    account._transazione(db)
    try:
        prova = db.execute("UPDATE codici_email SET tentativi = tentativi + 1 WHERE id = ? AND usato = 0 AND tentativi < ?",
                           (riga["id"], TENTATIVI_PER_CODICE))
        if prova.rowcount != 1:                              # usato, bruciato o finite le prove (anche da richieste insieme)
            db.commit()
            return False
        if giusto:
            db.execute("UPDATE codici_email SET usato = 1 WHERE id = ?", (riga["id"],))
            db.commit()
            return True
        bruciato = db.execute("UPDATE codici_email SET usato = 1 WHERE id = ? AND tentativi >= ?", (riga["id"], TENTATIVI_PER_CODICE))
        if bruciato.rowcount:
            db.execute("INSERT INTO tentativi (chiave, quando) VALUES (?, ?)",
                       (chi, account._orologio()))
        db.commit()
        return False
    except BaseException:
        db.rollback()
        raise


def _codice_vivo(db: sqlite3.Connection, scopo: str, adesso: datetime, *, utente_id: int | None = None,
                 email: str | None = None) -> sqlite3.Row | None:
    if utente_id is not None:
        return db.execute("SELECT * FROM codici_email WHERE scopo = ? AND utente_id = ? AND usato = 0 AND scade > ? "
                          "ORDER BY id DESC LIMIT 1", (scopo, utente_id, _testo(adesso))).fetchone()
    return db.execute("SELECT * FROM codici_email WHERE scopo = ? AND email = ? AND usato = 0 AND scade > ? "
                      "ORDER BY id DESC LIMIT 1", (scopo, email, _testo(adesso))).fetchone()


def _pulisci(db: sqlite3.Connection, adesso: datetime) -> None:
    db.execute("DELETE FROM codici_email WHERE scade < ?", (_testo(adesso - timedelta(days=1)),))


# ---------------------------------------------------------------- aggiungere o cambiare l'email
def chiedi_verifica(db: sqlite3.Connection, utente_id: int, email_grezza, password: str | None, ip: str | None = None,
                    adesso: datetime | None = None, *, senza_password: bool = False, sessione: str | None = None) -> dict:
    """Manda un codice all'indirizzo indicato. Serve la password (chi ruba una sessione non può mettere la propria email e poi
    «recuperare» l'account), salvo `senza_password` (alla registrazione, dove la password è appena stata scelta).
    Stessa risposta se l'indirizzo è libero, è già di un altro account o ha troppi invii alle spalle."""
    adesso = _ora(adesso)
    email = normalizza_email(email_grezza)
    if not senza_password:
        account._controlla_password_attuale(db, utente_id, password, sessione)
    _tetti_ip(db, ip)
    _pulisci(db, adesso)
    libero = not _gia_di_un_account(db, email, tranne=utente_id)
    gia_mia = db.execute("SELECT 1 FROM utenti WHERE email = ? AND id = ?", (email, utente_id)).fetchone() is not None
    consentito = (_invio_consentito(db, email, _chi_prova(ip, utente_id))
                  and _puo(db, _chiave("email-invio-account", utente_id), *INVII_PER_ACCOUNT))
    if libero and not gia_mia and consentito:
        codice = _nuovo_codice(db, "verifica", email, utente_id, adesso)
        _invia(db, posta.modello_verifica(email, codice, int(DURATA_CODICE.total_seconds() // 60)))
    else:
        limite.aggiungi(db, _chiave("email-nessun-invio"))       # stessa scrittura sul database di quando si invia
        if not libero and consentito:
            _invia(db, posta.modello_gia_registrato(email))
    evento("email_verifica_richiesta", ip=ip)
    return dict(RISPOSTA_INVIO)


def conferma_email(db: sqlite3.Connection, utente_id: int, codice, ip: str | None = None, adesso: datetime | None = None) -> dict:
    adesso = _ora(adesso)
    limite.consuma(db, _chiave("email-prove-account", utente_id), 20, account.ORA)
    if ip:
        limite.consuma(db, _chiave("email-prove-ip", ip), *PROVE_PER_IP)
    riga = _codice_vivo(db, "verifica", adesso, utente_id=utente_id)
    if not _prova_codice(db, riga, codice, adesso, _chi_prova(ip, utente_id)):
        evento("email_codice_sbagliato", ip=ip)
        raise ErroreAccount(NON_VALIDO, 403)
    vecchia = db.execute("SELECT email FROM utenti WHERE id = ?", (utente_id,)).fetchone()["email"]
    try:
        db.execute("UPDATE utenti SET email = ? WHERE id = ?", (riga["email"], utente_id))
        db.commit()
    except sqlite3.IntegrityError:                           # un altro l'ha verificata nel frattempo
        db.rollback()
        raise ErroreAccount(NON_VALIDO, 403) from None
    evento("email_verificata", ip=ip)
    if vecchia and vecchia != riga["email"]:
        _invia(db, posta.modello_email_cambiata(vecchia))
    return {"ok": True, "email": riga["email"]}


def togli_email(db: sqlite3.Connection, utente_id: int, password: str, sessione: str | None = None) -> dict:
    account._controlla_password_attuale(db, utente_id, password, sessione)
    db.execute("UPDATE utenti SET email = NULL WHERE id = ?", (utente_id,))
    db.execute("UPDATE codici_email SET usato = 1 WHERE utente_id = ?", (utente_id,))
    db.commit()
    evento("email_tolta")
    return {"ok": True}


# ---------------------------------------------------------------- password dimenticata, via email
def chiedi_recupero(db: sqlite3.Connection, email_grezza, ip: str | None = None, adesso: datetime | None = None) -> dict:
    """Risponde sempre allo stesso modo: l'email esista o no, sia scritta bene o male."""
    adesso = _ora(adesso)
    _tetti_ip(db, ip)
    _pulisci(db, adesso)
    email = _email_o_none(email_grezza)
    riga = db.execute("SELECT id FROM utenti WHERE email = ?", (email,)).fetchone() if email else None
    consentito = email is not None and _invio_consentito(db, email, _chi_prova(ip))
    if riga and consentito and _puo(db, _chiave("email-invio-account", riga["id"]), *INVII_PER_ACCOUNT):
        codice = _nuovo_codice(db, "recupero", email, riga["id"], adesso)
        _invia(db, posta.modello_recupero(email, codice, int(DURATA_CODICE.total_seconds() // 60)))
    else:                           # tante scritture quante ne fa un invio vero (account, codice, tetto globale): stesso tempo
        for _ in range(3):
            limite.aggiungi(db, _chiave("email-nessun-invio"))
    evento("recupero_email_richiesto", ip=ip)
    return dict(RISPOSTA_INVIO)


def recupera_con_email(db: sqlite3.Connection, email_grezza, codice, nuova: str, ip: str | None = None,
                       adesso: datetime | None = None) -> str:
    """Nuova password con il codice ricevuto per email. Chiude tutte le sessioni e restituisce il NUOVO codice di recupero."""
    adesso = _ora(adesso)
    account.valida_password(nuova)                           # prima del codice: una password debole non brucia il codice
    email = _email_o_none(email_grezza) or ""
    with account.uno_alla_volta(ip):
        return _recupera_con_email(db, email, codice, nuova, ip, adesso)


def _recupera_con_email(db, email, codice, nuova, ip, adesso) -> str:
    righe = account._prenota_tentativo(db, "recupero", email or "-", ip)    # stessi limiti e attese del recupero normale
    if ip:
        limite.consuma(db, _chiave("email-prove-ip", ip), *PROVE_PER_IP)
    riga_utente = db.execute("SELECT * FROM utenti WHERE email = ?", (email,)).fetchone() if email else None
    riga = _codice_vivo(db, "recupero", adesso, utente_id=riga_utente["id"]) if riga_utente else None
    if not _prova_codice(db, riga, codice, adesso, _chi_prova(ip)):
        account._fallimento("recupero", email or "-", ip)
        raise ErroreAccount("Email o codice non validi", 403)
    limite.annulla(db, righe)
    account.valida_password(nuova, riga_utente["nome_utente"])             # (password uguale al nome: caso raro, serve una nuova email)
    nuovo = account.nuovo_codice(20)
    cambio = db.execute("UPDATE utenti SET password_hash = ?, recupero_hash = ?, senza_password = 0 WHERE id = ?",
                        (account.hash_password(nuova), _hash_codice(nuovo), riga_utente["id"]))
    db.commit()
    if cambio.rowcount != 1:
        raise ErroreAccount("Email o codice non validi", 403)
    account._riuscito(db, [], "recupero", email or "-", ip)
    account.esci_da_tutti(db, riga_utente["id"], scollega_social=True)
    evento("recupero", nome=riga_utente["nome_utente"], ip=ip, via="email")
    return nuovo


# ---------------------------------------------------------------- come ci si iscrive (FANTA_REGISTRAZIONE)
MODI_REGISTRAZIONE = ("invito", "aperta", "email")
ISCRIZIONI_PER_IP = (5, account.ORA)         # richieste di iscrizione con email da un indirizzo IP
ISCRIZIONI_GLOBALI = (100, 24 * account.ORA)
ISCRIZIONI_GIORNO_PREDEFINITO = 10           # modo `aperta`: account nuovi al massimo in 24 ore (FANTA_ISCRIZIONI_GIORNO)
CHIUSE_PER_OGGI = "Per oggi le iscrizioni sono chiuse: riprova domani"


def iscrizioni_al_giorno() -> int:
    try:
        v = int(os.environ.get("FANTA_ISCRIZIONI_GIORNO", ""))
        return v if v > 0 else ISCRIZIONI_GIORNO_PREDEFINITO
    except ValueError:
        return ISCRIZIONI_GIORNO_PREDEFINITO


def _tetto_del_giorno(db: sqlite3.Connection, adesso: datetime) -> None:
    """Modo `aperta`: quanti account sono nati nelle ultime 24 ore (chi ha un invito non conta qui: lo decide l'amministratore)."""
    nuovi = db.execute("SELECT COUNT(*) FROM utenti WHERE creato > ?", (_testo(adesso - timedelta(days=1)),)).fetchone()[0]
    if nuovi >= iscrizioni_al_giorno():
        raise ErroreAccount(CHIUSE_PER_OGGI, 403)


def _hash_segreto(segreto) -> str:
    return hashlib.sha256(("iscrizione-" + (segreto if isinstance(segreto, str) else "")[:100]).encode()).hexdigest()


def modo_registrazione() -> str:
    """- `invito` (predefinito): serve un invito dell'amministratore; l'email è facoltativa.
    - `email`: serve l'invito E un'email: l'account nasce solo quando l'email è verificata col codice.
    - `aperta`: nessun invito; serve un'email verificata col codice (tetto MAX_UTENTI e limiti per indirizzo IP).
    In `aperta` un invito valido funziona anche col percorso classico (account subito, email facoltativa)."""
    m = os.environ.get("FANTA_REGISTRAZIONE", "invito").strip().lower()
    return m if m in MODI_REGISTRAZIONE else "invito"


def invito_classico(modo: str, invito) -> bool:
    """Questa richiesta segue il percorso di sempre (invito, account subito)? Sì in modalità `invito`, e in `aperta` se c'è un invito."""
    return modo == "invito" or (modo == "aperta" and bool(str(invito or "").strip()))


def _invito_vivo(db: sqlite3.Connection, invito, adesso: datetime, ip: str | None) -> sqlite3.Row:
    """Controlla un invito SENZA usarlo, con gli stessi limiti e lo stesso messaggio di `account.registra`."""
    invito = invito if isinstance(invito, str) else ""
    righe = account.prenota_invito(db, ip)                   # controlla e conta insieme (richieste in parallelo comprese)
    try:
        limite.consuma(db, _chiave("registra-invito", _hash_codice(invito)), *account.prove_per_invito(db, invito))
    except ErroreAccount:
        limite.annulla(db, righe)
        raise
    inv = db.execute("SELECT * FROM inviti WHERE codice_hash = ?", (_hash_codice(invito),)).fetchone()
    if not account.invito_vivo(inv, adesso):
        evento("registrazione_invito_sbagliato", ip=ip)
        raise ErroreAccount(account.INVITO_NON_VALIDO, 403)
    limite.annulla(db, righe)
    return inv


ISCRIZIONE_POSTA_SPENTA = ("Su questo server l'iscrizione con l'email non è disponibile: l'invio delle email è spento "
                           "e il codice non potrebbe arrivare. Chiedi un invito a chi gestisce il server.")


def iscrivi(db: sqlite3.Connection, nome_utente: str, password: str, email_grezza, invito: str | None, ip: str | None = None,
            adesso: datetime | None = None, accetto_termini: bool | None = None) -> dict:
    """Prima metà dell'iscrizione con email (modi `aperta` e `email`): controlla tutto, tiene nome e hash della password in attesa e
    manda il codice. L'account NON esiste ancora: nasce in `conferma_iscrizione`. Risposta uguale se l'indirizzo è già di un
    altro account (in quel caso la mail dice che l'account c'è già) o ha troppi invii."""
    adesso = _ora(adesso)
    termini = account.controlla_termini(accetto_termini)
    modo = modo_registrazione()
    if modo == "invito":
        raise ErroreAccount(account.INVITO_NON_VALIDO, 403)
    if not posta.attiva():       # il codice non può arrivare: l'iscrizione resterebbe in attesa per sempre. Uguale per ogni indirizzo, prima dei limiti
        raise ErroreAccount(ISCRIZIONE_POSTA_SPENTA, 503, codice="iscrizione_posta_spenta")
    if ip:
        limite.consuma(db, _chiave("iscrizioni-ip", ip), *ISCRIZIONI_PER_IP)
        limite.consuma(db, _chiave("registra-ip", ip), *account.REGISTRAZIONI_PER_IP)
    limite.troppi(db, _chiave("iscrizioni-globali"), *ISCRIZIONI_GLOBALI)     # si conta solo quando parte davvero un codice
    inv = _invito_vivo(db, invito, adesso, ip) if modo == "email" else None
    nome = account.valida_nome(nome_utente)
    account.valida_password(password, nome)
    if not email_grezza:
        raise ErroreAccount("Per iscriverti serve un indirizzo email: ti mandiamo un codice per confermarlo")
    email = normalizza_email(email_grezza)
    _tetti_ip(db, ip)
    password_hash = account.hash_password(password)           # sempre, anche se poi non si invia niente: stesso tempo
    if db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] >= account.max_utenti():
        raise ErroreAccount("Le registrazioni sono chiuse: è stato raggiunto il numero massimo di utenti", 403)
    if modo == "aperta":
        _tetto_del_giorno(db, adesso)
    # Il nome già preso NON si dice qui: chi scrive un nome e un indirizzo qualsiasi non deve poter scoprire quali nomi esistono.
    # Lo si dice in `conferma_iscrizione`, dopo che chi si iscrive ha dimostrato di avere l'email. Qui la risposta è sempre la stessa.
    occupata = _gia_di_un_account(db, email)
    consentito = _invio_consentito(db, email, _chi_prova(ip))
    segreto = secrets.token_urlsafe(24)          # lega il codice a QUESTA iscrizione: si rimanda insieme al codice
    if consentito and not occupata:
        codice = _nuovo_codice(db, "iscrizione", email, None, adesso,
                               {"nome": nome, "nome_visualizzato": account.nome_da_mostrare(nome_utente, nome), "password_hash": password_hash, "invito": inv["codice_hash"] if inv else None,
                                "segreto": _hash_segreto(segreto), "termini": termini})
        limite.aggiungi(db, _chiave("iscrizioni-globali"))
        _invia(db, posta.modello_verifica(email, codice, int(DURATA_CODICE.total_seconds() // 60), nome))
    else:
        limite.aggiungi(db, _chiave("email-nessun-invio"))
        if consentito:
            _invia(db, posta.modello_gia_registrato(email))
    evento("iscrizione_richiesta", nome=nome, ip=ip)
    return {"ok": True, "verifica_email": True, "scade_minuti": int(DURATA_CODICE.total_seconds() // 60), "iscrizione": segreto}


def _iscrizione_viva(db: sqlite3.Connection, email: str, segreto, adesso: datetime) -> sqlite3.Row | None:
    """L'iscrizione in attesa per questo indirizzo che ha QUESTO segreto (ce ne possono essere più d'una, di persone diverse).
    Si confrontano tutte a tempo costante; senza il segreto giusto non c'è nessuna iscrizione."""
    atteso, trovata = _hash_segreto(segreto), None
    for r in db.execute("SELECT * FROM codici_email WHERE scopo = 'iscrizione' AND email = ? AND usato = 0 AND scade > ? "
                        "ORDER BY id", (email, _testo(adesso))):
        try:
            salvato = json.loads(r["dati"] or "{}").get("segreto") or ""
        except (ValueError, AttributeError):
            salvato = ""
        if hmac.compare_digest(str(salvato), atteso) and isinstance(segreto, str) and segreto:
            trovata = r
    return trovata


def conferma_iscrizione(db: sqlite3.Connection, email_grezza, codice, ip: str | None = None, dispositivo: str = "",
                        adesso: datetime | None = None, segreto: str | None = None):
    """Seconda metà: con il codice giusto E il segreto restituito da `iscrivi` nasce l'account (già con l'email verificata) e si
    apre la sessione. Restituisce (utente, token, codice di recupero)."""
    adesso = _ora(adesso)
    if ip:
        limite.consuma(db, _chiave("email-prove-ip", ip), *PROVE_PER_IP)
    email = _email_o_none(email_grezza) or ""
    righe = account._prenota_tentativo(db, "iscrizione", email or "-", ip)
    riga = _iscrizione_viva(db, email, segreto, adesso) if email else None
    if not _prova_codice(db, riga, codice, adesso, _chi_prova(ip)):
        account._fallimento("iscrizione", email or "-", ip)
        raise ErroreAccount(NON_VALIDO, 403)
    limite.annulla(db, righe)
    dati = json.loads(riga["dati"])
    recupero = account.nuovo_codice(20)
    account._transazione(db)
    try:
        ruolo = "utente"
        if db.execute("SELECT 1 FROM utenti WHERE nome_utente = ?", (dati["nome"],)).fetchone():     # ora l'email è provata: si può dire
            raise ErroreAccount("Questo nome utente è già preso: ricomincia l'iscrizione con un altro nome")
        if dati.get("invito"):                                # modo `email`: l'invito si usa adesso, e solo se vale ancora
            inv = db.execute("SELECT * FROM inviti WHERE codice_hash = ?", (dati["invito"],)).fetchone()
            if not account.invito_vivo(inv, adesso):
                raise ErroreAccount(account.INVITO_NON_VALIDO, 403)
            ruolo = inv["ruolo"]
        else:                                                 # modo `aperta`: tetto di account nuovi al giorno
            _tetto_del_giorno(db, adesso)
        if db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] >= account.max_utenti():
            raise ErroreAccount("Le registrazioni sono chiuse: è stato raggiunto il numero massimo di utenti", 403)
        cur = db.execute("INSERT INTO utenti (nome_utente, nome_visualizzato, password_hash, recupero_hash, ruolo, creato, email) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (dati["nome"], dati.get("nome_visualizzato") or dati["nome"], dati["password_hash"], _hash_codice(recupero), ruolo, _testo(adesso), email))
        if dati.get("invito") and not account.consuma_invito(db, dati["invito"], cur.lastrowid):
            raise ErroreAccount(account.INVITO_NON_VALIDO, 403)
        if dati.get("termini"):
            account.segna_termini(db, cur.lastrowid, adesso)
        account._segna_indirizzo(db, cur.lastrowid, ip)
        db.commit()
    except sqlite3.IntegrityError:                           # nome o email presi un attimo prima
        db.rollback()
        raise ErroreAccount("Questo nome utente o questo indirizzo sono già in uso: ricomincia l'iscrizione") from None
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    limite.azzera(db, _chiave("iscrizione", email, ip or "-"))
    utente = account.trova(db, cur.lastrowid)
    evento("registrazione", nome=utente.nome_utente, ip=ip, ruolo=utente.ruolo, via="email")
    return utente, account._apri_sessione(db, utente.id, dispositivo, adesso), recupero
