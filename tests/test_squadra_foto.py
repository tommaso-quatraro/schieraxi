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
    esito = foto.schermate(["ios/Sources/Presentation/Oggi/OggiView.swift",
                            "ios/Sources/Presentation/Mercato/SchedaGiocatoreView.swift",
                            "ios/Tests/SchieraxiTests/ViewModelTests.swift",
                            "fanta/server.py"])
    assert esito["schermate"][:5] == ["oggi", "oggi-fondo", "oggi-in-corso", "oggi-finita", "oggi-rinvio"]
    assert "giocatore" in esito["schermate"] and "mercato-consigliati" not in esito["schermate"]
    assert esito["widget"] is False and esito["senza"] == []


def test_parte_comune_porta_le_principali_e_widget_la_sua_foto():
    esito = foto.schermate(["ios/Sources/Support/Design/Colori.swift", "ios/WidgetSources/Widget.swift"])
    assert esito["schermate"] == comune.leggi_json("foto.json")["principali"]
    assert esito["widget"] is True


def test_file_ios_senza_schermata_avvisa_ed_esce_con_3(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/scripts/nuovo.sh"},
                                          {"path": "ios/Sources/Presentation/Scambi/ScambiView.swift"}]}})
    assert foto.main(f, pr=7) == 3
    cattura = capsys.readouterr()
    assert "ios/scripts/nuovo.sh" in cattura.err and "foto.json" in cattura.err
    assert 'gh workflow run screenshot.yml --ref main -f dispositivi=iphone -f schermate="scambi' in cattura.out


def test_di_default_non_lancia_niente():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Scambi/ScambiView.swift"}]}})
    assert foto.main(f, pr=7) == 0
    assert not f.lanciati("gh workflow")


def test_lancia_solo_con_lancia():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/WidgetSources/W.swift"},
                                          {"path": "ios/Sources/Presentation/Scambi/ScambiView.swift"}]},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 0
    [c] = [c for c in f.chiamate if c[:3] == ["gh", "workflow", "run"]]
    assert c[c.index("-f") + 1] == "dispositivi=iphone"
    assert "widget=si" in c and any(a.startswith("schermate=scambi ") for a in c)


def test_da_commit_usa_git_diff():
    f = Finto({"git diff --name-only abc123..origin/main -- ios/": "ios/Sources/Presentation/Formazione/FormazioneView.swift\n"})
    assert foto.main(f, da="abc123") == 0
    assert f.lanciati("git diff")


def test_niente_ios(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "fanta/server.py"}]}})
    assert foto.main(f, pr=7) == 0
    assert "Nessuna schermata" in capsys.readouterr().out


def test_json(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Scambi/ScambiView.swift"}]}})
    foto.main(f, pr=7, json_=True)
    dati = json.loads(capsys.readouterr().out)
    assert dati["schermate"][0] == "scambi" and dati["comando"][:4] == ["gh", "workflow", "run", "screenshot.yml"]
