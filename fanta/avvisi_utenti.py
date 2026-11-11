"""Gli avvisi di ogni utente (solo con FANTA_MULTIUTENTE=1): cambi delle probabili, promemoria, riepilogo, «formazione pronta».

Con l'interruttore spento gli avvisi sono quelli di sempre (un solo utente, file globali, ntfy): non passano di qui.
Con l'interruttore acceso i comandi `cambi`, `promemoria`, `riepilogo` e `avviso` (che il server lancia da cron) chiamano
`esegui`, che passa uno per uno gli utenti *attivi* (con una squadra indicata e almeno un dispositivo iscritto alle notifiche web)
e per ciascuno usa i SUOI file: rose, regole, impostazioni, osservati, scelte, iscrizioni e «cosa ho già avvisato».
- Il canale ntfy è uno solo ed è del proprietario del server: gli utenti non ci passano mai. L'unica eccezione è un
  amministratore che ha acceso l'opzione dell'app nativa (come con l'interruttore spento).
- Un errore con un utente non ferma gli altri.
- Il giro ha un tempo massimo e un ordine a rotazione: chi resta fuori per il tempo finito passa per primo al giro dopo.
- Lavoro pesante: i cambi confrontano prima gli stati dei giocatori (poco costoso) e ricalcolano la formazione solo se qualcosa è cambiato.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import account, avvisi, consigli, lega, notifiche, percorsi, push, regole
from .account import Utente
from .contesto import Contesto
from .lega import Rose
from .percorsi import scrivi_sicuro

FUNZIONI = ("cambi", "promemoria", "riepilogo", "pronta")
LOG = logging.getLogger(__name__)


@dataclass
class Attivo:
    utente: Utente
    ctx: Contesto
    rose: Rose
    opzioni: dict
    ntfy: bool

    @property
    def manda(self) -> Callable[..., bool]:
        return notifiche.manda_di(self.ctx.impostazioni_avvisi, self.ctx.iscrizioni_push, self.ntfy)


def ntfy_consentito(utente: Utente, opzioni: dict) -> bool:
    """Il canale ntfy è del proprietario del server: solo un amministratore, e solo se ha acceso l'opzione dell'app nativa."""
    return utente.amministratore and bool(opzioni.get("app_nativa"))


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
    avvisi, e non ferma gli altri."""
    with contextlib.closing(account.apri()) as db:
        elenco = [account.trova(db, r["id"]) for r in account.elenco(db)]
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
    righe = []
    if a.opzioni["cambi"]:
        righe = notifiche.cambi(db, r, a.rose, adesso, a.ctx.stato_cambi, a.manda, a.opzioni, a.ctx.osservati, risparmia=True,
                                file_scelte=a.ctx.scelte, file_promemoria=a.ctx.stato_promemoria)
    try:                                           # reparti della rosa scoperti: stesso giro, opzione propria
        righe += notifiche.copertura(db, r, a.rose, adesso, a.ctx.stato_cambi, a.manda, a.opzioni)
    except Exception:                              # noqa: BLE001  (i cambi sono già partiti)
        pass
    return righe


def _promemoria(a: Attivo, db: sqlite3.Connection, r: regole.Regole, adesso: datetime) -> list[str]:
    righe = []
    if a.opzioni.get("avviso_prima"):              # prima l'avviso «cambia la formazione»: se parte, il promemoria non fa il doppione
        try:
            righe = notifiche.avviso_scadenza(db, r, a.rose, adesso, a.ctx.stato_promemoria, a.manda, a.opzioni, a.ctx.scelte,
                                              a.ctx.stato_cambi)
        except Exception:                          # noqa: BLE001  (i promemoria partono comunque)
            righe = []
    if not (a.opzioni["promemoria_60"] or a.opzioni["promemoria_15"]):
        return righe
    return righe + notifiche.promemoria(db, r, a.rose, adesso, a.ctx.stato_promemoria, a.manda, a.opzioni, a.ctx.scelte)


def _riepilogo(a: Attivo, db: sqlite3.Connection, r: regole.Regole, adesso: datetime) -> list[str]:
    if not a.opzioni["riepilogo"]:
        return []
    return notifiche.riepilogo(db, r, a.rose, adesso, a.ctx.stato_riepilogo, a.manda, a.opzioni, a.ctx.stato_cambi, a.ctx.scelte,
                               a.ctx.diario)


def _pronta(a: Attivo, db: sqlite3.Connection, r: regole.Regole, adesso: datetime) -> list[str]:
    """«La formazione è pronta»: una volta per giornata, e solo se l'avviso è davvero partito (nelle ore tranquille si riprova dopo)."""
    if notifiche.in_silenzio(adesso, a.opzioni):
        return []
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, r, adesso)     # l'ora del giro, non l'orologio vero
    avviso = avvisi.da_mandare(db, stagione, giornata, adesso, a.ctx.stato_avvisi, segna=False, regole=r)
    if avviso and a.manda(avviso["titolo"], avviso["testo"], 3, "soccer"):
        avvisi.segna(stagione, giornata, a.ctx.stato_avvisi)
        return [avviso["testo"]]
    return []


_LAVORI = {"cambi": _cambi, "promemoria": _promemoria, "riepilogo": _riepilogo, "pronta": _pronta}

# ---------------------------------------------------------------- tempo e ordine del giro
# Gli script del server fermano il comando dopo un tempo massimo (promemoria.sh, aggiorna.sh; le stesse variabili di
# dati/ambiente.env). Il giro si ferma da solo un po' prima, fra un utente e l'altro, così salva l'ordine e non viene interrotto.
TEMPO_SCRIPT = {"promemoria": ("FANTA_MAX_SECONDI_GIRO_PROMEMORIA", 480)}
TEMPO_SCRIPT_ALTRI = ("FANTA_MAX_SECONDI_GIRO_AVVISI", 600)        # cambi, riepilogo, «formazione pronta»
MARGINE_SECONDI = 120          # il lavoro di un utente può durare un po' (due invii lenti e un calcolo): resta questo margine
FILE_GIRO = "avvisi-giro.json"  # nella cartella degli account: per ogni giro, l'ordine in cui gli utenti sono stati serviti


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
    """Salva l'ordine del giro `funzione` lasciando com'è quello degli altri giri. Falso se non si riesce (disco pieno, permessi):
    lo dice il registro, con il solo tipo d'errore, e gli avvisi partono lo stesso."""
    try:
        try:
            tutto = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tutto = {}
        tutto = (tutto if isinstance(tutto, dict) else {}) | {funzione: serviti}
        scrivi_sicuro(file, json.dumps(tutto))
    except OSError as e:
        LOG.warning("Avvisi (%s): ordine del giro non salvato (%s), si continua senza", funzione, type(e).__name__)
        return False
    return True


def esegui(funzione: str, db: sqlite3.Connection, adesso: datetime | None = None,
           attivi: list[Attivo] | None = None, *, max_secondi: float | None = None,
           orologio: Callable[[], float] = time.monotonic, file_giro: Path | None = None) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Esegue `funzione` (una di FUNZIONI) per ogni utente attivo. Restituisce ({nome utente: righe mandate}, {nome utente: errore}).
    Dell'errore si dice solo il tipo (niente dati personali nei log).
    Il giro dura al massimo `max_secondi` (di base `secondi_del_giro`): il tempo si guarda fra un utente e l'altro (almeno uno si
    serve sempre); chi resta passa al giro dopo. L'ordine è a rotazione: prima chi è stato servito meno di recente (o mai), in fondo
    chi è stato servito per ultimo. Ogni utente si segna come servito PRIMA del suo lavoro, così se il giro si ferma mentre lavora
    per lui, al giro dopo va in fondo. L'ordine sta in `file_giro` (di base FILE_GIRO nella cartella degli account; con `attivi`
    indicato da chi chiama, solo se si passa `file_giro`)."""
    lavoro = _LAVORI[funzione]
    adesso = adesso or datetime.now()
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
        if n and orologio() - inizio > limite:
            LOG.warning("Avvisi (%s): tempo del giro finito, %d utenti al prossimo giro", funzione, len(ordinati) - n)
            break
        if file_giro:
            posizione += 1
            serviti[str(a.utente.id)] = posizione
            if not _scrivi_giro(file_giro, funzione, serviti):
                file_giro = None                      # una riga sola nel registro: per questo giro non si riprova
        try:
            esiti[a.utente.nome_utente] = lavoro(a, db, regole.carica(a.ctx.regole), adesso)
        except Exception as e:  # noqa: BLE001 - un utente con dati strani non deve fermare gli avvisi degli altri
            errori[a.utente.nome_utente] = type(e).__name__
    return esiti, errori
