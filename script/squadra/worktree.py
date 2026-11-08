"""Le worktree degli agenti (.claude/worktrees/) e i rami locali senza worktree: ramo, PR, unito o no, modifiche, bloccata.
Usato da `stato` e `pulisci`.

Gruppi delle worktree:
- bloccata: un agente la sta usando (`git worktree lock`): non si guarda e non si tocca.
- sparita: la cartella non c'è più (`prunable`): non si guarda; si sistema con `git worktree prune`.
- con_modifiche: file cambiati non salvati in un commit, o commit fatti dopo l'unione della PR. Si chiede all'utente.
- in_corso: la PR del ramo è aperta.
- da_togliere: ramo unito e niente modifiche.
- senza_pr: niente PR aperta né unita, e la testa non è in origin/main.

«Unito» (funzione `unione`): PR MERGED con la stessa testa; oppure testa già dentro origin/main (dell'ultimo `git fetch`);
oppure PR MERGED con una testa che discende da quella locale (PR portata in pari con main da GitHub, «Update branch»):
`compare/<testa della PR>...<testa locale>` con `status` uguale a `behind` o `identical`.

Gruppi dei rami locali (`rami_locali`): da_togliere (PR MERGED e unito come sopra), in_corso (PR aperta), da_chiedere (tutto
il resto: senza PR, anche se la testa è in main; PR chiusa senza unione; commit non uniti). Mai `main`, mai il ramo corrente, mai un ramo aperto in una worktree."""
from __future__ import annotations

import comune

CARTELLA_WORKTREE = "/.claude/worktrees/"
DISCENDENTE = ("behind", "identical")
SQUASH = ("stessa_testa", "antenata")      # unione squash: il ramo si toglie con «git branch -D»


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


def antenata_della_pr(esegui: comune.Esegui, testa: str, testa_pr: str) -> bool:
    """La testa locale è un antenato della testa della PR (o la stessa)? Lo chiede a GitHub, che ha la testa della PR anche
    quando la copia locale non ce l'ha. Un errore (commit mai mandato su GitHub, rete) vale «no»: nel dubbio non si toglie."""
    r = esegui(["gh", "api", f"repos/{{owner}}/{{repo}}/compare/{testa_pr}...{testa}", "--jq", ".status"])
    return r.codice == 0 and r.uscita.strip() in DISCENDENTE


def unione(esegui: comune.Esegui, pr: dict | None, testa: str) -> str | None:
    """Come il lavoro è arrivato su main: «stessa_testa», «in_main», «antenata», oppure None (non unito)."""
    unita = bool(pr and pr["state"] == "MERGED")
    if unita and pr["headRefOid"] == testa:
        return "stessa_testa"
    if in_main(esegui, testa):
        return "in_main"
    if unita and antenata_della_pr(esegui, testa, pr["headRefOid"]):
        return "antenata"
    return None


def raccogli(esegui: comune.Esegui, prs: dict[str, dict] | None = None) -> list[dict]:
    voci = [v for v in _leggi_porcelain(comune.chiama(esegui, ["git", "worktree", "list", "--porcelain"]))
            if CARTELLA_WORKTREE in v["percorso"]]
    if prs is None:
        prs = pr_per_ramo(esegui) if voci else {}
    for v in voci:
        pr = prs.get(v["ramo"]) if v["ramo"] else None
        v.update(pr=pr["number"] if pr else None, stato_pr=pr["state"] if pr else None, modifiche=False, unito=False,
                 unione=None)
        if v["bloccata"]:
            v["gruppo"] = "bloccata"
            continue
        if v["sparita"]:
            v["gruppo"], v["motivo"] = "sparita", "cartella cancellata a mano"
            continue
        v["modifiche"] = bool(comune.chiama(esegui, ["git", "-C", v["percorso"], "status", "--porcelain"]).strip())
        v["unione"] = unione(esegui, pr, v["testa"])
        v["unito"] = v["unione"] is not None
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


def rami_locali(esegui: comune.Esegui, prs: dict[str, dict]) -> list[dict]:
    """I rami locali che non sono aperti in nessuna worktree (né nella cartella principale), tranne main e il ramo corrente."""
    aperti = {v["ramo"] for v in _leggi_porcelain(comune.chiama(esegui, ["git", "worktree", "list", "--porcelain"]))
              if v["ramo"]}
    corrente = comune.chiama(esegui, ["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    esclusi = aperti | {"main", corrente}
    rami = []
    for riga in comune.chiama(esegui, ["git", "for-each-ref", "--format=%(refname:short) %(objectname)",
                                       "refs/heads"]).splitlines():
        nome, _, testa = riga.strip().partition(" ")
        if not nome or not testa or nome in esclusi:
            continue
        pr = prs.get(nome)
        voce = {"ramo": nome, "testa": testa, "pr": pr["number"] if pr else None, "stato_pr": pr["state"] if pr else None,
                "unione": unione(esegui, pr, testa), "motivo": ""}
        if pr and pr["state"] == "OPEN":
            voce["gruppo"] = "in_corso"
        elif voce["unione"] and voce["stato_pr"] == "MERGED":
            voce["gruppo"] = "da_togliere"
        else:
            # Anche un ramo senza PR con la testa già in main (appena creato, non ancora usato) si chiede: può servire a qualcuno.
            voce["gruppo"] = "da_chiedere"
            voce["motivo"] = {"MERGED": "commit fatti dopo l'unione della PR",
                              "CLOSED": "PR chiusa senza unione"}.get(voce["stato_pr"], "niente PR")
        rami.append(voce)
    return rami
