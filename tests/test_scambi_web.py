"""Analizzatore di scambi nella web app: controlli statici su app.js e stile.css (la prova nel browser si fa a mano a 390, 768, 1024 e 1440 px)."""
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_l_analizzatore_usa_l_analisi_completa_con_conguaglio():
    assert "/api/scambi/analizza?completo=true" in APP and "&conguaglio=" in APP
    assert "MAX_PARTE = 4" in APP


def test_il_risultato_non_mette_nel_codice_html_dati_non_protetti():
    """I nomi e i testi del server nel risultato passano da esc()."""
    corpo = APP[APP.index("function esitoAnalisi"):APP.index("async function vistaScambi")]
    for dato in ("s.altra", "g.testo", "p)", "r)"):
        assert f"esc({dato}" in corpo or f"esc({dato[:-1]})" in corpo, dato
    assert "innerHTML" not in corpo               # il testo si costruisce e basta: lo inserisce il chiamante


@pytest.mark.parametrize("selettore", [".scelto-chip", ".analizzatore .scelte label.voce-scelta", ".riga-conguaglio .campo-testo"])
def test_bersagli_di_tocco_da_44_px(selettore):
    regola = re.search(re.escape(selettore) + r" \{([^}]*)\}", CSS)
    assert regola, selettore
    altezza = re.search(r"min-height:\s*(\d+)px", regola.group(1))
    assert altezza and int(altezza.group(1)) >= 44, selettore


def test_due_colonne_solo_in_aggiunta_al_layout_esistente():
    """Dai e Ricevi sono affiancati solo da 1100 px (a 768-1024 px le colonne da 150 px tagliavano i nomi)."""
    assert re.search(r"@media \(min-width: 1100px\) \{ \.analizzatore \.parti \{ grid-template-columns: repeat\(2", CSS)
    assert ".analizzatore .parti { display: grid; grid-template-columns: minmax(0, 1fr)" in CSS


SCAMBI = APP[APP.index("const MODI_SCAMBIO"):APP.index("// ---------------------------------------------------------------- lega: squadre, rose, regole")]


def test_gli_scambi_hanno_tre_modi_in_un_solo_punto():
    assert '["trova", "scambio.trova_per"], ["costruisci", "scambio.costruisci"], ["valuta", "scambio.valuta_offerta"]' in SCAMBI
    for pannello in ("trova", "costruisci", "valuta"):
        assert f'data-pannello="{pannello}"' in SCAMBI and f'data-esito="{pannello}"' in SCAMBI
    assert "Ho ricevuto un'offerta" not in SCAMBI and "Cerca scambi</h2>" not in SCAMBI          # niente più i vecchi blocchi impilati


def test_il_risultato_e_lo_stesso_nei_tre_modi():
    """Costruisci e Valuta mostrano esitoAnalisi; ogni proposta di Trova lo apre con un tocco (analisi completa)."""
    assert SCAMBI.count("esitoAnalisi(") >= 3
    assert "completo: true" in SCAMBI and "data-dettaglio" in SCAMBI


def test_il_limite_e_un_contatore_e_non_un_errore():
    assert '"/api/scambi/limite"' in SCAMBI and "scambio.ricerche_restano" in SCAMBI and "scambio.ricerche_finite" in SCAMBI
    assert "el.hidden = n == null" in SCAMBI                          # per l'amministratore (nessun limite) il contatore non si vede
    assert "errore(e)" in SCAMBI                                       # il 429 mostra il testo del server (con il tempo che manca), senza aggiunte
    assert "Tailscale" not in SCAMBI and "controlla la connessione" not in SCAMBI


def test_nessuna_ricerca_parte_da_sola_ne_due_insieme():
    assert SCAMBI.count('api("/api/scambi/proposte"') == 1
    assert "if (cercando) return;" in SCAMBI and "pulsante.disabled = true" in SCAMBI
    # la ricerca sta solo nel gestore del pulsante: cambiare squadra, misura o modo non la fa partire
    assert SCAMBI.index('api("/api/scambi/proposte"') > SCAMBI.index('$("#cerca-scambi").addEventListener("click"')


def test_misure_grandi_solo_con_una_squadra_scelta():
    assert "b.disabled = !!n && !con" in SCAMBI


@pytest.mark.parametrize("selettore", [r"\.chips\.misure \.chip"])
def test_misure_con_bersagli_da_44_px(selettore):
    regola = re.search(selettore + r" \{([^}]*)\}", CSS)
    assert regola and int(re.search(r"min-height:\s*(\d+)px", regola.group(1)).group(1)) >= 44


def test_a_due_colonne_su_schermi_larghi():
    assert re.search(r"@media \(min-width: 900px\) \{\s*\.scambi-colonne \{ display: grid; grid-template-columns: minmax\(340px", CSS)


@pytest.mark.skipif(shutil.which("node") is None, reason="serve Node per controllare la sintassi")
def test_sintassi_di_app_js():
    r = subprocess.run(["node", "--check", str(server.WEB / "app.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_rose_dopo_lo_scambio_con_le_sigle_della_lingua_e_crediti_solo_se_valutati():
    """Collaudo 2/11: in inglese «P3 D8 C9 A6» invece di G/D/M/F; con un conguaglio impossibile la riga «Contando i crediti»
    mostrava centinaia di punti inventati; «g10» invece di «G10» come nel calendario."""
    corpo = APP[APP.index("function esitoAnalisi"):APP.index("async function vistaScambi")]
    assert "ruoloSigla(r)" in corpo and "`P${x.conteggio.P}" not in corpo
    assert "c.valore_mio != null" in corpo
    assert "`G${gg}" in corpo and "`g${gg}" not in corpo
