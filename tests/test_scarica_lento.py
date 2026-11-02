"""Server lento (goccia a goccia): il tempo massimo del download e' un tetto TOTALE vero e i posti di download si liberano."""
import http.client
import socket
import threading
import time

import pytest

from fanta import limiti, scarica_immagine as si


def _server_lento(intervallo, intestazioni_lente=False):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    fermo = threading.Event()

    def servi(c):
        try:
            c.recv(4096)
            testa = b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nConnection: close\r\n\r\n"
            if intestazioni_lente:
                for b in testa[:20]:
                    c.sendall(bytes([b]))
                    time.sleep(intervallo)
            c.sendall(testa)
            c.sendall(b"\x89")
            while not fermo.is_set():
                time.sleep(intervallo)
                c.sendall(b"0")
        except OSError:
            pass
        finally:
            c.close()

    def accetta():
        while not fermo.is_set():
            try:
                c, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=servi, args=(c,), daemon=True).start()

    threading.Thread(target=accetta, daemon=True).start()
    return srv, fermo


class _ConnLocale(http.client.HTTPConnection):
    porta = 0

    def __init__(self, host, ip, porta, timeout):
        super().__init__("127.0.0.1", _ConnLocale.porta, timeout=timeout)


@pytest.mark.parametrize("testa_lenta", [False, True])
def test_server_a_goccia_tagliato_entro_il_tempo_totale_e_posti_liberi(monkeypatch, testa_lenta):
    srv, fermo = _server_lento(1.5, testa_lenta)
    _ConnLocale.porta = srv.getsockname()[1]
    monkeypatch.setattr(si, "_Connessione", _ConnLocale)
    monkeypatch.setattr(si, "TEMPO_TOTALE", 2.0)
    monkeypatch.setattr(limiti, "_scarichi_insieme", threading.BoundedSemaphore(3))
    esiti, t0 = [], time.monotonic()

    def lavora():
        try:
            with limiti.download_in_corso():
                si.scarica("https://img.example.com/s.png", risolvi=lambda h, p: ["93.184.216.34"])
        except ValueError as e:
            esiti.append(str(e))

    try:
        fili = [threading.Thread(target=lavora) for _ in range(3)]
        for f in fili:
            f.start()
        for f in fili:
            f.join(15)
        assert not any(f.is_alive() for f in fili)
        assert time.monotonic() - t0 < 6                 # con la vecchia lettura a pezzi pieni durava ben di piu'
        assert len(esiti) == 3
        assert all(limiti._scarichi_insieme.acquire(blocking=False) for _ in range(3))      # i tre posti sono tornati liberi
    finally:
        fermo.set()
        srv.close()
