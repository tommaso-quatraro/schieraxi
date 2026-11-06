"""Taratura di «gioca N%» con le probabili formazioni (#379, L2 di #165): misura sul server se le costanti scelte a mano di
`modello._p_da_probabili` si possono ritarare sulle giornate già giocate.

Legge SOLO il registro delle giornate (`registro_giocatori`, `registro_giornate.py`): le probabili salvate poco prima della prima
partita, cioè quelle che l'utente aveva davanti quando ha scelto, e il «gioca N%» che l'app ha mostrato. Mai le tabelle
`probabili` e `probabili_storia`, che possono avere letture di dopo la scadenza. Nessuna richiesta in rete.
Tara una regressione logistica (titolare e panchina, un peso solo per «in dubbio») sulla metà più vecchia delle giornate, la prova
sulla più recente e scrive l'esito nella tabella `taratura_probabili`: `pronta` se sbaglia meno sia dei numeri di partenza sia di
quelli mostrati, `scartata` se no.

In questa versione misura soltanto (`ATTIVAZIONE = False`): il modello non legge la tabella e nessun numero mostrato cambia.
Comando: `python -m fanta taratura-probabili [--prova]`, ultimo passo di `script/server/aggiorna.sh`.
Piano: `docs/superpowers/plans/2026-11-06-gioca-probabili-server.md`; decisione: `docs/decisioni/0009-gioca-probabili-si-ritara-sul-server.md`.
"""
from __future__ import annotations

import math
import sqlite3

import numpy as np
import pandas as pd

from . import modello, registro_giornate as rg
from .punteggio import COLONNA_VOTO

MIN_GIORNATE = 4                 # giornate misurate con le probabili di prima della scadenza per fare la prova (issue #379)
MIN_GIORNATE_ACCENSIONE = 8      # per accendere (PR B): almeno 8 giornate (D1 del 5/11)...
MIN_PROVA_ACCENSIONE = 3         # ...e almeno 3 di prova
MAX_PROVA = 8                    # la prova usa al massimo le ultime 8 giornate
MIN_RIGHE_STATO = 200            # righe di titolari e di panchinari che servono in ciascuna metà
K_NON_CITATO = 50                # chi non è citato: la quota vera tirata verso P_NON_CITATO come con 50 casi in più
P_NON_CITATO = 0.02              # quanto vale oggi chi non è citato in una squadra coperta (`modello._pezzi`)
COLONNE = ["stagione", "giornata", "calciatore_id", "stato", "percentuale", "dubbio", "p_mostrato", "preso"]


# ---------------------------------------------------------------- le righe di taratura
def righe(db: sqlite3.Connection) -> pd.DataFrame:
    """Una riga per giocatore e giornata del registro: probabili mostrate allora (`stato`, `percentuale` 0-100 o NaN, `dubbio`),
    «gioca N%» mostrato (`p_mostrato`) e se ha preso voto (`preso`). Solo giornate misurate, salvate con le probabili e non perse;
    solo partite giocate con i voti di tutte e due le squadre (`registro_giornate._partite`); solo squadre coperte dalle probabili
    (`stato` non vuoto). I valori rovinati non fermano niente: una percentuale illeggibile o fuori scala vale mancante, una riga
    senza il numero mostrato non conta."""
    col = COLONNA_VOTO[rg.REGOLE.fonte_voto]
    validi: set[tuple[str, int, int]] = set()
    for stagione, g in db.execute("SELECT stagione, giornata FROM registro_giornate WHERE misurato IS NOT NULL AND con_probabili = 1 "
                                  "AND persa IS NULL ORDER BY stagione, giornata").fetchall():
        validi |= {(stagione, g, p) for p in rg._partite(db, stagione, g)[0]}
    dati = db.execute(
        "SELECT r.stagione, r.giornata, r.calciatore_id, r.stato, r.percentuale, r.dubbio, r.p_voto, r.partita_id, "
        f"EXISTS (SELECT 1 FROM voti v WHERE v.stagione = r.stagione AND v.giornata = r.giornata AND v.calciatore_id = r.calciatore_id "
        f"AND v.{col} IS NOT NULL) "
        "FROM registro_giocatori r JOIN registro_giornate g ON g.stagione = r.stagione AND g.giornata = r.giornata "
        "WHERE g.misurato IS NOT NULL AND g.con_probabili = 1 AND g.persa IS NULL AND r.stato IS NOT NULL").fetchall()
    dati = [tuple(x) for x in dati if (x[0], x[1], x[7]) in validi]
    t = pd.DataFrame(dati, columns=["stagione", "giornata", "calciatore_id", "stato", "percentuale", "dubbio", "p_mostrato",
                                    "partita", "preso"])
    t["calciatore_id"] = pd.to_numeric(t["calciatore_id"], errors="coerce")
    t["giornata"] = pd.to_numeric(t["giornata"], errors="coerce")
    t["percentuale"] = pd.to_numeric(t["percentuale"], errors="coerce").astype(float)
    t.loc[~t["percentuale"].between(0, 100), "percentuale"] = np.nan
    t["p_mostrato"] = pd.to_numeric(t["p_mostrato"], errors="coerce").astype(float)
    t = t[t["p_mostrato"].between(0, 1) & t["calciatore_id"].notna() & t["giornata"].notna()].copy()
    t["stagione"] = t["stagione"].astype(str)
    t["stato"] = t["stato"].astype(str)
    t["giornata"] = t["giornata"].astype(int)
    t["calciatore_id"] = t["calciatore_id"].astype(int)
    t["dubbio"] = (pd.to_numeric(t["dubbio"], errors="coerce") == 1).astype(int)
    t["preso"] = t["preso"].astype(int)
    return t[COLONNE].sort_values(["stagione", "giornata", "calciatore_id"], kind="stable", ignore_index=True)


def giornate(r: pd.DataFrame) -> list[tuple[str, int]]:
    """Le giornate delle righe, dalla più vecchia."""
    return sorted({(str(s), int(g)) for s, g in zip(r["stagione"], r["giornata"])})


def dividi(gg: list[tuple[str, int]]) -> tuple[list, list]:
    """(taratura, prova): la prova sono le ultime min(metà, MAX_PROVA) giornate, la taratura quelle prima."""
    k = min(len(gg) // 2, MAX_PROVA)
    return list(gg[:len(gg) - k]), list(gg[len(gg) - k:])


# ---------------------------------------------------------------- la formula tarata e la stima
def colonne_regressione(r: pd.DataFrame) -> np.ndarray:
    """Le colonne della regressione per ogni riga: [è titolare, è titolare × q, è in panchina, è in panchina × q, in dubbio], con q
    la percentuale / 100 (0,8 per i titolari e 0,2 in panchina se manca, come `modello._p_da_probabili`). Niente costante comune:
    titolari e panchinari hanno ognuno la sua, e il peso di «in dubbio» è uno solo."""
    tit = (r["stato"] == "titolare").to_numpy(float)
    pan = (r["stato"] == "panchina").to_numpy(float)
    perc = r["percentuale"].to_numpy(float)
    q = np.where(np.isnan(perc), np.where(tit == 1, 0.8, 0.2), perc / 100)
    dub = (r["dubbio"].to_numpy() == 1).astype(float)
    return np.column_stack([tit, tit * q, pan, pan * q, dub])


def regressione_logistica(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Regressione logistica (Newton, 50 passi, con un filo di regolarizzazione). Usata anche da `prove/calibra_p_voto.py`."""
    w = np.zeros(X.shape[1])
    with np.errstate(over="ignore"):                  # dati degeneri (tutti in campo): exp trabocca, ma il risultato resta giusto
        for _ in range(50):
            p = 1 / (1 + np.exp(-X @ w))
            H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-3 * np.eye(len(w))
            w += np.linalg.solve(H, X.T @ (y - p) - 1e-3 * w)
    return w


def stima(r: pd.DataFrame) -> dict:
    """I coefficienti tarati sulle righe: {"titolare": [a, b], "panchina": [a, b], "dubbio": c, "non_citato": n}, a 4 decimali.
    Una regressione sola sulle righe di titolari e panchinari; chi non è citato vale la sua quota vera tirata verso 0,02."""
    sc = r[r["stato"].isin(("titolare", "panchina"))]
    try:
        w = regressione_logistica(colonne_regressione(sc), sc["preso"].to_numpy(float))
    except np.linalg.LinAlgError:
        w = np.full(5, np.nan)                        # sistema singolare: coefficienti vuoti, mai coerenti
    nc = r[r["stato"] == "non_citato"]
    n = (float(nc["preso"].sum()) + P_NON_CITATO * K_NON_CITATO) / (len(nc) + K_NON_CITATO)
    c = [float(round(float(x), 4)) for x in w]
    return {"titolare": c[0:2], "panchina": c[2:4], "dubbio": c[4], "non_citato": float(round(n, 4))}


def coerente(t) -> bool:
    """Coefficienti sensati: più percentuale vuol dire più probabilità (b ≥ 0), «in dubbio» non la alza (c ≤ 0), il titolare non
    sta mai sotto il panchinario alla stessa percentuale, il titolare al 100% gioca tra 85 e 99 volte su 100 (oggi 96), chi non è
    citato al massimo 10 su 100; tutti numeri finiti. Qualsiasi forma diversa: non coerente."""
    try:
        at, bt = (float(x) for x in t["titolare"])
        ap, bp = (float(x) for x in t["panchina"])
        c, n = float(t["dubbio"]), float(t["non_citato"])
    except (TypeError, KeyError, ValueError, IndexError):
        return False
    if not all(math.isfinite(x) for x in (at, bt, ap, bp, c, n)):
        return False
    if bt < 0 or bp < 0 or c > 0 or not 0 <= n <= 0.10:
        return False
    if any(at + bt * q < ap + bp * q for q in (i / 10 for i in range(11))):
        return False
    return 0.85 <= modello._p_da_probabili("titolare", 100.0, False, {"titolare": [at, bt], "dubbio": c}) <= 0.99
