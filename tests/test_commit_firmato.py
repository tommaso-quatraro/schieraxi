"""script/ci/commit_firmato.py: la richiesta che fa ricreare a GitHub (firmato) il commit di versione del job rilascia."""
import base64
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("commit_firmato", RADICE / "script" / "ci" / "commit_firmato.py")
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                        "-c", "core.autocrlf=false", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "fanta" / "novita.d").mkdir(parents=True)
    (tmp_path / "fanta" / "novita.json").write_bytes(b'[{"versione": "1.1"}]\n')
    (tmp_path / "fanta" / "novita.d" / "cosa-nuova.json").write_bytes(b'{"titolo": "x"}\n')
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_ricrea_modifiche_aggiunte_e_cancellazioni_con_il_messaggio(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "fanta" / "novita.json").write_bytes('[{"versione": "1.2", "voci": ["perché"]}]\n'.encode())
    (repo / "fanta" / "web").mkdir()
    (repo / "fanta" / "web" / "sw.js").write_bytes(b"const VERSIONE = 2;\n")
    _git(repo, "rm", "-q", "fanta/novita.d/cosa-nuova.json")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Versione 1.2: cosa nuova\n\naltre righe")
    c = cf.corpo(base, "HEAD", "proprietario/repo")
    inp = c["variables"]["input"]
    assert "createCommitOnBranch" in c["query"]
    assert inp["branch"] == {"repositoryNameWithOwner": "proprietario/repo", "branchName": "main"}
    assert inp["expectedHeadOid"] == base                       # se main e' cambiato nel frattempo GitHub rifiuta
    assert inp["message"] == {"headline": "Versione 1.2: cosa nuova", "body": "altre righe"}
    aggiunte = {a["path"]: base64.b64decode(a["contents"]) for a in inp["fileChanges"]["additions"]}
    assert aggiunte == {"fanta/novita.json": '[{"versione": "1.2", "voci": ["perché"]}]\n'.encode(),
                        "fanta/web/sw.js": b"const VERSIONE = 2;\n"}
    assert inp["fileChanges"]["deletions"] == [{"path": "fanta/novita.d/cosa-nuova.json"}]
    json.dumps(c)                                               # si scrive in JSON senza problemi


def test_uscita_sempre_json_valido_anche_con_terminale_latin1(repo):
    # Un runner con l'uscita in latin-1: con «più» nel messaggio il corpo usciva in latin-1 (non UTF-8)
    # e GitHub rispondeva «Problems parsing JSON (HTTP 400)» a ogni tentativo (job rilascia, novembre 2026).
    import os
    import sys
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "fanta" / "novita.json").write_bytes('[{"versione": "1.2", "titolo": "Novità più sicure"}]\n'.encode())
    _git(repo, "rm", "-q", "fanta/novita.d/cosa-nuova.json")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Versione 1.2: novità più sicure\n\nperché sì")
    env = {**os.environ, "PYTHONIOENCODING": "latin-1", "GITHUB_REPOSITORY": "p/r"}
    r = subprocess.run([sys.executable, "-s", str(RADICE / "script" / "ci" / "commit_firmato.py"), base, "HEAD"],
                       cwd=repo, env=env, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout.decode("utf-8"))                   # GitHub vuole UTF-8: qui falliva
    assert c["variables"]["input"]["message"] == {"headline": "Versione 1.2: novità più sicure", "body": "perché sì"}
    assert r.stdout.isascii()                                  # solo ASCII: va bene con qualunque codifica del terminale


def test_rifiuta_piu_di_un_commit_sopra_la_base(repo):
    base = _git(repo, "rev-parse", "HEAD")
    for i in (1, 2):
        (repo / f"f{i}.txt").write_bytes(b"x")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", f"c{i}")
    with pytest.raises(SystemExit, match="UNO solo"):
        cf.corpo(base, "HEAD", "p/r")


def test_main_senza_repository_si_ferma(repo, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(SystemExit, match="manca il repository"):
        cf.main(["HEAD~0", "HEAD"])
