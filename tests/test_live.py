"""Risultati in diretta: lettura della fonte, finestre di gioco, raccoglitore con tempo e fonte finti, rotta /api/live."""
import copy
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from fanta import live, server

DATI = Path(__file__).parent / "dati"
SLUG = {"inter", "fiorentina", "lecce", "juventus", "napoli", "roma", "milan", "udinese"}


def _espn():
    return json.loads((DATI / "espn_scoreboard.json").read_text(encoding="utf8"))


def _partita(corpo, sigla):
    return next(p for p in live.leggi_espn(corpo, SLUG) if sigla in (p["casa"], p["trasferta"]))


# ---------------------------------------------------------------- lettura ESPN
def test_partita_finita_con_rigore_e_marcatori():
    p = _partita(_espn(), "fiorentina")
    assert (p["casa"], p["trasferta"], p["stato"], p["minuto"]) == ("inter", "fiorentina", "finita", None)
    assert (p["gol_casa"], p["gol_trasferta"]) == (2, 1)
    assert p["data"] == "2026-10-25 12:30"                       # 11:30 UTC = 12:30 italiane (ora solare)
    gol = [e for e in p["eventi"] if e["tipo"] in ("gol", "rigore")]
    assert len(gol) == 3 and any(e["tipo"] == "rigore" and e["chi"] and e["squadra"] == "casa" for e in gol)
    assert sum(e["squadra"] == "casa" for e in gol) == 2 and sum(e["squadra"] == "trasferta" for e in gol) == 1
    assert {e["tipo"] for e in p["eventi"]} <= {"gol", "rigore", "rosso", "autogol"}                  # niente gialli


def test_espulsione_e_sei_gol():
    juve = _partita(_espn(), "juventus")
    assert [e["tipo"] for e in juve["eventi"] if e["tipo"] == "rosso"] == ["rosso"] and juve["gol_trasferta"] == 2
    na = _partita(_espn(), "napoli")
    assert na["gol_casa"] + na["gol_trasferta"] == 6
    assert sum(e["tipo"] in ("gol", "rigore") for e in na["eventi"]) == 6


def _con_stato(nome, stato, orologio, punteggio=("1", "0")):
    c = copy.deepcopy(_espn())
    comp = c["events"][0]["competitions"][0]
    comp["status"]["type"]["name"] = nome
    comp["status"]["type"]["state"] = stato
    comp["status"]["displayClock"] = orologio
    for k, g in zip(comp["competitors"], punteggio):
        k["score"] = g
    comp["details"] = []
    return c


@pytest.mark.parametrize("nome,stato_fonte,orologio,atteso,minuto", [
    ("STATUS_SCHEDULED", "pre", "0'", "da_giocare", None),
    ("STATUS_FIRST_HALF", "in", "34'", "primo_tempo", "34'"),
    ("STATUS_HALFTIME", "in", "45'", "intervallo", None),
    ("STATUS_SECOND_HALF", "in", "67'", "secondo_tempo", "67'"),
    ("STATUS_SECOND_HALF", "in", "90'+3'", "secondo_tempo", "90'+3'"),
    ("STATUS_FULL_TIME", "post", "90'", "finita", None),
    ("STATUS_POSTPONED", "post", "0'", "rinviata", None),
    ("STATUS_SUSPENDED", "in", "50'", "sospesa", None),
    ("STATUS_MAI_VISTO", "in", "12'", "in_corso", "12'"),
])
def test_stati_della_fonte(nome, stato_fonte, orologio, atteso, minuto):
    p = live.leggi_espn(_con_stato(nome, stato_fonte, orologio), SLUG)[0]
    assert (p["stato"], p["minuto"]) == (atteso, minuto)
    assert p["stato"] in live.STATI


def test_squadra_sconosciuta_o_risposta_strana_non_rompe_niente():
    assert live.leggi_espn(_espn(), {"inter"}) == []             # nessuna partita con due squadre note
    assert live.leggi_espn({}, SLUG) == [] and live.leggi_espn({"events": [{"x": 1}, None]}, SLUG) == []
    c = _espn()
    c["events"].insert(0, {"competitions": [{}]})
    assert len(live.leggi_espn(c, SLUG)) == 3


def test_autogol_va_alla_squadra_che_fa_tornare_il_punteggio():
    c = _con_stato("STATUS_FULL_TIME", "post", "90'", ("1", "0"))
    comp = c["events"][0]["competitions"][0]
    casa = next(k for k in comp["competitors"] if k["homeAway"] == "home")["team"]["id"]
    trasf = next(k for k in comp["competitors"] if k["homeAway"] == "away")["team"]["id"]
    # il giocatore della squadra in trasferta segna contro di sé: il gol conta per la casa, che sta 1-0
    ev = {"type": {"id": "1", "text": "Own Goal"}, "clock": {"displayValue": "10'"}, "team": {"id": trasf}, "scoringPlay": True,
          "ownGoal": True, "redCard": False, "yellowCard": False, "penaltyKick": False, "athletesInvolved": [{"displayName": "Tizio"}]}
    comp["details"] = [ev]
    p = live.leggi_espn(c, SLUG)[0]
    assert [(e["tipo"], e["squadra"]) for e in p["eventi"]] == [("autogol", "casa")]
    comp["details"][0]["team"]["id"] = casa                       # la fonte ha già il lato giusto: resta com'è
    assert live.leggi_espn(c, SLUG)[0]["eventi"][0]["squadra"] == "casa"


# ---------------------------------------------------------------- finestre
def test_finestra_di_gioco():
    d = "2026-10-31 15:00"
    f = lambda h, m: live.in_finestra(d, datetime(2026, 10, 31, h, m))
    assert not f(14, 49) and f(14, 50) and f(15, 0) and f(17, 0)
    assert f(17, 10) and not f(17, 11)                            # 15:00 + 110' + 20'
    assert not live.in_finestra(None, datetime(2026, 10, 31, 15, 0)) and not live.in_finestra("boh", datetime(2026, 10, 31, 15, 0))


def test_giorno_da_chiedere_alla_fonte():
    assert live.data_per_fonte("2026-10-31 20:45") == "20261031" and live.data_per_fonte("2026-10-31 00:30") == "20261030"
    assert live.data_per_fonte("") is None


# ---------------------------------------------------------------- il raccoglitore, con tempo e fonte finti
class Orologio:
    def __init__(self, inizio="2026-10-31 14:00"):
        self.t = datetime.fromisoformat(inizio)
        self.mono = 1000.0

    def avanza(self, secondi):
        self.t += timedelta(seconds=secondi)
        self.mono += secondi


class FonteFinta:
    def __init__(self, orologio, risposte=None):
        self.o, self.url, self.quando, self.risposte = orologio, [], [], risposte or {}
        self.errore = None

    def __call__(self, url):
        self.url.append(url)
        self.quando.append(self.o.mono)
        if self.errore:
            raise self.errore
        return self.risposte.get("html") if "fantacalcio" in url else json.dumps(self.corpo())

    def corpo(self):
        return self.risposte["json"]


def _calendario():
    return [{"data": "2026-10-31 15:00", "casa": "inter", "trasferta": "fiorentina", "giornata": 10, "stagione": "2026-27"},
            {"data": "2026-10-31 18:00", "casa": "lecce", "trasferta": "juventus", "giornata": 10, "stagione": "2026-27"}]


def _corpo(stato1="STATUS_FIRST_HALF", stato2="STATUS_SCHEDULED", minuto="10'"):
    c = _con_stato(stato1, "in", minuto)
    e2 = copy.deepcopy(c["events"][1])
    e2["competitions"][0]["status"]["type"].update(name=stato2, state="pre")
    for k, g in zip(e2["competitions"][0]["competitors"], ("0", "0")):
        k["score"] = g
    e2["competitions"][0]["details"] = []
    c["events"] = [c["events"][0], e2]
    for e, d in zip(c["events"], ("2026-10-31T14:00Z", "2026-10-31T17:00Z")):
        e["date"] = e["competitions"][0]["date"] = d
    return c


def _racc(o, fonte, cal=None):
    cal = _calendario() if cal is None else cal
    return live.Raccoglitore(lambda: cal, scarica=fonte, adesso=lambda: o.t, orologio=lambda: o.mono)


def test_fuori_finestra_non_fa_nessuna_richiesta():
    o = Orologio("2026-10-31 09:00")
    f = FonteFinta(o, {"json": _corpo()})
    r = _racc(o, f)
    for _ in range(100):
        assert r.passo() == "ferma"
        o.avanza(15)
    assert f.url == [] and r.richieste == 0 and r.istantanea()["partite"] == {} and r.fonte is None


def test_dentro_la_finestra_una_richiesta_al_minuto_e_cache():
    o = Orologio("2026-10-31 14:50")
    f = FonteFinta(o, {"json": _corpo()})
    r = _racc(o, f)
    assert r.passo() == "ok" and len(f.url) == 1 and "dates=20261031" in f.url[0]
    assert r.fonte == "espn" and r.aggiornato_il == "2026-10-31 14:50:00"
    assert list(r.istantanea()["partite"]) == [("inter", "fiorentina"), ("lecce", "juventus")], list(r.istantanea()["partite"])
    snap = r.istantanea()["partite"][("inter", "fiorentina")]
    assert snap["stato"] == "primo_tempo" and snap["minuto"] == "10'"
    assert r.in_gioco()
    for _ in range(3):                                            # troppo presto: nessuna richiesta
        o.avanza(15)
        assert r.passo() == "attesa"
    o.avanza(15)
    assert r.passo() == "ok" and len(f.url) == 2


def test_mai_piu_di_una_richiesta_al_minuto_per_tutto_il_giorno():
    o = Orologio("2026-10-31 08:00")
    f = FonteFinta(o, {"json": _corpo()})
    r = _racc(o, f)
    for _ in range(12 * 4 * 60):                                  # 12 ore, un controllo ogni 15 secondi
        r.passo()
        o.avanza(15)
    assert all(b - a >= 60 for a, b in zip(f.quando, f.quando[1:]))
    assert 0 < len(f.url) <= 12 * 60 // 1


def test_smette_quando_tutte_le_partite_sono_finite():
    o = Orologio("2026-10-31 15:20")
    cal = [_calendario()[0]]
    f = FonteFinta(o, {"json": _corpo("STATUS_FULL_TIME")})
    r = _racc(o, f, cal)
    assert r.passo() == "ok" and not r.in_gioco()
    o.avanza(120)
    assert r.passo() == "ferma" and len(f.url) == 1               # segnata finita: basta chiedere


def test_errori_aspettano_sempre_di_piu_poi_il_ripiego():
    o = Orologio("2026-10-31 15:05")
    f = FonteFinta(o, {"json": _corpo(), "html": (DATI / "calendario_1.html").read_text(encoding="utf8")})
    f.errore = OSError("rete giu")
    r = _racc(o, f)
    attese = []
    for _ in range(2):
        assert r.passo() == "errore"
        attese.append(r.prossima - o.mono)
        o.avanza(r.prossima - o.mono)
    assert attese == [60, 120]
    assert r.passo() == "errore"                                  # terzo errore: da qui in poi il ripiego
    assert r.prossima - o.mono == 60 and r.ripiego_fino > o.mono
    o.avanza(60)
    f.errore = None
    assert r.passo() == "ok" and "fantacalcio" in f.url[-1]       # calendario della giornata 10, la pagina d'esempio è la 1
    o.avanza(600)
    r.passo()
    assert "espn" in f.url[-1]                                    # finito il periodo, si torna alla fonte principale
    assert all(b - a >= 60 for a, b in zip(f.quando, f.quando[1:]))


def test_ripiego_legge_punteggi_del_calendario():
    html = (DATI / "calendario_1.html").read_text(encoding="utf8")
    p = live.leggi_ripiego(html, 1, "2026-27")
    assert len(p) == 10 and all(x["stato"] in live.STATI and x["eventi"] == [] and x["minuto"] is None for x in p)
    assert live.leggi_ripiego(html, 2, "2026-27") == []
    # una partita con stato sconosciuto e punteggio = in corso
    html2 = html.replace('data-match-status="0"', 'data-match-status="2"', 1)
    stati = [x["stato"] for x in live.leggi_ripiego(html2, 1, "2026-27")]
    assert stati.count("in_corso") + stati.count("da_giocare") + stati.count("finita") == 10


def test_il_ripiego_non_cancella_i_marcatori():
    o = Orologio("2026-10-31 15:30")
    f = FonteFinta(o, {"json": _corpo()})
    f.risposte["json"]["events"][0]["competitions"][0]["details"] = _espn()["events"][0]["competitions"][0]["details"][:1]
    r = _racc(o, f)
    r.passo()
    k = next(iter(r.istantanea()["partite"]))
    assert r.istantanea()["partite"][k]["eventi"]
    r._unisci([{"casa": k[0], "trasferta": k[1], "data": "2026-10-31 15:00", "stato": "in_corso", "minuto": None,
                "gol_casa": 1, "gol_trasferta": 0, "eventi": []}], "fantacalcio", o.t)
    assert r.istantanea()["partite"][k]["eventi"] and r.fonte == "fantacalcio"


def test_calendario_da_database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (data TEXT, casa TEXT, trasferta TEXT, giornata INT, stagione TEXT, giocata INT, gol_casa INT, gol_trasferta INT)")
    for d in ("2026-10-29 20:45", "2026-10-30 20:45", "2026-10-31 15:00", "2026-11-01 15:00", "2026-11-02 15:00"):
        db.execute("INSERT INTO partite VALUES (?, 'a', 'b', 10, '2026-27', 0, NULL, NULL)", (d,))
    assert [p["data"][:10] for p in live.calendario_da_db(db, datetime(2026, 10, 31, 12, 0))] == ["2026-10-30", "2026-10-31", "2026-11-01"]


# ---------------------------------------------------------------- la risposta e la rotta
def _db_prova():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (id INTEGER PRIMARY KEY, stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, "
               "gol_casa INT, gol_trasferta INT, giocata INT)")
    s = server.consigli.stagione_corrente()
    righe = [("2026-10-24 18:00", "napoli", "roma", 3, 3, 1)] + [(f"2026-10-31 {15 + i}:00", c, t, None, None, 0) for i, (c, t) in
                                                                    enumerate([("inter", "fiorentina"), ("lecce", "juventus"), ("milan", "udinese"),
                                                                               ("torino", "genoa"), ("cagliari", "como"), ("pisa", "parma")])]
    for i, (d, c, t, gc, gt, g) in enumerate(righe):
        db.execute("INSERT INTO partite VALUES (?, ?, 10, ?, ?, ?, ?, ?, ?)", (i, s, d, c, t, gc, gt, g))
    return db


@pytest.fixture
def cliente_live(monkeypatch):
    db = _db_prova()
    monkeypatch.setattr(server, "_db", lambda: NS(execute=db.execute, close=lambda: None))
    monkeypatch.setattr(server.account, "multiutente", lambda: False)
    o = Orologio("2026-10-31 15:20")
    # la giornata «in corso» si sceglie con la stessa ora finta: con l'ora vera le partite di prova sarebbero già vecchie
    monkeypatch.setattr(server.consigli, "_adesso", lambda: datetime(2026, 10, 31, 15, 20))
    f = FonteFinta(o, {"json": _corpo()})
    r = _racc(o, f)
    monkeypatch.setattr(live, "unico", r)
    return TestClient(server.app), r, f


def test_rotta_senza_dati_in_cache_risponde_dal_database(monkeypatch, cliente_live):
    c, r, f = cliente_live
    j = c.get("/api/live").json()
    assert j["aggiornato_il"] is None and j["fonte"] is None and j["in_corso"] == 0
    assert len(j["partite"]) == 7 and [p["stato"] for p in j["partite"]].count("da_giocare") == 6
    assert j["partite"][0]["stato"] == "finita" and (j["partite"][0]["gol_casa"], j["partite"][0]["gol_trasferta"]) == (3, 3)
    assert f.url == []                                            # leggere non fa partire richieste


def test_rotta_con_partita_in_corso_etag_e_dimensione(cliente_live):
    c, r, f = cliente_live
    r.passo()
    resp = c.get("/api/live")
    j = resp.json()
    live_p = next(p for p in j["partite"] if p["casa"] == "inter")
    assert j["in_corso"] == 1 and j["fonte"] == "espn" and live_p["stato"] == "primo_tempo" and live_p["minuto"] == "10'"
    assert resp.headers["cache-control"] == "private, max-age=20" and len(resp.content) < 5000
    n = len(f.url)
    for _ in range(20):                                           # 20 letture: nessuna richiesta esterna in più
        c.get("/api/live")
    assert len(f.url) == n
    r2 = c.get("/api/live", headers={"If-None-Match": resp.headers["etag"]})
    assert r2.status_code == 304 and not r2.content


def test_assist_e_rigore_sbagliato_dalla_fonte():
    c = _espn()
    gol = c["events"][0]["competitions"][0]["details"]
    d = next(x for x in gol if x.get("scoringPlay") and not x.get("penaltyKick") and not x.get("ownGoal"))
    d["athletesInvolved"].append({"shortName": "Ferguson"})
    errore = copy.deepcopy(d) | {"scoringPlay": False, "penaltyKick": True}
    gol.append(errore)
    ev = live.leggi_espn(c, SLUG)[0]["eventi"]
    assert any(e["tipo"] == "gol" and e.get("assist") == "Ferguson" for e in ev)
    assert any(e["tipo"] == "rigore_sbagliato" and "assist" not in e for e in ev)


def test_risposta_resta_sotto_il_tetto_senza_gialli_anche_con_tanti_eventi():
    ev = [{"tipo": "giallo" if i % 2 else "gol", "minuto": f"{i}'", "squadra": "casa", "chi": "Nome Cognome"} for i in range(20)]
    p = {"casa": "a", "trasferta": "b", "data": "2026-10-31 15:00", "stato": "finita", "minuto": None, "gol_casa": 9, "gol_trasferta": 9, "eventi": ev}
    corpo = live._stringi({"aggiornato_il": "x", "fonte": "espn", "in_corso": 0, "partite": [dict(p, casa=f"s{i}") for i in range(10)]})
    assert len(json.dumps(corpo, separators=(",", ":"))) <= live.MAX_BYTE
    assert all(e["tipo"] != "giallo" for e in corpo["partite"][0]["eventi"])
