"""Stemma e maglia delle squadre della lega (immagini caricate dall'utente, salvate in lega/immagini/)."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .percorsi import CARTELLA_LEGA, RADICE

CARTELLA = CARTELLA_LEGA / "immagini"
ESEMPIO = RADICE / "lega" / "esempio" / "immagini"
TIPI = ("stemma", "maglia")
FORMATI = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}
MAX_BYTE = 4 * 1024 * 1024


MAX_SLUG = 80          # un nome molto lungo (o con caratteri che si espandono, «㎯») darebbe un file troppo lungo per il disco


def _slug_pieno(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "squadra"


def slug(nome: str) -> str:
    return _slug_pieno(nome)[:MAX_SLUG].strip("-") or "squadra"


def _slug_possibili(nome: str) -> list[str]:
    """Lo slug di adesso e, se diverso, quello intero di prima (immagini salvate prima del taglio a MAX_SLUG)."""
    return list(dict.fromkeys([slug(nome), _slug_pieno(nome)]))


def percorso(nome: str, tipo: str, cartella: Path | None = None) -> Path | None:
    if tipo not in TIPI:
        return None
    for s in _slug_possibili(nome):
        for estensione in FORMATI:
            p = (cartella or CARTELLA) / f"{s}-{tipo}{estensione}"
            try:
                if p.exists():
                    return p
            except OSError:              # nome di file troppo lungo per il disco: per quel nome non c'è immagine
                continue
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


def rinomina(vecchio: str, nuovo: str, cartella: Path | None = None) -> list[tuple[Path, Path]]:
    """Stemma e maglia seguono la squadra quando cambia nome (i file si chiamano come la squadra). Restituisce gli spostamenti
    fatti, per `annulla` se poi il salvataggio delle rose non riesce; se uno spostamento fallisce, quelli già fatti si annullano."""
    cartella = cartella or CARTELLA
    fatti: list[tuple[Path, Path]] = []
    if slug(vecchio) == slug(nuovo):
        return fatti
    try:
        for tipo in TIPI:
            p = percorso(vecchio, tipo, cartella)
            if p is None:
                continue
            for altra in FORMATI:           # file rimasti di una squadra che non c'è più con lo stesso nome: non si ereditano
                (cartella / f"{slug(nuovo)}-{tipo}{altra}").unlink(missing_ok=True)
            dest = cartella / f"{slug(nuovo)}-{tipo}{p.suffix}"
            p.rename(dest)
            fatti.append((p, dest))
    except OSError:
        annulla(fatti)
        raise
    return fatti


def annulla(spostamenti: list[tuple[Path, Path]]) -> None:
    """Rimette i file dove stavano prima di `rinomina` (in ordine inverso)."""
    for da, a in reversed(spostamenti):
        try:
            a.rename(da)
        except OSError:
            pass


def pulisci(nomi: list[str], cartella: Path | None = None) -> int:
    """Toglie stemmi e maglie che non appartengono a nessuna delle squadre `nomi` (per esempio di una squadra tolta dalle rose):
    una squadra nuova con lo stesso nome non deve ereditarli. Le immagini in attesa («_in-attesa») restano. Quante ne ha tolte."""
    cartella = cartella or CARTELLA
    if not cartella.is_dir() or cartella.resolve() == ESEMPIO.resolve():
        return 0                                  # le immagini della lega di esempio stanno nel repository: mai toccarle
    tenuti = {f"{s}-{t}" for n in nomi for s in _slug_possibili(n) for t in TIPI}
    tolte = 0
    for p in cartella.iterdir():
        if p.suffix in FORMATI and not p.name.startswith("_") and p.stem.endswith(TIPI) and p.stem not in tenuti:
            p.unlink(missing_ok=True)
            tolte += 1
    return tolte


def rimuovi(nome: str, tipo: str, cartella: Path | None = None) -> bool:
    """Toglie stemma o maglia di una squadra. Vero se c'era qualcosa da togliere."""
    if tipo not in TIPI:
        raise ValueError("Tipo di immagine non valido: stemma o maglia")
    tolto = False
    while (p := percorso(nome, tipo, cartella)) is not None:
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
