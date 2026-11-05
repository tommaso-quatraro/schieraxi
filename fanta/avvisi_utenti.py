"""Gli avvisi di ogni utente (solo con FANTA_MULTIUTENTE=1): cambi delle probabili, promemoria, riepilogo, «formazione pronta».

Con l'interruttore spento gli avvisi sono quelli di sempre (un solo utente, file globali, ntfy): non passano di qui.
Con l'interruttore acceso i comandi `cambi`, `promemoria`, `riepilogo` e `avviso` (che il server lancia da cron) chiamano
`esegui`, che passa uno per uno gli utenti *attivi* (con una squadra indicata e almeno un dispositivo iscritto alle notifiche web)
e per ciascuno usa i SUOI file: rose, regole, impostazioni, osservati, scelte, iscrizioni e «cosa ho già avvisato».
- Il canale ntfy è uno solo ed è del proprietario del server: gli utenti non ci passano mai. L'unica eccezione è un
  amministratore che ha acceso l'opzione dell'app nativa (come con l'interruttore spento).
- Un errore con un utente non ferma gli altri.
- Lavoro pesante: i cambi confrontano prima gli stati dei giocatori (poco costoso) e ricalcolano la formazione solo se qualcosa è cambiato.
"""
from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from . import account, avvisi, consigli, lega, notifiche, push, regole
from .account import Utente
from .contesto import Contesto
from .lega import Rose

FUNZIONI = ("cambi", "promemoria", "riepilogo", "pronta")


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


def utenti_attivi() -> list[Attivo]:
    """Chi ha una squadra e almeno un modo per ricevere gli avvisi."""
    with contextlib.closing(account.apri()) as db:
        elenco = [account.trova(db, r["id"]) for r in account.elenco(db)]
    attivi = []
    for utente in elenco:
        ctx = Contesto.per_utente(utente.id)
        try:
            rose = lega.carica(ctx.rose)
        except ValueError:                                 # file rovinato: quell'utente per ora non riceve avvisi
            continue
        if not rose or not rose.mia_squadra:
            continue
        opzioni = notifiche.impostazioni(ctx.impostazioni_avvisi)
        ntfy = ntfy_consentito(utente, opzioni)
        if push.iscrizioni(ctx.iscrizioni_push) or (ntfy and notifiche.canale()):
            attivi.append(Attivo(utente, ctx, rose, opzioni, ntfy))
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
    giornata = consigli.giornata_da_giocare(db, stagione, r)
    avviso = avvisi.da_mandare(db, stagione, giornata, adesso, a.ctx.stato_avvisi, segna=False, regole=r)
    if avviso and a.manda(avviso["titolo"], avviso["testo"], 3, "soccer"):
        avvisi.segna(stagione, giornata, a.ctx.stato_avvisi)
        return [avviso["testo"]]
    return []


_LAVORI = {"cambi": _cambi, "promemoria": _promemoria, "riepilogo": _riepilogo, "pronta": _pronta}


def esegui(funzione: str, db: sqlite3.Connection, adesso: datetime | None = None,
           attivi: list[Attivo] | None = None) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Esegue `funzione` (una di FUNZIONI) per ogni utente attivo. Restituisce ({nome utente: righe mandate}, {nome utente: errore}).
    Dell'errore si dice solo il tipo (niente dati personali nei log)."""
    lavoro = _LAVORI[funzione]
    adesso = adesso or datetime.now()
    esiti: dict[str, list[str]] = {}
    errori: dict[str, str] = {}
    for a in (utenti_attivi() if attivi is None else attivi):
        try:
            esiti[a.utente.nome_utente] = lavoro(a, db, regole.carica(a.ctx.regole), adesso)
        except Exception as e:  # noqa: BLE001 - un utente con dati strani non deve fermare gli avvisi degli altri
            errori[a.utente.nome_utente] = type(e).__name__
    return esiti, errori
