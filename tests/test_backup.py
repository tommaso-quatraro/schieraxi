"""Backup e ripristino dei dati della lega, su una cartella temporanea."""
import json

import pytest

from fanta import backup, lega, server
from fanta.regole import Regole
from fanta.regole import salva as salva_regole
from fastapi.testclient import TestClient


@pytest.fixture
def radice(tmp_path):
    salva_regole(Regole(), tmp_path / "lega" / "regole.json")
    lega.salva(lega.Rose([lega.Squadra("Mia", []), lega.Squadra("Altra", [])], "Mia"), tmp_path / "lega" / "rose.json")
    (tmp_path / "dati").mkdir()
    (tmp_path / "dati" / "osservati.json").write_text("[5, 7]")
    (tmp_path / "dati" / "scelte.json").write_text('{"2025-26/9": {"titolari": [1], "modulo": "3-4-3"}}')
    (tmp_path / "dati" / "vapid.json").write_text('{"chiave": "segreta"}')
    return tmp_path


def test_il_backup_ha_i_dati_e_non_i_segreti(radice):
    b = backup.crea(radice)
    assert b["formato"] == backup.FORMATO
    assert set(b["file"]) == {"lega/regole.json", "lega/rose.json", "dati/osservati.json", "dati/scelte.json"}
    assert "segreta" not in json.dumps(b)


def test_ripristino_su_una_cartella_vuota_e_ritorno_identico(radice, tmp_path_factory):
    b = backup.crea(radice)
    nuova = tmp_path_factory.mktemp("nuova")
    assert backup.ripristina(b, nuova) == sorted(b["file"])
    assert backup.crea(nuova)["file"] == b["file"]
    assert lega.carica(nuova / "lega" / "rose.json").mia_squadra == "Mia"


def test_ripristino_tiene_la_copia_dello_stato_di_prima(radice):
    b = backup.crea(radice)
    (radice / "dati" / "osservati.json").write_text("[1]")
    backup.ripristina(b, radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]
    prima = json.loads((radice / backup.COPIA_PRIMA).read_text())
    assert prima["file"]["dati/osservati.json"] == [1]


@pytest.mark.parametrize("brutto", [
    [], "ciao", {}, {"formato": "altro", "versione": 1, "file": {"dati/osservati.json": []}},
    {"formato": backup.FORMATO, "versione": 99, "file": {"dati/osservati.json": []}},
    {"formato": backup.FORMATO, "versione": 1, "file": {}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"../fuori.json": []}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/vapid.json": {}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": {"a": 1}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [float("inf")]}},     # «Infinity» o 1e999 nel JSON: era un errore 500
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/regole.json": {"moduli": ["3-4-4"]}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/rose.json": {"squadre": [{"giocatori": []}]}}},
])
def test_un_backup_sbagliato_non_cambia_niente(radice, brutto):
    prima = backup.crea(radice)
    with pytest.raises(ValueError):
        backup.ripristina(brutto, radice)
    dopo = backup.crea(radice)          # una sola chiamata: "creato" cambia al secondo e due chiamate possono cadere in secondi diversi
    assert dopo == {**prima, "creato": dopo["creato"]}
    assert not (radice / backup.COPIA_PRIMA).exists()


def test_un_file_alla_volta_il_resto_resta(radice):
    parziale = {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [9]}}
    backup.ripristina(parziale, radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [9]
    assert json.loads((radice / "dati" / "scelte.json").read_text())["2025-26/9"]


def test_indirizzi_del_server(radice, monkeypatch):
    monkeypatch.setattr(server, "RADICE", radice)
    client = TestClient(server.app, headers={"X-Fanta": "1"})
    r = client.get("/api/backup")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    b = r.json()
    (radice / "dati" / "osservati.json").write_text("[1]")
    assert client.post("/api/backup/ripristina", json=b).json()["ripristinati"]
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]
    assert client.post("/api/backup/ripristina", json={"formato": "x"}).status_code == 400
    assert TestClient(server.app).post("/api/backup/ripristina", json=b).status_code == 403


def test_nome_del_file_e_formato():
    assert backup.nome_file("2026-10-31T10:00:00") == "schieraxi-backup-2026-10-31.json"
    assert backup.FORMATO == "schieraxi-backup"
    assert backup.controlla({"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [1]}})
    with pytest.raises(ValueError):
        backup.controlla({"formato": "altro-backup", "versione": 1, "file": {"dati/osservati.json": [1]}})


def test_copia_serale_una_al_giorno_e_si_tengono_le_ultime(radice, monkeypatch):
    cartella = radice / "dati" / "backup"
    cartella.mkdir()
    for giorno in range(1, 10):
        (cartella / f"schieraxi-backup-2026-10-0{giorno}.json").write_text("{}")
    monkeypatch.setattr(backup, "datetime", type("D", (), {"now": staticmethod(lambda: __import__("datetime").datetime(2026, 10, 29, 3, 30))}))
    f = backup.salva_copia(radice, tieni=7)
    assert f.name == "schieraxi-backup-2026-10-29.json"
    assert len(list(cartella.glob("*.json"))) == 7 and f.exists()
    assert backup.controlla(json.loads(f.read_text()))                      # è un backup ripristinabile
    assert backup.salva_copia(radice, tieni=7) == f and len(list(cartella.glob("*.json"))) == 7      # stesso giorno: si sostituisce


def test_copia_serale_senza_dati_non_scrive(tmp_path):
    assert backup.salva_copia(tmp_path) is None and not (tmp_path / "dati" / "backup").exists()
