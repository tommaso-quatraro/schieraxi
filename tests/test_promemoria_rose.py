"""Promemoria «aggiorna le rose» di Da fare (issue #334): compare solo dopo un momento di mercato della lega (inizio della stagione,
sosta del campionato, asta invernale, finestre di scambio indicate in regole.json) e solo se le rose non sono state aggiornate da
quando è cominciato; sparisce con l'aggiornamento o alla scadenza della prima giornata dopo. Calendari e date inventati."""
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from fanta import da_fare, regole as R, server
from fanta.regole import Regole

ST = "2026-27"
D = datetime
# autunno inventato: giornate di sabato (dieci partite a sei ore l'una dall'altra, fino al lunedì sera), sosta fra la 11 e la 12
AUTUNNO = [(9, D(2026, 10, 24, 15)), (10, D(2026, 10, 31, 15)), (11, D(2026, 11, 7, 15)), (12, D(2026, 11, 21, 15)),
           (13, D(2026, 11, 28, 15))]
# gennaio inventato, una giornata a settimana e nessuna sosta
GENNAIO = [(19, D(2027, 1, 9, 15)), (20, D(2027, 1, 16, 15)), (21, D(2027, 1, 23, 15)), (22, D(2027, 1, 30, 15))]
# inizio della stagione inventato: sosta fra la 2 e la 3
ESTATE = [(1, D(2026, 8, 22, 18)), (2, D(2026, 8, 29, 18)), (3, D(2026, 9, 12, 15)), (4, D(2026, 9, 19, 15))]
FRASE = "È il momento di aste e scambi nella lega: se le rose sono cambiate, aggiornale prima della giornata {n}."


@pytest.fixture(autouse=True)
def _stagione(monkeypatch):
    monkeypatch.setattr(da_fare.consigli, "stagione_corrente", lambda: ST)


def calendario(giornate, adesso):
    """Le partite già cominciate a `adesso` sono giocate (come nell'archivio vero)."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INTEGER, data TEXT, giocata INTEGER)")
    for g, inizio in giornate:
        for i in range(10):
            quando = inizio + timedelta(hours=6 * i)
            db.execute("INSERT INTO partite VALUES (?, ?, ?, ?)", (ST, g, quando.isoformat(sep=" ")[:16], int(quando < adesso)))
    return db


def rose_del(tmp_path, quando: datetime):
    f = tmp_path / "rose.json"
    f.write_text("{}", encoding="utf-8")
    os.utime(f, (quando.timestamp(), quando.timestamp()))
    return f


def promemoria(tmp_path, giornate, adesso, rose_aggiornate, regole=None):
    """La voce `rose` di Da fare (o None), con la formazione già chiusa: così restano solo i controlli che non sono consigli."""
    rose = rose_del(tmp_path, rose_aggiornate)
    ctx = NS(utente_id=1, rose=rose, scelte=tmp_path / "scelte.json", diario=tmp_path / "diario.json", impostazioni_avvisi=None)
    voci = da_fare.costruisci(calendario(giornate, adesso), regole or Regole(), None, {"iniziata": True}, ctx, adesso=adesso)
    r = [v for v in voci if v["tipo"] == "rose"]
    assert len(r) <= 1
    return r[0] if r else None


# ---------------------------------------------------------------- soste dal calendario della Serie A (nessuna data nelle regole)
def test_in_mezzo_al_campionato_niente_anche_con_rose_vecchie(tmp_path):
    """Prima: «Le rose non sono aggiornate da N giorni e nel frattempo si è giocata una giornata» ogni settimana."""
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 4, 12), rose_aggiornate=D(2026, 10, 1)) is None


def test_dopo_la_sosta_il_promemoria_dice_perche_e_fino_a_quando(tmp_path):
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), rose_aggiornate=D(2026, 11, 1, 10))
    assert v is not None
    assert v["testo"] == FRASE.format(n=12)
    assert v["frase"] == {"chiave": "dafare.rose_mercato", "param": {"n": 12}}
    assert (v["id"], v["priorita"], v["azione"]) == ("rose-vecchie", 2, "Aggiorna le rose")
    assert v["destinazione"]["link"] == "schieraxi://lega/rose" and v["giorni"] == 11


def test_la_sosta_comincia_dopo_l_ultima_partita_della_giornata_prima(tmp_path):
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 9, 12), rose_aggiornate=D(2026, 11, 1)) is None       # si gioca ancora la 11
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 9, 22), rose_aggiornate=D(2026, 11, 1)) is not None


def test_dopo_l_aggiornamento_delle_rose_sparisce(tmp_path):
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), rose_aggiornate=D(2026, 11, 10, 9)) is None


def test_sparisce_alla_scadenza_della_giornata_dopo_la_sosta(tmp_path):
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 21, 14, 59), rose_aggiornate=D(2026, 11, 1)) is not None
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 21, 15, 0), rose_aggiornate=D(2026, 11, 1)) is None
    trenta = Regole(scadenza_minuti=30)                                       # la scadenza della lega, non l'inizio della partita
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 21, 14, 29), D(2026, 11, 1), trenta) is not None
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 21, 14, 31), D(2026, 11, 1), trenta) is None


def test_il_numero_e_quello_della_giornata_della_lega(tmp_path):
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), D(2026, 11, 1), Regole(prima_giornata_lega=4))
    assert v["frase"]["param"] == {"n": 9} and v["testo"] == FRASE.format(n=9)


def test_una_partita_rinviata_non_nasconde_la_sosta(tmp_path):
    """Una partita della 11 rinviata a dicembre non è la «fine» della 11 (regola unica del turno, turno.py): la sosta resta."""
    adesso = D(2026, 11, 12, 12)
    db = calendario(AUTUNNO, adesso)
    db.execute("UPDATE partite SET data = '2026-12-16 18:30', giocata = 0 WHERE giornata = 11 AND data = '2026-11-09 21:00'")
    ctx = NS(utente_id=1, rose=rose_del(tmp_path, D(2026, 11, 1)), scelte=tmp_path / "s.json", diario=tmp_path / "d.json",
             impostazioni_avvisi=None)
    voci = [v for v in da_fare.costruisci(db, Regole(), None, {"iniziata": True}, ctx, adesso=adesso) if v["tipo"] == "rose"]
    assert len(voci) == 1 and voci[0]["frase"]["param"] == {"n": 12}


# ---------------------------------------------------------------- date della lega in regole.json
def test_asta_invernale_dalle_regole(tmp_path):
    asta = Regole(asta_invernale={"dal": "2027-01-19", "al": "2027-01-20"})
    vecchie = D(2027, 1, 2)
    assert promemoria(tmp_path, GENNAIO, D(2027, 1, 19, 9), vecchie) is None                # senza la data: nessuna sosta, niente
    assert promemoria(tmp_path, GENNAIO, D(2027, 1, 18, 12), vecchie, asta) is None          # l'asta non è ancora cominciata
    v = promemoria(tmp_path, GENNAIO, D(2027, 1, 19, 9), vecchie, asta)
    assert v is not None and v["frase"]["param"] == {"n": 21}                                # la prima giornata dopo la fine dell'asta
    assert promemoria(tmp_path, GENNAIO, D(2027, 1, 23, 15), vecchie, asta) is None          # scaduta la 21
    assert promemoria(tmp_path, GENNAIO, D(2027, 1, 21, 12), D(2027, 1, 20, 18), asta) is None    # rose aggiornate durante l'asta


def test_asta_invernale_di_un_giorno_solo(tmp_path):
    asta = Regole(asta_invernale={"dal": "2027-01-18"})
    v = promemoria(tmp_path, GENNAIO, D(2027, 1, 18, 21), D(2027, 1, 2), asta)
    assert v is not None and v["frase"]["param"] == {"n": 21}


def test_le_finestre_di_scambio_della_lega_prendono_il_posto_delle_soste(tmp_path):
    vecchie = D(2026, 11, 1)
    nessuna = Regole(finestre_scambio=[])
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), vecchie, nessuna) is None
    una = Regole(finestre_scambio=[{"dal": "2026-11-13", "al": "2026-11-15"}])
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), vecchie, una) is None           # la sosta da sola non basta più
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 14, 12), vecchie, una)
    assert v is not None and v["frase"]["param"] == {"n": 12}
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 14, 12), D(2026, 11, 13, 20), una) is None


def test_finestre_solo_di_un_altra_stagione_valgono_le_soste(tmp_path):
    """Date dell'anno prima dimenticate in regole.json: per questa stagione la lega non ha indicato niente, quindi le soste."""
    vecchie_date = Regole(finestre_scambio=[{"dal": "2025-11-13", "al": "2025-11-15"}], asta_invernale={"dal": "2026-01-20"})
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), D(2026, 11, 1), vecchie_date)
    assert v is not None and v["frase"]["param"] == {"n": 12}
    assert promemoria(tmp_path, AUTUNNO, D(2026, 11, 4, 12), D(2026, 10, 1), vecchie_date) is None


def test_lega_senza_i_campi_nuovi_usa_le_soste_del_calendario(tmp_path):
    vecchio_file = asdict(Regole(nome_lega="Lega di prima"))
    for k in ("asta_invernale", "finestre_scambio"):
        vecchio_file.pop(k, None)
    regole = R.da_dict(vecchio_file)
    assert regole.asta_invernale is None and regole.finestre_scambio is None
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), D(2026, 11, 1), regole)
    assert v is not None and v["frase"]["param"] == {"n": 12}


# ---------------------------------------------------------------- inizio della stagione
def test_inizio_stagione_con_le_rose_della_stagione_prima(tmp_path):
    maggio = D(2026, 5, 20)
    v = promemoria(tmp_path, ESTATE, D(2026, 8, 20, 12), maggio)
    assert v is not None and v["frase"]["param"] == {"n": 1}
    assert promemoria(tmp_path, ESTATE, D(2026, 8, 20, 12), D(2026, 8, 18)) is None          # rose dell'asta di agosto
    assert promemoria(tmp_path, ESTATE, D(2026, 8, 25, 12), maggio) is None                  # scaduta la prima giornata


def test_inizio_stagione_con_la_lega_che_parte_dopo(tmp_path):
    tre = Regole(prima_giornata_lega=3)
    v = promemoria(tmp_path, ESTATE, D(2026, 8, 25, 12), D(2026, 5, 20), tre)
    assert v is not None and v["frase"]["param"] == {"n": 1}                                 # la giornata 1 della lega (3 di Serie A)
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 5, 12), D(2026, 9, 1), tre) is None       # asta fatta nella sosta


def test_senza_calendario_niente(tmp_path):
    assert promemoria(tmp_path, [], D(2026, 11, 12, 12), D(2026, 1, 1)) is None


# ---------------------------------------------------------------- regole.json: i campi nuovi si controllano
@pytest.mark.parametrize("campi", [
    {"asta_invernale": {"dal": "2027-01-20"}},
    {"asta_invernale": {"dal": "2027-01-20", "al": "2027-01-22"}},
    {"asta_invernale": {"dal": "2027-01-20", "al": None}},
    {"finestre_scambio": []},
    {"finestre_scambio": [{"dal": "2026-10-10", "al": "2026-10-16"}, {"dal": "2026-11-14"}]},
    {"asta_invernale": None, "finestre_scambio": None},
])
def test_date_della_lega_valide(campi):
    assert R.da_dict(asdict(Regole()) | campi).problemi() == []


@pytest.mark.parametrize("campi", [
    {"asta_invernale": "2027-01-20"},
    {"asta_invernale": {"al": "2027-01-20"}},
    {"asta_invernale": {"dal": "20/01/2027"}},
    {"asta_invernale": {"dal": "2027-02-30"}},
    {"asta_invernale": {"dal": 20270120}},
    {"asta_invernale": {"dal": "2027-01-20", "al": "2027-01-10"}},
    {"asta_invernale": {"dal": "2027-01-20", "fino": "2027-01-22"}},
    {"asta_invernale": {"dal": "2026-11-01", "al": "2027-03-01"}},
    {"finestre_scambio": {"dal": "2026-11-14"}},
    {"finestre_scambio": ["2026-11-14"]},
    {"finestre_scambio": [{"dal": "2026-11-14"}] * 100},                                     # troppe
])
def test_date_della_lega_sbagliate(campi):
    with pytest.raises(ValueError):
        R.da_dict(asdict(Regole()) | campi)


def test_la_lega_d_esempio_indica_le_date_nel_formato_giusto():
    esempio = R.carica(Path(__file__).resolve().parent.parent / "lega" / "esempio" / "regole.json")
    assert esempio.asta_invernale and esempio.problemi() == []
    assert esempio.finestre_scambio is None                       # di partenza le soste dal calendario


def test_un_client_vecchio_non_cancella_le_date_della_lega(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    r = c.get("/api/regole").json()
    assert r["asta_invernale"] is None and r["finestre_scambio"] is None                     # campi nuovi, facoltativi
    nuove = r | {"asta_invernale": {"dal": "2027-01-20"}, "finestre_scambio": [{"dal": "2026-11-14", "al": "2026-11-16"}]}
    assert c.put("/api/regole", json=nuove).status_code == 200
    vecchio = c.get("/api/regole").json() | {"nome_lega": "Dal client vecchio"}
    vecchio.pop("asta_invernale"), vecchio.pop("finestre_scambio")
    assert c.put("/api/regole", json=vecchio).status_code == 200
    r = c.get("/api/regole").json()
    assert r["nome_lega"] == "Dal client vecchio"
    assert r["asta_invernale"] == {"dal": "2027-01-20"} and r["finestre_scambio"] == [{"dal": "2026-11-14", "al": "2026-11-16"}]
    assert c.put("/api/regole", json=r | {"asta_invernale": {"dal": "domani"}}).status_code in (400, 422)
