"""script/squadra: `pulisci` elenca le worktree in gruppi e con --esegui toglie solo quelle unite e pulite."""
from __future__ import annotations

import json

from test_squadra_comune import Finto
from test_squadra_stato import WT, risposte_worktree

import comune
import pulisci


def finto(**extra):
    r = risposte_worktree()
    r.update({"git worktree remove": "", "git branch -d": "", "git branch -D": "", "git for-each-ref": "",
              "git rev-parse --abbrev-ref HEAD": "main\n"})
    r.update(extra)
    return Finto(r)


def test_prova_non_toglie_niente(capsys):
    f = finto()
    assert pulisci.main(f) == 0
    assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    testo = capsys.readouterr().out
    assert "Da togliere (2)" in testo and "Con modifiche (2)" in testo and "Senza PR (1)" in testo
    assert "PROVA" in testo and "--esegui" in testo


def test_esegui_toglie_solo_le_unite_e_pulite():
    f = finto()
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert f.lanciati("git worktree remove") == [f"git worktree remove {WT}/agent-1", f"git worktree remove {WT}/agent-5"]
    # mai --force; il ramo unito con la stessa testa della PR si toglie con -D (unione squash), la staccata non ha ramo
    assert not [c for c in f.chiamate if "--force" in c]
    assert f.lanciati("git branch") == ["git branch -D unito-pulito"]


def test_ramo_gia_in_main_si_toglie_con_d_minuscola():
    f = finto(**{"git merge-base --is-ancestor h3 origin/main": comune.Risposta(0, "", "")})
    pulisci.main(f, esegui_davvero=True)
    assert "git branch -d senza-pr" in f.lanciati("git branch")


def test_bloccate_e_con_modifiche_non_si_toccano_mai():
    f = finto()
    pulisci.main(f, esegui_davvero=True)
    tolte = " ".join(f.lanciati("git worktree remove"))
    for n in (2, 3, 4, 6, 7):
        assert f"agent-{n}" not in tolte


def test_rimozione_rifiutata_esce_con_1_e_non_tocca_il_ramo(capsys):
    f = finto(**{f"git worktree remove {WT}/agent-1": comune.Risposta(128, "", "contains modified or untracked files")})
    assert pulisci.main(f, esegui_davvero=True) == 1
    assert "git branch -D unito-pulito" not in f.lanciati("git branch")
    assert "untracked" in capsys.readouterr().err


def test_json(capsys):
    pulisci.main(finto(), json_=True)
    dati = json.loads(capsys.readouterr().out)
    assert dati["prova"] is True
    assert sorted(w["percorso"].rsplit("/", 1)[1] for w in dati["gruppi"]["da_togliere"]) == ["agent-1", "agent-5"]


def test_cartelle_sparite_suggeriscono_prune(capsys):
    porcelain = f"worktree {WT}/agent-9\nHEAD h9\nbranch refs/heads/sparita\nprunable gitdir file points to non-existent location\n"
    f = Finto({"git worktree list --porcelain": porcelain, "gh pr list --state all": [], "git for-each-ref": "",
               "git rev-parse --abbrev-ref HEAD": "main\n"})
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert "git worktree prune" in capsys.readouterr().out
    assert not f.lanciati("git worktree remove")


# #476 punto 1: PR portata in pari con main da GitHub («Update branch»): la sua testa non è quella locale.
def _aggiornata(stato_compare):
    porcelain = f"worktree C:/repo\nHEAD aaa\nbranch refs/heads/main\n\nworktree {WT}/agent-8\nHEAD h8\nbranch refs/heads/aggiornato\n"
    return Finto({
        "git worktree list --porcelain": porcelain,
        "gh pr list --state all": [{"number": 469, "state": "MERGED", "headRefName": "aggiornato", "headRefOid": "su-github"}],
        "git -C C:/repo/.claude/worktrees/agent-8 status --porcelain": "",
        "git merge-base --is-ancestor": comune.Risposta(1, "", ""),
        "gh api repos/{owner}/{repo}/compare/su-github...h8": stato_compare,
        "git for-each-ref": "", "git rev-parse --abbrev-ref HEAD": "main\n",
        "git worktree remove": "", "git branch -D": "", "git branch -d": "",
    })


def test_worktree_con_pr_aggiornata_da_github_risulta_unita():
    for stato_compare in ("behind\n", "identical\n"):
        f = _aggiornata(stato_compare)
        assert pulisci.main(f, esegui_davvero=True) == 0
        assert f.lanciati("git worktree remove") == [f"git worktree remove {WT}/agent-8"]
        assert f.lanciati("git branch") == ["git branch -D aggiornato"]     # unione squash: serve -D


def test_worktree_con_commit_dopo_la_pr_aggiornata_non_si_toglie(capsys):
    for risposta in ("ahead\n", "diverged\n", comune.Risposta(1, "", "HTTP 404: No common ancestor")):
        f = _aggiornata(risposta)
        assert pulisci.main(f, esegui_davvero=True) == 0
        assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    assert "Con modifiche (1)" in capsys.readouterr().out


# #476 punto 4: i rami locali senza worktree.
RAMI = "\n".join([
    "main aaa", "corrente c0", "unito-pulito h1",                      # main, ramo corrente, ramo di una worktree: mai
    "locale-unito l1", "locale-in-main l2", "locale-aggiornato l3",
    "locale-senza-pr l4", "locale-aperto l5", "locale-dopo l6", "locale-chiuso l7",
    "locale-nuovo l8",                                                  # senza PR, testa già in main: si chiede lo stesso
]) + "\n"
PR_RAMI = [
    {"number": 30, "state": "MERGED", "headRefName": "locale-unito", "headRefOid": "l1"},
    {"number": 35, "state": "MERGED", "headRefName": "locale-in-main", "headRefOid": "altra"},
    {"number": 31, "state": "MERGED", "headRefName": "locale-aggiornato", "headRefOid": "g3"},
    {"number": 32, "state": "OPEN", "headRefName": "locale-aperto", "headRefOid": "l5"},
    {"number": 33, "state": "MERGED", "headRefName": "locale-dopo", "headRefOid": "g6"},
    {"number": 34, "state": "CLOSED", "headRefName": "locale-chiuso", "headRefOid": "l7"},
]


def finto_rami():
    from test_squadra_stato import PR_TUTTE
    return finto(**{
        "git for-each-ref": RAMI, "git rev-parse --abbrev-ref HEAD": "corrente\n",
        "gh pr list --state all": PR_TUTTE + PR_RAMI,
        "git merge-base --is-ancestor l2 origin/main": comune.Risposta(0, "", ""),
        "git merge-base --is-ancestor l8 origin/main": comune.Risposta(0, "", ""),
        "gh api repos/{owner}/{repo}/compare/g3...l3": "behind\n",
        "gh api repos/{owner}/{repo}/compare/g6...l6": "ahead\n",
    })


def test_rami_locali_in_prova_si_elencano_e_non_si_toccano(capsys):
    f = finto_rami()
    assert pulisci.main(f) == 0
    assert not f.lanciati("git branch")
    testo = capsys.readouterr().out
    assert "Rami locali da togliere (3)" in testo and "Rami locali da chiedere (4)" in testo
    assert "Rami locali con PR aperta (1)" in testo
    for nome in ("locale-unito", "locale-in-main", "locale-aggiornato", "locale-senza-pr", "locale-dopo", "locale-chiuso",
                 "locale-nuovo"):
        assert nome in testo


def test_rami_locali_con_esegui_toglie_solo_quelli_su_main():
    f = finto_rami()
    assert pulisci.main(f, esegui_davvero=True) == 0
    tolti = f.lanciati("git branch")
    assert "git branch -D locale-unito" in tolti and "git branch -d locale-in-main" in tolti
    assert "git branch -D locale-aggiornato" in tolti
    for mai in ("main", "corrente", "locale-senza-pr", "locale-aperto", "locale-dopo", "locale-chiuso", "locale-nuovo"):
        assert not [c for c in tolti if c.endswith(" " + mai)], mai
    assert len([c for c in tolti if "unito-pulito" in c]) == 1          # solo con la sua worktree, non due volte


def test_rami_locali_nel_json(capsys):
    pulisci.main(finto_rami(), json_=True)
    rami = json.loads(capsys.readouterr().out)["rami"]
    assert sorted(r["ramo"] for r in rami["da_togliere"]) == ["locale-aggiornato", "locale-in-main", "locale-unito"]
    assert sorted(r["ramo"] for r in rami["da_chiedere"]) == ["locale-chiuso", "locale-dopo", "locale-nuovo", "locale-senza-pr"]
