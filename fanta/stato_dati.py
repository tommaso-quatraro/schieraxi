"""Stato dei dati: da dove arrivano, quanto sono freschi e quanto il modello ci azzecca.

La calibrazione confronta, per ogni gruppo di giocatori delle probabili formazioni (titolare al 90%, in panchina al 30%...),
quanti hanno davvero preso voto con la probabilità che il modello aveva stimato. Serve a capire se i numeri di partenza
(modello._p_da_probabili) vanno corretti: si compila da sola man mano che le giornate vengono giocate.
"""
from __future__ import annotations

import json
import sqlite3

from . import controlli, coppe, fonti_attive, modello, uso

try:                                              # senza foto.py (versione pubblica) le foto sono sempre zero
    from . import foto
except ImportError:
    foto = None

GRUPPI = modello.GRUPPI_PROBABILI      # (nome del gruppo, stato nelle probabili, percentuale minima, percentuale massima esclusa)
MINIMO_PER_GRUPPO = 20      # sotto questo numero di giocatori il confronto è solo indicativo


def calibrazione(db: sqlite3.Connection, stagione: str) -> dict:
    """{"giornate": quante giornate hanno probabili e partite giocate, "gruppi": [{gruppo, n, osservato, previsto}]}.
    "osservato" = quota di giocatori che hanno preso voto; "previsto" = media della probabilità stimata dal modello."""
    righe = db.execute(
        "SELECT p.giornata, p.stato, p.percentuale, p.in_dubbio, v.voto_red IS NOT NULL "
        "FROM probabili p JOIN partite g ON g.id = p.partita_id AND g.giocata = 1 "
        "LEFT JOIN voti v ON v.stagione = p.stagione AND v.giornata = p.giornata AND v.calciatore_id = p.calciatore_id "
        "WHERE p.stagione = ? AND p.fonte = 'fantacalcio'", (stagione,)).fetchall()
    gruppi = []
    for nome, stato, da, a in GRUPPI:
        scelti = [r for r in righe if r[1] == stato and r[2] is not None and da <= r[2] < a]
        if not scelti:
            gruppi.append({"gruppo": nome, "n": 0, "osservato": None, "previsto": None, "indicativo": True})
            continue
        osservato = sum(1 for r in scelti if r[4]) / len(scelti)
        previsto = sum(modello._p_da_probabili(r[1], r[2], bool(r[3])) for r in scelti) / len(scelti)
        gruppi.append({"gruppo": nome, "n": len(scelti), "osservato": round(osservato, 3), "previsto": round(previsto, 3),
                       "indicativo": len(scelti) < MINIMO_PER_GRUPPO})
    return {"giornate": len({r[0] for r in righe}), "gruppi": gruppi}


MIN_GIORNATE = 3          # sotto queste giornate non si corregge niente
MIN_GIOCATORI = 30        # né un gruppo con meno giocatori di questi
LIMITE_FATTORE = 0.15     # la correzione non supera mai il 15% in più o in meno


def fattori_da(c: dict) -> dict[str, float]:
    """Correzione per gruppo = giocatori che hanno davvero preso voto / quelli previsti. Con pochi dati ci si fida poco
    (peso n / (n + 60)) e il valore resta entro il 15%."""
    if c["giornate"] < MIN_GIORNATE:
        return {}
    risultato = {}
    for g in c["gruppi"]:
        if g["n"] >= MIN_GIOCATORI and g["previsto"]:
            grezzo = g["osservato"] / g["previsto"]
            fattore = 1 + (grezzo - 1) * g["n"] / (g["n"] + 60)
            risultato[g["gruppo"]] = round(min(1 + LIMITE_FATTORE, max(1 - LIMITE_FATTORE, fattore)), 3)
    return risultato


def fattori(db: sqlite3.Connection, stagione: str) -> dict[str, float]:
    return fattori_da(calibrazione(db, stagione))


def ombra(db: sqlite3.Connection) -> dict:
    """Fonti raccolte «in ombra» (il modello non le legge): righe in tabella e ultima raccolta."""
    def conta(tabella: str, colonna_ora: str) -> dict:
        n, ultima = db.execute(f"SELECT COUNT(*), MAX({colonna_ora}) FROM {tabella}").fetchone()
        return {"righe": n, "ultima": ultima}
    pf2 = conta("probabili_fonte2", "rilevato")
    pf2["giornate"] = db.execute("SELECT COUNT(DISTINCT stagione || '/' || giornata) FROM probabili_fonte2").fetchone()[0]
    return {"partite_extra": conta("partite_extra", "rilevato"), "probabili_fonte2": pf2}


def riepilogo(db: sqlite3.Connection, stagione: str) -> dict:
    """Tutto quello che serve alla pagina "Stato dei dati". `registro`: quanto ci hanno preso i numeri mostrati prima di ogni
    giornata (I1-I3, `registro_giornate.riepilogo`). `consiglio`: gli indicatori del consiglio di formazione C1-C4, sommati sui
    Diari di tutti (`indicatori_consiglio.riepilogo`)."""
    from . import indicatori_consiglio, registro_giornate      # qui dentro: importano consigli, che importa questo modulo
    agg = []
    for cosa, quando, dettaglio in db.execute("SELECT cosa, quando, dettaglio FROM aggiornamenti ORDER BY cosa"):
        try:
            errori = json.loads(dettaglio) if dettaglio and dettaglio.startswith("[") else []
        except ValueError:
            errori = []
        agg.append({"cosa": cosa, "quando": quando, "errori": errori})
    partite = db.execute("SELECT COUNT(*), COALESCE(SUM(giocata), 0) FROM partite WHERE stagione = ?", (stagione,)).fetchone()
    probabili = db.execute("SELECT giornata, COUNT(*), MAX(rilevato) FROM probabili WHERE stagione = ? AND fonte = 'fantacalcio' "
                           "GROUP BY giornata ORDER BY giornata", (stagione,)).fetchall()
    return {
        "stagione": stagione, "aggiornamenti": agg,
        "calciatori": db.execute("SELECT COUNT(*) FROM calciatori").fetchone()[0],
        "partite": {"totali": partite[0], "giocate": partite[1]},
        "voti": db.execute("SELECT COUNT(*) FROM voti WHERE stagione = ?", (stagione,)).fetchone()[0],
        "probabili": [{"giornata": g, "giocatori": n, "rilevato": q} for g, n, q in probabili],
        "controlli": controlli.leggi(db, stagione),
        "ombra": ombra(db),
        "foto": len(foto.disponibili()) if foto else 0,
        "fonti": fonti_attive.stato(),
        "uso": uso.riepilogo(),
        "coppe_fino": coppe.aggiornate_fino().isoformat(),
        "calibrazione": {**(c := calibrazione(db, stagione)), "fattori": fattori_da(c)},
        "registro": registro_giornate.riepilogo(db),
        "consiglio": indicatori_consiglio.riepilogo(),
    }
