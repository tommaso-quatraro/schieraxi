"""Il riassunto compatto per i widget dell'iPhone (GET /api/widget): tutto in una chiamata, poche decine di righe, meno di 20 kB.

Due livelli:
- il NUCLEO (scadenza, formazione consigliata, avvisi, la mia rosa) dipende dai calcoli di sempre: se non sono pronti la
  risposta è 202 «sto calcolando», come per le altre rotte;
- le parti FACOLTATIVE (miglior scambio, miglior svincolato) si leggono SOLO se già in cache (le riempie l'app quando l'utente apre
  quelle schermate): se mancano, non compaiono e il loro nome sta in `mancano`. Il widget non fa mai partire un calcolo per loro.
  Il miglior svincolato c'è solo se «Cambi consigliati» è accesa per l'utente: spenta, non si legge nemmeno (né in `mancano`, #797).
  Allo stesso modo il miglior scambio c'è solo se «Scambi: trova» è accesa per l'utente (#803).
Niente capitano (la lega non lo usa) e niente classifica della lega (l'app non ne ha i dati): si espone solo ciò che esiste.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from . import avatar, calcolo, consigli, diario, fasi, funzioni, gestione, osservati, scelte, versioni
from .lega import Rose
from .regole import Regole

MAX_AVVISI = 6
MAX_OSSERVATI = 8
MAX_DIARIO = 5
# la fase della giornata e i suoi blocchi: stessi nomi e stessa forma di /api/oggi (calcolati da gestione.oggi -> fasi.aggiungi);
# `senza_formazione` (#651): chi è entrato a giornata iniziata senza formazione, al posto di `in_corso` (niente punti finti)
CAMPI_FASE = ("fase", "in_corso", "riepilogo", "prossima", "senza_formazione")
# tranne questi elenchi di `in_corso`: il widget mostra solo i numeri della giornata (punti fatti, previsti, chi deve giocare);
# giocatore per giocatore e cambi dalla panchina restano in /api/oggi (sono ~5 kB a giornata in corso)
SENZA_IN_CORSO = ("giocatori", "sostituzioni")
MAX_BYTE = 18000              # tetto di sicurezza della risposta (il server toglie le parti facoltative se lo supera)
TAGLI_PESO = ("scambio", "osservati")    # cosa si toglie sopra MAX_BYTE, in quest'ordine (il nome finisce in `mancano`)
# le sole funzioni che interessano ai widget (il token del widget non può leggere /api/funzioni)
FUNZIONI_WIDGET = ("live", "diario", "scambi_trova", "seguiti", "widget_extra")


def funzioni_per_widget(mostra_tutte: bool = False, amministratore: bool = False) -> dict[str, bool]:
    """id -> acceso, per le sole `FUNZIONI_WIDGET`, con le regole di `funzioni.acceso` (scelte dell'amministratore, ambiente,
    «Mostra tutte» e ruolo di chi chiede): gli stessi valori di GET /api/funzioni per lo stesso utente (#803)."""
    return {k: funzioni.acceso(k, mostra_tutte, amministratore=amministratore) for k in FUNZIONI_WIDGET}


def _g(scheda: dict, tratti: dict, *campi: str) -> dict:
    """Un giocatore in forma compatta: id (= codice calciatore, per il volto illustrato), nome, ruolo, tratti del volto se ci sono."""
    out = {"id": scheda["id"], "nome": scheda["nome"], "ruolo": scheda["ruolo"]} | {c: scheda.get(c) for c in campi if c in scheda}
    if scheda.get("squadra"):                      # il club (stesso codice di miei_titolari in /api/oggi): serve a evidenziare le partite e a vestire gli avatar
        out["squadra"] = scheda["squadra"]
    t = tratti.get(scheda["id"])
    if t:
        out["avatar"] = t
    return out


def _titolari_prima(avvisi: list[dict]) -> list[dict]:
    """Gli avvisi di Oggi con quelli dei titolari in testa, per il taglio a MAX_AVVISI (26/11/2026): Oggi mette prima infortunati e
    squalificati anche fuori formazione, e con tanti di loro i dubbi dei titolari restavano fuori dai primi sei. `sorted` è stabile:
    dentro i due gruppi resta l'ordine di Oggi."""
    return sorted(avvisi, key=lambda a: not a.get("in_formazione"))


def _opzionale(mancano: list[str], nome: str, funzione):
    """Esegue una parte facoltativa senza mai far partire calcoli: se il risultato non è in cache, `nome` finisce in `mancano`.
    Senza aspettare nemmeno un calcolo già in corso (#907): una parte facoltativa non rallenta Oggi né il widget."""
    gettone = calcolo.solo_cache.set(True)
    try:
        with calcolo.senza_attesa():
            return funzione()
    except calcolo.InCalcolo:
        mancano.append(nome)
        return None
    except ValueError:
        return None
    finally:
        calcolo.solo_cache.reset(gettone)


def _tua_scelta(db, regole, rose, f: dict, giornata: int, file_scelte) -> dict | None:
    """La formazione salvata dall'utente per la giornata (titolari, modulo, punti, panchina), o None se non c'è o non vale più.
    Senza consigliata (rosa che non basta) None subito, come Oggi: `valuta` richiederebbe la consigliata (#651)."""
    if not file_scelte or not f["titolari"]:
        return None
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte)
    if not scelta:
        return None
    try:
        v = consigli.valuta(db, regole, rose, scelta["titolari"], None, giornata)
    except ValueError:                                       # la rosa è cambiata: resta la consigliata
        return None
    schede = f.get("schede") or {}
    mie = [schede.get(str(i)) for i in scelta["titolari"]]
    pan = [schede.get(str(i)) for i in v["panchina"]]
    if not all(mie) or not all(pan):
        return None
    return {"titolari": mie, "panchina": pan, "modulo": v["modulo"], "punteggio_atteso": v["punteggio_atteso"],
            "intervallo": v.get("intervallo")}


def costruisci(db: sqlite3.Connection, regole: Regole, rose: Rose, file_diario, file_osservati, file_scelte=None,
                live_partite: dict | None = None, dal: datetime | None = None, mercato: bool = True,
                scambi_trova: bool = True) -> dict:
    """`dal` (facoltativo): quando è nato l'account, come in /api/oggi: chi è entrato a giornata iniziata senza formazione ha
    `senza_formazione` e la `prossima` giornata invece dei punti di una formazione che non ha schierato (#651).
    `mercato`: se «Cambi consigliati» è accesa per l'utente (lo decide il server con `funzioni.acceso`); spenta, niente `svincolato` (#797).
    `scambi_trova`: lo stesso per «Scambi: trova»; spenta, niente `scambio` (#803)."""
    tratti = avatar.tutti()
    # il nucleo: può alzare InCalcolo (202). La consigliata si chiede UNA volta e la usa anche Oggi: l'errore di un calcolo in coda
    # arriva una volta sola, e una seconda richiesta lo rimetteva in coda («sto calcolando» per sempre con una rosa che non basta, #651)
    f = gestione.formazione_di_oggi(db, regole, rose)
    o = gestione.oggi(db, regole, rose, file_scelte=file_scelte, file_diario=file_diario, live_partite=live_partite, dal=dal,
                      formazione=f)
    if o.get("campionato_finito"):
        return _campionato_finito(db, regole, rose, o, file_diario)
    prev, giornata, _ = consigli.previsioni(db, regole)
    consigliata = {"modulo": f["modulo"], "punti_attesi": f["punteggio_atteso"]}
    tua = _tua_scelta(db, regole, rose, f, giornata, file_scelte)
    if tua:                                                  # l'utente ha salvato la sua formazione: il widget mostra quella
        f = f | tua
    s = rose.squadra(rose.mia_squadra or "")
    titolari = {g["id"] for g in f["titolari"]}

    mia = []
    for g in s.giocatori:
        if g.id is None or g.id not in prev.index:
            continue
        x = consigli.scheda_di(prev, g.id)
        mia.append(_g(x, tratti, "avversario", "in_casa", "data_partita", "stato", "percentuale", "dubbio", "diffidato", "punti_attesi",
                      "p_voto")                      # «gioca N%» come in Oggi; facoltativo: senza p_voto il campo manca
                   | {"titolare": g.id in titolari, "rigorista": consigli.rigorista(prev.loc[g.id])})      # la regola della scheda
    mia.sort(key=lambda m: (m["data_partita"] is None, m["data_partita"] or "", m["nome"]))
    fuori = [m for m in mia if m["stato"] in ("infortunato", "squalificato")]

    prima = o.get("inizio")                  # la prima partita del turno (regola unica, turno.py), non la data più vecchia del calendario
    corpo = {
        "giornata": o["giornata"], "giornata_lega": o.get("giornata_lega"), "prima_partita": prima, "scadenza": o.get("scadenza") or o["inizio"], "ore_mancanti": o["ore_mancanti"],
        "iniziata": o["iniziata"], "con_probabili": o["con_probabili"],
        "squadra": f["squadra"], "crediti_residui": s.crediti_residui,
        "formazione": {"modulo": f["modulo"], "punti_attesi": f["punteggio_atteso"], "intervallo": f.get("intervallo"),
                       # `fv_atteso`: il numero che l'app mostra accanto al titolare (#240); `punti_attesi` resta per i widget già installati
                       "titolari": [_g(t, tratti, "punti_attesi", "p_voto", "fv_atteso") for t in f["titolari"]],
                       "panchina": [t["id"] for t in f["panchina"]]}
                      | ({"tua_scelta": True, "consigliata": consigliata} if tua else {}),
        # `etichetta` (facoltativa): la stessa di Oggi e della Formazione, da mostrare al posto delle parole composte dal `tipo` (#282)
        "avvisi": [_g(a, tratti, "tipo", "in_formazione", "p_voto", "etichetta") for a in _titolari_prima(o["avvisi"])[:MAX_AVVISI]],
        # quanti avvisi dei titolari ci sono, contati su tutti e non sui primi MAX_AVVISI: il numero di «Da controllare» (26/11/2026)
        "da_controllare": sum(1 for a in o["avvisi"] if a.get("in_formazione")),
        "rosa": mia,
        "squalificati": [m["id"] for m in fuori if m["stato"] == "squalificato"],
        "diffidati": [m["id"] for m in mia if m["diffidato"]],
        "rigoristi": [m["id"] for m in mia if m["rigorista"]],
    }
    # fase della giornata (facoltativi, come in /api/oggi): solo quelli che ci sono, i blocchi vuoti (null) non si mandano
    corpo |= {k: o[k] for k in CAMPI_FASE if o.get(k) is not None}
    if isinstance(corpo.get("in_corso"), dict):              # una copia: il blocco di gestione.oggi non si tocca
        corpo["in_corso"] = {k: v for k, v in corpo["in_corso"].items() if k not in SENZA_IN_CORSO}
        # la riga sotto i punti in breve per il widget medio, solo quando quella di Oggi ha i nomi di chi aspetta il recupero
        # (#911); `situazione` resta com'è per i widget già installati
        breve = fasi.situazione_breve(corpo["in_corso"].get("situazione_frase"))
        if breve:
            corpo["in_corso"] |= {"situazione_breve": breve, "situazione_breve_frase": breve.json()}

    corpo["diario"] = _diario(file_diario, regole)

    ossv = []
    for i in osservati.leggi(file_osservati)[:MAX_OSSERVATI]:
        if i in prev.index:
            x = consigli.scheda_di(prev, i)
            ossv.append(_g(x, tratti, "voto_atteso", "fv_atteso", "punti_attesi", "avversario", "in_casa", "data_partita", "stato",
                           "percentuale", "dubbio", "p_voto"))       # «In dubbio · gioca N%» come la rosa e Oggi (stessa scheda); facoltativi: se mancano, mancano
    corpo["osservati"] = ossv
    corpo["dati"] = _dati(db)

    mancano: list[str] = []

    def scambio():
        _, proposte = consigli.proposte_scambi(db, regole, rose)
        return proposte[0] if proposte else None
    p = _opzionale(mancano, "scambio", scambio) if scambi_trova else None
    if p:
        corpo["scambio"] = p

    def svincolato():
        m = consigli.mercato(db, regole, rose)
        return m["proposte"][0] if m["proposte"] else None
    m = _opzionale(mancano, "svincolato", svincolato) if mercato else None
    if m:
        corpo["svincolato"] = {"esce": _g(m["esce"], tratti), "entra": _g(m["entra"], tratti, "quotazione"), "guadagno": m["guadagno"],
                               "fattibile": m.get("fattibile")}
    if mancano:
        corpo["mancano"] = mancano
    return corpo


def _diario(file_diario, regole: Regole) -> list[dict]:
    """Punti attesi contro punti fatti nelle ultime giornate (dal diario; con la formazione schierata se c'è, altrimenti la
    consigliata). `giornata_lega` e `stagione` come in /api/diario: il widget scrive lo stesso numero dell'app (null fuori dalla
    stagione in corso)."""
    voci = diario.elenco(file_diario, regole)["giornate"][:MAX_DIARIO]
    return [{"giornata": v["giornata"], "giornata_lega": v.get("giornata_lega"), "stagione": v["stagione"],
             "attesi": (v.get("schierata") or v["consigliata"])["atteso"],
             "fatti": (v.get("schierata") or v["consigliata"])["reale"],
             "intervallo": (v.get("schierata") or v["consigliata"]).get("intervallo")} for v in voci]


def _dati(db: sqlite3.Connection) -> dict:
    return {"ultimo_aggiornamento": db.execute("SELECT MAX(quando) FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()[0]}


def _campionato_finito(db: sqlite3.Connection, regole: Regole, rose: Rose, o: dict, file_diario) -> dict:
    """Il widget a campionato finito (#656), coerente con Oggi (`gestione.oggi_campionato_finito`): stessi campi di sempre, vuoti
    dove servirebbe una giornata (formazione, avvisi, rosa, seguiti), `campionato_finito` e la fase con i suoi blocchi come in Oggi
    (il `riepilogo` dell'ultima giornata nelle 48 ore), le ultime giornate del diario. Prima: 400 «calendario non ancora disponibile»."""
    s = rose.squadra(rose.mia_squadra or "")
    corpo = {"giornata": None, "giornata_lega": None, "prima_partita": None, "scadenza": None, "ore_mancanti": None, "iniziata": False,
             "con_probabili": False, "squadra": s.nome, "crediti_residui": s.crediti_residui,
             "formazione": {"modulo": "–", "punti_attesi": None, "intervallo": None, "titolari": [], "panchina": []},
             "avvisi": [], "rosa": [], "squalificati": [], "diffidati": [], "rigoristi": [],
             "campionato_finito": o["campionato_finito"]}
    corpo |= {k: o[k] for k in CAMPI_FASE if o.get(k) is not None}
    corpo["diario"] = _diario(file_diario, regole)
    corpo["osservati"] = []
    corpo["dati"] = _dati(db)
    return corpo


def etag(corpo: dict) -> str:
    """L'ETag della risposta: cambia solo quando cambia qualcosa che il widget mostra (#651). Senza i campi che cambiano soltanto
    con l'orologio e che il client ricava da altri campi: `ore_mancanti` (decimi d'ora, da `scadenza`) e `prossima.prepara_da`
    (l'ora di adesso quando si può già preparare, altrimenti `scadenza` meno le ore delle probabili). Restano nel corpo."""
    fermo = {k: v for k, v in corpo.items() if k != "ore_mancanti"}
    if isinstance(fermo.get("prossima"), dict):
        fermo["prossima"] = {k: v for k, v in fermo["prossima"].items() if k != "prepara_da"}
    return versioni.etag_dati(fermo)


def peso(corpo: dict) -> int:
    """La misura del tetto: il JSON con gli spazi e i caratteri accentati così come sono (la stessa misura della sentinella)."""
    return len(json.dumps(corpo, ensure_ascii=False))


def entro_il_peso(corpo: dict) -> dict:
    """Rete di sicurezza sulla dimensione: sopra MAX_BYTE toglie i blocchi di TAGLI_PESO, uno alla volta e solo finché serve, e
    ne scrive il nome in `mancano`, così il widget sa che mancano invece di perderli in silenzio. Un blocco vuoto o già
    assente (per esempio lo scambio non in cache, già in `mancano`) non si tocca."""
    for chiave in TAGLI_PESO:
        if corpo.get(chiave) and peso(corpo) > MAX_BYTE:
            del corpo[chiave]
            corpo["mancano"] = [*corpo.get("mancano", []), chiave]
    return corpo
