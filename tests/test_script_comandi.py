"""Gli script del server (cron e servizi) lanciano `python -m fanta <comando>`: ogni comando deve esistere. Se un comando viene
tolto e uno script lo lancia ancora, a ogni giro il registro si riempie di errori e quel lavoro non si fa più senza che nessuno
se ne accorga. Qui si leggono solo i file degli script (niente bash) e si chiede l'aiuto di ogni comando."""
import re
from pathlib import Path

import pytest

from fanta import __main__ as cli

SCRIPT = Path(__file__).resolve().parents[1] / "script" / "server"
# `fanta foto` c'è solo nelle copie private, dove c'è fanta/foto.py (docs/AVATAR-DIRITTI.md): aggiorna.sh lo lancia solo con FANTA_FOTO=1
SOLO_COPIE_PRIVATE = {"foto"}


def _comandi() -> list[tuple[str, str]]:
    """(nome dello script, comando) per ogni `python -m fanta <comando>` negli script e nei servizi di script/server/."""
    trovati = set()
    for f in sorted(SCRIPT.rglob("*")):
        if f.is_file() and f.suffix in (".sh", ".service"):
            trovati |= {(f.name, c) for c in re.findall(r"python3? -m fanta ([a-z][a-z-]*)", f.read_text(encoding="utf-8"))}
    return sorted(trovati)


def test_gli_script_del_server_lanciano_solo_comandi_che_esistono(capsys):
    trovati = _comandi()
    assert ("aggiorna.sh", "cambi") in trovati and ("promemoria.sh", "promemoria") in trovati     # la ricerca li trova davvero
    for nome, comando in trovati:
        if comando in SOLO_COPIE_PRIVATE:
            continue
        with pytest.raises(SystemExit) as uscita:
            cli.main([comando, "--help"])
        assert uscita.value.code == 0, f"{nome} lancia «python -m fanta {comando}», che non esiste"
    capsys.readouterr()
