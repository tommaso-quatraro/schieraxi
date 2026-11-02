"""Controllo di salute dell'app (gira ogni 10 minuti sul server insieme ai promemoria): se il servizio non risponde o i dati
non si aggiornano da troppo tempo manda un avviso sul telefono. Testi generici, un avviso per problema (poi ogni 12 ore finche' dura)."""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from .notifiche import _json, invia
from .percorsi import RADICE, scrivi_sicuro

FILE_STATO = RADICE / "dati" / "salute.json"
DATI_VECCHI = timedelta(hours=30)         # l'aggiornamento gira 4 volte al giorno: 30 ore senza novita' sono un problema
RIPETI = timedelta(hours=12)
ERRORI_GRAVI = 3                          # passi dell'aggiornamento falliti nello stesso giro (su sei) oltre i quali si avvisa


def servizio_risponde(indirizzo: str = "http://127.0.0.1:8000/api/stato", attesa: float = 6.0) -> bool:
    try:
        with urllib.request.urlopen(indirizzo, timeout=attesa) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 401          # con gli account accesi lo stato chiede l'accesso: un 401 vuol dire che il servizio c'è e protegge
    except (OSError, ValueError):
        return False


TENTATIVI = 3                             # prove prima di dire "non risponde": un riavvio (aggiornamento dell'app) dura qualche secondo
PAUSA = 5.0                               # secondi fra una prova e l'altra


def servizio_risponde_con_tentativi(prova: Callable[[], bool] = servizio_risponde, tentativi: int = TENTATIVI,
                                     pausa: float = PAUSA, dormi: Callable[[float], None] = time.sleep) -> bool:
    """True appena una prova riesce; False solo se falliscono tutte (con una pausa fra l'una e l'altra)."""
    for i in range(tentativi):
        if prova():
            return True
        if i < tentativi - 1:
            dormi(pausa)
    return False


def controlla(db: sqlite3.Connection, adesso: datetime | None = None, file_stato: Path | None = None,
              manda: Callable[..., bool] = invia, risponde: Callable[[], bool] = servizio_risponde_con_tentativi) -> list[str]:
    """Restituisce i problemi trovati (e li manda sul telefono se sono nuovi o se durano da piu' di 12 ore)."""
    adesso = adesso or datetime.now()
    file_stato = file_stato or FILE_STATO
    problemi = {}
    if not risponde():
        problemi["servizio"] = "L'app SchieraXI non risponde: controlla il servizio sul server."
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    try:
        ultimo = datetime.fromisoformat(r[0]) if r and r[0] else None
    except ValueError:
        ultimo = None
    if ultimo is None or adesso - ultimo > DATI_VECCHI:
        ore = "da molto" if ultimo is None else f"da {int((adesso - ultimo).total_seconds() // 3600)} ore"
        problemi["dati"] = f"I dati di SchieraXI non si aggiornano {ore}."
    errori = db.execute("SELECT dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    try:
        n_errori = len(json.loads(errori[0])) if errori and errori[0] else 0
    except (ValueError, TypeError):
        n_errori = 0
    if n_errori >= ERRORI_GRAVI:
        problemi["errori"] = f"L'ultimo aggiornamento dei dati ha avuto {n_errori} errori: controlla in Lega > Dati > Stato dei dati."
    stato = _json(file_stato)
    avvisati = stato.get("avvisati", {})
    for chiave in [k for k in avvisati if k not in problemi]:
        avvisati.pop(chiave)                   # il problema e' passato: se torna, si riavvisa subito
    for chiave, testo in problemi.items():
        prima = avvisati.get(chiave)
        if prima and adesso - datetime.fromisoformat(prima) < RIPETI:
            continue
        if manda("SchieraXI · attenzione", testo, 4, "warning"):
            avvisati[chiave] = adesso.isoformat(timespec="seconds")
    stato["avvisati"] = avvisati
    scrivi_sicuro(file_stato, json.dumps(stato))
    return list(problemi.values())
