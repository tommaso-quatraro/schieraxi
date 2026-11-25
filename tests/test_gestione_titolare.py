"""Gestione per chi gestisce il server (#894): l'avviso con i posti pieni prima di creare un invito, le richieste normali prima
dell'accesso che non contano come rifiutate (i rifiuti veri sì), le richieste più lente solo delle parti dell'app, la frase sulle
fonti spente detta una volta sola."""
import contextlib

import pytest
from fastapi.testclient import TestClient

from fanta import account, fonti_attive, registro, server

PASSWORD = "una-password-lunga-9"


def cliente(**intestazioni) -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1"} | intestazioni, raise_server_exceptions=False)


def registra(c: TestClient, nome: str, amministratore=False):
    with contextlib.closing(account.apri()) as db:
        codice = account.crea_invito(db, "prova", amministratore)
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": codice})
    assert r.status_code == 200, r.text


@pytest.fixture
def titolare(multiutente, dati_isolati, monkeypatch):
    """Un server con due posti, il primo preso da chi lo gestisce."""
    monkeypatch.setenv("MAX_UTENTI", "2")
    c = cliente()
    registra(c, "capo", amministratore=True)
    registro.contatori.azzera()
    return c


# ---------------------------------------------------------------- posti pieni
def test_con_un_posto_libero_nessun_avviso(titolare):
    r = titolare.get("/api/admin/utenti").json()
    assert r["massimo"] == 2 and len(r["utenti"]) == 1
    assert r["avviso"] is None and r["avviso_frase"] is None
    invito = titolare.post("/api/admin/inviti", json={"etichetta": "Luca"}).json()
    assert invito["codice"] and invito["avviso"] is None and invito["avviso_frase"] is None


def test_con_i_posti_pieni_l_avviso_arriva_prima_e_dopo_l_invito(titolare):
    registra(cliente(), "luca")
    r = titolare.get("/api/admin/utenti").json()
    assert r["avviso"].startswith("Posti pieni: 2 utenti su 2.") and "registrazioni chiuse" in r["avviso"], r["avviso"]
    assert r["avviso_frase"] == {"chiave": "admin.posti_pieni", "param": {"n": 2, "massimo": 2}}
    invito = titolare.post("/api/admin/inviti", json={"etichetta": "Sara"})
    assert invito.status_code == 200 and invito.json()["codice"]       # si crea lo stesso: il tetto si può alzare dopo
    assert invito.json()["avviso"] == r["avviso"] and invito.json()["avviso_frase"] == r["avviso_frase"]


def test_posti_pieni_al_singolare(titolare, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "1")
    assert titolare.get("/api/admin/utenti").json()["avviso"].startswith("Posti pieni: 1 utente su 1.")


# ---------------------------------------------------------------- contatori di «Errori recenti»
def test_le_richieste_prima_dell_accesso_non_sono_rifiutate(titolare):
    sconosciuto = cliente()
    assert sconosciuto.get("/api/account/me").status_code == 401        # la web chiede chi sei prima di mostrare l'accesso
    assert sconosciuto.get("/api/oggi").status_code == 401
    assert sconosciuto.get("/api/oggi", headers={"Authorization": "Bearer scaduto"}).status_code == 401     # sessione finita
    c = registro.contatori.riepilogo()
    assert (c["richieste"], c["rifiutate"], c["senza_accesso"]) == (3, 0, 3), c


def test_i_rifiuti_veri_restano_fra_le_rifiutate(titolare):
    sconosciuto = cliente()
    codici = [sconosciuto.post("/api/account/accedi", json={"nome_utente": "capo", "password": "sbagliata-sbagliata"}).status_code
              for _ in range(6)]
    assert codici[0] == 401 and codici[-1] == 429, codici               # password sbagliata, poi troppi tentativi
    semplice = cliente()
    registra(semplice, "pippo")
    assert semplice.get("/api/admin/registro").status_code == 403       # non è chi gestisce
    c = registro.contatori.riepilogo()
    assert c["rifiutate"] == 7 and c["senza_accesso"] == 0, c


def test_le_richieste_piu_lente_sono_solo_delle_parti_dell_app(titolare):
    titolare.get("/")
    titolare.get("/stile.css")
    titolare.get("/robots.txt")
    titolare.get("/api/account/me")
    c = registro.contatori.riepilogo()
    assert [p["rotta"] for p in c["piu_lente"]] == ["/api/account/me"], c["piu_lente"]
    assert c["richieste"] == 4                                          # contate lo stesso nel totale e nei tempi


def test_il_registro_dice_le_richieste_prima_dell_accesso(titolare):
    cliente().get("/api/account/me")
    assert titolare.get("/api/admin/registro").json()["contatori"]["senza_accesso"] == 1


# ---------------------------------------------------------------- Stato dei dati, fonti spente
@pytest.fixture
def spente(monkeypatch, tmp_path):
    for k in fonti_attive.FONTI:
        monkeypatch.delenv(f"FANTA_FONTE_{k.upper()}", raising=False)
    for v in ("FANTA_LIVE", "FANTA_FOTO"):
        monkeypatch.delenv(v, raising=False)
    return tmp_path / "fonti.json"


def test_la_frase_delle_fonti_spente_non_si_ripete_a_ogni_fonte(spente):
    righe = fonti_attive.stato(spente)
    assert righe and not any(r["acceso"] for r in righe)
    for r in righe:
        m = r["messaggio"]
        assert m and "condizioni d'uso" not in m and "dati già salvati" not in m, m      # detta una volta sola, sotto l'elenco
        assert r["nome"] not in m, m                                                     # il nome è già sulla riga, col pulsante
    assert len({r["messaggio"] for r in righe}) == len(righe)


def test_l_errore_di_una_fonte_spenta_resta_intero(spente):
    """Il messaggio di una fonte spenta che arriva da solo (aggiornamento, errore) dice ancora tutto."""
    m = fonti_attive.messaggio_spenta("understat")
    assert m.startswith("Understat è spenta") and "condizioni d'uso" in m
