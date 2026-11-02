"""Seconda fonte di probabili formazioni (feed RSS di Sosfanta) in MODALITÀ OMBRA: si raccoglie e si misura, il modello NON la legge.

Rispetto del sito: una sola richiesta al feed ogni INTERVALLO_MIN minuti al massimo (e solo quando l'aggiornamento generale gira),
User-Agent che dice chi siamo, niente altre pagine, nessun testo conservato (solo nome abbinato, segnale, link e ora).
Ogni segnale va alla prossima giornata ancora da giocare; gli articoli precedenti all'ultima partita della giornata prima sono ignorati.
Misura: `verifica --fonti probabili_fonte2` (verifica_probabili_fonte2.py). Righe in tabella `probabili_fonte2`.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Callable

from . import archivio, nomi, rete
from .fonti import sosfanta

INTERVALLO_MIN = 30
ETA_MASSIMA = timedelta(days=7)
CHIAVE = "probabili-fonte2"


def scarica_feed() -> bytes:
    return rete.scarica(sosfanta.URL_FEED, headers={"User-Agent": sosfanta.USER_AGENT}).content


def _squadra_della_voce(indice: nomi.Indice, voce: dict) -> str | None:
    squadre = {c for c in voce["categorie"] if indice.e_squadra_serie_a(c)}
    return next(iter(squadre)) if len(squadre) == 1 else None


def abbina(indice: nomi.Indice, nome: str, squadra: str | None) -> int | None:
    """Codice calciatore, o None. Un nome ambiguo o una squadra di Serie A non si abbinano mai."""
    if indice.e_squadra_serie_a(nome):
        return None
    for forma in dict.fromkeys([nome, nome.split()[-1]]):
        e = indice.cerca(forma, squadra=squadra)
        if e.trovato:
            return e.calciatore.id
    # il listone scrive «Maignan M.»: il solo cognome vale se è unico (nella squadra, se la si conosce)
    cognome = nomi.normalizza(nome.split()[-1])
    if len(cognome) < 4:
        return None
    candidati = [c for c in indice.calciatori if nomi.normalizza(c.nome).split()[:1] == [cognome]
                 and (not squadra or indice.squadra_corrisponde(squadra, c))]
    return candidati[0].id if len(candidati) == 1 else None


def righe_da_feed(contenuto: bytes | str, indice: nomi.Indice, stagione: str, giornata: int, dal: datetime, rilevato: str) -> tuple[list[dict], int]:
    """(righe da scrivere, quanti nomi citati non sono stati abbinati)."""
    righe, non_abbinati = [], 0
    for voce in sosfanta.leggi_feed(contenuto):
        if not sosfanta.e_utile(voce) or datetime.fromisoformat(voce["pubblicato"]) < dal:
            continue
        squadra = _squadra_della_voce(indice, voce)
        visti = set()
        for s in sosfanta.segnali(voce):
            cid = abbina(indice, s["nome"], squadra)
            if cid is None:
                non_abbinati += 1
                continue
            if cid in visti:
                continue
            visti.add(cid)
            righe.append({"stagione": stagione, "giornata": giornata, "fonte": sosfanta.FONTE, "calciatore_id": cid,
                          "squadra": squadra, "titolare": {"titolare": 1, "fuori": 0}.get(s["segnale"]),
                          "percentuale": s["percentuale"], "segnale": s["segnale"], "link": voce["link"],
                          "pubblicato": voce["pubblicato"], "rilevato": rilevato})
    return righe, non_abbinati


def raccogli(db: sqlite3.Connection, stagione: str, calciatori: list, adesso: datetime | None = None,
             scarica: Callable[[], bytes] = scarica_feed, scrivi: Callable[[str], None] = print) -> dict:
    """Una raccolta, se è passato abbastanza tempo. Torna {"motivo", "righe", "non_abbinati"}."""
    adesso = adesso or datetime.now()
    esito = {"motivo": "", "righe": 0, "non_abbinati": 0}
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = ?", (CHIAVE,)).fetchone()
    if r and adesso - datetime.fromisoformat(r[0]) < timedelta(minutes=INTERVALLO_MIN):
        esito["motivo"] = "già raccolta di recente"
        return esito
    g = db.execute("SELECT MIN(giornata) FROM partite WHERE stagione = ? AND giocata = 0", (stagione,)).fetchone()[0]
    if g is None:
        esito["motivo"] = "nessuna giornata da giocare"
        return esito
    ultima = db.execute("SELECT MAX(data) FROM partite WHERE stagione = ? AND giocata = 1 AND giornata < ?", (stagione, g)).fetchone()[0]
    dal = adesso - ETA_MASSIMA
    if ultima:
        try:
            dal = max(dal, datetime.fromisoformat(ultima.replace("/", "-")[:16]))
        except ValueError:
            pass
    quando = adesso.isoformat(timespec="seconds")
    righe, esito["non_abbinati"] = righe_da_feed(scarica(), nomi.Indice(calciatori), stagione, g, dal, quando)
    esistenti = {(x[0], x[1]) for x in db.execute(
        "SELECT calciatore_id, link FROM probabili_fonte2 WHERE stagione = ? AND giornata = ? AND fonte = ?", (stagione, g, sosfanta.FONTE))}
    nuove = [x for x in righe if (x["calciatore_id"], x["link"]) not in esistenti]      # la prima rilevazione resta quella buona
    esito["righe"] = archivio.inserisci(db, "probabili_fonte2", nuove)
    archivio.segna(db, CHIAVE, quando)
    return esito
