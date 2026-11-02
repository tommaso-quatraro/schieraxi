"""Primo avvio (fanta/web/primoavvio.js): quale passo viene dopo. La funzione `paPassoDopo` si legge dal file e si prova con node."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
PRIMOAVVIO_JS = RADICE / "fanta" / "web" / "primoavvio.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")

PASSI = ["rose", "squadra"]


def _funzione() -> str:
    src = PRIMOAVVIO_JS.read_text(encoding="utf-8")
    m = re.search(r"^function paPassoDopo\(.*?^\}\n", src, re.S | re.M)
    assert m, "paPassoDopo non trovata in primoavvio.js"
    return m.group(0)


def passo_dopo(attuale, fatti, saltati, passi=PASSI):
    codice = _funzione() + (
        f"\nconsole.log(JSON.stringify(paPassoDopo({json.dumps(passi)}, {json.dumps(attuale)}, "
        f"{json.dumps(fatti)}, {json.dumps(saltati)})));"
    )
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_dalle_rose_si_va_alla_squadra():
    assert passo_dopo("rose", [], []) == "squadra"


def test_saltate_le_rose_avanti_sulla_squadra_chiude_il_primo_avvio():
    # Il bug: senza rose, «Avanti» sul passo della squadra restava lì. Ora non c'è più nessun passo aperto: null = si chiude.
    assert passo_dopo("squadra", [], ["rose"]) is None


def test_tutto_fatto_chiude():
    assert passo_dopo("squadra", ["rose", "squadra"], []) is None


def test_se_le_rose_sono_saltate_ma_la_squadra_e_aperta_si_va_alla_squadra():
    assert passo_dopo("rose", [], ["rose"]) == "squadra"


def test_non_torna_mai_al_passo_attuale_se_ce_n_e_un_altro_aperto():
    # Dalla squadra, con le rose ancora aperte: si torna alle rose, non si resta sulla squadra.
    assert passo_dopo("squadra", [], []) == "rose"
