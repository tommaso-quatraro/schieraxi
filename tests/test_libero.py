"""Momento libero per installare una versione nuova: mai durante una partita di Serie A né nell'ora prima della scadenza della
formazione di una lega (un riavvio interrompe la diretta e i giri delle probabili). Orari simulati, nessuna rete."""
import json
import sqlite3
from datetime import datetime

import pytest

from fanta import consigli, libero, regole
from fanta.regole import Regole

ST = "2026-27"
H = lambda giorno, ora, minuto=0: datetime(2026, 11, giorno, ora, minuto)  # noqa: E731


def _db(giocate=()):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    righe = [(10, "2026-11-01 20:45", "juventus", "napoli"), (11, "2026-11-07 15:00", "inter", "lecce"),
             (11, "2026-11-07 20:45", "milan", "genoa"), (11, "2026-11-08 15:00", "roma", "como")]
    db.executemany("INSERT INTO partite VALUES (?, ?, ?, ?, ?, ?)", [(ST, g, d, c, t, int(c in giocate)) for g, d, c, t in righe])
    return db


@pytest.fixture(autouse=True)
def _stagione(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)


def _lega(minuti=10):
    return regole.imposta(Regole(), "scadenza_minuti", str(minuti))


@pytest.mark.parametrize("ora,occupato", [
    (H(1, 20, 34), False), (H(1, 20, 35), True), (H(1, 22, 0), True), (H(1, 22, 55), True), (H(1, 22, 56), False)])
def test_partita_in_corso(ora, occupato):
    assert (libero.motivo(_db(), [], ora) is not None) is occupato


def test_partita_gia_giocata_nel_calendario_non_blocca():
    assert libero.motivo(_db(giocate=("juventus",)), [], H(1, 22, 0)) is None


def test_diretta_ferma_oltre_la_finestra_blocca_fino_al_tetto(tmp_path):
    f = tmp_path / "live.json"
    f.write_text(json.dumps({"versione": 1, "partite": {"juventus|napoli": {"casa": "juventus", "trasferta": "napoli",
                                                                             "stato": "secondo_tempo", "eventi": []}}}), encoding="utf-8")
    assert "juventus" in libero.motivo(_db(), [], H(1, 23, 10), file_live=f)
    assert libero.motivo(_db(), [], H(2, 0, 46), file_live=f) is None            # oltre 4 ore dal calcio d'inizio
    f.write_text(json.dumps({"partite": {"juventus|napoli": {"casa": "juventus", "trasferta": "napoli", "stato": "finita"}}}),
                 encoding="utf-8")
    assert libero.motivo(_db(), [], H(1, 23, 10), file_live=f) is None


def test_file_della_diretta_rotto_o_mancante(tmp_path):
    f = tmp_path / "live.json"
    assert libero.motivo(_db(), [], H(1, 23, 10), file_live=f) is None
    f.write_text("{rotto", encoding="utf-8")
    assert libero.motivo(_db(), [], H(1, 23, 10), file_live=f) is None


@pytest.mark.parametrize("ora,occupato", [
    (H(7, 13, 29), False), (H(7, 13, 30), True), (H(7, 14, 30), True), (H(7, 14, 31), False)])
def test_ora_prima_della_scadenza(ora, occupato, monkeypatch):
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda db, st, r: 11)
    # giornata 11: prima partita alle 15:00, scadenza 30 minuti prima = 14:30; si blocca da 13:30 (dalle 14:50 c'è la partita)
    m = libero.motivo(_db(), [_lega(30)], ora)
    assert (m is not None) is occupato and (not occupato or "14:30" in m)


def test_due_leghe_con_scadenze_diverse(monkeypatch):
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda db, st, r: 11)
    assert libero.motivo(_db(), [_lega(10)], H(7, 13, 40)) is None
    assert "14:00" in libero.motivo(_db(), [_lega(10), _lega(60)], H(7, 13, 40))   # la seconda chiude alle 14


def test_una_lega_con_dati_strani_non_ferma_le_altre(monkeypatch):
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda db, st, r: 11)
    rotta = Regole()
    rotta.scadenza_minuti = "boh"                                                    # noqa - dati sbagliati di proposito
    assert libero.motivo(_db(), [rotta, _lega(10)], H(7, 14, 0)) is not None


def test_comando_codici_di_uscita(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(libero, "leghe_attive", lambda: [])
    monkeypatch.setattr(libero, "_apri_db", lambda: _db())
    monkeypatch.setattr(libero, "FILE_LIVE", tmp_path / "manca.json")
    assert libero.main(H(1, 22, 0)) == libero.OCCUPATO and "juventus" in capsys.readouterr().out
    assert libero.main(H(3, 10, 0)) == 0


def test_comando_senza_archivio_e_libero(monkeypatch):
    def rotto():
        raise sqlite3.OperationalError("niente archivio")
    monkeypatch.setattr(libero, "_apri_db", rotto)
    assert libero.main(H(1, 22, 0)) == 0                                             # un controllo guasto non blocca gli aggiornamenti


def test_il_comando_esiste():
    from fanta import __main__ as cli
    with pytest.raises(SystemExit):
        cli.main(["momento-libero", "--help"])
