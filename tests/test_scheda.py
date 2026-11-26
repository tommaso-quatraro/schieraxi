"""Scheda di un giocatore (fanta/scheda.py): l'andamento dei fantavoti lo decide il server (#895), i client lo mostrano.
Solo dati inventati."""
import pytest

from fanta import archivio, fasi, scheda
from fanta.regole import Bonus, Regole


def _voti(*fv):
    return [{"giornata": g, "fv": v} for g, v in enumerate(fv, start=1)]


@pytest.mark.parametrize("fv, atteso", [
    ((), None),                                        # nessuna presenza: niente andamento
    ((6.0, 7.0, None), "pochi_dati"),                  # meno di 4 voti veri
    ((6.0, 6.0, 6.0, 8.0, 8.0, 8.0), "in_crescita"),   # media delle ultime 3 (8) contro tutte (7): +1
    ((8.0, 8.0, 8.0, 6.0, 6.0, 6.0), "in_calo"),
    ((6.0, 6.5, 6.0, 6.5, 6.0, 6.5), "stabile"),
    ((6.0, 6.0, None, 6.0, 7.0, 7.0), "stabile"),      # senza voto non conta: ultime 3 (6,7) contro tutte (6,4), sotto 0,6
    ((5.0, 5.0, 5.0, 8.0, None, 8.0, 8.0), "in_crescita"),
])
def test_andamento_dei_fantavoti(fv, atteso):
    assert scheda.andamento(_voti(*fv)) == atteso


def test_la_scheda_porta_l_andamento(tmp_path):
    """GET /api/giocatore manda `andamento` accanto ai voti: la web e l'iPhone mostrano la parola, non la ricalcolano."""
    from fanta import archivio
    db = archivio.apri(tmp_path / "fanta.sqlite")
    archivio.inserisci(db, "calciatori", [{"id": 7, "nome": "Rossi", "ruolo": "C", "squadra": "INT", "squadra_slug": "inter"}])
    zero = dict.fromkeys(("gol", "assist", "ammonizioni", "espulsioni", "gol_subiti", "rig_segnati", "rig_sbagliati", "rig_parati",
                          "autogol", "subentrato", "sostituito"), 0)
    archivio.inserisci(db, "voti", [{"stagione": "2026-27", "giornata": g, "calciatore_id": 7, "nome": "Rossi", "squadra": "inter", "ruolo": "C",
                                     "voto_red": v, "fv_red": v} | zero for g, v in enumerate((6.0, 6.0, 6.0, 8.0, 8.0, 8.0), start=1)])
    s = scheda.scheda(db, 7, "2026-27", Regole())
    assert [v["fv"] for v in s["voti"]] == [6.0, 6.0, 6.0, 8.0, 8.0, 8.0] and s["andamento"] == "in_crescita"


# ---------------------------------------------------------------- i fantavoti con le regole della lega (26/11/2026)
ST = "2026-27"
# una lega con il gol del difensore a 4,5, l'assist a 1,5 e l'ammonizione a -1 (Fantacalcio.it: 3, 1 e -0,5)
LEGA = Regole(bonus=Bonus(gol={"P": 3.0, "D": 4.5, "C": 3.0, "A": 3.0}, assist=1.5, ammonizione=-1.0))
# giornata: (voto, gol, assist, ammonizioni, fantavoto già pronto di Fantacalcio.it con i bonus classici); la 3 senza voto
VOTI_DIFENSORE = {1: (6.0, 0, 0, 0, 6.0), 2: (6.0, 0, 0, 0, 6.0), 3: (None, 0, 0, 0, None), 4: (6.5, 0, 0, 1, 6.0),
                  5: (6.0, 0, 0, 0, 6.0), 6: (6.0, 1, 0, 0, 9.0), 7: (5.5, 0, 1, 0, 6.5)}


def _difensore(db) -> None:
    archivio.inserisci(db, "calciatori", [{"id": 7, "nome": "Verdi", "ruolo": "D", "squadra": "GEN", "squadra_slug": "genoa"}])
    zero = dict.fromkeys(("gol_subiti", "rig_segnati", "rig_sbagliati", "rig_parati", "autogol", "espulsioni", "mvp", "subentrato",
                          "sostituito"), 0)
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": g, "calciatore_id": 7, "nome": "Verdi", "squadra": "genoa", "ruolo": "D",
                                     "voto_red": v, "fv_red": fv, "gol": gol, "assist": ass, "ammonizioni": amm} | zero
                                    for g, (v, gol, ass, amm, fv) in VOTI_DIFENSORE.items()])
    db.commit()


def test_la_scheda_conta_i_fantavoti_con_i_bonus_della_lega(tmp_path):
    """Difetto del 26/11/2026: la scheda prendeva i fantavoti già pronti di Fantacalcio.it (`fv_red`), con i bonus classici, mentre
    Formazione, Oggi e Giornate li calcolano con le regole della lega: un difensore che prende 6 e segna faceva 10,5 in Giornate e 9
    nella scheda. Ora pallini, grafico, fantamedia e andamento hanno lo stesso fantavoto delle altre schermate."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _difensore(db)
    s = scheda.scheda(db, 7, ST, LEGA)
    fv = [v["fv"] for v in s["voti"]]
    assert fv == [6.0, 6.0, None, 5.5, 6.0, 10.5, 7.0]                          # 6 + 4,5 del gol, non il 9 di Fantacalcio.it
    # lo stesso numero di «fv_preso» in Formazione e Oggi (fasi._fantavoti_presi), giornata per giornata
    for g, atteso in zip(VOTI_DIFENSORE, fv):
        assert fasi._fantavoti_presi(db, LEGA, ST, g, {7: {"ruolo": "D"}}).get(7) == atteso
    assert s["stagione"]["fantamedia"] == round((6 + 6 + 5.5 + 6 + 10.5 + 7) / 6, 2)     # 6,83; con i bonus classici 6,58
    assert s["stagione"]["ultime_5_fv"] == [None, 5.5, 6.0, 10.5, 7.0]
    # media delle ultime 3 contro tutte: +1 con i bonus della lega (in crescita), +0,58 con quelli classici (stabile)
    assert s["andamento"] == "in_crescita"
    assert scheda.scheda(db, 7, ST, Regole())["andamento"] == "stabile"


def test_la_scheda_parte_dal_voto_scelto_dalla_lega(tmp_path):
    """Il voto di partenza è quello delle regole (`fonte_voto`), come in Formazione e Giornate."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _difensore(db)
    db.execute("UPDATE voti SET voto_stat = voto_red + 1 WHERE voto_red IS NOT NULL")
    s = scheda.scheda(db, 7, ST, Regole(fonte_voto="statistico"))
    assert [v["voto"] for v in s["voti"]][:2] == [7.0, 7.0] and [v["fv"] for v in s["voti"]][5] == 10.0     # 7 + 3 del gol


def test_la_rotta_della_scheda_usa_le_regole_della_lega(tmp_path, monkeypatch):
    """GET /api/giocatore/{id}: la fantamedia e i voti della scheda con le regole della lega di chi chiede."""
    from fastapi.testclient import TestClient

    from fanta import consigli, server
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _difensore(db)
    db.close()
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(server, "_regole", lambda ctx: LEGA)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda *a, **k: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda *a, **k: (_ for _ in ()).throw(ValueError("niente previsioni nel test")))
    s = TestClient(server.app, headers={"X-Fanta": "1"}).get("/api/giocatore/7").json()
    assert s["stagione"]["fantamedia"] == 6.83 and s["voti"][5]["fv"] == 10.5 and s["andamento"] == "in_crescita"
