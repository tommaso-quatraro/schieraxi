"""Controlli di coerenza dei dati scaricati (docs/archivio/PIANO-DATI.md, 4): dopo ogni aggiornamento si controlla che i numeri tornino
(10 partite per giornata, voti presenti, xG dei giocatori contro quello della partita, 11 titolari per squadra, gol dei voti e gol
presi dai portieri contro il risultato). Il risultato sta nella tabella `controlli` (l'ultimo per stagione e controllo) e si vede nello
«stato dei dati». Un controllo che non riesce non ferma niente: segnala soltanto. Quelli di `CONTANO_COME_ERRORI` contano anche tra
gli errori della corsa.

Esiti: "ok", "avviso" (qualcosa non torna, di solito una fonte da guardare), "errore" (dati sicuramente sbagliati).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Callable

PARTITE_PER_GIORNATA = 10
MIN_VOTI_GIORNATA = 180          # in una giornata finita ne arrivano circa 280
SOGLIA_XG = 1.0                  # differenza massima tra l'xG della partita e la somma di quello dei giocatori
QUOTA_TOLLERATA = 0.02           # fino al 2% di righe fuori misura è rumore delle fonti, oltre è un avviso
TITOLARI = 11

Esito = tuple[str, float | None, str]     # (esito, valore, dettaglio)


def _percento(n: int, tot: int) -> str:
    return f"{n} su {tot}"


def partite_per_giornata(db: sqlite3.Connection, stagione: str) -> Esito | None:
    righe = db.execute("SELECT giornata, COUNT(*) FROM partite WHERE stagione = ? GROUP BY giornata", (stagione,)).fetchall()
    if not righe:
        return None
    storte = [(g, n) for g, n in righe if n != PARTITE_PER_GIORNATA]
    if storte:
        elenco = ", ".join(f"g{g}: {n}" for g, n in storte[:8])
        return "errore", float(len(storte)), f"{len(storte)} giornate senza {PARTITE_PER_GIORNATA} partite ({elenco})"
    return "ok", 0.0, f"{len(righe)} giornate, tutte con {PARTITE_PER_GIORNATA} partite"


def voti_per_giornata(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """Le giornate finite devono avere i voti (almeno MIN_VOTI_GIORNATA giocatori con voto)."""
    finite = [g for g, in db.execute("SELECT giornata FROM partite WHERE stagione = ? GROUP BY giornata "
                                     "HAVING COUNT(*) = ? AND SUM(giocata) = COUNT(*)", (stagione, PARTITE_PER_GIORNATA))]
    if not finite:
        return None
    con_voto = dict(db.execute("SELECT giornata, SUM(voto_red IS NOT NULL) FROM voti WHERE stagione = ? GROUP BY giornata",
                               (stagione,)).fetchall())
    poche = [g for g in finite if (con_voto.get(g) or 0) < MIN_VOTI_GIORNATA]
    if poche:
        return "avviso", float(len(poche)), f"giornate finite con pochi voti: {', '.join(f'g{g}' for g in poche[:8])}"
    return "ok", 0.0, f"{len(finite)} giornate finite, tutte con i voti"


def somma_xg(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """La somma dell'xG dei giocatori di una squadra deve somigliare all'xG della partita (Understat)."""
    righe = db.execute("""
        SELECT u.id, u.xg_casa, u.xg_trasferta,
               (SELECT SUM(xg) FROM prestazioni p WHERE p.understat_partita = u.id AND p.squadra = u.casa),
               (SELECT SUM(xg) FROM prestazioni p WHERE p.understat_partita = u.id AND p.squadra = u.trasferta)
        FROM partite_understat u WHERE u.stagione = ? AND u.scaricata = 1 AND u.xg_casa IS NOT NULL""", (stagione,)).fetchall()
    if not righe:
        return None
    lontane = [r[0] for r in righe
               if r[3] is None or r[4] is None or abs(r[1] - r[3]) > SOGLIA_XG or abs(r[2] - r[4]) > SOGLIA_XG]
    quota = len(lontane) / len(righe)
    dettaglio = f"{_percento(len(lontane), len(righe))} partite con la somma xG dei giocatori lontana più di {SOGLIA_XG:g} dal totale"
    return ("ok" if quota <= QUOTA_TOLLERATA else "avviso"), float(len(lontane)), dettaglio


def titolari_per_squadra(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """Nell'ultima giornata di probabili ogni squadra deve avere 11 titolari."""
    ultima = db.execute("SELECT MAX(giornata) FROM probabili WHERE stagione = ? AND fonte = 'fantacalcio'", (stagione,)).fetchone()[0]
    if ultima is None:
        return None
    conti = db.execute("SELECT squadra, SUM(stato = 'titolare') FROM probabili WHERE stagione = ? AND giornata = ? "
                       "AND fonte = 'fantacalcio' GROUP BY squadra", (stagione, ultima)).fetchall()
    storte = [(s, int(n or 0)) for s, n in conti if int(n or 0) != TITOLARI]
    squadre_attese = 2 * db.execute("SELECT COUNT(*) FROM partite WHERE stagione = ? AND giornata = ?", (stagione, ultima)).fetchone()[0]
    if storte or (squadre_attese and len(conti) != squadre_attese):
        elenco = ", ".join(f"{s}: {n}" for s, n in storte[:8])
        extra = f"; squadre trovate {len(conti)} su {squadre_attese}" if squadre_attese and len(conti) != squadre_attese else ""
        return "avviso", float(len(storte)), f"giornata {ultima}: squadre senza {TITOLARI} titolari ({elenco or 'nessuna'}){extra}"
    return "ok", 0.0, f"giornata {ultima}: {len(conti)} squadre, tutte con {TITOLARI} titolari"


def _partite_con_i_voti(db: sqlite3.Connection, stagione: str) -> list[tuple]:
    """Le partite giocate con il risultato e i voti di tutte e due le squadre (quelle i cui voti non sono ancora arrivati non si
    guardano): (giornata, casa, trasferta, gol casa, gol trasferta, gol casa nei voti, gol trasferta nei voti, gol presi dai
    portieri di casa, gol presi dai portieri ospiti). Nei voti «gol» non ha i rigori (sono in `rig_segnati`) e le autoreti contano
    per l'altra squadra."""
    return db.execute("""
        WITH s AS (SELECT giornata, squadra, SUM(COALESCE(gol, 0) + COALESCE(rig_segnati, 0)) AS fatti,
                          SUM(COALESCE(autogol, 0)) AS autoreti,
                          SUM(CASE WHEN ruolo = 'P' THEN COALESCE(gol_subiti, 0) ELSE 0 END) AS presi
                   FROM voti WHERE stagione = ? GROUP BY giornata, squadra)
        SELECT p.giornata, p.casa, p.trasferta, p.gol_casa, p.gol_trasferta,
               c.fatti + t.autoreti, t.fatti + c.autoreti, c.presi, t.presi
        FROM partite p JOIN s c ON c.giornata = p.giornata AND c.squadra = p.casa
                       JOIN s t ON t.giornata = p.giornata AND t.squadra = p.trasferta
        WHERE p.stagione = ? AND p.giocata = 1 AND p.gol_casa IS NOT NULL AND p.gol_trasferta IS NOT NULL
        ORDER BY p.giornata, p.id""", (stagione, stagione)).fetchall()


def _confronto(righe: list[tuple], storte: list[str], che_cosa: str, giuste: str) -> Esito | None:
    if not righe:
        return None
    if storte:
        return "errore", float(len(storte)), f"{len(storte)} partite su {len(righe)} con {che_cosa}: {', '.join(storte[:5])}"
    return "ok", 0.0, f"{len(righe)} partite, {giuste}"


def gol_dei_voti(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """I gol dei voti (gol, rigori segnati, autoreti dell'altra squadra) devono fare il risultato. Se non tornano, la pagina dei voti
    è stata letta male (per esempio un titolo dei bonus cambiato): sui dati veri non è mai successo, quindi è un errore."""
    righe = _partite_con_i_voti(db, stagione)
    storte = [f"g{g} {c}-{t} {gc}-{gt} (nei voti {vc}-{vt})" for g, c, t, gc, gt, vc, vt, _, _ in righe if (gc, gt) != (vc, vt)]
    return _confronto(righe, storte, "i gol dei voti diversi dal risultato", "gol dei voti uguali al risultato")


def gol_subiti_portieri(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """I gol presi dai portieri di una squadra (anche due, con un cambio) devono essere i gol dell'altra squadra."""
    righe = _partite_con_i_voti(db, stagione)
    storte = [f"g{g} {c}-{t} {gc}-{gt} (portieri {pt}-{pc})" for g, c, t, gc, gt, _, _, pc, pt in righe if (pc, pt) != (gt, gc)]
    return _confronto(righe, storte, "i gol presi dai portieri diversi dal risultato", "gol presi dai portieri uguali al risultato")


def partite_senza_statistiche(db: sqlite3.Connection, stagione: str) -> Esito | None:
    """Le partite giocate che hanno già i voti devono avere anche le statistiche per partita (minuti, xG, rigori calciati). Se
    mancano, la fonte è ferma o in ritardo: per quelle partite il modello usa le righe ricostruite dai voti, senza xG
    (`modello.con_prestazioni_dai_voti`, #613). Una partita senza voti non conta: è appena finita."""
    righe = db.execute("""
        SELECT p.giornata, COUNT(*),
               SUM(NOT EXISTS (SELECT 1 FROM prestazioni pr WHERE pr.understat_partita = p.understat_id))
        FROM partite p
        WHERE p.stagione = ? AND p.giocata = 1
          AND EXISTS (SELECT 1 FROM voti v WHERE v.stagione = p.stagione AND v.giornata = p.giornata
                      AND v.squadra IN (p.casa, p.trasferta))
        GROUP BY p.giornata ORDER BY p.giornata""", (stagione,)).fetchall()
    if not righe:
        return None
    senza = [(g, int(n)) for g, _, n in righe if n]
    partite = sum(n for _, n, _ in righe)
    if senza:
        quante = sum(n for _, n in senza)
        elenco = ", ".join(f"g{g}: {n}" for g, n in senza[-8:])
        return "avviso", float(quante), (f"{_percento(quante, partite)} partite giocate senza statistiche ({elenco}): "
                                         "gol, assist e minuti attesi lì vengono dai voti")
    return "ok", 0.0, f"{partite} partite giocate, tutte con le statistiche"


CONTROLLI: dict[str, Callable[[sqlite3.Connection, str], Esito | None]] = {
    "partite_per_giornata": partite_per_giornata,
    "voti_per_giornata": voti_per_giornata,
    "somma_xg": somma_xg,
    "titolari_per_squadra": titolari_per_squadra,
    "gol_dei_voti": gol_dei_voti,
    "gol_subiti_portieri": gol_subiti_portieri,
    "partite_senza_statistiche": partite_senza_statistiche,
}
# Il nome di ogni controllo per chi legge «Stato dei dati» (campo `etichetta`: le etichette nascono qui, i client le mostrano)
ETICHETTE = {
    "partite_per_giornata": "10 partite per giornata",
    "voti_per_giornata": "Voti nelle giornate finite",
    "somma_xg": "Gol attesi dei giocatori e della partita",
    "titolari_per_squadra": "11 titolari per squadra",
    "gol_dei_voti": "Gol dei voti uguali al risultato",
    "gol_subiti_portieri": "Gol presi dai portieri uguali al risultato",
    "partite_senza_statistiche": "Statistiche delle partite giocate",
    "sentinella": "Sentinella: risposte dell'app",
}


def etichetta(nome: str) -> str:
    """Il nome leggibile di un controllo; le righe della sentinella («sentinella_<invariante>») con il nome dell'invariante."""
    if nome in ETICHETTE:
        return ETICHETTE[nome]
    if nome.startswith("sentinella_"):
        return "Sentinella: " + nome.removeprefix("sentinella_").replace("_", " ")
    testo = nome.replace("_", " ").replace("-", " ").strip()
    return testo[:1].upper() + testo[1:]


# Controlli che sui dati veri danno sempre zero (misurato il 12/11/2026 su tutte le partite in archivio): un «errore» è un passo
# dell'aggiornamento che ha scritto dati sbagliati, e la corsa lo conta tra i suoi errori (`aggiorna.Aggiornamento.controlli`).
CONTANO_COME_ERRORI = frozenset({"gol_dei_voti", "gol_subiti_portieri"})


def esegui(db: sqlite3.Connection, quando: str | None = None) -> list[dict]:
    """Lancia tutti i controlli su ogni stagione in archivio e salva l'esito (sostituisce quello di prima).
    Un controllo che si rompe diventa un avviso: non ferma gli altri."""
    quando = quando or datetime.now().isoformat(timespec="seconds")
    stagioni = [s for s, in db.execute("SELECT DISTINCT stagione FROM partite ORDER BY stagione")]
    risultati = []
    for stagione in stagioni:
        for nome, funzione in CONTROLLI.items():
            try:
                esito = funzione(db, stagione)
            except Exception as e:  # noqa: BLE001 - un controllo rotto non deve fermare l'aggiornamento
                esito = ("avviso", None, f"controllo non riuscito ({type(e).__name__})")
            if esito is None:
                db.execute("DELETE FROM controlli WHERE stagione = ? AND nome = ?", (stagione, nome))
                continue
            stato, valore, dettaglio = esito
            db.execute("INSERT OR REPLACE INTO controlli (stagione, nome, esito, valore, dettaglio, controllato) VALUES (?, ?, ?, ?, ?, ?)",
                       (stagione, nome, stato, valore, dettaglio, quando))
            risultati.append({"stagione": stagione, "nome": nome, "esito": stato, "valore": valore, "dettaglio": dettaglio})
    return risultati


def leggi(db: sqlite3.Connection, stagione: str | None = None) -> list[dict]:
    """Gli ultimi esiti salvati (di una stagione, o di tutte)."""
    sql = "SELECT stagione, nome, esito, valore, dettaglio, controllato FROM controlli"
    parametri: tuple = ()
    if stagione:
        sql += " WHERE stagione = ?"
        parametri = (stagione,)
    return [dict(zip(("stagione", "nome", "esito", "valore", "dettaglio", "controllato"), r))
            for r in db.execute(sql + " ORDER BY stagione DESC, nome", parametri)]
