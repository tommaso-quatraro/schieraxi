"""Statistiche di squadra da football-data.co.uk (xG, tiri, angoli, falli, cartellini): MODALITÀ OMBRA, il modello non le legge.
Del file si usano solo queste colonne; il resto non viene letto né salvato."""
from __future__ import annotations

import csv
import io
from datetime import datetime

BASE = "https://www.football-data.co.uk"


def url_stagione(codice: str) -> str:
    """codice tipo '2627' per la stagione 2026/27."""
    return f"{BASE}/mmz4281/{codice}/I1.csv"


URL_PROSSIME = f"{BASE}/fixtures.csv"

_EXTRA_NUMERI = {
    "xg_casa": "HxG", "xg_trasferta": "AxG",
    "tiri_casa": "HS", "tiri_trasferta": "AS", "in_porta_casa": "HST", "in_porta_trasferta": "AST",
    "angoli_casa": "HC", "angoli_trasferta": "AC", "falli_casa": "HF", "falli_trasferta": "AF",
    "gialli_casa": "HY", "gialli_trasferta": "AY", "rossi_casa": "HR", "rossi_trasferta": "AR",
}


def _numero(riga: dict, colonna: str) -> float | None:
    v = (riga.get(colonna) or "").strip()
    try:
        return float(v) if v else None
    except ValueError:
        return None


def leggi_extra(testo: str, slug_di) -> list[dict]:
    """Una riga per partita di Serie A con almeno un valore; i campi mancanti restano None. Chiave: (casa, trasferta)."""
    righe = []
    for r in csv.DictReader(io.StringIO(testo.lstrip("﻿"))):
        if r.get("Div") != "I1":
            continue
        casa, trasferta = slug_di(r.get("HomeTeam", "")), slug_di(r.get("AwayTeam", ""))
        if not casa or not trasferta:
            continue
        try:
            data = datetime.strptime(r["Date"], "%d/%m/%Y").date().isoformat()
        except (KeyError, ValueError):
            continue
        valori = {k: _numero(r, colonna) for k, colonna in _EXTRA_NUMERI.items()}
        for k in ("xg_casa", "xg_trasferta"):      # fuori dall'intervallo plausibile (0-6): dato rotto, si scarta
            if valori[k] is not None and not 0 <= valori[k] <= 6:
                valori[k] = None
        if all(v is None for v in valori.values()):
            continue
        righe.append({"data": data, "casa": casa, "trasferta": trasferta, **valori})
    return righe
