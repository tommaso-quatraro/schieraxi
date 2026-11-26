"""Conteggio d'uso ANONIMO dell'app: quante volte è chiamata ogni rotta e ogni funzione, giorno per giorno, per 4 settimane.

Serve a decidere quali funzioni tenere in primo piano (docs/DIETA-FUNZIONI.md, sezione 7). Sono solo numeri aggregati:
nessun nome utente, nessun id, nessun indirizzo di rete, nessun valore ricevuto; la rotta è sempre quella «di modello»
(`/api/giocatore/{calciatore_id}`), mai l'indirizzo scritto da chi chiede. Il file `dati/uso.json` lo vede solo l'amministratore (Stato dei dati).
I giorni più vecchi di 28 si cancellano da soli. Se non si riesce a contare o a scrivere, l'app va avanti lo stesso.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from . import frasi, funzioni
from .percorsi import RADICE, scrivi_sicuro

FILE = RADICE / "dati" / "uso.json"
GIORNI = 28                       # quanti giorni si tengono
MAX_VOCI = 400                    # tetto di rotte diverse al giorno (le rotte sono poche: è solo una cintura di sicurezza)
OGNI_SECONDI = 60                 # ogni quanto si scrive il file (i conteggi stanno in memoria nel frattempo)

# rotta di modello -> funzione (solo dove la rotta è di una sola funzione; le altre contano solo come rotta)
FUNZIONE_DI_ROTTA: dict[str, str] = {
    "/api/live": "live", "/api/asta": "asta", "/api/confronto": "confronto",
    "/api/scambi/proposte": "scambi_trova", "/api/scambi/limite": "scambi_trova",
    "/api/scambi/analizza": "scambi_costruisci", "/api/scambi/da-testo": "scambi_costruisci",
    "/api/squadre/immagine/da-url": "immagini_web", "/api/squadre/immagine/condivisa": "immagini_web",
    "/api/classifica": "elenco_giocatori",
    "/api/osservati": "seguiti", "/api/osservati/{i}": "seguiti",
    "/api/diario": "diario", "/api/diario/schierata": "diario",
    "/api/backup": "backup", "/api/backup/ripristina": "backup",
    "/api/novita": "novita",
}
# nomi usati prima nel file -> funzione di oggi: fino al 26/11/2026 «Valuta un'offerta» si contava così (non è una funzione)
VECCHI_NOMI = {"scambi_valuta_o_costruisci": "scambi_costruisci"}

# la parte dell'app di una rotta, dalla prima parte del percorso dopo /api/ («/api/oggi» -> Formazione): gli stessi gruppi e gli
# stessi nomi della tabella AREE_DELLE_ROTTE di «Errori recenti» (fanta/web/app.js), con la frase `uso.parte_<id>` del catalogo
# (fanta/frasi.py). Una rotta che qui non c'è conta in «altro».
PARTI: dict[str, tuple[str, ...]] = {
    "formazione": ("oggi", "formazione", "scelta", "giocatore", "giocatori", "live", "osservati", "confronto", "classifica", "avatar"),
    "giornate": ("diario", "calendario", "affidabilita"),
    "lega": ("regole", "rose", "rosa", "squadre", "mia-squadra", "crediti", "stagione", "nuova-stagione", "onboarding", "primo-avvio",
             "scambi", "movimenti", "mercato", "asta"),
    "account": ("account",),
    "avvisi": ("avvisi", "push"),
    "aspetto": ("icona",),
    "gestione": ("admin", "aggiorna", "backup", "stato-dati"),
    "informazioni": ("novita", "sotto-il-cofano"),
    "scrivici": ("feedback",),
    "avvio": ("stato", "funzioni"),
    "widget": ("widget",),
    "controllo": ("salute",),
}
_PARTE_DI = {inizio: parte for parte, inizi in PARTI.items() for inizio in inizi}

_blocco = threading.Lock()
_in_memoria: dict[str, dict[str, dict[str, int]]] = {}       # giorno -> {"rotte": {...}, "funzioni": {...}} (solo quello non ancora scritto)
_ultima_scrittura = 0.0


def _oggi() -> str:
    return date.today().isoformat()


def conta(metodo: str, rotta: str, stato: int, giorno: str | None = None, percorso: Path | None = None) -> None:
    """Un'altra chiamata a `rotta` (di modello). Solo `/api/`; i file dell'app e le rotte sconosciute non si contano. Non alza mai errori."""
    try:
        if not rotta.startswith("/api/") or stato >= 500:
            return
        g = giorno or _oggi()
        with _blocco:
            d = _in_memoria.setdefault(g, {"rotte": {}, "funzioni": {}})
            chiave = f"{metodo.upper()} {rotta}"[:80]
            if chiave in d["rotte"] or len(d["rotte"]) < MAX_VOCI:
                d["rotte"][chiave] = d["rotte"].get(chiave, 0) + 1
            f = FUNZIONE_DI_ROTTA.get(rotta)
            if f:
                d["funzioni"][f] = d["funzioni"].get(f, 0) + 1
        _scrivi_se_ora(percorso)
    except Exception:  # noqa: BLE001 - contare non deve mai far fallire una richiesta
        pass


def _scrivi_se_ora(percorso: Path | None) -> None:
    global _ultima_scrittura
    if time.monotonic() - _ultima_scrittura >= OGNI_SECONDI:
        _ultima_scrittura = time.monotonic()
        salva(percorso)


def _leggi(percorso: Path) -> dict[str, dict]:
    try:
        d = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    giorni = d.get("giorni") if isinstance(d, dict) else None
    if not isinstance(giorni, dict):
        return {}
    pulito = {}
    for g, v in giorni.items():
        try:
            date.fromisoformat(g)
        except (TypeError, ValueError):
            continue
        if not isinstance(v, dict):
            continue
        voce = {}
        for k in ("rotte", "funzioni"):
            grezzo = v.get(k)
            grezzo = grezzo if isinstance(grezzo, dict) else {}
            voce[k] = {str(n)[:80]: c for n, c in grezzo.items() if isinstance(c, int) and not isinstance(c, bool) and c >= 0}
        pulito[g] = voce
    return pulito


def salva(percorso: Path | None = None) -> None:
    """Scrive nel file ciò che è in memoria (sommandolo a quello che c'è) e toglie i giorni oltre i 28. Chiamata anche allo spegnimento."""
    p = percorso or FILE
    try:
        with _blocco:
            nuovi = {g: v for g, v in _in_memoria.items() if v["rotte"] or v["funzioni"]}
            _in_memoria.clear()
            tutti = _leggi(p)
            for g, v in nuovi.items():
                base = tutti.setdefault(g, {"rotte": {}, "funzioni": {}})
                for k in ("rotte", "funzioni"):
                    for nome, n in v[k].items():
                        if nome in base[k] or len(base[k]) < MAX_VOCI:
                            base[k][nome] = base[k].get(nome, 0) + n
            limite = (date.today() - timedelta(days=GIORNI - 1)).isoformat()
            tutti = {g: v for g, v in tutti.items() if g >= limite}
            if not nuovi and not p.exists():
                return
            scrivi_sicuro(p, json.dumps({"giorni": tutti}))
            try:
                os.chmod(p, 0o600)
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass


def parte_di(chiave: str) -> str:
    """La parte dell'app di una voce del conteggio («GET /api/giocatore/{calciatore_id}» -> "formazione"), "altro" se non si sa."""
    percorso = chiave.split(" ", 1)[-1]
    inizio = percorso.removeprefix("/api/").split("/", 1)[0] if percorso.startswith("/api/") else ""
    return _PARTE_DI.get(inizio, "altro")


def nome_funzione(funzione: str) -> str:
    """Il nome per l'utente di una funzione contata (`funzioni.FUNZIONI`); una che non c'è più resta col suo nome, senza trattini."""
    voce = funzioni.FUNZIONI.get(funzione)
    return voce[0] if voce else funzione.replace("_", " ")


def riepilogo(percorso: Path | None = None, massimo_rotte: int = 40) -> dict:
    """Per l'amministratore: totali sulle ultime 4 settimane, per funzione, per parte dell'app e per rotta, e le richieste di ogni
    giorno. Funzioni e parti hanno il nome da mostrare (`etichetta`; per le parti anche `etichetta_frase`, per tradurlo); `per_rotta`
    resta con le rotte di modello, per chi gestisce il server."""
    p = percorso or FILE
    salva(p)                                           # include anche quello che è ancora in memoria
    giorni = _leggi(p)
    rotte: dict[str, int] = {}
    per_funz: dict[str, int] = {}
    per_giorno = []
    for g in sorted(giorni):
        v = giorni[g]
        for n, c in v["rotte"].items():
            rotte[n] = rotte.get(n, 0) + c
        for n, c in v["funzioni"].items():
            n = VECCHI_NOMI.get(n, n)
            per_funz[n] = per_funz.get(n, 0) + c
        per_giorno.append({"giorno": g, "richieste": sum(v["rotte"].values())})
    ordinate = sorted(rotte.items(), key=lambda kv: kv[1], reverse=True)
    parti: dict[str, int] = {}
    for n, c in rotte.items():
        parte = parte_di(n)
        parti[parte] = parti.get(parte, 0) + c
    nomi_parti = {k: frasi.F(f"uso.parte_{k}") for k in parti}
    return {"giorni": GIORNI, "dal": min(giorni) if giorni else None, "al": max(giorni) if giorni else None,
            "richieste": sum(rotte.values()),
            "per_funzione": [{"funzione": n, "etichetta": nome_funzione(n), "richieste": c}
                             for n, c in sorted(per_funz.items(), key=lambda kv: kv[1], reverse=True)],
            "per_parte": [{"parte": n, "etichetta": str(nomi_parti[n]), "etichetta_frase": frasi.di(nomi_parti[n]), "richieste": c}
                          for n, c in sorted(parti.items(), key=lambda kv: kv[1], reverse=True)],
            "per_rotta": [{"rotta": n, "richieste": c} for n, c in ordinate[:massimo_rotte]],
            "per_giorno": per_giorno,
            "nota": "Conteggi anonimi e aggregati: nessun utente, nessun indirizzo."}
