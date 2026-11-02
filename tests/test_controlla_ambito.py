"""Job «ambito»: la PR dichiara le sue aree (riga «Aree: …» nella descrizione) e non tocca file fuori da quelle."""
import importlib.util
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("controlla_ambito", RADICE / "script" / "ci" / "controlla_ambito.py")
ambito = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ambito)


def test_legge_le_aree_dalla_descrizione():
    corpo = "## Cosa cambia\nbla\n\nAree: `fanta/web`, docs/ , tests\r\nCloses #3\n"
    assert ambito.aree(corpo) == ["fanta/web", "docs", "tests"]
    assert ambito.aree("niente riga") == []
    assert ambito.aree("Aree:   \n") == []
    assert ambito.aree("<!-- Aree: esempio -->\naree: ios") == ["ios"]   # i commenti del modello non contano


def test_file_dentro_e_fuori_dalle_aree():
    file = ["fanta/web/app.js", "fanta/webby.py", "docs/API.md", "fanta/novita.d/x.json", "README.md"]
    # fanta/novita.d è sempre ammessa (la chiede il job «versione»); «fanta/web» non comprende «fanta/webby.py»
    assert ambito.fuori(file, ["fanta/web", "docs"]) == ["fanta/webby.py", "README.md"]
    assert ambito.fuori(["README.md", "ios/Sources/A.swift"], ["README.md", "ios/*"]) == []


def test_esenti_bot_e_soli_documenti():
    assert ambito.esente("dependabot[bot]", ["requirements.txt"])
    assert ambito.esente("github-actions[bot]", ["fanta/novita.json"])
    assert ambito.esente("persona", ["docs/A.md", "MAPPA.md", "docs/decisioni/0001-x.md"])
    assert not ambito.esente("persona", ["docs/A.md", "fanta/server.py"])
    assert not ambito.esente("persona", [])


def test_main_esito_e_messaggi(capsys):
    assert ambito.main("persona", "Aree: fanta/web", ["fanta/web/app.js"]) == 0
    assert ambito.main("persona", "Aree: fanta/web", ["fanta/server.py"]) == 1
    assert "fanta/server.py" in capsys.readouterr().out
    assert ambito.main("persona", "senza aree", ["fanta/server.py"]) == 1
    assert "Aree:" in capsys.readouterr().out
    assert ambito.main("dependabot[bot]", "", ["requirements.txt"]) == 0


def test_job_ambito_segnala_soltanto_e_non_blocca_l_unione():
    testo = (RADICE / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    inizio = testo.index("\n  ambito:\n")
    blocco = testo[inizio:testo.index("\n  versione:\n", inizio)]
    assert "continue-on-error: true" in blocco and "_ci-main/script/ci/controlla_ambito.py" in blocco
    assert "CORPO: ${{ github.event.pull_request.body }}" in blocco
    assert "${{ github.event.pull_request.body }}" not in blocco.split("run: |")[1], "testo della PR dentro il comando"
    unisci = testo[testo.index("\n  unisci:\n"):]
    needs = unisci.split("needs:")[1].split("\n")[0]
    assert "ambito" not in needs
