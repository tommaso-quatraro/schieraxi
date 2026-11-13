"""Il risultato visto in diretta resta: cache su file (sopravvive ai riavvii), partita seguita finché la fonte dice «finita»
(con un tetto), il risultato ufficiale del calendario vince. Caso vero: Juventus-Napoli del 1/11, servizio riavviato alle 23:00
(fuori dalla finestra di gioco): fino al giro di aggiornamento del mattino la partita era senza punteggio."""
import json
import sqlite3
from datetime import datetime, timedelta

import pytest

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


def test_rinviata_e_rimessa_il_giorno_dopo_si_segue_quando_si_gioca():
    """#661: domenica alle 20:40 la fonte dà la partita rinviata; il calendario la rimette a lunedì alle 18:30. Lunedì la diretta
    chiede di nuovo e lo stato segue l'orario: non resta «rinviata» con la data vecchia (Oggi farebbe entrare la riserva)."""
    from fanta import fasi
    m = Mondo("2026-11-01 20:40", _espn("STATUS_POSTPONED", "post", ("0", "0"), "0"))
    cal = [dict(CAL[0])]
    r = m.raccoglitore(cal=cal)
    assert r.passo() == "ok" and _juve(r)["stato"] == "rinviata"
    m.avanza(120)
    assert r.passo() == "ferma" and len(m.url) == 1                 # stessa data nel calendario: chiusa, nessuna richiesta
    cal[0]["data"] = "2026-11-02 18:30"                              # il calendario la rimette a lunedì
    m.avanza((datetime(2026, 11, 2, 12, 0) - m.t).total_seconds())
    assert r.passo() == "ferma" and len(m.url) == 1                 # lunedì mattina: fuori dalla finestra
    p = live.risposta(r, cal)["partite"][0]
    assert (p["stato"], p["data"]) == ("da_giocare", "2026-11-02 18:30")
    assert fasi.stato_partita(cal[0], m.t, r.istantanea()["partite"]) == "da_giocare"
    m.avanza((datetime(2026, 11, 2, 18, 25) - m.t).total_seconds())  # si apre la finestra della data nuova
    m.corpo = _espn("STATUS_FIRST_HALF", "in", ("1", "0"), "5'")
    m.corpo["events"][0]["date"] = "2026-11-02T17:30Z"
    assert r.passo() == "ok" and len(m.url) == 2 and "dates=20261102" in m.url[-1]
    p = live.risposta(r, cal)["partite"][0]
    assert (p["stato"], p["gol_casa"], p["data"]) == ("primo_tempo", 1, "2026-11-02 18:30")


def _ev(data_utc, casa, trasf, stato, gruppo):
    return {"date": data_utc, "competitions": [{"status": {"type": {"name": stato, "state": gruppo}, "displayClock": "0"},
            "competitors": [{"homeAway": "home", "score": "0", "team": {"id": casa, "displayName": casa}},
                            {"homeAway": "away", "score": "0", "team": {"id": trasf, "displayName": trasf}}], "details": []}]}


def _due_partite():
    """Domenica: Juventus-Napoli alle 15 (la fonte la darà rinviata) e Inter-Milan alle 18."""
    riga = {"giornata": 10, "stagione": "2026-27", "giocata": 0, "gol_casa": None, "gol_trasferta": None}
    return [riga | {"data": "2026-11-01 15:00", "casa": "juventus", "trasferta": "napoli"},
            riga | {"data": "2026-11-01 18:00", "casa": "inter", "trasferta": "milan"}]


RINVIATA_VECCHIA = _ev("2026-11-01T14:00Z", "Juventus", "Napoli", "STATUS_POSTPONED", "post")   # la fonte non cambia la data


def _juve_in(r, cal):
    return next((p["stato"], p["data"]) for p in live.risposta(r, cal)["partite"] if p["casa"] == "juventus")


@pytest.mark.parametrize("nuova, inizio, passo_secondi, giri", [
    ("2026-11-02 18:30", "2026-11-01 17:50", 15, 16),      # rimessa a lunedì: la fonte la ridà rinviata a ogni lettura di domenica
    ("2026-11-01 20:45", "2026-11-01 20:34", 180, 12),     # rimessa alla sera stessa: si gioca mentre la fonte dice «rinviata»
])
def test_una_rinviata_alla_data_vecchia_non_torna_se_il_calendario_l_ha_spostata(nuova, inizio, passo_secondi, giri):
    """Revisione #700: la fonte tiene la partita rinviata alla data vecchia, il calendario l'ha spostata. Prima «rinviata» e «da
    giocare» si alternavano a ogni lettura (o restava «rinviata» mentre si giocava): la rinviata alla data vecchia non conta."""
    m = Mondo("2026-11-01 14:50", {"events": [RINVIATA_VECCHIA,
                                               _ev("2026-11-01T17:00Z", "Inter", "Milan", "STATUS_FIRST_HALF", "in")]})
    cal = _due_partite()
    r = m.raccoglitore(cal=cal)
    assert r.passo() == "ok" and _juve_in(r, cal) == ("rinviata", "2026-11-01 15:00")
    cal[0]["data"] = nuova
    m.avanza((datetime.fromisoformat(inizio) - m.t).total_seconds())
    visti = []
    for _ in range(giri):
        r.passo()
        visti.append(_juve_in(r, cal))
        m.avanza(passo_secondi)
    assert {d for _, d in visti} == {nuova} and "rinviata" not in {s for s, _ in visti}, visti
    assert len(m.url) > 2                                            # la fonte si è letta davvero, più volte


def test_una_lettura_con_la_sola_rinviata_alla_data_vecchia_conta_come_errore():
    """Se nella risposta l'unica partita seguita è la rinviata alla data vecchia, la fonte non sa niente della partita vera:
    è un errore (dopo tre si passa al ripiego), non una lettura buona."""
    m = Mondo("2026-11-01 20:40", {"events": [RINVIATA_VECCHIA]})
    cal = _due_partite()[:1]
    cal[0]["data"] = "2026-11-01 20:45"
    r = m.raccoglitore(cal=cal)
    assert r.passo() == "errore" and r.aggiornato_il is None


def test_dopo_la_finestra_un_errore_non_accorcia_la_pausa_di_cinque_minuti():
    """Revisione #700: oltre la finestra si chiede una volta ogni 5 minuti; un errore (anche una risposta senza la partita)
    non deve riportare la pausa a un minuto, né il passaggio al ripiego (poche richieste alle fonti)."""
    m = Mondo("2026-11-01 23:00", {"events": []})                  # finestra chiusa alle 22:55, partita non ancora «finita»
    quando = []
    scarica = m.scarica
    m.scarica = lambda url: quando.append(m.mono) or scarica(url)
    r = m.raccoglitore()
    for _ in range(4 * 60):                                          # un'ora, un controllo ogni 15 secondi
        r.passo()
        m.avanza(15)
    assert len(quando) >= 3 and r.errori >= 3
    assert all(b - a >= live.INTERVALLO_DOPO for a, b in zip(quando, quando[1:])), [b - a for a, b in zip(quando, quando[1:])]


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


# ---------------------------------------------------------------- dalla sentinella (invarianti punteggio_mancante e
# stato_partita_incoerente), adattati: il raccoglitore dopo un riavvio è quello del servizio, con il file della cache
RIGA = {"data": "2026-10-31 15:00", "casa": "c0", "trasferta": "t0", "giornata": 10, "stagione": "2026-27", "giocata": 0,
        "gol_casa": None, "gol_trasferta": None}


def _nessuna_richiesta(url):
    raise AssertionError("nessuna richiesta")


def test_sentinella_dopo_un_riavvio_i_risultati_appena_finiti_non_spariscono(tmp_path):
    f = tmp_path / "live.json"
    prima = live.Raccoglitore(lambda: [RIGA], scarica=_nessuna_richiesta, adesso=lambda: datetime(2026, 10, 31, 17, 0), file=f)
    prima._unisci([{"casa": "c0", "trasferta": "t0", "data": "2026-10-31 15:00", "stato": "finita", "minuto": None, "gol_casa": 2,
                    "gol_trasferta": 1, "eventi": []}], live.FONTE_ESPN, datetime(2026, 10, 31, 16, 55))
    prima._salva()
    r = live.Raccoglitore(lambda: [RIGA], scarica=_nessuna_richiesta, adesso=lambda: datetime(2026, 10, 31, 18, 10), file=f)
    assert r.passo() == "ferma"
    p = live.risposta(r, [RIGA])["partite"][0]
    assert (p["stato"], p["gol_casa"], p["gol_trasferta"]) == ("finita", 2, 1)


def test_sentinella_una_partita_rimasta_in_gioco_nella_cache_non_copre_il_risultato_finale():
    giocata = RIGA | {"giocata": 1, "gol_casa": 2, "gol_trasferta": 1}
    r = live.Raccoglitore(lambda: [giocata], scarica=_nessuna_richiesta, adesso=lambda: datetime(2026, 10, 31, 17, 20))
    r._unisci([{"casa": "c0", "trasferta": "t0", "data": "2026-10-31 15:00", "stato": "secondo_tempo", "minuto": 88, "gol_casa": 1,
                "gol_trasferta": 1, "eventi": []}], live.FONTE_ESPN, datetime(2026, 10, 31, 16, 58))
    assert r.passo() == "ferma"                                      # il calendario la dà per giocata: non si chiede più
    p = live.risposta(r, [giocata])["partite"][0]
    assert (p["stato"], p["gol_casa"], p["gol_trasferta"]) == ("finita", 2, 1)


# ---------------------------------------------------------------- senza diretta: stato dall'ora del raccoglitore e dal turno
TURNO = [RIGA | {"casa": f"c{i}", "trasferta": f"t{i}", "data": f"2026-10-3{1 if i < 5 else 0} 15:00"} for i in range(1, 9)]


@pytest.mark.parametrize("ora,stato", [((14, 0), "da_giocare"), ((16, 0), "in_corso"), ((17, 0), "finita")])
def test_senza_diretta_lo_stato_viene_dall_ora_del_raccoglitore(ora, stato):
    r = live.Raccoglitore(lambda: [], adesso=lambda: datetime(2026, 10, 31, *ora))
    assert live.risposta(r, [RIGA])["partite"][0]["stato"] == stato


def test_senza_diretta_una_partita_fuori_dal_turno_e_rinviata():
    vecchia = RIGA | {"casa": "x", "trasferta": "y", "data": "2026-09-20 15:00"}     # rinviata, con la data vecchia mai aggiornata
    r = live.Raccoglitore(lambda: [], adesso=lambda: datetime(2026, 10, 31, 12, 0))
    stati = {p["casa"]: p["stato"] for p in live.risposta(r, [vecchia, RIGA] + TURNO)["partite"]}
    assert stati["x"] == "rinviata" and stati["c0"] == "da_giocare"
