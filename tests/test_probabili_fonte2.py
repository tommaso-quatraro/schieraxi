"""Seconda fonte di probabili (feed Sosfanta) in ombra: lettore, classificazione prudente, abbinamento nomi, raccolta e misura.
Nessuna chiamata di rete: feed finto in tests/dati."""
from datetime import datetime
from pathlib import Path

import pytest

from fanta import archivio, nomi, probabili_fonte2 as pf2, stato_dati
from fanta.fonti import sosfanta
from fanta.listone import Calciatore

FEED = (Path(__file__).parent / "dati" / "sosfanta_feed.xml").read_bytes()
CALC = [Calciatore(1, "Rossetti A.", "C", "C", "MIL", "milan", 20, 20, 600), Calciatore(2, "Gallo", "D", "D", "LAZ", "lazio", 8, 8, 200),
        Calciatore(3, "Pavone S.", "D", "D", "MIL", "milan", 12, 12, 300), Calciatore(4, "Torrisi F.", "D", "D", "MIL", "milan", 12, 12, 300),
        Calciatore(5, "Magnani M.", "P", "P", "MIL", "milan", 20, 20, 500), Calciatore(6, "Leoni R.", "A", "A", "MIL", "milan", 28, 28, 700),
        Calciatore(7, "Dumini D.", "D", "D", "INT", "inter", 15, 15, 400), Calciatore(8, "Barile N.", "C", "C", "INT", "inter", 22, 22, 600)]
ADESSO = datetime(2026, 10, 30, 12, 0)


def test_leggi_feed_salta_voci_senza_data():
    voci = sosfanta.leggi_feed(FEED)
    assert [v["link"].rsplit("/", 2)[-2] for v in voci] == ["prova-uno", "prova-due", "mercato"]
    assert voci[0]["pubblicato"] == "2026-10-29T15:15:14"
    assert "Rossetti" in voci[0]["grassetti"] and "Milan" in voci[0]["categorie"]
    assert [sosfanta.e_utile(v) for v in voci] == [True, True, False]


@pytest.mark.parametrize("frase,atteso", [
    ("Leoni out per un problema muscolare.", "fuori"),
    ("Dumini salta il derby.", "fuori"),
    ("Oggi in gruppo Rossetti e Gallo.", None),                   # recupero: nessun segnale
    ("Rossetti ritrova la squadra ma e' ko in allenamento.", None),   # misto: prudenza
    ("Ballottaggio tra Pavone e Torrisi (60%).", "dubbio"),
    ("Magnani sara titolare.", "titolare"),
    ("Barile e' dal 1' e poi in dubbio.", "dubbio"),         # dubbio batte titolare
    ("Parla Sky.", None),
])
def test_classifica_frase(frase, atteso):
    assert sosfanta.classifica_frase(frase) == atteso


def test_segnali_della_prima_voce():
    s = {x["nome"]: x for x in sosfanta.segnali(sosfanta.leggi_feed(FEED)[0])}
    assert set(s) == {"Pavone", "Torrisi", "Magnani", "Leoni"}
    assert s["Pavone"]["segnale"] == "dubbio" and s["Pavone"]["percentuale"] == 60.0
    assert s["Magnani"]["segnale"] == "titolare" and s["Leoni"]["segnale"] == "fuori"


def test_titoletti_in_grassetto_non_sono_nomi():
    assert sosfanta._nome_plausibile("OSVALDI CON LA JUVE") is None
    assert sosfanta._nome_plausibile("Milan,") == "Milan"
    assert sosfanta._nome_plausibile("PANDOLFI") == "PANDOLFI"
    assert sosfanta._nome_plausibile("Dopo 3 giornate di stop") is None
    assert sosfanta._nome_plausibile("Alta frequenza di infortuni muscolari recenti") is None


def test_abbina_non_prende_squadre_e_rispetta_la_squadra():
    ind = nomi.Indice(CALC)
    assert pf2.abbina(ind, "Magnani", "milan") == 5
    assert pf2.abbina(ind, "Milan", None) is None                 # e' una squadra
    assert pf2.abbina(ind, "Sconosciuto", None) is None


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    d.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (1, '2026-27', 9, '2026-10-26 20:45', 'inter', 'roma', 1)")
    d.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (2, '2026-27', 10, '2026-10-31 20:45', 'inter', 'milan', 0)")
    yield d
    d.close()


def test_raccogli_scrive_in_ombra_una_volta_e_rispetta_l_intervallo(db):
    e = pf2.raccogli(db, "2026-27", CALC, ADESSO, scarica=lambda: FEED)
    assert e["righe"] > 0 and e["motivo"] == ""
    rig = {r["calciatore_id"]: r for r in db.execute("SELECT * FROM probabili_fonte2")}
    assert rig[6]["segnale"] == "fuori" and rig[6]["titolare"] == 0 and rig[6]["giornata"] == 10
    assert rig[5]["titolare"] == 1 and rig[3]["titolare"] is None and rig[7]["segnale"] == "fuori"
    assert 1 not in rig and 2 not in rig                           # Rossetti e Gallo: solo recuperi o voce non utile
    n = db.execute("SELECT COUNT(*) FROM probabili_fonte2").fetchone()[0]
    chiamate = []
    e2 = pf2.raccogli(db, "2026-27", CALC, ADESSO.replace(minute=10), scarica=lambda: chiamate.append(1) or FEED)
    assert e2["motivo"] and not chiamate                           # meno di 30 minuti: nessuna richiesta
    e3 = pf2.raccogli(db, "2026-27", CALC, ADESSO.replace(hour=13), scarica=lambda: FEED)
    assert e3["righe"] == 0 and db.execute("SELECT COUNT(*) FROM probabili_fonte2").fetchone()[0] == n   # niente doppioni


def test_articoli_prima_dell_ultima_partita_sono_ignorati(db):
    db.execute("UPDATE partite SET data = '2026-10-29 21:00' WHERE id = 1")      # il feed e' del 29 alle 15-16: vecchio
    e = pf2.raccogli(db, "2026-27", CALC, ADESSO, scarica=lambda: FEED)
    assert e["righe"] == 0


def test_senza_giornate_da_giocare_non_chiede_nulla(db):
    db.execute("UPDATE partite SET giocata = 1")
    chiamate = []
    e = pf2.raccogli(db, "2026-27", CALC, ADESSO, scarica=lambda: chiamate.append(1) or FEED)
    assert e["motivo"] and not chiamate


def _riga_fonte2(db, g, c, segnale, pub, ril):
    db.execute("INSERT INTO probabili_fonte2 VALUES ('2026-27', ?, 'sosfanta', ?, 'x', ?, NULL, ?, ?, ?, ?)",
               (g, c, {"fuori": 0, "titolare": 1}.get(segnale), segnale, f"https://x/{g}/{c}", pub, ril))


def test_stato_dati_mostra_la_fonte(db):
    _riga_fonte2(db, 10, 5, "titolare", "2026-10-29T15:00:00", "2026-10-30T12:00:00")
    o = stato_dati.ombra(db)["probabili_fonte2"]
    assert o == {"righe": 1, "ultima": "2026-10-30T12:00:00", "giornate": 1}
