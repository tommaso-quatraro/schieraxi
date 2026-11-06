"""Registro dei numeri «nostri» (I4 dal vivo, L3b di #165; Fase D del piano `docs/superpowers/plans/2026-11-06-gol-attesi-nostri.md`).

Accanto ai numeri MOSTRATI che il registro delle giornate (`registro_giornate.py`) salva poco prima della prima partita, si salvano
anche i numeri «nostri» (solo Fantacalcio.it, `nostri.previsioni`) degli stessi giocatori, con `nostri.VERSIONE`. A giornata finita,
dopo la misura del registro, si confrontano con i mostrati sugli stessi giocatori: errore del fantavoto atteso, punti veri della
formazione migliore sulle stesse 20 rose di I3, gol attesi per fasce. Quando le ultime FINESTRA giornate della versione di oggi
reggono le tre soglie (D1, 5/11), un avviso al proprietario, una volta per versione: si può passare alla Fase G1.

I numeri mostrati non cambiano e il loro salvataggio non dipende da questo modulo: gira in passi a sé del `giro` del registro,
DOPO il salvataggio dei mostrati, e un suo errore finisce nel log senza fermare gli altri passi. Se i nostri non si salvano prima
della prima partita, o se la loro misura non riesce TENTATIVI_MISURA volte, la giornata dei nostri è «persa» (riga con il motivo
in breve, che non conta) e parte un avviso solo.
Tabelle `registro_nostri` e `registro_i4` dell'archivio (NON si ricostruiscono). Regole classiche, solo id e numeri, niente nomi.
"""
from __future__ import annotations

import bisect
import contextlib
import json
import logging
import math
import sqlite3
from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd

from . import archivio, avvisi, consigli, nostri, stato_dati
from . import formazione as fz
from . import registro_giornate as rg
from .modello import Parametri
from .punteggio import COLONNA_VOTO

REGOLE = rg.REGOLE                      # regole classiche, come il registro dei mostrati
FINESTRA = 8                            # verdetto sulle ultime 8 giornate misurate della versione di oggi
MOSTRATE = 38                           # righe per giornata in «Stato dei dati»: al massimo una stagione
# soglie I4 (D1, 5/11/2026): errore del fantavoto al massimo +1% e punti al massimo −0,3 a giornata rispetto ai mostrati; scarto tra gol
# attesi e veri al massimo 0,03 in ogni fascia con almeno `nostri.MIN_CASI_FASCIA` casi
SOGLIE = {"errore": 0.01, "punti": -0.3, "scarto_gol": 0.03}
FASCE = len(nostri.FASCE_GOL) - 1
ESSENZIALI = ("p_voto", "mu")
FACOLTATIVE = ("mu_voto", "e_gol", "e_rigori", "e_assist", "minuti")
SENZA_TENTATIVI = "nessun tentativo prima della prima partita (servizio fermo o riavviato)"
TENTATIVI_MISURA = 3                    # misure non riuscite prima che la giornata diventi persa (il calcolo è pesante)
TITOLO = "SchieraXI: gol attesi nostri"
LOG = logging.getLogger(__name__)
# l'ultimo motivo per cui i nostri di una giornata non si sono salvati, {(stagione, giornata): motivo}, finché non si salvano o la
# giornata diventa persa. In memoria: dopo un riavvio la giornata diventa persa con il motivo SENZA_TENTATIVI.
_tentativi: dict[tuple[str, int], str] = {}


def _righe(cursore: sqlite3.Cursor) -> list[dict]:
    nomi = [c[0] for c in cursore.description]
    return [dict(zip(nomi, r)) for r in cursore.fetchall()]


def _ha_nostri(db: sqlite3.Connection, stagione: str, giornata: int) -> bool:
    return db.execute("SELECT 1 FROM registro_nostri WHERE stagione = ? AND giornata = ? LIMIT 1", (stagione, giornata)).fetchone() is not None


def _non_salvati(stagione: str, giornata: int, motivo: str, nel_log: bool = True) -> None:
    """Ricorda il motivo (diventa quello della giornata persa, se resta così) e lo scrive nel log. Solo numeri, tipi d'errore e
    nomi di colonne, mai dati."""
    _tentativi[(stagione, int(giornata))] = motivo
    if nel_log:
        LOG.warning("registro dei numeri nostri: giornata %s (%s) non salvata per ora: %s", giornata, stagione, motivo)


# ---------------------------------------------------------------- salvataggio, subito dopo i mostrati
def previsioni_dal_vivo(db: sqlite3.Connection, giornata: int) -> pd.DataFrame:
    """I numeri nostri della giornata (indice = id), come `consigli._calcola_previsioni` fa per i mostrati: stessi dati
    (`consigli.dati`, già in memoria), stesse probabili formazioni, stesse correzioni di «gioca N%»."""
    stagione = consigli.stagione_corrente()
    d = consigli.dati(db)
    prob = pd.read_sql_query("SELECT * FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio'",
                             db, params=(stagione, giornata))
    p = nostri.previsioni(d, stagione, giornata, REGOLE, probabili=None if prob.empty else prob, giocatori=d.calciatori,
                          fattori_probabili=stato_dati.fattori(db, stagione))
    return p.set_index("id") if "id" in p.columns else p


def da_salvare(db: sqlite3.Connection, adesso: datetime) -> tuple[str, int] | None:
    """(stagione, giornata) dei nostri da salvare adesso: i mostrati ci sono già, i nostri no, e la prima partita non è iniziata."""
    stagione = consigli.stagione_corrente()
    g = consigli.prossima_giornata(db, stagione, adesso)
    if g is None:
        return None
    inizio = avvisi.prima_partita(db, stagione, g)
    if inizio is None or adesso >= inizio:
        return None
    mostrati = db.execute("SELECT 1 FROM registro_giornate WHERE stagione = ? AND giornata = ? AND salvato IS NOT NULL",
                          (stagione, g)).fetchone()
    if not mostrati or _ha_nostri(db, stagione, g):
        return None
    return stagione, g


def _rigori_mostrati(db: sqlite3.Connection, giornata: int, previsioni_mostrate) -> dict[int, float]:
    """{id: rigori attesi mostrati} dalle previsioni mostrate (in cache). Servono solo alle fasce dei mostrati: se non si leggono,
    i nostri si salvano lo stesso, con i rigori mostrati vuoti (e un avviso nel log)."""
    try:
        prev, g, _ = (previsioni_mostrate or consigli.previsioni)(db, REGOLE, giornata)
    except Exception as e:  # noqa: BLE001 - un dato in più, non deve fermare il salvataggio dei nostri
        LOG.warning("registro dei numeri nostri: rigori attesi mostrati non letti (%s), si salvano vuoti", type(e).__name__)
        return {}
    if g != giornata or "e_rigori" not in prev.columns:
        LOG.warning("registro dei numeri nostri: nelle previsioni mostrate della giornata %s mancano i rigori attesi, si salvano vuoti",
                    giornata)
        return {}
    return {int(i): v for i, x in prev["e_rigori"].items() if (v := rg._numero(x)) is not None}


def _da_scrivere(db: sqlite3.Connection, stagione: str, giornata: int, prev: pd.DataFrame, previsioni_mostrate) -> tuple[list[dict], str]:
    """Le righe da salvare (i soli giocatori già in `registro_giocatori`) e, se non ce n'è nessuna, il motivo in breve."""
    if prev is None or len(prev) == 0:
        return [], "numeri nostri vuoti"
    if mancano := [c for c in ESSENZIALI if c not in prev.columns]:
        return [], f"nei numeri nostri mancano le colonne {', '.join(mancano)}"
    if mancano := [c for c in FACOLTATIVE if c not in prev.columns]:
        LOG.warning("registro dei numeri nostri: mancano le colonne %s, si salvano vuote", ", ".join(mancano))
    prev = prev[~prev.index.duplicated(keep="first")]
    rigori = _rigori_mostrati(db, giornata, previsioni_mostrate)
    ids = [int(i) for (i,) in db.execute("SELECT calciatore_id FROM registro_giocatori WHERE stagione = ? AND giornata = ? "
                                         "ORDER BY calciatore_id", (stagione, giornata))]
    righe = []
    for cid in ids:
        if cid not in prev.index:
            continue
        x = prev.loc[cid]
        r = {"stagione": stagione, "giornata": int(giornata), "calciatore_id": cid, "versione": nostri.VERSIONE,
             **{c: rg._numero(x.get(c)) for c in ESSENZIALI + FACOLTATIVE}, "e_rigori_mostrati": rigori.get(cid)}
        if r["p_voto"] is not None and r["mu"] is not None:
            righe.append(r)
    if righe:
        return righe, ""
    return [], f"nessuno dei {len(ids)} giocatori del registro ha «gioca N%» e fantavoto atteso nei numeri nostri"


def salva_se_serve(db: sqlite3.Connection, adesso: datetime, previsioni_nostre=None, previsioni_mostrate=None) -> int:
    """Se i mostrati della giornata sono salvati e i nostri no (prima della prima partita), salva i nostri degli stessi giocatori.
    `previsioni_nostre(db, giornata)` (di norma `previsioni_dal_vivo`), `previsioni_mostrate(db, regole, giornata)` (di norma
    `consigli.previsioni`, in cache). Restituisce le righe scritte (0 = niente da fare o niente salvato, con il motivo nel log). Un
    errore si ricorda come motivo e risale a `giro`, che lo scrive nel log con i punti del codice e passa ai passi dopo."""
    quale = da_salvare(db, adesso)
    if quale is None:
        return 0
    stagione, g = quale
    try:
        prev = (previsioni_nostre or previsioni_dal_vivo)(db, g)
    except Exception as e:
        _non_salvati(stagione, g, f"numeri nostri non calcolati ({type(e).__name__})", nel_log=False)
        raise
    righe, motivo = _da_scrivere(db, stagione, g, prev, previsioni_mostrate)
    if not righe:
        _non_salvati(stagione, g, motivo)
        return 0                            # si riprova al minuto dopo
    try:
        archivio.inserisci(db, "registro_nostri", righe)
        db.commit()
    except Exception as e:
        _non_salvati(stagione, g, f"scrittura non riuscita ({type(e).__name__})", nel_log=False)
        raise
    _tentativi.pop((stagione, int(g)), None)
    return len(righe)


def segna_perse(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Le giornate con i mostrati salvati, la prima partita iniziata e i nostri mai salvati diventano «perse» per i nostri, una volta
    sola: una riga in `registro_i4` con `persa` (il motivo in breve) e 0 voti, che non conta mai; l'avviso lo manda `avvisa_perse`.
    Come `registro_giornate.segna_perse`: contano le giornate dalla prima con i nostri (o tentata) della stagione in poi, da subito
    se i nostri c'erano già nelle stagioni prima; con i nostri mai partiti, nessuna. Restituisce le giornate segnate."""
    stagione = consigli.stagione_corrente()
    presenti = {int(g) for (g,) in db.execute("SELECT DISTINCT giornata FROM registro_nostri WHERE stagione = ?", (stagione,))}
    presenti |= {int(g) for (g,) in db.execute("SELECT giornata FROM registro_i4 WHERE stagione = ?", (stagione,))}
    tentate = {g for s, g in _tentativi if s == stagione}
    if presenti or tentate:
        da = min(presenti | tentate)
    elif db.execute("SELECT 1 FROM registro_nostri LIMIT 1").fetchone():
        da = 1
    else:
        return []                           # i nostri non sono mai partiti: le giornate di prima non erano loro
    perse = []
    for (g,) in db.execute("SELECT giornata FROM registro_giornate WHERE stagione = ? AND giornata >= ? AND salvato IS NOT NULL "
                           "ORDER BY giornata", (stagione, da)).fetchall():
        g = int(g)
        if g in presenti:
            continue
        inizio = avvisi.prima_partita(db, stagione, g)
        if inizio is None or adesso < inizio:
            continue
        motivo = _tentativi.get((stagione, g), SENZA_TENTATIVI)
        db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, voti, rose, persa, avvisato) VALUES (?, ?, ?, 0, 0, ?, 0)",
                   (stagione, g, nostri.VERSIONE, motivo))
        perse.append((stagione, g, motivo))
    if not perse:
        return []
    db.commit()
    for s, g, motivo in perse:
        _tentativi.pop((s, g), None)
        LOG.warning("registro dei numeri nostri: giornata %s (%s) persa, nostri non salvati prima della prima partita: %s", g, s, motivo)
    return [(s, g) for s, g, _ in perse]


# ---------------------------------------------------------------- misura a giornata finita
def _fascia(gol_attesi: float) -> int:
    """L'indice della fascia di `nostri.FASCE_GOL` (estremo sinistro compreso, come `verifica_pacchetti.gol_per_fasce`)."""
    return min(FASCE - 1, max(0, bisect.bisect_right(nostri.FASCE_GOL, gol_attesi) - 1))


def _rose(registro: list[dict], stagione: str, giornata: int):
    """Le stesse rose estratte a sorte di I3 (`registro_giornate._fascia`: stesso seme, stesso gruppo, stesso ordine)."""
    rng = np.random.default_rng(1000 * giornata + int(stagione[:4]))
    per_id = {int(r["calciatore_id"]): r for r in registro}
    pool = {ruolo: np.array(sorted(i for i, r in per_id.items() if r["ruolo"] == ruolo and r["p_voto"] >= rg.P_MINIMA_ROSA))
            for ruolo in rg.POSTI_ROSA}
    if any(len(pool[r]) < n for r, n in rg.POSTI_ROSA.items()):
        return
    for _ in range(rg.ROSE_SINTETICHE):
        yield [int(i) for r, n in rg.POSTI_ROSA.items() for i in rng.choice(pool[r], n, replace=False)]


def _giocatore(i: int, ruolo: str, r: dict) -> fz.Giocatore:
    """Il giocatore per `formazione.migliore` con i numeri della riga `r` (mostrati o nostri), come in I3."""
    return fz.Giocatore(i, "", ruolo, float(r["p_voto"]), float(r["mu"]), float(r["mu_voto"] if r["mu_voto"] is not None else 6.0))


def _punti(registro: list[dict], loro: dict[int, dict], fv: dict[int, float], voto: dict[int, float], stagione: str,
           giornata: int) -> tuple[int, float, float]:
    """(rose confrontate, punti veri con i nostri, punti veri con i mostrati) sulle rose di I3. Una rosa con un giocatore senza
    numeri nostri non si confronta."""
    mostrati = {int(r["calciatore_id"]): r for r in registro}
    rose, punti_n, punti_m = 0, 0.0, 0.0
    for ids in _rose(registro, stagione, giornata):
        if any(i not in loro for i in ids):
            continue
        try:
            fm = fz.migliore([_giocatore(i, mostrati[i]["ruolo"], mostrati[i]) for i in ids], REGOLE, rg.SIMULAZIONI)
            fn = fz.migliore([_giocatore(i, mostrati[i]["ruolo"], loro[i]) for i in ids], REGOLE, rg.SIMULAZIONI)
        except ValueError:
            continue
        gioca, fvs, voti = {i: i in fv for i in ids}, {i: fv.get(i, 0.0) for i in ids}, {i: voto.get(i, 0.0) for i in ids}
        punti_m += fz.punteggio(fm.titolari, fm.panchina, gioca, fvs, voti, REGOLE)
        punti_n += fz.punteggio(fn.titolari, fn.panchina, gioca, fvs, voti, REGOLE)
        rose += 1
    return rose, punti_n, punti_m


def misura_giornata(db: sqlite3.Connection, stagione: str, giornata: int) -> dict | None:
    """I pezzi di I4 di una giornata finita, solo per le partite giocate e con i voti (`registro_giornate._partite`) e per i giocatori
    con tutti e due i numeri (None se non ce n'è): `voti`, `sq_nostri`, `sq_mostrati` (chi ha preso voto); `rose`, `punti_nostri`,
    `punti_mostrati` (stesse rose di I3); `fasce` e `fasce_mostrati` (per fascia di gol attesi con i rigori, `nostri.gol_attesi`:
    [casi, somma attesi, somma veri], solo chi ha preso voto; veri = gol su azione + rigori segnati)."""
    valide, _ = rg._partite(db, stagione, giornata)
    registro = [r for r in _righe(db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = ? ORDER BY calciatore_id",
                                             (stagione, giornata))) if r["partita_id"] in valide]
    loro = {int(r["calciatore_id"]): r for r in _righe(db.execute(
        "SELECT * FROM registro_nostri WHERE stagione = ? AND giornata = ?", (stagione, giornata)))}
    if not registro or not loro:
        return None
    col = COLONNA_VOTO[REGOLE.fonte_voto]
    righe_voti = {int(v["calciatore_id"]): v for v in _righe(db.execute(
        f"SELECT * FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL", (stagione, giornata)))}
    fv: dict[int, float] = {}
    voto: dict[int, float] = {}
    for r in registro:
        i = int(r["calciatore_id"])
        if i in righe_voti and (f := rg.fantavoto_vero(righe_voti[i], r["ruolo"])) is not None:
            fv[i], voto[i] = f, float(righe_voti[i][col])
    coppie = [(r, loro[int(r["calciatore_id"])]) for r in registro if int(r["calciatore_id"]) in loro and int(r["calciatore_id"]) in fv]
    sq_n = sq_m = 0.0
    for m, n in coppie:
        i = int(m["calciatore_id"])
        sq_n += (n["mu"] - fv[i]) ** 2
        sq_m += (m["mu"] - fv[i]) ** 2
    veri = {i: float((righe_voti[i].get("gol") or 0) + (righe_voti[i].get("rig_segnati") or 0)) for i in fv}

    def fasce(e_gol: list, e_rigori: list, ids: list, par: Parametri) -> list[list]:
        f = [[0, 0.0, 0] for _ in range(FASCE)]
        ok = [k for k in range(len(ids)) if e_gol[k] is not None and e_rigori[k] is not None]
        if ok:
            attesi = nostri.gol_attesi(pd.DataFrame({"e_gol": [float(e_gol[k]) for k in ok],
                                                     "e_rigori": [float(e_rigori[k]) for k in ok]}), par)
            for k, a in zip(ok, attesi):
                b = _fascia(float(a))
                f[b] = [f[b][0] + 1, f[b][1] + float(a), f[b][2] + int(veri[ids[k]])]
        return [[c, round(s, 4), v] for c, s, v in f]

    ids = [int(m["calciatore_id"]) for m, _ in coppie]
    rose, punti_n, punti_m = _punti(registro, loro, fv, voto, stagione, giornata)
    return {"voti": len(coppie), "sq_nostri": round(sq_n, 4), "sq_mostrati": round(sq_m, 4),
            "rose": rose, "punti_nostri": round(punti_n, 3), "punti_mostrati": round(punti_m, 3),
            "fasce": fasce([n["e_gol"] for _, n in coppie], [n["e_rigori"] for _, n in coppie], ids, nostri.parametri()),
            "fasce_mostrati": fasce([m["e_gol"] for m, _ in coppie], [n["e_rigori_mostrati"] for _, n in coppie], ids, Parametri())}


def _misura_non_riuscita(db: sqlite3.Connection, stagione: str, giornata: int, versione: str, e: Exception) -> None:
    """Conta il tentativo nell'archivio (vale anche dopo un riavvio) e lo scrive nel log (tipo d'errore e punti del codice, mai il
    messaggio). Al TENTATIVI_MISURA-esimo la giornata diventa «persa» con il motivo: non si rifà più il calcolo pesante e
    `avvisa_perse` manda un avviso solo."""
    with contextlib.suppress(sqlite3.Error):
        db.rollback()
    prima = db.execute("SELECT tentativi FROM registro_i4 WHERE stagione = ? AND giornata = ?", (stagione, giornata)).fetchone()
    n = (prima[0] or 0) + 1 if prima else 1
    persa = f"misura non riuscita {n} volte ({type(e).__name__})" if n >= TENTATIVI_MISURA else None
    db.execute("INSERT OR REPLACE INTO registro_i4 (stagione, giornata, versione, voti, rose, tentativi, persa, avvisato) "
               "VALUES (?, ?, ?, 0, 0, ?, ?, 0)", (stagione, giornata, versione, n, persa))
    db.commit()
    LOG.warning("registro dei numeri nostri: misura dei numeri nostri della giornata %s (%s) non riuscita (%s), tentativo %s di %s%s "
                "in %s", giornata, stagione, type(e).__name__, n, TENTATIVI_MISURA, ": giornata persa" if persa else "", rg._dove(e))


def chiudi_giornate(db: sqlite3.Connection, adesso: datetime) -> list[tuple[str, int]]:
    """Misura, dalla più vecchia, le giornate già misurate dal registro dei mostrati che hanno i numeri nostri e non sono ancora
    misurate né perse in `registro_i4`. La versione è quella dei numeri salvati. Una misura che va in errore non ferma le giornate
    dopo: si riprova al giro dopo, al massimo TENTATIVI_MISURA volte (`_misura_non_riuscita`). Restituisce quelle misurate."""
    fatte = []
    for stagione, g in db.execute(
            "SELECT g.stagione, g.giornata FROM registro_giornate g WHERE g.misurato IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM registro_nostri n WHERE n.stagione = g.stagione AND n.giornata = g.giornata) "
            "AND NOT EXISTS (SELECT 1 FROM registro_i4 i WHERE i.stagione = g.stagione AND i.giornata = g.giornata "
            "AND (i.misurato IS NOT NULL OR i.persa IS NOT NULL)) "
            "ORDER BY g.stagione, g.giornata").fetchall():
        versione = db.execute("SELECT MIN(versione) FROM registro_nostri WHERE stagione = ? AND giornata = ?", (stagione, g)).fetchone()[0]
        try:
            m = misura_giornata(db, stagione, g) or {"voti": 0, "rose": 0}
        except Exception as e:  # noqa: BLE001 - contata e nel log; le giornate dopo si misurano lo stesso
            _misura_non_riuscita(db, stagione, int(g), versione, e)
            continue
        prima = db.execute("SELECT tentativi FROM registro_i4 WHERE stagione = ? AND giornata = ?", (stagione, g)).fetchone()
        db.execute("INSERT OR REPLACE INTO registro_i4 (stagione, giornata, versione, misurato, voti, sq_nostri, sq_mostrati, rose, "
                   "punti_nostri, punti_mostrati, fasce, fasce_mostrati, tentativi, avvisato) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                   (stagione, g, versione, adesso.isoformat(timespec="seconds"), m["voti"], m.get("sq_nostri"), m.get("sq_mostrati"),
                    m["rose"], m.get("punti_nostri"), m.get("punti_mostrati"),
                    json.dumps(m["fasce"]) if "fasce" in m else None,
                    json.dumps(m["fasce_mostrati"]) if "fasce_mostrati" in m else None, prima[0] if prima else 0))
        db.commit()
        fatte.append((stagione, int(g)))
    return fatte


# ---------------------------------------------------------------- medie sulla finestra e soglie
def _fasce_sommate(righe: list[dict], chiave: str) -> list[list]:
    tot = [[0, 0.0, 0] for _ in range(FASCE)]
    for r in righe:
        for b, f in enumerate(rg._lista(r.get(chiave))[:FASCE]):
            if isinstance(f, list) and len(f) == 3:
                tot[b] = [tot[b][0] + int(f[0]), tot[b][1] + float(f[1]), tot[b][2] + int(f[2])]
    return tot


def _gol(fasce: list[list]) -> tuple[float | None, float | None]:
    """(scarto più grande |veri − attesi| a partita nelle fasce con almeno MIN_CASI_FASCIA casi, attesi / veri su tutte)."""
    piene = [abs(v - s) / n for n, s, v in fasce if n >= nostri.MIN_CASI_FASCIA]
    attesi, veri = sum(s for _, s, _ in fasce), sum(v for _, _, v in fasce)
    return (round(max(piene), 3) if piene else None), (round(attesi / veri, 3) if veri else None)


def _numeri(righe: list[dict]) -> dict:
    """I numeri di I4 di più giornate, sommando i pezzi (ogni giocatore e ogni rosa pesano uguale)."""
    somma = lambda k: sum(float(r.get(k) or 0) for r in righe)  # noqa: E731
    voti, rose = int(somma("voti")), int(somma("rose"))
    sq_n, sq_m = somma("sq_nostri"), somma("sq_mostrati")
    scarto, su_veri = _gol(_fasce_sommate(righe, "fasce"))
    scarto_m, su_veri_m = _gol(_fasce_sommate(righe, "fasce_mostrati"))
    return {"voti": voti, "rose": rose,
            "errore_pct": round(math.sqrt(sq_n / sq_m) - 1, 4) if voti and sq_m > 0 else None,
            "punti": round((somma("punti_nostri") - somma("punti_mostrati")) / rose, 3) if rose else None,
            "scarto_gol": scarto, "gol_su_veri": su_veri, "scarto_gol_mostrati": scarto_m, "gol_su_veri_mostrati": su_veri_m}


def medie(righe: list[dict], versione: str | None = None) -> dict:
    """Le medie di I4 delle giornate misurate della versione di oggi (`nostri.VERSIONE`, o `versione`): le altre non contano.
    `errore_pct` = √(Σ sq_nostri / Σ sq_mostrati) − 1; `punti` = punti veri in più dei nostri per rosa e giornata; `scarto_gol`,
    `gol_su_veri` (e gli stessi dei mostrati, per confronto). `verdetto` solo con FINESTRA giornate; allora `regge` dice per ogni
    soglia se è rispettata (None = non si può dire) e `regge_tutto` se lo sono tutte e tre."""
    versione = versione or nostri.VERSIONE
    righe = [r for r in righe if r.get("versione") == versione and (r.get("voti") or 0) > 0]
    m = {"giornate": len(righe), "versione": versione, **_numeri(righe)}
    m["verdetto"] = v = len(righe) >= FINESTRA
    m["regge"] = {"errore": None if not v or m["errore_pct"] is None else m["errore_pct"] <= SOGLIE["errore"],
                  "punti": None if not v or m["punti"] is None else m["punti"] >= SOGLIE["punti"],
                  "gol": None if not v or m["scarto_gol"] is None else m["scarto_gol"] <= SOGLIE["scarto_gol"]}
    m["regge_tutto"] = v and all(ok is True for ok in m["regge"].values())
    return m


def _misurate(db: sqlite3.Connection, versione: str | None = None, quante: int = FINESTRA) -> list[dict]:
    """Le ultime `quante` giornate misurate con dei dati della versione di oggi, dalla più vecchia."""
    return list(reversed(_righe(db.execute(
        "SELECT * FROM registro_i4 WHERE versione = ? AND misurato IS NOT NULL AND voti > 0 ORDER BY stagione DESC, giornata DESC "
        "LIMIT ?", (versione or nostri.VERSIONE, quante)))))


def riepilogo(db: sqlite3.Connection) -> dict:
    """Per «Stato dei dati»: versione di oggi, finestra, soglie, le medie (come `medie`) e una riga per ogni giornata con i nostri
    salvati o persi, dalla più recente (al massimo MOSTRATE), con i suoi numeri (None finché non è misurata) e `persa` (None, o il
    motivo in breve). Solo giornate e numeri, niente giocatori."""
    giornate: dict[tuple[str, int], dict] = {}
    for s, g, versione, n in db.execute("SELECT stagione, giornata, MIN(versione), COUNT(*) FROM registro_nostri "
                                        "GROUP BY stagione, giornata ORDER BY stagione DESC, giornata DESC LIMIT ?", (MOSTRATE,)):
        giornate[(s, int(g))] = {"versione": versione, "giocatori": n}
    misure = {(r["stagione"], int(r["giornata"])): r for r in _righe(db.execute(
        "SELECT * FROM registro_i4 ORDER BY stagione DESC, giornata DESC LIMIT ?", (MOSTRATE,)))}
    per_giornata = []
    for chiave in sorted(set(giornate) | set(misure), reverse=True)[:MOSTRATE]:
        salvata, r = giornate.get(chiave, {}), misure.get(chiave, {})
        numeri = _numeri([r]) if r.get("misurato") and (r.get("voti") or 0) > 0 else {}
        per_giornata.append({
            "stagione": chiave[0], "giornata": chiave[1], "versione": r.get("versione") or salvata.get("versione"),
            "giocatori": salvata.get("giocatori", 0), "misurato": r.get("misurato"), "voti": r.get("voti"), "rose": r.get("rose"),
            **{k: numeri.get(k) for k in ("errore_pct", "punti", "scarto_gol", "gol_su_veri")}, "persa": r.get("persa")})
    return {"finestra": FINESTRA, "soglie": dict(SOGLIE), **medie(_misurate(db)), "per_giornata": per_giornata}


# ---------------------------------------------------------------- avvisi al proprietario (canale della sentinella)
def _num(x: float, cifre: int, segno: bool = False) -> str:
    testo = f"{abs(x):.{cifre}f}".replace(".", ",")
    return (("−" if x < 0 else "+") + testo) if segno else testo


def testo_avviso(m: dict) -> tuple[str, str]:
    """Titolo e testo dell'avviso «reggono»: versione e i tre numeri, mai nomi."""
    return (TITOLO, f"I gol attesi nostri (solo Fantacalcio.it, versione {m['versione']}) reggono da {m['giornate']} giornate dal "
            f"vivo: errore del fantavoto {_num(100 * m['errore_pct'], 1, True)}% (al massimo +1%), punti "
            f"{_num(m['punti'], 2, True)} a giornata (almeno −0,3), scarto dei gol attesi per fasce {_num(m['scarto_gol'], 3)} "
            "(al massimo 0,03). Si può passare alla Fase G1 del piano 2026-11-06-gol-attesi-nostri (dettagli in Stato dei dati).")


def avvisa(db: sqlite3.Connection, manda: Callable[[str, str], bool]) -> bool:
    """La prima volta che le ultime FINESTRA giornate della versione di oggi reggono tutte e tre le soglie, un avviso
    (`manda(titolo, testo)`, vero se è partito), una volta per versione. Se non parte si riprova al giro dopo. «Fuori soglia» qui non
    avvisa: all'inizio lo sarà di sicuro. True se ha mandato qualcosa."""
    finestra = _misurate(db)
    m = medie(finestra)
    if not m["regge_tutto"] or db.execute("SELECT 1 FROM registro_i4 WHERE versione = ? AND persa IS NULL AND avvisato = 1",
                                          (m["versione"],)).fetchone():
        return False
    if not manda(*testo_avviso(m)):
        return False
    db.execute("UPDATE registro_i4 SET avvisato = 1 WHERE stagione = ? AND giornata = ?", (finestra[-1]["stagione"], finestra[-1]["giornata"]))
    db.commit()
    return True


def testo_perse(righe: list[dict]) -> tuple[str, str]:
    """Titolo e testo dell'avviso delle giornate perse dei nostri (non salvati prima della prima partita, o misura non riuscita):
    giornate e motivi in breve, mai nomi."""
    voci = [f"• giornata {r['giornata']} ({r['stagione']}): {r['persa']}" for r in righe]
    return (TITOLO, "Giornate perse per la misura dal vivo dei numeri nostri: non contano nel verdetto (i numeri mostrati sono salvi; "
            "dettagli in Stato dei dati e nel log del server):\n" + "\n".join(voci))


def avvisa_perse(db: sqlite3.Connection, manda: Callable[[str, str], bool]) -> bool:
    """Un avviso solo per le giornate perse dei nostri non ancora avvisate, tutte insieme. Se non parte si riprova al giro dopo."""
    righe = _righe(db.execute("SELECT stagione, giornata, persa FROM registro_i4 WHERE persa IS NOT NULL AND avvisato = 0 "
                              "ORDER BY stagione, giornata"))
    if not righe or not manda(*testo_perse(righe)):
        return False
    db.executemany("UPDATE registro_i4 SET avvisato = 1 WHERE stagione = ? AND giornata = ?", [(r["stagione"], r["giornata"]) for r in righe])
    db.commit()
    return True
