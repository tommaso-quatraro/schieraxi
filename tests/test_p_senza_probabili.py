"""p_voto senza probabili formazioni: calibrata (chi ha giocato tutte le ultime partite non è più «98%»)."""
from fanta import modello
from fanta.modello import p_senza_probabili


def test_sempre_presente_non_e_piu_quasi_certo():
    p = p_senza_probabili(1.0, 1.0, 1.0, 0.75, False)
    assert 0.85 <= p <= 0.93           # misurato: chi ha preso voto in tutte le ultime 6 gioca circa 9 volte su 10


def test_chi_non_gioca_da_settimane_resta_basso():
    assert p_senza_probabili(0.0, 0.0, 0.0, 0.25, False) < 0.12


def test_cresce_con_ogni_quota():
    base = (0.5, 0.5, 0.5, 0.5)
    for i in range(4):
        piu = list(base)
        piu[i] = 0.9
        assert p_senza_probabili(*piu, False) > p_senza_probabili(*base, False)


def test_portiere_titolare_sopra_e_riserva_sotto():
    assert p_senza_probabili(1.0, 1.0, 1.0, 0.75, True) > p_senza_probabili(1.0, 1.0, 1.0, 0.75, False)
    assert p_senza_probabili(0.0, 0.0, 0.0, 0.25, True) < p_senza_probabili(0.0, 0.0, 0.0, 0.25, False)


def test_pesi_solo_nella_tabella():
    vecchi = dict(modello.CALIBRAZIONE_SENZA_PROBABILI)
    try:
        modello.CALIBRAZIONE_SENZA_PROBABILI.update({k: 0.0 for k in vecchi})
        assert p_senza_probabili(1.0, 1.0, 1.0, 1.0, True) == 0.5
    finally:
        modello.CALIBRAZIONE_SENZA_PROBABILI.update(vecchi)
