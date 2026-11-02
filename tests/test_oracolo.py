"""Oracolo di verifica: spento di default (stessi numeri di prima), acceso dà al modello la verità."""
import pytest

from fanta import verifica
from fanta.modello import Parametri, previsioni
from fanta.regole import Regole

from test_modello import ST, _dati


def test_oracolo_spento_non_cambia_nulla():
    d = _dati()
    a = previsioni(d, ST, 5, Regole(), Parametri())
    b = previsioni(d, ST, 5, Regole(), Parametri(), oracolo=None)
    c = previsioni(d, ST, 5, Regole(), Parametri(), oracolo={})
    assert a.equals(b) and a.equals(c)


def test_oracolo_sconosciuto_rifiutato():
    with pytest.raises(ValueError):
        verifica.dati_oracolo(_dati(), ST, {"magia"})


def test_dati_oracolo_gol_e_rigorista():
    d = _dati()
    v = verifica.dati_oracolo(d, ST, {"gol_squadra", "rigorista"})
    assert v["gol_squadra"][1] == (1.0, 1.0) and 5 not in v["gol_squadra"]   # la 5 non è giocata
    assert set(v["rigorista"]) == {1}                                         # solo il Bomber calcia rigori
    assert 0.8 < v["rigorista"][1] <= 1.0


def test_gol_veri_e_rigorista_vero_entrano_nelle_previsioni():
    d = _dati()
    base = previsioni(d, ST, 5, Regole(), Parametri()).set_index("id")
    # partita 5: alfa in casa; con 4 gol veri alfa deve aspettarsi più gol del solito
    o = previsioni(d, ST, 5, Regole(), Parametri(), oracolo={"gol_squadra": {5: (4.0, 0.0)}}).set_index("id")
    assert o.at[1, "gol_squadra"] == 4.0 and o.at[1, "gol_avversario"] == 0.0
    assert o.at[1, "gol_squadra"] > base.at[1, "gol_squadra"]
    # rigorista vero: se non è il Bomber, i rigori attesi passano al Mediano
    r = previsioni(d, ST, 5, Regole(), Parametri(), oracolo={"rigorista": {3: 0.9}}).set_index("id")
    assert r.at[1, "e_rigori"] == 0 and r.at[3, "e_rigori"] > 0


def test_verifica_con_oracolo_presenze_azzera_il_brier():
    d = _dati()
    # la giornata 4 è giocata: il Brier con l'oracolo delle presenze è zero, senza è positivo
    n = verifica.verifica_giornata(d, ST, 4, Regole(), Parametri())
    o = verifica.verifica_giornata(d, ST, 4, Regole(), Parametri(), oracolo={"presenze"})
    assert n is not None and o is not None
    assert o.brier == pytest.approx(0.0, abs=1e-9)
    assert n.brier >= 0.0


def test_guadagno_oracoli_ha_una_riga_per_prova():
    d = _dati()
    t = verifica.guadagno_oracoli(d, Regole(), Parametri(), [(ST, 3), (ST, 4)], None, 20, scrivi=None)
    assert list(t["prova"]) == ["base", "presenze", "gol_squadra", "rigorista", "tutti"]
    assert t.loc[t["prova"] == "presenze", "brier"].iloc[0] == pytest.approx(0.0, abs=1e-9)
