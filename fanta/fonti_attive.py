"""Un interruttore per ogni fonte di dati esterna (Fantacalcio.it, Understat, football-data, ESPN, Sosfanta, foto).

Chi decide, in ordine: 1) la scelta dell'amministratore (file dati/fonti.json, cambiabile dall'app); 2) la variabile d'ambiente
FANTA_FONTE_<NOME> ("1" acceso, "0" spento); 3) il predefinito. Il predefinito è SPENTO (chi scarica il codice non contatta siti di terzi senza una scelta);
chi gestisce un server lo accende con FANTA_FONTI_PREDEFINITO=1 (tutte le fonti tranne le foto).
Le foto sono sempre spente salvo scelta esplicita. Restano validi i vecchi FANTA_LIVE=0 (ESPN) e FANTA_FOTO=1 (foto).
Le fonti spente non vengono mai contattate: l'app lavora coi dati già in archivio e con quelli inseriti dall'utente.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .percorsi import RADICE, scrivi_sicuro

PREDEFINITO_ACCESO = os.environ.get("FANTA_FONTI_PREDEFINITO", "").strip() == "1"
FILE = RADICE / "dati" / "fonti.json"


class FonteSpenta(ValueError):
    """La fonte è spenta: il messaggio è adatto all'utente. È un ValueError: le rotte rispondono 400 con il messaggio, non 500."""


# id -> (nome per l'utente, a cosa serve, vero se di norma resta spenta anche nel codice privato)
FONTI: dict[str, tuple[str, str, bool]] = {
    "fantacalcio": ("Fantacalcio.it", "listone, quotazioni, calendario, voti e probabili formazioni", False),
    "understat": ("Understat", "statistiche avanzate (gol e assist attesi, rigori)", False),
    "footballdata": ("football-data.co.uk", "risultati e statistiche di squadra delle partite giocate", False),
    "espn": ("ESPN", "risultati in diretta", False),
    "sosfanta": ("Sosfanta", "seconda fonte di probabili formazioni (solo misura)", False),
    "foto": ("Foto dei giocatori", "foto al posto dei volti illustrati", True),
}


_BLOCCO = threading.Lock()
_cache: dict[str, tuple[tuple[int, int], dict[str, bool]]] = {}      # percorso -> ((data, dimensione), scelte)


def _scelte_admin(percorso: Path | None = None) -> dict[str, bool]:
    """Le scelte dell'amministratore; il file si rilegge solo se è cambiato (data e dimensione)."""
    p = percorso or FILE
    try:
        s = p.stat()
        impronta = (s.st_mtime_ns, s.st_size)
        c = _cache.get(str(p))
        if c and c[0] == impronta:
            return dict(c[1])
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    ok = {k: v for k, v in d.items() if k in FONTI and isinstance(v, bool)} if isinstance(d, dict) else {}
    _cache[str(p)] = (impronta, ok)
    return dict(ok)


def _da_ambiente(fonte: str) -> bool | None:
    v = os.environ.get(f"FANTA_FONTE_{fonte.upper()}", "").strip()
    if fonte == "espn" and not v and os.environ.get("FANTA_LIVE") == "0":
        return False
    if fonte == "foto" and not v and os.environ.get("FANTA_FOTO", "").strip() == "1":
        return True
    return {"1": True, "0": False}.get(v)


def origine(fonte: str, percorso: Path | None = None) -> tuple[bool, str]:
    """(acceso, da dove viene la scelta: "amministratore", "ambiente" o "predefinito")."""
    if fonte not in FONTI:
        raise KeyError(fonte)
    a = _scelte_admin(percorso).get(fonte)
    if a is not None:
        return a, "amministratore"
    e = _da_ambiente(fonte)
    if e is not None:
        return e, "ambiente"
    return (PREDEFINITO_ACCESO and not FONTI[fonte][2]), "predefinito"


def acceso(fonte: str, percorso: Path | None = None) -> bool:
    return origine(fonte, percorso)[0]


def messaggio_spenta(fonte: str) -> str:
    nome, serve, _ = FONTI[fonte]
    if fonte == "foto":
        return "Le foto sono spente: l'app usa i volti illustrati."
    return (f"{nome} è spenta: non scarico {serve}. L'app usa i dati già salvati e quelli che inserisci tu "
            "(per esempio il listone e le rose da file). Se la accendi, rispetti le condizioni d'uso del sito.")


def richiedi(fonte: str) -> None:
    """Alza FonteSpenta (con un messaggio chiaro) se la fonte non va contattata."""
    if not acceso(fonte):
        raise FonteSpenta(messaggio_spenta(fonte))


def stato(percorso: Path | None = None) -> list[dict]:
    """Per «Stato dei dati»: una riga per fonte."""
    righe = []
    for k, (nome, serve, _) in FONTI.items():
        on, da = origine(k, percorso)
        righe.append({"id": k, "nome": nome, "serve": serve, "acceso": on, "scelta_da": da,
                      "messaggio": None if on else messaggio_spenta(k)})
    return righe


def imposta(fonte: str, acceso_: bool | None, percorso: Path | None = None) -> None:
    """Scelta dell'amministratore; None la toglie (torna ambiente o predefinito)."""
    if fonte not in FONTI:
        raise KeyError(fonte)
    p = percorso or FILE
    with _BLOCCO:                                       # leggi-modifica-scrivi: due richieste insieme non si perdono a vicenda
        scelte = _scelte_admin(p)
        if acceso_ is None:
            scelte.pop(fonte, None)
        else:
            scelte[fonte] = bool(acceso_)
        scrivi_sicuro(p, json.dumps(scelte))
        try:
            os.chmod(p, 0o600)                          # solo il proprietario (su Windows non ha effetto)
        except OSError:
            pass
        _cache.pop(str(p), None)
