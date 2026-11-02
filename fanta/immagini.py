"""Stemma e maglia delle squadre della lega (immagini caricate dall'utente, salvate in lega/immagini/)."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .percorsi import CARTELLA_LEGA

CARTELLA = CARTELLA_LEGA / "immagini"
TIPI = ("stemma", "maglia")
FORMATI = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}
MAX_BYTE = 4 * 1024 * 1024


def slug(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "squadra"


def percorso(nome: str, tipo: str, cartella: Path | None = None) -> Path | None:
    if tipo not in TIPI:
        return None
    for estensione in FORMATI:
        p = (cartella or CARTELLA) / f"{slug(nome)}-{tipo}{estensione}"
        if p.exists():
            return p
    return None


def estensione_da_contenuto(dati: bytes) -> str | None:
    if dati[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if dati[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if dati[:4] == b"RIFF" and dati[8:12] == b"WEBP":
        return ".webp"
    return None


def salva(nome: str, tipo: str, dati: bytes, cartella: Path | None = None) -> Path:
    if tipo not in TIPI:
        raise ValueError("Tipo di immagine non valido: stemma o maglia")
    if len(dati) > MAX_BYTE:
        raise ValueError("Immagine troppo grande (massimo 4 MB)")
    estensione = estensione_da_contenuto(dati)
    if estensione is None:
        raise ValueError("Formato non supportato: usa PNG, JPEG o WebP")
    cartella = cartella or CARTELLA
    cartella.mkdir(parents=True, exist_ok=True)
    for altra in FORMATI:                       # una sola immagine per tipo: le vecchie si tolgono
        (cartella / f"{slug(nome)}-{tipo}{altra}").unlink(missing_ok=True)
    destinazione = cartella / f"{slug(nome)}-{tipo}{estensione}"
    destinazione.write_bytes(dati)
    return destinazione


def rinomina(vecchio: str, nuovo: str, cartella: Path | None = None) -> None:
    """Stemma e maglia seguono la squadra quando cambia nome (i file si chiamano come la squadra)."""
    cartella = cartella or CARTELLA
    if slug(vecchio) == slug(nuovo):
        return
    for tipo in TIPI:
        p = percorso(vecchio, tipo, cartella)
        if p is None:
            continue
        for altra in FORMATI:
            (cartella / f"{slug(nuovo)}-{tipo}{altra}").unlink(missing_ok=True)
        p.rename(cartella / f"{slug(nuovo)}-{tipo}{p.suffix}")


def rimuovi(nome: str, tipo: str, cartella: Path | None = None) -> bool:
    """Toglie stemma o maglia di una squadra. Vero se c'era qualcosa da togliere."""
    if tipo not in TIPI:
        raise ValueError("Tipo di immagine non valido: stemma o maglia")
    tolto = False
    for estensione in FORMATI:
        p = (cartella or CARTELLA) / f"{slug(nome)}-{tipo}{estensione}"
        if p.exists():
            p.unlink(missing_ok=True)
            tolto = True
    return tolto


# Immagine arrivata dal menu «Condividi» del telefono, in attesa che l'utente scelga squadra e tipo.
# Il nome inizia con «_»: uno slug non può mai avere quel nome.
def in_attesa(cartella: Path | None = None) -> Path | None:
    for estensione in FORMATI:
        p = (cartella or CARTELLA) / f"_in-attesa{estensione}"
        if p.exists():
            return p
    return None


def salva_in_attesa(dati: bytes, cartella: Path | None = None) -> Path:
    if len(dati) > MAX_BYTE:
        raise ValueError("Immagine troppo grande (massimo 4 MB)")
    estensione = estensione_da_contenuto(dati)
    if estensione is None:
        raise ValueError("Formato non supportato: usa PNG, JPEG o WebP")
    cartella = cartella or CARTELLA
    cartella.mkdir(parents=True, exist_ok=True)
    togli_in_attesa(cartella)
    destinazione = cartella / f"_in-attesa{estensione}"
    destinazione.write_bytes(dati)
    return destinazione


def togli_in_attesa(cartella: Path | None = None) -> bool:
    p = in_attesa(cartella)
    if p is None:
        return False
    p.unlink(missing_ok=True)
    return True


def presenti(nome: str, cartella: Path | None = None) -> dict[str, bool]:
    return {t: percorso(nome, t, cartella) is not None for t in TIPI}
