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
