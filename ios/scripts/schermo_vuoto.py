"""Riconosce la foto di uno schermo ancora vuoto (lo usa scripts/screenshot.sh, issue #860).

Una foto può uscire prima che l'app abbia disegnato la schermata: la schermata d'avvio (fondo pieno e marchio al centro),
il marchio del caricamento da solo, uno scheletro così chiaro che non si vede. «Schermo fermo» (schermo_fermo.py) non basta:
la schermata d'avvio è ferma, e il caricamento che si muove si fotografa comunque allo scadere dell'attesa. Qui si guarda la
foto: tolte le barre in alto (stato, schede, titolo) e in basso (schede, indicatore della Home), una schermata vera ha testo e
riquadri sparsi per lo schermo; uno schermo vuoto ha al più un oggetto piccolo (il marchio). Misure sulle foto vere delle corse
del 20/11/2026 (770 foto, cinque corse): le 8 foto vuote hanno tutto in un riquadro largo al massimo 23% e alto 15%; la
schermata vera più raccolta (l'accesso sull'iPad in orizzontale) è larga 36% e alta 54%. Con la soglia dei bordi fra 30 e 40 e
tre modi di rimpicciolire il risultato non cambia; a 50 un accesso in tema chiaro (poco contrasto) risultava vuoto.

Prima di guardarla la foto si rimpicciolisce a 200 punti sul lato lungo con `sips` (sul Mac): bastano per vedere testo e
riquadri, e i pochi pixel si leggono in fretta. Un bordo è un salto di colore forte fra due pixel vicini: le sfumature del fondo
cambiano di pochi livelli da un pixel all'altro e non contano.

Uso: python3 -I schermo_vuoto.py <file.png>
Uscita: 0 la foto mostra una schermata; 3 schermo vuoto (schermata d'avvio o caricamento); 1 non si può dire (file che non si
legge o rimpicciolimento non riuscito); 2 uso sbagliato. Scrive sempre una riga con la misura. Solo libreria standard.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import zlib

PIENO = 0
ERRORE = 1
USO = 2
VUOTO = 3

LATO = 200            # punti sul lato lungo della foto rimpicciolita
LATO_MASSIMO = 400    # una foto più piccola si guarda com'è (le immagini dei test), una più grande si rimpicciolisce
SOGLIA = 30           # salto di colore (0-255, sul canale che cambia di più) fra due pixel vicini che vale come bordo
ALTO = 0.16           # parte alta che non conta: barra di stato, schede dell'iPad, titolo
BASSO = 0.12          # parte bassa che non conta: schede dell'iPhone, indicatore della Home
LARGO_MAX = 0.30      # schermo vuoto: tutti i bordi della parte centrale stanno in un riquadro largo al massimo così
ALTO_MAX = 0.25       # e alto al massimo così (frazioni della foto)
FIRMA = b"\x89PNG\r\n\x1a\n"
CANALI = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}   # tipo di colore del PNG -> campioni per pixel


def _testa(dati: bytes):
    """(larghezza, altezza, profondità, tipo di colore, interlacciato) dall'intestazione, o None."""
    if not dati.startswith(FIRMA) or len(dati) < 33 or dati[12:16] != b"IHDR":
        return None
    larghezza, altezza, profondita, colore, compressione, filtro, interlacciato = struct.unpack(">IIBBBBB", dati[16:29])
    if compressione != 0 or filtro != 0:
        return None
    return larghezza, altezza, profondita, colore, interlacciato


def _togli_filtro(tipo: int, riga: bytearray, sopra: bytearray, bpp: int) -> bool:
    """Toglie il filtro PNG della riga (sul posto). Falso se il filtro non esiste."""
    n = len(riga)
    if tipo == 0:
        return True
    if tipo == 1:
        for i in range(bpp, n):
            riga[i] = (riga[i] + riga[i - bpp]) & 255
    elif tipo == 2:
        for i in range(n):
            riga[i] = (riga[i] + sopra[i]) & 255
    elif tipo == 3:
        for i in range(n):
            a = riga[i - bpp] if i >= bpp else 0
            riga[i] = (riga[i] + ((a + sopra[i]) >> 1)) & 255
    elif tipo == 4:
        for i in range(n):
            a = riga[i - bpp] if i >= bpp else 0
            b = sopra[i]
            c = sopra[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            riga[i] = (riga[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
    else:
        return False
    return True


def leggi_png(dati: bytes):
    """(larghezza, altezza, righe di pixel (r, g, b)) di un PNG a 8 o 16 bit non interlacciato (come li scrive sips), o None.
    L'alfa non conta: le foto del simulatore sono opache. A 16 bit si tiene il byte alto."""
    testa = _testa(dati)
    if testa is None:
        return None
    larghezza, altezza, profondita, colore, interlacciato = testa
    if interlacciato or colore not in CANALI or profondita not in (8, 16) or (colore == 3 and profondita != 8):
        return None
    if larghezza == 0 or altezza == 0:
        return None
    pos, idat, tavolozza = len(FIRMA), [], []
    while pos + 8 <= len(dati):
        lunghezza, tipo = struct.unpack(">I4s", dati[pos:pos + 8])
        corpo = dati[pos + 8:pos + 8 + lunghezza]
        if len(corpo) < lunghezza:
            return None   # file tronco
        if tipo == b"IDAT":
            idat.append(corpo)
        elif tipo == b"PLTE":
            tavolozza = [tuple(corpo[i:i + 3]) for i in range(0, len(corpo) - 2, 3)]
        elif tipo == b"IEND":
            break
        pos += 12 + lunghezza
    if not idat:
        return None
    try:
        grezzi = zlib.decompress(b"".join(idat))
    except zlib.error:
        return None
    lato = profondita // 8
    bpp = CANALI[colore] * lato
    passo = larghezza * bpp
    if len(grezzi) < altezza * (passo + 1):
        return None
    righe, sopra = [], bytearray(passo)
    for y in range(altezza):
        inizio = y * (passo + 1)
        riga = bytearray(grezzi[inizio + 1:inizio + 1 + passo])
        if not _togli_filtro(grezzi[inizio], riga, sopra, bpp):
            return None
        if colore == 3:
            try:
                pixel = [tavolozza[i] for i in riga]
            except IndexError:
                return None
        elif colore in (0, 4):
            pixel = [(v, v, v) for v in riga[0::bpp]]
        else:
            pixel = list(zip(riga[0::bpp], riga[lato::bpp], riga[2 * lato::bpp]))
        righe.append(pixel)
        sopra = riga
    return larghezza, altezza, righe


def riquadro(larghezza: int, altezza: int, righe):
    """Il riquadro (x0, x1, y0, y1, in frazioni della foto) che contiene tutti i bordi della parte centrale, o None se non
    ce n'è nessuno."""
    y0, y1 = int(altezza * ALTO), int(altezza * (1 - BASSO))
    xs, ys = [], []
    for y in range(y0, y1):
        riga = righe[y]
        sotto = righe[y + 1] if y + 1 < altezza else None
        for x in range(larghezza):
            r, g, b = riga[x]
            salto = 0
            if x + 1 < larghezza:
                r2, g2, b2 = riga[x + 1]
                salto = max(abs(r - r2), abs(g - g2), abs(b - b2))
            if sotto is not None:
                r2, g2, b2 = sotto[x]
                salto = max(salto, abs(r - r2), abs(g - g2), abs(b - b2))
            if salto > SOGLIA:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs) / larghezza, (max(xs) + 1) / larghezza, min(ys) / altezza, (max(ys) + 1) / altezza


def vuoto(larghezza: int, altezza: int, righe) -> bool:
    """Vero se, tolte le barre in alto e in basso, nella foto c'è al più un oggetto piccolo (o niente)."""
    r = riquadro(larghezza, altezza, righe)
    return r is None or (r[1] - r[0] <= LARGO_MAX and r[3] - r[2] <= ALTO_MAX)


def rimpicciolisci_con_sips(origine, destinazione, lato) -> bool:
    """Copia rimpicciolita (lato lungo `lato`) con sips, lo strumento delle immagini del Mac."""
    try:
        r = subprocess.run(["sips", "-Z", str(lato), str(origine), "--out", str(destinazione)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and os.path.isfile(destinazione)


def _percento(v: float) -> str:
    return f"{round(v * 100)}%"


def esamina(percorso, rimpicciolisci=rimpicciolisci_con_sips):
    """(esito, frase) per la foto in `percorso`: PIENO, VUOTO o ERRORE (non si può dire)."""
    try:
        with open(percorso, "rb") as f:
            dati = f.read()
    except OSError:
        return ERRORE, f"foto non controllata: {os.path.basename(str(percorso))} non si legge"
    testa = _testa(dati)
    if testa is None:
        return ERRORE, "foto non controllata: non è un PNG che si sa leggere"
    if max(testa[0], testa[1]) > LATO_MASSIMO:
        with tempfile.TemporaryDirectory() as cartella:
            piccola = os.path.join(cartella, "piccola.png")
            if not rimpicciolisci(percorso, piccola, LATO):
                return ERRORE, "foto non controllata: non sono riuscito a rimpicciolirla"
            try:
                with open(piccola, "rb") as f:
                    dati = f.read()
            except OSError:
                return ERRORE, "foto non controllata: non sono riuscito a rimpicciolirla"
    immagine = leggi_png(dati)
    if immagine is None:
        return ERRORE, "foto non controllata: non è un PNG che si sa leggere"
    r = riquadro(*immagine)
    if r is None:
        return VUOTO, "schermo vuoto: niente fra le barre in alto e in basso (schermata d'avvio o caricamento?)"
    misura = f"riquadro {_percento(r[1] - r[0])} x {_percento(r[3] - r[2])}"
    if vuoto(*immagine):
        return VUOTO, f"schermo vuoto: fra le barre solo un oggetto piccolo, {misura} (schermata d'avvio o caricamento?)"
    return PIENO, f"schermata: {misura}"


def main(argv) -> int:
    if len(argv) != 2:
        print("uso: schermo_vuoto.py <file.png>", file=sys.stderr)
        return USO
    esito, frase = esamina(argv[1])
    print(frase)
    return esito


if __name__ == "__main__":
    sys.exit(main(sys.argv))
