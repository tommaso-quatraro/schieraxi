"""D'estate (#608): dal 1° luglio il programma passa alla stagione nuova, ma per settimane le pagine delle fonti mostrano ancora la
vecchia o niente. Non sono guasti: il passo riesce senza dati e non apre l'avviso del «passo fermo». Un guasto vero resta un errore.
Dati inventati, nessuna richiesta in rete, ore fisse (niente orologio vero)."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from fanta import aggiorna, archivio, fonti_attive
from fanta.fonti import fantacalcio as fc

DATI = Path(__file__).parent / "dati"
LUGLIO = "2027-07-10T08:03:00"
VECCHIA, NUOVA = "2026-27", "2027-28"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _agg(db, monkeypatch, ora=LUGLIO, anno=2027):
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    righe = []
    return aggiorna.Aggiornamento(db, aggiorna.Stagione(anno), scrivi=righe.append), righe


def _partita(db, pid, stagione, giornata, data, giocata=0):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, 'casa', 'ospite', ?)",
               (pid, stagione, giornata, data, giocata))


def _probabili(giornata, partita, titolari=22):
    return giornata, [{"calciatore_id": 100 + i, "squadra": "casa", "partita_id": partita,
                       "stato": "titolare" if i < titolari else "panchina", "percentuale": 90.0, "in_dubbio": 0, "diffidato": 0,
                       "nota": None} for i in range(30)]


def _pagina(monkeypatch, giornata, righe):
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text=""))
    monkeypatch.setattr(aggiorna.fc, "leggi_probabili", lambda html: (giornata, [dict(r) for r in righe]))


def test_a_luglio_le_probabili_della_stagione_vecchia_non_sono_un_guasto(db, monkeypatch):
    _partita(db, 3801, VECCHIA, 38, "2027-05-23 20:45", giocata=1)
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    _pagina(monkeypatch, *_probabili(38, 3801))
    a, righe = _agg(db, monkeypatch)
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori == [] and "probabili" in a.riusciti
    assert db.execute("SELECT COUNT(*) FROM probabili").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM probabili_storia").fetchone()[0] == 0
    assert any(f"stagione {VECCHIA}" in r for r in righe)
    assert archivio.passi_fermi(db, datetime(2027, 8, 5, 9, 0)) == []


def test_probabili_di_partite_che_non_conosciamo_restano_un_errore(db, monkeypatch):
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    _pagina(monkeypatch, *_probabili(1, 9999))
    a, _ = _agg(db, monkeypatch)
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori and a.errori[0].startswith("probabili: ValueError: le probabili non corrispondono")


def test_giornata_lontana_senza_probabili_non_e_un_guasto(db, monkeypatch):
    """Ad agosto la pagina ha già la giornata 1 ma senza formazioni: con la prima partita fra più di 4 giorni è normale."""
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    _pagina(monkeypatch, *_probabili(1, 4001, titolari=0))
    a, righe = _agg(db, monkeypatch, ora="2027-08-15T08:03:00")
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori == [] and any("non ancora uscite" in r for r in righe)
    assert db.execute("SELECT COUNT(*) FROM probabili").fetchone()[0] == 0


def test_giornata_vicina_senza_probabili_e_un_errore(db, monkeypatch):
    """A meno di 4 giorni dalla prima partita una pagina senza titolari non è normale (pagina cambiata?): resta un errore."""
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    _pagina(monkeypatch, *_probabili(1, 4001, titolari=0))
    a, _ = _agg(db, monkeypatch, ora="2027-08-21T08:03:00")
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori and "probabili: ValueError: pagina probabili non riconosciuta" in a.errori[0]


def test_a_luglio_il_calendario_della_stagione_vecchia_non_e_un_guasto(db, monkeypatch):
    """Il sito mostra ancora la stagione vecchia: una richiesta sola, nessun errore, niente salvato."""
    chiamate = []
    html = (DATI / "calendario_1.html").read_text(encoding="utf-8")            # giornata 1 della stagione 2026-27
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *x, **k: chiamate.append(url) or SimpleNamespace(text=html))
    a, righe = _agg(db, monkeypatch)
    a._passo("calendario", a.calendario, "fantacalcio")
    assert a.errori == [] and chiamate == [fc.url_calendario(1)]
    assert db.execute("SELECT COUNT(*) FROM partite").fetchone()[0] == 0
    assert any(f"stagione {VECCHIA}" in r for r in righe)


def test_in_stagione_un_calendario_con_un_altra_stagione_e_un_errore(db, monkeypatch):
    """A stagione iniziata «un'altra stagione» nei collegamenti non è l'estate ma un cambio del sito (qui «2026-2027» al posto di
    «2026-27»): calendario, risultati e voti si fermerebbero senza avviso. Errore del passo."""
    for g in range(1, 12):
        _partita(db, 2600 + g, VECCHIA, g, f"2026-10-{g:02d} 15:00", giocata=1)
    html = (DATI / "calendario_1.html").read_text(encoding="utf-8").replace("/2026-27/", "/2026-2027/")
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text=html))
    a, _ = _agg(db, monkeypatch, ora="2026-11-12T08:03:00", anno=2026)
    a._passo("calendario", a.calendario, "fantacalcio")
    assert a.errori and "calendario: ValueError: giornata 1: trovate 0 partite" in a.errori[0]


def test_in_stagione_le_probabili_di_una_stagione_vecchia_sono_un_errore(db, monkeypatch):
    """Solo la stagione appena finita, o una stagione nuova non ancora iniziata, giustifica una pagina di un'altra stagione."""
    _partita(db, 2401, "2024-25", 38, "2025-05-25 20:45", giocata=1)
    _partita(db, 2601, VECCHIA, 1, "2026-08-23 18:30", giocata=1)
    _pagina(monkeypatch, *_probabili(38, 2401))
    a, _ = _agg(db, monkeypatch, ora="2026-11-12T08:03:00", anno=2026)
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori and "le probabili non corrispondono" in a.errori[0]


def test_tre_giorni_prima_senza_titolari_e_un_errore(db, monkeypatch):
    """Le probabili escono 3-4 giorni prima: a 72 ore dalla prima partita una pagina senza titolari è un guasto (soglia 96 ore)."""
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    _pagina(monkeypatch, *_probabili(1, 4001, titolari=0))
    a, _ = _agg(db, monkeypatch, ora="2027-08-19T18:30:00")
    a._passo("probabili", a.probabili, "fantacalcio")
    assert a.errori and "pagina probabili non riconosciuta" in a.errori[0]


def test_calendario_senza_partite_riconoscibili_resta_un_errore(db, monkeypatch):
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text="<html><body>niente</body></html>"))
    a, _ = _agg(db, monkeypatch)
    a._passo("calendario", a.calendario, "fantacalcio")
    assert a.errori and "trovate 0 partite" in a.errori[0]


def test_a_luglio_understat_senza_partite_non_e_un_guasto(db, monkeypatch):
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30")
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(content=b'{"dates": [], "players": []}'))
    a, righe = _agg(db, monkeypatch)
    a._passo("Understat", a.understat, "understat")
    assert a.errori == [] and any("non ancora iniziata" in r for r in righe)


def test_a_stagione_iniziata_understat_senza_partite_resta_un_errore(db, monkeypatch):
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30", giocata=1)
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(content=b'{"dates": [], "players": []}'))
    a, _ = _agg(db, monkeypatch, ora="2027-08-25T08:03:00")
    a._passo("Understat", a.understat, "understat")
    assert a.errori and "Understat non ha restituito partite" in a.errori[0]


def _non_trovato(url):
    r = requests.Response()
    r.status_code = 404
    r.url = url
    return r


def test_a_luglio_il_file_della_stagione_nuova_di_football_data_che_manca_non_e_un_guasto(db, monkeypatch):
    csv = (DATI / "football_data_extra.csv").read_bytes()

    def scarica(url, *a, **k):
        if "2728" in url:
            _non_trovato(url).raise_for_status()
        return SimpleNamespace(content=csv)
    monkeypatch.setattr(aggiorna.rete, "scarica", scarica)
    a, _ = _agg(db, monkeypatch)
    a.slug_noti = {"como", "sassuolo", "milan", "pisa"}
    a._passo("dati extra", a.dati_extra, "footballdata")
    assert a.errori == []
    _partita(db, 4001, NUOVA, 1, "2027-08-22 18:30", giocata=1)                 # a stagione iniziata lo stesso 404 è un errore
    db.execute("DELETE FROM partite_extra")
    a, _ = _agg(db, monkeypatch, ora="2027-08-25T08:03:00")
    a.slug_noti = {"como", "sassuolo", "milan", "pisa"}
    a._passo("dati extra", a.dati_extra, "footballdata")
    assert a.errori and "404" in a.errori[0]
