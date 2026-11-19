"""Sentinella del ritorno di Understat (issue #756): una richiesta al giorno dai server di GitHub, mai di più.

Dal novembre 2026 Understat risponde a tutti con la pagina «We will come back soon» e la fonte è spenta sul server: il server non
le fa più richieste. Questo script, lanciato da .github/workflows/sentinella-understat.yml, chiede una volta i dati della Serie A
(stesso indirizzo e stesse intestazioni del lettore fanta/fonti/understat.py, nessun nuovo tentativo, timeout breve) e decide con
la funzione del lettore se sono dati veri o una pagina web. Se sono tornati, commenta l'issue #756 una volta sola (il commento
porta un segno fisso, contato solo se scritto da github-actions) e la riapre se è chiusa. Ancora la pagina: non fa niente.

Comandi:
  python script/ci/sentinella_understat.py gia-avvisato   -> avvisato=si|no in $GITHUB_OUTPUT (gh, nessuna richiesta a Understat)
  python script/ci/sentinella_understat.py controlla      -> esito=tornato|fermo in $GITHUB_OUTPUT (una richiesta a Understat;
                                                             un indirizzo dopo «controlla» solo per i test, con un server finto)
  python script/ci/sentinella_understat.py avvisa         -> commenta e riapre l'issue, se non è già stato fatto (gh)
Il primo e il terzo usano solo la libreria standard; il secondo vuole le librerie di requirements.txt."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
if str(RADICE) not in sys.path:      # lanciato per percorso (come nel workflow) Python vede solo script/ci
    sys.path.insert(0, str(RADICE))
ISSUE = 756
TIMEOUT = 20                     # secondi: una risposta più lenta vale «ancora fermo», e si riprova domani
SEGNO = "<!-- sentinella-understat: tornato -->"
AUTORI = {"github-actions", "github-actions[bot]"}     # il bot dei workflow (GraphQL e REST lo chiamano in due modi)
COMMENTO = ("Understat è tornato: riaccendere la fonte.\n\n"
            "La sentinella (workflow «Sentinella di Understat», una richiesta al giorno dai server di GitHub) ha ricevuto di nuovo "
            "i dati della Serie A al posto della pagina «We will come back soon». Prossimi passi: riaccendere la fonte dalla "
            "pagina dell'amministratore, guardare il primo aggiornamento, poi togliere il workflow "
            "`.github/workflows/sentinella-understat.yml` e lo script `script/ci/sentinella_understat.py`.")


def _lettore():
    from fanta.fonti import understat
    return understat


def indirizzo(anno: int | None = None) -> str:
    """L'indirizzo dei dati della Serie A della stagione in corso, lo stesso che usa il lettore."""
    if anno is None:
        from fanta.aggiorna import Stagione
        anno = Stagione.di(date.today()).anno
    return _lettore().url_lega(anno)


def dati_veri(contenuto: bytes) -> bool:
    """Vero solo se è JSON della lega che il lettore sa leggere, con almeno una partita: una pagina web, un JSON vuoto o di
    un'altra forma non bastano (un falso «è tornato» zittirebbe la sentinella per sempre)."""
    us = _lettore()
    try:
        partite, _ = us.leggi_lega(us.dati_json(contenuto))
    except (us.RispostaNonDati, LookupError, TypeError, ValueError, AttributeError):
        return False
    return bool(partite)


def controlla(url: str | None = None) -> str:
    """Una sola richiesta, nessun nuovo tentativo né reindirizzamento seguito: «tornato» se arrivano dati veri, altrimenti
    «fermo» (anche senza risposta o con un 3xx)."""
    import requests

    from fanta import rete
    us = _lettore()
    try:
        r = requests.get(url or indirizzo(), headers={"User-Agent": rete.UA, **us.HEADERS}, timeout=TIMEOUT,
                         allow_redirects=False)
    except requests.RequestException as e:
        print(f"Nessuna risposta da Understat ({type(e).__name__}): ancora fermo.")
        return "fermo"
    if r.status_code != 200:
        print(f"Understat risponde con il codice {r.status_code}: ancora fermo.")
        return "fermo"
    if not dati_veri(r.content):
        print("Understat risponde ancora senza i dati: ancora fermo.")
        return "fermo"
    print("Understat risponde di nuovo con i dati.")
    return "tornato"


def gia_avvisato(commenti: list[dict]) -> bool:
    """Un commento del bot dei workflow con il segno c'è già (quelli di altri non contano: il repository è pubblico)."""
    return any(SEGNO in (c.get("body") or "") and ((c.get("author") or {}).get("login") in AUTORI) for c in commenti)


def azioni(stato: str, commenti: list[dict]) -> list[str]:
    """Cosa fare sull'issue quando Understat è tornato: niente se già avvisato (anche se poi l'issue è stata chiusa)."""
    if gia_avvisato(commenti):
        return []
    return ["commenta"] + (["riapri"] if stato.upper() == "CLOSED" else [])


def avvisa(stato: str, commenti: list[dict], esegui: Callable[[list[str]], object], corsa: str = "") -> None:
    testo = COMMENTO + (f"\n\nCorsa: {corsa}" if corsa else "") + "\n\n" + SEGNO
    for azione in azioni(stato, commenti):
        if azione == "commenta":
            esegui(["gh", "issue", "comment", str(ISSUE), "--body", testo])
        elif azione == "riapri":
            esegui(["gh", "issue", "reopen", str(ISSUE)])


def _issue() -> tuple[str, list[dict]]:
    uscita = subprocess.run(["gh", "issue", "view", str(ISSUE), "--json", "state,comments"],
                            check=True, capture_output=True, text=True, encoding="utf-8").stdout
    dati = json.loads(uscita)
    return dati["state"], dati["comments"]


def _scrivi_uscita(chiave: str, valore: str) -> None:
    print(f"{chiave}={valore}")
    if percorso := os.environ.get("GITHUB_OUTPUT"):
        with open(percorso, "a", encoding="utf-8") as f:
            f.write(f"{chiave}={valore}\n")


def main(argomenti: list[str]) -> int:
    comando = argomenti[0] if argomenti else ""
    if comando == "gia-avvisato":
        _scrivi_uscita("avvisato", "si" if gia_avvisato(_issue()[1]) else "no")
    elif comando == "controlla":
        _scrivi_uscita("esito", controlla(argomenti[1] if len(argomenti) > 1 else None))
    elif comando == "avvisa":
        stato, commenti = _issue()
        avvisa(stato, commenti, lambda c: subprocess.run(c, check=True), corsa=os.environ.get("CORSA", ""))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
