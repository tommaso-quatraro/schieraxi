"""Il diario delle giornate: per ogni giornata finita, la formazione che hai schierato (la tua scelta salvata) contro quella che il
modello avrebbe consigliato, con i punti attesi e quelli fatti. Il modello rifà la scelta con i soli dati che c'erano prima della
giornata e con la rosa di oggi (le rose passate non si conservano). La panchina è quella che sceglie il sistema, anche per la tua.
Il calcolo è pesante: si fa solo per le giornate nuove e il risultato resta in dati/diario.json."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import avvisi, consigli, incertezza, rinvii, scelte
from . import indicatori_consiglio as ic
from . import verifica_consiglio as vc
from . import formazione as fz
from .blocco import BloccoFile
from .lega import Rose
from .modello import Dati, Parametri, previsioni
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .punteggio import COLONNA_VOTO, fantavoto
from .regole import RUOLI, Regole, serie_a_a_lega
from .verifica import MIN_GIOCATORI_ROSA

FILE = RADICE / "dati" / "diario.json"
MASSIMO_GIORNATE = 12
SIMULAZIONI = 300
MAX_ISTANTANEE = 60
_blocco = threading.Lock()
LOG = logging.getLogger(__name__)


def carica(percorso: Path | None = None) -> dict:
    try:
        d = json.loads((percorso or FILE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("giornate"), dict) else {"giornate": {}}
    except (OSError, ValueError):
        return {"giornate": {}}


def _scrivi(percorso: Path | None, voci: dict | None = None, istantanee: dict | None = None, cambi: dict | None = None) -> None:
    """Aggiunge voci e/o istantanee al file ricaricandolo subito prima di scrivere: il calcolo del diario è lungo e nel frattempo
    la schermata della formazione può aver salvato un'istantanea nuova, che non va persa. Il blocco vale anche fra processi
    (servizio e comando del cron) e una voce con la formazione schierata non viene MAI sostituita da una che non ce l'ha:
    il cron, che ha calcolato su una copia vecchia, non cancella un «Ho schierato» arrivato nel frattempo dall'app.
    `cambi` = {chiave: cambio} (`indicatori_consiglio.cambio`): si aggiunge in fondo a quelli della giornata, al massimo
    `indicatori_consiglio.MAX_CAMBI` (gli ultimi), solo se l'istantanea nel file ha ancora i titolari di prima del cambio: due
    salvataggi della stessa consigliata nuova nello stesso momento (app e copia alla scadenza) contano un cambio solo.
    Stanno a parte, fuori dalle istantanee che l'app riceve."""
    file = percorso or FILE
    with _blocco, BloccoFile(file.with_name(file.name + ".lock")):
        d = carica(percorso)
        for chiave, nuova in (voci or {}).items():
            d["giornate"][chiave] = _unisci_voce(d["giornate"].get(chiave), nuova)
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
    sovrascrive con titolari diversi si registra il cambio (C2), a parte."""
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
    prima = carica(percorso).get("istantanee")
    vecchia = prima.get(chiave) if isinstance(prima, dict) else None
    if isinstance(vecchia, dict) and {k: v for k, v in vecchia.items() if k != "calcolata"} == nuova:
        return False
    nuova["calcolata"] = _adesso().isoformat(timespec="seconds")
    c = ic.cambio(vecchia, f, nuova["calcolata"]) if isinstance(vecchia, dict) else None
    _scrivi(percorso, istantanee={chiave: nuova}, cambi={chiave: c} if c else None)
    return True


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


def _riga(titolari: list[fz.Giocatore], stat: tuple, reale: float) -> dict:
    """`stat` = (atteso, dev simulata) dal Valutatore; la fascia è quella calibrata (incertezza.py)."""
    conta = {r: sum(1 for g in titolari if g.ruolo == r) for r in RUOLI}
    atteso, dev = stat[0], stat[1]
    return {"modulo": f"{conta['D']}-{conta['C']}-{conta['A']}", "atteso": round(atteso, 1), "reale": round(reale, 1),
            "dev_simulata": round(dev, 1), "intervallo": incertezza.intervallo(atteso, dev),
            "titolari": [{"id": g.id, "nome": g.nome, "ruolo": g.ruolo} for g in titolari]}


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


def _numeri_giocatori(prev: pd.DataFrame, fv_vero: dict, ids) -> list[dict]:
    """Per «Quanto ci abbiamo preso»: per ogni giocatore la probabilità di voto e il fantavoto atteso RICOSTRUITI con i dati di
    prima e il fantavoto vero (`fv` null = non ha preso voto). Circa 60 byte a giocatore."""
    out = []
    for i in dict.fromkeys(int(x) for x in ids):
        if i in prev.index:
            out.append({"id": i, "p_voto": round(float(prev.at[i, "p_voto"]), 3), "fv_atteso": round(float(prev.at[i, "mu"]), 2),
                        "fv": round(float(fv_vero[i]), 2) if i in fv_vero else None})
    return out[:MAX_GIOCATORI_VOCE]


def numeri_giocatori(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, ids) -> list[dict] | None:
    """Solo i numeri per giocatore di una giornata finita, senza simulazioni: completa le voci scritte prima che ci fossero."""
    pv = _previsti_e_veri(d, stagione, giornata, regole, par)
    return None if pv is None else _numeri_giocatori(pv[0], pv[2], ids)


def calcola_giornata(d: Dati, stagione: str, giornata: int, regole: Regole, par: Parametri, ids_rosa: list[int],
                     scelta: dict | None, simulazioni: int = SIMULAZIONI, automatica: dict | None = None,
                     altri_ids=(), istantanea: dict | None = None, cambi: tuple | None = None,
                     indicatori: bool = True) -> dict | None:
    """La voce del diario di una giornata finita, o None se mancano i dati (o la rosa è troppo piccola per quella giornata).
    `altri_ids`: chi era nella consigliata di allora (istantanea) ma non è più in rosa, per i numeri per giocatore.
    `istantanea` (la consigliata mostrata) e `cambi` (C2 già contato, `indicatori_consiglio.conta_cambi`): per gli indicatori del
    consiglio della voce (`consiglio`, vedi `_consiglio`). Gli indicatori non fermano mai la voce: se il loro calcolo non riesce (o
    `indicatori` è falso, perché non si sono potuti preparare) la voce si scrive senza `consiglio`."""
    col = COLONNA_VOTO[regole.fonte_voto]
    # partite rinviate (fuori dal turno, recuperate o no): la regola della lega per quella giornata, come prima della scadenza
    r_rinvio = rinvii.regola(regole, stagione, giornata)
    rinviate = rinvii.id_fuori_turno(d.partite, stagione, giornata)
    pv = _previsti_e_veri(d, stagione, giornata, regole, par, rinviate if r_rinvio["modo"] != "aspetta" else frozenset())
    if pv is None:
        return None
    prev, reali, fv_vero = pv
    numeri_prev = prev                    # «Quanto ci abbiamo preso» misura il modello: numeri di prima della regola dei rinvii
    prev = rinvii.applica(prev, rinviate, r_rinvio)
    ids = [i for i in ids_rosa if i in prev.index]
    if len(ids) < MIN_GIOCATORI_ROSA:
        return None
    rosa = {int(i): fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                                 float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids}
    lista = list(rosa.values())
    gioca = {i: i in fv_vero for i in rosa}
    fv = {i: fv_vero.get(i, 0.0) for i in rosa}
    voto = {i: float(reali.at[i, col]) if i in fv_vero else 0.0 for i in rosa}
    rinvii.voti_lega(gioca, fv, voto, [i for i in rosa if prev.at[i, "rinvio"] is not None], r_rinvio)
    val = fz.Valutatore(lista, regole, simulazioni)
    try:
        migliore = fz.migliore(lista, regole, simulazioni, valutatore=val)
    except ValueError:
        return None
    voce = {"stagione": stagione, "giornata": giornata, "calcolata": datetime.now().isoformat(timespec="seconds"),
            "regole": impronta_regole(regole, stagione, giornata, bool(rinviate)),
            "consigliata": _riga(migliore.titolari, val.statistiche(migliore.titolari, migliore.panchina),
                                 fz.punteggio(migliore.titolari, migliore.panchina, gioca, fv, voto, regole)),
            "schierata": None, "automatica": None,
            "giocatori": _numeri_giocatori(numeri_prev, fv_vero, list(ids) + list(altri_ids))}

    ruoli = {i: g.ruolo for i, g in rosa.items()}

    def riga_di(sc: dict | None) -> dict | None:
        scelti = list(dict.fromkeys(int(i) for i in (sc or {}).get("titolari", [])))
        if not scelte.motivo_non_valida(scelti, ruoli, regole):        # la regola unica della scelta (anche il modulo)
            tit = [rosa[i] for i in scelti]
            propria = [rosa[i] for i in dict.fromkeys(int(i) for i in (sc or {}).get("panchina", []) if i in rosa and i not in scelti)]
            panchina = propria or fz._panchina(lista, tit, regole)      # la panchina schierata davvero, se la conosciamo (giornate importate)
            return _riga(tit, val.statistiche(tit, panchina), fz.punteggio(tit, panchina, gioca, fv, voto, regole))
        return None
    voce["schierata"] = riga_di(scelta)
    if voce["schierata"]:
        voce["schierata"]["tipo"] = (scelta or {}).get("tipo") or "manuale"        # «manuale» o «consigliata»; i file vecchi non hanno il campo
    voce["automatica"] = riga_di(automatica)      # la consigliata salvata dal programma prima della scadenza, se l'utente non ha scelto
    if indicatori:
        try:
            voce["consiglio"] = _consiglio(voce, riga_di, istantanea, cambi, d, stagione, giornata, regole, (lista, gioca, fv, voto),
                                           simulazioni)
        except Exception as e:  # noqa: BLE001 - un di più: la voce del Diario si scrive comunque, senza gli indicatori
            _senza_indicatori(e)
    return voce


def _senza_indicatori(e: Exception) -> None:
    """Nel log del server solo il tipo d'errore: il messaggio può contenere dati."""
    LOG.warning("diario: indicatori del consiglio non calcolati (%s), la voce si scrive senza", type(e).__name__)


def _ids(giocatori) -> list[int]:
    return [x["id"] for x in giocatori or [] if isinstance(x, dict) and isinstance(x.get("id"), int)]


def _consiglio(voce: dict, riga_di, istantanea: dict | None, cambi: tuple | None, d: Dati, stagione: str, giornata: int,
               regole: Regole, veri: tuple, simulazioni: int) -> dict:
    """Gli indicatori del consiglio di una giornata finita (`indicatori_consiglio.py`, campi facoltativi: le app vecchie li ignorano).
    C1 sulla consigliata MOSTRATA: l'istantanea, se si può ancora schierare con la rosa di oggi (`mostrata` = "istantanea"),
    altrimenti quella ricostruita della voce ("ricostruita"); punti veri suoi, di S2 (la scelta semplice di `verifica_consiglio`)
    e della schierata solo se ha titolari diversi. C2 = `cambi`; C3 e C4 dalle `misure` dell'istantanea. None = non misurato."""
    rosa, gioca, fv, voto = veri
    ist = istantanea if isinstance(istantanea, dict) else {}
    mostrata = riga_di({"titolari": _ids(ist.get("titolari")), "panchina": _ids(ist.get("panchina"))}) if ist else None
    tipo = "istantanea" if mostrata else "ricostruita"
    mostrata = mostrata or voce["consigliata"]
    ha_giocato, fantamedia = vc.dati_s2(d, stagione, giornata, regole)
    try:
        s2 = fz.migliore(vc.rosa_s2(rosa, ha_giocato, fantamedia), regole, simulazioni)
        punti_s2 = round(fz.punteggio(s2.titolari, s2.panchina, gioca, fv, voto, regole), 1)
    except ValueError:                    # in qualche ruolo nessuno: S2 non si può formare
        punti_s2 = None
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
    (`indicatori` falso)."""
    try:
        chiave = f"{stagione}/{giornata}"
        ist = d.get("istantanee", {}).get(chiave) if isinstance(d.get("istantanee"), dict) else None
        ist = ist if isinstance(ist, dict) else None
        if ist is None or not isinstance(ist.get("misure"), dict):
            return {"istantanea": ist, "cambi": None}
        tutti = d.get("cambi") if isinstance(d.get("cambi"), dict) else {}
        cambi = tutti.get(chiave) if isinstance(tutti.get(chiave), list) else []
        scadenza = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
        return {"istantanea": ist, "cambi": ic.conta_cambi(cambi, scadenza, regole)}
    except Exception as e:  # noqa: BLE001 - un di più: la voce del Diario si scrive comunque, senza gli indicatori
        _senza_indicatori(e)
        return {"indicatori": False}


def aggiorna(db: sqlite3.Connection, regole: Regole, rose: Rose | None, percorso: Path | None = None,
             simulazioni: int = SIMULAZIONI, file_scelte: Path | None = None, scadenza: float | None = None) -> int:
    """Aggiunge al diario le giornate finite che mancano (e quelle fatte senza la tua scelta, se nel frattempo l'hai salvata).
    Restituisce quante voci ha scritto. `scadenza` (ora di `time.monotonic()`): passata quella, non comincia altre giornate e
    salva quelle già fatte (il resto al giro dopo)."""
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
    for g in [x for x in rinvii.giornate_chiuse(db, stagione, regole) if x >= regole.prima_giornata_lega][-MASSIMO_GIORNATE:]:
        if scadenza is not None and time.monotonic() > scadenza:
            break
        chiave = f"{stagione}/{g}"
        ist = istantanee.get(chiave) if isinstance(istantanee.get(chiave), dict) else {}
        altri = [t["id"] for t in (ist.get("titolari") or []) + (ist.get("panchina") or [])
                 if isinstance(t, dict) and isinstance(t.get("id"), int) and t["id"] not in ids]
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
        vecchia = voci.get(chiave)
        impronta = impronta_regole(regole, stagione, g, rinvii.ha_fuori_turno(db, stagione, g))
        if vecchia:
            salta = False
            if vecchia.get("regole") != impronta:
                salta = bool(vecchia.get("schierata") and not scelta)      # regole cambiate ma la scelta non c'è più: non si perde quella schierata già nel diario
            elif vecchia.get("schierata") or (not scelta and not (auto and not vecchia.get("automatica"))):
                salta = True
            if salta:
                if "giocatori" not in vecchia:          # voce scritta prima dei numeri per giocatore: si completa senza simulazioni
                    numeri = numeri_giocatori(consigli.dati(db), stagione, g, regole, Parametri(), ids + altri)
                    if numeri is not None:
                        nuove_voci[chiave] = {**vecchia, "giocatori": numeri}
                continue
        voce = calcola_giornata(consigli.dati(db), stagione, g, regole, Parametri(), ids, scelta, simulazioni, auto, altri,
                                **per_il_consiglio(db, regole, stagione, g, dati_diario))
        if voce:
            nuove_voci[chiave] = voce
    if nuove_voci:
        _scrivi(percorso, voci=nuove_voci)
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
    """Il pezzo veloce: salva la scelta e la voce già calcolata."""
    stagione = consigli.stagione_corrente()
    scelte.salva(stagione, giornata, scelti, voce["schierata"]["modulo"], file_scelte, tipo=tipo)
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
        raise SchierataNonValida("Indica prima la tua squadra in Squadra > Squadre e rose")
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
                            **per_il_consiglio(db, regole, stagione, giornata, diario))
    if not voce or not voce["schierata"]:
        raise SchierataNonValida("Non riesco a valutare questa formazione per quella giornata")
    return voce, scelti


def sintesi(voci: list[dict]) -> dict:
    """Sulle giornate in cui hai schierato una tua formazione: punti medi fatti con la tua e con la consigliata."""
    con = [v for v in voci if v.get("schierata")]
    if not con:
        return {"giornate": 0}
    media = lambda f: round(sum(f(v) for v in con) / len(con), 1)      # noqa: E731
    return {"giornate": len(con), "punti_schierata": media(lambda v: v["schierata"]["reale"]),
            "punti_consigliata": media(lambda v: v["consigliata"]["reale"]),
            "attesi_schierata": media(lambda v: v["schierata"]["atteso"]),
            "meglio_tua": sum(1 for v in con if v["schierata"]["reale"] > v["consigliata"]["reale"]),
            "meglio_consigliata": sum(1 for v in con if v["schierata"]["reale"] < v["consigliata"]["reale"])}


POCHI_DATI = 8          # sotto questo numero di giornate la percentuale è troppo instabile: i client dicono «ancora pochi dati»


def scelte_tue(voci: list[dict]) -> dict:
    """Le giornate in cui hai schierato undici diversi da quelli consigliati: chi aveva ragione (punti fatti con la tua formazione
    contro quella consigliata). `differenza` = tua - consigliata (positiva: avevi ragione tu). Le voci vanno dalla più recente."""
    giornate = []
    for v in voci:
        s, c = v.get("schierata"), v.get("consigliata")
        if not s or not c or not s.get("titolari") or not c.get("titolari"):
            continue
        tue, loro = {t["id"] for t in s["titolari"]}, {t["id"] for t in c["titolari"]}
        if tue == loro:
            continue
        diff = round(s["reale"] - c["reale"], 1)
        giornate.append({"stagione": v["stagione"], "giornata": v["giornata"], "giornata_lega": v.get("giornata_lega"),
                         "hai_scelto": [t["nome"] for t in s["titolari"] if t["id"] not in loro],
                         "consigliava": [t["nome"] for t in c["titolari"] if t["id"] not in tue],
                         "punti_tua": s["reale"], "punti_consigliata": c["reale"], "differenza": diff,
                         "esito": "tua" if diff > 0 else "consigliata" if diff < 0 else "pari"})
    n = len(giornate)
    if not n:
        return {"giornate": 0, "pochi_dati": True, "per_giornata": []}
    meglio_tua = sum(1 for g in giornate if g["esito"] == "tua")
    return {"giornate": n, "meglio_tua": meglio_tua, "meglio_consigliata": sum(1 for g in giornate if g["esito"] == "consigliata"),
            "pari": sum(1 for g in giornate if g["esito"] == "pari"),
            "punti_differenza": round(sum(g["differenza"] for g in giornate), 1),
            "percentuale_tua": round(100 * meglio_tua / n), "pochi_dati": n < POCHI_DATI, "per_giornata": giornate}


COPERTURA_MINIMA = 0.6          # sotto questa quota di giornate dentro la fascia (dichiarata: 8 su 10) il periodo è «andato peggio del previsto»


def atteso_vs_fatto(voce: dict) -> dict | None:
    """Per una giornata finita: i punti che SchieraXI si aspettava dalla formazione consigliata (ricostruita con i dati di allora),
    quelli fatti, lo scarto (fatti meno attesi, positivo = meglio del previsto) e se sono caduti dentro la fascia «tra X e Y».
    La consigliata c'è in ogni voce, così il confronto vale ogni giornata allo stesso modo."""
    c = voce.get("consigliata")
    if not isinstance(c, dict) or c.get("atteso") is None or c.get("reale") is None:
        return None
    basso, alto = (c.get("intervallo") or {}).get("basso"), (c.get("intervallo") or {}).get("alto")
    dentro = None if basso is None or alto is None else bool(basso <= c["reale"] <= alto)
    return {"riferimento": "consigliata", "atteso": c["atteso"], "fatti": c["reale"], "scarto": round(c["reale"] - c["atteso"], 1),
            "nella_fascia": dentro, "intervallo": {"basso": basso, "alto": alto} if dentro is not None else None}


def affidabilita(voci: list[dict]) -> dict:
    """Quanto ci ha preso SchieraXI sui punti della squadra, giornata per giornata, ANCHE quando va male. Tutto si ricalcola dalle voci:
    `scarto_medio` = media degli scarti senza segno (in punti), `errore_medio` = media con segno (negativo: i punti veri sono stati
    meno dei previsti), `dentro_fascia` = in quante giornate i punti fatti sono caduti nella fascia prevista (dichiarata: 8 su 10).
    `giudizio`: `pochi_dati` (meno di POCHI_DATI giornate), `in_linea`, oppure `sotto_le_attese` / `sopra_le_attese` se la quota dentro
    la fascia è sotto COPERTURA_MINIMA (dice se i punti veri sono stati meno o più dei previsti)."""
    righe = [r for r in (atteso_vs_fatto(v) for v in voci) if r]
    n = len(righe)
    if not n:
        return {"giornate": 0, "giudizio": "pochi_dati", "pochi_dati": True, "giornate_minime": POCHI_DATI}
    con_fascia = [r for r in righe if r["nella_fascia"] is not None]
    dentro = sum(1 for r in con_fascia if r["nella_fascia"])
    quota = dentro / len(con_fascia) if con_fascia else None
    errore = sum(r["scarto"] for r in righe) / n
    pochi = n < POCHI_DATI
    giudizio = "pochi_dati" if pochi else "in_linea" if quota is None or quota >= COPERTURA_MINIMA else "sotto_le_attese" if errore < 0 else "sopra_le_attese"
    return {"giornate": n, "scarto_medio": round(sum(abs(r["scarto"]) for r in righe) / n, 1), "errore_medio": round(errore, 1),
            "punti_medi_attesi": round(sum(r["atteso"] for r in righe) / n, 1), "punti_medi_fatti": round(sum(r["fatti"] for r in righe) / n, 1),
            "dentro_fascia": dentro, "con_fascia": len(con_fascia), "percentuale_dentro": None if quota is None else round(100 * quota),
            "fascia_dichiarata": round(100 * incertezza.CONFIDENZA), "pochi_dati": pochi, "giornate_minime": POCHI_DATI, "giudizio": giudizio}


def motivo_vuoto(db: sqlite3.Connection, regole: Regole, rose: Rose | None) -> str:
    """Perché il diario è vuoto, per dirlo all'utente: «squadra» (non hai indicato la tua), «giornate» (nessuna giornata finita della
    lega), «calcolo» (tutto a posto, le voci si calcolano al prossimo aggiornamento o al tocco su «Ho schierato la consigliata»)."""
    if not (rose and rose.mia_squadra and rose.squadra(rose.mia_squadra)):
        return "squadra"
    if not [g for g in rinvii.giornate_chiuse(db, consigli.stagione_corrente(), regole) if g >= regole.prima_giornata_lega]:
        return "giornate"
    return "calcolo"


def elenco(percorso: Path | None = None, regole: Regole | None = None) -> dict:
    """Le voci dalla più recente, con la sintesi: quello che mostra l'app. Con le regole della lega, la stagione in corso conta solo
    dalla prima giornata della lega e ogni voce porta anche `giornata_lega` (il numero nel calendario della lega)."""
    d = carica(percorso)
    istantanee = d["istantanee"] if isinstance(d.get("istantanee"), dict) else {}
    voci = sorted(d["giornate"].values(), key=lambda v: (v["stagione"], v["giornata"]), reverse=True)
    corrente = consigli.stagione_corrente()
    if regole is not None:
        voci = [v for v in voci if v["stagione"] != corrente or v["giornata"] >= regole.prima_giornata_lega]
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
        for k in ("consigliata", "schierata", "automatica"):     # file vecchi senza fascia: la si calcola senza la parte simulata
            if v.get(k) and "intervallo" not in v[k]:
                v[k]["intervallo"] = incertezza.intervallo(v[k]["atteso"], v[k].get("dev_simulata", 0.0))
    for v in voci:
        v["atteso_vs_fatto"] = atteso_vs_fatto(v)
    return {"giornate": voci, "sintesi": sintesi(voci), "scelte_tue": scelte_tue(voci), "affidabilita": affidabilita(voci)}
