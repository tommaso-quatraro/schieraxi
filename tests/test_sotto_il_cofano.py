"""«Sotto il cofano»: testi controllati, numeri attuali da cose già calcolate, ETag, 503, niente campi privati."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fanta import server, sotto_il_cofano as sc, stato_dati


@pytest.fixture
def cliente(monkeypatch, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server, "_db", lambda: sqlite3.connect(":memory:"))
    monkeypatch.setattr(stato_dati, "calibrazione", lambda db, st: {"giornate": 3, "gruppi": [{"gruppo": "x", "n": 40, "osservato": 0.9, "previsto": 0.85}]})
    monkeypatch.setattr(stato_dati, "ombra", lambda db: {"partite_extra": {"righe": 5, "ultima": "2026-10-01"}})
    return TestClient(server.app)


def test_il_file_vero_e_a_posto():
    assert sc.controlla(json.loads(sc.FILE.read_text(encoding="utf-8"))) == []


def test_traduzione_inglese_completa_e_della_stessa_forma():
    it = json.loads(sc.FILE.read_text(encoding="utf-8"))
    en = json.loads(sc.file_inglese(sc.FILE).read_text(encoding="utf-8"))
    assert set(en["sezioni"]) == {s["id"] for s in it["sezioni"]}              # ogni sezione ha la sua traduzione
    for s in it["sezioni"]:
        e = en["sezioni"][s["id"]]
        assert set(e) <= {"titolo", "paragrafi", "formula", "esempio", "rimandi"}, s["id"]
        assert len(e["paragrafi"]) == len(s["paragrafi"]), s["id"]
        assert len(e.get("rimandi", [])) == len(s.get("rimandi", [])), s["id"]
        assert ("formula" in e) == ("formula" in s) and ("esempio" in e) == ("esempio" in s), s["id"]
        if "esempio" in s:
            assert set(e["esempio"]) == {"titolo", "testo"}
    assert len(en["glossario"]) == len(it["glossario"]) and len(en["introduzione"]) == len(it["introduzione"])
    assert set(en["livelli"]) == set(it["livelli"])
    voci_it, voci_en = it["misure"]["riferimento"]["voci"], en["misure"]["riferimento"]["voci"]
    assert set(voci_en) == set(voci_it)
    for k, v in voci_en.items():
        assert v["etichetta"] and set(v) <= {"etichetta", "unita", "valore"}


def test_inglese_cambia_solo_le_parole():
    it, en = sc.contenuto(lingua="it"), sc.contenuto(lingua="en")
    assert en["titolo"] == "Under the hood" and it["titolo"] == "Sotto il cofano"
    assert [s["id"] for s in en["sezioni"]] == [s["id"] for s in it["sezioni"]]
    assert [s.get("livello") for s in en["sezioni"]] == [s.get("livello") for s in it["sezioni"]]
    assert [s.get("numeri") for s in en["sezioni"]] == [s.get("numeri") for s in it["sezioni"]]
    assert [[r["schermata"] for r in s.get("rimandi", [])] for s in en["sezioni"]] == [[r["schermata"] for r in s.get("rimandi", [])] for s in it["sezioni"]]
    vi, ve = it["misure"]["riferimento"]["voci"], en["misure"]["riferimento"]["voci"]
    assert {k: v["valore"] for k, v in vi.items() if isinstance(v["valore"], (int, float))} == \
        {k: v["valore"] for k, v in ve.items() if isinstance(v["valore"], (int, float))}
    assert "fonte_codice" not in json.dumps(en)
    assert sc.contenuto(lingua="it")["titolo"] == "Sotto il cofano"            # la cache non mescola le lingue


def test_senza_traduzione_resta_italiano(tmp_path):
    (tmp_path / "x.json").write_text(sc.FILE.read_text(encoding="utf-8"), encoding="utf-8")
    assert sc.contenuto(tmp_path / "x.json", "en")["titolo"] == "Sotto il cofano"


def test_rotta_in_inglese_con_parametro_o_intestazione(cliente):
    assert cliente.get("/api/sotto-il-cofano").json()["titolo"] == "Sotto il cofano"
    assert cliente.get("/api/sotto-il-cofano", headers={"Accept-Language": "it-IT,it;q=0.9"}).json()["titolo"] == "Sotto il cofano"
    r = cliente.get("/api/sotto-il-cofano", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert r.json()["titolo"] == "Under the hood" and "Accept-Language" in r.headers["vary"]
    assert cliente.get("/api/sotto-il-cofano?lingua=en").json()["titolo"] == "Under the hood"
    assert cliente.get("/api/sotto-il-cofano?lingua=it", headers={"Accept-Language": "en"}).json()["titolo"] == "Sotto il cofano"
    e1 = cliente.get("/api/sotto-il-cofano").headers["etag"]
    assert cliente.get("/api/sotto-il-cofano?lingua=en").headers["etag"] != e1       # ETag diversi per lingue diverse


def test_controlli_trovano_i_guai():
    d = json.loads(sc.FILE.read_text(encoding="utf-8"))
    d["sezioni"][1]["id"] = d["sezioni"][0]["id"]
    d["sezioni"][0]["livello"] = "boh"
    d["sezioni"][0]["numeri"] = ["non.esiste"]
    d["sezioni"][0]["rimandi"] = [{"schermata": "nonce", "etichetta": "x"}]
    guai = " ".join(sc.controlla(d))
    assert "doppio" in guai and "livello" in guai and "non.esiste" in guai and "nonce" in guai


def test_risposta_senza_fonte_codice_e_con_numeri_attuali(cliente, monkeypatch):
    monkeypatch.setattr(server.affidabilita, "carica",
                        lambda p=None: {"calcolato": "2026-10-28T00:38:07", "ultima": "2026-27/8",
                                        "righe": [{"nome": "segreto"}], "sintesi": {"giornate": 8, "errore_modello": 1.6, "punti_modello": 70.1}})
    r = cliente.get("/api/sotto-il-cofano")
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-cache"
    d = r.json()
    assert "fonte_codice" not in json.dumps(d) and "segreto" not in json.dumps(d) and "crediti" not in json.dumps(d["misure"]["attuali"]["ombra"])
    a = d["misure"]["attuali"]
    assert a["voci"]["app.errore_modello"] == {"valore": 1.6, "aggiornato": "2026-10-28T00:38:07"}
    assert "app.errore_fantamedia" not in a["voci"] and a["affidabilita"]["giornate"] == 8 and a["calibrazione"]["giornate"] == 3
    assert d["misure"]["riferimento"]["voci"] and d["sezioni"] and d["glossario"]


def test_senza_prova_automatica_i_numeri_attuali_mancano_ma_risponde(cliente, monkeypatch):
    monkeypatch.setattr(server.affidabilita, "carica", lambda p=None: {})
    a = cliente.get("/api/sotto-il-cofano").json()["misure"]["attuali"]
    assert a["voci"] == {} and a["affidabilita"] is None


def test_etag_e_304(cliente):
    r = cliente.get("/api/sotto-il-cofano")
    etag = r.headers["etag"]
    r2 = cliente.get("/api/sotto-il-cofano", headers={"If-None-Match": etag})
    assert r2.status_code == 304 and r2.headers["etag"] == etag
    assert cliente.get("/api/sotto-il-cofano", headers={"If-None-Match": '"altro"'}).status_code == 200


def test_file_mancante_o_rotto_e_503(cliente, monkeypatch, tmp_path):
    for contenuto in (None, "{ non json", json.dumps({"formato": 1, "sezioni": []})):
        p = tmp_path / "x.json"
        if contenuto is not None:
            p.write_text(contenuto, encoding="utf-8")
        monkeypatch.setattr(sc, "FILE", p)
        r = cliente.get("/api/sotto-il-cofano")
        assert r.status_code == 503 and "non sono disponibili" in r.json()["detail"]


def test_il_file_si_rilegge_se_cambia(tmp_path):
    d = json.loads(sc.FILE.read_text(encoding="utf-8"))
    p = tmp_path / "c.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    assert sc.contenuto(p)["titolo"] == "Sotto il cofano"
    d["titolo"] = "Altro"
    p.write_text(json.dumps(d) + " ", encoding="utf-8")
    assert sc.contenuto(p)["titolo"] == "Altro"


def test_il_file_si_rilegge_anche_con_la_stessa_data_di_modifica(tmp_path):
    """Filesystem con orologio grossolano: due scritture di fila hanno la stessa data, cambia solo la dimensione."""
    import os
    d = json.loads(sc.FILE.read_text(encoding="utf-8"))
    p = tmp_path / "c.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    os.utime(p, (1_700_000_000, 1_700_000_000))
    assert sc.contenuto(p)["titolo"] == "Sotto il cofano"
    d["titolo"] = "Altro"
    p.write_text(json.dumps(d) + " ", encoding="utf-8")
    os.utime(p, (1_700_000_000, 1_700_000_000))
    assert sc.contenuto(p)["titolo"] == "Altro"
