"""Quanti minuti ci mette un amico nuovo a caricare la sua lega (#574, misura dell'obiettivo #168: «un amico entra da solo dalla
web e carica la sua lega in meno di 10 minuti»).

Usa solo dati che il server ha già, in sola lettura, senza nessun dato nuovo sugli utenti:
- l'inizio è `utenti.creato` di `account.sqlite` (UTC, con il fuso);
- la lega è caricata quando ci sono rose vere (non le squadre di esempio del primo avvio, che segna `rose` fatto anche con
  «Usa le squadre di esempio», nemmeno se rinominate) e `tempi` è fra i passi fatti del primo avvio (`avvisi-impostazioni.json`,
  campo `primo_avvio`);
- la fine è la più tarda fra `aggiornato` delle rose e `aggiornato` del primo avvio.
Trappola: quelle due ore sono SENZA fuso, nell'ora del server (`datetime.now()` in `lega.py` e `stato_utente.py`); si leggono con
`fuso_del_server`. Se l'amico riapre il primo avvio o reimporta le rose dopo, la misura viene più lunga del vero: sbaglia a sfavore.

Comando: `python -m fanta ingresso --dal <ISO con fuso> [--al <ISO con fuso>]`, sul server (come `sentinella --giri`). Una riga per
account, mai nomi utente; uscita 0 se tutti gli account del periodo sono dentro in meno di 10 minuti, 1 altrimenti, 2 se nel periodo
non c'è nessun account, 3 se la misura non si può fare (date sbagliate, database o file che non si leggono).
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

from . import lega, onboarding, percorsi, stato_utente
from .contesto import FILE_UTENTE
from .lega import Rose

DENTRO, SOLO_ESEMPIO, NON_FINITO, NON_INIZIATO = "dentro", "solo_esempio", "non_finito", "non_iniziato"
SOGLIA_MINUTI = 10
ERRORE = 3                     # codice di uscita quando la misura non si può fare: diverso da 1 («non tutti in tempo») e da 2
_FRASI = {SOLO_ESEMPIO: "solo squadre di esempio", NON_FINITO: "non finito", NON_INIZIATO: "non iniziato"}


class _FusoDelSistema(tzinfo):
    """L'ora locale del sistema con l'ora legale giusta per OGNI data (come la scrive `datetime.now()`), non solo per adesso:
    `datetime.now().astimezone().tzinfo` sarebbe uno scarto fisso, sbagliato di un'ora per le date dell'altra stagione."""

    def utcoffset(self, quando: datetime | None) -> timedelta | None:
        return None if quando is None else quando.replace(tzinfo=None).astimezone().utcoffset()

    def dst(self, quando: datetime | None) -> timedelta | None:
        return None

    def tzname(self, quando: datetime | None) -> str | None:
        return None if quando is None else quando.replace(tzinfo=None).astimezone().tzname()


def fuso_del_server() -> tzinfo:
    """Il fuso con cui il server scrive le ore senza fuso: quello del sistema su cui gira il comando (lo stesso del servizio)."""
    return _FusoDelSistema()


def _ora(testo: object, fuso: tzinfo) -> datetime | None:
    """Un'ora ISO salvata; senza fuso vale nel `fuso` indicato. Vuota o illeggibile: None."""
    if not isinstance(testo, str) or not testo:
        return None
    try:
        quando = datetime.fromisoformat(testo)
    except ValueError:
        return None
    return quando if quando.utcoffset() is not None else quando.replace(tzinfo=fuso)


def _solo_esempio(rose: Rose | None) -> bool:
    """Le squadre di esempio del primo avvio, anche rinominate: la rinomina lascia il nome di prima in `nome_importato`
    (`onboarding.e_demo` guarda solo il nome di adesso, e un amico che rinomina «Atletico Prova» risulterebbe dentro)."""
    return bool(rose and rose.squadre and {s.nome_importato or s.nome for s in rose.squadre} == set(onboarding.SQUADRE_DEMO))


def minuti_di_ingresso(creato: str, rose: Rose | None, primo_avvio: dict | None, fuso_server: tzinfo) -> tuple[str, float | None]:
    """(esito, minuti). `dentro` con i minuti dalla creazione dell'account alla lega caricata (rose vere e `tempi` fatto);
    `solo_esempio` se le rose sono le squadre di esempio; `non_finito` se mancano rose vere o `tempi` (anche se saltati);
    `non_iniziato` se non ci sono né rose né primo avvio. Minuti None anche per `dentro` quando non c'è un'ora buona (nessuna
    ora salvata, o ore prima della creazione: orologio sbagliato): mai «entro 10 minuti» per omissione."""
    if _solo_esempio(rose):
        return SOLO_ESEMPIO, None
    vere = bool(rose and rose.squadre)
    if not vere and primo_avvio is None:
        return NON_INIZIATO, None
    if not vere or primo_avvio is None or "tempi" not in (primo_avvio.get("fatti") or []):
        return NON_FINITO, None
    inizio = _ora(creato, timezone.utc)
    ore = [o for o in (_ora(rose.aggiornato, fuso_server), _ora(primo_avvio.get("aggiornato"), fuso_server)) if o]
    if inizio is None or not ore:
        return DENTRO, None
    minuti = (max(ore) - inizio).total_seconds() / 60
    return DENTRO, (minuti if minuti >= 0 else None)


def misura(db: sqlite3.Connection, cartella_utenti: Path, dal: datetime, al: datetime, fuso_server: tzinfo) -> list[dict]:
    """Gli account creati con `dal <= creato <= al`, in ordine: [{"utente": id, "esito": …, "minuti": …}]. Solo letture.
    `dal` e `al` vogliono il fuso (`creato` è in UTC: un confronto con un'ora senza fuso sarebbe sbagliato)."""
    if dal.utcoffset() is None or al.utcoffset() is None:
        raise ValueError("--dal e --al vogliono data e ora con il fuso (esempio: 2026-12-10T00:00:00+01:00 o 2026-12-09T23:00:00Z)")
    if dal > al:
        raise ValueError("--dal viene dopo --al: nessun periodo da misurare")
    righe = []
    for utente, creato in db.execute("SELECT id, creato FROM utenti ORDER BY id").fetchall():
        quando = _ora(creato, timezone.utc)
        if quando is None:
            raise ValueError(f"utente {utente}: la data di creazione dell'account non si legge")
        if not dal <= quando <= al:
            continue
        cartella = Path(cartella_utenti) / str(int(utente))
        try:
            rose = lega.carica(cartella / FILE_UTENTE["rose"])
        except ValueError as e:                # rose rovinate: un amico con l'app rotta si deve vedere, non sparire dalla misura
            raise ValueError(f"utente {utente}: {e}") from None
        primo = stato_utente.leggi_primo_avvio(cartella / FILE_UTENTE["impostazioni_avvisi"])
        esito, minuti = minuti_di_ingresso(creato, rose, primo, fuso_server)
        righe.append({"utente": int(utente), "esito": esito, "minuti": minuti})
    return righe


def apri_in_sola_lettura(percorso: Path) -> sqlite3.Connection:
    """Il database degli account in sola lettura (`mode=ro`): niente migrazioni, e se manca non si crea."""
    if not percorso.is_file():
        raise ValueError("Non trovo il database degli account: il comando va lanciato sul server che ha gli account.")
    return sqlite3.connect(percorso.resolve().as_uri() + "?mode=ro", uri=True)


def _numero(minuti: float) -> str:
    """Troncato al decimo, mai arrotondato: 9 minuti e 58 secondi sono «9,9», non «10» (che non conta come in tempo)."""
    return f"{math.floor(minuti * 10) / 10:.1f}".replace(".", ",").removesuffix(",0")


def _riga(r: dict) -> str:
    if r["esito"] != DENTRO:
        return f"utente {r['utente']}: {_FRASI[r['esito']]}"
    if r["minuti"] is None:
        return f"utente {r['utente']}: dentro, minuti non misurabili"
    numero = _numero(r["minuti"])
    return f"utente {r['utente']}: dentro in {numero} {'minuto' if numero == '1' else 'minuti'}"


def _in_tempo(r: dict) -> bool:
    return r["esito"] == DENTRO and r["minuti"] is not None and r["minuti"] < SOGLIA_MINUTI


def riassunto(righe: list[dict]) -> tuple[list[str], int]:
    """Le righe da stampare e il codice di uscita: 0 se tutti dentro in meno di 10 minuti, 1 se no, 2 se nessun account."""
    in_tempo = sum(_in_tempo(r) for r in righe)
    testo = [_riga(r) for r in righe] + [f"dentro in meno di {SOGLIA_MINUTI} minuti: {in_tempo} su {len(righe)}"]
    if not righe:
        return testo, 2
    return testo, 0 if in_tempo == len(righe) else 1


def comando(dal: datetime, al: datetime) -> int:
    """Il comando `ingresso`: stampa le righe e restituisce il codice di uscita. Database o file degli utenti che non si
    leggono: errore con il motivo (ValueError, codice ERRORE per chi lo lancia), mai una misura a metà.
    Unica eccezione: un `avvisi-impostazioni.json` rovinato vale «primo avvio mai iniziato» (`stato_utente.leggi_primo_avvio`
    non distingue), quindi quell'account risulta «non finito» o «non iniziato» senza messaggio: la misura sbaglia a sfavore."""
    try:
        db = apri_in_sola_lettura(percorsi.cartella_account() / "account.sqlite")
        try:
            righe = misura(db, percorsi.cartella_utenti(), dal, al, fuso_del_server())
        finally:
            db.close()
    except (sqlite3.DatabaseError, OSError) as e:
        raise ValueError(f"il database degli account o i file degli utenti non si leggono ({type(e).__name__}): "
                         "lancia il comando sul server, con l'utente del servizio") from None
    testo, codice = riassunto(righe)
    print("\n".join(testo))
    return codice
