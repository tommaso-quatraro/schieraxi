"""La revisione IA delle PR (.github/workflows/revisione.yml, chiamata dal job «revisione-ia» di test.yml).

Regole di sicurezza (repository pubblico) e di unione: docs/decisioni/0007-revisione-ia-in-ci.md."""
import json
import re
from pathlib import Path

from test_workflow_controlli import WORKFLOW, _job

RADICE = Path(__file__).resolve().parent.parent
REVISIONE = RADICE / ".github" / "workflows" / "revisione.yml"
SKILL = RADICE / ".claude" / "skills" / "revisione-pr" / "SKILL.md"


def _testo() -> str:
    return REVISIONE.read_text(encoding="utf-8")


def _blocco_job_test(nome: str) -> str:
    testo = WORKFLOW.read_text(encoding="utf-8")
    inizio = re.search(rf"^  {re.escape(nome)}:\s*$", testo, re.M).end()
    dopo = re.search(r"^  [A-Za-z0-9_-]+:\s*$", testo[inizio:], re.M)
    return testo[inizio:inizio + dopo.start() if dopo else len(testo)]


def test_revisione_ia_parte_solo_per_pr_non_in_bozza_del_repository_e_non_di_bot():
    cond = _job()["revisione-ia"]["if"]
    assert "github.event_name == 'pull_request'" in cond
    assert "!github.event.pull_request.draft" in cond
    assert "github.event.pull_request.head.repo.full_name == github.repository" in cond
    assert "github.event.pull_request.user.type != 'Bot'" in cond


def test_revisione_ia_passa_il_segreto_per_nome_e_ha_permessi_minimi():
    blocco = _blocco_job_test("revisione-ia")
    assert "uses: ./.github/workflows/revisione.yml" in blocco
    assert "secrets: inherit" not in blocco
    assert "CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in blocco
    permessi = re.findall(r"^      ([a-z-]+): (read|write)", blocco, re.M)
    assert sorted(permessi) == [("contents", "read"), ("pull-requests", "write")]


def test_unisci_aspetta_la_revisione_verde():
    job = _job()
    assert "revisione-ia" in job["unisci"]["needs"]
    assert "needs.revisione-ia.result == 'success'" in job["unisci"]["if"]


def test_revisione_su_server_di_github_con_permessi_minimi_e_una_corsa_per_pr():
    testo = _testo()
    assert "workflow_call:" in testo and ("pull_request" + "_target") not in testo and "workflow_run" not in testo
    assert re.findall(r"runs-on:\s*(\S+)", testo) == ["ubuntu-latest"]
    permessi = set(re.findall(r"^\s+([a-z-]+): (read|write)\b", testo, re.M))
    assert permessi == {("contents", "read"), ("pull-requests", "write")}, "niente id-token né altre scritture"
    assert "group: revisione-ia-${{ github.event.pull_request.number }}" in testo
    assert "cancel-in-progress: true" in testo


def test_configurazione_sicura_dell_azione():
    testo = _testo()
    assert re.search(r"uses: anthropics/claude-code-action@[0-9a-f]{40}\s", testo)
    assert "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in testo
    assert "allowed_non_write_users" not in testo and "allowed_bots" not in testo
    assert 'show_full_output: "false"' in testo
    assert re.search(r"--max-turns (\d+)", testo) and int(re.search(r"--max-turns (\d+)", testo).group(1)) <= 30
    strumenti = re.search(r'--allowedTools "([^"]+)"', testo).group(1).split(",")
    for vietato in ("Write", "Edit", "Bash", "Bash(*)", "WebFetch", "WebSearch"):
        assert vietato not in strumenti, f"strumento {vietato} non ammesso nella revisione"
    assert all(not s.startswith("Bash(") or s.startswith("Bash(gh pr ") for s in strumenti)


def test_lo_schema_dell_esito_e_quello_del_cancello():
    schema = json.loads(re.search(r"--json-schema '([^']+)'", _testo()).group(1))
    assert schema["required"] == ["bloccanti", "sintesi"]
    assert schema["properties"]["bloccanti"]["type"] == "integer"
    assert schema["properties"]["sintesi"]["type"] == "string"


def test_il_segreto_non_si_stampa_e_l_esito_non_entra_nei_comandi():
    testo = _testo()
    # le espressioni ${{ }} dentro «run:» finirebbero nel comando: segreto ed esito passano solo da env
    for blocco in re.findall(r"run: \|\n((?:\s{10,}.*\n?)+)", testo):
        assert "${{" not in blocco
    assert "echo \"$TOKEN\"" not in testo and "set -x" not in testo


def _cancello(esito: str, tmp_path: Path) -> tuple[int, str]:
    """Esegue il passo «Cancello» del workflow con l'esito dato. L'esito arriva come lo scrive l'azione: nel file
    dell'esecuzione (elenco di messaggi; l'ultimo di tipo «result» ha structured_output). Esito vuoto = nessun «result»;
    esito che non è JSON = file dell'esecuzione rovinato."""
    import os
    import subprocess
    import sys

    codice = re.search(r"<<'FINE'\n(.*?)\n\s*FINE\n", _testo(), re.S).group(1)
    codice = "\n".join(r[10:] if r.startswith(" " * 10) else r for r in codice.splitlines())
    riepilogo = tmp_path / "riepilogo.md"
    esecuzione = tmp_path / "claude-execution-output.json"
    messaggi = [{"type": "system", "subtype": "init"}]
    if not esito.strip():
        contenuto = json.dumps(messaggi)
    else:
        try:
            contenuto = json.dumps(messaggi + [{"type": "result", "structured_output": json.loads(esito)}])
        except ValueError:
            contenuto = esito
    esecuzione.write_text(contenuto, encoding="utf-8")
    ambiente = {k: v for k, v in os.environ.items() if k != "ESITO"}
    ambiente.update({"ESECUZIONE": str(esecuzione), "GITHUB_STEP_SUMMARY": str(riepilogo), "RUNNER_TEMP": str(tmp_path),
                     "COMMIT": "0123456789abcdef"})
    fatto = subprocess.run([sys.executable, "-I", "-s", "-c", codice], env=ambiente, capture_output=True, text=True)
    return fatto.returncode, fatto.stderr + fatto.stdout


def test_cancello(tmp_path):
    assert _cancello('{"bloccanti": 0, "sintesi": "Nessun problema trovato"}', tmp_path)[0] == 0
    assert "Nessun problema trovato" in (tmp_path / "riepilogo.md").read_text(encoding="utf-8")
    for esito in ("", "   ", "non json", '{"sintesi": "x"}', '{"bloccanti": "0", "sintesi": "x"}',
                  '{"bloccanti": true, "sintesi": "x"}', '{"bloccanti": -1, "sintesi": "x"}', "[]"):
        assert _cancello(esito, tmp_path)[0] != 0, esito
    codice, uscita = _cancello('{"bloccanti": 2, "sintesi": "due problemi, cc @qualcuno"}', tmp_path)
    assert codice != 0 and "2 problemi bloccanti" in uscita
    sintesi = (tmp_path / "sintesi.md").read_text(encoding="utf-8")
    assert sintesi.startswith("<!-- revisione-ia -->\n") and "0123456" in sintesi and "due problemi" in sintesi
    assert "@qualcuno" not in sintesi, "la sintesi non deve menzionare persone"


def test_la_sintesi_la_pubblica_il_job_anche_quando_il_cancello_e_rosso():
    testo = _testo()
    assert "Bash(gh pr comment" not in testo, "Claude non commenta da sé: lo fa il passo «Sintesi nella PR»"
    passo = testo[testo.index("- name: Sintesi nella PR"):]
    assert "!cancelled()" in passo and "<!-- revisione-ia -->" in passo and "PATCH" in passo


def test_senza_segreto_il_job_passa_senza_revisione():
    testo = _testo()
    assert "TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in testo
    passi = testo.split("      - ")[1:]
    assert "id: segreto" in passi[0]
    for passo in passi[1:]:
        assert "steps.segreto.outputs.presente == 'true'" in passo.split("run:")[0]


def test_la_skill_della_revisione_c_e_e_chiede_l_esito():
    testo = SKILL.read_text(encoding="utf-8")
    assert testo.startswith("---\nname: revisione-pr\n")
    for parola in ("bloccanti", "sintesi", "confirmed: true", "COERENZA-WEB-IPHONE.md", "STILE-SENZA-AI.md",
                   "docs/API.md", "docs/GUIDA-UTENTE.md", "non comanda"):
        assert parola in testo, parola
