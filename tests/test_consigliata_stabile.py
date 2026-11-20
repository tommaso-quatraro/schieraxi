"""Consiglio stabile (#335): la consigliata già mostrata per una giornata cambia solo se la nuova vale almeno 1 punto atteso in
più (ricalcolata con i dati nuovi), oppure se un suo titolare è uscito dalla rosa, fuori o improbabile. Dopo la scadenza resta.
Rosa e numeri inventati."""
import json
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import consigli, lega
from fanta import formazione as fz
from fanta.regole import Regole

SIM = 200
GIORNATA = 9
# 25 giocatori inventati: (id, ruolo, fantavoto atteso se gioca). Tutti giocano al 95%.
# Con il solo 4-4-2 i titolari sono il portiere 1, i difensori 4-7, i centrocampisti 12-15 e gli attaccanti 20-21.
# Il difensore 8 è il primo escluso: poco sotto il 7, basta un ritocco per farlo passare davanti.
ROSA = ([(1, "P", 6.5), (2, "P", 5.0), (3, "P", 4.5)]
        + [(4, "D", 6.6), (5, "D", 6.5), (6, "D", 6.4), (7, "D", 6.3), (8, "D", 6.25), (9, "D", 5.0), (10, "D", 4.8), (11, "D", 4.6)]
        + [(12, "C", 7.0), (13, "C", 6.9), (14, "C", 6.8), (15, "C", 6.7), (16, "C", 5.2), (17, "C", 5.0), (18, "C", 4.8), (19, "C", 4.6)]
        + [(20, "A", 8.0), (21, "A", 7.8), (22, "A", 6.0), (23, "A", 5.0), (24, "A", 4.8), (25, "A", 4.6)])
SOLO_442 = Regole(moduli=["4-4-2"])


@pytest.fixture(autouse=True)
def _schede_semplici(monkeypatch):
    """Le schede dei giocatori qui non contano: bastano id, nome, ruolo, punti attesi e titolarità."""
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2),
        "titolarita": consigli.titolarita(x)})


def _prev(cambi: dict | None = None) -> pd.DataFrame:
    """Previsioni inventate della rosa; `cambi` = {id: {colonna: valore}} per i ritocchi."""
    righe = {i: {"nome": f"Giocatore {i}", "ruolo": r, "p_voto": 0.95, "mu": mu, "mu_voto": 6.0, "stato": "titolare",
                 "quota_titolare": 0.9} for i, r, mu in ROSA}
    for i, c in (cambi or {}).items():
        righe[int(i)].update(c)
    return pd.DataFrame.from_dict(righe, orient="index")


def _squadra(senza=()) -> lega.Squadra:
    return lega.Squadra("Squadra Prova", [lega.GiocatoreRosa(i, f"Giocatore {i}", r, "AAA", 1) for i, r, _ in ROSA if i not in senza])


def _migliore(prev, regole=SOLO_442, senza=()) -> dict:
    return consigli._calcola_formazione(_squadra(senza), prev, GIORNATA, True, regole, SIM)


def _ricordata(f: dict) -> dict:
    return {"titolari": [g["id"] for g in f["titolari"]], "panchina": [g["id"] for g in f["panchina"]]}


def _ids(f: dict, chi="titolari") -> set[int]:
    return {g["id"] for g in f[chi]}


def _valore(prev, titolari, regole=SOLO_442) -> float:
    """Punti attesi di questi titolari con la panchina del sistema, sulle stesse simulazioni della formazione."""
    rosa = [fz.Giocatore(int(i), x["nome"], x["ruolo"], float(x["p_voto"]), float(x["mu"]), float(x["mu_voto"]))
            for i, x in prev.iterrows()]
    tit = [g for g in rosa if g.id in set(titolari)]
    return fz.Valutatore(rosa, regole, SIM).atteso(tit, fz._panchina(rosa, tit, regole))


def test_ritocco_sotto_un_punto_resta_la_consigliata_di_prima():
    prima = _migliore(_prev())
    assert 7 in _ids(prima) and 8 not in _ids(prima)
    nuove = _prev({8: {"mu": 6.4}})                       # il difensore 8 passa davanti al 7 di poco
    migliore = _migliore(nuove)
    assert 8 in _ids(migliore) and 7 not in _ids(migliore)       # da sola la migliore cambierebbe
    f = consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), SOLO_442, SIM)
    assert _ids(f) == _ids(prima)
    assert f["punteggio_atteso"] == round(_valore(nuove, _ids(prima)), 1)     # i punti ricalcolati con i dati nuovi


def test_almeno_un_punto_in_piu_cambia():
    prima = _migliore(_prev())
    nuove = _prev({8: {"mu": 8.0}})
    migliore = _migliore(nuove)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) >= consigli.SOGLIA_CAMBIO_PUNTI
    f = consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), SOLO_442, SIM)
    assert f is migliore


def test_la_soglia_e_quella_dell_avviso_alla_scadenza():
    from fanta import notifiche
    assert consigli.SOGLIA_CAMBIO_PUNTI == notifiche.SOGLIA_AVVISO_PUNTI == 1.0


@pytest.mark.parametrize("ritocco", [{"stato": "infortunato", "p_voto": 0.0},      # fuori
                                     {"stato": "squalificato", "p_voto": 0.0},
                                     {"stato": "non_citato", "p_voto": 0.1}])       # improbabile: gioca meno del 20%
def test_titolare_diventato_fuori_o_improbabile_cambia_anche_sotto_un_punto(ritocco):
    prima = _migliore(_prev())
    nuove = _prev({7: ritocco})
    migliore = _migliore(nuove)
    assert 7 not in _ids(migliore)
    # con la riserva che entra al suo posto la consigliata di prima vale quasi lo stesso: senza la regola resterebbe
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    f = consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), SOLO_442, SIM)
    assert f is migliore


def _portieri(*p) -> dict:
    """I ritocchi che danno ai portieri 1, 2 e 3 queste probabilità di giocare (sotto il 20%: non tra i convocati previsti)."""
    return {i + 1: ({"p_voto": x} if x >= 0.2 else {"stato": "non_citato", "p_voto": x}) for i, x in enumerate(p)}


def test_titolare_gia_improbabile_quando_era_mostrata_non_basta_per_cambiare():
    """D2: cambia sempre un titolare DIVENTATO fuori o improbabile. Se lo era già quando la consigliata è stata mostrata (tre
    portieri al 10%, 5% e 3%: titolare il primo), un ritocco che lo toglie dalla migliore per un altro improbabile (il secondo sale
    al 15%) vale come gli altri: sotto 1 punto resta."""
    prima = _migliore(_prev(_portieri(0.10, 0.05, 0.03)))
    assert 1 in _ids(prima)
    nuove = _prev(_portieri(0.10, 0.15, 0.03))
    migliore = _migliore(nuove)
    assert 2 in _ids(migliore) and 1 not in _ids(migliore)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    ricordata = _ricordata(prima) | {"non_giocano": [1]}
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, SIM)
    assert _ids(f) == _ids(prima)


@pytest.mark.parametrize("p_secondo", [0.92, 0.2])
def test_titolare_gia_improbabile_cambia_se_la_migliore_mette_nel_ruolo_un_compagno_che_gioca(p_secondo):
    """#632, primo caso: tre portieri al 10%, 5% e 3% alla prima apertura (titolare il 10%, già improbabile); poi il secondo
    passa al 92% (o proprio al 20%). La migliore lo schiera e vale meno di 1 punto in più: prima restava titolare il 10%, perché
    era improbabile già quando la consigliata è stata mostrata. Quell'esenzione non vale se nel suo ruolo c'è un compagno che
    gioca almeno il 20% (qui la migliore lo mette titolare; con un altro modulo vedi il test che segue)."""
    prima = _migliore(_prev(_portieri(0.10, 0.05, 0.03)))
    assert 1 in _ids(prima)
    nuove = _prev(_portieri(0.10, p_secondo, 0.03))
    migliore = _migliore(nuove)
    assert 2 in _ids(migliore) and 1 not in _ids(migliore)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    ricordata = _ricordata(prima) | {"non_giocano": [1]}
    assert consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, SIM) is migliore


CON_IL_4_4_2 = Regole(moduli=["3-4-3", "4-4-2"])


def _attaccante_improbabile_mostrato(anticipo=()):
    """Il 3-4-3 mostrato con l'attaccante 22 al 10% titolare: solo tre difensori e due attaccanti giocano, quindi ogni modulo
    ha un improbabile e vince il 3-4-3 (il 22 quando gioca fa 14). Poi il difensore 7 sale al 95% e l'attaccante 23 al 30%: la
    migliore è un 4-4-2 che non mette nessun attaccante nuovo. `anticipo` = chi gioca un anticipo già cominciato.
    Restituisce (consigliata ricordata, previsioni nuove, migliore con le previsioni nuove)."""
    improbabile = {"stato": "non_citato"}
    allora = {i: improbabile | {"p_voto": p} for i, p in ((7, 0.15), (8, 0.12), (9, 0.05), (10, 0.04), (11, 0.03),
                                                         (22, 0.10), (23, 0.05), (24, 0.04), (25, 0.03))}
    allora[22]["mu"] = 14.0
    prima = _migliore(_prev(allora), CON_IL_4_4_2)
    assert prima["modulo"] == "3-4-3" and 22 in _ids(prima) and 23 not in _ids(prima)
    ricordata = consigli.da_ricordare(prima)
    assert 22 in ricordata["non_giocano"]
    nuove = _prev(allora | {7: {"p_voto": 0.95, "stato": "titolare"}, 23: {"p_voto": 0.30, "stato": "panchina", "quota_titolare": 0.3}}
                  | {i: {"squadra": "ANT"} for i in anticipo})
    migliore = _migliore(nuove, CON_IL_4_4_2)
    assert migliore["modulo"] == "4-4-2" and not {22, 23} & _ids(migliore)        # nessun attaccante nuovo fra i titolari
    assert _valore(nuove, _ids(migliore), CON_IL_4_4_2) - _valore(nuove, _ids(prima), CON_IL_4_4_2) < consigli.SOGLIA_CAMBIO_PUNTI
    return ricordata, nuove, migliore


def test_titolare_gia_improbabile_cambia_anche_se_la_migliore_cambia_modulo():
    """Rilievo della revisione di #736: l'esenzione guardava solo i titolari nuovi della migliore, e un 4-4-2 non ne mette nessuno
    in attacco: restava il 22 (10%) titolare e il 23 (30%) fuori. Basta un compagno di ruolo fuori dagli 11 di prima che gioca
    almeno il 20%."""
    ricordata, nuove, migliore = _attaccante_improbabile_mostrato()
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), CON_IL_4_4_2, SIM)
    assert 22 not in _ids(f)


def test_titolare_gia_improbabile_resta_se_il_compagno_che_gioca_e_fermo_per_un_anticipo():
    """Lo stesso, ma il 23 gioca un anticipo già cominciato: era fuori e non si può più mettere titolare, quindi non conta e sotto
    1 punto la consigliata di prima resta."""
    ricordata, nuove, migliore = _attaccante_improbabile_mostrato(anticipo=(23,))
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), CON_IL_4_4_2, SIM, iniziate=("ANT",))
    assert 22 in _ids(f) and 23 not in _ids(f)


@pytest.mark.parametrize("titolare, oscilla", [(0.15, (0.20, 0.02)), (0.195, (0.21, 0.19)), (0.15, (0.25, 0.14))])
def test_un_compagno_che_sale_e_scende_attorno_al_20_per_cento_non_fa_oscillare_la_consigliata(titolare, oscilla):
    """Rilievo della revisione di #736: portiere 1 titolare già improbabile, il portiere 2 che a ogni giro sale sopra il 20% e
    riscende. Al primo giro la consigliata passa al 2 (un compagno che gioca); quando il 2 riscende diventava «titolare diventato
    improbabile» e tornava l'1, di nuovo già improbabile, e così via: un cambio a ogni giro. Un titolare improbabile fa cambiare
    la consigliata solo se nel suo ruolo c'è un compagno che gioca almeno il 20%; altrimenti vale la soglia di 1 punto."""
    ricordata = consigli.da_ricordare(_migliore(_prev(_portieri(titolare, 0.02, 0.01))))
    assert 1 in ricordata["titolari"] and ricordata["non_giocano"] == [1]
    cambi = 0
    for giro in range(6):
        nuove = _prev(_portieri(titolare, oscilla[giro % 2], 0.01))
        f = consigli.stabile(_migliore(nuove), ricordata, nuove, _squadra(), SOLO_442, SIM)
        mostrata = consigli.da_ricordare(f, ricordata)
        cambi += set(mostrata["titolari"]) != set(ricordata["titolari"])
        ricordata = mostrata
    assert cambi <= 1                                   # al più il primo passaggio al portiere che gioca


@pytest.mark.parametrize("allora, primo, scambio", [
    ((0.10, 0.05, 0.03), 1, (0.21, 0.19)),     # titolare l'1 già improbabile, poi il 2 e il 3 si scambiano 21% e 19%
    ((0.10, 0.05, 0.03), 1, (0.25, 0.12)),     # ...oppure 25% e 12%
    ((0.02, 0.21, 0.19), 2, (0.19, 0.21)),     # titolare il 2 che gioca, poi si scambia con il 3
])
def test_due_compagni_che_si_scambiano_attorno_al_20_per_cento_non_fanno_oscillare_la_consigliata(allora, primo, scambio):
    """#737: due portieri che a ogni aggiornamento si scambiano sopra e sotto il 20%. Il titolare che giocava quando la consigliata
    è stata mostrata diventava improbabile, il compagno ora giocava almeno il 20% e la consigliata cambiava a ogni giro (6 cambi
    su 6). Un titolare diventato improbabile la fa cambiare solo se il compagno gioca molto più di lui."""
    ricordata = consigli.da_ricordare(_migliore(_prev(_portieri(*allora))))
    assert primo in ricordata["titolari"]
    cambi = 0
    for giro in range(6):
        secondo, terzo = scambio if giro % 2 == 0 else scambio[::-1]
        nuove = _prev(_portieri(allora[0], secondo, terzo))
        f = consigli.stabile(_migliore(nuove), ricordata, nuove, _squadra(), SOLO_442, SIM)
        mostrata = consigli.da_ricordare(f, ricordata)
        cambi += set(mostrata["titolari"]) != set(ricordata["titolari"])
        ricordata = mostrata
    assert cambi <= 1                                   # al più il primo passaggio al portiere che gioca


@pytest.mark.parametrize("p_compagno, cambia", [(0.25, False), (0.32, True), (0.40, True)])
def test_titolare_diventato_improbabile_cambia_se_un_compagno_gioca_almeno_20_punti_piu_di_lui(p_compagno, cambia):
    """#737: il portiere 1 giocava il 30% quando la consigliata è stata mostrata, ora il 12%; il 2 sale. Sotto 1 punto la
    consigliata cambia solo se il 2 gioca almeno il 20% e almeno 20 punti percentuali più dell'1 (qui dal 32%)."""
    prima = _migliore(_prev(_portieri(0.30, 0.05, 0.03)))
    ricordata = consigli.da_ricordare(prima)
    assert 1 in ricordata["titolari"] and ricordata["non_giocano"] == []
    nuove = _prev(_portieri(0.12, p_compagno, 0.03))
    migliore = _migliore(nuove)
    assert 2 in _ids(migliore) and 1 not in _ids(migliore)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, SIM)
    assert (f is migliore) == cambia
    assert (1 in _ids(f)) != cambia


@pytest.mark.parametrize("p_titolare, p_compagno", [(0.02, 0.20), (0.05, 0.22)])
def test_titolare_sceso_sotto_il_10_per_cento_cambia_con_un_compagno_al_20_per_cento(p_titolare, p_compagno):
    """Revisione di #738: il margine vale solo per chi è sceso di poco. Il portiere 1 giocava il 95% quando la consigliata è stata
    mostrata, ora non è citato (2% o 5%); il 2 gioca il 20% o il 22%. Chi quasi certamente non gioca non resta titolare con un
    compagno al 20%: con il margine di 20 punti restava."""
    prima = _migliore(_prev(_portieri(0.95, p_compagno, 0.01)))
    ricordata = consigli.da_ricordare(prima)
    assert 1 in ricordata["titolari"] and ricordata["non_giocano"] == []
    nuove = _prev(_portieri(p_titolare, p_compagno, 0.01))
    migliore = _migliore(nuove)
    assert 2 in _ids(migliore) and 1 not in _ids(migliore)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    assert consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, SIM) is migliore


def test_titolare_diventato_fuori_cambia_anche_senza_un_compagno_che_gioca():
    """Il portiere 1 si infortuna e gli altri due giocano il 10% e il 5%: nessun compagno arriva al 20%, ma un titolare fuori non
    resta nella consigliata (al suo posto il 2, più probabile che giochi). Con un improbabile, invece, vale la soglia di punti."""
    prima = _migliore(_prev(_portieri(0.95, 0.10, 0.05)))
    assert 1 in _ids(prima)
    nuove = _prev(_portieri(0.95, 0.10, 0.05) | {1: {"stato": "infortunato", "p_voto": 0.0}})
    migliore = _migliore(nuove)
    assert 2 in _ids(migliore)
    assert _valore(nuove, _ids(migliore)) - _valore(nuove, _ids(prima)) < consigli.SOGLIA_CAMBIO_PUNTI
    assert consigli.stabile(migliore, consigli.da_ricordare(prima), nuove, _squadra(), SOLO_442, SIM) is migliore


def test_titolare_uscito_dalla_rosa_cambia():
    prima = _migliore(_prev())
    migliore = _migliore(_prev(), senza=(7,))
    f = consigli.stabile(migliore, _ricordata(prima), _prev(), _squadra(senza=(7,)), SOLO_442, SIM)
    assert f is migliore and 7 not in _ids(f)


def test_senza_consigliata_di_prima_vale_la_migliore():
    migliore = _migliore(_prev())
    assert consigli.stabile(migliore, None, _prev(), _squadra(), SOLO_442, SIM) is migliore


def test_consigliata_di_prima_rovinata_vale_la_migliore():
    migliore = _migliore(_prev())
    for rovinata in ({"titolari": [1, 2, 3]}, {"titolari": "x"}, {}, {"titolari": [1] * 11}):
        assert consigli.stabile(migliore, rovinata, _prev(), _squadra(), SOLO_442, SIM) is migliore


def test_dopo_la_scadenza_resta_anche_per_molti_punti():
    prima = _migliore(_prev())
    nuove = _prev({8: {"mu": 9.0}, 7: {"stato": "infortunato", "p_voto": 0.0}})
    migliore = _migliore(nuove)
    f = consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), SOLO_442, SIM, chiusa=True)
    assert [g["id"] for g in f["titolari"]] and _ids(f) == _ids(prima)
    assert [g["id"] for g in f["panchina"]] == [g["id"] for g in prima["panchina"]]      # anche la panchina resta com'era


def test_la_consigliata_tenuta_e_la_stessa_in_ogni_parte_della_risposta():
    """Il web e l'iPhone mostrano i titolari dalla voce del modulo nello stile scelto (`livelli`, `moduli`): devono essere quelli
    tenuti, con lo stesso modulo e gli stessi punti, e `fuori` non deve contenere nessuno dei titolari o della panchina."""
    regole = Regole(moduli=["4-4-2", "3-4-3"])
    prima = _migliore(_prev(), regole)
    nuove = _prev({22: {"mu": 6.5}, 8: {"mu": 6.4}})         # più valore al terzo attaccante e al quinto difensore: ritocchi
    migliore = _migliore(nuove, regole)
    assert _ids(migliore) != _ids(prima)
    f = consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), regole, SIM)
    assert _ids(f) == _ids(prima) and f["modulo"] == prima["modulo"]
    for blocco in (f, next(x for x in f["livelli"] if x["rischio"] == f["stile_consigliato"])):
        assert blocco["modulo"] == f["modulo"] and blocco["punteggio_atteso"] == f["punteggio_atteso"]
        voce = next(m for m in blocco["moduli"] if m["modulo"] == f["modulo"])
        assert set(voce["titolari"]) == _ids(f) and voce["panchina"] == [g["id"] for g in f["panchina"]]
        assert voce["punteggio_atteso"] == f["punteggio_atteso"] and voce["intervallo"] == f["intervallo"]
    scelti = _ids(f) | _ids(f, "panchina")
    assert not scelti & {g["id"] for g in f["fuori"]} and len(scelti) + len(f["fuori"]) == len(ROSA)
    assert f["modulo"] not in [a["modulo"] for a in f["alternative"]]
    assert sorted(a["modulo"] for a in f["alternative"]) == sorted(m["modulo"] for m in f["moduli"] if m["modulo"] != f["modulo"])
    assert migliore["titolari"] != f["titolari"]                  # la risposta in cache della migliore non cambia


def test_rosa_con_un_giocatore_doppio_nessun_doppione_nella_consigliata_tenuta():
    """Rosa salvata con il 22 due volte (un file vecchio o un backup ripristinato: l'importazione di oggi i doppioni li toglie).
    Dopo un ritocco che vale meno di 1 punto la consigliata tenuta mostrava il 22 due volte in panchina e il 23 finiva fuori (#659).
    Ora la rosa conta il doppione una volta sola: tutto come con la rosa senza doppioni."""
    doppia = lega.Squadra("Squadra Prova", _squadra().giocatori + [lega.GiocatoreRosa(22, "Giocatore 22", "A", "AAA", 1)])
    nuove = _prev({8: {"mu": 6.4}})
    prima = consigli._calcola_formazione(doppia, _prev(), GIORNATA, True, SOLO_442, SIM)
    migliore = consigli._calcola_formazione(doppia, nuove, GIORNATA, True, SOLO_442, SIM)
    f = consigli.stabile(migliore, _ricordata(prima), nuove, doppia, SOLO_442, SIM)
    assert _ids(f) == _ids(prima) and 7 in _ids(f)                # tenuta: il ritocco vale meno di 1 punto
    panchina = [g["id"] for g in f["panchina"]]
    assert len(panchina) == len(set(panchina)) == 7 and 23 in panchina
    assert 22 not in {g["id"] for g in f["fuori"]}
    pulita = consigli.stabile(_migliore(nuove), _ricordata(_migliore(_prev())), nuove, _squadra(), SOLO_442, SIM)
    assert panchina == [g["id"] for g in pulita["panchina"]] and f["punteggio_atteso"] == pulita["punteggio_atteso"]


# ---------------------------------------------------------------- consigli.formazione: ricorda la consigliata e la rilegge
ST = "2026-27"
PRIMA_PARTITA = datetime(2026, 11, 8, 15, 0)            # scadenza della giornata 9 (regole senza minuti di anticipo)


@pytest.fixture
def mondo(monkeypatch, tmp_path):
    """Una giornata 9 con le previsioni che il test cambia (`stato["prev"]`) e una versione dei dati per ogni cambio, come un
    aggiornamento vero. Il file delle consigliate sta nella cartella temporanea."""
    monkeypatch.setattr(consigli, "FILE_CONSIGLIATE", tmp_path / "consigliate.json")
    stato = {"prev": _prev(), "versione": "v1", "adesso": PRIMA_PARTITA - timedelta(hours=5)}
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: GIORNATA)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (stato["prev"], GIORNATA, True))
    monkeypatch.setattr(consigli, "_versione", lambda db: stato["versione"])
    monkeypatch.setattr(consigli, "_adesso", lambda: stato["adesso"])
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, GIORNATA, "2026-11-08 15:00", 0), (ST, GIORNATA, "2026-11-09 20:45", 0)])
    stato["db"] = db
    consigli._cache.clear()
    yield stato
    consigli._cache.clear()


def _rose() -> lega.Rose:
    return lega.Rose([_squadra()], "Squadra Prova")


def _formazione(mondo, prev=None) -> dict:
    """La consigliata come la chiedono tutti (Formazione, Oggi, widget, Da fare...): simulazioni di sempre."""
    if prev is not None:                                   # dati nuovi: come un aggiornamento vero, cambia anche la versione
        mondo["prev"], mondo["versione"] = prev, mondo["versione"] + "+"
    return consigli.formazione(mondo["db"], SOLO_442, _rose())


def test_formazione_tiene_la_consigliata_dopo_un_ritocco_anche_dopo_un_riavvio(mondo):
    prima = _formazione(mondo)
    assert 7 in _ids(prima)
    dopo = _formazione(mondo, _prev({8: {"mu": 6.4}}))
    assert _ids(dopo) == _ids(prima)
    consigli._cache.clear()                                   # riavvio del servizio: la memoria si svuota, il file resta
    assert _ids(_formazione(mondo)) == _ids(prima)


def test_da_fare_legge_la_stessa_consigliata(mondo):
    """Da fare (#333) chiama `consigli.formazione` senza sapere niente della consigliata di prima: deve vedere quella tenuta."""
    from fanta import da_fare
    prima = _formazione(mondo)
    _formazione(mondo, _prev({8: {"mu": 6.4}}))
    titolari, _ = da_fare._consigliata(mondo["db"], SOLO_442, _rose())
    assert set(titolari) == _ids(prima)


def test_cambia_per_almeno_un_punto_e_poi_tiene_la_nuova(mondo):
    _formazione(mondo)
    nuova = _formazione(mondo, _prev({8: {"mu": 8.0}}))
    assert 8 in _ids(nuova) and 7 not in _ids(nuova)
    dopo = _formazione(mondo, _prev({8: {"mu": 6.2}}))       # ora il 7 vale di nuovo un po' più dell'8: un ritocco, si tiene la nuova
    assert _ids(dopo) == _ids(nuova)


def test_dopo_la_scadenza_la_consigliata_non_cambia_e_il_file_resta_com_era(mondo):
    prima = _formazione(mondo)
    scritto = consigli.FILE_CONSIGLIATE.read_bytes()
    mondo["adesso"] = PRIMA_PARTITA + timedelta(minutes=1)
    dopo = _formazione(mondo, _prev({8: {"mu": 9.0}, 7: {"stato": "infortunato", "p_voto": 0.0}}))
    assert _ids(dopo) == _ids(prima) and [g["id"] for g in dopo["panchina"]] == [g["id"] for g in prima["panchina"]]
    assert consigli.FILE_CONSIGLIATE.read_bytes() == scritto


def test_dopo_la_scadenza_senza_consigliata_di_prima_vale_la_prima_vista(mondo):
    mondo["adesso"] = PRIMA_PARTITA + timedelta(minutes=1)
    prima = _formazione(mondo)
    assert _ids(_formazione(mondo, _prev({8: {"mu": 9.0}}))) == _ids(prima)


def test_la_panchina_ricordata_e_l_ultima_mostrata_prima_della_scadenza(mondo):
    prima = _formazione(mondo)
    dopo = _formazione(mondo, _prev({8: {"mu": 6.4}, 22: {"mu": 3.0}}))      # il terzo attaccante scende: la panchina si riordina
    assert _ids(dopo) == _ids(prima) and [g["id"] for g in dopo["panchina"]] != [g["id"] for g in prima["panchina"]]
    ricordata = next(iter(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")).values()))
    assert ricordata["panchina"] == [g["id"] for g in dopo["panchina"]]
    assert set(ricordata["titolari"]) == _ids(dopo)


def test_il_file_non_ha_nomi_di_squadre_ne_di_giocatori(mondo):
    _formazione(mondo)
    testo = consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")
    assert "Squadra Prova" not in testo and "Giocatore" not in testo
    voce = next(iter(json.loads(testo).values()))
    assert set(voce) <= {"stagione", "giornata", "modulo", "titolari", "panchina", "non_giocano", "quando"}


def test_si_ricordano_i_titolari_che_gia_non_giocavano(mondo):
    """Con soli 4 difensori il 7 è titolare anche se improbabile: la consigliata ricordata lo segna, e quando poi la si tiene
    (stessi titolari) l'elenco resta quello di quando è stata mostrata."""
    quattro = lega.Rose([_squadra(senza=(8, 9, 10, 11))], "Squadra Prova")
    mondo["prev"] = _prev({7: {"stato": "non_citato", "p_voto": 0.1}})
    consigli.formazione(mondo["db"], SOLO_442, quattro)
    prima = next(iter(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")).values()))
    assert prima["non_giocano"] == [7]
    mondo["prev"], mondo["versione"] = _prev({7: {"stato": "titolare", "p_voto": 0.9}, 22: {"mu": 3.0}}), "v2"
    consigli.formazione(mondo["db"], SOLO_442, quattro)          # il 7 torna sicuro e la panchina cambia: si riscrive
    dopo = next(iter(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")).values()))
    assert set(dopo["titolari"]) == set(prima["titolari"]) and dopo["panchina"] != prima["panchina"]
    assert dopo["non_giocano"] == [7]


def test_file_rovinato_vale_la_migliore_e_si_riscrive(mondo):
    consigli.FILE_CONSIGLIATE.write_text("{non è json", encoding="utf-8")
    f = _formazione(mondo)
    assert len(f["titolari"]) == 11
    assert len(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))) == 1


def test_una_voce_per_squadra_e_un_tetto_al_file(mondo, monkeypatch):
    monkeypatch.setattr(consigli, "MAX_CONSIGLIATE", 2)
    # rose diverse (un attaccante di riserva in meno): l'impronta è dei giocatori, non del nome (#780)
    squadre = [lega.Squadra(nome, _squadra(senza=(via,)).giocatori) for nome, via in (("Prima", 25), ("Seconda", 24), ("Terza", 23))]
    voci = []
    for s in squadre:
        mondo["adesso"] += timedelta(minutes=1)
        consigli.formazione(mondo["db"], SOLO_442, lega.Rose(squadre, s.nome))
        voci.append(len(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))))
    assert voci == [1, 2, 2]                                  # squadre diverse: voci diverse; poi esce la più vecchia


def test_formazione_segna_la_consigliata_della_propria_squadra(mondo):
    """Con gli account la consigliata della squadra di chi chiede si segna come sua (`proprie`), quella di un'avversaria no;
    rivedendo la propria già ricordata (prima senza il segno) il segno si aggiunge."""
    from fanta import calcolo
    squadre = [lega.Squadra("Mia", _squadra(senza=(25,)).giocatori), lega.Squadra("Avversaria", _squadra(senza=(24,)).giocatori)]
    gettone = calcolo.utente_richiesta.set(7)
    try:
        consigli.formazione(mondo["db"], SOLO_442, lega.Rose(squadre, "Avversaria"), "Mia")      # un'altra lega: Mia non è sua
        mondo["adesso"] += timedelta(minutes=1)
        consigli.formazione(mondo["db"], SOLO_442, lega.Rose(squadre, "Mia"), "Avversaria")
        voci = json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))
        assert len(voci) == 2 and not [v for v in voci.values() if "proprie" in v]
        mondo["adesso"] += timedelta(minutes=1)
        consigli.formazione(mondo["db"], SOLO_442, lega.Rose(squadre, "Mia"))                   # la sua, già vista: si segna
    finally:
        calcolo.utente_richiesta.reset(gettone)
    voci = json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))
    assert sorted(v.get("proprie", []) for v in voci.values()) == [[], [7]]


def test_giocatori_non_riconosciuti_diversi_non_si_mescolano_fra_utenti(mondo):
    """La memoria dei calcoli è di tutti: due utenti con la stessa squadra e gli stessi giocatori riconosciuti, ma un giocatore
    non riconosciuto scritto in modo diverso, vedono ognuno il proprio nome tra quelli senza dati (#480)."""
    def rose_con(nome_scritto: str) -> lega.Rose:
        s = _squadra()
        s.giocatori.append(lega.GiocatoreRosa(None, nome_scritto, "A", "", 1))
        return lega.Rose([s], s.nome)
    prima = consigli.formazione(mondo["db"], SOLO_442, rose_con("Nome Inventato Uno"))
    seconda = consigli.formazione(mondo["db"], SOLO_442, rose_con("Nome Inventato Due"))
    assert prima["senza_dati"] == ["Nome Inventato Uno"] and seconda["senza_dati"] == ["Nome Inventato Due"]
