"""Gestione per chi gestisce il server (#894): l'avviso con i posti pieni (o già promessi agli inviti aperti) prima di creare un
invito; gli inviti aperti con la frase del server (creato, scade, posti liberi) e il loro annullamento, solo per chi gestisce; le
richieste senza nessun accesso verso le rotte dell'app contate a parte, tutti gli altri 401 fra le rifiutate; le richieste più lente
solo delle parti dell'app; la frase sulle fonti spente detta una volta sola, con la sua chiave."""
import contextlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from fanta import account, fonti_attive, frasi, registro, rotte_account, server

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
def test_con_un_posto_libero_e_nessun_invito_aperto_nessun_avviso(titolare):
    r = titolare.get("/api/admin/utenti").json()
    assert r["massimo"] == 2 and len(r["utenti"]) == 1
    assert r["avviso"] is None and r["avviso_frase"] is None


def test_gli_inviti_aperti_tengono_i_posti(titolare, monkeypatch):
    """3 utenti su 4 e un invito aperto: l'ultimo posto è già promesso, chi riceve un invito in più può trovare le registrazioni
    chiuse. Lo dice prima di creare il secondo invito e dopo averlo creato."""
    monkeypatch.setenv("MAX_UTENTI", "4")
    registra(cliente(), "luca")
    registra(cliente(), "sara")
    assert titolare.get("/api/admin/utenti").json()["avviso"] is None              # 3 su 4, nessun invito aperto
    primo = titolare.post("/api/admin/inviti", json={"etichetta": "Anna"}).json()
    atteso = {"chiave": "admin.posti_promessi", "param": {"n": 1, "utenti": 3, "massimo": 4}}
    assert primo["avviso_frase"] == atteso, primo
    assert primo["avviso"].startswith("Posti quasi pieni: 3 su 4 presi, e 1 posto è già in un invito aperto."), primo["avviso"]
    assert "registrazioni chiuse" in primo["avviso"]
    r = titolare.get("/api/admin/utenti").json()
    assert r["avviso_frase"] == atteso                                               # prima del secondo invito
    secondo = titolare.post("/api/admin/inviti", json={"etichetta": "Piero"}).json()
    assert secondo["avviso_frase"] == {"chiave": "admin.posti_promessi", "param": {"n": 2, "utenti": 3, "massimo": 4}}
    assert "2 posti sono già in inviti aperti" in secondo["avviso"], secondo["avviso"]


def test_contano_solo_i_posti_degli_inviti_ancora_buoni(titolare, monkeypatch):
    """Un invito annullato, uno scaduto e uno già usato non tengono posti; uno per tre amici ne tiene tre."""
    monkeypatch.setenv("MAX_UTENTI", "5")
    with contextlib.closing(account.apri()) as db:
        account.crea_invito(db, "annullato")
        annullato = db.execute("SELECT id FROM inviti WHERE etichetta = 'annullato'").fetchone()[0]
        account.revoca_invito(db, annullato)
        account.crea_invito(db, "scaduto", adesso=datetime.now(timezone.utc) - timedelta(days=8))
    registra(cliente(), "luca")                                                      # usa il suo invito
    assert titolare.get("/api/admin/utenti").json()["avviso"] is None              # 2 su 5, nessun posto promesso
    titolare.post("/api/admin/inviti", json={"etichetta": "amici", "usi": 3})
    r = titolare.get("/api/admin/utenti").json()
    assert r["avviso_frase"] == {"chiave": "admin.posti_promessi", "param": {"n": 3, "utenti": 2, "massimo": 5}}, r


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


# ---------------------------------------------------------------- inviti aperti, con «Annulla» (#894, punto 1)
APERTO = {"id": 1, "etichetta": "Sara", "ruolo": "utente", "creato": "2026-11-25T09:00:00+00:00", "scade": "2026-12-02T09:00:00+00:00",
          "usi": 0, "usi_max": 1, "stato": "attivo"}


def giorno(sigla: str, n: int, mese: str) -> dict:
    return {"chiave": "data.giorno_mese", "param": {"giorno": {"chiave": f"giorno.{sigla}", "param": {}}, "n": n,
                                                    "mese": {"chiave": f"mese.{mese}", "param": {}}}}


def test_un_invito_aperto_dice_quando_e_nato_e_quando_scade():
    """La frase la scrive il server (la web la mostra): i due giorni come li scrive l'app, «mer 25 nov», con la chiave per tradurla."""
    f = rotte_account.dettaglio_invito(APERTO)
    assert f == "Creato mer 25 nov, scade mer 2 dic.", f
    assert frasi.di(f) == {"chiave": "admin.invito_aperto", "param": {"creato": giorno("mer", 25, "nov"), "scade": giorno("mer", 2, "dic")}}


def test_i_giorni_dell_invito_sono_nell_ora_italiana():
    """Il server salva l'ora in UTC: alle 23:30 UTC in Italia è già il giorno dopo."""
    tardi = APERTO | {"creato": "2026-11-25T23:30:00+00:00", "scade": "2026-12-02T23:30:00+00:00"}
    assert rotte_account.dettaglio_invito(tardi) == "Creato gio 26 nov, scade gio 3 dic."


@pytest.mark.parametrize("usi, usi_max, posti", [(1, 3, "2 posti liberi su 3."), (1, 2, "1 posto libero su 2."), (0, 30, "30 posti liberi su 30.")])
def test_un_invito_per_piu_amici_dice_i_posti_liberi(usi, usi_max, posti):
    f = rotte_account.dettaglio_invito(APERTO | {"usi": usi, "usi_max": usi_max})
    assert f == "Creato mer 25 nov, scade mer 2 dic. " + posti, f
    assert frasi.di(f)["chiave"] == "admin.invito_aperto_posti"
    assert frasi.di(f)["param"] | {"creato": None, "scade": None} == {"creato": None, "scade": None, "n": usi_max - usi, "posti": usi_max}


@pytest.mark.parametrize("stato", ["finito", "scaduto", "revocato"])
def test_un_invito_chiuso_non_ha_la_frase(stato):
    assert rotte_account.dettaglio_invito(APERTO | {"stato": stato}) is None


def registra_con(nome: str, codice: str) -> None:
    r = cliente().post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": codice})
    assert r.status_code == 200, r.text


def test_l_elenco_degli_inviti_ha_la_frase_dei_soli_aperti(titolare, monkeypatch):
    """`dettaglio` e `dettaglio_frase` in più nella risposta di sempre (nessun campo tolto): la frase per gli inviti aperti, null
    per quelli chiusi."""
    monkeypatch.setenv("MAX_UTENTI", "5")
    titolare.post("/api/admin/inviti", json={"etichetta": "Sara"})
    amici = titolare.post("/api/admin/inviti", json={"etichetta": "amici", "usi": 3}).json()
    registra_con("luca", amici["codice"])
    titolare.post("/api/admin/inviti", json={"etichetta": "Piero"})
    elenco = {i["etichetta"]: i for i in titolare.get("/api/admin/inviti").json()["inviti"]}
    assert titolare.delete(f"/api/admin/inviti/{elenco['Piero']['id']}").status_code == 200
    elenco = {i["etichetta"]: i for i in titolare.get("/api/admin/inviti").json()["inviti"]}
    for i in elenco.values():
        assert {"id", "etichetta", "ruolo", "creato", "scade", "usi", "usi_max", "stato", "dettaglio", "dettaglio_frase"} <= set(i), i
    sara, gruppo, piero = elenco["Sara"], elenco["amici"], elenco["Piero"]
    assert sara["stato"] == "attivo" and sara["dettaglio"].startswith("Creato ") and ", scade " in sara["dettaglio"], sara
    assert "posti" not in sara["dettaglio"] and sara["dettaglio_frase"]["chiave"] == "admin.invito_aperto", sara
    assert gruppo["dettaglio"].endswith(". 2 posti liberi su 3."), gruppo
    assert gruppo["dettaglio_frase"]["chiave"] == "admin.invito_aperto_posti" and gruppo["dettaglio_frase"]["param"]["n"] == 2, gruppo
    assert piero["stato"] == "revocato" and piero["dettaglio"] is None and piero["dettaglio_frase"] is None, piero


def test_annullare_un_invito_libera_il_suo_posto(titolare):
    """Due posti, uno preso da chi gestisce: con un invito aperto l'ultimo posto è promesso. Annullato l'invito, l'avviso non c'è
    più e l'invito resta nell'elenco come annullato."""
    titolare.post("/api/admin/inviti", json={"etichetta": "Sara"})
    assert titolare.get("/api/admin/utenti").json()["avviso_frase"]["chiave"] == "admin.posti_promessi"
    invito = titolare.get("/api/admin/inviti").json()["inviti"][0]
    assert titolare.delete(f"/api/admin/inviti/{invito['id']}").json() == {"ok": True}
    assert titolare.get("/api/admin/utenti").json()["avviso"] is None
    assert titolare.get("/api/admin/inviti").json()["inviti"][0]["stato"] == "revocato"


def test_un_account_normale_non_vede_ne_annulla_gli_inviti(titolare):
    titolare.post("/api/admin/inviti", json={"etichetta": "Sara"})
    amico = cliente()
    registra(amico, "luca")
    sara = lambda: next(i for i in titolare.get("/api/admin/inviti").json()["inviti"] if i["etichetta"] == "Sara")  # noqa: E731
    for r in (amico.get("/api/admin/inviti"), amico.delete(f"/api/admin/inviti/{sara()['id']}")):
        assert r.status_code == 403 and "Sara" not in r.text, r.text
    assert sara()["stato"] == "attivo"


# ---------------------------------------------------------------- contatori di «Errori recenti»
def test_le_richieste_senza_nessun_accesso_si_contano_a_parte(titolare):
    """Senza cookie né token, verso una rotta dell'app non riservata: è quello che fa la pagina prima dell'ingresso."""
    sconosciuto = cliente()
    assert sconosciuto.get("/api/account/me").status_code == 401        # la web chiede chi sei prima di mostrare l'accesso
    assert sconosciuto.get("/api/oggi").status_code == 401
    c = registro.contatori.riepilogo()
    assert (c["richieste"], c["rifiutate"], c["senza_accesso"]) == (2, 0, 2), c


@pytest.mark.parametrize("richiesta", [
    {"percorso": "/api/oggi", "intestazioni": {"Authorization": "Bearer inventato"}},          # token che non vale
    {"percorso": "/api/oggi", "intestazioni": {"Authorization": "Bearer fw_inventato"}},       # token del widget che non vale
    {"percorso": "/api/oggi", "cookie": "inventato"},                                          # cookie di una sessione che non c'è
    {"percorso": "/api/admin/registro"},                                                       # rotta riservata senza sessione
    {"percorso": "/api/stato-dati"},
    {"percorso": "/wp-login.php"},                                                             # fuori dall'app, da un programma
])
def test_gli_altri_401_restano_fra_le_rifiutate(titolare, richiesta):
    c = cliente(**richiesta.get("intestazioni", {}))
    if "cookie" in richiesta:
        c.cookies.set("fanta_sessione", richiesta["cookie"])
    assert c.get(richiesta["percorso"]).status_code == 401
    conti = registro.contatori.riepilogo()
    assert (conti["rifiutate"], conti["senza_accesso"]) == (1, 0), conti


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
        # dal catalogo, con la chiave per tradurla (`messaggio_frase`, come le altre frasi del server)
        assert r["messaggio_frase"] == {"chiave": f"fonte.spenta_{r['id']}", "param": {}}, r
        assert m == frasi.CATALOGO[f"fonte.spenta_{r['id']}"]
    assert len({r["messaggio"] for r in righe}) == len(righe)


def test_ogni_fonte_ha_la_sua_frase_nel_catalogo():
    assert {f"fonte.spenta_{k}" for k in fonti_attive.FONTI} <= set(frasi.CATALOGO)


def test_l_errore_di_una_fonte_spenta_resta_intero(spente):
    """Il messaggio di una fonte spenta che arriva da solo (aggiornamento, errore) dice ancora tutto."""
    m = fonti_attive.messaggio_spenta("understat")
    assert m.startswith("Understat è spenta") and "condizioni d'uso" in m
