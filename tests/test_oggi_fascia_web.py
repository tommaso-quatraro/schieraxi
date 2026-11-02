"""In Oggi la fascia dei punti attesi si legge come sull'iPhone: «tra 62 e 84 · 8 volte su 10»."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _frase(m: dict) -> str:
    inizio = APP.index("function fraseFascia(m) {")
    fine = APP.index("\n}\n", inizio) + 3
    num = re.search(r"^const num = .*$", APP, re.M).group(0)
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    codice = f"{testi}\n{num}\n{APP[inizio:fine]}\nconsole.log(JSON.stringify(fraseFascia({json.dumps(m)})));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_oggi_mostra_la_fascia_sotto_i_punti_attesi():
    assert 'id="oggi-fascia"' in APP and "fraseFascia(o.formazione)" in APP


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_frase_della_fascia_come_ios():
    assert _frase({"intervallo": {"basso": 62.2, "alto": 83.9, "confidenza": 0.8}}) == "tra 62 e 84 · 8 volte su 10"
    assert _frase({"intervallo": {"basso": 63, "alto": 81.6, "confidenza": 0.8, "indicativo": True}}) == "tra 63 e 82 · 8 volte su 10 (indicativo)"
    assert _frase({"intervallo": {"basso": 60, "alto": 80, "confidenza": 0.95}}) == "tra 60 e 80 · 19 volte su 20"
    assert _frase({"intervallo": {"basso": 60, "alto": 80}}) == "tra 60 e 80"                         # senza confidenza non si inventa
    assert _frase({"intervallo": {"basso": 90, "alto": 80, "confidenza": 0.8}, "dev": 7.3}) == "oscilla di ±7"   # fascia storta: ripiego
    assert _frase({"intervallo": None, "dev": 7.3}) == "oscilla di ±7"                                  # server vecchio
    assert _frase({"intervallo": None, "dev": None}) == ""
