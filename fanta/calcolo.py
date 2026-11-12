"""Calcoli pesanti su richiesta: cache a impronta con tetto, al massimo due calcoli contemporanei, risposta «sto calcolando».

- Ogni risultato (previsioni, formazione, valori degli scambi) ha una chiave che contiene tutto ciò da cui dipende: versione dei
  dati, regole, rosa... («impronta»). Stessa chiave, stesso risultato: si riusa, anche fra utenti con le stesse regole.
- La cache ha un tetto (MAX_RISULTATI): quando è piena esce il risultato usato meno di recente (LRU), così con molti utenti
  la memoria del server non cresce senza fine. I dati del modello (`fissa=True`) restano finché non cambiano.
- Al massimo MAX_CONTEMPORANEI calcoli pesanti insieme (nello stesso processo); chi arriva dopo aspetta il suo turno. Due richieste
  per la stessa chiave non calcolano due volte: la seconda aspetta il risultato della prima.
- In modalità «in coda» (la attiva il server con gli account accesi, per ogni richiesta /api/) un calcolo che non è in cache non
  blocca la richiesta: parte in un thread a parte e la richiesta riceve InCalcolo, che il server trasforma in una risposta 202
  «sto calcolando». L'app riprova da sola e al secondo giro trova il risultato. Se il calcolo fallisce, l'errore arriva al
  primo tentativo successivo. Fuori da quella modalità (comandi, app senza account) si calcola subito, come sempre.
- Parte di ciascuno (#513; numeri in limiti.py): con gli account il server dice chi chiede (`utente_richiesta`). Un utente ha al
  massimo `limiti.MAX_CALCOLI_UTENTE` calcoli in coda o in corso (oltre, il calcolo aspetta fuori dalla coda e lui riceve InCalcolo,
  cioè 202: entra appena uno dei suoi finisce; Occupato, 429, resta solo per la coda piena di tutto il server) e le sue voci occupano al
  massimo `limiti.QUOTA_RISULTATI_UTENTE` della cache: oltre, escono prima le sue voci usate meno di recente. Una voce letta da un
  altro utente diventa di tutti (non conta più per nessuno). Senza account (`utente_richiesta` None) nessun tetto per utente.
"""
from __future__ import annotations

import contextvars
import sqlite3
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, TypeVar

from . import limiti

T = TypeVar("T")

MAX_CONTEMPORANEI = 2
MAX_RISULTATI = 256                # «unità» di cache. Misurato: una lega con regole proprie occupa 5-6 voci (circa 1,5 MB); con 64 voci ne bastavano ~12 e poi si ricalcolava di continuo
PESO_LEGGERO = 0.25                # le voci di un solo utente (formazione, mercato, proposte: ~140 kB) valgono un quarto di unità; quelle condivise per regole (previsioni, valori: 0,6-0,7 MB) una intera.
                                   # Misurato con 200 account: 3 voci a testa = 600 voci, con il tetto a 256 voci intere il 23% delle richieste a cache calda tornava a calcolare.
MAX_IN_CODA = 256                  # calcoli in attesa o in corso, in tutto: oltre, Occupato. Una voce in coda costa pochi byte: con 16, 200 utenti che aprono l'app insieme ricevevano 179 errori
RIPROVA_TRA = 3                    # secondi: ogni quanto l'app riprova mentre si calcola
RIPROVA_MAX = 10                   # con tanti calcoli in coda l'app riprova meno spesso (ogni 8 in coda, un secondo in più): meno richieste a vuoto mentre il processore lavora
RIPROVA_SENZA_CALCOLO = 60         # secondi: sola cache (il widget) e nessuno sta calcolando quel risultato: lo prepara il riscaldamento del servizio (riscaldamento.py), non fra 3 secondi
DURATA_ERRORE = 120                # secondi: quanto si ricorda un calcolo fallito (per dire l'errore a chi riprova)

in_coda: contextvars.ContextVar[bool] = contextvars.ContextVar("calcolo_in_coda", default=False)
# «solo cache»: chi chiede (il widget) può leggere i risultati già pronti ma non fa partire nessun calcolo: se manca, InCalcolo (202),
# o NonPronto (202 con un'attesa più lunga) se nessuno lo sta calcolando
solo_cache: contextvars.ContextVar[bool] = contextvars.ContextVar("calcolo_solo_cache", default=False)
# chi chiede (id dell'utente, solo con gli account): lo mette il server per ogni richiesta, il thread della coda per il suo calcolo
utente_richiesta: contextvars.ContextVar[int | None] = contextvars.ContextVar("calcolo_utente", default=None)


class InCalcolo(Exception):
    """Il risultato non è ancora pronto: sta venendo calcolato. Da trasformare in una risposta «riprova tra poco»."""

    def __init__(self, riprova_tra: int = RIPROVA_TRA):
        super().__init__("Sto calcolando: ci vuole qualche secondo")
        self.riprova_tra = riprova_tra


class NonPronto(InCalcolo):
    """Sola cache (il token del widget): il risultato non c'è e nessuno lo sta calcolando. Resta un 202 come «sto calcolando» (i
    client non cambiano), ma senza promettere qualche secondo: lo prepara il riscaldamento del servizio (#651)."""

    def __init__(self, riprova_tra: int = RIPROVA_SENZA_CALCOLO):
        Exception.__init__(self, "I dati non sono ancora pronti: il server li prepara da solo nei prossimi minuti")
        self.riprova_tra = riprova_tra


class Occupato(Exception):
    """Troppi calcoli già in coda: meglio dire «riprova fra poco» che accumulare lavoro senza fine (un utente non deve poter intasare il server)."""

    def __init__(self, riprova_tra: int = 10):
        super().__init__("Il server ha molti calcoli in coda: riprova fra qualche secondo")
        self.riprova_tra = riprova_tra


MANCA = object()             # «non c'è» per `Cache.get`: un risultato può anche valere None


class Cache:
    """Un dizionario con tetto: oltre MAX_RISULTATI esce il meno usato di recente. Sicuro fra thread.
    Per leggere usare `get(chiave, MANCA)`: «if chiave in cache: cache[chiave]» sono due passi, e fra l'uno e l'altro un altro
    thread può far uscire la voce (cache piena, o svuotata da un aggiornamento dei dati) -> KeyError.
    Ogni voce non fissa è di chi l'ha messa (`utente_richiesta` di quel momento): le voci di un utente pesano al massimo
    `limiti.QUOTA_RISULTATI_UTENTE` del tetto, oltre esce prima la sua usata meno di recente. Letta o rimessa da un altro
    utente, o rimessa senza account, la voce diventa di tutti: non conta più nella quota di nessuno."""

    def __init__(self, massimo: float = MAX_RISULTATI):
        self.massimo = massimo
        self._voci: OrderedDict = OrderedDict()
        self._fisse: set = set()
        self._pesi: dict = {}                  # chiave -> peso, solo per le voci non fisse
        self._totale = 0.0                     # somma dei pesi (pesi multipli di 0,25: la somma è esatta)
        self._padroni: dict = {}               # chiave -> utente, per le voci non fisse di un utente solo
        self._per_utente: dict = {}            # utente -> somma dei pesi delle sue voci
        self._blocco = threading.RLock()

    def __contains__(self, chiave) -> bool:
        with self._blocco:
            return chiave in self._voci

    def __getitem__(self, chiave):
        with self._blocco:
            self._voci.move_to_end(chiave)
            padrone = self._padroni.get(chiave)
            if padrone is not None and utente_richiesta.get() not in (None, padrone):
                self._di_tutti(chiave)
            return self._voci[chiave]

    def get(self, chiave, predefinito=None):
        with self._blocco:
            return self[chiave] if chiave in self._voci else predefinito

    def __setitem__(self, chiave, valore) -> None:
        self.metti(chiave, valore)

    def metti(self, chiave, valore, fissa: bool = False, peso: float = 1.0) -> None:
        """`peso`: quanto «pesa» la voce sul tetto (1 = una voce intera; vedi PESO_LEGGERO). Le fisse non contano."""
        with self._blocco:
            utente = utente_richiesta.get()
            if chiave in self._voci and self._padroni.get(chiave) != utente:
                utente = None                                   # c'era già, di un altro o di tutti: resta di tutti
            self._di_tutti(chiave)
            self._totale -= self._pesi.pop(chiave, 0.0)          # se la voce c'era già, il suo peso vecchio si toglie
            self._voci[chiave] = valore
            self._voci.move_to_end(chiave)
            if fissa:
                self._fisse.add(chiave)
            if chiave not in self._fisse:
                self._pesi[chiave] = peso
                self._totale += peso
                if utente is not None:
                    self._padroni[chiave] = utente
                    self._per_utente[utente] = self._per_utente.get(utente, 0.0) + peso
                    quota = self.massimo * limiti.valore("QUOTA_RISULTATI_UTENTE")
                    while self._per_utente.get(utente, 0.0) > quota:
                        vecchia = next((k for k in self._voci if k != chiave and self._padroni.get(k) == utente), None)
                        if vecchia is None:
                            break
                        self._togli(vecchia)
            while self._totale > self.massimo:
                vecchia = next((k for k in self._voci if k in self._pesi), None)       # la meno usata di recente tra le non fisse
                if vecchia is None:
                    break
                self._togli(vecchia)

    def _di_tutti(self, chiave) -> None:
        """La voce non è più di un utente solo: il suo peso esce dalla quota di chi l'aveva."""
        padrone = self._padroni.pop(chiave, None)
        if padrone is None:
            return
        resto = self._per_utente.get(padrone, 0.0) - self._pesi.get(chiave, 0.0)
        if resto > 0:
            self._per_utente[padrone] = resto
        else:
            self._per_utente.pop(padrone, None)

    def _togli(self, chiave) -> None:
        """Fa uscire una voce non fissa."""
        self._di_tutti(chiave)
        del self._voci[chiave]
        self._totale -= self._pesi.pop(chiave)

    def __len__(self) -> int:
        with self._blocco:
            return len(self._voci)

    def clear(self) -> None:
        with self._blocco:
            self._voci.clear()
            self._fisse.clear()
            self._pesi.clear()
            self._padroni.clear()
            self._per_utente.clear()
            self._totale = 0.0


cache = Cache()
_blocco = threading.RLock()
_permessi = threading.BoundedSemaphore(MAX_CONTEMPORANEI)
_locale = threading.local()                    # il thread che ha già un permesso non ne chiede un secondo (calcoli dentro calcoli)
_in_corso: dict = {}                           # chiave -> Event, finché un thread (con il suo permesso) la sta calcolando
_accodati: dict = {}                           # chiave -> chi l'ha chiesta (None senza account): calcoli in coda partiti e non finiti
_errori: dict = {}                             # chiave -> (quando, eccezione) dei calcoli in coda finiti male
_coda = ThreadPoolExecutor(max_workers=MAX_CONTEMPORANEI, thread_name_prefix="calcolo")


def _percorso_db(db: sqlite3.Connection) -> Path | None:
    """Il file dell'archivio a cui è collegata `db` (None se è in memoria): il thread del calcolo apre una sua connessione."""
    try:
        riga = db.execute("PRAGMA database_list").fetchone()
        return Path(riga[2]) if riga and riga[2] else None
    except sqlite3.Error:
        return None


def _con_permesso(funzione: Callable[[], T]) -> T:
    if getattr(_locale, "ha_permesso", False):         # un calcolo dentro un calcolo: il permesso c'è già (altrimenti ci si bloccherebbe da soli)
        return funzione()
    with _permessi:
        _locale.ha_permesso = True
        try:
            return funzione()
        finally:
            _locale.ha_permesso = False


def ottieni(chiave, calcola: Callable[[sqlite3.Connection], T], db: sqlite3.Connection, fissa: bool = False,
            peso: float = 1.0) -> T:
    """Il risultato di `calcola(db)` per `chiave`: dalla cache se c'è, altrimenti lo calcola (o, in coda, fa partire il calcolo e alza InCalcolo)."""
    valore = cache.get(chiave, MANCA)
    if valore is not MANCA:
        return valore
    if solo_cache.get():
        with _blocco:
            in_lavorazione = chiave in _in_corso or chiave in _accodati
        raise InCalcolo(_riprova()) if in_lavorazione else NonPronto()
    if in_coda.get():
        percorso = _percorso_db(db)
        if percorso is not None:
            return _in_coda(chiave, calcola, percorso, fissa, peso)
    return _subito(chiave, calcola, db, fissa, peso)


def _subito(chiave, calcola, db, fissa, peso=1.0):
    """Calcola qui, aspettando il proprio turno. Se un altro thread sta già calcolando la stessa chiave si aspetta il suo risultato."""
    def lavoro():
        while True:
            with _blocco:
                valore = cache.get(chiave, MANCA)
                if valore is not MANCA:
                    return valore
                attesa = _in_corso.get(chiave)
                if attesa is None:
                    _in_corso[chiave] = fine = threading.Event()
                    break
            attesa.wait()
        try:
            valore = calcola(db)
            cache.metti(chiave, valore, fissa, peso)
            return valore
        finally:
            with _blocco:
                _in_corso.pop(chiave, None)
            fine.set()
    return _con_permesso(lavoro)


def _in_coda(chiave, calcola, percorso: Path, fissa, peso=1.0):
    with _blocco:
        valore = cache.get(chiave, MANCA)
        if valore is not MANCA:
            return valore
        errore = _errori.pop(chiave, None)
        if errore and time.monotonic() - errore[0] < DURATA_ERRORE:
            raise errore[1]
        if chiave not in _accodati:
            if len(_accodati) >= MAX_IN_CODA:
                raise Occupato()
            utente = utente_richiesta.get()
            # Tetto per utente: oltre, il calcolo NON entra in coda ma la risposta resta «sto calcolando» (202): l'app riprova da
            # sola e il calcolo entra appena uno dei suoi finisce (nell'uso normale succede: Formazione più quattro avversarie).
            # Una richiesta uguale a un calcolo già in coda (anche di un altro) non è un calcolo nuovo: il tetto vale solo qui.
            if utente is not None and sum(1 for u in _accodati.values() if u == utente) >= limiti.valore("MAX_CALCOLI_UTENTE"):
                raise InCalcolo(_riprova())
            _accodati[chiave] = utente
            _coda.submit(_lavoro, chiave, calcola, percorso, fissa, peso, utente)
        riprova = _riprova()
    raise InCalcolo(riprova)


def _riprova() -> int:
    """Fra quanti secondi l'app riprova: con tanti calcoli in coda, meno spesso (ogni 8 in coda un secondo in più)."""
    return min(RIPROVA_MAX, RIPROVA_TRA + len(_accodati) // 8)


def _lavoro(chiave, calcola, percorso: Path, fissa, peso=1.0, utente=None) -> None:
    from . import archivio
    gettone = utente_richiesta.set(utente)              # le voci che questo calcolo mette in cache sono di chi l'ha chiesto
    try:
        db = archivio.apri(percorso)
        try:
            _subito(chiave, calcola, db, fissa, peso)
        finally:
            db.close()
    except BaseException as e:  # noqa: BLE001 - l'errore va a chi riprova, non deve restare nel thread
        with _blocco:
            _errori[chiave] = (time.monotonic(), e)
            for k in [k for k, (t, _) in _errori.items() if time.monotonic() - t > DURATA_ERRORE]:
                _errori.pop(k, None)
    finally:
        utente_richiesta.reset(gettone)
        with _blocco:
            _accodati.pop(chiave, None)


def in_corso() -> int:
    """Quanti calcoli sono in corso o in attesa adesso (per la diagnosi e per i test)."""
    with _blocco:
        return len(set(_in_corso) | set(_accodati))
