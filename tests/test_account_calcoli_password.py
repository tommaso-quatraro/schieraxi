"""Il calcolo delle password (scrypt) ha pochi posti. Le richieste che lo useranno prendono prima un posto in fila, PRIMA di contare
qualunque tentativo: oltre CALCOLI_INSIEME + ATTESE_MASSIME la risposta è subito «riprova» (429) e nessun contatore cresce.
Chi è noto (dispositivo fidato o indirizzo già visto per quel nome) non ha questo tetto: aspetta come prima. Un accesso respinto
perché il server è occupato non conta come tentativo sbagliato. Cartelle temporanee e dati finti."""
import contextlib
import threading
import time

import pytest

from fanta import account, rotte_account

from test_account_http import PASSWORD, cliente, invito

SBAGLIATA = "sbagliata-sbagliata"


def _aspetta(condizione, secondi: float) -> bool:
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        if condizione():
            return True
        time.sleep(0.01)
    return condizione()


def da(ip: str) -> object:
    return cliente(**{"X-Forwarded-For": ip})


def entra(c, password=PASSWORD, nome="marco"):
    return c.post("/api/account/accedi", json={"nome_utente": nome, "password": password})


def tentativi() -> int:
    with contextlib.closing(account.apri()) as db:
        return db.execute("SELECT COUNT(*) FROM tentativi").fetchone()[0]


@pytest.fixture
def web(multiutente, dati_isolati):
    return da("1.1.1.1")


def test_account_dispositivo_fidato_entra_anche_con_i_calcoli_pieni(web, monkeypatch):
    monkeypatch.setattr(account, "ATTESE_MASSIME", 2)               # in fila al massimo 2 calcoli + 2 attese
    r = web.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200
    segreto = web.cookies.get(rotte_account.COOKIE_DISPOSITIVO)
    posti = threading.BoundedSemaphore(2)
    monkeypatch.setattr(account, "_calcoli", posti)
    posti.acquire()
    posti.acquire()                                                  # tutti e due i calcoli occupati a lungo
    esiti = {}

    def prova(nome, c, password):
        esiti[nome] = entra(c, password).status_code
    fidato_c = da("8.8.8.8")
    fidato_c.cookies.set(rotte_account.COOKIE_DISPOSITIVO, segreto, path="/api/account/")
    altri = [threading.Thread(target=prova, args=(f"altro{i}", da(f"6.6.6.{i + 1}"), f"{SBAGLIATA}-{i}")) for i in range(4)]
    estraneo = threading.Thread(target=prova, args=("estraneo", da("7.7.7.7"), PASSWORD))
    fidato = threading.Thread(target=prova, args=("fidato", fidato_c, PASSWORD))
    try:
        for t in altri:
            t.start()
        _aspetta(lambda: getattr(account, "_prenotati", 0) >= 4, 3.0)          # la fila è piena
        estraneo.start()
        estraneo.join(3)
        estraneo_subito = not estraneo.is_alive()
        fidato.start()
        time.sleep(0.3)
        fidato_aspetta = fidato.is_alive() and "fidato" not in esiti           # non respinto: aspetta il suo turno
    finally:
        posti.release()
        posti.release()
        for t in altri + [estraneo, fidato]:
            if t.is_alive() or t.ident:
                t.join(30)
    assert estraneo_subito and esiti["estraneo"] == 429
    assert fidato_aspetta and esiti["fidato"] == 200


def test_account_server_occupato_non_consuma_i_tetti(web, monkeypatch):
    r = web.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()})
    assert r.status_code == 200
    prima = tentativi()
    monkeypatch.setattr(account, "_prenotati", 10 ** 6, raising=False)     # fila piena
    sconosciuto, nuovo = da("7.7.7.7"), da("9.9.9.9")
    accessi = [entra(sconosciuto, SBAGLIATA) for _ in range(7)]
    cambi = [web.post("/api/account/cambia-password", json={"attuale": SBAGLIATA, "nuova": "nuova-password-lunga"}) for _ in range(12)]
    iscrizioni = [nuovo.post("/api/account/registra", json={"nome_utente": f"luca{i}", "password": PASSWORD, "invito": "ZZZZZ-ZZZZZ"})
                  for i in range(7)]
    for risposta in accessi + cambi + iscrizioni:
        assert risposta.status_code == 429 and risposta.json()["detail"] == account.OCCUPATO, risposta.text
        assert int(risposta.headers["retry-after"]) >= 1
    assert tentativi() == prima                                              # nessun contatore è cresciuto
    monkeypatch.setattr(account, "_prenotati", 0, raising=False)            # fila libera
    assert entra(sconosciuto).status_code == 200                             # nessuna attesa crescente
    assert web.post("/api/account/cambia-password", json={"attuale": PASSWORD, "nuova": "nuova-password-lunga"}).status_code == 200
    r = nuovo.post("/api/account/registra", json={"nome_utente": "luca", "password": PASSWORD, "invito": "ZZZZZ-ZZZZZ"})
    assert r.status_code == 403                                              # invito sbagliato, non «troppi inviti sbagliati»


def test_account_posto_per_il_calcolo_vale_una_volta_per_richiesta(monkeypatch):
    monkeypatch.setattr(account, "ATTESE_MASSIME", 0)
    monkeypatch.setattr(account, "CALCOLI_INSIEME", 1)
    with account.posto_per_il_calcolo():
        with account.posto_per_il_calcolo():                                # nella stessa richiesta non si conta due volte
            assert account._prenotati == 1
        esiti = []

        def altro():
            try:
                with account.posto_per_il_calcolo():
                    esiti.append("dentro")
            except account.ErroreAccount as e:
                esiti.append(e.stato)
        t = threading.Thread(target=altro)
        t.start()
        t.join(5)
        assert esiti == [429]
        with account.posto_per_il_calcolo(esente=True):                     # chi è noto non ha il tetto
            pass
    assert account._prenotati == 0


def test_account_accesso_con_i_calcoli_occupati_non_conta_come_sbagliato(web, monkeypatch):
    assert web.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito()}).status_code == 200
    vero = account._scrypt

    def occupato(*a, **k):
        raise account.ErroreAccount(account.OCCUPATO, 503, 5)
    monkeypatch.setattr(account, "_scrypt", occupato)
    for _ in range(6):
        assert entra(da("7.7.7.7")).status_code in (429, 503)
    monkeypatch.setattr(account, "_scrypt", vero)
    r = entra(da("7.7.7.7"))
    assert r.status_code == 200, r.text                      # nessuna attesa crescente per colpa del server occupato
