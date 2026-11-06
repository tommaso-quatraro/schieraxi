"""Calibrazione della probabilità di prendere voto (p_voto): misura e ristima, senza guardare il futuro.

Per ogni giornata già giocata rifà le previsioni con i soli dati precedenti (come `python -m fanta verifica`) e confronta
«gioca N%» con chi ha preso voto davvero, per fasce di 10 punti, per stagione e per ruolo:
- «prima» = la sola quota delle presenze recenti (come fino al 2/11/2026);
- «dopo»  = `modello.p_senza_probabili` con i pesi di `modello.CALIBRAZIONE_SENZA_PROBABILI`.
Con `--stima 2025-26` ristima i pesi SOLO sulle stagioni indicate e li stampa (da copiare in `modello.py`; prima e dopo:
`python -m fanta verifica`). Se l'archivio ha probabili formazioni di giornate già giocate, misura anche quelle per stato
e percentuale (`modello._p_da_probabili`).
«in squadra» = giocatori che in quella stagione hanno almeno una riga di voto con quella squadra: toglie chi è andato via
d'estate e nella verifica resta in elenco con la vecchia squadra (nell'app vera non c'è). Serve SOLO a misurare.

Uso: .venv\\Scripts\\python.exe prove\\calibra_p_voto.py [--stima 2025-26] [--dalla 5]   (regole della lega: come `python -m fanta`)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fanta import archivio, coppe, modello, regole  # noqa: E402
from fanta.percorsi import CARTELLA_LEGA  # noqa: E402
from fanta.punteggio import COLONNA_VOTO  # noqa: E402
from fanta.taratura_probabili import regressione_logistica  # noqa: E402

VARIABILI = ["p_storico", "p_lungo", "p_titolare", "p_ultima", "portiere", "portiere_x_p_storico"]
FASCE = np.append(np.arange(0, 1.0, 0.1), 1.0001)


def raccogli(d: modello.Dati, r, giornate) -> pd.DataFrame:
    """Una riga per giocatore e giornata: le quote che entrano in `p_senza_probabili`, p prima e dopo, e se ha preso voto."""
    col = COLONNA_VOTO[r.fonte_voto]
    originale = modello.p_senza_probabili
    righe = []
    for st, gi in giornate:
        quote = []

        def spia(*a):
            quote.append(a)  # noqa: B023 la funzione spia si usa solo dentro questo giro del ciclo
            return originale(*a)
        modello.p_senza_probabili = spia
        try:
            prev = modello.previsioni(d, st, gi, r)
        finally:
            modello.p_senza_probabili = originale
        prev = prev.drop(columns=["p_lungo"]).reset_index(drop=True)      # (la stessa quota arriva, non arrotondata, da `quote`)
        q = pd.DataFrame(quote, columns=["p_storico", "p_lungo", "p_titolare", "p_ultima", "portiere"])
        prev = pd.concat([prev, q], axis=1)          # una chiamata per riga, nello stesso ordine
        giocate = set(d.partite.loc[(d.partite["stagione"] == st) & (d.partite["giornata"] == gi) & (d.partite["giocata"] == 1), "id"])
        prev = prev[prev["partita"].isin(giocate)].copy()
        reali = d.voti[(d.voti["stagione"] == st) & (d.voti["giornata"] == gi) & d.voti[col].notna()]
        prev["preso"] = prev["id"].isin(set(reali["calciatore_id"])).astype(int)
        turnover = [coppe.fattore_turnover(q, dp) for q, dp in zip(prev["squadra"], prev["data_partita"])]
        prev["prima"] = prev["p_storico"] * turnover
        prev["dopo"] = prev["p_voto"]
        prev["stagione"], prev["giornata"] = st, gi
        righe.append(prev[["stagione", "giornata", "id", "ruolo", "squadra", "p_storico", "p_lungo", "p_titolare", "p_ultima",
                           "portiere", "prima", "dopo", "preso"]])
        print(f"  {st} g{gi:>2}: {len(prev)} giocatori", flush=True)
    t = pd.concat(righe, ignore_index=True)
    t["portiere"] = t["portiere"].astype(float)
    t["portiere_x_p_storico"] = t["portiere"] * t["p_storico"]
    in_squadra = d.voti[["stagione", "calciatore_id", "squadra"]].drop_duplicates()
    in_squadra = set(zip(in_squadra["stagione"], in_squadra["calciatore_id"], in_squadra["squadra"]))
    t["in_squadra"] = [(s, i, q) in in_squadra for s, i, q in zip(t["stagione"], t["id"], t["squadra"])]
    return t


def errore_calibrazione(p: pd.Series, y: pd.Series) -> float:
    """Media pesata, sulle fasce di 10 punti, di |detto - giocato| (0 = perfetta)."""
    g = pd.DataFrame({"p": p, "y": y}).groupby(pd.cut(p, FASCE, right=False), observed=True).agg(n=("y", "size"), d=("p", "mean"), o=("y", "mean"))
    return float((g["n"] * (g["d"] - g["o"]).abs()).sum() / g["n"].sum())


def tabella(t: pd.DataFrame, titolo: str) -> None:
    print(f"\n== {titolo}: {len(t)} casi | Brier prima {((t.prima - t.preso) ** 2).mean():.4f} dopo {((t.dopo - t.preso) ** 2).mean():.4f}"
          f" | errore di calibrazione prima {errore_calibrazione(t.prima, t.preso):.3f} dopo {errore_calibrazione(t.dopo, t.preso):.3f}")
    parti = {}
    for c in ("prima", "dopo"):
        parti[c] = t.groupby(pd.cut(t[c], FASCE, right=False), observed=True).agg(n=("preso", "size"), detto=(c, "mean"), giocato=("preso", "mean"))
        parti[c].index = [f"{int(round(i.left * 100))}-{min(100, int(round(i.right * 100)))}%" for i in parti[c].index]
    print(pd.concat(parti, axis=1).round(3).to_string())


def stima(t: pd.DataFrame) -> np.ndarray:
    """Regressione logistica (Newton, con un filo di regolarizzazione: `taratura_probabili.regressione_logistica`)."""
    X = np.column_stack([np.ones(len(t)), t[VARIABILI].to_numpy(float)])
    return regressione_logistica(X, t["preso"].to_numpy(float))


def probabili(db, d: modello.Dati, r) -> None:
    """Calibrazione delle probabili formazioni (fonte fantacalcio) nelle giornate già giocate, se ce ne sono."""
    col = COLONNA_VOTO[r.fonte_voto]
    p = pd.read_sql_query("SELECT p.stagione, p.giornata, p.calciatore_id, p.stato, p.percentuale, p.in_dubbio FROM probabili p "
                          "JOIN partite g ON g.id = p.partita_id AND g.giocata = 1 WHERE p.fonte = 'fantacalcio'", db)
    if p.empty:
        print("\nProbabili formazioni: nessuna giornata già giocata nell'archivio (si misurano dove sono raccolte).")
        return
    veri = set(zip(*[d.voti.loc[d.voti[col].notna(), c] for c in ("stagione", "giornata", "calciatore_id")]))
    p["preso"] = [(s, g, i) in veri for s, g, i in zip(p["stagione"], p["giornata"], p["calciatore_id"])]
    p["detto"] = [modello._p_da_probabili(s, None if pd.isna(c) else float(c), bool(u)) for s, c, u in zip(p["stato"], p["percentuale"], p["in_dubbio"])]
    p["gruppo"] = [modello.gruppo_probabili(s, None if pd.isna(c) else float(c)) or s for s, c in zip(p["stato"], p["percentuale"])]
    print(f"\n== Probabili formazioni: {p['giornata'].nunique()} giornate, {len(p)} casi, errore di calibrazione "
          f"{errore_calibrazione(p['detto'], p['preso'].astype(int)):.3f}")
    print(p.groupby("gruppo").agg(n=("preso", "size"), detto=("detto", "mean"), giocato=("preso", "mean")).round(3).to_string())


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--stima", nargs="*", default=None, help="stagioni su cui ristimare i pesi (es. 2025-26)")
    a.add_argument("--dalla", type=int, default=5, help="prima giornata della stagione più vecchia (come verifica)")
    a = a.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    r = regole.carica(CARTELLA_LEGA / "regole.json")      # FANTA_LEGA, poi lega/, poi lega/esempio
    db = archivio.apri()
    d = modello.carica(db)
    giornate = []
    for st in d.stagioni:
        g = sorted(d.partite.loc[(d.partite["stagione"] == st) & (d.partite["giocata"] == 1), "giornata"].unique())
        giornate += [(st, int(x)) for x in g if x >= (a.dalla if st == d.stagioni[0] else 2)]
    t = raccogli(d, r, giornate)
    for st, x in t.groupby("stagione"):
        tabella(x, st)
        if not x["in_squadra"].all():
            tabella(x[x["in_squadra"]], f"{st}, solo chi era nella squadra")
    for ruolo, x in t.groupby("ruolo"):
        print(f"ruolo {ruolo}: n {len(x)}, detto prima {x.prima.mean():.3f} dopo {x.dopo.mean():.3f}, giocato {x.preso.mean():.3f}")
    if a.stima:
        w = stima(t[t["stagione"].isin(a.stima)])
        nomi = ["costante", "p_storico", "p_lungo", "p_titolare", "p_ultima", "portiere", "portiere_x_p_storico"]
        print("\nPesi nuovi (stimati su " + ", ".join(a.stima) + "):\n" + "{" + ", ".join(f'"{n}": {v:.3f}' for n, v in zip(nomi, w)) + "}")
    probabili(db, d, r)


if __name__ == "__main__":
    main()
