"""Giornate, web (#614, revisione di #642): la frase sulle giornate che non hanno un verdetto la scrive il server (`nota` di
`precisione.confronto` e di `scelte_tue`, `diario.nota_confronto`) e la pagina «Giornate» la mostra così com'è nei «Dettagli»,
tradotta con `nota_frase`. Prima la web scriveva una frase sua dal numero `senza_istantanea`, che non sapeva delle giornate con gli
stessi titolari. Si prova la funzione vera di `app.js` (`dettagliPrecisione`), con node, sulle risposte vere del server.
Qui anche i controlli che le fixture dell'iPhone siano quello che il server scrive davvero (`DiarioNotaTests.swift`,
`DiarioOrigineTests.swift`)."""
import html
import json
import re
import shutil
import subprocess

import pytest

from fanta import diario, precisione
from fanta.regole import Regole

import codice_web
from test_diario import CON_IL_25, ST, _mostrata, _scelta, finto  # noqa: F401  (fixture del Diario con dati finti)

APP = codice_web.app()
TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
FIXTURE_NOTA = codice_web.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "diario-nota.json"
FIXTURE_ORIGINE = codice_web.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "diario-origine.json"


def _funzione(nome: str) -> str:
    inizio = APP.index(f"function {nome}(")
    return APP[inizio:APP.index("\n}\n", inizio) + 3]


def _riga(prefisso: str) -> str:
    return next(r for r in APP.splitlines() if r.startswith(prefisso)) + "\n"


def _voce(g, tue, mostrata=True):
    """Una voce del Diario con la tua formazione: titolari 1-11 nella consigliata, i tuoi `tue`."""
    riga = lambda ids, r: {"reale": r, "atteso": 70.0, "titolari": [{"id": i, "nome": f"G{i}", "ruolo": "C"} for i in ids]}  # noqa: E731
    return {"stagione": ST, "giornata": g, "giornata_lega": g, "schierata": riga(tue, 66.0) | {"tipo": "manuale"},
            "consigliata": riga(range(1, 12), 70.0) | {"origine": "mostrata" if mostrata else "ricostruita"}, "giocatori": []}


UGUALI, DIVERSI = list(range(1, 12)), list(range(2, 13))
# le tre situazioni della revisione: solo giornate senza la consigliata di allora; una sola confrontabile, con gli stessi titolari,
# e cinque diverse lasciate fuori; una con un verdetto e una lasciata fuori
CASI = {"tutte_fuori": [_voce(g, DIVERSI, mostrata=False) for g in (1, 2, 3)],
        "una_uguale": [_voce(6, UGUALI)] + [_voce(g, DIVERSI, mostrata=False) for g in range(1, 6)],
        "verdetto": [_voce(2, DIVERSI), _voce(1, DIVERSI, mostrata=False)]}
ATTESE = {"it": {"tutte_fuori": "3 giornate non entrano nel confronto: la consigliata di allora non era stata salvata.",
                 "una_uguale": "Hai schierato gli stessi undici della consigliata in tutte le giornate in cui era stata salvata. "
                               "5 giornate non entrano nel confronto: la consigliata di allora non era stata salvata.",
                 "verdetto": "1 giornata non entra nel confronto: la consigliata di allora non era stata salvata."},
          "en": {"tutte_fuori": "3 matchdays are left out of the comparison: the recommended lineup of the time had not been saved.",
                 "una_uguale": "You fielded the same eleven as the recommended lineup in every matchday where it had been saved. "
                               "5 matchdays are left out of the comparison: the recommended lineup of the time had not been saved.",
                 "verdetto": "1 matchday is left out of the comparison: the recommended lineup of the time had not been saved."}}


def _dettagli(precisioni: dict, lingua: str) -> dict:
    """{nome: html} di `dettagliPrecisione(p, conConfronto)`, con `conConfronto` vero se una giornata ha la consigliata mostrata."""
    if NODE is None:
        pytest.skip("serve node")
    prova = (TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _riga("const num = ") + _riga("const virgola = ") + _riga("const alPercento = ")
             + _riga("const elidiOrdinali = ") + _funzione("esc") + _funzione("nomeGiornata") + _funzione("dettagliPrecisione")
             + f"\nconst r = {json.dumps(precisioni)};\n"
             + "console.log(JSON.stringify(Object.fromEntries(Object.entries(r).map(([k, x]) => [k, dettagliPrecisione(x.p, x.con)]))));")
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo(h: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", h)).split())


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_i_dettagli_di_giornate_mostrano_la_frase_del_server(lingua):
    precisioni = {nome: {"p": precisione.riassunto(voci), "con": any(v["consigliata"]["origine"] == "mostrata" for v in voci)}
                  for nome, voci in CASI.items()}
    carte = _dettagli(precisioni, lingua)
    for nome, h in carte.items():
        assert ATTESE[lingua][nome] in _testo(h), nome
        assert "frase.diario" not in h and "undefined" not in h and "null" not in h, nome
        if lingua == "it":                                                     # in italiano: il testo del server, uguale
            assert ATTESE["it"][nome] == precisioni[nome]["p"]["confronto"]["nota"]
    # con un verdetto il confronto c'è, e la frase dice solo chi resta fuori
    assert "1 su 1" in _testo(carte["verdetto"]) or "1 of 1" in _testo(carte["verdetto"])


def test_senza_la_frase_del_server_non_si_scrive_niente():
    """Un server senza `nota` (o niente da dire): nei Dettagli nessuna frase sulle giornate lasciate fuori."""
    p = {"giornate": 1, "confronto": {"giornate": 0, "senza_istantanea": 2}, "per_giornata": []}
    h = _dettagli({"x": {"p": p, "con": False}}, "it")["x"]
    assert "non entra" not in h and "qp-nota" not in h


# ---------------------------------------------------------------- le fixture dell'iPhone sono le risposte del server
def _risposte() -> dict:
    """Per ogni caso la risposta di `GET /api/diario` (solo i due blocchi che servono), come la scrive il server."""
    return {"casi": {nome: {"giornate": [], "scelte_tue": diario.scelte_tue(voci), "precisione": precisione.riassunto(voci)}
                     for nome, voci in CASI.items()}}


def test_la_fixture_della_frase_e_la_risposta_del_server():
    """`ios/Tests/Fixtures/diario-nota.json` (`DiarioNotaTests.swift`) è quello che il server scrive oggi per i tre casi (dati
    inventati). Se cambia, si rifà scrivendo `_risposte()` nel file (JSON, `indent=1`)."""
    assert json.loads(FIXTURE_NOTA.read_text(encoding="utf-8")) == _risposte()


def test_la_fixture_dell_origine_ha_i_campi_che_scrive_il_server(finto):  # noqa: F811 (fixture importata)
    """La voce «mostrata» di `diario-origine.json` (`DiarioOrigineTests.swift`) è scritta a mano: i suoi campi devono essere quelli
    di una voce vera del server."""
    vera = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), _scelta(CON_IL_25), simulazioni=50,
                                   istantanea=_mostrata(finto))
    finta = json.loads(FIXTURE_ORIGINE.read_text(encoding="utf-8"))["giornate"][0]
    assert vera["consigliata"]["origine"] == finta["consigliata"]["origine"] == "mostrata"
    assert vera["ricostruita"]["origine"] == finta["ricostruita"]["origine"] == "ricostruita"
    for campo in ("consigliata", "ricostruita", "schierata"):
        assert set(finta[campo]) <= set(vera[campo]), campo
