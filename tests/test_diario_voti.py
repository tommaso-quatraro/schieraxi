"""#793: il Diario calcola una giornata solo quando i suoi voti sono arrivati (`fasi.voti_arrivati`) e la rifà quando i voti
cambiano: l'ultima partita arrivata dopo, una correzione dei giorni dopo. Per questo ogni voce ha l'impronta dei voti con cui è
stata calcolata. Dati inventati: giornata 1 con due partite, a-b (giocatori 1-19) e c-d (giocatori 20-25), tutte e due giocate
per il calendario. Tutti prendono 6, tranne l'attaccante 25 (seconda partita) che prende 9."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import archivio, consigli, diario, lega, scelte
from fanta.regole import Regole

ST = "2026-27"
CHIAVE = f"{ST}/1"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25
SCELTI = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]             # 3-4-3, con i tre attaccanti della seconda partita
CON_TUTTI_I_VOTI = 10 * 6 + 9                                  # 69,0
DATA = {1: "2026-09-01 18:00", 2: "2026-09-01 20:45"}          # le due partite: a-b e c-d


def _voti_con_data(db) -> pd.DataFrame:
    """I voti dell'archivio con la data della loro partita, come li vede il calcolo (`modello.carica`)."""
    v = pd.read_sql_query("SELECT * FROM voti", db)
    return v.assign(data=v["squadra"].map({"a": DATA[1], "b": DATA[1], "c": DATA[2], "d": DATA[2]}))


@pytest.fixture
def mondo(monkeypatch, tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    for n, (casa, trasferta) in enumerate((("a", "b"), ("c", "d")), start=1):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, 1, ?, ?, ?, 1)",
                   (n, ST, DATA[n], casa, trasferta))
    dati = SimpleNamespace(partite=pd.DataFrame([{"id": n, "stagione": ST, "giornata": 1, "data": DATA[n], "giocata": 1} for n in (1, 2)]),
                           voti=_voti_con_data(db))

    def previsioni(d, stagione, giornata, regole, par):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0,
                              "partita": 1 if i < 20 else 2} for i in range(1, 26)])
    monkeypatch.setattr(diario, "previsioni", previsioni)
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db_: dati)
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26)])], "Mia")
    m = SimpleNamespace(db=db, dati=dati, rose=rose, diario=tmp_path / "diario.json", scelte=tmp_path / "scelte.json")
    # «Ho schierato la consigliata», con la spunta «L'ho messa»: quello che l'utente ha scritto e che non si deve perdere
    scelte.salva(ST, 1, SCELTI, "3-4-3", m.scelte, tipo="consigliata", messa=True)
    return m


def _voti(m, partita: int, diversi: dict[int, float] | None = None) -> None:
    """I voti di una partita arrivano (o si correggono): nella tabella `voti`, da cui si vede se sono arrivati, e nei dati del
    calcolo, come dopo un aggiornamento vero."""
    ids, squadre = (range(1, 20), "ab") if partita == 1 else (range(20, 26), "cd")
    voto = {25: 9.0} | (diversi or {})
    archivio.inserisci(m.db, "voti", [{"stagione": ST, "giornata": 1, "calciatore_id": i, "nome": f"G{i}", "squadra": squadre[i % 2],
                                       "ruolo": RUOLI[i - 1], "voto_red": voto.get(i, 6.0)} for i in ids])
    m.dati.voti = _voti_con_data(m.db)


def _aggiorna(m, regole=None) -> int:
    return diario.aggiorna(m.db, regole or Regole(), m.rose, m.diario, simulazioni=50, file_scelte=m.scelte)


def _voce(m) -> dict:
    return diario.carica(m.diario)["giornate"][CHIAVE]


def test_la_giornata_entra_nel_diario_solo_quando_ci_sono_i_voti_di_tutte_le_partite(mondo):
    """Il calendario dà giocata anche l'ultima partita ma i suoi voti non sono usciti: prima la voce si scriveva lo stesso (54,0,
    i tre attaccanti senza voto) e non si rifaceva più."""
    _voti(mondo, 1)
    assert _aggiorna(mondo) == 0
    assert CHIAVE not in diario.carica(mondo.diario)["giornate"]
    _voti(mondo, 2)
    assert _aggiorna(mondo) == 1
    assert _voce(mondo)["schierata"]["reale"] == CON_TUTTI_I_VOTI
    e = diario.elenco(mondo.diario)["giornate"][0]
    assert e["fatti_e_attesi"]["fatti"] == CON_TUTTI_I_VOTI
    assert "impronta_voti" not in e                                       # l'impronta resta nel file: l'API non cambia
    assert _aggiorna(mondo) == 0                                          # poi resta ferma


def test_una_correzione_dei_voti_dei_giorni_dopo_rifa_la_voce(mondo):
    _voti(mondo, 1)
    _voti(mondo, 2)
    assert _aggiorna(mondo) == 1
    assert _aggiorna(mondo) == 0
    _voti(mondo, 2, {25: 10.0})                                           # il voto del 25 corretto da 9 a 10
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v["schierata"]["reale"] == CON_TUTTI_I_VOTI + 1
    assert {g["id"]: g["fv"] for g in v["giocatori"]}[25] == 10.0
    assert _aggiorna(mondo) == 0                                          # una volta sola, non a ogni giro


def test_ho_schierato_prima_dei_voti_dell_ultima_partita_si_corregge_quando_arrivano(mondo):
    """«Ho schierato» non passa dal controllo dei voti arrivati (giornata finita per il calendario): la voce si scrive con i voti
    che ci sono, ma con la loro impronta, e il giro dopo l'arrivo dei voti la rifà con la scelta registrata."""
    _voti(mondo, 1)
    voce = diario.salva_schierata(mondo.db, Regole(), mondo.rose, 1, "manuale", SCELTI, mondo.diario, mondo.scelte, simulazioni=50)
    assert voce["schierata"]["reale"] < CON_TUTTI_I_VOTI
    _voti(mondo, 2)
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v["schierata"]["reale"] == CON_TUTTI_I_VOTI and v["schierata"]["tipo"] == "manuale"
    assert sorted(t["id"] for t in v["schierata"]["titolari"]) == sorted(SCELTI)
    assert _aggiorna(mondo) == 0


MOSTRATA = [1, 4, 5, 6, 12, 13, 14, 15, 20, 22, 25]           # la consigliata mostrata prima della scadenza: 22 invece di 21


def _istantanea(m) -> dict:
    """La consigliata congelata alla scadenza, diversa dalla scelta dell'utente: la giornata ha un verdetto in «Le tue scelte»."""
    g = lambda i: {"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1]}      # noqa: E731
    ist = {"giornata": 1, "modulo": "3-4-3", "titolari": [g(i) for i in MOSTRATA], "panchina": [g(i) for i in (3, 24, 23, 21, 19, 18, 17)],
           "atteso": 70.0, "stile": None, "calcolata": "2026-09-01T17:50:00"}
    diario._scrivi(m.diario, istantanee={CHIAVE: ist})
    return ist


def _voce_di_prima(m, istantanea=None, con_tutti_i_voti=False) -> dict:
    """Una voce come quelle già scritte sul server prima di #793, senza l'impronta dei voti: di base calcolata quando i voti della
    seconda partita non c'erano ancora."""
    completi = m.dati.voti
    if not con_tutti_i_voti:
        m.dati.voti = completi[completi["calciatore_id"] < 20].copy()
    voce = diario.calcola_giornata(m.dati, ST, 1, Regole(), None, list(range(1, 26)), scelte.leggi(ST, 1, m.scelte), simulazioni=50,
                                   istantanea=istantanea)
    m.dati.voti = completi
    voce.pop("impronta_voti", None)
    diario._scrivi(m.diario, voci={CHIAVE: voce})
    return voce


def _vendi(m, i) -> None:
    squadra = m.rose.squadra("Mia")
    squadra.giocatori = [g for g in squadra.giocatori if g.id != i]


def test_una_voce_senza_impronta_si_rifa_una_volta_e_tiene_ho_schierato(mondo):
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo)
    assert prima["schierata"]["reale"] < CON_TUTTI_I_VOTI                # il numero sbagliato rimasto sul server
    diario._scrivi(mondo.diario, istantanee={f"{ST}/5": {"giornata": 5, "titolari": [{"id": i} for i in SCELTI]}})     # altro nel file
    assert _aggiorna(mondo) == 1                                          # il primo giro dopo il rilascio la rifà
    v = _voce(mondo)
    assert v["schierata"]["reale"] == CON_TUTTI_I_VOTI
    # quello che l'utente ha scritto resta: gli stessi titolari, «Ho schierato la consigliata», «L'ho messa»
    assert [t["id"] for t in v["schierata"]["titolari"]] == [t["id"] for t in prima["schierata"]["titolari"]]
    assert (v["schierata"]["tipo"], v["schierata"]["confermata"]) == ("consigliata", True)
    assert scelte.leggi(ST, 1, mondo.scelte)["titolari"] == SCELTI
    assert f"{ST}/5" in diario.carica(mondo.diario)["istantanee"]
    assert _aggiorna(mondo) == 0                                          # e poi non più


def test_la_migrazione_non_toglie_la_giornata_da_le_tue_scelte(mondo):
    """Decisione del coordinatore: la migrazione rifà solo i punti. Qui un titolare della consigliata mostrata (22) non è più nella
    rosa: rifatta da zero, la voce passava a «ricostruita» e usciva da «Le tue scelte» e dall'affidabilità. La mostrata con la rosa
    di oggi non si valuta (come in «Correggi»), e allora nessun numero della voce cambia (ricontrollo di #798)."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo, _istantanea(mondo))
    esito = diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"]
    assert prima["consigliata"]["origine"] == "mostrata" and len(esito) == 1
    _vendi(mondo, 22)
    assert _aggiorna(mondo) == 1                                          # solo l'impronta
    v = _voce(mondo)
    assert v.pop("impronta_voti") and v == prima
    e = diario.elenco(mondo.diario)
    assert e["scelte_tue"]["per_giornata"] == esito and e["affidabilita"]["senza_istantanea"] == 0
    assert _aggiorna(mondo) == 0                                          # e i giri dopo non ci riprovano


@pytest.mark.parametrize("venduto", [None, 22, 24])                    # nessuno, un titolare della mostrata, la riserva entrata
def test_con_gli_stessi_voti_la_migrazione_cambia_solo_l_impronta(mondo, venduto):
    """Una voce già giusta (calcolata con tutti i voti) resta uguale: stessi punti, stesso verdetto. Il 21, titolare della scelta,
    non prende voto e al suo posto entra il 24, prima riserva della panchina scelta dal sistema con la rosa di allora."""
    _voti(mondo, 1)
    _voti(mondo, 2, {21: None})
    prima = _voce_di_prima(mondo, _istantanea(mondo), con_tutti_i_voti=True)
    esito = diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"]
    if venduto:
        _vendi(mondo, venduto)
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v.pop("impronta_voti") and v == prima
    assert diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"] == esito
    assert _aggiorna(mondo) == 0


def test_una_correzione_dopo_il_rilascio_non_toglie_il_verdetto(mondo):
    """Stessa strada per una voce che ha già l'impronta: se cambiano i voti cambiano solo i punti. Con il 22, titolare della
    mostrata, non più in rosa la mostrata non si rifà, e allora non cambia nessun numero: tutti insieme o nessuno."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    _istantanea(mondo)
    assert _aggiorna(mondo) == 1
    assert _voce(mondo)["consigliata"]["origine"] == "mostrata"
    _vendi(mondo, 22)
    _voti(mondo, 2, {25: 10.0})
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v["consigliata"]["origine"] == "mostrata"
    assert v["consigliata"]["reale"] == v["schierata"]["reale"] == CON_TUTTI_I_VOTI
    assert diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"][0]["esito"] == "pari"


def test_un_titolare_della_mostrata_venduto_con_i_voti_a_meta_lascia_il_verdetto_com_era(mondo):
    """Ricontrollo di #798, sonda del revisore: voce di prima con i voti a metà, poi il 22, titolare della mostrata, è venduto. La
    tua veniva rifatta (54,0 → 69,0) e la mostrata no (54,0): «Le tue scelte» passava da «pari» a «hai fatto meglio di 15 punti».
    Decisione del coordinatore: i numeri che si confrontano cambiano tutti insieme o nessuno."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo, _istantanea(mondo))
    esito = diario.elenco(mondo.diario)["scelte_tue"]
    assert esito["per_giornata"][0]["esito"] == "pari"
    _vendi(mondo, 22)
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert (v["schierata"]["reale"], v["consigliata"]["reale"], v["ricostruita"]["reale"]) == (
        prima["schierata"]["reale"], prima["consigliata"]["reale"], prima["ricostruita"]["reale"])
    assert v["consiglio"] == prima["consiglio"] and v["giocatori"] == prima["giocatori"]
    assert diario.elenco(mondo.diario)["scelte_tue"] == esito             # verdetto e media invariati

def test_con_i_voti_cambiati_si_rifanno_anche_i_punti_degli_indicatori(mondo):
    """Gli indicatori del consiglio della voce (`consiglio`) seguono i punti rifatti: quelli della consigliata e della schierata
    (diversa dalla mostrata) sono i nuovi `reale`, S2 si rifà con la rosa di allora; il resto (C2-C4, chi è la consigliata) resta."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo, _istantanea(mondo))
    assert prima["consiglio"]["punti_s2"] is not None                   # con il ruolo nei voti S2 si calcola
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    c = v["consiglio"]
    assert c["punti_consigliata"] == v["consigliata"]["reale"] == CON_TUTTI_I_VOTI
    assert c["punti_schierata"] == v["schierata"]["reale"] == CON_TUTTI_I_VOTI
    assert c["punti_s2"] is not None and c["punti_s2"] != prima["consiglio"]["punti_s2"]      # S2 ha giocatori della seconda partita
    assert {k: x for k, x in c.items() if not k.startswith("punti_")} == {k: x for k, x in prima["consiglio"].items()
                                                                          if not k.startswith("punti_")}


def test_una_voce_senza_impronta_con_ho_schierato_ma_senza_piu_la_scelta_tiene_la_schierata(mondo, monkeypatch):
    """La scelta non c'è più: la formazione schierata resta quella della voce (titolari, tipo, «L'ho messa») e si rifanno solo i
    suoi punti; i giri dopo non rifanno le simulazioni."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo)
    scelte.cancella(ST, 1, mondo.scelte)
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)["schierata"]
    assert {k: x for k, x in v.items() if k != "reale"} == {k: x for k, x in prima["schierata"].items() if k != "reale"}
    assert v["reale"] == CON_TUTTI_I_VOTI
    monkeypatch.setattr(diario.fz, "migliore", lambda *a, **k: pytest.fail("non deve rifare le simulazioni"))
    assert _aggiorna(mondo) == 0


def test_con_le_regole_cambiate_una_voce_che_perde_la_schierata_resta_com_era(mondo, monkeypatch):
    """Le regole cambiano e la voce si rifà da zero; la scelta c'è ed è valida con la rosa, ma rifatta non si valuta più (qui le
    previsioni danno il 25 come portiere: due portieri). Resta la voce di prima, con la formazione schierata e i soli punti rifatti,
    e i giri dopo non rifanno le simulazioni ogni volta."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    assert _aggiorna(mondo) == 1
    prima = _voce(mondo)
    nuove = Regole()
    nuove.bonus.rigore_sbagliato = -3.0
    previsioni = diario.previsioni
    monkeypatch.setattr(diario, "previsioni", lambda *a: previsioni(*a).assign(
        ruolo=lambda p: p["ruolo"].where(p["id"] != 25, "P")))
    assert _aggiorna(mondo, nuove) == 1                                   # rifatta una volta, poi tenuta com'era
    assert _voce(mondo)["schierata"] == prima["schierata"]
    monkeypatch.setattr(diario.fz, "migliore", lambda *a, **k: pytest.fail("non deve rifare le simulazioni"))
    assert _aggiorna(mondo, nuove) == 0
    assert _voce(mondo)["schierata"] == prima["schierata"]


def _togli_impronta(m) -> dict:
    d = diario.carica(m.diario)
    d["giornate"][CHIAVE].pop("impronta_voti")
    m.diario.write_text(json.dumps(d), encoding="utf-8")
    return d["giornate"][CHIAVE]


def _correggi(m) -> float:
    diario.salva_schierata(m.db, Regole(), m.rose, 1, "manuale", SCELTI, m.diario, m.scelte, simulazioni=50)
    return _voce(m)["consigliata"]["reale"]


def test_al_rilascio_una_voce_scritta_dopo_la_vendita_di_una_riserva_resta_uguale(mondo):
    """Revisione di #798, scenario del revisore: il 22, titolare della mostrata, non prende voto; il 24, prima riserva
    dell'istantanea, prende 8 ma era già venduto quando la voce è stata calcolata. Al rilascio, con gli stessi voti, la
    consigliata passava da 69,0 a 71,0 e l'esito in «Le tue scelte» cambiava. Con i voti uguali si scrive solo l'impronta."""
    _voti(mondo, 1)
    _voti(mondo, 2, {22: None, 24: 8.0})
    _istantanea(mondo)
    _vendi(mondo, 24)
    assert _aggiorna(mondo) == 1
    prima = _togli_impronta(mondo)
    esito = diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"]
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v.pop("impronta_voti") and v == prima
    assert diario.elenco(mondo.diario)["scelte_tue"]["per_giornata"] == esito
    assert _aggiorna(mondo) == 0


def test_correggi_e_rilascio_danno_lo_stesso_numero_anche_con_una_riserva_venduta(mondo):
    """Revisione di #798: «Correggi» e il giro del cron contano con lo stesso insieme di giocatori (la rosa di oggi), quindi il
    numero non oscilla. Prima: 69,0 dopo «Correggi», 71,0 dopo il giro, di nuovo 69,0 dopo un altro «Correggi»."""
    _voti(mondo, 1)
    _voti(mondo, 2, {22: None, 24: 8.0})
    _istantanea(mondo)
    assert _aggiorna(mondo) == 1                                          # voce scritta con la rosa intera
    _vendi(mondo, 24)
    dopo_correggi = _correggi(mondo)
    _togli_impronta(mondo)
    assert _aggiorna(mondo) == 1
    assert _voce(mondo)["consigliata"]["reale"] == dopo_correggi
    assert _correggi(mondo) == dopo_correggi


def test_con_i_voti_cambiati_i_punti_rifatti_sono_quelli_di_correggi(mondo):
    """Quando i voti cambiano davvero (voce calcolata senza i voti della seconda partita), i punti rifatti dal giro del cron sono
    quelli che darebbe «Correggi»: stessa funzione e stesso insieme di giocatori."""
    _voti(mondo, 1)
    _voti(mondo, 2, {22: None, 24: 8.0})
    prima = _voce_di_prima(mondo, _istantanea(mondo))
    assert _aggiorna(mondo) == 1
    dal_giro = _voce(mondo)
    assert dal_giro["schierata"]["reale"] != prima["schierata"]["reale"]  # i punti sono stati rifatti davvero
    assert _correggi(mondo) == dal_giro["consigliata"]["reale"]
    assert _voce(mondo)["schierata"]["reale"] == dal_giro["schierata"]["reale"]
    assert _aggiorna(mondo) == 0


def test_con_i_voti_cambiati_e_un_venduto_in_una_formazione_la_voce_resta_com_era(mondo):
    """Il 24, titolare della ricostruita e riserva della mostrata, viene venduto dopo il calcolo della voce: la ricostruita non si
    rifà, quindi non cambia nessun numero (tutti insieme o nessuno), e i giri dopo non ci riprovano."""
    _voti(mondo, 1)
    _voti(mondo, 2, {22: None, 24: 8.0})
    prima = _voce_di_prima(mondo, _istantanea(mondo))
    assert 24 in [t["id"] for t in prima["ricostruita"]["titolari"]]
    _vendi(mondo, 24)
    assert _aggiorna(mondo) == 1
    v = _voce(mondo)
    assert v.pop("impronta_voti") and v == prima
    assert _aggiorna(mondo) == 0


def test_regole_cambiate_su_una_voce_con_i_voti_a_meta_che_perde_la_schierata(mondo, monkeypatch):
    """Revisione di #798 (sonda del revisore): voce di prima con i voti a metà (54,0), poi cambiano le regole e la scelta, rifatta,
    non si valuta più. Prima restava 54,0 con l'impronta nuova, e la correzione di #793 non le arrivava più. Ora se ne rifanno i
    punti: 69,0, con la formazione schierata di prima."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    prima = _voce_di_prima(mondo)
    assert prima["schierata"]["reale"] < CON_TUTTI_I_VOTI
    nuove = Regole()
    nuove.bonus.rigore_sbagliato = -3.0
    previsioni = diario.previsioni
    monkeypatch.setattr(diario, "previsioni", lambda *a: previsioni(*a).assign(
        ruolo=lambda p: p["ruolo"].where(p["id"] != 25, "P")))
    assert _aggiorna(mondo, nuove) == 1
    v = _voce(mondo)
    assert v["schierata"]["reale"] == CON_TUTTI_I_VOTI and v["schierata"]["titolari"] == prima["schierata"]["titolari"]
    assert _aggiorna(mondo, nuove) == 0


def test_un_correggi_arrivato_mentre_il_cron_rifa_la_voce_non_si_perde(mondo, monkeypatch):
    """Il cron rifà i punti della voce perché i voti sono cambiati. Intanto l'utente tocca «Correggi» e registra altri titolari:
    quando il cron scrive, resta la voce dell'utente."""
    _voti(mondo, 1)
    _voti(mondo, 2)
    assert _aggiorna(mondo) == 1
    _voti(mondo, 2, {25: 10.0})
    corretti = [1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 25]                   # 4-4-2
    rifai_vera, fatto = diario.rifai_i_punti, {}

    def rifai_lenta(*a, **k):
        voce = rifai_vera(*a, **k)
        if not fatto:                                                     # «nel frattempo» l'app salva la correzione
            fatto["in_corso"] = True
            fatto["voce"] = diario.salva_schierata(mondo.db, Regole(), mondo.rose, 1, "manuale", corretti, mondo.diario, mondo.scelte,
                                                   simulazioni=50)
        return voce
    monkeypatch.setattr(diario, "rifai_i_punti", rifai_lenta)
    _aggiorna(mondo)
    assert fatto
    assert sorted(t["id"] for t in _voce(mondo)["schierata"]["titolari"]) == sorted(corretti)
    assert _voce(mondo)["schierata"] == fatto["voce"]["schierata"]


def test_l_impronta_cambia_con_voti_e_bonus_non_con_nome_squadra_o_ordine():
    righe = [{"stagione": ST, "giornata": g, "calciatore_id": i, "nome": f"G{i}", "squadra": "a", "data": "2026-09-01 18:00", "t": 1,
              "voto_red": 6.0, "fv_red": 6.0, "gol": 0, "assist": 0} for g in (1, 2) for i in (1, 2, 3)]
    impronta = lambda df: diario.impronta_voti(SimpleNamespace(voti=df), ST, 1)      # noqa: E731
    base = pd.DataFrame(righe)
    prima = impronta(base)
    cambia = lambda **k: base.assign(**k)                                # noqa: E731
    assert impronta(base.iloc[::-1]) == prima                             # l'ordine delle righe non conta
    assert impronta(cambia(nome="Altro", squadra="b", data="2026-09-02 20:45", t=99)) == prima
    assert impronta(base.astype({"gol": float, "assist": float})) == prima      # 0 o 0.0: gli stessi voti
    altra_giornata = base.copy()
    altra_giornata.loc[altra_giornata["giornata"] == 2, "voto_red"] = 4.0
    assert impronta(altra_giornata) == prima                              # conta solo la giornata della voce
    for colonna, valore in (("voto_red", 6.5), ("fv_red", 9.0), ("gol", 1), ("assist", 1)):
        corretta = base.copy()
        corretta.loc[(corretta["giornata"] == 1) & (corretta["calciatore_id"] == 2), colonna] = valore
        assert impronta(corretta) != prima, colonna
    senza_voto = base.copy()
    senza_voto.loc[(senza_voto["giornata"] == 1) & (senza_voto["calciatore_id"] == 3), "voto_red"] = None
    assert impronta(senza_voto) != prima
    assert impronta(base[base["calciatore_id"] != 3]) != prima            # una riga in più o in meno
    assert json.loads(json.dumps(prima)) == prima and len(prima) == 12
