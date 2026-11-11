"""Accedere e registrarsi con Google (e, in futuro, altri servizi), e collegare Google a un account che c'è già.

Il giro con Google lo fa il SERVER (flusso «authorization code» con PKCE): il browser o l'app aprono solo l'indirizzo che
il server dà e alla fine ricevono un codice monouso di 60 secondi, da riscattare mostrando un segreto che non è mai uscito
dal loro dispositivo. Il token di Google non arriva mai al client e non si conserva.

Regole che non si toccano:
- L'email di Google NON collega mai da sola un account esistente: si collega solo da una sessione già autenticata.
- Chi si iscrive con Google rispetta le regole del server (`FANTA_REGISTRAZIONE`): invito, o email affidabile, o iscrizioni aperte.
- Senza `FANTA_GOOGLE_CLIENT_ID` e `FANTA_GOOGLE_CLIENT_SECRET` il servizio è spento (le rotte rispondono 404).
- Nei log mai token, codici, `state`, email: solo il tipo di evento e un prefisso dell'identificativo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from . import account, account_email
from .account import ErroreAccount, evento, limite

PROVIDER = ("google",)
GOOGLE_AUTORIZZA = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_CHIAVI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_EMITTENTI = ("https://accounts.google.com", "accounts.google.com")
TIMEOUT = 5                                    # secondi, per ogni chiamata in uscita
DURATA_GIRO = timedelta(minutes=10)
DURATA_CODICE = timedelta(seconds=60)
DURATA_ISCRIZIONE = timedelta(minutes=15)
DURATA_RICONFERMA = timedelta(minutes=5)
AVVII_PER_IP = (20, account.ORA)
RITORNI_RIUSCITI_GLOBALI = (2000, 24 * account.ORA)      # solo i giri arrivati in fondo (token di Google valido): pochi indirizzi non possono esaurirlo
RITORNI_PER_IP = (60, account.ORA)
RISCATTI_PER_IP = (30, account.ORA)
COMPLETAMENTI_PER_IP = (10, account.ORA)
SCOPI = ("accedi", "collega", "riconferma")
PIATTAFORME = ("web", "ios")
_FORMATO_SFIDA = re.compile(r"[A-Za-z0-9_-]{43}")
_FORMATO_VERIFICATORE = re.compile(r"[A-Za-z0-9._~-]{43,128}")
_FORMATO_SEGRETO = re.compile(r"[A-Za-z0-9_-]{20,100}")
NON_ATTIVO = "L'accesso con Google non è attivo"
SESSIONE_DIVERSA = "Questa operazione va fatta dal dispositivo in cui hai cominciato"
CODICE_NON_VALIDO = "Il collegamento con Google è scaduto: riprova"


class ErroreSocial(ErroreAccount):
    pass


# ---------------------------------------------------------------- configurazione (solo variabili d'ambiente)
def _client_id() -> str:
    return os.environ.get("FANTA_GOOGLE_CLIENT_ID", "").strip()


def _client_secret() -> str:
    return os.environ.get("FANTA_GOOGLE_CLIENT_SECRET", "").strip()


def _redirect() -> str:
    """L'indirizzo di ritorno registrato presso Google: SOLO da `FANTA_GOOGLE_REDIRECT` e solo https. Non si ricostruisce dall'intestazione
    Host (chi la scrive può cambiarla): senza questa variabile il servizio resta spento."""
    v = os.environ.get("FANTA_GOOGLE_REDIRECT", "").strip()
    return v if v.startswith("https://") and len(v) <= 300 else ""


def google_attivo() -> bool:
    return bool(_client_id() and _client_secret() and _redirect())


def provider_attivi() -> list[str]:
    return ["google"] if google_attivo() else []


def indirizzo_ritorno() -> str:
    return _redirect()


# ---------------------------------------------------------------- piccoli strumenti
def _h(valore: str) -> str:
    return hashlib.sha256(("social-" + valore).encode()).hexdigest()


def _t(quando: datetime) -> str:
    return account._testo(quando)


def sfida_di(verificatore: str) -> str:
    """S256: la sfida che il client manda all'inizio e che il server confronta quando ha il verificatore."""
    return base64.urlsafe_b64encode(hashlib.sha256(verificatore.encode("ascii")).digest()).rstrip(b"=").decode()


def _pulisci(db: sqlite3.Connection, adesso: datetime) -> None:
    """Le email in chiaro di un giro non restano oltre la sua ultima scadenza (codice monouso o iscrizione); i giri vecchi si cancellano."""
    db.execute("UPDATE flussi_social SET esito = NULL WHERE esito IS NOT NULL AND COALESCE(iscrizione_scade, codice_scade, scade) < ?", (_t(adesso),))
    db.execute("DELETE FROM flussi_social WHERE scade < ?", (_t(adesso - timedelta(days=1)),))
    db.commit()


def _limiti_avvio(db: sqlite3.Connection, ip: str | None) -> None:
    if ip:
        limite.consuma(db, account._chiave("social-avvii-ip", ip), *AVVII_PER_IP)


# ---------------------------------------------------------------- chiamate a Google (si sostituiscono nei test)
def _cambia_codice(codice: str, verificatore: str, redirect: str) -> str:
    """Scambia il codice con Google (HTTPS, indirizzo fisso, secret del server) e restituisce l'id_token."""
    import requests
    r = requests.post(GOOGLE_TOKEN, data={"code": codice, "client_id": _client_id(), "client_secret": _client_secret(),
                                          "redirect_uri": redirect, "grant_type": "authorization_code",
                                          "code_verifier": verificatore},
                      timeout=TIMEOUT, allow_redirects=False)
    r.raise_for_status()
    token = r.json().get("id_token")
    if not isinstance(token, str):
        raise ValueError("risposta senza id_token")
    return token


def _scarica_chiavi() -> tuple[dict, int]:
    """Le chiavi pubbliche di Google (JWKS) e per quanti secondi si possono tenere."""
    import requests
    r = requests.get(GOOGLE_CHIAVI, timeout=TIMEOUT, allow_redirects=False)
    r.raise_for_status()
    m = re.search(r"max-age=(\d+)", r.headers.get("Cache-Control", ""))
    return r.json(), int(m.group(1)) if m else 3600


_cache_chiavi: dict = {"chiavi": {}, "scade": 0.0, "letta": 0.0}


def _chiave_per(kid: str):
    """La chiave pubblica con questo `kid`. Cache secondo Cache-Control (tra 5 minuti e 24 ore); un `kid` sconosciuto
    fa rileggere l'elenco al massimo una volta al minuto."""
    import jwt
    adesso = time.time()
    c = _cache_chiavi
    vecchia = adesso >= c["scade"]
    sconosciuta = kid not in c["chiavi"] and adesso - c["letta"] >= 60
    if vecchia or sconosciuta:
        jwks, durata = _scarica_chiavi()
        c["chiavi"] = {k["kid"]: k for k in jwks.get("keys", []) if isinstance(k, dict) and k.get("kid") and k.get("kty") == "RSA"}
        c["letta"], c["scade"] = adesso, adesso + min(max(durata, 300), 86400)
    jwk = c["chiavi"].get(kid)
    if jwk is None:
        raise ValueError("chiave sconosciuta")
    return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))


# ---------------------------------------------------------------- verifica del token
def verifica_id_token(token: str, nonce_atteso: str) -> dict:
    """Controlla firma (solo RS256), emittente, destinatario (il nostro client id), scadenza e nonce. Alza ValueError se qualcosa non va."""
    import jwt
    try:
        intestazione = jwt.get_unverified_header(token)
        if intestazione.get("alg") != "RS256" or not isinstance(intestazione.get("kid"), str):
            raise ValueError("algoritmo")
        dati = jwt.decode(token, _chiave_per(intestazione["kid"]), algorithms=["RS256"], audience=_client_id(),
                          issuer=list(GOOGLE_EMITTENTI), leeway=30,
                          options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.PyJWTError as e:
        raise ValueError("token non valido") from e
    if not isinstance(dati.get("sub"), str) or not dati["sub"] or len(dati["sub"]) > 255:
        raise ValueError("sub")
    if not hmac.compare_digest(str(dati.get("nonce") or ""), nonce_atteso):
        raise ValueError("nonce")
    return dati


def _dominio_fidato(email: str) -> bool:
    """L'email vale come verificata (per iscriversi e per il recupero) solo se è @gmail.com o di un dominio che l'amministratore ha
    indicato in `FANTA_GOOGLE_DOMINI` (elenco separato da virgole). Un dominio Workspace qualsiasi no: chi lo amministra può creare indirizzi a piacere."""
    dominio = email.rsplit("@", 1)[-1]
    altri = {d.strip().lower() for d in os.environ.get("FANTA_GOOGLE_DOMINI", "").split(",") if d.strip()}
    return dominio == "gmail.com" or dominio in altri


def _esito_da_claims(dati: dict) -> dict:
    email = str(dati.get("email") or "").strip().lower()[:300]
    verificata = dati.get("email_verified") in (True, "true")
    affidabile = bool(email) and verificata and _dominio_fidato(email)
    return {"sub": dati["sub"], "email": email, "verificata": verificata, "affidabile": affidabile}


# ---------------------------------------------------------------- 1. inizio del giro
def inizia(db: sqlite3.Connection, provider: str, scopo: str, sfida: str, piattaforma: str, utente_id: int | None, ip: str | None,
           redirect: str, adesso: datetime | None = None, sessione: str | None = None, password: str = "") -> dict:
    if provider != "google" or not google_attivo():
        raise ErroreAccount(NON_ATTIVO, 404)
    if scopo not in SCOPI or piattaforma not in PIATTAFORME or not _FORMATO_SFIDA.fullmatch(sfida or ""):
        raise ErroreAccount("Richiesta non valida")
    if scopo in ("collega", "riconferma") and not utente_id:
        raise ErroreAccount("Accesso richiesto", 401)
    if scopo == "accedi":
        utente_id = None
    adesso = account._ora(adesso)
    _limiti_avvio(db, ip)
    if scopo == "collega":                           # collegare un accesso nuovo è delicato: serve la password (o la riconferma, se non ce l'ha)
        account._controlla_password_attuale(db, utente_id, password, sessione)
    _pulisci(db, adesso)
    stato, nonce, verificatore = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    db.execute("INSERT INTO flussi_social (stato_hash, provider, scopo, utente_id, nonce, verificatore_provider, sfida, piattaforma, creato, scade, sessione_hash) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (_h(stato), provider, scopo, utente_id, nonce, verificatore, sfida, piattaforma, _t(adesso), _t(adesso + DURATA_GIRO),
                account._hash_token(sessione) if scopo != "accedi" and sessione else None))
    db.commit()
    url = GOOGLE_AUTORIZZA + "?" + urlencode({
        "client_id": _client_id(), "redirect_uri": redirect, "response_type": "code", "scope": "openid email",
        "state": stato, "nonce": nonce, "code_challenge": sfida_di(verificatore), "code_challenge_method": "S256",
        "prompt": "select_account"})
    evento("social_inizio", provider=provider, scopo=scopo, ip=ip)
    return {"url": url, "scade_minuti": int(DURATA_GIRO.total_seconds() // 60)}


# ---------------------------------------------------------------- 2. il ritorno di Google (nessuna sessione, nessun cookie)
def ritorno(db: sqlite3.Connection, codice: str | None, stato: str | None, errore: str | None, ip: str | None, redirect: str,
            adesso: datetime | None = None) -> tuple[str, str]:
    """Restituisce (piattaforma, codice_monouso o motivo dell'errore). Chi chiama fa il redirect: ?social=<codice> oppure ?social_errore=<motivo>."""
    if not google_attivo():
        raise ErroreAccount(NON_ATTIVO, 404)
    adesso = account._ora(adesso)
    valido = isinstance(stato, str) and 20 <= len(stato) <= 200
    if ip:
        try:
            limite.consuma(db, account._chiave("social-ritorni-ip", ip), *RITORNI_PER_IP)
        except ErroreAccount:
            if not valido:
                raise
            nota = db.execute("SELECT piattaforma FROM flussi_social WHERE stato_hash = ?", (_h(stato),)).fetchone()
            if nota is None or nota["piattaforma"] != "ios":
                raise
            return "ios", "non_valido"             # su iOS si torna comunque all'app, non a una pagina web
    if not valido:
        return "web", "non_valido"
    _pulisci(db, adesso)
    # il giro si consuma subito e una volta sola: lo stesso ritorno non vale due volte
    account._transazione(db)
    riga = db.execute("SELECT * FROM flussi_social WHERE stato_hash = ?", (_h(stato),)).fetchone()
    if riga is None or riga["ritornato"] or riga["scade"] <= _t(adesso):
        db.rollback()
        evento("social_rifiutato", motivo="stato", ip=ip)
        if riga is None:
            return "web", "non_valido"
        return riga["piattaforma"], "scaduto"
    db.execute("UPDATE flussi_social SET ritornato = 1 WHERE id = ?", (riga["id"],))
    db.commit()
    piattaforma = riga["piattaforma"]
    if errore or not isinstance(codice, str) or not 1 <= len(codice) <= 2000:
        evento("social_rifiutato", motivo="annullato" if errore == "access_denied" else "errore_provider", ip=ip)
        return piattaforma, "annullato" if errore == "access_denied" else "non_valido"
    try:
        token = _cambia_codice(codice, riga["verificatore_provider"], redirect)
        esito = _esito_da_claims(verifica_id_token(token, riga["nonce"]))
    except Exception as e:                           # rete, firma, nonce, destinatario, scadenza: all'utente un solo messaggio
        evento("social_rifiutato", motivo=type(e).__name__, ip=ip)
        return piattaforma, "non_valido"
    limite.consuma(db, account._chiave("social-ritorni-riusciti"), *RITORNI_RIUSCITI_GLOBALI)
    monouso = secrets.token_urlsafe(32)
    db.execute("UPDATE flussi_social SET esito = ?, codice_hash = ?, codice_scade = ? WHERE id = ?",
               (json.dumps(esito), _h(monouso), _t(adesso + DURATA_CODICE), riga["id"]))
    db.commit()
    return piattaforma, monouso


# ---------------------------------------------------------------- 3. il client riscatta il codice monouso
def scambio(db: sqlite3.Connection, codice: str, verificatore: str, utente_sessione: account.Utente | None, ip: str | None,
            dispositivo: str = "", adesso: datetime | None = None, sessione: str | None = None) -> dict:
    """Restituisce {"stato": "ok", "utente", "token"} | {"stato": "nuovo", ...} | {"stato": "collegato"} | {"stato": "riconfermato"}."""
    if not google_attivo():
        raise ErroreAccount(NON_ATTIVO, 404)
    adesso = account._ora(adesso)
    if ip:
        limite.consuma(db, account._chiave("social-riscatti-ip", ip), *RISCATTI_PER_IP)
    if not (isinstance(codice, str) and 20 <= len(codice) <= 200 and isinstance(verificatore, str)
            and _FORMATO_VERIFICATORE.fullmatch(verificatore)):
        raise ErroreAccount(CODICE_NON_VALIDO, 403)
    _pulisci(db, adesso)
    account._transazione(db)
    riga = db.execute("SELECT * FROM flussi_social WHERE codice_hash = ?", (_h(codice),)).fetchone()
    # il codice si brucia subito, anche se poi il verificatore è sbagliato: un solo tentativo
    if riga is None or riga["usato"] or not riga["codice_scade"] or riga["codice_scade"] <= _t(adesso) or not riga["esito"]:
        db.rollback()
        evento("social_rifiutato", motivo="codice", ip=ip)
        raise ErroreAccount(CODICE_NON_VALIDO, 403)
    db.execute("UPDATE flussi_social SET usato = 1 WHERE id = ?", (riga["id"],))
    db.commit()
    if not hmac.compare_digest(sfida_di(verificatore), riga["sfida"]):
        evento("social_rifiutato", motivo="verificatore", ip=ip)
        raise ErroreAccount(CODICE_NON_VALIDO, 403)
    esito = json.loads(riga["esito"])
    scopo = riga["scopo"]
    if scopo in ("collega", "riconferma"):
        # lo stesso utente NON basta: deve essere la stessa sessione (dispositivo) che ha avviato il giro
        if (utente_sessione is None or utente_sessione.id != riga["utente_id"] or not sessione or not riga["sessione_hash"]
                or not hmac.compare_digest(account._hash_token(sessione), riga["sessione_hash"])):
            evento("social_rifiutato", motivo="sessione_diversa", ip=ip)
            raise ErroreAccount(SESSIONE_DIVERSA, 403)
        db.execute("UPDATE flussi_social SET esito = NULL WHERE id = ?", (riga["id"],))
        if scopo == "collega":
            return _collega(db, utente_sessione.id, esito, adesso)
        return _riconferma(db, riga["sessione_hash"], utente_sessione.id, esito, adesso)
    # scopo accedi
    ident = db.execute("SELECT * FROM identita_esterne WHERE provider = 'google' AND soggetto = ?", (esito["sub"],)).fetchone()
    if ident is not None:
        db.execute("UPDATE flussi_social SET esito = NULL WHERE id = ?", (riga["id"],))
        db.execute("UPDATE identita_esterne SET ultimo_uso = ? WHERE id = ?", (_t(adesso), ident["id"]))
        utente = account.trova(db, ident["utente_id"])
        email_utente = db.execute("SELECT email FROM utenti WHERE id = ?", (utente.id,)).fetchone()["email"]
        nuovo_dispositivo = bool(email_utente) and bool(ip) and not account._indirizzo_noto(db, utente.nome_utente, ip)
        account._segna_indirizzo(db, utente.id, ip)
        token = account._apri_sessione(db, utente.id, dispositivo, adesso)        # fa il commit
        evento("social_accesso", provider="google", id=esito["sub"][:6], ip=ip)
        if nuovo_dispositivo:                        # stesso avviso dell'accesso con password: «sei stato tu?»
            from . import posta
            posta.invia(posta.modello_accesso_nuovo(email_utente, dispositivo, adesso.strftime("%d/%m/%Y %H:%M UTC")))
        return {"stato": "ok", "utente": utente, "token": token}
    if esito["email"] and esito["verificata"] and account_email._gia_di_un_account(db, esito["email"]):
        db.execute("UPDATE flussi_social SET esito = NULL WHERE id = ?", (riga["id"],))
        db.commit()
        evento("social_rifiutato", motivo="email_gia_usata", ip=ip)
        raise ErroreSocial("Questo indirizzo ha già un account: entra come fai di solito e poi, in Impostazioni > Il tuo account, "
                           "collega Google.", 409, codice="email_gia_usata")
    modo = account_email.modo_registrazione()
    if modo != "invito" and not esito["affidabile"]:
        db.execute("UPDATE flussi_social SET esito = NULL WHERE id = ?", (riga["id"],))
        db.commit()
        raise ErroreSocial("Per iscriverti usa il modulo con la tua email.", 403, codice="email_non_affidabile")
    segreto = secrets.token_urlsafe(32)
    db.execute("UPDATE flussi_social SET iscrizione_hash = ?, iscrizione_scade = ? WHERE id = ?",
               (_h(segreto), _t(adesso + DURATA_ISCRIZIONE), riga["id"]))
    db.commit()
    return {"stato": "nuovo", "iscrizione": segreto, "provider": "google", "nome_suggerito": _suggerisci_nome(esito["email"]),
            "serve_invito": modo != "aperta"}


def _suggerisci_nome(email: str) -> str:
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())[:20].lstrip("._-")
    return base if len(base) >= 3 else "giocatore"


def _collega(db: sqlite3.Connection, utente_id: int, esito: dict, adesso: datetime) -> dict:
    """Aggiunge Google all'account di chi ha la sessione. Un Google solo per account, e un Google non sta in due account."""
    try:
        db.execute("INSERT INTO identita_esterne (utente_id, provider, soggetto, email, email_verificata, creata, ultimo_uso) "
                   "VALUES (?, 'google', ?, ?, ?, ?, ?)",
                   (utente_id, esito["sub"], esito["email"] or None, int(esito["verificata"]), _t(adesso), _t(adesso)))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        evento("social_rifiutato", motivo="gia_collegato")
        raise ErroreSocial("Questo Google è già collegato a un account (forse questo): scollegalo da lì per usarlo qui.", 409,
                           codice="google_gia_collegato") from None
    evento("social_collegato", provider="google", id=esito["sub"][:6])
    avviso = db.execute("SELECT email FROM utenti WHERE id = ?", (utente_id,)).fetchone()["email"]
    if avviso:                                       # chi ha un'email verificata sa subito che è stato collegato un accesso nuovo
        from . import posta
        posta.invia(posta.modello_google_collegato(avviso, adesso.strftime("%d/%m/%Y %H:%M UTC")))
    return {"stato": "collegato", "accessi": accessi(db, utente_id)}


def _riconferma(db: sqlite3.Connection, sessione_hash: str, utente_id: int, esito: dict, adesso: datetime) -> dict:
    """Chi è solo-Google conferma un'azione delicata (eliminare l'account, mettere una password...) rientrando da Google, per 5 minuti."""
    ident = db.execute("SELECT 1 FROM identita_esterne WHERE utente_id = ? AND provider = 'google' AND soggetto = ?",
                       (utente_id, esito["sub"])).fetchone()
    if ident is None:
        raise ErroreSocial("Hai scelto un altro account Google: scegli quello collegato a SchieraXI.", 403, codice="google_diverso")
    db.execute("UPDATE sessioni SET riconfermata = ? WHERE utente_id = ? AND token_hash = ? AND revocata = 0", (_t(adesso), utente_id, sessione_hash))
    db.commit()
    return {"stato": "riconfermato"}


def riconfermato_di_recente(db: sqlite3.Connection, utente_id: int, sessione: str | None, adesso: datetime | None = None) -> bool:
    """La riconferma vale solo per la sessione (dispositivo) che l'ha fatta."""
    if not sessione:
        return False
    soglia = _t(account._ora(adesso) - DURATA_RICONFERMA)
    return db.execute("SELECT 1 FROM sessioni WHERE utente_id = ? AND token_hash = ? AND revocata = 0 AND riconfermata > ?",
                      (utente_id, account._hash_token(sessione), soglia)).fetchone() is not None


# ---------------------------------------------------------------- 4. nuovo account con Google
def completa(db: sqlite3.Connection, iscrizione: str, nome_utente: str, invito: str, accetto_termini: bool, ip: str | None,
             dispositivo: str = "", adesso: datetime | None = None):
    """Crea l'account con le stesse regole del server. Restituisce (utente, token). Niente password e niente codice di recupero."""
    if not google_attivo():
        raise ErroreAccount(NON_ATTIVO, 404)
    adesso = account._ora(adesso)
    if ip:
        limite.consuma(db, account._chiave("social-completa-ip", ip), *COMPLETAMENTI_PER_IP)
    if not accetto_termini:
        raise ErroreAccount("Per iscriverti devi accettare Privacy e Termini")
    if not (isinstance(iscrizione, str) and _FORMATO_SEGRETO.fullmatch(iscrizione)):
        raise ErroreAccount(CODICE_NON_VALIDO, 403)
    with account.uno_alla_volta(ip):
        nome = account.valida_nome(nome_utente)
        riga = db.execute("SELECT * FROM flussi_social WHERE iscrizione_hash = ?", (_h(iscrizione),)).fetchone()
        if riga is None or riga["iscrizione_usata"] or riga["iscrizione_scade"] <= _t(adesso) or not riga["esito"]:
            raise ErroreAccount(CODICE_NON_VALIDO, 403)
        esito = json.loads(riga["esito"])
        modo = account_email.modo_registrazione()
        if modo != "invito" and not esito["affidabile"]:
            raise ErroreSocial("Per iscriverti usa il modulo con la tua email.", 403, codice="email_non_affidabile")
        inv = None
        if modo in ("invito", "email"):
            inv = account_email._invito_vivo(db, invito, adesso, ip)              # stessi limiti e stesso messaggio di sempre
        elif ip:
            limite.consuma(db, account._chiave("registra-ip", ip), *account.REGISTRAZIONI_PER_IP)
        password_hash = account.hash_password(secrets.token_urlsafe(32))          # mai mostrata: nessun accesso con password
        recupero_hash = account._hash_codice(secrets.token_urlsafe(32))
        account._transazione(db)
        try:
            preso = db.execute("UPDATE flussi_social SET iscrizione_usata = 1 WHERE id = ? AND iscrizione_usata = 0", (riga["id"],))
            if preso.rowcount != 1:
                raise ErroreAccount(CODICE_NON_VALIDO, 403)
            if db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] >= account.max_utenti():
                raise ErroreAccount("Le registrazioni sono chiuse: è stato raggiunto il numero massimo di utenti", 403)
            if modo == "aperta":
                account_email._tetto_del_giorno(db, adesso)
            if db.execute("SELECT 1 FROM utenti WHERE nome_utente = ?", (nome,)).fetchone():
                raise ErroreAccount("Questo nome utente è già preso: scegline un altro")
            email = esito["email"] if esito["affidabile"] and not account_email._gia_di_un_account(db, esito["email"]) else None
            cur = db.execute("INSERT INTO utenti (nome_utente, nome_visualizzato, password_hash, recupero_hash, ruolo, creato, email, senza_password) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                             (nome, account.nome_da_mostrare(nome_utente, nome), password_hash, recupero_hash,
                              inv["ruolo"] if inv else "utente", _t(adesso), email))
            db.execute("INSERT INTO identita_esterne (utente_id, provider, soggetto, email, email_verificata, creata, ultimo_uso) "
                       "VALUES (?, 'google', ?, ?, ?, ?, ?)",
                       (cur.lastrowid, esito["sub"], esito["email"] or None, int(esito["verificata"]), _t(adesso), _t(adesso)))
            if inv and not account.consuma_invito(db, inv["codice_hash"], cur.lastrowid):
                raise ErroreAccount(account.INVITO_NON_VALIDO, 403)
            account.segna_termini(db, cur.lastrowid, adesso)
            db.execute("UPDATE flussi_social SET esito = NULL WHERE id = ?", (riga["id"],))
            account._segna_indirizzo(db, cur.lastrowid, ip)
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            raise ErroreAccount("Questo nome utente (o questo Google) è già in uso: riprova con un altro nome") from None
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
    utente = account.trova(db, cur.lastrowid)
    evento("social_registrazione", provider="google", id=esito["sub"][:6], ip=ip, ruolo=utente.ruolo)
    return utente, account._apri_sessione(db, utente.id, dispositivo, adesso)


# ---------------------------------------------------------------- accessi di un account
def accessi(db: sqlite3.Connection, utente_id: int) -> dict:
    riga = db.execute("SELECT senza_password FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    # l'email di Google si mostra solo se Google l'ha verificata (le altre restano nel database ma non escono)
    social = [{"provider": r["provider"], "email": r["email"] if r["email_verificata"] else None, "creata": r["creata"], "ultimo_uso": r["ultimo_uso"]}
              for r in db.execute("SELECT provider, email, email_verificata, creata, ultimo_uso FROM identita_esterne WHERE utente_id = ? "
                                  "ORDER BY id", (utente_id,))]
    return {"password": bool(riga) and not riga["senza_password"], "social": social, "disponibili": provider_attivi()}


def email_google(db: sqlite3.Connection, utente_id: int) -> str | None:
    """L'email verificata dell'identità Google collegata a QUESTO account (o None). Serve solo a mostrarla all'interessato nel profilo:
    non vale per il recupero della password né per gli inviti, che usano soltanto l'email dell'account."""
    riga = db.execute("SELECT email FROM identita_esterne WHERE utente_id = ? AND provider = 'google' AND email IS NOT NULL "
                      "AND email != '' AND email_verificata = 1 ORDER BY id LIMIT 1", (utente_id,)).fetchone()
    return riga["email"] if riga else None


def profilo_email(db: sqlite3.Connection, utente_id: int, dati_email: dict) -> dict:
    """Completa `email_di` per il profilo: se l'account non ha un'email sua ma c'è un Google con email, la mostra con `email_origine`
    «google». `email_origine` è «account» (email verificata dell'account), «google» o None. Nient'altro di Google esce da qui."""
    if dati_email.get("email"):
        return dati_email | {"email_origine": "account"}
    google = email_google(db, utente_id)
    return dati_email | {"email": google, "email_origine": "google" if google else None}


def scollega(db: sqlite3.Connection, utente_id: int, provider: str) -> dict:
    """Toglie un accesso solo se ne resta un altro (password o un altro servizio). Controllo e cancellazione in una transazione sola."""
    if provider not in PROVIDER:
        raise ErroreAccount("Servizio sconosciuto", 404)
    account._transazione(db)
    try:
        riga = db.execute("SELECT senza_password FROM utenti WHERE id = ?", (utente_id,)).fetchone()
        altri = db.execute("SELECT COUNT(*) FROM identita_esterne WHERE utente_id = ? AND provider != ?", (utente_id, provider)).fetchone()[0]
        ha_password = bool(riga) and not riga["senza_password"]
        presente = db.execute("SELECT 1 FROM identita_esterne WHERE utente_id = ? AND provider = ?", (utente_id, provider)).fetchone()
        if presente is None:
            raise ErroreAccount("Questo accesso non è collegato", 404)
        if not ha_password and not altri:
            raise ErroreSocial("Prima aggiungi una password o un altro accesso.", 409, codice="ultimo_accesso")
        db.execute("DELETE FROM identita_esterne WHERE utente_id = ? AND provider = ?", (utente_id, provider))
        db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    evento("social_scollegato", provider=provider)
    return {"accessi": accessi(db, utente_id)}


def imposta_password(db: sqlite3.Connection, utente_id: int, password: str, sessione: str | None = None) -> str:
    """Per chi è entrato solo con Google: aggiunge una password (serve la riconferma recente con Google). Restituisce il codice di recupero."""
    riga = db.execute("SELECT * FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    if riga is None or not riga["senza_password"]:
        raise ErroreAccount("Hai già una password: usa «Cambia password»")
    if not riconfermato_di_recente(db, utente_id, sessione):
        raise account.ErroreAccount("Conferma prima con Google", 403, codice="serve_riconferma")
    account.valida_password(password, riga["nome_utente"])
    recupero = account.nuovo_codice(20)
    db.execute("UPDATE utenti SET password_hash = ?, recupero_hash = ?, senza_password = 0 WHERE id = ?",
               (account.hash_password(password), account._hash_codice(recupero), utente_id))
    db.commit()
    evento("social_password_impostata")
    return recupero


# ---------------------------------------------------------------- log degli accessi
class _SenzaQuery:
    """Il ritorno di Google ha `code` e `state` nell'indirizzo: nel log degli accessi di uvicorn si scrive solo il percorso."""

    def filter(self, record) -> bool:
        a = record.args
        if isinstance(a, tuple) and len(a) >= 3 and isinstance(a[2], str) and "?" in a[2]:
            percorso, _, query = a[2].partition("?")
            # il ritorno di Google (code, state) e il redirect finale con il codice monouso (?social=, ?social_errore=)
            if percorso.startswith("/api/account/social/") or re.search(r"(^|&)social(_errore)?=", query):
                record.args = a[:2] + (percorso,) + a[3:]
        return True


def togli_query_dai_log() -> None:
    import logging
    logging.getLogger("uvicorn.access").addFilter(_SenzaQuery())


AVVISO_PROXY = ("Account accesi ma FANTA_PROXY non è 1: se il server sta dietro un proxy (per esempio nginx sullo stesso computer) "
                "i limiti per indirizzo vedono l'indirizzo del proxy e non quello di chi chiede, quindi non distinguono gli utenti. "
                "Imposta FANTA_PROXY=1 nelle variabili del servizio.")


def avvisa_se_manca_il_proxy() -> None:
    """All'avvio, con gli account accesi (o Google attivo) e senza FANTA_PROXY=1: un avviso chiaro nel registro del servizio.
    Il server parte lo stesso (un server raggiunto direttamente, senza proxy, non ne ha bisogno)."""
    if (account.multiutente() or google_attivo()) and os.environ.get("FANTA_PROXY", "").strip() != "1":
        import logging
        logging.getLogger("uvicorn.error").warning(AVVISO_PROXY)
