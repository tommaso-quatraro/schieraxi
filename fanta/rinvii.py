"""Partite rinviate: quale regola vale per una giornata e cosa cambia per i giocatori coinvolti.

Una partita della giornata è RINVIATA se non è ancora stata giocata e non sta nel turno (regola unica in turno.py): senza data o
spostata a un recupero, anche settimane dopo. Una partita già recuperata (giocata) non è più rinviata: i voti del recupero
valgono per la sua giornata (Fantacalcio.it li mette lì).

Cosa fa la lega lo dicono le regole (mai il codice): `partite_rinviate` (regola generale) e `rinvii_giornate` (eccezione decisa
volta per volta per una giornata, che vince sulla regola generale).
- `aspetta`: la lega aspetta il recupero e conta il voto preso lì. I numeri del modello non cambiano (per il recupero non ci
  sono ancora probabili: la probabilità di giocare viene dalle presenze recenti); il «perché» lo dice.
- `senza_voto`: i giocatori restano senza voto: probabilità di voto 0, la formazione mette chi gioca davvero.
- `voto_ufficio`: tutti prendono il voto fisso `voto_ufficio_rinviate` (fantavoto = voto, niente bonus né malus), sicuro.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Iterable

import pandas as pd

from . import turno
from .frasi import F, Frase, di
from .regole import MODI_RINVIO, Regole, da_dict, serie_a_a_lega

# colonne che con il voto d'ufficio non hanno senso (niente bonus né malus): a zero, così nessuna schermata mostra gol attesi
_A_ZERO = ("e_gol", "e_assist", "e_rigori", "p_gol", "p_assist", "p_giallo", "p_rosso", "p_imbattuto", "gol_subiti")


def chiave(stagione: str, giornata: int) -> str:
    """La chiave dell'eccezione in `regole.rinvii_giornate`: stagione e giornata di Serie A, come per le scelte."""
    return f"{stagione}/{int(giornata)}"


def regola(regole: Regole, stagione: str, giornata: int) -> dict:
    """La regola che vale per la giornata: {modo, valore (solo con il voto d'ufficio, se no None), predefinito, eccezione}."""
    predefinito = getattr(regole, "partite_rinviate", "aspetta")
    eccezione = (getattr(regole, "rinvii_giornate", None) or {}).get(chiave(stagione, giornata))
    modo = eccezione if eccezione in MODI_RINVIO else predefinito
    valore = float(getattr(regole, "voto_ufficio_rinviate", 6.0)) if modo == "voto_ufficio" else None
    return {"modo": modo, "valore": valore, "predefinito": predefinito, "eccezione": eccezione in MODI_RINVIO}


def con_eccezione(regole: Regole, stagione: str, giornata: int, modo: str | None) -> Regole:
    """Nuove regole con l'eccezione della giornata impostata (`modo`) o tolta (None, oppure uguale alla regola generale).
    Le eccezioni delle altre stagioni non servono più e si tolgono (così l'elenco non cresce per sempre)."""
    if modo is not None and modo not in MODI_RINVIO:
        raise ValueError(f"Scegli una di queste: {', '.join(MODI_RINVIO)}")
    dati = asdict(regole)
    eccezioni = {k: v for k, v in (dati.get("rinvii_giornate") or {}).items() if k.startswith(f"{stagione}/")}
    k = chiave(stagione, giornata)
    eccezioni.pop(k, None)
    if modo is not None and modo != dati.get("partite_rinviate"):
        eccezioni[k] = modo
    dati["rinvii_giornate"] = eccezioni
    return da_dict(dati)


def _data(testo) -> datetime | None:
    if testo is None or (isinstance(testo, float) and pd.isna(testo)):
        return None
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " ")) if str(testo).strip() else None
    except ValueError:
        return None


def fuori_turno(partite: Iterable[dict]) -> list[dict]:
    """Le partite di una giornata ({data, ...}) fuori dal turno o senza data: rinviate, giocate o no (una già recuperata ha la data
    del recupero). Se il calendario non ha date (inizio stagione) nessuna."""
    partite = list(partite)
    inizio = turno.inizio(_data(p.get("data")) for p in partite)
    if inizio is None:
        return []
    return [p for p in partite if (d := _data(p.get("data"))) is None or not turno.nel_turno(d, inizio)]


def rinviate(partite: Iterable[dict]) -> list[dict]:
    """Le partite rinviate tra quelle di una giornata ({data, giocata, ...}) ancora da recuperare: fuori dal turno e non giocate."""
    return [p for p in fuori_turno(partite) if not bool(p.get("giocata"))]


def _della_giornata(partite: pd.DataFrame, stagione: str, giornata: int) -> list[dict]:
    if "data" not in partite.columns:            # tabella senza date (prove, dati vecchi): nessuna partita fuori dal turno
        return []
    sel = partite[(partite["stagione"] == stagione) & (partite["giornata"] == giornata)]
    return sel[["id", "data", "giocata"]].to_dict("records")


def id_rinviate(partite: pd.DataFrame, stagione: str, giornata: int) -> set[int]:
    """Gli id delle partite rinviate (da recuperare) di una giornata, dalla tabella delle partite del modello (`Dati.partite`)."""
    return {int(p["id"]) for p in rinviate(_della_giornata(partite, stagione, giornata))}


def id_fuori_turno(partite: pd.DataFrame, stagione: str, giornata: int) -> set[int]:
    """Gli id delle partite fuori dal turno di una giornata, anche già recuperate (per il Diario delle giornate finite)."""
    return {int(p["id"]) for p in fuori_turno(_della_giornata(partite, stagione, giornata))}


def voti_lega(gioca: dict[int, bool], fv: dict[int, float], voto: dict[int, float], coinvolti: Iterable[int], r: dict) -> None:
    """Il Diario (giornata finita): i voti che la lega ha contato davvero per chi aveva la partita rinviata. Con `aspetta` quelli
    del recupero (non cambia niente); con `senza_voto` nessuno (entra la riserva); con `voto_ufficio` il voto fisso. Cambia i
    dizionari passati (solo per gli id `coinvolti` che ci sono)."""
    if r["modo"] == "aspetta":
        return
    v = float(r["valore"] if r["valore"] is not None else 6.0)
    for i in coinvolti:
        if i not in gioca:
            continue
        if r["modo"] == "senza_voto":
            gioca[i], fv[i], voto[i] = False, 0.0, 0.0
        else:
            gioca[i], fv[i], voto[i] = True, v, v


def _quando(data) -> str | None:
    d = _data(data)
    return f"{d.day}/{d.month}" if d else None


def frase(modo: str, valore: float | None, data_recupero=None) -> Frase:
    """Il motivo per l'utente (uguale nel «perché» e nei motivi della scheda): testo italiano con la chiave `rinvio.*` per
    tradurlo (fanta/frasi.py)."""
    if modo == "senza_voto":
        return F("rinvio.senza_voto")
    if modo == "voto_ufficio":
        v = float(valore if valore is not None else 6.0)
        return F("rinvio.voto_ufficio", voto=int(v) if v.is_integer() else v)        # «6», «5,5»
    quando = _quando(data_recupero)
    return F("rinvio.aspetta", data=quando) if quando else F("rinvio.aspetta_senza_data")


def applica(p: pd.DataFrame, ids: set[int], r: dict) -> pd.DataFrame:
    """Le previsioni con la regola dei rinvii applicata ai giocatori delle partite `ids`. Aggiunge la colonna `rinvio` (il modo, o
    None per chi non è coinvolto). Restituisce una copia: le previsioni di partenza non cambiano."""
    p = p.copy()
    coinvolti = p["partita"].isin(ids) if ids else pd.Series(False, index=p.index)
    p["rinvio"] = pd.Series([r["modo"] if c else None for c in coinvolti], index=p.index, dtype=object)
    if not coinvolti.any():
        return p
    if r["modo"] == "senza_voto":
        p.loc[coinvolti, ["p_voto", "atteso"]] = 0.0
    elif r["modo"] == "voto_ufficio":
        v = float(r["valore"] if r["valore"] is not None else 6.0)
        p.loc[coinvolti, ["mu", "mu_voto", "atteso"]] = v
        p.loc[coinvolti, ["p_voto", "quota_titolare"]] = 1.0
        p.loc[coinvolti, [c for c in _A_ZERO if c in p.columns]] = 0.0
    return p


def perche(p: pd.DataFrame, r: dict, massimo: int) -> pd.Series:
    """`perche_numero` con il motivo del rinvio: per chi aspetta il recupero va in cima agli altri motivi (i numeri sono quelli di
    sempre); con senza voto o voto d'ufficio è l'unico motivo (i pezzi del fantavoto atteso non valgono più)."""
    out = p["perche_numero"].copy()
    for i in p.index[p["rinvio"].notna()]:
        testo = frase(r["modo"], r["valore"], p.at[i, "data_partita"])
        m = {"chiave": "rinvio", "testo": testo, "frase": di(testo), "effetto": None}
        resto = list(out.at[i] or []) if r["modo"] == "aspetta" else []
        out.at[i] = [m] + resto[:max(0, massimo - 1)]
    return out


def blocco_oggi(regole: Regole, stagione: str, giornata: int | None, partite: list[dict], mie: list[dict]) -> dict | None:
    """Il campo `rinvio` di GET /api/oggi: None se nella giornata non c'è una partita rinviata. `partite` con `stato` (fasi.py:
    calendario e diretta), `mie` = {id, nome, ruolo, squadra} dei giocatori della mia rosa."""
    if giornata is None:
        return None
    rinv = [p for p in partite if p.get("stato") == "rinviata"]
    if not rinv:
        return None
    squadre = {s for p in rinv for s in (p.get("casa"), p.get("trasferta")) if s}
    r = regola(regole, stagione, giornata)
    return {"stagione": stagione, "giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole), **r,
            "modi": list(MODI_RINVIO), "voto_ufficio": float(getattr(regole, "voto_ufficio_rinviate", 6.0)),
            "partite": [{"casa": p.get("casa"), "trasferta": p.get("trasferta"), "data": p.get("data")} for p in rinv],
            "miei": [g for g in mie if g.get("squadra") in squadre]}
