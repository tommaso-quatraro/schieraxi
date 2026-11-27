"""Gli avvisi di ogni utente (solo con FANTA_MULTIUTENTE=1). Solo due (#676): il cambio della formazione da schierare (giro
`cambi`, e nell'ultima ora l'avviso «cambia la formazione» del giro `promemoria`) e il promemoria prima della scadenza.
Riepilogo della giornata, reparto scoperto e «formazione pronta» non partono più.

Con l'interruttore spento gli avvisi sono quelli di sempre (un solo utente, file globali, ntfy): non passano di qui.
Con l'interruttore acceso i comandi `cambi` e `promemoria` (che il server lancia da cron) chiamano `esegui`, che passa uno per
uno gli utenti *attivi* (con una squadra indicata e almeno un dispositivo iscritto alle notifiche web: è l'interruttore unico
«Avvisi su questo dispositivo») e per ciascuno usa i SUOI file: rose, regole, impostazioni, scelte, iscrizioni e «cosa ho già
avvisato». Delle impostazioni contano le ore tranquille, la lingua e `app_nativa`; le scelte per avviso di prima no.
- Il canale ntfy è uno solo ed è del proprietario del server: gli utenti non ci passano mai. L'unica eccezione è un
  amministratore che ha acceso l'opzione dell'app nativa (come con l'interruttore spento).
- Un errore con un utente non ferma gli altri, e non resta muto: una riga nel registro (numero dell'utente e tipo d'errore) e
  l'errore nel ritorno di `esegui`, che il comando stampa. Lo stesso per un pezzo di un avviso che non riesce mentre il resto
  parte (`notifiche.segna_guasto`).
- Due giri insieme (i promemoria dal cron e i cambi del pianificatore dentro il servizio) non lavorano mai sullo stesso utente:
  «leggi lo stato, decidi, manda, scrivi» di un utente sta dentro un blocco su file fra processi (`blocco_avvisi`, #660).
- Il giro ha un tempo massimo e un ordine a rotazione: chi resta fuori per il tempo finito passa per primo al giro dopo.
- Lavoro pesante: i cambi confrontano prima gli stati dei giocatori (poco costoso) e ricalcolano la formazione solo se qualcosa è cambiato.
- Il giro dei promemoria lo fa il servizio (`sorveglia_promemoria`), con i calcoli che ha già in memoria: il comando `promemoria`
  del cron lo rifà solo se il servizio salta il turno in corso (servizio fermo, giro bloccato o in errore), come prima
  (`promemoria_dal_cron`).
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from . import account, lega, notifiche, percorsi, push, regole
from .account import Utente
from .blocco import BloccoFile
from .contesto import Contesto
from .lega import Rose
from .percorsi import scrivi_sicuro

FUNZIONI = ("cambi", "promemoria")
LOG = logging.getLogger(__name__)
FILE_BLOCCO = "avvisi.lock"    # accanto agli stati degli avvisi dell'utente
# secondi: il lavoro di un utente dura di solito pochi secondi (un calcolo e un invio, al massimo `limiti.MAX_SECONDI_INVIO`).
# Si aspetta un po' invece di saltarlo subito, così il promemoria di un quarto d'ora prima non va perso per un incrocio di un attimo;
# oltre, l'utente passa al giro dopo. Resta dentro MARGINE_SECONDI, il margine del giro per il lavoro di un utente.
ATTESA_BLOCCO = 30.0


@dataclass
class Attivo:
    utente: Utente
    ctx: Contesto
    rose: Rose
    opzioni: dict
    ntfy: bool
    guasti: list[str] = field(default_factory=list)      # i pezzi non riusciti nel lavoro di questo giro (`notifiche.segna_guasto`)

    @property
    def manda(self) -> Callable[..., bool]:
        return notifiche.manda_di(self.ctx.impostazioni_avvisi, self.ctx.iscrizioni_push, self.ntfy)


def ntfy_consentito(utente: Utente, opzioni: dict) -> bool:
    """Il canale ntfy è del proprietario del server: solo un amministratore, e solo se ha acceso l'opzione dell'app nativa."""
    return utente.amministratore and bool(opzioni.get("app_nativa"))


def blocco_avvisi(ctx: Contesto) -> BloccoFile:
    """Il blocco fra processi degli avvisi di un utente: lo tiene chi legge, decide, manda e scrive i suoi stati (cambi e
    promemoria insieme: tutti e due leggono e scrivono tutti e due i file). La cartella non si crea: quella di un account eliminato
    non rinasce per il file del blocco (FileNotFoundError). Occupato oltre ATTESA_BLOCCO secondi: TimeoutError."""
    return BloccoFile(ctx.stato_promemoria.with_name(FILE_BLOCCO), ATTESA_BLOCCO, crea_cartella=False)


def _attivo(utente: Utente) -> Attivo | None:
    """L'utente pronto per il giro, o None se non ha una squadra o un modo per ricevere gli avvisi."""
    ctx = Contesto.per_utente(utente.id)
    rose = lega.carica(ctx.rose)
    if not rose or not rose.mia_squadra:
        return None
    opzioni = notifiche.impostazioni(ctx.impostazioni_avvisi)
    ntfy = ntfy_consentito(utente, opzioni)
    if push.iscrizioni(ctx.iscrizioni_push) or (ntfy and notifiche.canale()):
        return Attivo(utente, ctx, rose, opzioni, ntfy)
    return None


def utenti_attivi() -> list[Attivo]:
    """Chi ha una squadra e almeno un modo per ricevere gli avvisi. Un utente con un file rovinato o strano per ora non riceve
    avvisi, e non ferma gli altri. Un account bloccato da chi gestisce il server non riceve niente."""
    with contextlib.closing(account.apri()) as db:
        elenco = [account.trova(db, r["id"]) for r in account.elenco(db) if not r["bloccato"]]
    attivi = []
    for utente in elenco:
        try:
            a = _attivo(utente)
        except Exception as e:  # noqa: BLE001 - un utente con dati strani non deve fermare gli avvisi degli altri
            LOG.warning("Avvisi: utente %s saltato in questo giro (%s)", utente.id, type(e).__name__)      # niente nomi né contenuti
            continue
        if a is not None:
            attivi.append(a)
    return attivi


def _cambi(a: Attivo, db: sqlite3.Connection, r: regole.Regole, adesso: datetime) -> list[str]:
    """La formazione da schierare è cambiata per un titolare che non gioca più (`notifiche.cambi`), qualunque fosse la vecchia
    scelta `cambi` dell'utente."""
    return notifiche.cambi(db, r, a.rose, adesso, a.ctx.stato_cambi, a.manda, a.opzioni, risparmia=True, file_scelte=a.ctx.scelte,
                           file_promemoria=a.ctx.stato_promemoria, guasti=a.guasti)


def _promemoria(a: Attivo, db: sqlite3.Connection, r: regole.Regole, adesso: datetime) -> list[str]:
    """Prima l'avviso «cambia la formazione» (nell'ultima ora): se parte, il promemoria non fa il doppione. Poi il promemoria.
    Per tutti, qualunque fossero le vecchie scelte `avviso_prima`, `promemoria_60` e `promemoria_15`. Se l'avviso alza un errore
    il promemoria parte lo stesso e il guasto va in `a.guasti`."""
    try:
        righe = notifiche.avviso_scadenza(db, r, a.rose, adesso, a.ctx.stato_promemoria, a.manda, a.opzioni, a.ctx.scelte,
                                          a.ctx.stato_cambi)
    except Exception as e:                         # noqa: BLE001  (i promemoria partono comunque; il guasto si vede)
        righe = []
        notifiche.segna_guasto(a.guasti, "avviso «cambia la formazione» non controllato", e)
    return righe + notifiche.promemoria(db, r, a.rose, adesso, a.ctx.stato_promemoria, a.manda, a.opzioni, a.ctx.scelte,
                                        guasti=a.guasti, file_cambi=a.ctx.stato_cambi)


_LAVORI = {"cambi": _cambi, "promemoria": _promemoria}

# ---------------------------------------------------------------- tempo e ordine del giro
# Gli script del server fermano il comando dopo un tempo massimo (promemoria.sh, aggiorna.sh; le stesse variabili di
# dati/ambiente.env). Il giro si ferma da solo un po' prima, fra un utente e l'altro, così salva l'ordine e non viene interrotto.
TEMPO_SCRIPT = {"promemoria": ("FANTA_MAX_SECONDI_GIRO_PROMEMORIA", 480)}
TEMPO_SCRIPT_ALTRI = ("FANTA_MAX_SECONDI_GIRO_AVVISI", 600)        # cambi
MARGINE_SECONDI = 120          # il lavoro di un utente può durare un po' (due invii lenti e un calcolo): resta questo margine
FILE_GIRO = "avvisi-giro.json"  # nella cartella degli account: per ogni giro, l'ordine in cui gli utenti sono stati serviti
ATTESA_GIRO = 5.0              # secondi: leggere e riscrivere FILE_GIRO dura millisecondi; oltre, per questo giro l'ordine non si salva


def secondi_del_giro(funzione: str) -> float:
    """Quanto può durare il giro di `funzione`: il tempo massimo dello script del server meno un margine (almeno la metà)."""
    variabile, base = TEMPO_SCRIPT.get(funzione, TEMPO_SCRIPT_ALTRI)
    testo = os.environ.get(variabile, "")
    esterno = int(testo) if re.fullmatch(r"[1-9][0-9]{0,4}", testo) else base       # come gli script: un valore non valido vale quello di base
    return max(esterno - MARGINE_SECONDI, esterno / 2)


def _leggi_giro(file: Path, funzione: str) -> dict[str, int]:
    """{numero dell'utente: posizione nell'ultimo servizio} del giro `funzione` (più alta = servito più di recente)."""
    try:
        voce = json.loads(file.read_text(encoding="utf-8")).get(funzione)
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(voce, dict):
        return {}
    return {k: v for k, v in voce.items() if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool)}


def _scrivi_giro(file: Path, funzione: str, serviti: dict[str, int]) -> bool:
    """Salva l'ordine del giro `funzione` lasciando com'è quello degli altri giri. Falso se non si riesce (disco pieno, permessi,
    file tenuto da un altro giro oltre ATTESA_GIRO secondi): lo dice il registro, con il solo tipo d'errore, e gli avvisi partono
    lo stesso. Il file è uno per tutti i giri, che possono girare insieme in processi diversi: leggere e riscrivere sta dentro un
    blocco su file (`<file>.lock`), così nessuno cancella l'ordine scritto dall'altro."""
    try:
        with BloccoFile(file.with_name(file.name + ".lock"), ATTESA_GIRO):
            try:
                tutto = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                tutto = {}
            tutto = (tutto if isinstance(tutto, dict) else {}) | {funzione: serviti}
            scrivi_sicuro(file, json.dumps(tutto))
    except OSError as e:                              # anche TimeoutError (blocco occupato), che è un OSError
        LOG.warning("Avvisi (%s): ordine del giro non salvato (%s), si continua senza", funzione, type(e).__name__)
        return False
    return True


def esegui(funzione: str, db: sqlite3.Connection, adesso: datetime | None = None,
           attivi: list[Attivo] | None = None, *, max_secondi: float | None = None,
           orologio: Callable[[], float] = time.monotonic, file_giro: Path | None = None,
           fermo: threading.Event | None = None) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Esegue `funzione` (una di FUNZIONI) per ogni utente attivo. Restituisce ({nome utente: righe mandate}, {nome utente: errore}).
    Dell'errore si dice solo il tipo (niente dati personali nei log). Un utente può stare in tutti e due: un pezzo dei suoi avvisi
    non è riuscito e il resto è partito. Ogni utente in errore lascia anche una riga nel registro, con il suo numero.
    Il lavoro di un utente sta dentro il suo blocco fra processi (`blocco_avvisi`): se un altro giro lo tiene oltre ATTESA_BLOCCO
    secondi, l'utente passa al giro dopo (una riga nel registro, nessun errore) senza segnarsi come servito.
    `adesso`: un'ora fissa per tutto il giro (le prove). Senza, l'ora di ogni utente si prende DOPO aver preso il suo blocco: un
    altro giro, partito dopo questo ma arrivato prima, può aver appena scritto nei suoi stati un avviso con un'ora più recente della
    partenza di questo; con l'ora della partenza quell'avviso sembrerebbe «nel futuro», non recente, e ne partirebbe un altro.
    Il giro dura al massimo `max_secondi` (di base `secondi_del_giro`): il tempo si guarda fra un utente e l'altro (almeno uno si
    serve sempre); chi resta passa al giro dopo. L'ordine è a rotazione: prima chi è stato servito meno di recente (o mai), in fondo
    chi è stato servito per ultimo. Ogni utente si segna come servito PRIMA del suo lavoro, così se il giro si ferma mentre lavora
    per lui, al giro dopo va in fondo. L'ordine sta in `file_giro` (di base FILE_GIRO nella cartella degli account; con `attivi`
    indicato da chi chiama, solo se si passa `file_giro`).
    `fermo` (il giro del servizio): quando il servizio si chiude, il giro finisce il lavoro dell'utente a cui è arrivato (invio e
    stato «mandato») e non comincia quello degli altri, che passano al giro dopo (del servizio nuovo o del cron)."""
    lavoro = _LAVORI[funzione]
    inizio = orologio()
    limite = secondi_del_giro(funzione) if max_secondi is None else max_secondi
    if attivi is None:
        attivi = utenti_attivi()
        file_giro = file_giro or percorsi.cartella_account() / FILE_GIRO
    serviti: dict[str, int] = {}
    ordinati = list(attivi)
    if file_giro:
        presenti = {str(a.utente.id) for a in attivi}
        serviti = {k: v for k, v in _leggi_giro(file_giro, funzione).items() if k in presenti}
        ordinati.sort(key=lambda a: serviti.get(str(a.utente.id), -1))      # sort è stabile: a pari merito, l'ordine di prima
    posizione = max(serviti.values(), default=0)
    esiti: dict[str, list[str]] = {}
    errori: dict[str, str] = {}
    for n, a in enumerate(ordinati):
        if fermo is not None and fermo.is_set():
            LOG.warning("Avvisi (%s): servizio in chiusura, %d utenti al prossimo giro", funzione, len(ordinati) - n)
            break
        if n and orologio() - inizio > limite:
            LOG.warning("Avvisi (%s): tempo del giro finito, %d utenti al prossimo giro", funzione, len(ordinati) - n)
            break
        with contextlib.ExitStack() as pila:
            try:
                pila.enter_context(blocco_avvisi(a.ctx))
            except OSError as e:                      # TimeoutError: un altro giro lavora per lui; o la cartella non c'è più
                LOG.warning("Avvisi (%s): utente %s al prossimo giro, blocco dei suoi avvisi non preso (%s)", funzione,
                            a.utente.id, type(e).__name__)
                continue
            if file_giro:
                posizione += 1
                serviti[str(a.utente.id)] = posizione
                if not _scrivi_giro(file_giro, funzione, serviti):
                    file_giro = None                  # una riga sola nel registro: per questo giro non si riprova
            a.guasti = []
            try:
                esiti[a.utente.nome_utente] = lavoro(a, db, regole.carica(a.ctx.regole), adesso or datetime.now())   # dopo il blocco
            except Exception as e:  # noqa: BLE001 - un utente con dati strani non deve fermare gli avvisi degli altri
                a.guasti.append(type(e).__name__)
        if a.guasti:
            errori[a.utente.nome_utente] = "; ".join(a.guasti)
            LOG.warning("Avvisi (%s): utente %s in errore: %s", funzione, a.utente.id, errori[a.utente.nome_utente])
    return esiti, errori


# ---------------------------------------------------------------- promemoria dentro il servizio
# Il giro dei promemoria (cron `script/server/promemoria.sh`, ogni 10 minuti) caricava il modello in un processo a parte e rifaceva
# previsioni e formazione di ogni utente proprio mentre il servizio, nell'ora prima della scadenza, rifà le stesse cose (giri delle
# probabili a 60, 30 e 15 minuti, pianificatore.py). Con gli account lo fa il servizio, negli stessi minuti tondi del cron, con i
# calcoli che ha già in memoria (riscaldamento.py). Dopo ogni giro riuscito segna in FILE_SEGNO l'ora in cui l'ha cominciato.
# Il comando `promemoria` del cron (`promemoria_dal_cron`) non rifà il giro se il segno è del turno in corso: un segno più vecchio
# vuol dire che il servizio quel turno non l'ha fatto, o non ancora. Il cron e il servizio partono insieme al minuto tondo e il
# segno arriva alla fine del giro: se il segno è del turno prima il cron aspetta, fino a ATTESA_CRON secondi dopo il minuto tondo.
# Servizio fermo, giro bloccato o in errore: niente segno del turno, e il giro lo fa il cron già in quel turno, così ogni finestra
# dei promemoria (larga almeno 16 minuti, notifiche.FINESTRE) ha sempre un giro. Una soglia sull'età del segno (15 minuti, fino
# alla 1.611) lasciava un turno senza nessuno quando il servizio si fermava subito dopo un giro: scadenza alle 20:43, giri alle 20:20
# e alle 20:40, a 3 minuti, fuori dal «quarto d'ora prima». Due giri insieme non mandano doppioni: blocco per utente e stato di
# «cosa ho già mandato» (`blocco_avvisi`). Alla chiusura il servizio aspetta la fine del lavoro dell'utente in corso
# (server._ciclo, `fermo` in `esegui`). FANTA_PIANIFICATORE=0 (come nell'ambiente di prova) spegne anche questo giro.
FILE_SEGNO = "promemoria-servizio.json"    # nella cartella degli account: {"giro": inizio dell'ultimo giro riuscito del servizio}
OGNI_MINUTI = 10                           # come il cron (*/10): stessi orari, quindi stesse finestre dei promemoria
# secondi dopo il minuto tondo: il servizio comincia il giro mezzo secondo dopo e di solito lo finisce in pochi secondi; un giro in
# errore si riprova al minuto dopo. Il ritardo del cron quando subentra non fa uscire nessuno dalle finestre dei promemoria.
ATTESA_CRON = 90.0
PASSO_CRON = 5.0                           # secondi: mentre aspetta, il cron riguarda il segno ed esce appena il servizio ha finito
ATTESA_MASSIMA = 60.0                      # secondi: l'ora si riguarda almeno ogni minuto (cambio dell'ora legale, sospensioni)


def promemoria_nel_servizio() -> bool:
    """Il servizio fa il giro dei promemoria? Con gli account e con il pianificatore acceso (`FANTA_PIANIFICATORE=0` lo spegne)."""
    from . import pianificatore
    return account.multiutente() and pianificatore.acceso()


def _file_segno(file: Path | None) -> Path:
    return file or percorsi.cartella_account() / FILE_SEGNO       # letto a ogni chiamata: le prove spostano la cartella


def _ora_del_segno(file: Path | None) -> datetime | None:
    """L'ora dell'ultimo giro riuscito del servizio, o None se il segno non c'è o non si legge (vale come nessun segno)."""
    try:
        ora = datetime.fromisoformat(json.loads(_file_segno(file).read_text(encoding="utf-8"))["giro"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    return ora if ora.tzinfo is None else None      # il servizio scrive l'ora senza fuso, come `adesso`


def promemoria_dal_cron(adesso: Callable[[], datetime] | None = None, file: Path | None = None,
                        dormi: Callable[[float], None] | None = None) -> tuple[bool, str]:
    """(il comando `promemoria` del cron fa il giro?, riga per il registro del cron o ""). No se il servizio ha già fatto il giro
    di questo turno di OGNI_MINUTI minuti. Segno del turno prima: il servizio sta forse facendo il giro di adesso (lo scrive solo
    alla fine), e il cron lo aspetta fino a ATTESA_CRON secondi dopo il minuto tondo, riguardando il segno ogni PASSO_CRON secondi;
    se non arriva il servizio ha saltato il turno: sì, con una riga. Segno più vecchio (saltato anche il turno prima): sì, subito,
    con una riga. Sì, senza dire niente, se il segno non c'è (servizio senza promemoria, spento apposta, o nessun giro riuscito) o
    è «nel futuro» (l'ora legale è tornata indietro). `adesso` e `dormi`: l'orologio e l'attesa (le prove li fingono)."""
    adesso, dormi = adesso or datetime.now, dormi or time.sleep
    ora, segno = adesso(), _ora_del_segno(file)
    if segno is None or segno > ora:
        return True, ""
    turno = _turno(ora)
    if segno >= turno:
        return False, ""
    if segno >= turno - timedelta(minutes=OGNI_MINUTI):
        resta = (turno - ora).total_seconds() + ATTESA_CRON      # contato con le attese, non con l'ora: regge un cambio d'ora
        while resta > 0:
            dormi(min(PASSO_CRON, resta))
            resta -= PASSO_CRON
            nuovo = _ora_del_segno(file)
            if nuovo is not None and nuovo >= turno:
                return False, ""
    minuti = int((adesso() - segno).total_seconds() // 60)
    return True, f"promemoria: il servizio non fa il giro da {minuti} minuti, lo fa il cron"


def _turno(adesso: datetime) -> datetime:
    """L'inizio del turno di OGNI_MINUTI minuti (20:37 -> 20:30)."""
    return adesso.replace(minute=adesso.minute - adesso.minute % OGNI_MINUTI, second=0, microsecond=0)


def _attesa(adesso: datetime) -> float:
    """Secondi fino a mezzo secondo dopo l'inizio del turno dopo, al massimo ATTESA_MASSIMA."""
    dopo = _turno(adesso) + timedelta(minutes=OGNI_MINUTI)
    return min((dopo - adesso).total_seconds() + 0.5, ATTESA_MASSIMA)


def _giro_promemoria(db: sqlite3.Connection, fermo: threading.Event) -> tuple[dict[str, list[str]], dict[str, str]]:
    # senza `adesso`: l'ora di ogni utente si prende dopo il suo blocco (vedi `esegui`); `fermo`: alla chiusura si ferma fra due utenti
    return esegui("promemoria", db, fermo=fermo)


def sorveglia_promemoria(fermo: threading.Event, apri_db: Callable[[], sqlite3.Connection],
                         adesso: Callable[[], datetime] = datetime.now, file: Path | None = None,
                         giro: Callable[[sqlite3.Connection, threading.Event], tuple] = _giro_promemoria,
                         ritardo: float = 5.0) -> None:
    """Il thread del servizio. Spento (`promemoria_nel_servizio`): toglie il segno (con gli account) e finisce, il giro resta al
    cron. Acceso: un giro subito (dopo `ritardo` secondi: le prime richieste passano prima) e poi uno a ogni turno di OGNI_MINUTI
    minuti, mezzo secondo dopo il minuto tondo.
    Il segno si scrive solo dopo un giro riuscito e finito (non interrotto dalla chiusura del servizio): vuol dire «i promemoria di
    questo turno sono partiti». Un giro in errore lascia una riga nel registro (solo il tipo), niente segno, e si riprova al minuto
    dopo invece che al turno dopo; se non riesce entro ATTESA_CRON secondi dal minuto tondo il giro di quel turno lo fa il cron.
    Quanti promemoria sono partiti va nel registro del servizio, con il numero dell'utente e mai il nome."""
    if not promemoria_nel_servizio():
        if account.multiutente():
            _file_segno(file).unlink(missing_ok=True)
        return
    from .riscaldamento import bassa_priorita
    bassa_priorita()
    fermo.wait(ritardo)
    fatto = None
    while not fermo.is_set():
        ora = adesso()
        if _turno(ora) != fatto:              # «diverso», non «dopo»: anche quando l'ora legale torna indietro
            try:
                db = apri_db()
                try:
                    esiti, _ = giro(db, fermo)    # gli errori di un utente li scrive già `esegui` nel registro
                finally:
                    db.close()
            except Exception as e:  # noqa: BLE001 - il thread deve continuare; nel registro solo il tipo, mai i dati
                LOG.warning("Promemoria nel servizio: giro non riuscito (%s), si riprova fra un minuto", type(e).__name__)
            else:
                fatto = _turno(ora)
                _dopo_il_giro(ora, esiti, file, finito=not fermo.is_set())
        fermo.wait(_attesa(adesso()))


def _dopo_il_giro(ora: datetime, esiti: dict[str, list[str]], file: Path | None, finito: bool) -> None:
    """Dopo un giro riuscito: il segno (solo se il giro è finito: interrotto dalla chiusura del servizio, gli utenti rimasti li
    serve il giro dopo) e le righe dei promemoria partiti. Se uno dei due non si scrive, una riga nel registro e si va avanti."""
    if finito:
        try:
            scrivi_sicuro(_file_segno(file), json.dumps({"giro": ora.isoformat(timespec="seconds")}))
        except OSError as e:
            LOG.warning("Promemoria nel servizio: segno non scritto (%s), il prossimo giro lo rifà anche il cron", type(e).__name__)
    try:
        _registra_mandati(esiti)
    except Exception as e:  # noqa: BLE001 - i promemoria sono partiti: manca solo la riga che li conta
        LOG.warning("Promemoria nel servizio: avvisi partiti non contati nel registro (%s)", type(e).__name__)


def _registra_mandati(esiti: dict[str, list[str]]) -> None:
    """«Promemoria: utente 3, 1 avvisi», come le righe del cron in dati/promemoria.log: solo il numero dell'utente."""
    mandati = {nome: len(righe) for nome, righe in esiti.items() if righe}
    if not mandati:
        return
    with contextlib.closing(account.apri()) as db:
        numero = {u["nome_utente"]: u["id"] for u in account.elenco(db)}
    for nome, n in mandati.items():
        logging.getLogger("uvicorn.error").info("Promemoria: utente %s, %d avvisi", numero.get(nome, "?"), n)
