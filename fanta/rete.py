"""Scaricamento dalle fonti, con educazione: una richiesta alla volta, pausa tra l'una e l'altra, nuovi tentativi."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

CONTATTO_PREDEFINITO = "contatti@schieraxi.it"


def _versione() -> str:
    """Numero di versione dell'app (la prima voce di novita.json); "0" se non si legge."""
    try:
        return str(json.loads((Path(__file__).parent / "novita.json").read_text(encoding="utf-8"))[0]["versione"])
    except (OSError, ValueError, LookupError, TypeError):
        return "0"


def agente_onesto() -> str:
    """User-Agent che dice chi siamo e dove trovarci (FANTA_CONTATTO per mettere un altro indirizzo o una email)."""
    contatto = "".join(c for c in (os.environ.get("FANTA_CONTATTO") or CONTATTO_PREDEFINITO) if 32 < ord(c) < 127)[:200]
    return f"SchieraXI/{_versione()} (+{contatto or CONTATTO_PREDEFINITO})"


UA = agente_onesto()      # agente onesto: dice chi siamo
PAUSA = 1.0          # secondi tra una richiesta e l'altra
TENTATIVI = 3

_sessione = requests.Session()
_sessione.headers["User-Agent"] = UA
_ultima = 0.0
contatore = 0        # richieste fatte in questa esecuzione (per i resoconti)


def scarica(url: str, headers: dict | None = None, timeout: int = 30) -> requests.Response:
    global _ultima, contatore
    errore: Exception | None = None
    for tentativo in range(TENTATIVI):
        attesa = PAUSA * (1 + 2 * tentativo) - (time.monotonic() - _ultima)
        if attesa > 0:
            time.sleep(attesa)
        _ultima = time.monotonic()
        contatore += 1
        try:
            r = _sessione.get(url, headers=headers, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                errore = requests.HTTPError(f"{r.status_code} per {url}")
                continue
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout) as e:
            errore = e
    raise errore  # type: ignore[misc]
