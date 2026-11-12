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


def _leggi_righe(a, n, volte=1):
    """`volte` letture della giornata 11 con `n` righe; restituisce i messaggi d'errore (None = salvata)."""
    esiti = []
    for _ in range(volte):
        try:
            a._salva_voti(a.st, 11, _righe(n))
            esiti.append(None)
        except aggiorna.VotiCalati as e:
            esiti.append(str(e))
    return esiti


def test_una_riga_tolta_dalla_redazione_si_accetta_dopo_3_letture_uguali(db):
    righe = []
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=righe.append)
    a._salva_voti(a.st, 11, _righe(30))
    esiti = _leggi_righe(a, 29, volte=3)
    assert esiti[0] and esiti[1] and esiti[2] is None                         # le prime due no, la terza uguale sì
    assert "lettura 2 di 3" in esiti[1]
    assert _salvati(db) == 29
    assert any("accettata la pagina con 29 voti (prima 30) dopo 3 letture uguali" in r for r in righe)   # nel registro
    assert db.execute("SELECT COUNT(*) FROM voti_calati").fetchone()[0] == 0


def test_letture_diverse_ricominciano_il_conto(db):
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    assert all(_leggi_righe(a, 29, 2)) and all(_leggi_righe(a, 28, 2)) and all(_leggi_righe(a, 29, 2))
    assert _salvati(db) == 30


def test_un_calo_grande_resta_bloccato_e_si_vede(db):
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    esiti = _leggi_righe(a, 20, volte=6)
    assert all(esiti) and _salvati(db) == 30
    assert "lettura 6" in esiti[-1] and "troppi per accettarla da sola" in esiti[-1]


def test_il_conto_delle_letture_resta_anche_se_il_passo_non_riesce(db):
    """Il passo voti che non riesce annulla le sue scritture (rollback): il conto delle letture uguali deve restare."""
    a = _agg(db)
    a._salva_voti(a.st, 11, _righe(30))
    for _ in range(3):
        a._passo("voti", lambda: a._salva_voti(a.st, 11, _righe(29)))
    assert _salvati(db) == 29


# ---------------- giornate con i voti a metà (#658) ----------------
def _giornata_giocata(db, giornata, data, squadre_con_voti):
    """10 partite giocate il `data` (c0-t0 ... c9-t9); 14 voti per ognuna delle prime `squadre_con_voti` squadre, le altre senza."""
    squadre = []
    for i in range(10):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, 1)",
                   (giornata * 100 + i, ST, giornata, data, f"c{i}", f"t{i}"))
        squadre += [f"c{i}", f"t{i}"]
    for k, sq in enumerate(squadre[:squadre_con_voti]):
        for j in range(14):
            db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red) VALUES (?, ?, ?, 'x', ?, 'C', 6.0)",
                       (ST, giornata, giornata * 10000 + k * 100 + j, sq))


def test_giornata_con_i_voti_a_meta_si_riscarica_anche_dopo_4_giorni(db, monkeypatch):
    """I voti di una giornata arrivano a metà, poi la fonte non si legge per più di 4 giorni: la giornata ha già dei voti, tutte
    le partite giocate e l'ultima è vecchia, e non si riscaricava più (i giocatori delle altre partite restavano senza voto per
    sempre). Si riscarica finché una squadra di una partita giocata non ha nessun voto; una giornata completa no."""
    monkeypatch.setattr(aggiorna, "_ora", lambda: "2026-11-12T08:03:00")
    _giornata_giocata(db, 9, "2026-10-31 15:00", 20)
    _giornata_giocata(db, 10, "2026-11-07 15:00", 14)            # 14 squadre su 20 con i voti, ultima partita 5 giorni fa
    _giornata_giocata(db, 11, "2026-11-11 15:00", 20)            # finita da meno di 4 giorni: le correzioni arrivano dopo
    assert _agg(db)._giornate_voti_da_scaricare() == [10, 11]


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


def test_per_l_app_la_copia_vecchia_vale_subito_senza_richieste(tmp_path, monkeypatch):
    """Le rotte dell'app non aspettano il sito (con i tentativi di rete.scarica fino a 90 secondi): usano subito la copia che c'è.
    La rinnova il passo dell'aggiornamento (severo)."""
    f = tmp_path / "listone.json"
    _cache(f, 30)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(listone.rete, "scarica", lambda *a, **k: pytest.fail("rete usata da una rotta dell'app"))
    assert listone.carica(file_cache=f)[0][0].nome == "Finto A."


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
