r"""Fotografie dal vero per l'app iPhone: le risposte del server su una COPIA dei dati veri, in tre momenti della giornata,
con nomi inventati. L'app le legge in modalità demo (`-DEMO_SCENARIO vero-prima`, vedi `ios/Sources/Support/ScenarioVero.swift`)
e il workflow degli screenshot le fotografa: così le foto mostrano i casi veri (rinvii, nomi lunghi, voti a metà, rose da 25,
giocatori senza percentuale, scelta salvata...) invece dei dati demo scritti a mano.

Uso (dalla radice del repository, Windows):
    .venv\Scripts\python.exe prove\fotografie_dal_vero.py --uscita ios\fotografie
    [--dati dati] [--lega lega] [--scenari vero-prima,vero-in-corso,vero-finita]

Cosa fa, per ogni scenario:
1. copia `fanta/`, `dati/` (senza foto) e `lega/` (solo regole e rose) in una cartella temporanea: gli originali NON si toccano.
   Le ROSE della copia si inventano (calciatori a caso dal listone, stesso ruolo, seme fisso) e il diario si rifà su quelle:
   la composizione della lega vera non esce mai. Per le regole usa una copia di quelle del server (`--lega` su una cartella
   con `regole.json` copiato in sola lettura e `rose.json`, di cui contano solo i nomi delle squadre e i posti per ruolo);
2. riporta la copia del database a quel momento (risultati, voti e probabili del futuro tolti; una partita rinviata);
3. avvia il server in un processo a parte, con l'orologio fermo su quel momento e SENZA rete (ogni connessione fallisce),
   chiama le rotte dell'app (come i test: TestClient, nessuna porta aperta) e salva le risposte;
4. sostituisce nomi di squadre, utenti e lega (mappatura privata, come l'esportazione) e dei calciatori (nomi inventati,
   coerenti in ogni forma), poi controlla che non resti nessun nome vero: parole vietate private, cognomi veri, email, indirizzi.
   Se trova qualcosa NON scrive il file e dice dove (senza stampare la parola privata).

Scenari: `vero-prima` (qualche ora prima della scadenza, con una formazione salvata), `vero-in-corso` (giornata a metà: partite
finite con i voti, finite senza voti, in corso, da giocare e una rinviata), `vero-finita` (giornata appena finita).
I momenti si ricavano dal calendario della copia: prossima giornata da giocare e ultima giocata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date as _date_vera, datetime as _datetime_vera, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

RADICE = Path(__file__).resolve().parent.parent
SCENARI = ("vero-prima", "vero-in-corso", "vero-finita")
CARTELLA_PRIVATA = Path(os.environ.get("USERPROFILE") or str(Path.home())) / "Backup-privati"
PAROLE_VIETATE = Path(os.environ.get("SCHIERAXI_NOMI_VIETATI") or CARTELLA_PRIVATA / "parole-vietate.txt")
MAPPATURA = CARTELLA_PRIVATA / "mappatura-privata.txt"
LEGA_FINTA = "Lega delle Fotografie"
DURATA = timedelta(minutes=110)            # come live.FINE_STIMATA e fasi.DURATA_PARTITA
ATTESA_VOTI = timedelta(hours=3)           # i voti escono qualche ora dopo la fine: prima, la partita è «in attesa dei voti»
RINVIO = timedelta(days=24)                # la partita rinviata si gioca settimane dopo (recupero)
CERCA = "ma"                               # il testo che gli screenshot scrivono nella ricerca (-DEMO_CERCA)
FORMATO_DATA = "%Y-%m-%d %H:%M"


# =========================== nomi inventati ===========================
PARTICELLE = {"di", "de", "da", "del", "della", "dal", "van", "von", "der", "den", "dos", "das", "do", "el", "al", "ben", "ter",
              "le", "la", "lo", "mac", "st", "jr", "junior"}
SILLABE = ["ba", "be", "bi", "bo", "ca", "ce", "co", "da", "de", "do", "fa", "fe", "fo", "ga", "go", "la", "le", "li", "lo", "ma",
           "me", "mi", "mo", "na", "ne", "ni", "no", "pa", "pe", "po", "ra", "re", "ri", "ro", "sa", "se", "so", "ta", "te", "ti",
           "to", "va", "ve", "vi", "vo", "za", "zo", "lla", "nni", "rra", "sso", "tto", "ndo", "rti", "lvi", "sca", "stra", "rbo",
           "ghe", "chi", "mbe", "nza"]
# pezzi che un nome inventato non deve contenere: parolacce e parole che in una foto sembrerebbero uno scherzo
SCONCI = ("cess", "cul", "merd", "cazz", "fig", "troi", "putt", "stronz", "minchi", "pirl", "scem", "fess", "coglio", "porc", "suin",
          "vacc", "zoccol", "bastard", "negr", "frocio", "nazi", "mafi", "sesso", "sex", "pene", "tett")
SEPARA = re.compile(r"[^\wÀ-ÿ]+|_")       # i pezzi di un nome: spazi, punti, apostrofi, trattini


def piega(testo: str) -> str:
    """Minuscolo e senza accenti: «Martínez» e «MARTINEZ» sono lo stesso pezzo."""
    return "".join(c for c in unicodedata.normalize("NFKD", testo.lower()) if not unicodedata.combining(c))


def pezzi(nome: str) -> list[str]:
    return [p for p in SEPARA.split(nome or "") if p]


def e_da_cambiare(pezzo: str) -> bool:
    return len(pezzo) >= 3 and piega(pezzo) not in PARTICELLE and not pezzo.isdigit()


class NomiFinti:
    """Ogni pezzo di nome vero (cognome, nome) diventa sempre lo stesso pezzo inventato, di lunghezza simile: «Rossi M.» e
    «Mario Rossi» restano la stessa persona. Un pezzo inventato non è mai un pezzo vero e non ne contiene uno lungo."""

    def __init__(self, veri: set[str], vietate: list[str] = ()):
        self.veri = {piega(p) for p in veri}
        self.vietate = [piega(v) for v in vietate if v.strip()]
        self.lunghi = sorted({v for v in self.veri if len(v) >= 5})
        self.mappa: dict[str, str] = {}
        self.usati: set[str] = set()

    def _accettabile(self, finto: str) -> bool:
        f = piega(finto)
        return (f not in self.veri and f not in self.usati and not any(v in f for v in self.lunghi)
                and not any(v in f for v in self.vietate) and not any(v in f for v in SCONCI))

    def pezzo(self, vero: str) -> str:
        chiave = piega(vero)
        if chiave in self.mappa:
            return self.mappa[chiave]
        for sale in range(500):
            h = hashlib.sha256(f"{chiave}|{sale}".encode()).digest()
            finto, i = "", 0
            while len(finto) < max(3, len(vero) - 1):
                finto += SILLABE[h[i % len(h)] % len(SILLABE)]
                i += 1
            finto = finto[: len(vero) + 1].capitalize()
            if self._accettabile(finto):
                break
        self.mappa[chiave] = finto
        self.usati.add(piega(finto))
        return finto

    def nome(self, vero: str) -> str:
        """Il nome intero, pezzo per pezzo (solo i pezzi di nomi veri), con gli stessi separatori e le stesse maiuscole."""
        def cambia(m: re.Match) -> str:
            p = m.group(0)
            return stile(p, self.pezzo(p)) if e_da_cambiare(p) and piega(p) in self.veri else p
        return re.sub(r"[\wÀ-ÿ]+", cambia, vero or "")


def stile(modello: str, nuovo: str) -> str:
    if modello.isupper() and len(modello) > 1:
        return nuovo.upper()
    if modello.islower():
        return nuovo.lower()
    return nuovo


# =========================== mappatura privata (squadre, persone, lega) ===========================
def leggi_mappatura(testo: str) -> dict[str, str]:
    """`vero => finto`, una coppia per riga, # per i commenti (stesso formato del file usato dall'esportazione pubblica)."""
    coppie: dict[str, str] = {}
    for n, riga in enumerate(testo.splitlines(), 1):
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        if "=>" not in riga:
            raise SystemExit(f"mappatura privata, riga {n}: manca «=>»")
        vero, finto = (x.strip() for x in riga.split("=>", 1))
        if vero and finto:
            coppie[vero] = finto
    return coppie


SEPARATORI = [" ", "%20", "+", "-", "_", ""]      # come si scrive lo spazio di un nome negli indirizzi e negli identificativi


def applica_mappatura(testo: str, coppie: list[tuple[str, str]]) -> str:
    """Ogni nome vero, in ogni forma («Mario Rossi», «Mario%20Rossi», «mario-rossi», «MARIO ROSSI»), diventa il finto
    scritto nello stesso modo."""
    for vero, finto in coppie:
        pv, pf = vero.split(), finto.split()
        if len(pv) > 1:
            forme = [(re.escape(sep).join(re.escape(p) for p in pv), sep.join(pf)) for sep in SEPARATORI]
        else:
            forme = [(re.escape(vero), finto)]
        for schema, nuovo in forme:
            def stesso_stile(m: re.Match, n: str = nuovo) -> str:
                return n.lower() if m.group(0).islower() else n.upper() if m.group(0).isupper() else n
            testo = re.sub(r"(?<![\wÀ-ÿ])" + schema + r"(?![\wÀ-ÿ])", stesso_stile, testo, flags=re.I)
    return testo


def coppie_private(nome_lega: str, squadre: list[str]) -> list[tuple[str, str]]:
    """Le coppie «vero => finto» della mappatura privata (la stessa dell'esportazione), più la lega. Ogni squadra deve averne una."""
    if not MAPPATURA.is_file():
        raise SystemExit(f"Manca la mappatura privata ({MAPPATURA.name} in Backup-privati): senza, i nomi veri resterebbero.")
    coppie = leggi_mappatura(MAPPATURA.read_text(encoding="utf-8"))
    if nome_lega and nome_lega not in coppie:
        coppie[nome_lega] = LEGA_FINTA
    mancano = [s for s in squadre if s not in coppie]
    if mancano:
        raise SystemExit(f"{len(mancano)} squadre senza nome finto nella mappatura privata: aggiungile prima (non le stampo).")
    return sorted(coppie.items(), key=lambda c: -len(c[0]))         # prima i nomi lunghi


# =========================== copia e viaggio nel tempo ===========================
def copia_ambiente(dati: Path, lega: Path, dove: Path) -> None:
    shutil.copytree(RADICE / "fanta", dove / "fanta", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(dati, dove / "dati", ignore=shutil.ignore_patterns("foto", "backup", "*.log", "utenti", "account.sqlite*"))
    (dove / "lega").mkdir()
    for nome in ("regole.json", "rose.json"):
        shutil.copy2(lega / nome, dove / "lega" / nome)
    inventa_rose(dove)


SEME_ROSE = 20261102


def inventa_rose(dove: Path, seme: int = SEME_ROSE) -> None:
    """Le rose della copia diventano INVENTATE: stesse squadre (nomi che poi si sostituiscono) e stessi posti per ruolo, ma ogni
    calciatore è preso a caso dal listone (stesso ruolo, seme fisso, i più quotati più probabili, come in una lega vera), con costi e
    crediti inventati. Così la composizione della lega vera non esce mai: né nelle risposte né nel diario (rifatto dopo)."""
    file_rose = dove / "lega" / "rose.json"
    rose = json.loads(file_rose.read_text(encoding="utf-8"))
    regole = json.loads((dove / "lega" / "regole.json").read_text(encoding="utf-8"))
    crediti = int(regole.get("crediti_iniziali") or 500)
    db = sqlite3.connect(dove / "dati" / "fanta.sqlite")
    listone: dict[str, list[tuple]] = {}
    for i, nome, ruolo, squadra, q in db.execute("SELECT id, nome, ruolo, squadra, quotazione FROM calciatori ORDER BY id"):
        listone.setdefault(ruolo, []).append((i, nome, squadra or "", max(1, int(q or 1))))
    db.close()
    caso = random.Random(seme)
    usati: set[int] = set()
    for s in rose.get("squadre") or []:
        posti = [g.get("ruolo") for g in s.get("giocatori") or []]
        nuovi = []
        for ruolo in posti:
            liberi = [c for c in listone.get(ruolo, []) if c[0] not in usati]
            if not liberi:
                raise SystemExit(f"listone: troppo pochi giocatori nel ruolo {ruolo} per inventare le rose")
            c = caso.choices(liberi, weights=[c[3] ** 1.5 for c in liberi])[0]
            usati.add(c[0])
            nuovi.append(c)
        spesi = caso.randint(crediti - 40, crediti)
        pesi = [c[3] * caso.uniform(0.6, 1.4) for c in nuovi]
        costi = [max(1, round(w * spesi / sum(pesi))) for w in pesi]
        s["giocatori"] = [{"id": c[0], "nome": c[1], "ruolo": r, "squadra": c[2], "costo": costi[k],
                           "riconosciuto": "esatto", "avviso": ""} for k, (c, r) in enumerate(zip(nuovi, posti))]
        s["crediti_residui"] = max(0, crediti - sum(costi))
    file_rose.write_text(json.dumps(rose, ensure_ascii=False, indent=1), encoding="utf-8")


def _d(testo: str) -> _datetime_vera:
    return _datetime_vera.fromisoformat(str(testo)[:16].replace("T", " "))


def momenti(db: sqlite3.Connection) -> dict:
    """I tre momenti dal calendario: la prossima giornata da giocare e l'ultima giocata del tutto."""
    stagione = db.execute("SELECT MAX(stagione) FROM partite").fetchone()[0]
    righe = db.execute("SELECT giornata, data, giocata FROM partite WHERE stagione = ? ORDER BY data", (stagione,)).fetchall()
    per_g: dict[int, list] = {}
    for g, d, giocata in righe:
        per_g.setdefault(g, []).append((d, giocata))
    giocate = [g for g, v in per_g.items() if all(x[1] for x in v)]
    da_giocare = [g for g, v in per_g.items() if not any(x[1] for x in v)]
    if not giocate or not da_giocare:
        raise SystemExit("Il calendario della copia non ha una giornata giocata e una da giocare: aggiorna i dati prima.")
    ultima, prossima = max(giocate), min(da_giocare)
    date_ultima = sorted(_d(d) for d, _ in per_g[ultima] if d)
    inizio_prossima = min(_d(d) for d, _ in per_g[prossima] if d)
    meta = date_ultima[len(date_ultima) // 2]
    return {"stagione": stagione, "ultima": ultima, "prossima": prossima,
            "vero-prima": (prossima, inizio_prossima - timedelta(hours=3, minutes=20)),
            "vero-in-corso": (ultima, meta + timedelta(minutes=72)),            # la partita di metà è al secondo tempo
            "vero-finita": (ultima, max(date_ultima) + DURATA + timedelta(hours=11))}


def viaggia_nel_tempo(cartella: Path, scenario: str) -> dict:
    """Riporta la copia del database al momento dello scenario. Restituisce i dati dello scenario (giornata, adesso, rinviata)."""
    file_db = cartella / "dati" / "fanta.sqlite"
    db = sqlite3.connect(file_db)
    m = momenti(db)
    giornata, adesso = m[scenario]
    stagione = m["stagione"]
    info = {"scenario": scenario, "stagione": stagione, "giornata": giornata, "adesso": adesso.strftime("%Y-%m-%dT%H:%M:%S"),
            "rinviata": None}
    if scenario == "vero-in-corso":
        partite = db.execute("SELECT id, data, casa, trasferta FROM partite WHERE stagione = ? AND giornata = ? ORDER BY data",
                             (stagione, giornata)).fetchall()
        # la rinviata: l'ultima partita del turno, spostata di settimane (recupero) e mai giocata
        pid, data, casa, trasferta = partite[-1]
        nuova = (_d(data) + RINVIO).strftime(FORMATO_DATA)
        db.execute("UPDATE partite SET data = ?, giocata = 0, gol_casa = NULL, gol_trasferta = NULL WHERE id = ?", (nuova, pid))
        db.execute("DELETE FROM voti WHERE stagione = ? AND giornata = ? AND squadra IN (?, ?)", (stagione, giornata, casa, trasferta))
        info["rinviata"] = {"casa": casa, "trasferta": trasferta, "data_prima": data, "data_nuova": nuova}
        # NB: niente rinvio in «vero-finita». Con un recupero in calendario fasi.fine_giornata non chiude mai la giornata e Oggi
        # salta il riepilogo (difetto del server segnalato con le prime fotografie): la foto della fase «finita» non si vedrebbe.
        for pid2, data2, casa2, trasferta2 in partite[:-1]:
            inizio = _d(data2)
            if inizio + DURATA > adesso:                    # in corso o da giocare: niente risultato e niente voti
                db.execute("UPDATE partite SET giocata = 0, gol_casa = NULL, gol_trasferta = NULL WHERE id = ?", (pid2,))
            if inizio + DURATA + ATTESA_VOTI > adesso:      # finita da poco: il risultato c'è, i voti non ancora
                db.execute("DELETE FROM voti WHERE stagione = ? AND giornata = ? AND squadra IN (?, ?)",
                           (stagione, giornata, casa2, trasferta2))
    # niente dal futuro: voti delle giornate dopo, probabili rilevate dopo, statistiche delle partite dopo, aggiornamenti dopo
    db.execute("DELETE FROM voti WHERE stagione = ? AND giornata > ?", (stagione, giornata))
    db.execute("DELETE FROM probabili WHERE rilevato > ?", (adesso.strftime("%Y-%m-%dT%H:%M:%S"),))
    db.execute("DELETE FROM probabili_storia WHERE rilevato > ?", (adesso.strftime("%Y-%m-%dT%H:%M:%S"),))
    utc = (adesso.replace(tzinfo=_fuso()).astimezone(timezone.utc) - DURATA).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("DELETE FROM prestazioni WHERE understat_partita IN (SELECT id FROM partite_understat WHERE data > ?)", (utc,))
    db.execute("UPDATE partite_understat SET giocata = 0 WHERE data > ?", (utc,))
    prima = (adesso - timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%S")
    db.execute("UPDATE aggiornamenti SET quando = ? WHERE quando > ?", (prima, prima))
    db.commit()
    db.close()
    # il diario si rifà da zero sulle rose inventate (dentro il server, con l'orologio fermo): quello vero parla della rosa vera
    (cartella / "dati" / "diario.json").unlink(missing_ok=True)
    for nome in ("scelte.json", "osservati.json"):          # si partono vuote: la scelta salvata e gli osservati li crea lo scenario
        (cartella / "dati" / nome).write_text("{}" if nome == "scelte.json" else "[]", encoding="utf-8")
    return info


def _fuso():
    from zoneinfo import ZoneInfo
    return ZoneInfo("Europe/Rome")


# =========================== dentro il processo del server (copia, orologio fermo, senza rete) ===========================
def spegni_rete() -> None:
    """Ogni connessione verso fuori fallisce (resta solo il giro interno 127.0.0.1 che asyncio usa su Windows)."""
    import socket
    connetti, connetti_ex, risolvi = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo
    interni = ("127.0.0.1", "::1", "localhost")

    def interno(indirizzo) -> bool:
        return isinstance(indirizzo, tuple) and str(indirizzo[0]) in interni

    def connect(self, indirizzo):
        if not interno(indirizzo):
            raise OSError("fotografie dal vero: rete spenta")
        return connetti(self, indirizzo)

    def connect_ex(self, indirizzo):
        if not interno(indirizzo):
            raise OSError("fotografie dal vero: rete spenta")
        return connetti_ex(self, indirizzo)

    def getaddrinfo(host, *a, **k):
        if str(host) not in interni:
            raise OSError("fotografie dal vero: rete spenta")
        return risolvi(host, *a, **k)
    socket.socket.connect = connect            # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex      # type: ignore[method-assign]
    socket.getaddrinfo = getaddrinfo           # type: ignore[assignment]


def ferma_orologio(adesso: _datetime_vera) -> None:
    """Ogni `datetime` e `date` importato dai moduli di `fanta` diventa una copia con `now()`/`today()` fermi su `adesso`."""
    fuso = _fuso()

    class _Meta(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, cls.__mro__[1])

    class DatetimeFermo(_datetime_vera, metaclass=_Meta):
        @classmethod
        def now(cls, tz=None):
            return adesso if tz is None else adesso.replace(tzinfo=fuso).astimezone(tz)

        @classmethod
        def today(cls):
            return adesso

        @classmethod
        def utcnow(cls):
            return adesso.replace(tzinfo=fuso).astimezone(timezone.utc).replace(tzinfo=None)

    class DateFerma(_date_vera, metaclass=_Meta):
        @classmethod
        def today(cls):
            return adesso.date()

    for modulo in _moduli_da_fermare():
        if getattr(modulo, "datetime", None) is _datetime_vera:
            modulo.datetime = DatetimeFermo
        if getattr(modulo, "date", None) is _date_vera:
            modulo.date = DateFerma


def _moduli_da_fermare() -> list:
    """Tutti i moduli di `fanta`, caricati prima: così nessuno sfugge all'orologio fermo."""
    import importlib
    import pkgutil

    import fanta
    for info in pkgutil.walk_packages(fanta.__path__, "fanta."):
        if info.name.endswith("__main__"):
            continue
        try:
            importlib.import_module(info.name)
        except Exception as e:                         # noqa: BLE001 - un modulo che non si carica non serve alle fotografie
            print(f"  (modulo {info.name} non caricato: {type(e).__name__})")
    return [m for n, m in list(sys.modules.items()) if n == "fanta" or n.startswith("fanta.")]


def diretta_finta(db_file: Path, info: dict, adesso: _datetime_vera):
    """La diretta delle partite del turno com'era in quel momento: in corso con un punteggio parziale e i marcatori presi dai
    voti veri (minuti inventati), finite col risultato, la rinviata come «rinviata». Nessuna richiesta a siti esterni."""
    from fanta import live
    db = sqlite3.connect(db_file)
    db.row_factory = sqlite3.Row
    righe = db.execute("SELECT data, casa, trasferta, gol_casa, gol_trasferta FROM partite WHERE stagione = ? AND giornata = ?",
                       (info["stagione"], info["giornata"])).fetchall()
    originale = sqlite3.connect(info["db_originale"])
    originale.row_factory = sqlite3.Row
    nuove = []
    for r in righe:
        inizio = _d(r["data"])
        rinv = info["rinviata"]
        if rinv and (r["casa"], r["trasferta"]) == (rinv["casa"], rinv["trasferta"]):
            nuove.append({"casa": r["casa"], "trasferta": r["trasferta"], "data": rinv["data_prima"][:16], "stato": "rinviata",
                          "minuto": None, "gol_casa": None, "gol_trasferta": None, "eventi": []})
            continue
        if inizio > adesso:
            continue                                            # da giocare: basta il calendario
        finita = adesso >= inizio + DURATA
        minuti = 200 if finita else int((adesso - inizio).total_seconds() // 60)
        minuto_gioco = minuti if minuti <= 45 else max(46, min(90, minuti - 18))
        stato = "finita" if finita else "primo_tempo" if minuti <= 47 else "intervallo" if minuti < 63 else "secondo_tempo"
        eventi = []
        for lato in ("casa", "trasferta"):
            marcatori = originale.execute("SELECT nome, gol FROM voti WHERE stagione = ? AND giornata = ? AND squadra = ? AND gol > 0 "
                                          "ORDER BY calciatore_id", (info["stagione"], info["giornata"], r[lato])).fetchall()
            k = 0
            for m in marcatori:
                for _ in range(int(m["gol"])):
                    k += 1
                    al = min(90, 6 + 19 * k + (9 if lato == "trasferta" else 0))
                    if finita or al <= minuto_gioco:
                        eventi.append({"tipo": "gol", "minuto": f"{al}'", "squadra": lato, "chi": m["nome"]})
        eventi.sort(key=lambda e: int(e["minuto"].rstrip("'")))
        gc = r["gol_casa"] if finita and r["gol_casa"] is not None else sum(e["squadra"] == "casa" for e in eventi)
        gt = r["gol_trasferta"] if finita and r["gol_trasferta"] is not None else sum(e["squadra"] == "trasferta" for e in eventi)
        nuove.append({"casa": r["casa"], "trasferta": r["trasferta"], "data": r["data"][:16], "stato": stato,
                      "minuto": None if stato in ("intervallo", "finita") else f"{minuto_gioco}'", "gol_casa": gc, "gol_trasferta": gt,
                      "eventi": eventi})
    db.close()
    originale.close()
    raccoglitore = live.Raccoglitore(lambda: [], scarica=lambda _u: (_ for _ in ()).throw(OSError("rete spenta")),
                                     adesso=lambda: adesso)
    raccoglitore._unisci(nuove, live.FONTE_ESPN, adesso)
    live.unico = raccoglitore


def fotografa(cartella: Path, info: dict) -> dict:
    """Chiama le rotte dell'app sul server della copia. Restituisce {percorso: {stato, tipo, corpo}} e i dati per la demo."""
    adesso = _datetime_vera.fromisoformat(info["adesso"])
    spegni_rete()
    sys.path.insert(0, str(cartella))
    import fanta
    if Path(fanta.__file__).resolve().parent != (cartella / "fanta").resolve():
        raise SystemExit("il pacchetto fanta non è quello della copia: mi fermo per non toccare i dati veri")
    ferma_orologio(adesso)
    from fastapi.testclient import TestClient
    from fanta import server
    # sempre: anche senza partite iniziate la diretta deve usare l'orologio fermo (il raccoglitore di serie ha quello vero)
    diretta_finta(cartella / "dati" / "fanta.sqlite", info, adesso)
    from fanta import archivio, diario, lega, regole as regole_lega
    db = archivio.apri()
    try:                                                       # il diario delle giornate finite, con le rose inventate
        print(f"  diario: {diario.aggiorna(db, regole_lega.carica(cartella / 'lega' / 'regole.json'), lega.carica(cartella / 'lega' / 'rose.json'))} giornate")
    finally:
        db.close()
    cliente = TestClient(server.app, headers={"X-Fanta": "1"})
    risposte: dict[str, dict] = {}

    def chiedi(percorso: str, metodo: str = "GET", corpo=None, chiave: str | None = None):
        r = cliente.request(metodo, percorso, json=corpo)
        tipo = "json" if "json" in r.headers.get("content-type", "") else "testo"
        valore = r.json() if tipo == "json" else r.text
        if r.status_code >= 400:
            print(f"  {metodo} {percorso}: {r.status_code}")
        risposte[chiave or percorso] = {"stato": r.status_code, "tipo": tipo, "corpo": valore}
        return valore if r.status_code < 400 else None

    stato = chiedi("/api/stato") or {}
    f = chiedi("/api/formazione") or {}
    g = f.get("giornata") or info["giornata"]
    demo: dict = {}
    # scenario «prima»: una formazione salvata (la consigliata con un cambio) e tre giocatori osservati
    if info["scenario"] == "vero-prima" and f.get("titolari"):
        titolari = [t["id"] for t in f["titolari"]]
        panchina = f.get("panchina") or []
        ultimo = f["titolari"][-1]
        cambio = next((p for p in panchina if p.get("ruolo") == ultimo.get("ruolo")), None)
        if cambio:
            titolari[-1] = cambio["id"]
        chiedi("/api/formazione/valuta", "POST", {"titolari": titolari, "salva": True})
    if info["scenario"] == "vero-finita":                    # la giornata appena finita: «ho schierato la consigliata»
        chiedi("/api/diario/schierata", "POST", {"giornata": info["giornata"], "tipo": "consigliata"})
    mercato = chiedi("/api/mercato") or {}
    liberi = chiedi("/api/classifica?limite=60&liberi=true") or {}
    chiedi("/api/classifica?limite=60&liberi=false")
    if info["scenario"] == "vero-prima":
        voci = (liberi.get("giocatori") if isinstance(liberi, dict) else liberi) or []
        for v in voci[:3]:
            cliente.put(f"/api/osservati/{v['id']}")
    # le rotte che l'app chiede di solito (percorsi uguali a quelli dell'app: il server finto risponde per prefisso)
    for p in ("/api/stato-dati", "/api/oggi", "/api/live", "/api/formazione/testo", f"/api/scelta?giornata={g}", "/api/squadre",
              "/api/rosa", "/api/calendario", "/api/osservati", "/api/regole", "/api/avvisi", "/api/diario", "/api/asta",
              "/api/asta?modo=riparazione", "/api/affidabilita", "/api/movimenti?limite=30", "/api/stagione",
              "/api/funzioni", "/api/primo-avvio", "/api/account/me", "/api/widget", "/api/scambi/limite"):
        chiedi(p)
    chiedi("/api/formazione")                                  # di nuovo: dopo la scelta salvata
    squadre = risposte.get("/api/squadre", {}).get("corpo") or []
    nomi_squadre = [s.get("nome") for s in squadre if isinstance(s, dict) and s.get("nome")]
    mia = stato.get("mia_squadra") or (f.get("squadra") if isinstance(f, dict) else None)
    for nome in nomi_squadre:
        chiedi(f"/api/rosa?squadra={quote(nome, safe='')}", chiave=f"ROSA::{nome}")
        if nome != mia:
            chiedi(f"/api/formazione?squadra={quote(nome, safe='')}", chiave=f"FORMAZIONE::{nome}")
    proposte = chiedi("/api/scambi/proposte") or {}
    prima = next(iter((proposte.get("proposte") or []) if isinstance(proposte, dict) else []), None)
    if prima:
        do = ",".join(str(x["id"]) for x in prima.get("do") or [])
        ricevo = ",".join(str(x["id"]) for x in prima.get("ricevo") or [])
        chiedi(f"/api/scambi/analizza?con={quote(prima.get('altra') or '', safe='')}&do={do}&ricevo={ricevo}&completo=true",
               chiave="/api/scambi/analizza")
        if prima.get("do") and prima.get("ricevo"):
            demo["offerta_vera"] = (prima["do"][0].get("nome"), prima["ricevo"][0].get("nome"))
            chiedi("/api/scambi/da-testo", "POST", {"testo": f"Ciao! Ti do {demo['offerta_vera'][0]} e tu mi dai "
                                                             f"{demo['offerta_vera'][1]}, ci stai?"})
    # schede: la mia rosa, gli osservati, i primi svincolati consigliati
    ids = [t["id"] for t in (f.get("titolari") or []) + (f.get("panchina") or []) + (f.get("esclusi") or []) if "id" in t]
    rosa_mia = risposte.get("/api/rosa", {}).get("corpo") or {}
    ids += [x["id"] for x in (rosa_mia.get("giocatori") if isinstance(rosa_mia, dict) else []) or [] if "id" in x]
    oss = risposte.get("/api/osservati", {}).get("corpo") or []
    ids += [x["id"] for x in (oss if isinstance(oss, list) else oss.get("giocatori", [])) if isinstance(x, dict) and "id" in x]
    for blocco in (mercato.get("ruoli") or []) if isinstance(mercato, dict) else []:
        ids += [x["id"] for x in (blocco.get("giocatori") or [])[:2] if "id" in x]
    for i in dict.fromkeys(ids):
        chiedi(f"/api/giocatore/{i}")
    # la scheda da fotografare: un titolare in dubbio se c'è, altrimenti il primo
    tit = f.get("titolari") or []
    dubbio = next((t for t in tit if t.get("in_dubbio") or (t.get("p_voto") or 1) < 0.75), None)
    demo["giocatore"] = (dubbio or (tit[0] if tit else {})).get("id")
    # il confronto: un titolare contro il primo della panchina dello stesso ruolo
    panc = f.get("panchina") or []
    for t in reversed(tit):
        b = next((p for p in panc if p.get("ruolo") == t.get("ruolo")), None)
        if b:
            demo["confronto"] = [t["id"], b["id"]]
            chiedi(f"/api/confronto?a={t['id']}&b={b['id']}", chiave="/api/confronto")
            break
    chiedi("/api/giocatori?q=a&limite=60", chiave="/api/giocatori")
    # foto: solo QUALI giocatori ce l'hanno (l'app ne disegna una finta); le foto vere non escono mai dalla cartella dei dati
    # (solo se questo server ha le foto: nella versione pubblica non ci sono e l'app disegna i volti)
    con_foto = (cartella / "fanta" / "foto.py").is_file()
    demo["foto"] = sorted(int(p.stem) for p in (Path(info["dati_originali"]) / "foto").glob("*.png") if p.stem.isdigit()) if con_foto else []
    demo["mia_squadra"] = mia
    demo["altre_squadre"] = [n for n in nomi_squadre if n != mia]
    return {"risposte": risposte, "demo": demo}


# =========================== nomi veri -> finti, controlli ===========================
def nomi_dei_calciatori(file_db: Path, rose: dict) -> set[str]:
    """Ogni forma dei nomi dei calciatori che il server può scrivere: listone, quotazioni, voti, Understat, rose."""
    db = sqlite3.connect(file_db)
    tutti: set[str] = set()
    for tabella in ("calciatori", "quotazioni", "voti"):
        for (nome,) in db.execute(f"SELECT nome FROM {tabella}"):
            if nome:
                tutti.add(nome)
    for (nome,) in db.execute("SELECT nome FROM understat_giocatori"):
        if nome:
            tutti.add(nome)
    db.close()
    for s in rose.get("squadre") or []:
        for g in s.get("giocatori") or []:
            if g.get("nome"):
                tutti.add(g["nome"])
    return tutti


# Pezzi di nomi veri che sono anche parole italiane o sigle dei testi: SCRITTI IN MINUSCOLO restano (sono «al massimo», «che»,
# lo slug «milan»); con la maiuscola si cambiano lo stesso (meglio una parola strana in una frase che un cognome vero).
# Si aggiungono da sole le squadre di Serie A (slug del calendario) e i pezzi dei nomi finti delle squadre.
PAROLE_ITALIANE = {"che", "giu", "man", "lang", "calo", "caviglia", "massimo", "grandi", "piccoli", "lontani", "rosa", "gol",
                   "pace", "mare", "sole", "conti", "prati", "gatti", "ricci", "leone", "bella", "fine", "forte"}


def parole_ammesse(file_db: Path, coppie) -> set[str]:
    db = sqlite3.connect(file_db)
    club = {piega(c) for (c,) in db.execute("SELECT casa FROM partite UNION SELECT trasferta FROM partite") if c}
    db.close()
    return PAROLE_ITALIANE | club | {piega(p) for _, f in coppie for p in pezzi(f)}


# Campi tolti: i tratti dei volti (`avatar`) vengono dalle foto vere dei calciatori; senza, l'app disegna il volto dal codice.
CAMPI_TOLTI = {"avatar"}


def anonimizza(valore, regola, sostituisci_privati):
    """Ogni testo: prima squadre, persone e lega (mappatura privata), poi i pezzi dei nomi dei calciatori (sempre gli stessi finti)."""
    if isinstance(valore, dict):
        nuovo = {}
        for k, v in valore.items():
            if k in CAMPI_TOLTI:
                continue
            k2 = sostituisci_privati(k) if isinstance(k, str) else k        # le chiavi sono nomi di campi, id e squadre
            nuovo[k2] = anonimizza(v, regola, sostituisci_privati)
        return nuovo
    if isinstance(valore, list):
        return [anonimizza(v, regola, sostituisci_privati) for v in valore]
    if isinstance(valore, str):
        testo = sostituisci_privati(valore)
        return regola(testo)
    return valore


def controlla(testo: str, vietate: list[str], veri: set[str], ammesse: set[str]) -> list[str]:
    """Parole vietate private (anche dentro altre parole), pezzi di nomi veri (parole intere: in minuscolo solo se non sono
    parole italiane ammesse), email e indirizzi di rete. Restituisce l'elenco dei problemi (senza le parole private)."""
    problemi = []
    piegato = piega(testo)
    for n, parola in enumerate(vietate, 1):
        if parola and piega(parola) in piegato:
            problemi.append(f"parola vietata n. {n} del file privato")
    resti = sorted({piega(w) for w in re.findall(r"[\wÀ-ÿ]{3,}", testo)
                    if piega(w) in veri and not (w.islower() and piega(w) in ammesse)})
    if resti:
        problemi.append(f"cognomi veri rimasti: {', '.join(resti[:30])}")
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}", testo):
        problemi.append("un indirizzo email")
    if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|ts\.net|" + "tail" + "scale", testo, re.I):     # a pezzi: il nome di rete non compare intero
        problemi.append("un indirizzo di rete")
    return problemi


def leggi_vietate() -> list[str]:
    if not PAROLE_VIETATE.is_file():
        raise SystemExit("Manca l'elenco privato delle parole vietate: senza, non posso controllare i nomi.")
    return [r.strip() for r in PAROLE_VIETATE.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


def scrivi_scenario(grezzo: dict, info: dict, cartella: Path, uscita: Path, vietate: list[str], scarti: Path | None = None) -> bool:
    rose = json.loads((cartella / "lega" / "rose.json").read_text(encoding="utf-8"))
    regole = json.loads((cartella / "lega" / "regole.json").read_text(encoding="utf-8"))
    coppie = coppie_private(regole.get("nome_lega") or "", [s["nome"] for s in rose.get("squadre") or []])
    tutti = nomi_dei_calciatori(cartella / "dati" / "fanta.sqlite", rose)
    pezzi_veri = {p for n in tutti for p in pezzi(n) if e_da_cambiare(p)}
    finti = NomiFinti(pezzi_veri, vietate)
    for n in sorted(tutti):
        finti.nome(n)                                       # tutti subito: la mappa non dipende dall'ordine delle risposte
    ammesse = parole_ammesse(cartella / "dati" / "fanta.sqlite", coppie)
    da_cambiare = sorted(pezzi_veri, key=len, reverse=True)
    schema = re.compile(r"(?<![\wÀ-ÿ])(" + "|".join(re.escape(p) for p in da_cambiare) + r")(?![\wÀ-ÿ])", re.I) if da_cambiare else None

    def cambia(m: re.Match) -> str:
        w = m.group(0)
        if w.islower() and piega(w) in ammesse:
            return w
        return stile(w, finti.pezzo(w))

    def regola(testo: str) -> str:
        return schema.sub(cambia, testo) if schema else testo

    def privati(testo: str) -> str:
        return applica_mappatura(testo, coppie)

    risposte_finte: dict[str, str] = {}
    for chiave, r in grezzo["risposte"].items():
        if r["stato"] >= 400:
            continue
        corpo = anonimizza(r["corpo"], regola, privati)
        if chiave.startswith(("ROSA::", "FORMAZIONE::")):
            tipo, _, nome = chiave.partition("::")
            nome_finto = privati(nome)
            chiave = ("/api/rosa?squadra=" if tipo == "ROSA" else "/api/formazione?squadra=") + quote(nome_finto, safe="!$'()*,-./:;@_~")
        elif chiave == "/api/giocatori" and isinstance(corpo, list):
            corpo = [x for x in corpo if CERCA in piega(str(x.get("nome", "")))][:25]
        risposte_finte[chiave] = corpo if r["tipo"] == "testo" else json.dumps(corpo, ensure_ascii=False, separators=(",", ":"))
    d = grezzo["demo"]
    demo = {"giocatore": d.get("giocatore"), "confronto": d.get("confronto"), "foto": d.get("foto") or [],
            "cerca": CERCA, "mia_squadra": privati(d.get("mia_squadra") or ""),
            "rosa_altra": privati((d.get("altre_squadre") or [""])[0]),
            "stemmi": [privati(s) for s in [d.get("mia_squadra")] + (d.get("altre_squadre") or []) if s]}
    if d.get("offerta_vera"):
        a, b = (regola(x) for x in d["offerta_vera"])
        demo["offerta"] = f"Ciao! Ti do {a} e tu mi dai {b}, ci stai?"
    risultato = {"scenario": info["scenario"], "adesso": info["adesso"], "giornata": info["giornata"],
                 "nota": "Risposte vere di SchieraXI con nomi inventati (prove/fotografie_dal_vero.py). Solo per le fotografie.",
                 "demo": demo, "risposte": dict(sorted(risposte_finte.items()))}
    testo = json.dumps(risultato, ensure_ascii=False, indent=1)
    problemi = controlla(testo, vietate, {piega(p) for p in pezzi_veri}, ammesse)
    if problemi:
        print(f"  {info['scenario']}: NON scritto. Trovati: " + "; ".join(problemi))
        if scarti:                                          # per capire dove: una cartella PRIVATA, fuori dal repository
            scarti.mkdir(parents=True, exist_ok=True)
            (scarti / f"{info['scenario']}.json").write_text(testo, encoding="utf-8")
        return False
    uscita.mkdir(parents=True, exist_ok=True)
    (uscita / f"{info['scenario']}.json").write_text(testo + "\n", encoding="utf-8", newline="\n")
    print(f"  {info['scenario']}: {len(risposte_finte)} risposte, {len(testo) // 1024} kB, giornata {info['giornata']}, "
          f"adesso {info['adesso']}")
    return True


# =========================== principale ===========================
def principale() -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--uscita", required=True, type=Path, help="cartella dei file degli scenari (per esempio ios/fotografie)")
    a.add_argument("--dati", type=Path, default=RADICE / "dati")
    a.add_argument("--lega", type=Path, default=RADICE / "lega")
    a.add_argument("--scenari", default=",".join(SCENARI))
    a.add_argument("--scarti", type=Path,
                   help="cartella PRIVATA (fuori dal repository) dove lasciare gli scenari che non passano i controlli")
    a.add_argument("--interno", nargs=2, metavar=("CARTELLA", "INFO"), help=argparse.SUPPRESS)
    arg = a.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if arg.interno:                                         # il processo del server, dentro la copia
        cartella, file_info = Path(arg.interno[0]), Path(arg.interno[1])
        info = json.loads(file_info.read_text(encoding="utf-8"))
        risultato = fotografa(cartella, info)
        (cartella / "grezzo.json").write_text(json.dumps(risultato, ensure_ascii=False), encoding="utf-8")
        return 0

    dati, lega = arg.dati.resolve(), arg.lega.resolve()
    if not (dati / "fanta.sqlite").is_file() or not (lega / "rose.json").is_file():
        raise SystemExit("Servono dati/fanta.sqlite e lega/rose.json (le cartelle con i dati veri).")
    uscita = arg.uscita.resolve()
    if dati in uscita.parents or uscita == dati:
        raise SystemExit("La cartella di uscita non può stare dentro i dati veri.")
    vietate = leggi_vietate()
    scenari = [s.strip() for s in arg.scenari.split(",") if s.strip()]
    if any(s not in SCENARI for s in scenari):
        raise SystemExit(f"Scenari possibili: {', '.join(SCENARI)}")
    tutto_bene = True
    for scenario in scenari:
        print(f"{scenario}:")
        with tempfile.TemporaryDirectory(prefix="fotografie-") as tmp:
            cartella = Path(tmp)
            copia_ambiente(dati, lega, cartella)
            info = viaggia_nel_tempo(cartella, scenario)
            info["db_originale"] = str(cartella / "dati" / "originale.sqlite")
            shutil.copy2(dati / "fanta.sqlite", info["db_originale"])          # per i marcatori della diretta (copia, sola lettura)
            info["dati_originali"] = str(dati)
            (cartella / "info.json").write_text(json.dumps(info), encoding="utf-8")
            ambiente = {k: v for k, v in os.environ.items() if not k.startswith("FANTA_")}
            ambiente |= {"PYTHONPATH": str(cartella), "FANTA_PIANIFICATORE": "0", "FANTA_RISCALDA": "0",
                         # tutte le funzioni accese, anche quelle spente di norma: si fotografa ogni schermata
                         "FANTA_PROFILO_FUNZIONI": "completo", "FANTA_FUNZIONE_LIVE": "1", "FANTA_FUNZIONE_ASTA": "1",
                         "FANTA_FUNZIONE_CREDITI": "1", "FANTA_FUNZIONE_CONFRONTO": "1", "FANTA_FUNZIONE_SCAMBI_TROVA": "1",
                         "FANTA_LEGA": str(cartella / "lega"), "PYTHONIOENCODING": "utf-8"}
            esito = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--uscita", str(uscita), "--interno",
                                    str(cartella), str(cartella / "info.json")], cwd=cartella, env=ambiente)
            if esito.returncode != 0:
                print(f"  {scenario}: il server della copia si è fermato con un errore")
                tutto_bene = False
                continue
            grezzo = json.loads((cartella / "grezzo.json").read_text(encoding="utf-8"))
            tutto_bene &= scrivi_scenario(grezzo, info, cartella, uscita, vietate, arg.scarti)
    return 0 if tutto_bene else 1


if __name__ == "__main__":
    sys.exit(principale())
