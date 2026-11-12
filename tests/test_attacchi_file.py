"""Attacchi su file e avvio (trovati in revisione): database degli account appena creato con tante richieste insieme (falso
«database rovinato»), permessi dei file con dati sensibili, `dati/ambiente.env` eseguito come codice dagli script del server.
Tutto su cartelle temporanee."""
import contextlib
import os
import shutil
import stat
import subprocess
import threading
from pathlib import Path

import pytest

from fanta import account, registro
from fanta.account import ErroreAccount

RADICE = Path(__file__).resolve().parent.parent
POSIX = os.name == "posix"


# ---------------------------------------------------------------- (7) database nuovo, richieste in parallelo
def test_database_nuovo_aperto_da_tante_richieste_insieme(multiutente):
    """prova3: senza database, 80 richieste insieme; alcune rispondevano 503 «database rovinato» (era solo occupato)."""
    errori, via = [], threading.Barrier(40)

    def apri():
        via.wait()
        try:
            with contextlib.closing(account.apri()) as db:
                db.execute("SELECT COUNT(*) FROM utenti").fetchone()
        except ErroreAccount as e:
            errori.append(e.messaggio)
    fili = [threading.Thread(target=apri) for _ in range(40)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    assert errori == []
    with contextlib.closing(account.apri()) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)


def test_database_occupato_non_e_rovinato(multiutente, monkeypatch):
    """Se il database è bloccato da un altro processo il messaggio non deve dire «rovinato» (che spaventa e manda a ripristinare)."""
    percorso = account.percorsi.cartella_account() / "account.sqlite"
    account.apri().close()
    import sqlite3
    altro = sqlite3.connect(percorso, isolation_level=None)
    altro.execute("PRAGMA user_version = 0")                 # finge una migrazione da fare...
    altro.execute("BEGIN EXCLUSIVE")                          # ...mentre un altro processo tiene il database
    monkeypatch.setattr(account, "ATTESA_DATABASE", 0.2)
    try:
        with pytest.raises(ErroreAccount) as e:
            account.apri()
        assert e.value.stato == 503 and "rovinato" not in e.value.messaggio
    finally:
        altro.execute("ROLLBACK")
        altro.execute(f"PRAGMA user_version = {len(account.MIGRAZIONI)}")
        altro.close()


# ---------------------------------------------------------------- (8) permessi dei file
@pytest.mark.skipif(not POSIX, reason="permessi POSIX (sul server e su GitHub)")
def test_file_sensibili_leggibili_solo_dal_proprietario(multiutente, monkeypatch):
    vecchia = os.umask(0o022)                                # come un servizio con l'umask di sistema
    try:
        account.apri().close()
        cartella = account.percorsi.cartella_account()
        for nome in ("sicurezza.log", "posta.log", "errori.log"):
            registro.scrivi(cartella / nome, "riga di prova")
        for nome in ("account.sqlite", "sicurezza.log", "posta.log", "errori.log"):
            modo = stat.S_IMODE((cartella / nome).stat().st_mode)
            assert modo & 0o077 == 0, (nome, oct(modo))
        assert stat.S_IMODE(cartella.stat().st_mode) & 0o077 == 0
    finally:
        os.umask(vecchia)


@pytest.mark.skipif(not POSIX, reason="permessi POSIX")
def test_anche_dopo_la_rotazione_del_registro(tmp_path):
    vecchia = os.umask(0o022)
    try:
        f = tmp_path / "sicurezza.log"
        for _ in range(50):
            registro.scrivi(f, "x" * 100, 1000)
        for g in [f, *tmp_path.glob("sicurezza.log.*")]:
            assert stat.S_IMODE(g.stat().st_mode) & 0o077 == 0, g
    finally:
        os.umask(vecchia)


# ---------------------------------------------------------------- (8) ambiente.env letto senza eseguire niente
BASH = shutil.which("bash")


@pytest.mark.skipif(not (POSIX and BASH), reason="serve bash (sul server e su GitHub)")
def test_ambiente_env_non_esegue_comandi(tmp_path):
    preso = tmp_path / "preso"
    env = tmp_path / "ambiente.env"
    env.write_text(
        "# commento\n"
        "FANTA_MULTIUTENTE=1\n"
        f"touch {preso}\n"
        f"FANTA_X=$(touch {preso})\n"
        f"FANTA_Y=`touch {preso}`\n"
        "FANTA_Z=\"con spazi e $HOME\"\r\n"
        "export FANTA_REGISTRAZIONE=invito\n"
        "PATH=/niente\n"
        "LD_PRELOAD=/tmp/x.so\n"
        f"FANTA_W=a; touch {preso}\n"
        "MAX_UTENTI=5", encoding="utf-8")
    prova = tmp_path / "prova.sh"
    prova.write_text(f'. "{RADICE}/script/server/leggi-ambiente.sh"\nleggi_ambiente "{env}"\n'
                     'printf "%s|" "$FANTA_MULTIUTENTE" "$FANTA_X" "$FANTA_Y" "$FANTA_Z" "$FANTA_REGISTRAZIONE" "$PATH" '
                     '"${LD_PRELOAD:-}" "$FANTA_W" "$MAX_UTENTI"\n', encoding="utf-8")
    uscita = subprocess.run([BASH, str(prova)], capture_output=True, text=True, timeout=20,
                            env={"PATH": os.environ["PATH"], "HOME": "/casa", "SCHIERAXI_AMBIENTE": "/nessun-percorso/fantacalcio.env"})
    assert uscita.returncode == 0, uscita.stderr
    valori = uscita.stdout.split("|")
    assert not preso.exists()                                 # nessun comando eseguito
    assert valori[0] == "1" and valori[1] == f"$(touch {preso})" and valori[2] == f"`touch {preso}`"
    assert valori[3] == "con spazi e $HOME" and valori[4] == "invito"
    assert valori[5] == os.environ["PATH"] and valori[6] == ""             # chiavi fuori dall'elenco: ignorate
    assert valori[7] == f"a; touch {preso}" and valori[8] == "5"


def test_gli_script_del_server_non_eseguono_ambiente_env():
    for f in (RADICE / "script" / "server").glob("*.sh"):
        if f.name == "leggi-ambiente.sh":
            continue
        testo = f.read_text(encoding="utf-8")
        assert ". dati/ambiente.env" not in testo and "source dati/ambiente.env" not in testo, f.name
        if "ambiente.env" in testo:
            assert "leggi_ambiente dati/ambiente.env" in testo, f.name
