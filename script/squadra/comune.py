"""Parti comuni dei comandi della squadra: la funzione unica che lancia gh e git, lettura dei file di dati, date.

Ogni comando riceve `esegui(argomenti) -> Risposta`. Nel programma vero è `esegui_vero`; nei test è un finto con risposte
scritte a mano, così nessun test tocca GitHub."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

CARTELLA = Path(__file__).resolve().parent
RADICE = CARTELLA.parent.parent


@dataclass
class Risposta:
    codice: int
    uscita: str
    errore: str = ""


Esegui = Callable[[list[str]], Risposta]


class ErroreComando(Exception):
    """Un comando gh o git è fallito, o ha risposto qualcosa che non si capisce."""


def esegui_vero(argomenti: list[str]) -> Risposta:
    """L'unico punto che lancia programmi esterni (gh, git). Niente shell: gli argomenti passano come lista."""
    try:
        p = subprocess.run(argomenti, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=RADICE, check=False)
    except FileNotFoundError:
        return Risposta(127, "", f"programma non trovato: {argomenti[0]}")
    return Risposta(p.returncode, p.stdout or "", p.stderr or "")


def chiama(esegui: Esegui, argomenti: list[str]) -> str:
    r = esegui(argomenti)
    if r.codice != 0:
        errore = (r.errore or r.uscita).strip().splitlines()
        raise ErroreComando(f"«{' '.join(argomenti[:4])}» è uscito con {r.codice}: {' '.join(errore)[:300]}")
    return r.uscita


def chiama_json(esegui: Esegui, argomenti: list[str]):
    testo = chiama(esegui, argomenti)
    try:
        return json.loads(testo) if testo.strip() else None
    except json.JSONDecodeError as e:
        raise ErroreComando(f"«{' '.join(argomenti[:4])}» non ha risposto in JSON: {e}") from e


def leggi_json(nome: str) -> dict:
    return json.loads((CARTELLA / nome).read_text(encoding="utf-8"))


def data(testo: str) -> datetime:
    return datetime.fromisoformat(testo.replace("Z", "+00:00"))


def ora() -> datetime:
    return datetime.now(timezone.utc)


def eta(testo: str, adesso: datetime | None = None) -> str:
    """Età leggibile: «10 min», «2 h», «3 g»."""
    secondi = ((adesso or ora()) - data(testo)).total_seconds()
    if secondi < 3600:
        return f"{max(0, int(secondi // 60))} min"
    if secondi < 86400:
        return f"{int(secondi // 3600)} h"
    return f"{int(secondi // 86400)} g"


def tabella(righe: list[list[str]], intestazione: list[str]) -> str:
    """Tabella di testo semplice, colonne allineate a sinistra."""
    tutte = [intestazione] + [[str(c) for c in r] for r in righe]
    larghezze = [max(len(r[i]) for r in tutte) for i in range(len(intestazione))]
    return "\n".join("  ".join(c.ljust(larghezze[i]) for i, c in enumerate(r)).rstrip() for r in tutte)
