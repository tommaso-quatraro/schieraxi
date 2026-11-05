"""Indicatori del consiglio nel Diario e in Stato dei dati (C1-C4 di #166, lavoro L4): misurati sulla consigliata MOSTRATA
(l'istantanea congelata alla scadenza), medie sulle ultime 8 giornate e avviso al proprietario. Dati inventati."""
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
def con_ruolo(finto):
    """Come nell'archivio vero, i voti hanno il ruolo: serve alla fantamedia di S2 (`verifica_consiglio.dati_s2`). I dati finti
    del Diario non ce l'hanno, e così restano: senza, gli indicatori non si calcolano ma la voce si scrive lo stesso."""
    finto.dati.voti["ruolo"] = [RUOLI[i - 1] for i in finto.dati.voti["calciatore_id"]]
    return finto


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


def test_due_salvataggi_insieme_contano_un_cambio_solo(tmp_path):
    """L'app e la copia alla scadenza salvano la stessa consigliata nuova nello stesso momento: tutte e due hanno letto
    l'istantanea vecchia e preparato lo stesso cambio, ma chi scrive per secondo trova già la nuova e non lo aggiunge."""
    f = tmp_path / "diario.json"
    diario.salva_istantanea(_app(), ST, f)
    vecchia = diario.carica(f)["istantanee"][f"{ST}/1"]
    c = ic.cambio(vecchia, _app(titolari=MOSTRATI[:-1] + [23]), "2026-09-01T12:00:00")
    nuova = {**vecchia, "titolari": [{"id": i} for i in MOSTRATI[:-1] + [23]]}
    for _ in range(2):
        diario._scrivi(f, istantanee={f"{ST}/1": nuova}, cambi={f"{ST}/1": c})
    assert len(diario.carica(f)["cambi"][f"{ST}/1"]) == 1


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


def test_la_voce_del_diario_ha_c1_c4_sulla_consigliata_mostrata(finto, con_ruolo):
    scelti = MOSTRATI[:-1] + [25]                                       # la tua, con l'attaccante che ha preso 9
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), _scelta(scelti), simulazioni=50,
                                istantanea=_ist(), cambi=(2, 1))
    # mostrata: 11 da 6. S2: la giornata prima hanno preso voto tutti, la fantamedia più alta è dell'attaccante 25 (9)
    assert v["consiglio"] == {"mostrata": "istantanea", "punti_consigliata": 66.0, "punti_s2": 69.0, "punti_schierata": 69.0,
                              "cambi": 2, "cambi_sotto_soglia": 1, **MISURE}


def test_senza_istantanea_si_misura_la_consigliata_ricostruita(finto, con_ruolo):
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    assert v["consiglio"] == {"mostrata": "ricostruita", "punti_consigliata": v["consigliata"]["reale"], "punti_s2": 69.0,
                              "punti_schierata": None, "cambi": None, "cambi_sotto_soglia": None, **SENZA_MISURE}
    fuori_rosa = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), None, simulazioni=50,
                                         istantanea=_ist(titolari=MOSTRATI[:-1] + [99]))
    assert fuori_rosa["consiglio"]["mostrata"] == "ricostruita"         # un mostrato non è più in rosa: non si può rifare


def test_schierata_uguale_alla_mostrata_non_conta_per_c1(finto, con_ruolo):
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), _scelta(list(reversed(MOSTRATI))),
                                simulazioni=50, istantanea=_ist())
    assert v["schierata"] and v["consiglio"]["punti_schierata"] is None


def test_aggiorna_conta_i_cambi_delle_24_ore_prima_della_scadenza(finto, con_ruolo, orologio):
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


def test_ho_schierato_tiene_gli_indicatori(vero, con_ruolo, orologio):
    diario.salva_istantanea(_app(giornata=1), ST, vero.file)
    voce = _salva(vero, 1, "manuale", MOSTRATI[:-1] + [25])
    c = diario.carica(vero.file)["giornate"][f"{ST}/1"]["consiglio"]
    assert c == voce["consiglio"] and c["mostrata"] == "istantanea"
    assert c["punti_consigliata"] == 66.0 and c["punti_schierata"] == 69.0 and c["titolari"] == 11


# ------------------------------------------------------------------ gli indicatori non fermano mai il Diario
def test_se_gli_indicatori_falliscono_la_voce_si_scrive_senza(finto, caplog):
    """I dati finti del Diario non hanno il ruolo nei voti: S2 non si calcola. La voce c'è lo stesso, senza `consiglio`, e nel log
    va solo il tipo d'errore."""
    v = diario.calcola_giornata(finto.dati, ST, 2, Regole(), None, list(range(1, 26)), _scelta(MOSTRATI), simulazioni=50,
                                istantanea=_ist())
    assert "consiglio" not in v and v["consigliata"]["reale"] > 50 and v["schierata"]["reale"] == 66.0
    assert "indicatori del consiglio non calcolati (KeyError)" in caplog.text


def test_aggiorna_scrive_le_voci_anche_se_gli_indicatori_falliscono(finto, orologio, monkeypatch):
    diario.salva_istantanea(_app(giornata=2), ST, finto.file)
    monkeypatch.setattr(diario.avvisi, "prima_partita", lambda *a: (_ for _ in ()).throw(RuntimeError("calendario rotto")))
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    voci = diario.carica(finto.file)["giornate"]
    assert set(voci) == {f"{ST}/1", f"{ST}/2"} and "consiglio" not in voci[f"{ST}/2"]


def test_ho_schierato_funziona_anche_se_gli_indicatori_falliscono(vero, orologio):
    diario.salva_istantanea(_app(giornata=2), ST, vero.file)
    voce = _salva(vero, 2, "manuale", MOSTRATI[:-1] + [25])                 # giornata 2: S2 avrebbe bisogno del ruolo
    assert voce["schierata"]["reale"] == 69.0 and "consiglio" not in voce
    assert diario.carica(vero.file)["giornate"][f"{ST}/2"]["schierata"]["reale"] == 69.0


# ------------------------------------------------------------------ Stato dei dati: totali di tutti, medie, soglie, avviso
def _voce(g, meno_s2=1.0, meno_schierata=None, cambi=1, sotto=0, con_compagno=0, storte=1, spiegate=1, senza_motivo=1):
    """Una voce del Diario con i suoi indicatori (solo quello che serve ai totali)."""
    return {"stagione": ST, "giornata": g, "consiglio": {
        "mostrata": "istantanea", "punti_consigliata": 70.0, "punti_s2": 70.0 - meno_s2,
        "punti_schierata": None if meno_schierata is None else 70.0 - meno_schierata, "cambi": cambi, "cambi_sotto_soglia": sotto,
        "improbabili": con_compagno, "con_compagno": con_compagno, "reparti": 4, "storte": storte, "spiegate": spiegate,
        "titolari": 11, "vuoti": 0, "senza_motivo": senza_motivo}}


def test_totali_per_giornata_su_tutti_gli_utenti():
    primo = [_voce(10), _voce(9, meno_s2=2.0, meno_schierata=-1.0)]
    secondo = [_voce(9, meno_s2=-1.0, cambi=2, sotto=1),
               {"stagione": ST, "giornata": 10, "consigliata": {"reale": 60}},          # voce di prima: niente indicatori
               {"stagione": ST, "giornata": 11, "consiglio": dict.fromkeys(_voce(11)["consiglio"]) | {"mostrata": "ricostruita",
                                                                                                  "punti_consigliata": 60.0}}]
    righe = ic.per_giornata([primo, secondo])
    assert [(r["stagione"], r["giornata"], r["voci"]) for r in righe] == [(ST, 9, 2), (ST, 10, 1), (ST, 11, 1)]
    nona = righe[0]
    assert (nona["con_s2"], nona["somma_meno_s2"], nona["con_schierata"], nona["somma_meno_schierata"]) == (2, 1.0, 1, -1.0)
    assert (nona["con_cambi"], nona["cambi"], nona["cambi_sotto_soglia"]) == (2, 3, 1)
    assert (nona["con_misure"], nona["titolari"], nona["senza_motivo"], nona["storte"]) == (2, 22, 2, 2)
    assert righe[2]["con_s2"] == 0 and righe[2]["con_cambi"] == 0 and righe[2]["con_misure"] == 0     # niente da misurare
    assert all(isinstance(v, (int, float, str)) for r in righe for v in r.values())                  # solo numeri, niente nomi


def test_nessun_verdetto_prima_di_otto_giornate():
    sette = ic.medie(ic.per_giornata([[_voce(g) for g in range(1, 8)]]))
    assert not sette["verdetto"] and sette["regge"] == {"C1": None, "C2": None, "C3": None, "C4": None} and sette["fuori"] == []
    otto = ic.medie(ic.per_giornata([[_voce(g) for g in range(1, 9)]]))
    assert otto["verdetto"] and otto["regge"] == {"C1": True, "C2": True, "C3": True, "C4": True} and otto["fuori"] == []
    assert (otto["giornate"], otto["voci"], otto["meno_s2"], otto["meno_schierata"], otto["cambi"]) == (8, 8, 1.0, None, 1.0)
    assert (otto["cambi_sotto_soglia"], otto["con_compagno"], otto["storte"], otto["spiegate"]) == (0, 0, 8, 8)
    assert otto["senza_motivo"] == 0.091                                                             # 8 su 88
    assert ic.medie([])["meno_s2"] is None and ic.medie([])["giornate"] == 0


@pytest.mark.parametrize("cattive, fuori", [
    ({"meno_s2": -0.5}, "C1"),                       # la scelta semplice fa meglio
    ({"meno_schierata": -2.0}, "C1"),                # la schierata, quando è diversa, fa meglio
    ({"sotto": 1}, "C2"),                            # un cambio per meno di 1 punto atteso
    ({"con_compagno": 1}, "C3"),                     # un titolare che non gioca con un compagno che gioca
    ({"spiegate": 0}, "C4"),                         # una scelta storta senza spiegazione
    ({"senza_motivo": 2}, "C4"),                     # 18% dei titolari senza un motivo proprio
])
def test_ogni_indicatore_esce_dalla_sua_soglia(cattive, fuori):
    m = ic.medie(ic.per_giornata([[_voce(g, **cattive) for g in range(1, 9)]]))
    assert m["fuori"] == [fuori]


@pytest.fixture
def avvisi(tmp_path):
    file = tmp_path / "indicatori.json"
    voci = [_voce(g) for g in range(1, 9)]
    inviati, esito = [], {"riesce": True}

    def manda(titolo, testo):
        if esito["riesce"]:
            inviati.append((titolo, testo))
        return esito["riesce"]

    def passo(g=None, **cattive):
        if g is not None:
            voci.append(_voce(g, **cattive))
        return ic.giro(manda, diari=[voci], file=file)["avvisato"]

    assert passo() == []
    return passo, inviati, esito, file


def test_avviso_dopo_due_giornate_fuori_soglia_una_volta_sola(avvisi):
    passo, inviati, _, file = avvisi
    assert passo(9, sotto=1) == [] and inviati == []                                # fuori la prima volta: si aspetta
    assert passo(10, sotto=1) == ["C2"] and len(inviati) == 1                       # fuori due giornate di fila: un avviso
    assert "C2" in inviati[0][1] and "C1" not in inviati[0][1]
    assert passo() == [] and passo(11) == [] and len(inviati) == 1                  # resta fuori: niente raffiche
    for g in range(12, 20):                                                        # rientra quando i cambi escono dalla finestra
        passo(g)
    assert ic.riepilogo(file)["fuori"] == []
    assert passo(20, sotto=1) == [] and passo(21, sotto=1) == ["C2"] and len(inviati) == 2   # esce di nuovo: nuovo avviso


def test_avviso_non_mandato_si_riprova(avvisi):
    passo, inviati, esito, _ = avvisi
    passo(9, sotto=1)
    esito["riesce"] = False                                                        # canale mancante o rete giù
    assert passo(10, sotto=1) == [] and inviati == []
    esito["riesce"] = True
    assert passo() == ["C2"] and len(inviati) == 1                                  # al giro dopo parte
    assert passo() == [] and len(inviati) == 1


def test_testo_dell_avviso_solo_indicatori_e_numeri():
    m = ic.medie(ic.per_giornata([[_voce(g, meno_s2=-1.5, sotto=1, con_compagno=1, spiegate=0, senza_motivo=3)
                                   for g in range(1, 9)]]))
    assert m["fuori"] == ["C1", "C2", "C3", "C4"]
    titolo, testo = ic.testo_avviso(m["fuori"], m)
    assert titolo == "SchieraXI: consiglio di formazione"
    assert "2 giornate di fila" in testo and "ultime 8 giornate" in testo and "Stato dei dati" in testo
    assert "-1,50 punti" in testo and "8 cambi" in testo and "8 titolari" in testo and "spiegate 0 su 8" in testo and "27%" in testo
    assert all(f"• {c}" in testo for c in ("C1", "C2", "C3", "C4"))


def test_riepilogo_per_stato_dei_dati(tmp_path):
    from fanta import registro_giornate
    file = tmp_path / "indicatori.json"
    vuoto = ic.riepilogo(file)                                                     # mai calcolati: niente, senza errori
    assert vuoto["per_giornata"] == [] and vuoto["aggiornato"] is None and vuoto["giornate"] == 0
    ic.giro(lambda t, x: True, diari=[[_voce(9), _voce(10, meno_s2=-2.0)]], file=file, adesso=datetime(2026, 11, 5, 21, 0))
    r = ic.riepilogo(file)
    assert r["finestra"] == ic.FINESTRA == registro_giornate.FINESTRA and r["aggiornato"] == "2026-11-05T21:00:00"
    assert r["soglie"] == {"C1": 0.0, "C2": 0, "C3": 0, "C4_senza_motivo": 0.1}
    assert r["giornate"] == 2 and not r["verdetto"] and r["meno_s2"] == -0.5
    assert [(g["giornata"], g["voci"], g["meno_s2"], g["fuori"]) for g in r["per_giornata"]] == [(10, 1, -2.0, []), (9, 1, 1.0, [])]
    file.write_text("non è json", encoding="utf-8")
    assert ic.riepilogo(file)["per_giornata"] == []


def test_stato_dei_dati_ha_gli_indicatori_del_consiglio(tmp_path, monkeypatch):
    monkeypatch.setattr(ic, "FILE", tmp_path / "indicatori.json")
    ic.giro(lambda t, x: True, diari=[[_voce(g) for g in range(1, 4)]])
    r = stato_dati.riepilogo(archivio.apri(tmp_path / "t.sqlite"), ST)["consiglio"]
    assert r["giornate"] == 3 and len(r["per_giornata"]) == 3 and r["soglie"]["C4_senza_motivo"] == 0.1


def test_il_giro_legge_il_diario_di_ogni_utente(multiutente, tmp_path):
    import contextlib
    from fanta import account
    from fanta.contesto import Contesto
    ids = []
    for nome in ("primo", "secondo"):
        with contextlib.closing(account.apri()) as db:
            utente, _, _ = account.registra(db, nome, "una-password-lunga-9", account.crea_invito(db, nome))
        ids.append(utente.id)
    for i, uid in enumerate(ids):
        diario._scrivi(Contesto.per_utente(uid).diario, voci={f"{ST}/9": _voce(9, meno_s2=float(i))})
    assert ic.giro(lambda t, x: True, file=tmp_path / "indicatori.json")["giornate"] == 1
    riga = ic.riepilogo(tmp_path / "indicatori.json")["per_giornata"][0]
    assert riga["voci"] == 2 and riga["meno_s2"] == 0.5


def test_il_comando_affidabilita_aggiorna_gli_indicatori_e_avvisa(tmp_path, monkeypatch, capsys):
    """Dopo il Diario di tutti (cron, `python -m fanta affidabilita`) si rifanno i totali e, se serve, parte l'avviso."""
    from fanta import affidabilita, sentinella
    from fanta.__main__ import main
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    apri = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: apri(tmp_path / "t.sqlite"))
    monkeypatch.setattr(affidabilita, "aggiorna_se_serve", lambda *a, **k: False)
    monkeypatch.setattr(diario, "aggiorna", lambda *a, **k: 0)                     # le voci ci sono già
    inviati = []
    monkeypatch.setattr(sentinella, "manda_ntfy", lambda titolo, testo: inviati.append(titolo) or True)
    diario._scrivi(None, voci={f"{ST}/{g}": _voce(g, sotto=int(g > 8)) for g in range(1, 11)})
    main(["affidabilita"])
    assert inviati == ["SchieraXI: consiglio di formazione"]
    assert ic.riepilogo()["giornate"] == 8 and "indicatori del consiglio: 10 giornate" in capsys.readouterr().out
