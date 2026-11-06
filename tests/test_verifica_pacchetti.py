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


# ---------------------------------------------------------------- «solo Fantacalcio.it» (L3a, indicatore I4)
def test_minuti_stimati_da_entrato_e_uscito():
    v = pd.DataFrame({"subentrato": [0, 0, 1, 1, None], "sostituito": [0, 1, 0, 1, None]})
    assert vp.minuti_stimati(v).tolist() == [90.0, 71.0, 19.0, 30.0, 90.0]


def test_solo_fantacalcio_non_usa_understat():
    d = _dati([_riga(4, cid=4, nome="Riserva", voto_red=None, subentrato=1)])
    s = vp.solo_fantacalcio(d)
    # niente xG, né dei giocatori né delle squadre: la forza delle squadre viene dai soli gol
    assert s.prestazioni["xg"].isna().all() and s.prestazioni["xa"].isna().all()
    assert s.partite["xg_casa"].isna().all() and s.partite["xg_trasferta"].isna().all()
    # una riga per ogni presenza nei voti di Fantacalcio.it, anche chi è entrato ed è rimasto senza voto
    assert len(s.prestazioni) == len(d.voti)
    p = s.prestazioni.set_index(["giornata", "calciatore_id"])
    assert p.at[(4, 4), "minuti"] == 19.0 and p.at[(3, 1), "minuti"] == 90.0
    # Bomber: un gol su azione e un rigore segnato a partita -> 2 gol, 1 rigore calciato, 1 della squadra
    assert p.at[(3, 1), "gol"] == 2 and p.at[(3, 1), "rigori_calciati"] == 1 and p.at[(3, 1), "rigori_segnati"] == 1
    assert p.at[(3, 1), "rigori_squadra"] == 1 and p.at[(3, 3), "rigori_squadra"] == 0
    assert p.at[(3, 1), "understat_partita"] == 3          # la partita di Fantacalcio.it, non quella di Understat
    assert d.prestazioni["xg"].notna().all() and d.prestazioni["minuti"].eq(90).all()      # originale intatto


def test_solo_fantacalcio_rigori_calciati_comprendono_gli_sbagliati():
    d = _dati()
    d.voti.loc[(d.voti["calciatore_id"] == 3) & (d.voti["giornata"] == 2), "rig_sbagliati"] = 1
    p = vp.solo_fantacalcio(d).prestazioni.set_index(["giornata", "calciatore_id"])
    assert p.at[(2, 3), "rigori_calciati"] == 1 and p.at[(2, 3), "rigori_segnati"] == 0 and p.at[(2, 3), "gol"] == 0
    assert p.at[(2, 3), "rigori_squadra"] == 1


def test_solo_fantacalcio_ignora_le_prestazioni_di_understat():
    d = _dati()
    a = vp.solo_fantacalcio(d).prestazioni
    d.prestazioni = d.prestazioni.assign(minuti=5, rigori_calciati=7, xg=9.0).iloc[:1]
    b = vp.solo_fantacalcio(d).prestazioni
    pd.testing.assert_frame_equal(a, b)


def test_scenario_solo_fantacalcio_fa_girare_il_modello():
    d = _dati()
    kw, _ = vp.prepara("solo_fantacalcio", d, Regole(), Parametri())
    assert "solo_fantacalcio" in vp.SCENARI
    assert kw["par"].peso_xg == 0.0 and kw["par"].peso_xa == 0.0
    from fanta.modello import previsioni
    p = previsioni(kw["dati_modello"], ST, 5, Regole(), kw["par"]).set_index("id")
    assert p.at[1, "minuti"] == pytest.approx(90.0) and p.at[1, "e_rigori"] > 0 and p.at[3, "e_rigori"] == 0


def test_gol_per_fasce_confronta_attesi_e_veri():
    d = _dati([_riga(4, cid=4, nome="Riserva", voto_red=None, subentrato=1)])
    previsti = pd.DataFrame({"stagione": ST, "giornata": [3, 4, 3, 4, 4, 4],
                             "id": [1, 1, 3, 3, 4, 9], "gol_attesi": [0.5, 0.6, 0.02, 0.04, 0.03, 0.2]})
    f = vp.gol_per_fasce(d, Regole(), previsti)
    tutte = f[f["stagione"] == "tutte"].set_index("fascia")
    # Bomber: 2 gol veri a partita (uno su rigore); Mediano: nessuno. Senza voto (4) o assente (9): fuori
    alta = tutte.loc[vp.FASCE_GOL_NOMI[-1]]
    assert alta["casi"] == 2 and alta["attesi"] == pytest.approx(0.55) and alta["veri"] == pytest.approx(2.0)
    assert alta["scarto"] == pytest.approx(1.45)
    bassa = tutte.loc[vp.FASCE_GOL_NOMI[0]]
    assert bassa["casi"] == 2 and bassa["scarto"] == pytest.approx(-0.03)
    assert tutte["casi"].sum() == 4 and set(f["stagione"]) == {"tutte", ST}


def test_scarto_gol_solo_fasce_con_abbastanza_casi():
    f = pd.DataFrame({"stagione": "tutte", "fascia": ["a", "b", "c"], "casi": [10, 200, 300],
                      "attesi": [0.1, 0.1, 0.3], "veri": [0.9, 0.12, 0.25], "scarto": [0.8, 0.02, -0.05]})
    assert vp.scarto_gol(f, "tutte", minimo=50) == pytest.approx(0.05)
    assert np.isnan(vp.scarto_gol(f, "tutte", minimo=1000)) and np.isnan(vp.scarto_gol(f, ST))


def test_esegui_completo_identico_alla_verifica_normale():
    d, giornate = _dati(), [(ST, 3), (ST, 4)]
    t, note = vp.esegui("completo", d, Regole(), Parametri(), giornate, None, 20)
    pd.testing.assert_frame_equal(t, verifica.verifica(_dati(), Regole(), Parametri(), giornate, None, 20, scrivi=None))
    assert "gol_per_fasce" in note


def test_conti_attesi_a_mano():
    # giornata 3: Bomber (1) segna su azione e su rigore, Mediano (3) niente ed esce prima; la Riserva (4) entra e resta senza voto
    d = _dati([_riga(3, cid=4, nome="Riserva", voto_red=None, subentrato=1)])
    d.voti.loc[(d.voti["calciatore_id"] == 3) & (d.voti["giornata"] == 3), "sostituito"] = 1
    previsti = pd.DataFrame({"stagione": ST, "giornata": 3, "id": [1, 3, 4], "e_gol": [0.3, 0.1, 0.9],
                             "e_rigori": [0.5, 0.0, 0.5], "e_assist": [0.2, 0.2, 0.9], "minuti": [95.0, 60.0, 20.0],
                             "gol_attesi": [0.69, 0.10, 1.29]})
    c = vp.conti_attesi(d, Regole(), previsti)
    assert c["stagione"].tolist() == ["tutte", ST]
    for _, r in c.iterrows():
        assert r["casi"] == 2                                     # la Riserva, senza voto, non conta
        assert r["azione_su_veri"] == pytest.approx(0.4)          # (0,3 + 0,1) / 1 gol su azione
        assert r["rigori_su_veri"] == pytest.approx(0.5)          # 0,5 rigori attesi / 1 calciato
        assert r["gol_su_veri"] == pytest.approx((0.4 + 0.39) / 2)  # gol con i rigori: 0,79 attesi / 2 veri
        assert np.isnan(r["assist_su_veri"])                      # nessun assist vero: niente rapporto
        assert r["minuti_attesi"] == pytest.approx(75.0)          # 95 conta 90
        assert r["minuti_stimati"] == pytest.approx(80.5)         # 90 (tutta la partita) e 71 (uscito)


def test_conti_attesi_rigore_sbagliato_e_calciato_ma_non_gol():
    d = _dati()
    d.voti.loc[(d.voti["calciatore_id"] == 3) & (d.voti["giornata"] == 3), "rig_sbagliati"] = 1
    previsti = pd.DataFrame({"stagione": ST, "giornata": 3, "id": [1, 3], "e_gol": [0.3, 0.1], "e_rigori": [0.5, 0.0],
                             "e_assist": [0.2, 0.2], "minuti": [90.0, 90.0], "gol_attesi": [0.69, 0.10]})
    r = vp.conti_attesi(d, Regole(), previsti).set_index("stagione").loc["tutte"]
    assert r["rigori_su_veri"] == pytest.approx(0.25)            # 0,5 attesi / 2 calciati (uno segnato, uno sbagliato)
    assert r["gol_su_veri"] == pytest.approx(0.79 / 2)          # il rigore sbagliato non è un gol


def test_tabella_con_i_conti_dei_gol_attesi():
    t = pd.DataFrame({"stagione": [ST, ST], "quadratico_modello": [1.0, 1.0], "errore_modello": [0.9, 0.9],
                      "brier": [0.1, 0.1]})
    conti = pd.DataFrame({"stagione": ["tutte", ST], "casi": [10, 10], "gol_su_veri": [1.01, 1.02],
                          "azione_su_veri": [1.0, 1.0], "rigori_su_veri": [0.42, 0.43], "assist_su_veri": [0.95, 0.96],
                          "minuti_attesi": [65.0, 65.0], "minuti_stimati": [68.0, 68.0]})
    tab = vp.tabella({"completo": t, "pacchetto_a": t}, None, {"completo": conti}).set_index(["scenario", "stagione"])
    assert tab.loc[("completo", "tutte"), ["gol_su_veri", "rigori_su_veri", "assist_su_veri"]].tolist() == [1.01, 0.42, 0.95]
    assert tab.loc[("completo", ST), ["gol_su_veri", "rigori_su_veri", "assist_su_veri"]].tolist() == [1.02, 0.43, 0.96]
    assert tab.loc[("pacchetto_a", "tutte"), ["gol_su_veri", "rigori_su_veri", "assist_su_veri"]].isna().all()


def test_confronto_con_i_conti_dei_gol_attesi():
    righe = []
    t, note = vp.confronto(_dati(), Regole(), Parametri(), [(ST, 3), (ST, 4)], None, 20,
                           ("completo", "solo_fantacalcio", "pacchetto_a"), scrivi=righe.append)
    t = t.set_index(["scenario", "stagione"])
    for nome in ("completo", "solo_fantacalcio"):
        assert np.isfinite(t.loc[(nome, "tutte"), ["gol_su_veri", "rigori_su_veri"]].astype(float)).all()
        assert note[nome]["conti_attesi"].set_index("stagione").at["tutte", "casi"] == 6    # 3 giocatori con voto, 2 giornate
    assert t.loc[("pacchetto_a", "tutte"), ["gol_su_veri", "rigori_su_veri", "assist_su_veri"]].isna().all()
    assert any("Conti dei gol attesi" in r for r in righe)


def test_confronto_con_solo_fantacalcio_e_gol_per_fasce():
    righe = []
    t, note = vp.confronto(_dati(), Regole(), Parametri(), [(ST, 3), (ST, 4)], None, 20,
                           ("completo", "solo_fantacalcio", "pacchetto_a"), scrivi=righe.append)
    assert {"scarto_gol", "rmse_vs_completo_pct"} <= set(t.columns)
    sf = t[(t["scenario"] == "solo_fantacalcio") & (t["stagione"] == "tutte")].iloc[0]
    assert np.isfinite(sf["rmse"]) and np.isfinite(sf["rmse_vs_completo_pct"])
    assert "gol_per_fasce" in note["solo_fantacalcio"] and "gol_per_fasce" not in note["pacchetto_a"]
    assert any("Gol attesi per fasce" in r for r in righe)
