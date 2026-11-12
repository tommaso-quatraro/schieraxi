"""Verifica del modello sulle giornate già giocate (backtest): per ogni giornata usa solo i dati precedenti.

Misura:
1. previsione del fantavoto di chi ha giocato: errore del modello e di due avversari onesti (#614), la fantamedia tirata verso
   il ruolo e un numero fisso per ruolo (`avversari`). La fantamedia della sola stagione in corso, con 6 a chi non ha voti,
   era l'avversario di prima: fa peggio di un numero fisso per ruolo e faceva sembrare il vantaggio del modello dieci volte
   più grande (misura del 12/11/2026: modello -6,7% contro quella, -2,2% contro il numero fisso, -1,1% contro la tirata).
   Resta solo come numero di confronto (`quadratico_fantamedia_stagione`);
2. presenze: quanto bene p_voto prevede chi prende voto (punteggio di Brier, più basso = meglio);
3. formazioni: punti veri (con le sostituzioni) delle formazioni consigliate alle rose della lega, contro le formazioni scelte
   per fantamedia (quella tirata) e contro il massimo possibile col senno di poi (con le regole della lega, `_perfetta`).
   Con `sintetiche` anche su rose estratte a sorte: poche rose vere non distinguono mezzo punto (`riepilogo_sorte`).
Nelle giornate passate non abbiamo le probabili formazioni: p_voto viene dalle presenze recenti, quindi
qui il modello è più debole che dal vivo.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import formazione as fz
from .modello import Dati, Parametri, previsioni
from .punteggio import COLONNA_VOTO, fantavoto, modificatore_difesa
from .regole import RUOLI, Regole, modulo_in_numeri

MIN_GIOCATORI_ROSA = 20
PRESENZE_FITTIZIE = 10      # fantamedia tirata verso il ruolo: presenze fittizie alla media del ruolo
ROSE_A_SORTE = 20           # rose estratte a sorte per giornata nelle misure in punti (`python -m fanta verifica`)
FANTAVOTO_SENZA_RUOLO = 6.0  # ruolo che non ha ancora nessun voto (solo all'inizio dell'archivio)

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
    quadratico_fantamedia: float = float("nan")   # la fantamedia tirata verso il ruolo (anche `errore_fantamedia`)
    quadratico_ruolo: float = float("nan")        # un numero fisso per ruolo
    quadratico_fantamedia_stagione: float = float("nan")   # l'avversario di prima: fantamedia della stagione, 6 senza voti
    errore_ruolo: float = float("nan")
    sorte: list | None = None         # rose a sorte: [(punti della consigliata, punti «da fantamedia», massimo possibile)]


def _fantamedia(d: Dati, stagione: str, giornata: int, regole: Regole) -> pd.Series:
    """Fantamedia (con le regole della lega) nelle giornate precedenti della stagione; 6 se non ha voti. È quella che vede chi
    non ha l'app (la usa S2 di `verifica_consiglio`); come avversario del modello è debole: vedi `avversari`."""
    col = COLONNA_VOTO[regole.fonte_voto]
    V = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] < giornata) & d.voti[col].notna()]
    fv = V.apply(lambda r: fantavoto(r.to_dict(), r["ruolo"], regole), axis=1)
    return fv.groupby(V["calciatore_id"]).mean() if len(V) else pd.Series(dtype=float)


def avversari(d: Dati, stagione: str, giornata: int, regole: Regole) -> tuple[pd.Series, dict[str, float]]:
    """Gli avversari onesti del fantavoto atteso, con i voti di PRIMA della giornata (anche delle stagioni passate) e le regole
    della lega: (fantamedia tirata verso il ruolo per giocatore, {ruolo: fantavoto medio}).
    Tirata = (somma dei suoi fantavoti + PRESENZE_FITTIZIE x media del suo ruolo) / (presenze + PRESENZE_FITTIZIE): chi ha pochi
    voti sta vicino al ruolo. Chi non ne ha nessuno non c'è: per lui vale la media del ruolo."""
    col = COLONNA_VOTO[regole.fonte_voto]
    v = d.voti
    prima = ((v["stagione"] < stagione) | ((v["stagione"] == stagione) & (v["giornata"] < giornata))) & v[col].notna()
    V = v[prima].drop_duplicates(["stagione", "giornata", "calciatore_id"]).sort_values(["stagione", "giornata"])
    if V.empty:
        return pd.Series(dtype=float), {}
    fv = pd.Series([fantavoto(x, x["ruolo"], regole) for x in V.to_dict("records")], index=V.index, dtype=float)
    ruolo = {str(r): float(m) for r, m in fv.groupby(V["ruolo"]).mean().items()}
    per = fv.groupby(V["calciatore_id"]).agg(["sum", "size"])
    del_ruolo = V.groupby("calciatore_id")["ruolo"].last().map(ruolo)          # il ruolo dell'ultimo voto
    return (per["sum"] + PRESENZE_FITTIZIE * del_ruolo) / (per["size"] + PRESENZE_FITTIZIE), ruolo


def verifica_giornata(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri,
                      rose: list[list[int]] | None = None, simulazioni: int = 300,
                      oracolo=frozenset(), verita: dict | None = None, casi: list | None = None,
                      sintetiche: int = 0, dati_modello: Dati | None = None, prevedi=None,
                      ritocca=None, sorte: bool = False) -> EsitoGiornata | None:
    """Una giornata del backtest. Con `casi` (una lista) vi aggiunge, per ogni rosa, la formazione del modello con i punti
    attesi, la deviazione simulata e i punti fatti (serve a `incertezza.py`); `sintetiche` = quante rose estratte a sorte
    in più, che vanno SOLO in `casi` (più campioni per misurare lo scarto, senza toccare le medie della verifica) e, con
    `sorte`, in `EsitoGiornata.sorte`: per ognuna i punti della consigliata, della formazione «da fantamedia» e il massimo.
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
    fm = _fantamedia(d, stagione, giornata, regole)             # l'avversario di prima: resta come numero di confronto
    tirata, media_ruolo = avversari(d, stagione, giornata, regole)
    tirata = tirata.to_dict()
    prev = prev.set_index("id")

    def fisso(i) -> float:
        return media_ruolo.get(prev.at[i, "ruolo"], FANTAVOTO_SENZA_RUOLO)

    def onesta(i) -> float:
        return float(tirata[i]) if i in tirata else fisso(i)
    # 1. fantavoto di chi ha giocato
    giocato = [i for i in prev.index if i in reali.index and pd.notna(reali.at[i, col])]
    fv_vero = {i: fantavoto(reali.loc[i].to_dict(), prev.at[i, "ruolo"], regole) for i in giocato}

    def medio(stima, potenza: int) -> float:
        return float(np.mean([abs(stima(i) - fv_vero[i]) ** potenza for i in giocato])) if giocato else float("nan")
    err_m, err_f, err_r = medio(lambda i: prev.at[i, "mu"], 1), medio(onesta, 1), medio(fisso, 1)
    # errore quadratico: la misura giusta per un valore MEDIO atteso (quello che serve per scegliere)
    q_m, q_f, q_r = medio(lambda i: prev.at[i, "mu"], 2), medio(onesta, 2), medio(fisso, 2)
    q_s = medio(lambda i: fm.get(i, 6.0), 2)
    # 2. presenze
    preso = np.array([1.0 if i in fv_vero else 0.0 for i in prev.index])
    if "presenze" in oracolo:       # oracolo: il modello sa già chi prende voto
        prev["p_voto"] = preso
    if ritocca is not None:         # esperimento: probabilità di giocare da un'altra fonte (simulata)
        prev["p_voto"] = np.asarray(ritocca(prev, d, stagione, giornata), dtype=float)
    brier = float(np.mean((prev["p_voto"].to_numpy() - preso) ** 2))
    esito = EsitoGiornata(stagione, giornata, float(err_m), float(err_f), brier, len(giocato))
    esito.quadratico_modello, esito.quadratico_fantamedia = float(q_m), float(q_f)
    esito.quadratico_ruolo, esito.quadratico_fantamedia_stagione, esito.errore_ruolo = float(q_r), float(q_s), float(err_r)
    # 3. formazioni sulle rose
    if sintetiche and (casi is not None or sorte):
        esito.sorte = _casi_sintetici(prev, sintetiche, stagione, giornata, regole, simulazioni, fv_vero,
                                      {i: reali.at[i, col] for i in fv_vero}, casi, onesta if sorte else None) or None
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
            semplice = [fz.Giocatore(g.id, g.nome, g.ruolo, g.p, onesta(g.id), 6.0) for g in modello]
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
            # il massimo non sta mai sotto una formazione valutata (con il voto d'ufficio un buco può valere più di un voto vero)
            punti["perfetta"].append(max(_perfetta(modello, fv_vero, regole, voto_vero), punti["modello"][-1], punti["fantamedia"][-1]))
        if punti["modello"]:
            esito.formazioni = {k: float(np.mean(v)) for k, v in punti.items()}
            esito.rose_valutate = len(punti["modello"])
    return esito


def _caso(f: fz.Formazione, reale: float, stagione: str, giornata: int, tipo: str) -> dict:
    """Un caso per misurare l'incertezza: punti attesi e deviazione simulata della formazione del modello, punti fatti."""
    return {"stagione": stagione, "giornata": giornata, "tipo": tipo, "atteso": f.atteso, "dev": f.dev, "reale": reale}


POSTI_SINTETICI = {"P": 3, "D": 8, "C": 8, "A": 6}


def _casi_sintetici(prev, quante, stagione, giornata, regole, simulazioni, fv_vero, voto_vero, casi, fantamedia=None) -> list:
    """Rose estratte a sorte (seme fisso) tra chi ha una probabilità vera di giocare: la formazione del modello e i punti fatti,
    in `casi` se è una lista. Con `fantamedia` (funzione id -> stima) anche la formazione scelta con quella stima e il massimo
    possibile: restituisce [(punti della consigliata, punti «da fantamedia», massimo)], una voce per rosa."""
    rng = np.random.default_rng(1000 * giornata + int(stagione[:4]))
    pool = {r: prev.index[(prev["ruolo"] == r) & (prev["p_voto"] >= 0.3)].to_numpy() for r in RUOLI}
    if any(len(pool[r]) < n for r, n in POSTI_SINTETICI.items()):
        return []
    punti = []
    for _ in range(quante):
        ids = [int(i) for r, n in POSTI_SINTETICI.items() for i in rng.choice(pool[r], n, replace=False)]
        rosa = [fz.Giocatore(i, prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                             float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids]
        try:
            f = fz.migliore(rosa, regole, simulazioni)
        except ValueError:
            continue
        veri = ({i: i in fv_vero for i in ids}, {i: fv_vero.get(i, 0.0) for i in ids}, {i: voto_vero.get(i, 0.0) for i in ids})
        reale = fz.punteggio(f.titolari, f.panchina, *veri, regole)
        if casi is not None:
            casi.append(_caso(f, reale, stagione, giornata, "sintetica"))
        if fantamedia is not None:
            s = fz.migliore([fz.Giocatore(g.id, g.nome, g.ruolo, g.p, fantamedia(g.id), 6.0) for g in rosa], regole, simulazioni)
            semplice = fz.punteggio(s.titolari, s.panchina, *veri, regole)
            punti.append((reale, semplice, max(_perfetta(rosa, fv_vero, regole, voto_vero), reale, semplice)))
    return punti


def _perfetta(rosa: list[fz.Giocatore], fv_vero: dict[int, float], regole: Regole,
              voto_vero: dict[int, float] | None = None) -> float:
    """Il massimo ottenibile col senno di poi con le regole della lega: i migliori fantavoti veri nel modulo migliore, più il
    modificatore della difesa se la lega lo usa e si passano i voti (`voto_vero`; senza, il conto è senza modificatore).
    Con il modificatore i difensori non si scelgono solo per fantavoto: si provano tutti i gruppi di difensori e ogni portiere
    (poche centinaia di casi). Prima il modificatore non c'era e in una lega che lo usa la consigliata a volte superava il
    «massimo» (4 giornate su 16 nel 2025-26, misura del 12/11/2026)."""
    con_voto = {r: sorted((g.id for g in rosa if g.ruolo == r and g.id in fv_vero), key=lambda i: -fv_vero[i]) for r in RUOLI}
    mod = regole.modificatore_difesa
    con_modificatore = bool(mod.attivo) and voto_vero is not None
    meglio = 0.0
    for m in regole.moduli:
        d, c, a = modulo_in_numeri(m)
        davanti = sum(fv_vero[i] for i in con_voto["C"][:c]) + sum(fv_vero[i] for i in con_voto["A"][:a])
        dietro = sum(fv_vero[i] for i in con_voto["P"][:1]) + sum(fv_vero[i] for i in con_voto["D"][:d])
        if con_modificatore and con_voto["P"] and min(d, len(con_voto["D"])) >= mod.min_difensori:
            for p in con_voto["P"]:
                for dif in itertools.combinations(con_voto["D"], min(d, len(con_voto["D"]))):
                    dietro = max(dietro, fv_vero[p] + sum(fv_vero[i] for i in dif)
                                 + modificatore_difesa(voto_vero[p], [voto_vero[i] for i in dif], regole))
        meglio = max(meglio, dietro + davanti)
    return meglio


def verifica(d: Dati, regole: Regole, par: Parametri, giornate: list[tuple[str, int]],
             rose: list[list[int]] | None = None, simulazioni: int = 300, scrivi=print,
             oracolo=frozenset(), dati_modello: Dati | None = None, prevedi=None, ritocca=None,
             sintetiche: int = 0) -> pd.DataFrame:
    """Una riga per giornata. `sintetiche` = rose estratte a sorte per giornata per le misure in punti (colonne `sorte_*`,
    da riassumere con `riepilogo_sorte`); 0 = solo le rose date."""
    righe = []
    verita: dict[str, dict] = {}
    for stagione, g in giornate:
        if oracolo and stagione not in verita:
            verita[stagione] = dati_oracolo(d, stagione, oracolo)
        e = verifica_giornata(d, stagione, g, regole, par, rose, simulazioni, oracolo, verita.get(stagione),
                              dati_modello=dati_modello, prevedi=prevedi, ritocca=ritocca, sintetiche=sintetiche,
                              sorte=bool(sintetiche))
        if e is None:
            continue
        riga = {"stagione": e.stagione, "giornata": e.giornata, "errore_modello": e.errore_modello,
                "errore_fantamedia": e.errore_fantamedia, "brier": e.brier, "n": e.n,
                "quadratico_modello": e.quadratico_modello, "quadratico_fantamedia": e.quadratico_fantamedia,
                "errore_ruolo": e.errore_ruolo, "quadratico_ruolo": e.quadratico_ruolo,
                "quadratico_fantamedia_stagione": e.quadratico_fantamedia_stagione}
        if e.formazioni:
            riga |= {f"punti_{k}": v for k, v in e.formazioni.items()} | {"rose": e.rose_valutate}
        if e.sorte:
            m, f, p = (float(np.mean(x)) for x in zip(*e.sorte))
            riga |= {"sorte_casi": len(e.sorte), "sorte_modello": m, "sorte_fantamedia": f, "sorte_perfetta": p,
                     "sorte_differenza": m - f}
        righe.append(riga)
        if scrivi:
            extra = (f"  punti ({e.rose_valutate} rose): modello {e.formazioni['modello']:.1f} / fantamedia "
                     f"{e.formazioni['fantamedia']:.1f} / perfetta {e.formazioni['perfetta']:.1f}") if e.formazioni else ""
            scrivi(f"  {stagione} g{g:>2}: errore {e.errore_modello:.2f} (fantamedia {e.errore_fantamedia:.2f}),"
                   f" Brier {e.brier:.3f}{extra}")
    return pd.DataFrame(righe)


def riepilogo_sorte(t: pd.DataFrame, giri: int = 4000, seme: int = 5) -> dict[str, dict]:
    """Per stagione, sulle rose a sorte di `verifica(..., sintetiche=N)`: punti medi della consigliata, della formazione «da
    fantamedia» e massimo possibile, e la differenza consigliata meno fantamedia con l'intervallo al 95%, ricampionando le
    giornate intere (le rose della stessa giornata non sono indipendenti). {} se `t` non ha rose a sorte."""
    if "sorte_casi" not in t:
        return {}
    rng = np.random.default_rng(seme)
    esito = {}
    for stagione, x in t[t["sorte_casi"].notna()].groupby("stagione"):
        n = x["sorte_casi"].to_numpy(dtype=float)
        media = lambda c, x=x, n=n: float((x[c].to_numpy(dtype=float) * n).sum() / n.sum())      # noqa: E731
        somme = x["sorte_differenza"].to_numpy(dtype=float) * n
        pesca = rng.integers(0, len(x), (giri, len(x)))
        basso, alto = np.percentile(somme[pesca].sum(axis=1) / n[pesca].sum(axis=1), [2.5, 97.5])
        esito[str(stagione)] = {"casi": int(n.sum()), "giornate": len(x), "modello": media("sorte_modello"),
                                "fantamedia": media("sorte_fantamedia"), "perfetta": media("sorte_perfetta"),
                                "differenza": media("sorte_differenza"), "basso": float(basso), "alto": float(alto)}
    return esito


def stampa_riepilogo(t: pd.DataFrame, scrivi=print) -> None:
    """Il riepilogo per stagione di `python -m fanta verifica`: errori (radice della media dei quadrati) del modello e degli
    avversari, punti sulle rose date e, se ci sono, sulle rose a sorte con l'intervallo."""
    t = t.copy()
    nomi = {"rmse_modello": "quadratico_modello", "rmse_fantamedia": "quadratico_fantamedia", "rmse_ruolo": "quadratico_ruolo",
            "rmse_fantamedia_stagione": "quadratico_fantamedia_stagione"}
    for nuovo_nome, vecchio in nomi.items():
        if vecchio in t:
            t[nuovo_nome] = t[vecchio]
    colonne = [c for c in (*nomi, "errore_modello", "errore_fantamedia", "brier", "punti_modello", "punti_fantamedia",
                           "punti_perfetta") if c in t]
    riepilogo = t.groupby("stagione")[colonne].mean()
    for c in nomi:
        if c in riepilogo:
            riepilogo[c] = riepilogo[c] ** 0.5          # radice della media dei quadrati
    scrivi("\nRiepilogo per stagione (rmse = errore quadratico medio, la misura principale; «fantamedia» = tirata verso il ruolo,")
    scrivi("«ruolo» = un numero fisso per ruolo, «fantamedia_stagione» = quella di prima, della sola stagione e 6 senza voti):")
    scrivi(riepilogo.round(3).to_string())
    for stagione, r in riepilogo.iterrows():
        if "rmse_fantamedia" in riepilogo and r["rmse_fantamedia"] > 0:
            scrivi(f"  {stagione}: il modello sbaglia {100 * (r['rmse_modello'] / r['rmse_fantamedia'] - 1):+.1f}% rispetto alla fantamedia "
                   f"tirata e {100 * (r['rmse_modello'] / r['rmse_ruolo'] - 1):+.1f}% rispetto al numero fisso per ruolo")
    sorte = riepilogo_sorte(t)
    if sorte:
        scrivi("\nPunti su rose estratte a sorte (intervallo al 95% ricampionando le giornate):")
        for stagione, r in sorte.items():
            scrivi(f"  {stagione}: {r['casi']} rose in {r['giornate']} giornate; consigliata {r['modello']:.2f}, da fantamedia "
                   f"{r['fantamedia']:.2f}, massimo possibile {r['perfetta']:.2f}; consigliata meno fantamedia "
                   f"{r['differenza']:+.2f} [{r['basso']:+.2f}; {r['alto']:+.2f}]")


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
