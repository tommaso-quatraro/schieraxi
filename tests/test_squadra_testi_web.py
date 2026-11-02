"""Squadra, Regole e accesso: testi e accessibilità trovati nel collaudo 7 (2/11/2026)."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
IMPOSTAZIONI = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def test_i_pulsanti_per_tornare_indietro_hanno_la_freccia_come_icona():
    # docs/STILE-SENZA-AI.md: «← Squadra» è vietato, la freccia è un'icona (ICONA_INDIETRO). Restava nei pannelli di
    # Squadra, Altro e Impostazioni e in Novità.
    for nome, sorgente in (("app.js", APP), ("impostazioni.js", IMPOSTAZIONI)):
        assert not re.search(r">← ?\$\{", sorgente), nome
    assert "${ICONA_INDIETRO}${cfg.indietro}" in IMPOSTAZIONI


def _riga_regola(etichetta: str) -> str:
    inizio = APP.index("function stepper(")
    stepper = APP[inizio:APP.index("\n}\n", inizio) + 3]
    riga = re.search(r"^const rigaRegola = .*$", APP, re.M).group(0)
    inizio_esc = APP.index("function esc(")
    esc = APP[inizio_esc:APP.index("\n}\n", inizio_esc) + 3]
    codice = ("const t = k => k; const num = (x) => String(x);\n" + esc + stepper + riga
              + f"\nconsole.log(JSON.stringify(rigaRegola({json.dumps(etichetta)}, stepper('scad_min', 10, {{ passo: 5 }}), 'aiuto')));")
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_ogni_campo_delle_regole_ha_il_nome_della_sua_riga():
    # prima: i campi di «Tempi della lega», «Partite rinviate» e «Rosa e crediti» senza nome; quelli dei punteggi con il titolo
    # della sezione («Gol» anche per l'assist)
    html = _riga_regola("Scadenza della formazione")
    assert re.search(r'<input aria-label="Scadenza della formazione" id="scad_min"', html)
    # il nome è testo: virgolette e «<» non diventano mai HTML (CodeQL segnalava la prima versione, che toglieva i tag con una regex)
    assert 'aria-label="Voto &quot;d&#39;ufficio&quot; &lt;script&gt;"' in _riga_regola('Voto "d\'ufficio" <script>')
    assert "/<[^>]*>/g" not in re.search(r"^const rigaRegola = .*$", APP, re.M).group(0)


def test_la_prova_del_modificatore_non_arrotonda_il_bonus():
    # fascia da 3,5 punti: la prova diceva «bonus +4 punti»
    inizio = APP.index("const aggiornaProva = () => {")
    prova = APP[inizio:APP.index("};", inizio)]
    assert 'tp("regole.media_bonus", Math.abs(b),' in prova
    assert "num(b, Number.isInteger(b) ? 0 : 1)" in prova


def _testo(chiave: str, lingua: int = 0) -> str:
    return re.findall(rf'^    "{re.escape(chiave)}": "(.*)",$', TESTI, re.M)[lingua]


def test_il_comando_rapido_porta_il_nome_dell_app():
    for chiave in ("lega.una_volta_sola", "lega.sc1", "lega.per_usarlo_apri"):
        for lingua in (0, 1):
            assert "Fanta»" not in _testo(chiave, lingua) and "Fanta<" not in _testo(chiave, lingua)
            assert "SchieraXI" in _testo(chiave, lingua)


def test_l_errore_della_casella_dice_anche_l_eta():
    # la casella dice «e ho almeno {eta} anni»: l'errore, se non la spunti, diceva solo Privacy e Termini
    assert "almeno {eta} anni" in _testo("accesso.spunta_letto", 0) and "{eta}" in _testo("accesso.spunta_letto", 1)
    assert APP.count('t("accesso.spunta_letto", { eta: ETA_MINIMA })') == 2
