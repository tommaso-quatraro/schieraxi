"""Lega ripulita (solo la lega): controlli statici su app.js e stile.css."""
import re

from fanta import server
from testi_it import espandi

APP = espandi((server.WEB / "app.js").read_text(encoding="utf-8"))
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def _lega():
    inizio = APP.index("async function vistaLega(")
    return APP[inizio:APP.index("\n}\n", inizio)]


# Dieta delle funzioni: la vecchia Lega è divisa tra Squadra e Altro; i nomi delle voci di prima non cambiano (docs/ETICHETTE.md).
# L'asta non c'è più (non è prevista): dal 1/11/2026 non compare nemmeno in Altro.
VOCI_LEGA_DI_PRIMA = ["Aggiorna le rose", "Squadre e rose", "Movimenti e storico", "Diario delle giornate", "Regole", "Crediti delle squadre", "Nuova stagione"]


def _voci():
    inizio = APP.index("const VOCI_LEGA = [")
    elenco = APP[inizio:APP.index("\n];", inizio)]
    return re.findall(r'\{ id: "(\w+)", ambito: "(\w+)",(?: f: "(\w+)",)? nome: "([^"]+)"', elenco)


def test_le_voci_di_lega_stanno_in_squadra_e_in_altro_con_i_nomi_di_prima():
    voci = _voci()
    assert all(a in ("squadra", "altro") for _, a, _, _ in voci)
    nomi = [n for _, _, _, n in voci]
    assert all(n in nomi for n in VOCI_LEGA_DI_PRIMA)
    # Squadra: la mia squadra, cambi, seguiti, elenco, aggiornamento rose. Altro: scambi, diario, regole, ... novità (le Impostazioni solo dall'ingranaggio)
    assert [i for i, a, _, _ in voci if a == "squadra"][:3] == ["squadre", "consigli", "osservati"]
    assert [n for _, a, _, n in voci if a == "altro"][-1] == "Novità"
    assert "Impostazioni" not in [n for _, _, _, n in voci] and "Asta e riparazione" not in [n for _, _, _, n in voci]


def test_le_voci_nascoste_dalla_dieta_hanno_la_loro_funzione():
    f = {i: fn for i, _, fn, _ in _voci()}
    assert f["osservati"] == "seguiti" and f["giocatori"] == "elenco_giocatori" and f["diario"] == "diario"
    assert f["crediti"] == "crediti" and f["novita"] == "novita"
    assert not {"asta", "cofano", "backup", "impostazioni"} & set(f)
    assert f["squadre"] == "" and f["regole"] == "" and f["scambi"] == ""            # il nucleo non si spegne


def test_lega_riusa_il_componente_a_due_pannelli_delle_impostazioni():
    imp = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")
    assert "function montaPannelli(cfg)" in imp and "function apriPannello(cfg, id" in imp
    assert "montaPannelli(cfg)" in _lega() and "montaPannelli(cfg)" in imp[: imp.index("function montaPannelli")]
    assert 'id="storico-movimenti"' in _lega() and "/api/movimenti?limite=20" in _lega()


def test_la_mia_squadra_ha_stemma_maglia_e_i_crediti_sono_una_voce():
    lega = _lega()
    assert 'immagine(miaS, "stemma")' in lega and 'immagine(miaS, "maglia")' in lega and 'id="apri-stemma-maglia"' in lega
    assert 'id="salva-crediti"' in lega and '"/api/crediti"' in lega and 'method: "PUT"' in lega
    assert 'id="crediti-squadra"' in APP                                  # resta anche il campo nella pagina della singola rosa


def test_plurali_corretti_nelle_squadre():
    lega = _lega()
    assert 'tp("sd.n_giocatori", x.giocatori)' in lega and 'tp("lega.n_crediti", x.crediti_residui)' in lega
    assert "${s.giocatori} giocatori" not in APP and "crediti_residui} crediti" not in APP


def test_regole_a_sezioni_ripiegabili_con_il_nome_vero_della_lega():
    inizio = APP.index("async function vistaRegole()")
    regole = APP[inizio:APP.index('<div class="salva-fisso" hidden><button class="bottone" id="salva-regole">')]
    assert len(re.findall(r'<details class="carta regola-sez"', regole)) == 7 and regole.count("</details>") >= 7          # 7 = con «Partite rinviate»
    assert "<h2 style=\"margin-top:14px\">${esc(r.nome_lega)}</h2>" in regole
    assert regole.count('<details class="carta regola-sez" open>') == 1           # solo la prima è aperta


def test_l_asta_non_compare_piu():
    """L'asta non è prevista: niente voce, niente schermata, niente richieste (la rotta resta per i client vecchi)."""
    assert "function vistaAsta()" not in APP and "tabAsta" not in APP and "asta-corpo" not in APP and "asta-corpo" not in CSS
    assert "/api/asta" not in APP and 'vaiLega("asta")' not in APP


def test_nuova_stagione_e_una_voce_e_il_banner_compare_solo_quando_serve():
    assert "async function nuovaStagione(dove)" in APP and 'id="nuova-stagione"' in APP
    assert "if (!s.nuova || stato.vista !== \"altro\"" in APP and "contenuto.prepend(c)" in APP


def test_primo_avvio_non_chiede_le_squadre_se_le_rose_non_ci_sono():
    assert "async function caricaSquadre(seServono = false)" in APP
    assert "seServono && stato.info && stato.info.rose_importate === false" in APP
    assert "caricaInfo().then(() => caricaSquadre(true))" in APP
    pa = (server.WEB / "primoavvio.js").read_text(encoding="utf-8")
    assert "await caricaSquadre(true);" in pa
