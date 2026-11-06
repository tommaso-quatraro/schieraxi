"""`attendi <PR>`: aspetta finché la PR è unita o c'è qualcosa da fare. Guarda solo l'ultima corsa di ogni workflow sul commit
in testa alla PR (una corsa vecchia rossa poi rilanciata non conta) e stampa una riga solo quando cambia qualcosa.

Codici di uscita: 0 unita; 1 errore di gh o PR chiusa senza unione; 2 conflitto con main (DIRTY); 3 rosso vero;
4 guasto d'infrastruttura (da rilanciare: corsa annullata, avvio fallito, job fallito senza passi falliti);
5 tempo scaduto; 6 tutto verde ma la PR è in bozza (revisione e poi «gh pr ready»)."""
from __future__ import annotations

import json
import sys
import time
from typing import Callable

import comune

RICHIEDE_PASSI = {"failure", "timed_out"}
INFRA = {"startup_failure", "cancelled"}
OK = {"success", "skipped", "neutral"}


def ultime_corse(esegui: comune.Esegui, commit: str) -> list[dict]:
    """L'ultima corsa di ogni workflow sul commit."""
    tutte = comune.chiama_json(esegui, ["gh", "run", "list", "--commit", commit, "--limit", "50", "--json",
                                        "databaseId,workflowName,status,conclusion,event,createdAt"]) or []
    ultime: dict[str, dict] = {}
    for c in sorted(tutte, key=lambda c: (c["createdAt"], c["databaseId"])):
        ultime[c["workflowName"]] = c
    return list(ultime.values())


def esito_corsa(esegui: comune.Esegui, corsa: dict) -> str:
    """«in corso», «verde», «rosso» o «infrastruttura»."""
    if corsa["status"] != "completed":
        return "in corso"
    esito = (corsa.get("conclusion") or "").lower()
    if esito in OK:
        return "verde"
    if esito in INFRA:
        return "infrastruttura"
    if esito not in RICHIEDE_PASSI:
        return "rosso"
    lavori = (comune.chiama_json(esegui, ["gh", "run", "view", str(corsa["databaseId"]), "--json", "jobs"]) or {}).get("jobs", [])
    falliti = [j for j in lavori if (j.get("conclusion") or "").lower() in RICHIEDE_PASSI | INFRA]
    if not falliti:
        return "infrastruttura"
    # Un passo fallito in un qualunque job = rosso vero, anche se un altro job è fermo per un guasto.
    if any((s.get("conclusion") or "").lower() in RICHIEDE_PASSI for j in falliti for s in j.get("steps") or []):
        return "rosso"
    return "infrastruttura"


def valuta(esegui: comune.Esegui, numero: int) -> tuple[str, int | None]:
    """(descrizione, codice d'uscita) oppure (descrizione, None) se si continua ad aspettare."""
    pr = comune.chiama_json(esegui, ["gh", "pr", "view", str(numero), "--json",
                                     "state,mergeable,mergeStateStatus,headRefOid,isDraft"])
    if pr["state"] == "MERGED":
        return "unita", 0
    if pr["state"] == "CLOSED":
        return "chiusa senza unione", 1
    if pr["mergeable"] == "CONFLICTING" or pr.get("mergeStateStatus") == "DIRTY":
        return "conflitto con main: serve «git merge origin/main» nel ramo", 2
    testa = pr["headRefOid"]
    corse = ultime_corse(esegui, testa)
    if not corse:
        return f"nessuna corsa ancora sul commit {testa[:7]}", None
    esiti = {c["workflowName"]: esito_corsa(esegui, c) for c in corse}
    rossi = sorted(w for w, e in esiti.items() if e == "rosso")
    if rossi:
        return f"rosso vero in: {', '.join(rossi)}", 3
    guasti = sorted(w for w, e in esiti.items() if e == "infrastruttura")
    if guasti:
        return f"guasto d'infrastruttura in: {', '.join(guasti)} (da rilanciare)", 4
    in_corso = sorted(w for w, e in esiti.items() if e == "in corso")
    if in_corso:
        return f"controlli in corso sul commit {testa[:7]}: {', '.join(in_corso)}", None
    if pr["isDraft"]:
        return "tutto verde ma in bozza: revisione e poi «gh pr ready»", 6
    return f"tutto verde sul commit {testa[:7]}: aspetto l'unione automatica", None


def main(esegui: comune.Esegui, numero: int, intervallo: float = 60, massimo: float = 3600, json_: bool = False,
         dorme: Callable[[float], None] = time.sleep, orologio: Callable[[], float] = time.monotonic) -> int:
    inizio, ultima = orologio(), None
    while True:
        try:
            descrizione, codice = valuta(esegui, numero)
        except comune.ErroreComando as e:
            descrizione, codice = f"errore: {e}", 1
        if descrizione != ultima and not json_:
            print(f"[{time.strftime('%H:%M')}] #{numero}: {descrizione}", flush=True)
        ultima = descrizione
        if codice is None and orologio() - inizio >= massimo:
            descrizione, codice = f"tempo scaduto ({int(massimo)} s); ultimo stato: {descrizione}", 5
            if not json_:
                print(f"#{numero}: {descrizione}")
        if codice is not None:
            if json_:
                print(json.dumps({"pr": numero, "codice": codice, "esito": descrizione}, ensure_ascii=False))
            elif codice == 1:
                print(f"attendi: {descrizione}", file=sys.stderr)
            return codice
        dorme(intervallo)


NOME = "attendi"
AIUTO = "Aspetta una PR: esce quando è unita o c'è da fare (solo l'ultima corsa del commit in testa)."
USCITE = ("0 unita; 1 errore o PR chiusa senza unione; 2 conflitto (DIRTY); 3 rosso vero; 4 guasto d'infrastruttura "
          "(da rilanciare); 5 tempo scaduto; 6 tutto verde ma in bozza.")


def opzioni(p) -> None:
    p.add_argument("pr", type=int, help="numero della PR")
    p.add_argument("--intervallo", type=float, default=60, help="secondi fra due controlli (predefinito 60)")
    p.add_argument("--massimo", type=float, default=3600, help="secondi al massimo prima di uscire con 5 (predefinito 3600)")
    p.add_argument("--json", action="store_true", help="stampa solo l'esito finale in JSON")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, args.pr, intervallo=args.intervallo, massimo=args.massimo, json_=args.json)
