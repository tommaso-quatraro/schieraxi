"""Oggi, «punti attesi» (foto della PR #415): Oggi mostrava 8,9 e 11,8 mentre la Formazione, per la stessa formazione, mostrava 65,5.
Il campo era lo stesso (`formazione.punteggio_atteso` di /api/oggi, uguale al modulo di /api/formazione); il numero però saliva da 0
con un'animazione (`animaNumero`, un passo a ogni fotogramma): finché i fotogrammi non arrivano (foto, scheda del browser in secondo
piano, telefono lento) restava un numero falso. Regola dell'utente: gli stessi numeri ovunque. Qui `mostraOggi` gira con node, con
un solo fotogramma: il numero letto deve essere quello della Formazione."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _funzione(nome):
    i = re.search(rf"\nfunction {nome}\(", APP).start()
    return APP[i:APP.index("\n}\n", i) + 2]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_oggi_mostra_i_punti_attesi_della_formazione_anche_se_i_fotogrammi_non_arrivano():
    oggi = {"fase": "prima", "giornata": 11, "giornata_lega": 8, "scadenza": "2099-11-14 14:50", "con_probabili": True,
            "formazione": {"modulo": "4-4-2", "punteggio_atteso": 65.5, "tua_scelta": False}, "avvisi": [], "migliori": [], "partite": []}
    formazione = {"moduli": [{"modulo": "4-4-2", "punteggio_atteso": 65.5}]}          # lo stesso numero in /api/formazione
    codice = "\n".join([
        TESTI, "LINGUA = 'it';",
        re.search(r"^const num = .*$", APP, re.M).group(0),
        _funzione("animaNumero"),
        # pagina finta: il numero nell'HTML è il testo iniziale dell'elemento; un fotogramma solo, 30 ms dopo l'inizio
        """const esc = s => String(s ?? ""); const vuoto = () => ""; let html = "";
const el = { textContent: "" };
const pagina = h => { html = h; const m = h.match(/id="oggi-punti">([^<]*)</); el.textContent = m ? m[1] : ""; };
const $ = sel => (sel === "#oggi-punti" ? el : null);
globalThis.document = { body: { contains: () => true } };
globalThis.performance = { now: () => 1000 };
globalThis.requestAnimationFrame = cb => { if (!globalThis.fatto) { globalThis.fatto = true; cb(1030); } };
const menoMovimento = () => false;
const testoConto = () => ({ grande: "1 giorno", piccolo: "" }); const nomeGiornata = () => "Giornata 8";
const miaSquadra = () => null; const parseData = () => null; const quando = vuoto;
const LiveSchieraxi = { punteggioUfficiale: vuoto, chiave: vuoto }; const urlImg = vuoto; const fraseFascia = vuoto;
const cardRiepilogo = vuoto, cardSenzaFormazione = vuoto, cardInCorso = vuoto, cardRinvio = vuoto, cardDaFare = vuoto;
const novitaDaVedere = () => false; const stato = {};
const intestazioneColonne = vuoto, voceGiocatore = vuoto, rigaAvviso = vuoto, collegaDaFare = vuoto, collegaRinvio = vuoto;
const funz = () => false; const avviaLive = vuoto; let timerConto = null; globalThis.setInterval = () => 0;""",
        _funzione("mostraOggi"),
        f"mostraOggi({json.dumps(oggi)});",
        f"console.log(JSON.stringify({{ oggi: el.textContent, formazione: num({json.dumps(formazione)}.moduli[0].punteggio_atteso) }}));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    numeri = json.loads(r.stdout.strip().splitlines()[-1])
    assert numeri["oggi"] == numeri["formazione"] == "65,5", numeri


def test_in_oggi_il_numero_non_sale_da_zero():
    """Spec grafica B §7.6: resta solo il movimento che risponde a un gesto; il numero che sale da 0 all'apertura di Oggi non lo è."""
    assert "animaNumero(" not in _funzione("mostraOggi")
