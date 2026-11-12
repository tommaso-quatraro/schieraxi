"""Accessibilità della Formazione sulla web (issue #244): i tre errori che axe trovava su main a 390 e 1440 px, in chiaro e in scuro.
- valore piccolo e stella dentro il chip scelto (modulo e stile): 4,09:1 sul lime del tema chiaro;
- sigla della squadra nella legenda del campo (e sulle pedine): bianco su azzurro del Napoli 3,47:1;
- nome accessibile delle pedine (`label-content-name-mismatch`): l'aria-label non conteneva il testo che si vede.
La prova vera è axe nel browser; qui i controlli che si possono fare senza browser."""
import json
import re
import shutil
import subprocess


from fanta import server
from tests.test_design_web import _colore, _contrasto_rgb, _sopra, _temi
import codice_web

APP = codice_web.app()
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
        chip = _colore(v["--sfondo"])[0]       # grafica B: la carta della Formazione e i chip non scelti non hanno fondo, sotto c'è la pagina
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


def _opacita_dell_entrata(vela):
    """L'opacità a ogni tappa (percentuale) dell'animazione di entrata della pedina; `vela` = valore di `--vela` (1 senza
    la regola del movimento calmo, 0 con `html[data-calmo]`)."""
    nome = re.search(r"^\.pedina \{[^}]*?animation: ([\w-]+) ", CSS, re.M).group(1)
    tappe = re.search(r"^@keyframes " + re.escape(nome) + r" \{(.*)\}\s*$", CSS, re.M).group(1)
    uscita = {}
    for percento, corpo in re.findall(r"(\d+)% \{([^{}]*)\}", tappe):
        valore = re.search(r"(?<![\w-])opacity: ([^;]+?)\s*(?:;|$)", corpo.strip())
        if valore:
            uscita[int(percento)] = float(re.sub(r"var\(--vela, 1\)", str(vela), valore.group(1)))
    return uscita


def test_entrata_delle_pedine_non_lascia_il_testo_a_meta_dissolvenza():
    """Issue #307: con la pedina a metà dissolvenza il testo delle pillole («⚠ gioca 45%», sigla della squadra) ha un contrasto più
    basso di quello a riposo, perché il fondo della pillola si mescola al campo scuro: axe lo segnalava se misurava nei primi
    100 ms dell'entrata (a opacità 0,7 l'arancio sta a 4,16:1; alcune sigle scendono sotto 4,5:1). La pedina compare di colpo e
    il resto dell'entrata è solo movimento (scala e spostamento)."""
    opacita = _opacita_dell_entrata(vela=1)
    assert opacita[0] == 0                                                   # prima del proprio turno (ritardo) non si vede
    assert any(p <= 5 and o == 1 for p, o in opacita.items()), opacita       # entro il 5% (27 ms) è già piena
    assert all(o == 1 for p, o in opacita.items() if p > 5), opacita


def test_movimento_calmo_mantiene_la_dissolvenza_delle_pedine():
    """Con «Riduci movimento» (`--vela: 0`) le pedine non si muovono: restano le sole dissolvenze, come prima."""
    assert re.search(r"^html\[data-calmo\] \{ --mov: 0; --vela: 0; \}", CSS, re.M)
    opacita = _opacita_dell_entrata(vela=0)
    assert opacita[0] == 0 and opacita[100] == 1
    assert all(o == 0 for p, o in opacita.items() if 0 < p < 100), opacita   # nessun salto: sale in tutta la durata
