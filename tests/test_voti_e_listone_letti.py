"""Dati letti davvero (#608): i voti di una giornata non calano mai rispetto a quelli salvati, le righe dei voti scartate si vedono,
il listone che non si legge durante l'aggiornamento è un errore (non la copia di ieri in silenzio). Dati inventati, niente rete."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from fanta import aggiorna, archivio, fonti_attive, listone
from fanta.fonti import fantacalcio as fc

ST = "2026-27"
VOTI_8 = (Path(__file__).parent / "dati" / "voti_8.html").read_text(encoding="utf-8")


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _righe(n, giornata=11):
    return [{"giornata": giornata, "calciatore_id": i, "nome": f"finto{i}", "squadra": "casa", "ruolo": "C", "voto_red": 6.0,
             "fv_red": 6.0, "voto_stat": 6.0, "fv_stat": 6.0, "voto_ita": 6.0, "fv_ita": 6.0, "gol": 0, "gol_subiti": 0, "autogol": 0,
             "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0,
             "subentrato": 0, "sostituito": 0} for i in range(n)]


def _agg(db):
    return aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)


def _salvati(db, giornata=11):
    return db.execute("SELECT COUNT(*) FROM voti WHERE stagione = ? AND giornata = ?", (ST, giornata)).fetchone()[0]


def test_voti_piu_o_uguali_sostituiscono_quelli_di_prima(db):
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    a._salva_voti(a.st, 11, _righe(31))
    assert _salvati(db) == 31


def test_voti_meno_di_prima_non_si_salvano_e_il_passo_lo_dice(db):
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    with pytest.raises(ValueError, match="giornata 11: la pagina ha 20 voti, prima erano 30"):
        a._salva_voti(a.st, 11, _righe(20))
    assert _salvati(db) == 30


def test_pagina_dei_voti_vuota_con_voti_gia_salvati_e_un_errore(db):
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    with pytest.raises(ValueError, match="la pagina ha 0 voti, prima erano 30"):
        a._salva_voti(a.st, 11, [])
    assert _salvati(db) == 30


def test_pagina_dei_voti_vuota_senza_voti_salvati_non_e_un_errore(db):
    a = _agg(db)
    a._salva_voti(a.st, 12, [])                  # voti non ancora usciti
    assert _salvati(db, 12) == 0


def test_il_passo_voti_salva_le_altre_giornate_e_poi_dice_quella_calata(db, monkeypatch):
    """Una giornata calata non ferma le altre: si salvano, e alla fine il passo non riesce con il motivo."""
    for g in (10, 11):
        for i in range(10):
            db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2099-01-01 15:00', "
                       "?, ?, 1)", (g * 100 + i, ST, g, f"c{i}", f"t{i}"))
    a = _agg(db)
    a._salva_voti(a.st, 10, _righe(30, 10))
    a._salva_voti(a.st, 11, _righe(30, 11))
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *x, **k: SimpleNamespace(text=url))
    monkeypatch.setattr(aggiorna.fc, "leggi_voti_e_scarti", lambda html, g: (_righe(20 if g == 10 else 35, g), 0))
    with pytest.raises(ValueError, match="giornata 10"):
        a.voti()
    assert _salvati(db, 10) == 30 and _salvati(db, 11) == 35


# ---------------- righe dei voti scartate ----------------
def test_righe_dei_voti_senza_i_tre_voti_si_contano():
    righe, scartate = fc.leggi_voti_e_scarti(VOTI_8, 8)
    assert (len(righe), scartate) == (8, 0)
    rotta = VOTI_8.replace('class="player-fanta-grade"', 'class="altro"', 1)          # una riga senza fantavoti
    righe, scartate = fc.leggi_voti_e_scarti(rotta, 8)
    assert (len(righe), scartate) == (7, 1)
    assert len(fc.leggi_voti(rotta, 8)) == 7                                             # la funzione di sempre non cambia


def test_troppe_righe_scartate_sono_un_errore():
    tutta = VOTI_8.replace('class="player-fanta-grade"', 'class="altro"')               # la pagina è cambiata: nessuna riga si legge
    with pytest.raises(ValueError, match="8 righe su 8 senza i tre voti"):
        fc.leggi_voti_e_scarti(tutta, 8)


# ---------------- listone ----------------
def _cache(f, ore_fa):
    scaricato = (datetime.now() - timedelta(hours=ore_fa)).isoformat(timespec="seconds")
    c = listone.Calciatore(1, "Finto A.", "C", "C", "CAS", "casa", 10, 10, 100)
    f.write_text(json.dumps({"scaricato": scaricato, "calciatori": [c.__dict__]}), encoding="utf-8")


def _rete_rotta(*a, **k):
    raise requests.ConnectionError("rete giù")


def test_listone_non_letto_durante_l_aggiornamento_e_un_errore(tmp_path, monkeypatch):
    f = tmp_path / "listone.json"
    _cache(f, 30)                                                       # copia di ieri
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(listone.rete, "scarica", _rete_rotta)
    assert listone.carica(file_cache=f)[0][0].nome == "Finto A."         # per l'app: meglio il listone di ieri che niente
    with pytest.raises(requests.ConnectionError):
        listone.carica(file_cache=f, severo=True)                       # per l'aggiornamento: l'errore si vede


def test_listone_fresco_non_fa_richieste_neanche_severo(tmp_path, monkeypatch):
    f = tmp_path / "listone.json"
    _cache(f, 2)
    monkeypatch.setattr(listone.rete, "scarica", lambda *a, **k: pytest.fail("rete usata"))
    assert listone.carica(file_cache=f, severo=True)[0][0].nome == "Finto A."


def test_il_listone_passa_da_rete_scarica(tmp_path, monkeypatch):
    """Pausa tra le richieste e nuovi tentativi come le altre pagine di Fantacalcio.it."""
    chiamate = []
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(listone.rete, "scarica", lambda url, *a, **k: chiamate.append(url) or SimpleNamespace(text="<html></html>"))
    with pytest.raises(ValueError, match="trovati solo 0 giocatori"):
        listone.carica(aggiorna=True, file_cache=tmp_path / "listone.json", severo=True)
    assert chiamate == [listone.URL]


def test_il_passo_listone_dell_aggiornamento_non_usa_la_copia_vecchia(db, monkeypatch):
    chiesto = {}
    monkeypatch.setattr(aggiorna.listone, "carica", lambda **k: chiesto.update(k) or _rete_rotta())
    a = _agg(db)
    a._passo("listone", a.listone)
    assert chiesto.get("severo") is True and a.errori and a.errori[0].startswith("listone: ConnectionError")
