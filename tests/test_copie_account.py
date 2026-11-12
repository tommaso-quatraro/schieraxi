"""Copie di sicurezza del database degli account (#653): le copie «prima della migrazione» non tolgono posto alle copie serali,
scadono dopo backup.GIORNI_COPIE_MIGRAZIONE giorni e nascono leggibili solo dal proprietario.
Cartelle temporanee, account inventati, l'ora sempre passata come argomento (niente orologio vero)."""
import contextlib
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

from fanta import account, backup, percorsi

ADESSO = datetime(2026, 11, 12, 3, 30)          # il giro serale (cron delle 3:30)
SERALE = "account-????-??-??.sqlite"


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
    serali = sorted(p.name for p in cartella.glob(SERALE))
    assert serali == [f"account-2026-11-0{g}.sqlite" for g in range(2, 8)] + ["account-2026-11-12.sqlite"]
    assert len(list(cartella.glob("account-prima-della-migrazione-*.sqlite"))) == migrazioni    # recenti: restano
