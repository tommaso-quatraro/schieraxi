"""Parole che nei testi in inglese non si usano (catalogo `fanta/testi/`, novità): solo nel senso sbagliato, senza falsi allarmi.

- «round» per la giornata (si dice «matchday»), non «year-round», «round to 6.3», «round up», «a round number», «rounded»;
- «lock» per la chiusura della formazione (la formazione «closes»), non «Lock Screen» dell'iPhone né un account bloccato;
- «line-up» (si scrive «lineup») e le virgolette italiane «» (in inglese “ ”).
Le usano `test_inglese_web.py` e `test_novita_inglese.py`; `test_parole_inglesi.py` prova le espressioni."""
import re

ROUND = re.compile(r"(?<![-\w])rounds?\b(?![-\w])(?!\s+(?:to|up|down|off|numbers?)\b)", re.I)
_FORMAZIONE = r"(?:lineups?|formations?)"
LOCK = re.compile(rf"\b{_FORMAZIONE}\s+(?:locks?|locked)\b|\block(?:s|ed)?\s+(?:\w+\s+){{0,2}}{_FORMAZIONE}\b", re.I)
LINE_UP = re.compile(r"\bline-ups?\b", re.I)
VIRGOLETTE = re.compile(r"[«»]")
