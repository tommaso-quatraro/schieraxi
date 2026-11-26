"""I test non aprono i file della `dati/` del repository (#934): l'ascoltatore di conftest blocca le aperture, e l'archivio
predefinito (`archivio.FILE`) si legge a ogni chiamata, così le prove lo spostano in una cartella temporanea."""
import json
import os
import shutil
import sqlite3

from pathlib import Path

import pytest

from fanta import archivio, libero, registro_copia


@pytest.fixture
def conftest(request):
    """Il conftest di questa cartella, come l'ha caricato pytest (`import conftest` può trovare quello di un'altra cartella)."""
    mio = Path(__file__).with_name("conftest.py").resolve()
    for plugin in request.config.pluginmanager.get_plugins():
        if Path(getattr(plugin, "__file__", None) or ".").resolve() == mio:
            return plugin
    raise AssertionError("conftest di tests/ non trovato")


def test_aprire_un_file_di_dati_e_bloccato(conftest):
    with pytest.raises(PermissionError):
        open(conftest.DATI_DEL_REPOSITORY / "qualcosa.json", "rb")
    assert conftest._aperture_in_dati                # e il test sarebbe segnato come fallito alla chiusura
    conftest._aperture_in_dati.clear()


def test_l_ascoltatore_ignora_le_aperture_relative_a_una_cartella(conftest):
    """Su Linux `shutil.rmtree` apre le sottocartelle con `os.open(nome, flag, dir_fd=...)`: l'evento arriva con il nome
    relativo e senza modo (`args[1] is None`), e non va completato con la cartella corrente (la radice del repository)."""
    assert conftest._percorso_aperto("open", ("dati", None, os.O_RDONLY)) is None
    assert conftest._percorso_aperto("open", (str(conftest.DATI_DEL_REPOSITORY / "x"), None, os.O_RDONLY)) is not None


def test_rmtree_di_una_cartella_temporanea_con_dati(conftest, tmp_path, monkeypatch):
    (tmp_path / "copia" / "dati" / "sotto").mkdir(parents=True)
    (tmp_path / "copia" / "dati" / "sotto" / "f.txt").write_text("x", encoding="utf-8")
    monkeypatch.chdir(conftest.DATI_DEL_REPOSITORY.parent)       # come nel CI: la cartella corrente è la radice del repository
    shutil.rmtree(tmp_path / "copia")
    assert not (tmp_path / "copia").exists()


def test_apri_segue_archivio_file(tmp_path, monkeypatch):
    file = tmp_path / "altro" / "fanta.sqlite"
    monkeypatch.setattr(archivio, "FILE", file)
    archivio.apri().close()
    assert file.is_file()


def test_libero_legge_l_archivio_di_archivio_file(tmp_path, monkeypatch):
    file = tmp_path / "ro" / "fanta.sqlite"
    monkeypatch.setattr(archivio, "FILE", file)
    with pytest.raises(sqlite3.OperationalError):                 # in sola lettura: non lo crea
        libero._apri_db()
    archivio.apri(file).close()
    db = libero._apri_db()
    db.execute("SELECT COUNT(*) FROM calciatori").fetchone()
    db.close()


def test_registro_copia_importa_in_archivio_file(tmp_path, monkeypatch):
    sorgente = tmp_path / "sorgente.sqlite"
    archivio.apri(sorgente).close()
    copia = tmp_path / "registro.json"
    registro_copia.esporta(sorgente, copia)
    assert json.loads(copia.read_text(encoding="utf-8"))["tabelle"] is not None
    file = tmp_path / "destinazione" / "fanta.sqlite"
    monkeypatch.setattr(archivio, "FILE", file)
    registro_copia.importa(copia)
    assert file.is_file()
    assert registro_copia.main(["importa", str(copia)]) == 0


def test_sentinella_e_notifiche_seguono_le_costanti(tmp_path, monkeypatch):
    """I percorsi predefiniti di sentinella e notifiche si leggono a ogni chiamata, non nella firma: le prove li spostano."""
    import inspect
    from datetime import datetime, timezone

    from fanta import notifiche, sentinella
    stato = tmp_path / "sentinella.json"
    stato.write_text(json.dumps({"giri": [{"quando": "2026-11-15T20:00:00+00:00", "rotte": [], "inviato": False}], "x": 1}),
                     encoding="utf-8")
    monkeypatch.setattr(sentinella, "FILE_STATO", stato)
    assert sentinella.leggi_stato()["x"] == 1
    t = timezone.utc
    assert len(sentinella.giri_sentinella(datetime(2026, 11, 15, tzinfo=t), datetime(2026, 11, 16, tzinfo=t))) == 1
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"partite": [{"casa": "A", "trasferta": "B"}]}), encoding="utf-8")
    monkeypatch.setattr(sentinella, "FILE_LIVE", live)
    assert sentinella.leggi_live() is not None
    for funzione, nome in ((sentinella.giro, "file_stato"), (notifiche.cambi, "file_stato"),
                           (notifiche.promemoria, "file_stato"), (notifiche.avviso_scadenza, "file_stato")):
        assert inspect.signature(funzione).parameters[nome].default is None, funzione.__name__
