"""Squadra (e Altro) con il menu e la pagina affiancati sugli schermi larghi, Elenco dei giocatori e rosa con l'intestazione
ferma (grafica B, PR 10; spec §5 C7 e C10, §9 «Squadra e Altro»). Controlli su app.js e stile.css e prove con node del codice
vero di app.js (le misure nel browser sono nella descrizione della pull request)."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _funzione(nome: str) -> str:
    i = re.search(rf"\n(?:async )?function {nome}\(", APP).start()
    return APP[i:APP.index("\n}\n", i) + 3]


def _riga(inizio: str) -> str:
    return re.search(r"\n" + re.escape(inizio) + r"[^\n]*\n", APP).group(0)


def _blocco(intestazione: str) -> str:
    """Tutti i blocchi CSS che iniziano con `intestazione` (per esempio «@media (min-width: 1100px) {»), uniti."""
    pezzi, da = [], 0
    while (i := CSS.find("\n" + intestazione, da)) != -1:
        livello, j = 0, i + len(intestazione)
        for j in range(CSS.index("{", i), len(CSS)):
            livello += {"{": 1, "}": -1}.get(CSS[j], 0)
            if livello == 0:
                break
        pezzi.append(CSS[i:j])
        da = j
    return "\n".join(pezzi)


def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- C10: menu a sinistra, pagina a destra

def test_squadra_e_altro_a_due_colonne_sul_pc():
    assert re.search(r"@media \(min-width: 1100px\) \{[^@]*\.lega-colonne \{[^}]*grid-template-columns: 280px minmax\(0, 1fr\)", CSS)
    corpo = _funzione("vistaLega")
    assert 'class="lega-colonne"' in corpo and "aria-current" in corpo


def test_sotto_i_1100_px_una_cosa_alla_volta_senza_scorrere_di_lato():
    """Sotto i 1100 px il menu, oppure la pagina con «‹ Squadra» (come oggi); una colonna `minmax(0, 1fr)`, mai larga quanto il
    contenuto più lungo (issue #288 delle Impostazioni). Da 1100 px il menu resta fermo sotto la testata se ci sta nello schermo
    (controllaFerme) e «‹ Squadra» non serve."""
    base = re.search(r"\n\.lega-colonne \{([^}]*)\}", CSS)
    assert base and "grid-template-columns: minmax(0, 1fr)" in base.group(1)
    stretta = _blocco("@media (max-width: 1099.98px) {")
    assert '.lega-colonne[data-aperto="1"] > .lega-menu { display: none; }' in stretta
    assert '.lega-colonne[data-aperto="0"] > .lega-pagina { display: none; }' in stretta
    larga = _blocco("@media (min-width: 1100px) {")
    assert re.search(r"\.lega-menu \{[^}]*position: sticky; top: calc\(var\(--alto-ferma\) \+ 16px\)", larga)
    assert re.search(r"\.lega-indietro \{ display: none; \}", larga)
    assert ".lega-menu" in re.search(r'const FERME = "([^"]+)"', APP).group(1)


def test_la_voce_aperta_si_riconosce_anche_senza_il_colore():
    """La voce aperta ha aria-current="page" (la dice il lettore di schermo) e, a vista, il testo pieno e una linea di 3 px a
    sinistra nel colore delle azioni, come la linea sotto la scheda accesa in testata: non solo un fondo colorato."""
    regola = re.search(r'\n\.lega-voce\[aria-current="page"\] \{([^}]*)\}', CSS)
    assert regola and "inset 3px 0 0 var(--azione)" in regola.group(1)
    assert ".imp-voce.attiva" in CSS                                   # le Impostazioni restano come sono (PR 12)


@pytest.mark.skipif(not NODE, reason="serve node")
def test_il_menu_segna_solo_la_voce_aperta():
    codice = "\n".join([
        "const t = k => k;",
        _funzione("menuLega"),
        """const voci = [{ id: "squadre", nome: "Squadre e rose", sub: "La tua squadra" }, { id: "osservati", nome: "Seguiti", sub: "Chi segui" }];
console.log(JSON.stringify([menuLega(voci, "osservati", "Voci della squadra"), menuLega(voci, null, "Voci della squadra")]));""",
    ])
    aperta, nessuna = _node(codice)
    assert aperta.count('aria-current="page"') == 1
    assert re.search(r'<button class="voce lega-voce" type="button" data-lega="osservati" aria-current="page">', aperta)
    assert '<nav class="lega-menu" aria-label="Voci della squadra">' in aperta
    assert "aria-current" not in nessuna and nessuna.count('type="button"') == 2


@pytest.mark.skipif(not NODE, reason="serve node")
def test_le_pagine_di_mercato_si_aprono_accanto_al_menu_solo_da_1100_px():
    """Da 1100 px Cambi consigliati, Seguiti, Elenco dei giocatori e Calendario si aprono a destra del menu, che resta in vista;
    sotto i 1100 px portano alla loro pagina, come oggi. Le voci di Altro che portano altrove (Scambi, Regole, Novità) non cambiano."""
    codice = "\n".join([
        _riga("const TAB_MERCATO = "), _riga("const nellaPagina = "),
        """const vai = () => {};
const prove = [[{ id: "squadre" }, true], [{ id: "squadre" }, false], [{ id: "osservati", vai }, true], [{ id: "osservati", vai }, false],
  [{ id: "calendario", vai }, true], [{ id: "giocatori", vai }, true], [{ id: "consigli", vai }, true], [{ id: "scambi", vai }, true],
  [{ id: "regole", vai }, true], [{ id: "diario" }, false]];
console.log(JSON.stringify(prove.map(([v, largo]) => nellaPagina(v, largo))));""",
    ])
    assert _node(codice) == [True, True, True, False, True, True, True, False, False, True]


def test_mercato_da_1100_px_si_apre_dentro_squadra():
    """Un collegamento a una pagina di Mercato (?vista=mercato&scheda=calendario, «Confronta» dalla scheda, Indietro) da 1100 px
    apre Squadra con quella voce a destra; sotto i 1100 px la pagina di Mercato con le sue quattro sezioni, come oggi."""
    corpo = _funzione("vistaMercato")
    assert 'if (legaLarga()) { stato.legaTorna = stato.mercatoTab; return vistaLega("squadra"); }' in corpo
    assert 'class="segmenti" id="mercato-tab"' in corpo
    lega = _funzione("vistaLega")
    assert '<div id="mercato-corpo"></div>' in lega and "caricaMercato();" in lega
    assert "chiudiPannelloAffiancato();" in lega              # il pannello del giocatore si chiude con la pagina da cui è nato
    assert "indirizzoLega(" in lega
    # tornando alla lista dopo il confronto, l'elenco si ridisegna anche quando è aperto accanto al menu
    assert 'if (stato.vista === "mercato" && stato.mercatoTab === "giocatori") caricaMercato();' in APP


@pytest.mark.skipif(not NODE, reason="serve node")
def test_la_voce_aperta_accanto_al_menu_scrive_il_suo_indirizzo():
    """Da Seguiti a Calendario con un clic: l'indirizzo diventa quello del Calendario (Indietro torna a Seguiti, un ricaricamento
    riapre il Calendario); la stessa voce non aggiunge voci alla cronologia; tornare a «Squadre e rose» riporta ?vista=squadra.
    La voce di Squadra o di Altro sta nello stato della cronologia (l'indirizzo non la dice): con Indietro dal Calendario si torna a
    «Squadre e rose», non alla voce dell'ultima volta. Due voci con lo stesso indirizzo non aggiungono voci alla cronologia
    (Indietro non cambierebbe niente): si corregge quella di adesso."""
    codice = "\n".join([
        "const stato = { vista: \"squadra\" }; const chiamate = [];",
        "const location = { pathname: \"/\", search: \"?vista=squadra\" };",
        "const vaiA = u => { const x = new URL(u, \"http://x\"); location.pathname = x.pathname; location.search = x.search; };",
        "const history = { pushState(s, _, u) { chiamate.push([\"push\", u, s.vista, s.scheda, s.voce]); vaiA(u); },"
        " replaceState(s, _, u) { chiamate.push([\"replace\", u, s.vista, s.scheda, s.voce]); vaiA(u); } };",
        _riga("const indirizzoVista = "), _riga("let indirizzoMostrato = "),
        _funzione("indirizzoLega"),
        """indirizzoLega("squadra", null, false, "squadre");
indirizzoLega("mercato", "osservati", true, "osservati");
indirizzoLega("mercato", "calendario", true, "calendario");
indirizzoLega("mercato", "calendario", true, "calendario");
indirizzoLega("squadra", null, true, "squadre");
indirizzoLega("squadra", null, true, "importa");
console.log(JSON.stringify({ chiamate, vista: stato.vista, mostrato: indirizzoMostrato }));""",
    ])
    r = _node(codice)
    assert r["chiamate"] == [["replace", "/?vista=squadra", "squadra", None, "squadre"],
                             ["push", "/?vista=mercato&scheda=osservati", "mercato", "osservati", "osservati"],
                             ["push", "/?vista=mercato&scheda=calendario", "mercato", "calendario", "calendario"],
                             ["replace", "/?vista=mercato&scheda=calendario", "mercato", "calendario", "calendario"],
                             ["push", "/?vista=squadra", "squadra", None, "squadre"],
                             ["replace", "/?vista=squadra", "squadra", None, "importa"]]
    assert r["vista"] == "squadra" and r["mostrato"] == "/?vista=squadra"
    popstate = APP[APP.index('window.addEventListener("popstate"'):]
    assert "if (typeof v.voce === \"string\") stato.legaTorna = v.voce;" in popstate[:popstate.index("\n});\n")]
    assert "indirizzoLega(mercato ? \"mercato\" : ambito, mercato ? id : null, sposta, id);" in _funzione("vistaLega")


def test_la_rosa_di_una_squadra_ha_il_menu_di_squadra_accanto():
    """Dalla rosa di una squadra al Calendario con un clic, sul PC; sotto i 1100 px la rosa resta da sola con «‹ Squadra»."""
    corpo = _funzione("vistaRosa")
    assert '<div class="lega-colonne" data-aperto="1">' in corpo and 'menuLega(vociLega("squadra"), "squadre"' in corpo
    assert 'class="lega-pagina"' in corpo and "vaiVoceLega(" in corpo


def test_il_menu_si_riempie_quando_la_finestra_si_allarga():
    """Finestra stretta con il solo menu, poi allargata oltre i 1100 px: a destra si apre la voce di prima (o la prima), invece di
    una colonna vuota."""
    assert re.search(r'LEGA_LARGA\.addEventListener\("change", \(\) => \{[^}]*legaQuandoLarga', APP)
    assert "legaQuandoLarga = () =>" in _funzione("vistaLega")


# ---------------------------------------------------------------- C7: intestazione ferma negli elenchi lunghi

def test_intestazione_dell_elenco_ferma_sotto_la_testata():
    assert re.search(r"\.intestazione-colonne\.ferma \{[^}]*position: sticky; top: var\(--alto-ferma\)", CSS)
    assert "intestazioneColonne({ partita: true, ferma: true })" in APP       # Elenco dei giocatori e rosa di una squadra
    assert "intestazioneColonne({ partita: true, ferma: true })" in _funzione("vistaRosa")
    # nell'Elenco la riga sotto il nome dice squadra, quotazione e proprietario, non la partita: niente «Partita» sopra
    corpo = APP[APP.index("function tabGiocatori"):APP.index("// ---------------------------------------------------------------- scheda giocatore")]
    assert "intestazioneColonne({ partita: false, ferma: true })" in corpo


def test_il_focus_non_finisce_sotto_l_intestazione_ferma():
    """WCAG 2.2, 2.4.11: lo spazio lasciato in alto al focus è l'altezza vera dell'intestazione ferma (--alto-colonne, misurata
    da app.js come --alto-stato), non un numero fisso."""
    assert re.search(r"html:has\(\.intestazione-colonne\.ferma\) \{ scroll-padding-top: "
                     r"calc\(var\(--alto-testata, 0px\) \+ var\(--alto-colonne, 0px\) \+ 8px\); \}", CSS)
    segui = APP[APP.index("(function seguiFerme()"):]
    assert "controllaColonneFerme();" in segui[:segui.index("})();")]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_l_intestazione_oltre_un_terzo_della_finestra_scorre_con_la_pagina():
    """Zoom al 200% o testo grande su una finestra bassa: un'intestazione ferma più alta di un terzo della finestra coprirebbe le
    righe; scorre con la pagina (`non-ferma`) e non chiede spazio al focus."""
    i = APP.index("const QUOTA_STATO")
    codice = "\n".join([
        """let innerHeight = 900; const variabili = {}; let tutte = [];
function riga(alto, posizione = "sticky") {
  const r = { alto, posizione, classi: new Set(), tocchi: 0, get offsetHeight() { return this.alto; }, getBoundingClientRect() { return { height: this.alto }; } };
  r.classList = { contains: c => r.classi.has(c), toggle: (c, si) => { r.tocchi++; if (si) r.classi.add(c); else r.classi.delete(c); } };
  return r;
}
const document = { querySelectorAll: s => (s === ".intestazione-colonne.ferma" ? tutte : []), documentElement: { style: { setProperty: (k, v) => { variabili[k] = v; } } } };
const getComputedStyle = el => ({ position: el.classi.has("non-ferma") ? "static" : el.posizione });""",
        APP[i:APP.index("\n", i)],
        _funzione("controllaColonneFerme"),
        """const esiti = [], passo = () => { controllaColonneFerme(); esiti.push([tutte.map(x => x.classi.has("non-ferma")), variabili["--alto-colonne"]]); };
tutte = [riga(28)]; passo();                             // bassa: ferma, il focus le resta sotto
tutte[0].alto = 320; passo();                            // più di un terzo di 900: scorre con la pagina
const tocchi = tutte[0].tocchi; passo(); esiti.push(tutte[0].tocchi - tocchi);   // rifatto senza cambiamenti: la classe non si tocca
innerHeight = 1200; passo();                             // finestra più alta: torna ferma
tutte = [riga(0)]; passo();                              // pagina strettissima: nascosta
tutte = []; passo();                                     // nessun elenco lungo
console.log(JSON.stringify(esiti));""",
    ])
    assert _node(codice) == [[[False], "28px"], [[True], "0px"], [[True], "0px"], 0, [[False], "320px"], [[False], "0px"], [[], "0px"]]


# ---------------------------------------------------------------- §9: filtri dell'Elenco in una riga, Calendario tabella

def test_filtri_dell_elenco_in_una_riga_sopra_l_elenco():
    """Spec §9: i filtri dell'Elenco in una riga (ricerca, ruolo come controllo segmentato, «solo svincolati») sopra l'elenco,
    che così prende tutta la larghezza della pagina (la riga larga dei giocatori scatta da 680 px). Non è più una colonna ferma."""
    assert "grid-template-columns: 320px" not in CSS and ".giocatori-pagina .filtri-giocatori" not in CSS
    assert ".filtri-giocatori" not in re.search(r'const FERME = "([^"]+)"', APP).group(1)
    larga = _blocco("@media (min-width: 900px) {")
    assert re.search(r"\.filtri-giocatori \{[^}]*display: flex; flex-wrap: wrap;", larga)
    # il ruolo come controllo segmentato: un bordo solo, le voci separate da un filo, la scelta in lime con il bordo scuro
    assert re.search(r"\n\.chips\.filtri \{[^}]*gap: 0;[^}]*border: 1px solid var\(--bordo-campo\)", CSS)
    assert re.search(r"\n\.chips\.filtri \.chip \+ \.chip \{[^}]*border-left: 1px solid var\(--filo\)", CSS)


def test_cambi_consigliati_righe_vicine_e_seguiti_a_tutta_larghezza():
    """Da 900 px una sezione (`.carta`) ha 32 px sotto: le righe dei Cambi consigliati (`carta proposta-r`) li prendevano e tra una
    riga e l'altra restava un buco più alto della riga di testo. Le righe stanno vicine, separate dal filo. Nella griglia di Mercato
    solo i Cambi consigliati vanno in colonne: l'elenco dei Seguiti restava largo mezza pagina e senza la colonna «Partita»."""
    assert re.search(r"\n\.griglia-proposte > \.proposta-r \{ margin-bottom: 0; \}", CSS)
    larga = _blocco("@media (min-width: 768px) {")
    assert "#mercato-corpo > :not(.griglia-proposte) { grid-column: 1 / -1; }" in larga


def test_stemma_e_maglia_senza_riquadri_ne_ombre():
    """Nella rosa di una squadra stemma e maglia stavano in due riquadri bordati, con l'ombra sotto l'immagine; nelle liste lo stemma
    aveva l'ombra. Grafica B (spec §11): niente riquadri per ogni blocco, niente ombre; come la maglia in Oggi, dritta e senza ombra."""
    def corpo(selettore):
        m = re.search(r"\n" + re.escape(selettore) + r" \{([^}]*)\}", CSS)
        assert m, selettore
        return m.group(1)
    riquadro = corpo(".immagine-squadra")
    assert "border:" not in riquadro and "background" not in riquadro and "border-radius" not in riquadro
    for selettore in (".immagine-squadra img", ".stemma-lista"):
        assert "drop-shadow" not in corpo(selettore), selettore


def test_anteprima_delle_rose_a_sezioni_con_i_dubbi_come_avvisi():
    """Aggiorna le rose: ogni rosa letta è una sezione (titolo con il filo spesso sotto, niente riquadro); un dubbio è una riga con il
    filo di 3 px a sinistra nel colore del significato, arancio da controllare e rosso non trovato (spec §4.1, §8.3, §8.13)."""
    def corpo(selettore):
        m = re.search(r"\n" + re.escape(selettore) + r" \{([^}]*)\}", CSS)
        assert m, selettore
        return m.group(1)
    squadra = corpo(".ar-squadra")
    assert "border:" not in squadra and "background" not in squadra
    assert "border-bottom: 2px solid var(--testo)" in corpo(".ar-squadra h4")
    dubbio = corpo(".ar-dubbio")
    assert "border-left: 3px solid var(--arancio)" in dubbio and "background" not in dubbio and "border-radius" not in dubbio
    assert "border-left-color: var(--rosso)" in corpo(".ar-dubbio:has(.etichetta.rossa)")
    assert "background" not in corpo(".ar-dubbio:has(.etichetta.rossa)")


def test_il_calendario_resta_una_tabella_con_le_celle_colorate():
    corpo = APP[APP.index("async function tabCalendario"):APP.index("// Ricerca dei giocatori")]
    assert '<table class="tabella-cal">' in corpo and 'class="cella d${p.difficolta}"' in corpo
