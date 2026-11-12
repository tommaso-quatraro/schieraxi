"""Le misure di `verifica` (#614): avversari onesti (numero fisso per ruolo, fantamedia tirata verso il ruolo), massimo possibile
con le regole della lega, punti su rose estratte a sorte con l'intervallo a gruppi di giornata. Dati inventati."""
import itertools
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fanta import formazione as fz
from fanta import verifica
from fanta.modello import Parametri
from fanta.regole import Regole, imposta

S1, S2 = "2025-26", "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25


def _voto(st, g, i, voto, ruolo=None):
    return {"stagione": st, "giornata": g, "calciatore_id": i, "ruolo": ruolo or RUOLI[i - 1], "voto_red": voto}


def _dati(voti):
    partite = pd.DataFrame([{"id": 100 * k + g, "stagione": st, "giornata": g, "giocata": 1}
                            for k, st in enumerate((S1, S2)) for g in range(1, 7)])
    return SimpleNamespace(stagioni=[S1, S2], partite=partite, voti=pd.DataFrame(voti))


@pytest.fixture
def finto(monkeypatch):
    """Il fantavoto è il voto; le previsioni danno a tutti i 25 giocatori 0,9 di giocare e un fantavoto atteso che cresce con l'id."""
    def previsioni(d, stagione, giornata, regole, par, oracolo=None):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0,
                              "partita": 100 * (stagione == S2) + giornata} for i in range(1, 26)])
    monkeypatch.setattr(verifica, "previsioni", previsioni)
    monkeypatch.setattr(verifica, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))


# ---------------------------------------------------------------- avversari onesti
def test_avversari_numero_fisso_per_ruolo_e_fantamedia_tirata(finto):
    # difensori: il 4 ha preso 8 e 8 la stagione scorsa e 5 in questa; il 5 un solo 6; il 6 non ha mai giocato
    d = _dati([_voto(S1, 1, 4, 8.0), _voto(S1, 2, 4, 8.0), _voto(S2, 1, 4, 5.0), _voto(S2, 1, 5, 6.0),
               _voto(S2, 1, 20, 7.0), _voto(S2, 3, 4, 10.0)])                       # l'ultimo è dopo la giornata 2: non conta
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    assert ruolo == {"D": pytest.approx(27 / 4), "A": pytest.approx(7.0)}             # media di tutti i voti del ruolo, di prima
    k = verifica.PRESENZE_FITTIZIE
    assert tirata[4] == pytest.approx((21 + k * 6.75) / (3 + k))                      # tutta la storia, tirata verso il ruolo
    assert tirata[5] == pytest.approx((6 + k * 6.75) / (1 + k))
    assert 6 not in tirata.index                                                      # senza voti: chi chiama usa la media del ruolo
    # la fantamedia di prima (solo la stagione in corso) resta quella: serve a S2 e si stampa per confronto
    assert verifica._fantamedia(d, S2, 2, Regole()).to_dict() == {4: 5.0, 5: 6.0, 20: 7.0}


def test_verifica_misura_il_modello_contro_gli_avversari_onesti(finto):
    voti = [_voto(S1, g, i, 6.0 + (i % 3) * 0.5) for g in range(1, 7) for i in range(1, 26)]
    voti += [_voto(S2, g, i, 6.0 + (i % 3) * 0.5) for g in range(1, 3) for i in range(1, 26)]
    d = _dati(voti)
    e = verifica.verifica_giornata(d, S2, 2, Regole(), Parametri())
    # ognuno prende sempre lo stesso voto: la fantamedia tirata sbaglia poco, il numero fisso per ruolo di più, e con sette
    # presenze la fantamedia della sola stagione (una presenza) è uguale al voto vero
    assert 0 < e.quadratico_fantamedia < e.quadratico_ruolo
    assert e.quadratico_fantamedia_stagione == pytest.approx(0.0)
    assert e.errore_ruolo > e.errore_fantamedia > 0
    t = verifica.verifica(d, Regole(), Parametri(), [(S2, 2)], scrivi=None)
    assert {"quadratico_ruolo", "quadratico_fantamedia_stagione", "errore_ruolo"} <= set(t.columns)


# ---------------------------------------------------------------- massimo possibile
def _rosa():
    return [fz.Giocatore(i, f"G{i}", RUOLI[i - 1], 0.9, 6.0, 6.0) for i in range(1, 26)]


def _con_modificatore():
    r = Regole()
    r.modificatore_difesa.attivo, r.modificatore_difesa.min_difensori = True, 4
    r.modificatore_difesa.soglie = [[6.0, 1.0], [6.5, 3.0], [7.0, 6.0]]
    return r


def test_massimo_possibile_conta_il_modificatore_della_difesa():
    """Tutti prendono fantavoto e voto 6 tranne quattro difensori con voto 7,5: senza modificatore il massimo è 66; con il
    modificatore conviene schierare 4 difensori (media di portiere e tre migliori 7,1: +6)."""
    fv = {i: 6.0 for i in range(1, 26)}
    voto = dict(fv) | {4: 7.5, 5: 7.5, 6: 7.5, 7: 7.5}
    assert verifica._perfetta(_rosa(), fv, Regole(), voto) == 66.0
    assert verifica._perfetta(_rosa(), fv, _con_modificatore()) == 66.0             # senza i voti resta il conto di prima
    assert verifica._perfetta(_rosa(), fv, _con_modificatore(), voto) == 72.0


def test_massimo_possibile_sceglie_i_difensori_per_fantavoto_e_modificatore_insieme():
    """Il difensore con il fantavoto più alto (9, per un gol) ha il voto basso: il massimo tiene lui e i tre con il voto alto."""
    fv = {i: 6.0 for i in range(1, 26)} | {4: 9.0}
    voto = {i: 6.0 for i in range(1, 26)} | {4: 5.0, 5: 7.5, 6: 7.5, 7: 7.5, 1: 7.5}
    assert verifica._perfetta(_rosa(), fv, _con_modificatore(), voto) == 66.0 + 3.0 + 6.0


@pytest.mark.parametrize("seme", range(6))
def test_il_massimo_possibile_non_e_mai_sotto_una_formazione_schierata(seme):
    """Con il modificatore della difesa e il cambio di modulo: nessuna formazione di giocatori con voto fa più del massimo."""
    rng = np.random.default_rng(seme)
    r = imposta(_con_modificatore(), "panchina.max_sostituzioni", "0")
    rosa = _rosa()
    con_voto = [g for g in rosa if rng.random() < 0.8]
    fv = {g.id: float(np.round(rng.normal(6.3, 1.5) * 2) / 2) for g in con_voto}
    voto = {g.id: float(np.round(rng.normal(6.1, 0.6) * 2) / 2) for g in con_voto}
    gioca = {g.id: g.id in fv for g in rosa}
    massimo = verifica._perfetta(rosa, fv, r, voto)
    per_ruolo = {ru: [g for g in con_voto if g.ruolo == ru] for ru in "PDCA"}
    for modulo in r.moduli:
        d, c, a = (int(x) for x in modulo.split("-"))
        if any(len(per_ruolo[ru]) < n for ru, n in zip("PDCA", (1, d, c, a))):
            continue
        for _ in range(40):
            tit = [per_ruolo[ru][k] for ru, n in zip("PDCA", (1, d, c, a)) for k in rng.choice(len(per_ruolo[ru]), n, replace=False)]
            punti = fz.punteggio(tit, [], gioca, {g.id: fv.get(g.id, 0.0) for g in rosa}, {g.id: voto.get(g.id, 0.0) for g in rosa}, r)
            assert punti <= massimo + 1e-9, (modulo, punti, massimo)
    # ed è raggiunto da una formazione vera (forza bruta sui difensori del modulo migliore)
    migliori = []
    for modulo in r.moduli:
        d, c, a = (int(x) for x in modulo.split("-"))
        if any(len(per_ruolo[ru]) < n for ru, n in zip("PDCA", (1, d, c, a))):
            continue
        centro = sorted(per_ruolo["C"], key=lambda g: -fv[g.id])[:c] + sorted(per_ruolo["A"], key=lambda g: -fv[g.id])[:a]
        for p in per_ruolo["P"]:
            for dif in itertools.combinations(per_ruolo["D"], d):
                migliori.append(fz.punteggio([p, *dif, *centro], [], gioca, {g.id: fv.get(g.id, 0.0) for g in rosa},
                                             {g.id: voto.get(g.id, 0.0) for g in rosa}, r))
    assert massimo == pytest.approx(max(migliori))


def test_nella_verifica_il_massimo_non_sta_sotto_la_consigliata(finto):
    """Con il voto d'ufficio una formazione con un buco può fare più punti di undici giocatori con voto: il massimo mostrato non
    sta comunque sotto i punti delle formazioni valutate."""
    r = _con_modificatore()
    voti = [_voto(S2, g, i, 6.0 + (i % 4) * 0.5) for g in (1, 2) for i in range(1, 26)]
    e = verifica.verifica_giornata(_dati(voti), S2, 2, r, Parametri(), rose=[list(range(1, 26))], simulazioni=30)
    assert e.formazioni["perfetta"] >= max(e.formazioni["modello"], e.formazioni["fantamedia"])


# ---------------------------------------------------------------- punti su rose a sorte
def test_punti_su_rose_a_sorte_con_intervallo_a_gruppi_di_giornata(finto):
    voti = [_voto(st, g, i, 5.0 + (i * g) % 4) for st in (S1, S2) for g in range(1, 7) for i in range(1, 26)]
    d = _dati(voti)
    giornate = [(S2, g) for g in range(2, 7)]
    t = verifica.verifica(d, Regole(), Parametri(), giornate, simulazioni=30, scrivi=None, sintetiche=4)
    assert (t["sorte_casi"] == 4).all() and {"sorte_modello", "sorte_fantamedia", "sorte_perfetta", "sorte_differenza"} <= set(t.columns)
    assert (t["sorte_perfetta"] >= t[["sorte_modello", "sorte_fantamedia"]].max(axis=1) - 1e-9).all()
    r = verifica.riepilogo_sorte(t)[S2]
    assert r["casi"] == 20 and r["giornate"] == 5
    assert r["differenza"] == pytest.approx(r["modello"] - r["fantamedia"])
    assert r["basso"] <= r["differenza"] <= r["alto"]
    # senza rose a sorte la verifica è quella di sempre e il riepilogo è vuoto
    senza = verifica.verifica(d, Regole(), Parametri(), giornate, simulazioni=30, scrivi=None)
    assert "sorte_casi" not in senza.columns and verifica.riepilogo_sorte(senza) == {}
