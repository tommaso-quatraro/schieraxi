#!/usr/bin/env python3
"""Maschera nei log di compilazione tutto cio' che e' privato PRIMA di caricarli come artifact (il repository e' pubblico).

Uso: maschera_log.py ingresso uscita. Legge FANTA_HOST e FANTA_PORT dall'ambiente e toglie anche, in ogni caso:
indirizzi *.<dominio privato>, intestazioni Authorization/Bearer, token e password in forma chiave=valore, indirizzi IP privati."""
import os
import re
import sys

MASCHERA = "***"


def maschera(testo: str, host: str = "", porta: str = "") -> str:
    for valore in (host, porta):
        # la porta sola (443, 8443) e' troppo corta per essere sostituita ovunque: si toglie solo accanto a un indirizzo (sotto)
        if valore and len(valore) > 4:
            testo = testo.replace(valore, MASCHERA)
    testo = re.sub(r"[A-Za-z0-9.-]+\.ts\.net(:\d+)?", MASCHERA, testo)
    testo = re.sub(r"FANTA_(HOST|PORT)(\s*=\s*|\s*:\s*)\S+", r"FANTA_\1\2" + MASCHERA, testo)
    testo = re.sub(r"(?i)(authorization:\s*)(bearer\s+)?\S+", r"\1" + MASCHERA, testo)
    testo = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", "Bearer " + MASCHERA, testo)
    testo = re.sub(r"(?i)\b(token|password|secret|chiave|api[_-]?key)(\s*[=:]\s*)[^\s\"',;]+", r"\1\2" + MASCHERA, testo)
    testo = re.sub(r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b", MASCHERA, testo)
    return testo


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: maschera_log.py ingresso uscita", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        testo = f.read()
    testo = maschera(testo, os.environ.get("FANTA_HOST", ""), os.environ.get("FANTA_PORT", ""))
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(testo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
