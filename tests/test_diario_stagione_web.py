"""Diario sul web con due stagioni (#176, parte web): la giornata 10 dell'anno scorso e quella di quest'anno sono due voci diverse.
- «Ho schierato la consigliata» e «Correggi a mano» mandano la `stagione` della voce (il server rifiuta le stagioni passate);
- i pulsanti ci sono solo se la voce non ha `modificabile: false` (server vecchio senza il campo: ci sono);
- id della carta, pulsanti e ricerca della voce usano stagione + giornata, non il solo numero della giornata.
Il codice vero di app.js (apriDiario, correggiDiario) gira in node con un DOM finto minimo e dati inventati."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

ORA, PRIMA = "2026-27", "2025-26"
RUOLI = ["P", "D", "D", "D", "D", "C", "C", "C", "C", "A", "A"]


def _titolari(da: int) -> list[dict]:
    return [{"id": da + i, "nome": f"Giocatore {da + i}", "ruolo": r} for i, r in enumerate(RUOLI)]


def _voce(stagione: str, giornata: int, schierata_da: int | None = None, **altro) -> dict:
    v = {"stagione": stagione, "giornata": giornata, "giornata_lega": giornata - 3 if stagione == ORA else None,
         "consigliata": {"modulo": "4-4-2", "titolari": _titolari(1), "reale": 70.5, "atteso": 68.0},
         "schierata": None, "automatica": None, "istantanea": None, "atteso_vs_fatto": None}
    if schierata_da is not None:
        v["schierata"] = {"modulo": "4-4-2", "tipo": "manuale", "titolari": _titolari(schierata_da), "reale": 66.0, "atteso": 67.5}
    return v | altro


ROSA = {"giocatori": [{"id": p["id"], "nome": p["nome"], "ruolo": p["ruolo"], "squadra": "inter"} for da in (1, 21, 41) for p in _titolari(da)]}

# DOM finto: il foglio tiene l'ultimo HTML; querySelectorAll legge i <button>/<input> con l'attributo chiesto (dataset compreso)
DOM = r"""
const chiamate = [], scorrimenti = [], avvisi = [];
let elementi = {}, trovati = {};
const decodifica = s => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
function nuovoElemento(id) {
  return { id, textContent: "", className: "", disabled: false, checked: false, dataset: {}, ascoltatori: {},
           addEventListener(tipo, fn) { this.ascoltatori[tipo] = fn; }, scrollIntoView() { scorrimenti.push(this.id); } };
}
const foglio = {
  hidden: false, html: "",
  querySelectorAll(sel) {
    const attr = sel.slice(1, -1);
    if (!trovati[attr]) trovati[attr] = [...this.html.matchAll(/<(button|input)\b([^>]*)>/g)].filter(m => m[2].includes(attr + "=")).map(m => {
      const el = nuovoElemento(null);
      for (const [, k, v] of m[2].matchAll(/data-([a-z-]+)="([^"]*)"/g)) el.dataset[k.replace(/-([a-z])/g, (x, c) => c.toUpperCase())] = decodifica(v);
      el.checked = /\schecked\b/.test(m[2]);
      return el;
    });
    return trovati[attr];
  },
};
function apriFoglio(html) { foglio.html = html; elementi = {}; trovati = {}; }
var document = {                                       // var: testi.js controlla `typeof document` prima di questa riga
  querySelector(sel) { return sel === "#foglio" ? foglio : sel.startsWith("#") ? document.getElementById(sel.slice(1)) : null; },
  getElementById(id) { return foglio.html.includes(`id="${id}"`) ? (elementi[id] ||= nuovoElemento(id)) : null; },
};
let DIARIO = null;
async function api(percorso, opzioni = {}) {
  chiamate.push({ percorso, metodo: opzioni.method || "GET", corpo: opzioni.body ? JSON.parse(opzioni.body) : null });
  if (percorso === "/api/diario") return JSON.parse(JSON.stringify(DIARIO));
  if (percorso === "/api/rosa") return ROSA;
  if (percorso === "/api/diario/schierata") return {};
  throw new Error("percorso inatteso " + percorso);
}
const avviso = testo => avvisi.push(testo);
const errore = e => "ERRORE " + e.message;
const cartaPrecisione = () => "", cartaScelteTue = () => "";
const SIGLE = {}; let ultimaScheda = 0;
const pausa = () => new Promise(r => setTimeout(r, 0));
const clicca = async el => { await el.ascoltatori.click(); for (let i = 0; i < 5; i++) await pausa(); };
const stato = () => ({ html: foglio.html, chiamate: chiamate.filter(c => c.metodo === "POST"), scorrimenti });
"""


def _pezzo(inizio: str, fine: str) -> str:
    return APP[APP.index(inizio):APP.index(fine)]


def _esegui(diario: dict, passi: str):
    """Esegue `passi` (codice async) con il Diario `diario`; restituisce ciò che `passi` mette in `risultato`."""
    codice = "\n".join([
        TESTI,
        re.search(r"^const \$ = .*$", APP, re.M).group(0),
        _pezzo("function esc(x)", "const perc ="),
        re.search(r"^const segno = .*$", APP, re.M).group(0),
        re.search(r"^const NOMI_RUOLO = .*$", APP, re.M).group(0),
        re.search(r"^const ruoloSigla = .*$", APP, re.M).group(0),
        re.search(r"^const badgeRuolo = .*$", APP, re.M).group(0),
        DOM,
        f"const ROSA = {json.dumps(ROSA)}; DIARIO = {json.dumps(diario)};",
        _pezzo("// Diario delle giornate: formazione schierata", "// Prova del modello sulle ultime giornate giocate"),
        f"(async () => {{ let risultato = null; {passi}; console.log(JSON.stringify(risultato)); }})()"
        ".catch(e => { console.error(e.stack || e); process.exit(1); });",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _carte(html: str) -> dict[str, str]:
    """Le carte del Diario per «stagione giornata» (la stagione si legge nella testata della carta, il numero da `giornata_lega`)."""
    pezzi = re.split(r'(?=<div class="carta" id=")', html)[1:]
    carte = {}
    for p in pezzi:
        st = re.search(r'<span class="debole piccolo">(\d{4}-\d{2})</span>', p).group(1)
        g = re.search(r"Giornata (\d+)", p).group(1)
        carte[f"{st} {g}"] = p
    return carte


def _id(carta: str) -> str:
    return re.match(r'<div class="carta" id="([^"]+)"', carta).group(1)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_ho_schierato_la_consigliata_manda_la_stagione_della_voce():
    # server vecchio (niente `modificabile`): due voci «giornata 10», una per stagione, entrambe con il pulsante
    diario = {"giornate": [_voce(ORA, 10), _voce(PRIMA, 10)]}
    corpi = _esegui(diario, """
      await apriDiario();
      const [quest_anno, anno_scorso] = foglio.querySelectorAll("[data-schierata]");
      await clicca(anno_scorso);
      await apriDiario();
      await clicca(foglio.querySelectorAll("[data-schierata]")[0]);
      risultato = stato().chiamate.map(c => c.corpo);""")
    assert corpi == [{"giornata": 10, "tipo": "consigliata", "stagione": PRIMA},
                     {"giornata": 10, "tipo": "consigliata", "stagione": ORA}]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_correggi_apre_la_voce_della_sua_stagione_e_manda_la_stagione():
    # stessa giornata nelle due stagioni, con titolari diversi: «Correggi a mano» dell'anno scorso parte dai SUOI titolari
    diario = {"giornate": [_voce(ORA, 10, schierata_da=1), _voce(PRIMA, 10, schierata_da=21)]}
    r = _esegui(diario, """
      await apriDiario();
      await clicca(foglio.querySelectorAll("[data-correggi]")[1]);
      const spuntati = foglio.querySelectorAll("[data-scelto]").filter(c => c.checked).map(c => Number(c.dataset.scelto));
      await clicca(document.getElementById("diario-salva"));
      risultato = { spuntati, ...stato() };""")
    assert r["spuntati"] == list(range(21, 32))
    assert [c["corpo"] for c in r["chiamate"]] == [{"giornata": 10, "tipo": "manuale", "titolari": list(range(21, 32)), "stagione": PRIMA}]
    carte = _carte(r["html"])                                               # dopo il salvataggio il Diario si riapre su QUELLA voce
    assert r["scorrimenti"] == [_id(carte[f"{PRIMA} 10"])]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_stagione_passata_senza_pulsanti_per_cambiare():
    diario = {"giornate": [_voce(ORA, 10, modificabile=True), _voce(PRIMA, 10, modificabile=False),
                           _voce(PRIMA, 9, schierata_da=21, modificabile=False)]}
    carte = _carte(_esegui(diario, "await apriDiario(); risultato = stato();")["html"])
    assert set(carte) == {f"{ORA} 7", f"{PRIMA} 10", f"{PRIMA} 9"}
    for chiave in (f"{PRIMA} 10", f"{PRIMA} 9"):
        c = carte[chiave]
        assert "data-schierata" not in c and "data-correggi" not in c, chiave
        assert "Ho schierato" not in c and "Correggi a mano" not in c, chiave
    assert "Cosa hai schierato (4-4-2)" in carte[f"{PRIMA} 9"]                           # la formazione registrata si vede lo stesso
    attuale = carte[f"{ORA} 7"]
    assert "data-schierata" in attuale and "data-correggi" in attuale
    assert "Ho schierato la consigliata" in attuale and "Ho schierato un'altra formazione" in attuale


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_due_stagioni_stessa_giornata_carte_distinte_e_scorrimento_giusto():
    diario = {"giornate": [_voce(ORA, 10), _voce(ORA, 9), _voce(PRIMA, 10), _voce(PRIMA, 9)]}
    r = _esegui(diario, """
      await apriDiario(10);                 // da Oggi: solo il numero, vale la stagione più recente
      const html = foglio.html;
      await apriDiario(10, "2025-26");
      risultato = { html, scorrimenti };""")
    carte = _carte(r["html"])
    ids = [_id(c) for c in carte.values()]
    assert len(ids) == 4 and len(set(ids)) == 4
    assert r["scorrimenti"] == [_id(carte[f"{ORA} 7"]), _id(carte[f"{PRIMA} 10"])]
