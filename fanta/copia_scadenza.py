"""Copia della formazione consigliata alla scadenza, fatta dal server per ogni utente (anche se nessuno apre l'app).

Prima la copia si salvava solo quando si apriva la pagina Formazione: chi non la apriva prima della scadenza, a giornata finita
non aveva il riepilogo in Oggi né la voce del Diario. Ora un thread del servizio controlla ogni minuto e, negli ultimi ANTICIPO
minuti prima della scadenza della lega di ciascun utente, salva una volta sola:
- la copia automatica in `scelte` (`scelte.salva_automatica`: mai sopra una scelta vera dell'utente);
- l'istantanea della consigliata per il Diario (`diario.salva_istantanea`).
La pagina Formazione continua ad aggiornarle finché la formazione è aperta (`server._copia_automatica`). Dopo la scadenza non si
scrive più niente. Senza account: l'utente unico; con gli account: tutti quelli con una squadra (al massimo MAX_UTENTI).
Un errore con un utente non ferma gli altri; un calcolo non riuscito si riprova al minuto dopo. `FANTA_COPIA_SCADENZA=0` la spegne.
"""
from __future__ import annotations

import contextlib
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Callable, Iterable

from . import account, avvisi, consigli, diario, lega, regole, scelte
from .contesto import Contesto

ANTICIPO = timedelta(minutes=10)    # dopo l'ultimo giro delle probabili (15 minuti prima): la consigliata è già quella finale
INTERVALLO = 60                     # secondi tra un controllo e l'altro
MAX_UTENTI = 200
TENUTE = 1000                       # copie ricordate in memoria (chiavi utente/stagione/giornata)
LOG = logging.getLogger(__name__)


def acceso() -> bool:
    """Interruttore (variabile d'ambiente, letta a ogni controllo): `FANTA_COPIA_SCADENZA=0` la spegne."""
    return os.environ.get("FANTA_COPIA_SCADENZA", "1").strip().lower() not in ("0", "no", "false", "off")


def dovuta(adesso: datetime, scadenza: datetime | None) -> bool:
    """True negli ultimi ANTICIPO minuti prima della scadenza (la scadenza esclusa: da lì la formazione è chiusa)."""
    return scadenza is not None and scadenza - ANTICIPO <= adesso < scadenza


def salva(f: dict, stagione: str, file_scelte, file_diario) -> None:
    """Copia automatica (se l'utente non ha una sua scelta) e istantanea per il Diario della formazione consigliata `f`."""
    g = f.get("giornata")
    if not g or not f.get("titolari"):
        return
    scelte.salva_automatica(stagione, g, [t["id"] for t in f["titolari"]], f.get("modulo", ""), file_scelte)
    diario.salva_istantanea(f, stagione, file_diario)


def copia_utente(ctx: Contesto, db, adesso: datetime, fatte: set[str]) -> str | None:
    """Fa la copia per un utente se è il momento e non è già fatta. Restituisce la chiave della copia fatta, altrimenti None."""
    rose = lega.carica(ctx.rose)
    if not rose or not rose.mia_squadra:
        return None
    reg = regole.carica(ctx.regole)
    stagione = consigli.stagione_corrente()
    g = consigli.giornata_da_giocare(db, stagione, reg, adesso)   # l'ora del giro, non l'orologio vero
    if g is None or not dovuta(adesso, avvisi.scadenza(avvisi.prima_partita(db, stagione, g), reg)):
        return None
    chiave = f"{ctx.utente_id}/{stagione}/{g}"
    if chiave in fatte:
        return None
    f = consigli.formazione(db, reg, rose, giornata=g)            # la stessa giornata, non cercata di nuovo con l'orologio vero
    if f.get("giornata") != g:
        return None
    salva(f, stagione, ctx.scelte, ctx.diario)
    return chiave


def contesti(contesto_locale: Callable[[], Contesto]) -> list[Contesto]:
    """Senza account l'utente unico; con gli account tutti gli utenti (chi non ha una squadra lo salta `copia_utente`)."""
    if not account.multiutente():
        return [contesto_locale()]
    with contextlib.closing(account.apri()) as db:
        return [Contesto.per_utente(r["id"]) for r in account.elenco(db)][:MAX_UTENTI]


def giro(adesso: datetime, elenco: Iterable[Contesto], apri_db: Callable[[], object], fatte: set[str]) -> list[str]:
    """Un controllo per tutti gli utenti. Aggiunge a `fatte` le chiavi delle copie fatte e le restituisce."""
    nuove: list[str] = []
    db = apri_db()
    try:
        for ctx in elenco:
            try:
                chiave = copia_utente(ctx, db, adesso, fatte)
            except Exception as e:  # noqa: BLE001 - rose rovinate, calcolo non riuscito: si riprova al prossimo controllo
                LOG.warning("copia alla scadenza non riuscita (%s)", type(e).__name__)
                continue
            if chiave:
                fatte.add(chiave)
                nuove.append(chiave)
    finally:
        db.close()
    if len(fatte) > TENUTE:
        fatte.clear()                   # le giornate passate non tornano: basta non ricrescere senza fine
        fatte.update(nuove)
    return nuove


def sorveglia(fermo: threading.Event, elenco: Callable[[], list[Contesto]], apri_db: Callable[[], object],
              intervallo: float = INTERVALLO, adesso: Callable[[], datetime] = datetime.now) -> None:
    """Il thread: un controllo al minuto finché `fermo` non scatta."""
    from .riscaldamento import bassa_priorita
    bassa_priorita()
    fatte: set[str] = set()
    while not fermo.is_set():
        try:
            if acceso():
                giro(adesso(), elenco(), apri_db, fatte)
        except Exception as e:  # noqa: BLE001 - il controllo deve continuare anche dopo un errore
            LOG.warning("copia alla scadenza: controllo non riuscito (%s)", type(e).__name__)
        fermo.wait(intervallo)
