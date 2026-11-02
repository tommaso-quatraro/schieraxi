"""`consigliato` di `/api/confronto` dice chi schierare: lo stesso giocatore del titolo «Schiera X» (issue #121, punto 1).
Prima era sempre chi ha più punti attesi da solo, anche quando la formazione del sistema teneva titolare l'altro (un titolare
incerto con una riserva sicura dietro): la web e l'iPhone scrivevano «Schiera Stolz» e mettevano «Consigliato» su Meret."""
import pandas as pd
import pytest

from fanta import consigli
from fanta.regole import Regole

REGOLE = Regole(moduli=["4-4-2"])


def _prev():
    base = {"ruolo": "P", "squadra": "a", "avversario": "b", "in_casa": True, "mu_voto": 6.3, "e_gol": 0.0, "e_assist": 0.0,
            "e_rigori": 0.0, "gol_subiti": 1.0, "p_imbattuto": 0.2}
    # 1 da solo vale di più (0,9 x 6 = 5,4) di 2 (0,2 x 6,5 = 1,3)
    return pd.DataFrame([base | {"nome": "Sicuro", "p_voto": 0.9, "mu": 6.0}, base | {"nome": "Incerto", "p_voto": 0.2, "mu": 6.5}],
                        index=[1, 2])


def _scheda_finta(i, x):
    return {"id": int(i), "nome": x["nome"], "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2)}


@pytest.fixture
def finto(monkeypatch):
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None, *a, **k: (_prev(), 10, None))
    monkeypatch.setattr(consigli, "scheda_previsione", _scheda_finta)


def _con_formazione(monkeypatch, posto_a, posto_b):
    monkeypatch.setattr(consigli, "_in_formazione", lambda *a, **k: {"modulo": "4-4-2", "posto_a": posto_a, "posto_b": posto_b,
                                                                     "testo": "", "differenza": 0.02})


def test_senza_rosa_consigliato_e_chi_ha_piu_punti_attesi(finto):
    assert consigli.confronto(None, REGOLE, 1, 2)["consigliato"] == 1


def test_titolare_della_formazione_e_il_consigliato_anche_con_meno_punti_da_solo(finto, monkeypatch):
    _con_formazione(monkeypatch, "panchina 1", "titolare")
    r = consigli.confronto(None, REGOLE, 1, 2, rose=object())
    assert r["formazione"]["posto_b"] == "titolare"
    assert r["consigliato"] == 2


def test_titolare_primo_resta_consigliato(finto, monkeypatch):
    _con_formazione(monkeypatch, "titolare", "fuori")
    assert consigli.confronto(None, REGOLE, 2, 1, rose=object())["consigliato"] == 2


@pytest.mark.parametrize("pa,pb", [("titolare", "titolare"), ("panchina 1", "panchina 2"), ("fuori", "panchina 1")])
def test_tutti_e_due_titolari_o_nessuno_vale_chi_ha_piu_punti(finto, monkeypatch, pa, pb):
    _con_formazione(monkeypatch, pa, pb)
    assert consigli.confronto(None, REGOLE, 2, 1, rose=object())["consigliato"] == 1
