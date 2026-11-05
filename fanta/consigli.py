"""Consigli pronti da mostrare (comando e app): formazione con le spiegazioni, confronto tra due giocatori."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from collections.abc import Collection
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from . import calcolo, etichette, frasi, incertezza, perche
from . import formazione as fz
from . import modello, rinvii, stato_dati, turno
from .aggiorna import Stagione
from .frasi import F
from .lega import Rose
from .punteggio import modulo_valido
from .regole import Regole, serie_a_a_lega

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
    (leggibile) più un'impronta di tutte le righe."""
    righe = db.execute("SELECT cosa, quando FROM aggiornamenti ORDER BY cosa").fetchall()
    if not righe:
        return None
    impronta = hashlib.sha1("\n".join(f"{c}={q}" for c, q in righe).encode()).hexdigest()[:12]
    return f"{max(str(q or '') for _, q in righe)}|{impronta}"


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
    p = modello.previsioni(d, stagione, giornata, regole, probabili=None if prob.empty else prob,
                           giocatori=d.calciatori, fattori_probabili=stato_dati.fattori(db, stagione))
    if p.empty:
        raise ValueError(f"Non ci sono ancora previsioni per la giornata {giornata}: riprova più tardi.")
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
    if x["e_rigori"] >= 0.15:
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


# Titolare poco sicuro con una riserva quasi sicura dello stesso ruolo: la scelta è giusta (se lui non gioca entra la riserva, e
# insieme valgono di più che la riserva da sola) ma a prima vista sembra un errore, quindi la si spiega. Soglie su `p_voto` (`Giocatore.p`).
INCERTO_SOTTO = 0.5        # il titolare gioca meno di così...
RISERVA_SOPRA = 0.8        # ...e la riserva che entrerebbe al suo posto più di così


def incerti(titolari: list, panchina: list) -> list[dict]:
    """I titolari incerti e la riserva che entra al loro posto: [{titolare, riserva}] (id). La riserva è la prima dello stesso
    ruolo nell'ordine della panchina (come le sostituzioni, `formazione.chi_va_a_punteggio`), una sola per titolare: con due
    incerti dello stesso ruolo il secondo prende la riserva dopo. Dal titolare più incerto."""
    usate: set[int] = set()
    risultato = []
    for t in sorted((g for g in titolari if g.p < INCERTO_SOTTO), key=lambda g: g.p):
        r = next((b for b in panchina if b.ruolo == t.ruolo and b.id not in usate), None)
        if r is None:
            continue
        usate.add(r.id)
        if r.p > RISERVA_SOPRA:
            risultato.append({"titolare": int(t.id), "riserva": int(r.id)})
    return risultato


def _moduli(tutte: list) -> list[dict]:
    return [{"modulo": x.modulo, "punteggio_atteso": round(x.atteso, 1), **incertezza.campi(x.atteso, x.dev),
             "titolari": [g.id for g in x.titolari], "panchina": [g.id for g in x.panchina],
             "incerti": incerti(x.titolari, x.panchina)} for x in tutte]


def formazione(db: sqlite3.Connection, regole: Regole, rose: Rose, nome_squadra: str | None = None,
               giornata: int | None = None, simulazioni: int = 600) -> dict:
    s = rose.squadra(nome_squadra or rose.mia_squadra or "")
    if not s:
        raise ValueError("Squadra non trovata: indica la tua squadra in Squadra > Squadre e rose")
    giornata = giornata or giornata_da_giocare(db, stagione_corrente(), regole)
    if giornata is None:
        raise ValueError(SENZA_CALENDARIO)
    # stessa squadra, rosa, giornata, regole e dati: stesso risultato (svuotata quando i dati cambiano)
    chiave = ("formazione", _versione(db), s.nome, tuple(g.id for g in s.giocatori), giornata, repr(regole),
              simulazioni)
    return calcolo.ottieni(chiave, lambda d: _formazione_pronta(d, s, giornata, regole, simulazioni), db, peso=calcolo.PESO_LEGGERO)


def _formazione_pronta(db, s, giornata, regole, simulazioni) -> dict:
    prev, giornata, con_probabili = previsioni(db, regole, giornata)
    return _calcola_formazione(s, prev, giornata, con_probabili, regole, simulazioni)


def _calcola_formazione(s, prev, giornata, con_probabili, regole, simulazioni) -> dict:
    ids = [g.id for g in s.giocatori if g.id is not None]
    rosa = [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                         float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids if i in prev.index]
    val = fz.Valutatore(rosa, regole, simulazioni)           # le stesse simulazioni per tutti i livelli: i calcoli si riusano
    try:
        f = fz.migliore(rosa, regole, simulazioni, valutatore=val)
    except ValueError:
        raise ValueError("Non si riesce a formare una squadra: in qualche ruolo nessuno gioca questa giornata") from None
    livelli = []
    for rischio, nome, peso, inclinazione, descrizione in fz.LIVELLI_RISCHIO:
        fl = f if (peso, inclinazione) == (fz.PESO_BASE, (0.0, 0.0)) else fz.migliore(
            rosa, regole, simulazioni, peso=peso, valutatore=val, inclinazione=inclinazione)
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
    return risultato


class FormazioneNonValida(ValueError):
    """La formazione scelta (o salvata) non è valida: titolari non della rosa, ripetuti o modulo non ammesso. Risposta 400 con il
    testo per l'utente e `codice` = «formazione_non_valida», così i client sanno che la scelta salvata va rifatta (non cancellata da sola)."""
    codice = "formazione_non_valida"


def valuta(db: sqlite3.Connection, regole: Regole, rose: Rose, titolari: list[int], nome_squadra: str | None = None,
           giornata: int | None = None, simulazioni: int = 600) -> dict:
    """Quanto vale una formazione scelta a mano (11 titolari della rosa): punti attesi, oscillazione e differenza dalla consigliata
    con lo stesso modulo. La panchina è scelta come sempre dal sistema. Usa le stesse simulazioni della formazione consigliata."""
    s = rose.squadra(nome_squadra or rose.mia_squadra or "")
    if not s:
        raise ValueError("Squadra non trovata: indica la tua squadra in Squadra > Squadre e rose")
    prev, giornata, _ = previsioni(db, regole, giornata)
    ids = [g.id for g in s.giocatori if g.id is not None and g.id in prev.index]
    rosa = {int(i): fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]),
                                 float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"])) for i in ids}
    scelti = list(dict.fromkeys(int(i) for i in titolari))
    if len(scelti) != 11 or any(i not in rosa for i in scelti):
        raise FormazioneNonValida("Servono 11 titolari diversi, tutti della rosa")
    tit = [rosa[i] for i in scelti]
    conta = {r: sum(1 for g in tit if g.ruolo == r) for r in "PDCA"}
    if conta["P"] != 1 or not modulo_valido(conta["D"], conta["C"], conta["A"], regole):
        raise FormazioneNonValida(f"Il modulo {conta['D']}-{conta['C']}-{conta['A']} con {conta['P']} portieri non è ammesso nella tua lega")
    modulo = f"{conta['D']}-{conta['C']}-{conta['A']}"
    lista = list(rosa.values())
    val = fz.Valutatore(lista, regole, simulazioni)
    panchina = fz._panchina(lista, tit, regole)
    media, dev = val.statistiche(tit, panchina)[:2]
    consigliata = formazione(db, regole, rose, nome_squadra, giornata, simulazioni)      # già in cache: non si ricalcola tutto a ogni tocco
    stesso = next((x["punteggio_atteso"] for x in consigliata["moduli"] if x["modulo"] == modulo), None)
    fascia = incertezza.campi(media, dev)
    # brutta/eccezionale = gli estremi della fascia calibrata (10% e 90%), non quelli della simulazione (troppo stretti)
    return {"modulo": modulo, "giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole),
            "punteggio_atteso": round(media, 1), **fascia,
            "brutta_giornata": fascia["intervallo"]["basso"], "giornata_eccezionale": fascia["intervallo"]["alto"],
            "panchina": [g.id for g in panchina],
            "consigliata_stesso_modulo": stesso, "differenza": round(media - stesso, 1) if stesso is not None else None,
            "consigliata": consigliata["punteggio_atteso"]}


def testo_formazione(f: dict, modulo: str, titolari: list[int], panchina: list[int]) -> str:
    """La formazione come testo semplice: modulo, nomi per ruolo e panchina in ordine (per leggerla, mandarla o per i Comandi di Apple)."""
    sch = f["schede"]
    righe = [f"Giornata {f['giornata']} · {modulo}"]
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
            parti.append(F("confronto.gioca_di_piu", pa=round(pa * 100), pb=round(pb * 100), peso=peso))
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
        entrata = F("confronto.entra_se", titolare=titolare.nome, p=round((1 - titolare.p) * 100), altro=altro.nome, posto=posto_frase(posto_altro))
    if diff > 0.04:
        esito = F("confronto.esito_meglio", titolare=titolare.nome, attuale=attuale, invertita=invertita, d=-diff)
    elif diff < -0.04:
        esito = F("confronto.esito_peggio", invertita=invertita, attuale=attuale, d=-diff, modulo=m["modulo"])
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
            raise ValueError(f"Giocatore {i} senza previsione per la giornata {giornata} (la sua squadra non gioca?)")
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
