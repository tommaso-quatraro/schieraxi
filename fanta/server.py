"""Server dell'app (PWA): le stesse funzioni dei comandi, esposte all'app su iPhone.

Avvio:  .venv\\Scripts\\python.exe -m fanta server            (solo da questo PC: http://127.0.0.1:8000)
"""
from __future__ import annotations

import contextlib
import gzip
import hashlib
import shutil
from datetime import datetime
import json
import mimetypes
import unicodedata
import logging
import re
import secrets
import traceback
from functools import lru_cache
import sqlite3
import tempfile
import threading
import time
from urllib.parse import urlsplit
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal, NamedTuple

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi import Path as FPath
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from . import da_fare, etichette, frasi, note_infortuni, stato_utente
from . import lingua as lingua_testi
from . import widget as widget_riassunto
from . import account, affidabilita, aggiorna, anteprima_rose, archivio, avatar, calcolo, asta, backup, consigli, diario, fonti_attive, funzioni, push as notifiche_web, gestione, immagini, importa_sicuro, lega, limiti, listone, movimenti, nomi, notifiche, onboarding, osservati, precisione, regole, regole_testo, rinvii, rose, scelte, scheda, sotto_il_cofano as sotto_il_cofano_mod, stato_dati, uso, versioni
from . import avvisi as avvisi_pronta
from . import avvisi_utenti
from . import fasi, live
from . import scambi_multi
from . import copia_scadenza, pianificatore, rotte_account, riscaldamento, social
from . import blocco, percorsi, registro, scarica_immagine, testi_legali
from .contesto import Contesto
from . import stagione as cambio_stagione
from .percorsi import CARTELLA_LEGA, RADICE, scrivi_sicuro

FILE_REGOLE = CARTELLA_LEGA / "regole.json"
FILE_ROSE = CARTELLA_LEGA / "rose.json"
FILE_MOVIMENTI = CARTELLA_LEGA / "movimenti.json"
WEB = Path(__file__).parent / "web"
LIMITE_RICHIESTA = 12 * 1024 * 1024        # byte: più del file Excel più grande ammesso (5 MB) con un largo margine
FILE_NOVITA = Path(__file__).parent / "novita.json"
FILE_NOVITA_EN = Path(__file__).parent / "contenuti" / "novita.en.json"

@asynccontextmanager
async def _ciclo(_):
    # formazione e mercato pronti appena parte il servizio e dopo ogni aggiornamento dei dati (anche fatto da un altro processo)
    fermo = threading.Event()
    if not account.multiutente():                                        # senza account: solo richieste dirette da questo computer
        logging.getLogger("uvicorn.error").warning(rotte_account.AVVISO_SOLO_LOCALE)
    registro.accorcia_registro_richieste()                               # anche il registro delle richieste: mai l'indirizzo intero
    threading.Thread(target=registro.sorveglia, args=(fermo,), name="registri", daemon=True).start()     # righe oltre 30 giorni
    if riscaldamento.attivo():                                           # FANTA_RISCALDA=0 lo spegne
        threading.Thread(target=riscaldamento.sorveglia, args=(lambda: _versione_dati(), lambda: _scalda(), fermo),
                         kwargs={"ritardo": riscaldamento.ritardo_avvio()}, name="riscaldamento", daemon=True).start()
    threading.Thread(target=pianificatore.sorveglia, args=(fermo, _leghe_attive, _db, _aggiorna_leggero, _dopo_giro_leggero),
                     kwargs={"risultati": _risultati_leggeri},       # e risultati e voti la sera stessa, dopo le partite
                     name="pianificatore", daemon=True).start()          # giri in più vicino alla scadenza (FANTA_PIANIFICATORE=0 lo spegne)
    threading.Thread(target=copia_scadenza.sorveglia, args=(fermo, lambda: copia_scadenza.contesti(_contesto_locale), _db),
                     name="copia-scadenza", daemon=True).start()       # copia della consigliata alla scadenza per ogni utente (FANTA_COPIA_SCADENZA=0 la spegne)
    if fonti_attive.acceso("espn") and funzioni.acceso("live"):          # risultati in diretta: un solo raccoglitore per tutto il servizio
        live.unico = live.Raccoglitore(_calendario_live, file=live.FILE)        # la cache resta anche dopo un riavvio
        threading.Thread(target=live.sorveglia, args=(live.unico, fermo), name="live", daemon=True).start()
    try:
        yield
    finally:
        fermo.set()
        uso.salva()


app = FastAPI(title="SchieraXI", lifespan=_ciclo)
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=5)     # risposte più leggere; livello 5: meno della metà della CPU del 9 per lo 0,5-2% di byte in più (1 solo processore sul server)
MAX_FILE = 5 * 1024 * 1024
MAX_ID_CALCIATORE = 2**31 - 1             # codici calciatore: oltre questo numero sqlite non li sa cercare (errore 500)
MAX_GIORNATA = 100                        # numeri di giornata: un numero enorme farebbe un errore 500 in sqlite (si risponde 422)
PERCORSO_CONDIVISIONE = "/api/squadre/immagine/condivisa"      # azione di `share_target` nel manifest


# Intestazioni di sicurezza su ogni risposta. La pagina usa solo file suoi (niente script in linea né siti esterni); gli stili
# in linea servono ai disegni generati dall'app. Nessun altro sito può incorniciare l'app (clickjacking).
SICUREZZA = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                               "connect-src 'self'; font-src 'self'; manifest-src 'self'; worker-src 'self'; object-src 'none'; "
                               "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Robots-Tag": "noindex, nofollow",                # niente motori di ricerca (vedi anche /robots.txt)
}
LIMITE_ACCOUNT = 8 * 1024                  # byte: le richieste di accesso, registrazione e amministrazione sono piccolissime
LIMITE_ROSE_AMICO = 600 * 1024             # byte: le rose incollate dal proprietario per un amico (il testo vale al massimo 200 mila caratteri)


def _tetto_corpo(percorso: str) -> int:
    if percorso.startswith("/api/admin/utenti/") and percorso.endswith("/rose"):
        return LIMITE_ROSE_AMICO
    return LIMITE_ACCOUNT if percorso.startswith(("/api/account/", "/api/admin/")) else LIMITE_RICHIESTA


RISPOSTE_PER_PERSONA = ("/api/oggi", "/api/widget")      # leggibili anche con il token del widget


@app.middleware("http")
async def protezioni(request: Request, chiama):
    inizio = time.perf_counter()
    try:
        risposta = await _risposta(request, chiama)
    except Exception as e:  # noqa: BLE001 - qualunque errore imprevisto: risposta pulita, mai la traccia
        request.state.tipo_errore = type(e).__name__
        if _e_connessione_chiusa(e):
            risposta = Response(status_code=499)          # il browser ha chiuso la richiesta: non è un errore del server, nessuna traccia nel log
        else:
            risposta = _errore_imprevisto(request, e)
    _annota(request, risposta.status_code, (time.perf_counter() - inizio) * 1000)
    for k, v in SICUREZZA.items():
        risposta.headers.setdefault(k, v)
    if rotte_account.e_https(request):
        risposta.headers["Strict-Transport-Security"] = "max-age=15552000"
    return risposta


def _e_connessione_chiusa(e: Exception) -> bool:
    """Starlette dice «No response returned.» quando chi ha chiesto la pagina se ne va prima della risposta (scheda chiusa, cambio pagina)."""
    return isinstance(e, RuntimeError) and str(e).startswith("No response returned")


class _CorpoTroppoGrande(Exception):
    """Il corpo della richiesta ha superato il tetto mentre arrivava (vedi LimiteCorpo)."""


class LimiteCorpo:
    """Conta i byte VERI del corpo mentre arrivano e si ferma (413) appena superano il tetto: vale anche per le richieste senza
    Content-Length («chunked») e per i multipart, che altrimenti verrebbero letti (o scritti su disco) tutti prima di ogni controllo.
    Il controllo veloce sul Content-Length dichiarato resta in `_risposta`."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        tetto = _tetto_corpo(scope.get("path", ""))
        letti, superato, mandata = 0, False, False
        rifiuto = JSONResponse(status_code=413, content={"detail": "Richiesta troppo grande"},
                               headers={"Connection": "close", "Cache-Control": "no-store"} | SICUREZZA)

        async def ricevi():
            nonlocal letti, superato
            messaggio = await receive()
            if messaggio["type"] == "http.request":
                letti += len(messaggio.get("body", b""))
                if letti > tetto:
                    superato = True
                    raise _CorpoTroppoGrande()        # FastAPI lo trasforma in un errore di lettura: la risposta la cambia `manda`
            return messaggio

        async def manda(messaggio):
            nonlocal mandata
            if not superato:
                mandata = mandata or messaggio["type"] == "http.response.start"
                await send(messaggio)
            elif messaggio["type"] == "http.response.start" and not mandata:
                mandata = True
                await rifiuto(scope, receive, send)    # al posto della risposta dell'app (400 o 500): 413

        try:
            await self.app(scope, ricevi, manda)
        except _CorpoTroppoGrande:
            if not mandata:
                await rifiuto(scope, receive, send)


app.add_middleware(LimiteCorpo)          # il più esterno: conta i byte prima di tutto il resto


def _annota(request: Request, stato: int, ms: float) -> None:
    """Contatori (richieste, errori, tempi) e, per ogni risposta 5xx, una riga nel registro degli errori. Mai un problema per la richiesta."""
    try:
        rotta = registro.rotta_di_modello(request)
        registro.contatori.conta(rotta, stato, ms)
        uso.conta(request.method, rotta, stato)          # conteggio anonimo per rotta e per funzione (fanta/uso.py)
        if stato >= 500:
            registro.errore(request.method, rotta, stato, getattr(request.state, "tipo_errore", None))
    except Exception:  # noqa: BLE001
        pass


def _da_un_altro_sito(request: Request) -> bool:
    """Le richieste che cambiano qualcosa devono venire dall'app stessa. I browser dicono da dove parte la richiesta
    (Sec-Fetch-Site); quelli vecchi mandano almeno Origin, che deve essere questo stesso indirizzo. Le app native non mandano
    nessuna delle due e passano (hanno il loro token)."""
    sito = request.headers.get("sec-fetch-site")
    if sito is not None:
        return sito not in ("same-origin", "none")
    origine = request.headers.get("origin")
    if origine is None:
        return False
    host = urlsplit(origine).netloc.lower() if origine != "null" else ""
    validi = {request.headers.get("host", "").lower()} | {h.strip().lower() for h in request.headers.get("x-forwarded-host", "").split(",")}
    return not host or host not in validi


TETTO_NOTE = 4 * 1024 * 1024          # byte: oltre questa dimensione una risposta non si riscrive


def _accoda_vary(risposta, valori: str) -> None:
    """Aggiunge voci a `Vary` senza perdere quelle che ci sono già (es. Accept-Encoding) e senza ripeterle."""
    presenti = [v.strip() for v in risposta.headers.get("vary", "").split(",") if v.strip()]
    for v in (x.strip() for x in valori.split(",")):
        if v and v.lower() not in (p.lower() for p in presenti):
            presenti.append(v)
    risposta.headers["Vary"] = ", ".join(presenti)


def _etag_inglese(etag: str) -> str:
    """L'ETag della versione inglese di una risposta: quello italiano con «-en» (così le due copie non si scambiano)."""
    etag = etag.strip()
    return etag[:-1] + '-en"' if etag.endswith('"') else etag + "-en"


def _etag_in_if_none_match(valore: str, etag: str) -> bool:
    voci = [v.strip().removeprefix("W/") for v in valore.split(",")]
    return "*" in voci or etag.removeprefix("W/") in voci


def _riscrivi_note(corpo: bytes, compresso: bool) -> bytes:
    """Il corpo con le note e le etichette di stato tradotte; se non c'è niente da tradurre (o qualcosa non va) restituisce lo stesso corpo. Lavoro da thread."""
    try:
        chiaro = gzip.decompress(corpo) if compresso else corpo
        if len(chiaro) > TETTO_NOTE or not (b'"nota"' in chiaro or b'"motivi"' in chiaro or b'"etichetta"' in chiaro):
            return corpo
        dati = json.loads(chiaro)
        nuovi = note_infortuni.traduci_dati(dati)
        if b'"etichetta"' in chiaro:                   # le etichette di stato dei giocatori (fanta/etichette.py)
            nuovi = etichette.traduci_dati(nuovi, lingua_testi.EN)
        if nuovi == dati:
            return corpo
        nuovo = json.dumps(nuovi, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return gzip.compress(nuovo, 5) if compresso else nuovo
    except Exception:  # noqa: BLE001 - mai un 500 per una traduzione: la risposta resta com'era
        return corpo


def _e_lettura_json(request: Request, risposta) -> bool:
    return (request.method == "GET" and request.url.path.startswith("/api/") and risposta.status_code == 200
            and "application/json" in risposta.headers.get("content-type", ""))


async def _note_in_inglese(request: Request, risposta, if_none_match: str | None = None):
    """Con la lingua inglese, nelle risposte JSON di lettura (GET /api/) le note sugli infortuni delle fonti (campi `nota`, e la stessa nota
    dentro `motivi`) si traducono con il vocabolario di note_infortuni.py; quel che non si riconosce resta in italiano.
    Se il corpo cambia, anche l'ETag cambia (suffisso «-en») e `If-None-Match` si confronta qui (`if_none_match` è quello originale della richiesta:
    chiama() l'ha tolto, così il 304 non arriva dall'ETag italiano). Le risposte da scaricare (Content-Disposition) non si toccano."""
    if (not _e_lettura_json(request, risposta) or not hasattr(risposta, "body_iterator")
            or "attachment" in risposta.headers.get("content-disposition", "").lower()):
        return risposta
    corpo = b"".join([pezzo async for pezzo in risposta.body_iterator])
    compresso = risposta.headers.get("content-encoding") == "gzip"            # la compressione sta più dentro: si apre e si richiude
    nuovo = await run_in_threadpool(_riscrivi_note, corpo, compresso)
    etag = risposta.headers.get("etag")
    if etag and nuovo is not corpo:
        etag = _etag_inglese(etag)
    escluse = (b"content-length", b"vary") + ((b"etag",) if etag else ())
    intestazioni = [(k, v) for k, v in risposta.raw_headers if k.lower() not in escluse]
    if etag:
        intestazioni.append((b"etag", etag.encode()))
    stato = 200
    if etag and if_none_match and _etag_in_if_none_match(if_none_match, etag):
        stato, nuovo = 304, b""
        intestazioni = [(k, v) for k, v in intestazioni if k.lower() not in (b"content-type", b"content-encoding")]
    intestazioni.append((b"content-length", str(len(nuovo)).encode()))
    nuova = Response(content=nuovo, status_code=stato)
    nuova.raw_headers = intestazioni
    if risposta.headers.get("vary"):
        nuova.headers["Vary"] = risposta.headers["vary"]
    return nuova


async def _risposta(request: Request, chiama):
    # Le richieste che cambiano qualcosa devono venire dall'app: un altro sito aperto sullo stesso telefono
    # non può aggiungere questa intestazione, quindi non può importare rose o avviare aggiornamenti.
    # Unica eccezione a X-Fanta: la pagina che riceve l'immagine dal menu «Condividi» del telefono (la manda il sistema, non l'app);
    # resta il controllo «dallo stesso sito» e serve la sessione (vedi `riceve_immagine_condivisa`).
    senza_x_fanta = request.url.path == PERCORSO_CONDIVISIONE and request.method == "POST"
    if request.method not in ("GET", "HEAD") and ((request.headers.get("x-fanta") != "1" and not senza_x_fanta) or _da_un_altro_sito(request)):
        return JSONResponse(status_code=403, content={"detail": "Richiesta non permessa"})
    limite = _tetto_corpo(request.url.path)
    lunghezza = request.headers.get("content-length")
    try:
        troppo_grande = not 0 <= int(lunghezza or 0) <= limite
    except ValueError:
        troppo_grande = True
    if troppo_grande:
        return JSONResponse(status_code=413, content={"detail": "Richiesta troppo grande"})
    if limite == LIMITE_ACCOUNT and lunghezza is None and "chunked" in request.headers.get("transfer-encoding", "").lower():
        return JSONResponse(status_code=411, content={"detail": "Manca la lunghezza della richiesta"})
    # Con FANTA_MULTIUTENTE=1 ogni /api/ senza sessione valida si ferma qui (401); spento non succede niente.
    # Il controllo legge il database: si fa in un thread, così un database lento non ferma tutte le altre richieste.
    rifiuto = await run_in_threadpool(rotte_account.controllo_accesso, request)
    if rifiuto is not None:
        rifiuto.headers["Cache-Control"] = "no-store"
        return rifiuto
    # Funzione spenta: le sue rotte rispondono 404 con un messaggio chiaro. «Mostra tutte le funzioni» le riapre, tranne
    # quelle di funzioni.SEMPRE_BLOCCATE (rete e costi): spente dall'amministratore, spente per tutti.
    funzione = funzioni.di_rotta(request.method, request.url.path)
    if funzione and not funzioni.acceso(funzione) and (funzione in funzioni.SEMPRE_BLOCCATE or not await run_in_threadpool(_vede_tutto, request, funzione)):
        return JSONResponse(status_code=404, content={"detail": funzioni.messaggio_spenta(funzione), "funzione": funzione},
                            headers={"Cache-Control": "no-store"})
    # Con gli account i calcoli pesanti non bloccano la richiesta: partono in coda e la richiesta riceve 202 «sto calcolando» (vedi calcolo.py)
    calcolo.in_coda.set(account.multiutente() and request.url.path.startswith("/api/"))
    calcolo.solo_cache.set(bool(getattr(request.state, "solo_widget", False)))     # il token del widget non fa partire calcoli
    # chi chiede, per la parte di ciascuno di calcoli e memorie condivise (limiti.MAX_CALCOLI_UTENTE...); senza account nessuno
    utente = getattr(request.state, "utente", None)
    calcolo.utente_richiesta.set(utente.id if utente is not None and account.multiutente() else None)
    if_none_match = None
    if request.method == "GET" and request.url.path.startswith("/api/") and lingua_testi.della_richiesta(request) == lingua_testi.EN:
        # In inglese l'ETag italiano non vale: la richiesta va avanti senza If-None-Match e il confronto si fa dopo la traduzione
        if_none_match = request.headers.get("if-none-match")
        if if_none_match is not None:
            request.scope["headers"] = [(k, v) for k, v in request.scope["headers"] if k.lower() != b"if-none-match"]
            request.__dict__.pop("_headers", None)          # Starlette tiene una copia in memoria delle intestazioni
        risposta = await _note_in_inglese(request, await chiama(request), if_none_match)
    else:
        risposta = await chiama(request)
    if request.method == "GET" and request.url.path.startswith("/api/") and risposta.status_code in (200, 304) \
            and (risposta.status_code == 304 or "application/json" in risposta.headers.get("content-type", "")):
        _accoda_vary(risposta, "Accept-Language")            # la risposta cambia con la lingua: le copie in memoria devono saperlo
    if request.url.path in RISPOSTE_PER_PERSONA:
        # Vale anche con il token del widget: la copia del telefono si ricontrolla sempre (ETag) e non passa da un account all'altro
        risposta.headers["Cache-Control"] = "private, no-cache"
        _accoda_vary(risposta, "Authorization, Cookie, Accept-Language")
    elif not request.url.path.startswith("/api/"):
        risposta.headers["Cache-Control"] = "no-cache"      # l'iPhone controlla sempre se l'app è cambiata
    elif request.url.path.startswith(("/api/account/", "/api/admin/")):
        risposta.headers["Cache-Control"] = "no-store"      # sessioni e codici non restano in nessuna copia
    elif account.multiutente():                             # con gli account ogni risposta di /api/ è di qualcuno: niente copie condivise
        attuale = risposta.headers.get("cache-control", "")
        risposta.headers["Cache-Control"] = attuale.replace("public", "private") if attuale else "no-store"
    return risposta


DISCO_PIENO = "Il server ha finito lo spazio e non è riuscito a salvare: riprova più tardi. Quello che avevi salvato prima è al sicuro."


def _disco_pieno(e: Exception) -> bool:
    """Vero se la scrittura è fallita perché il disco (o la quota) è pieno: file normali o database SQLite."""
    import errno
    import sqlite3
    if isinstance(e, OSError) and e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)):
        return True
    return isinstance(e, sqlite3.OperationalError) and "disk is full" in str(e).lower()


def _errore_imprevisto(request: Request, e: Exception) -> JSONResponse:
    """Un errore che il codice non si aspettava: 500 con un messaggio in italiano, la traccia resta solo nel log del servizio."""
    import sqlite3
    import traceback
    if isinstance(e, sqlite3.OperationalError) and any(p in str(e).lower() for p in ("locked", "busy")):
        account.evento("database_occupato", percorso=request.url.path)       # momentaneo: l'app riprova da sola dopo Retry-After
        return JSONResponse(status_code=503, content={"detail": "Il server è molto occupato: riprova fra qualche secondo"},
                            headers={"Retry-After": "3", "Cache-Control": "no-store"})
    if _disco_pieno(e):
        logging.getLogger("uvicorn.error").error("Disco pieno: scrittura non riuscita (rotta %s, %s)",
                                                 registro.rotta_di_modello(request), type(e).__name__)
        account.evento("disco_pieno", percorso=request.url.path)               # lo vede chi gestisce il server
        return JSONResponse(status_code=507, content={"detail": DISCO_PIENO}, headers={"Cache-Control": "no-store"})
    traceback.print_exception(e)
    account.evento("errore_interno", percorso=request.url.path, errore=type(e).__name__)
    return JSONResponse(status_code=500, content={"detail": "Errore interno del server: riprova. Se succede ancora, avvisa chi gestisce l'app."},
                        headers={"Cache-Control": "no-store"})


DATI_NON_VALIDI = "Alcuni dati non sono validi: controlla quello che hai scritto e riprova."


def _dati_non_validi(_, e: RequestValidationError) -> JSONResponse:
    """422 senza ripetere i valori ricevuti (nel corpo ci potrebbe essere una password). Il messaggio è una frase sola per chi usa l'app
    (prima diceva «controlla corpo» o il nome interno del campo); i campi che non vanno stanno a parte, in `campi`, per chi scrive un client."""
    # un corpo che non è nemmeno JSON ha come «posizione» il carattere dove si rompe (un numero): si dice «corpo», non «1»
    campi = sorted({"corpo" if err.get("type") == "json_invalid" else ".".join(str(x) for x in err.get("loc", ())[1:]) or "corpo"
                    for err in e.errors()})
    return JSONResponse(status_code=422, content={"detail": DATI_NON_VALIDI, "campi": campi[:20]},
                        headers={"Cache-Control": "no-store"})
_aggiornamento = {"in_corso": False, "righe": [], "errori": []}
_blocco = threading.Lock()


def _db():
    return archivio.apri()


def _contesto_locale() -> Contesto:
    """L'app di sempre (interruttore spento): i file di `lega/` e `dati/`, letti dai moduli al momento della richiesta."""
    return Contesto(utente_id=None, regole=FILE_REGOLE, rose=FILE_ROSE, movimenti=FILE_MOVIMENTI, scelte=scelte.FILE_SCELTE,
                    osservati=osservati.FILE_OSSERVATI, impostazioni_avvisi=notifiche.FILE_IMPOSTAZIONI, icona=FILE_ICONA,
                    iscrizioni_push=notifiche_web.FILE_ISCRIZIONI, diario=diario.FILE, affidabilita=affidabilita.FILE,
                    stato_cambi=notifiche.FILE_STATO, stato_promemoria=notifiche.FILE_PROMEMORIA,
                    stato_riepilogo=notifiche.FILE_RIEPILOGO, stato_avvisi=avvisi_pronta.FILE_STATO, immagini=immagini.CARTELLA)


def _mostra_tutte(request: Request) -> bool:
    """L'impostazione «Mostra tutte le funzioni» di chi chiede (falso se non si sa chi è)."""
    try:
        return stato_utente.leggi_mostra_tutte(lega_corrente(request).impostazioni_avvisi)
    except Exception:  # noqa: BLE001 - nel dubbio la funzione resta spenta
        return False


def _e_amministratore(request: Request) -> bool:
    try:
        return bool(rotte_account.utente_corrente(request).amministratore)
    except Exception:  # noqa: BLE001 - nel dubbio non è l'amministratore
        return False


def _vede_tutto(request: Request, funzione: str) -> bool:
    """Vero se chi chiede ha acceso «Mostra tutte», o è l'amministratore e la funzione è spenta solo di predefinito."""
    return _mostra_tutte(request) or (_e_amministratore(request) and funzioni.origine(funzione)[1] == "predefinito")


def lega_corrente(request: Request) -> Contesto:
    """Dipendenza: i file personali di chi sta chiedendo. Con gli account vengono SOLO dalla sessione (senza sessione: 401);
    mai da un parametro della richiesta, quindi un utente non può nominare i file di un altro."""
    utente = rotte_account.utente_corrente(request)
    if not account.multiutente():
        return _contesto_locale()
    return Contesto.per_utente(utente.id)


def _manda(ctx: Contesto):
    """La funzione che manda gli avvisi di questo utente (i suoi dispositivi e le sue impostazioni)."""
    return lambda *a, **k: notifiche.invia(*a, file_impostazioni=ctx.impostazioni_avvisi, file_iscrizioni=ctx.iscrizioni_push,
                                           ntfy=ctx.ntfy, **k)


def _regole(ctx: Contesto) -> regole.Regole:
    return regole.carica(ctx.regole)


def _rose(ctx: Contesto) -> lega.Rose:
    r = lega.carica(ctx.rose)
    if not r:
        raise HTTPException(409, "Nessuna rosa importata: importale in Squadra > Aggiorna le rose")
    return r


@app.exception_handler(RecursionError)
def _troppo_annidato(_, e: RecursionError):
    """Un JSON annidato a dismisura fa andare in errore il lettore: è una richiesta sbagliata, non un guasto del server."""
    return JSONResponse(status_code=400, content={"detail": "La richiesta non è valida"})


_PACCHETTO = Path(__file__).resolve().parent
_RIGA_RAISE = re.compile(r"(^|:\s*)raise\s+\w")
RICHIESTA_NON_VALIDA = "La richiesta non è valida: controlla i dati e riprova."


def _messaggio_per_l_utente(e: ValueError) -> bool:
    """Vero solo per un `raise ValueError("...")` scritto apposta nel codice dell'app (il messaggio è una frase per chi usa
    l'app). Falso per gli errori delle librerie e di Python (`int("x")`, JSON rotto, date...): il loro testo può contenere
    valori ricevuti o dettagli interni e non va mostrato."""
    if type(e) is not ValueError and not type(e).__module__.startswith("fanta."):
        return False
    passi = traceback.extract_tb(e.__traceback__)
    if not passi:
        return False
    ultimo = passi[-1]
    try:
        dentro = Path(ultimo.filename).resolve().is_relative_to(_PACCHETTO)
    except (OSError, ValueError):
        return False
    return dentro and bool(_RIGA_RAISE.search((ultimo.line or "").strip()))


@app.exception_handler(ValueError)
def _errore_valore(request: Request, e: ValueError):
    if _messaggio_per_l_utente(e):
        codice = getattr(type(e), "codice", None)           # nome breve dell'errore per i client (es. «formazione_non_valida»), facoltativo
        stato = getattr(type(e), "stato", 400)              # 422 per i dati oltre i tetti (regole_testo.TestoTroppoLungo, regole.RegoleTroppoGrandi)
        return JSONResponse(status_code=stato if stato in (400, 422) else 400,
                            content={"detail": str(e)[:500]} | ({"codice": codice} if isinstance(codice, str) else {}))
    codice = secrets.token_hex(4)               # lo stesso codice nel log del servizio: chi gestisce l'app ritrova il caso
    passi = traceback.extract_tb(e.__traceback__)
    dove = f"{Path(passi[-1].filename).name}:{passi[-1].lineno}" if passi else "?"
    logging.getLogger("uvicorn.error").warning("Richiesta non valida id=%s rotta=%s errore=%s in %s", codice,
                                               registro.rotta_di_modello(request), type(e).__name__, dove)
    return JSONResponse(status_code=400, content={"detail": RICHIESTA_NON_VALIDA, "id_errore": codice})


def _sto_calcolando(_, e: calcolo.InCalcolo):
    """Il risultato non è ancora pronto: l'app mostra il marchio animato e riprova da sola dopo `riprova_tra` secondi."""
    return JSONResponse(status_code=202, content={"calcolo": "in_corso", "detail": str(e), "riprova_tra": e.riprova_tra},
                        headers={"Retry-After": str(e.riprova_tra), "Cache-Control": "no-store"})


def _occupato(_, e: calcolo.Occupato):
    return JSONResponse(status_code=429, content={"detail": str(e)}, headers={"Retry-After": str(e.riprova_tra), "Cache-Control": "no-store"})


def _account_non_verificato(_, e: percorsi.DatabaseAccountNonRisponde):
    """Salvataggio non fatto perché il database degli account non risponde (#542): 503 «riprova», mai «salvato». Senza
    Retry-After: l'app non rifà la richiesta da sola, lo decide chi la usa."""
    return JSONResponse(status_code=503, content={"detail": percorsi.NON_VERIFICATO}, headers={"Cache-Control": "no-store"})


app.add_exception_handler(calcolo.InCalcolo, _sto_calcolando)
app.add_exception_handler(calcolo.Occupato, _occupato)
app.add_exception_handler(percorsi.DatabaseAccountNonRisponde, _account_non_verificato)
app.add_exception_handler(account.ErroreAccount, rotte_account.errore_account)
app.add_exception_handler(RequestValidationError, _dati_non_validi)
app.add_exception_handler(Exception, _errore_imprevisto)
app.include_router(rotte_account.router)          # /api/account/... e /api/admin/... (attivi solo con FANTA_MULTIUTENTE=1; "me" risponde sempre)
try:                                              # le foto dei calciatori esistono solo nelle copie private e sono spente di norma; il repository pubblico non ha questo modulo
    from . import rotte_foto
    app.include_router(rotte_foto.router)
except ImportError:
    pass


def _scalda(ctx: Contesto | None = None) -> None:
    """Calcola in anticipo formazione e mercato, così quando apri l'app sono già pronti. Senza `ctx`: per l'utente unico
    (senza account) o per gli utenti attivi di recente (con gli account); con `ctx`: solo per quell'utente."""
    if ctx is None:
        riscaldamento.scalda_tutti(_contesto_locale, _db)
        return
    db = _db()
    try:
        riscaldamento.scalda_contesto(ctx, db)
    except Exception:  # noqa: BLE001 - è solo un'anticipazione: se non riesce, si calcola alla prima richiesta
        pass
    finally:
        db.close()


def _leghe_attive() -> list[regole.Regole]:
    """Le regole delle leghe attive (una senza account; con gli account, quelle di chi ha usato l'app da poco)."""
    return [regole.carica(c.regole) for c in riscaldamento.contesti_da_scaldare(_contesto_locale)]


def _aggiorna_leggero() -> bool | None:
    """Solo le probabili, mai insieme a un aggiornamento completo del servizio. None = occupato (si riprova al prossimo controllo)."""
    if not _blocco.acquire(blocking=False):
        return None
    try:
        return pianificatore.aggiorna_probabili()
    finally:
        _blocco.release()


def _risultati_leggeri(giornate: list[int]) -> bool | None:
    """Solo risultati e voti delle giornate indicate, mai insieme a un aggiornamento completo. None = occupato (si riprova)."""
    if not _blocco.acquire(blocking=False):
        return None
    try:
        return pianificatore.aggiorna_risultati(giornate)
    finally:
        _blocco.release()


def _dopo_giro_leggero() -> None:
    """Dopo le probabili nuove: ricalcolo e avvisi sui cambi (stessi dei comandi `cambi` del server).
    Dentro `_blocco`, come l'aggiornamento completo: non si sovrappongono."""
    with _blocco:
        _scalda()
        db = _db()
        try:
            if account.multiutente():
                avvisi_utenti.esegui("cambi", db)
            else:
                rose_ = lega.carica(FILE_ROSE)
                if rose_ and rose_.mia_squadra:
                    notifiche.cambi(db, regole.carica(FILE_REGOLE), rose_)
        finally:
            db.close()


def _versione_dati() -> str | None:
    db = _db()
    try:
        return consigli._versione(db)
    finally:
        db.close()


def _novita() -> list[dict]:
    try:
        dati = json.loads(FILE_NOVITA.read_text(encoding="utf-8"))
        return dati if isinstance(dati, list) else []
    except (OSError, ValueError):
        return []


def _novita_en() -> dict:
    """Le novità tradotte per le versioni vecchie: {versione: {titolo, voci}} (fanta/contenuti/novita.en.json)."""
    try:
        dati = json.loads(FILE_NOVITA_EN.read_text(encoding="utf-8"))
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError):
        return {}


# In inglese, per le versioni senza traduzione: un testo breve generico invece dell'italiano (collaudo del 2/11/2026).
NOVITA_EN_TITOLO = "Improvements and fixes"
NOVITA_EN_VOCE = "This version has no English description yet. Switch the language to Italian to read the details."


def novita_in_lingua(lingua: str) -> list[dict]:
    """Le novità nella lingua chiesta. In inglese: `titolo_en` e `voci_en` della voce (le mette il bot dai file di novita.d) oppure la
    traduzione di novita.en.json; dove manca, un titolo e una voce generici in inglese (NOVITA_EN_*), mai l'italiano a metà.
    I campi `titolo_en`/`voci_en` non escono mai."""
    elenco, en = _novita(), (_novita_en() if lingua == lingua_testi.EN else {})
    fuori = []
    for v in elenco:
        if not isinstance(v, dict):
            continue
        voce = {k: x for k, x in v.items() if k not in ("titolo_en", "voci_en")}
        if lingua == lingua_testi.EN:
            e = en.get(str(v.get("versione"))) or {}
            titolo = v.get("titolo_en") or e.get("titolo")
            voci = v.get("voci_en") or e.get("voci")
            voce["titolo"] = titolo if isinstance(titolo, str) and titolo.strip() else NOVITA_EN_TITOLO
            if isinstance(voci, list) and voci and len(voci) == len(v.get("voci") or []) and all(isinstance(x, str) for x in voci):
                voce["voci"] = voci
            else:
                voce["voci"] = [NOVITA_EN_VOCE]
        fuori.append(voce)
    return fuori


@app.get("/api/novita")
def novita(request: Request):
    """Elenco delle novità dell'app, dalla più recente. In inglese con ?lingua=en o Accept-Language (le versioni non tradotte restano in italiano)."""
    return JSONResponse(novita_in_lingua(lingua_testi.della_richiesta(request)), headers={"Vary": "Accept-Language"})


# ---------------- stato e aggiornamento ----------------
def _errori_per(errori: list, amministratore: bool) -> list:
    """Gli errori dell'ultimo aggiornamento: per intero solo all'amministratore. Agli altri solo QUALE passo non è riuscito
    (il testo dell'eccezione può contenere indirizzi, percorsi o dettagli interni)."""
    if amministratore:
        return errori
    return [f"{e.split(':', 1)[0][:60]}: non riuscito" for e in errori if isinstance(e, str)]


@app.get("/api/stato")
def stato(request: Request, ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        ultimo = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
        st = consigli.stagione_corrente()
        r = lega.carica(ctx.rose)
        rg = _regole(ctx)
        prossima = consigli.giornata_da_giocare(db, st, rg)
        return {
            "stagione": st, "prossima_giornata": prossima,
            "prima_giornata_lega": rg.prima_giornata_lega,
            "prossima_giornata_lega": None if prossima is None else regole.serie_a_a_lega(prossima, rg),
            "ultimo_aggiornamento": ultimo["quando"] if ultimo else None,
            "errori_ultimo": _errori_per(json.loads(ultimo["dettaglio"]) if ultimo and ultimo["dettaglio"] else [],
                                         _e_amministratore(request)),
            "mia_squadra": r.mia_squadra if r else None, "rose_importate": bool(r and r.squadre),
            "nome_lega": rg.nome_lega, "aggiornamento_in_corso": _aggiornamento["in_corso"],
            "versione": (_novita() or [{"versione": "?"}])[0]["versione"],
            "sorgente": testi_legali.sorgente(),          # indirizzo del codice sorgente (AGPL); "" se non impostato
        }
    finally:
        db.close()


SALUTE_PER_IP = (600, 3600)          # richieste e secondi per indirizzo: il controllo esterno chiede ogni pochi minuti
_salute_orari: dict[str, list[float]] = {}      # solo in memoria (nessuna scrittura su disco): indirizzo -> orari delle richieste recenti
_salute_lock = threading.Lock()
_salute_pulizia = [0.0]


def _salute_troppe(ip: str, adesso: float | None = None) -> int:
    """0 se la richiesta passa (e la conta), altrimenti i secondi da aspettare. Limite per indirizzo, tutto in memoria."""
    massimo, finestra = SALUTE_PER_IP
    adesso = time.monotonic() if adesso is None else adesso
    with _salute_lock:
        if adesso - _salute_pulizia[0] > 300 or len(_salute_orari) > 10000:      # ogni tanto si dimenticano gli indirizzi fermi
            _salute_pulizia[0] = adesso
            for k in [k for k, v in _salute_orari.items() if not v or adesso - v[-1] > finestra]:
                del _salute_orari[k]
            if len(_salute_orari) > 10000:
                _salute_orari.clear()
        orari = [t for t in _salute_orari.get(ip, []) if adesso - t < finestra]
        if len(orari) >= massimo:
            _salute_orari[ip] = orari
            return max(1, int(finestra - (adesso - orari[0])) + 1)
        orari.append(adesso)
        _salute_orari[ip] = orari
        return 0


@app.api_route("/api/salute", methods=["GET", "HEAD"])
def salute(request: Request):
    """Rotta PUBBLICA per il monitoraggio (anche con gli account accesi): il sito è vivo e i dati sono freschi? Nessun dato personale.
    Database dei dati illeggibile: 503 con ok:false. Nessun aggiornamento registrato: ok:true ma ultimo_aggiornamento null (allarme)."""
    intestazioni = {"Cache-Control": "no-store"}
    ip = rotte_account.ip_reale(request)
    if ip:                                                  # in locale (senza indirizzo visibile) non c'è limite
        attesa = _salute_troppe(ip)
        if attesa:
            return JSONResponse({"detail": "Troppe richieste: riprova fra poco", "riprova_tra": attesa}, status_code=429,
                                headers=intestazioni | {"Retry-After": str(attesa)})
    quando = None
    try:
        db = _db()
        try:
            r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
            quando = r["quando"] if r else None
        finally:
            db.close()
    except Exception:                                       # database dei dati rotto o assente: il monitor deve vederlo
        return JSONResponse({"ok": False, "ultimo_aggiornamento": None}, status_code=503, headers=intestazioni)
    return JSONResponse({"ok": True, "ultimo_aggiornamento": quando}, headers=intestazioni)


@app.get("/api/stato-dati")
def stato_dei_dati():
    """Fonti, freschezza dei dati, errori e quanto il modello azzecca (pagina "Stato dei dati")."""
    db = _db()
    try:
        return stato_dati.riepilogo(db, consigli.stagione_corrente())
    finally:
        db.close()


@app.post("/api/aggiorna")
def avvia_aggiornamento():
    if not _blocco.acquire(blocking=False):
        return {"avviato": False, "messaggio": "Aggiornamento già in corso"}

    def lavoro():
        try:
            _aggiornamento["errori"] = aggiorna.esegui(scrivi=_aggiornamento["righe"].append)
            _scalda()
        except Exception as e:  # noqa: BLE001 - va riportato all'app, non deve far cadere il server
            _aggiornamento["errori"].append(str(e))
        finally:
            _aggiornamento["in_corso"] = False
            _blocco.release()

    _aggiornamento.update(in_corso=True, righe=[], errori=[])
    threading.Thread(target=lavoro, daemon=True).start()
    return {"avviato": True}


@app.get("/api/aggiorna")
def stato_aggiornamento():
    return _aggiornamento


# ---------------- formazione e giocatori ----------------
def _json_diretto(dati):
    """Risposta JSON già pronta per i dati grandi che sono già semplici (liste, numeri, testi): salta `jsonable_encoder` di FastAPI,
    che ripassa ogni elemento uno per uno (circa un terzo del tempo di una formazione già in cache). Il testo che esce è identico.
    Se dentro c'è qualcosa che JSON non sa scrivere, si restituisce `dati` e ci pensa FastAPI come prima."""
    try:
        return JSONResponse(dati)
    except (TypeError, ValueError):
        return dati


@app.get("/api/formazione")
def formazione(request: Request, squadra: str | None = None, giornata: int | None = Query(None, ge=1, le=MAX_GIORNATA), ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        r = _regole(ctx)
        saltata = None if squadra or giornata else _giornata_saltata(db, r, ctx, request)
        f = consigli.formazione(db, r, _rose(ctx), squadra, saltata + 1 if saltata else giornata)
        if saltata:
            f = f | {"giornata_saltata": saltata, "giornata_saltata_lega": regole.serie_a_a_lega(saltata, r)}
        if not squadra:
            _copia_automatica(db, ctx, f)
            stato_scelta = _stato_scelta(ctx, f, r)
            if stato_scelta:
                f = f | {"stato_scelta": stato_scelta}          # una copia: la formazione in cache non cambia
        # dopo la scadenza: niente etichette delle probabili, lo stato vero della giornata (fasi.py; f resta intatta nella cache)
        f = fasi.formazione_a_giornata_iniziata(f, db, r, consigli.stagione_corrente(), datetime.now(), _stati_live())
        return _json_diretto(_con_bloccati(db, f))
    finally:
        db.close()


def _con_bloccati(db, f: dict) -> dict:
    """Campo facoltativo `bloccati` (#373): con la formazione ancora aperta, gli id dei giocatori di un anticipo già cominciato, che
    nella lega non si spostano più (web e iPhone non li fanno sostituire; il salvataggio lo controlla con `_non_sposta_i_fermi`).
    Senza anticipi cominciati, o dopo la scadenza (`iniziata`), la risposta non cambia. Una copia: `f` può venire dalla cache."""
    if f.get("iniziata"):
        return f
    squadre = consigli._anticipi_iniziati(db, consigli.stagione_corrente(), f.get("giornata"))
    ids = scelte.bloccati(f.get("schede") or {}, squadre)
    return f | {"bloccati": ids} if ids else f


def _giornata_saltata(db, r, ctx: Contesto, request: Request) -> int | None:
    """La giornata in corso, se l'utente è entrato dopo la sua scadenza e non ha una formazione per lei: allora la Formazione
    mostra la prossima (fasi.entrato_dopo_la_scadenza, come Oggi). None in tutti gli altri casi (e senza account)."""
    try:
        dal = _ora_locale(rotte_account.utente_corrente(request).creato)
    except HTTPException:
        return None
    if dal is None:
        return None
    stagione = consigli.stagione_corrente()
    g = consigli.giornata_da_giocare(db, stagione, r)
    if not g:
        return None
    scad = avvisi_pronta.scadenza(avvisi_pronta.prima_partita(db, stagione, g), r)
    if scad is None or datetime.now() < scad or avvisi_pronta.prima_partita(db, stagione, g + 1) is None:
        return None
    return g if fasi.entrato_dopo_la_scadenza(stagione, g, scad, dal, ctx.scelte, getattr(ctx, "diario", None)) else None


def _stato_scelta(ctx: Contesto, f: dict, regole_: regole.Regole) -> str | None:
    """Il campo `stato_scelta` della tua Formazione: `nessuna`, `valida` o `non_valida`, con la regola unica della scelta
    (`scelte.motivo_non_valida`) sui giocatori che la Formazione può schierare (`schede`). A giornata chiusa dice quale formazione
    vale: la tua scelta se `valida`, altrimenti la consigliata (come Oggi, il riepilogo e il Diario). None se non si sa."""
    try:
        ruoli = {int(k): x.get("ruolo") for k, x in (f.get("schede") or {}).items() if isinstance(x, dict)}
    except (TypeError, ValueError):
        return None
    return scelte.stato(scelte.leggi(consigli.stagione_corrente(), f.get("giornata"), ctx.scelte), ruoli, regole_)


def _copia_automatica(db, ctx: Contesto, f: dict) -> None:
    """Finché la formazione è aperta (prima della prima partita) e l'utente non ha scelto, tiene una copia della consigliata:
    dopo la scadenza resta quella, e il diario può dire «salvata automaticamente». Non deve mai far fallire la risposta.
    La stessa copia la fa il server da solo poco prima della scadenza, anche se nessuno apre l'app (`copia_scadenza.py`)."""
    try:
        g = f.get("giornata")
        if not g or not f.get("titolari"):
            return
        stagione = consigli.stagione_corrente()
        prima = avvisi_pronta.scadenza(avvisi_pronta.prima_partita(db, stagione, g), _regole(ctx))
        if prima is None or datetime.now() >= prima:
            return
        copia_scadenza.salva(f, stagione, ctx.scelte, ctx.diario)    # copia e consigliata di allora per il diario (si congela alla scadenza)
    except Exception:                       # noqa: BLE001 - la copia è un di più
        pass


class FormazioneScelta(BaseModel):
    titolari: list[int]
    squadra: str | None = None
    giornata: int | None = Field(None, ge=1, le=MAX_GIORNATA)
    salva: bool = False


def _etag_scelta(ctx: Contesto, giornata: int) -> str:
    return versioni.etag_dati(scelte.leggi(consigli.stagione_corrente(), giornata, ctx.scelte))


FORMAZIONE_CHIUSA = "La giornata è già iniziata: la formazione non si può più cambiare."


def _formazione_chiusa(db, ctx: Contesto, giornata: int | None) -> JSONResponse | None:
    """409 con `codice: "formazione_chiusa"` se la scadenza della lega per questa giornata è passata (stessa regola della Formazione
    e di Oggi, `fasi.iniziata`): dopo la scadenza nessuno cambia più la scelta, amministratore compreso. La copia automatica alla
    scadenza (`copia_scadenza.py`) scrive da sola PRIMA della scadenza e non passa di qui. Calendario illeggibile: si lascia scrivere."""
    try:
        chiusa = fasi.iniziata(db, _regole(ctx), consigli.stagione_corrente(), giornata, datetime.now())
    except sqlite3.Error:
        return None
    if not chiusa:
        return None
    return JSONResponse(status_code=409, content={"detail": FORMAZIONE_CHIUSA, "codice": "formazione_chiusa"},
                        headers={"Cache-Control": "no-store"})


def _fermi(db, ctx: Contesto, giornata: int | None) -> tuple[int, dict, list[int]] | None:
    """Anticipi già cominciati (#373): (giornata, consigliata mostrata, id dei giocatori della tua rosa che non si spostano più), o None
    se nessuno della rosa gioca una partita già cominciata. «Cominciata» è la regola della consigliata (`consigli._anticipi_iniziati`,
    #368, calendario e orario). La consigliata è quella di `consigli.formazione`, già in cache dopo `consigli.valuta`."""
    squadre = consigli._anticipi_iniziati(db, consigli.stagione_corrente(), giornata) if giornata else ()
    if not squadre:
        return None
    f = consigli.formazione(db, _regole(ctx), _rose(ctx), None, giornata)
    ids = scelte.bloccati(f.get("schede") or {}, squadre)
    return (giornata, f, ids) if ids else None


def _non_sposta_i_fermi(ctx: Contesto, regole_: regole.Regole, fermi: tuple[int, dict, list[int]] | None,
                        nuovi: list[int] | None = None) -> None:
    """400 `giocatore_bloccato` (`scelte.GiocatoreBloccato`) se i titolari `nuovi` (None = la consigliata: si torna a lei) spostano un
    giocatore fermo (`_fermi`) rispetto alla formazione che vale adesso: la scelta salvata se vale (regola unica della scelta),
    altrimenti la consigliata. Si chiama dentro il lucchetto delle scelte: la scelta letta qui è quella che si sovrascrive."""
    if fermi is None:
        return
    giornata, f, ids = fermi
    schede = {int(k): x for k, x in (f.get("schede") or {}).items() if isinstance(x, dict)}
    consigliata = [int(g["id"]) for g in f.get("titolari") or []]
    valida = scelte.che_vale(scelte.leggi(consigli.stagione_corrente(), giornata, ctx.scelte),
                             {i: x.get("ruolo") for i, x in schede.items()}, regole_)
    scelte.controlla_bloccati(ids, valida["titolari"] if valida else consigliata, consigliata if nuovi is None else nuovi,
                              {i: x.get("nome") for i, x in schede.items()})


@app.post("/api/formazione/valuta")
def valuta_formazione(dati: FormazioneScelta, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """Punti attesi di una formazione scelta a mano. Con salva=true la ricorda come "la mia scelta" della giornata
    (solo prima della scadenza: dopo 409 `formazione_chiusa`; valutare senza salvare resta possibile)."""
    # Se gli 11 sono quelli della consigliata («Salva questa») la scelta ha anche `era_consigliata`: «Da fare» poi non propone
    # cambi (da_fare.py, #333). Conta anche la consigliata che GET /api/formazione ti ha mostrato (istantanea del Diario), se nel
    # frattempo i dati si sono aggiornati. Qui un commento e non nella docstring, che finisce nel contratto docs/openapi.json.
    # Dopo l'inizio di un anticipo i suoi giocatori non si spostano più: un salvataggio che lo fa risponde 400 `giocatore_bloccato`
    # (#373, `_fermi` e `_non_sposta_i_fermi`).
    db = _db()
    try:
        regole_, rose_ = _regole(ctx), _rose(ctx)
        r = consigli.valuta(db, regole_, rose_, dati.titolari, dati.squadra, dati.giornata)
        if dati.salva and not dati.squadra:
            chiusa = _formazione_chiusa(db, ctx, r["giornata"])
            if chiusa is not None:
                return chiusa
            era = da_fare.era_consigliata(db, regole_, rose_, dati.titolari, r["giornata"], ctx.diario)     # anche quella mostrata
            fermi = _fermi(db, ctx, r["giornata"])
            with versioni.blocco("scelte"):
                versioni.controlla(request, _etag_scelta(ctx, r["giornata"]))
                _non_sposta_i_fermi(ctx, regole_, fermi, dati.titolari)
                scelte.salva(consigli.stagione_corrente(), r["giornata"], dati.titolari, r["modulo"], ctx.scelte, era_consigliata=era)
                response.headers["ETag"] = _etag_scelta(ctx, r["giornata"])
        return r
    finally:
        db.close()


@app.get("/api/scelta")
def leggi_scelta(response: Response, giornata: int = Query(ge=1, le=MAX_GIORNATA), ctx: Contesto = Depends(lega_corrente)):
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, ctx.scelte)
    response.headers["ETag"] = versioni.etag_dati(scelta)
    return scelta


@app.delete("/api/scelta")
def cancella_scelta(request: Request, response: Response, giornata: int = Query(ge=1, le=MAX_GIORNATA), ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        # dopo la scadenza la scelta non si toglie più da qui (409). Unica eccezione voluta: POST /api/diario/schierata riscrive
        # la scelta di una giornata FINITA (l'utente dice cosa ha schierato davvero nella lega)
        chiusa = _formazione_chiusa(db, ctx, giornata)
        # tornare alla consigliata non sposta chi gioca un anticipo già cominciato (#373); senza una tua scelta non cambia niente
        fermi = None if chiusa is not None or scelte.leggi(consigli.stagione_corrente(), giornata, ctx.scelte) is None \
            else _fermi(db, ctx, giornata)
    finally:
        db.close()
    if chiusa is not None:
        return chiusa
    with versioni.blocco("scelte"):
        versioni.controlla(request, _etag_scelta(ctx, giornata))
        _non_sposta_i_fermi(ctx, _regole(ctx), fermi)
        scelte.cancella(consigli.stagione_corrente(), giornata, ctx.scelte)
        response.headers["ETag"] = _etag_scelta(ctx, giornata)
    return {"ok": True}


def _stato_vero(schede: list[dict], db, r, giornata: int) -> list[dict]:
    """Dopo la scadenza ogni scheda dell'elenco dei Giocatori mostra lo stato vero della giornata («Voto in arrivo»,
    «Da giocare»...) invece delle probabili, come Rosa, scheda e Formazione. Prima della scadenza le schede restano com'erano.
    Le voci senza previsione (`assente`) non si toccano."""
    stagione = consigli.stagione_corrente()
    if not schede or not fasi.iniziata(db, r, stagione, giornata, datetime.now()):
        return schede
    nuove = fasi.schede_a_giornata_iniziata([x for x in schede if not x.get("assente")], db, r, stagione, giornata,
                                            datetime.now(), _stati_live())
    return [nuove.get(int(x["id"]), x) if not x.get("assente") else x for x in schede]


@app.get("/api/osservati")
def lista_osservati(response: Response, ctx: Contesto = Depends(lega_corrente)):
    """I giocatori osservati con la previsione di questa giornata e di chi sono (o svincolati)."""
    response.headers["ETag"] = versioni.etag_file(ctx.osservati)
    db = _db()
    try:
        prev, giornata, _ = consigli.previsioni(db, _regole(ctx))
        r = lega.carica(ctx.rose)
        proprietari = {g.id: s.nome for s in r.squadre for g in s.giocatori if g.id is not None} if r else {}
        giocatori = []
        for i in osservati.leggi(ctx.osservati):
            if i in prev.index:
                x = consigli.scheda_previsione(i, prev.loc[i])
            else:                                   # non gioca questa giornata: solo i dati del listone
                riga = db.execute("SELECT id, nome, ruolo, squadra, quotazione FROM calciatori WHERE id = ?", (i,)).fetchone()
                if not riga:
                    continue
                x = {"id": i, "nome": riga["nome"], "ruolo": riga["ruolo"], "squadra": riga["squadra"], "assente": True}
            x["proprietario"] = proprietari.get(i)
            giocatori.append(x)
        stagione = consigli.stagione_corrente()
        in_gioco = [x for x in giocatori if not x.get("assente")]
        if in_gioco and fasi.iniziata(db, _regole(ctx), stagione, giornata, datetime.now()):
            # dopo la scadenza lo stato vero della giornata («Partita in corso», «Voto in arrivo»...), come la Rosa e la Formazione
            nuove = fasi.schede_a_giornata_iniziata(in_gioco, db, _regole(ctx), stagione, giornata, datetime.now(), _stati_live())
            giocatori = [nuove.get(x["id"], x) | {"proprietario": x.get("proprietario")} if not x.get("assente") else x
                         for x in giocatori]
        return {"giornata": giornata, "giocatori": giocatori}
    finally:
        db.close()


@app.put("/api/osservati/{i}")
def osserva(request: Request, response: Response, i: int = FPath(ge=1, le=MAX_ID_CALCIATORE), ctx: Contesto = Depends(lega_corrente)):
    # `le`: un numero più grande di quelli che sqlite sa cercare bloccherebbe per sempre l'elenco degli osservati (errore 500)
    # Solo giocatori del listone (tabella `calciatori`, la stessa che usa GET /api/osservati): un codice inventato verrebbe salvato,
    # non comparirebbe mai e occuperebbe uno dei MASSIMO posti. Quelli già salvati e non validi si tolgono al primo salvataggio.
    db = _db()
    try:
        if not osservati.nel_listone(db, [i]):
            raise HTTPException(404, "Giocatore non trovato nel listone")
        with versioni.blocco("osservati"):
            versioni.controlla(request, versioni.etag_file(ctx.osservati))
            elenco = osservati.aggiungi(i, ctx.osservati, validi=osservati.nel_listone(db, osservati.leggi(ctx.osservati)))
            response.headers["ETag"] = versioni.etag_file(ctx.osservati)
    finally:
        db.close()
    return {"osservati": elenco}


@app.delete("/api/osservati/{i}")
def non_osservare(i: int, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    with versioni.blocco("osservati"):
        versioni.controlla(request, versioni.etag_file(ctx.osservati))
        elenco = osservati.togli(i, ctx.osservati)
        response.headers["ETag"] = versioni.etag_file(ctx.osservati)
    return {"osservati": elenco}


class CreditiSquadre(BaseModel):
    crediti: dict[str, int]


class _BloccoRose:
    """Le rose si modificano una richiesta alla volta (crediti, mia squadra, importazione): i thread del servizio con un
    `threading.Lock`, e con gli account anche gli altri processi (il comando `importa-per-conto-di`) con un blocco su file."""

    def __init__(self):
        self._thread = threading.Lock()
        self._file = None

    def __enter__(self):
        self._thread.acquire()
        try:
            if account.multiutente():
                self._file = blocco.BloccoFile(percorsi.cartella_account() / "blocco-rose.lock")
                self._file.__enter__()
        except TimeoutError as e:
            self._thread.release()
            raise HTTPException(503, str(e)) from None
        except BaseException:
            self._thread.release()
            raise
        return self

    def __exit__(self, *_):
        try:
            if self._file is not None:
                self._file.__exit__()
        finally:
            self._file = None
            self._thread.release()


_scrittura_rose = _BloccoRose()


@app.put("/api/crediti")
def imposta_crediti(dati: CreditiSquadre, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    with _scrittura_rose:
        versioni.controlla(request, versioni.etag_file(ctx.rose))
        risposta = _imposta_crediti(dati, ctx)
        response.headers["ETag"] = versioni.etag_file(ctx.rose)
        return risposta


def _imposta_crediti(dati: CreditiSquadre, ctx: Contesto):
    """Crediti residui di ogni squadra (non sono nell'Excel di Leghe: si leggono dalla schermata Squadre e si inseriscono qui)."""
    r = _rose(ctx)
    nomi_ = {s.nome for s in r.squadre}
    for nome, c in dati.crediti.items():
        if nome not in nomi_:
            raise ValueError(f"Squadra non trovata: {nome}")
        if c < 0 or c > 100000:
            raise ValueError(f"Crediti non validi per {nome}")
    for s in r.squadre:
        if s.nome in dati.crediti:
            s.crediti_residui = dati.crediti[s.nome]
    lega.salva(r, ctx.rose)
    return {"squadre": [{"nome": s.nome, "crediti_residui": s.crediti_residui} for s in r.squadre]}


@app.get("/api/affidabilita")
def leggi_affidabilita(ctx: Contesto = Depends(lega_corrente)):
    """Il risultato dell'ultima prova del modello sulle giornate passate (vuoto se non è ancora stata fatta)."""
    return affidabilita.carica(ctx.affidabilita) or {"righe": [], "sintesi": None}


class SchierataDiario(BaseModel):
    giornata: int = Field(ge=1, le=MAX_GIORNATA)
    tipo: str                               # "consigliata" | "manuale"
    titolari: list[int] | None = None       # per "manuale": gli 11 titolari
    modulo: str | None = None               # facoltativo: il modulo si ricava dai titolari
    stagione: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")      # quella della voce; senza (client vecchi): la stagione in corso


@app.post("/api/diario/schierata")
def diario_schierata(dati: SchierataDiario, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """«Ho schierato la consigliata» (o una formazione a mano) per una giornata già finita: salva la scelta e rifà solo quella voce
    del diario. Al massimo 30 all'ora per utente (il «sto calcolando» ripetuto con gli stessi dati vale una volta). Risponde con la voce del diario.
    Solo per la stagione in corso: una voce di una stagione passata risponde 400 (non scrive sulla giornata con lo stesso numero di quest'anno)."""
    try:
        diario.controlla_stagione(dati.stagione)                           # subito: né coda né limiti per una voce dell'anno prima
    except diario.SchierataNonValida as e:
        raise HTTPException(400, str(e)) from None
    versioni.controlla(request, _etag_scelta(ctx, dati.giornata))          # subito, prima del lavoro lungo (si ricontrolla sotto, al momento di scrivere)
    regole_, rose_ = _regole(ctx), _rose(ctx)
    firma_regole, firma_rose = repr(regole_), (consigli._impronta_rose(rose_), rose_.mia_squadra)
    try:
        firma = ctx.diario.stat().st_mtime_ns if ctx.diario.exists() else 0
    except OSError:
        firma = 0
    db = _db()
    prenotazione = None
    try:
        chiave = ("schierata", ctx.utente_id, dati.giornata, dati.tipo, tuple(dati.titolari or []), firma_regole, firma_rose, firma,
                  consigli._versione(db))
        prenotazione = limiti.prenota_ora(ctx, "schierate", chiave)          # controlla e segna insieme (429 al tetto)
        # le simulazioni girano FUORI dal blocco delle scelte (con gli account in coda: 202 «sto calcolando»); il blocco serve solo a scrivere
        try:
            voce, scelti = calcolo.ottieni(chiave, lambda d: diario.prepara_schierata(d, regole_, rose_, dati.giornata, dati.tipo, dati.titolari,
                                                                                        ctx.diario, stagione=dati.stagione), db)
        except diario.SchierataNonValida as e:
            raise HTTPException(400, str(e)) from None
        with versioni.blocco("scelte"):
            versioni.controlla(request, _etag_scelta(ctx, dati.giornata))
            if repr(_regole(ctx)) != firma_regole or (consigli._impronta_rose(_rose(ctx)), _rose(ctx).mia_squadra) != firma_rose:
                raise HTTPException(409, "Le regole o la rosa sono cambiate mentre calcolavo: riprova")
            diario.scrivi_schierata(voce, scelti, dati.giornata, dati.tipo, ctx.diario, ctx.scelte)
            response.headers["ETag"] = _etag_scelta(ctx, dati.giornata)
        return voce
    except (calcolo.InCalcolo, calcolo.Occupato):
        raise                                                              # il posto resta preso: il nuovo tentativo con gli stessi dati non conta
    except BaseException:
        if prenotazione is not None:
            prenotazione.annulla()                                         # fallito subito: il posto si restituisce
        raise
    finally:
        db.close()


@app.get("/api/diario")
def leggi_diario(ctx: Contesto = Depends(lega_corrente)):
    """Giornata per giornata: la formazione che hai schierato contro quella consigliata, con punti attesi e fatti."""
    r = diario.elenco(ctx.diario, _regole(ctx))
    r["precisione"] = precisione.riassunto(r["giornate"])          # «Quanto ci abbiamo preso» (campo nuovo: i client vecchi lo ignorano)
    r["precisione"]["serie_a"] = None
    try:
        db = _db()
    except sqlite3.Error:                                          # archivio occupato o assente: il Diario si apre lo stesso, senza la riga
        return r
    try:
        try:
            r["precisione"]["serie_a"] = precisione.serie_a(db)    # la riga su tutta la Serie A, dal registro delle giornate (#374)
        except sqlite3.Error:
            r["precisione"]["serie_a"] = None
        if not r["giornate"]:
            r["motivo_vuoto"] = diario.motivo_vuoto(db, _regole(ctx), _rose(ctx))          # campo facoltativo: i client vecchi lo ignorano
    finally:
        db.close()
    return r


@app.get("/api/stagione")
def stato_stagione(ctx: Contesto = Depends(lega_corrente)):
    """Le rose sono della stagione in corso o di una passata? (serve al passaggio di stagione)"""
    return cambio_stagione.stato(lega.carica(ctx.rose), ctx.rose, consigli.stagione_corrente())


@app.post("/api/nuova-stagione")
def nuova_stagione(ctx: Contesto = Depends(lega_corrente)):
    """Archivia rose, regole, movimenti, scelte e osservati della stagione finita in lega/archivio/ e riparte da rose vuote."""
    return cambio_stagione.archivia_e_riparti(_rose(ctx), ctx.rose, consigli.stagione_corrente(), _regole(ctx).crediti_iniziali,
                                              [ctx.scelte, ctx.osservati])


@app.get("/api/asta")
def piano_asta(modo: str = "estiva", ctx: Contesto = Depends(lega_corrente)):
    """Prezzi consigliati e budget per reparto (stime per orientarsi). modo=riparazione: solo gli svincolati, per l'asta di febbraio."""
    db = _db()
    try:
        r = lega.carica(ctx.rose)
        v, regole_ = consigli.valori_scambi(db, _regole(ctx)), _regole(ctx)
        if modo == "riparazione":
            return asta.piano_riparazione(v, regole_, _rose(ctx))
        return asta.piano(v, regole_, len(r.squadre) if r and r.squadre else 10)
    finally:
        db.close()


@app.get("/api/formazione/testo", response_class=PlainTextResponse)
def formazione_testo(ctx: Contesto = Depends(lega_corrente)):
    """La formazione come testo (la tua scelta salvata se c'è, altrimenti la consigliata): per i Comandi di Apple."""
    db = _db()
    try:
        regole_, rose_ = _regole(ctx), _rose(ctx)
        f = consigli.formazione(db, regole_, rose_)
        scelta = scelte.leggi(consigli.stagione_corrente(), f["giornata"], ctx.scelte)
        if scelta:
            try:
                r = consigli.valuta(db, regole_, rose_, scelta["titolari"], None, f["giornata"])
                return consigli.testo_formazione(f, r["modulo"], scelta["titolari"], r["panchina"])
            except ValueError:
                pass                               # la rosa è cambiata: vale la consigliata
        m = next(x for x in f["moduli"] if x["modulo"] == f["modulo"])
        return consigli.testo_formazione(f, m["modulo"], m["titolari"], m["panchina"])
    finally:
        db.close()


@app.get("/api/confronto")
def confronto(a: int, b: int, giornata: int | None = Query(None, ge=1, le=MAX_GIORNATA), squadra: str | None = None, modulo: str | None = None, livello: int = 0, ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        r = lega.carica(ctx.rose)
        return consigli.confronto(db, _regole(ctx), a, b, giornata, rose=r if r and r.mia_squadra or (r and squadra) else None,
                                  nome_squadra=squadra, modulo=modulo, livello=livello)
    finally:
        db.close()


@lru_cache(maxsize=4096)
def _nome_normalizzato(nome: str) -> str:
    return nomi.normalizza(nome)


@app.get("/api/giocatori")
def cerca_giocatori(q: str = "", limite: int = 15, tutti: bool = False):
    """Ricerca per nome nel listone (anche con accenti o iniziali diverse, e per nome proprio: «Lautaro»). Con `tutti=1` l'elenco
    intero (circa 600 righe, senza ordine particolare): l'app lo scarica una volta e cerca sul dispositivo, così ogni tasto
    risponde subito. `nome_completo` (facoltativo, solo per chi lo ha): nome e cognome per esteso, per cercare anche con quello."""
    db = _db()
    try:
        righe = db.execute("SELECT id, nome, ruolo, squadra, quotazione FROM calciatori").fetchall()
    finally:
        db.close()
    completi = listone.nomi_completi()
    elenco = [{**dict(r), **({"nome_completo": completi[r["id"]]} if r["id"] in completi else {})} for r in righe]
    if tutti:
        return [_con_avatar(g) for g in elenco]
    n = nomi.normalizza(q)
    if not n:
        return []
    chiavi = {g["id"]: (_nome_normalizzato(g["nome"]), _nome_normalizzato(g.get("nome_completo", ""))) for g in elenco}
    trovati = [g for g in elenco if any(n in k for k in chiavi[g["id"]])]
    trovati.sort(key=lambda g: (not any(k.startswith(n) for k in chiavi[g["id"]]), -g["quotazione"]))
    return [_con_avatar(g) for g in trovati[:max(1, min(limite, 100))]]


def _con_avatar(g: dict) -> dict:
    """Aggiunge `avatar` (tratti grossolani per il volto illustrato) solo a chi li ha: campo facoltativo, i client vecchi lo ignorano."""
    tratti = avatar.di(g.get("id"))
    if tratti:
        g["avatar"] = tratti
    return g


@app.get("/api/avatar")
def tratti_avatar():
    """Tratti di tutti i giocatori che li hanno, in un colpo solo (l'app li scarica una volta). Dati comuni, nessuna foto."""
    return {"versione": 3, "tratti": {str(k): v for k, v in avatar.tutti().items()}}


@app.get("/api/oggi")
def oggi(request: Request, certificato_giorni: int | None = Query(None, ge=-3650, le=3650), ctx: Contesto = Depends(lega_corrente)):
    """La schermata Oggi. In più `da_fare`: le cose da sbrigare, in ordine (vedi da_fare.py e docs/API.md). `certificato_giorni`
    (facoltativo) lo manda l'app iPhone: giorni che restano al certificato dell'app (il server non può saperlo)."""
    db = _db()
    try:
        try:
            rose_ = _rose(ctx)
        except HTTPException as e:
            if e.status_code != 409:
                raise
            corpo = gestione.oggi_senza_rose(db, regole=_regole(ctx))           # account nuovo: un benvenuto, non un errore (200 con `senza_rose`)
            corpo["da_fare"] = da_fare.senza_rose(getattr(ctx, "impostazioni_avvisi", None))
            return corpo
        r = _regole(ctx)
        try:
            utente = rotte_account.utente_corrente(request)
            admin, dal = utente.amministratore, _ora_locale(utente.creato)
        except HTTPException:
            admin, dal = False, None
        corpo = dict(gestione.oggi(db, r, rose_, file_scelte=ctx.scelte, file_diario=getattr(ctx, "diario", None),
                                   live_partite=_stati_live(), dal=dal))
        admin = admin and not getattr(request.state, "solo_widget", False)     # il token del widget non vede le voci da admin
        corpo["da_fare"] = da_fare.costruisci(db, r, rose_, corpo, ctx, certificato_giorni, amministratore=admin,
                                              lingua=lingua_testi.della_richiesta(request), dal=dal)
        return corpo
    finally:
        db.close()


def _ora_locale(quando: str | None) -> datetime | None:
    """Una data salvata con il fuso (per esempio la nascita dell'account, in UTC) nell'ora locale del server, come il calendario."""
    try:
        d = datetime.fromisoformat(str(quando))
    except (TypeError, ValueError):
        return None
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def _stati_live() -> dict:
    """Lo stato in diretta delle partite ({(casa, trasferta): partita}) per le fasi di Oggi: solo la cache, nessuna richiesta esterna."""
    try:
        return live.unico.istantanea()["partite"] if live.unico else {}
    except Exception:                                        # noqa: BLE001 - senza diretta Oggi usa il calendario
        return {}


def _live_per_widget() -> dict:
    """Versione piccola per il widget: stato, minuto e punteggio di ogni partita, solo i marcatori (niente cartellini)."""
    c = _risposta_live()
    return {"aggiornato_il": c["aggiornato_il"], "fonte": c["fonte"], "in_corso": c["in_corso"],
            "partite": [p | {"eventi": [e for e in p["eventi"] if e["tipo"] != "giallo"][:8]} for p in c["partite"]]}


def _calendario_live() -> list[dict]:
    db = _db()
    try:
        return live.calendario_da_db(db)
    finally:
        db.close()


def _risposta_live() -> dict:
    """Le partite del turno con lo stato in diretta. Legge solo la cache del raccoglitore: nessuna richiesta esterna."""
    db = _db()
    try:
        stagione = consigli.stagione_corrente()
        giornata = consigli.prossima_giornata(db, stagione)
        righe = db.execute("SELECT data, casa, trasferta, giornata, giocata, gol_casa, gol_trasferta FROM partite "
                           "WHERE stagione = ? AND giornata = ? ORDER BY data", (stagione, giornata)).fetchall() if giornata else []
    except sqlite3.Error:                                  # archivio non ancora pronto: nessuna partita, non un errore
        righe = []
    finally:
        db.close()
    return live.risposta(live.unico or live.Raccoglitore(lambda: []), righe)


@app.get("/api/live")
def risultati_live(request: Request):
    """Risultati in diretta delle partite del turno (stesso per tutti, sola lettura, dalla cache: vedi `live.py` e `docs/LIVE.md`)."""
    corpo = _risposta_live()
    etag = versioni.etag_dati(corpo)
    intestazioni = {"ETag": etag, "Cache-Control": "private, max-age=20"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=intestazioni)
    return JSONResponse(corpo, headers=intestazioni)


@app.get("/api/widget")
def widget(request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Tutto per i widget dell'iPhone in una chiamata (vedi `widget.py`; apribile anche con il token del widget). Risposta piccola
    (< 20 kB) con ETag: se non è cambiato niente, `If-None-Match` ottiene 304. Se i calcoli del nucleo non sono pronti: 202."""
    db = _db()
    try:
        corpo = widget_riassunto.costruisci(db, _regole(ctx), _rose(ctx), ctx.diario, ctx.osservati, file_scelte=ctx.scelte,
                                            live_partite=_stati_live())
    finally:
        db.close()
    corpo["live"] = _live_per_widget()
    corpo["funzioni"] = widget_riassunto.funzioni_per_widget(stato_utente.leggi_mostra_tutte(ctx.impostazioni_avvisi))
    widget_riassunto.entro_il_peso(corpo)                 # rete di sicurezza sulla dimensione: i blocchi tolti vanno in `mancano`
    etag = versioni.etag_dati(corpo)
    intestazioni = {"ETag": etag, "Cache-Control": "private, no-cache", "Vary": "Authorization, Cookie"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=intestazioni)
    return JSONResponse(corpo, headers=intestazioni)


@app.get("/api/sotto-il-cofano")
def sotto_il_cofano(request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Testi di «Sotto il cofano» (uguali per tutti) con i numeri di adesso, letti da cose già calcolate. ETag/304. Mai calcoli pesanti."""
    db = _db()
    try:
        corpo = sotto_il_cofano_mod.costruisci(db, consigli.stagione_corrente(), affidabilita.carica(ctx.affidabilita),
                                               lingua=lingua_testi.della_richiesta(request))
    except sotto_il_cofano_mod.TestiNonDisponibili:
        raise HTTPException(503, sotto_il_cofano_mod.MESSAGGIO_NON_DISPONIBILE) from None
    finally:
        db.close()
    etag = versioni.etag_dati(corpo)
    intestazioni = {"ETag": etag, "Cache-Control": "private, no-cache", "Vary": "Accept-Language"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=intestazioni)
    return JSONResponse(corpo, headers=intestazioni)


@app.get("/api/calendario")
def calendario(ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        return gestione.calendario(db, regole=_regole(ctx))
    finally:
        db.close()


@app.get("/api/mercato")
def mercato(squadra: str | None = None, ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        return consigli.mercato(db, _regole(ctx), _rose(ctx), squadra)
    finally:
        db.close()


@app.get("/api/classifica")
def classifica(ruolo: str | None = None, liberi: bool = False, limite: int = 60, ctx: Contesto = Depends(lega_corrente)):
    """Tutti i giocatori della giornata ordinati per punti attesi, con un indice 0-100 dentro il ruolo."""
    r = _regole(ctx)
    db = _db()
    try:
        prev, giornata, _ = consigli.previsioni(db, r)
        quot = {row["id"]: row["quotazione"] for row in db.execute("SELECT id, quotazione FROM calciatori")}
    finally:
        db.close()
    rs = lega.carica(ctx.rose)
    proprietari = {g.id: sq.nome for sq in (rs.squadre if rs else []) for g in sq.giocatori if g.id is not None}
    prev = prev[prev["p_voto"] >= 0.2]
    if ruolo:
        prev = prev[prev["ruolo"] == ruolo.upper()]
    if liberi:
        prev = prev[~prev.index.isin(proprietari)]
    prev = prev.sort_values("atteso", ascending=False).head(max(1, min(limite, 800)))
    schede = [consigli.scheda_previsione(i, x) | {"quotazione": quot.get(i), "proprietario": proprietari.get(i)}
              for i, x in prev.iterrows()]
    db = _db()
    try:
        return {"giornata": giornata, "giocatori": _stato_vero(schede, db, r, giornata)}
    finally:
        db.close()


@app.get("/api/giocatore/{calciatore_id}")
def giocatore(calciatore_id: int = FPath(le=MAX_ID_CALCIATORE), ctx: Contesto = Depends(lega_corrente)):
    db = _db()
    try:
        r = _regole(ctx)
        s = scheda.scheda(db, calciatore_id, consigli.stagione_corrente(), r.fonte_voto)
        try:
            prev, giornata, _ = consigli.previsioni(db, r)
            if calciatore_id in prev.index:
                s["previsione"] = consigli.scheda_previsione(calciatore_id, prev.loc[calciatore_id])
                s["previsione"]["giornata"] = giornata
                s["previsione"]["giornata_lega"] = regole.serie_a_a_lega(giornata, r)   # numero della lega, come in Oggi
                stagione = consigli.stagione_corrente()
                if fasi.iniziata(db, r, stagione, giornata, datetime.now()):       # dopo la scadenza: lo stato vero, non le probabili
                    s["previsione"] = fasi.schede_a_giornata_iniziata([s["previsione"]], db, r, stagione, giornata, datetime.now(),
                                                                      _stati_live())[calciatore_id]
        except ValueError:
            pass
        s["rendimento"] = scheda.rendimento(s["avanzate"], s["calciatore"]["ruolo"], s["stagione"]["con_voto"], r)
        # di chi è nella lega
        rs = lega.carica(ctx.rose)
        s["proprietario"] = next((sq.nome for sq in (rs.squadre if rs else []) for g in sq.giocatori
                                  if g.id == calciatore_id), None)
        tratti = avatar.di(calciatore_id)
        if tratti:
            s["avatar"] = tratti
        return s
    finally:
        db.close()


# ---------------- scambi ----------------
def _lista_id(testo: str) -> list[int]:
    try:
        return [int(x) for x in testo.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "Elenco di giocatori non valido") from None


@app.get("/api/scambi/proposte")
def proposte_scambi(con: str | None = None, due: bool = False, fino_a: int | None = None, ctx: Contesto = Depends(lega_corrente)):
    """Scambi vantaggiosi per tutti e due. `due=true` aggiunge i 2 contro 2; `fino_a` (2-4) tutti gli N contro M fino a quella misura.
    Gli scambi più grandi del 1 contro 1 si cercano con una squadra alla volta."""
    r_ose, r = _rose(ctx), _regole(ctx)
    if not r_ose.mia_squadra:
        raise ValueError("Indica prima la tua squadra in Squadra > Squadre e rose")
    if fino_a is not None and not 2 <= fino_a <= scambi_multi.MAX_PER_LATO:
        raise ValueError(f"fino_a deve essere un numero da 2 a {scambi_multi.MAX_PER_LATO}")
    if (due or fino_a) and not con:
        raise ValueError("Gli scambi più grandi dell'1 contro 1 si cercano con una squadra alla volta: scegline una")
    chiave = (con, bool(due), fino_a or 0, consigli._impronta_rose(r_ose))
    if not limiti.gia_contata_oggi(ctx, "scambi", chiave):      # una ricerca identica a una di oggi non costa: passa anche a tetto finito
        limiti.controlla(ctx, "scambi")
    # il posto si prende PRIMA del calcolo (richieste parallele a un passo dal tetto non passano tutte) e si restituisce se
    # il calcolo non finisce (202 «sto calcolando», errore): la stessa ricerca ripetuta oggi non conta di nuovo
    prenotazione = limiti.prenota(ctx, "scambi", chiave)
    try:
        db = _db()
        try:
            v, proposte = consigli.proposte_scambi(db, r, r_ose, con, due, fino_a or 0)
        finally:
            db.close()
    except BaseException:
        if prenotazione is not None:
            prenotazione.annulla()
        raise
    return {"giornate": v.giornate, "proposte": proposte, "ricerche": limiti.restano(ctx, "scambi")}


@app.get("/api/scambi/limite")
def limite_scambi(ctx: Contesto = Depends(lega_corrente)):
    """Quante ricerche di scambi restano oggi (`restano`, `tetto`; entrambi null se non ci sono limiti). Solo lettura: non consuma niente."""
    return limiti.restano(ctx, "scambi")


@app.get("/api/scambi/analizza")
def analizza_scambio(request: Request, con: str, do: str, ricevo: str, conguaglio: int | None = None, completo: bool = False,
                     ctx: Contesto = Depends(lega_corrente)):
    """Analisi di uno scambio. Così com'è (senza `conguaglio` né `completo`) è l'analisi di sempre: stesso numero di giocatori
    per ruolo. Con `completo=true` o `conguaglio` (crediti, positivo = li ricevi tu, negativo = li paghi tu) vale per qualsiasi
    N contro M da 1 a 4 e aggiunge validità delle rose, panchina, valore dei crediti e giudizio (campi nuovi, tutti facoltativi)."""
    from . import scambi
    r_ose, r = _rose(ctx), _regole(ctx)
    if not r_ose.mia_squadra:
        raise ValueError("Indica prima la tua squadra in Squadra > Squadre e rose")
    da, a = _lista_id(do), _lista_id(ricevo)
    # tetto al minuto per utente e analisi contemporanee limitate (la stessa analisi ripetuta, come fa l'app sul 202, non conta)
    with limiti.analisi_scambio(ctx, (con, tuple(da), tuple(a), conguaglio, bool(completo))):
        db = _db()
        try:
            if completo or conguaglio is not None:
                return consigli.analisi_scambio(db, r, r_ose, con, da, a, conguaglio or 0, lingua_testi.della_richiesta(request))
            v = consigli.valori_scambi(db, r)
        finally:
            db.close()
        return scambi.analizza(v, r, r_ose, r_ose.mia_squadra, con, da, a).come_dict(v)


class OffertaTesto(BaseModel):
    testo: str
    con: str | None = None
    completo: bool = False      # true: riconosce soltanto (con gli id) e non fa l'analisi semplice; quella completa si chiede a /api/scambi/analizza


def _analisi_da_testo(trovati: dict, r, r_ose, request: Request) -> dict:
    """L'analisi di un'offerta riconosciuta nel testo: quella semplice, o la completa se i ruoli non tornano."""
    from . import scambi
    db = _db()
    try:
        v = consigli.valori_scambi(db, r)
    finally:
        db.close()
    try:
        return scambi.analizza(v, r, r_ose, r_ose.mia_squadra, trovati["con"], trovati["do"], trovati["ricevo"]).come_dict(v)
    except ValueError:
        # l'analisi semplice vuole lo stesso numero di giocatori per ruolo: un'offerta 2 contro 1, o con ruoli diversi,
        # riceve l'analisi completa (stessi campi più validità delle rose e giudizio) invece di perdere i nomi riconosciuti
        # (l'app iPhone dà il giudizio dai soli punti: uno scambio che non si può fare resta un errore, con i motivi)
        db = _db()
        try:
            completa = consigli.analisi_scambio(db, r, r_ose, trovati["con"], list(trovati["do"]), list(trovati["ricevo"]),
                                                0, lingua_testi.della_richiesta(request))
        finally:
            db.close()
        if not completa["valido"]:
            raise ValueError(f"Così com'è lo scambio non si può fare: {'; '.join(completa['problemi'])}") from None
        return completa


@app.post("/api/scambi/da-testo")
def scambio_da_testo(dati: OffertaTesto, request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Valuta un'offerta scritta a parole (per esempio il messaggio di un altro allenatore): trova i giocatori e fa l'analisi."""
    from . import scambi
    r_ose, r = _rose(ctx), _regole(ctx)
    if not r_ose.mia_squadra:
        raise ValueError("Indica prima la tua squadra in Squadra > Squadre e rose")
    trovati = scambi.riconosci_nel_testo(dati.testo[:4000], r_ose, r_ose.mia_squadra, dati.con)
    nomi_ = {g.id: g.nome for s in r_ose.squadre for g in s.giocatori if g.id is not None}
    risposta = {"con": trovati["con"], "do": [nomi_[i] for i in trovati["do"]], "ricevo": [nomi_[i] for i in trovati["ricevo"]],
                "ambigui": trovati["ambigui"], "analisi": None, "ids": {"do": list(trovati["do"]), "ricevo": list(trovati["ricevo"])}}
    if trovati["con"] and trovati["do"] and trovati["ricevo"] and not dati.completo:
        # stesso limite di /api/scambi/analizza (al minuto per utente, analisi contemporanee): anche l'analisi completa N contro M
        # passa di qui; la stessa offerta ripetuta non conta di nuovo
        with limiti.analisi_scambio(ctx, ("testo", trovati["con"], tuple(trovati["do"]), tuple(trovati["ricevo"]))):
            risposta["analisi"] = _analisi_da_testo(trovati, r, r_ose, request)
    return risposta


# ---------------- lega: squadre, rose, regole ----------------
@app.get("/api/squadre")
def squadre(response: Response, ctx: Contesto = Depends(lega_corrente)):
    r = _rose(ctx)
    response.headers["ETag"] = versioni.etag_file(ctx.rose)
    return [{"nome": s.nome, "mia": s.nome == r.mia_squadra, "giocatori": len(s.giocatori),
             "crediti_residui": s.crediti_residui, "immagini": immagini.presenti(s.nome, ctx.immagini)} for s in r.squadre]


@app.get("/api/squadre/immagine")
def immagine_squadra(squadra: str, tipo: str, ctx: Contesto = Depends(lega_corrente)):
    """Stemma o maglia di una squadra della lega (404 se non c'è)."""
    s = _rose(ctx).squadra(squadra)
    p = immagini.percorso(s.nome, tipo, ctx.immagini) if s else None
    if p is None:
        raise HTTPException(404, "Nessuna immagine")
    return FileResponse(p, media_type=immagini.FORMATI[p.suffix], headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/squadre/immagine")
def carica_immagine_squadra(squadra: str, tipo: str, file: UploadFile, ctx: Contesto = Depends(lega_corrente)):
    dati = file.file.read(immagini.MAX_BYTE + 1)
    return _salva_immagine(squadra, tipo, dati, ctx)


def _salva_immagine(squadra: str, tipo: str, dati: bytes, ctx: Contesto) -> dict:
    """Con il blocco delle rose: una rinomina o un'importazione nello stesso momento non lascia l'immagine al nome vecchio."""
    with _scrittura_rose:
        s = _rose(ctx).squadra(squadra)
        if not s:
            raise HTTPException(404, "Squadra non trovata")
        limiti.controlla_spazio(ctx, len(dati))
        immagini.salva(s.nome, tipo, dati, ctx.immagini)
        return {"squadra": s.nome, "tipo": tipo, "immagini": immagini.presenti(s.nome, ctx.immagini)}


@app.delete("/api/squadre/immagine")
def togli_immagine_squadra(squadra: str, tipo: str, ctx: Contesto = Depends(lega_corrente)):
    """Toglie lo stemma o la maglia (200 anche se non c'era: il risultato è lo stesso)."""
    with _scrittura_rose:
        s = _rose(ctx).squadra(squadra)
        if not s:
            raise HTTPException(404, "Squadra non trovata")
        immagini.rimuovi(s.nome, tipo, ctx.immagini)
        return {"squadra": s.nome, "tipo": tipo, "immagini": immagini.presenti(s.nome, ctx.immagini)}


class DaUrl(BaseModel):
    squadra: str = Field(max_length=100)
    tipo: str = Field(max_length=20)
    url: str = Field(max_length=2100)


@app.post("/api/squadre/immagine/da-url")
def immagine_squadra_da_url(corpo: DaUrl, ctx: Contesto = Depends(lega_corrente)):
    """Scarica stemma o maglia da un indirizzo https pubblico (vedi `scarica_immagine.py`: niente reti private, tetto 4 MB)."""
    s = _rose(ctx).squadra(corpo.squadra)
    if not s:
        raise HTTPException(404, "Squadra non trovata")
    if corpo.tipo not in immagini.TIPI:
        raise HTTPException(400, "Tipo di immagine non valido: stemma o maglia")
    limiti.controlla(ctx, "immagini_url")
    limiti.distanzia_download(ctx)
    limiti.conta(ctx, "immagini_url")             # si conta prima: anche i tentativi sbagliati fanno lavorare il server
    with limiti.download_in_corso():
        dati, _ = scarica_immagine.scarica(corpo.url)           # fuori dal blocco: lo scaricamento può durare
    return _salva_immagine(corpo.squadra, corpo.tipo, dati, ctx)


@app.post(PERCORSO_CONDIVISIONE)
def riceve_immagine_condivisa(immagine: UploadFile, ctx: Contesto = Depends(lega_corrente)):
    """Web Share Target: il telefono manda qui l'immagine condivisa verso l'app installata. Serve il login (senza: 401).
    L'immagine aspetta in attesa; l'app (`/?condivisa=1`) chiede a che squadra e tipo assegnarla."""
    try:
        dati = immagine.file.read(immagini.MAX_BYTE + 1)
        limiti.controlla_spazio(ctx, len(dati))
        immagini.salva_in_attesa(dati, ctx.immagini)
    except (ValueError, account.ErroreAccount):
        return Response(status_code=303, headers={"Location": "/?condivisa=no", "Cache-Control": "no-store"})
    return Response(status_code=303, headers={"Location": "/?condivisa=1", "Cache-Control": "no-store"})


@app.get("/api/squadre/immagine/in-attesa")
def immagine_in_attesa(ctx: Contesto = Depends(lega_corrente)):
    """L'immagine ricevuta dal menu Condividi e non ancora assegnata (404 se non c'è)."""
    p = immagini.in_attesa(ctx.immagini)
    if p is None:
        raise HTTPException(404, "Nessuna immagine condivisa in attesa")
    return FileResponse(p, media_type=immagini.FORMATI[p.suffix], headers={"Cache-Control": "no-store"})


@app.delete("/api/squadre/immagine/in-attesa")
def scarta_immagine_in_attesa(ctx: Contesto = Depends(lega_corrente)):
    immagini.togli_in_attesa(ctx.immagini)
    return {"ok": True}


@app.get("/api/rosa")
def rosa(response: Response, squadra: str | None = None, ctx: Contesto = Depends(lega_corrente)):
    r = _rose(ctx)
    response.headers["ETag"] = versioni.etag_file(ctx.rose)
    s = r.squadra(squadra or r.mia_squadra or "")
    if not s:
        raise HTTPException(404, "Squadra non trovata")
    db = _db()
    try:
        prev, schede = None, {}
        try:
            prev, giornata, _ = consigli.previsioni(db, _regole(ctx))
            schede = {g.id: consigli.scheda_previsione(g.id, prev.loc[g.id]) for g in s.giocatori if g.id in prev.index}
            stagione = consigli.stagione_corrente()
            if schede and fasi.iniziata(db, _regole(ctx), stagione, giornata, datetime.now()):
                # dopo la scadenza lo stato vero della giornata («Ha giocato», «Voto in arrivo»...), come la scheda e la Formazione
                schede = schede | fasi.schede_a_giornata_iniziata(list(schede.values()), db, _regole(ctx), stagione, giornata,
                                                                  datetime.now(), _stati_live())
        except ValueError:
            pass
        quot = {row["id"]: (row["quotazione"], row["squadra_slug"])
                for row in db.execute("SELECT id, quotazione, squadra_slug FROM calciatori")}
    finally:
        db.close()
    giocatori = []
    for g in s.giocatori:
        q, slug = quot.get(g.id, (None, None))
        x = asdict(g) | {"quotazione": q, "squadra_slug": slug}
        if g.id in schede:
            x["previsione"] = schede[g.id]
        giocatori.append(x)
    avvisi_squadra = [a for a in lega.controlla(r, _regole(ctx))
                      if a.startswith(s.nome + ":") or a.startswith(s.nome + " (")
                      or a.endswith(f": {s.nome}") or f" {s.nome}," in a or a.endswith(f", {s.nome}")]
    return {"nome": s.nome, "mia": s.nome == r.mia_squadra, "crediti_residui": s.crediti_residui,
            "aggiornato": r.aggiornato, "giocatori": giocatori,
            "avvisi": avvisi_squadra, "avvisi_frasi": frasi.lista(avvisi_squadra)}


class MiaSquadra(BaseModel):
    nome: str


class NomeSquadra(BaseModel):
    nome: str = Field(max_length=100)          # il nome di adesso
    nuovo: str = Field(max_length=100)


NOME_SQUADRA_MAX = 60
NOME_SQUADRA_NON_VALIDO = "Scrivi un nome da 1 a 60 caratteri."           # 60 = NOME_SQUADRA_MAX
NOME_SQUADRA_DOPPIO = "C'è già una squadra con questo nome: scegline un altro."


@app.put("/api/squadre/nome")
def rinomina_squadra(dati: NomeSquadra, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """Cambia il nome di una squadra della lega dopo l'importazione: rose, «la mia squadra», stemma e maglia. If-Match come le
    rose (412 se sono cambiate da un altro dispositivo). Il nome vecchio va scritto per intero (maiuscole a parte)."""
    nuovo = " ".join(dati.nuovo.split())
    if not nuovo or len(nuovo) > NOME_SQUADRA_MAX or any(unicodedata.category(c)[0] == "C" for c in nuovo):
        raise HTTPException(400, NOME_SQUADRA_NON_VALIDO)
    with _scrittura_rose:
        versioni.controlla(request, versioni.etag_file(ctx.rose))
        r = _rose(ctx)
        s = next((x for x in r.squadre if x.nome.lower() == dati.nome.strip().lower()), None)
        if s is None:
            raise HTTPException(404, "Squadra non trovata")
        if any(x is not s and x.nome.lower() == nuovo.lower() for x in r.squadre):
            raise HTTPException(409, NOME_SQUADRA_DOPPIO)
        simile = next((x for x in r.squadre if x is not s and immagini.slug(x.nome) == immagini.slug(nuovo)), None)
        if simile is not None:                       # nomi diversi ma stesso file per stemma e maglia (simboli, punteggiatura)
            raise HTTPException(409, f"Questo nome si confonde con «{simile.nome}»: aggiungi o cambia una lettera o un numero.")
        vecchio = s.nome
        if vecchio != nuovo:
            spostati = immagini.rinomina(vecchio, nuovo, ctx.immagini)
            s.nome = nuovo
            s.nome_importato = s.nome_importato or vecchio       # il nome di Leghe, per riconoscerla alla prossima importazione
            if s.nome_importato == nuovo:
                s.nome_importato = None
            if r.mia_squadra == vecchio:
                r.mia_squadra = nuovo
            try:
                lega.salva(r, ctx.rose)
            except Exception:
                immagini.annulla(spostati)           # le rose non sono cambiate: stemma e maglia tornano al nome di prima
                raise
        response.headers["ETag"] = versioni.etag_file(ctx.rose)
        return {"nome": nuovo, "prima": vecchio, "mia_squadra": r.mia_squadra}


@app.put("/api/mia-squadra")
def imposta_mia_squadra(dati: MiaSquadra, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    with _scrittura_rose:
        versioni.controlla(request, versioni.etag_file(ctx.rose))
        r = _rose(ctx)
        s = r.squadra(dati.nome)
        if not s:
            raise HTTPException(404, "Squadra non trovata")
        r.mia_squadra = s.nome
        lega.salva(r, ctx.rose)
        response.headers["ETag"] = versioni.etag_file(ctx.rose)
        return {"mia_squadra": s.nome}


class _Riconosciute(NamedTuple):
    squadre: list                    # rose.SquadraLetta
    avvisi: list[str]
    calciatori: list                 # il listone usato


def _riconosci(griglie, ctx: Contesto, excel: bool = False) -> _Riconosciute:
    """I giocatori delle celle cercati nel listone: la parte lenta dell'importazione (e dell'anteprima). Si fa PRIMA di prendere
    il blocco delle rose, così le scritture degli altri non la aspettano. Con gli account ha un tempo massimo
    (`limiti.MAX_SECONDI_RICONOSCIMENTO`): oltre si ferma con `importa_sicuro.riconoscimento_lungo` (`excel`: quello dell'Excel)."""
    calciatori, _ = listone.carica()
    avvisi: list[str] = []
    indice = nomi.Indice(calciatori, listone.nomi_completi(), scaduto=limiti.tempo_riconoscimento(ctx))
    try:
        lette = rose.estrai(griglie, indice, _regole(ctx).rosa, avvisi)
    except nomi.TempoScaduto:
        raise ValueError(importa_sicuro.riconoscimento_lungo(excel)) from None
    if not lette:
        raise ValueError(rose.NESSUNA_ROSA)
    return _Riconosciute(lette, avvisi, calciatori)


def _leggi_rose(lette: _Riconosciute, correzioni: list[dict] | None = None, prima: lega.Rose | None = None):
    """Le squadre lette (con le scelte dell'utente sui dubbi già applicate) e gli avvisi della lettura. Veloce: si fa dentro il
    blocco delle rose, dopo `_riconosci`. `prima` (le rose salvate): le squadre rinominate nell'app prendono il nome dell'app
    (lega.nomi_rinominati)."""
    squadre, avvisi = lette.squadre, list(lette.avvisi)
    lega.nomi_rinominati(squadre, prima)
    anteprima_rose.applica_correzioni(squadre, correzioni, lette.calciatori)
    rose.togli_doppioni(squadre, avvisi)               # una correzione può indicare chi c'è già nella stessa rosa
    return squadre, avvisi


def _importa(riconosciute: _Riconosciute, sostituisci_tutto: bool, ctx: Contesto, correzioni: list[dict] | None = None,
             mia_squadra: str | None = None) -> dict:
    """Salva le rose già riconosciute (`_riconosci`). Da chiamare con il blocco delle rose preso."""
    r = _regole(ctx)
    prima = lega.carica(ctx.rose)
    lette, avvisi = _leggi_rose(riconosciute, correzioni, prima)
    nuove = lega.da_import(lette, prima, sostituisci_tutto)
    anteprima_rose.scegli_mia(nuove, mia_squadra)              # facoltativa: la squadra dell'utente scelta nell'anteprima
    limiti.controlla_rose(ctx, nuove)                          # con gli account: al massimo 20 squadre da 40 giocatori
    nuove.stagione = consigli.stagione_corrente()
    lega.salva(nuove, ctx.rose, copia_di_riserva=True)
    try:                                                       # stemmi e maglie di squadre tolte: una nuova con lo stesso nome non li eredita
        immagini.pulisci([s.nome for s in nuove.squadre], ctx.immagini)
    except OSError:
        pass
    diff = movimenti.differenze(prima, nuove)
    if prima and any(s.giocatori for s in prima.squadre):      # dopo il passaggio di stagione le rose partono vuote: non sono "acquisti"
        movimenti.registra(ctx.movimenti, diff)
    try:
        # un osservato lasciato libero: si può prendere
        notifiche.osservati_liberi(diff, ctx.osservati, manda=_manda(ctx), opzioni=notifiche.impostazioni(ctx.impostazioni_avvisi))
    except Exception:                                         # un avviso che non parte non deve far fallire l'importazione
        pass
    threading.Thread(target=_scalda, args=(ctx,), daemon=True).start()     # le rose sono cambiate: la nuova formazione si prepara subito
    return {"squadre_importate": [s.nome for s in lette], "totale_squadre": len(nuove.squadre),
            "avvisi": avvisi + lega.controlla(nuove, r), "mia_squadra": nuove.mia_squadra,
            "differenze": diff, "riepilogo": diff["testo"]}


MAX_CORREZIONI = limiti.MAX_SQUADRE * limiti.MAX_GIOCATORI_SQUADRA


class CorrezioneRosa(BaseModel):
    """Una scelta dell'utente su un dubbio dell'anteprima: `testo` = il nome come scritto nel file, `id` = il giocatore giusto
    del listone (null = togli la riga)."""
    squadra: str = Field(max_length=200)
    testo: str = Field(max_length=200)
    id: int | None = None


_CORREZIONI = TypeAdapter(list[CorrezioneRosa])


def _impronta(contenuto: str | bytes) -> str:
    """Lo stesso testo (o file) dà la stessa impronta: anteprima e importazione che segue contano una volta sola."""
    return hashlib.sha256(contenuto.encode("utf-8", "surrogatepass") if isinstance(contenuto, str) else contenuto).hexdigest()


class TestoRose(BaseModel):
    testo: str
    sostituisci_tutto: bool = False
    correzioni: list[CorrezioneRosa] | None = Field(None, max_length=MAX_CORREZIONI)     # facoltativo (piano «Ingresso facile»)
    mia_squadra: str | None = Field(None, max_length=200)                               # facoltativo


def _scelte(correzioni: list[CorrezioneRosa] | None) -> list[dict] | None:
    return [c.model_dump() for c in correzioni] if correzioni else None


@app.post("/api/rose/testo")
def importa_testo(dati: TestoRose, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    versioni.controlla(request, versioni.etag_file(ctx.rose))        # rose già cambiate: 412 prima di contare
    if ctx.utente_id is not None:
        importa_sicuro.controlla_testo(dati.testo)
    griglie = [("testo", rose.griglia_da_testo(dati.testo))]
    if ctx.utente_id is not None:
        importa_sicuro.controlla_griglie(griglie)
    # i testi rifiutati per dimensione o righe non consumano un'importazione; dopo l'anteprima dello stesso testo non conta
    with _buono_dell_anteprima(ctx, _impronta(dati.testo)):
        riconosciute = _riconosci(griglie, ctx)           # fuori dal blocco: le scritture degli altri non aspettano
        with _scrittura_rose:                            # due importazioni insieme (o con l'importazione per conto di) una alla volta
            versioni.controlla(request, versioni.etag_file(ctx.rose))
            risposta = _importa(riconosciute, dati.sostituisci_tutto, ctx, _scelte(dati.correzioni), dati.mia_squadra)
            response.headers["ETag"] = versioni.etag_file(ctx.rose)
            return risposta


@contextlib.contextmanager
def _buono_dell_anteprima(ctx: Contesto, impronta: str):
    """Conta l'importazione (o usa il buono dell'anteprima dello stesso contenuto). Se l'importazione pagata dal buono fallisce
    (scelte non valide, rose cambiate nel frattempo, tetti), il buono torna: riprovare non costa un'altra importazione.
    Un'importazione contata normalmente resta contata anche se fallisce, come sempre.
    Il buono torna al massimo una volta al giorno per lo stesso contenuto (vedi `limiti.restituisci_buono`). Se il server era
    occupato a leggere un altro Excel (503, il lavoro non è cominciato) non conta niente: né il buono né l'importazione.
    Si restituisce sempre nel giorno del conteggio (a cavallo della mezzanotte non diventa gratis un tentativo di domani)."""
    giorno = limiti.oggi()
    buono = limiti.conta_importazione(ctx, impronta, giorno)
    try:
        yield
    except ExcelOccupato:
        if buono:
            limiti.restituisci_buono(ctx, impronta, una_volta=False, giorno=giorno)
        else:
            limiti.rimetti_importazione(ctx, giorno)
        raise
    except BaseException:
        if buono:
            limiti.restituisci_buono(ctx, impronta, giorno=giorno)
        raise


class AnteprimaRose(BaseModel):
    testo: str
    sostituisci_tutto: bool = False
    correzioni: list[CorrezioneRosa] | None = Field(None, max_length=MAX_CORREZIONI)


def _anteprima(griglie, sostituisci_tutto: bool, correzioni: list[dict] | None, response: Response, ctx: Contesto,
               excel: bool = False) -> dict:
    """Come l'importazione ma senza scrivere niente: legge le rose salvate (per dire cosa cambierebbe) e basta."""
    etag = versioni.etag_file(ctx.rose)          # PRIMA di leggere le rose: se cambiano subito dopo, l'importazione darà 412
    r = _regole(ctx)
    prima = lega.carica(ctx.rose)
    lette, avvisi = _leggi_rose(_riconosci(griglie, ctx, excel), correzioni, prima)
    nuove = lega.da_import(lette, prima, sostituisci_tutto)
    limiti.controlla_rose(ctx, nuove)                              # stessi tetti dell'importazione
    risposta = anteprima_rose.anteprima(lette, avvisi, r, prima, nuove)
    response.headers["ETag"] = etag                               # da rimandare con If-Match all'importazione
    response.headers["Cache-Control"] = "no-store"
    return risposta


@app.post("/api/rose/anteprima")
def anteprima_testo(dati: AnteprimaRose, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """Le rose incollate come le capirebbe l'importazione, SENZA salvare: per ogni giocatore sicuro / da controllare (con le
    alternative) / non trovato, conteggi per ruolo, avvisi. Il testo non va nei log."""
    importa_sicuro.controlla_testo(dati.testo)                   # sempre, anche senza account: non scrive niente ma legge tutto
    griglie = [("testo", rose.griglia_da_testo(dati.testo))]
    importa_sicuro.controlla_griglie(griglie)
    limiti.conta_anteprima(ctx, _impronta(dati.testo))
    return _anteprima(griglie, dati.sostituisci_tutto, _scelte(dati.correzioni), response, ctx)


class RoseDiUnAmico(BaseModel):
    testo: str
    sostituisci_tutto: bool = False


IMPORTAZIONI_PER_CONTO_DI = (30, 3600)          # al massimo 30 all'ora, in tutto
COPIE_DELLE_ROSE = 5


def _copia_datata_delle_rose(ctx: Contesto) -> None:
    """Prima di sostituire tutto: copia con data e ora delle rose di prima (il solo .bak si perderebbe alla seconda importazione).
    Se ne tengono le ultime `COPIE_DELLE_ROSE`."""
    if not ctx.rose.exists():
        return
    cartella = ctx.cartella / "rose-prima"
    cartella.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ctx.rose, cartella / f"rose-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
    for vecchia in sorted(cartella.glob("rose-*.json"))[:-COPIE_DELLE_ROSE]:
        vecchia.unlink(missing_ok=True)


def importa_per_conto_di(utente_id: int, griglie, sostituisci_tutto: bool, da_chi: int | None) -> dict:
    """Importa delle rose nell'archivio di un altro utente (lo chiede lui, lo fa il proprietario dell'app). Stessi controlli
    dell'importazione normale (dimensioni, formato, tetti di squadre e giocatori); non consuma le importazioni al giorno
    dell'amico; lascia una riga nel registro di sicurezza (chi, per chi, quante squadre: mai il testo)."""
    if not account.multiutente():
        raise HTTPException(409, "Questa funzione serve solo con gli account attivi: accendi FANTA_MULTIUTENTE=1 sul server")
    with contextlib.closing(account.apri()) as db:
        if account.trova(db, utente_id) is None:
            raise HTTPException(404, "Utente non trovato")
        account.limite.consuma(db, account._chiave("importa-per-conto-di"), *IMPORTAZIONI_PER_CONTO_DI)
    importa_sicuro.controlla_griglie(griglie)
    ctx = Contesto.per_utente(utente_id)
    # fuori dal blocco, come le importazioni dall'app; il comando da riga di comando passa anche gli Excel letti da leggi_excel
    riconosciute = _riconosci(griglie, ctx, excel=isinstance(griglie, importa_sicuro.FogliExcel))
    with _scrittura_rose:
        if sostituisci_tutto:
            _copia_datata_delle_rose(ctx)
        risposta = _importa(riconosciute, sostituisci_tutto, ctx)
    account.evento("importazione_per_conto_di", admin=da_chi if da_chi is not None else "riga-di-comando", utente=utente_id,
                   squadre=len(risposta["squadre_importate"]), sostituisci=int(bool(sostituisci_tutto)))
    return risposta


@app.post("/api/admin/utenti/{utente_id}/rose")
def importa_rose_di_un_amico(utente_id: int, dati: RoseDiUnAmico, admin: account.Utente = Depends(rotte_account.solo_amministratore)):
    """Solo l'amministratore dell'app: importa le rose di un utente che l'ha chiesto. Risponde come l'importazione normale."""
    importa_sicuro.controlla_testo(dati.testo)
    return importa_per_conto_di(utente_id, [("testo", rose.griglia_da_testo(dati.testo))], dati.sostituisci_tutto, admin.id)


LETTURE_EXCEL_INSIEME = 1        # ogni lettura (con gli account) è un processo che può arrivare a 1 GB; il servizio ne ha 1,2 in tutto
ATTESA_LETTURA_EXCEL = 3.0       # secondi di attesa del proprio turno, poi 503
_letture_excel = threading.BoundedSemaphore(LETTURE_EXCEL_INSIEME)
OCCUPATO_EXCEL = "Sto già leggendo un altro file Excel: riprova tra poco."


class ExcelOccupato(HTTPException):
    def __init__(self):
        super().__init__(503, OCCUPATO_EXCEL, headers={"Retry-After": "5"})


@contextlib.contextmanager
def _turno_excel(ctx: Contesto):
    """Un Excel alla volta in tutto il servizio (anteprime e importazioni insieme): due o tre letture insieme potrebbero superare
    la memoria del servizio e farlo chiudere. Chi arriva mentre un altro legge aspetta poco, poi riceve 503 «riprova tra poco».
    Quei 503 sono gratuiti ma al massimo `limiti.MAX_EXCEL_OCCUPATO_ALL_ORA` all'ora per utente: oltre, 429 SUBITO (senza attesa),
    così decine di richieste non possono tenere occupati i thread del servizio."""
    if not _letture_excel.acquire(blocking=False):
        occupato = limiti.prenota_ora(ctx, "excel_occupato", massimo=limiti.MAX_EXCEL_OCCUPATO_ALL_ORA)
        if not _letture_excel.acquire(timeout=ATTESA_LETTURA_EXCEL):
            raise ExcelOccupato()
        if occupato is not None:
            occupato.annulla()                   # alla fine il turno è arrivato: non era un «occupato»
    try:
        yield
    finally:
        _letture_excel.release()


def _griglie_excel(percorso: Path, ctx: Contesto):
    """Le celle di un Excel. Con gli account (il file è di altri) si controlla e si legge in un processo separato."""
    return rose.leggi_griglie(percorso) if ctx.utente_id is None else importa_sicuro.leggi_excel(percorso)


def _leggi_file(file: UploadFile, ctx: Contesto) -> tuple[bytes, str]:
    """Il contenuto del file e la sua estensione, dopo i rifiuti immediati (troppo grande, vuoto, con macro): questi non contano."""
    estensione = Path(file.filename or "").suffix.lower()
    contenuto = file.file.read(MAX_FILE + 1)
    if len(contenuto) > MAX_FILE:
        raise HTTPException(400, "File troppo grande (massimo 5 MB): carica solo le rose")
    if not contenuto.strip():
        raise HTTPException(400, "Il file è vuoto")
    if ctx.utente_id is not None and estensione == ".xlsm":     # file di altri: controlli in più (vedi importa_sicuro.py)
        raise HTTPException(400, "I file con macro (.xlsm) non sono ammessi: salvalo come Excel normale (.xlsx)")
    return contenuto, estensione


def _correzioni_da_modulo(testo: str | None) -> list[dict] | None:
    """Il campo `correzioni` di un invio multipart: lo stesso elenco JSON del corpo di /api/rose/testo, scritto come testo."""
    if not testo:
        return None
    try:
        if len(testo) > 200_000:
            raise ValueError
        correzioni = _CORREZIONI.validate_json(testo)
    except (ValueError, ValidationError):
        raise HTTPException(422, DATI_NON_VALIDI) from None
    if len(correzioni) > MAX_CORREZIONI:
        raise HTTPException(422, DATI_NON_VALIDI)
    return _scelte(correzioni)


@app.post("/api/rose/file")
def importa_file(file: UploadFile, request: Request, response: Response, sostituisci_tutto: bool = False,
                 correzioni: str | None = Form(None), mia_squadra: str | None = Form(None, max_length=200),
                 ctx: Contesto = Depends(lega_corrente)):
    """Excel (.xlsx) oppure testo di qualunque tipo: CSV, TSV, TXT, o anche senza estensione (il menu Condividi dell'iPhone a volte
    non la passa). Un Excel è un archivio zip e si riconosce dall'inizio del file; tutto il resto si legge come testo.
    Facoltativi nel modulo: `correzioni` (JSON, come in /api/rose/testo) e `mia_squadra`."""
    versioni.controlla(request, versioni.etag_file(ctx.rose))
    scelte = _correzioni_da_modulo(correzioni)
    contenuto, estensione = _leggi_file(file, ctx)
    # da qui il file costa lavoro (zip, processo separato, lettura): conta come un'importazione anche se poi viene rifiutato,
    # così non si possono mandare file sbagliati all'infinito. I rifiuti immediati (vuoto, troppo grande, .xlsm) non contano.
    # Dopo l'anteprima dello stesso file non conta di nuovo.
    # Il file si legge e i giocatori si riconoscono PRIMA di prendere il lucchetto delle rose (un Excel può richiedere fino a
    # 30 s, il riconoscimento fino a 20: gli altri non aspettano).
    with _buono_dell_anteprima(ctx, _impronta(contenuto)):
        griglie = _griglie_del_file(contenuto, estensione, ctx)
        riconosciute = _riconosci(griglie, ctx, _e_excel(contenuto))
        with _scrittura_rose:                                     # una importazione alla volta (anche per conto di)
            versioni.controlla(request, versioni.etag_file(ctx.rose))
            risposta = _importa(riconosciute, sostituisci_tutto, ctx, scelte, mia_squadra)
            response.headers["ETag"] = versioni.etag_file(ctx.rose)
            return risposta


@app.post("/api/rose/anteprima/file")
def anteprima_file(file: UploadFile, response: Response, sostituisci_tutto: bool = False, correzioni: str | None = Form(None),
                   ctx: Contesto = Depends(lega_corrente)):
    """Come /api/rose/anteprima, per un file (gli stessi formati di /api/rose/file). Non salva niente."""
    scelte = _correzioni_da_modulo(correzioni)
    contenuto, estensione = _leggi_file(file, ctx)
    presi = limiti.conta_anteprima(ctx, _impronta(contenuto))
    try:
        griglie = _griglie_del_file(contenuto, estensione, ctx)
    except ExcelOccupato:                        # il lavoro non è cominciato: l'anteprima non conta (posti restituiti)
        for p in presi:
            p.annulla()
        raise
    return _anteprima(griglie, sostituisci_tutto, scelte, response, ctx, _e_excel(contenuto))


def _e_excel(contenuto: bytes) -> bool:
    """Un Excel è un archivio zip: si riconosce dall'inizio del file."""
    return contenuto[:4] == b"PK"


def _griglie_del_file(contenuto: bytes, estensione: str, ctx: Contesto):
    """Le celle del file: Excel (riconosciuto dall'inizio «PK») oppure testo. Con gli account, i controlli di importa_sicuro."""
    if _e_excel(contenuto):
        return _griglie_dell_excel(contenuto, ".xlsm" if estensione == ".xlsm" else ".xlsx", ctx)
    testo = rose.decodifica(contenuto)
    if ctx.utente_id is not None:
        importa_sicuro.controlla_testo(testo)
    griglie = rose.griglie_da_stringa(testo)
    if ctx.utente_id is not None:
        importa_sicuro.controlla_griglie(griglie)
    return griglie


def _griglie_dell_excel(contenuto: bytes, estensione: str, ctx: Contesto):
    # Il turno si prende PRIMA del file temporaneo e dei controlli dello zip (fino a 20 MB di XML): chi trova occupato non fa
    # nessun lavoro. Il turno si libera sempre, anche se il file è rotto o la lettura va oltre il tempo massimo.
    with _turno_excel(ctx):
        cartella = RADICE / "dati" / "cache"
        cartella.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=estensione, dir=cartella, delete=False) as f:
            f.write(contenuto)
            temporaneo = Path(f.name)
        try:
            # (l'importazione è già contata prima dei controlli: anche un Excel rifiutato conta)
            if ctx.utente_id is not None:
                importa_sicuro.controlla_zip(temporaneo)
            return _griglie_excel(temporaneo, ctx)
        finally:
            temporaneo.unlink(missing_ok=True)


class ImpostazioniAvvisi(BaseModel):
    cambi: bool = True
    promemoria_60: bool = True
    promemoria_15: bool = True
    riepilogo: bool = True
    copertura: bool = True          # avviso se un reparto della rosa è scoperto o senza ricambi
    app_nativa: bool = False        # avvisi anche con ntfy, il cui tocco apre l'app iOS nativa
    silenzio: bool = False          # ore tranquille: niente avvisi dalle `silenzio_da` alle `silenzio_a`
    silenzio_da: int = Field(23, ge=0, le=23)
    silenzio_a: int = Field(7, ge=0, le=23)
    avviso_prima: Literal[0, 30, 60, 90] = 60     # avviso «cambia la formazione»: minuti prima della scadenza (0 = spento)
    lingua: Literal["it", "en"] = "it"            # lingua dei testi degli avvisi sul telefono (la web app la manda quando cambia lingua)


def _stato_avvisi(ctx: Contesto, opzioni: dict) -> dict:
    iscrizioni = notifiche_web.iscrizioni(ctx.iscrizioni_push)
    return {"impostazioni": opzioni, "canale": (ctx.ntfy and notifiche.canale() is not None) or bool(iscrizioni),
            "dispositivi": len(iscrizioni)}


def _etag_avvisi(ctx: Contesto) -> str:
    """ETag dei soli avvisi: lo stesso file contiene anche «Mostra tutte», il primo avvio e la data del backup, che non c'entrano."""
    return versioni.etag_dati(notifiche.impostazioni(ctx.impostazioni_avvisi))


@app.get("/api/avvisi")
def leggi_avvisi(response: Response, ctx: Contesto = Depends(lega_corrente)):
    response.headers["ETag"] = _etag_avvisi(ctx)
    stato = _stato_avvisi(ctx, notifiche.impostazioni(ctx.impostazioni_avvisi))
    if notifiche.ore_tranquille_spente(ctx.impostazioni_avvisi):      # solo se serve: chi non la conosce la ignora
        stato["ore_tranquille_spente"] = True
    return stato


@app.put("/api/avvisi")
def scrivi_avvisi(dati: ImpostazioniAvvisi, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    with versioni.blocco("avvisi"):
        versioni.controlla(request, _etag_avvisi(ctx))
        # solo i campi mandati: un client che non conosce `app_nativa` (la web app vecchia in cache, l'app iOS) non la azzera
        nuove = {**notifiche.impostazioni(ctx.impostazioni_avvisi), **dati.model_dump(exclude_unset=True)}
        if nuove.get("silenzio") and nuove.get("silenzio_da") == nuove.get("silenzio_a"):
            raise HTTPException(422, "Le ore tranquille non possono iniziare e finire alla stessa ora: scegli due ore diverse "
                                     "(per esempio dalle 23 alle 7) oppure spegni l'interruttore")
        salvate = notifiche.salva_impostazioni(nuove, ctx.impostazioni_avvisi)
        response.headers["ETag"] = _etag_avvisi(ctx)
    return _stato_avvisi(ctx, salvate)


@app.post("/api/avvisi/prova")
def avviso_di_prova(ctx: Contesto = Depends(lega_corrente)):
    """Manda un avviso di prova al telefono (per controllare che il canale funzioni)."""
    if not ((ctx.ntfy and notifiche.canale() is not None) or notifiche_web.iscrizioni(ctx.iscrizioni_push)):
        raise HTTPException(409, "Nessun canale per gli avvisi: attiva le notifiche su questo dispositivo"
                            + (", oppure imposta il canale ntfy sul server." if ctx.ntfy else "."))
    limiti.prova_avvisi(ctx)                        # ogni prova manda davvero una notifica: tetto all'ora per utente (429)
    return {"inviato": _manda(ctx)(frasi.F("n.t_prova"), frasi.F("n.prova"), 3, "white_check_mark", ignora_silenzio=True)}


class IscrizionePush(BaseModel):
    endpoint: str
    keys: dict[str, str]


@app.get("/api/push/chiave")
def chiave_push():
    return {"chiave": notifiche_web.chiavi()["pubblica"]}


@app.post("/api/push/iscrivi")
def iscrivi_push(dati: IscrizionePush, request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Questo dispositivo vuole le notifiche web (le avvisi arriveranno qui e non più su ntfy). Con gli account la sessione si
    ricontrolla subito prima di scrivere: se nel frattempo si è chiusa (cambio password, «Esci da tutti») non resta niente."""
    ancora_valida = (lambda: rotte_account.identifica(request) is not None) if ctx.utente_id is not None else None
    with limiti.iscrizione_push(ctx):                # una alla volta per utente, poche in tutto, tetto all'ora (429)
        try:
            return {"dispositivi": len(notifiche_web.iscrivi(dati.model_dump(), ctx.iscrizioni_push, ancora_valida=ancora_valida))}
        except notifiche_web.NonPiuValida:
            raise HTTPException(401, "Accesso richiesto") from None
        except notifiche_web.Occupato as e:          # file tenuto da un altro processo: 503 «riprova», niente scritto
            raise HTTPException(503, str(e)) from None


class DisiscrizionePush(BaseModel):
    endpoint: str


@app.post("/api/push/disiscrivi")
def disiscrivi_push(dati: DisiscrizionePush, ctx: Contesto = Depends(lega_corrente)):
    try:
        return {"dispositivi": len(notifiche_web.togli(dati.endpoint, ctx.iscrizioni_push))}
    except notifiche_web.Occupato as e:              # file tenuto da un altro processo: 503 «riprova», niente tolto
        raise HTTPException(503, str(e)) from None


@app.get("/api/movimenti")
def ultimi_movimenti(limite: int = 30, ctx: Contesto = Depends(lega_corrente)):
    """Storico dei cambiamenti alle rose (scambi, svincolati presi, tagli) visti nelle importazioni, dal più recente."""
    return list(reversed(movimenti.leggi(ctx.movimenti, max(1, min(limite, 300)))))


class TestoRegole(BaseModel):
    testo: str


@app.post("/api/regole/riconosci")
def riconosci_regole(dati: TestoRegole):
    """Legge il regolamento incollato da Leghe e propone i valori (l'app li mostra per controllo, non cambia nulla da sola).
    Oltre i tetti (regole_testo.MAX_TESTO caratteri, MAX_RIGA per riga): 422 con una frase chiara."""
    return regole_testo.interpreta(dati.testo)


@app.get("/api/regole")
def leggi_regole(response: Response, ctx: Contesto = Depends(lega_corrente)):
    response.headers["ETag"] = versioni.etag_file(ctx.regole)
    return asdict(_regole(ctx))


@app.put("/api/regole")
def scrivi_regole(dati: dict, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    campi_lega = ("scadenza_minuti", "prima_giornata_lega", "aggiornamenti_vicino_scadenza",
                  "partite_rinviate", "voto_ufficio_rinviate", "rinvii_giornate", "asta_estiva", "asta_invernale",
                  "finestre_scambio")
    with versioni.blocco("regole"):
        versioni.controlla(request, versioni.etag_file(ctx.regole))
        if any(k not in dati for k in campi_lega):
            # un client vecchio rimanda le regole senza i campi nuovi: non devono tornare al valore di partenza (letti DENTRO il
            # lucchetto: un'eccezione dei rinvii salvata intanto da un altro dispositivo non si perde)
            attuali = asdict(_regole(ctx))
            dati = {**{k: attuali[k] for k in campi_lega}, **dati}
        nuove = regole.da_dict(dati)        # controlla tutto: chiavi, tipi, valori
        regole.salva(nuove, ctx.regole)
        response.headers["ETag"] = versioni.etag_file(ctx.regole)
    return asdict(nuove)


class EccezioneRinvio(BaseModel):
    giornata: int = Field(ge=1, le=regole.GIORNATE_SERIE_A)          # giornata di Serie A (il campo `giornata` di /api/oggi)
    stagione: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    modo: Literal["aspetta", "senza_voto", "voto_ufficio"] | None = None     # None = torna alla regola della lega


@app.put("/api/regole/rinvio")
def scrivi_eccezione_rinvio(dati: EccezioneRinvio, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """Partite rinviate, decisione per UNA giornata («per la giornata 12: voto d'ufficio»): vince sulla regola generale della lega.
    `modo` null (o uguale alla regola generale) toglie l'eccezione. Risponde con la regola che vale ora per quella giornata."""
    stagione = dati.stagione or consigli.stagione_corrente()
    with versioni.blocco("regole"):
        versioni.controlla(request, versioni.etag_file(ctx.regole))
        nuove = rinvii.con_eccezione(_regole(ctx), stagione, dati.giornata, dati.modo, consigli.stagione_corrente())
        regole.salva(nuove, ctx.regole)
        response.headers["ETag"] = versioni.etag_file(ctx.regole)
    return {"stagione": stagione, "giornata": dati.giornata, **rinvii.regola(nuove, stagione, dati.giornata)}


class CorrezioneGiocatore(BaseModel):
    squadra: str
    nome: str                # come è scritto adesso nella rosa (quello non riconosciuto)
    id: int                  # il calciatore giusto, dal listone


@app.post("/api/rose/correggi")
def correggi_giocatore(dati: CorrezioneGiocatore, request: Request, response: Response, ctx: Contesto = Depends(lega_corrente)):
    """Un giocatore che l'importazione non ha riconosciuto (o ha riconosciuto per somiglianza): lo si abbina a mano a quello del listone."""
    calciatori, _ = listone.carica()
    c = next((x for x in calciatori if x.id == dati.id), None)
    if c is None:
        raise HTTPException(404, "Giocatore non trovato nel listone")
    with _scrittura_rose:
        versioni.controlla(request, versioni.etag_file(ctx.rose))
        r = _rose(ctx)
        s = r.squadra(dati.squadra)
        g = next((x for x in s.giocatori if x.nome == dati.nome and x.riconosciuto not in ("esatto", "manuale")), None) if s else None
        if g is None:
            raise HTTPException(404, "Quel giocatore non c'è più nella rosa: ricarica la pagina")
        g.id, g.nome, g.ruolo, g.squadra, g.riconosciuto, g.avviso = c.id, c.nome, c.ruolo, c.squadra, "manuale", ""
        lega.salva(r, ctx.rose)
        response.headers["ETag"] = versioni.etag_file(ctx.rose)
        return {"giocatore": asdict(g), "avvisi": lega.controlla(r, _regole(ctx))}


# ---------------- procedura guidata (solo con gli account) ----------------
def _con_account() -> None:
    if not account.multiutente():
        raise HTTPException(404, "Gli account non sono attivi")


def _ha_rose(ctx: Contesto) -> bool:
    try:
        r = lega.carica(ctx.rose)
    except ValueError:
        return False
    return bool(r and any(s.giocatori for s in r.squadre))


class PrimoAvvio(BaseModel):
    fatti: list[str] | None = Field(None, max_length=12)
    saltati: list[str] | None = Field(None, max_length=12)
    chiuso: bool | None = None


@app.get("/api/primo-avvio")
def leggi_primo_avvio(ctx: Contesto = Depends(lega_corrente)):
    """A che punto è la configurazione guidata (passi fatti e saltati). `primo_avvio` è null se non l'ha mai iniziata.
    Funziona anche senza account (FANTA_MULTIUTENTE spento), a differenza di /api/onboarding."""
    return {"primo_avvio": stato_utente.leggi_primo_avvio(ctx.impostazioni_avvisi), "passi": list(stato_utente.PASSI)}


@app.put("/api/primo-avvio")
def scrivi_primo_avvio(dati: PrimoAvvio, ctx: Contesto = Depends(lega_corrente)):
    """Cambia solo i campi mandati (`fatti`, `saltati`, `chiuso`). Passo sconosciuto: 400."""
    try:
        s = stato_utente.scrivi_primo_avvio(ctx.impostazioni_avvisi, **dati.model_dump(exclude_unset=True))
    except stato_utente.ErroreStato as e:
        raise HTTPException(400, str(e)) from None
    return {"primo_avvio": s, "passi": list(stato_utente.PASSI)}


class ScelteFunzioni(BaseModel):
    mostra_tutte: bool


def _risposta_funzioni(ctx: Contesto, request: Request) -> dict:
    tutte = stato_utente.leggi_mostra_tutte(ctx.impostazioni_avvisi)
    return {"funzioni": funzioni.per_utente(tutte, amministratore=_e_amministratore(request)), "mostra_tutte": tutte}


@app.get("/api/funzioni")
def leggi_funzioni(request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Quali funzioni sono accese per chi chiede. Una chiave che manca vale «acceso». Con «Mostra tutte» è tutto acceso."""
    return _risposta_funzioni(ctx, request)


@app.put("/api/funzioni")
def scrivi_funzioni(dati: ScelteFunzioni, request: Request, ctx: Contesto = Depends(lega_corrente)):
    """Accende o spegne «Mostra tutte le funzioni» (solo per questo utente)."""
    stato_utente.scrivi_mostra_tutte(ctx.impostazioni_avvisi, dati.mostra_tutte)
    return _risposta_funzioni(ctx, request)


@app.get("/api/onboarding", dependencies=[Depends(_con_account)])
def leggi_onboarding(ctx: Contesto = Depends(lega_corrente)):
    """A che punto è la procedura guidata di chi sta chiedendo (stato salvato sul server: si riprende da un altro dispositivo)."""
    with contextlib.closing(account.apri()) as db:
        return onboarding.leggi(db, ctx.utente_id, _ha_rose(ctx))


class PassoOnboarding(BaseModel):
    passo: str | None = None
    stato: str | None = None
    tipo: str | None = None


@app.put("/api/onboarding", dependencies=[Depends(_con_account)])
def scrivi_onboarding(dati: PassoOnboarding, ctx: Contesto = Depends(lega_corrente)):
    with contextlib.closing(account.apri()) as db:
        return onboarding.aggiorna(db, ctx.utente_id, dati.passo, dati.stato, dati.tipo, ha_rose=_ha_rose(ctx))


@app.post("/api/onboarding/regole", dependencies=[Depends(_con_account)])
def proponi_regole(dati: TestoRegole, ctx: Contesto = Depends(lega_corrente)):
    """Il regolamento incollato diventa una proposta di regole (non salva niente): righe riconosciute e righe «da confermare»."""
    regole_testo.controlla_lunghezza(dati.testo)            # gli stessi tetti di /api/regole/riconosci (422)
    return onboarding.proponi_regole(_regole(ctx), dati.testo)


@app.get("/api/onboarding/controlli", dependencies=[Depends(_con_account)])
def controlli_onboarding(ctx: Contesto = Depends(lega_corrente)):
    """Le spunte prima della prima formazione."""
    return onboarding.controlli(_regole(ctx), lega.carica(ctx.rose), ctx.regole.exists())


@app.post("/api/onboarding/demo", dependencies=[Depends(_con_account)])
def crea_demo(ctx: Contesto = Depends(lega_corrente)):
    """Una lega di prova con squadre inventate (e calciatori veri) per vedere l'app al lavoro. Non sovrascrive mai rose vere."""
    with contextlib.closing(account.apri()) as db:
        onboarding.leggi(db, ctx.utente_id, _ha_rose(ctx))
        if _ha_rose(ctx) and not onboarding.e_demo(lega.carica(ctx.rose)):
            raise HTTPException(409, "Hai già le tue rose: la lega demo le sostituirebbe, quindi non la creo.")
        limiti.azione_pesante(ctx)                      # creare e togliere la demo si ripete: tetto all'ora (429)
        calciatori, _ = listone.carica()
        r = _regole(ctx)
        rose_demo = onboarding.crea_demo(calciatori, r)
        rose_demo.stagione = consigli.stagione_corrente()
        with _scrittura_rose:
            lega.salva(rose_demo, ctx.rose)
        regole.salva(r, ctx.regole)
        return onboarding.aggiorna(db, ctx.utente_id, passo="formazione", stato="in_corso", demo=True)


@app.delete("/api/onboarding/demo", dependencies=[Depends(_con_account)])
def togli_demo(ctx: Contesto = Depends(lega_corrente)):
    """Toglie la lega demo (solo se è davvero la demo) per ricominciare con la propria lega."""
    with contextlib.closing(account.apri()) as db:
        if not onboarding.leggi(db, ctx.utente_id, _ha_rose(ctx))["demo"]:
            raise HTTPException(409, "Non c'è nessuna lega demo da togliere.")
        if onboarding.e_demo(lega.carica(ctx.rose)):          # solo se sono ancora le rose della demo: quelle vere non si toccano mai
            limiti.azione_pesante(ctx)
            with _scrittura_rose:
                for f in (ctx.rose, ctx.regole, ctx.movimenti, ctx.scelte, ctx.osservati):
                    f.unlink(missing_ok=True)
            # niente da svuotare nella memoria dei calcoli: le chiavi contengono rose e regole, e quella memoria è di tutti
        return onboarding.aggiorna(db, ctx.utente_id, passo="tipo", stato="in_corso", demo=False)


# ---------------- backup ----------------
@app.get("/api/backup")
def scarica_backup(ctx: Contesto = Depends(lega_corrente)):
    """Un file con regole, rose, scelte, osservati e impostazioni degli avvisi (niente chiavi né iscrizioni alle notifiche).
    Con gli account c'è anche la sezione `account` (portabilità: solo i dati di chi chiede, mai segreti); il ripristino la ignora."""
    b = backup.crea(RADICE, ctx.file_backup)
    if ctx.utente_id is not None and account.multiutente():
        try:
            with contextlib.closing(account.apri()) as db:
                dati_account = account.esporta(db, ctx.utente_id, stato_utente.leggi_mostra_tutte(ctx.impostazioni_avvisi))
        except (sqlite3.Error, account.ErroreAccount) as e:     # database degli account non leggibile: il file della lega esce lo stesso
            logging.getLogger("uvicorn.error").warning("Scarica i tuoi dati: sezione account saltata (%s)", type(e).__name__)
            dati_account = None
        if dati_account is not None:
            b["account"] = dati_account
    nome = backup.nome_file(b["creato"])
    try:
        stato_utente.segna_backup(ctx.impostazioni_avvisi)         # serve a «Da fare» per ricordare il backup
    except (OSError, percorsi.DatabaseAccountNonRisponde):         # un di più: il file dei dati esce lo stesso
        pass
    return JSONResponse(b, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


RIPRISTINO_FATTO = "Dati ripristinati."
RIPRISTINO_CHIUSE = "Dati ripristinati. Le formazioni delle giornate già chiuse non sono state cambiate."


def _giornata_chiusa_per(ctx: Contesto):
    """La regola di `_formazione_chiusa` per le voci di `scelte` («stagione/giornata») di un backup: chiuse le stagioni passate e,
    in questa, le giornate dopo la scadenza. Calendario illeggibile: chiusa (nel dubbio la scelta del server resta)."""
    stagione_ora, adesso = consigli.stagione_corrente(), datetime.now()
    try:
        r = _regole(ctx)
    except Exception:                       # noqa: BLE001 - regole rovinate: valgono quelle predefinite
        r = regole.Regole()
    db = _db()
    ricordate: dict[str, bool] = {}

    def chiusa(chiave: str) -> bool:
        if chiave not in ricordate:
            stagione, _, g = chiave.rpartition("/")
            if not g.isdigit() or not 1 <= int(g) <= MAX_GIORNATA:
                ricordate[chiave] = False   # voce che l'app non legge mai: non cambia nessuna formazione
            elif stagione != stagione_ora:
                ricordate[chiave] = stagione < stagione_ora
            else:
                try:
                    ricordate[chiave] = fasi.iniziata(db, r, stagione, int(g), adesso)
                except sqlite3.Error:
                    ricordate[chiave] = True
        return ricordate[chiave]
    return chiusa, db


@app.post("/api/backup/ripristina")
def ripristina_backup(dati: dict, ctx: Contesto = Depends(lega_corrente)):
    """Rimette i dati di un backup. Controlla tutto prima: se qualcosa non va non cambia niente. Le formazioni delle giornate
    già chiuse restano quelle del server (il backup non aggira la scadenza, come POST /api/formazione/valuta e DELETE /api/scelta)."""
    troppo = "Questo backup è troppo grande: controlla di aver scelto il file giusto."
    limiti.controlla_spazio(ctx, len(json.dumps(dati)), troppo)          # subito, prima dei controlli
    chiusa, db = _giornata_chiusa_per(ctx)
    try:
        with versioni.blocco("scelte"):
            esito = backup.ripristina_esito(dati, RADICE, ctx.file_backup, ctx.copia_prima, chiusa,
                                            lambda rose: limiti.controlla_rose(ctx, rose),      # stessi tetti dell'importazione
                                            spazio=lambda byte: limiti.controlla_spazio(ctx, byte, troppo))    # il peso vero dei file da scrivere
    finally:
        db.close()
    tenute = esito["scelte_chiuse_tenute"]
    return {"ripristinati": esito["ripristinati"], "formazioni_chiuse_tenute": tenute,
            "messaggio": RIPRISTINO_CHIUSE if tenute else RIPRISTINO_FATTO}


# ---------------- app ----------------
@app.api_route("/", methods=["GET", "HEAD"])     # HEAD: i controlli di raggiungibilità non ricevono più 404
def pagina():
    return FileResponse(WEB / "index.html")


@app.api_route("/privacy", methods=["GET", "HEAD"], response_class=HTMLResponse)
def pagina_privacy(lingua: str = "it"):
    """Pagina pubblica (anche senza accesso): quali dati tiene l'app."""
    return HTMLResponse(testi_legali.pagina("privacy", testi_legali.lingua_valida(lingua)))


@app.api_route("/termini", methods=["GET", "HEAD"], response_class=HTMLResponse)
def pagina_termini(lingua: str = "it"):
    """Pagina pubblica (anche senza accesso): regole d'uso."""
    return HTMLResponse(testi_legali.pagina("termini", testi_legali.lingua_valida(lingua)))


@app.api_route("/crediti", methods=["GET", "HEAD"], response_class=HTMLResponse)
def pagina_crediti(lingua: str = "it"):
    """Pagina pubblica: fonti dei dati, licenze dei programmi aperti, link al codice sorgente."""
    return HTMLResponse(testi_legali.pagina("crediti", testi_legali.lingua_valida(lingua)))


@app.get("/elimina-account", response_class=HTMLResponse)
def pagina_elimina_account(lingua: str = "it"):
    """Pagina pubblica (richiesta da Google Play): come cancellare l'account, anche senza riaprire l'app."""
    return HTMLResponse(testi_legali.pagina("elimina", testi_legali.lingua_valida(lingua)))


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /\n"


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="application/javascript")


# ---------------- icona dell'app ----------------
TEMI_ICONA = ["verde", "blu", "viola", "arancio", "rosso", "grafite"]
FILE_ICONA = RADICE / "dati" / "icona.json"


def _icona_scelta(file: Path) -> str:
    try:
        nome = json.loads(file.read_text(encoding="utf-8")).get("nome")
        return nome if nome in TEMI_ICONA else "verde"
    except (OSError, ValueError, AttributeError):
        return "verde"


class SceltaIcona(BaseModel):
    nome: str


@app.get("/api/icona")
def leggi_icona(ctx: Contesto = Depends(lega_corrente)):
    return {"scelta": _icona_scelta(ctx.icona), "elenco": TEMI_ICONA}


@app.put("/api/icona")
def scegli_icona(dati: SceltaIcona, ctx: Contesto = Depends(lega_corrente)):
    """Sceglie il colore dell'icona. Su iPhone l'icona sulla Home cambia solo quando si riaggiunge l'app alla Home."""
    if dati.nome not in TEMI_ICONA:
        raise ValueError("Icona non valida")
    ctx.icona.parent.mkdir(parents=True, exist_ok=True)
    scrivi_sicuro(ctx.icona, json.dumps({"nome": dati.nome}))
    return {"scelta": dati.nome, "elenco": TEMI_ICONA}


@app.get("/icona-maskable-{dim}.png")
def icona_maskable(dim: int, request: Request):
    """Variante «maskable» per Android (il sistema la ritaglia come vuole): stesso tema scelto, disegno nella zona sicura."""
    if dim not in (192, 512):
        raise HTTPException(404, "Dimensione non disponibile")
    if not account.multiutente():
        scelta = _icona_scelta(_contesto_locale().icona)
    else:
        utente = rotte_account.identifica(request)
        scelta = _icona_scelta(Contesto.per_utente(utente.id).icona) if utente else "verde"
    return FileResponse(WEB / "icone" / f"{scelta}-maskable-{dim}.png", headers={"Cache-Control": "no-cache"})


@app.get("/icona-{dim}.png")
def icona_dell_app(dim: int, request: Request):
    """L'icona dell'app (per la Home, il manifest e le schede): è quella scelta, nella dimensione richiesta."""
    if dim not in (180, 192, 512):
        raise HTTPException(404, "Dimensione non disponibile")
    if not account.multiutente():
        scelta = _icona_scelta(_contesto_locale().icona)
    else:                                                    # la pagina di accesso e il manifest non hanno sessione: icona di base
        utente = rotte_account.identifica(request)
        scelta = _icona_scelta(Contesto.per_utente(utente.id).icona) if utente else "verde"
    return FileResponse(WEB / "icone" / f"{scelta}-{dim}.png", headers={"Cache-Control": "no-cache"})


# Il tipo dei caratteri .woff2 non è conosciuto da Python su tutti i sistemi (Windows): senza, il file andrebbe come text/plain.
mimetypes.add_type("font/woff2", ".woff2")
app.mount("/", StaticFiles(directory=WEB), name="web")


def avvia(host: str = "127.0.0.1", porta: int = 8000) -> None:
    import uvicorn
    social.togli_query_dai_log()
    social.avvisa_se_manca_il_proxy()
    uvicorn.run(app, host=host, port=porta)
