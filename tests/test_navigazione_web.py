"""Navigazione della web (grafica B, PR 4): Indietro e Avanti del browser, link «Vai al contenuto», scheda accesa, tasti.
Si esegue con node il codice vero di app.js (vai, il gestore di popstate, quello dei tasti, pagina) con una cronologia finta che
si comporta come quella del browser: pushState/replaceState, Indietro che manda popstate con lo stato della voce, e un link «#…»
che aggiunge una voce senza stato e manda popstate (Chrome e Firefox lo fanno)."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="serve node")


def _da_a(inizio: str, fine: str) -> str:
    i = APP.index(inizio)
    return APP[i:APP.index(fine, i) + len(fine)]


def _funzione(nome: str) -> str:
    i = re.search(rf"\n(?:async )?function {nome}\(", APP).start()
    return APP[i:APP.index("\n}\n", i) + 3]


def _riga(inizio: str) -> str:
    return re.search(r"\n" + re.escape(inizio) + r"[^\n]*\n", APP).group(0)


AMBIENTE = r"""
const chiamate = [];
const stato = { vista: "formazione", scelta: null, impDaUrl: null, legaTorna: null };
const VOCI_LEGA = [{ id: "squadre", ambito: "squadra" }, { id: "importa", ambito: "squadra" }, { id: "diario", ambito: "altro" }, { id: "regole", ambito: "altro" }];
const t = k => ({ "shell.impostazioni": "Impostazioni", "nav.formazione": "Formazione", "nav.squadra": "Squadra", "nav.altro": "Altro" }[k] || k);
const esc = x => String(x ?? "");
let largo = false; const legaLarga = () => largo;                // finestra da 1100 px (Squadra con menu e pagina affiancati)
const classi = () => { const s = new Set(); return { toggle(c, si) { if (si === undefined ? !s.has(c) : si) s.add(c); else s.delete(c); }, contains: c => s.has(c), add: c => s.add(c), remove: c => s.delete(c) }; };
const elemento = (vista, id = "") => { const attr = {}; return { id, dataset: { vista }, classList: classi(), attr, setAttribute(k, v) { attr[k] = String(v); }, removeAttribute(k) { delete attr[k]; } }; };
const schede = ["formazione", "squadra", "altro"].map(v => elemento(v));
const ingranaggio = elemento(undefined, "bottone-impostazioni");
const titolo = { id: "titolo-pagina", focus(o) { chiamate.push(["focus-titolo", !!(o && o.preventScroll)]); } };
const document = { title: "", activeElement: null, querySelectorAll: s => (s === ".schede .scheda" ? schede : []), querySelector: () => null,
  addEventListener(n, f) { document["su_" + n] = f; } };
const $ = s => ({ "#bottone-impostazioni": ingranaggio, "#titolo-pagina": titolo }[s] || null);
const localStorage = { setItem() {} };
const window = { scrollTo() {}, ascolta: {}, addEventListener(n, f) { window.ascolta[n] = f; } };
const contenuto = { classList: classi(), dataset: {} };
let timerConto = null; const clearInterval = () => {}; let regoleAC = null;
const disegna = nome => () => chiamate.push(["disegna", nome]);
const vistaFormazione = disegna("formazione");
const vistaLega = a => chiamate.push(["disegna", a]), vistaImpostazioni = g => chiamate.push(["disegna", "impostazioni", g || null]);
const chiudiFoglio = () => chiamate.push(["chiudi-foglio"]);
const chiudiPannelloAffiancato = () => chiamate.push(["chiudi-pannello"]);
// cronologia del browser, finta ma con le sue regole
const location = { pathname: "/", search: "", hash: "" };
const voci = [{ state: null, url: "/" }]; let pos = 0;
const vaiA = url => { const u = new URL(url, "http://x"); location.pathname = u.pathname; location.search = u.search; location.hash = u.hash; };
const history = {
  get state() { return voci[pos].state; },
  pushState(s, _, url) { voci.splice(pos + 1); voci.push({ state: s, url }); pos++; vaiA(url); chiamate.push(["push", url]); },
  replaceState(s, _, url) { voci[pos] = { state: s, url }; vaiA(url); chiamate.push(["replace", url]); },
  back() { pos--; vaiA(voci[pos].url); window.ascolta.popstate({ state: voci[pos].state }); },
  forward() { pos++; vaiA(voci[pos].url); window.ascolta.popstate({ state: voci[pos].state }); },
  ancora(h) { const url = location.pathname + location.search + h; voci.splice(pos + 1); voci.push({ state: null, url }); pos++; vaiA(url); window.ascolta.popstate({ state: null }); },
};
const accesa = () => schede.filter(s => s.attr["aria-current"] === "page").map(s => s.dataset.vista).concat(ingranaggio.attr["aria-current"] ? ["ingranaggio"] : []);
const foto = () => ({ indirizzo: location.pathname + location.search + location.hash, vista: stato.vista, accesa: accesa(), voci: voci.length, pos,
  chiamate: chiamate.splice(0) });
"""


def _esegui(scena: str):
    codice = "\n".join([
        AMBIENTE,
        APP[APP.index("const VISTE = "):APP.index("const SCHEDA_DI = ")], _riga("const SCHEDA_DI = "),
        _riga("const indirizzoVista = "), _riga("let indirizzoMostrato = "),
        _riga("const DISEGNO_VISTE = "),
        _funzione("schermataCheResta"), _funzione("vai"),
        _da_a('window.addEventListener("popstate"', "\n});\n"),
        scena,
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_indietro_e_avanti_tornano_alle_schermate_di_prima_con_la_scheda_accesa():
    prima, squadra, altro, indietro, indietro2, avanti, imp, da_imp = _esegui("""
    const esiti = [];
    vai("formazione"); esiti.push(foto());                           // prima schermata: sostituisce la voce dell'avvio
    vai("squadra", undefined, { focoTitolo: true }); esiti.push(foto());
    vai("altro"); esiti.push(foto());
    history.back(); esiti.push(foto());
    history.back(); esiti.push(foto());
    history.forward(); esiti.push(foto());
    vai("impostazioni", "aspetto"); esiti.push(foto());
    history.back(); esiti.push(foto());
    console.log(JSON.stringify(esiti));
    """)
    assert prima["indirizzo"] == "/?vista=formazione" and prima["voci"] == 1 and ["replace", "/?vista=formazione"] in prima["chiamate"]
    assert prima["accesa"] == ["formazione"]
    assert squadra["indirizzo"] == "/?vista=squadra" and squadra["voci"] == 2 and squadra["accesa"] == ["squadra"]
    assert ["focus-titolo", True] in squadra["chiamate"]                          # cambio di scheda: il focus va sul titolo
    assert altro["voci"] == 3 and altro["accesa"] == ["altro"]
    assert indietro["indirizzo"] == "/?vista=squadra" and indietro["vista"] == "squadra" and indietro["accesa"] == ["squadra"]
    assert ["disegna", "squadra"] in indietro["chiamate"] and ["chiudi-foglio"] in indietro["chiamate"]
    assert not any(c[0] in ("push", "replace") for c in indietro["chiamate"])     # Indietro non scrive di nuovo la cronologia
    assert ["focus-titolo", True] in indietro["chiamate"]
    assert indietro2["indirizzo"] == "/?vista=formazione" and indietro2["accesa"] == ["formazione"] and indietro2["pos"] == 0
    assert avanti["indirizzo"] == "/?vista=squadra" and avanti["accesa"] == ["squadra"]
    assert imp["indirizzo"] == "/?vista=impostazioni&gruppo=aspetto" and imp["accesa"] == ["ingranaggio"]
    assert ["disegna", "impostazioni", "aspetto"] in imp["chiamate"]
    assert da_imp["indirizzo"] == "/?vista=squadra" and da_imp["accesa"] == ["squadra"]


def test_le_schermate_si_disegnano_da_una_mappa_con_i_soli_nomi_ammessi():
    """CodeQL (js/unvalidated-dynamic-method-call, #396): il nome della schermata arriva anche dall'indirizzo (?vista=, Indietro);
    prima si chiamava `oggetto[vista]()`. Ora una Map con i soli nomi ammessi: un nome strano, anche «__proto__» o «constructor»,
    porta alla Formazione e non chiama altro. Anche «oggi», che dal 12/11/2026 è la Formazione (#616). «mercato» e «scambi» (pagine
    tolte, #615) portano a Squadra e ad Altro."""
    assert "[vista]()" not in APP
    esiti = _esegui("""
    const esiti = [];
    for (const nome of ["__proto__", "constructor", "toString", "hasOwnProperty", "oggi", "mercato", "scambi"]) { vai(nome); esiti.push(foto()); }
    vai("squadra"); chiamate.splice(0);
    history.pushState(null, "", "/?vista=constructor"); chiamate.splice(0); indirizzoMostrato = null;
    window.ascolta.popstate({ state: null }); esiti.push(foto());
    console.log(JSON.stringify(esiti));
    """)
    for esito in esiti[:5]:
        disegni = [c for c in esito["chiamate"] if c[0] == "disegna"]
        assert disegni == [["disegna", "formazione"]] and esito["vista"] == "formazione" and esito["accesa"] == ["formazione"], esito
        assert esito["indirizzo"] == "/?vista=formazione", esito
    assert ["disegna", "squadra"] in esiti[5]["chiamate"] and esiti[5]["accesa"] == ["squadra"] and esiti[5]["indirizzo"] == "/?vista=squadra"
    assert ["disegna", "altro"] in esiti[6]["chiamate"] and esiti[6]["accesa"] == ["altro"] and esiti[6]["indirizzo"] == "/?vista=altro"
    assert [c for c in esiti[7]["chiamate"] if c[0] == "disegna"] == [["disegna", "formazione"]] and esiti[7]["vista"] == "formazione"


def test_il_link_vai_al_contenuto_non_ridisegna_la_schermata():
    """Revisione della #396: «Vai al contenuto» (href="#contenuto") manda popstate senza stato; prima l'app rileggeva ?vista= e
    ridisegnava tutto (pagina in cima, foglio chiuso, diretta ferma). Anche tornando indietro dalla voce con «#» non succede niente."""
    ancora, indietro, poi = _esegui("""
    const esiti = [];
    vai("formazione"); vai("squadra"); chiamate.splice(0);
    history.ancora("#contenuto"); esiti.push(foto());
    history.back(); esiti.push(foto());
    vai("altro"); history.back(); esiti.push(foto());
    console.log(JSON.stringify(esiti));
    """)
    assert ancora["indirizzo"] == "/?vista=squadra#contenuto" and ancora["chiamate"] == []
    assert indietro["indirizzo"] == "/?vista=squadra" and indietro["chiamate"] == [] and indietro["vista"] == "squadra"
    assert poi["indirizzo"] == "/?vista=squadra" and poi["accesa"] == ["squadra"]                # la cronologia resta giusta


def test_cambiare_schermata_chiude_il_pannello_affiancato():
    """Con il pannello affiancato (PR 9) schede, tasti e ingranaggio restano attivi: la schermata nuova chiude il pannello (la
    sostituzione di un titolare non deve restare aperta su una Formazione che non c'è più), prima di disegnarsi."""
    squadra, imp = _esegui("""
    const esiti = [];
    vai("formazione"); chiamate.splice(0);
    vai("squadra"); esiti.push(foto());
    vai("impostazioni", "aspetto"); esiti.push(foto());
    console.log(JSON.stringify(esiti));
    """)
    for esito in (squadra, imp):
        c = esito["chiamate"]
        assert ["chiudi-pannello"] in c and c.index(["chiudi-pannello"]) < next(i for i, x in enumerate(c) if x[0] == "disegna"), c


def test_tasti_slash_e_numeri_non_scattano_mentre_si_scrive():
    """`/` porta nel campo della testata (o apre la ricerca dove il campo non si vede); 1-3 cambiano scheda (tante quante sono le
    schede: un numero più alto non fa niente) e portano il focus sul titolo; dentro un campo di testo, con Ctrl/⌘/Alt o con il foglio
    modale aperto non succede niente. Con il pannello affiancato (PR 9) la pagina resta attiva: 1-3, «,» e `/` funzionano come a
    pannello chiuso."""
    codice = "\n".join([
        "const chiamate = []; let campoVisibile = true; const foglio = { hidden: true }; let affiancato = false;",
        "const foglioModale = () => !foglio.hidden && !affiancato;",
        "const campo = { getClientRects: () => (campoVisibile ? [1] : []), focus() { chiamate.push(['focus-campo']); } };",
        "const $ = s => ({ '#campo-cerca': campo, '#foglio': foglio }[s] || null);",
        "const document = { addEventListener(n, f) { document['su_' + n] = f; } };",
        "const apriRicerca = (q) => chiamate.push(['ricerca', q ?? '']); const vai = (v, g, o) => chiamate.push(['vai', v, !!(o && o.focoTitolo)]);",
        "const chiudiFoglio = () => chiamate.push(['chiudi-foglio']);",
        APP[APP.index("const VISTE = "):APP.index("\n", APP.index("const VISTE = "))],
        _da_a('document.addEventListener("keydown"', "\n});\n"),
        """
        const tasto = (key, target = { tagName: "BODY" }, altro = {}) => { let fermato = false;
          document.su_keydown({ key, target, preventDefault() { fermato = true; }, ...altro }); return [chiamate.splice(0), fermato]; };
        const esiti = {
          slash: tasto("/"), slash_campo: tasto("/", { tagName: "INPUT" }), slash_area: tasto("/", { tagName: "TEXTAREA" }),
          slash_scrivibile: tasto("/", { tagName: "DIV", isContentEditable: true }),
          due: tasto("2"), due_campo: tasto("2", { tagName: "INPUT" }), due_ctrl: tasto("2", undefined, { ctrlKey: true }),
          uno: tasto("1"), quattro: tasto("4"),
        };
        foglio.hidden = false; esiti.due_foglio = tasto("2"); esiti.virgola_foglio = tasto(","); esiti.slash_foglio = tasto("/");
        affiancato = true; esiti.due_pannello = tasto("2"); esiti.virgola_pannello = tasto(","); esiti.slash_pannello = tasto("/");
        affiancato = false;
        foglio.hidden = true; campoVisibile = false; esiti.slash_telefono = tasto("/");
        esiti.esc = tasto("Escape", { tagName: "INPUT" });
        console.log(JSON.stringify(esiti));
        """,
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    e = json.loads(r.stdout.strip().splitlines()[-1])
    assert e["slash"] == [[["focus-campo"]], True]                      # PC: il cursore nel campo della testata, «/» non si scrive
    for chiave in ("slash_campo", "slash_area", "slash_scrivibile", "due_campo", "due_ctrl", "due_foglio", "virgola_foglio"):
        assert e[chiave] == [[], False], chiave
    assert e["slash_foglio"] == [[["ricerca", ""]], True]                 # foglio modale: la ricerca prende il suo posto
    assert e["uno"] == [[["vai", "formazione", True]], False] and e["due"] == [[["vai", "squadra", True]], False]
    assert e["quattro"] == [[], False]                                   # le schede sono tre
    assert e["due_pannello"] == e["due"] and e["virgola_pannello"] == [[["vai", "impostazioni", True]], False]
    assert e["slash_pannello"] == [[["focus-campo"]], True]
    assert e["slash_telefono"] == [[["ricerca", ""]], True]
    assert e["esc"][0] == [["chiudi-foglio"]]


def test_pagina_scrive_il_titolo_della_finestra_e_tiene_il_focus_sul_titolo():
    """Il nome della finestra (letto dai lettori di schermo) è il titolo grande della schermata: «Real Esempio · SchieraXI» nella
    rosa, non «Squadra». Se il titolo aveva il focus (cambio di scheda), ridisegnando la schermata lo ritrova."""
    codice = "\n".join([
        "const chiamate = []; const stato = { vista: 'mercato' };",
        "const t = k => ({ 'nav.squadra': 'Squadra' }[k] || k); const esc = x => String(x ?? '').replace(/</g, '&lt;');",
        "const rigaStato = () => ''; const fDataOra = () => '';",
        "let html = ''; const attributi = {};",
        "const contenuto = { classList: { toggle() {} }, set innerHTML(v) { html = v; },",
        "  setAttribute(n, v) { attributi[n] = v; }, removeAttribute(n) { delete attributi[n]; } };",
        "const document = { title: '', activeElement: null };",
        "const $ = s => (s === '#titolo-pagina' ? { focus(o) { chiamate.push(['focus-titolo', !!(o && o.preventScroll)]); } } : null);",
        APP[APP.index("const VISTE = "):APP.index("const SCHEDA_DI = ")], _riga("const SCHEDA_DI = "),
        _funzione("pagina"),
        """
        const esiti = [];
        pagina("<p>x</p>"); esiti.push([document.title, html.includes('tabindex="-1"'), chiamate.splice(0)]);
        document.activeElement = { id: "titolo-pagina" };
        pagina("<p>y</p>", { titolo: "Real <Esempio>" }); esiti.push([document.title, html.includes("Real &lt;Esempio>"), chiamate.splice(0)]);
        const occupata = [];                              // aria-busy dell'area principale: solo mentre carica
        pagina("<p>carico</p>", { carica: true }); occupata.push(attributi["aria-busy"] ?? null);
        pagina("<p>pronta</p>"); occupata.push(attributi["aria-busy"] ?? null);
        console.log(JSON.stringify([...esiti, occupata]));
        """,
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    (t1, tab, c1), (t2, sicuro, c2), occupata = json.loads(r.stdout.strip().splitlines()[-1])
    assert t1 == "Squadra · SchieraXI" and tab and c1 == []
    assert t2 == "Real <Esempio> · SchieraXI" and sicuro and c2 == [["focus-titolo", True]]
    assert occupata == ["true", None]                # la schermata di attesa lo mette, la pagina che arriva dopo lo toglie
