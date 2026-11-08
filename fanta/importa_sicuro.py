"""Importazione di rose da file e testo caricati da altri (solo con FANTA_MULTIUTENTE=1): niente fidarsi del contenuto.

Un file Excel (.xlsx) è un archivio zip di file XML. Un file ostile può essere:
- una «bomba zip»: pochi KB che diventano gigabyte; si guardano le dimensioni dichiarate PRIMA di aprirlo;
- pieno di macro (.xlsm, vbaProject.bin), di oggetti incorporati o di collegamenti esterni: si rifiutano;
- un XML con entità (DOCTYPE/ENTITY) che gonfiano la memoria o leggono file del server: si rifiutano tutti i documenti
  con DOCTYPE, e quelli che cambiano codifica per nasconderlo (UTF-16, EBCDIC...). openpyxl consiglia defusedxml per questo
  rischio; qui lo stesso controllo si fa a monte, senza una libreria in più;
- enorme o lentissimo da leggere: la lettura avviene in un processo separato con un tempo massimo (e, su Linux, memoria e
  tempo di CPU massimi), che si può uccidere senza fermare il server. Il processo si ferma da solo oltre il tetto di celle
  (`limiti.MAX_CELLE_IMPORTAZIONE`, tutti i fogli insieme: lo stesso del testo) e la sua uscita si legge al massimo fino a
  `MAX_DECOMPRESSO` byte: oltre lo si ferma, senza tenerla in memoria.
Anche testo e CSV hanno limiti di dimensione, righe, colonne e lo stesso tetto di celle.
Con l'interruttore spento queste regole non si applicano (l'app di sempre legge i file come prima).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from . import limiti

MAX_DECOMPRESSO = 20 * 1024 * 1024       # byte: somma delle dimensioni dichiarate di tutte le parti (un Excel di rose pesa meno di 1 MB)
MAX_PARTE = 12 * 1024 * 1024
MAX_PARTI = 200
RAPPORTO_MAX = 100                       # una parte da più di 1 MB che si comprime più di così è sospetta
MAX_TESTO = 200_000                      # caratteri di testo o CSV incollati o caricati
MAX_FOGLI, MAX_RIGHE, MAX_COLONNE, MAX_TESTO_CELLA = 10, 1500, 60, 200
TEMPO_MASSIMO = 30                       # secondi per leggere un Excel
MEMORIA_MASSIMA = 1024 * 1024 * 1024     # byte di memoria per il processo figlio (solo Linux)
FIGLIO = Path(__file__).with_name("_excel_figlio.py")

# parti che un file di rose non ha bisogno di avere
PROIBITE = ("vbaproject", "macros/", "activex", "embeddings/", "externallinks/", "oleobject", "customui")
ERRORE_FILE = "File Excel non leggibile: è rovinato, protetto da password o non è un vero file .xlsx"
PESANTE = "Il file Excel è troppo pesante da leggere: carica solo il foglio con le rose"
GRANDE_APERTO = "Il file Excel è troppo grande una volta aperto: carica solo il foglio con le rose"
PEZZO_USCITA = 64 * 1024                 # byte letti alla volta dall'uscita del processo che legge l'Excel
TROPPE_CELLE = 5                         # uscita del processo figlio: oltre il tetto di celle (vedi _excel_figlio.py)
_ENTITA = re.compile(rb"<!(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_DICHIARAZIONE = re.compile(rb"""^(?:\xef\xbb\xbf)?\s*<\?xml[^>]*?encoding\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def controlla_zip(percorso: Path) -> None:
    """Rifiuta (ValueError con un messaggio da mostrare) i file Excel pericolosi, senza aprirli con openpyxl."""
    try:
        z = zipfile.ZipFile(percorso)
    except (zipfile.BadZipFile, OSError):
        raise ValueError(ERRORE_FILE) from None
    with z:
        parti = z.infolist()
        if not parti or len(parti) > MAX_PARTI:
            raise ValueError("Il file Excel ha una struttura strana: salvalo di nuovo da Excel come .xlsx normale")
        if sum(p.file_size for p in parti) > MAX_DECOMPRESSO or any(p.file_size > MAX_PARTE for p in parti):
            raise ValueError(GRANDE_APERTO)
        for p in parti:
            nome = p.filename.lower()
            if p.flag_bits & 0x1:
                raise ValueError("Il file Excel è protetto da password: toglila e riprova")
            if nome.startswith(("/", "\\")) or ".." in nome.split("/") or "\\" in nome or ":" in nome:
                raise ValueError("Il file Excel contiene nomi di parti non ammessi")
            if any(x in nome for x in PROIBITE):
                raise ValueError("Il file contiene macro, oggetti incorporati o collegamenti esterni: salvalo come .xlsx normale, senza macro")
            if p.file_size > 1024 * 1024 and p.file_size / max(1, p.compress_size) > RAPPORTO_MAX:
                raise ValueError("Il file Excel è fatto in modo sospetto (si gonfia troppo quando lo apro)")
        tipi = _leggi(z, "[Content_Types].xml")
        if tipi is None:
            raise ValueError(ERRORE_FILE)
        if b"macroenabled" in tipi.lower() or b"vbaproject" in tipi.lower():
            raise ValueError("Il file contiene macro: salvalo come .xlsx normale, senza macro")
        for p in parti:
            if p.filename.lower().endswith((".xml", ".rels", ".vml")):
                _controlla_xml(z, p)


def _leggi(z: zipfile.ZipFile, nome: str) -> bytes | None:
    try:
        with z.open(nome) as f:
            return f.read(MAX_PARTE + 1)
    except (KeyError, zipfile.BadZipFile, RuntimeError, OSError):
        return None


def _controlla_xml(z: zipfile.ZipFile, parte: zipfile.ZipInfo) -> None:
    """Niente DOCTYPE/ENTITY e solo codifica UTF-8 nei documenti XML. Si legge a pezzi (le parti stanno già nei limiti sopra)."""
    prima = True
    resto = b""
    try:
        with z.open(parte) as f:
            while True:
                pezzo = f.read(1024 * 1024)
                if not pezzo:
                    break
                if prima:
                    prima = False
                    _controlla_testa(pezzo[:300])
                blocco = resto + pezzo
                if _ENTITA.search(blocco):
                    raise ValueError("Il file Excel contiene dichiarazioni XML non ammesse: salvalo di nuovo da Excel")
                resto = blocco[-16:]
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError):
        raise ValueError(ERRORE_FILE) from None


def _controlla_testa(testa: bytes) -> None:
    if testa[:2] in (b"\xff\xfe", b"\xfe\xff") or testa[:1] == b"\x00" or testa[1:2] == b"\x00":
        raise ValueError("Il file Excel usa una codifica non ammessa: salvalo di nuovo da Excel come .xlsx normale")
    d = _DICHIARAZIONE.match(testa)
    if d and d.group(1).lower() not in (b"utf-8", b"utf8", b"us-ascii", b"ascii"):
        raise ValueError("Il file Excel usa una codifica non ammessa: salvalo di nuovo da Excel come .xlsx normale")


def leggi_excel(percorso: Path) -> list[tuple[str, list[list[str]]]]:
    """[(nome foglio, griglia)] di un .xlsx, dopo i controlli e in un processo separato con tempo (e su Linux memoria) limitati."""
    controlla_zip(percorso)
    try:
        codice, uscita = _esegui_lettore([sys.executable, "-I", str(FIGLIO), str(percorso), json.dumps({
            "fogli": MAX_FOGLI, "righe": MAX_RIGHE, "colonne": MAX_COLONNE, "cella": MAX_TESTO_CELLA,
            "celle": limiti.valore("MAX_CELLE_IMPORTAZIONE"),
            "memoria": MEMORIA_MASSIMA, "cpu": max(1, int(TEMPO_MASSIMO))})])
    except subprocess.TimeoutExpired:
        raise ValueError(PESANTE) from None
    except OSError:
        raise ValueError(ERRORE_FILE) from None
    if codice == TROPPE_CELLE:
        raise ValueError(GRANDE_APERTO)
    if codice != 0 or uscita is None:
        raise ValueError(ERRORE_FILE if codice == 3 else PESANTE)
    try:
        return [(titolo, griglia) for titolo, griglia in json.loads(uscita)]
    except (ValueError, TypeError):
        raise ValueError(ERRORE_FILE) from None


def leggi_al_massimo(flusso, massimo: int) -> bytes | None:
    """Tutti i byte di `flusso` se sono al massimo `massimo`; altrimenti None, e la lettura si ferma appena li supera:
    in memoria non resta mai più di `massimo` + 1 byte."""
    pezzi, letti = [], 0
    while True:
        pezzo = flusso.read(min(PEZZO_USCITA, massimo + 1 - letti))
        if not pezzo:
            return b"".join(pezzi)
        pezzi.append(pezzo)
        letti += len(pezzo)
        if letti > massimo:
            return None


def _esegui_lettore(comando: list[str]) -> tuple[int | None, bytes | None]:
    """Lancia il processo che legge l'Excel e ne legge l'uscita al massimo fino a MAX_DECOMPRESSO byte, entro TEMPO_MASSIMO
    secondi. (codice di uscita, byte); byte None = uscita oltre il tetto, e il processo è già fermato. Oltre il tempo:
    subprocess.TimeoutExpired. In ogni caso, all'uscita il processo non è più vivo."""
    fine = time.monotonic() + TEMPO_MASSIMO
    processo = subprocess.Popen(comando, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    letto: dict = {}

    def leggi():
        try:
            letto["uscita"] = leggi_al_massimo(processo.stdout, MAX_DECOMPRESSO)
        except (OSError, ValueError):                 # flusso chiuso a metà: come un'uscita che non si può usare
            letto["uscita"] = None
    lettore = threading.Thread(target=leggi, daemon=True)
    try:
        lettore.start()
        lettore.join(max(0.0, fine - time.monotonic()))
        if lettore.is_alive():
            raise subprocess.TimeoutExpired(comando, TEMPO_MASSIMO)
        if letto.get("uscita") is None:
            return None, None
        return processo.wait(timeout=max(0.01, fine - time.monotonic())), letto["uscita"]
    finally:
        if processo.poll() is None:
            processo.kill()                           # oltre il tetto o il tempo: si ferma qui, la sua uscita non serve più
        processo.wait()
        lettore.join(5)
        processo.stdout.close()


def testo_troppo_lungo() -> str:
    return f"Il testo è troppo lungo (massimo {MAX_TESTO // 1000} mila caratteri): incolla solo le rose"


def troppo_pesante(excel: bool) -> str:
    """Il messaggio per un contenuto che costa troppo lavoro (per esempio un riconoscimento oltre il tempo massimo): quello dei
    file Excel troppo pesanti o quello del testo troppo lungo. Messaggi di sempre: i client li traducono già."""
    return PESANTE if excel else testo_troppo_lungo()


def controlla_testo(testo: str) -> None:
    if len(testo) > MAX_TESTO:
        raise ValueError(testo_troppo_lungo())


def celle(griglie: list[tuple[str, list[list[str]]]]) -> int:
    """Le celle che contano per il tetto: in ogni riga fino all'ultima cella piena (le colonne vuote in fondo non costano
    lavoro). Lo stesso conto del processo che legge gli Excel (_excel_figlio.py)."""
    totale = 0
    for _, g in griglie:
        for riga in g:
            totale += next((i + 1 for i in range(len(riga) - 1, -1, -1) if riga[i]), 0)
    return totale


def controlla_griglie(griglie: list[tuple[str, list[list[str]]]]) -> None:
    """Righe, colonne e celle massime per testo e CSV (l'Excel viene già tagliato e fermato dal processo che lo legge)."""
    for _, g in griglie:
        if len(g) > MAX_RIGHE:
            raise ValueError(f"Il file ha troppe righe (massimo {MAX_RIGHE}): carica solo le rose")
        if any(len(r) > MAX_COLONNE for r in g):
            raise ValueError(f"Il file ha troppe colonne (massimo {MAX_COLONNE}): carica solo le rose")
    if celle(griglie) > limiti.valore("MAX_CELLE_IMPORTAZIONE"):            # lo stesso tetto dell'Excel (conta solo con FANTA_ più basso)
        raise ValueError(testo_troppo_lungo())
