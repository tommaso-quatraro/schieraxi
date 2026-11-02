"""Attacchi con corpi delle richieste enormi (trovati in revisione): senza Content-Length («chunked») il tetto non valeva fuori da
/api/account, e un multipart enorme finiva tutto su disco. Più: i file rifiutati non consumavano le importazioni del giorno."""
import pytest

from fanta import limiti, server

from test_account_http import cliente
from test_limiti import ambiente, nuovo_utente  # noqa: F401 - fixture


def a_pezzi(totale: int, pezzo: int = 256 * 1024):
    """Un corpo mandato a pezzi, senza Content-Length (httpx usa Transfer-Encoding: chunked)."""
    mandati = 0
    while mandati < totale:
        n = min(pezzo, totale - mandati)
        mandati += n
        yield b"a" * n


@pytest.fixture
def piccolo(monkeypatch):
    monkeypatch.setattr(server, "LIMITE_RICHIESTA", 64 * 1024)
    monkeypatch.setattr(server, "LIMITE_ACCOUNT", 1024)


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


def test_chunked_oltre_il_tetto_fuori_dagli_account(dati_isolati, piccolo, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    c = cliente()
    for percorso in ("/api/regole/riconosci", "/api/scambi/da-testo", "/api/backup/ripristina"):
        r = c.post(percorso, content=a_pezzi(200 * 1024), headers={"Content-Type": "application/json"})
        assert r.status_code == 413, (percorso, r.status_code, r.text[:200])


def test_multipart_chunked_oltre_il_tetto(dati_isolati, piccolo, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    confine = "XyZ"
    def corpo():
        yield f"--{confine}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"r.csv\"\r\n\r\n".encode()
        yield from a_pezzi(300 * 1024)
        yield f"\r\n--{confine}--\r\n".encode()
    r = cliente().post("/api/rose/file", content=corpo(), headers={"Content-Type": f"multipart/form-data; boundary={confine}"})
    assert r.status_code == 413


def test_chunked_piccolo_passa_ancora(dati_isolati, piccolo, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    r = cliente().post("/api/regole/riconosci", content=iter([b'{"testo": ', b'"bonus gol 3"}']), headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_i_file_rifiutati_contano_nelle_importazioni(ambiente):
    """Un Excel finto o un CSV che non passa i controlli costa lavoro al server: conta come un'importazione."""
    a, id_a = nuovo_utente("utentea")
    assert a.post("/api/rose/file", files={"file": ("rose.xlsx", b"PK\x03\x04" + b"\x00" * 100, "application/zip")}).status_code == 400
    assert a.post("/api/rose/file", files={"file": ("rose.csv", b"a\n" * 2000, "text/csv")}).status_code == 400
    assert limiti.usati_oggi(id_a, "importazioni") == 2
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO - 2):
        a.post("/api/rose/file", files={"file": ("rose.xlsx", b"PK\x03\x04" + b"\x00" * 100, "application/zip")})
    r = a.post("/api/rose/file", files={"file": ("rose.xlsx", b"PK\x03\x04" + b"\x00" * 100, "application/zip")})
    assert r.status_code == 429
