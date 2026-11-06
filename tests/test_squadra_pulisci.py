"""script/squadra: `pulisci` elenca le worktree in gruppi e con --esegui toglie solo quelle unite e pulite."""
from __future__ import annotations

import json

from test_squadra_comune import Finto
from test_squadra_stato import WT, risposte_worktree

import comune
import pulisci


def finto(**extra):
    r = risposte_worktree()
    r.update({"git worktree remove": "", "git branch -d": "", "git branch -D": ""})
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
    f = Finto({"git worktree list --porcelain": porcelain, "gh pr list --state all": []})
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert "git worktree prune" in capsys.readouterr().out
    assert not f.lanciati("git worktree remove")
