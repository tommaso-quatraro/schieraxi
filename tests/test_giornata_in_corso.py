"""La giornata resta «in corso» finché non sono finite TUTTE le sue partite (domenica sera e posticipi del lunedì compresi).

Caso vero del 1/11/2026: giornata 10 di Serie A con 6 partite giocate e 4 da giocare (domenica 18:00 e 20:45, lunedì 18:30 e 20:45).
Prima della correzione la giornata «da giocare» era già la 11 (serviva metà delle partite ancora da giocare): Oggi diceva che la
giornata era finita e contava 5 giorni e 1 ora alla scadenza della successiva."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from fanta import consigli, gestione, regole
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
    sono giocate tutte, la giornata da giocare resta la 10; dopo si passa alla 11, che comincia prima del recupero."""
    prima = _rinviate(6, giocate=False)
    assert consigli.prossima_giornata(_db(prima, G11, G12), ST, datetime(2026, 10, 30, 12, 0)) == 10
    sabato_sera = [(d, 1 if i < 2 else 0) for i, (d, _) in enumerate(prima)]     # 2 giocate, la terza in corso, la quarta domenica
    assert consigli.prossima_giornata(_db(sabato_sera, G11, G12), ST, datetime(2026, 10, 31, 22, 0)) == 10
    assert consigli.prossima_giornata(_db(_rinviate(6), G11, G12), ST, datetime(2026, 11, 1, 23, 0)) == 11


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
