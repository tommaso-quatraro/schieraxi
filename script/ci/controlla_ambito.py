"""Controllo delle PR: la PR resta nelle aree che dichiara (contro il lavoro fuori piano).
Uso (job «ambito» di test.yml):  git diff --name-only ... | python script/ci/controlla_ambito.py
con le variabili d'ambiente AUTORE (login di chi ha aperto la PR) e CORPO (descrizione della PR).

- La descrizione ha una riga «Aree: fanta/web, tests, docs» (cartelle o file, separati da virgole; `*` ammesso).
- Ogni file cambiato deve stare in una delle aree. `fanta/novita.d/` è sempre ammessa (la chiede il job «versione»).
- Esenti: le PR dei bot (nome che finisce con «[bot]») e quelle di soli documenti (file .md o cartella docs/).
Esce con 1 e scrive gli avvisi (formato di GitHub Actions) se la riga manca o un file sta fuori. Il testo della PR arriva
solo come variabile d'ambiente: non passa mai dentro un comando."""
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


def esente(autore: str, file: list[str]) -> bool:
    if (autore or "").endswith("[bot]"):
        return True
    return bool(file) and all(f.startswith("docs/") or f.lower().endswith(".md") for f in file)


def main(autore: str, corpo: str, file: list[str]) -> int:
    file = [f.strip() for f in file if f.strip()]
    if esente(autore, file):
        print("Ambito: PR esente (bot o soli documenti).")
        return 0
    elenco = aree(corpo)
    if not elenco:
        print("::warning title=Ambito::Manca la riga «Aree: …» nella descrizione della PR "
              "(esempio: «Aree: fanta/web, tests, docs»).")
        return 1
    usciti = fuori(file, elenco)
    if usciti:
        for f in usciti:
            print(f"::warning file={f},title=Ambito::{f} è fuori dalle aree dichiarate ({', '.join(elenco)}).")
        print(f"Ambito: {len(usciti)} file fuori da «Aree: {', '.join(elenco)}». Aggiungi l'area o sposta il lavoro in un'altra PR.")
        return 1
    print(f"Ambito: tutti i {len(file)} file stanno in «Aree: {', '.join(elenco)}».")
    return 0


if __name__ == "__main__":
    sys.exit(main(os.environ.get("AUTORE", ""), os.environ.get("CORPO", ""), sys.stdin.read().splitlines()))
