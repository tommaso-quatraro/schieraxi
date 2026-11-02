"""Il "cervello": fantavoto atteso di ogni giocatore in una giornata, secondo le regole della lega.

Per ogni giocatore si stima:
- p_voto: probabilità che prenda voto (dalle probabili formazioni; nella verifica storica dalle presenze recenti);
- mu: fantavoto atteso SE prende voto = voto in pagella atteso + bonus/malus attesi con i valori della lega.

Ingredienti (tutti pesati di più se recenti, e "tirati" verso la media del ruolo quando i dati sono pochi):
- forza delle squadre da gol e xG fatti/subiti -> gol attesi della partita (attacco e difesa di ogni squadra stimati insieme, con memoria lunga e fattore campo);
- per il giocatore: voto medio, gol senza rigori e xG ogni 90', assist e xA, quota dei rigori della squadra,
  minuti per presenza, cartellini; per i portieri gol subiti attesi e probabilità di porta inviolata.
Usa solo dati PRECEDENTI alla giornata: così la stessa funzione serve per la verifica sulle giornate passate.
"""
from __future__ import annotations

import hashlib
import math
import pickle
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from . import coppe
from .punteggio import COLONNA_VOTO
from .regole import RUOLI, Regole

PASSO_STAGIONE = 50          # distanza "in giornate" tra l'inizio di una stagione e la successiva (38 + pausa estiva)
XG_RIGORE = 0.76             # xG che Understat assegna a un rigore
# Quanto della retta quotazione -> voto si usa per il voto di partenza (1 = tutta). Misura del 2/11/2026: con la retta intera
# il voto dei giocatori da 15 crediti in su era sopravvalutato (0,06-0,15) in tutte e due le stagioni; con metà l'errore
# scende in entrambe (verifica prima e dopo nella PR). Gol e assist usano ancora la retta intera.
PESO_QUOTAZIONE_VOTO = 0.5


@dataclass
class Parametri:
    # valori tarati il 26/10/2026 sul 2025-26 (giornate 5-38) con l'errore QUADRATICO, controllati sul 2026-27
    decadimento: float = 0.92         # peso di una partita di una giornata prima (rispetto all'ultima)
    peso_stagione_prec: float = 0.5   # le partite della stagione scorsa contano la metà
    k_voto: float = 20.0              # presenze "fittizie" alla media del ruolo (stabilizza chi ha giocato poco)
    k_90: float = 16.0                # 90 minuti "fittizi" al tasso del ruolo per gol e assist
    k_cartellini: float = 10.0
    peso_xg: float = 1.0              # gol attesi: quanto contano gli xG rispetto ai gol veri
    peso_xa: float = 0.3
    beta_voto: float = 0.1            # voto in più per ogni gol di differenza atteso a favore della squadra
    conversione_rigori: float = 0.78
    k_squadre: float = 3.0            # partite fittizie a forza media
    # forza delle squadre (tarata il 31/10/2026 sull'errore dei gol attesi): memoria più lunga di quella dei giocatori
    decadimento_squadre: float = 0.98
    peso_stagione_prec_squadre: float = 0.8
    peso_xg_squadre: float = 0.6      # gol attesi di squadra: quanto contano gli xG rispetto ai gol veri
    decadimento_presenze: float = 0.75
    giornate_presenze: int = 6


# ---------------------------------------------------------------- dati
@dataclass
class Dati:
    stagioni: list[str]
    voti: pd.DataFrame
    prestazioni: pd.DataFrame
    partite: pd.DataFrame
    calciatori: pd.DataFrame
    quotazioni: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["stagione", "calciatore_id", "qi"]))
    # modalità ombra: colonne in più di football-data.co.uk (tabella partite_extra). Il modello NON le legge;
    # le usa solo `verifica --fonti` per misurare se varrebbero qualcosa.
    extra: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __post_init__(self):
        # Se Understat non ha dato nessun xG, le colonne arrivano tutte vuote e pandas le legge come testo:
        # il calcolo si fermerebbe con un errore. Qui si fanno numeri (vuoti restano «mancante», come prima).
        for df, colonne in ((self.partite, ("xg_casa", "xg_trasferta")), (self.prestazioni, ("xg", "xa"))):
            for c in colonne:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)

    def t(self, stagione: str, giornata) -> int:
        return self.stagioni.index(stagione) * PASSO_STAGIONE + giornata

    def inizio(self, stagione: str, giornata: int) -> str:
        """Data e ora della prima partita della giornata: il modello usa solo ciò che è successo prima.
        (Filtrare per numero di giornata sbaglierebbe con i recuperi giocati settimane dopo.)"""
        date = self.partite.loc[(self.partite["stagione"] == stagione) & (self.partite["giornata"] == giornata), "data"]
        return str(date.min()) if len(date.dropna()) else "9999"


def carica(db: sqlite3.Connection) -> Dati:
    q = lambda sql: pd.read_sql_query(sql, db)  # noqa: E731
    partite = q("""
        SELECT p.id, p.stagione, p.giornata, p.data, p.casa, p.trasferta, p.gol_casa, p.gol_trasferta, p.giocata,
               u.xg_casa, u.xg_trasferta, p.understat_id
        FROM partite p
        LEFT JOIN partite_understat u ON u.id = p.understat_id""")
    stagioni = sorted(partite["stagione"].unique().tolist())
    voti = q("SELECT * FROM voti")
    voti = voti[voti["stagione"].isin(stagioni)].copy()
    prestazioni = q("""
        SELECT pr.*, p.stagione, p.giornata, p.data, ug.calciatore_id
        FROM prestazioni pr
        JOIN partite p ON p.understat_id = pr.understat_partita
        LEFT JOIN understat_giocatori ug ON ug.id = pr.understat_giocatore""")
    calciatori = q("SELECT id, nome, ruolo, squadra, squadra_slug, quotazione FROM calciatori")
    # data della partita di ogni voto (dalla giornata e dalla squadra)
    per_squadra = pd.concat([partite[["stagione", "giornata", c, "data"]].rename(columns={c: "squadra"})
                             for c in ("casa", "trasferta")]).drop_duplicates(["stagione", "giornata", "squadra"])
    voti = voti.merge(per_squadra, on=["stagione", "giornata", "squadra"], how="left")
    quotazioni = q("SELECT stagione, calciatore_id, qi FROM quotazioni")
    d = Dati(stagioni, voti, prestazioni, partite, calciatori, quotazioni, q("SELECT * FROM partite_extra"))
    idx = {s: i for i, s in enumerate(stagioni)}
    for df in (voti, prestazioni, partite):
        df["t"] = df["stagione"].map(idx) * PASSO_STAGIONE + df["giornata"]
    # rigori calciati dalla squadra in ogni partita (per la quota del rigorista)
    rig = prestazioni.groupby(["understat_partita", "squadra"])["rigori_calciati"].sum().rename("rigori_squadra")
    d.prestazioni = prestazioni.join(rig, on=["understat_partita", "squadra"])
    return d


def _pesi(t: pd.Series, stagione_t: pd.Series, t0: int, stagione0: str, par: Parametri) -> np.ndarray:
    return (par.decadimento ** (t0 - t).clip(lower=0)).to_numpy() * np.where(stagione_t == stagione0, 1.0, par.peso_stagione_prec)


# ---------------------------------------------------------------- squadre
@dataclass
class Forza:
    base: float                  # gol per squadra a partita (media del campionato)
    casa: float                  # fattore campo (moltiplica i gol di chi gioca in casa)
    attacco: dict[str, float]
    difesa: dict[str, float]     # > 1 = subisce più della media
    rigori_partita: float        # rigori calciati per squadra a partita

    def gol_attesi(self, casa: str, trasferta: str) -> tuple[float, float]:
        a, d = self.attacco, self.difesa
        lc = self.base * a.get(casa, 0.85) * d.get(trasferta, 1.15) * self.casa
        lt = self.base * a.get(trasferta, 0.85) * d.get(casa, 1.15) / self.casa
        return lc, lt


def prima_di(df: pd.DataFrame, data0: str) -> pd.Series:
    """Righe di partite giocate prima di data0 (le righe senza data non contano)."""
    return df["data"].notna() & (df["data"] < data0)


def forza_squadre(d: Dati, stagione: str, giornata: int, par: Parametri, iterazioni: int = 15) -> Forza:
    """Attacco e difesa di ogni squadra dalle partite già giocate (stile Dixon-Coles semplice).

    Gol attesi = gol medi x attacco di chi segna x difesa di chi subisce x fattore campo; le tre cose si stimano insieme
    (una squadra che ha affrontato avversari forti non viene penalizzata), le partite recenti pesano di più e chi ha
    poche partite viene tirato verso la media. Si usa un misto di xG e gol veri."""
    t0 = d.t(stagione, giornata)
    data0 = d.inizio(stagione, giornata)
    m = d.partite[prima_di(d.partite, data0) & (d.partite["giocata"] == 1)]
    if m.empty:
        return Forza(1.35, 1.1, {}, {}, 0.25)
    pp = replace(par, decadimento=par.decadimento_squadre, peso_stagione_prec=par.peso_stagione_prec_squadre)
    w = _pesi(m["t"], m["stagione"], t0, stagione, pp)
    fx = lambda xg, gol: np.where(xg.notna(), par.peso_xg_squadre * xg.fillna(0) + (1 - par.peso_xg_squadre) * gol, gol)  # noqa: E731
    gc = fx(m["xg_casa"], m["gol_casa"])
    gt = fx(m["xg_trasferta"], m["gol_trasferta"])
    squadre = sorted(set(m["casa"]) | set(m["trasferta"]))
    indice = {s: i for i, s in enumerate(squadre)}
    ic = m["casa"].map(indice).to_numpy()
    it = m["trasferta"].map(indice).to_numpy()
    n = len(squadre)
    base = float(np.sum(w * (gc + gt)) / (2 * np.sum(w)))
    k = par.k_squadre * base
    att, dif, casa = np.ones(n), np.ones(n), 1.1
    for _ in range(iterazioni):
        num = np.bincount(ic, w * gc, n) + np.bincount(it, w * gt, n)
        den = np.bincount(ic, w * base * dif[it] * casa, n) + np.bincount(it, w * base * dif[ic] / casa, n)
        att = (num + k) / (den + k)
        num = np.bincount(it, w * gc, n) + np.bincount(ic, w * gt, n)
        den = np.bincount(it, w * base * att[ic] * casa, n) + np.bincount(ic, w * base * att[it] / casa, n)
        dif = (num + k) / (den + k)
        casa = math.sqrt(float(np.sum(w * gc) / np.sum(w * base * att[ic] * dif[it]))
                         / float(np.sum(w * gt) / np.sum(w * base * att[it] * dif[ic])))
    p = d.prestazioni[prima_di(d.prestazioni, data0)]
    partite_squadra = p.groupby(["understat_partita", "squadra"]).ngroups
    rigori = float(p["rigori_calciati"].sum() / partite_squadra) if partite_squadra else 0.25
    return Forza(base, casa, {s: float(att[i]) for s, i in indice.items()},
                 {s: float(dif[i]) for s, i in indice.items()}, rigori)


# ---------------------------------------------------------------- giocatori
def previsioni(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri | None = None,
               probabili: pd.DataFrame | None = None, giocatori: pd.DataFrame | None = None,
               fattori_probabili: dict[str, float] | None = None,
               oracolo: dict | None = None) -> pd.DataFrame:
    """Una riga per giocatore: p_voto, mu (fantavoto atteso se gioca), mu_voto e i pezzi del calcolo.

    probabili: righe della tabella probabili per la giornata (live); se None, p_voto dalle presenze recenti.
    giocatori: chi prevedere (colonne id, nome, ruolo, squadra_slug); se None, il listone (live) o chi ha
               giocato prima della giornata (verifica storica).
    oracolo: SOLO per misurare quanto vale un dato in più (comando `oracolo`), mai nell'uso normale. Chiavi facoltative:
             "gol_squadra" {partita: (gol casa, gol trasferta) veri} e "rigorista" {giocatore: quota vera dei rigori
             della squadra} (chi non c'è vale 0).

    Delle regole contano solo la fonte del voto e i bonus/malus, e i bonus entrano solo nell'ultimo passo (mu). Tutto il resto
    (forza delle squadre, medie, presenze, gol e assist attesi...) si calcola una volta e vale per tutte le leghe con la stessa
    fonte del voto: vedi `_pezzi_condivisi`. Stesse operazioni nello stesso ordine: stessi numeri.
    """
    par = par or Parametri()
    pezzi, rigori_partita = _pezzi_condivisi(d, stagione, giornata, COLONNA_VOTO[regole.fonte_voto], par, probabili, giocatori,
                                             fattori_probabili, oracolo)
    return _con_bonus(pezzi, rigori_partita, regole.bonus, par)


def _con_bonus(pezzi: list, rigori_partita: float, b, par: Parametri) -> pd.DataFrame:
    """L'ultimo passo di `previsioni`: il fantavoto atteso `mu` con i bonus/malus della lega, e la tabella."""
    righe = []
    for prima, dopo, (r, voto, voto_tondo, voto_base, fattore, p_voto, e_gol, e_ass, e_rig, p_amm, p_esp, p_og, p_mvp,
                      gol_subiti, p_imbattuto) in pezzi:
        mu = (voto + b.gol[r] * e_gol + b.assist * e_ass
              + e_rig * (par.conversione_rigori * b.rigore_segnato + (1 - par.conversione_rigori) * b.rigore_sbagliato)
              + b.ammonizione * p_amm + b.espulsione * p_esp + b.autogol * p_og + b.mvp * p_mvp)
        if r == "P":
            mu += b.gol_subito_portiere * gol_subiti + b.portiere_imbattuto * p_imbattuto
            mu += b.rigore_parato * rigori_partita * 0.2
        righe.append(prima | {
            "mu": round(mu, 3), "mu_voto": voto_tondo,
            # pezzi per spiegare il numero (non entrano nel calcolo): voto prima della partita e quanto la partita pesa sui gol
            # attesi rispetto al solito della squadra (1 = partita normale)
            "voto_base": voto_base, "fattore": fattore,
            "atteso": round(p_voto * mu, 3)} | dopo)
    return pd.DataFrame(righe)


MAX_PEZZI = 16            # giornate (con fonte del voto e parametri) ricordate per ogni versione dei dati: circa 1,1 MB l'una (600 giocatori)


def _pezzi_condivisi(d: Dati, stagione: str, giornata: int, col_voto: str, par: Parametri, probabili, giocatori,
                     fattori_probabili, oracolo) -> tuple[list, float]:
    """`_pezzi`, ricordati dentro `d` (i dati di una versione dell'archivio, che non cambiano): con molte leghe con bonus
    diversi le previsioni di una giornata si calcolano una volta sola, non una per lega. Si ricordano solo i casi d'uso
    normali (niente oracolo, giocatori = tutti o il listone); la chiave contiene tutto ciò da cui dipende il risultato,
    anche il contenuto delle probabili."""
    if oracolo is not None or not (giocatori is None or giocatori is d.calciatori):
        return _pezzi(d, stagione, giornata, col_voto, par, probabili, giocatori, fattori_probabili, oracolo)
    try:
        firma_probabili = None if probabili is None else hashlib.sha1(pickle.dumps(probabili.to_dict("split"))).hexdigest()
        chiave = (stagione, giornata, col_voto, repr(par), firma_probabili, giocatori is None,
                  None if fattori_probabili is None else tuple(sorted(fattori_probabili.items())))
        hash(chiave)
    except Exception:  # noqa: BLE001 - qualcosa che non si sa firmare: si calcola e basta
        return _pezzi(d, stagione, giornata, col_voto, par, probabili, giocatori, fattori_probabili, oracolo)
    with _blocco_pezzi:
        memoria = d.__dict__.setdefault("_pezzi", OrderedDict())
        if chiave in memoria:
            memoria.move_to_end(chiave)
            return memoria[chiave]
    risultato = _pezzi(d, stagione, giornata, col_voto, par, probabili, giocatori, fattori_probabili, oracolo)
    with _blocco_pezzi:
        memoria[chiave] = risultato
        while len(memoria) > MAX_PEZZI:
            memoria.popitem(last=False)
    return risultato


_blocco_pezzi = threading.Lock()


def _pezzi(d: Dati, stagione: str, giornata: int, col_voto: str, par: Parametri, probabili, giocatori, fattori_probabili,
           oracolo) -> tuple[list, float]:
    """Tutto `previsioni` tranne i bonus/malus: per ogni giocatore (campi della riga prima di mu, campi dopo, numeri per mu),
    e i rigori a partita (servono a mu dei portieri). Chi lo riceve lo legge soltanto."""
    t0 = d.t(stagione, giornata)
    data0 = d.inizio(stagione, giornata)
    forza = forza_squadre(d, stagione, giornata, par)

    V = d.voti[prima_di(d.voti, data0)].copy()
    V["w"] = _pesi(V["t"], V["stagione"], t0, stagione, par)
    Vv = V[V[col_voto].notna()].copy()
    U = d.prestazioni[prima_di(d.prestazioni, data0) & d.prestazioni["calciatore_id"].notna()].copy()
    U["w"] = _pesi(U["t"], U["stagione"], t0, stagione, par)
    U["calciatore_id"] = U["calciatore_id"].astype(int)

    if giocatori is None:
        if probabili is not None:
            giocatori = d.calciatori.rename(columns={"squadra_slug": "squadra_slug"})
        else:   # verifica storica: squadra e ruolo dall'ultima presenza
            ultime = V.sort_values("t").groupby("calciatore_id").tail(1)
            giocatori = pd.DataFrame({"id": ultime["calciatore_id"], "nome": ultime["nome"],
                                      "ruolo": ultime["ruolo"], "squadra_slug": ultime["squadra"]})
    g = giocatori[["id", "nome", "ruolo", "squadra_slug"]].copy().set_index("id")

    # ---- medie del ruolo (per chi ha pochi dati) ----
    medie_ruolo = {}
    for r in RUOLI:
        vr = Vv[Vv["ruolo"] == r]
        ur = U[U["calciatore_id"].isin(vr["calciatore_id"].unique())]
        min90 = max(ur["minuti"].sum() / 90, 1)
        medie_ruolo[r] = {
            "voto": float(vr[col_voto].mean()) if len(vr) else 6.0,
            "gol90": float((ur["gol"].sum() - ur["rigori_segnati"].sum()) / min90),
            "xg90": float((ur["xg"].sum() - XG_RIGORE * ur["rigori_calciati"].sum()) / min90),
            "ass90": float(ur["assist"].sum() / min90), "xa90": float(ur["xa"].sum() / min90),
            "amm": float(vr["ammonizioni"].mean()) if len(vr) else 0.15,
            "esp": float(vr["espulsioni"].mean()) if len(vr) else 0.01,
            "autogol": float(vr["autogol"].mean()) if len(vr) else 0.003,
            "mvp": float(vr["mvp"].mean()) if len(vr) else 0.0,
            "minuti": float(ur.groupby(["understat_partita", "calciatore_id"])["minuti"].sum().mean()) if len(ur) else 70.0,
        }

    # ---- somme pesate per giocatore ----
    Vv["vw"] = Vv["w"] * Vv[col_voto]
    for c in ("gol", "assist", "ammonizioni", "espulsioni", "autogol", "mvp", "subentrato"):
        Vv[c + "_w"] = Vv["w"] * Vv[c]
    sv = Vv.groupby("calciatore_id")[["w", "vw", "gol_w", "assist_w", "ammonizioni_w", "espulsioni_w", "autogol_w",
                                       "mvp_w", "subentrato_w"]].sum()
    U["npxg"] = (U["xg"] - XG_RIGORE * U["rigori_calciati"]).clip(lower=0)
    for c in ("minuti", "npxg", "xa", "rigori_calciati", "rigori_squadra"):
        U[c + "_w"] = U["w"] * U[c]
    # minuti quando parte titolare (almeno 45') e quando entra dalla panchina: servono se le probabili lo danno titolare
    da_titolare = U["minuti"] >= 45
    U["uw_tit"], U["minuti_tit_w"] = U["w"] * da_titolare, U["minuti_w"] * da_titolare
    U["uw_sub"], U["minuti_sub_w"] = U["w"] * ~da_titolare, U["minuti_w"] * ~da_titolare
    su = U.groupby("calciatore_id")[["w", "minuti_w", "npxg_w", "xa_w", "rigori_calciati_w", "rigori_squadra_w",
                                      "uw_tit", "minuti_tit_w", "uw_sub", "minuti_sub_w"]].sum()
    su.columns = ["uw", "minuti_w", "npxg_w", "xa_w", "rc_w", "rs_w", "uw_tit", "minuti_tit_w", "uw_sub", "minuti_sub_w"]
    g = g.join(sv).join(su)
    g = g.fillna({c: 0.0 for c in list(sv.columns) + list(su.columns)})

    # ---- presenze recenti (p_voto senza probabili formazioni) ----
    # (e su un periodo lungo, per le giornate lontane: chi oggi è infortunato poi rientra; poi l'ultima partita da sola,
    # e le stesse finestre contando solo le partite iniziate da titolare: servono a `p_senza_probabili`)
    g["p_storico"], g["p_lungo"], g["p_ultima"], g["p_tit"], _, _ = _presenze_recenti_varie(
        d, V, col_voto, g, data0, [par, replace(par, giornate_presenze=20, decadimento_presenze=0.93),
                                   replace(par, giornate_presenze=1)], titolari=True)

    # ---- stima di partenza dalla quotazione iniziale ----
    # La quotazione iniziale (fissata prima del campionato, quindi senza dati dal futuro) riassume quanto gli
    # esperti si aspettano da un giocatore. Per ogni ruolo si misura, sui dati già giocati, come gol, assist e voto
    # crescono con la quotazione: un bomber nuovo in Serie A parte così da una stima da bomber, non da "attaccante medio".
    qi = d.quotazioni.loc[d.quotazioni["stagione"] == stagione].drop_duplicates("calciatore_id")
    g["qi"] = g.index.map(qi.set_index("calciatore_id")["qi"]).astype(float)
    con_u = g["uw"] > 0
    min90_g = np.where(con_u, g["minuti_w"] / 90, 0.0)
    g["tasso_gol"] = np.where(con_u, (par.peso_xg * g["npxg_w"] + (1 - par.peso_xg) * g["gol_w"]) / np.maximum(min90_g, 1e-9), np.nan)
    g["tasso_ass"] = np.where(con_u, (par.peso_xa * g["xa_w"] + (1 - par.peso_xa) * g["assist_w"]) / np.maximum(min90_g, 1e-9), np.nan)
    g["voto_medio"] = np.where(g["w"] > 0, g["vw"] / np.maximum(g["w"], 1e-9), np.nan)
    rette: dict[tuple[str, str], tuple[float, float]] = {}
    for r in RUOLI:
        for cosa, peso in (("tasso_gol", min90_g), ("tasso_ass", min90_g), ("voto_medio", g["w"].to_numpy())):
            sel = (g["ruolo"] == r).to_numpy() & g["qi"].notna().to_numpy() & g[cosa].notna().to_numpy() & (peso >= 3)
            if sel.sum() >= 15:
                pendenza, intercetta = np.polyfit(g.loc[sel, "qi"], g.loc[sel, cosa], 1, w=np.sqrt(peso[sel]))
                rette[(r, cosa)] = (float(intercetta), float(pendenza))

    def partenza(r: str, cosa: str, quotazione: float, media: float) -> float:
        if (r, cosa) not in rette or np.isnan(quotazione):
            return media
        intercetta, pendenza = rette[(r, cosa)]
        stima = intercetta + pendenza * quotazione
        if cosa == "voto_medio":        # solo una parte della retta: vedi PESO_QUOTAZIONE_VOTO
            return media + PESO_QUOTAZIONE_VOTO * (stima - media)
        return float(np.clip(stima, 0.25 * media, 4 * media)) if media > 0 else float(stima)

    righe = []
    prossime = d.partite[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == giornata)]
    avversari = {}
    for _, m in prossime.iterrows():
        lc, lt = forza.gol_attesi(m["casa"], m["trasferta"])
        if oracolo and int(m["id"]) in oracolo.get("gol_squadra", {}):
            lc, lt = oracolo["gol_squadra"][int(m["id"])]
        avversari[m["casa"]] = (m["trasferta"], True, lc, lt, int(m["id"]))
        avversari[m["trasferta"]] = (m["casa"], False, lt, lc, int(m["id"]))

    data_partita = {int(i): d_ for i, d_ in zip(prossime["id"], prossime["data"])}
    prob = probabili.set_index("calciatore_id") if probabili is not None and len(probabili) else None
    prob_righe = prob.to_dict("index") if prob is not None else {}        # un dizionario per riga: molto più veloce di prob.loc[cid]
    # squadre coperte dalle probabili: per le altre (pagina incompleta) si usano le presenze recenti
    coperte = set(probabili["squadra"]) if prob is not None and "squadra" in probabili else set()
    for cid, x in zip(g.index, g.to_dict("records")):        # (dizionari: più veloci delle righe pandas, stessi valori)
        r = x["ruolo"]
        if r not in RUOLI or x["squadra_slug"] not in avversari:
            continue                                   # ruolo sconosciuto o squadra che non gioca (rinvio)
        mr = medie_ruolo[r]
        avv, in_casa, l_sq, l_avv, partita = avversari[x["squadra_slug"]]
        # voto
        prior_voto = partenza(r, "voto_medio", x["qi"], mr["voto"])
        voto = (x["vw"] + par.k_voto * prior_voto) / (x["w"] + par.k_voto)
        voto_base = voto                  # il voto del giocatore prima dell'effetto della partita (serve a «perché questo numero»)
        voto += par.beta_voto * (l_sq - l_avv)
        # minuti per presenza (se non c'è altro: quelli medi delle sue presenze; con le probabili vedi più sotto)
        mt, ms = x["uw_tit"], x["uw_sub"]
        minuti_titolare = (x["minuti_tit_w"] + K_MINUTI * MINUTI_TITOLARE) / (mt + K_MINUTI)
        minuti_subentro = (x["minuti_sub_w"] + K_MINUTI * MINUTI_SUBENTRO) / (ms + K_MINUTI)
        if x["uw"] > 0:
            minuti = (x["minuti_w"] + 2 * mr["minuti"]) / (x["uw"] + 2)
        else:
            sub = x["subentrato_w"] / x["w"] if x["w"] > 0 else 0.3
            minuti = 82 * (1 - sub) + 25 * sub
        # probabilità di prendere voto
        stato, nota, perc, dubbio, diffidato = None, None, None, False, False
        if prob is not None and (x["squadra_slug"] in coperte or not coperte):
            if cid in prob_righe:
                pr = prob_righe[cid]
                stato, nota, perc = pr["stato"], pr["nota"], pr["percentuale"]
                dubbio = bool(pr["in_dubbio"])
                diffidato = bool(pr["diffidato"]) if "diffidato" in pr and pd.notna(pr["diffidato"]) else False
                p_voto = _p_da_probabili(stato, perc, bool(pr["in_dubbio"]))
                if fattori_probabili and pd.notna(perc):          # correzione imparata dalle giornate già giocate (stato_dati.fattori)
                    f = fattori_probabili.get(gruppo_probabili(stato, float(perc)) or "")
                    if f:
                        p_voto = min(0.99, p_voto * f)
            else:
                stato, p_voto = "non_citato", 0.02
        else:
            # senza probabili: chi gioca in coppa a ridosso della partita ha più probabilità di essere riposato
            p_voto = p_senza_probabili(x["p_storico"], x["p_lungo"], x["p_tit"], x["p_ultima"], r == "P")
            p_voto *= coppe.fattore_turnover(x["squadra_slug"], data_partita.get(partita))
        # se le probabili dicono che parte titolare, i minuti sono quelli da titolare (anche se finora è entrato dalla panchina)
        if stato == "titolare" and perc is not None and not np.isnan(perc) and p_voto > 0:
            parte = min(1.0, float(perc) / 100 / p_voto)
            minuti = max(minuti, parte * minuti_titolare + (1 - parte) * minuti_subentro)
        # gol (senza rigori) e assist ogni 90', tirati verso la media del ruolo
        min90 = x["minuti_w"] / 90 if x["uw"] > 0 else x["w"] * minuti / 90
        if x["uw"] > 0:
            gol_tasso = par.peso_xg * x["npxg_w"] + (1 - par.peso_xg) * x["gol_w"]
            ass_tasso = par.peso_xa * x["xa_w"] + (1 - par.peso_xa) * x["assist_w"]
        else:
            gol_tasso, ass_tasso = x["gol_w"], x["assist_w"]
        prior_g = partenza(r, "tasso_gol", x["qi"], par.peso_xg * mr["xg90"] + (1 - par.peso_xg) * mr["gol90"])
        prior_a = partenza(r, "tasso_ass", x["qi"], par.peso_xa * mr["xa90"] + (1 - par.peso_xa) * mr["ass90"])
        gol90 = (gol_tasso + par.k_90 * prior_g) / (min90 + par.k_90)
        ass90 = (ass_tasso + par.k_90 * prior_a) / (min90 + par.k_90)
        # la partita rispetto al solito: gol attesi oggi / gol medi della squadra
        media_sq = forza.base * forza.attacco.get(x["squadra_slug"], 0.85)
        fattore = float(np.clip(l_sq / media_sq, 0.5, 2.0)) if media_sq > 0 else 1.0
        quota90 = min(minuti, 90) / 90
        e_gol = gol90 * quota90 * fattore
        e_ass = ass90 * quota90 * fattore
        # rigori: quota del giocatore sui rigori della squadra
        quota_rig = x["rc_w"] / (x["rs_w"] + 0.5) if x["uw"] > 0 else 0.0
        if oracolo and "rigorista" in oracolo:
            quota_rig = float(oracolo["rigorista"].get(cid, 0.0))
        e_rig = quota_rig * forza.rigori_partita * fattore * min(1.0, minuti / 75)
        # cartellini e altro, per presenza
        n = x["w"]
        p_amm = (x["ammonizioni_w"] + par.k_cartellini * mr["amm"]) / (n + par.k_cartellini)
        p_esp = (x["espulsioni_w"] + par.k_cartellini * mr["esp"]) / (n + par.k_cartellini)
        p_og = (x["autogol_w"] + 20 * mr["autogol"]) / (n + 20)
        p_mvp = (x["mvp_w"] + par.k_cartellini * mr["mvp"]) / (n + par.k_cartellini)
        # mu (con i bonus/malus della lega) si calcola in `_con_bonus`, con questi numeri
        p_imbattuto = gol_subiti = 0.0
        if r == "P":
            gol_subiti = l_avv
            p_imbattuto = math.exp(-l_avv)
        prima = {
            "id": cid, "nome": x["nome"], "ruolo": r, "squadra": x["squadra_slug"], "avversario": avv,
            "in_casa": in_casa, "partita": partita, "gol_squadra": round(l_sq, 2), "gol_avversario": round(l_avv, 2),
            "p_voto": round(p_voto, 3), "p_lungo": round(float(x["p_lungo"]), 3),
            # quando gioca, quante volte parte titolare; con poche presenze conta la quotazione
            # (un giocatore da 30 crediti parte titolare quasi sempre)
            "quota_titolare": round(float((x["w"] - x["subentrato_w"] + 3 * _titolare_atteso(x["qi"])) / (x["w"] + 3)), 3)}
        per_mu = (r, voto, round(voto, 3), round(voto_base, 3), round(fattore, 3), p_voto, e_gol, e_ass, e_rig, p_amm, p_esp, p_og,
                  p_mvp, gol_subiti, p_imbattuto)
        dopo = {
            "e_gol": round(e_gol, 3), "e_assist": round(e_ass, 3), "e_rigori": round(e_rig, 3),
            # probabilità di almeno un gol (rigori compresi) / un assist / un cartellino, se gioca
            "p_gol": round(1 - math.exp(-(e_gol + par.conversione_rigori * e_rig)), 3),
            "p_assist": round(1 - math.exp(-e_ass), 3),
            "p_giallo": round(float(p_amm), 3),
            # il rosso è raro: serve più prudenza (un solo rosso non lo rende un "rosso facile")
            "p_rosso": round(float((x["espulsioni_w"] + 60 * mr["esp"]) / (n + 60)), 3),
            "p_imbattuto": round(p_imbattuto, 3), "gol_subiti": round(gol_subiti, 2),
            "minuti": round(minuti, 1), "presenze_pesate": round(n, 2),
            "stato": stato, "percentuale": perc, "nota": nota, "dubbio": dubbio, "diffidato": diffidato,
            "data_partita": data_partita.get(partita),
        }
        righe.append((prima, dopo, per_mu))
    return righe, forza.rigori_partita


# Probabilità di prendere voto dalle probabili formazioni di Fantacalcio.it.
# "percentuale" dei titolari = probabilità di partire titolare; chi non parte può comunque entrare.
# Per i panchinari la percentuale è più alta della loro quota nei ballottaggi: la trattiamo come
# probabilità di entrare in campo. Valori scelti perché la somma per squadra sia vicina ai ~14,5 giocatori
# con voto reali; da ritarare con le giornate raccolte (tabella probabili).
MINUTI_TITOLARE = 78           # minuti tipici di chi parte titolare (con poche presenze si parte da qui)
MINUTI_SUBENTRO = 22           # minuti tipici di chi entra dalla panchina
K_MINUTI = 2                   # peso (in presenze) di questi valori tipici
P_SUBENTRO_TITOLARE = 0.6      # un titolare previsto che non parte spesso entra comunque
P_SENZA_VOTO = 0.04            # chi entra per pochi minuti spesso resta senza voto
QUOTA_PANCHINA = 1.0

# Probabilità di prendere voto SENZA probabili formazioni (giornate lontane, squadre non coperte, verifica storica).
# Prima era la sola quota delle presenze recenti: chi aveva giocato le ultime 6 partite riceveva «98%» e poi giocava 86 volte
# su 100. Ora è una regressione logistica (stimata il 2/11/2026 SOLO sul 2025-26, giornate 5-38, 17.579 casi; controllata
# fuori campione sul 2026-27, giornate 2-8) su: presenze recenti (6 partite), presenze lunghe (20), partite iniziate da
# titolare (6), presenza nell'ultima partita (0,25 o 0,75: vedi `_presenze_recenti_varie`), più un termine per i portieri
# (il titolare gioca quasi sempre, la riserva quasi mai). Va da circa 6% a circa 93%. Da ristimare con
# `prove/calibra_p_voto.py` quando c'è una stagione intera in più; prima e dopo, `python -m fanta verifica`.
CALIBRAZIONE_SENZA_PROBABILI = {"costante": -2.681, "p_storico": 1.058, "p_lungo": 1.5, "p_titolare": 0.772,
                                "p_ultima": 2.122, "portiere": -0.909, "portiere_x_p_storico": 1.221}


def p_senza_probabili(p_storico: float, p_lungo: float, p_titolare: float, p_ultima: float, portiere: bool) -> float:
    """Probabilità di prendere voto dalle sole presenze (tutte quote tra 0 e 1, vedi `_presenze_recenti_varie`)."""
    c = CALIBRAZIONE_SENZA_PROBABILI
    z = (c["costante"] + c["p_storico"] * p_storico + c["p_lungo"] * p_lungo + c["p_titolare"] * p_titolare
         + c["p_ultima"] * p_ultima + (c["portiere"] + c["portiere_x_p_storico"] * p_storico if portiere else 0.0))
    return 1.0 / (1.0 + math.exp(-z))


# Gruppi delle probabili per la calibrazione: (nome, stato, percentuale minima, percentuale massima esclusa)
GRUPPI_PROBABILI = [
    ("Titolare 90-100%", "titolare", 90, 101), ("Titolare 70-89%", "titolare", 70, 90),
    ("Titolare 50-69%", "titolare", 50, 70), ("Titolare sotto 50%", "titolare", 0, 50),
    ("Panchina 50-100%", "panchina", 50, 101), ("Panchina 20-49%", "panchina", 20, 50), ("Panchina sotto 20%", "panchina", 0, 20),
]


def gruppo_probabili(stato: str | None, perc: float | None) -> str | None:
    if perc is None:
        return None
    for nome, s, da, a in GRUPPI_PROBABILI:
        if stato == s and da <= perc < a:
            return nome
    return None


def _titolare_atteso(qi: float) -> float:
    """Quota di partite da titolare attesa dalla quotazione iniziale (0,3 per i rincalzi, 0,95 per i big)."""
    return 0.5 if qi is None or np.isnan(qi) else float(np.clip(0.3 + qi / 40, 0.3, 0.95))


def _p_da_probabili(stato: str | None, perc: float | None, in_dubbio: bool) -> float:
    if perc is not None and math.isnan(perc):          # percentuale mancante (NULL nel database, NaN per pandas): vale il predefinito
        perc = None
    if stato in ("infortunato", "squalificato"):
        return 0.0
    if stato == "titolare":
        q = (perc if perc is not None else 80) / 100
        p = (q + (1 - q) * P_SUBENTRO_TITOLARE) * (1 - P_SENZA_VOTO)
    elif stato == "panchina":
        p = QUOTA_PANCHINA * (perc if perc is not None else 20) / 100
    else:
        p = 0.02
    return p * (0.75 if in_dubbio else 1.0)


def _presenze_recenti(d: Dati, V: pd.DataFrame, col_voto: str, g: pd.DataFrame, data0: str,
                      par: Parametri) -> pd.Series:
    """Quota pesata delle ultime partite giocate dalla SUA squadra in cui il giocatore ha preso voto.
    (Una partita rinviata non conta come assenza.)"""
    return _presenze_recenti_varie(d, V, col_voto, g, data0, [par])[0]


def _presenze_recenti_varie(d: Dati, V: pd.DataFrame, col_voto: str, g: pd.DataFrame, data0: str,
                            pars: list[Parametri], titolari: bool = False) -> list[pd.Series]:
    """Come `_presenze_recenti` per più parametri insieme (la parte comune si prepara una volta sola), con operazioni su tabelle
    intere invece di un ciclo per giocatore. Per ogni giocatore valgono le ultime partite della squadra (al massimo
    `giornate_presenze`) dal suo arrivo in quella squadra; la più recente pesa 1, le precedenti `decadimento_presenze` alla potenza
    della distanza (i pesi dipendono solo dalla posizione nella finestra della squadra, non dall'arrivo del giocatore)."""
    giocate = d.partite[prima_di(d.partite, data0) & (d.partite["giocata"] == 1)]
    lungo = pd.concat([
        pd.DataFrame({"slug": giocate[c].to_numpy(), "st": giocate["stagione"].to_numpy(), "gi": giocate["giornata"].to_numpy(),
                      "da": giocate["data"].to_numpy()}) for c in ("casa", "trasferta")], ignore_index=True)
    lungo = lungo.sort_values(["slug", "da", "st", "gi"], kind="stable", ignore_index=True)
    con_voto = V.loc[V[col_voto].notna(), ["calciatore_id", "stagione", "giornata"]].drop_duplicates()
    con_voto.columns = ["cid", "st", "gi"]
    con_voto["cv"] = True
    if titolari:        # partite iniziate da titolare (voto e non subentrato): servono alla calibrazione di p_voto
        da_tit = V.loc[V[col_voto].notna() & (V["subentrato"].fillna(0) == 0), ["calciatore_id", "stagione", "giornata"]]
        da_tit = da_tit.drop_duplicates()
        da_tit.columns = ["cid", "st", "gi"]
        da_tit["ct"] = True
        con_voto = con_voto.merge(da_tit, on=["cid", "st", "gi"], how="left")
    # prima partita del giocatore CON QUESTA SQUADRA: le partite della squadra prima del suo arrivo non sono assenze
    prima = V.dropna(subset=["data"]).sort_values("data", kind="stable").drop_duplicates(["calciatore_id", "squadra"])
    prima = prima[["calciatore_id", "squadra", "data"]]
    prima.columns = ["cid", "slug", "inizio"]
    gg = pd.DataFrame({"cid": g.index.to_numpy(), "slug": g["squadra_slug"].to_numpy()}).drop_duplicates("cid")
    gg = gg.merge(prima, on=["cid", "slug"], how="left")
    gg["inizio"] = gg["inizio"].fillna("9999")
    gg["inizio"] = gg["inizio"].astype(object)
    risultati, risultati_tit = [], []
    for par in pars:
        ult = lungo.groupby("slug", sort=False).tail(par.giornate_presenze).copy()
        pos = ult.groupby("slug", sort=False).cumcount()
        nt = ult.groupby("slug", sort=False)["da"].transform("size")
        ult["w"] = par.decadimento_presenze ** (nt - 1 - pos).to_numpy(dtype=float)
        m = gg.merge(ult, on="slug").merge(con_voto, on=["cid", "st", "gi"], how="left")
        valida = (m["da"].astype(object) >= m["inizio"]).to_numpy()
        peso = m["w"].to_numpy() * valida
        peso_voto = peso * m["cv"].notna().to_numpy()
        colonne = {"cid": m["cid"].to_numpy(), "num": peso_voto, "somma": peso, "n": valida.astype(int)}
        if titolari:
            colonne["num_tit"] = peso * m["ct"].notna().to_numpy()
        per = pd.DataFrame(colonne).groupby("cid").sum()
        piccolo = per["n"] < 3          # appena arrivato: poca informazione
        for num, uscita in (("num", risultati), ("num_tit", risultati_tit)):
            if num not in per:
                continue
            quota = per[num] / per["somma"].where(per["somma"] > 0)
            quota = quota.where(~piccolo, (quota * per["n"] + 0.5) / (per["n"] + 1))
            quota = quota.where(per["n"] > 0, 0.3)
            uscita.append(quota.reindex(gg["cid"]).fillna(0.3).astype(float).rename(None).rename_axis(None))
    return risultati + risultati_tit
