"""Asta (versione base): quanto vale ogni giocatore rispetto a un sostituto e quanti crediti conviene spendere per reparto.

Il metodo è quello classico delle aste: si stimano i punti della stagione di ogni giocatore, si toglie il livello di un sostituto
(il primo giocatore che non farebbe il titolare in nessuna squadra della lega) e si divide il budget della lega in proporzione a
quello che resta. Sono stime per orientarsi, non prezzi garantiti: in asta contano anche la fretta e gli avversari.
"""
from __future__ import annotations

from . import scambi
from .regole import RUOLI, Regole

POSTI_CHE_CONTANO = {"P": 1, "D": 4, "C": 4, "A": 3}     # titolari medi per reparto: oltre questi il giocatore è un sostituto
QUOTA_PANCHINA = 0.12                                       # parte del budget lasciata alla panchina (1 credito a testa o poco più)


def piano(v: scambi.Valori, regole: Regole, squadre: int = 10, massimo_per_ruolo: int = 40) -> dict:
    giornate = len(v.giornate) + v.resto
    punti: dict[int, float] = {}
    for i in v.info.index:
        serie = [t[i][1] * t[i][2] for t in v.per_giornata if i in t]
        if serie:
            punti[int(i)] = giornate * sum(serie) / len(serie)
    per_ruolo = {r: sorted(((i, p) for i, p in punti.items() if v.info.at[i, "ruolo"] == r), key=lambda x: -x[1]) for r in RUOLI}
    sostituzione = {}
    for r in RUOLI:
        elenco = per_ruolo[r]
        posto = squadre * POSTI_CHE_CONTANO[r]
        sostituzione[r] = elenco[posto][1] if len(elenco) > posto else (elenco[-1][1] if elenco else 0.0)
    vorp = {i: max(0.0, p - sostituzione[v.info.at[i, "ruolo"]]) for i, p in punti.items()}
    totale = sum(vorp.values())
    spendibile = regole.crediti_iniziali * squadre * (1 - QUOTA_PANCHINA)
    risultato = []
    for r in RUOLI:
        quota = sum(vorp[i] for i, _ in per_ruolo[r]) / totale if totale else 0.0
        giocatori = []
        for i, p in per_ruolo[r][:massimo_per_ruolo]:
            prezzo = max(1, round(spendibile * vorp[i] / totale)) if totale else 1
            giocatori.append({"id": i, "nome": v.info.at[i, "nome"], "squadra": v.info.at[i, "squadra"],
                              "quotazione": int(v.info.at[i, "quotazione"]), "punti_stagione": round(p, 1), "prezzo": prezzo})
        giocatori.sort(key=lambda g: (-g["prezzo"], -g["punti_stagione"]))
        risultato.append({"ruolo": r, "quota": round(quota, 3), "crediti": round(quota * regole.crediti_iniziali * (1 - QUOTA_PANCHINA)),
                          "giocatori": giocatori})
    return {"crediti": regole.crediti_iniziali, "squadre": squadre, "panchina": round(regole.crediti_iniziali * QUOTA_PANCHINA), "ruoli": risultato}


def piano_riparazione(v: scambi.Valori, regole: Regole, rose, nome: str | None = None, posti_per_squadra: int = 3, massimo_per_ruolo: int = 40) -> dict:
    """Riparazione di febbraio: si sceglie solo tra gli svincolati. Il prezzo di ognuno è la sua parte dei crediti che restano alla lega,
    in proporzione a quanto vale sopra l'ultimo svincolato che troverebbe posto. I posti da riempire sono quelli che mancano nelle rose;
    se le rose sono piene si ipotizza che ogni squadra cambi `posti_per_squadra` giocatori."""
    mia = rose.squadra(nome or rose.mia_squadra or "")
    occupati = {g.id for s in rose.squadre for g in s.giocatori if g.id is not None}
    giornate = len(v.giornate) + v.resto
    punti: dict[int, float] = {}
    for i in v.info.index:
        serie = [t[i][1] * t[i][2] for t in v.per_giornata if i in t]
        if serie:
            punti[int(i)] = giornate * sum(serie) / len(serie)
    liberi = {r: sorted(((i, p) for i, p in punti.items() if i not in occupati and v.info.at[i, "ruolo"] == r), key=lambda x: -x[1]) for r in RUOLI}
    posti = {r: sum(max(0, regole.rosa[r] - sum(1 for g in s.giocatori if g.ruolo == r)) for s in rose.squadre) for r in RUOLI}
    if not any(posti.values()):
        totale_rosa = sum(regole.rosa.values())
        posti = {r: round(len(rose.squadre) * posti_per_squadra * regole.rosa[r] / totale_rosa) for r in RUOLI}
    sostituzione = {}
    for r in RUOLI:
        elenco, n = liberi[r], posti[r]
        sostituzione[r] = elenco[n][1] if len(elenco) > n else (elenco[-1][1] if elenco else 0.0)
    vorp = {i: max(0.0, p - sostituzione[v.info.at[i, "ruolo"]]) for r in RUOLI for i, p in liberi[r]}
    # solo i giocatori che trovano posto contano per dividere il budget
    comprati = {i for r in RUOLI for i, _ in liberi[r][:posti[r]]}
    totale = sum(vorp[i] for i in comprati)
    crediti_lega = sum(s.crediti_residui for s in rose.squadre if s.crediti_residui is not None)
    conosciuti = [s for s in rose.squadre if s.crediti_residui is not None]

    def prezzo(i: int) -> int:
        if conosciuti and totale:
            return max(1, round(crediti_lega * vorp[i] / totale)) if i in comprati else 1
        return int(v.info.at[i, "quotazione"])           # crediti non inseriti: si usa la quotazione come prezzo di riferimento

    risultato = []
    for r in RUOLI:
        giocatori = [{"id": i, "nome": v.info.at[i, "nome"], "squadra": v.info.at[i, "squadra"], "quotazione": int(v.info.at[i, "quotazione"]),
                      "punti_stagione": round(p, 1), "prezzo": prezzo(i)} for i, p in liberi[r][:massimo_per_ruolo]]
        risultato.append({"ruolo": r, "posti": posti[r], "giocatori": giocatori})
    tuoi = mia.crediti_residui if mia else None
    per_te = []
    if mia:
        mie = {r: sorted(((g.id, punti.get(g.id, 0.0), g.nome) for g in mia.giocatori if g.ruolo == r and g.id is not None), key=lambda x: x[1]) for r in RUOLI}
        for r in RUOLI:
            if not mie[r]:
                continue
            debole = mie[r][0]
            for i, p in liberi[r]:
                costo = prezzo(i)
                if p > debole[1] + 0.5 and (tuoi is None or costo <= tuoi):
                    per_te.append({"id": i, "nome": v.info.at[i, "nome"], "ruolo": r, "squadra": v.info.at[i, "squadra"], "prezzo": costo,
                                   "miglioramento": round(p - debole[1], 1), "al_posto_di": debole[2]})
        per_te.sort(key=lambda g: -g["miglioramento"])
    nota = ("Stima: i prezzi dividono i crediti che restano alla lega tra gli svincolati che troverebbero posto; " if conosciuti
            else "I crediti delle squadre non sono inseriti (Lega > Crediti): come prezzo di riferimento c'è la quotazione. ")
    nota += ("Rose piene: si ipotizza che ogni squadra cambi %d giocatori." % posti_per_squadra) if not any(
        max(0, regole.rosa[r] - sum(1 for g in s.giocatori if g.ruolo == r)) for r in RUOLI for s in rose.squadre) else "I posti sono quelli che mancano nelle rose."
    return {"modo": "riparazione", "tuoi_crediti": tuoi, "crediti_lega": crediti_lega if conosciuti else None, "posti_liberi": sum(posti.values()),
            "nota": nota, "ruoli": risultato, "per_te": per_te[:10]}
