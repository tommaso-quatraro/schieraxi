"""Oggi mostra i risultati ufficiali delle partite giocate anche senza i risultati in diretta (funzione spenta o fonte giù):
`partite[].gol_casa`/`gol_trasferta` in GET /api/oggi, e il web li scrive al posto di «vs» già al primo disegno."""
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from test_fasi import ambiente, _oggi  # noqa: F401 - ambiente è una fixture

from fanta import gestione
import codice_web

WEB = Path(__file__).resolve().parent.parent / "fanta" / "web"
APP = codice_web.app()
NODE = shutil.which("node")


def test_partite_giocate_con_il_risultato_ufficiale(ambiente):
    ambiente.db.execute("UPDATE partite SET giocata = 1, gol_casa = 2, gol_trasferta = 0 WHERE casa = 'inter' AND giornata = 10")
    ambiente.db.commit()
    o = _oggi(ambiente, datetime(2026, 11, 8, 12, 0))
    p = {x["casa"]: x for x in o["partite"]}
    assert (p["inter"]["giocata"], p["inter"]["gol_casa"], p["inter"]["gol_trasferta"]) == (True, 2, 0)
    assert (p["roma"]["gol_casa"], p["roma"]["gol_trasferta"]) == (None, None)       # non ancora giocata: niente numeri


def test_anche_senza_rose(ambiente):
    ambiente.db.execute("UPDATE partite SET giocata = 1, gol_casa = 1, gol_trasferta = 1 WHERE casa = 'inter' AND giornata = 10")
    ambiente.db.commit()
    o = gestione.oggi_senza_rose(ambiente.db, adesso=datetime(2026, 11, 8, 12, 0))
    p = {x["casa"]: x for x in o["partite"]}
    assert (p["inter"]["gol_casa"], p["inter"]["gol_trasferta"]) == (1, 1) and p["napoli"]["gol_casa"] is None


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_punteggio_ufficiale_nel_web():
    codice = f"""const L=require({json.dumps(str(WEB / "live.js"))});
    const p={{casa:"inter",trasferta:"lecce",giocata:true,stato:"finita",gol_casa:2,gol_trasferta:0}};
    console.log(JSON.stringify([L.punteggioUfficiale(p), L.punteggioUfficiale({{...p,giocata:false}}),
      L.punteggioUfficiale({{...p,gol_casa:null}}), L.punteggioUfficiale({{casa:"a",trasferta:"b"}})]))"""
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["2 – 0", None, None, None]


def test_il_disegno_di_oggi_usa_il_punteggio_ufficiale_anche_senza_diretta():
    assert "LiveSchieraxi.punteggioUfficiale(p)" in APP                # primo disegno, prima e senza /api/live
    assert 'data-pt="' in APP
    assert "pt || el.dataset.pt" in APP                                # la diretta senza punteggio non cancella quello ufficiale
