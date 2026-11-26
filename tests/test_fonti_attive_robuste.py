"""Interruttori delle fonti: errore chiaro (400) a fonte spenta, scritture concorrenti, cache del file, registro del cambio."""
import threading

import pytest
from fastapi.testclient import TestClient

from fanta import fonti_attive as fa
from fanta import listone, registro, server


@pytest.fixture
def spente(monkeypatch):
    monkeypatch.setattr(fa, "PREDEFINITO_ACCESO", False)
    for k in fa.FONTI:
        monkeypatch.delenv(f"FANTA_FONTE_{k.upper()}", raising=False)


def cliente() -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_fonte_spenta_e_un_errore_di_valore():
    assert issubclass(fa.FonteSpenta, ValueError)


def test_importare_le_rose_a_fonte_spenta_e_senza_listone_da_400_chiaro(spente, monkeypatch, tmp_path):
    originale = listone.carica
    monkeypatch.setattr(listone, "carica", lambda *a, **k: originale(*a, file_cache=tmp_path / "nessun-listone.json",
                                                                         archivio_db=tmp_path / "nessun-archivio.sqlite"))
    r = cliente().post("/api/rose/testo", json={"testo": "P Sommer Inter"})
    assert r.status_code == 400 and "spenta" in r.json()["detail"]


def test_due_scelte_insieme_non_si_perdono(tmp_path):
    f = tmp_path / "f.json"
    nomi = [k for k in fa.FONTI if k != "foto"]
    threads = [threading.Thread(target=fa.imposta, args=(k, False, f)) for k in nomi]
    for x in threads:
        x.start()
    for x in threads:
        x.join()
    assert all(fa.origine(k, f) == (False, "amministratore") for k in nomi)


def test_il_file_si_rilegge_quando_cambia(tmp_path):
    f = tmp_path / "f.json"
    fa.imposta("footballdata", False, f)
    assert fa.acceso("footballdata", f) is False
    f.write_text('{"footballdata": true, "espn": false}', encoding="utf-8")
    assert fa.acceso("footballdata", f) is True and fa.acceso("espn", f) is False


def test_file_rovinato_lo_dice_e_dall_app_non_si_sovrascrive(tmp_path, caplog):
    """Come per dati/funzioni.json: un file scritto male lascia una riga nel registro con il suo nome, valgono ambiente e
    predefinito, e cambiare una fonte dall'app viene rifiutato (409 con la frase) senza toccare il file."""
    from fanta import interruttori
    fa.FILE.write_text('{"understat": false', encoding="utf-8")
    with caplog.at_level("WARNING"):
        assert fa.origine("understat")[1] != "amministratore"
    righe = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(righe) == 1 and "fonti-finte.json" in righe[0], righe
    with pytest.raises(interruttori.FileIlleggibile):
        fa.imposta("understat", False)
    r = cliente().put("/api/admin/fonti", json={"fonte": "understat", "acceso": False})
    assert r.status_code == 409 and "fonti-finte.json" in r.json()["detail"], r.text
    assert fa.FILE.read_text(encoding="utf-8") == '{"understat": false'


def test_un_elenco_al_posto_dell_oggetto_non_si_legge(tmp_path):
    from fanta import interruttori
    f = tmp_path / "f.json"
    f.write_text('["understat"]', encoding="utf-8")
    with pytest.raises(interruttori.FileIlleggibile):
        fa.imposta("understat", False, f)
    assert f.read_text(encoding="utf-8") == '["understat"]'


def test_uno_e_zero_valgono_acceso_e_spento(tmp_path):
    f = tmp_path / "f.json"
    f.write_text('{"understat": 0, "espn": 1, "footballdata": "0"}', encoding="utf-8")
    assert fa.origine("understat", f) == (False, "amministratore") and fa.origine("espn", f) == (True, "amministratore")
    assert fa.origine("footballdata", f)[1] != "amministratore"           # il testo "0" non vale: solo vero, falso, 1 e 0


def test_il_cambio_resta_nel_registro_di_sicurezza(monkeypatch, tmp_path):
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path))
    assert cliente().put("/api/admin/fonti", json={"fonte": "footballdata", "acceso": False}).status_code == 200
    righe = (tmp_path / registro.FILE_SICUREZZA).read_text(encoding="utf-8")
    assert "fonte-cambiata" in righe and "fonte=footballdata" in righe and "valore=spento" in righe
