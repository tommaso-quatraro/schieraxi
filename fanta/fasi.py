"""Le fasi della giornata per Oggi: campi `fase`, `in_corso`, `riepilogo`, `prossima` e `partite[].stato` di GET /api/oggi
(contratto in docs/API.md, «GET /api/oggi: fasi della giornata»).

- `prima`: la formazione si può ancora cambiare: Oggi come sempre (scelta, da controllare, consigli).
- `in_corso`: la scadenza è passata e ci sono partite in corso o da giocare: niente consigli sulla formazione, ma i punti fatti
  finora dalla formazione schierata, quelli attesi che restano, chi deve ancora giocare, i cambi dalla panchina (già scattati o
  probabili) e lo stato di ogni partita.
- `finita`: la giornata di prima è finita da poco e la prossima non si chiude a breve: riepilogo (punti fatti e attesi, confronto
  con la consigliata del Diario) e da quando conviene preparare la prossima.

Solo letture leggere (tabelle `partite` e `voti`, file delle scelte e del diario, cache dei risultati in diretta): mai un calcolo
nuovo. Chi chiama (gestione.oggi) non deve mai fallire per colpa di questo modulo: `aggiungi` intercetta ogni errore.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import diario, scelte, turno as turni
from . import formazione as fz
from .punteggio import COLONNA_VOTO, fantavoto, modificatore_difesa
from .regole import Regole, serie_a_a_lega

PRIMA, IN_CORSO, FINITA = "prima", "in_corso", "finita"
DURATA_PARTITA = timedelta(minutes=110)        # come live.FINE_STIMATA: 2 tempi + intervallo + recupero
RIEPILOGO_PER = timedelta(hours=48)            # il riepilogo resta in Oggi per 2 giorni dalla fine della giornata
ORE_PROSSIMA_VICINA = 24                       # ...ma se la prossima si chiude entro 24 ore si torna a prepararla (fase `prima`)
ORE_PROBABILI = 72                             # le probabili escono di solito negli ultimi 2-3 giorni: da lì conviene preparare
FINESTRA_TURNO = turni.FINESTRA               # oltre è un recupero, non chiude la giornata (regola unica in turno.py)
FUORI = ("infortunato", "squalificato")
# stati di una partita per i client: da_giocare, in_corso, finita, rinviata
_DA_LIVE = {"primo_tempo": IN_CORSO, "intervallo": IN_CORSO, "secondo_tempo": IN_CORSO, "in_corso": IN_CORSO,
            "finita": "finita", "rinviata": "rinviata", "sospesa": "rinviata"}
# stato di un giocatore: fatto (ha il voto), senza_voto (la sua partita ha i voti, lui no), attesa_voti (partita finita, voti non
# ancora usciti), in_corso, da_giocare, rinviata (partita rinviata o squadra che non gioca)
DECISI = ("fatto", "senza_voto")


def _data(testo) -> datetime | None:
    try:
        return datetime.fromisoformat(str(testo)[:16].replace("T", " ")) if testo else None
    except ValueError:
        return None


def inizio_turno(partite: list[dict]) -> datetime | None:
    """Quando comincia il turno (regola unica in turno.py, la stessa della scadenza): un recupero con la data vecchia non sposta
    l'inizio. None se il calendario non ha date."""
    return turni.inizio(_data(p.get("data")) for p in partite)


def stato_partita(p: dict, adesso: datetime, live: dict | None = None, turno: datetime | None = None) -> str:
    """Lo stato di una partita del turno: prima quello del calendario (giocata), poi quello in diretta, infine l'orario.
    Con `turno` (l'inizio del turno) una partita non giocata senza data, o fuori dalla finestra del turno, è «rinviata»:
    il calendario l'ha già spostata a un recupero."""
    if p.get("giocata"):
        return "finita"
    v = _DA_LIVE.get(((live or {}).get((p.get("casa"), p.get("trasferta"))) or {}).get("stato"))
    if v:
        return v
    inizio = _data(p.get("data"))
    if turno is not None and (inizio is None or not turni.nel_turno(inizio, turno)):
        return "rinviata"
    if inizio is None or adesso < inizio:
        return "da_giocare"
    return IN_CORSO if adesso < inizio + DURATA_PARTITA else "finita"


def calcola_fase(iniziata: bool, ore_mancanti: float | None, fine_precedente: datetime | None, adesso: datetime) -> str:
    """`in_corso` dalla scadenza finché la giornata non è chiusa; `finita` per 2 giorni dopo la fine della giornata di prima, se la
    prossima non si chiude entro 24 ore; altrimenti `prima`."""
    if iniziata:
        return IN_CORSO
    if (fine_precedente is not None and fine_precedente <= adesso <= fine_precedente + RIEPILOGO_PER
            and (ore_mancanti is None or ore_mancanti > ORE_PROSSIMA_VICINA)):
        return FINITA
    return PRIMA


def fine_giornata(db: sqlite3.Connection, stagione: str, giornata: int) -> datetime | None:
    """Fine stimata di una giornata GIÀ CHIUSA (tutte le partite giocate): inizio dell'ultima partita del turno più la durata.
    Un recupero giocato settimane dopo non conta. None se la giornata non è chiusa o non ha date."""
    righe = db.execute("SELECT data, giocata FROM partite WHERE stagione = ? AND giornata = ?", (stagione, giornata)).fetchall()
    if not righe or not all(r[1] for r in righe):
        return None
    date = [d for d in (_data(r[0]) for r in righe) if d]
    if not date:
        return None
    primo = turni.inizio(date)
    return max(d for d in date if turni.nel_turno(d, primo)) + DURATA_PARTITA


# ---------------------------------------------------------------- la formazione schierata
def schierata(stagione: str, giornata: int, file_scelte, file_diario, consigliata: list[int] | None = None,
              panchina_consigliata: list[int] | None = None) -> tuple[list[int], list[int] | None, str] | None:
    """(titolari, panchina o None, di chi è: `tua` o `consigliata`). In ordine: la scelta dell'utente, la consigliata congelata alla
    scadenza (istantanea del Diario), la copia automatica, la consigliata di adesso. Senza file non si legge niente (mai i file comuni)."""
    sc = scelte.leggi(stagione, giornata, file_scelte) if file_scelte else None
    if sc and len(sc.get("titolari") or []) == 11:
        return [int(i) for i in sc["titolari"]], [int(i) for i in sc.get("panchina") or []] or None, "tua"
    ist = (diario.carica(file_diario).get("istantanee") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    if isinstance(ist, dict) and len(ist.get("titolari") or []) == 11:
        return ([int(g["id"]) for g in ist["titolari"]], [int(g["id"]) for g in ist.get("panchina") or []] or None, "consigliata")
    auto = scelte.leggi(stagione, giornata, file_scelte, anche_automatica=True) if file_scelte else None
    if auto and len(auto.get("titolari") or []) == 11:
        return [int(i) for i in auto["titolari"]], None, "consigliata"
    if consigliata and len(consigliata) == 11:
        return [int(i) for i in consigliata], [int(i) for i in panchina_consigliata or []] or None, "consigliata"
    return None


def voti_giornata(db: sqlite3.Connection, stagione: str, giornata: int, ids: list[int], regole: Regole
                  ) -> tuple[dict[int, dict], set[str]]:
    """({id: riga dei voti} dei giocatori chiesti, squadre che hanno già i voti in questa giornata). Query parametrizzate; la
    colonna del voto viene da una tabella fissa (COLONNA_VOTO), mai da un input."""
    col = COLONNA_VOTO[regole.fonte_voto]
    squadre = {r[0] for r in db.execute(f"SELECT DISTINCT squadra FROM voti WHERE stagione = ? AND giornata = ? AND {col} IS NOT NULL",
                                        (stagione, giornata)) if r[0]}
    righe: dict[int, dict] = {}
    if ids:
        segni = ",".join("?" * len(ids))
        for r in db.execute(f"SELECT * FROM voti WHERE stagione = ? AND giornata = ? AND calciatore_id IN ({segni})",
                            (stagione, giornata, *ids)):
            # bonus mancanti = 0 (una riga a metà non deve far saltare il conto); il voto mancante resta None (= senza voto)
            righe[int(r["calciatore_id"])] = {k: (0 if v is None and not k.startswith(("voto_", "fv_")) else v) for k, v in dict(r).items()}
    return righe, squadre


# ---------------------------------------------------------------- la giornata in diretta
def andamento(titolari: list[dict], panchina: list[dict], partite: list[dict], voti: dict[int, dict], squadre_voti: set[str],
              attesi: dict[int, float], fuori: set[int], regole: Regole,
              previsione: dict[int, tuple[float, float, float]] | None = None) -> dict:
    """Come sta andando una formazione schierata. `titolari`/`panchina`: {id, nome, ruolo, squadra} in ordine; `partite` con `stato`;
    `attesi`: punti attesi di chi deve ancora giocare; `fuori`: infortunati e squalificati (probabilmente senza voto).
    Le sostituzioni seguono le regole della lega (formazione.chi_va_a_punteggio), solo sui fatti noti: chi deve ancora giocare
    si considera in campo, tranne chi è fuori (cambio «probabile»)."""
    per_squadra: dict[str, dict] = {}
    for p in partite:
        for s in (p.get("casa"), p.get("trasferta")):
            per_squadra.setdefault(s, p)
    fv: dict[int, float] = {}
    voto: dict[int, float] = {}
    stato: dict[int, str] = {}
    data: dict[int, str | None] = {}
    col = COLONNA_VOTO[regole.fonte_voto]
    for g in titolari + panchina:
        i, p = g["id"], per_squadra.get(g.get("squadra"))
        data[i] = (p or {}).get("data")
        r = voti.get(i)
        f = fantavoto(r, g["ruolo"], regole) if r else None
        if g.get("squadra") in squadre_voti or (f is not None):
            stato[i] = "fatto" if f is not None else "senza_voto"
            if f is not None:
                fv[i], voto[i] = float(f), float(r[col])
        elif p is None or p.get("stato") == "rinviata":
            stato[i] = "rinviata"
        else:
            stato[i] = {"finita": "attesa_voti", IN_CORSO: IN_CORSO}.get(p.get("stato"), "da_giocare")
    certo = {i: s in DECISI for i, s in stato.items()}
    gioca = {i: (s == "fatto") if s in DECISI else (s != "rinviata" and i not in fuori) for i, s in stato.items()}
    gioc = {g["id"]: fz.Giocatore(g["id"], g.get("nome", ""), g["ruolo"], 0.0, 0.0, 0.0) for g in titolari + panchina}
    tit = [gioc[g["id"]] for g in titolari]
    panc = [gioc[g["id"]] for g in panchina]
    ids_tit = {g.id for g in tit}
    # chi entra al posto di chi: chi_va_a_punteggio tratta i mancanti in ordine di ruolo, uno dopo l'altro; rifacendo il conto con i
    # primi k mancanti si vede chi è entrato al k-esimo (stesso algoritmo della lega, nessuna regola riscritta qui)
    mancanti = sorted([t for t in tit if not gioca[t.id]], key=lambda t: fz.ORDINE_RUOLO[t.ruolo])
    sostituzioni, entrati = [], set()
    for k, m in enumerate(mancanti, start=1):
        g2 = gioca | {x.id: True for x in mancanti[k:]}
        va, _ = fz.chi_va_a_punteggio(tit, panc, g2, regole)
        nuovo = next((g for g in va if g.id not in ids_tit and g.id not in entrati), None)
        if nuovo:
            entrati.add(nuovo.id)
        certa = certo[m.id] and (certo[nuovo.id] if nuovo else all(certo[b.id] for b in panc))
        sostituzioni.append({"esce": _breve(m), "entra": _breve(nuovo) if nuovo else None, "certa": bool(certa),
                             "motivo": stato[m.id] if stato[m.id] in ("senza_voto", "rinviata") else "fuori" if m.id in fuori else stato[m.id]})
    va, _ = fz.chi_va_a_punteggio(tit, panc, gioca, regole)
    a_punteggio = {g.id for g in va}
    fatti = sum(fv[g.id] for g in va if stato[g.id] == "fatto")
    if regole.voto_senza_sostituto is not None:
        fatti += regole.voto_senza_sostituto * sum(1 for s in sostituzioni if s["entra"] is None and s["certa"])
    portiere_difesa = [g for g in va if g.ruolo in ("P", "D")]
    modificatore = None
    if regole.modificatore_difesa.attivo and portiere_difesa and all(stato[g.id] == "fatto" for g in portiere_difesa):
        modificatore = modificatore_difesa(next((voto[g.id] for g in va if g.ruolo == "P"), None),
                                           [voto[g.id] for g in va if g.ruolo == "D"], regole)
        fatti += modificatore
    restanti = sum(float(attesi.get(g.id) or 0.0) for g in va if stato[g.id] not in DECISI)
    if previsione is not None:
        # Collaudo 2/11/2026: la somma qui sopra (p×mu dei titolari) non conta le riserve che entrano al posto di chi non gioca:
        # a giornata appena iniziata dava ≈ 61,5 contro i 72,4 attesi prima. Si rifà il conto della formazione (stesse simulazioni
        # e stesse regole di Valutatore) con i fatti noti fissati: chi ha giocato ha il suo fantavoto, chi resta senza voto è fuori.
        previsti = _previsti_condizionati(tit, panc, stato, fv, voto, {i: x for i, x in previsione.items() if i not in fuori}, regole)
        if previsti is not None:
            restanti = max(0.0, previsti - fatti)
    giocatori = [{"id": g["id"], "nome": g.get("nome", ""), "ruolo": g["ruolo"], "squadra": g.get("squadra"),
                  "titolare": g["id"] in ids_tit, "a_punteggio": g["id"] in a_punteggio, "stato": stato[g["id"]],
                  "fantavoto": round(fv[g["id"]], 2) if g["id"] in fv else None, "data": data[g["id"]]} for g in titolari + panchina]
    return {"punti_fatti": round(fatti, 1), "punti_attesi_restanti": round(restanti, 1), "punti_previsti": round(fatti + restanti, 1),
            "modificatore": None if modificatore is None else round(modificatore, 1),
            # chi deve ancora scendere in campo: non chi ha già giocato e aspetta il voto (attesa_voti) né chi ha la partita rinviata
            "ancora_da_giocare": sum(1 for g in va if stato[g.id] in ("da_giocare", IN_CORSO)),
            "giocatori": giocatori, "sostituzioni": sostituzioni}


def _previsti_condizionati(tit: list[fz.Giocatore], panc: list[fz.Giocatore], stato: dict[int, str], fv: dict[int, float],
                           voto: dict[int, float], previsione: dict[int, tuple[float, float, float]], regole: Regole) -> float | None:
    """Punti attesi a fine giornata con i fatti noti: (p_voto, mu, mu_voto) del modello per chi deve ancora giocare, il fantavoto
    vero per chi ha giocato, zero probabilità per chi è rimasto senza voto o ha la partita rinviata. Riserve, voto d'ufficio e
    modificatore difesa come nel calcolo della formazione. None se il conto non si può fare (dati mancanti)."""
    try:
        rosa = []
        for g in tit + panc:
            s = stato[g.id]
            if s == "fatto":
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, 1.0, fv[g.id], voto[g.id]))
            elif s in ("senza_voto", "rinviata"):
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, 0.0, 0.0, 6.0))
            else:
                p, mu, mu_voto = previsione.get(g.id, (0.0, 0.0, 6.0))
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, float(p), float(mu), float(mu_voto)))
        v = fz.Valutatore(rosa, regole)
        fatti = [i for i, g in enumerate(rosa) if stato[g.id] == "fatto"]
        v.voti[:, fatti] = [voto[rosa[i].id] for i in fatti]      # voto vero, senza il rumore della simulazione
        idx = {g.id: i for i, g in enumerate(rosa)}
        tit_r, panc_r = [rosa[idx[g.id]] for g in tit], [rosa[idx[g.id]] for g in panc]
        return float(v._punti(tit_r, panc_r).mean())
    except (KeyError, ValueError, IndexError, StopIteration):
        return None


def _breve(g: fz.Giocatore) -> dict:
    return {"id": g.id, "nome": g.nome, "ruolo": g.ruolo}


def conta_partite(partite: list[dict]) -> dict:
    stati = [p.get("stato") for p in partite]
    return {"in_corso": stati.count(IN_CORSO), "finite": stati.count("finita"), "da_giocare": stati.count("da_giocare"),
            "rinviate": stati.count("rinviata")}


def _info_rosa(rose, prev) -> dict[int, dict]:
    """{id: {id, nome, ruolo, squadra}} dei giocatori della mia rosa: dalle previsioni se ci sono, altrimenti dalla rosa."""
    s = rose.squadra(rose.mia_squadra or "")
    out = {}
    for g in (s.giocatori if s else []):
        if g.id is None:
            continue
        i = int(g.id)
        if prev is not None and i in prev.index:
            x = prev.loc[i]
            out[i] = {"id": i, "nome": str(x["nome"]), "ruolo": str(x["ruolo"]), "squadra": x["squadra"]}
        else:
            out[i] = {"id": i, "nome": g.nome, "ruolo": g.ruolo, "squadra": getattr(g, "squadra", None)}
    return out


def _panchina_di(info: dict[int, dict], prev, titolari: list[int], regole: Regole) -> list[int]:
    """La panchina che sceglie il sistema (come nel Diario) quando quella schierata non si conosce."""
    if prev is None:
        return []
    rosa = [fz.Giocatore(i, info[i]["nome"], info[i]["ruolo"], float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]),
                         float(prev.at[i, "mu_voto"])) for i in info if i in prev.index]
    tit = [g for g in rosa if g.id in set(titolari)]
    return [g.id for g in fz._panchina(rosa, tit, regole)]


def blocco_in_corso(db, regole: Regole, rose, prev, f: dict, stagione: str, giornata: int, partite: list[dict],
                    file_scelte, file_diario) -> dict | None:
    """Il campo `in_corso` di Oggi (fase in_corso). None se non si sa quale formazione è stata schierata."""
    info = _info_rosa(rose, prev)
    consigliata = [int(g["id"]) for g in f.get("titolari") or []]
    panchina_cons = [int(g["id"]) for g in f.get("panchina") or [] if isinstance(g, dict) and "id" in g]
    sch = schierata(stagione, giornata, file_scelte, file_diario, consigliata, panchina_cons)
    if not sch:
        return None
    tit_ids, panc_ids, di = sch
    if any(i not in info for i in tit_ids):
        return None                                  # la rosa è cambiata: la formazione schierata non si ricostruisce
    if panc_ids is None:
        panc_ids = _panchina_di(info, prev, tit_ids, regole)
    panc_ids = [i for i in panc_ids if i in info and i not in tit_ids]
    voti, squadre_voti = voti_giornata(db, stagione, giornata, tit_ids + panc_ids, regole)
    attesi = {int(i): float(prev.at[i, "atteso"]) for i in tit_ids + panc_ids if prev is not None and i in prev.index}
    fuori = {int(i) for i in tit_ids + panc_ids if prev is not None and i in prev.index and prev.at[i, "stato"] in FUORI}
    previsione = {int(i): (float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]), float(prev.at[i, "mu_voto"]))
                  for i in tit_ids + panc_ids if prev is not None and i in prev.index}
    a = andamento([info[i] for i in tit_ids], [info[i] for i in panc_ids], partite, voti, squadre_voti, attesi, fuori, regole,
                  previsione)
    return {"giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole), "formazione_di": di} | a | {
        "partite": conta_partite(partite)}


def blocco_riepilogo(db, regole: Regole, rose, stagione: str, giornata: int, file_scelte, file_diario) -> dict | None:
    """Il campo `riepilogo` di Oggi (fase finita): dal Diario se la giornata è già calcolata, altrimenti i punti fatti dai voti."""
    base = {"giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole)}
    voce = (diario.carica(file_diario).get("giornate") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    if isinstance(voce, dict) and isinstance(voce.get("consigliata"), dict):
        mia = voce.get("schierata") or voce.get("automatica") or voce["consigliata"]
        cons = voce["consigliata"]
        return base | {"formazione_di": "tua" if voce.get("schierata") else "consigliata", "nel_diario": True,
                       "punti_fatti": mia.get("reale"), "punti_attesi": mia.get("atteso"), "intervallo": mia.get("intervallo"),
                       "consigliata": {"punti_fatti": cons.get("reale"), "punti_attesi": cons.get("atteso")}}
    info = _info_rosa(rose, None)
    sch = schierata(stagione, giornata, file_scelte, file_diario)
    if not sch or any(i not in info for i in sch[0]):
        return None
    tit_ids, panc_ids, di = sch
    panc_ids = [i for i in (panc_ids or []) if i in info and i not in tit_ids]
    voti, squadre_voti = voti_giornata(db, stagione, giornata, tit_ids + panc_ids, regole)
    if not squadre_voti:
        return None                                   # voti non ancora scaricati: niente numeri inventati
    partite = [{"casa": s, "trasferta": None, "stato": "finita"} for s in squadre_voti]
    a = andamento([info[i] for i in tit_ids], [info[i] for i in panc_ids], partite, voti, squadre_voti, {}, set(), regole)
    ist = (diario.carica(file_diario).get("istantanee") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    atteso = ist.get("atteso") if isinstance(ist, dict) and di == "consigliata" else None
    return base | {"formazione_di": di, "nel_diario": False, "punti_fatti": a["punti_fatti"], "punti_attesi": atteso,
                   "intervallo": None, "consigliata": None}


def blocco_prossima(oggi: dict, adesso: datetime) -> dict:
    """Il campo `prossima` (fase finita): la giornata da preparare, quando si chiude e da quando conviene prepararla."""
    scad = _data(oggi.get("scadenza"))
    if oggi.get("con_probabili") or scad is None:
        da = adesso
    else:
        da = max(adesso, scad - timedelta(hours=ORE_PROBABILI))
    return {"giornata": oggi.get("giornata"), "giornata_lega": oggi.get("giornata_lega"), "scadenza": oggi.get("scadenza"),
            "prepara_da": da.isoformat(sep=" ", timespec="minutes"), "con_probabili": bool(oggi.get("con_probabili"))}


# ---------------------------------------------------------------- insieme
def aggiungi(corpo: dict, db, regole: Regole, rose, prev, f: dict, stagione: str, adesso: datetime, file_scelte=None,
             file_diario=None, live: dict | None = None) -> dict:
    """Aggiunge a Oggi `fase`, `partite[].stato` e, secondo la fase, `in_corso` o `riepilogo` + `prossima`. Non alza mai errori:
    se qualcosa non va, `fase` resta quella dei soli orari e i blocchi mancano (null)."""
    corpo["fase"] = IN_CORSO if corpo.get("iniziata") else PRIMA
    corpo["in_corso"] = corpo["riepilogo"] = corpo["prossima"] = None
    giornata = corpo.get("giornata")
    try:
        turno = inizio_turno(corpo.get("partite") or [])
        for p in corpo.get("partite") or []:
            p["stato"] = stato_partita(p, adesso, live, turno)
        precedente = None
        if giornata and not corpo.get("iniziata") and giornata - 1 >= getattr(regole, "prima_giornata_lega", 1):
            precedente = giornata - 1
        fine = fine_giornata(db, stagione, precedente) if precedente else None
        corpo["fase"] = calcola_fase(bool(corpo.get("iniziata")), corpo.get("ore_mancanti"), fine, adesso)
        if corpo["fase"] == IN_CORSO and giornata:
            corpo["in_corso"] = blocco_in_corso(db, regole, rose, prev, f, stagione, giornata, corpo.get("partite") or [],
                                                file_scelte, file_diario)
        elif corpo["fase"] == FINITA:
            corpo["riepilogo"] = blocco_riepilogo(db, regole, rose, stagione, precedente, file_scelte, file_diario)
            corpo["prossima"] = blocco_prossima(corpo, adesso)
    except Exception:                                   # noqa: BLE001  (Oggi si apre comunque)
        pass
    return corpo
