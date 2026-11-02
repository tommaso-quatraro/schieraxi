"""Esperimenti di ablazione (`verifica --pacchetti`): spenti di default, non toccano i dati veri."""
import numpy as np
import pandas as pd
import pytest

from fanta import verifica, verifica_pacchetti as vp
from fanta.modello import Parametri
from fanta.regole import Regole

from test_modello import ST, _dati


def _riga(g, cid=3, **kw):
    r = {"stagione": ST, "giornata": g, "calciatore_id": cid, "nome": "Mediano", "squadra": "beta", "ruolo": "C",
         "voto_red": 6.0, "fv_red": 0, "voto_stat": 6, "fv_stat": 0, "voto_ita": 6, "fv_ita": 0, "gol": 0, "gol_subiti": 0,
         "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0, "ammonizioni": 0,
         "espulsioni": 0, "subentrato": 0, "sostituito": 0, "data": f"2026-09-{g:02d} 15:00"}
    return r | kw


def test_verifica_senza_esperimento_identica():
    d = _dati()
    a = verifica.verifica_giornata(d, ST, 4, Regole(), Parametri())
    b = verifica.verifica_giornata(d, ST, 4, Regole(), Parametri(), dati_modello=d, prevedi=None, ritocca=None)
    assert a == b


def test_senza_xg_non_tocca_l_originale():
    d = _dati()
    s = vp.senza_xg(d)
    assert s.prestazioni["xg"].isna().all() and s.partite["xg_casa"].isna().all()
    assert d.prestazioni["xg"].notna().all()
    assert vp.par_senza_xg(Parametri()).peso_xg == 0.0


def test_voto_stimato_cambia_solo_i_voti_presenti():
    d = _dati([_riga(4, cid=4, voto_red=None, nome="Riserva")])
    dv, tar = vp.con_voto_stimato(d, Regole(), list(vp.EVENTI))
    assert dv.voti["voto_red"].isna().equals(d.voti["voto_red"].isna())   # chi era senza voto resta senza voto
    assert d.voti.loc[d.voti["calciatore_id"] == 1, "voto_red"].iloc[0] == 6.5     # originale intatto
    assert dv.voti["voto_red"].dropna().between(3.5, 9.5).all() and ST in tar.errore


def test_squalificati_dal_rosso_non_da_tre_gialli():
    gialli = [_riga(g, cid=3, ammonizioni=1) for g in range(1, 4)]   # il Mediano ha già un giallo a giornata (1-3)
    d = _dati()
    d.voti = d.voti[~((d.voti["calciatore_id"] == 3) & d.voti["giornata"].between(1, 3))]
    d.voti = pd.concat([d.voti, pd.DataFrame(gialli)], ignore_index=True)
    assert 3 not in vp.squalificati(d, ST, 4)            # 3 gialli: niente squalifica
    d.voti.loc[(d.voti["calciatore_id"] == 2) & (d.voti["giornata"] == 3), "espulsioni"] = 1
    assert vp.squalificati(d, ST, 4) == {2}              # rosso alla 3: fuori alla 4


def test_indisponibili_e_ritocca():
    d = _dati()
    # il Mediano non c'è nella 3 e nella 4: per la 3 è un indisponibile noto
    d.voti = d.voti[~((d.voti["calciatore_id"] == 3) & d.voti["giornata"].isin([3, 4]))]
    ind = vp.indisponibili(d, ST, 3)
    assert vp._assente(3, ind) and not vp._assente(1, ind)
    prev = pd.DataFrame({"squadra": ["alfa", "beta"], "p_voto": [0.8, 0.8], "partita": [3, 3]}, index=[1, 3])
    p = vp.ritocca(Regole(), sidelined=True)(prev, d, ST, 3)
    assert p[1] == 0.0 and p[0] == pytest.approx(0.8)


def test_scenario_sconosciuto_rifiutato():
    with pytest.raises(ValueError):
        vp.prepara("magia", _dati(), Regole(), Parametri())


def test_confronto_una_riga_per_scenario_e_stagione():
    scenari = ("completo", "senza_xg", "voto_stat", "pacchetto_a", "sportmonks_starter", "attuale_probabili_90")
    t, note = vp.confronto(_dati(), Regole(), Parametri(), [(ST, 3), (ST, 4)], None, 20, scenari, scrivi=None)
    assert set(t["scenario"]) == set(scenari)
    base = t[(t["scenario"] == "completo") & (t["stagione"] == "tutte")].iloc[0]
    assert base["rmse_vs_completo"] == pytest.approx(0.0) and np.isfinite(base["rmse"])
    assert "errore_voto_stimato" in note["voto_stat"]


def test_rose_sintetiche_rispettano_la_composizione():
    from dataclasses import replace
    regole = replace(Regole(), rosa={"P": 1, "D": 1, "C": 1, "A": 1})
    d = _dati([_riga(g, cid=4, nome="Terzino", ruolo="D") for g in range(1, 5)])
    rose = vp.rose_sintetiche(d, regole, 3, min_voti=2)
    assert len(rose) == 3 and all(sorted(r) == [1, 2, 3, 4] for r in rose)
    assert vp.rose_sintetiche(_dati(), regole, 3, min_voti=2) == []      # nessun difensore: niente rose
