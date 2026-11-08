"""Parte web dei risultati in diretta: la logica di `fanta/web/live.js` (provata con node) e il collegamento ai file dell'app."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import codice_web

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "fanta" / "web"
LIVE_JS = WEB / "live.js"
NODE = shutil.which("node")


def esegui(codice: str):
    r = subprocess.run([NODE, "-e", f"const L=require({json.dumps(str(LIVE_JS))});{codice}"], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")

P = '{casa:"inter",trasferta:"fiorentina",data:"2026-10-31 15:00",stato:"primo_tempo",minuto:"34\'",gol_casa:1,gol_trasferta:0,eventi:[]}'


def test_testi_di_stato_e_punteggio():
    out = esegui(f"""const p={P};
      const s=(st,extra={{}})=>L.etichetta({{...p,stato:st,...extra}});
      console.log(JSON.stringify({{
        pt:s("primo_tempo"), int:s("intervallo"), fin:s("finita"), rin:s("rinviata"), sosp:s("sospesa"), prima:s("da_giocare"),
        punti:L.punteggio(p), puntiPrima:L.punteggio({{...p,stato:"da_giocare",gol_casa:null,gol_trasferta:null}}),
        puntiRinv:L.punteggio({{...p,stato:"rinviata"}}), strano:s("stato_nuovo"), chiave:L.chiave(p),
        stranoVuoto:s("stato_nuovo",{{gol_casa:null,gol_trasferta:null}}), puntiStrano:L.punteggio({{...p,stato:"stato_nuovo"}}),
        puntiStranoVuoto:L.punteggio({{...p,stato:"stato_nuovo",gol_casa:null,gol_trasferta:null}}), dirStrano:L.inDiretta({{...p,stato:"stato_nuovo"}})}}))""")
    assert out["pt"] == {"live": True, "testo": "LIVE", "minuto": "34'"}
    assert out["int"] == {"live": True, "testo": "LIVE", "minuto": "Intervallo"}
    assert out["fin"]["testo"] == "Finita" and not out["fin"]["live"]
    assert out["rin"]["testo"] == "Rinviata" and out["sosp"]["testo"] == "Sospesa"
    assert out["prima"]["testo"] is None
    assert out["strano"] == {"live": True, "testo": "LIVE", "minuto": "34'"}   # stato mai visto CON punteggio: in corso, non «vs»
    assert out["stranoVuoto"]["testo"] is None and out["puntiStranoVuoto"] is None          # senza punteggio si lascia l'orario
    assert out["puntiStrano"] == "1 – 0" and out["dirStrano"] is True
    assert out["punti"] == "1 – 0" and out["puntiPrima"] is None and out["puntiRinv"] is None
    assert out["chiave"] == "inter|fiorentina"


def test_quando_richiedere_ancora():
    out = esegui(f"""const p={P}; const d=(h,m)=>new Date(2026,9,31,h,m);
      const con=(st,data,ad)=>L.prossimoControllo({{partite:[{{...p,stato:st,data}}]}},ad);
      console.log(JSON.stringify({{
        inGioco: con("secondo_tempo","2026-10-31 15:00",d(16,0)), intervallo: con("intervallo","2026-10-31 15:00",d(15,50)),
        pocoPrima: con("da_giocare","2026-10-31 15:00",d(14,55)), tra3Ore: con("da_giocare","2026-10-31 18:00",d(15,0)),
        tra2Giorni: con("da_giocare","2026-11-02 18:00",d(15,0)), finita: con("finita","2026-10-31 15:00",d(17,0)),
        vuota: L.prossimoControllo({{partite:[]}},d(15,0)), nulla: L.prossimoControllo(null,d(15,0))}}))""")
    assert out["inGioco"] == 45000 and out["intervallo"] == 45000 and out["pocoPrima"] == 60000
    assert out["tra3Ore"] == (3 * 60 - 10) * 60000                       # sveglia 10 minuti prima del calcio d'inizio
    assert out["tra2Giorni"] is None and out["finita"] is None and out["vuota"] is None and out["nulla"] is None


def test_gol_nuovi_solo_dopo_la_prima_lettura():
    out = esegui(f"""const p={P}, prec={{}}; const v=(a,b)=>({{partite:[{{...p,gol_casa:a,gol_trasferta:b}}]}});
      const prima=L.gol(prec,v(1,0)), uguale=L.gol(prec,v(1,0)), segna=L.gol(prec,v(2,0)), pareggio=L.gol(prec,v(2,1)), annullato=L.gol(prec,v(1,1));
      console.log(JSON.stringify({{prima,uguale,segna,pareggio,annullato}}))""")
    assert out == {"prima": [], "uguale": [], "segna": ["inter|fiorentina"], "pareggio": ["inter|fiorentina"], "annullato": []}


def test_eventi_e_miei_giocatori():
    out = esegui("""const ev=[{tipo:"gol"},{tipo:"giallo"},{tipo:"rosso"},{tipo:"<img>"},{tipo:"rigore"}];
      const tit=[{nome:"Thuram"},{nome:"Esposito Se."},{nome:"Dia"}];
      console.log(JSON.stringify({
        gioco:L.eventiVisibili({stato:"primo_tempo",eventi:ev}).map(e=>e.tipo), fine:L.eventiVisibili({stato:"finita",eventi:ev}).map(e=>e.tipo),
        senza:L.eventiVisibili({stato:"finita"}),
        thuram:L.eMio("M. Thuram",tit), esposito:L.eMio("Sebastiano Esposito",tit), accenti:L.eMio("Éspósito",tit), altro:L.eMio("Lautaro Martínez",tit),
        corto:L.eMio("A. Dia Ndiaye",tit), vuoto:L.eMio("",tit), niente:L.eMio("Thuram",null)}))""")
    assert out["gioco"] == ["gol", "rosso", "rigore"] and out["fine"] == ["gol", "rosso", "rigore"]      # gialli e tipi sconosciuti scartati
    t = esegui("""console.log(JSON.stringify([L.testoEvento({tipo:"rigore",minuto:"6'",chi:"Varela"}), L.testoEvento({tipo:"gol",minuto:"33'",chi:"Pobega",assist:"Ferguson"}),
      L.testoEvento({tipo:"rosso",minuto:"58'",chi:"Lucchesi"}), L.testoEvento({tipo:"autogol",minuto:"70'",chi:"Rui"}), L.testoEvento({tipo:"rigore_sbagliato",minuto:"80'",chi:"Dia"})]))""")
    assert t == ["6' Varela (rig.)", "33' Pobega (ass. Ferguson)", "58' Lucchesi", "70' Rui (autogol)", "80' Dia (rig. sbagliato)"]
    assert out["senza"] == []
    assert out["thuram"] and out["esposito"] and out["accenti"] and not out["altro"]
    assert not out["corto"] and not out["vuoto"] and not out["niente"]       # «Dia» ha 3 lettere: troppo corto per fidarsi


def test_collegamenti_con_l_app():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert html.index('src="live.js"') < html.index('src="app.js"')                 # app.js usa LiveSchieraxi all'avvio
    assert '"/live.js"' in codice_web.leggi("sw.js")                 # anche senza rete
    assert '"/live.js"' in (RADICE / "fanta" / "rotte_account.py").read_text(encoding="utf-8")
    app = codice_web.app()
    assert "innerHTML" not in app[app.index("function disegnaLive"):app.index("// ---------------------------------------------------------------- formazione")]     # solo textContent con dati di fuori
    assert "document.hidden" in app and "visibilitychange" in app                    # mai richieste con la scheda nascosta


def test_la_pagina_oggi_carica_senza_errori_di_sintassi():
    r = subprocess.run([NODE, "--check", str(WEB / "app.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
