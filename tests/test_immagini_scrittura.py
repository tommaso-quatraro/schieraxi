"""Stemma e maglia con il disco che si riempie a metà scrittura (#781): prima le immagini vecchie si toglievano prima di scrivere la
nuova, e la nuova si scriveva direttamente al suo posto. Restavano un file troncato (l'app lo mostrava rotto) e un messaggio d'errore
che diceva «quello che avevi salvato prima è al sicuro». Ora la nuova si scrive su un file temporaneo che poi prende il suo posto, e
le altre estensioni si tolgono solo dopo. Immagini inventate in cartelle temporanee."""
import errno
from pathlib import Path

import pytest

from fanta import immagini, server
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
PNG_NUOVO = b"\x89PNG\r\n\x1a\n" + b"2" * 100
JPG = b"\xff\xd8\xff" + b"1" * 100
SQUADRA = "Squadra Inventata"
_VERA = Path.write_bytes


def _disco_pieno(self, dati):
    """La scrittura di un'immagine (stemma, maglia o in attesa) si ferma a metà: una parte arriva su disco, poi lo spazio finisce.
    Le altre scritture vanno come sempre."""
    if not any(x in self.name for x in ("-stemma", "-maglia", "_in-attesa")):
        return _VERA(self, dati)
    _VERA(self, dati[:10])
    raise OSError(errno.ENOSPC, "No space left on device")


@pytest.mark.parametrize("nuova", [JPG, PNG_NUOVO], ids=["altro formato", "stesso formato"])
def test_disco_pieno_mentre_si_salva_lo_stemma_quello_vecchio_resta(tmp_path, monkeypatch, nuova):
    vecchio = immagini.salva(SQUADRA, "stemma", PNG, tmp_path)
    with monkeypatch.context() as m:
        m.setattr(Path, "write_bytes", _disco_pieno)
        with pytest.raises(OSError) as e:
            immagini.salva(SQUADRA, "stemma", nuova, tmp_path)
    assert e.value.errno == errno.ENOSPC
    assert immagini.percorso(SQUADRA, "stemma", tmp_path) == vecchio and vecchio.read_bytes() == PNG
    assert [p.name for p in tmp_path.iterdir()] == [vecchio.name]           # niente file troncati né temporanei


def test_salvataggio_riuscito_toglie_le_altre_estensioni(tmp_path):
    immagini.salva(SQUADRA, "stemma", PNG, tmp_path)
    immagini.salva(SQUADRA, "maglia", PNG, tmp_path)
    nuovo = immagini.salva(SQUADRA, "stemma", JPG, tmp_path)
    assert nuovo.suffix == ".jpg" and nuovo.read_bytes() == JPG
    assert sorted(p.name for p in tmp_path.iterdir()) == ["squadra-inventata-maglia.png", "squadra-inventata-stemma.jpg"]
    assert immagini.salva(SQUADRA, "stemma", JPG, tmp_path) == nuovo and nuovo.read_bytes() == JPG     # stesso formato: resta


def test_l_immagine_troppo_grande_lo_dice_con_il_punto(tmp_path):
    """Revisione della #968: «Immagine troppo grande (massimo 4 MB)» era rimasta senza punto, fuori dal catalogo degli errori."""
    grande = PNG + b"0" * immagini.MAX_BYTE
    for salva in (lambda: immagini.salva(SQUADRA, "stemma", grande, tmp_path), lambda: immagini.salva_in_attesa(grande, tmp_path)):
        with pytest.raises(ValueError, match=r"^Immagine troppo grande \(massimo 4 MB\)\.$"):
            salva()
    assert not list(tmp_path.iterdir())


def test_disco_pieno_mentre_arriva_un_immagine_condivisa_quella_in_attesa_resta(tmp_path, monkeypatch):
    vecchia = immagini.salva_in_attesa(PNG, tmp_path)
    with monkeypatch.context() as m:
        m.setattr(Path, "write_bytes", _disco_pieno)
        with pytest.raises(OSError):
            immagini.salva_in_attesa(JPG, tmp_path)
    assert immagini.in_attesa(tmp_path) == vecchia and vecchia.read_bytes() == PNG
    assert [p.name for p in tmp_path.iterdir()] == [vecchia.name]
    nuova = immagini.salva_in_attesa(JPG, tmp_path)                       # riuscita: la vecchia si toglie
    assert [p.name for p in tmp_path.iterdir()] == [nuova.name] and nuova.read_bytes() == JPG


def test_dalla_rotta_il_messaggio_e_vero_e_lo_stemma_di_prima_resta(ambiente, monkeypatch):  # noqa: F811
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n"}).status_code == 200
    stemma = {"params": {"squadra": "Mia", "tipo": "stemma"}}
    assert a.post("/api/squadre/immagine", files={"file": ("s.png", PNG, "image/png")}, **stemma).status_code == 200
    with monkeypatch.context() as m:
        m.setattr(Path, "write_bytes", _disco_pieno)
        r = a.post("/api/squadre/immagine", files={"file": ("s.jpg", JPG, "image/jpeg")}, **stemma)
    assert r.status_code == 507 and r.json()["detail"] == server.DISCO_PIENO
    r = a.get("/api/squadre/immagine", **stemma)
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
