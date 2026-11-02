"""Il risultato visto in diretta resta: cache su file (sopravvive ai riavvii), partita seguita finché la fonte dice «finita»
(con un tetto), il risultato ufficiale del calendario vince. Caso vero: Juventus-Napoli del 1/11, servizio riavviato alle 23:00
(fuori dalla finestra di gioco): fino al giro di aggiornamento del mattino la partita era senza punteggio."""
import json
import sqlite3
from datetime import datetime, timedelta

from fanta import live

CAL = [{"data": "2026-11-01 20:45", "casa": "juventus", "trasferta": "napoli", "giornata": 10, "stagione": "2026-27",
        "giocata": 0, "gol_casa": None, "gol_trasferta": None}]


def _espn(stato="STATUS_FULL_TIME", gruppo="post", gol=("2", "0"), orologio="90"):
    return {"events": [{"date": "2026-11-01T19:45Z", "competitions": [{
        "status": {"type": {"name": stato, "state": gruppo}, "displayClock": orologio},
        "competitors": [{"homeAway": "home", "score": gol[0], "team": {"id": "1", "displayName": "Juventus"}},
                        {"homeAway": "away", "score": gol[1], "team": {"id": "2", "displayName": "Napoli"}}],
        "details": [{"scoringPlay": True, "clock": {"displayValue": "12"}, "team": {"id": "1"},
                     "athletesInvolved": [{"shortName": "D. Vlahovic"}]}]}]}]}


class Mondo:
    """Ora italiana, orologio monotono e fonte finta che conta le richieste."""
    def __init__(self, ora, corpo=None):
        self.t, self.mono, self.corpo, self.url = datetime.fromisoformat(ora), 1000.0, corpo or _espn(), []

    def avanza(self, secondi):
        self.t += timedelta(seconds=secondi)
        self.mono += secondi

    def scarica(self, url):
        self.url.append(url)
        return json.dumps(self.corpo)

    def raccoglitore(self, file=None, cal=None):
        cal = CAL if cal is None else cal
        return live.Raccoglitore(lambda: cal, scarica=self.scarica, adesso=lambda: self.t, orologio=lambda: self.mono, file=file)


def _juve(r):
    return live.risposta(r, CAL)["partite"][0]


def test_il_risultato_finale_sopravvive_al_riavvio(tmp_path):
    f = tmp_path / "live.json"
    m = Mondo("2026-11-01 22:50")
    assert m.raccoglitore(f).passo() == "ok" and f.exists()
    m.avanza(600)                                                    # 23:00: riavvio, fuori dalla finestra di gioco
    r2 = m.raccoglitore(f)
    assert r2.passo() == "ferma" and len(m.url) == 1                 # nessuna richiesta in più: il risultato c'è già
    p = _juve(r2)
    assert (p["stato"], p["gol_casa"], p["gol_trasferta"]) == ("finita", 2, 0) and p["eventi"][0]["chi"] == "D. Vlahovic"
    assert r2.aggiornato_il == "2026-11-01 22:50:00" and r2.fonte == "espn"


def test_formato_del_file(tmp_path):
    f = tmp_path / "live.json"
    m = Mondo("2026-11-01 22:50")
    m.raccoglitore(f).passo()
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["versione"] == 1 and d["aggiornato"] == "2026-11-01T22:50:00" and d["fonte"] == "espn"
    p = d["partite"]["juventus|napoli"]
    assert (p["casa"], p["trasferta"], p["stato"], p["gol_casa"], p["visto"]) == ("juventus", "napoli", "finita", 2, "2026-11-01T22:50:00")


def test_file_rotto_vuoto_o_strano_si_ignora(tmp_path):
    f = tmp_path / "live.json"
    m = Mondo("2026-11-01 23:00")
    for testo in ("", "{rotto", "[]", json.dumps({"partite": {"x|y": {"casa": "x"}}}), json.dumps({"partite": []}),
                  json.dumps({"partite": {"a|b": {"casa": "a", "trasferta": "b", "stato": "boh", "eventi": []}}})):
        f.write_text(testo, encoding="utf-8")
        r = m.raccoglitore(f)
        assert r.istantanea()["partite"] == {} and r.aggiornato_il is None


def test_le_partite_vecchie_del_file_non_si_caricano(tmp_path):
    f = tmp_path / "live.json"
    m = Mondo("2026-11-01 22:50")
    m.raccoglitore(f).passo()
    m.avanza(3 * 86400)
    assert m.raccoglitore(f).istantanea()["partite"] == {}


def test_partita_oltre_la_finestra_si_segue_finche_la_fonte_dice_finita():
    m = Mondo("2026-11-01 22:50", _espn("STATUS_SECOND_HALF", "in", ("1", "0"), "90+9"))
    r = m.raccoglitore()
    assert r.passo() == "ok" and _juve(r)["stato"] == "secondo_tempo"
    m.avanza(10 * 60)                                                # 23:00: la finestra (inizio + 130 minuti) è chiusa
    assert r.passo() == "ok" and len(m.url) == 2                     # ...ma la fonte non ha ancora detto «finita»
    m.corpo = _espn()
    m.avanza(live.INTERVALLO_DOPO)
    assert r.passo() == "ok" and _juve(r)["stato"] == "finita" and not r.in_gioco()
    m.avanza(live.INTERVALLO_DOPO)
    assert r.passo() == "ferma" and len(m.url) == 3


def test_dopo_la_finestra_si_chiede_piano_e_mai_oltre_il_tetto():
    m = Mondo("2026-11-01 23:00", _espn("STATUS_SECOND_HALF", "in", ("1", "0")))   # fonte ferma: non dice mai «finita»
    r = m.raccoglitore()
    fino = datetime(2026, 11, 1, 20, 45) + live.TETTO_SEGUI
    while m.t <= fino + timedelta(minutes=30):
        r.passo()
        m.avanza(15)
    attese = (fino - datetime(2026, 11, 1, 23, 0)).total_seconds() / live.INTERVALLO_DOPO
    assert 0 < len(m.url) <= attese + 1                              # una richiesta ogni 5 minuti, poi basta
    n = len(m.url)
    m.avanza(3600)
    assert r.passo() == "ferma" and len(m.url) == n


def test_dopo_un_riavvio_senza_file_basta_una_richiesta():
    m = Mondo("2026-11-01 23:00")
    r = m.raccoglitore()
    assert r.passo() == "ok" and _juve(r)["gol_casa"] == 2
    for _ in range(40):
        m.avanza(15)
        assert r.passo() == "ferma"
    assert len(m.url) == 1


def test_partita_giocata_nel_calendario_non_si_chiede_piu():
    m = Mondo("2026-11-01 23:00")
    r = m.raccoglitore(cal=[CAL[0] | {"giocata": 1, "gol_casa": 2, "gol_trasferta": 0}])
    assert r.passo() == "ferma" and m.url == []


def _riga(**k):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (data TEXT, casa TEXT, trasferta TEXT, giornata INT, giocata INT, gol_casa INT, gol_trasferta INT)")
    v = {"data": "2026-11-01 20:45", "casa": "juventus", "trasferta": "napoli", "giornata": 10, "giocata": 0,
         "gol_casa": None, "gol_trasferta": None} | k
    db.execute("INSERT INTO partite VALUES (:data, :casa, :trasferta, :giornata, :giocata, :gol_casa, :gol_trasferta)", v)
    return db.execute("SELECT * FROM partite").fetchall()


def test_il_risultato_ufficiale_vince_sulla_diretta_ferma():
    m = Mondo("2026-11-01 22:50", _espn("STATUS_SECOND_HALF", "in", ("2", "0"), "90+9"))
    r = m.raccoglitore()
    r.passo()
    corpo = live.risposta(r, _riga(giocata=1, gol_casa=2, gol_trasferta=0))
    p = corpo["partite"][0]
    assert (p["stato"], p["minuto"], p["gol_casa"], p["gol_trasferta"]) == ("finita", None, 2, 0) and corpo["in_corso"] == 0
    assert p["eventi"] and p["eventi"][0]["chi"] == "D. Vlahovic"     # i marcatori visti in diretta restano


def test_se_l_ufficiale_dice_un_altro_punteggio_i_marcatori_della_diretta_si_tolgono():
    m = Mondo("2026-11-01 22:50")
    r = m.raccoglitore()
    r.passo()
    p = live.risposta(r, _riga(giocata=1, gol_casa=3, gol_trasferta=0))["partite"][0]
    assert (p["stato"], p["gol_casa"], p["eventi"]) == ("finita", 3, [])


def test_senza_ufficiale_resta_la_diretta():
    m = Mondo("2026-11-01 22:50")
    r = m.raccoglitore()
    r.passo()
    p = live.risposta(r, _riga())["partite"][0]
    assert (p["stato"], p["gol_casa"], p["gol_trasferta"]) == ("finita", 2, 0)
