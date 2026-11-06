r"""Taratura della forza delle squadre per i gol attesi «nostri» (Fase C del piano 2026-11-06-gol-attesi-nostri).

Con i soli dati di Fantacalcio.it (`nostri.dati`: niente xG di squadra) prova memoria, peso della stagione prima, partite
fittizie e livello recente del campionato (`Parametri.decadimento_base`, «-» = senza livello). Misura i gol di ogni squadra in
ogni partita: devianza di Poisson media (più bassa = meglio) e gol attesi / veri (1 = tarati). Si sceglie sul 2025-26 dalla 5ª
giornata e si controlla sul 2026-27 dalla 2ª. Le prime due righe: «oggi» (i valori di `Parametri()`, usati dai nostri fino
alla Fase B) e «nostri» (quelli di `nostri.parametri`). `k_squadre` va oltre il 5 del piano: con 5 la migliore stava al bordo.
Il livello non si sceglie sulla devianza del 2025-26 (non c'è un cambio di stagione): vedi la pull request della Fase C.

Uso (dalla cartella del repository, con l'archivio in dati/fanta.sqlite; un paio di minuti):
    .venv\Scripts\python.exe prove\tara_forza_gol.py
    .venv\Scripts\python.exe prove\tara_forza_gol.py --ruoli     (Compito C3: gol veri / attesi per ruolo, con `nostri.parametri`)
Poi i valori scelti vanno in `nostri.parametri`, e `python -m fanta verifica --pacchetti completo,solo_fantacalcio` prima e dopo.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fanta import archivio, modello, nostri  # noqa: E402
from fanta.punteggio import COLONNA_VOTO  # noqa: E402
from fanta.regole import Regole  # noqa: E402

GRIGLIA = {"decadimento_squadre": (0.95, 0.97, 0.98, 0.99), "peso_stagione_prec_squadre": (0.5, 0.65, 0.8),
           "k_squadre": (2.0, 3.0, 5.0, 8.0, 12.0), "decadimento_base": (None, 0.85, 0.90, 0.95)}
TARA, CONTROLLO = ("2025-26", 5), ("2026-27", 2)      # stagione e prima giornata misurata


def giornate(d: modello.Dati, stagione: str, dalla: int) -> list[tuple[str, int]]:
    giocate = d.partite.loc[(d.partite["stagione"] == stagione) & (d.partite["giocata"] == 1), "giornata"].unique()
    return [(stagione, int(g)) for g in sorted(giocate) if g >= dalla]


def devianza(veri: np.ndarray, attesi: np.ndarray) -> np.ndarray:
    """Devianza di Poisson di ogni conto (0 se attesi = veri)."""
    termine = np.where(veri > 0, veri * np.log(np.where(veri > 0, veri, 1) / attesi), 0.0)
    return 2 * (termine - (veri - attesi))


def misura(d: modello.Dati, par: modello.Parametri, gg: list[tuple[str, int]]) -> tuple[float, float]:
    """(devianza media, gol attesi / veri) dei gol di ogni squadra nelle partite giocate delle giornate `gg`."""
    veri, attesi = [], []
    for st, g in gg:
        forza = modello.forza_squadre(d, st, g, par)
        m = d.partite[(d.partite["stagione"] == st) & (d.partite["giornata"] == g) & (d.partite["giocata"] == 1)]
        for casa, trasf, gc, gt in zip(m["casa"], m["trasferta"], m["gol_casa"], m["gol_trasferta"]):
            lc, lt = forza.gol_attesi(casa, trasf)
            veri += [gc, gt]
            attesi += [lc, lt]
    v, a = np.asarray(veri, dtype=float), np.asarray(attesi, dtype=float)
    return float(devianza(v, a).mean()), float(a.sum() / v.sum())


def griglia(d: modello.Dati) -> pd.DataFrame:
    """Una riga per combinazione; colonna `riga`: «oggi», «nostri» o vuota."""
    tara, controllo = giornate(d, *TARA), giornate(d, *CONTROLLO)
    base = nostri.parametri()
    nomi = {tuple(getattr(modello.Parametri(), k) for k in GRIGLIA): "oggi", tuple(getattr(base, k) for k in GRIGLIA): "nostri"}
    combinazioni = list(nomi) + [c for c in itertools.product(*GRIGLIA.values()) if c not in nomi]
    righe = []
    for i, valori in enumerate(combinazioni):
        par = replace(base, **dict(zip(GRIGLIA, valori)))
        dev_t, su_t = misura(d, par, tara)
        dev_c, su_c = misura(d, par, controllo)
        righe.append({"riga": nomi.get(valori, "")} | dict(zip(GRIGLIA, valori))
                     | {"devianza_tara": dev_t, "su_veri_tara": su_t, "devianza_controllo": dev_c, "su_veri_controllo": su_c})
        print(f"\r{i + 1}/{len(combinazioni)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return pd.DataFrame(righe)


def ruoli(d: modello.Dati) -> pd.DataFrame:
    """Compito C3: per ruolo, gol su azione e assist veri / attesi di chi prende voto, con `nostri.parametri`, sul 2025-26
    (taratura) e sul 2026-27 (controllo). I fattori di `Parametri.taratura_gol` sono quelli del 2025-26."""
    regole = Regole()
    col = COLONNA_VOTO[regole.fonte_voto]
    dn, par = nostri.dati(d), nostri.parametri()
    v = d.voti[d.voti[col].notna()]
    num = lambda c: pd.to_numeric(v[c], errors="coerce").fillna(0)  # noqa: E731
    veri = pd.DataFrame({"stagione": v["stagione"], "giornata": v["giornata"], "id": v["calciatore_id"],
                         "gol_veri": num("gol"), "assist_veri": num("assist")}).drop_duplicates(["stagione", "giornata", "id"])
    previsti = []
    for st, g in giornate(d, *TARA) + giornate(d, *CONTROLLO):
        p = modello.previsioni(dn, st, g, regole, par)
        previsti.append(p[["id", "ruolo", "e_gol", "e_assist"]].assign(stagione=st, giornata=g))
    m = pd.concat(previsti, ignore_index=True).merge(veri, on=["stagione", "giornata", "id"], how="inner")
    t = m.groupby(["stagione", "ruolo"])[["e_gol", "gol_veri", "e_assist", "assist_veri"]].sum()
    t["gol_veri_su_attesi"] = t["gol_veri"] / t["e_gol"]
    t["assist_veri_su_attesi"] = t["assist_veri"] / t["e_assist"]
    t["tutti_veri_su_attesi"] = (t["gol_veri"] + t["assist_veri"]) / (t["e_gol"] + t["e_assist"])
    return t


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--ruoli", action="store_true", help="gol e assist veri / attesi per ruolo (Compito C3)")
    args = a.parse_args()
    d = modello.carica(archivio.apri())
    if args.ruoli:
        print(ruoli(d).round(3).to_string())
        return
    t = griglia(nostri.dati(d))
    pd.set_option("display.width", 200)
    print(f"Gol di ogni squadra a partita, solo dati di Fantacalcio.it. Taratura: {TARA[0]} dalla {TARA[1]}ª giornata; "
          f"controllo: {CONTROLLO[0]} dalla {CONTROLLO[1]}ª. Devianza di Poisson media (più bassa = meglio), attesi / veri.")
    print("\nOggi e nostri:")
    print(t[t["riga"] != ""].round(4).to_string(index=False))
    print("\nLe 15 migliori sulla taratura:")
    print(t.sort_values("devianza_tara").head(15).round(4).to_string(index=False))
    print("\nLa migliore per ogni livello (decadimento_base), sulla taratura:")
    migliori = t.loc[t.groupby(t["decadimento_base"].fillna(0))["devianza_tara"].idxmin()]
    print(migliori.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
