"""Orari (#665): l'app usa l'ora italiana anche su un sistema in UTC, la salute avvisa se non ci riesce, le email di sicurezza
scrivono l'ora italiana senza sigle. Dati inventati, archivi temporanei, nessun invio vero."""
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fanta import account, archivio, fuso, posta, salute

RADICE = Path(__file__).resolve().parent.parent
UTC = timezone.utc


# ---------------------------------------------------------------- l'orologio dell'app
@pytest.mark.parametrize("locale, istante, giusto", [
    (datetime(2027, 6, 15, 21, 30), datetime(2027, 6, 15, 19, 30, tzinfo=UTC), True),      # estate: Italia = UTC + 2
    (datetime(2027, 6, 15, 19, 30), datetime(2027, 6, 15, 19, 30, tzinfo=UTC), False),     # sistema in UTC
    (datetime(2027, 1, 1, 0, 30), datetime(2026, 12, 31, 23, 30, tzinfo=UTC), True),       # inverno: Italia = UTC + 1
    (datetime(2026, 12, 31, 23, 30), datetime(2026, 12, 31, 23, 30, tzinfo=UTC), False),
])
def test_orologio_italiano_riconosce_un_sistema_in_utc(locale, istante, giusto):
    assert fuso.orologio_italiano(locale, istante) is giusto


FIGLIO = r"""
import runpy, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
cartella = Path(sys.argv[1])                        # la cartella temporanea del test
sys.argv = ["fanta", "--help"]                       # come sul server: python -m fanta <comando>
try:
    runpy.run_module("fanta", run_name="__main__", alter_sys=True)
except SystemExit:
    pass
from fanta import archivio, consigli, fasi
from fanta.regole import Regole
italia = datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
inizio = (italia - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")      # prima partita cominciata da 30 minuti, ora italiana
stagione = consigli.stagione_corrente()
db = archivio.apri(cartella / "prova.sqlite")
for k in range(10):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, 1, ?, ?, ?, 0)",
               (k + 1, stagione, inizio, f"casa{k}", f"trasferta{k}"))
db.commit()
print("CHIUSA", fasi.iniziata(db, Regole(), stagione, 1, consigli._adesso()))
"""


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="su Windows il fuso di un processo non si cambia: la prova vale su Linux e macOS")
def test_con_il_sistema_in_utc_la_formazione_e_chiusa_all_ora_italiana_giusta(tmp_path):
    """`python -m fanta` (servizio e comandi del cron) con il sistema in UTC: la formazione si chiude all'ora italiana giusta.
    Prima, con l'ora del sistema, 30 minuti dopo il calcio d'inizio risultava ancora aperta (1 o 2 ore di ritardo). La prova non
    dipende dal giorno: fra UTC e l'ora italiana c'è sempre almeno un'ora."""
    env = os.environ | {"TZ": "UTC", "PYTHONPATH": str(RADICE)}
    r = subprocess.run([sys.executable, "-c", FIGLIO, str(tmp_path)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "CHIUSA True", r.stdout + r.stderr


def test_la_salute_avvisa_se_l_orologio_non_da_l_ora_italiana(tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO aggiornamenti (cosa, quando) VALUES ('aggiornamento', ?)", ("2026-10-28T08:00:00",))
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    adesso = datetime(2026, 10, 28, 12, 0)
    assert salute.controlla(db, adesso, tmp_path / "a.json", manda, lambda: True, orologio_italiano=lambda: True) == []
    problemi = salute.controlla(db, adesso, tmp_path / "b.json", manda, lambda: True, orologio_italiano=lambda: False)
    assert len(problemi) == 1 and "ora italiana" in problemi[0] and mandati == problemi
    db.close()


# ---------------------------------------------------------------- le email di sicurezza
@pytest.mark.parametrize("istante, testo", [
    (datetime(2027, 6, 15, 19, 30, tzinfo=UTC), "15/06/2027 alle 21:30"),          # sera d'estate
    (datetime(2026, 12, 31, 23, 30, tzinfo=UTC), "01/01/2027 alle 00:30"),         # mezzanotte e mezza di Capodanno
    (datetime(2026, 12, 31, 22, 40, tzinfo=UTC), "31/12/2026 alle 23:40"),
    (datetime(2027, 6, 15, 19, 30), "15/06/2027 alle 21:30"),                      # senza fuso: è un'ora UTC, come negli account
])
def test_ora_delle_email_in_ora_italiana_senza_sigle(istante, testo):
    assert posta.ora_italiana(istante) == testo


def test_email_password_cambiata_con_l_ora_italiana(monkeypatch):
    mandati = []
    monkeypatch.setattr(posta, "invia", lambda m: mandati.append(m) or True)
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE utenti (id INTEGER PRIMARY KEY, email TEXT)")
    db.execute("INSERT INTO utenti VALUES (1, 'marco@example.com')")
    account._avvisa_password_cambiata(db, 1, datetime(2026, 12, 31, 23, 30, tzinfo=UTC))
    assert len(mandati) == 1 and "Quando: 01/01/2027 alle 00:30" in mandati[0].testo and "UTC" not in mandati[0].testo
