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
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/altro/nuovo.sh"},
                                          {"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}]}})
    assert foto.main(f, pr=7) == 3
    cattura = capsys.readouterr()
    assert "ios/altro/nuovo.sh" in cattura.err and "foto.json" in cattura.err
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
    """Un file di ios/Sources/Presentation non prende in silenzio tutte le schermate di una sezione: ha una regola stretta, o il
    codice lo porta a poche viste radice («radici» di foto.json, #505), o è scritto in «ripiego_dichiarato» (parti comuni)."""
    dati = comune.leggi_json("foto.json")
    dichiarati = set(dati["ripiego_dichiarato"])
    file = sorted(str(p.relative_to(RADICE)).replace("\\", "/")
                  for p in (RADICE / "ios" / "Sources" / "Presentation").rglob("*.swift"))
    assert file
    grafo, scene = foto.grafo_del_repository(), foto.scene_di_screenshot()
    senza_voce = [f for f in file if f not in dichiarati and foto.scegli(f, dati, grafo, scene)["modo"] in ("ripiego", "senza")]
    assert senza_voce == [], ("il codice non porta questi file a nessuna vista radice (o a troppe): aggiungi una regola in "
                              "script/squadra/foto.json, le viste radice in «radici» o il file in «ripiego_dichiarato», "
                              "e script/squadra nella riga «Aree:» della PR")
    assert dichiarati - set(file) == set(), ("in «ripiego_dichiarato» di script/squadra/foto.json ci sono file che non "
                                             "esistono più (e script/squadra va nella riga «Aree:» della PR)")


def _ref_lanciato(f) -> str:
    [c] = [c for c in f.chiamate if c[:3] == ["gh", "workflow", "run"]]
    return c[c.index("--ref") + 1]


def test_pr_aperta_fotografa_il_suo_ramo():
    """#717: per una PR aperta le foto vanno fatte sul suo ramo, non su main (che non ha ancora le sue modifiche)."""
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo-della-pr", "state": "OPEN"},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 0
    assert _ref_lanciato(f) == "ramo-della-pr"


def test_pr_unita_fotografa_main():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo-della-pr", "state": "MERGED"},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 0
    assert _ref_lanciato(f) == "main"


def test_ref_scritto_a_mano_vince_sul_ramo_della_pr():
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo-della-pr", "state": "OPEN"},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True, ref="altro") == 0
    assert _ref_lanciato(f) == "altro"


def test_pr_aperta_da_riga_di_comando_usa_il_ramo(capsys):
    import squadra
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo-della-pr", "state": "OPEN"}})
    squadra.main(["foto", "7"], esegui=f)
    assert "--ref ramo-della-pr" in capsys.readouterr().out


def test_gli_strumenti_di_ios_scripts_non_chiedono_foto():
    """#717: ios/scripts/screenshot.sh (lo strumento delle foto, non l'app) dava l'avviso «aggiungi una regola»."""
    esito = foto.schermate(["ios/scripts/screenshot.sh", "ios/scripts/schermo_fermo.py"])
    esito.pop("perche")
    assert esito == {"schermate": [], "widget": False, "senza": []}


def test_gli_script_dei_widget_chiedono_le_foto_dei_widget():
    esito = foto.schermate(["ios/scripts/screenshot_widget.sh"])
    esito.pop("perche")
    assert esito == {"schermate": [], "widget": True, "senza": []}


def test_ios_scripts_come_file_widget_di_screenshot_yml():
    """Ogni file di ios/scripts chiede le foto dei widget se e solo se FILE_WIDGET di screenshot.yml lo fa ripartire, e nessuno
    resta senza regola."""
    flusso = (RADICE / ".github" / "workflows" / "screenshot.yml").read_text(encoding="utf-8")
    schema = re.compile(re.search(r"FILE_WIDGET: '(.*)'", flusso).group(1))
    file = sorted(f"ios/scripts/{p.name}" for p in (RADICE / "ios" / "scripts").iterdir() if p.is_file())
    assert file
    for f in file:
        esito = foto.schermate([f])
        assert esito["senza"] == [], f
        assert esito["widget"] is bool(schema.search(f)), f


def test_pr_da_un_fork_non_lancia(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo", "state": "OPEN", "isCrossRepository": True},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 1
    assert not f.lanciati("gh workflow")
    assert "PR da un fork: le foto si lanciano dal ramo di questo repository" in capsys.readouterr().err


def test_pr_chiusa_senza_unione_non_lancia(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "headRefName": "ramo", "state": "CLOSED", "isCrossRepository": False},
               "gh workflow run screenshot.yml": ""})
    assert foto.main(f, pr=7, lancia=True) == 1
    assert not f.lanciati("gh workflow")
    assert "chiusa senza unione" in capsys.readouterr().err


def test_spiega_dice_per_ogni_file_come_ha_scelto(capsys):
    """#505: con --spiega ogni file dice se ha deciso una regola a mano, il codice (con la strada) o la regola larga."""
    import squadra
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Lega/NomeConPillola.swift"},
                                          {"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}],
                                "state": "MERGED"}})
    squadra.main(["foto", "7", "--spiega"], esegui=f)
    out = capsys.readouterr().out
    assert "ios/Sources/Presentation/Lega/NomeConPillola.swift: grafo: dal codice: " in out
    assert "ios/Sources/Presentation/Giornate/GiornateView.swift: regola:" in out


def test_senza_spiega_niente_perche(capsys):
    f = Finto({"gh pr view 7": {"files": [{"path": "ios/Sources/Presentation/Giornate/GiornateView.swift"}], "state": "MERGED"}})
    foto.main(f, pr=7)
    assert "regola a mano" not in capsys.readouterr().out
