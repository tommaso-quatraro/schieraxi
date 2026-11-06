"""`pulisci`: le worktree degli agenti (.claude/worktrees/) in gruppi. Di default fa solo la PROVA.

Con --esegui toglie SOLO il gruppo «da togliere» (ramo unito e niente modifiche): `git worktree remove` senza --force, poi
il ramo locale (`git branch -d`, oppure `-D` quando la PR è unita con squash e la testa del ramo è la stessa della PR).
Le worktree bloccate da un agente, quelle con modifiche e quelle senza PR non si toccano mai.
Codici di uscita: 0 fatto; 1 errore di gh o git, o una rimozione non riuscita."""
from __future__ import annotations

import json
import sys

import comune
import worktree

TITOLI = [("da_togliere", "Da togliere", "ramo unito, niente modifiche"),
          ("con_modifiche", "Con modifiche", "da chiedere all'utente"),
          ("senza_pr", "Senza PR", "niente PR aperta né unita: da chiedere"),
          ("in_corso", "Con PR aperta", "lavoro in corso"),
          ("bloccata", "Bloccate", "un agente le sta usando"),
          ("sparita", "Cartelle sparite", "per toglierle dall'elenco di git: «git worktree prune»")]


def _riga(w: dict) -> str:
    parti = [w["percorso"].rsplit("/", 1)[-1], w["ramo"] or "(staccata)"]
    if w["pr"]:
        parti.append(f"PR #{w['pr']} {w['stato_pr']}")
    if w.get("motivo"):
        parti.append(w["motivo"])
    return "  " + ", ".join(parti)


def togli(esegui: comune.Esegui, w: dict) -> str | None:
    """Toglie worktree e ramo; restituisce l'errore o None."""
    r = esegui(["git", "worktree", "remove", w["percorso"]])
    if r.codice != 0:
        return f"{w['percorso']}: {(r.errore or r.uscita).strip()[:200]}"
    if w["ramo"] and w["ramo"] != "main":
        r = esegui(["git", "branch", "-D" if w.get("pr_unita_stessa_testa") else "-d", w["ramo"]])
        if r.codice != 0:
            return f"ramo {w['ramo']}: {(r.errore or r.uscita).strip()[:200]}"
    return None


def main(esegui: comune.Esegui, esegui_davvero: bool = False, json_: bool = False) -> int:
    try:
        voci = worktree.raccogli(esegui)
    except comune.ErroreComando as e:
        print(f"pulisci: {e}", file=sys.stderr)
        return 1
    gruppi = {chiave: [w for w in voci if w["gruppo"] == chiave] for chiave, _, _ in TITOLI}
    errori, tolte = [], []
    if esegui_davvero:
        for w in gruppi["da_togliere"]:
            errore = togli(esegui, w)
            if errore:
                errori.append(errore)
            else:
                tolte.append(w["percorso"])
    if json_:
        print(json.dumps({"prova": not esegui_davvero, "gruppi": gruppi, "tolte": tolte, "errori": errori},
                         ensure_ascii=False, indent=2))
    else:
        for chiave, titolo, nota in TITOLI:
            print(f"{titolo} ({len(gruppi[chiave])}): {nota}")
            for w in gruppi[chiave]:
                print(_riga(w))
        if esegui_davvero:
            print(f"Tolte: {len(tolte)} worktree.")
        elif gruppi["da_togliere"]:
            print(f"PROVA: niente tolto. Per togliere le {len(gruppi['da_togliere'])} worktree «da togliere»: aggiungi --esegui.")
    for e in errori:
        print(f"pulisci: {e}", file=sys.stderr)
    return 1 if errori else 0


NOME = "pulisci"
AIUTO = "Worktree degli agenti in gruppi; con --esegui toglie solo quelle unite e senza modifiche. Prova senza --esegui."
USCITE = "0 fatto; 1 errore di gh o git, o una rimozione non riuscita."


def opzioni(p) -> None:
    p.add_argument("--esegui", action="store_true", help="toglie davvero il gruppo «da togliere» (senza: solo prova)")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, esegui_davvero=args.esegui, json_=args.json)
