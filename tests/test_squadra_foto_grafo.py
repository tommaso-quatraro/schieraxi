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


def test_i_nomi_dentro_una_interpolazione_contano():
    """«\\(Formato.euro(x))» dentro una stringa usa Formato: il testo della stringa no, quello fra «\\(» e «)» sì."""
    pulito = grafo_ios.pulisci('let s = "Prezzo \\(Formato.euro(x)) di Tizio"\nlet m = """\nRiga \\(Altro.y)\n"""\n')
    assert "Formato" in pulito and "euro" in pulito and "Altro" in pulito
    assert "Prezzo" not in pulito and "Tizio" not in pulito and "Riga" not in pulito
    testi = {**TESTI, "ios/Sources/Presentation/A/Riquadro.swift":
             'struct Riquadro: View {\n    var body: some View { Text("costa \\(Prezzo.uno)") }\n}\n',
             "ios/Sources/Domain/Prezzo.swift": "enum Prezzo {\n    static let uno = 1\n}\n"}
    s = _scegli("ios/Sources/Domain/Prezzo.swift", testi=testi)
    assert s["modo"] == "grafo" and s["schermate"] == ["a", "a-fondo"]


def test_una_radice_dentro_un_altra_porta_anche_le_schermate_di_fuori():
    """Come AspettoSezione dentro ImpostazioniView: una parte usata solo dalla sezione si vede anche nella pagina intera."""
    testi = {**TESTI,
             "ios/Sources/Presentation/A/VistaA.swift": "struct VistaA: View {\n    var body: some View { Sezione() }\n}\n",
             "ios/Sources/Presentation/A/Sezione.swift": "struct Sezione: View {\n    var body: some View { Riquadro() }\n}\n"}
    dati = {**DATI, "radici": {"a": ["VistaA"], "a-fondo": ["Sezione"], "b": ["VistaB"]}, "soglia_radici": 2}
    # senza «annidate» ci si ferma alla sezione (una pagina aperta da un'altra, come RosaView da ImpostazioniView, non è dentro)
    assert _scegli("ios/Sources/Presentation/A/Riquadro.swift", dati, testi)["schermate"] == ["a-fondo"]
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift", {**dati, "annidate": ["Sezione"]}, testi)
    assert s["modo"] == "grafo" and s["schermate"] == ["a", "a-fondo"]
    assert "VistaA ← Sezione ← Riquadro" in s["perche"]


def test_file_nuovo_prende_le_schermate_della_vista_che_lo_usa():
    """Il caso che costringeva a rinominare i file: una parte nuova senza regola a mano."""
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift")
    assert s["modo"] == "grafo" and s["schermate"] == ["a", "a-fondo"]
    assert "VistaA" in s["perche"] and "Riquadro" in s["perche"]


def test_parte_comune_oltre_la_soglia_usa_la_regola_larga():
    s = _scegli("ios/Sources/Support/Comune.swift")
    assert s["modo"] == "ripiego" and s["schermate"] == ["a"]


def test_regola_larga_piu_le_schermate_delle_viste_radice_del_file():
    """Un file che dichiara una vista radice (come LegaExtra.swift con StatoDatiView) e arriva a troppe radici prende la
    regola larga più le schermate delle viste radice che dichiara lui stesso: cambiarlo può cambiare proprio quelle."""
    testi = {k: v for k, v in TESTI.items() if k != "ios/Sources/Presentation/B/VistaB.swift"}
    testi["ios/Sources/Presentation/C/Insieme.swift"] = (
        "struct VistaB: View {\n    var body: some View { Comune() }\n}\n"
        "struct PezzoA: View {\n    var body: some View { Text(\"p\") }\n}\n")
    testi["ios/Sources/Presentation/A/VistaA.swift"] = "struct VistaA: View {\n    var body: some View { PezzoA() }\n}\n"
    s = _scegli("ios/Sources/Presentation/C/Insieme.swift", testi=testi)
    assert s["modo"] == "ripiego" and s["schermate"] == ["a", "b"]
    assert "VistaB" in s["perche"]


def test_contenitore_piu_le_schermate_delle_viste_radice_del_file():
    """Anche quando il codice arriva a un contenitore (Demo.swift dichiara ProvaMarchio): la regola larga può non comprendere
    la schermata della vista dichiarata nel file."""
    testi = {**TESTI, "ios/Sources/App/Contenitore.swift": "struct Contenitore: View {\n    var body: some View { PezzoB() }\n}\n"}
    testi["ios/Sources/Presentation/B/VistaB.swift"] += "struct PezzoB: View {\n    var body: some View { Text(\"p\") }\n}\n"
    dati = {**DATI, "contenitori": ["Contenitore"], "regole": DATI["regole"][1:]}
    s = _scegli("ios/Sources/Presentation/B/VistaB.swift", dati, testi)
    assert s["modo"] == "ripiego" and s["schermate"] == ["a", "b"]
    assert "VistaB" in s["perche"]


def test_estensione_di_una_vista_radice_conta_come_la_vista():
    testi = {**TESTI, "ios/Sources/Presentation/B/VistaB+Altro.swift":
             "extension VistaB {\n    var altro: some View { Text(\"x\") }\n}\n"
             "struct PezzoA: View {\n    var body: some View { Text(\"p\") }\n}\n"}
    testi["ios/Sources/Presentation/A/VistaA.swift"] = "struct VistaA: View {\n    var body: some View { PezzoA() }\n}\n"
    dati = {**DATI, "regole": DATI["regole"][1:]}
    s = _scegli("ios/Sources/Presentation/B/VistaB+Altro.swift", dati, testi)
    assert s["modo"] == "ripiego" and s["schermate"] == ["a", "b"] and "VistaB" in s["perche"]


def test_regola_a_mano_piu_le_schermate_delle_viste_radice_del_file():
    """Una regola a mano stretta che dimentica una schermata della vista del suo file (AccessoView.swift senza accesso-rete):
    la schermata si aggiunge da sola."""
    dati = {**DATI, "regole": [{"percorsi": ["ios/Sources/Presentation/A/VistaA.swift"], "schermate": ["a"]}] + DATI["regole"]}
    s = _scegli("ios/Sources/Presentation/A/VistaA.swift", dati)
    assert s["modo"] == "regola" and s["schermate"] == ["a", "a-fondo"]
    assert "VistaA" in s["perche"]


def test_regola_larga_senza_viste_radice_nel_file_resta_com_era():
    s = _scegli("ios/Sources/Support/Comune.swift")
    assert s["schermate"] == ["a"] and "dichiara" not in s["perche"]


def test_la_barriera_ferma_la_risalita():
    """ModelloA arriva a VistaB solo attraverso Tutto (come AppModel, che tutti usano): non conta."""
    s = _scegli("ios/Sources/Domain/ModelloA.swift")
    assert s["modo"] == "ripiego"


def test_una_parte_del_contenitore_dell_app_usa_la_regola_larga():
    """Un contenitore (come RadiceView) mostra le sue parti su ogni schermata: un file che ci arriva non si restringe alle
    poche viste radice trovate altrove, ma va alla regola larga come prima."""
    testi = {**TESTI, "ios/Sources/App/Contenitore.swift": "struct Contenitore: View {\n    var body: some View { Riquadro() }\n}\n"}
    dati = {**DATI, "contenitori": ["Contenitore"]}
    s = _scegli("ios/Sources/Presentation/A/Riquadro.swift", dati, testi)
    assert s["modo"] == "ripiego" and s["schermate"] == ["a"]
    assert "Contenitore" in s["perche"]


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


def test_lega_extra_porta_anche_lo_stato_dei_dati():
    """LegaExtra.swift contiene StatoDatiView (Impostazioni › Gestione › Stato dei dati): nella PR #850 le sue schermate
    erano state aggiunte a mano perché la regola larga della cartella Lega non le comprende."""
    s = foto.scegli("ios/Sources/Presentation/Lega/LegaExtra.swift", _dati(), foto.grafo_del_repository(),
                    foto.scene_di_screenshot())
    assert {"lega-stato", "lega-stato-nostri", "lega-stato-fondo"} <= set(s["schermate"])
    assert "StatoDatiView" in s["perche"]


def test_ogni_file_porta_le_schermate_delle_viste_radice_che_dichiara():
    """Regole a mano strette e regole larghe: le schermate della vista radice del file ci sono sempre (revisione di #855)."""
    dati, grafo, scene = _dati(), foto.grafo_del_repository(), foto.scene_di_screenshot()
    attese = {
        "ios/Sources/Support/Demo.swift": {"marchio"},
        "ios/Sources/Presentation/Lega/ImpostazioniView.swift": {"lega"},
        "ios/Sources/Presentation/Formazione/FormazioneView.swift": {"accesso-rose"},
        "ios/Sources/Presentation/Lega/AccountPagina.swift": {"accesso-account-fondo"},
        "ios/Sources/Presentation/Accesso/AccessoView.swift": {"accesso-rete", "accesso-limite", "accesso-non-valido"},
        "ios/Sources/Presentation/Accesso/ConfigurazioneGuidataView.swift": {"guida"},
    }
    for file, schermate in attese.items():
        assert schermate <= set(foto.scegli(file, dati, grafo, scene)["schermate"]), file


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


def test_ogni_radice_barriera_e_contenitore_e_un_tipo_dichiarato():
    g = foto.grafo_del_repository()
    dati = _dati()
    nomi = {t for tipi in dati["radici"].values() for t in tipi} | set(dati["barriere"]) | set(dati["contenitori"])
    assert set(dati["annidate"]) <= {t for tipi in dati["radici"].values() for t in tipi}, "ogni tipo di «annidate» è una radice"
    assert nomi - g.dichiarati == set(), "tipi di «radici», «barriere» o «contenitori» in script/squadra/foto.json che il codice non ha più"


def test_scene_di_screenshot_come_il_file():
    testo = (RADICE / "ios" / "scripts" / "screenshot.sh").read_text(encoding="utf-8")
    attese = re.search(r"^TUTTE=\((.*?)\)", testo, re.S | re.M).group(1).split()
    assert foto.scene_di_screenshot() == attese
