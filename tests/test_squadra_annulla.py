"""script/squadra: `annulla-superate` annulla solo le corse push/pull_request su commit vecchi, mai dispatch né schedule né main."""
from __future__ import annotations

import json

from test_squadra_comune import Finto

import annulla_superate as annulla
import comune

LS_REMOTE = "nuovo\trefs/heads/ramo-a\nmmm\trefs/heads/main\nb2\trefs/heads/ramo-b\n"


def corsa(id_, evento, ramo="ramo-a", sha="vecchio", stato="queued", wf="Controlli", fork=False):
    return {"databaseId": id_, "workflowName": wf, "status": stato, "conclusion": "", "event": evento,
            "headBranch": ramo, "headSha": sha, "createdAt": "2026-11-06T10:00:00Z", "fork": fork}


def come_api(corse) -> dict:
    """Le corse nel formato dell'API delle Actions (che dice da quale repository arriva il commit)."""
    return {"workflow_runs": [
        {"id": c["databaseId"], "name": c["workflowName"], "status": c["status"], "event": c["event"],
         "head_branch": c["headBranch"], "head_sha": c["headSha"],
         "head_repository": {"full_name": "altro/progetto" if c.get("fork") else "esempio/progetto"},
         "repository": {"full_name": "esempio/progetto"}} for c in corse]}


def chiave_api(stato: str) -> str:
    return f"gh api repos/{{owner}}/{{repo}}/actions/runs?status={stato}&per_page=100"


def risposte(corse_in_coda, corse_in_corso=()):
    return {
        chiave_api("queued"): come_api(corse_in_coda),
        chiave_api("in_progress"): come_api(corse_in_corso),
        chiave_api("waiting"): come_api([]),
        chiave_api("pending"): come_api([]),
        "git ls-remote --heads origin": LS_REMOTE,
        "gh run cancel": "",
    }


def test_superate_solo_push_e_pull_request_su_commit_vecchi():
    finto = Finto(risposte(
        [corsa(1, "pull_request"),                      # superata
         corsa(2, "push"),                              # superata
         corsa(3, "pull_request", sha="nuovo"),         # testa del ramo: resta
         corsa(4, "workflow_dispatch"),                 # mai
         corsa(5, "schedule", ramo="main"),             # mai
         corsa(6, "push", ramo="main", sha="vecchio"),  # main mai (c'è il rilascio)
         corsa(7, "pull_request", ramo="cancellato")],  # ramo sparito: non si sa, resta
        [corsa(8, "pull_request", ramo="ramo-b", sha="b1", stato="in_progress")]))
    assert [c["id"] for c in annulla.superate(finto)] == [1, 2, 8]


def test_corse_da_un_fork_con_lo_stesso_nome_di_ramo_non_si_toccano():
    finto = Finto(risposte([corsa(9, "pull_request", ramo="ramo-a", sha="vecchio", fork=True),
                            corsa(1, "pull_request")]))
    assert [c["id"] for c in annulla.superate(finto)] == [1]
    assert annulla.main(finto, esegui_davvero=True) == 0
    assert finto.lanciati("gh run cancel") == ["gh run cancel 1"]


def test_dispatch_e_schedule_non_si_annullano_mai_neanche_con_esegui():
    finto = Finto(risposte([corsa(4, "workflow_dispatch"), corsa(5, "schedule", ramo="ramo-a")]))
    assert annulla.main(finto, esegui_davvero=True) == 0
    assert finto.lanciati("gh run cancel") == []


def test_di_default_solo_prova(capsys):
    finto = Finto(risposte([corsa(1, "pull_request")]))
    assert annulla.main(finto) == 0
    assert finto.lanciati("gh run cancel") == []
    uscita = capsys.readouterr().out
    assert "PROVA" in uscita and "--esegui" in uscita


def test_con_esegui_annulla_le_superate():
    finto = Finto(risposte([corsa(1, "pull_request"), corsa(3, "pull_request", sha="nuovo")]))
    assert annulla.main(finto, esegui_davvero=True) == 0
    assert finto.lanciati("gh run cancel") == ["gh run cancel 1"]


def test_annullamento_fallito_esce_con_1(capsys):
    r = risposte([corsa(1, "pull_request")])
    r["gh run cancel 1"] = comune.Risposta(1, "", "run already completed")
    assert annulla.main(Finto(r), esegui_davvero=True) == 1
    assert "already completed" in capsys.readouterr().err


def test_json(capsys):
    annulla.main(Finto(risposte([corsa(1, "pull_request")])), json_=True)
    dati = json.loads(capsys.readouterr().out)
    assert dati["prova"] is True and [c["id"] for c in dati["superate"]] == [1]
