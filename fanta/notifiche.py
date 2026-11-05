"""Avvisi sul telefono (ntfy) per le decisioni della formazione.

- cambi: dopo ogni aggiornamento dei dati si confronta lo stato dei TUOI giocatori (titolare, panchina, infortunato, squalificato,
  in dubbio) con quello dell'aggiornamento precedente e si avvisa solo se cambia qualcosa che conta;
- promemoria: un'ora e un quarto d'ora prima della prima partita della giornata (quando si chiude la formazione).

Il canale ntfy sta nella variabile FANTA_CANALE_AVVISI (o FANTA_NTFY_CANALE) oppure nel file dati/canale-avvisi.txt. I testi contengono i nomi dei calciatori:
passano dal server pubblico ntfy.sh e il nome del canale fa da password.

Lingua: titolo e testo sono `Frase` (fanta/frasi.py, inglese in fanta/frasi_avvisi.py); `invia` li scrive nella lingua scelta
dall'utente nelle impostazioni degli avvisi (`lingua`, "it" o "en", predefinito italiano).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from . import avvisi, frasi, osservati
from .frasi import F
from .lega import Rose
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .regole import Regole

LOG = logging.getLogger(__name__)
FILE_STATO = RADICE / "dati" / "notifiche.json"
FILE_PROMEMORIA = RADICE / "dati" / "notifiche-promemoria.json"      # file separato: cambi e promemoria girano da script diversi
FILE_IMPOSTAZIONI = RADICE / "dati" / "avvisi-impostazioni.json"
FILE_RIEPILOGO = RADICE / "dati" / "notifiche-riepilogo.json"
LINGUE = ("it", "en")
LINGUA_PREDEFINITA = "it"
IMPOSTAZIONI_PREDEFINITE = {"cambi": True, "promemoria_60": True, "promemoria_15": True, "riepilogo": True, "app_nativa": False,
                            "silenzio": False, "copertura": True}
CAMPI_UTENTE = ("primo_avvio", "backup_il", "mostra_tutte")    # altri campi dello stesso file, gestiti da stato_utente.py
BLOCCO_FILE = threading.Lock()
ORE_PREDEFINITE = {"silenzio_da": 23, "silenzio_a": 7}      # ore tranquille: dalle 23 alle 7 (se "silenzio" è acceso)
# a quale sezione dell'app nativa porta il tocco sull'avviso ntfy (schema schieraxi://, vedi l'app iOS); quel che non è qui apre Lega
SEZIONE_PER_TAG = {"rotating_light": "formazione", "alarm_clock": "formazione", "bar_chart": "oggi", "unlock": "mercato", "no_entry": "mercato"}
FUORI = ("infortunato", "squalificato")
# un titolare delle probabili sotto questa percentuale della fonte è «in ballottaggio» (come consigli.PERC_BALLOTTAGGIO): l'avviso
# scatta quando la passa, in su o in giù, e lo dice a parole (all'utente si mostra una sola percentuale, «gioca N%»)
PERC_BALLOTTAGGIO = 60
MAX_RIGHE = 8
FINESTRE = [("60", 45, 65, "promemoria_60", 3), ("15", 4, 20, "promemoria_15", 4)]   # (nome, da minuti, a minuti, opzione, priorità)
# avviso intelligente prima della scadenza (vedi `avviso_scadenza`)
MINUTI_AVVISO = (0, 30, 60, 90)          # da quanti minuti prima della scadenza si guarda se il consiglio è cambiato (0 = spento)
AVVISO_PRIMA_PREDEFINITO = 60
SOGLIA_AVVISO_PUNTI = 1.0                # punti attesi in più perché valga la pena disturbare: sotto è il su e giù normale
MAX_AVVISI_SCADENZA = 2                  # al massimo per giornata
MINUTI_MINIMI = 2                        # a meno di 2 minuti dalla chiusura non serve più
DOPPIONE_PROMEMORIA = 20                 # minuti: subito dopo questo avviso il promemoria della stessa finestra non riparte
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
          file_impostazioni: Path | None = None, file_iscrizioni: Path | None = None, ntfy: bool = True) -> bool:
    """Manda l'avviso: con le notifiche web attive su almeno un dispositivo si usano quelle; altrimenti (o se non arriva a nessuno) ntfy.
    Nelle ore tranquille non parte niente e restituisce False: cambi e riepilogo allora riprovano al giro dopo, fuori dalla fascia.
    I file sono quelli dell'utente (di norma quelli di sempre); `ntfy=False` per gli utenti con un account: il canale ntfy è uno
    solo, del proprietario del server, e i nomi dei calciatori di un altro non devono finire lì."""
    from . import push
    opzioni = impostazioni(file_impostazioni)
    if not ignora_silenzio and in_silenzio(datetime.now(), opzioni):
        return False
    titolo, testo = frasi.testo(titolo, opzioni["lingua"]), frasi.testo(testo, opzioni["lingua"])      # nella lingua scelta dall'utente
    arrivato = bool(push.iscrizioni(file_iscrizioni)) and push.invia(titolo, testo, priorita, tag, file_iscrizioni) > 0
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
    except (TypeError, ValueError):
        return predefinita
    return v if 0 <= v <= 23 else predefinita


def _minuti_avviso(valore, predefinito: int) -> int:
    """Uno dei valori ammessi per `avviso_prima` (0, 30, 60, 90); altrimenti quello di prima."""
    if isinstance(valore, bool):
        return predefinito
    try:
        v = int(valore)
    except (TypeError, ValueError):
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
    if ok["silenzio"] and ok["silenzio_da"] == ok["silenzio_a"]:
        ok["silenzio"] = False      # salvate prima del controllo: inizio = fine non è una fascia, si trattano come spente
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


def in_silenzio(adesso: datetime, opzioni: dict) -> bool:
    """Siamo nelle ore tranquille scelte (per esempio dalle 23 alle 7, anche a cavallo della mezzanotte)?"""
    da, a = opzioni.get("silenzio_da", ORE_PREDEFINITE["silenzio_da"]), opzioni.get("silenzio_a", ORE_PREDEFINITE["silenzio_a"])
    if not opzioni.get("silenzio") or da == a:
        return False
    return da <= adesso.hour < a if da < a else adesso.hour >= da or adesso.hour < a


# ---------------------------------------------------------------- osservati che tornano liberi
def osservati_liberi(diff: dict, file_osservati: Path | None = None, manda: Callable[..., bool] = invia,
                     opzioni: dict | None = None) -> list[str]:
    """Dopo un'importazione delle rose: avvisa se un giocatore tra gli osservati è stato lasciato libero da una squadra
    (si può prendere dagli svincolati). `diff` è il risultato di movimenti.differenze. Restituisce le righe mandate."""
    opzioni = opzioni if opzioni is not None else impostazioni()
    if not opzioni.get("cambi", True):
        return []
    seguiti = set(osservati.leggi(file_osservati))
    righe = [F("n.osservato_libero", nome=g["nome"], ruolo=g.get("ruolo") or "?", squadra=t["squadra"])
             for t in diff.get("tagliati", []) for g in t.get("giocatori", []) if g.get("id") in seguiti]
    if righe and manda(F("n.t_osservato_libero"), frasi.elenco(righe[:MAX_RIGHE], sep="\n"), 3, "unlock"):
        return righe
    return []


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
    """«Cambio pronto»: per ogni tuo titolare (quello della tua scelta salvata, altrimenti il consigliato) che ora è infortunato,
    squalificato o in panchina, chi mettere al suo posto (lo stesso calcolo di «Da fare» in Oggi: solo se la consigliata lo toglie).
    Ogni cambio una volta sola: la chiave è giornata, giocatore e motivo. Senza un sostituto non c'è niente da proporre.
    `formazione`: la consigliata già calcolata da `cambi` (None = la legge «Da fare», dalla cache)."""
    from . import da_fare, scelte
    scelta = scelte.leggi(chiave.split("/")[0], giornata, file_scelte)
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
        try:
            d = float(alt["punti_attesi"]) - float(prev.at[i, "atteso"])
            if d > 0.05:
                consiglio = F("n.meglio_guadagno", alt=alt["nome"], punti=d)
        except (KeyError, TypeError, ValueError):
            pass
        risultato.append({"nome": nome, "chiave": f"{chiave}/{i}/{nuovi[i]}", "frase": F("n.tuo_" + nuovi[i], nome=nome),
                          "consiglio": consiglio})
    return risultato


def cambi(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_STATO,
          manda: Callable[..., bool] = invia, opzioni: dict | None = None, file_osservati: Path | None = None,
          risparmia: bool = False, file_scelte: Path | None = None, file_promemoria: Path | None = None) -> list[str]:
    """Confronta lo stato dei tuoi giocatori (e di quelli che osservi) con quello dell'ultimo controllo e avvisa se è cambiato
    qualcosa. Restituisce le righe.
    Vicino alla scadenza (finestra dell'avviso «cambia la formazione») prova prima quell'avviso; i cambi dei tuoi giocatori tacciono
    solo se è partito davvero, con i dati di adesso, negli ultimi DOPPIONE_CAMBI minuti. Se non parte (già due avvisi, guadagno
    piccolo...) i cambi si dicono come sempre: nessuna notizia va persa. `file_promemoria`: lo stato di quell'avviso (di base il
    file `notifiche-promemoria.json` accanto a `file_stato`).
    `risparmia` (per chi ha molti utenti da controllare): il confronto degli stati costa poco, la formazione consigliata molto;
    se non è cambiato niente si tiene quella dell'ultimo controllo invece di ricalcolarla."""
    from . import consigli
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    ids = _mia_rosa_ids(rose)
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole)
    if not ids or giornata is None:
        return []
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
    if inizio is None or inizio <= adesso:
        return []                                  # la formazione si è già chiusa: i cambi non servono più
    prev, giornata, con_probabili = consigli.previsioni(db, regole)
    if not con_probabili:
        return []                                  # senza probabili non c'è niente da confrontare
    ids_oss = [i for i in osservati.leggi(file_osservati) if i not in ids]
    ora = istantanea(prev, ids + ids_oss)
    chiave = f"{stagione}/{giornata}"
    stato = _json(file_stato)
    vecchio = stato.get("cambi", {}).get(chiave)
    chiavi_oss = {str(i) for i in ids_oss}
    righe, oss = [], []
    if vecchio:
        righe = confronta({k: v for k, v in vecchio["giocatori"].items() if k not in chiavi_oss}, {k: v for k, v in ora.items() if k not in chiavi_oss})
        oss = [F("n.osservato_riga", riga=r) for r in confronta({k: v for k, v in vecchio["giocatori"].items() if k in chiavi_oss}, {k: v for k, v in ora.items() if k in chiavi_oss})]
    if risparmia and vecchio and vecchio.get("titolari") and not righe and not oss and set(vecchio["giocatori"]) == set(ora):
        f, titolari = None, vecchio["titolari"]    # niente è cambiato: la formazione di prima vale ancora
    else:
        try:
            f = consigli.formazione(db, regole, rose)
            titolari = sorted(int(x["id"]) for x in f["titolari"])
        except ValueError:                         # per esempio nessun portiere disponibile: l'avviso sui cambi serve proprio ora
            f, titolari = None, []
    if righe and vecchio and f and vecchio.get("titolari") != titolari:
        entrano = [prev.at[i, "nome"] for i in set(titolari) - set(vecchio["titolari"]) if i in prev.index]
        escono = [prev.at[i, "nome"] for i in set(vecchio["titolari"]) - set(titolari) if i in prev.index]
        righe.append(F("n.formazione_aggiornata", modulo=f["modulo"], entrano=", ".join(entrano) or "–", escono=", ".join(escono) or "–"))
    pronti = _cambi_pronti(db, regole, rose, prev, ora, titolari, giornata, set(stato.get("pronti", [])), chiave, file_scelte, f) \
        if opzioni.get("cambi", True) else []
    singoli = []                                   # un cambio pronto che ha già una riga nell'avviso dei cambi la completa; gli altri vanno da soli
    for p in pronti:
        k = next((n for n, r in enumerate(righe) if r.startswith(p["nome"] + ":")), None)
        if k is None:
            singoli.append(p)
        else:
            righe[k] = F("n.riga_consiglio", riga=righe[k], consiglio=p["consiglio"])
    gia_detti = []
    if (righe or singoli) and tocca_all_avviso(inizio, adesso, opzioni):
        file_promemoria = file_promemoria or file_stato.with_name(FILE_PROMEMORIA.name)
        try:                                       # prima l'avviso «cambia la formazione», con i dati appena arrivati
            gia_detti = avviso_scadenza(db, regole, rose, adesso, file_promemoria, manda, opzioni, file_scelte, file_stato)
        except Exception:                          # noqa: BLE001  (i cambi partono comunque)
            gia_detti = []
        if _avviso_scadenza_partito(file_promemoria, chiave, adesso, _versione_dati(db)):
            righe, singoli = [], []                # l'ha già detto lui (niente doppioni); lo stato si salva lo stesso, così questi
            #                                        cambi non ripartono più tardi
    proprie = bool(righe or singoli)
    righe = righe + oss                            # i giocatori che osservi vengono dopo i tuoi, con la stella
    cambi_mandato = False
    if righe and opzioni.get("cambi", True):
        visibili = righe[:MAX_RIGHE]
        if len(righe) > MAX_RIGHE:
            visibili.append(F("n.altre_novita", n=len(righe) - MAX_RIGHE))
        if not manda(F("n.t_cambi", giornata=giornata), frasi.elenco(visibili, sep="\n"), 4, "rotating_light"):
            return righe                           # invio fallito: lo stato resta quello vecchio e al prossimo giro si riprova
        cambi_mandato = True
    if singoli:
        testi = [F("n.frase_consiglio", frase=p["frase"], consiglio=p["consiglio"]) for p in singoli[:MAX_RIGHE]]
        if not manda(F("n.t_cambio_pronto"), frasi.elenco(testi, sep="\n"), 4, "rotating_light"):   # il tocco apre la Formazione
            if not cambi_mandato:
                return righe                       # ore tranquille o invio fallito: si riprova al giro dopo
            pronti = [p for p in pronti if p not in singoli]     # l'avviso dei cambi è già partito: lo stato si salva (niente doppioni), il «cambio pronto» riprova
    if pronti:
        stato["pronti"] = (list(stato.get("pronti", [])) + [p["chiave"] for p in pronti])[-80:]
    cambi_stato = stato.setdefault("cambi", {})
    # quando è partito l'ultimo avviso sui TUOI giocatori: l'avviso «cambia la formazione» non lo ripete (DOPPIONE_CAMBI)
    inviato = adesso.isoformat(timespec="seconds") if proprie and (cambi_mandato or singoli) else (vecchio or {}).get("inviato")
    cambi_stato[chiave] = {"giocatori": ora, "titolari": titolari} | ({"inviato": inviato} if inviato else {})
    for vecchia in chiavi_vecchie(cambi_stato, 6):
        cambi_stato.pop(vecchia, None)
    scrivi_sicuro(file_stato, json.dumps(stato))
    return gia_detti + righe + [F("n.frase_consiglio", frase=p["frase"], consiglio=p["consiglio"]) for p in singoli]


# ---------------------------------------------------------------- copertura della rosa
def copertura(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_STATO,
              manda: Callable[..., bool] = invia, opzioni: dict | None = None) -> list[str]:
    """Avvisa (facoltativo) se un reparto della tua rosa è scoperto o senza ricambi per la prossima giornata, finché la formazione è
    aperta. Ogni situazione una volta sola (giornata, reparto, gravità); nelle ore tranquille non segna niente e riprova al giro dopo."""
    from . import consigli, copertura as cop
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    if not opzioni.get("copertura", True):
        return []
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole)      # la giornata della lega, come cambi e promemoria
    if giornata is None:
        return []
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)     # la scadenza, non l'inizio della partita
    if inizio is None or inizio <= adesso:
        return []
    prev, giornata, _ = consigli.previsioni(db, regole)
    r = cop.analizza(prev, regole, rose, opzioni.get("lingua", LINGUA_PREDEFINITA))          # il testo del reparto è già nella lingua dell'utente
    stato = _json(file_stato)
    gia = set(stato.get("copertura", []))
    nuovi = [(f"{stagione}/{giornata}/{x['ruolo'] or 'moduli'}/{x['livello']}", x) for x in (r or {}).get("reparti", [])]
    nuovi = [(k, x) for k, x in nuovi if k not in gia]
    if not nuovi:
        return []
    scoperti = any(x["livello"] == cop.SCOPERTO for _, x in nuovi)
    titolo = F("n.t_reparto_scoperto") if scoperti else F("n.t_reparto_rischio")
    righe = [x["testo"] for _, x in nuovi]
    if not manda(titolo, "\n".join(righe), 4 if scoperti else 3, "no_entry"):
        return righe                                   # ore tranquille o invio fallito: si riprova al giro dopo
    stato["copertura"] = (list(stato.get("copertura", [])) + [k for k, _ in nuovi])[-40:]
    scrivi_sicuro(file_stato, json.dumps(stato))
    return righe


# ---------------------------------------------------------------- promemoria prima della scadenza
def _gia_schierato(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, file_scelte: Path | None) -> list[str] | None:
    """None se non hai ancora schierato (nessuna scelta salvata, né «ho schierato la consigliata»). Altrimenti la lista, anche vuota,
    dei titolari che hai schierato e che ora risultano fuori, in panchina o non citati nelle probabili."""
    from . import consigli, scelte
    scelta = scelte.leggi(stagione, giornata, file_scelte)
    if not scelta:
        return None
    try:
        prev, _, _ = consigli.previsioni(db, regole, giornata)
    except Exception:                              # senza previsioni non so dire se è cambiato qualcosa: lo considero a posto
        return []
    problemi = []
    for i in scelta["titolari"]:
        if i in prev.index and prev.at[i, "stato"] in FUORI + ("panchina", "non_citato"):
            problemi.append(str(prev.at[i, "nome"]))
    return problemi


def promemoria(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_PROMEMORIA,
               manda: Callable[..., bool] = invia, opzioni: dict | None = None, file_scelte: Path | None = None) -> list[str]:
    """Un avviso un'ora prima e uno un quarto d'ora prima della scadenza della formazione (la prima partita della giornata meno i
    minuti della regola della lega; una volta sola ciascuno).
    Se hai già schierato (scelta salvata) e nessuno dei tuoi titolari è diventato indisponibile, non ti disturba; se qualcuno lo è
    diventato, l'avviso parte e lo dice. Quando tace non segna niente come mandato: se più tardi cambia qualcosa, parte ancora."""
    from . import consigli
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole)
    if giornata is None:
        return []
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)     # la scadenza, non l'inizio della partita
    if inizio is None or inizio <= adesso:
        return []
    minuti = (inizio - adesso).total_seconds() / 60
    stato = _json(file_stato)
    mandati = stato.setdefault("promemoria", [])
    inviati = []
    saltati = False
    for nome, da, a, opzione, priorita in FINESTRE:
        chiave = f"{stagione}/{giornata}/{nome}"
        if not (da < minuti <= a) or chiave in mandati or not opzioni.get(opzione, True):
            continue
        if _avviso_scadenza_recente(stato, f"{stagione}/{giornata}", adesso):
            mandati.append(chiave)                 # l'avviso «cambia la formazione» è appena partito e dice già l'ora: niente doppione
            saltati = True
            continue
        ora_chiusura = inizio.strftime("%H:%M")
        problemi = _gia_schierato(db, regole, stagione, giornata, file_scelte)
        if problemi is not None and not problemi:
            continue                               # hai già schierato e va ancora bene: niente disturbo
        if problemi:
            testo = F("n.rischio", n=len(problemi[:4]), nomi=", ".join(problemi[:4]), giornata=giornata, ora=ora_chiusura)
            titolo = F("n.t_titolare_rischio")
        elif nome == "60":
            parti = [F("n.tra_un_ora", giornata=giornata, ora=ora_chiusura)]
            try:
                f = consigli.formazione(db, regole, rose)
                dubbi = [x["nome"] for x in f["titolari"] if x["titolarita"] != "titolare" or x["dubbio"]][:4]
                parti.append(F("n.consigliato", modulo=f["modulo"], punti=float(f["punteggio_atteso"])))
                if dubbi:
                    parti.append(F("n.da_controllare", nomi=", ".join(dubbi)))
            except Exception:                      # il promemoria parte comunque, anche senza i dettagli della formazione
                pass
            testo = frasi.elenco(parti, sep=" ")
            titolo = F("n.t_un_ora")
        else:
            testo = F("n.ultimi_minuti", giornata=giornata, ora=ora_chiusura)
            titolo = F("n.t_ultimi_minuti")
        if manda(titolo, testo, priorita, "alarm_clock"):      # se l'invio fallisce si riprova al giro dopo, finché dura la finestra
            mandati.append(chiave)
            inviati.append(testo)
    if inviati or saltati:
        stato["promemoria"] = mandati[-20:]
        scrivi_sicuro(file_stato, json.dumps(stato))
    return inviati


# ---------------------------------------------------------------- avviso intelligente prima della scadenza
def tocca_all_avviso(chiusura: datetime, adesso: datetime, opzioni: dict) -> bool:
    """Siamo nella finestra dell'avviso «cambia la formazione» (acceso)? Lì i cambi dei tuoi giocatori li dice solo lui."""
    prima = _minuti_avviso(opzioni.get("avviso_prima", AVVISO_PRIMA_PREDEFINITO), AVVISO_PRIMA_PREDEFINITO)
    return bool(prima) and 0 < (chiusura - adesso).total_seconds() / 60 <= prima


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
    """Avviso intelligente: da `avviso_prima` minuti (30, 60 o 90; 0 = spento) prima della scadenza della formazione, se le ultime
    probabili cambiano il consiglio rispetto a quello di riferimento, un avviso con il motivo in una frase (il tocco apre la Formazione).

    Riferimento: la formazione che hai salvato per la giornata (scelta o «ho schierato la consigliata»); senza, la consigliata com'era
    prima che si aprisse la finestra (l'ultima calcolata dall'avviso dei cambi, `file_cambi`). Avvisa solo se la consigliata di adesso
    vale almeno SOGLIA_AVVISO_PUNTI punti attesi più del riferimento ricalcolato con i dati nuovi; al massimo MAX_AVVISI_SCADENZA per
    giornata, mai due volte lo stesso consiglio. Ricalcola solo quando i dati (o la tua scelta) sono cambiati dall'ultima volta.
    Nelle ore tranquille o se l'invio fallisce non segna niente: si riprova al giro dopo, finché la finestra è aperta."""
    from . import consigli, scelte
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    prima = _minuti_avviso(opzioni.get("avviso_prima", AVVISO_PRIMA_PREDEFINITO), AVVISO_PRIMA_PREDEFINITO)
    if not prima:
        return []
    stagione = consigli.stagione_corrente()
    giornata = consigli.giornata_da_giocare(db, stagione, regole)
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
    rif = sorted(int(i) for i in (scelta["titolari"] if scelta else mio.get("rif") or []))
    versione = _versione_dati(db)
    firma_giro = f"{versione}|{','.join(map(str, rif))}"
    if versione is not None and firma_giro == mio.get("valutato"):
        return []                                  # niente di nuovo dall'ultima volta: niente calcoli
    try:
        f = consigli.formazione(db, regole, rose)
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
        v = consigli.valuta(db, regole, rose, rif)
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
    prev, _, _ = consigli.previsioni(db, regole)
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
    if not manda(titolo, testo, 4, "rotating_light"):    # il tocco apre la Formazione; ore tranquille o invio fallito: si riprova
        return []
    mio |= {"mandati": int(mio.get("mandati", 0)) + 1, "firme": firme,
            "ultimo": adesso.isoformat(timespec="seconds"), "versione_inviato": versione, "valutato": firma_giro}
    if not scelta:                                 # da qui il riferimento è il consiglio appena mandato
        mio |= {"rif": ora, "valutato": f"{versione}|{','.join(map(str, ora))}"}
    salva()
    return [testo]


# ---------------------------------------------------------------- riepilogo a giornata finita
def riepilogo(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_stato: Path = FILE_RIEPILOGO,
              manda: Callable[..., bool] = invia, opzioni: dict | None = None, file_cambi: Path = FILE_STATO,
              file_scelte: Path | None = None) -> list[str]:
    """Quando una giornata è finita e i voti sono arrivati: quanti punti ha fatto la formazione che avevi (la tua scelta salvata,
    altrimenti la consigliata), quanti se ne aspettava il modello e il massimo possibile con la tua rosa. Una volta per giornata."""
    from datetime import timedelta
    from . import consigli, scelte, verifica
    from . import formazione as fz
    from .punteggio import COLONNA_VOTO, fantavoto
    adesso = adesso or datetime.now()
    opzioni = opzioni if opzioni is not None else impostazioni()
    if not opzioni.get("riepilogo", True):
        return []
    stagione = consigli.stagione_corrente()
    r = db.execute("SELECT giornata, MAX(data) FROM partite WHERE stagione = ? AND data IS NOT NULL GROUP BY giornata "
                   "HAVING MIN(giocata) = 1 ORDER BY giornata DESC LIMIT 1", (stagione,)).fetchone()
    if not r:
        return []
    giornata = r[0]
    try:
        ultima = datetime.fromisoformat(str(r[1])[:16].replace("T", " "))
    except ValueError:
        return []
    chiave = f"{stagione}/{giornata}"
    stato = _json(file_stato)
    fatti = stato.setdefault("riepilogo", [])
    if chiave in fatti or not timedelta(0) < adesso - ultima <= timedelta(days=6):
        return []
    righe_voti = [dict(x) for x in db.execute("SELECT * FROM voti WHERE stagione = ? AND giornata = ?", (stagione, giornata))]
    if len(righe_voti) < 60:
        return []                                  # i voti non sono ancora arrivati
    scelta = scelte.leggi(stagione, giornata, file_scelte)
    snap = _json(file_cambi).get("cambi", {}).get(chiave)
    if scelta:
        ids, fonte = scelta["titolari"], F("n.fonte_scelta")
    elif snap and snap.get("titolari"):
        ids, fonte = snap["titolari"], F("n.fonte_consigliata")
    else:
        return []                                  # non so cosa avevi schierato
    prev, _, _ = consigli.previsioni(db, regole, giornata)
    squadra = rose.squadra(rose.mia_squadra or "")
    if not squadra:
        return []
    lista = [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]),
                          float(prev.at[i, "mu_voto"])) for i in (g.id for g in squadra.giocatori if g.id is not None) if i in prev.index]
    per_id = {g.id: g for g in lista}
    if any(i not in per_id for i in ids):
        return []
    fv_vero, voto_vero = {}, {}
    for v in righe_voti:
        i = int(v["calciatore_id"])
        fv = fantavoto(v, v["ruolo"], regole) if i in per_id else None
        if fv is not None:
            fv_vero[i], voto_vero[i] = fv, v[COLONNA_VOTO[regole.fonte_voto]]
    gioca = {g.id: g.id in fv_vero for g in lista}
    tit = [per_id[i] for i in ids]
    pan = fz._panchina(lista, tit, regole)
    punti = fz.punteggio(tit, pan, gioca, {g.id: fv_vero.get(g.id, 0.0) for g in lista}, {g.id: voto_vero.get(g.id, 0.0) for g in lista}, regole)
    attesi = fz.Valutatore(lista, regole, 600).atteso(tit, pan)
    massimo = verifica._perfetta(lista, fv_vero, regole)
    parti = [F("n.riepilogo", giornata=giornata, fonte=fonte, punti=float(punti), attesi=float(attesi), massimo=float(massimo))]
    migliori = sorted((t for t in tit if gioca[t.id]), key=lambda t: -fv_vero[t.id])[:3]
    if migliori:
        parti.append(F("n.migliori", elenco=frasi.elenco([F("n.nome_voto", nome=t.nome, voto=float(fv_vero[t.id])) for t in migliori])))
    senza = [t.nome for t in tit if not gioca[t.id]]
    if senza:
        parti.append(F("n.senza_voto", nomi=", ".join(senza)))
    prossima = consigli.giornata_da_giocare(db, stagione, regole)
    inizio = avvisi.scadenza(avvisi.prima_partita(db, stagione, prossima), regole) if prossima else None
    if inizio:
        parti.append(F("n.prossima", giornata=prossima, data=f"{inizio:%d/%m}", ora=f"{inizio:%H:%M}"))
    testo = frasi.elenco(parti, sep=" ")
    if manda(F("n.t_riepilogo", giornata=giornata), testo, 3, "bar_chart"):
        fatti.append(chiave)
        stato["riepilogo"] = fatti[-20:]
        scrivi_sicuro(file_stato, json.dumps(stato))
    return [testo]
