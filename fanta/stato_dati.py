"""Stato dei dati: da dove arrivano, quanto sono freschi e quanto il modello ci azzecca.

La calibrazione confronta, per ogni gruppo di giocatori delle probabili formazioni (titolare al 90%, in panchina al 30%...),
quanti hanno davvero preso voto con la probabilità che il modello aveva stimato. Serve a capire se i numeri di partenza
(modello._p_da_probabili) vanno corretti: si compila da sola man mano che le giornate vengono giocate, solo con le probabili lette
prima delle partite. I numeri della pagina sono quelli che usa il modello (stessa funzione, `taratura_e_fattori`).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta

from . import archivio, controlli, coppe, fonti_attive, modello, uso

try:                                              # senza foto.py (versione pubblica) le foto sono sempre zero
    from . import foto
except ImportError:
    foto = None

LOG = logging.getLogger(__name__)
GRUPPI = modello.GRUPPI_PROBABILI      # (nome del gruppo, stato nelle probabili, percentuale minima, percentuale massima esclusa)
MINIMO_PER_GRUPPO = 20      # sotto questo numero di giocatori il confronto è solo indicativo


def calibrazione(db: sqlite3.Connection, stagione: str) -> dict:
    """{"giornate": quante giornate hanno probabili e partite giocate, "gruppi": [{gruppo, n, osservato, previsto}]}.
    "osservato" = quota di giocatori che hanno preso voto; "previsto" = media della probabilità stimata dal modello.
    Con una riga attiva della taratura di «gioca N%» (`taratura_probabili.attiva`) i gruppi si fanno sulle probabili salvate prima
    della scadenza (registro delle giornate) e il «previsto» usa la riga attiva; senza (o se il registro non si legge), sull'ultima
    lettura delle probabili di prima di ogni partita (`probabili_storia`, `_letture_prima_delle_partite`)."""
    return _con_taratura(db, stagione)[1]


def taratura_e_fattori(db: sqlite3.Connection, stagione: str) -> tuple[dict | None, dict[str, float], bool]:
    """Quello che serve a «gioca N%» con le probabili, letto una volta sola: (coefficienti della riga attiva o None, correzione per
    gruppi fatta con la stessa formula, ripiego). `ripiego` vero = c'è una riga attiva ma il registro non si legge: allora numeri
    di partenza per tutto (None e la correzione di sempre), mai la formula tarata senza la sua correzione (mai misurata)."""
    t, c, ripiego = _con_taratura(db, stagione)
    return t, fattori_da(c), ripiego


def _con_taratura(db: sqlite3.Connection, stagione: str) -> tuple[dict | None, dict, bool]:
    """(taratura, calibrazione, ripiego): vedi `taratura_e_fattori`. Nel log il tipo d'errore e i punti del codice, mai il
    messaggio. Mai un errore: da qui passano le previsioni."""
    from . import registro_giornate, taratura_probabili   # qui dentro: importano consigli, che importa questo modulo
    t = taratura_probabili.attiva(db)
    if t is None:
        return None, _calibrazione_probabili(db, stagione), False
    try:
        r = taratura_probabili.righe(db)
        return t, taratura_probabili.calibrazione_su(r[r["stagione"] == stagione], t), False
    except Exception as e:  # noqa: BLE001 - le previsioni non si fermano: tornano ai numeri di partenza
        LOG.warning("stato dei dati: registro non letto per la taratura di «gioca N%%» (%s) in %s, valgono i numeri di partenza",
                    type(e).__name__, registro_giornate._dove(e))
        return None, _calibrazione_probabili(db, stagione), True


def _letture_prima_delle_partite(db: sqlite3.Connection, stagione: str) -> list[tuple]:
    """(giornata, stato, percentuale, in dubbio, ha preso voto) dei giocatori delle partite giocate, presi dall'ultima lettura delle
    probabili di PRIMA del calcio d'inizio della loro partita (`probabili_storia`, copie della giornata prima escluse). Non la tabella
    `probabili`: tiene l'ultima lettura della giornata, che a partite finite è la formazione vera e farebbe sembrare le probabili
    perfette. Partite senza una lettura di prima: non contano. Una richiesta per partita sull'indice `probabili_storia_letture`."""
    partite = db.execute("SELECT id, giornata, REPLACE(data, ' ', 'T') FROM partite WHERE stagione = ? AND giocata = 1 "
                         "AND data IS NOT NULL", (stagione,)).fetchall()
    per_lettura: dict[tuple[int, str], set[int]] = {}
    for pid, giornata, inizio in partite:
        r = db.execute("SELECT MAX(rilevato) FROM probabili_storia WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio' "
                       "AND copia = 0 AND rilevato < ?", (stagione, giornata, inizio)).fetchone()
        if r and r[0]:
            per_lettura.setdefault((giornata, r[0]), set()).add(pid)
    righe = []
    for (giornata, rilevato), pids in per_lettura.items():
        for pid, stato, perc, dubbio, preso in db.execute(
                "SELECT s.partita_id, s.stato, s.percentuale, s.in_dubbio, v.voto_red IS NOT NULL FROM probabili_storia s "
                "LEFT JOIN voti v ON v.stagione = s.stagione AND v.giornata = s.giornata AND v.calciatore_id = s.calciatore_id "
                "WHERE s.stagione = ? AND s.giornata = ? AND s.fonte = 'fantacalcio' AND s.copia = 0 AND s.rilevato = ?",
                (stagione, giornata, rilevato)):
            if pid in pids:
                righe.append((giornata, stato, perc, dubbio, preso))
    return righe


def _calibrazione_probabili(db: sqlite3.Connection, stagione: str) -> dict:
    """La calibrazione di sempre, con i numeri di partenza, sulle letture di prima di ogni partita (`_letture_prima_delle_partite`).
    `giornate` = giornate misurabili (con almeno una partita così): sotto MIN_GIORNATE `fattori_da` non corregge niente."""
    try:
        righe = _letture_prima_delle_partite(db, stagione)
    except sqlite3.Error as e:          # per esempio archivio non ancora con la colonna `copia`: nessuna correzione, mai un errore
        LOG.warning("stato dei dati: letture delle probabili non lette (%s), nessuna correzione di «gioca N%%»", type(e).__name__)
        righe = []
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


def _taratura(db: sqlite3.Connection) -> dict | None:
    """La taratura di «gioca N%» (`taratura_probabili.riepilogo`). Campo in più e facoltativo: se va in errore la pagina resta in
    piedi, il campo vale None e nel log vanno il tipo d'errore e i punti del codice (mai il messaggio)."""
    from . import registro_giornate
    try:
        from . import taratura_probabili
        return taratura_probabili.riepilogo(db)
    except Exception as e:  # noqa: BLE001 - un campo in più non deve togliere la pagina
        LOG.warning("stato dei dati: taratura di «gioca N%%» non letta (%s) in %s", type(e).__name__, registro_giornate._dove(e))
        return None


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


def _registro_nostri(db: sqlite3.Connection) -> dict | None:
    """I4 dal vivo (`registro_nostri.riepilogo`). Campo in più e facoltativo: se va in errore la pagina resta in piedi, il campo vale
    None e nel log vanno il tipo d'errore e i punti del codice (mai il messaggio, che può contenere dati)."""
    from . import registro_giornate
    try:
        from . import registro_nostri
        return registro_nostri.riepilogo(db)
    except Exception as e:  # noqa: BLE001 - un campo in più non deve togliere la pagina
        LOG.warning("stato dei dati: registro dei numeri nostri non letto (%s) in %s", type(e).__name__, registro_giornate._dove(e))
        return None


def _quando_breve(quando: str | None, formato: str) -> str:
    try:
        return datetime.fromisoformat(str(quando)[:19]).strftime(formato)
    except ValueError:
        return str(quando)


def _errori_passo(passo: dict, adesso: datetime) -> list[str]:
    """L'errore di un passo dell'aggiornamento per «Stato dei dati» (una riga, accanto all'ora del suo ultimo successo). Fermo da più
    di `archivio.PASSO_FERMO`: «Fermo da 3 giorni (non riesce dal …)», come la salute; se no «Non riuscito alle … del …»."""
    if not passo.get("errore"):
        return []
    fermo = archivio.fermo_da(passo, adesso)
    if fermo is not None and fermo > archivio.PASSO_FERMO:
        return [f"Fermo da {archivio.durata_testo(fermo)} (non riesce dal {_quando_breve(passo['dal'], '%d/%m alle %H:%M')}): {passo['errore']}"]
    return [f"Non riuscito alle {_quando_breve(passo['ultimo'], '%H:%M del %d/%m')}: {passo['errore']}"]


GIRI_SENTINELLA = timedelta(days=7)      # in «Stato dei dati» i giri della sentinella dell'ultima settimana


def _sentinella_giri(adesso: datetime | None) -> list[dict] | None:
    """I giri della sentinella degli ultimi GIRI_SENTINELLA (`sentinella.giri_sentinella`: solo ore e nomi di invarianti). Campo in
    più e facoltativo: se va in errore la pagina resta in piedi e vale None (nel log solo il tipo d'errore)."""
    from . import sentinella
    try:
        al = (adesso or datetime.now()).astimezone()
        return sentinella.giri_sentinella(al - GIRI_SENTINELLA, al, sentinella.FILE_STATO)
    except Exception as e:  # noqa: BLE001 - un campo in più non deve togliere la pagina
        LOG.warning("stato dei dati: giri della sentinella non letti (%s)", type(e).__name__)
        return None


def riepilogo(db: sqlite3.Connection, stagione: str, *, adesso: datetime | None = None) -> dict:
    """Tutto quello che serve alla pagina "Stato dei dati". `registro`: quanto ci hanno preso i numeri mostrati prima di ogni
    giornata (I1-I3, `registro_giornate.riepilogo`). `registro_nostri`: i numeri «nostri» contro i mostrati (I4 dal vivo,
    `registro_nostri.riepilogo`; None se non si leggono). `consiglio`: gli indicatori del consiglio di formazione C1-C4, sommati sui
    Diari di tutti (`indicatori_consiglio.riepilogo`). `calibrazione.taratura`: la taratura di «gioca N%» con le probabili
    (`taratura_probabili.riepilogo`; None se non si legge). `sentinella_giri`: i giri della sentinella dell'ultima settimana
    (None se non si leggono); `adesso` (senza fuso, di norma l'ora del server) serve solo a quello."""
    from . import indicatori_consiglio, registro_giornate      # qui dentro: importano consigli, che importa questo modulo
    passi = {p["passo"]: p for p in archivio.passi(db)}
    agg = []
    for cosa, quando, dettaglio in db.execute("SELECT cosa, quando, dettaglio FROM aggiornamenti ORDER BY cosa"):
        if cosa in passi:                    # un passo dell'aggiornamento: `quando` è il suo ultimo successo
            errori = _errori_passo(passi[cosa], adesso or datetime.now())
        else:
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
        "calibrazione": {**(c := calibrazione(db, stagione)), "fattori": fattori_da(c), "taratura": _taratura(db)},
        "registro": registro_giornate.riepilogo(db),
        "registro_nostri": _registro_nostri(db),
        "consiglio": indicatori_consiglio.riepilogo(),
        "sentinella_giri": _sentinella_giri(adesso),
    }
