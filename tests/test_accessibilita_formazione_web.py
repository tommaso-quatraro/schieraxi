"""Accessibilità della Formazione sulla web (issue #244): i tre errori che axe trovava su main a 390 e 1440 px, in chiaro e in scuro.
- valore piccolo e stella dentro il chip scelto (modulo e stile): 4,09:1 sul lime del tema chiaro;
- sigla della squadra nella legenda del campo (e sulle pedine): bianco su azzurro del Napoli 3,47:1;
- nome accessibile delle pedine (`label-content-name-mismatch`): l'aria-label non conteneva il testo che si vede.
La prova vera è axe nel browser; qui i controlli che si possono fare senza browser."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
from tests.test_design_web import _colore, _contrasto_rgb, _sopra, _temi

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _regola(selettore):
    corpo = re.search(r"^" + re.escape(selettore) + r" \{([^}]*)\}", CSS, re.M)
    assert corpo, selettore
    return corpo.group(1)


def _colore_della_regola(selettore, v, fondo):
    """Il colore della scritta di una regola, già sopra il suo fondo: «var(--x)» o «color-mix(in srgb, var(--x) N%, transparent)»."""
    valore = re.search(r"(?<![\w-])color: ([^;]+);", _regola(selettore)).group(1).strip()
    misto = re.fullmatch(r"color-mix\(in srgb, var\((--[\w-]+)\) (\d+)%, transparent\)", valore)
    if misto:
        return _sopra(_colore(v[misto.group(1)])[0], int(misto.group(2)) / 100, fondo)
    nome = re.fullmatch(r"var\((--[\w-]+)\)", valore).group(1)
    return _colore(v[nome])[0]


def test_valore_e_stella_dei_chip_almeno_4_5_in_chiaro_e_scuro():
    """Il numero piccolo accanto al modulo («4-3-3 73,8») e la stella: testo da 12 px, serve 4,5:1 sul lime del chip scelto e
    sulla carta dei chip non scelti. Prima, nel chiaro, il colore all'80% sul lime #86a800 dava 4,09:1."""
    sotto = []
    for tema, v in _temi().items():
        sfondo = _colore(v["--sfondo"])[0]
        carta, a_carta = _colore(v["--vetro-carta"])
        chip = _sopra(carta, a_carta, _sopra(carta, a_carta, sfondo))              # chip (vetro-carta) dentro la carta della Formazione
        lime = _colore(v["--capitano"])[0]
        for selettore, fondo in ((".chip span", chip), (".chip i", chip), (".chip.attiva span, .chip.attiva i", lime)):
            c = _contrasto_rgb(_colore_della_regola(selettore, v, fondo), fondo)
            if c < 4.5:
                sotto.append(f"{tema} {selettore}: {c:.2f}")
        c = _contrasto_rgb(_colore_della_regola(".chip.attiva", v, lime), lime)
        if c < 4.5:
            sotto.append(f"{tema} .chip.attiva: {c:.2f}")
    assert not sotto, sotto


def _node(codice):
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _luminanza(rgb):
    c = [x / 255 for x in rgb]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_sigla_della_squadra_leggibile_su_ogni_colore_sociale_come_su_iphone():
    """La sigla nei colori sociali (legenda del campo, pedine): bianco o nero, quello con il contrasto più alto, come
    `LetturaPedina.testoScuro` dell'iPhone. Prima la web sceglieva con la luminosità sopra 0,35: Napoli 3,47:1, Sassuolo 4,38:1."""
    funz = APP[APP.index("const nomeClub"):APP.index("// Per i lettori di schermo")]
    tabella = APP[APP.index("const COLORI_SQUADRA = {"):APP.index("// Avatar: volto illustrato")]
    codice = ("const SIGLE={}; const sigla=s=>String(s).slice(0,3).toUpperCase();" + tabella + funz
              + "console.log(JSON.stringify([...Object.keys(COLORI_SQUADRA), 'sconosciuta'].map(s => [s, distintivo(s)])))")
    sotto, diversi = [], []
    for squadra, html in _node(codice):
        fondo = re.search(r"--c1:(#[0-9a-f]{6})", html).group(1)
        testo = re.search(r"--ct:(#[0-9a-f]{6})", html).group(1)
        c = _contrasto_rgb(_colore(testo)[0], _colore(fondo)[0])
        if c < 4.5:
            sotto.append(f"{squadra} {testo} su {fondo}: {c:.2f}")
        l = _luminanza(_colore(fondo)[0])
        atteso = "#000000" if (l + 0.05) / 0.05 > 1.05 / (l + 0.05) else "#ffffff"       # la regola dell'iPhone
        if testo != atteso:
            diversi.append(f"{squadra}: {testo} invece di {atteso}")
    assert not sotto, sotto
    assert not diversi, diversi


def test_pedina_nome_accessibile_dal_contenuto_con_il_testo_che_si_vede():
    """Le pedine avevano un aria-label («Rossi L., fantavoto atteso 6,8, …») diverso dal testo visibile («6,8 Rossi gioca 85%
    vs NAP»): chi usa il controllo vocale dice quello che vede (WCAG 2.5.3). Ora il pulsante prende il nome dal contenuto: le
    abbreviazioni visibili sono nascoste ai lettori di schermo e accanto c'è la frase intera, come «vs PAR» nelle righe (vsAt)."""
    pedina = APP[APP.index("function pedina("):APP.index("// Legenda del campo")]
    apertura = re.search(r'<button class="pedina"[^>]*>', pedina).group(0)
    assert "aria-label" not in apertura
    assert '<span class="solo-lettori">${esc(vocePedina(x, esitoPartita(x)))}</span>' in pedina
    for pezzo in ('<span class="avatar-pedina" aria-hidden="true">', '<span class="nome" aria-hidden="true">',
                  '<span class="gioca esito" aria-hidden="true">', '<span class="gioca${p < SOGLIA_GIOCA ? " basso" : ""}" aria-hidden="true">',
                  '<span class="avv" aria-hidden="true">'):
        assert pezzo in pedina, pezzo
