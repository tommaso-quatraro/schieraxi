"""Sceglie un simulatore tra quelli disponibili sul Mac e ne stampa "UDID<TAB>nome<TAB>iOS".

Uso: python3 -I scripts/scegli_simulatore.py iphone|ipad

Si usa il runtime iOS più recente. iPhone: preferisce il "Pro" col numero più alto (iPhone 17 Pro, ...), poi un iPhone qualsiasi.
iPad: preferisce un "iPad Pro 11-inch", poi un "iPad Air 11-inch", poi un iPad qualsiasi.
"""
import json
import re
import subprocess
import sys


def versione(runtime):
    m = re.search(r"iOS-(\d+)-(\d+)", runtime)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def numero(nome):
    m = re.search(r"(\d+)", nome)
    return int(m.group(1)) if m else 0


def main():
    tipo = sys.argv[1] if len(sys.argv) > 1 else "iphone"
    dati = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    voci = []
    for runtime, dispositivi in dati["devices"].items():
        if "iOS" not in runtime:
            continue
        for d in dispositivi:
            if d.get("isAvailable", True):
                voci.append((versione(runtime), d["name"], d["udid"]))
    if not voci:
        sys.exit("Nessun simulatore iOS disponibile")
    ultima = max(v[0] for v in voci)
    voci = [v for v in voci if v[0] == ultima]

    if tipo == "iphone":
        telefoni = [v for v in voci if v[1].startswith("iPhone")]
        pro = [v for v in telefoni if re.fullmatch(r"iPhone \d+ Pro", v[1])]
        if pro:
            scelta = max(pro, key=lambda v: numero(v[1]))
        else:
            scelta = max(telefoni, key=lambda v: numero(v[1]))
    else:
        tavolette = [v for v in voci if v[1].startswith("iPad")]
        for modello in ("iPad Pro 11-inch", "iPad Air 11-inch"):
            trovati = [v for v in tavolette if v[1].startswith(modello)]
            if trovati:
                scelta = sorted(trovati, key=lambda v: v[1])[-1]
                break
        else:
            scelta = tavolette[0]

    print("\t".join([scelta[2], scelta[1], "iOS %d.%d" % scelta[0]]))


main()
