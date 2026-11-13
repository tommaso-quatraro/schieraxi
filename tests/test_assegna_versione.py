"""script/ci/assegna_versione.py: il segno «urgente» nel commit di versione (#635) e le PR delle novità in attesa.

Il server installa le versioni nuove al massimo una volta ogni intervallo (script/server/aggiorna-app.sh), subito solo se fra i commit
nuovi c'è la riga «Rilascio: urgente». La scrive il job rilascia con `--commit --urgente` quando una delle PR delle novità in attesa,
o una issue che chiudono, ha l'etichetta P1 o urgente (`--pr-e-issue-in-attesa`, dal commit di unione).
Si prova lo script vero, come lo lancia il job, in un repository git in una cartella temporanea."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "script" / "ci" / "assegna_versione.py"


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                        "-c", "core.autocrlf=false", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _unisci(repo, titolo, nome=None, **file):
    """Un commit su main come quello del job unisci: titolo «Titolo della PR (#N)»; con `nome` aggiunge la sua novità in attesa."""
    if nome:
        file[f"fanta/novita.d/{nome}.json"] = json.dumps({"titolo": f"Novità {nome}", "voci": ["Una frase per l'utente."]})
    for rel, testo in file.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(testo, encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", titolo)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    # lo script fa il suo commit senza le opzioni di _git: sul runner di GitHub non c'è un'identità globale
    for chiave, valore in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(tmp_path, "config", chiave, valore)
    _unisci(tmp_path, "base", **{"fanta/novita.json": json.dumps([{"versione": "1.4", "data": "2026-11-01T10:00:00",
                                                                     "titolo": "Prima", "voci": ["x"]}]) + "\n"})
    return tmp_path


def _lancia(repo, *argomenti):
    return subprocess.run([sys.executable, "-I", "-s", str(SCRIPT), *argomenti], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def test_pr_e_issue_in_attesa_dal_commit_di_unione_senza_cambiare_niente(repo):
    """Le PR dal titolo «... (#N)» del commit di unione; le issue dalle righe di chiusura che il job unisci mette nel corpo (solo
    quelle che GitHub collega alla PR). Ognuna una volta sola, nell'ordine in cui sono entrate in main."""
    _unisci(repo, "Correzione dei voti (#12)\n\nCloses #600\nFixes #601\n\nCo-authored-by: Qualcuno <q@example.com>", "voti")
    _unisci(repo, "Solo documenti (#13)\n\nCloses #602", **{"docs/x.md": "doc"})  # nessuna novità: non conta
    _unisci(repo, "Titolo con (#3) in mezzo (#15)\n\nresolves #600\nVedi anche closes #603 nel testo", "titolo")
    _unisci(repo, "commit spinto senza numero", "senza-numero")
    r = _lancia(repo, "--pr-e-issue-in-attesa")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["pr 12", "issue 600", "issue 601", "pr 15"]
    assert _git(repo, "status", "--porcelain") == ""                             # niente versioni assegnate, nessun file tolto


@pytest.mark.parametrize("urgente", [True, False])
def test_commit_di_versione_con_la_riga_urgente_solo_se_chiesta(repo, urgente):
    _unisci(repo, "Correzione urgente (#20)", "correzione")
    r = _lancia(repo, "--commit", *(["--urgente"] if urgente else []))
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["1.5"]
    righe = _git(repo, "log", "-1", "--format=%B").splitlines()
    assert righe[0] == "Versione 1.5: Novità correzione"
    # aggiorna-app.sh cerca la riga intera, esatta (git log ... | grep -x): un titolo di PR che la contiene non basta
    assert ("Rilascio: urgente" in righe) is urgente


def _versione_sw(repo) -> str:
    return (repo / "fanta" / "web" / "sw.js").read_text(encoding="utf-8").splitlines()[0]


@pytest.mark.parametrize("toccato", ["fanta/web/app.js", "fanta/web/sw.js"])
def test_un_unione_che_tocca_la_web_alza_versione_del_service_worker(repo, toccato):
    """Il service worker dà la scocca dell'app dalla copia della sua VERSIONE (#654): se VERSIONE non sale, chi ha l'app
    installata resta alla web di prima. Ogni unione che tocca fanta/web/ (anche solo sw.js, senza alzarla) la porta a +1."""
    _unisci(repo, "Service worker", **{"fanta/web/sw.js": 'const VERSIONE = "fanta-41";\nconst FILE = ["/"];\n'})
    _unisci(repo, "Una schermata nuova (#30)", "schermata", **{toccato: 'const VERSIONE = "fanta-41";\n// cambiato\n'})
    r = _lancia(repo, "--commit")
    assert r.returncode == 0, r.stderr
    assert _versione_sw(repo) == 'const VERSIONE = "fanta-42";', _versione_sw(repo)
    assert "fanta/web/sw.js" in _git(repo, "show", "--name-only", "--format=", "HEAD").split()


def test_versione_del_service_worker_non_sale_due_volte_ne_senza_la_web(repo):
    """Una PR che ha già alzato VERSIONE da sé non la vede salire di nuovo; una PR senza file della web non la tocca."""
    _unisci(repo, "Service worker", **{"fanta/web/sw.js": 'const VERSIONE = "fanta-41";\n'})
    _unisci(repo, "Alzata a mano (#31)", "a-mano", **{"fanta/web/sw.js": 'const VERSIONE = "fanta-42";\n'})
    _unisci(repo, "Solo il server (#32)", "server", **{"fanta/x.py": "x = 1\n"})
    r = _lancia(repo, "--commit")
    assert r.returncode == 0, r.stderr
    assert _versione_sw(repo) == 'const VERSIONE = "fanta-42";', _versione_sw(repo)
