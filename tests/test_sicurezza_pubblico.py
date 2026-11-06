"""Correzioni prima di rendere pubblico il codice (revisione di sicurezza del 1/11/2026). Ogni test dice quale attacco prova.
Tutto su cartelle temporanee e dati finti: nessun file vero viene toccato."""
import contextlib
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from fanta import account, immagini, limiti, percorsi, registro, rotte_account, server
from fanta.account import ErroreAccount

from test_account_http import PASSWORD, cliente, invito

SBAGLIATA = "sbagliata-sbagliata"


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


@pytest.fixture
def attese(monkeypatch):
    """Il rallentamento non dorme davvero nei test: si registra quanto avrebbe aspettato."""
    lista = []
    monkeypatch.setattr(account, "_dormi", lista.append)
    return lista


def da(ip: str, **extra) -> TestClient:
    return cliente(**{"X-Forwarded-For": ip} | extra)


def registra(c: TestClient, nome="marco"):
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200, r.text
    return r


def entra(c: TestClient, nome="marco", password=PASSWORD, **extra):
    return c.post("/api/account/accedi", json={"nome_utente": nome, "password": password} | extra)


# ================================================================ 1) blocchi degli accessi
def test_tanti_errori_con_nomi_inventati_non_chiudono_fuori_chi_ha_la_password(web, monkeypatch, attese):
    """Attacco: da pochi indirizzi, tanti accessi sbagliati con nomi inventati per superare il tetto globale e chiudere fuori
    tutti. Prima: 429 per 9 minuti a chiunque non fosse su un indirizzo noto. Ora: si rallenta, ma chi ha la password entra."""
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (20, 600))
    registra(da("9.9.9.9"))
    for i in range(30):                                          # 30 errori da 3 indirizzi (10 ciascuno, sotto il tetto per indirizzo)
        assert entra(da(f"6.6.6.{i % 3}"), f"inventato{i}", "x" * 12).status_code == 401
    assert attese and max(attese) <= account.RITARDO_SOTTO_ATTACCO[1]           # i tentativi oltre la soglia aspettano
    attese.clear()
    assert entra(da("5.5.5.5")).status_code == 200              # indirizzo e dispositivo nuovi: entra lo stesso (dopo una breve attesa)
    assert attese == [1.0]


def test_rallentamento_progressivo_con_un_tetto(web, monkeypatch, attese):
    """Il ritardo cresce con l'attacco (1 secondo per ogni soglia superata) ma non supera 3 secondi."""
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (5, 600))
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (1000, 900))
    for i in range(40):
        entra(da(f"6.6.{i}.1"), f"inventato{i}", "x" * 12)
    assert attese[0] == 1.0 and 2.0 in attese and max(attese) == 3.0


def test_dispositivo_fidato_non_e_rallentato(web, monkeypatch, attese):
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (5, 600))
    casa = da("1.1.1.1")
    registra(casa)
    for i in range(10):
        entra(da(f"6.6.{i}.1"), f"inventato{i}", "x" * 12)
    attese.clear()
    viaggio = cliente(**{"X-Forwarded-For": "8.8.8.8"})
    viaggio.cookies.set(rotte_account.COOKIE_DISPOSITIVO, casa.cookies.get(rotte_account.COOKIE_DISPOSITIVO), path="/api/account/")
    assert entra(viaggio).status_code == 200 and attese == []    # stesso dispositivo, rete diversa: niente attesa


def test_il_recupero_ha_il_suo_tetto_separato(web, monkeypatch, attese):
    """Attacco: riempire i contatori degli accessi per bloccare anche il recupero della password. Hanno contatori separati."""
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (5, 600))
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (5, 3600))
    codice = registra(da("1.1.1.1")).json()["codice_recupero"]
    for i in range(10):
        entra(da(f"6.6.{i}.1"), "marco", SBAGLIATA)
    attese.clear()
    r = da("7.7.7.7").post("/api/account/recupero", json={"nome_utente": "marco", "codice": codice, "nuova": "nuova-password-lunga"})
    assert r.status_code == 200 and attese == []


def test_tetto_per_nome_non_blocca_il_dispositivo_fidato(web, monkeypatch, attese):
    """Attacco: 50 password sbagliate su «marco» da tanti indirizzi per chiuderlo fuori un'ora. Il suo telefono (dispositivo
    fidato) entra anche da una rete nuova; un dispositivo mai visto da una rete nuova aspetta l'ora, come prima."""
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (10, 3600))
    telefono = da("1.1.1.1")
    registra(telefono)
    for i in range(10):
        assert entra(da(f"6.6.{i}.1"), "marco", SBAGLIATA).status_code == 401
    assert entra(da("7.7.7.7")).status_code == 429                                  # dispositivo nuovo, rete nuova
    in_treno = da("8.8.8.8")
    in_treno.cookies.set(rotte_account.COOKIE_DISPOSITIVO, telefono.cookies.get(rotte_account.COOKIE_DISPOSITIVO), path="/api/account/")
    assert entra(in_treno).status_code == 200                                       # il suo dispositivo fidato sì


def test_app_nativa_riceve_il_segreto_e_lo_rimanda_nell_intestazione(web, monkeypatch, attese):
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (5, 3600))
    registra(da("1.1.1.1"))
    r = entra(da("2.2.2.2"), nativo=True)
    assert r.status_code == 200 and "set-cookie" not in r.headers                   # le app native non ricevono cookie
    segreto = r.json()["dispositivo"]
    assert account.formato_dispositivo(segreto)
    for i in range(5):
        entra(da(f"6.6.{i}.1"), "marco", SBAGLIATA)
    assert entra(da("3.3.3.3"), nativo=True).status_code == 429
    r2 = entra(da("3.3.3.3", **{"X-Fanta-Dispositivo": segreto}), nativo=True)
    assert r2.status_code == 200 and r2.json()["dispositivo"] == segreto            # lo stesso segreto, rinnovato


def test_un_segreto_scelto_da_fuori_non_diventa_fidato(web, monkeypatch, attese):
    """Attacco (fissazione): mettere nel browser della vittima un segreto noto all'attaccante prima che entri. Il server non
    lo adotta: dopo l'accesso ne dà uno suo, e quello inventato non apre niente."""
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (5, 3600))
    registra(da("1.1.1.1"))
    inventato = "A" * 43
    vittima = da("2.2.2.2", **{"X-Fanta-Dispositivo": inventato})
    r = entra(vittima, nativo=True)
    assert r.status_code == 200 and r.json()["dispositivo"] != inventato
    for i in range(5):
        entra(da(f"6.6.{i}.1"), "marco", SBAGLIATA)
    assert entra(da("4.4.4.4", **{"X-Fanta-Dispositivo": inventato})).status_code == 429


def test_il_dispositivo_fidato_vale_solo_per_il_suo_titolare(web, monkeypatch, attese):
    """Attacco: entrare con il proprio account per avere un dispositivo «fidato» e poi provare password su un altro nome."""
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (5, 3600))
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (8, 900))
    registra(da("1.1.1.1"), "marco")
    attaccante = da("6.6.6.6")
    registra(attaccante, "furbo")
    esiti = [entra(attaccante, "marco", SBAGLIATA).status_code for _ in range(12)]
    assert 429 in esiti and esiti.count(401) <= 5                                     # i limiti valgono anche per lui


def test_segreti_di_formato_sbagliato_si_ignorano(web, attese):
    registra(da("1.1.1.1"))
    for brutto in ("", "x", "A" * 44, "../../etc", "A" * 42 + "!"):
        assert entra(da("2.2.2.2", **{"X-Fanta-Dispositivo": brutto})).status_code == 200


# ================================================================ 2) senza account: solo da questo computer
def _richiesta(host, intestazioni=(), destinazione="127.0.0.1:8000"):
    """Una richiesta da `host` (l'indirizzo della connessione) verso `destinazione` (l'intestazione Host; None = senza Host)."""
    voci = [(k.lower().encode(), v.encode()) for k, v in intestazioni]
    if destinazione is not None:
        voci.append((b"host", destinazione.encode()))
    return Request({"type": "http", "method": "GET", "path": "/api/stato", "query_string": b"", "client": (host, 1) if host else None,
                    "headers": voci})


@pytest.mark.parametrize("host,intestazioni,locale", [
    ("127.0.0.1", (), True), ("::1", (), True), ("127.0.0.53", (), True), ("::ffff:127.0.0.1", (), True), ("testclient", (), True),
    ("192.168.1.10", (), False), ("100.64.0.1", (), False), ("8.8.8.8", (), False), ("2001:db8::1", (), False), (None, (), False),
    ("nome-a-caso", (), False),
    ("127.0.0.1", (("X-Forwarded-For", "8.8.8.8"),), False), ("127.0.0.1", (("X-Forwarded-Proto", "https"),), False),
    ("127.0.0.1", (("X-Forwarded-Host", "esempio.it"),), False), ("127.0.0.1", (("Forwarded", "for=8.8.8.8"),), False),
    ("127.0.0.1", (("X-Real-IP", "8.8.8.8"),), False),
])
def test_richiesta_locale(host, intestazioni, locale):
    assert rotte_account.richiesta_locale(_richiesta(host, intestazioni)) is locale


@pytest.mark.parametrize("destinazione,locale", [
    ("127.0.0.1", True), ("127.0.0.1:8000", True), ("localhost", True), ("localhost:8000", True), ("LocalHost:8000", True),
    ("[::1]", True), ("[::1]:8000", True),
    (None, False), ("", False), ("rebind.example", False), ("rebind.example:8000", False), ("127.0.0.1.nip.io:8000", False),
    ("localhost.rebind.example", False), ("0.0.0.0:8000", False), ("127.0.0.1:8000@evil", False), ("127.0.0.1:abc", False),
    ("127.0.0.1:8000, evil", False), ("::1", False), ("testserver", False),
])
def test_senza_account_conta_anche_l_indirizzo_scritto_nella_richiesta(destinazione, locale):
    """Attacco «DNS rebinding»: una pagina di un altro sito fa puntare il suo nome a 127.0.0.1 e chiama il server locale dal browser.
    La connessione arriva da questo computer, ma l'intestazione Host porta il nome dell'altro sito: si rifiuta."""
    assert rotte_account.richiesta_locale(_richiesta("127.0.0.1", (), destinazione)) is locale


def test_il_client_di_prova_resta_locale():
    """Il client di prova di Starlette («testclient» verso «testserver») non esiste in un server vero: resta locale come prima."""
    assert rotte_account.richiesta_locale(_richiesta("testclient", (), "testserver")) is True
    assert rotte_account.richiesta_locale(_richiesta("127.0.0.1", (), "testserver")) is False


def test_senza_account_un_nome_di_un_altro_sito_riceve_403(monkeypatch, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    altro = TestClient(server.app, headers={"X-Fanta": "1", "Sec-Fetch-Site": "same-origin"}, client=("127.0.0.1", 4000),
                       base_url="http://rebind.example:8000")
    for metodo, percorso in (("GET", "/api/regole"), ("GET", "/api/backup"), ("PUT", "/api/regole"), ("GET", "/")):
        r = altro.request(metodo, percorso, json={} if metodo == "PUT" else None)
        assert r.status_code == 403 and r.json()["detail"] == rotte_account.SOLO_LOCALE, (metodo, percorso)
    for indirizzo in ("http://127.0.0.1:8000", "http://localhost:8000", "http://[::1]:8000"):
        qui = TestClient(server.app, headers={"X-Fanta": "1"}, client=("127.0.0.1", 4000), base_url=indirizzo)
        assert qui.get("/api/regole").status_code == 200, indirizzo


def test_con_gli_account_l_indirizzo_scritto_non_cambia_niente(web):
    """Con FANTA_MULTIUTENTE=1 il server sta dietro il proxy con il suo nome pubblico: il controllo dell'Host non si applica."""
    altro = TestClient(server.app, headers={"X-Fanta": "1"}, base_url="https://app.esempio.it")
    r = altro.get("/api/regole")
    assert r.status_code == 401 and r.json()["detail"] == "Accesso richiesto"


def test_senza_account_da_fuori_403_da_qui_si(monkeypatch, dati_isolati):
    """Attacco: raggiungere un server lasciato senza account (FANTA_MULTIUTENTE spento) da un'altra macchina o attraverso un
    proxy (Funnel, Caddy...). Lì chiunque sarebbe amministratore: si risponde 403 a tutto ciò che non è diretto da qui."""
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    da_fuori = TestClient(server.app, headers={"X-Fanta": "1"}, client=("203.0.113.5", 4000))
    for metodo, percorso in (("GET", "/api/account/me"), ("POST", "/api/aggiorna"), ("GET", "/"), ("GET", "/api/admin/utenti")):
        r = da_fuori.request(metodo, percorso)
        assert r.status_code == 403 and r.json()["detail"] == rotte_account.SOLO_LOCALE, percorso
    via_proxy = TestClient(server.app, headers={"X-Fanta": "1", "X-Forwarded-For": "203.0.113.5"}, client=("127.0.0.1", 4000))
    assert via_proxy.get("/api/account/me").status_code == 403
    qui = TestClient(server.app, headers={"X-Fanta": "1"}, client=("127.0.0.1", 4000), base_url="http://127.0.0.1:8000")
    assert qui.get("/api/account/me").status_code == 200


def test_avviso_all_avvio_senza_account(monkeypatch, dati_isolati, caplog):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server.riscaldamento, "attivo", lambda: False)
    monkeypatch.setenv("FANTA_LIVE", "0")
    with caplog.at_level("WARNING"), TestClient(server.app):
        pass
    assert any("FANTA_MULTIUTENTE=1" in r.getMessage() for r in caplog.records)


def test_modello_del_servizio_accende_gli_account():
    testo = (percorsi.RADICE / "script" / "server" / "fantacalcio.service").read_text(encoding="utf-8")
    assert "FANTA_MULTIUTENTE=1" in testo


# ================================================================ 3) messaggi d'errore
def _richiesta_vuota():
    return Request({"type": "http", "method": "GET", "path": "/api/prova", "query_string": b"", "headers": []})


def _corpo(risposta):
    import json
    return json.loads(risposta.body)


def test_errori_di_python_non_arrivano_all_utente():
    """Attacco: mandare valori storti per leggere dettagli interni nel messaggio d'errore (valori ricevuti, percorsi...)."""
    for fai in (lambda: int("segreto-123"), lambda: account._data("non-una-data /home/utente/dati"),
                lambda: __import__("json").loads("{rotto")):
        try:
            fai()
        except ValueError as e:
            r = server._errore_valore(_richiesta_vuota(), e)
            corpo = _corpo(r)
            assert r.status_code == 400 and corpo["detail"] == server.RICHIESTA_NON_VALIDA
            assert "segreto" not in r.body.decode() and "/home" not in r.body.decode() and len(corpo["id_errore"]) == 8


def test_i_messaggi_scritti_per_l_utente_restano():
    try:
        immagini.salva("Squadra", "boh", b"")
    except ValueError as e:
        r = server._errore_valore(_richiesta_vuota(), e)
    assert _corpo(r)["detail"] == "Tipo di immagine non valido: stemma o maglia"


def test_errori_dell_aggiornamento_per_intero_solo_all_amministratore():
    errori = ["voti: ConnectionError: HTTPSConnectionPool(host='x', port=443): Max retries /percorso?chiave=abc", "probabili: KeyError: 'x'"]
    assert server._errori_per(errori, True) == errori
    assert server._errori_per(errori, False) == ["voti: non riuscito", "probabili: non riuscito"]


# ================================================================ 4) registri
def test_registro_di_sicurezza_scade_dopo_30_giorni(tmp_path):
    f = tmp_path / registro.FILE_SICUREZZA
    vecchio = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(timespec="seconds")
    recente = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    f.write_text(f"{vecchio} accesso nome=marco ip=1.2.3.x\n{recente} accesso nome=luca ip=5.6.7.x\n", encoding="utf-8")
    (tmp_path / f"{f.name}.1").write_text(f"{vecchio} accesso nome=anna\n", encoding="utf-8")
    registro._ultima_potatura.clear()
    registro.scrivi(f, f"{registro.adesso()} prova")
    testo = f.read_text(encoding="utf-8")
    assert "marco" not in testo and "luca" in testo and "prova" in testo
    assert not (tmp_path / f"{f.name}.1").exists()                                   # copia ruotata tutta vecchia: cancellata


@pytest.mark.parametrize("ip,atteso", [("1.2.3.4", "1.2.3.x"), ("2001:db8:1:2:3:4:5:6", "2001:db8:1:2::/64"),
                                       ("2001:db8:1:2::/64", "2001:db8:1:2::/64"), ("::ffff:9.8.7.6", "9.8.7.x"), ("boh", "?")])
def test_indirizzi_accorciati(ip, atteso):
    assert registro.accorcia_ip(ip) == atteso


# ================================================================ 5) analisi degli scambi
@pytest.fixture
def analisi_pulite(monkeypatch):
    monkeypatch.setattr(limiti, "_analisi_recenti", {})
    monkeypatch.setattr(limiti, "_analisi_in_corso", {})
    monkeypatch.setattr(limiti, "_analisi_insieme", threading.BoundedSemaphore(limiti.ANALISI_INSIEME))


def test_analisi_tetto_al_minuto_per_utente(analisi_pulite, monkeypatch):
    """Attacco: un utente chiede centinaia di analisi diverse in un minuto per occupare il processore di tutti."""
    adesso = [100.0]
    monkeypatch.setattr(limiti.time, "monotonic", lambda: adesso[0])
    marco, luca = SimpleNamespace(utente_id=1), SimpleNamespace(utente_id=2)
    for i in range(limiti.ANALISI_AL_MINUTO):
        with limiti.analisi_scambio(marco, i):
            pass
    with pytest.raises(ErroreAccount) as e:
        with limiti.analisi_scambio(marco, "nuova"):
            pass
    assert e.value.stato == 429 and 1 <= e.value.riprova_tra <= 61
    with limiti.analisi_scambio(marco, 3):          # la stessa analisi ripetuta (l'app riprova sul 202) passa
        pass
    with limiti.analisi_scambio(luca, "x"):          # gli altri utenti no: tetto per utente
        pass
    adesso[0] += 61
    with limiti.analisi_scambio(marco, "nuova"):     # passato il minuto si riparte
        pass


def test_analisi_contemporanee_limitate(analisi_pulite):
    utenti = [SimpleNamespace(utente_id=i) for i in range(5)]
    with contextlib.ExitStack() as pila:
        pila.enter_context(limiti.analisi_scambio(utenti[0], "a"))
        pila.enter_context(limiti.analisi_scambio(utenti[0], "b"))
        with pytest.raises(ErroreAccount, match="già analizzando"):              # al massimo 2 per utente
            pila.enter_context(limiti.analisi_scambio(utenti[0], "c"))
        pila.enter_context(limiti.analisi_scambio(utenti[1], "a"))
        with pytest.raises(ErroreAccount, match="altri scambi"):                  # al massimo 3 in tutto il server
            pila.enter_context(limiti.analisi_scambio(utenti[2], "a"))
    with limiti.analisi_scambio(utenti[2], "a"):                                  # finite le altre, si riparte
        pass
    assert limiti._analisi_in_corso == {}


def test_analisi_senza_account_niente_tetto_al_minuto(analisi_pulite):
    locale = SimpleNamespace(utente_id=None)
    for i in range(limiti.ANALISI_AL_MINUTO + 5):
        with limiti.analisi_scambio(locale, i):
            pass


def test_analisi_un_errore_libera_il_posto(analisi_pulite):
    marco = SimpleNamespace(utente_id=1)
    for _ in range(5):
        with pytest.raises(RuntimeError), limiti.analisi_scambio(marco, "a"):
            raise RuntimeError("calcolo rotto")
    assert limiti._analisi_in_corso == {}
