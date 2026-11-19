"""Le date del server lette e scritte in ora italiana, qualunque sia il fuso del browser (#776), con node.

`parseData` e `quando` di app.js con il fuso del processo messo apposta altrove (`process.env.TZ`, che node legge anche su
Windows) e l'orologio fermo. Il server scrive le date in ora italiana senza fuso (docs/API.md, «Date e ore»); la prova nel
browser vero è tests/browser/test_ora_italiana.py.
"""
import json
import shutil
import subprocess

import pytest

import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="serve node")

FUSI = ["America/New_York", "Asia/Tokyo", "UTC", "Europe/Rome"]
FERMO = "2026-10-27T14:10:00Z"           # martedì 27/10/2026, 15:10 in Italia (ora solare)


def _esegui(fuso: str, chiamata: str, fermo: str = FERMO):
    a = APP.index("function parseData(s)")
    codice = "\n".join([
        f"process.env.TZ = {json.dumps(fuso)};", TESTI, 'LINGUA = "it";',
        f"const FERMO = Date.parse({json.dumps(fermo)}), DataVera = Date;",
        "globalThis.Date = class extends DataVera { constructor(...a) { super(...(a.length ? a : [FERMO])); } static now() { return FERMO; } };",
        APP[a:APP.index("// ETag e If-Match", a)], f"console.log(JSON.stringify({chiamata}));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# data del server -> istante (UTC)
LETTURE = {
    "2026-10-27 18:20": "2026-10-27T17:20:00.000Z",                 # ora solare
    "2026-07-01T12:00:00": "2026-07-01T10:00:00.000Z",              # ora legale, con la T e i secondi
    "2026-10-25 01:30": "2026-10-24T23:30:00.000Z",                 # la notte del cambio di ottobre: prima (legale)
    "2026-10-25 03:30": "2026-10-25T02:30:00.000Z",                 # e dopo (solare)
    "2027-03-28 01:30": "2027-03-28T00:30:00.000Z",                 # la notte del cambio di marzo: prima (solare)
    "2027-03-28 03:30": "2027-03-28T01:30:00.000Z",                 # e dopo (legale)
    "2026-11-01": "2026-10-31T23:00:00.000Z",                       # solo il giorno: la mezzanotte italiana
    "2026-11-15T20:00:00+01:00": "2026-11-15T19:00:00.000Z",        # con il fuso (sentinella, account): com'è
    "2026-11-15T19:00:00.000Z": "2026-11-15T19:00:00.000Z",
}


@pytest.mark.parametrize("fuso", FUSI)
def test_parse_data_legge_l_ora_italiana(fuso):
    chiamata = f"{json.dumps(list(LETTURE))}.map(s => parseData(s).toISOString())"
    assert dict(zip(LETTURE, _esegui(fuso, chiamata), strict=True)) == LETTURE


@pytest.mark.parametrize("fuso", FUSI)
def test_parse_data_senza_una_data_da_null(fuso):
    assert _esegui(fuso, '["", null, undefined, "boh", "2026-13-01 10:00"].map(parseData)') == [None] * 5


# orologio fermo (UTC) -> {data del server: come si legge}
QUANDO = {
    # martedì 27/10 alle 15:10 italiane: a New York le 10:10, a Tokyo le 23:10, tutti martedì
    "2026-10-27T14:10:00Z": {"2026-10-27 18:20": "oggi 18:20", "2026-10-27 23:59": "oggi 23:59", "2026-10-28 00:30": "domani 00:30",
                             "2026-10-26 23:30": "ieri 23:30", "2026-10-31 20:45": "sab 31 20:45", "2026-10-24 20:45": "sab 24 20:45",
                             "2026-11-08 15:00": "dom 8 nov 15:00"},             # oltre la settimana anche il mese
    # martedì 27/10 alle 23:30 italiane: a Tokyo è già mercoledì, ma il giorno è quello italiano
    "2026-10-27T22:30:00Z": {"2026-10-27 23:45": "oggi 23:45", "2026-10-28 08:00": "domani 08:00"},
    # mercoledì 28/10 alle 00:30 italiane: a New York è ancora martedì
    "2026-10-27T23:30:00Z": {"2026-10-28 18:20": "oggi 18:20", "2026-10-27 22:00": "ieri 22:00"},
}


@pytest.mark.parametrize("fermo", list(QUANDO))
@pytest.mark.parametrize("fuso", FUSI)
def test_quando_conta_i_giorni_e_le_ore_in_italia(fuso, fermo):
    attese = QUANDO[fermo]
    assert dict(zip(attese, _esegui(fuso, f"{json.dumps(list(attese))}.map(quando)", fermo), strict=True)) == attese
