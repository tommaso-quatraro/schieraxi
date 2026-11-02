"""Formazioni delle giornate passate della lega, importate da un file (per esempio lette dagli screenshot di Leghe Fantacalcio).

Un file di importazione ha tre parti, tutte facoltative:
  scelte          la TUA formazione schierata, per giornata di Serie A: {"4": {"modulo", "titolari": [11 id], "panchina": [id in ordine]}}
                  va nello stesso file delle scelte (`dati/scelte.json`) e il Diario la usa per i punti fatti e attesi
  altre_squadre   le formazioni schierate dagli altri: {"4": {"Nome squadra": {"modulo", "titolari", "panchina", "punti"}}}
                  vanno in `dati/formazioni_altre_squadre.json` (chiave "stagione/giornata", poi il nome della squadra)
  calendario      le partite della lega: [{"giornata_lega", "giornata_serie_a", "casa", "trasferta", "gol": [c, t], "punti": [c, t]}]
                  (senza gol e punti = ancora da giocare) in `dati/calendario_lega.json`
I file di `dati/` sono dati personali: non stanno in git. Nei giocatori c'è solo il codice calciatore di Fantacalcio.it."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import scelte
from .percorsi import RADICE, scrivi_sicuro

FILE_ALTRE = RADICE / "dati" / "formazioni_altre_squadre.json"
FILE_CALENDARIO = RADICE / "dati" / "calendario_lega.json"
MAX_BYTE = 1_000_000
MAX_GIORNATE = 60
MAX_SQUADRE = 40
MAX_PARTITE = 2000
MAX_PANCHINA = 20
_MODULO = re.compile(r"^[1-6]-[1-6]-[1-6]$")
_STAGIONE = re.compile(r"^\d{4}-\d{2}$")


def _id(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and 0 < x < 10_000_000


def _giornata(k) -> bool:
    return str(k).isdigit() and 1 <= int(k) <= 60


def _nome(x) -> bool:
    return isinstance(x, str) and 1 <= len(x.strip()) <= 60


def _punti(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 300


def _formazione(f, dove: str, errori: list[str], con_punti: bool = False) -> None:
    if not isinstance(f, dict):
        errori.append(f"{dove}: formazione non valida")
        return
    tit, pan = f.get("titolari"), f.get("panchina", [])
    if not (isinstance(tit, list) and len(tit) == 11 and all(_id(i) for i in tit) and len(set(tit)) == 11):
        errori.append(f"{dove}: servono 11 titolari diversi (codici calciatore)")
        return
    if not (isinstance(pan, list) and len(pan) <= MAX_PANCHINA and all(_id(i) for i in pan) and len(set(pan)) == len(pan)
            and not set(pan) & set(tit)):
        errori.append(f"{dove}: la panchina deve avere giocatori diversi tra loro e dai titolari")
    if not (isinstance(f.get("modulo"), str) and _MODULO.match(f["modulo"])):
        errori.append(f"{dove}: modulo non valido")
    if con_punti and f.get("punti") is not None and not _punti(f["punti"]):
        errori.append(f"{dove}: punti non validi")


def valida(dati) -> list[str]:
    """Le cose che non vanno nel file (lista vuota = si può importare). Niente viene scritto."""
    if not isinstance(dati, dict):
        return ["Il file non è nel formato giusto"]
    errori: list[str] = []
    if not (isinstance(dati.get("stagione"), str) and _STAGIONE.match(dati["stagione"])):
        errori.append("Manca la stagione (per esempio 2026-27)")
    sc = dati.get("scelte") or {}
    if not isinstance(sc, dict) or len(sc) > MAX_GIORNATE:
        errori.append("scelte: formato non valido")
    else:
        for g, f in sc.items():
            if not _giornata(g):
                errori.append(f"scelte: giornata «{str(g)[:10]}» non valida")
            else:
                _formazione(f, f"scelte, giornata {g}", errori)
    al = dati.get("altre_squadre") or {}
    if not isinstance(al, dict) or len(al) > MAX_GIORNATE:
        errori.append("altre_squadre: formato non valido")
    else:
        for g, squadre in al.items():
            if not _giornata(g) or not isinstance(squadre, dict) or len(squadre) > MAX_SQUADRE:
                errori.append(f"altre_squadre: giornata «{str(g)[:10]}» non valida")
                continue
            for nome, f in squadre.items():
                if not _nome(nome):
                    errori.append(f"altre_squadre, giornata {g}: nome squadra non valido")
                else:
                    _formazione(f, f"{nome[:30]}, giornata {g}", errori, con_punti=True)
    cal = dati.get("calendario") or []
    if not isinstance(cal, list) or len(cal) > MAX_PARTITE:
        errori.append("calendario: formato non valido")
    else:
        for i, p in enumerate(cal):
            ok = (isinstance(p, dict) and _giornata(p.get("giornata_lega")) and _giornata(p.get("giornata_serie_a"))
                  and _nome(p.get("casa")) and _nome(p.get("trasferta")))
            if ok and "gol" in p:
                ok = (isinstance(p["gol"], list) and len(p["gol"]) == 2 and all(isinstance(x, int) and 0 <= x <= 30 for x in p["gol"])
                      and isinstance(p.get("punti"), list) and len(p["punti"]) == 2 and all(_punti(x) for x in p["punti"]))
            if not ok:
                errori.append(f"calendario: la partita {i + 1} non è valida")
                break
    return errori


def _leggi(percorso: Path, chiave: str) -> dict:
    try:
        d = json.loads(percorso.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get(chiave), dict) else {chiave: {}}
    except (OSError, ValueError):
        return {chiave: {}}


def altre_squadre(percorso: Path | None = None) -> dict:
    """{"stagione/giornata": {"Squadra": {modulo, titolari, panchina, punti}}}."""
    return _leggi(percorso or FILE_ALTRE, "giornate")["giornate"]


def calendario(percorso: Path | None = None) -> list[dict]:
    try:
        d = json.loads((percorso or FILE_CALENDARIO).read_text(encoding="utf-8"))
        return d["partite"] if isinstance(d, dict) and isinstance(d.get("partite"), list) else []
    except (OSError, ValueError, KeyError):
        return []


def importa(dati: dict, sovrascrivi_scelte: bool = False, file_scelte: Path | None = None, file_altre: Path | None = None,
            file_calendario: Path | None = None) -> dict:
    """Scrive le tre parti del file nei file di dati. Le scelte che l'utente ha già salvato non si toccano (salvo `sovrascrivi_scelte`).
    Le altre squadre e il calendario si aggiornano voce per voce. Solleva ValueError se il file non è valido."""
    errori = valida(dati)
    if errori:
        raise ValueError("; ".join(errori[:5]))
    stagione = dati["stagione"]
    esito = {"scelte": 0, "scelte_gia_presenti": [], "altre_squadre": 0, "partite": 0}
    for g, f in (dati.get("scelte") or {}).items():
        if scelte.leggi(stagione, int(g), file_scelte) and not sovrascrivi_scelte:
            esito["scelte_gia_presenti"].append(int(g))
            continue
        scelte.salva(stagione, int(g), f["titolari"], f["modulo"], file_scelte, tipo="manuale", panchina=f.get("panchina") or None)
        esito["scelte"] += 1
    if dati.get("altre_squadre"):
        percorso = file_altre or FILE_ALTRE
        archivio = _leggi(percorso, "giornate")
        for g, squadre in dati["altre_squadre"].items():
            voce = archivio["giornate"].setdefault(f"{stagione}/{int(g)}", {})
            for nome, f in squadre.items():
                voce[nome.strip()] = {k: f[k] for k in ("modulo", "titolari", "panchina", "punti") if k in f}
                esito["altre_squadre"] += 1
        scrivi_sicuro(percorso, json.dumps(archivio, ensure_ascii=False))
    if dati.get("calendario"):
        percorso = file_calendario or FILE_CALENDARIO
        per_chiave = {(p["stagione"], p["giornata_lega"], p["casa"], p["trasferta"]): p for p in calendario(percorso)}
        for p in dati["calendario"]:
            voce = {"stagione": stagione, "giornata_lega": int(p["giornata_lega"]), "giornata_serie_a": int(p["giornata_serie_a"]),
                    "casa": p["casa"].strip(), "trasferta": p["trasferta"].strip()}
            if "gol" in p:
                voce["gol"], voce["punti"] = p["gol"], p["punti"]
            per_chiave[(stagione, voce["giornata_lega"], voce["casa"], voce["trasferta"])] = voce
            esito["partite"] += 1
        partite = sorted(per_chiave.values(), key=lambda v: (v["stagione"], v["giornata_lega"], v["casa"]))
        scrivi_sicuro(percorso, json.dumps({"partite": partite}, ensure_ascii=False))
    return esito


def importa_file(percorso: Path, **kw) -> dict:
    if percorso.stat().st_size > MAX_BYTE:
        raise ValueError("Il file è troppo grande")
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except ValueError:
        raise ValueError("Il file non è un JSON valido") from None
    return importa(dati, **kw)
