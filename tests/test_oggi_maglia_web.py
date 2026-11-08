"""Oggi con la maglia della squadra (collaudo del 1/11/2026, issue #384): il testo sotto «Chiusa» finiva sotto la maglia e la maglia,
larga 150 px e appoggiata sopra la carta, copriva il conto alla rovescia («20 h 22 mi…»). Con la grafica B (spec §9) conto e maglia
stanno in due colonne della stessa griglia: il testo non può più finire sotto la maglia, a nessuna larghezza e con ogni densità."""
import re

from fanta import server
import codice_web

APP = codice_web.app()
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_classe_con_maglia_staccata_da_conto():
    assert '"con-maglia" : ""' not in APP
    assert re.search(r'class="conto-oggi\$\{[^}]*\? " con-maglia" : ""\}"', APP)


def test_testo_e_maglia_in_due_colonne_con_ogni_densita():
    regola = re.search(r'\n\.conto-oggi\.con-maglia \{([^}]*)\}', CSS)
    assert regola and "grid-template-columns: minmax(0, 1fr) auto" in regola.group(1)
    assert re.search(r"\n\.conto-oggi \{[^}]*display: grid", CSS)
    # nessuna regola della densità compatta tocca il conto: niente margine da difendere, come prima con «padding-right: 132px»
    assert not re.search(r'data-densita="compatta"\][^{]*\.(conto-oggi|con-maglia|maglia-hero)', CSS)
    assert ".carta.con-maglia" not in CSS
