"""Avvisi sul telefono (notifiche web, ntfy) per le decisioni della formazione. Solo due (#676):

- promemoria: un'ora e un quarto d'ora prima della scadenza della formazione, se non è a posto (`promemoria`; con una scelta
  salvata dalla web serve la spunta «L'ho messa», #639);
- cambio della formazione da schierare: un tuo titolare diventa fuori e la consigliata lo toglie (`cambi`, dopo ogni aggiornamento
  delle probabili), oppure, nell'ultima ora, la consigliata vale almeno un punto atteso in più (`avviso_scadenza`).

Le scelte per avviso delle impostazioni (`cambi`, `promemoria_60`, `promemoria_15`, `riepilogo`, `copertura`, `avviso_prima`) restano
nel file e la rotta le legge e le scrive come prima (l'app per iPhone di oggi le usa), ma qui non contano più: decide l'interruttore
unico, cioè se l'utente ha acceso gli avvisi su un dispositivo. Contano ancora le ore tranquille, la lingua e `app_nativa`.

Il canale ntfy sta nella variabile FANTA_CANALE_AVVISI (o FANTA_NTFY_CANALE) oppure nel file dati/canale-avvisi.txt. I testi contengono i nomi dei calciatori:
passano dal server pubblico ntfy.sh e il nome del canale fa da password.

Lingua: titolo e testo sono `Frase` (fanta/frasi.py, inglese in fanta/frasi_avvisi.py); `invia` li scrive nella lingua scelta
dall'utente nelle impostazioni degli avvisi (`lingua`, "it" o "en", predefinito italiano).
"""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from . import avvisi, frasi
from .frasi import F
from .lega import Rose
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .regole import Regole, serie_a_a_lega

LOG = logging.getLogger(__name__)
FILE_STATO = RADICE / "dati" / "notifiche.json"
FILE_PROMEMORIA = RADICE / "dati" / "notifiche-promemoria.json"      # file separato: cambi e promemoria girano da script diversi
FILE_IMPOSTAZIONI = RADICE / "dati" / "avvisi-impostazioni.json"
LINGUE = ("it", "en")
LINGUA_PREDEFINITA = "it"
IMPOSTAZIONI_PREDEFINITE = {"cambi": True, "promemoria_60": True, "promemoria_15": True, "riepilogo": True, "app_nativa": False,
                            "silenzio": False, "copertura": True}
CAMPI_UTENTE = ("primo_avvio", "backup_il", "mostra_tutte")    # altri campi dello stesso file, gestiti da stato_utente.py
BLOCCO_FILE = threading.Lock()
ORE_PREDEFINITE = {"silenzio_da": 23, "silenzio_a": 7}      # ore tranquille: dalle 23 alle 7 (se "silenzio" è acceso)
# a quale sezione dell'app nativa porta il tocco sull'avviso ntfy (schema schieraxi://, vedi l'app iOS); quel che non è qui apre Lega
SEZIONE_PER_TAG = {"rotating_light": "formazione", "alarm_clock": "formazione"}
FUORI = ("infortunato", "squalificato")
# un titolare delle probabili sotto questa percentuale della fonte è «in ballottaggio» (come consigli.PERC_BALLOTTAGGIO): l'avviso
# scatta quando la passa, in su o in giù, e lo dice a parole (all'utente si mostra una sola percentuale, «gioca N%»)
PERC_BALLOTTAGGIO = 60
MAX_RIGHE = 8
FINESTRE = [("60", 45, 65, 3), ("15", 4, 20, 4)]   # promemoria: (nome, da minuti, a minuti, priorità)
# avviso intelligente prima della scadenza (vedi `avviso_scadenza`)
MINUTI_AVVISO = (0, 30, 60, 90)          # valori ammessi di `avviso_prima` nelle impostazioni (la rotta li salva ancora, #676)
AVVISO_PRIMA_PREDEFINITO = 60            # da quanti minuti prima della scadenza si guarda se il consiglio è cambiato: per tutti
SOGLIA_AVVISO_PUNTI = 1.0                # punti attesi in più perché valga la pena disturbare: sotto è il su e giù normale
MAX_AVVISI_SCADENZA = 2                  # al massimo per giornata
MINUTI_MINIMI = 2                        # a meno di 2 minuti dalla chiusura non serve più
DOPPIONE_PROMEMORIA = 20                 # minuti: subito dopo questo avviso (o un «cambio pronto» sugli stessi titolari, #906) il
#                                          promemoria della stessa finestra non riparte
DOPPIONE_CAMBI = 15                      # minuti: se l'avviso sui cambi delle probabili è appena partito, questo non lo ripete


# ---------------------------------------------------------------- invio
def canale() -> str | None:
    for nome in ("FANTA_CANALE_AVVISI", "FANTA_NTFY_CANALE"):
        c = os.environ.get(nome)
        if c and c.strip():
            return c.strip()
    # file nella cartella dei dati; il secondo e' il posto dove i server gia' installati lo tengono (ripiego, resta valido)
    for file in (RADICE / "dati" / "canale-avvisi.txt", Path.home() / ".config" / "schieraxi" / "canale"):
        try:
            c = file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if c:
            return c
    return None


def invia(titolo: str, testo: str, priorita: int = 3, tag: str = "soccer", ignora_silenzio: bool = False,
          file_impostazioni: Path | None = None, file_iscrizioni: Path | None = None, ntfy: bool = True,
          vale_per: timedelta | None = None) -> bool:
    """Manda l'avviso: con le notifiche web attive su almeno un dispositivo si usano quelle; altrimenti (o se non arriva a nessuno) ntfy.
    Nelle ore tranquille non parte niente e restituisce False: cambi e promemoria allora riprovano al giro dopo, fuori dalla fascia.
    I file sono quelli dell'utente (di norma quelli di sempre); `ntfy=False` per gli utenti con un account: il canale ntfy è uno
    solo, del proprietario del server, e i nomi dei calciatori di un altro non devono finire lì.
    `vale_per`: per gli avvisi sulla formazione, quanto manca alla scadenza: la notifica web non arriva dopo (`push.tempo_di_vita`)."""
    from . import push
    opzioni = impostazioni(file_impostazioni)
    if not ignora_silenzio and in_silenzio(datetime.now(), opzioni):
        return False
    titolo, testo = frasi.testo(titolo, opzioni["lingua"]), frasi.testo(testo, opzioni["lingua"])      # nella lingua scelta dall'utente
    arrivato = bool(push.iscrizioni(file_iscrizioni)) and push.invia(titolo, testo, priorita, tag, file_iscrizioni,
                                                                     vale_per=vale_per) > 0
    if not ntfy:
        return arrivato
    if opzioni.get("app_nativa"):
        # con l'app nativa (che non può ricevere le push di Apple) l'avviso va anche su ntfy: il tocco apre l'app nativa
        return _invia_ntfy(titolo, testo, priorita, tag, f"schieraxi://{SEZIONE_PER_TAG.get(tag, 'lega')}") or arrivato
    return arrivato or _invia_ntfy(titolo, testo, priorita, tag)


def _invia_ntfy(titolo: str, testo: str, priorita: int, tag: str, apri: str | None = None) -> bool:
    c = canale()
    if not c:
        return False
    corpo = {"topic": c, "title": titolo, "message": testo, "priority": priorita, "tags": [tag]}
    if apri:
        corpo["click"] = apri
    try:
        r = requests.post("https://ntfy.sh", json=corpo, timeout=20)
        return r.ok
    except requests.RequestException:
        return False


def manda_di(file_impostazioni: Path, file_iscrizioni: Path, ntfy: bool) -> Callable[..., bool]:
    """La funzione `manda` di un utente: i suoi dispositivi, le sue impostazioni, e ntfy solo se `ntfy` è vero."""
    return lambda *a, **k: invia(*a, file_impostazioni=file_impostazioni, file_iscrizioni=file_iscrizioni, ntfy=ntfy, **k)


def segna_guasto(guasti: list[str] | None, cosa: str, errore: Exception) -> None:
    """Un pezzo di un avviso non riuscito mentre il resto parte lo stesso: il guasto non si ingoia (#660). Con `guasti` (il giro
    degli utenti, che sa di chi è) va nell'elenco e lo scrive chi chiama, con il numero dell'utente; senza, una riga nel registro.
    Solo il tipo d'errore: il messaggio può contenere dati."""
    testo = f"{cosa} ({type(errore).__name__})"
    if guasti is None:
        LOG.warning("Avvisi: %s", testo)
    else:
        guasti.append(testo)


# ---------------------------------------------------------------- impostazioni e stato su file
def _json(percorso: Path) -> dict:
    try:
        d = json.loads(percorso.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _ora(valore, predefinita: int) -> int:
    try:
        v = int(valore)
    except (TypeError, ValueError, OverflowError):      # OverflowError: un numero infinito (1e999 nel JSON)
        return predefinita
    return v if 0 <= v <= 23 else predefinita


def _minuti_avviso(valore, predefinito: int) -> int:
    """Uno dei valori ammessi per `avviso_prima` (0, 30, 60, 90); altrimenti quello di prima."""
    if isinstance(valore, bool):
        return predefinito
    try:
        v = int(valore)
    except (TypeError, ValueError, OverflowError):
        return predefinito
    return v if v in MINUTI_AVVISO else predefinito


def _lingua(valore, predefinita: str) -> str:
    """«it» o «en»; qualunque altra cosa: quella di prima."""
    return valore if isinstance(valore, str) and valore in LINGUE else predefinita


def impostazioni(percorso: Path | None = None) -> dict:
    d = _json(percorso or FILE_IMPOSTAZIONI)
    ok = {k: bool(d.get(k, v)) for k, v in IMPOSTAZIONI_PREDEFINITE.items()}
    ok |= {k: _ora(d.get(k, v), v) for k, v in ORE_PREDEFINITE.items()}
    ok["avviso_prima"] = _minuti_avviso(d.get("avviso_prima", AVVISO_PRIMA_PREDEFINITO), AVVISO_PRIMA_PREDEFINITO)
    ok["lingua"] = _lingua(d.get("lingua"), LINGUA_PREDEFINITA)
    if ok["silenzio_da"] == ok["silenzio_a"]:
        # inizio = fine non è una fascia (salvate prima del controllo): spente e con le ore predefinite, così riaccendendole con
        # il solo `silenzio` (web e iPhone non scelgono le ore) valgono dalle 23 alle 7 invece di dare errore (#711)
        ok |= {"silenzio": False, **ORE_PREDEFINITE}
    return ok


def ore_tranquille_spente(percorso: Path | None = None) -> bool:
    """Nel file ci sono ore tranquille accese con inizio uguale a fine (vecchio salvataggio): `impostazioni` le dà per spente."""
    d = _json(percorso or FILE_IMPOSTAZIONI)
    da, a = (_ora(d.get(k, v), v) for k, v in ORE_PREDEFINITE.items())
    return bool(d.get("silenzio", IMPOSTAZIONI_PREDEFINITE.get("silenzio", False))) and da == a


def salva_impostazioni(nuove: dict, percorso: Path | None = None) -> dict:
    percorso = percorso or FILE_IMPOSTAZIONI
    with BLOCCO_FILE:
        prima = impostazioni(percorso)
        ok = {k: bool(nuove.get(k, prima[k])) for k in IMPOSTAZIONI_PREDEFINITE}
        ok |= {k: _ora(nuove.get(k, prima[k]), prima[k]) for k in ORE_PREDEFINITE}
        ok["avviso_prima"] = _minuti_avviso(nuove.get("avviso_prima", prima["avviso_prima"]), prima["avviso_prima"])
        ok["lingua"] = _lingua(nuove.get("lingua"), prima["lingua"])
        # nello stesso file vivono anche piccoli campi dell'utente che non sono avvisi (vedi stato_utente.py): non si perdono
        altri = {k: v for k, v in _json(percorso).items() if k in CAMPI_UTENTE}
        scrivi_sicuro(percorso, json.dumps(altri | ok))
    return ok


def _intero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _numeri_finiti(valore) -> bool:
    """Vero se dentro `valore` (anche in liste e dizionari annidati) non c'è nessun numero infinito o NaN."""
    da_vedere = [valore]
    while da_vedere:
        v = da_vedere.pop()
        if isinstance(v, float) and not math.isfinite(v):
            return False
        if isinstance(v, dict):
            da_vedere.extend(v.values())
        elif isinstance(v, list):
            da_vedere.extend(v)
    return True


def impostazioni_da_ripristinare(d) -> dict:
    """Le impostazioni di un backup, con gli stessi valori ammessi dal salvataggio (`salva_impostazioni`): restano solo le voci
    note (gli avvisi e CAMPI_UTENTE, che stato_utente ripulisce quando li legge); le altre si tolgono. Un valore che l'app non
    salverebbe mai (tipo sbagliato, ora fuori dalla giornata, minuti non previsti, lingua sconosciuta, numero non finito) alza
    ValueError: il ripristino allora non scrive niente."""
    if not isinstance(d, dict):
        raise ValueError("deve essere un elenco di voci")
    tenute = {k: v for k, v in d.items() if k in IMPOSTAZIONI_PREDEFINITE or k in ORE_PREDEFINITE or k in CAMPI_UTENTE
              or k in ("avviso_prima", "lingua")}
    giusti = (all(isinstance(tenute[k], bool) for k in IMPOSTAZIONI_PREDEFINITE if k in tenute)
              and all(_intero(tenute[k]) and 0 <= tenute[k] <= 23 for k in ORE_PREDEFINITE if k in tenute)
              and ("avviso_prima" not in tenute or (_intero(tenute["avviso_prima"]) and tenute["avviso_prima"] in MINUTI_AVVISO))
              and ("lingua" not in tenute or (isinstance(tenute["lingua"], str) and tenute["lingua"] in LINGUE)))
    if not giusti or not _numeri_finiti(tenute):
        raise ValueError("formato non riconosciuto")       # messaggio interno: il backup lo sostituisce con il suo
    return tenute


def in_silenzio(adesso: datetime, opzioni: dict) -> bool:
    """Siamo nelle ore tranquille scelte (per esempio dalle 23 alle 7, anche a cavallo della mezzanotte)?"""
    da, a = opzioni.get("silenzio_da", ORE_PREDEFINITE["silenzio_da"]), opzioni.get("silenzio_a", ORE_PREDEFINITE["silenzio_a"])
    if not opzioni.get("silenzio") or da == a:
        return False
    return da <= adesso.hour < a if da < a else adesso.hour >= da or adesso.hour < a


# ---------------------------------------------------------------- cambi delle probabili
def istantanea(prev: pd.DataFrame, ids: list[int]) -> dict:
    """Lo stato dei giocatori indicati: nome, stato nelle probabili, percentuale, in dubbio."""
    risultato = {}
    for i in ids:
        if i in prev.index:
            x = prev.loc[i]
            risultato[str(i)] = {"nome": x["nome"], "stato": None if pd.isna(x["stato"]) else str(x["stato"]),
                                 "perc": None if pd.isna(x["percentuale"]) else float(x["percentuale"]), "dubbio": bool(x["dubbio"]),
                                 "diffidato": bool(x["diffidato"]) if "diffidato" in x.index and pd.notna(x["diffidato"]) else False}
    return risultato


def confronta(prima: dict, dopo: dict) -> list[str]:
    """Righe di testo per ogni giocatore il cui stato è cambiato in modo che conti per la formazione. A parole, senza la
    percentuale delle probabili (l'unica percentuale che l'utente vede è «gioca N%»)."""
    righe = []
    for k, d in dopo.items():
        p = prima.get(k)
        if not p:
            continue
        nome, sp, sd = d["nome"], p["stato"], d["stato"]
        if sd in FUORI and sp not in FUORI:
            righe.append(F("n.ora_" + sd, nome=nome))
        elif sp in FUORI and sd in ("titolare", "panchina"):
            righe.append(F("n.torna_" + sd, nome=nome))
        elif sp == "titolare" and sd == "panchina":
            righe.append(F("n.titolare_a_panchina", nome=nome))
        elif sp == "panchina" and sd == "titolare":
            righe.append(F("n.ora_titolare", nome=nome))
        elif sp == "titolare" and sd == "non_citato":
            righe.append(F("n.non_convocato", nome=nome))
        elif sp == "titolare" and sd == "titolare" and p["perc"] is not None and d["perc"] is not None \
                and (p["perc"] < PERC_BALLOTTAGGIO) != (d["perc"] < PERC_BALLOTTAGGIO):
            righe.append(F("n.ora_ballottaggio" if d["perc"] < PERC_BALLOTTAGGIO else "n.ora_titolare_sicuro", nome=nome))
        elif sd == "titolare" and d["dubbio"] and not p["dubbio"]:
            righe.append(F("n.ora_dubbio", nome=nome))
        if d.get("diffidato") and not p.get("diffidato") and sd not in FUORI:
            righe.append(F("n.diffidato", nome=nome))
    return righe


def _mia_rosa_ids(rose: Rose) -> list[int]:
    s = rose.squadra(rose.mia_squadra or "")
    return [g.id for g in s.giocatori if g.id is not None] if s else []


def _cambi_pronti(db: sqlite3.Connection, regole: Regole, rose: Rose, prev: pd.DataFrame, ora: dict, titolari: list[int], giornata: int,
                  gia: set[str], chiave: str, file_scelte: Path | None, formazione: dict | None = None) -> list[dict]:
    """«Cambio pronto»: per ogni tuo titolare (quello della tua scelta salvata, se si può ancora schierare, altrimenti il consigliato)
    che ora è infortunato, squalificato o in panchina, chi mettere al suo posto (lo stesso calcolo di «Da fare» in Oggi: solo se la
    consigliata lo toglie).
    Ogni cambio una volta sola: la chiave è giornata, giocatore e motivo. Senza un sostituto non c'è niente da proporre.
    `formazione`: la consigliata già calcolata da `cambi` (None = la legge «Da fare», dalla cache)."""
    from . import da_fare, scelte
    scelta = scelte.leggi(chiave.split("/")[0], giornata, file_scelte)
    if scelta:                                     # conta solo se si può ancora schierare (regola unica): se no vale la consigliata
        scelta = scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole)
    schierati = [int(i) for i in scelta["titolari"]] if scelta else list(titolari)
    motivi = ("infortunato", "squalificato", "panchina")
    nuovi = {}
    for i in schierati:
        s = (ora.get(str(i)) or {}).get("stato")
        if s in motivi and f"{chiave}/{i}/{s}" not in gia:
            nuovi[i] = s
    if not nuovi:
        return []
    try:                                           # il cambio solo se la consigliata lo fa (come «Da fare», #266)
        voci = da_fare._dubbi(db, regole, rose, giornata, file_scelte, formazione=formazione)
    except Exception as e:                         # noqa: BLE001  (l'avviso dei cambi parte comunque)
        LOG.warning("cambio pronto: sostituti non calcolati (%s)", type(e).__name__)
        return []
    risultato = []
    for v in voci:
        i = (v.get("giocatore") or {}).get("id")
        alt = v.get("alternativa")
        if i not in nuovi or not alt:
            continue
        nome = v["giocatore"]["nome"]
        consiglio = F("n.meglio", alt=alt["nome"])
        # i punti attesi della FORMAZIONE in più con il cambio (`differenza` della voce, gli stessi della decisione in cima alla
        # Formazione), non la differenza fra i due giocatori: la panchina copre già in parte chi non gioca (collaudo del 26/11)
        d = v.get("differenza")
        if isinstance(d, (int, float)) and d > 0.05:
            consiglio = F("n.meglio_guadagno", alt=alt["nome"], punti=float(d))
        risultato.append({"nome": nome, "chiave": f"{chiave}/{i}/{nuovi[i]}", "frase": F("n.tuo_" + nuovi[i], nome=nome),
                          "consiglio": consiglio, "fatto": f"{i}/{nuovi[i]}"})
    return risultato


def _consigliata_cambiata(prev: pd.DataFrame, vecchio: dict | None, ora: dict, titolari: list[int], modulo: str | None,
                          chiusura: datetime) -> frasi.Frase | None:
    """La frase dell'avviso se dall'ultimo controllo (`vecchio`) la consigliata ha cambiato titolari perché uno di loro è diventato
    fuori (MOTIVI_FUORI: prima non lo era, ora sì, `ora`), altrimenti None: «Castoldi è infortunato: metti Bonvicini e passa al
    4-4-2. La formazione si chiude il 28/10 alle 18:30.» Senza `titolari` (con la rosa non si forma più una squadra) lo dice.
    Un cambio di soli punti attesi non passa di qui: nell'ultima ora lo dice `avviso_scadenza`."""
    prima = [int(i) for i in (vecchio or {}).get("titolari") or []]
    if not prima or set(prima) == set(titolari):
        return None
    giocatori = (vecchio or {}).get("giocatori") or {}
    motivi = []
    for i in prima:
        adesso, allora = ora.get(str(i)) or {}, giocatori.get(str(i)) or {}
        if i not in titolari and adesso.get("stato") in MOTIVI_FUORI and allora.get("stato") not in MOTIVI_FUORI:
            motivi.append(F("n.m_" + adesso["stato"], nome=adesso["nome"]))
    if not motivi:
        return None
    entrano = [str(prev.at[i, "nome"]) for i in titolari if i not in prima and i in prev.index]
    if not titolari:
        frase = F("n.senza_sostituto", motivi=_elenco(motivi, 2))
    elif entrano:
        frase = F("n.metti", motivi=_elenco(motivi, 2), entrano=_elenco(entrano))
        if modulo and (vecchio or {}).get("modulo") not in (None, modulo):
            frase = F("n.e_passa", frase=frase, modulo=modulo)
    else:
        return None
    return F("n.testo_cambiata", frase=frase, data=f"{chiusura:%d/%m}", ora=f"{chiusura:%H:%M}")


def cambi(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_STATO,
          manda: Callable[..., bool] = invia, opzioni: dict | None = None, *, risparmia: bool = False,
          file_scelte: Path | None = None, file_promemoria: Path | None = None, guasti: list[str] | None = None) -> list[str]:
    """Dopo ogni aggiornamento delle probabili: l'avviso quando cambia la formazione da schierare perché un tuo titolare non gioca
    più (#676). Restituisce le frasi mandate.
    - Con una formazione salvata che si può ancora schierare: «cambio pronto» per ogni suo titolare ora infortunato, squalificato o
      in panchina che la consigliata toglie, con chi mettere (`_cambi_pronti`, una volta sola per giocatore e motivo).
    - Senza, o se non vale più, conta la consigliata: se dall'ultimo controllo ha cambiato titolari perché uno è diventato fuori,
      un avviso con il motivo, chi entra e la scadenza (`_consigliata_cambiata`).
    I cambi delle probabili che non cambiano la formazione da schierare (chi non è titolare, un titolare in dubbio o diffidato) e i
    giocatori seguiti non si avvisano più; un cambio di soli punti attesi lo dice, nell'ultima ora, `avviso_scadenza`. La vecchia
    scelta `cambi` delle impostazioni non conta: di `opzioni` contano solo le ore tranquille (che guarda `manda`).
    Vicino alla scadenza (finestra dell'avviso «cambia la formazione») prova prima quell'avviso; questo tace solo se è partito
    davvero, con i dati di adesso, negli ultimi DOPPIONE_CAMBI minuti. Se non parte (già due avvisi, guadagno piccolo...) questo
    si dice come sempre: nessuna notizia va persa. `file_promemoria`: lo stato di quell'avviso (di base il file
    `notifiche-promemoria.json` accanto a `file_stato`). Nelle ore tranquille o se l'invio fallisce lo stato non cambia: si
    riprova al giro dopo.
    `risparmia` (per chi ha molti utenti da controllare): il confronto degli stati costa poco, la formazione consigliata molto;
    se non è cambiato niente si tiene quella dell'ultimo controllo invece di ricalcolarla.
    Se l'avviso «cambia la formazione» alza un errore questo parte lo stesso, e il guasto va in `guasti` o nel registro
    (`segna_guasto`)."""
    from . import consigli, scelte
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    ids = _mia_rosa_ids(rose)
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole, adesso)     # l'ora del giro, non l'orologio vero
    if not ids or giornata is None:
        return []
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
    if inizio is None or inizio <= adesso:
        return []                                  # la formazione si è già chiusa: i cambi non servono più
    prev, giornata, con_probabili = consigli.previsioni(db, regole, giornata)     # la giornata del giro, non cercata di nuovo
    if not con_probabili:
        return []                                  # senza probabili non c'è niente da confrontare
    ora = istantanea(prev, ids)
    chiave = f"{stagione}/{giornata}"
    stato = _json(file_stato)
    vecchio = stato.get("cambi", {}).get(chiave)
    cambiato = bool(vecchio) and bool(confronta(vecchio["giocatori"], ora))
    if risparmia and vecchio and vecchio.get("titolari") and not cambiato and set(vecchio["giocatori"]) == set(ora):
        f, titolari, modulo = None, vecchio["titolari"], vecchio.get("modulo")     # niente è cambiato: vale quella di prima
    else:
        try:
            f = consigli.formazione(db, regole, rose, giornata=giornata, adesso=adesso)
            titolari, modulo = sorted(int(x["id"]) for x in f["titolari"]), f.get("modulo")
        except ValueError:                         # per esempio nessun portiere disponibile: con un titolare fuori va detto
            f, titolari, modulo = None, [], None
    scelta = scelte.leggi(stagione, giornata, file_scelte)
    salvata = bool(scelta) and scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole) is not None
    pronti = _cambi_pronti(db, regole, rose, prev, ora, titolari, giornata, set(stato.get("pronti", [])), chiave, file_scelte, f)
    cambiata = None if salvata else _consigliata_cambiata(prev, vecchio, ora, titolari, modulo, inizio)
    singoli = list(pronti)
    gia_detti = []
    if (singoli or cambiata is not None) and tocca_all_avviso(inizio, adesso):
        file_promemoria = file_promemoria or file_stato.with_name(FILE_PROMEMORIA.name)
        try:                                       # prima l'avviso «cambia la formazione», con i dati appena arrivati
            gia_detti = avviso_scadenza(db, regole, rose, adesso, file_promemoria, manda, opzioni, file_scelte, file_stato)
        except Exception as e:                     # noqa: BLE001  (questo avviso parte comunque; il guasto si vede)
            gia_detti = []
            segna_guasto(guasti, "avviso «cambia la formazione» non controllato", e)
        if _avviso_scadenza_partito(file_promemoria, chiave, adesso, _versione_dati(db)):
            singoli, cambiata = [], None           # l'ha già detto lui (niente doppioni); lo stato si salva lo stesso, così
            #                                        questa notizia non riparte più tardi
    detti = []
    fatti = _fatti_detti(vecchio)                  # «giocatore/motivo» -> quando l'ha detto il «cambio pronto» (per il promemoria)
    if cambiata is not None:                       # il tocco apre la Formazione; la notifica web non arriva dopo la scadenza
        if not manda(F("n.t_cambia_titolare"), cambiata, 4, "rotating_light", vale_per=inizio - adesso):
            return gia_detti                       # ore tranquille o invio fallito: lo stato resta, al prossimo giro si riprova
        detti.append(cambiata)
    if singoli:
        testi = [F("n.frase_consiglio", frase=p["frase"], consiglio=p["consiglio"]) for p in singoli[:MAX_RIGHE]]
        if manda(F("n.t_cambio_pronto"), frasi.elenco(testi, sep="\n"), 4, "rotating_light", vale_per=inizio - adesso):
            detti += testi
            fatti |= {p["fatto"]: adesso.isoformat(timespec="seconds") for p in singoli[:MAX_RIGHE]}
        elif not detti:
            return gia_detti                       # ore tranquille o invio fallito: si riprova al giro dopo
        else:
            pronti = [p for p in pronti if p not in singoli]     # l'altro avviso è partito: lo stato si salva, il «cambio pronto» riprova
    if pronti:
        stato["pronti"] = (list(stato.get("pronti", [])) + [p["chiave"] for p in pronti])[-80:]
    cambi_stato = stato.setdefault("cambi", {})
    # quando è partito l'ultimo avviso sui TUOI giocatori: l'avviso «cambia la formazione» non lo ripete (DOPPIONE_CAMBI)
    inviato = adesso.isoformat(timespec="seconds") if detti else (vecchio or {}).get("inviato")
    cambi_stato[chiave] = ({"giocatori": ora, "titolari": titolari} | ({"modulo": modulo} if modulo else {})
                           | ({"inviato": inviato} if inviato else {}) | ({"detti": fatti} if fatti else {}))
    for vecchia in chiavi_vecchie(cambi_stato, 6):
        cambi_stato.pop(vecchia, None)
    scrivi_sicuro(file_stato, json.dumps(stato))
    return gia_detti + detti


# ---------------------------------------------------------------- promemoria prima della scadenza
NON_VALIDA = "non_valida"          # `_gia_schierato`: c'è una scelta salvata, ma non si può più schierare
NON_MESSA = "non_messa"            # `_gia_schierato`: scelta salvata (web o app) e a posto, ma non segnata come messa nell'app della lega
SOLO_SCADENZA = "solo_scadenza"    # promemoria: i titolari a rischio li ha appena detti il «cambio pronto», resta solo l'ora (#906)


def _giornata(giornata: int, regole: Regole) -> frasi.Frase:
    """La giornata negli avvisi con i due numeri, «Giornata 6 · 9ª di Serie A» (frasi.nome_giornata): `giornata` è quella di Serie A."""
    return frasi.nome_giornata(giornata, serie_a_a_lega(giornata, regole), avviso=True)


def _situazione(db: sqlite3.Connection, regole: Regole, rose: Rose, stagione: str, giornata: int,
                file_scelte: Path | None) -> tuple[list[tuple[int, str, str]] | str | None, bool]:
    """La scelta salvata vista dal promemoria: (esito, schierata). `esito` è la regola di `_gia_schierato`, con i titolari a rischio
    come (codice, nome, stato nelle probabili); `schierata` è vero se la scelta è segnata «L'ho messa» o è di quelle salvate prima
    del 13/11, che non dicono da dove arrivano (il testo dice «hai schierato» invece di «hai salvato», #906)."""
    from . import consigli, scelte
    scelta = scelte.leggi(stagione, giornata, file_scelte)
    if not scelta:
        return None, False
    try:
        prev, _, _ = consigli.previsioni(db, regole, giornata)
    except Exception:                              # noqa: BLE001  (senza previsioni la regola si controlla con la rosa)
        prev = None
    if not scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole):
        return NON_VALIDA, False                   # giocatore ceduto, modulo non ammesso...: vale la consigliata
    schierata = scelta.get("da") not in scelte.DA or scelta.get("messa") is True
    problemi = []
    for i in (scelta["titolari"] if prev is not None else []):     # senza previsioni non so dire se è cambiato qualcosa
        if i in prev.index and prev.at[i, "stato"] in MOTIVI_FUORI:
            problemi.append((int(i), str(prev.at[i, "nome"]), str(prev.at[i, "stato"])))
    if not problemi and not schierata:
        return NON_MESSA, False
    return problemi, schierata


def _gia_schierato(db: sqlite3.Connection, regole: Regole, rose: Rose, stagione: str, giornata: int,
                   file_scelte: Path | None) -> list[tuple[int, str, str]] | str | None:
    """None se non hai ancora schierato (nessuna scelta salvata, né «ho schierato la consigliata»). `NON_VALIDA` se la scelta salvata
    non si può più schierare (regola unica della scelta, come la Formazione: vale la consigliata, come senza scelta, ma il promemoria
    lo dice con una frase sua). Altrimenti la lista dei titolari che hai schierato e che ora risultano fuori, in panchina o non
    citati nelle probabili, come (codice, nome, stato); se non ce n'è nessuno, la lista vuota (a posto) oppure `NON_MESSA` (#639):
    web e iPhone salvano da soli a ogni tocco, quindi una loro scelta è a posto solo con la spunta «L'ho messa» (l'iPhone ce l'ha
    dal riallineamento, #673). Le scelte che non dicono da dove arrivano (salvate prima del 13/11) restano a posto come prima. La
    regola è una sola: la usano il promemoria, `serve_promemoria` e `testi_promemoria` (campi di GET /api/oggi)."""
    return _situazione(db, regole, rose, stagione, giornata, file_scelte)[0]


def serve_promemoria(db: sqlite3.Connection, regole: Regole, rose: Rose, stagione: str, giornata: int, file_scelte: Path | None) -> bool:
    """Il promemoria della scadenza serve per questa giornata? La regola di `promemoria` (`_gia_schierato`), senza finestre né invii:
    no (False) solo con una scelta che si può schierare, spuntata «L'ho messa» (o salvata prima che la scelta ricordasse da dove
    arriva) e senza titolari diventati indisponibili. È il campo `serve_promemoria` di GET /api/oggi: l'iPhone programma con questo i
    suoi promemoria locali, anche in background, così una spunta messa o tolta dalla web vale anche lì (#710)."""
    return _gia_schierato(db, regole, rose, stagione, giornata, file_scelte) != []


def _testo_promemoria(db: sqlite3.Connection, regole: Regole, rose: Rose, giornata: int, nome: str, inizio: datetime, adesso: datetime,
                      esito, schierata: bool, guasti: list[str] | None = None) -> tuple[frasi.Frase, frasi.Frase]:
    """Titolo e testo del promemoria della finestra `nome` («60» o «15») per l'`esito` di `_situazione` (mai la lista vuota: allora
    il promemoria non parte). Il fatto che conta in testa al testo e nel titolo, la giornata e l'ora dopo: con due o tre righe il
    resto si taglia (#906). Lo usano il giro dei promemoria e `testi_promemoria`.
    Se i dettagli della formazione (un'ora prima) non si calcolano il testo resta senza, e il guasto va in `guasti` o nel registro."""
    from . import consigli
    g, ora = _giornata(giornata, regole), inizio.strftime("%H:%M")
    un_ora = nome == "60"
    if esito == NON_MESSA:                         # salvata ma non segnata come messa: la domanda è proprio questa (#639)
        return F("n.t_non_messa"), F("n.non_messa_tra_un_ora" if un_ora else "n.non_messa_ultimi_minuti", giornata=g, ora=ora)
    if isinstance(esito, list) and esito:          # titolari a rischio: il loro stato vero, «A è infortunato e B è squalificato»
        motivi = [F("n.m_" + stato, nome=chi) for _, chi, stato in esito]
        return (F("n.t_titolare_rischio" if len(esito) == 1 else "n.t_titolari_rischio"),
                F("n.rischio_schierata" if schierata else "n.rischio_salvata", motivi=_elenco(motivi, 2), giornata=g, ora=ora))
    if esito == SOLO_SCADENZA:                     # formazione schierata, titolari già detti dal «cambio pronto»: solo l'ora
        return (F("n.t_un_ora" if un_ora else "n.t_ultimi_minuti"),
                F("n.tra_un_ora" if un_ora else "n.solo_scadenza", giornata=g, ora=ora))
    non_valida = esito == NON_VALIDA
    titolo = F("n.t_non_valida") if non_valida else F("n.t_un_ora" if un_ora else "n.t_ultimi_minuti")
    if not un_ora:
        return titolo, F("n.non_valida_ultimi_minuti" if non_valida else "n.ultimi_minuti", giornata=g, ora=ora)
    parti = [F("n.non_valida_tra_un_ora" if non_valida else "n.tra_un_ora", giornata=g, ora=ora)]
    try:
        f = consigli.formazione(db, regole, rose, giornata=giornata, adesso=adesso)
        dubbi = [x["nome"] for x in f["titolari"] if x["titolarita"] != "titolare" or x["dubbio"]][:4]
        parti.append(F("n.consigliato", modulo=f["modulo"], punti=float(f["punteggio_atteso"])))
        if dubbi:
            parti.append(F("n.da_controllare", nomi=", ".join(dubbi)))
    except ValueError:                             # nessuna formazione possibile con la rosa: non è un guasto, parte senza dettagli
        pass
    except Exception as e:                         # noqa: BLE001  (il promemoria parte comunque, anche senza i dettagli)
        segna_guasto(guasti, "promemoria senza i dettagli della formazione", e)
    return titolo, frasi.elenco(parti, sep=" ")


def _fatti_detti(voce) -> dict[str, str]:
    """I fatti già detti dal «cambio pronto» per una giornata, «codice/motivo» -> quando (campo `detti` dello stato dei cambi)."""
    detti = voce.get("detti") if isinstance(voce, dict) else None
    return {str(k): str(v) for k, v in detti.items()} if isinstance(detti, dict) else {}


def _fatti_da_poco(file_cambi: Path, chiave: str, adesso: datetime) -> set[str]:
    """I fatti («codice/motivo») che il «cambio pronto» ha detto negli ultimi DOPPIONE_PROMEMORIA minuti per la giornata `chiave`."""
    tutti = _json(file_cambi).get("cambi")
    voce = tutti.get(chiave) if isinstance(tutti, dict) else None
    return {k for k, quando in _fatti_detti(voce).items() if _da_poco(quando, adesso, DOPPIONE_PROMEMORIA)}


def testi_promemoria(db: sqlite3.Connection, regole: Regole, rose: Rose, stagione: str, giornata: int, scadenza: datetime | None,
                     file_scelte: Path | None, adesso: datetime | None = None, lingua: str = LINGUA_PREDEFINITA,
                     guasti: list[str] | None = None) -> list[dict]:
    """I due promemoria della giornata come li scriverebbe adesso il giro del server, nella `lingua` degli avvisi:
    [{"minuti": 60, "titolo", "testo"}, {"minuti": 15, "titolo", "testo"}]. `scadenza`: quando si chiude la formazione, quella
    che mostra Oggi (la stessa regola del giro: prima partita meno i minuti della lega); None se non si sa. La lista vuota se il
    promemoria non serve (la regola di `serve_promemoria`) o la scadenza non si sa. Come `serve_promemoria` non guarda l'ora né le
    finestre, e nemmeno i doppioni con il «cambio pronto» (li toglie il giro che manda). È il campo `testi_promemoria` di
    GET /api/oggi: l'iPhone mostra questi testi nei suoi promemoria locali invece di comporne di suoi (#906)."""
    adesso = adesso or datetime.now()
    inizio = scadenza
    if inizio is None:
        return []
    esito, schierata = _situazione(db, regole, rose, stagione, giornata, file_scelte)
    if esito == []:
        return []
    testi = []
    for nome, *_ in FINESTRE:
        titolo, testo = _testo_promemoria(db, regole, rose, giornata, nome, inizio, adesso, esito, schierata, guasti)
        testi.append({"minuti": int(nome), "titolo": frasi.testo(titolo, lingua), "testo": frasi.testo(testo, lingua)})
    return testi


def promemoria(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_PROMEMORIA,
               manda: Callable[..., bool] = invia, opzioni: dict | None = None, file_scelte: Path | None = None,
               guasti: list[str] | None = None, file_cambi: Path | None = None) -> list[str]:
    """Un avviso un'ora prima e uno un quarto d'ora prima della scadenza della formazione (la prima partita della giornata meno i
    minuti della regola della lega; una volta sola ciascuno), per tutti: le vecchie scelte `promemoria_60` e `promemoria_15` non
    contano più (#676); `opzioni` resta per chi chiama (le ore tranquille le guarda `manda`).
    Se hai già schierato (scelta salvata che si può ancora schierare, e messa: `_gia_schierato`) e nessuno dei tuoi titolari è
    diventato indisponibile, non ti disturba; se qualcuno lo è diventato, l'avviso parte e lo dice. Quando tace non segna niente
    come mandato: se più tardi cambia qualcosa, parte ancora.
    Un solo avviso per lo stesso fatto (#906): un titolare che il «cambio pronto» ha detto negli ultimi DOPPIONE_PROMEMORIA minuti
    con lo stesso stato non si ripete. Il richiamo della scadenza parte sempre: se non resta nessun titolare da dire, il promemoria
    dice solo l'ora (e chiede della spunta «L'ho messa» se manca). `file_cambi`: lo stato del giro dei cambi (di base
    `notifiche.json` accanto a `file_stato`).
    Se i dettagli della formazione non si calcolano il promemoria parte senza, e il guasto va in `guasti` o nel registro."""
    from . import consigli
    adesso = adesso or datetime.now()
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole, adesso)     # l'ora del giro, non l'orologio vero
    if giornata is None:
        return []
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)     # la scadenza, non l'inizio della partita
    if inizio is None or inizio <= adesso:
        return []
    minuti = (inizio - adesso).total_seconds() / 60
    file_cambi = file_cambi or file_stato.with_name(FILE_STATO.name)
    stato = _json(file_stato)
    mandati = stato.setdefault("promemoria", [])
    inviati = []
    saltati = False
    for nome, da, a, priorita in FINESTRE:
        chiave = f"{stagione}/{giornata}/{nome}"
        if not (da < minuti <= a) or chiave in mandati:
            continue
        if _avviso_scadenza_recente(stato, f"{stagione}/{giornata}", adesso):
            mandati.append(chiave)                 # l'avviso «cambia la formazione» è appena partito e dice già l'ora: niente doppione
            saltati = True
            continue
        esito, schierata = _situazione(db, regole, rose, stagione, giornata, file_scelte)
        if esito == []:
            continue                               # hai già schierato (e messo) e va ancora bene: niente disturbo
        if isinstance(esito, list):                # chi il «cambio pronto» ha appena detto non si ripete; la scadenza sì
            detti = _fatti_da_poco(file_cambi, f"{stagione}/{giornata}", adesso)
            esito = [p for p in esito if f"{p[0]}/{p[2]}" not in detti] or (SOLO_SCADENZA if schierata else NON_MESSA)
        titolo, testo = _testo_promemoria(db, regole, rose, giornata, nome, inizio, adesso, esito, schierata, guasti)
        # se l'invio fallisce si riprova al giro dopo, finché dura la finestra; la notifica web non arriva dopo la scadenza
        if manda(titolo, testo, priorita, "alarm_clock", vale_per=inizio - adesso):
            mandati.append(chiave)
            inviati.append(testo)
    if inviati or saltati:
        stato["promemoria"] = mandati[-20:]
        scrivi_sicuro(file_stato, json.dumps(stato))
    return inviati


# ---------------------------------------------------------------- avviso intelligente prima della scadenza
def tocca_all_avviso(chiusura: datetime, adesso: datetime) -> bool:
    """Siamo nella finestra dell'avviso «cambia la formazione» (AVVISO_PRIMA_PREDEFINITO minuti prima della scadenza, per tutti)?
    Lì l'avviso dei cambi lascia parlare prima lui."""
    return 0 < (chiusura - adesso).total_seconds() / 60 <= AVVISO_PRIMA_PREDEFINITO


def _da_poco(quando, adesso: datetime, minuti: int) -> bool:
    """`quando` (data e ora in testo) è al massimo `minuti` fa?"""
    try:
        t = datetime.fromisoformat(str(quando))
    except (TypeError, ValueError):
        return False
    return 0 <= (adesso - t).total_seconds() <= minuti * 60


def _avviso_scadenza_partito(file_promemoria: Path, chiave: str, adesso: datetime, versione: str | None) -> bool:
    """L'avviso «cambia la formazione» è partito negli ultimi DOPPIONE_CAMBI minuti con i dati di adesso (quindi sapeva già
    questa notizia)? Con dati più nuovi di quelli dell'avviso, no: la notizia è nuova e va detta."""
    stato = _json(file_promemoria)
    voce = (stato.get("scadenza") or {}).get(chiave) if isinstance(stato.get("scadenza"), dict) else None
    return (isinstance(voce, dict) and _da_poco(voce.get("ultimo"), adesso, DOPPIONE_CAMBI)
            and voce.get("versione_inviato") == versione)


def _avviso_scadenza_recente(stato: dict, chiave: str, adesso: datetime) -> bool:
    voce = (stato.get("scadenza") or {}).get(chiave) if isinstance(stato.get("scadenza"), dict) else None
    return isinstance(voce, dict) and _da_poco(voce.get("ultimo"), adesso, DOPPIONE_PROMEMORIA)


def _versione_dati(db: sqlite3.Connection) -> str | None:
    from . import consigli
    try:
        return consigli._versione(db)                # noqa: SLF001
    except Exception:                                # noqa: BLE001  (archivio senza la tabella: si valuta ogni volta)
        return None


def _elenco(nomi: list, massimo: int = 3):
    """«A», «A e B», «A, B e C», «A, B, C e altri 2» (`Frase`, nella lingua dell'utente)."""
    nomi = [n for n in nomi if n]
    if len(nomi) > massimo:
        return F("n.elenco_altri", lista=frasi.elenco(nomi[:massimo]), n=len(nomi) - massimo)
    return frasi.elenco(nomi, con_e=True)


MOTIVI_FUORI = ("infortunato", "squalificato", "panchina", "non_citato")


def testo_avviso_scadenza(prev: pd.DataFrame, escono: list[int], entrano: list[str], modulo_prima: str | None, modulo_ora: str,
                          guadagno: float, chiusura: datetime):
    """Il motivo in una frase: «Castoldi è infortunato: metti Bonvicini e passa al 3-4-3 (+1,8 punti attesi). Si chiude alle 18:30.»"""
    motivi, senza = [], []
    for i in escono:
        nome = str(prev.at[i, "nome"]) if i in prev.index else None
        if not nome:
            continue
        stato = prev.at[i, "stato"] if "stato" in prev.columns else None
        stato = None if stato is None or pd.isna(stato) else str(stato)
        dubbio = prev.at[i, "dubbio"] if "dubbio" in prev.columns else None
        dubbio = False if dubbio is None or pd.isna(dubbio) else bool(dubbio)
        if stato in MOTIVI_FUORI:
            motivi.append(F("n.m_" + stato, nome=nome))
        elif dubbio:
            motivi.append(F("n.m_dubbio", nome=nome))
        else:
            senza.append(nome)
    if motivi:
        frase = F("n.metti", motivi=_elenco(motivi, 2), entrano=_elenco(entrano))
    elif entrano:
        frase = F("n.conviene_al_posto", entrano=_elenco(entrano), senza=_elenco(senza)) if senza else F("n.conviene", entrano=_elenco(entrano))
    else:
        frase = F("n.altra_formazione")
    if modulo_prima and modulo_prima != modulo_ora:
        frase = F("n.e_passa", frase=frase, modulo=modulo_ora)
    return F("n.testo_scadenza", frase=frase, punti=float(guadagno), ora=f"{chiusura:%H:%M}")


def avviso_scadenza(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_PROMEMORIA,
                    manda: Callable[..., bool] = invia, opzioni: dict | None = None, file_scelte: Path | None = None,
                    file_cambi: Path = FILE_STATO) -> list[str]:
    """Avviso intelligente: da AVVISO_PRIMA_PREDEFINITO minuti prima della scadenza della formazione (per tutti: la vecchia scelta
    `avviso_prima` non conta più, #676), se le ultime probabili cambiano il consiglio rispetto a quello di riferimento, un avviso con
    il motivo in una frase (il tocco apre la Formazione). Di `opzioni` contano solo le ore tranquille.

    Riferimento: la formazione che hai salvato per la giornata (scelta o «ho schierato la consigliata»), se si può ancora schierare
    (regola unica della scelta, come la Formazione); senza, o se non vale più, la consigliata com'era
    prima che si aprisse la finestra (l'ultima calcolata dall'avviso dei cambi, `file_cambi`). Avvisa solo se la consigliata di adesso
    vale almeno SOGLIA_AVVISO_PUNTI punti attesi più del riferimento ricalcolato con i dati nuovi; al massimo MAX_AVVISI_SCADENZA per
    giornata, mai due volte lo stesso consiglio. Ricalcola solo quando i dati (o la tua scelta) sono cambiati dall'ultima volta.
    Nelle ore tranquille o se l'invio fallisce non segna niente: si riprova al giro dopo, finché la finestra è aperta."""
    from . import consigli, scelte
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    prima = AVVISO_PRIMA_PREDEFINITO
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole, adesso)     # l'ora del giro, non l'orologio vero
    if giornata is None:
        return []
    chiusura = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
    if chiusura is None or chiusura <= adesso:
        return []
    minuti = (chiusura - adesso).total_seconds() / 60
    chiave = f"{stagione}/{giornata}"
    stato = _json(file_stato)
    tutti = stato.get("scadenza") if isinstance(stato.get("scadenza"), dict) else {}
    mio = tutti.get(chiave) if isinstance(tutti.get(chiave), dict) else {}
    snap = (_json(file_cambi).get("cambi") or {}).get(chiave) or {}

    def salva() -> None:
        tutti[chiave] = mio
        for vecchia in chiavi_vecchie(tutti, 6):
            tutti.pop(vecchia, None)
        stato["scadenza"] = tutti
        scrivi_sicuro(file_stato, json.dumps(stato))

    if minuti > prima:                             # prima della finestra: si ricorda la consigliata di adesso (costa solo una lettura)
        rif = sorted(int(i) for i in snap.get("titolari") or [])
        if rif and rif != mio.get("rif"):
            mio["rif"] = rif
            salva()
        return []
    if minuti < MINUTI_MINIMI or int(mio.get("mandati", 0)) >= MAX_AVVISI_SCADENZA or in_silenzio(adesso, opzioni):
        return []
    scelta = scelte.leggi(stagione, giornata, file_scelte)
    if scelta:                                     # conta solo se si può ancora schierare: se no è come non averla salvata
        try:
            prev, _, _ = consigli.previsioni(db, regole, giornata)
        except ValueError:                         # senza previsioni non c'è nessun consiglio da confrontare
            return []
        scelta = scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole)
    rif = sorted(int(i) for i in (scelta["titolari"] if scelta else mio.get("rif") or []))
    versione = _versione_dati(db)
    firma_giro = f"{versione}|{','.join(map(str, rif))}"
    if versione is not None and firma_giro == mio.get("valutato"):
        return []                                  # niente di nuovo dall'ultima volta: niente calcoli
    try:
        f = consigli.formazione(db, regole, rose, giornata=giornata, adesso=adesso)     # la giornata e l'ora del giro
    except ValueError:
        return []
    ora = sorted(int(x["id"]) for x in f["titolari"])
    if not rif:                                    # nessun riferimento (per esempio avviso dei cambi spento): da qui in poi si confronta
        mio |= {"rif": ora, "valutato": firma_giro}
        salva()
        return []
    if set(rif) == set(ora) or ",".join(map(str, ora)) in mio.get("firme", []):
        mio["valutato"] = firma_giro
        salva()
        return []
    try:
        v = consigli.valuta(db, regole, rose, rif, giornata=giornata, adesso=adesso)
    except ValueError:                             # il riferimento non è più valido (un giocatore non è più nella rosa)
        if not scelta:
            mio |= {"rif": ora, "valutato": firma_giro}
            salva()
        return []
    guadagno = float(f["punteggio_atteso"]) - float(v["punteggio_atteso"])
    if guadagno < SOGLIA_AVVISO_PUNTI:
        mio["valutato"] = firma_giro               # cambio piccolo: non vale un avviso
        salva()
        return []
    prev, _, _ = consigli.previsioni(db, regole, giornata)
    nomi = {int(x["id"]): x.get("nome") for x in f["titolari"]}
    entrano = [nomi[i] for i in ora if i not in rif]
    escono = [i for i in rif if i not in ora]
    testo = testo_avviso_scadenza(prev, escono, entrano, v.get("modulo"), f["modulo"], guadagno, chiusura)
    titolo = F("n.t_cambia") if scelta else F("n.t_cambia_consigliata")
    firme = list(mio.get("firme", [])) + [",".join(map(str, ora))]
    if _da_poco(snap.get("inviato"), adesso, DOPPIONE_CAMBI):
        # l'avviso sui cambi delle probabili dei tuoi giocatori è appena partito con la stessa notizia: questo consiglio non si ripete
        mio |= {"firme": firme, "valutato": firma_giro} | ({} if scelta else {"rif": ora, "valutato": f"{versione}|{','.join(map(str, ora))}"})
        salva()
        return []
    # il tocco apre la Formazione; ore tranquille o invio fallito: si riprova. La notifica web non arriva dopo la scadenza
    if not manda(titolo, testo, 4, "rotating_light", vale_per=chiusura - adesso):
        return []
    mio |= {"mandati": int(mio.get("mandati", 0)) + 1, "firme": firme,
            "ultimo": adesso.isoformat(timespec="seconds"), "versione_inviato": versione, "valutato": firma_giro}
    if not scelta:                                 # da qui il riferimento è il consiglio appena mandato
        mio |= {"rif": ora, "valutato": f"{versione}|{','.join(map(str, ora))}"}
    salva()
    return [testo]

