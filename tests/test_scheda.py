"""Scheda di un giocatore (fanta/scheda.py): l'andamento dei fantavoti lo decide il server (#895), i client lo mostrano.
Solo dati inventati."""
import pytest

from fanta import scheda


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
    s = scheda.scheda(db, 7, "2026-27")
    assert [v["fv"] for v in s["voti"]] == [6.0, 6.0, 6.0, 8.0, 8.0, 8.0] and s["andamento"] == "in_crescita"
