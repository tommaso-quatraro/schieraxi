"""Inviti per gli amici: un codice che vale per più persone (12 usi, 7 giorni), con scadenza, revoca e tetto di utenti."""
import contextlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from fanta import account, limiti
from fanta.account import ErroreAccount
from test_account_http import PASSWORD, cliente

ADESSO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(multiutente):
    with contextlib.closing(account.apri()) as d:
        yield d


def entra(db, nome, codice, adesso=ADESSO):
    return account.registra(db, nome, PASSWORD, codice, adesso=adesso)[0]


def errore(f, *a, **k) -> ErroreAccount:
    with pytest.raises(ErroreAccount) as e:
        f(*a, **k)
    return e.value


def test_codice_per_dodici_amici(db):
    codice = account.crea_invito(db, "amici", usi_max=12, adesso=ADESSO)
    for i in range(12):
        assert entra(db, f"amico{i:02d}", codice).ruolo == "utente"
    assert errore(entra, db, "amico99", codice).stato == 403                         # il tredicesimo no
    riga = db.execute("SELECT usi, usi_max, usato FROM inviti").fetchone()
    assert tuple(riga) == (12, 12, 1)
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 12


IP = "5.5.5.5"                                       # tutti dallo stesso Wi-Fi


def test_dodici_amici_dalla_stessa_rete_entrano_tutti(db):
    """La sera dell'asta tutti si iscrivono dalla stessa rete; qualcuno sbaglia prima la password. Entrano tutti e dodici: le
    iscrizioni riuscite e i moduli scritti male non contano fra i tentativi dell'indirizzo."""
    codice = account.crea_invito(db, "amici", usi_max=12, adesso=ADESSO)
    for i in range(account.REGISTRAZIONI_PER_IP[0]):                # tanti errori quanti il tetto dei tentativi dell'indirizzo
        sbagliato = ("password", f"amico{i:02d}") if i % 2 else (PASSWORD, f"a {i}")     # password troppo corta o nome non valido
        assert errore(account.registra, db, sbagliato[1], sbagliato[0], codice, ip=IP, adesso=ADESSO).stato == 400
    for i in range(12):
        assert account.registra(db, f"amico{i:02d}", PASSWORD, codice, ip=IP, adesso=ADESSO)[0].ruolo == "utente"
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 12


def test_dodici_amici_con_un_invito_a_testa_dalla_stessa_rete(db):
    for i in range(12):
        codice = account.crea_invito(db, f"amico {i}", adesso=ADESSO)
        account.registra(db, f"amico{i:02d}", PASSWORD, codice, ip=IP, adesso=ADESSO)
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 12


def test_i_tentativi_non_riusciti_contano_ancora_per_indirizzo(db):
    codice = account.crea_invito(db, "amici", usi_max=30, adesso=ADESSO)
    account.registra(db, "marco", PASSWORD, codice, ip=IP, adesso=ADESSO)
    for _ in range(account.REGISTRAZIONI_PER_IP[0]):
        assert "già preso" in errore(account.registra, db, "marco", PASSWORD, codice, ip=IP, adesso=ADESSO).messaggio
    assert errore(account.registra, db, "luca", PASSWORD, codice, ip=IP, adesso=ADESSO).stato == 429
    assert account.registra(db, "luca", PASSWORD, codice, ip="6.6.6.6", adesso=ADESSO)[0]       # un'altra rete no


def test_tetto_di_account_nuovi_per_indirizzo(db):
    """Un tetto resta anche per le iscrizioni riuscite: una lega intera (fino a MAX_SQUADRE squadre) entra dalla stessa rete in
    un'ora, oltre no."""
    assert account.ACCOUNT_PER_IP[0] >= limiti.MAX_SQUADRE and account.ACCOUNT_PER_IP[1] == account.ORA
    codice = account.crea_invito(db, "tutti", usi_max=30, adesso=ADESSO)
    for i in range(account.ACCOUNT_PER_IP[0]):
        account.registra(db, f"amico{i:02d}", PASSWORD, codice, ip=IP, adesso=ADESSO)
    assert errore(account.registra, db, "uno-di-troppo", PASSWORD, codice, ip=IP, adesso=ADESSO).stato == 429
    assert db.execute("SELECT usi FROM inviti").fetchone()[0] == account.ACCOUNT_PER_IP[0]      # il posto non si consuma


def test_tetto_di_account_controllato_anche_quando_nasce_l_account(db):
    """Due richieste insieme passano entrambe il primo controllo del tetto: vale quello dentro la transazione che crea l'account,
    e lì l'account in più non nasce."""
    codice = account.crea_invito(db, "tutti", usi_max=30, adesso=ADESSO)
    for i in range(account.ACCOUNT_PER_IP[0]):
        account.registra(db, f"amico{i:02d}", PASSWORD, codice, ip=IP, adesso=ADESSO)
    account._transazione(db)                         # come chi ha già passato il primo controllo ed entra nella transazione
    try:
        e = errore(account.crea_utente, db, "in-ritardo", "in-ritardo", "impronta", "recupero", "utente", ADESSO, ip=IP)
        assert e.stato == 429
        assert db.execute("SELECT COUNT(*) FROM utenti WHERE nome_utente = 'in-ritardo'").fetchone()[0] == 0
    finally:
        db.rollback()
    nuovo = account.crea_utente(db, "altra-rete", "altra-rete", "impronta", "recupero", "utente", ADESSO, ip="6.6.6.6")
    assert nuovo and db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == account.ACCOUNT_PER_IP[0] + 1


def test_invito_monouso_come_sempre(db):
    codice = account.crea_invito(db, "uno", adesso=ADESSO)
    entra(db, "primo", codice)
    assert errore(entra, db, "secondo", codice).stato == 403


def test_scadenza_dopo_sette_giorni(db):
    codice = account.crea_invito(db, "amici", usi_max=5, adesso=ADESSO)
    entra(db, "presto", codice, ADESSO + timedelta(days=6))
    assert errore(entra, db, "tardi", codice, ADESSO + timedelta(days=8)).stato == 403


def test_revoca_ferma_i_nuovi_ma_non_chi_e_gia_dentro(db):
    codice = account.crea_invito(db, "amici", usi_max=5, adesso=ADESSO)
    entra(db, "dentro", codice)
    account.revoca_invito(db, db.execute("SELECT id FROM inviti").fetchone()[0])
    assert errore(entra, db, "fuori", codice).stato == 403
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 1
    assert errore(account.revoca_invito, db, 999).stato == 404


def test_il_tetto_di_utenti_vale_anche_con_il_codice_multiuso(db, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "3")
    codice = account.crea_invito(db, "amici", usi_max=12, adesso=ADESSO)
    for i in range(3):
        entra(db, f"amico{i}", codice)
    assert "numero massimo" in errore(entra, db, "amico9", codice).messaggio
    assert db.execute("SELECT usi FROM inviti").fetchone()[0] == 3                   # il posto non si consuma se il tetto blocca


def test_nome_preso_non_consuma_un_posto(db):
    codice = account.crea_invito(db, "amici", usi_max=2, adesso=ADESSO)
    entra(db, "marco", codice)
    assert "già preso" in errore(entra, db, "marco", codice).messaggio
    assert db.execute("SELECT usi FROM inviti").fetchone()[0] == 1


def test_parametri_validi(db):
    for usi in (0, 31, "5", True, None, 1.5):
        assert errore(account.crea_invito, db, "x", usi_max=usi).stato == 400
    assert "una volta sola" in errore(account.crea_invito, db, "x", True, usi_max=2).messaggio     # da amministratore: monouso


def test_elenco_senza_codici_con_stato(db):
    a = account.crea_invito(db, "attivo", usi_max=3, adesso=ADESSO)
    b = account.crea_invito(db, "revocato", adesso=ADESSO)
    c = account.crea_invito(db, "finito", adesso=ADESSO)
    entra(db, "uno", c)
    account.revoca_invito(db, 2)
    righe = account.elenco_inviti(db, ADESSO)
    assert {r["etichetta"]: r["stato"] for r in righe} == {"attivo": "attivo", "revocato": "revocato", "finito": "finito"}
    assert all("codice" not in r and "codice_hash" not in r for r in righe)
    assert a.replace("-", "") not in str(righe) and b not in str(righe)
    assert account.elenco_inviti(db, ADESSO + timedelta(days=9))[-1]["stato"] == "scaduto"


def test_migrazione_inviti_vecchi(multiutente):
    percorso = account.percorsi.cartella_account() / "account.sqlite"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    vecchio = sqlite3.connect(percorso)
    for m in account.MIGRAZIONI[:6]:                 # fino a prima degli inviti con più usi
        vecchio.executescript(m)
    vecchio.execute("PRAGMA user_version = 6")
    for i, usato in enumerate((0, 1)):
        vecchio.execute("INSERT INTO inviti (codice_hash, etichetta, creato, scade, usato) VALUES (?, 'v', 'z', '2999-01-01T00:00:00+00:00', ?)", (f"h{i}", usato))
    vecchio.commit()
    vecchio.close()
    with contextlib.closing(account.apri()) as d:
        assert [tuple(r) for r in d.execute("SELECT usato, usi, usi_max, revocato FROM inviti ORDER BY id")] == [(0, 0, 1, 0), (1, 1, 1, 0)]


# ---------------------------------------------------------------- HTTP
@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


def test_rotte_admin_degli_inviti(web):
    with contextlib.closing(account.apri()) as d:
        primo = account.crea_invito(d, "io", True)
    assert web.post("/api/account/registra", json={"nome_utente": "luigi", "password": PASSWORD, "invito": primo}).status_code == 200
    r = web.post("/api/admin/inviti", json={"etichetta": "Amici", "usi": 12})
    assert r.status_code == 200 and r.json()["usi_max"] == 12 and r.json()["valido_giorni"] == 7
    codice = r.json()["codice"]
    assert web.post("/api/admin/inviti", json={"etichetta": "Uno"}).json()["usi_max"] == 1            # i client vecchi: come prima
    assert web.post("/api/admin/inviti", json={"etichetta": "x", "usi": 31}).status_code == 422
    elenco = web.get("/api/admin/inviti").json()["inviti"]
    assert [i["etichetta"] for i in elenco] == ["Uno", "Amici", "io"] and codice not in str(elenco)
    amico = cliente()
    assert amico.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": codice}).status_code == 200
    assert amico.get("/api/admin/inviti").status_code == 403                      # un amico non vede né revoca gli inviti
    assert amico.delete("/api/admin/inviti/2").status_code == 403
    assert web.delete(f"/api/admin/inviti/{elenco[1]['id']}").status_code == 200
    altro = cliente()
    assert altro.post("/api/account/registra", json={"nome_utente": "luca", "password": PASSWORD, "invito": codice}).status_code == 403
    assert web.delete("/api/admin/inviti/9999").status_code == 404
    assert cliente().get("/api/admin/inviti").status_code == 401                  # senza accesso
