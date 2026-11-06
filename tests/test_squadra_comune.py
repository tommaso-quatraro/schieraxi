"""Comandi della squadra (script/squadra): la funzione unica per gh e git, e il finto usato da tutti i test test_squadra_*.

Nessun test chiama la rete: ogni comando riceve `esegui` (la funzione che lancia gh e git) e nei test riceve un `Finto`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
CARTELLA = RADICE / "script" / "squadra"
if str(CARTELLA) not in sys.path:
    sys.path.insert(0, str(CARTELLA))

import comune  # noqa: E402


class Sequenza:
    """Risposte diverse a chiamate successive dello stesso comando (l'ultima si ripete)."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)

    def prossima(self):
        return self.risposte.pop(0) if len(self.risposte) > 1 else self.risposte[0]


class Finto:
    """Al posto di gh e git: chiave = inizio del comando (parole separate da spazi), vince la chiave più lunga.
    Valore: stringa (uscita), dict/list (JSON), comune.Risposta (codice e errore) o Sequenza. Comando sconosciuto = errore."""

    def __init__(self, risposte: dict):
        self.risposte = risposte
        self.chiamate: list[list[str]] = []

    def __call__(self, argomenti):
        self.chiamate.append(list(argomenti))
        testo = " ".join(argomenti)
        chiavi = [k for k in self.risposte if testo == k or testo.startswith(k + " ")]
        if not chiavi:
            raise AssertionError(f"comando non previsto dal test: {testo}")
        valore = self.risposte[max(chiavi, key=len)]
        if isinstance(valore, Sequenza):
            valore = valore.prossima()
        if isinstance(valore, comune.Risposta):
            return valore
        if not isinstance(valore, str):
            valore = json.dumps(valore)
        return comune.Risposta(0, valore, "")

    def lanciati(self, inizio: str) -> list[str]:
        return [" ".join(c) for c in self.chiamate if " ".join(c).startswith(inizio)]


def test_chiama_restituisce_l_uscita_e_alza_errore_se_il_comando_fallisce():
    finto = Finto({"gh pr list": "ok", "gh rotto": comune.Risposta(1, "", "HTTP 502")})
    assert comune.chiama(finto, ["gh", "pr", "list"]) == "ok"
    with pytest.raises(comune.ErroreComando) as e:
        comune.chiama(finto, ["gh", "rotto"])
    assert "HTTP 502" in str(e.value)


def test_chiama_json_legge_il_json():
    finto = Finto({"gh pr view 3": {"number": 3}})
    assert comune.chiama_json(finto, ["gh", "pr", "view", "3"]) == {"number": 3}


def test_chiama_json_con_json_rotto_alza_errore_chiaro():
    finto = Finto({"gh pr view 3": "non json"})
    with pytest.raises(comune.ErroreComando):
        comune.chiama_json(finto, ["gh", "pr", "view", "3"])


def test_comando_sconosciuto_nel_finto_ferma_il_test():
    with pytest.raises(AssertionError):
        Finto({})(["gh", "api", "qualcosa"])


def test_eta_in_ore_e_giorni():
    assert comune.eta("2026-11-06T10:00:00Z", adesso=comune.data("2026-11-06T12:30:00Z")) == "2 h"
    assert comune.eta("2026-11-03T10:00:00Z", adesso=comune.data("2026-11-06T12:30:00Z")) == "3 g"
    assert comune.eta("2026-11-06T12:20:00Z", adesso=comune.data("2026-11-06T12:30:00Z")) == "10 min"
