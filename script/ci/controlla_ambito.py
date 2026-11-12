"""Controllo delle PR: la PR resta nelle aree che dichiara (contro il lavoro fuori piano).
Uso (job «ambito» di test.yml):  git diff --name-only ... | python script/ci/controlla_ambito.py
con le variabili d'ambiente AUTORE (login di chi ha aperto la PR) e CORPO (descrizione della PR).

- La descrizione ha una riga «Aree: fanta/web, tests, docs» (cartelle o file, separati da virgole; `*` ammesso).
- Ogni file cambiato deve stare in una delle aree. `fanta/novita.d/` è sempre ammessa (la chiede il job «versione»).
- Esenti: le PR dei bot (nome che finisce con «[bot]») e quelle di soli documenti (file .md o cartella docs/;
  NON sono documenti `.claude/`, `.github/` e i `CLAUDE.md`: funzione `solo_documenti`, usata anche da controlla_pr.py).
Bloccante: se esce con 1 il job «ambito» è rosso e «unisci» non parte.
Esce con 1 e scrive gli errori (formato di GitHub Actions) se la riga manca o un file sta fuori. Il testo della PR arriva
solo come variabile d'ambiente: non passa mai dentro un comando.

Con `--dimensione` (#620) legge invece `git diff --numstat` e avvisa, senza mai bloccare, se la PR cambia più di 600 righe
senza contare test e file generati (NON_CONTANO)."""
from __future__ import annotations

import fnmatch
import os
import re
import sys

SEMPRE = ("fanta/novita.d",)


def aree(corpo: str) -> list[str]:
    """Le aree della prima riga «Aree:» fuori dai commenti HTML (quelli del modello di PR)."""
    corpo = re.sub(r"<!--.*?-->", "", corpo or "", flags=re.S)
    m = re.search(r"^[ \t]*aree[ \t]*:[ \t]*(.*?)[ \t\r]*$", corpo, re.I | re.M)
    if not m:
        return []
    voci = (v.strip().strip("`").strip().rstrip("/") for v in m.group(1).split(","))
    return [v for v in voci if v]


def _dentro(file: str, area: str) -> bool:
    if any(c in area for c in "*?["):
        return fnmatch.fnmatchcase(file, area)
    return file == area or file.startswith(area + "/")


def fuori(file: list[str], elenco: list[str]) -> list[str]:
    ammesse = list(elenco) + list(SEMPRE)
    return [f for f in file if not any(_dentro(f, a) for a in ammesse)]


NON_DOCUMENTI = (".claude/", ".github/")      # regole della revisione IA (skill, agenti) e CI: anche se sono file .md


def documento(file: str) -> bool:
    """Un file di soli documenti: in docs/ o un .md, ma non in .claude/ o .github/ e non un CLAUDE.md (regole del lavoro)."""
    if file.startswith(NON_DOCUMENTI) or file.rsplit("/", 1)[-1] == "CLAUDE.md":
        return False
    return file.startswith("docs/") or file.lower().endswith(".md")


def solo_documenti(file) -> bool:
    """Definizione unica di «PR di soli documenti»: la usa anche controlla_pr.py (per percorso, dalla stessa cartella)."""
    file = list(file)
    return bool(file) and all(documento(f) for f in file)


def esente(autore: str, file: list[str]) -> bool:
    if (autore or "").endswith("[bot]"):
        return True
    return solo_documenti(file)


# ---------------------------------------------------------------- dimensione (#620): solo un avviso
SOGLIA_RIGHE = 600
# Non contano: i test e i file generati da uno script (non li scrive una persona, e chi rivede non li legge riga per riga).
NON_CONTANO = ("tests/*", "ios/Tests/*", "fanta/web/testi.js", "ios/Sources/Support/Catalogo/*", "ios/fotografie/*",
               "docs/COERENZA-WEB-IPHONE.md", "docs/SOTTO-IL-COFANO.md", "docs/openapi.json", "THIRD-PARTY-NOTICES.md",
               "requirements.txt", "requirements-dev.txt", "fanta/novita.json")


def _percorso_nuovo(campo: str) -> str:
    """Il percorso dopo un rinomina di `git diff --numstat` («a/{x => y}/b» o «x => y»); gli altri come sono."""
    m = re.fullmatch(r"(.*)\{(.*) => (.*)\}(.*)", campo)
    if m:
        return re.sub(r"/{2,}", "/", m.group(1) + m.group(3) + m.group(4)).lstrip("/")
    return campo.split(" => ", 1)[1] if " => " in campo else campo


def righe_cambiate(numstat: str) -> tuple[int, list[str]]:
    """Righe aggiunte più tolte (righe di `git diff --numstat`), senza i file di NON_CONTANO; e i file contati, in ordine.
    I file binari («-» al posto dei numeri) non hanno righe e non si contano."""
    totale, contati = 0, []
    for riga in (numstat or "").splitlines():
        parti = riga.split("\t", 2)
        if len(parti) != 3:
            continue
        file = _percorso_nuovo(parti[2].strip())
        if any(fnmatch.fnmatchcase(file, schema) for schema in NON_CONTANO):
            continue
        if parti[0].isdigit() and parti[1].isdigit():
            totale += int(parti[0]) + int(parti[1])
            contati.append(file)
    return totale, contati


def dimensione(numstat: str) -> int:
    """Avviso di GitHub Actions se la PR cambia più di SOGLIA_RIGHE righe (senza test e file generati). Esce sempre con 0."""
    righe, _ = righe_cambiate(numstat)
    if righe > SOGLIA_RIGHE:
        print(f"::warning title=Dimensione::La PR cambia {righe} righe (senza test e file generati), oltre {SOGLIA_RIGHE}: "
              "una PR più piccola si rivede meglio. Se non si può dividere, scrivi il perché nella descrizione.")
    else:
        print(f"Dimensione: {righe} righe cambiate (senza test e file generati), entro {SOGLIA_RIGHE}.")
    return 0


def main(autore: str, corpo: str, file: list[str]) -> int:
    file = [f.strip() for f in file if f.strip()]
    if esente(autore, file):
        print("Ambito: PR esente (bot o soli documenti).")
        return 0
    elenco = aree(corpo)
    if not elenco:
        print("::error title=Ambito::Manca la riga «Aree: …» nella descrizione della PR "
              "(esempio: «Aree: fanta/web, tests, docs»).")
        return 1
    usciti = fuori(file, elenco)
    if usciti:
        for f in usciti:
            print(f"::error file={f},title=Ambito::{f} è fuori dalle aree dichiarate ({', '.join(elenco)}).")
        print(f"Ambito: {len(usciti)} file fuori da «Aree: {', '.join(elenco)}». Aggiungi l'area o sposta il lavoro in un'altra PR.")
        return 1
    print(f"Ambito: tutti i {len(file)} file stanno in «Aree: {', '.join(elenco)}».")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:] == ["--dimensione"]:
        sys.exit(dimensione(sys.stdin.read()))
    sys.exit(main(os.environ.get("AUTORE", ""), os.environ.get("CORPO", ""), sys.stdin.read().splitlines()))
