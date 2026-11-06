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

import json
import math
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

from . import modello, registro_giornate as rg
from .punteggio import COLONNA_VOTO

NOME = "taratura-probabili"      # inizio di ogni riga nel log di aggiorna.sh
ATTIVAZIONE = False              # solo misura: le righe sono «pronta» o «scartata» e il modello non le legge (la accende la PR B)
SOGLIA_BRIER = 0.005             # Brier almeno lo 0,5% più basso, come per promuovere una fonte (`verifica_fonti.SOGLIA_ERRORE`)
MIN_GIORNATE = 4                # giornate misurate con le probabili di prima della scadenza per fare la prova (issue #379)
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
        "EXISTS (SELECT 1 FROM voti v WHERE v.stagione = r.stagione AND v.giornata = r.giornata AND v.calciatore_id = r.calciatore_id "
        f"AND v.{col} IS NOT NULL) "          # colonna fissa delle regole classiche, mai un dato
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


# ---------------------------------------------------------------- la prova
def _p(r: pd.DataFrame, taratura: dict | None) -> np.ndarray:
    """«gioca N%» di ogni riga con la formula (di partenza se `taratura` è None), senza correzione per gruppi."""
    return np.array([modello._p_da_probabili(s, None if math.isnan(q) else float(q), bool(d), taratura)
                     for s, q, d in zip(r["stato"], r["percentuale"].to_numpy(float), r["dubbio"])], dtype=float)


def fattori_su(r: pd.DataFrame, taratura: dict | None) -> dict[str, float]:
    """La correzione per gruppi (±15%, `stato_dati.fattori_da`) calcolata su queste righe invece che sulla tabella `probabili`:
    gruppi di `modello.GRUPPI_PROBABILI`, nella forma di `stato_dati.calibrazione`, con il «previsto» della formula indicata."""
    from . import stato_dati                          # qui dentro: stato_dati importa modello e il registro importa consigli
    previsto = _p(r, taratura)
    perc = r["percentuale"].to_numpy(float)
    gruppi = []
    for nome, stato, da, a in modello.GRUPPI_PROBABILI:
        scelti = ((r["stato"] == stato).to_numpy() & ~np.isnan(perc) & (perc >= da) & (perc < a))
        n = int(scelti.sum())
        if not n:
            gruppi.append({"gruppo": nome, "n": 0, "osservato": None, "previsto": None, "indicativo": True})
            continue
        gruppi.append({"gruppo": nome, "n": n, "osservato": round(float(r["preso"].to_numpy()[scelti].mean()), 3),
                       "previsto": round(float(previsto[scelti].mean()), 3), "indicativo": n < stato_dati.MINIMO_PER_GRUPPO})
    return stato_dati.fattori_da({"giornate": len(giornate(r)), "gruppi": gruppi})


def _misura_p(r: pd.DataFrame, p: np.ndarray) -> dict:
    """{casi, brier, calibrazione, per_giornata}. Calibrazione come I2 del registro: fasce di 10 punti, media pesata di
    |detto − giocato| (0,05 = 5 punti). `per_giornata`: [[stagione, giornata, Brier], …] dalla più vecchia."""
    y = r["preso"].to_numpy(float)
    if not len(y):
        return {"casi": 0, "brier": None, "calibrazione": None, "per_giornata": []}
    errore = (p - y) ** 2
    fascia = np.clip(np.floor(p * rg.FASCE + 1e-9), 0, rg.FASCE - 1).astype(int)
    detto, giocato = np.bincount(fascia, p, rg.FASCE), np.bincount(fascia, y, rg.FASCE)
    chiavi = list(zip(r["stagione"], r["giornata"]))
    per = pd.Series(errore).groupby(pd.MultiIndex.from_tuples(chiavi)).mean()
    return {"casi": len(y), "brier": float(errore.mean()), "calibrazione": float(np.abs(detto - giocato).sum() / len(y)),
            "per_giornata": [[str(s), int(g), float(b)] for (s, g), b in per.sort_index().items()]}


def misura(r: pd.DataFrame, taratura: dict | None, fattori: dict[str, float]) -> dict:
    """Quanto sbaglia la formula sulle righe, con la correzione per gruppi come in `modello._pezzi` (al massimo 0,99)."""
    p = _p(r, taratura)
    if fattori:
        perc = r["percentuale"].to_numpy(float)
        f = np.array([fattori.get(modello.gruppo_probabili(s, float(q)) or "", 0.0) if not math.isnan(q) else 0.0
                      for s, q in zip(r["stato"], perc)])
        p = np.where(f > 0, np.minimum(0.99, p * f), p)
    return _misura_p(r, p)


def misura_mostrati(r: pd.DataFrame) -> dict:
    """Gli stessi numeri con il «gioca N%» mostrato davvero allora (`p_mostrato`)."""
    return _misura_p(r, r["p_mostrato"].to_numpy(float))


def verdetto(nuova: dict, attuale: dict, mostrati: dict, t: dict) -> tuple[bool, str]:
    """(passa, motivo). Passa solo se i coefficienti sono coerenti, il Brier della nuova è almeno lo 0,5% più basso sia della
    formula di adesso sia dei numeri mostrati, è più basso di tutti e due in almeno due terzi delle giornate di prova (per eccesso:
    3 → 2, 4 → 3) e la nuova sta nelle soglie di I2 (calibrazione ≤ 5 punti, Brier ≤ 0,15). Motivi: `migliora`, `incoerente`,
    `non_migliora`, `fuori_soglia`."""
    if not coerente(t):
        return False, "incoerente"
    b, ba, bm = nuova.get("brier"), attuale.get("brier"), mostrati.get("brier")
    if b is None or ba is None or bm is None or b > min(ba, bm) * (1 - SOGLIA_BRIER):
        return False, "non_migliora"
    altre = {(s, g): min(x, y) for (s, g, x), (_, _, y) in zip(attuale["per_giornata"], mostrati["per_giornata"])}
    gg = nuova["per_giornata"]
    meglio = sum(1 for s, g, x in gg if (s, g) in altre and x < altre[(s, g)])
    if not gg or meglio < -(-2 * len(gg) // 3):
        return False, "non_migliora"
    if nuova["calibrazione"] is None or nuova["calibrazione"] > rg.SOGLIE["I2_calibrazione"] or b > rg.SOGLIE["I2_brier"]:
        return False, "fuori_soglia"
    return True, "migliora"


def _conta(r: pd.DataFrame) -> tuple[int, int]:
    return int((r["stato"] == "titolare").sum()), int((r["stato"] == "panchina").sum())


def _prova(r: pd.DataFrame, attuale: dict | None) -> dict | None:
    gg = giornate(r)
    if len(gg) < MIN_GIORNATE:
        return None
    tar, pro = dividi(gg)
    chiavi = pd.Series(list(zip(r["stagione"], r["giornata"])), index=r.index)
    rt, rp = r[chiavi.isin(set(tar))], r[chiavi.isin(set(pro))]
    if min(*_conta(rt), *_conta(rp)) < MIN_RIGHE_STATO:
        return None
    t = stima(rt)
    return {"giornate": len(gg), "taratura": tar, "prova": pro, "coefficienti": t,
            "nuova": misura(rp, t, fattori_su(rt, t)), "attuale": misura(rp, attuale, fattori_su(rt, attuale)),
            "mostrati": misura_mostrati(rp)}


def prova(db: sqlite3.Connection, attuale: dict | None) -> dict | None:
    """Tara sulla metà più vecchia delle giornate e misura sulla più recente la nuova, quella di adesso (`attuale`, None = numeri
    di partenza), ognuna con la sua correzione per gruppi imparata sulla metà di taratura, e i numeri mostrati. None se le giornate
    sono meno di MIN_GIORNATE o una metà ha meno di MIN_RIGHE_STATO titolari o panchinari."""
    return _prova(righe(db), attuale)


# ---------------------------------------------------------------- il comando
def _giornate_da(testo) -> list[tuple[str, int]] | None:
    """La lista JSON [[stagione, giornata], …] di una riga della tabella; None se manca o è rovinata."""
    try:
        v = json.loads(testo)
        return [(str(s), int(g)) for s, g in v]
    except (TypeError, ValueError):
        return None


def _numeri(x):
    """Numeri a 4 decimali per la tabella (JSON valido: niente NaN né infiniti)."""
    if isinstance(x, dict):
        return {k: _numeri(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_numeri(v) for v in x]
    if isinstance(x, float):
        return round(x, 4) if math.isfinite(x) else None
    return x


def _scrivi(db: sqlite3.Connection, adesso: datetime, stato: str, esito: dict, motivo: str) -> int:
    misura_ = {k: esito[k] for k in ("nuova", "attuale", "mostrati")}
    testo = lambda x: json.dumps(_numeri(x), ensure_ascii=False, allow_nan=False, separators=(",", ":"))  # noqa: E731
    cur = db.execute("INSERT INTO taratura_probabili (creata, stato, coefficienti, taratura, prova, misura, motivo, avvisato) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                     (adesso.isoformat(timespec="seconds"), stato, testo(esito["coefficienti"]), testo(esito["taratura"]),
                      testo(esito["prova"]), testo(misura_), motivo))
    db.commit()
    return int(cur.lastrowid)


def _in_attesa(r: pd.DataFrame, gg: list) -> str:
    if len(gg) < MIN_GIORNATE:
        return f"{NOME}: in attesa: {len(gg)} giornate su {MIN_GIORNATE}"
    tar, pro = dividi(gg)
    chiavi = pd.Series(list(zip(r["stagione"], r["giornata"])), index=r.index)
    (t1, p1), (t2, p2) = _conta(r[chiavi.isin(set(tar))]), _conta(r[chiavi.isin(set(pro))])
    return (f"{NOME}: in attesa: poche righe (taratura {t1} titolari e {p1} panchinari, prova {t2} e {p2}; "
            f"ne servono {MIN_RIGHE_STATO} per metà)")


def esegui(db: sqlite3.Connection, adesso: datetime) -> str:
    """Un giro del comando, per il log: con giornate nuove rifà la prova e scrive una riga `pronta` (supera il verdetto) o
    `scartata`. Non scrive niente se l'ultima riga ha già la stessa prova («niente di nuovo»: il lavoro vero si fa al massimo una
    volta per giornata) o se le giornate o le righe non bastano («in attesa»). Solo misura: nessun numero mostrato cambia."""
    r = righe(db)
    gg = giornate(r)
    if len(gg) < MIN_GIORNATE:
        return _in_attesa(r, gg)
    ultima = db.execute("SELECT versione, stato, prova FROM taratura_probabili ORDER BY versione DESC LIMIT 1").fetchone()
    if ultima is not None and _giornate_da(ultima[2]) == dividi(gg)[1]:
        return f"{NOME}: niente di nuovo (versione {ultima[0]}, {ultima[1]})"
    esito = _prova(r, None)                           # la formula di adesso: i numeri di partenza (nessuna riga attiva)
    if esito is None:
        return _in_attesa(r, gg)
    passa, motivo = verdetto(esito["nuova"], esito["attuale"], esito["mostrati"], esito["coefficienti"])
    stato = "pronta" if passa else "scartata"
    versione = _scrivi(db, adesso, stato, esito, motivo)
    n, a, m = esito["nuova"], esito["attuale"], esito["mostrati"]
    return (f"{NOME}: versione {versione} {stato} ({motivo}): Brier {n['brier']:.4f} contro {a['brier']:.4f} dei numeri di partenza "
            f"e {m['brier']:.4f} dei mostrati, calibrazione {100 * n['calibrazione']:.1f} punti, {len(esito['prova'])} giornate di prova")


def rapporto(db: sqlite3.Connection) -> list[str]:
    """Le righe di `--prova`: giornate, casi, Brier e calibrazione di adesso, nuova e mostrati, coefficienti e verdetto. Non scrive
    niente nella tabella."""
    r = righe(db)
    gg = giornate(r)
    esito = _prova(r, None)
    if esito is None:
        return [_in_attesa(r, gg)]
    passa, motivo = verdetto(esito["nuova"], esito["attuale"], esito["mostrati"], esito["coefficienti"])
    fmt = lambda lista: ", ".join(f"{s} g{g}" for s, g in lista)  # noqa: E731
    righe_ = [f"Giornate: {len(gg)}; taratura {fmt(esito['taratura'])}; prova {fmt(esito['prova'])}"]
    for nome, chiave in (("adesso (numeri di partenza)", "attuale"), ("nuova", "nuova"), ("mostrati", "mostrati")):
        m = esito[chiave]
        righe_.append(f"{nome}: {m['casi']} casi, Brier {m['brier']:.4f}, calibrazione {100 * m['calibrazione']:.1f} punti")
    righe_.append(f"Coefficienti: {json.dumps(esito['coefficienti'])}")
    righe_.append(f"Verdetto: {'passa' if passa else 'non passa'} ({motivo}); nessuna riga scritta")
    return righe_
