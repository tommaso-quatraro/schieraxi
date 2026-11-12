"""`pulisci`: le worktree degli agenti (.claude/worktrees/) e i rami locali senza worktree, in gruppi. Di default fa solo la PROVA.

Con --esegui toglie SOLO:
- le worktree del gruppo «da togliere» (ramo unito e niente modifiche): `git worktree remove` senza --force, poi il ramo
  locale (`git branch -d`, oppure `-D` quando la PR è unita con squash e la testa del ramo è quella della PR o un suo antenato);
- i rami locali «da togliere»: PR del ramo unita e lavoro già su main (stessa testa della PR, testa antenata di quella della
  PR, o testa dentro origin/main).
Le worktree bloccate da un agente, quelle con modifiche e quelle senza PR non si toccano mai. «Unito» vuole una PR unita: una
worktree con la testa già in main ma senza PR unita (ramo senza commit propri, o staccata) è anche lo stato di una sessione
appena aperta e sta in «Senza PR» (#524). Le worktree delle sessioni dell'app (ramo `claude/…`) non si tolgono mai da sole,
neppure a PR unita: la sessione può essere ancora aperta; stanno in «Sessioni dell'app».
I rami locali senza PR, con PR chiusa o con commit non uniti si elencano «da chiedere» e non si toccano; mai `main`, mai il
ramo corrente.
Codici di uscita: 0 fatto; 1 errore di gh o git, o una rimozione non riuscita."""
from __future__ import annotations

import json
import sys

import comune
import worktree

TITOLI = [("da_togliere", "Da togliere", "ramo unito, niente modifiche"),
          ("con_modifiche", "Con modifiche", "da chiedere all'utente"),
          ("senza_pr", "Senza PR", "niente PR aperta né unita: da chiedere"),
          ("sessione_app", "Sessioni dell'app", "ramo claude/… unito, niente modifiche: si tolgono a mano, a sessione chiusa"),
          ("in_corso", "Con PR aperta", "lavoro in corso"),
          ("bloccata", "Bloccate", "un agente le sta usando"),
          ("sparita", "Cartelle sparite", "per toglierle dall'elenco di git: «git worktree prune»")]

TITOLI_RAMI = [("da_togliere", "Rami locali da togliere", "PR unita, lavoro già su main"),
               ("da_chiedere", "Rami locali da chiedere", "senza PR, PR chiusa o commit non uniti: non si toccano"),
               ("in_corso", "Rami locali con PR aperta", "lavoro in corso")]


def _riga(w: dict) -> str:
    parti = [w["percorso"].rsplit("/", 1)[-1], w["ramo"] or "(staccata)"]
    if w["pr"]:
        parti.append(f"PR #{w['pr']} {w['stato_pr']}")
    if w.get("motivo"):
        parti.append(w["motivo"])
    return "  " + ", ".join(parti)


def _riga_ramo(r: dict) -> str:
    parti = [r["ramo"]]
    if r["pr"]:
        parti.append(f"PR #{r['pr']} {r['stato_pr']}")
    if r.get("motivo"):
        parti.append(r["motivo"])
    return "  " + ", ".join(parti)


def _togli_ramo(esegui: comune.Esegui, ramo: str, unione: str | None) -> str | None:
    r = esegui(["git", "branch", "-D" if unione in worktree.SQUASH else "-d", ramo])
    if r.codice != 0:
        return f"ramo {ramo}: {(r.errore or r.uscita).strip()[:200]}"
    return None


def togli(esegui: comune.Esegui, w: dict) -> str | None:
    """Toglie worktree e ramo; restituisce l'errore o None."""
    r = esegui(["git", "worktree", "remove", w["percorso"]])
    if r.codice != 0:
        return f"{w['percorso']}: {(r.errore or r.uscita).strip()[:200]}"
    if w["ramo"] and w["ramo"] != "main":
        return _togli_ramo(esegui, w["ramo"], w.get("unione"))
    return None


def main(esegui: comune.Esegui, esegui_davvero: bool = False, json_: bool = False) -> int:
    try:
        prs = worktree.pr_per_ramo(esegui)
        voci = worktree.raccogli(esegui, prs)
        rami = worktree.rami_locali(esegui, prs)
    except comune.ErroreComando as e:
        print(f"pulisci: {e}", file=sys.stderr)
        return 1
    gruppi = {chiave: [w for w in voci if w["gruppo"] == chiave] for chiave, _, _ in TITOLI}
    gruppi_rami = {chiave: [r for r in rami if r["gruppo"] == chiave] for chiave, _, _ in TITOLI_RAMI}
    errori, tolte, rami_tolti = [], [], []
    if esegui_davvero:
        for w in gruppi["da_togliere"]:
            errore = togli(esegui, w)
            if errore:
                errori.append(errore)
            else:
                tolte.append(w["percorso"])
        for r in gruppi_rami["da_togliere"]:
            errore = _togli_ramo(esegui, r["ramo"], r["unione"])
            if errore:
                errori.append(errore)
            else:
                rami_tolti.append(r["ramo"])
    if json_:
        print(json.dumps({"prova": not esegui_davvero, "gruppi": gruppi, "rami": gruppi_rami, "tolte": tolte,
                          "rami_tolti": rami_tolti, "errori": errori}, ensure_ascii=False, indent=2))
    else:
        for chiave, titolo, nota in TITOLI:
            print(f"{titolo} ({len(gruppi[chiave])}): {nota}")
            for w in gruppi[chiave]:
                print(_riga(w))
        for chiave, titolo, nota in TITOLI_RAMI:
            print(f"{titolo} ({len(gruppi_rami[chiave])}): {nota}")
            for r in gruppi_rami[chiave]:
                print(_riga_ramo(r))
        if esegui_davvero:
            print(f"Tolte: {len(tolte)} worktree e {len(rami_tolti)} rami locali senza worktree.")
        elif gruppi["da_togliere"] or gruppi_rami["da_togliere"]:
            print(f"PROVA: niente tolto. Per togliere le {len(gruppi['da_togliere'])} worktree e i "
                  f"{len(gruppi_rami['da_togliere'])} rami locali «da togliere»: aggiungi --esegui.")
    for e in errori:
        print(f"pulisci: {e}", file=sys.stderr)
    return 1 if errori else 0


NOME = "pulisci"
AIUTO = ("Worktree degli agenti e rami locali in gruppi; con --esegui toglie solo quelli uniti su main e senza modifiche. "
         "Prova senza --esegui.")
USCITE = "0 fatto; 1 errore di gh o git, o una rimozione non riuscita."


def opzioni(p) -> None:
    p.add_argument("--esegui", action="store_true",
                   help="toglie davvero le worktree e i rami locali «da togliere» (senza: solo prova)")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, esegui_davvero=args.esegui, json_=args.json)
