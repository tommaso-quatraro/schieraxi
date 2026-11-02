"""Import di formazioni e calendario delle giornate passate: solo dati finti e cartelle temporanee."""
import json

import pytest

from fanta import formazioni_lega as fl
from fanta import scelte

ST = "2026-27"
TIT = list(range(1, 12))
PAN = list(range(12, 22))


def _file(**extra):
    d = {"stagione": ST,
         "scelte": {"4": {"modulo": "4-3-3", "titolari": TIT, "panchina": PAN}},
         "altre_squadre": {"4": {"Squadra Finta": {"modulo": "3-5-2", "titolari": TIT, "panchina": PAN, "punti": 70.5}}},
         "calendario": [{"giornata_lega": 1, "giornata_serie_a": 4, "casa": "A", "trasferta": "B", "gol": [2, 1], "punti": [75, 69.5]},
                        {"giornata_lega": 2, "giornata_serie_a": 5, "casa": "B", "trasferta": "A"}]}
    d.update(extra)
    return d


@pytest.fixture
def cart(tmp_path):
    cartella = tmp_path / "dati"
    return dict(file_scelte=cartella / "scelte.json", file_altre=cartella / "altre.json", file_calendario=cartella / "cal.json")


def test_importa_scrive_le_tre_parti(cart):
    esito = fl.importa(_file(), **cart)
    assert esito == {"scelte": 1, "scelte_gia_presenti": [], "altre_squadre": 1, "partite": 2}
    s = scelte.leggi(ST, 4, cart["file_scelte"])
    assert s["titolari"] == TIT and s["panchina"] == PAN and s["modulo"] == "4-3-3" and s["tipo"] == "manuale"
    assert fl.altre_squadre(cart["file_altre"])[f"{ST}/4"]["Squadra Finta"]["punti"] == 70.5
    cal = fl.calendario(cart["file_calendario"])
    assert len(cal) == 2 and cal[0]["gol"] == [2, 1] and "gol" not in cal[1]


def test_rifare_l_importazione_non_duplica_e_non_tocca_le_scelte_tue(cart):
    fl.importa(_file(), **cart)
    scelte.salva(ST, 4, list(range(30, 41)), "4-4-2", cart["file_scelte"])           # nel frattempo l'hai cambiata a mano
    esito = fl.importa(_file(), **cart)
    assert esito["scelte"] == 0 and esito["scelte_gia_presenti"] == [4]
    assert scelte.leggi(ST, 4, cart["file_scelte"])["modulo"] == "4-4-2"
    assert len(fl.calendario(cart["file_calendario"])) == 2 and len(fl.altre_squadre(cart["file_altre"])[f"{ST}/4"]) == 1
    assert fl.importa(_file(), sovrascrivi_scelte=True, **cart)["scelte"] == 1


def test_scelta_senza_panchina_resta_come_prima(cart):
    scelte.salva(ST, 1, TIT, "4-3-3", cart["file_scelte"])
    assert "panchina" not in scelte.leggi(ST, 1, cart["file_scelte"])


@pytest.mark.parametrize("cambia", [
    {"stagione": "boh"},
    {"scelte": {"4": {"modulo": "4-3-3", "titolari": TIT[:10], "panchina": PAN}}},
    {"scelte": {"4": {"modulo": "4-3-3", "titolari": TIT[:10] + [1], "panchina": PAN}}},
    {"scelte": {"4": {"modulo": "4-3-3", "titolari": TIT, "panchina": [1, 2]}}},               # la panchina ripete i titolari
    {"scelte": {"4": {"modulo": "<b>", "titolari": TIT, "panchina": PAN}}},
    {"scelte": {"99": {"modulo": "4-3-3", "titolari": TIT, "panchina": PAN}}},
    {"altre_squadre": {"4": {"": {"modulo": "4-3-3", "titolari": TIT, "panchina": PAN}}}},
    {"altre_squadre": {"4": {"X": {"modulo": "4-3-3", "titolari": TIT, "panchina": PAN, "punti": 9999}}}},
    {"calendario": [{"giornata_lega": 1, "giornata_serie_a": 4, "casa": "A", "trasferta": "B", "gol": [2], "punti": [1, 2]}]},
    {"calendario": [{"giornata_lega": 1}]},
    {"calendario": "no"},
])
def test_file_non_valido_non_scrive_niente(cart, tmp_path, cambia):
    with pytest.raises(ValueError):
        fl.importa(_file(**cambia), **cart)
    assert not (tmp_path / "dati").exists()


def test_importa_file_rifiuta_file_enormi_o_rotti(cart, tmp_path):
    brutto = tmp_path / "x.json"
    brutto.write_text("{non json", encoding="utf-8")
    with pytest.raises(ValueError):
        fl.importa_file(brutto, **cart)
    grande = tmp_path / "g.json"
    grande.write_text(json.dumps({"stagione": ST, "x": "a" * (fl.MAX_BYTE + 1)}), encoding="utf-8")
    with pytest.raises(ValueError):
        fl.importa_file(grande, **cart)
