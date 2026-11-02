"""«Sotto il cofano»: i testi (fanta/contenuti/sotto-il-cofano.json) più i numeri attuali, letti da cose già calcolate.

Il file si legge una volta e si rilegge solo se cambia (data di modifica). Niente calcoli pesanti: i numeri `app.*` vengono dal file
dell'affidabilità già salvato, calibrazione e fonti in ombra da letture rapide dell'archivio (le stesse dello «Stato dei dati»).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from . import stato_dati
from .lingua import EN

FILE = Path(__file__).parent / "contenuti" / "sotto-il-cofano.json"
FORMATO = 1
LIVELLI = ("base", "nerd")
SCHERMATE = ("oggi", "formazione", "scambi", "mercato", "lega", "regole", "crediti", "stato-dati", "diario", "giocatore", "novita")
CAMPI_PRIVATI = ("fonte_codice",)           # servono a chi controlla i testi, non vanno ai client
MESSAGGIO_NON_DISPONIBILE = "I testi di «Sotto il cofano» non sono disponibili in questo momento"
# chiave del numero attuale -> chiave della sintesi dell'affidabilità
_NUMERI_APP = {"app.errore_modello": "errore_modello", "app.errore_fantamedia": "errore_fantamedia", "app.punti_modello": "punti_modello",
               "app.punti_fantamedia": "punti_fantamedia", "app.punti_perfetta": "punti_perfetta"}


class TestiNonDisponibili(Exception):
    pass


def controlla(d: object) -> list[str]:
    """Elenco dei problemi del contenuto (vuoto = a posto)."""
    if not isinstance(d, dict):
        return ["il file non è un oggetto"]
    guai = []
    if d.get("formato") != FORMATO:
        guai.append("formato sconosciuto")
    voci = (((d.get("misure") or {}).get("riferimento") or {}).get("voci"))
    if not isinstance(voci, dict):
        guai.append("mancano le misure di riferimento")
        voci = {}
    visti = set()
    for s in d.get("sezioni") or []:
        sid = s.get("id")
        if not sid or sid in visti:
            guai.append(f"id mancante o doppio: {sid}")
        visti.add(sid)
        if s.get("livello") not in LIVELLI:
            guai.append(f"livello non valido in {sid}")
        guai += [f"numero sconosciuto in {sid}: {k}" for k in s.get("numeri") or [] if k not in voci]
        guai += [f"schermata sconosciuta in {sid}: {r.get('schermata')}" for r in s.get("rimandi") or [] if r.get("schermata") not in SCHERMATE]
    if not d.get("sezioni"):
        guai.append("nessuna sezione")
    return guai


_cache: dict = {}            # lingua -> (chiave del file, testi)
_blocco = threading.Lock()


def file_inglese(p: Path) -> Path:
    """Le traduzioni stanno accanto al file italiano: `sotto-il-cofano.json` -> `sotto-il-cofano.en.json`."""
    return p.with_name(p.stem + ".en.json")


def traduci(d: dict, en: dict) -> dict:
    """Copia di `d` (italiano) con i testi presi da `en`. Numeri, id, livelli e schermate restano quelli italiani: la traduzione
    contiene solo le parole (sezioni per id, glossario e rimandi nello stesso ordine). Quello che manca resta in italiano."""
    out = dict(d)
    for k in ("titolo", "sottotitolo", "livelli", "introduzione"):
        if k in en:
            out[k] = en[k]
    rif_en = ((en.get("misure") or {}).get("riferimento")) or {}
    rif = dict(d["misure"]["riferimento"])
    rif.update({k: rif_en[k] for k in ("come", "nota") if k in rif_en})
    rif["voci"] = {k: {**v, **(rif_en.get("voci") or {}).get(k, {})} for k, v in rif["voci"].items()}
    out["misure"] = {**d["misure"], "riferimento": rif}
    sezioni = []
    for s in d["sezioni"]:
        e = (en.get("sezioni") or {}).get(s.get("id"))
        if e:
            s = dict(s)
            for k in ("titolo", "paragrafi", "formula"):
                if k in e:
                    s[k] = e[k]
            if s.get("esempio") and e.get("esempio"):
                s["esempio"] = {**s["esempio"], **e["esempio"]}
            etichette = e.get("rimandi")
            if etichette and len(etichette) == len(s.get("rimandi") or []):
                s["rimandi"] = [{**r, "etichetta": x} for r, x in zip(s["rimandi"], etichette)]
        sezioni.append(s)
    out["sezioni"] = sezioni
    gl_en = en.get("glossario") or []
    if len(gl_en) == len(d.get("glossario") or []):
        out["glossario"] = gl_en
    return out


def contenuto(percorso: Path | None = None, lingua: str = "it") -> dict:
    """I testi, senza i campi privati, in italiano o in inglese (se manca la traduzione: italiano).
    TestiNonDisponibili se il file italiano manca o non è valido."""
    p = percorso or FILE
    en = file_inglese(p) if lingua == EN else None
    try:
        st = p.stat()
        chiave = [str(p), st.st_mtime_ns, st.st_size]   # la sola data può coincidere tra due scritture ravvicinate
        if en is not None:
            try:
                se = en.stat()
                chiave += [se.st_mtime_ns, se.st_size]
            except OSError:
                en = None
    except OSError as e:
        raise TestiNonDisponibili() from e
    chiave = tuple(chiave)
    with _blocco:
        presente = _cache.get(lingua)
        if presente and presente[0] == chiave:
            return presente[1]
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise TestiNonDisponibili() from e
        if controlla(d):
            raise TestiNonDisponibili()
        d["sezioni"] = [{k: v for k, v in s.items() if k not in CAMPI_PRIVATI} for s in d["sezioni"]]
        if en is not None:
            try:
                d = traduci(d, json.loads(en.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass                                   # traduzione rotta: meglio i testi italiani che nessun testo
        _cache[lingua] = (chiave, d)
        return d


def attuali(db: sqlite3.Connection, stagione: str, aff: dict) -> dict:
    """Numeri di adesso: solo medie e conteggi, nessun dato di rose o giocatori."""
    aff = aff or {}
    sint = aff.get("sintesi") or {}
    voci = {}
    for chiave, campo in _NUMERI_APP.items():
        if sint.get(campo) is not None:
            voci[chiave] = {"valore": sint[campo], "aggiornato": aff.get("calcolato")}
    cal = stato_dati.calibrazione(db, stagione)
    ombra = stato_dati.ombra(db)
    return {
        "voci": voci,
        "affidabilita": ({"giornate": sint.get("giornate"), "ultima": aff.get("ultima"), "calcolato": aff.get("calcolato"), "sintesi": sint}
                         if sint else None),
        "calibrazione": {**cal, "fattori": stato_dati.fattori_da(cal)},
        "ombra": {"partite_extra": ombra["partite_extra"]},
    }


def costruisci(db: sqlite3.Connection, stagione: str, aff: dict, percorso: Path | None = None, lingua: str = "it") -> dict:
    d = contenuto(percorso, lingua)
    ris = {k: v for k, v in d.items() if k != "misure"}
    ris["misure"] = {"riferimento": d["misure"]["riferimento"], "attuali": attuali(db, stagione, aff)}
    return ris
