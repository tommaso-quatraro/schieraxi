"""Giornate › dettaglio (#900): perché i punti della giornata non sono la somma dei fantavoti dei suoi 11. Il Diario salva, per ogni
formazione, chi è entrato dalla panchina al posto di chi, chi è rimasto senza sostituto, il modificatore difesa e chi aveva la partita
rinviata (`dettaglio`), e il server ne scrive le frasi (`spiegazione_punti`). Dati finti, come in test_diario.py."""
import json
from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import archivio, consigli, diario, lega
from fanta.regole import ModificatoreDifesa, Regole

ST = "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25
TRE_QUATTRO_TRE = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
QUATTRO_QUATTRO_DUE = [1, 4, 5, 6, 7, 12, 13, 14, 15, 21, 25]


@pytest.fixture
def finto(monkeypatch, tmp_path):
    """Due giornate finite; tutti prendono 6, tranne l'ultimo attaccante (id 25) che prende 9."""
    partite = pd.DataFrame([{"id": g, "stagione": ST, "giornata": g, "data": f"2026-09-0{g} 18:00", "giocata": 1} for g in (1, 2)])
    voti = pd.DataFrame([{"stagione": ST, "giornata": g, "calciatore_id": i, "voto_red": 9.0 if i == 25 else 6.0,
                          "data": f"2026-09-0{g} 18:00"} for g in (1, 2) for i in range(1, 26)])
    dati = SimpleNamespace(partite=partite, voti=voti)

    def previsioni(d, stagione, giornata, regole, par):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0,
                              "partita": giornata} for i in range(1, 26)])
    monkeypatch.setattr(diario, "previsioni", previsioni)
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db: dati)
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in (1, 2):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2026-09-01 18:00', 'a', 'b', 1)", (g, ST, g))
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": g, "calciatore_id": i, "squadra": "ab"[i % 2],
                                     "voto_red": 9.0 if i == 25 else 6.0} for g in (1, 2) for i in range(1, 26)])
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26)])], "Mia")
    return SimpleNamespace(dati=dati, db=db, rose=rose, file=tmp_path / "diario.json")


def _senza_voto(finto, *ids, giornata=1) -> None:
    v = finto.dati.voti
    finto.dati.voti = v[~((v["giornata"] == giornata) & v["calciatore_id"].isin(ids))].copy()


def _voto(finto, i, voto) -> None:
    finto.dati.voti.loc[finto.dati.voti["calciatore_id"] == i, "voto_red"] = voto


def _voce(finto, titolari, panchina=None, regole=None, **altro) -> dict:
    scelta = {"titolari": titolari} | ({"panchina": panchina} if panchina is not None else {})
    return diario.calcola_giornata(finto.dati, ST, 1, regole or Regole(), None, list(range(1, 26)), scelta, simulazioni=50, **altro)


def g(i) -> dict:
    return {"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1]}


def _somma(v: dict, riga: dict) -> float:
    """I punti di una formazione rifatti dal suo dettaglio: i fantavoti dei titolari che hanno contato (`giocatori[].fv`, oppure il voto
    d'ufficio), quelli di chi è entrato, chi è rimasto senza sostituto e il modificatore. Deve dare `reale`."""
    d = riga["dettaglio"]
    fuori = {e["esce"]["id"] for e in d["entrati"]} | {x["id"] for x in d["senza_sostituto"]}
    rinvio = d.get("rinvio") or {}
    ufficio = {x["id"] for x in rinvio.get("giocatori", [])} if rinvio.get("modo") == "voto_ufficio" else set()
    fv = {x["id"]: x["fv"] for x in v["giocatori"]}
    tot = sum(rinvio["valore"] if t["id"] in ufficio else fv[t["id"]] for t in riga["titolari"] if t["id"] not in fuori)
    tot += sum(e["fv"] for e in d["entrati"])
    tot += len(d["senza_sostituto"]) * (d["voto_senza_sostituto"] or 0.0)
    return round(tot + (d["modificatore"] or 0.0), 1)


# ---------------------------------------------------------------- il dettaglio salvato con la voce
def test_chi_e_entrato_dalla_panchina_e_al_posto_di_chi(finto):
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    v = _voce(finto, TRE_QUATTRO_TRE, panchina=[22, 24])
    s = v["schierata"]
    assert s["reale"] == 9 * 6 + 9 + 10
    assert s["dettaglio"] == {"entrati": [{"esce": g(20), "entra": g(22), "fv": 10.0}], "senza_sostituto": [],
                              "voto_senza_sostituto": None, "modificatore": None}
    assert _somma(v, s) == s["reale"]


def test_tutti_in_campo_e_niente_modificatore_niente_da_spiegare(finto):
    v = _voce(finto, TRE_QUATTRO_TRE)
    for k in ("schierata", "consigliata", "ricostruita"):
        assert v[k]["dettaglio"] == {"entrati": [], "senza_sostituto": [], "voto_senza_sostituto": None, "modificatore": None}, k
        assert _somma(v, v[k]) == v[k]["reale"]


def test_il_modificatore_difesa_della_lega(finto):
    regole = replace(Regole(), modificatore_difesa=ModificatoreDifesa(attivo=True))       # media 6: +1 (fasce predefinite)
    v = _voce(finto, QUATTRO_QUATTRO_DUE, regole=regole)
    s = v["schierata"]
    assert s["reale"] == 10 * 6 + 9 + 1 and s["dettaglio"]["modificatore"] == 1.0
    assert _somma(v, s) == s["reale"]


def test_senza_sostituto_conta_il_voto_della_lega(finto):
    """L'attaccante 20 non prende voto e la sua panchina ha solo un portiere: non entra nessuno e la lega gli dà 4."""
    _senza_voto(finto, 20)
    v = _voce(finto, TRE_QUATTRO_TRE, panchina=[2], regole=replace(Regole(), voto_senza_sostituto=4.0))
    s = v["schierata"]
    assert s["reale"] == 9 * 6 + 9 + 4
    assert s["dettaglio"]["entrati"] == [] and s["dettaglio"]["senza_sostituto"] == [g(20)]
    assert s["dettaglio"]["voto_senza_sostituto"] == 4.0
    assert _somma(v, s) == s["reale"]


@pytest.mark.parametrize("modo", ["voto_ufficio", "senza_voto"])
def test_la_partita_rinviata_con_la_regola_della_lega(monkeypatch, finto, modo):
    """Gli attaccanti 21-25 giocano la partita 2, rinviata e recuperata settimane dopo (come in test_rinvii.py)."""
    finto.dati.partite = pd.DataFrame([{"id": 1, "stagione": ST, "giornata": 1, "data": "2026-09-01 18:00", "giocata": 1},
                                       {"id": 3, "stagione": ST, "giornata": 1, "data": "2026-09-01 20:45", "giocata": 1},
                                       {"id": 4, "stagione": ST, "giornata": 1, "data": "2026-09-02 18:00", "giocata": 1},
                                       {"id": 2, "stagione": ST, "giornata": 1, "data": "2026-10-20 20:45", "giocata": 1}])
    prima = diario.previsioni
    monkeypatch.setattr(diario, "previsioni", lambda *a: prima(*a).assign(partita=lambda p: [2 if i > 20 else 1 for i in p["id"]]))
    v = _voce(finto, TRE_QUATTRO_TRE, panchina=[2, 22], regole=replace(Regole(), partite_rinviate=modo))
    s = v["schierata"]
    if modo == "voto_ufficio":
        assert s["reale"] == 11 * 6
        assert s["dettaglio"]["rinvio"] == {"modo": "voto_ufficio", "valore": 6.0, "giocatori": [g(21), g(25)]}
        assert s["dettaglio"]["senza_sostituto"] == []
    else:
        assert s["reale"] == 9 * 6                     # 21 e 25 senza voto, e il 22 della panchina ha la stessa partita
        assert s["dettaglio"]["rinvio"] == {"modo": "senza_voto", "valore": None, "giocatori": [g(21), g(25)]}
        assert s["dettaglio"]["senza_sostituto"] == [g(21), g(25)]
    assert _somma(v, s) == s["reale"]


def _formazione_finta(ids):
    pers = lambda i: {"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "punti_attesi": 6.1}      # noqa: E731
    return {"giornata": 1, "modulo": "3-4-3", "punteggio_atteso": 71.46, "titolari": [pers(i) for i in ids],
            "panchina": [pers(i) for i in (22, 24, 23)], "livelli": [{"rischio": 0, "nome": "Equilibrata"}]}


def test_gli_stessi_titolari_della_mostrata_hanno_il_suo_dettaglio(finto):
    """Con gli stessi 11 della consigliata mostrata, la tua formazione prende i suoi punti, fatti con la panchina mostrata allora
    (entra il 22, che prende 10; con quella del sistema entrerebbe il 24): anche il dettaglio è il suo."""
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    diario.salva_istantanea(_formazione_finta(TRE_QUATTRO_TRE), ST, finto.file)
    ist = diario.carica(finto.file)["istantanee"][f"{ST}/1"]
    v = _voce(finto, TRE_QUATTRO_TRE, istantanea=ist)
    c, s = v["consigliata"], v["schierata"]
    assert c["origine"] == "mostrata" and s["reale"] == c["reale"] == 73.0
    assert s["dettaglio"] == c["dettaglio"] and c["dettaglio"]["entrati"] == [{"esce": g(20), "entra": g(22), "fv": 10.0}]


def test_con_i_voti_cambiati_si_rifa_anche_il_dettaglio(finto):
    voce = _voce(finto, TRE_QUATTRO_TRE, panchina=[22, 24])
    assert voce["schierata"]["dettaglio"]["entrati"] == []
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    nuova = diario.rifai_i_punti(finto.dati, ST, 1, Regole(), None, voce, list(range(1, 26)),
                                 {"titolari": TRE_QUATTRO_TRE, "panchina": [22, 24]}, None, None, None, simulazioni=50)
    s = nuova["schierata"]
    assert s["reale"] == 73.0 and s["dettaglio"]["entrati"] == [{"esce": g(20), "entra": g(22), "fv": 10.0}]
    assert _somma(nuova, s) == s["reale"]
    for k in ("consigliata", "ricostruita"):
        assert _somma(nuova, nuova[k]) == nuova[k]["reale"], k


# ---------------------------------------------------------------- le frasi della pagina Giornate (il server le scrive, i client le mostrano)
def _in_pagina(finto, voce) -> dict:
    """La voce come la riceve la pagina Giornate (`GET /api/diario`)."""
    diario._scrivi(finto.file, voci={f"{voce['stagione']}/{voce['giornata']}": voce})
    return diario.elenco(finto.file)["giornate"][0]


def test_le_frasi_dicono_chi_e_entrato_e_il_modificatore(finto):
    _senza_voto(finto, 21)
    _voto(finto, 22, 10.0)
    regole = replace(Regole(), modificatore_difesa=ModificatoreDifesa(attivo=True))
    v = _in_pagina(finto, _voce(finto, QUATTRO_QUATTRO_DUE, panchina=[22], regole=regole))
    assert v["spiegazione_punti"] == {
        "formazione": "schierata",
        "righe": ["G22 (10,0) è entrato dalla panchina al posto di G21.", "Modificatore difesa: +1,0."],
        "righe_frasi": [{"chiave": "diario.punti_entrato", "param": {"entra": "G22", "fv": "10.0", "esce": "G21"}},
                        {"chiave": "diario.punti_modificatore", "param": {"d": "+1.0"}}]}


def test_tutti_in_campo_e_modificatore_zero_nessuna_frase(finto):
    regole = replace(Regole(), modificatore_difesa=ModificatoreDifesa(attivo=True, soglie=[[7.0, 2.0]]))      # media 6: niente
    v = _in_pagina(finto, _voce(finto, QUATTRO_QUATTRO_DUE, regole=regole))
    assert v["schierata"]["dettaglio"]["modificatore"] == 0.0 and v["spiegazione_punti"] is None


@pytest.mark.parametrize("voto, mancanti, frase", [
    (None, (20,), "Al posto di G20 non è entrato nessuno dalla panchina."),
    (4.0, (20,), "Al posto di G20 non è entrato nessuno dalla panchina: per la tua lega vale 4,0."),
    (4.0, (20, 21), "Al posto di G20 e G21 non è entrato nessuno dalla panchina: per la tua lega valgono 4,0 ciascuno."),
])
def test_la_frase_di_chi_resta_senza_sostituto(finto, voto, mancanti, frase):
    _senza_voto(finto, *mancanti)
    v = _in_pagina(finto, _voce(finto, TRE_QUATTRO_TRE, panchina=[2], regole=replace(Regole(), voto_senza_sostituto=voto)))
    assert v["spiegazione_punti"]["righe"] == [frase]


@pytest.mark.parametrize("modo, righe", [
    ("voto_ufficio", ["Partita rinviata: G21 e G25 prendono il voto d'ufficio (6,0)."]),
    ("senza_voto", ["Partita rinviata: G21 e G25 non prendono voto in questa giornata.",
                    "Al posto di G21 e G25 non è entrato nessuno dalla panchina."]),
])
def test_la_frase_della_partita_rinviata(monkeypatch, finto, modo, righe):
    finto.dati.partite = pd.DataFrame([{"id": 1, "stagione": ST, "giornata": 1, "data": "2026-09-01 18:00", "giocata": 1},
                                       {"id": 3, "stagione": ST, "giornata": 1, "data": "2026-09-01 20:45", "giocata": 1},
                                       {"id": 4, "stagione": ST, "giornata": 1, "data": "2026-09-02 18:00", "giocata": 1},
                                       {"id": 2, "stagione": ST, "giornata": 1, "data": "2026-10-20 20:45", "giocata": 1}])
    prima = diario.previsioni
    monkeypatch.setattr(diario, "previsioni", lambda *a: prima(*a).assign(partita=lambda p: [2 if i > 20 else 1 for i in p["id"]]))
    v = _in_pagina(finto, _voce(finto, TRE_QUATTRO_TRE, panchina=[2, 22], regole=replace(Regole(), partite_rinviate=modo)))
    assert v["spiegazione_punti"]["righe"] == righe


def test_senza_la_tua_formazione_le_frasi_sono_della_consigliata(finto):
    _senza_voto(finto, 25)
    voce = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    assert 25 in [t["id"] for t in voce["consigliata"]["titolari"]]           # il 25 vale di più: è titolare, e non prende voto
    v = _in_pagina(finto, voce)
    assert v["spiegazione_punti"]["formazione"] == "consigliata"
    assert v["spiegazione_punti"]["righe_frasi"][0]["param"]["esce"] == "G25"


def _di_prima(voce: dict) -> dict:
    """La voce come quelle scritte prima di #900: le formazioni senza `dettaglio`."""
    for k in ("consigliata", "ricostruita", "schierata", "automatica"):
        if isinstance(voce.get(k), dict):
            voce[k].pop("dettaglio", None)
    return voce


def test_una_voce_di_prima_che_torna_con_i_voti_degli_11_non_ha_frasi(finto):
    v = _in_pagina(finto, _di_prima(_voce(finto, TRE_QUATTRO_TRE)))
    assert v["spiegazione_punti"] is None


@pytest.mark.parametrize("dettaglio", ["assente", None])
def test_una_voce_di_prima_che_non_torna_dice_che_il_dettaglio_manca(finto, dettaglio):
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    voce = _di_prima(_voce(finto, TRE_QUATTRO_TRE, panchina=[22]))
    if dettaglio is None:
        voce["schierata"]["dettaglio"] = None                 # la voce non si è potuta completare (vedi aggiorna)
    v = _in_pagina(finto, voce)
    assert v["spiegazione_punti"] == {
        "formazione": "schierata",
        "righe": ["Per questa giornata manca il dettaglio dei punti (riserve entrate, modificatore difesa): è stata calcolata "
                  "prima che SchieraXI lo salvasse."],
        "righe_frasi": [{"chiave": "diario.punti_senza_dettaglio", "param": {}}]}


# ---------------------------------------------------------------- le giornate già calcolate: una volta sola, senza toccare i punti
def _aggiorna(finto) -> int:
    return diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50)


def _come_prima_di_900(finto, cambia=lambda voci: None) -> dict:
    """Il file come sul server prima di #900: le formazioni delle voci senza `dettaglio`. Torna le voci scritte."""
    d = diario.carica(finto.file)
    for v in d["giornate"].values():
        _di_prima(v)
    cambia(d["giornate"])
    finto.file.write_text(json.dumps(d), encoding="utf-8")
    return json.loads(json.dumps(d["giornate"]))


def _senza_dettagli(voci: dict) -> dict:
    return {k: _di_prima(json.loads(json.dumps(v))) for k, v in voci.items()}


def test_le_giornate_gia_calcolate_prendono_il_dettaglio_senza_cambiare_niente_altro(finto, monkeypatch):
    regole = replace(Regole(), modificatore_difesa=ModificatoreDifesa(attivo=True, min_difensori=3))
    assert diario.aggiorna(finto.db, regole, finto.rose, finto.file, simulazioni=50) == 2
    nuove = diario.carica(finto.file)["giornate"]
    prima = _come_prima_di_900(finto)
    monkeypatch.setattr(diario.fz, "migliore", lambda *a, **k: pytest.fail("non deve rifare le simulazioni"))
    assert diario.aggiorna(finto.db, regole, finto.rose, finto.file, simulazioni=50) == 2
    dopo = diario.carica(finto.file)["giornate"]
    assert _senza_dettagli(dopo) == prima                        # punti, formazioni, indicatori, impronte: tutto com'era
    assert dopo == nuove                                         # e il dettaglio è quello che avrebbe una voce nuova
    assert dopo[f"{ST}/1"]["consigliata"]["dettaglio"]["modificatore"] == 1.0
    assert diario.aggiorna(finto.db, regole, finto.rose, finto.file, simulazioni=50) == 0          # una volta sola


def test_con_la_panchina_di_allora_il_dettaglio_dice_chi_e_entrato(finto):
    """La consigliata mostrata prima della scadenza ha la sua panchina salvata (istantanea): chi è entrato si sa."""
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    diario.salva_istantanea(_formazione_finta(TRE_QUATTRO_TRE), ST, finto.file)
    assert _aggiorna(finto) == 2
    nuove = diario.carica(finto.file)["giornate"]
    _come_prima_di_900(finto)
    assert _aggiorna(finto) == 2
    c = diario.carica(finto.file)["giornate"][f"{ST}/1"]["consigliata"]
    assert c["origine"] == "mostrata" and c["dettaglio"] == nuove[f"{ST}/1"]["consigliata"]["dettaglio"]
    assert c["dettaglio"]["entrati"] == [{"esce": g(20), "entra": g(22), "fv": 10.0}]


def test_chi_entra_deve_essere_nella_rosa_di_allora(finto):
    """Chi entra dalla panchina deve essere fra i giocatori della voce (`giocatori`, la rosa di allora): se no il dettaglio non vale."""
    _senza_voto(finto, 20)
    _voto(finto, 22, 10.0)
    diario.salva_istantanea(_formazione_finta(TRE_QUATTRO_TRE), ST, finto.file)
    assert _aggiorna(finto) == 2

    def senza_il_22(voci):
        voci[f"{ST}/1"]["giocatori"] = [x for x in voci[f"{ST}/1"]["giocatori"] if x["id"] != 22]
    _come_prima_di_900(finto, senza_il_22)
    assert _aggiorna(finto) == 2
    assert diario.carica(finto.file)["giornate"][f"{ST}/1"]["consigliata"]["dettaglio"] is None


def test_con_la_panchina_del_sistema_una_riserva_entrata_non_si_indovina(finto, monkeypatch):
    """Revisione di #905: senza la panchina di allora (né istantanea né scelta con la sua panchina) la panchina si rifà con la rosa
    di oggi. Il 20 non prese voto ed entrò il 22 (6,0); poi il 22 è stato ceduto ed è arrivato il 26, stesso ruolo e stesso voto: i
    punti rifatti tornano uguali, ma «G26 è entrato al posto di G20» sarebbe falso. Il dettaglio resta vuoto."""
    prima = diario.previsioni
    monkeypatch.setattr(diario, "previsioni", lambda *a: pd.concat(
        [prima(*a), pd.DataFrame([{"id": 26, "nome": "G26", "ruolo": "A", "p_voto": 0.9, "mu": 6.8, "mu_voto": 6.0, "partita": a[2]}])],
        ignore_index=True))
    finto.dati.voti = pd.concat([finto.dati.voti, pd.DataFrame([{"stagione": ST, "giornata": gg, "calciatore_id": 26, "voto_red": 6.0,
                                                                 "data": f"2026-09-0{gg} 18:00"} for gg in (1, 2)])], ignore_index=True)
    _senza_voto(finto, 20, 23, 24)
    monkeypatch.setattr(diario.scelte, "leggi", lambda st, gg, *a, **k: {"titolari": TRE_QUATTRO_TRE} if gg == 1 and not k else None)
    assert _aggiorna(finto) == 2
    s = diario.carica(finto.file)["giornate"][f"{ST}/1"]["schierata"]
    assert s["reale"] == 69.0 and s["dettaglio"]["entrati"] == [{"esce": g(20), "entra": g(22), "fv": 6.0}]
    _come_prima_di_900(finto)
    tutti = [i for i in range(1, 27) if i != 22]                                   # il 22 ceduto, il 26 comprato
    finto.rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", (RUOLI + ["A"])[i - 1], "INT") for i in tutti])], "Mia")
    assert _aggiorna(finto) == 2
    voci = diario.carica(finto.file)["giornate"]
    s = voci[f"{ST}/1"]["schierata"]
    assert s["reale"] == 69.0 and s["dettaglio"] is None
    assert "G26" not in json.dumps(voci)
    assert diario.spiegazione_punti(voci[f"{ST}/1"])["righe_frasi"] == [{"chiave": "diario.punti_senza_dettaglio", "param": {}}]
    assert _aggiorna(finto) == 0


def test_dove_i_punti_rifatti_non_sono_quelli_salvati_il_dettaglio_resta_vuoto(finto):
    """Per esempio la panchina del sistema è cambiata da quando la voce è stata calcolata: i punti salvati restano quelli, la
    formazione non prende un dettaglio che non torna con loro e non ci si riprova a ogni giro."""
    assert _aggiorna(finto) == 2

    def tocca(voci):
        voci[f"{ST}/1"]["consigliata"]["reale"] = 75.0
    prima = _come_prima_di_900(finto, tocca)
    assert _aggiorna(finto) == 2
    dopo = diario.carica(finto.file)["giornate"]
    c = dopo[f"{ST}/1"]["consigliata"]
    assert c["reale"] == 75.0 and c["dettaglio"] is None
    assert isinstance(dopo[f"{ST}/1"]["ricostruita"]["dettaglio"], dict)
    assert _senza_dettagli(dopo) == prima                        # i punti salvati restano quelli, anche il 75,0
    assert diario.spiegazione_punti(dopo[f"{ST}/1"])["righe_frasi"] == [{"chiave": "diario.punti_senza_dettaglio", "param": {}}]
    assert _aggiorna(finto) == 0


def test_se_il_dettaglio_non_si_calcola_le_giornate_nuove_si_scrivono_lo_stesso(finto, monkeypatch, caplog):
    """Un guasto nel completare una voce di prima non deve fermare il Diario (le giornate si scorrono dalla più vecchia): il
    registro del server lo dice una volta, la voce resta com'era con il dettaglio vuoto (non ci si riprova a ogni giro) e la
    giornata nuova si scrive."""
    assert _aggiorna(finto) == 2
    prima = _come_prima_di_900(finto, lambda voci: voci.pop(f"{ST}/2"))
    tentativi = []

    def rotto(*a, **k):
        tentativi.append(1)
        raise RuntimeError("guasto")
    monkeypatch.setattr(diario, "rifai_i_punti", rotto)
    with caplog.at_level("WARNING", logger="fanta.diario"):
        assert _aggiorna(finto) == 2                                              # la 1 segnata, la 2 nuova
        voci = diario.carica(finto.file)["giornate"]
        assert _senza_dettagli(voci)[f"{ST}/1"] == prima[f"{ST}/1"] and f"{ST}/2" in voci
        assert all(voci[f"{ST}/1"][k]["dettaglio"] is None for k in ("consigliata", "ricostruita"))
        assert _aggiorna(finto) == 0                                              # al giro dopo non ci riprova
    assert len(tentativi) == 1 and caplog.text.count("dettaglio dei punti") == 1 and "RuntimeError" in caplog.text
