"""Guasti delle fonti che si vedono (#608): ogni passo dell'aggiornamento ha il suo ultimo successo, la riga generale non fa sembrare
freschi i dati di un passo che non riesce, la salute avvisa per nome del passo fermo da più di 24 ore, una pagina web al posto dei
dati dà un errore leggibile. Archivi temporanei, dati inventati, nessuna richiesta in rete."""
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from fanta import aggiorna, archivio, fonti_attive, funzioni, salute, stato_dati
from fanta.fonti import understat as us

ST = "2026-27"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _agg(db, monkeypatch, ora, righe=None):
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    return aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=(righe if righe is not None else []).append)


def _riga(db, cosa):
    r = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = ?", (cosa,)).fetchone()
    return None if r is None else (r[0], json.loads(r[1]) if r[1] else None)


def _rotto():
    raise ValueError("pagina strana")


def test_un_passo_riuscito_segna_il_suo_ultimo_successo(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("probabili", lambda: None)
    assert _riga(db, "probabili") == ("2026-11-02T08:03:00", None)


def test_un_passo_che_non_riesce_tiene_l_ultimo_successo_e_dice_da_quando(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    quando, d = _riga(db, "understat")
    assert quando == "2026-11-01T21:03:00"
    assert d == {"errore": "ValueError: pagina strana", "dal": "2026-11-02T08:03:00", "ultimo": "2026-11-02T08:03:00"}
    righe = []
    a = _agg(db, monkeypatch, "2026-11-04T13:03:00", righe)
    a._passo("Understat", _rotto)
    quando, d = _riga(db, "understat")
    assert quando == "2026-11-01T21:03:00" and d["dal"] == "2026-11-02T08:03:00" and d["ultimo"] == "2026-11-04T13:03:00"
    # nell'errore della corsa (riga generale, registro, avviso) c'è da quando non riesce e l'ultimo successo
    assert a.errori[0].startswith("Understat: ValueError: pagina strana")
    assert "non riesce dal 02/11 alle 08:03" in a.errori[0] and "ultimo riuscito il 01/11 alle 21:03" in a.errori[0]
    assert any("non riesce dal 02/11" in r for r in righe)
    _agg(db, monkeypatch, "2026-11-05T08:03:00")._passo("Understat", lambda: None)
    assert _riga(db, "understat") == ("2026-11-05T08:03:00", None)


def test_un_passo_mai_riuscito_ha_l_ora_vuota(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("listone", _rotto)
    quando, d = _riga(db, "listone")
    assert quando is None and d["dal"] == "2026-11-02T08:03:00"


def test_solo_i_passi_seguiti_hanno_una_riga(db, monkeypatch):
    a = _agg(db, monkeypatch, "2026-11-02T08:03:00")
    a._passo("risultati 11", lambda: None)
    a._passo("voti 2025-26", _rotto)
    assert db.execute("SELECT COUNT(*) FROM aggiornamenti").fetchone()[0] == 0


def test_un_passo_spento_non_resta_in_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto, "understat")
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    _agg(db, monkeypatch, "2026-11-02T13:03:00")._passo("Understat", _rotto, "understat")
    assert _riga(db, "understat") == (None, None)
    assert archivio.passi_fermi(db, datetime(2026, 11, 10, 8, 0)) == []


def _tutti(monkeypatch, riusciti: set[str]):
    """esegui() con passi finti: quelli in `riusciti` vanno, gli altri si rompono."""
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(funzioni, "acceso", lambda nome: True)
    for metodo in ("listone", "calendario", "voti", "probabili", "probabili_fonte2", "understat", "dati_extra", "controlli"):
        monkeypatch.setattr(aggiorna.Aggiornamento, metodo,
                            (lambda self: None) if metodo in riusciti else (lambda self: _rotto()))


def test_la_riga_generale_non_avanza_se_nessun_passo_dei_dati_riesce(db, monkeypatch):
    archivio.segna(db, "aggiornamento", "2026-11-01T21:03:00", "[]")
    db.commit()
    _tutti(monkeypatch, {"controlli"})
    errori = _agg(db, monkeypatch, "2026-11-02T08:03:00").esegui()
    quando, dettaglio = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    assert quando == "2026-11-01T21:03:00"                    # i dati sono ancora quelli di ieri sera
    assert json.loads(dettaglio) == errori and len(errori) >= 5


def test_la_riga_generale_avanza_se_un_passo_dei_dati_riesce(db, monkeypatch):
    archivio.segna(db, "aggiornamento", "2026-11-01T21:03:00", "[]")
    db.commit()
    _tutti(monkeypatch, {"probabili", "controlli"})
    _agg(db, monkeypatch, "2026-11-02T08:03:00").esegui()
    quando, dettaglio = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    assert quando == "2026-11-02T08:03:00" and any(e.startswith("Understat:") for e in json.loads(dettaglio))


def test_passi_fermi_da_piu_di_24_ore_dal_primo_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("voti", lambda: None)
    assert archivio.passi_fermi(db, datetime(2026, 11, 3, 8, 0)) == []                    # 24 ore dal primo errore: non ancora
    fermi = archivio.passi_fermi(db, datetime(2026, 11, 3, 9, 0))
    assert [(p["passo"], p["ultimo_successo"], p["dal"]) for p in fermi] == [("understat", "2026-11-01T21:03:00", "2026-11-02T08:03:00")]


def test_una_fonte_riaccesa_non_e_subito_ferma(db, monkeypatch):
    """Spenta apposta per 16 giorni e riaccesa: al primo errore non è «ferma da 16 giorni» (niente avviso subito); lo diventa solo
    dopo 24 ore di errori di fila."""
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto, "understat")
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    _agg(db, monkeypatch, "2026-11-18T08:03:00")._passo("Understat", _rotto, "understat")
    assert archivio.passi_fermi(db, datetime(2026, 11, 18, 9, 0)) == []
    _agg(db, monkeypatch, "2026-11-19T08:03:00")._passo("Understat", _rotto, "understat")
    assert [p["passo"] for p in archivio.passi_fermi(db, datetime(2026, 11, 19, 9, 0))] == ["understat"]


def test_passo_mai_riuscito_fermo_dal_primo_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("probabili", _rotto)
    assert archivio.passi_fermi(db, datetime(2026, 11, 3, 7, 0)) == []
    assert [p["passo"] for p in archivio.passi_fermi(db, datetime(2026, 11, 3, 9, 0))] == ["probabili"]


def test_la_salute_avvisa_per_nome_del_passo_fermo_e_ripete_ogni_24_ore(db, monkeypatch, tmp_path):
    archivio.segna(db, "aggiornamento", "2026-11-04T08:03:00", "[]")       # la corsa gira: il resto arriva
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    f = tmp_path / "salute.json"
    problemi = salute.controlla(db, datetime(2026, 11, 4, 9, 0), f, manda, lambda: True)
    assert len(problemi) == 1 and "«understat»" in problemi[0] and "da 2 giorni" in problemi[0] and len(mandati) == 1
    salute.controlla(db, datetime(2026, 11, 4, 22, 0), f, manda, lambda: True)
    assert len(mandati) == 1                                                  # dopo 13 ore no
    salute.controlla(db, datetime(2026, 11, 5, 9, 30), f, manda, lambda: True)
    assert len(mandati) == 2                                                  # dopo 24 ore sì, finché dura
    _agg(db, monkeypatch, "2026-11-05T13:03:00")._passo("Understat", lambda: None)
    assert salute.controlla(db, datetime(2026, 11, 5, 13, 10), f, manda, lambda: True) == []


def test_stato_dei_dati_mostra_il_passo_fermo_con_l_ora_vera(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 4, 9, 0))
    voce = next(a for a in r["aggiornamenti"] if a["cosa"] == "understat")
    assert voce["quando"] == "2026-11-01T21:03:00"                            # l'ultimo successo, non l'ora dell'ultima corsa
    assert voce["errori"] == ["Fermo da 2 giorni (non riesce dal 02/11 alle 08:03): ValueError: pagina strana"]
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 2, 9, 0))
    voce = next(a for a in r["aggiornamenti"] if a["cosa"] == "understat")
    assert voce["errori"] == ["Non riuscito alle 08:03 del 02/11: ValueError: pagina strana"]


# ---------------- una pagina web al posto dei dati ----------------
MANUTENZIONE = b"<!DOCTYPE html>\n<html><head><title>  Sito in\nmanutenzione </title></head><body>Torniamo presto</body></html>"


def test_understat_pagina_web_al_posto_dei_dati():
    with pytest.raises(us.RispostaNonDati, match="pagina web al posto dei dati") as e:
        us.dati_json(MANUTENZIONE)
    assert "«Sito in manutenzione»" in str(e.value)
    with pytest.raises(us.RispostaNonDati, match="non si leggono"):
        us.dati_json(b"Errore 42")
    with pytest.raises(us.RispostaNonDati, match="vuota"):
        us.dati_json(b"  ")
    assert us.dati_json('{"dates": [], "players": []}'.encode()) == {"dates": [], "players": []}
    assert us.dati_json("{\"nome\": \"Martínez\"}".encode("utf-8")) == {"nome": "Martínez"}


def test_aggiornamento_understat_con_pagina_web_una_richiesta_sola_e_errore_chiaro(db, monkeypatch):
    chiamate = []
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *a, **k: chiamate.append(url) or SimpleNamespace(content=MANUTENZIONE))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    a = _agg(db, monkeypatch, "2026-11-04T17:03:00")
    a._passo("Understat", a.understat, "understat")
    assert chiamate == [us.url_lega(2026)]                                     # niente altre richieste dopo la pagina sbagliata
    assert a.errori[0].startswith("Understat: RispostaNonDati: Understat ha risposto con una pagina web al posto dei dati")
