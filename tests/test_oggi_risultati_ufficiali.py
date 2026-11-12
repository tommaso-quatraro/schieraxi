"""I risultati ufficiali delle partite giocate ci sono anche senza i risultati in diretta (funzione spenta o fonte giù):
`partite[].gol_casa`/`gol_trasferta` in GET /api/oggi. Li mostra l'iPhone; la web non ha più le Partite del turno (#615)."""
from datetime import datetime

from test_fasi import ambiente, _oggi  # noqa: F401 - ambiente è una fixture

from fanta import gestione


def test_partite_giocate_con_il_risultato_ufficiale(ambiente):
    ambiente.db.execute("UPDATE partite SET giocata = 1, gol_casa = 2, gol_trasferta = 0 WHERE casa = 'inter' AND giornata = 10")
    ambiente.db.commit()
    o = _oggi(ambiente, datetime(2026, 11, 8, 12, 0))
    p = {x["casa"]: x for x in o["partite"]}
    assert (p["inter"]["giocata"], p["inter"]["gol_casa"], p["inter"]["gol_trasferta"]) == (True, 2, 0)
    assert (p["roma"]["gol_casa"], p["roma"]["gol_trasferta"]) == (None, None)       # non ancora giocata: niente numeri


def test_anche_senza_rose(ambiente):
    ambiente.db.execute("UPDATE partite SET giocata = 1, gol_casa = 1, gol_trasferta = 1 WHERE casa = 'inter' AND giornata = 10")
    ambiente.db.commit()
    o = gestione.oggi_senza_rose(ambiente.db, adesso=datetime(2026, 11, 8, 12, 0))
    p = {x["casa"]: x for x in o["partite"]}
    assert (p["inter"]["gol_casa"], p["inter"]["gol_trasferta"]) == (1, 1) and p["napoli"]["gol_casa"] is None
