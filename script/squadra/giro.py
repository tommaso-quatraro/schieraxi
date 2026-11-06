"""`giro`: la procedura fissa del coordinatore in un comando. Fa `stato`, cerca le PR in conflitto e le corse fallite per
guasto d'infrastruttura, le corse superate (`annulla-superate`), le worktree da pulire (`pulisci`, SEMPRE solo prova) e, se la
variabile d'ambiente SCHIERAXI_URL c'è, la versione in produzione (letta da /sw.js, pubblico; l'indirizzo non si stampa).
Confronta con il giro di prima (.superpowers/squadra/giro.json, fuori da git) e stampa SOLO ciò che è cambiato.

Con --esegui: rilancia una volta sola le corse con guasto d'infrastruttura (`gh run rerun <id> --failed`) e annulla le corse
superate. Senza: solo prova. Non unisce mai, non toglie worktree.
Codici di uscita: 0 niente di nuovo; 1 errore di gh o git; 10 c'è qualcosa da guardare (cambiamenti stampati)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

import annulla_superate
import attendi
import comune
import stato

CARTELLA_STATO = comune.RADICE / ".superpowers" / "squadra"
UNIBILE = {"MERGEABLE": "unibile", "CONFLICTING": "IN CONFLITTO con main", "UNKNOWN": "unibile da calcolare"}


def prepara_cartella() -> Path:
    CARTELLA_STATO.mkdir(parents=True, exist_ok=True)
    ignora = CARTELLA_STATO / ".gitignore"
    if not ignora.exists():
        ignora.write_text("*\n", encoding="utf-8")
    return CARTELLA_STATO / "giro.json"


def leggi_url_vero(indirizzo: str) -> str:
    richiesta = urllib.request.Request(indirizzo, headers={"User-Agent": "SchieraXI-squadra"})
    with urllib.request.urlopen(richiesta, timeout=15) as r:  # noqa: S310 (indirizzo https scelto da chi usa il comando)
        return r.read(200_000).decode("utf-8", "replace")


def versione_produzione(url: str, leggi_url: Callable[[str], str]) -> str:
    try:
        testo = leggi_url(url.rstrip("/") + "/sw.js")
    except Exception as e:  # rete, certificato, risposta: qui basta dire che non si legge
        return f"non raggiungibile ({type(e).__name__})"
    m = re.search(r'VERSIONE\s*=\s*"([^"]+)"', testo)
    return m.group(1) if m else "versione non trovata in /sw.js"


def guasti(esegui: comune.Esegui, prs: list[dict]) -> list[dict]:
    """Corse con guasto d'infrastruttura sull'ultima testa delle PR rosse o annullate."""
    uscita = []
    for p in prs:
        if p["controlli"] not in ("rosso", "annullato") or not p.get("testa"):
            continue
        for c in attendi.ultime_corse(esegui, p["testa"]):
            if attendi.esito_corsa(esegui, c) == "infrastruttura":
                uscita.append({"id": c["databaseId"], "workflow": c["workflowName"], "pr": p["numero"]})
    return uscita


def osserva(esegui: comune.Esegui, url: str | None, leggi_url: Callable[[str], str],
            adesso: datetime | None) -> tuple[dict[str, str], list[dict], list[dict]]:
    s = stato.raccogli(esegui, adesso)
    voci: dict[str, str] = {}
    for p in s["pr"]:
        voci[f"pr:{p['numero']}"] = (f"PR #{p['numero']} {p['titolo'][:50]}: {'bozza' if p['bozza'] else 'pronta'}, "
                                     f"{UNIBILE.get(p['mergeable'], p['mergeable'])}, controlli {p['controlli']}")
        if p["mergeable"] == "CONFLICTING":
            voci[f"conflitto:{p['numero']}"] = f"DA FARE: PR #{p['numero']} in conflitto: «git merge origin/main» nel ramo"
    for g, t in s["tetti"].items():
        voci[f"tetto:{g}"] = f"Tetto {g}: {t['aperte']}/{t['tetto']}" + (" (PIENO)" if t["aperte"] >= t["tetto"] else "")
    for c in s["mac"]:
        voci[f"mac:{c['id']}"] = f"Corsa sui Mac {c['id']} {c['workflow']} [{c['stato']}] ramo {c['ramo']}"
    for o in s["obiettivi"]:
        voci[f"obiettivo:{o['numero']}"] = f"Obiettivo #{o['numero']} {o['titolo']}: {o['aperte']} sotto-issue aperte su {o['totali']}"
    for w in s["worktree"]:
        if w["gruppo"] in ("da_togliere", "con_modifiche", "senza_pr"):
            nome = w["percorso"].rsplit("/", 1)[-1]
            voci[f"worktree:{nome}"] = f"Worktree {nome} ({w['ramo'] or 'staccata'}): {w['gruppo'].replace('_', ' ')}"
    rotte = guasti(esegui, s["pr"])
    for g in rotte:
        voci[f"guasto:{g['id']}"] = f"DA FARE: corsa {g['id']} {g['workflow']} della PR #{g['pr']}: guasto d'infrastruttura"
    superate = annulla_superate.superate(esegui)
    for c in superate:
        voci[f"superata:{c['id']}"] = f"Corsa superata {c['id']} {c['workflow']} ramo {c['ramo']} (commit {c['commit']})"
    if url:
        voci["produzione"] = f"Produzione: {versione_produzione(url, leggi_url)}"
    return voci, rotte, superate


def main(esegui: comune.Esegui, esegui_davvero: bool = False, tutto: bool = False, json_: bool = False,
         stato_file: Path | None = None, url: str | None = None, leggi_url: Callable[[str], str] = leggi_url_vero,
         adesso: datetime | None = None) -> int:
    try:
        voci, rotte, superate = osserva(esegui, url, leggi_url, adesso)
    except comune.ErroreComando as e:
        print(f"giro: {e}", file=sys.stderr)
        return 1
    if stato_file is None:
        stato_file = prepara_cartella()
    prima = {"voci": {}, "rilanciate": []}
    if stato_file.exists():
        prima.update(json.loads(stato_file.read_text(encoding="utf-8")))
    rilanciate = [i for i in prima["rilanciate"] if f"guasto:{i}" in voci]
    azioni = []
    for g in rotte:
        if g["id"] in rilanciate:
            azioni.append(f"corsa {g['id']} già rilanciata in un giro prima: non la rilancio di nuovo, guardala a mano")
        elif esegui_davvero:
            r = esegui(["gh", "run", "rerun", str(g["id"]), "--failed"])
            if r.codice == 0:
                rilanciate.append(g["id"])
            azioni.append(f"corsa {g['id']}: " + ("rilanciata" if r.codice == 0 else f"rilancio non riuscito: {r.errore.strip()[:200]}"))
        else:
            azioni.append(f"corsa {g['id']}: da rilanciare (aggiungi --esegui)")
    for c in superate:
        if esegui_davvero:
            r = esegui(["gh", "run", "cancel", str(c["id"])])
            azioni.append(f"corsa superata {c['id']}: " + ("annullata" if r.codice == 0 else "annullamento non riuscito"))
        else:
            azioni.append(f"corsa superata {c['id']}: da annullare (aggiungi --esegui)")
    nuove = {k: v for k, v in voci.items() if prima["voci"].get(k) != v}
    sparite = {k: v for k, v in prima["voci"].items() if k not in voci}
    stato_file.parent.mkdir(parents=True, exist_ok=True)
    stato_file.write_text(json.dumps({"voci": voci, "rilanciate": rilanciate}, ensure_ascii=False, indent=1), encoding="utf-8")
    cambiato = bool(nuove or sparite)
    if json_:
        print(json.dumps({"cambiato": cambiato, "nuove": nuove, "sparite": sparite, "azioni": azioni,
                          "prova": not esegui_davvero, **({"voci": voci} if tutto else {})}, ensure_ascii=False, indent=2))
    else:
        if tutto:
            print("Tutto:")
            for v in voci.values():
                print(f"  {v}")
            if not cambiato:
                print("Nessun cambiamento dall'ultimo giro.")
        for k, v in nuove.items():
            print(f"{'~' if k in prima['voci'] else '+'} {v}")
        for v in sparite.values():
            print(f"- {v}")
        if cambiato or tutto or esegui_davvero:
            for a in azioni:
                print(f"  > {a}")
    return 10 if cambiato else 0


NOME = "giro"
AIUTO = "Procedura fissa del coordinatore: stampa solo ciò che è cambiato dal giro prima. Prova senza --esegui."
USCITE = "0 niente di nuovo; 1 errore di gh o git; 10 c'è qualcosa da guardare."


def opzioni(p) -> None:
    p.add_argument("--esegui", action="store_true", help="rilancia i guasti d'infrastruttura (una volta) e annulla le corse superate")
    p.add_argument("--tutto", action="store_true", help="stampa anche ciò che non è cambiato")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, esegui_davvero=args.esegui, tutto=args.tutto, json_=args.json,
                url=os.environ.get("SCHIERAXI_URL") or None)
