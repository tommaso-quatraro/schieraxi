"""Quanto è affidabile il modello: prova sulle ultime giornate già giocate (usando solo i dati che c'erano prima di ognuna).

Confronta il modello con una scelta "da fantamedia" (la formazione scelta con la fantamedia tirata verso il ruolo e la stessa
probabilità di giocare del modello; testo per l'utente: `avv.prova_su`) su tre cose: l'errore sul fantavoto di chi ha giocato,
i punti delle formazioni consigliate alle rose della lega e il massimo possibile col senno di poi. Il calcolo è pesante (simulazioni):
si rifà solo quando cambiano le giornate finite (con i voti di tutte le partite), i loro voti, le regole o i giocatori delle
rose, e il risultato resta in dati/affidabilita.json (con gli account, nella cartella di ogni utente).
Dal 12/11/2026 (#614) la fantamedia è quella tirata verso il ruolo (`verifica.avversari`): `errore_fantamedia` e
`punti_fantamedia` sono un confronto onesto. In più, facoltativi: `errore_ruolo` (un numero fisso per ruolo),
`errore_fantamedia_stagione` (l'avversario di prima) e `rose_a_sorte` (punti su rose estratte a sorte, con l'intervallo).
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import consigli, fasi, frasi, modello, verifica
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


def giornate_concluse(db: sqlite3.Connection, stagione: str, regole: Regole | None = None) -> list[int]:
    """Le giornate finite della stagione: tutte le partite giocate e i voti di tutte e due le squadre di ognuna, nella colonna del
    voto della lega (`fasi.voti_arrivati`, la regola del riepilogo di Oggi e del Diario). Prima bastava «giocata»: una partita
    con i voti non ancora arrivati contava i suoi giocatori come «non hanno giocato» (#832)."""
    regole = regole or Regole()
    giocate = [r[0] for r in db.execute("SELECT giornata FROM partite WHERE stagione = ? GROUP BY giornata HAVING MIN(giocata) = 1 "
                                        "ORDER BY giornata", (stagione,))]
    return [g for g in giocate if fasi.voti_arrivati(db, stagione, g, regole)]


def sintesi(righe: list[dict]) -> dict:
    """Medie sulle giornate provate: errore (radice della media dei quadrati, due cifre) e punti medi delle formazioni (una cifra),
    arrotondati con la regola di `frasi.arrotonda`, come li scrivono web e iPhone."""
    def media(chiave):
        v = [r[chiave] for r in righe if r.get(chiave) is not None and not (isinstance(r[chiave], float) and math.isnan(r[chiave]))]
        return sum(v) / len(v) if v else None
    radice = lambda q: frasi.arrotonda(math.sqrt(q), 2) if q is not None else None      # noqa: E731
    return {"giornate": len(righe),
            "errore_modello": radice(media("quadratico_modello")), "errore_fantamedia": radice(media("quadratico_fantamedia")),
            "errore_ruolo": radice(media("quadratico_ruolo")),
            "errore_fantamedia_stagione": radice(media("quadratico_fantamedia_stagione")),
            "punti_modello": _arr(media("punti_modello")), "punti_fantamedia": _arr(media("punti_fantamedia")),
            "punti_perfetta": _arr(media("punti_perfetta"))}


def _arr(x):
    return None if x is None else frasi.arrotonda(x, 1)


def giornate_della_prova(db: sqlite3.Connection, regole: Regole | None = None) -> list[tuple[str, int]]:
    """Le giornate su cui si fa la prova: le ultime MASSIMO_GIORNATE concluse della stagione in corso, completate con le ultime
    della precedente se sono meno di MINIMO_GIORNATE (d'estate, prima della prima giornata, sono tutte della precedente)."""
    stagione = consigli.stagione_corrente()
    precedente = f"{int(stagione[:4]) - 1}-{stagione[2:4]}"
    elenco = [(stagione, g) for g in giornate_concluse(db, stagione, regole)[-MASSIMO_GIORNATE:]]
    if len(elenco) < MINIMO_GIORNATE:
        elenco = [(precedente, g) for g in giornate_concluse(db, precedente, regole)[-(MASSIMO_GIORNATE - len(elenco)):]] + elenco
    return elenco


def _chiave(elenco: list[tuple[str, int]]) -> str | None:
    """L'ultima giornata della prova, «stagione/giornata» (None senza giornate): il campo `ultima` del file, che i client mostrano."""
    return f"{elenco[-1][0]}/{elenco[-1][1]}" if elenco else None


def _liste(rose: Rose | None) -> list[list[int]] | None:
    """I giocatori di ogni squadra (solo gli id riconosciuti), come la prova li passa a `verifica.verifica`."""
    return [[g.id for g in s.giocatori if g.id is not None] for s in rose.squadre] if rose else None


def impronta(db: sqlite3.Connection, elenco: list[tuple[str, int]], regole: Regole | None = None,
             rose: Rose | None = None) -> str:
    """Impronta (hash corto) di ciò da cui esce la prova: le giornate e i loro voti, le regole e i giocatori delle rose. Cambia se
    entra una giornata (finita, o con un recupero giocato e i suoi voti), se ne esce una, se un voto si corregge (#832) o se
    l'utente cambia le sue regole o le sue rose (#840). Con questa si decide se rifare la prova. Le regole ci sono tutte, come
    nella memoria di `verifica.verifica` (anche i campi che non cambiano i punti: al più una prova in più); delle rose solo gli id
    dei giocatori di ogni squadra, senza i nomi: rinominare una squadra non la rifà."""
    h = hashlib.sha1()
    h.update(json.dumps(asdict(regole or Regole()), sort_keys=True, default=str).encode("utf-8"))
    liste = _liste(rose)
    h.update(json.dumps(None if liste is None else sorted(sorted(ids) for ids in liste)).encode("utf-8"))
    for stagione, g in elenco:
        h.update(json.dumps([stagione, g]).encode("utf-8"))
        for r in db.execute("SELECT * FROM voti WHERE stagione = ? AND giornata = ? ORDER BY calciatore_id", (stagione, g)):
            h.update(json.dumps(list(r), default=str).encode("utf-8"))
    return h.hexdigest()[:12]


def calcola(db: sqlite3.Connection, regole: Regole, rose: Rose | None, simulazioni: int = 200,
            elenco: list[tuple[str, int]] | None = None, memo: dict | None = None) -> dict:
    """La prova sulle giornate di `elenco` (di norma `giornate_della_prova`) con le regole e le rose date. `memo`: le rose a
    sorte già provate nello stesso giro (`verifica.verifica`), così con gli account la prova di ogni utente non le rifà."""
    elenco = giornate_della_prova(db, regole) if elenco is None else elenco
    df = verifica.verifica(consigli.dati(db), regole, modello.Parametri(), elenco, rose=_liste(rose), simulazioni=simulazioni,
                           scrivi=None, sintetiche=verifica.ROSE_A_SORTE, memo=memo)
    righe = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()} for r in df.to_dict("records")]
    ultima = _chiave(elenco)
    riassunto = sintesi(righe)
    # i punti su rose estratte a sorte, tutte le giornate insieme: le poche rose della lega non distinguono mezzo punto
    sorte = verifica.riepilogo_sorte(df.assign(stagione="tutte")).get("tutte") if len(df) else None
    if sorte:
        riassunto["rose_a_sorte"] = {k: (v if isinstance(v, int) else round(v, 2)) for k, v in sorte.items()}
    return {"calcolato": datetime.now().isoformat(timespec="seconds"), "ultima": ultima, "righe": righe, "sintesi": riassunto}


def aggiorna_se_serve(db: sqlite3.Connection, regole: Regole, rose: Rose | None, forza: bool = False,
                      percorso: Path | None = None, simulazioni: int = 200, memo: dict | None = None) -> bool:
    """Rifà la prova solo se dall'ultima volta sono cambiate le giornate della prova, i loro voti, le regole o le rose (`impronta`,
    salvata nel file). True se ha ricalcolato. Le giornate sono quelle della prova (`giornate_della_prova`), non della sola
    stagione in corso: d'estate quella non ne ha e la prova ripartiva a ogni giro del cron. Un file senza impronta (scritto prima
    di #832) o con quella di prima di #840 (senza regole e rose) si rifà una volta."""
    elenco = giornate_della_prova(db, regole)
    nuova = impronta(db, elenco, regole, rose)
    vecchio = carica(percorso)
    if not forza and vecchio.get("impronta") == nuova and vecchio.get("righe"):
        return False
    esito = calcola(db, regole, rose, simulazioni, elenco=elenco, memo=memo) | {"impronta": nuova}
    scrivi_sicuro(percorso or FILE, json.dumps(esito, ensure_ascii=False))
    return True
