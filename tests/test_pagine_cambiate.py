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


def _giornata(g, html=BUONA):
    """La pagina registrata spostata alla giornata g, con altri numeri di partita (17959 diventa 27959 per la giornata 2)."""
    return html.replace("/calendario/1/", f"/calendario/{g}/").replace("/179", f"/{g}79")


def test_giornata_senza_le_date_non_ferma_le_altre_giornate(db, monkeypatch):
    """Una giornata intera senza le date di prima (pagina cambiata, o giornata rinviata senza data nuova: la pagina non lo
    distingue) tiene le sue date e il passo non riesce, ma le giornate dopo si aggiornano lo stesso."""
    monkeypatch.setattr(aggiorna, "GIORNATE", 2)
    pagine = {}
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *a, **k: SimpleNamespace(text=pagine[url]))
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)
    pagine.update({aggiorna.fc.url_calendario(1): _giornata(1), aggiorna.fc.url_calendario(2): _giornata(2)})
    for g in (1, 2):
        a._calendario_giornata(g)
    db.commit()
    pagine.update({aggiorna.fc.url_calendario(1): _giornata(1, BUONA.replace('itemprop="startDate"', 'itemprop="dataInizio"')),
                   aggiorna.fc.url_calendario(2): _giornata(2, BUONA.replace(">18:30<", ">20:45<", 1))})    # orario spostato
    a._passo("calendario", a.calendario, "fantacalcio")
    assert len(a.errori) == 1 and "calendario 2026-27 giornata 1" in a.errori[0]
    assert _partita(db, 17959) == ("inter", "monza", "2026-08-22 18:30")                 # date di prima tenute
    assert _partita(db, 27959) == ("inter", "monza", "2026-08-22 20:45")                 # la giornata dopo aggiornata


def test_giornata_ancora_senza_date_non_e_un_guasto(db, monkeypatch):
    """Le giornate lontane possono non avere ancora le date (#552): senza date già salvate il passo riesce."""
    a = _agg(db, monkeypatch, BUONA.replace('itemprop="startDate"', 'itemprop="dataInizio"'))
    assert a._calendario_giornata(1) == 10
    assert _partita(db) == ("inter", "monza", None)


# ---------------------------------------------------------------- listone
def _pagina_listone(attributo="data-filter-role-classic", ruoli=("p", "d", "c", "a"), senza_ruolo=0):
    """350 giocatori; i primi `senza_ruolo` con il ruolo vuoto."""
    righe = "".join(
        f'<tr class="player-row" {attributo}="{"" if i <= senza_ruolo else ruoli[i % len(ruoli)]}" data-filter-role-mantra="dc">'
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


def test_listone_pochi_giocatori_senza_ruolo_si_saltano_e_si_contano_nel_registro(caplog):
    """Stessa tolleranza dei voti: fino al 10% delle righe (35 su 350) si saltano, con una riga nel registro."""
    calciatori = listone.analizza_html(_pagina_listone(senza_ruolo=35))
    assert len(calciatori) == 315 and {c.ruolo for c in calciatori} == {"P", "D", "C", "A"}
    righe = [r.getMessage() for r in caplog.records if r.name == "fanta.listone"]
    assert len(righe) == 1 and "35" in righe[0]


def test_listone_oltre_la_soglia_dei_giocatori_senza_ruolo_e_un_errore():
    with pytest.raises(ValueError, match="Listone: 36 giocatori"):
        listone.analizza_html(_pagina_listone(senza_ruolo=36))
