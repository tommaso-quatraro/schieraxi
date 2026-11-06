"""Comandi del coordinatore della squadra. Uso: python script/squadra/squadra.py <comando> [opzioni]

Ogni comando che cambia qualcosa (annulla, toglie, rilancia, lancia) di default fa solo la PROVA e stampa cosa farebbe:
agisce solo con --esegui (o --lancia per `foto`). Nessun comando unisce una PR né scrive su main. Guida: LEGGIMI.md."""
from __future__ import annotations

import argparse
import sys

import comune
import annulla_superate
import attendi
import pulisci
import stato

COMANDI = [stato, attendi, annulla_superate, pulisci]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="squadra.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Codici di uscita: vedi «squadra.py <comando> --help». Argomenti sbagliati: 2.")
    sotto = p.add_subparsers(dest="comando", required=True, metavar="comando")
    for m in COMANDI:
        q = sotto.add_parser(m.NOME, help=m.AIUTO, description=m.AIUTO, epilog=f"Codici di uscita: {m.USCITE}",
                             formatter_class=argparse.RawDescriptionHelpFormatter)
        m.opzioni(q)
        q.set_defaults(modulo=m)
    return p


def main(argv: list[str] | None = None, esegui: comune.Esegui = comune.esegui_vero) -> int:
    args = parser().parse_args(argv)
    return args.modulo.da_riga(args, esegui)


if __name__ == "__main__":
    for flusso in (sys.stdout, sys.stderr):
        if hasattr(flusso, "reconfigure"):
            flusso.reconfigure(encoding="utf-8")
    sys.exit(main())
