"""Sceglie un simulatore tra quelli disponibili sul Mac e ne stampa "UDID<TAB>nome<TAB>iOS".

Uso: python3 -I scripts/scegli_simulatore.py iphone|iphone-piccolo|iphone-grande|ipad

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


def crea_piccolo(ultima):
    """Crea un iPhone SE (o mini) col runtime più recente, se il tipo di dispositivo esiste. Torna (versione, nome, udid) o None."""
    try:
        tipi = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devicetypes", "-j"]))["devicetypes"]
        runtime = [r for r in json.loads(subprocess.check_output(["xcrun", "simctl", "list", "runtimes", "-j"]))["runtimes"]
                   if r.get("isAvailable", True) and "iOS" in r.get("identifier", "") and versione(r["identifier"]) == ultima]
        if not runtime:
            return None
        for nome in ("iPhone SE (3rd generation)", "iPhone 13 mini", "iPhone 12 mini"):
            tipo = [t for t in tipi if t.get("name") == nome]
            if not tipo:
                continue
            ris = subprocess.run(["xcrun", "simctl", "create", nome, tipo[0]["identifier"], runtime[0]["identifier"]],
                                 capture_output=True, text=True)
            if ris.returncode == 0 and ris.stdout.strip():
                return (ultima, nome, ris.stdout.strip())
    except (subprocess.CalledProcessError, KeyError, ValueError):
        return None
    return None


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

    if tipo == "iphone-piccolo":
        # lo schermo più stretto disponibile (se manca, se ne crea uno: il tipo di dispositivo c'è anche se il simulatore no)
        telefoni = [v for v in voci if v[1].startswith("iPhone")]
        for modello in ("iPhone SE (3rd generation)", "iPhone 13 mini", "iPhone 12 mini", "iPhone 16e"):
            trovati = [v for v in telefoni if v[1] == modello]
            if trovati:
                scelta = trovati[0]
                break
        else:
            scelta = crea_piccolo(ultima) or min(telefoni, key=lambda v: numero(v[1]))
    elif tipo == "iphone-grande":
        telefoni = [v for v in voci if v[1].startswith("iPhone")]
        grandi = [v for v in telefoni if v[1].endswith("Pro Max")] or [v for v in telefoni if v[1].endswith("Plus")]
        scelta = max(grandi or telefoni, key=lambda v: numero(v[1]))
    elif tipo == "iphone":
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
