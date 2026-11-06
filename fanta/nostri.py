"""Gol e assist attesi «nostri» (L3b di #165): lo stesso modello, con i soli dati di Fantacalcio.it.

I numeri «nostri» sono quelli di `modello.previsioni` con i dati di `dati(d)` (prestazioni ricostruite dai voti, niente
Understat) e i parametri di `parametri()`. Oggi servono solo a misurare (scenario `solo_fantacalcio` di `verifica --pacchetti`):
la produzione non cambia fino alla Fase G1 del piano `docs/superpowers/plans/2026-11-06-gol-attesi-nostri.md`.

Chi cambia `parametri` o la formula usata dai nostri alza `VERSIONE` nella stessa pull request: la misura dal vivo conta
solo le giornate della stessa versione.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .modello import Dati, Parametri
from .modello import previsioni as _previsioni_modello
from .regole import Regole

# 2: rigori con memoria lunga divisi nella squadra, minuti dalle presenze con voto (Fase B)
# 3: forza delle squadre tarata sui soli gol, livello recente del campionato, medie del ruolo pesate (Fase C)
VERSIONE: str = "3"

# Minuti giocati per presenza, da «entrato» e «uscito» dei voti di Fantacalcio.it (che non dà i minuti), per
# (subentrato, sostituito). Medie dei minuti veri di Understat sull'archivio di sviluppo (2025-26 e 2026-27, circa 14.400
# presenze, misura del 5/11/2026): 89,7 · 70,9 · 19,0 · 30,3 (quest'ultima su 29 casi soltanto).
MINUTI_STIMATI = {(0, 0): 90.0, (0, 1): 71.0, (1, 0): 19.0, (1, 1): 30.0}

# Fasce dei gol attesi per dire se sono tarati (indicatore I4)
FASCE_GOL = (0.0, 0.05, 0.10, 0.20, 0.30, 0.45, np.inf)
FASCE_GOL_NOMI = ("0-0,05", "0,05-0,10", "0,10-0,20", "0,20-0,30", "0,30-0,45", "0,45 e più")
MIN_CASI_FASCIA = 50                # sotto, lo scarto di una fascia è quasi solo caso: non entra in `scarto_gol`


def minuti_stimati(voti: pd.DataFrame) -> pd.Series:
    """Minuti stimati di ogni riga dei voti (vedi `MINUTI_STIMATI`); un dato mancante vale «no»."""
    sub, sos = (pd.to_numeric(voti[c], errors="coerce").fillna(0).astype(int).clip(0, 1) for c in ("subentrato", "sostituito"))
    return pd.Series([MINUTI_STIMATI[(a, b)] for a, b in zip(sub, sos)], index=voti.index, dtype=float)


def dati(d: Dati) -> Dati:
    """Copia dei dati come se avessimo solo Fantacalcio.it: niente xG e xA (giocatori e squadre: la forza delle squadre viene
    dai soli gol) e prestazioni ricostruite dai voti, una riga per presenza (anche chi resta senza voto): minuti stimati da
    entrato e uscito, rigori calciati = segnati + sbagliati, gol con i rigori (come Understat; nei voti «gol» li esclude).
    Le prestazioni di Understat non si leggono; la partita è quella di Fantacalcio.it."""
    v = d.voti
    num = lambda c: pd.to_numeric(v[c], errors="coerce").fillna(0)  # noqa: E731
    pr = pd.DataFrame({"stagione": v["stagione"], "giornata": v["giornata"], "data": v["data"], "t": v["t"],
                       "squadra": v["squadra"], "calciatore_id": v["calciatore_id"], "minuti": minuti_stimati(v),
                       "gol": num("gol") + num("rig_segnati"), "assist": num("assist"), "rigori_segnati": num("rig_segnati"),
                       "rigori_calciati": num("rig_segnati") + num("rig_sbagliati"), "xg": np.nan, "xa": np.nan})
    partita = pd.concat([d.partite[["stagione", "giornata", c, "id"]].rename(columns={c: "squadra", "id": "understat_partita"})
                         for c in ("casa", "trasferta")]).drop_duplicates(["stagione", "giornata", "squadra"])
    pr = pr.merge(partita, on=["stagione", "giornata", "squadra"], how="left")
    rig = pr.groupby(["understat_partita", "squadra"])["rigori_calciati"].sum().rename("rigori_squadra")
    pa = d.partite.copy()
    pa["xg_casa"] = np.nan
    pa["xg_trasferta"] = np.nan
    return replace(d, prestazioni=pr.join(rig, on=["understat_partita", "squadra"]), partite=pa)


# Forza delle squadre dai soli gol (senza xG): tarata il 6/11/2026 con `prove/tara_forza_gol.py` sul 2025-26 dalla 5ª giornata,
# controllata sul 2026-27 (pull request della Fase C). Più partite fittizie a forza media perché i gol veri sono più rumorosi
# degli xG; il livello recente (memoria 0,85) segue i gol del campionato, che nel 2026-27 sono il 24% in più.
# Onestà sulla taratura: k_squadre 8 (invece di 12, pari sul 2025-26) è stato preferito guardando anche il controllo 2026-27, e la
# memoria 0,85 è stata scelta con i gol attesi/veri del 2025-26: i miglioramenti misurati non sono del tutto «fuori campione».
FORZA = {"decadimento_squadre": 0.99, "k_squadre": 8.0, "decadimento_base": 0.85}


def parametri(par: Parametri | None = None) -> Parametri:
    """I parametri dei nostri: quelli dati (o i predefiniti) senza xG e xA, perché i nostri non li hanno, e con le correzioni
    tarate sui gol veri: rigori con memoria lunga divisi nella squadra e minuti dalle sole presenze con voto (Fase B del
    piano), forza delle squadre di `FORZA` con il livello recente del campionato e medie del ruolo pesate (Fase C)."""
    return replace(par or Parametri(), peso_xg=0.0, peso_xa=0.0, rigori_squadra=True, minuti_con_voto=True,
                   medie_ruolo_pesate=True, **FORZA)


def gol_attesi(prev: pd.DataFrame, par: Parametri) -> pd.Series:
    """Gol attesi se gioca, rigori compresi: gol su azione più i rigori calciati attesi per la quota che va a segno. È l'unica
    definizione: la usano la misura nel passato (`verifica_pacchetti`) e quella dal vivo."""
    return prev["e_gol"] + par.conversione_rigori * prev["e_rigori"]


def previsioni(d: Dati, stagione: str, giornata: int, regole: Regole, probabili: pd.DataFrame | None = None,
               giocatori: pd.DataFrame | None = None, fattori_probabili: dict[str, float] | None = None,
               taratura: dict | None = None) -> pd.DataFrame:
    """`modello.previsioni` con i dati e i parametri dei nostri (gli argomenti hanno lo stesso significato)."""
    return _previsioni_modello(dati(d), stagione, giornata, regole, parametri(), probabili=probabili, giocatori=giocatori,
                               fattori_probabili=fattori_probabili, taratura=taratura)
