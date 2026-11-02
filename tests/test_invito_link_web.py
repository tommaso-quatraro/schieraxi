"""Link d'invito (fanta/web/app.js): `?invito=CODICE` apre «Registrati» con il codice già scritto.
La funzione pura `invitoDaIndirizzo` si legge dal file e si prova con node; il resto si controlla sul testo del file."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
APP_JS = (RADICE / "fanta" / "web" / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _da_indirizzo(search: str) -> str:
    m = re.search(r"^function invitoDaIndirizzo\(.*?^\}\n", APP_JS, re.S | re.M)
    assert m, "invitoDaIndirizzo non trovata in app.js"
    codice = m.group(0) + f"\nconsole.log(JSON.stringify(invitoDaIndirizzo({json.dumps(search)})));"
    out = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, timeout=30, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(NODE is None, reason="node non installato")
@pytest.mark.parametrize("search, atteso", [
    ("?invito=ABCDE-FGHIJ-KLMNO-PQRST", "ABCDE-FGHIJ-KLMNO-PQRST"),
    ("?invito=abcde%20fghij", "ABCDEFGHIJ"),                      # minuscole e spazi (scritto a mano)
    ("?vista=oggi&invito=AB12C", "AB12C"),
    ("", ""), ("?invito=", ""), ("?altro=1", ""),
    ("?invito=AB", ""),                                           # troppo corto: non è un codice
    ("?invito=" + "A" * 41, ""),                                  # troppo lungo
    ("?invito=%3Cscript%3E%22onfocus%3D", "SCRIPTONFOCUS"),       # niente caratteri che possano uscire dall'attributo
])
def test_codice_dal_link(search, atteso):
    assert _da_indirizzo(search) == atteso


def test_il_codice_si_toglie_dall_indirizzo_e_si_scrive_nel_campo():
    assert 'u.searchParams.delete("invito")' in APP_JS and "history.replaceState" in APP_JS
    assert APP_JS.count("SENZA_AIUTI + valoreInvito()") == 2           # registrazione e primo accesso con Google
    assert 'mostraAccesso("", invito ? "registra" : "accedi")' in APP_JS
    assert APP_JS.count("dimenticaInvito();") == 3                    # dopo ogni registrazione riuscita


def test_l_amministratore_riceve_il_link():
    assert "linkInvito(r.codice)" in APP_JS and 'id="adm-copia-messaggio"' in APP_JS
    assert 'tp("admin.utenti_riepilogo", r.utenti.length' in APP_JS
