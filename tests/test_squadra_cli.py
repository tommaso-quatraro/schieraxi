"""script/squadra/squadra.py: entrata unica, ogni comando ha --help con i codici di uscita."""
from __future__ import annotations

import subprocess
import sys

import pytest
import test_squadra_comune  # noqa: F401

import squadra

ATTESI = {"stato", "attendi", "annulla-superate", "pulisci", "brief", "foto", "giro", "pr-pronta", "giornata"}


def test_ci_sono_tutti_i_comandi_del_piano():
    assert {m.NOME for m in squadra.COMANDI} == ATTESI


@pytest.mark.parametrize("nome", sorted(ATTESI))
def test_aiuto_con_i_codici_di_uscita(nome, capsys):
    if nome not in {m.NOME for m in squadra.COMANDI}:
        pytest.fail(f"manca il comando {nome}")
    with pytest.raises(SystemExit) as e:
        squadra.main([nome, "--help"])
    assert e.value.code == 0
    uscita = capsys.readouterr().out
    assert "Codici di uscita: 0" in uscita


def test_lo_script_si_lancia_da_solo():
    r = subprocess.run([sys.executable, str(test_squadra_comune.CARTELLA / "squadra.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0 and "stato" in r.stdout and "--esegui" in r.stdout


def test_argomento_sbagliato_esce_con_64_non_con_un_codice_dei_comandi():
    with pytest.raises(SystemExit) as e:
        squadra.main(["attendi", "non-un-numero"])
    assert e.value.code == 64
    with pytest.raises(SystemExit) as e:
        squadra.main(["comando-che-non-esiste"])
    assert e.value.code == 64
