"""Nome delle squadre di Serie A: ogni fonte le scrive a modo suo, qui diventano lo "slug" di Fantacalcio.it."""
from __future__ import annotations

from .nomi import normalizza

# solo i casi in cui il nome della fonte non contiene lo slug
ALIAS = {
    "internazionale": "inter", "inter milan": "inter", "ac milan": "milan", "hellas verona": "verona", "hellas": "verona",
    "juve": "juventus", "spal": "spal", "parma calcio 1913": "parma",
}


def slug(nome: str, slug_noti: set[str]) -> str | None:
    """'AC Milan' -> 'milan', 'Parma Calcio 1913' -> 'parma', 'Inter' -> 'inter'. None se non si capisce."""
    n = normalizza(nome)
    if n in slug_noti:
        return n
    if n in ALIAS and ALIAS[n] in slug_noti:
        return ALIAS[n]
    contenuti = [s for s in slug_noti if s in n.split() or s == n.replace(" ", "-")]
    if len(contenuti) == 1:
        return contenuti[0]
    iniziano = [s for s in slug_noti if len(n) >= 3 and s.startswith(n)]
    return iniziano[0] if len(iniziano) == 1 else None
