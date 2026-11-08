"""Squadra, Regole e accesso: testi e accessibilità trovati nel collaudo 7 (2/11/2026)."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
IMPOSTAZIONI = codice_web.leggi("impostazioni.js")
TESTI = codice_web.leggi("testi.js")
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


def _regole_node(chiamata: str, lingua: str = "it"):
    pezzo = lambda inizio, fine: APP[APP.index(inizio):APP.index(fine, APP.index(inizio))]  # noqa: E731
    codice = "\n".join([TESTI, f"LINGUA = '{lingua}';", pezzo("function esc(", "\n}\n") + "\n}",
                        re.search(r"^const num = .*$", APP, re.M).group(0),
                        pezzo("function stepper(", "\n}\n") + "\n}",
                        pezzo("// Il nome dei campi delle fasce", "\n\ndocument.addEventListener"),
                        f"console.log(JSON.stringify({chiamata}));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_ogni_campo_delle_fasce_dice_quale_fascia_e_quale_numero():
    """#454: i campi delle fasce si chiamavano tutti «Fasce di bonus» (il titolo della sezione, messo da sincronizzaAria)."""
    html = _regole_node("rigaFascia(6.25, 1.5, 2)")
    assert re.search(r'<input aria-label="Fascia 2, media almeno" [^>]*class="f-media"[^>]*value="6,25"', html)
    assert re.search(r'<input aria-label="Fascia 2, bonus" [^>]*class="f-bonus"[^>]*value="1,5"', html)
    assert 'class="rimuovi-fascia" aria-label="Togli la fascia 2"' in html
    assert re.search(r'<input aria-label="Band 1, average at least" ', _regole_node("rigaFascia(6, 1, 1)", "en"))
    # anche i quattro voti della prova: prima prendevano lo stesso titolo
    prova = _regole_node("votiProva([6.5, 6, 6.5, 7])")
    assert re.findall(r'aria-label="([^"]+)" id="pv\d"', prova) == [
        "Voto del portiere", "Voto del difensore 1", "Voto del difensore 2", "Voto del difensore 3"]
    regole = APP[APP.index("async function vistaRegole"):APP.index("async function vistaRegole") + 12000]
    assert "fascia(s[0], s[1])" not in regole and "numeraFasce()" in regole      # dopo «Togli» i numeri si rifanno


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
