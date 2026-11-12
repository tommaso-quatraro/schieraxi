"""Web senza le funzioni tolte il 12/11/2026 (#615): cosa succede a ciò che puntava a una schermata che non c'è più.

Si esegue il codice vero della web con Node (niente ricerca di testo nel sorgente): le righe di «Da fare» che portavano a
Cambi consigliati o a Scambi non si mostrano, e un indirizzo vecchio apre la schermata più vicina che resta.
Le schermate si provano nel browser: prove/web_comportamento/.
"""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")


def _node(codice: str):
    out = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _da_fare(voci: list[dict]) -> list[str]:
    """Gli id delle righe che la carta «Da fare» mostra, con `dafare.js` caricato per intero."""
    sorgente = codice_web.leggi("dafare.js")
    codice = f"""
      const vm = require("vm");
      const ctx = {{ t: k => k, tp: (k, n) => k + ":" + n, esc: x => String(x), testoDi: (v, c) => (c ? v[c] : v.testo) }};
      vm.createContext(ctx);
      vm.runInContext({json.dumps(sorgente)} + "\\n;globalThis.fuori = dfValide(" + {json.dumps(json.dumps(voci))} + ").map(v => v.id);", ctx);
      console.log(JSON.stringify(ctx.fuori));
    """
    return _node(codice)


def _voce(id: str, tipo: str, scheda: str, sezione: str | None = None, **extra) -> dict:
    return {"id": id, "tipo": tipo, "testo": f"testo di {id}", "priorita": 2, "azione": "Apri",
            "destinazione": {"scheda": scheda, "sezione": sezione, **extra}}


def test_da_fare_non_mostra_le_righe_delle_funzioni_tolte():
    voci = [_voce("dubbio:1", "dubbio", "formazione", giocatore=1),
            _voce("svincolato:7", "svincolato", "mercato", giocatore=7),
            _voce("scambio:Atletico Prova", "scambio", "scambi"),
            _voce("copertura:D", "copertura", "mercato"),
            _voce("rose-vecchie", "rose", "lega", "rose"),
            _voce("diario:5", "diario", "lega", "diario", giornata=5),
            _voce("dati-vecchi", "dati", "impostazioni", "avanzate")]
    assert _da_fare(voci) == ["dubbio:1", "rose-vecchie", "diario:5", "dati-vecchi"]


def test_da_fare_tiene_una_riga_senza_destinazione_e_scarta_quelle_senza_testo():
    voci = [{"id": "senza-destinazione", "tipo": "certificato", "testo": "Rinnova"}, {"id": "rotta", "tipo": "dubbio"}, None]
    assert _da_fare(voci) == ["senza-destinazione"]


def _schermata(vista, voce=None):
    """`schermataCheResta` di app.js con le voci di Squadra e Altro di oggi: {vista, voce, gruppo}."""
    js = codice_web.app()
    funzione = re.search(r"^function schermataCheResta\(.*?^}", js, re.S | re.M)
    assert funzione, "manca schermataCheResta in app.js"
    voci = [{"id": "squadre", "ambito": "squadra"}, {"id": "importa", "ambito": "squadra"},
            {"id": "diario", "ambito": "altro"}, {"id": "regole", "ambito": "altro"}]
    codice = (f'const VISTE = ["oggi", "formazione", "squadra", "altro"];\n{funzione.group(0)}\n'
              f"const r = schermataCheResta({json.dumps(vista)}, {json.dumps(voce)}, {json.dumps(voci)});\n"
              "console.log(JSON.stringify({ vista: r.vista, voce: r.voce ?? null, gruppo: r.gruppo ?? null }));")
    return _node(codice)


@pytest.mark.parametrize("vista, voce, attesa", [
    # le pagine di Squadra tolte: Cambi consigliati, Seguiti, Elenco dei giocatori, Calendario
    ("mercato", None, {"vista": "squadra", "voce": None, "gruppo": None}),
    ("mercato", "calendario", {"vista": "squadra", "voce": None, "gruppo": None}),
    ("squadra", "osservati", {"vista": "squadra", "voce": None, "gruppo": None}),
    # Scambi, Movimenti, Crediti e Nuova stagione: Altro
    ("scambi", None, {"vista": "altro", "voce": None, "gruppo": None}),
    ("altro", "movimenti", {"vista": "altro", "voce": None, "gruppo": None}),
    ("altro", "crediti", {"vista": "altro", "voce": None, "gruppo": None}),
    ("altro", "stagione", {"vista": "altro", "voce": None, "gruppo": None}),
    ("lega", "crediti", {"vista": "altro", "voce": None, "gruppo": None}),
    # le novità si leggono in Impostazioni > Informazioni
    ("altro", "novita", {"vista": "impostazioni", "voce": None, "gruppo": "informazioni"}),
    ("lega", "novita", {"vista": "impostazioni", "voce": None, "gruppo": "informazioni"}),
])
def test_un_indirizzo_di_una_pagina_tolta_apre_la_schermata_piu_vicina(vista, voce, attesa):
    assert _schermata(vista, voce) == attesa


@pytest.mark.parametrize("vista, voce, attesa", [
    ("oggi", None, {"vista": "oggi", "voce": None, "gruppo": None}),
    ("formazione", None, {"vista": "formazione", "voce": None, "gruppo": None}),
    ("squadra", "importa", {"vista": "squadra", "voce": "importa", "gruppo": None}),
    ("altro", "regole", {"vista": "altro", "voce": "regole", "gruppo": None}),
    ("lega", "diario", {"vista": "altro", "voce": "diario", "gruppo": None}),         # «lega» è il nome vecchio di Squadra e Altro
    ("lega", "importa", {"vista": "squadra", "voce": "importa", "gruppo": None}),
    ("impostazioni", None, {"vista": "impostazioni", "voce": None, "gruppo": None}),
    ("altro", "importa", {"vista": "altro", "voce": None, "gruppo": None}),           # la voce è di un'altra scheda: il menu
    ("__proto__", None, {"vista": "oggi", "voce": None, "gruppo": None}),             # un nome che non c'è porta a Oggi
    (None, None, {"vista": "oggi", "voce": None, "gruppo": None}),
])
def test_gli_indirizzi_delle_schermate_che_restano_non_cambiano(vista, voce, attesa):
    assert _schermata(vista, voce) == attesa
