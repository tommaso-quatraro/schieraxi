"""Risultati in diretta delle partite di Serie A (GET /api/live). Scelta e motivi della fonte: `docs/LIVE.md`.

Un SOLO raccoglitore nel servizio (un thread) interroga la fonte e riempie una cache in memoria condivisa da tutti gli utenti:
- lavora solo nelle finestre di gioco (da 10 minuti prima del calcio d'inizio a 20 minuti dopo la fine stimata) e smette di
  chiedere per le partite già segnate come finite o rinviate (una rinviata che il calendario rimette più avanti si segue di nuovo);
- al massimo UNA richiesta al minuto in totale (qualunque fonte, qualunque numero di utenti o di schede aperte);
- se la fonte sbaglia (anche una risposta senza nessuna delle partite seguite), aspetta sempre di più (fino a 10 minuti) e dopo 3
  errori di fila prova il ripiego (calendario di Fantacalcio.it) per 10 minuti, poi riprova la fonte principale; ogni lettura non
  riuscita lascia una riga nel registro con il nome della fonte;
- le richieste degli utenti leggono solo la cache: nessuna richiesta esterna parte mai da un utente;
- la cache si salva anche su file (`dati/live.json`, formato in `docs/LIVE.md`): un riavvio del servizio dopo la partita non fa
  sparire il risultato finale (1/11/2026: Juventus-Napoli senza punteggio fino al mattino dopo un riavvio alle 23);
- una partita che a fine finestra non è ancora «finita» per la fonte si segue ancora, più piano (ogni 5 minuti), fino a
  TETTO_SEGUI dal calcio d'inizio o finché il calendario non la dà per giocata.
Le funzioni di lettura sono pure (testate su estratti in `tests/dati/`); il tempo e la rete si possono sostituire nei test.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from . import fonti_attive, rete, turno
from . import squadre
from .percorsi import RADICE, scrivi_sicuro

FUSO = ZoneInfo("Europe/Rome")
URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard?dates={}"
UA = rete.UA          # agente onesto: nome, versione e contatto (da novita.json e FANTA_CONTATTO)
FONTE_ESPN, FONTE_RIPIEGO = "espn", "fantacalcio"

PRIMA = timedelta(minutes=10)         # la finestra si apre 10 minuti prima del calcio d'inizio
FINE_STIMATA = timedelta(minutes=110)  # 2 tempi + intervallo + recupero
DOPO = timedelta(minutes=20)          # e si chiude 20 minuti dopo la fine stimata
INTERVALLO = 60.0                     # secondi: mai più di una richiesta al minuto in totale
TETTO_SEGUI = timedelta(hours=4)      # oltre la finestra si segue una partita non ancora «finita» al massimo fino a qui
INTERVALLO_DOPO = 300.0               # ...e con calma: una richiesta ogni 5 minuti
TIENI = timedelta(days=2)             # le partite più vecchie escono dalla cache (e dal file)
VERSIONE_FILE = 1
FILE = RADICE / "dati" / "live.json"  # la cache su file (si rigenera: non va nel backup)
ATTESA_MASSIMA = 600.0
ERRORI_PER_RIPIEGO = 3
DURATA_RIPIEGO = 600.0
MAX_EVENTI = 20                       # per partita
MAX_BYTE = 8000                       # tetto della risposta: oltre, si tolgono prima gli assist, poi i marcatori più vecchi
LOG = logging.getLogger(__name__)

STATI = ("da_giocare", "primo_tempo", "intervallo", "secondo_tempo", "in_corso", "finita", "rinviata", "sospesa")
IN_GIOCO = ("primo_tempo", "intervallo", "secondo_tempo", "in_corso")
CHIUSI = ("finita", "rinviata")
_STATO_ESPN = {
    "STATUS_SCHEDULED": "da_giocare", "STATUS_FIRST_HALF": "primo_tempo", "STATUS_HALFTIME": "intervallo",
    "STATUS_SECOND_HALF": "secondo_tempo", "STATUS_END_PERIOD": "intervallo",
    "STATUS_FULL_TIME": "finita", "STATUS_FINAL": "finita", "STATUS_FINAL_PEN": "finita", "STATUS_FINAL_AET": "finita",
    "STATUS_POSTPONED": "rinviata", "STATUS_CANCELED": "rinviata", "STATUS_CANCELLED": "rinviata",
    "STATUS_DELAYED": "sospesa", "STATUS_SUSPENDED": "sospesa", "STATUS_ABANDONED": "sospesa", "STATUS_RAIN_DELAY": "sospesa",
}


# ---------------------------------------------------------------- tempo
def locale(data_utc: str) -> str | None:
    """'2026-10-25T19:45Z' -> '2026-10-25 20:45' (ora italiana, come le date del calendario)."""
    try:
        d = datetime.fromisoformat(data_utc.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(FUSO).strftime("%Y-%m-%d %H:%M")


def _inizio(data: str) -> datetime | None:
    try:
        return datetime.fromisoformat(data[:16].replace("T", " "))
    except (ValueError, TypeError):
        return None


def in_finestra(data: str, adesso: datetime) -> bool:
    """True se `adesso` (ora italiana, senza fuso) cade fra 10 minuti prima del calcio d'inizio e 20 dopo la fine stimata."""
    i = _inizio(data)
    return i is not None and i - PRIMA <= adesso <= i + FINE_STIMATA + DOPO


def dopo_finestra(data: str, adesso: datetime) -> bool:
    """True se la finestra di gioco è chiusa ma non è passato TETTO_SEGUI dal calcio d'inizio."""
    i = _inizio(data)
    return i is not None and i + FINE_STIMATA + DOPO < adesso <= i + TETTO_SEGUI


def data_per_fonte(data: str) -> str | None:
    """Giorno (UTC, AAAAMMGG) da chiedere alla fonte per una partita con questa data italiana."""
    i = _inizio(data)
    return None if i is None else i.replace(tzinfo=FUSO).astimezone(timezone.utc).strftime("%Y%m%d")


def rimessa_dopo(visto: str | None, data: str | None) -> bool:
    """True se la finestra di gioco della data `data` (calendario) si apre dopo `visto` (l'ultima volta che la fonte ha dato la
    partita): una «rinviata» vista prima di quella finestra non chiude la partita rimessa a questa data (recupero, #661)."""
    i = _inizio(data or "")
    try:
        v = datetime.fromisoformat(str(visto)[:19])
    except (TypeError, ValueError):
        return False
    return i is not None and i - PRIMA > v


def _data16(data) -> str:
    """'2026-11-01T15:00:00' o '2026-11-01 15:00' -> '2026-11-01 15:00' (per confrontare le date della fonte e del calendario)."""
    return str(data or "")[:16].replace("T", " ")


def senza_rinvii_superati(nuove: list[dict], calendario: list[dict]) -> list[dict]:
    """La lettura senza le partite «rinviate» a una data più vecchia di quella del calendario: la fonte tiene il rinvio alla data
    vecchia, ma il calendario ha già rimesso la partita più avanti. Contarle farebbe tornare «rinviata» a ogni lettura (o la terrebbe
    mentre si gioca); così lo stato viene dall'orario della data nuova finché la fonte non dà la partita vera (revisione #700)."""
    nel_calendario = {(p.get("casa"), p.get("trasferta")): _data16(p.get("data")) for p in calendario}
    return [p for p in nuove if not (p["stato"] == "rinviata" and p.get("data")
                                     and _data16(p["data"]) < nel_calendario.get((p["casa"], p["trasferta"]), ""))]


class SenzaPartite(ValueError):
    """La fonte ha risposto, ma nella risposta non c'è nessuna delle partite seguite (forma cambiata o elenco vuoto)."""


# ---------------------------------------------------------------- lettura della fonte principale (ESPN)
def _tipo_evento(d: dict) -> str | None:
    if d.get("ownGoal"):
        return "autogol"
    if d.get("scoringPlay"):
        return "rigore" if d.get("penaltyKick") else "gol"
    if d.get("redCard"):
        return "rosso"                                    # anche la doppia ammonizione: la fonte la dà come cartellino rosso
    if d.get("penaltyKick"):                              # rigore non segnato (parato o fuori) [non verificato dal vivo]
        return "rigore_sbagliato"
    return None                                           # i cartellini gialli non servono e non si tengono


def _chi(d: dict) -> str:
    a = (d.get("athletesInvolved") or [{}])[0]
    return str(a.get("shortName") or a.get("displayName") or "")[:30]


def _assist(d: dict) -> str:
    """Chi ha fatto l'assist, se la fonte lo dà (secondo nome fra i coinvolti di un gol) [non verificato: nei dati provati c'è un solo nome]."""
    altri = d.get("athletesInvolved") or []
    if len(altri) < 2 or not isinstance(altri[1], dict):
        return ""
    return str(altri[1].get("shortName") or altri[1].get("displayName") or "")[:30]


def leggi_espn(corpo: dict, slug_noti: set[str]) -> list[dict]:
    """Le partite del giorno dalla risposta di ESPN, con le nostre squadre (slug di Fantacalcio.it). Le partite con una squadra
    che non si riconosce vengono saltate. Campi: casa, trasferta, data (ora italiana), stato, minuto, gol_casa, gol_trasferta, eventi."""
    risultato = []
    for e in (corpo or {}).get("events") or []:
        try:
            c = e["competitions"][0]
            lati = {k["homeAway"]: k for k in c["competitors"]}
            casa = squadre.slug(lati["home"]["team"]["displayName"], slug_noti)
            trasf = squadre.slug(lati["away"]["team"]["displayName"], slug_noti)
            if not casa or not trasf:
                continue
            tipo = c["status"]["type"]
            stato = _STATO_ESPN.get(tipo.get("name"))
            if stato is None:                                    # stato mai visto: si fida del gruppo generale
                stato = {"pre": "da_giocare", "in": "in_corso", "post": "finita"}.get(tipo.get("state"), "da_giocare")
            gc, gt = int(lati["home"].get("score") or 0), int(lati["away"].get("score") or 0)
            lato_di = {lati["home"]["team"]["id"]: "casa", lati["away"]["team"]["id"]: "trasferta"}
            eventi = []
            for d in c.get("details") or []:
                t = _tipo_evento(d)
                lato = lato_di.get(str((d.get("team") or {}).get("id")))
                if t and lato:
                    ev = {"tipo": t, "minuto": str((d.get("clock") or {}).get("displayValue") or ""), "squadra": lato, "chi": _chi(d)}
                    if t in ("gol", "rigore") and _assist(d):
                        ev["assist"] = _assist(d)                  # campo facoltativo
                    eventi.append(ev)
            _correggi_autogol(eventi, gc, gt)
            minuto = str(c["status"].get("displayClock") or "") if stato in ("primo_tempo", "secondo_tempo", "in_corso") else None
            prima = stato in ("da_giocare", "rinviata")          # niente «0-0» per chi non ha ancora giocato
            risultato.append({"casa": casa, "trasferta": trasf, "data": locale(e.get("date") or c.get("date") or ""), "stato": stato,
                              "minuto": minuto or None, "gol_casa": None if prima else gc, "gol_trasferta": None if prima else gt,
                              "eventi": eventi[:MAX_EVENTI]})
        except (KeyError, IndexError, TypeError, ValueError):
            continue                                              # una partita strana non rovina le altre
    return risultato


def _correggi_autogol(eventi: list[dict], gc: int, gt: int) -> None:
    """Non è sicuro a quale squadra la fonte attribuisca un autogol: si sceglie il lato per cui i conti tornano con il punteggio."""
    auto = [e for e in eventi if e["tipo"] == "autogol"]
    if not auto:
        return
    def conti():
        return (sum(e["squadra"] == "casa" for e in eventi if e["tipo"] in ("gol", "rigore", "autogol")),
                sum(e["squadra"] == "trasferta" for e in eventi if e["tipo"] in ("gol", "rigore", "autogol")))
    if conti() == (gc, gt):
        return
    for e in auto:
        e["squadra"] = "trasferta" if e["squadra"] == "casa" else "casa"
    if conti() != (gc, gt):                                       # nemmeno così: si torna a come lo dà la fonte
        for e in auto:
            e["squadra"] = "trasferta" if e["squadra"] == "casa" else "casa"


# ---------------------------------------------------------------- ripiego: calendario di Fantacalcio.it
def leggi_ripiego(html: str, giornata: int, stagione: str) -> list[dict]:
    """Solo punteggio e stato (da giocare / in corso / finita), senza minuto né marcatori. Lo stato 0 = da giocare e 4 = finita sono
    visti sul sito; qualsiasi altro valore con un punteggio si considera «in corso» (non verificato dal vivo)."""
    from .fonti import fantacalcio as fc
    s = BeautifulSoup(html, "lxml")
    fatte = {p["id"]: p for p in fc.leggi_calendario(html, giornata, stagione)}
    risultato = []
    for pill in s.select("li.match .match-pill"):
        a = pill.select_one("a.match-score")
        href = a.get("href", "") if a else ""
        m = re.search(r"/calendario/(\d+)/([^/]+)/[^/]+/(\d+)", href)
        if not m or int(m.group(1)) != giornata or m.group(2) != stagione:
            continue
        p = fatte.get(int(m.group(3)))
        if p is None:
            continue
        codice = pill.get("data-match-status")
        gc, gt = pill.select_one(".score-home"), pill.select_one(".score-away")
        testo = lambda x: x.get_text(strip=True) if x else ""
        if codice == fc.STATO_FINITA:
            stato = "finita"
        elif codice in (None, "", "0") or not (testo(gc).isdigit() and testo(gt).isdigit()):
            stato = "da_giocare"
        else:
            stato = "in_corso"
        risultato.append({"casa": p["casa"], "trasferta": p["trasferta"], "data": (p["data"] or "")[:16] or None, "stato": stato,
                          "minuto": None, "gol_casa": int(testo(gc)) if stato != "da_giocare" else 0,
                          "gol_trasferta": int(testo(gt)) if stato != "da_giocare" else 0, "eventi": []})
    return risultato


# ---------------------------------------------------------------- la cache condivisa e il raccoglitore
def _scarica_http(url: str) -> str:
    fonti_attive.richiedi("espn")
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"}, timeout=10)
    r.raise_for_status()
    return r.text


class Raccoglitore:
    """Cache + logica di raccolta. `passo()` fa AL PIÙ una richiesta; è il thread di `sorveglia` a chiamarlo ogni pochi secondi.

    calendario() -> elenco di dict {data, casa, trasferta, giornata, stagione} delle partite vicine a oggi (dal database)
    scarica(url) -> testo della risposta (solleva un errore se la rete o la fonte falliscono)
    adesso() -> ora italiana senza fuso; orologio() -> secondi monotoni (per le pause)
    file -> dove salvare la cache (None = solo in memoria): si rilegge alla partenza, si riscrive dopo ogni lettura riuscita
    """

    def __init__(self, calendario, scarica=_scarica_http, adesso=datetime.now, orologio=time.monotonic, file: Path | None = None):
        self.calendario, self.scarica, self.adesso, self.orologio = calendario, scarica, adesso, orologio
        self._blocco = threading.Lock()
        self._partite: dict[tuple[str, str], dict] = {}
        self._visto: dict[tuple[str, str], str] = {}   # quando la fonte ha dato l'ultima volta ogni partita (solo nel file)
        self.aggiornato_il: str | None = None
        self.fonte: str | None = None
        self.errori = 0
        self.prossima = 0.0                       # orologio() prima del quale non si chiede niente
        self.ripiego_fino = 0.0
        self.richieste = 0                        # per i resoconti e i test
        self._giro = 0
        self.file = file
        if file is not None:
            self._carica()

    # ---- il file (la cache sopravvive ai riavvii del servizio)
    def _carica(self) -> None:
        """Rilegge la cache salvata. File mancante, rotto o di forma strana: si parte vuoti, senza errori."""
        try:
            dati = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(dati, dict) or not isinstance(dati.get("partite"), dict):
            return
        limite = (self.adesso() - TIENI).strftime("%Y-%m-%d")
        for p in dati["partite"].values():
            if not (isinstance(p, dict) and isinstance(p.get("casa"), str) and isinstance(p.get("trasferta"), str)
                    and p.get("stato") in STATI and isinstance(p.get("eventi"), list) and (p.get("data") or "9") >= limite):
                continue
            k = (p["casa"], p["trasferta"])
            self._partite[k] = {c: p.get(c) for c in ("casa", "trasferta", "data", "stato", "minuto", "gol_casa", "gol_trasferta")} | {
                "eventi": [e for e in p["eventi"] if isinstance(e, dict)][:MAX_EVENTI]}
            if isinstance(p.get("visto"), str):
                self._visto[k] = p["visto"]
        if self._partite:
            agg = dati.get("aggiornato")
            self.aggiornato_il = agg.replace("T", " ")[:19] if isinstance(agg, str) else None
            self.fonte = dati.get("fonte") if dati.get("fonte") in (FONTE_ESPN, FONTE_RIPIEGO) else None

    def _salva(self) -> None:
        """Scrittura atomica del file (mai a metà). Un errore di disco non ferma la raccolta."""
        if self.file is None:
            return
        with self._blocco:
            dati = {"versione": VERSIONE_FILE, "aggiornato": (self.aggiornato_il or "").replace(" ", "T") or None, "fonte": self.fonte,
                    "partite": {f"{k[0]}|{k[1]}": p | {"visto": self._visto.get(k)} for k, p in self._partite.items()}}
        try:
            scrivi_sicuro(self.file, json.dumps(dati, ensure_ascii=False, separators=(",", ":")))
        except OSError:
            pass

    # ---- lettura (le richieste degli utenti)
    def istantanea(self) -> dict:
        with self._blocco:
            return {"partite": {k: dict(v) for k, v in self._partite.items()}, "aggiornato_il": self.aggiornato_il, "fonte": self.fonte}

    def in_gioco(self) -> bool:
        with self._blocco:
            return any(p["stato"] in IN_GIOCO for p in self._partite.values())

    # ---- raccolta
    def _da_seguire(self, adesso: datetime, calendario: list[dict]) -> list[dict]:
        """Le partite nella finestra di gioco, più quelle con la finestra chiusa che la fonte non ha ancora dato per finite (fino a
        TETTO_SEGUI e solo se il calendario non le dà già per giocate). Mai quelle già finite o rinviate.
        Eccezione (#661): una «rinviata» che il calendario ha rimesso a una data la cui finestra si apre dopo l'ultima volta che la
        fonte l'ha data (`rimessa_dopo`) non è più chiusa; se la data è cambiata la voce vecchia esce dalla cache, così fino alla
        lettura nuova lo stato viene dall'orario della data nuova e non resta «rinviata» con la data vecchia."""
        nel_calendario = {(p.get("casa"), p.get("trasferta")): p for p in calendario}
        with self._blocco:
            chiuse = set()
            for k, v in list(self._partite.items()):
                if v["stato"] not in CHIUSI:
                    continue
                cal = nel_calendario.get(k)
                if v["stato"] == "rinviata" and cal and rimessa_dopo(self._visto.get(k), cal.get("data")):
                    if _data16(v.get("data")) != _data16(cal.get("data")):
                        del self._partite[k]
                        self._visto.pop(k, None)
                    continue
                chiuse.add(k)
        return [p for p in calendario if p.get("data") and (p["casa"], p["trasferta"]) not in chiuse
                and (in_finestra(p["data"], adesso) or (dopo_finestra(p["data"], adesso) and not p.get("giocata")))]

    def passo(self) -> str:
        """'ferma' (niente da seguire), 'attesa' (troppo presto), 'ok' o 'errore'."""
        adesso = self.adesso()
        calendario = self.calendario()
        da_seguire = self._da_seguire(adesso, calendario)
        if not da_seguire:
            return "ferma"
        ora = self.orologio()
        if ora < self.prossima:
            return "attesa"
        solo_dopo = not any(in_finestra(p["data"], adesso) for p in da_seguire)
        normale = INTERVALLO_DOPO if solo_dopo else INTERVALLO
        self.prossima = ora + normale                    # mai due richieste a meno di un minuto (5 minuti dopo la finestra)
        usa_ripiego = ora < self.ripiego_fino
        fonte = FONTE_RIPIEGO if usa_ripiego else FONTE_ESPN
        slug_noti = {p["casa"] for p in calendario} | {p["trasferta"] for p in calendario}
        seguite = {(p["casa"], p["trasferta"]) for p in da_seguire}
        try:
            self.richieste += 1
            if usa_ripiego:
                p0 = da_seguire[0]
                nuove = leggi_ripiego(self.scarica(_url_ripiego(p0["giornata"])), p0["giornata"], p0["stagione"])
            else:
                date = sorted({data_per_fonte(p["data"]) for p in da_seguire} - {None})
                self._giro += 1
                nuove = leggi_espn(json.loads(self.scarica(URL_ESPN.format(date[self._giro % len(date)]))), slug_noti)
            nuove = senza_rinvii_superati(nuove, calendario)
            if not seguite & {(p["casa"], p["trasferta"]) for p in nuove}:
                raise SenzaPartite                       # risposta arrivata ma inutile: è un errore, non una lettura buona (#661)
        except Exception as e:                           # rete, risposta storta, fonte che cambia forma: mai fermare il servizio
            self.errori += 1
            motivo = "nessuna delle partite seguite nella risposta" if isinstance(e, SenzaPartite) else type(e).__name__
            LOG.warning("diretta: lettura di %s non riuscita (%s), %d di fila", fonte, motivo, self.errori)
            # la pausa dopo un errore non è mai più corta di quella normale (dopo la finestra: 5 minuti, anche verso il ripiego)
            self.prossima = ora + max(normale, min(INTERVALLO * 2 ** (self.errori - 1), ATTESA_MASSIMA))
            if not usa_ripiego and self.errori >= ERRORI_PER_RIPIEGO:
                self.ripiego_fino = ora + DURATA_RIPIEGO
                self.prossima = ora + normale
            return "errore"
        self.errori = 0
        self._unisci(nuove, fonte, adesso)
        self._salva()
        return "ok"

    def _unisci(self, nuove: list[dict], fonte: str, adesso: datetime) -> None:
        visto = adesso.strftime("%Y-%m-%dT%H:%M:%S")
        with self._blocco:
            for p in nuove:
                vecchia = self._partite.get((p["casa"], p["trasferta"]))
                if fonte == FONTE_RIPIEGO and vecchia and vecchia["eventi"] and p["stato"] != "finita":
                    p = p | {"eventi": vecchia["eventi"], "minuto": vecchia["minuto"]}      # il ripiego non cancella i marcatori già noti
                self._partite[(p["casa"], p["trasferta"])] = p
                self._visto[(p["casa"], p["trasferta"])] = visto
            limite = (adesso - TIENI).strftime("%Y-%m-%d")
            for k in [k for k, p in self._partite.items() if (p.get("data") or "9") < limite]:
                del self._partite[k]
                self._visto.pop(k, None)
            self.aggiornato_il = adesso.strftime("%Y-%m-%d %H:%M:%S")
            self.fonte = fonte


def _url_ripiego(giornata: int) -> str:
    from .fonti import fantacalcio as fc
    return fc.url_calendario(giornata)


def sorveglia(raccoglitore: Raccoglitore, fermo: threading.Event, pausa: float = 15.0) -> None:
    """Il thread del servizio: ogni 15 secondi guarda se serve una richiesta (e il raccoglitore decide: al massimo una al minuto)."""
    while not fermo.is_set():
        try:
            raccoglitore.passo()
        except Exception:
            pass                                          # il raccoglitore non deve mai far cadere il servizio
        fermo.wait(pausa)


# ---------------------------------------------------------------- la risposta di /api/live
def calendario_da_db(db, adesso: datetime | None = None) -> list[dict]:
    """Le partite di ieri, oggi e domani (basta a coprire le finestre di gioco; recuperi compresi)."""
    adesso = adesso or datetime.now()
    da, a = (adesso - timedelta(days=1)).strftime("%Y-%m-%d"), (adesso + timedelta(days=1)).strftime("%Y-%m-%d 23:59")
    righe = db.execute("SELECT data, casa, trasferta, giornata, stagione, giocata, gol_casa, gol_trasferta FROM partite "
                       "WHERE data >= ? AND data <= ? ORDER BY data", (da, a)).fetchall()
    return [dict(r) for r in righe]


def _ora() -> datetime:
    """Ora italiana senza fuso, come le date del calendario (nei test si ferma)."""
    return datetime.now()


def _da_database(r, adesso: datetime | None = None, inizio_turno: datetime | None = None) -> dict:
    """Una partita del nostro calendario (dove la fonte live non ha ancora detto niente). Se il calendario non la segna ancora giocata
    lo stato viene dall'orario, come per Oggi (fasi.stato_partita): `da_giocare` prima del calcio d'inizio, `in_corso` fino alla fine
    stimata, poi `finita` (senza punteggio finché il calendario non lo scrive). Con `inizio_turno`, fuori dal turno è `rinviata`."""
    finita = bool(r["giocata"])
    data = (r["data"] or "")[:16] or None
    if finita:
        stato = "finita"
    else:
        inizio = _inizio(data) if data else None
        adesso = adesso or _ora()
        if inizio_turno is not None and not turno.della_giornata(inizio, inizio_turno):     # un anticipo non è «rinviata»
            stato = "rinviata"
        elif inizio is None or adesso < inizio:
            stato = "da_giocare"
        else:
            stato = "in_corso" if adesso < inizio + FINE_STIMATA else "finita"
    return {"casa": r["casa"], "trasferta": r["trasferta"], "data": data, "stato": stato, "minuto": None,
            "gol_casa": r["gol_casa"] if finita else None, "gol_trasferta": r["gol_trasferta"] if finita else None, "eventi": []}


def risposta(raccoglitore: Raccoglitore, righe_turno: list) -> dict:
    """Le partite del turno (righe della tabella `partite`) con lo stato live dove c'è, più le partite live fuori turno (recuperi).
    Corpo: {aggiornato_il, fonte, in_corso, partite: [{casa, trasferta, data, stato, minuto, gol_casa, gol_trasferta, eventi}]}."""
    snap = raccoglitore.istantanea()
    viste = dict(snap["partite"])
    # senza diretta lo stato viene dall'orario: quello del raccoglitore (lo stesso orologio della cache) e l'inizio del turno (fuori
    # dal turno = rinviata), come in Oggi
    adesso = raccoglitore.adesso()
    inizio_turno = turno.inizio(_inizio((r["data"] or "")[:16]) if r["data"] else None for r in righe_turno)
    partite = []
    for r in righe_turno:
        k = (r["casa"], r["trasferta"])
        vista = viste.pop(k, None)
        if r["giocata"]:
            # il risultato ufficiale vince (una diretta rimasta ferma su «secondo tempo» non deve restare LIVE); i marcatori
            # visti in diretta restano solo se il punteggio è lo stesso
            p = _da_database(r, adesso, inizio_turno)
            if vista and (vista.get("gol_casa"), vista.get("gol_trasferta")) == (p["gol_casa"], p["gol_trasferta"]):
                p["eventi"] = list(vista.get("eventi") or [])
            partite.append(p)
        else:
            partite.append(vista or _da_database(r, adesso, inizio_turno))
    partite += [p for p in viste.values() if p["stato"] in IN_GIOCO]
    partite.sort(key=lambda p: (p.get("data") or "9", p["casa"]))
    in_corso = sum(p["stato"] in IN_GIOCO for p in partite)
    corpo = {"aggiornato_il": snap["aggiornato_il"], "fonte": snap["fonte"], "in_corso": in_corso, "partite": partite}
    return _stringi(corpo)


def _stringi(corpo: dict) -> dict:
    """Tiene la risposta sotto gli 8 kB: prima via gli assist, poi (caso quasi impossibile) solo gli ultimi eventi di ogni partita."""
    def peso():
        return len(json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode())
    for p in corpo["partite"]:
        p["eventi"] = [e for e in p["eventi"] if e["tipo"] != "giallo"]      # un raccoglitore vecchio o un ripiego non deve far uscire i gialli
    if peso() <= MAX_BYTE:
        return corpo
    for p in corpo["partite"]:
        p["eventi"] = [{k: v for k, v in e.items() if k != "assist"} for e in p["eventi"]]
    if peso() <= MAX_BYTE:
        return corpo
    for p in corpo["partite"]:
        p["eventi"] = p["eventi"][-8:]
    return corpo


# il raccoglitore del servizio (creato all'avvio da server.py; nei test se ne può mettere un altro)
unico: Raccoglitore | None = None
