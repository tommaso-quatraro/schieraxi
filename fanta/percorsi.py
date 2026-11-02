"""Cartelle usate dal programma e scrittura sicura dei file."""
import os
import uuid
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent


def cartella_lega() -> Path:
    """Dove stanno regole.json e rose.json della lega. Chi decide, in ordine: 1) la variabile FANTA_LEGA (una cartella);
    2) `lega/`, se ci sono le regole di una lega vera (copia di lavoro di chi la usa: la cartella non va in git);
    3) `lega/esempio`, la lega inventata che sta nel repository."""
    v = os.environ.get("FANTA_LEGA", "").strip()
    if v:
        return Path(v)
    vera = RADICE / "lega"
    return vera if (vera / "regole.json").is_file() else vera / "esempio"


CARTELLA_LEGA = cartella_lega()          # regole.json e rose.json della lega in uso
CACHE = RADICE / "dati" / "cache"        # dati scaricati, si rigenerano


def cartella_account() -> Path:
    """Dove stanno account.sqlite e le cartelle degli utenti (solo con FANTA_MULTIUTENTE=1).
    Di norma è `dati/`; FANTA_DATI_UTENTI la sposta (per provare l'app su una cartella temporanea) senza toccare gli altri dati."""
    return Path(os.environ.get("FANTA_DATI_UTENTI") or RADICE / "dati")


def cartella_privata(cartella: Path) -> Path:
    """Crea la cartella (se manca) leggibile solo dall'utente del servizio (700). Una cartella che c'è già non si tocca."""
    cartella.mkdir(parents=True, exist_ok=True, mode=0o700)
    return cartella


def chiavi_vecchie(chiavi, tieni: int) -> list[str]:
    """Le chiavi "stagione/giornata" più vecchie, da togliere per tenerne `tieni`. Ordinate come numeri: la giornata 10 viene dopo la 9."""
    def ordine(k: str):
        stagione, _, giornata = str(k).rpartition("/")
        return (stagione, int(giornata) if giornata.isdigit() else 0)
    ordinate = sorted(chiavi, key=ordine)
    return ordinate[:-tieni] if tieni > 0 and len(ordinate) > tieni else []


def scrivi_sicuro(percorso: Path, testo: str) -> None:
    """Scrive su un file temporaneo e poi lo rinomina: se qualcosa va storto, il file vecchio resta intatto."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_name(f"{percorso.name}.{uuid.uuid4().hex[:8]}.tmp")   # nome unico: salvataggi in parallelo
    try:
        tmp.write_text(testo, encoding="utf-8")
        os.replace(tmp, percorso)
    except BaseException:
        tmp.unlink(missing_ok=True)       # disco pieno o altro: niente file a metà che occupano altro spazio
        raise
