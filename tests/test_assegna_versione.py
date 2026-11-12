"""script/ci/assegna_versione.py: il segno «urgente» nel commit di versione (#635) e le PR delle novità in attesa.

Il server installa le versioni nuove al massimo una volta ogni intervallo (script/server/aggiorna-app.sh), subito solo se fra i commit
nuovi c'è la riga «Rilascio: urgente». La scrive il job rilascia con `--commit --urgente` quando una delle PR delle novità in attesa
(`--pr-in-attesa`, dal titolo «... (#N)» del commit di unione) ha l'etichetta P1 o urgente.
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
    _unisci(tmp_path, "base", **{"fanta/novita.json": json.dumps([{"versione": "1.4", "data": "2026-11-01T10:00:00",
                                                                     "titolo": "Prima", "voci": ["x"]}]) + "\n"})
    return tmp_path


def _lancia(repo, *argomenti):
    return subprocess.run([sys.executable, "-I", "-s", str(SCRIPT), *argomenti], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


def test_pr_in_attesa_dal_titolo_del_commit_di_unione_senza_cambiare_niente(repo):
    _unisci(repo, "Correzione dei voti (#12)", "voti")
    _unisci(repo, "Solo documenti (#13)", **{"docs/x.md": "doc"})                 # nessuna novità: non conta
    _unisci(repo, "Titolo con (#3) in mezzo (#15)", "titolo")
    _unisci(repo, "commit spinto senza numero", "senza-numero")
    r = _lancia(repo, "--pr-in-attesa")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["12", "15"]
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
