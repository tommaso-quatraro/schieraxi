"""Regole confermate dall'utente (31/10/2026) per la sua lega, lette dal file di regole (la lega d'esempio ha le stesse)."""
from pathlib import Path

from fanta import punteggio
from fanta.regole import Regole, carica

LEGA = Path(__file__).resolve().parent.parent / "lega" / "esempio" / "regole.json"


def test_bonus_confermati_dalla_lega():
    b = carica(LEGA).bonus
    assert b.rigore_sbagliato == -1.0
    assert b.autogol == -2.0
    assert b.ammonizione == -0.5
    assert b.espulsione == -1.0


def test_default_coincide_con_la_lega():
    assert Regole().bonus.rigore_sbagliato == carica(LEGA).bonus.rigore_sbagliato


def test_ramos_g_con_rigore_segnato_e_sbagliato():
    # Giornata 7 2026-27: voto 6,5, un rigore segnato e uno sbagliato -> 8,5 (prima 6,5 con -3)
    riga = {"voto_red": 6.5, "rig_segnati": 1, "rig_sbagliati": 1}
    assert punteggio.fantavoto(riga, "A", carica(LEGA)) == 8.5


def test_de_bruyne_con_rigore_sbagliato():
    # Giornata 7 2026-27: voto 5,0 e un rigore sbagliato -> 4,0 con -1 (2,0 con il vecchio -3)
    riga = {"voto_red": 5.0, "rig_sbagliati": 1}
    assert punteggio.fantavoto(riga, "C", carica(LEGA)) == 4.0
