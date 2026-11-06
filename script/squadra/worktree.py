"""Le worktree degli agenti (.claude/worktrees/): ramo, PR, unito o no, modifiche, bloccata. Usato da `stato` e `pulisci`.

Gruppi:
- bloccata: un agente la sta usando (`git worktree lock`): non si guarda e non si tocca.
- sparita: la cartella non c'è più (`prunable`): non si guarda; si sistema con `git worktree prune`.
- con_modifiche: file cambiati non salvati in un commit, o commit fatti dopo l'unione della PR. Si chiede all'utente.
- in_corso: la PR del ramo è aperta.
- da_togliere: ramo unito (PR MERGED con la stessa testa, o testa già dentro origin/main) e niente modifiche.
- senza_pr: niente PR aperta né unita, e la testa non è in origin/main."""
from __future__ import annotations

import comune

CARTELLA_WORKTREE = "/.claude/worktrees/"


def _leggi_porcelain(testo: str) -> list[dict]:
    voci, voce = [], None
    for riga in testo.splitlines() + [""]:
        if not riga.strip():
            if voce:
                voci.append(voce)
            voce = None
            continue
        chiave, _, valore = riga.partition(" ")
        if chiave == "worktree":
            voce = {"percorso": valore.replace("\\", "/"), "testa": None, "ramo": None, "bloccata": False, "sparita": False}
        elif voce is None:
            continue
        elif chiave == "HEAD":
            voce["testa"] = valore
        elif chiave == "branch":
            voce["ramo"] = valore.removeprefix("refs/heads/")
        elif chiave == "locked":
            voce["bloccata"] = True
        elif chiave == "prunable":
            voce["sparita"] = True
    return voci


def pr_per_ramo(esegui: comune.Esegui) -> dict[str, dict]:
    """Per ogni ramo la PR che conta: quella aperta se c'è, se no l'ultima unita, se no l'ultima chiusa."""
    prs = comune.chiama_json(esegui, ["gh", "pr", "list", "--state", "all", "--limit", "300",
                                      "--json", "number,state,headRefName,headRefOid"]) or []
    ordine = {"OPEN": 0, "MERGED": 1, "CLOSED": 2}
    scelte: dict[str, dict] = {}
    for pr in sorted(prs, key=lambda p: (ordine.get(p["state"], 3), -p["number"])):
        scelte.setdefault(pr["headRefName"], pr)
    return scelte


def in_main(esegui: comune.Esegui, testa: str) -> bool:
    r = esegui(["git", "merge-base", "--is-ancestor", testa, "origin/main"])
    if r.codice in (0, 1):
        return r.codice == 0
    raise comune.ErroreComando(f"git merge-base è uscito con {r.codice}: {r.errore.strip()[:200]}")


def raccogli(esegui: comune.Esegui) -> list[dict]:
    voci = [v for v in _leggi_porcelain(comune.chiama(esegui, ["git", "worktree", "list", "--porcelain"]))
            if CARTELLA_WORKTREE in v["percorso"]]
    prs = pr_per_ramo(esegui) if voci else {}
    for v in voci:
        pr = prs.get(v["ramo"]) if v["ramo"] else None
        v.update(pr=pr["number"] if pr else None, stato_pr=pr["state"] if pr else None, modifiche=False, unito=False)
        if v["bloccata"]:
            v["gruppo"] = "bloccata"
            continue
        if v["sparita"]:
            v["gruppo"], v["motivo"] = "sparita", "cartella cancellata a mano"
            continue
        v["modifiche"] = bool(comune.chiama(esegui, ["git", "-C", v["percorso"], "status", "--porcelain"]).strip())
        v["pr_unita_stessa_testa"] = bool(pr and pr["state"] == "MERGED" and pr["headRefOid"] == v["testa"])
        v["unito"] = v["pr_unita_stessa_testa"] or in_main(esegui, v["testa"])
        if v["modifiche"]:
            v["gruppo"], v["motivo"] = "con_modifiche", "file cambiati non salvati"
        elif pr and pr["state"] == "OPEN":
            v["gruppo"] = "in_corso"
        elif v["unito"]:
            v["gruppo"] = "da_togliere"
        elif pr and pr["state"] == "MERGED":
            v["gruppo"], v["motivo"] = "con_modifiche", "commit fatti dopo l'unione della PR"
        else:
            v["gruppo"] = "senza_pr"
    return voci
