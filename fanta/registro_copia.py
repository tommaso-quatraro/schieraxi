"""Copia del registro delle giornate (#343): esporta in un file JSON piccolo le sole tabelle `registro_*` dell'archivio e le rimette.

Il registro (`registro_giornate.py`) sta in `dati/fanta.sqlite` ma, a differenza del resto dell'archivio, NON si ricostruisce con
`aggiorna`: per questo la copia notturna (`script/server/backup-dati.sh`) lo esporta a parte in `dati/registro-giornate.json`.
Perché un file a sé e non l'archivio intero: le statistiche si riscaricano, la copia resta piccola e il ripristino rimette solo
il registro, senza toccare il resto. L'esportazione apre l'archivio in sola lettura e legge le due tabelle nella stessa
transazione: anche con il servizio acceso prende i dati confermati (pure quelli ancora nel file -wal) e mai una scrittura a metà.
L'importazione aggiunge solo le righe che mancano (quelle che ci sono già restano com'erano: si può ripetere) e tutto o niente.

Solo libreria standard: la copia notturna lo lancia con il Python di sistema, senza le librerie dell'app.
  python3 -m fanta.registro_copia esporta [--archivio dati/fanta.sqlite] FILE
  python3 -m fanta.registro_copia importa [--archivio dati/fanta.sqlite] FILE
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
from pathlib import Path

from . import archivio
from .percorsi import scrivi_sicuro

TABELLE = ("registro_giornate", "registro_giocatori")     # le sole tabelle che viaggiano (nomi fissi: mai presi dal file)
FORMATO = 1
TETTO = 100 * 1024 * 1024                                 # una stagione intera sono pochi MB


def esporta(file_archivio: Path, file: Path) -> dict[str, int]:
    """Scrive in `file` le tabelle del registro di `file_archivio` (senza mai scriverci). Restituisce le righe per tabella;
    un archivio di prima del registro dà un file senza tabelle."""
    file_archivio = Path(file_archivio)
    if not file_archivio.is_file():
        raise ValueError(f"non trovo l'archivio {file_archivio}")
    tabelle = {}
    try:
        db = sqlite3.connect(file_archivio.resolve().as_uri() + "?mode=ro", uri=True, timeout=30, isolation_level=None)
    except sqlite3.Error as e:
        raise ValueError(f"non riesco ad aprire l'archivio: {e}") from e
    try:
        db.execute("PRAGMA busy_timeout = 30000")
        db.execute("BEGIN")                               # una sola lettura coerente per tutte e due le tabelle
        presenti = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for tabella in TABELLE:
            if tabella not in presenti:
                continue
            chiave = [r[1] for r in sorted(db.execute(f"PRAGMA table_info({tabella})"), key=lambda r: r[5]) if r[5]]
            cur = db.execute(f"SELECT * FROM {tabella} ORDER BY {', '.join(_nome(c) for c in chiave) or 'rowid'}")
            tabelle[tabella] = {"colonne": [c[0] for c in cur.description], "righe": [list(r) for r in cur]}
        db.execute("ROLLBACK")
    except sqlite3.Error as e:
        raise ValueError(f"non riesco a leggere il registro delle giornate dall'archivio: {e}") from e
    finally:
        db.close()
    scrivi_sicuro(Path(file), json.dumps({"formato": FORMATO, "tabelle": tabelle}, ensure_ascii=False, separators=(",", ":")))
    return {t: len(v["righe"]) for t, v in tabelle.items()}


def importa(file: Path, file_archivio: Path = archivio.FILE) -> dict[str, tuple[int, int]]:
    """Rimette in `file_archivio` (lo crea se manca) il registro salvato in `file`: {tabella: (righe nuove, righe che c'erano già)}.
    Le righe già presenti restano com'erano. Un file non valido non scrive niente (ValueError)."""
    dati = _leggi(Path(file))
    with contextlib.closing(archivio.apri(Path(file_archivio))) as db:
        lavoro = []
        for tabella in TABELLE:
            if tabella in dati:
                colonne = {r[1]: r[5] for r in db.execute(f"PRAGMA table_info({tabella})")}
                lavoro.append((tabella, *_controlla(tabella, dati[tabella], colonne)))
        esito = {}
        with db:                                          # tutto o niente
            for tabella, colonne, righe in lavoro:
                sql = (f"INSERT OR IGNORE INTO {tabella} ({', '.join(_nome(c) for c in colonne)}) "
                       f"VALUES ({', '.join('?' * len(colonne))})")
                nuove = db.executemany(sql, righe).rowcount if righe else 0
                esito[tabella] = (nuove, len(righe) - nuove)
    return esito


def _nome(colonna: str) -> str:
    return '"' + colonna.replace('"', '""') + '"'


def _leggi(file: Path) -> dict:
    """Le tabelle del file, con la forma controllata (le colonne si controllano poi sull'archivio)."""
    try:
        if file.stat().st_size > TETTO:
            raise ValueError(f"il file {file} è troppo grande per essere una copia del registro")
        dati = json.loads(file.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"non riesco a leggere il file {file}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"il file {file} non è una copia del registro delle giornate") from e
    if not isinstance(dati, dict) or dati.get("formato") != FORMATO or not isinstance(dati.get("tabelle"), dict):
        raise ValueError(f"il file {file} non è una copia del registro delle giornate (o è di una versione che non conosco)")
    estranee = set(dati["tabelle"]) - set(TABELLE)
    if estranee:
        raise ValueError(f"il file contiene tabelle che non sono del registro: {', '.join(sorted(estranee))}")
    for tabella, blocco in dati["tabelle"].items():
        if not isinstance(blocco, dict) or not isinstance(blocco.get("colonne"), list) or not isinstance(blocco.get("righe"), list):
            raise ValueError(f"tabella {tabella}: servono «colonne» e «righe»")
    return dati["tabelle"]


def _controlla(tabella: str, blocco: dict, colonne_archivio: dict[str, int]) -> tuple[list[str], list[list]]:
    """Colonne note all'archivio, senza doppioni, con tutta la chiave; righe della lunghezza giusta con valori semplici."""
    colonne, righe = blocco["colonne"], blocco["righe"]
    if not all(isinstance(c, str) for c in colonne) or len(set(colonne)) != len(colonne):
        raise ValueError(f"tabella {tabella}: colonne non valide")
    sconosciute = [c for c in colonne if c not in colonne_archivio]
    if sconosciute:
        raise ValueError(f"tabella {tabella}: colonne che l'archivio non ha: {', '.join(sconosciute)}")
    manca = [c for c, chiave in colonne_archivio.items() if chiave and c not in colonne]
    if manca:
        raise ValueError(f"tabella {tabella}: mancano le colonne della chiave: {', '.join(manca)}")
    for riga in righe:
        if not isinstance(riga, list) or len(riga) != len(colonne):
            raise ValueError(f"tabella {tabella}: una riga non ha {len(colonne)} valori")
        if not all(v is None or (isinstance(v, (int, float, str)) and not isinstance(v, bool)) for v in riga):
            raise ValueError(f"tabella {tabella}: una riga ha un valore che non è un numero né un testo")
    return colonne, righe


def main(argv: list[str] | None = None) -> int:
    for flusso in (sys.stdout, sys.stderr):
        flusso.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="python -m fanta.registro_copia",
                                description="Copia del registro delle giornate: esporta in un file JSON o lo rimette nell'archivio")
    p.add_argument("azione", choices=("esporta", "importa"))
    p.add_argument("file", type=Path, help="file della copia (per esempio dati/registro-giornate.json)")
    p.add_argument("--archivio", type=Path, default=archivio.FILE, help="archivio (di norma dati/fanta.sqlite)")
    a = p.parse_args(argv)
    try:
        if a.azione == "esporta":
            n = esporta(a.archivio, a.file)
            print(f"Registro esportato in {a.file}: {n.get('registro_giornate', 0)} giornate, "
                  f"{n.get('registro_giocatori', 0)} righe di giocatori.")
        else:
            esito = importa(a.file, a.archivio)
            giornate, giocatori = esito.get("registro_giornate", (0, 0)), esito.get("registro_giocatori", (0, 0))
            print(f"Registro rimesso in {a.archivio}: {giornate[0]} giornate e {giocatori[0]} righe di giocatori nuove; "
                  f"{giornate[1] + giocatori[1]} righe c'erano già e sono rimaste com'erano.")
    except (ValueError, OSError, sqlite3.Error) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
