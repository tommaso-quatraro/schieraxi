"""«Perché questo numero»: i motivi principali del fantavoto atteso di un giocatore, ricavati dai pezzi veri del calcolo.

Il fantavoto atteso `mu` (quello «se gioca») è la somma di pezzi che il modello calcola davvero: il voto del giocatore, l'effetto della
partita (avversario e campo), i gol e gli assist attesi, i rigori, la porta (per i portieri) e il resto (cartellini, autogol, migliore in
campo). Qui non si inventa niente e non si cambia nessun numero: si rimettono in fila quei pezzi e si confronta ognuno con quello di un
giocatore medio dello stesso ruolo che questa giornata gioca (`p_voto` almeno 0,5). Così la differenza si legge subito:
«+0,6 partita favorevole», «+1,1 segna più della media del ruolo».

Regola di conti (verificata dai test): la somma di tutti i pezzi, in fantavoti, è esattamente `mu` meno il fantavoto atteso medio del
ruolo; i motivi mostrati sono i tre più grandi, il «resto» sono gli altri.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .frasi import F, di
from .modello import Parametri
from .regole import Regole

SOGLIA = 0.08              # sotto questa differenza (fantavoti) un pezzo non è un motivo da dire
MAX_MOTIVI = 3
P_RIFERIMENTO = 0.5        # il giocatore «medio» del ruolo è la media di chi gioca davvero (p_voto almeno 0,5)
PEZZI = ("voti", "partita", "gol", "assist", "rigori", "porta", "altro")


def pezzi(p: pd.DataFrame, regole: Regole) -> pd.DataFrame:
    """I pezzi di `mu` per ogni giocatore (stesso indice di `p`): la loro somma è `mu`.
    `partita` = quanto cambia rispetto a una partita normale per la sua squadra (voto più alto o più basso per la differenza di forza
    tra le squadre, gol/assist/rigori più o meno probabili); `gol`, `assist` e `rigori` sono quelli «di una partita normale»."""
    b = regole.bonus
    conv = Parametri().conversione_rigori
    f = p["fattore"].where(p["fattore"] > 0, 1.0).astype(float)
    gol = p["ruolo"].map(lambda r: float(b.gol[r])).astype(float) * p["e_gol"]
    assist = float(b.assist) * p["e_assist"]
    rigori = p["e_rigori"] * (conv * float(b.rigore_segnato) + (1 - conv) * float(b.rigore_sbagliato))
    porta = pd.Series(np.where(p["ruolo"] == "P", float(b.gol_subito_portiere) * p["gol_subiti"] + float(b.portiere_imbattuto) * p["p_imbattuto"], 0.0),
                      index=p.index)
    out = pd.DataFrame({
        "voti": p["voto_base"], "partita": (p["mu_voto"] - p["voto_base"]) + (gol + assist + rigori) * (1 - 1 / f),
        "gol": gol / f, "assist": assist / f, "rigori": rigori / f, "porta": porta}, index=p.index)
    out["altro"] = p["mu"] - out.sum(axis=1)
    return out


def riferimento(p: pd.DataFrame, parti: pd.DataFrame) -> pd.DataFrame:
    """Il giocatore medio di ogni ruolo: media dei pezzi (e di `mu`, colonna «mu») di chi gioca davvero questa giornata."""
    tutto = parti.assign(mu=p["mu"], ruolo=p["ruolo"], p_voto=p["p_voto"])
    righe = {}
    for r, g in tutto.groupby("ruolo"):
        scelti = g[g["p_voto"] >= P_RIFERIMENTO]
        if scelti.empty:
            scelti = g[g["p_voto"] >= 0.2]
        righe[r] = (scelti if len(scelti) else g)[[*PEZZI, "mu"]].mean()
    return pd.DataFrame(righe).T


def _pct(x: float) -> int:
    return round(float(x) * 100)


def _frase_gioca(x: dict) -> str | None:
    """Il motivo sulla probabilità di giocare, solo quando c'è un dubbio (non cambia il fantavoto «se gioca»: cambia i punti attesi)."""
    stato, p = x.get("stato"), float(x["p_voto"])
    if stato == "infortunato":
        return F("perche.infortunato")
    if stato == "squalificato":
        return F("perche.squalificato")
    if stato == "non_citato" and p < 0.2:
        return F("perche.non_convocato")
    if p < 0.2:
        return F("perche.gioca_improbabile", p=_pct(p))
    if p < 0.5:
        return F("perche.gioca_panchina", p=_pct(p))
    if p < 0.8:
        return F("perche.gioca_dubbio", p=_pct(p))
    return None


def _frase(chiave: str, d: float, x: dict) -> str:
    """Il motivo in una frase semplice. Le frasi sono scritte per intero (e non assemblate): ognuna ha la sua chiave `perche.*`
    (fanta/frasi.py) e la sua traduzione in `fanta/web/testi.js`."""
    su, casa = d > 0, bool(x["in_casa"])
    if chiave == "voti":
        return F("perche.voti_su" if su else "perche.voti_giu")
    if chiave == "partita":
        return F(f"perche.partita_{'su' if su else 'giu'}_{'casa' if casa else 'fuori'}")
    if chiave == "gol":
        return F("perche.gol_su", p=_pct(x["p_gol"])) if su else F("perche.gol_giu")
    if chiave == "assist":
        return F("perche.assist_su" if su else "perche.assist_giu")
    if chiave == "rigori":
        return F("perche.rigori_su" if su else "perche.rigori_giu")
    if chiave == "porta":
        return F("perche.porta_su" if su else "perche.porta_giu", p=_pct(x["p_imbattuto"]))
    return F("perche.altro_su" if su else "perche.altro_giu")


def calcola(p: pd.DataFrame, regole: Regole) -> tuple[pd.Series, pd.Series]:
    """Per ogni giocatore di `p`: (lista di motivi, fantavoto atteso medio del suo ruolo).
    Un motivo è `{"chiave", "testo", "frase", "effetto"}` (`frase` = come tradurre `testo`, vedi fanta/frasi.py); `effetto` è in fantavoti rispetto al giocatore medio del ruolo, con segno
    (null per «gioca N%», che non cambia il fantavoto «se gioca»). Al massimo MAX_MOTIVI, dal più pesante."""
    if p.empty:
        return pd.Series(dtype=object), pd.Series(dtype=float)
    parti = pezzi(p, regole)
    rif = riferimento(p, parti)
    differenze = parti - rif.loc[p["ruolo"], list(PEZZI)].set_axis(p.index)
    medio = p["ruolo"].map(rif["mu"])
    motivi = []
    ricerca = p[["ruolo", "stato", "p_voto", "in_casa", "p_gol", "p_imbattuto"]].to_dict("records")
    for x, riga in zip(ricerca, differenze.to_dict("records")):
        numerici = sorted(((k, v) for k, v in riga.items() if abs(v) >= SOGLIA), key=lambda kv: -abs(kv[1]))
        gioca = _frase_gioca(x)
        scelti = numerici[:MAX_MOTIVI - (1 if gioca else 0)]
        lista = [{"chiave": "gioca", "testo": gioca, "frase": di(gioca), "effetto": None}] if gioca else []
        for k, v in scelti:
            testo = _frase(k, v, x)
            lista.append({"chiave": k, "testo": testo, "frase": di(testo), "effetto": round(float(v), 2)})
        motivi.append(lista)
    return pd.Series(motivi, index=p.index, dtype=object), medio.round(2)
