"""«Titolare anche se incerto»: titolare sotto il 50% e la riserva dello stesso ruolo che gioca più dell'80%, se in panchina c'è
(campo `incerti` di ogni modulo)."""
from fanta import consigli
from fanta.formazione import Giocatore


def g(i, ruolo, p):
    return Giocatore(i, f"G{i}", ruolo, p, 6.0, 6.0)


def test_titolare_incerto_con_riserva_sicura():
    tit = [g(1, "P", 0.95), g(2, "D", 0.35), g(3, "C", 0.9), g(4, "A", 0.45)]
    pan = [g(10, "P", 0.9), g(11, "D", 0.89), g(12, "A", 0.6)]
    # attaccante: in panchina nessuno del suo ruolo gioca più dell'80%, e si dice (riserva = None)
    assert consigli.incerti(tit, pan) == [{"titolare": 2, "riserva": 11}, {"titolare": 4, "riserva": None}]


def test_la_riserva_e_la_prima_sicura_nell_ordine_della_panchina():
    """Revisione di #612: la panchina è in ordine di fantavoto atteso, quindi la prima riserva del ruolo è spesso quella che gioca
    meno. La riga deve nominare la prima che gioca quasi di sicuro, non fermarsi alla prima del ruolo."""
    tit = [g(2, "D", 0.35)]
    pan = [g(10, "P", 0.99), g(11, "D", 0.6), g(12, "D", 0.85), g(13, "D", 0.95)]
    assert consigli.incerti(tit, pan) == [{"titolare": 2, "riserva": 12}]


def test_soglie_e_riserve_una_per_titolare():
    tit = [g(1, "D", 0.5), g(2, "D", 0.2), g(3, "D", 0.3)]
    pan = [g(11, "D", 0.81), g(12, "D", 0.8), g(13, "C", 0.99)]
    # 0,5 non è sotto la soglia; il più incerto (2) prende la riserva sicura, per il secondo (3) non ne resta una (0,8 non basta)
    assert consigli.incerti(tit, pan) == [{"titolare": 2, "riserva": 11}, {"titolare": 3, "riserva": None}]
    assert consigli.incerti(tit, []) == [{"titolare": 2, "riserva": None}, {"titolare": 3, "riserva": None}]
    # due riserve sicure: una a testa, nell'ordine della panchina
    assert consigli.incerti(tit, pan + [g(14, "D", 0.9)]) == [{"titolare": 2, "riserva": 11}, {"titolare": 3, "riserva": 14}]


def test_ogni_modulo_porta_gli_incerti():
    class F:
        modulo, atteso, dev = "3-4-3", 70.0, 5.0
        titolari = [g(2, "D", 0.35)]
        panchina = [g(11, "D", 0.89)]
    m = consigli._moduli([F()])[0]
    assert m["incerti"] == [{"titolare": 2, "riserva": 11}] and m["titolari"] == [2] and m["panchina"] == [11]
