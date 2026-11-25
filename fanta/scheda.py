"""Scheda di un giocatore: tutto quello che l'archivio sa su di lui, in un dizionario (lo userà anche l'app)."""
from __future__ import annotations

import sqlite3
from datetime import datetime

FONTI_VOTO = {"redazione": ("voto_red", "fv_red"), "statistico": ("voto_stat", "fv_stat"), "italia": ("voto_ita", "fv_ita")}


def rendimento(avanzate: dict | None, ruolo: str, con_voto: int, regole) -> dict | None:
    """Quanto il giocatore rende sopra (o sotto) le occasioni che ha avuto: (gol - xG) e (assist - xA) valutati
    con i bonus della lega, per partita con voto. Positivo = sta avendo fortuna/precisione, tende a calare."""
    if not avanzate or not avanzate.get("minuti") or not con_voto:
        return None
    gol, xg = avanzate.get("gol") or 0, avanzate.get("xg") or 0.0
    ass, xa = avanzate.get("assist") or 0, avanzate.get("xa") or 0.0
    b = regole.bonus
    if ruolo not in b.gol:
        return None
    extra = (b.gol[ruolo] * (gol - xg) + b.assist * (ass - xa)) / con_voto
    return {"sovra_rendimento": round(extra, 2), "gol_meno_xg": round(gol - xg, 2), "assist_meno_xa": round(ass - xa, 2)}


def con_voto_fino_al(db: sqlite3.Connection, calciatore_id: int, stagione: str, giorno: str | None,
                     fonte_voto: str = "redazione") -> int:
    """Le partite con voto del giocatore giocate entro `giorno` (compreso), la finestra delle statistiche avanzate
    (`dati_fino_al`): il rendimento divide per queste i gol meno i gol attesi della fonte. Con tutte le partite con voto, a fonte
    ferma il numero calava da solo a ogni giornata (#862). 0 senza giorno."""
    if not giorno:
        return 0
    col_v = FONTI_VOTO[fonte_voto][0]
    return db.execute(
        f"SELECT COUNT(*) FROM voti v WHERE v.stagione = ? AND v.calciatore_id = ? AND v.{col_v} IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM partite p WHERE p.stagione = v.stagione AND p.giornata = v.giornata "
        "AND (p.casa = v.squadra OR p.trasferta = v.squadra) AND substr(p.data, 1, 10) <= ?)",
        (stagione, calciatore_id, giorno)).fetchone()[0]


SOGLIA_ANDAMENTO = 0.6        # di quanto la media delle ultime 3 si stacca da quella della stagione


def andamento(voti: list[dict]) -> str | None:
    """L'andamento dei fantavoti nella scheda (#895: prima lo calcolava la web): `in_crescita` o `in_calo` se la media delle ultime 3
    partite con il voto si stacca di più di 0,6 da quella di tutte, `stabile` altrimenti, `pochi_dati` con meno di 4 voti. None
    senza presenze. `voti` in ordine di giornata, `fv` None = senza voto."""
    if not voti:
        return None
    con = [float(v["fv"]) for v in voti if v.get("fv") is not None]
    if len(con) < 4:
        return "pochi_dati"
    differenza = sum(con[-3:]) / 3 - sum(con) / len(con)
    return "in_crescita" if differenza > SOGLIA_ANDAMENTO else "in_calo" if differenza < -SOGLIA_ANDAMENTO else "stabile"


def scheda(db: sqlite3.Connection, calciatore_id: int, stagione: str, fonte_voto: str = "redazione") -> dict:
    c = db.execute("SELECT * FROM calciatori WHERE id = ?", (calciatore_id,)).fetchone()
    if not c:
        raise ValueError(f"calciatore {calciatore_id} non nel listone")
    col_v, col_fv = FONTI_VOTO[fonte_voto]
    voti = [dict(r) for r in db.execute(
        f"SELECT giornata, {col_v} AS voto, {col_fv} AS fv, gol, assist, ammonizioni, espulsioni, gol_subiti, "
        "rig_segnati, rig_sbagliati, rig_parati, autogol, subentrato, sostituito "
        "FROM voti WHERE stagione = ? AND calciatore_id = ? ORDER BY giornata", (stagione, calciatore_id))]
    giornate_giocate = db.execute("SELECT COUNT(DISTINCT giornata) FROM partite WHERE stagione = ? AND giocata = 1",
                                  (stagione,)).fetchone()[0]
    con_voto = [v for v in voti if v["voto"] is not None]
    n = len(con_voto)
    stagione_fc = {
        "giornate_giocate_serie_a": giornate_giocate,
        "presenze": len(voti), "con_voto": n,
        "media_voto": round(sum(v["voto"] for v in con_voto) / n, 2) if n else None,
        "fantamedia": round(sum(v["fv"] for v in con_voto) / n, 2) if n else None,
        **{k: sum(v[k] for v in voti) for k in ("gol", "assist", "ammonizioni", "espulsioni", "gol_subiti",
                                                 "rig_segnati", "rig_sbagliati", "rig_parati", "autogol")},
        "titolare": sum(1 for v in voti if not v["subentrato"]),
        "ultime_5_fv": [v["fv"] for v in voti[-5:]],
    }
    # Understat (statistiche avanzate)
    us = db.execute("SELECT id, nome, abbinamento FROM understat_giocatori WHERE calciatore_id = ?",
                    (calciatore_id,)).fetchone()
    avanzate = None
    if us:
        t = db.execute(
            "SELECT COUNT(*) AS partite, SUM(minuti) AS minuti, SUM(xg) AS xg, SUM(xa) AS xa, SUM(tiri) AS tiri, "
            "SUM(passaggi_chiave) AS passaggi_chiave, SUM(gol) AS gol, SUM(assist) AS assist, "
            "SUM(rigori_calciati) AS rigori_calciati, SUM(rigori_segnati) AS rigori_segnati, SUM(punizioni) AS punizioni, "
            "SUM(xg_chain) AS xg_chain, SUM(entrato) AS entrato "
            "FROM prestazioni pr JOIN partite_understat pu ON pu.id = pr.understat_partita "
            "WHERE pu.stagione = ? AND pr.understat_giocatore = ?", (stagione, us["id"])).fetchone()
        avanzate = {k: (round(t[k], 2) if isinstance(t[k], float) else t[k]) for k in t.keys()}
        minuti = t["minuti"] or 0
        if minuti:
            avanzate["per_90"] = {k: round((t[k] or 0) * 90 / minuti, 2) for k in ("xg", "xa", "tiri", "passaggi_chiave")}
        avanzate["nome_understat"] = us["nome"]
        avanzate["abbinamento"] = us["abbinamento"]
        # fin dove arrivano i dati della fonte (#862): il giorno dell'ultima partita della stagione con le statistiche
        # nell'archivio, di chiunque (con la fonte ferma i numeri restano quelli di quel giorno, e i client lo scrivono)
        ultima = db.execute("SELECT MAX(pu.data) FROM partite_understat pu WHERE pu.stagione = ? AND EXISTS "
                            "(SELECT 1 FROM prestazioni pr WHERE pr.understat_partita = pu.id)", (stagione,)).fetchone()[0]
        avanzate["dati_fino_al"] = str(ultima)[:10] if ultima else None
        precedenti = db.execute("SELECT stagione, partite, minuti, gol, xg, assist, xa FROM understat_stagione "
                                "WHERE understat_giocatore = ? AND stagione <> ? ORDER BY stagione DESC",
                                (us["id"], stagione)).fetchall()
        avanzate["stagioni_precedenti"] = [dict(r) for r in precedenti]
    # probabili per la prossima giornata
    prob = db.execute("SELECT giornata, stato, percentuale, in_dubbio, diffidato, nota, rilevato FROM probabili "
                      "WHERE stagione = ? AND calciatore_id = ? AND fonte = 'fantacalcio' AND giornata = "
                      "(SELECT MAX(giornata) FROM probabili WHERE stagione = ? AND fonte = 'fantacalcio')",
                      (stagione, calciatore_id, stagione)).fetchone()
    prossima = db.execute(
        "SELECT p.giornata, p.data, p.casa, p.trasferta FROM partite p "
        "WHERE p.stagione = ? AND p.giocata = 0 AND p.data >= ? AND (p.casa = ? OR p.trasferta = ?) "
        "ORDER BY p.data LIMIT 1",   # una partita rinviata con data passata non è la "prossima"
        (stagione, datetime.now().strftime("%Y-%m-%d"), c["squadra_slug"], c["squadra_slug"])).fetchone()
    return {
        "calciatore": dict(c),
        "stagione": stagione_fc,
        "voti": voti,
        "andamento": andamento(voti),
        "avanzate": avanzate,
        "probabile": dict(prob) if prob else None,
        "prossima_partita": dict(prossima) if prossima else None,
    }
