"""Contratto delle API fra server, web e iPhone: l'OpenAPI vero deve essere uguale all'istantanea in docs/openapi.json.

Se fallisce, l'API è cambiata: se è voluto, `python script/ci/aggiorna_openapi.py`, controlla web e iPhone
(docs/METODO.md, «Contratto delle API») e metti docs/openapi.json nella stessa pull request.
"""
import importlib.util
import json
from pathlib import Path

_f = Path(__file__).resolve().parent.parent / "script" / "ci" / "aggiorna_openapi.py"
_spec = importlib.util.spec_from_file_location("aggiorna_openapi", _f)
aggiorna_openapi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aggiorna_openapi)


def _operazioni(dati):
    return {f"{metodo.upper()} {percorso}" for percorso, metodi in dati.get("paths", {}).items() for metodo in metodi}


def test_api_uguale_all_istantanea():
    vero = aggiorna_openapi.contratto()
    assert aggiorna_openapi.ISTANTANEA.exists(), "Manca docs/openapi.json: lancia `python script/ci/aggiorna_openapi.py`."
    salvato = json.loads(aggiorna_openapi.ISTANTANEA.read_text(encoding="utf-8"))
    if vero == salvato:
        return
    nuove = sorted(_operazioni(vero) - _operazioni(salvato))
    tolte = sorted(_operazioni(salvato) - _operazioni(vero))
    schemi = sorted(set(vero.get("components", {}).get("schemas", {})) ^ set(salvato.get("components", {}).get("schemas", {})))
    raise AssertionError(
        "L'API del server non è più uguale a docs/openapi.json (contratto fra server, web e iPhone).\n"
        f"Rotte nuove: {nuove or 'nessuna'}\nRotte tolte: {tolte or 'nessuna'}\n"
        f"Modelli aggiunti o tolti: {schemi or 'nessuno'} (altrimenti sono cambiati campi, parametri o risposte)\n"
        "Se il cambio è voluto: `python script/ci/aggiorna_openapi.py`, guarda il diff di docs/openapi.json, controlla che web e\n"
        "iPhone reggano il cambio (docs/METODO.md, «Contratto delle API») e metti il file nella stessa pull request."
    )


def test_istantanea_senza_campi_instabili_e_ordinata():
    testo = aggiorna_openapi.ISTANTANEA.read_text(encoding="utf-8")
    assert '"operationId"' not in testo
    assert testo == aggiorna_openapi.testo(json.loads(testo)), "docs/openapi.json va scritto da script/ci/aggiorna_openapi.py"
