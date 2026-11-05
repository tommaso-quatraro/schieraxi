"""Indicatori del consiglio di formazione nel Diario e in «Stato dei dati» (C1-C4 di #166, lavoro L4).

Si misurano a ogni giornata finita sulla consigliata MOSTRATA (l'istantanea del Diario, congelata alla scadenza), per ogni utente,
con le definizioni della misura in laboratorio (`verifica_consiglio.py`, riusate così come sono):
- C1 valore: punti veri della consigliata mostrata contro la scelta semplice S2 e contro la schierata, quando è diversa;
- C2 stabilità: quante volte i titolari della consigliata sono cambiati nelle 24 ore prima della scadenza, e quanti di quei cambi
  valevano meno della soglia (1 punto atteso) senza un titolare diventato fuori o improbabile. Il cambio si registra quando
  l'istantanea si sovrascrive (`cambio`), con i numeri di allora; il suo valore si ricalcola a giornata finita (`conta_cambi`);
- C3 chi gioca: titolari sotto il 20% (o fuori) con un compagno di ruolo al 50% o più;
- C4 perché: scelte che sembrano storte e titolari senza un motivo proprio nel «perché questo numero».
C3 e C4 si contano a ogni salvataggio dell'istantanea (`misure`): resta quello dell'ultima, la mostrata.
Niente nomi né dati personali: solo id dei giocatori nel Diario dell'utente, e solo numeri nei totali per il proprietario.
"""
from __future__ import annotations

from . import verifica_consiglio as vc

MAX_CAMBI = 10                  # cambi ricordati per giornata (gli ultimi: quelli vicini alla scadenza)


def misure(f: dict) -> dict | None:
    """C3 e C4 della consigliata `f` (la risposta di `consigli.formazione`): titolari improbabili e quanti con un compagno di ruolo
    che gioca, scelte che sembrano storte per reparto, titolari con il «perché» vuoto o senza un motivo proprio. None se `f` non ha
    le schede dei giocatori o i moduli (formazione incompleta)."""
    if not isinstance(f.get("schede"), dict) or not isinstance(f.get("moduli"), list):
        return None
    try:
        ng = vc.non_giocano(f)
        return {"improbabili": len(ng), "con_compagno": sum(1 for _, c in ng if c is not None), **vc.scelte_storte(f),
                **vc.perche_titolari(f)}
    except (KeyError, TypeError, ValueError):
        return None


def _p(x, altrimenti: float) -> float:
    """Un «gioca N%» letto da un file o da una scheda; `altrimenti` se manca o non è un numero."""
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else altrimenti


def cambio(vecchia: dict, f: dict, quando: str) -> dict | None:
    """Il cambio dalla consigliata dell'istantanea `vecchia` alla nuova `f`, se i titolari sono diversi (None se no).
    `motivata`: un titolare di prima è uscito dalla rosa, è fuori o è sceso sotto il 20% (`verifica_consiglio.motivata`): quel cambio
    va bene anche se vale poco. Se non è motivata il cambio porta anche i numeri della rosa di quel momento (id, ruolo, «gioca N%»,
    fantavoto e voto attesi, nell'ordine della rosa come l'app), per ricalcolarne il valore a giornata finita con le regole della lega."""
    prima = [int(t["id"]) for t in vecchia.get("titolari") or [] if isinstance(t, dict) and "id" in t]
    dopo = [int(t["id"]) for t in f.get("titolari") or [] if isinstance(t, dict) and "id" in t]
    if not prima or set(prima) == set(dopo):
        return None
    r = {"quando": quando, "prima": prima, "dopo": dopo, "motivata": None}
    schede = f.get("schede")
    if not isinstance(schede, dict):
        return r                                                   # senza schede non si giudica: conta solo il cambio
    p_prima = {int(t["id"]): _p(t.get("p_voto"), 1.0) for t in vecchia["titolari"] if isinstance(t, dict) and "id" in t}
    p_dopo = {}
    for i in prima:
        s = schede.get(str(i))
        p_dopo[i] = 0.0 if not isinstance(s, dict) or vc.e_fuori(s) else _p(s.get("p_voto"), 0.0)
    r["motivata"] = vc.motivata(p_prima, p_dopo, prima)
    if not r["motivata"]:
        try:
            r["rosa"] = [[int(s["id"]), str(s["ruolo"])[:1], round(float(s["p_voto"]), 3), round(float(s["fv_atteso"]), 2),
                          round(float(s["voto_atteso"]), 2)] for s in schede.values()]
        except (KeyError, TypeError, ValueError):
            pass                                                   # schede incomplete: il valore del cambio non si potrà ricalcolare
        r["panchina"] = [int(t["id"]) for t in f.get("panchina") or [] if isinstance(t, dict) and "id" in t]
    return r
