"""Testo intero sulla web a 320 px e con il testo «Grande» e «Molto grande» (issue #265, regola «mai testo tagliato»).
Su main, nel browser (dati verosimili delle fotografie, 320/390/1440 px):
- il cognome lungo sulla pedina finiva con «…» a ogni larghezza («Zosaba Nd…», 81 px di testo in 76 px);
- lo stato della pedina a giornata in corso («fantavoto 10,0», «Partita in corso») e «⚠ gioca 19%» non andavano a capo: le scritte
  delle pedine vicine si sovrapponevano e, con cinque pedine in una fila, l'ultima usciva dal campo e il campo la tagliava
  (320 px, 390 px con il testo «Grande», 1440 px con «Molto grande»);
- la sigla «MON» nelle partite del turno perdeva 2 px a 320 px;
- il menu a tendina del rinvio tagliava la scelta («aspettano il recupero (conta il suo vo»): un <select> non va a capo;
- la cella d'angolo vuota del calendario era un'intestazione senza testo (axe `empty-table-header`).
Come sull'iPhone (`PedinaCampo`: cognome intero; `MenuRinvio`: la scelta va a capo accanto al simbolo del menu).
La prova vera è nel browser (collaudo della pull request); qui le regole e il codice di app.js eseguito con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

APP = codice_web.app()
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")
STRETTA = "@container pagina (max-width: 319.98px) {"
SENZA_COMMENTI = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
# le regole che valgono a ogni larghezza: prima del blocco della pagina strettissima (in fondo al file) e fuori dalle @container
GLOBALE = re.sub(r"@container[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", SENZA_COMMENTI[:SENZA_COMMENTI.index(STRETTA)])


def _blocco(apertura: str) -> str:
    i = SENZA_COMMENTI.index(apertura) + len(apertura)
    livello, j = 1, i
    while livello:
        livello += {"{": 1, "}": -1}.get(SENZA_COMMENTI[j], 0)
        j += 1
    return SENZA_COMMENTI[i:j - 1]


def _regole(testo: str, selettore: str) -> str:
    """Tutti i corpi delle regole il cui elenco di selettori contiene proprio `selettore`."""
    corpi = [corpo for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", testo)
             if selettore in [s.strip() for s in sel.split(",")]]
    assert corpi, f"manca la regola {selettore}"
    return " ".join(corpi)


def _px(corpo: str, proprieta: str) -> float:
    m = re.search(r"(?<![\w-])" + re.escape(proprieta) + r"\s*:\s*([\d.]+)px", corpo)
    assert m, f"{proprieta} in px: {corpo}"
    return float(m.group(1))


def _riempimento_x(corpo: str) -> float:
    """Il riempimento a destra (e a sinistra) di una regola `padding: a b ...`."""
    valori = re.search(r"(?<![\w-])padding\s*:\s*([^;]+);", corpo).group(1).split()
    return float((valori[1] if len(valori) > 1 else valori[0]).removesuffix("px"))


# ---------------------------------------------------------------- campo

def test_cognome_e_stato_della_pedina_vanno_a_capo_a_ogni_larghezza():
    """Mai «…»: il cognome intero, a capo tra le parole («Zosaba» sopra, «Ndorti» sotto) e, solo per una parola più larga della
    pedina, dentro la parola. Lo stesso per lo stato («Partita in corso», «fantavoto 10,0»), «⚠ gioca 19%» e «vs MON»."""
    for selettore in (".pedina .nome", ".pedina .gioca", ".pedina .avv"):
        corpo = _regole(GLOBALE, selettore)
        assert "ellipsis" not in corpo and "nowrap" not in corpo, f"{selettore}: non si taglia e va a capo"
        assert not re.search(r"overflow(-x)?\s*:\s*hidden", corpo), f"{selettore}: non si taglia"
        assert not re.search(r"max-width\s*:\s*\d", corpo), f"{selettore}: niente larghezza fissa, segue la pedina"
    assert "overflow-wrap: anywhere" in _regole(GLOBALE, ".pedina .nome")
    assert "overflow-wrap: anywhere" in _regole(GLOBALE, ".pedina .gioca")
    assert "flex-wrap: wrap" in _regole(GLOBALE, ".pedina .avv")             # «vs» sopra la sigla solo se insieme non ci stanno
    # la pillola arancio su due righe resta tonda agli angoli (come le etichette), non una capsula tagliata dal testo
    raggio = re.search(r"border-radius\s*:\s*([^;]+);", _regole(GLOBALE, ".pedina .gioca.basso")).group(1)
    assert "999" not in raggio and "r-pill" not in raggio


def test_le_pedine_si_stringono_dentro_il_campo_anche_con_cinque_per_fila():
    """Cinque pedine in una fila (5-4-1, 3-5-2) a 320 px: il campo è largo 288 px; con i volti da 56 px cinque pedine con gli spazi ne
    chiedevano 308 e l'ultima usciva dal campo, tagliata. La pedina non ha una larghezza fissa (si stringe fino al disco) e il disco
    della grafica B (44 px, spec §8.10) ci sta cinque volte anche nel campo più stretto, senza rimpicciolirsi: il tocco resta da 44 px."""
    pedina = _regole(GLOBALE, ".pedina")
    assert not re.search(r"(?<![\w-])width\s*:", pedina), "la pedina non ha una larghezza fissa"
    assert re.search(r"(?<![\w-])flex\s*:\s*0 1 \d+px", pedina), "la pedina parte da una larghezza e si stringe"
    assert "container: campo / inline-size" in _regole(GLOBALE, ".campo")
    campo, linea = _regole(GLOBALE, ".campo"), _regole(GLOBALE, ".linea")
    fuori = 2 * _riempimento_x(campo) + 4 * _px(linea, "gap")                 # riempimento del campo e quattro spazi tra cinque pedine
    disco = _px(_regole(GLOBALE, ".disco"), "width")
    assert disco >= 44 and 5 * disco + fuori <= 320 - 2 * 16, "a 320 px (campo largo 288 px) cinque dischi ci stanno"
    assert not any(".disco" in _blocco(m.group(0)) for m in re.finditer(r"@container campo \(max-width: ([\d.]+)px\) \{", SENZA_COMMENTI))
    # in una pedina stretta un cognome di una parola («Merondo») va a capo dentro la parola: dove il browser lo sa fare, con il
    # trattino della sillabazione («Meron-do») invece che a una lettera dalla fine («Merond/o»); il testo non si rimpicciolisce
    stretti = [m for m in re.finditer(r"@container campo \(max-width: ([\d.]+)px\) \{", SENZA_COMMENTI) if ".pedina .nome" in _blocco(m.group(0))]
    assert len(stretti) == 1, "manca il campo stretto (@container campo) con la sillabazione"
    sillabe = _regole(_blocco(stretti[0].group(0)), ".pedina .nome")
    assert "hyphens: auto" in sillabe and "-webkit-hyphens: auto" in sillabe and "font-size" not in sillabe
    # lo stesso in ogni fila da cinque, anche con il volto normale (390 px con il testo «Grande»: pedine da 58 px, «Rogheceb/e»)
    cinque = _regole(GLOBALE, ".linea:has(> .pedina:nth-child(5)) .nome")
    assert "hyphens: auto" in cinque and "-webkit-hyphens: auto" in cinque


# ---------------------------------------------------------------- partite del turno

# ---------------------------------------------------------------- menu del rinvio

def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _pezzo(inizio: str, fine: str) -> str:
    return APP[APP.index(inizio):APP.index(fine)]


RINVIO = {"stagione": "2026-27", "giornata": 8, "giornata_lega": 5, "modo": "aspetta", "predefinito": "aspetta", "eccezione": False,
          "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6.0,
          "partite": [{"casa": "udinese", "trasferta": "milan", "data": "2026-11-18 20:45"}], "miei": []}


def _codice_rinvio(dopo: str) -> str:
    return "\n".join([
        TESTI, "LINGUA = 'it';",
        "var document = { querySelectorAll: () => [] };",           # var dopo testi.js: lì `typeof document` è ancora "undefined"
        _pezzo("function esc(x)", "const sigla ="), _pezzo("const num =", "const perc ="),
        _pezzo("const MODI_RINVIO", "function cardRinvio("),
        _pezzo("function collegaRinvio()", "function mostraOggi("),
        dopo,
    ])


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_menu_del_rinvio_mostra_la_scelta_intera():
    """La scelta si legge in un riquadro che va a capo, con il simbolo del menu accanto; il <select> vero sta sopra, trasparente:
    riceve il tocco, la tastiera e il lettore di schermo e apre il menu del sistema con le scelte intere."""
    html = _node(_codice_rinvio(f"console.log(JSON.stringify(menuRinvio({json.dumps(RINVIO)})));"))
    riquadro = re.search(r'<span class="menu-scelta"><span class="menu-scelta-testo" aria-hidden="true">([^<]*)</span>\s*<select class="rinvio-modo"', html)
    assert riquadro, html
    assert riquadro.group(1) == "aspettano il recupero (conta il suo voto)"
    assert html.index("<select") > html.index('<label class="rinvio-scelta">') and html.index("</select>") < html.index("</label>")   # il nome resta la domanda
    # scelta che non è fra i modi (server più nuovo): il riquadro dice quello che il <select> mostra, cioè la prima voce
    strano = _node(_codice_rinvio(f"console.log(JSON.stringify(menuRinvio({json.dumps(RINVIO | {'modo': 'altro'})})));"))
    assert '<span class="menu-scelta-testo" aria-hidden="true">aspettano il recupero (conta il suo voto)</span>' in strano

    testo = _regole(GLOBALE, ".menu-scelta-testo")
    assert "nowrap" not in testo and "ellipsis" not in testo and "overflow-wrap: break-word" in testo
    assert "position: relative" in _regole(GLOBALE, ".menu-scelta")
    menu = _regole(GLOBALE, ".menu-scelta select")
    for pezzo in ("position: absolute", "inset: 0", "opacity: 0", "width: 100%", "height: 100%"):
        assert pezzo in menu, pezzo
    assert "outline: 2px solid" in _regole(GLOBALE, ".menu-scelta:has(select:focus-visible)")   # il fuoco si vede sul riquadro
    assert _px(_regole(GLOBALE, ".menu-scelta"), "min-height") >= 44


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_il_riquadro_del_rinvio_segue_la_scelta_e_torna_indietro_se_non_si_salva():
    """Cambiata la scelta, il riquadro la mostra subito; se il server non la salva, il menu e il riquadro tornano a quella di prima
    (prima il <select> restava sulla scelta non salvata)."""
    dom = r"""
const NOMI = { aspetta: "aspettano il recupero (conta il suo voto)", senza_voto: "restano senza voto (entra la riserva)", voto_ufficio: "prendono il voto d'ufficio (6)" };
const testo = { textContent: NOMI.aspetta };
const sel = { value: "aspetta", disabled: false, dataset: { giornata: "8", stagione: "2026-27" }, ascolta: {},
  get selectedOptions() { return [{ textContent: NOMI[this.value] }]; },
  closest: s => s === ".menu-scelta" ? { querySelector: q => q === ".menu-scelta-testo" ? testo : null } : null,
  addEventListener(ev, f) { this.ascolta[ev] = f; } };
document.querySelectorAll = s => s === "select.rinvio-modo" ? [sel] : [];
const chiamate = [], avvisi = []; let fallisci = false, ridisegni = 0;
async function api(p, o) { chiamate.push([p, JSON.parse(o.body)]); if (fallisci) throw new Error("Non riesco a salvare la scelta."); return {}; }
const svuotaCache = () => {}, avviso = m => avvisi.push(m), vistaOggi = () => { ridisegni++; };
(async () => {
  collegaRinvio();
  const visto = [];
  sel.value = "senza_voto"; const attesa = sel.ascolta.change(); visto.push(testo.textContent); await attesa;
  visto.push([testo.textContent, sel.value, ridisegni]);
  fallisci = true; sel.disabled = false;
  sel.value = "voto_ufficio"; await sel.ascolta.change();
  visto.push([testo.textContent, sel.value, sel.disabled, avvisi]);
  console.log(JSON.stringify({ visto, chiamate }));
})();
"""
    r = _node(_codice_rinvio(dom))
    subito, salvata, rifiutata = r["visto"]
    assert subito == "restano senza voto (entra la riserva)"                    # prima della risposta del server
    assert salvata == ["restano senza voto (entra la riserva)", "senza_voto", 1]
    assert rifiutata == ["restano senza voto (entra la riserva)", "senza_voto", False,                    # torna alla scelta salvata
                         ["Fatto: consigli aggiornati per questa giornata", "Non riesco a salvare la scelta."]]
    assert r["chiamate"] == [["/api/regole/rinvio", {"giornata": 8, "modo": "senza_voto", "stagione": "2026-27"}],
                             ["/api/regole/rinvio", {"giornata": 8, "modo": "voto_ufficio", "stagione": "2026-27"}]]
