"""Catalogo unico dei testi (`fanta/testi/`) e generatore `script/testi.py`.

Il catalogo è la fonte: da lì nascono il blocco dei dati di `fanta/web/testi.js` (fra le due righe-segno) e i file Swift delle
chiavi che l'iPhone elenca in `ios/testi/<prefisso>.txt`. Qui si controlla che i file generati siano quelli del catalogo, che il
catalogo non abbia errori e che testi difficili (virgolette, barre, a capo, emoji) tornino uguali in JavaScript e in Swift.
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import codice_web

RADICE = Path(__file__).resolve().parent.parent
CATALOGO = RADICE / "fanta" / "testi"
IOS_TESTI = RADICE / "ios" / "testi"
CARTELLA_SWIFT = RADICE / "ios" / "Sources" / "Support" / "Catalogo"
SEGNO_INIZIO = "// <catalogo> generato da script/testi.py: non modificare a mano"
SEGNO_FINE = "// </catalogo>"

_spec = importlib.util.spec_from_file_location("script_testi", RADICE / "script" / "testi.py")
testi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(testi)

TESTI_JS_FINTO = (
    '"use strict";\n'
    "// commento in testa, scritto a mano\n"
    f"{SEGNO_INIZIO}\n"
    "const TESTI = {};\n"
    f"{SEGNO_FINE}\n"
    'const LINGUE = { it: "Italiano", en: "English" };\n'
)


def _lf(testo: str) -> str:
    return testo.replace("\r\n", "\n")


def _scrivi_catalogo(cartella: Path, file: dict) -> Path:
    """Un file `<prefisso>.json` per voce di `file`; un valore stringa si scrive così com'è (JSON scritto a mano)."""
    cartella.mkdir(parents=True, exist_ok=True)
    for prefisso, voci in file.items():
        testo = voci if isinstance(voci, str) else json.dumps(voci, ensure_ascii=False, indent=2)
        (cartella / f"{prefisso}.json").write_bytes(testo.encode("utf-8"))
    return cartella


def _radice(tmp_path: Path, catalogo: dict, ios: dict | None = None, testi_js: str = TESTI_JS_FINTO) -> Path:
    """Un repository finto: catalogo, `fanta/web/testi.js` e, se dati, gli elenchi `ios/testi/<prefisso>.txt`."""
    _scrivi_catalogo(tmp_path / "fanta" / "testi", catalogo)
    (tmp_path / "fanta" / "web").mkdir(parents=True)
    (tmp_path / "fanta" / "web" / "testi.js").write_bytes(testi_js.encode("utf-8"))
    if ios is not None:
        (tmp_path / "ios" / "testi").mkdir(parents=True)
        for prefisso, righe in ios.items():
            (tmp_path / "ios" / "testi" / f"{prefisso}.txt").write_bytes(righe.encode("utf-8"))
    return tmp_path


def _testi_js(radice: Path) -> str:
    return _lf(codice_web.leggi("testi.js", radice / "fanta" / "web"))


def _blocco_tra_i_segni(testo: str) -> str:
    return _lf(testo).split(SEGNO_INIZIO + "\n", 1)[1].split(SEGNO_FINE, 1)[0]


def _errore(cartella: Path) -> str:
    with pytest.raises(testi.ErroreCatalogo) as e:
        testi.carica_catalogo(cartella)
    return str(e.value)


# ---------------------------------------------------------------- il repository vero

def test_testi_js_e_generato_dal_catalogo():
    attuale = _blocco_tra_i_segni(codice_web.leggi("testi.js"))
    assert attuale == testi.blocco_testi_js(testi.carica_catalogo(CATALOGO)), \
        "fanta/web/testi.js non è quello generato: i testi si scrivono in fanta/testi/, poi python script/testi.py --scrivi"


def test_ogni_chiave_ios_esiste_nel_catalogo():
    assert testi.errori_ios(testi.carica_catalogo(CATALOGO), testi.chiavi_ios(IOS_TESTI)) == []


def test_file_swift_aggiornati(tmp_path):
    attesi = testi.swift(testi.carica_catalogo(CATALOGO), testi.chiavi_ios(IOS_TESTI))
    presenti = {p.name: _lf(p.read_text(encoding="utf-8")) for p in CARTELLA_SWIFT.glob("*.swift")} if CARTELLA_SWIFT.is_dir() else {}
    generati = {nome: testo for nome, testo in presenti.items() if testo.startswith("// Generato da script/testi.py")}
    assert generati == attesi, "i file Swift del catalogo non sono quelli generati: python script/testi.py --scrivi"
    (tmp_path / "vuota").mkdir()                       # nessun elenco dell'iPhone: nessun file Swift atteso
    catalogo = testi.carica_catalogo(CATALOGO)
    assert testi.chiavi_ios(tmp_path / "vuota") == {}
    assert testi.chiavi_ios(tmp_path / "assente") == {}
    assert testi.swift(catalogo, {}) == {}


def test_nomi_dei_file_swift_non_si_scontrano():
    """Due file con lo stesso nome nello stesso bersaglio non compilano (Swift usa il nome del file): i file generati non
    possono chiamarsi come un file dell'app, per nessun prefisso del catalogo."""
    nomi = {testi.nome_file_swift(p) for p in testi.carica_catalogo(CATALOGO)} | {"Catalogo.swift"}
    altri = {p.name for p in (RADICE / "ios").rglob("*.swift") if p.parent != CARTELLA_SWIFT}
    assert not nomi & altri, sorted(nomi & altri)


def test_una_riga_a_mano_in_testi_js_fa_fallire(tmp_path, capsys):
    shutil.copytree(CATALOGO, tmp_path / "fanta" / "testi")
    (tmp_path / "fanta" / "web").mkdir()
    vero = _lf(codice_web.leggi("testi.js"))
    (tmp_path / "fanta" / "web" / "testi.js").write_bytes(vero.encode("utf-8"))
    if IOS_TESTI.is_dir():
        shutil.copytree(IOS_TESTI, tmp_path / "ios" / "testi")
    if CARTELLA_SWIFT.is_dir():
        shutil.copytree(CARTELLA_SWIFT, tmp_path / "ios" / "Sources" / "Support" / "Catalogo")
    assert testi.main(["--controlla", "--radice", str(tmp_path)]) == 0

    a_mano = vero.replace("  it: {\n", '  it: {\n    "oggi.scritto_a_mano": "Scritto a mano",\n', 1)
    assert a_mano != vero
    (tmp_path / "fanta" / "web" / "testi.js").write_bytes(a_mano.encode("utf-8"))
    capsys.readouterr()
    assert testi.main(["--controlla", "--radice", str(tmp_path)]) == 1
    uscita = capsys.readouterr().out
    assert "testi.js" in uscita and "python script/testi.py --scrivi" in uscita


# ---------------------------------------------------------------- lettura del catalogo

def test_carica_catalogo_tiene_ordine_e_note(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {
        "oggi": {"oggi.b": {"it": "Bi", "en": "Bee"}, "oggi.a": {"it": "A", "en": "Ay", "nota": "sezione"}},
        "lega": {"lega.x": {"it": "Ics", "en": "Ex"}},
    })
    catalogo = testi.carica_catalogo(cartella)
    assert list(catalogo) == ["lega", "oggi"]                      # file in ordine alfabetico
    assert list(catalogo["oggi"]) == ["oggi.b", "oggi.a"]          # chiavi nell'ordine del file
    assert catalogo["oggi"]["oggi.a"] == testi.Voce(it="A", en="Ay", nota="sezione")
    assert catalogo["oggi"]["oggi.b"].nota is None


def test_chiave_nel_file_sbagliato(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {"oggi": {"mercato.prezzo": {"it": "Prezzo", "en": "Price"}}})
    messaggio = _errore(cartella)
    assert "mercato.prezzo" in messaggio and "mercato.json" in messaggio


def test_chiave_in_due_file(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {
        "oggi": {"oggi.titolo": {"it": "Oggi", "en": "Today"}},
        "lega": {"oggi.titolo": {"it": "Oggi", "en": "Today"}},
    })
    messaggio = _errore(cartella)
    assert "oggi.titolo" in messaggio and "due file" in messaggio


def test_chiave_ripetuta_nello_stesso_file(tmp_path):
    a_mano = '{\n  "oggi.a": {"it": "Uno", "en": "One"},\n  "oggi.a": {"it": "Due", "en": "Two"}\n}\n'
    assert "oggi.a" in _errore(_scrivi_catalogo(tmp_path / "testi", {"oggi": a_mano}))


@pytest.mark.parametrize("voce", [{"it": "Ciao"}, {"it": "Ciao", "en": "   "}, {"it": "", "en": "Hi"}, {"en": "Hi"}],
                         ids=["inglese-mancante", "inglese-vuoto", "italiano-vuoto", "italiano-mancante"])
def test_lingua_mancante_o_vuota(tmp_path, voce):
    assert "oggi.saluto" in _errore(_scrivi_catalogo(tmp_path / "testi", {"oggi": {"oggi.saluto": voce}}))


def test_segnaposto_diversi(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {"oggi": {
        "oggi.saluto": {"it": "Ciao {nome}", "en": "Hi {name}"},
        "oggi.giusta": {"it": "{n} punti", "en": "{n} points"},
    }})
    messaggio = _errore(cartella)
    assert "oggi.saluto" in messaggio and "oggi.giusta" not in messaggio


def test_plurale_incompleto(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {"oggi": {
        "oggi.titolari.one": {"it": "{n} titolare", "en": "{n} starter"},
        "oggi.panchina.one": {"it": "{n} riserva", "en": "{n} sub"},
        "oggi.panchina.other": {"it": "{n} riserve", "en": "{n} subs"},
    }})
    messaggio = _errore(cartella)
    assert "oggi.titolari" in messaggio and "oggi.panchina" not in messaggio


def test_campo_sconosciuto_in_una_voce(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {"oggi": {"oggi.a": {"it": "A", "en": "A", "fr": "A"}}})
    messaggio = _errore(cartella)
    assert "oggi.a" in messaggio and "fr" in messaggio


# ---------------------------------------------------------------- testi.js

def test_blocco_testi_js_forma(tmp_path):
    cartella = _scrivi_catalogo(tmp_path / "testi", {
        "oggi": {"oggi.b": {"it": "Bi", "en": "Bee", "nota": "non va nel file"}, "oggi.a": {"it": "A", "en": "Ay"}},
        "lega": {"lega.x": {"it": "Ics", "en": "Ex"}},
    })
    assert testi.blocco_testi_js(testi.carica_catalogo(cartella)) == (
        "const TESTI = {\n"
        "  it: {\n"
        '    "lega.x": "Ics",\n'
        "\n"
        '    "oggi.b": "Bi",\n'
        '    "oggi.a": "A",\n'
        "  },\n"
        "  en: {\n"
        '    "lega.x": "Ex",\n'
        "\n"
        '    "oggi.b": "Bee",\n'
        '    "oggi.a": "Ay",\n'
        "  },\n"
        "};\n"
    )


DIFFICILI = {
    "oggi.virgolette": "Tocca \"Salva\"",
    "oggi.barra": "C:\\cartella \\(non è Swift)",
    "oggi.a_capo": "riga uno\n        riga due",
    "oggi.tab": "a\tb",
    "oggi.emoji": "Gol ⚽ 🎉",
    "oggi.puntini": "«Carico…»",
    "oggi.separatore": "prima\u2028dopo",
    "oggi.conto.one": "{n} giocatore",
    "oggi.conto.other": "{n} giocatori",
}


def test_testi_difficili_tornano_uguali(tmp_path):
    voci = {k: {"it": v, "en": "EN " + v} for k, v in DIFFICILI.items()}
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {"oggi": voci}))
    blocco = testi.blocco_testi_js(catalogo)

    righe = [r for r in blocco.splitlines() if r.startswith('    "')]  # splitlines spezza anche su U+2028
    assert len(righe) == 2 * len(DIFFICILI), "ogni chiave deve stare su una riga sola"

    if shutil.which("node"):
        r = subprocess.run(["node", "-"], input=blocco + "console.log(JSON.stringify(TESTI));\n",
                           capture_output=True, encoding="utf-8", timeout=30)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout) == {"it": DIFFICILI, "en": {k: "EN " + v for k, v in DIFFICILI.items()}}

    elenco = "\n".join(DIFFICILI) + "\n"
    swift = testi.swift(catalogo, testi.chiavi_ios(_elenco_ios(tmp_path, {"oggi": elenco})))["Catalogo+Oggi.swift"]
    for attesa in (
        r'static let virgolette = "Tocca \"Salva\""',
        r'static let barra = "C:\\cartella \\(non è Swift)"',
        r'static let aCapo = "riga uno\n        riga due"',
        r'static let tab = "a\tb"',
        'static let emoji = "Gol ⚽ 🎉"',
        'static let puntini = "«Carico…»"',
        r'static let separatore = "prima\u{2028}dopo"',
        r'n == 1 ? "\(n) giocatore" : "\(n) giocatori"',
    ):
        assert attesa in swift, attesa
    assert "\u2028" not in swift


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_testi_js_generato_si_legge_con_node(tmp_path):
    radice = _radice(tmp_path, {"oggi": {"oggi.a": {"it": "A", "en": "Ay"}}})
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    r = subprocess.run(["node", "-"], input=_testi_js(radice) + "console.log(JSON.stringify([TESTI, LINGUE]));\n",
                       capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [{"it": {"oggi.a": "A"}, "en": {"oggi.a": "Ay"}}, {"it": "Italiano", "en": "English"}]


def test_scrivi_cambia_solo_il_blocco_fra_i_segni(tmp_path):
    radice = _radice(tmp_path, {"oggi": {"oggi.a": {"it": "A", "en": "Ay"}}})
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    assert _testi_js(radice) == (
        '"use strict";\n'
        "// commento in testa, scritto a mano\n"
        f"{SEGNO_INIZIO}\n"
        'const TESTI = {\n  it: {\n    "oggi.a": "A",\n  },\n  en: {\n    "oggi.a": "Ay",\n  },\n};\n'
        f"{SEGNO_FINE}\n"
        'const LINGUE = { it: "Italiano", en: "English" };\n'
    )
    assert testi.main(["--controlla", "--radice", str(radice)]) == 0


def test_senza_righe_segno_niente_scrittura(tmp_path, capsys):
    senza = '"use strict";\nconst TESTI = {};\n'
    radice = _radice(tmp_path, {"oggi": {"oggi.a": {"it": "A", "en": "Ay"}}}, testi_js=senza)
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 1
    assert _testi_js(radice) == senza
    assert testi.main(["--controlla", "--radice", str(radice)]) == 1
    assert "righe-segno" in capsys.readouterr().out


def test_catalogo_sbagliato_controlla_esce_con_1(tmp_path, capsys):
    radice = _radice(tmp_path, {"oggi": {"oggi.saluto": {"it": "Ciao {nome}", "en": "Hi"}}})
    assert testi.main(["--controlla", "--radice", str(radice)]) == 1
    assert "oggi.saluto" in capsys.readouterr().out
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 1
    assert _testi_js(radice) == TESTI_JS_FINTO


# ---------------------------------------------------------------- Swift

def _elenco_ios(tmp_path: Path, file: dict) -> Path:
    cartella = tmp_path / "elenchi"
    cartella.mkdir(exist_ok=True)
    for prefisso, testo in file.items():
        (cartella / f"{prefisso}.txt").write_bytes(testo.encode("utf-8"))
    return cartella


def test_chiavi_ios_legge_elenchi_e_commenti(tmp_path):
    cartella = _elenco_ios(tmp_path, {
        "oggi": "# chiavi di Oggi\noggi.b\n\n  oggi.a   # usata nella testata\n",
        "lega": "lega.x\n",
    })
    assert testi.chiavi_ios(cartella) == {"lega": ["lega.x"], "oggi": ["oggi.b", "oggi.a"]}


def test_swift_solo_per_le_chiavi_elencate(tmp_path):
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {
        "oggi": {
            "oggi.usata": {"it": "Usata", "en": "Used"},
            "oggi.non_usata": {"it": "Non usata", "en": "Unused"},
            "oggi.titolari.one": {"it": "{n} titolare", "en": "{n} starter"},
            "oggi.titolari.other": {"it": "{n} titolari", "en": "{n} starters"},
        },
        "lega": {"lega.x": {"it": "Ics", "en": "Ex"}},
    }))
    file = testi.swift(catalogo, {"oggi": ["oggi.usata", "oggi.titolari"]})
    assert sorted(file) == ["Catalogo+Oggi.swift", "Catalogo.swift"]
    assert "enum Catalogo {}" in file["Catalogo.swift"]
    oggi = file["Catalogo+Oggi.swift"]
    assert 'static let usata = "Usata"' in oggi
    assert "static func titolari(_ n: Int) -> String" in oggi
    assert "Non usata" not in oggi and "nonUsata" not in oggi
    for testo in file.values():
        assert testo.startswith("// Generato da script/testi.py: non modificare a mano")
    assert testi.swift(catalogo, {"oggi": ["oggi.titolari.one", "oggi.titolari.other"]}) \
        == testi.swift(catalogo, {"oggi": ["oggi.titolari"]})           # la coppia o la base: stessa funzione


def test_nomi_swift(tmp_path):
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {
        "oggi": {
            "oggi.tua_formazione": {"it": "La tua formazione", "en": "Your line-up"},
            "oggi.default": {"it": "Predefinito", "en": "Default"},
            "oggi.giorni_ore": {"it": "Mancano {giorni} giorni e {ore} ore", "en": "{giorni} days and {ore} hours left"},
            "oggi.prima_dopo": {"it": "{b} poi {a}", "en": "{b} then {a}"},
            "oggi.parola": {"it": "Fai {do} e {1}", "en": "Do {do} and {1}"},
            "oggi.titolari.one": {"it": "un titolare", "en": "one starter"},
            "oggi.titolari.other": {"it": "{n} titolari", "en": "{n} starters"},
            "oggi.giorni.one": {"it": "{n} giorno {h} h", "en": "{n} day {h} h"},
            "oggi.giorni.other": {"it": "{n} giorni {h} h", "en": "{n} days {h} h"},
        },
        "diff": {"diff.1": {"it": "Facile", "en": "Easy"}},
        "regola": {"regola.et.bonus.rigore_parato": {"it": "Rigore parato", "en": "Penalty saved"}},
        "ruolo": {"ruolo.P_pl": {"it": "Portieri", "en": "Goalkeepers"}},
    }))
    chiavi = {"oggi": list(catalogo["oggi"]), "diff": ["diff.1"], "regola": ["regola.et.bonus.rigore_parato"],
              "ruolo": ["ruolo.P_pl"]}
    file = testi.swift(catalogo, chiavi)
    oggi = file["Catalogo+Oggi.swift"]
    for attesa in (
        "extension Catalogo {\n    enum Oggi {\n",
        'static let tuaFormazione = "La tua formazione"',
        'static let `default` = "Predefinito"',
        "static func giorniOre(giorni: String, ore: String) -> String {\n"
        '            "Mancano \\(giorni) giorni e \\(ore) ore"\n        }',
        'static func primaDopo(a: String, b: String) -> String {\n            "\\(b) poi \\(a)"\n        }',
        'static func parola(_1: String, `do`: String) -> String {\n            "Fai \\(`do`) e \\(_1)"\n        }',
        'static func titolari(_ n: Int) -> String {\n            n == 1 ? "un titolare" : "\\(n) titolari"\n        }',
        "static func giorni(_ n: Int, h: String) -> String {",
    ):
        assert attesa in oggi, attesa
    assert 'enum Diff {\n        /// `diff.1`\n        static let _1 = "Facile"' in file["Catalogo+Diff.swift"]
    assert 'static let etBonusRigoreParato = "Rigore parato"' in file["Catalogo+Regola.swift"]
    assert 'static let pPl = "Portieri"' in file["Catalogo+Ruolo.swift"]


def test_plurale_segnaposto_solo_dentro_ogni_testo(tmp_path):
    """I segnaposto del plurale si cercano in `.one` e in `.other` separati: le due frasi attaccate non ne inventano uno."""
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {"oggi": {
        "oggi.graffe.one": {"it": "uno {", "en": "one {"},
        "oggi.graffe.other": {"it": "x} {n}", "en": "x} {n}"},
    }}))
    oggi = testi.swift(catalogo, {"oggi": ["oggi.graffe"]})["Catalogo+Oggi.swift"]
    assert "static func graffe(_ n: Int) -> String {" in oggi
    assert 'n == 1 ? "uno {" : "x} \\(n)"' in oggi


def test_nomi_swift_uguali_sono_un_errore(tmp_path):
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {"oggi": {
        "oggi.a_b": {"it": "Uno", "en": "One"},
        "oggi.a.b": {"it": "Due", "en": "Two"},
    }}))
    with pytest.raises(testi.ErroreCatalogo) as e:
        testi.swift(catalogo, {"oggi": ["oggi.a_b", "oggi.a.b"]})
    assert "oggi.a_b" in str(e.value) and "oggi.a.b" in str(e.value)


def test_chiave_ios_mancante_o_nel_file_sbagliato(tmp_path):
    catalogo = testi.carica_catalogo(_scrivi_catalogo(tmp_path / "testi", {
        "oggi": {"oggi.a": {"it": "A", "en": "Ay"}},
        "lega": {"lega.x": {"it": "Ics", "en": "Ex"}},
    }))
    errori = testi.errori_ios(catalogo, {"oggi": ["oggi.a", "oggi.sparita", "lega.x"]})
    assert len(errori) == 2
    assert any("oggi.sparita" in e for e in errori) and any("lega.x" in e and "lega.txt" in e for e in errori)
    with pytest.raises(testi.ErroreCatalogo):
        testi.swift(catalogo, {"oggi": ["oggi.sparita"]})


def test_testo_cambiato_senza_rigenerare_fa_fallire(tmp_path, capsys):
    catalogo = {"oggi": {"oggi.a": {"it": "A", "en": "Ay"}, "oggi.b": {"it": "Bi", "en": "Bee"}}}
    radice = _radice(tmp_path, catalogo, ios={"oggi": "oggi.a\n"})
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    generato = radice / "ios" / "Sources" / "Support" / "Catalogo" / "Catalogo+Oggi.swift"
    assert 'static let a = "A"' in generato.read_text(encoding="utf-8")
    assert testi.main(["--controlla", "--radice", str(radice)]) == 0

    catalogo["oggi"]["oggi.a"]["it"] = "A nuova"
    _scrivi_catalogo(radice / "fanta" / "testi", catalogo)
    capsys.readouterr()
    assert testi.main(["--controlla", "--radice", str(radice)]) == 1
    assert "Catalogo+Oggi.swift" in capsys.readouterr().out
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    assert 'static let a = "A nuova"' in generato.read_text(encoding="utf-8")


def test_scrivi_toglie_i_file_swift_non_piu_elencati(tmp_path):
    radice = _radice(tmp_path, {"oggi": {"oggi.a": {"it": "A", "en": "Ay"}}}, ios={"oggi": "oggi.a\n"})
    cartella = radice / "ios" / "Sources" / "Support" / "Catalogo"
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    a_mano = cartella / "Scritto.swift"
    a_mano.write_bytes(b"// scritto a mano\n")
    (radice / "ios" / "testi" / "oggi.txt").write_bytes(b"# nessuna chiave\n")
    assert testi.main(["--controlla", "--radice", str(radice)]) == 1
    assert testi.main(["--scrivi", "--radice", str(radice)]) == 0
    assert sorted(p.name for p in cartella.iterdir()) == ["Scritto.swift"]   # i generati se ne vanno, quello a mano resta
    assert testi.main(["--controlla", "--radice", str(radice)]) == 0
