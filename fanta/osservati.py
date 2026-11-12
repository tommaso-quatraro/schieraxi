"""Lista dei giocatori osservati (per il mercato): restano sul server, così li ritrovi da ogni dispositivo
e gli avvisi sul telefono possono dirti quando cambia qualcosa (infortunio, titolare, panchina...)."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from .percorsi import RADICE, scrivi_sicuro

FILE_OSSERVATI = RADICE / "dati" / "osservati.json"
MASSIMO = 60
ID_MASSIMO = 2**31 - 1              # il codice calciatore più grande che sqlite sa cercare
_blocco = threading.Lock()          # leggere-modificare-scrivere una alla volta: due tocchi insieme non si perdono


def leggi(percorso: Path | None = None) -> list[int]:
    """L'elenco come lo tiene `aggiungi`: ogni codice una volta, al massimo gli ultimi MASSIMO (vale anche per un file scritto da fuori)."""
    try:
        d = json.loads((percorso or FILE_OSSERVATI).read_text(encoding="utf-8"))
        # un numero fuori misura (salvato da una versione vecchia) farebbe fallire ogni lettura dell'elenco: si salta
        validi = [int(i) for i in d if 1 <= int(i) <= ID_MASSIMO] if isinstance(d, list) else []
    except (OSError, ValueError, TypeError, OverflowError):      # OverflowError: «Infinity» nel file
        return []
    return list(dict.fromkeys(validi))[-MASSIMO:]


def nel_listone(db, ids: list[int]) -> set[int]:
    """Quali di questi codici sono giocatori del listone (tabella `calciatori`). Query parametrizzata (al massimo 900 codici: il tetto delle variabili di sqlite)."""
    ids = [int(i) for i in ids][:900]
    if not ids:
        return set()
    segni = ",".join("?" * len(ids))
    return {int(r[0]) for r in db.execute(f"SELECT id FROM calciatori WHERE id IN ({segni})", ids)}


def aggiungi(i: int, percorso: Path | None = None, validi: set[int] | None = None) -> list[int]:
    """Aggiunge un osservato (in fondo; oltre MASSIMO si perdono i più vecchi). Con `validi` (i codici del listone) quelli salvati
    e non più validi si tolgono: non occupano posti."""
    with _blocco:
        lista = leggi(percorso)
        if validi is not None:
            lista = [x for x in lista if x in validi]
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
