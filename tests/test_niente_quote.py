"""Regola di prodotto: nessun riferimento a quote, bookmaker o scommesse nei testi che l'utente puo' leggere."""
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
PAROLE = re.compile(r"bookmaker|scommess|betting|azzardo|\bodds\b|quote storiche|\bquote (dei|delle|1x2)", re.I)


def _file_visibili():
    for sotto, tipi in (("fanta", ("*.py", "*.js", "*.html", "*.json")),):
        for t in tipi:
            for p in (RADICE / sotto).rglob(t):
                yield p     # novita' comprese (vedi anche test_niente_quote_novita.py)
    for nome in ("README.md", "docs/GUIDA-UTENTE.md", "docs/API.md", "docs/API-SOTTO-IL-COFANO.md", "docs/SOTTO-IL-COFANO.md"):
        if (RADICE / nome).exists():
            yield RADICE / nome


def test_nessuna_parola_di_scommesse_nei_testi_visibili():
    trovati = [f"{p.relative_to(RADICE)}:{i}" for p in _file_visibili()
               for i, riga in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1) if PAROLE.search(riga)]
    assert not trovati, trovati


def test_footballdata_descritta_come_fonte_di_risultati():
    from fanta.fonti_attive import FONTI
    assert "partite" in FONTI["footballdata"][1] and "quot" not in FONTI["footballdata"][1].lower()
