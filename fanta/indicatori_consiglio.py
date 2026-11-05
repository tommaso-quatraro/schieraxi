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

from datetime import datetime, timedelta

from . import formazione as fz
from . import verifica_consiglio as vc
from .regole import Regole

MAX_CAMBI = 10                  # cambi ricordati per giornata (gli ultimi: quelli vicini alla scadenza)
PRIMA_DELLA_SCADENZA = timedelta(hours=24)      # C2 conta i cambi da qui alla scadenza
# C3 e C4 di una consigliata (`misure`), nell'istantanea e nella voce del Diario
MISURE = ("improbabili", "con_compagno", "reparti", "storte", "spiegate", "titolari", "vuoti", "senza_motivo")


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


def guadagno(c: dict, regole: Regole) -> float | None:
    """Quanto valeva un cambio (`cambio`): punti attesi della consigliata nuova meno quelli dei titolari di prima, con i numeri di quel
    momento e le simulazioni dell'app (`verifica_consiglio.valore_di_prima`, lo stesso conto della consigliata stabile). None se il
    cambio non porta i numeri della rosa o non tornano."""
    try:
        rosa = [fz.Giocatore(int(i), "", str(ruolo), float(p), float(mu), float(mv)) for i, ruolo, p, mu, mv in c["rosa"]]
        per_id = {g.id: g for g in rosa}
        prima = [int(i) for i in c["prima"]]
        nuovi = [per_id[int(i)] for i in c["dopo"]]
        panchina = [per_id[int(i)] for i in c.get("panchina") or [] if int(i) in per_id]
        if len(prima) != 11 or len(nuovi) != 11 or any(i not in per_id for i in prima):
            return None
        val = fz.Valutatore(rosa, regole, vc.SIMULAZIONI)
        return float(val.atteso(nuovi, panchina) - vc.valore_di_prima(val, rosa, prima, regole))
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _quando(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo))
    except ValueError:
        return None


def conta_cambi(cambi: list, scadenza: datetime | None, regole: Regole) -> tuple[int | None, int | None]:
    """C2 di una giornata: (cambi dei titolari nelle 24 ore prima della scadenza, quanti di loro valevano meno della soglia
    `verifica_consiglio.SOGLIA_CAMBIO` senza essere motivati). (None, None) senza la scadenza (calendario senza date)."""
    if scadenza is None:
        return None, None
    da = scadenza - PRIMA_DELLA_SCADENZA
    nel_giorno = [c for c in cambi if isinstance(c, dict) and (q := _quando(c.get("quando"))) is not None and da <= q < scadenza]
    sotto = 0
    for c in nel_giorno:
        if c.get("motivata") is False and (g := guadagno(c, regole)) is not None and g < vc.SOGLIA_CAMBIO:
            sotto += 1
    return len(nel_giorno), sotto
