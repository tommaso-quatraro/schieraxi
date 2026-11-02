"""Misura il riconoscimento dei nomi (fanta/nomi.py) sul corpus di prova (tests/corpus_nomi.py).

    .venv\\Scripts\\python.exe prove\\misura_nomi.py            # listone inventato (lo stesso dei test)
    .venv\\Scripts\\python.exe prove\\misura_nomi.py --vero     # anche il listone salvato in dati/cache (solo in locale)
    ... --dettagli                                             # esiti per tipo di variante

Stampa solo percentuali e conteggi: nessun nome di calciatore finisce a schermo o in un file.
"""
from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "tests"))

from corpus_nomi import genera, listone_inventato, misura, tabella  # noqa: E402

from fanta import listone  # noqa: E402
from fanta.nomi import Indice  # noqa: E402


def _stampa(titolo: str, calciatori: list, dettagli: bool) -> None:
    prove = genera(calciatori)
    veri, finti, per_tipo = misura(Indice(calciatori), prove)
    print(f"== {titolo} ({len(calciatori)} calciatori)")
    print(tabella(veri, finti))
    if dettagli:
        for tipo, conta in sorted(per_tipo.items()):
            print(f"  {tipo:26} " + ", ".join(f"{k} {v}" for k, v in conta.most_common()))
    print()


def main() -> None:
    dettagli = "--dettagli" in sys.argv
    _stampa("listone inventato", listone_inventato(), dettagli)
    if "--vero" in sys.argv:
        cache = listone._leggi_cache(RADICE / "dati" / "cache" / "listone.json")
        if not cache:
            sys.exit("Listone vero non trovato in dati/cache/listone.json.")
        _stampa("listone vero", cache[0], dettagli)


if __name__ == "__main__":
    main()
