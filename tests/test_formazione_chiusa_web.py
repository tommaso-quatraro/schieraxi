"""Formazione nel web (collaudo del 2/11/2026): giornata iniziata senza «Modifica a mano» né «Salva», avviso prima di lasciare una
modifica a mano non salvata, spiegazione dei titolari incerti, data dei dati in testata non tagliata sui telefoni."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def test_data_dei_dati_intera_sui_telefoni():
    """In una riga sola la data dei dati si tagliava (390 px, anche in inglese a 430). Ora sta nella riga di stato sotto il titolo,
    in un pezzo suo che non si spezza a metà («dati del 26 ott 23:55»): se non ci sta va a capo intero, dopo il « · »."""
    assert "pezzi.map(p => `<span>${esc(p)}</span>`).join(\" · \")" in APP
    corpo = re.search(r"\n\.stato-pagina > span \{([^}]*)\}", CSS)
    assert corpo and "display: inline-block" in corpo.group(1) and "max-width: 100%" in corpo.group(1)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_a_partita_finita_il_voto_preso_al_posto_di_gioca():
    inizio = APP.index("// A partita iniziata «gioca N%» non serve più")
    funz = APP[inizio:APP.index("function pedina(")]
    base = ("const PARTITA_INIZIATA=['in_corso','attesa_voti','fatto','senza_voto'];"
            "const etichettaPronta = x => !!(x && x.etichetta && typeof x.etichetta.testo === 'string' && x.etichetta.testo);"
            "const STATO_PARTITA={fatto:['tit.st_fatto',''],senza_voto:['tit.st_senza_voto','arancio'],attesa_voti:['tit.st_attesa_voti','neutra'],in_corso:['tit.st_in_corso','']};"
            "const T={'formazione.fv_preso':'fantavoto {fv}','tit.st_attesa_voti':'Voto in arrivo','tit.st_senza_voto':'Senza voto','tit.st_in_corso':'In corso','tit.st_fatto':'Ha giocato'};"
            r"const t=(k,v={})=>T[k].replace(/\{(\w+)\}/g,(m,x)=>v[x]); const num=x=>String(x).replace('.',',');")
    prova = ("console.log(JSON.stringify([esitoPartita({stato_partita:'fatto',fv_preso:9.5}), esitoPartita({stato_partita:'attesa_voti'}),"
             "esitoPartita({stato_partita:'in_corso'}), esitoPartita({stato_partita:'da_giocare'}), esitoPartita({}),"
             "esitoPartita({stato_partita:'attesa_voti', etichetta:{codice:'voto_in_arrivo', testo:'Grade coming', tono:'neutro'}}),"
             "esitoPartita({stato_partita:'fatto', fv_preso:7, etichetta:{codice:'voto', testo:'Played', tono:'positivo'}})]))")
    r = subprocess.run([NODE, "-e", base + funz + prova], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [{"fv": 9.5, "testo": "fantavoto 9,5"}, {"fv": None, "testo": "Voto in arrivo"},
                                    {"fv": None, "testo": "In corso"}, None, None,
                                    {"fv": None, "testo": "Grade coming"}, {"fv": 7, "testo": "fantavoto 7"}]
    assert TESTI.count('"formazione.fv_preso"') == 2
