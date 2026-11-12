"""Backup dei dati della lega in un file solo: regole, rose, movimenti, scelte, osservati e impostazioni degli avvisi.
Serve quando si cambia server o si vuole una copia al sicuro. Non contiene chiavi né iscrizioni alle notifiche
(restano dove sono): sul nuovo dispositivo si riattivano dall'app."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import lega, movimenti, osservati, regole, scelte
from .limiti import MAX_GIOCATORI_SQUADRA
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .rose import MAX_TESTO_CELLA

FORMATO = "schieraxi-backup"
VERSIONE = 1
COPIA_PRIMA = Path("dati") / "backup-prima-del-ripristino.json"      # lo stato di prima, per tornare indietro
PREFISSO_FILE = "schieraxi-backup"         # nome del file che si scarica e della copia serale

# Tetti del ripristino (oltre: il file non è valido e non si scrive niente).
# Il file più annidato che l'app scrive è lo storico dei movimenti (elenco > voce > scambi > scambio > giocatori > giocatore:
# 6 livelli); 10 lascia margine ai campi che una versione più nuova potrebbe aggiungere.
MAX_PROFONDITA = 10
# Titolari e panchina di una scelta: mai più dei giocatori di una rosa (la più grande ammessa ne ha 40); una lega vera ne usa 11
# più la panchina.
MAX_GIOCATORI_SCELTA = MAX_GIOCATORI_SQUADRA
# Lo storico dei movimenti ne tiene al massimo movimenti.MAX_STORICO (lo taglia movimenti.registra) e gli osservati sono al massimo
# osservati.MASSIMO (osservati.aggiungi): un backup con di più non viene dall'app.
# Una voce dei movimenti: in un gruppo (i giocatori di uno scambio, presi o lasciati da una squadra) al massimo una rosa intera, la
# più grande che le regole ammettono (4 ruoli da regole.MAX_ROSA_PER_RUOLO); il riassunto di un'importazione che cambia tutte le
# rose (20 squadre da 40 giocatori lasciati e presi, nomi veri sotto i 30 caratteri) resta sotto i 100 mila caratteri.
MAX_GIOCATORI_MOVIMENTO = 4 * regole.MAX_ROSA_PER_RUOLO
MAX_TESTO_MOVIMENTO = 100_000


def nome_file(creato: str) -> str:
    """Nome del file di backup per una data ISO (`creato`)."""
    return f"{PREFISSO_FILE}-{creato[:10]}.json"


def _non_valido(nome: str) -> str:
    return f"{nome} non è valido: controlla di aver scelto il file di backup giusto"


def _troppo_annidato(d: Any, massimo: int = MAX_PROFONDITA) -> bool:
    """Vero se `d` ha liste o dizionari uno dentro l'altro per più di `massimo` livelli (`d` stesso è il primo). Senza ricorsione."""
    pila = [(d, 1)] if isinstance(d, (list, dict)) else []
    while pila:
        x, livello = pila.pop()
        if livello > massimo:
            return True
        figli = x.values() if isinstance(x, dict) else x
        pila.extend((v, livello + 1) for v in figli if isinstance(v, (list, dict)))
    return False


def _intero(v: Any) -> bool:
    return type(v) is int                     # non True/False, non 1.0, non «1»


def _numero_o_niente(v: Any) -> bool:
    return v is None or _intero(v) or (type(v) is float and math.isfinite(v))


def _codici(v: Any) -> bool:
    """Un elenco di codici di giocatori, come i titolari salvati dall'app."""
    return (isinstance(v, list) and len(v) <= MAX_GIOCATORI_SCELTA
            and all(_intero(i) and 1 <= i <= osservati.ID_MASSIMO for i in v))


def _dizionario(d: Any) -> None:
    if not isinstance(d, dict):
        raise ValueError("deve essere un elenco di voci")


def _osservati(d: Any) -> list[int]:
    """Codici interi; come nella lettura dell'elenco (osservati.leggi) i doppioni e i numeri che non possono essere giocatori si
    tolgono. Più di osservati.MASSIMO giocatori diversi: non valido. Si scrive l'elenco ripulito."""
    if not isinstance(d, list):
        raise ValueError("deve essere una lista")
    tenuti = list(dict.fromkeys(i for i in d if _intero(i) and 1 <= i <= osservati.ID_MASSIMO))
    if len(tenuti) > osservati.MASSIMO or not all(_intero(i) for i in d):
        raise ValueError("formato non riconosciuto")         # messaggi interni: `controlla` li sostituisce con il suo
    return tenuti


_CHIAVE_SCELTA = re.compile(r"([0-9]{4}-[0-9]{2})/([0-9]{1,3})")      # «stagione/giornata», come la scrive scelte.salva


def _scelte(d: Any) -> None:
    """Le voci come le scrive scelte.salva: chiave «stagione/giornata», titolari (e panchina, se c'è) elenchi di codici di
    giocatori, modulo, tipo e data testi brevi. Gli altri campi (di una versione più nuova) restano com'erano."""
    _dizionario(d)
    for chiave, voce in d.items():
        giusta = _CHIAVE_SCELTA.fullmatch(chiave)
        if not (giusta and int(giusta.group(2)) >= 1 and isinstance(voce, dict) and _codici(voce.get("titolari"))
                and ("panchina" not in voce or _codici(voce["panchina"]))
                and all(k not in voce or (isinstance(voce[k], str) and len(voce[k]) <= MAX_TESTO_ROSE)
                        for k in ("modulo", "tipo", "salvata"))):
            raise ValueError("formato non riconosciuto")


def _forma(giusta: bool) -> None:
    if not giusta:
        raise ValueError("formato non riconosciuto")


def _breve(v: Any) -> bool:
    return isinstance(v, str) and len(v) <= MAX_TESTO_ROSE


def _breve_o_niente(v: Any) -> bool:
    return v is None or _breve(v)


def _solo(d: dict, chiavi: tuple[str, ...]) -> dict:
    return {k: v for k, v in d.items() if k in chiavi}


def _giocatore_movimento(g: Any) -> dict:
    """Le parti di movimenti._breve: codice, nome, ruolo, squadra di Serie A, costo."""
    _forma(isinstance(g, dict) and _breve(g.get("nome")) and (g.get("id") is None or _intero(g["id"]))
           and _breve_o_niente(g.get("ruolo")) and _breve_o_niente(g.get("squadra")) and _numero_o_niente(g.get("costo")))
    return _solo(g, ("id", "nome", "ruolo", "squadra", "costo"))


def _giocatori_movimento(v: Any) -> list[dict]:
    _forma(isinstance(v, list) and len(v) <= MAX_GIOCATORI_MOVIMENTO)
    return [_giocatore_movimento(g) for g in v]


def _scambio(s: Any) -> dict:
    _forma(isinstance(s, dict) and isinstance(s.get("squadre"), list) and len(s["squadre"]) == 2 and all(_breve(n) for n in s["squadre"]))
    return {"squadre": list(s["squadre"]), "da_a": _giocatori_movimento(s.get("da_a")), "da_b": _giocatori_movimento(s.get("da_b"))}


def _gruppo(s: Any) -> dict:
    _forma(isinstance(s, dict) and _breve(s.get("squadra")))
    return {"squadra": s["squadra"], "giocatori": _giocatori_movimento(s.get("giocatori"))}


def _credito(c: Any) -> dict:
    _forma(isinstance(c, dict) and _breve(c.get("squadra")) and _numero_o_niente(c.get("prima")) and _numero_o_niente(c.get("dopo")))
    return _solo(c, ("squadra", "prima", "dopo"))


def _nome_squadra(n: Any) -> str:
    _forma(_breve(n))
    return n


_PARTI_MOVIMENTO = {"scambi": _scambio, "svincolati_presi": _gruppo, "tagliati": _gruppo, "crediti": _credito,
                    "squadre_nuove": _nome_squadra, "squadre_tolte": _nome_squadra}


def _voce_movimento(m: Any) -> dict:
    _forma(isinstance(m, dict) and _breve_o_niente(m.get("quando"))
           and (m.get("testo") is None or (isinstance(m["testo"], str) and len(m["testo"]) <= MAX_TESTO_MOVIMENTO)))
    voce = {}
    for k, v in m.items():
        if k in ("quando", "testo"):
            voce[k] = v
        elif k in _PARTI_MOVIMENTO:
            _forma(v is None or isinstance(v, list))
            voce[k] = None if v is None else [_PARTI_MOVIMENTO[k](x) for x in v]
    return voce


def _movimenti(d: Any) -> list[dict]:
    """Lo storico come lo scrive movimenti.registra: un elenco di voci (al massimo movimenti.MAX_STORICO), ognuna con data e testo
    e gli elenchi di scambi, svincolati presi, tagli, crediti e squadre nuove o tolte, ciascuno con la sua forma (la leggono l'avviso
    «preso da poco» e l'app per iPhone). Si scrive una copia con le sole parti che l'app scrive."""
    _forma(isinstance(d, list) and len(d) <= movimenti.MAX_STORICO)
    return [_voce_movimento(m) for m in d]


REGOLE_OLTRE_I_TETTI = ("Le regole di questo backup superano i limiti dell'app (per esempio troppi moduli o fasce del modificatore, "
                        "oppure testi troppo lunghi) e non è stato cambiato niente: riporta le regole nei limiti dall'app e "
                        "scarica un backup nuovo.")


def _regole(d: Any) -> None:
    """Le regole del backup si controllano come quelle salvate dall'app, con i tetti di misura (#480), anche in un backup fatto
    prima dei tetti: oltre i tetti `regole.RegoleTroppoGrandi` (il ripristino lo dice con REGOLE_OLTRE_I_TETTI e non scrive niente)."""
    regole.da_dict(d)


# Tetti dei testi delle rose del backup, come quelli dell'importazione: ogni cella letta da un file si accorcia a 200 caratteri
# (rose.MAX_TESTO_CELLA), anche il nome di una squadra (la rinomina dall'app ne ammette 60, quindi sta dentro). L'avviso di un
# giocatore lo scrive l'app (per esempio l'elenco dei giocatori con lo stesso nome): un tetto più largo.
MAX_TESTO_ROSE = MAX_TESTO_CELLA
MAX_AVVISO_ROSE = 2000


def _corto(testo: str | None, tetto: int = MAX_TESTO_ROSE) -> bool:
    return testo is None or len(testo) <= tetto


def _rose(d: Any) -> None:
    """Forma e tipi come il file delle rose (lega.da_dict), più i tetti di lunghezza dell'importazione."""
    r = lega.da_dict(d)
    giusti = (_corto(r.mia_squadra) and _corto(r.aggiornato)
              and all(_corto(s.nome) and _corto(s.nome_importato) for s in r.squadre)
              and all(_corto(g.nome) and _corto(g.ruolo) and _corto(g.squadra) and _corto(g.riconosciuto)
                      and _corto(g.avviso, MAX_AVVISO_ROSE) for s in r.squadre for g in s.giocatori))
    if not giusti:
        raise ValueError("formato non riconosciuto")


def _impostazioni_avvisi(d: Any) -> dict:
    """Gli stessi valori ammessi dal salvataggio delle impostazioni; si scrive la versione ripulita (senza voci sconosciute)."""
    from . import notifiche
    return notifiche.impostazioni_da_ripristinare(d)


FILE_SCELTE_BACKUP = "dati/scelte.json"     # le formazioni scelte, una voce per «stagione/giornata»

# file salvati (percorso dentro il progetto) -> controllo del contenuto. Il controllo alza un errore se il contenuto non va;
# restituisce None (si scrive com'è) oppure il contenuto ripulito da scrivere al suo posto. Prima, per ogni file: non più di
# MAX_PROFONDITA livelli (vedi `controlla`).
CONTROLLI: dict[str, Callable[[Any], Any]] = {
    "lega/regole.json": _regole,
    "lega/rose.json": _rose,
    "lega/movimenti.json": _movimenti,
    "dati/scelte.json": _scelte,
    "dati/osservati.json": _osservati,
    "dati/avvisi-impostazioni.json": _impostazioni_avvisi,
}


def _percorsi(radice: Path, file: dict[str, Path] | None) -> dict[str, Path]:
    """Dove sta ogni file del backup: sotto la radice (l'app di sempre) oppure nei percorsi indicati (la cartella di un utente)."""
    return file if file is not None else {nome: radice / nome for nome in CONTROLLI}


def crea(radice: Path = RADICE, file_utente: dict[str, Path] | None = None) -> dict:
    """Tutto quello che c'è, in un dizionario pronto per essere scritto come JSON."""
    file = {}
    for nome, percorso in _percorsi(radice, file_utente).items():
        try:
            file[nome] = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                                  # non c'è (ancora) o è rovinato: nel backup non finisce
    return {"formato": FORMATO, "versione": VERSIONE, "creato": datetime.now().isoformat(timespec="seconds"), "file": file}


def salva_copia(radice: Path = RADICE, cartella: Path | None = None, tieni: int = 7, file_utente: dict[str, Path] | None = None) -> Path | None:
    """Scrive la copia di oggi in dati/backup/ (una al giorno: se c'è già si sostituisce) e tiene solo le ultime `tieni`.
    Con `file_utente` (e `cartella`) è la copia di un utente con un account. Restituisce il file scritto, o None se non c'è niente da salvare."""
    b = crea(radice, file_utente)
    if not b["file"]:
        return None
    cartella = cartella or radice / "dati" / "backup"
    destinazione = cartella / nome_file(b["creato"])
    scrivi_sicuro(destinazione, json.dumps(b, ensure_ascii=False))
    # Si tengono le ultime `tieni` copie (ordine per data, non per nome).
    copie = sorted(cartella.glob(f"{PREFISSO_FILE}-*.json"), key=lambda p: (p.stem[-10:], p.name))
    for vecchia in copie[:-tieni]:
        vecchia.unlink(missing_ok=True)
    return destinazione


def copia_account(cartella: Path, origine: Path, tieni: int = 7) -> Path | None:
    """Con gli account: una copia del database degli utenti (account.sqlite) con l'API di backup di SQLite, che è sicura anche
    mentre il server lo usa. Una al giorno, ne tiene `tieni`. Contiene gli hash delle password: il file lo legge solo chi lo ha creato."""
    import sqlite3
    if not origine.exists():
        return None
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / f"account-{datetime.now():%Y-%m-%d}.sqlite"
    sorgente, copia = sqlite3.connect(origine), sqlite3.connect(destinazione)
    try:
        sorgente.backup(copia)
    finally:
        copia.close()
        sorgente.close()
    try:
        destinazione.chmod(0o600)
    except OSError:
        pass
    for vecchia in sorted(cartella.glob("account-*.sqlite"))[:-tieni]:
        vecchia.unlink(missing_ok=True)
    return destinazione


def controlla(backup: Any) -> dict[str, Any]:
    """Controlla il backup per intero senza toccare niente. Restituisce i file da ripristinare (ripuliti dove serve) o alza ValueError."""
    if not isinstance(backup, dict) or backup.get("formato") != FORMATO:
        raise ValueError("Questo non è un backup di SchieraXI")
    if not isinstance(backup.get("versione"), int) or backup["versione"] > VERSIONE:
        raise ValueError("Il backup viene da una versione più nuova dell'app: aggiorna l'app e riprova")
    file = backup.get("file")
    if not isinstance(file, dict) or not file:
        raise ValueError("Il backup è vuoto")
    pulito: dict[str, Any] = {}
    for nome, contenuto in file.items():
        if nome not in CONTROLLI:
            raise ValueError(f"Il backup contiene un file che non conosco: {str(nome)[:60]}")
        try:
            if _troppo_annidato(contenuto):
                raise ValueError("troppo annidato")
            nuovo = CONTROLLI[nome](contenuto)
        except regole.RegoleTroppoGrandi:
            raise ValueError(REGOLE_OLTRE_I_TETTI) from None
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):      # OverflowError: «Infinity» o 1e999 dove serve un intero
            raise ValueError(_non_valido(nome)) from None
        pulito[nome] = contenuto if nuovo is None else nuovo
    return pulito


def _testi(file: dict[str, Any]) -> dict[str, str]:
    """Il testo di ogni file come andrà su disco, in forma compatta. Un testo che non si può scrivere (un carattere spezzato) si
    scopre qui, prima di scrivere il primo file."""
    testi = {}
    for nome, contenuto in file.items():
        testo = json.dumps(contenuto, ensure_ascii=False)
        try:
            testo.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError(_non_valido(nome)) from None
        testi[nome] = testo
    return testi


def _ultime_giornate(tutte: dict) -> dict:
    """Le scelte delle ultime scelte.MAX_GIORNATE giornate, come le tiene scelte.salva."""
    vecchie = set(chiavi_vecchie(tutte, scelte.MAX_GIORNATE))
    return {k: v for k, v in tutte.items() if k not in vecchie}


def ripristina(backup: Any, radice: Path = RADICE, file_utente: dict[str, Path] | None = None, copia_prima: Path | None = None,
               chiusa: Callable[[str], bool] | None = None) -> list[str]:
    """Rimette i dati del backup (i nomi dei file ripristinati). Vedi `ripristina_esito`."""
    return ripristina_esito(backup, radice, file_utente, copia_prima, chiusa)["ripristinati"]


def ripristina_esito(backup: Any, radice: Path = RADICE, file_utente: dict[str, Path] | None = None, copia_prima: Path | None = None,
                     chiusa: Callable[[str], bool] | None = None, controlla_rose: Callable[[lega.Rose], None] | None = None,
                     spazio: Callable[[int], None] | None = None) -> dict:
    """Rimette i dati del backup. Prima controlla tutto: se qualcosa non va non cambia niente. I file che il backup
    non ha restano com'erano. Lo stato di prima si salva in dati/backup-prima-del-ripristino.json.
    `chiusa(chiave)` dice se la giornata di una voce di `scelte` («stagione/giornata») è già chiusa: quelle voci restano come sono
    sul server (un backup non deve aggirare la scadenza). `controlla_rose(rose)` applica alle rose del backup gli stessi tetti
    dell'importazione (con gli account: `limiti.controlla_rose`), prima di scrivere qualsiasi file. `spazio(byte)` riceve quanto
    pesano i file che si stanno per scrivere (con gli account: `limiti.controlla_spazio`) e può fermare tutto alzando un errore.
    Le scelte tengono le ultime scelte.MAX_GIORNATE giornate. Restituisce {ripristinati, scelte_chiuse_tenute: vero se il backup
    avrebbe cambiato almeno una formazione di una giornata chiusa}."""
    file = controlla(backup)
    if controlla_rose is not None and "lega/rose.json" in file:
        controlla_rose(lega.da_dict(file["lega/rose.json"]))
    dove = _percorsi(radice, file_utente)
    tenute = False
    if FILE_SCELTE_BACKUP in file:
        file = dict(file)
        if chiusa is not None:
            try:
                attuali = json.loads(dove[FILE_SCELTE_BACKUP].read_text(encoding="utf-8"))
            except (OSError, ValueError):
                attuali = {}
            file[FILE_SCELTE_BACKUP], tenute = unisci_scelte(file[FILE_SCELTE_BACKUP], attuali if isinstance(attuali, dict) else {},
                                                             chiusa)
        file[FILE_SCELTE_BACKUP] = _ultime_giornate(file[FILE_SCELTE_BACKUP])
    testi = _testi(file)
    if spazio is not None:
        spazio(sum(len(t.encode("utf-8")) for t in testi.values()))
    scrivi_sicuro(copia_prima or radice / COPIA_PRIMA, json.dumps(crea(radice, file_utente), ensure_ascii=False))
    for nome, testo in testi.items():
        scrivi_sicuro(dove[nome], testo)
    return {"ripristinati": sorted(file), "scelte_chiuse_tenute": tenute}


def unisci_scelte(nuove: dict, attuali: dict, chiusa: Callable[[str], bool]) -> tuple[dict, bool]:
    """Le scelte da scrivere: quelle del backup per le giornate ancora aperte, quelle del server (o nessuna) per le giornate chiuse.
    Il secondo valore è vero se il backup ne avrebbe cambiata almeno una chiusa."""
    chiuse = {k for k in set(nuove) | set(attuali) if chiusa(str(k))}
    unite = {k: v for k, v in nuove.items() if k not in chiuse} | {k: v for k, v in attuali.items() if k in chiuse}
    return unite, any(nuove.get(k) != attuali.get(k) for k in chiuse)
