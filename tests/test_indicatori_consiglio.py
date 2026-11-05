"""Indicatori del consiglio nel Diario e in Stato dei dati (C1-C4 di #166, lavoro L4): misurati sulla consigliata MOSTRATA
(l'istantanea congelata alla scadenza), medie sulle ultime 8 giornate e avviso al proprietario. Dati inventati."""
import json
from datetime import datetime, timedelta

import pytest

from fanta import archivio, diario, stato_dati
from fanta import formazione as fz
from fanta import indicatori_consiglio as ic
from fanta.regole import Regole

from test_diario import RUOLI, ST, _salva, _scelta, finto, vero  # noqa: F401  (fixture del Diario con dati finti)
from test_verifica_consiglio import F, S

MOSTRATI = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 22]          # 3-4-3 della rosa finta (id 1-3 P, 4-11 D, 12-19 C, 20-25 A)


def _app(titolari=MOSTRATI, panchina=(2, 7, 16, 23), giornata=1, **schede):
    """Una consigliata come quella di `consigli.formazione` per la rosa finta: schede con i numeri, moduli e perché.
    `schede` = {"s<id>": scheda} per cambiare qualche giocatore."""
    def scheda(i):
        s = schede.get(f"s{i}", S(i, RUOLI[i - 1]))
        return s | {"fv_atteso": s.get("fv_atteso", 6.0), "voto_atteso": 6.0}
    f = F([scheda(i) for i in titolari], [scheda(i) for i in panchina])
    return f | {"giornata": giornata, "punteggio_atteso": 70.0, "livelli": [{"rischio": 0, "nome": "Equilibrata"}]}


@pytest.fixture
def orologio(monkeypatch):
    ora = {"t": datetime(2026, 9, 1, 10, 0)}
    monkeypatch.setattr(diario, "_adesso", lambda: ora["t"])
    return ora


# ------------------------------------------------------------------ istantanea: C3 e C4 della consigliata mostrata
def test_l_istantanea_ricorda_c3_e_c4_della_consigliata_mostrata(tmp_path):
    f = tmp_path / "diario.json"
    form = _app(s4=S(4, "D", p=0.1), s7=S(7, "D", p=0.7), s13=S(13, "C", perche=("gioca",)), s16=S(16, "C", punti=6.0))
    assert diario.salva_istantanea(form, ST, f)
    m = diario.carica(f)["istantanee"][f"{ST}/1"]["misure"]
    # C3: il 4 gioca il 10% e il 7, in panchina, il 70%. C4: il 16 (escluso) ha più punti attesi dei centrocampisti titolari, senza
    # la nota «titolare anche se incerto»; il 13 ha solo «gioca N%» come motivo
    assert m == {"improbabili": 1, "con_compagno": 1, "reparti": 4, "storte": 1, "spiegate": 0, "titolari": 11, "vuoti": 0,
                 "senza_motivo": 1}


def test_istantanea_senza_schede_non_ha_misure(tmp_path):
    f = tmp_path / "diario.json"
    form = _app()
    form.pop("schede")
    assert diario.salva_istantanea(form, ST, f)
    assert "misure" not in diario.carica(f)["istantanee"][f"{ST}/1"]


# ------------------------------------------------------------------ C2: i cambi, registrati quando l'istantanea si sovrascrive
def test_un_cambio_di_titolari_si_registra_quando_l_istantanea_si_sovrascrive(tmp_path, orologio):
    f = tmp_path / "diario.json"
    assert diario.salva_istantanea(_app(), ST, f)
    assert diario.carica(f).get("cambi", {}) == {}                                     # la prima non è un cambio
    orologio["t"] += timedelta(hours=1)
    assert diario.salva_istantanea(_app(panchina=(23, 16, 7, 2)), ST, f)                # cambia solo la panchina
    assert diario.carica(f).get("cambi", {}) == {}
    orologio["t"] += timedelta(hours=1)
    nuova = _app(titolari=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 23], panchina=(2, 7, 16, 22))      # il 23 al posto del 22
    assert diario.salva_istantanea(nuova, ST, f)
    c = diario.carica(f)["cambi"][f"{ST}/1"]
    assert len(c) == 1 and c[0]["quando"] == "2026-09-01T12:00:00" and c[0]["motivata"] is False
    assert c[0]["prima"] == MOSTRATI and c[0]["dopo"] == [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 23] and c[0]["panchina"] == [2, 7, 16, 22]
    assert [r[0] for r in c[0]["rosa"]] == [int(k) for k in nuova["schede"]]           # i numeri di allora, nell'ordine della rosa
    assert c[0]["rosa"][0] == [1, "P", 0.9, 6.0, 6.0]
    assert diario.salva_istantanea(nuova, ST, f) is False                              # uguale: niente di nuovo
    assert len(diario.carica(f)["cambi"][f"{ST}/1"]) == 1


@pytest.mark.parametrize("nuova, perche", [
    (_app(titolari=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 23], panchina=(2, 7, 16, 22), s22=S(22, "A", p=0.1)), "improbabile"),
    (_app(titolari=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 23], panchina=(2, 7, 16, 22), s22=S(22, "A", stato="infortunato")), "fuori"),
    (_app(titolari=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 23], panchina=(2, 7, 16)), "uscito dalla rosa"),
])
def test_cambio_per_un_titolare_che_non_gioca_piu_e_motivato(tmp_path, nuova, perche):
    f = tmp_path / "diario.json"
    diario.salva_istantanea(_app(), ST, f)
    diario.salva_istantanea(nuova, ST, f)
    c = diario.carica(f)["cambi"][f"{ST}/1"]
    assert c[0]["motivata"] is True, perche
    assert "rosa" not in c[0]                                                          # non serve ricalcolarne il valore


def test_cambi_tenuti_al_massimo(tmp_path, orologio):
    f = tmp_path / "diario.json"
    for n in range(ic.MAX_CAMBI + 3):
        orologio["t"] += timedelta(minutes=10)
        diario.salva_istantanea(_app(titolari=MOSTRATI[:-1] + [22 + n % 2], panchina=(2, 7, 16)), ST, f)
    c = diario.carica(f)["cambi"][f"{ST}/1"]
    assert len(c) == ic.MAX_CAMBI and c[-1]["quando"] == orologio["t"].isoformat(timespec="seconds")


def test_l_elenco_del_diario_non_manda_i_cambi_alle_app(tmp_path, orologio):
    f = tmp_path / "diario.json"
    diario.salva_istantanea(_app(), ST, f)
    diario.salva_istantanea(_app(titolari=MOSTRATI[:-1] + [23]), ST, f)
    diario._scrivi(f, voci={f"{ST}/1": {"stagione": ST, "giornata": 1, "consigliata": {"atteso": 70, "reale": 66}, "schierata": None}})
    e = diario.elenco(f)
    assert "cambi" not in e and "cambi" not in e["giornate"][0]["istantanea"]


# ------------------------------------------------------------------ C2 a giornata finita: i cambi delle 24 ore prima della scadenza
SCADENZA = datetime(2026, 9, 1, 18, 0)


def _rosa_cambio(mu=None):
    """La rosa finta come la ricorda un cambio: tutti al 90% con fantavoto atteso 6 (salvo `mu` = {id: valore})."""
    return [[i, RUOLI[i - 1], 0.9, (mu or {}).get(i, 6.0), 6.0] for i in range(1, 26)]


def _cambio(ore_prima, dopo=MOSTRATI[:-1] + [23], rosa=None, motivata=False):
    rosa = rosa or _rosa_cambio()
    giocatori = {r[0]: fz.Giocatore(r[0], "", r[1], r[2], r[3], r[4]) for r in rosa}
    panchina = fz._panchina(list(giocatori.values()), [giocatori[i] for i in dopo], Regole())
    return {"quando": (SCADENZA - timedelta(hours=ore_prima)).isoformat(timespec="seconds"), "prima": MOSTRATI, "dopo": dopo,
            "motivata": motivata, "rosa": rosa, "panchina": [g.id for g in panchina]}


def test_contano_solo_i_cambi_delle_24_ore_prima_della_scadenza():
    cambi = [_cambio(30, motivata=True), _cambio(24, motivata=True), _cambio(23, motivata=True), _cambio(1, motivata=True),
             _cambio(-1, motivata=True)]                                                   # l'ultimo è dopo la scadenza
    assert ic.conta_cambi(cambi, SCADENZA, Regole()) == (3, 0)
    assert ic.conta_cambi([], SCADENZA, Regole()) == (0, 0)
    assert ic.conta_cambi(cambi, None, Regole()) == (None, None)                           # senza calendario non si misura


def test_un_cambio_che_vale_meno_di_un_punto_atteso_e_sotto_soglia():
    poco = _cambio(2, rosa=_rosa_cambio({23: 6.05}))                                      # il 23 vale appena più del 22
    assert ic.conta_cambi([poco], SCADENZA, Regole()) == (1, 1)
    tanto = _cambio(2, rosa=_rosa_cambio({23: 9.0}))                                      # quasi 3 punti attesi in più
    assert ic.conta_cambi([tanto], SCADENZA, Regole()) == (1, 0)
    assert ic.conta_cambi([{**poco, "motivata": True}], SCADENZA, Regole()) == (1, 0)     # un titolare non giocava più: va bene
    senza_numeri = {k: v for k, v in poco.items() if k != "rosa"}
    assert ic.conta_cambi([senza_numeri], SCADENZA, Regole()) == (1, 0)                   # non ricalcolabile: conta solo come cambio


def test_il_valore_del_cambio_e_quello_della_misura_in_laboratorio():
    """Lo stesso conto di `verifica_consiglio` (e della consigliata stabile): nuova contro i titolari di prima con la panchina del
    sistema, sulle stesse simulazioni dell'app."""
    from fanta import verifica_consiglio as vc
    c = _cambio(2, rosa=_rosa_cambio({23: 7.0}))
    rosa = [fz.Giocatore(r[0], "", r[1], r[2], r[3], r[4]) for r in c["rosa"]]
    per_id = {g.id: g for g in rosa}
    val = fz.Valutatore(rosa, Regole(), vc.SIMULAZIONI)
    atteso = (val.atteso([per_id[i] for i in c["dopo"]], [per_id[i] for i in c["panchina"]])
              - vc.valore_di_prima(val, rosa, MOSTRATI, Regole()))
    assert ic.guadagno(c, Regole()) == pytest.approx(atteso) and 0.5 < atteso < 1.5


# ------------------------------------------------------------------ la voce del Diario
MISURE = {"improbabili": 1, "con_compagno": 0, "reparti": 4, "storte": 2, "spiegate": 1, "titolari": 11, "vuoti": 0, "senza_motivo": 3}
SENZA_MISURE = dict.fromkeys(MISURE)


def _ist(titolari=MOSTRATI, panchina=(2, 7, 16, 23), misure=MISURE):
    return {"giornata": 2, "modulo": "3-4-3", "titolari": [{"id": i} for i in titolari], "panchina": [{"id": i} for i in panchina],
            "atteso": 70.0, "stile": "Equilibrata", **({"misure": misure} if misure else {})}


def test_la_voce_del_diario_ha_c1_c4_sulla_consigliata_mostrata(finto):
    scelti = MOSTRATI[:-1] + [25]                                       # la tua, con l'attaccante che ha preso 9
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), _scelta(scelti), simulazioni=50,
                                istantanea=_ist(), cambi=(2, 1))
    # mostrata: 11 da 6. S2: la giornata prima hanno preso voto tutti, la fantamedia più alta è dell'attaccante 25 (9)
    assert v["consiglio"] == {"mostrata": "istantanea", "punti_consigliata": 66.0, "punti_s2": 69.0, "punti_schierata": 69.0,
                              "cambi": 2, "cambi_sotto_soglia": 1, **MISURE}


def test_senza_istantanea_si_misura_la_consigliata_ricostruita(finto):
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    assert v["consiglio"] == {"mostrata": "ricostruita", "punti_consigliata": v["consigliata"]["reale"], "punti_s2": 69.0,
                              "punti_schierata": None, "cambi": None, "cambi_sotto_soglia": None, **SENZA_MISURE}
    fuori_rosa = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), None, simulazioni=50,
                                         istantanea=_ist(titolari=MOSTRATI[:-1] + [99]))
    assert fuori_rosa["consiglio"]["mostrata"] == "ricostruita"         # un mostrato non è più in rosa: non si può rifare


def test_schierata_uguale_alla_mostrata_non_conta_per_c1(finto):
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), _scelta(list(reversed(MOSTRATI))),
                                simulazioni=50, istantanea=_ist())
    assert v["schierata"] and v["consiglio"]["punti_schierata"] is None


def test_aggiorna_conta_i_cambi_delle_24_ore_prima_della_scadenza(finto, orologio):
    orologio["t"] = datetime(2026, 8, 30, 10, 0)                         # la prima partita della giornata 2: 1/9 alle 18
    diario.salva_istantanea(_app(giornata=2), ST, finto.file)
    orologio["t"] = datetime(2026, 8, 30, 11, 0)                         # cambio di due giorni prima: non conta
    diario.salva_istantanea(_app(titolari=MOSTRATI[:-1] + [23], panchina=(2, 7, 16, 22), giornata=2), ST, finto.file)
    orologio["t"] = datetime(2026, 9, 1, 12, 0)                          # 6 ore prima: conta, e vale quasi niente
    diario.salva_istantanea(_app(giornata=2, panchina=(2, 7, 16, 23)), ST, finto.file)
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    voci = diario.carica(finto.file)["giornate"]
    c = voci[f"{ST}/2"]["consiglio"]
    assert c["mostrata"] == "istantanea" and c["punti_consigliata"] == 66.0
    assert (c["cambi"], c["cambi_sotto_soglia"]) == (1, 1)
    assert c["titolari"] == 11 and c["improbabili"] == 0                 # le misure dell'ultima istantanea, la mostrata
    assert voci[f"{ST}/1"]["consiglio"]["mostrata"] == "ricostruita"     # nessuna istantanea per la giornata 1


def test_ho_schierato_tiene_gli_indicatori(vero, orologio):
    diario.salva_istantanea(_app(giornata=1), ST, vero.file)
    voce = _salva(vero, 1, "manuale", MOSTRATI[:-1] + [25])
    c = diario.carica(vero.file)["giornate"][f"{ST}/1"]["consiglio"]
    assert c == voce["consiglio"] and c["mostrata"] == "istantanea"
    assert c["punti_consigliata"] == 66.0 and c["punti_schierata"] == 69.0 and c["titolari"] == 11
