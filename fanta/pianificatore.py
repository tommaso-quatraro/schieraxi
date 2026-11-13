"""Pianificatore dentro il servizio: aggiorna probabili e infortuni più spesso nei momenti che contano.

Le consuete quattro volte al giorno restano quelle del server (cron, non toccato). Qui si aggiungono tre giri vicino alla
scadenza della formazione: a 60, 30 e 15 minuti prima (la scadenza è la prima partita della giornata meno i minuti della regola
`scadenza_minuti` della lega). Un thread controlla ogni minuto; quando un giro è dovuto:
- scarica SOLO le probabili (una pagina di Fantacalcio.it), con la pausa di `rete.py`, mai a raffica;
- segna l'aggiornamento (così il riscaldamento ricalcola formazione e mercato da solo) e subito dopo manda gli avvisi sui cambi.
Non parte se: un aggiornamento completo è in corso (nel servizio o dal cron), le probabili sono state lette meno di 8 minuti fa,
la scadenza è passata. Dopo un riavvio non rifà i giri già fatti (stato in `dati/pianificatore.json`). Se il servizio era fermo e
due giri sono scaduti insieme se ne fa uno solo. Si spegne con `FANTA_PIANIFICATORE=0` oppure, per ogni lega, con l'impostazione
`aggiornamenti_vicino_scadenza` delle regole (spenta in tutte le leghe attive = nessun giro).

Giro dei risultati (`giro_risultati`): per ogni orario di calcio d'inizio, 2 ore e 30 dopo si leggono risultati e voti di quella
giornata (due pagine di Fantacalcio.it, `Aggiornamento.risultati_giornata`), e 4 ore dopo una seconda volta solo se mancano
ancora risultati o voti. Così la partita «finita», i punti fatti e la fine della giornata arrivano la sera stessa e non col giro del
mattino. Partite alla stessa ora = un giro; niente se il cron ha già portato tutto; niente oltre 12 ore dal calcio d'inizio.

Registro delle giornate (`registro_giornate.py`): a ogni controllo, dopo i giri, salva i numeri mostrati poco prima della prima
partita, misura le giornate finite e avvisa il proprietario se una media resta fuori soglia. Si spegne con
`FANTA_REGISTRO_GIORNATE=0`.
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
GIRI_RISULTATI = (("1", timedelta(minutes=150)), ("2", timedelta(hours=4)))   # dopo il calcio d'inizio
MARGINE_RISULTATI = timedelta(hours=12)            # oltre, ci pensa l'aggiornamento completo
CHIAVE_RISULTATI = archivio.PASSO_SERA                # la riga del giro della sera in `aggiornamenti`


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
    giornata = consigli.giornata_da_giocare(db, stagione, regole, adesso)     # l'ora del controllo, non l'orologio vero
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


def risultati_dovuti(adesso: datetime, db, fatti: set[str]) -> tuple[list[int], list[str]]:
    """(giornate da rileggere, giri da segnare come fatti). Un giro è per orario di calcio d'inizio: dovuto da `ritardo` dopo, se
    a qualche partita di quell'orario mancano ancora il risultato o i voti (altrimenti si segna senza leggere niente)."""
    stagione = consigli.stagione_corrente()
    righe = db.execute("SELECT giornata, data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND data >= ? AND data <= ?",
                       (stagione, (adesso - MARGINE_RISULTATI).strftime("%Y-%m-%d %H:%M"),
                        (adesso - GIRI_RISULTATI[0][1]).strftime("%Y-%m-%d %H:%M"))).fetchall()
    orari: dict[tuple[int, str], list] = {}
    for g, data, casa, trasf, giocata in righe:
        orari.setdefault((int(g), str(data)[:16]), []).append((casa, trasf, giocata))
    con_voti: dict[int, set[str]] = {}
    giornate: set[int] = set()
    segnare: list[str] = []
    for (g, ora), partite in sorted(orari.items()):
        try:
            inizio = datetime.fromisoformat(ora.replace("T", " "))
        except ValueError:
            continue
        dovuti = [f"risultati/{stagione}/{g}/{ora}/{nome}" for nome, ritardo in GIRI_RISULTATI if inizio + ritardo <= adesso]
        dovuti = [k for k in dovuti if k not in fatti]
        if not dovuti:
            continue
        if g not in con_voti:
            con_voti[g] = {r[0] for r in db.execute("SELECT DISTINCT squadra FROM voti WHERE stagione = ? AND giornata = ?", (stagione, g))}
        if any(not giocata or casa not in con_voti[g] or trasf not in con_voti[g] for casa, trasf, giocata in partite):
            giornate.add(g)
        segnare += dovuti
    return sorted(giornate), segnare


def giro_risultati(adesso: datetime, db, stato: dict, aggiorna: Callable[[list[int]], bool | None]) -> str | None:
    """Un controllo del giro dei risultati. `aggiorna(giornate)` legge risultati e voti (True/False, None = occupato: non conta e
    si riprova). Restituisce "risultati" se ha letto qualcosa, altrimenti None."""
    giornate, segnare = risultati_dovuti(adesso, db, set(stato.get("fatti", [])))
    if not segnare:
        return None
    prima = list(stato.get("fatti", []))
    stato["fatti"] = prima + segnare                             # segnato prima: un errore non deve far ripartire un giro dopo l'altro
    if not giornate:
        return None                                             # già tutto arrivato (per esempio dal cron)
    if aggiorna(giornate) is None:
        stato["fatti"] = prima
        return None
    return "risultati"


def aggiorna_risultati(giornate: list[int], scrivi: Callable[[str], None] = lambda _: None) -> bool | None:
    """Risultati e voti delle giornate indicate (due pagine per giornata) e segna l'aggiornamento (il riscaldamento ricalcola da
    solo). None se l'aggiornamento completo del server sta girando, False se la fonte è spenta o la lettura non è riuscita.
    L'esito va nella riga `CHIAVE_RISULTATI` come un passo seguito (`archivio.segna_passo`, #661): riuscito = ultimo successo;
    non riuscito = errore con il primo fallimento di fila (lo vede «Stato dei dati», non la salute: `archivio.FUORI_SALUTE`) e una riga nel registro."""
    from . import fonti_attive
    from .aggiorna import Aggiornamento, Stagione, _ora
    with blocco_processo() as libero:
        if not libero:
            return None
        db = archivio.apri()
        try:
            if not fonti_attive.acceso("fantacalcio"):
                archivio.passo_saltato(db, CHIAVE_RISULTATI)          # spenta apposta: non è un guasto, l'errore di prima si toglie
                db.commit()
                return False                                        # fonte spenta: niente richieste
            agg = Aggiornamento(db, Stagione.di(date.today()), scrivi)
            for g in giornate:
                agg._passo(f"risultati {g}", lambda g=g: agg.risultati_giornata(g))    # noqa: SLF001 - stesso passo dell'aggiornamento completo
            if agg.errori:
                archivio.segna_passo(db, CHIAVE_RISULTATI, _ora(), "; ".join(agg.errori))   # l'ora dell'ultimo successo resta
                db.commit()
                # nel registro solo il passo e il tipo d'errore («risultati 12: ConnectionError»), mai il resto del messaggio
                LOG.warning("pianificatore: risultati della sera non riusciti (%s)",
                            ", ".join(": ".join(e.split(": ")[:2]) for e in agg.errori))
                return False
            archivio.segna_passo(db, CHIAVE_RISULTATI, _ora())         # cambia la «versione» dei dati: il riscaldamento ricalcola
            db.commit()
            return True
        finally:
            db.close()


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
    """Scarica le probabili e segna l'aggiornamento. True se le probabili sono arrivate,
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
            archivio.segna(db, CHIAVE_ARCHIVIO, _ora())             # cambia la «versione» dei dati: il riscaldamento ricalcola
            db.commit()
        return riuscito
    finally:
        db.close()


def _registro(adesso: datetime, db) -> None:
    """Il registro delle giornate (`registro_giornate.py`, #165): salva i numeri mostrati prima della prima partita, misura le
    giornate finite e avvisa il proprietario. Non alza mai: un suo errore non ferma il pianificatore. `FANTA_REGISTRO_GIORNATE=0`
    lo spegne."""
    try:
        from . import registro_giornate
        if registro_giornate.acceso():
            registro_giornate.giro(adesso, db)
    except Exception as e:  # noqa: BLE001 - il giro dopo riprova; nel registro solo il tipo, mai i dati
        LOG.warning("pianificatore: registro delle giornate non riuscito (%s)", type(e).__name__)


def sorveglia(fermo: threading.Event, leghe: Callable[[], list[Regole]], apri_db: Callable[[], object],
              aggiorna: Callable[[], bool], dopo: Callable[[], object], intervallo: float = INTERVALLO,
              adesso: Callable[[], datetime] = datetime.now,
              risultati: Callable[[list[int]], bool | None] | None = None) -> None:
    """Il thread. `leghe()` dà le regole delle leghe attive; `aggiorna()` scarica le probabili (False se non è riuscito, None se un aggiornamento completo è in corso); `dopo()` ricalcola e manda gli avvisi.
    `risultati(giornate)` legge risultati e voti dopo le partite (giro_risultati); None = niente giro dei risultati.
    Dopo i giri, il registro delle giornate (`_registro`): nessuna richiesta alle fonti, solo l'archivio."""
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
                    try:
                        giro(adesso(), db, leghe(), stato, aggiorna, dopo)
                    finally:
                        if risultati is not None:                # anche se il giro delle probabili è andato in errore
                            giro_risultati(adesso(), db, stato, risultati)
                finally:
                    _registro(adesso(), db)                     # anche se i giri prima sono andati in errore; non alza mai
                    db.close()
                    try:
                        if stato.get("fatti", []) != prima:
                            salva_stato(stato)
                    except Exception as e:  # noqa: BLE001
                        LOG.warning("pianificatore: stato non salvato (%s)", type(e).__name__)
        except Exception as e:  # noqa: BLE001 - il controllo deve continuare anche dopo un errore
            LOG.warning("pianificatore: giro non riuscito (%s)", type(e).__name__)
        fermo.wait(intervallo)
