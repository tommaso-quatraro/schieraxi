"""Disco pieno e versione dei dati (prove avversarie del 1/11/2026, giro di stabilità del server).

- Con il disco pieno `scrivi_sicuro` lasciava nella cartella il file temporaneo a metà (che occupava altro spazio) e il server
  rispondeva «Errore interno del server», senza dire che cosa succede.
- La «versione» dei dati (chiave delle copie in memoria dei calcoli) era solo l'ora più recente fra gli aggiornamenti: alla fine
  dell'ora legale (le 2:00-3:00 si ripetono) un aggiornamento fatto «prima» sull'orologio non la cambiava, e l'app continuava a
  usare i consigli calcolati con i dati vecchi."""
import errno
import sqlite3

import pytest
from fastapi.testclient import TestClient

from fanta import consigli, percorsi, server
import codice_web


def test_scrittura_fallita_non_lascia_file_temporanei(tmp_path, monkeypatch):
    f = tmp_path / "scelte.json"
    f.write_text("vecchio", encoding="utf-8")
    vera = type(f).write_text

    def disco_pieno(self, *a, **k):
        vera(self, "met", encoding="utf-8")                # una parte arriva su disco, poi lo spazio finisce
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(type(f), "write_text", disco_pieno)
    with pytest.raises(OSError):
        percorsi.scrivi_sicuro(f, "nuovo")
    monkeypatch.undo()
    assert f.read_text(encoding="utf-8") == "vecchio"
    assert [p.name for p in tmp_path.iterdir()] == ["scelte.json"]


@pytest.mark.parametrize("errore", [OSError(errno.ENOSPC, "No space left on device"),
                                    sqlite3.OperationalError("database or disk is full")])
def test_disco_pieno_messaggio_chiaro(tmp_path, monkeypatch, errore):
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")

    def salva(*a, **k):
        raise errore
    monkeypatch.setattr(server.regole, "salva", salva)
    c = TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)
    r = c.put("/api/regole", json=c.get("/api/regole").json())
    assert r.status_code == 507, r.text
    assert r.json()["detail"] == server.DISCO_PIENO
    assert "spazio" in server.DISCO_PIENO


def test_messaggio_disco_pieno_tradotto_nell_app():
    testi = codice_web.leggi("testi.js")
    assert f'"err.disco_pieno": "{server.DISCO_PIENO}"' in testi


def _db(righe):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aggiornamenti (cosa TEXT PRIMARY KEY, quando TEXT, dettaglio TEXT)")
    db.executemany("INSERT OR REPLACE INTO aggiornamenti VALUES (?, ?, '')", righe)
    return db


def test_versione_cambia_anche_se_l_ora_torna_indietro():
    """25/10: alle 3:00 si torna alle 2:00. L'aggiornamento delle 2:10 (ora solare) viene dopo quello delle 2:50 (ora legale)."""
    db = _db([("aggiornamento", "2026-10-25T02:50:00"), ("probabili fonte 2", "2026-10-25T02:50:30")])
    prima = consigli._versione(db)
    db.execute("INSERT OR REPLACE INTO aggiornamenti VALUES ('aggiornamento', '2026-10-25T02:10:00', '')")
    assert consigli._versione(db) != prima


def test_versione_stabile_e_vuota_senza_aggiornamenti():
    assert consigli._versione(_db([])) is None
    righe = [("aggiornamento", "2026-10-30T10:00:00"), ("dati-extra", "2026-10-30T09:00:00")]
    assert consigli._versione(_db(righe)) == consigli._versione(_db(list(reversed(righe))))
