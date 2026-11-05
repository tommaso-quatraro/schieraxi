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

import numpy as np
import pandas as pd

from . import archivio, avvisi, consigli, fasi, incertezza
from . import formazione as fz
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import Regole

ANTICIPO = timedelta(minutes=10)        # si salva negli ultimi 10 minuti prima della prima partita (dopo l'ultimo giro delle probabili)
REGOLE = Regole()                       # regole classiche: i numeri non dipendono da una lega
DOPO_FINE = timedelta(hours=24)         # a turno finito si misura un giorno dopo: i voti hanno il tempo di assestarsi
ATTESA_VOTI = timedelta(hours=72)       # oltre, si misura anche se a qualche partita mancano i voti (quelle partite non contano)
FASCE = 10                              # fasce di 10 punti di «gioca N%» per l'errore di calibrazione
FANTAMEDIA_SENZA_VOTI = 6.0             # come nella verifica: chi non ha ancora voti ha fantamedia 6
# Fascia «8 volte su 10» (I3): come `verifica --incertezza`, su rose estratte a sorte (seme fisso) tra chi ha una probabilità vera di
# giocare; per ogni rosa la formazione migliore con i numeri MOSTRATI, la sua fascia e i punti veri.
ROSE_SINTETICHE = 20
SIMULAZIONI = 300
POSTI_ROSA = {"P": 3, "D": 8, "C": 8, "A": 6}
P_MINIMA_ROSA = 0.3
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


# ---------------------------------------------------------------- misura a giornata finita
def _partite(db: sqlite3.Connection, stagione: str, giornata: int) -> tuple[set[int], set[int]]:
    """(partite del registro giocate con i voti di tutte e due le squadre, partite del registro giocate ma ancora senza voti)."""
    col = COLONNA_VOTO[REGOLE.fonte_voto]
    con_voti = {r[0] for r in db.execute(f"SELECT DISTINCT squadra FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL",
                                         (stagione, giornata))}
    valide: set[int] = set()
    senza: set[int] = set()
    for pid, casa, trasferta in db.execute(
            "SELECT id, casa, trasferta FROM partite WHERE stagione = ? AND giocata = 1 AND id IN "
            "(SELECT DISTINCT partita_id FROM registro_giocatori WHERE stagione = ? AND giornata = ?)", (stagione, stagione, giornata)):
        (valide if casa in con_voti and trasferta in con_voti else senza).add(int(pid))
    return valide, senza


def da_misurare(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Le giornate salvate e non ancora misurate che sono finite: turno giocato (`fasi.fine_giornata`, le rinviate non lo tengono
    aperto) da almeno DOPO_FINE e voti di ogni partita giocata, oppure da almeno ATTESA_VOTI anche senza tutti i voti."""
    pronte = []
    for stagione, g in db.execute("SELECT stagione, giornata FROM registro_giornate WHERE misurato IS NULL "
                                  "ORDER BY stagione, giornata").fetchall():
        fine = fasi.fine_giornata(db, stagione, g)
        if fine is None or adesso < fine + DOPO_FINE:
            continue
        if _partite(db, stagione, g)[1] and adesso < fine + ATTESA_VOTI:
            continue
        pronte.append((stagione, int(g)))
    return pronte


def _fascia(registro: list[dict], fv: dict[int, float], voto: dict[int, float], stagione: str, giornata: int) -> tuple[int, int]:
    """(rose provate, rose con i punti veri dentro la fascia 8 volte su 10). Zero rose se i giocatori non bastano."""
    rng = np.random.default_rng(1000 * giornata + int(stagione[:4]))
    per_id = {int(r["calciatore_id"]): r for r in registro}
    pool = {ruolo: np.array(sorted(i for i, r in per_id.items() if r["ruolo"] == ruolo and r["p_voto"] >= P_MINIMA_ROSA))
            for ruolo in POSTI_ROSA}
    if any(len(pool[r]) < n for r, n in POSTI_ROSA.items()):
        return 0, 0
    casi = dentro = 0
    for _ in range(ROSE_SINTETICHE):
        ids = [int(i) for r, n in POSTI_ROSA.items() for i in rng.choice(pool[r], n, replace=False)]
        rosa = [fz.Giocatore(i, "", per_id[i]["ruolo"], float(per_id[i]["p_voto"]), float(per_id[i]["mu"]),
                             float(per_id[i]["mu_voto"] if per_id[i]["mu_voto"] is not None else 6.0)) for i in ids]
        try:
            f = fz.migliore(rosa, REGOLE, SIMULAZIONI)
        except ValueError:
            continue
        reale = fz.punteggio(f.titolari, f.panchina, {i: i in fv for i in ids}, {i: fv.get(i, 0.0) for i in ids},
                             {i: voto.get(i, 0.0) for i in ids}, REGOLE)
        fascia = incertezza.intervallo(f.atteso, f.dev)
        casi += 1
        dentro += int(fascia["basso"] <= reale <= fascia["alto"])
    return casi, dentro


def misura_giornata(db: sqlite3.Connection, stagione: str, giornata: int) -> dict | None:
    """I pezzi delle misure di una giornata finita, solo per le partite giocate e con i voti (None se non ce n'è):
    I1 `voti`, `sq_modello`, `sq_fantamedia` (somme dei quadrati degli errori di chi ha preso voto);
    I2 `presenze`, `brier_somma`, `fasce` (per fascia di «gioca N%»: [giocatori, somma del detto, quanti hanno preso voto]);
    I3 `fascia_casi`, `fascia_dentro`. Si sommano poi sulla finestra (`medie`)."""
    valide, _ = _partite(db, stagione, giornata)
    registro = [r for r in _righe(db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = ? ORDER BY calciatore_id",
                                             (stagione, giornata))) if r["partita_id"] in valide]
    if not registro:
        return None
    col = COLONNA_VOTO[REGOLE.fonte_voto]
    righe_voti = {int(v["calciatore_id"]): v for v in _righe(db.execute(
        f"SELECT * FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL", (stagione, giornata)))}
    fv: dict[int, float] = {}
    voto: dict[int, float] = {}
    for r in registro:
        i = int(r["calciatore_id"])
        if i in righe_voti and (f := fantavoto_vero(righe_voti[i], r["ruolo"])) is not None:
            fv[i], voto[i] = f, float(righe_voti[i][col])
    sq_m = sq_f = brier = 0.0
    fasce = [[0, 0.0, 0] for _ in range(FASCE)]
    for r in registro:
        i, p = int(r["calciatore_id"]), float(r["p_voto"])
        preso = i in fv
        if preso:
            fm = r["fantamedia"] if r["fantamedia"] is not None else FANTAMEDIA_SENZA_VOTI
            sq_m += (r["mu"] - fv[i]) ** 2
            sq_f += (fm - fv[i]) ** 2
        brier += (p - preso) ** 2
        b = min(FASCE - 1, max(0, math.floor(p * FASCE + 1e-9)))
        fasce[b][0] += 1
        fasce[b][1] += p
        fasce[b][2] += int(preso)
    casi, dentro = _fascia(registro, fv, voto, stagione, giornata)
    return {"voti": len(fv), "sq_modello": round(sq_m, 4), "sq_fantamedia": round(sq_f, 4), "presenze": len(registro),
            "brier_somma": round(brier, 4), "fasce": [[n, round(s, 4), g] for n, s, g in fasce],
            "fascia_casi": casi, "fascia_dentro": dentro}
