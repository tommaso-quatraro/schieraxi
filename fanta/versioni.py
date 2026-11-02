"""ETag e If-Match: due dispositivi dello stesso utente non si sovrascrivono a vicenda senza accorgersene.

Ogni risorsa personale (regole, rose, scelta di una giornata, osservati, impostazioni degli avvisi) ha un ETag: l'impronta
del suo contenuto. Chi legge lo riceve nell'intestazione `ETag`; chi scrive può rimandarlo in `If-Match`. Se nel frattempo
la risorsa è cambiata (un altro telefono, un'altra scheda) la scrittura si ferma con 412 e un messaggio chiaro, e l'app
rilegge i dati. Senza `If-Match` la scrittura funziona come sempre: i client vecchi (l'app web in cache, l'app iOS) non si rompono.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from fastapi import HTTPException, Request

MESSAGGIO_CONFLITTO = ("Questi dati sono stati cambiati da un altro dispositivo. Ho ricaricato la versione nuova: "
                       "controlla e rifai la modifica.")
_blocchi: dict[str, threading.Lock] = {}
_blocco_elenco = threading.Lock()


def blocco(nome: str) -> threading.Lock:
    """Un lucchetto per risorsa: «controlla l'ETag e scrivi» non può essere interrotto da un'altra scrittura."""
    with _blocco_elenco:
        return _blocchi.setdefault(nome, threading.Lock())


def _etag(contenuto: bytes) -> str:
    return '"' + hashlib.sha256(contenuto).hexdigest()[:20] + '"'


def etag_file(percorso: Path) -> str:
    """L'ETag di un file (un file che non c'è ancora ha il suo ETag, sempre lo stesso)."""
    try:
        return _etag(percorso.read_bytes())
    except OSError:
        return _etag(b"")


def etag_dati(dati) -> str:
    return _etag(json.dumps(dati, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _tag(t: str) -> str:
    """Il tag senza «W/» e senza il suffisso della lingua: la copia inglese di una risposta (server._etag_inglese, «"abc-en"») è la
    STESSA versione dei dati, cambia solo la lingua dei testi. Senza questo, chi usa l'app in inglese riceveva 412 a ogni scrittura
    dopo una lettura tradotta (per esempio «Questa è la mia» nel primo avvio dopo aver visto una rosa)."""
    t = t.strip()
    t = t[2:] if t[:2] in ("W/", "w/") else t
    return t[:-4] + '"' if t.endswith('-en"') else t


def controlla(request: Request, attuale: str) -> None:
    """Alza 412 se la richiesta ha un If-Match che non corrisponde all'ETag di adesso. Senza If-Match (o con `*`) non fa niente."""
    voluto = request.headers.get("if-match")
    if voluto is None or voluto.strip() == "*":
        return
    if attuale not in [_tag(t) for t in voluto.split(",")]:
        raise HTTPException(412, MESSAGGIO_CONFLITTO, headers={"ETag": attuale})
