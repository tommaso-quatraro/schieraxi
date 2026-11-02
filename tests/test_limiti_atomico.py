"""Prenotazione ATOMICA delle ricerche di scambi: richieste parallele a un passo dal tetto non passano tutte."""
import threading
import time

from fanta import limiti, server

from test_limiti import _niente_ricordi_di_altri_test, ambiente, importa, nuovo_utente, ricerca  # noqa: F401  (fixture)


def _quasi_al_tetto(utente_id, quante):
    ctx = type("C", (), {"utente_id": utente_id})()
    for _ in range(quante):
        limiti.conta(ctx, "scambi")


def _pronto(nome):
    a, id_a = nuovo_utente(nome)
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    return a, id_a


def test_richieste_parallele_a_59_su_60_ne_passa_una_sola(ambiente, monkeypatch):
    a, id_a = _pronto("utentea")
    _quasi_al_tetto(id_a, limiti.MAX_SCAMBI_AL_GIORNO - 1)
    originale = server.consigli.proposte_scambi

    def lenta(*args, **k):
        time.sleep(0.4)                          # il calcolo dura: tutte le richieste arrivano mentre la prima lavora
        return originale(*args, **k)
    monkeypatch.setattr(server.consigli, "proposte_scambi", lenta)
    codici, porta = [], threading.Barrier(8)

    def vai(i):
        porta.wait()
        codici.append(ricerca(a, 100 + i).status_code)
    fili = [threading.Thread(target=vai, args=(i,)) for i in range(8)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(30)
    assert sorted(codici) == [200] + [429] * 7
    assert limiti.usati_oggi(id_a, "scambi") == limiti.MAX_SCAMBI_AL_GIORNO


def test_ricerca_fallita_restituisce_il_posto(ambiente, monkeypatch):
    a, id_a = _pronto("utentea")
    assert ricerca(a, 1).status_code == 200
    assert limiti.usati_oggi(id_a, "scambi") == 1
    buona = server.consigli.proposte_scambi

    def rotta(*args, **k):
        raise ValueError("calcolo non riuscito")
    monkeypatch.setattr(server.consigli, "proposte_scambi", rotta)
    assert ricerca(a, 2).status_code == 400
    assert limiti.usati_oggi(id_a, "scambi") == 1                  # l'errore non consuma
    monkeypatch.setattr(server.consigli, "proposte_scambi", buona)
    assert ricerca(a, 2).status_code == 200                        # e riprovarla costa un solo uso
    assert limiti.usati_oggi(id_a, "scambi") == 2


def test_in_calcolo_202_restituisce_il_posto(ambiente, monkeypatch):
    a, id_a = _pronto("utentea")
    from fanta import calcolo

    def in_calcolo(*args, **k):
        raise calcolo.InCalcolo()
    monkeypatch.setattr(server.consigli, "proposte_scambi", in_calcolo)
    assert ricerca(a, 3).status_code == 202
    assert limiti.usati_oggi(id_a, "scambi") == 0
