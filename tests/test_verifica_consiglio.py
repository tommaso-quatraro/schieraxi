"""Misura in laboratorio del consiglio di formazione (#166, C1-C4): `python -m fanta verifica --consiglio`.
Dati inventati: rose finte e previsioni scritte a mano, niente archivio vero."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fanta import __main__ as cli
from fanta import archivio, lega, verifica
from fanta import formazione as fz
from fanta import verifica_consiglio as vc
from fanta.regole import Regole

ST = "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25


def G(id, ruolo, p=1.0, mu=6.0, voto=6.0):
    return fz.Giocatore(id, f"G{id}", ruolo, p, mu, voto)


def S(id, ruolo, p=0.9, punti=5.0, stato=None, perche=("gioca", "voti")):
    """Una scheda come quelle di `consigli.formazione` (solo i campi che la misura legge, con i valori veri dell'app)."""
    fuori = stato in ("infortunato", "squalificato")
    tit = "fuori" if fuori else "titolare" if p >= 0.8 else "ballottaggio" if p >= 0.5 else "panchina" if p >= 0.2 else "improbabile"
    return {"id": id, "nome": f"G{id}", "ruolo": ruolo, "p_voto": p, "punti_attesi": punti, "stato": stato,
            "titolarita": tit, "perche_numero": [{"chiave": c, "testo": c, "frase": None, "effetto": None} for c in perche]}


def F(titolari, panchina=(), fuori=(), incerti=(), modulo="3-4-3", scelta=None):
    """Una formazione come quella di `consigli.formazione`: titolari, panchina, fuori, schede di tutti, incerti per modulo e, se
    `scelta` non è None, le righe del perché della scelta (`perche_scelta`) del modulo scelto per quei titolari."""
    tutte = [*titolari, *panchina, *fuori]
    scelto = {"modulo": modulo, "incerti": [{"titolare": t, "riserva": r} for t, r in incerti]}
    if scelta is not None:
        scelto["perche_scelta"] = [{"titolare": t, "altro": 0, "testo": "riga", "frase": None} for t in scelta]
    altro = {"modulo": "4-4-2", "incerti": [{"titolare": 999, "riserva": 998}]}
    if scelta is not None:
        altro["perche_scelta"] = [{"titolare": t, "altro": 0, "testo": "riga", "frase": None} for t in (2, 3, 4)]
    return {"modulo": modulo, "titolari": list(titolari), "panchina": list(panchina), "fuori": list(fuori),
            "schede": {str(x["id"]): x for x in tutte}, "moduli": [altro, scelto]}


def _titolari_343(**cambi):
    """Gli 11 titolari sicuri del 3-4-3 (id 1-11); `cambi` = {id: scheda} per sostituirne qualcuno."""
    ruoli = ["P", "D", "D", "D", "C", "C", "C", "C", "A", "A", "A"]
    return [cambi.get(f"t{i}", S(i, r)) for i, r in enumerate(ruoli, start=1)]


# ------------------------------------------------------------------ S2, il riferimento semplice
def test_s2_gioca_chi_ha_preso_voto_la_giornata_prima_con_la_sua_fantamedia():
    rosa = [G(1, "P", p=0.3, mu=7.0, voto=6.4), G(2, "D", p=0.95, mu=6.5, voto=6.2)]
    s2 = vc.rosa_s2(rosa, ha_giocato={1}, fantamedia={1: 6.8})
    assert [(g.id, g.ruolo, g.p, g.mu, g.mu_voto) for g in s2] == [(1, "P", 0.9, 6.8, 6.0), (2, "D", 0.1, 5.5, 6.0)]


# ------------------------------------------------------------------ C3: titolari che non giocano
@pytest.mark.parametrize("titolare, panchina, atteso", [
    (S(2, "D", p=0.1), [S(20, "D", p=0.7)], [(2, 20)]),                              # improbabile, compagno al 70%
    (S(2, "D", p=0.2), [S(20, "D", p=0.7)], []),                                     # 20% giusto: non è improbabile
    (S(2, "D", p=0.1), [S(20, "D", p=0.49)], [(2, 20)]),                             # dal 12/11/2026 basta un compagno al 20%
    (S(2, "D", p=0.1), [S(20, "D", p=0.2)], [(2, 20)]),                              # 20% giusto: il compagno conta
    (S(2, "D", p=0.1), [S(20, "D", p=0.19)], [(2, None)]),                           # compagno sotto il 20%
    (S(2, "D", p=0.1), [S(20, "D", p=0.6, stato="infortunato")], [(2, None)]),       # compagno fuori
    (S(2, "D", p=0.1), [S(20, "C", p=0.9)], [(2, None)]),                            # compagno di un altro ruolo
    (S(2, "D", p=0.6, stato="squalificato"), [S(20, "D", p=0.7)], [(2, 20)]),        # titolare fuori
    (S(2, "D", p=0.1), [S(20, "D", p=0.7, punti=3.0), S(21, "D", p=0.9, punti=4.5)], [(2, 21)]),   # il compagno migliore
])
def test_titolari_che_non_giocano_e_compagno_sicuro(titolare, panchina, atteso):
    f = F(_titolari_343(t2=titolare), panchina)
    assert vc.non_giocano(f) == atteso


def test_le_soglie_di_chi_gioca_sono_quelle_con_cui_l_app_sceglie():
    """C3 misura la regola con cui l'app toglie i titolari improbabili (`formazione._senza_improbabili`): le due soglie si leggono
    da lì, non si ricopiano. Fino a #612 il compagno doveva giocare almeno il 50%, e qui era rimasto quel numero (#614)."""
    assert vc.IMPROBABILE_SOTTO == fz.IMPROBABILE_SOTTO
    assert vc.COMPAGNO_DA == fz.COMPAGNO_ALMENO


def test_compagno_anche_tra_i_fuori_dalla_panchina_ma_mai_un_altro_titolare():
    f = F(_titolari_343(t2=S(2, "D", p=0.05)), panchina=[S(20, "P")], fuori=[S(30, "D", p=0.8)])
    assert vc.non_giocano(f) == [(2, 30)]
    f = F(_titolari_343(t2=S(2, "D", p=0.05)), panchina=[S(20, "P")])      # i difensori al 90% sono tutti titolari
    assert vc.non_giocano(f) == [(2, None)]


def test_costo_di_mettere_il_compagno_al_posto_dell_improbabile():
    # D2 gioca il 10% e se gioca fa 10; D20 gioca sempre e fa 6, ed è il primo della panchina: oggi D2 vale 0,1 x 10 + 0,9 x 6
    # = 6,4 (quando non gioca entra D20); con D20 titolare la squadra fa sempre 66. Costo: 66,4 - 66 = 0,4 punti attesi.
    rosa = [G(1, "P"), G(2, "D", p=0.1, mu=10.0), G(3, "D"), G(4, "D"), G(5, "C"), G(6, "C"), G(7, "C"), G(8, "C"),
            G(9, "A"), G(10, "A"), G(11, "A"), G(20, "D")]
    val = fz.Valutatore(rosa, Regole(), 600)
    assert vc.costo_compagno(rosa, list(range(1, 12)), Regole(), val, 2, 20) == pytest.approx(0.4, abs=0.1)


# ------------------------------------------------------------------ C4: scelte che sembrano storte e perché
def test_scelte_storte_per_reparto_e_quelle_spiegate_dagli_incerti():
    tit = _titolari_343(t2=S(2, "D", punti=4.0), t3=S(3, "D", punti=5.0), t4=S(4, "D", punti=4.5),
                        t5=S(5, "C", punti=6.0), t6=S(6, "C", punti=6.0), t7=S(7, "C", punti=6.0), t8=S(8, "C", punti=6.0))
    pan = [S(20, "D", punti=4.2), S(21, "C", punti=5.9), S(22, "C", punti=6.0)]   # D storta; C: 5,9 e 6,0 non battono 6,0
    assert vc.scelte_storte(F(tit, pan)) == {"reparti": 2, "storte": 1, "spiegate": 0}
    # la nota «titolare anche se incerto» del modulo scelto spiega la scelta (quella di un altro modulo no)
    assert vc.scelte_storte(F(tit, pan, incerti=[(2, 20)])) == {"reparti": 2, "storte": 1, "spiegate": 1}
    assert vc.scelte_storte(F(tit, pan, incerti=[(3, 20)])) == {"reparti": 2, "storte": 1, "spiegate": 0}


def test_scelte_storte_spiegate_dalla_riga_del_perche_della_scelta():
    """Con il campo `perche_scelta` (#356) conta la riga sotto il campo del titolare più debole, come la mostra l'app; quelle di
    un altro modulo no, e la nota degli incerti vale solo per un server senza il campo."""
    tit = _titolari_343(t2=S(2, "D", punti=4.0), t3=S(3, "D", punti=5.0), t4=S(4, "D", punti=4.5))
    pan = [S(20, "D", punti=4.2)]
    assert vc.scelte_storte(F(tit, pan, scelta=[2])) == {"reparti": 1, "storte": 1, "spiegate": 1}
    assert vc.scelte_storte(F(tit, pan, scelta=[3])) == {"reparti": 1, "storte": 1, "spiegate": 0}
    assert vc.scelte_storte(F(tit, pan, incerti=[(2, 20)], scelta=[])) == {"reparti": 1, "storte": 1, "spiegate": 0}


def test_perche_vuoto_e_senza_un_motivo_proprio():
    tit = _titolari_343(t1=S(1, "P", perche=()), t2=S(2, "D", perche=("gioca", "partita")), t3=S(3, "D", perche=("altro",)),
                        t4=S(4, "D", perche=("gioca", "gol")))
    pan = [S(20, "D", perche=())]                                   # la panchina non conta
    # titolari 5-11 hanno «voti»: un motivo proprio
    assert vc.perche_titolari(F(tit, pan)) == {"titolari": 11, "vuoti": 1, "senza_motivo": 3}


# ------------------------------------------------------------------ C2: stabilità
def _rosa_netta(p=0.95):
    """11 buoni (fantavoto atteso 8) che stanno solo nel 4-4-2, gli altri scarsi (4): nessun ritocco cambia la scelta."""
    buoni = {1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21}
    return [G(i, RUOLI[i - 1], p=p, mu=8.0 if i in buoni else 4.0) for i in range(1, 26)]


def test_stabilita_con_dati_netti_nessun_cambio():
    rosa = _rosa_netta()
    base = fz.migliore(rosa, Regole(), 200)
    prove = vc.stabilita(rosa, [g.id for g in base.titolari], base.modulo, Regole(), 200, np.random.default_rng(1))
    assert [p.tipo for p in prove] == ["seme"] * len(vc.SEMI) + ["ritocco"] * vc.RITOCCHI
    assert all(p.cambiati == 0 and not p.modulo_cambiato and p.guadagno == pytest.approx(0.0) for p in prove)


def test_stabilita_conta_i_titolari_cambiati_e_quanto_vale_la_nuova():
    # si parte da una scelta peggiore: l'attaccante scarso 22 al posto del buono 20, tutti giocano sempre. Ogni prova rimette
    # il 20: 1 titolare cambiato, stesso modulo. Con il solo seme nessuno manca mai: la nuova vale 8 - 4 = 4 punti attesi in più.
    # Con il ritocco ognuno gioca il 97-99% e quando un titolare manca entra il 20 dalla panchina: un po' meno, sempre sopra 1.
    rosa = _rosa_netta(p=1.0)
    base = [1, 4, 5, 6, 7, 12, 13, 14, 15, 22, 21]
    prove = vc.stabilita(rosa, base, "4-4-2", Regole(), 600, np.random.default_rng(1))
    assert all(p.cambiati == 1 and not p.modulo_cambiato and not p.motivata for p in prove)
    assert [p.guadagno for p in prove if p.tipo == "seme"] == [pytest.approx(4.0)] * len(vc.SEMI)
    assert all(2.5 < p.guadagno < 4.0 for p in prove if p.tipo == "ritocco")
    assert vc.riassumi(prove, "ritocco")["sotto_soglia"] == 0


def test_stabilita_ripetibile_con_lo_stesso_seme():
    rng = np.random.default_rng(3)
    rosa = [G(i, RUOLI[i - 1], p=float(rng.uniform(0.3, 0.95)), mu=float(rng.uniform(5.5, 7.0))) for i in range(1, 26)]
    base = fz.migliore(rosa, Regole(), 200)
    ids = [g.id for g in base.titolari]
    una = vc.stabilita(rosa, ids, base.modulo, Regole(), 200, np.random.default_rng(42))
    due = vc.stabilita(rosa, ids, base.modulo, Regole(), 200, np.random.default_rng(42))
    assert una == due


def test_cambio_motivato_solo_se_un_titolare_diventa_improbabile():
    prima, dopo = {1: 0.25, 2: 0.15, 3: 0.9}, {1: 0.18, 2: 0.12, 3: 0.85}
    assert vc.motivata(prima, dopo, [1, 3]) is True            # 1 scende sotto il 20%
    assert vc.motivata(prima, dopo, [2, 3]) is False           # 2 era già sotto: non è una novità


def test_riassunto_della_stabilita():
    P = vc.Prova
    prove = [P("ritocco", 0, False, 0.0), P("ritocco", 3, True, 0.04), P("ritocco", 1, False, 1.5),
             P("ritocco", 2, False, 0.2, motivata=True), P("seme", 1, False, 0.01)]
    assert vc.riassumi(prove, "ritocco") == {"prove": 4, "almeno_uno": 3, "tre_o_piu": 1, "modulo": 1,
                                             "mediana_guadagno": pytest.approx(0.2), "sotto_soglia": 1}
    assert vc.riassumi(prove, "seme")["sotto_soglia"] == 1
    assert vc.riassumi([], "seme") == {"prove": 0, "almeno_uno": 0, "tre_o_piu": 0, "modulo": 0,
                                       "mediana_guadagno": None, "sotto_soglia": 0}


# ------------------------------------------------------------------ parte B: una squadra con la formazione dell'app
def test_caso_dell_app_mette_insieme_c3_c4_e_stabilita():
    rosa = [G(1, "P"), G(2, "D", p=0.1, mu=10.0), G(3, "D"), G(4, "D"), G(5, "C"), G(6, "C"), G(7, "C"), G(8, "C"),
            G(9, "A"), G(10, "A"), G(11, "A"), G(20, "D")]
    f = F(_titolari_343(t1=S(1, "P", perche=()), t2=S(2, "D", p=0.1, punti=1.0)), [S(20, "D", p=1.0, punti=6.0)])
    c = vc.caso_app(f, rosa, Regole(), 300, np.random.default_rng(1))
    assert c["titolari"] == 11 and c["non_giocano"] == 1 and c["con_compagno"] == 1
    assert c["costi"] == [pytest.approx(0.4, abs=0.15)]
    assert (c["reparti"], c["storte"], c["spiegate"]) == (1, 1, 0) and (c["vuoti"], c["senza_motivo"]) == (1, 1)
    assert len(c["prove"]) == len(vc.SEMI) + vc.RITOCCHI


# ------------------------------------------------------------------ parte A: giornate già giocate
@pytest.fixture
def giocate(monkeypatch):
    """Tre giornate giocate: tutti prendono 6, l'attaccante 25 prende 9. Il modello lo dà quasi sicuro fuori (gioca 5%): la
    consigliata e S1 (che usa il «gioca N%» del modello) non lo schierano e fanno 66; S2 vede che ha preso voto la giornata prima,
    lo schiera e fa 69 come il senno di poi. Il portiere 3 (il migliore per il modello) non prende voto dalla giornata 2: è
    titolare della consigliata senza voto, ed entra la riserva."""
    partite = pd.DataFrame([{"id": g, "stagione": ST, "giornata": g, "giocata": 1} for g in (1, 2, 3)])
    voti = pd.DataFrame([{"stagione": ST, "giornata": g, "calciatore_id": i, "ruolo": RUOLI[i - 1],
                          "voto_red": 9.0 if i == 25 else 6.0} for g in (1, 2, 3) for i in range(1, 26)
                         if not (i == 3 and g >= 2)])
    d = SimpleNamespace(partite=partite, voti=voti)

    def previsioni(d, stagione, giornata, regole, par):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.05 if i == 25 else 0.9,
                              "mu": 5.5 + i * 0.05, "mu_voto": 6.0, "partita": giornata} for i in range(1, 26)])
    monkeypatch.setattr(vc, "previsioni", previsioni)
    monkeypatch.setattr(vc, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(verifica, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26)])], "Mia")
    return SimpleNamespace(d=d, rose=rose)


def test_parte_giocate_confronta_consigliata_s1_s2_e_senno_di_poi(giocate):
    a = vc.parte_giocate(giocate.d, Regole(), giocate.rose, ST, simulazioni=60)
    assert a["giornate"] == [2, 3] and a["casi"] == 2
    assert a["punti"] == {"consigliata": 66.0, "s1": 66.0, "s2": 69.0, "perfetta": 69.0}
    assert a["differenza_s2"] == pytest.approx(-3.0) and a["casi_pari_s2"] == 0 and a["giornate_pari_s2"] == 0
    assert a["quota_perfetta"] == pytest.approx(100 * 66 / 69)
    assert a["senza_voto"] == {"consigliata": 1.0, "s2": 0.0} and a["scoperti"] == 0.0
    assert len(a["prove"]) == 2 * (len(vc.SEMI) + vc.RITOCCHI)


def test_il_senno_di_poi_conta_il_modificatore_della_difesa_della_lega(giocate):
    """In una lega con il modificatore il senno di poi lo conta (`verifica._perfetta` con i voti, #614): qui tutti hanno 6 in
    pagella, quindi con quattro difensori vale un punto in più dei 69 di prima."""
    r = Regole()
    r.modificatore_difesa.attivo = True
    a = vc.parte_giocate(giocate.d, r, giocate.rose, ST, simulazioni=60)
    assert a["punti"]["perfetta"] == 70.0
    assert a["punti"]["perfetta"] >= max(a["punti"][k] for k in ("consigliata", "s1", "s2"))


def test_il_senno_di_poi_non_sta_mai_sotto_una_formazione_valutata(giocate):
    """Con il voto d'ufficio un titolare senza voto e senza riserva può valere più di un voto vero: il portiere 3 non prende voto
    e la consigliata, che lo schiera, fa 70 contro i 69 dei migliori voti veri. Il senno di poi è almeno quello (come `verifica`)."""
    r = Regole()
    r.panchina.max_sostituzioni, r.voto_senza_sostituto = 0, 10.0
    a = vc.parte_giocate(giocate.d, r, giocate.rose, ST, simulazioni=60)
    assert a["punti"]["consigliata"] == 70.0
    assert a["punti"]["perfetta"] >= max(a["punti"][k] for k in ("consigliata", "s1", "s2"))
    assert a["quota_perfetta"] <= 100.0


def test_misura_senza_probabili_salta_la_parte_b_e_il_rapporto_lo_dice(giocate, tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        m = vc.misura(giocate.d, db, Regole(), giocate.rose, ST, simulazioni=60)
    finally:
        db.close()
    assert m["probabili"] is None and m["giocate"]["casi"] == 2
    e = vc.esiti(m)
    assert e["C1"] is False and e["C3"] is None and e["C4"] is None      # C2 dipende dai ritocchi: qui non si fissa a mano
    righe = []
    vc.rapporto(m, scrivi=righe.append)
    testo = "\n".join(righe)
    for c in ("C1", "C2", "C3", "C4"):
        assert c in testo
    assert "66,00" in testo and "69,00" in testo and "-3,00" in testo


# ------------------------------------------------------------------ esiti contro le soglie della proposta
def _misura(diff=0.66, sotto=0, compagno=0, storte=8, spiegate=8, senza=10, titolari=110):
    prove = [vc.Prova("ritocco", 0, False, 0.0)] + [vc.Prova("ritocco", 2, False, 0.04)] * sotto
    return {"giocate": {"casi": 57, "differenza_s2": diff, "prove": prove},
            "probabili": {"titolari": titolari, "con_compagno": compagno, "storte": storte, "spiegate": spiegate,
                          "senza_motivo": senza, "prove": []}}


@pytest.mark.parametrize("cambi, atteso", [
    ({}, {"C1": True, "C2": True, "C3": True, "C4": True}),
    ({"diff": -0.01}, {"C1": False, "C2": True, "C3": True, "C4": True}),
    ({"diff": 0.0}, {"C1": True, "C2": True, "C3": True, "C4": True}),                  # soglia: almeno 0
    ({"sotto": 1}, {"C1": True, "C2": False, "C3": True, "C4": True}),
    ({"compagno": 1}, {"C1": True, "C2": True, "C3": False, "C4": True}),
    ({"spiegate": 7}, {"C1": True, "C2": True, "C3": True, "C4": False}),
    ({"senza": 12}, {"C1": True, "C2": True, "C3": True, "C4": False}),                 # 12 su 110 = 10,9%: sopra il 10%
    ({"senza": 11}, {"C1": True, "C2": True, "C3": True, "C4": True}),                  # 11 su 110 = 10%: dentro
])
def test_esiti_contro_le_soglie(cambi, atteso):
    assert vc.esiti(_misura(**cambi)) == atteso


def test_senza_prove_ne_parti_gli_esiti_non_sono_misurati():
    assert vc.esiti({"giocate": {"casi": 0, "prove": []}, "probabili": None}) == {"C1": None, "C2": None, "C3": None, "C4": None}


def test_rapporto_completo_dice_i_numeri_della_proposta_in_italiano():
    m = _misura(compagno=9, storte=22, spiegate=8, senza=48)
    m["giocate"] |= {"stagione": ST, "giornate": [2, 3, 4, 5, 6, 7, 8], "errore_standard": 0.49, "casi_pari_s2": 39,
                     "giornate_pari_s2": 5, "quota_perfetta": 94.9, "scoperti": 1.18,
                     "punti": {"consigliata": 62.95, "s1": 62.32, "s2": 62.29, "perfetta": 66.47},
                     "senza_voto": {"consigliata": 3.28, "s2": 3.09}}
    m["probabili"] |= {"giornata": 9, "con_probabili": True, "squadre": 10, "non_giocano": 12, "squadre_non_giocano": 8,
                       "costi": [0.004, 0.13], "reparti": 40, "vuoti": 18}
    righe = []
    vc.rapporto(m, scrivi=righe.append)
    testo = "\n".join(righe)
    for frammento in ("+0,66", "62,29", "39 su 57", "9 su 110", "22 su 40", "senza la loro riga: 14", "48 su 110", "giornata 9",
                      "meno di 1 punto atteso"):
        assert frammento in testo, frammento


@pytest.mark.parametrize("x, atteso", [(1.0, "1 punto atteso"), (1.5, "1,5 punti attesi"), (2, "2 punti attesi"),
                                       (0.5, "0,5 punti attesi")])
def test_soglia_in_punti_attesi_scritta_all_italiana(x, atteso):
    assert vc._punti_attesi(x) == atteso


# ------------------------------------------------------------------ la giornata della parte B
def test_giornata_con_probabili_e_l_ultima_della_stagione_dalla_fonte_dell_app(tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        assert vc.giornata_con_probabili(db, ST) is None
        archivio.inserisci(db, "probabili", [
            {"stagione": ST, "giornata": 8, "fonte": "fantacalcio", "calciatore_id": 1},
            {"stagione": ST, "giornata": 9, "fonte": "fantacalcio", "calciatore_id": 1},
            {"stagione": ST, "giornata": 12, "fonte": "altra", "calciatore_id": 1},           # un'altra fonte non conta
            {"stagione": "2025-26", "giornata": 30, "fonte": "fantacalcio", "calciatore_id": 1}])   # né un'altra stagione
        assert vc.giornata_con_probabili(db, ST) == 9
    finally:
        db.close()


def test_giornata_senza_previsioni_salta_la_parte_b_e_il_rapporto_dice_perche(giocate, tmp_path, monkeypatch):
    def senza(*a, **k):
        raise ValueError("Non ci sono ancora previsioni per la giornata 40: riprova più tardi.")
    monkeypatch.setattr(vc, "parte_probabili", senza)
    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        m = vc.misura(giocate.d, db, Regole(), giocate.rose, ST, giornata=40, simulazioni=60)
    finally:
        db.close()
    assert m["probabili"] is None and m["giocate"]["casi"] == 2          # la parte A resta
    righe = []
    vc.rapporto(m, scrivi=righe.append)
    testo = "\n".join(righe)
    assert "Parte B: giornata 40 saltata: non ci sono ancora previsioni" in testo
    assert "nessuna giornata con le probabili" not in testo


# ------------------------------------------------------------------ comando
@pytest.mark.parametrize("argomenti, atteso", [([], None), (["--consiglio"], 0), (["--consiglio", "9"], 9)])
def test_opzione_consiglio_del_comando_verifica(monkeypatch, argomenti, atteso):
    visti = []
    monkeypatch.setattr(cli, "cmd_verifica", lambda a: visti.append(a.consiglio))
    cli.main(["verifica", *argomenti])
    assert visti == [atteso]
