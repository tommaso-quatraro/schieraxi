"""Diario, web (#614): l'etichetta dei punti della consigliata segue `consigliata.origine`. Con «mostrata» quei punti sono della
consigliata che SchieraXI mostrava prima della scadenza, non di una ricostruzione: prima la riga diceva «Ricostruita oggi» ogni
volta che c'era l'istantanea. Un server di prima non manda `origine`: per lui resta tutto com'era.
Si prova la funzione vera di `app.js`, con node, sulle voci nelle due forme (con e senza `origine`)."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import diario
from fanta.regole import Regole

import codice_web
from test_diario import CON_IL_25, ST, _mostrata, _scelta, finto  # noqa: F401  (fixture del Diario con dati finti)

APP = codice_web.app()
TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
# le stesse voci dei test dell'iPhone (DiarioOrigineTests): giornate 11, 10 e 9 con `origine`, 8 e 7 senza (server di prima)
FIXTURE_IOS = codice_web.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "diario-origine.json"
ISTANTANEA = {"giornata": 11, "modulo": "3-4-3", "titolari": [{"id": 1, "nome": "G1", "ruolo": "P"}], "atteso": 72.5,
              "calcolata": "2026-11-06T15:20:00"}


def _voce(modulo, origine=None, istantanea=None):
    """Una voce di `GET /api/diario`, solo con quello che serve all'etichetta. Senza `origine` è quella di un server di prima."""
    consigliata = {"modulo": modulo, "atteso": 70.0, "reale": 66.0} | ({"origine": origine} if origine else {})
    return {"stagione": "2026-27", "giornata": 11, "consigliata": consigliata, "istantanea": istantanea}


def _etichette(voci, lingua="it"):
    if NODE is None:
        pytest.skip("serve node")
    esc = APP[APP.index("function esc(x)"):APP.index("\n}\n", APP.index("function esc(x)")) + 3]
    funzione = re.search(r"^const etichettaConsigliataDiario = .*$", APP, re.M)
    assert funzione, "in app.js manca etichettaConsigliataDiario"
    prova = (TESTI_JS + f'\nLINGUA = "{lingua}";\n' + esc + funzione.group(0)
             + f"\nconsole.log(JSON.stringify({json.dumps(voci)}.map(etichettaConsigliataDiario)));")
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_i_punti_della_consigliata_mostrata_non_si_chiamano_ricostruita():
    assert _etichette([_voce("3-4-3", "mostrata", ISTANTANEA)]) == ["La consigliata (3-4-3)"]
    assert _etichette([_voce("3-4-3", "mostrata", ISTANTANEA)], "en") == ["The recommended one (3-4-3)"]


def test_la_ricostruita_resta_detta_ricostruita():
    """`origine: "ricostruita"`: la consigliata di allora c'è ma non si può più schierare, oppure non era stata registrata."""
    assert _etichette([_voce("4-4-2", "ricostruita", ISTANTANEA), _voce("4-4-2", "ricostruita")]) == [
        "Ricostruita oggi (4-4-2)", "Del modello (4-4-2)"]


def test_con_un_server_di_prima_resta_com_era():
    """Senza `origine` la consigliata della voce è sempre la ricostruzione: le due etichette di prima."""
    assert _etichette([_voce("4-3-3", None, ISTANTANEA), _voce("4-3-3")]) == ["Ricostruita oggi (4-3-3)", "Del modello (4-3-3)"]


def test_il_modulo_scritto_dal_server_passa_da_esc():
    assert _etichette([_voce("<b>3-4-3</b>", "mostrata", ISTANTANEA)]) == ["La consigliata (&lt;b&gt;3-4-3&lt;/b&gt;)"]


def test_le_stesse_voci_dei_test_dell_iphone():
    """Web e iPhone sulle stesse voci, nelle due forme. L'iPhone scrive le stesse etichette; dove la web dice «Del modello»
    lui dice «Di SchieraXI», come prima di questa modifica."""
    voci = json.loads(FIXTURE_IOS.read_text(encoding="utf-8"))["giornate"]
    assert [(v["giornata"], v["consigliata"].get("origine")) for v in voci] == [
        (11, "mostrata"), (10, "ricostruita"), (9, "ricostruita"), (8, None), (7, None)]
    assert _etichette(voci) == ["La consigliata (3-4-3)", "Ricostruita oggi (4-4-2)", "Del modello (4-4-2)",
                                "Ricostruita oggi (4-3-3)", "Del modello (4-3-3)"]


def test_la_fixture_dell_iphone_ha_i_campi_che_scrive_il_server(finto):  # noqa: F811 (fixture importata)
    """La voce «mostrata» della fixture è scritta a mano: i suoi campi devono essere quelli di una voce vera del server."""
    vera = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), _scelta(CON_IL_25), simulazioni=50,
                                   istantanea=_mostrata(finto))
    finta = json.loads(FIXTURE_IOS.read_text(encoding="utf-8"))["giornate"][0]
    assert vera["consigliata"]["origine"] == finta["consigliata"]["origine"] == "mostrata"
    assert vera["ricostruita"]["origine"] == finta["ricostruita"]["origine"] == "ricostruita"
    for campo in ("consigliata", "ricostruita", "schierata"):
        assert set(finta[campo]) <= set(vera[campo]), campo


def test_la_riga_dei_punti_del_diario_usa_quell_etichetta():
    corpo = APP[APP.index("async function apriDiario("):APP.index("async function correggiDiario(")]
    assert "righePunti(etichettaConsigliataDiario(g), g.consigliata)" in corpo
