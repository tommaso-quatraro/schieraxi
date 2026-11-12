"""Il job «rilascia» di test.yml segna urgente il commit di versione (#635).

Il server installa le versioni nuove al massimo una volta all'ora (script/server/aggiorna-app.sh), subito solo se fra i commit nuovi
c'è la riga «Rilascio: urgente». Il passo che assegna il numero di versione la chiede ad assegna_versione.py quando una delle PR
delle novità in attesa ha l'etichetta P1 o urgente: tutte le PR in attesa, non solo quella della corsa, perché un «rilascia» in
attesa può essere scavalcato da quello della PR dopo, che dà il numero a tutte le novità. Etichette che non si leggono: un avviso,
il rilascio va avanti senza segno.
Il passo bash si prova davvero: script veri di script/ci, un «GitHub» in una cartella temporanea e un `gh` finto."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_workflow_main import _job, _permessi
from test_workflow_unisci import BASH, _comandi, serve_bash

RADICE = Path(__file__).resolve().parent.parent
PASSO = "Numero di versione alle novità in attesa"

# gh finto: le etichette delle PR da ETICHETTE_<numero> (nessuna variabile = gh che non risponde), e per createCommitOnBranch
# l'oid del commit locale (come se GitHub l'avesse ricreato uguale). Le chiamate si annotano in CHIAMATE.
GH_FINTO = r'''
gh() {
  printf '%s\n' "$*" >> "$CHIAMATE"
  case "$1 $2" in
    "pr view")
      local v="ETICHETTE_$3"
      [ -n "${!v+x}" ] || { echo "HTTP 502" >&2; return 1; }
      printf '%s\n' ${!v} ;;
    "api graphql") git rev-parse HEAD ;;
    *) echo "gh finto: chiamata inattesa $*" >&2; return 1 ;;
  esac
}
python3() { "$PYTHON_VERO" "$@"; }
'''


def _passo_rilascia() -> str:
    blocco = _job("rilascia")
    inizio = blocco.index(f"- name: {PASSO}")
    fine = blocco.find("\n      - name:", inizio + 1)
    return blocco[inizio:fine if fine != -1 else len(blocco)]


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                        "-c", "core.autocrlf=false", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _unisci(repo, titolo, nome):
    """Un'unione come quella del job unisci («Titolo (#N)») che porta la sua novità in attesa."""
    f = repo / "fanta" / "novita.d" / f"{nome}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"titolo": f"Novità {nome}", "voci": ["Una frase."]}), encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", titolo)


def _rilascia(tmp_path, **etichette) -> tuple[str, dict, list[str]]:
    """Il passo vero, in un clone di un «GitHub» con due PR unite (#12 e #15) e le loro novità in attesa.
    Restituisce l'uscita, il messaggio del commit che GitHub ricreerebbe e le chiamate a gh."""
    origine, clone = tmp_path / "github", tmp_path / "clone"
    origine.mkdir()
    _git(origine, "init", "-q", "-b", "main")
    for nome in ("assegna_versione.py", "commit_firmato.py"):
        (origine / "script" / "ci").mkdir(parents=True, exist_ok=True)
        (origine / "script" / "ci" / nome).write_bytes((RADICE / "script" / "ci" / nome).read_bytes())
    (origine / "fanta").mkdir()
    (origine / "fanta" / "novita.json").write_text('[{"versione": "1.4", "data": "2026-11-01T10:00:00", "titolo": "x", '
                                                   '"voci": ["y"]}]\n', encoding="utf-8", newline="\n")
    _git(origine, "add", "-A")
    _git(origine, "commit", "-q", "-m", "base")
    _unisci(origine, "Correzione dei voti (#12)", "voti")
    _unisci(origine, "Correzione del widget (#15)", "widget")
    _git(tmp_path, "clone", "-q", origine.as_posix(), clone.as_posix())
    chiamate = tmp_path / "chiamate.txt"
    prova = tmp_path / "passo.sh"
    prova.write_text("set -e\n" + GH_FINTO + _comandi(_passo_rilascia()), encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", ""),
                "CHIAMATE": chiamate.as_posix(), "GITHUB_REPOSITORY": "esempio/repo", "GH_TOKEN": "finto",
                "PYTHON_VERO": Path(sys.executable).as_posix(),
                **{f"ETICHETTE_{n}": " ".join(v) for n, v in etichette.items()}}
    r = subprocess.run([BASH, prova.as_posix()], cwd=clone, capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env=ambiente)
    assert r.returncode == 0, r.stdout + r.stderr
    messaggio = json.loads((clone / "corpo.json").read_text(encoding="utf-8"))["variables"]["input"]["message"]
    return r.stdout + r.stderr, messaggio, chiamate.read_text(encoding="utf-8").splitlines()


@serve_bash
@pytest.mark.parametrize(("etichette", "urgente"), [
    ({"12": ["server", "P2"], "15": ["ci", "P1"]}, True),              # basta una PR in attesa con P1
    ({"12": ["urgente"], "15": []}, True),
    ({"12": ["P1-dopo", "P2"], "15": ["non-urgente"]}, False),          # solo l'etichetta intera
])
def test_versione_segnata_urgente_se_una_pr_in_attesa_ha_p1_o_urgente(tmp_path, etichette, urgente):
    testo, messaggio, chiamate = _rilascia(tmp_path, **etichette)
    assert messaggio["headline"] == "Versione 1.5, 1.6: Novità voti; Novità widget"
    assert (messaggio.get("body") == "Rilascio: urgente") is urgente, messaggio
    assert [c for c in chiamate if c.startswith("pr view")] == [
        "pr view 12 --repo esempio/repo --json labels --jq .labels[].name",
        "pr view 15 --repo esempio/repo --json labels --jq .labels[].name"]


@serve_bash
def test_etichette_che_non_si_leggono_avvisano_e_il_rilascio_va_avanti(tmp_path):
    testo, messaggio, _ = _rilascia(tmp_path, **{"15": ["P2"]})            # la PR 12: gh non risponde
    assert "::warning title=Rilascio::non leggo le etichette della PR #12" in testo
    assert messaggio == {"headline": "Versione 1.5, 1.6: Novità voti; Novità widget"}


def test_rilascia_legge_le_etichette_con_il_solo_permesso_in_lettura():
    assert _permessi(_job("rilascia")) == {"contents": "write", "actions": "write", "pull-requests": "read"}
    assert "${{" not in _comandi(_passo_rilascia())        # numeri ed etichette passano per variabili, mai dentro il comando
