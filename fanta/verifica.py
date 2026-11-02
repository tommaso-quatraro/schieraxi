"""Verifica del modello sulle giornate già giocate (backtest): per ogni giornata usa solo i dati precedenti.

Misura:
1. previsione del fantavoto di chi ha giocato: errore medio del modello e di una scelta "da fantamedia";
2. presenze: quanto bene p_voto prevede chi prende voto (punteggio di Brier, più basso = meglio);
3. formazioni: punti veri (con le sostituzioni) delle formazioni consigliate alle rose della lega,
   contro le formazioni scelte per fantamedia e contro la formazione perfetta col senno di poi.
Nelle giornate passate non abbiamo le probabili formazioni: p_voto viene dalle presenze recenti, quindi
qui il modello è più debole che dal vivo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import formazione as fz
from .modello import Dati, Parametri, previsioni
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import RUOLI, Regole, modulo_in_numeri

MIN_GIOCATORI_ROSA = 20

# Esperimenti «oracolo» (spenti di default): al modello si dà, una cosa alla volta, la conoscenza perfetta di ciò che
# nella realtà non si sa prima della partita. Il guadagno rispetto alla verifica normale dice quanto varrebbe una fonte nuova.
ORACOLI = ("presenze", "gol_squadra", "rigorista")


def dati_oracolo(d: Dati, stagione: str, opzioni) -> dict:
    """Le verità della stagione che servono agli oracoli scelti (per `previsioni`, tranne le presenze)."""
    sconosciute = set(opzioni) - set(ORACOLI)
    if sconosciute:
        raise ValueError(f"oracolo sconosciuto: {', '.join(sorted(sconosciute))} (validi: {', '.join(ORACOLI)})")
    out: dict = {}
    if "gol_squadra" in opzioni:
        p = d.partite[(d.partite["stagione"] == stagione) & (d.partite["giocata"] == 1)
                      & d.partite["gol_casa"].notna() & d.partite["gol_trasferta"].notna()]
        out["gol_squadra"] = {int(i): (float(a), float(b)) for i, a, b in zip(p["id"], p["gol_casa"], p["gol_trasferta"])}
    if "rigorista" in opzioni:
        u = d.prestazioni[(d.prestazioni["stagione"] == stagione) & d.prestazioni["calciatore_id"].notna()]
        sq = u.groupby("squadra")["rigori_calciati"].sum()
        per_g = u.groupby(["calciatore_id", "squadra"])["rigori_calciati"].sum()
        quote: dict[int, float] = {}
        for (cid, squadra), n in per_g.items():
            if n > 0:   # quota vera dei rigori della squadra in tutta la stagione (stessa formula del modello)
                quote[int(cid)] = quote.get(int(cid), 0.0) + float(n) / (float(sq[squadra]) + 0.5)
        out["rigorista"] = quote
    return out


@dataclass
class EsitoGiornata:
    stagione: str
    giornata: int
    errore_modello: float
    errore_fantamedia: float
    brier: float
    n: int
    formazioni: dict | None = None    # {"modello": punti medi, "fantamedia": ..., "perfetta": ...}
    rose_valutate: int = 0
    quadratico_modello: float = float("nan")      # media dei quadrati degli errori (se ne fa la radice nel riepilogo)
    quadratico_fantamedia: float = float("nan")


def _fantamedia(d: Dati, stagione: str, giornata: int, regole: Regole) -> pd.Series:
    """Fantamedia (con le regole della lega) nelle giornate precedenti della stagione; 6 se non ha voti."""
    col = COLONNA_VOTO[regole.fonte_voto]
    V = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] < giornata) & d.voti[col].notna()]
    fv = V.apply(lambda r: fantavoto(r.to_dict(), r["ruolo"], regole), axis=1)
    return fv.groupby(V["calciatore_id"]).mean() if len(V) else pd.Series(dtype=float)


def verifica_giornata(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri,
                      rose: list[list[int]] | None = None, simulazioni: int = 300,
                      oracolo=frozenset(), verita: dict | None = None, casi: list | None = None,
                      sintetiche: int = 0, dati_modello: Dati | None = None, prevedi=None,
                      ritocca=None) -> EsitoGiornata | None:
    """Una giornata del backtest. Con `casi` (una lista) vi aggiunge, per ogni rosa, la formazione del modello con i punti
    attesi, la deviazione simulata e i punti fatti (serve a `incertezza.py`); `sintetiche` = quante rose estratte a sorte
    in più, che vanno SOLO in `casi` (più campioni per misurare lo scarto, senza toccare le medie della verifica).
    Solo per gli esperimenti di `verifica_pacchetti.py` (spenti di default, None = verifica normale): `dati_modello` = i dati
    che vede il modello (la verità resta `d`), `prevedi` = funzione al posto di `previsioni`, `ritocca` = funzione
    (prev, d, stagione, giornata) -> nuove probabilità di giocare."""
    col = COLONNA_VOTO[regole.fonte_voto]
    if oracolo and verita is None:
        verita = dati_oracolo(d, stagione, oracolo)
    dm = d if dati_modello is None else dati_modello
    if prevedi is None:
        prev = previsioni(dm, stagione, giornata, regole, par, oracolo=verita if oracolo else None)
    else:
        prev = prevedi(dm, stagione, giornata, regole, par)
    # solo le partite già giocate (una giornata in corso non deve contare chi deve ancora giocare)
    giocate = d.partite.loc[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == giornata)
                            & (d.partite["giocata"] == 1), "id"]
    if prev.empty or giocate.empty:
        return None
    prev = prev[prev["partita"].isin(set(giocate))]
    reali = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] == giornata)]
    reali = reali.drop_duplicates("calciatore_id").set_index("calciatore_id")
    fm = _fantamedia(d, stagione, giornata, regole)
    prev = prev.set_index("id")
    # 1. fantavoto di chi ha giocato
    giocato = [i for i in prev.index if i in reali.index and pd.notna(reali.at[i, col])]
    fv_vero = {i: fantavoto(reali.loc[i].to_dict(), prev.at[i, "ruolo"], regole) for i in giocato}
    err_m = np.mean([abs(prev.at[i, "mu"] - fv_vero[i]) for i in giocato]) if giocato else np.nan
    err_f = np.mean([abs(fm.get(i, 6.0) - fv_vero[i]) for i in giocato]) if giocato else np.nan
    # errore quadratico: la misura giusta per un valore MEDIO atteso (quello che serve per scegliere)
    q_m = np.mean([(prev.at[i, "mu"] - fv_vero[i]) ** 2 for i in giocato]) if giocato else np.nan
    q_f = np.mean([(fm.get(i, 6.0) - fv_vero[i]) ** 2 for i in giocato]) if giocato else np.nan
    # 2. presenze
    preso = np.array([1.0 if i in fv_vero else 0.0 for i in prev.index])
    if "presenze" in oracolo:       # oracolo: il modello sa già chi prende voto
        prev["p_voto"] = preso
    if ritocca is not None:         # esperimento: probabilità di giocare da un'altra fonte (simulata)
        prev["p_voto"] = np.asarray(ritocca(prev, d, stagione, giornata), dtype=float)
    brier = float(np.mean((prev["p_voto"].to_numpy() - preso) ** 2))
    esito = EsitoGiornata(stagione, giornata, float(err_m), float(err_f), brier, len(giocato))
    esito.quadratico_modello, esito.quadratico_fantamedia = float(q_m), float(q_f)
    # 3. formazioni sulle rose
    if casi is not None and sintetiche:
        _casi_sintetici(prev, sintetiche, stagione, giornata, regole, simulazioni, fv_vero,
                        {i: reali.at[i, col] for i in fv_vero}, casi)
    if rose:
        punti = {"modello": [], "fantamedia": [], "perfetta": []}
        voto_vero = {i: reali.at[i, col] for i in fv_vero}
        gioca_vero = {i: (i in fv_vero) for i in prev.index}
        for rosa_ids in rose:
            ids = [i for i in rosa_ids if i in prev.index]
            if len(ids) < MIN_GIOCATORI_ROSA:   # rosa di oggi quasi vuota in quella giornata: confronto poco utile
                continue
            modello = [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                                    float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids]
            semplice = [fz.Giocatore(g.id, g.nome, g.ruolo, g.p, float(fm.get(g.id, 5.5)), 6.0) for g in modello]
            fv_tutti = {g.id: fv_vero.get(g.id, 0.0) for g in modello}
            voto_tutti = {g.id: voto_vero.get(g.id, 0.0) for g in modello}
            try:
                scelte = {nome: fz.migliore(rosa, regole, simulazioni)
                          for nome, rosa in (("modello", modello), ("fantamedia", semplice))}
            except ValueError:      # rosa di oggi con troppo pochi giocatori presenti in quella giornata
                continue
            for nome, f in scelte.items():
                punti[nome].append(fz.punteggio(f.titolari, f.panchina, gioca_vero, fv_tutti, voto_tutti, regole))
            if casi is not None:
                casi.append(_caso(scelte["modello"], punti["modello"][-1], stagione, giornata, "lega"))
            punti["perfetta"].append(_perfetta(modello, fv_vero, regole))
        if punti["modello"]:
            esito.formazioni = {k: float(np.mean(v)) for k, v in punti.items()}
            esito.rose_valutate = len(punti["modello"])
    return esito


def _caso(f: fz.Formazione, reale: float, stagione: str, giornata: int, tipo: str) -> dict:
    """Un caso per misurare l'incertezza: punti attesi e deviazione simulata della formazione del modello, punti fatti."""
    return {"stagione": stagione, "giornata": giornata, "tipo": tipo, "atteso": f.atteso, "dev": f.dev, "reale": reale}


POSTI_SINTETICI = {"P": 3, "D": 8, "C": 8, "A": 6}


def _casi_sintetici(prev, quante, stagione, giornata, regole, simulazioni, fv_vero, voto_vero, casi) -> None:
    """Rose estratte a sorte (seme fisso) tra chi ha una probabilità vera di giocare: la formazione del modello e i punti fatti."""
    rng = np.random.default_rng(1000 * giornata + int(stagione[:4]))
    pool = {r: prev.index[(prev["ruolo"] == r) & (prev["p_voto"] >= 0.3)].to_numpy() for r in RUOLI}
    if any(len(pool[r]) < n for r, n in POSTI_SINTETICI.items()):
        return
    for _ in range(quante):
        ids = [int(i) for r, n in POSTI_SINTETICI.items() for i in rng.choice(pool[r], n, replace=False)]
        rosa = [fz.Giocatore(i, prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                             float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids]
        try:
            f = fz.migliore(rosa, regole, simulazioni)
        except ValueError:
            continue
        reale = fz.punteggio(f.titolari, f.panchina, {i: i in fv_vero for i in ids}, {i: fv_vero.get(i, 0.0) for i in ids},
                             {i: voto_vero.get(i, 0.0) for i in ids}, regole)
        casi.append(_caso(f, reale, stagione, giornata, "sintetica"))


def _perfetta(rosa: list[fz.Giocatore], fv_vero: dict[int, float], regole: Regole) -> float:
    """Il massimo ottenibile col senno di poi: i migliori fantavoti veri nel modulo migliore (senza modificatore)."""
    per_ruolo = {r: sorted([fv_vero[g.id] for g in rosa if g.ruolo == r and g.id in fv_vero], reverse=True)
                 for r in RUOLI}
    meglio = 0.0
    for m in regole.moduli:
        d, c, a = modulo_in_numeri(m)
        meglio = max(meglio, sum(per_ruolo["P"][:1]) + sum(per_ruolo["D"][:d]) + sum(per_ruolo["C"][:c])
                     + sum(per_ruolo["A"][:a]))
    return meglio


def verifica(d: Dati, regole: Regole, par: Parametri, giornate: list[tuple[str, int]],
             rose: list[list[int]] | None = None, simulazioni: int = 300, scrivi=print,
             oracolo=frozenset(), dati_modello: Dati | None = None, prevedi=None, ritocca=None) -> pd.DataFrame:
    righe = []
    verita: dict[str, dict] = {}
    for stagione, g in giornate:
        if oracolo and stagione not in verita:
            verita[stagione] = dati_oracolo(d, stagione, oracolo)
        e = verifica_giornata(d, stagione, g, regole, par, rose, simulazioni, oracolo, verita.get(stagione),
                              dati_modello=dati_modello, prevedi=prevedi, ritocca=ritocca)
        if e is None:
            continue
        riga = {"stagione": e.stagione, "giornata": e.giornata, "errore_modello": e.errore_modello,
                "errore_fantamedia": e.errore_fantamedia, "brier": e.brier, "n": e.n,
                "quadratico_modello": e.quadratico_modello, "quadratico_fantamedia": e.quadratico_fantamedia}
        if e.formazioni:
            riga |= {f"punti_{k}": v for k, v in e.formazioni.items()} | {"rose": e.rose_valutate}
        righe.append(riga)
        if scrivi:
            extra = (f"  punti ({e.rose_valutate} rose): modello {e.formazioni['modello']:.1f} / fantamedia "
                     f"{e.formazioni['fantamedia']:.1f} / perfetta {e.formazioni['perfetta']:.1f}") if e.formazioni else ""
            scrivi(f"  {stagione} g{g:>2}: errore {e.errore_modello:.2f} (fantamedia {e.errore_fantamedia:.2f}),"
                   f" Brier {e.brier:.3f}{extra}")
    return pd.DataFrame(righe)


def guadagno_oracoli(d: Dati, regole: Regole, par: Parametri, giornate: list[tuple[str, int]],
                     rose: list[list[int]] | None = None, simulazioni: int = 300, scrivi=print) -> pd.DataFrame:
    """Lancia la verifica normale e una per ciascun oracolo (poi tutti insieme); una riga per prova con i numeri medi
    e il guadagno rispetto alla base (punti a giornata per le rose della lega, errore quadratico, Brier)."""
    prove = [("base", frozenset())] + [(o, frozenset([o])) for o in ORACOLI] + [("tutti", frozenset(ORACOLI))]
    righe = []
    for nome, op in prove:
        if scrivi:
            scrivi(f"Prova «{nome}»...")
        t = verifica(d, regole, par, giornate, rose, simulazioni, scrivi=None, oracolo=op)
        if t.empty:
            continue
        riga = {"prova": nome, "giornate": len(t), "rmse": float(t["quadratico_modello"].mean() ** 0.5),
                "brier": float(t["brier"].mean())}
        if "punti_modello" in t:
            riga |= {"punti_modello": float(t["punti_modello"].mean()), "punti_perfetta": float(t["punti_perfetta"].mean())}
        righe.append(riga)
    r = pd.DataFrame(righe)
    if len(r) and "punti_modello" in r:
        base = r.iloc[0]
        r["guadagno_punti"] = r["punti_modello"] - base["punti_modello"]
        r["guadagno_rmse"] = base["rmse"] - r["rmse"]
        r["guadagno_brier"] = base["brier"] - r["brier"]
    return r
