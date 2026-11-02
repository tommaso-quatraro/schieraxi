"""Fantavoto secondo le regole della MIA lega (non quello standard di Fantacalcio.it) e modificatore difesa."""
from __future__ import annotations

from functools import lru_cache

from .regole import Regole, modulo_in_numeri

COLONNA_VOTO = {"redazione": "voto_red", "statistico": "voto_stat", "italia": "voto_ita"}


def fantavoto(r: dict, ruolo: str, regole: Regole) -> float | None:
    """r: una riga della tabella voti. None se senza voto.

    Attenzione: in Fantacalcio.it "gol" esclude i rigori, che sono in rig_segnati (bonus rigore_segnato).
    """
    voto = r.get(COLONNA_VOTO[regole.fonte_voto])
    if voto is None:
        return None
    b = regole.bonus
    fv = (voto + r.get("gol", 0) * b.gol[ruolo] + r.get("rig_segnati", 0) * b.rigore_segnato
          + r.get("assist", 0) * b.assist + r.get("rig_parati", 0) * b.rigore_parato
          + r.get("rig_sbagliati", 0) * b.rigore_sbagliato + r.get("autogol", 0) * b.autogol
          + r.get("ammonizioni", 0) * b.ammonizione + r.get("espulsioni", 0) * b.espulsione
          + r.get("mvp", 0) * b.mvp)
    if ruolo == "P":
        gs = r.get("gol_subiti", 0)
        fv += gs * b.gol_subito_portiere + (b.portiere_imbattuto if gs == 0 else 0)
    return fv


def modificatore_difesa(voto_portiere: float | None, voti_difensori: list[float], regole: Regole) -> float:
    """Bonus se in campo ci sono almeno min_difensori difensori con voto: media di portiere + 3 migliori difensori."""
    m = regole.modificatore_difesa
    if not m.attivo or voto_portiere is None or len(voti_difensori) < m.min_difensori:
        return 0.0
    media = (voto_portiere + sum(sorted(voti_difensori, reverse=True)[:3])) / 4
    bonus = 0.0
    for soglia, valore in sorted(m.soglie):
        if media >= soglia:
            bonus = valore
    return bonus


@lru_cache(maxsize=64)
def _moduli_ammessi(moduli: tuple[str, ...]) -> frozenset[tuple[int, int, int]]:
    return frozenset(modulo_in_numeri(m) for m in moduli)


def modulo_valido(d: int, c: int, a: int, regole: Regole) -> bool:
    return (d, c, a) in _moduli_ammessi(tuple(regole.moduli))
