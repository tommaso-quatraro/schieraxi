"""Cartelle usate dal programma e scrittura sicura dei file."""
import contextlib
import logging
import os
import shutil
import sqlite3
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


def cartella_utenti() -> Path:
    """Dove stanno le cartelle degli utenti, una per account: `utenti/<numero dell'account>/`."""
    return cartella_account() / "utenti"


def utente_della_cartella(percorso: Path) -> int | None:
    """Il numero dell'account se `percorso` sta nella cartella di un utente (`utenti/<numero>/...`), altrimenti None.
    Il percorso si risolve prima («..» e collegamenti), e il numero deve essere scritto come lo scrive l'app («7», non «07»)."""
    try:
        parti = Path(percorso).resolve().relative_to(cartella_utenti().resolve()).parts
    except (OSError, ValueError, RuntimeError):
        return None
    if not parti or not (parti[0].isascii() and parti[0].isdecimal()) or str(int(parti[0])) != parti[0]:
        return None
    return int(parti[0])


def _segno(utente_id: int) -> Path:
    return cartella_account() / "cancellati" / str(int(utente_id))


def segna_cancellato(utente_id: int) -> bool:
    """Il segno di cancellazione di un account: un file vuoto `cancellati/<numero>` accanto al database degli account, fuori
    dalla cartella dell'utente (che sta per sparire). Lo scrive account.elimina subito dopo aver tolto l'account. Falso se non si scrive."""
    try:
        file = _segno(utente_id)
        cartella_privata(file.parent)
        os.close(os.open(file, os.O_WRONLY | os.O_CREAT, 0o600))
        return True
    except OSError:
        return False


def account_cancellato(utente_id: int) -> bool:
    """Vero se l'account è stato eliminato: c'è il suo segno e nel database degli account non c'è più un account con quel numero.
    Il database (in sola lettura) si guarda solo se il segno c'è: per gli altri utenti basta un controllo sul disco. Serve per un
    segno rimasto da prima di un ripristino del database, quando lo stesso numero può tornare a un account nuovo. Se il database
    non si legge, vale il segno."""
    if not _segno(utente_id).exists():
        return False
    file = cartella_account() / "account.sqlite"
    try:
        with contextlib.closing(sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True, timeout=5)) as db:
            return db.execute("SELECT 1 FROM utenti WHERE id = ?", (int(utente_id),)).fetchone() is None
    except sqlite3.Error:
        return True


def _togli_cartella_cancellata(utente_id: int, percorso: Path) -> None:
    """Una scrittura per un account eliminato: non si fa, e se la cartella dell'utente è rinata (scritture partite prima) si toglie.
    Quello che non si riesce a togliere lo trova `python -m fanta cartelle-senza-account`."""
    logging.getLogger(__name__).warning("Account %s eliminato: %s non salvato", utente_id, percorso.name)
    shutil.rmtree(cartella_utenti() / str(utente_id), ignore_errors=True)


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


def dentro(cartella: Path, percorso: Path) -> bool:
    """Vero se `percorso`, risolto (niente «..», collegamenti seguiti), sta sotto `cartella` e non è la cartella stessa.
    Da controllare prima di scrivere in un percorso costruito con un nome che viene dai dati. Un nome che il disco non accetta
    (carattere nullo, percorso non risolvibile) dà falso, uguale su Windows e su Linux."""
    if "\x00" in str(percorso):
        return False
    try:
        base, vero = cartella.resolve(), percorso.resolve()
    except (OSError, ValueError, RuntimeError):         # RuntimeError: giro di collegamenti (Python prima della 3.13)
        return False
    return vero != base and vero.is_relative_to(base)


def scrivi_sicuro(percorso: Path, testo: str) -> None:
    """Scrive su un file temporaneo e poi lo rinomina: se qualcosa va storto, il file vecchio resta intatto.
    Nella cartella di un account eliminato non scrive (anche se il lavoro era partito prima dell'eliminazione): il segno si guarda
    prima e di nuovo dopo, così la cartella non rinasce nemmeno se l'eliminazione arriva a metà scrittura."""
    utente = utente_della_cartella(percorso)
    if utente is not None and account_cancellato(utente):
        _togli_cartella_cancellata(utente, percorso)
        return
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_name(f"{percorso.name}.{uuid.uuid4().hex[:8]}.tmp")   # nome unico: salvataggi in parallelo
    try:
        tmp.write_text(testo, encoding="utf-8")
        os.replace(tmp, percorso)
    except BaseException:
        tmp.unlink(missing_ok=True)       # disco pieno o altro: niente file a metà che occupano altro spazio
        raise
    if utente is not None and account_cancellato(utente):      # eliminato mentre scrivevamo: si toglie quello che è rinato
        _togli_cartella_cancellata(utente, percorso)
