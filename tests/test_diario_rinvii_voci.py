"""Diario e riepilogo di Oggi: quattro difetti trovati il 26/11/2026. Una voce calcolata con il voto d'ufficio e poi «aspettano il
recupero»; il voto del recupero al posto di quello contato dalla lega; l'istantanea persa per un errore; il confronto con una
consigliata rifatta. Archivio in una cartella temporanea, dati inventati."""
import logging
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import archivio, consigli, diario, fasi, lega, precisione, rinvii
from fanta.regole import Regole

ST = "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori: gli attaccanti 21-25 giocano la partita 2
TIT = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]                  # 3-4-3 con due attaccanti della partita 2
UFFICIO = replace(Regole(), partite_rinviate="voto_ufficio")
# giornata 1: tre partite nel turno e la 2 rinviata al 20 ottobre, ancora da giocare
PARTITE = [(1, "2026-09-01 18:00", "a", "b", 1), (3, "2026-09-01 20:45", "c", "d", 1), (4, "2026-09-02 18:00", "e", "f", 1),
           (2, "2026-10-20 20:45", "g", "h", 0)]
TUTTI_SEI = {i: 6.0 for i in range(21, 26)}


@pytest.fixture
def mondo(monkeypatch, tmp_path):
    db = archivio.apri(tmp_path / "fanta.sqlite")
    for i, d, c, t, gi in PARTITE:
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, 1, ?, ?, ?, ?)",
                   (i, ST, d, c, t, gi))
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": 1, "calciatore_id": i, "squadra": "abcdef"[i % 6], "voto_red": 6.0}
                                    for i in range(1, 21)])
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda d: NS(partite=pd.read_sql("SELECT * FROM partite", d),
                                                       voti=pd.read_sql("SELECT * FROM voti", d)))
    monkeypatch.setattr(diario, "previsioni", lambda d, stagione, giornata, regole, par: pd.DataFrame([
        {"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.0, "partita": 2 if i > 20 else 1}
        for i in range(1, 26)]))
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(diario.scelte, "leggi", lambda st, g, *a, **k: {"titolari": TIT, "modulo": "3-4-3"})
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26)])], "Mia")

    def recupero(voti: dict) -> None:
        """La partita 2 si gioca: i voti dei suoi giocatori {id: voto}."""
        db.execute("UPDATE partite SET giocata = 1 WHERE id = 2")
        archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": 1, "calciatore_id": i, "squadra": "gh"[i % 2], "voto_red": v}
                                        for i, v in voti.items()])

    def voce(regole: Regole) -> dict:
        return next(v for v in diario.elenco(file, regole, db)["giornate"] if v["giornata"] == 1)

    def riepilogo(regole: Regole) -> dict:
        return fasi.blocco_riepilogo(db, regole, rose, ST, 1, tmp_path / "scelte.json", file)
    file = tmp_path / "diario.json"
    return NS(db=db, rose=rose, file=file, recupero=recupero, voce=voce, riepilogo=riepilogo,
              aggiorna=lambda regole: diario.aggiorna(db, regole, rose, file, simulazioni=30))


def _istantanea(file, monkeypatch, titolari=TIT, misure=None) -> None:
    """La consigliata mostrata prima della scadenza: `titolari`, 70 punti attesi, ogni titolare «gioca 90%» e 6,0 atteso."""
    monkeypatch.setattr(diario.ic, "misure", lambda f: misure)
    f = {"giornata": 1, "modulo": "3-4-3", "punteggio_atteso": 70.0, "livelli": [],
         "titolari": [{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "fv_atteso": 6.0} for i in titolari],
         "panchina": [{"id": 2, "nome": "G2", "ruolo": "P"}]}
    assert diario.salva_istantanea(f, ST, file)


# ---------------------------------------------------------------- 1. voto d'ufficio, poi «aspettano il recupero»
def test_voce_col_voto_d_ufficio_non_si_mostra_finche_la_giornata_aspetta_il_recupero(mondo):
    """Il Diario conta il 6 d'ufficio; poi l'utente sceglie «aspettano il recupero» per quella giornata, che così non è più finita.
    La voce (66 punti, «prendono il voto d'ufficio») non è più quella della lega: né il Diario né il riepilogo di Oggi la mostrano
    (prima stava accanto a «manca il recupero»). Giocato il recupero, la voce si rifà con i suoi voti."""
    assert mondo.aggiorna(UFFICIO) == 1
    assert mondo.voce(UFFICIO)["schierata"]["reale"] == 66.0                     # 11 voti da 6, G21 e G25 d'ufficio
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    assert diario.elenco(mondo.file, aspetta, mondo.db)["giornate"] == []
    r = mondo.riepilogo(aspetta)
    # dai voti, come prima del calcolo del Diario: G21 e G25 aspettano il recupero; 9 voti da 6 e il portiere a porta inviolata
    assert r["nel_diario"] is False and r["recuperi"] and r["punti_fatti"] == 9 * 6.0 + 1
    assert mondo.aggiorna(aspetta) == 0
    mondo.recupero(TUTTI_SEI | {21: 7.0, 25: 10.0})
    assert mondo.aggiorna(aspetta) == 1
    v = mondo.voce(aspetta)
    assert v["schierata"]["reale"] == 9 * 6.0 + 7.0 + 10.0 and v["spiegazione_punti"] is None
    assert mondo.riepilogo(aspetta)["nel_diario"] is True and mondo.riepilogo(aspetta)["punti_fatti"] == 71.0


def test_la_rotta_del_diario_e_il_widget_non_mostrano_la_voce_sospesa(mondo, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from fanta import regole, server, widget
    mondo.aggiorna(UFFICIO)
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(diario, "FILE", mondo.file)
    lega.salva(mondo.rose, tmp_path / "rose.json")
    mondo.db.commit()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))     # la rotta chiude la connessione
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    regole.salva(UFFICIO, tmp_path / "regole.json")
    assert [v["giornata"] for v in c.get("/api/diario").json()["giornate"]] == [1]
    assert [v["fatti"] for v in widget._diario(mondo.file, UFFICIO, mondo.db)] == [66.0]
    regole.salva(aspetta, tmp_path / "regole.json")
    r = c.get("/api/diario").json()
    assert r["giornate"] == [] and [x["testo"] for x in r["in_attesa"]] == [ATTESA_1]
    assert widget._diario(mondo.file, aspetta, mondo.db) == []


def test_con_le_stesse_regole_la_voce_resta(mondo):
    """Solo la voce calcolata con regole diverse da quelle di adesso si nasconde: con il voto d'ufficio la giornata resta finita."""
    mondo.aggiorna(UFFICIO)
    assert mondo.riepilogo(UFFICIO)["nel_diario"] is True and mondo.riepilogo(UFFICIO)["punti_fatti"] == 66.0


ATTESA_1 = "Giornata 1 · 1ª di Serie A: in attesa del recupero, i punti arrivano dopo."


def test_la_giornata_sospesa_ha_una_riga_che_lo_dice(mondo):
    """Revisione di #947: la giornata nascosta perché aspetta il recupero non sparisce senza spiegazione. `in_attesa` la elenca
    con la frase del server (web e iPhone la mostrano così com'è); vuoto quando non c'è niente da aspettare."""
    mondo.aggiorna(UFFICIO)
    assert diario.elenco(mondo.file, UFFICIO, mondo.db)["in_attesa"] == []
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    attesa = diario.elenco(mondo.file, aspetta, mondo.db)["in_attesa"]
    assert [(x["stagione"], x["giornata"], x["giornata_lega"], x["testo"]) for x in attesa] == [(ST, 1, 1, ATTESA_1)]
    assert attesa[0]["frase"]["chiave"] == "diario.in_attesa_recupero"
    mondo.recupero(TUTTI_SEI)
    mondo.aggiorna(aspetta)
    assert diario.elenco(mondo.file, aspetta, mondo.db)["in_attesa"] == []


def test_con_la_regola_aspetta_la_giornata_col_recupero_da_giocare_ha_la_frase(mondo):
    """Con «aspetta», il predefinito, una giornata con un recupero ancora da giocare non è finita: non ha una voce, e prima
    nemmeno la frase, perché `in_attesa` nasceva solo dalle voci nascoste. In Giornate spariva per settimane senza spiegazione."""
    r = diario.elenco(mondo.file, Regole(), mondo.db)
    assert r["giornate"] == []
    assert [(x["stagione"], x["giornata"], x["giornata_lega"], x["testo"]) for x in r["in_attesa"]] == [(ST, 1, 1, ATTESA_1)]
    assert r["in_attesa"][0]["frase"] == {"chiave": "diario.in_attesa_recupero",
                                          "param": {"giornata": {"chiave": "giornata.lega", "param": {"n": 1, "a": 1}}}}
    mondo.recupero(TUTTI_SEI)                                   # giocato il recupero (e arrivati i voti) la giornata entra nel Diario
    mondo.aggiorna(Regole())
    r = diario.elenco(mondo.file, Regole(), mondo.db)
    assert [v["giornata"] for v in r["giornate"]] == [1] and r["in_attesa"] == []


@pytest.mark.parametrize("mia", ["Mia", None])
def test_la_rotta_del_diario_dice_l_attesa_solo_a_chi_ha_la_sua_squadra(mondo, monkeypatch, tmp_path, mia):
    """Senza la tua squadra nessun punto arriverà: la pagina dice dove sceglierla (`motivo_vuoto` «squadra»), non che la giornata
    aspetta il recupero. Web e iPhone, con una frase d'attesa, non mostrano la frase della pagina vuota."""
    from fastapi.testclient import TestClient

    from fanta import regole, server
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(diario, "FILE", mondo.file)
    lega.salva(lega.Rose(mondo.rose.squadre, mia), tmp_path / "rose.json")
    regole.salva(Regole(), tmp_path / "regole.json")
    mondo.db.commit()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))     # la rotta chiude la connessione
    r = TestClient(server.app, headers={"X-Fanta": "1"}).get("/api/diario").json()
    assert r["giornate"] == []
    if mia:
        assert r["motivo_vuoto"] == "giornate" and [x["testo"] for x in r["in_attesa"]] == [ATTESA_1]
    else:
        assert r["motivo_vuoto"] == "squadra" and r["in_attesa"] == []


def test_la_frase_d_attesa_solo_a_turno_giocato_e_dalla_prima_giornata_della_lega(mondo):
    """Una partita del turno ancora da giocare: la giornata è in corso, non aspetta il recupero. E come le voci, niente frase per
    una giornata di prima che la lega cominciasse."""
    assert [x["giornata"] for x in diario.elenco(mondo.file, Regole(prima_giornata_lega=2), mondo.db)["in_attesa"]] == []
    mondo.db.execute("UPDATE partite SET giocata = 0 WHERE id = 4")
    assert diario.elenco(mondo.file, Regole(), mondo.db)["in_attesa"] == []


def test_una_giornata_sola_nella_frase_d_attesa(mondo):
    """La voce nascosta (calcolata con il voto d'ufficio, poi «aspetta») e la giornata senza voce che aspetta il recupero sono la
    stessa giornata: una frase sola."""
    mondo.aggiorna(UFFICIO)
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    assert [x["giornata"] for x in diario.elenco(mondo.file, aspetta, mondo.db)["in_attesa"]] == [1]


def test_con_le_regole_di_adesso_il_diario_legge_l_archivio_una_volta(mondo, monkeypatch):
    """Revisione di #947: una voce calcolata con le regole di adesso non chiede niente all'archivio per sé (prima ogni GET
    /api/diario e /api/widget lo leggeva una volta per voce): né se la giornata è finita né se i voti sono arrivati. L'archivio si
    legge una volta sola per tutte, per il calendario delle giornate che aspettano un recupero."""
    mondo.aggiorna(UFFICIO)
    voce = diario.carica(mondo.file)["giornate"][f"{ST}/1"]
    diario._scrivi(mondo.file, voci={f"{ST}/3": voce | {"giornata": 3}})
    monkeypatch.setattr(rinvii, "giornate_chiuse", lambda *a, **k: pytest.fail("non serve"))
    monkeypatch.setattr(fasi, "voti_arrivati", lambda *a, **k: pytest.fail("non serve"))
    letture = []
    mondo.db.set_trace_callback(lambda sql: letture.append(sql) if sql.lstrip().upper().startswith("SELECT") else None)
    assert [v["giornata"] for v in diario.elenco(mondo.file, UFFICIO, mondo.db)["giornate"]] == [3, 1]
    mondo.db.set_trace_callback(None)
    assert len(letture) == 1 and "FROM partite" in letture[0]


def _giornata_2_giocata(db) -> None:
    """La giornata 2, l'8 settembre, tutta giocata (senza voti: non entra nel Diario)."""
    for i, d in ((5, "2026-09-08 18:00"), (6, "2026-09-08 20:45")):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, 2, ?, 'x', 'y', 1)",
                   (i, ST, d))


def test_recupero_giocato_oltre_le_ultime_giornate_rifa_la_voce(mondo, monkeypatch):
    """Revisione di #947: il recupero si gioca mesi dopo, quando la giornata non è più fra le ultime MASSIMO_GIORNATE (qui 1, con
    la giornata 2 finita dopo). Prima la voce tornava visibile con i punti del voto d'ufficio, per sempre; ora si rifà lo stesso,
    perché le sue regole non sono quelle di adesso."""
    assert mondo.aggiorna(UFFICIO) == 1
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    _giornata_2_giocata(mondo.db)
    monkeypatch.setattr(diario, "MASSIMO_GIORNATE", 1)
    mondo.recupero(TUTTI_SEI | {21: 7.0, 25: 10.0})
    assert mondo.aggiorna(aspetta) == 1
    v = mondo.voce(aspetta)
    assert v["schierata"]["reale"] == 9 * 6.0 + 7.0 + 10.0 and v["spiegazione_punti"] is None
    assert mondo.aggiorna(aspetta) == 0                                          # una volta sola


def test_recupero_giocato_ma_voti_in_arrivo_la_voce_resta_nascosta(mondo):
    """Revisione di #947: il recupero è giocato ma i suoi voti non sono ancora usciti. La giornata è di nuovo finita, ma la voce
    (calcolata con il voto d'ufficio) non si mostra finché il Diario non la rifà con i voti; Oggi aspetta i voti, senza numeri."""
    assert mondo.aggiorna(UFFICIO) == 1
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    mondo.db.execute("UPDATE partite SET giocata = 1 WHERE id = 2")
    assert mondo.aggiorna(aspetta) == 0
    assert diario.elenco(mondo.file, aspetta, mondo.db)["giornate"] == []
    assert mondo.riepilogo(aspetta) is None


@pytest.mark.parametrize("oltre", [False, True])
def test_titolare_ceduto_prima_del_recupero_la_voce_si_rifa_lo_stesso(mondo, monkeypatch, oltre):
    """Seconda revisione di #947: G12, titolare della formazione salvata, viene ceduto prima del recupero (mercato di gennaio).
    La scelta non si può più schierare con la rosa di oggi, ma la voce ha la formazione schierata: prima non si rifaceva più e
    restavano per sempre i 66 punti del voto d'ufficio. Ora se ne rifanno i punti con la regola di adesso, contando anche G12
    (6 nella giornata), dentro le ultime giornate e oltre."""
    assert mondo.aggiorna(UFFICIO) == 1
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    if oltre:
        _giornata_2_giocata(mondo.db)
        monkeypatch.setattr(diario, "MASSIMO_GIORNATE", 1)
    mondo.recupero(TUTTI_SEI | {21: 7.0, 25: 10.0})
    senza_12 = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26) if i != 12])],
                         "Mia")
    assert diario.aggiorna(mondo.db, aspetta, senza_12, mondo.file, simulazioni=30) == 1
    v = mondo.voce(aspetta)
    assert [t["id"] for t in v["schierata"]["titolari"]] == TIT and v["schierata"]["reale"] == 9 * 6.0 + 7.0 + 10.0
    assert v["spiegazione_punti"] is None
    assert diario.aggiorna(mondo.db, aspetta, senza_12, mondo.file, simulazioni=30) == 0      # una volta sola


def test_voti_del_recupero_arrivati_prima_del_calcolo_la_voce_resta_nascosta(mondo, monkeypatch):
    """Seconda revisione di #947: il recupero è giocato e i suoi voti sono arrivati, ma il Diario non ha ancora fatto il suo giro.
    I segni `rinvio` della voce dicono il voto d'ufficio e la regola di adesso è «aspetta»: la voce non si mostra, senza nemmeno
    chiedere all'archivio se la giornata è finita e se i voti sono arrivati, e Oggi conta dai voti."""
    assert mondo.aggiorna(UFFICIO) == 1
    aspetta = rinvii.con_eccezione(UFFICIO, ST, 1, "aspetta", ST)
    mondo.recupero(TUTTI_SEI | {21: 7.0, 25: 10.0})
    assert diario.elenco(mondo.file, aspetta, mondo.db)["giornate"] == []
    with monkeypatch.context() as m:
        m.setattr(rinvii, "giornate_chiuse", lambda *a, **k: pytest.fail("non serve"))
        m.setattr(fasi, "voti_arrivati", lambda *a, **k: pytest.fail("non serve"))
        assert diario.elenco(mondo.file, aspetta, mondo.db)["giornate"] == []
    assert mondo.riepilogo(aspetta)["nel_diario"] is False


def test_il_diario_chiede_le_giornate_finite_una_volta_sola(mondo, monkeypatch):
    """Seconda revisione di #947: con più voci calcolate con altre regole `elenco` chiede all'archivio le giornate finite una
    volta, non una per voce."""
    mondo.aggiorna(UFFICIO)
    voce = diario.carica(mondo.file)["giornate"][f"{ST}/1"] | {"regole": "di-prima"}
    diario._scrivi(mondo.file, voci={f"{ST}/1": voce, f"{ST}/3": voce | {"giornata": 3}})
    chiamate = []
    vera = rinvii.giornate_chiuse
    monkeypatch.setattr(rinvii, "giornate_chiuse", lambda *a, **k: chiamate.append(1) or vera(*a, **k))
    r = diario.elenco(mondo.file, UFFICIO, mondo.db)
    assert [v["giornata"] for v in r["giornate"]] == [1] and [x["giornata"] for x in r["in_attesa"]] == [3]
    assert len(chiamate) == 1


# ---------------------------------------------------------------- 2. il voto contato dalla lega nella tabella degli 11
@pytest.mark.parametrize("modo, preso, segno", [("voto_ufficio", 6.0, "voto_ufficio"), ("senza_voto", None, "senza_voto"),
                                                ("aspetta", 10.0, None)])
def test_tabella_degli_11_con_il_voto_che_la_lega_ha_contato(mondo, monkeypatch, modo, preso, segno):
    """Partita rinviata e poi recuperata, G25 prende 10 nel recupero. Con il voto d'ufficio la lega gli ha contato 6: la tabella
    diceva «preso 10,0» e «Meglio del previsto: G25 (+4,0)». Ora mostra il voto della lega; chi ha la partita rinviata non entra in
    «meglio/peggio» né in «Quanto ci abbiamo preso». Con «aspetta» la lega conta il voto del recupero: tutto come prima."""
    _istantanea(mondo.file, monkeypatch)
    mondo.recupero(TUTTI_SEI | {25: 10.0})
    regole = replace(Regole(), partite_rinviate=modo)
    assert mondo.aggiorna(regole) == 1
    v = mondo.voce(regole)
    numeri = {g["id"]: g for g in v["giocatori"]}
    assert numeri[25]["fv"] == preso and numeri[25].get("rinvio") == segno
    assert numeri[21].get("rinvio") == segno and numeri[20].get("rinvio") is None
    assert [r["nome"] for r in v["fatti_e_attesi"]["meglio"]] == (["G25"] if modo == "aspetta" else [])
    mostrati, ricostruiti = precisione.numeri_giornata(v)
    assert (len(mostrati), len(ricostruiti)) == ((11, 25) if modo == "aspetta" else (9, 20))      # fuori 21-25 (G21 e G25 fra gli 11)


@pytest.mark.parametrize("modo, fv_di_prima, preso", [("voto_ufficio", 10.0, 6.0), ("senza_voto", None, None)])
def test_voce_di_prima_prende_il_voto_della_lega_quando_cambiano_i_voti(mondo, modo, fv_di_prima, preso):
    """Una voce scritta prima della correzione ha in `giocatori` il voto del recupero (o nessun voto) e nessun segno del rinvio:
    quando i voti della giornata cambiano se ne rifanno i punti, e anche questi numeri."""
    regole = replace(Regole(), partite_rinviate=modo)
    mondo.recupero(TUTTI_SEI | {25: 10.0})
    assert mondo.aggiorna(regole) == 1
    d = diario.carica(mondo.file)
    voce = d["giornate"][f"{ST}/1"]
    for g in voce["giocatori"]:
        g.pop("rinvio", None)
        if g["id"] == 25:
            g["fv"] = fv_di_prima
    voce["impronta_voti"] = "di-prima"
    diario._scrivi(mondo.file, voci={f"{ST}/1": voce})
    assert mondo.aggiorna(regole) == 1
    g25 = next(g for g in diario.carica(mondo.file)["giornate"][f"{ST}/1"]["giocatori"] if g["id"] == 25)
    assert g25["fv"] == preso and g25["rinvio"] == modo
    assert mondo.aggiorna(regole) == 0


# ---------------------------------------------------------------- 3. istantanea persa per un errore
def test_un_errore_degli_indicatori_non_perde_la_consigliata_mostrata(mondo, monkeypatch):
    """`avvisi.prima_partita` va in errore (archivio occupato): la voce si scrive senza gli indicatori ma con la consigliata
    mostrata. Prima il ripiego perdeva l'istantanea e la voce diceva «quella mostrata prima della scadenza non era stata salvata»."""
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)
    mondo.recupero(TUTTI_SEI)
    _istantanea(mondo.file, monkeypatch, misure={"C3": 1, "C4": 0})

    def rotto(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(diario.avvisi, "prima_partita", rotto)
    assert mondo.aggiorna(Regole()) == 1
    v = mondo.voce(Regole())
    assert v["consigliata"]["origine"] == "mostrata" and v["consigliata_di_allora"] == "mostrata" and v["nota_consigliata"] is None
    assert v["consigliata"]["atteso"] == 70.0 and "consiglio" not in v


def test_voce_rifatta_per_errore_si_rifa_una_volta_con_la_consigliata_mostrata(mondo, monkeypatch):
    """Le voci già scritte con l'istantanea persa (consigliata rifatta, «non era stata salvata», ma l'istantanea c'è): il calcolo
    dopo le rifà una volta con la consigliata mostrata. Senza istantanea la voce resta com'è e non si rifà a ogni giro."""
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)
    mondo.recupero(TUTTI_SEI)
    assert mondo.aggiorna(Regole()) == 1
    assert mondo.voce(Regole())["consigliata_di_allora"] == "non_salvata"
    assert mondo.aggiorna(Regole()) == 0                                         # senza istantanea: niente da rifare
    _istantanea(mondo.file, monkeypatch)                                         # come se ci fosse stata, persa dal ripiego
    assert mondo.aggiorna(Regole()) == 1
    v = mondo.voce(Regole())
    assert v["consigliata"]["origine"] == "mostrata" and v["consigliata_di_allora"] == "mostrata"
    assert mondo.aggiorna(Regole()) == 0                                         # una volta sola


def test_la_copia_automatica_che_non_riesce_lascia_una_riga_nel_registro(monkeypatch, caplog, tmp_path):
    """La copia della consigliata (e l'istantanea per il Diario) fatta aprendo la Formazione non deve far fallire la risposta, ma
    se non riesce il registro lo dice, con il tipo d'errore (prima `except Exception: pass`)."""
    from fanta import server

    def rotta(*a, **k):
        raise OSError("disco")
    monkeypatch.setattr(server.copia_scadenza, "salva", rotta)
    monkeypatch.setattr(server.avvisi_pronta, "prima_partita", lambda *a: "2026-11-07 15:00")
    monkeypatch.setattr(server.avvisi_pronta, "scadenza", lambda *a: datetime.now() + timedelta(days=1))
    monkeypatch.setattr(server, "_regole", lambda ctx: Regole())
    ctx = NS(scelte=tmp_path / "scelte.json", diario=tmp_path / "diario.json")
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        server._copia_automatica(None, ctx, {"giornata": 10, "titolari": [{"id": 1}]})
    assert any("OSError" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------- 4. riepilogo di Oggi e confronto con la consigliata
@pytest.mark.parametrize("mostrata, consigliata", [(False, None), (True, {"punti_fatti": 66.0, "punti_attesi": 70.0})])
def test_riepilogo_di_oggi_confronta_solo_con_la_consigliata_mostrata(mondo, monkeypatch, mostrata, consigliata):
    """Senza la consigliata mostrata la pagina Giornate dice che il confronto non c'è: anche Oggi non scrive «Con la consigliata:
    X punti» con quella rifatta. Con la consigliata mostrata (G24 al posto di G25, 70 attesi) il confronto resta."""
    if mostrata:
        _istantanea(mondo.file, monkeypatch, titolari=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 24])
    mondo.recupero(TUTTI_SEI | {25: 10.0})
    assert mondo.aggiorna(Regole()) == 1
    r = mondo.riepilogo(Regole())
    assert r["nel_diario"] is True and r["formazione_di"] == "tua" and r["punti_fatti"] == 70.0      # la tua: G25 ha preso 10
    assert r["consigliata"] == consigliata
