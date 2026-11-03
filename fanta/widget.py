"""Il riassunto compatto per i widget dell'iPhone (GET /api/widget): tutto in una chiamata, poche decine di righe, meno di 20 kB.

Due livelli:
- il NUCLEO (scadenza, formazione consigliata, avvisi, la mia rosa) dipende dai calcoli di sempre: se non sono pronti la
  risposta è 202 «sto calcolando», come per le altre rotte;
- le parti FACOLTATIVE (miglior scambio, miglior svincolato) si leggono SOLO se già in cache (le riempie l'app quando l'utente apre
  quelle schermate): se mancano, non compaiono e il loro nome sta in `mancano`. Il widget non fa mai partire un calcolo per loro.
Niente capitano (la lega non lo usa) e niente classifica della lega (l'app non ne ha i dati): si espone solo ciò che esiste.
"""
from __future__ import annotations

import json
import sqlite3

from . import avatar, calcolo, consigli, diario, funzioni, gestione, osservati, scelte
from .lega import Rose
from .regole import Regole

MAX_AVVISI = 6
MAX_OSSERVATI = 8
MAX_DIARIO = 5
# la fase della giornata e i suoi blocchi: stessi nomi e stessa forma di /api/oggi (calcolati da gestione.oggi -> fasi.aggiungi)
CAMPI_FASE = ("fase", "in_corso", "riepilogo", "prossima")
# tranne questi elenchi di `in_corso`: il widget mostra solo i numeri della giornata (punti fatti, previsti, chi deve giocare);
# giocatore per giocatore e cambi dalla panchina restano in /api/oggi (sono ~5 kB a giornata in corso)
SENZA_IN_CORSO = ("giocatori", "sostituzioni")
MAX_BYTE = 18000              # tetto di sicurezza della risposta (il server toglie le parti facoltative se lo supera)
TAGLI_PESO = ("scambio", "osservati")    # cosa si toglie sopra MAX_BYTE, in quest'ordine (il nome finisce in `mancano`)
SOGLIA_RIGORISTA = 0.15       # la stessa del testo «rigorista» nelle schede
# le sole funzioni che interessano ai widget (il token del widget non può leggere /api/funzioni)
FUNZIONI_WIDGET = ("live", "diario", "scambi_trova", "seguiti", "widget_extra")


def funzioni_per_widget(mostra_tutte: bool = False) -> dict[str, bool]:
    """id -> acceso, per le sole `FUNZIONI_WIDGET`, con le regole di `funzioni.acceso` (amministratore, ambiente, «Mostra tutte»)."""
    return {k: funzioni.acceso(k, mostra_tutte) for k in FUNZIONI_WIDGET}


def _g(scheda: dict, tratti: dict, *campi: str) -> dict:
    """Un giocatore in forma compatta: id (= codice calciatore, per il volto illustrato), nome, ruolo, tratti del volto se ci sono."""
    out = {"id": scheda["id"], "nome": scheda["nome"], "ruolo": scheda["ruolo"]} | {c: scheda.get(c) for c in campi if c in scheda}
    if scheda.get("squadra"):                      # il club (stesso codice di miei_titolari in /api/oggi): serve a evidenziare le partite e a vestire gli avatar
        out["squadra"] = scheda["squadra"]
    t = tratti.get(scheda["id"])
    if t:
        out["avatar"] = t
    return out


def _opzionale(mancano: list[str], nome: str, funzione):
    """Esegue una parte facoltativa senza mai far partire calcoli: se il risultato non è in cache, `nome` finisce in `mancano`."""
    gettone = calcolo.solo_cache.set(True)
    try:
        return funzione()
    except calcolo.InCalcolo:
        mancano.append(nome)
        return None
    except ValueError:
        return None
    finally:
        calcolo.solo_cache.reset(gettone)


def _tua_scelta(db, regole, rose, f: dict, giornata: int, file_scelte) -> dict | None:
    """La formazione salvata dall'utente per la giornata (titolari, modulo, punti, panchina), o None se non c'è o non vale più."""
    if not file_scelte:
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
                live_partite: dict | None = None) -> dict:
    tratti = avatar.tutti()
    o = gestione.oggi(db, regole, rose, file_scelte=file_scelte, file_diario=file_diario,   # il nucleo: può alzare InCalcolo (202)
                      live_partite=live_partite)
    f = consigli.formazione(db, regole, rose)
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
        x = consigli.scheda_previsione(g.id, prev.loc[g.id])
        mia.append(_g(x, tratti, "avversario", "in_casa", "data_partita", "stato", "percentuale", "dubbio", "diffidato", "punti_attesi",
                      "p_voto")                      # «gioca N%» come in Oggi; facoltativo: senza p_voto il campo manca
                   | {"titolare": g.id in titolari, "rigorista": x["rigori_attesi"] >= SOGLIA_RIGORISTA})
    mia.sort(key=lambda m: (m["data_partita"] is None, m["data_partita"] or "", m["nome"]))
    fuori = [m for m in mia if m["stato"] in ("infortunato", "squalificato")]

    prima = o.get("inizio")                  # la prima partita del turno (regola unica, turno.py), non la data più vecchia del calendario
    corpo = {
        "giornata": o["giornata"], "giornata_lega": o.get("giornata_lega"), "prima_partita": prima, "scadenza": o.get("scadenza") or o["inizio"], "ore_mancanti": o["ore_mancanti"],
        "iniziata": o["iniziata"], "con_probabili": o["con_probabili"],
        "squadra": f["squadra"], "crediti_residui": s.crediti_residui,
        "formazione": {"modulo": f["modulo"], "punti_attesi": f["punteggio_atteso"], "intervallo": f.get("intervallo"),
                       "titolari": [_g(t, tratti, "punti_attesi", "p_voto") for t in f["titolari"]],
                       "panchina": [t["id"] for t in f["panchina"]]}
                      | ({"tua_scelta": True, "consigliata": consigliata} if tua else {}),
        "avvisi": [_g(a, tratti, "tipo", "in_formazione", "p_voto") for a in o["avvisi"][:MAX_AVVISI]],
        "rosa": mia,
        "squalificati": [m["id"] for m in fuori if m["stato"] == "squalificato"],
        "diffidati": [m["id"] for m in mia if m["diffidato"]],
        "rigoristi": [m["id"] for m in mia if m["rigorista"]],
    }
    # fase della giornata (facoltativi, come in /api/oggi): solo quelli che ci sono, i blocchi vuoti (null) non si mandano
    corpo |= {k: o[k] for k in CAMPI_FASE if o.get(k) is not None}
    if isinstance(corpo.get("in_corso"), dict):              # una copia: il blocco di gestione.oggi non si tocca
        corpo["in_corso"] = {k: v for k, v in corpo["in_corso"].items() if k not in SENZA_IN_CORSO}

    # punti attesi contro punti fatti nelle ultime giornate (dal diario; con la formazione schierata se c'è, altrimenti la consigliata).
    # `giornata_lega` e `stagione` come in /api/diario: il widget scrive lo stesso numero dell'app (null fuori dalla stagione in corso)
    voci = diario.elenco(file_diario, regole)["giornate"][:MAX_DIARIO]
    corpo["diario"] = [{"giornata": v["giornata"], "giornata_lega": v.get("giornata_lega"), "stagione": v["stagione"],
                        "attesi": (v.get("schierata") or v["consigliata"])["atteso"],
                        "fatti": (v.get("schierata") or v["consigliata"])["reale"],
                        "intervallo": (v.get("schierata") or v["consigliata"]).get("intervallo")} for v in voci]

    ossv = []
    for i in osservati.leggi(file_osservati)[:MAX_OSSERVATI]:
        if i in prev.index:
            x = consigli.scheda_previsione(i, prev.loc[i])
            ossv.append(_g(x, tratti, "voto_atteso", "fv_atteso", "punti_attesi", "avversario", "in_casa", "data_partita", "stato",
                           "percentuale", "dubbio", "p_voto"))       # «In dubbio · gioca N%» come la rosa e Oggi (stessa scheda); facoltativi: se mancano, mancano
    corpo["osservati"] = ossv

    ultimo = db.execute("SELECT MAX(quando) FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()[0]
    corpo["dati"] = {"ultimo_aggiornamento": ultimo}

    mancano: list[str] = []

    def scambio():
        _, proposte = consigli.proposte_scambi(db, regole, rose)
        return proposte[0] if proposte else None
    p = _opzionale(mancano, "scambio", scambio)
    if p:
        corpo["scambio"] = p

    def svincolato():
        m = consigli.mercato(db, regole, rose)
        return m["proposte"][0] if m["proposte"] else None
    m = _opzionale(mancano, "svincolato", svincolato)
    if m:
        corpo["svincolato"] = {"esce": _g(m["esce"], tratti), "entra": _g(m["entra"], tratti, "quotazione"), "guadagno": m["guadagno"],
                               "fattibile": m.get("fattibile")}
    if mancano:
        corpo["mancano"] = mancano
    return corpo


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
