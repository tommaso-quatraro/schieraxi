"""Il job «unisci» di test.yml scrive titolo e corpo dell'unione (issue #620).

Prima GitHub metteva nel commit su main tutta la descrizione della PR (impostazione del repository), e un «Closes #N» citato
in mezzo al testo o in un piano finiva lì; il passo che chiude le issue chiudeva tutte quelle che GitHub collega alla PR.
Ora, letti subito prima dell'unione: titolo = titolo della PR con il numero; corpo = le righe di chiusura della descrizione
(a inizio riga, un numero per riga) delle sole issue che GitHub collega alla PR, poi le righe «Co-authored-by» dei commit.
Si chiudono solo le issue di quelle righe. I passi bash si provano davvero, con un `gh` finto."""
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
def test_titolo_e_descrizione_si_leggono_subito_prima_dell_unione():
    passo = _passo(UNIONE)
    assert "id: unione" in passo
    # non quelli dell'evento che ha fatto partire la corsa: la descrizione cambia anche dopo «gh pr ready»
    assert "github.event.pull_request.title" not in _unisci() and "github.event.pull_request.body" not in _unisci()
    comando = _comandi(passo)
    assert "${{" not in comando, "un'espressione dentro il comando"
    lettura = comando.index('gh pr view "$PR" --repo "$GITHUB_REPOSITORY" --json title,body,closingIssuesReferences')
    assert lettura < comando.index("gh pr merge")
    assert comando.splitlines()[0].startswith("dati=$(gh pr view")     # dentro un'assegnazione: se fallisce, il passo si ferma
    # resta tutto quello che c'era: squash, ramo cancellato, solo il commit che ha passato i test, questo repository
    for parte in ('gh pr merge "$PR" --squash --delete-branch --match-head-commit "$TESTA"', '--subject="$titolo (#$PR)"',
                  '--repo "$GITHUB_REPOSITORY"', "env.GITHUB_REPOSITORY"):
        assert parte in comando, parte


def test_la_chiusura_usa_le_righe_dell_unione_e_avvisa_con_warning():
    passo = _passo(CHIUSURA)
    assert "RIGHE: ${{ steps.unione.outputs.numeri }}" in passo
    assert "${{" not in _comandi(passo)
    assert "closingIssuesReferences" in passo and "gh issue close" in passo
    assert 'echo "::warning title=Chiusura delle issue::' in _comandi(passo)


# ---------------------------------------------------------------- bash vero, gh finto
def _trova_bash():
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
serve_bash = pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")

# Ogni chiamata a gh: gli argomenti separati da \x1f, una chiamata per voce di CHIAMATE (\x1e alla fine).
# «gh pr view» risponde come farebbe gh con il suo --jq: per la lettura prima dell'unione titolo, numeri delle issue
# collegate (una riga) e descrizione; per i commit i loro messaggi; per la chiusura i numeri collegati.
GH_FINTO = r'''
gh() {
  printf '%s\x1f' "$@" >> "$CHIAMATE"; printf '\x1e' >> "$CHIAMATE"
  case "$*" in
    "pr merge "*) return 0 ;;
    *"--json title,body,closingIssuesReferences"*)
      [ "${GH_LETTURA_ROTTA:-}" = 1 ] && { echo "HTTP 502" >&2; return 1; }
      printf '%s\n%s\n%s\n' "$TITOLO" "$COLLEGATE" "$CORPO" ;;
    *"--json commits"*)
      [ "${GH_COMMIT_ROTTI:-}" = 1 ] && { echo "HTTP 502" >&2; return 1; }
      printf '%s\n' "$MESSAGGI" ;;
    *"--json closingIssuesReferences"*) printf '%s\n' $COLLEGATE ;;
    "issue view "*) echo OPEN ;;
    "issue close "*) return 0 ;;
    *) echo "gh finto: chiamata inattesa $*" >&2; return 1 ;;
  esac
}
'''


def _esegui(tmp_path, passo: str, opzioni: str = "set -e", **env) -> tuple[list[list[str]], dict, str, int]:
    chiamate, uscita = tmp_path / "chiamate.txt", tmp_path / "output.txt"
    chiamate.write_text("", encoding="utf-8")
    uscita.write_text("", encoding="utf-8")
    prova = tmp_path / "passo.sh"
    prova.write_text(opzioni + "\n" + GH_FINTO + _comandi(_passo(passo)), encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", ""),
                "CHIAMATE": chiamate.as_posix(), "GITHUB_OUTPUT": uscita.as_posix(), "GITHUB_REPOSITORY": "esempio/repo",
                "GH_TOKEN": "finto", "PR": "12", "TESTA": "a" * 40, "TITOLO": "Titolo", "COLLEGATE": "", "CORPO": "",
                "MESSAGGI": ""}
    ambiente.update(env)
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente)
    fatte = [c.split("\x1f")[:-1] for c in chiamate.read_text(encoding="utf-8").split("\x1e") if c]
    usciti = dict(riga.split("=", 1) for riga in uscita.read_text(encoding="utf-8").splitlines() if "=" in riga)
    return fatte, usciti, r.stdout + r.stderr, r.returncode


def _unione(tmp_path, opzioni: str = "set -e", **env) -> tuple[list[str], dict, str]:
    fatte, usciti, testo, codice = _esegui(tmp_path, UNIONE, opzioni, **env)
    assert codice == 0, testo
    unioni = [c for c in fatte if c[:2] == ["pr", "merge"]]
    assert len(unioni) == 1, fatte
    return unioni[0], usciti, testo


def _corpo(argomenti: list[str]) -> str:
    [b] = [a for a in argomenti if a.startswith("--body=")]
    return b[len("--body="):]


CORPO_VERO = ("Aree: .github, tests\r\nCloses #619\r\n\r\n## Cosa cambia\r\n- Il piano diceva: Closes #7 (da non chiudere).\r\n"
              "- Nel commit c'era «fixes #8».\r\n\r\n## Come l'ho provato\r\n```\r\ngit commit -m \"x\"\r\n```\r\n")


@serve_bash
@pytest.mark.parametrize("opzioni", ["set -e", "set -eo pipefail"])        # come GitHub senza e con «shell: bash»
def test_unione_con_titolo_e_solo_le_righe_di_chiusura(tmp_path, opzioni):
    argomenti, usciti, testo = _unione(tmp_path, opzioni, TITOLO="Controlli: la web nel browser", CORPO=CORPO_VERO,
                                       COLLEGATE="619 7 8")
    assert argomenti == ["pr", "merge", "12", "--squash", "--delete-branch", "--match-head-commit", "a" * 40,
                         "--subject=Controlli: la web nel browser (#12)", "--body=Closes #619", "--repo", "esempio/repo"]
    assert usciti["numeri"].split() == ["619"]
    # le parole di chiusura che il filtro non prende si dicono con un avviso di GitHub, non con un echo qualsiasi
    assert "::warning title=Unione::#7 " in testo and "::warning title=Unione::#8 " in testo


@serve_bash
def test_la_descrizione_si_legge_adesso_e_se_non_si_legge_non_si_unisce(tmp_path):
    argomenti, _, _ = _unione(tmp_path, TITOLO="Titolo cambiato dopo la bozza", CORPO="Closes #5\n## Revisione\n- r: ok",
                              COLLEGATE="5")
    assert "--subject=Titolo cambiato dopo la bozza (#12)" in argomenti and _corpo(argomenti) == "Closes #5"
    fatte, usciti, testo, codice = _esegui(tmp_path, UNIONE, GH_LETTURA_ROTTA="1")
    assert codice != 0 and not [c for c in fatte if c[:2] == ["pr", "merge"]] and "numeri" not in usciti


@serve_bash
def test_senza_titolo_non_si_unisce(tmp_path):
    """gh esce con 0 ma senza titolo: niente unione con il titolo « (#12)», un errore di GitHub e il passo rosso."""
    fatte, usciti, testo, codice = _esegui(tmp_path, UNIONE, TITOLO="", CORPO="Closes #5", COLLEGATE="5")
    assert codice != 0 and not [c for c in fatte if c[:2] == ["pr", "merge"]] and "numeri" not in usciti
    assert "::error title=Unione::" in testo


def test_i_commit_letti_sono_al_massimo_100_ed_e_scritto():
    # gh pr view --json commits dà i primi 100 commit: oltre, le righe Co-authored-by dei successivi si perdono
    passo = _passo(UNIONE)
    commento = passo[:passo.index("if messaggi=$(gh pr view")].rstrip().splitlines()[-1]
    assert commento.strip().startswith("#") and "100" in commento and "Co-authored-by" in commento


@serve_bash
@pytest.mark.parametrize("corpo, collegate, atteso, numeri", [
    # le forme che GitHub collega e che compaiono nei modelli
    ("- Closes #1\n* Fixes #2\nCloses: #3\n**Closes #4**\n**Resolves** #5\n  resolved #6\n", "1 2 3 4 5 6",
     "Closes #1\nFixes #2\nCloses #3\nCloses #4\nResolves #5\nresolved #6", "1 2 3 4 5 6"),
    # un numero per riga, il primo: «non closes #13» resta fuori; doppioni una volta sola
    ("Closes #1 e anche Fixes #9\nCloses #1\nCLOSED #4 non closes #13\n", "1 4 9 13", "Closes #1\nCLOSED #4", "1 4"),
    ("Closes #\n\nAree: tests\n<!-- modello -->\n", "", "Senza issue collegata.", ""),     # la riga vuota del modello
    ("Parte di #167\nNon closes #9 qui\n", "9", "Senza issue collegata.", ""),
    ("", "", "Senza issue collegata.", ""),
])
def test_corpo_dell_unione(tmp_path, corpo, collegate, atteso, numeri):
    argomenti, usciti, _ = _unione(tmp_path, CORPO=corpo, COLLEGATE=collegate)
    assert _corpo(argomenti) == atteso
    assert usciti["numeri"].split() == numeri.split()


@serve_bash
def test_blocchi_di_codice_rientri_e_commenti_non_chiudono(tmp_path):
    """GitHub non collega un «Closes #N» dentro un blocco di codice o un commento HTML: resta fuori anche dal commit.
    Una riga rientrata di 4 spazi è un blocco di codice: non è nemmeno una riga di chiusura."""
    corpo = ("Closes #619\n\n```\nCloses #20\n```\n\n    Closes #21\n\n<!--\nCloses #22\n-->\n"
             "Closes #30\n")                                      # #30: issue di un altro repository, GitHub la scarta
    argomenti, usciti, testo = _unione(tmp_path, CORPO=corpo, COLLEGATE="619")
    assert _corpo(argomenti) == "Closes #619" and usciti["numeri"].split() == ["619"]
    for n in ("20", "22", "30"):
        assert f"::warning title=Unione::#{n} sta in una riga di chiusura ma GitHub non la collega" in testo
    assert "o non ancora collegata da GitHub: in quel caso chiudila a mano" in testo
    assert "::warning title=Unione::#21 compare con una parola di chiusura fuori da una riga" in testo


@serve_bash
def test_le_righe_co_authored_by_dei_commit_restano(tmp_path):
    messaggi = ("Primo passo\n\nCo-Authored-By: Persona Uno <uno@example.com>\n"
                "Secondo passo\r\n\r\nco-authored-by: persona uno <UNO@example.com>\r\n"
                "  Co-authored-by: Persona Due <due@example.com>  \nCo-authored-by:\n")
    argomenti, _, _ = _unione(tmp_path, CORPO="Closes #5", COLLEGATE="5", MESSAGGI=messaggi)
    assert _corpo(argomenti) == ("Closes #5\n\nCo-Authored-By: Persona Uno <uno@example.com>\n"
                                 "Co-authored-by: Persona Due <due@example.com>")
    argomenti, _, _ = _unione(tmp_path, CORPO="", MESSAGGI="Co-authored-by: Persona Uno <uno@example.com>")
    assert _corpo(argomenti) == "Senza issue collegata.\n\nCo-authored-by: Persona Uno <uno@example.com>"


@serve_bash
def test_senza_i_commit_si_unisce_lo_stesso_con_un_avviso(tmp_path):
    argomenti, _, testo = _unione(tmp_path, CORPO="Closes #5", COLLEGATE="5", GH_COMMIT_ROTTI="1")
    assert _corpo(argomenti) == "Closes #5"
    assert "::warning title=Unione::non riesco a leggere i commit della PR" in testo


@serve_bash
def test_il_titolo_passa_com_e_senza_diventare_un_comando(tmp_path):
    titolo = 'Testi "tra virgolette" $(echo rotto) `echo rotto` -x; exit 3'
    argomenti, _, _ = _unione(tmp_path, TITOLO=titolo, CORPO="Closes #5", COLLEGATE="5")
    assert f"--subject={titolo} (#12)" in argomenti


@serve_bash
def test_si_chiudono_solo_le_issue_delle_righe_di_chiusura(tmp_path):
    fatte, _, testo, codice = _esegui(tmp_path, CHIUSURA, RIGHE="619", COLLEGATE="619 7")
    assert codice == 0, testo
    assert [c[2] for c in fatte if c[:2] == ["issue", "close"]] == ["619"]
    assert "::warning title=Chiusura delle issue::#7 " in testo           # si dice perché resta aperta
    fatte, _, _, _ = _esegui(tmp_path, CHIUSURA, RIGHE="", COLLEGATE="619")
    assert not [c for c in fatte if c[:2] == ["issue", "close"]]
