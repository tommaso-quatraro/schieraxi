"""Copia dell'archivio delle statistiche della produzione nell'ambiente di prova (script/server/prova/LEGGIMI.md).

Uso:  python copia_archivio.py ORIGINE DESTINAZIONE
      (ORIGINE: ~/fantacalcio/dati/fanta.sqlite della produzione; DESTINAZIONE: ~/schieraxi-prova/dati/fanta.sqlite)

Cosa fa, in ordine:
1. apre l'archivio della produzione in SOLA LETTURA (mode=ro: non lo cambia mai, nemmeno a fine lettura) e ne fa una copia coerente con
   l'API di backup di sqlite in un file di lavoro accanto alla destinazione (`fanta.sqlite.nuovo`), anche con il servizio acceso.
   Come a ogni apertura di un archivio WAL, sqlite usa i file di appoggio `-wal` e `-shm` accanto all'archivio: con il servizio acceso
   ci sono già; se nessuno lo tiene aperto li crea vuoti e li lascia lì (innocui: li riusa chiunque apra l'archivio dopo);
2. nella copia svuota la tabella `controlli`: sono gli esiti della sentinella e parlano degli utenti veri. Il resto sono dati di calcio
   pubblici (calendario, voti, statistiche, probabili, numeri mostrati);
3. controlla la copia (`PRAGMA quick_check`);
4. la scrive sopra l'archivio della prova in UNA transazione di sqlite (di nuovo l'API di backup): o tutto o niente, e chi legge
   l'archivio della prova in quel momento vede quello vecchio fino alla fine, poi quello nuovo.
Non si rinomina il file sopra quello della prova: la prova tiene l'archivio aperto in modo WAL, e un file nuovo con accanto il
`-wal` di quello vecchio sarebbe un archivio rovinato.
Se qualcosa non va la destinazione resta com'era, il file di lavoro si toglie, esce con 1 e una riga sull'errore.
Solo libreria standard: gira con qualunque Python 3 del server, senza l'app.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

TABELLE_DA_SVUOTARE = ("controlli",)          # esiti della sentinella: dicono «utente N», non vanno nella prova
ATTESA = 60                                   # secondi: se la prova sta scrivendo nel suo archivio, si aspetta


class CopiaNonRiuscita(Exception):
    """La copia non è andata: la destinazione è rimasta com'era. Il messaggio dice perché, in una riga."""


def _sola_lettura(percorso: Path) -> sqlite3.Connection:
    if not percorso.is_file():
        raise CopiaNonRiuscita(f"manca l'archivio della produzione: {percorso}")
    return sqlite3.connect(f"{percorso.resolve().as_uri()}?mode=ro", uri=True, timeout=ATTESA)


def _togli_lavoro(lavoro: Path) -> None:
    """Il file di lavoro (e i suoi -wal, -shm, -journal) sta nella cartella della prova ed è solo nostro."""
    for suffisso in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(f"{lavoro}{suffisso}")
        except FileNotFoundError:
            pass


def copia(origine: Path, destinazione: Path) -> int:
    """Copia `origine` in `destinazione` senza gli esiti della sentinella. Restituisce quante righe di `controlli` ha tolto.
    Alza CopiaNonRiuscita (destinazione invariata) se qualcosa non va."""
    origine, destinazione = Path(origine), Path(destinazione)
    if origine.resolve() == destinazione.resolve():
        raise CopiaNonRiuscita("origine e destinazione sono lo stesso file")
    lavoro = destinazione.with_name(destinazione.name + ".nuovo")
    _togli_lavoro(lavoro)                       # resto di un giro interrotto
    sorgente = copia_lavoro = arrivo = None
    try:
        sorgente = _sola_lettura(origine)
        copia_lavoro = sqlite3.connect(lavoro, timeout=ATTESA)
        sorgente.backup(copia_lavoro)
        sorgente.close()
        sorgente = None
        tabelle = {r[0] for r in copia_lavoro.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        tolti = 0
        for tabella in TABELLE_DA_SVUOTARE:
            if tabella in tabelle:
                tolti += copia_lavoro.execute(f'DELETE FROM "{tabella}"').rowcount
        copia_lavoro.commit()
        esito = copia_lavoro.execute("PRAGMA quick_check").fetchone()[0]
        if esito != "ok":
            raise CopiaNonRiuscita(f"la copia non è sana: {esito}")
        arrivo = sqlite3.connect(destinazione, timeout=ATTESA)
        copia_lavoro.backup(arrivo)             # una sola transazione: la prova vede il vecchio archivio o il nuovo, mai metà
        try:
            arrivo.execute("PRAGMA wal_checkpoint(TRUNCATE)")      # il -wal della prova non resta grande come l'archivio
        except sqlite3.Error:
            pass
        return tolti
    except sqlite3.Error as e:
        raise CopiaNonRiuscita(f"sqlite: {e}") from e
    finally:
        for c in (sorgente, copia_lavoro, arrivo):
            if c is not None:
                c.close()
        _togli_lavoro(lavoro)


def main(argomenti: list[str]) -> int:
    if len(argomenti) != 2:
        print("uso: python copia_archivio.py ORIGINE DESTINAZIONE", file=sys.stderr)
        return 2
    origine, destinazione = Path(argomenti[0]), Path(argomenti[1])
    try:
        tolti = copia(origine, destinazione)
    except CopiaNonRiuscita as e:
        print(f"archivio della prova NON aggiornato (resta quello di prima): {e}", file=sys.stderr)
        return 1
    print(f"archivio della prova aggiornato da {origine} ({tolti} esiti della sentinella tolti)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
