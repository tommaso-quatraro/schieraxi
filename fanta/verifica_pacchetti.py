"""Esperimenti di ABLAZIONE di `verifica --pacchetti` (spenti di default; il modello di produzione non cambia).

Domanda (docs/FONTI-DATI-CONFRONTO.md): quanto perdono il fantavoto atteso e la formazione consigliata con i dati che
avremmo comprando un solo fornitore invece delle fonti di oggi? Ogni scenario toglie o sostituisce dei dati e rifà il
backtest di `verifica.py` (la verità resta quella vera: fantavoti con i voti della redazione, come nella lega).

Scenari (vedi `SCENARI`):
- `completo`: la verifica normale (nel passato non ci sono le probabili: p_voto viene dalle presenze recenti);
- `senza_xg`: niente Understat xG/xA (giocatori e squadre); al loro posto gol e assist veri;
- `solo_fantacalcio`: niente Understat del tutto (indicatore I4 di #165): come `senza_xg`, e in più minuti stimati da
  entrato e uscito, rigori calciati = segnati + sbagliati, tutto dai voti di Fantacalcio.it: i numeri «nostri» di
  `nostri.py` (dati e parametri);
- `voto_fisso`: ogni voto dello storico vale la media del ruolo (nessun giudizio della redazione, nessun fatto);
- `voto_eventi` / `voto_stat`: il voto in pagella dello storico sostituito da un voto STIMATO con una regressione per ruolo
  (gol, assist, rigori, cartellini, autogol, minuti, entrato/uscito, risultato, gol subiti; `voto_stat` anche tiri e
  passaggi chiave, al posto del «rating» del fornitore che non abbiamo), tarata su `STAGIONE_TARATURA`;
- `pacchetto_a`: solo calendario e risultati (+ ruolo e quotazione iniziale dalle rose dell'utente);
- `pacchetto_b` (senza xG e voto stimato), `pacchetto_b_xg` (voto stimato, xG tenuti);
- `sportmonks_starter`: pacchetto B + squalifiche (dai cartellini) + indisponibili (simulati) + formazioni ufficiali per
  le partite che iniziano entro 50 minuti dalla prima (escono circa 1 ora prima; scadenza 10 minuti prima della prima);
- `attuale_probabili_90` / `_80`: stima del modello di OGGI dal vivo = completo + probabili SIMULATE che indovinano il
  90% (80%) dei titolari, con indisponibili e squalificati segnati (le probabili vere del passato non le abbiamo);
- `pacchetto_c`: B+xG + indisponibili + formazioni previste simulate all'87% (quanto dichiara il fornitore);
- `oracolo_presenze`: limite superiore (si sa già chi prende voto).
Per ogni scenario che dà i gol attesi si misura anche se sono tarati, per fasce (`gol_per_fasce`, `scarto_gol`).
Le parti «simulate» usano il futuro di proposito (chi non gioca per 3 giornate di fila = indisponibile noto): sono una
stima favorevole, scritta nel documento dei risultati (docs/FONTI-DATI-MISURE.md).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from . import nostri, verifica
from .modello import Dati, Parametri, _p_da_probabili, forza_squadre, previsioni, prima_di
from .punteggio import COLONNA_VOTO
from .regole import RUOLI, Regole

STAGIONE_TARATURA = "2025-26"      # stagione su cui si tarano le regressioni (voto stimato, pacchetto A)
RIDGE = 1.0                         # piccola penalità: coefficienti stabili anche con pochi portieri
SEME = 11
SCADENZA_MINUTI = 10               # la formazione si chiude 10 minuti prima della prima partita (lega dell'utente)
ANTICIPO_UFFICIALI = 60            # le formazioni ufficiali escono circa 60 minuti prima del calcio d'inizio
GIORNATE_INDISPONIBILE = 3         # assente in questa giornata e nelle 2 dopo = indisponibile noto (infortunio, squalifica)
SOGLIE_GIALLI = (5, 10, 14, 17)    # ammonizioni che fanno scattare una giornata di squalifica (poi una ogni ammonizione)
P_TITOLARE_PROB = _p_da_probabili("titolare", 85, False)   # titolare nelle probabili, 85%
P_PANCHINA_MAX = 0.35              # chi le probabili danno in panchina: al massimo così (come la percentuale delle panchine)
P_TITOLARE_UFFICIALE = 0.97
P_PANCHINA_UFFICIALE = 0.30


def stagione_taratura(d: Dati) -> str:
    """La stagione su cui tarare: `STAGIONE_TARATURA` se c'è nei dati, se no la più vecchia."""
    return STAGIONE_TARATURA if STAGIONE_TARATURA in d.stagioni else d.stagioni[0]


# ---------------------------------------------------------------- dati senza xG
def senza_xg(d: Dati) -> Dati:
    """Copia dei dati senza xG/xA (i tassi di gol e assist del modello tornano ai gol e assist veri)."""
    pr = d.prestazioni.copy()
    pa = d.partite.copy()
    pr["xg"] = np.nan
    pr["xa"] = np.nan
    pa["xg_casa"] = np.nan
    pa["xg_trasferta"] = np.nan
    return replace(d, prestazioni=pr, partite=pa)


def par_senza_xg(par: Parametri) -> Parametri:
    return replace(par, peso_xg=0.0, peso_xa=0.0)


# ---------------------------------------------------------------- solo Fantacalcio.it (niente Understat)
# I dati, i minuti stimati e le fasce stanno in `nostri` (gol e assist attesi nostri); qui restano gli stessi nomi.
MINUTI_STIMATI = nostri.MINUTI_STIMATI
minuti_stimati = nostri.minuti_stimati
solo_fantacalcio = nostri.dati


# ---------------------------------------------------------------- gol attesi tarati per fasce (indicatore I4)
FASCE_GOL = nostri.FASCE_GOL
FASCE_GOL_NOMI = nostri.FASCE_GOL_NOMI
MIN_CASI_FASCIA = nostri.MIN_CASI_FASCIA
COLONNE_FASCE = ["stagione", "fascia", "casi", "attesi", "veri", "scarto"]


def gol_per_fasce(d: Dati, regole: Regole, previsti: pd.DataFrame) -> pd.DataFrame:
    """Gol attesi contro gol veri, per fascia di gol attesi. `previsti`: stagione, giornata, id, gol_attesi (se gioca, rigori
    compresi). Contano solo le presenze con voto; gol veri = su azione + rigori segnati. Una riga per stagione («tutte» e
    ciascuna) e fascia con casi, medie e scarto = veri − attesi (gol a partita)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    v = d.voti[d.voti[col].notna()]
    veri = pd.DataFrame({"stagione": v["stagione"], "giornata": v["giornata"], "id": v["calciatore_id"],
                         "veri": pd.to_numeric(v["gol"], errors="coerce").fillna(0)
                         + pd.to_numeric(v["rig_segnati"], errors="coerce").fillna(0)}).drop_duplicates(["stagione", "giornata", "id"])
    m = previsti.merge(veri, on=["stagione", "giornata", "id"], how="inner")
    m["fascia"] = pd.cut(m["gol_attesi"], FASCE_GOL, right=False, labels=FASCE_GOL_NOMI)
    righe = []
    for s in ["tutte"] + sorted(m["stagione"].unique().tolist()):
        sel = m if s == "tutte" else m[m["stagione"] == s]
        for fascia, g in sel.groupby("fascia", observed=True):
            attesi, gol = float(g["gol_attesi"].mean()), float(g["veri"].mean())
            righe.append({"stagione": s, "fascia": str(fascia), "casi": len(g), "attesi": attesi, "veri": gol,
                          "scarto": gol - attesi})
    return pd.DataFrame(righe, columns=COLONNE_FASCE)


def scarto_gol(fasce: pd.DataFrame, stagione: str, minimo: int = MIN_CASI_FASCIA) -> float:
    """Lo scarto più grande (in valore assoluto) tra gol veri e attesi nelle fasce con almeno `minimo` casi (soglia di I4:
    0,03 gol a partita); senza fasce abbastanza piene: nan."""
    sel = fasce[(fasce["stagione"] == stagione) & (fasce["casi"] >= minimo)]
    return float(sel["scarto"].abs().max()) if len(sel) else float("nan")


def _con_registro(prevedi, raccolte: list):
    """`prevedi` per la verifica che in più mette da parte, giornata per giornata, i gol attesi di ogni giocatore (con i rigori,
    come `p_gol` del modello). Le previsioni restano quelle: i numeri della verifica non cambiano."""
    def f(dm: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri) -> pd.DataFrame:
        prev = prevedi(dm, stagione, giornata, regole, par)
        if {"id", "e_gol", "e_rigori"} <= set(prev.columns):
            raccolte.append(pd.DataFrame({"stagione": stagione, "giornata": giornata, "id": prev["id"].astype(int),
                                          "gol_attesi": nostri.gol_attesi(prev, par)}))
        return prev
    return f


def _previsioni(dm: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri) -> pd.DataFrame:
    return previsioni(dm, stagione, giornata, regole, par)      # come fa `verifica` quando non riceve `prevedi`


# ---------------------------------------------------------------- voto stimato
EVENTI = ["gol", "rig_segnati", "rig_sbagliati", "assist", "ammonizioni", "espulsioni", "autogol", "subentrato",
          "sostituito", "min90", "diff", "vittoria", "sconfitta", "subiti", "imbattuto", "gol_subiti", "rig_parati"]
STATISTICHE = ["tiri", "passaggi_chiave", "ha_stat"]
XG = ["xg", "xa", "xg_chain", "xg_buildup"]


def tabella_fatti(d: Dati) -> pd.DataFrame:
    """Le righe dei voti con accanto i fatti oggettivi della partita (stesso indice di `d.voti`)."""
    v = d.voti.copy()
    p = d.partite[d.partite["giocata"] == 1]
    sq = pd.concat([
        pd.DataFrame({"stagione": p["stagione"], "giornata": p["giornata"], "squadra": p["casa"],
                      "gf": p["gol_casa"], "gs": p["gol_trasferta"]}),
        pd.DataFrame({"stagione": p["stagione"], "giornata": p["giornata"], "squadra": p["trasferta"],
                      "gf": p["gol_trasferta"], "gs": p["gol_casa"]})]).drop_duplicates(["stagione", "giornata", "squadra"])
    u = d.prestazioni[d.prestazioni["calciatore_id"].notna()]
    u = u.groupby(["stagione", "giornata", "calciatore_id"])[["minuti", "tiri", "passaggi_chiave", "xg", "xa", "xg_chain",
                                                              "xg_buildup"]].sum(min_count=1).reset_index()
    u["calciatore_id"] = u["calciatore_id"].astype(int)
    idx = v.index
    v = v.merge(sq, on=["stagione", "giornata", "squadra"], how="left").merge(
        u, on=["stagione", "giornata", "calciatore_id"], how="left")
    v.index = idx
    v["ha_stat"] = v["minuti"].notna().astype(float)
    v["min90"] = (v["minuti"].fillna(pd.Series(np.where(v["subentrato"] == 1, 25, 85), index=v.index)) / 90).clip(upper=1.0)
    diff = (v["gf"] - v["gs"]).fillna(0)
    v["diff"] = diff.clip(-3, 3)
    v["vittoria"] = (diff > 0).astype(float)
    v["sconfitta"] = (diff < 0).astype(float)
    v["subiti"] = v["gs"].fillna(1).clip(upper=5)
    v["imbattuto"] = (v["gs"] == 0).astype(float)
    for c in EVENTI + STATISTICHE + XG:
        v[c] = pd.to_numeric(v[c], errors="coerce").fillna(0.0).astype(float)
    return v


@dataclass
class Taratura:
    colonne: list[str]
    coeff: dict[str, np.ndarray]        # per ruolo: intercetta + un coefficiente per colonna
    errore: dict[str, float]            # radice dell'errore quadratico del voto stimato per stagione


def tara_voto(f: pd.DataFrame, col: str, colonne: list[str], stagione: str = STAGIONE_TARATURA) -> Taratura:
    coeff = {}
    for r in RUOLI:
        t = f[(f["stagione"] == stagione) & (f["ruolo"] == r) & f[col].notna()]
        X = np.column_stack([np.ones(len(t))] + [t[c].to_numpy() for c in colonne])
        y = t[col].to_numpy(dtype=float)
        pen = RIDGE * np.eye(X.shape[1])
        pen[0, 0] = 0.0
        coeff[r] = np.linalg.solve(X.T @ X + pen, X.T @ y) if len(t) else np.r_[6.0, np.zeros(len(colonne))]
    tar = Taratura(colonne, coeff, {})
    stimato = stima_voto(f, tar)
    for s in sorted(f["stagione"].unique()):
        sel = (f["stagione"] == s) & f[col].notna()
        tar.errore[s] = float(np.sqrt(np.mean((stimato[sel] - f.loc[sel, col]) ** 2))) if sel.any() else float("nan")
    return tar


def stima_voto(f: pd.DataFrame, tar: Taratura) -> pd.Series:
    out = pd.Series(6.0, index=f.index)
    for r in RUOLI:
        sel = f["ruolo"] == r
        if sel.any():
            X = np.column_stack([np.ones(int(sel.sum()))] + [f.loc[sel, c].to_numpy() for c in tar.colonne])
            out[sel] = X @ tar.coeff[r]
    return out.clip(3.5, 9.5)


def con_voto_stimato(d: Dati, regole: Regole, colonne: list[str]) -> tuple[Dati, Taratura]:
    """Copia dei dati in cui il voto della redazione (dove c'è) è sostituito dal voto stimato; chi era senza voto resta così."""
    col = COLONNA_VOTO[regole.fonte_voto]
    f = tabella_fatti(d)
    tar = tara_voto(f, col, colonne, stagione_taratura(d))
    v = d.voti.copy()
    ha = v[col].notna()
    v.loc[ha, col] = stima_voto(f, tar)[ha]
    return replace(d, voti=v), tar


# ---------------------------------------------------------------- pacchetto A (solo calendario e risultati)
def tara_pacchetto_a(d: Dati, regole: Regole, stagione: str | None = None) -> dict:
    """Per ruolo, rette in funzione della quotazione iniziale: voto medio, gol, assist, ammonizioni a presenza e quota di
    presenze. È l'unica informazione sul giocatore del pacchetto A (le rose dell'utente)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    stagione = stagione or stagione_taratura(d)
    v = d.voti[(d.voti["stagione"] == stagione) & d.voti[col].notna()]
    giornate = max(int(d.partite.loc[(d.partite["stagione"] == stagione) & (d.partite["giocata"] == 1), "giornata"].nunique()), 1)
    agg = v.groupby("calciatore_id").agg(ruolo=("ruolo", "last"), pres=(col, "size"), voto=(col, "mean"),
                                         gol=("gol", "mean"), assist=("assist", "mean"), amm=("ammonizioni", "mean"))
    agg["quota"] = (agg["pres"] / giornate).clip(upper=1.0)
    qi = d.quotazioni[d.quotazioni["stagione"] == stagione].drop_duplicates("calciatore_id").set_index("calciatore_id")["qi"]
    agg["qi"] = agg.index.map(qi).astype(float)
    agg = agg.dropna(subset=["qi"])
    rette = {}
    for r in RUOLI:
        a = agg[agg["ruolo"] == r]
        for cosa in ("voto", "gol", "assist", "amm", "quota"):
            w = np.sqrt(a["pres"]) if cosa != "quota" else np.ones(len(a))
            rette[(r, cosa)] = tuple(np.polyfit(a["qi"], a[cosa], 1, w=w)) if len(a) >= 5 else (0.0, float(a[cosa].mean() if len(a) else 0))
    return rette


def prevedi_pacchetto_a(rette: dict):
    """`prevedi` per la verifica: fantavoto atteso solo da ruolo, quotazione e forza delle squadre (dai soli gol)."""
    def prevedi(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri) -> pd.DataFrame:
        b = regole.bonus
        data0 = d.inizio(stagione, giornata)
        dd = senza_xg(d)
        forza = forza_squadre(dd, stagione, giornata, par)
        # chi prevedere: stessa popolazione della verifica normale (solo per confrontare; nessun suo dato entra nel calcolo)
        V = d.voti[prima_di(d.voti, data0)]
        ultime = V.sort_values("t").groupby("calciatore_id").tail(1)
        qi = d.quotazioni[d.quotazioni["stagione"] == stagione].drop_duplicates("calciatore_id").set_index("calciatore_id")["qi"]
        prossime = d.partite[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == giornata)]
        avv = {}
        for _, m in prossime.iterrows():
            lc, lt = forza.gol_attesi(m["casa"], m["trasferta"])
            avv[m["casa"]] = (lc, lt, int(m["id"]))
            avv[m["trasferta"]] = (lt, lc, int(m["id"]))
        righe = []
        for cid, nome, r, sq in zip(ultime["calciatore_id"], ultime["nome"], ultime["ruolo"], ultime["squadra"]):
            if r not in RUOLI or sq not in avv:
                continue
            l_sq, l_avv, partita = avv[sq]
            q = float(qi.get(cid, np.nan))
            q = 5.0 if np.isnan(q) else q
            val = {k: float(np.polyval(rette[(r, k)], q)) for k in ("voto", "gol", "assist", "amm", "quota")}
            media_sq = forza.base * forza.attacco.get(sq, 0.85)
            fattore = float(np.clip(l_sq / media_sq, 0.5, 2.0)) if media_sq > 0 else 1.0
            voto = val["voto"] + par.beta_voto * (l_sq - l_avv)
            mu = (voto + b.gol[r] * max(val["gol"], 0) * fattore + b.assist * max(val["assist"], 0) * fattore
                  + b.ammonizione * max(val["amm"], 0))
            if r == "P":
                mu += b.gol_subito_portiere * l_avv + b.portiere_imbattuto * float(np.exp(-l_avv))
            righe.append({"id": int(cid), "nome": nome, "ruolo": r, "squadra": sq, "partita": partita,
                          "p_voto": float(np.clip(val["quota"], 0.05, 0.95)), "mu": mu, "mu_voto": voto})
        return pd.DataFrame(righe)
    return prevedi


# ---------------------------------------------------------------- presenze: squalifiche, indisponibili, ufficiali, probabili
def _verita(d: Dati, stagione: str, giornata: int, col: str) -> tuple[set, set, set]:
    """(chi ha preso voto, chi è partito titolare, chi c'era nel tabellino) nella giornata."""
    v = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] == giornata)]
    preso = v[v[col].notna()]
    return set(preso["calciatore_id"]), set(preso.loc[preso["subentrato"] == 0, "calciatore_id"]), set(v["calciatore_id"])


def squalificati(d: Dati, stagione: str, giornata: int) -> set:
    """Squalificati noti prima della giornata, dai cartellini: rosso nella giornata prima, o ammonizione che fa scattare la
    squalifica (5ª, 10ª, 14ª, 17ª, poi ogni ammonizione)."""
    v = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] < giornata)]
    out = set(v.loc[(v["giornata"] == giornata - 1) & (v["espulsioni"] > 0), "calciatore_id"])
    amm = v[v["ammonizioni"] > 0].sort_values("giornata")
    amm = amm.assign(n=amm.groupby("calciatore_id").cumcount() + 1)
    ultime = amm[amm["giornata"] == giornata - 1]
    out |= set(ultime.loc[ultime["n"].isin(SOGLIE_GIALLI) | (ultime["n"] >= 19), "calciatore_id"])
    return out


def indisponibili(d: Dati, stagione: str, giornata: int) -> set:
    """Simulazione dell'elenco infortunati del fornitore: chi non è nel tabellino né oggi né nelle 2 giornate dopo (solo
    giornate giocate). Usa il futuro di proposito: è una stima favorevole di cosa si saprebbe prima."""
    giocate = set(d.partite.loc[(d.partite["stagione"] == stagione) & (d.partite["giocata"] == 1), "giornata"])
    finestra = [g for g in range(giornata, giornata + GIORNATE_INDISPONIBILE) if g in giocate]
    if len(finestra) < 2:
        return set()
    v = d.voti[(d.voti["stagione"] == stagione) & d.voti["giornata"].isin(finestra)]
    return {"__tutti_tranne__", *map(int, v["calciatore_id"].unique())}


def _assente(cid: int, insieme: set) -> bool:
    """Per `indisponibili` l'insieme contiene chi C'ERA (marcato con «__tutti_tranne__»)."""
    if "__tutti_tranne__" in insieme:
        return cid not in insieme
    return cid in insieme


def partite_con_ufficiali(d: Dati, stagione: str, giornata: int) -> set:
    """Partite le cui formazioni ufficiali escono prima della scadenza della lega."""
    p = d.partite[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == giornata) & d.partite["data"].notna()]
    if p.empty:
        return set()
    t = pd.to_datetime(p["data"])
    limite = t.min() - pd.Timedelta(minutes=SCADENZA_MINUTI) + pd.Timedelta(minutes=ANTICIPO_UFFICIALI)
    return set(p.loc[(t <= limite).to_numpy(), "id"].astype(int))


def ritocca(regole: Regole, sidelined: bool = False, ufficiali: bool = False, probabili: float | None = None,
            seme: int = SEME):
    """Funzione `ritocca` per `verifica`: nuove probabilità di giocare con i dati di presenza di uno scenario."""
    col = COLONNA_VOTO[regole.fonte_voto]

    def f(prev: pd.DataFrame, d: Dati, stagione: str, giornata: int) -> np.ndarray:
        p = prev["p_voto"].to_numpy(dtype=float).copy()
        ids = [int(i) for i in prev.index]
        squadra = prev["squadra"].to_numpy()
        _, titolari, _ = _verita(d, stagione, giornata, col)
        fuori = np.zeros(len(ids), dtype=bool)
        if sidelined or probabili is not None:
            sq, ind = squalificati(d, stagione, giornata), indisponibili(d, stagione, giornata)
            fuori = np.array([(i in sq) or (bool(ind) and _assente(i, ind)) for i in ids])
            p[fuori] = 0.0
        if probabili is not None:
            rng = np.random.default_rng(seme * 1000 + giornata + int(stagione[:4]))
            for s in pd.unique(squadra):
                sel = np.flatnonzero(squadra == s)
                vero = np.array([ids[k] in titolari for k in sel])
                indovinato = vero & (rng.random(len(sel)) < probabili)
                mancano = int(vero.sum() - indovinato.sum())
                candidati = sel[~vero & ~fuori[sel]]
                scelti = np.array([], dtype=int)
                if mancano and len(candidati):
                    w = p[candidati] + 1e-3
                    scelti = rng.choice(candidati, min(mancano, len(candidati)), replace=False, p=w / w.sum())
                tit = set(sel[indovinato]) | set(scelti)
                for k in sel:
                    if fuori[k]:
                        continue
                    p[k] = P_TITOLARE_PROB if k in tit else min(p[k], P_PANCHINA_MAX)
        if ufficiali:
            con = partite_con_ufficiali(d, stagione, giornata)
            for k, part in enumerate(prev["partita"].to_numpy()):
                if int(part) in con:
                    p[k] = P_TITOLARE_UFFICIALE if ids[k] in titolari else (0.0 if fuori[k] else min(p[k], P_PANCHINA_UFFICIALE))
        return p
    return f


# ---------------------------------------------------------------- scenari
SCENARI = ("completo", "senza_xg", "solo_fantacalcio", "voto_fisso", "voto_eventi", "voto_stat", "pacchetto_a", "pacchetto_b",
           "pacchetto_b_xg", "solo_indisponibili", "sportmonks_starter", "attuale_probabili_90", "attuale_probabili_80",
           "pacchetto_c", "oracolo_presenze")


def prepara(nome: str, d: Dati, regole: Regole, par: Parametri) -> tuple[dict, dict]:
    """(argomenti per `verifica.verifica`, note) di uno scenario."""
    if nome not in SCENARI:
        raise ValueError(f"scenario sconosciuto: {nome} (validi: {', '.join(SCENARI)})")
    kw: dict = {"par": par}
    note: dict = {}
    ev, st = list(EVENTI), list(EVENTI) + STATISTICHE

    def voto(dati, colonne):
        dv, tar = con_voto_stimato(dati, regole, colonne)
        note["errore_voto_stimato"] = tar.errore
        return dv
    if nome == "senza_xg":
        kw |= {"dati_modello": senza_xg(d), "par": par_senza_xg(par)}
    elif nome == "solo_fantacalcio":
        kw |= {"dati_modello": nostri.dati(d), "par": nostri.parametri(par)}
    elif nome == "voto_fisso":
        kw["dati_modello"] = voto(d, [])
    elif nome == "voto_eventi":
        kw["dati_modello"] = voto(d, ev)
    elif nome == "voto_stat":
        kw["dati_modello"] = voto(d, st)
    elif nome == "pacchetto_a":
        kw["prevedi"] = prevedi_pacchetto_a(tara_pacchetto_a(d, regole))
    elif nome in ("pacchetto_b", "sportmonks_starter"):
        kw |= {"dati_modello": voto(senza_xg(d), st), "par": par_senza_xg(par)}
        if nome == "sportmonks_starter":
            kw["ritocca"] = ritocca(regole, sidelined=True, ufficiali=True)
    elif nome in ("pacchetto_b_xg", "pacchetto_c"):
        kw["dati_modello"] = voto(d, st + XG)
        if nome == "pacchetto_c":
            kw["ritocca"] = ritocca(regole, probabili=0.87, ufficiali=True)
    elif nome == "solo_indisponibili":
        kw["ritocca"] = ritocca(regole, sidelined=True)
    elif nome.startswith("attuale_probabili_"):
        kw["ritocca"] = ritocca(regole, probabili=int(nome.rsplit("_", 1)[1]) / 100)
    elif nome == "oracolo_presenze":
        kw["oracolo"] = frozenset(["presenze"])
    return kw, note


def rose_sintetiche(d: Dati, regole: Regole, per_stagione: int, seme: int = SEME, min_voti: int = 8) -> list[list[int]]:
    """Rose fisse estratte a sorte (seme fisso) per ogni stagione, con la composizione della lega, tra chi ha almeno
    `min_voti` voti in quella stagione: più casi per misurare i punti (le rose vere della lega sono poche)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    rng = np.random.default_rng(seme)
    out = []
    for st in d.stagioni:
        v = d.voti[(d.voti["stagione"] == st) & d.voti[col].notna()]
        n = v.groupby("calciatore_id").agg(ruolo=("ruolo", "last"), voti=(col, "size"))
        pool = {r: n.index[(n["ruolo"] == r) & (n["voti"] >= min_voti)].to_numpy() for r in RUOLI}
        if any(len(pool[r]) < k for r, k in regole.rosa.items()):
            continue
        for _ in range(per_stagione):
            out.append([int(i) for r, k in regole.rosa.items() for i in rng.choice(pool[r], k, replace=False)])
    return out


def _riassunto(t: pd.DataFrame) -> dict:
    out = {"giornate": len(t), "rmse": float(t["quadratico_modello"].mean() ** 0.5), "mae": float(t["errore_modello"].mean()),
           "brier": float(t["brier"].mean())}
    if "punti_modello" in t:
        out |= {"punti": float(t["punti_modello"].mean()), "perfetta": float(t["punti_perfetta"].mean())}
    return out


def esegui(nome: str, d: Dati, regole: Regole, par: Parametri, giornate, rose=None,
           simulazioni: int = 300) -> tuple[pd.DataFrame, dict]:
    """(tabella di `verifica.verifica` per giornata, note) di uno scenario. Nelle note, se il modello dà i gol attesi,
    `gol_per_fasce` (vedi `gol_per_fasce`)."""
    kw, note = prepara(nome, d, regole, par)
    par_s = kw.pop("par")
    raccolte: list = []
    if "oracolo" not in kw:              # con un oracolo `verifica` chiama `previsioni` da sola, con la verità
        kw["prevedi"] = _con_registro(kw.get("prevedi") or _previsioni, raccolte)
    t = verifica.verifica(d, regole, par_s, giornate, rose, simulazioni, scrivi=None, **kw)
    if raccolte:
        note["gol_per_fasce"] = gol_per_fasce(d, regole, pd.concat(raccolte, ignore_index=True))
    return t, note


def tabella(tabelle: dict[str, pd.DataFrame], fasce: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Una riga per scenario e stagione: rmse, mae, Brier, punti della consigliata, massimo col senno di poi, scarto dal
    massimo, differenze rispetto a `completo` (che deve esserci; rmse anche in percentuale) e `scarto_gol` (vedi `scarto_gol`)
    dalle `fasce` di ogni scenario."""
    righe = []
    base = tabelle["completo"]
    for nome, t in tabelle.items():
        for s in ["tutte"] + sorted(t["stagione"].unique().tolist()):
            sel = t if s == "tutte" else t[t["stagione"] == s]
            b = base if s == "tutte" else base[base["stagione"] == s]
            r, rb = _riassunto(sel), _riassunto(b)
            riga = {"scenario": nome, "stagione": s, **r}
            if "punti" in r and "punti" in rb:
                riga["dal_massimo"] = r["punti"] - r["perfetta"]
                riga["vs_completo"] = r["punti"] - rb["punti"]
            riga["rmse_vs_completo"] = r["rmse"] - rb["rmse"]
            riga["rmse_vs_completo_pct"] = 100 * (r["rmse"] - rb["rmse"]) / rb["rmse"] if rb["rmse"] else float("nan")
            riga["scarto_gol"] = scarto_gol(fasce[nome], s) if fasce and nome in fasce else float("nan")
            righe.append(riga)
    return pd.DataFrame(righe)


def testo_fasce(fasce: dict[str, pd.DataFrame]) -> str:
    """Le fasce di gol attesi di ogni scenario, in una tabella da leggere."""
    t = pd.concat([f.assign(scenario=nome) for nome, f in fasce.items()], ignore_index=True)
    return ("\nGol attesi per fasce (presenze con voto; attesi e veri = gol a partita, rigori compresi; scarto = veri − attesi;"
            f" in tabella `scarto_gol` = lo scarto più grande nelle fasce con almeno {MIN_CASI_FASCIA} casi):\n"
            + t[["scenario"] + COLONNE_FASCE].round(3).to_string(index=False))


def confronto(d: Dati, regole: Regole, par: Parametri, giornate, rose=None, simulazioni: int = 300,
              scenari=SCENARI, scrivi=print) -> tuple[pd.DataFrame, dict]:
    """`tabella` degli scenari scelti (più `completo`, che si calcola sempre) e le note di ciascuno; con `scrivi`, anche le
    fasce dei gol attesi."""
    nomi = ["completo"] + [s for s in scenari if s != "completo"]
    tabelle, note = {}, {}
    for nome in nomi:
        if scrivi:
            scrivi(f"Scenario «{nome}»...")
        t, n = esegui(nome, d, regole, par, giornate, rose, simulazioni)
        if not t.empty:
            tabelle[nome], note[nome] = t, n
    fasce = {nome: n["gol_per_fasce"] for nome, n in note.items() if "gol_per_fasce" in n}
    if scrivi and fasce:
        scrivi(testo_fasce(fasce))
    return (tabella(tabelle, fasce) if "completo" in tabelle else pd.DataFrame()), note
