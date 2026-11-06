"""Fonti in ombra (football-data.co.uk): lettura delle colonne in più, tabella, esperimenti di `verifica --fonti`.
Nessuna chiamata di rete: file finto in tests/dati."""
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import aggiorna, archivio, squadre, stato_dati, verifica_fonti
from fanta.fonti import footballdata
from fanta.modello import Dati

CSV = Path(__file__).parent / "dati" / "football_data_extra.csv"
SLUG = {"como", "sassuolo", "milan", "pisa", "roma", "inter"}
slug = lambda n: squadre.slug(n, SLUG)  # noqa: E731


def test_leggi_extra_prende_le_colonne_in_piu():
    righe = footballdata.leggi_extra(CSV.read_text(encoding="utf-8"), slug)
    assert [(r["casa"], r["trasferta"]) for r in righe] == [("como", "sassuolo"), ("milan", "pisa")]   # E0 e riga senza dati saltate
    como, milan = righe
    assert (como["xg_casa"], como["xg_trasferta"]) == (2.10, 0.85)
    assert (como["tiri_casa"], como["in_porta_trasferta"], como["angoli_casa"], como["falli_trasferta"]) == (15, 3, 7, 12)
    assert (como["gialli_trasferta"], como["rossi_casa"]) == (3, 0)
    assert milan["xg_casa"] is None and milan["xg_trasferta"] == 0.4        # xG 9,5 fuori da 0-6: scartato
    assert como["data"] == "2026-10-24"


def test_aggiorna_salva_senza_chiamate_in_piu(tmp_path, monkeypatch):
    chiamate = []

    def finta(url, *a, **k):
        chiamate.append(url)
        return SimpleNamespace(content=CSV.read_bytes())
    monkeypatch.setattr(aggiorna.rete, "scarica", finta)
    db = archivio.apri(tmp_path / "t.sqlite")
    a = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None)
    a.slug_noti = set(SLUG)
    a.dati_extra()
    assert len(chiamate) == 2                         # stagione + prossime partite
    assert db.execute("SELECT COUNT(*) FROM partite_extra WHERE stagione = '2026-27'").fetchone()[0] == 2
    assert db.execute("SELECT name FROM sqlite_master WHERE name = 'quote'").fetchone() is None   # nessuna tabella di quote
    r = db.execute("SELECT xg_casa, rilevato FROM partite_extra WHERE casa = 'como'").fetchone()
    assert r["xg_casa"] == 2.10 and r["rilevato"]
    o = stato_dati.ombra(db)["partite_extra"]
    assert o["righe"] == 2 and o["ultima"]
    db.close()


def _dati(extra, partite=None):
    p = partite if partite is not None else pd.DataFrame([
        {"id": 1, "stagione": "2026-27", "giornata": 1, "casa": "como", "trasferta": "sassuolo", "gol_casa": 2, "gol_trasferta": 1,
         "xg_casa": 1.5, "xg_trasferta": 1.0},
        {"id": 2, "stagione": "2026-27", "giornata": 1, "casa": "roma", "trasferta": "inter", "gol_casa": 0, "gol_trasferta": 0,
         "xg_casa": 1.0, "xg_trasferta": 1.2}])
    return Dati(["2026-27"], pd.DataFrame(), pd.DataFrame(), p, pd.DataFrame(), extra=pd.DataFrame(extra))


EXTRA = [{"stagione": "2026-27", "data": "2026-10-24", "casa": "como", "trasferta": "sassuolo", "rilevato": "x",
          "xg_casa": 2.1, "xg_trasferta": 0.85, "in_porta_casa": 6, "in_porta_trasferta": 3}]


def test_varianti_cambiano_solo_le_partite_con_il_dato_e_non_toccano_l_originale():
    d = _dati(EXTRA)
    prima = d.partite.copy()
    x, n = verifica_fonti.dati_con_variante(d, "xg_fd")
    assert n == 1 and x.partite.loc[0, "xg_casa"] == 2.1 and x.partite.loc[1, "xg_casa"] == 1.0
    pd.testing.assert_frame_equal(d.partite, prima)                        # l'originale è intatto
    with pytest.raises(ValueError):
        verifica_fonti.dati_con_variante(d, "inventata")


def test_tiri_porta_tolta_perche_mescola_gli_xg_di_understat():
    assert verifica_fonti.VARIANTI == ("xg_fd",)
    with pytest.raises(ValueError, match="fonte sconosciuta"):
        verifica_fonti.dati_con_variante(_dati(EXTRA), "tiri_porta")


def test_senza_dati_extra_le_varianti_non_cambiano_niente():
    d = _dati(pd.DataFrame())
    for v in verifica_fonti.VARIANTI:
        assert verifica_fonti.dati_con_variante(d, v)[1] == 0


def _tabella(righe):
    return pd.DataFrame([{"prova": p, "stagione": s, "variazione_errore_pct": v, "partite_cambiate": n}
                         for p, s, v, n in righe])


def test_regola_di_promozione():
    ok = _tabella([("xg_fd", "tutte", -0.8, 300), ("xg_fd", "2024-25", -0.6, 300), ("xg_fd", "2025-26", -1.0, 300),
                   ("xg_fd", "2026-27", 0.3, 300)])
    assert verifica_fonti.giudizio(ok)["xg_fd"].startswith("PROMOSSA")
    poco = _tabella([("xg_fd", "tutte", -0.2, 300), ("xg_fd", "2025-26", -0.5, 300), ("xg_fd", "2026-27", -0.1, 300)])
    assert verifica_fonti.giudizio(poco)["xg_fd"].startswith("non promossa")
    una = _tabella([("xg_fd", "tutte", -3.0, 50), ("xg_fd", "2026-27", -3.0, 50)])
    assert "solo indicativo" in verifica_fonti.giudizio(una)["xg_fd"]
    niente = _tabella([("xg_fd", "tutte", 0.0, 0), ("xg_fd", "2025-26", 0.0, 0), ("xg_fd", "2026-27", 0.0, 0)])
    assert "niente da misurare" in verifica_fonti.giudizio(niente)["xg_fd"]


def test_confronto_riporta_prima_e_dopo(monkeypatch):
    def finta(dati, regole, par, giornate, rose, simulazioni, scrivi=None, oracolo=frozenset()):
        meglio = bool((dati.partite["xg_casa"] == 2.1).any())      # la variante xg_fd ha l'xG nuovo
        e = 1.0 if meglio else 2.0
        return pd.DataFrame([{"stagione": "2026-27", "giornata": 1, "quadratico_modello": e * e, "brier": 0.2,
                              "punti_modello": 70.0 + (1 if meglio else 0)}])
    monkeypatch.setattr(verifica_fonti.verifica, "verifica", finta)
    tab = verifica_fonti.confronto(_dati(EXTRA), None, None, [("2026-27", 1)], varianti=("xg_fd",), scrivi=None)
    riga = tab[(tab["prova"] == "xg_fd") & (tab["stagione"] == "tutte")].iloc[0]
    assert riga["variazione_errore_pct"] == pytest.approx(-50.0) and riga["variazione_punti"] == 1.0
    assert tab[tab["prova"] == "base"]["variazione_errore_pct"].eq(0).all()


def test_archivio_vecchio_perde_la_tabella_delle_quote(tmp_path):
    import sqlite3
    f = tmp_path / "vecchio.sqlite"
    v = sqlite3.connect(f)
    v.execute("CREATE TABLE quote (stagione TEXT, casa TEXT, trasferta TEXT, q1 REAL)")
    v.execute("CREATE TABLE aggiornamenti (cosa TEXT PRIMARY KEY, quando TEXT, dettaglio TEXT)")
    v.execute("INSERT INTO aggiornamenti VALUES ('quote', 'x', ''), ('quote-odds', 'x', ''), ('voti', 'x', '')")
    v.commit()
    v.close()
    db = archivio.apri(f)
    assert db.execute("SELECT name FROM sqlite_master WHERE name = 'quote'").fetchone() is None
    assert [r[0] for r in db.execute("SELECT cosa FROM aggiornamenti")] == ["voti"]
    db.close()
