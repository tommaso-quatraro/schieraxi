"""Esperimenti «fonti in ombra» di `verifica --fonti` (spenti di default).

Le colonne in più di football-data.co.uk (tabella `partite_extra`) NON sono lette dal modello. Qui si prova, una cosa alla
volta, a dargliele al posto di quelle di oggi e si confronta il risultato con la verifica normale:
- `xg_fd`: forza delle squadre dall'xG di squadra di football-data (disponibile solo dal 2026-27) al posto di quello di Understat;
- `tiri_porta`: forza delle squadre da una media tra l'xG di Understat e i tiri in porta (convertiti in gol con il rapporto
  gol/tiri in porta del campionato).

Regola di promozione (da docs/archivio/PIANO-DATI.md): errore sui voti almeno 0,5% più basso e miglioramento nello stesso senso in almeno
2 stagioni su 3. Il modello non cambia da solo: la promozione è una decisione da prendere guardando questi numeri.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import verifica
from .modello import Dati

VARIANTI = ("xg_fd", "tiri_porta")
SOGLIA_ERRORE = -0.5          # per cento: serve una riduzione dell'errore di almeno così
STAGIONI_MIN_MIGLIORI = 2     # su (al massimo) le ultime 3 stagioni misurate
PESO_TIRI = 0.5               # tiri_porta: quanto pesa la parte dei tiri in porta (il resto è l'xG di Understat)


def _unisci_extra(d: Dati) -> pd.DataFrame:
    """Le partite con le colonne extra accanto (prefisso fd_ per non confondersi con quelle di Understat)."""
    p = d.partite.copy()
    e = d.extra
    if e is None or e.empty:
        return p
    e = e.drop(columns=[c for c in ("data", "rilevato") if c in e.columns]).add_prefix("fd_")
    e = e.rename(columns={"fd_stagione": "stagione", "fd_casa": "casa", "fd_trasferta": "trasferta"})
    return p.merge(e, on=["stagione", "casa", "trasferta"], how="left")


def dati_con_variante(d: Dati, nome: str) -> tuple[Dati, int]:
    """(copia dei dati con la variante applicata, quante partite sono davvero cambiate). Non tocca l'originale."""
    if nome not in VARIANTI:
        raise ValueError(f"fonte sconosciuta: {nome} (valide: {', '.join(VARIANTI)})")
    p = _unisci_extra(d)
    cambiate = 0

    def col(n: str) -> pd.Series:
        return p[n] if n in p.columns else pd.Series(np.nan, index=p.index)
    if nome == "xg_fd":
        usa = col("fd_xg_casa").notna() & col("fd_xg_trasferta").notna()
        p.loc[usa, "xg_casa"] = col("fd_xg_casa")[usa]
        p.loc[usa, "xg_trasferta"] = col("fd_xg_trasferta")[usa]
        cambiate = int(usa.sum())
    else:   # tiri_porta
        usa = col("fd_in_porta_casa").notna() & col("fd_in_porta_trasferta").notna()
        gol = (p["gol_casa"] + p["gol_trasferta"])[usa].sum()
        tiri = (col("fd_in_porta_casa") + col("fd_in_porta_trasferta"))[usa].sum()
        k = float(gol / tiri) if tiri > 0 else 0.0
        for xg, tp in (("xg_casa", "fd_in_porta_casa"), ("xg_trasferta", "fd_in_porta_trasferta")):
            da_tiri = k * col(tp)
            mescolato = np.where(p[xg].notna(), (1 - PESO_TIRI) * p[xg] + PESO_TIRI * da_tiri, da_tiri)
            p.loc[usa, xg] = mescolato[usa.to_numpy()]
        cambiate = int(usa.sum())
    return replace(d, partite=p), cambiate


def _riassunto(t: pd.DataFrame) -> dict:
    """Per una verifica: rmse (errore sui voti), Brier delle presenze, punti delle formazioni."""
    out = {"giornate": len(t), "rmse": float(t["quadratico_modello"].mean() ** 0.5), "brier": float(t["brier"].mean())}
    if "punti_modello" in t:
        out["punti"] = float(t["punti_modello"].mean())
    return out


def confronto(d: Dati, regole, par, giornate: list[tuple[str, int]], rose=None, simulazioni: int = 300,
              varianti=VARIANTI, scrivi=print) -> pd.DataFrame:
    """Una riga per prova (base e ciascuna variante) e stagione, con la differenza percentuale dell'errore rispetto alla base."""
    prove = [("base", d, None)]
    for v in varianti:
        dv, n = dati_con_variante(d, v)
        prove.append((v, dv, n))
    risultati: dict[str, pd.DataFrame] = {}
    for nome, dati, n in prove:
        if scrivi:
            scrivi(f"Prova «{nome}»" + (f" ({n} partite con il dato nuovo)" if n is not None else "") + "...")
        t = verifica.verifica(dati, regole, par, giornate, rose, simulazioni, scrivi=None)
        if not t.empty:
            risultati[nome] = t
    righe = []
    base = risultati.get("base")
    if base is None:
        return pd.DataFrame(righe)
    for nome, t in risultati.items():
        n_cambiate = next((n for q, _, n in prove if q == nome), None)
        for stagione in ["tutte"] + sorted(t["stagione"].unique().tolist()):
            sel = (lambda x: x) if stagione == "tutte" else (lambda x, s=stagione: x[x["stagione"] == s])
            r, b = _riassunto(sel(t)), _riassunto(sel(base))
            riga = {"prova": nome, "stagione": stagione, "giornate": r["giornate"], "rmse": r["rmse"], "brier": r["brier"],
                    "variazione_errore_pct": (r["rmse"] / b["rmse"] - 1) * 100 if b["rmse"] else 0.0,
                    "variazione_brier_pct": (r["brier"] / b["brier"] - 1) * 100 if b["brier"] else 0.0,
                    "partite_cambiate": n_cambiate}
            if "punti" in r:
                riga["punti"] = r["punti"]
                riga["variazione_punti"] = r["punti"] - b.get("punti", r["punti"])
            righe.append(riga)
    return pd.DataFrame(righe)


def giudizio(tab: pd.DataFrame) -> dict[str, str]:
    """Verdetto per variante secondo la regola di promozione: errore -0,5% o meglio sul totale e stesso segno
    (miglioramento) in almeno 2 delle ultime 3 stagioni misurate. Con una sola stagione: solo indicativo."""
    out = {}
    if tab.empty:
        return out
    for v in sorted(set(tab["prova"]) - {"base"}):
        t = tab[(tab["prova"] == v)]
        totale = t[t["stagione"] == "tutte"]["variazione_errore_pct"]
        per_stagione = t[t["stagione"] != "tutte"].sort_values("stagione").tail(3)
        if totale.empty or per_stagione.empty:
            continue
        pct = float(totale.iloc[0])
        migliori = int((per_stagione["variazione_errore_pct"] < 0).sum())
        if (t["partite_cambiate"].fillna(0) == 0).all():
            out[v] = "nessuna partita con il dato nuovo: niente da misurare"
        elif len(per_stagione) < 2:
            out[v] = f"errore {pct:+.2f}% su una sola stagione: solo indicativo, non si promuove"
        elif pct <= SOGLIA_ERRORE and migliori >= STAGIONI_MIN_MIGLIORI:
            out[v] = f"PROMOSSA: errore {pct:+.2f}%, migliora in {migliori} stagioni su {len(per_stagione)}"
        else:
            out[v] = f"non promossa: errore {pct:+.2f}%, migliora in {migliori} stagioni su {len(per_stagione)} (servono {SOGLIA_ERRORE}% e {STAGIONI_MIN_MIGLIORI})"
    return out
