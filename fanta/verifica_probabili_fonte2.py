"""Misura della seconda fonte di probabili (`probabili_fonte2`, feed Sosfanta) contro le probabili di Fantacalcio.it (`probabili`).
È la parte «probabili_fonte2» di `verifica --fonti`. Il modello NON cambia: si dice solo quanto la fonte varrebbe.

Tre numeri per stagione:
- accordo: sui giocatori dati «fuori» o «titolare» dalla fonte 2 e presenti anche nelle probabili, quante volte la pensano uguale;
- anticipo: per i «fuori» che le probabili danno poi infortunato/squalificato, quante ore prima lo diceva la fonte 2 (mediana;
  positivo = la fonte 2 era in anticipo);
- errore di presenza: Brier della probabilità di prendere voto, come la conosceva l'app nel momento della raccolta (ultima
  rilevazione di `probabili_storia` fino a quel momento) contro la stessa corretta dal segnale. Correzione: fuori -> al più
  P_FUORI, titolare -> almeno P_TITOLARE, dubbio -> al più P_DUBBIO. Variazione negativa = la fonte aiuta.
Regola di promozione (docs/archivio/PIANO-DATI.md): errore almeno 0,5% più basso e miglioramento in almeno 2 delle ultime 3 stagioni;
con una sola stagione resta «solo indicativo».
"""
from __future__ import annotations

import sqlite3
from statistics import median

import pandas as pd

from .fonti.sosfanta import FONTE
from .verifica_fonti import SOGLIA_ERRORE, STAGIONI_MIN_MIGLIORI

NOME = "probabili_fonte2"
P_FUORI, P_TITOLARE, P_DUBBIO = 0.03, 0.85, 0.60
MIN_RIGHE = 30            # sotto questo numero di segnali in una stagione il verdetto non si dà
FUORI_UFFICIALE = ("infortunato", "squalificato", "non_convocato")


def _ore(a: str, b: str) -> float:
    from datetime import datetime
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 3600


def _p_app(stato, perc, dubbio) -> float:
    from .modello import _p_da_probabili
    return _p_da_probabili(stato, None if perc is None or pd.isna(perc) else float(perc), bool(dubbio))


def _corretta(p: float, segnale: str) -> float:
    if segnale == "fuori":
        return min(p, P_FUORI)
    if segnale == "titolare":
        return max(p, P_TITOLARE)
    return min(p, P_DUBBIO)


def misura_stagione(db: sqlite3.Connection, stagione: str) -> dict | None:
    """Numeri di una stagione, o None se non ci sono segnali."""
    segn = db.execute("SELECT giornata, calciatore_id, segnale, pubblicato, rilevato FROM probabili_fonte2 "
                      "WHERE stagione = ? AND fonte = ? ORDER BY pubblicato", (stagione, FONTE)).fetchall()
    if not segn:
        return None
    storia: dict[tuple[int, int], list] = {}
    for g, c, stato, perc, dub, ril in db.execute(
            "SELECT giornata, calciatore_id, stato, percentuale, in_dubbio, rilevato FROM probabili_storia "
            "WHERE stagione = ? AND fonte = 'fantacalcio' ORDER BY rilevato", (stagione,)):
        storia.setdefault((g, c), []).append((ril, stato, perc, dub))
    presi = {(g, c) for g, c in db.execute(
        "SELECT giornata, calciatore_id FROM voti WHERE stagione = ? AND "
        "(voto_red IS NOT NULL OR voto_stat IS NOT NULL OR voto_ita IS NOT NULL)", (stagione,))}
    giocate = {g for (g,) in db.execute("SELECT DISTINCT giornata FROM voti WHERE stagione = ?", (stagione,))}

    ultimo: dict[tuple[int, int], tuple] = {}          # l'ultima notizia vince
    primo_fuori: dict[tuple[int, int], str] = {}
    for g, c, s, pub, ril in segn:
        ultimo[(g, c)] = (s, ril)
        if s == "fuori":
            primo_fuori.setdefault((g, c), pub)

    d = {"stagione": stagione, "segnali": len(ultimo), "accordo": 0, "contrasto": 0, "ore_anticipo": [], "fuori_solo_fonte2": 0,
         "righe": 0, "brier_prima": 0.0, "brier_dopo": 0.0}
    for (g, c), (s, ril) in ultimo.items():
        h = storia.get((g, c), [])
        if h and s in ("fuori", "titolare"):                       # accordo con l'ultima rilevazione di Fantacalcio.it
            _, stato, perc, _ = h[-1]
            ufficiale_fuori = stato in FUORI_UFFICIALE
            ufficiale_titolare = stato == "titolare" and (perc is None or pd.isna(perc) or perc >= 50)
            if (s == "fuori" and ufficiale_fuori) or (s == "titolare" and ufficiale_titolare):
                d["accordo"] += 1
            elif (s == "fuori" and stato in ("titolare", "panchina")) or (s == "titolare" and (ufficiale_fuori or stato == "panchina")):
                d["contrasto"] += 1
        if g in giocate and h:                                     # effetto sulla presenza
            note = [x for x in h if x[0] <= ril]
            if note:
                _, stato, perc, dub = note[-1]
                p = _p_app(stato, perc, dub)
                y = 1.0 if (g, c) in presi else 0.0
                d["righe"] += 1
                d["brier_prima"] += (p - y) ** 2
                d["brier_dopo"] += (_corretta(p, s) - y) ** 2
    for (g, c), pub in primo_fuori.items():
        ufficiali = [x[0] for x in storia.get((g, c), []) if x[1] in FUORI_UFFICIALE]
        if ufficiali:
            d["ore_anticipo"].append(_ore(pub, ufficiali[0]))
        else:
            d["fuori_solo_fonte2"] += 1
    return d


def misura(db: sqlite3.Connection) -> dict:
    """{"tabella": DataFrame (una riga per stagione), "verdetto": testo}."""
    righe = []
    for (stagione,) in db.execute("SELECT DISTINCT stagione FROM probabili_fonte2 ORDER BY stagione").fetchall():
        d = misura_stagione(db, stagione)
        if not d:
            continue
        ore = d["ore_anticipo"]
        righe.append({"stagione": stagione, "segnali": d["segnali"], "accordi": d["accordo"], "contrasti": d["contrasto"],
                      "fuori_anticipati": len(ore), "anticipo_ore_mediana": round(median(ore), 1) if ore else None,
                      "fuori_solo_fonte2": d["fuori_solo_fonte2"], "righe_presenza": d["righe"],
                      "brier": d["brier_prima"] / d["righe"] if d["righe"] else None,
                      "variazione_errore_pct": (d["brier_dopo"] / d["brier_prima"] - 1) * 100 if d["brier_prima"] else None})
    tab = pd.DataFrame(righe)
    return {"tabella": tab, "verdetto": giudizio(tab)}


def giudizio(tab: pd.DataFrame) -> str:
    """Stesso criterio delle altre fonti in ombra (errore -0,5% e 2 stagioni su 3); una stagione sola: solo indicativo."""
    if tab.empty:
        return "nessun segnale raccolto ancora: niente da misurare"
    t = tab[tab["variazione_errore_pct"].notna() & (tab["righe_presenza"] >= MIN_RIGHE)].sort_values("stagione").tail(3)
    if t.empty:
        return f"troppo pochi dati (servono almeno {MIN_RIGHE} segnali su giornate già giocate in una stagione): niente da giudicare"
    pesi = t["righe_presenza"]
    pct = float((t["variazione_errore_pct"] * pesi).sum() / pesi.sum())
    migliori = int((t["variazione_errore_pct"] < 0).sum())
    if len(t) < 2:
        return f"errore {pct:+.2f}% su una sola stagione: solo indicativo, non si promuove"
    if pct <= SOGLIA_ERRORE and migliori >= STAGIONI_MIN_MIGLIORI:
        return f"PROMOSSA: errore {pct:+.2f}%, migliora in {migliori} stagioni su {len(t)}"
    return f"non promossa: errore {pct:+.2f}%, migliora in {migliori} stagioni su {len(t)} (servono {SOGLIA_ERRORE}% e {STAGIONI_MIN_MIGLIORI})"
