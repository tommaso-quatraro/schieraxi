"""Aree del repository (aree.json): da un file alla sua area, da un insieme di file al gruppo del tetto delle PR."""
from __future__ import annotations

import re
from functools import lru_cache

import comune


@lru_cache(maxsize=1)
def carica() -> dict:
    return comune.leggi_json("aree.json")


@lru_cache(maxsize=256)
def _regex(percorso: str) -> re.Pattern:
    """«**» = qualunque cosa (anche «/»); «*» e «?» non attraversano «/»."""
    parti = re.split(r"(\*\*|\*|\?)", percorso)
    tradotto = {"**": ".*", "*": "[^/]*", "?": "[^/]"}
    return re.compile("".join(tradotto.get(p, re.escape(p)) for p in parti) + r"\Z")


def corrisponde(file: str, percorso: str) -> bool:
    return bool(_regex(percorso).match(file))


def area_di(file: str) -> str | None:
    for area in carica()["aree"]:
        if any(corrisponde(file, p) for p in area["percorsi"]):
            return area["nome"]
    return None


def _gruppo_area(area: str) -> str | None:
    for nome, g in carica()["gruppi"].items():
        if area in g["aree"]:
            return nome
    return None


def gruppo_di(file: list[str]) -> str | None:
    """Gruppo del tetto per una PR: None se tocca solo aree neutre (documenti, test)."""
    dati = carica()
    gruppi = {_gruppo_area(a) for a in (area_di(f) for f in file) if a and a not in dati["neutre"]} - {None}
    if not gruppi:
        return None
    if dati["gruppo_vince"] in gruppi:
        return dati["gruppo_vince"]
    return sorted(gruppi)[0]


def tetto(gruppo: str) -> int:
    return carica()["gruppi"][gruppo]["tetto"]


def _aree_delle_etichette(etichette: list[str]) -> list[dict]:
    nomi = set(etichette)
    return [a for a in carica()["aree"] if a["nome"] in nomi and a["nome"] not in carica()["neutre"]]


def percorsi_per_etichette(etichette: list[str]) -> tuple[list[str], list[str]]:
    """(Puoi toccare, NON toccare) per un brief. Vuoti se nessuna etichetta è un'area."""
    dati = carica()
    scelte = _aree_delle_etichette(etichette)
    if not scelte:
        return [], []
    nomi = {a["nome"] for a in scelte} | set(dati["neutre"])
    tocca = [p for a in dati["aree"] if a["nome"] in nomi for p in a["percorsi"]]
    non_tocca = [p for a in dati["aree"] if a["nome"] not in nomi and a["nome"] != "altro" for p in a["percorsi"]]
    return tocca, non_tocca


def agente_per_etichette(etichette: list[str]) -> str | None:
    scelte = _aree_delle_etichette(etichette)
    return scelte[0]["agente"] if scelte else None
