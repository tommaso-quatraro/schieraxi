"""«Titolare anche se incerto»: titolare sotto il 50% con la riserva dello stesso ruolo sopra l'80% (campo `incerti` di ogni modulo)."""
from fanta import consigli
from fanta.formazione import Giocatore


def g(i, ruolo, p):
    return Giocatore(i, f"G{i}", ruolo, p, 6.0, 6.0)


def test_titolare_incerto_con_riserva_sicura():
    tit = [g(1, "P", 0.95), g(2, "D", 0.35), g(3, "C", 0.9), g(4, "A", 0.45)]
    pan = [g(10, "P", 0.9), g(11, "D", 0.89), g(12, "A", 0.6)]
    assert consigli.incerti(tit, pan) == [{"titolare": 2, "riserva": 11}]      # attaccante: la riserva non è abbastanza sicura


def test_soglie_e_riserve_una_per_titolare():
    tit = [g(1, "D", 0.5), g(2, "D", 0.2), g(3, "D", 0.3)]
    pan = [g(11, "D", 0.81), g(12, "D", 0.8), g(13, "C", 0.99)]
    # 0,5 non è sotto la soglia; il più incerto (2) prende la prima riserva, il secondo (3) la seconda, che non supera l'80%
    assert consigli.incerti(tit, pan) == [{"titolare": 2, "riserva": 11}]
    assert consigli.incerti(tit, []) == []


def test_ogni_modulo_porta_gli_incerti():
    class F:
        modulo, atteso, dev = "3-4-3", 70.0, 5.0
        titolari = [g(2, "D", 0.35)]
        panchina = [g(11, "D", 0.89)]
    m = consigli._moduli([F()])[0]
    assert m["incerti"] == [{"titolare": 2, "riserva": 11}] and m["titolari"] == [2] and m["panchina"] == [11]
