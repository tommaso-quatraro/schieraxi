"""La formazione scelta a mano per una giornata ("la mia scelta"): resta sul server, così si ritrova da ogni dispositivo
e un domani si potrà confrontare con quella consigliata. Un file solo, una voce per giornata."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro

FILE_SCELTE = RADICE / "dati" / "scelte.json"
MAX_GIORNATE = 60
TIPO_AUTOMATICA = "automatica"
_blocco = threading.Lock()


def _tutte(percorso: Path | None = None) -> dict:
    try:
        d = json.loads((percorso or FILE_SCELTE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def leggi(stagione: str, giornata: int, percorso: Path | None = None, anche_automatica: bool = False) -> dict | None:
    """La scelta dell'utente per la giornata. La copia salvata in automatico dal programma (tipo «automatica») non è una scelta
    dell'utente: si vede solo con `anche_automatica=True`."""
    v = _tutte(percorso).get(f"{stagione}/{giornata}")
    if not (isinstance(v, dict) and isinstance(v.get("titolari"), list)):
        return None
    return v if anche_automatica or v.get("tipo") != TIPO_AUTOMATICA else None


def salva(stagione: str, giornata: int, titolari: list[int], modulo: str, percorso: Path | None = None, tipo: str = "manuale",
          panchina: list[int] | None = None) -> dict:
    """Salva la scelta dell'utente. `tipo`: «manuale» (scelta a mano, anche quando non c'è il campo: file vecchi) o «consigliata»
    (ha detto «ho schierato la consigliata»). `panchina` (facoltativa, per le giornate importate): gli id della panchina nell'ordine
    in cui l'hai schierata; senza, il Diario sceglie la panchina da solo."""
    with _blocco:
        tutte = _tutte(percorso)
        voce = {"titolari": [int(i) for i in titolari], "modulo": modulo, "salvata": datetime.now().isoformat(timespec="seconds"),
                "tipo": tipo}
        if panchina:
            voce["panchina"] = [int(i) for i in panchina][:20]
        tutte[f"{stagione}/{giornata}"] = voce
        for vecchia in chiavi_vecchie(tutte, MAX_GIORNATE):
            tutte.pop(vecchia, None)
        scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
        return voce


def salva_automatica(stagione: str, giornata: int, titolari: list[int], modulo: str, percorso: Path | None = None) -> bool:
    """Ricorda la formazione consigliata come copia automatica, ma solo se l'utente non ha già una sua scelta per la giornata.
    True se ha scritto qualcosa (la copia cambia finché la formazione non si chiude)."""
    with _blocco:
        tutte = _tutte(percorso)
        chiave = f"{stagione}/{giornata}"
        attuale = tutte.get(chiave)
        if isinstance(attuale, dict) and attuale.get("tipo") != TIPO_AUTOMATICA and isinstance(attuale.get("titolari"), list):
            return False
        nuovi = [int(i) for i in titolari]
        if isinstance(attuale, dict) and attuale.get("titolari") == nuovi and attuale.get("modulo") == modulo:
            return False
        tutte[chiave] = {"titolari": nuovi, "modulo": modulo, "salvata": datetime.now().isoformat(timespec="seconds"), "tipo": TIPO_AUTOMATICA}
        for vecchia in chiavi_vecchie(tutte, MAX_GIORNATE):
            tutte.pop(vecchia, None)
        scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
        return True


def cancella(stagione: str, giornata: int, percorso: Path | None = None) -> None:
    with _blocco:
        tutte = _tutte(percorso)
        if tutte.pop(f"{stagione}/{giornata}", None) is not None:
            scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
