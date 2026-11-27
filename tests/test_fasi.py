"""Fasi della giornata in Oggi (fanta/fasi.py): prima della scadenza, giornata in corso (anche la domenica sera con le partite del
lunedì), giornata finita. Orari simulati, archivio finto in una cartella temporanea, nessuna rete."""
import json
from datetime import datetime
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import archivio, consigli, da_fare, fasi, gestione, lega
from fanta.punteggio import fantavoto
from fanta.regole import Regole, serie_a_a_lega

ST = "2026-27"
REGOLE = Regole()
# id: (nome, ruolo, squadra, punti attesi, stato nelle probabili)
ROSA = {1: ("Portiere", "P", "inter", 5.0, "titolare"), 2: ("Dif2", "D", "inter", 6.0, "titolare"),
        3: ("Dif3", "D", "milan", 6.0, "titolare"), 4: ("Dif4", "D", "roma", 6.0, "titolare"),
        5: ("Dif5", "D", "napoli", 6.0, "titolare"), 6: ("Cen6", "C", "milan", 6.5, "titolare"),
        7: ("Cen7", "C", "roma", 6.5, "titolare"), 8: ("Cen8", "C", "napoli", 6.5, "titolare"),
        9: ("Cen9", "C", "juve", 6.5, "infortunato"), 10: ("Att10", "A", "inter", 7.0, "titolare"),
        11: ("Att11", "A", "lazio", 7.0, "titolare"),
        12: ("Dif12", "D", "inter", 5.5, "titolare"), 13: ("Cen13", "C", "juve", 5.5, "titolare"),
        14: ("Port14", "P", "milan", 4.0, "panchina")}
TITOLARI, PANCHINA = list(range(1, 12)), [12, 13, 14]
# giornata 10: sabato, domenica sera, lunedì sera; giornata 11 il sabato dopo
PARTITE = [(10, "2026-11-07 15:00", "inter", "milan"), (10, "2026-11-08 20:45", "roma", "lazio"),
           (10, "2026-11-09 20:45", "napoli", "juve"), (11, "2026-11-14 15:00", "inter", "roma"),
           (11, "2026-11-15 20:45", "milan", "napoli")]
# voti della partita del sabato: Dif3 senza voto (non è entrato); Att10 un gol
VOTI = {1: (6.0, 0), 2: (6.5, 0), 3: (None, 0), 6: (7.0, 0), 10: (6.5, 1), 12: (6.0, 0), 14: (None, 0)}
# voti delle partite di domenica (roma-lazio) e lunedì (napoli-juve): Cen9, infortunato, senza voto; Att11 un gol
VOTI_DOMENICA = {4: (6.0, 0), 7: (6.5, 0), 11: (7.0, 1)}
VOTI_LUNEDI = {5: (5.5, 0), 8: (6.0, 0), 9: (None, 0), 13: (6.0, 0)}


def _fv(i):
    v, gol = (VOTI | VOTI_DOMENICA | VOTI_LUNEDI)[i]
    return fantavoto({"voto_red": v, "gol": gol}, ROSA[i][1], REGOLE)


def _voti(a, voti: dict) -> None:
    archivio.inserisci(a.db, "voti", [{"stagione": ST, "giornata": 10, "calciatore_id": i, "nome": ROSA[i][0], "squadra": ROSA[i][2],
                                       "ruolo": ROSA[i][1], "voto_red": v, "gol": g} for i, (v, g) in voti.items()])


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    db = archivio.apri(tmp_path / "fanta.sqlite")
    stato = {"giornata": 10, "giocate": set()}

    def carica():
        db.execute("DELETE FROM partite")
        archivio.inserisci(db, "partite", [{"id": n, "stagione": ST, "giornata": g, "data": d, "casa": c, "trasferta": t,
                                            "gol_casa": None, "gol_trasferta": None, "giocata": int(n in stato["giocate"]),
                                            "understat_id": None} for n, (g, d, c, t) in enumerate(PARTITE)])
    stato["carica"] = carica
    a = NS(db=db, stato=stato, tmp=tmp_path)
    _voti(a, VOTI)
    prev = pd.DataFrame([{"id": i, "nome": n, "ruolo": r, "squadra": s, "atteso": a, "stato": st, "p_voto": 0.9, "mu": a + 0.5,
                          "mu_voto": 6.0, "dubbio": False, "diffidato": False} for i, (n, r, s, a, st) in ROSA.items()]).set_index("id")
    scheda = lambda i: {"id": i, "nome": ROSA[i][0], "ruolo": ROSA[i][1], "squadra": ROSA[i][2], "punti_attesi": ROSA[i][3]}
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, stato["giornata"], True))
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {"p_voto": 0.9, "nota": None})
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "titolari": [scheda(i) for i in TITOLARI], "panchina": [scheda(i) for i in PANCHINA], "modulo": "4-4-2",
        "punteggio_atteso": 70.0, "squadra": "Mia"})
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, r, s, 1) for i, (n, r, s, _, _) in ROSA.items()])], "Mia")
    carica()
    a.rose = rose
    return a


def _oggi(a, adesso, **k):
    return gestione.oggi(a.db, REGOLE, a.rose, adesso=adesso, file_scelte=a.tmp / "scelte.json", file_diario=a.tmp / "diario.json", **k)


# ---------------------------------------------------------------- funzioni pure
def test_calcola_fase():
    fine = datetime(2026, 11, 9, 22, 35)
    assert fasi.calcola_fase(True, -5.0, None, datetime(2026, 11, 8, 21, 0)) == "in_corso"
    assert fasi.calcola_fase(False, 100.0, fine, datetime(2026, 11, 10, 10, 0)) == "finita"
    assert fasi.calcola_fase(False, 100.0, fine, datetime(2026, 11, 12, 10, 0)) == "prima"      # passati 2 giorni
    assert fasi.calcola_fase(False, 20.0, fine, datetime(2026, 11, 10, 10, 0)) == "prima"       # turno infrasettimanale vicino
    assert fasi.calcola_fase(False, 100.0, None, datetime(2026, 11, 10, 10, 0)) == "prima"      # nessuna giornata finita prima


def test_stato_partita_calendario_diretta_orario():
    p = {"data": "2026-11-08 20:45", "casa": "roma", "trasferta": "lazio", "giocata": False}
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 18, 0)) == "da_giocare"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 30)) == "in_corso"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 23, 30)) == "finita"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 30), {("roma", "lazio"): {"stato": "finita"}}) == "finita"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 30), {("roma", "lazio"): {"stato": "rinviata"}}) == "rinviata"
    assert fasi.stato_partita(p | {"giocata": True}, datetime(2026, 11, 8, 18, 0)) == "finita"


def test_partita_ritardata_resta_da_giocare_come_dice_la_diretta():
    """#901: la fonte conferma «da giocare» DOPO l'orario previsto e da poco (`visto`, al più 15 minuti fa): calcio d'inizio in
    ritardo, Oggi dice lo stesso invece di dedurre «in corso» e poi «finita» dall'orario. Il calendario «giocata» vince sempre."""
    p = {"data": "2026-11-08 20:45", "casa": "roma", "trasferta": "lazio", "giocata": False}
    def diretta(visto):
        return {("roma", "lazio"): {"stato": "da_giocare", "visto": visto}}
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 30), diretta("2026-11-08T21:29:10")) == "da_giocare"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 23, 30), diretta("2026-11-08T23:25:00")) == "da_giocare"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 30), diretta("2026-11-08T21:14:00")) == "in_corso"   # 16 minuti fa
    assert fasi.stato_partita(p | {"giocata": True}, datetime(2026, 11, 8, 21, 30), diretta("2026-11-08T21:29:10")) == "finita"


def test_da_giocare_letto_prima_del_calcio_d_inizio_non_ferma_l_orario():
    """#901, revisione: la diretta legge già 10 minuti prima dell'inizio («da giocare», 20:38), poi la fonte smette di rispondere.
    Quel valore vecchio non è la conferma di un ritardo: dalle 20:45 vale l'orario («in corso», poi «finita»). Lo stesso senza `visto`
    (il ripiego che scrive «da giocare» non lo lascia: non sa distinguere una partita da giocare da una in corso)."""
    p = {"data": "2026-11-08 20:45", "casa": "roma", "trasferta": "lazio", "giocata": False}
    vecchia = {("roma", "lazio"): {"stato": "da_giocare", "visto": "2026-11-08T20:38:00"}}
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 20, 40), vecchia) == "da_giocare"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 20, 50), vecchia) == "in_corso"             # prima: «da_giocare»
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 0), vecchia) == "in_corso"
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 23, 30), vecchia) == "finita"
    senza = {("roma", "lazio"): {"stato": "da_giocare", "visto": None}}
    assert fasi.stato_partita(p, datetime(2026, 11, 8, 21, 0), senza) == "in_corso"


def test_partita_spostata_dal_calendario_e_rinviata():
    """Collaudo 2/11/2026: un rinvio già scritto nel calendario (recupero settimane dopo, o senza data) ora ha l'etichetta."""
    turno = [{"data": f"2026-11-0{g} 15:00", "casa": f"c{g}", "trasferta": f"t{g}", "giocata": False} for g in (7, 8, 8, 9)]
    recupero = {"data": "2026-12-03 18:30", "casa": "roma", "trasferta": "lazio", "giocata": False}
    vecchia = {"data": "2026-10-01 18:30", "casa": "inter", "trasferta": "milan", "giocata": False}
    senza_data = {"data": None, "casa": "juve", "trasferta": "toro", "giocata": False}
    inizio = fasi.inizio_turno(turno + [recupero, vecchia, senza_data])
    assert inizio == datetime(2026, 11, 7, 15, 0)                       # il recupero e la data vecchia non spostano il turno
    adesso = datetime(2026, 11, 6, 12, 0)
    for p in (recupero, vecchia, senza_data):
        assert fasi.stato_partita(p, adesso, turno=inizio) == "rinviata"
    assert fasi.stato_partita(turno[3], adesso, turno=inizio) == "da_giocare"
    assert fasi.stato_partita(recupero | {"giocata": True}, adesso, turno=inizio) == "finita"      # giocata vince sempre
    assert fasi.inizio_turno([{"data": None}]) is None                  # calendario senza date: nessuna partita «rinviata»
    assert fasi.stato_partita(senza_data, adesso, turno=None) == "da_giocare"


# ---------------------------------------------------------------- (a) prima della scadenza
def test_prima_della_scadenza_come_sempre(ambiente):
    o = _oggi(ambiente, datetime(2026, 11, 6, 12, 0))
    assert o["fase"] == "prima" and o["in_corso"] is None and o["riepilogo"] is None and o["prossima"] is None
    assert [p["stato"] for p in o["partite"]] == ["da_giocare"] * 3
    assert any(a["in_formazione"] for a in o["avvisi"])          # «Da controllare» resta (Cen9 infortunato in formazione)
    cen9 = next(a for a in o["avvisi"] if a["id"] == 9)
    assert cen9["etichetta"] == {"codice": "infortunato", "testo": "Infortunato", "tono": "negativo"}
    assert all(a["etichetta"]["codice"] in ("infortunato", "squalificato", "in_dubbio", "diffidato") for a in o["avvisi"])


# ---------------------------------------------------------------- (b) giornata in corso: domenica sera, lunedì da giocare
def test_domenica_sera_con_partite_lunedi(ambiente):
    o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30))
    assert o["fase"] == "in_corso" and o["iniziata"] is True
    assert [p["stato"] for p in o["partite"]] == ["finita", "in_corso", "da_giocare"]
    c = o["in_corso"]
    assert c["giornata"] == 10 and c["formazione_di"] == "consigliata" and c["partite"]["da_giocare"] == 1
    g = {x["id"]: x for x in c["giocatori"]}
    assert g[1]["stato"] == "fatto" and g[3]["stato"] == "senza_voto" and g[4]["stato"] == "in_corso"
    assert g[5]["stato"] == "da_giocare" and g[5]["data"] == "2026-11-09 20:45"
    # l'etichetta pronta (fanta/etichette.py): stesse parole di Formazione e scheda; Cen9 infortunato resta «Infortunato»
    assert [g[i]["etichetta"]["testo"] for i in (1, 3, 4, 5, 9)] == ["Ha giocato", "Senza voto", "Partita in corso", "Da giocare",
                                                                     "Infortunato"]
    # Dif3 non è entrato: al suo posto Dif12 (primo in panchina, ha il voto) = cambio già scattato;
    # Cen9 è infortunato e gioca lunedì: cambio probabile con Cen13 (che deve ancora giocare)
    cambi = {s["esce"]["id"]: s for s in c["sostituzioni"]}
    assert cambi[3]["entra"]["id"] == 12 and cambi[3]["certa"] is True and cambi[3]["motivo"] == "senza_voto"
    assert cambi[9]["entra"]["id"] == 13 and cambi[9]["certa"] is False and cambi[9]["motivo"] == "fuori"
    assert g[12]["a_punteggio"] and not g[3]["a_punteggio"] and not g[14]["a_punteggio"]
    assert c["punti_fatti"] == pytest.approx(round(sum(_fv(i) for i in (1, 2, 6, 10, 12)), 1))
    # restanti: stesse simulazioni della formazione con i fatti fissati (Cen9 infortunato = fuori). Prima era la somma p×mu dei
    # titolari, che non contava le riserve al posto di chi non gioca: ora sta tra quella somma e «giocano tutti»
    solo_titolari = sum(0.9 * (ROSA[i][3] + 0.5) for i in (4, 5, 7, 8, 11, 13))
    giocano_tutti = sum(ROSA[i][3] + 0.5 for i in (4, 5, 7, 8, 11, 13))
    assert solo_titolari < c["punti_attesi_restanti"] <= giocano_tutti and c["ancora_da_giocare"] == 6
    assert c["punti_previsti"] == pytest.approx(c["punti_fatti"] + c["punti_attesi_restanti"], abs=0.11)


def test_stima_di_fine_giornata_a_inizio_giornata_uguale_agli_attesi_prima():
    """Collaudo 2/11/2026: a giornata iniziata e niente ancora giocato, «A fine giornata» diceva ≈ 61,5 contro 72,4 attesi prima."""
    rosa = [fasi.fz.Giocatore(i, f"g{i}", r, 0.8, 6.5, 6.0) for i, r in enumerate("PDDDDCCCCAA" + "PDCA", start=1)]
    tit, panc = rosa[:11], rosa[11:]
    prima = float(fasi.fz.Valutatore(rosa, REGOLE)._punti(tit, panc).mean())
    stato = {g.id: "da_giocare" for g in rosa}
    previsione = {g.id: (g.p, g.mu, g.mu_voto) for g in rosa}
    adesso = fasi._previsti_condizionati(tit, panc, stato, {}, {}, previsione, REGOLE)
    assert adesso == pytest.approx(prima, abs=0.01)
    assert adesso > sum(g.p * g.mu for g in tit) + 5                    # le riserve contano (la somma vecchia era molto più bassa)
    # tutto giocato: la stima coincide con i fatti (fantavoto veri, nessun caso)
    stato = {g.id: "fatto" for g in rosa}
    fv = {g.id: 7.0 for g in rosa}
    voti = {g.id: 6.5 for g in rosa}
    assert fasi._previsti_condizionati(tit, panc, stato, fv, voti, previsione, REGOLE) == pytest.approx(
        77.0 + (fasi.modificatore_difesa(6.5, [6.5] * 4, REGOLE) if REGOLE.modificatore_difesa.attivo else 0.0))


def test_in_corso_con_diretta_e_tua_scelta(ambiente, monkeypatch):
    from fanta import scelte
    tit = [1, 2, 3, 4, 5, 6, 7, 8, 12, 10, 11]                   # l'utente ha messo Dif12 al posto di Cen9: 5-3-2
    scelte.salva(ST, 10, tit, "5-3-2", ambiente.tmp / "scelte.json", panchina=[13, 9, 14])
    monkeypatch.setattr(consigli, "valuta", lambda *a, **k: {"modulo": "5-3-2", "punteggio_atteso": 69.0})
    o = _oggi(ambiente, datetime(2026, 11, 8, 22, 40), live_partite={("roma", "lazio"): {"stato": "finita"}})
    c = o["in_corso"]
    assert c["formazione_di"] == "tua" and o["partite"][1]["stato"] == "finita"
    g = {x["id"]: x for x in c["giocatori"]}
    assert g[4]["stato"] == "attesa_voti"                         # partita finita, voti non ancora usciti
    # «devono ancora giocare»: solo chi gioca lunedì (Dif5, Cen8, Cen13), non chi ha già giocato e aspetta il voto (prima: 6)
    assert c["ancora_da_giocare"] == 3
    cambi = {s["esce"]["id"]: s for s in c["sostituzioni"]}
    assert set(cambi) == {3} and cambi[3]["entra"]["id"] == 13 and cambi[3]["certa"] is False    # Cen13 gioca lunedì


def test_in_corso_niente_consigli_su_chi_schierare(ambiente, monkeypatch):
    voce = lambda tipo: [{"id": tipo, "tipo": tipo, "testo": "x", "priorita": 1, "azione": "a", "destinazione": {}}]
    monkeypatch.setattr(da_fare, "_dubbi", lambda *a, **k: voce("dubbio"))
    monkeypatch.setattr(da_fare, "_copertura", lambda *a, **k: voce("copertura"))
    monkeypatch.setattr(da_fare, "_svincolato", lambda *a, **k: None)
    monkeypatch.setattr(da_fare, "_scambio", lambda *a, **k: None)
    monkeypatch.setattr(da_fare, "_diario", lambda *a, **k: [])
    ctx = NS(scelte=ambiente.tmp / "s.json", diario=ambiente.tmp / "d.json", utente_id=1, rose=None)
    tipi = lambda o: {v["tipo"] for v in da_fare.costruisci(ambiente.db, REGOLE, ambiente.rose, o, ctx, adesso=datetime(2026, 11, 8))}
    assert tipi({"giornata": 10, "iniziata": True, "fase": "in_corso"}) == set()
    assert tipi({"giornata": 11, "iniziata": False, "fase": "finita", "ore_mancanti": 100}) == {"copertura"}
    assert tipi({"giornata": 11, "iniziata": False, "fase": "prima", "ore_mancanti": 30}) == {"dubbio", "copertura"}


# ---------------------------------------------------------------- (c) giornata finita
def _giornata_finita(a, voti=(VOTI_DOMENICA, VOTI_LUNEDI)):
    """Le tre partite della giornata 10 giocate e, di base, con i voti di tutte (quelli del sabato ci sono già)."""
    a.stato["giornata"] = 11
    a.stato["giocate"] = {0, 1, 2}
    a.stato["carica"]()
    for v in voti:
        _voti(a, v)


def test_giornata_finita_riepilogo_dal_diario_e_prossima(ambiente):
    _giornata_finita(ambiente)
    (ambiente.tmp / "diario.json").write_text(json.dumps({"giornate": {f"{ST}/10": {
        "consigliata": {"reale": 70.5, "atteso": 68.0, "origine": "mostrata"}, "schierata": {"reale": 66.0, "atteso": 67.0, "tipo": "manuale",
                                                                      "intervallo": {"basso": 60, "alto": 75}}}}}), encoding="utf-8")
    o = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))             # martedì mattina
    assert o["fase"] == "finita" and o["giornata"] == 11 and o["in_corso"] is None
    r = o["riepilogo"]
    assert (r["giornata"], r["formazione_di"], r["nel_diario"], r["punti_fatti"], r["punti_attesi"]) == (10, "tua", True, 66.0, 67.0)
    assert r["consigliata"] == {"punti_fatti": 70.5, "punti_attesi": 68.0}
    p = o["prossima"]
    assert p["giornata"] == 11 and p["scadenza"] == "2026-11-14 15:00" and p["prepara_da"] == "2026-11-10 10:00"
    # giovedì la giornata 10 è finita da più di 2 giorni: si torna a preparare la prossima
    assert _oggi(ambiente, datetime(2026, 11, 12, 10, 0))["fase"] == "prima"


def test_giornata_finita_senza_diario_usa_i_voti(ambiente, monkeypatch):
    _giornata_finita(ambiente)
    prev, _, _ = consigli.previsioni(None, REGOLE)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 11, False))     # probabili non ancora uscite
    from fanta import scelte
    scelte.salva(ST, 10, TITOLARI, "4-4-2", ambiente.tmp / "scelte.json", panchina=PANCHINA)
    o = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))
    r = o["riepilogo"]
    assert r["nel_diario"] is False and r["formazione_di"] == "tua" and r["consigliata"] is None
    # tutte le partite hanno i voti: Dif12 al posto di Dif3 (senza voto), Cen13 al posto di Cen9 (infortunato, senza voto).
    # Prima il test passava con i soli voti del sabato, cioè con un totale a metà (#649)
    assert r["punti_fatti"] == pytest.approx(round(sum(_fv(i) for i in (1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13)), 1))
    assert o["prossima"]["prepara_da"] == "2026-11-11 15:00" and o["prossima"]["con_probabili"] is False


def _scheda(prev, i) -> dict:
    x = prev.loc[i]
    return {"id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "p_voto": float(x["p_voto"]), "fv_atteso": float(x["mu"])}


def _copia_alla_scadenza(a, prev, titolari, panchina) -> None:
    """Il passo del server alla scadenza (`copia_scadenza.salva`, come fa per ogni utente): l'istantanea della consigliata e i
    numeri della rosa di allora, dalle previsioni `prev` della giornata 10."""
    from fanta import copia_scadenza
    f = {"giornata": 10, "modulo": "4-4-2", "punteggio_atteso": 70.0, "titolari": [_scheda(prev, i) for i in titolari],
         "panchina": [_scheda(prev, i) for i in panchina], "schede": {str(i): _scheda(prev, i) for i in prev.index}}
    copia_scadenza.salva(f, ST, a.tmp / "scelte.json", a.tmp / "diario.json")


def test_i_numeri_della_rosa_alla_scadenza_restano_per_le_giornate_che_il_diario_rifa(ambiente):
    """La copia alla scadenza di tredici giornate di fila: restano i numeri delle ultime dodici, quante il Diario ne rifà a un cambio
    di regole (`MASSIMO_GIORNATE`): con meno, dalla quinta alla dodicesima la panchina del sistema (scelta con questi numeri)
    cambiava per un motivo che non è la regola cambiata. La 10 e la 11 comprese (le giornate si ordinano come numeri), e non
    entrano nell'istantanea che va ai client."""
    from fanta import copia_scadenza, diario
    prev, _, _ = consigli.previsioni(None, REGOLE)
    for g in range(1, 14):
        f = {"giornata": g, "modulo": "4-4-2", "punteggio_atteso": 70.0, "titolari": [_scheda(prev, i) for i in TITOLARI],
             "panchina": [_scheda(prev, i) for i in PANCHINA], "schede": {str(i): _scheda(prev, i) for i in prev.index}}
        copia_scadenza.salva(f, ST, ambiente.tmp / "scelte.json", ambiente.tmp / "diario.json")
    d = diario.carica(ambiente.tmp / "diario.json")
    assert diario.MASSIMO_GIORNATE == 12 and set(d["numeri_rosa"]) == {f"{ST}/{g}" for g in range(2, 14)}
    assert set(diario.numeri_rosa(ambiente.tmp / "diario.json", ST, 11)) == set(prev.index)
    assert all("numeri" not in str(list(ist)) for ist in d["istantanee"].values())


def test_giornata_finita_senza_diario_con_la_scelta_salvata_senza_panchina(ambiente, monkeypatch):
    """#794: web e iPhone salvano la formazione senza panchina. Senza la voce del Diario il riepilogo usava una panchina vuota e
    le riserve entrate in corso sparivano (64,0 invece di 76,0). Con gli stessi 11 della consigliata congelata alla scadenza la
    panchina è la sua: Dif12 entra al posto di Dif3 (senza voto), Cen13 al posto di Cen9 (infortunato, senza voto)."""
    prev, _, _ = consigli.previsioni(None, REGOLE)
    from fanta import scelte
    scelte.salva(ST, 10, TITOLARI, "4-4-2", ambiente.tmp / "scelte.json")          # come web e iPhone: niente panchina
    _copia_alla_scadenza(ambiente, prev, TITOLARI, PANCHINA)
    _giornata_finita(ambiente)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 11, False))
    r = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))["riepilogo"]
    assert r["nel_diario"] is False and r["formazione_di"] == "tua"
    assert r["punti_fatti"] == pytest.approx(round(sum(_fv(i) for i in (1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13)), 1))


def test_riepilogo_con_una_riserva_senza_ruolo_nella_rosa(ambiente, monkeypatch):
    """Una riserva della rosa senza ruolo (rosa scritta a mano), con il ruolo nei numeri della scadenza e con il voto: nella
    panchina del sistema ha il ruolo di allora, come in «in corso». Con il ruolo vuoto il conto si rompeva e il riepilogo spariva."""
    prev, _, _ = consigli.previsioni(None, REGOLE)
    prev = pd.concat([prev, pd.DataFrame([{"id": 15, "nome": "Dif15", "ruolo": "D", "squadra": "inter", "atteso": 4.5, "stato": "titolare",
                                           "p_voto": 0.9, "mu": 5.0, "mu_voto": 6.0, "dubbio": False, "diffidato": False}]).set_index("id")])
    ambiente.rose.squadra("Mia").giocatori.append(lega.GiocatoreRosa(15, "Dif15", None, "INT", 1))
    archivio.inserisci(ambiente.db, "voti", [{"stagione": ST, "giornata": 10, "calciatore_id": 15, "nome": "Dif15", "squadra": "inter",
                                              "ruolo": "D", "voto_red": 6.0, "gol": 0}])
    from fanta import scelte
    scelte.salva(ST, 10, TITOLARI, "4-4-2", ambiente.tmp / "scelte.json")
    consigliata = [1, 2, 3, 4, 5, 6, 7, 8, 13, 10, 11]                      # 11 diversi da quelli dell'utente
    _copia_alla_scadenza(ambiente, prev, consigliata, [12, 9, 15, 14])
    _giornata_finita(ambiente)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 11, False))
    atteso = pytest.approx(round(sum(_fv(i) for i in (1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13)), 1))
    assert _oggi(ambiente, datetime(2026, 11, 10, 10, 0))["riepilogo"]["punti_fatti"] == atteso
    r = fasi.blocco_riepilogo(ambiente.db, REGOLE, ambiente.rose, ST, 10, ambiente.tmp / "scelte.json", ambiente.tmp / "diario.json")
    assert r["punti_fatti"] == atteso


# sei giocatori in più: più non titolari dei 7 posti in panchina. Cen19 (napoli) prende voto il lunedì, gli altri (torino) non giocano
ALTRI = {15: ("Dif15", "D", "torino"), 16: ("Cen16", "C", "torino"), 17: ("Att17", "A", "torino"), 18: ("Dif18", "D", "torino"),
         19: ("Cen19", "C", "napoli"), 20: ("Att20", "A", "torino")}


def _con_altri_sei(a, dif4_poco=False):
    """Previsioni della giornata 10 e della 11 con i sei giocatori in più. Nella 11 Cen13, che ha preso voto nella 10, è
    squalificato («gioca 0%»): con quelle previsioni resterebbe fuori dalla panchina."""
    base, _, _ = consigli.previsioni(None, REGOLE)
    for i, (n, r, s) in ALTRI.items():
        a.rose.squadra("Mia").giocatori.append(lega.GiocatoreRosa(i, n, r, s, 1))
    righe = pd.DataFrame([{"id": i, "nome": n, "ruolo": r, "squadra": s, "atteso": 4.2, "stato": "titolare", "p_voto": 0.8, "mu": 5.2,
                           "mu_voto": 6.0, "dubbio": False, "diffidato": False} for i, (n, r, s) in ALTRI.items()]).set_index("id")
    prev10 = pd.concat([base, righe])
    if dif4_poco:
        prev10.loc[4, "p_voto"] = 0.3
    prev11 = prev10.copy()
    prev11.loc[13, ["p_voto", "stato"]] = [0.0, "squalificato"]
    archivio.inserisci(a.db, "voti", [{"stagione": ST, "giornata": 10, "calciatore_id": 19, "nome": "Cen19", "squadra": "napoli",
                                       "ruolo": "C", "voto_red": 6.0, "gol": 0}])
    return prev10, prev11


def _fine_giornata_e_giorno_dopo(a, monkeypatch, prev10, prev11, titolari):
    """(«in corso» lunedì alle 23:30, con le previsioni della 10; riepilogo di martedì, quando Oggi ha le previsioni della 11)."""
    from fanta import scelte
    scelte.salva(ST, 10, titolari, "4-4-2", a.tmp / "scelte.json")
    info10 = fasi._info_rosa(a.rose, prev10)
    _copia_alla_scadenza(a, prev10, TITOLARI, fasi._panchina_di(info10, prev10, TITOLARI, REGOLE))
    monkeypatch.setattr(consigli, "valuta", lambda *x, **k: {"modulo": "4-4-2", "punteggio_atteso": 69.0})
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev10, 10, True))
    a.stato["giocate"] = {0, 1}
    a.stato["carica"]()
    _voti(a, VOTI_DOMENICA)
    _voti(a, VOTI_LUNEDI)
    c = _oggi(a, datetime(2026, 11, 9, 23, 30))["in_corso"]
    _giornata_finita(a, voti=())
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev11, 11, False))
    r = _oggi(a, datetime(2026, 11, 10, 10, 0))["riepilogo"]
    return c, r


def _panchina_del_riepilogo(a, titolari) -> list[int]:
    info, numeri, ist = fasi._rosa_della_giornata(a.rose, ST, 10, a.tmp / "diario.json")
    return fasi._panchina_della_giornata(info, numeri, ist, titolari, REGOLE)


def test_riepilogo_senza_panchina_salvata_non_usa_le_previsioni_della_giornata_dopo(ambiente, monkeypatch):
    """#794, revisione: la panchina del riepilogo è quella di «in corso» per la stessa giornata, con i numeri della rosa alla
    scadenza. Con le previsioni della 11 Cen13 (squalificato per la 11) restava fuori: 70,0 invece di 76,0. Qui l'utente ha gli 11
    della consigliata congelata (dove c'è Dif4 e non Dif12): Dif12 entra per Dif3, Cen13 per Cen9."""
    prev10, prev11 = _con_altri_sei(ambiente)
    c, r = _fine_giornata_e_giorno_dopo(ambiente, monkeypatch, prev10, prev11, TITOLARI)
    attesi = round(sum(_fv(i) for i in (1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13)), 1)
    assert c["punti_fatti"] == pytest.approx(attesi)
    assert r["nel_diario"] is False and r["punti_fatti"] == pytest.approx(attesi)
    assert _panchina_del_riepilogo(ambiente, TITOLARI) == [g["id"] for g in c["giocatori"] if not g["titolare"]]


def test_riepilogo_con_11_diversi_dalla_consigliata_e_una_riserva_che_non_era_nella_consigliata(ambiente, monkeypatch):
    """Dif4, titolare della consigliata congelata, vale poco; l'utente lo lascia fuori e mette Dif12. La panchina è allora quella
    di «in corso» per i suoi 11: entra Cen19, che non era né titolare né riserva della consigliata (serve il suo numero di allora),
    e prende il posto di Cen9; Cen13 prende quello di Dif3."""
    prev10, prev11 = _con_altri_sei(ambiente, dif4_poco=True)
    mia = [1, 2, 3, 12, 5, 6, 7, 8, 9, 10, 11]
    c, r = _fine_giornata_e_giorno_dopo(ambiente, monkeypatch, prev10, prev11, mia)
    attesi = round(sum(_fv(i) for i in (1, 2, 5, 6, 7, 8, 10, 11, 12, 13)) + 6.0, 1)       # più Cen19
    assert c["punti_fatti"] == pytest.approx(attesi)
    assert r["punti_fatti"] == pytest.approx(attesi)
    panchina = _panchina_del_riepilogo(ambiente, mia)
    assert 19 in panchina and panchina == [g["id"] for g in c["giocatori"] if not g["titolare"]]


def test_giornata_finita_con_i_voti_a_meta_niente_totale(ambiente, monkeypatch):
    """#649: lunedì sera napoli-juve è segnata giocata ma i suoi voti non sono ancora usciti. Prima Oggi faceva entrare le riserve al
    posto di Dif5, Cen8 e Cen9 e dava un totale che sembrava definitivo (e senza recuperi da aspettare). Ora niente totale finché
    ogni squadra che ha giocato non ha i voti; arrivati quelli, il numero giusto."""
    _giornata_finita(ambiente, voti=(VOTI_DOMENICA,))
    prev, _, _ = consigli.previsioni(None, REGOLE)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 11, False))
    from fanta import scelte
    scelte.salva(ST, 10, TITOLARI, "4-4-2", ambiente.tmp / "scelte.json", panchina=PANCHINA)
    o = _oggi(ambiente, datetime(2026, 11, 9, 23, 0))                  # lunedì, 25 minuti dopo la fine stimata della partita
    assert o["fase"] == "finita" and o["riepilogo"] is None
    # #895: la testa diceva solo la giornata dopo; ora il server dice che la giornata è finita e i voti arrivano
    assert o["voti_in_arrivo"] == {"giornata": 10, "giornata_lega": serie_a_a_lega(10, REGOLE), "testo": "I punti arrivano quando escono i voti.",
                                   "frase": {"chiave": "riepilogo.voti_in_arrivo", "param": {}}}
    _voti(ambiente, VOTI_LUNEDI)                                        # i voti del lunedì arrivano col giro di mezzanotte
    o = _oggi(ambiente, datetime(2026, 11, 10, 0, 50))
    r = o["riepilogo"]
    assert r["punti_fatti"] == pytest.approx(round(sum(_fv(i) for i in (1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13)), 1))
    assert "voti_in_arrivo" not in o


def test_giornata_finita_senza_formazione_niente_voti_in_arrivo(ambiente):
    """Chi non ha una formazione per la giornata finita non ha punti da aspettare: niente «i punti arrivano»."""
    _giornata_finita(ambiente, voti=(VOTI_DOMENICA,))
    o = _oggi(ambiente, datetime(2026, 11, 9, 23, 0))
    assert o["riepilogo"] is None and "voti_in_arrivo" not in o


def test_oggi_non_si_rompe_se_le_fasi_falliscono(ambiente, monkeypatch):
    monkeypatch.setattr(fasi, "blocco_in_corso", lambda *a, **k: 1 / 0)
    o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30))
    assert o["fase"] == "in_corso" and o["in_corso"] is None and o["formazione"]["modulo"] == "4-4-2"


# Guasti visibili (26/11/2026): Oggi e la Formazione si aprono lo stesso, ma il guasto lascia una riga nel registro del server con il
# tipo d'errore e il punto del codice, mai il messaggio dell'errore (può contenere dati: qui un nome inventato che non deve uscire).
def _rotto(*a, **k):
    raise ValueError("Portiere della Mia")


def _righe_del_registro(caplog, logger: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == logger and r.levelname == "WARNING"]


def test_oggi_scrive_nel_registro_se_la_giornata_in_corso_non_si_calcola(ambiente, monkeypatch, caplog):
    monkeypatch.setattr(fasi, "blocco_in_corso", _rotto)
    with caplog.at_level("WARNING", logger="fanta.fasi"):
        o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30))
    assert o["in_corso"] is None
    righe = _righe_del_registro(caplog, "fanta.fasi")
    assert len(righe) == 1 and "ValueError" in righe[0] and "fasi.py:" in righe[0] and "aggiungi" in righe[0]
    assert "Portiere" not in caplog.text and "Mia" not in caplog.text


def test_formazione_a_giornata_iniziata_tiene_iniziata_e_scrive_nel_registro(ambiente, monkeypatch, caplog):
    """Prima un errore dopo la scadenza faceva tornare la formazione senza `iniziata`: i client la credevano ancora aperta."""
    monkeypatch.setattr(fasi, "schede_a_giornata_iniziata", _rotto)
    f = _formazione_con_etichette()
    with caplog.at_level("WARNING", logger="fanta.fasi"):
        r = fasi.formazione_a_giornata_iniziata(f, ambiente.db, REGOLE, ST, datetime(2026, 11, 8, 21, 30))
    assert r["iniziata"] is True and r["titolari"] == f["titolari"]
    righe = _righe_del_registro(caplog, "fanta.fasi")
    assert len(righe) == 1 and "ValueError" in righe[0] and "formazione_a_giornata_iniziata" in righe[0]
    assert "Portiere" not in caplog.text


def test_oggi_scrive_nel_registro_se_il_blocco_della_partita_rinviata_non_si_calcola(ambiente, monkeypatch, caplog):
    monkeypatch.setattr(gestione.rinvii, "blocco_oggi", _rotto)
    with caplog.at_level("WARNING", logger="fanta.gestione"):
        o = _oggi(ambiente, datetime(2026, 11, 6, 12, 0))
    assert o["rinvio"] is None
    righe = _righe_del_registro(caplog, "fanta.gestione")
    assert len(righe) == 1 and "ValueError" in righe[0] and "gestione.py:" in righe[0] and "oggi" in righe[0]
    assert "Portiere" not in caplog.text


def test_partita_rinviata_con_la_data_vecchia_non_chiude_la_formazione(ambiente):
    """Una partita della giornata 10 rinviata e rimasta in calendario con la data vecchia (prima del turno): Oggi resta nella fase
    «prima» con la scadenza della prima partita del turno (regola unica in turno.py, come promemoria e copia automatica)."""
    archivio.inserisci(ambiente.db, "partite", [{"id": 99, "stagione": ST, "giornata": 10, "data": "2026-10-28 20:45", "casa": "lecce",
                                                 "trasferta": "genoa", "gol_casa": None, "gol_trasferta": None, "giocata": 0,
                                                 "understat_id": None}])
    o = _oggi(ambiente, datetime(2026, 11, 5, 12, 0))
    assert o["inizio"] == o["scadenza"] == "2026-11-07 15:00"
    assert o["iniziata"] is False and o["fase"] == "prima" and o["in_corso"] is None
    assert next(p for p in o["partite"] if p["casa"] == "lecce")["stato"] == "rinviata"



# ---------------------------------------------------------------- etichette della Formazione a giornata iniziata
def _formazione_con_etichette():
    s = lambda i, tit: {"id": i, "nome": ROSA[i][0], "ruolo": ROSA[i][1], "squadra": ROSA[i][2], "p_voto": 0.93, "titolarita": tit,
                        "motivi": ["titolare", "rigorista", "non tra i convocati previsti", "partita favorevole"],
                        "motivi_frasi": [{"chiave": "motivo.titolare"}, {"chiave": "motivo.rigorista"}, {"chiave": "motivo.non_convocato"},
                                         {"chiave": "motivo.favorevole"}]}
    tit = [s(i, "ballottaggio") for i in TITOLARI]
    pan = [s(i, "panchina") for i in PANCHINA]
    return {"giornata": 10, "titolari": tit, "panchina": pan, "fuori": [], "schede": {str(x["id"]): x for x in tit + pan}}


def test_formazione_prima_della_scadenza_tiene_le_etichette(ambiente):
    f = _formazione_con_etichette()
    r = fasi.formazione_a_giornata_iniziata(f, ambiente.db, REGOLE, ST, datetime(2026, 11, 6, 12, 0))
    assert r["iniziata"] is False and r["titolari"][0]["titolarita"] == "ballottaggio" and "stato_partita" not in r["titolari"][0]


def test_formazione_a_giornata_iniziata_stato_vero_non_le_probabili(ambiente):
    """Collaudo 2/11/2026: a giornata in corso i 22 giocatori erano tutti «Ballottaggio» (anche al 93%). Dopo la scadenza le
    etichette delle probabili spariscono: al loro posto lo stato vero della partita."""
    f = _formazione_con_etichette()
    copia = json.loads(json.dumps(f))
    r = fasi.formazione_a_giornata_iniziata(f, ambiente.db, REGOLE, ST, datetime(2026, 11, 8, 21, 30))
    assert f == copia                                              # la formazione in cache non si tocca
    assert r["iniziata"] is True
    tutte = r["titolari"] + r["panchina"] + list(r["schede"].values())
    assert all(x["titolarita"] is None for x in tutte)
    assert all(x["motivi"] == ["rigorista", "partita favorevole"] for x in tutte)     # via i motivi delle probabili
    assert all([m["chiave"] for m in x["motivi_frasi"]] == ["motivo.rigorista", "motivo.favorevole"] for x in tutte)   # in parallelo
    st = {x["id"]: x["stato_partita"] for x in r["titolari"] + r["panchina"]}
    # sabato: Portiere ha il voto, Dif3 è rimasto fuori; domenica sera roma-lazio in corso; lunedì napoli-juve da giocare
    assert (st[1], st[3], st[4], st[5]) == ("fatto", "senza_voto", "in_corso", "da_giocare")
    assert r["schede"]["4"]["stato_partita"] == "in_corso"
    # con la diretta: roma-lazio finita, voti non ancora usciti
    r = fasi.formazione_a_giornata_iniziata(f, ambiente.db, REGOLE, ST, datetime(2026, 11, 8, 21, 30),
                                            {("roma", "lazio"): {"stato": "finita"}})
    assert {x["id"]: x["stato_partita"] for x in r["titolari"]}[4] == "attesa_voti"


def test_a_giornata_iniziata_l_infortunato_resta_fuori_fino_ai_voti(ambiente):
    f = _formazione_con_etichette()
    for x in f["titolari"]:
        if x["id"] in (5, 3):                 # Dif5 gioca lunedì, Dif3 ha già giocato (senza voto)
            x["titolarita"], x["motivi"] = "fuori", ["infortunato"]
    r = fasi.formazione_a_giornata_iniziata(f, ambiente.db, REGOLE, ST, datetime(2026, 11, 8, 21, 30))
    g = {x["id"]: x for x in r["titolari"]}
    assert (g[5]["titolarita"], g[5]["stato_partita"], g[5]["motivi"]) == ("fuori", "da_giocare", ["infortunato"])
    assert (g[3]["titolarita"], g[3]["stato_partita"]) == (None, "senza_voto")         # i voti dicono già com'è andata


def test_formazione_a_giornata_iniziata_non_fallisce_mai(ambiente):
    f = {"giornata": 10, "titolari": [{"id": 1}], "schede": None}
    assert fasi.formazione_a_giornata_iniziata(f, None, REGOLE, ST, datetime(2026, 11, 8, 21, 30)) == f


# ---------------------------------------------------------------- chi entra a giornata iniziata
def test_chi_entra_a_giornata_iniziata_prepara_la_prossima(ambiente):
    """Account nato domenica, dopo la scadenza della giornata 10, senza formazione: niente punti finti, la giornata 11 da preparare."""
    adesso, nato = datetime(2026, 11, 8, 21, 30), datetime(2026, 11, 8, 18, 0)
    o = _oggi(ambiente, adesso, dal=nato)
    assert o["fase"] == "in_corso" and o["in_corso"] is None and o["senza_formazione"] is True
    p = o["prossima"]
    assert p["giornata"] == 11 and p["scadenza"] == "2026-11-14 15:00" and p["con_probabili"] is False
    assert o["miei_titolari"] == {}                              # nessun «tuo titolare» nelle partite
    # chi c'era già prima della scadenza vede la giornata in diretta come sempre (la consigliata)
    o = _oggi(ambiente, adesso, dal=datetime(2026, 11, 1, 10, 0))
    assert o["in_corso"]["formazione_di"] == "consigliata" and "senza_formazione" not in o and o["prossima"] is None
    # senza account (o data non nota): come sempre
    assert _oggi(ambiente, adesso)["in_corso"] is not None


def test_chi_entra_a_giornata_iniziata_ma_ha_salvato_la_sua(ambiente, monkeypatch):
    from fanta import scelte
    monkeypatch.setattr(consigli, "valuta", lambda *a, **k: {"modulo": "4-4-2", "punteggio_atteso": 70.0})
    scelte.salva(ST, 10, TITOLARI, "4-4-2", ambiente.tmp / "scelte.json", panchina=PANCHINA)
    o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30), dal=datetime(2026, 11, 8, 18, 0))
    assert o["in_corso"]["formazione_di"] == "tua" and "senza_formazione" not in o


def test_formazione_sulla_prossima_per_chi_entra_dopo(ambiente, monkeypatch):
    """GET /api/formazione senza giornata: chi è entrato a giornata iniziata senza formazione vede la prossima (server._giornata_saltata)."""
    from fanta import rotte_account, server
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda db, st, r: 10)

    class Orologio(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 8, 21, 30)
    monkeypatch.setattr(server, "datetime", Orologio)
    ctx = NS(scelte=ambiente.tmp / "scelte.json", diario=ambiente.tmp / "diario.json")
    nato = lambda quando: monkeypatch.setattr(rotte_account, "utente_corrente", lambda req: NS(creato=quando))  # noqa: E731
    nato("2026-11-08T17:00:00+00:00")                            # domenica, dopo la scadenza di sabato
    assert server._giornata_saltata(ambiente.db, REGOLE, ctx, None) == 10
    nato("2026-11-01T10:00:00+00:00")                            # c'era già: la giornata in corso, come sempre
    assert server._giornata_saltata(ambiente.db, REGOLE, ctx, None) is None
    nato(None)                                                   # data non nota (o senza account)
    assert server._giornata_saltata(ambiente.db, REGOLE, ctx, None) is None


# ---------------------------------------------------------------- #895: partita rinviata a giornata in corso
def _napoli_juve_rinviata(a) -> None:
    """La partita del lunedì (napoli-juve: Dif5, Cen8, Cen9, Cen13) spostata a dicembre, fuori dal turno: rinviata."""
    a.db.execute("UPDATE partite SET data = '2026-12-09 20:45' WHERE giornata = 10 AND casa = 'napoli'")
    a.db.commit()


def _oggi_in_corso(a, monkeypatch, regole=REGOLE, titolari=TITOLARI, adesso=datetime(2026, 11, 8, 22, 40), panchina=PANCHINA):
    """Oggi a giornata in corso con la formazione salvata (gli 11 di `titolari`, la panchina di sempre) e roma-lazio finita."""
    from fanta import scelte
    monkeypatch.setattr(consigli, "valuta", lambda *a, **k: {"modulo": "4-4-2", "punteggio_atteso": 70.0})
    scelte.salva(ST, 10, titolari, "4-4-2", a.tmp / "scelte.json", panchina=[i for i in panchina if i not in titolari])
    return gestione.oggi(a.db, regole, a.rose, adesso=adesso, file_scelte=a.tmp / "scelte.json", file_diario=a.tmp / "diario.json",
                         live_partite={("roma", "lazio"): {"stato": "finita"}})


def test_in_corso_il_voto_d_ufficio_della_partita_rinviata_ha_la_sua_etichetta(ambiente, monkeypatch):
    """#895: con il voto d'ufficio il server conta il 6 tra i punti fatti; l'etichetta del giocatore lo dice («Voto d'ufficio»),
    così web e iPhone mostrano il voto contato e non «Rinviata» con il fantavoto atteso."""
    from dataclasses import replace
    _napoli_juve_rinviata(ambiente)
    o = _oggi_in_corso(ambiente, monkeypatch, replace(REGOLE, partite_rinviate="voto_ufficio"))
    g = {x["id"]: x for x in o["in_corso"]["giocatori"]}
    assert (g[5]["stato"], g[5]["fantavoto"], g[5]["a_punteggio"]) == ("rinviata", 6.0, True)
    assert g[5]["etichetta"] == {"codice": "voto_ufficio", "testo": "Voto d'ufficio", "tono": "positivo"}
    # con «aspetta» resta «Rinviata», senza voto
    g = {x["id"]: x for x in _oggi_in_corso(ambiente, monkeypatch)["in_corso"]["giocatori"]}
    assert (g[5]["fantavoto"], g[5]["etichetta"]["codice"]) == (None, "rinviata")


def _situazione(o) -> tuple[str, dict]:
    c = o["in_corso"]
    return c["situazione"], c["situazione_frase"]


def test_in_corso_la_frase_sotto_i_punti_la_sceglie_il_server(ambiente, monkeypatch):
    """#895: «Hanno giocato tutti: mancano solo i voti ufficiali.» la diceva la web a ogni `ancora_da_giocare` zero, anche con i
    voti già usciti e un recupero da giocare. Ora la frase la sceglie il server, giusta per il caso, con la sua chiave."""
    from dataclasses import replace
    # domenica sera: roma-lazio finita senza voti, napoli-juve lunedì
    assert _situazione(_oggi_in_corso(ambiente, monkeypatch)) == (
        "3 giocatori devono ancora giocare", {"chiave": "in_corso.da_giocare", "param": {"n": 3}})
    # lunedì notte: tutte finite, voti di domenica e lunedì non ancora usciti
    tardi = datetime(2026, 11, 9, 23, 30)
    o = _oggi_in_corso(ambiente, monkeypatch, adesso=tardi)
    assert o["in_corso"]["ancora_da_giocare"] == 0
    assert _situazione(o)[0] == "Hanno giocato tutti: mancano solo i voti ufficiali."
    # napoli-juve rinviata (la lega aspetta il recupero) e voti di domenica usciti: niente «voti ufficiali», il recupero
    _napoli_juve_rinviata(ambiente)
    _voti(ambiente, VOTI_DOMENICA)
    testo, frase = _situazione(_oggi_in_corso(ambiente, monkeypatch))
    assert testo == "Hanno giocato tutti tranne Dif5, Cen8 e Cen13, che aspettano il recupero."
    assert frase["chiave"] == "in_corso.recupero" and frase["param"]["n"] == 3
    # con il voto d'ufficio la partita rinviata è già contata: i voti ci sono tutti
    assert _situazione(_oggi_in_corso(ambiente, monkeypatch, replace(REGOLE, partite_rinviate="voto_ufficio")))[0] == \
        "I voti dei tuoi giocatori sono tutti usciti."


def test_in_corso_recupero_e_voti_che_mancano_insieme(ambiente, monkeypatch):
    _napoli_juve_rinviata(ambiente)                          # roma-lazio finita, voti non ancora usciti
    titolari = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]          # 5-3-2 con il solo portiere in panchina: del recupero va a punteggio Dif5
    testo, frase = _situazione(_oggi_in_corso(ambiente, monkeypatch, titolari=titolari, panchina=[14]))
    assert (frase["chiave"], frase["param"]["n"]) == ("in_corso.voti_e_recupero", 1)
    assert testo == "Hanno giocato tutti tranne Dif5, che aspetta il recupero; mancano anche i voti ufficiali."
