"""La giornata resta «in corso» finché non sono finite TUTTE le sue partite (domenica sera e posticipi del lunedì compresi).

Caso vero del 1/11/2026: giornata 10 di Serie A con 6 partite giocate e 4 da giocare (domenica 18:00 e 20:45, lunedì 18:30 e 20:45).
Prima della correzione la giornata «da giocare» era già la 11 (serviva metà delle partite ancora da giocare): Oggi diceva che la
giornata era finita e contava 5 giorni e 1 ora alla scadenza della successiva."""
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import avvisi, consigli, fasi, gestione, live, regole, rinvii
from fanta.regole import Regole

ST = "2026-27"
G10 = [("2026-10-31 15:00", 1), ("2026-10-31 18:00", 1), ("2026-10-31 20:45", 1), ("2026-11-01 12:30", 1), ("2026-11-01 15:00", 1),
       ("2026-11-01 15:00", 1), ("2026-11-01 18:00", 0), ("2026-11-01 20:45", 0), ("2026-11-02 18:30", 0), ("2026-11-02 20:45", 0)]
G11 = [("2026-11-06 20:45", 0), ("2026-11-07 15:00", 0), ("2026-11-07 15:00", 0), ("2026-11-07 18:00", 0), ("2026-11-07 20:45", 0),
       ("2026-11-08 12:30", 0), ("2026-11-08 15:00", 0), ("2026-11-08 15:00", 0), ("2026-11-08 18:00", 0), ("2026-11-08 20:45", 0)]
DOMENICA_SERA = datetime(2026, 11, 1, 19, 35)


def _db(g10=G10, g11=G11, g12=(), altre: dict | None = None):
    """Il calendario delle giornate 10, 11 e 12; `altre` = {giornata: partite} per quelle dopo."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)",
                   [(ST, g, d, f"c{g}{i}", f"t{g}{i}", gi)
                    for g, partite in ((10, g10), (11, g11), (12, g12), *(altre or {}).items()) for i, (d, gi) in enumerate(partite)])
    return db


def _regole_scadenza_10():
    r = regole.imposta(Regole(), "scadenza_minuti", "10")
    return regole.imposta(r, "prima_giornata_lega", "4")


def test_domenica_sera_con_partite_in_corso_la_giornata_non_e_finita(monkeypatch):
    assert consigli.prossima_giornata(_db(), ST, DOMENICA_SERA) == 10
    monkeypatch.setattr(consigli, "_adesso", lambda: DOMENICA_SERA)     # senza «adesso» esplicito: l'ora del server
    assert consigli.prossima_giornata(_db(), ST) == 10
    assert consigli.giornata_da_giocare(_db(), ST, _regole_scadenza_10()) == 10


def test_oggi_dice_in_corso_e_non_conta_alla_giornata_dopo(monkeypatch):
    monkeypatch.setattr(consigli, "_adesso", lambda: DOMENICA_SERA)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(), adesso=DOMENICA_SERA, regole=_regole_scadenza_10())
    assert o["giornata"] == 10 and o["giornata_lega"] == 7
    assert o["iniziata"] is True                                   # «In corso», non un conto alla rovescia di 5 giorni
    assert len(o["partite"]) == 10 and sum(not p["giocata"] for p in o["partite"]) == 4


def test_lunedi_sera_i_posticipi_tengono_aperta_la_giornata():
    assert consigli.prossima_giornata(_db(), ST, datetime(2026, 11, 2, 23, 0)) == 10   # risultati non ancora scaricati


def test_finite_tutte_si_passa_alla_prossima_con_la_scadenza_giusta(monkeypatch):
    finite = [(d, 1) for d, _ in G10]
    martedi = datetime(2026, 11, 3, 10, 0)
    assert consigli.prossima_giornata(_db(finite), ST, martedi) == 11
    monkeypatch.setattr(consigli, "_adesso", lambda: martedi)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(finite), adesso=martedi, regole=_regole_scadenza_10())
    assert o["giornata"] == 11 and o["iniziata"] is False
    assert o["scadenza"] == "2026-11-06 20:35"                     # 10 minuti prima della prima partita della giornata 11


def test_se_i_risultati_tardano_dopo_mezza_giornata_si_passa_alla_prossima():
    assert consigli.prossima_giornata(_db(), ST, datetime(2026, 11, 3, 10, 0)) == 11


def test_recupero_isolato_non_tiene_ferma_la_giornata():
    rinviata_lontano = [(d, 1) for d, _ in G10[:-1]] + [("2026-12-10 20:45", 0)]   # rinviata a dicembre
    assert consigli.prossima_giornata(_db(rinviata_lontano), ST, datetime(2026, 11, 3, 10, 0)) == 11
    vecchia_data = [(d, 1) for d, _ in G10[:-1]] + [("2026-11-02 20:45", 0)]       # rinviata, data mai aggiornata
    assert consigli.prossima_giornata(_db(vecchia_data), ST, datetime(2026, 11, 4, 10, 0)) == 11


def test_giornata_ancora_quasi_tutta_da_giocare():
    sabato = [(d, 1 if i < 2 else 0) for i, (d, _) in enumerate(G10)]
    assert consigli.prossima_giornata(_db(sabato), ST, datetime(2026, 10, 31, 19, 0)) == 10


# ---------------------------------------------------------------- metà giornata rinviata a un mese dopo (#659)
# La giornata 10 giocata in parte nel fine settimana e il resto rinviato ai primi di dicembre (o senza data): la giornata da giocare
# deve passare alla 11 e poi alla 12, che intanto si giocano. Prima, con 5 o più partite rinviate, restava la 10 fino al recupero.
G12 = [("2026-11-21 15:00", 0), ("2026-11-21 18:00", 0), ("2026-11-21 20:45", 0), ("2026-11-22 12:30", 0), ("2026-11-22 15:00", 0),
       ("2026-11-22 15:00", 0), ("2026-11-22 18:00", 0), ("2026-11-22 20:45", 0), ("2026-11-23 18:30", 0), ("2026-11-23 20:45", 0)]
RECUPERI = ["2026-12-02 18:30", "2026-12-02 20:45", "2026-12-02 20:45", "2026-12-03 18:30", "2026-12-03 20:45", "2026-12-03 20:45"]
MARTEDI = datetime(2026, 11, 3, 10, 0)
MARTEDI_DOPO = datetime(2026, 11, 10, 10, 0)


def _rinviate(n: int, con_data: bool = True, giocate: bool = True) -> list:
    """La giornata 10 con le prime 10 - n partite nel fine settimana (giocate) e le altre n rinviate a dicembre (o senza data)."""
    return [(d, int(giocate)) for d, _ in G10[:10 - n]] + [(RECUPERI[k] if con_data else None, 0) for k in range(n)]


@pytest.mark.parametrize("con_data", [True, False], ids=["recupero a dicembre", "senza data"])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_partite_rinviate_a_un_mese_dopo_non_tengono_ferma_la_giornata(n, con_data):
    g10 = _rinviate(n, con_data)
    assert consigli.prossima_giornata(_db(g10, G11, G12), ST, MARTEDI) == 11
    g11_finita = [(d, 1) for d, _ in G11]
    assert consigli.prossima_giornata(_db(g10, g11_finita, G12), ST, MARTEDI_DOPO) == 12
    assert consigli.giornata_da_giocare(_db(g10, g11_finita, G12), ST, _regole_scadenza_10(), MARTEDI_DOPO) == 12


def test_cinque_rinviate_oggi_mostra_la_giornata_dopo_aperta(monkeypatch):
    monkeypatch.setattr(consigli, "_adesso", lambda: MARTEDI)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(_db(_rinviate(5), G11, G12), adesso=MARTEDI, regole=_regole_scadenza_10())
    assert o["giornata"] == 11 and o["iniziata"] is False
    assert o["scadenza"] == "2026-11-06 20:35"


def test_quattro_giocate_e_sei_rinviate_la_giornata_resta_finche_si_gioca_il_fine_settimana():
    """4 partite nel fine settimana e 6 rinviate a dicembre: per turno.py il turno è il gruppo di dicembre. Finché le 4 partite non
    sono giocate tutte, la giornata da giocare resta la 10; dopo si passa alla 11: quelle che restano sono recuperi settimane dopo."""
    prima = _rinviate(6, giocate=False)
    assert consigli.prossima_giornata(_db(prima, G11, G12), ST, datetime(2026, 10, 30, 12, 0)) == 10
    sabato_sera = [(d, 1 if i < 2 else 0) for i, (d, _) in enumerate(prima)]     # 2 giocate, la terza in corso, la quarta domenica
    assert consigli.prossima_giornata(_db(sabato_sera, G11, G12), ST, datetime(2026, 10, 31, 22, 0)) == 10
    assert consigli.prossima_giornata(_db(_rinviate(6), G11, G12), ST, datetime(2026, 11, 1, 23, 0)) == 11


@pytest.mark.parametrize("modo", ["aspetta", "senza_voto", "voto_ufficio"])
def test_quattro_giocate_e_sei_rinviate_con_i_recuperi_gia_in_calendario_la_scadenza_e_quella_del_turno(monkeypatch, modo):
    """#698: 4 partite della 10 nel fine settimana e 6 rinviate al 2-3 dicembre, dopo la 11, già in calendario il venerdì. Prima che
    le 4 partite si giochino il turno è il loro fine settimana, non i recuperi: la scadenza è il 31/10 alle 15:00 (prima: il recupero
    del 2/12, e la formazione restava aperta mentre si giocava), le 4 partite sono «da giocare» e i 6 recuperi «rinviata» (prima il
    contrario), e la regola dei rinvii della lega cade su chi ha il recupero, non su chi gioca nel fine settimana."""
    db = _db(_rinviate(6, giocate=False), G11, G12)
    venerdi, reg = datetime(2026, 10, 30, 12, 0), replace(_regole_scadenza_10(), partite_rinviate=modo)
    assert avvisi.prima_partita(db, ST, 10) == datetime(2026, 10, 31, 15, 0)
    assert not fasi.iniziata(db, reg, ST, 10, venerdi)
    assert fasi.iniziata(db, reg, ST, 10, datetime(2026, 10, 31, 14, 50))
    monkeypatch.setattr(consigli, "_adesso", lambda: venerdi)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(db, adesso=venerdi, regole=reg)
    assert o["giornata"] == 10 and o["scadenza"] == "2026-10-31 14:50" and o["iniziata"] is False
    assert [p["stato"] for p in o["partite"]] == ["da_giocare"] * 4 + ["rinviata"] * 6
    partite = pd.read_sql_query("SELECT rowid AS id, stagione, giornata, data, giocata FROM partite", db)
    recuperi = set(partite[(partite["giornata"] == 10) & (partite["data"] >= "2026-12")]["id"])
    assert len(recuperi) == 6 and rinvii.id_rinviate(partite, ST, 10) == recuperi
    sabato, recupero = (int(partite[(partite["giornata"] == 10) & (partite["data"] == d)]["id"].iloc[0])
                        for d in ("2026-10-31 15:00", RECUPERI[0]))
    prev = pd.DataFrame([{"id": 1, "partita": sabato, "p_voto": 0.9, "mu": 7.0, "mu_voto": 6.4, "atteso": 6.3, "quota_titolare": 0.9},
                         {"id": 2, "partita": recupero, "p_voto": 0.8, "mu": 7.0, "mu_voto": 6.4, "atteso": 5.6,
                          "quota_titolare": 0.8}]).set_index("id")
    p = rinvii.applica(prev, rinvii.id_rinviate(partite, ST, 10), rinvii.regola(reg, ST, 10))      # come consigli._calcola_previsioni
    assert p.at[1, "rinvio"] is None and p.at[1, "p_voto"] == 0.9                 # gioca sabato: numeri di sempre
    assert p.at[2, "rinvio"] == modo
    # GET /api/live (server._risposta_live) con l'inizio della giornata dopo: stessi stati di Oggi
    righe = db.execute("SELECT data, casa, trasferta, giornata, giocata FROM partite WHERE giornata = 10 ORDER BY data").fetchall()
    corpo = live.risposta(live.Raccoglitore(lambda: [], adesso=lambda: venerdi), righe, avvisi.turno_dopo(db, ST, 10))
    assert [p["stato"] for p in corpo["partite"]] == ["da_giocare"] * 4 + ["rinviata"] * 6


VENERDI = datetime(2026, 10, 30, 12, 0)


def _archivio(tmp_path, g10: list, g11: list = G11, g12: list = G12):
    """Le giornate 10, 11 e 12 in un archivio vero (con le tabelle dei voti e dei gol); il percorso: le rotte chiudono la connessione."""
    from fanta import archivio
    percorso = tmp_path / "fanta.sqlite"
    db = archivio.apri(percorso)
    archivio.inserisci(db, "partite", [{"id": 100 * g + i, "stagione": ST, "giornata": g, "data": d, "casa": f"c{g}{i}",
                                        "trasferta": f"t{g}{i}", "gol_casa": None, "gol_trasferta": None, "giocata": gi,
                                        "understat_id": None}
                                       for g, partite in ((10, g10), (11, g11), (12, g12)) for i, (d, gi) in enumerate(partite)])
    db.commit()
    db.close()
    return percorso


def _partite_oggi(db, giornata: int) -> list[dict]:
    return [{"data": r[0], "casa": r[1], "trasferta": r[2], "giocata": bool(r[3])} for r in
            db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND giornata = ? ORDER BY data",
                       (ST, giornata))]


def test_quattro_giocate_e_sei_rinviate_oggi_con_le_rose_ha_gli_stati_del_turno(tmp_path):
    """#698, revisione della #721: Oggi con le rose (`fasi.aggiungi`) il venerdì, recuperi già in calendario: 4 partite «da_giocare»
    e 6 «rinviata», come Oggi senza rose (prima il contrario)."""
    from fanta import archivio
    db = archivio.apri(_archivio(tmp_path, _rinviate(6, giocate=False)))
    corpo = {"giornata": 10, "iniziata": False, "ore_mancanti": 26.8, "partite": _partite_oggi(db, 10)}
    corpo = fasi.aggiungi(corpo, db, _regole_scadenza_10(), None, None, {}, ST, VENERDI)
    assert [p["stato"] for p in corpo["partite"]] == ["da_giocare"] * 4 + ["rinviata"] * 6


def test_quattro_giocate_e_sei_rinviate_dopo_la_scadenza_il_giocatore_del_recupero_e_rinviato(tmp_path):
    """#698, revisione della #721: lo stato dei giocatori a formazione chiusa (`fasi.stati_giocatori`, Formazione e Oggi in corso):
    chi gioca sabato «da_giocare», chi ha il recupero di dicembre «rinviata» (prima il contrario)."""
    from fanta import archivio
    db = archivio.apri(_archivio(tmp_path, _rinviate(6, giocate=False)))
    giocatori = [{"id": 1, "ruolo": "A", "squadra": "c100"}, {"id": 2, "ruolo": "A", "squadra": "c104"}]   # sabato 15:00, recupero
    assert fasi.stati_giocatori(db, _regole_scadenza_10(), ST, 10, giocatori, datetime(2026, 10, 31, 14, 55)) == {
        1: "da_giocare", 2: "rinviata"}


def test_quattro_giocate_e_sei_rinviate_api_live_ha_gli_stati_del_turno(tmp_path, monkeypatch):
    """#698, revisione della #721: GET /api/live (`server._risposta_live`) il venerdì: 4 partite «da_giocare» e 6 «rinviata», come in
    Oggi (prima il contrario)."""
    from fanta import archivio, server
    percorso = _archivio(tmp_path, _rinviate(6, giocate=False))
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(percorso))
    monkeypatch.setattr(consigli, "_adesso", lambda: VENERDI)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(live, "unico", live.Raccoglitore(lambda: [], adesso=lambda: VENERDI))
    assert [p["stato"] for p in server._risposta_live()["partite"]] == ["da_giocare"] * 4 + ["rinviata"] * 6


def test_quattro_giocate_e_sei_rinviate_oggi_finita_dopo_il_fine_settimana(tmp_path):
    """#698, revisione della #721: lunedì, giocate le 4 partite del fine settimana e con i 6 recuperi a dicembre, Oggi della giornata
    11 è in fase «finita» (riepilogo della 10, finita col suo turno), come con 5 giocate e 5 rinviate. Prima la 10 non finiva fino al
    recupero e Oggi restava in fase «prima»."""
    from fanta import archivio
    db = archivio.apri(_archivio(tmp_path, _rinviate(6)))
    lunedi = datetime(2026, 11, 2, 12, 0)
    corpo = {"giornata": 11, "iniziata": False, "ore_mancanti": 104.6, "partite": _partite_oggi(db, 11)}
    assert fasi.aggiungi(corpo, db, _regole_scadenza_10(), None, None, {}, ST, lunedi)["fase"] == fasi.FINITA


def test_quattro_giocate_e_sei_rinviate_con_un_anticipo_i_suoi_giocatori_restano_fermi(tmp_path):
    """#698, revisione della #721: nel 4 + 6 una delle 4 partite si gioca il mercoledì prima (anticipo del turno del fine settimana).
    A partita cominciata le sue squadre sono quelle di un anticipo (`fasi.squadre_in_anticipo_iniziato`: giocatori fermi, stato vero)
    e la formazione resta aperta fino al sabato; prima il turno era il recupero di dicembre e l'anticipo non si riconosceva."""
    from fanta import archivio
    g10 = [("2026-10-28 20:45", 0)] + [(d, 0) for d, _ in G10[:3]] + [(d, 0) for d in RECUPERI]
    db = archivio.apri(_archivio(tmp_path, g10))
    mercoledi_sera = datetime(2026, 10, 28, 21, 30)
    assert fasi.squadre_in_anticipo_iniziato(db, ST, 10, mercoledi_sera) == {"c100", "t100"}
    assert avvisi.prima_partita(db, ST, 10) == datetime(2026, 10, 31, 15, 0)
    assert not fasi.iniziata(db, _regole_scadenza_10(), ST, 10, mercoledi_sera)


def _sposta(partite: list, giorni: int, giocata: int = 0) -> list:
    """Le stesse partite `giorni` dopo (un turno uguale qualche settimana più in là)."""
    return [((datetime.fromisoformat(d) + timedelta(days=giorni)).strftime("%Y-%m-%d %H:%M"), giocata) for d, _ in partite]


def test_quattro_giocate_e_sei_rinviate_la_giornata_chiusa_non_torna_prima_del_recupero(monkeypatch):
    """Revisione della #695: quando i recuperi della 10 (2-3 dicembre) diventano le partite più vicine, la 10, chiusa dal 31/10, non
    torna «da giocare»: si prepara la 14 (4-7 dicembre), come con 5 giocate e 5 rinviate. Una giornata già cominciata la tengono
    aperta solo le partite entro turno.FINESTRA dalla sua prima."""
    finite = {11: [(d, 1) for d, _ in G11], 12: [(d, 1) for d, _ in G12], 13: _sposta(G12, 6, giocata=1)}
    db = _db(_rinviate(6), finite[11], finite[12], {13: finite[13], 14: _sposta(G12, 13)})
    for adesso in (datetime(2026, 12, 1, 10, 0), datetime(2026, 12, 2, 19, 0), datetime(2026, 12, 3, 23, 30)):
        assert consigli.prossima_giornata(db, ST, adesso) == 14, adesso
    monkeypatch.setattr(consigli, "_adesso", lambda: datetime(2026, 12, 1, 10, 0))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(db, adesso=datetime(2026, 12, 1, 10, 0), regole=_regole_scadenza_10())
    assert o["giornata"] == 14 and o["iniziata"] is False


def test_giornata_normale_cominciata_resta_finche_ha_partite_entro_la_finestra():
    """Le giornate normali non cambiano: una partita da giocare entro turno.FINESTRA dalla prima (un recupero a metà settimana) tiene
    aperta la giornata; dalla FINESTRA in poi è un recupero e non la tiene."""
    dentro = [(d, 1) for d, _ in G10[:-1]] + [("2026-11-05 14:59", 0)]      # 5 giorni meno un minuto dopo sabato alle 15:00
    assert consigli.prossima_giornata(_db(dentro), ST, datetime(2026, 11, 4, 12, 0)) == 10
    fuori = [(d, 1) for d, _ in G10[:-1]] + [("2026-11-05 15:00", 0)]
    assert consigli.prossima_giornata(_db(fuori), ST, datetime(2026, 11, 4, 12, 0)) == 11


ANTICIPATE = [("2026-11-02 20:45", 1), ("2026-11-03 20:45", 1), ("2026-11-04 20:45", 1), ("2026-11-05 20:45", 1)]


@pytest.mark.parametrize("quante", [1, 2, 3, 4])
def test_partite_anticipate_di_settimane_non_fanno_saltare_la_giornata(monkeypatch, quante):
    """Coordinatore, #695: partite della 12 giocate settimane prima del suo turno (21-23 novembre: Supercoppa, coppe) sono anticipi
    lontani, non metà giornata giocata: il turno della 12 comincia prima di quello della 13. La 12 resta «da giocare» finché il suo
    turno ha partite da cominciare, quante che siano le partite anticipate (si decide dalla posizione, non dal numero), come su
    main. Nel 4 + 6 invece il turno (i recuperi) comincia dopo la giornata dopo (test sopra)."""
    g12 = ANTICIPATE[:quante] + [(d, 0) for d, _ in G12[quante:]]
    db = _db([(d, 1) for d, _ in G10], [(d, 1) for d, _ in G11], g12, {13: _sposta(G12, 7)})
    for adesso in (datetime(2026, 11, 12, 12, 0), datetime(2026, 11, 21, 16, 0), datetime(2026, 11, 23, 21, 0)):
        assert consigli.prossima_giornata(db, ST, adesso) == 12, adesso
    monkeypatch.setattr(consigli, "_adesso", lambda: datetime(2026, 11, 12, 12, 0))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    assert gestione.oggi_senza_rose(db, adesso=datetime(2026, 11, 12, 12, 0), regole=_regole_scadenza_10())["giornata"] == 12


@pytest.mark.parametrize("quante", [1, 2, 3])
def test_partite_anticipate_di_settimane_non_fissano_la_scadenza_e_i_loro_giocatori_restano_fermi(quante):
    """Coordinatore, #695 (difetto già su main): la scadenza viene dal turno principale. Prima la partita anticipata di settimane, già
    giocata, fissava la scadenza: la giornata risultava iniziata dal giorno dell'anticipo, quindi niente salvataggio (409), niente
    copia alla scadenza e niente promemoria. Chi ha giocato l'anticipo resta fermo come per un anticipo (turno.py)."""
    g12 = ANTICIPATE[:quante] + [(d, 0) for d, _ in G12[quante:]]
    db = _db([(d, 1) for d, _ in G10], [(d, 1) for d, _ in G11], g12, {13: _sposta(G12, 7)})
    turno_12 = datetime.fromisoformat(G12[quante][0])
    assert avvisi.prima_partita(db, ST, 12) == turno_12
    reg = _regole_scadenza_10()
    assert not fasi.iniziata(db, reg, ST, 12, datetime(2026, 11, 12, 12, 0))                  # la formazione si salva
    assert fasi.iniziata(db, reg, ST, 12, turno_12 - timedelta(minutes=10))                   # e si chiude col turno
    attese = {s for k in range(quante) for s in (f"c12{k}", f"t12{k}")}
    assert fasi.squadre_in_anticipo_iniziato(db, ST, 12, datetime(2026, 11, 12, 12, 0)) == attese
    # nel 4 + 6 le partite giocate prima del recupero fissano la scadenza come prima: lì il turno comincia dopo la giornata dopo
    finite = {11: [(d, 1) for d, _ in G11], 12: [(d, 1) for d, _ in G12]}
    db = _db(_rinviate(6), finite[11], finite[12])
    assert avvisi.prima_partita(db, ST, 10) == datetime(2026, 10, 31, 15, 0)
    assert fasi.squadre_in_anticipo_iniziato(db, ST, 10, datetime(2026, 11, 3, 12, 0)) == set()


def test_meta_giornata_rinviata_dentro_la_sosta_la_scadenza_passata_non_torna_indietro(monkeypatch):
    """Quarta revisione della #695: 4 partite della 10 giocate il 31/10-1/11, le altre 6 rinviate all'11-12/11 dentro la sosta, la
    11 dal 20/11. Per turno.py il turno è il recupero, che comincia prima della giornata dopo: le 4 partite sembravano anticipi
    lontani e la 10 tornava aperta con scadenza 11/11. Un anticipo lontano si gioca prima della fine del turno della giornata
    precedente (la 9, 24-27 ottobre); queste sono state giocate dopo, quindi sono metà giornata e la scadenza resta il 31/10."""
    g9 = [(d, 1) for d, _ in _sposta(G10, -7)]
    sosta = [("2026-11-11 18:30", 0), ("2026-11-11 20:45", 0), ("2026-11-11 20:45", 0), ("2026-11-12 18:30", 0),
             ("2026-11-12 20:45", 0), ("2026-11-12 20:45", 0)]
    g10 = [(d, 1) for d, _ in G10[:4]] + sosta
    db = _db(g10, _sposta(G11, 14), (), {9: g9})
    reg = _regole_scadenza_10()
    assert avvisi.prima_partita(db, ST, 10) == datetime(2026, 10, 31, 15, 0)
    for adesso in (datetime(2026, 11, 1, 18, 0), datetime(2026, 11, 3, 10, 0)):
        assert fasi.iniziata(db, reg, ST, 10, adesso), adesso
        assert fasi.squadre_in_anticipo_iniziato(db, ST, 10, adesso) == set()
    monkeypatch.setattr(consigli, "_adesso", lambda: datetime(2026, 11, 3, 10, 0))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    o = gestione.oggi_senza_rose(db, adesso=datetime(2026, 11, 3, 10, 0), regole=reg)
    assert o["iniziata"] is True and o["scadenza"] == "2026-10-31 14:50"
