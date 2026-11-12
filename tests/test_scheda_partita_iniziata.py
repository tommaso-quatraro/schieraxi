"""Scheda del giocatore a partita iniziata o finita (collaudo del 2/11/2026): niente «gioca N%» né probabilità di prima."""
import json
import re
from pathlib import Path

from fanta import server
import codice_web

WEB = Path(server.__file__).parent / "web"
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
SCHEDA = APP[APP.index("function htmlScheda"):APP.index("// Il posto in formazione a parole")]


def test_stati_iniziati_e_finiti_sono_quelli_del_server():
    assert 'const PARTITA_INIZIATA = ["in_corso", "attesa_voti", "fatto", "senza_voto"], PARTITA_FINITA = ["attesa_voti", "fatto", "senza_voto"];' in APP


def test_assist_al_plurale_giusto_in_inglese():
    assert 'tp("mercato.n_assist", st.assist)' in SCHEDA
    en = TESTI[TESTI.index("\n  en: {"):]
    assert json.loads('"' + re.search(r'"mercato.n_assist.one": "([^"]+)"', en).group(1) + '"') == "assist"
    assert re.search(r'"mercato.n_assist.other": "([^"]+)"', en).group(1) == "assists"
