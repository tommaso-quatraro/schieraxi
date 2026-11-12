"""Lega ripulita (solo la lega): controlli statici su app.js e stile.css."""
import re

from fanta import server
from testi_it import espandi
import codice_web

APP = espandi(codice_web.app())
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def _lega():
    inizio = APP.index("async function vistaLega(")
    return APP[inizio:APP.index("\n}\n", inizio)]


def test_plurali_corretti_nelle_squadre():
    lega = _lega()
    assert 'tp("sd.n_giocatori", x.giocatori)' in lega and 'tp("lega.n_crediti", x.crediti_residui)' in lega
    assert "${s.giocatori} giocatori" not in APP and "crediti_residui} crediti" not in APP


def test_regole_a_sezioni_ripiegabili_con_il_nome_vero_della_lega():
    inizio = APP.index("async function vistaRegole(")
    regole = APP[inizio:APP.index('<div class="salva-fisso" hidden><button class="bottone" id="salva-regole">')]
    assert len(re.findall(r'<details class="carta regola-sez"', regole)) == 7 and regole.count("</details>") >= 7          # 7 = con «Partite rinviate»
    assert "<h2 style=\"margin-top:14px\">${esc(r.nome_lega)}</h2>" in regole
    assert regole.count('<details class="carta regola-sez" open>') == 1           # solo la prima è aperta


def test_l_asta_non_compare_piu():
    """L'asta non è prevista: niente voce, niente schermata, niente richieste (la rotta resta per i client vecchi)."""
    assert "function vistaAsta()" not in APP and "tabAsta" not in APP and "asta-corpo" not in APP and "asta-corpo" not in CSS
    assert "/api/asta" not in APP and 'vaiLega("asta")' not in APP


def test_primo_avvio_non_chiede_le_squadre_se_le_rose_non_ci_sono():
    assert "async function caricaSquadre(seServono = false)" in APP
    assert "seServono && stato.info && stato.info.rose_importate === false" in APP
    assert "caricaInfo().then(() => caricaSquadre(true))" in APP
    pa = codice_web.leggi("primoavvio.js")
    assert "await caricaSquadre(true);" in pa
