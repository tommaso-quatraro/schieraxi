"""THIRD-PARTY-NOTICES.md è generato da script/avvisi_terze_parti.py: ogni dipendenza diretta ha la sua licenza e il file è aggiornato."""
import importlib.util
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("avvisi_terze_parti", RADICE / "script" / "avvisi_terze_parti.py")
avvisi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(avvisi)


def test_ogni_dipendenza_diretta_ha_una_licenza():
    nomi = avvisi.nomi_requisiti((RADICE / "requirements.in").read_text(encoding="utf-8"))
    assert nomi and avvisi.mancanti(nomi) == []


def test_nomi_requisiti_ignora_versioni_e_commenti():
    assert avvisi.nomi_requisiti("Requests>=2.0  # http\n\n-r altro.txt\nPython_Dotenv[cli]==1\n") == ["requests", "python-dotenv"]


def test_pacchetto_senza_licenza_si_vede():
    assert avvisi.mancanti(["requests", "pacchetto-nuovo"]) == ["pacchetto-nuovo"]


def test_il_file_e_aggiornato_e_cita_mpl():
    nomi = avvisi.nomi_requisiti((RADICE / "requirements.in").read_text(encoding="utf-8"))
    atteso = avvisi.genera(nomi)
    assert (RADICE / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8").replace("\r\n", "\n") == atteso
    assert "MPL-2.0" in atteso and "pywebpush" in atteso and "py-vapid" in atteso
    assert avvisi.principale(["--controlla"]) == 0
