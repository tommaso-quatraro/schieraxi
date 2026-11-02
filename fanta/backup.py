"""Backup dei dati della lega in un file solo: regole, rose, movimenti, scelte, osservati e impostazioni degli avvisi.
Serve quando si cambia server o si vuole una copia al sicuro. Non contiene chiavi né iscrizioni alle notifiche
(restano dove sono): sul nuovo dispositivo si riattivano dall'app."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import lega, regole
from .percorsi import RADICE, scrivi_sicuro

FORMATO = "schieraxi-backup"
VERSIONE = 1
COPIA_PRIMA = Path("dati") / "backup-prima-del-ripristino.json"      # lo stato di prima, per tornare indietro
PREFISSO_FILE = "schieraxi-backup"         # nome del file che si scarica e della copia serale


def nome_file(creato: str) -> str:
    """Nome del file di backup per una data ISO (`creato`)."""
    return f"{PREFISSO_FILE}-{creato[:10]}.json"


def _lista_di_interi(d: Any) -> None:
    if not isinstance(d, list):
        raise ValueError("deve essere una lista")
    [int(i) for i in d]


def _dizionario(d: Any) -> None:
    if not isinstance(d, dict):
        raise ValueError("deve essere un elenco di voci")


def _lista_o_dizionario(d: Any) -> None:
    if not isinstance(d, (list, dict)):
        raise ValueError("formato non riconosciuto")


FILE_SCELTE_BACKUP = "dati/scelte.json"     # le formazioni scelte, una voce per «stagione/giornata»

# file salvati (percorso dentro il progetto) -> controllo del contenuto
CONTROLLI: dict[str, Callable[[Any], None]] = {
    "lega/regole.json": regole.da_dict,
    "lega/rose.json": lega.da_dict,
    "lega/movimenti.json": _lista_o_dizionario,
    "dati/scelte.json": _dizionario,
    "dati/osservati.json": _lista_di_interi,
    "dati/avvisi-impostazioni.json": _dizionario,
}


def _percorsi(radice: Path, file: dict[str, Path] | None) -> dict[str, Path]:
    """Dove sta ogni file del backup: sotto la radice (l'app di sempre) oppure nei percorsi indicati (la cartella di un utente)."""
    return file if file is not None else {nome: radice / nome for nome in CONTROLLI}


def crea(radice: Path = RADICE, file_utente: dict[str, Path] | None = None) -> dict:
    """Tutto quello che c'è, in un dizionario pronto per essere scritto come JSON."""
    file = {}
    for nome, percorso in _percorsi(radice, file_utente).items():
        try:
            file[nome] = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                                  # non c'è (ancora) o è rovinato: nel backup non finisce
    return {"formato": FORMATO, "versione": VERSIONE, "creato": datetime.now().isoformat(timespec="seconds"), "file": file}


def salva_copia(radice: Path = RADICE, cartella: Path | None = None, tieni: int = 7, file_utente: dict[str, Path] | None = None) -> Path | None:
    """Scrive la copia di oggi in dati/backup/ (una al giorno: se c'è già si sostituisce) e tiene solo le ultime `tieni`.
    Con `file_utente` (e `cartella`) è la copia di un utente con un account. Restituisce il file scritto, o None se non c'è niente da salvare."""
    b = crea(radice, file_utente)
    if not b["file"]:
        return None
    cartella = cartella or radice / "dati" / "backup"
    destinazione = cartella / nome_file(b["creato"])
    scrivi_sicuro(destinazione, json.dumps(b, ensure_ascii=False))
    # Si tengono le ultime `tieni` copie (ordine per data, non per nome).
    copie = sorted(cartella.glob(f"{PREFISSO_FILE}-*.json"), key=lambda p: (p.stem[-10:], p.name))
    for vecchia in copie[:-tieni]:
        vecchia.unlink(missing_ok=True)
    return destinazione


def copia_account(cartella: Path, origine: Path, tieni: int = 7) -> Path | None:
    """Con gli account: una copia del database degli utenti (account.sqlite) con l'API di backup di SQLite, che è sicura anche
    mentre il server lo usa. Una al giorno, ne tiene `tieni`. Contiene gli hash delle password: il file lo legge solo chi lo ha creato."""
    import sqlite3
    if not origine.exists():
        return None
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"account-{datetime.now():%Y-%m-%d}.sqlite"
    sorgente, copia = sqlite3.connect(origine), sqlite3.connect(destinazione)
    try:
        sorgente.backup(copia)
    finally:
        copia.close()
        sorgente.close()
    try:
        destinazione.chmod(0o600)
    except OSError:
        pass
    for vecchia in sorted(cartella.glob("account-*.sqlite"))[:-tieni]:
        vecchia.unlink(missing_ok=True)
    return destinazione


def controlla(backup: Any) -> dict[str, Any]:
    """Controlla il backup per intero senza toccare niente. Restituisce i file da ripristinare o alza ValueError."""
    if not isinstance(backup, dict) or backup.get("formato") != FORMATO:
        raise ValueError("Questo non è un backup di SchieraXI")
    if not isinstance(backup.get("versione"), int) or backup["versione"] > VERSIONE:
        raise ValueError("Il backup viene da una versione più nuova dell'app: aggiorna l'app e riprova")
    file = backup.get("file")
    if not isinstance(file, dict) or not file:
        raise ValueError("Il backup è vuoto")
    for nome, contenuto in file.items():
        if nome not in CONTROLLI:
            raise ValueError(f"Il backup contiene un file che non conosco: {str(nome)[:60]}")
        try:
            CONTROLLI[nome](contenuto)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):      # OverflowError: «Infinity» o 1e999 dove serve un intero
            raise ValueError(f"{nome} non è valido: controlla di aver scelto il file di backup giusto") from None
    return file


def ripristina(backup: Any, radice: Path = RADICE, file_utente: dict[str, Path] | None = None, copia_prima: Path | None = None,
               chiusa: Callable[[str], bool] | None = None) -> list[str]:
    """Rimette i dati del backup (i nomi dei file ripristinati). Vedi `ripristina_esito`."""
    return ripristina_esito(backup, radice, file_utente, copia_prima, chiusa)["ripristinati"]


def ripristina_esito(backup: Any, radice: Path = RADICE, file_utente: dict[str, Path] | None = None, copia_prima: Path | None = None,
                     chiusa: Callable[[str], bool] | None = None) -> dict:
    """Rimette i dati del backup. Prima controlla tutto: se qualcosa non va non cambia niente. I file che il backup
    non ha restano com'erano. Lo stato di prima si salva in dati/backup-prima-del-ripristino.json.
    `chiusa(chiave)` dice se la giornata di una voce di `scelte` («stagione/giornata») è già chiusa: quelle voci restano come sono
    sul server (un backup non deve aggirare la scadenza). Restituisce {ripristinati, scelte_chiuse_tenute: vero se il backup
    avrebbe cambiato almeno una formazione di una giornata chiusa}."""
    file = controlla(backup)
    dove = _percorsi(radice, file_utente)
    scrivi_sicuro(copia_prima or radice / COPIA_PRIMA, json.dumps(crea(radice, file_utente), ensure_ascii=False))
    tenute = False
    if chiusa is not None and FILE_SCELTE_BACKUP in file:
        try:
            attuali = json.loads(dove[FILE_SCELTE_BACKUP].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            attuali = {}
        file = dict(file)
        file[FILE_SCELTE_BACKUP], tenute = unisci_scelte(file[FILE_SCELTE_BACKUP], attuali if isinstance(attuali, dict) else {}, chiusa)
    for nome, contenuto in file.items():
        scrivi_sicuro(dove[nome], json.dumps(contenuto, ensure_ascii=False, indent=2))
    return {"ripristinati": sorted(file), "scelte_chiuse_tenute": tenute}


def unisci_scelte(nuove: dict, attuali: dict, chiusa: Callable[[str], bool]) -> tuple[dict, bool]:
    """Le scelte da scrivere: quelle del backup per le giornate ancora aperte, quelle del server (o nessuna) per le giornate chiuse.
    Il secondo valore è vero se il backup ne avrebbe cambiata almeno una chiusa."""
    chiuse = {k for k in set(nuove) | set(attuali) if chiusa(str(k))}
    unite = {k: v for k, v in nuove.items() if k not in chiuse} | {k: v for k, v in attuali.items() if k in chiuse}
    return unite, any(nuove.get(k) != attuali.get(k) for k in chiuse)
