"""`stato`: PR aperte, tetti per gruppo, corse sui Mac, issue aperte per obiettivo, worktree locali. Sola lettura.

Codici di uscita: 0 fatto; 1 errore di gh o git (scritto su stderr)."""
from __future__ import annotations

import json
import sys
from datetime import datetime

import aree
import comune
import worktree

CAMPI_PR = "number,title,isDraft,mergeable,headRefName,headRefOid,createdAt,files,statusCheckRollup"
CAMPI_CORSE = "databaseId,workflowName,status,conclusion,event,headBranch,headSha,createdAt"
ROSSI = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED", "ERROR"}
UNIBILE = {"MERGEABLE": "sì", "CONFLICTING": "CONFLITTO", "UNKNOWN": "da calcolare"}


def controlli(rollup: list[dict]) -> str:
    """Un controllo in corso → «in corso»; poi rosso; poi annullato (che non è rosso: va rilanciato); poi verde."""
    if not rollup:
        return "nessuno"
    stati = []
    for c in rollup:
        if c.get("__typename") == "StatusContext":
            stati.append({"PENDING": "in corso", "EXPECTED": "in corso"}.get(c.get("state"), "rosso" if c.get("state") in ROSSI else "ok"))
        elif c.get("status") != "COMPLETED":
            stati.append("in corso")
        elif c.get("conclusion") in ROSSI:
            stati.append("rosso")
        elif c.get("conclusion") == "CANCELLED":
            stati.append("annullato")
        else:
            stati.append("ok")
    for s in ("in corso", "rosso", "annullato"):
        if s in stati:
            return s
    return "verde"


def corse(esegui: comune.Esegui, stato_corsa: str) -> list[dict]:
    return comune.chiama_json(esegui, ["gh", "run", "list", "--status", stato_corsa, "--limit", "100",
                                       "--json", CAMPI_CORSE]) or []


def _obiettivi(esegui: comune.Esegui) -> list[dict]:
    etichetta = aree.carica()["etichetta_obiettivo"]
    elenco = comune.chiama_json(esegui, ["gh", "issue", "list", "--label", etichetta, "--state", "open",
                                         "--json", "number,title"]) or []
    uscita = []
    for o in sorted(elenco, key=lambda x: x["number"]):
        figlie = comune.chiama_json(esegui, ["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{o['number']}/sub_issues",
                                             "--paginate"]) or []
        uscita.append({"numero": o["number"], "titolo": o["title"],
                       "aperte": sum(1 for f in figlie if f.get("state") == "open"), "totali": len(figlie)})
    return uscita


def raccogli(esegui: comune.Esegui, adesso: datetime | None = None) -> dict:
    dati = aree.carica()
    prs = []
    for p in comune.chiama_json(esegui, ["gh", "pr", "list", "--state", "open", "--limit", "100", "--json", CAMPI_PR]) or []:
        prs.append({"numero": p["number"], "titolo": p["title"], "bozza": p["isDraft"], "mergeable": p["mergeable"],
                    "ramo": p["headRefName"], "testa": p.get("headRefOid"),
                    "controlli": controlli(p.get("statusCheckRollup") or []),
                    "gruppo": aree.gruppo_di([f["path"] for f in p.get("files") or []]),
                    "eta": comune.eta(p["createdAt"], adesso)})
    tetti = {g: {"aperte": sum(1 for p in prs if p["gruppo"] == g), "tetto": v["tetto"]} for g, v in dati["gruppi"].items()}
    mac = [{"id": c["databaseId"], "workflow": c["workflowName"], "stato": c["status"], "evento": c["event"],
            "ramo": c["headBranch"], "eta": comune.eta(c["createdAt"], adesso)}
           for s in ("in_progress", "queued") for c in corse(esegui, s) if c["workflowName"] in dati["workflow_mac"]]
    return {"pr": sorted(prs, key=lambda p: p["numero"]), "tetti": tetti, "mac": mac,
            "obiettivi": _obiettivi(esegui), "worktree": worktree.raccogli(esegui)}


def testo(s: dict) -> str:
    righe = [f"PR aperte: {len(s['pr'])}"]
    if s["pr"]:
        righe.append(comune.tabella(
            [[f"#{p['numero']}", p["titolo"][:60], "bozza" if p["bozza"] else "", UNIBILE.get(p["mergeable"], p["mergeable"]),
              p["controlli"], p["gruppo"] or "senza tetto", p["eta"]] for p in s["pr"]],
            ["PR", "titolo", "bozza", "unibile", "controlli", "gruppo", "età"]))
    righe.append("Tetti: " + " · ".join(f"{g} {t['aperte']}/{t['tetto']}" + (" (PIENO)" if t["aperte"] >= t["tetto"] else "")
                                         for g, t in s["tetti"].items()))
    righe.append(f"Corse sui Mac (in corso o in coda): {len(s['mac'])}")
    righe += [f"  {c['workflow']} [{c['stato']}, {c['evento']}] ramo {c['ramo']}, {c['eta']}" for c in s["mac"]]
    righe.append("Obiettivi (sotto-issue aperte/totali):")
    righe += [f"  #{o['numero']} {o['titolo']}: {o['aperte']}/{o['totali']}" for o in s["obiettivi"]] or ["  nessuno aperto"]
    righe.append(f"Worktree degli agenti: {len(s['worktree'])}")
    if s["worktree"]:
        righe.append(comune.tabella(
            [[w["percorso"].rsplit("/", 1)[-1], w["ramo"] or "(staccata)", f"#{w['pr']}" if w["pr"] else "",
              "sì" if w["unito"] else "no", "sì" if w["modifiche"] else "no", w["gruppo"]] for w in s["worktree"]],
            ["cartella", "ramo", "PR", "unito", "modifiche", "gruppo"]))
    return "\n".join(righe)


def main(esegui: comune.Esegui, json_: bool = False, adesso: datetime | None = None) -> int:
    try:
        s = raccogli(esegui, adesso)
    except comune.ErroreComando as e:
        print(f"stato: {e}", file=sys.stderr)
        return 1
    print(json.dumps(s, ensure_ascii=False, indent=2) if json_ else testo(s))
    return 0


NOME = "stato"
AIUTO = "Tabella di PR aperte, tetti, corse sui Mac, obiettivi e worktree (sola lettura)."
USCITE = "0 fatto; 1 errore di gh o git."


def opzioni(p) -> None:
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, json_=args.json)
