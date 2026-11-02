"""Scambi N contro M con conguaglio: analisi completa, rosa valida, crediti, ricerca automatica con budget."""
import pytest

from fanta import scambi, scambi_multi
from fanta.regole import Regole

from test_scambi import REGOLE, TAB, _rose, _valori

V = _valori(TAB)


def analizza(do, ricevo, **k):
    return scambi_multi.analizza_completo(V, REGOLE, k.pop("rose", None) or _rose(), "A", "B", do, ricevo, **k)


def test_uno_contro_uno_coincide_con_l_analisi_di_sempre():
    vecchia = scambi.analizza(V, REGOLE, _rose(), "A", "B", [10], [31]).come_dict(V)
    nuova = analizza([10], [31])
    assert nuova["formato"] == "1v1" and nuova["completo"] is True
    for campo in ("guadagno_mio", "guadagno_loro", "per_giornata_mio", "reparti", "percentuale_mio"):
        assert nuova[campo] == vecchia[campo]


def test_due_contro_due_conviene_a_entrambi():
    vecchia = scambi.analizza(V, REGOLE, _rose(), "A", "B", [12, 9], [32, 30])
    d = analizza([12, 9], [32, 30])
    assert d["formato"] == "2v2" and d["valido"] is True and d["problemi"] == []
    assert d["guadagno_mio"] == pytest.approx(vecchia.guadagno_mio, abs=0.01) and d["guadagno_mio"] > 0
    assert d["giudizio"]["chi"] == "entrambi" and d["giudizio"]["spiegazione"]
    assert set(d["rose"]) == {"mio", "loro"} and d["rose"]["mio"]["valida"] and d["rose"]["mio"]["modulo"] == "4-4-2"


def test_due_contro_uno_con_rose_che_hanno_posto():
    # A dà un attaccante e un centrocampista, riceve un centrocampista: A resta a 11 giocatori, B a 13, tutti nei limiti
    d = analizza([12, 9], [30])
    assert d["formato"] == "2v1" and d["n_do"] == 2 and d["n_ricevo"] == 1
    assert d["valido"] is True
    assert d["rose"]["mio"]["conteggio"] == {"P": 1, "D": 4, "C": 4, "A": 2}
    assert d["rose"]["loro"]["conteggio"] == {"P": 1, "D": 4, "C": 5, "A": 3}
    assert "panchina" in d and set(d["panchina"]["mio"]) == {"prima", "dopo", "variazione"}


def test_tre_contro_tre_e_il_massimo_per_lato():
    d = analizza([6, 7, 12], [26, 27, 32])
    assert d["formato"] == "3v3" and len(d["do"]) == 3
    with pytest.raises(ValueError, match="Al massimo 4"):
        analizza([2, 3, 4, 5, 6], [22, 23, 24, 25, 26])
    d4 = analizza([2, 3, 4, 5], [22, 23, 24, 25])
    assert d4["formato"] == "4v4"


def test_rosa_non_valida_segnalata_con_il_motivo():
    # A dà due difensori e riceve un attaccante: ne avrebbe 4 su 3 e solo 2 difensori per un 4-4-2
    d = analizza([2, 3], [31])
    assert d["valido"] is False
    testo = " ".join(d["problemi"])
    assert "attaccanti su un massimo di 3" in testo and "non si potrebbe schierare nessun modulo" in testo
    assert "difensori su un massimo di 5" in testo            # anche B ne riceverebbe troppi
    assert d["rose"]["mio"]["valida"] is False and d["rose"]["loro"]["valida"] is False
    assert d["giudizio"]["testo"].startswith("Così com'è lo scambio non si può fare") and "solo i punti" in d["giudizio"]["testo"]


def test_la_rosa_oltre_il_massimo_si_valuta_liberando_i_meno_forti():
    rose = _rose()
    d = analizza([12], [31], rose=rose)          # 1 contro 1: invariato
    assert d["valido"] is True
    d2 = analizza([12], [31, 32])                # A riceve 2 attaccanti e ne dà 1 -> 4 su un massimo di 3
    assert d2["valido"] is False and "ne andrebbe liberato 1" in " ".join(d2["problemi"])
    assert d2["rose"]["mio"]["problemi"] and d2["rose"]["loro"]["problemi"]       # B resta con un solo attaccante: ne servono 2
    # la rosa si valuta già sistemata (A libera l'attaccante in più, il meno forte): vale come il 1 contro 1 con uno dei due
    assert d2["valore_rosa"]["mio"]["dopo"] == analizza([12], [31])["valore_rosa"]["mio"]["dopo"]


def test_scambio_a_somma_zero():
    # due portieri identici: niente cambia per nessuno
    d = analizza([1], [21])
    assert d["guadagno_mio"] == 0 and d["guadagno_loro"] == 0
    assert d["giudizio"]["chi"] == "poco"


def test_giudizio_conviene_a_te_a_lui_o_nessuno():
    soglia = scambi.SOGLIA
    f = scambi_multi._verdetto
    assert f(2, 2, True, soglia)["chi"] == "entrambi"
    assert f(2, 0, True, soglia)["chi"] == "te" and "può anche accettare" in f(2, 0, True, soglia)["testo"]
    assert "difficile che accetti" in f(2, -2, True, soglia)["testo"]
    assert f(0, 2, True, soglia)["chi"] == "lui"
    assert f(-2, 2, True, soglia)["chi"] == "lui"
    assert f(-2, -2, True, soglia)["chi"] == "nessuno"
    assert f(-2, 0, True, soglia)["chi"] == "nessuno" and "a te" in f(-2, 0, True, soglia)["testo"]


def test_giudizio_e_motivi_in_inglese_a_richiesta():
    soglia = scambi.SOGLIA
    f = scambi_multi._verdetto
    for args, chi in (((2, 2), "entrambi"), ((2, 0), "te"), ((2, -2), "te"), ((0, 2), "lui"), ((-2, 2), "lui"), ((0, 0), "poco"), ((-2, -2), "nessuno"), ((-2, 0), "nessuno")):
        it, en = f(*args, True, soglia), f(*args, True, soglia, "en")
        assert en["chi"] == it["chi"] == chi and en["testo"] != it["testo"] and en["testo"].isascii()      # stessi codici, altre parole
    assert f(2, 2, True, soglia, "en")["testo"].startswith("Good for both")
    assert f(-2, 0, True, soglia, "en")["testo"] == "Not worth it: for you."
    assert f(2, 2, False, soglia, "en")["testo"].startswith("As it stands the trade cannot be made") and "as it stands" not in f(2, 2, False, soglia, "en")["testo"]
    d = analizza([2, 3], [31], lingua="en")
    assert d["valido"] is False
    testo = " ".join(d["problemi"])
    assert "forwards out of a maximum of 3" in testo and "no formation could be fielded" in testo and "defenders out of a maximum of 5" in testo
    assert all(s.isascii() for s in d["problemi"]) and d["giudizio"]["testo"].startswith("As it stands")
    assert d["giudizio"]["spiegazione"][0].startswith("For you the best line-up goes from") and "points over the season" in d["giudizio"]["spiegazione"][1]
    assert "Così" in analizza([2, 3], [31])["giudizio"]["testo"]                        # senza lingua: italiano come prima
    rose = _rose()
    rose.squadre[0].crediti_residui = 10
    c = analizza([12, 9], [32, 30], conguaglio=-50, rose=rose, lingua="en")
    assert c["conguaglio"]["problema"].endswith("has 10 credits and cannot pay 50")
    s = analizza([12, 9], [32, 30], conguaglio=20, tasso_mio=0.05, lingua="en")["giudizio"]["spiegazione"]
    assert s[-1].startswith("Balance: receiving 20 credits is worth about") and "0.05 points" in s[-1]
    with pytest.raises(ValueError, match="non può superare"):
        analizza([12], [32], conguaglio=10 ** 7, lingua="en")                           # gli errori restano in italiano


def test_conguaglio_oltre_i_fondi_della_squadra_che_paga():
    rose = _rose()
    rose.squadre[0].crediti_residui = 10                  # A
    rose.squadre[1].crediti_residui = 100                 # B
    d = analizza([12, 9], [32, 30], conguaglio=-50, rose=rose)       # pago io 50, ne ho 10
    assert d["conguaglio"]["valido"] is False and d["valido"] is False
    assert d["conguaglio"]["chi_paga"] == "tu" and "non può pagarne 50" in d["conguaglio"]["problema"]
    ok = analizza([12, 9], [32, 30], conguaglio=-10, rose=rose)      # pago giusto quanto ho: scendo a zero, non sotto
    assert ok["conguaglio"]["valido"] is True and ok["conguaglio"]["dopo"] == {"mio": 0, "loro": 110}
    loro = analizza([12, 9], [32, 30], conguaglio=150, rose=rose)    # mi dovrebbero dare 150, ne hanno 100
    assert loro["conguaglio"]["valido"] is False and loro["conguaglio"]["chi_paga"] == "loro"


def test_conguaglio_senza_crediti_indicati_avvisa_ma_non_blocca():
    d = analizza([12, 9], [32, 30], conguaglio=20)
    assert d["conguaglio"]["valido"] is True and "non sono indicati" in d["conguaglio"]["problema"]
    assert d["conguaglio"]["dopo"] == {"mio": None, "loro": None}


def test_conguaglio_assurdo_e_rifiutato():
    with pytest.raises(ValueError, match="non può superare"):
        analizza([12], [32], conguaglio=10 ** 7)
    with pytest.raises(ValueError, match="intero"):
        analizza([12], [32], conguaglio=1.5)


def test_valore_dei_crediti_cambia_il_giudizio():
    # a somma zero: con 10 crediti ricevuti a 0,2 punti l'uno ho +2 punti e lui -2 (a 0,2 anche per lui)
    senza = analizza([1], [21])
    con = analizza([1], [21], conguaglio=10, tasso_mio=0.2, tasso_loro=0.2)
    assert senza["giudizio"]["chi"] == "poco"
    assert con["conguaglio"]["valore_mio"] == pytest.approx(2.0) and con["conguaglio"]["valore_loro"] == pytest.approx(-2.0)
    assert con["netto_mio"] == pytest.approx(2.0) and con["netto_loro"] == pytest.approx(-2.0)
    assert con["guadagno_mio"] == 0                                      # i punti puri restano separati
    assert con["giudizio"]["chi"] == "te"
    pago = analizza([1], [21], conguaglio=-10, tasso_mio=0.2, tasso_loro=0.2)
    assert pago["giudizio"]["chi"] == "lui"
    # senza tasso i crediti sono mostrati ma non contano
    muto = analizza([1], [21], conguaglio=10)
    assert muto["conguaglio"]["valore_mio"] is None and muto["giudizio"]["chi"] == "poco"


def test_il_tasso_dei_crediti_viene_dal_mercato():
    mercato = {"proposte": [{"entra": {"quotazione": 10}, "rimborso": 2, "guadagno": 4.0},
                            {"entra": {"quotazione": 5}, "rimborso": None, "guadagno": 1.0},
                            {"entra": {"quotazione": 1}, "rimborso": 3, "guadagno": 9.0},     # costo netto <= 0: ignorata
                            {"entra": {"quotazione": 8}, "rimborso": 0, "guadagno": -1.0}]}   # non migliora: ignorata
    assert scambi_multi.tasso_da_mercato(mercato) == pytest.approx(5.0 / 13)
    assert scambi_multi.tasso_da_mercato({"proposte": []}) is None


def test_errori_di_input():
    with pytest.raises(ValueError, match="sono in A"):
        analizza([21], [32])
    with pytest.raises(ValueError, match="almeno un giocatore"):
        analizza([], [32])
    with pytest.raises(ValueError, match="ripetuto"):
        analizza([12, 12], [32, 31])
    with pytest.raises(ValueError, match="te stesso"):
        scambi_multi.analizza_completo(V, REGOLE, _rose(), "A", "A", [12], [11])
    with pytest.raises(ValueError, match="non trovata"):
        scambi_multi.analizza_completo(V, REGOLE, _rose(), "A", "zzz", [12], [32])


# ---------------------------------------------------------------- ricerca automatica
# Scenario con rose piene (2 P, 5 D, 5 C, 3 A) e probabilità 1: A ha in panchina un attaccante da 7 che B vorrebbe, B ha in
# panchina un centrocampista da 7 che A vorrebbe. Il 1 contro 1 "attaccante per centrocampista" lascerebbe le rose sbagliate:
# serve un 2 contro 2 (con due riempitivi di ruolo opposto), che prima non veniva mai trovato in modo sensato.
def _scenario(posto_per_b: bool = False):
    tab = {1: ("P", 1, 6), 2: ("P", 1, 6), **{i: ("D", 1, 5) for i in range(3, 8)},
           **{i: ("C", 1, 5) for i in range(8, 12)}, 12: ("C", 1, 1), 13: ("A", 1, 9), 14: ("A", 1, 9), 15: ("A", 1, 7),
           21: ("P", 1, 6), 22: ("P", 1, 6), **{i: ("D", 1, 5) for i in range(23, 28)},
           **{i: ("C", 1, 8) for i in range(28, 32)}, 32: ("C", 1, 7), 33: ("A", 1, 3), 34: ("A", 1, 3), 35: ("A", 1, 1)}
    if posto_per_b:
        del tab[35]
    from fanta import lega
    sq = lambda nome, ids: lega.Squadra(nome, [lega.GiocatoreRosa(i, f"g{i}", tab[i][0], "X") for i in ids])  # noqa: E731
    rose = lega.Rose([sq("A", range(1, 16)), sq("B", [i for i in range(21, 36) if i in tab])], "A")
    return _valori(tab), rose


def test_un_due_contro_due_vero_con_rose_piene():
    v, rose = _scenario()
    assert scambi.proponi(v, REGOLE, rose, "A", "B") == []                 # nessun 1 contro 1 conviene a tutti e due
    trovati = scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True)
    assert trovati and all(sorted(s.do) == [12, 15] and 35 in s.ricevo for s in trovati)    # attaccante e riempitivo per centrocampista e riempitivo
    assert all(s.guadagno_mio >= 2 and s.guadagno_loro >= 3 for s in trovati)
    assert scambi.proponi(v, REGOLE, rose, "A", "B", fino_a=3)[0].come_dict(v)["formato"] == "2v2"
    d = scambi_multi.analizza_completo(v, REGOLE, rose, "A", "B", [15, 12], [32, 35])
    assert d["valido"] and d["giudizio"]["chi"] == "entrambi"
    # l'attaccante per il centrocampista da solo lascerebbe le rose sbagliate, e il programma lo dice
    solo = scambi_multi.analizza_completo(v, REGOLE, rose, "A", "B", [15], [32])
    assert not solo["valido"] and "centrocampisti su un massimo di 5" in " ".join(solo["problemi"])


def test_un_due_contro_uno_se_la_rosa_ha_posto():
    v, rose = _scenario(posto_per_b=True)                                  # B ha 14 giocatori: un posto libero per gli attaccanti
    assert scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True) == []
    trovati = scambi.proponi(v, REGOLE, rose, "A", "B", fino_a=2)
    assert trovati and all(sorted(s.do) == [12, 15] and len(s.ricevo) == 1 for s in trovati)
    assert all(s.come_dict(v)["formato"] == "2v1" for s in trovati)
    d = scambi_multi.analizza_completo(v, REGOLE, rose, "A", "B", [12, 15], [32])
    assert d["valido"] and d["rose"]["mio"]["conteggio"]["C"] == 5


def test_le_proposte_grandi_lasciano_rose_valide():
    for scenario in (_scenario(), _scenario(True)):
        v, rose = scenario
        for s in scambi.proponi(v, REGOLE, rose, "A", "B", fino_a=3):
            d = scambi_multi.analizza_completo(v, REGOLE, rose, "A", "B", s.do, s.ricevo)
            assert d["valido"], d["problemi"]
            assert d["guadagno_mio"] == pytest.approx(s.guadagno_mio, abs=0.01)


def test_il_budget_di_calcoli_e_un_numero_fisso():
    """Con 0 calcoli non si trova niente; con il budget normale sì, e ripetendo la ricerca il risultato è identico
    (non dipende dal tempo: si può ricordare in cache)."""
    v, rose = _scenario()
    assert scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True, max_valutazioni=0) == []
    uno = scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True, max_valutazioni=40)
    due = scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True, max_valutazioni=40)
    assert uno and [(s.do, s.ricevo) for s in uno] == [(s.do, s.ricevo) for s in due]


def test_la_ricerca_con_dati_dispersi_in_ordine_di_rosa_trova_gli_attaccanti():
    """Rosa con molti candidati: il budget piccolo non deve favorire chi sta prima nella rosa (portieri e difensori)."""
    v, rose = _scenario()
    # tanti difensori e portieri "neutri" davanti agli attaccanti nella rosa: l'ordine della rosa non conta
    assert scambi.proponi(v, REGOLE, rose, "A", "B", anche_due=True, max_valutazioni=15)


def test_misure_della_ricerca():
    assert scambi_multi.formati_da_cercare() == []
    assert scambi_multi.formati_da_cercare(anche_due=True) == [(2, 2)]
    assert len(scambi_multi.formati_da_cercare(fino_a=3)) == 8      # 3x3 senza l'1 contro 1
    with pytest.raises(ValueError, match="da 2 a 4"):
        scambi_multi.formati_da_cercare(fino_a=5)


def test_rosa_gia_incompleta_non_blocca_le_proposte():
    """Rose importate incomplete: lo scambio non deve peggiorarle, ma non si blocca tutto per un problema che c'era già."""
    corta = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3})
    prima = {"P": 1, "D": 3, "C": 4, "A": 2}                  # mancano due difensori
    assert scambi_multi.non_peggiora(prima, dict(prima), corta)
    assert not scambi_multi.non_peggiora(prima, {"P": 1, "D": 2, "C": 5, "A": 2}, corta)


def test_plurale_dei_giocatori_da_liberare():
    """Collaudo 2/11: «ne andrebbero liberati 1»."""
    from fanta.scambi_multi import problemi_rosa
    uno = problemi_rosa("A", {"P": 1, "D": 4, "C": 4, "A": 4}, REGOLE)
    due = problemi_rosa("A", {"P": 1, "D": 4, "C": 4, "A": 5}, REGOLE)
    assert "ne andrebbe liberato 1" in uno[0]["testo"] and "ne andrebbero liberati 2" in due[0]["testo"]


def test_conguaglio_oltre_i_fondi_non_si_valuta_in_punti():
    rose = _rose()
    rose.squadre[0].crediti_residui = 10
    rose.squadre[1].crediti_residui = 100
    d = analizza([12, 9], [32, 30], conguaglio=-50, rose=rose, tasso_mio=0.2, tasso_loro=0.2)
    assert d["conguaglio"]["dopo"] == {"mio": None, "loro": None} and d["conguaglio"]["valore_mio"] is None
    assert d["netto_mio"] == d["guadagno_mio"]
    en = analizza([12, 9], [32, 30], conguaglio=-50, rose=rose, tasso_mio=0.2, tasso_loro=0.2, lingua="en")
    assert "is not possible" in en["giudizio"]["spiegazione"][-1]
