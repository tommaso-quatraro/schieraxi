"""Il job «unisci» di test.yml scrive titolo e corpo dell'unione (issue #620).

Prima GitHub metteva nel commit su main tutta la descrizione della PR (impostazione del repository), e un «Closes #N» citato
in mezzo al testo o in un piano finiva lì; il passo che chiude le issue chiudeva tutte quelle che GitHub collega alla PR.
Ora: titolo = titolo della PR con il numero, corpo = le sole righe «Closes #N» della descrizione (anche Fixes e Resolves, a
inizio riga), e si chiudono solo le issue di quelle righe. I passi bash si provano davvero, con un `gh` finto."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
TEST_YML = RADICE / ".github" / "workflows" / "test.yml"


def _unisci() -> str:
    testo = TEST_YML.read_text(encoding="utf-8")
    return testo[testo.index("\n  unisci:\n"):testo.index("\n  rilascia:\n")]


def _passo(nome: str) -> str:
    blocco = _unisci()
    inizio = blocco.index(f"- name: {nome}")
    fine = blocco.find("\n      - name:", inizio + 1)
    return blocco[inizio:fine if fine != -1 else len(blocco)]


def _comandi(passo: str) -> str:
    """Il testo di «run: |» senza il rientro e senza le righe di commento."""
    m = re.search(r"^(\s+)run: \|\s*\n", passo, re.M)
    assert m, "il passo non ha «run: |»"
    rientro = len(m.group(1)) + 2
    righe = []
    for riga in passo[m.end():].splitlines():
        if riga.strip() and len(riga) - len(riga.lstrip()) < rientro:
            break
        righe.append(riga[rientro:])
    return "\n".join(righe) + "\n"


UNIONE = "Unisci la PR (solo il commit che ha passato i test)"
CHIUSURA = "Chiudi le issue collegate alla PR"


# ---------------------------------------------------------------- com'è scritto il job
def test_titolo_e_corpo_arrivano_solo_come_variabili_d_ambiente():
    passo = _passo(UNIONE)
    assert "id: unione" in passo
    assert "TITOLO: ${{ github.event.pull_request.title }}" in passo
    assert "CORPO: ${{ github.event.pull_request.body }}" in passo
    assert "${{" not in _comandi(passo), "un'espressione dentro il comando"
    comando = _comandi(passo)
    # resta tutto quello che c'era: squash, ramo cancellato, solo il commit che ha passato i test, questo repository
    for parte in ('gh pr merge "$PR" --squash --delete-branch --match-head-commit "$TESTA"', '--subject="$TITOLO (#$PR)"',
                  '--repo "$GITHUB_REPOSITORY"'):
        assert parte in comando, parte


def test_la_chiusura_usa_le_righe_closes_dell_unione():
    passo = _passo(CHIUSURA)
    assert "RIGHE: ${{ steps.unione.outputs.numeri }}" in passo
    assert "${{" not in _comandi(passo)
    assert "closingIssuesReferences" in passo and "gh issue close" in passo


# ---------------------------------------------------------------- bash vero, gh finto
def _trova_bash():
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
serve_bash = pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")

# ogni chiamata a gh: gli argomenti separati da \x1f, una chiamata per riga di CHIAMATE (\x1e alla fine)
GH_FINTO = r'''
gh() {
  printf '%s\x1f' "$@" >> "$CHIAMATE"; printf '\x1e' >> "$CHIAMATE"
  case "$*" in
    "pr merge "*) return 0 ;;
    *closingIssuesReferences*) printf '%s\n' $COLLEGATE ;;
    "issue view "*) echo OPEN ;;
    "issue close "*) return 0 ;;
    *) echo "gh finto: chiamata inattesa $*" >&2; return 1 ;;
  esac
}
'''


def _esegui(tmp_path, passo: str, opzioni: str = "set -e", **env) -> tuple[list[list[str]], dict, str]:
    chiamate, uscita = tmp_path / "chiamate.txt", tmp_path / "output.txt"
    chiamate.write_text("", encoding="utf-8")
    uscita.write_text("", encoding="utf-8")
    prova = tmp_path / "passo.sh"
    prova.write_text(opzioni + "\n" + GH_FINTO + _comandi(_passo(passo)), encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", ""),
                "CHIAMATE": chiamate.as_posix(), "GITHUB_OUTPUT": uscita.as_posix(), "GITHUB_REPOSITORY": "esempio/repo",
                "GH_TOKEN": "finto", "PR": "12", "TESTA": "a" * 40}
    ambiente.update(env)
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente)
    assert r.returncode == 0, r.stdout + r.stderr
    fatte = [c.split("\x1f")[:-1] for c in chiamate.read_text(encoding="utf-8").split("\x1e") if c]
    usciti = dict(riga.split("=", 1) for riga in uscita.read_text(encoding="utf-8").splitlines() if "=" in riga)
    return fatte, usciti, r.stdout


def _unione(tmp_path, titolo: str, corpo: str, opzioni: str = "set -e") -> tuple[list[str], dict]:
    fatte, usciti, _ = _esegui(tmp_path, UNIONE, opzioni, TITOLO=titolo, CORPO=corpo)
    assert len(fatte) == 1 and fatte[0][:2] == ["pr", "merge"]
    return fatte[0], usciti


CORPO_VERO = ("Aree: .github, tests\r\nCloses #619\r\n\r\n## Cosa cambia\r\n- Il piano diceva: Closes #7 (da non chiudere).\r\n"
              "- Nel commit c'era «fixes #8».\r\n\r\n## Come l'ho provato\r\n```\r\ngit commit -m \"x\"\r\n```\r\n")


@serve_bash
@pytest.mark.parametrize("opzioni", ["set -e", "set -eo pipefail"])        # come GitHub senza e con «shell: bash»
def test_unione_con_titolo_e_solo_le_righe_closes(tmp_path, opzioni):
    argomenti, usciti = _unione(tmp_path, "Controlli: la web nel browser", CORPO_VERO, opzioni)
    assert argomenti == ["pr", "merge", "12", "--squash", "--delete-branch", "--match-head-commit", "a" * 40,
                         "--subject=Controlli: la web nel browser (#12)", "--body=Closes #619", "--repo", "esempio/repo"]
    assert usciti["numeri"].split() == ["619"]


@serve_bash
@pytest.mark.parametrize("corpo, atteso, numeri", [
    ("Closes #1\nFixes #2\n  resolves #3\nCloses #1\nCLOSED #4 e #5\n", "Closes #1\nFixes #2\nresolves #3\nCLOSED #4", "1 2 3 4"),
    ("Closes #\n\nAree: tests\n<!-- modello -->\n", "Senza issue collegata.", ""),     # la riga vuota del modello
    ("Parte di #167\nNon closes #9 qui\n", "Senza issue collegata.", ""),
    ("", "Senza issue collegata.", ""),
])
def test_corpo_dell_unione(tmp_path, corpo, atteso, numeri):
    argomenti, usciti = _unione(tmp_path, "Titolo", corpo)
    assert argomenti[argomenti.index("--subject=Titolo (#12)") + 1] == f"--body={atteso}"
    assert usciti["numeri"].split() == numeri.split()


@serve_bash
def test_il_titolo_passa_com_e_senza_diventare_un_comando(tmp_path):
    titolo = 'Testi "tra virgolette" $(echo rotto) `echo rotto` -x; exit 3'
    argomenti, _ = _unione(tmp_path, titolo, "Closes #5")
    assert f"--subject={titolo} (#12)" in argomenti


@serve_bash
def test_si_chiudono_solo_le_issue_delle_righe_closes(tmp_path):
    fatte, _, testo = _esegui(tmp_path, CHIUSURA, RIGHE="619 ", COLLEGATE="619 7")
    chiuse = [c[2] for c in fatte if c[:2] == ["issue", "close"]]
    assert chiuse == ["619"]
    assert "#7" in testo                                       # si dice perché resta aperta
    fatte, _, _ = _esegui(tmp_path, CHIUSURA, RIGHE="", COLLEGATE="619")
    assert not [c for c in fatte if c[:2] == ["issue", "close"]]
