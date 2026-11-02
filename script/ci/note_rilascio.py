"""Scrive le note di una release prendendo titolo e voci dalla versione in `fanta/novita.json` (le stesse del Registro delle novità dell'app).
Uso:  python script/ci/note_rilascio.py            -> versione più recente: stampa il numero sulla prima riga, poi le note
      python script/ci/note_rilascio.py 1.9        -> solo le note di quella versione"""
from __future__ import annotations

import json
import re
import sys


def data_leggibile(data: str) -> str:
    """'2026-10-30T14:05:12' -> '30/10/2026 14:05:12' (ora italiana); la sola data -> '30/10/2026'."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}:\d{2}))?", str(data or ""))
    if not m:
        return ""
    return f"{m[3]}/{m[2]}/{m[1]}" + (f" {m[4]}" if m[4] else "")


def note(v: dict) -> str:
    quando = data_leggibile(v.get("data"))
    testa = f"_Versione {v['versione']} del {quando}_\n\n" if quando else ""
    testo = f"## {v['titolo']}\n\n" + testa + "\n".join(f"- {voce}" for voce in v["voci"]) + "\n"
    if v.get("tecnico"):
        testo += "\n### Dettagli tecnici\n\n" + "\n".join(f"- {voce}" for voce in v["tecnico"]) + "\n"
    return testo


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")      # il computer dei controlli ha l'uscita in latin-1: senza questo il segno meno (−) lo ferma
    with open("fanta/novita.json", encoding="utf-8") as f:
        elenco = json.load(f)
    if len(sys.argv) > 1:
        scelte = [v for v in elenco if v["versione"] == sys.argv[1]]
        if not scelte:
            print(f"versione {sys.argv[1]} non trovata", file=sys.stderr)
            return 1
        sys.stdout.write(note(scelte[0]))
    else:
        print(elenco[0]["versione"])
        sys.stdout.write(note(elenco[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
