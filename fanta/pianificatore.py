"""Pianificatore dentro il servizio: aggiorna probabili e infortuni più spesso nei momenti che contano.

Le consuete quattro volte al giorno restano quelle del server (cron, non toccato). Qui si aggiungono tre giri vicino alla
scadenza della formazione: a 60, 30 e 15 minuti prima (la scadenza è la prima partita della giornata meno i minuti della regola
`scadenza_minuti` della lega). Un thread controlla ogni minuto; quando un giro è dovuto:
- scarica SOLO le probabili (una pagina di Fantacalcio.it) e, se è passata la sua pausa, la seconda fonte: una richiesta per fonte
  alla volta, con la pausa di `rete.py`, mai a raffica;
- segna l'aggiornamento (così il riscaldamento ricalcola formazione e mercato da solo) e subito dopo manda gli avvisi sui cambi.
Non parte se: un aggiornamento completo è in corso (nel servizio o dal cron), le probabili sono state lette meno di 8 minuti fa,
la scadenza è passata. Dopo un riavvio non rifà i giri già fatti (stato in `dati/pianificatore.json`). Se il servizio era fermo e
due giri sono scaduti insieme se ne fa uno solo. Si spegne con `FANTA_PIANIFICATORE=0` oppure, per ogni lega, con l'impostazione
`aggiornamenti_vicino_scadenza` delle regole (spenta in tutte le leghe attive = nessun giro).
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
from datetime import date, datetime, timedelta
from typing import Callable, Iterator

from . import archivio, avvisi, consigli
from .percorsi import RADICE, scrivi_sicuro
from .regole import Regole

FILE_STATO = RADICE / "dati" / "pianificatore.json"
GIRI = (("60", 60), ("30", 30), ("15", 15))        # (nome, minuti prima della scadenza)
DISTANZA_MINIMA = timedelta(minutes=8)             # tra due letture delle probabili: le fonti non si martellano
INTERVALLO = 60                                    # secondi tra un controllo e l'altro
CHIAVE_ARCHIVIO = "probabili-rapido"
LOG = logging.getLogger(__name__)
TENUTI = 60                                        # giri ricordati nello stato


def acceso() -> bool:
    """Interruttore del servizio (variabile d'ambiente): `FANTA_PIANIFICATORE=0` lo spegne."""
    return os.environ.get("FANTA_PIANIFICATORE", "1").strip().lower() not in ("0", "no", "false", "off")


def giro_dovuto(adesso: datetime, scadenza: datetime | None, fatti: set[str], prefisso: str) -> tuple[str | None, list[str]]:
    """(giro da fare, giri da segnare come fatti). Un giro è dovuto da `minuti` prima della scadenza fino alla scadenza.
    Se ne sono scaduti più d'uno (servizio fermo) si fa solo l'ultimo e si segnano tutti."""
    if scadenza is None or adesso >= scadenza:
        return None, []
    dovuti = [nome for nome, minuti in GIRI if scadenza - timedelta(minutes=minuti) <= adesso and f"{prefisso}/{nome}" not in fatti]
    if not dovuti:
        return None, []
    return dovuti[-1], [f"{prefisso}/{n}" for n in dovuti]


def _scadenza(db, regole: Regole, adesso: datetime) -> tuple[str, datetime | None]:
    """(chiave della giornata, scadenza della formazione) per la prossima giornata della lega."""
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole)
    if giornata is None:
        return "", None
    return f"{stagione}/{giornata}/{regole.scadenza_minuti}", avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)


def probabili_recenti(db, adesso: datetime) -> bool:
    """True se le probabili sono state lette da meno di DISTANZA_MINIMA (anche dal cron): inutile rileggerle."""
    try:
        r = db.execute("SELECT MAX(rilevato) FROM probabili WHERE fonte = 'fantacalcio'").fetchone()
        ultima = datetime.fromisoformat(str(r[0])[:19]) if r and r[0] else None
    except Exception:  # noqa: BLE001 - tabella o data illeggibili: meglio rileggere
        return False
    return ultima is not None and timedelta(0) <= adesso - ultima < DISTANZA_MINIMA


def carica_stato(percorso=None) -> dict:
    try:
        dati = json.loads((percorso or FILE_STATO).read_text(encoding="utf-8"))
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError):
        return {}


def salva_stato(stato: dict, percorso=None) -> None:
    stato["fatti"] = list(stato.get("fatti", []))[-TENUTI:]
    scrivi_sicuro(percorso or FILE_STATO, json.dumps(stato))


def giro(adesso: datetime, db, leghe: list[Regole], stato: dict, aggiorna: Callable[[], bool | None], dopo: Callable[[], object]) -> str | None:
    """Un controllo. `leghe` = le regole delle leghe attive (una per utente; senza account una sola). `aggiorna()` scarica le probabili
    e dice se è riuscito (True/False) oppure None se era occupato: in quel caso il giro non conta come fatto e si riprova; `dopo()` ricalcola e manda gli avvisi. Restituisce il nome del giro fatto, o None."""
    fatti = set(stato.get("fatti", []))
    da_fare = None
    segnare: list[str] = []
    for regole in {(r.scadenza_minuti, r.prima_giornata_lega): r for r in leghe if r.aggiornamenti_vicino_scadenza}.values():
        prefisso, scadenza = _scadenza(db, regole, adesso)
        nome, tutti = giro_dovuto(adesso, scadenza, fatti, prefisso)
        if nome:
            da_fare = da_fare or nome
            segnare += tutti
    if not da_fare:
        return None
    prima = list(stato.get("fatti", []))
    stato["fatti"] = prima + segnare                             # segnato prima: un errore non deve far ripartire un giro dopo l'altro
    if probabili_recenti(db, adesso):
        return None                                             # già lette da poco (per esempio dal cron): il giro conta come fatto
    esito = aggiorna()
    if esito is None:                                           # occupato (aggiornamento completo in corso): non conta, si riprova
        stato["fatti"] = prima
        return None
    if esito:
        dopo()
    return da_fare


@contextlib.contextmanager
def blocco_processo() -> Iterator[bool]:
    """Lo stesso blocco dell'aggiornamento del server (`~/.cache/fantacalcio/blocco`): se `aggiorna.sh` sta girando, si rinuncia.
    Dove il blocco di file non esiste (Windows) o la cartella manca, si va avanti."""
    try:
        import fcntl
        from pathlib import Path
        cartella = Path.home() / ".cache" / "fantacalcio"
        cartella.mkdir(parents=True, exist_ok=True)
        f = open(cartella / "blocco", "w")          # noqa: SIM115 - serve aperto per tutta la durata
    except (ImportError, OSError):
        yield True
        return
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        f.close()


def aggiorna_probabili(scrivi: Callable[[str], None] = lambda _: None) -> bool | None:
    """Scarica le probabili (e la seconda fonte, che ha la sua pausa) e segna l'aggiornamento. True se le probabili sono arrivate,
    None se l'aggiornamento del server (cron) sta girando: il blocco di file si tiene solo durante il download."""
    with blocco_processo() as libero:
        if not libero:
            return None
        return _scarica_probabili(scrivi)


def _scarica_probabili(scrivi: Callable[[str], None]) -> bool:
    from . import fonti_attive
    from .aggiorna import Aggiornamento, Stagione, _ora
    if not fonti_attive.acceso("fantacalcio"):
        return False                                                # fonte spenta: niente richieste
    db = archivio.apri()
    try:
        agg = Aggiornamento(db, Stagione.di(date.today()), scrivi)
        agg._passo("probabili", agg.probabili)                      # noqa: SLF001 - stesso passo dell'aggiornamento completo
        riuscito = not any(e.startswith("probabili:") for e in agg.errori)
        if riuscito:
            agg._passo("probabili fonte 2", agg.probabili_fonte2, "sosfanta")   # noqa: SLF001
            archivio.segna(db, CHIAVE_ARCHIVIO, _ora())             # cambia la «versione» dei dati: il riscaldamento ricalcola
            db.commit()
        return riuscito
    finally:
        db.close()


def sorveglia(fermo: threading.Event, leghe: Callable[[], list[Regole]], apri_db: Callable[[], object],
              aggiorna: Callable[[], bool], dopo: Callable[[], object], intervallo: float = INTERVALLO,
              adesso: Callable[[], datetime] = datetime.now) -> None:
    """Il thread. `leghe()` dà le regole delle leghe attive; `aggiorna()` scarica le probabili (False se non è riuscito, None se un aggiornamento completo è in corso); `dopo()` ricalcola e manda gli avvisi."""
    from .riscaldamento import bassa_priorita
    bassa_priorita()
    while not fermo.is_set():
        stato: dict = {}
        try:
            if acceso():
                stato = carica_stato()
                prima = list(stato.get("fatti", []))
                db = apri_db()
                try:
                    giro(adesso(), db, leghe(), stato, aggiorna, dopo)
                finally:
                    db.close()
                    try:
                        if stato.get("fatti", []) != prima:
                            salva_stato(stato)
                    except Exception as e:  # noqa: BLE001
                        LOG.warning("pianificatore: stato non salvato (%s)", type(e).__name__)
        except Exception as e:  # noqa: BLE001 - il controllo deve continuare anche dopo un errore
            LOG.warning("pianificatore: giro non riuscito (%s)", type(e).__name__)
        fermo.wait(intervallo)
