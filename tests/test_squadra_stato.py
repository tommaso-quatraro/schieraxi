"""script/squadra: `stato` (PR, tetti, corse sui Mac, obiettivi, worktree) e la lettura delle worktree, con risposte finte."""
from __future__ import annotations

import json

from test_squadra_comune import Finto, Sequenza

import comune
import stato
import worktree

ADESSO = comune.data("2026-11-06T12:00:00Z")
WT = "C:/repo/.claude/worktrees"

PORCELAIN = f"""worktree C:/repo
HEAD aaa
branch refs/heads/main

worktree {WT}/agent-1
HEAD h1
branch refs/heads/unito-pulito

worktree {WT}/agent-2
HEAD h2
branch refs/heads/unito-sporco

worktree {WT}/agent-3
HEAD h3
branch refs/heads/senza-pr

worktree {WT}/agent-4
HEAD h4
branch refs/heads/vivo
locked claude agent agent-4 (pid 1)

worktree {WT}/agent-5
HEAD h5
detached

worktree {WT}/agent-6
HEAD h6
branch refs/heads/aperta

worktree {WT}/agent-7
HEAD h7
branch refs/heads/unito-poi-altri-commit
"""

PR_TUTTE = [
    {"number": 10, "state": "MERGED", "headRefName": "unito-pulito", "headRefOid": "h1"},
    {"number": 11, "state": "MERGED", "headRefName": "unito-sporco", "headRefOid": "h2"},
    {"number": 12, "state": "OPEN", "headRefName": "aperta", "headRefOid": "h6"},
    {"number": 9, "state": "CLOSED", "headRefName": "aperta", "headRefOid": "vecchio"},
    {"number": 13, "state": "MERGED", "headRefName": "unito-poi-altri-commit", "headRefOid": "prima"},
]


def risposte_worktree():
    r = {
        "git worktree list --porcelain": PORCELAIN,
        "gh pr list --state all": PR_TUTTE,
        "git merge-base --is-ancestor": comune.Risposta(1, "", ""),     # nessuna testa già in main...
        "git merge-base --is-ancestor h5 origin/main": comune.Risposta(0, "", ""),   # ...tranne la staccata
    }
    for i in range(1, 8):
        r[f"git -C {WT}/agent-{i} status --porcelain"] = " M fanta/x.py\n" if i == 2 else ""
    return r


def test_worktree_classificate_nei_gruppi():
    voci = {v["percorso"].rsplit("/", 1)[1]: v for v in worktree.raccogli(Finto(risposte_worktree()))}
    assert set(voci) == {f"agent-{i}" for i in range(1, 8)}        # la cartella principale non c'è
    assert voci["agent-1"]["gruppo"] == "da_togliere"
    assert voci["agent-2"]["gruppo"] == "con_modifiche"
    assert voci["agent-3"]["gruppo"] == "senza_pr"
    assert voci["agent-4"]["gruppo"] == "bloccata"
    assert voci["agent-5"]["gruppo"] == "da_togliere" and voci["agent-5"]["ramo"] is None
    assert voci["agent-6"]["gruppo"] == "in_corso" and voci["agent-6"]["pr"] == 12
    assert voci["agent-7"]["gruppo"] == "con_modifiche"            # commit dopo l'unione: non si perde nulla
    assert voci["agent-1"]["unito"] and not voci["agent-3"]["unito"]


def test_bloccata_non_si_guarda_neppure_dentro():
    finto = Finto(risposte_worktree())
    worktree.raccogli(finto)
    assert not finto.lanciati(f"git -C {WT}/agent-4")


def _check(stato_, conclusione=""):
    return {"__typename": "CheckRun", "status": stato_, "conclusion": conclusione, "name": "x", "workflowName": "Controlli"}


def test_riassunto_dei_controlli():
    assert stato.controlli([]) == "nessuno"
    assert stato.controlli([_check("COMPLETED", "SUCCESS"), _check("COMPLETED", "SKIPPED")]) == "verde"
    assert stato.controlli([_check("COMPLETED", "SUCCESS"), _check("IN_PROGRESS")]) == "in corso"
    assert stato.controlli([_check("COMPLETED", "FAILURE"), _check("QUEUED")]) == "in corso"
    assert stato.controlli([_check("COMPLETED", "FAILURE"), _check("COMPLETED", "SUCCESS")]) == "rosso"
    assert stato.controlli([_check("COMPLETED", "CANCELLED"), _check("COMPLETED", "SUCCESS")]) == "annullato"
    assert stato.controlli([{"__typename": "StatusContext", "state": "PENDING"}]) == "in corso"
    assert stato.controlli([{"__typename": "StatusContext", "state": "ERROR"}]) == "rosso"


def risposte_stato():
    r = risposte_worktree()
    r.update({
        "gh pr list --state open": [
            {"number": 20, "title": "Web: una cosa", "isDraft": False, "mergeable": "MERGEABLE", "headRefName": "a",
             "createdAt": "2026-11-06T09:00:00Z", "files": [{"path": "fanta/web/app.js"}],
             "statusCheckRollup": [_check("COMPLETED", "SUCCESS")]},
            {"number": 21, "title": "iPhone e web", "isDraft": True, "mergeable": "CONFLICTING", "headRefName": "b",
             "createdAt": "2026-11-04T09:00:00Z", "files": [{"path": "ios/Sources/A.swift"}, {"path": "fanta/web/app.js"}],
             "statusCheckRollup": [_check("COMPLETED", "FAILURE")]},
            {"number": 22, "title": "Documenti", "isDraft": False, "mergeable": "UNKNOWN", "headRefName": "c",
             "createdAt": "2026-11-06T11:50:00Z", "files": [{"path": "docs/A.md"}], "statusCheckRollup": []},
        ],
        "gh run list --status in_progress": [
            {"databaseId": 1, "workflowName": "Screenshot", "status": "in_progress", "event": "workflow_dispatch",
             "headBranch": "main", "createdAt": "2026-11-06T11:00:00Z"},
            {"databaseId": 2, "workflowName": "Controlli", "status": "in_progress", "event": "pull_request",
             "headBranch": "a", "createdAt": "2026-11-06T11:00:00Z"},
        ],
        "gh run list --status queued": [
            {"databaseId": 3, "workflowName": "iOS", "status": "queued", "event": "pull_request",
             "headBranch": "b", "createdAt": "2026-11-06T11:30:00Z"},
        ],
        "gh issue list --label obiettivo": [{"number": 165, "title": "Statistiche"}, {"number": 167, "title": "App semplice"}],
        "gh api repos/{owner}/{repo}/issues/165/sub_issues": [{"number": 1, "state": "open"}, {"number": 2, "state": "closed"}],
        "gh api repos/{owner}/{repo}/issues/167/sub_issues": [],
    })
    return r


def test_stato_raccoglie_tutto():
    s = stato.raccogli(Finto(risposte_stato()), adesso=ADESSO)
    prs = {p["numero"]: p for p in s["pr"]}
    assert prs[20]["gruppo"] == "server-web" and prs[20]["controlli"] == "verde" and prs[20]["eta"] == "3 h"
    assert prs[21]["gruppo"] == "ios" and prs[21]["mergeable"] == "CONFLICTING" and prs[21]["bozza"]
    assert prs[22]["gruppo"] is None
    assert s["tetti"] == {"server-web": {"aperte": 1, "tetto": 4}, "ios": {"aperte": 1, "tetto": 3}}
    assert [c["id"] for c in s["mac"]] == [1, 3]             # «Controlli» non è nell'elenco dei workflow sui Mac
    assert s["obiettivi"] == [{"numero": 165, "titolo": "Statistiche", "aperte": 1, "totali": 2},
                              {"numero": 167, "titolo": "App semplice", "aperte": 0, "totali": 0}]
    assert len(s["worktree"]) == 7


def test_stato_testo_e_json(capsys):
    finto = Finto(risposte_stato())
    assert stato.main(finto, json_=False, adesso=ADESSO) == 0
    testo = capsys.readouterr().out
    assert "#21" in testo and "CONFLITTO" in testo and "server-web 1/4" in testo and "ios 1/3" in testo
    assert stato.main(finto, json_=True, adesso=ADESSO) == 0
    dati = json.loads(capsys.readouterr().out)
    assert {p["numero"] for p in dati["pr"]} == {20, 21, 22}


def test_stato_con_gh_rotto_esce_con_1(capsys):
    r = risposte_stato()
    r["gh pr list --state open"] = comune.Risposta(1, "", "gh: non autenticato")
    assert stato.main(Finto(r), json_=False, adesso=ADESSO) == 1
    assert "non autenticato" in capsys.readouterr().err


def test_sequenza_del_finto():
    s = Sequenza("a", "b")
    assert [s.prossima(), s.prossima(), s.prossima()] == ["a", "b", "b"]
