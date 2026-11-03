"""Fotografa lo schermo del simulatore quando è fermo (lo usa scripts/screenshot.sh).

Due foto di fila con gli stessi pixel vogliono dire che caricamenti e animazioni sono finiti. Lo scheletro e la rotellina del
caricamento si muovono sempre, quindi una schermata che sta caricando non risulta mai ferma; i numeri che salgono («0,0» che
diventa «9,0») nemmeno. Le schermate che si muovono da sole (il conto alla rovescia di Oggi) arrivano al tempo massimo e si
fotografano lo stesso, con l'ultima foto.

Si confrontano i pixel (intestazione e dati dell'immagine decompressi), non i file: i metadati possono cambiare a ogni foto.

Uso: python3 -I schermo_fermo.py <udid del simulatore> <file.png> [secondi massimi, predefinito 8]
Uscita: 0 foto a schermo fermo; 3 foto scattata allo scadere del tempo (lo schermo si muoveva ancora); 1 foto non riuscita;
2 uso sbagliato. Solo libreria standard.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zlib

FERMO = 0
ERRORE = 1
USO = 2
SI_MUOVE = 3

MASSIMO = 8.0      # secondi di attesa al massimo dopo la prima foto
INTERVALLO = 1.0   # secondi tra due foto: più delle pause brevi della demo tra un passo e l'altro (0,4-0,8 s)
FIRMA = b"\x89PNG\r\n\x1a\n"


def pixel(percorso) -> bytes | None:
    """Intestazione (IHDR) e dati dell'immagine (IDAT) decompressi. None se il file manca o non è un PNG leggibile."""
    try:
        with open(percorso, "rb") as f:
            dati = f.read()
    except OSError:
        return None
    if not dati.startswith(FIRMA):
        return None
    pos, testa, pezzi = len(FIRMA), None, []
    while pos + 8 <= len(dati):
        lunghezza, tipo = struct.unpack(">I4s", dati[pos:pos + 8])
        corpo = dati[pos + 8:pos + 8 + lunghezza]
        if len(corpo) < lunghezza:
            return None   # file tronco
        if tipo == b"IHDR":
            testa = corpo
        elif tipo == b"IDAT":
            pezzi.append(corpo)
        elif tipo == b"IEND":
            break
        pos += 12 + lunghezza
    if testa is None or not pezzi:
        return None
    try:
        return testa + zlib.decompress(b"".join(pezzi))
    except zlib.error:
        return None


def uguali(a, b) -> bool:
    """Le due foto hanno gli stessi pixel (e le stesse misure)."""
    pa = pixel(a)
    return pa is not None and pa == pixel(b)


def aspetta_fermo(scatta, file, massimo=MASSIMO, intervallo=INTERVALLO, orologio=time.monotonic, dormi=time.sleep) -> int:
    """Scatta, poi riscatta ogni `intervallo` secondi finché due foto di fila sono uguali o passano `massimo` secondi.
    In `file` va l'ultima foto riuscita. `scatta(percorso)` fa una foto e dice se è riuscita.
    Le foto di prova stanno in una cartella temporanea: accanto alle foto vere non resta niente."""
    with tempfile.TemporaryDirectory() as cartella:
        ultima = os.path.join(cartella, "a.png")
        nuova = os.path.join(cartella, "b.png")
        if not scatta(ultima):
            return ERRORE
        esito = SI_MUOVE
        fine = orologio() + massimo
        while orologio() < fine:
            dormi(intervallo)
            if not scatta(nuova):
                break   # resta l'ultima foto buona
            if uguali(ultima, nuova):
                esito = FERMO
                break
            ultima, nuova = nuova, ultima
        try:
            shutil.copyfile(ultima, file)
        except OSError:
            return ERRORE
        return esito


def scatto_del_simulatore(udid):
    def scatta(percorso) -> bool:
        try:
            r = subprocess.run(["xcrun", "simctl", "io", udid, "screenshot", percorso],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return r.returncode == 0 and os.path.isfile(percorso)
    return scatta


def main(argv) -> int:
    if len(argv) not in (3, 4):
        print("uso: schermo_fermo.py <udid> <file.png> [secondi massimi]", file=sys.stderr)
        return USO
    try:
        massimo = float(argv[3]) if len(argv) == 4 else MASSIMO
    except ValueError:
        print("i secondi massimi devono essere un numero", file=sys.stderr)
        return USO
    return aspetta_fermo(scatto_del_simulatore(argv[1]), argv[2], massimo=massimo)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
