"""Inizio del turno: una regola sola (fanta/turno.py) per scadenza della formazione, giornata da giocare, «Rinviata» e fine della
giornata. Prima era scritta tre volte con piccole differenze (bordo dei 5 giorni, ripiego, punto di partenza). Dati finti."""
import sqlite3
from datetime import datetime, timedelta

from fanta import avvisi, consigli, fasi, rinvii, turno

ST = "2026-27"


def d(testo):
    return datetime.fromisoformat(testo)


def test_inizio_del_turno():
    turno_vero = [d("2026-11-07 15:00"), d("2026-11-08 15:00"), d("2026-11-08 18:00"), d("2026-11-09 20:45")]
    assert turno.inizio(turno_vero + [d("2026-12-03 18:30"), d("2026-10-01 18:30"), None]) == d("2026-11-07 15:00")
    # Supercoppa (giornata 16 del 2025-26): sei partite il 20-21 dicembre, quattro recuperi a gennaio
    supercoppa = [d("2025-12-20 15:00")] * 3 + [d("2025-12-21 18:00")] * 3 + [d("2026-01-14 20:45")] * 4
    assert turno.inizio(supercoppa) == d("2025-12-20 15:00")
    # date sparse, nessun gruppo con metà delle partite: il gruppo più grande
    sparse = [d("2026-09-01 15:00"), d("2026-09-10 15:00"), d("2026-09-11 15:00"), d("2026-09-20 15:00"), d("2026-09-30 15:00"),
              d("2026-10-10 15:00")]
    assert turno.inizio(sparse) == d("2026-09-10 15:00")
    assert turno.inizio([]) is None and turno.inizio([None]) is None
    # bordo: da `inizio` compreso a `inizio + 5 giorni` escluso
    t = d("2026-11-07 15:00")
    assert turno.nel_turno(t, t) and turno.nel_turno(t + turno.FINESTRA - timedelta(minutes=1), t)
    assert not turno.nel_turno(t + turno.FINESTRA, t) and not turno.nel_turno(t - timedelta(minutes=1), t)
    assert consigli.FINESTRA_TURNO == fasi.FINESTRA_TURNO == turno.FINESTRA


def _db(righe):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, data, giocata) for data, giocata in righe])
    return db


def test_scadenza_rinviata_e_giornata_aperta_coerenti():
    """La partita con la data vecchia (rinviata, prima del turno) e il recupero a 5 giorni esatti: per tutti fuori dal turno."""
    righe = [("2026-10-31 15:00", 0),                                       # rinviata, data vecchia mai aggiornata
             ("2026-11-07 15:00", 0), ("2026-11-08 15:00", 0), ("2026-11-08 18:00", 0), ("2026-11-09 20:45", 0),
             ("2026-11-12 15:00", 0)]                                       # recupero esattamente 5 giorni dopo l'inizio
    db = _db(righe)
    partite = [{"data": data, "giocata": bool(g)} for data, g in righe]
    inizio = fasi.inizio_turno(partite)
    assert inizio == d("2026-11-07 15:00")
    adesso = d("2026-11-06 12:00")
    stati = [fasi.stato_partita(p, adesso, turno=inizio) for p in partite]
    assert stati == ["rinviata", "da_giocare", "da_giocare", "da_giocare", "da_giocare", "rinviata"]
    # la scadenza è la prima partita NON rinviata
    da_giocare = [d(p["data"]) for p, s in zip(partite, stati) if s != "rinviata"]
    assert avvisi.prima_partita(db, ST, 9) == min(da_giocare)
    # a turno finito (tutte giocate tranne le due fuori dal turno) la giornata non resta aperta per loro
    db = _db([(data, 0 if data in ("2026-10-31 15:00", "2026-11-12 15:00") else 1) for data, _ in righe])
    assert consigli.prossima_giornata(db, ST, d("2026-11-11 12:00")) is None
    # ma una partita del turno ancora da giocare (posticipo del lunedì) la tiene aperta
    db = _db([(data, 0 if data in ("2026-10-31 15:00", "2026-11-09 20:45") else 1) for data, _ in righe])
    assert consigli.prossima_giornata(db, ST, d("2026-11-09 21:00")) == 9


def test_fine_della_giornata_dal_turno():
    db = _db([("2026-10-31 15:00", 1), ("2026-11-07 15:00", 1), ("2026-11-08 15:00", 1), ("2026-11-09 20:45", 1),
              ("2026-11-30 20:45", 1)])                                     # recupero giocato settimane dopo: non conta
    assert fasi.fine_giornata(db, ST, 9) == d("2026-11-09 20:45") + fasi.DURATA_PARTITA


# ---------------------------------------------------------------- anticipi (decisione del 2/11/2026)
# giornata normale: sabato 7 - lunedì 9 novembre, 9 partite; l'anticipo è martedì 4 alle 20:45 (3 giorni prima del sabato)
NORMALE = ["2026-11-07 15:00", "2026-11-07 18:00", "2026-11-07 20:45", "2026-11-08 12:30", "2026-11-08 15:00",
           "2026-11-08 15:00", "2026-11-08 18:00", "2026-11-08 20:45", "2026-11-09 20:45"]
ANTICIPO = "2026-11-04 20:45"


def _db_squadre(righe):
    """Calendario con le squadre (per gli stati dei giocatori): righe (data, casa, trasferta, giocata)."""
    from fanta import archivio
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(archivio.SCHEMA)
    db.executemany("INSERT INTO partite (stagione, giornata, data, casa, trasferta, giocata) VALUES (?,?,?,?,?,?)",
                   [(ST, 9, data, casa, trasf, g) for data, casa, trasf, g in righe])
    return db


def test_giornata_normale_invariata():
    assert turno.inizio(d(x) for x in NORMALE) == d("2026-11-07 15:00")
    db = _db([(x, 0) for x in NORMALE])
    assert avvisi.prima_partita(db, ST, 9) == d("2026-11-07 15:00")
    partite = [{"data": x, "giocata": False} for x in NORMALE]
    assert all(fasi.stato_partita(p, d("2026-11-06 12:00"), turno=fasi.inizio_turno(partite)) == "da_giocare" for p in partite)
    # il venerdì sera seguito dal sabato (meno di 36 ore) è del gruppo principale, non un anticipo
    venerdi = ["2026-11-06 20:45"] + NORMALE
    assert turno.inizio(d(x) for x in venerdi) == d("2026-11-06 20:45")
    assert avvisi.prima_partita(_db([(x, 0) for x in venerdi]), ST, 9) == d("2026-11-06 20:45")


def test_anticipo_di_tre_giorni_non_chiude_la_giornata():
    from fanta.regole import Regole
    reg = Regole(scadenza_minuti=10)
    date = [ANTICIPO] + NORMALE
    assert turno.inizio(d(x) for x in date) == d("2026-11-07 15:00")               # il gruppo principale, non l'anticipo
    assert turno.anticipo(d(ANTICIPO), d("2026-11-07 15:00")) and not turno.anticipo(d(NORMALE[0]), d("2026-11-07 15:00"))
    for giocata in (0, 1):                                                         # prima e dopo l'anticipo: la scadenza resta
        db = _db([(ANTICIPO, giocata)] + [(x, 0) for x in NORMALE])
        assert avvisi.prima_partita(db, ST, 9) == d("2026-11-07 15:00")
        assert avvisi.scadenza(avvisi.prima_partita(db, ST, 9), reg) == d("2026-11-07 14:50")    # X minuti dalle regole della lega
        assert not fasi.iniziata(db, reg, ST, 9, d("2026-11-05 12:00"))            # giornata aperta: la formazione si salva
        assert fasi.iniziata(db, reg, ST, 9, d("2026-11-07 14:50"))
        assert consigli.prossima_giornata(db, ST, d("2026-11-05 12:00")) == 9
    # nessuna partita «Rinviata»: né l'anticipo né il posticipo del lunedì (la finestra parte dal gruppo principale)
    partite = [{"data": x, "giocata": False} for x in [ANTICIPO] + NORMALE]
    inizio = fasi.inizio_turno(partite)
    for adesso in (d("2026-11-03 12:00"), d("2026-11-04 21:00"), d("2026-11-09 12:00")):
        assert "rinviata" not in [fasi.stato_partita(p, adesso, turno=inizio) for p in partite]
    assert rinvii.rinviate(partite) == []
    from fanta import live                                                          # la diretta usa la stessa regola
    riga = lambda x: {"giocata": 0, "data": x, "casa": "a", "trasferta": "b", "gol_casa": None, "gol_trasferta": None}
    assert live._da_database(riga(NORMALE[-1]), d("2026-11-06 12:00"), inizio)["stato"] == "da_giocare"     # il lunedì
    assert live._da_database(riga(ANTICIPO), d("2026-11-04 21:00"), inizio)["stato"] == "in_corso"
    assert fasi.stato_partita(partite[0], d("2026-11-04 21:00"), turno=inizio) == fasi.IN_CORSO
    # a turno finito la giornata si chiude dall'ultima del gruppo principale
    db = _db([(x, 1) for x in [ANTICIPO] + NORMALE])
    assert fasi.fine_giornata(db, ST, 9) == d("2026-11-09 20:45") + fasi.DURATA_PARTITA


def test_anticipo_i_suoi_giocatori_hanno_gia_lo_stato_vero_e_la_formazione_resta_aperta():
    from fanta.regole import Regole
    reg = Regole(scadenza_minuti=10)
    db = _db_squadre([(ANTICIPO, "inter", "milan", 1)] + [(x, f"c{i}", f"t{i}", 0) for i, x in enumerate(NORMALE)])
    f = {"giornata": 9, "titolari": [{"id": 1, "ruolo": "A", "squadra": "inter", "titolarita": "titolare", "motivi": ["titolare"]},
                                     {"id": 2, "ruolo": "C", "squadra": "c0", "titolarita": "titolare", "motivi": ["titolare"]}],
         "panchina": [], "fuori": [], "schede": {}}
    r = fasi.formazione_a_giornata_iniziata(f, db, reg, ST, d("2026-11-05 12:00"))
    assert r["iniziata"] is False                                                  # si può ancora salvare
    uno, due = r["titolari"]
    assert uno["stato_partita"] == "attesa_voti" and uno["titolarita"] is None and uno["etichetta"]["codice"] != "titolare"
    assert "stato_partita" not in due and due["titolarita"] == "titolare"         # gli altri: le probabili, come prima
    # prima che l'anticipo cominci: tutto come prima
    db = _db_squadre([(ANTICIPO, "inter", "milan", 0)] + [(x, f"c{i}", f"t{i}", 0) for i, x in enumerate(NORMALE)])
    assert fasi.formazione_a_giornata_iniziata(f, db, reg, ST, d("2026-11-04 12:00")) == f | {"iniziata": False}


def test_recuperi_oltre_sette_giorni_restano_prima_del_turno():
    """Metà giornata di recuperi: 4 partite giocate a dicembre, 6 rinviate a gennaio. Le 4 giocate sono più di 7 giorni prima del
    gruppo principale: fissano la scadenza come sempre (la giornata non si riapre a gennaio)."""
    dicembre = ["2025-12-20 15:00", "2025-12-20 18:00", "2025-12-21 15:00", "2025-12-21 20:45"]
    gennaio = ["2026-01-14 18:00", "2026-01-14 20:45", "2026-01-15 18:00", "2026-01-15 20:45", "2026-01-15 20:45", "2026-01-15 20:45"]
    assert turno.inizio(d(x) for x in dicembre + gennaio) == d("2026-01-14 18:00")
    db = _db([(x, 1) for x in dicembre] + [(x, 0) for x in gennaio])
    assert avvisi.prima_partita(db, ST, 9) == d("2025-12-20 15:00")
    # prima di giocarle, le stesse 4 date (oltre 7 giorni) contano come oggi: «prima del turno», non un anticipo
    assert not turno.anticipo(d(dicembre[-1]), d("2026-01-14 18:00"))


def test_rinvio_vero_resta_rinviato():
    """Una partita senza data, una con la data vecchia mai aggiornata (oltre 7 giorni prima) e un recupero dopo la finestra."""
    partite = ([{"data": None, "giocata": False}, {"data": "2026-10-28 20:45", "giocata": False},
                {"data": "2026-11-25 20:45", "giocata": False}] + [{"data": x, "giocata": False} for x in NORMALE])
    inizio = fasi.inizio_turno(partite)
    assert inizio == d("2026-11-07 15:00")
    stati = [fasi.stato_partita(p, d("2026-11-06 12:00"), turno=inizio) for p in partite]
    assert stati[:3] == ["rinviata"] * 3 and set(stati[3:]) == {"da_giocare"}
    assert len(rinvii.rinviate(partite)) == 3
    db = _db([(p["data"], 0) for p in partite if p["data"]])
    assert avvisi.prima_partita(db, ST, 9) == d("2026-11-07 15:00")


def test_turno_diviso_a_pasqua_non_e_un_anticipo():
    """Pasqua 2023-24 (calendario vero): 5 partite sabato 30 marzo e 5 lunedì 1 aprile, più di 36 ore in mezzo. Anche con una
    divisione 3 + 7 il sabato non diventa un «anticipo»: la formazione si chiude sabato come sempre."""
    sabato = ["2024-03-30 12:30", "2024-03-30 15:00", "2024-03-30 18:00", "2024-03-30 18:00", "2024-03-30 20:45"]
    lunedi = ["2024-04-01 12:30", "2024-04-01 15:00", "2024-04-01 18:00", "2024-04-01 18:00", "2024-04-01 20:45"]
    assert turno.inizio(d(x) for x in sabato + lunedi) == d("2024-03-30 12:30")
    tre_sette = sabato[:3] + lunedi + ["2024-04-01 20:45", "2024-04-01 20:45"]
    assert turno.inizio(d(x) for x in tre_sette) == d("2024-03-30 12:30")
    assert avvisi.prima_partita(_db([(x, 0) for x in tre_sette]), ST, 9) == d("2024-03-30 12:30")
    # due anticipi (martedì e mercoledì) restano anticipi
    due = ["2026-11-03 20:45", "2026-11-04 20:45"] + NORMALE
    assert turno.inizio(d(x) for x in due) == d("2026-11-07 15:00")


def test_turno_diviso_con_gruppo_principale_cinque_giorni_dopo():
    """Issue #139 (controesempio di Hypothesis): 3 partite venerdì e 4 il mercoledì dopo, a 5 giorni. Più di MAX_ANTICIPI partite
    prima del gruppo principale non sono anticipi ma un turno diviso: il turno parte dalla prima e la formazione si chiude venerdì."""
    from fanta.regole import Regole
    venerdi, mercoledi = "2026-08-21 12:30", "2026-08-26 12:30"
    date = [venerdi] * 3 + [mercoledi] * 4
    inizio = turno.inizio(d(x) for x in date)
    assert inizio == d(venerdi)
    assert sum(turno.anticipo(d(x), inizio) for x in date) <= turno.MAX_ANTICIPI
    assert turno.conta_per_scadenza(d(venerdi), True, inizio)
    reg = Regole(scadenza_minuti=10)
    for giocata in (0, 1):                                  # prima e dopo le partite del venerdì: la scadenza è venerdì
        db = _db([(venerdi, giocata)] * 3 + [(mercoledi, 0)] * 4)
        assert avvisi.prima_partita(db, ST, 9) == d(venerdi)
        assert fasi.iniziata(db, reg, ST, 9, d("2026-08-21 12:20"))
