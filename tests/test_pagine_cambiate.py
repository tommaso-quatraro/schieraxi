"""Pagine di Fantacalcio.it che cambiano forma (26/11/2026): un passo che non trova più squadre, date o ruoli deve fallire con un
errore che nomina la pagina, e non scrivere dati vuoti sopra quelli buoni. Pagina registrata in tests/dati/ modificata qui (come
farebbe il sito rinominando una classe o un attributo); nessuna richiesta in rete."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from fanta import aggiorna, archivio, listone

DATI = Path(__file__).parent / "dati"
# giornata 1 della stagione 2026-27, dieci partite; la prima è 17959 inter-monza, sabato 22/8 alle 18:30
BUONA = (DATI / "calendario_1.html").read_text(encoding="utf-8")
PRIMA = 17959


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _agg(db, monkeypatch, *pagine):
    """Un aggiornamento della stagione 2026-27 a cui il sito risponde con queste pagine, una per richiesta."""
    giro = iter(pagine)
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text=next(giro)))
    return aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)


def _partita(db, pid=PRIMA):
    return tuple(db.execute("SELECT casa, trasferta, data FROM partite WHERE id = ?", (pid,)).fetchone())


@pytest.mark.parametrize("cambiata", [
    BUONA.replace("team-link", "team-anchor"),                           # la classe dei link alle squadre rinominata
    BUONA.replace("team-name team-link", "team-name", 1),                # una sola squadra senza link
], ids=["tutte le squadre", "una squadra"])
def test_calendario_senza_squadre_ferma_il_passo_e_tiene_i_dati_buoni(db, monkeypatch, cambiata):
    a = _agg(db, monkeypatch, BUONA, cambiata)
    assert a._calendario_giornata(1) == 10
    with pytest.raises(ValueError, match="calendario 2026-27 giornata 1"):
        a._calendario_giornata(1)
    assert _partita(db) == ("inter", "monza", "2026-08-22 18:30")


@pytest.mark.parametrize("cambiata", [
    BUONA.replace('itemprop="startDate"', 'itemprop="dataInizio"'),     # nessuna partita ha più il giorno
    BUONA.replace('class="hours"', 'class="ore"'),                      # nessuna partita ha più l'ora
], ids=["giorno", "ora"])
def test_calendario_senza_le_date_gia_salvate_ferma_il_passo_e_tiene_i_dati_buoni(db, monkeypatch, cambiata):
    a = _agg(db, monkeypatch, BUONA, cambiata)
    a._calendario_giornata(1)
    with pytest.raises(ValueError, match="calendario 2026-27 giornata 1"):
        a._calendario_giornata(1)
    assert _partita(db) == ("inter", "monza", "2026-08-22 18:30")


def test_calendario_cambiato_e_un_errore_del_passo_che_nomina_il_calendario(db, monkeypatch):
    a = _agg(db, monkeypatch, BUONA, BUONA.replace("team-link", "team-anchor"))
    a._calendario_giornata(1)
    db.commit()                                                          # come `calendario()`, una giornata alla volta
    a._passo("risultati", lambda: a._calendario_giornata(1))
    assert len(a.errori) == 1 and "calendario 2026-27 giornata 1" in a.errori[0]
    assert _partita(db) == ("inter", "monza", "2026-08-22 18:30")


def test_una_partita_che_perde_la_data_e_un_rinvio_non_un_guasto(db, monkeypatch):
    """Una partita rinviata senza data nuova resta senza data nel calendario (rinvii.py la riconosce così): non è una pagina
    cambiata, finché le altre partite della giornata hanno ancora la loro."""
    rinviata = BUONA.replace('<meta content="2026-08-22" itemprop="startDate"/><span class="hours">18:30</span>', "", 1)
    a = _agg(db, monkeypatch, BUONA, rinviata)
    a._calendario_giornata(1)
    assert a._calendario_giornata(1) == 10
    assert _partita(db) == ("inter", "monza", None)


def test_giornata_ancora_senza_date_non_e_un_guasto(db, monkeypatch):
    """Le giornate lontane possono non avere ancora le date (#552): senza date già salvate il passo riesce."""
    a = _agg(db, monkeypatch, BUONA.replace('itemprop="startDate"', 'itemprop="dataInizio"'))
    assert a._calendario_giornata(1) == 10
    assert _partita(db) == ("inter", "monza", None)


# ---------------------------------------------------------------- listone
def _pagina_listone(attributo="data-filter-role-classic", ruoli=("p", "d", "c", "a")):
    righe = "".join(
        f'<tr class="player-row" {attributo}="{ruoli[i % len(ruoli)]}" data-filter-role-mantra="dc">'
        f'<th><a class="player-name player-link" href="https://www.fantacalcio.it/serie-a/squadre/inter/gioc-{i}/{i}">'
        f'<span>Gioc {i}</span></a></th><td data-col-key="sq">INT</td><td data-col-key="c_qi">5</td>'
        f'<td data-col-key="c_qa">7</td><td data-col-key="c_fvm">10</td></tr>'
        for i in range(1, 351))
    return f"<table><tbody>{righe}</tbody></table>"


def test_listone_con_i_quattro_ruoli():
    assert {c.ruolo for c in listone.analizza_html(_pagina_listone())} == {"P", "D", "C", "A"}


@pytest.mark.parametrize("pagina", [
    _pagina_listone(attributo="data-role-classic"),                      # attributo del ruolo rinominato: tutti senza ruolo
    _pagina_listone(ruoli=("por", "dif", "cen", "att")),                 # ruoli scritti in un altro modo
], ids=["attributo rinominato", "ruoli scritti in altro modo"])
def test_listone_senza_ruoli_riconoscibili_e_un_errore(pagina):
    with pytest.raises(ValueError, match="Listone"):
        listone.analizza_html(pagina)
