"""Copie di sicurezza del database degli account (#653): le copie «prima della migrazione» non tolgono posto alle copie serali,
scadono dopo backup.GIORNI_COPIE_MIGRAZIONE giorni e nascono leggibili solo dal proprietario.
Cartelle temporanee, account inventati, l'ora sempre passata come argomento (niente orologio vero)."""
import contextlib
import os
import re
import sqlite3
from datetime import datetime, timedelta

import pytest

from fanta import account, backup, percorsi

ADESSO = datetime(2026, 11, 12, 3, 30)          # il giro serale (cron delle 3:30)
SERALE = re.compile(r"account-\d{4}-\d{2}-\d{2}\.sqlite")      # account-AAAA-MM-GG.sqlite


def _origine(tmp_path):
    origine = tmp_path / "account.sqlite"
    with contextlib.closing(sqlite3.connect(origine)) as db:
        db.execute("CREATE TABLE x (a)")
    return origine


def _data(p, quando: datetime) -> None:
    os.utime(p, (quando.timestamp(), quando.timestamp()))


@pytest.mark.parametrize("migrazioni", [1, 3, 7])
def test_le_copie_di_migrazione_non_tolgono_posto_alle_serali(tmp_path, migrazioni):
    cartella = tmp_path / "backup"
    cartella.mkdir()
    for giorno in range(1, 8):                                       # sette notti di copie già fatte
        (cartella / f"account-2026-11-0{giorno}.sqlite").write_bytes(b"serale")
    for versione in range(5, 5 + migrazioni):                        # copie di migrazione recenti (un giorno fa)
        copia = cartella / f"account-prima-della-migrazione-{versione}.sqlite"
        copia.write_bytes(b"migrazione")
        _data(copia, ADESSO - timedelta(days=1))
    scritta = backup.copia_account(cartella, _origine(tmp_path), tieni=7, adesso=ADESSO)
    assert scritta == cartella / "account-2026-11-12.sqlite" and scritta.exists()
    serali = sorted(p.name for p in cartella.iterdir() if SERALE.fullmatch(p.name))
    assert serali == [f"account-2026-11-0{g}.sqlite" for g in range(2, 8)] + ["account-2026-11-12.sqlite"]
    assert len(list(cartella.glob("account-prima-della-migrazione-*.sqlite"))) == migrazioni    # recenti: restano


def _nomi(copia) -> list[str]:
    with contextlib.closing(sqlite3.connect(copia)) as db:
        return [r[0] for r in db.execute("SELECT nome_utente FROM utenti")]


def _database_vecchio():
    """Un database degli account fermo alla migrazione 5, con un utente: aprirlo fa nascere la copia di prima."""
    percorso = percorsi.cartella_account() / "account.sqlite"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(percorso)) as db:
        for m in account.MIGRAZIONI[:5]:
            db.executescript(m)
        db.execute("PRAGMA user_version = 5")
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('via', 'x', 'y', 'z')")
        db.commit()
    return percorso


def test_la_copia_di_migrazione_di_un_account_eliminato_scade(multiutente):
    """Un utente c'è quando il server si aggiorna con una migrazione (nasce la copia di prima), poi elimina l'account: il suo nome
    resta solo nella copia, e la copia sparisce al primo giro serale dopo backup.GIORNI_COPIE_MIGRAZIONE giorni."""
    percorso = _database_vecchio()
    with contextlib.closing(account.apri()) as db:                   # l'aggiornamento: migrazioni e copia di prima
        account.elimina(db, db.execute("SELECT id FROM utenti WHERE nome_utente = 'via'").fetchone()[0])
    cartella = percorso.parent / "backup"
    copia = cartella / "account-prima-della-migrazione-5.sqlite"
    assert _nomi(copia) == ["via"]
    creata = datetime(2026, 11, 1, 10, 0)
    _data(copia, creata)
    giorni = backup.GIORNI_COPIE_MIGRAZIONE
    backup.copia_account(cartella, percorso, adesso=creata + timedelta(days=giorni - 1))
    assert copia.exists()                                            # ancora giovane: resta (serve se la migrazione è andata storta)
    backup.copia_account(cartella, percorso, adesso=creata + timedelta(days=giorni, hours=1))
    assert not copia.exists()
    rimaste = sorted(cartella.glob("account-*.sqlite"))
    assert rimaste and all(SERALE.fullmatch(p.name) for p in rimaste)  # restano solo le serali, senza di lui
    assert all("via" not in _nomi(p) for p in rimaste)


@pytest.mark.skipif(os.name != "posix", reason="i permessi dei file si provano solo su Linux e macOS")
def test_la_copia_di_migrazione_nasce_leggibile_solo_dal_proprietario(multiutente):
    """Anche se il processo non ha l'umask stretta del servizio (per esempio un comando lanciato a mano), la copia con nomi,
    email e impronte delle password nasce come le serali: lettura e scrittura solo per il proprietario."""
    _database_vecchio()
    prima = os.umask(0o022)
    try:
        account.apri().close()
    finally:
        os.umask(prima)
    copia = percorsi.cartella_account() / "backup" / "account-prima-della-migrazione-5.sqlite"
    assert oct(copia.stat().st_mode & 0o777) == oct(0o600)


def test_le_copie_serali_non_scadono_per_eta(tmp_path):
    """Le serali le regola solo il loro numero (`tieni`): una vecchia resta se rientra fra le ultime `tieni`."""
    cartella = tmp_path / "backup"
    cartella.mkdir()
    vecchia = cartella / "account-2026-01-01.sqlite"
    vecchia.write_bytes(b"serale")
    _data(vecchia, datetime(2026, 1, 1, 3, 30))
    backup.copia_account(cartella, _origine(tmp_path), tieni=7, adesso=ADESSO)
    assert vecchia.exists()
