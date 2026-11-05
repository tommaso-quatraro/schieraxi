"""#333: «Da fare» quando hai salvato la consigliata. Nessun cambio proposto se la consigliata è la stessa; se intanto è cambiata, UNA
voce sola che porta alla Formazione e dice cosa è cambiato; la scelta salvata non si tocca; con una formazione fatta a mano tutto come
prima. Dati finti (il `mondo` di test_da_fare.py), file in una cartella temporanea."""
import json
import logging
from datetime import datetime

from fastapi.testclient import TestClient

from fanta import da_fare, diario, frasi, scelte, server
from test_da_fare import RUOLI, STAGIONE, mondo, vai  # noqa: F401  (mondo = fixture)
from test_frasi import CON_NODE, _in_node

TUTTI = list(range(1, 12))


def _salva_la_consigliata(m, titolari=TUTTI):
    """Come «Salva questa» in Formazione: gli 11 della consigliata di quel momento."""
    scelte.salva(STAGIONE, 9, titolari, "3-5-2", m.ctx.scelte, era_consigliata=True)


def _cambia(m, *cambi):
    """La consigliata di adesso toglie `esce` (va in panchina) e schiera `entra`."""
    for esce, entra in cambi:
        m.sistema.titolari = [entra if i == esce else i for i in m.sistema.titolari]
        m.sistema.panchina = [esce if i == entra else i for i in m.sistema.panchina]


def _della_formazione(voci):
    """Le voci che parlano dei titolari: i dubbi e la consigliata cambiata."""
    return [v for v in voci if v["tipo"] == "dubbio" or v["id"].startswith("consigliata:")]


# ---------------------------------------------------------------- (1) salvata la consigliata, ed è ancora quella
def test_1_consigliata_salvata_e_uguale_nessun_cambio(mondo):
    """Il 5 è in dubbio e il 6 infortunato, ma la consigliata li tiene: nessun «Meglio…», nessun «Sostituisci», nessuna voce nuova."""
    _salva_la_consigliata(mondo)
    voci = vai(mondo)
    assert not [v for v in voci if "alternativa" in v or v["azione"] == "Sostituisci"]
    assert not [v for v in voci if v["id"].startswith("consigliata:")]
    assert {v["id"] for v in voci if v["tipo"] == "dubbio"} == {"dubbio:5", "dubbio:6"}     # restano le voci che non chiedono cambi


def test_1_senza_consigliata_calcolabile_nessun_cambio(mondo, monkeypatch):
    """Se la consigliata di adesso non si riesce a calcolare, una consigliata salvata non riceve cambi inventati."""
    _salva_la_consigliata(mondo)

    def non_si_forma(*a, **k):
        raise ValueError("in qualche ruolo nessuno gioca")
    monkeypatch.setattr(da_fare.consigli, "formazione", non_si_forma)
    voci = vai(mondo)
    assert not [v for v in voci if "alternativa" in v or v["azione"] == "Sostituisci" or v["id"].startswith("consigliata:")]


# ---------------------------------------------------------------- (2) salvata la consigliata, ma ora è un'altra
def test_2_consigliata_cambiata_una_voce_sola(mondo):
    _salva_la_consigliata(mondo)
    _cambia(mondo, (7, 14))                                                  # g7 sta bene: la consigliata ha solo cambiato idea
    voci = _della_formazione(vai(mondo))
    assert len(voci) == 1                                                    # niente dubbi sui titolari salvati: una voce sola
    v = voci[0]
    assert v["id"] == "consigliata:9" and v["tipo"] == "formazione" and v["priorita"] == 2
    assert v["testo"] == "La consigliata è cambiata da quando l'hai salvata: rivedila. Ora schiera g14 al posto di g7."
    assert v["frase"] == {"chiave": "dafare.consigliata_cambiata", "param": {"entrano": "g14", "escono": "g7"}}
    assert v["azione"] == "Apri la formazione"
    assert v["destinazione"] == {"scheda": "formazione", "sezione": None, "link": "schieraxi://formazione"}
    assert v["entrano"] == [{"id": 14, "nome": "g14"}] and v["escono"] == [{"id": 7, "nome": "g7"}]
    assert frasi.da_json(v["frase"]) == v["testo"] and frasi.da_json(v["azione_frase"]) == v["azione"]


def test_2_titolare_salvato_infortunato_priorita_alta_e_il_perche(mondo):
    """La consigliata toglie Bianchi perché è infortunato: priorità alta («Urgente», come prima il suo dubbio) e il perché in breve."""
    _salva_la_consigliata(mondo)
    _cambia(mondo, (6, 14))
    voci = _della_formazione(vai(mondo))
    assert len(voci) == 1 and voci[0]["priorita"] == 1
    v = voci[0]
    assert v["testo"] == ("Bianchi è infortunato e la consigliata è cambiata da quando l'hai salvata: rivedila. "
                          "Ora schiera g14 al posto di Bianchi.")
    assert v["frase"] == {"chiave": "dafare.consigliata_cambiata_fuori", "param": {
        "fuori": {"chiave": "dafare.fuori_infortunato", "param": {"nome": "Bianchi"}}, "entrano": "g14", "escono": "Bianchi"}}
    assert frasi.da_json(v["frase"]) == v["testo"]


def test_2_infortunato_e_squalificato_insieme(mondo, monkeypatch):
    schede = {i: da_fare.consigli.scheda_previsione(i, None) for i in range(1, 15)}
    schede[7] = schede[7] | {"stato": "squalificato", "p_voto": 0.0}
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    _salva_la_consigliata(mondo)
    _cambia(mondo, (6, 14), (7, 12))
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    assert v["priorita"] == 1
    assert v["testo"] == ("Bianchi è infortunato, g7 è squalificato e la consigliata è cambiata da quando l'hai salvata: rivedila. "
                          "Ora schiera g14 e Riserva al posto di Bianchi e g7.")
    monkeypatch.setattr(da_fare, "MAX_NOMI_CAMBIATI", 1)
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    assert v["testo"] == ("Bianchi è infortunato, g7 è squalificato e la consigliata è cambiata da quando l'hai salvata: rivedila. "
                          "Cambiano 2 titolari.")
    assert v["frase"]["chiave"] == "dafare.consigliata_cambiata_fuori_molti" and frasi.da_json(v["frase"]) == v["testo"]


def test_2_piu_titolari_cambiati_nomi_fino_a_tre_poi_il_numero(mondo, monkeypatch):
    _salva_la_consigliata(mondo)
    _cambia(mondo, (7, 14), (8, 12))
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    assert v["testo"] == "La consigliata è cambiata da quando l'hai salvata: rivedila. Ora schiera g14 e Riserva al posto di g7 e g8."
    assert [x["id"] for x in v["entrano"]] == [14, 12] and [x["id"] for x in v["escono"]] == [7, 8]
    assert v["priorita"] == 2 and frasi.da_json(v["frase"]) == v["testo"]
    _cambia(mondo, (9, 13))                                                  # tre titolari diversi: ancora i nomi
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    assert v["testo"].endswith("Ora schiera g14, Riserva e Fuori al posto di g7, g8 e g9.")
    assert da_fare.MAX_NOMI_CAMBIATI == 3
    # oltre il tetto solo quanti sono (i nomi restano nei campi `entrano` ed `escono`); la rosa finta ha solo 3 riserve
    monkeypatch.setattr(da_fare, "MAX_NOMI_CAMBIATI", 2)
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    assert v["testo"] == "La consigliata è cambiata da quando l'hai salvata: rivedila. Cambiano 3 titolari."
    assert v["frase"] == {"chiave": "dafare.consigliata_cambiata_molti", "param": {"n": 3}}
    assert len(v["entrano"]) == len(v["escono"]) == 3 and frasi.da_json(v["frase"]) == v["testo"]


@CON_NODE
def test_2_la_web_la_traduce_con_i_nomi_dentro(mondo):
    _salva_la_consigliata(mondo)
    _cambia(mondo, (6, 14), (5, 12))
    v = next(x for x in vai(mondo) if x["id"] == "consigliata:9")
    molti = frasi.F("dafare.consigliata_cambiata_molti", n=5)
    assert _in_node("en", [[v["frase"], v["testo"]], [molti.json(), str(molti)]]) == [
        "Bianchi is injured and the recommended lineup has changed since you saved it: review it. "
        "It now starts Riserva and g14 instead of Rossi and Bianchi.",
        "The recommended lineup has changed since you saved it: review it. 5 starters are different."]
    assert _in_node("it", [[v["frase"], v["testo"]]]) == [v["testo"]]


def test_2_anche_ho_schierato_la_consigliata_vale(mondo):
    """Il tipo «consigliata» («ho schierato la consigliata») dice la stessa cosa del segno messo da «Salva questa»."""
    scelte.salva(STAGIONE, 9, TUTTI, "3-5-2", mondo.ctx.scelte, tipo="consigliata")
    _cambia(mondo, (6, 14))
    assert [v["id"] for v in _della_formazione(vai(mondo))] == ["consigliata:9"]


# ---------------------------------------------------------------- (3) la scelta salvata non si tocca
def test_3_la_scelta_salvata_resta_com_era(mondo):
    _salva_la_consigliata(mondo)
    prima = mondo.ctx.scelte.read_text(encoding="utf-8")
    _cambia(mondo, (6, 14), (5, 12))
    vai(mondo)
    assert mondo.ctx.scelte.read_text(encoding="utf-8") == prima
    assert scelte.leggi(STAGIONE, 9, mondo.ctx.scelte)["titolari"] == TUTTI


# ---------------------------------------------------------------- (4) formazione fatta a mano: come prima
def test_4_formazione_a_mano_i_cambi_restano(mondo):
    scelte.salva(STAGIONE, 9, TUTTI, "3-5-2", mondo.ctx.scelte)              # «manuale», senza il segno della consigliata
    _cambia(mondo, (6, 14), (5, 12))
    voci = vai(mondo)
    assert not [v for v in voci if v["id"].startswith("consigliata:")]
    d = {v["id"]: v for v in voci if v["tipo"] == "dubbio"}
    assert d["dubbio:6"]["alternativa"]["id"] == 14 and d["dubbio:5"]["alternativa"]["id"] == 12
    assert all(v["azione"] == "Sostituisci" for v in d.values())


def test_4_una_consigliata_salvata_che_non_vale_piu_conta_come_nessuna(mondo):
    """Un giocatore della scelta non c'è più nella rosa: la scelta non vale (regola unica) e si guarda la consigliata, come prima."""
    _salva_la_consigliata(mondo, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 99])
    _cambia(mondo, (6, 14))
    assert not [v for v in vai(mondo) if v["id"].startswith("consigliata:")]


# ---------------------------------------------------------------- il segno si mette salvando
def test_era_consigliata_confronta_i_titolari_senza_ordine(mondo, monkeypatch):
    chieste = []
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda db, r, ro, giornata=None: chieste.append(giornata) or {
        "giornata": 9, "titolari": [{"id": i} for i in mondo.sistema.titolari]})
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, list(reversed(TUTTI)), 9, mondo.ctx.diario) is True
    assert chieste == [9]                                                    # la consigliata della giornata della scelta
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14], 9, mondo.ctx.diario) is False


def _mostrata(titolari, giornata=9):
    """La consigliata come la manda GET /api/formazione (quella che l'app fa vedere)."""
    return {"giornata": giornata, "modulo": "3-5-2", "punteggio_atteso": 70.0, "schede": {},
            "titolari": [{"id": i, "nome": f"g{i}", "ruolo": RUOLI[i]} for i in titolari]}


def test_era_consigliata_anche_se_la_consigliata_cambia_mentre_la_guardi(mondo, monkeypatch):
    """Revisione #333: apri la Formazione con la consigliata A, i dati si aggiornano e la consigliata diventa B, poi tocchi «Salva
    questa» sugli 11 di A. Valgono come consigliata: sono quelli dell'istantanea, la consigliata che l'app ti ha mostrato."""
    diario.salva_istantanea(_mostrata(TUTTI), STAGIONE, mondo.ctx.diario)            # quello che fa GET /api/formazione
    adesso = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14]
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda db, r, ro, giornata=None: {"giornata": 9, "titolari": [{"id": i} for i in adesso]})
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, TUTTI, 9, mondo.ctx.diario) is True
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, adesso, 9, mondo.ctx.diario) is True     # anche quella di adesso
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13], 9, mondo.ctx.diario) is False
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, TUTTI, 10, mondo.ctx.diario) is False    # istantanea di un'altra giornata


def test_era_consigliata_nel_dubbio_e_falso_e_lo_scrive_nel_log(mondo, monkeypatch, caplog):
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda *a, **k: (_ for _ in ()).throw(ValueError("niente")))
    with caplog.at_level(logging.WARNING, logger="fanta.da_fare"):
        assert da_fare.era_consigliata(mondo.db, None, mondo.rose, TUTTI, 9, mondo.ctx.diario) is False
    assert "ValueError" in caplog.text and "niente" not in caplog.text                 # il tipo, non il testo dell'errore
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda *a, **k: {"giornata": 10, "titolari": [{"id": i} for i in TUTTI]})
    assert da_fare.era_consigliata(mondo.db, None, mondo.rose, TUTTI, 9, mondo.ctx.diario) is False     # consigliata di un'altra giornata


def test_scelta_senza_segno_resta_come_prima_nel_file(tmp_path):
    """Una scelta a mano si scrive come sempre (nessun campo nuovo): i file e i client di prima non vedono differenze."""
    f = tmp_path / "scelte.json"
    scelte.salva(STAGIONE, 9, TUTTI, "3-5-2", f)
    assert "era_consigliata" not in json.loads(f.read_text(encoding="utf-8"))[f"{STAGIONE}/9"]
    scelte.salva(STAGIONE, 9, TUTTI, "3-5-2", f, era_consigliata=True)
    v = scelte.leggi(STAGIONE, 9, f)
    assert v["era_consigliata"] is True and v["tipo"] == "manuale"           # il tipo non cambia: il Diario resta com'è


def test_salva_questa_mette_il_segno_solo_alla_consigliata(dati_isolati, monkeypatch):
    """POST /api/formazione/valuta con salva=true: il server scrive `era_consigliata` se gli 11 sono quelli della consigliata."""
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: STAGIONE)
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "3-5-2", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": 0.0})
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: {"giornata": 9, "titolari": [{"id": i} for i in TUTTI]})
    monkeypatch.setattr(server, "_rose", lambda *a: object())
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a, **k: False)
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.post("/api/formazione/valuta", json={"titolari": list(reversed(TUTTI)), "giornata": 9, "salva": True}).status_code == 200
    s = c.get("/api/scelta?giornata=9").json()
    assert s["era_consigliata"] is True and s["tipo"] == "manuale"
    a_mano = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14]
    assert c.post("/api/formazione/valuta", json={"titolari": a_mano, "giornata": 9, "salva": True}).status_code == 200
    s = c.get("/api/scelta?giornata=9").json()
    assert s["titolari"] == a_mano and "era_consigliata" not in s


def test_salva_questa_dopo_un_aggiornamento_resta_la_consigliata(dati_isolati, monkeypatch):
    """Revisione #333, dalla rotta: GET /api/formazione mostra A; la consigliata diventa B; «Salva questa» sugli 11 di A → la scelta
    ha `era_consigliata`, quindi Da fare non torna a proporre «Meglio Y · Sostituisci»."""
    adesso = {"f": _mostrata(TUTTI)}
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: STAGIONE)
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: adesso["f"])
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "3-5-2", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": 0.0})
    monkeypatch.setattr(server, "_rose", lambda *a: object())
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a, **k: False)
    monkeypatch.setattr(server.fasi, "formazione_a_giornata_iniziata", lambda f, *a, **k: f)
    monkeypatch.setattr(server.avvisi_pronta, "prima_partita", lambda *a, **k: datetime(2100, 1, 1, 15, 0))     # formazione aperta
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/formazione").status_code == 200                    # l'app mostra A
    adesso["f"] = _mostrata([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14])           # i dati si aggiornano: la consigliata è B
    assert c.post("/api/formazione/valuta", json={"titolari": TUTTI, "giornata": 9, "salva": True}).status_code == 200
    s = c.get("/api/scelta?giornata=9").json()
    assert s["titolari"] == TUTTI and s["era_consigliata"] is True
