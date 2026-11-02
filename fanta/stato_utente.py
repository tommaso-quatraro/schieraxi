"""Due piccoli campi dell'utente che stanno nel file delle sue impostazioni (lo stesso degli avvisi, `avvisi-impostazioni.json`):

- `primo_avvio`: a che punto è la configurazione guidata (passi fatti, passi saltati, se l'ha chiusa);
- `backup_il`: quando ha scaricato l'ultima copia dei dati (serve a «Da fare» per ricordargli il backup).

Il file lo scrive anche `notifiche.salva_impostazioni`, che questi campi li lascia intatti. Tutto quello che si legge dal file
viene ripulito (il file può arrivare da un backup ripristinato): nessun valore sconosciuto esce da qui.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import json

from . import notifiche
from .percorsi import scrivi_sicuro

# i passi della configurazione guidata (l'ordine è quello in cui si propongono); i primi due si segnano da soli
PASSI = ("server", "accesso", "rose", "stemma", "squadra", "pwa", "widget", "avvisi")
MAX_TESTO = 40


class ErroreStato(ValueError):
    """Valore non accettato (messaggio già in italiano, per l'utente)."""


def _ora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _pulisci(valore) -> dict:
    """Il `primo_avvio` salvato, in forma sicura: liste di passi noti senza doppioni, `chiuso` booleano, `aggiornato` testo breve."""
    if not isinstance(valore, dict):
        return {}
    fatti = [p for p in PASSI if p in (valore.get("fatti") if isinstance(valore.get("fatti"), list) else [])]
    saltati = [p for p in PASSI if p in (valore.get("saltati") if isinstance(valore.get("saltati"), list) else []) and p not in fatti]
    agg = valore.get("aggiornato")
    return {"fatti": fatti, "saltati": saltati, "chiuso": valore.get("chiuso") is True,
            "aggiornato": agg[:MAX_TESTO] if isinstance(agg, str) else None}


def leggi_primo_avvio(percorso: Path) -> dict | None:
    """None = non l'ha mai iniziato (o il file non c'è)."""
    grezzo = notifiche._json(percorso).get("primo_avvio")
    return _pulisci(grezzo) if isinstance(grezzo, dict) else None


def scrivi_primo_avvio(percorso: Path, fatti: list | None = None, saltati: list | None = None, chiuso: bool | None = None) -> dict:
    """Cambia solo i campi indicati. Un passo sconosciuto o liste troppo lunghe: errore chiaro, non si salva niente."""
    for nome, lista in (("fatti", fatti), ("saltati", saltati)):
        if lista is None:
            continue
        if not isinstance(lista, list) or len(lista) > len(PASSI) or any(not isinstance(p, str) for p in lista):
            raise ErroreStato("Elenco dei passi non valido")
        if any(p not in PASSI for p in lista):
            raise ErroreStato("Passo sconosciuto della configurazione")
    with notifiche.BLOCCO_FILE:
        tutto = notifiche._json(percorso)
        attuale = _pulisci(tutto.get("primo_avvio"))
        nuovo = {"fatti": attuale.get("fatti", []) if fatti is None else fatti,
                 "saltati": attuale.get("saltati", []) if saltati is None else saltati,
                 "chiuso": attuale.get("chiuso", False) if chiuso is None else chiuso is True, "aggiornato": _ora()}
        tutto["primo_avvio"] = _pulisci(nuovo)
        scrivi_sicuro(percorso, json.dumps(tutto))
        return tutto["primo_avvio"]


def leggi_backup_il(percorso: Path) -> datetime | None:
    v = notifiche._json(percorso).get("backup_il")
    try:
        return datetime.fromisoformat(v[:19]) if isinstance(v, str) else None
    except ValueError:
        return None


def segna_backup(percorso: Path, adesso: datetime | None = None) -> None:
    """Ricorda la data dell'ultimo backup scaricato (se l'ultima è di meno di un'ora fa non riscrive il file)."""
    adesso = adesso or datetime.now()
    with notifiche.BLOCCO_FILE:
        tutto = notifiche._json(percorso)
        try:
            if abs((adesso - datetime.fromisoformat(str(tutto.get("backup_il"))[:19])).total_seconds()) < 3600:
                return
        except ValueError:
            pass
        tutto["backup_il"] = adesso.isoformat(timespec="seconds")
        scrivi_sicuro(percorso, json.dumps(tutto))


def leggi_mostra_tutte(percorso: Path) -> bool:
    """«Mostra tutte le funzioni» (Impostazioni avanzate): vero solo se l'utente l'ha acceso di proposito."""
    return notifiche._json(percorso).get("mostra_tutte") is True


def scrivi_mostra_tutte(percorso: Path, valore: bool) -> bool:
    with notifiche.BLOCCO_FILE:
        tutto = notifiche._json(percorso)
        tutto["mostra_tutte"] = valore is True
        scrivi_sicuro(percorso, json.dumps(tutto))
        return tutto["mostra_tutte"]
