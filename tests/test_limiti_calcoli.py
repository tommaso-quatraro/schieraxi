"""Limiti per utente su calcoli e memorie condivise (#513, requisiti R1, R2 e R5 di #483).

- R1: un utente non può avere più di `limiti.MAX_CALCOLI_UTENTE` calcoli pesanti in coda o in corso insieme (oltre: 429 con
  Retry-After, solo a lui) né occupare più di `limiti.QUOTA_RISULTATI_UTENTE` della memoria condivisa dei risultati;
- R2: nessuna azione di un utente svuota i risultati già calcolati per gli altri; le azioni ripetibili che costano calcoli hanno
  un tetto all'ora per utente (`limiti.MAX_AZIONI_PESANTI_ORA`);
- R5: la memoria delle consigliate già mostrate ha una parte per ciascuno (`limiti.MAX_CONSIGLIATE_UTENTE`).
Senza account (un solo utente) nessuno di questi tetti per utente vale. Cartelle temporanee e dati inventati."""
import contextlib
import threading
import time
from datetime import datetime, timedelta

import pytest

from fanta import archivio, calcolo, consigli, limiti, server

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_onboarding import listone_grande

ROSE_MIA = ("Mia\nP\tSommer\t10\nSeconda\nP\tCarnesecchi\t5\nTerza\nP\tMartinez Jo.\t5\n"
            "Quarta\nD\tBastoni\t5\nQuinta\nD\tN'Dicka\t5\n")
AVVERSARIE = ("Seconda", "Terza", "Quarta", "Quinta")
ORA_FISSA = datetime(2026, 11, 8, 10, 15)          # mai l'orologio vero: il tetto orario non deve cambiare ora a metà test


@contextlib.contextmanager
def da_utente(utente_id):
    """Come una richiesta di `utente_id` (il server lo mette per ogni richiesta con gli account accesi)."""
    gettone = calcolo.utente_richiesta.set(utente_id)
    try:
        yield
    finally:
        calcolo.utente_richiesta.reset(gettone)


def attendi_fine(secondi: float = 10) -> None:
    fine = time.monotonic() + secondi
    while calcolo.in_corso() and time.monotonic() < fine:
        time.sleep(0.01)
    assert calcolo.in_corso() == 0


@pytest.fixture(autouse=True)
def pulito():
    calcolo.cache.clear()
    calcolo._errori.clear()
    yield
    attendi_fine()
    calcolo.cache.clear()
    calcolo._errori.clear()
    calcolo.in_coda.set(False)


@pytest.fixture
def db_file(tmp_path):
    db = archivio.apri(tmp_path / "prova.sqlite")
    yield db
    db.close()


@pytest.fixture
def lenta(ambiente, monkeypatch):  # noqa: F811 (fixture importata)
    """La formazione vera passa dalla coda; il calcolo, invece di durare, aspetta il «via» di adesso (`stato["via"]`)."""
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA)
    stato = {"via": threading.Event()}

    def finta(db, s, giornata, regole, simulazioni):
        stato["via"].wait(10)
        return {"squadra": s.nome, "giornata": giornata, "titolari": [], "moduli": []}
    monkeypatch.setattr(consigli, "_formazione_pronta", finta)
    yield stato
    stato["via"].set()
    attendi_fine()


def prepara(c, testo=ROSE_MIA, mia="Mia"):
    assert c.post("/api/rose/testo", json={"testo": testo}).status_code == 200
    assert c.put("/api/mia-squadra", json={"nome": mia}).status_code == 200


def fino_al_risultato(c, **params):
    """Come l'app: con 202 riprova finché il risultato non è pronto."""
    for _ in range(500):
        r = c.get("/api/formazione", params=params)
        if r.status_code != 202:
            return r
        time.sleep(0.01)
    raise AssertionError("il calcolo non finisce")


# ---------------------------------------------------------------- R1: calcoli in coda per utente
def test_quinto_calcolo_dello_stesso_utente_429_con_retry_after(lenta):
    a, _ = nuovo_utente("utentea")
    prepara(a)
    for giornata in (None, 10, 11, 12):                         # quattro calcoli diversi in coda insieme: si può
        assert a.get("/api/formazione", params={"giornata": giornata} if giornata else {}).status_code == 202
    r = a.get("/api/formazione", params={"giornata": 13})
    assert r.status_code == 429
    assert r.json()["detail"] == str(calcolo.Occupato())        # messaggio dei limiti di oggi, già tradotto da web e iPhone
    assert int(r.headers["retry-after"]) > 0 and r.headers["cache-control"] == "no-store"
    assert a.get("/api/formazione").status_code == 202            # riprovare un calcolo già in coda non è un calcolo nuovo
    lenta["via"].set()
    attendi_fine()
    assert fino_al_risultato(a, giornata=13).status_code == 200   # finiti i suoi calcoli, il quinto parte


def test_un_altro_utente_non_aspetta(lenta):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    prepara(a)
    prepara(b, "Sua\nA\tKean\t30\n", "Sua")
    for giornata in (9, 10, 11, 12):
        assert a.get("/api/formazione", params={"giornata": giornata}).status_code == 202
    assert a.get("/api/formazione", params={"giornata": 13}).status_code == 429     # A è al tetto
    assert b.get("/api/formazione").status_code == 202                              # B no: il suo calcolo entra
    lenta["via"].set()
    r = fino_al_risultato(b)
    assert r.status_code == 200 and r.json()["squadra"] == "Sua"


def test_uso_normale_non_incontra_limiti(lenta):
    """La propria formazione, tre giornate, quattro squadre avversarie e qualche ricarica, anche toccate in fretta (i calcoli
    partono prima che finiscano quelli di prima): mai «troppe richieste»."""
    a, _ = nuovo_utente("utentea")
    prepara(a)
    risposte = []
    # apre Formazione e passa subito alle tre giornate dopo, poi ricarica mentre calcola
    risposte += [a.get("/api/formazione", params=p) for p in ({}, {"giornata": 10}, {"giornata": 11}, {"giornata": 12}, {})]
    lenta["via"].set()
    risposte += [fino_al_risultato(a, **p) for p in ({}, {"giornata": 10}, {"giornata": 11}, {"giornata": 12})]
    # guarda le quattro squadre avversarie una dopo l'altra, senza aspettare
    lenta["via"] = threading.Event()
    risposte += [a.get("/api/formazione", params={"squadra": s}) for s in AVVERSARIE]
    risposte.append(a.get("/api/formazione", params={"squadra": AVVERSARIE[0]}))
    lenta["via"].set()
    risposte += [fino_al_risultato(a, squadra=s) for s in AVVERSARIE]
    # e torna alla sua, due volte
    risposte += [fino_al_risultato(a), fino_al_risultato(a)]
    assert len(risposte) >= 12
    assert [r.status_code for r in risposte if r.status_code not in (200, 202)] == []


def test_i_calcoli_in_coda_si_contano_per_utente(db_file):
    """Il tetto è per utente: un altro utente, o chi usa l'app senza account, non lo sente."""
    calcolo.in_coda.set(True)
    via = threading.Event()
    lento = lambda d: via.wait(10)  # noqa: E731
    try:
        with da_utente(1):
            for i in range(limiti.MAX_CALCOLI_UTENTE):
                with pytest.raises(calcolo.InCalcolo):
                    calcolo.ottieni(("a", i), lento, db_file)
            with pytest.raises(calcolo.Occupato):
                calcolo.ottieni(("a", "uno di troppo"), lento, db_file)
        with da_utente(2):
            with pytest.raises(calcolo.InCalcolo):
                calcolo.ottieni(("b", 0), lento, db_file)
        for i in range(limiti.MAX_CALCOLI_UTENTE + 2):              # senza account: nessun tetto per utente
            with pytest.raises(calcolo.InCalcolo):
                calcolo.ottieni(("locale", i), lento, db_file)
    finally:
        via.set()
        attendi_fine()


def test_i_numeri_dei_limiti_si_cambiano_con_una_variabile_d_ambiente(monkeypatch, db_file):
    monkeypatch.setenv("FANTA_MAX_CALCOLI_UTENTE", "2")
    monkeypatch.setenv("FANTA_QUOTA_RISULTATI_UTENTE", "0.5")
    assert limiti.valore("MAX_CALCOLI_UTENTE") == 2 and limiti.valore("QUOTA_RISULTATI_UTENTE") == 0.5
    for sbagliato in ("niente", "0", "-3", "1.5"):                 # un valore che non va bene: vale il numero di sempre
        monkeypatch.setenv("FANTA_MAX_CALCOLI_UTENTE", sbagliato)
        assert limiti.valore("MAX_CALCOLI_UTENTE") == limiti.MAX_CALCOLI_UTENTE == 4
    monkeypatch.setenv("FANTA_MAX_CALCOLI_UTENTE", "2")
    calcolo.in_coda.set(True)
    via = threading.Event()
    try:
        with da_utente(1):
            for i in range(2):
                with pytest.raises(calcolo.InCalcolo):
                    calcolo.ottieni(("a", i), lambda d: via.wait(10), db_file)
            with pytest.raises(calcolo.Occupato):
                calcolo.ottieni(("a", 2), lambda d: via.wait(10), db_file)
    finally:
        via.set()
        attendi_fine()


# ---------------------------------------------------------------- R1: memoria dei risultati per utente
def test_oltre_la_quota_escono_prima_le_voci_dello_stesso_utente():
    c = calcolo.Cache(massimo=8)                                   # quota per utente: un quarto, cioè 2 voci intere
    with da_utente(2):
        c.metti("b1", 1)
        c.metti("b2", 2)
    with da_utente(1):
        for i in range(5):
            c.metti(f"a{i}", i)
    assert "b1" in c and "b2" in c                                 # le voci dell'altro restano
    assert [k for k in ("a0", "a1", "a2", "a3", "a4") if k in c] == ["a3", "a4"]   # di A restano le due più recenti


def test_una_voce_usata_anche_da_un_altro_utente_e_di_tutti():
    """Un risultato che serve a due utenti (stessa lega) non esce per la quota di chi l'ha calcolato per primo."""
    c = calcolo.Cache(massimo=8)
    with da_utente(1):
        c.metti("comune", "x")
    with da_utente(2):
        assert c.get("comune") == "x"
    with da_utente(1):
        for i in range(3):
            c.metti(f"a{i}", i)
    assert "comune" in c and "a0" not in c and "a1" in c and "a2" in c


def test_i_risultati_calcolati_in_coda_contano_per_chi_li_ha_chiesti(monkeypatch, db_file):
    monkeypatch.setattr(calcolo, "cache", calcolo.Cache(massimo=8))
    calcolo.in_coda.set(True)
    with da_utente(2):
        with pytest.raises(calcolo.InCalcolo):
            calcolo.ottieni("di B", lambda d: "b", db_file)
        attendi_fine()
    with da_utente(1):
        for i in range(3):
            with pytest.raises(calcolo.InCalcolo):
                calcolo.ottieni(("a", i), lambda d: "a", db_file)
            attendi_fine()
    assert "di B" in calcolo.cache and ("a", 0) not in calcolo.cache and ("a", 2) in calcolo.cache


# ---------------------------------------------------------------- R2: azioni che costano calcoli
def test_azioni_di_un_utente_non_svuotano_i_risultati_degli_altri(lenta, monkeypatch):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    prepara(b, "Sua\nA\tKean\t30\n", "Sua")
    lenta["via"].set()
    assert fino_al_risultato(b).status_code == 200
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_grande(), "oggi"))
    assert a.post("/api/onboarding/demo").status_code == 200
    assert a.delete("/api/onboarding/demo").status_code == 200
    assert b.get("/api/formazione").status_code == 200            # il risultato di B è ancora pronto: niente da ricalcolare


def test_tetto_orario_azioni_pesanti(lenta, monkeypatch):
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_grande(), "oggi"))
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    for i in range(limiti.MAX_AZIONI_PESANTI_ORA):                 # crea e togli la lega di prova, avanti e indietro
        r = a.post("/api/onboarding/demo") if i % 2 == 0 else a.delete("/api/onboarding/demo")
        assert r.status_code == 200, (i, r.text)
    r = a.post("/api/onboarding/demo")
    assert r.status_code == 429 and "in quest'ora" in r.json()["detail"]
    assert int(r.headers["retry-after"]) == 45 * 60                 # alle 10:15 l'ora finisce tra 45 minuti
    assert b.post("/api/onboarding/demo").status_code == 200       # gli altri non se ne accorgono
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA + timedelta(hours=1))
    assert a.post("/api/onboarding/demo").status_code == 200       # l'ora dopo si riparte


# ---------------------------------------------------------------- R5: consigliate già mostrate
ST, GIORNATA = "2026-27", 9


def consigliata(primo: int = 1) -> dict:
    """Una risposta della Formazione ridotta a ciò che si ricorda: 11 titolari e la panchina (id inventati)."""
    return {"modulo": "4-4-2", "titolari": [{"id": primo + i} for i in range(11)], "panchina": [{"id": 900}]}


@pytest.fixture
def memoria(monkeypatch):
    """Tetti piccoli (5 in tutto, 3 per utente) e un orologio che va avanti di un minuto a ogni voce."""
    monkeypatch.setattr(consigli, "MAX_CONSIGLIATE", 5)
    monkeypatch.setattr(limiti, "MAX_CONSIGLIATE_UTENTE", 3)
    ora = {"t": datetime(2026, 11, 8, 9, 0)}

    def adesso():
        ora["t"] += timedelta(minutes=1)
        return ora["t"]
    monkeypatch.setattr(consigli, "_adesso", adesso)


def ricorda(impronta: str, prima: dict | None = None) -> None:
    consigli._ricorda(impronta, consigliata(), ST, GIORNATA, prima)


def test_consigliate_di_un_utente_non_fanno_dimenticare_quelle_degli_altri(memoria):
    with da_utente(2):
        ricorda("di-b")
    with da_utente(1):
        for i in range(10):
            ricorda(f"di-a-{i}")
    tutte = consigli._consigliate()
    assert "di-b" in tutte                                          # la consigliata di B resta
    assert sorted(k for k in tutte if k.startswith("di-a")) == ["di-a-7", "di-a-8", "di-a-9"]   # di A le sue ultime 3


def test_una_consigliata_usata_anche_da_un_altro_resta_per_lui(memoria):
    """Stessa squadra, rosa e regole (due utenti della stessa lega): la consigliata è una sola. Se A ne mostra tante altre,
    quella resta finché serve a B."""
    with da_utente(1):
        ricorda("stessa-lega")
    with da_utente(2):
        ricorda("stessa-lega", consigli._consigliate()["stessa-lega"])     # B la legge, uguale
    with da_utente(1):
        for i in range(6):
            ricorda(f"di-a-{i}")
    assert "stessa-lega" in consigli._consigliate()


def test_senza_account_la_memoria_delle_consigliate_e_quella_di_sempre(memoria):
    for i in range(7):
        ricorda(f"locale-{i}")
    tutte = consigli._consigliate()
    assert sorted(tutte) == [f"locale-{i}" for i in range(2, 7)]  # solo il tetto di tutto il file
    assert all(set(v) <= {"stagione", "giornata", "modulo", "titolari", "panchina", "non_giocano", "quando"} for v in tutte.values())
