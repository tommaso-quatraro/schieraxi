"""Lettura delle rose della lega da Excel, CSV o testo copiato da una pagina web.

Non dipende da un formato fisso: cerca nella tabella i nomi dei calciatori (riconosciuti col listone),
poi per ognuno risale fino al nome della fantasquadra. Funziona con:
- l'Excel di Leghe Fantacalcio (squadre affiancate: "nome squadra | costo", poi i 25 giocatori, poi "totale");
- tabelle con colonne ruolo / calciatore / squadra / costo;
- testo incollato, con le colonne separate da tabulazioni o con un valore per riga.
Quello che non è sicuro finisce negli avvisi, non viene indovinato in silenzio.
I fogli che non sono rose (listone, calendario, classifica nello stesso Excel) si riconoscono e si saltano (`_foglio_non_rosa`);
se ci sono solo quelli, il messaggio d'errore dice quali.
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .frasi import F
from .nomi import Esito, Indice, normalizza
from .regole import RUOLI

# parole che compaiono nelle intestazioni di colonna: una cella fatta solo di queste parole è un'intestazione
PAROLE_INTESTAZIONE = {
    "ruolo", "r", "calciatore", "calciatori", "giocatore", "giocatori", "nome", "cognome", "squadra", "sq",
    "club", "serie", "a", "costo", "prezzo", "acquisto", "pagato", "crediti", "totale", "spesa", "spesi",
    "quotazione", "quot", "qt", "qa", "qi", "fvm", "attuale", "iniziale", "rosa", "fantasquadra", "n", "num",
    "mv", "fm", "pv", "media", "voto", "fantamedia", "presenze", "di", "del", "della", "in",
}
PAROLE_COSTO = {"costo", "prezzo", "acquisto", "pagato", "spesa"}
# righe di contorno sotto il nome della squadra, copiate dalla pagina delle rose (es. «Allenatore: Marco»): non sono una squadra
ETICHETTA_PERSONA = re.compile(r"^\s*(allenatore|fantallenatore|presidente|proprietario|manager|coach|mister)\s*[:\-–]", re.IGNORECASE)
SIGLE_RUOLO = {"p": "P", "por": "P", "portiere": "P", "portieri": "P",
               "d": "D", "dif": "D", "difensore": "D", "difensori": "D",
               "c": "C", "cen": "C", "centrocampista": "C", "centrocampisti": "C",
               "a": "A", "att": "A", "attaccante": "A", "attaccanti": "A"}
FOGLI_ANONIMI = {"sheet1", "foglio1", "foglio 1", "rose", "testo", "csv"}


@dataclass
class RigaRosa:
    testo: str                      # il nome come scritto nel file
    esito: Esito
    ruolo: str | None = None        # dal file (colonna ruolo o posizione nel blocco)
    squadra: str | None = None      # squadra di Serie A scritta nel file
    costo: int | None = None


@dataclass
class SquadraLetta:
    nome: str
    righe: list[RigaRosa] = field(default_factory=list)
    crediti_residui: int | None = None
    totale_speso: int | None = None


# ---------- lettura del file in una griglia di celle ----------
def _testo(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def griglia_da_testo(testo: str) -> list[list[str]]:
    """Le celle di un testo incollato. Ogni cella si accorcia a MAX_TESTO_CELLA caratteri, come nel CSV e nell'Excel."""
    righe = testo.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if any("\t" in r for r in righe):
        return [[c.strip()[:MAX_TESTO_CELLA] for c in r.split("\t")] for r in righe]
    if any(";" in r for r in righe):
        return [[c.strip()[:MAX_TESTO_CELLA] for c in r.split(";")] for r in righe]
    d = _delimitatore(testo)                       # CSV con la virgola (o la barra verticale), anche con le virgolette
    if d:
        return _righe_csv(testo, d)
    return [[c.strip()[:MAX_TESTO_CELLA] for c in re.split(r"\s{2,}", r.strip())] for r in righe]


MAX_FOGLI, MAX_RIGHE, MAX_COLONNE, MAX_TESTO_CELLA = 10, 1500, 60, 200      # un Excel normale delle rose sta largamente dentro

# intero, senza tagli: il server manda al massimo 500 caratteri (tests/test_rose_fogli_non_rose.py)
NESSUNA_ROSA = ("Non ho trovato rose nel file. Leggo l'esportazione «rosters» di Leghe (righe come «Real Esempio,7627,12», "
                "con «$,$,$» tra una squadra e l'altra) oppure un Excel, un CSV o un testo con il nome di ogni squadra "
                "e sotto i suoi calciatori (come «P;Sommer;10»).")


# ---------- CSV e testo caricati: codifica e separatori ----------
def decodifica(dati: bytes) -> str:
    """Il testo di un file CSV/TSV/TXT, qualunque codifica abbia: BOM UTF-8, UTF-16 e UTF-32 (con o senza BOM), poi UTF-8,
    poi Windows-1252 (Excel italiano) e come ultima scelta Latin-1: gli accenti dei nomi restano giusti. Alza ValueError
    (con un messaggio da mostrare) se il file non è testo."""
    if dati.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValueError("Questo è un vecchio file Excel (.xls): aprilo, salvalo come «Cartella di lavoro Excel (.xlsx)» "
                         "oppure come CSV, e riprova.")
    if dati.startswith((b"%PDF", b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"{\\rtf")):
        raise ValueError("Questo file non contiene una tabella di rose (è un PDF, un'immagine o un documento): "
                         "esporta le rose in Excel (.xlsx) o in CSV e riprova.")
    if dati.startswith(b"\xef\xbb\xbf"):
        testo = dati[3:].decode("utf-8", errors="replace")
    elif dati.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        testo = dati.decode("utf-32", errors="replace")
    elif dati.startswith((b"\xff\xfe", b"\xfe\xff")):
        testo = dati.decode("utf-16", errors="replace")
    elif b"\x00" in dati[:4000]:                    # UTF-16 senza BOM: i caratteri latini hanno un byte a zero ogni due
        testa = dati[:4000]
        zeri_dispari, zeri_pari = testa[1::2].count(0), testa[0::2].count(0)
        meta = len(testa) // 2 * 0.3
        if zeri_dispari > meta and zeri_dispari > zeri_pari:
            testo = dati.decode("utf-16-le", errors="replace")
        elif zeri_pari > meta:
            testo = dati.decode("utf-16-be", errors="replace")
        else:
            raise ValueError("Il file non sembra testo né Excel: esporta le rose come .xlsx oppure come CSV (UTF-8) e riprova.")
    else:
        try:
            testo = dati.decode("utf-8")
        except UnicodeDecodeError:
            try:
                testo = dati.decode("cp1252")
            except UnicodeDecodeError:              # cp1252 lascia cinque byte vuoti: latin-1 li legge tutti
                testo = dati.decode("latin-1")
    if "\x00" in testo:
        raise ValueError("Il file non sembra testo né Excel: esporta le rose come .xlsx oppure come CSV (UTF-8) e riprova.")
    return testo.lstrip("﻿")


def _righe_csv(testo: str, delimitatore: str) -> list[list[str]]:
    """Le celle di un CSV (virgolette e a capo dentro le celle compresi). Righe vuote e spazi attorno alle celle restano come sono."""
    try:
        return [[c.replace("﻿", "").strip()[:MAX_TESTO_CELLA] for c in r]
                for r in csv.reader(io.StringIO(testo, newline=""), delimiter=delimitatore)]
    except csv.Error:
        raise ValueError("Il CSV non è leggibile: ci sono virgolette aperte e mai chiuse oppure una cella enorme. "
                         "Riesportalo da Excel come «CSV UTF-8».") from None


def _separatore_rosters(testo: str) -> str | None:
    """Il separatore scritto nella riga «$,$,$» dell'esportazione «rosters» (anche «$;$;$», «$|$|$», «$<tab>$<tab>$»), con
    spazi e tabulazioni attorno. Conta la prima riga che comincia con «$», un separatore e un altro «$»; il resto della riga
    non importa. Si guarda una riga alla volta, con le funzioni delle stringhe."""
    for riga in testo[:60000].split("\n"):
        riga = riga.lstrip(" \t")
        if not riga.startswith("$"):
            continue
        dopo = riga[1:]
        resto = dopo.lstrip(" \t")                   # quello che c'è dopo gli spazi e le tabulazioni che seguono il «$»
        if resto[:1] in (",", ";", "|") and resto[1:].lstrip(" \t").startswith("$"):
            return resto[0]
        if resto.startswith("$") and "\t" in dopo[:len(dopo) - len(resto)]:      # «$<tab>$»: la tabulazione è il separatore
            return "\t"
    return None


def _delimitatore(testo: str) -> str | None:
    """Il separatore di colonne di un CSV: quello che dà righe con lo stesso numero di colonne (almeno due).
    None se il testo è a una colonna sola (una squadra per blocco) o non è tabellare."""
    separatore = _separatore_rosters(testo)
    if separatore:                                   # esportazione «rosters»: la riga «$,$,$» dice il separatore
        return separatore
    migliore, punteggio = None, 0
    for d in ("\t", ";", ",", "|"):
        if d not in testo:
            continue
        try:
            righe = [r for r in csv.reader(io.StringIO(testo[:60000], newline=""), delimiter=d) if any(c.strip() for c in r)]
        except csv.Error:
            continue
        tabellari = [len(r) for r in righe if len(r) >= 2]
        if not righe or len(tabellari) / len(righe) < 0.5:
            continue
        lunghezza, quante = Counter(tabellari).most_common(1)[0]
        regolari = quante / len(tabellari) >= 0.7 or len(tabellari) / len(righe) >= 0.9     # «rosters»: 3 o 4 colonne
        if regolari and quante > punteggio:
            migliore, punteggio = d, quante
    return migliore


def griglie_da_bytes(dati: bytes) -> list[tuple[str, list[list[str]]]]:
    """Le celle di un file di testo (CSV, TSV, TXT, senza estensione...) già caricato in memoria."""
    return griglie_da_stringa(decodifica(dati))


def griglie_da_stringa(testo: str) -> list[tuple[str, list[list[str]]]]:
    """Le celle di un testo già decodificato: CSV con il suo separatore, oppure testo a colonne di spazi / una colonna sola."""
    d = _delimitatore(testo)
    if d:
        return [("csv", _righe_csv(testo, d))]
    return [("testo", griglia_da_testo(testo))]


def leggi_griglie(percorso: Path) -> list[tuple[str, list[list[str]]]]:
    """Restituisce [(nome foglio, griglia)] per Excel, CSV o testo. Excel con fogli enormi: si leggono solo i primi
    MAX_FOGLI fogli, MAX_RIGHE righe e MAX_COLONNE colonne (un file con dimensioni dichiarate gigantesche esaurirebbe la memoria del server)."""
    est = percorso.suffix.lower()
    if est in (".xlsx", ".xlsm"):
        import zipfile

        import openpyxl
        try:
            wb = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
        except (zipfile.BadZipFile, KeyError, OSError, ValueError):
            raise ValueError("File Excel non leggibile: è rovinato o protetto da password") from None
        try:
            return [(ws.title, [[_testo(v)[:MAX_TESTO_CELLA] for v in r]
                                for r in ws.iter_rows(max_row=MAX_RIGHE, max_col=MAX_COLONNE, values_only=True)])
                    for ws in wb.worksheets[:MAX_FOGLI]]
        finally:
            wb.close()
    return griglie_da_bytes(percorso.read_bytes())


# ---------- riconoscimento delle celle ----------
def _e_intestazione(n: str) -> bool:
    parole = n.split()
    return not parole or all(p in PAROLE_INTESTAZIONE for p in parole)


class _Celle:
    """Classifica ogni cella: vuoto, numero, ruolo, intestazione, crediti, squadra_a, giocatore, testo."""

    def __init__(self, griglia: list[list], indice: Indice):
        larghezza = max((len(r) for r in griglia), default=0)
        self.g = [[_testo(v) for v in r] + [""] * (larghezza - len(r)) for r in griglia]
        self.larghezza = larghezza
        self.indice = indice
        self.esiti: dict[tuple[int, int], Esito] = {}
        self.tipo: dict[tuple[int, int], str] = {}
        for r, riga in enumerate(self.g):
            for c, v in enumerate(riga):
                self.tipo[r, c] = self._classifica(r, c, v)

    def _classifica(self, r: int, c: int, v: str) -> str:
        if not v:
            return "vuoto"
        if re.fullmatch(r"-?\d+([.,]\d+)?", v):
            return "numero"
        n = normalizza(v)
        if n.startswith(("crediti", "totale", "spesa", "spesi")):
            return "crediti"
        if ETICHETTA_PERSONA.match(v):
            return "intestazione"
        if n in SIGLE_RUOLO:
            return "ruolo"
        if not re.search(r"[a-z]", n) or _e_intestazione(n):
            return "intestazione"
        if self.indice.e_squadra_serie_a(v):
            return "squadra_a"
        esito = self.indice.cerca(v)
        self.esiti[r, c] = esito              # per un testo: i nomi somiglianti, se poi si rivela un giocatore non riconosciuto
        return "giocatore" if esito.metodo != "non trovato" else "testo"

    def blocchi(self) -> list[tuple[int, int]]:
        """Gruppi di colonne separati da colonne del tutto vuote (es. le squadre affiancate)."""
        piene = [any(self.tipo[r, c] != "vuoto" for r in range(len(self.g))) for c in range(self.larghezza)]
        blocchi, inizio = [], None
        for c, piena in enumerate(piene + [False]):
            if piena and inizio is None:
                inizio = c
            elif not piena and inizio is not None:
                blocchi.append((inizio, c - 1))
                inizio = None
        return blocchi


def _primo(celle: _Celle, r: int, colonne, tipo: str) -> str | None:
    for c in colonne:
        if 0 <= c < celle.larghezza and celle.tipo[r, c] == tipo:
            return celle.g[r][c]
    return None


def _da_un_valore_per_riga(griglia: list[list], indice: Indice) -> list[list[str]]:
    """Testo con un valore per riga (es. copiato da una pagina a schede): ricompone le righe dei giocatori."""
    celle = _Celle([[r[0] if r else ""] for r in griglia], indice)
    nuove: list[list[str]] = []
    ruolo_in_attesa = ""
    corrente: list[str] | None = None
    for r, riga in enumerate(celle.g):
        tipo, v = celle.tipo[r, 0], riga[0]
        if tipo == "ruolo":
            ruolo_in_attesa = v
        elif tipo == "giocatore" or (tipo == "testo" and ruolo_in_attesa):
            # un testo subito dopo un ruolo è un giocatore non riconosciuto, non una nuova squadra
            corrente = [ruolo_in_attesa, v, "", ""]
            nuove.append(corrente)
            ruolo_in_attesa = ""
        elif tipo == "squadra_a" and corrente is not None:
            corrente[2] = v
        elif tipo == "numero" and corrente is not None and not corrente[3]:
            corrente[3] = v
        elif tipo == "testo":
            nuove.append([v])
            corrente = None
        elif tipo == "crediti":
            nuove.append(["", "", "", "", v])
            corrente = None
    return nuove


# ---------- estrazione ----------
def estrai(griglie: list[tuple[str, list[list]]], indice: Indice,
           rosa: dict[str, int] | None = None, avvisi: list[str] | None = None) -> list[SquadraLetta]:
    """Trova le fantasquadre e i loro giocatori.

    `rosa` (es. {"P": 3, ...}) serve a dedurre il ruolo dalla posizione quando il file non ha la colonna ruolo.
    In `avvisi`, se passato, finiscono le cose da controllare a mano.
    """
    avvisi = avvisi if avvisi is not None else []
    squadre: dict[str, SquadraLetta] = {}
    da_codici: set[str] = set()          # squadre lette dall'esportazione «rosters» (già abbinate per codice)
    saltati: list[tuple[str, str]] = []  # (nome del foglio, che cosa è): listone, calendario, classifica
    fogli = 0
    for nome_foglio, griglia in griglie:
        fogli += 1
        if _e_schermate(griglia):        # già cercate con ruolo e squadra: niente secondo giro qui sotto
            da_codici |= _estrai_schermate(griglia, indice, squadre, avvisi)
            continue
        if _e_rosters(griglia, indice):
            da_codici |= _estrai_rosters(griglia, indice, squadre, avvisi)
            continue
        piene = [r for r in griglia if any(_testo(x) for x in r)]
        if piene and sum(1 for r in piene if sum(1 for x in r if _testo(x)) == 1) / len(piene) > 0.8:
            griglia = _da_un_valore_per_riga(griglia, indice)
        celle = _Celle(griglia, indice)
        lette: dict[str, SquadraLetta] = {}
        avvisi_foglio: list[str] = []
        for c0, c1 in celle.blocchi():
            _estrai_blocco(celle, c0, c1, nome_foglio, lette, avvisi_foglio)
        tipo = _foglio_non_rosa(celle, lette)
        if tipo:                         # listone, calendario o classifica dello stesso Excel: si salta, senza avvisi
            saltati.append((nome_foglio, tipo))
            continue
        avvisi += avvisi_foglio
        _unisci(squadre, lette)
    elenco = [s for s in squadre.values() if s.righe]   # un titolo sopra le rose non è una squadra
    if not elenco and saltati:           # solo fogli saltati: si dice quali, non il generico NESSUNA_ROSA
        messaggio = _solo_fogli_saltati(saltati, fogli)
        raise ValueError(messaggio)
    for s in elenco:
        if s.nome in da_codici:
            continue
        if rosa:
            _ruoli_da_posizione(s, rosa)
        for riga in s.righe:  # con ruolo e squadra noti si sciolgono gli omonimi e si scoprono le discordanze
            if riga.esito.metodo != "non trovato" and (riga.ruolo or riga.squadra):
                riga.esito = indice.cerca(riga.testo, riga.squadra, riga.ruolo)
    togli_doppioni(elenco, avvisi)
    return elenco


# ---------- fogli dello stesso Excel che non sono rose (#543) ----------
SOGLIA_LISTONE = 60          # giocatori per squadra, in media: più di qualunque rosa (con gli account al massimo 40)
QUOTA_GIOCATORI = 0.25       # sotto questa quota di nomi del listone, i nomi del foglio sono di fantasquadre
# parole delle intestazioni che solo una rosa ha: un foglio con una di queste non è mai un calendario né una classifica
INTESTAZIONE_ROSA = {"calciatore", "calciatori", "giocatore", "giocatori", "crediti"} | PAROLE_COSTO
# che cosa sembra un file senza fogli (CSV o testo incollato): queste parole le traduce l'app (chiavi err.p_*)
SEMBRA = {"listone": "un listone", "calendario": "un calendario", "classifica": "una classifica"}
FOGLI_DI_TESTO = {"csv", "testo"}       # i nomi che griglie_da_stringa e le rotte del testo danno all'unica griglia


def _foglio_non_rosa(celle: _Celle, lette: dict[str, SquadraLetta]) -> str | None:
    """«listone», «calendario» o «classifica» per i fogli che l'esportazione della lega mette accanto alle rose (`lette`: le
    squadre trovate nel foglio), None per gli altri:
    - listone (o statistiche, svincolati): in media più di SOGLIA_LISTONE giocatori per squadra, cioè centinaia di nomi
      senza i nomi delle squadre in mezzo;
    - calendario: almeno due righe con la parola «giornata» e quasi nessun nome del listone (sono coppie di fantasquadre);
    - classifica: almeno 3 righe, e almeno metà del foglio, fatte di un nome e di due o più numeri, senza ruolo né squadra
      di Serie A, e quasi nessun nome del listone.
    Una rosa ha il ruolo o la squadra accanto ai nomi, nomi che il listone conosce o un'intestazione da rosa (calciatore,
    costo, prezzo, crediti...): resta una rosa."""
    con_righe = [s for s in lette.values() if s.righe]
    if con_righe and sum(len(s.righe) for s in con_righe) / len(con_righe) > SOGLIA_LISTONE:
        return "listone"
    righe = [(r, [celle.tipo[r, c] for c in range(celle.larghezza)]) for r in range(len(celle.g))]
    righe = [(r, tipi) for r, tipi in righe if any(t != "vuoto" for t in tipi)]
    giocatori = sum(tipi.count("giocatore") for _, tipi in righe)
    nomi = giocatori + sum(tipi.count("testo") for _, tipi in righe)
    if not nomi or giocatori / nomi >= QUOTA_GIOCATORI:
        return None
    if any(celle.tipo[r, c] in ("intestazione", "crediti") and set(normalizza(v).split()) & INTESTAZIONE_ROSA
           for r, _ in righe for c, v in enumerate(celle.g[r])):
        return None
    if sum(any("giornata" in normalizza(v).split() for v in celle.g[r]) for r, _ in righe) >= 2:
        return "calendario"
    classifica = sum(1 for _, t in righe if t.count("testo") + t.count("giocatore") == 1 and t.count("numero") >= 2
                     and "ruolo" not in t and "squadra_a" not in t)
    return "classifica" if classifica >= 3 and 2 * classifica >= len(righe) else None


def _solo_fogli_saltati(saltati: list[tuple[str, str]], fogli: int) -> str:
    """Il messaggio per un file in cui ci sono solo fogli saltati. Un CSV o un testo (una griglia sola, senza nome di foglio):
    che cosa sembra. Un Excel: i nomi dei fogli saltati (al massimo MAX_FOGLI, ognuno di al massimo 31 caratteri come in Excel),
    così il messaggio sta sempre intero nei 500 caratteri che il server manda."""
    if fogli == 1 and saltati[0][0] in FOGLI_DI_TESTO:
        return f"Il file sembra {SEMBRA[saltati[0][1]]}, non le rose: carica il file delle rose esportato dalla lega."
    nomi = ", ".join(f"«{nome[:31]}»" for nome, _ in saltati[:MAX_FOGLI])
    return (f"Nel file non ho trovato rose. Ho saltato i fogli che sono listone, calendario o classifica: {nomi}. "
            "Carica il file delle rose esportato dalla lega.")


def _unisci(squadre: dict[str, SquadraLetta], lette: dict[str, SquadraLetta]) -> None:
    """Le squadre di un foglio con quelle dei fogli prima: lo stesso nome è la stessa squadra (righe in coda; crediti e spesa
    dall'ultimo foglio che li scrive)."""
    for nome, s in lette.items():
        gia = squadre.setdefault(nome, s)
        if gia is s:
            continue
        gia.righe += s.righe
        if s.crediti_residui is not None:
            gia.crediti_residui = s.crediti_residui
        if s.totale_speso is not None:
            gia.totale_speso = s.totale_speso


def togli_doppioni(squadre: list[SquadraLetta], avvisi: list[str]) -> None:
    """Lo stesso giocatore due volte nella stessa rosa (riga incollata due volte, o un dubbio sciolto su chi c'era già): resta la
    prima riga e lo si dice negli avvisi. Senza, la rosa salvata avrebbe un giocatore in più e i conti di formazione e scambi
    non tornerebbero. Vale anche dopo le correzioni dell'utente."""
    for s in squadre:
        visti: set[int] = set()
        tenute = []
        for riga in s.righe:
            c = riga.esito.calciatore
            if c is not None and c.id in visti:
                avvisi.append(F("rose.nome_doppio", squadra=s.nome, nome=c.nome))
                continue
            if c is not None:
                visti.add(c.id)
            tenute.append(riga)
        s.righe = tenute


# ---------- esportazione «rosters» di Leghe: Nome squadra,codice calciatore,costo ----------
def _senza_vuote_finali(riga: list) -> list[str]:
    celle = [_testo(c) for c in riga]
    while celle and not celle[-1]:
        celle.pop()
    return celle


def _e_separatore(riga: list[str]) -> bool:
    return len(riga) >= 2 and all(c == "$" for c in riga)


def _riga_rosters(riga: list[str]) -> tuple[str, int, int] | None:
    """(nome squadra, codice, costo) se la riga è «nome,codice,costo». Si legge da destra: le ultime due celle sono numeri e
    il resto è il nome (che può contenere una virgola: «Under Prova»)."""
    if len(riga) < 3 or not (re.fullmatch(r"\d{1,9}", riga[-1]) and re.fullmatch(r"\d{1,9}", riga[-2])):
        return None
    nome = ",".join(riga[:-2]).strip()
    if not nome or nome == "$" or re.fullmatch(r"\d+", nome):
        return None
    return nome, int(riga[-2]), int(riga[-1])


def _e_rosters(griglia: list[list], indice: Indice) -> bool:
    """Firma del formato: righe «$,$,$» tra le squadre, oppure (senza separatori) quasi tutte le righe sono «nome,codice,costo»
    e i codici sono davvero nel listone."""
    piene = [r for r in (_senza_vuote_finali(r) for r in griglia) if r]
    dati = [d for d in (_riga_rosters(r) for r in piene) if d]
    if not dati:
        return False
    if any(_e_separatore(r) for r in piene):
        return True
    ids = {c.id for c in indice.calciatori}
    return len(dati) >= 5 and len(dati) / len(piene) >= 0.9 and sum(d[1] in ids for d in dati) / len(dati) >= 0.5


def _estrai_rosters(griglia: list[list], indice: Indice, squadre: dict[str, SquadraLetta], avvisi: list[str]) -> set[str]:
    """Una riga per giocatore: ruolo, nome e squadra di Serie A vengono dal listone (il codice è lo stesso di Fantacalcio.it), il
    costo dal file. Un codice che non è nel listone resta in rosa come «non riconosciuto» e finisce negli avvisi."""
    per_id = {c.id: c for c in indice.calciatori}
    toccate: set[str] = set()
    visti_dati = False
    for numero, riga in enumerate(griglia, 1):
        celle = _senza_vuote_finali(riga)
        if not celle or _e_separatore(celle):
            continue
        d = _riga_rosters(celle)
        if d is None:
            if not visti_dati and all(not re.search(r"\d", c) for c in celle):       # intestazione sopra i dati
                continue
            avvisi.append(F("rose.riga_ignorata", riga=numero, celle=", ".join(celle)[:60]))
            continue
        visti_dati = True
        nome, codice, costo = d
        s = squadre.setdefault(nome, SquadraLetta(nome))
        toccate.add(nome)
        c = per_id.get(codice)
        if c is None:
            avvisi.append(F("rose.codice_sconosciuto", squadra=nome, codice=codice))
            s.righe.append(RigaRosa(f"Codice {codice}", Esito(None, "non trovato", avviso=F("rose.codice_assente", codice=codice)),
                                    costo=_intero(str(costo))))
        elif any(x.esito.calciatore is c for x in s.righe):
            avvisi.append(F("rose.codice_doppio", squadra=nome, nome=c.nome, codice=codice))
        else:
            s.righe.append(RigaRosa(c.nome, Esito(c, "esatto"), ruolo=c.ruolo, squadra=c.squadra, costo=_intero(str(costo))))
    return toccate


# ---------- testo dalle schermate di Leghe (OCR dell'app per iPhone): «ruolo;nome;club;prezzo» ----------
INTESTAZIONE_SCHERMATE = (("ruolo",), ("nome",), ("club", "squadra"), ("prezzo", "costo"))


def _e_schermate(griglia: list[list]) -> bool:
    """Firma del formato: la prima riga piena è l'intestazione «ruolo;nome;club;prezzo» (il prezzo può mancare)."""
    prima = next((r for r in (_senza_vuote_finali(r) for r in griglia) if r), None)
    if not prima or not 3 <= len(prima) <= 4:
        return False
    return all(normalizza(c) in ammessi for c, ammessi in zip(prima, INTESTAZIONE_SCHERMATE))


def _prezzo(testo: str) -> int | None:
    """Il prezzo letto dall'OCR: «12», «12 cr», anche «1O» (la O al posto dello zero)."""
    m = re.search(r"\d+", testo.replace("O", "0").replace("o", "0"))
    return _intero(m.group()) if m and len(m.group()) <= 5 else None


def _estrai_schermate(griglia: list[list], indice: Indice, squadre: dict[str, SquadraLetta], avvisi: list[str]) -> set[str]:
    """Le colonne sono fisse, niente da indovinare: una riga con una cella sola è il nome della fantasquadra (anche con virgole
    e numeri: «FC Esempio 17,5»), «crediti;N» i crediti rimasti, le altre «ruolo;nome;club;prezzo». Ogni nome si cerca nel
    listone con il suo ruolo e la sua squadra: con tutti e due uguali al listone anche un nome abbreviato è sicuro."""
    toccate: set[str] = set()
    corrente: SquadraLetta | None = None
    intestazione = True
    for numero, riga in enumerate(griglia, 1):
        celle = [c[:MAX_TESTO_CELLA] for c in _senza_vuote_finali(riga)]
        if not celle:
            continue
        if intestazione:                             # la prima riga piena è l'intestazione (vedi _e_schermate)
            intestazione = False
            continue
        piene = [c for c in celle if c]
        if len(celle) == 1:
            n = normalizza(celle[0])
            if ETICHETTA_PERSONA.match(celle[0]):
                continue
            numero_crediti = re.search(r"\d+", celle[0])
            if n.startswith("crediti") and numero_crediti and corrente is not None:     # «Crediti residui: 37»
                if len(numero_crediti.group()) <= 5:
                    corrente.crediti_residui = int(numero_crediti.group())
                continue
            corrente = squadre.setdefault(celle[0], SquadraLetta(celle[0]))
            toccate.add(corrente.nome)
            continue
        if normalizza(celle[0]) == "crediti" and len(piene) == 2 and corrente is not None:
            corrente.crediti_residui = _prezzo(celle[1])
            continue
        ruolo = SIGLE_RUOLO.get(normalizza(celle[0]))
        nome = celle[1] if len(celle) > 1 else ""
        if not nome or (celle[0] and ruolo is None):
            avvisi.append(F("rose.riga_schermate_ignorata", riga=numero, celle=", ".join(celle)[:60]))
            continue
        if corrente is None:
            corrente = squadre.setdefault("Squadra senza nome", SquadraLetta("Squadra senza nome"))
            toccate.add(corrente.nome)
        club = celle[2] if len(celle) > 2 and celle[2] else None
        corrente.righe.append(RigaRosa(nome, indice.cerca(nome, club, ruolo), ruolo=ruolo, squadra=club,
                                       costo=_prezzo(celle[3]) if len(celle) > 3 else None))
    return toccate


def _estrai_blocco(celle: _Celle, c0: int, c1: int, nome_foglio: str,
                   squadre: dict[str, SquadraLetta], avvisi: list[str]) -> None:
    colonne = range(c0, c1 + 1)
    squadra_corrente: SquadraLetta | None = None
    col_costo: int | None = None
    for r, _riga in enumerate(celle.g):
        tipi = {c: celle.tipo[r, c] for c in colonne}
        if all(t == "vuoto" for t in tipi.values()):
            continue
        giocatori = [c for c, t in tipi.items() if t == "giocatore"]
        testi = [c for c, t in tipi.items() if t == "testo"]
        # colonna del costo dichiarata da un'intestazione ("costo", "prezzo"...)
        for c, t in tipi.items():
            if t == "intestazione" and set(normalizza(celle.g[r][c]).split()) & PAROLE_COSTO:
                col_costo = c
        # testo con accanto un ruolo o un costo, dentro una squadra: giocatore non riconosciuto (es. ceduto)
        if not giocatori and testi and squadra_corrente is not None and any(
                t in ("ruolo", "numero") for t in tipi.values()):
            celle.esiti[r, testi[0]] = Esito(None, "non trovato", celle.esiti[r, testi[0]].alternative)
            giocatori, testi = [testi[0]], testi[1:]
        if len(giocatori) > 1:
            avvisi.append(F("rose.piu_giocatori_riga", riga=r + 1, nomi=", ".join(celle.g[r][c] for c in giocatori)))
        if giocatori:
            if squadra_corrente is None:
                nome = nome_foglio if normalizza(nome_foglio) not in FOGLI_ANONIMI else "Squadra senza nome"
                squadra_corrente = squadre.setdefault(nome, SquadraLetta(nome))
            c = giocatori[0]
            squadra_corrente.righe.append(RigaRosa(
                testo=celle.g[r][c],
                esito=celle.esiti[r, c],
                ruolo=SIGLE_RUOLO.get(normalizza(_primo(celle, r, colonne, "ruolo") or "")),
                squadra=_primo(celle, r, colonne, "squadra_a"),
                costo=_costo(celle, r, c, c1, col_costo),
            ))
            continue
        if len(testi) == 1:  # nome di una nuova fantasquadra
            nome = celle.g[r][testi[0]]
            squadra_corrente = squadre.setdefault(nome, SquadraLetta(nome))
        elif len(testi) > 1:
            avvisi.append(F("rose.riga_non_chiara", riga=r + 1, celle=" | ".join(celle.g[r][c] for c in testi)))
        crediti = [c for c, t in tipi.items() if t == "crediti"]
        if crediti and squadra_corrente is not None:
            _leggi_crediti(celle, r, crediti[0], colonne, squadra_corrente)


def _costo(celle: _Celle, r: int, c: int, c1: int, col_costo: int | None) -> int | None:
    if col_costo is not None and celle.tipo[r, col_costo] == "numero":
        n = celle.g[r][col_costo]
    else:
        n = _primo(celle, r, range(c + 1, c1 + 1), "numero")
    return _intero(n) if n else None


def _intero(n: str) -> int | None:
    """Un costo o un numero di crediti: solo valori sensati (0-10000); numeri enormi o negativi si scartano."""
    try:
        v = float(n.replace(",", "."))
    except ValueError:
        return None
    return int(v) if 0 <= v <= 10000 else None


def _leggi_crediti(celle: _Celle, r: int, c: int, colonne, squadra: SquadraLetta) -> None:
    testo = celle.g[r][c]
    numero = re.search(r"\d+", testo) or re.search(r"\d+", _primo(celle, r, colonne, "numero") or "")
    if not numero or len(numero.group()) > 5:        # niente numeri a decine di cifre: sono errori o file ostili
        return
    n = normalizza(testo)
    spesi = any(p in n for p in ("spes", "usat", "total", "pagat"))
    if not spesi and (n.startswith("crediti") or "resid" in n or "rimast" in n):
        squadra.crediti_residui = int(numero.group())
    else:  # "totale", "spesa", "crediti spesi"
        squadra.totale_speso = int(numero.group())


def _ruoli_da_posizione(s: SquadraLetta, rosa: dict[str, int]) -> None:
    """Se il file non ha la colonna ruolo ma la rosa è completa e in ordine P, D, C, A, il ruolo si deduce dalla posizione."""
    if any(r.ruolo for r in s.righe) or len(s.righe) != sum(rosa.values()):
        return
    ruoli = [ruolo for ruolo in RUOLI for _ in range(rosa[ruolo])]
    noti = [(riga.esito.calciatore.ruolo, atteso) for riga, atteso in zip(s.righe, ruoli) if riga.esito.trovato]
    if noti and sum(a == b for a, b in noti) / len(noti) >= 0.9:  # l'ordine è davvero per ruolo
        for riga, ruolo in zip(s.righe, ruoli):
            riga.ruolo = ruolo
