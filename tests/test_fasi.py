"""Fasi della giornata in Oggi (fanta/fasi.py): prima della scadenza, giornata in corso (anche la domenica sera con le partite del
lunedì), giornata finita. Orari simulati, archivio finto in una cartella temporanea, nessuna rete."""
import json
from datetime import datetime
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import archivio, consigli, da_fare, fasi, gestione, lega
from fanta.punteggio import fantavoto
from fanta.regole import Regole

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


def _fv(i):
    v, gol = VOTI[i]
    return fantavoto({"voto_red": v, "gol": gol}, ROSA[i][1], REGOLE)


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
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": 10, "calciatore_id": i, "nome": ROSA[i][0], "squadra": ROSA[i][2],
                                     "ruolo": ROSA[i][1], "voto_red": v, "gol": g} for i, (v, g) in VOTI.items()])
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
    return NS(db=db, stato=stato, rose=rose, tmp=tmp_path)


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
def _giornata_finita(a):
    a.stato["giornata"] = 11
    a.stato["giocate"] = {0, 1, 2}
    a.stato["carica"]()


def test_giornata_finita_riepilogo_dal_diario_e_prossima(ambiente):
    _giornata_finita(ambiente)
    (ambiente.tmp / "diario.json").write_text(json.dumps({"giornate": {f"{ST}/10": {
        "consigliata": {"reale": 70.5, "atteso": 68.0}, "schierata": {"reale": 66.0, "atteso": 67.0, "tipo": "manuale",
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
    # nell'archivio finto solo la partita del sabato ha i voti: vanno a punteggio quelli con il voto, Dif12 al posto di Dif3
    assert r["punti_fatti"] == pytest.approx(round(sum(_fv(i) for i in (1, 2, 6, 10, 12)), 1))
    assert o["prossima"]["prepara_da"] == "2026-11-11 15:00" and o["prossima"]["con_probabili"] is False


def test_oggi_non_si_rompe_se_le_fasi_falliscono(ambiente, monkeypatch):
    monkeypatch.setattr(fasi, "blocco_in_corso", lambda *a, **k: 1 / 0)
    o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30))
    assert o["fase"] == "in_corso" and o["in_corso"] is None and o["formazione"]["modulo"] == "4-4-2"
