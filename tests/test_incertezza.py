"""Fascia di incertezza calibrata: contiene circa 8 punteggi veri su 10, non cambia le scelte."""
import json

import numpy as np
import pandas as pd
import pytest

from fanta import diario, incertezza
from fanta.regole import Regole

from test_diario import ST, finto  # noqa: F401  (fixture)


def test_intervallo_largo_quanto_lo_scarto_vero_e_coerente_con_dev():
    i = incertezza.intervallo(70.0, 2.0)
    assert i["confidenza"] == 0.8 and i["basso"] < 70 < i["alto"]
    assert 14 < i["alto"] - i["basso"] < 20          # misurato: lo scarto vero ha deviazione circa 6,7 punti
    c = incertezza.campi(70.0, 2.0)
    assert c["dev_simulata"] == 2.0 and c["intervallo"] == i
    assert c["dev"] * 2 * incertezza.Z_80 == pytest.approx(i["alto"] - i["basso"], abs=0.3)
    # più incertezza nella simulazione (giocatori in dubbio) = fascia più larga
    assert incertezza.intervallo(70.0, 6.0)["alto"] > i["alto"]


def test_con_pochi_casi_della_lega_la_fascia_e_indicativa():
    cal = dict(incertezza.CALIBRAZIONE)
    assert incertezza.intervallo(70, 2, cal | {"casi_lega": 10})["indicativo"] is True
    assert incertezza.intervallo(70, 2, cal | {"casi_lega": 500})["indicativo"] is False


def _casi_finti(n=4000, seme=3):
    rng = np.random.default_rng(seme)
    dev = rng.uniform(0.5, 4.0, n)
    atteso = rng.uniform(60, 75, n)
    reale = atteso + rng.normal(0, np.sqrt(6.0 ** 2 + dev ** 2))
    return pd.DataFrame({"stagione": "x", "tipo": "sintetica", "atteso": atteso, "dev": dev, "reale": reale,
                         "scarto": reale - atteso})


def test_calibra_ritrova_lo_scarto_e_la_copertura_va_all_80():
    t = _casi_finti()
    cal = incertezza.calibra(t)
    assert cal["fisso"] == pytest.approx(6.0, abs=0.3)
    assert cal["q_basso"] == pytest.approx(-1.28, abs=0.1) and cal["q_alto"] == pytest.approx(1.28, abs=0.1)
    prova = _casi_finti(seme=9)                          # fuori campione
    assert incertezza.copertura(prova, cal)["dentro"] == pytest.approx(0.8, abs=0.03)
    assert incertezza.copertura(prova, vecchia=True)["dentro"] < 0.5      # la fascia di prima (solo simulazione) è troppo stretta


def test_rapporto_stampa_e_restituisce_le_costanti():
    righe = []
    cal = incertezza.rapporto(_casi_finti(500), scrivi=righe.append)
    assert set(cal) == {"fisso", "q_basso", "q_alto", "casi", "casi_lega"} and any("Costanti" in r for r in righe)


def test_diario_ha_la_fascia_anche_per_le_voci_vecchie(finto, tmp_path):  # noqa: F811
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    c = v["consigliata"]
    assert c["intervallo"]["basso"] < c["atteso"] < c["intervallo"]["alto"] and "dev_simulata" in c
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"giornate": {"2026-27/1": {"stagione": "2026-27", "giornata": 1,
                                                        "consigliata": {"reale": 60, "atteso": 70}, "schierata": None}}}),
                 encoding="utf-8")
    assert diario.elenco(f)["giornate"][0]["consigliata"]["intervallo"] == incertezza.intervallo(70, 0.0)


def test_raccogliere_i_casi_non_cambia_la_verifica():
    from fanta import verifica
    from fanta.modello import Parametri
    from test_modello import ST as ST_M, _dati
    d = _dati()
    casi = []
    a = verifica.verifica_giornata(d, ST_M, 4, Regole(), Parametri())
    b = verifica.verifica_giornata(d, ST_M, 4, Regole(), Parametri(), casi=casi, sintetiche=3)
    assert a == b
