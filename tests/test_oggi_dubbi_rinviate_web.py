"""Il dubbio dice «gioca N%» (una sola percentuale, come nel resto dell'app). «Un'altra cosa da fare» non c'è più: la lista Da fare
è diventata le decisioni in cima alla Formazione (#616, #673) e le sue chiavi sono uscite dal catalogo. Con node."""
import json
import shutil
import subprocess

import pytest

import codice_web

TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _testo(espr: str, lingua: str) -> str:
    codice = f"{TESTI}\nLINGUA = {json.dumps(lingua)};\nconsole.log(JSON.stringify({espr}));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_dubbio_con_gioca():
    assert _testo('t("oggi.dubbio", {p: "17%"})', "it") == "In dubbio · gioca 17%"
    assert _testo('t("oggi.dubbio", {p: "17%"})', "en") == "Doubtful · plays 17%"
