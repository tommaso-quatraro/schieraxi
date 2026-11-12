"""Registro delle giornate: i numeri MOSTRATI prima di ogni giornata, per tutta la Serie A, e quanto ci hanno preso (#165, L1).

Poco prima della prima partita della giornata (negli ultimi ANTICIPO minuti, come la copia alla scadenza) si salvano per ogni
giocatore della Serie A i numeri che l'app mostra: «gioca N%» (`p_voto`), fantavoto atteso (`mu`), voto atteso, gol e assist
attesi, minuti attesi e stato delle probabili formazioni, più la fantamedia di allora. Regole classiche (`Regole()`, come
`precisione.pubblico`), mai quelle di una lega; niente nomi né dati personali, solo id e numeri. Nessuna richiesta in più alle
fonti: sono le previsioni già calcolate (`consigli.previsioni`, in cache). Chi ha la partita già iniziata (un anticipo) non si salva.

Il registro sta nell'archivio (tabelle `registro_giocatori` e `registro_giornate`) e NON si ricostruisce: una giornata non salvata
è persa. Perché qualcuno se ne accorga, quando la prima partita inizia e la giornata non è salvata diventa «persa» (`segna_perse`):
una riga con il motivo in breve, che «Stato dei dati» mostra, e un avviso solo al proprietario (`avvisa_perse`).
Gira nel thread del pianificatore, una volta al minuto; `FANTA_REGISTRO_GIORNATE=0` lo spegne.
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import sqlite3
import traceback
from datetime import datetime, timedelta
from typing import Callable

import numpy as np
import pandas as pd

from . import archivio, avvisi, consigli, fasi, incertezza
from . import formazione as fz
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import Regole

ANTICIPO = timedelta(minutes=10)        # si salva negli ultimi 10 minuti prima della prima partita (dopo l'ultimo giro delle probabili)
REGOLE = Regole()                       # regole classiche: i numeri non dipendono da una lega
DOPO_FINE = timedelta(hours=24)         # a turno finito si misura un giorno dopo: i voti hanno il tempo di assestarsi
ATTESA_VOTI = timedelta(hours=72)       # oltre, si misura anche se a qualche partita mancano i voti (quelle partite non contano)
FASCE = 10                              # fasce di 10 punti di «gioca N%» per l'errore di calibrazione
PRESENZE_FITTIZIE = 10                  # fantamedia tirata verso il ruolo, come `verifica.PRESENZE_FITTIZIE`
FANTAVOTO_SENZA_RUOLO = 6.0             # ruolo che non ha ancora nessun voto
# Fascia «8 volte su 10» (I3): come `verifica --incertezza`, su rose estratte a sorte (seme fisso) tra chi ha una probabilità vera di
# giocare; per ogni rosa la formazione migliore con i numeri MOSTRATI, la sua fascia e i punti veri.
ROSE_SINTETICHE = 20
SIMULAZIONI = 300
POSTI_ROSA = {"P": 3, "D": 8, "C": 8, "A": 6}
P_MINIMA_ROSA = 0.3
FINESTRA = 8                            # le medie si fanno sulle ultime 8 giornate misurate; verdetto solo a finestra piena
MOSTRATE = 38                           # righe per giornata in «Stato dei dati»: al massimo una stagione
# soglie decise il 5/11/2026 (spec §2 e §4, D1), I1 rifatta il 12/11/2026 (#614). Prima I1 chiedeva un errore almeno il 3% sotto
# quello della fantamedia della sola stagione (6 a chi non ha voti): un avversario che fa peggio di un numero fisso per ruolo, per
# cui la soglia non si accorgeva di un modello rotto (un numero fisso per ruolo dava -2,7% e -9,3%). Ora l'avversario è la
# fantamedia tirata verso il ruolo (`fantamedie_tirate`): il modello la batte di circa l'1% (-1,3% [-1,8; -0,8] e -0,5%
# [-1,3; +0,2] nelle due stagioni, pari con le probabili) e un numero fisso per ruolo fa +0,8% e +1,9%. Soglia: l'errore del
# fantavoto atteso non deve superare di più dell'1% quello della fantamedia tirata;
# I2 «gioca N%» con errore di calibrazione al massimo 5 punti e Brier al massimo 0,15; I3 punti veri nella fascia tra 72% e 88%
SOGLIE = {"I1": 0.01, "I2_calibrazione": 0.05, "I2_brier": 0.15, "I3_minimo": 0.72, "I3_massimo": 0.88}
# il segno dell'avversario di I1 in ogni giornata misurata (`registro_giornate.avversario` nell'archivio): la fantamedia tirata verso
# il ruolo di #614. Le giornate senza segno sono state misurate prima e si rimisurano una volta (`rimisura_avversario`)
AVVERSARIO = "fantamedia_tirata"
LOG = logging.getLogger(__name__)
BONUS_E_MALUS = ("gol", "gol_subiti", "autogol", "rig_segnati", "rig_sbagliati", "rig_parati", "assist", "mvp", "ammonizioni",
                 "espulsioni")
# colonne di `consigli.previsioni` che il registro legge: senza le essenziali non si salva niente (e il motivo va nel log); senza
# una facoltativa si salva vuota, con un avviso nel log
ESSENZIALI = ("partita", "ruolo", "p_voto", "mu")
FACOLTATIVE = ("data_partita", "squadra", "mu_voto", "e_gol", "e_assist", "minuti", "stato", "percentuale", "dubbio")
PERSA = "persa"                         # in `da_avvisare` / `avvisati` di una giornata persa
SENZA_TENTATIVI = "nessun tentativo negli ultimi 10 minuti prima della prima partita (servizio fermo o registro spento)"
# l'ultimo motivo per cui una giornata non si è salvata, {(stagione, giornata): motivo}, finché non si salva o diventa persa. In
# memoria: dopo un riavvio la giornata diventa persa lo stesso, con il motivo SENZA_TENTATIVI.
_tentativi: dict[tuple[str, int], str] = {}


def acceso() -> bool:
    """Interruttore (variabile d'ambiente, letta a ogni giro): `FANTA_REGISTRO_GIORNATE=0` lo spegne."""
    return os.environ.get("FANTA_REGISTRO_GIORNATE", "1").strip().lower() not in ("0", "no", "false", "off")


def _numero(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _testo(x) -> str | None:
    return x if isinstance(x, str) else None


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " "))
    except ValueError:
        return None


def _righe(cursore: sqlite3.Cursor) -> list[dict]:
    nomi = [c[0] for c in cursore.description]
    return [dict(zip(nomi, r)) for r in cursore.fetchall()]


def fantavoto_vero(riga: dict, ruolo: str, regole: Regole = REGOLE) -> float | None:
    """Il fantavoto di una riga della tabella `voti` (None = senza voto); i bonus mancanti valgono zero."""
    return fantavoto({**riga, **{k: riga.get(k) or 0 for k in BONUS_E_MALUS}}, ruolo, regole)


def fantamedie_tirate(db: sqlite3.Connection, stagione: str, giornata: int,
                      regole: Regole = REGOLE) -> tuple[dict[int, float], dict[str, float]]:
    """L'avversario onesto del fantavoto atteso (come `verifica.avversari`, #614), con i voti di PRIMA di `giornata`, anche
    delle stagioni passate: ({id: fantamedia tirata verso il ruolo}, {ruolo: fantavoto medio}). Tirata = (somma dei suoi fantavoti
    + PRESENZE_FITTIZIE x media del suo ruolo) / (presenze + PRESENZE_FITTIZIE); il ruolo è quello dell'ultimo voto. Chi non ha
    voti non c'è: per lui vale la media del ruolo (`avversario`)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    del_ruolo: dict[str, list[float]] = {}
    suoi: dict[int, tuple[float, int, str]] = {}
    for r in _righe(db.execute(f"SELECT * FROM voti WHERE (stagione < ? OR (stagione = ? AND giornata < ?)) AND {col} IS NOT NULL "
                               "ORDER BY stagione, giornata", (stagione, stagione, giornata))):
        fv = fantavoto_vero(r, r["ruolo"], regole)
        if fv is None:
            continue
        del_ruolo.setdefault(str(r["ruolo"]), []).append(fv)
        somma, n, _ = suoi.get(int(r["calciatore_id"]), (0.0, 0, ""))
        suoi[int(r["calciatore_id"])] = (somma + fv, n + 1, str(r["ruolo"]))
    ruoli = {ruolo: sum(v) / len(v) for ruolo, v in del_ruolo.items()}
    tirate = {i: round((somma + PRESENZE_FITTIZIE * ruoli[ruolo]) / (n + PRESENZE_FITTIZIE), 3) for i, (somma, n, ruolo) in suoi.items()}
    return tirate, {ruolo: round(m, 3) for ruolo, m in ruoli.items()}


def avversario(tirate: dict[int, float], ruoli: dict[str, float], calciatore_id: int, ruolo: str) -> float:
    """La stima dell'avversario per un giocatore: la sua fantamedia tirata; senza voti la media del ruolo; senza nemmeno quella 6."""
    return tirate.get(int(calciatore_id), ruoli.get(str(ruolo), FANTAVOTO_SENZA_RUOLO))


def _salvata(db: sqlite3.Connection, stagione: str, giornata: int) -> bool:
    return db.execute("SELECT 1 FROM registro_giornate WHERE stagione = ? AND giornata = ?", (stagione, giornata)).fetchone() is not None


def _non_salvata(stagione: str, giornata: int, motivo: str, nel_log: bool = True) -> None:
    """Ricorda il motivo (diventa quello della giornata persa, se resta così) e lo scrive nel log del server. Il motivo ha solo
    numeri, tipi d'errore e nomi di colonne, mai dati."""
    _tentativi[(stagione, int(giornata))] = motivo
    if nel_log:
        LOG.warning("registro delle giornate: giornata %s (%s) non salvata per ora: %s", giornata, stagione, motivo)


def _da_scrivere(db: sqlite3.Connection, stagione: str, giornata: int, prev: pd.DataFrame, adesso: datetime) -> tuple[list[dict], str]:
    """Le righe da salvare di `prev` e, se non ce n'è nessuna, il motivo in breve."""
    if prev is None or len(prev) == 0:
        return [], "previsioni vuote"
    if mancano := [c for c in ESSENZIALI if c not in prev.columns]:
        return [], f"nelle previsioni mancano le colonne {', '.join(mancano)}"
    if mancano := [c for c in FACOLTATIVE if c not in prev.columns]:
        LOG.warning("registro delle giornate: nelle previsioni mancano le colonne %s, si salvano vuote", ", ".join(mancano))
    tirate, ruoli = fantamedie_tirate(db, stagione, giornata)
    righe, fuori, senza_numeri = [], 0, 0
    for cid, x in prev.iterrows():
        partita = _numero(x.get("partita"))
        inizio = _data(x.get("data_partita"))
        if partita is None or (inizio is not None and inizio <= adesso):
            fuori += 1
            continue
        r = {"stagione": stagione, "giornata": int(giornata), "calciatore_id": int(cid), "ruolo": str(x.get("ruolo")),
             "squadra": _testo(x.get("squadra")), "partita_id": int(partita), "p_voto": _numero(x.get("p_voto")),
             "mu": _numero(x.get("mu")), "mu_voto": _numero(x.get("mu_voto")), "e_gol": _numero(x.get("e_gol")),
             "e_assist": _numero(x.get("e_assist")), "minuti": _numero(x.get("minuti")),
             "stato": _testo(x.get("stato")), "percentuale": _numero(x.get("percentuale")),
             "dubbio": 1 if x.get("dubbio") == 1 else 0, "fantamedia": avversario(tirate, ruoli, int(cid), str(x.get("ruolo")))}
        if r["p_voto"] is None or r["mu"] is None:
            senza_numeri += 1
            continue
        righe.append(r)
    if righe:
        return righe, ""
    return [], (f"nessun giocatore da salvare su {len(prev)}: {fuori} senza partita o con la partita già iniziata, "
                f"{senza_numeri} senza «gioca N%» o fantavoto atteso")


def salva(db: sqlite3.Connection, stagione: str, giornata: int, prev: pd.DataFrame, con_probabili: bool, adesso: datetime) -> int:
    """Salva i numeri di `prev` (la tabella di `consigli.previsioni`, indice = id) per la giornata. Una volta sola: se la giornata c'è
    già restituisce 0 e non cambia niente. Salta chi non ha una partita e chi ha la partita già iniziata. Restituisce le righe scritte;
    se non ce n'è nessuna da scrivere, il motivo va nel log (e diventa quello della giornata persa, se resta così)."""
    if _salvata(db, stagione, giornata):
        return 0
    righe, motivo = _da_scrivere(db, stagione, giornata, prev, adesso)
    if not righe:
        _non_salvata(stagione, giornata, motivo)
        return 0                            # si riprova al minuto dopo
    archivio.inserisci(db, "registro_giocatori", righe)
    db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, ?, ?)",
               (stagione, int(giornata), adesso.isoformat(timespec="seconds"), len(righe), int(bool(con_probabili))))
    db.commit()
    _tentativi.pop((stagione, int(giornata)), None)
    return len(righe)


def da_salvare(db: sqlite3.Connection, adesso: datetime) -> tuple[str, int] | None:
    """(stagione, giornata) da salvare adesso: negli ultimi ANTICIPO minuti prima della prima partita (esclusa), se non è già salvata."""
    stagione = consigli.stagione_corrente()
    g = consigli.prossima_giornata(db, stagione, adesso)
    if g is None:
        return None
    inizio = avvisi.prima_partita(db, stagione, g)
    if inizio is None or not inizio - ANTICIPO <= adesso < inizio or _salvata(db, stagione, g):
        return None
    return stagione, g


def salva_se_serve(db: sqlite3.Connection, adesso: datetime, previsioni=None) -> int:
    """Se è il momento, salva la giornata con le previsioni già calcolate (`previsioni(db, regole, giornata)`, come
    `consigli.previsioni`). Restituisce le righe scritte (0 = niente da fare o niente salvato, col motivo nel log). Un errore delle
    previsioni o della scrittura si ricorda come motivo e risale a `giro`, che lo scrive nel log con i punti del codice."""
    quale = da_salvare(db, adesso)
    if quale is None:
        return 0
    stagione, g = quale
    try:
        prev, giornata, con_probabili = (previsioni or consigli.previsioni)(db, REGOLE, g)
    except Exception as e:
        _non_salvata(stagione, g, f"previsioni non calcolate ({type(e).__name__})", nel_log=False)
        raise
    if giornata != g:
        _non_salvata(stagione, g, f"previsioni della giornata {giornata} invece della {g}")
        return 0
    try:
        return salva(db, stagione, g, prev, con_probabili, adesso)
    except Exception as e:
        _non_salvata(stagione, g, f"scrittura non riuscita ({type(e).__name__})", nel_log=False)
        raise


def segna_perse(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Le giornate della stagione con la prima partita già iniziata e non salvate diventano «perse», una volta sola: una riga in
    `registro_giornate` con `salvato` NULL, 0 giocatori e il motivo in breve in `persa` (l'ultimo salvataggio non riuscito, o
    SENZA_TENTATIVI), che non si misura mai; l'avviso lo manda `avvisa_perse`. Contano le giornate dalla prima registrata o tentata
    della stagione in poi (da subito se il registro c'era già nelle stagioni prima); con il registro mai partito, nessuna.
    Restituisce le giornate segnate."""
    stagione = consigli.stagione_corrente()
    presenti = {int(g) for (g,) in db.execute("SELECT giornata FROM registro_giornate WHERE stagione = ?", (stagione,))}
    tentate = {g for s, g in _tentativi if s == stagione}
    if presenti or tentate:
        da = min(presenti | tentate)
    elif db.execute("SELECT 1 FROM registro_giornate LIMIT 1").fetchone():
        da = 1
    else:
        return []                           # registro appena acceso: le giornate di prima non erano sue
    perse = []
    for g, primo in db.execute("SELECT giornata, MIN(data) FROM partite WHERE stagione = ? AND giornata >= ? AND data IS NOT NULL "
                               "GROUP BY giornata ORDER BY giornata", (stagione, da)).fetchall():
        g = int(g)
        if g in presenti or (p := _data(primo)) is None or adesso < p:     # nessuna partita iniziata: si salta subito
            continue
        inizio = avvisi.prima_partita(db, stagione, g)
        if inizio is None or adesso < inizio:
            continue
        motivo = _tentativi.get((stagione, g), SENZA_TENTATIVI)
        db.execute("INSERT INTO registro_giornate (stagione, giornata, giocatori, con_probabili, persa, da_avvisare, avvisati) "
                   "VALUES (?, ?, 0, 0, ?, ?, '[]')", (stagione, g, motivo, json.dumps([PERSA])))
        perse.append((stagione, g, motivo))
    if not perse:
        return []
    db.commit()
    for s, g, motivo in perse:
        _tentativi.pop((s, g), None)
        LOG.warning("registro delle giornate: giornata %s (%s) persa, non salvata prima della prima partita: %s", g, s, motivo)
    return [(s, g) for s, g, _ in perse]


# ---------------------------------------------------------------- misura a giornata finita
def _partite(db: sqlite3.Connection, stagione: str, giornata: int) -> tuple[set[int], set[int]]:
    """(partite del registro giocate con i voti di tutte e due le squadre, partite del registro giocate ma ancora senza voti)."""
    col = COLONNA_VOTO[REGOLE.fonte_voto]
    con_voti = {r[0] for r in db.execute(f"SELECT DISTINCT squadra FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL",
                                         (stagione, giornata))}
    valide: set[int] = set()
    senza: set[int] = set()
    for pid, casa, trasferta in db.execute(
            "SELECT id, casa, trasferta FROM partite WHERE stagione = ? AND giocata = 1 AND id IN "
            "(SELECT DISTINCT partita_id FROM registro_giocatori WHERE stagione = ? AND giornata = ?)", (stagione, stagione, giornata)):
        (valide if casa in con_voti and trasferta in con_voti else senza).add(int(pid))
    return valide, senza


def da_misurare(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Le giornate salvate e non ancora misurate che sono finite: turno giocato (`fasi.fine_giornata`, le rinviate non lo tengono
    aperto) da almeno DOPO_FINE e voti di ogni partita giocata, oppure da almeno ATTESA_VOTI anche senza tutti i voti."""
    pronte = []
    for stagione, g in db.execute("SELECT stagione, giornata FROM registro_giornate WHERE misurato IS NULL AND persa IS NULL "
                                  "ORDER BY stagione, giornata").fetchall():
        fine = fasi.fine_giornata(db, stagione, g)
        if fine is None or adesso < fine + DOPO_FINE:
            continue
        if _partite(db, stagione, g)[1] and adesso < fine + ATTESA_VOTI:
            continue
        pronte.append((stagione, int(g)))
    return pronte


def _fascia(registro: list[dict], fv: dict[int, float], voto: dict[int, float], stagione: str, giornata: int) -> tuple[int, int]:
    """(rose provate, rose con i punti veri dentro la fascia 8 volte su 10). Zero rose se i giocatori non bastano."""
    rng = np.random.default_rng(1000 * giornata + int(stagione[:4]))
    per_id = {int(r["calciatore_id"]): r for r in registro}
    pool = {ruolo: np.array(sorted(i for i, r in per_id.items() if r["ruolo"] == ruolo and r["p_voto"] >= P_MINIMA_ROSA))
            for ruolo in POSTI_ROSA}
    if any(len(pool[r]) < n for r, n in POSTI_ROSA.items()):
        return 0, 0
    casi = dentro = 0
    for _ in range(ROSE_SINTETICHE):
        ids = [int(i) for r, n in POSTI_ROSA.items() for i in rng.choice(pool[r], n, replace=False)]
        rosa = [fz.Giocatore(i, "", per_id[i]["ruolo"], float(per_id[i]["p_voto"]), float(per_id[i]["mu"]),
                             float(per_id[i]["mu_voto"] if per_id[i]["mu_voto"] is not None else 6.0)) for i in ids]
        try:
            f = fz.migliore(rosa, REGOLE, SIMULAZIONI)
        except ValueError:
            continue
        reale = fz.punteggio(f.titolari, f.panchina, {i: i in fv for i in ids}, {i: fv.get(i, 0.0) for i in ids},
                             {i: voto.get(i, 0.0) for i in ids}, REGOLE)
        fascia = incertezza.intervallo(f.atteso, f.dev)
        casi += 1
        dentro += int(fascia["basso"] <= reale <= fascia["alto"])
    return casi, dentro


def misura_giornata(db: sqlite3.Connection, stagione: str, giornata: int) -> dict | None:
    """I pezzi delle misure di una giornata finita, solo per le partite giocate e con i voti (None se non ce n'è):
    I1 `voti`, `sq_modello`, `sq_fantamedia` (somme dei quadrati degli errori di chi ha preso voto; la fantamedia è quella
    tirata verso il ruolo, ricalcolata dall'archivio: le righe salvate prima di #614 hanno ancora quella di allora);
    I2 `presenze`, `brier_somma`, `fasce` (per fascia di «gioca N%»: [giocatori, somma del detto, quanti hanno preso voto]);
    I3 `fascia_casi`, `fascia_dentro`. Si sommano poi sulla finestra (`medie`)."""
    valide, _ = _partite(db, stagione, giornata)
    registro = [r for r in _righe(db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = ? ORDER BY calciatore_id",
                                             (stagione, giornata))) if r["partita_id"] in valide]
    if not registro:
        return None
    col = COLONNA_VOTO[REGOLE.fonte_voto]
    righe_voti = {int(v["calciatore_id"]): v for v in _righe(db.execute(
        f"SELECT * FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL", (stagione, giornata)))}
    fv: dict[int, float] = {}
    voto: dict[int, float] = {}
    for r in registro:
        i = int(r["calciatore_id"])
        if i in righe_voti and (f := fantavoto_vero(righe_voti[i], r["ruolo"])) is not None:
            fv[i], voto[i] = f, float(righe_voti[i][col])
    sq_m = sq_f = brier = 0.0
    fasce = [[0, 0.0, 0] for _ in range(FASCE)]
    tirate, ruoli = fantamedie_tirate(db, stagione, giornata)
    for r in registro:
        i, p = int(r["calciatore_id"]), float(r["p_voto"])
        preso = i in fv
        if preso:
            sq_m += (r["mu"] - fv[i]) ** 2
            sq_f += (avversario(tirate, ruoli, i, r["ruolo"]) - fv[i]) ** 2
        brier += (p - preso) ** 2
        b = min(FASCE - 1, max(0, math.floor(p * FASCE + 1e-9)))
        fasce[b][0] += 1
        fasce[b][1] += p
        fasce[b][2] += int(preso)
    casi, dentro = _fascia(registro, fv, voto, stagione, giornata)
    return {"voti": len(fv), "sq_modello": round(sq_m, 4), "sq_fantamedia": round(sq_f, 4), "presenze": len(registro),
            "brier_somma": round(brier, 4), "fasce": [[n, round(s, 4), g] for n, s, g in fasce],
            "fascia_casi": casi, "fascia_dentro": dentro}


# ---------------------------------------------------------------- medie sulla finestra e soglie (spec §2)
def _lista(testo) -> list:
    if isinstance(testo, list):
        return testo
    try:
        v = json.loads(testo) if testo else []
    except ValueError:
        return []
    return v if isinstance(v, list) else []


def medie(righe: list[dict]) -> dict:
    """Le medie di più giornate misurate, sommando i pezzi (ogni giocatore pesa uguale): `errore_modello` e `errore_fantamedia`
    (radice dell'errore quadratico), `i1` (il primo diviso il secondo, meno 1), `brier`, `calibrazione` (media pesata sulle fasce di
    |detto − giocato|, 0,05 = 5 punti), `copertura` (quota di rose con i punti veri dentro la fascia). `verdetto` solo con FINESTRA
    giornate; allora `regge` dice per ogni indicatore se è entro soglia (None = non si può dire) e `fuori` quali non lo sono."""
    righe = [r for r in righe if (r.get("presenze") or 0) > 0]
    somma = lambda k: sum(float(r.get(k) or 0) for r in righe)  # noqa: E731
    voti, presenze, casi = int(somma("voti")), int(somma("presenze")), int(somma("fascia_casi"))
    sq_m, sq_f = somma("sq_modello"), somma("sq_fantamedia")
    fasce = [[0, 0.0, 0] for _ in range(FASCE)]
    for r in righe:
        for b, f in enumerate(_lista(r.get("fasce"))[:FASCE]):
            if isinstance(f, list) and len(f) == 3:
                fasce[b] = [fasce[b][0] + int(f[0]), fasce[b][1] + float(f[1]), fasce[b][2] + int(f[2])]
    tot = sum(n for n, _, _ in fasce)
    m = {"giornate": len(righe), "voti": voti, "presenze": presenze, "fascia_casi": casi,
         "errore_modello": round(math.sqrt(sq_m / voti), 3) if voti else None,
         "errore_fantamedia": round(math.sqrt(sq_f / voti), 3) if voti else None,
         "i1": round(math.sqrt(sq_m / sq_f) - 1, 3) if voti and sq_f > 0 else None,
         "brier": round(somma("brier_somma") / presenze, 3) if presenze else None,
         "calibrazione": round(sum(abs(s - g) for n, s, g in fasce if n) / tot, 3) if tot else None,
         "copertura": round(somma("fascia_dentro") / casi, 3) if casi else None}
    m["verdetto"] = len(righe) >= FINESTRA
    v = m["verdetto"]
    m["regge"] = {
        "I1": None if not v or m["i1"] is None else m["i1"] <= SOGLIE["I1"],
        "I2": None if not v or m["calibrazione"] is None or m["brier"] is None
        else m["calibrazione"] <= SOGLIE["I2_calibrazione"] and m["brier"] <= SOGLIE["I2_brier"],
        "I3": None if not v or m["copertura"] is None else SOGLIE["I3_minimo"] <= m["copertura"] <= SOGLIE["I3_massimo"]}
    m["fuori"] = [k for k, ok in m["regge"].items() if ok is False]
    return m


def _misurate(db: sqlite3.Connection, fino_a: tuple[str, int] | None = None, quante: int = FINESTRA) -> list[dict]:
    """Le ultime `quante` giornate misurate con dei dati (fino a `fino_a` compresa), dalla più vecchia."""
    sql, par = "SELECT * FROM registro_giornate WHERE misurato IS NOT NULL AND presenze > 0", []
    if fino_a:
        sql += " AND (stagione < ? OR (stagione = ? AND giornata <= ?))"
        par = [fino_a[0], fino_a[0], fino_a[1]]
    return list(reversed(_righe(db.execute(sql + " ORDER BY stagione DESC, giornata DESC LIMIT ?", (*par, quante)))))


def ultime_misurate(db: sqlite3.Connection, quante: int = FINESTRA) -> list[dict]:
    """Le ultime `quante` giornate misurate con dei dati, dalla più vecchia, con `fasce` già letta (una lista): per la riga «su
    tutta la Serie A» del Diario (`precisione.serie_a`, #374). Solo giornate e numeri, nessun giocatore."""
    return [{**r, "fasce": _lista(r.get("fasce"))} for r in _misurate(db, None, quante)]


def registra_misura(db: sqlite3.Connection, stagione: str, giornata: int, m: dict | None, adesso: datetime) -> list[str]:
    """Scrive la misura di una giornata (None = nessuna partita utile: la giornata non conta nella finestra) e decide gli avvisi:
    da avvisare = fuori soglia adesso E nella giornata misurata prima, e non già avvisati mentre restavano fuori."""
    chiave = (stagione, int(giornata))
    if m is None:
        db.execute("UPDATE registro_giornate SET misurato = ?, voti = 0, presenze = 0, fuori = '[]', da_avvisare = '[]', avvisati = '[]', "
                   "avversario = ? WHERE stagione = ? AND giornata = ?", (adesso.isoformat(timespec="seconds"), AVVERSARIO, *chiave))
        db.commit()
        return []
    db.execute("UPDATE registro_giornate SET misurato = ?, voti = ?, sq_modello = ?, sq_fantamedia = ?, presenze = ?, brier_somma = ?, "
               "fasce = ?, fascia_casi = ?, fascia_dentro = ?, avversario = ? WHERE stagione = ? AND giornata = ?",
               (adesso.isoformat(timespec="seconds"), m["voti"], m["sq_modello"], m["sq_fantamedia"], m["presenze"], m["brier_somma"],
                json.dumps(m["fasce"]), m["fascia_casi"], m["fascia_dentro"], AVVERSARIO, *chiave))
    finestra = _misurate(db, chiave, FINESTRA + 1)
    fuori = medie(finestra[-FINESTRA:])["fuori"]
    prima = finestra[-2] if len(finestra) >= 2 else {}
    prima_fuori, prima_avvisati = set(_lista(prima.get("fuori"))), set(_lista(prima.get("avvisati")))
    da_avvisare = sorted(set(fuori) & prima_fuori - prima_avvisati)
    avvisati = sorted(prima_avvisati & set(fuori))
    db.execute("UPDATE registro_giornate SET fuori = ?, da_avvisare = ?, avvisati = ? WHERE stagione = ? AND giornata = ?",
               (json.dumps(fuori), json.dumps(da_avvisare), json.dumps(avvisati), *chiave))
    db.commit()
    return da_avvisare


def riepilogo(db: sqlite3.Connection) -> dict:
    """Per «Stato dei dati»: finestra, soglie, le medie delle ultime FINESTRA giornate misurate (come `medie`) e una riga per ogni
    giornata salvata o persa, dalla più recente (al massimo MOSTRATE), con i suoi numeri (None finché la giornata non è misurata) e
    `persa` (None, o il motivo in breve se la giornata non è stata salvata in tempo). Solo giornate e numeri, niente giocatori."""
    per_giornata = []
    for r in _righe(db.execute("SELECT * FROM registro_giornate ORDER BY stagione DESC, giornata DESC LIMIT ?", (MOSTRATE,))):
        g = medie([r]) if r["misurato"] else {}
        per_giornata.append({
            "stagione": r["stagione"], "giornata": r["giornata"], "salvato": r["salvato"], "giocatori": r["giocatori"],
            "con_probabili": bool(r["con_probabili"]), "misurato": r["misurato"], "voti": r["voti"], "presenze": r["presenze"],
            **{k: g.get(k) for k in ("errore_modello", "errore_fantamedia", "i1", "brier", "calibrazione", "copertura")},
            "fuori": _lista(r["fuori"]), "persa": r["persa"]})
    return {"finestra": FINESTRA, "soglie": dict(SOGLIE), **medie(_misurate(db)), "per_giornata": per_giornata}


def chiudi_giornate(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Misura le giornate finite non ancora misurate, dalla più vecchia. Restituisce quelle misurate."""
    fatte = []
    for stagione, g in da_misurare(db, adesso):
        registra_misura(db, stagione, g, misura_giornata(db, stagione, g), adesso)
        fatte.append((stagione, g))
    return fatte


def rimisura_avversario(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Le giornate misurate quando l'avversario di I1 era la fantamedia della sola stagione (prima di #614) si rimisurano contro
    quello di adesso: senza, per otto giornate la media mescolerebbe due avversari. Si riconoscono dal segno nell'archivio
    (`avversario` diverso da AVVERSARIO, NULL per quelle di prima): una volta rimisurate lo hanno, e ai giri dopo la ricerca non
    trova niente senza rifare nessun calcolo, anche dopo un riavvio del servizio. Se il numero non cambia si scrive solo il
    segno: la misura e i suoi avvisi restano com'erano. Restituisce quelle rifatte."""
    fatte = []
    for r in _righe(db.execute("SELECT stagione, giornata, sq_fantamedia FROM registro_giornate WHERE misurato IS NOT NULL "
                               "AND presenze > 0 AND (avversario IS NULL OR avversario != ?) ORDER BY stagione, giornata",
                               (AVVERSARIO,))):
        m = misura_giornata(db, r["stagione"], r["giornata"])
        if m is not None and abs(m["sq_fantamedia"] - float(r["sq_fantamedia"] or 0.0)) > 1e-3:
            registra_misura(db, r["stagione"], r["giornata"], m, adesso)
            fatte.append((r["stagione"], int(r["giornata"])))
        else:
            db.execute("UPDATE registro_giornate SET avversario = ? WHERE stagione = ? AND giornata = ?",
                       (AVVERSARIO, r["stagione"], r["giornata"]))
            db.commit()
    return fatte


# ---------------------------------------------------------------- avviso al proprietario (come la sentinella)
def _percento(x: float) -> str:
    return f"{100 * x:.0f}%"


def testo_avviso(fuori: list[str], m: dict) -> tuple[str, str]:
    """Titolo e testo dell'avviso: solo indicatori e numeri, mai nomi."""
    righe = []
    if "I1" in fuori and m.get("i1") is not None:
        righe.append(f"• I1 errore del fantavoto atteso {_percento(abs(m['i1']))} {'sotto' if m['i1'] < 0 else 'sopra'} quello della "
                     "fantamedia tirata verso il ruolo (non deve superarlo di più dell'1%)")
    if "I2" in fuori and m.get("calibrazione") is not None and m.get("brier") is not None:
        righe.append(f"• I2 «gioca N%»: calibrazione sbagliata di {100 * m['calibrazione']:.1f} punti, Brier {m['brier']:.3f} "
                     "(al massimo 5 punti e 0,150)".replace(".", ","))
    if "I3" in fuori and m.get("copertura") is not None:
        righe.append(f"• I3 fascia «8 volte su 10»: punti veri dentro {_percento(m['copertura'])} (deve stare tra 72% e 88%)")
    return ("SchieraXI: statistiche", f"Fuori soglia da 2 giornate di fila, media delle ultime {m.get('giornate')} giornate "
            "(dettagli in Stato dei dati):\n" + "\n".join(righe))


def avvisa(db: sqlite3.Connection, manda: Callable[[str, str], bool]) -> bool:
    """Manda l'avviso in sospeso dell'ultima giornata misurata (`manda(titolo, testo)`, vero se è partito). Se non parte resta in
    sospeso e si riprova al giro dopo. True se ha mandato qualcosa."""
    ultima = _misurate(db, quante=1)
    if not ultima or not (da := _lista(ultima[0].get("da_avvisare"))):
        return False
    r = ultima[0]
    titolo, testo = testo_avviso(da, medie(_misurate(db, (r["stagione"], r["giornata"]))))
    if not manda(titolo, testo):
        return False
    db.execute("UPDATE registro_giornate SET da_avvisare = '[]', avvisati = ? WHERE stagione = ? AND giornata = ?",
               (json.dumps(sorted(set(_lista(r.get("avvisati"))) | set(da))), r["stagione"], r["giornata"]))
    db.commit()
    return True


def testo_perse(righe: list[dict]) -> tuple[str, str]:
    """Titolo e testo dell'avviso delle giornate perse: giornate e motivi in breve, mai nomi."""
    voci = [f"• giornata {r['giornata']} ({r['stagione']}): {r['persa']}" for r in righe]
    return ("SchieraXI: registro delle giornate", "Giornate non salvate prima della prima partita: i numeri mostrati allora sono persi "
            "e non si potranno misurare (dettagli in Stato dei dati e nel log del server):\n" + "\n".join(voci))


def avvisa_perse(db: sqlite3.Connection, manda: Callable[[str, str], bool]) -> bool:
    """Un avviso solo per le giornate perse non ancora avvisate, tutte insieme (`manda(titolo, testo)`, vero se è partito). Se non
    parte restano in sospeso e si riprova al giro dopo. True se ha mandato qualcosa."""
    righe = _righe(db.execute("SELECT stagione, giornata, persa FROM registro_giornate WHERE persa IS NOT NULL AND da_avvisare = ? "
                              "ORDER BY stagione, giornata", (json.dumps([PERSA]),)))
    if not righe or not manda(*testo_perse(righe)):
        return False
    db.executemany("UPDATE registro_giornate SET da_avvisare = '[]', avvisati = ? WHERE stagione = ? AND giornata = ?",
                   [(json.dumps([PERSA]), r["stagione"], r["giornata"]) for r in righe])
    db.commit()
    return True


def _dove(e: BaseException, passi: int = 6) -> str:
    """Dove è nato un errore, per il log del server: gli ultimi `passi` punti del codice («file.py:riga funzione», dal più vicino
    all'errore). Senza il messaggio dell'errore, che può contenere dati."""
    punti = traceback.extract_tb(e.__traceback__)[-passi:]
    return " < ".join(f"{os.path.basename(p.filename)}:{p.lineno} {p.name}" for p in reversed(punti)) or "punto sconosciuto"


def giro(adesso: datetime, db: sqlite3.Connection, manda: Callable[[str, str], bool] | None = None) -> None:
    """Un controllo (dal thread del pianificatore, una volta al minuto): salva, segna le giornate perse, misura, avvisa. Un passo che
    va in errore non ferma gli altri; nel log vanno il tipo d'errore e i punti del codice (file e righe), mai il messaggio.
    I passi dei numeri «nostri» (`registro_nostri.py`, I4 dal vivo) vengono ciascuno DOPO il passo dei mostrati: un loro errore non
    tocca mai i numeri mostrati (nemmeno se il modulo non si carica: si importa dentro il passo)."""
    from . import sentinella
    invia = manda or sentinella.manda_ntfy

    def rn():
        from . import registro_nostri
        return registro_nostri

    passi = (("salvataggio", lambda: salva_se_serve(db, adesso)),
             ("salvataggio dei numeri nostri", lambda: rn().salva_se_serve(db, adesso)),
             ("controllo delle giornate perse", lambda: segna_perse(db, adesso)),
             ("controllo delle giornate perse dei numeri nostri", lambda: rn().segna_perse(db, adesso)),
             ("misura", lambda: chiudi_giornate(db, adesso)), ("misura dei numeri nostri", lambda: rn().chiudi_giornate(db, adesso)),
             ("misura contro l'avversario di adesso", lambda: rimisura_avversario(db, adesso)),
             ("avviso", lambda: avvisa(db, invia)), ("avviso delle giornate perse", lambda: avvisa_perse(db, invia)),
             ("avviso dei numeri nostri", lambda: rn().avvisa(db, invia)),
             ("avviso delle giornate perse dei numeri nostri", lambda: rn().avvisa_perse(db, invia)))
    for nome, passo in passi:
        try:
            passo()
        except Exception as e:  # noqa: BLE001 - il giro dopo riprova
            LOG.warning("registro delle giornate: %s non riuscito (%s) in %s", nome, type(e).__name__, _dove(e))
            with contextlib.suppress(sqlite3.Error):
                db.rollback()
