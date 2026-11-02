"""Controllo delle PR: se cambia il codice dell'app, la PR deve dire cosa cambia per l'utente.
Uso (nei controlli di GitHub):  python script/ci/controlla_versione.py origin/main

- Modo da usare: un file proprio `fanta/novita.d/<nome-breve>.json` con {"titolo": "...", "voci": ["..."]} e SENZA
  numero. Il numero, la data e il VERSIONE di sw.js li mette il bot quando la PR si unisce (script/ci/assegna_versione.py).
  Non serve toccare fanta/novita.json né la riga VERSIONE di sw.js.
- Il modo vecchio (voce nuova scritta a mano in cima a `fanta/novita.json`, versione più alta di main) è ancora accettato
  dal controllo ma non si usa più.
Le PR che toccano solo documenti, test o strumenti di sviluppo non hanno bisogno di novità."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

CODICE = ("fanta/", "script/server/", "requirements.txt")        # cosa finisce sul server e cambia l'app
CARTELLA_D = "fanta/novita.d/"


def _assegna():
    spec = importlib.util.spec_from_file_location("assegna_versione", Path(__file__).with_name("assegna_versione.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def numero(versione: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(\.\d+)+", versione):
        raise ValueError(f"versione non valida: {versione!r} (serve un formato come 1.10)")
    return tuple(int(p) for p in versione.split("."))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def controlla(nuove: list[dict], vecchie: list[dict]) -> list[str]:
    """Modo vecchio: la prima voce di novita.json è una versione nuova, con data, titolo e voci."""
    errori = []
    versioni = [v.get("versione", "") for v in nuove]
    try:
        numeri = [numero(v) for v in versioni]
    except ValueError as e:
        return [str(e)]
    if len(set(numeri)) != len(numeri):
        errori.append("in novita.json c'è una versione ripetuta")
    if numeri != sorted(numeri, reverse=True):
        errori.append("in novita.json le versioni devono andare dalla più nuova alla più vecchia")
    prima = nuove[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?", prima.get("data", "")):
        errori.append("la versione nuova ha bisogno di una data AAAA-MM-GGTOO:MM:SS (ora italiana; la sola data AAAA-MM-GG resta valida per le voci vecchie)")
    if not prima.get("titolo") or not prima.get("voci"):
        errori.append("la versione nuova ha bisogno di un titolo e di almeno una voce di novità")
    if vecchie and numeri[0] <= numero(vecchie[0]["versione"]):
        errori.append(f"la versione è ancora {vecchie[0]['versione']}: il codice è cambiato, serve una novità: "
                      f"un file fanta/novita.d/<nome-breve>.json con titolo e voci (consigliato, il numero lo mette il bot) "
                      f"oppure una versione più alta di {vecchie[0]['versione']} in cima a fanta/novita.json")
    return errori


def controlla_d(file_d: dict[str, object], nuove: list[dict], vecchie: list[dict]) -> list[str]:
    """Modo nuovo: i file in fanta/novita.d sono validi e novita.json non ha preso un numero nuovo per conto suo."""
    errori = []
    for nome, dati in file_d.items():
        errori += _assegna().errori_file(nome, dati)
    try:
        piu_alta = bool(nuove and vecchie and numero(nuove[0].get("versione", "")) > numero(vecchie[0].get("versione", "")))
    except ValueError as e:
        return errori + [str(e)]
    if piu_alta:
        errori.append("c'è sia un file in fanta/novita.d sia una versione nuova in fanta/novita.json: usa un modo solo "
                      "(meglio il file in novita.d: togli la voce nuova da novita.json)")
    return errori


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    cambiati = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    toccati = [f for f in cambiati if f.startswith(CODICE)]
    if not toccati:
        print("Nessuna modifica al codice dell'app: non serve una versione nuova.")
        return 0
    with open("fanta/novita.json", encoding="utf-8") as f:
        nuove = json.load(f)
    try:
        vecchie = json.loads(git("show", f"{base}:fanta/novita.json"))
    except subprocess.CalledProcessError:
        vecchie = []
    if toccati == ["fanta/novita.json"] and nuove and vecchie and nuove[0].get("versione") == vecchie[0].get("versione"):
        errori = controlla(nuove, [])                 # solo testi di novità già uscite: basta che il registro resti valido
        for e in errori:
            print(" -", e)
        print("Controllo versione NON superato" if errori else "Solo testi delle novità già uscite: non serve una versione nuova.")
        return 1 if errori else 0
    nomi_d = git("diff", "--name-only", "--diff-filter=AMR", f"{base}...HEAD", "--", CARTELLA_D).splitlines()
    file_d: dict[str, object] = {}
    errori = []
    for percorso in nomi_d:
        try:
            file_d[Path(percorso).name] = json.loads(Path(percorso).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            errori.append(f"{percorso}: non è un JSON valido ({e})")
    if nomi_d:
        errori += controlla_d(file_d, nuove, vecchie)
    else:
        errori += controlla(nuove, vecchie)
    if errori:
        print("Controllo versione NON superato (file del codice modificati: " + ", ".join(toccati[:5]) + (" ..." if len(toccati) > 5 else "") + ")")
        for e in errori:
            print(" -", e)
        return 1
    for dati in (list(file_d.values()) if nomi_d else nuove[:1]):     # le voci le legge l'utente: avvisi, non errori
        for a in _assegna().avvisi_voci(dati.get("voci") if isinstance(dati, dict) else None):
            print(f"::warning title=Novità per l'utente::{a}")
    if nomi_d:
        web = any(f.startswith("fanta/web/") and f != "fanta/web/sw.js" for f in cambiati)
        print(f"Novità in {', '.join(nomi_d)}: ok. Il numero di versione lo assegna il bot quando la PR si unisce"
              + (" (e alza anche VERSIONE in sw.js, se la PR non l'ha già fatto)." if web else "."))
    else:
        print(f"Versione {nuove[0]['versione']} con le sue novità: ok (modo vecchio; il nuovo è un file in fanta/novita.d).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
