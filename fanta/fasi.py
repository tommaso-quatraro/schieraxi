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

from . import avvisi, diario, rinvii, scelte, turno as turni
from . import etichette
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
    Con `turno` (l'inizio del turno) una partita non giocata senza data, o fuori dalla finestra del turno e non in anticipo, è «rinviata»:
    il calendario l'ha già spostata a un recupero."""
    if p.get("giocata"):
        return "finita"
    v = _DA_LIVE.get(((live or {}).get((p.get("casa"), p.get("trasferta"))) or {}).get("stato"))
    if v:
        return v
    inizio = _data(p.get("data"))
    if turno is not None and not turni.della_giornata(inizio, turno):       # un anticipo non è «rinviata» (turno.py)
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
    """Fine stimata di una giornata GIÀ CHIUSA (giocate tutte le partite del turno): inizio dell'ultima partita del turno più la
    durata. Le partite rinviate (fuori dal turno o senza data, rinvii.py) non la tengono aperta, recuperate o no: quelle ancora da
    recuperare le dice `recuperi_mancanti`. None se una partita del turno è ancora da giocare o se la giornata non ha date."""
    righe = db.execute("SELECT data, giocata FROM partite WHERE stagione = ? AND giornata = ?", (stagione, giornata)).fetchall()
    date = [d for d in (_data(r[0]) for r in righe) if d]
    if not date:
        return None
    primo = turni.inizio(date)
    del_turno = [(d, g) for d, g in ((_data(r[0]), r[1]) for r in righe) if d and turni.nel_turno(d, primo)]
    if not del_turno or not all(g for _, g in del_turno):
        return None
    return max(d for d, _ in del_turno) + DURATA_PARTITA


def recuperi_mancanti(db: sqlite3.Connection, stagione: str, giornata: int) -> list[dict]:
    """Le partite rinviate della giornata non ancora recuperate: [{casa, trasferta, data}] (data del recupero o None)."""
    righe = db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND giornata = ? ORDER BY data",
                       (stagione, giornata)).fetchall()
    partite = [{"data": r[0], "casa": r[1], "trasferta": r[2], "giocata": r[3]} for r in righe]
    return [{"casa": p["casa"], "trasferta": p["trasferta"], "data": p["data"]} for p in rinvii.rinviate(partite)]


# ---------------------------------------------------------------- la formazione schierata
def schierata(stagione: str, giornata: int, file_scelte, file_diario, consigliata: list[int] | None = None,
              panchina_consigliata: list[int] | None = None, ruoli: dict[int, str] | None = None,
              regole: Regole | None = None) -> tuple[list[int], list[int] | None, str] | None:
    """(titolari, panchina o None, di chi è: `tua` o `consigliata`). In ordine: la scelta dell'utente, la consigliata congelata alla
    scadenza (istantanea del Diario), la copia automatica, la consigliata di adesso. Senza file non si legge niente (mai i file comuni).
    Con `ruoli` ({id: ruolo} della rosa) e `regole` la scelta dell'utente conta solo se si può schierare (regola unica,
    `scelte.motivo_non_valida`, la stessa della Formazione): se no vale la consigliata, come senza scelta."""
    sc = scelte.leggi(stagione, giornata, file_scelte) if file_scelte else None
    controlla = ruoli is not None and regole is not None
    if sc and len(sc.get("titolari") or []) == 11 and not (controlla and scelte.motivo_non_valida(sc["titolari"], ruoli, regole)):
        return [int(i) for i in sc["titolari"]], [int(i) for i in sc.get("panchina") or []] or None, "tua"
    ist = (diario.carica(file_diario).get("istantanee") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    if isinstance(ist, dict) and len(ist.get("titolari") or []) == 11:
        return ([int(g["id"]) for g in ist["titolari"]], [int(g["id"]) for g in ist.get("panchina") or []] or None, "consigliata")
    auto = scelte.leggi(stagione, giornata, file_scelte, anche_automatica=True) if file_scelte else None
    if auto and auto.get("tipo") == scelte.TIPO_AUTOMATICA and len(auto.get("titolari") or []) == 11:    # non la scelta scartata sopra
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


def voti_arrivati(db: sqlite3.Connection, stagione: str, giornata: int, regole: Regole) -> bool:
    """I voti della giornata sono arrivati: ogni squadra con una partita giocata della giornata (del turno o recuperata) ha i suoi
    voti, la stessa regola dello stato «attesa_voti». Regola unica per il riepilogo di Oggi e per l'avviso di fine giornata (#649):
    finché manca, niente totale. Falso se nessuna partita è giocata."""
    giocate = {s for r in db.execute("SELECT casa, trasferta FROM partite WHERE stagione = ? AND giornata = ? AND giocata = 1",
                                     (stagione, giornata)) for s in r if s}
    return bool(giocate) and giocate <= voti_giornata(db, stagione, giornata, [], regole)[1]


def squadre_dei_giocatori(db: sqlite3.Connection, stagione: str, giornata: int, ids) -> dict[int, str]:
    """{id: squadra di Serie A come la scrivono calendario e voti, «atalanta»}: dalla riga dei voti della giornata, altrimenti dal
    listone (tabella `calciatori`). Le rose hanno la sigla scritta dall'utente («ATA»), che con il calendario non si confronta:
    così la partita rinviata di un giocatore si trova (#649)."""
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    segni = ",".join("?" * len(ids))
    out = {int(i): s for i, s in db.execute(f"SELECT id, squadra_slug FROM calciatori WHERE id IN ({segni})", ids) if s}
    out |= {int(i): s for i, s in db.execute(f"SELECT calciatore_id, squadra FROM voti WHERE stagione = ? AND giornata = ? "
                                             f"AND calciatore_id IN ({segni})", (stagione, giornata, *ids)) if s}
    return out


# ---------------------------------------------------------------- la giornata in diretta
def _stato_giocatore(g: dict, partita: dict | None, riga_voti: dict | None, squadre_voti: set[str], regole: Regole
                     ) -> tuple[str, float | None]:
    """(stato del giocatore nella giornata, fantavoto se l'ha preso). Stati: fatto, senza_voto, attesa_voti, in_corso, da_giocare,
    rinviata (vedi in cima al file). `partita` è quella della sua squadra, con `stato` già calcolato."""
    f = fantavoto(riga_voti, g["ruolo"], regole) if riga_voti else None
    if g.get("squadra") in squadre_voti or (f is not None):
        return ("fatto" if f is not None else "senza_voto"), f
    if partita is None or partita.get("stato") == "rinviata":
        return "rinviata", None
    return {"finita": "attesa_voti", IN_CORSO: IN_CORSO}.get(partita.get("stato"), "da_giocare"), None


def andamento(titolari: list[dict], panchina: list[dict], partite: list[dict], voti: dict[int, dict], squadre_voti: set[str],
              attesi: dict[int, float], fuori: set[int], regole: Regole,
              previsione: dict[int, tuple[float, float, float]] | None = None, rinvio: dict | None = None) -> dict:
    """Come sta andando una formazione schierata. `titolari`/`panchina`: {id, nome, ruolo, squadra} in ordine; `partite` con `stato`;
    `attesi`: punti attesi di chi deve ancora giocare; `fuori`: infortunati e squalificati (probabilmente senza voto).
    Le sostituzioni seguono le regole della lega (formazione.chi_va_a_punteggio), solo sui fatti noti: chi deve ancora giocare
    si considera in campo, tranne chi è fuori (cambio «probabile»).
    `rinvio` (rinvii.regola della giornata; None = la regola generale della lega) dice cosa vale per chi ha la partita rinviata:
    `aspetta` = resta in formazione e conta il voto del recupero (punti attesi, nessun cambio); `senza_voto` = entra la riserva
    (cambio certo); `voto_ufficio` = prende il voto fisso, contato subito tra i punti fatti."""
    modo = (rinvio or {}).get("modo") or getattr(regole, "partite_rinviate", "aspetta")
    ufficio = (rinvio or {}).get("valore")
    ufficio = float(getattr(regole, "voto_ufficio_rinviate", 6.0) if ufficio is None else ufficio)
    senza_partita: set[int] = set()
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
        stato[i], f = _stato_giocatore(g, p, voti.get(i), squadre_voti, regole)
        if f is not None:
            fv[i], voto[i] = float(f), float(voti[i][col])
        elif stato[i] == "rinviata":
            if p is None:                    # la sua squadra non ha proprio una partita in questa giornata: niente recupero né voto
                senza_partita.add(i)
            elif modo == "voto_ufficio":
                fv[i], voto[i] = ufficio, ufficio
    # una partita rinviata: con il voto d'ufficio è come un voto preso; senza voto è un cambio certo; se si aspetta resta in campo
    aspetta = {i for i, s in stato.items() if s == "rinviata" and modo == "aspetta" and i not in senza_partita}
    certo = {i: s in DECISI or (s == "rinviata" and i not in aspetta) for i, s in stato.items()}
    gioca = {i: (s == "fatto") if s in DECISI else (i in fv) if s == "rinviata" and i not in aspetta else i not in fuori
             for i, s in stato.items()}
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
    fatti = sum(fv[g.id] for g in va if g.id in fv)          # voti presi e voti d'ufficio delle partite rinviate
    if regole.voto_senza_sostituto is not None:
        fatti += regole.voto_senza_sostituto * sum(1 for s in sostituzioni if s["entra"] is None and s["certa"])
    portiere_difesa = [g for g in va if g.ruolo in ("P", "D")]
    modificatore = None
    if regole.modificatore_difesa.attivo and portiere_difesa and all(g.id in voto for g in portiere_difesa):
        modificatore = modificatore_difesa(next((voto[g.id] for g in va if g.ruolo == "P"), None),
                                           [voto[g.id] for g in va if g.ruolo == "D"], regole)
        fatti += modificatore
    restanti = sum(float(attesi.get(g.id) or 0.0) for g in va if stato[g.id] not in DECISI and g.id not in fv)
    if previsione is not None:
        # Collaudo 2/11/2026: la somma qui sopra (p×mu dei titolari) non conta le riserve che entrano al posto di chi non gioca:
        # a giornata appena iniziata dava ≈ 61,5 contro i 72,4 attesi prima. Si rifà il conto della formazione (stesse simulazioni
        # e stesse regole di Valutatore) con i fatti noti fissati: chi ha giocato ha il suo fantavoto, chi resta senza voto è fuori.
        previsti = _previsti_condizionati(tit, panc, stato, fv, voto, {i: x for i, x in previsione.items() if i not in fuori}, regole,
                                          modo)
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
                           voto: dict[int, float], previsione: dict[int, tuple[float, float, float]], regole: Regole,
                           modo: str = "senza_voto") -> float | None:
    """Punti attesi a fine giornata con i fatti noti: (p_voto, mu, mu_voto) del modello per chi deve ancora giocare, il fantavoto
    vero per chi ha giocato (o il voto d'ufficio di una partita rinviata), zero probabilità per chi è rimasto senza voto. Chi ha la
    partita rinviata: con `aspetta` conta come chi deve ancora giocare (il recupero), con `senza_voto` è fuori. Riserve, voto
    d'ufficio e modificatore difesa come nel calcolo della formazione. None se il conto non si può fare (dati mancanti)."""
    try:
        rosa = []
        for g in tit + panc:
            s = stato[g.id]
            if g.id in fv:
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, 1.0, fv[g.id], voto[g.id]))
            elif s == "senza_voto" or (s == "rinviata" and modo != "aspetta"):
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, 0.0, 0.0, 6.0))
            else:
                p, mu, mu_voto = previsione.get(g.id, (0.0, 0.0, 6.0))
                rosa.append(fz.Giocatore(g.id, g.nome, g.ruolo, float(p), float(mu), float(mu_voto)))
        v = fz.Valutatore(rosa, regole)
        fatti = [i for i, g in enumerate(rosa) if g.id in fv]
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
    # chi si può schierare: come la Formazione, i giocatori della rosa con una previsione per la giornata
    ruoli = {i: x["ruolo"] for i, x in info.items() if prev is None or i in prev.index}
    sch = schierata(stagione, giornata, file_scelte, file_diario, consigliata, panchina_cons, ruoli, regole)
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
                  previsione, rinvii.regola(regole, stagione, giornata))
    for g in a["giocatori"]:                         # la stessa etichetta di Formazione e scheda (fanta/etichette.py)
        i = g["id"]
        g["etichetta"] = etichette.di_giocatore({"stato_partita": g["stato"], "titolarita": "fuori" if i in fuori and g["stato"] not in DECISI else None,
                                                 "stato": prev.at[i, "stato"] if prev is not None and i in prev.index else None})
    return {"giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole), "formazione_di": di} | a | {
        "partite": conta_partite(partite)}


def blocco_riepilogo(db, regole: Regole, rose, stagione: str, giornata: int, file_scelte, file_diario) -> dict | None:
    """Il campo `riepilogo` di Oggi (fase finita): dal Diario se la giornata è già calcolata, altrimenti i punti fatti dai voti.
    Con una partita rinviata ancora da recuperare la giornata è finita lo stesso (fine_giornata): la regola della lega dice cosa
    contano i suoi giocatori; con `aspetta` restano in formazione senza voto e `recuperi` elenca le partite che mancano (i punti
    possono ancora cambiare), con le altre regole `recuperi` è vuoto (i punti sono già quelli finali)."""
    r_rinvio = rinvii.regola(regole, stagione, giornata)
    mancano = recuperi_mancanti(db, stagione, giornata)
    # con un recupero da giocare il riepilogo ha anche il menu per decidere quella giornata (`rinvio`, come in Oggi)
    base = {"giornata": giornata, "giornata_lega": serie_a_a_lega(giornata, regole),
            "recuperi": mancano if r_rinvio["modo"] == "aspetta" else [],
            "rinvio": rinvii.scelta(regole, stagione, giornata) if mancano else None}
    voce = (diario.carica(file_diario).get("giornate") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    if isinstance(voce, dict) and isinstance(voce.get("consigliata"), dict):
        mia = voce.get("schierata") or voce.get("automatica") or voce["consigliata"]
        cons = voce["consigliata"]
        return base | {"formazione_di": "tua" if voce.get("schierata") else "consigliata", "nel_diario": True,
                       "punti_fatti": mia.get("reale"), "punti_attesi": mia.get("atteso"), "intervallo": mia.get("intervallo"),
                       "consigliata": {"punti_fatti": cons.get("reale"), "punti_attesi": cons.get("atteso")}}
    info = _info_rosa(rose, None)
    sch = schierata(stagione, giornata, file_scelte, file_diario, ruoli={i: x["ruolo"] for i, x in info.items()}, regole=regole)
    if not sch or any(i not in info for i in sch[0]):
        return None
    tit_ids, panc_ids, di = sch
    panc_ids = [i for i in (panc_ids or []) if i in info and i not in tit_ids]
    if not voti_arrivati(db, stagione, giornata, regole):
        return None                                   # una partita giocata senza i suoi voti: niente numeri inventati (#649)
    voti, squadre_voti = voti_giornata(db, stagione, giornata, tit_ids + panc_ids, regole)
    # le partite dal calendario della giornata e la squadra di ogni giocatore dall'archivio: le rose hanno la sigla (#649)
    da_recuperare = {(p["casa"], p["trasferta"]) for p in mancano}
    partite = [{"casa": c, "trasferta": t, "data": d, "stato": "finita" if g else "rinviata" if (c, t) in da_recuperare else "da_giocare"}
               for d, c, t, g in db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND giornata = ?",
                                            (stagione, giornata))]
    squadre = squadre_dei_giocatori(db, stagione, giornata, tit_ids + panc_ids)
    giocatore = lambda i: info[i] | ({"squadra": squadre[i]} if i in squadre else {})     # noqa: E731
    a = andamento([giocatore(i) for i in tit_ids], [giocatore(i) for i in panc_ids], partite, voti, squadre_voti, {}, set(), regole,
                  rinvio=r_rinvio)
    ist = (diario.carica(file_diario).get("istantanee") or {}).get(f"{stagione}/{giornata}") if file_diario else None
    atteso = ist.get("atteso") if isinstance(ist, dict) and di == "consigliata" else None
    return base | {"formazione_di": di, "nel_diario": False, "punti_fatti": a["punti_fatti"], "punti_attesi": atteso,
                   "intervallo": None, "consigliata": None}


def entrato_dopo_la_scadenza(stagione: str, giornata: int, scadenza: datetime | None, dal: datetime | None, file_scelte,
                             file_diario) -> bool:
    """Chi è entrato in SchieraXI dopo la scadenza della giornata e non ha nessuna formazione per lei (né sua né la copia della
    consigliata vista prima della scadenza): quella giornata non l'ha schierata con noi, niente punti finti; si prepara la prossima.
    `dal` = quando è nato l'account (ora locale); None (senza account o non noto) = mai."""
    if dal is None or scadenza is None or dal < scadenza:
        return False
    return schierata(stagione, giornata, file_scelte, file_diario) is None


def prossima_dopo(db, regole: Regole, stagione: str, giornata: int, adesso: datetime) -> dict | None:
    """Il blocco `prossima` per la giornata dopo `giornata` (stessa forma della fase finita). None se non è in calendario."""
    g = giornata + 1
    scad = avvisi.scadenza(avvisi.prima_partita(db, stagione, g), regole)
    if scad is None:
        return None
    con_probabili = db.execute("SELECT 1 FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio' LIMIT 1",
                               (stagione, g)).fetchone() is not None
    return blocco_prossima({"giornata": g, "giornata_lega": serie_a_a_lega(g, regole), "con_probabili": con_probabili,
                            "scadenza": scad.isoformat(sep=" ", timespec="minutes")}, adesso)


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
             file_diario=None, live: dict | None = None, dal: datetime | None = None) -> dict:
    """Aggiunge a Oggi `fase`, `partite[].stato` e, secondo la fase, `in_corso` o `riepilogo` + `prossima`. Non alza mai errori:
    se qualcosa non va, `fase` resta quella dei soli orari e i blocchi mancano (null).
    `dal` (facoltativo): quando è nato l'account. Chi è entrato a giornata iniziata senza una formazione (entrato_dopo_la_scadenza)
    non ha `in_corso` (niente punti finti) ma `senza_formazione: true` e la `prossima` giornata da preparare."""
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
        if corpo["fase"] == IN_CORSO and giornata and entrato_dopo_la_scadenza(stagione, giornata, _data(corpo.get("scadenza")), dal,
                                                                            file_scelte, file_diario):
            corpo["senza_formazione"] = True
            corpo["prossima"] = prossima_dopo(db, regole, stagione, giornata, adesso)
            corpo["miei_titolari"] = {}                 # nessun «tuo titolare» nelle partite: la formazione non l'ha schierata
        elif corpo["fase"] == IN_CORSO and giornata:
            corpo["in_corso"] = blocco_in_corso(db, regole, rose, prev, f, stagione, giornata, corpo.get("partite") or [],
                                                file_scelte, file_diario)
        elif corpo["fase"] == FINITA:
            corpo["riepilogo"] = blocco_riepilogo(db, regole, rose, stagione, precedente, file_scelte, file_diario)
            corpo["prossima"] = blocco_prossima(corpo, adesso)
    except Exception:                                   # noqa: BLE001  (Oggi si apre comunque)
        pass
    return corpo


# ---------------------------------------------------------------- etichette a giornata iniziata
# motivi che vengono dalle probabili formazioni (consigli.motivi): dopo la scadenza non dicono più niente di vero
_MOTIVI_PROBABILI = ("titolare", "parte dalla panchina", "non tra i convocati previsti")


def stati_giocatori(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, giocatori: list[dict], adesso: datetime,
                    live: dict | None = None) -> dict[int, str]:
    """{id: stato nella giornata} (fatto, senza_voto, attesa_voti, in_corso, da_giocare, rinviata) per i giocatori chiesti
    ({id, ruolo, squadra}): dalla partita della sua squadra (calendario, diretta, orario) e dai voti già usciti."""
    righe = db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND giornata = ? ORDER BY data",
                       (stagione, giornata)).fetchall()
    partite = [{"data": r[0], "casa": r[1], "trasferta": r[2], "giocata": bool(r[3])} for r in righe]
    turno = inizio_turno(partite)
    per_squadra: dict[str, dict] = {}
    for p in partite:
        p["stato"] = stato_partita(p, adesso, live, turno)
        for sq in (p["casa"], p["trasferta"]):
            per_squadra.setdefault(sq, p)
    ids = [int(g["id"]) for g in giocatori]
    voti, squadre_voti = voti_giornata(db, stagione, giornata, ids, regole)
    return {int(g["id"]): _stato_giocatore(g, per_squadra.get(g.get("squadra")), voti.get(int(g["id"])), squadre_voti, regole)[0]
            for g in giocatori}


def iniziata(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int | None, adesso: datetime) -> bool:
    """La formazione di questa giornata è chiusa (scadenza passata): stessa regola di Oggi (`iniziata`)."""
    if not giornata:
        return False
    scad = avvisi.scadenza(avvisi.prima_partita(db, stagione, giornata), regole)
    return scad is not None and scad <= adesso


def schede_a_giornata_iniziata(schede: list[dict], db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int,
                               adesso: datetime, live: dict | None = None) -> dict[int, dict]:
    """Dopo la scadenza le etichette delle probabili (titolare, ballottaggio, panchina...) non hanno più senso: ogni scheda
    perde `titolarita` (null; resta `fuori` per infortunati e squalificati finché non c'è il voto) e i motivi delle probabili, e
    prende `stato_partita` (lo stato vero della sua giornata) e `fv_preso` (il fantavoto preso con le regole della lega, solo con
    `stato_partita` «fatto»; altrimenti null): a partita finita i client mostrano com'è andata invece di «gioca N%».
    Restituisce {id: scheda nuova}; le schede ricevute non si toccano (possono stare nella cache dei calcoli)."""
    uniche = {int(x["id"]): x for x in schede if isinstance(x, dict) and "id" in x}
    stati = stati_giocatori(db, regole, stagione, giornata, list(uniche.values()), adesso, live)
    fv_presi = _fantavoti_presi(db, regole, stagione, giornata, {i: x for i, x in uniche.items() if stati.get(i) == "fatto"})
    # chi è infortunato o squalificato resta «fuori» finché i voti non dicono com'è andata (altrimenti sarebbe «da giocare»)
    fuori = lambda x, st: x.get("titolarita") == "fuori" and st not in DECISI
    nuove = {i: x | {"titolarita": "fuori" if fuori(x, stati.get(i)) else None, "stato_partita": stati.get(i), "fv_preso": fv_presi.get(i)}
             | _senza_probabili(x) for i, x in uniche.items()}
    for x in nuove.values():
        x["etichetta"] = etichette.di_giocatore(x)
    return nuove


def _fantavoti_presi(db: sqlite3.Connection, regole: Regole, stagione: str, giornata: int, giocatori: dict[int, dict]) -> dict[int, float]:
    """{id: fantavoto preso} con le regole della lega, per chi ha già il voto (stesso calcolo di `_stato_giocatore`)."""
    if not giocatori:
        return {}
    voti, _ = voti_giornata(db, stagione, giornata, list(giocatori), regole)
    presi = {}
    for i, g in giocatori.items():
        if i in voti and g.get("ruolo"):
            f = fantavoto(voti[i], g["ruolo"], regole)
            if f is not None:
                presi[i] = round(float(f), 2)
    return presi


def _senza_probabili(x: dict) -> dict:
    """`motivi` senza quelli delle probabili; `motivi_frasi` (in parallelo, una per motivo) perde le stesse voci."""
    motivi = list(x.get("motivi") or [])
    tieni = [k for k, m in enumerate(motivi) if not str(m).startswith(_MOTIVI_PROBABILI)]
    out = {"motivi": [motivi[k] for k in tieni]}
    if isinstance(x.get("motivi_frasi"), list) and len(x["motivi_frasi"]) == len(motivi):
        out["motivi_frasi"] = [x["motivi_frasi"][k] for k in tieni]
    return out


def squadre_in_anticipo_iniziato(db: sqlite3.Connection, stagione: str, giornata: int | None, adesso: datetime,
                                 live: dict | None = None) -> set[str]:
    """Le squadre di Serie A che hanno già cominciato (o finito) una partita in ANTICIPO di questa giornata (turno.anticipo), o che
    hanno giocato un anticipo lontano (turno.lontano: settimane prima, #659): i loro giocatori mostrano lo stato vero della partita
    anche con la formazione ancora aperta, e restano fermi."""
    if not giornata:
        return set()
    righe = db.execute("SELECT data, casa, trasferta, giocata FROM partite WHERE stagione = ? AND giornata = ?",
                       (stagione, giornata)).fetchall()
    partite = [{"data": r[0], "casa": r[1], "trasferta": r[2], "giocata": bool(r[3])} for r in righe]
    inizio = inizio_turno(partite)
    precedente, prossimo = avvisi.turni_vicini(db, stagione, giornata)
    squadre: set[str] = set()
    for p in partite:
        d = _data(p["data"])
        if (turni.lontano(d, p["giocata"], inizio, precedente, prossimo)
                or turni.anticipo(d, inizio) and stato_partita(p, adesso, live, inizio) != "da_giocare"):
            squadre.update(s for s in (p["casa"], p["trasferta"]) if s)
    return squadre


def formazione_a_giornata_iniziata(f: dict, db: sqlite3.Connection, regole: Regole, stagione: str, adesso: datetime,
                                   live: dict | None = None) -> dict:
    """La risposta della Formazione dopo la scadenza (`iniziata: true`, schede come `schede_a_giornata_iniziata`); prima della
    scadenza `iniziata: false` e tutto com'era, tranne i giocatori di un anticipo già cominciato (stato vero della partita).
    Una copia: `f` viene dalla cache e non si modifica. Mai un errore: se qualcosa
    non va, la formazione torna com'era."""
    try:
        tutte = [*(f.get("titolari") or []), *(f.get("panchina") or []), *(f.get("fuori") or []), *(f.get("schede") or {}).values()]
        aperta = not iniziata(db, regole, stagione, f.get("giornata"), adesso)
        if aperta:
            # formazione ancora aperta: solo chi gioca in un anticipo già cominciato ha lo stato vero della partita («Ha giocato»,
            # «Voto in arrivo»...); la formazione resta salvabile (turno.py, anticipi)
            squadre = squadre_in_anticipo_iniziato(db, stagione, f.get("giornata"), adesso, live)
            tutte = [x for x in tutte if isinstance(x, dict) and x.get("squadra") in squadre]
            if not tutte:
                return f | {"iniziata": False}
        nuove = schede_a_giornata_iniziata(tutte, db, regole, stagione, f["giornata"], adesso, live)
        lista = lambda chiave: [nuove.get(int(x["id"]), x) for x in f.get(chiave) or []]
        return f | {"iniziata": not aperta, "titolari": lista("titolari"), "panchina": lista("panchina"), "fuori": lista("fuori"),
                    "schede": {k: nuove.get(int(x["id"]), x) for k, x in (f.get("schede") or {}).items()}}
    except Exception:                                   # noqa: BLE001  (la Formazione si apre comunque)
        return f
