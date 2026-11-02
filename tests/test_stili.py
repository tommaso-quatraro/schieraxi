"""Stili della formazione: preset completi (profilo di rischio + preferenza di modulo + testo di una riga)."""
import pytest

from fanta import formazione as fz
from fanta.regole import Regole


def G(id, ruolo, p=1.0, mu=6.0, voto=6.0):
    return fz.Giocatore(id, f"g{id}", ruolo, p, mu, voto)


def _rosa_pari():
    """Tutti uguali (stessi punti, sempre in campo): ogni modulo vale lo stesso, decide solo l'inclinazione dello stile."""
    return ([G(1, "P"), G(2, "P")] + [G(10 + i, "D") for i in range(6)] + [G(30 + i, "C") for i in range(6)]
            + [G(50 + i, "A") for i in range(4)])


def test_inclinazione_sposta_il_modulo_ma_non_i_punti():
    rosa = _rosa_pari()
    base = fz.migliore(rosa, Regole(), 50)
    neutra = fz.migliore(rosa, Regole(), 50, inclinazione=(0.0, 0.0))
    assert neutra.modulo == base.modulo and neutra.atteso == base.atteso          # (0, 0) = comportamento di prima
    prudente = fz.migliore(rosa, Regole(), 50, inclinazione=(0.5, 0.0))
    audace = fz.migliore(rosa, Regole(), 50, inclinazione=(0.0, 0.5))
    assert prudente.modulo.startswith("5") and audace.modulo.endswith("3")
    assert prudente.atteso == pytest.approx(audace.atteso, abs=1e-6)               # a punti pari cambia solo il modulo


def test_stili_sono_preset_completi_e_equilibrata_non_cambia():
    assert [s[0] for s in fz.LIVELLI_RISCHIO] == [-2, -1, 0, 1, 2]
    for _rischio, nome, _peso, inclinazione, descrizione in fz.LIVELLI_RISCHIO:
        assert nome and len(descrizione) > 20 and len(inclinazione) == 2
    eq = next(s for s in fz.LIVELLI_RISCHIO if s[0] == 0)
    assert eq[2] == fz.PESO_BASE and eq[3] == (0.0, 0.0)
    # prudenti: solo difensori in più; audaci: solo attaccanti in più
    assert all(s[3][0] > 0 and s[3][1] == 0 for s in fz.LIVELLI_RISCHIO if s[0] < 0)
    assert all(s[3][1] > 0 and s[3][0] == 0 for s in fz.LIVELLI_RISCHIO if s[0] > 0)
