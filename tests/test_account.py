"""Account: password, inviti, sessioni, recupero, limiti di tentativi (la logica, senza HTTP)."""
import contextlib
from datetime import datetime, timedelta, timezone

import pytest

from fanta import account
from fanta.account import ErroreAccount

PASSWORD = "una-password-lunga-9"
ADESSO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(multiutente):
    with contextlib.closing(account.apri()) as d:
        yield d


def nuovo(db, nome="marco", password=PASSWORD, admin=False):
    """Registra un utente con un invito fresco: (utente, token, codice di recupero)."""
    inv = account.crea_invito(db, "prova", admin, ADESSO)
    return account.registra(db, nome, password, inv, adesso=ADESSO)


def errore(funzione, *args, **kw) -> ErroreAccount:
    with pytest.raises(ErroreAccount) as e:
        funzione(*args, **kw)
    return e.value


# ---------------------------------------------------------------- database
def test_database_e_migrazioni(db, multiutente):
    assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
    tabelle = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"utenti", "sessioni", "inviti", "reset_password"} <= tabelle
    with contextlib.closing(account.apri()) as ancora:             # riaprire non rifà le migrazioni
        assert ancora.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)
    db.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError):
        account.apri()


def test_interruttore_spento_di_default(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    assert not account.multiutente()
    monkeypatch.setenv("FANTA_MULTIUTENTE", "0")
    assert not account.multiutente()
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    assert account.multiutente()


# ---------------------------------------------------------------- password
def test_password_hash_e_verifica(multiutente):
    h = account.hash_password(PASSWORD)
    assert h.startswith("scrypt$") and PASSWORD not in h
    assert account.verifica_password(PASSWORD, h)
    assert not account.verifica_password(PASSWORD + "x", h)
    assert not account.verifica_password("", h)
    assert account.hash_password(PASSWORD) != h                     # sale diverso ogni volta
    assert not account.verifica_password(PASSWORD, "non-e-un-hash")
    assert not account.verifica_password(PASSWORD, "md5$1$2$3$aa$bb")


def test_la_verifica_usa_i_parametri_salvati(multiutente, monkeypatch):
    h = account.hash_password(PASSWORD)
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 5, "r": 8, "p": 1})        # un domani si alza il costo: le vecchie valgono ancora
    assert account.verifica_password(PASSWORD, h)
    assert account.hash_password(PASSWORD).split("$")[1] == str(2 ** 5)


@pytest.mark.parametrize("password", ["corta", "123456789012", "aaaaaaaaaaaa", "Password123", "fantacalcio", "schieraxi", "marco12345", "x" * 201])
def test_password_rifiutate(password):
    with pytest.raises(ErroreAccount):
        account.valida_password(password, "marco")


def test_password_accettata():
    account.valida_password("cavallo-batteria-graffetta", "marco")


@pytest.mark.parametrize("nome", ["", "ab", "con spazio", "-iniziale", "a" * 33, "marco@example.com", "è.strano"])
def test_nomi_utente_rifiutati(nome):
    with pytest.raises(ErroreAccount):
        account.valida_nome(nome)


def test_nome_utente_senza_maiuscole():
    assert account.valida_nome("  Marco.Rossi_1 ") == "marco.rossi_1"


# ---------------------------------------------------------------- inviti e registrazione
def test_senza_invito_non_ci_si_registra(db):
    assert errore(account.registra, db, "marco", PASSWORD, "", adesso=ADESSO).stato == 403
    assert errore(account.registra, db, "marco", PASSWORD, "AAAAA-BBBBB-CCCCC-DDDDD", adesso=ADESSO).stato == 403
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 0


def test_invito_monouso(db):
    inv = account.crea_invito(db, "Luca", adesso=ADESSO)
    utente, token, recupero = account.registra(db, "luca", PASSWORD, inv, adesso=ADESSO)
    assert utente.nome_utente == "luca" and not utente.amministratore and token and recupero
    assert errore(account.registra, db, "altro", PASSWORD, inv, adesso=ADESSO).stato == 403          # già usato
    assert db.execute("SELECT usato_da FROM inviti").fetchone()[0] == utente.id


def test_invito_si_scrive_come_capita(db):
    inv = account.crea_invito(db, "Luca", adesso=ADESSO)
    scritto = " " + inv.lower().replace("-", " ") + " "
    assert account.registra(db, "luca", PASSWORD, scritto, adesso=ADESSO)[0].nome_utente == "luca"


def test_invito_scade_dopo_sette_giorni(db):
    inv = account.crea_invito(db, "Luca", adesso=ADESSO)
    assert errore(account.registra, db, "luca", PASSWORD, inv, adesso=ADESSO + timedelta(days=7, seconds=1)).stato == 403
    account.registra(db, "luca", PASSWORD, inv, adesso=ADESSO + timedelta(days=6, hours=23))


def test_invito_senza_etichetta(db):
    for etichetta in ("", "   ", "x" * 61):
        assert errore(account.crea_invito, db, etichetta).stato == 400


def test_invito_per_amministratore(db):
    utente, _, _ = nuovo(db, "capo", admin=True)
    assert utente.amministratore and utente.ruolo == "amministratore"
    assert not nuovo(db, "ospite")[0].amministratore


def test_registrazione_errori_non_bruciano_l_invito(db):
    inv = account.crea_invito(db, "Luca", adesso=ADESSO)
    assert errore(account.registra, db, "luca", "corta", inv, adesso=ADESSO).stato == 400
    assert errore(account.registra, db, "l", PASSWORD, inv, adesso=ADESSO).stato == 400
    nuovo(db, "marco")
    assert "già preso" in errore(account.registra, db, "MARCO", PASSWORD, inv, adesso=ADESSO).messaggio
    account.registra(db, "luca", PASSWORD, inv, adesso=ADESSO)                          # l'invito vale ancora


def test_tetto_utenti(db, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "2")
    nuovo(db, "uno")
    nuovo(db, "due")
    inv = account.crea_invito(db, "terzo", adesso=ADESSO)
    assert "numero massimo" in errore(account.registra, db, "tre", PASSWORD, inv, adesso=ADESSO).messaggio
    monkeypatch.setenv("MAX_UTENTI", "3")
    account.registra(db, "tre", PASSWORD, inv, adesso=ADESSO)


def test_tetto_utenti_predefinito_trenta(monkeypatch):
    monkeypatch.delenv("MAX_UTENTI", raising=False)
    assert account.max_utenti() == 30
    monkeypatch.setenv("MAX_UTENTI", "boh")
    assert account.max_utenti() == 30
    monkeypatch.setenv("MAX_UTENTI", "-4")
    assert account.max_utenti() == 30


def test_nel_database_non_ci_sono_segreti(db):
    inv = account.crea_invito(db, "Luca", adesso=ADESSO)
    _, token, recupero = account.registra(db, "luca", PASSWORD, inv, adesso=ADESSO)
    reset = account.crea_reset(db, "luca", ADESSO)
    tutto = " ".join(str(tuple(r)) for t in ("utenti", "sessioni", "inviti", "reset_password") for r in db.execute(f"SELECT * FROM {t}"))
    for segreto in (PASSWORD, token, recupero, recupero.replace("-", ""), inv, inv.replace("-", ""), reset, reset.replace("-", "")):
        assert segreto not in tutto


# ---------------------------------------------------------------- accesso e sessioni
def test_accesso(db):
    nuovo(db, "marco")
    utente, token = account.accedi(db, "  Marco ", PASSWORD, adesso=ADESSO)
    assert utente.nome_utente == "marco"
    assert account.utente_da_token(db, token, ADESSO).id == utente.id


def test_accesso_sbagliato_stesso_messaggio_e_stesso_lavoro(db, monkeypatch):
    nuovo(db, "marco")
    chiamate = []
    vera = account._verifica
    monkeypatch.setattr(account, "_verifica", lambda p, h: chiamate.append(h) or vera(p, h))
    sbagliata = errore(account.accedi, db, "marco", "password-sbagliata", adesso=ADESSO)
    sconosciuto = errore(account.accedi, db, "nessuno", PASSWORD, adesso=ADESSO)
    assert (sbagliata.stato, sbagliata.messaggio) == (sconosciuto.stato, sconosciuto.messaggio) == (401, sbagliata.messaggio)
    # anche per un nome che non esiste si calcola un hash vero (stesso tempo di una password sbagliata)
    assert len(chiamate) == 2 and chiamate[1].startswith("scrypt$") and chiamate[1] != chiamate[0]


def test_accesso_con_dati_strani(db):
    nuovo(db, "marco")
    for nome, pw in ((None, None), ("marco", None), ("marco", 12345), ("", ""), ("marco\x00", PASSWORD)):
        assert errore(account.accedi, db, nome, pw, adesso=ADESSO).stato == 401


def test_sessione_scaduta_revocata_o_inventata(db):
    utente, token, _ = nuovo(db)
    _, altra = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    assert account.utente_da_token(db, token, ADESSO + timedelta(days=31)) is None          # 30 giorni senza usarla
    assert account.utente_da_token(db, altra, ADESSO + timedelta(days=29)).id == utente.id
    for falso in (None, "", "x", token + "x", token[:-1], "a" * 500):
        assert account.utente_da_token(db, falso, ADESSO) is None


def test_la_sessione_si_allunga_con_l_uso(db):
    utente, token, _ = nuovo(db)
    for giorni in range(25, 176, 25):                       # usata ogni 25 giorni resta aperta...
        assert account.utente_da_token(db, token, ADESSO + timedelta(days=giorni)).id == utente.id
    assert account.utente_da_token(db, token, ADESSO + timedelta(days=181)) is None             # ...ma non oltre 180 giorni


def test_esci_revoca_solo_quella_sessione(db):
    utente, t1, _ = nuovo(db)
    _, t2 = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    account.esci(db, t1)
    assert account.utente_da_token(db, t1, ADESSO) is None
    assert account.utente_da_token(db, t2, ADESSO).id == utente.id
    account.esci(db, None)                                         # non fa danni


def test_esci_da_tutti(db):
    utente, t1, _ = nuovo(db)
    _, t2 = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    altro, t3, _ = nuovo(db, "luca")
    assert account.esci_da_tutti(db, utente.id) == 2
    assert account.utente_da_token(db, t1, ADESSO) is None and account.utente_da_token(db, t2, ADESSO) is None
    assert account.utente_da_token(db, t3, ADESSO).id == altro.id            # quelle degli altri restano


def test_le_sessioni_scadute_si_ripuliscono_all_accesso(db):
    nuovo(db)
    account.accedi(db, "marco", PASSWORD, adesso=ADESSO + timedelta(days=200))
    assert db.execute("SELECT COUNT(*) FROM sessioni").fetchone()[0] == 1


# ---------------------------------------------------------------- cambio password
def test_cambia_password(db):
    utente, t1, _ = nuovo(db)
    _, t2 = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    assert errore(account.cambia_password, db, utente.id, "sbagliata-sbagliata", "nuova-password-lunga", t1).stato == 403
    assert errore(account.cambia_password, db, utente.id, PASSWORD, "corta", t1).stato == 400
    t3 = account.cambia_password(db, utente.id, PASSWORD, "nuova-password-lunga", t1, adesso=ADESSO)
    assert account.utente_da_token(db, t3, ADESSO).id == utente.id      # questa riparte con un token nuovo
    assert account.utente_da_token(db, t1, ADESSO) is None              # quello di prima non vale più
    assert account.utente_da_token(db, t2, ADESSO) is None              # e le altre si chiudono
    assert errore(account.accedi, db, "marco", PASSWORD, adesso=ADESSO).stato == 401
    account.accedi(db, "marco", "nuova-password-lunga", adesso=ADESSO)


# ---------------------------------------------------------------- password dimenticata
def test_recupero_con_codice_di_recupero(db):
    utente, token, codice = nuovo(db)
    assert len(codice.replace("-", "")) == 20
    assert errore(account.recupera, db, "marco", "AAAAA-AAAAA-AAAAA-AAAAA", "nuova-password-lunga").stato == 403
    assert errore(account.recupera, db, "nessuno", codice, "nuova-password-lunga").stato == 403
    assert errore(account.recupera, db, "marco", codice, "corta").stato == 400
    nuovo_codice = account.recupera(db, "MARCO", codice.lower().replace("-", ""), "nuova-password-lunga")
    assert nuovo_codice != codice
    assert account.utente_da_token(db, token, ADESSO) is None                         # le sessioni vecchie sono chiuse
    account.accedi(db, "marco", "nuova-password-lunga", adesso=ADESSO)
    assert errore(account.recupera, db, "marco", codice, "ancora-un-altra-pw").stato == 403   # il codice usato non vale più
    account.recupera(db, "marco", nuovo_codice, "ancora-un-altra-pw")                 # quello nuovo sì
    assert account.rigenera_codice_recupero(db, utente.id, "ancora-un-altra-pw")


def test_il_codice_di_recupero_non_e_la_password(db):
    _, _, codice = nuovo(db)
    assert errore(account.accedi, db, "marco", codice, adesso=ADESSO).stato == 401


def test_rigenera_codice_di_recupero(db):
    utente, _, vecchio = nuovo(db)
    assert errore(account.rigenera_codice_recupero, db, utente.id, "sbagliata-sbagliata").stato == 403
    nuovo_c = account.rigenera_codice_recupero(db, utente.id, PASSWORD)
    assert errore(account.recupera, db, "marco", vecchio, "nuova-password-lunga").stato == 403
    account.recupera(db, "marco", nuovo_c, "nuova-password-lunga")


def test_reset_dell_amministratore(db):
    utente, token, codice_recupero = nuovo(db)
    assert errore(account.crea_reset, db, "nessuno").stato == 404
    reset = account.crea_reset(db, "marco", ADESSO)
    assert errore(account.recupera, db, "marco", reset, "nuova-password-lunga", adesso=ADESSO + timedelta(hours=24, seconds=1)).stato == 403
    account.recupera(db, "marco", reset, "nuova-password-lunga", adesso=ADESSO + timedelta(hours=23))
    assert account.utente_da_token(db, token, ADESSO) is None
    account.accedi(db, "marco", "nuova-password-lunga", adesso=ADESSO)
    # monouso
    assert errore(account.recupera, db, "marco", reset, "un-altra-password-1", adesso=ADESSO).stato == 403
    # il codice di un altro utente non vale per questo
    nuovo(db, "luca")
    reset_luca = account.crea_reset(db, "luca", ADESSO)
    assert errore(account.recupera, db, "marco", reset_luca, "un-altra-password-1", adesso=ADESSO).stato == 403


def test_un_nuovo_reset_annulla_il_vecchio(db):
    nuovo(db)
    primo = account.crea_reset(db, "marco", ADESSO)
    secondo = account.crea_reset(db, "marco", ADESSO)
    assert errore(account.recupera, db, "marco", primo, "nuova-password-lunga", adesso=ADESSO).stato == 403
    account.recupera(db, "marco", secondo, "nuova-password-lunga", adesso=ADESSO)


def test_elimina_account(db):
    utente, token, _ = nuovo(db)
    account.crea_reset(db, "marco", ADESSO)
    account.elimina(db, utente.id)
    assert account.utente_da_token(db, token, ADESSO) is None
    for t in ("utenti", "sessioni", "reset_password"):
        assert db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
    nuovo(db, "marco")                                               # il nome torna libero


# ---------------------------------------------------------------- limiti di tentativi
def test_dopo_cinque_errori_si_aspetta_e_l_attesa_cresce(db, multiutente):
    nuovo(db)
    for _ in range(5):
        assert errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO).stato == 401
    bloccato = errore(account.accedi, db, "marco", PASSWORD, adesso=ADESSO)           # anche con la password giusta
    assert bloccato.stato == 429 and 1 <= bloccato.riprova_tra <= 30
    multiutente.t += 31
    assert errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO).stato == 401      # sesto errore: ora l'attesa è 60 s
    multiutente.t += 31
    assert errore(account.accedi, db, "marco", PASSWORD, adesso=ADESSO).stato == 429
    multiutente.t += 31
    account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    for _ in range(5):                                                                 # entrare azzera il conto
        assert errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO).stato == 401


def test_l_attesa_non_supera_un_quarto_d_ora(db, multiutente):
    nuovo(db)
    for _ in range(12):                      # chi insiste aspettando ogni volta il tempo richiesto: 30, 60, 120... ma mai oltre 900 s
        e = errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO)
        while e.stato == 429:
            assert e.riprova_tra <= 900
            multiutente.t += e.riprova_tra + 1
            e = errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO)
    bloccato = errore(account.accedi, db, "marco", PASSWORD, adesso=ADESSO)
    assert bloccato.stato == 429 and 800 < bloccato.riprova_tra <= 900
    multiutente.t += 901
    account.accedi(db, "marco", PASSWORD, adesso=ADESSO)


def test_il_blocco_vale_anche_per_nomi_che_non_esistono(db):
    for _ in range(5):
        errore(account.accedi, db, "fantasma", "x" * 12, adesso=ADESSO)
    assert errore(account.accedi, db, "fantasma", "x" * 12, adesso=ADESSO).stato == 429       # non si capisce che non esiste


def test_il_blocco_di_un_nome_non_ferma_gli_altri(db):
    nuovo(db, "marco")
    nuovo(db, "luca")
    for _ in range(5):
        errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO)
    account.accedi(db, "luca", PASSWORD, adesso=ADESSO)


def test_limite_per_indirizzo_solo_se_si_vede(db, monkeypatch):
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (3, 900))
    nuovo(db, "marco")
    for i in range(3):
        errore(account.accedi, db, f"nome{i}", "x" * 12, ip="1.2.3.4", adesso=ADESSO)
    assert errore(account.accedi, db, "marco", PASSWORD, ip="1.2.3.4", adesso=ADESSO).stato == 429
    account.accedi(db, "marco", PASSWORD, ip="5.6.7.8", adesso=ADESSO)                 # un altro indirizzo no
    for i in range(10):                                                                 # indirizzo non visibile: nessun limite per indirizzo
        errore(account.accedi, db, f"altro{i}", "x" * 12, ip=None, adesso=ADESSO)
    account.accedi(db, "marco", PASSWORD, ip=None, adesso=ADESSO)


def test_tetto_globale_dei_tentativi_sbagliati_rallenta_non_blocca(db, monkeypatch):
    """Oltre la soglia globale nessuno resta chiuso fuori: chi ha la password giusta entra, ma chi non è noto aspetta un po'.
    Il recupero ha il suo conteggio: gli errori di accesso non lo toccano."""
    attese = []
    monkeypatch.setattr(account, "_dormi", attese.append)
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (4, 600))
    nuovo(db, "marco")
    for i in range(4):
        errore(account.accedi, db, f"nome{i}", "x" * 12, adesso=ADESSO)
    assert attese == []
    account.accedi(db, "marco", PASSWORD, adesso=ADESSO)                      # 5° tentativo: oltre la soglia, ma entra
    assert attese == [1.0]
    errore(account.recupera, db, "marco", "AAAAA", "nuova-password-lunga")    # il recupero non è rallentato dagli accessi
    assert attese == [1.0]


def test_limite_di_registrazioni_per_indirizzo(db):
    for _ in range(5):
        assert errore(account.registra, db, "luca", PASSWORD, "sbagliato", ip="1.2.3.4", adesso=ADESSO).stato == 403
    assert errore(account.registra, db, "luca", PASSWORD, "sbagliato", ip="1.2.3.4", adesso=ADESSO).stato == 429


def test_il_recupero_a_forza_di_tentativi_si_blocca(db):
    nuovo(db)
    for _ in range(5):
        errore(account.recupera, db, "marco", "AAAAA-AAAAA-AAAAA-AAAAA", "nuova-password-lunga")
    assert errore(account.recupera, db, "marco", "AAAAA-AAAAA-AAAAA-AAAAA", "nuova-password-lunga").stato == 429


def test_cambio_password_a_forza_di_tentativi(db):
    utente, token, _ = nuovo(db)
    for _ in range(10):
        errore(account.cambia_password, db, utente.id, "sbagliata-sbagliata", "nuova-password-lunga", token)
    assert errore(account.cambia_password, db, utente.id, PASSWORD, "nuova-password-lunga", token).stato == 429
