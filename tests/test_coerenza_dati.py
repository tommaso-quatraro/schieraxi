"""Coerenza web-iPhone come dati: `docs/COERENZA-WEB-IPHONE.md` è generato da `docs/coerenza/` (script/coerenza.py)."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("coerenza", RADICE / "script" / "coerenza.py")
coerenza = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(coerenza)


@pytest.fixture
def copia(tmp_path):
    """Copia dei soli documenti: si può rompere senza toccare il repository vero."""
    (tmp_path / "docs").mkdir()
    shutil.copytree(RADICE / "docs" / "coerenza", tmp_path / "docs" / "coerenza")
    shutil.copy(RADICE / "docs" / "COERENZA-WEB-IPHONE.md", tmp_path / "docs" / "COERENZA-WEB-IPHONE.md")
    return tmp_path


def _lancia(radice, *argomenti):
    return coerenza.main([*argomenti, "--radice", str(radice)])


def _file_schermata(radice, nome="oggi"):
    return radice / "docs" / "coerenza" / "schermate" / f"{nome}.json"


def _modifica_json(percorso, funzione):
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    funzione(dati)
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_il_documento_nel_repository_e_quello_generato():
    assert coerenza.main(["--controlla"]) == 0


def test_riga_aggiunta_a_mano_al_documento(copia, capsys):
    md = copia / "docs" / "COERENZA-WEB-IPHONE.md"
    md.write_text(md.read_text(encoding="utf-8") + "\n| 99 | Riga a mano | a | b | c | d |\n", encoding="utf-8")
    assert _lancia(copia, "--controlla") == 1
    assert "--scrivi" in capsys.readouterr().out


def test_scrivi_poi_controlla(copia):
    md = copia / "docs" / "COERENZA-WEB-IPHONE.md"
    md.write_text("vecchio\n", encoding="utf-8")
    assert _lancia(copia, "--controlla") == 1
    assert _lancia(copia, "--scrivi") == 0
    assert _lancia(copia, "--controlla") == 0


def test_documento_con_a_capo_di_windows_e_uguale(copia):
    md = copia / "docs" / "COERENZA-WEB-IPHONE.md"
    md.write_bytes(md.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert _lancia(copia, "--controlla") == 0


def test_id_doppio(copia, capsys):
    def duplica(d):
        d["righe"].append(dict(d["righe"][0], web="altro testo"))

    _modifica_json(_file_schermata(copia, "oggi"), duplica)
    assert _lancia(copia, "--controlla") == 1
    assert "doppio" in capsys.readouterr().out


def test_id_doppio_fra_due_schermate(copia):
    primo = json.loads(_file_schermata(copia, "oggi").read_text(encoding="utf-8"))["righe"][0]["id"]
    _modifica_json(_file_schermata(copia, "diario"), lambda d: d["righe"].append(dict(d["righe"][0], id=primo)))
    assert _lancia(copia, "--controlla") == 1


def test_riga_ripetuta(copia, capsys):
    _modifica_json(_file_schermata(copia, "oggi"), lambda d: d["righe"].append(dict(d["righe"][0], id=900)))
    assert _lancia(copia, "--controlla") == 1
    assert "ripetut" in capsys.readouterr().out


def test_riga_del_vocabolario_ripetuta(copia):
    percorso = copia / "docs" / "coerenza" / "vocabolario.json"
    _modifica_json(percorso, lambda d: d["righe"].append(dict(d["righe"][0])))
    assert _lancia(copia, "--controlla") == 1


def test_campo_mancante(copia, capsys):
    _modifica_json(_file_schermata(copia, "oggi"), lambda d: d["righe"][0].pop("iphone"))
    assert _lancia(copia, "--controlla") == 1
    assert "iphone" in capsys.readouterr().out


def test_campo_mancante_nel_vocabolario(copia):
    percorso = copia / "docs" / "coerenza" / "vocabolario.json"
    _modifica_json(percorso, lambda d: d["righe"][0].pop("mai"))
    assert _lancia(copia, "--controlla") == 1


def test_stato_sconosciuto(copia, capsys):
    _modifica_json(_file_schermata(copia, "oggi"), lambda d: d["righe"][0].update(stato="quasi"))
    assert _lancia(copia, "--controlla") == 1
    assert "quasi" in capsys.readouterr().out


def test_nuova_riga_nei_dati_va_nel_documento(copia):
    _modifica_json(
        _file_schermata(copia, "oggi"),
        lambda d: d["righe"].append(
            {"id": 901, "schermata": "Prova", "web": "w", "iphone": "i", "forma": "f", "chi": "c", "stato": "da-fare"}
        ),
    )
    assert _lancia(copia, "--controlla") == 1  # il documento non è ancora rigenerato
    assert _lancia(copia, "--scrivi") == 0
    assert "| 901 | Prova | w | i | f | c |" in (copia / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    assert _lancia(copia, "--controlla") == 0


def test_il_documento_dice_che_e_generato():
    testo = (RADICE / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    assert "File generato: si cambiano i dati in docs/coerenza/, poi `python script/coerenza.py --scrivi`" in testo
