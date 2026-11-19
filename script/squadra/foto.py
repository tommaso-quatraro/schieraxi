"""`foto <PR>` (o `foto --da <commit>`): dai file iOS cambiati ricava le schermate da fotografare (foto.json) e stampa il comando
`gh workflow run screenshot.yml …`. Lo lancia solo con --lancia (solo il fotografo). Fotografa il ramo della PR se è aperta,
main se è unita o con --da; --ref sceglie un altro ramo.

Codici di uscita: 0 fatto (anche se non c'è nulla da fotografare); 1 errore di gh o git, o PR da un fork o chiusa senza
unione; 3 ci sono file iOS senza schermata
in foto.json (avviso su stderr: il comando stampato non li copre)."""
from __future__ import annotations

import json
import shlex
import sys

import aree
import comune


def _corrisponde(file: str, percorsi: list[str]) -> bool:
    return any(aree.corrisponde(file, p) for p in percorsi)


def schermate(file: list[str]) -> dict:
    dati = comune.leggi_json("foto.json")
    scelte: list[str] = []
    widget, senza = False, []
    for f in file:
        if not f.startswith("ios/") or _corrisponde(f, dati["ignora"]):
            continue
        if _corrisponde(f, dati["widget"]):
            widget = True
            continue
        regola = next((r for r in dati["regole"] if _corrisponde(f, r["percorsi"])), None)
        if regola is None:
            senza.append(f)
            continue
        nomi = dati["principali"] if regola["schermate"] == "principali" else regola["schermate"]
        scelte += [n for n in nomi if n not in scelte]
    return {"schermate": scelte, "widget": widget, "senza": senza}


def comando(esito: dict, ref: str = "main", dispositivi: str = "iphone") -> list[str]:
    c = ["gh", "workflow", "run", "screenshot.yml", "--ref", ref, "-f", f"dispositivi={dispositivi}"]
    if esito["schermate"]:
        c += ["-f", "schermate=" + " ".join(esito["schermate"])]
    if esito["widget"]:
        c += ["-f", "widget=si"]
    return c


def _per_persone(c: list[str]) -> str:
    return " ".join(f'{a.split("=", 1)[0]}="{a.split("=", 1)[1]}"' if a.startswith("schermate=") else shlex.quote(a) for a in c)


def file_cambiati(esegui: comune.Esegui, pr: int | None, da: str | None) -> tuple[list[str], str, str]:
    """File cambiati, ramo da fotografare (quello della PR se è ancora aperta, #717, altrimenti main) e, se la PR non si può
    fotografare (da un fork o chiusa senza unione), il perché."""
    if pr is not None:
        dati = comune.chiama_json(esegui, ["gh", "pr", "view", str(pr), "--json",
                                            "files,headRefName,state,isCrossRepository"]) or {}
        stato, ramo, perche = dati.get("state"), None, ""
        if stato == "CLOSED":
            perche = f"la PR {pr} è chiusa senza unione: niente da fotografare"
        elif stato == "OPEN" and dati.get("isCrossRepository"):
            perche = "PR da un fork: le foto si lanciano dal ramo di questo repository"
        elif stato == "OPEN":
            ramo = dati.get("headRefName")
        return [f["path"] for f in dati.get("files") or []], ramo or "main", perche
    return [r for r in comune.chiama(esegui, ["git", "diff", "--name-only", f"{da}..origin/main", "--", "ios/"]).splitlines()
            if r.strip()], "main", ""


def main(esegui: comune.Esegui, pr: int | None = None, da: str | None = None, lancia: bool = False, ref: str | None = None,
         dispositivi: str = "iphone", json_: bool = False) -> int:
    try:
        file, ramo, perche = file_cambiati(esegui, pr, da)
        esito = schermate(file)
    except comune.ErroreComando as e:
        print(f"foto: {e}", file=sys.stderr)
        return 1
    if ref is None and perche:
        print(f"foto: {perche} (con --ref si sceglie un ramo a mano).", file=sys.stderr)
        return 1
    ref = ref or ramo
    da_fare = bool(esito["schermate"] or esito["widget"])
    c = comando(esito, ref, dispositivi) if da_fare else []
    lanciato = False
    if lancia and da_fare:
        r = esegui(c)
        if r.codice != 0:
            print(f"foto: il lancio non è riuscito: {(r.errore or r.uscita).strip()[:300]}", file=sys.stderr)
            return 1
        lanciato = True
    if json_:
        print(json.dumps({**esito, "comando": c, "lanciato": lanciato}, ensure_ascii=False, indent=2))
    elif not da_fare:
        print("Nessuna schermata da fotografare.")
    else:
        print(f"Foto da fare: {' '.join(esito['schermate']) or '(solo widget)'}" + (" + widget" if esito["widget"] else ""))
        print(("Lanciato: " if lanciato else "Comando (aggiungi --lancia per lanciarlo): ") + _per_persone(c))
    for f in esito["senza"]:
        print(f"foto: attenzione, {f} non ha una schermata in script/squadra/foto.json: aggiungi una regola.", file=sys.stderr)
    return 3 if esito["senza"] else 0


NOME = "foto"
AIUTO = "Schermate da fotografare per una PR (o dai commit dopo --da) e comando screenshot.yml; lo lancia solo con --lancia."
USCITE = "0 fatto; 1 errore di gh o git, lancio non riuscito, PR da un fork o chiusa senza unione; 3 file iOS senza schermata in foto.json (avviso)."


def opzioni(p) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("pr", type=int, nargs="?", help="numero della PR")
    g.add_argument("--da", help="commit dell'ultimo giro di foto: guarda i file iOS cambiati da lì a origin/main")
    p.add_argument("--lancia", action="store_true", help="lancia davvero screenshot.yml (solo il fotografo)")
    p.add_argument("--ref", default=None, help="ramo su cui fotografare (predefinito: quello della PR se è aperta, altrimenti main)")
    p.add_argument("--dispositivi", default="iphone", choices=["iphone", "ipad", "tutti"], help="predefinito: iphone")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, pr=args.pr, da=args.da, lancia=args.lancia, ref=args.ref, dispositivi=args.dispositivi,
                json_=args.json)
