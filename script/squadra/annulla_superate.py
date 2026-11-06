"""`annulla-superate`: annulla le corse in coda o in corso partite da `push` o `pull_request` su un commit che non è più la
testa del suo ramo (è arrivato un push dopo). Di default fa solo la PROVA; annulla solo con --esegui.

Mai: corse `workflow_dispatch` (prove rosse volute, foto), `schedule`, e nessuna corsa del ramo main (c'è il rilascio).
Un ramo che non c'è più su GitHub non si tocca (non si sa quale sia la testa). Le corse dei fork non si toccano mai.
Codici di uscita: 0 fatto (anche niente da annullare); 1 errore di gh o git, o un annullamento non riuscito."""
from __future__ import annotations

import json
import sys

import comune

EVENTI = {"push", "pull_request"}
STATI = ("queued", "in_progress", "waiting", "pending")
RAMO_PRINCIPALE = "main"


def teste_dei_rami(esegui: comune.Esegui) -> dict[str, str]:
    teste = {}
    for riga in comune.chiama(esegui, ["git", "ls-remote", "--heads", "origin"]).splitlines():
        sha, _, ref = riga.partition("\t")
        if ref.startswith("refs/heads/"):
            teste[ref.removeprefix("refs/heads/")] = sha.strip()
    return teste


def corse_del_repository(esegui: comune.Esegui, stato_corsa: str) -> list[dict]:
    """Le corse in uno stato, dall'API delle Actions: a differenza di `gh run list` dice da quale repository arriva il commit.
    Le corse dei fork (head_repository diverso dal repository) si scartano: il loro ramo può avere lo stesso nome di uno
    di origin, e la testa da confrontare sarebbe quella sbagliata."""
    dati = comune.chiama_json(esegui, ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs?status={stato_corsa}&per_page=100"]) or {}
    uscita = []
    for c in dati.get("workflow_runs") or []:
        da = (c.get("head_repository") or {}).get("full_name")
        if not da or da != (c.get("repository") or {}).get("full_name"):
            continue
        uscita.append({"databaseId": c["id"], "workflowName": c.get("name", ""), "status": c.get("status", ""),
                       "event": c.get("event", ""), "headBranch": c.get("head_branch") or "", "headSha": c.get("head_sha") or ""})
    return uscita


def superate(esegui: comune.Esegui) -> list[dict]:
    candidate = [c for s in STATI for c in corse_del_repository(esegui, s)
                 if c["event"] in EVENTI and c["headBranch"] != RAMO_PRINCIPALE]
    if not candidate:
        return []
    teste = teste_dei_rami(esegui)
    uscita = []
    for c in sorted(candidate, key=lambda c: c["databaseId"]):
        testa = teste.get(c["headBranch"])
        if testa and testa != c["headSha"]:
            uscita.append({"id": c["databaseId"], "workflow": c["workflowName"], "evento": c["event"],
                           "ramo": c["headBranch"], "commit": c["headSha"][:7], "testa": testa[:7], "stato": c["status"]})
    return uscita


def main(esegui: comune.Esegui, esegui_davvero: bool = False, json_: bool = False) -> int:
    try:
        elenco = superate(esegui)
    except comune.ErroreComando as e:
        print(f"annulla-superate: {e}", file=sys.stderr)
        return 1
    errori = []
    for c in elenco:
        c["annullata"] = False
        if esegui_davvero:
            r = esegui(["gh", "run", "cancel", str(c["id"])])
            c["annullata"] = r.codice == 0
            if r.codice != 0:
                errori.append(f"corsa {c['id']}: {(r.errore or r.uscita).strip()[:200]}")
    if json_:
        print(json.dumps({"prova": not esegui_davvero, "superate": elenco, "errori": errori}, ensure_ascii=False, indent=2))
    else:
        if not elenco:
            print("Nessuna corsa superata da annullare.")
        for c in elenco:
            verbo = ("annullata" if c["annullata"] else "NON annullata") if esegui_davvero else "annullerei"
            print(f"{verbo}: corsa {c['id']} {c['workflow']} [{c['evento']}, {c['stato']}] ramo {c['ramo']}, "
                  f"commit {c['commit']} (la testa ora è {c['testa']})")
        if elenco and not esegui_davvero:
            print(f"PROVA: niente annullato. Per annullare queste {len(elenco)} corse: aggiungi --esegui.")
    for e in errori:
        print(f"annulla-superate: {e}", file=sys.stderr)
    return 1 if errori else 0


NOME = "annulla-superate"
AIUTO = "Annulla le corse push/pull_request su commit superati (mai dispatch, schedule o main). Prova senza --esegui."
USCITE = "0 fatto (anche niente da annullare); 1 errore di gh o git, o un annullamento non riuscito."


def opzioni(p) -> None:
    p.add_argument("--esegui", action="store_true", help="annulla davvero (senza: solo prova)")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, esegui_davvero=args.esegui, json_=args.json)
