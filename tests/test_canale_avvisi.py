"""Il canale degli avvisi (ntfy): variabile d'ambiente, file nella cartella dei dati, ripiego sul file dei server gia' installati."""
from pathlib import Path

from fanta import notifiche


def _isola(monkeypatch, tmp_path):
    for n in ("FANTA_CANALE_AVVISI", "FANTA_NTFY_CANALE"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setattr(notifiche, "RADICE", tmp_path / "radice")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "casa"))


def test_nessun_canale(monkeypatch, tmp_path):
    _isola(monkeypatch, tmp_path)
    assert notifiche.canale() is None


def test_variabili_e_file_in_ordine(monkeypatch, tmp_path):
    _isola(monkeypatch, tmp_path)
    vecchio = tmp_path / "casa" / ".config" / "schieraxi"
    vecchio.mkdir(parents=True)
    (vecchio / "canale").write_text("canale-vecchio\n", encoding="utf-8")
    assert notifiche.canale() == "canale-vecchio"                     # ripiego: file dei server gia' installati
    (tmp_path / "radice" / "dati").mkdir(parents=True)
    (tmp_path / "radice" / "dati" / "canale-avvisi.txt").write_text(" canale-dati \n", encoding="utf-8")
    assert notifiche.canale() == "canale-dati"
    monkeypatch.setenv("FANTA_NTFY_CANALE", "da-ntfy")
    assert notifiche.canale() == "da-ntfy"
    monkeypatch.setenv("FANTA_CANALE_AVVISI", " da-avvisi ")
    assert notifiche.canale() == "da-avvisi"
