"""Scheda del giocatore a partita iniziata o finita (collaudo del 2/11/2026): niente «gioca N%» né probabilità di prima."""
import json
import re
from pathlib import Path

from fanta import server

WEB = Path(server.__file__).parent / "web"
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
SCHEDA = APP[APP.index("async function apriGiocatore"):APP.index("async function osservatiIds")]


def test_stati_iniziati_e_finiti_sono_quelli_del_server():
    assert 'const PARTITA_INIZIATA = ["in_corso", "attesa_voti", "fatto", "senza_voto"], PARTITA_FINITA = ["attesa_voti", "fatto", "senza_voto"];' in APP


def test_a_partita_iniziata_spariscono_gioca_e_probabilita():
    # «gioca N%» è la seconda cifra accanto al fantavoto atteso (grafica B, spec §9): a partita iniziata la cifra sparisce
    assert '${iniziataP ? "" : `<div class="cifra"><div class="debole">${t("mercato.gioca")}</div>' in SCHEDA
    assert '${nonGioca || iniziataP ? "" : `<div class="stat-fila' in SCHEDA
    assert 'perche_numero: pr.perche_numero.filter(m => m.chiave !== "gioca")' in SCHEDA     # «gioca l'1%: improbabile»
    assert '${finitaP ? "" : cartaPerche(prSenzaGioca)}' in SCHEDA


def test_a_partita_finita_resta_solo_com_e_andata():
    assert '(s.voti || []).find(v => v.giornata === pr.giornata)' in SCHEDA
    assert 't(STATO_PARTITA[pr.stato_partita][0])' in SCHEDA
    assert '!finitaP && motiviUtili(pr)' in SCHEDA


def test_assist_al_plurale_giusto_in_inglese():
    assert 'tp("mercato.n_assist", st.assist)' in SCHEDA
    en = TESTI[TESTI.index("\n  en: {"):]
    assert json.loads('"' + re.search(r'"mercato.n_assist.one": "([^"]+)"', en).group(1) + '"') == "assist"
    assert re.search(r'"mercato.n_assist.other": "([^"]+)"', en).group(1) == "assists"
