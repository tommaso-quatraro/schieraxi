"""Misura in laboratorio del consiglio di formazione (#166, indicatori C1-C4): `python -m fanta verifica --consiglio`.

È il «prima e dopo» dei lavori sul consiglio (proposta in docs/superpowers/specs/2026-11-05-consiglio-giusto-proposta.md,
§2 e §3 L0). Misura soltanto: non cambia nessun numero dell'app. Due parti:
A. le giornate già giocate della stagione, come `verifica` (per ogni giornata solo i dati di prima, senza probabili): punti veri
   della consigliata contro S1 (fantamedia con il «gioca N%» del modello, la scelta semplice di `verifica`), S2 (fantamedia tra
   chi ha preso voto la giornata prima, senza modello: quello che farebbe chi non ha l'app) e il senno di poi;
B. una giornata con le probabili, per la strada vera dell'app (`consigli.formazione`): titolari che non giocano, scelte che
   sembrano storte, «perché questo numero» senza un motivo del giocatore.
In tutte e due la stabilità: la scelta rifatta con un altro seme della simulazione (stessi dati) e con un piccolo ritocco dei
dati. Semi fissi: rifatta sugli stessi dati, la misura dà gli stessi numeri.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from statistics import median

import numpy as np
import pandas as pd

from . import consigli, verifica
from . import formazione as fz
from .lega import Rose
from .modello import Parametri, previsioni
from .notifiche import SOGLIA_AVVISO_PUNTI
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import RUOLI, Regole

SIMULAZIONI = 600                   # come l'app (consigli.formazione)
SEME = 166                          # seme dei ritocchi: gli stessi dati danno gli stessi numeri
SEMI = (8, 9, 10)                   # altri semi della simulazione (l'app usa sempre quello di fz.Valutatore)
RITOCCHI = 3                        # piccoli aggiornamenti dei dati per ogni caso
SCARTO_P, SCARTO_MU = 0.03, 0.10    # «piccolo aggiornamento»: ogni «gioca N%» si sposta di circa 3 punti, ogni fantavoto atteso di 0,1
IMPROBABILE_SOTTO = 0.2             # C3: un titolare che gioca meno di così...
COMPAGNO_DA = 0.5                   # ...con un compagno di ruolo fuori dagli 11 che gioca almeno così
SOGLIA_CAMBIO = SOGLIA_AVVISO_PUNTI  # C2 (decisione D2): un cambio di titolari deve valere almeno quanto l'avviso alla scadenza
MAX_SENZA_MOTIVO = 0.10             # C4: titolari senza un motivo proprio nel «perché», al massimo il 10%
NON_PROPRI = ("gioca", "partita", "altro")   # motivi del «perché questo numero» che non parlano del giocatore
P_S2 = (0.9, 0.1)                   # S2: «gioca» chi ha preso voto la giornata prima, gli altri quasi mai
FANTAMEDIA_SENZA_VOTI = 5.5         # come `verifica`: chi non ha ancora voti in stagione


@dataclass(frozen=True)
class Prova:
    """Una prova di stabilità: la scelta rifatta con un altro seme o con i dati ritoccati, contro quella di partenza."""
    tipo: str                 # "seme" o "ritocco"
    cambiati: int             # titolari diversi da quelli di partenza
    modulo_cambiato: bool
    guadagno: float           # punti attesi della nuova meno quelli dei titolari di prima, ricalcolati con gli stessi dati
    motivata: bool = False    # un titolare di prima è diventato improbabile: il cambio è giusto anche se vale poco


# ---------------------------------------------------------------- C1: il riferimento semplice
def rosa_s2(rosa: list[fz.Giocatore], ha_giocato, fantamedia) -> list[fz.Giocatore]:
    """S2: la rosa come la vedrebbe chi non ha l'app. Gioca chi ha preso voto la giornata prima; vale la sua fantamedia."""
    return [fz.Giocatore(g.id, g.nome, g.ruolo, P_S2[0] if g.id in ha_giocato else P_S2[1],
                         float(fantamedia.get(g.id, FANTAMEDIA_SENZA_VOTI)), 6.0) for g in rosa]


# ---------------------------------------------------------------- C3: titolari che non giocano
def _fuori(s: dict) -> bool:
    return s.get("stato") in consigli.FUORI or s.get("titolarita") == "fuori"


def _esclusi(f: dict) -> list[dict]:
    """Le schede dei giocatori della rosa che non sono tra gli 11 (panchina e fuori)."""
    tit = {int(x["id"]) for x in f["titolari"]}
    return [s for s in f["schede"].values() if int(s["id"]) not in tit]


def non_giocano(f: dict) -> list[tuple[int, int | None]]:
    """I titolari della formazione `f` (come la dà `consigli.formazione`) che giocano meno del 20% o sono fuori, ognuno con il
    miglior compagno di ruolo fuori dagli 11 che gioca almeno il 50% (None se non c'è): [(titolare, compagno)]."""
    esclusi = _esclusi(f)
    esito = []
    for t in f["titolari"]:
        if not (_fuori(t) or t["p_voto"] < IMPROBABILE_SOTTO):
            continue
        compagni = [s for s in esclusi if s["ruolo"] == t["ruolo"] and s["p_voto"] >= COMPAGNO_DA and not _fuori(s)]
        meglio = max(compagni, key=lambda s: s["punti_attesi"], default=None)
        esito.append((int(t["id"]), None if meglio is None else int(meglio["id"])))
    return esito


def costo_compagno(rosa: list[fz.Giocatore], titolari: list[int], regole: Regole, val: fz.Valutatore,
                   titolare: int, compagno: int) -> float:
    """Punti attesi persi mettendo `compagno` al posto di `titolare` (negativo = se ne guadagnano). La panchina si ricalcola
    come fa l'app, con le stesse simulazioni per le due formazioni."""
    per_id = {g.id: g for g in rosa}
    prima = [per_id[i] for i in titolari]
    dopo = [per_id[compagno] if i == titolare else per_id[i] for i in titolari]
    return (val.atteso(prima, fz._panchina(rosa, prima, regole))
            - val.atteso(dopo, fz._panchina(rosa, dopo, regole)))


# ---------------------------------------------------------------- C4: scelte che sembrano storte e il loro perché
def _con_riga(m: dict) -> set[int]:
    """I titolari con una riga sotto il campo nel modulo `m`, come li mostra l'app: il perché della scelta (`perche_scelta`, #356);
    da un server senza quel campo, la nota «titolare anche se incerto» (`incerti`)."""
    if isinstance(m.get("perche_scelta"), list):
        return {int(r["titolare"]) for r in m["perche_scelta"]}
    return {int(i["titolare"]) for i in m.get("incerti") or []}


def scelte_storte(f: dict) -> dict:
    """Per reparto: c'è un escluso con più punti attesi del titolare più debole? È «spiegata» se quel titolare ha la sua riga sotto
    il campo nel modulo scelto (`_con_riga`). Contano solo i reparti con almeno un escluso."""
    con_riga = {i for m in f["moduli"] if m["modulo"] == f["modulo"] for i in _con_riga(m)}
    esclusi = _esclusi(f)
    reparti = storte = spiegate = 0
    for ruolo in RUOLI:
        t_r = [s for s in f["titolari"] if s["ruolo"] == ruolo]
        e_r = [s for s in esclusi if s["ruolo"] == ruolo]
        if not t_r or not e_r:
            continue
        reparti += 1
        debole = min(t_r, key=lambda s: s["punti_attesi"])
        if max(s["punti_attesi"] for s in e_r) > debole["punti_attesi"]:
            storte += 1
            spiegate += int(debole["id"]) in con_riga
    return {"reparti": reparti, "storte": storte, "spiegate": spiegate}


def perche_titolari(f: dict) -> dict:
    """Titolari con «perché questo numero» vuoto, e senza un motivo proprio (vuoto, oppure solo «gioca N%», partita o «altro»)."""
    motivi = [[m["chiave"] for m in t.get("perche_numero") or []] for t in f["titolari"]]
    return {"titolari": len(motivi), "vuoti": sum(not m for m in motivi),
            "senza_motivo": sum(all(c in NON_PROPRI for c in m) for m in motivi)}


# ---------------------------------------------------------------- C2: stabilità
def motivata(prima: dict[int, float], dopo: dict[int, float], titolari: list[int]) -> bool:
    """Vero se un titolare di prima, con i dati nuovi, è sceso sotto il 20% (e prima non lo era)."""
    return any(prima[i] >= IMPROBABILE_SOTTO and dopo[i] < IMPROBABILE_SOTTO for i in titolari)


def _ritocca(rosa: list[fz.Giocatore], rng: np.random.Generator) -> list[fz.Giocatore]:
    return [fz.Giocatore(g.id, g.nome, g.ruolo, float(np.clip(g.p + rng.normal(0, SCARTO_P), 0.01, 0.99)),
                         g.mu + float(rng.normal(0, SCARTO_MU)), g.mu_voto) for g in rosa]


def stabilita(rosa: list[fz.Giocatore], titolari: list[int], modulo: str, regole: Regole, simulazioni: int,
              rng: np.random.Generator) -> list[Prova]:
    """Rifà la scelta con gli altri semi (stessi dati) e con RITOCCHI piccoli aggiornamenti dei dati (seme dell'app), e la
    confronta con i titolari di partenza. Il guadagno usa le simulazioni della prova per tutte e due le formazioni."""
    varianti = [("seme", rosa, s) for s in SEMI] + [("ritocco", _ritocca(rosa, rng), None) for _ in range(RITOCCHI)]
    prima = {g.id: g.p for g in rosa}
    prove = []
    for tipo, rr, seme in varianti:
        val = fz.Valutatore(rr, regole, simulazioni) if seme is None else fz.Valutatore(rr, regole, simulazioni, seme=seme)
        nuova = fz.migliore(rr, regole, simulazioni, valutatore=val)
        per_id = {g.id: g for g in rr}
        vecchi = [per_id[i] for i in titolari]
        guadagno = nuova.atteso - val.atteso(vecchi, fz._panchina(rr, vecchi, regole))
        cambiati = len(titolari) - len(set(titolari) & {g.id for g in nuova.titolari})
        prove.append(Prova(tipo, cambiati, nuova.modulo != modulo, float(guadagno),
                           tipo == "ritocco" and motivata(prima, {g.id: g.p for g in rr}, titolari)))
    return prove


def riassumi(prove: list[Prova], tipo: str) -> dict:
    """Quante prove di un tipo cambiano almeno 1 titolare, 3 o più, il modulo; quanto vale la nuova quando cambia (mediana);
    quanti cambi valgono meno della soglia senza un titolare diventato improbabile (C2 li vuole a zero)."""
    x = [p for p in prove if p.tipo == tipo]
    cambiate = [p for p in x if p.cambiati >= 1]
    return {"prove": len(x), "almeno_uno": len(cambiate), "tre_o_piu": sum(1 for p in x if p.cambiati >= 3),
            "modulo": sum(1 for p in x if p.modulo_cambiato),
            "mediana_guadagno": float(median(p.guadagno for p in cambiate)) if cambiate else None,
            "sotto_soglia": sum(1 for p in cambiate if p.guadagno < SOGLIA_CAMBIO and not p.motivata)}


# ---------------------------------------------------------------- parte A: giornate già giocate
def _rosa_modello(prev: pd.DataFrame, ids: list[int]) -> list[fz.Giocatore]:
    return [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                         float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids if i in prev.index]


def parte_giocate(d, regole: Regole, rose: Rose, stagione: str, simulazioni: int = SIMULAZIONI) -> dict:
    """Parte A: per ogni giornata giocata della stagione (dalla 2) e ogni rosa con almeno MIN_GIOCATORI_ROSA presenti, i punti
    veri della consigliata, di S1, di S2 e del senno di poi, i titolari senza voto e la stabilità della consigliata."""
    col = COLONNA_VOTO[regole.fonte_voto]
    par = Parametri()
    pt, vo = d.partite, d.voti
    giornate = sorted(int(g) for g in pt.loc[(pt["stagione"] == stagione) & (pt["giocata"] == 1), "giornata"].unique() if g >= 2)
    rose_ids = [[g.id for g in s.giocatori if g.id] for s in rose.squadre]
    righe, prove = [], []
    for g in giornate:
        giocate = set(pt.loc[(pt["stagione"] == stagione) & (pt["giornata"] == g) & (pt["giocata"] == 1), "id"])
        prev = previsioni(d, stagione, g, regole, par)
        if prev.empty or not giocate:
            continue
        prev = prev[prev["partita"].isin(giocate)].set_index("id")       # chi ha giocato una partita già finita
        reali = vo[(vo["stagione"] == stagione) & (vo["giornata"] == g)].drop_duplicates("calciatore_id").set_index("calciatore_id")
        fv_vero = {i: fantavoto(reali.loc[i].to_dict(), prev.at[i, "ruolo"], regole) for i in prev.index
                   if i in reali.index and pd.notna(reali.at[i, col])}
        voto_vero = {i: float(reali.at[i, col]) for i in fv_vero}
        prima = vo[(vo["stagione"] == stagione) & (vo["giornata"] == g - 1) & vo[col].notna()]
        ha_giocato = {int(x) for x in prima["calciatore_id"].dropna()}
        fm = verifica._fantamedia(d, stagione, g, regole)
        for k, ids in enumerate(rose_ids):
            mod = _rosa_modello(prev, ids)
            if len(mod) < verifica.MIN_GIOCATORI_ROSA:
                continue
            s1 = [fz.Giocatore(x.id, x.nome, x.ruolo, x.p, float(fm.get(x.id, FANTAMEDIA_SENZA_VOTI)), 6.0) for x in mod]
            try:
                cons = fz.migliore(mod, regole, simulazioni, valutatore=fz.Valutatore(mod, regole, simulazioni))
                scelte = {"consigliata": cons, "s1": fz.migliore(s1, regole, simulazioni),
                          "s2": fz.migliore(rosa_s2(mod, ha_giocato, fm), regole, simulazioni)}
            except ValueError:      # troppo pochi presenti in qualche ruolo
                continue
            gioca = {x.id: x.id in fv_vero for x in mod}
            fv = {x.id: fv_vero.get(x.id, 0.0) for x in mod}
            voti = {x.id: voto_vero.get(x.id, 0.0) for x in mod}
            riga = {"giornata": g} | {n: fz.punteggio(f.titolari, f.panchina, gioca, fv, voti, regole) for n, f in scelte.items()}
            riga["perfetta"] = verifica._perfetta(mod, fv_vero, regole)
            riga["senza_voto_consigliata"] = sum(not gioca[x.id] for x in cons.titolari)
            riga["senza_voto_s2"] = sum(not gioca[x.id] for x in scelte["s2"].titolari)
            riga["scoperti"] = fz.chi_va_a_punteggio(cons.titolari, cons.panchina, gioca, regole)[1]
            righe.append(riga)
            prove += stabilita(mod, [x.id for x in cons.titolari], cons.modulo, regole, simulazioni,
                               np.random.default_rng([SEME, 1, g, k]))
    if not righe:
        return {"stagione": stagione, "giornate": [], "casi": 0, "prove": prove}
    t = pd.DataFrame(righe)
    diff = t["consigliata"] - t["s2"]
    per_g = t.groupby("giornata")[["consigliata", "s2"]].mean()
    con_perfetta = t[t["perfetta"] > 0]
    return {
        "stagione": stagione, "giornate": sorted(int(x) for x in t["giornata"].unique()), "casi": len(t),
        "punti": {k: float(t[k].mean()) for k in ("consigliata", "s1", "s2", "perfetta")},
        "differenza_s2": float(diff.mean()),
        "errore_standard": float(diff.std(ddof=1) / math.sqrt(len(diff))) if len(diff) > 1 else None,
        "casi_pari_s2": int((t["consigliata"] >= t["s2"]).sum()),
        "giornate_pari_s2": int((per_g["consigliata"] >= per_g["s2"]).sum()),
        "quota_perfetta": float(100 * (con_perfetta["consigliata"] / con_perfetta["perfetta"]).mean()) if len(con_perfetta) else None,
        "senza_voto": {"consigliata": float(t["senza_voto_consigliata"].mean()), "s2": float(t["senza_voto_s2"].mean())},
        "scoperti": float(t["scoperti"].mean()), "prove": prove,
    }


# ---------------------------------------------------------------- parte B: una giornata con le probabili, come l'app
def caso_app(f: dict, rosa: list[fz.Giocatore], regole: Regole, simulazioni: int, rng: np.random.Generator) -> dict:
    """Le misure di una squadra sulla formazione dell'app `f`; `rosa` = gli stessi giocatori con i numeri del modello."""
    titolari = [int(x["id"]) for x in f["titolari"]]
    val = fz.Valutatore(rosa, regole, simulazioni)          # le stesse simulazioni dell'app (stesso seme)
    ng = non_giocano(f)
    return {"non_giocano": len(ng), "con_compagno": sum(1 for _, c in ng if c is not None),
            "costi": [costo_compagno(rosa, titolari, regole, val, t, c) for t, c in ng if c is not None],
            **scelte_storte(f), **perche_titolari(f),
            "prove": stabilita(rosa, titolari, f["modulo"], regole, simulazioni, rng)}


def giornata_con_probabili(db: sqlite3.Connection, stagione: str) -> int | None:
    """L'ultima giornata della stagione che ha le probabili nell'archivio (None se nessuna)."""
    r = db.execute("SELECT MAX(giornata) FROM probabili WHERE stagione = ? AND fonte = 'fantacalcio'", (stagione,)).fetchone()
    return None if r is None or r[0] is None else int(r[0])


def parte_probabili(db: sqlite3.Connection, regole: Regole, rose: Rose, giornata: int,
                    simulazioni: int = SIMULAZIONI) -> dict:
    """Parte B: la formazione dell'app (`consigli.formazione`) per ogni squadra della lega nella giornata indicata."""
    prev, giornata, con_probabili = consigli.previsioni(db, regole, giornata)
    casi = []
    for k, s in enumerate(rose.squadre):
        try:
            f = consigli.formazione(db, regole, rose, s.nome, giornata=giornata, simulazioni=simulazioni)
        except ValueError:          # squadra che non si riesce a formare
            continue
        rosa = _rosa_modello(prev, [g.id for g in s.giocatori if g.id is not None])     # come consigli._calcola_formazione
        casi.append(caso_app(f, rosa, regole, simulazioni, np.random.default_rng([SEME, 2, giornata, k])))

    def somma(chiave):
        return sum(c[chiave] for c in casi)
    return {"giornata": giornata, "con_probabili": con_probabili, "squadre": len(casi),
            **{k: somma(k) for k in ("titolari", "non_giocano", "con_compagno", "reparti", "storte", "spiegate", "vuoti",
                                     "senza_motivo")},
            "squadre_non_giocano": sum(1 for c in casi if c["non_giocano"]),
            "costi": [x for c in casi for x in c["costi"]], "prove": [p for c in casi for p in c["prove"]]}


def misura(d, db: sqlite3.Connection, regole: Regole, rose: Rose, stagione: str, giornata: int | None = None,
           simulazioni: int = SIMULAZIONI) -> dict:
    """Le due parti. `giornata` = quella con le probabili della parte B (None = l'ultima che le ha; nessuna = parte B saltata).
    Una giornata senza previsioni (per esempio un numero oltre il calendario) salta la parte B e ne tiene il motivo."""
    g = giornata or giornata_con_probabili(db, stagione)
    m = {"giocate": parte_giocate(d, regole, rose, stagione, simulazioni), "probabili": None, "simulazioni": simulazioni}
    if g:
        try:
            m["probabili"] = parte_probabili(db, regole, rose, g, simulazioni)
        except ValueError as e:
            m["saltata"] = {"giornata": g, "motivo": str(e)}
    return m


# ---------------------------------------------------------------- esiti e rapporto
def esiti(m: dict) -> dict[str, bool | None]:
    """Per ogni indicatore: True = dentro la soglia della proposta, False = fuori, None = non misurato."""
    a, b = m.get("giocate"), m.get("probabili")
    ha_a = bool(a and a.get("casi"))
    c2 = riassumi((a["prove"] if a else []) + (b["prove"] if b else []), "ritocco")
    ha_b = bool(b and b.get("titolari"))
    return {
        "C1": a["differenza_s2"] >= 0 if ha_a else None,
        "C2": c2["sotto_soglia"] == 0 if c2["prove"] else None,
        "C3": b["con_compagno"] == 0 if ha_b else None,
        "C4": (b["storte"] == b["spiegate"] and b["senza_motivo"] / b["titolari"] <= MAX_SENZA_MOTIVO) if ha_b else None,
    }


def _n(x: float, cifre: int = 2, segno: bool = False) -> str:
    """Numero all'italiana: virgola per i decimali."""
    return (f"{x:+.{cifre}f}" if segno else f"{x:.{cifre}f}").replace(".", ",")


def _punti_attesi(x: float) -> str:
    """«1 punto atteso», «1,5 punti attesi»."""
    testo = _n(x, 1).removesuffix(",0")
    return f"{testo} punto atteso" if x == 1 else f"{testo} punti attesi"


def _quota(k: int, n: int) -> str:
    return f"{k} su {n} ({round(100 * k / n)}%)" if n else f"{k} su 0"


def _esito(v: bool | None) -> str:
    return "non misurato" if v is None else "dentro la soglia" if v else "fuori dalla soglia"


def _stabilita(scrivi, nome: str, r: dict, ritocco: bool) -> None:
    if not r["prove"]:
        scrivi(f"    {nome}: nessuna prova")
        return
    if ritocco:
        mediana = "" if r["mediana_guadagno"] is None else f"; quando cambia, la nuova vale in mediana {_n(r['mediana_guadagno'], segno=True)} punti attesi"
        scrivi(f"    {nome}: 3 o più titolari cambiano in {_quota(r['tre_o_piu'], r['prove'])}; almeno 1 in "
               f"{_quota(r['almeno_uno'], r['prove'])}; modulo cambiato {r['modulo']} volte{mediana}")
        scrivi(f"       cambi che valgono meno di {_punti_attesi(SOGLIA_CAMBIO)}: {r['sotto_soglia']}")
    else:
        scrivi(f"    {nome}: almeno 1 titolare cambia in {_quota(r['almeno_uno'], r['prove'])}; 3 o più in "
               f"{_quota(r['tre_o_piu'], r['prove'])}")


def rapporto(m: dict, scrivi=print) -> None:
    """Stampa C1-C4 in italiano semplice, con le soglie della proposta e l'esito di ognuno."""
    a, b = m.get("giocate") or {"casi": 0, "prove": []}, m.get("probabili")
    e = esiti(m)
    scrivi(f"Consiglio di formazione: misura in laboratorio (indicatori C1-C4 di #166; {m.get('simulazioni', SIMULAZIONI)} "
           "simulazioni come l'app, semi fissi: sugli stessi dati dà sempre gli stessi numeri)")
    scrivi("  S1 = fantamedia con il «gioca N%» del modello (la scelta semplice della verifica); S2 = fantamedia tra chi ha "
           "preso voto la giornata prima, senza modello (quello che farebbe chi non ha l'app).")
    if a["casi"]:
        g = a["giornate"]
        scrivi(f"  Parte A: giornate {g[0]}-{g[-1]} del {a['stagione']} già giocate, {a['casi']} casi squadra-giornata "
               f"(rose con almeno {verifica.MIN_GIOCATORI_ROSA} presenti), solo i dati di prima e senza probabili.")
    else:
        scrivi("  Parte A: nessuna giornata giocata con rose abbastanza complete: saltata.")
    if b:
        scrivi(f"  Parte B: giornata {b['giornata']} {'con le probabili' if b['con_probabili'] else 'SENZA probabili'}, "
               f"{b['squadre']} squadre, {b['titolari']} titolari: la formazione che mostra l'app.")
    elif m.get("saltata"):
        s = m["saltata"]
        motivo = s["motivo"][:1].lower() + s["motivo"][1:]
        scrivi(f"  Parte B: giornata {s['giornata']} saltata: {motivo}")
    else:
        scrivi("  Parte B: nessuna giornata con le probabili nell'archivio: saltata (si può indicare con --consiglio N).")

    scrivi("")
    scrivi(f"C1. Valore (soglia: consigliata meno S2 almeno 0): {_esito(e['C1'])}")
    if a["casi"]:
        p = a["punti"]
        scrivi(f"  Punti veri a giornata: consigliata {_n(p['consigliata'])} / S1 {_n(p['s1'])} / S2 {_n(p['s2'])} / "
               f"senno di poi {_n(p['perfetta'])}")
        es = a.get("errore_standard")
        dubbio = "" if es is None else f" (errore standard {_n(es)}" + (": non si distingue dal caso)" if abs(a["differenza_s2"]) < 2 * es else ")")
        scrivi(f"  Consigliata meno S2: {_n(a['differenza_s2'], segno=True)}{dubbio}")
        scrivi(f"  Casi con la consigliata almeno pari a S2: {a['casi_pari_s2']} su {a['casi']}; "
               f"giornate: {a['giornate_pari_s2']} su {len(a['giornate'])}")
        if a.get("quota_perfetta") is not None:
            scrivi(f"  Quota del senno di poi presa dalla consigliata: {_n(a['quota_perfetta'], 1)}%")
    scrivi("  Contro la formazione schierata: non misurabile qui (servono le formazioni schierate, si misura nel Diario).")

    scrivi("")
    scrivi(f"C2. Stabilità (soglia: nessun cambio di titolari che valga meno di {_punti_attesi(SOGLIA_CAMBIO)}, salvo un "
           f"titolare diventato improbabile): {_esito(e['C2'])}")
    scrivi(f"  Piccolo ritocco dei dati («gioca N%» di circa {round(SCARTO_P * 100)} punti, fantavoto atteso di circa "
           f"{_n(SCARTO_MU, 1)}; {RITOCCHI} prove per caso):")
    if a["casi"]:
        _stabilita(scrivi, "A", riassumi(a["prove"], "ritocco"), True)
    if b:
        _stabilita(scrivi, "B", riassumi(b["prove"], "ritocco"), True)
    scrivi("  Solo il seme della simulazione (stessi dati; l'app usa sempre lo stesso, quindi è un segno di scelta piatta):")
    if a["casi"]:
        _stabilita(scrivi, "A", riassumi(a["prove"], "seme"), False)
    if b:
        _stabilita(scrivi, "B", riassumi(b["prove"], "seme"), False)

    scrivi("")
    scrivi(f"C3. Chi gioca (soglia: 0 titolari sotto il {round(IMPROBABILE_SOTTO * 100)}% con un compagno di ruolo al "
           f"{round(COMPAGNO_DA * 100)}% o più): {_esito(e['C3'])}")
    if b:
        scrivi(f"  Titolari che giocano meno del {round(IMPROBABILE_SOTTO * 100)}% o sono fuori: {b['non_giocano']} su "
               f"{b['titolari']}, in {b['squadre_non_giocano']} squadre su {b['squadre']}")
        scrivi(f"  Di questi, con un compagno di ruolo che gioca il {round(COMPAGNO_DA * 100)}% o più e non è tra gli 11: "
               f"{b['con_compagno']} su {b['titolari']}")
        if b["costi"]:
            scrivi(f"  Metterci il compagno costa in punti attesi: mediana {_n(median(b['costi']), 3)}, "
                   f"al massimo {_n(max(b['costi']), 3)}")
    else:
        scrivi("  Serve la parte B.")
    if a["casi"]:
        sv = a["senza_voto"]
        scrivi(f"  Giornate giocate: titolari senza voto per formazione, consigliata {_n(sv['consigliata'])} / S2 "
               f"{_n(sv['s2'])}; senza voto e senza una riserva entrata {_n(a['scoperti'])}")

    scrivi("")
    scrivi(f"C4. Perché (soglia: tutte le scelte che sembrano storte spiegate; titolari senza un motivo proprio al massimo il "
           f"{round(MAX_SENZA_MOTIVO * 100)}%): {_esito(e['C4'])}")
    if b:
        scrivi(f"  Reparti con un escluso che ha più punti attesi del titolare più debole: {b['storte']} su {b['reparti']}; "
               f"spiegati da una riga sotto il campo (il perché della scelta): {b['spiegate']}; "
               f"senza la loro riga: {b['storte'] - b['spiegate']}")
        scrivi(f"  Titolari con «perché questo numero» vuoto: {b['vuoti']} su {b['titolari']}; senza un motivo proprio "
               f"(solo «gioca N%», partita o «altro»): {_quota(b['senza_motivo'], b['titolari'])}")
    else:
        scrivi("  Serve la parte B.")

    scrivi("")
    scrivi("Esito: " + ", ".join(f"{c} {_esito(v)}" for c, v in e.items()))
