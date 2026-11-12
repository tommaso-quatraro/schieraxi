"""Consigli pronti da mostrare (comando e app): formazione con le spiegazioni, confronto tra due giocatori."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Collection
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import calcolo, etichette, frasi, incertezza, limiti, perche
from . import formazione as fz
from . import modello, perche_scelta, rinvii, scelte, stato_dati, turno
from .aggiorna import Stagione
from .blocco import BloccoFile
from .frasi import F
from .lega import Rose, Squadra
from .notifiche import SOGLIA_AVVISO_PUNTI
from .percorsi import RADICE, scrivi_sicuro
from .regole import Regole, serie_a_a_lega

LOG = logging.getLogger(__name__)

# Risultati già calcolati (vedi calcolo.py: cache con tetto, al massimo due calcoli pesanti insieme, risposta «sto calcolando»).
# Le chiavi contengono la "versione" dei dati (ora dell'ultimo aggiornamento), così un risultato calcolato con dati vecchi
# non può essere scambiato per uno nuovo. Il server usa più thread.
_cache = calcolo.cache
_blocco = threading.RLock()      # per chi legge e scrive `_cache` a più passi (gestione.py)
FINESTRA_TURNO = turno.FINESTRA             # un turno di Serie A dura al massimo da venerdì a lunedì: oltre è un recupero
MARGINE_RISULTATI = timedelta(hours=12)     # dopo l'ultima partita si aspettano i risultati al massimo mezza giornata
SENZA_CALENDARIO ="Il calendario della stagione non è ancora disponibile (di solito esce a luglio): previsioni e asta partono appena arriva. Aggiorna i dati più avanti."


def _versione(db: sqlite3.Connection) -> str | None:
    """Cambia a ogni aggiornamento registrato. Non basta l'ora più recente: alla fine dell'ora legale (le 2:00-3:00 si ripetono)
    un aggiornamento nuovo può avere un'ora «più vecchia» di un altro e la versione non cambierebbe. Quindi: l'ora più recente
    (leggibile) più un'impronta di tutte le righe. Finché le previsioni sono di ripiego (vedi `_ripieghi`) ha in più un pezzo che
    cambia ogni RIPIEGO_SECONDI: i risultati di ripiego non restano in cache e il calcolo si riprova."""
    righe = db.execute("SELECT cosa, quando FROM aggiornamenti ORDER BY cosa").fetchall()
    if not righe:
        return None
    impronta = hashlib.sha1("\n".join(f"{c}={q}" for c, q in righe).encode()).hexdigest()[:12]
    versione = f"{max(str(q or '') for _, q in righe)}|{impronta}"
    if _ripieghi and _archivio(db) in _ripieghi:
        versione += f"|ripiego{int(time.monotonic() // RIPIEGO_SECONDI)}"
    return versione


# Previsioni di ripiego: c'è una riga attiva della taratura di «gioca N%» ma il registro non si legge, quindi numeri di partenza
# (`stato_dati.taratura_e_fattori`). Non devono restare in cache con la versione dei dati di sempre: finché l'archivio sta qui,
# `_versione` cambia ogni RIPIEGO_SECONDI (i risultati si rifanno, e con loro tutto quello che ne dipende); il primo calcolo
# riuscito toglie l'archivio e la versione torna quella di sempre.
RIPIEGO_SECONDI = 300
_ripieghi: dict[str, bool] = {}


def _archivio(db: sqlite3.Connection) -> str:
    return str(calcolo._percorso_db(db) or ":memory:")


def _segna_ripiego(db: sqlite3.Connection, ripiego: bool) -> None:
    if ripiego:
        _ripieghi[_archivio(db)] = True
    elif _ripieghi:
        _ripieghi.pop(_archivio(db), None)


def dati(db: sqlite3.Connection) -> modello.Dati:
    """Dati del modello, ricaricati solo se l'archivio è cambiato da un aggiornamento."""
    versione = _versione(db)
    chiave = ("dati", versione)
    pronti = _cache.get(chiave, calcolo.MANCA)
    if pronti is not calcolo.MANCA:
        return pronti
    return calcolo.ottieni(chiave, lambda d: _ricarica(d, chiave), db, fissa=True)


def _ricarica(db: sqlite3.Connection, chiave) -> modello.Dati:
    _cache.clear()                   # i risultati calcolati con i dati di prima non servono più
    return modello.carica(db)


def stagione_corrente() -> str:
    return Stagione.di(date.today()).codice


def _adesso() -> datetime:
    return datetime.now()          # ora locale del server (Europe/Rome), come le date del calendario


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " "))
    except ValueError:
        return None


def prossima_giornata(db: sqlite3.Connection, stagione: str, adesso: datetime | None = None) -> int | None:
    """La giornata in corso o, se non ce n'è una, la prossima. È la prima con almeno metà delle partite ancora da giocare,
    oppure con anche una sola partita da giocare nel suo turno (regola unica in turno.py, come la scadenza) e non passata da più di
    MARGINE_RISULTATI: così la domenica sera e i posticipi del lunedì tengono aperta la giornata finché non sono finite tutte.
    Un recupero isolato (rinviato a settimane dopo, o rimasto con la vecchia data) non tiene ferma la giornata."""
    adesso = adesso or _adesso()
    per_giornata: dict[int, list[tuple[datetime | None, bool]]] = {}
    for g, testo, giocata in db.execute("SELECT giornata, data, giocata FROM partite WHERE stagione = ? ORDER BY giornata",
                                        (stagione,)):
        per_giornata.setdefault(g, []).append((_data(testo) if testo else None, bool(giocata)))
    for g in sorted(per_giornata):
        partite = per_giornata[g]
        aperte = [d for d, giocata in partite if not giocata]
        # 5 o più partite aperte tengono la giornata, ma non se sono TUTTE passate da più di MARGINE_RISULTATI: vuol dire che
        # il calendario non si aggiorna (fonte giù) e quella giornata è già stata giocata
        if len(aperte) >= 5 and any(d is None or d >= adesso - MARGINE_RISULTATI for d in aperte):
            return g
        inizio = turno.inizio(d for d, _ in partite)
        if aperte and inizio and any(d and turno.nel_turno(d, inizio) and d >= adesso - MARGINE_RISULTATI for d in aperte):
            return g
    return None


def giornata_da_giocare(db: sqlite3.Connection, stagione: str, regole: Regole | None, adesso: datetime | None = None) -> int | None:
    """La prossima giornata PER LA LEGA: come `prossima_giornata`, ma mai prima della prima giornata della lega
    (regole.prima_giornata_lega). Prima che la lega parta, la «giornata da giocare» è la sua prima.
    `adesso`: l'ora da usare (per i test e per chi l'ha già fissata); senza, l'ora vera."""
    g = prossima_giornata(db, stagione, adesso)
    if g is None or regole is None:
        return g
    return max(g, regole.prima_giornata_lega)


def previsioni(db: sqlite3.Connection, regole: Regole, giornata: int | None = None) -> tuple[pd.DataFrame, int, bool]:
    """(previsioni di tutti i giocatori, giornata, se ci sono le probabili formazioni)."""
    stagione = stagione_corrente()
    giornata = giornata or giornata_da_giocare(db, stagione, regole)
    if giornata is None:
        raise ValueError(SENZA_CALENDARIO)
    chiave = ("prev", _versione(db), giornata, repr(regole))
    return calcolo.ottieni(chiave, lambda d: _calcola_previsioni(d, dati(d), regole, stagione, giornata, chiave), db)


def _calcola_previsioni(db, d, regole, stagione, giornata, chiave):
    prob = pd.read_sql_query("SELECT * FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio'",
                             db, params=(stagione, giornata))
    # «gioca N%» con le probabili: la riga attiva della taratura sul server, se c'è (None = numeri di partenza), e la correzione
    # per gruppi fatta con la stessa formula. Quando la riga attiva cambia, cambia anche `_versione` (riga in `aggiornamenti`) e
    # queste previsioni si rifanno. Se il registro non si legge: numeri di partenza, e `_versione` lo dice (vedi `_ripieghi`)
    taratura, fattori, ripiego = stato_dati.taratura_e_fattori(db, stagione)
    _segna_ripiego(db, ripiego)
    p = modello.previsioni(d, stagione, giornata, regole, probabili=None if prob.empty else prob,
                           giocatori=d.calciatori, fattori_probabili=fattori, taratura=taratura)
    if p.empty:
        raise ValueError(frasi.elidi_ordinali(f"Non ci sono ancora previsioni per la {frasi.nome_giornata(giornata, serie_a_a_lega(giornata, regole))}: riprova più tardi."))
    p = p.set_index("id")
    p["difficolta"] = (p["gol_squadra"] - p["gol_avversario"]).map(difficolta)
    # «perché questo numero» (perche.py): spiega mu con i suoi pezzi veri, non cambia nessun numero
    p["perche_numero"], p["fv_atteso_medio_ruolo"] = perche.calcola(p, regole)
    # partite rinviate: la regola della lega (o l'eccezione per questa giornata) dopo il «perché», che spiega il modello di sempre
    r = rinvii.regola(regole, stagione, giornata)
    p = rinvii.applica(p, rinvii.id_rinviate(d.partite, stagione, giornata), r)
    p["perche_numero"] = rinvii.perche(p, r, perche.MAX_MOTIVI)
    p["indice"] = _indice(p)
    return (p, giornata, not prob.empty)


def difficolta(differenza: float) -> int:
    """Quanto è dura la partita per la squadra: 1 (molto facile) ... 5 (molto difficile), dai gol attesi di differenza."""
    return 1 if differenza >= 0.9 else 2 if differenza >= 0.3 else 3 if differenza > -0.3 else 4 if differenza > -0.9 else 5


def _indice(p: pd.DataFrame) -> pd.Series:
    """Indice 0-100: dove si colloca il giocatore tra quelli del suo ruolo per punti attesi questa giornata
    (100 = il migliore). Contano solo i giocatori che hanno una probabilità reale di giocare."""
    risultato = pd.Series(0.0, index=p.index)
    for _, g in p.groupby("ruolo"):
        pool = np.sort(g.loc[g["p_voto"] >= 0.2, "atteso"].to_numpy())
        if len(pool):
            risultato.loc[g.index] = 100 * np.searchsorted(pool, g["atteso"].to_numpy(), side="right") / len(pool)
    return risultato.clip(0, 100).round(0)


FUORI = ("infortunato", "squalificato")
# sotto questa percentuale delle probabili (quella della fonte, che non si mostra) un titolare è «in ballottaggio»
PERC_BALLOTTAGGIO = 60
# «Rigorista»: chi, quando gioca, calcia almeno questa parte dei rigori della sua squadra (`quota_rigori` della previsione).
# Prima la frase guardava i rigori attesi a partita (almeno 0,15): una squadra ne calcia circa 0,14, quindi non usciva mai (#613).
QUOTA_RIGORISTA = 0.5


def _numero(v) -> float:
    """`v` come numero; 0 se manca (previsione senza quel campo) o non è un numero."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if np.isnan(n) else n


def rigorista(x) -> bool:
    """Vero se, quando gioca, calcia almeno QUOTA_RIGORISTA dei rigori della sua squadra (`quota_rigori` della previsione `x`) ed
    è il primo della squadra fra chi può giocare (`primo_rigorista`; senza la colonna vale la sola quota): uno per squadra.
    È la regola unica di «rigorista»: il motivo della scheda (`motivi`) e l'elenco `rigoristi` di `/api/widget` passano di qui.
    Chi è infortunato o squalificato, o ha la partita rinviata senza voto, non lo è: la scheda non gli dice niente sui rigori."""
    if x.get("stato") in FUORI or _rinvio(x) in ("senza_voto", "voto_ufficio"):
        return False
    primo = x.get("primo_rigorista")
    if primo is not None and not pd.isna(primo) and not bool(primo):
        return False
    return _numero(x.get("quota_rigori")) >= QUOTA_RIGORISTA


def titolarita(x: pd.Series) -> str:
    """Etichetta semplice, a parole (senza numero): quanto è sicuro che giochi. L'unico numero mostrato è «gioca N%» (`p_voto`);
    chi le probabili danno titolare e ha `p_voto` alto è titolare anche se finora è partito spesso dalla panchina."""
    stato = x.get("stato")
    if stato in FUORI or _rinvio(x) == "senza_voto":          # senza voto per la partita rinviata
        return "fuori"
    p, q = float(x["p_voto"]), float(x["quota_titolare"])
    if p >= 0.8 and (q >= 0.6 or stato == "titolare"):
        return "titolare"
    return "ballottaggio" if p >= 0.5 else "panchina" if p >= 0.2 else "improbabile"


def motivi(x: pd.Series) -> list[str]:
    """Perché il modello dà quel valore: frasi brevi per l'utente (`Frase`: testo italiano e chiave per tradurlo; la nota delle
    fonti è un testo semplice, lo traduce il server con note_infortuni.py). Nessuna percentuale sul giocare: l'unica è «gioca N%»
    (`p_voto`), qui le probabili diventano parole. Chi è infortunato o squalificato non gioca: niente frasi sulla partita, i gol
    o i rigori."""
    m = []
    if _rinvio(x) in ("senza_voto", "voto_ufficio"):          # la partita non si gioca in questa giornata: conta solo questo
        return [_frase_rinvio(x)]
    if _rinvio(x):
        m.append(_frase_rinvio(x))
    stato, perc = x.get("stato"), x.get("percentuale")
    if stato == "titolare":
        m.append(F("motivo.titolare_ballottaggio") if pd.notna(perc) and perc < PERC_BALLOTTAGGIO else F("motivo.titolare"))
    elif stato == "panchina":
        m.append(F("motivo.panchina"))
    elif stato in FUORI:
        m.append(F("motivo." + stato))
    elif stato == "non_citato":
        m.append(F("motivo.non_convocato"))
    if pd.notna(x.get("nota")) and x.get("nota"):
        m.append(str(x["nota"]))
    if stato in FUORI:
        return m
    if rigorista(x):
        m.append(F("motivo.rigorista"))
    if x["ruolo"] == "P":
        m.append(F("motivo.porta_inviolata", p=round(float(x["p_imbattuto"]) * 100)))
    elif x["e_gol"] >= 0.3:
        # la probabilità di segnare almeno un gol (la stessa di «segna N%» nella scheda), non i gol attesi scritti come percentuale
        p_gol = x.get("p_gol")
        p_gol = float(p_gol) if p_gol is not None and pd.notna(p_gol) else 1 - float(np.exp(-float(x["e_gol"])))
        m.append(F("motivo.gol_atteso", p=round(p_gol * 100)))
    if x["gol_squadra"] - x["gol_avversario"] >= 0.8:
        m.append(F("motivo.favorevole"))
    elif x["gol_avversario"] - x["gol_squadra"] >= 0.8:
        m.append(F("motivo.difficile"))
    return m


def _rinvio(x) -> str | None:
    """Il modo del rinvio della sua partita (colonna `rinvio`), o None se si gioca (o con previsioni senza la colonna)."""
    v = x.get("rinvio")
    return v if isinstance(v, str) else None


def _frase_rinvio(x) -> str:
    modo = _rinvio(x)
    return rinvii.frase(modo, float(x["mu"]) if modo == "voto_ufficio" else None, x.get("data_partita"))


def scheda_previsione(i: int, x: pd.Series) -> dict:
    x = x.to_dict()           # una volta sola: leggere ogni campo dalla Series di pandas costa circa 10 volte di più (e qui sono una trentina)
    elenco_motivi = motivi(x)
    s = {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "squadra": x["squadra"], "avversario": x["avversario"],
        "in_casa": bool(x["in_casa"]), "p_voto": round(float(x["p_voto"]), 3), "fv_atteso": round(float(x["mu"]), 2),
        "voto_atteso": round(float(x["mu_voto"]), 2), "punti_attesi": round(float(x["atteso"]), 2),
        "gol_attesi": round(float(x["e_gol"]), 3), "assist_attesi": round(float(x["e_assist"]), 3),
        "rigori_attesi": round(float(x["e_rigori"]), 3), "porta_inviolata": round(float(x["p_imbattuto"]), 3),
        "p_gol": float(x["p_gol"]), "p_assist": float(x["p_assist"]),
        "p_giallo": float(x["p_giallo"]), "p_rosso": float(x["p_rosso"]),
        "quota_titolare": float(x["quota_titolare"]),
        "indice": int(x["indice"]), "difficolta": int(x["difficolta"]), "titolarita": titolarita(x),
        "dubbio": bool(x["dubbio"]), "diffidato": bool(x["diffidato"]),
        "data_partita": None if pd.isna(x["data_partita"]) else str(x["data_partita"]),
        "gol_squadra": float(x["gol_squadra"]), "gol_avversario": float(x["gol_avversario"]),
        "stato": None if pd.isna(x["stato"]) else x["stato"],
        "percentuale": None if pd.isna(x["percentuale"]) else float(x["percentuale"]),
        "nota": None if pd.isna(x["nota"]) else x["nota"], "motivi": elenco_motivi, "motivi_frasi": frasi.lista(elenco_motivi),
        # «perché questo numero» (fanta/perche.py): al massimo 3 motivi, in fantavoti rispetto a un giocatore medio dello stesso ruolo
        "perche_numero": list(x.get("perche_numero") or []),
        "fv_atteso_medio_ruolo": None if pd.isna(x.get("fv_atteso_medio_ruolo", float("nan"))) else float(x["fv_atteso_medio_ruolo"]),
        # partita rinviata: la regola che vale per questa giornata (aspetta, senza_voto, voto_ufficio); null se la partita si gioca
        "rinvio": _rinvio(x),
    }
    s["etichetta"] = etichette.di_giocatore(s)       # stato a parole, pronto per i client (fanta/etichette.py)
    return s


# Titolare poco sicuro con una riserva quasi sicura dello stesso ruolo: la scelta è giusta (se lui non gioca c'è la riserva, e
# insieme valgono di più che la riserva da sola) ma a prima vista sembra un errore, quindi la si spiega. Soglie su `p_voto` (`Giocatore.p`).
INCERTO_SOTTO = 0.5        # il titolare gioca meno di così...
RISERVA_SOPRA = 0.8        # ...e la riserva che copre il suo posto più di così


def incerti(titolari: list, panchina: list) -> list[dict]:
    """I titolari incerti e la riserva sicura dello stesso ruolo: [{titolare, riserva}] (id), dal titolare più incerto. La riserva
    è la prima del ruolo, nell'ordine della panchina, che gioca più di RISERVA_SOPRA, una sola per titolare (con due incerti dello
    stesso ruolo il secondo prende la riserva sicura dopo); `riserva` = None se in panchina non ce n'è una.
    Non è per forza chi entra per primo: la panchina è in ordine di fantavoto atteso (#612), quindi davanti può esserci un compagno
    che vale di più e gioca meno spesso. Prima di #612 si guardava solo la prima riserva del ruolo, che era quasi sempre la più
    sicura; con l'ordine nuovo la riga si perdeva per due titolari incerti su tre."""
    usate: set[int] = set()
    risultato = []
    for t in sorted((g for g in titolari if g.p < INCERTO_SOTTO), key=lambda g: g.p):
        r = next((b for b in panchina if b.ruolo == t.ruolo and b.id not in usate and b.p > RISERVA_SOPRA), None)
        if r is not None:
            usate.add(r.id)
        risultato.append({"titolare": int(t.id), "riserva": None if r is None else int(r.id)})
    return risultato


def _moduli(tutte: list) -> list[dict]:
    return [{"modulo": x.modulo, "punteggio_atteso": round(x.atteso, 1), **incertezza.campi(x.atteso, x.dev),
             "titolari": [g.id for g in x.titolari], "panchina": [g.id for g in x.panchina],
             "incerti": incerti(x.titolari, x.panchina)} for x in tutte]


def formazione(db: sqlite3.Connection, regole: Regole, rose: Rose, nome_squadra: str | None = None,
               giornata: int | None = None, simulazioni: int = 600, adesso: datetime | None = None) -> dict:
    """La formazione consigliata. `adesso`: l'ora con cui cercare la giornata e contare scadenza passata e anticipi cominciati nella
    risposta (per chi l'ha già fissata, come il giro degli avvisi, e per le prove); senza, l'ora vera. Ricordare la consigliata invece
    deve andare bene anche per l'ora vera (`_si_ricorda`)."""
    s = rose.squadra(nome_squadra or rose.mia_squadra or "")
    if not s:
        raise ValueError("Squadra non trovata: indica la tua squadra in Squadra > Squadre e rose")
    stagione = stagione_corrente()
    giornata = giornata or giornata_da_giocare(db, stagione, regole, adesso)
    if giornata is None:
        raise ValueError(SENZA_CALENDARIO)
    # La consigliata già mostrata per questa squadra e giornata (#335): resta finché la migliore non vale almeno SOGLIA_CAMBIO_PUNTI in
    # più o un suo titolare non gioca più (`stabile`); dopo la scadenza resta e basta. Tutti passano di qui (Formazione, Oggi, widget,
    # Da fare, avvisi, copia alla scadenza): leggono la stessa.
    impronta = _impronta(stagione, giornata, s, regole, simulazioni)
    prima = _consigliate().get(impronta)
    prima = prima if _ids(prima, "titolari") is not None else None          # voce rovinata: come se non ci fosse
    chiusa = _chiusa(db, regole, stagione, giornata, adesso)
    # Anticipi già cominciati (#368): con la formazione ancora aperta i loro giocatori restano dove sono nella consigliata di prima.
    # Dopo la scadenza resta già tutta; senza una consigliata di prima non c'è niente da tenere.
    iniziate = () if chiusa or prima is None else _anticipi_iniziati(db, stagione, giornata, adesso)
    # stessa squadra, rosa, giornata, regole e dati: stesso risultato (svuotata quando i dati cambiano). Anche i nomi della rosa:
    # quelli dei giocatori non riconosciuti (o senza previsione) finiscono nella risposta (`senza_dati`), e la memoria è di tutti.
    chiave = ("formazione", _versione(db), s.nome, tuple((g.id, g.nome) for g in s.giocatori), giornata, repr(regole),
              simulazioni)
    chiave_stabile = chiave + ("stabile", _firma(prima, chiusa or bool(iniziate)), chiusa, iniziate)

    def con_la_stabile(d, migliore: dict) -> dict:
        return stabile(migliore, prima, previsioni(d, regole, giornata)[0], s, regole, simulazioni, chiusa, iniziate)

    def da_rivedere(migliore: dict) -> bool:
        return prima is not None and (bool(iniziate) or not _stessa(prima, migliore, chiusa))

    def pronta(d) -> dict:
        migliore = _formazione_pronta(d, s, giornata, regole, simulazioni)
        if da_rivedere(migliore):                       # nello stesso giro: un solo «sto calcolando»
            _cache.metti(chiave_stabile, con_la_stabile(d, migliore), peso=calcolo.PESO_LEGGERO)
        return migliore
    f = migliore = calcolo.ottieni(chiave, pronta, db, peso=calcolo.PESO_LEGGERO)
    if da_rivedere(migliore):
        f = calcolo.ottieni(chiave_stabile, lambda d: con_la_stabile(d, migliore), db, peso=calcolo.PESO_LEGGERO)
    if _si_ricorda(db, regole, stagione, giornata, prima, chiusa, iniziate, adesso):
        _ricorda(impronta, f, stagione, giornata, prima, propria=s.nome == rose.mia_squadra)
    return f


def _si_ricorda(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, prima: dict | None, chiusa: bool,
                iniziate: tuple[str, ...], adesso: datetime | None) -> bool:
    """Se la consigliata appena calcolata si ricorda, cioè diventa quella mostrata da lì in poi: senza una di prima sempre, con una di
    prima solo a formazione aperta. Con un'ora data (`adesso`, che il giro degli avvisi fissa al suo inizio) anche per l'ora vera la
    formazione deve essere aperta, con gli stessi anticipi cominciati: la risposta segue l'ora data, ma un giro partito prima della
    scadenza o di un anticipo non cambia mai la consigliata già fissata (#335, #368)."""
    if prima is None:
        return True
    if chiusa:
        return False
    return adesso is None or (not _chiusa(db, regole, stagione, giornata) and _anticipi_iniziati(db, stagione, giornata) == iniziate)


def _formazione_pronta(db, s, giornata, regole, simulazioni) -> dict:
    prev, giornata, con_probabili = previsioni(db, regole, giornata)
    return _calcola_formazione(s, prev, giornata, con_probabili, regole, simulazioni)


def _rosa(s: Squadra, prev: pd.DataFrame) -> list[fz.Giocatore]:
    """I giocatori della squadra che hanno una previsione per la giornata, nell'ordine della rosa (lo stesso ordine dà le stesse
    simulazioni: la consigliata e quella di prima si confrontano alla pari)."""
    ids = [g.id for g in s.giocatori if g.id is not None]
    return [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                         float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids if i in prev.index]


def _calcola_formazione(s, prev, giornata, con_probabili, regole, simulazioni, fermi: Fermi | None = None) -> dict:
    """La risposta della Formazione con la migliore di adesso. Con `fermi` (anticipi già cominciati, #368) ogni modulo e ogni
    stile li lascia dove sono."""
    rosa = _rosa(s, prev)
    val = fz.Valutatore(rosa, regole, simulazioni)           # le stesse simulazioni per tutti i livelli: i calcoli si riusano
    candidati, vincoli = (rosa, {}) if fermi is None else fermi.per_la_ricerca(rosa, regole)
    try:
        f = fz.migliore(candidati, regole, simulazioni, valutatore=val, **vincoli)
    except ValueError:
        raise ValueError("Non si riesce a formare una squadra: in qualche ruolo nessuno gioca questa giornata") from None
    livelli = []
    for rischio, nome, peso, inclinazione, descrizione in fz.LIVELLI_RISCHIO:
        fl = f if (peso, inclinazione) == (fz.PESO_BASE, (0.0, 0.0)) else fz.migliore(
            candidati, regole, simulazioni, peso=peso, valutatore=val, inclinazione=inclinazione, **vincoli)
        livelli.append({"rischio": rischio, "stile": rischio, "nome": nome, "descrizione": descrizione, "modulo": fl.modulo,
                        "punteggio_atteso": round(fl.atteso, 1), **incertezza.campi(fl.atteso, fl.dev),
                        "moduli": _moduli(fl.tutte)})
    scelti = {g.id for g in f.titolari + f.panchina}
    fuori = [scheda_previsione(g.id, prev.loc[g.id]) for g in rosa if g.id not in scelti]
    senza_dati = [g.nome for g in s.giocatori if g.id is None or g.id not in prev.index]
    risultato = {
        "squadra": s.nome, "giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole), "modulo": f.modulo, "punteggio_atteso": round(f.atteso, 1),
        "alternative": [{"modulo": m, "punteggio_atteso": v} for m, v in f.alternative],
        "titolari": [scheda_previsione(g.id, prev.loc[g.id]) for g in f.titolari],
        "panchina": [scheda_previsione(g.id, prev.loc[g.id]) for g in f.panchina],
        "fuori": sorted(fuori, key=lambda x: -x["punti_attesi"]),
        "senza_dati": senza_dati, "con_probabili": con_probabili,
        # la formazione migliore per ogni modulo (l'app li fa scorrere come Algo); i dettagli dei giocatori in "schede"
        # `dev` e `intervallo` sono calibrati sul backtest (incertezza.py): la fascia contiene i punti veri circa 8 volte su 10
        "moduli": _moduli(f.tutte), **incertezza.campi(f.atteso, f.dev),
        # la stessa scelta per ogni livello di rischio (da molto sicura a molto rischiosa): quella di base è la consigliata
        # ogni livello è uno STILE completo (preset): profilo di rischio dei giocatori + preferenza di modulo + testo di una riga
        "livelli": livelli, "stile_consigliato": 0,
        "schede": {str(g.id): scheda_previsione(g.id, prev.loc[g.id]) for g in rosa},
    }
    return perche_scelta.aggiungi(risultato, rosa, regole, val)       # il perché delle scelte che sembrano storte (#356)


# ---------------------------------------------------------------- consigliata stabile (#335)
# La consigliata già mostrata per una giornata cambia solo se la nuova vale almeno questi punti attesi in più, ricalcolati con i dati
# nuovi: è la soglia dell'avviso alla scadenza, così app e avvisi dicono la stessa cosa. Sotto è il su e giù normale dei dati
# (misura del 5/11/2026: quando 3 o più titolari cambiano per un ritocco, la nuova vale in mediana 3-4 centesimi di punto).
SOGLIA_CAMBIO_PUNTI = SOGLIA_AVVISO_PUNTI
NON_GIOCA = ("fuori", "improbabile")      # `titolarita`: infortunato, squalificato, senza voto per il rinvio, o gioca meno del 20%
# Le consigliate già mostrate, una per squadra e giornata:
# {impronta: {stagione, giornata, modulo, titolari, panchina, non_giocano, quando}} (`da_ricordare`).
# Comune a tutti come la cache dei calcoli (stessa squadra, rosa e regole: stessa consigliata), ma sopravvive ai riavvii e vale
# anche per i comandi lanciati a parte (avvisi, sentinella). Solo id di giocatori: la chiave è un'impronta, niente nomi.
# Parte di ciascuno (#513): con gli account ogni voce ha anche `utenti` (id di chi l'ha vista); un utente ne tiene al massimo
# `limiti.MAX_CONSIGLIATE_UTENTE`, oltre perde le sue più vecchie (una voce che serve anche ad altri resta per loro). Le voci
# senza `utenti` (senza account, comandi) contano solo nel tetto di tutto il file. Per quel tetto escono prima le più vecchie
# fuori dalla parte riservata di ciascuno (`_riservate`: al massimo `RISERVATE_UTENTE` voci, prima la più recente della propria
# squadra per ogni giornata, campo facoltativo `proprie`); quelle riservate solo se da sole lo superano.
FILE_CONSIGLIATE = RADICE / "dati" / "consigliate.json"
MAX_CONSIGLIATE = 1000                    # oltre, esce la più vecchia: ~250 byte l'una
RISERVATE_UTENTE = 10                     # le ultime consigliate di ogni utente: escono per ultime dal tetto di tutto il file
_blocco_consigliate = threading.Lock()
_letto: tuple = (None, {})                # (firma del file, contenuto): si rilegge solo quando il file cambia


def _ids(prima, chiave: str) -> list[int] | None:
    v = prima.get(chiave) if isinstance(prima, dict) else None
    if not isinstance(v, list):
        return None
    try:
        return [int(i) for i in v]
    except (TypeError, ValueError):
        return None


def _stessa(prima: dict, f: dict, chiusa: bool) -> bool:
    """La consigliata di prima ha gli stessi titolari della risposta `f` (dopo la scadenza anche la stessa panchina, in ordine)."""
    titolari = _ids(prima, "titolari")
    if titolari is None or set(titolari) != {int(g["id"]) for g in f.get("titolari") or []}:
        return False
    return not chiusa or (_ids(prima, "panchina") or []) == [int(g["id"]) for g in f.get("panchina") or []]


def _firma(prima: dict | None, chiusa: bool) -> tuple:
    """Ciò della consigliata di prima da cui dipende la risposta, per la chiave della cache: i titolari e chi di loro già non
    giocava; dopo la scadenza anche la panchina (prima della scadenza la panchina la rifà il sistema)."""
    return (tuple(sorted(_ids(prima, "titolari") or [])), tuple(sorted(_ids(prima, "non_giocano") or [])),
            tuple(_ids(prima, "panchina") or []) if chiusa else ())


def da_ricordare(f: dict, prima: dict | None = None) -> dict | None:
    """La consigliata `f` come si ricorda: modulo, id di titolari e panchina, e i titolari che già non giocavano (fuori o
    improbabili) quando è stata mostrata. Con gli stessi titolari di `prima` quell'elenco resta quello di allora.
    None se `f` non ha 11 titolari."""
    titolari = [int(g["id"]) for g in f.get("titolari") or []]
    if len(titolari) != 11:
        return None
    if prima is not None and set(_ids(prima, "titolari") or []) == set(titolari):
        non_giocano = _ids(prima, "non_giocano") or []
    else:
        non_giocano = [int(g["id"]) for g in f["titolari"] if g.get("titolarita") in NON_GIOCA]
    return {"modulo": str(f.get("modulo", ""))[:8], "titolari": titolari,
            "panchina": [int(g["id"]) for g in f.get("panchina") or []], "non_giocano": non_giocano}


def _impronta(stagione: str, giornata: int, s: Squadra, regole: Regole, simulazioni: int) -> str:
    """La chiave della consigliata ricordata: stagione, giornata, squadra, rosa, regole e simulazioni, in un'impronta."""
    testo = json.dumps([stagione, int(giornata), s.nome, sorted(g.id for g in s.giocatori if g.id is not None), repr(regole),
                        simulazioni], ensure_ascii=False)
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:32]


def _consigliate() -> dict:
    """Le consigliate ricordate; {} se il file non c'è o è rovinato."""
    global _letto
    file = FILE_CONSIGLIATE
    try:
        st = file.stat()
    except OSError:
        return {}
    firma = (str(file), st.st_mtime_ns, st.st_size, st.st_ino)
    if _letto[0] == firma:
        return _letto[1]
    try:
        d = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    _letto = (firma, d)
    return d


def _utenti(voce) -> list[int]:
    """Gli id di chi ha visto la consigliata ricordata `voce` ([] senza account, o se il campo è rovinato)."""
    return _ids(voce, "utenti") or []


def _quando(voce) -> str:
    """Quando è stata ricordata `voce` (testo ISO: l'ordine dei testi è quello del tempo); "" se manca o è rovinata."""
    return str(voce.get("quando", "")) if isinstance(voce, dict) else ""


def _giornata(voce) -> tuple[str, str]:
    """Stagione e giornata della consigliata ricordata `voce` (come testi: una voce rovinata non ferma niente)."""
    return (str(voce.get("stagione")), str(voce.get("giornata"))) if isinstance(voce, dict) else ("", "")


def _proprie(voce) -> list[int]:
    """Gli id di chi ha visto `voce` come consigliata della propria squadra (sottoinsieme di `utenti`)."""
    utenti = _utenti(voce)
    return [u for u in _ids(voce, "proprie") or [] if u in utenti]


def _riservate(tutte: dict) -> set[str]:
    """La parte riservata di ciascun utente: al massimo `RISERVATE_UTENTE` voci, in quest'ordine: la più recente della propria
    squadra per ogni giornata, poi la più recente di ogni giornata, poi le altre dalla più recente."""
    di_ciascuno: dict[int, list[str]] = {}
    for k in sorted(tutte, key=lambda k: _quando(tutte[k]), reverse=True):
        for u in _utenti(tutte[k]):
            di_ciascuno.setdefault(u, []).append(k)
    riservate: set[str] = set()
    for u, voci in di_ciascuno.items():                  # di ciascuno, dalla più recente
        proprie_viste: set[tuple[str, str]] = set()
        viste: set[tuple[str, str]] = set()
        livello = {}
        for k in voci:
            g = _giornata(tutte[k])
            if u in _proprie(tutte[k]) and g not in proprie_viste:
                livello[k] = 0
                proprie_viste.add(g)
            else:
                livello[k] = 1 if g not in viste else 2
            viste.add(g)
        riservate.update(sorted(voci, key=lambda k: livello[k])[:RISERVATE_UTENTE])     # stabile: poi dalla più recente
    return riservate


def _ricorda(impronta: str, f: dict, stagione: str, giornata: int, prima: dict | None, propria: bool = False) -> None:
    """Ricorda la consigliata mostrata (`da_ricordare`), solo se è cambiata o se chi chiede (`calcolo.utente_richiesta`, con gli
    account) non l'aveva ancora vista (con `propria`: non l'aveva ancora vista come la sua squadra, campo `proprie`). Rilegge il
    file subito prima di scrivere, con il blocco valido anche fra processi. Un errore non ferma la risposta: si riprova alla prossima."""
    voce = da_ricordare(f, prima)
    if voce is None:
        return
    utente = calcolo.utente_richiesta.get()
    if (prima is not None and set(_ids(prima, "titolari") or []) == set(voce["titolari"]) and _ids(prima, "panchina") == voce["panchina"]
            and prima.get("modulo") == voce["modulo"] and _ids(prima, "non_giocano") == voce["non_giocano"]
            and (utente is None or (utente in _utenti(prima) and (not propria or utente in _proprie(prima))))):
        return
    nuova = {"stagione": str(stagione), "giornata": int(giornata), **voce, "quando": _adesso().isoformat(timespec="seconds")}
    file = FILE_CONSIGLIATE
    try:
        with _blocco_consigliate, BloccoFile(file.with_name(file.name + ".lock")):
            try:
                tutte = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                tutte = {}
            tutte = tutte if isinstance(tutte, dict) else {}
            utenti, proprie = _utenti(tutte.get(impronta)), _proprie(tutte.get(impronta))
            if utente is not None and utente not in utenti:
                utenti.append(utente)
            if propria and utente is not None and utente not in proprie:
                proprie.append(utente)
            tutte[impronta] = nuova | ({"utenti": utenti} if utenti else {}) | ({"proprie": proprie} if proprie else {})
            per_eta = sorted((k for k in tutte if k != impronta), key=lambda k: _quando(tutte[k]))
            if utente is not None:                       # la parte di chi chiede: oltre, perde le sue più vecchie
                mie = [k for k in per_eta if utente in _utenti(tutte[k])]
                for vecchia in mie[:max(0, len(mie) + 1 - limiti.valore("MAX_CONSIGLIATE_UTENTE"))]:
                    altri = [u for u in _utenti(tutte[vecchia]) if u != utente]
                    if altri:
                        tutte[vecchia]["utenti"] = altri         # serve ancora ad altri utenti: resta per loro
                        altre_proprie = [u for u in _proprie(tutte[vecchia]) if u != utente]
                        if altre_proprie:
                            tutte[vecchia]["proprie"] = altre_proprie
                        else:
                            tutte[vecchia].pop("proprie", None)
                    else:
                        tutte.pop(vecchia)
                per_eta = [k for k in per_eta if k in tutte]
            if len(tutte) > MAX_CONSIGLIATE:             # prima le più vecchie fuori dalla parte riservata di ciascuno
                riservate = _riservate(tutte)
                per_eta.sort(key=lambda k: k in riservate)       # ordinamento stabile: in ogni gruppo resta l'ordine di età
            for vecchia in per_eta[:max(0, len(tutte) - MAX_CONSIGLIATE)]:
                tutte.pop(vecchia, None)
            scrivi_sicuro(file, json.dumps(tutte, ensure_ascii=False))
    except OSError as e:
        LOG.warning("consigliata non ricordata (%s)", type(e).__name__)


def _chiusa(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, adesso: datetime | None = None) -> bool:
    """La formazione della giornata è chiusa (scadenza della lega passata): la regola di Oggi e della Formazione."""
    from . import fasi
    try:
        return fasi.iniziata(db, regole, stagione, giornata, adesso or _adesso())
    except sqlite3.Error:                 # archivio senza calendario: come una giornata ancora aperta
        return False


def stabile(migliore: dict, prima: dict | None, prev: pd.DataFrame, s: Squadra, regole: Regole, simulazioni: int,
            chiusa: bool = False, iniziate: Collection[str] = ()) -> dict:
    """La consigliata da mostrare: quella di prima (`prima` = {"titolari": [id], "panchina": [id]}) se c'è e regge, altrimenti la
    migliore di adesso (`migliore`, la risposta di `_calcola_formazione`, restituita così com'è).
    Prima della scadenza la migliore prende il posto di quella di prima se vale almeno SOGLIA_CAMBIO_PUNTI punti attesi in più (sulle
    stesse simulazioni, con i dati nuovi), o se un titolare di prima non gioca più (uscito dalla rosa, diventato fuori o improbabile:
    non chi lo era già quando è stata mostrata, `prima["non_giocano"]`) e la migliore lo lascia fuori; tenuta quella di prima, la
    sua panchina la sceglie il sistema come sempre. Dopo la scadenza (`chiusa`)
    resta quella di prima, panchina compresa. La scelta salvata dall'utente non passa di qui.
    `iniziate` (squadre di Serie A con un anticipo già cominciato, #368): prima della scadenza i loro giocatori restano dove erano
    nella consigliata di prima (titolari, stesso posto in panchina, fuori), anche quando la migliore li sposterebbe: al posto della
    migliore si confronta la migliore che li lascia lì, con le stesse regole."""
    titolari = _ids(prima, "titolari")
    if titolari is None or len({int(g["id"]) for g in migliore.get("titolari") or []}) != 11:
        return migliore
    rosa = _rosa(s, prev)
    fermi = None if chiusa else Fermi.di(prima, rosa, prev, iniziate)
    if _stessa(prima, migliore, chiusa) and (fermi is None or fermi.rispettati(migliore)):
        return migliore
    panchina_prima = _ids(prima, "panchina") or []
    per_id = {g.id: g for g in rosa}
    if scelte.motivo_non_valida(titolari, {g.id: g.ruolo for g in rosa}, regole):
        return migliore                  # un titolare uscito dalla rosa o senza previsione, un modulo non più ammesso, un file rovinato
    if fermi is not None and not fermi.rispettati(migliore):
        migliore = _calcola_formazione(s, prev, migliore["giornata"], migliore["con_probabili"], regole, simulazioni, fermi)
        if _stessa(prima, migliore, chiusa):
            return migliore
    nuovi = {int(g["id"]) for g in migliore["titolari"]}
    gia = set(_ids(prima, "non_giocano") or [])           # chi non giocava già quando la consigliata è stata mostrata
    if not chiusa and any(titolarita(prev.loc[i]) in NON_GIOCA and i not in nuovi and i not in gia for i in titolari):
        return migliore
    tit = sorted((per_id[i] for i in titolari), key=lambda g: (fz.ORDINE_RUOLO[g.ruolo], -g.valore))
    if chiusa and panchina_prima:
        panchina = [per_id[i] for i in panchina_prima if i in per_id and i not in titolari]
    elif fermi is not None:
        panchina = fermi.panchina_di(rosa, tit, regole)
    else:
        panchina = fz._panchina(rosa, tit, regole)
    val = fz.Valutatore(rosa, regole, simulazioni)          # le stesse simulazioni della migliore (stessa rosa, regole e seme)
    atteso, dev = val.statistiche(tit, panchina)[:2]
    atteso_migliore = val.atteso([per_id[int(g["id"])] for g in migliore["titolari"]],
                                 [per_id[int(g["id"])] for g in migliore.get("panchina") or []])
    if not chiusa and atteso_migliore - atteso >= SOGLIA_CAMBIO_PUNTI:
        return migliore
    return perche_scelta.aggiungi(_con_consigliata(migliore, tit, panchina, atteso, dev, atteso_migliore, rosa), rosa, regole, val,
                                  tenuta=not chiusa)


def _con_consigliata(migliore: dict, tit: list, panchina: list, atteso: float, dev: float, atteso_migliore: float,
                     rosa: list) -> dict:
    """Una copia della risposta della migliore con la consigliata di prima al suo posto: in cima, nella voce del suo modulo
    (`moduli`) e nello stile consigliato (`livelli`), da cui web e iPhone prendono i titolari; `alternative` e `fuori` rifatti.
    La risposta della migliore (in cache) non cambia."""
    conta = {r: sum(1 for g in tit if g.ruolo == r) for r in "DCA"}
    modulo = f"{conta['D']}-{conta['C']}-{conta['A']}"
    fascia = incertezza.campi(atteso, dev)
    voce = {"modulo": modulo, "punteggio_atteso": round(atteso, 1), **fascia, "titolari": [g.id for g in tit],
            "panchina": [g.id for g in panchina], "incerti": incerti(tit, panchina)}
    moduli = [voce if m["modulo"] == modulo else m for m in migliore.get("moduli") or []]
    if not any(m["modulo"] == modulo for m in moduli):
        moduli.append(voce)
    alternative = [{"modulo": migliore["modulo"], "punteggio_atteso": round(atteso_migliore, 2)}] if migliore["modulo"] != modulo else []
    alternative += [a for a in migliore.get("alternative") or [] if a["modulo"] != modulo]
    stile = migliore.get("stile_consigliato", 0)
    livelli = [x | {"modulo": modulo, "punteggio_atteso": voce["punteggio_atteso"], **fascia, "moduli": moduli}
               if x.get("rischio") == stile else x for x in migliore.get("livelli") or []]
    schede = migliore["schede"]
    scelti = {g.id for g in tit} | {g.id for g in panchina}
    return migliore | {
        "modulo": modulo, "punteggio_atteso": voce["punteggio_atteso"], **fascia, "alternative": alternative,
        "titolari": [schede[str(g.id)] for g in tit], "panchina": [schede[str(g.id)] for g in panchina],
        "fuori": sorted((schede[str(g.id)] for g in rosa if g.id not in scelti), key=lambda x: -x["punti_attesi"]),
        "moduli": moduli, "livelli": livelli}


# ---------------------------------------------------------------- anticipi già cominciati (#368)
# Un anticipo (turno.py: da 36 ore a 7 giorni prima del gruppo principale) non fissa la scadenza: la formazione resta aperta, ma
# nella lega chi gioca una partita già cominciata non si sposta più. Nella consigliata quei giocatori restano dove erano in quella
# già mostrata (titolari, stesso posto in panchina, fuori); gli altri si spostano come sempre.
def _anticipi_iniziati(db: sqlite3.Connection, stagione: str, giornata: int, adesso: datetime | None = None) -> tuple[str, ...]:
    """Le squadre di Serie A con un anticipo della giornata già cominciato o finito (calendario e orario), in ordine."""
    from . import fasi
    try:
        return tuple(sorted(fasi.squadre_in_anticipo_iniziato(db, stagione, giornata, adesso or _adesso())))
    except sqlite3.Error:                 # archivio senza calendario: nessun anticipo
        return ()


@dataclass
class Fermi:
    """I giocatori della rosa che non si possono più spostare e il loro posto nella consigliata di prima."""
    titolari: frozenset[int]
    panchina: dict[int, int]              # id -> posto in panchina (da 0)
    fuori: frozenset[int]

    @classmethod
    def di(cls, prima: dict, rosa: list[fz.Giocatore], prev: pd.DataFrame, iniziate: Collection[str]) -> Fermi | None:
        """Chi della rosa gioca per una delle squadre `iniziate` e dove stava in `prima`. None se nessuno."""
        if not iniziate or "squadra" not in prev.columns:
            return None
        ids = {g.id for g in rosa if prev.at[g.id, "squadra"] in iniziate}
        if not ids:
            return None
        titolari = set(_ids(prima, "titolari") or [])
        panchina = _ids(prima, "panchina") or []
        return cls(frozenset(ids & titolari), {i: k for k, i in enumerate(panchina) if i in ids and i not in titolari},
                   frozenset(ids - titolari - set(panchina)))

    def _a_posto(self, titolari, panchina) -> bool:
        t, p = {int(i) for i in titolari}, [int(i) for i in panchina]
        if not self.titolari <= t or t & (self.panchina.keys() | self.fuori) or self.fuori & set(p):
            return False
        return all(k < len(p) and p[k] == i for i, k in self.panchina.items())

    def rispettati(self, f: dict) -> bool:
        """In ogni formazione della risposta `f` (in cima, in ogni modulo e in ogni stile) i fermi stanno al loro posto."""
        coppie = [([g["id"] for g in f.get("titolari") or []], [g["id"] for g in f.get("panchina") or []])]
        coppie += [(m["titolari"], m["panchina"]) for x in [f, *(f.get("livelli") or [])] for m in x.get("moduli") or []]
        return all(self._a_posto(t, p) for t, p in coppie)

    def per_la_ricerca(self, rosa: list[fz.Giocatore], regole: Regole) -> tuple[list[fz.Giocatore], dict]:
        """(chi può stare fra i titolari, argomenti per formazione.migliore): la ricerca di sempre con i fermi al loro posto."""
        candidati = [g for g in rosa if g.id not in self.panchina and g.id not in self.fuori]
        return candidati, {"fissi": self.titolari, "scegli_panchina": lambda tit: self.panchina_di(rosa, tit, regole)}

    def panchina_di(self, rosa: list[fz.Giocatore], titolari: list[fz.Giocatore], regole: Regole) -> list[fz.Giocatore]:
        """La panchina di sempre (formazione._panchina) fra chi si può ancora spostare, nei posti che restano (per ruolo se la lega
        li fissa); chi è fermo in panchina torna al suo posto."""
        ids = {g.id for g in titolari}
        fermi = sorted(((self.panchina[g.id], g) for g in rosa if g.id in self.panchina and g.id not in ids), key=lambda x: x[0])
        liberi = [g for g in rosa if g.id not in ids and g.id not in self.panchina and g.id not in self.fuori]
        pr = regole.panchina
        if pr.posti:
            posti = {r: max(0, n - sum(1 for _, g in fermi if g.ruolo == r)) for r, n in pr.posti.items()}
            meno = replace(pr, posti=posti, numero=sum(posti.values()))
        else:
            meno = replace(pr, numero=max(0, pr.numero - len(fermi)))
        scelti = fz._panchina(liberi, titolari, replace(regole, panchina=meno))
        for k, g in fermi:
            scelti.insert(min(k, len(scelti)), g)
        return scelti


class FormazioneNonValida(ValueError):
    """La formazione scelta (o salvata) non è valida: titolari non della rosa, ripetuti o modulo non ammesso. Risposta 400 con il
    testo per l'utente e `codice` = «formazione_non_valida», così i client sanno che la scelta salvata va rifatta (non cancellata da sola)."""
    codice = "formazione_non_valida"


def valuta(db: sqlite3.Connection, regole: Regole, rose: Rose, titolari: list[int], nome_squadra: str | None = None,
           giornata: int | None = None, simulazioni: int = 600, adesso: datetime | None = None) -> dict:
    """Quanto vale una formazione scelta a mano (11 titolari della rosa): punti attesi, oscillazione e differenza dalla consigliata
    con lo stesso modulo. La panchina è scelta come sempre dal sistema. Usa le stesse simulazioni della formazione consigliata.
    `adesso`: l'ora con cui si chiede la consigliata (vedi `formazione`)."""
    s = rose.squadra(nome_squadra or rose.mia_squadra or "")
    if not s:
        raise ValueError("Squadra non trovata: indica la tua squadra in Squadra > Squadre e rose")
    if giornata is None and adesso is not None:     # con l'ora data la giornata si cerca con quella (senza: `previsioni`, ora vera)
        giornata = giornata_da_giocare(db, stagione_corrente(), regole, adesso)
        if giornata is None:
            raise ValueError(SENZA_CALENDARIO)
    prev, giornata, _ = previsioni(db, regole, giornata)
    ids = [g.id for g in s.giocatori if g.id is not None and g.id in prev.index]
    rosa = {int(i): fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                                 float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids}
    motivo = scelte.motivo_non_valida(titolari, {i: g.ruolo for i, g in rosa.items()}, regole)     # la regola unica della scelta
    if motivo:
        raise FormazioneNonValida(motivo)
    scelti = list(dict.fromkeys(int(i) for i in titolari))
    tit = [rosa[i] for i in scelti]
    conta = {r: sum(1 for g in tit if g.ruolo == r) for r in "PDCA"}
    modulo = f"{conta['D']}-{conta['C']}-{conta['A']}"
    lista = list(rosa.values())
    val = fz.Valutatore(lista, regole, simulazioni)
    panchina = fz._panchina(lista, tit, regole)
    media, dev = val.statistiche(tit, panchina)[:2]
    consigliata = formazione(db, regole, rose, nome_squadra, giornata, simulazioni, adesso)      # già in cache: non si ricalcola tutto a ogni tocco
    stesso = next((x["punteggio_atteso"] for x in consigliata["moduli"] if x["modulo"] == modulo), None)
    fascia = incertezza.campi(media, dev)
    # brutta/eccezionale = gli estremi della fascia calibrata (10% e 90%), non quelli della simulazione (troppo stretti)
    return {"modulo": modulo, "giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole),
            "punteggio_atteso": round(media, 1), **fascia,
            "brutta_giornata": fascia["intervallo"]["basso"], "giornata_eccezionale": fascia["intervallo"]["alto"],
            "panchina": [g.id for g in panchina],
            # la differenza dei due numeri scritti (questo e quello della consigliata), così «60,0 … −4,1 (64,1)» torna (#392)
            "consigliata_stesso_modulo": stesso, "differenza": float(frasi.differenza(media, stesso)) if stesso is not None else None,
            "consigliata": consigliata["punteggio_atteso"]}


def testo_formazione(f: dict, modulo: str, titolari: list[int], panchina: list[int]) -> str:
    """La formazione come testo semplice: modulo, nomi per ruolo e panchina in ordine (per leggerla, mandarla o per i Comandi di Apple)."""
    sch = f["schede"]
    righe = [f"{frasi.nome_giornata(f['giornata'], f.get('giornata_lega'))} · {modulo}"]
    for r in "PDCA":
        righe.append(f"{r}: " + ", ".join(sch[str(i)]["nome"] for i in titolari if sch[str(i)]["ruolo"] == r))
    if panchina:
        righe.append("Panchina: " + ", ".join(f"{k + 1}) {sch[str(i)]['nome']}" for k, i in enumerate(panchina)))
    return "\n".join(righe)


def valori_scambi(db: sqlite3.Connection, regole: Regole):
    """Valori dei giocatori sulle prossime giornate (per gli scambi), in cache come le previsioni."""
    from . import scambi
    return calcolo.ottieni(("scambi", _versione(db), repr(regole)), lambda d: scambi.valori(d, regole), db)


def _impronta_rose(rose: Rose) -> tuple:
    """Tutto ciò delle rose da cui dipendono scambi e mercato: se cambia, il risultato ricordato non vale più. Anche il prezzo pagato:
    il mercato ci calcola il rimborso allo svincolo e se un cambio è fattibile (reimportare la rosa con i prezzi non cambia i giocatori)."""
    return tuple((q.nome, tuple((g.id, g.costo) for g in q.giocatori), q.crediti_residui) for q in rose.squadre)


def proposte_scambi(db: sqlite3.Connection, regole: Regole, rose: Rose, con: str | None = None, due: bool = False,
                    fino_a: int = 0):
    """(valori, proposte di scambio come dizionari). Si ricordano (stessi dati, regole e rose: stesso risultato; ci vogliono
    qualche secondo sul server). Anche i 2 contro 2 e gli N contro M: il loro budget è un numero fisso di calcoli, quindi
    il risultato non cambia da una volta all'altra. Con gli account il calcolo passa dalla coda (risposta 202)."""
    from . import scambi
    v = valori_scambi(db, regole)

    def cerca(_):
        return [s.come_dict(v) for s in scambi.proponi(v, regole, rose, rose.mia_squadra, con, anche_due=due, fino_a=fino_a)]
    chiave = ("proposte", _versione(db), repr(regole), rose.mia_squadra, con, due, fino_a, _impronta_rose(rose))
    return v, calcolo.ottieni(chiave, cerca, db, peso=calcolo.PESO_LEGGERO)


def mercato(db: sqlite3.Connection, regole: Regole, rose: Rose, nome: str | None = None) -> dict:
    """Svincolati consigliati (gestione.mercato) in cache: stessi dati, regole e rose, stesso risultato. Il widget li legge da qui."""
    from . import gestione
    chiave = ("mercato", _versione(db), repr(regole), nome or rose.mia_squadra, _impronta_rose(rose))
    return calcolo.ottieni(chiave, lambda d: gestione.mercato(d, regole, rose, nome), db, peso=calcolo.PESO_LEGGERO)


def analisi_scambio(db: sqlite3.Connection, regole: Regole, rose: Rose, con: str, do: list[int], ricevo: list[int],
                    conguaglio: int = 0, lingua: str = "it") -> dict:
    """Analisi completa di uno scambio N contro M con conguaglio (vedi scambi_multi). Il valore dei crediti in punti si stima
    dal mercato svincolati delle due squadre (in cache come le proposte) e solo se c'è un conguaglio."""
    from . import gestione, scambi_multi
    v = valori_scambi(db, regole)
    mia = rose.mia_squadra
    tassi = (None, None)
    if conguaglio and rose.squadra(con) and mia and rose.squadra(mia):
        impronta = _impronta_rose(rose)

        def tasso(nome):
            chiave = ("tasso-crediti", _versione(db), repr(regole), nome, impronta)
            return calcolo.ottieni(chiave, lambda d: scambi_multi.tasso_da_mercato(gestione.mercato(d, regole, rose, nome, con_buon_senso=False)), db,
                                   peso=calcolo.PESO_LEGGERO)
        # i due calcoli partono insieme: con la coda («sto calcolando») l'app riprova una volta sola invece di due
        tassi, attesa = [], None
        for nome in (rose.squadra(mia).nome, rose.squadra(con).nome):
            try:
                tassi.append(tasso(nome))
            except calcolo.InCalcolo as e:
                tassi.append(None)
                attesa = e
        if attesa is not None:
            raise attesa
    return scambi_multi.analizza_completo(v, regole, rose, mia, con, do, ricevo, conguaglio, tassi[0], tassi[1], lingua=lingua)


def _componenti(x: pd.Series, regole: Regole) -> dict[str, float]:
    """Da cosa è fatto il fantavoto atteso di un giocatore se gioca (somma = mu)."""
    b = regole.bonus
    r = x["ruolo"]
    rigori = float(x["e_rigori"]) * (modello.Parametri().conversione_rigori * b.rigore_segnato
                                      + (1 - modello.Parametri().conversione_rigori) * b.rigore_sbagliato)
    porta = 0.0
    if r == "P":
        porta = b.gol_subito_portiere * float(x["gol_subiti"]) + b.portiere_imbattuto * float(x["p_imbattuto"])
    voto = float(x["mu_voto"])
    gol = b.gol[r] * float(x["e_gol"])
    assist = b.assist * float(x["e_assist"])
    altro = float(x["mu"]) - voto - gol - assist - rigori - porta     # cartellini, migliore in campo, autogol, rigori parati
    return {"voto": voto, "gol": gol, "assist": assist, "rigori": rigori, "porta": porta, "altro": altro}


ETICHETTE_FATTORI = {"giocare": "Probabilità di giocare", "voto": "Voto in pagella atteso", "gol": "Gol attesi", "assist": "Assist attesi",
                     "rigori": "Rigori", "porta": "Porta (gol subiti, imbattibilità)", "altro": "Cartellini e altro"}


def spiega(xa: pd.Series, xb: pd.Series, regole: Regole) -> dict:
    """Perché il sistema preferisce uno dei due. I punti attesi sono p x mu; la differenza si scompone esattamente così:
    (pA-pB) x media(mu) per la probabilità di giocare, più media(p) x (muA-muB) divisa nelle sue parti (voto, gol, assist...)."""
    pa, pb = float(xa["p_voto"]), float(xb["p_voto"])
    ma, mb = float(xa["mu"]), float(xb["mu"])
    ca, cb = _componenti(xa, regole), _componenti(xb, regole)
    p_medio = (pa + pb) / 2
    fattori = [{"chiave": "giocare", "etichetta": ETICHETTE_FATTORI["giocare"], "a": pa, "b": pb,
                "effetto": (pa - pb) * (ma + mb) / 2, "percentuale": True}]
    for k in ("voto", "gol", "assist", "rigori", "porta", "altro"):
        if k == "porta" and xa["ruolo"] != "P" and xb["ruolo"] != "P":
            continue
        fattori.append({"chiave": k, "etichetta": ETICHETTE_FATTORI[k], "a": ca[k], "b": cb[k],
                        "effetto": p_medio * (ca[k] - cb[k]), "percentuale": False})
    for f in fattori:
        f["a"], f["b"], f["effetto"] = round(f["a"], 3), round(f["b"], 3), round(f["effetto"], 3)
    totale = round(pa * ma - pb * mb, 3)
    return {"fattori": fattori, "differenza": totale}


def _frase_perche(nome_a: str, nome_b: str, spiegazione: dict, margine: float) -> str:
    totale = spiegazione["differenza"]
    if abs(totale) < 0.15:
        return F("confronto.pari", a=nome_a, b=nome_b)
    primo, secondo = (nome_a, nome_b) if totale > 0 else (nome_b, nome_a)
    segno = 1 if totale > 0 else -1
    motivi = sorted((f for f in spiegazione["fattori"] if f["effetto"] * segno > 0.05), key=lambda f: -f["effetto"] * segno)[:3]
    if not motivi:
        return F("confronto.avanti_sparsi", primo=primo, punti=abs(totale))
    parti = []
    for f in motivi:
        peso = abs(f["effetto"])
        if f["chiave"] == "giocare":
            pa, pb = (f["a"], f["b"]) if segno > 0 else (f["b"], f["a"])
            parti.append(F("confronto.gioca_di_piu", pa=etichette.percento(pa), pb=etichette.percento(pb), peso=peso))
        else:
            parti.append(F("confronto.alto_" + f["chiave"], peso=peso))
    return F("confronto.avanti", primo=primo, secondo=secondo, punti=abs(totale), motivi=frasi.elenco(parti, sep="; "))


def _in_formazione(db: sqlite3.Connection, regole: Regole, rose: Rose, nome_squadra: str | None, giornata: int | None,
                   modulo: str | None, id_a: int, id_b: int, prev: pd.DataFrame, livello: int = 0) -> dict | None:
    """Come sta davvero la formazione scelta dal sistema per questi due: chi è titolare, chi in panchina, e quanto vale la
    formazione se si scambiano di posto. È la vera ragione della scelta: se il titolare non prende voto entra il panchinaro,
    quindi conta anche quanto vale ciascuno quando gioca, non solo la probabilità di giocare."""
    try:
        f = formazione(db, regole, rose, nome_squadra, giornata)
    except ValueError:
        return None
    stile = next((x for x in f.get("livelli", []) if x["rischio"] == livello), None)       # la formazione dello stile scelto (sicura, rischiosa...)
    moduli, migliore = (stile["moduli"], stile["modulo"]) if stile else (f["moduli"], f["modulo"])
    m = next((x for x in moduli if x["modulo"] == modulo), None) or next(x for x in moduli if x["modulo"] == migliore)
    if str(id_a) not in f["schede"] or str(id_b) not in f["schede"]:
        return None                                       # uno dei due non è nella rosa di questa formazione
    rosa = {int(k): fz.Giocatore(int(k), prev.at[int(k), "nome"], prev.at[int(k), "ruolo"], float(prev.at[int(k), "p_voto"]),
                                 float(prev.at[int(k), "mu"]), float(prev.at[int(k), "mu_voto"])) for k in f["schede"]}

    def posto(i: int) -> str:
        if i in m["titolari"]:
            return "titolare"
        return f"panchina {m['panchina'].index(i) + 1}" if i in m["panchina"] else "fuori"

    def posto_frase(p: str):
        return F("posto.panchina", n=int(p.split()[1])) if p.startswith("panchina") else F("posto." + p)

    pa, pb = posto(id_a), posto(id_b)
    base = {"modulo": m["modulo"], "posto_a": pa, "posto_b": pb, "attuale": None, "invertita": None, "differenza": None, "testo": ""}

    def scrivi(frase) -> dict:                               # il testo italiano e, accanto, come tradurlo
        base["testo"], base["frase"] = frase, frasi.di(frase)
        return base
    ga, gb = rosa[id_a], rosa[id_b]
    if pa == "titolare" and pb == "titolare":
        return scrivi(F("confronto.tutti_titolari", a=ga.nome, b=gb.nome, modulo=m["modulo"]))
    if pa != "titolare" and pb != "titolare":
        return scrivi(F("confronto.non_titolari_ordine" if pa != "fuori" and pb != "fuori" else "confronto.non_titolari_fuori",
                        a=ga.nome, b=gb.nome, modulo=m["modulo"], pa=posto_frase(pa), pb=posto_frase(pb)))
    titolare, altro = (ga, gb) if pa == "titolare" else (gb, ga)
    posto_altro = pb if pa == "titolare" else pa
    if titolare.ruolo != altro.ruolo:
        return scrivi(F("confronto.ruoli_diversi", titolare=titolare.nome, altro=altro.nome, posto=posto_frase(posto_altro)))
    titolari = [rosa[i] for i in m["titolari"]]
    panchina = [rosa[i] for i in m["panchina"]]
    titolari2 = [altro if g.id == titolare.id else g for g in titolari]
    tutti = list(rosa.values())
    val = fz.Valutatore(tutti, regole, 600)
    attuale = val.atteso(titolari, panchina)
    invertita = val.atteso(titolari2, fz._panchina(tutti, titolari2, regole))
    diff = attuale - invertita
    base.update(attuale=round(attuale, 2), invertita=round(invertita, 2), differenza=round(diff, 2))
    if posto_altro == "fuori":
        entrata = F("confronto.entra_fuori", altro=altro.nome)
    elif regole.panchina.max_sostituzioni <= 0:
        entrata = F("confronto.senza_sostituzioni", altro=altro.nome, posto=posto_frase(posto_altro), titolare=titolare.nome)
    else:
        entrata = F("confronto.entra_se", titolare=titolare.nome, p=100 - etichette.percento(titolare.p), altro=altro.nome, posto=posto_frase(posto_altro))
    scritta = frasi.differenza(invertita, attuale)          # tra parentesi: la differenza dei due numeri scritti, «72,1 (−0,6)» (#392)
    if diff > 0.04:
        esito = F("confronto.esito_meglio", titolare=titolare.nome, attuale=attuale, invertita=invertita, d=scritta)
    elif diff < -0.04 and titolare.p >= fz.COMPAGNO_ALMENO and altro.p < fz.IMPROBABILE_SOTTO:
        # invertirli varrebbe di più, ma l'altro quasi certamente non gioca: è la regola dei titolari che giocano (#329, #341)
        return scrivi(F("confronto.titolare_che_gioca", altro=altro.nome, p=etichette.percento(altro.p), titolare=titolare.nome,
                        pt=etichette.percento(titolare.p), d=-diff, entrata=entrata))
    elif diff < -0.04:
        esito = F("confronto.esito_peggio", invertita=invertita, attuale=attuale, d=scritta, modulo=m["modulo"])
    else:
        esito = F("confronto.esito_pari", attuale=attuale, invertita=invertita)
    return scrivi(F("confronto.principale", titolare=titolare.nome, entrata=entrata, esito=esito, mu_t=titolare.mu, altro=altro.nome, mu_a=altro.mu))


def da_schierare(a: dict, b: dict, titolari: Collection[int] | None = None) -> dict:
    """Chi schierare tra due giocatori (schede con `id` e `punti_attesi`): se la formazione del sistema (`titolari`, i suoi id; None
    = non si sa) ne schiera uno solo, è lui, anche con meno punti attesi da solo (se non gioca entra la riserva, e insieme valgono di
    più); altrimenti chi ha più punti attesi. Regola unica: `consigliato` del confronto e cambi proposti da «Da fare» (da_fare.py)."""
    if titolari is not None:
        dentro = [g for g in (a, b) if g["id"] in titolari]
        if len(dentro) == 1:
            return dentro[0]
    return a if a["punti_attesi"] >= b["punti_attesi"] else b


def confronto(db: sqlite3.Connection, regole: Regole, id_a: int, id_b: int, giornata: int | None = None,
              rose: Rose | None = None, nome_squadra: str | None = None, modulo: str | None = None, livello: int = 0) -> dict:
    """Ballottaggio: chi dei due schierare questa giornata, e perché (le differenze tra le statistiche usate per scegliere).
    Con le rose indica anche come stanno nella formazione del sistema e quanto cambierebbe scambiandoli."""
    prev, giornata, _ = previsioni(db, regole, giornata)
    risultato = []
    for i in (id_a, id_b):
        if i not in prev.index:
            raise ValueError(frasi.elidi_ordinali(f"Giocatore {i} senza previsione per la {frasi.nome_giornata(giornata, serie_a_a_lega(giornata, regole))} (la sua squadra non gioca?)"))
        risultato.append(scheda_previsione(i, prev.loc[i]))
    a, b = risultato
    spiegazione = spiega(prev.loc[id_a], prev.loc[id_b], regole)
    margine = round(abs(a["punti_attesi"] - b["punti_attesi"]), 2)
    in_formazione = _in_formazione(db, regole, rose, nome_squadra, giornata, modulo, id_a, id_b, prev, livello) if rose is not None else None
    titolari = None              # chi dei due è titolare nella formazione del sistema (titolo «Schiera X» dei client)
    if in_formazione:
        titolari = {g["id"] for g, p in ((a, in_formazione["posto_a"]), (b, in_formazione["posto_b"])) if p == "titolare"}
    meglio = da_schierare(a, b, titolari)
    perche_testo = _frase_perche(a["nome"], b["nome"], spiegazione, margine)
    return {"giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole), "giocatori": risultato,
            "consigliato": meglio["id"], "margine": margine,
            "fattori": spiegazione["fattori"], "perche": perche_testo, "perche_frase": frasi.di(perche_testo),
            "formazione": in_formazione}
