"""Un interruttore per ogni fonte di dati esterna (Fantacalcio.it, Understat, football-data, ESPN, foto).

Chi decide, in ordine: 1) la scelta dell'amministratore (file dati/fonti.json, cambiabile dall'app, `true`/`false` o `1`/`0`; se è
scritto male vale come assente, con una riga nel registro: vedi `interruttori.py`); 2) la variabile d'ambiente
FANTA_FONTE_<NOME> ("1" acceso, "0" spento); 3) il predefinito. Il predefinito è SPENTO (chi scarica il codice non contatta siti di terzi senza una scelta);
chi gestisce un server lo accende con FANTA_FONTI_PREDEFINITO=1 (tutte le fonti tranne le foto).
Le foto sono sempre spente salvo scelta esplicita. Restano validi i vecchi FANTA_LIVE=0 (ESPN) e FANTA_FOTO=1 (foto).
Le fonti spente non vengono mai contattate: l'app lavora coi dati già in archivio e con quelli inseriti dall'utente.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from . import frasi, interruttori
from .percorsi import RADICE

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
    "foto": ("Foto dei giocatori", "foto al posto dei volti illustrati", True),
}


_SCELTE = interruttori.FileScelte(FONTI)


def disponibile(fonte: str) -> bool:
    """Le foto dei giocatori esistono solo nelle copie private (modulo `fanta/foto.py`, docs/AVATAR-DIRITTI.md): senza il modulo
    la loro riga non si mostra in «Stato dei dati», perché il suo interruttore non farebbe niente."""
    return fonte != "foto" or importlib.util.find_spec(f"{__package__}.foto") is not None


def _scelte_admin(percorso: Path | None = None) -> dict[str, bool]:
    """Le scelte dell'amministratore (`interruttori.FileScelte`: cache, `1`/`0`, avviso nel registro se il file è scritto male)."""
    return _SCELTE.leggi(percorso or FILE) or {}


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


def cosa_manca(fonte: str) -> frasi.Frase:
    """Per la riga di una fonte spenta in «Stato dei dati» (#894): solo cosa non arriva, frase del catalogo `fonte.spenta_<id>`
    (fanta/frasi.py). Il nome e «spenta» sono già sulla riga, e la frase comune (dati già salvati, condizioni d'uso) la pagina la
    scrive una volta sola sotto l'elenco."""
    if fonte not in FONTI:
        raise KeyError(fonte)
    return frasi.F(f"fonte.spenta_{fonte}")


def richiedi(fonte: str) -> None:
    """Alza FonteSpenta (con un messaggio chiaro) se la fonte non va contattata."""
    if not acceso(fonte):
        raise FonteSpenta(messaggio_spenta(fonte))


# Le fonti con un nome comune, che si traduce (`nome_frase`, #949); le altre hanno un nome proprio («Understat») e restano com'è
NOMI_TRADUCIBILI = {"foto": "fonte.nome_foto"}


def stato(percorso: Path | None = None) -> list[dict]:
    """Per «Stato dei dati»: una riga per fonte (non quella delle foto dove non c'è il loro modulo, vedi `disponibile`)."""
    righe = []
    for k, (nome, serve, _) in FONTI.items():
        if not disponibile(k):
            continue
        on, da = origine(k, percorso)
        manca = None if on else cosa_manca(k)
        righe.append({"id": k, "nome": nome, "nome_frase": frasi.di(frasi.F(NOMI_TRADUCIBILI[k])) if k in NOMI_TRADUCIBILI else None,
                      "serve": serve, "acceso": on, "scelta_da": da,
                      "messaggio": str(manca) if manca else None, "messaggio_frase": frasi.di(manca)})
    return righe


def imposta(fonte: str, acceso_: bool | None, percorso: Path | None = None) -> None:
    """Scelta dell'amministratore; None la toglie (torna ambiente o predefinito). Con il file scritto male alza
    `interruttori.FileIlleggibile` e non lo tocca."""
    if fonte not in FONTI:
        raise KeyError(fonte)
    _SCELTE.imposta(percorso or FILE, fonte, acceso_)
