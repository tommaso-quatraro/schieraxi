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


WORKFLOW = RADICE / ".github" / "workflows" / "test.yml"


def _blocco_ambito() -> str:
    testo = WORKFLOW.read_text(encoding="utf-8")
    inizio = testo.index("\n  ambito:\n")
    return testo[inizio:testo.index("\n  versione:\n", inizio)]


def test_main_scrive_errori_e_non_avvisi(capsys):
    """L'ambito è bloccante: i messaggi sono errori di GitHub Actions."""
    ambito.main("persona", "Aree: fanta/web", ["fanta/server.py"])
    ambito.main("persona", "senza aree", ["fanta/server.py"])
    uscita = capsys.readouterr().out
    assert uscita.count("::error ") == 2 and "::warning" not in uscita


def test_job_ambito_blocca_l_unione():
    blocco = _blocco_ambito()
    assert "continue-on-error" not in blocco
    assert "_ci-main/script/ci/controlla_ambito.py" in blocco and "_ci-main/script/ci/controlla_pr.py" in blocco
    assert "CORPO: ${{ github.event.pull_request.body }}" in blocco
    assert "BOZZA: ${{ github.event.pull_request.draft }}" in blocco
    for comando in blocco.split("run: |")[1:]:
        assert "${{" not in comando.split("\n      - ")[0], "testo della PR (o un'espressione) dentro il comando"
    testo = WORKFLOW.read_text(encoding="utf-8")
    unisci = testo[testo.index("\n  unisci:\n"):testo.index("\n  rilascia:\n")]
    needs = unisci.split("needs:")[1].split("\n")[0]
    assert "ambito" in needs and "needs.ambito.result == 'success'" in unisci


def test_controlla_pr_salta_se_non_e_ancora_su_main():
    """Gli script si prendono da main: finché controlla_pr.py non c'è, il passo lo dice e non blocca."""
    blocco = _blocco_ambito()
    assert "if [ ! -f _ci-main/script/ci/controlla_pr.py ]" in blocco
    assert "git diff --name-status HEAD^1 HEAD | python3 -I -s _ci-main/script/ci/controlla_pr.py" in blocco


def test_una_modifica_della_descrizione_non_rilancia_i_controlli():
    """Scelta: niente «edited» fra gli eventi. La revisione si scrive in bozza e «gh pr ready» rifà tutti i controlli con la
    descrizione nuova; con «edited» ogni ritocco del testo annullerebbe la corsa in corso (stesso gruppo di concurrency)."""
    testo = WORKFLOW.read_text(encoding="utf-8")
    tipi = testo.split("pull_request:", 1)[1].split("types:", 1)[1].split("\n")[0]
    assert "edited" not in tipi and "ready_for_review" in tipi
