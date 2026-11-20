"""`foto <PR>` (o `foto --da <commit>`): dai file iOS cambiati ricava le schermate da fotografare (foto.json) e stampa il comando
`gh workflow run screenshot.yml …`. Lo lancia solo con --lancia (solo il fotografo). Fotografa il ramo della PR se è aperta,
main se è unita o con --da; --ref sceglie un altro ramo. Per un file senza regola a mano stretta le schermate vengono dal codice
Swift (grafo_ios.py, #505); --spiega dice per ogni file come sono state scelte.

Codici di uscita: 0 fatto (anche se non c'è nulla da fotografare); 1 errore di gh o git, o PR da un fork o chiusa senza
unione; 3 ci sono file iOS senza schermata
in foto.json (avviso su stderr: il comando stampato non li copre)."""
from __future__ import annotations

import json
import re
import shlex
import sys
from functools import lru_cache

import aree
import comune
import grafo_ios


def _corrisponde(file: str, percorsi: list[str]) -> bool:
    return any(aree.corrisponde(file, p) for p in percorsi)


def scene_di_screenshot() -> list[str]:
    """I nomi delle schermate (variabile TUTTE di ios/scripts/screenshot.sh, letto e mai cambiato)."""
    testo = (comune.RADICE / "ios" / "scripts" / "screenshot.sh").read_text(encoding="utf-8")
    trovato = re.search(r"^TUTTE=\((.*?)\)", testo, re.S | re.M)
    return trovato.group(1).split() if trovato else []


@lru_cache(maxsize=1)
def grafo_del_repository() -> grafo_ios.Grafo:
    return grafo_ios.Grafo(grafo_ios.leggi(comune.RADICE))


def _nomi(dati: dict, schermate) -> list[str]:
    return list(dati["principali"] if schermate == "principali" else schermate)


def scegli(file: str, dati: dict, grafo: grafo_ios.Grafo, scene: list[str]) -> dict:
    """Come si sceglie per un file: «ignora», «widget», «regola» (a mano, stretta: vince), «grafo» (viste radice raggiunte,
    al massimo «soglia_radici»), «ripiego» (regola larga), «senza». Restituisce modo, schermate e perché."""
    if not file.startswith("ios/") or _corrisponde(file, dati["ignora"]):
        return {"modo": "ignora", "schermate": [], "perche": "non cambia l'aspetto"}
    if _corrisponde(file, dati["widget"]):
        return {"modo": "widget", "schermate": [], "perche": "foto dei widget"}
    regola = next((r for r in dati["regole"] if _corrisponde(file, r["percorsi"])), None)
    radici_scena: dict[str, list[str]] = {}
    for s in scene:
        for modello, tipi in dati.get("radici", {}).items():
            if aree.corrisponde(s, modello):
                for t in tipi:
                    radici_scena.setdefault(t, []).append(s)
    # le viste radice dichiarate nel file stesso (LegaExtra.swift tiene StatoDatiView, Demo.swift ProvaMarchio): cambiarlo
    # può cambiare proprio quelle schermate, che una regola a mano o larga non sempre comprende
    proprie = grafo.radici_dichiarate(file, set(radici_scena))

    def con_proprie(modo: str, perche: str) -> dict:
        scelte = _nomi(dati, regola["schermate"])
        if proprie:
            scelte += [s for s in scene if s not in scelte and any(s in radici_scena[t] for t in proprie)]
            perche += f", più le schermate delle viste radice dichiarate nel file: {', '.join(proprie)}"
        return {"modo": modo, "schermate": scelte, "perche": perche}

    if regola is not None and not regola.get("ripiego"):
        return con_proprie("regola", "regola a mano di foto.json")
    # i contenitori (RadiceView...) mostrano le loro parti su ogni schermata: arrivarci vale «troppe radici»
    contenitori = set(dati.get("contenitori", []))
    trovate = grafo.radici(file, set(radici_scena) | contenitori, set(dati.get("barriere", [])),
                           set(dati.get("annidate", [])))
    soglia = dati.get("soglia_radici", 4)
    dentro = [t for t in trovate if t in contenitori]
    if dentro and regola is not None:
        strade = "; ".join(" ← ".join(trovate[t]) for t in dentro)
        return con_proprie("ripiego", f"il codice arriva a un contenitore di tutte le schermate ({strade}): regola larga")
    if not dentro and 0 < len(trovate) <= soglia:
        scelte = {s for t in trovate for s in radici_scena[t]}
        strade = "; ".join(" ← ".join(strada) for strada in trovate.values())
        return {"modo": "grafo", "schermate": [s for s in scene if s in scelte], "perche": f"dal codice: {strade}"}
    motivo = (f"il codice arriva a {len(trovate)} viste radice (più di {soglia})" if trovate
              else "il codice non arriva a nessuna vista radice")
    if regola is not None:
        return con_proprie("ripiego", f"{motivo}: regola larga")
    return {"modo": "senza", "schermate": [], "perche": motivo}


def schermate(file: list[str], dati: dict | None = None, grafo: grafo_ios.Grafo | None = None,
              scene: list[str] | None = None) -> dict:
    dati = dati if dati is not None else comune.leggi_json("foto.json")
    scelte: list[str] = []
    widget, senza, perche = False, [], {}
    for f in file:
        if not f.startswith("ios/") or _corrisponde(f, dati["ignora"]):
            continue
        if grafo is None and not _corrisponde(f, dati["widget"]):
            grafo = grafo_del_repository()
        if scene is None:
            scene = scene_di_screenshot()
        s = scegli(f, dati, grafo, scene)
        perche[f] = f"{s['modo']}: {s['perche']}"
        if s["modo"] == "widget":
            widget = True
        elif s["modo"] == "senza":
            senza.append(f)
        else:
            scelte += [n for n in s["schermate"] if n not in scelte]
    return {"schermate": scelte, "widget": widget, "senza": senza, "perche": perche}


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
         dispositivi: str = "iphone", json_: bool = False, spiega: bool = False) -> int:
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
    if spiega and not json_:
        for f, motivo in esito["perche"].items():
            print(f"  {f}: {motivo}")
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
    p.add_argument("--spiega", action="store_true",
                   help="per ogni file: regola a mano, codice (con la strada fino alla vista radice) o regola larga")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, pr=args.pr, da=args.da, lancia=args.lancia, ref=args.ref, dispositivi=args.dispositivi,
                json_=args.json, spiega=args.spiega)
