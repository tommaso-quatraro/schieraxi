"""Passaggio di stagione: le rose del campionato appena finito si archiviano e l'app riparte da rose vuote (con gli stessi nomi di squadra).

Si fa da Lega quando l'app si accorge che le rose sono di una stagione precedente (da luglio, quando cambia la stagione).
Dopo si importa il nuovo Excel di Leghe come all'inizio. Niente si cancella: tutto resta in lega/archivio/<stagione>/.
"""
from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from . import lega
from .aggiorna import Stagione
from .percorsi import dentro


def stagione_delle_rose(rose: lega.Rose, file: Path) -> str:
    """La stagione a cui appartengono le rose: quella segnata all'importazione, altrimenti quella del file."""
    if rose.stagione:
        return rose.stagione
    try:
        return Stagione.di(date.fromtimestamp(file.stat().st_mtime)).codice
    except OSError:
        return ""


def stato(rose: lega.Rose | None, file: Path, corrente: str) -> dict:
    if not rose or not any(s.giocatori for s in rose.squadre):
        return {"corrente": corrente, "rose": None, "nuova": False}
    vecchia = stagione_delle_rose(rose, file)
    return {"corrente": corrente, "rose": vecchia, "nuova": bool(vecchia) and vecchia != corrente}


def archivia_e_riparti(rose: lega.Rose, file: Path, corrente: str, crediti_iniziali: int, da_spostare: list[Path] | None = None) -> dict:
    """Copia i file della stagione in `archivio/<stagione>/` accanto alle rose e riparte da rose vuote. La stagione deve essere un
    nome come «2026-27» e la cartella deve restare dentro `archivio/`: altrimenti ValueError, senza scrivere niente.
    La risposta dice il nome della stagione archiviata, non dove sta sul server."""
    vecchia = stagione_delle_rose(rose, file)
    if vecchia and not lega.stagione_valida(vecchia):
        raise ValueError(lega.FORMA_SBAGLIATA)
    vecchia = vecchia or "precedente"
    archivio = file.parent / "archivio"
    cartella = archivio / vecchia
    if not dentro(archivio, cartella):
        raise ValueError(lega.FORMA_SBAGLIATA)
    cartella.mkdir(parents=True, exist_ok=True)
    for nome in ("rose.json", "regole.json", "movimenti.json"):
        sorgente = file.parent / nome
        if sorgente.exists():
            shutil.copy2(sorgente, cartella / nome)
    for f in da_spostare or []:                       # scelte e osservati della stagione finita: restano nell'archivio
        if f.exists():
            shutil.copy2(f, cartella / f.name)
            f.unlink()
    nuove = lega.Rose([lega.Squadra(s.nome, [], crediti_iniziali) for s in rose.squadre], rose.mia_squadra, "", corrente)
    lega.salva(nuove, file)
    return {"archivio": vecchia, "squadre": len(nuove.squadre), "stagione": corrente}
