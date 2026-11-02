"""Scambi: valore di una rosa, analisi, proposte vantaggiose per tutti e due."""
import pandas as pd
import pytest

from fanta import lega, scambi
from fanta.regole import Regole

# rosa minima: moduli con 1 P + 10 di movimento; per semplicità un solo modulo 4-4-2
REGOLE = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3})


def _valori(tabella, giornate=1, resto=0):
    info = pd.DataFrame([{"id": i, "nome": f"g{i}", "ruolo": r, "squadra": "X", "quotazione": 10}
                         for i, (r, _, _) in tabella.items()]).set_index("id")
    return scambi.Valori(list(range(1, giornate + 1)), resto, [tabella] * giornate, info)


def _rosa(ids):
    return [i for i in ids]


TAB = {
    # squadra A: attaccanti forti, centrocampisti scarsi
    1: ("P", 0.9, 6), 2: ("D", 0.9, 6), 3: ("D", 0.9, 6), 4: ("D", 0.9, 6), 5: ("D", 0.9, 6),
    6: ("C", 0.9, 5), 7: ("C", 0.9, 5), 8: ("C", 0.9, 5), 9: ("C", 0.9, 5),
    10: ("A", 0.9, 8), 11: ("A", 0.9, 8), 12: ("A", 0.9, 8),
    # squadra B: centrocampisti forti, attaccanti scarsi
    21: ("P", 0.9, 6), 22: ("D", 0.9, 6), 23: ("D", 0.9, 6), 24: ("D", 0.9, 6), 25: ("D", 0.9, 6),
    26: ("C", 0.9, 8), 27: ("C", 0.9, 8), 28: ("C", 0.9, 8), 29: ("C", 0.9, 8), 30: ("C", 0.9, 8),
    31: ("A", 0.9, 5), 32: ("A", 0.9, 5),
}


def _rose():
    def sq(nome, ids):
        return lega.Squadra(nome, [lega.GiocatoreRosa(i, f"g{i}", TAB[i][0], "X") for i in ids])
    return lega.Rose([sq("A", list(range(1, 13))), sq("B", list(range(21, 33)))], "A")


def test_valore_giornata_titolari_e_riserva():
    v = _valori(TAB)
    # 4-4-2 per A: P + 4 D + 4 C + 2 A titolari; il terzo A entra solo se manca almeno uno dei due (1 - 0.9*0.9)
    atteso = 0.9 * 6 * 5 + 0.9 * 5 * 4 + 2 * 0.9 * 8 + 0.9 * 8 * (1 - 0.81)
    assert scambi.valore_giornata(list(range(1, 13)), v.per_giornata[0], REGOLE) == pytest.approx(atteso)


def test_una_riserva_entra_una_volta_sola():
    tab = {1: ("P", 1.0, 6), **{i: ("D", 0.5, 6) for i in range(2, 6)}, 6: ("D", 1.0, 6),
           **{i: ("C", 1.0, 6) for i in range(7, 11)}, 11: ("A", 1.0, 6), 12: ("A", 1.0, 6)}
    v = _valori(tab)
    base = 6 + 4 * 0.5 * 6 + 4 * 6 + 2 * 6
    valore = scambi.valore_giornata(list(range(1, 13)), v.per_giornata[0], REGOLE)
    # la riserva (sicura, 6 punti) vale 6 x P(almeno un difensore assente) = 6 x (1 - 0.5^4), non 4 x 0.5 x 6
    assert valore == pytest.approx(base + 6 * (1 - 0.5 ** 4))


def test_analizza_scambio_che_conviene_a_tutti_e_due():
    v = _valori(TAB)
    # A dà il suo 3° attaccante (riserva) e un centrocampista scarso; riceve un A scarso e un C forte (riserva di B)
    s = scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[12, 9], ricevo=[32, 30])
    assert s.guadagno_mio > 0 and s.guadagno_loro > 0
    # 1 contro 1 nello stesso ruolo: A cede un attaccante forte per uno scarso, perde
    assert scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[10], ricevo=[31]).guadagno_mio < 0


def test_analizza_rifiuta_ruoli_diversi_e_giocatori_non_suoi():
    v = _valori(TAB)
    with pytest.raises(ValueError, match="ruolo"):
        scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[12], ricevo=[29])
    with pytest.raises(ValueError):
        scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[21], ricevo=[31])
    with pytest.raises(ValueError):    # stesso giocatore due volte
        scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[12, 12], ricevo=[31, 32])
    with pytest.raises(ValueError):    # con se stessi
        scambi.analizza(v, REGOLE, _rose(), "A", "A", do=[12], ricevo=[11])
    with pytest.raises(ValueError, match="non trovata"):
        scambi.proponi(v, REGOLE, _rose(), "A", "zzz")


def test_proposte_solo_vantaggiose_per_tutti_e_due():
    v = _valori(TAB)
    proposte = scambi.proponi(v, REGOLE, _rose(), "A", "B", anche_due=True)
    assert proposte
    assert all(s.guadagno_mio > 0 and s.guadagno_loro > 0 for s in proposte)


def test_resto_della_stagione_conta():
    tab_futuro = dict(TAB)
    v = scambi.Valori([1, 2, 3], 10, [TAB, TAB, tab_futuro], _valori(TAB).info)
    per_giornata = [1.0, 1.0, 1.0]
    assert scambi.totale(per_giornata, v) == pytest.approx(3 + scambi.PESO_RESTO * 10 * 1.0)


def test_impatto_per_reparto():
    v = _valori(TAB)
    # A dà una riserva d'attacco e un centrocampista scarso, riceve un centrocampista forte: cambia solo il centrocampo
    s = scambi.analizza(v, REGOLE, _rose(), "A", "B", do=[12, 9], ricevo=[32, 30])
    r = s.reparti["mio"]
    assert set(r) == {"P", "D", "C", "A"}
    assert r["P"] == 0 and r["D"] == 0
    assert r["C"] > 0
    assert s.percentuale_mio > 0
    assert s.come_dict(v)["reparti"]["loro"].keys() == r.keys()


def test_le_proposte_si_ricordano_ma_non_con_rose_diverse(monkeypatch):
    """La ricerca 1 contro 1 (lenta sul server) si fa una volta sola per stessi dati, regole e rose."""
    import sqlite3
    from fanta import calcolo, consigli
    calcolo.cache.clear()
    v = _valori(TAB, giornate=2)
    chiamate = []
    originale = scambi.proponi
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: v)
    monkeypatch.setattr(consigli, "_versione", lambda db: "v1")
    monkeypatch.setattr(scambi, "proponi", lambda *a, **k: chiamate.append(1) or originale(*a, **k))
    db = sqlite3.connect(":memory:")
    r1 = consigli.proposte_scambi(db, REGOLE, _rose(), None, False)[1]
    r2 = consigli.proposte_scambi(db, REGOLE, _rose(), None, False)[1]
    assert r1 == r2 and len(chiamate) == 1
    altre = _rose()
    altre.squadre[0].giocatori.pop()                          # una rosa cambiata: si ricalcola
    consigli.proposte_scambi(db, REGOLE, altre, None, False)
    assert len(chiamate) == 2
    consigli.proposte_scambi(db, REGOLE, _rose(), "B", True)   # anche i 2 contro 2 si ricordano (budget fisso di calcoli)
    consigli.proposte_scambi(db, REGOLE, _rose(), "B", True)
    assert len(chiamate) == 3
    consigli.proposte_scambi(db, REGOLE, _rose(), "B", False, 3)   # un'altra misura di ricerca è un'altra chiave
    assert len(chiamate) == 4
    calcolo.cache.clear()


def test_almeno_prefissi_uguale_a_almeno_per_ogni_numero_di_titolari():
    """Un solo passaggio dà gli stessi numeri (identici, non solo vicini) di una chiamata a `_almeno` per ogni prefisso."""
    p = [0.12, 0.3, 0.05, 0.9, 0.47, 0.2]
    for massimo in (1, 3, 5, 9):
        prefissi = scambi._almeno_prefissi(p, massimo)
        assert len(prefissi) == min(len(p), massimo) + 1
        for k, atteso in enumerate(prefissi):
            assert atteso == scambi._almeno(p[:k])


def test_i_numeri_ricordati_sono_gli_stessi_alla_seconda_chiamata_e_con_moduli_diversi():
    """Le scorciatoie (moduli letti una volta, prefissi ricordati) non cambiano nessun risultato."""
    p = [0.12, 0.3, 0.05, 0.9, 0.47, 0.2]
    assert scambi._almeno_prefissi(p, 5) == scambi._almeno_prefissi(list(p), 5) == scambi._almeno_prefissi_ricordati(tuple(p), 5)
    elenco, massimo = scambi._moduli_e_massimi(("3-4-3", "4-4-2", "5-3-2"))
    assert elenco == (("3-4-3", 3, 4, 3), ("4-4-2", 4, 4, 2), ("5-3-2", 5, 3, 2)) and massimo == {"P": 1, "D": 5, "C": 4, "A": 3}
    r1, r2 = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3}), Regole(moduli=["4-4-2", "3-5-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3})
    base = scambi.valore_giornata(list(range(1, 13)), TAB, r1)
    assert scambi.valore_giornata(list(range(1, 13)), TAB, r1) == base                         # stessa chiamata, stesso numero
    assert scambi.valore_giornata(list(range(1, 13)), TAB, r2) >= base                        # un modulo in più non fa mai peggio, e i moduli non si confondono fra regole
