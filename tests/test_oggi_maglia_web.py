"""Oggi con la maglia della squadra (collaudo del 1/11/2026): il testo sotto «Chiusa» finiva sotto la maglia.
Due difetti insieme: mancava lo spazio prima di «con-maglia» (classe «contocon-maglia») e la densità compatta azzerava il margine a destra."""
import re

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_classe_con_maglia_staccata_da_conto():
    assert '"con-maglia" : ""' not in APP
    assert re.search(r'class="carta hero conto\$\{[^}]*\? " con-maglia" : ""\}"', APP)


def test_margine_per_la_maglia_anche_con_la_densita_compatta():
    regola = re.search(r'^([^{\n]*\.carta\.con-maglia[^{]*)\{([^}]*)\}', CSS, re.M)
    assert regola and 'html[data-densita="compatta"] .carta.con-maglia' in regola.group(1)
    assert "padding-right: 132px" in regola.group(2)
