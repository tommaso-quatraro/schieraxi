"""Focus da tastiera in vista e bersagli da 44 px sulla web (issue #280 e #289, WCAG 2.2 2.4.11 e 2.5.8).
Su main, nel browser (dati verosimili delle fotografie, 390/768/1440 px, testo normale e «Molto grande», Tab e Maiusc+Tab):
- Oggi a 390 px: «Apri la formazione» prendeva il focus sotto la barra in basso (0 punti visibili su 25); in Formazione, andando
  indietro con Maiusc+Tab, le pedine e i pulsanti ⇄ restavano sotto la testata fissa. Nel CSS non c'era `scroll-padding`;
- le pagine Privacy, Termini e Crediti avevano «Torna a SchieraXI» e i collegamenti in fondo alti 20 px;
- nelle Regole i «−» e «+» di «Prova la difesa» si stringevano a 26 px (due contatori in una griglia `auto` più stretta di loro);
- la scelta «Qual è la tua squadra?» di Aggiorna le rose è un'etichetta con dentro un radio: prendeva `aria-pressed`, che su
  un'etichetta non è ammesso (axe `aria-allowed-attr`, critical).
La prova vera è nel browser (collaudo della pull request); qui le regole e il codice di app.js eseguito con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server, testi_legali

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
SENZA_COMMENTI = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
ANTEPRIMA = (server.WEB / "anteprima.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _regole(selettore: str, testo: str = SENZA_COMMENTI) -> str:
    """Tutti i corpi delle regole il cui elenco di selettori contiene proprio `selettore`."""
    corpi = [corpo for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", testo) if selettore in [s.strip() for s in sel.split(",")]]
    assert corpi, f"manca la regola {selettore}"
    return " ".join(corpi)


def _blocco(apertura: str) -> str:
    i = SENZA_COMMENTI.index(apertura) + len(apertura)
    livello, j = 1, i
    while livello:
        livello += {"{": 1, "}": -1}.get(SENZA_COMMENTI[j], 0)
        j += 1
    return SENZA_COMMENTI[i:j - 1]


# ---------------------------------------------------------------- #280: il focus non finisce sotto testata e barra

def test_il_browser_porta_il_focus_tra_la_testata_e_la_barra():
    """`scroll-padding` sulla radice: il browser porta l'elemento con il focus dentro la finestra lasciando fuori la testata (in
    alto, ferma da 900 px, con la sua altezza vera) e la barra in basso (fissa sul bordo, alta `--barra` più lo spazio del
    sistema). Da 900 px le schede stanno nella testata: in basso basta poco."""
    radice = re.search(r"\nhtml \{([^}]*scroll-padding[^}]*)\}", SENZA_COMMENTI)
    assert radice, "manca scroll-padding su html"
    alto = re.search(r"scroll-padding-top: calc\(var\(--alto-testata, (\d+)px\) \+ (\d+)px\)", radice.group(1))
    basso = re.search(r"scroll-padding-bottom: calc\(var\(--barra\) \+ env\(safe-area-inset-bottom\) \+ (\d+)px\)", radice.group(1))
    assert alto and basso, radice.group(1)
    barra = re.search(r"\n\.schede \{([^}]*)\}", SENZA_COMMENTI).group(1)
    assert "bottom: 0;" in barra and "height: calc(var(--barra) + env(safe-area-inset-bottom));" in barra   # la barra è alta così, dal bordo
    assert int(basso.group(1)) >= 8                                             # sopra la barra resta almeno un filo di pagina
    assert int(alto.group(2)) >= 8
    largo = _blocco("@media (min-width: 900px) {")
    assert re.search(r"(?:^|\n)\s*html \{ scroll-padding-bottom: \d+px; \}", largo)
    assert re.search(r"(?:^|\n)\s*\.testata \{[^}]*position: sticky; top: 0;", largo)    # la testata ferma: --alto-testata la misura


def test_con_salva_in_basso_il_focus_resta_sopra_il_pulsante():
    """Regole: con una modifica da salvare il pulsante «Salva» galleggia sopra la barra (sticky): il margine in basso cresce."""
    corpo = _regole("html:has(.salva-fisso:not([hidden]))")
    m = re.search(r"scroll-padding-bottom: calc\(var\(--barra\) \+ env\(safe-area-inset-bottom\) \+ (\d+)px\)", corpo)
    assert m and int(m.group(1)) >= 24 + 46 + 8                                 # posto del pulsante (sticky a +24 px, alto 46) e un filo


def _codice_testata(posizione: str, altezza: int) -> str:
    pezzo = APP[APP.index("(function altezzaTestata()"):]
    pezzo = pezzo[:pezzo.index("})();") + len("})();")]
    return "\n".join([
        "const scritte = []; let richiamo = null;",
        f"const testata = {{ offsetHeight: {altezza}, stile: {{ position: {json.dumps(posizione)} }} }};",
        "const document = { querySelector: s => (s === '.testata' ? testata : null),",
        "  documentElement: { style: { setProperty: (k, v) => scritte.push([k, v]) } } };",
        "const getComputedStyle = el => el.stile;",
        "class ResizeObserver { constructor(f) { richiamo = f; } observe(el) { this.el = el; } }",
        pezzo,
        "testata.offsetHeight = 118; richiamo();",                              # il nome va a capo: la testata cresce
        "testata.stile.position = 'relative'; richiamo();",                     # sotto i 320 px la testata scorre via con la pagina
        "console.log(JSON.stringify(scritte));",
    ])


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_l_altezza_della_testata_segue_quella_vera():
    """app.js scrive in --alto-testata l'altezza della testata quando resta ferma in alto, e la aggiorna quando cambia (nome che va
    a capo, testo grande, rotazione del telefono); quando la testata scorre via con la pagina scrive 0."""
    r = subprocess.run([NODE, "-"], input=_codice_testata("sticky", 77), capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == [["--alto-testata", "77px"], ["--alto-testata", "118px"], ["--alto-testata", "0px"]]


def _codice_ferme(dopo: str, top_da_ferma: str = "76px") -> str:
    pezzo = APP[APP.index("const FERME = "):]
    pezzo = pezzo[:pezzo.index("\n}\n") + 3]
    return "\n".join([
        "let innerHeight = 390;",
        "const el = (nome, alto, position, z = 1) => ({ nome, offsetHeight: alto, stile: { position, top: '76px' },",
        "  getBoundingClientRect: () => ({ height: alto * z }), classi: new Set(),",
        "  classList: { contains(c) { return this.o.classi.has(c); }, toggle(c, si) { this.o.tocchi++; if (si) this.o.classi.add(c); else this.o.classi.delete(c); } },",
        "  tocchi: 0 });",
        "const tutti = [el('campo', 700, 'sticky'), el('colonna', 250, 'sticky'), el('ingrandita', 250, 'sticky', 1.25), el('ferma no', 900, 'static')];",
        "tutti.forEach(x => { x.classList.o = x; });",
        "const radice = { classi: new Set(), stile: { scrollPaddingBottom: '16px' } };",          # in basso niente barra (da 900 px è a sinistra)
        "const document = { querySelectorAll: () => tutti, documentElement: radice };",
        f"const getComputedStyle = x => (x.classi.has('non-ferma') ? {{ position: 'static', top: {json.dumps(top_da_ferma)} }} : x.stile);",
        pezzo,
        dopo,
    ])


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_le_colonne_ferme_restano_ferme_solo_se_ci_stanno_nello_schermo():
    """iPad verticale con il testo grande (768 e 820 px), telefono in orizzontale (844 × 390) e PC con la finestra bassa: la prima
    colonna di Oggi, il campo della Formazione e l'elenco di Impostazioni restavano fermi in alto (sticky) anche se più alti dello
    schermo, quindi il loro fondo («Apri la formazione», il portiere, «Aggiorna le rose») restava sotto la barra o fuori dallo
    schermo, con il Tab e anche scorrendo. app.js li lascia fermi solo se ci stanno; se no scorrono con la pagina (`non-ferma`)."""
    fuori = subprocess.run([NODE, "-"], input=_codice_ferme(
        "controllaFerme(); const a = tutti.map(x => [x.nome, x.classi.has('non-ferma')]);"
        "const tocchi = () => tutti.reduce((n, x) => n + x.tocchi, 0), prima = tocchi(); controllaFerme(); const ripetuto = tocchi() - prima;"
        "innerHeight = 1000; controllaFerme(); const b = tutti.map(x => [x.nome, x.classi.has('non-ferma')]);"
        "console.log(JSON.stringify({ a, b, ripetuto }));"), capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert fuori.returncode == 0, fuori.stderr
    r = json.loads(fuori.stdout.strip().splitlines()[-1])
    # 390 px di schermo: il campo (700) non ci sta; la colonna (250 + 76) sì; ingrandita al 125% (312 + 95) no; quella non sticky non si tocca
    assert r["a"] == [["campo", True], ["colonna", False], ["ingrandita", True], ["ferma no", False]]
    # rifatto il controllo senza cambiamenti, la classe non si tocca (sincronizzaAria osserva le classi e ripartirebbe ogni volta)
    assert r["ripetuto"] == 0
    # schermo più alto (o finestra allargata): tornano ferme
    assert r["b"] == [["campo", False], ["colonna", False], ["ingrandita", False], ["ferma no", False]]
    assert re.search(r"\n\.non-ferma \{ position: static !important; \}", SENZA_COMMENTI)
    for selettore in (".colonne-oggi > .col:first-child", ".colonne-campo .campo-fermo", ".imp-elenco"):
        assert selettore in re.search(r'const FERME = "([^"]+)"', APP).group(1), selettore


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_le_colonne_ferme_non_oscillano_se_il_browser_da_top_auto():
    """Quando la colonna non è più ferma (`position: static`) qualche browser (Safari) può dare `top: auto`: contato come 0, la colonna
    sembrerebbe starci, tornerebbe ferma e al giro dopo di nuovo no, avanti e indietro. Vale il `top` di quando era ferma."""
    fuori = subprocess.run([NODE, "-"], input=_codice_ferme(
        "innerHeight = 400; tutti.splice(0, tutti.length, el('campo', 350, 'sticky')); tutti[0].classList.o = tutti[0];"
        "const stati = []; for (let i = 0; i < 4; i++) { controllaFerme(); stati.push(tutti[0].classi.has('non-ferma')); }"
        "console.log(JSON.stringify({ stati, tocchi: tutti[0].tocchi }));", top_da_ferma="auto"),
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert fuori.returncode == 0, fuori.stderr
    r = json.loads(fuori.stdout.strip().splitlines()[-1])
    # 350 + 76 + 16 = 442 > 400: non ci sta, e resta così (con «auto» preso per 0 sarebbe 366: ferma, poi no, poi ferma…)
    assert r == {"stati": [True, True, True, True], "tocchi": 1}


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_le_strisce_scorrevoli_portano_in_vista_la_voce_con_il_focus():
    """Formazione a 390 e 768 px: con il tasto Tab il modulo «5-3-2» restava per metà fuori dalla sua striscia (Chrome fa scorrere la
    striscia solo se la voce è tutta fuori). La striscia porta in vista la voce che prende il focus, con un margine che la tiene
    fuori dal bordo sfumato."""
    pezzo = APP[APP.index("function striscia(el)"):]
    pezzo = pezzo[:pezzo.index("\n}\n") + 3]
    codice = "\n".join([
        "const ascolta = {}, chiamate = [];",
        "const voce = { scrollIntoView: o => chiamate.push(o) };",
        "const el = { dataset: {}, style: { setProperty() {} }, scrollLeft: 0, clientWidth: 300, scrollWidth: 700,",
        "  querySelector: () => null, contains: x => x === voce, addEventListener: (tipo, f) => { ascolta[tipo] = f; } };",
        pezzo,
        "striscia(el);",
        "ascolta.focusin({ target: { closest: s => (s === 'button' ? voce : null) } });",
        "console.log(JSON.stringify(chiamate));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == [{"block": "nearest", "inline": "nearest"}]
    for striscia in (".chips.scorri", ".segmenti.scorri"):
        assert re.search(r"scroll-padding-inline: \d+px", _regole(striscia)), striscia


# ---------------------------------------------------------------- #289: bersagli da 44 px e aria-pressed

def test_collegamenti_delle_pagine_legali_alti_44_px():
    """«Torna a SchieraXI» e i collegamenti in fondo (`nav.piede-legale`) non stanno dentro una frase: sono bersagli da soli e
    misurano almeno 44 × 44 px (docs/DESIGN.md). Il CSS li trova con la forma della pagina scritta da fanta/testi_legali.py."""
    corpo = _regole(".piede-legale a")
    assert corpo == _regole(".pagina-testo #contenuto > p:first-child > a")
    for proprieta in ("display: inline-flex", "align-items: center", "min-height: 44px", "min-width: 44px"):
        assert proprieta in corpo, proprieta
    for quale in ("privacy", "termini", "crediti"):
        html = testi_legali.pagina(quale)
        assert '<body class="pagina-testo">' in html and re.search(r'<main class="carta testo-lungo" id="contenuto">\s*<p><a href="/">', html)
        assert '<nav class="piede-legale"' in html


def test_i_meno_e_piu_delle_regole_restano_da_44_px():
    """I due contatori di «Prova la difesa» stavano in una griglia di due colonne `auto`: a 320 px, più stretta di loro, i pulsanti
    si stringevano a 26 px. Ora vanno a capo (flex con wrap) e i pulsanti non si stringono mai; se il posto proprio non basta
    (pagina da 160 px) si stringe la casella del numero."""
    prova = _regole(".prova-voti")
    assert "display: flex" in prova and "flex-wrap: wrap" in prova and "grid-template-columns" not in prova
    assert "flex: none" in _regole(".stepper button")
    assert "max-width: 100%" in _regole(".stepper")
    assert "min-width: 0" in _regole(".stepper input")


def test_aria_pressed_solo_sui_pulsanti():
    """sincronizzaAria mette `aria-pressed` alle scelte (moduli, stili, segmenti): solo ai pulsanti. «Qual è la tua squadra?» è
    un'etichetta (`<label class="chip">`) con dentro un radio, che dice già se è scelta."""
    m = re.search(r'document\.querySelectorAll\("([^"]+)"\)\.forEach\(b => \{\s*b\.setAttribute\("aria-pressed"', APP)
    assert m, "manca sincronizzaAria"
    for parte in m.group(1).split(","):
        assert re.match(r"\s*(button\b|\.segmenti button\b)", parte), parte
    assert re.search(r'<label class="chip [^>]*><input type="radio" name="ar-mia"', ANTEPRIMA)
    assert not re.search(r"<label[^>]*aria-pressed", ANTEPRIMA + APP)
