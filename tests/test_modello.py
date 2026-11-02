"""Modello: niente dati dal futuro, regole della lega rispettate, probabili formazioni usate."""
import pandas as pd
import pytest

from fanta import modello
from fanta.regole import Regole, imposta

ST = "2026-27"


def _dati(voti_extra=()):
    """Due squadre (alfa, beta) che si affrontano ogni giornata, 4 giornate giocate e la 5 da giocare."""
    partite, voti, prest = [], [], []
    for g in range(1, 6):
        casa, trasf = ("alfa", "beta") if g % 2 else ("beta", "alfa")
        giocata = int(g <= 4)
        partite.append({"id": g, "stagione": ST, "giornata": g, "data": f"2026-09-{g:02d} 15:00", "casa": casa,
                        "trasferta": trasf, "gol_casa": 1 if giocata else None, "gol_trasferta": 1 if giocata else None,
                        "giocata": giocata, "xg_casa": 1.2 if giocata else None, "xg_trasferta": 1.0 if giocata else None,
                        "understat_id": 100 + g})
        if not giocata:
            continue
        for cid, nome, ruolo, sq, gol, rig in ((1, "Bomber", "A", "alfa", 1, 1), (2, "Portiere", "P", "beta", 0, 0),
                                               (3, "Mediano", "C", "beta", 0, 0)):
            voti.append({"stagione": ST, "giornata": g, "calciatore_id": cid, "nome": nome, "squadra": sq,
                         "ruolo": ruolo, "voto_red": 6.5 if gol else 6.0, "fv_red": 0, "voto_stat": 6, "fv_stat": 0,
                         "voto_ita": 6, "fv_ita": 0, "gol": gol, "gol_subiti": 1 if ruolo == "P" else 0, "autogol": 0,
                         "rig_segnati": rig, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0,
                         "ammonizioni": 0, "espulsioni": 0, "subentrato": 0, "sostituito": 0,
                         "data": f"2026-09-{g:02d} 15:00"})
            prest.append({"understat_partita": 100 + g, "understat_giocatore": cid, "squadra": sq, "posizione": "",
                          "minuti": 90, "gol": gol + rig, "autogol": 0, "tiri": 3, "xg": 0.8 + 0.76 * rig, "xa": 0.1,
                          "assist": 0, "passaggi_chiave": 1, "xg_chain": 0, "xg_buildup": 0, "gialli": 0, "rossi": 0,
                          "rigori_calciati": rig, "rigori_segnati": rig, "punizioni": 0, "entrato": 0, "uscito": 0,
                          "stagione": ST, "giornata": g, "calciatore_id": cid, "data": f"2026-09-{g:02d} 15:00"})
    voti += list(voti_extra)
    d = modello.Dati([ST], pd.DataFrame(voti), pd.DataFrame(prest), pd.DataFrame(partite),
                     pd.DataFrame([{"id": 1, "nome": "Bomber", "ruolo": "A", "squadra": "ALF", "squadra_slug": "alfa", "quotazione": 30},
                                   {"id": 2, "nome": "Portiere", "ruolo": "P", "squadra": "BET", "squadra_slug": "beta", "quotazione": 10},
                                   {"id": 3, "nome": "Mediano", "ruolo": "C", "squadra": "BET", "squadra_slug": "beta", "quotazione": 5}]))
    for df in (d.voti, d.prestazioni, d.partite):
        df["t"] = df["giornata"]
    rig = d.prestazioni.groupby(["understat_partita", "squadra"])["rigori_calciati"].sum().rename("rigori_squadra")
    d.prestazioni = d.prestazioni.join(rig, on=["understat_partita", "squadra"])
    return d


def _p(d, giornata=5, regole=None, probabili=None):
    return modello.previsioni(d, ST, giornata, regole or Regole(), probabili=probabili).set_index("id")


def test_niente_dati_dal_futuro():
    # un voto "dal futuro" (giornata 5, quella da prevedere) non deve cambiare nulla
    futuro = {"stagione": ST, "giornata": 5, "calciatore_id": 1, "nome": "Bomber", "squadra": "alfa", "ruolo": "A",
              "voto_red": 10.0, "fv_red": 0, "voto_stat": 10, "fv_stat": 0, "voto_ita": 10, "fv_ita": 0, "gol": 5,
              "gol_subiti": 0, "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 3,
              "mvp": 0, "ammonizioni": 0, "espulsioni": 0, "subentrato": 0, "sostituito": 0,
              "data": "2026-09-05 15:00"}
    a, b = _p(_dati()), _p(_dati([futuro]))
    assert a.at[1, "mu"] == pytest.approx(b.at[1, "mu"])


def test_bomber_e_rigorista():
    p = _p(_dati())
    assert p.at[1, "e_gol"] > p.at[3, "e_gol"]
    assert p.at[1, "e_rigori"] > 0 and p.at[3, "e_rigori"] == 0
    assert p.at[1, "mu"] > p.at[3, "mu"]


def test_regole_della_lega_cambiano_il_fantavoto_atteso():
    d = _dati()
    base = _p(d)
    piu_gol = _p(d, regole=imposta(Regole(), "bonus.gol.A", "6"))
    assert piu_gol.at[1, "mu"] > base.at[1, "mu"]
    assert piu_gol.at[3, "mu"] == pytest.approx(base.at[3, "mu"])     # il centrocampista non cambia


def test_portiere_gol_subiti_e_imbattibilita():
    p = _p(_dati())
    assert 0 < p.at[2, "p_imbattuto"] < 1 and p.at[2, "gol_subiti"] > 0
    meno_malus = _p(_dati(), regole=imposta(Regole(), "bonus.gol_subito_portiere", "0"))
    assert meno_malus.at[2, "mu"] > p.at[2, "mu"]


def test_probabili_formazioni():
    prob = pd.DataFrame([
        {"calciatore_id": 1, "stato": "infortunato", "percentuale": 0.0, "in_dubbio": 0, "nota": "ko"},
        {"calciatore_id": 2, "stato": "titolare", "percentuale": 90.0, "in_dubbio": 0, "nota": None},
    ])
    p = _p(_dati(), probabili=prob)
    assert p.at[1, "p_voto"] == 0
    assert p.at[2, "p_voto"] > 0.8
    assert p.at[3, "p_voto"] < 0.05          # non citato nelle probabili


def test_probabili_senza_percentuale():
    """La pagina delle probabili a volte non ha la barra della percentuale: nel database è NULL e pandas la legge come NaN.
    Prima p_voto diventava NaN (titolare trattato come se non giocasse mai, e la risposta all'app falliva con un NaN nel JSON)."""
    prob = pd.DataFrame([
        {"calciatore_id": 2, "stato": "titolare", "percentuale": float("nan"), "in_dubbio": 0, "nota": None},
        {"calciatore_id": 3, "stato": "panchina", "percentuale": float("nan"), "in_dubbio": 0, "nota": None},
        {"calciatore_id": 1, "stato": "titolare", "percentuale": 90.0, "in_dubbio": 0, "nota": None},
    ])
    p = _p(_dati(), probabili=prob)
    assert p["p_voto"].notna().all() and p["atteso"].notna().all()
    assert p.at[2, "p_voto"] == pytest.approx(modello._p_da_probabili("titolare", None, False), abs=1e-3)
    assert p.at[3, "p_voto"] == pytest.approx(modello._p_da_probabili("panchina", None, False), abs=1e-3)


def test_recupero_giocato_dopo_non_e_usato():
    """Una partita della giornata 2 recuperata dopo l'inizio della 5 non deve entrare nella previsione della 5."""
    d = _dati()
    d.partite.loc[d.partite["giornata"] == 2, "data"] = "2026-10-30 15:00"
    for df in (d.voti, d.prestazioni):
        df.loc[df["giornata"] == 2, "data"] = "2026-10-30 15:00"
    con, senza = _p(d), _p(_dati())
    assert con.at[1, "presenze_pesate"] < senza.at[1, "presenze_pesate"]


def test_forza_squadre_senza_quote():
    """Chi ha segnato di più e subito meno ha più gol attesi; il fattore campo c'è; i gol attesi sono sempre positivi."""
    d = _dati()
    d.partite.loc[d.partite["casa"] == "alfa", ["gol_casa", "xg_casa"]] = 3
    d.partite.loc[d.partite["trasferta"] == "alfa", ["gol_trasferta", "xg_trasferta"]] = 3
    f = modello.forza_squadre(d, ST, 5, modello.Parametri())
    assert f.attacco["alfa"] > f.attacco["beta"] and f.difesa["alfa"] < f.difesa["beta"]
    lc, lt = f.gol_attesi("alfa", "beta")
    assert lc > lt > 0
    assert not hasattr(modello.Parametri(), "peso_quote")


def test_forza_squadre_senza_partite():
    d = _dati()
    f = modello.forza_squadre(d, ST, 1, modello.Parametri())
    assert f.attacco == {} and f.gol_attesi("alfa", "beta")[0] > 0


def test_senza_nessun_xg_le_previsioni_ci_sono_lo_stesso():
    """Understat non ha dato nessun xG (colonne tutte vuote, come su un'installazione nuova): il modello usa i gol veri
    e non si ferma con un errore 500."""
    d = _dati()
    d = modello.Dati(d.stagioni, d.voti, d.prestazioni.assign(xg=None, xa=None),
                     d.partite.assign(xg_casa=None, xg_trasferta=None), d.calciatori, d.quotazioni, d.extra)
    p = _p(d)
    assert len(p) == 3
    assert p["mu"].notna().all()


def test_pezzi_condivisi_fra_leghe_stessi_numeri():
    """Una lega con bonus diversi riusa i pezzi gia' calcolati per un'altra (stessa fonte del voto): numeri identici a un calcolo da zero."""
    altre = imposta(imposta(Regole(), "bonus.gol.A", "4.5"), "bonus.gol_subito_portiere", "-0.5")
    prob = pd.DataFrame([{"calciatore_id": 1, "squadra": "alfa", "stato": "titolare", "percentuale": 80.0, "nota": None,
                          "in_dubbio": 0, "diffidato": 0}])
    for probabili in (None, prob):
        d = _dati()
        _p(d, probabili=probabili)                                    # prima lega: calcola e ricorda
        assert d._pezzi
        condivise = _p(d, regole=altre, probabili=probabili)          # seconda lega: riusa
        da_zero = _p(_dati(), regole=altre, probabili=probabili)
        pd.testing.assert_frame_equal(condivise, da_zero, check_exact=True)
    d = _dati()
    for g in range(1, 6):                                          # il ricordo ha un tetto
        for par in (modello.Parametri(), modello.Parametri(k_voto=10.0), modello.Parametri(k_voto=30.0), modello.Parametri(k_90=8.0)):
            modello.previsioni(d, ST, g, Regole(), par)
    assert len(d._pezzi) <= modello.MAX_PEZZI
