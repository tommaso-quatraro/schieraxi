"""Squadra, Altro e primo avvio: dopo un salvataggio la web usa i dati nuovi (collaudo 7 del 2/11/2026).

1. Ogni rotta del server che controlla l'If-Match delle rose (o delle regole, degli avvisi) deve essere
   riconosciuta da `risorsaDi` di app.js, altrimenti la web non aggiorna l'ETag dopo la scrittura e la scrittura seguente
   risponde 412 «cambiati da un altro dispositivo» (successo nel primo avvio: «Giocatori da sistemare», poi «Questa è la mia»).
   `risorsaDi` si legge dal file e si prova con node.
2. I pannelli di Squadra e Altro disegnano le squadre lette all'apertura: dopo aver scelto la propria squadra, salvato i
   crediti o importato le rose, le squadre si rileggono (prima restavano quelle vecchie finché non si cambiava scheda).
"""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

APP = codice_web.app()
PRIMOAVVIO = codice_web.leggi("primoavvio.js")
SERVER = (server.WEB.parent / "server.py").read_text(encoding="utf-8")
NODE = shutil.which("node")

# quale ETag controlla la rotta (testo nel corpo della funzione) -> risorsa di app.js
# (i giocatori seguiti non sono più nella web, #615: la loro rotta la usa solo l'iPhone)
RISORSE = {"versioni.etag_file(ctx.rose)": "rose", "versioni.etag_file(ctx.regole)": "regole", "_etag_avvisi(ctx)": "avvisi"}


def _rotte_con_if_match():
    """(metodo, percorso, risorsa) di ogni rotta che scrive con versioni.controlla su una risorsa di RISORSE."""
    pezzi = re.split(r"\n(?=@app\.)", SERVER)
    trovate = []
    for pezzo in pezzi:
        m = re.match(r'@app\.(put|post|delete)\("([^"]+)"', pezzo)
        if not m:
            continue
        corpo = pezzo.split("\n\n\n")[0]
        for chiave, risorsa in RISORSE.items():
            if f"versioni.controlla(request, {chiave})" in corpo:
                trovate.append((m.group(1).upper(), re.sub(r"\{[^}]+\}", "1", m.group(2)), risorsa))
    return trovate


def _risorse_web(rotte):
    inizio = APP.index("function risorsaDi(")
    funzione = APP[inizio:APP.index("\n}\n", inizio) + 3]
    codice = funzione + f"\nconsole.log(JSON.stringify({json.dumps(rotte)}.map(([m, p]) => risorsaDi(p, {{ method: m, body: '{{}}' }}))));"
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_ogni_rotta_con_if_match_ha_la_sua_risorsa_nella_web():
    rotte = _rotte_con_if_match()
    percorsi = {p for _, p, _ in rotte}
    assert {"/api/rose/correggi", "/api/mia-squadra", "/api/crediti", "/api/regole"} <= percorsi        # il controllo trova le rotte
    web = _risorse_web([[m, p] for m, p, _ in rotte])
    sbagliate = [(m, p, attesa, vista) for (m, p, attesa), vista in zip(rotte, web) if vista != attesa]
    assert sbagliate == []


def _funzione(nome: str) -> str:
    inizio = APP.index(f"function {nome}(")
    return APP[inizio:APP.index("\n}\n", inizio)]


def test_dopo_un_salvataggio_le_pagine_rileggono_le_squadre():
    """La mia squadra scelta, le rose importate (Impostazioni > La mia lega, #618): dopo ognuno si rileggono le squadre, così «La
    mia squadra», i crediti e l'elenco delle squadre non restano quelli di prima; la pagina si ridisegna solo se si è ancora in
    Impostazioni."""
    scelta = _funzione("collegaSceltaMia")
    dopo = scelta[scelta.index('"/api/mia-squadra"'):]
    assert "caricaSquadre()" in dopo[:dopo.index("catch")] and 'if (stato.vista === "impostazioni") vaiQui();' in dopo
    rose = _funzione("vistaImportaRose")
    esito = rose[rose.index("const mostraEsito"):rose.index("const controlla")]
    assert "caricaSquadre()" in esito


def test_primo_avvio_toglie_il_giocatore_sistemato_dal_conto():
    # «Giocatori da sistemare (2)» restava 2 dopo averne sistemato uno
    inizio = PRIMOAVVIO.index("async function paNonRiconosciuti(")
    corpo = PRIMOAVVIO[inizio:PRIMOAVVIO.index("\n}\n", inizio)]
    assert "paContaDaSistemare(dove)" in corpo
    assert "function paContaDaSistemare(" in PRIMOAVVIO
