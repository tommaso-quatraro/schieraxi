"""script/squadra: `pulisci` elenca le worktree in gruppi e con --esegui toglie solo quelle unite e pulite."""
from __future__ import annotations

import json

import pytest
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


def una_worktree(nome, testa, ramo, prs=(), in_main=False):
    """La cartella principale su main (testa «aaa») e una sola worktree degli agenti, senza modifiche. `ramo` None = staccata."""
    porcelain = (f"worktree C:/repo\nHEAD aaa\nbranch refs/heads/main\n\n"
                 f"worktree {WT}/{nome}\nHEAD {testa}\n" + (f"branch refs/heads/{ramo}\n" if ramo else "detached\n"))
    return Finto({
        "git worktree list --porcelain": porcelain,
        "gh pr list --state all": list(prs),
        f"git -C {WT}/{nome} status --porcelain": "",
        "git merge-base --is-ancestor": comune.Risposta(0 if in_main else 1, "", ""),
        "git for-each-ref": "main aaa\n" + (f"{ramo} {testa}\n" if ramo else ""),
        "git rev-parse --abbrev-ref HEAD": "main\n",
        "git worktree remove": "", "git branch -D": "", "git branch -d": "",
    })


def test_prova_non_toglie_niente(capsys):
    f = finto()
    assert pulisci.main(f) == 0
    assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    testo = capsys.readouterr().out
    assert "Da togliere (1)" in testo and "Con modifiche (2)" in testo and "Senza PR (2)" in testo
    assert "PROVA" in testo and "--esegui" in testo


def test_esegui_toglie_solo_le_unite_e_pulite():
    f = finto()
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert f.lanciati("git worktree remove") == [f"git worktree remove {WT}/agent-1"]
    # mai --force; il ramo unito con la stessa testa della PR si toglie con -D (unione squash)
    assert not [c for c in f.chiamate if "--force" in c]
    assert f.lanciati("git branch") == ["git branch -D unito-pulito"]


def test_ramo_con_pr_unita_e_testa_gia_in_main_si_toglie_con_d_minuscola():
    unita = [{"number": 14, "state": "MERGED", "headRefName": "gia-in-main", "headRefOid": "altra"}]
    f = una_worktree("agent-8", "h8", "gia-in-main", prs=unita, in_main=True)
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert f.lanciati("git worktree remove") == [f"git worktree remove {WT}/agent-8"]
    assert f.lanciati("git branch") == ["git branch -d gia-in-main"]


# #524: una sessione appena aperta lavora su un ramo senza commit propri. La sua testa è in main, ma niente è stato unito:
# con --esegui la cartella spariva mentre la sessione la usava.
@pytest.mark.parametrize("ramo", ["claude/sessione-nuova", "lavoro-nuovo", None])
def test_worktree_senza_commit_propri_e_senza_pr_si_chiede_e_non_si_toglie(ramo, capsys):
    f = una_worktree("sessione-nuova", "aaa", ramo, in_main=True)
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    righe = capsys.readouterr().out.splitlines()
    assert [r for r in righe if r.startswith("Da togliere (0)")] and [r for r in righe if r.startswith("Senza PR (1)")]
    [riga] = [r for r in righe if "sessione-nuova" in r]
    assert "nessun commit proprio" in riga                     # chi legge l'elenco capisce perché non è «da togliere»


def test_worktree_senza_commit_propri_con_pr_chiusa_non_si_toglie(capsys):
    chiusa = [{"number": 40, "state": "CLOSED", "headRefName": "lavoro-lasciato", "headRefOid": "vecchia"}]
    f = una_worktree("agent-9", "aaa", "lavoro-lasciato", prs=chiusa, in_main=True)
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    assert "Senza PR (1)" in capsys.readouterr().out


# #524 (facoltativo): le sessioni aperte dall'app lavorano in .claude/worktrees/<nome> sul ramo claude/<nome>. Anche a PR
# unita la sessione può essere ancora aperta: la sua cartella non si toglie da sola.
def _ramo_unito(ramo):
    unita = [{"number": 50, "state": "MERGED", "headRefName": ramo, "headRefOid": "s1"}]
    return una_worktree("sessione-finita", "s1", ramo, prs=unita)


def test_sessione_dell_app_con_pr_unita_non_si_toglie(capsys):
    f = _ramo_unito("claude/sessione-finita")
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
    righe = capsys.readouterr().out.splitlines()
    assert [r for r in righe if r.startswith("Da togliere (0)")] and [r for r in righe if r.startswith("Sessioni dell'app (1)")]
    assert [r for r in righe if "sessione-finita" in r and "PR #50 MERGED" in r]


def test_sessione_dell_app_con_pr_unita_nel_json(capsys):
    pulisci.main(_ramo_unito("claude/sessione-finita"), json_=True)
    gruppi = json.loads(capsys.readouterr().out)["gruppi"]
    assert gruppi["da_togliere"] == []
    assert [w["ramo"] for w in gruppi["sessione_app"]] == ["claude/sessione-finita"]


def test_un_ramo_che_non_comincia_per_claude_barra_si_toglie_come_gli_altri():
    # Il confine è la barra: «claude-md-…» comincia per «claude» ma è un ramo come gli altri, non quello di una sessione.
    f = _ramo_unito("claude-md-finita")
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert f.lanciati("git worktree remove") == [f"git worktree remove {WT}/sessione-finita"]
    assert f.lanciati("git branch") == ["git branch -D claude-md-finita"]


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
    assert sorted(w["percorso"].rsplit("/", 1)[1] for w in dati["gruppi"]["da_togliere"]) == ["agent-1"]
    assert sorted(w["percorso"].rsplit("/", 1)[1] for w in dati["gruppi"]["senza_pr"]) == ["agent-3", "agent-5"]


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


def test_worktree_compare_senza_risposta_non_si_toglie_e_lo_dice(capsys):
    for errore in ("HTTP 502: Bad Gateway", "API rate limit exceeded (HTTP 403)", "error connecting to api.github.com"):
        f = _aggiornata(comune.Risposta(1, "", errore))
        assert pulisci.main(f, esegui_davvero=True) == 0
        assert not f.lanciati("git worktree remove") and not f.lanciati("git branch")
        testo = capsys.readouterr().out
        assert "GitHub non ha risposto: riprova" in testo and "commit fatti dopo" not in testo


def test_ramo_locale_compare_senza_risposta_resta_da_chiedere_col_motivo_giusto(capsys):
    f = finto_rami()
    f.risposte["gh api repos/{owner}/{repo}/compare/g3...l3"] = comune.Risposta(1, "", "HTTP 503: Service Unavailable")
    f.risposte["gh api repos/{owner}/{repo}/compare/g6...l6"] = comune.Risposta(1, "", "HTTP 404: No common ancestor")
    assert pulisci.main(f, esegui_davvero=True) == 0
    assert not [c for c in f.lanciati("git branch") if c.endswith(" locale-aggiornato")]
    righe = capsys.readouterr().out.splitlines()
    [aggiornato] = [r for r in righe if "locale-aggiornato" in r]
    [dopo] = [r for r in righe if "locale-dopo" in r]
    assert "GitHub non ha risposto: riprova" in aggiornato
    assert "commit fatti dopo l'unione" in dopo           # 404: il commit non è su GitHub, quindi non è nella PR


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
