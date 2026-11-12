"""Il job «rilascia» di test.yml segna urgente il commit di versione (#635).

Il server installa le versioni nuove al massimo una volta all'ora (script/server/aggiorna-app.sh), subito solo se fra i commit nuovi
c'è la riga «Rilascio: urgente». Il passo che assegna il numero di versione la chiede ad assegna_versione.py quando una delle PR
delle novità in attesa, o una issue che quella PR chiude (le righe di chiusura che il job unisci mette nel commit di unione), ha
l'etichetta P1 o urgente: nella pratica P1 sta sulle issue. Tutte le PR in attesa, non solo quella della corsa, perché un «rilascia»
in attesa può essere scavalcato da quello della PR dopo, che dà il numero a tutte le novità. Etichette che non si leggono: un
avviso, il rilascio va avanti senza segno.
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

# gh finto: le etichette di una PR o di una issue da ETICHETTE_pr_<numero> o ETICHETTE_issue_<numero> (nessuna variabile = gh che
# non risponde), e per createCommitOnBranch l'oid del commit locale (come se GitHub l'avesse ricreato uguale). Chiamate in CHIAMATE.
GH_FINTO = r'''
gh() {
  printf '%s\n' "$*" >> "$CHIAMATE"
  case "$1 $2" in
    "pr view"|"issue view")
      local v="ETICHETTE_$1_$3"
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


def _unisci(repo, messaggio, nome):
    """Un'unione come quella del job unisci («Titolo (#N)», nel corpo le righe di chiusura) che porta la sua novità in attesa."""
    cartella = repo / "fanta" / "novita.d"                # nel «GitHub» finto, mai quella vera
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / f"{nome}.json").write_text(json.dumps({"titolo": f"Novità {nome}", "voci": ["Una frase."]}), encoding="utf-8",
                                           newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", messaggio)


def _rilascia(tmp_path, **etichette) -> tuple[str, dict, list[str]]:
    """Il passo vero, in un clone di un «GitHub» con due PR unite e le loro novità in attesa: la #12 chiude la issue 600, la #15
    le issue 600 e 601. `etichette`: pr_12=[...], issue_600=[...]. Restituisce l'uscita, il messaggio del commit che GitHub
    ricreerebbe e le chiamate a gh per leggere le etichette."""
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
    _unisci(origine, "Correzione dei voti (#12)\n\nCloses #600", "voti")
    _unisci(origine, "Correzione del widget (#15)\n\nCloses #600\nCloses #601", "widget")
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
    letture = [c for c in chiamate.read_text(encoding="utf-8").splitlines() if " view " in f" {c}"]
    return r.stdout + r.stderr, messaggio, letture


TUTTE_SENZA = {"pr_12": [], "pr_15": [], "issue_600": [], "issue_601": []}


@serve_bash
@pytest.mark.parametrize(("etichette", "urgente"), [
    ({**TUTTE_SENZA, "pr_15": ["ci", "P1"]}, True),                     # basta una PR in attesa con P1
    ({**TUTTE_SENZA, "pr_12": ["urgente"]}, True),
    ({**TUTTE_SENZA, "issue_601": ["server", "P1"]}, True),             # P1 sulla issue che la PR chiude: il caso di tutti i giorni
    ({**TUTTE_SENZA, "issue_600": ["urgente"]}, True),
    ({**TUTTE_SENZA, "pr_12": ["P1-dopo", "P2"], "issue_600": ["non-urgente"]}, False),     # solo l'etichetta intera
])
def test_versione_segnata_urgente_se_una_pr_in_attesa_o_una_sua_issue_ha_p1_o_urgente(tmp_path, etichette, urgente):
    testo, messaggio, letture = _rilascia(tmp_path, **etichette)
    assert messaggio["headline"] == "Versione 1.5, 1.6: Novità voti; Novità widget"
    assert (messaggio.get("body") == "Rilascio: urgente") is urgente, messaggio
    attese = ["pr view 12", "issue view 600", "pr view 15", "issue view 601"]          # la issue 600 si legge una volta sola
    assert letture == [f"{a} --repo esempio/repo --json labels --jq .labels[].name" for a in attese]


@serve_bash
def test_etichette_che_non_si_leggono_avvisano_e_il_rilascio_va_avanti(tmp_path):
    testo, messaggio, _ = _rilascia(tmp_path, pr_15=["P2"], issue_601=[])     # PR 12 e issue 600: gh non risponde
    assert "::warning title=Rilascio::non leggo le etichette di pr #12" in testo
    assert "::warning title=Rilascio::non leggo le etichette di issue #600" in testo
    assert messaggio == {"headline": "Versione 1.5, 1.6: Novità voti; Novità widget"}


def test_rilascia_legge_le_etichette_con_i_soli_permessi_in_lettura():
    assert _permessi(_job("rilascia")) == {"contents": "write", "actions": "write", "pull-requests": "read", "issues": "read"}
    assert "${{" not in _comandi(_passo_rilascia())        # numeri ed etichette passano per variabili, mai dentro il comando
