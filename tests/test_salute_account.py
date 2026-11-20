"""Controllo del database degli account dopo un'installazione (#825): lo chiama script/server/aggiorna-app.sh con il codice nuovo,
dopo il riavvio. Apre davvero il database (con le migrazioni, come farebbe il servizio alla prima richiesta) e confronta la sua
versione con le migrazioni attese. Database finti in cartelle temporanee."""
import sqlite3

import pytest

from fanta import account, salute


@pytest.fixture
def cartella(tmp_path, monkeypatch):
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path))
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    return tmp_path


def _versione(percorso):
    db = sqlite3.connect(percorso)
    try:
        return db.execute("PRAGMA user_version").fetchone()[0]
    finally:
        db.close()


def test_database_a_posto(cartella):
    account.apri().close()
    ok, testo = salute.controlla_database_account()
    assert ok, testo
    assert str(len(account.MIGRAZIONI)) in testo


def test_senza_database_non_lo_crea(cartella):
    ok, testo = salute.controlla_database_account()
    assert ok, testo
    assert not (cartella / "account.sqlite").exists()                 # niente file nuovi (account spenti o percorso diverso)


def test_migrazione_che_fallisce_sui_dati_veri_non_va(cartella, monkeypatch):
    """Una migrazione che sui dati veri dà un errore di integrità: il 401 di /api/account/me non se ne accorgerebbe mai."""
    account.apri().close()
    rotta = "INSERT INTO utenti (id, nome_utente, password_hash) VALUES (1, 'a', 'x'), (1, 'b', 'y');"
    monkeypatch.setattr(account, "MIGRAZIONI", [*account.MIGRAZIONI, rotta])
    ok, testo = salute.controlla_database_account()
    assert not ok
    assert "IntegrityError" in testo or "UNIQUE" in testo, testo
    assert _versione(cartella / "account.sqlite") == len(account.MIGRAZIONI) - 1       # niente versione nuova a metà


def test_migrazione_nuova_si_applica_e_il_controllo_passa(cartella, monkeypatch):
    account.apri().close()
    monkeypatch.setattr(account, "MIGRAZIONI", [*account.MIGRAZIONI, "CREATE TABLE prova_825 (x INTEGER);"])
    ok, testo = salute.controlla_database_account()
    assert ok, testo
    assert _versione(cartella / "account.sqlite") == len(account.MIGRAZIONI)


def test_database_piu_nuovo_del_codice_non_va(cartella):
    account.apri().close()
    db = sqlite3.connect(cartella / "account.sqlite")
    db.execute(f"PRAGMA user_version = {len(account.MIGRAZIONI) + 1}")
    db.commit()
    db.close()
    ok, testo = salute.controlla_database_account()
    assert not ok and "più nuova" in testo, testo


def test_senza_fanta_dati_utenti_controlla_il_database_della_cartella_dati(tmp_path, monkeypatch):
    """Sul server FANTA_DATI_UTENTI non c'è: il controllo guarda dati/account.sqlite come il servizio, e se non va lo dice."""
    from fanta import percorsi
    monkeypatch.delenv("FANTA_DATI_UTENTI", raising=False)
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setattr(percorsi, "RADICE", tmp_path)
    account.apri(tmp_path / "dati" / "account.sqlite").close()
    ok, testo = salute.controlla_database_account()
    assert ok and str(len(account.MIGRAZIONI)) in testo, testo
    monkeypatch.setattr(account, "MIGRAZIONI", [*account.MIGRAZIONI, "INSERT INTO tabella_che_non_c_e VALUES (1);"])
    ok, testo = salute.controlla_database_account()
    assert not ok, testo
