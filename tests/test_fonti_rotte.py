"""Fonti che rispondono male (prove avversarie del 1/11/2026, giro di stabilità del server).

- Un solo campo illeggibile (punteggio «-» di una partita finita, percentuale «n.d.» di una probabile, bonus «1.0») faceva
  fallire tutta la pagina: niente calendario, niente probabili o niente voti per quel giro.
- Se il calendario non si aggiorna per giorni (fonte giù o pagina cambiata), la giornata già giocata restava «da giocare» per sempre
  quando aveva ancora 5 o più partite non segnate come finite: consigli e scadenza di una giornata passata."""
import sqlite3
from datetime import datetime
from pathlib import Path

from fanta import consigli
from fanta.fonti import fantacalcio as fc

DATI = Path(__file__).parent / "dati"


def _leggi(nome):
    return (DATI / nome).read_text(encoding="utf-8")


def test_calendario_punteggio_illeggibile_non_ferma_la_pagina():
    html = _leggi("calendario_1.html").replace('class="score-home">4<', 'class="score-home">-<', 1)
    partite = fc.leggi_calendario(html, 1, "2026-27")
    assert len(partite) == 10
    p = next(x for x in partite if x["id"] == 17959)
    # punteggio non leggibile: la partita resta «da finire», il prossimo aggiornamento la completa
    assert (p["gol_casa"], p["gol_trasferta"], p["giocata"]) == (None, None, 0)
    assert sum(x["giocata"] for x in partite) == 9


def test_probabili_percentuale_illeggibile_non_ferma_la_pagina():
    html = _leggi("probabili.html").replace('aria-valuenow="75"', 'aria-valuenow="n.d."')
    giornata, righe = fc.leggi_probabili(html)
    per_id = {r["calciatore_id"]: r for r in righe}
    assert giornata == 9 and per_id[4236]["stato"] == "titolare" and per_id[4236]["percentuale"] is None
    assert sum(r["stato"] == "titolare" for r in righe) == 22


def test_voti_bonus_scritto_in_altro_modo_non_ferma_la_pagina():
    normale = fc.leggi_voti(_leggi("voti_8.html"), 8)
    html = _leggi("voti_8.html").replace('player-bonus cell malus" data-value="0"', 'player-bonus cell malus" data-value="n.d."')
    html = html.replace('player-bonus cell bonus" data-value="2"', 'player-bonus cell bonus" data-value="2.0"')
    righe = fc.leggi_voti(html, 8)
    assert len(righe) == len(normale)
    assert {r["calciatore_id"]: r["gol"] for r in righe} == {r["calciatore_id"]: r["gol"] for r in normale}
    assert 2 in {r["gol"] for r in righe}


ST = "2026-27"


def _db(giornate):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,?)",
                   [(ST, g, d, f"c{g}{i}", f"t{g}{i}", gi) for g, partite in giornate.items() for i, (d, gi) in enumerate(partite)])
    return db


G9 = [("2026-10-27 18:30", 0), ("2026-10-27 20:45", 0), ("2026-10-27 20:45", 0), ("2026-10-28 18:30", 0), ("2026-10-28 18:30", 0),
      ("2026-10-28 18:30", 0), ("2026-10-28 20:45", 0), ("2026-10-28 20:45", 0), ("2026-10-29 18:30", 0), ("2026-10-29 20:45", 0)]
G10 = [("2026-10-31 15:00", 0), ("2026-10-31 18:00", 0), ("2026-10-31 20:45", 0), ("2026-11-01 12:30", 0), ("2026-11-01 15:00", 0),
       ("2026-11-01 15:00", 0), ("2026-11-01 18:00", 0), ("2026-11-01 20:45", 0), ("2026-11-02 18:30", 0), ("2026-11-02 20:45", 0)]


def test_calendario_fermo_da_giorni_non_tiene_ferma_una_giornata_gia_giocata():
    """Caso vero dell'archivio del PC il 1/11/2026: calendario non aggiornato dal 26/10, giornata 9 (27-29/10) ancora tutta «da giocare»."""
    assert consigli.prossima_giornata(_db({9: G9, 10: G10}), ST, datetime(2026, 10, 30, 10, 0)) == 10
    assert consigli.prossima_giornata(_db({9: G9, 10: G10}), ST, datetime(2026, 11, 1, 10, 0)) == 10


def test_giornata_appena_giocata_senza_risultati_resta_per_mezza_giornata():
    # mercoledì sera: la giornata 9 è in corso o appena finita e i risultati non sono ancora arrivati
    assert consigli.prossima_giornata(_db({9: G9, 10: G10}), ST, datetime(2026, 10, 28, 23, 0)) == 9
    assert consigli.prossima_giornata(_db({9: G9, 10: G10}), ST, datetime(2026, 10, 30, 8, 0)) == 9      # 12 ore dopo l'ultima
    assert consigli.prossima_giornata(_db({9: G9, 10: G10}), ST, datetime(2026, 10, 27, 12, 0)) == 9      # prima che inizi


def test_partite_senza_data_tengono_aperta_la_giornata():
    """Una giornata ancora tutta senza date (calendario non ancora fissato) resta da giocare, anche se il calendario è fermo."""
    senza_date = [(None, 0)] * 10
    assert consigli.prossima_giornata(_db({9: senza_date, 10: G10}), ST, datetime(2026, 11, 1, 10, 0)) == 9


def test_in_una_giornata_con_le_date_le_partite_senza_data_sono_rinviate():
    """Con le date, le partite senza data sono rinviate (rinvii.py) e non tengono aperta la giornata, quante che siano (#659):
    prima 6 partite senza data tenevano la giornata 9 da giocare finché il calendario non dava loro una data."""
    senza_data = [(None, 0)] * 6 + G9[6:]
    assert consigli.prossima_giornata(_db({9: senza_data, 10: G10}), ST, datetime(2026, 11, 1, 10, 0)) == 10
