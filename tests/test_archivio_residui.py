"""All'avvio l'archivio toglie le tabelle e le righe di cose dismesse (#609): le quote (decisione 0005) e la seconda fonte di
probabili. Una volta sola, senza toccare il resto. Archivio di prova in una cartella temporanea, dati inventati."""
import sqlite3

from fanta import archivio, fonti_attive, stato_dati, testi_legali


def _archivio_vecchio(f):
    """Un archivio come quelli sul server prima di #609: le tabelle di oggi più i residui."""
    archivio.apri(f).close()
    c = sqlite3.connect(f)
    c.execute("CREATE TABLE quote_giocatore (stagione TEXT, giornata INTEGER, calciatore_id INTEGER, quota REAL)")
    c.execute("INSERT INTO quote_giocatore VALUES ('2026-27', 10, 1, 2.5)")
    c.execute("CREATE TABLE IF NOT EXISTS probabili_fonte2 (stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, "
              "squadra TEXT, titolare INTEGER, percentuale REAL, segnale TEXT, link TEXT, pubblicato TEXT, rilevato TEXT)")
    c.execute("INSERT INTO probabili_fonte2 VALUES ('2026-27', 10, 'x', 1, 'casa', 1, NULL, 'titolare', 'l', 'p', 'r')")
    righe = [("aggiornamento", "2026-11-12T08:03:07"), ("calendario 2026-27", "2026-11-10T08:03:39"),
             ("quote-giocatore", "2026-10-30T15:01:50"), ("quote-giocatore 2026-27 g10", "2026-10-30T15:01:50"),
             ("crediti-giocatore 2026-10", "2026-10-30T15:01:50"), ("probabili-fonte2", "2026-11-12T08:03:04")]
    c.executemany("INSERT INTO aggiornamenti VALUES (?, ?, '')", righe)
    c.executemany("INSERT INTO controlli VALUES (?, ?, 'ok', 0, 'x', 't')",
                  [("2026-27", "somma_quote"), ("2025-26", "somma_quote"), ("2026-27", "partite_per_giornata")])
    c.commit()
    c.close()


def _tabelle(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_all_avvio_via_i_residui_delle_quote_e_della_seconda_fonte(tmp_path):
    f = tmp_path / "fanta.sqlite"
    _archivio_vecchio(f)
    for _ in range(2):                                         # la seconda apertura non trova più niente da togliere
        db = archivio.apri(f)
        try:
            assert not {"quote", "quote_giocatore", "probabili_fonte2"} & _tabelle(db)
            assert [r[0] for r in db.execute("SELECT cosa FROM aggiornamenti ORDER BY cosa")] == ["aggiornamento", "calendario 2026-27"]
            assert [tuple(r) for r in db.execute("SELECT stagione, nome FROM controlli")] == [("2026-27", "partite_per_giornata")]
        finally:
            db.close()


def test_un_archivio_nuovo_non_ha_la_tabella_della_seconda_fonte(tmp_path):
    db = archivio.apri(tmp_path / "nuovo.sqlite")
    try:
        assert "probabili_fonte2" not in _tabelle(db)
        assert set(stato_dati.ombra(db)) == {"partite_extra"}           # in ombra resta solo football-data
    finally:
        db.close()


def test_interruttori_e_testi_legali_solo_delle_fonti_che_si_usano(monkeypatch):
    assert set(fonti_attive.FONTI) == {"fantacalcio", "understat", "footballdata", "espn", "foto"}
    assert set(testi_legali.FONTI_TESTO) == {"fantacalcio", "understat", "footballdata", "espn"}
    for k in fonti_attive.FONTI:
        monkeypatch.setenv(f"FANTA_FONTE_{k.upper()}", "1")
    crediti = testi_legali.pagina("crediti")
    assert all(testi_legali.FONTI_TESTO[k].split(":")[0] in crediti for k in testi_legali.FONTI_TESTO)
