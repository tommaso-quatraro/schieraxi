"""Tratti grossolani dei giocatori per gli avatar illustrati (docs/AVATAR.md, sezione 8: p carnagione, c capelli, a acconciatura, b barba, f barba folta; vedi docs/AVATAR-DIRITTI.md).

`fanta/avatar_tratti.json` lo scrive `script/avatar_tratti.py` (offline, dai ritagli già scaricati); qui si legge soltanto, con controlli:
un file mancante o rovinato vale «nessun tratto» e gli avatar vengono tutti dal seme. Nessuna foto serve a runtime."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

FILE = Path(__file__).resolve().parent / "avatar_tratti.json"
RADICE = Path(__file__).resolve().parent.parent
FAMIGLIE = {"R", "C", "L", "I"}


def _valido(t) -> dict | None:
    if not isinstance(t, dict):
        return None
    o = {}
    if type(t.get("p")) is int and 0 <= t["p"] <= 6:
        o["p"] = t["p"]
    if type(t.get("c")) is int and 0 <= t["c"] <= 7:
        o["c"] = t["c"]
    if t.get("a") in FAMIGLIE:
        o["a"] = t["a"]
    if t.get("b") in (0, 1) and type(t.get("b")) is int:
        o["b"] = t["b"]
    if o.get("b") == 1 and t.get("f") in (0, 1) and type(t.get("f")) is int:
        o["f"] = t["f"]                                  # barba folta: ha senso solo con la barba
    return o or None


def percorso() -> Path:
    """Il file dei tratti: quello indicato da FANTA_AVATAR_TRATTI (se esiste; un percorso relativo parte dalla radice del progetto,
    per esempio `dati/avatar_tratti.json`), altrimenti `fanta/avatar_tratti.json`. Il file non sta nel repository pubblico (riguarda persone vere):
    se non c'è da nessuna parte, tutti i volti hanno la carnagione neutra."""
    v = os.environ.get("FANTA_AVATAR_TRATTI", "").strip()
    if v:
        p = Path(v)
        p = p if p.is_absolute() else RADICE / p
        if p.is_file():
            return p
    return FILE


@lru_cache(maxsize=1)
def tutti() -> dict[int, dict]:
    """{codice calciatore: tratti} (solo voci valide)."""
    try:
        grezzo = json.loads(percorso().read_text(encoding="utf-8")).get("tratti", {})
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for k, v in (grezzo.items() if isinstance(grezzo, dict) else []):
        t = _valido(v)
        if t and str(k).isdigit():
            out[int(k)] = t
    return out


def di(calciatore_id) -> dict | None:
    try:
        return tutti().get(int(calciatore_id))
    except (TypeError, ValueError):
        return None
