"""Il diario delle giornate: per ogni giornata finita, la formazione che hai schierato (la tua scelta salvata) contro la consigliata,
con i punti attesi e quelli fatti. La panchina è quella che sceglie il sistema, anche per la tua, tranne quando hai schierato gli
stessi undici della consigliata mostrata: allora la tua è quella formazione, con la sua panchina e i suoi punti attesi.
La consigliata del confronto è quella MOSTRATA prima della scadenza (l'istantanea, `salva_istantanea`), con i punti attesi mostrati
allora (#614): `consigliata.origine` = "mostrata". Dove l'istantanea non c'è, o non si può più schierare con la rosa di oggi,
`consigliata` è la ricostruita ("ricostruita") e il Diario non dà un verdetto (`sintesi`, `scelte_tue`, `affidabilita`).
La ricostruita è la scelta rifatta dal modello a giornata finita con i soli dati che c'erano prima e con la rosa di oggi (le rose
passate non si conservano), senza le probabili che l'utente aveva davanti: sta sempre in `ricostruita`, come misura del modello.
Il calcolo è pesante: si fa solo per le giornate nuove (quando i voti di tutte le partite sono arrivati) e per quelle con voti o regole
cambiati, e il risultato resta in dati/diario.json."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

from . import avvisi, consigli, fasi, incertezza, rinvii, scelte
from . import indicatori_consiglio as ic
from . import verifica_consiglio as vc
from . import formazione as fz
from .blocco import BloccoFile
from .frasi import F, ConSegno, elenco as elenco_frasi, nome_giornata
from .lega import Rose
from .modello import Dati, Parametri, previsioni
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .punteggio import COLONNA_VOTO, fantavoto, modificatore_difesa
from .regole import RUOLI, Regole, serie_a_a_lega
from .verifica import MIN_GIOCATORI_ROSA

FILE = RADICE / "dati" / "diario.json"
MASSIMO_GIORNATE = 12
SIMULAZIONI = 300
MAX_ISTANTANEE = 60
# I numeri di tutta la rosa alla scadenza (`numeri_rosa`): servono solo al riepilogo di Oggi della giornata appena finita (#794)
MAX_NUMERI_ROSA = 4
# «L'ho messa» (#616): il campo della scelta salvata che dice «ho messo questi 11 nell'app della lega». `scelte.salva` lo scrive
# solo quando è vero (`messa: true`, con `messa_il`) e lo fa cadere se gli 11 cambiano. È l'unico punto dove il Diario lo legge:
# `schierata_confermata` dice se la scelta salvata è quella schierata davvero e ogni voce lo porta in `schierata.confermata`.
# Una scelta senza il campo (salvata prima di #616, o senza la spunta) vale None: non si sa, e il Diario fa come prima.
CAMPO_NELLA_LEGA: str | None = "messa"
_blocco = threading.Lock()
LOG = logging.getLogger(__name__)


def carica(percorso: Path | None = None) -> dict:
    try:
        d = json.loads((percorso or FILE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("giornate"), dict) else {"giornate": {}}
    except (OSError, ValueError):
        return {"giornate": {}}


def _scrivi(percorso: Path | None, voci: dict | None = None, istantanee: dict | None = None, cambi: dict | None = None,
            basi: dict | None = None, numeri: dict | None = None) -> None:
    """Aggiunge voci e/o istantanee al file ricaricandolo subito prima di scrivere: il calcolo del diario è lungo e nel frattempo
    la schermata della formazione può aver salvato un'istantanea nuova, che non va persa. Il blocco vale anche fra processi
    (servizio e comando del cron) e una voce con la formazione schierata non viene MAI sostituita da una che non ce l'ha:
    il cron, che ha calcolato su una copia vecchia, non cancella un «Ho schierato» arrivato nel frattempo dall'app.
    `basi` = {chiave: voce letta prima del calcolo (None se non c'era)}, da chi rifà le voci (il cron): se nel file la voce non è
    più quella e ha la formazione schierata, qualcuno (l'app: «Ho schierato», «Correggi») l'ha scritta mentre si calcolava, e vale
    la sua anche quando la voce nuova ha la schierata, fatta con la scelta di prima (#793).
    `cambi` = {chiave: cambio} (`indicatori_consiglio.cambio`): si aggiunge in fondo a quelli della giornata, al massimo
    `indicatori_consiglio.MAX_CAMBI` (gli ultimi), solo se l'istantanea nel file ha ancora i titolari di prima del cambio: due
    salvataggi della stessa consigliata nuova nello stesso momento (app e copia alla scadenza) contano un cambio solo.
    Stanno a parte, fuori dalle istantanee che l'app riceve. Così anche `numeri` = {chiave: numeri della rosa} (`numeri_rosa`),
    al massimo MAX_NUMERI_ROSA giornate."""
    file = percorso or FILE
    with _blocco, BloccoFile(file.with_name(file.name + ".lock")):
        d = carica(percorso)
        for chiave, nuova in (voci or {}).items():
            attuale = d["giornate"].get(chiave)
            if basi and chiave in basi and attuale != basi[chiave] and isinstance(attuale, dict) and attuale.get("schierata"):
                continue
            d["giornate"][chiave] = _unisci_voce(attuale, nuova)
        ist = d["istantanee"] if isinstance(d.get("istantanee"), dict) else {}
        if cambi:
            tutti = d["cambi"] if isinstance(d.get("cambi"), dict) else {}
            for chiave, c in cambi.items():
                attuale = ist.get(chiave) if isinstance(ist.get(chiave), dict) else {}
                if set(_ids(attuale.get("titolari"))) != set(c.get("prima") or []):
                    continue                            # qualcun altro l'ha già sovrascritta: il cambio è già contato
                prima = tutti.get(chiave) if isinstance(tutti.get(chiave), list) else []
                tutti[chiave] = (prima + [c])[-ic.MAX_CAMBI:]
            for vecchia in chiavi_vecchie(tutti, MAX_ISTANTANEE):
                tutti.pop(vecchia, None)
            d["cambi"] = tutti
        if istantanee:
            ist.update(istantanee)
            for vecchia in chiavi_vecchie(ist, MAX_ISTANTANEE):
                ist.pop(vecchia, None)
            d["istantanee"] = ist
        if numeri:
            tenuti = d["numeri_rosa"] if isinstance(d.get("numeri_rosa"), dict) else {}
            tenuti.update(numeri)
            for vecchia in chiavi_vecchie(tenuti, MAX_NUMERI_ROSA):
                tenuti.pop(vecchia, None)
            d["numeri_rosa"] = tenuti
        scrivi_sicuro(file, json.dumps(d, ensure_ascii=False))


def _unisci_voce(vecchia, nuova: dict) -> dict:
    """La voce da tenere per una giornata: la nuova, tranne quando quella già nel file ha la formazione schierata e la nuova no.
    In quel caso resta la vecchia, completata con i numeri per giocatore della nuova se le mancavano."""
    if isinstance(vecchia, dict) and vecchia.get("schierata") and not nuova.get("schierata"):
        return vecchia if "giocatori" in vecchia or "giocatori" not in nuova else {**vecchia, "giocatori": nuova["giocatori"]}
    return nuova


def _giocatore(x: dict) -> dict:
    """Un giocatore dell'istantanea, con i numeri mostrati allora (`p_voto`, `fv_atteso`) se la formazione li aveva: servono a
    «Quanto ci abbiamo preso» (precisione.py) per confrontare quello che l'app ha detto con quello che è successo."""
    g = {"id": int(x["id"]), "nome": str(x.get("nome", ""))[:60], "ruolo": str(x.get("ruolo", ""))[:1]}
    for k, cifre in (("p_voto", 3), ("fv_atteso", 2)):
        v = x.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v:
            g[k] = round(float(v), cifre)
    return g


def _adesso() -> datetime:
    return datetime.now()


def salva_istantanea(f: dict, stagione: str, percorso: Path | None = None) -> bool:
    """Ricorda la formazione consigliata di una giornata (modulo, 11 titolari, panchina in ordine, punti attesi, stile, ora del calcolo):
    circa 1 KB per giornata, una sola per giornata. Chi chiama la usa solo finché la formazione è aperta; dopo la scadenza non si
    chiama più e quella già salvata resta com'è (congelata). True se ha scritto.
    Per gli indicatori del consiglio (`indicatori_consiglio.py`): `misure` = C3 e C4 di questa consigliata; quando l'istantanea si
    sovrascrive con titolari diversi si registra il cambio (C2), a parte.
    A parte anche i numeri di tutta la rosa (`f["schede"]`, vedi `numeri_rosa`), congelati alla scadenza come l'istantanea."""
    g = f.get("giornata")
    tit = [_giocatore(x) for x in f.get("titolari", []) if isinstance(x, dict) and "id" in x]
    if not isinstance(g, int) or len(tit) != 11:
        return False
    stile = next((l.get("nome") for l in f.get("livelli", []) if l.get("rischio") == 0), None)
    nuova = {"giornata": g, "modulo": str(f.get("modulo", ""))[:8], "titolari": tit,
             "panchina": [_giocatore(x) for x in f.get("panchina", []) if isinstance(x, dict) and "id" in x][:12],
             "atteso": round(float(f.get("punteggio_atteso", 0.0)), 1), "stile": stile}
    if (m := ic.misure(f)) is not None:
        nuova["misure"] = m
    chiave = f"{stagione}/{g}"
    d = carica(percorso)
    prima = d.get("istantanee")
    vecchia = prima.get(chiave) if isinstance(prima, dict) else None
    numeri = [{k: v for k, v in _giocatore(x).items() if k != "nome"}
              for x in (f.get("schede") or {}).values() if isinstance(x, dict) and "id" in x][:MAX_GIOCATORI_VOCE]
    numeri = {chiave: numeri} if numeri and numeri != (d.get("numeri_rosa") or {}).get(chiave) else None
    if isinstance(vecchia, dict) and {k: v for k, v in vecchia.items() if k != "calcolata"} == nuova:
        if numeri:
            _scrivi(percorso, numeri=numeri)
        return bool(numeri)
    nuova["calcolata"] = _adesso().isoformat(timespec="seconds")
    c = ic.cambio(vecchia, f, nuova["calcolata"]) if isinstance(vecchia, dict) else None
    _scrivi(percorso, istantanee={chiave: nuova}, cambi={chiave: c} if c else None, numeri=numeri)
    return True


def numeri_rosa(percorso: Path | None, stagione: str, giornata: int) -> dict[int, dict]:
    """{id: {ruolo, p_voto, fv_atteso}} della rosa alla scadenza della giornata, come li mostrava l'app: i numeri di tutta la rosa
    (`f["schede"]`) e, per le giornate salvate prima che ci fossero, quelli che l'istantanea ha (titolari e panchina). Per la
    panchina del riepilogo di Oggi, scelta con questi numeri congelati (#794). Vuoto se non c'è niente."""
    d = carica(percorso)
    chiave = f"{stagione}/{giornata}"
    ist = (d.get("istantanee") or {}).get(chiave) if isinstance(d.get("istantanee"), dict) else None
    righe = [x for x in ((ist or {}).get("titolari") or []) + ((ist or {}).get("panchina") or []) if isinstance(x, dict)]
    tutti = (d.get("numeri_rosa") or {}).get(chiave) if isinstance(d.get("numeri_rosa"), dict) else None
    righe += [x for x in tutti or [] if isinstance(x, dict)]
    return {x["id"]: {k: x[k] for k in ("ruolo", "p_voto", "fv_atteso")} for x in righe
            if isinstance(x.get("id"), int) and all(_numero(x.get(k)) is not None for k in ("p_voto", "fv_atteso")) and x.get("ruolo") in RUOLI}


def impronta_regole(regole: Regole, stagione: str | None = None, giornata: int | None = None, fuori_turno: bool = False) -> str:
    """Impronta (hash corto) di ciò che cambia i punti fatti: fonte del voto, bonus/malus, panchina, modificatore, voto d'ufficio, moduli
    e, con stagione e giornata, la regola delle partite rinviate di quella giornata, solo se la giornata ha partite fuori dal turno
    (`fuori_turno`) e la regola non è «aspetta», il predefinito: così le altre voci non si rifanno mai. Salvata con ogni voce: se la lega cambia una di queste regole, le voci
    calcolate si rifanno da sole."""
    d = asdict(regole)
    parti = {k: d.get(k) for k in ("fonte_voto", "bonus", "panchina", "modificatore_difesa", "voto_senza_sostituto", "moduli")}
    if giornata is not None and fuori_turno:
        r = rinvii.regola(regole, stagione or "", giornata)
        if r["modo"] != "aspetta":
            parti["rinvio"] = [r["modo"], r["valore"]]
    return hashlib.sha1(json.dumps(parti, sort_keys=True).encode("utf-8")).hexdigest()[:12]


# Ciò che cambia i punti fatti, riga per riga della tabella `voti`: i voti e i fantavoti di ogni fonte e i bonus e malus che legge
# `punteggio.fantavoto`. Non nome, squadra e ruolo, né le colonne che il modello aggiunge ai voti (data della partita, `t`).
_COLONNE_VOTI = ("calciatore_id", "voto_red", "fv_red", "voto_stat", "fv_stat", "voto_ita", "fv_ita", "gol", "gol_subiti", "autogol",
                 "rig_segnati", "rig_sbagliati", "rig_parati", "assist", "mvp", "ammonizioni", "espulsioni")
INTERNI = ("impronta_voti",)          # campi della voce che restano nel file: web e iPhone non li ricevono (`per_i_client`)


def _valore(x):
    """Un valore della riga dei voti in una forma sola: 0 e 0.0 uguali (il tipo di una colonna può cambiare da un caricamento
    all'altro), vuoto (None o NaN) = None."""
    if x is None or isinstance(x, str):
        return x
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    return None if f != f else round(f, 4)


def impronta_voti(d: Dati, stagione: str, giornata: int) -> str:
    """Impronta (hash corto) dei voti di una giornata, tutta la Serie A (non solo la rosa: cambiare la rosa non rifà le voci), dagli
    stessi dati da cui escono i punti fatti (`d.voti`). Salvata con ogni voce (`impronta_voti`): se i voti della giornata cambiano
    (l'ultima partita arrivata dopo il calcolo, una correzione dei giorni dopo) la voce si rifà da sola (#793)."""
    v = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] == giornata)]
    colonne = [c for c in _COLONNE_VOTI if c in v.columns]
    righe = sorted(json.dumps([_valore(x) for x in r]) for r in v[colonne].itertuples(index=False, name=None))
    return hashlib.sha1(json.dumps([colonne, righe]).encode("utf-8")).hexdigest()[:12]


def per_i_client(voce: dict) -> dict:
    """La voce come la ricevono web e iPhone: senza i campi interni (`INTERNI`). Una copia: la voce passata resta com'è (può stare
    nella cache dei calcoli)."""
    return {k: v for k, v in voce.items() if k not in INTERNI}


def _riga(titolari: list[fz.Giocatore], stat: tuple, reale: float, dettaglio: dict) -> dict:
    """`stat` = (atteso, dev simulata) dal Valutatore; la fascia è quella calibrata (incertezza.py). `dettaglio`: da dove vengono i
    punti fatti (`_dettaglio`)."""
    conta = {r: sum(1 for g in titolari if g.ruolo == r) for r in RUOLI}
    atteso, dev = stat[0], stat[1]
    return {"modulo": f"{conta['D']}-{conta['C']}-{conta['A']}", "atteso": round(atteso, 1), "reale": round(reale, 1),
            "dev_simulata": round(dev, 1), "intervallo": incertezza.intervallo(atteso, dev),
            "titolari": [_breve(g) for g in titolari], "dettaglio": dettaglio}


def _breve(g: fz.Giocatore) -> dict:
    return {"id": g.id, "nome": g.nome, "ruolo": g.ruolo}


def _dettaglio(titolari: list[fz.Giocatore], panchina: list[fz.Giocatore], gioca: dict, fv: dict, voto: dict, regole: Regole,
               rinviati=frozenset(), r_rinvio: dict | None = None) -> dict:
    """Da dove vengono i punti fatti di una formazione, per spiegarli nella pagina Giornate (#900, `spiegazione_punti`): i punti
    sono i fantavoti di chi va a punteggio, più il voto di chi resta senza sostituto, più il modificatore difesa
    (`formazione.punteggio`). `entrati` = [{esce, entra, fv}]: chi è entrato dalla panchina, al posto di chi e con quale fantavoto;
    `senza_sostituto` = i titolari senza voto per cui non è entrato nessuno, `voto_senza_sostituto` = quanto conta ciascuno per la
    lega (null = zero, o nessuno senza sostituto); `modificatore` = il modificatore difesa (null se la lega non lo usa); `rinvio`
    (solo se c'è) = chi aveva la partita rinviata e la regola della lega che ha contato: {modo: "voto_ufficio" (chi ha preso il
    voto fisso `valore`) o "senza_voto" (i titolari rimasti senza voto per questo), valore, giocatori}.
    Chi entra al posto di chi: `chi_va_a_punteggio` tratta i mancanti in ordine di ruolo, uno dopo l'altro; rifacendo il conto con
    i primi k mancanti si vede chi è entrato al k-esimo (lo stesso algoritmo dei punti, nessuna regola riscritta qui; come
    `fasi.andamento`). Il calcolo dei punti non cambia: questa funzione li legge soltanto."""
    ids_tit = {t.id for t in titolari}
    mancanti = sorted([t for t in titolari if not gioca[t.id]], key=lambda t: fz.ORDINE_RUOLO[t.ruolo])
    entrati, senza, usati = [], [], set()
    for k, m in enumerate(mancanti, start=1):
        va_k, _ = fz.chi_va_a_punteggio(titolari, panchina, gioca | {x.id: True for x in mancanti[k:]}, regole)
        nuovo = next((x for x in va_k if x.id not in ids_tit and x.id not in usati), None)
        if nuovo is None:
            senza.append(_breve(m))
        else:
            usati.add(nuovo.id)
            entrati.append({"esce": _breve(m), "entra": _breve(nuovo), "fv": round(float(fv[nuovo.id]), 2)})
    va, _ = fz.chi_va_a_punteggio(titolari, panchina, gioca, regole)
    modificatore = None
    if regole.modificatore_difesa.attivo:
        modificatore = round(float(modificatore_difesa(next((voto[x.id] for x in va if x.ruolo == "P"), None),
                                                       [voto[x.id] for x in va if x.ruolo == "D"], regole)), 2)
    vss = regole.voto_senza_sostituto
    out = {"entrati": entrati, "senza_sostituto": senza, "voto_senza_sostituto": float(vss) if senza and vss is not None else None,
           "modificatore": modificatore}
    modo = (r_rinvio or {}).get("modo")
    if modo in ("voto_ufficio", "senza_voto"):
        chi = [x for x in va if x.id in rinviati] if modo == "voto_ufficio" else [t for t in titolari if t.id in rinviati and not gioca[t.id]]
        if chi:
            valore = float(r_rinvio["valore"] if r_rinvio["valore"] is not None else 6.0) if modo == "voto_ufficio" else None
            out["rinvio"] = {"modo": modo, "valore": valore, "giocatori": [_breve(x) for x in chi]}
    return out


def schierata_confermata(scelta: dict | None) -> bool | None:
    """Se la scelta salvata dice che l'utente l'ha messa nell'app della lega (`CAMPO_NELLA_LEGA`): True; None se non si sa (la
    scelta non ha il campo: salvata prima che esistesse, o senza la spunta «L'ho messa»). False solo se il campo c'è ed è falso,
    cosa che `scelte.salva` oggi non scrive."""
    if not isinstance(scelta, dict) or CAMPO_NELLA_LEGA is None or CAMPO_NELLA_LEGA not in scelta:
        return None
    return bool(scelta[CAMPO_NELLA_LEGA])


def _mostrata(istantanea: dict | None, riga_di) -> dict | None:
    """La riga della consigliata MOSTRATA prima della scadenza (l'istantanea), se si può ancora schierare con la rosa di oggi:
    i suoi titolari e la sua panchina con i punti fatti, e i punti attesi mostrati allora (`atteso` dell'istantanea; se manca,
    quelli ricalcolati). None se l'istantanea non c'è o non si può più schierare."""
    if not isinstance(istantanea, dict):
        return None
    riga = riga_di({"titolari": _ids(istantanea.get("titolari")), "panchina": _ids(istantanea.get("panchina"))})
    if riga is None:
        return None
    atteso = istantanea.get("atteso")
    if isinstance(atteso, (int, float)) and not isinstance(atteso, bool) and atteso > 0:
        riga["atteso"] = round(float(atteso), 1)
        riga["intervallo"] = incertezza.intervallo(riga["atteso"], riga["dev_simulata"])
    return riga | {"origine": "mostrata"}


def _come_la_mostrata(riga: dict | None, sc: dict | None, consigliata: dict, istantanea: dict | None) -> dict | None:
    """La riga di una formazione dell'utente (schierata o copia automatica) con gli stessi undici della consigliata MOSTRATA e
    senza una panchina sua (o con la stessa panchina mostrata): è quella formazione, quindi ne prende la panchina e i punti attesi
    mostrati allora. Altrimenti la riga resta com'è. Senza questo la stessa formazione aveva due numeri, la panchina e gli attesi
    rifatti a giornata finita da una parte e quelli mostrati dall'altra, e il Diario dava un verdetto fra due uguali."""
    if riga is None or consigliata.get("origine") != "mostrata" or set(_ids(riga["titolari"])) != set(_ids(consigliata["titolari"])):
        return riga
    propria = [int(i) for i in (sc or {}).get("panchina") or []]
    if propria and propria != _ids((istantanea or {}).get("panchina")):
        return riga
    return riga | {k: consigliata[k] for k in ("atteso", "reale", "dev_simulata", "intervallo", "dettaglio") if k in consigliata}


ALLORA_FUORI = ("non_salvata", "fuori_rosa", "non_valutabile")      # perché la consigliata di allora non entra nel confronto (#674)


def _allora_al_calcolo(istantanea: dict | None, consigliata: dict, ruoli: dict) -> str:
    """Al calcolo della voce, il valore di `consigliata_di_allora` (vedi `consigliata_di_allora`): "fuori_rosa" se fra i titolari
    dell'istantanea c'è chi non si può più schierare perché non è nella rosa di oggi (`ruoli`, quelli di `riga_di`), "non_valutabile"
    se sono tutti in rosa ma non si può schierare lo stesso (modulo o ruoli che la lega non ammette più)."""
    if consigliata.get("origine") == "mostrata":
        return "mostrata"
    ids = _ids(istantanea.get("titolari")) if isinstance(istantanea, dict) else []
    if not ids:
        return "non_salvata"
    return "fuori_rosa" if any(i not in ruoli for i in ids) else "non_valutabile"


def consigliata_di_allora(voce: dict) -> str:
    """La consigliata mostrata prima della scadenza (l'istantanea), per una voce: "mostrata" = è la consigliata della voce, quindi
    c'è il confronto; "non_salvata" = non era stata salvata; "fuori_rosa" = salvata, ma fra i suoi titolari c'è chi non è più nella
    rosa; "non_valutabile" = salvata ma non si può più valutare per un altro motivo (modulo o ruoli che la lega non ammette più),
    oppure la voce è stata scritta prima di #674 e il motivo non lo ricorda. Lo dice il campo scritto al calcolo; per le voci di
    prima lo si ricava dall'istantanea (`elenco` la mette nella voce). I client usano questo campo, non `consigliata.origine`."""
    if _con_mostrata(voce):
        return "mostrata"
    scritto = voce.get("consigliata_di_allora")
    if scritto in ALLORA_FUORI:
        return scritto
    ist = voce.get("istantanea")
    return "non_valutabile" if isinstance(ist, dict) and _ids(ist.get("titolari")) else "non_salvata"


def nota_consigliata(voce: dict) -> dict:
    """La frase della pagina Giornate sulla consigliata di allora che non entra nel confronto: con la tua formazione «Qui il
    confronto con la consigliata non c'è: …», senza (quando i punti sono della consigliata rifatta a giornata finita) «Questa è
    rifatta con i dati di allora: …», con il perché giusto (#674). Null con la consigliata mostrata e con la copia fatta alla
    scadenza. {"nota_consigliata": testo, "nota_consigliata_frase": {chiave, param}}."""
    allora, frase = consigliata_di_allora(voce), None
    if allora != "mostrata":
        perche = F("diario.allora_" + allora)
        if voce.get("schierata"):
            frase = F("diario.senza_confronto", perche=perche)
        elif not voce.get("automatica"):
            frase = F("diario.rifatta", perche=perche)
    return {"nota_consigliata": str(frase) if frase else None, "nota_consigliata_frase": frase.json() if frase else None}


def _conta_fuori(voci: list[dict]) -> dict:
    """{motivo: giornate} delle voci fuori dal confronto, per `nota_confronto`."""
    conta: dict = {}
    for v in voci:
        m = consigliata_di_allora(v)
        conta[m] = conta.get(m, 0) + 1
    return conta


def _stessa_formazione(voce: dict) -> bool:
    """Vero se la formazione schierata ha gli stessi undici della consigliata della voce (l'ordine non conta). Senza i titolari
    non si sa: falso."""
    s, c = voce.get("schierata"), voce.get("consigliata")
    if not isinstance(s, dict) or not isinstance(c, dict):
        return False
    tua = set(_ids(s.get("titolari")))
    return bool(tua) and tua == set(_ids(c.get("titolari")))


def _con_mostrata(voce: dict) -> bool:
    """Vero se la consigliata della voce è quella mostrata prima della scadenza: solo allora il confronto dà un verdetto."""
    c = voce.get("consigliata")
    return isinstance(c, dict) and c.get("origine") == "mostrata"


def _previsti_e_veri(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, anche=frozenset()):
    """(previsioni ricostruite con i soli dati di prima, voti veri, {id: fantavoto vero} di chi ha preso voto) di una giornata
    finita, solo per le partite giocate e per quelle in `anche` (partite rinviate non ancora recuperate, che la regola della lega
    conta senza voto o con il voto d'ufficio); None se mancano i dati."""
    col = COLONNA_VOTO[regole.fonte_voto]
    prev = previsioni(d, stagione, giornata, regole, par)
    giocate = d.partite.loc[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == giornata) & (d.partite["giocata"] == 1), "id"]
    if prev.empty or giocate.empty:
        return None
    prev = prev[prev["partita"].isin(set(giocate) | set(anche))].set_index("id")
    reali = d.voti[(d.voti["stagione"] == stagione) & (d.voti["giornata"] == giornata)].drop_duplicates("calciatore_id").set_index("calciatore_id")
    fv_vero = {i: fantavoto(reali.loc[i].to_dict(), prev.at[i, "ruolo"], regole)
               for i in prev.index if i in reali.index and pd.notna(reali.at[i, col])}
    return prev, reali, fv_vero


MAX_GIOCATORI_VOCE = 60          # rosa + chi era nella consigliata di allora: il tetto tiene piccolo il file anche con rose strane


def _fv_della_lega(prev: pd.DataFrame, fv_vero: dict, r_rinvio: dict) -> tuple[dict, dict]:
    """({id: fantavoto che la lega ha contato}, {id: regola}) di una giornata finita. Chi aveva la partita rinviata, con «senza
    voto» o con il voto d'ufficio, ha il voto della regola della lega (`rinvii.voti_lega`: nessuno o quello fisso) anche se il
    recupero si è giocato, e la regola nel secondo dizionario; gli altri il voto vero. Con «aspetta» la lega conta il voto del
    recupero: sono i voti veri. `prev` = le previsioni con la regola applicata (`rinvii.applica`, colonna `rinvio`)."""
    if r_rinvio["modo"] == "aspetta" or "rinvio" not in prev.columns:
        return fv_vero, {}
    coinvolti = [int(i) for i in prev.index[prev["rinvio"].notna()]]
    gioca, fv = {i: i in fv_vero for i in coinvolti}, dict(fv_vero)
    rinvii.voti_lega(gioca, fv, {}, coinvolti, r_rinvio)
    return {i: x for i, x in fv.items() if gioca.get(i, True)}, dict.fromkeys(coinvolti, r_rinvio["modo"])


def _numeri_giocatori(prev: pd.DataFrame, fv_lega: dict, ids, rinvio: dict | None = None, senza: dict | None = None) -> list[dict]:
    """Per la tabella degli 11 della pagina Giornate e per «Quanto ci abbiamo preso»: per ogni giocatore la probabilità di voto e il
    fantavoto atteso RICOSTRUITI con i dati di prima e il fantavoto che la lega ha contato (`fv`, null = nessun voto; vedi
    `_fv_della_lega`). Chi aveva la partita rinviata e ha il voto della regola della lega ha in più `rinvio` (la regola, da
    `rinvio` = {id: regola}): quel voto non è del campo, quindi non si confronta con l'atteso. Circa 60 byte a giocatore.
    Chi non ha una previsione ricostruita (`senza` = {id: fantavoto contato dalla lega o None}, `_numeri_senza_previsione`) c'è con
    `p_voto` e `fv_atteso` null: il suo voto conta nei punti, quindi sta anche nella tabella, con l'atteso vuoto («–»); «Quanto ci
    abbiamo preso» lo lascia fuori (`precisione.numeri_giornata`)."""
    out = []
    for i in dict.fromkeys(int(x) for x in ids):
        if i in prev.index:
            riga = {"id": i, "p_voto": round(float(prev.at[i, "p_voto"]), 3), "fv_atteso": round(float(prev.at[i, "mu"]), 2),
                    "fv": round(float(fv_lega[i]), 2) if i in fv_lega else None}
        elif senza and i in senza:
            riga = {"id": i, "p_voto": None, "fv_atteso": None, "fv": senza[i]}
        else:
            continue
        out.append(riga | ({"rinvio": rinvio[i]} if rinvio and i in rinvio else {}))
    return out[:MAX_GIOCATORI_VOCE]


def _numeri_senza_previsione(extra, gioca: dict, fv: dict, rinviati, r_rinvio: dict) -> tuple[dict, dict]:
    """({id: fantavoto che la lega ha contato, o None se nessun voto}, {id: regola dei rinvii}) di chi non ha una previsione
    ricostruita (`extra`, da `_senza_previsione`), dai voti già passati per la regola della lega (`rinvii.voti_lega`): i numeri
    di `_numeri_giocatori` per loro. Con «aspetta» nessuno ha la regola."""
    senza = {int(i): round(float(fv[i]), 2) if gioca.get(i) else None for i in extra}
    rinvio = {int(i): r_rinvio["modo"] for i in extra if i in rinviati} if r_rinvio["modo"] != "aspetta" else {}
    return senza, rinvio


def numeri_giocatori(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, ids,
                     giocatori_rosa: dict[int, tuple[str, str | None]] | None = None) -> list[dict] | None:
    """Solo i numeri per giocatore di una giornata finita, senza simulazioni, con la regola della lega per le partite rinviate come
    in `calcola_giornata`: completa le voci scritte prima che ci fossero e dice se i voti sono cambiati (`_stessi_voti`).
    Con `giocatori_rosa` ({id: (nome, ruolo)}, come in `calcola_giornata`) ci sono anche quelli di `ids` senza una previsione."""
    r_rinvio = rinvii.regola(regole, stagione, giornata)
    rinviate = rinvii.id_fuori_turno(d.partite, stagione, giornata)
    pv = _previsti_e_veri(d, stagione, giornata, regole, par, rinviate if r_rinvio["modo"] != "aspetta" else frozenset())
    if pv is None:
        return None
    prev, reali, fv_vero = pv
    fv_lega, rinvio = _fv_della_lega(rinvii.applica(prev, rinviate, r_rinvio), fv_vero, r_rinvio)
    chiesti = {int(i) for i in ids}
    gioca, fv, voto = {}, {}, {}
    extra, extra_rinviati = _senza_previsione(d, {i: x for i, x in (giocatori_rosa or {}).items() if i in chiesti}, prev.index,
                                              reali, COLONNA_VOTO[regole.fonte_voto], regole, rinviate, r_rinvio, gioca, fv, voto)
    rinvii.voti_lega(gioca, fv, voto, extra_rinviati, r_rinvio)
    senza, rinvio_senza = _numeri_senza_previsione(extra, gioca, fv, set(extra_rinviati), r_rinvio)
    return _numeri_giocatori(prev, fv_lega, ids, rinvio | rinvio_senza, senza)


def _senza_previsione(d: Dati, giocatori_rosa, rosa, reali: pd.DataFrame, col: str, regole: Regole, rinviate, r_rinvio: dict,
                      gioca: dict, fv: dict, voto: dict) -> tuple[dict, list[int]]:
    """Chi è in rosa (`giocatori_rosa`) ma non fra chi ha una previsione ricostruita per la giornata (`rosa`, gli id) (mai sceso in
    campo prima, #447): {id: Giocatore} che non
    prende mai voto nelle simulazioni, con il voto vero se l'ha preso (scritto in `gioca`, `fv`, `voto`), e gli id di chi giocava
    una partita rinviata, trovata dal suo club (`d.calciatori` e `d.partite`), per la regola della lega (`rinvii.voti_lega`). Con il
    voto d'ufficio la lega glielo dà di sicuro: allora prende voto sempre, con quel voto (come `rinvii.applica` per gli altri)."""
    extra, rinviati = {}, []
    club, club_rinviati = {}, set()
    if r_rinvio["modo"] != "aspetta" and rinviate:
        cal, partite = getattr(d, "calciatori", None), d.partite
        if cal is not None and {"id", "squadra_slug"} <= set(cal.columns) and {"casa", "trasferta"} <= set(partite.columns):
            club = dict(zip(cal["id"].astype(int), cal["squadra_slug"]))
            righe = partite[partite["id"].isin(rinviate)]
            club_rinviati = set(righe["casa"]) | set(righe["trasferta"])
    for i, (nome, ruolo) in (giocatori_rosa or {}).items():
        if i in rosa or ruolo not in RUOLI:
            continue
        ha_voto = i in reali.index and pd.notna(reali.at[i, col])
        gioca[i] = bool(ha_voto)
        fv[i] = float(fantavoto(reali.loc[i].to_dict(), ruolo, regole)) if ha_voto else 0.0
        voto[i] = float(reali.at[i, col]) if ha_voto else 0.0
        p = mu = 0.0
        if club.get(i) in club_rinviati:
            rinviati.append(i)
            if r_rinvio["modo"] == "voto_ufficio":
                p, mu = 1.0, float(r_rinvio["valore"] if r_rinvio["valore"] is not None else 6.0)
        extra[i] = fz.Giocatore(i, nome, ruolo, p, mu, mu)
    return extra, rinviati


def _voti_veri(d: Dati, rosa: dict, giocatori_rosa, prev: pd.DataFrame, reali: pd.DataFrame, fv_vero: dict, regole: Regole,
               rinviate, r_rinvio: dict) -> tuple[dict, dict, dict, dict, frozenset]:
    """(gioca, fv, voto, chi non ha previsione, chi aveva la partita rinviata) di una giornata finita per i giocatori di `rosa`
    ({id: Giocatore}, con una previsione) e di `giocatori_rosa` ({id: (nome, ruolo)}) che una previsione non ce l'hanno
    (`_senza_previsione`), con la regola della lega per le partite rinviate (`rinvii.voti_lega`)."""
    col = COLONNA_VOTO[regole.fonte_voto]
    gioca = {i: i in fv_vero for i in rosa}
    fv = {i: fv_vero.get(i, 0.0) for i in rosa}
    voto = {i: float(reali.at[i, col]) if i in fv_vero else 0.0 for i in rosa}
    extra, extra_rinviati = _senza_previsione(d, giocatori_rosa, rosa, reali, col, regole, rinviate, r_rinvio, gioca, fv, voto)
    rinviati = [i for i in rosa if prev.at[i, "rinvio"] is not None] + extra_rinviati
    rinvii.voti_lega(gioca, fv, voto, rinviati, r_rinvio)
    return gioca, fv, voto, extra, frozenset(rinviati)


def _punti_s2(d: Dati, stagione: str, giornata: int, regole: Regole, rosa: list, gioca: dict, fv: dict, voto: dict,
              simulazioni: int) -> float | None:
    """I punti fatti da S2 (la scelta semplice di `verifica_consiglio`) con la rosa `rosa`; None se in qualche ruolo nessuno."""
    ha_giocato, fantamedia = vc.dati_s2(d, stagione, giornata, regole)
    try:
        s2 = fz.migliore(vc.rosa_s2(rosa, ha_giocato, fantamedia), regole, simulazioni)
        return round(fz.punteggio(s2.titolari, s2.panchina, gioca, fv, voto, regole), 1)
    except ValueError:                    # in qualche ruolo nessuno: S2 non si può formare
        return None


def calcola_giornata(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, ids_rosa: list[int],
                     scelta: dict | None, simulazioni: int = SIMULAZIONI, automatica: dict | None = None,
                     altri_ids=(), istantanea: dict | None = None, cambi: tuple | None = None,
                     indicatori: bool = True, giocatori_rosa: dict[int, tuple[str, str | None]] | None = None,
                     tieni: dict | None = None, completa: bool = False, ceduti=()) -> dict | None:
    """La voce del diario di una giornata finita, o None se mancano i dati (o la rosa è troppo piccola per quella giornata).
    Con `tieni` (una voce già scritta) non la rifà da zero: ne rifà solo i punti (`rifai_i_punti`); con anche `completa` (per dare
    il dettaglio dei punti a una voce di prima, `_con_il_dettaglio`) il dettaglio di una formazione è null se la sua panchina di
    allora non si conosce intera e la panchina ha contato.
    `altri_ids`: chi era nella consigliata di allora (istantanea) o fra i titolari della tua formazione ma non è più in rosa, per
    i numeri per giocatore. `ceduti`: i titolari della tua formazione (schierata o copia alla scadenza) non più in rosa; con
    `tieni` si contano nelle formazioni da ricontare.
    `giocatori_rosa`: {id: (nome, ruolo)} di tutta la rosa. Chi non ha una previsione per quella giornata (mai sceso in campo prima,
    come spesso il portiere di riserva) si può schierare lo stesso (#447, la regola di `scelte.ruoli_schierabili` a giornata finita):
    entra nella schierata senza voto atteso e con il suo voto vero, se l'ha preso. La consigliata non lo usa.
    `istantanea` = la consigliata mostrata prima della scadenza: se si può ancora schierare è la `consigliata` della voce
    (`origine` "mostrata"), altrimenti lo è la ricostruita, che resta sempre anche in `ricostruita` (vedi in cima al file).
    `istantanea` e `cambi` (C2 già contato, `indicatori_consiglio.conta_cambi`) servono anche agli indicatori del consiglio della
    voce (`consiglio`, vedi `_consiglio`). Gli indicatori non fermano mai la voce: se il loro calcolo non riesce (o `indicatori`
    è falso, perché non si sono potuti preparare) la voce si scrive senza `consiglio`."""
    # partite rinviate (fuori dal turno, recuperate o no): la regola della lega per quella giornata, come prima della scadenza
    r_rinvio = rinvii.regola(regole, stagione, giornata)
    rinviate = rinvii.id_fuori_turno(d.partite, stagione, giornata)
    pv = _previsti_e_veri(d, stagione, giornata, regole, par, rinviate if r_rinvio["modo"] != "aspetta" else frozenset())
    if pv is None:
        return None
    prev, reali, fv_vero = pv
    numeri_prev = prev                    # «Quanto ci abbiamo preso» misura il modello: numeri di prima della regola dei rinvii
    prev = rinvii.applica(prev, rinviate, r_rinvio)
    fv_lega, rinvio_numeri = _fv_della_lega(prev, fv_vero, r_rinvio)      # ... e i voti che la lega ha contato
    ids = [i for i in ids_rosa if i in prev.index]
    if len(ids) < MIN_GIOCATORI_ROSA:
        return None
    rosa = {int(i): fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                                 float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids}
    lista = list(rosa.values())
    # con `tieni` (le formazioni di allora, da ricontare) si conta anche chi le aveva fra i titolari e non è più in rosa (`ceduti`:
    # per esempio un titolare della formazione salvata ceduto prima del recupero, seconda revisione di #947), con i suoi numeri di
    # quella giornata. La consigliata non si sceglie di nuovo, quindi non lo usa mai
    fuori_rosa = {i: fz.Giocatore(i, prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]),
                              float(prev.at[i, "mu_voto"]))
              for i in dict.fromkeys(int(x) for x in ceduti) if tieni is not None and i in prev.index and i not in rosa}
    gioca, fv, voto, extra, rinviati = _voti_veri(d, rosa | fuori_rosa, giocatori_rosa, prev, reali, fv_vero, regole, rinviate, r_rinvio)
    tutti = rosa | fuori_rosa | extra
    ruoli = {i: g.ruolo for i, g in tutti.items()}
    # chi non ha una previsione sta anche nella tabella degli 11, con il voto che conta nei punti e l'atteso vuoto
    senza, rinvio_senza = _numeri_senza_previsione(extra, gioca, fv, rinviati, r_rinvio)
    ids_numeri = list(ids) + list(senza) + list(altri_ids)

    def fatti(tit: list[fz.Giocatore], panc: list[fz.Giocatore]) -> tuple[float, dict]:
        """(punti fatti, da dove vengono) di una formazione: i punti sono quelli di sempre (`formazione.punteggio`)."""
        return fz.punteggio(tit, panc, gioca, fv, voto, regole), _dettaglio(tit, panc, gioca, fv, voto, regole, rinviati, r_rinvio)

    def formazione(scelti: list[int], panchina) -> tuple[list[fz.Giocatore], list[fz.Giocatore]]:
        """(titolari, panchina) di una formazione con i giocatori di questa giornata e della rosa di oggi (`tutti`): la panchina sua,
        se la conosciamo (giornate importate), altrimenti quella del sistema. La usano la voce (`riga_di`) e i soli punti di una
        voce già scritta (`tieni`): lo stesso insieme di giocatori, così il numero non cambia fra «Correggi» e il giro del cron."""
        tit = [tutti[i] for i in scelti]
        propria = [tutti[i] for i in dict.fromkeys(int(i) for i in panchina if i in tutti and i not in scelti)]
        # la panchina del sistema pesca anche chi non ha previsione solo se la formazione ne usa qualcuno: le altre restano come prima
        lista_v = lista + list(extra.values()) if any(g.id in extra for g in tit + propria) else lista
        return tit, propria or fz._panchina(lista_v, tit, regole)

    if tieni is not None:
        def punti(scelti: list[int], panchina=()) -> tuple[float, dict | None] | None:
            if not scelti or any(i not in tutti for i in scelti):
                return None                     # un titolare non è più in rosa: come in «Correggi», la formazione non si rifà
            reale, dettaglio = fatti(*formazione(scelti, panchina))
            # senza la panchina di allora, intera (dall'istantanea o dalla scelta), quella del sistema rifatta con la rosa e il modello
            # di oggi può far entrare un altro giocatore con lo stesso voto: i punti tornano, chi è entrato no (revisione di #905).
            # Per una voce di prima allora il dettaglio vale solo se la panchina non ha contato
            nota = bool(panchina) and all(int(i) in tutti for i in panchina)
            if completa and not nota and (dettaglio["entrati"] or dettaglio["senza_sostituto"]):
                dettaglio = None
            return round(reale, 1), dettaglio
        impronte = {"regole": impronta_regole(regole, stagione, giornata, bool(rinviate)),
                    "impronta_voti": impronta_voti(d, stagione, giornata)}
        nuova = _solo_punti(tieni, punti, istantanea, scelta, automatica)
        if nuova is not None and isinstance(nuova.get("consiglio"), dict):
            try:
                nuova["consiglio"]["punti_s2"] = _punti_s2(d, stagione, giornata, regole, lista, gioca, fv, voto, simulazioni)
            except Exception as e:  # noqa: BLE001 - S2 non si rifà: allora non cambia nessun numero della voce
                _senza_indicatori(e)
                nuova = None
        if nuova is None:
            # i numeri che si confrontano (schierata, consigliata, ricostruita, S2) cambiano tutti insieme o nessuno (ricontrollo di
            # #798): uno non si rifà, quindi la voce resta com'era, con le impronte di adesso perché i giri dopo non ci riprovino
            return json.loads(json.dumps(tieni)) | impronte
        for g in nuova.get("giocatori") or []:
            if not isinstance(g, dict) or not (g.get("id") in numeri_prev.index or g.get("id") in senza):
                continue
            i = g["id"]
            g["fv"] = (round(float(fv_lega[i]), 2) if i in fv_lega else None) if i in numeri_prev.index else senza[i]
            g.pop("rinvio", None)
            if i in rinvio_numeri or i in rinvio_senza:
                g["rinvio"] = rinvio_numeri.get(i) or rinvio_senza[i]
        if "giocatori" not in nuova:
            nuova["giocatori"] = _numeri_giocatori(numeri_prev, fv_lega, ids_numeri, rinvio_numeri | rinvio_senza, senza)
        else:
            # una voce scritta prima che ci fosse chi non ha previsione: lo prende ora, con il voto che conta nei punti
            presenti = {g.get("id") for g in nuova["giocatori"] if isinstance(g, dict)}
            nuova["giocatori"] = (nuova["giocatori"] + _numeri_giocatori(numeri_prev, fv_lega, [i for i in senza if i not in presenti],
                                                                         rinvio_senza, senza))[:MAX_GIOCATORI_VOCE]
        return nuova | impronte
    # chi non ha previsione sta in colonne fisse DOPO le estrazioni della rosa: la consigliata vale come prima, e la stessa
    # formazione vale lo stesso con o senza di lui (revisione di #461)
    val = fz.Valutatore(lista, regole, simulazioni, fissi=list(extra.values()))
    try:
        migliore = fz.migliore(lista, regole, simulazioni, valutatore=val)
    except ValueError:
        return None
    ricostruita = _riga(migliore.titolari, val.statistiche(migliore.titolari, migliore.panchina),
                        *fatti(migliore.titolari, migliore.panchina)) | {"origine": "ricostruita"}
    voce = {"stagione": stagione, "giornata": giornata, "calcolata": datetime.now().isoformat(timespec="seconds"),
            "regole": impronta_regole(regole, stagione, giornata, bool(rinviate)),
            "impronta_voti": impronta_voti(d, stagione, giornata),
            "consigliata": ricostruita, "ricostruita": dict(ricostruita),
            "schierata": None, "automatica": None,
            "giocatori": _numeri_giocatori(numeri_prev, fv_lega, ids_numeri, rinvio_numeri | rinvio_senza, senza)}

    def riga_di(sc: dict | None) -> dict | None:
        scelti = list(dict.fromkeys(int(i) for i in (sc or {}).get("titolari", [])))
        if not scelte.motivo_non_valida(scelti, ruoli, regole):        # la regola unica della scelta (anche il modulo)
            tit, panchina = formazione(scelti, (sc or {}).get("panchina", []))
            return _riga(tit, val.statistiche(tit, panchina), *fatti(tit, panchina))
        return None
    voce["consigliata"] = _mostrata(istantanea, riga_di) or ricostruita
    voce["consigliata_di_allora"] = _allora_al_calcolo(istantanea, voce["consigliata"], ruoli)
    voce["schierata"] = _come_la_mostrata(riga_di(scelta), scelta, voce["consigliata"], istantanea)
    if voce["schierata"]:
        voce["schierata"]["tipo"] = (scelta or {}).get("tipo") or "manuale"        # «manuale» o «consigliata»; i file vecchi non hanno il campo
        voce["schierata"]["confermata"] = schierata_confermata(scelta)             # messa nell'app della lega? None = non si sa
    # la consigliata salvata dal programma prima della scadenza, se l'utente non ha scelto
    voce["automatica"] = _come_la_mostrata(riga_di(automatica), automatica, voce["consigliata"], istantanea)
    if indicatori:
        try:
            voce["consiglio"] = _consiglio(voce, riga_di, istantanea, cambi, d, stagione, giornata, regole, (lista, gioca, fv, voto),
                                           simulazioni)
        except Exception as e:  # noqa: BLE001 - un di più: la voce del Diario si scrive comunque, senza gli indicatori
            _senza_indicatori(e)
    return voce


def rifai_i_punti(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, voce: dict, ids_rosa: list[int],
                  scelta: dict | None, automatica: dict | None, istantanea: dict | None,
                  giocatori_rosa: dict[int, tuple[str, str | None]] | None, simulazioni: int = SIMULAZIONI, altri_ids=(),
                  completa: bool = False, ceduti=()) -> dict | None:
    """La voce `voce` con i soli punti fatti rifatti con i voti di adesso (#793, decisione del coordinatore): stesse formazioni,
    stessa classificazione (consigliata mostrata o ricostruita, `consigliata_di_allora`, tipo e «L'ho messa» della schierata,
    copia automatica), stessi punti attesi. Cambiano `reale` di ogni formazione, `fv` dei numeri per giocatore, i punti degli
    indicatori del consiglio e le impronte. Le formazioni si contano con lo stesso insieme di giocatori e la stessa funzione di
    `calcola_giornata` e di «Correggi» (la rosa di oggi, `formazione`), così il numero non cambia fra l'uno e l'altro. I numeri che
    si confrontano (schierata, consigliata, ricostruita, S2) cambiano tutti insieme o nessuno: se una formazione non si rifà (un
    titolare non più in rosa) la voce resta com'era, con le sole impronte nuove. Le simulazioni servono solo a S2 degli
    indicatori. None se mancano i dati (come `calcola_giornata`). `completa`: vedi `calcola_giornata`."""
    return calcola_giornata(d, stagione, giornata, regole, par, ids_rosa, scelta, simulazioni, automatica, altri_ids,
                            istantanea=istantanea, giocatori_rosa=giocatori_rosa, tieni=voce, completa=completa,
                            ceduti=ceduti)


def _solo_punti(voce: dict, punti, istantanea: dict | None, scelta: dict | None, automatica: dict | None) -> dict | None:
    """Una copia di `voce` con `reale` e `dettaglio` di ogni formazione rifatti da `punti(titolari, panchina)` (la coppia, o None), e
    i punti della consigliata e della
    schierata negli indicatori; None se anche una sola formazione non si rifà (`punti` None: un titolare non più in rosa), perché
    i numeri che si confrontano cambiano tutti insieme o nessuno. La panchina è l'unico dato che la riga non ha: per la mostrata
    quella dell'istantanea; per una formazione con gli stessi 11 della mostrata e senza una panchina sua, i punti della mostrata
    (come `_come_la_mostrata`); altrimenti quella della scelta, se ha gli stessi 11, o quella del sistema."""
    nuova = json.loads(json.dumps(voce))
    ist_panc = _ids((istantanea or {}).get("panchina"))
    mancate = []

    def rifai(riga: dict, panchina=()) -> None:
        p = punti(_ids(riga.get("titolari")), panchina)
        if p is None:
            mancate.append(riga)
        else:
            riga["reale"], riga["dettaglio"] = p

    cons = nuova.get("consigliata") if isinstance(nuova.get("consigliata"), dict) else None
    mostrata = bool(cons) and cons.get("origine") == "mostrata"
    if cons:
        rifai(cons, ist_panc if mostrata else ())
    if isinstance(nuova.get("ricostruita"), dict):
        rifai(nuova["ricostruita"])
    for chiave, sc in (("schierata", scelta), ("automatica", automatica)):
        riga = nuova.get(chiave)
        if not isinstance(riga, dict):
            continue
        tit = set(_ids(riga.get("titolari")))
        propria = [int(i) for i in (sc or {}).get("panchina") or []] if {int(i) for i in (sc or {}).get("titolari") or []} == tit else []
        if mostrata and tit == set(_ids(cons["titolari"])) and (not propria or propria == ist_panc):
            riga["reale"] = cons["reale"]
            if "dettaglio" in cons:                     # senza: la consigliata non si è rifatta e la voce resta com'era
                riga["dettaglio"] = cons["dettaglio"]
        else:
            rifai(riga, propria)
    if mancate:
        return None
    c = nuova.get("consiglio")
    if isinstance(c, dict):
        if cons:
            c["punti_consigliata"] = cons["reale"]
        if c.get("punti_schierata") is not None and isinstance(nuova.get("schierata"), dict):
            c["punti_schierata"] = nuova["schierata"]["reale"]
    return nuova


def _stessi_voti(d: Dati, stagione: str, giornata: int, regole: Regole, voce: dict,
                 giocatori_rosa: dict[int, tuple[str, str | None]] | None = None) -> bool:
    """Vero se i voti dei giocatori della voce (il fantavoto contato dalla lega di ciascuno in `giocatori`, con il segno `rinvio`)
    sono quelli di adesso: i suoi punti sono già giusti e basta scriverle l'impronta (revisione di #798: al rilascio, a voti
    invariati, nessun numero cambia). `giocatori_rosa` come in `numeri_giocatori`: anche chi non ha una previsione."""
    prima = {g["id"]: (g.get("fv"), g.get("rinvio")) for g in voce.get("giocatori") or []
             if isinstance(g, dict) and isinstance(g.get("id"), int)}
    adesso = numeri_giocatori(d, stagione, giornata, regole, Parametri(), list(prima), giocatori_rosa) if prima else None
    if adesso is None:
        return False
    adesso = {g["id"]: (g["fv"], g.get("rinvio")) for g in adesso}
    return all(i in adesso and adesso[i] == x for i, x in prima.items())


def _giocatori_rosa(squadra) -> dict[int, tuple[str, str | None]]:
    """{id: (nome, ruolo)} della rosa, per `calcola_giornata` (chi non ha una previsione si può schierare lo stesso)."""
    return {int(g.id): (g.nome, g.ruolo) for g in squadra.giocatori if g.id is not None}


def _senza_indicatori(e: Exception) -> None:
    """Nel log del server solo il tipo d'errore: il messaggio può contenere dati."""
    LOG.warning("diario: indicatori del consiglio non calcolati (%s), la voce si scrive senza", type(e).__name__)


def _ids(giocatori) -> list[int]:
    return [x["id"] for x in giocatori or [] if isinstance(x, dict) and isinstance(x.get("id"), int)]


def _consiglio(voce: dict, riga_di, istantanea: dict | None, cambi: tuple | None, d: Dati, stagione: str, giornata: int,
               regole: Regole, veri: tuple, simulazioni: int) -> dict:
    """Gli indicatori del consiglio di una giornata finita (`indicatori_consiglio.py`, campi facoltativi: le app vecchie li ignorano).
    C1 sulla consigliata della voce: quella MOSTRATA, se l'istantanea si può ancora schierare con la rosa di oggi (`mostrata` =
    "istantanea"), altrimenti la ricostruita ("ricostruita"); punti veri suoi, di S2 (la scelta semplice di `verifica_consiglio`)
    e della schierata solo se ha titolari diversi. C2 = `cambi`; C3 e C4 dalle `misure` dell'istantanea. None = non misurato."""
    rosa, gioca, fv, voto = veri
    ist = istantanea if isinstance(istantanea, dict) else {}
    mostrata = voce["consigliata"]
    tipo = "istantanea" if _con_mostrata(voce) else "ricostruita"
    punti_s2 = _punti_s2(d, stagione, giornata, regole, rosa, gioca, fv, voto, simulazioni)
    sch = voce.get("schierata")
    diversa = bool(sch) and set(_ids(sch["titolari"])) != set(_ids(mostrata["titolari"]))
    misure = ist.get("misure") if isinstance(ist.get("misure"), dict) else {}
    return {"mostrata": tipo, "punti_consigliata": mostrata["reale"], "punti_s2": punti_s2,
            "punti_schierata": sch["reale"] if diversa else None,
            "cambi": cambi[0] if cambi else None, "cambi_sotto_soglia": cambi[1] if cambi else None,
            **{k: misure.get(k) if isinstance(misure.get(k), int) else None for k in ic.MISURE}}


def per_il_consiglio(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, d: dict) -> dict:
    """Gli argomenti di `calcola_giornata` per gli indicatori del consiglio, dal file del diario `d`: l'istantanea della giornata e
    C2 contato sui cambi delle 24 ore prima della scadenza della lega. C2 solo se l'istantanea ha le `misure`: le istantanee
    salvate prima di questa versione non registravano i cambi. Non alza mai: se qualcosa non riesce, la voce si fa senza indicatori
    (`indicatori` falso) ma con l'istantanea, letta prima: senza, la voce perdeva la consigliata mostrata e diceva che non era
    stata salvata (difetto del 26/11/2026)."""
    chiave = f"{stagione}/{giornata}"
    ist = d.get("istantanee", {}).get(chiave) if isinstance(d.get("istantanee"), dict) else None
    ist = ist if isinstance(ist, dict) else None
    if ist is None or not isinstance(ist.get("misure"), dict):
        return {"istantanea": ist, "cambi": None}
    try:
        tutti = d.get("cambi") if isinstance(d.get("cambi"), dict) else {}
        cambi = tutti.get(chiave) if isinstance(tutti.get(chiave), list) else []
        scadenza = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
        return {"istantanea": ist, "cambi": ic.conta_cambi(cambi, scadenza, regole)}
    except Exception as e:  # noqa: BLE001 - un di più: la voce del Diario si scrive comunque, senza gli indicatori
        _senza_indicatori(e)
        return {"istantanea": ist, "indicatori": False}


FORMAZIONI = ("consigliata", "ricostruita", "schierata", "automatica")          # le formazioni di una voce, ognuna con i suoi punti


def _senza_dettaglio(voce: dict) -> bool:
    """Vero se una formazione della voce non ha il campo `dettaglio` (voce scritta prima di #900). `dettaglio` null vuol dire che
    non si è potuto calcolare (`_con_il_dettaglio`): non ci si riprova."""
    return any(isinstance(voce.get(k), dict) and "dettaglio" not in voce[k] for k in FORMAZIONI)


def _con_il_dettaglio(vecchia: dict, rifatta: dict | None) -> dict:
    """Le voci già calcolate prima di #900 (decisione della pull request: completarle una volta, senza perdere né cambiare niente):
    una copia di `vecchia` in cui ogni formazione senza `dettaglio` prende quello di `rifatta` (la stessa voce con i punti rifatti,
    `rifai_i_punti`), solo se i punti rifatti sono uguali a quelli salvati. Tutto il resto resta com'era, punti compresi. Dove i
    punti rifatti sono diversi (per esempio la panchina del sistema è cambiata perché una riserva è stata ceduta) o la formazione
    non si rifà (`rifatta` None, o un titolare non più in rosa), `dettaglio` null: la pagina Giornate dice che il dettaglio manca.
    Null anche quando chi entra non è fra i giocatori della voce (`giocatori`, la rosa di allora) e, già in `rifatta` (rifatta con
    `completa`), quando la panchina di allora non si conosce e ha contato (revisione di #905)."""
    nuova = json.loads(json.dumps(vecchia))
    allora = {x.get("id") for x in vecchia.get("giocatori") or [] if isinstance(x, dict)}
    for k in FORMAZIONI:
        riga = nuova.get(k)
        if not isinstance(riga, dict) or "dettaglio" in riga:
            continue
        r = (rifatta or {}).get(k)
        d = r.get("dettaglio") if isinstance(r, dict) else None
        uguale = isinstance(d, dict) and r.get("reale") == riga.get("reale") and all(
            isinstance(e, dict) and (e.get("entra") or {}).get("id") in allora for e in d.get("entrati") or [])
        riga["dettaglio"] = d if uguale else None
    return nuova


def aggiorna(db: sqlite3.Connection, regole: Regole, rose: Rose | None, percorso: Path | None = None,
             simulazioni: int = SIMULAZIONI, file_scelte: Path | None = None, scadenza: float | None = None) -> int:
    """Aggiunge al diario le giornate finite che mancano (e quelle fatte senza la tua scelta, se nel frattempo l'hai salvata).
    Una giornata entra solo quando i voti di tutte le sue partite giocate sono arrivati (`fasi.voti_arrivati`, la regola del
    riepilogo di Oggi), finché resta fra le ultime MASSIMO_GIORNATE. Quando cambiano i suoi voti (`impronta_voti`, o la voce non
    ce l'ha) se ne rifanno solo i punti (`rifai_i_punti`); quando cambiano le regole si rifà da zero (#793). Una giornata con
    partite fuori dal turno e la voce calcolata con altre regole si rifà anche se non è più fra le ultime MASSIMO_GIORNATE: un
    recupero giocato mesi dopo la sua giornata non lascia la voce con i punti di un'altra regola dei rinvii (revisione di #947,
    vedi `sospesa`). Restituisce quante voci ha scritto. `scadenza` (ora di
    `time.monotonic()`): passata quella, non comincia altre giornate e salva quelle già fatte (il resto al giro dopo)."""
    squadra = rose.squadra(rose.mia_squadra) if rose and rose.mia_squadra else None
    if not squadra:
        return 0
    stagione = consigli.stagione_corrente()
    ids = [g.id for g in squadra.giocatori if g.id is not None]
    ruoli = {g.id: g.ruolo for g in squadra.giocatori if g.id is not None}
    dati_diario = carica(percorso)
    voci = dati_diario["giornate"]
    istantanee = dati_diario["istantanee"] if isinstance(dati_diario.get("istantanee"), dict) else {}
    nuove_voci: dict = {}
    chiuse = [x for x in rinvii.giornate_chiuse(db, stagione, regole) if x >= regole.prima_giornata_lega]
    ultime = chiuse[-MASSIMO_GIORNATE:]
    # le giornate più vecchie solo con partite fuori dal turno e la voce calcolata con altre regole: sono le sole che `sospesa`
    # nasconde e poi rimostra a giornata richiusa. Le altre voci vecchie restano com'erano anche se cambiano le regole (rifarle con
    # la rosa di oggi può togliere il confronto con la consigliata mostrata). Dopo le ultime: con il tempo finito, prima loro
    vecchie = [x for x in chiuse[:len(chiuse) - len(ultime)] if isinstance(v := voci.get(f"{stagione}/{x}"), dict)
               and rinvii.ha_fuori_turno(db, stagione, x) and v.get("regole") != impronta_regole(regole, stagione, x, True)]
    for g in ultime + vecchie:
        if scadenza is not None and time.monotonic() > scadenza:
            break
        if not fasi.voti_arrivati(db, stagione, g, regole):
            continue                    # il calendario la dà finita ma i voti di una partita giocata non ci sono ancora
        chiave = f"{stagione}/{g}"
        ist = istantanee.get(chiave) if isinstance(istantanee.get(chiave), dict) else {}
        vecchia = voci.get(chiave)
        # chi non è più in rosa: della consigliata di allora (solo per i numeri per giocatore) e, seconda revisione di #947, i
        # titolari della tua formazione (schierata o copia alla scadenza), per esempio uno ceduto prima del recupero: questi si
        # contano anche quando se ne rifanno i punti (`ceduti` di `rifai_i_punti`)
        ceduti = list(dict.fromkeys(t["id"] for k in ("schierata", "automatica") if isinstance((vecchia or {}).get(k), dict)
                                    for t in vecchia[k].get("titolari") or []
                                    if isinstance(t, dict) and isinstance(t.get("id"), int) and t["id"] not in ids))
        altri = list(dict.fromkeys([t["id"] for t in (ist.get("titolari") or []) + (ist.get("panchina") or [])
                                    if isinstance(t, dict) and isinstance(t.get("id"), int) and t["id"] not in ids] + ceduti))
        scelta = scelte.leggi(stagione, g, file_scelte)
        # una scelta che non si può schierare (regola unica) conta come nessuna scelta. La copia automatica in quel caso non c'è
        # (stesso posto nel file): al suo posto la consigliata congelata alla scadenza (istantanea), la stessa di Oggi in diretta e
        # nel riepilogo (fasi.schierata). Così i punti non cambiano quando il Diario calcola la giornata, né la si ricalcola a ogni giro
        non_vale = bool(scelta) and scelte.motivo_non_valida(scelta.get("titolari") or [], ruoli, regole) is not None
        if non_vale:
            scelta = None
            congelati = [t.get("id") for t in ist.get("titolari") or [] if isinstance(t, dict)]
            auto = None if scelte.motivo_non_valida(congelati, ruoli, regole) else {
                "titolari": congelati, "panchina": [t["id"] for t in ist.get("panchina") or [] if isinstance(t, dict) and "id" in t]}
        else:
            auto = None if scelta else scelte.leggi(stagione, g, file_scelte, anche_automatica=True)
        impronta = impronta_regole(regole, stagione, g, rinvii.ha_fuori_turno(db, stagione, g))
        if vecchia and vecchia.get("regole") != impronta and vecchia.get("schierata") and not scelta:
            # regole cambiate, ma la scelta non c'è più o non si può schierare con la rosa di oggi (un titolare ceduto): rifatta da
            # zero la voce perderebbe la formazione schierata. Se ne rifanno i punti con le regole di adesso, con le stesse formazioni
            # e chi è stato ceduto (`ceduti`). Prima restava com'era, con i punti di un'altra regola dei rinvii (seconda revisione di #947)
            if voce := rifai_i_punti(consigli.dati(db), stagione, g, regole, Parametri(), vecchia, ids, None, auto, ist or None,
                                     _giocatori_rosa(squadra), simulazioni, altri, ceduti=ceduti):
                nuove_voci[chiave] = voce
            continue
        if vecchia:
            salta = False                       # regole cambiate: si rifà da zero (senza una scelta valida, sopra: solo i punti)
            if vecchia.get("regole") == impronta and (vecchia.get("schierata") or (not scelta and not (auto and not vecchia.get("automatica")))):
                salta = True
            # voce scritta prima di #614, con l'istantanea della giornata: si rifà una volta, per confrontare con la consigliata
            # mostrata (se aveva la schierata e la scelta non c'è più resta com'è: rifarla la perderebbe)
            if salta and "ricostruita" not in vecchia and ist.get("titolari") and (scelta or not vecchia.get("schierata")):
                salta = False
            # voce che dice «la consigliata mostrata non era stata salvata» mentre l'istantanea c'è: un errore l'aveva persa
            # (per_il_consiglio, difetto del 26/11/2026). Si rifà una volta, alle stesse condizioni: con l'istantanea non torna più
            # «non_salvata» (_allora_al_calcolo)
            if salta and vecchia.get("consigliata_di_allora") == "non_salvata" and _ids(ist.get("titolari")) and (
                    scelta or not vecchia.get("schierata")):
                salta = False
            # voti cambiati, o voce scritta prima dell'impronta dei voti (il primo giro dopo il rilascio): si rifanno solo i punti,
            # con le stesse formazioni e la stessa classificazione (decisione del coordinatore su #793)
            dati = consigli.dati(db)
            if salta and vecchia.get("regole") == impronta and vecchia.get("impronta_voti") != (adesso := impronta_voti(dati, stagione, g)):
                if _stessi_voti(dati, stagione, g, regole, vecchia, _giocatori_rosa(squadra)):
                    nuove_voci[chiave] = {**vecchia, "impronta_voti": adesso}     # voti dei suoi giocatori invariati: solo l'impronta
                elif voce := rifai_i_punti(dati, stagione, g, regole, Parametri(), vecchia, ids, scelta, auto, ist or None,
                                           _giocatori_rosa(squadra), simulazioni, altri, ceduti=ceduti):
                    nuove_voci[chiave] = voce
                continue
            if salta:
                if "giocatori" not in vecchia:          # voce scritta prima dei numeri per giocatore: si completa senza simulazioni
                    numeri = numeri_giocatori(consigli.dati(db), stagione, g, regole, Parametri(), ids + altri, _giocatori_rosa(squadra))
                    if numeri is not None:
                        nuove_voci[chiave] = {**vecchia, "giocatori": numeri}
                elif _senza_dettaglio(vecchia):         # voce scritta prima di #900: prende il dettaglio dei punti, una volta
                    try:
                        # le stesse formazioni con i punti rifatti come per i voti cambiati; senza gli indicatori, che non servono
                        # e vorrebbero le simulazioni
                        rifatta = rifai_i_punti(dati, stagione, g, regole, Parametri(), {k: x for k, x in vecchia.items() if k != "consiglio"},
                                                ids, scelta, auto, ist or None, _giocatori_rosa(squadra), simulazioni, altri,
                                                completa=True, ceduti=ceduti)
                    except Exception as e:  # noqa: BLE001 - un di più: non deve fermare le giornate dopo
                        # una volta sola: la voce resta com'era, con il dettaglio null, così i giri dopo non ci riprovano
                        LOG.warning("diario: dettaglio dei punti della giornata %s non calcolato (%s), la voce resta senza",
                                    g, type(e).__name__)
                        rifatta = None
                    nuove_voci[chiave] = _con_il_dettaglio(vecchia, rifatta)
                continue
        voce = calcola_giornata(consigli.dati(db), stagione, g, regole, Parametri(), ids, scelta, simulazioni, auto, altri,
                                giocatori_rosa=_giocatori_rosa(squadra), **per_il_consiglio(db, regole, stagione, g, dati_diario))
        if voce and vecchia and vecchia.get("schierata") and not voce["schierata"]:
            # rifatta da zero (regole cambiate) la formazione schierata non si valuta più con la rosa di oggi: resta la voce di prima,
            # con i soli punti rifatti (anche con i voti di adesso, #793) e le impronte nuove, così i giri dopo non la rifanno ogni volta
            voce = rifai_i_punti(consigli.dati(db), stagione, g, regole, Parametri(), vecchia, ids, scelta, auto, ist or None,
                                 _giocatori_rosa(squadra), simulazioni, altri, ceduti=ceduti) or (
                _unisci_voce(vecchia, voce) | {"regole": voce["regole"], "impronta_voti": voce["impronta_voti"]})
        if voce:
            nuove_voci[chiave] = voce
    if nuove_voci:
        _scrivi(percorso, voci=nuove_voci, basi={chiave: voci.get(chiave) for chiave in nuove_voci})
    return len(nuove_voci)


class SchierataNonValida(ValueError):
    """La richiesta «ho schierato...» non si può registrare (giornata non finita, formazione sbagliata)."""


def controlla_stagione(stagione: str | None) -> None:
    """«Ho schierato…» vale solo per la stagione in corso: il diario mostra anche le voci dell'anno prima, e scrivere sulla giornata con
    lo stesso numero di quest'anno sarebbe sbagliato. Senza stagione (i client vecchi non la mandano) vale quella in corso."""
    if stagione is not None and stagione != consigli.stagione_corrente():
        raise SchierataNonValida("Si può decidere solo per la stagione in corso.")      # stesso testo di rinvii.py: già tradotto (err.rinvio_stagione)


def salva_schierata(db: sqlite3.Connection, regole: Regole, rose: Rose | None, giornata: int, tipo: str, titolari: list[int] | None,
                    file_diario: Path | None = None, file_scelte: Path | None = None, simulazioni: int = SIMULAZIONI,
                    stagione: str | None = None) -> dict:
    """Registra cosa l'utente ha schierato in una giornata finita e rifà SOLO quella voce del diario.
    tipo «consigliata»: la formazione che il modello avrebbe consigliato allora (già nella voce del diario, calcolata se manca);
    tipo «manuale»: i `titolari` indicati (11 della tua rosa). Salva la scelta nello stesso file delle scelte (stesso formato).
    `stagione`: quella della voce del diario (vedi `controlla_stagione`).
    Il server fa i due pezzi separati (`prepara_schierata` fuori dal blocco, `scrivi_schierata` dentro): questa li fa uno dopo l'altro."""
    voce, scelti = prepara_schierata(db, regole, rose, giornata, tipo, titolari, file_diario, simulazioni, stagione)
    scrivi_schierata(voce, scelti, giornata, tipo, file_diario, file_scelte)
    return voce


def scrivi_schierata(voce: dict, scelti: list[int], giornata: int, tipo: str, file_diario: Path | None = None,
                     file_scelte: Path | None = None) -> None:
    """Il pezzo veloce: salva la scelta e la voce già calcolata. «L'ho messa» lo decide `scelte.salva` (resta finché i titolari
    sono quelli di prima): la voce lo prende dalla scelta appena salvata."""
    stagione = consigli.stagione_corrente()
    salvata = scelte.salva(stagione, giornata, scelti, voce["schierata"]["modulo"], file_scelte, tipo=tipo)
    voce["schierata"]["confermata"] = schierata_confermata(salvata)
    _scrivi(file_diario, voci={f"{stagione}/{giornata}": voce})


def prepara_schierata(db: sqlite3.Connection, regole: Regole, rose: Rose | None, giornata: int, tipo: str, titolari: list[int] | None,
                      file_diario: Path | None = None, simulazioni: int = SIMULAZIONI,
                      stagione: str | None = None) -> tuple[dict, list[int]]:
    """Il pezzo lento (simulazioni), senza scrivere niente: (voce del diario, titolari scelti). Alza SchierataNonValida."""
    if tipo not in ("consigliata", "manuale"):
        raise SchierataNonValida("Il tipo deve essere «consigliata» o «manuale»")
    controlla_stagione(stagione)
    squadra = rose.squadra(rose.mia_squadra) if rose and rose.mia_squadra else None
    if not squadra:
        raise SchierataNonValida("Indica prima la tua squadra in «La mia squadra»")
    stagione = consigli.stagione_corrente()
    if giornata < regole.prima_giornata_lega:
        raise SchierataNonValida("Quella giornata è precedente all'inizio della tua lega")
    if giornata not in rinvii.giornate_chiuse(db, stagione, regole):
        raise SchierataNonValida("Si può dire cosa hai schierato solo per le giornate già finite")
    ids = [g.id for g in squadra.giocatori if g.id is not None]
    dati = consigli.dati(db)
    diario = carica(file_diario)
    chiave = f"{stagione}/{giornata}"
    if tipo == "consigliata":
        voce = diario["giornate"].get(chiave) or calcola_giornata(dati, stagione, giornata, regole, Parametri(), ids, None, simulazioni)
        if not voce:
            raise SchierataNonValida("Per questa giornata non ho i dati per ricostruire la formazione consigliata")
        scelti = [t["id"] for t in voce["consigliata"]["titolari"]]
        ist = (diario.get("istantanee") or {}).get(chiave)          # meglio quella davvero mostrata allora, se la rosa è ancora la stessa
        if isinstance(ist, dict):
            visti = [t.get("id") for t in ist.get("titolari", []) if isinstance(t, dict)]
            if len(set(visti)) == 11 and set(visti) <= set(ids):
                scelti = [int(i) for i in visti]
    else:
        scelti = [int(i) for i in (titolari or [])]
        if len(set(scelti)) != 11:
            raise SchierataNonValida("Servono 11 titolari diversi")
        if not set(scelti) <= set(ids):
            raise SchierataNonValida("Tra i titolari ci sono giocatori che non sono nella tua rosa")
        motivo = scelte.motivo_non_valida(scelti, {g.id: g.ruolo for g in squadra.giocatori if g.id is not None}, regole)
        if motivo:                                                   # la regola unica della scelta: qui resta il modulo
            raise SchierataNonValida(motivo)
    scelta = {"titolari": scelti, "tipo": tipo}
    voce = calcola_giornata(dati, stagione, giornata, regole, Parametri(), ids, scelta, simulazioni,
                            giocatori_rosa=_giocatori_rosa(squadra), **per_il_consiglio(db, regole, stagione, giornata, diario))
    if not voce or not voce["schierata"]:
        raise SchierataNonValida("Non riesco a valutare questa formazione per quella giornata")
    return voce, scelti


def sintesi(voci: list[dict]) -> dict:
    """Sulle giornate in cui hai schierato undici diversi dalla consigliata mostrata prima della scadenza: punti medi fatti con la
    tua e con la consigliata. Le giornate con gli stessi undici non contano, come in `scelte_tue`: fra due formazioni uguali non
    c'è un verdetto. `senza_consigliata_mostrata` = le giornate con la tua formazione lasciate fuori perché la consigliata di
    allora non c'è (il confronto con una ricostruita non sarebbe con quello che avevi davanti)."""
    tue = [v for v in voci if v.get("schierata")]
    mostrate = [v for v in tue if _con_mostrata(v)]
    con = [v for v in mostrate if not _stessa_formazione(v)]
    if not con:
        return {"giornate": 0, "senza_consigliata_mostrata": len(tue) - len(mostrate)}
    media = lambda f: round(sum(f(v) for v in con) / len(con), 1)      # noqa: E731
    return {"giornate": len(con), "punti_schierata": media(lambda v: v["schierata"]["reale"]),
            "punti_consigliata": media(lambda v: v["consigliata"]["reale"]),
            "attesi_schierata": media(lambda v: v["schierata"]["atteso"]),
            "meglio_tua": sum(1 for v in con if v["schierata"]["reale"] > v["consigliata"]["reale"]),
            "meglio_consigliata": sum(1 for v in con if v["schierata"]["reale"] < v["consigliata"]["reale"]),
            "senza_consigliata_mostrata": len(tue) - len(mostrate)}


POCHI_DATI = 8          # sotto questo numero di giornate la percentuale è troppo instabile: i client dicono «ancora pochi dati»


def scelte_tue(voci: list[dict]) -> dict:
    """Le giornate in cui hai schierato undici diversi da quelli consigliati: chi aveva ragione (punti fatti con la tua formazione
    contro quella consigliata). `differenza` = tua - consigliata (positiva: avevi ragione tu). Le voci vanno dalla più recente.
    Conta solo la consigliata mostrata prima della scadenza: `senza_istantanea` = le giornate con la tua formazione per cui la
    consigliata di allora non c'è, e che quindi non hanno un verdetto; `stessi_titolari` = quelle con gli stessi titolari della
    consigliata mostrata. `nota` (con `nota_frase`) = la frase su quelle giornate (`nota_confronto`), null se non c'è niente da dire.
    `senza_istantanea` conta anche le giornate con la consigliata di allora salvata ma non più valutabile: il perché lo dice la frase
    e, per giornata, `consigliata_di_allora` (#674)."""
    giornate, fuori, stessi = [], [], 0
    for v in voci:
        s, c = v.get("schierata"), v.get("consigliata")
        if not s or not c or not s.get("titolari") or not c.get("titolari"):
            continue
        tue, loro = {t["id"] for t in s["titolari"]}, {t["id"] for t in c["titolari"]}
        if not _con_mostrata(v):
            fuori.append(v)
            continue
        if tue == loro:
            stessi += 1
            continue
        diff = round(s["reale"] - c["reale"], 1)
        giornate.append({"stagione": v["stagione"], "giornata": v["giornata"], "giornata_lega": v.get("giornata_lega"),
                         "hai_scelto": [t["nome"] for t in s["titolari"] if t["id"] not in loro],
                         "consigliava": [t["nome"] for t in c["titolari"] if t["id"] not in tue],
                         "punti_tua": s["reale"], "punti_consigliata": c["reale"], "differenza": diff,
                         "esito": "tua" if diff > 0 else "consigliata" if diff < 0 else "pari"})
    n = len(giornate)
    conti = {"senza_istantanea": len(fuori), "stessi_titolari": stessi} | nota_confronto(n, stessi, len(fuori), _conta_fuori(fuori))
    if not n:
        return {"giornate": 0, "pochi_dati": True, "per_giornata": []} | conti
    meglio_tua = sum(1 for g in giornate if g["esito"] == "tua")
    return {"giornate": n, "meglio_tua": meglio_tua, "meglio_consigliata": sum(1 for g in giornate if g["esito"] == "consigliata"),
            "pari": sum(1 for g in giornate if g["esito"] == "pari"),
            "punti_differenza": round(sum(g["differenza"] for g in giornate), 1),
            "percentuale_tua": round(100 * meglio_tua / n), "pochi_dati": n < POCHI_DATI, "per_giornata": giornate} | conti


def nota_confronto(giornate: int, stessi: int, senza: int, motivi: dict | None = None) -> dict:
    """La frase sulle giornate con la tua formazione che non hanno un verdetto, per «Le tue scelte» (`scelte_tue`) e per il confronto
    di «Quanto ci abbiamo preso» (`precisione._confronto`): la scrive il server, web e iPhone la mostrano così com'è.
    `giornate` = quelle con un verdetto, `stessi` = con gli stessi titolari della consigliata mostrata, `senza` = senza la consigliata
    mostrata. `motivi` = {motivo: giornate} di quelle `senza` (`consigliata_di_allora`): le giornate «fuori_rosa» e
    «non_valutabile» avevano la consigliata salvata, e la frase lo dice (#674); le altre non l'avevano salvata.
    {"nota": testo, "nota_frase": {chiave, param}}; tutti e due null se non c'è niente da dire (nessuna giornata segnata, oppure
    tutte con un verdetto)."""
    motivi = motivi or {}
    rosa, altro = int(motivi.get("fuori_rosa", 0)), int(motivi.get("non_valutabile", 0))
    parti = []
    if senza - rosa - altro > 0:
        parti.append(F("diario.confronto_fuori", n=senza - rosa - altro))
    if rosa + altro:
        parti.append(F("diario.confronto_non_valutabili", n=rosa + altro) if altro else F("diario.confronto_fuori_rosa", n=rosa))
    fuori = elenco_frasi(parti, sep=" ") or None
    if giornate or not stessi:
        frase = fuori
    elif not fuori:
        frase = F("diario.confronto_stessa")
    else:
        frase = F("diario.confronto_stessa_confrontabili" if rosa + altro else "diario.confronto_stessa_fuori", fuori=fuori)
    return {"nota": str(frase) if frase else None, "nota_frase": frase.json() if frase else None}


MAX_SCARTI = 2          # «chi ha fatto meglio o peggio del previsto»: al massimo due giocatori per parte
# ... e solo chi si scosta dal suo fantavoto atteso di almeno 1 punto (scelta del proprietario, revisione di #702): sotto un punto
# lo scarto è il rumore di mezzo voto in pagella o di un'ammonizione, e nominare chi ha fatto «come previsto» non dice niente.
# Se nessuno arriva a 1 punto le liste sono vuote e la frase non c'è.
SOGLIA_SCARTO = 1.0


def _numero(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else None


def _letto(x: float) -> float:
    """Il numero come lo scrive la pagina: una cifra, come `toFixed(1)` della web (il mezzo lontano dallo zero, sul valore vero del
    numero: 6,25 → 6,3; 5,55, che è 5,5499…, → 5,5). `round` di Python farebbe 6,2."""
    return float(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _formazione_che_conta(voce: dict) -> tuple[str, dict] | None:
    """La formazione dei punti della giornata, come nella riga della pagina Giornate e nel riepilogo della Formazione: la tua
    (`schierata`), altrimenti la copia della consigliata fatta alla scadenza (`automatica`), altrimenti la consigliata."""
    return next(((k, voce[k]) for k in ("schierata", "automatica", "consigliata") if isinstance(voce.get(k), dict)), None)


def _frase_scarti(meglio: list[dict], peggio: list[dict]):
    """«Meglio del previsto: Rossi (+3,9) e Verdi (+2,0). Peggio: Bianchi (−2,5).», o una parte sola; None senza nessuno."""
    def nomi(righe):
        return elenco_frasi([F("diario.scarto_giocatore", nome=r["nome"], d=ConSegno(r["differenza"])) for r in righe], con_e=True)
    if meglio and peggio:
        return F("diario.meglio_peggio", meglio=nomi(meglio), peggio=nomi(peggio))
    if meglio:
        return F("diario.meglio", meglio=nomi(meglio))
    return F("diario.peggio", peggio=nomi(peggio)) if peggio else None


def fatti_e_attesi(voce: dict) -> dict | None:
    """Per la pagina Giornate (#672): i punti fatti e attesi della formazione che conta (`formazione`: "schierata", "automatica" o
    "consigliata", vedi `_formazione_che_conta`), la `differenza` (fatti meno attesi, positiva = meglio del previsto) e chi dei suoi
    titolari ha fatto meglio (`meglio`) o peggio (`peggio`) del suo fantavoto atteso di almeno SOGLIA_SCARTO punti, al massimo
    MAX_SCARTI per parte, dalla differenza più grande: `{id, nome, ruolo, atteso, preso, differenza}`. L'atteso di un giocatore è quello mostrato prima della
    scadenza (istantanea), se c'è, altrimenti quello rifatto con i soli dati di prima (`giocatori`): gli stessi numeri della tabella
    della pagina. Chi non ha preso voto non c'è (senza un fantavoto non si confronta; la tabella lo dice «senza voto»), e nemmeno
    chi aveva la partita rinviata e ha il voto della regola della lega (`giocatori[].rinvio`: d'ufficio o nessuno, non del campo).
    Le differenze sono quelle dei numeri come la pagina li scrive (`_letto`). `testo` e `frase`: la frase su `meglio` e `peggio`,
    null se sono vuoti. None se la formazione non ha i punti."""
    chi = _formazione_che_conta(voce)
    if chi is None or _numero(chi[1].get("atteso")) is None or _numero(chi[1].get("reale")) is None:
        return None
    nome, f = chi
    ist = voce.get("istantanea") if isinstance(voce.get("istantanea"), dict) else {}
    mostrati = {t.get("id"): t["fv_atteso"] for t in (ist.get("titolari") or []) + (ist.get("panchina") or [])
                if isinstance(t, dict) and _numero(t.get("fv_atteso")) is not None}
    numeri = {g.get("id"): g for g in voce.get("giocatori") or [] if isinstance(g, dict)}
    righe = []
    for t in f.get("titolari") or []:
        if not isinstance(t, dict) or "id" not in t:
            continue
        n = numeri.get(t["id"]) or {}
        atteso, preso = mostrati.get(t["id"], n.get("fv_atteso")), n.get("fv")
        if _numero(atteso) is None or _numero(preso) is None or n.get("rinvio"):
            continue
        righe.append({"id": t["id"], "nome": t.get("nome", ""), "ruolo": t.get("ruolo"), "atteso": atteso, "preso": preso,
                      "differenza": round(_letto(preso) - _letto(atteso), 1)})
    meglio = sorted((r for r in righe if r["differenza"] >= SOGLIA_SCARTO), key=lambda r: -r["differenza"])[:MAX_SCARTI]
    peggio = sorted((r for r in righe if r["differenza"] <= -SOGLIA_SCARTO), key=lambda r: r["differenza"])[:MAX_SCARTI]
    frase = _frase_scarti(meglio, peggio)
    return {"formazione": nome, "atteso": f["atteso"], "fatti": f["reale"],
            "differenza": round(_letto(f["reale"]) - _letto(f["atteso"]), 1), "meglio": meglio, "peggio": peggio,
            "testo": str(frase) if frase else None, "frase": frase.json() if frase else None}


def _nomi(giocatori: list) -> str:
    """«Rossi», «Rossi e Bianchi», «Rossi, Bianchi e Verdi»."""
    return elenco_frasi([str(x.get("nome", "")) for x in giocatori if isinstance(x, dict)], con_e=True)


def _righe_dettaglio(d: dict) -> list:
    """Le frasi del `dettaglio` di una formazione (`_dettaglio`), nell'ordine in cui si leggono: la partita rinviata, chi è entrato
    dalla panchina e al posto di chi, chi è rimasto senza sostituto, il modificatore difesa (solo se non è zero)."""
    righe = []
    r = d.get("rinvio") if isinstance(d.get("rinvio"), dict) else {}
    chi = [x for x in r.get("giocatori") or [] if isinstance(x, dict)]
    if chi and r.get("modo") == "voto_ufficio" and _numero(r.get("valore")) is not None:
        righe.append(F("diario.punti_ufficio", n=len(chi), nomi=_nomi(chi), voto=_letto(r["valore"])))
    elif chi and r.get("modo") == "senza_voto":
        righe.append(F("diario.punti_rinvio_senza_voto", n=len(chi), nomi=_nomi(chi)))
    for e in d.get("entrati") or []:
        if isinstance(e, dict) and isinstance(e.get("entra"), dict) and isinstance(e.get("esce"), dict) and _numero(e.get("fv")) is not None:
            righe.append(F("diario.punti_entrato", entra=str(e["entra"].get("nome", "")), fv=_letto(e["fv"]),
                           esce=str(e["esce"].get("nome", ""))))
    senza = [x for x in d.get("senza_sostituto") or [] if isinstance(x, dict)]
    if senza:
        v = _numero(d.get("voto_senza_sostituto"))
        righe.append(F("diario.punti_nessuno", nomi=_nomi(senza)) if v is None
                     else F("diario.punti_nessuno_voto", n=len(senza), nomi=_nomi(senza), v=_letto(v)))
    m = _numero(d.get("modificatore"))
    if m:
        righe.append(F("diario.punti_modificatore", d=ConSegno(_letto(m))))
    return righe


def _tornano(voce: dict, f: dict) -> bool:
    """Vero se i punti della formazione `f` sono la somma dei fantavoti presi dai suoi 11 (`giocatori[].fv`, quelli della tabella
    della pagina Giornate): allora non c'è niente da spiegare. Falso se a qualcuno manca il voto."""
    fv = {g.get("id"): g.get("fv") for g in voce.get("giocatori") or [] if isinstance(g, dict)}
    presi = [fv.get(t.get("id")) for t in f.get("titolari") or [] if isinstance(t, dict)]
    if not presi or any(_numero(x) is None for x in presi):
        return False
    return abs(sum(presi) - f["reale"]) < 0.1


def spiegazione_punti(voce: dict) -> dict | None:
    """Per la pagina Giornate (#900): perché i punti della formazione che conta (`formazione`, come in `fatti_e_attesi`) non sono la
    somma dei fantavoti presi dai suoi 11. `righe` = le frasi, dal `dettaglio` salvato con la formazione (`_righe_dettaglio`: partita
    rinviata, chi è entrato al posto di chi, chi è rimasto senza sostituto, modificatore difesa), con `righe_frasi` per tradurle.
    Una voce scritta prima del dettaglio (o che non si è potuta completare, `dettaglio` null) ha una frase sola che lo dice, ma solo
    se i conti non tornano con i voti degli 11. None se non c'è niente da spiegare."""
    chi = _formazione_che_conta(voce)
    if chi is None or _numero(chi[1].get("reale")) is None:
        return None
    nome, f = chi
    d = f.get("dettaglio")
    righe = _righe_dettaglio(d) if isinstance(d, dict) else [] if _tornano(voce, f) else [F("diario.punti_senza_dettaglio")]
    if not righe:
        return None
    return {"formazione": nome, "righe": [str(r) for r in righe], "righe_frasi": [r.json() for r in righe]}


COPERTURA_MINIMA = 0.6          # sotto questa quota di giornate dentro la fascia (dichiarata: 8 su 10) il periodo è «andato peggio del previsto»


def atteso_vs_fatto(voce: dict) -> dict | None:
    """Per una giornata finita: i punti che SchieraXI si aspettava dalla formazione consigliata, quelli fatti, lo scarto (fatti
    meno attesi, positivo = meglio del previsto) e se sono caduti dentro la fascia «tra X e Y». `riferimento`: "consigliata" se
    è quella mostrata prima della scadenza, con i punti attesi mostrati allora; "ricostruita" se la consigliata di allora non
    c'è e i numeri sono della scelta rifatta a giornata finita (una misura del modello, non di quello che avevi davanti)."""
    c = voce.get("consigliata")
    if not isinstance(c, dict) or c.get("atteso") is None or c.get("reale") is None:
        return None
    basso, alto = (c.get("intervallo") or {}).get("basso"), (c.get("intervallo") or {}).get("alto")
    dentro = None if basso is None or alto is None else bool(basso <= c["reale"] <= alto)
    return {"riferimento": "consigliata" if _con_mostrata(voce) else "ricostruita", "atteso": c["atteso"], "fatti": c["reale"],
            "scarto": round(c["reale"] - c["atteso"], 1),
            "nella_fascia": dentro, "intervallo": {"basso": basso, "alto": alto} if dentro is not None else None}


def affidabilita(voci: list[dict]) -> dict:
    """Quanto ci ha preso SchieraXI sui punti della squadra, giornata per giornata, ANCHE quando va male. Tutto si ricalcola dalle voci:
    `scarto_medio` = media degli scarti senza segno (in punti), `errore_medio` = media con segno (negativo: i punti veri sono stati
    meno dei previsti), `dentro_fascia` = in quante giornate i punti fatti sono caduti nella fascia prevista (dichiarata: 8 su 10).
    `giudizio`: `pochi_dati` (meno di POCHI_DATI giornate), `in_linea`, oppure `sotto_le_attese` / `sopra_le_attese` se la quota dentro
    la fascia è sotto COPERTURA_MINIMA (dice se i punti veri sono stati meno o più dei previsti).
    Contano solo le giornate con la consigliata mostrata prima della scadenza (i punti attesi che avevi davanti);
    `senza_istantanea` = le altre, lasciate fuori."""
    tutte = [r for r in (atteso_vs_fatto(v) for v in voci) if r]
    righe = [r for r in tutte if r["riferimento"] == "consigliata"]
    n = len(righe)
    if not n:
        return {"giornate": 0, "giudizio": "pochi_dati", "pochi_dati": True, "giornate_minime": POCHI_DATI,
                "senza_istantanea": len(tutte)}
    con_fascia = [r for r in righe if r["nella_fascia"] is not None]
    dentro = sum(1 for r in con_fascia if r["nella_fascia"])
    quota = dentro / len(con_fascia) if con_fascia else None
    errore = sum(r["scarto"] for r in righe) / n
    pochi = n < POCHI_DATI
    giudizio = "pochi_dati" if pochi else "in_linea" if quota is None or quota >= COPERTURA_MINIMA else "sotto_le_attese" if errore < 0 else "sopra_le_attese"
    return {"giornate": n, "scarto_medio": round(sum(abs(r["scarto"]) for r in righe) / n, 1), "errore_medio": round(errore, 1),
            "punti_medi_attesi": round(sum(r["atteso"] for r in righe) / n, 1), "punti_medi_fatti": round(sum(r["fatti"] for r in righe) / n, 1),
            "dentro_fascia": dentro, "con_fascia": len(con_fascia), "percentuale_dentro": None if quota is None else round(100 * quota),
            "fascia_dichiarata": round(100 * incertezza.CONFIDENZA), "pochi_dati": pochi, "giornate_minime": POCHI_DATI, "giudizio": giudizio,
            "senza_istantanea": len(tutte) - n}


def motivo_vuoto(db: sqlite3.Connection, regole: Regole, rose: Rose | None) -> str:
    """Perché il diario è vuoto, per dirlo all'utente: «squadra» (non hai indicato la tua), «giornate» (nessuna giornata finita della
    lega), «calcolo» (tutto a posto, le voci si calcolano al prossimo aggiornamento o al tocco su «Ho schierato la consigliata»)."""
    if not (rose and rose.mia_squadra and rose.squadra(rose.mia_squadra)):
        return "squadra"
    if not [g for g in rinvii.giornate_chiuse(db, consigli.stagione_corrente(), regole) if g >= regole.prima_giornata_lega]:
        return "giornate"
    return "calcolo"


def sospesa(db: sqlite3.Connection, regole: Regole, voce: dict, chiuse: set[int] | None = None) -> bool:
    """Vero se la voce non va mostrata, né nel Diario né nel riepilogo di Oggi: è stata calcolata con regole diverse da quelle di
    adesso (`impronta_regole`) e la sua giornata (della stagione in corso) per la lega non è più finita, oppure lo è di nuovo ma i
    voti non sono ancora tutti arrivati (`fasi.voti_arrivati`: `aggiorna` non l'ha ancora rifatta). Succede quando la regola delle
    partite rinviate di quella giornata torna ad «aspetta» dopo il calcolo: i punti della voce (con il voto d'ufficio o senza voto)
    non sono più quelli della lega, che aspetta il recupero. Arrivati i voti del recupero `aggiorna` la rifà, anche fuori dalle
    ultime MASSIMO_GIORNATE (revisione di #947), perché l'impronta è cambiata. `chiuse` = le giornate finite
    (`rinvii.giornate_chiuse`), se chi chiama le ha già: `elenco` le chiede una volta sola."""
    nota = _sospesa_senza_archivio(regole, voce)
    if nota is not None:
        return nota
    stagione, g = consigli.stagione_corrente(), voce["giornata"]
    finite = chiuse if chiuse is not None else set(rinvii.giornate_chiuse(db, stagione, regole))
    return not (g in finite and fasi.voti_arrivati(db, stagione, g, regole))


def _sospesa_senza_archivio(regole: Regole, voce: dict) -> bool | None:
    """Quello che di `sospesa` si sa senza leggere l'archivio: False se la voce resta (un'altra stagione, una voce senza l'impronta
    delle regole, o calcolata con le regole di adesso: con queste una giornata ha una di due impronte, senza o con partite fuori dal
    turno; resta anche nel solo caso in cui l'impronta giusta è l'altra, cioè quando il calendario ha spostato una partita dentro o
    fuori dal turno dopo il calcolo, e la rifà `aggiorna`, che usa quella esatta). True se la voce ha i segni `rinvio` dei suoi
    giocatori (voto d'ufficio o senza voto) e per la giornata adesso vale «aspetta»: i suoi punti non sono quelli della lega
    nemmeno fra l'arrivo dei voti del recupero e il giro di `aggiorna` (seconda revisione di #947). None se serve l'archivio."""
    stagione = consigli.stagione_corrente()
    g, fatta = voce.get("giornata"), voce.get("regole")
    if voce.get("stagione") != stagione or not isinstance(g, int) or not isinstance(fatta, str):
        return False
    if fatta in (impronta_regole(regole, stagione, g, False), impronta_regole(regole, stagione, g, True)):
        return False
    segni = any(isinstance(x, dict) and x.get("rinvio") for x in voce.get("giocatori") or [])
    if segni and rinvii.regola(regole, stagione, g)["modo"] == "aspetta":
        return True
    return None


def elenco(percorso: Path | None = None, regole: Regole | None = None, db: sqlite3.Connection | None = None) -> dict:
    """Le voci dalla più recente, con la sintesi: quello che mostra l'app. Con le regole della lega, la stagione in corso conta solo
    dalla prima giornata della lega e ogni voce porta anche `giornata_lega` (il numero nel calendario della lega). Con le regole e
    l'archivio `db` non ci sono le voci sospese (`sospesa`), nemmeno nei conti in cima: le loro giornate stanno in `in_attesa`
    (dalla più recente, {stagione, giornata, giornata_lega, testo, frase}, «Giornata 5 · 8ª di Serie A: in attesa del recupero, i
    punti arrivano dopo.»), che web e iPhone mostrano così com'è (revisione di #947: prima la giornata spariva senza spiegazione)."""
    d = carica(percorso)
    istantanee = d["istantanee"] if isinstance(d.get("istantanee"), dict) else {}
    voci = [per_i_client(v) for v in sorted(d["giornate"].values(), key=lambda v: (v["stagione"], v["giornata"]), reverse=True)]
    corrente = consigli.stagione_corrente()
    in_attesa = []
    if regole is not None:
        voci = [v for v in voci if v["stagione"] != corrente or v["giornata"] >= regole.prima_giornata_lega]
        if db is not None:
            # le giornate finite si chiedono all'archivio una volta sola, e solo se una voce ne ha bisogno
            serve = any(_sospesa_senza_archivio(regole, v) is None for v in voci)
            chiuse = set(rinvii.giornate_chiuse(db, corrente, regole)) if serve else set()
            sospese = [v for v in voci if sospesa(db, regole, v, chiuse)]
            voci = [v for v in voci if v not in sospese]
            for v in sospese:
                lega = serie_a_a_lega(v["giornata"], regole)
                frase = F("diario.in_attesa_recupero", giornata=nome_giornata(v["giornata"], lega))
                in_attesa.append({"stagione": v["stagione"], "giornata": v["giornata"], "giornata_lega": lega, "testo": str(frase),
                                  "frase": frase.json()})
        for v in voci:
            v["giornata_lega"] = serie_a_a_lega(v["giornata"], regole) if v["stagione"] == corrente else None
    for v in voci:
        ist = istantanee.get(f"{v['stagione']}/{v['giornata']}")
        v["istantanea"] = ist if isinstance(ist, dict) else None      # la consigliata di allora; null se non era stata registrata
        v["modificabile"] = v["stagione"] == corrente                 # «Ho schierato…» e «Correggi» solo per la stagione in corso (controlla_stagione)
        # contratto per le app: «schierata» ha sempre il tipo, «automatica» c'è sempre (anche null)
        v.setdefault("automatica", None)
        if v.get("schierata"):
            v["schierata"].setdefault("tipo", "manuale")
        if isinstance(v.get("consigliata"), dict):                    # voci scritte prima di #614: la consigliata è la ricostruita
            v["consigliata"].setdefault("origine", "ricostruita")
            v.setdefault("ricostruita", dict(v["consigliata"]))
        for k in ("consigliata", "schierata", "automatica"):     # file vecchi senza fascia: la si calcola senza la parte simulata
            if v.get(k) and "intervallo" not in v[k]:
                v[k]["intervallo"] = incertezza.intervallo(v[k]["atteso"], v[k].get("dev_simulata", 0.0))
    for v in voci:
        v["atteso_vs_fatto"] = atteso_vs_fatto(v)
        v["fatti_e_attesi"] = fatti_e_attesi(v)                      # #672: fatti meno attesi, e chi ha fatto meglio o peggio
        v["spiegazione_punti"] = spiegazione_punti(v)                # #900: perché i punti non sono la somma dei voti degli 11
        v["consigliata_di_allora"] = consigliata_di_allora(v)        # #674: perché c'è, o non c'è, il confronto
        v.update(nota_consigliata(v))
    return {"giornate": voci, "sintesi": sintesi(voci), "scelte_tue": scelte_tue(voci), "affidabilita": affidabilita(voci),
            "in_attesa": in_attesa}
