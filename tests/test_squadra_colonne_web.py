"""Squadra (e Altro) con il menu e la pagina affiancati sugli schermi larghi, Elenco dei giocatori e rosa con l'intestazione
ferma (grafica B, PR 10; spec §5 C7 e C10, §9 «Squadra e Altro»). Controlli su app.js e stile.css e prove con node del codice
vero di app.js (le misure nel browser sono nella descrizione della pull request)."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

APP = codice_web.app()
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
# Dal 12/11/2026 (#618) Squadra e Altro non ci sono più: le loro voci sono pagine di Impostazioni, una alla volta, provate nel
# browser vero (tests/browser/test_impostazioni.py).


# ---------------------------------------------------------------- C7: intestazione ferma negli elenchi lunghi

def test_intestazione_dell_elenco_ferma_sotto_la_testata():
    assert re.search(r"\.intestazione-colonne\.ferma \{[^}]*position: sticky; top: var\(--alto-ferma\)", CSS)
    assert "intestazioneColonne({ partita: true, ferma: true })" in _funzione("vistaRosa")       # la rosa di una squadra


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
