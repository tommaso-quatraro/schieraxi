"""Dieta delle funzioni nella web app: menu a 4 voci, funzioni spente nascoste, 404 con «funzione» gestito, «Mostra tutte» (controlli statici)."""
import re

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
IMP = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")
HTML = (server.WEB / "index.html").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_la_barra_ha_quattro_voci_oggi_formazione_squadra_altro():
    assert re.findall(r'<button data-vista="(\w+)"', HTML) == ["oggi", "formazione", "squadra", "altro"]
    assert re.findall(r'<span data-t="nav\.\w+">(\w+)</span>\s*</button>', HTML) == ["Oggi", "Formazione", "Squadra", "Altro"]
    assert CSS.count("repeat(4, 1fr)") >= 1 and "repeat(4, 72px)" in CSS and "repeat(5, 72px)" not in CSS


def test_mercato_scambi_e_lega_di_prima_restano_raggiungibili_sotto_squadra_e_altro():
    assert 'const SOTTO_VISTE = { mercato: "squadra", scambi: "altro", lega: "altro" }' in APP
    assert 'vai("scambi")' in APP and "function vaiMercato(" in APP


def test_le_funzioni_si_leggono_all_avvio_e_una_chiave_che_manca_vale_acceso():
    assert 'api("/api/funzioni")' in APP
    assert 'const funz = id => !stato.funzioni || stato.funzioni.funzioni[id] !== false' in APP
    assert "caricaFunzioni()" in APP[APP.index("controllaAccesso().then"):]


def test_ogni_funzione_spenta_nasconde_la_sua_parte():
    assert 'funz("live")) avviaLive' in APP
    assert 'funz("seguiti")' in APP and 'funz("confronto")' in APP and 'funz("elenco_giocatori")' in APP
    assert 'funz("immagini_web")' in APP and 'funz("stili_ridotti")' in APP and 'funz("scambi_trova")' in APP
    assert 'funz("squadre_altrui")' in APP and 'funz("novita")' in APP
    assert 'funz("backup")' not in IMP and 'funz("aspetto_avanzato")' not in APP     # copia di sicurezza e aspetto avanzato tolti il 1/11/2026


def test_un_404_con_funzione_non_e_un_guasto():
    assert 'r.status === 404 && dati && typeof dati.funzione === "string"' in APP
    assert "const funzioneSpenta = " in APP and "cartaFunzioneSpenta" in APP
    corpo = APP[APP.index("const cartaFunzioneSpenta"):APP.index("// ---------------------------------------------------------------- copia sul telefono")]
    assert "data-riprova" not in corpo.split("const erroreVista")[0]              # niente «Riprova» inutile
    assert 'soloAmministratore() ? `<button class="bottone secondario" type="button" data-imp-gruppo="avanzate">' in corpo   # le impostazioni solo a chi gestisce


def test_mostra_tutte_le_funzioni_solo_per_chi_gestisce():
    """Dal 1/11/2026 (come sull'iPhone) Avanzate, e quindi «Mostra tutte le funzioni», c'è solo per chi gestisce SchieraXI."""
    assert 'id="mostra-tutte"' in IMP and '"/api/funzioni", { method: "PUT"' in IMP and "mostra_tutte: mt.checked" in IMP
    gruppo = re.search(r'\{ id: "avanzate"[^}]*\}', IMP).group(0)
    assert "visibile: () => soloAmministratore()" in gruppo
