"""Copia del registro delle giornate (#343): esporta le due tabelle `registro_*` dell'archivio in un file piccolo e le rimette in un
archivio nuovo, identiche. Dati inventati, archivi in cartelle temporanee."""
import contextlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from fanta import archivio, registro_copia

RADICE = Path(__file__).resolve().parent.parent

COLONNE = {
    "registro_giocatori": ["stagione", "giornata", "calciatore_id", "ruolo", "squadra", "partita_id", "p_voto", "mu", "mu_voto",
                           "e_gol", "e_assist", "minuti", "stato", "percentuale", "dubbio", "fantamedia"],
    "registro_giornate": ["stagione", "giornata", "salvato", "giocatori", "con_probabili", "misurato", "voti", "sq_modello",
                          "sq_fantamedia", "presenze", "brier_somma", "fasce", "fascia_casi", "fascia_dentro", "fuori", "da_avvisare",
                          "avvisati", "persa"],
}
# 0.30000000000000004 = 0.1 + 0.2: il numero deve tornare uguale fino all'ultima cifra
GIOCATORI = [
    ("2026-27", 9, 101, "A", "Squadra Uno", 5001, 0.873, 6.734, 6.12, 0.41, 0.12, 78.5, "titolare", 85.0, 0, 7.25),
    ("2026-27", 9, 102, "P", "Squadra Due", 5002, 0.30000000000000004, 5.0, 6.0, 0.0, 0.0, 90.0, None, None, 0, None),
    ("2026-27", 10, 101, "A", "Squadra Uno", 5011, 0.66, 6.5, 6.05, 0.38, 0.1, 70.0, "ballottaggio", 55.0, 1, 7.31),
]
GIORNATE = [
    ("2026-27", 9, "2026-10-25T14:50:00", 2, 1, "2026-10-27T09:00:00", 2, 3.5, 4.25, 2, 0.31, '{"80": [1, 1]}', 20, 17, '["I1"]',
     None, None, None),
    ("2026-27", 10, "2026-11-01T12:20:00", 1, 0, None, None, None, None, None, None, None, None, None, None, None, None, None),
    # giornata persa: non salvata prima della prima partita (salvato vuoto), resta il motivo
    ("2026-27", 11, None, 0, 0, None, None, None, None, None, None, None, None, None, None, None, None, "servizio fermo"),
]
ORDINE = {"registro_giocatori": "stagione, giornata, calciatore_id", "registro_giornate": "stagione, giornata"}
SENZA_NOSTRI = {"registro_nostri": 0, "registro_i4": 0}          # tabelle dei numeri nostri: ci sono anche vuote


def _inserisci(db, tabella, righe):
    colonne = COLONNE[tabella]
    db.executemany(f"INSERT INTO {tabella} ({', '.join(colonne)}) VALUES ({', '.join('?' * len(colonne))})", righe)


def _riempi(db):
    _inserisci(db, "registro_giocatori", GIOCATORI)
    _inserisci(db, "registro_giornate", GIORNATE)
    # altri dati dell'archivio: si ricostruiscono con `aggiorna` e NON vanno nella copia del registro
    db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, ruolo, voto_red) VALUES ('2026-27', 9, 101, "
               "'Giocatore Finto', 'A', 6.5)")
    db.commit()


def _archivio_con_registro(percorso):
    with contextlib.closing(archivio.apri(percorso)) as db:
        _riempi(db)


def _righe(percorso, tabella):
    with contextlib.closing(sqlite3.connect(percorso)) as db:
        return db.execute(f"SELECT {', '.join(COLONNE[tabella])} FROM {tabella} ORDER BY {ORDINE[tabella]}").fetchall()


def _conta(percorso, tabella):
    with contextlib.closing(sqlite3.connect(percorso)) as db:
        return db.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]


def test_esporta_e_reimporta_il_registro_identico_in_un_archivio_nuovo(tmp_path):
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo" / "fanta.sqlite"
    _archivio_con_registro(vecchio)
    assert registro_copia.esporta(vecchio, copia) == {"registro_giornate": 3, "registro_giocatori": 3, **SENZA_NOSTRI}
    assert registro_copia.importa(copia, nuovo) == {"registro_giornate": (3, 0), "registro_giocatori": (3, 0),
                                                    **{t: (0, 0) for t in SENZA_NOSTRI}}
    assert _righe(nuovo, "registro_giocatori") == GIOCATORI
    assert _righe(nuovo, "registro_giornate") == GIORNATE
    assert _conta(nuovo, "voti") == 0                     # il resto dell'archivio non viaggia con il registro


def test_la_copia_non_porta_con_se_il_resto_dell_archivio(tmp_path):
    vecchio, copia = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json"
    _archivio_con_registro(vecchio)
    registro_copia.esporta(vecchio, copia)
    testo = copia.read_text(encoding="utf-8")
    assert "Giocatore Finto" not in testo                 # niente nomi: le altre tabelle restano fuori (copia piccola)
    assert "Squadra Uno" in testo


def test_esporta_a_server_acceso_prende_i_dati_confermati_e_non_quelli_a_meta(tmp_path):
    """Il servizio tiene l'archivio aperto: i dati confermati possono stare ancora nel file -wal (una copia del solo file .sqlite
    li perderebbe) e un'altra scrittura può essere a metà. La copia prende i primi e non i secondi, e non aspetta lo scrittore."""
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    servizio = archivio.apri(vecchio)
    try:
        _riempi(servizio)
        servizio.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) "
                         "VALUES ('2026-27', 12, '2026-11-22T14:50:00', 0, 1)")         # non confermata
        assert registro_copia.esporta(vecchio, copia) == {"registro_giornate": 3, "registro_giocatori": 3, **SENZA_NOSTRI}
    finally:
        servizio.rollback()
        servizio.close()
    registro_copia.importa(copia, nuovo)
    assert _righe(nuovo, "registro_giornate") == GIORNATE


def test_importa_non_tocca_le_righe_che_ci_sono_gia_e_si_puo_ripetere(tmp_path):
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    _archivio_con_registro(vecchio)
    registro_copia.esporta(vecchio, copia)
    with contextlib.closing(archivio.apri(nuovo)) as db:
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) "
                   "VALUES ('2026-27', 9, 'GIÀ QUI', 5, 0)")
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome) VALUES ('2026-27', 9, 999, 'Altro Finto')")
        db.commit()
    assert registro_copia.importa(copia, nuovo) == {"registro_giornate": (2, 1), "registro_giocatori": (3, 0),
                                                    **{t: (0, 0) for t in SENZA_NOSTRI}}
    giornate = _righe(nuovo, "registro_giornate")
    assert giornate[0][:5] == ("2026-27", 9, "GIÀ QUI", 5, 0) and giornate[1:] == GIORNATE[1:]
    assert _conta(nuovo, "voti") == 1
    assert registro_copia.importa(copia, nuovo) == {"registro_giornate": (0, 3), "registro_giocatori": (0, 3),
                                                    **{t: (0, 0) for t in SENZA_NOSTRI}}
    assert _conta(nuovo, "registro_giocatori") == 3 and _conta(nuovo, "registro_giornate") == 3


def test_importa_una_copia_senza_le_colonne_aggiunte_dopo(tmp_path):
    """Una copia fatta prima di una colonna nuova (qui `persa`) si rimette lo stesso: la colonna resta vuota."""
    file, nuovo = tmp_path / "copia-vecchia.json", tmp_path / "nuovo.sqlite"
    vecchie = [c for c in COLONNE["registro_giornate"] if c != "persa"]
    file.write_text(json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": vecchie, "righe": [list(GIORNATE[0][:-1])]}}}),
                    encoding="utf-8")
    assert registro_copia.importa(file, nuovo) == {"registro_giornate": (1, 0)}
    assert _righe(nuovo, "registro_giornate") == [GIORNATE[0]]          # persa = None


@pytest.mark.parametrize("contenuto", [
    "non è una copia",
    json.dumps({"formato": 2, "tabelle": {}}),
    json.dumps({"formato": 1, "tabelle": {"voti": {"colonne": ["stagione", "giornata", "calciatore_id"], "righe": [["s", 1, 1]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "giornata", "nome_utente"],
                                                                "righe": [["s", 1, "x"]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "giornata) ; DROP TABLE voti; --"],
                                                                "righe": [["s", 1]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "stagione", "giornata"],
                                                                "righe": [["s", "s", 1]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giocatori": {"colonne": ["stagione", "giornata", "p_voto"],
                                                                 "righe": [["s", 1, 0.5]]}}}),         # manca calciatore_id
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "giornata"], "righe": [["s"]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "giornata", "fasce"],
                                                                "righe": [["s", 1, {"80": [1, 1]}]]}}}),
    json.dumps({"formato": 1, "tabelle": {"registro_giornate": {"colonne": ["stagione", "giornata", "con_probabili"],
                                                                "righe": [["s", 1, True]]}}}),
    # una tabella buona e una sbagliata: non entra niente, nemmeno la buona
    json.dumps({"formato": 1, "tabelle": {
        "registro_giornate": {"colonne": ["stagione", "giornata"], "righe": [["s", 1]]},
        "registro_giocatori": {"colonne": ["stagione", "giornata"], "righe": [["s", 1]]}}}),
])
def test_importa_rifiuta_un_file_sbagliato_senza_scrivere_niente(tmp_path, contenuto):
    file, nuovo = tmp_path / "copia.json", tmp_path / "nuovo.sqlite"
    file.write_text(contenuto, encoding="utf-8")
    with contextlib.closing(archivio.apri(nuovo)) as db:
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id) VALUES ('2026-27', 1, 1)")
        db.commit()
    with pytest.raises(ValueError):
        registro_copia.importa(file, nuovo)
    assert _conta(nuovo, "registro_giornate") == 0 and _conta(nuovo, "registro_giocatori") == 0
    assert _conta(nuovo, "voti") == 1


def test_importa_rifiuta_un_file_troppo_grande(tmp_path, monkeypatch):
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    _archivio_con_registro(vecchio)
    registro_copia.esporta(vecchio, copia)
    monkeypatch.setattr(registro_copia, "TETTO", copia.stat().st_size - 1)
    with pytest.raises(ValueError, match="troppo grande"):
        registro_copia.importa(copia, nuovo)
    assert not nuovo.exists() or _conta(nuovo, "registro_giornate") == 0


def test_esporta_un_archivio_di_prima_del_registro_senza_cambiarlo(tmp_path):
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    with contextlib.closing(sqlite3.connect(vecchio)) as db:
        db.execute("CREATE TABLE voti (stagione TEXT, giornata INTEGER, calciatore_id INTEGER)")
        db.commit()
    assert registro_copia.esporta(vecchio, copia) == {}
    with contextlib.closing(sqlite3.connect(vecchio)) as db:
        assert [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")] == ["voti"]
    assert registro_copia.importa(copia, nuovo) == {}


def test_esporta_senza_archivio_non_lo_crea(tmp_path):
    manca, copia = tmp_path / "manca.sqlite", tmp_path / "registro-giornate.json"
    with pytest.raises(ValueError):
        registro_copia.esporta(manca, copia)
    assert not manca.exists() and not copia.exists()


def _comando(*argomenti):
    # -S: senza le librerie installate (niente pandas, requests...): la copia notturna usa il Python di sistema
    return subprocess.run([sys.executable, "-S", "-m", "fanta.registro_copia", *map(str, argomenti)], cwd=RADICE,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def test_comando_da_terminale_con_la_sola_libreria_standard(tmp_path):
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    _archivio_con_registro(vecchio)
    r = _comando("esporta", "--archivio", vecchio, copia)
    assert r.returncode == 0, r.stderr
    assert "3 giornate" in r.stdout
    r = _comando("importa", "--archivio", nuovo, copia)
    assert r.returncode == 0, r.stderr
    assert "3 giornate" in r.stdout
    assert _righe(nuovo, "registro_giocatori") == GIOCATORI and _righe(nuovo, "registro_giornate") == GIORNATE


NOSTRI = [("2026-27", 9, 101, "1", 0.86, 6.9, 6.1, 0.37, 0.12, 0.11, 81.0, 0.1), ("2026-27", 9, 102, "1", 0.3, 5.1, 6.0, 0.0, 0.0, 0.0,
                                                                                    90.0, None)]
I4 = [("2026-27", 9, "1", "2026-10-27T09:05:00", 2, 3.25, 3.5, 20, 1301.5, 1300.0, '[[1, 0.0, 0]]', '[[1, 0.0, 0]]', 1, None, 0),
      ("2026-27", 10, "1", None, 0, None, None, 0, None, None, None, None, 3, "misura non riuscita 3 volte (KeyError)", 1)]


def test_copia_notturna_porta_le_tabelle_nuove(tmp_path):
    """I numeri nostri e le misure I4 (gol attesi nostri) non si ricostruiscono: viaggiano con il registro, identici."""
    vecchio, copia, nuovo = tmp_path / "vecchio.sqlite", tmp_path / "registro-giornate.json", tmp_path / "nuovo.sqlite"
    with contextlib.closing(archivio.apri(vecchio)) as db:
        _riempi(db)
        db.executemany(f"INSERT INTO registro_nostri VALUES ({', '.join('?' * 12)})", NOSTRI)
        db.executemany(f"INSERT INTO registro_i4 VALUES ({', '.join('?' * 15)})", I4)
        db.commit()
    assert registro_copia.esporta(vecchio, copia) == {"registro_giornate": 3, "registro_giocatori": 3, "registro_nostri": 2,
                                                      "registro_i4": 2}
    assert registro_copia.importa(copia, nuovo) == {"registro_giornate": (3, 0), "registro_giocatori": (3, 0),
                                                    "registro_nostri": (2, 0), "registro_i4": (2, 0)}
    with contextlib.closing(sqlite3.connect(nuovo)) as db:
        assert db.execute("SELECT * FROM registro_nostri ORDER BY calciatore_id").fetchall() == NOSTRI
        assert db.execute("SELECT * FROM registro_i4 ORDER BY giornata").fetchall() == I4
    r = _comando("esporta", "--archivio", vecchio, copia)
    assert r.returncode == 0 and "2 righe dei numeri nostri" in r.stdout
    r = _comando("importa", "--archivio", tmp_path / "terzo.sqlite", copia)
    assert r.returncode == 0 and "2 righe dei numeri nostri" in r.stdout


def test_comando_da_terminale_errore_in_una_riga_senza_traccia(tmp_path):
    r = _comando("importa", "--archivio", tmp_path / "nuovo.sqlite", tmp_path / "manca.json")
    assert r.returncode == 1
    assert r.stderr.startswith("Errore: ") and "Traceback" not in r.stderr
