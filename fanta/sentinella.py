"""Sentinella: ogni ora, sul server, rifà IN SOLA LETTURA le risposte vere dell'app per ogni utente e controlla che dicano cose
sensate (le «invarianti»). Così i difetti li trova il server, non chi usa l'app.

- Per ogni utente (con gli account: chi ha le rose; senza: l'app di sempre) chiama le stesse funzioni delle rotte `/api/oggi`,
  `/api/formazione`, `/api/scelta`, `/api/diario`, `/api/widget` e `/api/live`, senza passare dalla rete e senza scrivere niente:
  `/api/formazione` si legge con `consigli.formazione` (la rotta salverebbe la copia automatica della consigliata), i risultati in
  diretta dalla copia su file della cache del servizio (`dati/live.json`, se c'è), come li vede l'utente.
- Esito nella tabella `controlli` (una riga `sentinella_<invariante>` per invariante, più `sentinella` col riassunto): si vede in
  «Stato dei dati». I dettagli non hanno mai nomi (né di persone, né di squadre della lega, né di giocatori): solo «utente N»,
  giornata, campo e numeri (al massimo le squadre di Serie A).
- Avviso sul canale del proprietario (`~/.config/schieraxi/canale`, come gli script del server) quando un'invariante si rompe per la
  prima volta: deve risultare rotta in CONFERME giri di fila (un aggiornamento dei dati a metà non fa partire niente), un solo
  messaggio per giro, e la stessa rottura non si riavvisa finché non è rimasta a posto per RICORDA_RISOLTE.
- Storia dei giri nel file di stato (`giri`, ultimi TIENI_GIRI): una voce {quando, rotte, inviato} per ogni giro del server, anche
  senza rotture; i giri a mano (`--senza-invio`) non entrano. La legge la «giornata senza errori» (`giri_sentinella`).
Comando: `python -m fanta sentinella [--minuti N] [--senza-invio]` (script del server: `script/server/sentinella.sh`);
`python -m fanta sentinella --giri --dal ISO --al ISO` stampa i giri fra due date con il fuso, senza fare il giro.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from . import percorsi

PREFISSO = "sentinella_"
DOPO_INIZIO_PUNTEGGIO = timedelta(hours=2, minutes=30)   # una partita iniziata da più di così deve avere il punteggio
DURATA_PARTITA = timedelta(minutes=110)                   # come live.FINE_STIMATA e fasi.DURATA_PARTITA
VOTI_ENTRO = timedelta(hours=24)                          # dalla fine di una partita i voti arrivano entro un giorno
RISULTATI_ENTRO = timedelta(hours=12)                     # come consigli.MARGINE_RISULTATI: oltre, il calendario non si aggiorna
DIARIO_ENTRO = timedelta(hours=36)                        # una giornata finita con i voti entra nel diario entro un giorno e mezzo
GIORNI_INDIETRO = 14                                      # i controlli sul calendario guardano solo le ultime due settimane
TOLLERANZA_PUNTI = 0.051                                  # i punti attesi sono arrotondati a un decimale
TOLLERANZA_ORE = 0.25                                     # ore_mancanti è calcolato in un altro istante (e arrotondato)
MAX_BYTE_WIDGET = 20 * 1024                               # docs/API.md: il widget resta sotto i 20 kB
CONFERME = 2                                              # giri di fila con la stessa rottura prima di avvisare
RICORDA_RISOLTE = timedelta(hours=24)                     # una rottura già avvisata non si riavvisa prima che sia a posto da tanto
TIENI_GIRI = timedelta(days=60)                           # storia dei giri nel file di stato (la legge la «giornata senza errori»)
MAX_RIGHE_AVVISO = 6
MAX_DETTAGLIO = 600                                       # caratteri del dettaglio in «Stato dei dati»
FILE_STATO = percorsi.RADICE / "dati" / "sentinella.json"
FILE_LIVE = percorsi.RADICE / "dati" / "live.json"        # copia su file della cache della diretta, scritta dal servizio (se c'è)
NTFY = "https://ntfy.sh"

# nome -> (esito quando è rotta, cosa garantisce). «errore» = l'utente vede una cosa sbagliata; «avviso» = da guardare.
INVARIANTI: dict[str, tuple[str, str]] = {
    "risposta_in_errore": ("errore", "nessuna risposta va in errore (sarebbe un 500)"),
    "risposta_rifiutata": ("avviso", "nessuna risposta rifiuta con un messaggio (400) chi ha rose e squadra"),
    "json_non_valido": ("errore", "niente NaN, infinito o tipi che JSON non sa scrivere"),
    "numero_mancante": ("errore", "un numero dove il client se lo aspetta (punti attesi, probabilità, ore)"),
    "fuori_intervallo": ("errore", "percentuali tra 0 e 100, probabilità tra 0 e 1, fasce in ordine"),
    "data_non_valida": ("errore", "date nel formato del contratto (docs/API.md), senza fuso"),
    "formazione_non_valida": ("errore", "11 titolari diversi della rosa, un portiere, modulo ammesso, panchina senza titolari"),
    "punti_diversi": ("errore", "stessi punti attesi e modulo in Oggi, Formazione e widget"),
    "giornata_diversa": ("errore", "stessa giornata e scadenza in Oggi, Formazione e widget"),
    "scelta_non_mostrata": ("errore", "la formazione salvata per la giornata si vede in Oggi, nel widget e nella giornata in corso"),
    "scelta_ignorata": ("avviso", "la formazione salvata vale ancora (giocatori ancora in rosa, modulo ammesso)"),
    "fase_incoerente": ("errore", "fase della giornata coerente con l'orario, la scadenza e il calendario"),
    "stato_partita_incoerente": ("errore", "stato di ogni partita coerente con l'orario"),
    "giocatore_fermo": ("errore", "nella giornata in corso nessun giocatore resta «da giocare» o «attesa voti» troppo a lungo"),
    "punteggio_mancante": ("errore", "ogni partita del turno iniziata da più di 2 ore e mezza ha il punteggio"),
    "risultati_fermi": ("avviso", "il calendario segna giocate le partite finite da più di 12 ore"),
    "voti_mancanti": ("avviso", "le squadre di una partita finita hanno i voti entro 24 ore"),
    "giornata_incoerente": ("errore", "la giornata da giocare non salta avanti e non resta ferma su una giornata finita"),
    "diario_incoerente": ("errore", "il diario ha solo giornate finite, una volta sola, con 11 titolari"),
    "diario_mancante": ("avviso", "una giornata finita con i voti da più di 36 ore è nel diario"),
    "widget_troppo_grande": ("avviso", "il riassunto del widget sta sotto i 20 kB"),
}


@dataclass(frozen=True)
class Rottura:
    invariante: str
    utente: str | None            # «utente 3», «utente locale» o None (comune a tutti)
    giornata: int | None
    dettaglio: str                # senza nomi: campi, numeri, al massimo squadre di Serie A

    @property
    def chiave(self) -> str:
        return f"{self.invariante}|{self.utente or '-'}|{self.giornata if self.giornata is not None else '-'}"


# ---------------------------------------------------------------- piccoli attrezzi
def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " ")) if testo else None
    except ValueError:
        return None


def _ids(lista) -> list:
    return [g.get("id") if isinstance(g, dict) else g for g in (lista or [])]


def _ore(d: timedelta) -> str:
    return f"{d.total_seconds() / 3600:.1f} ore"


_TIPI_JSON = (str, int, float, bool, type(None))


def cammina(obj, percorso: str = "") -> Iterable[tuple[str, str | None, Any]]:
    """(percorso, chiave, valore) di ogni elemento, in profondità. Il percorso usa solo nomi di campo e indici."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{percorso}.{k}" if percorso else str(k)
            yield p, str(k), v
            yield from cammina(v, p)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield f"{percorso}[{i}]", None, v
            yield from cammina(v, f"{percorso}[{i}]")


# chiave -> (minimo, massimo) compresi
INTERVALLI = {"percentuale": (0, 100), "percentuale_dentro": (0, 100), "percentuale_tua": (0, 100), "entro_un_punto": (0, 100),
              "fascia_dichiarata": (0, 100), "p_voto": (0, 1), "p_gol": (0, 1), "p_assist": (0, 1), "p_giallo": (0, 1),
              "p_rosso": (0, 1), "quota_titolare": (0, 1), "porta_inviolata": (0, 1), "confidenza": (0, 1), "difficolta": (1, 5),
              "indice": (0, 100), "minuti_fa": (0, math.inf), "ancora_da_giocare": (0, 11), "minuti_scadenza": (0, 720)}
_PERCENTUALI_GRUPPI = ("detto", "giocato")      # dentro `precisione.gioca.gruppi[]` sono percentuali
# formati delle date (docs/API.md): ora italiana senza fuso
_MINUTI = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")                      # «AAAA-MM-GG HH:MM»
_SECONDI_T = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")             # «AAAA-MM-GGTHH:MM:SS» (scritti dal server)
_GIORNO_O_MINUTI = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")         # partita: con l'ora o solo il giorno
_QUALSIASI = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")    # «accetta la T o lo spazio, con o senza secondi»
FORMATI_DATE = {"scadenza": _MINUTI, "inizio": _MINUTI, "prepara_da": _MINUTI, "aggiornate_il": _MINUTI,
                "ultimo_aggiornamento": _SECONDI_T, "calcolata": _SECONDI_T, "salvata": _SECONDI_T,
                "data": _GIORNO_O_MINUTI, "data_partita": _GIORNO_O_MINUTI, "prima_partita": _GIORNO_O_MINUTI,
                "aggiornato_il": _QUALSIASI, "aggiornato": _QUALSIASI}


def controlla_forma(nome: str, corpo, utente: str | None, giornata: int | None) -> list[Rottura]:
    """Controlli che valgono per ogni risposta: tipi JSON, numeri finiti, intervalli e formati delle date (per nome del campo)."""
    out: list[Rottura] = []
    non_json, fuori, date = [], [], []
    for p, k, v in cammina(corpo):
        if not isinstance(v, (dict, list, tuple)) and not isinstance(v, _TIPI_JSON):
            non_json.append(f"{p} ({type(v).__name__})")
            continue
        if isinstance(v, float) and not math.isfinite(v):
            non_json.append(f"{p}={v}")
            continue
        if k is None:
            continue
        intervallo = (0, 100) if k in _PERCENTUALI_GRUPPI and ".gruppi[" in p else INTERVALLI.get(k)
        if intervallo and _num(v) and not (intervallo[0] <= v <= intervallo[1]):
            fuori.append(f"{p}={v}")
        formato = FORMATI_DATE.get(k)
        if formato and v is not None and (not isinstance(v, str) or not formato.match(v) or _data(v) is None):
            date.append(f"{p}={v!r}"[:80])
        if k == "intervallo" and isinstance(v, dict) and _num(v.get("basso")) and _num(v.get("alto")) and v["basso"] > v["alto"]:
            fuori.append(f"{p}: basso {v['basso']} > alto {v['alto']}")
    if non_json:
        out.append(Rottura("json_non_valido", utente, giornata, f"{nome}: " + ", ".join(non_json[:4])))
    if fuori:
        out.append(Rottura("fuori_intervallo", utente, giornata, f"{nome}: " + ", ".join(fuori[:4])))
    if date:
        out.append(Rottura("data_non_valida", utente, giornata, f"{nome}: " + ", ".join(date[:3])))
    return out


# ---------------------------------------------------------------- formazioni
def problemi_formazione(titolari, ruoli: dict, modulo: str | None, regole, rosa: set | None, panchina=None) -> list[str]:
    """Cosa non va in una formazione (lista vuota = va bene). `titolari`/`panchina`: id o schede; `ruoli`: {id: ruolo}."""
    from .punteggio import modulo_valido
    ids = _ids(titolari)
    p: list[str] = []
    if len(ids) != 11:
        p.append(f"{len(ids)} titolari")
    if len(set(ids)) != len(ids):
        p.append("titolari ripetuti")
    if rosa is not None and any(i not in rosa for i in ids):
        p.append(f"{sum(1 for i in ids if i not in rosa)} titolari fuori rosa")
    if len(ids) == 11 and all(i in ruoli for i in ids):
        conta = {r: sum(1 for i in ids if ruoli.get(i) == r) for r in "PDCA"}
        atteso = f"{conta['D']}-{conta['C']}-{conta['A']}"
        if conta["P"] != 1:
            p.append(f"{conta['P']} portieri")
        if modulo and modulo != atteso:
            p.append(f"modulo {modulo} ma i ruoli dicono {atteso}")
        if not modulo_valido(conta["D"], conta["C"], conta["A"], regole):
            p.append(f"modulo {atteso} non ammesso")
    if panchina:
        pan = _ids(panchina)
        if set(pan) & set(ids):
            p.append("un titolare anche in panchina")
        if len(set(pan)) != len(pan):
            p.append("panchina con ripetuti")
    return p


# ---------------------------------------------------------------- invarianti di un utente
def controlla_utente(utente: str, r: dict, regole, rosa: set, scelta: dict | None, db, stagione: str,
                     adesso: datetime) -> list[Rottura]:
    """Le invarianti sulle risposte di un utente. `r`: {rotta: corpo} (le rotte andate in errore mancano); `rosa`: id della sua
    squadra; `scelta`: la formazione salvata per la giornata (GET /api/scelta) o None."""
    out: list[Rottura] = []
    oggi, form, wid, diario_ = r.get("oggi"), r.get("formazione"), r.get("widget"), r.get("diario")
    oggi = oggi if isinstance(oggi, dict) else None
    g = oggi.get("giornata") if oggi else None

    def rompi(nome: str, dettaglio: str, giornata: int | None = g) -> None:
        out.append(Rottura(nome, utente, giornata, dettaglio))

    for nome, corpo in r.items():
        if nome != "live":                        # la risposta di /api/live è la stessa per tutti: la guarda controlla_comuni
            out.extend(controlla_forma(nome, corpo, utente, g))

    ruoli: dict = {}
    if isinstance(form, dict):
        for s in list((form.get("schede") or {}).values()) + list(form.get("titolari") or []) + list(form.get("panchina") or []):
            if isinstance(s, dict):
                ruoli[s.get("id")] = s.get("ruolo")
        _controlla_formazione(form, ruoli, regole, rosa, rompi)

    # ---- la scelta salvata (GET /api/scelta) vale ancora?
    scelta_valida = False
    if scelta:
        pr = problemi_formazione(scelta.get("titolari"), ruoli, scelta.get("modulo") or None, regole, rosa) if ruoli else []
        if pr:
            rompi("scelta_ignorata", "scelta salvata: " + ", ".join(pr))
        else:
            scelta_valida = True
    tit_scelta = set(_ids((scelta or {}).get("titolari")))

    # ---- Oggi
    miei: list = []
    if oggi and not oggi.get("senza_rose"):
        f = oggi.get("formazione") or {}
        miei = [x.get("id") for lista in (oggi.get("miei_titolari") or {}).values() for x in lista]
        ha_formazione = bool(miei)
        if ha_formazione and not _num(f.get("punteggio_atteso")):
            rompi("numero_mancante", "oggi.formazione.punteggio_atteso")
        if not ha_formazione and isinstance(form, dict):
            rompi("formazione_non_valida", "oggi senza titolari mentre la formazione c'è")
        if ha_formazione and (len(miei) != 11 or len(set(miei)) != 11):
            rompi("formazione_non_valida", f"oggi.miei_titolari: {len(set(miei))} diversi su {len(miei)}")
        if oggi.get("scadenza") and not _num(oggi.get("ore_mancanti")):
            rompi("numero_mancante", "oggi.ore_mancanti")
        if any(x.get("id") not in set(miei) for x in oggi.get("migliori") or []):
            rompi("formazione_non_valida", "oggi.migliori: un migliore non è tra i titolari")
        if scelta_valida:
            if not f.get("tua_scelta"):
                rompi("scelta_non_mostrata", "oggi.formazione.tua_scelta è falso con una scelta salvata valida")
            elif set(miei) != tit_scelta:
                rompi("scelta_non_mostrata", "oggi mostra titolari diversi da quelli salvati")
        elif f.get("tua_scelta"):
            rompi("scelta_non_mostrata", "oggi dice «tua scelta» ma non c'è una scelta valida")
        out.extend(_controlla_fase(utente, oggi, regole, db, stagione, adesso, ha_formazione))
        if isinstance(form, dict):
            if form.get("giornata") != g or form.get("giornata_lega") != oggi.get("giornata_lega"):
                rompi("giornata_diversa", f"oggi g{g} contro formazione g{form.get('giornata')}")
            if ha_formazione and not f.get("tua_scelta"):
                _stessi_punti("oggi", f.get("punteggio_atteso"), f.get("modulo"), "formazione", form.get("punteggio_atteso"),
                              form.get("modulo"), rompi)
                if set(miei) != set(_ids(form.get("titolari"))):
                    rompi("punti_diversi", "oggi mostra titolari diversi dalla formazione consigliata")

    # ---- widget
    if isinstance(wid, dict):
        wf = wid.get("formazione") or {}
        if not _num(wf.get("punti_attesi")):
            rompi("numero_mancante", "widget.formazione.punti_attesi")
        wt = _ids(wf.get("titolari"))
        wruoli = ruoli or {x.get("id"): x.get("ruolo") for x in wf.get("titolari") or [] if isinstance(x, dict)}
        pr = problemi_formazione(wt, wruoli, wf.get("modulo"), regole, rosa, wf.get("panchina"))
        if pr:
            rompi("formazione_non_valida", "widget: " + ", ".join(pr))
        segnati = {x.get("id") for x in wid.get("rosa") or [] if x.get("titolare")}
        if segnati != set(wt):
            rompi("formazione_non_valida", "widget.rosa: i «titolare» non sono i titolari della formazione mostrata")
        if oggi and not oggi.get("senza_rose"):
            of = oggi.get("formazione") or {}
            if wid.get("giornata") != g or wid.get("giornata_lega") != oggi.get("giornata_lega") \
                    or wid.get("scadenza") != (oggi.get("scadenza") or oggi.get("inizio")):
                rompi("giornata_diversa", f"widget g{wid.get('giornata')} scadenza {wid.get('scadenza')} contro oggi g{g} {oggi.get('scadenza')}")
            _stessi_punti("widget", wf.get("punti_attesi"), wf.get("modulo"), "oggi", of.get("punteggio_atteso"), of.get("modulo"), rompi)
            if bool(wf.get("tua_scelta")) != bool(of.get("tua_scelta")):
                rompi("scelta_non_mostrata", f"widget tua_scelta={bool(wf.get('tua_scelta'))}, oggi tua_scelta={bool(of.get('tua_scelta'))}")
            if miei and set(wt) != set(miei):
                rompi("punti_diversi", "widget e oggi mostrano titolari diversi")
        if scelta_valida and not wf.get("tua_scelta"):
            rompi("scelta_non_mostrata", "widget.formazione.tua_scelta manca con una scelta salvata valida")
        if isinstance(form, dict):
            cons = wf.get("consigliata") if wf.get("tua_scelta") else wf
            if isinstance(cons, dict):
                _stessi_punti("widget (consigliata)", cons.get("punti_attesi"), cons.get("modulo"), "formazione",
                              form.get("punteggio_atteso"), form.get("modulo"), rompi)
        dimensione = len(json.dumps(wid, ensure_ascii=False).encode())
        if dimensione > MAX_BYTE_WIDGET:
            rompi("widget_troppo_grande", f"{dimensione} byte")

    # ---- diario: solo giornate finite, una volta sola
    if isinstance(diario_, dict):
        viste = set()
        for i, v in enumerate(diario_.get("giornate") or []):
            k = (v.get("stagione"), v.get("giornata"))
            if k in viste:
                rompi("diario_incoerente", f"giornate[{i}]: giornata ripetuta", k[1])
            viste.add(k)
            if v.get("stagione") == stagione and g is not None and _num(v.get("giornata")) and v["giornata"] >= g:
                rompi("diario_incoerente", f"giornate[{i}]: la giornata {v['giornata']} non è ancora finita", v["giornata"])
            if not _num((v.get("consigliata") or {}).get("atteso")):
                rompi("numero_mancante", f"diario.giornate[{i}].consigliata.atteso", v.get("giornata"))
            ist = v.get("istantanea")
            if isinstance(ist, dict) and len(set(_ids(ist.get("titolari")))) != 11:
                rompi("diario_incoerente", f"giornate[{i}].istantanea: {len(set(_ids(ist.get('titolari'))))} titolari", v.get("giornata"))
        for gg in giornate_da_diario(db, stagione, adesso, getattr(regole, "prima_giornata_lega", 1)):
            if (stagione, gg) not in viste:
                rompi("diario_mancante", f"la giornata {gg} è finita con i voti da più di {DIARIO_ENTRO.total_seconds() / 3600:.0f} ore ma non è nel diario", gg)

    # ---- Oggi e Live dicono lo stesso stato della stessa partita
    live_ = r.get("live")
    if oggi and isinstance(live_, dict):
        dal_live = {(p.get("casa"), p.get("trasferta")): p.get("stato") for p in live_.get("partite") or []}
        for i, p in enumerate(oggi.get("partite") or []):
            sl = dal_live.get((p.get("casa"), p.get("trasferta")))
            so = p.get("stato")
            if sl is None or so is None or so == "rinviata":      # recupero: Oggi lo sa dal turno, Live dal calendario
                continue
            sl = "in_corso" if sl in _IN_GIOCO else "rinviata" if sl == "sospesa" else sl
            if sl != so:
                rompi("stato_partita_incoerente", f"oggi.partite[{i}] «{so}» ma live «{sl}»")
                break

    # ---- giornata in corso: numeri, giocatori fermi, formazione schierata
    blocco = oggi.get("in_corso") if oggi else None
    if isinstance(blocco, dict):
        campi = ("punti_fatti", "punti_attesi_restanti", "punti_previsti")
        for campo in campi:
            if not _num(blocco.get(campo)):
                rompi("numero_mancante", f"oggi.in_corso.{campo}")
        if all(_num(blocco.get(c)) for c in campi) \
                and abs(blocco["punti_fatti"] + blocco["punti_attesi_restanti"] - blocco["punti_previsti"]) > 0.15:
            rompi("punti_diversi", "oggi.in_corso: fatti + restanti diverso da previsti")
        if blocco.get("giornata") != g:
            rompi("giornata_diversa", f"oggi.in_corso g{blocco.get('giornata')} contro oggi g{g}")
        for i, x in enumerate(blocco.get("giocatori") or []):
            inizio = _data(x.get("data"))
            if inizio is None:
                continue
            if x.get("stato") in ("da_giocare", "in_corso") and adesso - inizio > DOPO_INIZIO_PUNTEGGIO:
                rompi("giocatore_fermo", f"oggi.in_corso.giocatori[{i}] «{x.get('stato')}» con la partita iniziata da {_ore(adesso - inizio)}")
                break
            if x.get("stato") == "attesa_voti" and adesso - inizio - DURATA_PARTITA > VOTI_ENTRO:
                rompi("giocatore_fermo", f"oggi.in_corso.giocatori[{i}] «attesa_voti» da {_ore(adesso - inizio - DURATA_PARTITA)}")
                break
        if scelta_valida:
            schierati = {x.get("id") for x in blocco.get("giocatori") or [] if x.get("titolare")}
            if blocco.get("formazione_di") != "tua" or schierati != tit_scelta:
                rompi("scelta_non_mostrata", f"oggi.in_corso.formazione_di = {blocco.get('formazione_di')} con una scelta salvata")
    return out


def _stessi_punti(a: str, punti_a, modulo_a, b: str, punti_b, modulo_b, rompi) -> None:
    if _num(punti_a) and _num(punti_b) and abs(punti_a - punti_b) > TOLLERANZA_PUNTI:
        rompi("punti_diversi", f"{a} {punti_a} contro {b} {punti_b}")
    elif modulo_a != modulo_b and modulo_a and modulo_b:
        rompi("punti_diversi", f"{a} modulo {modulo_a} contro {b} {modulo_b}")


def _controlla_formazione(form: dict, ruoli: dict, regole, rosa: set, rompi) -> None:
    """GET /api/formazione: la consigliata, ogni modulo e ogni stile."""
    if not _num(form.get("punteggio_atteso")):
        rompi("numero_mancante", "formazione.punteggio_atteso")
    for i, t in enumerate(list(form.get("titolari") or []) + list(form.get("panchina") or [])):
        mancante = next((c for c in ("punti_attesi", "p_voto", "fv_atteso") if not _num(t.get(c))), None)
        if mancante:
            rompi("numero_mancante", f"formazione: giocatore {i}, {mancante}")
            break
    pr = problemi_formazione(form.get("titolari"), ruoli, form.get("modulo"), regole, rosa, form.get("panchina"))
    if pr:
        rompi("formazione_non_valida", "formazione: " + ", ".join(pr))
    for j, m in enumerate(form.get("moduli") or []):
        pr = problemi_formazione(m.get("titolari"), ruoli, m.get("modulo"), regole, rosa, m.get("panchina"))
        if pr:
            rompi("formazione_non_valida", f"formazione.moduli[{j}]: " + ", ".join(pr))
            break
    livelli = form.get("livelli") or []
    for j, liv in enumerate(livelli):
        mod = next((m for m in liv.get("moduli") or [] if m.get("modulo") == liv.get("modulo")), None)
        if mod is None:
            rompi("formazione_non_valida", f"formazione.livelli[{j}]: il modulo dello stile non è tra i suoi moduli")
            break
        pr = problemi_formazione(mod.get("titolari"), ruoli, mod.get("modulo"), regole, rosa, mod.get("panchina"))
        if pr:
            rompi("formazione_non_valida", f"formazione.livelli[{j}]: " + ", ".join(pr))
            break
        if _num(liv.get("punteggio_atteso")) and _num(mod.get("punteggio_atteso")) \
                and abs(liv["punteggio_atteso"] - mod["punteggio_atteso"]) > TOLLERANZA_PUNTI:
            rompi("punti_diversi", f"formazione.livelli[{j}]: {liv['punteggio_atteso']} contro {mod['punteggio_atteso']} del suo modulo")
            break
    if livelli:                       # `stile_consigliato` è l'id dello stile (campo `stile`), non la posizione nella lista
        consigliato = next((liv for liv in livelli if liv.get("stile") == form.get("stile_consigliato")), None)
        if consigliato is None:
            rompi("formazione_non_valida", f"stile_consigliato {form.get('stile_consigliato')!r} non è tra gli stili")
        else:
            _stessi_punti("stile consigliato", consigliato.get("punteggio_atteso"), consigliato.get("modulo"), "formazione",
                          form.get("punteggio_atteso"), form.get("modulo"), rompi)


def _controlla_fase(utente, oggi: dict, regole, db, stagione: str, adesso: datetime, ha_formazione: bool) -> list[Rottura]:
    """Fase della giornata, scadenza e stato delle partite di Oggi contro l'orario e il calendario (regola unica di turno.py)."""
    from . import avvisi, fasi, turno
    out: list[Rottura] = []
    g = oggi.get("giornata")

    def rompi(nome, dettaglio):
        out.append(Rottura(nome, utente, g, dettaglio))

    fase = oggi.get("fase")
    if fase not in (fasi.PRIMA, fasi.IN_CORSO, fasi.FINITA):
        rompi("fase_incoerente", f"fase sconosciuta {fase!r}")
        return out
    if g is not None:
        attesa = avvisi.scadenza(avvisi.prima_partita(db, stagione, g), regole)
        attesa_t = attesa.isoformat(sep=" ", timespec="minutes") if attesa else None
        if oggi.get("scadenza") != attesa_t:
            rompi("fase_incoerente", f"scadenza di Oggi {oggi.get('scadenza')} contro {attesa_t} della regola unica (promemoria, copia automatica)")
    scad = _data(oggi.get("scadenza"))
    if scad is not None:
        if bool(oggi.get("iniziata")) != (scad <= adesso):
            rompi("fase_incoerente", f"iniziata={oggi.get('iniziata')} con la scadenza {oggi.get('scadenza')}")
        ore = oggi.get("ore_mancanti")
        if _num(ore) and abs(ore - (scad - adesso).total_seconds() / 3600) > TOLLERANZA_ORE:
            rompi("fase_incoerente", f"ore_mancanti {ore} con la scadenza {oggi.get('scadenza')}")
    if (fase == fasi.IN_CORSO) != bool(oggi.get("iniziata")):
        rompi("fase_incoerente", f"fase {fase} con iniziata={oggi.get('iniziata')}")
    partite = oggi.get("partite") or []
    inizio_turno = turno.inizio(_data(p.get("data")) for p in partite)
    for i, p in enumerate(partite):
        d, stato = _data(p.get("data")), p.get("stato")
        if d is None or inizio_turno is None or not turno.nel_turno(d, inizio_turno):
            continue
        if fase == fasi.PRIMA and stato in (fasi.IN_CORSO, "finita"):
            rompi("fase_incoerente", f"fase «prima» ma oggi.partite[{i}] è «{stato}»")
        if stato == "da_giocare" and adesso - d > DOPO_INIZIO_PUNTEGGIO:
            rompi("stato_partita_incoerente", f"oggi.partite[{i}] «da_giocare» iniziata da {_ore(adesso - d)}")
        elif stato in (fasi.IN_CORSO, "finita") and not p.get("giocata") and d - adesso > timedelta(minutes=15):
            rompi("stato_partita_incoerente", f"oggi.partite[{i}] «{stato}» ma comincia tra {_ore(d - adesso)}")
    if fase == fasi.IN_CORSO and ha_formazione and oggi.get("in_corso") is None:
        rompi("fase_incoerente", "fase «in_corso» senza il blocco in_corso")
    if fase == fasi.FINITA and oggi.get("prossima") is None:
        rompi("fase_incoerente", "fase «finita» senza il blocco prossima")
    if fase != fasi.IN_CORSO and oggi.get("in_corso") is not None:
        rompi("fase_incoerente", f"blocco in_corso con fase «{fase}»")
    return out


def giornate_da_diario(db: sqlite3.Connection, stagione: str, adesso: datetime, prima_giornata_lega: int = 1) -> list[int]:
    """Le giornate delle ultime due settimane con tutte le partite giocate, i voti di tutte le squadre e la fine da più di
    DIARIO_ENTRO: devono essere nel diario di chi ha la squadra."""
    da = (adesso - timedelta(days=GIORNI_INDIETRO)).strftime("%Y-%m-%d")
    voti = {(g, s) for g, s in db.execute("SELECT DISTINCT giornata, squadra FROM voti WHERE stagione = ? AND voto_red IS NOT NULL",
                                           (stagione,))}
    per_g: dict[int, list] = {}
    for g, testo, casa, trasferta, giocata in db.execute("SELECT giornata, data, casa, trasferta, giocata FROM partite WHERE stagione = ?",
                                                          (stagione,)):
        per_g.setdefault(g, []).append((_data(testo), casa, trasferta, giocata))
    pronte = []
    for g, rr in sorted(per_g.items()):
        date = [d for d, *_ in rr if d]
        if g < prima_giornata_lega or not date or not rr or max(date).strftime("%Y-%m-%d") < da:
            continue
        if all(gi and (g, c) in voti and (g, t) in voti for _, c, t, gi in rr) and adesso - max(date) - DURATA_PARTITA > DIARIO_ENTRO:
            pronte.append(g)
    return pronte


# ---------------------------------------------------------------- invarianti comuni (calendario, voti, risultati in diretta)
_IN_GIOCO = ("primo_tempo", "intervallo", "secondo_tempo", "in_corso")


def controlla_comuni(db: sqlite3.Connection, stagione: str, adesso: datetime, live_corpo: dict | None) -> list[Rottura]:
    """Le invarianti uguali per tutti: calendario e voti dell'archivio, giornata da giocare, risposta di GET /api/live."""
    from . import consigli, turno
    out: list[Rottura] = []
    da = (adesso - timedelta(days=GIORNI_INDIETRO)).strftime("%Y-%m-%d")
    righe = db.execute("SELECT giornata, data, casa, trasferta, giocata FROM partite WHERE stagione = ? ORDER BY giornata, data",
                       (stagione,)).fetchall()
    per_g: dict[int, list] = {}
    for r in righe:
        per_g.setdefault(r[0], []).append(r)
    turni = {g: turno.inizio(_data(r[1]) for r in rr) for g, rr in per_g.items()}

    def nel_turno(g, d) -> bool:
        return turno.della_giornata(d, turni.get(g))          # anticipi compresi: sono partite della giornata

    # partite del turno finite da più di 12 ore e non ancora «giocate» nel calendario; voti delle partite finite
    voti = {(g, s) for g, s in db.execute("SELECT DISTINCT giornata, squadra FROM voti WHERE stagione = ? AND voto_red IS NOT NULL",
                                           (stagione,))}
    ferme: dict[int, int] = {}
    senza_voti: dict[int, set] = {}
    for g, rr in per_g.items():
        for _, testo, casa, trasferta, giocata in rr:
            d = _data(testo)
            if d is None or (testo or "") < da or not nel_turno(g, d):
                continue
            dalla_fine = adesso - d - DURATA_PARTITA
            if not giocata and dalla_fine > RISULTATI_ENTRO:
                ferme[g] = ferme.get(g, 0) + 1
            if dalla_fine > VOTI_ENTRO:
                senza_voti.setdefault(g, set()).update(s for s in (casa, trasferta) if (g, s) not in voti)
    for g, n in sorted(ferme.items()):
        out.append(Rottura("risultati_fermi", None, g, f"{n} partite finite da più di {RISULTATI_ENTRO.total_seconds() / 3600:.0f} ore non risultano giocate"))
    for g, squadre in sorted(senza_voti.items()):
        if squadre:
            out.append(Rottura("voti_mancanti", None, g, f"{len(squadre)} squadre senza voti: {', '.join(sorted(squadre)[:6])}"))

    # la giornata da giocare: non salta una giornata ancora da cominciare, non resta su una giornata finita da giorni
    g = consigli.prossima_giornata(db, stagione, adesso)
    if g is None and any((_data(r[1]) or datetime.min) > adesso for r in righe):
        out.append(Rottura("giornata_incoerente", None, None, "nessuna giornata da giocare ma il calendario ha partite future"))
    if g is not None:
        da_iniziare = [r for r in per_g.get(g - 1) or [] if nel_turno(g - 1, _data(r[1])) and _data(r[1]) > adesso and not r[4]]
        if da_iniziare:
            out.append(Rottura("giornata_incoerente", None, g, f"la giornata {g - 1} ha ancora {len(da_iniziare)} partite da cominciare"))
        del_turno = [_data(r[1]) for r in per_g.get(g) or [] if nel_turno(g, _data(r[1]))]
        if del_turno and all(adesso - d - DURATA_PARTITA > timedelta(hours=24) for d in del_turno):
            out.append(Rottura("giornata_incoerente", None, g, "giornata da giocare con tutte le partite finite da più di un giorno"))

    # risultati in diretta (GET /api/live, come lo vede l'utente)
    if isinstance(live_corpo, dict):
        out.extend(controlla_forma("live", live_corpo, None, g))
        inizio = turni.get(g) if g is not None else None
        for p in live_corpo.get("partite") or []:
            d, stato = _data(p.get("data")), p.get("stato")
            if d is None or stato == "rinviata":
                continue
            trascorso = adesso - d
            nome = f"{p.get('casa')}-{p.get('trasferta')}"           # squadre di Serie A: nessun dato personale
            nel = turno.della_giornata(d, inizio)
            if nel and trascorso > DOPO_INIZIO_PUNTEGGIO and not (_num(p.get("gol_casa")) and _num(p.get("gol_trasferta"))):
                out.append(Rottura("punteggio_mancante", None, g, f"{nome} iniziata da {_ore(trascorso)}, stato «{stato}», senza punteggio"))
            if stato == "da_giocare" and trascorso > DOPO_INIZIO_PUNTEGGIO:
                out.append(Rottura("stato_partita_incoerente", None, g, f"live: {nome} «da_giocare» iniziata da {_ore(trascorso)}"))
            elif stato in _IN_GIOCO and (trascorso > timedelta(hours=4) or -trascorso > timedelta(minutes=15)):
                out.append(Rottura("stato_partita_incoerente", None, g, f"live: {nome} «{stato}» con l'inizio a {p.get('data')}"))
            elif stato == "finita" and -trascorso > timedelta(minutes=15):
                out.append(Rottura("stato_partita_incoerente", None, g, f"live: {nome} «finita» prima di cominciare"))
    return out


# ---------------------------------------------------------------- le risposte vere (stesse funzioni delle rotte, niente rete)
def _richiesta_finta(percorso: str):
    """Una GET senza cookie né token: serve alle funzioni delle rotte che leggono intestazioni (lingua, amministratore)."""
    from starlette.requests import Request
    return Request({"type": "http", "method": "GET", "path": percorso, "raw_path": percorso.encode(), "query_string": b"",
                    "headers": [], "client": ("127.0.0.1", 0), "server": ("127.0.0.1", 80), "scheme": "http", "root_path": ""})


def _in_json(corpo) -> None:
    """Come FastAPI scrive la risposta di un dizionario: jsonable_encoder e poi JSON stretto (allow_nan=False). Alza se non si può."""
    from fastapi.encoders import jsonable_encoder
    json.dumps(jsonable_encoder(corpo), allow_nan=False)


def _da_risposta(risposta) -> dict:
    """Il corpo di una JSONResponse (widget, live) come lo riceve il client."""
    return json.loads(bytes(risposta.body).decode("utf-8"))


def risposte_utente(ctx, db) -> tuple[dict, dict, dict | None]:
    """({rotta: corpo}, {rotta: (tipo d'errore, gravità)}, scelta salvata della giornata). Gravità: `senza_rose` (409, normale per
    un account nuovo), `rifiutata` (400 con il messaggio per l'utente), `errore` (sarebbe un 500), `json` (non si scrive in JSON)."""
    from fastapi import HTTPException
    from fastapi.responses import Response
    from . import consigli, server
    corpi: dict = {}
    errori: dict = {}

    def prova(nome, funzione):
        try:
            corpi[nome] = funzione()
        except HTTPException as e:
            errori[nome] = (f"HTTP {e.status_code}", "senza_rose" if e.status_code == 409 else "errore" if e.status_code >= 500 else "rifiutata")
        except ValueError as e:              # il server la trasforma in 400 con il messaggio per l'utente
            errori[nome] = (type(e).__name__, "rifiutata")
        except Exception as e:               # noqa: BLE001 - sarebbe un 500: è proprio quello che si cerca
            errori[nome] = (type(e).__name__, "errore")

    prova("oggi", lambda: server.oggi(_richiesta_finta("/api/oggi"), None, ctx))
    # NON la rotta /api/formazione: salverebbe la copia automatica della consigliata (scrittura). Stessa funzione che chiama lei.
    prova("formazione", lambda: consigli.formazione(db, server._regole(ctx), server._rose(ctx)))
    prova("diario", lambda: server.leggi_diario(ctx))
    prova("widget", lambda: _da_risposta(server.widget(_richiesta_finta("/api/widget"), ctx)))
    prova("live", lambda: _da_risposta(server.risultati_live(_richiesta_finta("/api/live"))))
    g = (corpi.get("oggi") or {}).get("giornata")
    if g:
        prova("scelta", lambda: server.leggi_scelta(response=Response(), giornata=int(g), ctx=ctx))     # per nome: la firma della rotta può cambiare ordine
    for nome in [n for n in ("oggi", "formazione", "diario", "scelta") if n in corpi]:     # quelle che FastAPI scrive dopo
        try:
            _in_json(corpi[nome])
        except (TypeError, ValueError) as e:
            errori[nome + ":json"] = (type(e).__name__, "json")
    return corpi, errori, corpi.get("scelta")


def _contesti() -> list[tuple[str, Any]]:
    """(etichetta, contesto) di chi controllare. Con gli account: ogni utente con le rose (database aperto in sola lettura)."""
    from . import account, server
    from .contesto import Contesto
    if not account.multiutente():
        return [("utente locale", server._contesto_locale())]
    file = percorsi.cartella_account() / "account.sqlite"
    if not file.exists():
        return []
    adb = sqlite3.connect(f"{file.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
    try:
        ids = [r[0] for r in adb.execute("SELECT id FROM utenti ORDER BY id")]
    finally:
        adb.close()
    return [(f"utente {i}", c) for i, c in ((i, Contesto.per_utente(i)) for i in ids) if c.rose.exists()]


def leggi_live(file: Path = FILE_LIVE):
    """Un raccoglitore FERMO (non chiede niente a nessuno) con la cache letta dalla copia su file del servizio:
    {"aggiornato_il", "fonte", "partite": [partita come in /api/live]} (le partite possono stare anche in un dizionario).
    None se il file non c'è o non si legge: allora si usa il solo calendario, come il servizio senza diretta."""
    from . import live
    try:
        d = json.loads(file.read_text(encoding="utf-8"))
        partite = d.get("partite") or []
        partite = list(partite.values()) if isinstance(partite, dict) else list(partite)
        r = live.Raccoglitore(lambda: [], scarica=lambda url: "")
        r._partite = {(p["casa"], p["trasferta"]): p for p in partite if isinstance(p, dict) and "casa" in p and "trasferta" in p}
        r.aggiornato_il, r.fonte = d.get("aggiornato_il"), d.get("fonte")
        return r
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def _prepara_live() -> None:
    """In questo processo non c'è il raccoglitore del servizio: si usa la sua copia su file, alle stesse condizioni con cui il
    servizio lo accende (server._ciclo). Così /api/live e le fasi di Oggi sono quelle che vede l'utente."""
    from . import fonti_attive, funzioni, live
    if live.unico is None and fonti_attive.acceso("espn") and funzioni.acceso("live"):
        live.unico = leggi_live()


def esegui(db: sqlite3.Connection, adesso: datetime | None = None, minuti: float = 15, stato: dict | None = None,
           contesti: list | None = None) -> dict:
    """Un giro completo: {rotture, controllati, rimandati, secondi, stagione}. Non scrive niente (per salvare: `registra`)."""
    from . import consigli, lega, regole as mod_regole, server
    inizio = time.monotonic()
    adesso = adesso or datetime.now()
    stagione = consigli.stagione_corrente()
    _prepara_live()
    contesti = _contesti() if contesti is None else contesti
    ultimi = (stato or {}).get("utenti") or {}
    contesti = sorted(contesti, key=lambda c: ultimi.get(c[0], ""))          # prima chi è stato controllato meno di recente
    rotture: list[Rottura] = []
    controllati: list[str] = []
    live_corpo = None
    for etichetta, ctx in contesti:
        if controllati and time.monotonic() - inizio > 60 * minuti:
            break
        controllati.append(etichetta)
        try:
            r_regole, rose_ = mod_regole.carica(ctx.regole), lega.carica(ctx.rose)
        except Exception as e:                 # noqa: BLE001 - file rovinati: l'app andrebbe in errore anche lei
            rotture.append(Rottura("risposta_in_errore", etichetta, None, f"regole o rose illeggibili ({type(e).__name__})"))
            continue
        squadra = rose_.squadra(rose_.mia_squadra or "") if rose_ else None
        corpi, errori, scelta = risposte_utente(ctx, db)
        g = (corpi.get("oggi") or {}).get("giornata")
        for nome, (tipo, gravita) in sorted(errori.items()):
            if gravita == "json":
                rotture.append(Rottura("json_non_valido", etichetta, g, f"{nome.split(':')[0]}: {tipo} nel trasformarla in JSON"))
            elif gravita == "rifiutata" and squadra is not None:     # senza la propria squadra il rifiuto è giusto (lo dice l'app)
                rotture.append(Rottura("risposta_rifiutata", etichetta, g, f"{nome}: {tipo}"))
            elif gravita == "errore":
                rotture.append(Rottura("risposta_in_errore", etichetta, g, f"{nome}: {tipo}"))
        if live_corpo is None and "live" in corpi:
            live_corpo = corpi["live"]
        if squadra is not None:
            rosa = {x.id for x in squadra.giocatori if x.id is not None}
            try:
                rotture.extend(controlla_utente(etichetta, {k: v for k, v in corpi.items() if k != "scelta"},
                                                r_regole, rosa, scelta, db, stagione, adesso))
            except Exception as e:             # noqa: BLE001 - un controllo rotto si segnala e non ferma gli altri utenti
                rotture.append(Rottura("risposta_in_errore", etichetta, g, f"sentinella: controllo non riuscito ({type(e).__name__})"))
    if live_corpo is None:
        try:
            live_corpo = _da_risposta(server.risultati_live(_richiesta_finta("/api/live")))
        except Exception as e:                 # noqa: BLE001
            rotture.append(Rottura("risposta_in_errore", None, None, f"live: {type(e).__name__}"))
    try:
        rotture.extend(controlla_comuni(db, stagione, adesso, live_corpo))
    except Exception as e:                     # noqa: BLE001
        rotture.append(Rottura("risposta_in_errore", None, None, f"sentinella: controlli comuni non riusciti ({type(e).__name__})"))
    viste, uniche = set(), []
    for r in rotture:
        if (r.chiave, r.dettaglio) not in viste:
            viste.add((r.chiave, r.dettaglio))
            uniche.append(r)
    return {"rotture": uniche, "controllati": controllati, "rimandati": len(contesti) - len(controllati),
            "secondi": round(time.monotonic() - inizio, 1), "stagione": stagione}


# ---------------------------------------------------------------- tabella `controlli` («Stato dei dati»)
def registra(db: sqlite3.Connection, esito: dict, quando: str | None = None) -> None:
    """Una riga per invariante (ok o rotta) più quella di riassunto, nella stagione in corso. Le righe di `controlli.esegui` restano."""
    quando = quando or datetime.now().isoformat(timespec="seconds")
    stagione = esito["stagione"]
    per_inv: dict[str, list[Rottura]] = {}
    for r in esito["rotture"]:
        per_inv.setdefault(r.invariante, []).append(r)
    nomi = [PREFISSO + k for k in INVARIANTI]
    db.execute(f"DELETE FROM controlli WHERE stagione = ? AND nome LIKE ? AND nome NOT IN ({','.join('?' * len(nomi))})",
               (stagione, PREFISSO + "%", *nomi))          # invarianti tolte dal codice: la loro riga vecchia sparisce
    for nome, (gravita, descrizione) in INVARIANTI.items():
        rr = per_inv.get(nome) or []
        if rr:
            dettaglio = "; ".join(f"{r.utente or 'tutti'}{f' · g{r.giornata}' if r.giornata is not None else ''}: {r.dettaglio}" for r in rr)
            if len(dettaglio) > MAX_DETTAGLIO:
                dettaglio = dettaglio[:MAX_DETTAGLIO - 25].rsplit("; ", 1)[0] + f"; … ({len(rr)} in tutto)"
            riga = (gravita, float(len(rr)), dettaglio)
        else:
            riga = ("ok", 0.0, descrizione)
        db.execute("INSERT OR REPLACE INTO controlli (stagione, nome, esito, valore, dettaglio, controllato) VALUES (?, ?, ?, ?, ?, ?)",
                   (stagione, PREFISSO + nome, *riga, quando))
    rotte = len(per_inv)
    riassunto = (f"{len(esito['controllati'])} utenti controllati in {esito['secondi']:g} s"
                 + (f", {esito['rimandati']} al prossimo giro" if esito["rimandati"] else "")
                 + (f"; {rotte} invarianti rotte su {len(INVARIANTI)}" if rotte else f"; {len(INVARIANTI)} invarianti a posto"))
    peggiore = "errore" if any(INVARIANTI[k][0] == "errore" for k in per_inv) else "avviso" if rotte else "ok"
    db.execute("INSERT OR REPLACE INTO controlli (stagione, nome, esito, valore, dettaglio, controllato) VALUES (?, ?, ?, ?, ?, ?)",
               (stagione, "sentinella", peggiore, float(rotte), riassunto, quando))
    db.commit()


# ---------------------------------------------------------------- avvisi (una volta sola, niente raffiche)
def leggi_stato(file: Path = FILE_STATO) -> dict:
    try:
        d = json.loads(file.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def aggiorna_stato(stato: dict, esito: dict, adesso: datetime) -> tuple[dict, list[Rottura]]:
    """(stato nuovo, rotture da avvisare adesso). Una rottura si avvisa quando è vista CONFERME giri di fila e non è già stata
    avvisata; tornata a posto resta ricordata come «avvisata» per RICORDA_RISOLTE, così un'altalena non manda raffiche. Le rotture
    di chi non è stato controllato in questo giro (tempo finito) restano come sono."""
    ora = adesso.isoformat(timespec="seconds")
    aperte = {k: dict(v) for k, v in (stato.get("aperte") or {}).items() if isinstance(v, dict)}
    utenti = dict(stato.get("utenti") or {})
    for u in esito["controllati"]:
        utenti[u] = ora
    viste: dict[str, Rottura] = {}
    for r in esito["rotture"]:
        viste.setdefault(r.chiave, r)
    da_avvisare = []
    for chiave, r in viste.items():
        e = aperte.get(chiave) or {"volte": 0, "avvisata": False}
        e["volte"] = (0 if e.pop("risolta", False) else int(e.get("volte") or 0)) + 1
        e["ultima"] = ora
        aperte[chiave] = e
        if not e.get("avvisata") and e["volte"] >= CONFERME:
            da_avvisare.append(r)
    controllati = set(esito["controllati"])
    for chiave in [k for k in aperte if k not in viste]:
        utente = chiave.split("|")[1]
        if utente != "-" and utente not in controllati:
            continue                                            # non controllato in questo giro: non si sa
        e = aperte[chiave]
        e["risolta"], e["volte"] = True, 0
        if not e.get("avvisata") or adesso - (_data(e.get("ultima")) or adesso) > RICORDA_RISOLTE:
            del aperte[chiave]
    return {"aperte": aperte, "utenti": utenti, "ultimo_giro": ora}, da_avvisare


def segna_avvisate(stato: dict, rotture: list[Rottura]) -> None:
    for r in rotture:
        if r.chiave in stato["aperte"]:
            stato["aperte"][r.chiave]["avvisata"] = True


def testo_avviso(rotture: list[Rottura]) -> tuple[str, str]:
    """Titolo e testo dell'avviso: SOLO nome dell'invariante, giornata e «utente N» (mai nomi, squadre, giocatori o dettagli)."""
    gruppi: dict[tuple, set] = {}
    for r in rotture:
        gruppi.setdefault((r.invariante, r.giornata), set()).add(r.utente or "tutti")
    righe = []
    for (inv, g), chi in sorted(gruppi.items(), key=lambda x: (INVARIANTI[x[0][0]][0] != "errore", x[0][0], x[0][1] or 0)):
        chi = sorted(chi, key=lambda u: (len(u), u))
        quali = ", ".join(chi[:3]) + (f" e altri {len(chi) - 3}" if len(chi) > 3 else "")
        righe.append(f"• {inv}{f' · giornata {g}' if g is not None else ''} · {quali}")
    if len(righe) > MAX_RIGHE_AVVISO:
        righe = righe[:MAX_RIGHE_AVVISO - 1] + [f"• e altri {len(righe) - MAX_RIGHE_AVVISO + 1}"]
    n = len(gruppi)
    return ("SchieraXI: sentinella", f"{n} {'controllo rotto' if n == 1 else 'controlli rotti'} per la prima volta "
            "(dettagli in Stato dei dati):\n" + "\n".join(righe))


# ---------------------------------------------------------------- storia dei giri (la «giornata senza errori», #532)
def _quando(voce) -> datetime | None:
    """L'ora di una voce della storia, con il fuso; None se la voce è rovinata o senza fuso."""
    try:
        q = datetime.fromisoformat(voce["quando"])
    except (TypeError, KeyError, ValueError):
        return None
    return q if q.utcoffset() is not None else None


def rotte_confermate(stato: dict, esito: dict) -> list[str]:
    """Le invarianti rotte in questo giro e confermate (viste CONFERME giri di fila, come per l'avviso), anche se già avvisate:
    una rottura vista in un giro solo non è un allarme. `stato` è quello appena aggiornato da `aggiorna_stato`."""
    aperte = stato.get("aperte") or {}
    return sorted({r.invariante for r in esito["rotture"] if int((aperte.get(r.chiave) or {}).get("volte") or 0) >= CONFERME})


def aggiungi_giro(giri, voce: dict) -> list[dict]:
    """La storia con la voce nuova in fondo, senza le voci più vecchie di TIENI_GIRI (né quelle che non si leggono)."""
    limite = _quando(voce) - TIENI_GIRI
    tenute = [v for v in (giri if isinstance(giri, list) else []) if (q := _quando(v)) is not None and q >= limite]
    return tenute + [voce]


def giri_sentinella(dal: datetime, al: datetime, file: Path = FILE_STATO) -> list[dict]:
    """I giri del server con `dal <= quando <= al`, dal più vecchio: [{quando, rotte, inviato}] (solo ore e nomi di invarianti).
    `dal` e `al` vogliono il fuso: la storia ha l'ora con il fuso, e un confronto con un'ora senza fuso sarebbe sbagliato."""
    if dal.utcoffset() is None or al.utcoffset() is None:
        raise ValueError("dal e al vogliono data e ora col fuso (esempio: 2026-11-15T20:00:00+01:00 o 2026-11-15T19:00:00Z)")
    giri = leggi_stato(file).get("giri")
    scelti = []
    for v in giri if isinstance(giri, list) else []:
        q = _quando(v)
        if q is None or not dal <= q <= al:
            continue
        rotte = v.get("rotte") or []
        rotte = [str(x) for x in rotte] if isinstance(rotte, list) else [str(rotte)]   # rovinata: resta un allarme, mai verde
        scelti.append((q, {"quando": v["quando"], "rotte": rotte, "inviato": v.get("inviato") is True}))
    return [v for _, v in sorted(scelti, key=lambda x: x[0])]


def canale() -> str | None:
    """Il canale del proprietario, come gli script del server: il file in SCHIERAXI_CANALE o ~/.config/schieraxi/canale."""
    file = Path(os.environ.get("SCHIERAXI_CANALE") or Path.home() / ".config" / "schieraxi" / "canale")
    try:
        c = "".join(file.read_text(encoding="utf-8").split())
    except OSError:
        return None
    return c or None


def manda_ntfy(titolo: str, testo: str) -> bool:
    """Manda l'avviso con ntfy. Il canale non compare mai nei log né tra gli argomenti di un comando."""
    c = canale()
    if not c:
        return False
    corpo = json.dumps({"topic": c, "title": titolo, "message": testo, "priority": 4, "tags": ["mag"]}).encode()
    richiesta = urllib.request.Request(os.environ.get("SENTINELLA_NTFY_URL") or NTFY, data=corpo, method="POST",
                                       headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(richiesta, timeout=20) as r:     # noqa: S310 - indirizzo fisso (o quello delle prove)
            return 200 <= r.status < 300
    except OSError:
        return False


def giro(minuti: float = 15, manda: Callable[[str, str], bool] | None = manda_ntfy, file_stato: Path = FILE_STATO,
         adesso: datetime | None = None, scrivi: Callable[[str], None] = print, db_percorso: Path | None = None) -> dict:
    """Il comando del cron: controlla, scrive la tabella `controlli`, avvisa le rotture nuove e aggiunge il giro alla storia
    (`giri`). Con `manda=None` (--senza-invio) stampa l'avviso invece di mandarlo e non tocca il file di stato: le prove a mano non
    consumano gli avvisi e non entrano nella storia (non coprono il buco di un cron fermo)."""
    from . import archivio
    adesso = adesso or datetime.now()
    stato = leggi_stato(file_stato)
    db = archivio.apri(db_percorso) if db_percorso else archivio.apri()
    try:
        esito = esegui(db, adesso, minuti, stato)
        registra(db, esito)
    finally:
        db.close()
    nuovo, da_avvisare = aggiorna_stato(stato, esito, adesso)
    scrivi(f"sentinella: {len(esito['controllati'])} utenti in {esito['secondi']:g} s, {len(esito['rotture'])} rotture"
           + (f", {esito['rimandati']} rimandati al prossimo giro" if esito["rimandati"] else ""))
    for r in esito["rotture"]:
        scrivi(f"  [{INVARIANTI[r.invariante][0]}] {r.invariante} · {r.utente or 'tutti'} · g{r.giornata}: {r.dettaglio}")
    inviato = False
    if da_avvisare:
        titolo, testo = testo_avviso(da_avvisare)
        if manda is None:
            scrivi(f"[prova, non inviato] {titolo}: {testo}")
        elif manda(titolo, testo):
            segna_avvisate(nuovo, da_avvisare)
            inviato = True
            scrivi(f"avviso mandato: {len(da_avvisare)} rotture nuove")
        else:
            scrivi("avviso NON mandato (canale mancante o rete): si riprova al prossimo giro")
    if manda is not None:
        voce = {"quando": adesso.astimezone().isoformat(timespec="seconds"), "rotte": rotte_confermate(nuovo, esito),
                "inviato": inviato}
        nuovo["giri"] = aggiungi_giro(stato.get("giri"), voce)
        percorsi.scrivi_sicuro(file_stato, json.dumps(nuovo, ensure_ascii=False))
    return esito | {"da_avvisare": da_avvisare}
