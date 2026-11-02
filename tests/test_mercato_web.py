"""Mercato a 4 schede nella web app: controlli statici su app.js e stile.css (la prova nel browser si fa a mano a 390, 768 e 1280 px)."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_le_schede_vecchie_portano_a_quelle_nuove():
    assert re.search(r'SCHEDE_MERCATO_VECCHIE = \{ classifica: "giocatori", cerca: "giocatori" \}', APP)
    assert "function schedaMercato(" in APP
    # il confronto riapre l'elenco nella scheda nuova; l'indirizzo ?vista=mercato&scheda=... accetta anche i nomi vecchi
    assert 'stato.mercatoTab = "giocatori";' in APP
    assert 'get("scheda")' in APP


def test_l_asta_non_c_e_piu():
    """L'asta non è prevista: niente voce né scheda; un vecchio collegamento all'asta porta ai Consigliati."""
    assert 'id: "asta"' not in APP and 'asta-corpo' not in APP and 'mercatoTab === "asta"' not in APP
    assert 'return tabMercatoVisibili().some(([n]) => n === k) ? k : "consigli";' in APP


def test_giocatori_unisce_classifica_e_cerca_con_filtri():
    corpo = APP[APP.index("function tabGiocatori"):APP.index("// ---------------------------------------------------------------- scheda giocatore")]
    assert 'id="cerca"' in corpo and 'id="solo-liberi"' in corpo and "data-ruolo" in corpo
    assert "filtraListone(" in corpo                      # ricerca locale istantanea già presente


def test_la_riga_del_giocatore_protegge_i_dati_del_server():
    corpo = APP[APP.index("function rigaGiocatoreCompatta"):APP.index("function tabGiocatori")]
    assert "esc(x.nome)" in corpo and "esc(x.proprietario)" in corpo
    assert "num(x.fv_atteso)" in corpo                    # un solo voto atteso, quello che arriva dal server


def test_filtri_con_bersagli_da_44_px():
    for selettore in (r"\.chips\.filtri \.chip", r"\.filtri-giocatori \.interruttore", r"\.voce\.riga-g"):
        regola = re.search(selettore + r" \{([^}]*)\}", CSS)
        assert regola, selettore
        assert int(re.search(r"min-height:\s*(\d+)px", regola.group(1)).group(1)) >= 44, selettore


def test_scheda_giocatore_dice_difficolta_media_e_un_solo_fantavoto_atteso():
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    assert '"diff.3": "Normale"' in testi and "Difficoltà media" not in testi       # parola semplice (1/11/2026)
    assert 'riga(t("mercato.fantavoto_atteso_riga")' in APP and '"mercato.atteso_ponderato": "Atteso ponderato' in testi
    assert "FV atteso" not in APP


def test_la_classifica_accetta_tutti_i_giocatori_che_giocano():
    assert "min(limite, 800)" in Path(server.__file__).read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="serve Node per controllare la sintassi")
def test_sintassi_di_app_js():
    r = subprocess.run(["node", "--check", str(server.WEB / "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_errori_delle_schede_del_mercato_hanno_il_riprova():
    corpo = APP[APP.index("async function tabOsservati"):APP.index("async function tabCalendario")]
    assert "erroreVista(e)" in corpo and "dove.innerHTML = errore(e)" not in corpo
    assert "dove.innerHTML = erroreVista(e)" in APP[APP.index("async function tabCalendario"):APP.index("async function tabCalendario") + 2500]


def test_osservati_col_plurale_giusto():
    """Collaudo 2/11: «1 giocatori osservati» (dal 2/11 il nome è «Seguiti»)."""
    from fanta import server
    app = (server.WEB / "app.js").read_text(encoding="utf-8")
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    assert 'tp("mercato.n_osservati", r.giocatori.length' in app
    assert '"mercato.n_osservati.one": "{n} giocatore seguito"' in testi and '"mercato.n_osservati.one": "{n} player followed"' in testi    # un solo nome: Seguiti
    assert "prossime 5 giornate una per una" not in testi                  # il testo dei Consigliati diceva «giornata per giornata», la riga mostra il totale
