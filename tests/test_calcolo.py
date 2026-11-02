"""Calcoli pesanti: cache con tetto, al massimo due insieme, un solo calcolo per chiave, risposta «sto calcolando» (202)."""
import sqlite3
import threading
import time

import pytest

from fanta import archivio, calcolo, consigli, server

from test_account_http import cliente
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)


@pytest.fixture(autouse=True)
def pulito():
    calcolo.cache.clear()
    calcolo._errori.clear()
    yield
    attendi_fine()
    calcolo.cache.clear()
    calcolo._errori.clear()
    calcolo.in_coda.set(False)


def attendi_fine(secondi: float = 10) -> None:
    fine = time.monotonic() + secondi
    while calcolo.in_corso() and time.monotonic() < fine:
        time.sleep(0.01)
    assert calcolo.in_corso() == 0


@pytest.fixture
def db_file(tmp_path):
    db = archivio.apri(tmp_path / "prova.sqlite")
    yield db
    db.close()


# ---------------------------------------------------------------- la cache
def test_la_cache_ha_un_tetto_e_butta_il_meno_usato():
    c = calcolo.Cache(massimo=3)
    for k in "abc":
        c[k] = k.upper()
    assert c["a"] == "A"                              # «a» è stato usato: ora il meno usato è «b»
    c["d"] = "D"
    assert "b" not in c and {"a", "c", "d"} == {k for k in "abcd" if k in c} and len(c) == 3


def test_le_voci_fisse_non_escono_e_non_contano():
    c = calcolo.Cache(massimo=2)
    c.metti("dati", "grandi", fissa=True)
    for k in "abcd":
        c[k] = k
    assert "dati" in c and len(c) == 3 and "a" not in c and "b" not in c
    c.clear()
    assert len(c) == 0


class CacheSfuggente(calcolo.Cache):
    """Una voce c'è quando la si cerca e sparisce subito dopo: è quello che succede quando un altro thread, nello stesso istante,
    mette un risultato nuovo e la cache piena butta fuori proprio quella voce (o la svuota un aggiornamento dei dati)."""

    def __contains__(self, chiave) -> bool:
        c = super().__contains__(chiave)
        self.clear()
        return c


def test_una_voce_che_esce_mentre_la_si_legge_non_da_errore(monkeypatch, db_file):
    sfuggente = CacheSfuggente()
    monkeypatch.setattr(calcolo, "cache", sfuggente)
    monkeypatch.setattr(consigli, "_cache", sfuggente)
    monkeypatch.setattr(consigli.modello, "carica", lambda db: "dati nuovi")
    sfuggente["x"] = "vecchio"
    assert calcolo.ottieni("x", lambda d: "ricalcolato", db_file) in ("vecchio", "ricalcolato")      # prima: KeyError
    sfuggente[("dati", consigli._versione(db_file))] = "dati vecchi"
    assert consigli.dati(db_file) in ("dati vecchi", "dati nuovi")


def test_la_cache_del_programma_non_cresce_senza_fine():
    for i in range(calcolo.MAX_RISULTATI * 3):
        calcolo.cache[("prova", i)] = i
    assert len(calcolo.cache) == calcolo.MAX_RISULTATI


def test_le_voci_leggere_pesano_un_quarto_e_ne_stanno_quattro_volte_di_piu():
    c = calcolo.Cache(massimo=2)
    for i in range(8):
        c.metti(("utente", i), i, peso=calcolo.PESO_LEGGERO)
    assert len(c) == 8                                            # 8 voci leggere = 2 unità
    c.metti(("utente", 8), 8, peso=calcolo.PESO_LEGGERO)
    assert len(c) == 8 and ("utente", 0) not in c and ("utente", 8) in c        # la nona fa uscire la meno usata
    c.metti("grande", "x")                                        # una voce intera = 4 leggere
    assert "grande" in c and len(c) == 5
    c.metti("grande", "y")                                        # riscritta: il peso vecchio si toglie, non si somma
    assert c["grande"] == "y" and len(c) == 5
    c.clear()
    c.metti("a", 1, peso=calcolo.PESO_LEGGERO)
    assert len(c) == 1 and c._totale == calcolo.PESO_LEGGERO


def test_la_cache_del_programma_regge_tre_voci_leggere_per_duecento_utenti():
    for u in range(200):
        for cosa in ("formazione", "mercato", "proposte"):
            calcolo.cache.metti((cosa, u), u, peso=calcolo.PESO_LEGGERO)
    assert len(calcolo.cache) == 600                              # prima del cambio il tetto era 256 voci: ne restava meno della metà


def test_con_tanti_calcoli_in_coda_l_app_riprova_meno_spesso(db_file):
    calcolo.in_coda.set(True)
    via = threading.Event()
    lento = lambda d: via.wait(10)  # noqa: E731
    attese = []
    try:
        for i in range(40):
            with pytest.raises(calcolo.InCalcolo) as e:
                calcolo.ottieni(("k", i), lento, db_file)
            attese.append(e.value.riprova_tra)
        assert attese[0] == calcolo.RIPROVA_TRA and attese == sorted(attese)
        assert calcolo.RIPROVA_TRA < attese[-1] <= calcolo.RIPROVA_MAX
    finally:
        via.set()
        attendi_fine()


# ---------------------------------------------------------------- calcolo immediato
def test_un_calcolo_per_chiave_anche_con_molte_richieste_insieme():
    db = sqlite3.connect(":memory:")
    chiamate = []

    def lento(_):
        chiamate.append(1)
        time.sleep(0.2)
        return "risultato"
    risultati = []
    thread = [threading.Thread(target=lambda: risultati.append(calcolo.ottieni("k", lento, db))) for _ in range(6)]
    [t.start() for t in thread]
    [t.join(10) for t in thread]
    assert risultati == ["risultato"] * 6 and len(chiamate) == 1


def test_al_massimo_due_calcoli_pesanti_insieme():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    ora, massimo, blocco = [0], [0], threading.Lock()

    def pesante(_):
        with blocco:
            ora[0] += 1
            massimo[0] = max(massimo[0], ora[0])
        time.sleep(0.15)
        with blocco:
            ora[0] -= 1
        return 1
    thread = [threading.Thread(target=calcolo.ottieni, args=(("k", i), pesante, db)) for i in range(7)]
    [t.start() for t in thread]
    [t.join(20) for t in thread]
    assert all(not t.is_alive() for t in thread)
    assert massimo[0] == calcolo.MAX_CONTEMPORANEI == 2


def test_un_calcolo_dentro_un_altro_non_si_blocca():
    """Un calcolo che ne chiede un secondo (la formazione chiede le previsioni) non deve aspettare un permesso che ha già."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    esterno = lambda i: (lambda d: calcolo.ottieni(("dentro", i), lambda x: i * 10, d) + 1)  # noqa: E731
    risultati = {}
    thread = [threading.Thread(target=lambda i=i: risultati.update({i: calcolo.ottieni(("fuori", i), esterno(i), db)})) for i in range(6)]
    [t.start() for t in thread]
    [t.join(10) for t in thread]
    assert all(not t.is_alive() for t in thread), "bloccati"
    assert risultati == {i: i * 10 + 1 for i in range(6)}


def test_un_errore_non_resta_in_cache_e_il_prossimo_riprova():
    db = sqlite3.connect(":memory:")
    esito = {"ok": False}

    def calcola(_):
        if not esito["ok"]:
            raise ValueError("dati mancanti")
        return 5
    with pytest.raises(ValueError, match="dati mancanti"):
        calcolo.ottieni("k", calcola, db)
    esito["ok"] = True
    assert calcolo.ottieni("k", calcola, db) == 5 and calcolo.in_corso() == 0


# ---------------------------------------------------------------- in coda
def test_in_coda_la_richiesta_non_aspetta(db_file):
    calcolo.in_coda.set(True)
    via, vista = threading.Event(), []

    def lento(d):
        vista.append(d)
        via.wait(10)
        return "pronto"
    with pytest.raises(calcolo.InCalcolo) as e:
        calcolo.ottieni("k", lento, db_file)
    assert e.value.riprova_tra == calcolo.RIPROVA_TRA
    with pytest.raises(calcolo.InCalcolo):                    # richiesto di nuovo mentre calcola: non riparte un secondo calcolo
        calcolo.ottieni("k", lento, db_file)
    via.set()
    attendi_fine()
    assert calcolo.ottieni("k", lento, db_file) == "pronto" and len(vista) == 1
    assert vista[0] is not db_file                           # il calcolo ha usato una sua connessione: quella della richiesta si chiude subito


def test_in_coda_un_errore_arriva_a_chi_riprova(db_file):
    calcolo.in_coda.set(True)

    def rotto(_):
        raise ValueError("Non si riesce a formare una squadra")
    with pytest.raises(calcolo.InCalcolo):
        calcolo.ottieni("k", rotto, db_file)
    attendi_fine()
    with pytest.raises(ValueError, match="formare una squadra"):
        calcolo.ottieni("k", rotto, db_file)
    with pytest.raises(calcolo.InCalcolo):                    # l'errore si dice una volta; poi si riprova da capo
        calcolo.ottieni("k", rotto, db_file)


def test_in_coda_con_un_archivio_in_memoria_si_calcola_subito():
    calcolo.in_coda.set(True)
    assert calcolo.ottieni("k", lambda d: 7, sqlite3.connect(":memory:")) == 7


# ---------------------------------------------------------------- dal server
@pytest.fixture
def formazione_lenta(ambiente, monkeypatch):
    """La formazione vera passa dalla coda; il calcolo, invece di durare, aspetta un via e conta le volte."""
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st: 9)
    stato = {"via": threading.Event(), "chiamate": 0, "errore": None}

    def finta(db, s, giornata, regole, simulazioni):
        stato["chiamate"] += 1
        stato["via"].wait(10)
        if stato["errore"]:                  # un errore vero del calcolo, scritto apposta per l'utente in fanta/consigli.py
            import pandas as pd
            vuote = pd.DataFrame(columns=["nome", "ruolo", "p_voto", "mu", "mu_voto"])
            consigli._calcola_formazione(s, vuote, giornata, False, regole, simulazioni)
        return {"squadra": s.nome, "giornata": giornata, "titolari": [], "moduli": []}
    monkeypatch.setattr(consigli, "_formazione_pronta", finta)
    return stato


def prepara(c):
    assert c.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n"}).status_code == 200
    assert c.put("/api/mia-squadra", json={"nome": "Mia"}).status_code == 200


def test_la_formazione_risponde_sto_calcolando_poi_il_risultato(formazione_lenta):
    a, _ = nuovo_utente("utentea")
    prepara(a)
    r = a.get("/api/formazione")
    assert r.status_code == 202 and r.json()["calcolo"] == "in_corso" and r.json()["riprova_tra"] == calcolo.RIPROVA_TRA
    assert r.headers["retry-after"] == str(calcolo.RIPROVA_TRA) and "calcolando" in r.json()["detail"]
    assert a.get("/api/formazione").status_code == 202
    formazione_lenta["via"].set()
    attendi_fine()
    r = a.get("/api/formazione")
    assert r.status_code == 200 and r.json()["squadra"] == "Mia"
    assert formazione_lenta["chiamate"] == 1                  # tre richieste, un solo calcolo


def test_lo_stesso_calcolo_serve_due_utenti_con_la_stessa_rosa(formazione_lenta):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    prepara(a)
    prepara(b)
    formazione_lenta["via"].set()
    assert a.get("/api/formazione").status_code == 202
    attendi_fine()
    assert a.get("/api/formazione").status_code == 200 and b.get("/api/formazione").status_code == 200
    assert formazione_lenta["chiamate"] == 1                  # stessa squadra, rosa, giornata e regole: stessa impronta


def test_un_errore_di_calcolo_arriva_con_il_suo_messaggio(formazione_lenta):
    a, _ = nuovo_utente("utentea")
    prepara(a)
    formazione_lenta["errore"] = "Non si riesce a formare una squadra"
    formazione_lenta["via"].set()
    assert a.get("/api/formazione").status_code == 202
    attendi_fine()
    r = a.get("/api/formazione")
    assert r.status_code == 400 and "formare una squadra" in r.json()["detail"]


def test_spento_si_calcola_come_sempre_senza_202(formazione_lenta, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    formazione_lenta["via"].set()
    c = cliente()
    assert c.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n"}).status_code == 200
    c.put("/api/mia-squadra", json={"nome": "Mia"})
    r = c.get("/api/formazione")
    assert r.status_code == 200 and r.json()["squadra"] == "Mia"


def test_la_coda_ha_un_tetto(db_file, monkeypatch):
    calcolo.in_coda.set(True)
    via = threading.Event()
    lento = lambda d: via.wait(10)  # noqa: E731
    try:
        for i in range(calcolo.MAX_IN_CODA):
            with pytest.raises(calcolo.InCalcolo):
                calcolo.ottieni(("k", i), lento, db_file)
        with pytest.raises(calcolo.Occupato) as e:                    # uno più del tetto non entra
            calcolo.ottieni(("k", "ultimo"), lento, db_file)
        assert e.value.riprova_tra > 0
        with pytest.raises(calcolo.InCalcolo):                        # chi chiede una cosa già in coda non è un problema
            calcolo.ottieni(("k", 0), lento, db_file)
    finally:
        via.set()
        attendi_fine()


def test_il_mercato_si_rifa_se_cambia_il_prezzo_pagato(monkeypatch, db_file):
    """Il mercato usa il prezzo pagato (rimborso allo svincolo, cambi fattibili): reimportare la rosa con i prezzi, stessi giocatori,
    deve dare un risultato nuovo. Prima la chiave della cache guardava solo giocatori e crediti: restava il mercato di prima."""
    from fanta import gestione, lega
    from fanta.regole import Regole
    monkeypatch.setattr(gestione, "mercato", lambda db, regole, rose, nome=None, **k: {"costo": rose.squadre[0].giocatori[0].costo})
    rosa = lambda costo: lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", costo)], 50)], "Mia")  # noqa: E731
    assert consigli.mercato(db_file, Regole(), rosa(None))["costo"] is None
    assert consigli.mercato(db_file, Regole(), rosa(30))["costo"] == 30
