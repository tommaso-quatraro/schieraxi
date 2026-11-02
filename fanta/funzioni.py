"""Un interruttore per ogni funzione dell'app (la «dieta»: la formazione al centro, il resto dietro un interruttore, senza cancellare codice).

Stesso schema di `fonti_attive.py`. Chi decide, in ordine: 1) la scelta dell'amministratore (file dati/funzioni.json, cambiabile dall'app);
2) la variabile d'ambiente FANTA_FUNZIONE_<NOME> ("1" acceso, "0" spento); 3) il predefinito.
Il predefinito è quello pubblico della tabella FUNZIONI (il nucleo e poche funzioni; il resto nascosto).
Con FANTA_PROFILO_FUNZIONI=completo il predefinito diventa «tutto acceso», tranne le funzioni di `SPENTE_DI_NORMA` (il profilo di un server già in uso).
L'amministratore vede anche ciò che è spento solo di predefinito (non quello che ha spento lui o l'ambiente).
Una chiave che non è in elenco vale «acceso»: così un client o un server vecchio non si rompe.
Ogni utente può accendere «Mostra tutte le funzioni» (impostazione avanzata, spenta di norma): vale SOLO per i menu e le schermate.
Le funzioni di `SEMPRE_BLOCCATE` (rete e costi) restano spente per tutti se le ha spente l'amministratore.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .percorsi import RADICE, scrivi_sicuro

VERSIONE_PUBBLICA = os.environ.get("FANTA_PROFILO_FUNZIONI", "").strip().lower() != "completo"
FILE = RADICE / "dati" / "funzioni.json"

# id -> (nome per l'utente, a cosa serve, predefinito nella versione pubblica)
FUNZIONI: dict[str, tuple[str, str, bool]] = {
    # nascoste nel menu (le rotte restano come sono)
    "stili_ridotti": ("Stili a 3 livelli", "nel foglio della formazione solo «più sicura», «equilibrata», «più rischiosa»", False),
    "confronto": ("Confronto tra due giocatori", "confronto fianco a fianco dentro la scheda del giocatore", False),
    "elenco_giocatori": ("Elenco dei giocatori", "elenco con filtri, oltre alla ricerca", False),
    "seguiti": ("Seguiti", "giocatori seguiti con avvisi quando si liberano", False),
    "diario": ("Diario delle giornate", "formazione schierata contro consigliata, in «Altro»", False),
    "movimenti": ("Movimenti e storico", "storico di acquisti, tagli e scambi della propria rosa, in «Altro» (serve a tenerla aggiornata)", True),
    "backup": ("Copia di sicurezza", "scarica e ripristina i dati, in «Altro»", False),
    "squadre_altrui": ("Squadre della lega", "rose e crediti delle altre squadre", False),
    "aspetto_avanzato": ("Aspetto avanzato", "colore, densità, animazioni, sezione di apertura e icona", False),
    "novita": ("Novità", "l'elenco delle novità di ogni versione", False),
    "crediti": ("Crediti delle squadre", "crediti di tutte le squadre della lega", False),
    # rimandate (le rotte esclusive rispondono 404 se la funzione è spenta, vedi ROTTE)
    "live": ("Risultati in diretta", "partite del turno in diretta e widget Live", False),
    "asta": ("Asta e riparazione", "prezzi consigliati per l'asta", False),
    "scambi_trova": ("Scambi: trova per me", "proposte di scambio con le altre squadre", False),
    "scambi_costruisci": ("Scambi: costruisci", "scambi da 1 a 4 contro 1 a 4 con conguaglio in crediti (solo la schermata)", False),
    "immagini_web": ("Immagini da indirizzo web", "stemma e maglia da un indirizzo web o dal menu Condividi", False),
    "widget_extra": ("Widget aggiuntivi", "widget oltre a formazione e scadenza", False),
    "fonti_ombra": ("Fonti in ombra", "raccolta di dati usati solo per misurare il modello", False),
}

# spente di norma anche nel codice privato: restano all'amministratore e a chi accende «Mostra tutte le funzioni».
# Chi ha già una scelta (file dell'amministratore o variabile d'ambiente) la conserva.
SPENTE_DI_NORMA = frozenset({"asta", "crediti"})

# funzioni tolte dalle app (non si riaccendono, nemmeno con «Mostra tutte»): restano nella risposta come `false`,
# così un client vecchio, per cui una chiave che manca vale «acceso», non le mostra più. «Sotto il cofano»: tolta il 1/11/2026.
RITIRATE = frozenset({"sotto_il_cofano"})

# le funzioni di cui il server blocca le rotte quando sono spente (le altre sono solo da nascondere nelle schermate)
# («scambi_costruisci» non ne ha di sue: la schermata usa /api/scambi/analizza, che serve anche a «Valuta un'offerta»)
CON_ROTTE = frozenset({"live", "asta", "scambi_trova", "immagini_web", "confronto"})

# spente dall'amministratore = spente per tutti, anche per chi ha acceso «Mostra tutte»: `immagini_web` scarica indirizzi scritti dall'utente,
# `live` fa partire il raccoglitore e le chiamate verso l'esterno
SEMPRE_BLOCCATE = frozenset({"live", "immagini_web"})

# (metodo, percorso intero) -> funzione. Solo percorsi esclusivi della funzione: quelli condivisi con funzioni sempre accese non si bloccano mai.
ROTTE: dict[tuple[str, str], str] = {
    ("GET", "/api/live"): "live",
    ("GET", "/api/asta"): "asta",
    ("GET", "/api/scambi/proposte"): "scambi_trova",
    ("GET", "/api/scambi/limite"): "scambi_trova",
    ("GET", "/api/confronto"): "confronto",
    ("POST", "/api/squadre/immagine/da-url"): "immagini_web",
    ("POST", "/api/squadre/immagine/condivisa"): "immagini_web",
}


def di_rotta(metodo: str, percorso: str) -> str | None:
    """La funzione a cui appartiene la rotta (solo se il server ne blocca le rotte), altrimenti None."""
    return ROTTE.get((metodo.upper(), percorso.rstrip("/") or "/"))

_BLOCCO = threading.Lock()
_cache: dict[str, tuple[tuple[int, int], dict[str, bool]]] = {}      # percorso -> ((data, dimensione), scelte)


def _scelte_admin(percorso: Path | None = None) -> dict[str, bool]:
    """Le scelte dell'amministratore; il file si rilegge solo se è cambiato (data e dimensione)."""
    p = percorso or FILE
    try:
        s = p.stat()
        impronta = (s.st_mtime_ns, s.st_size)
        c = _cache.get(str(p))
        if c and c[0] == impronta:
            return dict(c[1])
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    ok = {k: v for k, v in d.items() if k in FUNZIONI and isinstance(v, bool)} if isinstance(d, dict) else {}
    _cache[str(p)] = (impronta, ok)
    return dict(ok)


def _da_ambiente(funzione: str) -> bool | None:
    return {"1": True, "0": False}.get(os.environ.get(f"FANTA_FUNZIONE_{funzione.upper()}", "").strip())


def predefinito(funzione: str) -> bool:
    if VERSIONE_PUBBLICA:
        return FUNZIONI[funzione][2]
    return funzione not in SPENTE_DI_NORMA


def origine(funzione: str, percorso: Path | None = None) -> tuple[bool, str]:
    """(acceso, da dove viene la scelta: "amministratore", "ambiente" o "predefinito"). Non conta «Mostra tutte» (è dell'utente)."""
    if funzione not in FUNZIONI:
        raise KeyError(funzione)
    a = _scelte_admin(percorso).get(funzione)
    if a is not None:
        return a, "amministratore"
    e = _da_ambiente(funzione)
    if e is not None:
        return e, "ambiente"
    return predefinito(funzione), "predefinito"


def acceso(funzione: str, mostra_tutte: bool = False, percorso: Path | None = None, amministratore: bool = False) -> bool:
    """Una funzione fuori elenco vale acceso (tranne quelle `RITIRATE`). Con `mostra_tutte` (scelta dell'utente) è accesa, tranne quelle
    di `SEMPRE_BLOCCATE`. L'amministratore vede anche quelle spente solo di predefinito (non quelle che ha spento lui o l'ambiente)."""
    if funzione in RITIRATE:
        return False
    if funzione not in FUNZIONI:
        return True
    if mostra_tutte and funzione not in SEMPRE_BLOCCATE:
        return True
    on, da = origine(funzione, percorso)
    if amministratore and da == "predefinito" and funzione not in SEMPRE_BLOCCATE:
        return True
    return on


def per_utente(mostra_tutte: bool = False, percorso: Path | None = None, amministratore: bool = False) -> dict[str, bool]:
    """Per `GET /api/funzioni`: id -> acceso, già tenuto conto di «Mostra tutte» e del ruolo. Le funzioni ritirate valgono sempre `false`."""
    return {k: acceso(k, mostra_tutte, percorso, amministratore) for k in FUNZIONI} | {k: False for k in sorted(RITIRATE)}


def messaggio_spenta(funzione: str) -> str:
    nome = FUNZIONI[funzione][0]
    return f"«{nome}» non è disponibile in questa versione dell'app."


def stato(percorso: Path | None = None) -> list[dict]:
    """Per l'amministratore: una riga per funzione."""
    righe = []
    for k, (nome, serve, pubblico) in FUNZIONI.items():
        on, da = origine(k, percorso)
        righe.append({"id": k, "nome": nome, "serve": serve, "acceso": on, "scelta_da": da,
                      "predefinito_pubblico": pubblico, "blocca_rotte": k in CON_ROTTE})
    return righe


def imposta(funzione: str, acceso_: bool | None, percorso: Path | None = None) -> None:
    """Scelta dell'amministratore; None la toglie (torna ambiente o predefinito)."""
    if funzione not in FUNZIONI:
        raise KeyError(funzione)
    p = percorso or FILE
    with _BLOCCO:                                       # leggi-modifica-scrivi: due richieste insieme non si perdono a vicenda
        scelte = _scelte_admin(p)
        if acceso_ is None:
            scelte.pop(funzione, None)
        else:
            scelte[funzione] = bool(acceso_)
        scrivi_sicuro(p, json.dumps(scelte))
        try:
            os.chmod(p, 0o600)                          # solo il proprietario (su Windows non ha effetto)
        except OSError:
            pass
        _cache.pop(str(p), None)
