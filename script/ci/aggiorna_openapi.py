"""Istantanea del contratto delle API (`docs/openapi.json`): rotte, parametri, corpi e risposte del server FastAPI.

Web, iPhone e widget leggono le stesse rotte: `tests/test_contratto_api.py` confronta l'API vera con questa istantanea, così
ogni rotta o campo che cambia si vede nel diff della pull request. Quando cambi l'API apposta:

    python script/ci/aggiorna_openapi.py

poi controlla web e iPhone (docs/METODO.md, «Contratto delle API») e metti nella stessa pull request il file aggiornato.
Togliamo solo ciò che FastAPI genera in modo diverso a ogni avvio e che nessun client usa (`operationId`: per le rotte
GET+HEAD dipende dall'ordine casuale dei metodi).
"""
import json
import sys
import warnings
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
ISTANTANEA = RADICE / "docs" / "openapi.json"
INSTABILI = {"operationId"}


def _pulisci(x):
    if isinstance(x, dict):
        return {k: _pulisci(v) for k, v in x.items() if k not in INSTABILI}
    if isinstance(x, list):
        return [_pulisci(v) for v in x]
    return x


def contratto() -> dict:
    """L'OpenAPI del server, senza i campi instabili."""
    if str(RADICE) not in sys.path:
        sys.path.insert(0, str(RADICE))
    from fanta import server
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)        # «Duplicate Operation ID» delle rotte GET+HEAD
        server.app.openapi_schema = None                    # ricalcola: niente copia vecchia in memoria
        return _pulisci(server.app.openapi())


def testo(dati: dict) -> str:
    return json.dumps(dati, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def main() -> int:
    nuovo = testo(contratto())
    vecchio = ISTANTANEA.read_text(encoding="utf-8") if ISTANTANEA.exists() else ""
    if nuovo == vecchio:
        print("docs/openapi.json è già aggiornato.")
        return 0
    ISTANTANEA.write_text(nuovo, encoding="utf-8", newline="\n")
    print("docs/openapi.json aggiornato: guarda il diff e controlla web e iPhone (docs/METODO.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
