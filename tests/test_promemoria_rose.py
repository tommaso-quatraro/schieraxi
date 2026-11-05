"""Promemoria «aggiorna le rose» di Da fare (issue #334): compare solo dopo un momento di mercato della lega (asta estiva e asta
invernale, di partenza dal 1° al 21 settembre e dal 1° al 21 febbraio, 2-3 settimane dopo la chiusura del mercato; soste del
campionato o finestre di scambio indicate in regole.json) e solo se le rose non sono state aggiornate da quando è cominciato;
sparisce con l'aggiornamento o alla scadenza della prima giornata della lega dopo la fine del momento. Calendari e date inventati."""
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
# inverno inventato, una giornata a settimana e nessuna sosta
INVERNO = [(g, D(2027, 1, 9, 15) + timedelta(weeks=g - 19)) for g in range(19, 27)]          # dalla 19 (9/1) alla 26 (27/2)
# inizio della stagione inventato, una giornata a settimana dal 22/8 al 26/9 e nessuna sosta
ESTATE = [(g, D(2026, 8, 22, 18) + timedelta(weeks=g - 1)) for g in range(1, 7)]               # la 4 è sabato 12/9
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


# ---------------------------------------------------------------- aste: date di partenza e date della lega in regole.json
def test_asta_estiva_di_partenza_dopo_la_chiusura_del_mercato(tmp_path):
    """Lega che parte dalla giornata 4: l'asta si fa dopo la chiusura del mercato estivo, a Serie A già cominciata."""
    lega = Regole(prima_giornata_lega=4)
    agosto = D(2026, 8, 1)
    assert promemoria(tmp_path, ESTATE, D(2026, 8, 15, 12), D(2026, 5, 20), lega) is None    # metà agosto: niente
    v = promemoria(tmp_path, ESTATE, D(2026, 9, 10, 12), agosto, lega)
    assert v is not None and v["testo"] == FRASE.format(n=1)        # la lega non gioca senza rose: prima della sua giornata 1
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 1, 0, 1), agosto, lega) is not None
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 10, 12), D(2026, 9, 6), lega) is None     # rose aggiornate dopo l'asta
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 12, 18), agosto, lega) is None            # scaduta la giornata 1 della lega


def test_asta_estiva_di_partenza_quando_la_lega_comincia_con_la_serie_a(tmp_path):
    """Lega che gioca dalla giornata 1 (22/8): l'asta c'è stata prima, a settembre non si chiede niente."""
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 10, 12), D(2026, 8, 18)) is None
    assert promemoria(tmp_path, ESTATE, D(2026, 8, 20, 12), D(2026, 5, 20)) is None         # agosto: nessun momento di mercato


def test_asta_estiva_della_lega_vince_su_quella_di_partenza(tmp_path):
    lega = Regole(prima_giornata_lega=4, asta_estiva={"dal": "2026-08-24", "al": "2026-08-27"})
    agosto = D(2026, 8, 1)
    v = promemoria(tmp_path, ESTATE, D(2026, 8, 25, 12), agosto, lega)
    assert v is not None and v["frase"]["param"] == {"n": 1}
    assert promemoria(tmp_path, ESTATE, D(2026, 9, 10, 12), D(2026, 8, 28), lega) is None    # settembre non conta più
    sempre = Regole(asta_estiva={"dal": "2026-09-02", "al": "2026-09-05"})                   # anche con la lega già partita
    v = promemoria(tmp_path, ESTATE, D(2026, 9, 3, 12), agosto, sempre)
    assert v is not None and v["frase"]["param"] == {"n": 4}                                 # la 3 è il 5/9: dopo la fine, la 4


def test_asta_invernale_di_partenza_a_febbraio(tmp_path):
    gennaio = D(2027, 1, 25)
    assert promemoria(tmp_path, INVERNO, D(2027, 1, 31, 12), gennaio) is None               # non è ancora cominciata
    v = promemoria(tmp_path, INVERNO, D(2027, 2, 10, 12), gennaio)
    assert v is not None and v["frase"]["param"] == {"n": 26}        # copre tutto il periodo: la prima giornata dopo il 21/2
    assert promemoria(tmp_path, INVERNO, D(2027, 2, 10, 12), D(2027, 2, 3)) is None         # rose aggiornate
    assert promemoria(tmp_path, INVERNO, D(2027, 2, 27, 15), gennaio) is None               # scaduta la 26
    v = promemoria(tmp_path, INVERNO, D(2027, 2, 10, 12), gennaio, Regole(prima_giornata_lega=4))
    assert v["frase"]["param"] == {"n": 23}


def test_asta_invernale_della_lega_vince_su_quella_di_partenza(tmp_path):
    asta = Regole(asta_invernale={"dal": "2027-01-19", "al": "2027-01-20"})
    vecchie = D(2027, 1, 2)
    assert promemoria(tmp_path, INVERNO, D(2027, 1, 19, 9), vecchie) is None                # di partenza è a febbraio
    assert promemoria(tmp_path, INVERNO, D(2027, 1, 18, 12), vecchie, asta) is None          # l'asta non è ancora cominciata
    v = promemoria(tmp_path, INVERNO, D(2027, 1, 19, 9), vecchie, asta)
    assert v is not None and v["frase"]["param"] == {"n": 21}                                # la prima giornata dopo la fine dell'asta
    assert promemoria(tmp_path, INVERNO, D(2027, 1, 23, 15), vecchie, asta) is None          # scaduta la 21
    assert promemoria(tmp_path, INVERNO, D(2027, 1, 21, 12), D(2027, 1, 20, 18), asta) is None    # rose aggiornate durante l'asta
    assert promemoria(tmp_path, INVERNO, D(2027, 2, 10, 12), vecchie, asta) is None          # febbraio non conta più
    altra_stagione = Regole(asta_invernale={"dal": "2026-01-19"})                            # data dell'anno prima: vale febbraio
    assert promemoria(tmp_path, INVERNO, D(2027, 2, 10, 12), vecchie, altra_stagione) is not None


def test_asta_invernale_di_un_giorno_solo(tmp_path):
    asta = Regole(asta_invernale={"dal": "2027-01-18"})
    v = promemoria(tmp_path, INVERNO, D(2027, 1, 18, 21), D(2027, 1, 2), asta)
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
    for k in ("asta_estiva", "asta_invernale", "finestre_scambio"):
        vecchio_file.pop(k, None)
    regole = R.da_dict(vecchio_file)
    assert regole.asta_estiva is None and regole.asta_invernale is None and regole.finestre_scambio is None
    v = promemoria(tmp_path, AUTUNNO, D(2026, 11, 12, 12), D(2026, 11, 1), regole)
    assert v is not None and v["frase"]["param"] == {"n": 12}


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
    {"asta_estiva": {"dal": "2026-09-01", "al": "2026-09-21"}},
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
    {"asta_estiva": {"dal": "2026-09-21", "al": "2026-09-01"}},
    {"asta_estiva": ["2026-09-01"]},
    {"finestre_scambio": {"dal": "2026-11-14"}},
    {"finestre_scambio": ["2026-11-14"]},
    {"finestre_scambio": [{"dal": "2026-11-14"}] * 100},                                     # troppe
])
def test_date_della_lega_sbagliate(campi):
    with pytest.raises(ValueError):
        R.da_dict(asdict(Regole()) | campi)


def test_la_lega_d_esempio_indica_le_date_nel_formato_giusto():
    esempio = R.carica(Path(__file__).resolve().parent.parent / "lega" / "esempio" / "regole.json")
    assert esempio.asta_estiva and esempio.asta_invernale and esempio.problemi() == []
    assert esempio.finestre_scambio is None                       # di partenza le soste dal calendario


def test_un_client_vecchio_non_cancella_le_date_della_lega(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    r = c.get("/api/regole").json()
    assert r["asta_estiva"] is None and r["asta_invernale"] is None and r["finestre_scambio"] is None     # campi nuovi, facoltativi
    nuove = r | {"asta_estiva": {"dal": "2026-09-03"}, "asta_invernale": {"dal": "2027-01-20"},
                 "finestre_scambio": [{"dal": "2026-11-14", "al": "2026-11-16"}]}
    assert c.put("/api/regole", json=nuove).status_code == 200
    vecchio = c.get("/api/regole").json() | {"nome_lega": "Dal client vecchio"}
    vecchio.pop("asta_estiva"), vecchio.pop("asta_invernale"), vecchio.pop("finestre_scambio")
    assert c.put("/api/regole", json=vecchio).status_code == 200
    r = c.get("/api/regole").json()
    assert r["nome_lega"] == "Dal client vecchio"
    assert r["asta_estiva"] == {"dal": "2026-09-03"} and r["asta_invernale"] == {"dal": "2027-01-20"}
    assert r["finestre_scambio"] == [{"dal": "2026-11-14", "al": "2026-11-16"}]
    assert c.put("/api/regole", json=r | {"asta_invernale": {"dal": "domani"}}).status_code in (400, 422)
