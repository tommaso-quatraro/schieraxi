"""Regola di prodotto: nemmeno lo storico delle novita' (it, en e voci in attesa) cita quote, bookmaker o scommesse."""
import json
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
PAROLE = re.compile(r"\bquot[ae]\b|quote_|bookmaker|scommess|betting|azzardo|\bodds|pinnacle|1x2", re.I)


def _file():
    yield RADICE / "fanta" / "novita.json"
    yield RADICE / "fanta" / "contenuti" / "novita.en.json"
    yield from sorted((RADICE / "fanta" / "novita.d").glob("*.json"))


def test_storico_novita_senza_parole_di_scommesse():
    trovati = [f"{p.relative_to(RADICE)}:{i}" for p in _file()
               for i, riga in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if PAROLE.search(riga)]
    assert not trovati, trovati


def test_novita_restano_json_validi():
    for p in _file():
        assert json.loads(p.read_text(encoding="utf-8"))
