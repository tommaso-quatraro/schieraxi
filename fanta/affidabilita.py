"""Quanto è affidabile il modello: prova sulle ultime giornate già giocate (usando solo i dati che c'erano prima di ognuna).

Confronta il modello con una scelta "da fantamedia" (chi ha la media più alta) su tre cose: l'errore sul fantavoto di chi ha giocato,
i punti delle formazioni consigliate alle rose della lega e il massimo possibile col senno di poi. Il calcolo è pesante (simulazioni):
si rifà solo quando finisce una nuova giornata e il risultato resta in dati/affidabilita.json.
Dal 12/11/2026 (#614) la fantamedia è quella tirata verso il ruolo (`verifica.avversari`): `errore_fantamedia` e
`punti_fantamedia` sono un confronto onesto. In più, facoltativi: `errore_ruolo` (un numero fisso per ruolo),
`errore_fantamedia_stagione` (l'avversario di prima) e `rose_a_sorte` (punti su rose estratte a sorte, con l'intervallo).
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

from . import consigli, modello, verifica
from .lega import Rose
from .percorsi import RADICE, scrivi_sicuro
from .regole import Regole

FILE = RADICE / "dati" / "affidabilita.json"
MASSIMO_GIORNATE = 8
MINIMO_GIORNATE = 4        # se la stagione in corso ne ha meno, si completano con quelle della precedente


def carica(percorso: Path | None = None) -> dict:
    try:
        d = json.loads((percorso or FILE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def giornate_concluse(db: sqlite3.Connection, stagione: str) -> list[int]:
    return [r[0] for r in db.execute("SELECT giornata FROM partite WHERE stagione = ? GROUP BY giornata HAVING MIN(giocata) = 1 "
                                     "ORDER BY giornata", (stagione,))]


def sintesi(righe: list[dict]) -> dict:
    """Medie sulle giornate provate: errore (radice della media dei quadrati) e punti medi delle formazioni."""
    def media(chiave):
        v = [r[chiave] for r in righe if r.get(chiave) is not None and not (isinstance(r[chiave], float) and math.isnan(r[chiave]))]
        return sum(v) / len(v) if v else None
    radice = lambda q: round(math.sqrt(q), 2) if q is not None else None      # noqa: E731
    return {"giornate": len(righe),
            "errore_modello": radice(media("quadratico_modello")), "errore_fantamedia": radice(media("quadratico_fantamedia")),
            "errore_ruolo": radice(media("quadratico_ruolo")),
            "errore_fantamedia_stagione": radice(media("quadratico_fantamedia_stagione")),
            "punti_modello": _arr(media("punti_modello")), "punti_fantamedia": _arr(media("punti_fantamedia")),
            "punti_perfetta": _arr(media("punti_perfetta"))}


def _arr(x):
    return None if x is None else round(x, 1)


def calcola(db: sqlite3.Connection, regole: Regole, rose: Rose | None, simulazioni: int = 200) -> dict:
    stagione = consigli.stagione_corrente()
    precedente = f"{int(stagione[:4]) - 1}-{stagione[2:4]}"
    elenco = [(stagione, g) for g in giornate_concluse(db, stagione)[-MASSIMO_GIORNATE:]]
    if len(elenco) < MINIMO_GIORNATE:
        elenco = [(precedente, g) for g in giornate_concluse(db, precedente)[-(MASSIMO_GIORNATE - len(elenco)):]] + elenco
    liste = [[g.id for g in s.giocatori if g.id is not None] for s in rose.squadre] if rose else None
    df = verifica.verifica(consigli.dati(db), regole, modello.Parametri(), elenco, rose=liste, simulazioni=simulazioni, scrivi=None,
                           sintetiche=verifica.ROSE_A_SORTE)
    righe = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()} for r in df.to_dict("records")]
    ultima = f"{elenco[-1][0]}/{elenco[-1][1]}" if elenco else None
    riassunto = sintesi(righe)
    # i punti su rose estratte a sorte, tutte le giornate insieme: le poche rose della lega non distinguono mezzo punto
    sorte = verifica.riepilogo_sorte(df.assign(stagione="tutte")).get("tutte") if len(df) else None
    if sorte:
        riassunto["rose_a_sorte"] = {k: (v if isinstance(v, int) else round(v, 2)) for k, v in sorte.items()}
    return {"calcolato": datetime.now().isoformat(timespec="seconds"), "ultima": ultima, "righe": righe, "sintesi": riassunto}


def aggiorna_se_serve(db: sqlite3.Connection, regole: Regole, rose: Rose | None, forza: bool = False,
                      percorso: Path | None = None, simulazioni: int = 200) -> bool:
    """Rifà la prova solo se dall'ultima volta è finita una giornata nuova. True se ha ricalcolato."""
    stagione = consigli.stagione_corrente()
    conc = giornate_concluse(db, stagione)
    chiave = f"{stagione}/{conc[-1]}" if conc else None
    vecchio = carica(percorso)
    if not forza and vecchio.get("ultima") == chiave and vecchio.get("righe"):
        return False
    scrivi_sicuro(percorso or FILE, json.dumps(calcola(db, regole, rose, simulazioni), ensure_ascii=False))
    return True
