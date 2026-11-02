"""probabili_storia: ogni rilevazione delle probabili resta, con la sua ora; `probabili` si comporta come prima."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from fanta import aggiorna, archivio
from fanta.fonti import fantacalcio as fc

HTML = (Path(__file__).parent / "dati" / "probabili.html").read_text(encoding="utf-8")


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    giornata, righe = fc.leggi_probabili(HTML)
    for pid in {r["partita_id"] for r in righe}:
        d.execute("INSERT INTO partite (id, stagione, giornata, giocata) VALUES (?, '2026-27', ?, 0)", (pid, giornata))
    d.commit()
    yield d, giornata, len(righe)
    d.close()


def _aggiorna(db, monkeypatch, ora):
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text=HTML))
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None).probabili()
    db.commit()


def test_la_tabella_c_e_e_si_riempie(db, monkeypatch):
    d, giornata, n = db
    _aggiorna(d, monkeypatch, "2026-10-30T08:00:00")
    assert d.execute("SELECT COUNT(*) FROM probabili_storia").fetchone()[0] == n
    assert d.execute("SELECT COUNT(*) FROM probabili").fetchone()[0] == n


def test_ogni_rilevazione_resta_con_la_sua_ora_e_probabili_tiene_l_ultima(db, monkeypatch):
    d, giornata, n = db
    _aggiorna(d, monkeypatch, "2026-10-30T08:00:00")
    _aggiorna(d, monkeypatch, "2026-10-30T13:00:00")
    # comportamento di prima: una sola rilevazione per giornata, l'ultima
    assert d.execute("SELECT COUNT(*), MIN(rilevato) FROM probabili").fetchone()[:] == (n, "2026-10-30T13:00:00")
    # in più: tutte le rilevazioni
    ore = [r[0] for r in d.execute("SELECT DISTINCT rilevato FROM probabili_storia ORDER BY 1")]
    assert ore == ["2026-10-30T08:00:00", "2026-10-30T13:00:00"]
    assert d.execute("SELECT COUNT(*) FROM probabili_storia").fetchone()[0] == 2 * n


def test_colonne_uguali(tmp_path):
    d = archivio.apri(tmp_path / "c.sqlite")
    try:
        a = [r[1] for r in d.execute("PRAGMA table_info(probabili)")]
        b = [r[1] for r in d.execute("PRAGMA table_info(probabili_storia)")]
        assert a == b
    finally:
        d.close()


def test_archivio_vecchio_riceve_la_tabella_senza_perdere_nulla(tmp_path):
    """Un archivio creato prima di questa versione (senza probabili_storia) si apre e si completa, i dati restano."""
    import sqlite3
    f = tmp_path / "vecchio.sqlite"
    c = sqlite3.connect(f)
    c.execute("CREATE TABLE probabili (stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, squadra TEXT,"
              " partita_id INTEGER, stato TEXT, percentuale REAL, in_dubbio INTEGER, diffidato INTEGER, nota TEXT,"
              " rilevato TEXT, PRIMARY KEY (stagione, giornata, fonte, calciatore_id))")
    c.execute("INSERT INTO probabili VALUES ('2026-27', 9, 'fantacalcio', 1, 'x', 1, 'titolare', 90, 0, 0, NULL, 't')")
    c.commit()
    c.close()
    d = archivio.apri(f)
    try:
        assert d.execute("SELECT COUNT(*) FROM probabili").fetchone()[0] == 1
        assert d.execute("SELECT COUNT(*) FROM probabili_storia").fetchone()[0] == 0
    finally:
        d.close()
