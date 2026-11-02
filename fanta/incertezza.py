"""Incertezza ONESTA dei punti attesi di una formazione: la fascia in cui cadono i punti veri 8 volte su 10.

La simulazione della formazione (formazione.Valutatore) rende casuali solo chi prende voto e il voto per il modificatore difesa:
la sua deviazione (`dev` simulata, di solito 1-5 punti) serve a confrontare due formazioni, ma è molto più stretta dello scarto
vero, perché gol, assist e voti di chi gioca restano fissi al loro valore atteso. Qui la fascia si calibra sul backtest
(punti attesi contro punti fatti, solo con i dati di prima di ogni giornata):

    scarto tipico = radice(FISSO² + dev simulata²)
    fascia 80%    = da atteso + Q_BASSO × scarto tipico  a  atteso + Q_ALTO × scarto tipico

FISSO viene dai quadrati degli scarti veri (meno la parte già spiegata dalla simulazione); Q_BASSO e Q_ALTO sono il 10° e il
90° percentile degli scarti divisi per lo scarto tipico. Provata anche una parte che cresce con i bonus attesi dei titolari
(gol, assist, rigori): non prevede quali giornate vanno peggio (correlazione circa 0), quindi non c'è.
Il calcolo NON cambia le scelte: stesse formazioni e stessi punti attesi, cambia solo la fascia mostrata.
Rifare la misura: `python -m fanta verifica --incertezza` (stampa scarti, copertura e le costanti da copiare in CALIBRAZIONE).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

CONFIDENZA = 0.8
Z_80 = 1.2816       # per una normale, il 10° e il 90° percentile stanno a ±1,2816 deviazioni dalla media
# Misurate il 30/10/2026 con `verifica --incertezza` su 913 casi (93 rose della lega e 820 rose estratte a sorte,
# stagioni 2025-26 e 2026-27); dettagli e copertura in docs/INCERTEZZA.md.
CALIBRAZIONE = {"fisso": 6.47, "q_basso": -1.18, "q_alto": 1.25, "casi": 913, "casi_lega": 93}
MIN_CASI_LEGA = 200        # con meno casi sulle rose vere della lega la fascia è «indicativa»


def scarto_tipico(dev: float, cal: dict | None = None) -> float:
    c = cal or CALIBRAZIONE
    return math.sqrt(c["fisso"] ** 2 + dev ** 2)


def intervallo(atteso: float, dev: float, cal: dict | None = None) -> dict:
    """{basso, alto, confidenza, indicativo}: dove cadono i punti veri con probabilità CONFIDENZA (`dev` = deviazione simulata)."""
    c = cal or CALIBRAZIONE
    s = scarto_tipico(dev, c)
    return {"basso": round(atteso + c["q_basso"] * s, 1), "alto": round(atteso + c["q_alto"] * s, 1),
            "confidenza": CONFIDENZA, "indicativo": c.get("casi_lega", 0) < MIN_CASI_LEGA}


def dev_onesta(dev: float, cal: dict | None = None) -> float:
    """La deviazione coerente con la fascia: metà della sua larghezza divisa per 1,28 (come per una normale).
    È il campo `dev` delle risposte; quella della simulazione resta in `dev_simulata`."""
    c = cal or CALIBRAZIONE
    return (c["q_alto"] - c["q_basso"]) / (2 * Z_80) * scarto_tipico(dev, c)


def campi(atteso: float, dev: float) -> dict:
    """I campi da mettere in una risposta: `dev` (onesta), `dev_simulata`, `intervallo`."""
    return {"dev": round(dev_onesta(dev), 1), "dev_simulata": round(float(dev), 1), "intervallo": intervallo(atteso, dev)}


# ---------------------------------------------------------------- misura (backtest)
def misura(d, regole, par, giornate, rose=None, simulazioni: int = 300, sintetiche: int = 20) -> pd.DataFrame:
    """Un caso per rosa e giornata: punti attesi, dev simulata e punti fatti (solo dati precedenti)."""
    from . import verifica
    casi: list[dict] = []
    for stagione, g in giornate:
        verifica.verifica_giornata(d, stagione, g, regole, par, rose, simulazioni, casi=casi, sintetiche=sintetiche)
    t = pd.DataFrame(casi)
    if len(t):
        t["scarto"] = t["reale"] - t["atteso"]
    return t


def calibra(casi: pd.DataFrame) -> dict:
    """Le costanti dai casi: FISSO dai quadrati degli scarti meno dev², poi i quantili degli scarti normalizzati."""
    s = casi["scarto"].to_numpy(float)
    dev2 = casi["dev"].to_numpy(float) ** 2
    fisso = math.sqrt(max(float(np.mean(s ** 2 - dev2)), 0.0))
    z = s / np.sqrt(fisso ** 2 + dev2)
    q_basso, q_alto = (float(x) for x in np.percentile(z, (10, 90)))
    return {"fisso": round(fisso, 2), "q_basso": round(q_basso, 2), "q_alto": round(q_alto, 2), "casi": int(len(s)),
            "casi_lega": int((casi["tipo"] == "lega").sum()) if "tipo" in casi else int(len(s))}


def copertura(casi: pd.DataFrame, cal: dict | None = None, vecchia: bool = False) -> dict:
    """Quota dei punti fatti dentro la fascia 10-90%. `vecchia` = la fascia di prima, atteso ± 1,28 × dev simulata."""
    if not len(casi):
        return {"casi": 0}
    if vecchia:
        basso, alto = casi["atteso"] - Z_80 * casi["dev"], casi["atteso"] + Z_80 * casi["dev"]
    else:
        f = [intervallo(a, dv, cal) for a, dv in zip(casi["atteso"], casi["dev"])]
        basso = pd.Series([x["basso"] for x in f], index=casi.index)
        alto = pd.Series([x["alto"] for x in f], index=casi.index)
    dentro = (casi["reale"] >= basso) & (casi["reale"] <= alto)
    return {"casi": int(len(casi)), "dentro": round(float(dentro.mean()), 3),
            "sotto": round(float((casi["reale"] < basso).mean()), 3), "sopra": round(float((casi["reale"] > alto).mean()), 3),
            "larghezza": round(float((alto - basso).mean()), 1)}


def riepilogo(casi: pd.DataFrame) -> dict:
    """Lo scarto vero (punti fatti - attesi): media, deviazione standard, 10° e 90° percentile, e la dev simulata media."""
    s = casi["scarto"]
    return {"casi": int(len(s)), "media": round(float(s.mean()), 2), "dev": round(float(s.std()), 2),
            "q10": round(float(s.quantile(0.1)), 1), "q90": round(float(s.quantile(0.9)), 1),
            "dev_simulata": round(float(casi["dev"].mean()), 2)}


def rapporto(casi: pd.DataFrame, scrivi=print) -> dict:
    """Stampa scarti e copertura (prima/dopo, in campione e fuori campione) e restituisce le costanti da usare."""
    cal = calibra(casi)
    scrivi(f"Scarto vero (fatti - attesi), tutti: {riepilogo(casi)}")
    for (st, tipo), g in casi.groupby(["stagione", "tipo"]):
        scrivi(f"  {st} {tipo:<9} scarto {riepilogo(g)}")
        scrivi(f"  {'':<17} fascia di prima {copertura(g, vecchia=True)}  calibrata {copertura(g, cal)}")
    for nome, a in (("una stagione -> l'altra", "stagione"), ("rose sintetiche -> rose della lega", "tipo")):
        for v in sorted(casi[a].unique()):
            if a == "tipo" and v != "sintetica":
                continue
            prova = casi[casi[a] != v]
            if len(prova):
                scrivi(f"  fuori campione ({nome}, tarata su {v}): {copertura(prova, calibra(casi[casi[a] == v]))}")
    scrivi(f"Costanti da copiare in incertezza.CALIBRAZIONE: {cal}")
    return cal
