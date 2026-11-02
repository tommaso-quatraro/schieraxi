"""Formazione nel web (collaudo del 2/11/2026): giornata iniziata senza «Modifica a mano» né «Salva», avviso prima di lasciare una
modifica a mano non salvata, spiegazione dei titolari incerti, data dei dati in testata non tagliata sui telefoni."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_giornata_iniziata_stato_chiusa_senza_pulsanti():
    funz = APP[APP.index("const stessiIds"):APP.index("// «oggi alle 21:40»")]
    undici = list(range(1, 12))
    casi = [(None, False), ("NON_LETTA", False), ({"titolari": undici}, True), ({"titolari": undici[:10] + [99]}, True)]
    righe = ",".join(f"statoScelta({json.dumps(undici)}, {'undefined' if s == 'NON_LETTA' else json.dumps(s)}, {str(man).lower()}, false, false, true)"
                     for s, man in casi)
    r = subprocess.run([NODE, "-e", funz + f"console.log(JSON.stringify([{righe}]))"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["chiusa"] * 4                       # anche prima di leggere la scelta e dopo una modifica
    assert 'chiusa: "",' in APP                                          # nessun pulsante nella riga dello stato
    assert "${st || chiusa ? \"\" : manuale ?" in APP                    # niente «Modifica a mano» nemmeno senza riga dello stato
    assert "if (!base || !sc.manuale || f.iniziata) return;" in APP     # niente sostituzioni a mano
    assert 'e.codice === "formazione_chiusa"' in APP                     # il 409 del server ridisegna la Formazione chiusa
    for chiave in ("formazione.stato_chiusa", "formazione.stato_chiusa_tua", "err.formazione_chiusa"):
        assert TESTI.count(f'"{chiave}"') == 2, chiave
    assert '"err.formazione_chiusa": "' + server.FORMAZIONE_CHIUSA + '"' in TESTI     # il testo italiano è il messaggio del server


def test_modifica_a_mano_non_salvata_chiede_prima_di_uscire():
    assert 'window.addEventListener("beforeunload"' in APP
    assert 'if (vista !== "formazione" && !lasciaFormazione()) return;' in APP
    assert 'confirm(t("formazione.esci_senza_salvare"))' in APP
    assert 'sc.nonSalvata = !squadra && !chiusa && manuale && (st === "modificata" || (st === "mano" && !sc.manuale.uguale));' in APP
    assert TESTI.count('"formazione.esci_senza_salvare"') == 2


def test_titolari_incerti_spiegati():
    assert 'id="nota-incerti"' in APP and 'id="perche-incerto"' in APP
    assert "apriPerche(x, (inc[x.id] || {}).riga)" in APP
    assert "if (sc.manuale || f.iniziata) return r;" in APP
    assert TESTI.count('"formazione.incerto"') == 2
    assert "{p}" in TESTI.split('"formazione.incerto": "')[1].split('"')[0]


def test_data_dei_dati_su_due_righe_sui_telefoni():
    assert 'pezzo("sotto-dati", dati)' in APP and 'pezzo("sotto-sep", " · ")' in APP
    blocco = re.search(r"@media \(max-width: 480px\) \{(.*?)\n\}", CSS, re.S)
    assert blocco and ".sottotitolo > span { display: block;" in blocco.group(1) and ".sotto-sep { display: none; }" in blocco.group(1)
