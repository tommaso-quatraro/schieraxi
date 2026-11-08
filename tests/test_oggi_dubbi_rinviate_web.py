"""Oggi nel web: il dubbio dice «gioca N%» (una sola percentuale, come nel resto dell'app), «Un'altra cosa da fare» al singolare,
le partite senza data (recupero da definire) in fondo alle «Partite del turno». Con node dove serve."""
import json
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _testo(espr: str, lingua: str) -> str:
    codice = f"{TESTI}\nLINGUA = {json.dumps(lingua)};\nconsole.log(JSON.stringify({espr}));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_dubbio_con_gioca_e_altre_cose_al_singolare():
    assert _testo('t("oggi.dubbio", {p: "17%"})', "it") == "In dubbio · gioca 17%"
    assert _testo('t("oggi.dubbio", {p: "17%"})', "en") == "Doubtful · plays 17%"
    assert _testo('[tp("df.altre", 1), tp("df.altre", 3)]', "it") == ["Un'altra cosa da fare", "Altre 3 cose da fare"]
    assert _testo('[tp("df.altre", 1), tp("df.altre", 3)]', "en") == ["One more thing to do", "3 more things to do"]


def test_partite_senza_data_in_fondo():
    blocco = APP[APP.index("// partite del turno, divise per giorno"):APP.index("  pagina(`", APP.index("// partite del turno, divise per giorno"))]
    assert "Object.values(perGiorno).sort((x, y) => (x.d ? 0 : 1) - (y.d ? 0 : 1))" in blocco
    # l'ordinamento è stabile: i giorni con la data restano nell'ordine del calendario
    if NODE:
        r = subprocess.run([NODE, "-e", "const g=[{d:null,k:'?'},{d:1,k:'a'},{d:2,k:'b'}];"
                            "console.log(g.sort((x, y) => (x.d ? 0 : 1) - (y.d ? 0 : 1)).map(x=>x.k).join(''))"],
                           capture_output=True, text=True, timeout=30)
        assert r.stdout.strip() == "ab?"
