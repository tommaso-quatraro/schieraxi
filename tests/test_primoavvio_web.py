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


# Con il passo «tempi» (dal 2/11/2026): scadenza e prima giornata, dopo la squadra.
PASSI_CON_TEMPI = ["rose", "squadra", "tempi"]


def test_l_elenco_dei_passi_ha_i_tempi_della_lega():
    src = PRIMOAVVIO_JS.read_text(encoding="utf-8")
    assert 'const PA_PASSI = ["rose", "squadra", "tempi"];' in src
    assert "scadenza_minuti" in src and "prima_giornata_lega" in src


def test_dopo_la_squadra_vengono_i_tempi():
    assert passo_dopo("squadra", ["rose", "squadra"], [], PASSI_CON_TEMPI) == "tempi"
    # la squadra scelta già nell'anteprima delle rose: dalle rose si salta direttamente ai tempi
    assert passo_dopo("rose", ["rose", "squadra"], [], PASSI_CON_TEMPI) == "tempi"


def test_tempi_fatti_o_saltati_chiude():
    assert passo_dopo("tempi", ["rose", "squadra", "tempi"], [], PASSI_CON_TEMPI) is None
    assert passo_dopo("tempi", ["rose", "squadra"], ["tempi"], PASSI_CON_TEMPI) is None


# ---- #456: nel passo «Le rose» il file si sceglie con il pulsante dell'app, come in Squadra › Aggiorna le rose ----
def _rose_html() -> str:
    testi = (RADICE / "fanta" / "web" / "testi.js").read_text(encoding="utf-8")
    codice = "\n".join([testi, "const esc = x => String(x); const stato = { account: true };",
                        PRIMOAVVIO_JS.read_text(encoding="utf-8"), "console.log(JSON.stringify(PA_SCHERMATE.rose().html));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_il_file_si_sceglie_con_il_pulsante_dell_app():
    html = _rose_html()
    campo = re.search(r"<input id=\"pa-file\"[^>]*>", html).group(0)
    assert 'type="file"' in campo and " hidden" in campo                  # il controllo del browser non si vede più
    assert re.search(r'<button class="bottone secondario" id="pa-scegli-file" type="button">Scegli il file Excel</button>', html)
    assert re.search(r'<p class="debole piccolo" id="pa-file-nome" role="status"[^>]*></p>', html)   # il nome del file scelto
    src = PRIMOAVVIO_JS.read_text(encoding="utf-8")
    assert '$("#pa-scegli-file").addEventListener("click", () => $("#pa-file").click())' in src
    assert '$("#pa-file").addEventListener("change"' in src
