"""`pr-pronta <PR>`: toglie la bozza SOLO se tutto torna. Di default fa solo la PROVA; `gh pr ready` solo con --esegui.

Controlla: PR aperta; `mergeable` esattamente uguale a «MERGEABLE» (CONFLICTING, UNKNOWN o altro = no); ramo non indietro
rispetto a main; ultima corsa di ogni workflow sul commit in testa verde; descrizione, revisione e novità con le funzioni di
script/ci/controlla_pr.py (la revisione come se la PR fosse già pronta); coerenza web-iPhone con script/coerenza.py
--controlla sui file della PR (se la PR tocca i dati della coerenza); «Foto da fare: …» nella descrizione se la PR tocca ios/.
Se uno dei due controlli non c'è su questo main, rifiuta: «controllo non disponibile su questo main».
Caso a parte (#476): è rosso solo il job «ambito» e la descrizione ATTUALE va bene (controlla_pr.py senza problemi, aree di
controlla_ambito.py che coprono i file). Il job ha letto la descrizione di prima e un «Re-run» la rilegge uguale: lo dice e
suggerisce update-branch (ramo indietro) o un push; con --esegui, se l'unico altro motivo è il ramo indietro, fa da solo
l'update-branch su GitHub ed esce con 4.
Codici di uscita: 0 tutto torna (con --esegui: bozza tolta; PR già pronta: niente da fare); 1 almeno un motivo di rifiuto
(stampati tutti); 3 errore di gh o git; 4 controlli ripartiti con l'update-branch, riprova fra qualche minuto."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Callable

import attendi
import comune

FILE_COERENZA = ("script/coerenza.py", "docs/coerenza", "docs/COERENZA-WEB-IPHONE.md")
NON_DISPONIBILE = "controllo non disponibile su questo main"


def _carica_da_ci(nome: str):
    """Uno script di script/ci di main come modulo, o None se su questo main non c'è."""
    percorso = comune.RADICE / "script" / "ci" / f"{nome}.py"
    if not percorso.exists():
        return None
    spec = importlib.util.spec_from_file_location(nome, percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def carica_controlli_pr():
    return _carica_da_ci("controlla_pr")


def carica_controlli_ambito():
    return _carica_da_ci("controlla_ambito")


def _tocca_coerenza(file: list[str]) -> bool:
    return any(f == p or f.startswith(p + "/") for f in file for p in FILE_COERENZA)


def _copia_dal_commit(esegui: comune.Esegui, testa: str, percorso: str, base: Path) -> None:
    """Scrive in `base` un file del commit della PR, da LEGGERE soltanto (mai eseguire). Percorsi fuori da `base` no."""
    destinazione = (base / percorso).resolve()
    if not destinazione.is_relative_to(base.resolve()):
        raise comune.ErroreComando(f"percorso inatteso nel commit della PR: {percorso}")
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(comune.chiama(esegui, ["git", "show", f"{testa}:{percorso}"]), encoding="utf-8")


def coerenza_vera(esegui: comune.Esegui, testa: str, file: list[str]) -> list[str]:
    """`coerenza.py --controlla` sui DATI della PR (commit in testa), copiati in una cartella temporanea. Lo script è SEMPRE
    quello di main (comune.RADICE): il codice di una PR, anche da un fork, non si esegue mai. [] se va bene o non serve."""
    if not _tocca_coerenza(file):
        return []
    dati = [p for p in FILE_COERENZA if not p.endswith(".py")]
    elenco = comune.chiama(esegui, ["git", "ls-tree", "-r", "--name-only", testa, "--", *dati]).splitlines()
    with tempfile.TemporaryDirectory(prefix="pr-pronta-") as cartella:
        base = Path(cartella)
        for percorso in (p.strip() for p in elenco if p.strip()):
            _copia_dal_commit(esegui, testa, percorso, base)
        script = comune.RADICE / "script" / "coerenza.py"
        r = esegui([sys.executable, str(script), "--controlla", "--radice", str(base)])
    if r.codice == 0:
        return []
    return [f"coerenza web-iPhone: {' '.join((r.uscita + ' ' + r.errore).split())[:400]}"]


def _test_della_pr(esegui: comune.Esegui, testa: str, file: list[tuple], cartella: Path) -> None:
    """Copia nella cartella i file di test aggiunti o cambiati dalla PR (per il controllo «test che leggono una novità per nome»,
    che ne legge solo l'albero sintattico: nessun file della PR si esegue)."""
    for voce in file:
        stato, percorso = voce[0], voce[-1]
        if stato != "removed" and percorso.startswith("tests/") and percorso.endswith(".py"):
            _copia_dal_commit(esegui, testa, percorso, cartella)


def _foto_scritte(corpo: str) -> bool:
    corpo = re.sub(r"<!--.*?(?:-->|\Z)", "", corpo or "", flags=re.S)
    return bool(re.search(r"^\W*foto (da fare|prima dell'unione)\s*:", corpo, re.I | re.M))


def _solo_ambito_vecchio(esegui: comune.Esegui, non_verdi: list[tuple], pr: dict, file: list[str], controlli_ambito) -> bool:
    """Il solo controllo rosso è il job «ambito» e le aree della descrizione ATTUALE coprono i file della PR?
    (Il job legge la descrizione al momento della corsa: corretta dopo, resta rosso finché i controlli non ripartono.)"""
    if controlli_ambito is None or len(non_verdi) != 1 or non_verdi[0][1] != "rosso":
        return False
    lavori = (comune.chiama_json(esegui, ["gh", "run", "view", str(non_verdi[0][0]["databaseId"]), "--json", "jobs"])
              or {}).get("jobs", [])
    falliti = {j.get("name") for j in lavori if (j.get("conclusion") or "").lower() not in attendi.OK}
    if falliti != {"ambito"}:
        return False
    autore = (pr.get("author") or {}).get("login", "")
    if controlli_ambito.esente(autore, file):
        return True
    aree = controlli_ambito.aree(pr.get("body") or "")
    return bool(aree) and not controlli_ambito.fuori(file, aree)


def valuta(esegui: comune.Esegui, numero: int, controlli_pr, controlla_coerenza: Callable | None,
           controlli_ambito=None) -> tuple[dict, list[str], list[str], dict | None]:
    """(pr, motivi, avvisi, ripartenza): `ripartenza` non è None quando è rosso solo l'«ambito» della descrizione vecchia."""
    pr = comune.chiama_json(esegui, ["gh", "pr", "view", str(numero), "--json",
                                     "number,state,isDraft,mergeable,mergeStateStatus,headRefOid,body,author"])
    motivi: list[str] = []
    avvisi: list[str] = []
    ambito_vecchio = False
    if pr["state"] != "OPEN":
        motivi.append(f"la PR non è aperta (stato {pr['state']})")
    mergeable = pr.get("mergeable")
    if mergeable != "MERGEABLE":
        spiegazione = {"CONFLICTING": "conflitto con main: «git merge origin/main» nel ramo",
                       "UNKNOWN": "GitHub non l'ha ancora calcolato: riprova fra un minuto"}.get(mergeable, "valore inatteso")
        motivi.append(f"mergeable è «{mergeable}», non «MERGEABLE» ({spiegazione})")
    testa = pr["headRefOid"]
    # Qui GitHub non dà «BEHIND» (main non chiede rami aggiornati): si conta quanti commit di main mancano al ramo.
    dietro = comune.chiama(esegui, ["gh", "api", f"repos/{{owner}}/{{repo}}/compare/main...{testa}", "--jq", ".behind_by"]).strip()
    if not dietro.isdigit():
        motivi.append(f"non so se il ramo è indietro rispetto a main (risposta inattesa: «{dietro[:40]}»)")
    elif int(dietro) > 0:
        motivi.append(f"il ramo è indietro di {dietro} commit rispetto a main: «git merge origin/main» nel ramo e push, "
                      "poi aspetta i controlli")
    corse = attendi.ultime_corse(esegui, testa)
    if not corse:
        motivi.append(f"nessuna corsa dei controlli sul commit in testa {testa[:7]}")
    non_verdi = [(c, e) for c, e in ((c, attendi.esito_corsa(esegui, c)) for c in corse) if e != "verde"]
    for c, esito in non_verdi:
        motivi.append(f"controlli: {c['workflowName']} è «{esito}» sul commit in testa {testa[:7]}"
                      + (" (guasto d'infrastruttura: da rilanciare)" if esito == "infrastruttura" else ""))
    file = [(f["status"], f["previous_filename"], f["filename"]) if f.get("previous_filename") else (f["status"], f["filename"])
            for f in comune.chiama_json(esegui, ["gh", "api", f"repos/{{owner}}/{{repo}}/pulls/{numero}/files", "--paginate"]) or []]
    percorsi = [p for voce in file for p in voce[1:]]
    serve_commit = _tocca_coerenza(percorsi) or any(p.startswith("tests/") for p in percorsi)
    if serve_commit:
        comune.chiama(esegui, ["git", "fetch", "origin", f"refs/pull/{numero}/head"])
    if controlli_pr is None:
        motivi.append(f"descrizione, revisione e novità: {NON_DISPONIBILE} (manca script/ci/controlla_pr.py)")
    else:
        with tempfile.TemporaryDirectory(prefix="pr-pronta-test-") as cartella:
            _test_della_pr(esegui, testa, file, Path(cartella))
            problemi, avvisi_pr = controlli_pr.controlla(pr.get("body") or "", False, (pr.get("author") or {}).get("login", ""),
                                                         file, str(Path(cartella) / "tests"))
        motivi += problemi
        avvisi += avvisi_pr
        if not problemi and _solo_ambito_vecchio(esegui, non_verdi, pr, [voce[-1] for voce in file], controlli_ambito):
            motivi.remove(next(m for m in motivi if m.startswith("controlli: ")))
            ambito_vecchio = True
    if controlla_coerenza is None:
        if _tocca_coerenza(percorsi) or not (comune.RADICE / "script" / "coerenza.py").exists():
            motivi.append(f"coerenza web-iPhone: {NON_DISPONIBILE} (manca script/coerenza.py)")
    else:
        motivi += controlla_coerenza(esegui, testa, percorsi)
    if any(p.startswith("ios/") for p in percorsi) and not _foto_scritte(pr.get("body") or ""):
        motivi.append("la PR tocca ios/ ma la descrizione non ha «Foto da fare: <schermate>» "
                      "(le ricava «squadra.py foto <PR>»)")
    ripartenza = None
    if ambito_vecchio:
        indietro = dietro.isdigit() and int(dietro) > 0
        come = ("porta il ramo in pari con main da GitHub (update-branch: «pr-pronta --esegui» lo fa da solo)" if indietro
                else "un push nel ramo, anche un commit vuoto («git commit --allow-empty» e «git push»)")
        motivi.insert(0, f"controlli: è rosso solo il job «ambito», che ha letto la descrizione di prima; la descrizione attuale "
                         f"va bene. Un «Re-run» rilegge quella vecchia: per rifare i controlli {come}")
        # update-branch da solo solo se i motivi sono esattamente due: questo e il ramo indietro.
        ripartenza = {"update_branch": indietro and len(motivi) == 2}
    return pr, motivi, avvisi, ripartenza


def main(esegui: comune.Esegui, numero: int, esegui_davvero: bool = False, json_: bool = False, controlli_pr=None,
         controlla_coerenza: Callable | None = None, controlli_ambito=None) -> int:
    if controlli_pr is None:
        controlli_pr = carica_controlli_pr()
    if controlli_ambito is None:
        controlli_ambito = carica_controlli_ambito()
    if controlla_coerenza is None and (comune.RADICE / "script" / "coerenza.py").exists():
        controlla_coerenza = coerenza_vera
    try:
        pr, motivi, avvisi, ripartenza = valuta(esegui, numero, controlli_pr, controlla_coerenza, controlli_ambito)
    except comune.ErroreComando as e:
        print(f"pr-pronta: {e}", file=sys.stderr)
        return 3
    tolta = ripartiti = False
    nota = ""
    if ripartenza and ripartenza["update_branch"] and esegui_davvero:
        r = esegui(["gh", "api", "-X", "PUT", f"repos/{{owner}}/{{repo}}/pulls/{numero}/update-branch"])
        if r.codice != 0:
            print(f"pr-pronta: update-branch non riuscito: {(r.errore or r.uscita).strip()[:300]}", file=sys.stderr)
            return 3
        ripartiti, nota = True, ("ramo portato in pari con main da GitHub: i controlli ripartono con la descrizione attuale, "
                                 "riprova fra qualche minuto")
    elif not motivi:
        if not pr["isDraft"]:
            nota = "la PR è già fuori dalla bozza: niente da fare"
        elif esegui_davvero:
            r = esegui(["gh", "pr", "ready", str(numero)])
            if r.codice != 0:
                print(f"pr-pronta: «gh pr ready» non riuscito: {r.errore.strip()[:300]}", file=sys.stderr)
                return 3
            tolta, nota = True, "bozza tolta"
        else:
            nota = "PROVA: tutto torna. Per togliere la bozza: aggiungi --esegui"
    if json_:
        print(json.dumps({"pr": numero, "pronta": not motivi, "motivi": motivi, "avvisi": avvisi, "prova": not esegui_davvero,
                          "bozza_tolta": tolta, "controlli_ripartiti": ripartiti, "nota": nota},
                         ensure_ascii=False, indent=2))
    else:
        if ripartiti:
            print(f"PR #{numero}: {nota}.")
        elif motivi:
            print(f"PR #{numero}: NON pronta. Motivi ({len(motivi)}):")
            for m in motivi:
                print(f"  - {m}")
        else:
            print(f"PR #{numero}: {nota}.")
        for a in avvisi:
            print(f"  avviso: {a}")
    if ripartiti:
        return RIPARTITI
    return 1 if motivi else 0


RIPARTITI = 4
NOME = "pr-pronta"
AIUTO = "Toglie la bozza a una PR solo se tutto torna (prova senza --esegui); se no stampa ogni motivo."
USCITE = ("0 tutto torna (con --esegui: bozza tolta); 1 almeno un motivo di rifiuto; 3 errore di gh o git; "
          "4 controlli ripartiti, riprova fra qualche minuto (con --esegui, quando era rosso solo il job «ambito» sulla "
          "descrizione vecchia e il ramo era indietro: fatto l'update-branch su GitHub).")


def opzioni(p) -> None:
    p.add_argument("pr", type=int, help="numero della PR")
    p.add_argument("--esegui", action="store_true",
                   help="toglie davvero la bozza con «gh pr ready», oppure fa l'update-branch nel caso dell'«ambito» "
                        "vecchio (senza: solo prova)")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui) -> int:
    return main(esegui, args.pr, esegui_davvero=args.esegui, json_=args.json)
