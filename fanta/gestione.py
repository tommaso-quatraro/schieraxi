"""Gestione della lega: cosa fare oggi, calendario con difficoltà, mercato (chi prendere tra gli svincolati).

Tutto parte dai calcoli già fatti per la formazione e per gli scambi (stesse previsioni, stesse regole).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from . import avvisi, buon_senso, calcolo, consigli, etichette, fasi, frasi, modello, rinvii, scambi, scelte
from .avvisi import prima_partita       # in `oggi` il nome `avvisi` è anche la lista degli avvisi
from .frasi import F
from .lega import Rose
from .regole import RUOLI, Regole, serie_a_a_lega

GIORNATE_CALENDARIO = 5


# ---------------------------------------------------------------- calendario con difficoltà
def calendario(db: sqlite3.Connection, n: int = GIORNATE_CALENDARIO, regole: Regole | None = None) -> dict:
    """Prossime n giornate di ogni squadra: avversario, casa/fuori e difficoltà da 1 (facile) a 5 (difficile)."""
    stagione = consigli.stagione_corrente()
    prima = consigli.giornata_da_giocare(db, stagione, regole)
    if prima is None:
        raise ValueError("Il calendario della stagione non è ancora disponibile (di solito esce a luglio): previsioni e asta partono appena arriva. Aggiorna i dati più avanti.")
    d = consigli.dati(db)
    chiave = ("calendario", consigli._versione(db), prima, n)
    pronto = consigli._cache.get(chiave, calcolo.MANCA)
    if pronto is not calcolo.MANCA:
        return pronto
    par = modello.Parametri()
    # per la prima giornata la difficoltà è quella delle previsioni (che nascono dal modello): stessi colori ovunque
    dalla_previsione: dict[str, int] = {}
    if regole is not None:
        try:
            prev, _, _ = consigli.previsioni(db, regole)
            dalla_previsione = prev.groupby("squadra")["difficolta"].first().astype(int).to_dict()
        except ValueError:
            pass
    squadre: dict[str, list[dict]] = {}
    giornate = []
    for g in range(prima, prima + n):
        incontri = d.partite[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == g)]
        if incontri.empty:
            continue
        giornate.append(g)
        forza = modello.forza_squadre(d, stagione, g, par)
        for _, m in incontri.iterrows():
            lc, lt = forza.gol_attesi(m["casa"], m["trasferta"])
            data = None if pd.isna(m["data"]) else str(m["data"])
            dc, dt = consigli.difficolta(lc - lt), consigli.difficolta(lt - lc)
            if g == prima:
                dc, dt = dalla_previsione.get(m["casa"], dc), dalla_previsione.get(m["trasferta"], dt)
            squadre.setdefault(m["casa"], []).append({"giornata": g, "avversario": m["trasferta"], "in_casa": True,
                                                      "difficolta": dc, "data": data})
            squadre.setdefault(m["trasferta"], []).append({"giornata": g, "avversario": m["casa"], "in_casa": False,
                                                           "difficolta": dt, "data": data})
    righe = []
    for s, partite in squadre.items():
        media = sum(p["difficolta"] for p in partite) / len(partite)
        righe.append({"squadra": s, "media": round(media, 2), "partite": sorted(partite, key=lambda p: p["giornata"])})
    risultato = {"giornate": giornate, "squadre": sorted(righe, key=lambda r: (r["media"], r["squadra"]))}
    with consigli._blocco:
        consigli._cache[chiave] = risultato
    return risultato


# ---------------------------------------------------------------- mercato
def _giocatore(v: scambi.Valori, i: int) -> dict:
    return {"id": int(i), "nome": v.info.at[i, "nome"], "ruolo": v.info.at[i, "ruolo"],
            "squadra": v.info.at[i, "squadra"], "quotazione": int(v.info.at[i, "quotazione"])}


def mercato(db: sqlite3.Connection, regole: Regole, rose: Rose, nome: str | None = None, massimo: int = 10,
            candidati_per_ruolo: int = 12, con_buon_senso: bool = True) -> dict:
    """Svincolati che migliorano la squadra: per ogni coppia (chi esce, chi entra) dello stesso ruolo
    i punti attesi in più (prossime giornate una per una + resto della stagione, come per gli scambi).
    Ogni proposta passa dal buon senso (`buon_senso.giudica_svincolo`): `proposte` ha solo quelle sensate (`sensato` True,
    `motivo` = perché conviene), `scartate` le prime MAX_SCARTATI bocciate con il motivo in una frase. Con `con_buon_senso=False` niente
    filtro (serve a stimare quanto valgono i crediti, `scambi_multi.tasso_da_mercato`: lì contano i numeri, non i consigli)."""
    s = rose.squadra(nome or rose.mia_squadra or "")
    if not s:
        raise ValueError("Squadra non trovata: indica la tua squadra in Squadra > Squadre e rose")
    v = consigli.valori_scambi(db, regole)
    mie = [g.id for g in s.giocatori if g.id is not None and g.id in v.info.index]
    occupati = {g.id for sq in rose.squadre for g in sq.giocatori if g.id is not None}
    liberi = [i for i in v.info.index if i not in occupati]

    def forza(i: int) -> float:
        return sum(t[i][1] * t[i][2] for t in v.per_giornata if i in t)

    ordinati = {r: sorted((i for i in liberi if v.info.at[i, "ruolo"] == r), key=lambda i: -forza(i)) for r in RUOLI}
    costi = {g.id: g.costo for g in s.giocatori if g.id is not None}
    crediti = s.crediti_residui

    def candidati(x: int) -> list[int]:
        """I migliori svincolati dello stesso ruolo, e se si conoscono i crediti solo quelli che si possono permettere
        (crediti + rimborso di chi esce)."""
        elenco = ordinati[v.info.at[x, "ruolo"]]
        if crediti is None:
            return elenco[:candidati_per_ruolo]
        pagato = costi.get(x)
        budget = crediti + (round(pagato * regole.rimborso_svincolo) if pagato is not None else 0)
        return [i for i in elenco if int(v.info.at[i, "quotazione"]) <= budget][:candidati_per_ruolo]
    base = scambi.valore_rosa(mie, v, regole)
    prof = _profili(db, regole)
    trovati = []
    for x in mie:
        for y in candidati(x):
            nuova = [i for i in mie if i != x] + [y]
            per_giornata = [b - a for a, b in zip(base, scambi.valore_rosa(nuova, v, regole))]
            guadagno = scambi.totale(per_giornata, v)
            if guadagno >= scambi.SOGLIA:
                trovati.append({"esce": _giocatore(v, x), "entra": _giocatore(v, y), "guadagno": round(guadagno, 2),
                                "breve": round(sum(per_giornata), 2), "giornate": v.giornate, "_per_giornata": per_giornata})
    trovati.sort(key=lambda t: -t["guadagno"])
    # crediti: con il prezzo pagato (rimborso allo svincolo) e la quotazione di chi entra si vede se il cambio è fattibile
    for t in trovati:
        pagato = costi.get(t["esce"]["id"])
        t["rimborso"] = None if pagato is None else round(pagato * regole.rimborso_svincolo)
        t["crediti_dopo"] = None if crediti is None or t["rimborso"] is None else crediti + t["rimborso"] - t["entra"]["quotazione"]
        t["fattibile"] = None if t["crediti_dopo"] is None else t["crediti_dopo"] >= 0
        # buon senso (buon_senso.py): un cambio che i numeri promuovono ma che un allenatore non farebbe finisce tra gli scartati
        ok, motivo = buon_senso.giudica_svincolo(prof.get(t["esce"]["id"]), prof.get(t["entra"]["id"]), t.pop("_per_giornata"),
                                                 t["esce"]["ruolo"], pagato, regole.crediti_iniziali, regole.rimborso_svincolo, t["fattibile"])
        t["sensato"], t["motivo"] = ok or not con_buon_senso, motivo if con_buon_senso else ""
        if frasi.di(t["motivo"]):
            t["motivo_frase"] = frasi.di(t["motivo"])             # come tradurlo (fanta/frasi.py); il testo italiano resta in `motivo`
    scelti, scartati, conta = [], [], {}
    for t in trovati:            # varietà: lo stesso giocatore compare al massimo due volte
        if not t["sensato"]:
            if len(scartati) < MAX_SCARTATI:
                scartati.append(t)
            continue
        a, b = t["esce"]["id"], t["entra"]["id"]
        if conta.get(a, 0) >= 2 or conta.get(b, 0) >= 2:
            continue
        conta[a] = conta.get(a, 0) + 1
        conta[b] = conta.get(b, 0) + 1
        scelti.append(t)
        if len(scelti) >= massimo:
            break
    return {"squadra": s.nome, "proposte": scelti, "scartate": scartati, "svincolati": len(liberi), "crediti_residui": s.crediti_residui,
            "rimborso_ipotizzato": regole.rimborso_svincolo}


MAX_SCARTATI = 5             # cambi bocciati dal buon senso che si mostrano comunque (con il motivo) in Mercato > Consigliati


def _profili(db, regole: Regole) -> dict[int, dict]:
    """Profili per il buon senso dalle previsioni della prossima giornata (già in cache). Se non si possono avere, le regole che
    ne hanno bisogno non si applicano (si giudica solo il guadagno e i crediti)."""
    try:
        prev, _, _ = consigli.previsioni(db, regole)
    except Exception:                                   # noqa: BLE001  (db di prova, calendario assente: il mercato esce comunque)
        return {}
    return buon_senso.profili(prev)


# ---------------------------------------------------------------- oggi
VECCHIE_DOPO_ORE = 6        # probabili più vecchie di così, con la partita entro un giorno: avviso
FINESTRA_AVVISO_ORE = 24


def _giornata_lega(giornata: int | None, regole: Regole | None) -> int | None:
    return None if giornata is None or regole is None else serie_a_a_lega(giornata, regole)


def _eta_testo(minuti: int) -> str:
    if minuti < 1:
        return F("tempo.fa_meno_di_un_minuto")
    if minuti < 60:
        return F("tempo.minuti_fa", n=minuti)
    ore = minuti // 60
    if ore < 48:
        return F("tempo.ore_fa", n=ore)
    return F("tempo.giorni_fa", n=ore // 24)


def freschezza_probabili(rilevato: str | None, adesso: datetime, ore_mancanti: float | None) -> dict | None:
    """Quanto sono fresche le probabili: ora dell'ultima rilevazione in parole semplici e, se sono vecchie con la partita
    vicina, un avviso. None se non si sa quando sono state lette."""
    try:
        quando = datetime.fromisoformat(str(rilevato)[:19]) if rilevato else None
    except ValueError:
        quando = None
    if quando is None:
        return None
    minuti = max(0, int((adesso - quando).total_seconds() // 60))
    giorni = (adesso.date() - quando.date()).days
    ora = quando.strftime("%H:%M")
    if giorni <= 0:
        testo = F("probabili.oggi", ora=ora)
    elif giorni == 1:
        testo = F("probabili.ieri", ora=ora)
    else:
        testo = F("probabili.data", giorno=quando.day, mese=quando.month, ora=ora)
    vicina = ore_mancanti is not None and 0 < ore_mancanti <= FINESTRA_AVVISO_ORE
    vecchie = bool(vicina and minuti >= VECCHIE_DOPO_ORE * 60)
    avviso = None
    if vecchie:
        avviso = F("probabili.vecchie", eta=_eta_testo(minuti), tempo=F("tempo.ore", n=max(1, round(ore_mancanti))))
    eta = _eta_testo(minuti)
    # `testo`, `eta` e `avviso` sono in italiano; `frase`, `eta_frase` e `avviso_frase` dicono come tradurli (fanta/frasi.py)
    return {"aggiornate_il": quando.isoformat(sep=" ", timespec="minutes"), "minuti_fa": minuti, "eta": eta, "eta_frase": frasi.di(eta),
            "testo": testo, "frase": frasi.di(testo), "vecchie": vecchie, "avviso": avviso, "avviso_frase": frasi.di(avviso)}


def _tempi(inizio_dt: datetime | None, adesso: datetime, regole: Regole | None) -> dict:
    """Campi di Oggi sul tempo. `inizio` = prima partita; `scadenza` = quando si chiude la formazione (inizio meno i minuti della
    regola della lega); `ore_mancanti` e `iniziata` contano dalla scadenza (è quella che conta per chi schiera)."""
    scad = avvisi.scadenza(inizio_dt, regole)
    ore = None if scad is None else round((scad - adesso).total_seconds() / 3600, 1)
    return {"inizio": None if inizio_dt is None else inizio_dt.isoformat(sep=" ", timespec="minutes"),
            "scadenza": None if scad is None else scad.isoformat(sep=" ", timespec="minutes"),
            "minuti_scadenza": getattr(regole, "scadenza_minuti", 0) or 0,
            "ore_mancanti": ore, "iniziata": scad is not None and scad <= adesso}


def _partita_turno(r) -> dict:
    """Una partita di Oggi: il risultato ufficiale solo se il calendario la dà per giocata (anche senza i risultati in diretta)."""
    giocata, colonne = bool(r["giocata"]), r.keys()
    gol = lambda c: r[c] if giocata and c in colonne else None    # noqa: E731 - archivi vecchi o di prova senza le colonne dei gol
    return {"data": r["data"], "casa": r["casa"], "trasferta": r["trasferta"], "giocata": giocata,
            "gol_casa": gol("gol_casa"), "gol_trasferta": gol("gol_trasferta")}


def oggi_senza_rose(db: sqlite3.Connection, adesso: datetime | None = None, regole: Regole | None = None) -> dict:
    """Oggi per chi non ha ancora le rose: stessi campi di `oggi` ma vuoti (i client vecchi non si rompono), `senza_rose: true`,
    e la giornata con la scadenza se il calendario c'è."""
    adesso = adesso or datetime.now()
    stagione = consigli.stagione_corrente()
    giornata, partite, inizio_dt = None, [], None
    try:
        giornata = consigli.giornata_da_giocare(db, stagione, regole)
        righe = db.execute("SELECT * FROM partite WHERE stagione = ? AND giornata = ? ORDER BY data",
                           (stagione, giornata)).fetchall() if giornata else []
        partite = [_partita_turno(r) for r in righe]
        inizio_dt = prima_partita(db, stagione, giornata) if giornata else None     # regola unica (turno.py), come i promemoria
    except (sqlite3.Error, ValueError):                     # archivio non pronto: Oggi si apre lo stesso
        pass
    tempi = _tempi(inizio_dt, adesso, regole)
    for p in partite:
        p["stato"] = fasi.stato_partita(p, adesso, turno=fasi.inizio_turno(partite))
    return {"senza_rose": True, "giornata": giornata, "giornata_lega": _giornata_lega(giornata, regole)} | tempi | {
            "con_probabili": False, "probabili": None,
            "formazione": {"modulo": "–", "punteggio_atteso": None, "squadra": "", "dev": None, "intervallo": None},
            "avvisi": [], "migliori": [], "partite": partite, "miei_titolari": {},
            "fase": fasi.IN_CORSO if tempi["iniziata"] else fasi.PRIMA, "in_corso": None, "riepilogo": None, "prossima": None,
            "rinvio": None}


def oggi(db: sqlite3.Connection, regole: Regole, rose: Rose, adesso: datetime | None = None, file_scelte=None,
         file_diario=None, live_partite: dict | None = None, dal: datetime | None = None) -> dict:
    """Tutto ciò che serve per decidere oggi: scadenza, formazione in breve, cose da controllare, partite del turno; e, secondo
    la fase della giornata, la giornata in diretta o il riepilogo (fasi.py). `file_diario` e `live_partite` (la cache dei
    risultati in diretta, {(casa, trasferta): partita}) sono facoltativi: senza, i blocchi usano solo il calendario e i voti.
    `dal` (facoltativo): quando è nato l'account, per chi entra a giornata iniziata (fasi.aggiungi)."""
    adesso = adesso or datetime.now()
    s = rose.squadra(rose.mia_squadra or "")
    if not s:
        raise ValueError("Indica la tua squadra in Squadra > Squadre e rose")
    stagione = consigli.stagione_corrente()
    try:
        f = consigli.formazione(db, regole, rose)
    except ValueError:          # per esempio in un reparto nessuno gioca (rinvii): il resto della schermata si mostra lo stesso
        f = {"titolari": [], "modulo": "–", "punteggio_atteso": None, "squadra": s.nome}
    prev, giornata, con_probabili = consigli.previsioni(db, regole)
    tua_scelta, f_extra = False, {}
    scelta = scelte.leggi(stagione, giornata, file_scelte) if file_scelte else None
    if scelta and f["titolari"]:             # l'utente ha salvato la sua formazione: Oggi mostra quella, non la consigliata
        try:
            v = consigli.valuta(db, regole, rose, scelta["titolari"], None, giornata)
            schede = f.get("schede") or {}
            mie = [schede.get(str(i)) or next((g for g in f["titolari"] if g["id"] == i), None) for i in scelta["titolari"]]
            if all(mie):
                f = f | {"titolari": mie, "modulo": v["modulo"], "punteggio_atteso": v["punteggio_atteso"]}
                f_extra = {"dev": v.get("dev"), "intervallo": v.get("intervallo")}
                tua_scelta = True
        except ValueError:                   # la rosa è cambiata e la scelta non vale più: resta la consigliata
            pass
    righe = db.execute("SELECT * FROM partite WHERE stagione = ? AND giornata = ? "
                       "ORDER BY data", (stagione, giornata)).fetchall()
    partite = [_partita_turno(r) for r in righe]
    # la formazione si chiude alla PRIMA partita del turno, anche se è già stata giocata: regola unica (turno.py, avvisi.prima_partita),
    # la stessa di promemoria e copia automatica. Una partita rinviata rimasta con la data vecchia non chiude la formazione prima.
    inizio_dt = prima_partita(db, stagione, giornata)
    tempi = _tempi(inizio_dt, adesso, regole)
    ore = tempi["ore_mancanti"]

    fresche = None
    if con_probabili:
        try:
            r = db.execute("SELECT MAX(rilevato) FROM probabili WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio'",
                           (stagione, giornata)).fetchone()
            fresche = freschezza_probabili(r[0] if r else None, adesso, ore)
        except sqlite3.Error:
            fresche = None
    mie_ids = [g.id for g in s.giocatori if g.id is not None and g.id in prev.index]
    in_formazione = {g["id"] for g in f["titolari"]}
    avvisi = []
    for i in mie_ids:
        x = prev.loc[i]
        scheda = consigli.scheda_previsione(i, x)
        base = {"id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "squadra": x["squadra"]}
        if x["stato"] in ("infortunato", "squalificato"):
            avvisi.append(base | {"tipo": x["stato"], "nota": scheda["nota"], "in_formazione": i in in_formazione,
                                  "etichetta": etichette.di_avviso(x["stato"])})
            continue
        if i in in_formazione and (scheda["p_voto"] < 0.75 or x["dubbio"]):
            avvisi.append(base | {"tipo": "dubbio", "p_voto": scheda["p_voto"], "nota": scheda["nota"], "in_formazione": True,
                                  "etichetta": etichette.di_avviso("dubbio", scheda["p_voto"])})
        if x["diffidato"]:
            avvisi.append(base | {"tipo": "diffidato", "in_formazione": i in in_formazione, "etichetta": etichette.di_avviso("diffidato")})
    ordine = {"infortunato": 0, "squalificato": 1, "dubbio": 2, "diffidato": 3}
    avvisi.sort(key=lambda a: (not a["in_formazione"] and a["tipo"] in ("dubbio", "diffidato"), ordine[a["tipo"]], a["nome"]))
    migliori = sorted(f["titolari"], key=lambda g: -g["punti_attesi"])[:3]
    # i miei titolari per squadra reale: serve a evidenziare le partite dei miei giocatori nei risultati in diretta
    miei_titolari: dict[str, list] = {}
    for g in f["titolari"]:
        miei_titolari.setdefault(g["squadra"], []).append({"id": g["id"], "nome": g["nome"], "ruolo": g["ruolo"]})
    corpo = {
        "giornata": giornata, "giornata_lega": _giornata_lega(giornata, regole)} | tempi | {
        "con_probabili": con_probabili, "probabili": fresche,
        "formazione": {"modulo": f["modulo"], "punteggio_atteso": f["punteggio_atteso"], "squadra": f["squadra"],
                       "dev": f_extra.get("dev", f.get("dev")), "intervallo": f_extra.get("intervallo", f.get("intervallo")),
                       "tua_scelta": tua_scelta},
        "avvisi": avvisi, "migliori": migliori, "partite": partite, "miei_titolari": miei_titolari,
    }
    # fase della giornata (prima / in_corso / finita) e i blocchi che servono in quella fase: vedi fasi.py e docs/API.md
    corpo = fasi.aggiungi(corpo, db, regole, rose, prev, f, stagione, adesso, file_scelte, file_diario, live_partite, dal)
    # partite rinviate della giornata: la regola che vale e i miei giocatori coinvolti (rinvii.py; null se non ce ne sono)
    mie = [{"id": int(i), "nome": prev.at[i, "nome"], "ruolo": prev.at[i, "ruolo"], "squadra": prev.at[i, "squadra"]} for i in mie_ids]
    try:
        corpo["rinvio"] = rinvii.blocco_oggi(regole, stagione, giornata, corpo.get("partite") or [], mie)
    except Exception:                                   # noqa: BLE001  (Oggi si apre comunque)
        corpo["rinvio"] = None
    return corpo
