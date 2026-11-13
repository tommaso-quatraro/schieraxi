"""script/squadra: `foto` ricava le schermate da fotografare dai file iOS cambiati (foto.json) e stampa il comando."""
from __future__ import annotations

import json
import re

from test_squadra_comune import RADICE, Finto

import comune
import foto


def _tutte_le_schermate() -> set[str]:
    testo = (RADICE / "ios" / "scripts" / "screenshot.sh").read_text(encoding="utf-8")
    return set(re.search(r"^TUTTE=\((.*?)\)", testo, re.S | re.M).group(1).split())


def test_i_nomi_di_foto_json_esistono_in_screenshot_sh():
    tutte = _tutte_le_schermate()
    dati = comune.leggi_json("foto.json")
    nomi = set(dati["principali"])
    for r in dati["regole"]:
        if r["schermate"] != "principali":
            nomi |= set(r["schermate"])
    assert nomi - tutte == set()


def test_ogni_file_swift_di_oggi_ha_una_regola_o_e_ignorato():
    file = [str(p.relative_to(RADICE)).replace("\\", "/") for p in (RADICE / "ios").rglob("*.swift")]
    assert file
    assert foto.schermate(file)["senza"] == []


def test_schermate_dai_file():
    esito = foto.schermate(["ios/Sources/Presentation/Formazione/FormazioneView.swift",
                            "ios/Sources/Presentation/Mercato/SchedaGiocatoreView.swift",
                            "ios/Tests/SchieraxiTests/ViewModelTests.swift",
                            "fanta/server.py"])
    assert esito["schermate"][:5] == ["formazione", "formazione-fondo", "formazione-in-corso", "formazione-finita", "formazione-rinvio"]
    assert "giocatore" in esito["schermate"] and "giornate" not in esito["schermate"]
    assert esito["widget"] is False and esito["senza"] == []


def test_parte_comune_porta_le_principali_e_widget_la_sua_foto():
    esito = foto.schermate(["ios/Sources/Support/Design/Colori.swift", "ios/WidgetSources/Widget.swift"])
    assert esito["schermate"] == comune.leggi_json("foto.json")["principali"]
    assert esito["widget"] is True


def test_file_ios_senza_schermata_avvisa_ed_esce_con_3(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/scripts/nuovo.sh"},
                                          {"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}]}})
    assert foto.main(f, pr=7) == 3
    cattura = capsys.readouterr()
    assert "ios/scripts/nuovo.sh" in cattura.err and "foto.json" in cattura.err
    assert 'gh workflow run screenshot.yml --ref main -f dispositivi=iphone -f schermate="giornate' in cattura.out


def test_di_default_non_lancia_niente():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}]}})
    assert foto.main(f, pr=7) == 0
    assert not f.lanciati("gh workflow")


def test_lancia_solo_con_lancia():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/WidgetSources/W.swift"},
                                          {"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}]},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 0
    [c] = [c for c in f.chiamate if c[:3] == ["gh", "workflow", "run"]]
    assert c[c.index("-f") + 1] == "dispositivi=iphone"
    assert "widget=si" in c and any(a.startswith("schermate=giornate ") for a in c)


def test_da_commit_usa_git_diff():
    f = Finto({"git diff --name-only abc123..origin/main -- ios/": "ios/Sources/Presentation/Formazione/FormazioneView.swift\n"})
    assert foto.main(f, da="abc123") == 0
    assert f.lanciati("git diff")


def test_niente_ios(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "fanta/server.py"}]}})
    assert foto.main(f, pr=7) == 0
    assert "Nessuna schermata" in capsys.readouterr().out


def test_json(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}]}})
    foto.main(f, pr=7, json_=True)
    dati = json.loads(capsys.readouterr().out)
    assert dati["schermate"][0] == "giornate" and dati["comando"][:4] == ["gh", "workflow", "run", "screenshot.yml"]


def test_righe_dei_crediti_portano_solo_la_rosa():
    """#476: per RigaCreditiResidui.swift serviva solo «lega-rosa», non tutte le schermate «lega*»."""
    esito = foto.schermate(["ios/Sources/Presentation/Lega/RigaCreditiResidui.swift"])
    assert esito["schermate"] == ["lega-rosa"]


def test_ogni_file_di_presentation_ha_una_voce_o_un_ripiego_dichiarato():
    """Le regole «ripiego» (larghe) valgono per un file di ios/Sources/Presentation solo se è scritto in «ripiego_dichiarato»:
    un file nuovo chiede di scegliere le sue schermate invece di prendere tutte quelle di una sezione."""
    dati = comune.leggi_json("foto.json")
    dichiarati = set(dati["ripiego_dichiarato"])
    file = sorted(str(p.relative_to(RADICE)).replace("\\", "/")
                  for p in (RADICE / "ios" / "Sources" / "Presentation").rglob("*.swift"))
    assert file
    senza_voce = []
    for f in file:
        regola = next(r for r in dati["regole"] if any(foto.aree.corrisponde(f, p) for p in r["percorsi"]))
        if regola.get("ripiego") and f not in dichiarati:
            senza_voce.append(f)
    assert senza_voce == [], ("aggiungi una regola in script/squadra/foto.json o il file in «ripiego_dichiarato», "
                              "e script/squadra nella riga «Aree:» della PR")
    assert dichiarati - set(file) == set(), ("in «ripiego_dichiarato» di script/squadra/foto.json ci sono file che non "
                                             "esistono più (e script/squadra va nella riga «Aree:» della PR)")
