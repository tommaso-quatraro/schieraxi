"""Funzioni accese e spente nella web app: menu a 4 voci, 404 con «funzione» gestito (controlli statici)."""
import re

from fanta import server
import codice_web

APP = codice_web.app()
HTML = (server.WEB / "index.html").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")


def test_la_barra_ha_quattro_voci_oggi_formazione_squadra_altro():
    # grafica B: le voci sono collegamenti (Indietro del browser, Ctrl+clic); al telefono la barra in basso ha 4 colonne
    assert re.findall(r'<a class="scheda" data-vista="(\w+)"', HTML) == ["oggi", "formazione", "squadra", "altro"]
    assert re.findall(r'<span data-t="nav\.\w+">(\w+)</span>\s*</a>', HTML) == ["Oggi", "Formazione", "Squadra", "Altro"]
    barra = re.search(r"\n\.schede \{([^}]*)\}", CSS).group(1)
    assert "grid-template-columns: repeat(4, 1fr)" in barra


def test_le_funzioni_si_leggono_all_avvio_e_una_chiave_che_manca_vale_acceso():
    assert 'api("/api/funzioni")' in APP
    assert 'const funz = id => !stato.funzioni || stato.funzioni.funzioni[id] !== false' in APP
    assert "caricaFunzioni()" in APP[APP.index("controllaAccesso().then"):]


def test_un_404_con_funzione_non_e_un_guasto():
    assert 'r.status === 404 && dati && typeof dati.funzione === "string"' in APP
    assert "const funzioneSpenta = " in APP and "cartaFunzioneSpenta" in APP
    corpo = APP[APP.index("const cartaFunzioneSpenta"):APP.index("// ---------------------------------------------------------------- copia sul telefono")]
    assert "data-riprova" not in corpo.split("const erroreVista")[0]              # niente «Riprova» inutile
    assert 'role="alert"' not in corpo.split("const erroreVista")[0]             # e niente avviso di errore: non è un guasto
