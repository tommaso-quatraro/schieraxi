"""Riscaldamento della cache dentro il servizio: dopo ogni aggiornamento dei dati (e all'avvio) si calcolano in anticipo
formazione, scambi proposti, svincolati consigliati e riassunto per il widget, così quando si apre l'app sono già pronti.

Come funziona: un thread a bassa priorità controlla ogni minuto la «versione» dei dati (l'ora dell'ultimo aggiornamento,
scritta dal comando `aggiorna` anche se gira in un altro processo) e lo stato delle giornate delle leghe attive (`stato_giornate`:
giornata, scadenza passata, anticipi cominciati, che cambiano con l'ora). Se uno dei due è cambiato, o comunque ogni RIPASSO,
calcola per l'utente unico (senza account) oppure per gli utenti attivi di recente (con gli account, anche chi usa solo il
widget). I calcoli passano dalla coda di `calcolo`, quindi non sono mai più di due insieme e le richieste vere aspettano al
massimo un calcolo alla volta."""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Iterable

from . import account, calcolo, consigli, lega, regole, widget
from .contesto import Contesto

INTERVALLO = 60            # secondi tra un controllo e l'altro
MAX_UTENTI = 40            # quanti utenti attivi si preparano dopo ogni aggiornamento (i più recenti per primi). Misurato il 2/11/2026 in locale, 1 CPU:
                           # circa 0,8 s di CPU a utente con regole tutte diverse (30 utenti: 23-29 s; sul server di produzione circa il doppio). Ognuno occupa
                           # circa 3 «unità» della cache (calcolo.MAX_RISULTATI = 256): 40 utenti ne usano circa 110, nessuno esce prima di servire
ATTIVO_DA = timedelta(days=7)
RITARDO_AVVIO = 3.0        # secondi di attesa dopo l'avvio: il primo /api/stato e le prime richieste passano per primi
PAUSA = 0.2               # secondi di respiro tra un utente e l'altro
RIPASSO = 15 * 60          # secondi: anche senza cambi, un giro ogni quarto d'ora rimette in memoria quello che ne è uscito (cache piena) o non
                           # è riuscito (errore momentaneo). Per chi è già pronto costa poco (è tutto in memoria); il widget, che non calcola,
                           # così non resta mai senza dati più di tanto (#651)


def attivo() -> bool:
    """FANTA_RISCALDA=0 spegne il riscaldamento (si calcola alla prima richiesta, come prima)."""
    return os.environ.get("FANTA_RISCALDA", "").strip() != "0"


def ritardo_avvio() -> float:
    """Secondi prima del primo riscaldamento (FANTA_RISCALDA_RITARDO li cambia; valore non valido = predefinito)."""
    try:
        return max(0.0, min(300.0, float(os.environ.get("FANTA_RISCALDA_RITARDO", RITARDO_AVVIO))))
    except ValueError:
        return RITARDO_AVVIO


def bassa_priorita() -> None:
    """Il thread corrente passa dietro agli altri (dove il sistema lo permette: su Linux ogni thread ha la sua «nice»)."""
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 10)
    except (AttributeError, OSError):
        pass


def contesti_da_scaldare(contesto_locale: Callable[[], Contesto], adesso=None) -> list[Contesto]:
    """Utente unico senza account; con gli account, chi ha usato l'app o il widget negli ultimi 7 giorni (i più recenti per primi).
    Il widget conta (#651): il suo token non fa partire calcoli, quindi chi guarda solo il widget trova i dati solo se si preparano qui."""
    if not account.multiutente():
        return [contesto_locale()]
    ora = account._ora(adesso)
    limite = account._testo(ora - ATTIVO_DA)
    db = account.apri()
    try:
        righe = db.execute("SELECT utente_id FROM ("
                           "SELECT utente_id, ultimo_uso FROM sessioni WHERE revocata = 0 AND ultimo_uso >= ? "
                           "UNION ALL SELECT utente_id, ultimo_uso FROM token_widget WHERE ultimo_uso >= ? AND scade > ?"
                           ") GROUP BY utente_id ORDER BY MAX(ultimo_uso) DESC LIMIT ?",
                           (limite, limite, account._testo(ora), MAX_UTENTI)).fetchall()
    finally:
        db.close()
    return [Contesto.per_utente(r[0]) for r in righe]


def stato_giornate(db: sqlite3.Connection, leghe: Iterable[regole.Regole], adesso: datetime) -> tuple:
    """Quello che cambia con l'ora e cambia i calcoli da tenere pronti, per ogni lega attiva: la giornata da giocare, se la formazione
    è chiusa (scadenza passata) e, prima della scadenza, le squadre con un anticipo già cominciato. Sono le parti della chiave della
    consigliata che non vengono dai dati (consigli.formazione): quando cambiano, il widget (sola cache) non trova più la sua finché non
    si riscalda (#651). Contano solo la prima giornata della lega e i minuti della scadenza: leghe uguali su questi si guardano una volta."""
    stagione = consigli.stagione_corrente()
    tempi = {(getattr(r, "prima_giornata_lega", 1), getattr(r, "scadenza_minuti", 0)): r for r in leghe}
    stati = set()
    for r in tempi.values():
        giornata = consigli.giornata_da_giocare(db, stagione, r, adesso)
        if giornata is None:
            continue
        chiusa = consigli._chiusa(db, r, stagione, giornata, adesso)
        stati.add((giornata, chiusa, () if chiusa else consigli._anticipi_iniziati(db, stagione, giornata, adesso)))
    return tuple(sorted(stati))


def scalda_contesto(ctx: Contesto, db) -> bool:
    """Formazione e valori del mercato di un utente. False se non ha ancora rose o squadra."""
    r = lega.carica(ctx.rose)
    if not r or not r.mia_squadra:
        return False
    reg = regole.carica(ctx.regole)
    consigli.formazione(db, reg, r)
    consigli.valori_scambi(db, reg)
    # quello che chiedono subito la schermata Oggi, il Mercato e il widget dell'iPhone (/api/widget legge solo la cache)
    consigli.proposte_scambi(db, reg, r)
    consigli.mercato(db, reg, r)
    try:
        widget.costruisci(db, reg, r, ctx.diario, ctx.osservati)       # ricorda anche il riassunto del nucleo (Oggi)
    except calcolo.InCalcolo:
        pass
    return True


def scalda_tutti(contesto_locale: Callable[[], Contesto], apri_db: Callable[[], object], adesso=None) -> int:
    """Scalda tutti gli utenti da scaldare. Un errore (rose mancanti, calendario non ancora uscito) non ferma gli altri.
    `adesso`: l'ora con cui contare chi è attivo (per le prove); senza, l'ora vera."""
    fatti = 0
    try:
        contesti = contesti_da_scaldare(contesto_locale, adesso)
    except Exception:  # noqa: BLE001 - è solo un'anticipazione
        return 0
    for i, ctx in enumerate(contesti):
        if i:
            threading.Event().wait(PAUSA)
        db = apri_db()
        try:
            fatti += bool(scalda_contesto(ctx, db))
        except Exception:  # noqa: BLE001 - se non riesce, si calcola alla prima richiesta
            pass
        finally:
            db.close()
    return fatti


def sorveglia(versione: Callable[[], object], scalda: Callable[[], object], fermo: threading.Event,
              intervallo: float = INTERVALLO, ritardo: float = 0, ripasso: float = RIPASSO,
              tempo: Callable[[], float] = time.monotonic) -> None:
    """Scalda all'avvio, ogni volta che cambia quello che restituisce `versione` (dal server: versione dei dati e `stato_giornate`) e
    comunque ogni `ripasso` secondi (0 = mai), finché `fermo` non scatta. `tempo`: i secondi che passano (per le prove)."""
    bassa_priorita()
    if ritardo and fermo.wait(ritardo):   # prima si servono le richieste dell'avvio; se il servizio si ferma prima, non si calcola nulla
        return
    vista, ultimo = object(), 0.0         # nessuna versione ancora vista: il primo giro scalda sempre
    while not fermo.is_set():
        try:
            v = versione()
            if v != vista or (ripasso and tempo() - ultimo >= ripasso):
                vista, ultimo = v, tempo()
                scalda()
        except Exception:  # noqa: BLE001 - il controllo deve continuare anche dopo un errore
            pass
        fermo.wait(intervallo)
