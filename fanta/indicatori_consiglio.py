"""Indicatori del consiglio di formazione nel Diario e in «Stato dei dati» (C1-C4 di #166, lavoro L4).

Si misurano a ogni giornata finita sulla consigliata MOSTRATA (l'istantanea del Diario, congelata alla scadenza), per ogni utente,
con le definizioni della misura in laboratorio (`verifica_consiglio.py`, riusate così come sono):
- C1 valore: punti veri della consigliata mostrata contro la scelta semplice S2 e contro la schierata, quando è diversa;
- C2 stabilità: quante volte i titolari della consigliata sono cambiati nelle 24 ore prima della scadenza, e quanti di quei cambi
  valevano meno della soglia (1 punto atteso) senza un titolare diventato fuori o improbabile. Il cambio si registra quando
  l'istantanea si sovrascrive (`cambio`), con i numeri di allora; il suo valore si ricalcola a giornata finita (`conta_cambi`);
- C3 chi gioca: titolari sotto il 20% (o fuori) con un compagno di ruolo che gioca almeno il 20% (le soglie con cui l'app
  sceglie, `formazione.IMPROBABILE_SOTTO` e `COMPAGNO_ALMENO`, lette da `verifica_consiglio`);
- C4 perché: scelte che sembrano storte e titolari senza un motivo proprio nel «perché questo numero».
C3 e C4 si contano a ogni salvataggio dell'istantanea (`misure`): resta quello dell'ultima, la mostrata.

Per il proprietario («Stato dei dati», campo `consiglio`): `giro` somma le voci di tutti i Diari per giornata, fa le medie sulle
ultime FINESTRA giornate (verdetto solo a finestra piena) e manda un avviso (canale della sentinella) quando una media resta fuori
soglia per 2 giornate di fila, una volta sola; se l'avviso non parte si riprova al giro dopo. Lo stesso schema del registro delle
giornate (#165). C1 non manda avvisi (`AVVISANO`, #614): resta in «Stato dei dati» con il suo numero. Gira dopo il Diario di
tutti, nel comando `python -m fanta affidabilita` del cron; i totali e lo stato dell'avviso stanno in
`dati/indicatori-consiglio.json` (solo giornate e numeri).
Niente nomi né dati personali: solo id dei giocatori nel Diario dell'utente, e solo numeri nei totali per il proprietario.
"""
from __future__ import annotations

import contextlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from . import formazione as fz
from . import verifica_consiglio as vc
from .percorsi import RADICE, scrivi_sicuro
from .regole import Regole

MAX_CAMBI = 10                  # cambi ricordati per giornata (gli ultimi: quelli vicini alla scadenza)
PRIMA_DELLA_SCADENZA = timedelta(hours=24)      # C2 conta i cambi da qui alla scadenza
# C3 e C4 di una consigliata (`misure`), nell'istantanea e nella voce del Diario
MISURE = ("improbabili", "con_compagno", "reparti", "storte", "spiegate", "titolari", "vuoti", "senza_motivo")
FILE = RADICE / "dati" / "indicatori-consiglio.json"
FINESTRA = 8                    # come il registro delle giornate (registro_giornate.FINESTRA): medie sulle ultime 8 giornate
MOSTRATE = 38                   # giornate tenute e mostrate in «Stato dei dati»: al massimo una stagione
# soglie della proposta (§2, decise il 5/11/2026): C1 consigliata meno S2 e meno la schierata almeno 0; C2 nessun cambio sotto
# la soglia; C3 nessun titolare improbabile con un compagno che gioca; C4 tutte le scelte storte spiegate e titolari senza un motivo
# proprio al massimo il 10%
SOGLIE = {"C1": 0.0, "C2": 0, "C3": 0, "C4_senza_motivo": vc.MAX_SENZA_MOTIVO}
# Gli indicatori che mandano l'avviso. C1 no (#614): su 8 giornate di poche rose la differenza in punti esce dalla soglia per
# caso (misura del 12/11/2026 su 97 casi: +1,1 punti con un errore standard di 0,4; con 10 formazioni a giornata l'errore
# standard di una finestra è più grande della differenza). Resta come numero; i punti si giudicano sulle rose a sorte di `verifica`.
AVVISANO = ("C2", "C3", "C4")


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


# ---------------------------------------------------------------- totali di tutti i Diari, medie e soglie (per il proprietario)
# i pezzi che si sommano per giornata: quante voci hanno un indicatore (con_*) e le somme
PEZZI = ("voci", "con_s2", "somma_meno_s2", "con_schierata", "somma_meno_schierata", "con_cambi", "cambi", "cambi_sotto_soglia",
         "con_misure", *MISURE)


def _num(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else None


def _aggiungi(r: dict, c: dict) -> None:
    """Aggiunge alla riga di una giornata gli indicatori `c` della voce di un utente (quelli che mancano non contano)."""
    r["voci"] += 1
    mostrata = _num(c.get("punti_consigliata"))
    if mostrata is None:
        return
    if (s2 := _num(c.get("punti_s2"))) is not None:
        r["con_s2"] += 1
        r["somma_meno_s2"] += mostrata - s2
    if (sch := _num(c.get("punti_schierata"))) is not None:
        r["con_schierata"] += 1
        r["somma_meno_schierata"] += mostrata - sch
    if _num(c.get("cambi")) is not None:
        r["con_cambi"] += 1
        r["cambi"] += int(c["cambi"])
        r["cambi_sotto_soglia"] += int(_num(c.get("cambi_sotto_soglia")) or 0)
    if all(_num(c.get(k)) is not None for k in MISURE):
        r["con_misure"] += 1
        for k in MISURE:
            r[k] += int(c[k])


def per_giornata(diari: list[list[dict]]) -> list[dict]:
    """Le voci di tutti i Diari (una lista di voci per utente) sommate per giornata, dalla più vecchia: solo le voci con gli
    indicatori (`consiglio`). Solo numeri: chi ha fatto cosa non resta."""
    somme: dict[tuple[str, int], dict] = {}
    for voci in diari:
        for v in voci:
            c = v.get("consiglio") if isinstance(v, dict) else None
            if not isinstance(c, dict) or not isinstance(v.get("stagione"), str) or not isinstance(v.get("giornata"), int):
                continue
            chiave = (v["stagione"], v["giornata"])
            r = somme.setdefault(chiave, {"stagione": chiave[0], "giornata": chiave[1], **dict.fromkeys(PEZZI, 0)})
            _aggiungi(r, c)
    for r in somme.values():
        r["somma_meno_s2"], r["somma_meno_schierata"] = round(r["somma_meno_s2"], 2), round(r["somma_meno_schierata"], 2)
    return [somme[k] for k in sorted(somme)]


def medie(righe: list[dict]) -> dict:
    """Le medie di più giornate (`per_giornata`), sommando i pezzi: `meno_s2` e `meno_schierata` (punti a giornata della consigliata
    mostrata meno S2 e meno la schierata quando è diversa), `cambi` (cambi a formazione nelle 24 ore prima della scadenza) e i totali
    `cambi_sotto_soglia`, `improbabili`, `con_compagno`, `reparti`, `storte`, `spiegate`; `senza_motivo` = quota dei titolari senza un
    motivo proprio. None = niente da misurare. `verdetto` solo con FINESTRA giornate; allora `regge` dice per ogni indicatore se è
    entro soglia (None = non si può dire) e `fuori` quali non lo sono."""
    t = {k: sum(_num(r.get(k)) or 0 for r in righe) for k in PEZZI}
    con_misure = t["con_misure"] > 0
    m = {"giornate": len(righe), "voci": int(t["voci"]),
         "meno_s2": round(t["somma_meno_s2"] / t["con_s2"], 2) if t["con_s2"] else None,
         "meno_schierata": round(t["somma_meno_schierata"] / t["con_schierata"], 2) if t["con_schierata"] else None,
         "cambi": round(t["cambi"] / t["con_cambi"], 2) if t["con_cambi"] else None,
         "cambi_sotto_soglia": int(t["cambi_sotto_soglia"]) if t["con_cambi"] else None,
         **{k: int(t[k]) if con_misure else None for k in ("improbabili", "con_compagno", "reparti", "storte", "spiegate")},
         "senza_motivo": round(t["senza_motivo"] / t["titolari"], 3) if t["titolari"] else None}
    v = m["verdetto"] = len(righe) >= FINESTRA
    m["regge"] = {
        "C1": None if not v or m["meno_s2"] is None
        else m["meno_s2"] >= SOGLIE["C1"] and (m["meno_schierata"] is None or m["meno_schierata"] >= SOGLIE["C1"]),
        "C2": None if not v or m["cambi_sotto_soglia"] is None else m["cambi_sotto_soglia"] <= SOGLIE["C2"],
        "C3": None if not v or m["con_compagno"] is None else m["con_compagno"] <= SOGLIE["C3"],
        "C4": None if not v or m["senza_motivo"] is None
        else m["storte"] == m["spiegate"] and m["senza_motivo"] <= SOGLIE["C4_senza_motivo"]}
    m["fuori"] = [k for k, ok in m["regge"].items() if ok is False]
    return m


# ---------------------------------------------------------------- avviso al proprietario (come il registro delle giornate)
def _n(x: float, cifre: int = 2, segno: bool = False) -> str:
    return (f"{x:+.{cifre}f}" if segno else f"{x:.{cifre}f}").replace(".", ",")


def testo_avviso(fuori: list[str], m: dict) -> tuple[str, str]:
    """Titolo e testo dell'avviso: solo indicatori e numeri, mai nomi. Solo gli indicatori di `AVVISANO`: C1 non ha la sua riga."""
    righe = []
    if "C2" in fuori and m.get("cambi_sotto_soglia") is not None:
        righe.append(f"• C2 stabilità: {m['cambi_sotto_soglia']} cambi della consigliata nelle 24 ore prima della scadenza per meno "
                     "di 1 punto atteso, senza un titolare diventato fuori o improbabile (devono essere 0)")
    if "C3" in fuori and m.get("con_compagno") is not None:
        righe.append(f"• C3 chi gioca: {m['con_compagno']} titolari sotto il {round(100 * vc.IMPROBABILE_SOTTO)}% con un compagno "
                     f"di ruolo al {round(100 * vc.COMPAGNO_DA)}% o più (devono essere 0)")
    if "C4" in fuori and m.get("senza_motivo") is not None:
        righe.append(f"• C4 perché: scelte che sembrano storte spiegate {m['spiegate']} su {m['storte']}; titolari senza un "
                     f"motivo proprio {round(100 * m['senza_motivo'])}% (tutte spiegate, al massimo 10%)")
    return ("SchieraXI: consiglio di formazione", f"Fuori soglia da 2 giornate di fila, media delle ultime {m.get('giornate')} "
            f"giornate su {m.get('voci')} formazioni (dettagli in Stato dei dati):\n" + "\n".join(righe))


def _lista(x) -> list[str]:
    return [str(k) for k in x] if isinstance(x, list) else []


def _carica(file: Path | None) -> dict:
    try:
        d = json.loads((file or FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def tutti_i_diari() -> list[list[dict]]:
    """Le voci del Diario di ogni utente (con gli account) o dell'utente unico."""
    from . import account, diario
    from .contesto import Contesto
    if not account.multiutente():
        return [list(diario.carica()["giornate"].values())]
    with contextlib.closing(account.apri()) as adb:
        ids = [u["id"] for u in account.elenco(adb)]
    return [list(diario.carica(Contesto.per_utente(i).diario)["giornate"].values()) for i in ids]


def giro(manda: Callable[[str, str], bool], diari: list[list[dict]] | None = None, file: Path | None = None,
         adesso: datetime | None = None) -> dict:
    """Rifà i totali per giornata da tutti i Diari (`diari`: di norma `tutti_i_diari`), segna per ogni giornata gli indicatori fuori
    soglia (media delle FINESTRA giornate fino a lei) e decide l'avviso: da mandare = fuori nell'ultima giornata E in quella prima, e
    non già avvisati mentre restavano fuori (un indicatore rientrato si può avvisare di nuovo). Avvisano solo gli indicatori di
    `AVVISANO`: C1 resta tra i `fuori` della giornata ma non parte e non si segna. `manda(titolo, testo)` vero se è
    partito; se non parte resta da mandare e si riprova al giro dopo. Scrive tutto in `file`.
    Restituisce {giornate, fuori (dell'ultima), avvisato (gli indicatori dell'avviso partito adesso)}."""
    righe = per_giornata(tutti_i_diari() if diari is None else diari)
    for i, r in enumerate(righe):
        r["fuori"] = medie(righe[max(0, i + 1 - FINESTRA): i + 1])["fuori"]
    ultima = righe[-1]["fuori"] if righe else []
    prima = righe[-2]["fuori"] if len(righe) >= 2 else []
    fuori_da_due = set(ultima) & set(prima) & set(AVVISANO)
    avvisati = sorted(set(_lista(_carica(file).get("avvisati"))) & set(ultima) & set(AVVISANO))
    da_avvisare = sorted(fuori_da_due - set(avvisati))
    mandati = da_avvisare if da_avvisare and manda(*testo_avviso(da_avvisare, medie(righe[-FINESTRA:]))) else []
    avvisati = sorted(set(avvisati) | set(mandati))
    scrivi_sicuro(file or FILE, json.dumps({
        "aggiornato": (adesso or datetime.now()).isoformat(timespec="seconds"), "per_giornata": righe[-MOSTRATE:],
        "avvisati": avvisati, "da_avvisare": sorted(set(da_avvisare) - set(mandati))}, ensure_ascii=False))
    return {"giornate": len(righe), "fuori": ultima, "avvisato": mandati}


def riepilogo(file: Path | None = None) -> dict:
    """Per «Stato dei dati» (campo `consiglio`): finestra, soglie, quando sono stati rifatti i totali (`aggiornato`, None = mai), le
    medie delle ultime FINESTRA giornate (come `medie`), gli indicatori già avvisati e una riga per giornata dalla più recente (al
    massimo MOSTRATE) con le sue medie e `fuori`. Solo giornate e numeri."""
    d = _carica(file)
    righe = [r for r in d.get("per_giornata") or [] if isinstance(r, dict)][-MOSTRATE:]
    per = []
    for r in reversed(righe):
        g = medie([r])
        per.append({"stagione": r.get("stagione"), "giornata": r.get("giornata"), "voci": g["voci"],
                    **{k: g[k] for k in ("meno_s2", "meno_schierata", "cambi", "cambi_sotto_soglia", "improbabili", "con_compagno",
                                         "storte", "spiegate", "senza_motivo")},
                    "fuori": _lista(r.get("fuori"))})
    return {"finestra": FINESTRA, "soglie": dict(SOGLIE), "aggiornato": d.get("aggiornato"), **medie(righe[-FINESTRA:]),
            "avvisati": _lista(d.get("avvisati")), "per_giornata": per}
