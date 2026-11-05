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


def test_titolare_gia_improbabile_quando_era_mostrata_non_basta_per_cambiare():
    """D2: cambia sempre un titolare DIVENTATO fuori o improbabile. Se lo era già quando la consigliata è stata mostrata (il sistema
    lo teneva titolare con una riserva sicura dietro), un ritocco che lo toglie dalla migliore vale come gli altri: sotto 1 punto resta."""
    nuove = _prev({7: {"stato": "non_citato", "p_voto": 0.1}})
    prima = _migliore(_prev())
    migliore = _migliore(nuove)
    assert 7 not in _ids(migliore)
    ricordata = _ricordata(prima) | {"non_giocano": [7]}
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, SIM)
    assert _ids(f) == _ids(prima)


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
    squadre = [lega.Squadra(nome, _squadra().giocatori) for nome in ("Prima", "Seconda", "Terza")]
    voci = []
    for s in squadre:
        mondo["adesso"] += timedelta(minutes=1)
        consigli.formazione(mondo["db"], SOLO_442, lega.Rose(squadre, s.nome))
        voci.append(len(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8"))))
    assert voci == [1, 2, 2]                                  # stessa rosa ma squadre diverse: voci diverse; poi esce la più vecchia
