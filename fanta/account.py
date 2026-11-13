"""Account degli utenti (modalità multiutente, spenta di norma: si accende con FANTA_MULTIUTENTE=1).

Un piccolo database `account.sqlite` (nella cartella dati, vedi `percorsi.cartella_account`) con utenti, sessioni, inviti e
codici di reset. Qui c'è solo la logica, senza FastAPI: le rotte stanno in `rotte_account.py`. Si entra con nome utente e
password; l'email è facoltativa (vedi `account_email.py`).

- password: scrypt (libreria standard), sale casuale, confronto a tempo costante; il formato salvato contiene i parametri,
  così si possono alzare senza rompere quelle già salvate (al primo accesso riuscito si ricalcola con quelli nuovi);
  password e nomi si normalizzano in Unicode NFKC (la «é» composta o scomposta, le lettere a larghezza piena...);
- sessione: token casuale da 256 bit; nel database c'è solo il suo SHA-256, quindi chi legge il file non può usarlo; scade
  dopo 30 giorni senza uso e comunque dopo 180; si revoca; cambiando la password si chiudono tutte e se ne apre una nuova;
- registrazione: solo con un codice d'invito (7 giorni, monouso o per più amici) generato da un amministratore; tetto MAX_UTENTI; il controllo
  dell'invito, del tetto e del nome avviene in una transazione sola (due richieste insieme non creano due account);
- password dimenticata, due vie: il «codice di recupero» (mostrato una volta sola alla registrazione) oppure un codice
  monouso di 24 ore generato da un amministratore;
- limiti di tentativi salvati nel database (valgono anche dopo un riavvio): per nome utente e indirizzo insieme (attesa
  crescente fino a 15 minuti, mai per sempre), per nome utente da tutti gli indirizzi (ma chi ci era già entrato da quel
  indirizzo o da quel dispositivo fidato passa lo stesso), per indirizzo; accesso e recupero hanno contatori separati. Il
  conteggio globale non blocca: rallenta (fino a 3 secondi) chi non è noto. Così un attaccante blocca soprattutto sé stesso;
- da fuori non si capisce se un nome esiste: stesso messaggio, stesso codice e stesso lavoro (un hash fittizio per i nomi
  che non esistono);
- registro degli eventi di sicurezza (`sicurezza.log`, con rotazione e righe tenute al massimo 30 giorni): mai password né
  codici; gli indirizzi si scrivono accorciati (IPv4 senza l'ultimo numero, IPv6 solo la rete /64).
"""
from __future__ import annotations

import base64
import collections
import contextlib
import hashlib
import hmac
import logging
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import percorsi, registro

INATTIVITA = timedelta(days=30)               # una sessione non usata per 30 giorni si chiude
DURATA_MASSIMA = timedelta(days=180)          # e comunque dopo 180 giorni bisogna rientrare
DURATA_SESSIONE = DURATA_MASSIMA              # durata del cookie (la scadenza vera la decide il server)
RINNOVO_DOPO = timedelta(hours=1)             # l'ultimo uso si scrive al massimo una volta all'ora
DURATA_INVITO = timedelta(days=7)
DURATA_RESET = timedelta(hours=24)
MAX_UTENTI_PREDEFINITO = 30
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # senza lettere e cifre che si confondono (O/0, I/1)
PASSWORD_MIN, PASSWORD_MAX = 10, 200
RUOLI = ("utente", "amministratore")
COSTO = {"n": 2 ** 16, "r": 8, "p": 1}       # costo di scrypt (64 MB e circa mezzo secondo): i test lo abbassano
CALCOLI_INSIEME = 2                          # quanti scrypt alla volta: la memoria del server resta sotto controllo
BANALI = {"password", "password1", "password12", "password123", "password1234", "qwertyuiop", "qwerty12345", "1234567890",
          "12345678910", "0123456789", "abcdefghij", "iloveyou12", "passw0rd123", "fantacalcio", "schieraxi", "schieraxi1",
          "juventus123", "forzajuve123", "forzainter123", "forzamilan123", "forzaroma123", "forzanapoli", "adminadmin",
          "administrator", "letmein1234", "welcome1234", "123456789a", "a123456789", "qazwsxedcr", "schieraxischieraxi",
          "passwordpassword", "qwertyqwerty", "asdfghjkl", "zxcvbnm123", "ciaociao12", "napoli1926", "juventus1897",
          "sempreinter", "forzaitalia"}
# parole che, con qualche numero o simbolo intorno, non bastano («Password2026!», «fantacalcio_1»)
RADICI_BANALI = {"password", "passw0rd", "qwerty", "qwertyuiop", "asdfgh", "asdfghjkl", "abcdef", "abcdefgh", "iloveyou",
                 "fantacalcio", "schieraxi", "juventus", "juve", "inter", "milan", "napoli", "roma", "lazio",
                 "admin", "administrator", "welcome", "letmein", "ciao", "calcio", "forzajuve", "forzainter", "forzamilan",
                 "forzaroma", "forzanapoli", "forzalazio", "segreto", "segreta", "amore", "123456"}
_NOME = re.compile(r"[a-z0-9][a-z0-9._-]{2,31}")


class ErroreAccount(Exception):
    """Un errore da mostrare all'utente, con il codice HTTP che gli spetta."""

    def __init__(self, messaggio: str, stato: int = 400, riprova_tra: int | None = None, codice: str | None = None):
        super().__init__(messaggio)
        self.messaggio, self.stato, self.riprova_tra = messaggio, stato, riprova_tra
        self.codice = codice                         # facoltativo: un nome breve per i client (per esempio «serve_riconferma»)


@dataclass(frozen=True)
class Utente:
    id: int
    nome_utente: str
    ruolo: str
    creato: str
    nome_visualizzato: str = ""      # come l'ha scritto l'utente (maiuscole comprese); vuoto = si mostra `nome_utente`

    @property
    def nome_mostrato(self) -> str:
        return self.nome_visualizzato or self.nome_utente

    @property
    def amministratore(self) -> bool:
        return self.ruolo == "amministratore"

    def come_dict(self) -> dict:
        return {"id": self.id, "nome_utente": self.nome_utente, "nome_visualizzato": self.nome_mostrato,
                "ruolo": self.ruolo, "creato": self.creato}


UTENTE_LOCALE = Utente(0, "locale", "amministratore", "")      # a interruttore spento: l'unico utente, senza accesso


def multiutente() -> bool:
    """L'interruttore. Spento (predefinito): l'app resta quella di sempre, senza accessi."""
    return os.environ.get("FANTA_MULTIUTENTE", "").strip() == "1"


def max_utenti() -> int:
    try:
        v = int(os.environ.get("MAX_UTENTI", ""))
        return v if v > 0 else MAX_UTENTI_PREDEFINITO
    except ValueError:
        return MAX_UTENTI_PREDEFINITO


def _ora(adesso: datetime | None) -> datetime:
    return adesso or datetime.now(timezone.utc)


def _testo(quando: datetime) -> str:
    return quando.astimezone(timezone.utc).isoformat(timespec="seconds")


def _data(testo: str) -> datetime:
    return datetime.fromisoformat(testo)


# ---------------------------------------------------------------- database
# Ogni voce è una migrazione: si applicano in ordine, una sola volta, e il numero resta in PRAGMA user_version.
# Solo aggiunte: una migrazione non cancella né cambia mai i dati che ci sono.
# REGOLA: una migrazione già rilasciata NON si modifica mai, nemmeno per «una colonna in più» (i database già migrati non la
# riceverebbero: è successo con flussi_social.sessione_hash). Ogni cambio di struttura è una voce NUOVA in fondo. Una voce può essere
# testo SQL oppure una funzione `f(db)` (per le condizioni, come «aggiungi se manca»). tests/test_migrazioni.py controlla che un
# database migrato passo per passo e uno creato alla versione finale abbiano lo stesso schema.
def _riparazione_sessione_hash(db: sqlite3.Connection) -> None:
    """flussi_social.sessione_hash era stata aggiunta dentro la migrazione che crea la tabella, già applicata altrove: ai database
    esistenti mancava. Qui si aggiunge solo se manca (database nuovi e database già sistemati a mano la hanno)."""
    if "sessione_hash" not in [r[1] for r in db.execute("PRAGMA table_info(flussi_social)")]:
        db.execute("ALTER TABLE flussi_social ADD COLUMN sessione_hash TEXT")


MIGRAZIONI = [
    """
    CREATE TABLE utenti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_utente TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        recupero_hash TEXT NOT NULL,
        ruolo TEXT NOT NULL DEFAULT 'utente' CHECK (ruolo IN ('utente', 'amministratore')),
        creato TEXT NOT NULL
    );
    CREATE TABLE sessioni (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        creata TEXT NOT NULL,
        scade TEXT NOT NULL,
        ultimo_uso TEXT NOT NULL,
        dispositivo TEXT NOT NULL DEFAULT '',
        revocata INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX sessioni_utente ON sessioni(utente_id);
    CREATE TABLE inviti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codice_hash TEXT NOT NULL UNIQUE,
        etichetta TEXT NOT NULL,
        ruolo TEXT NOT NULL DEFAULT 'utente' CHECK (ruolo IN ('utente', 'amministratore')),
        creato TEXT NOT NULL,
        scade TEXT NOT NULL,
        usato INTEGER NOT NULL DEFAULT 0,
        usato_da INTEGER REFERENCES utenti(id) ON DELETE SET NULL
    );
    CREATE TABLE reset_password (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
        codice_hash TEXT NOT NULL,
        creato TEXT NOT NULL,
        scade TEXT NOT NULL,
        usato INTEGER NOT NULL DEFAULT 0
    );
    """,
    # limiti giornalieri per utente (importazioni, proposte di scambi): una riga per utente, giorno e cosa
    """
    CREATE TABLE contatori (
        utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
        giorno TEXT NOT NULL,
        cosa TEXT NOT NULL,
        n INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (utente_id, giorno, cosa)
    );
    """,
    # la lega di ogni utente e la sua procedura guidata (a che passo è: così si riprende da un altro dispositivo)
    """
    CREATE TABLE leghe (
        utente_id INTEGER PRIMARY KEY REFERENCES utenti(id) ON DELETE CASCADE,
        tipo TEXT NOT NULL DEFAULT 'classic' CHECK (tipo IN ('classic')),
        stato TEXT NOT NULL DEFAULT 'da_fare' CHECK (stato IN ('da_fare', 'in_corso', 'completato', 'saltato')),
        passo TEXT NOT NULL DEFAULT 'benvenuto',
        demo INTEGER NOT NULL DEFAULT 0,
        aggiornato TEXT NOT NULL
    );
    """,
    # tentativi (falliti o contati) per i limiti: la chiave è un hash, quindi nel file non ci sono né nomi né indirizzi;
    # indirizzi da cui un utente è già entrato (hash anche loro): da lì passa anche se il suo nome è sotto attacco
    """
    CREATE TABLE tentativi (
        chiave TEXT NOT NULL,
        quando REAL NOT NULL
    );
    CREATE INDEX tentativi_chiave ON tentativi(chiave, quando);
    CREATE INDEX tentativi_quando ON tentativi(quando);
    CREATE TABLE indirizzi_noti (
        utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
        indirizzo_hash TEXT NOT NULL,
        ultimo REAL NOT NULL,
        PRIMARY KEY (utente_id, indirizzo_hash)
    );
    """,
    # email FACOLTATIVA (solo aggiunte): `utenti.email` contiene solo indirizzi verificati ed è unica; i codici di verifica, di
    # recupero e di iscrizione (6 cifre, brevi, monouso) stanno in `codici_email`, con il solo hash
    """
    ALTER TABLE utenti ADD COLUMN email TEXT;
    CREATE UNIQUE INDEX utenti_email ON utenti(email) WHERE email IS NOT NULL;
    CREATE TABLE codici_email (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scopo TEXT NOT NULL CHECK (scopo IN ('verifica', 'recupero', 'iscrizione')),
        utente_id INTEGER REFERENCES utenti(id) ON DELETE CASCADE,
        email TEXT NOT NULL,
        codice_hash TEXT NOT NULL,
        dati TEXT,
        creato TEXT NOT NULL,
        scade TEXT NOT NULL,
        usato INTEGER NOT NULL DEFAULT 0,
        tentativi INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX codici_email_utente ON codici_email(utente_id, scopo);
    CREATE INDEX codici_email_email ON codici_email(email, scopo);
    """,
    # nome come scritto dall'utente (maiuscole comprese), solo per mostrarlo: accesso e unicità restano su `nome_utente`
    """
    ALTER TABLE utenti ADD COLUMN nome_visualizzato TEXT;
    """,
    # token dedicato al widget iOS (solo aggiunte): uno per utente, solo l'hash, scadenza fissa; vale solo per leggere /api/oggi e /api/widget
    """
    CREATE TABLE token_widget (
        utente_id INTEGER PRIMARY KEY REFERENCES utenti(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        etichetta TEXT NOT NULL DEFAULT 'widget',
        creato TEXT NOT NULL,
        scade TEXT NOT NULL,
        ultimo_uso TEXT NOT NULL
    );
    """,
    # inviti con più usi (solo aggiunte): `usi_max` = quante persone possono entrare con lo stesso codice (1 = come sempre), `usi`
    # quante sono già entrate, `revocato` = l'amministratore l'ha annullato. `usato` resta e diventa 1 quando i posti sono finiti.
    """
    ALTER TABLE inviti ADD COLUMN usi_max INTEGER NOT NULL DEFAULT 1;
    ALTER TABLE inviti ADD COLUMN usi INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE inviti ADD COLUMN revocato INTEGER NOT NULL DEFAULT 0;
    UPDATE inviti SET usi = 1 WHERE usato = 1;
    """,
    # accesso con Google (solo aggiunte): identità esterne collegate agli account, giri di accesso in corso (vita 10 minuti),
    # `senza_password` per chi è entrato solo con Google, `riconfermata` = quando ha riconfermato con Google (5 minuti di validità)
    """
    ALTER TABLE utenti ADD COLUMN senza_password INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE sessioni ADD COLUMN riconfermata TEXT;
    CREATE TABLE IF NOT EXISTS identita_esterne (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        utente_id INTEGER NOT NULL REFERENCES utenti(id) ON DELETE CASCADE,
        provider TEXT NOT NULL CHECK (provider IN ('google', 'apple')),
        soggetto TEXT NOT NULL,
        email TEXT,
        email_verificata INTEGER NOT NULL DEFAULT 0,
        email_privata INTEGER NOT NULL DEFAULT 0,
        creata TEXT NOT NULL,
        ultimo_uso TEXT,
        UNIQUE (provider, soggetto),
        UNIQUE (utente_id, provider)
    );
    CREATE TABLE IF NOT EXISTS flussi_social (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stato_hash TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        scopo TEXT NOT NULL CHECK (scopo IN ('accedi', 'collega', 'riconferma')),
        utente_id INTEGER,
        nonce TEXT NOT NULL,
        verificatore_provider TEXT NOT NULL,
        sfida TEXT NOT NULL,
        piattaforma TEXT NOT NULL CHECK (piattaforma IN ('web', 'ios')),
        creato TEXT NOT NULL,
        scade TEXT NOT NULL,
        ritornato INTEGER NOT NULL DEFAULT 0,
        esito TEXT,
        codice_hash TEXT UNIQUE,
        codice_scade TEXT,
        usato INTEGER NOT NULL DEFAULT 0,
        iscrizione_hash TEXT UNIQUE,
        iscrizione_scade TEXT,
        iscrizione_usata INTEGER NOT NULL DEFAULT 0,
        sessione_hash TEXT
    );
    """,
    # termini d'uso accettati (solo aggiunte, facoltative): quando e quale versione; vuote per chi si è iscritto prima o da un client vecchio
    """
    ALTER TABLE utenti ADD COLUMN termini_accettati TEXT;
    ALTER TABLE utenti ADD COLUMN termini_versione TEXT;
    """,
    _riparazione_sessione_hash,
]

# Versione dei testi «Privacy» e «Termini d'uso» (la data di «Ultimo aggiornamento» delle pagine): si cambia quando cambiano i testi.
VERSIONE_TERMINI = "2026-11-02"
TERMINI_RIFIUTATI = ("Per iscriverti devi accettare Privacy e Termini d'uso. / "
                     "To sign up you must accept the Privacy policy and the Terms of use.")


def controlla_termini(accetto_termini) -> bool:
    """`None` = il client non manda il campo (web e app vecchie): si iscrive lo stesso, ma senza traccia dell'accettazione.
    `False` = ha detto di no: errore. `True` = accettati: si registra quando e quale versione."""
    if accetto_termini is None:
        return False
    if accetto_termini is not True:
        raise ErroreAccount(TERMINI_RIFIUTATI, 400)
    return True


def segna_termini(db: sqlite3.Connection, utente_id: int, adesso: datetime) -> None:
    db.execute("UPDATE utenti SET termini_accettati = ?, termini_versione = ? WHERE id = ?", (_testo(adesso), VERSIONE_TERMINI, utente_id))

ROVINATO = ("Il database degli account (account.sqlite) non si riesce a leggere: forse è rovinato. Non ho cancellato niente. "
            "L'amministratore deve rimetterlo dalla copia di backup (cartella backup accanto al file) e riavviare il servizio.")


def _copia_prima_di_migrare(db: sqlite3.Connection, percorso: Path, versione: int) -> None:
    """Copia di sicurezza del file prima di cambiarne la struttura (cartella `backup` accanto al file). Se la copia non riesce
    non si migra: meglio un errore che dati senza rete. Nasce leggibile solo dal proprietario (600) come le copie serali, anche
    senza l'umask del servizio: dentro ci sono nomi, email e impronte delle password. Scade nel giro serale
    (backup.GIORNI_COPIE_MIGRAZIONE)."""
    cartella = percorso.parent / "backup"
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"{percorso.stem}-prima-della-migrazione-{versione}.sqlite"
    try:
        os.close(os.open(destinazione, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except FileExistsError:
        return
    copia = sqlite3.connect(destinazione)
    try:
        db.backup(copia)
    finally:
        copia.close()


def _applica_migrazioni(db: sqlite3.Connection, versione: int) -> None:
    """Applica le migrazioni mancanti, una alla volta. Prima di ognuna si rilegge `user_version`: se un altro processo l'ha già
    fatta (o la fa nello stesso istante e la nostra BEGIN IMMEDIATE fallisce su una colonna già aggiunta) si passa oltre."""
    for numero in range(versione, len(MIGRAZIONI)):
        if db.execute("PRAGMA user_version").fetchone()[0] > numero:
            continue
        try:
            voce = MIGRAZIONI[numero]
            if callable(voce):
                db.execute("BEGIN IMMEDIATE")
                voce(db)
                db.execute(f"PRAGMA user_version = {numero + 1}")
                db.execute("COMMIT")
            else:
                db.executescript("BEGIN IMMEDIATE;" + voce + f"PRAGMA user_version = {numero + 1}; COMMIT;")
        except sqlite3.OperationalError:
            if db.in_transaction:
                db.execute("ROLLBACK")
            if db.execute("PRAGMA user_version").fetchone()[0] > numero:       # l'ha fatta un altro processo: va bene
                continue
            raise


OCCUPATO ="Il server è molto occupato: riprova fra qualche secondo"
ATTESA_DATABASE = 15.0                       # secondi: quanto si aspetta il proprio turno sul database prima di dire «occupato»
_blocco_migrazioni = threading.Lock()


def _solo_proprietario(percorso: Path) -> None:
    """Il database e i suoi file di appoggio (-wal, -shm) leggibili solo dall'utente del servizio (chmod 600). Su Windows non fa niente."""
    if os.name != "posix":
        return
    for p in (percorso, percorso.with_name(percorso.name + "-wal"), percorso.with_name(percorso.name + "-shm")):
        try:
            if p.exists() and p.stat().st_mode & 0o077:
                os.chmod(p, 0o600)
        except OSError:
            pass


def _occupato(e: sqlite3.Error) -> bool:
    return isinstance(e, sqlite3.OperationalError) and any(x in str(e).lower() for x in ("locked", "busy"))


def apri(percorso: Path | None = None) -> sqlite3.Connection:
    """Apre (e se serve crea o aggiorna) il database degli account. Un file rovinato non si tocca: ErroreAccount 503.
    Tante richieste insieme su un database appena creato: le migrazioni le fa una sola (blocco), le altre aspettano; se il database
    è solo occupato (da un altro processo) il messaggio dice «occupato», non «rovinato»."""
    percorso = percorso or percorsi.cartella_account() / "account.sqlite"
    percorsi.cartella_privata(percorso.parent)
    if not percorso.exists():
        try:
            os.close(os.open(percorso, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))     # nasce già leggibile solo dal proprietario
        except FileExistsError:
            pass
    db = sqlite3.connect(percorso, timeout=ATTESA_DATABASE)
    try:
        db.row_factory = sqlite3.Row
        db.execute(f"PRAGMA busy_timeout = {int(ATTESA_DATABASE * 1000)}")   # con richieste insieme si aspetta il proprio turno
        db.execute("PRAGMA foreign_keys = ON")
        # In WAL, NORMAL non aspetta il disco a ogni conferma (solo ai checkpoint): sulla scheda SD del server ogni commit con
        # FULL costa decine di ms TENENDO il blocco di scrittura, e con tante richieste insieme le attese sommate superavano
        # i 15 secondi («database is locked»). Il file non si rovina mai; con un'interruzione di corrente si può perdere
        # l'ultima conferma (un contatore di tentativi o una sessione appena aperta).
        db.execute("PRAGMA synchronous = NORMAL")
        versione = db.execute("PRAGMA user_version").fetchone()[0]
        if versione > len(MIGRAZIONI):
            raise RuntimeError("Il database degli account è di una versione più nuova dell'app: aggiorna l'app")
        if versione < len(MIGRAZIONI) or db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            with _blocco_migrazioni:                     # una richiesta sola prepara il database, le altre aspettano qui
                if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                    db.execute("PRAGMA journal_mode = WAL")
                versione = db.execute("PRAGMA user_version").fetchone()[0]     # (un'altra può averlo appena fatto)
                if 0 < versione < len(MIGRAZIONI):
                    _copia_prima_di_migrare(db, percorso, versione)
                _applica_migrazioni(db, versione)
        _solo_proprietario(percorso)
    except sqlite3.DatabaseError as e:
        db.close()
        if _occupato(e):
            raise ErroreAccount(OCCUPATO, 503, 5) from None
        evento("database_illeggibile", percorso=percorso.name)
        raise ErroreAccount(ROVINATO, 503) from None
    except BaseException:
        db.close()
        raise
    return db


# ---------------------------------------------------------------- registro degli eventi di sicurezza
MAX_REGISTRO, COPIE_REGISTRO = 512 * 1024, 3
_blocco_registro = threading.Lock()


def _pulito(v) -> str:
    """Un valore da scrivere nel registro: niente a capo né caratteri strani (nessuno può inventarsi righe finte), corto."""
    return re.sub(r"[^\w.:@/+-]", "?", str(v), flags=re.ASCII)[:64]


def evento(tipo: str, **campi) -> None:
    """Una riga nel registro di sicurezza (accessi falliti, blocchi, reset...). Mai password, codici o token: chi chiama passa
    solo tipo, nome utente (se valido), indirizzo e motivo. Se il registro non si scrive, l'app va avanti lo stesso."""
    if not multiutente():
        return
    if campi.get("ip"):
        campi["ip"] = registro.accorcia_ip(campi["ip"])      # mai l'indirizzo intero: basta la rete
    riga = " ".join([datetime.now(timezone.utc).isoformat(timespec="seconds"), _pulito(tipo)]
                    + [f"{k}={_pulito(v)}" for k, v in campi.items() if v is not None]) + "\n"
    registro.scrivi(percorsi.cartella_account() / registro.FILE_SICUREZZA, riga.rstrip("\n"), MAX_REGISTRO)     # con rotazione: .1, .2, .3


def _nome_per_registro(nome: str) -> str:
    return nome if _NOME.fullmatch(nome or "") else "(non valido)"


# ---------------------------------------------------------------- password e codici
def _memoria(n: int, r: int, p: int) -> int:
    return 128 * r * (n + p + 2) + 1024 * 1024


_calcoli = threading.BoundedSemaphore(CALCOLI_INSIEME)
ATTESE_MASSIME = 20                          # richieste non note che possono aspettare insieme un posto di scrypt (oltre a chi calcola)
_prenotati = 0                               # richieste non note che adesso hanno un posto in fila (vedi `posto_per_il_calcolo`)
_blocco_prenotati = threading.Lock()
_in_fila = threading.local()                 # questa richiesta (questo thread) ha già il suo posto: non si conta due volte
OCCUPATO = "Il server è molto occupato: riprova fra qualche secondo"


@contextlib.contextmanager
def posto_per_il_calcolo(esente: bool = False):
    """Un posto in fila per le richieste che faranno scrypt, preso PRIMA di contare qualunque tentativo (accesso, password attuale,
    invito, recupero): la fila ha al massimo CALCOLI_INSIEME + ATTESE_MASSIME posti; a fila piena la risposta è subito 429
    «riprova» e nessun contatore cresce (non è un tentativo). Così l'attesa non occupa tutti i thread condivisi con le altre rotte.
    `esente`: chi è noto per quel nome (dispositivo fidato o indirizzo già visto) non ha il tetto e aspetta come prima.
    Nella stessa richiesta il posto si prende una volta sola (le funzioni annidate non si contano due volte)."""
    global _prenotati
    if esente or getattr(_in_fila, "dentro", False):
        yield
        return
    with _blocco_prenotati:
        if _prenotati >= CALCOLI_INSIEME + ATTESE_MASSIME:
            raise ErroreAccount(OCCUPATO, 429, 2)
        _prenotati += 1
    _in_fila.dentro = True
    try:
        yield
    finally:
        _in_fila.dentro = False
        with _blocco_prenotati:
            _prenotati -= 1


def _scrypt(dati: bytes, sale: bytes, n: int, r: int, p: int, lunghezza: int) -> bytes:
    """scrypt, al massimo CALCOLI_INSIEME alla volta: tante richieste insieme aspettano invece di esaurire la memoria. Quante
    richieste possono aspettare lo decide prima `posto_per_il_calcolo`."""
    if not _calcoli.acquire(timeout=30):
        raise ErroreAccount(OCCUPATO, 503, 5)
    try:
        return hashlib.scrypt(dati, salt=sale, n=n, r=r, p=p, maxmem=_memoria(n, r, p), dklen=lunghezza)
    finally:
        _calcoli.release()


def normalizza_password(password: str) -> str:
    """NFKC: la stessa password scritta da un iPhone, da un Mac o da Windows dà gli stessi byte."""
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    sale = secrets.token_bytes(16)
    n, r, p = COSTO["n"], COSTO["r"], COSTO["p"]
    h = _scrypt(normalizza_password(password).encode("utf-8", "surrogatepass"), sale, n, r, p, 32)
    return f"scrypt${n}${r}${p}${base64.b64encode(sale).decode()}${base64.b64encode(h).decode()}"


def _parametri(salvato: str) -> tuple[int, int, int] | None:
    try:
        schema, n, r, p, _, _ = salvato.split("$")
        return (int(n), int(r), int(p)) if schema == "scrypt" else None
    except (ValueError, AttributeError):
        return None


def _verifica(password: str, salvato: str) -> tuple[bool, bool]:
    """(giusta, da ricalcolare). Si prova prima la forma NFKC; per le password salvate prima della normalizzazione anche quella
    scritta così com'è (formato vecchio: deve continuare a funzionare). «Da ricalcolare»: giusta ma con parametri vecchi o non
    normalizzata, quindi al primo accesso riuscito si salva di nuovo con quelli di adesso."""
    try:
        schema, n, r, p, sale, atteso = salvato.split("$")
        n, r, p = int(n), int(r), int(p)
        if schema != "scrypt" or not (1 < n <= 2 ** 20 and 0 < r <= 32 and 0 < p <= 16):
            return False, False
        sale, atteso = base64.b64decode(sale), base64.b64decode(atteso)
        normale = normalizza_password(password)
        candidati = [normale] + ([password] if password != normale else [])
        for i, c in enumerate(candidati):
            if hmac.compare_digest(_scrypt(c.encode("utf-8", "surrogatepass"), sale, n, r, p, len(atteso)), atteso):
                return True, i > 0 or (n, r, p) != (COSTO["n"], COSTO["r"], COSTO["p"])
        return False, False
    except (ValueError, TypeError):
        return False, False


def verifica_password(password: str, salvato: str) -> bool:
    return _verifica(password, salvato)[0]


def _pareggia(salvato: str) -> None:
    """Un hash salvato con parametri più leggeri di quelli di adesso si verifica più in fretta di quello fittizio dei nomi che non
    esistono: si aggiunge lavoro a vuoto con gli stessi parametri finché il tempo torna simile (da fuori non si distingue chi c'è)."""
    vecchi = _parametri(salvato)
    if not vecchi:
        return
    n, r, p = vecchi
    volte = round(COSTO["n"] * COSTO["r"] * COSTO["p"] / (n * r * p)) - 1
    for _ in range(max(0, min(volte, 7))):
        _scrypt(b"pareggio", b"0" * 16, n, r, p, 32)


_fittizio: dict[tuple, str] = {}


def _hash_fittizio() -> str:
    """Un hash che non corrisponde a nessuna password: serve a spendere lo stesso tempo anche quando il nome utente non esiste."""
    chiave = tuple(COSTO.values())
    if chiave not in _fittizio:
        _fittizio[chiave] = hash_password(secrets.token_urlsafe(16))
    return _fittizio[chiave]


def _hash_codice(codice: str) -> str:
    """SHA-256 di un codice (sono casuali e lunghi: non serve scrypt). I codici si ricopiano a mano:
    maiuscole, trattini e spazi non contano."""
    return hashlib.sha256(re.sub(r"[^A-Za-z0-9]", "", (codice or "")[:100]).upper().encode()).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest()


def nuovo_codice(lunghezza: int) -> str:
    """Un codice casuale a gruppi di 5 caratteri separati da trattino (per leggerlo e ricopiarlo). 20 caratteri = 100 bit."""
    c = "".join(secrets.choice(ALFABETO) for _ in range(lunghezza))
    return "-".join(c[i:i + 5] for i in range(0, len(c), 5))


def normalizza_nome(nome: str) -> str:
    """Il nome come si confronta: NFKC (le lettere «strane» che sembrano normali diventano normali), minuscolo, senza spazi ai lati.
    Due nomi che si scrivono uguali a occhio finiscono uguali, quindi il secondo trova il nome già preso."""
    if not isinstance(nome, str):
        return ""
    n = unicodedata.normalize("NFKC", nome[:100]).strip().casefold()
    return unicodedata.normalize("NFKC", n)


_NOME_VISTO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,31}")


def nome_da_mostrare(nome: str, normalizzato: str) -> str:
    """Il nome come l'ha scritto l'utente (senza spazi ai lati), se è lo stesso nome di `normalizzato` e usa solo i caratteri
    ammessi; se no il nome normalizzato. Accesso e unicità non guardano mai questo valore."""
    if not isinstance(nome, str):
        return normalizzato
    n = unicodedata.normalize("NFKC", nome[:100]).strip()
    return n if _NOME_VISTO.fullmatch(n) and normalizza_nome(n) == normalizzato else normalizzato


def cambia_maiuscole(db: sqlite3.Connection, utente_id: int, nome: str) -> Utente:
    """Cambia solo le maiuscole del proprio nome: le lettere devono restare le stesse (per l'accesso non cambia niente)."""
    riga = db.execute("SELECT nome_utente FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    if riga is None:
        raise ErroreAccount("Account non trovato", 404)
    nuovo = nome_da_mostrare(nome, riga["nome_utente"])
    pulito = unicodedata.normalize("NFKC", nome[:100]).strip() if isinstance(nome, str) else ""
    if nuovo != pulito:
        raise ErroreAccount("Puoi cambiare solo le maiuscole e le minuscole: le lettere devono restare le stesse")
    db.execute("UPDATE utenti SET nome_visualizzato = ? WHERE id = ?", (nuovo, utente_id))
    db.commit()
    return trova(db, utente_id)


def valida_nome(nome: str) -> str:
    n = normalizza_nome(nome)
    if not _NOME.fullmatch(n):
        raise ErroreAccount("Il nome utente deve avere da 3 a 32 caratteri: lettere senza accenti, numeri, punto, trattino o "
                            "trattino basso, e cominciare con una lettera o un numero")
    return n


def valida_password(password: str, nome_utente: str = "") -> None:
    if not isinstance(password, str) or len(normalizza_password(password)) < PASSWORD_MIN:
        raise ErroreAccount(f"La password deve avere almeno {PASSWORD_MIN} caratteri")
    password = normalizza_password(password)
    if len(password) > PASSWORD_MAX:
        raise ErroreAccount(f"La password può avere al massimo {PASSWORD_MAX} caratteri")
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs") for c in password):
        raise ErroreAccount("La password contiene caratteri invisibili o di controllo: usa solo caratteri che si vedono")
    p, nome = password.casefold(), normalizza_nome(nome_utente)
    contiene_il_nome = bool(nome) and any(x in p and len(p) < len(nome) + 6 for x in (nome, nome[::-1]))   # il nome (anche al contrario) con poco intorno
    radice = re.sub(r"^[\d\W_]+|[\d\W_]+$", "", p)                                # «Password2026!» -> «password»
    if (p in BANALI or radice in BANALI or radice in RADICI_BANALI or len(set(p)) < 4 or p.isdigit() or contiene_il_nome
            ):
        raise ErroreAccount("Password troppo banale: scegline una meno prevedibile (per esempio tre parole a caso)")


# ---------------------------------------------------------------- limiti di tentativi
def _orologio() -> float:
    return time.time()


FILE_CHIAVE_IMPRONTE = "chiave-impronte.key"
_chiavi_impronte: dict[str, bytes] = {}
_blocco_chiave = threading.Lock()


def _chiave_segreta() -> bytes:
    """La chiave delle impronte (32 byte casuali), in `dati/` accanto al database degli account, leggibile solo dal servizio.
    Nasce al primo uso. Senza questa chiave un'impronta non si può ricalcolare: con un semplice SHA-256 basterebbe provare
    i 4 miliardi di indirizzi IPv4 per risalire a quello vero."""
    file = percorsi.cartella_account() / FILE_CHIAVE_IMPRONTE
    with _blocco_chiave:
        if str(file) in _chiavi_impronte:
            return _chiavi_impronte[str(file)]
        percorsi.cartella_privata(file.parent)
        if not file.exists():
            _scrivi_chiave(file, sostituisci=False)
        chiave = file.read_bytes()
        if len(chiave) < 32:                          # vuoto o tagliato (per esempio disco pieno): una chiave debole non si usa,
            evento("chiave_impronte_ricreata")        # se ne fa una nuova (si perdono solo indirizzi noti e contatori)
            _scrivi_chiave(file, sostituisci=True)
            chiave = file.read_bytes()
            if len(chiave) < 32:
                raise ErroreAccount("Il server ha un problema con i suoi file: riprova più tardi. Se succede ancora, avvisa chi gestisce l'app.", 503)
        _chiavi_impronte[str(file)] = chiave
        return chiave


def _scrivi_chiave(file: Path, sostituisci: bool) -> None:
    """Scrittura atomica: la chiave intera va prima in un file temporaneo (600, scritto su disco), poi prende il nome giusto
    con un collegamento (`os.link`, che non sovrascrive: se un altro processo l'ha appena creata vince la sua) o, per
    `sostituisci`, con `os.replace`. Così non resta mai un file di chiave vuoto o a metà."""
    temporaneo = file.with_name(f".{file.name}.{secrets.token_hex(6)}.tmp")
    descrittore = os.open(temporaneo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descrittore, "wb") as f:
            f.write(secrets.token_bytes(32))
            f.flush()
            os.fsync(f.fileno())
        if sostituisci:
            os.replace(temporaneo, file)
        else:
            try:
                os.link(temporaneo, file)
            except FileExistsError:
                pass                                  # un altro processo l'ha appena creata: si legge la sua
    finally:
        temporaneo.unlink(missing_ok=True)


def _testo_chiave(parti) -> bytes:
    return "\x1f".join(str(p) for p in parti).encode("utf-8", "surrogatepass")


def _chiave(*parti) -> str:
    """La chiave di un contatore o di un indirizzo noto: un'impronta HMAC-SHA256 con la chiave segreta del server, così nel
    database non restano né nomi né indirizzi, e chi legge solo il database non può risalirci provando tutti i valori."""
    return hmac.new(_chiave_segreta(), _testo_chiave(parti), hashlib.sha256).hexdigest()[:40]


def _chiave_vecchia(*parti) -> str:
    """L'impronta senza chiave delle versioni fino alla 1.258: serve solo a riconoscere (e riscrivere) gli indirizzi noti salvati
    prima. Quelle righe spariscono al prossimo accesso riuscito o comunque entro 60 giorni."""
    return hashlib.sha256(_testo_chiave(parti)).hexdigest()[:40]


def _transazione(db: sqlite3.Connection) -> None:
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


class Limite:
    """Conta gli eventi recenti per chiave, nel database: i contatori restano anche dopo un riavvio del servizio."""

    CONSERVA = 2 * 24 * 3600

    @staticmethod
    def _recenti(db: sqlite3.Connection, chiave: str, finestra: float, adesso: float) -> tuple[int, float | None, float | None]:
        r = db.execute("SELECT COUNT(*), MIN(quando), MAX(quando) FROM tentativi WHERE chiave = ? AND quando > ?",
                       (chiave, adesso - finestra)).fetchone()
        return r[0], r[1], r[2]

    def troppi(self, db: sqlite3.Connection, chiave: str, massimo: int, finestra: float) -> None:
        """Alza ErroreAccount (429) se `chiave` ha già `massimo` eventi nella finestra (secondi)."""
        adesso = _orologio()
        quanti, primo, _ = self._recenti(db, chiave, finestra, adesso)
        if quanti >= massimo:
            raise ErroreAccount("Troppi tentativi: riprova più tardi", 429, max(1, math.ceil(finestra - (adesso - primo))))

    def aggiungi(self, db: sqlite3.Connection, *chiavi: str) -> None:
        adesso = _orologio()
        _transazione(db)
        db.executemany("INSERT INTO tentativi (chiave, quando) VALUES (?, ?)", [(k, adesso) for k in chiavi])
        db.execute("DELETE FROM tentativi WHERE quando < ?", (adesso - self.CONSERVA,))     # niente crescita senza fine
        db.commit()

    def consuma(self, db: sqlite3.Connection, chiave: str, massimo: int, finestra: float) -> None:
        """Controlla e poi conta questo tentativo, in una transazione sola (due richieste insieme non passano entrambe)."""
        adesso = _orologio()
        _transazione(db)
        try:
            quanti, primo, _ = self._recenti(db, chiave, finestra, adesso)
            if quanti >= massimo:
                raise ErroreAccount("Troppi tentativi: riprova più tardi", 429, max(1, math.ceil(finestra - (adesso - primo))))
            db.execute("INSERT INTO tentativi (chiave, quando) VALUES (?, ?)", (chiave, adesso))
            db.commit()
        except BaseException:
            db.rollback()
            raise

    def prenota(self, db: sqlite3.Connection, controlli: list[tuple[str, int | None, float]], crescente: str | None = None) -> list[int]:
        """Controlla TUTTI i limiti e conta questo tentativo su tutte le chiavi, in una transazione sola e PRIMA del lavoro vero
        (scrypt, confronto del codice): cento richieste insieme non passano tutte il controllo prima che una sola sia contata.
        `controlli`: (chiave, massimo o None = conta senza controllare, finestra); `crescente`: chiave con attesa crescente
        (dopo 5 errori in un'ora si aspetta 30 secondi dall'ultimo, poi il doppio a ogni errore, al massimo 15 minuti: mai per sempre).
        Restituisce le righe contate: se poi il tentativo riesce si tolgono con `annulla` (un accesso giusto non consuma limiti)."""
        adesso = _orologio()
        _transazione(db)
        try:
            for chiave, massimo, finestra in controlli:
                if massimo is not None:
                    quanti, primo, _ = self._recenti(db, chiave, finestra, adesso)
                    if quanti >= massimo:
                        raise ErroreAccount("Troppi tentativi: riprova più tardi", 429, max(1, math.ceil(finestra - (adesso - primo))))
            if crescente:
                quanti, _, ultimo = self._recenti(db, crescente, 3600, adesso)
                if quanti >= 5:
                    resta = min(900, 30 * 2 ** min(quanti - 5, 20)) - (adesso - ultimo)
                    if resta > 0:
                        raise ErroreAccount("Troppi tentativi sbagliati: aspetta prima di riprovare", 429, math.ceil(resta))
            righe = []
            for chiave in [c for c, _, _ in controlli] + ([crescente] if crescente else []):
                righe.append(db.execute("INSERT INTO tentativi (chiave, quando) VALUES (?, ?)", (chiave, adesso)).lastrowid)
            db.execute("DELETE FROM tentativi WHERE quando < ?", (adesso - self.CONSERVA,))     # niente crescita senza fine
            db.commit()
            return righe
        except BaseException:
            db.rollback()
            raise

    def annulla(self, db: sqlite3.Connection, righe: list[int], conferma: bool = True) -> None:
        """Toglie i tentativi contati da `prenota` (il tentativo è andato bene). Con `conferma=False` il commit lo fa chi chiama."""
        if righe:
            db.executemany("DELETE FROM tentativi WHERE rowid = ?", [(r,) for r in righe])
            if conferma:
                db.commit()

    def sotto(self, db: sqlite3.Connection, chiave: str, massimo: int, finestra: float) -> bool:
        """Sì se `chiave` ha meno di `massimo` eventi nella finestra (senza contare niente e senza errori)."""
        return self._recenti(db, chiave, finestra, _orologio())[0] < massimo

    def azzera(self, db: sqlite3.Connection, chiave: str | None = None, conferma: bool = True) -> None:
        if chiave is None:
            db.execute("DELETE FROM tentativi")
        else:
            db.execute("DELETE FROM tentativi WHERE chiave = ?", (chiave,))
        if conferma:
            db.commit()


limite = Limite()
ORA = 3600
QUARTO_D_ORA = 900
# Oltre questa soglia di tentativi sbagliati di tutti insieme (per tipo: accesso, recupero, iscrizione hanno ciascuno la sua)
# NON si blocca nessuno: si rallenta. Un blocco globale chiuderebbe fuori anche chi ha la password giusta.
FALLIMENTI_GLOBALI = (200, 600)          # (quanti, in quanti secondi)
RITARDO_SOTTO_ATTACCO = (1.0, 3.0)       # secondi: rallentamento oltre la soglia globale (base per ogni soglia superata, massimo)
FALLIMENTI_PER_IP = (30, QUARTO_D_ORA)
FALLIMENTI_PER_NOME = (50, ORA)          # da tutti gli indirizzi insieme: oltre, entra solo chi usa un indirizzo o un dispositivo già noti
REGISTRAZIONI_PER_IP = (10, ORA)         # tentativi di registrazione da un indirizzo che non fanno nascere un account
# Account nati da uno stesso indirizzo in un'ora. Le iscrizioni riuscite non contano fra i tentativi (sopra): la sera dell'asta
# una lega intera si iscrive dallo stesso Wi-Fi, anche con un invito a testa. Il tetto resta comunque: 20 è il numero massimo di
# squadre di una lega nell'app (limiti.MAX_SQUADRE), quindi una lega intera entra tutta; oltre non è più un gruppo di amici.
ACCOUNT_PER_IP = (20, ORA)
INVITI_SBAGLIATI_PER_IP = (5, ORA)
INVITI_SBAGLIATI_GLOBALI = (500, ORA)    # alto: gli inviti hanno 100 bit, il tetto serve solo contro le raffiche da molti indirizzi
PROVE_PER_INVITO = (10, ORA)             # con un invito valido si prova un nome dopo l'altro: tetto per invito
NOTO_PER = 60 * 24 * 3600                # un indirizzo (o un dispositivo) resta «noto» per 60 giorni dall'ultimo accesso
_DISPOSITIVO = re.compile(r"[A-Za-z0-9_-]{43}")      # secrets.token_urlsafe(32)


RALLENTATI_INSIEME = 5                   # richieste che possono aspettare insieme il rallentamento: le altre ricevono subito 429
_rallentati = threading.BoundedSemaphore(RALLENTATI_INSIEME)


def _dormi(secondi: float) -> None:
    time.sleep(secondi)


def _impronte(tipo: str, valore: str) -> tuple[str, str]:
    """L'impronta di adesso (con chiave) e quella vecchia (senza), per riconoscere anche le righe salvate prima."""
    return _chiave(tipo, valore), _chiave_vecchia(tipo, valore)


def formato_dispositivo(token) -> bool:
    return isinstance(token, str) and bool(_DISPOSITIVO.fullmatch(token))


def _noto(db: sqlite3.Connection, nome: str, impronte: tuple[str, str]) -> bool:
    return db.execute("SELECT 1 FROM indirizzi_noti n JOIN utenti u ON u.id = n.utente_id "
                      "WHERE u.nome_utente = ? AND n.indirizzo_hash IN (?, ?) AND n.ultimo > ?",
                      (nome, *impronte, _orologio() - NOTO_PER)).fetchone() is not None


def _indirizzo_noto(db: sqlite3.Connection, nome: str, ip: str | None) -> bool:
    return bool(ip) and _noto(db, nome, _impronte("indirizzo", ip))


def _dispositivo_noto(db: sqlite3.Connection, nome: str, dispositivo: str | None) -> bool:
    """Il «dispositivo fidato»: un segreto casuale che il server dà dopo un accesso riuscito (cookie HttpOnly per il web,
    campo `dispositivo` per le app). Sta nella stessa tabella degli indirizzi noti, solo come impronta."""
    return formato_dispositivo(dispositivo) and _noto(db, nome, _impronte("dispositivo", dispositivo))


def _salva_noto(db: sqlite3.Connection, utente_id: int, tipo: str, valore: str, adesso: float) -> None:
    nuova, vecchia = _impronte(tipo, valore)
    db.execute("DELETE FROM indirizzi_noti WHERE utente_id = ? AND indirizzo_hash = ?", (utente_id, vecchia))   # riga di prima: si riscrive
    db.execute("INSERT INTO indirizzi_noti (utente_id, indirizzo_hash, ultimo) VALUES (?, ?, ?) "
               "ON CONFLICT (utente_id, indirizzo_hash) DO UPDATE SET ultimo = excluded.ultimo", (utente_id, nuova, adesso))


def _segna_indirizzo(db: sqlite3.Connection, utente_id: int, ip: str | None) -> None:
    if ip:
        _salva_noto(db, utente_id, "indirizzo", ip, _orologio())


def ricorda_dispositivo(db: sqlite3.Connection, utente_id: int, attuale: str | None = None, conferma: bool = True) -> str:
    """Dopo un accesso riuscito: il segreto del dispositivo fidato. Se quello che il dispositivo ha già mandato vale per questo
    utente si tiene (e si rinnova), altrimenti se ne crea uno nuovo: un valore scelto da fuori non diventa mai fidato."""
    adesso = _orologio()
    gia = formato_dispositivo(attuale) and db.execute(
        "SELECT 1 FROM indirizzi_noti WHERE utente_id = ? AND indirizzo_hash IN (?, ?) AND ultimo > ?",
        (utente_id, *_impronte("dispositivo", attuale), adesso - NOTO_PER)).fetchone() is not None
    token = attuale if gia else secrets.token_urlsafe(32)
    db.execute("DELETE FROM indirizzi_noti WHERE utente_id = ? AND ultimo <= ?", (utente_id, adesso - NOTO_PER))
    _salva_noto(db, utente_id, "dispositivo", token, adesso)
    if conferma:
        db.commit()
    return token


def _prenota_tentativo(db: sqlite3.Connection, prefisso: str, nome: str, ip: str | None, dispositivo: str | None = None) -> list[int]:
    """Prima di provare nome e password (o un codice): controlla i limiti e conta il tentativo come sbagliato, tutto insieme e
    prima di scrypt (chi non supera un limite non spende nemmeno uno scrypt). Se poi va bene: `_riuscito` lo toglie.
    Limiti: per indirizzo, per nome da questo indirizzo (attesa crescente), per nome da tutti gli indirizzi. Il dispositivo
    fidato del titolare non è fermato dal tetto per nome né da quello per indirizzo; l'indirizzo già noto non è fermato dal tetto
    per nome. Il conteggio globale (uno per tipo) non blocca mai: oltre la soglia chi non è noto aspetta un po' (rallentamento)."""
    fidato = _dispositivo_noto(db, nome, dispositivo)
    noto = fidato or _indirizzo_noto(db, nome, ip)
    globale = _chiave(prefisso + "-fallimenti-globali")
    controlli = [(globale, None, FALLIMENTI_GLOBALI[1]),
                 (_chiave(prefisso + "-nome", nome), FALLIMENTI_PER_NOME[0] if ip and not noto else None, FALLIMENTI_PER_NOME[1])]
    if ip:
        controlli.insert(1, (_chiave("fallimenti-ip", ip), None if fidato else FALLIMENTI_PER_IP[0], FALLIMENTI_PER_IP[1]))
    try:
        righe = limite.prenota(db, controlli, crescente=_chiave(prefisso, nome, ip or "-"))
    except ErroreAccount:
        evento(prefisso + "_bloccato", nome=_nome_per_registro(nome), ip=ip)
        raise
    if not noto:
        try:
            _rallenta(db, globale)
        except ErroreAccount:
            # Respinto solo perché i posti del rallentamento sono pieni: non è un tentativo sbagliato. Si tolgono i conteggi per
            # nome, per indirizzo e dell'attesa crescente (resta solo quello globale, che misura l'attacco): chi ha la password
            # giusta, anche senza dispositivo fidato e da una rete mobile nuova, non si allunga le attese riprovando.
            limite.annulla(db, righe[1:])
            evento(prefisso + "_rallentamento_pieno", nome=_nome_per_registro(nome), ip=ip)
            raise
    return righe


def _rallenta(db: sqlite3.Connection, chiave: str) -> None:
    """Contro i tentativi distribuiti (tanti indirizzi, pochi tentativi ciascuno): oltre la soglia globale ogni tentativo da un
    indirizzo o dispositivo non noto aspetta 1 secondo per ogni soglia superata, al massimo 3. Fuori dalla transazione.
    L'attesa occupa un thread condiviso con le altre rotte: possono aspettare al massimo RALLENTATI_INSIEME richieste alla volta,
    le altre ricevono subito 429 (contato solo nel conteggio globale, vedi `_prenota_tentativo`). Chi è noto non passa di qui."""
    massimo, finestra = FALLIMENTI_GLOBALI
    quanti = limite._recenti(db, chiave, finestra, _orologio())[0]
    if quanti > massimo:
        attesa = min(RITARDO_SOTTO_ATTACCO[1], RITARDO_SOTTO_ATTACCO[0] * (quanti // massimo))
        if not _rallentati.acquire(blocking=False):
            raise ErroreAccount("Troppi tentativi in questo momento: riprova tra qualche secondo", 429, math.ceil(attesa) + 1)
        try:
            _dormi(attesa)
        finally:
            _rallentati.release()


def _riuscito(db: sqlite3.Connection, righe: list[int], prefisso: str, nome: str, ip: str | None, conferma: bool = True) -> None:
    limite.annulla(db, righe, conferma=False)
    limite.azzera(db, _chiave(prefisso, nome, ip or "-"), conferma=False)
    if conferma:
        db.commit()


def _fallimento(prefisso: str, nome: str, ip: str | None) -> None:
    """Il tentativo è già contato da `_prenota_tentativo`: qui resta solo la riga nel registro."""
    evento(prefisso + "_fallito", nome=_nome_per_registro(nome), ip=ip)


_in_corso: collections.Counter = collections.Counter()
_blocco_in_corso = threading.Lock()


@contextlib.contextmanager
def uno_alla_volta(ip: str | None):
    """Una sola richiesta pesante (scrypt) alla volta per indirizzo: chi ne manda cento insieme riceve subito 429 invece di
    occupare i calcoli di tutti (che poi risponderebbero 503 anche agli altri)."""
    if not ip:
        yield
        return
    with _blocco_in_corso:
        if _in_corso[ip]:
            raise ErroreAccount("Una richiesta alla volta: aspetta la risposta della precedente", 429, 2)
        _in_corso[ip] += 1
    try:
        yield
    finally:
        with _blocco_in_corso:
            _in_corso[ip] -= 1
            if not _in_corso[ip]:
                del _in_corso[ip]


# ---------------------------------------------------------------- utenti
def _utente(riga: sqlite3.Row | None) -> Utente | None:
    return None if riga is None else Utente(riga["id"], riga["nome_utente"], riga["ruolo"], riga["creato"],
                                            riga["nome_visualizzato"] or "")


def trova(db: sqlite3.Connection, utente_id: int) -> Utente | None:
    return _utente(db.execute("SELECT * FROM utenti WHERE id = ?", (utente_id,)).fetchone())


def elenco(db: sqlite3.Connection) -> list[dict]:
    return [dict(id=r["id"], nome_utente=r["nome_utente"], nome_visualizzato=r["nome_visualizzato"] or r["nome_utente"], ruolo=r["ruolo"], creato=r["creato"])
            for r in db.execute("SELECT * FROM utenti ORDER BY id")]


MAX_USI_INVITO = 30


def invito_vivo(inv, adesso: datetime) -> bool:
    """Un invito (riga di `inviti`) che si può ancora usare: esiste, non è revocato, ha posti e non è scaduto."""
    return inv is not None and not inv["usato"] and not inv["revocato"] and _data(inv["scade"]) > adesso


def prove_per_invito(db: sqlite3.Connection, invito) -> tuple[int, float]:
    """Il tetto di prove all'ora con questo codice: 10 più un posto per ogni persona che può entrarci, se sono più di una (un codice per dodici amici
    non si blocca all'undicesimo che entra). Un codice che non esiste ha il tetto base."""
    riga = db.execute("SELECT usi_max FROM inviti WHERE codice_hash = ?", (_hash_codice(invito if isinstance(invito, str) else ""),)).fetchone()
    return PROVE_PER_INVITO[0] + (riga[0] if riga and riga[0] > 1 else 0), PROVE_PER_INVITO[1]


def consuma_invito(db: sqlite3.Connection, codice_hash: str, utente_id: int) -> bool:
    """Usa un posto dell'invito, in modo atomico (due richieste insieme non superano `usi_max`). Falso se non c'è più posto."""
    return db.execute("UPDATE inviti SET usi = usi + 1, usato = (usi + 1 >= usi_max), usato_da = ? "
                      "WHERE codice_hash = ? AND usato = 0 AND revocato = 0", (utente_id, codice_hash)).rowcount == 1


def crea_invito(db: sqlite3.Connection, etichetta: str, amministratore: bool = False, adesso: datetime | None = None,
                usi_max: int = 1) -> str:
    """Un codice d'invito valido 7 giorni, monouso o (con `usi_max`) per più amici insieme, fino a 30. Si mostra una volta sola:
    nel database resta solo il suo hash. L'etichetta serve a ricordare per chi era (per esempio il nome dell'amico).
    Un invito da amministratore è sempre monouso."""
    if isinstance(usi_max, bool) or not isinstance(usi_max, int) or not 1 <= usi_max <= MAX_USI_INVITO:
        raise ErroreAccount(f"Gli usi dell'invito vanno da 1 a {MAX_USI_INVITO}")
    if amministratore and usi_max != 1:
        raise ErroreAccount("Un invito da amministratore si può usare una volta sola")
    etichetta = (etichetta or "").strip() if isinstance(etichetta, str) else ""
    if not etichetta or len(etichetta) > 60 or any(unicodedata.category(c) == "Cc" for c in etichetta):
        raise ErroreAccount("Serve un'etichetta di al massimo 60 caratteri (per ricordare per chi è l'invito)")
    limite.consuma(db, _chiave("crea-invito"), 30, ORA)
    adesso = _ora(adesso)
    codice = nuovo_codice(20)
    db.execute("INSERT INTO inviti (codice_hash, etichetta, ruolo, creato, scade, usi_max) VALUES (?, ?, ?, ?, ?, ?)",
               (_hash_codice(codice), etichetta, "amministratore" if amministratore else "utente", _testo(adesso),
                _testo(adesso + DURATA_INVITO), usi_max))
    db.commit()
    evento("invito_creato", ruolo="amministratore" if amministratore else "utente", usi=usi_max)
    return codice


def elenco_inviti(db: sqlite3.Connection, adesso: datetime | None = None) -> list[dict]:
    """Gli inviti, SENZA i codici (non si possono rileggere): per vedere chi ha ancora posti e per revocarli."""
    ora = _testo(_ora(adesso))
    return [dict(id=r["id"], etichetta=r["etichetta"], ruolo=r["ruolo"], creato=r["creato"], scade=r["scade"], usi=r["usi"], usi_max=r["usi_max"],
                 stato="revocato" if r["revocato"] else "finito" if r["usato"] else "scaduto" if r["scade"] <= ora else "attivo")
            for r in db.execute("SELECT * FROM inviti ORDER BY id DESC LIMIT 200")]


def revoca_invito(db: sqlite3.Connection, invito_id: int) -> None:
    """Annulla un invito: chi ha già un account lo tiene, ma il codice non vale più. Non si cancella: resta nell'elenco."""
    if db.execute("UPDATE inviti SET revocato = 1 WHERE id = ?", (invito_id,)).rowcount != 1:
        raise ErroreAccount("Invito non trovato", 404)
    db.commit()
    evento("invito_revocato", id=invito_id)


INVITO_NON_VALIDO = "Invito non valido o scaduto"


def posti_dell_invito(inv) -> int:
    """I posti ancora liberi di un invito valido per più persone (riga di `inviti`); 0 per un invito monouso o senza invito.
    I tetti per indirizzo dell'iscrizione con email hanno un posto in più per ognuno."""
    return max(0, inv["usi_max"] - inv["usi"]) if inv is not None and inv["usi_max"] > 1 else 0


def conta_per_indirizzo(db: sqlite3.Connection, ip: str | None, *tetti: tuple[str, int, float]) -> list[list]:
    """Conta questo tentativo di iscrizione nei tetti per indirizzo `tetti` ((nome, massimo, finestra)), controllandoli tutti
    nella stessa transazione (429 se uno è pieno). Restituisce le righe contate, [numero, chiave]: se l'account nasce,
    `crea_utente` le toglie. Senza indirizzo niente da contare."""
    if not ip:
        return []
    controlli = [(_chiave(nome, ip), massimo, finestra) for nome, massimo, finestra in tetti]
    return [[riga, chiave] for riga, (chiave, _, _) in zip(limite.prenota(db, controlli), controlli)]


def troppi_account(db: sqlite3.Connection, ip: str | None) -> None:
    """429 se da questo indirizzo sono già nati ACCOUNT_PER_IP account nell'ultima ora. Si guarda prima del lavoro (scrypt, codice
    usato); il controllo che vale è quello dentro la transazione di `crea_utente`."""
    if ip:
        limite.troppi(db, _chiave("account-ip", ip), *ACCOUNT_PER_IP)


def crea_utente(db: sqlite3.Connection, nome: str, nome_visualizzato: str, password_hash: str, recupero_hash: str, ruolo: str,
                adesso: datetime, *, ip: str | None = None, contate=(), email: str | None = None,
                senza_password: bool = False) -> int:
    """L'unico punto in cui nasce un account (invito, iscrizione con email, Google), dentro la transazione di chi chiama
    (BEGIN IMMEDIATE). Restituisce il numero del nuovo account.
    - Tetto degli account nati da un indirizzo (ACCOUNT_PER_IP), controllato qui: due richieste insieme non lo superano.
    - I tentativi contati per l'indirizzo in questa iscrizione (`contate`, da `conta_per_indirizzo`) si tolgono: un'iscrizione
      riuscita non consuma i tetti dei tentativi; conta invece fra gli account nati da quell'indirizzo.
    - Subito dopo la riga in `utenti` il numero riceve una cartella vuota (`contesto.libera_cartella`): se non si riesce a
      liberarla l'account non nasce (ErroreAccount 503, chi chiama annulla la transazione), perché ritroverebbe i dati di un altro."""
    troppi_account(db, ip)
    cur = db.execute("INSERT INTO utenti (nome_utente, nome_visualizzato, password_hash, recupero_hash, ruolo, creato, email, "
                     "senza_password) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (nome, nome_visualizzato, password_hash, recupero_hash, ruolo, _testo(adesso), email, int(senza_password)))
    from . import contesto                           # contesto usa questo modulo: si importa qui
    try:
        contesto.libera_cartella(cur.lastrowid, adesso)
    except OSError as e:
        evento("cartella_non_liberata", utente=cur.lastrowid, errore=type(e).__name__)
        logging.getLogger(__name__).error("Account nuovo con il numero %s non creato: la cartella che c'era già non si sposta (%s)",
                                          cur.lastrowid, type(e).__name__)
        raise ErroreAccount(percorsi.NON_VERIFICATO, 503) from None
    for riga, chiave in contate:                     # la chiave insieme al numero: mai la riga di un altro contatore
        db.execute("DELETE FROM tentativi WHERE rowid = ? AND chiave = ?", (riga, chiave))
    if ip:
        db.execute("INSERT INTO tentativi (chiave, quando) VALUES (?, ?)", (_chiave("account-ip", ip), _orologio()))
    return cur.lastrowid


def registra(db: sqlite3.Connection, nome_utente: str, password: str, invito: str, ip: str | None = None, dispositivo: str = "",
             adesso: datetime | None = None, accetto_termini: bool | None = None) -> tuple[Utente, str, str]:
    """Crea l'account (solo con un invito valido, e finché non si è al tetto di utenti) e apre la sessione.
    Restituisce (utente, token, codice di recupero): quest'ultimo si mostra una volta sola.
    Invito inesistente, scaduto o già usato: stesso messaggio. Nome già preso: lo si dice (serve a chi si iscrive), ma solo a chi
    ha un invito valido, e con un tetto di prove per invito e per indirizzo: non si possono provare i nomi in massa."""
    termini = controlla_termini(accetto_termini)
    with uno_alla_volta(ip), posto_per_il_calcolo():          # prima dei tetti: a fila piena non si conta niente
        return _registra(db, nome_utente, password, invito, ip, dispositivo, adesso, termini)


def prenota_invito(db: sqlite3.Connection, ip: str | None) -> list[int]:
    """Conta subito questo tentativo come «invito sbagliato» (per indirizzo e globale), controllando i limiti nella stessa
    transazione: con richieste insieme nessuna supera il limite. Se l'invito è buono il conteggio si toglie (`limite.annulla`)."""
    controlli = [(_chiave("inviti-sbagliati"), *INVITI_SBAGLIATI_GLOBALI)]
    if ip:
        controlli.insert(0, (_chiave("inviti-sbagliati-ip", ip), *INVITI_SBAGLIATI_PER_IP))
    return limite.prenota(db, controlli)


def _registra(db, nome_utente, password, invito, ip, dispositivo, adesso, termini=False) -> tuple[Utente, str, str]:
    adesso = _ora(adesso)
    invito = invito if isinstance(invito, str) else ""
    nome = valida_nome(nome_utente)                  # prima dei tetti: un modulo scritto male non consuma tentativi
    valida_password(password, nome)
    if ip:
        limite.troppi(db, _chiave("inviti-sbagliati-ip", ip), *INVITI_SBAGLIATI_PER_IP)
    troppi_account(db, ip)
    contate = conta_per_indirizzo(db, ip, ("registra-ip", *REGISTRAZIONI_PER_IP))     # tolto se l'account nasce
    limite.troppi(db, _chiave("inviti-sbagliati"), *INVITI_SBAGLIATI_GLOBALI)
    limite.consuma(db, _chiave("registra-invito", _hash_codice(invito)), *prove_per_invito(db, invito))
    righe = prenota_invito(db, ip)                   # contato come sbagliato finché non si vede che è buono
    password_hash = hash_password(password)          # prima di guardare invito e nome: lo stesso tempo in tutti i casi
    recupero = nuovo_codice(20)
    _transazione(db)                                 # invito, tetto e nome si controllano e si usano tutti insieme
    try:
        inv = db.execute("SELECT * FROM inviti WHERE codice_hash = ?", (_hash_codice(invito),)).fetchone()
        if not invito_vivo(inv, adesso):
            db.rollback()
            righe = []                               # resta contato
            evento("registrazione_invito_sbagliato", ip=ip)
            raise ErroreAccount(INVITO_NON_VALIDO, 403)
        if db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] >= max_utenti():
            raise ErroreAccount("Le registrazioni sono chiuse: è stato raggiunto il numero massimo di utenti", 403)
        if db.execute("SELECT 1 FROM utenti WHERE nome_utente = ?", (nome,)).fetchone():
            raise ErroreAccount("Questo nome utente è già preso: scegline un altro")
        nuovo = crea_utente(db, nome, nome_da_mostrare(nome_utente, nome), password_hash, _hash_codice(recupero), inv["ruolo"], adesso,
                            ip=ip, contate=contate)
        if not consuma_invito(db, inv["codice_hash"], nuovo):    # un altro ha appena preso l'ultimo posto
            raise ErroreAccount(INVITO_NON_VALIDO, 403)
        if termini:
            segna_termini(db, nuovo, adesso)
        _segna_indirizzo(db, nuovo, ip)
        db.commit()
    except sqlite3.IntegrityError:                   # il vincolo UNIQUE del database: un nome preso un attimo prima
        db.rollback()
        limite.annulla(db, righe)
        raise ErroreAccount("Questo nome utente è già preso: scegline un altro") from None
    except BaseException:
        if db.in_transaction:
            db.rollback()
        limite.annulla(db, righe)                    # invito buono (nome preso, tetto...): non è un invito sbagliato
        raise
    limite.annulla(db, righe)
    utente = trova(db, nuovo)
    evento("registrazione", nome=nome, ip=ip, ruolo=utente.ruolo)
    return utente, _apri_sessione(db, utente.id, dispositivo, adesso), recupero


ACCESSO_SBAGLIATO = "Nome utente o password sbagliati"


def accedi(db: sqlite3.Connection, nome_utente: str, password: str, ip: str | None = None, dispositivo: str = "",
           adesso: datetime | None = None, fidato: str | None = None) -> tuple[Utente, str]:
    """Controlla nome e password e apre una sessione. Il messaggio di errore è lo stesso sia per nome sconosciuto sia per
    password sbagliata, e l'hash si calcola comunque (stesso tempo): da fuori non si capisce quali nomi esistono.
    `fidato`: il segreto del dispositivo fidato, se il dispositivo lo manda (vedi `ricorda_dispositivo`)."""
    return accedi_ricordando(db, nome_utente, password, ip, dispositivo, adesso, fidato)[:2]


def accedi_ricordando(db: sqlite3.Connection, nome_utente: str, password: str, ip: str | None = None, dispositivo: str = "",
                      adesso: datetime | None = None, fidato: str | None = None) -> tuple[Utente, str, str]:
    """Come `accedi`, e in più restituisce il segreto del dispositivo fidato (salvato nella stessa transazione dell'accesso)."""
    with uno_alla_volta(ip), posto_per_il_calcolo(esente=_noto_per(db, nome_utente, ip, fidato)):
        return _accedi(db, nome_utente, password, ip, dispositivo, adesso, fidato)


def _noto_per(db: sqlite3.Connection, nome_utente, ip: str | None, dispositivo: str | None) -> bool:
    """Chi chiede è noto per questo nome (dispositivo fidato o indirizzo già visto)? Allora non ha il tetto della fila dei calcoli."""
    nome = normalizza_nome(nome_utente)
    return bool(nome) and (_dispositivo_noto(db, nome, dispositivo) or _indirizzo_noto(db, nome, ip))


def _accedi(db, nome_utente, password, ip, dispositivo, adesso, fidato=None) -> tuple[Utente, str, str]:
    adesso = _ora(adesso)
    nome = normalizza_nome(nome_utente)
    righe = _prenota_tentativo(db, "accesso", nome, ip, fidato)
    riga = db.execute("SELECT * FROM utenti WHERE nome_utente = ?", (nome,)).fetchone() if nome else None
    try:
        salvato = riga["password_hash"] if riga else _hash_fittizio()
        ok, da_ricalcolare = _verifica(password if isinstance(password, str) else "", salvato)
        _pareggia(salvato)
    except ErroreAccount:
        # Posti di scrypt pieni (429/503, prima di sapere se la password è giusta): non è un tentativo sbagliato. Come per il
        # rallentamento pieno si tolgono i conteggi per indirizzo, per nome e dell'attesa crescente; resta quello globale.
        limite.annulla(db, righe[1:])
        raise
    if not (riga and ok):
        _fallimento("accesso", nome, ip)
        raise ErroreAccount(ACCESSO_SBAGLIATO, 401)
    da_ricalcolare_hash = hash_password(password) if da_ricalcolare else None     # scrypt PRIMA di scrivere: mai dentro una transazione
    nuovo_dispositivo = bool(riga["email"]) and bool(ip) and not _indirizzo_noto(db, nome, ip) and not _dispositivo_noto(db, nome, fidato)
    # Tutto il lavoro di scrittura di un accesso riuscito in UNA transazione breve (prima erano cinque conferme una dopo l'altra,
    # ognuna col blocco di scrittura tenuto per tutto il tempo del disco).
    _riuscito(db, righe, "accesso", nome, ip, conferma=False)
    if da_ricalcolare_hash:                              # parametri vecchi o password salvata non normalizzata: si aggiorna ora
        db.execute("UPDATE utenti SET password_hash = ? WHERE id = ?", (da_ricalcolare_hash, riga["id"]))
    _segna_indirizzo(db, riga["id"], ip)
    segreto = ricorda_dispositivo(db, riga["id"], fidato, conferma=False)
    db.execute("DELETE FROM sessioni WHERE scade < ? OR creata < ?", (_testo(adesso), _testo(adesso - DURATA_MASSIMA)))
    db.execute("DELETE FROM reset_password WHERE scade < ?", (_testo(adesso - timedelta(days=1)),))
    db.execute("DELETE FROM codici_email WHERE scade < ?", (_testo(adesso - timedelta(days=1)),))
    utente = _utente(riga)
    token = _apri_sessione(db, utente.id, dispositivo, adesso)       # fa il commit di tutto
    if da_ricalcolare_hash:
        evento("password_ricalcolata", nome=nome)
    evento("accesso", nome=nome, ip=ip)
    if nuovo_dispositivo:                                # avviso all'email verificata: «sei stato tu?»
        from . import posta
        posta.invia(posta.modello_accesso_nuovo(riga["email"], dispositivo, posta.ora_italiana(adesso)))
    return utente, token, segreto


def _apri_sessione(db: sqlite3.Connection, utente_id: int, dispositivo: str, adesso: datetime) -> str:
    token = secrets.token_urlsafe(32)                    # 256 bit
    db.execute("INSERT INTO sessioni (utente_id, token_hash, creata, scade, ultimo_uso, dispositivo) VALUES (?, ?, ?, ?, ?, ?)",
               (utente_id, _hash_token(token), _testo(adesso), _testo(adesso + INATTIVITA), _testo(adesso),
                re.sub(r"[\x00-\x1f\x7f]", "", dispositivo or "")[:120]))
    db.commit()
    return token


def utente_da_token(db: sqlite3.Connection, token: str | None, adesso: datetime | None = None) -> Utente | None:
    """Di chi è questa sessione? None se il token non esiste, è scaduto (30 giorni senza uso o 180 in tutto) o è stato revocato."""
    if not token or not isinstance(token, str) or len(token) > 200:
        return None
    adesso = _ora(adesso)
    s = db.execute("SELECT * FROM sessioni WHERE token_hash = ?", (_hash_token(token),)).fetchone()
    if s is None or s["revocata"]:
        return None
    creata, ultimo = _data(s["creata"]), _data(s["ultimo_uso"])
    if _data(s["scade"]) <= adesso or adesso - ultimo > INATTIVITA or adesso - creata > DURATA_MASSIMA:
        return None
    if adesso - ultimo > RINNOVO_DOPO:
        db.execute("UPDATE sessioni SET ultimo_uso = ?, scade = ? WHERE id = ?",
                   (_testo(adesso), _testo(min(adesso + INATTIVITA, creata + DURATA_MASSIMA)), s["id"]))
        db.commit()
    return trova(db, s["utente_id"])


# ---------------------------------------------------------------- token del widget
# Scopo limitato: non è una sessione. Il server lo accetta SOLO per leggere /api/oggi e /api/widget (vedi rotte_account.controllo_accesso).
DURATA_TOKEN_WIDGET = timedelta(days=90)
PREFISSO_TOKEN_WIDGET = "fw_"
_FORMATO_TOKEN_WIDGET = re.compile(r"fw_[A-Za-z0-9_-]{43}")      # 32 byte casuali (256 bit) in base64 url-safe


def formato_token_widget(token) -> bool:
    return isinstance(token, str) and _FORMATO_TOKEN_WIDGET.fullmatch(token) is not None


def crea_token_widget(db: sqlite3.Connection, utente_id: int, adesso: datetime | None = None) -> tuple[str, str]:
    """Un token nuovo per il widget (il precedente, se c'era, smette di valere). Restituisce (token, scadenza): il token si vede una volta sola."""
    adesso = _ora(adesso)
    token = PREFISSO_TOKEN_WIDGET + secrets.token_urlsafe(32)
    scade = _testo(adesso + DURATA_TOKEN_WIDGET)
    db.execute("INSERT OR REPLACE INTO token_widget (utente_id, token_hash, etichetta, creato, scade, ultimo_uso) VALUES (?, ?, 'widget', ?, ?, ?)",
               (utente_id, _hash_token(token), _testo(adesso), scade, _testo(adesso)))
    db.commit()
    evento("token_widget_creato", utente=utente_id)
    return token, scade


def stato_token_widget(db: sqlite3.Connection, utente_id: int, adesso: datetime | None = None) -> dict:
    """Esiste un token del widget? Mai il token (di lui resta solo l'hash)."""
    r = db.execute("SELECT * FROM token_widget WHERE utente_id = ?", (utente_id,)).fetchone()
    if r is None:
        return {"presente": False}
    return {"presente": True, "valido": _data(r["scade"]) > _ora(adesso), "etichetta": r["etichetta"], "creato": r["creato"],
            "scade": r["scade"], "ultimo_uso": r["ultimo_uso"]}


def revoca_token_widget(db: sqlite3.Connection, utente_id: int) -> bool:
    cur = db.execute("DELETE FROM token_widget WHERE utente_id = ?", (utente_id,))
    db.commit()
    if cur.rowcount:
        evento("token_widget_revocato", utente=utente_id)
    return bool(cur.rowcount)


def utente_da_token_widget(db: sqlite3.Connection, token: str | None, adesso: datetime | None = None) -> Utente | None:
    """Di chi è questo token del widget? None se il formato non è quello, non esiste, è revocato o è scaduto."""
    if not formato_token_widget(token):
        return None
    adesso = _ora(adesso)
    r = db.execute("SELECT * FROM token_widget WHERE token_hash = ?", (_hash_token(token),)).fetchone()
    if r is None or _data(r["scade"]) <= adesso:
        return None
    if adesso - _data(r["ultimo_uso"]) > RINNOVO_DOPO:
        db.execute("UPDATE token_widget SET ultimo_uso = ? WHERE utente_id = ?", (_testo(adesso), r["utente_id"]))
        db.commit()
    return trova(db, r["utente_id"])


def esci(db: sqlite3.Connection, token: str | None) -> None:
    if token and isinstance(token, str) and len(token) <= 200:
        db.execute("UPDATE sessioni SET revocata = 1 WHERE token_hash = ?", (_hash_token(token),))
        db.commit()


def esci_da_tutti(db: sqlite3.Connection, utente_id: int, tranne: str | None = None, scollega_social: bool = False,
                  tieni_push: str | None = None) -> int:
    """Revoca tutte le sessioni dell'utente (tranne, se indicata, quella con questo token). Restituisce quante ne ha chiuse.
    Senza `tranne` (esci da tutti, cambio password, recupero) si dimenticano anche i dispositivi e gli indirizzi fidati e si
    tolgono le iscrizioni alle notifiche web, tranne quella del dispositivo che sta chiedendo (`tieni_push`, il suo indirizzo
    di notifica, se lo manda): gli altri dispositivi le riattivano dopo il nuovo accesso.
    Con `scollega_social` (il pulsante «Esci da tutti» e il recupero della password: i casi in cui si sospetta che qualcuno sia entrato)
    si scollegano anche i Google collegati: chi ci è entrato avrebbe altrimenti una porta che la nuova password non chiude.
    Un account senza password (solo Google) li tiene: sarebbe chiuso fuori."""
    if tranne:
        cur = db.execute("UPDATE sessioni SET revocata = 1 WHERE utente_id = ? AND revocata = 0 AND token_hash != ?",
                         (utente_id, _hash_token(tranne)))
    else:
        cur = db.execute("UPDATE sessioni SET revocata = 1 WHERE utente_id = ? AND revocata = 0", (utente_id,))
        db.execute("DELETE FROM token_widget WHERE utente_id = ?", (utente_id,))      # «esci da tutti» e cambio password chiudono anche il widget
        # e i dispositivi e gli indirizzi fidati: chi ha rubato un segreto di dispositivo non deve più saltare i tetti dei tentativi
        db.execute("DELETE FROM indirizzi_noti WHERE utente_id = ?", (utente_id,))
    if scollega_social:
        db.execute("DELETE FROM identita_esterne WHERE utente_id = ? AND EXISTS "
                   "(SELECT 1 FROM utenti WHERE id = ? AND senza_password = 0)", (utente_id, utente_id))
    db.commit()
    if not tranne:                       # dopo la revoca (vedi `push.iscrivi`, che ricontrolla la sessione prima di scrivere)
        _togli_notifiche(utente_id, tieni_push)
    return cur.rowcount


def _togli_notifiche(utente_id: int, tieni: str | None) -> None:
    """Le iscrizioni alle notifiche web dell'utente (nella sua cartella), tutte tranne quella con l'indirizzo `tieni` se c'è.
    Un errore di scrittura non si nasconde: arriva a chi ha chiesto (le sessioni sono già chiuse). Il file tenuto da un altro
    processo (`push.Occupato`) invece non fa fallire il cambio di password già fatto: si riprova una volta, poi le iscrizioni
    restano e lo dice una riga nel registro di sicurezza e in quello del servizio (#547)."""
    from . import contesto, push
    file = contesto.Contesto.per_utente(utente_id).iscrizioni_push
    for _ in range(2):
        try:
            push.tieni_solo(tieni if isinstance(tieni, str) else None, file)
            return
        except push.Occupato:
            continue
    logging.getLogger(__name__).error("Account %s: notifiche web dei dispositivi usciti non tolte (file occupato da un altro "
                                      "processo)", utente_id)
    evento("notifiche_non_tolte", utente=int(utente_id))


def _avvisa_password_cambiata(db: sqlite3.Connection, utente_id: int, adesso: datetime) -> None:
    """All'email verificata dell'account, se c'è: la password è cambiata, controlla l'email collegata. Con la posta spenta non
    parte niente e non c'è nessun errore (`posta.invia` non alza mai)."""
    riga = db.execute("SELECT email FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    if riga is not None and riga["email"]:
        from . import posta
        posta.invia(posta.modello_password_cambiata(riga["email"], posta.ora_italiana(adesso)))


def _controlla_password_attuale(db: sqlite3.Connection, utente_id: int, attuale: str, sessione: str | None = None) -> sqlite3.Row:
    with posto_per_il_calcolo():                     # prima del tetto: a fila piena il tentativo non si conta
        return _controlla_password(db, utente_id, attuale, sessione)


def _controlla_password(db: sqlite3.Connection, utente_id: int, attuale: str, sessione: str | None) -> sqlite3.Row:
    limite.consuma(db, _chiave("password-attuale", utente_id), 10, ORA)
    riga = db.execute("SELECT * FROM utenti WHERE id = ?", (utente_id,)).fetchone()
    if riga is not None and riga["senza_password"]:      # entrato solo con Google: al posto della password vale la riconferma recente
        from . import social
        if social.riconfermato_di_recente(db, utente_id, sessione):
            return riga
        raise ErroreAccount("Conferma prima con Google", 403, codice="serve_riconferma")
    if riga is None or not verifica_password(attuale if isinstance(attuale, str) else "", riga["password_hash"]):
        evento("password_attuale_sbagliata", nome=riga["nome_utente"] if riga else None)
        raise ErroreAccount("La password attuale non è giusta", 403)
    return riga


def conferma_password(db: sqlite3.Connection, utente_id: int, password: str, sessione: str | None = None) -> None:
    """Per le azioni che non si possono annullare (eliminare l'account): rimanda la password. Alza ErroreAccount se è sbagliata."""
    _controlla_password_attuale(db, utente_id, password, sessione)


def cambia_password(db: sqlite3.Connection, utente_id: int, attuale: str, nuova: str, token_corrente: str | None = None,
                    dispositivo: str = "", adesso: datetime | None = None, tieni_push: str | None = None) -> tuple[str, str]:
    """Cambio con la password di adesso. TUTTE le sessioni si chiudono, anche questa (chi l'avesse rubata resta fuori), e se ne
    apre una nuova al suo posto. Anche il codice di recupero cambia (quello di prima non vale più) e restano solo le notifiche
    di questo dispositivo (`tieni_push`). Restituisce (token nuovo, codice di recupero nuovo): il web
    riceve il token come cookie, le app nella risposta; il codice si mostra una volta sola."""
    adesso = _ora(adesso)
    with posto_per_il_calcolo():                     # un posto solo per i due calcoli (password attuale e nuova)
        riga = _controlla_password_attuale(db, utente_id, attuale)
        valida_password(nuova, riga["nome_utente"])
        password_hash = hash_password(nuova)
    codice = nuovo_codice(20)
    db.execute("UPDATE utenti SET password_hash = ?, recupero_hash = ? WHERE id = ?", (password_hash, _hash_codice(codice), utente_id))
    db.commit()
    esci_da_tutti(db, utente_id, tieni_push=tieni_push)
    evento("password_cambiata", nome=riga["nome_utente"])
    _avvisa_password_cambiata(db, utente_id, adesso)
    return _apri_sessione(db, utente_id, dispositivo, adesso), codice


def esci_da_tutti_i_dispositivi(db: sqlite3.Connection, utente_id: int, password: str | None = None,
                                sessione: str | None = None) -> tuple[int, str | None]:
    """Il pulsante «Esci da tutti»: chiude tutte le sessioni (anche questa), il widget, i dispositivi fidati, le notifiche web e i
    Google collegati (a chi ha una password). Con la password giusta (per chi è solo Google: la riconferma recente), come per
    «Genera un nuovo codice», cambia anche il codice di recupero e restituisce quello nuovo; senza password il codice di
    recupero resta quello di prima. Password sbagliata: 403 e non si chiude niente.
    Restituisce (sessioni chiuse, codice nuovo o None)."""
    codice = None
    if password is not None:
        _controlla_password_attuale(db, utente_id, password, sessione)
        codice = nuovo_codice(20)
        db.execute("UPDATE utenti SET recupero_hash = ? WHERE id = ?", (_hash_codice(codice), utente_id))
        db.commit()
    chiuse = esci_da_tutti(db, utente_id, scollega_social=True)
    evento("esci_da_tutti")
    return chiuse, codice


def rigenera_codice_recupero(db: sqlite3.Connection, utente_id: int, password: str, sessione: str | None = None) -> str:
    """Un nuovo codice di recupero (il vecchio smette di valere). Serve la password."""
    riga = _controlla_password_attuale(db, utente_id, password, sessione)
    codice = nuovo_codice(20)
    db.execute("UPDATE utenti SET recupero_hash = ? WHERE id = ?", (_hash_codice(codice), utente_id))
    db.commit()
    evento("codice_recupero_rigenerato", nome=riga["nome_utente"])
    return codice


def esporta(db: sqlite3.Connection, utente_id: int, mostra_tutte: bool | None = None) -> dict | None:
    """«Scarica i tuoi dati» (portabilità): i dati dell'account di QUESTO utente, in chiaro. Solo colonne scelte una per una
    (mai SELECT *): niente hash di password o codici, token, sessioni, segreti, soggetti dei servizi esterni né impronte di indirizzi.
    None se l'utente non c'è."""
    riga = db.execute("SELECT nome_utente, nome_visualizzato, email, ruolo, creato, senza_password, termini_accettati, termini_versione "
                      "FROM utenti WHERE id = ?", (int(utente_id),)).fetchone()
    if riga is None:
        return None
    collegati = [{"servizio": r["provider"], "email": r["email"] if r["email_verificata"] else None, "collegato": r["creata"]}
                 for r in db.execute("SELECT provider, email, email_verificata, creata FROM identita_esterne WHERE utente_id = ? ORDER BY id",
                                     (int(utente_id),))]
    lega = db.execute("SELECT tipo, stato, passo, demo, aggiornato FROM leghe WHERE utente_id = ?", (int(utente_id),)).fetchone()
    impostazioni: dict = {}
    if mostra_tutte is not None:
        impostazioni["mostra_tutte_le_funzioni"] = bool(mostra_tutte)
    if lega is not None:
        impostazioni["procedura_guidata"] = {"tipo": lega["tipo"], "stato": lega["stato"], "passo": lega["passo"],
                                             "demo": bool(lega["demo"]), "aggiornata": lega["aggiornato"]}
    return {
        "nome_visualizzato": riga["nome_visualizzato"] or riga["nome_utente"],
        "nome_utente": riga["nome_utente"],
        "email": riga["email"],
        "email_verificata": bool(riga["email"]),          # in `utenti.email` stanno solo indirizzi già confermati
        "creato": riga["creato"],
        "ruolo": riga["ruolo"],
        "accesso_con_password": not riga["senza_password"],
        "accessi_collegati": collegati,
        "termini": {"accettati": riga["termini_accettati"], "versione": riga["termini_versione"]},
        "impostazioni": impostazioni,
    }


def elimina(db: sqlite3.Connection, utente_id: int) -> None:
    """Toglie l'utente e, a cascata, sessioni e codici di reset. (La sua cartella di dati si cancella a parte.)
    Subito dopo lascia il segno di cancellazione (percorsi.segna_cancellato): da lì in poi nella sua cartella non si scrive più.
    Non si elimina l'ultimo amministratore: resterebbe il server senza nessuno che lo gestisca."""
    _transazione(db)                                 # il controllo e la cancellazione stanno in una transazione sola
    try:
        riga = db.execute("SELECT nome_utente, ruolo FROM utenti WHERE id = ?", (utente_id,)).fetchone()
        if riga and riga["ruolo"] == "amministratore" and db.execute(
                "SELECT COUNT(*) FROM utenti WHERE ruolo = 'amministratore'").fetchone()[0] <= 1:
            raise ErroreAccount("Non posso eliminare l'ultimo amministratore: prima promuovi un altro account")
        db.execute("DELETE FROM utenti WHERE id = ?", (utente_id,))
        db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    # il segno dopo la conferma (mai per un account che resta) e solo per un account che c'era (un numero mai usato resta libero)
    if riga and not percorsi.segna_cancellato(utente_id):
        evento("segno_cancellazione_non_riuscito", utente=int(utente_id))
    evento("account_eliminato", nome=riga["nome_utente"] if riga else None)


def imposta_ruolo(db: sqlite3.Connection, nome_utente: str, ruolo: str) -> Utente:
    """Promuove o declassa un account (`ruolo`: «amministratore» o «utente»). Non si lascia il server senza amministratori.
    Il ruolo si legge dal database a ogni richiesta: il cambio vale da subito, senza chiudere le sessioni né il token del widget.
    I dati dell'account (rose, scelte, diario, notifiche...) non si toccano."""
    if ruolo not in RUOLI:
        raise ErroreAccount("Ruolo sconosciuto: usa «admin» o «normale»")
    _transazione(db)                                 # il conteggio degli amministratori e il cambio stanno in una transazione sola
    try:
        riga = db.execute("SELECT * FROM utenti WHERE nome_utente = ?", (normalizza_nome(nome_utente),)).fetchone()
        if riga is None:
            raise ErroreAccount("Account non trovato", 404)
        if riga["ruolo"] == ruolo:
            db.rollback()
            return _utente(riga)                     # già così: niente da fare
        if riga["ruolo"] == "amministratore" and db.execute(
                "SELECT COUNT(*) FROM utenti WHERE ruolo = 'amministratore'").fetchone()[0] <= 1:
            raise ErroreAccount("Non posso declassare l'ultimo amministratore: prima promuovi un altro account")
        db.execute("UPDATE utenti SET ruolo = ? WHERE id = ?", (ruolo, riga["id"]))
        db.commit()
    except BaseException:
        if db.in_transaction:
            db.rollback()
        raise
    evento("ruolo_cambiato", nome=riga["nome_utente"], ruolo=ruolo)
    return trova(db, riga["id"])


# ---------------------------------------------------------------- password dimenticata
def crea_reset(db: sqlite3.Connection, nome_utente: str, adesso: datetime | None = None) -> str:
    """Per l'amministratore: un codice monouso di 24 ore con cui l'utente sceglie una nuova password (insieme al suo nome utente)."""
    adesso = _ora(adesso)
    limite.consuma(db, _chiave("crea-reset"), 30, ORA)
    riga = db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (normalizza_nome(nome_utente),)).fetchone()
    if riga is None:
        raise ErroreAccount("Utente non trovato", 404)
    codice = nuovo_codice(20)
    db.execute("UPDATE reset_password SET usato = 1 WHERE utente_id = ?", (riga["id"],))          # il nuovo annulla i vecchi
    db.execute("INSERT INTO reset_password (utente_id, codice_hash, creato, scade) VALUES (?, ?, ?, ?)",
               (riga["id"], _hash_codice(codice), _testo(adesso), _testo(adesso + DURATA_RESET)))
    db.commit()
    evento("reset_creato", nome=normalizza_nome(nome_utente))
    return codice


def recupera(db: sqlite3.Connection, nome_utente: str, codice: str, nuova: str, ip: str | None = None,
             adesso: datetime | None = None, fidato: str | None = None, tieni_push: str | None = None) -> str:
    """Sceglie una nuova password con il codice di recupero o con un codice di reset dell'amministratore. Tutte le sessioni
    si chiudono e restano solo le notifiche di questo dispositivo (`tieni_push`). Restituisce il NUOVO codice di recupero
    (il vecchio è usato), da mostrare una volta sola."""
    with uno_alla_volta(ip), posto_per_il_calcolo(esente=_noto_per(db, nome_utente, ip, fidato)):
        return _recupera(db, nome_utente, codice, nuova, ip, adesso, fidato, tieni_push)


def _recupera(db, nome_utente, codice, nuova, ip, adesso, fidato=None, tieni_push=None) -> str:
    adesso = _ora(adesso)
    nome = normalizza_nome(nome_utente)
    righe = _prenota_tentativo(db, "recupero", nome, ip, fidato)
    riga = db.execute("SELECT * FROM utenti WHERE nome_utente = ?", (nome,)).fetchone() if nome else None
    h = _hash_codice(codice if isinstance(codice, str) else "")
    reset = db.execute("SELECT * FROM reset_password WHERE utente_id = ? AND usato = 0 AND scade > ?",
                       (riga["id"] if riga else -1, _testo(adesso))).fetchall()
    # si confrontano sempre tutti i codici, a tempo costante
    buono_reset = [r for r in reset if hmac.compare_digest(r["codice_hash"], h)]
    buono_recupero = hmac.compare_digest(riga["recupero_hash"] if riga else _hash_codice("-"), h) and riga is not None
    if not (buono_reset or buono_recupero):
        _fallimento("recupero", nome, ip)
        raise ErroreAccount("Nome utente o codice non validi", 403)
    limite.annulla(db, righe)                        # codice giusto: il tentativo non conta come sbagliato
    valida_password(nuova, nome)
    nuovo = nuovo_codice(20)
    password_hash = hash_password(nuova)
    _transazione(db)
    if buono_reset:
        segnato = db.execute("UPDATE reset_password SET usato = 1 WHERE id = ? AND usato = 0", (buono_reset[0]["id"],))
        if segnato.rowcount != 1:                    # usato un attimo prima da un'altra richiesta
            db.rollback()
            raise ErroreAccount("Nome utente o codice non validi", 403)
        cambio = db.execute("UPDATE utenti SET password_hash = ?, recupero_hash = ?, senza_password = 0 WHERE id = ?",
                            (password_hash, _hash_codice(nuovo), riga["id"]))
    else:                                            # il codice di recupero vale una volta sola anche con richieste insieme
        cambio = db.execute("UPDATE utenti SET password_hash = ?, recupero_hash = ?, senza_password = 0 WHERE id = ? AND recupero_hash = ?",
                            (password_hash, _hash_codice(nuovo), riga["id"], h))
    if cambio.rowcount != 1:
        db.rollback()
        raise ErroreAccount("Nome utente o codice non validi", 403)
    db.commit()
    limite.azzera(db, _chiave("recupero", nome, ip or "-"))
    esci_da_tutti(db, riga["id"], scollega_social=True, tieni_push=tieni_push)
    evento("recupero", nome=nome, ip=ip, via="reset" if buono_reset else "codice_di_recupero")
    _avvisa_password_cambiata(db, riga["id"], adesso)
    return nuovo
