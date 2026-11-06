"""Gol e assist attesi «nostri» (L3b di #165): il modello con i soli dati di Fantacalcio.it. Dati inventati."""
from dataclasses import fields

import numpy as np
import pandas as pd
import pytest

from fanta import modello, nostri, verifica_pacchetti as vp
from fanta.modello import Parametri
from fanta.regole import Regole

from test_modello import ST, _dati


def _understat_a_caso(d, seme=7):
    """Gli stessi dati con xG, xA e minuti di Understat cambiati a caso (anche gli xG delle squadre)."""
    rng = np.random.default_rng(seme)
    n = len(d.prestazioni)
    d.prestazioni = d.prestazioni.assign(xg=rng.uniform(0, 2, n), xa=rng.uniform(0, 1, n), minuti=rng.integers(1, 91, n))
    m = len(d.partite)
    d.partite = d.partite.assign(xg_casa=rng.uniform(0, 3, m), xg_trasferta=rng.uniform(0, 3, m))
    return d


def test_previsioni_nostre_non_leggono_understat():
    a = nostri.previsioni(_dati(), ST, 5, Regole())
    b = nostri.previsioni(_understat_a_caso(_dati()), ST, 5, Regole())
    pd.testing.assert_frame_equal(a, b)
    # il cambio pesa davvero sul modello di oggi, che legge Understat: la prova sopra non è vuota
    oggi_a = modello.previsioni(_dati(), ST, 5, Regole())
    oggi_b = modello.previsioni(_understat_a_caso(_dati()), ST, 5, Regole())
    assert not oggi_a["e_gol"].equals(oggi_b["e_gol"])


def test_previsioni_nostre_passano_probabili_e_giocatori():
    giocatori = pd.DataFrame([{"id": 1, "nome": "Bomber", "ruolo": "A", "squadra_slug": "alfa"}])
    p = nostri.previsioni(_dati(), ST, 5, Regole(), giocatori=giocatori)
    assert p["id"].tolist() == [1]


def test_scenario_solo_fantacalcio_misura_i_numeri_nostri():
    d = _dati()
    kw, _ = vp.prepara("solo_fantacalcio", d, Regole(), Parametri())
    laboratorio = modello.previsioni(kw["dati_modello"], ST, 5, Regole(), kw["par"])
    pd.testing.assert_frame_equal(laboratorio, nostri.previsioni(_dati(), ST, 5, Regole()))


def test_parametri_nostri_senza_xg():
    p = nostri.parametri()
    assert p.peso_xg == 0.0 and p.peso_xa == 0.0
    # Fase B: rigori con memoria lunga e minuti dalle presenze con voto, accesi solo per i nostri (la produzione non cambia)
    assert p.rigori_squadra and p.minuti_con_voto
    assert not Parametri().rigori_squadra and not Parametri().minuti_con_voto
    # Fase C: livello recente del campionato e medie del ruolo pesate, forza delle squadre tarata sui soli gol
    assert p.decadimento_base is not None and p.medie_ruolo_pesate
    assert Parametri().decadimento_base is None and not Parametri().medie_ruolo_pesate
    assert (p.decadimento_squadre, p.k_squadre) != (Parametri().decadimento_squadre, Parametri().k_squadre)
    cambiati = ("peso_xg", "peso_xa", "rigori_squadra", "minuti_con_voto", "decadimento_base", "medie_ruolo_pesate",
                "decadimento_squadre", "k_squadre")
    altri = [f.name for f in fields(Parametri) if f.name not in cambiati]
    assert {c: getattr(p, c) for c in altri} == {c: getattr(Parametri(), c) for c in altri}
    # partendo da altri parametri, tiene i loro valori e spegne solo gli xG
    q = nostri.parametri(Parametri(k_90=5.0, peso_xg=0.7))
    assert q.k_90 == 5.0 and q.peso_xg == 0.0


def test_gol_attesi_con_i_rigori():
    prev = pd.DataFrame({"e_gol": [0.20, 0.0], "e_rigori": [0.50, 0.0]})
    assert nostri.gol_attesi(prev, Parametri()).tolist() == pytest.approx([0.59, 0.0])
    # la conversione dei rigori viene dai parametri
    assert nostri.gol_attesi(prev, Parametri(conversione_rigori=1.0)).tolist() == pytest.approx([0.70, 0.0])
