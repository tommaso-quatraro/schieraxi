"""Copia dell'archivio delle statistiche per l'ambiente di prova (script/server/prova/LEGGIMI.md). Si usa due volte:
- con l'utente della PRODUZIONE (esporta-archivio-prova.sh): ~/fantacalcio/dati/fanta.sqlite -> /srv/schieraxi-scambio/fanta.sqlite;
- con l'utente della PROVA (copia-archivio-prova.sh): /srv/schieraxi-scambio/fanta.sqlite -> ~/app/dati/fanta.sqlite.
Così la prova non ha nessun permesso sui file della produzione: legge solo la copia nella cartella di scambio.

Uso:  python copia_archivio.py ORIGINE DESTINAZIONE

Cosa fa, in ordine:
1. rifiuta i collegamenti simbolici al posto della destinazione, dei suoi file di appoggio (-wal, -shm, -journal) e della sua cartella:
   la cartella dati della prova la scrive anche il suo servizio, e chi lancia la copia (fuori dal recinto del servizio) non deve
   farsi portare a scrivere da un'altra parte;
2. apre l'origine in SOLA LETTURA (mode=ro: non la cambia mai) e ne fa una copia coerente con l'API di backup di sqlite in un file di
   lavoro nuovo accanto alla destinazione (`<nome>.nuovo`, creato con O_EXCL e O_NOFOLLOW), anche con il servizio acceso.
   Come a ogni apertura di un archivio WAL, sqlite usa i file di appoggio `-wal` e `-shm` accanto all'origine: con il servizio acceso
   ci sono già; se nessuno la tiene aperta li crea vuoti e li lascia lì (innocui: li riusa chiunque la apra dopo);
3. nella copia svuota la tabella `controlli` (esiti della sentinella: parlano degli utenti veri; il resto sono dati di calcio
   pubblici), la toglie dal modo WAL (la copia nella cartella di scambio si legge da una cartella in cui la prova non può scrivere)
   e la controlla (`PRAGMA quick_check`);
4. la scrive sopra la destinazione in UNA transazione di sqlite (di nuovo l'API di backup): o tutto o niente, e chi legge la
   destinazione in quel momento vede quella vecchia fino alla fine, poi quella nuova. Non si rinomina un file nuovo sopra la
   destinazione: l'archivio della prova è aperto in modo WAL, e un file nuovo accanto al `-wal` del vecchio sarebbe rovinato.
Se qualcosa non va la destinazione resta com'era, il file di lavoro si toglie, esce con 1 e una riga sull'errore.
Solo libreria standard: gira con qualunque Python 3 del server, senza l'app.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

TABELLE_DA_SVUOTARE = ("controlli",)          # esiti della sentinella: dicono «utente N», non vanno nella prova
ATTESA = 60                                   # secondi: se qualcuno sta scrivendo nella destinazione, si aspetta
APPOGGIO = ("-wal", "-shm", "-journal")       # i file che sqlite tiene accanto a un archivio


class CopiaNonRiuscita(Exception):
    """La copia non è andata: la destinazione è rimasta com'era. Il messaggio dice perché, in una riga."""


def _sola_lettura(percorso: Path) -> sqlite3.Connection:
    if not percorso.is_file():
        raise CopiaNonRiuscita(f"manca l'archivio da copiare: {percorso}")
    return sqlite3.connect(f"{percorso.resolve().as_uri()}?mode=ro", uri=True, timeout=ATTESA)


def _rifiuta_collegamenti(destinazione: Path) -> None:
    for p in (destinazione.parent, destinazione, *(Path(f"{destinazione}{s}") for s in APPOGGIO)):
        if os.path.islink(p):
            raise CopiaNonRiuscita(f"{p} è un collegamento simbolico: non scrivo")


def _togli_lavoro(lavoro: Path) -> None:
    """Il file di lavoro (e i suoi file di appoggio) sta nella cartella della destinazione ed è solo nostro. Se al suo posto c'è un
    collegamento simbolico, si toglie il collegamento, non il file a cui punta."""
    for suffisso in ("", *APPOGGIO):
        try:
            os.remove(f"{lavoro}{suffisso}")
        except FileNotFoundError:
            pass


def _crea_lavoro(lavoro: Path) -> None:
    """File di lavoro nuovo e vuoto (sqlite lo prende per un archivio vuoto): O_EXCL non segue i collegamenti e non riusa niente."""
    fd = os.open(lavoro, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(fd)


def copia(origine: Path, destinazione: Path) -> int:
    """Copia `origine` in `destinazione` senza gli esiti della sentinella. Restituisce quante righe di `controlli` ha tolto.
    Alza CopiaNonRiuscita (destinazione invariata) se qualcosa non va."""
    origine, destinazione = Path(origine), Path(destinazione)
    _rifiuta_collegamenti(destinazione)
    if origine.resolve() == destinazione.resolve():
        raise CopiaNonRiuscita("origine e destinazione sono lo stesso file")
    lavoro = destinazione.with_name(destinazione.name + ".nuovo")
    sorgente = copia_lavoro = arrivo = None
    try:
        _togli_lavoro(lavoro)                   # resto di un giro interrotto (o un collegamento messo lì)
        _crea_lavoro(lavoro)
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
        copia_lavoro.execute("PRAGMA journal_mode = DELETE")
        esito = copia_lavoro.execute("PRAGMA quick_check").fetchone()[0]
        if esito != "ok":
            raise CopiaNonRiuscita(f"la copia non è sana: {esito}")
        _rifiuta_collegamenti(destinazione)     # di nuovo subito prima di scrivere
        arrivo = sqlite3.connect(destinazione, timeout=ATTESA)
        copia_lavoro.backup(arrivo)             # una sola transazione: chi legge vede il vecchio archivio o il nuovo, mai metà
        try:
            arrivo.execute("PRAGMA wal_checkpoint(TRUNCATE)")      # se la destinazione è in WAL, il -wal non resta grande come lei
        except sqlite3.Error:
            pass
        return tolti
    except sqlite3.Error as e:
        raise CopiaNonRiuscita(f"sqlite: {e}") from e
    except OSError as e:
        raise CopiaNonRiuscita(f"file di lavoro: {e}") from e
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
        print(f"archivio NON aggiornato (resta quello di prima): {e}", file=sys.stderr)
        return 1
    print(f"archivio aggiornato da {origine} ({tolti} esiti della sentinella tolti)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
