"""script/squadra: le schermate da fotografare ricavate dal codice Swift (#505).

Il grafo dei tipi (`grafo_ios.py`) collega un file alle viste «radice» delle schermate (sezione `radici` di foto.json):
un file nuovo prende le schermate delle viste che lo usano, senza una regola a mano."""
from __future__ import annotations

import re

from test_squadra_comune import RADICE

import comune
import foto
import grafo_ios

# Un albero finto: due schermate con la loro vista radice, una parte usata da una sola, una parte comune a tutte e due,
# un modello usato attraverso una «barriera» (l'oggetto che tiene tutto, come AppModel), un'estensione di View.
TESTI = {
    "ios/Sources/Presentation/A/VistaA.swift": "struct VistaA: View {\n    var body: some View { Riquadro(); Comune(); Text(\"x\").bordino() }\n}\n",
    "ios/Sources/Presentation/A/Riquadro.swift": "struct Riquadro: View {\n    var body: some View { Text(\"r\") }\n}\n",
    "ios/Sources/Presentation/B/VistaB.swift": "struct VistaB: View {\n    @EnvironmentObject var m: Tutto\n    var body: some View { Comune() }\n}\n",
    "ios/Sources/Support/Comune.swift": "struct Comune: View {\n    var body: some View { Text(\"c\") }\n}\n",
    "ios/Sources/App/Tutto.swift": "final class Tutto {\n    let v = ModelloA()\n}\n",
    "ios/Sources/Domain/ModelloA.swift": "struct ModelloA {\n    let n = 1\n}\n",
    "ios/Sources/Support/Bordino.swift": "extension View {\n    func bordino() -> some View { self }\n}\n",
}

DATI = {
    "principali": ["a"],
    "radici": {"a*": ["VistaA"], "b": ["VistaB"]},
    "barriere": ["Tutto"],
    "soglia_radici": 1,
    "regole": [
        {"percorsi": ["ios/Sources/Presentation/B/VistaB.swift"], "schermate": ["b"]},
        {"percorsi": ["ios/Sources/**"], "ripiego": True, "schermate": "principali"},
    ],
    "ripiego_dichiarato": [],
    "widget": [],
    "ignora": [],
}
SCENE = ["a", "a-fondo", "b"]


def _scegli(file: str, dati: dict = DATI, testi: dict = TESTI) -> dict:
    return foto.scegli(file, dati, grafo_ios.Grafo(testi), SCENE)


def test_tipi_in_commenti_e_stringhe_non_contano():
    testo = ('// struct Finta {}\n/* class Altra {} */\nlet s = "struct Stringa {}"\n'
             'let m = """\nenum Lunga {}\n"""\nstruct Vera {}\nprivate struct Nascosta {}\nextension Vera {}\n')
    assert grafo_ios.tipi_dichiarati(testo) == {"Vera", "Nascosta"}


def test_file_nuovo_prende_le_schermate_della_vista_che_lo_usa():
    """Il caso che costringeva a rinominare i file: una parte nuova senza regola a mano."""
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift")
    assert s["modo"] == "grafo" and s["schermate"] == ["a", "a-fondo"]
    assert "VistaA" in s["perche"] and "Riquadro" in s["perche"]


def test_parte_comune_oltre_la_soglia_usa_la_regola_larga():
    s = _scegli("ios/Sources/Support/Comune.swift")
    assert s["modo"] == "ripiego" and s["schermate"] == ["a"]


def test_la_barriera_ferma_la_risalita():
    """ModelloA arriva a VistaB solo attraverso Tutto (come AppModel, che tutti usano): non conta."""
    s = _scegli("ios/Sources/Domain/ModelloA.swift")
    assert s["modo"] == "ripiego"


def test_estensione_di_un_tipo_esterno_va_a_chi_usa_i_suoi_membri():
    s = _scegli("ios/Sources/Support/Bordino.swift")
    assert s["modo"] == "grafo" and s["schermate"] == ["a", "a-fondo"]


def test_le_regole_a_mano_vincono_sul_grafo():
    dati = {**DATI, "regole": [{"percorsi": ["ios/Sources/Presentation/A/Riquadro.swift"], "schermate": ["b"]}] + DATI["regole"]}
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift", dati)
    assert s["modo"] == "regola" and s["schermate"] == ["b"]


def test_i_tipi_privati_valgono_solo_nel_loro_file():
    testi = {**TESTI, "ios/Sources/Presentation/A/Riquadro.swift": "private struct Riquadro: View {\n    var body: some View { Text(\"r\") }\n}\n"}
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift", testi=testi)
    assert s["modo"] == "ripiego"


def test_file_che_non_esiste_sul_disco_usa_le_regole():
    """Un file di una PR aperta che qui non c'è (o un file tolto): niente grafo, valgono le regole di prima."""
    s = _scegli("ios/Sources/Presentation/A/Nuovissimo.swift")
    assert s["modo"] == "ripiego" and s["schermate"] == ["a"]


def test_schermate_usa_il_grafo_e_spiega():
    esito = foto.schermate(["ios/Sources/Presentation/A/Riquadro.swift"], dati=DATI, grafo=grafo_ios.Grafo(TESTI), scene=SCENE)
    assert esito["schermate"] == ["a", "a-fondo"] and esito["senza"] == []
    assert "VistaA" in esito["perche"]["ios/Sources/Presentation/A/Riquadro.swift"]


# --- Il repository vero ---------------------------------------------------------------------------------------------

def _dati() -> dict:
    return comune.leggi_json("foto.json")


def test_ogni_schermata_di_screenshot_ha_una_radice():
    """Una schermata nuova di screenshot.sh chiede le sue viste radice in foto.json, o il grafo non la sceglie mai."""
    radici = _dati()["radici"]
    senza = [s for s in foto.scene_di_screenshot() if not any(foto.aree.corrisponde(s, m) for m in radici)]
    assert senza == [], "aggiungi le viste radice di queste schermate in «radici» di script/squadra/foto.json"


def test_ogni_modello_di_radici_corrisponde_a_una_schermata():
    """Una schermata rinominata o tolta in screenshot.sh (#710: «impostazioni-avanzate» → «-gestione») non resta qui."""
    scene = foto.scene_di_screenshot()
    vecchi = [m for m in _dati()["radici"] if not any(foto.aree.corrisponde(s, m) for s in scene)]
    assert vecchi == [], "in «radici» di script/squadra/foto.json ci sono schermate che screenshot.sh non ha più"


def test_ogni_radice_e_ogni_barriera_sono_tipi_dichiarati():
    g = foto.grafo_del_repository()
    dati = _dati()
    nomi = {t for tipi in dati["radici"].values() for t in tipi} | set(dati["barriere"])
    assert nomi - g.dichiarati == set(), "tipi di «radici» o «barriere» in script/squadra/foto.json che il codice non ha più"


def test_scene_di_screenshot_come_il_file():
    testo = (RADICE / "ios" / "scripts" / "screenshot.sh").read_text(encoding="utf-8")
    attese = re.search(r"^TUTTE=\((.*?)\)", testo, re.S | re.M).group(1).split()
    assert foto.scene_di_screenshot() == attese


def test_caso_vero_la_pillola_tua_porta_solo_le_squadre():
    """PillolaTua.swift ha una regola a mano (rosa); senza, il grafo la trova solo dentro RigaSquadra → «lega-squadre»."""
    dati = {**_dati(), "regole": [r for r in _dati()["regole"]
                                  if "ios/Sources/Presentation/Lega/PillolaTua.swift" not in r["percorsi"]]}
    s = foto.scegli("ios/Sources/Presentation/Lega/PillolaTua.swift", dati, foto.grafo_del_repository(),
                    foto.scene_di_screenshot())
    assert s["modo"] == "grafo" and s["schermate"] == ["lega-squadre"]
