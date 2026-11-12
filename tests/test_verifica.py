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


def test_gli_avversari_non_vedono_i_voti_della_giornata_stessa(finto):
    """La giornata da prevedere non è fra i dati dell'avversario: i suoi voti sono la risposta. Con «fino alla giornata
    compresa» il 6 (mai visto prima) avrebbe una fantamedia e il ruolo dei centrocampisti un voto in più."""
    d = _dati([_voto(S2, 1, 4, 6.0), _voto(S2, 2, 4, 10.0), _voto(S2, 2, 6, 9.0), _voto(S2, 2, 12, 9.0)])
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    assert ruolo == {"D": 6.0} and list(tirata.index) == [4] and tirata[4] == pytest.approx(6.0)


def test_la_formazione_da_fantamedia_si_sceglie_con_la_fantamedia_tirata(finto, monkeypatch):
    """Sulle rose della lega la formazione «da fantamedia» (l'avversario dei punti) si sceglie con la fantamedia tirata verso il
    ruolo, chi non ha voti con la media del ruolo: non con la fantamedia della sola stagione (6 a chi non ha voti)."""
    voti = [_voto(S1, g, i, 4.0 + (i % 5)) for g in range(1, 7) for i in range(1, 26) if i % 4]     # chi ha l'id multiplo di 4 mai
    voti += [_voto(S2, 1, i, 9.0 - (i % 5)) for i in range(1, 26) if i % 4]                          # in questa stagione al contrario
    voti += [_voto(S2, 2, i, 6.0) for i in range(1, 26)]
    d = _dati(voti)
    scelte, vera = [], fz.migliore
    monkeypatch.setattr(fz, "migliore", lambda rosa, *a, **k: scelte.append({g.id: g.mu for g in rosa}) or vera(rosa, *a, **k))
    verifica.verifica_giornata(d, S2, 2, Regole(), Parametri(), rose=[list(range(1, 26))], simulazioni=20)
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    attese = {i: float(tirata[i]) if i in tirata.index else ruolo[RUOLI[i - 1]] for i in range(1, 26)}
    assert len(scelte) == 2 and scelte[1] == pytest.approx(attese)                   # la seconda scelta è quella «da fantamedia»
    assert scelte[1] != pytest.approx({i: verifica._fantamedia(d, S2, 2, Regole()).get(i, 6.0) for i in range(1, 26)})


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


def test_con_il_voto_d_ufficio_il_massimo_sale_alla_formazione_con_i_buchi(finto):
    """Il caso in cui il conto del massimo (solo chi ha preso voto) sta davvero sotto una formazione: voto d'ufficio 6 a chi non
    ha voto né sostituto, niente cambi, e gli undici con il voto hanno preso tutti 3. Le formazioni scelte prima (fantavoto atteso
    più alto, id alti) hanno molti buchi e fanno più di 33: il massimo mostrato è il loro, sulle rose della lega e su quelle a sorte."""
    r = imposta(Regole(), "panchina.max_sostituzioni", "0")
    r.voto_senza_sostituto = 6.0
    con_voto = [1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21]                                # un 4-4-2 con voto, gli id bassi
    voti = [_voto(S2, 1, i, 6.0) for i in range(1, 26)] + [_voto(S2, 2, i, 3.0) for i in con_voto]
    e = verifica.verifica_giornata(_dati(voti), S2, 2, r, Parametri(), rose=[list(range(1, 26))], simulazioni=30,
                                   sintetiche=2, sorte=True)
    assert verifica._perfetta(_rosa(), {i: 3.0 for i in con_voto}, r) == 33.0
    f = e.formazioni
    assert max(f["modello"], f["fantamedia"]) > 33.0
    assert f["perfetta"] == pytest.approx(max(f["modello"], f["fantamedia"]))
    assert e.sorte and all(massimo == pytest.approx(max(reale, semplice)) and massimo > 33.0 for reale, semplice, massimo in e.sorte)


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


# ---------------------------------------------------------------- affidabilità («Quanto è affidabile il modello»)
def test_affidabilita_porta_gli_avversari_onesti_e_le_rose_a_sorte(finto, monkeypatch, tmp_path):
    from fanta import affidabilita, archivio, consigli
    voti = [_voto(st, g, i, 5.0 + (i * g) % 4) for st in (S1, S2) for g in range(1, 7) for i in range(1, 26)]
    d = _dati(voti)
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(1, 7):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2026-09-01 18:00', "
                   "'a', 'b', 1)", (100 + g, S2, g))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: S2)
    monkeypatch.setattr(consigli, "dati", lambda db: d)
    monkeypatch.setattr(verifica, "ROSE_A_SORTE", 3)
    r = affidabilita.calcola(db, Regole(), None, simulazioni=30)
    s = r["sintesi"]
    assert s["giornate"] == 6 and {"errore_modello", "errore_fantamedia", "errore_ruolo", "errore_fantamedia_stagione"} <= set(s)
    assert s["rose_a_sorte"]["casi"] == 18 and s["rose_a_sorte"]["basso"] <= s["rose_a_sorte"]["differenza"] <= s["rose_a_sorte"]["alto"]
    assert "sorte_modello" in r["righe"][0]
    import json
    json.dumps(r)                              # tutto si scrive nel file dell'affidabilità


def test_d_estate_la_prova_non_si_rifa_a_ogni_giro(monkeypatch, tmp_path):
    """D'estate la stagione in corso non ha giornate finite e la prova usa le ultime della precedente: si rifà solo quando ne
    finisce una nuova. Prima la chiave guardava solo la stagione in corso e la prova (con 20 rose a sorte in più per giornata)
    ripartiva a ogni giro del cron (revisione di #642)."""
    from fanta import affidabilita, archivio, consigli
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(30, 39):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2027-05-01 18:00', "
                   "'a', 'b', 1)", (g, S2, g))
    db.commit()
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2027-28")
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    prove = []

    def finta(d, regole, par, giornate, **k):
        prove.append(list(giornate))
        return pd.DataFrame([{"stagione": s, "giornata": g, "quadratico_modello": 2.0, "quadratico_fantamedia": 2.1} for s, g in giornate])
    monkeypatch.setattr(verifica, "verifica", finta)
    f = tmp_path / "affidabilita.json"
    assert [affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) for _ in range(3)] == [True, False, False]
    assert len(prove) == 1 and prove[0][-1] == (S2, 38) and affidabilita.carica(f)["ultima"] == f"{S2}/38"
    # finisce la prima giornata della stagione nuova: si rifà, una volta
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (99, '2027-28', 1, "
               "'2027-08-22 18:00', 'a', 'b', 1)")
    db.commit()
    assert [affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) for _ in range(2)] == [True, False]
    assert len(prove) == 2 and prove[1][-1] == ("2027-28", 1)


# ---------------------------------------------------------------- il comando su un archivio vuoto
def test_riepilogo_senza_giornate_verificate_lo_dice():
    righe = []
    verifica.stampa_riepilogo(pd.DataFrame(), scrivi=righe.append)
    assert len(righe) == 1 and righe[0].startswith("Nessuna giornata verificata")


def test_verifica_su_un_archivio_vuoto_esce_con_un_messaggio(monkeypatch, tmp_path):
    """`python -m fanta verifica` con l'archivio vuoto: prima una traccia (KeyError 'stagione'), ora un messaggio e l'uscita."""
    from fanta import __main__ as cli
    from fanta import archivio
    vuoto = archivio.apri(tmp_path / "vuoto.sqlite")
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vuoto)
    with pytest.raises(SystemExit) as uscita:
        cli.main(["verifica"])
    assert isinstance(uscita.value.code, str) and "nessuna giornata giocata" in uscita.value.code

