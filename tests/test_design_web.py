"""Linee guida di design della web app (docs/DESIGN.md): controlli statici su stile.css e app.js.
La prova visiva si fa a mano a 390, 768 e 1280 px, tema chiaro e scuro."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

NODE = shutil.which("node")
APP = codice_web.app()
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
IMP_JS = codice_web.leggi("impostazioni.js")
IOS = server.WEB.parent.parent / "ios/Sources"                              # l'app iPhone, nella copia pubblica del repository


def test_aree_di_tocco_da_44px_anche_in_densita_compatta():
    assert not re.search(r'data-densita="compatta"\] \.chip \{[^}]*min-height: (?:[0-3]\d|4[0-3])px', CSS)
    assert re.search(r"\.proposta-r button\.nome-g \{ padding: 13px 4px; margin: -13px -4px; \}", CSS)
    imp = codice_web.leggi("impostazioni.js")
    assert 'class="voce voce-link"' in imp                                   # privacy, termini e crediti sono voci intere da toccare
    # ✕ dei fogli, ⇄ della formazione e caselle: 44 px veri, senza aree invisibili intorno
    assert re.search(r"\.foglio-chiudi \{[^}]*width: 44px; height: 44px", CSS) and "foglio-chiudi::after" not in CSS
    assert re.search(r"\.confronta-mini \{[^}]*width: 44px; height: 44px", CSS) and "confronta-mini::after" not in CSS
    assert re.search(r'\.interruttore input\[type="checkbox"\], \.scelte input\[type="checkbox"\] \{[^}]*width: 44px; height: 44px; margin: -9px', CSS)

def test_accesso_e_primo_avvio_centrati():
    # il margine di .carta spingeva la scheda d'accesso in basso. Grafica B (spec §9): il modulo non è più una carta, ha auto su
    # tutti i lati (al centro, in verticale e in orizzontale) e nessuna regola di .carta gli toglie il margine
    assert re.search(r"\n\.accesso-corpo \{[^}]*margin: auto;", CSS)
    assert "carta accesso-corpo" not in codice_web.app()
    assert ".onb-griglia" not in CSS and ".onb-blocco" in CSS

def test_schermi_grandi_ingranditi():
    # su PC e ultrawide l'interfaccia si ingrandisce a gradini; l'iPad (fino a 1366 px) non cambia
    for larghezza, z in (("1800", "1.15"), ("2400", "1.3"), ("3000", "1.5")):
        assert f"@media (min-width: {larghezza}px) {{ :root {{ --z: {z}; }}" in CSS
    assert "html { zoom: var(--z); }" in CSS
    # le misure in vh si dividono per l'ingrandimento, altrimenti i fogli e l'indice escono dallo schermo
    assert "calc(90vh / var(--z))" in CSS


def test_composizione_a_colonne_su_schermi_larghi():
    # Formazione 5:7 da 900 px (grafica B, spec C6: tests/test_grafica_b_web.py) e campo | elenco 1:2 da 1400 px, dove l'elenco è
    # abbastanza largo per le righe su una linea (Oggi resta 5:7), foglio come pannello laterale da 1100 px, gradino di
    # ingrandimento per i 5120 px
    assert re.search(r"@media \(min-width: 1400px\) \{\s*main \.colonne-campo \{ grid-template-columns: minmax\(0, 1fr\) minmax\(0, 2fr\); --quota-campo: calc\(1 / 3\);", CSS)
    assert not re.search(r"@media \(min-width: 1400px\) \{[^@]*main \.colonne-oggi[^{]*\{ grid-template-columns", CSS)
    assert "columns: 2" in CSS and "animation-name: sale-lato" in CSS
    assert "@media (min-width: 4400px) { :root { --z: 1.75; } }" in CSS

def test_scorciatoia_virgola_per_le_impostazioni():
    app = codice_web.app()
    assert 'ev.key === ","' in app and 'vai("impostazioni", undefined, { focoTitolo: true })' in app

def test_stile_ha_le_parentesi_graffe_in_pari():
    # una } mancante nasconde nel @media tutto quello che viene dopo
    assert CSS.count("{") == CSS.count("}")
    assert re.search(r"\n\}\n/\* ---- Lega: la mia squadra", CSS)


def test_barra_in_basso_con_fondo_pieno_e_spazio_riservato():
    # senza la sfocatura (grafica B) un fondo al 90% lascerebbe leggere il testo che scorre sotto la barra: il fondo è pieno,
    # a tutta larghezza, con un filo sopra (spec §6), e la barra arriva fino al bordo dello schermo
    barra = re.search(r"\n\.schede \{([^}]*)\}", CSS).group(1)
    assert "background: var(--superficie);" in barra and "border-top: 1px solid var(--filo);" in barra
    assert "left: 0; right: 0; bottom: 0;" in barra and "transparent" not in barra
    corpo = re.search(r"\nbody \{([^}]*)\}", CSS).group(1)
    assert "padding-bottom: calc(var(--barra) + env(safe-area-inset-bottom)" in corpo


def test_densita_sempre_compatta():
    """Dal 1/11/2026 la densità non si sceglie più (come sull'iPhone): sempre compatta, con le aree di tocco grandi."""
    assert 'pref("densita"' not in APP and 'radice.dataset.densita = "compatta";' in APP
    assert re.search(r'data-densita="compatta"\] \.voce \{[^}]*min-height: 48px', CSS)
    assert re.search(r'data-densita="compatta"\] \.chip \{[^}]*min-height: 44px', CSS)


def test_mercato_ha_quattro_voci_a_tutta_larghezza():
    """Da 6 a 4 schede: un controllo segmentato a tutta larghezza, senza voci tagliate."""
    assert 'class="segmenti" id="mercato-tab"' in APP
    voci = re.search(r"const TAB_MERCATO = (\[.*?\]);", APP).group(1)
    assert voci.count('["') == 4 and "Asta" not in voci
    assert re.search(r"\.segmenti button \{[^}]*flex: 1; min-width: 0; min-height: 44px", CSS)


def test_card_introduttive_compatte_con_spiegazione_chiusa():
    assert "const introCompatta = " in APP
    corpo = APP[APP.index("const introCompatta"):APP.index("async function tabConsigli")]
    assert "<details" in corpo and " open" not in corpo        # la spiegazione lunga è chiusa di default
    consigli = APP[APP.index("async function tabConsigli"):APP.index("async function datiCalendario")]
    assert "introCompatta(" in consigli and "<h2>Svincolati che migliorano" not in consigli


def test_formazione_controlli_compatti_una_riga_e_un_solo_pulsante_primario():
    blocco = APP[APP.index('<div class="etichetta-riga">${t("formazione.modulo")}</div>'):APP.index('<div class="campo">')]          # la legenda del campo viene subito dopo
    assert blocco.count('class="chips scorri" data-striscia') == 2          # moduli e stili: una riga che scorre
    assert 'id="modifica"' in blocco and 'class="bottone" id="modifica"' in blocco
    assert 'class="altre-azioni"' in blocco and 'id="copia"' in blocco and 'id="condividi"' in blocco
    assert re.search(r"\.chips\.scorri \{[^}]*flex-wrap: nowrap", CSS)


def test_la_scelta_attiva_e_lime_con_testo_scuro():
    assert re.search(r"\.chip\.attiva \{[^}]*var\(--capitano\)[^}]*var\(--capitano-testo\)", CSS)
    assert "--capitano-testo: #1a2600" in CSS
    # grafica B (spec §7.1): il lime chiaro da solo sta a 2,8:1 dal bianco, la scelta ha anche il bordo del colore del testo
    assert re.search(r"\.chip\.attiva \{[^}]*border: 2px solid var\(--testo\)", CSS)


def test_proposta_di_mercato_ha_il_guadagno_in_evidenza_e_nomi_protetti():
    consigli = APP[APP.index("async function tabConsigli"):APP.index("async function datiCalendario")]
    assert 'class="pr-num"' in consigli and "esc(p.entra.nome)" in consigli and "esc(p.esce.nome)" in consigli
    assert re.search(r"\.pr-num b \{[^}]*font-size: var\(--t-titolo\)", CSS)
    # il nome grande quanto quello delle righe dei giocatori (grafica B, spec §7.3 e §8.4: nomi dei giocatori a 15 px)
    assert re.search(r"\.proposta-r button\.nome-g \{[^}]*font-size: var\(--t-corpo\)", CSS)
    assert re.search(r"\.voce-g \.nome \{[^}]*font-size: var\(--t-corpo\)", CSS)


def test_rimborso_e_costo_dei_cambi_si_vedono_senza_mouse():
    """Sul telefono non c'è il passaggio del mouse: rimborso e costo stanno nel testo, mai in un `title`.
    Tre pezzi («crediti dopo», «rimborso», «costo») che a 390 px vanno a capo interi, senza spezzarsi in mezzo."""
    consigli = APP[APP.index("const soldiDelCambio"):APP.index("async function datiCalendario")]      # l'aiutante e la schermata
    assert "title=" not in consigli and "${soldiDelCambio(p)}" in consigli
    for chiave in ("crediti_dopo", "rimborso_n", "costo_n"):
        assert f't("mercato.{chiave}"' in consigli, chiave
    assert "r: p.rimborso" in consigli and "c: p.entra.quotazione" in consigli
    assert re.search(r"\.pr-sec \.nb \{[^}]*display: inline-block; max-width: 100%", CSS)    # intero se ci sta, a capo dentro solo se è più largo della riga
    testi = codice_web.leggi("testi.js")
    it, en = testi.split("\n  en: {", 1)
    for blocco, voci in ((it, ("crediti dopo {dopo}{no}", "rimborso {r}", "costo {c}")), (en, ("credits after {dopo}{no}", "refund {r}", "cost {c}"))):
        for chiave, testo in zip(("crediti_dopo", "rimborso_n", "costo_n"), voci):
            assert f'"mercato.{chiave}": "{testo}"' in blocco, chiave
    assert "mercato.rimborso_meno_costo" not in testi and "mercato.crediti_dettaglio" not in testi


def test_scala_tipografica_a_sette_livelli_nessun_testo_sotto_12_px():
    for livello in ("eroe", "titolo", "card", "valore", "corpo", "sec", "eti"):
        assert re.search(rf"--t-{livello}: \d+px", CSS), livello
    assert not re.search(r"font-size:\s*[0-9.]+px", CSS), "font-size solo con le variabili --t-*"
    assert not re.search(r"font-size:\s*[0-9.]+px", APP), "niente font-size in pixel nello stile in linea"
    assert not re.search(r"--t-\w+: (?:[0-9]|1[01])(?:\.\d+)?px", CSS)
    assert "body { font-size: 18px" not in CSS                    # il testo non cresce sugli schermi enormi


def test_bersagli_di_tocco_44_px_e_date_di_stato_dati_come_altrove():
    assert re.search(r"\.stepper button \{ width: 44px", CSS)               # i «−/+» delle regole
    assert re.search(r"\.proposta-r button\.nome-g \{ padding: 13px 4px; margin: -13px -4px", CSS)
    assert 'class="debole piccolo piede-legale"' not in APP and 'voceLegale("privacy"' in IMP_JS   # Privacy e Termini: voci intere in Impostazioni > Informazioni, un posto solo
    assert "esc(quando(a.quando))" in APP and "esc(quando(p.rilevato))" in APP       # «ieri 18:30», non «2026-10-26 23:55»


def test_colori_semantici_come_su_ios():
    scuro, chiaro = CSS.split("@media (prefers-color-scheme: light)")[0], CSS.split(':root[data-tema="chiaro"] {')[1]
    for nome, s, c in (("verde", "#3ddc97", "#0a7d4c"), ("rosso", "#ff6b5e", "#b3261e"), ("arancio", "#ffb04a", "#9c5400"),
                       ("capitano", "#d4f34a", "#86a800"), ("blu", "#62a9ff", "#1a5bb5")):
        assert f"--{nome}: {s}" in scuro and f"--{nome}: {c}" in chiaro, nome
    assert "--testo-2: #bccdc2" in scuro and "--testo-2: #46564d" in chiaro      # il grigio secondario unico, uguale a iOS (Tema.secondarioScuro / secondarioChiaro)
    # colore delle azioni: nello scuro uguale all'iPhone; nel chiaro verde bosco solo sulla web (spec grafica B §18, scelta 1b),
    # l'iPhone resta oliva #526600
    assert "--azione: #3ddc97" in scuro and "--azione: #0b6b3a" in chiaro and "#526600" not in CSS


def test_grigio_secondario_unico_niente_opacita_sul_testo_e_stessi_valori_di_ios():
    """Un solo grigio per i testi secondari: le righe «finita» e «rinviata» passano a --testo-2 invece di sbiadire con l'opacità
    (a .55 il grigio scendeva a ~2:1 in chiaro); l'immagine da condividere usa lo stesso grigio del tema scuro."""
    assert not re.search(r"\.partita(?:\.\w+)*\s*(?:\.\w+\s*)*\{[^}]*opacity\s*:", CSS)
    assert not re.search(r"\.ar-dubbio\.tolto\s*\{[^}]*opacity", CSS)
    assert re.search(r"\.partita\.giocata \.sq \{ color: var\(--testo-2\)", CSS) and re.search(r"\.partita\.rinviata \.sq \{ color: var\(--testo-2\)", CSS)
    assert "#9db4a5" not in APP and APP.count('"#bccdc2"') == 2
    ios = (server.WEB.parent.parent / "ios/Sources/Support/Design/Tema.swift")
    if ios.exists():                                                         # nella copia pubblica c'è anche l'app iPhone: i due valori devono coincidere
        tema = ios.read_text(encoding="utf-8").lower()
        assert "secondarioscuro: uint32 = 0xbccdc2" in tema and "secondariochiaro: uint32 = 0x46564d" in tema


def test_nomi_piccoli_del_mercato_hanno_area_di_tocco_larga_44px():
    regola = re.search(r"\.proposta-r button\.nome-g\.piccolo \{([^}]*)\}", CSS).group(1)
    assert "min-width: 44px" in regola and "padding: 13px 10px" in regola and "margin: -13px -10px" in regola


def _lum(esa):
    c = [int(esa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrasto(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_tema_chiaro_azioni_in_verde_bosco_con_contrasto_sufficiente_su_ogni_superficie():
    chiaro = CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0]
    assert "--azione: #0b6b3a; --azione-2: #08552e; --azione-testo: #ffffff;" in chiaro
    superfici = ["#ffffff", "#f4f5f2"]                                  # fondo e superficie della grafica B (spec §7.1)
    for s in superfici:
        assert _contrasto("#0b6b3a", s) >= 6, s                         # testo e link di azione: 6,6:1 sul bianco, 6,0:1 sulla superficie
        assert _contrasto("#1f8a4b", s) >= 3, s                         # il verde del campo si distingue dal fondo
    assert _contrasto("#ffffff", "#0b6b3a") >= 6.5                      # testo bianco sul pulsante pieno (6,6:1)
    assert _contrasto("#ffffff", "#08552e") >= 4.5                      # la variante più scura
    assert _contrasto("#1a2600", "#86a800") >= 4.5                      # testo scuro sulla scelta lime
    assert _contrasto("#86a800", "#ffffff") < 4.5                       # per questo il lime non e' mai testo
    assert _contrasto("#ffffff", "#1f8a4b") >= 3                        # nomi e numeri sul campo


def test_fondo_neutro_superficie_e_filo_della_grafica_b():
    """Grafica B (spec §7.1): fondo bianco nel chiaro e grigio quasi nero nello scuro, al posto del menta #eaf3ee e del verde
    scurissimo #07100b; `--superficie` (passaggio del mouse, pannello, barra) e `--filo` (separatori) nei tre blocchi dei temi."""
    t = _temi()
    assert (t["chiaro"]["--sfondo"], t["scuro"]["--sfondo"]) == ("#ffffff", "#121513")
    assert (t["chiaro"]["--superficie"], t["scuro"]["--superficie"]) == ("#f4f5f2", "#1a1e1c")
    assert (t["chiaro"]["--filo"], t["scuro"]["--filo"]) == ("#dde1dc", "#2e3430")
    assert t["scuro"]["--testo"] == "#e9edea" and "#eaf3ee" not in CSS and "#07100b" not in CSS      # niente fondo menta né verde scurissimo
    assert t["scuro"]["--solido"] == "#1a1e1c"
    sistema = _variabili(CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0])
    for nome in ("--sfondo", "--superficie", "--filo", "--solido", "--azione", "--azione-2"):
        assert sistema[nome] == t["chiaro"][nome], nome


def test_contrasti_wcag_aa_sul_fondo_e_sulla_superficie_nuovi():
    """WCAG 2.2 AA sui fondi della grafica B: scritte almeno 4,5:1 (1.4.3) e bordo dei campi almeno 3:1 (1.4.11), sia sul fondo
    della pagina sia sulla superficie, in chiaro e in scuro. Il filo dei separatori è decorativo: nessun minimo."""
    sotto = []
    for tema, v in _temi().items():
        for fondo in ("--sfondo", "--superficie", "--solido"):
            for scritta, minimo in (("--testo", 4.5), ("--testo-2", 4.5), ("--azione", 4.5), ("--verde", 4.5), ("--rosso", 4.5),
                                    ("--arancio", 4.5), ("--blu", 4.5), ("--giallo-testo", 4.5), ("--eti-verde", 4.5),
                                    ("--eti-arancio", 4.5), ("--eti-rosso", 4.5), ("--bordo-campo", 3)):
                c = _contrasto(v[scritta], v[fondo])
                if c < minimo:
                    sotto.append(f"{tema} {scritta} su {fondo}: {c:.2f}")
        for scritta, fondo in (("--azione-testo", "--azione"), ("--capitano-testo", "--capitano")):
            if _contrasto(v[scritta], v[fondo]) < 4.5:
                sotto.append(f"{tema} {scritta} su {fondo}")
    assert not sotto, sotto


def test_voce_scelta_dei_controlli_segmentati_si_vede_sul_fondo_pieno():
    """Con le superfici piene `--vetro-carta` è uguale al fondo: la voce scelta di Lingua, Tema e Dimensione del testo, che aveva
    quel fondo, nello scuro non si distingueva più dalla striscia (visto nelle foto). Grafica B (spec §8.8): la striscia non ha
    fondo (sta sul fondo della pagina) e la voce scelta è lime, come moduli e stili, con il bordo del colore del testo e la scritta
    scura; la scelta la dicono anche la scritta in grassetto e `aria-pressed`."""
    striscia = re.search(r"\n\.segmenti \{([^}]*)\}", CSS).group(1)
    attivo = re.search(r"\n\.segmenti button\.attivo \{([^}]*)\}", CSS).group(1)
    assert "background: none" in striscia
    assert "background: var(--capitano)" in attivo and "color: var(--capitano-testo)" in attivo and "inset 0 0 0 2px var(--testo)" in attivo
    for tema, v in _temi().items():
        fondo_striscia, fondo_attivo = _colore(v["--sfondo"])[0], _colore(v["--capitano"])[0]
        assert _contrasto_rgb(fondo_attivo, fondo_striscia) >= 1.25, tema
        assert _contrasto_rgb(_colore(v["--capitano-testo"])[0], fondo_attivo) >= 4.5, tema
        assert _contrasto_rgb(_colore(v["--testo"])[0], fondo_striscia) >= 3, tema      # il bordo della scelta si vede sul fondo


def test_colore_della_barra_del_browser_segue_il_tema():
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    assert '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff">' in html
    assert '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#121513">' in html
    man = json.loads((server.WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert man["background_color"] == man["theme_color"] == "#121513"


@pytest.mark.skipif(not NODE, reason="serve node")
def test_colore_della_barra_del_browser_segue_il_tema_scelto_a_mano():
    """Con il tema automatico le due righe `theme-color` tengono i loro colori (le sceglie il sistema con `media`); con un tema
    scelto a mano tutte e due prendono il fondo di quel tema. Prima l'app scriveva il menta #eaf3ee nella prima riga sola."""
    corpo = re.search(r"\nfunction applicaAspetto\(\) \{.*?\n\}", APP, re.S).group(0)
    codice = """
    const metas = [{ media: "(prefers-color-scheme: light)", content: "?" }, { media: "(prefers-color-scheme: dark)", content: "?" }];
    const document = { documentElement: { dataset: {}, style: {} }, querySelectorAll: () => metas, querySelector: () => metas[0] };
    let tema = "auto", sistemaChiaro = true;
    const leggiAspetto = () => ({ tema, testo: "1" });
    const matchMedia = () => ({ matches: sistemaChiaro });
    const segnaMovimento = () => {};
    """ + corpo + """
    const esiti = {};
    for (const [t, s] of [["auto", true], ["auto", false], ["chiaro", false], ["scuro", true]]) {
      tema = t; sistemaChiaro = s; applicaAspetto(); esiti[t + "-" + (s ? "sistema-chiaro" : "sistema-scuro")] = metas.map(m => m.content);
    }
    console.log(JSON.stringify(esiti));
    """
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "auto-sistema-chiaro": ["#ffffff", "#121513"], "auto-sistema-scuro": ["#ffffff", "#121513"],
        "chiaro-sistema-scuro": ["#ffffff", "#ffffff"], "scuro-sistema-chiaro": ["#121513", "#121513"]}


def _variabili(blocco):
    blocco = re.sub(r"/\*.*?\*/", "", blocco, flags=re.S)
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", blocco))


def _temi():
    """Le variabili del tema scuro (`:root`) e del chiaro (`:root[data-tema="chiaro"]` sopra lo scuro), con i `var()` risolti."""
    scuro = _variabili(CSS.split(":root {", 1)[1].split("\n}", 1)[0])
    chiaro = {**scuro, **_variabili(CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0])}

    def risolvi(v, nome):
        return re.sub(r"var\((--[\w-]+)\)", lambda m: risolvi(v, m.group(1)), v[nome]).strip()
    return {tema: {k: risolvi(v, k) for k in v} for tema, v in (("scuro", scuro), ("chiaro", chiaro))}


def _colore(testo):
    """«#rrggbb» o «rgba(r, g, b, a)» → ((r, g, b), alfa)."""
    testo = testo.strip()
    if testo.startswith("#"):
        return tuple(int(testo[i:i + 2], 16) for i in (1, 3, 5)), 1.0
    r, g, b, a = (float(x) for x in re.match(r"rgba\(([^)]*)\)", testo).group(1).split(","))
    return (r, g, b), a


def _sopra(colore, alfa, fondo):
    return tuple(alfa * c + (1 - alfa) * f for c, f in zip(colore, fondo))


def _contrasto_rgb(a, b):
    def lum(c):
        c = [x / 255 for x in c]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _fondi_delle_pillole(v):
    """I fondi veri sotto le etichette dei giocatori e i campi (misurati nel browser, issue #234). Dalla grafica B le sezioni non hanno
    fondo e le superfici sono piene: il fondo della pagina (Formazione, Rosa, Oggi), la riga sotto il mouse (`--superficie`) e il
    foglio della scheda del giocatore (le etichette sotto il nome stanno direttamente sul foglio). Il fondo del foglio si legge dal
    CSS: se cambia, il test segue. Non legge più `--vetro` e `--vetro-carta`, che la grafica B toglie."""
    foglio = re.search(r"\.foglio-corpo \{[^}]*background: var\((--[\w-]+)\)", CSS).group(1)
    return {"fondo della pagina": _colore(v["--sfondo"])[0], "riga sotto il mouse": _colore(v["--superficie"])[0],
            "foglio della scheda": _colore(v[foglio])[0]}


def _etichette():
    """Le etichette dei giocatori: nome → variabile della scritta. Dalla grafica B sono testo senza tinta sotto (spec §8.9)."""
    regole = {"verde": r"\n\.etichetta \{([^}]*)\}", "arancio": r"\n\.etichetta\.arancio \{([^}]*)\}",
              "rossa": r"\n\.etichetta\.rossa \{([^}]*)\}", "neutra": r"\n\.etichetta\.neutra \{([^}]*)\}"}
    etichette = {}
    for nome, regola in regole.items():
        corpo = re.search(regola, CSS).group(1)
        assert "color-mix" not in corpo and "rgba" not in corpo, nome           # nessuna tinta sotto la scritta: la scritta sta sul fondo
        etichette[nome] = re.search(r"(?<![\w-])color: var\((--[\w-]+)\);", corpo).group(1)
    return etichette


def test_etichette_dei_giocatori_almeno_4_5_su_ogni_fondo_in_chiaro_e_scuro():
    """Issue #234: nel tema chiaro la scritta delle pillole verdi e arancio stava a 4,0:1 e 4,4:1 sulla carta e a 3,5:1 e 3,8:1 sul
    foglio della scheda. Testo piccolo (13 px): serve 4,5:1 (WCAG 2.2, 1.4.3) su ogni fondo, in chiaro e in scuro. Dalla grafica B
    l'etichetta è testo colorato senza tinta: la scritta sta direttamente sul fondo, anche nella riga sotto il mouse."""
    sotto = []
    for tema, v in _temi().items():
        for nome, scritta in _etichette().items():
            for dove, fondo in _fondi_delle_pillole(v).items():
                c = _contrasto_rgb(_colore(v[scritta])[0], fondo)
                if c < 4.5:
                    sotto.append(f"{tema} {nome} su {dove}: {c:.2f}")
    assert not sotto, sotto


def test_etichetta_del_giocatore_scelto_nel_confronto_almeno_4_5():
    """Rilievo di axe (PR #381): nel Confronto a 390 e 768 px, in chiaro, «Titolare» sotto il giocatore consigliato stava a 4,14:1.
    L'etichetta verde sta sopra la tinta verde dello scelto, sul foglio. Sotto i due giocatori ci sono solo l'etichetta verde
    («Titolare») e la neutra."""
    quota = int(re.search(r"\.duello-giocatore\.scelto \{[^}]*background: color-mix\(in srgb, var\(--verde\) (\d+)%, transparent\)",
                          CSS).group(1)) / 100
    sotto = []
    for tema, v in _temi().items():
        scelto = _sopra(_colore(v["--verde"])[0], quota, _fondi_delle_pillole(v)["foglio della scheda"])
        for nome in ("verde", "neutra"):
            c = _contrasto_rgb(_colore(v[_etichette()[nome]])[0], scelto)
            if c < 4.5:
                sotto.append(f"{tema} {nome}: {c:.2f}")
    assert not sotto, sotto


def test_scritta_delle_pillole_uguale_nei_due_temi_chiari_e_su_ios():
    """Il tema chiaro sta due volte nel CSS (sistema e scelta a mano): le scritte delle pillole devono essere le stesse. L'arancio e il
    rosso delle pillole dell'iPhone (`Tema` in Tema.swift) sono gli stessi della web, in chiaro e in scuro."""
    sistema = _variabili(CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0])
    a_mano = _variabili(CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0])
    for nome in ("--eti-verde", "--eti-arancio", "--eti-rosso", "--verde"):
        assert sistema.get(nome) and sistema.get(nome) == a_mano.get(nome), nome
    ios = IOS / "Support/Design/Tema.swift"
    if ios.exists():                                                         # nella copia pubblica c'è anche l'app iPhone
        tema = ios.read_text(encoding="utf-8").lower()
        temi = _temi()
        # scritta delle pillole verdi, arancio e rosse; il fondo verde (--verde al 16%, sull'iPhone `Color.positivo` al 14%, #242)
        for variabile, swift in (("--eti-verde", "pillolapositivo"), ("--eti-arancio", "pillolaattenzione"),
                                 ("--eti-rosso", "pillolamalus"), ("--verde", "positivo")):
            for nome_tema, suffisso in (("chiaro", "chiaro"), ("scuro", "scuro")):
                valore = temi[nome_tema][variabile].lstrip("#")
                assert re.search(rf"\b{swift}{suffisso}: uint32 = 0x{valore}\b", tema), (variabile, nome_tema)


def test_pillole_dei_giocatori_stesso_colore_su_web_e_ios():
    """Issue #242: «Probabile titolare» (e «Ha giocato», «Partita in corso») era una pillola verde sulla web e grigia sull'iPhone. Il
    colore viene dal tono: quello del server (`CLASSE_TONO`) o, senza etichetta, quello del ripiego (`TITOLARITA`, `STATO_PARTITA`).
    L'iPhone usa gli stessi quattro toni (`Etichetta.Tono`) con le stesse scelte: verde, grigio, arancio, rosso."""
    ios = IOS / "Domain/GiocatoreEtichette.swift"
    if not ios.exists():
        return
    swift = ios.read_text(encoding="utf-8")
    da_classe = {"": "positivo", "arancio": "attenzione", "rossa": "negativo", "neutra": "neutro"}   # classi di `.etichetta`
    for nome_js, nome_swift in (("TITOLARITA", "nomiTitolarita"), ("STATO_PARTITA", "nomiStatoPartita")):
        js = re.search(rf"const {nome_js} = \{{(.*?)\}};", APP, re.S).group(1)
        web = {chiave: da_classe[classe] for chiave, classe in re.findall(r'(\w+): \[[^\]]*?, "(\w*)"\]', js)}
        corpo = re.search(rf"static let {nome_swift}: [^=]+= \[(.*?)\n    \]", swift, re.S).group(1)
        iphone = dict(re.findall(r'"(\w+)": \("[^"]*", \.(\w+)\)', corpo))
        assert web and iphone == web, (nome_js, web, iphone)
    # il tono del server: stessa classe per ogni tono, e uno sconosciuto vale neutro (`classeTono`: `?? "neutra"`)
    classe_tono = dict(re.findall(r'(\w+): "(\w*)"', re.search(r"const CLASSE_TONO = \{([^}]*)\}", APP).group(1)))
    assert 'CLASSE_TONO[et && et.tono] ?? "neutra"' in APP
    corpo = re.search(r"init\(server: String\?\) \{(.*?)\n        \}", swift, re.S).group(1)
    tono_iphone, altrimenti = dict(re.findall(r'case "(\w+)": self = \.(\w+)', corpo)), re.search(r"default: self = \.(\w+)", corpo).group(1)
    assert classe_tono and {tono: tono_iphone.get(tono, altrimenti) for tono in classe_tono} == {t: da_classe[c] for t, c in classe_tono.items()}
    assert altrimenti == da_classe["neutra"] and set(tono_iphone) <= set(classe_tono)


def test_bordo_dei_campi_almeno_3_a_1_in_chiaro_e_scuro():
    """Issue #285: campi di testo, menu e caselle di testo avevano il bordo `--bordo` (il filo sottile delle carte): 1,2:1 nel chiaro e
    1,4:1 nello scuro, misurato in Registrati; il campo si riconosceva solo dall'etichetta. WCAG 2.2, 1.4.11: il bordo che fa
    riconoscere il campo vale almeno 3:1 sia con il fondo del campo sia con quello che gli sta intorno, su ogni superficie."""
    for regola in (r"\n\.campo-testo, select, textarea \{([^}]*)\}", r"\n\.stepper \{([^}]*)\}", r"\n\.menu-scelta \{([^}]*)\}"):
        corpo = re.search(regola, CSS).group(1)
        assert "border: 1px solid var(--bordo-campo)" in corpo, regola
    sistema = _variabili(CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0])
    a_mano = _variabili(CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0])
    assert sistema.get("--bordo-campo") and sistema["--bordo-campo"] == a_mano.get("--bordo-campo")
    quota = int(re.search(r"\n\.campo-testo, select, textarea \{[^}]*background: color-mix\(in srgb, var\(--solido\) (\d+)%, transparent\)", CSS).group(1)) / 100
    sotto = []
    for tema, v in _temi().items():
        bordo, solido = _colore(v["--bordo-campo"])[0], _colore(v["--solido"])[0]
        for dove, fondo in _fondi_delle_pillole(v).items():
            for lato, colore in (("intorno", fondo), ("dentro", _sopra(solido, quota, fondo))):
                c = _contrasto_rgb(bordo, colore)
                if c < 3:
                    sotto.append(f"{tema} {dove} {lato}: {c:.2f}")
    assert not sotto, sotto


def test_pulsanti_pieni_almeno_4_5_e_uguali_su_web_e_ios():
    """Issue #248: sull'iPhone, nel tema scuro, la scritta dei pulsanti pieni era bianca sul verde chiaro (1,77:1). La web scrive con
    --azione-testo (verde quasi nero nello scuro, bianco nel chiaro) sopra --azione: almeno 4,5:1 in tutti e due i temi. L'iPhone usa
    gli stessi colori: fondo `Accento.verde` (Aspetto.swift), scritta `Tema.scrittaPulsante*`. Dalla grafica B il fondo del tema
    chiaro è il verde bosco solo sulla web (spec §18, scelta 1b): nel chiaro si confronta solo la scritta, nello scuro tutti e due."""
    sistema = _variabili(CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0])
    a_mano = _variabili(CSS.split(':root[data-tema="chiaro"] {')[1].split("}")[0])
    for nome in ("--azione", "--azione-testo"):
        assert sistema.get(nome) and sistema.get(nome) == a_mano.get(nome), nome
    temi = _temi()
    for nome_tema, v in temi.items():
        c = _contrasto_rgb(_colore(v["--azione-testo"])[0], _colore(v["--azione"])[0])
        assert c >= 4.5, (nome_tema, round(c, 2))
    tema, aspetto = IOS / "Support/Design/Tema.swift", IOS / "Support/Aspetto.swift"
    if not (tema.exists() and aspetto.exists()):
        return
    tema, aspetto = tema.read_text(encoding="utf-8").lower(), aspetto.read_text(encoding="utf-8").lower()
    for nome_tema in ("chiaro", "scuro"):
        scritta, fondo = (temi[nome_tema][x].lstrip("#") for x in ("--azione-testo", "--azione"))
        assert re.search(rf"\bscrittapulsante{nome_tema}: uint32 = 0x{scritta}\b", tema), nome_tema
        verde = re.search(rf"var {nome_tema}: uicolor \{{.*?case \.verde: return self\.da\(0x(\w{{6}})\)", aspetto, re.S).group(1)
        if nome_tema == "scuro":
            assert verde == fondo, nome_tema
        else:                                                           # l'iPhone resta oliva: la sua scritta bianca regge anche lì
            assert _contrasto_rgb(_colore("#" + scritta)[0], _colore("#" + verde)[0]) >= 4.5, verde


def test_pulsanti_pieni_dell_iphone_passano_tutti_dallo_stesso_stile():
    """#248: lo stile di sistema dei pulsanti pieni (`.glassProminent`, `.borderedProminent`) scrive bianco anche sul verde chiaro dello
    scuro. Ogni pulsante pieno passa da `pulsanteVetro(prominente: true)` (Vetro.swift), che mette la scritta `Color.scrittaPulsante`
    (spento: il grigio dell'app, `Color.testoSecondario`)."""
    vetro = IOS / "Support/Design/Vetro.swift"
    if not vetro.exists():
        return
    fuori = [f"{p.relative_to(IOS).as_posix()}:{n}" for p in sorted(IOS.rglob("*.swift")) if p != vetro
             for n, riga in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if re.search(r"\.(bordered|glass)Prominent\b", riga)]
    assert not fuori, fuori
    testo = vetro.read_text(encoding="utf-8")
    stile = re.search(r"struct PulsantePieno: ViewModifier \{(.*?)\n\}", testo, re.S)
    assert stile and "modifier(PulsantePieno())" in testo
    for pezzo in (".glassProminent", ".borderedProminent", "Color.scrittaPulsante", "Color.testoSecondario", ".isEnabled"):
        assert pezzo in stile.group(1), pezzo


def test_pulsanti_link_e_azioni_usano_la_variabile_azione_non_il_lime():
    assert re.search(r"\.bottone \{[^}]*background: var\(--azione\);[^}]*color: var\(--azione-testo\)", CSS)   # pieno, senza lucido (docs/STILE-SENZA-AI.md)
    # grafica B (spec §8.7): l'azione scritta nella riga ha il colore delle azioni; il secondario da solo ha la scritta del testo e
    # il bordo dei controlli: né l'uno né l'altro usa il lime, che resta la scelta
    assert re.search(r"\.azione-testo \{[^}]*color: var\(--azione\)", CSS)
    assert re.search(r"\.bottone\.secondario \{[^}]*border-color: var\(--bordo-campo\)[^}]*color: var\(--testo\)", CSS)
    assert not re.search(r"\.(?:bottone|azione-testo)[^{]*\{[^}]*var\(--capitano\)", CSS)
    assert re.search(r"\.scheda\.attiva::before \{[^}]*background: var\(--azione\)", CSS)        # la linea della scheda attiva
    assert re.search(r"\.testo-lungo a[^{]*\{ color: var\(--azione\)", CSS)
    assert '"--azione-testo"' not in APP                                # niente colori a scelta: le azioni hanno sempre i colori del marchio
