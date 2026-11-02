"""Etichette dei giocatori nel web (collaudo 2/11/2026): una sola percentuale sul giocare («gioca N%»), le etichette a parole e
senza numero, a giornata iniziata lo stato vero della partita al posto delle probabili. Funzioni di app.js provate con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="serve node")


def _esegui(chiamata: str):
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    pezzi = [re.search(r"^const TITOLARITA = \{.*?\};$", APP, re.M | re.S).group(0)]
    inizio = APP.index("// A parole e senza numero")
    pezzi.append(APP[inizio:APP.index("// Il tocco sul fantavoto atteso")])
    pezzi.append(re.search(r"^const partenzaAParole = .*$", APP, re.M).group(0))
    codice = f"{testi}\n" + "\n".join(pezzi) + f"\nconsole.log(JSON.stringify({chiamata}));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_etichetta_a_parole_senza_numero():
    casi = [{"titolarita": "titolare", "stato": "titolare", "percentuale": 60}, {"titolarita": "ballottaggio", "stato": "titolare", "percentuale": 55},
            {"titolarita": "panchina", "stato": "panchina", "percentuale": 25}, {"titolarita": "improbabile"}, {"titolarita": "fuori", "stato": "infortunato"}]
    html = _esegui(f"{json.dumps(casi)}.map(pillTitolarita)")
    assert [re.sub(r"<[^>]+>", "", h) for h in html] == ["Probabile titolare", "In ballottaggio", "Probabile panchina", "Improbabile", "Fuori"]
    assert not any("%" in h for h in html)


def test_a_giornata_iniziata_lo_stato_della_partita():
    casi = [{"titolarita": None, "stato_partita": s} for s in ("fatto", "senza_voto", "attesa_voti", "in_corso", "da_giocare", "rinviata")]
    testi = [re.sub(r"<[^>]+>", "", h) for h in _esegui(f"{json.dumps(casi)}.map(pillTitolarita)")]
    assert testi == ["Ha giocato", "Senza voto", "Voto in arrivo", "Partita in corso", "Da giocare", "Rinviata"]
    # niente etichetta se il server non sa lo stato; un valore sconosciuto non passa nell'HTML
    assert _esegui('[pillTitolarita({titolarita: null}), pillTitolarita({titolarita: null, stato_partita: "<b>"})]') == ["", ""]


def test_quanto_parte_titolare_a_parole():
    assert _esegui("[0.9, 0.5, 0.1, null].map(partenzaAParole)") == ["quasi sempre titolare", "a volte titolare", "di solito entra dopo", "–"]


def test_a_formazione_chiusa_niente_alternative():
    assert 'if (f.iniziata || x.titolarita == null || x.titolarita === "titolare") return ""' in APP
    assert "const nonGioca = !!pr && pr.titolarita === \"fuori\"" in APP           # scheda: chi non gioca non ha la partita
