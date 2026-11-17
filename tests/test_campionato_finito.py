"""A campionato finito (#656): appena l'ultima giornata è tutta giocata non c'è più una giornata da giocare. Prima Oggi, Formazione e
widget rispondevano 400 «Il calendario della stagione non è ancora disponibile (di solito esce a luglio)» e la sentinella contava
il rifiuto come una rottura per ogni utente, da fine maggio fino al calendario nuovo.

Ora Oggi risponde 200: nelle solite 48 ore il riepilogo dell'ultima giornata (fase «finita», `prossima` nullo), poi solo la frase
del campionato finito (`campionato_finito`, chiave `campionato.finito`). Formazione e le altre rotte che vogliono una giornata
dicono la stessa frase (409, codice `campionato_finito`), il widget risponde 200 come Oggi. La sentinella non lancia l'allarme a
campionato finito né d'estate (stagione nuova senza calendario, quella prima finita), ma lo lancia ancora quando il calendario
manca davvero. Archivi inventati in cartelle temporanee, orari fissati."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, lega, regole, sentinella, server
from test_fasi import ST, _oggi, ambiente  # noqa: F401  (fixture)

FRASE = {"chiave": "campionato.finito", "param": {}}


# ---------------------------------------------------------------- Oggi (gestione.oggi, ora fissata)
def _ultima_giornata_giocata(a):
    """Le partite delle giornate 10 e 11 di test_fasi tutte giocate: la 11 fa da ultima giornata della stagione."""
    a.stato["giocate"] = {0, 1, 2, 3, 4}
    a.stato["carica"]()
    (a.tmp / "diario.json").write_text(json.dumps({"giornate": {f"{ST}/11": {
        "consigliata": {"reale": 71.5, "atteso": 69.0}}}}), encoding="utf-8")


def test_oggi_dopo_l_ultima_giornata_riepilogo_e_poi_campionato_finito(ambiente):  # noqa: F811
    _ultima_giornata_giocata(ambiente)
    # lunedì mattina: l'ultima partita (domenica 20:45) è finita da meno di 48 ore
    o = _oggi(ambiente, datetime(2026, 11, 16, 10, 0))
    assert o["fase"] == "finita" and o["giornata"] is None and o["prossima"] is None and o["in_corso"] is None
    r = o["riepilogo"]
    assert (r["giornata"], r["nel_diario"], r["punti_fatti"], r["punti_attesi"]) == (11, True, 71.5, 69.0)
    assert o["campionato_finito"]["frase"] == FRASE
    assert o["campionato_finito"]["testo"].startswith("Il campionato è finito")
    assert o["formazione"]["punteggio_atteso"] is None and o["avvisi"] == [] and o["migliori"] == [] and o["partite"] == []
    # dopo le 48 ore resta solo la frase del campionato finito
    o = _oggi(ambiente, datetime(2026, 11, 18, 10, 0))
    assert o["fase"] == "finita" and o["riepilogo"] is None and o["prossima"] is None
    assert o["campionato_finito"]["frase"] == FRASE


def test_con_una_giornata_da_giocare_niente_campionato_finito(ambiente):  # noqa: F811
    o = _oggi(ambiente, datetime(2026, 11, 6, 12, 0))
    assert o["giornata"] == 10 and "campionato_finito" not in o


def test_stagione_finita_solo_con_partite_giocate_e_niente_da_giocare(ambiente):  # noqa: F811
    db, adesso = ambiente.db, datetime(2026, 11, 18, 10, 0)
    assert not consigli.stagione_finita(db, ST, adesso)                 # la giornata 10 è ancora da giocare
    assert not consigli.stagione_finita(db, "2030-31", adesso)          # stagione senza calendario: non è finita
    _ultima_giornata_giocata(ambiente)
    assert consigli.stagione_finita(db, ST, adesso)


# ---------------------------------------------------------------- le rotte (server vero, archivio inventato)
STAGIONE = "2020-21"            # una stagione passata: l'orologio vero è sempre dopo le sue partite
PARTITE = [(37, "2021-05-15 15:00", "inter", "milan"), (37, "2021-05-16 20:45", "roma", "lazio"),
           (38, "2021-05-22 18:00", "milan", "roma"), (38, "2021-05-23 20:45", "lazio", "inter")]
RUOLI = {i: "P" if i <= 3 else "D" if i <= 11 else "C" if i <= 19 else "A" for i in range(1, 26)}


def _archivio(percorso, partite=PARTITE, stagione=STAGIONE):
    db = archivio.apri(percorso)
    archivio.inserisci(db, "partite", [{"id": n, "stagione": stagione, "giornata": g, "data": d, "casa": c, "trasferta": t,
                                        "gol_casa": 1, "gol_trasferta": 0, "giocata": 1, "understat_id": None}
                                       for n, (g, d, c, t) in enumerate(partite)])
    db.commit()
    db.close()


@pytest.fixture
def lega_finita(dati_isolati, tmp_path, monkeypatch):
    """L'app di sempre (senza account) con le rose, le regole e un archivio dove l'ultima giornata è tutta giocata."""
    regole.salva(regole.Regole(), dati_isolati / "regole.json")
    squadra = lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"g{i}", RUOLI[i], "INT") for i in RUOLI])
    lega.salva(lega.Rose([squadra], "Mia"), dati_isolati / "rose.json")
    percorso = tmp_path / "archivio-finto" / "fanta.sqlite"            # quello che apre server._db in dati_isolati
    percorso.parent.mkdir(parents=True, exist_ok=True)
    _archivio(percorso)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: STAGIONE)
    return percorso


def _client():
    return TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)


def test_a_campionato_finito_oggi_e_widget_200_formazione_dice_la_frase(lega_finita):
    c = _client()
    o = c.get("/api/oggi")
    assert o.status_code == 200, o.text
    o = o.json()
    assert o["campionato_finito"]["frase"] == FRASE and o["fase"] == "finita" and o["giornata"] is None and o["prossima"] is None
    w = c.get("/api/widget")
    assert w.status_code == 200, w.text
    w = w.json()
    assert w["campionato_finito"] == o["campionato_finito"] and w["fase"] == "finita" and w["giornata"] is None
    assert w["formazione"]["titolari"] == [] and w["rosa"] == [] and "prossima" not in w
    # Formazione e le rotte che vogliono una giornata: la stessa frase, non quella del calendario che deve ancora uscire
    for percorso in ("/api/formazione", "/api/formazione/testo", "/api/osservati"):
        r = c.get(percorso)
        assert r.status_code == 409, (percorso, r.status_code, r.text)
        assert r.json() == {"detail": o["campionato_finito"]["testo"], "codice": "campionato_finito"}, percorso


def test_senza_calendario_resta_il_messaggio_di_sempre(lega_finita, monkeypatch):
    """D'estate (stagione nuova senza partite) il 400 con la frase del calendario è la risposta giusta: non cambia."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2021-22")
    r = _client().get("/api/formazione")
    assert r.status_code == 400 and r.json()["detail"] == consigli.SENZA_CALENDARIO


# ---------------------------------------------------------------- la sentinella (giri veri, con le rotte vere)
def _due_giri(tmp_path, percorso, adesso):
    inviati = []
    stato = tmp_path / "sentinella.json"
    esiti = [sentinella.giro(manda=lambda t, x: inviati.append(x) or True, file_stato=stato, adesso=adesso, scrivi=lambda s: None,
                             db_percorso=percorso) for _ in range(2)]
    return esiti, inviati


def test_due_giri_a_campionato_finito_e_d_estate_niente_rotture_ne_avvisi(lega_finita, tmp_path, monkeypatch):
    monkeypatch.setattr(sentinella, "_prepara_live", lambda: None)
    esiti, inviati = _due_giri(tmp_path, lega_finita, datetime(2021, 6, 10, 12, 0))           # a giugno, campionato finito
    assert [e["rotture"] for e in esiti] == [[], []] and esiti[0]["controllati"] == ["utente locale"] and inviati == []
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2021-22")                     # d'estate: calendario nuovo in arrivo
    esiti, inviati = _due_giri(tmp_path, lega_finita, datetime(2021, 7, 20, 12, 0))
    assert [e["rotture"] for e in esiti] == [[], []] and inviati == []


def test_la_sentinella_avvisa_ancora_se_il_calendario_manca_davvero(lega_finita, tmp_path, monkeypatch):
    """Stagione in corso senza nessuna partita e nessuna stagione finita prima (archivio senza calendario): il rifiuto è una
    rottura vera e alla seconda volta parte l'avviso."""
    monkeypatch.setattr(sentinella, "_prepara_live", lambda: None)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2023-24")
    esiti, inviati = _due_giri(tmp_path, lega_finita, datetime(2023, 10, 20, 12, 0))
    rifiuti = {r.dettaglio.split(":")[0] for r in esiti[1]["rotture"] if r.invariante == "risposta_rifiutata"}
    assert {"oggi", "formazione", "widget"} <= rifiuti
    assert len(inviati) == 1 and "risposta_rifiutata" in inviati[0]
