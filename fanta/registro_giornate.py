"""Registro delle giornate: i numeri MOSTRATI prima di ogni giornata, per tutta la Serie A, e quanto ci hanno preso (#165, L1).

Poco prima della prima partita della giornata (negli ultimi ANTICIPO minuti, come la copia alla scadenza) si salvano per ogni
giocatore della Serie A i numeri che l'app mostra: «gioca N%» (`p_voto`), fantavoto atteso (`mu`), voto atteso, gol e assist
attesi, minuti attesi e stato delle probabili formazioni, più la fantamedia di allora. Regole classiche (`Regole()`, come
`precisione.pubblico`), mai quelle di una lega; niente nomi né dati personali, solo id e numeri. Nessuna richiesta in più alle
fonti: sono le previsioni già calcolate (`consigli.previsioni`, in cache). Chi ha la partita già iniziata (un anticipo) non si salva.

Il registro sta nell'archivio (tabelle `registro_giocatori` e `registro_giornate`) e NON si ricostruisce: una giornata non salvata
è persa. Gira nel thread del pianificatore, una volta al minuto; `FANTA_REGISTRO_GIORNATE=0` lo spegne.
"""
from __future__ import annotations

import math
import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

from . import archivio, avvisi, consigli
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import Regole

ANTICIPO = timedelta(minutes=10)        # si salva negli ultimi 10 minuti prima della prima partita (dopo l'ultimo giro delle probabili)
REGOLE = Regole()                       # regole classiche: i numeri non dipendono da una lega
BONUS_E_MALUS = ("gol", "gol_subiti", "autogol", "rig_segnati", "rig_sbagliati", "rig_parati", "assist", "mvp", "ammonizioni",
                 "espulsioni")


def acceso() -> bool:
    """Interruttore (variabile d'ambiente, letta a ogni giro): `FANTA_REGISTRO_GIORNATE=0` lo spegne."""
    return os.environ.get("FANTA_REGISTRO_GIORNATE", "1").strip().lower() not in ("0", "no", "false", "off")


def _numero(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _testo(x) -> str | None:
    return x if isinstance(x, str) else None


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " "))
    except ValueError:
        return None


def _righe(cursore: sqlite3.Cursor) -> list[dict]:
    nomi = [c[0] for c in cursore.description]
    return [dict(zip(nomi, r)) for r in cursore.fetchall()]


def fantavoto_vero(riga: dict, ruolo: str, regole: Regole = REGOLE) -> float | None:
    """Il fantavoto di una riga della tabella `voti` (None = senza voto); i bonus mancanti valgono zero."""
    return fantavoto({**riga, **{k: riga.get(k) or 0 for k in BONUS_E_MALUS}}, ruolo, regole)


def fantamedie(db: sqlite3.Connection, stagione: str, giornata: int, regole: Regole = REGOLE) -> dict[int, float]:
    """{id: fantamedia} con le giornate della stagione PRIMA di `giornata` (chi non ha voti non c'è)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    somme: dict[int, list[float]] = {}
    for r in _righe(db.execute(f"SELECT * FROM voti WHERE stagione = ? AND giornata < ? AND {col} IS NOT NULL", (stagione, giornata))):
        fv = fantavoto_vero(r, r["ruolo"], regole)
        if fv is not None:
            somme.setdefault(int(r["calciatore_id"]), []).append(fv)
    return {i: round(sum(v) / len(v), 3) for i, v in somme.items()}


def _salvata(db: sqlite3.Connection, stagione: str, giornata: int) -> bool:
    return db.execute("SELECT 1 FROM registro_giornate WHERE stagione = ? AND giornata = ?", (stagione, giornata)).fetchone() is not None


def salva(db: sqlite3.Connection, stagione: str, giornata: int, prev: pd.DataFrame, con_probabili: bool, adesso: datetime) -> int:
    """Salva i numeri di `prev` (la tabella di `consigli.previsioni`, indice = id) per la giornata. Una volta sola: se la giornata c'è
    già restituisce 0 e non cambia niente. Salta chi non ha una partita e chi ha la partita già iniziata. Restituisce le righe scritte."""
    if _salvata(db, stagione, giornata):
        return 0
    fm = fantamedie(db, stagione, giornata)
    righe = []
    for cid, x in prev.iterrows():
        partita = _numero(x.get("partita"))
        inizio = _data(x.get("data_partita"))
        if partita is None or (inizio is not None and inizio <= adesso):
            continue
        percentuale = _numero(x.get("percentuale"))
        righe.append({"stagione": stagione, "giornata": int(giornata), "calciatore_id": int(cid), "ruolo": str(x.get("ruolo")),
                      "squadra": _testo(x.get("squadra")), "partita_id": int(partita), "p_voto": _numero(x.get("p_voto")),
                      "mu": _numero(x.get("mu")), "mu_voto": _numero(x.get("mu_voto")), "e_gol": _numero(x.get("e_gol")),
                      "e_assist": _numero(x.get("e_assist")), "minuti": _numero(x.get("minuti")),
                      "stato": _testo(x.get("stato")), "percentuale": percentuale,
                      "dubbio": 1 if x.get("dubbio") == 1 else 0, "fantamedia": fm.get(int(cid))})
    righe = [r for r in righe if r["p_voto"] is not None and r["mu"] is not None]
    if not righe:
        return 0                            # niente da salvare (previsioni vuote): si riprova al minuto dopo
    archivio.inserisci(db, "registro_giocatori", righe)
    db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, ?, ?)",
               (stagione, int(giornata), adesso.isoformat(timespec="seconds"), len(righe), int(bool(con_probabili))))
    db.commit()
    return len(righe)


def da_salvare(db: sqlite3.Connection, adesso: datetime) -> tuple[str, int] | None:
    """(stagione, giornata) da salvare adesso: negli ultimi ANTICIPO minuti prima della prima partita (esclusa), se non è già salvata."""
    stagione = consigli.stagione_corrente()
    g = consigli.prossima_giornata(db, stagione, adesso)
    if g is None:
        return None
    inizio = avvisi.prima_partita(db, stagione, g)
    if inizio is None or not inizio - ANTICIPO <= adesso < inizio or _salvata(db, stagione, g):
        return None
    return stagione, g


def salva_se_serve(db: sqlite3.Connection, adesso: datetime, previsioni=None) -> int:
    """Se è il momento, salva la giornata con le previsioni già calcolate (`previsioni(db, regole, giornata)`, come
    `consigli.previsioni`). Restituisce le righe scritte (0 = niente da fare)."""
    quale = da_salvare(db, adesso)
    if quale is None:
        return 0
    stagione, g = quale
    prev, giornata, con_probabili = (previsioni or consigli.previsioni)(db, REGOLE, g)
    if giornata != g:
        return 0
    return salva(db, stagione, g, prev, con_probabili, adesso)
