"""Formazione, «punti attesi» (come Oggi nella PR #415): il numero saliva da 0 con un'animazione (`animaNumero`, un passo a ogni
fotogramma) al primo disegno, e da quello di prima al nuovo a ogni cambio di modulo o di stile. Finché i fotogrammi non arrivano
(foto, scheda del browser in secondo piano, telefono lento) restava un numero falso, diverso da quello di Oggi. Regola dell'utente:
gli stessi numeri ovunque. Qui `mostraFormazione` gira con node, con un solo fotogramma: il numero letto deve essere quello giusto,
al primo disegno e dopo un cambio di modulo."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _funzione(nome):
    i = re.search(rf"\nfunction {nome}\(", APP).start()
    return APP[i:APP.index("\n}\n", i) + 2]


def _pezzo(inizio, fine):
    i = APP.index(inizio)
    return APP[i:APP.index(fine, i)]


def _giocatore(i, ruolo):
    return {"id": i, "nome": f"Gioc{i}", "ruolo": ruolo, "squadra": "inter", "avversario": "milan", "in_casa": True,
            "p_voto": 0.9, "fv_atteso": 6.5, "punti_attesi": 5.8}


RUOLI = "PDDDDCCCCAA" + "PDCA"
SCHEDE = {str(i + 1): _giocatore(i + 1, r) for i, r in enumerate(RUOLI)}
TITOLARI = list(range(1, 12))
FORMAZIONE = {"giornata": 11, "giornata_lega": 8, "squadra": "Real Esempio", "iniziata": False, "con_probabili": True,
              "senza_dati": [], "schede": SCHEDE,
              "livelli": [{"rischio": 0, "nome": "Equilibrata", "descrizione": "La via di mezzo.", "modulo": "4-4-2",
                           "punteggio_atteso": 65.5, "dev": 8,
                           "moduli": [{"modulo": "4-4-2", "punteggio_atteso": 65.5, "titolari": TITOLARI, "panchina": [12, 13, 14, 15]},
                                      {"modulo": "4-3-3", "punteggio_atteso": 64.7, "titolari": TITOLARI, "panchina": [12, 13, 14, 15]}]}]}


def _esegui(dopo: str):
    codice = "\n".join([
        TESTI, "LINGUA = 'it'; const SIGLE = {};",
        _pezzo("function esc(x)", "// Numero con il segno"),                # esc, sigla, num, perc
        re.search(r"^const segno = .*$", APP, re.M).group(0),
        _pezzo("const codiceStile", "// Sul campo solo il cognome"),
        _pezzo("function fraseFascia(m)", "// La ★ sta sul modulo"),
        _pezzo("function stellaNonMassimo(l)", "// Il perché della scelta in una riga"),
        _pezzo("function righePercheScelta(m, scheda)", "// Stato della scelta della giornata"),
        _pezzo("function statoScelta(", "// «oggi alle 21:40»"),
        _pezzo("const giocatoriFermi", "function mostraFormazione("),
        # pagina finta: il numero nell'HTML è il testo iniziale dell'elemento; un fotogramma solo, 30 ms dopo l'inizio
        """const vuoto = () => ""; let html = "";
const el = { textContent: "" };
const pagina = h => { html = h; const m = h.match(/id="punti-attesi">([^<]*)</); el.textContent = m ? m[1] : ""; };
const $ = sel => (sel === "#punti-attesi" ? el : null);
globalThis.document = { body: { contains: () => true }, querySelectorAll: () => [] };
globalThis.window = { scrollY: 0, scrollTo: () => {} };
globalThis.performance = { now: () => 1000 };
let fotogrammi = 0;
globalThis.requestAnimationFrame = cb => { if (fotogrammi++ < 1) cb(1030); };
const menoMovimento = () => false;
const stato = { punteggioPrec: null }; const funz = () => false;
const nomeGiornata = () => "Giornata 8"; const elidiOrdinali = s => s;
const voceGiocatore = vuoto, alternativeVicine = vuoto, intestazioneColonne = vuoto, pedina = vuoto, legendaCampo = vuoto;
const striscia = vuoto, collegaLegenda = vuoto;
const api = () => new Promise(() => {});""",
        _funzione("animaNumero") if re.search(r"\nfunction animaNumero\(", APP) else "",
        _funzione("mostraFormazione"),
        dopo,
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_formazione_mostra_i_punti_attesi_giusti_anche_se_i_fotogrammi_non_arrivano():
    numeri = _esegui(f"""mostraFormazione({json.dumps(FORMAZIONE)}, null, {{}});
const primo = el.textContent;
fotogrammi = 0;                                                   // il cambio di modulo: un altro fotogramma solo
document.querySelectorAll = () => [];
stato.scelta.modulo = "4-3-3"; stato.scelta.disegna(true);
console.log(JSON.stringify({{ primo, dopo: el.textContent }}));""")
    assert numeri == {"primo": "65,5", "dopo": "64,7"}, numeri


def test_nella_formazione_il_numero_non_sale_da_zero():
    """Spec grafica B §7.6: resta solo il movimento che risponde a un gesto, e un numero che si muove si legge a metà (foto, schede in
    secondo piano). Il numero dei punti attesi si scrive una volta, già giusto, come in Oggi."""
    assert "animaNumero(" not in _funzione("mostraFormazione")
    assert "animaNumero" not in APP and "punteggioPrec" not in APP           # nessuno la usa più: tolta
