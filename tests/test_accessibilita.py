"""Accessibilità della web app: contrasto dei colori delle scritte (chiaro e scuro) e attributi che non devono sparire."""
import re

import pytest

from fanta import server
import codice_web

WEB = server.WEB
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
SCRITTE = ["--testo", "--testo-2", "--verde", "--rosso", "--arancio", "--blu", "--giallo-testo", "--azione"]
FONDI = ["--sfondo", "--solido", "--superficie"]           # --superficie: passaggio del mouse, pannello, barra (grafica B)


def _blocco(inizio: str) -> dict:
    """Le variabili colore di un blocco di stile (`:root {` oppure il tema chiaro)."""
    i = CSS.index(inizio)
    fine = CSS.index("}", i)
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", CSS[i:fine]))


def _luminanza(h: str) -> float:
    c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrasto(a: str, b: str) -> float:
    la, lb = sorted((_luminanza(a), _luminanza(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _temi() -> dict:
    scuro = _blocco(":root {")
    scuro["--giallo-testo"] = scuro["--giallo"]                 # nel tema scuro è lo stesso giallo
    return {"scuro": scuro, "chiaro": _blocco(':root[data-tema="chiaro"] {')}


@pytest.mark.parametrize("tema", ["scuro", "chiaro"])
def test_contrasto_scritte_almeno_4_5(tema):
    colori = _temi()[tema]
    for scritta in SCRITTE:
        for fondo in FONDI:
            assert _contrasto(colori[scritta], colori[fondo]) >= 4.5, f"{tema}: {scritta} su {fondo}"


def test_tema_chiaro_automatico_uguale_a_quello_scelto():
    """Il tema chiaro «automatico» (preferenza del sistema) e quello scelto a mano hanno gli stessi colori delle scritte."""
    automatico = _blocco(":root:not([data-tema=\"scuro\"]) {")
    scelto = _temi()["chiaro"]
    for k in SCRITTE:
        if k in automatico:
            assert automatico[k] == scelto[k], k


def test_movimento_ridotto_e_focus_visibile():
    js = codice_web.app()
    assert "html[data-calmo]" in CSS                                       # versione calma (vedi test_movimento_calmo.py)
    assert "prefers-reduced-motion: reduce" in js and '"ridotte"' in js    # sistema e impostazione dell'app la attivano
    assert ":focus-visible" in CSS
    assert not re.search(r":focus-visible\s*\{[^}]*border-radius", CSS)          # il fuoco non deve deformare i bottoni rotondi


def test_pagina_ha_titolo_lingua_e_pannello_con_nome():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = codice_web.app()
    # un solo titolo di primo livello, quello della schermata: lo scrive pagina() in cima a main (grafica B, spec §8.2)
    assert '<html lang="it">' in html and "<h1" not in html and '<h1 id="titolo-pagina"' in js
    assert re.search(r'role="dialog"[^>]*aria-label=', html)
    assert 'class="salta"' in html and 'id="contenuto"' in html


def test_pannello_aperto_blocca_anche_il_link_salta():
    """Con il pannello aperto il fuoco non esce dal pannello (neanche sul link «Vai al contenuto»)."""
    js = codice_web.app()
    riga = next(r for r in js.splitlines() if r.startswith("const SFONDO_FOGLIO"))
    assert '".salta"' in riga and '".testata"' in riga and '".schede"' in riga


def test_script_collega_nomi_ai_campi_e_titolo_per_sezione():
    js = codice_web.app()
    assert "document.title" in js and "aria-labelledby" in js and 'setAttribute("aria-label", nome.trim())' in js
