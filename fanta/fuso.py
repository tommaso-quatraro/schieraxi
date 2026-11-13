"""Ora italiana per tutta l'app (#665).

Le date del calendario sono in ora italiana e la logica le confronta con `datetime.now()`, cioè con l'ora del sistema senza fuso.
Su un sistema in UTC (il valore di partenza di quasi tutti i server) tutto slitterebbe di 1 ora d'inverno e di 2 d'estate, senza
nessun errore: formazione salvabile dopo il calcio d'inizio, ore mancanti sbagliate, promemoria, copia alla scadenza e diretta in
ritardo. Quindi:
- `imposta()`: chi lancia l'app (`python -m fanta`: il servizio e tutti i comandi del cron) dà a tutto il processo l'ora italiana,
  qualunque sia il fuso del sistema. Su Windows il fuso di un processo non si cambia: si controlla soltanto;
- `orologio_italiano()`: True se l'orologio del processo dà davvero l'ora italiana (la salute avvisa se no).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NOME = "Europe/Rome"
FUSO = ZoneInfo(NOME)
# la stessa regola scritta per esteso (ora solare +1, legale +2 dall'ultima domenica di marzo all'ultima di ottobre), per un sistema
# senza l'archivio dei fusi: lì «Europe/Rome» non si trova e la libreria del sistema userebbe UTC senza dirlo
REGOLA = "CET-1CEST,M3.5.0,M10.5.0/3"
TOLLERANZA = timedelta(minutes=1)


def orologio_italiano(locale: datetime | None = None, istante: datetime | None = None) -> bool:
    """True se `locale` (l'ora del processo, senza fuso) è l'ora italiana dell'istante `istante` (con fuso), a meno di un minuto.
    Senza argomenti guarda l'orologio vero (per la salute e per `imposta`)."""
    if locale is None or istante is None:
        istante = datetime.now(timezone.utc)
        locale = datetime.now()
    return abs(locale - istante.astimezone(FUSO).replace(tzinfo=None)) <= TOLLERANZA


def imposta() -> bool:
    """Ora italiana per tutto il processo (variabile TZ), prima con il nome del fuso e, se il sistema non lo conosce, con la regola
    per esteso. Va chiamata all'avvio, prima dei thread. True se dopo l'orologio del processo dà l'ora italiana."""
    if not hasattr(time, "tzset"):                 # Windows: il fuso del processo resta quello del sistema
        return orologio_italiano()
    for valore in (NOME, REGOLA):
        os.environ["TZ"] = valore
        time.tzset()
        if orologio_italiano():
            return True
    return False
