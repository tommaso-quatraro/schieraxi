"""L'elenco dei giocatori sul server (`GET /api/classifica`). Le pagine di mercato della web (Cambi consigliati, Seguiti, Elenco dei
giocatori, Calendario) sono state tolte il 12/11/2026 (#615): la rotta resta per l'iPhone."""
from pathlib import Path

from fanta import server


def test_la_classifica_accetta_tutti_i_giocatori_che_giocano():
    assert "min(limite, 800)" in Path(server.__file__).read_text(encoding="utf-8")
