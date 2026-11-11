"""Limiti per utente (solo con FANTA_MULTIUTENTE=1): un utente non deve poter riempire il disco o il processore del server.

- importazioni di rose e proposte di scambi: un tetto al giorno (contatori in account.sqlite, azzerati a mezzanotte);
- spazio: i dati personali di ciascuno (regole, rose, immagini, archivio...) stanno in 5 MB;
- dimensione della lega: al massimo 20 squadre da 40 giocatori;
- calcoli e memorie condivise: calcoli in coda insieme, parte della memoria dei risultati (li applica calcolo.py), consigliate
  ricordate (consigli.py) e azioni ripetibili che costano calcoli all'ora (`azione_pesante`);
- importazione delle rose: lo stesso tetto di celle per ogni formato (lo applica importa_sicuro.py) e un tempo massimo per
  riconoscere i giocatori (`tempo_riconoscimento`, lo applica nomi.Indice);
- avvisi: prove degli avvisi all'ora (`prova_avvisi`), iscrizioni alle notifiche web all'ora (`iscrizione_push`) e un tempo massimo
  per ogni invio a un servizio di notifica (lo applica push.py).
Con l'interruttore spento (`ctx.utente_id` è None) nessuno di questi controlli fa niente: l'app resta quella di sempre. Fa eccezione
il tempo massimo di un invio, che vale sempre: un servizio di notifica normale risponde in meno di un secondo.
Ogni tetto nuovo è una costante qui sotto che si può cambiare sul server con FANTA_<nome della costante> (vedi `valore`).
I messaggi sono pensati per chi li legge: dicono cosa è successo e come rimediare.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from . import account
from .account import ErroreAccount

MAX_IMPORTAZIONI_AL_GIORNO = 10
MAX_SCAMBI_AL_GIORNO = 60           # per gli utenti normali (variabile FANTA_MAX_SCAMBI); le richieste uguali già fatte oggi non si contano
SENZA_LIMITE = 10 ** 9              # tetto dell'amministratore: di fatto nessuno
MAX_IMMAGINI_URL_AL_GIORNO = 30
PAUSA_IMMAGINI_URL = 3.0           # secondi tra un download da indirizzo web e il successivo (per utente)
MAX_BYTE_UTENTE = 5 * 1024 * 1024
MAX_SQUADRE = 20
MAX_GIOCATORI_SQUADRA = 40

# Calcoli e memorie condivise (#513): un utente non occupa più della sua parte del server.
MAX_CALCOLI_UTENTE = 4               # calcoli pesanti in coda o in corso insieme per utente (vedi calcolo.py): oltre si aspetta (202)
QUOTA_RISULTATI_UTENTE = 0.25        # parte della memoria dei risultati (calcolo.MAX_RISULTATI) che le voci di un utente possono occupare
MAX_AZIONI_PESANTI_ORA = 20          # azioni ripetibili che costano calcoli (lega di prova creata o tolta), all'ora per utente
MAX_CONSIGLIATE_UTENTE = 100         # consigliate già mostrate ricordate per utente (vedi consigli.py)

# Importazione delle rose (#514): lo stesso tetto di lavoro per ogni formato.
MAX_CELLE_IMPORTAZIONE = 1500 * 60   # celle lette in tutto (tutti i fogli di un Excel insieme): come il testo, 1500 righe × 60 colonne
MAX_SECONDI_RICONOSCIMENTO = 20      # secondi per riconoscere i giocatori di un'importazione (o di un'anteprima): oltre si ferma

# Avvisi (#515): un destinatario lento o tante prove di fila non rallentano gli altri.
MAX_SECONDI_INVIO = 20               # secondi in tutto per mandare un avviso ai dispositivi di un utente (vedi push.invia)
MAX_PROVE_AVVISI_ORA = 5             # prove degli avvisi all'ora per utente: ognuna manda davvero una notifica
MAX_ISCRIZIONI_PUSH_ORA = 10         # iscrizioni alle notifiche web all'ora per utente: ognuna controlla il nome del servizio in rete

# cosa si conta al giorno: (tetto, come si dice nel messaggio)
AL_GIORNO = {"importazioni": (MAX_IMPORTAZIONI_AL_GIORNO, "importazioni di rose"),
             "scambi": (MAX_SCAMBI_AL_GIORNO, "ricerche di scambi"),
             "immagini_url": (MAX_IMMAGINI_URL_AL_GIORNO, "immagini scaricate da un indirizzo web")}


def _adesso() -> datetime:
    return datetime.now()


def tetto(ctx, cosa: str) -> int:
    """Il massimo di oggi per `cosa`. L'amministratore non ha limiti di uso (il contatore però si aggiorna, per le statistiche):
    restano per tutti i limiti di sicurezza (tentativi di accesso, IP, dimensioni, tetti globali). Per gli utenti normali le
    ricerche di scambi si possono regolare con FANTA_MAX_SCAMBI."""
    with contextlib.closing(account.apri()) as db:
        utente = account.trova(db, ctx.utente_id)
    if utente is not None and utente.amministratore:
        return SENZA_LIMITE
    if cosa == "scambi":
        return _intero_da_ambiente("FANTA_MAX_SCAMBI", MAX_SCAMBI_AL_GIORNO)
    return AL_GIORNO[cosa][0]


def valore(nome: str) -> int | float:
    """Il tetto `nome`, una costante di questo modulo (per esempio "MAX_CALCOLI_UTENTE"): la variabile d'ambiente FANTA_<nome>
    se c'è ed è un numero maggiore di zero dello stesso tipo della costante (intero o decimale), altrimenti la costante.
    Così un tetto si cambia sul server senza toccare il codice; un valore sbagliato non lo spegne."""
    predefinito = globals()[nome]
    try:
        v = type(predefinito)(os.environ.get(f"FANTA_{nome}", "").strip())
    except ValueError:
        return predefinito
    return v if v > 0 else predefinito


def azione_pesante(ctx) -> Prenotazione | None:
    """Un'azione ripetibile che costa calcoli o scritture (creare o togliere la lega di prova): al massimo
    MAX_AZIONI_PESANTI_ORA all'ora per utente, poi 429 con Retry-After. Senza account non conta niente."""
    return prenota_ora(ctx, "azioni_pesanti", massimo=valore("MAX_AZIONI_PESANTI_ORA"))


def prova_avvisi(ctx) -> Prenotazione | None:
    """La prova degli avvisi (manda davvero una notifica a tutti i dispositivi dell'utente): al massimo MAX_PROVE_AVVISI_ORA
    all'ora per utente, poi 429 con Retry-After. Senza account non conta niente."""
    return prenota_ora(ctx, "prove_avvisi", massimo=valore("MAX_PROVE_AVVISI_ORA"))


def iscrizione_push(ctx, endpoint: str) -> Prenotazione | None:
    """L'iscrizione di un dispositivo alle notifiche web (controlla in rete il nome del servizio): al massimo
    MAX_ISCRIZIONI_PUSH_ORA all'ora per utente, poi 429 con Retry-After. La stessa iscrizione ripetuta nell'ora conta una volta
    (in memoria). Senza account non conta niente."""
    chiave = ("iscrizione-push", hashlib.sha256(endpoint.encode("utf-8", "surrogatepass")).hexdigest()) if isinstance(endpoint, str) else None
    return prenota_ora(ctx, "iscrizioni_push", chiave=chiave, massimo=valore("MAX_ISCRIZIONI_PUSH_ORA"))


def _orologio() -> float:
    return time.monotonic()


def tempo_riconoscimento(ctx) -> Callable[[], bool] | None:
    """Il controllo «tempo finito?» del riconoscimento dei giocatori di un'importazione di rose (si passa a `nomi.Indice`, che
    lo guarda a ogni nome cercato): vero dopo MAX_SECONDI_RICONOSCIMENTO secondi da adesso. Senza account None: l'app di
    sempre non ha un tempo massimo."""
    if ctx.utente_id is None:
        return None
    fine = _orologio() + valore("MAX_SECONDI_RICONOSCIMENTO")
    return lambda: _orologio() > fine


def _intero_da_ambiente(nome: str, predefinito: int) -> int:
    try:
        valore = int(os.environ.get(nome, ""))
    except ValueError:
        return predefinito
    return valore if valore > 0 else predefinito


def _durata(secondi: int) -> str:
    minuti = max(1, -(-secondi // 60))
    if minuti <= 60:
        return f"{minuti} min"
    ore = round(minuti / 60)
    return f"circa {ore} {'ora' if ore == 1 else 'ore'}"


def _troppi(cosa: str, adesso: datetime, massimo: int) -> ErroreAccount:
    nome = AL_GIORNO[cosa][1]
    domani = datetime.combine(adesso.date() + timedelta(days=1), datetime.min.time())
    secondi = max(1, int((domani - adesso).total_seconds()))
    return ErroreAccount(f"Hai raggiunto il limite di {nome} di oggi ({massimo}). Si azzera tra {_durata(secondi)}.", 429, secondi)


def controlla(ctx, cosa: str) -> None:
    """Alza ErroreAccount (429) se il tetto di oggi è già raggiunto, ma NON segna niente. Si usa prima di un lavoro che può
    rispondere «sto calcolando» (202): l'uso si segna con `conta` solo quando il risultato è pronto, altrimenti ogni
    nuovo tentativo dell'app, che riprova da sola, ne consumerebbe uno."""
    if ctx.utente_id is None:
        return
    adesso = _adesso()
    massimo = tetto(ctx, cosa)
    if usati_oggi(ctx.utente_id, cosa) >= massimo:
        raise _troppi(cosa, adesso, massimo)


_gia_contate: dict[tuple, set] = {}          # (utente, giorno, cosa) -> richieste uguali già contate oggi (in memoria: al riavvio si riparte)
_blocco_contate = threading.Lock()
MAX_RICHIESTE_RICORDATE = 500


def _gia_contata(utente_id: int, giorno: str, cosa: str, chiave) -> bool:
    """True se questa stessa richiesta (`chiave`) è già stata contata oggi per l'utente: ripeterla, anche da un altro suo
    dispositivo, rilegge il risultato in cache e non costa un'altra ricerca. Altrimenti la ricorda."""
    with _blocco_contate:
        for k in [k for k in _gia_contate if k[1] != giorno and k[2] == cosa]:           # il giorno (o l'ora) passato di QUESTA voce
            del _gia_contate[k]
        visti = _gia_contate.setdefault((utente_id, giorno, cosa), set())
        if chiave in visti:
            return True
        if len(visti) < MAX_RICHIESTE_RICORDATE:
            visti.add(chiave)
        return False


def gia_contata_oggi(ctx, cosa: str, chiave) -> bool:
    """True se questa stessa richiesta è già stata contata oggi per l'utente. Solo lettura: non segna niente. Serve per non
    bloccare con «tetto raggiunto» una ricerca identica, che rilegge il risultato in cache e non costa un'altra ricerca."""
    if ctx.utente_id is None or chiave is None:
        return False
    with _blocco_contate:
        return chiave in _gia_contate.get((ctx.utente_id, _adesso().date().isoformat(), cosa), ())


class Prenotazione:
    """Un posto già segnato nel contatore di oggi. `annulla()` lo restituisce (calcolo in corso, 202, errore)."""

    def __init__(self, utente_id: int, giorno: str, cosa: str, chiave):
        self.utente_id, self.giorno, self.cosa, self.chiave = utente_id, giorno, cosa, chiave

    def annulla(self) -> None:
        with contextlib.closing(account.apri()) as db:
            db.execute("UPDATE contatori SET n = n - 1 WHERE utente_id = ? AND giorno = ? AND cosa = ? AND n > 0",
                       (self.utente_id, self.giorno, self.cosa))
            db.commit()
        if self.chiave is not None:
            with _blocco_contate:
                _gia_contate.get((self.utente_id, self.giorno, self.cosa), set()).discard(self.chiave)


def prenota(ctx, cosa: str, chiave=None) -> Prenotazione | None:
    """Come `conta`, ma restituisce la prenotazione da annullare se il lavoro non finisce (così richieste parallele a un passo
    dal tetto non passano tutte: il posto si prende PRIMA del calcolo, in un'istruzione sola). None = niente da annullare
    (nessun account, o richiesta identica già contata oggi)."""
    if ctx.utente_id is None:
        return None
    oggi = _adesso().date().isoformat()
    if chiave is not None and _gia_contata(ctx.utente_id, oggi, cosa, chiave):
        return None
    try:
        _segna(ctx, cosa)
    except ErroreAccount:
        if chiave is not None:
            with _blocco_contate:
                _gia_contate.get((ctx.utente_id, oggi, cosa), set()).discard(chiave)
        raise
    return Prenotazione(ctx.utente_id, oggi, cosa, chiave)


def conta(ctx, cosa: str, chiave=None) -> None:
    """Segna un uso di `cosa` per l'utente di `ctx`; se ha già raggiunto il tetto di oggi alza ErroreAccount (429) con Retry-After.
    Con `chiave` (cosa si è chiesto) una richiesta identica già contata oggi non conta di nuovo."""
    if ctx.utente_id is None:
        return
    oggi = _adesso().date().isoformat()
    if chiave is not None and _gia_contata(ctx.utente_id, oggi, cosa, chiave):
        return
    try:
        _segna(ctx, cosa)
    except ErroreAccount:
        if chiave is not None:          # tetto raggiunto: la richiesta NON è pagata, quindi non va ricordata come tale
            with _blocco_contate:
                _gia_contate.get((ctx.utente_id, oggi, cosa), set()).discard(chiave)
        raise


MAX_ANTEPRIME_ALL_ORA = 30           # controlli delle rose senza salvare (/api/rose/anteprima): ogni richiesta rilegge tutto il testo


def chiave_anteprima(impronta: str) -> tuple:
    return ("anteprima", impronta)


def conta_anteprima(ctx, impronta: str) -> list[Prenotazione]:
    """L'anteprima delle rose costa come un'importazione, ma una sola volta per lo stesso contenuto: rifarla (per esempio
    dopo aver scelto i dubbi) e poi importare QUEL contenuto non conta di nuovo (vedi `conta_importazione`). In più al massimo
    `MAX_ANTEPRIME_ALL_ORA` anteprime all'ora, anche dello stesso testo (ognuna rilegge tutto).
    Restituisce i posti presi (ognuno col suo giorno o la sua ora): da annullare se il lavoro non comincia (server occupato)."""
    if ctx.utente_id is None:
        return []
    presi = [prenota_ora(ctx, "anteprime_rose", massimo=MAX_ANTEPRIME_ALL_ORA)]
    try:
        presi.append(prenota(ctx, "importazioni", chiave=chiave_anteprima(impronta)))
    except ErroreAccount:
        for p in presi:
            if p is not None:
                p.annulla()
        raise
    return [p for p in presi if p is not None]


def oggi() -> str:
    """Il giorno dei contatori. Chi conta e poi restituisce lo prende una volta e lo passa: a mezzanotte non si sbaglia giorno."""
    return _adesso().date().isoformat()


def conta_importazione(ctx, impronta: str, giorno: str | None = None) -> bool:
    """Segna un'importazione di rose nel `giorno` (di base oggi). Se quel giorno c'è già stata l'anteprima dello stesso contenuto,
    quell'importazione è già pagata: non conta, e il «buono» si consuma (importare di nuovo lo stesso testo senza un'altra
    anteprima conta come sempre). True = si è usato il buono: se poi l'importazione fallisce, `restituisci_buono` lo rimette
    (con lo stesso `giorno`)."""
    if ctx.utente_id is None:
        return False
    giorno = giorno or oggi()
    with _blocco_contate:
        visti = _gia_contate.get((ctx.utente_id, giorno, "importazioni"))
        if visti is not None and chiave_anteprima(impronta) in visti:
            visti.discard(chiave_anteprima(impronta))
            return True
    _segna(ctx, "importazioni", giorno)
    return False


def chiave_buono_restituito(impronta: str) -> tuple:
    return ("buono-restituito", impronta)


def restituisci_buono(ctx, impronta: str, una_volta: bool = True, giorno: str | None = None) -> bool:
    """L'importazione pagata dall'anteprima non è andata a buon fine (scelte non valide, rose cambiate nel frattempo...): il buono
    torna, così riprovare con lo stesso contenuto non costa un'altra importazione. Ma al massimo UNA volta al giorno per lo stesso
    contenuto: altrimenti un file che fallisce sempre si potrebbe rimandare all'infinito senza contare (ogni volta un Excel
    aperto in un processo a parte). `una_volta=False` = il lavoro non è nemmeno cominciato (server occupato): torna senza
    consumare quell'unica volta. `giorno`: quello del conteggio (non quello di adesso). True = il buono è tornato."""
    if ctx.utente_id is None:
        return False
    with _blocco_contate:
        visti = _gia_contate.setdefault((ctx.utente_id, giorno or oggi(), "importazioni"), set())
        if una_volta and chiave_buono_restituito(impronta) in visti:
            return False
        if len(visti) >= MAX_RICHIESTE_RICORDATE - 1:
            return False
        visti.add(chiave_anteprima(impronta))
        if una_volta:
            visti.add(chiave_buono_restituito(impronta))
        return True


def rimetti_importazione(ctx, giorno: str | None = None) -> None:
    """Un'importazione contata (nel `giorno` del conteggio) che non è nemmeno cominciata (server occupato a leggere un altro
    Excel): non conta."""
    if ctx.utente_id is not None:
        Prenotazione(ctx.utente_id, giorno or oggi(), "importazioni", None).annulla()


MAX_EXCEL_OCCUPATO_ALL_ORA = 30      # risposte «sto leggendo un altro Excel» gratuite all'ora per utente; poi 429


def _segna(ctx, cosa: str, giorno: str | None = None) -> None:
    massimo = tetto(ctx, cosa)
    adesso = _adesso()
    oggi = giorno or adesso.date().isoformat()
    with contextlib.closing(account.apri()) as db:
        db.execute("DELETE FROM contatori WHERE giorno < ?", (oggi,))
        # un'istruzione sola: se due richieste arrivano insieme, una sola può prendere l'ultimo posto
        cur = db.execute("INSERT INTO contatori (utente_id, giorno, cosa, n) VALUES (?, ?, ?, 1) "
                         "ON CONFLICT (utente_id, giorno, cosa) DO UPDATE SET n = n + 1 WHERE n < ?",
                         (ctx.utente_id, oggi, cosa, massimo))
        db.commit()
    if cur.rowcount != 1:
        raise _troppi(cosa, adesso, massimo)


MAX_SCHIERATE_ALL_ORA = 30           # «ho schierato...» sul diario: ogni richiesta rifà delle simulazioni


def prenota_ora(ctx, cosa: str, chiave=None, massimo: int = MAX_SCHIERATE_ALL_ORA) -> Prenotazione | None:
    """Tetto ORARIO (finestra dell'ora di orologio) nella stessa tabella dei contatori, quindi condiviso tra i processi e valido dopo un
    riavvio. Controlla e segna in un'istruzione sola (richieste parallele a un passo dal tetto non passano tutte). Una richiesta con la
    stessa `chiave` già contata in quest'ora non conta di nuovo (il 202 «sto calcolando» ripetuto vale una volta). Restituisce la
    prenotazione da `annulla()` se il lavoro fallisce subito; None = niente da annullare. 429 al raggiungimento del tetto."""
    if ctx.utente_id is None:
        return None
    adesso = _adesso()
    fascia = adesso.strftime("%Y-%m-%dT%H")
    if chiave is not None and _gia_contata(ctx.utente_id, fascia, cosa, chiave):
        return None
    with contextlib.closing(account.apri()) as db:
        db.execute("DELETE FROM contatori WHERE giorno < ?", (adesso.date().isoformat(),))
        cur = db.execute("INSERT INTO contatori (utente_id, giorno, cosa, n) VALUES (?, ?, ?, 1) "
                         "ON CONFLICT (utente_id, giorno, cosa) DO UPDATE SET n = n + 1 WHERE n < ?",
                         (ctx.utente_id, fascia, cosa, massimo))
        db.commit()
    if cur.rowcount != 1:
        if chiave is not None:
            with _blocco_contate:
                _gia_contate.get((ctx.utente_id, fascia, cosa), set()).discard(chiave)
        attesa = max(1, 3600 - adesso.minute * 60 - adesso.second)
        raise ErroreAccount(f"Hai fatto troppe richieste in quest'ora. Riprova tra {_durata(attesa)}.", 429, attesa)
    return Prenotazione(ctx.utente_id, fascia, cosa, chiave)


def usati_oggi(utente_id: int, cosa: str) -> int:
    with contextlib.closing(account.apri()) as db:
        riga = db.execute("SELECT n FROM contatori WHERE utente_id = ? AND giorno = ? AND cosa = ?",
                          (utente_id, _adesso().date().isoformat(), cosa)).fetchone()
    return riga["n"] if riga else 0


def restano(ctx, cosa: str) -> dict:
    """Quante ricerche restano oggi per `cosa`: {"restano": N, "tetto": M}. Per chi non ha limiti (amministratore, o senza account)
    tutte e due sono None: l'app allora non mostra nessun contatore. Non segna niente."""
    if ctx.utente_id is None:
        return {"restano": None, "tetto": None}
    massimo = tetto(ctx, cosa)
    if massimo >= SENZA_LIMITE:
        return {"restano": None, "tetto": None}
    return {"restano": max(0, massimo - usati_oggi(ctx.utente_id, cosa)), "tetto": massimo}


def byte_usati(cartella: Path) -> int:
    """Quanto pesano i dati personali (tutti i file nella cartella dell'utente, anche nelle sottocartelle)."""
    totale = 0
    for p in cartella.rglob("*"):
        with contextlib.suppress(OSError):
            if p.is_file():
                totale += p.stat().st_size
    return totale


_ultimo_download: dict = {}
_blocco_download = threading.Lock()
_scarichi_insieme = threading.BoundedSemaphore(3)       # in tutto il server, al massimo 3 download di immagini contemporanei


def distanzia_download(ctx) -> None:
    """Tra due download da indirizzo web dello stesso utente passano almeno `PAUSA_IMMAGINI_URL` secondi (429 con Retry-After).
    Vale anche con l'interruttore spento (chiave «locale»)."""
    chiave = ctx.utente_id if ctx.utente_id is not None else "locale"
    adesso = time.monotonic()
    with _blocco_download:
        for k in [k for k, t in _ultimo_download.items() if adesso - t > 60]:
            del _ultimo_download[k]
        resta = PAUSA_IMMAGINI_URL - (adesso - _ultimo_download.get(chiave, -1e9))
        if resta > 0:
            raise ErroreAccount("Un'immagine alla volta: aspetta qualche secondo e riprova.", 429, max(1, int(resta) + 1))
        _ultimo_download[chiave] = adesso


@contextlib.contextmanager
def download_in_corso():
    """Tetto ai download contemporanei di tutto il server: oltre, 429 invece di accodare."""
    if not _scarichi_insieme.acquire(blocking=False):
        raise ErroreAccount("Il server sta già scaricando altre immagini: riprova tra poco.", 429, 5)
    try:
        yield
    finally:
        _scarichi_insieme.release()


ANALISI_AL_MINUTO = 20              # analisi di scambi DIVERSE per utente in un minuto (ripetere la stessa non conta: l'app riprova sul 202)
ANALISI_INSIEME = 3                 # in tutto il server, al massimo 3 analisi di scambi alla volta
ANALISI_INSIEME_PER_UTENTE = 2      # e al massimo 2 per utente
_analisi_recenti: dict = {}         # utente -> {chiave: ora (monotonic)} delle analisi dell'ultimo minuto
_analisi_in_corso: dict = {}        # utente -> quante adesso
_blocco_analisi = threading.Lock()
_analisi_insieme = threading.BoundedSemaphore(ANALISI_INSIEME)


@contextlib.contextmanager
def analisi_scambio(ctx, chiave):
    """Tetto per utente al minuto (solo con gli account) e limite di analisi contemporanee (per utente e per tutto il server,
    anche senza account). Oltre: 429 con Retry-After, senza mettere in coda (la richiesta non occupa il server ad aspettare)."""
    utente = ctx.utente_id if ctx.utente_id is not None else "locale"
    adesso = time.monotonic()
    with _blocco_analisi:
        for u in [u for u, v in _analisi_recenti.items() if not v or adesso - max(v.values()) > 60]:
            del _analisi_recenti[u]
        recenti = {k: t for k, t in _analisi_recenti.get(utente, {}).items() if adesso - t < 60}
        if ctx.utente_id is not None and chiave not in recenti and len(recenti) >= ANALISI_AL_MINUTO:
            attesa = max(1, int(60 - (adesso - min(recenti.values()))) + 1)
            _analisi_recenti[utente] = recenti
            raise ErroreAccount("Hai chiesto molte analisi di scambi in poco tempo: aspetta un minuto e riprova.", 429, attesa)
        if _analisi_in_corso.get(utente, 0) >= ANALISI_INSIEME_PER_UTENTE:
            raise ErroreAccount("Sto già analizzando i tuoi scambi: aspetta la risposta e riprova.", 429, 3)
        if not _analisi_insieme.acquire(blocking=False):
            raise ErroreAccount("Il server sta analizzando altri scambi: riprova tra qualche secondo.", 429, 3)
        recenti[chiave] = adesso
        _analisi_recenti[utente] = recenti
        _analisi_in_corso[utente] = _analisi_in_corso.get(utente, 0) + 1
    try:
        yield
    finally:
        with _blocco_analisi:
            _analisi_in_corso[utente] -= 1
            if not _analisi_in_corso[utente]:
                del _analisi_in_corso[utente]
        _analisi_insieme.release()


def controlla_spazio(ctx, in_arrivo: int = 0, consiglio: str = "Prova con immagini più leggere, poi riprova.") -> None:
    """Alza ErroreAccount (413) se con `in_arrivo` byte in più i dati dell'utente supererebbero il tetto.
    `consiglio` è l'ultima frase del messaggio (per le immagini: più leggere; per altro, si cambia)."""
    if ctx.utente_id is None:
        return
    if byte_usati(ctx.cartella) + in_arrivo > MAX_BYTE_UTENTE:
        raise ErroreAccount(f"Hai finito lo spazio per i tuoi dati ({MAX_BYTE_UTENTE // (1024 * 1024)} MB). {consiglio}", 413)


def controlla_rose(ctx, rose) -> None:
    """Dopo l'importazione: non più di 20 squadre e di 40 giocatori per squadra. Alza ErroreAccount (413) prima di salvare."""
    if ctx.utente_id is None:
        return
    if len(rose.squadre) > MAX_SQUADRE:
        raise ErroreAccount(f"La lega ha {len(rose.squadre)} squadre: il massimo è {MAX_SQUADRE}. "
                            "Controlla il file: forse ci sono righe che non sono squadre.", 413)
    for s in rose.squadre:
        if len(s.giocatori) > MAX_GIOCATORI_SQUADRA:
            raise ErroreAccount(f"«{s.nome[:40]}» ha {len(s.giocatori)} giocatori: il massimo è {MAX_GIOCATORI_SQUADRA}. "
                                "Controlla il file: forse due squadre sono finite insieme.", 413)
