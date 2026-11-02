"""Lista dei giocatori osservati (per il mercato): restano sul server, così li ritrovi da ogni dispositivo
e gli avvisi sul telefono possono dirti quando cambia qualcosa (infortunio, titolare, panchina...)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .percorsi import RADICE, scrivi_sicuro

FILE_OSSERVATI = RADICE / "dati" / "osservati.json"
MASSIMO = 60
_blocco = threading.Lock()          # leggere-modificare-scrivere una alla volta: due tocchi insieme non si perdono


def leggi(percorso: Path | None = None) -> list[int]:
    try:
        d = json.loads((percorso or FILE_OSSERVATI).read_text(encoding="utf-8"))
        return [int(i) for i in d] if isinstance(d, list) else []
    except (OSError, ValueError, TypeError):
        return []


def aggiungi(i: int, percorso: Path | None = None) -> list[int]:
    with _blocco:
        lista = leggi(percorso)
        if i not in lista:
            lista.append(int(i))
        lista = lista[-MASSIMO:]
        scrivi_sicuro(percorso or FILE_OSSERVATI, json.dumps(lista))
        return lista


def togli(i: int, percorso: Path | None = None) -> list[int]:
    with _blocco:
        lista = [x for x in leggi(percorso) if x != i]
        scrivi_sicuro(percorso or FILE_OSSERVATI, json.dumps(lista))
        return lista
