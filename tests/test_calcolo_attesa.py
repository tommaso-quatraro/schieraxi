"""Il server aspetta un poco il calcolo prima di rispondere «sto calcolando» (#907): in tutto al massimo `calcolo.ATTESA_MAX`
secondi per richiesta e al massimo `calcolo.MAX_IN_ATTESA` richieste ferme insieme; oltre il tetto il 202 arriva subito, come
prima. La risposta «sto calcolando» resta la stessa. Cartelle temporanee e calcoli finti."""
import threading
import time

import pytest

from fanta import archivio, calcolo, limiti

from test_calcolo import attendi_fine, formazione_lenta, prepara, pulito  # noqa: F401 (fixture e aiuti di prova)
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_limiti_calcoli import da_utente


@pytest.fixture(autouse=True)
def richiesta_finita():
    yield
    calcolo.attesa.set(None)                      # i test girano nello stesso thread: niente attesa lasciata al test dopo
    calcolo.in_coda.set(False)


@pytest.fixture
def percorso(tmp_path):
    """Un archivio vero su file: chi chiede in un altro thread apre la sua connessione, come le richieste del server."""
    p = tmp_path / "prova.sqlite"
    archivio.apri(p).close()
    return p


def come_richiesta(secondi: float) -> None:
    """Come il server con gli account: i calcoli vanno in coda e la richiesta può aspettare `secondi` in tutto."""
    calcolo.in_coda.set(True)
    calcolo.attesa.set(calcolo.Attesa(secondi))


def chiedi(percorso, chiave, calcola):
    db = archivio.apri(percorso)
    try:
        return calcolo.ottieni(chiave, calcola, db)
    finally:
        db.close()


def fermo_fino_a(via: threading.Event, chiamate: list | None = None):
    """Un calcolo che finisce solo quando scatta `via` (e conta le volte che parte)."""
    def calcola(_):
        if chiamate is not None:
            chiamate.append(1)
        via.wait(10)
        return "pronto"
    return calcola


def aspetta_che(condizione, secondi: float = 5) -> bool:
    fine = time.monotonic() + secondi
    while not condizione() and time.monotonic() < fine:
        time.sleep(0.01)
    return condizione()


# ---------------------------------------------------------------- nel calcolo
def test_un_calcolo_che_finisce_entro_l_attesa_da_subito_il_risultato(percorso):
    come_richiesta(2.0)
    chiamate = []

    def breve(_):
        chiamate.append(1)
        time.sleep(0.2)
        return "pronto"
    inizio = time.monotonic()
    assert chiedi(percorso, "k", breve) == "pronto"              # prima: «sto calcolando» subito, e l'app riprovava dopo 3 secondi
    assert time.monotonic() - inizio < 1.5 and chiamate == [1]


def test_un_calcolo_lento_risponde_sto_calcolando_dopo_l_attesa(percorso):
    come_richiesta(0.4)
    via, chiamate = threading.Event(), []
    inizio = time.monotonic()
    try:
        with pytest.raises(calcolo.InCalcolo) as e:
            chiedi(percorso, "k", fermo_fino_a(via, chiamate))
        passati = time.monotonic() - inizio
        assert 0.35 <= passati < 1.5                            # ha aspettato l'attesa, non di più
        assert type(e.value) is calcolo.InCalcolo and str(e.value) == "Sto calcolando: ci vuole qualche secondo"
        # 3 meno i secondi aspettati, arrotondato (almeno 1): fra il valore per tutto il tempo passato qui e 3. Non esatto: con il
        # processore occupato il risveglio può tardare di qualche decimo (0,4 + 0,1 secondi danno già 2)
        assert max(1, round(3 - passati)) <= e.value.riprova_tra <= 3
    finally:
        via.set()
        attendi_fine()
    assert chiedi(percorso, "k", fermo_fino_a(via, chiamate)) == "pronto" and chiamate == [1]     # il calcolo è andato avanti da solo


def test_dopo_l_attesa_l_app_riprova_prima_di_quanto_ha_gia_aspettato(percorso):
    """Chi ha aspettato 2 secondi senza risultato non deve riprovare dopo altri 3 (5 in tutto, peggio di prima): riprova dopo 1,
    così i tentativi restano uno ogni 3 secondi come senza attesa."""
    via = threading.Event()
    db = archivio.apri(percorso)                                 # aperto prima: l'attesa è quasi tutta dentro il calcolo
    try:
        come_richiesta(2.0)
        with pytest.raises(calcolo.InCalcolo) as e:
            calcolo.ottieni("k", fermo_fino_a(via), db)
        assert e.value.riprova_tra == 1                          # prima: 3 (vale 1 per un'attesa da 1,5 secondi in su)
    finally:
        db.close()
        via.set()
        attendi_fine()


def test_riprova_tra_toglie_tutta_l_attesa_della_richiesta(percorso):
    """Oggi dopo un aggiornamento aspetta due calcoli in fila (previsioni, poi formazione): se il primo arriva dopo 1,2 secondi e
    il secondo non arriva, la richiesta ha aspettato 2 secondi in tutto e l'app deve riprovare dopo 1, non dopo 2 o 3."""
    via = threading.Event()

    def primo(_):
        time.sleep(1.2)
        return "previsioni"
    db = archivio.apri(percorso)                                 # aperto prima: le due attese coprono quasi tutti i 2 secondi
    try:
        come_richiesta(2.0)
        assert calcolo.ottieni("primo", primo, db) == "previsioni"
        with pytest.raises(calcolo.InCalcolo) as e:
            calcolo.ottieni("secondo", fermo_fino_a(via), db)
        assert e.value.riprova_tra == 1                          # prima: 2 (si toglieva solo l'ultima attesa, 0,8 secondi)
    finally:
        db.close()
        via.set()
        attendi_fine()


def test_due_richieste_per_lo_stesso_calcolo_aspettano_un_calcolo_solo(percorso):
    chiamate, risultati, errori = [], [], []

    def breve(_):
        chiamate.append(1)
        time.sleep(0.3)
        return "pronto"

    def richiesta():
        come_richiesta(2.0)
        try:
            risultati.append(chiedi(percorso, "k", breve))
        except Exception as e:  # noqa: BLE001 - l'errore si guarda sotto
            errori.append(e)
    fili = [threading.Thread(target=richiesta) for _ in range(2)]
    [f.start() for f in fili]
    [f.join(10) for f in fili]
    assert errori == [] and risultati == ["pronto", "pronto"] and chiamate == [1]


def test_l_attesa_vale_per_tutta_la_richiesta_non_per_ogni_calcolo(percorso):
    come_richiesta(0.4)
    via = threading.Event()
    try:
        inizio = time.monotonic()
        with pytest.raises(calcolo.InCalcolo):
            chiedi(percorso, "primo", fermo_fino_a(via))
        assert time.monotonic() - inizio >= 0.35
        db = archivio.apri(percorso)
        try:
            inizio = time.monotonic()
            with pytest.raises(calcolo.InCalcolo):              # l'attesa della richiesta è finita: il secondo calcolo non ne ha altra
                calcolo.ottieni("secondo", fermo_fino_a(via), db)
            assert time.monotonic() - inizio < 0.3
        finally:
            db.close()
    finally:
        via.set()
        attendi_fine()


def test_oltre_il_tetto_di_chi_aspetta_si_risponde_subito(percorso):
    via, chiamate, esiti = threading.Event(), [], []

    def ferma(i):
        come_richiesta(10.0)
        try:
            esiti.append(chiedi(percorso, ("fermo", i), fermo_fino_a(via)))
        except Exception as e:  # noqa: BLE001 - l'esito si guarda sotto
            esiti.append(e)
    fili = [threading.Thread(target=ferma, args=(i,)) for i in range(calcolo.MAX_IN_ATTESA)]
    try:
        [f.start() for f in fili]
        assert aspetta_che(lambda: getattr(calcolo, "_in_attesa", 0) == calcolo.MAX_IN_ATTESA), "le richieste non aspettano"
        come_richiesta(10.0)
        inizio = time.monotonic()
        with pytest.raises(calcolo.InCalcolo):                  # una di troppo: «sto calcolando» subito, come prima
            chiedi(percorso, "oltre", fermo_fino_a(via, chiamate))
        assert time.monotonic() - inizio < 2.0                  # con posto avrebbe aspettato 10 secondi
    finally:
        via.set()
        [f.join(10) for f in fili]
        attendi_fine()
    assert esiti == ["pronto"] * calcolo.MAX_IN_ATTESA         # chi aspettava ha avuto il risultato appena pronto
    assert chiamate == [1] and calcolo.cache.get("oltre") == "pronto"         # il calcolo di quella di troppo è partito lo stesso
    assert calcolo._in_attesa == 0


def test_un_errore_del_calcolo_arriva_subito_a_chi_aspetta(percorso):
    come_richiesta(5.0)

    def rotto(_):
        time.sleep(0.1)
        raise ValueError("Non si riesce a formare una squadra")
    inizio = time.monotonic()
    with pytest.raises(ValueError, match="formare una squadra"):
        chiedi(percorso, "k", rotto)
    assert time.monotonic() - inizio < 2.0                      # non resta fermo fino alla fine dell'attesa
    assert calcolo._in_attesa == 0


def test_un_errore_arriva_a_tutte_le_richieste_che_aspettavano_lo_stesso_calcolo(percorso):
    """Il calcolo fallisce mentre tre richieste lo aspettano: l'errore arriva a tutte e tre (prima solo alla prima; le altre avevano
    il 202 e al tentativo dopo il calcolo ripartiva). Poi non resta: chi chiede dopo fa ripartire il calcolo."""
    via, chiamate, esiti = threading.Event(), [], []

    def rotto(_):
        chiamate.append(1)
        via.wait(10)
        raise ValueError("Non si riesce a formare una squadra")

    def richiesta():
        come_richiesta(5.0)
        try:
            esiti.append(chiedi(percorso, "k", rotto))
        except Exception as e:  # noqa: BLE001 - l'esito si guarda sotto
            esiti.append(e)
    fili = [threading.Thread(target=richiesta) for _ in range(3)]
    try:
        [f.start() for f in fili]
        assert aspetta_che(lambda: calcolo._in_attesa == 3), "le richieste non aspettano"
    finally:
        via.set()
        [f.join(10) for f in fili]
    assert [type(e) for e in esiti] == [ValueError] * 3 and all("formare una squadra" in str(e) for e in esiti)
    assert chiamate == [1]
    calcolo.in_coda.set(True)                                    # una richiesta dopo, senza attesa: non riceve l'errore vecchio
    with pytest.raises(calcolo.InCalcolo):
        chiedi(percorso, "k", rotto)
    attendi_fine()
    assert chiamate == [1, 1]                                    # il calcolo è ripartito


def test_un_utente_oltre_i_suoi_calcoli_non_aspetta(percorso):
    """Oltre `limiti.MAX_CALCOLI_UTENTE` il calcolo non entra in coda: non c'è niente da aspettare, il 202 arriva subito."""
    via = threading.Event()
    try:
        with da_utente(1):
            calcolo.in_coda.set(True)
            for i in range(limiti.MAX_CALCOLI_UTENTE):
                with pytest.raises(calcolo.InCalcolo):
                    chiedi(percorso, ("a", i), fermo_fino_a(via))
            come_richiesta(5.0)
            inizio = time.monotonic()
            with pytest.raises(calcolo.InCalcolo):
                chiedi(percorso, ("a", "di troppo"), fermo_fino_a(via))
            assert time.monotonic() - inizio < 2.0              # aspettando sarebbero 5 secondi
    finally:
        via.set()
        attendi_fine()


# ---------------------------------------------------------------- sola cache (il token del widget)
def sola_cache(percorso, chiave):
    """Come il token del widget: legge solo la cache, non fa partire calcoli."""
    gettone = calcolo.solo_cache.set(True)
    try:
        return chiedi(percorso, chiave, lambda d: "calcolato dal widget")
    finally:
        calcolo.solo_cache.reset(gettone)


def test_il_widget_aspetta_un_calcolo_in_coda_che_finisce_presto(percorso):
    via = threading.Event()
    calcolo.in_coda.set(True)
    with pytest.raises(calcolo.InCalcolo):                      # lo chiede l'app con la sessione: parte in coda
        chiedi(percorso, "k", fermo_fino_a(via))
    threading.Timer(0.3, via.set).start()
    come_richiesta(2.0)
    inizio = time.monotonic()
    assert sola_cache(percorso, "k") == "pronto"               # prima: 202 subito
    assert time.monotonic() - inizio < 1.5


def test_il_widget_aspetta_anche_il_calcolo_del_riscaldamento(percorso):
    """Il riscaldamento calcola fuori dalla coda (nel suo thread, subito): il widget aspetta anche quello."""
    via, partito = threading.Event(), threading.Event()

    def riscalda():
        partito.set()
        via.wait(10)
        return "pronto"
    filo = threading.Thread(target=chiedi, args=(percorso, "k", lambda d: riscalda()))
    filo.start()
    try:
        assert partito.wait(5)
        threading.Timer(0.3, via.set).start()
        come_richiesta(2.0)
        assert sola_cache(percorso, "k") == "pronto"
    finally:
        via.set()
        filo.join(10)


def test_le_parti_facoltative_di_oggi_e_del_widget_non_aspettano(percorso):
    """Svincolato e scambio (widget._opzionale, anche in Da fare di Oggi) non devono mai far aspettare: se il loro calcolo è in
    corso (per esempio nel riscaldamento) la parte va in `mancano` subito, anche se la richiesta potrebbe aspettare."""
    from fanta import widget
    via = threading.Event()
    calcolo.in_coda.set(True)
    with pytest.raises(calcolo.InCalcolo):
        chiedi(percorso, "svincolato", fermo_fino_a(via))         # il calcolo della parte facoltativa è in coda
    come_richiesta(5.0)
    mancano = []
    db = archivio.apri(percorso)
    try:
        inizio = time.monotonic()
        assert widget._opzionale(mancano, "svincolato", lambda: calcolo.ottieni("svincolato", fermo_fino_a(via), db)) is None
        assert time.monotonic() - inizio < 2.0 and mancano == ["svincolato"]          # aspettando sarebbero 5 secondi
    finally:
        db.close()
        via.set()
        attendi_fine()


def test_il_widget_non_aspetta_se_nessuno_sta_calcolando(percorso):
    come_richiesta(5.0)
    inizio = time.monotonic()
    with pytest.raises(calcolo.NonPronto):                      # niente da aspettare: il 202 «non ancora pronti» subito, come prima
        sola_cache(percorso, "k")
    assert time.monotonic() - inizio < 2.0 and calcolo.in_corso() == 0          # aspettando sarebbero 5 secondi


# ---------------------------------------------------------------- dal server
def test_la_formazione_aspetta_un_calcolo_breve_e_risponde_subito(formazione_lenta):  # noqa: F811 (fixture importata)
    a, _ = nuovo_utente("utentea")
    prepara(a)
    threading.Timer(0.3, formazione_lenta["via"].set).start()
    r = a.get("/api/formazione")
    assert r.status_code == 200 and r.json()["squadra"] == "Mia"          # prima: 202, e il risultato solo al giro dopo
    assert formazione_lenta["chiamate"] == 1


def test_l_analisi_di_uno_scambio_non_aspetta_tenendo_il_suo_posto(formazione_lenta, monkeypatch):  # noqa: F811 (fixture importata)
    """Le analisi di scambi hanno pochi posti in tutto il server e non devono occupare il server ad aspettare (limiti.analisi_scambio):
    con un calcolo in coda il 202 arriva subito, come prima, e il posto si libera."""
    from fanta import consigli
    via = threading.Event()
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: calcolo.ottieni(("valori di prova",), fermo_fino_a(via), db))
    a, _ = nuovo_utente("utentea")
    prepara(a)
    try:
        inizio = time.monotonic()
        r = a.get("/api/scambi/analizza", params={"con": "Loro", "do": "1", "ricevo": "2"})
        assert r.status_code == 202 and r.json()["calcolo"] == "in_corso"
        assert time.monotonic() - inizio < 1.5                  # aspettando sarebbero 2 secondi
    finally:
        via.set()
        formazione_lenta["via"].set()
        attendi_fine()


def test_un_calcolo_lento_dal_server_da_lo_stesso_202_dopo_l_attesa(formazione_lenta, monkeypatch):  # noqa: F811 (fixture importata)
    monkeypatch.setattr(calcolo, "ATTESA_MAX", 0.4)
    a, _ = nuovo_utente("utentea")
    prepara(a)
    try:
        inizio = time.monotonic()
        r = a.get("/api/formazione")
        passati = time.monotonic() - inizio
        assert r.status_code == 202 and passati >= 0.35
        # web, iPhone e widget leggono questi campi: restano gli stessi, con gli stessi tipi
        corpo = r.json()
        assert set(corpo) == {"calcolo", "detail", "riprova_tra"} and corpo["calcolo"] == "in_corso"
        assert corpo["detail"] == "Sto calcolando: ci vuole qualche secondo"
        assert isinstance(corpo["riprova_tra"], int) and 1 <= corpo["riprova_tra"] <= 3      # 3 meno i secondi aspettati, almeno 1
        assert r.headers["retry-after"] == str(corpo["riprova_tra"]) and r.headers["cache-control"] == "no-store"
    finally:
        formazione_lenta["via"].set()
        attendi_fine()
