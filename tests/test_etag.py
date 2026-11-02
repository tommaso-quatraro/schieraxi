"""ETag e If-Match: scrivere con un ETag vecchio si ferma con 412; senza If-Match (client vecchi) tutto funziona come prima."""
import contextlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pandas as pd
import pytest
from fastapi import HTTPException

from fanta import account, calcolo, server, versioni
from fanta.regole import Regole

from test_account_http import PASSWORD, cliente
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

ROSE = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"


@pytest.fixture
def mondo(ambiente, monkeypatch):
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()


def regole_con(nome: str) -> dict:
    return asdict(Regole()) | {"nome_lega": nome}


def etag(r) -> str:
    assert r.status_code == 200, r.text
    return r.headers["etag"]


# ---------------------------------------------------------------- le regole di If-Match
def test_if_match_assente_asterisco_debole_e_elenco():
    class R:
        def __init__(self, v):
            self.headers = {} if v is None else {"if-match": v}
    versioni.controlla(R(None), '"a"')
    versioni.controlla(R("*"), '"a"')
    versioni.controlla(R('"a"'), '"a"')
    versioni.controlla(R('W/"a"'), '"a"')
    versioni.controlla(R('"x", "a"'), '"a"')
    with pytest.raises(HTTPException) as e:
        versioni.controlla(R('"x"'), '"a"')
    assert e.value.status_code == 412 and e.value.headers["ETag"] == '"a"' and "altro dispositivo" in e.value.detail


def test_l_etag_cambia_con_il_contenuto_e_c_e_anche_senza_file(tmp_path):
    f = tmp_path / "x.json"
    vuoto = versioni.etag_file(f)
    assert vuoto == versioni.etag_file(f)
    f.write_text("[1]", encoding="utf-8")
    uno = versioni.etag_file(f)
    f.write_text("[1, 2]", encoding="utf-8")
    assert len({vuoto, uno, versioni.etag_file(f)}) == 3
    assert versioni.etag_dati({"a": 1, "b": 2}) == versioni.etag_dati({"b": 2, "a": 1})


# ---------------------------------------------------------------- ogni risorsa
def prova(c, leggi, scrivi):
    """leggi() -> risposta con ETag; scrivi(intestazioni) -> risposta. Il vecchio ETag non vale più dopo una scrittura."""
    e0 = etag(leggi())
    r1 = scrivi({"If-Match": e0})
    assert r1.status_code == 200, r1.text
    e1 = r1.headers["etag"]
    assert e1 != e0 and etag(leggi()) == e1                            # la risposta dice già il nuovo ETag
    vecchio = scrivi({"If-Match": e0})
    assert vecchio.status_code == 412 and "altro dispositivo" in vecchio.json()["detail"] and vecchio.headers["etag"] == e1
    assert etag(leggi()) == e1                                          # e non ha cambiato niente
    return e1


def test_regole(mondo):
    a, _ = nuovo_utente("utentea")
    prova(a, lambda: a.get("/api/regole"), lambda h, n=iter(range(100)): a.put("/api/regole", json=regole_con(f"Lega {next(n)}"), headers=h))


def test_rose_crediti_mia_squadra_e_importazione(mondo):
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    leggi = lambda: a.get("/api/squadre")  # noqa: E731
    contatore = iter(range(1, 100))
    prova(a, leggi, lambda h: a.put("/api/crediti", json={"crediti": {"Mia": next(contatore)}}, headers=h))
    nomi = iter(["Altra", "Mia"] * 20)
    prova(a, leggi, lambda h: a.put("/api/mia-squadra", json={"nome": next(nomi)}, headers=h))
    righe = iter(range(1, 100))
    prova(a, leggi, lambda h: a.post("/api/rose/testo", json={"testo": ROSE + f"Terza {next(righe)}\nD\tBastoni\t5\n"}, headers=h))
    quarte = iter(range(1, 100))
    prova(a, lambda: a.get("/api/rosa"), lambda h: a.post("/api/rose/file", headers=h, files={
        "file": ("r.txt", (ROSE + f"Quarta {next(quarte)}" + chr(10) + "C" + chr(9) + "Barella" + chr(9) + "5" + chr(10)).encode(), "text/plain")}))


def test_rinomina_squadra(mondo):
    """Il nome di una squadra si cambia dopo l'importazione: rose, «la mia squadra» e stemma la seguono; If-Match come le rose."""
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 40
    assert a.post("/api/squadre/immagine", params={"squadra": "Mia", "tipo": "stemma"},
                  files={"file": ("s.png", png, "image/png")}).status_code == 200
    nomi = iter(["I Lupi", "Mia"] * 20)
    prova(a, lambda: a.get("/api/squadre"), lambda h: a.put("/api/squadre/nome", json={"nome": _mia(a), "nuovo": next(nomi)}, headers=h))
    r = a.put("/api/squadre/nome", json={"nome": _mia(a), "nuovo": "  I   Lupi  "})
    assert r.status_code == 200 and r.json()["nome"] == "I Lupi" and r.json()["mia_squadra"] == "I Lupi"
    sq = {s["nome"]: s for s in a.get("/api/squadre").json()}
    assert set(sq) == {"I Lupi", "Altra"} and sq["I Lupi"]["mia"] and sq["I Lupi"]["immagini"]["stemma"]
    assert a.get("/api/squadre/immagine", params={"squadra": "I Lupi", "tipo": "stemma"}).status_code == 200
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "altra"}).status_code == 409      # c'è già (maiuscole a parte)
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "Altra!"}).status_code == 409     # stesso file dello stemma
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "   "}).status_code == 400
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "x" * 61}).status_code == 400
    assert a.put("/api/squadre/nome", json={"nome": "I Lupi", "nuovo": "I\tLupi\nRossi"}).json()["nome"] == "I Lupi Rossi"
    assert a.put("/api/squadre/nome", json={"nome": "Nessuna", "nuovo": "Altro"}).status_code == 404
    assert a.put("/api/squadre/nome", json={"nome": "I", "nuovo": "Altro"}).status_code == 404            # niente inizio del nome


def _mia(a):
    return next(s["nome"] for s in a.get("/api/squadre").json() if s["mia"])


def test_scelta_di_una_giornata(mondo):
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    leggi = lambda: a.get("/api/scelta", params={"giornata": 9})  # noqa: E731
    assert leggi().json() is None and etag(leggi())
    titolari = iter([[1, 2, 3], [4, 5, 6], [7, 8, 9], [1, 5, 9]])
    e1 = prova(a, leggi, lambda h: a.post("/api/formazione/valuta", json={"titolari": next(titolari), "giornata": 9, "salva": True}, headers=h))
    r = a.delete("/api/scelta", params={"giornata": 9}, headers={"If-Match": '"vecchio"'})
    assert r.status_code == 412 and leggi().json() is not None
    assert a.delete("/api/scelta", params={"giornata": 9}, headers={"If-Match": e1}).status_code == 200
    assert leggi().json() is None
    # valutare senza salvare non guarda l'ETag: non scrive niente
    assert a.post("/api/formazione/valuta", json={"titolari": [1, 2, 3], "giornata": 9}, headers={"If-Match": '"vecchio"'}).status_code == 200


def test_osservati(mondo):
    a, _ = nuovo_utente("utentea")
    numeri = iter(range(1, 100))
    prova(a, lambda: a.get("/api/osservati"), lambda h: a.put(f"/api/osservati/{next(numeri)}", headers=h))
    e = etag(a.get("/api/osservati"))
    assert a.delete("/api/osservati/1", headers={"If-Match": '"vecchio"'}).status_code == 412
    assert a.delete("/api/osservati/1", headers={"If-Match": e}).status_code == 200


def test_impostazioni_degli_avvisi(mondo):
    a, _ = nuovo_utente("utentea")
    valori = iter([False, True] * 10)
    prova(a, lambda: a.get("/api/avvisi"), lambda h: a.put("/api/avvisi", json={"riepilogo": next(valori)}, headers=h))


# ---------------------------------------------------------------- compatibilità e conflitti veri
def test_senza_if_match_si_scrive_come_prima(mondo):
    a, _ = nuovo_utente("utentea")
    assert a.put("/api/regole", json=regole_con("Uno")).status_code == 200
    assert a.put("/api/regole", json=regole_con("Due"), headers={"If-Match": "*"}).status_code == 200
    assert a.get("/api/regole").json()["nome_lega"] == "Due"


def test_client_vecchio_non_azzera_i_tempi_della_lega(mondo):
    a, _ = nuovo_utente("utentea")
    nuove = regole_con("Con i tempi")
    nuove["scadenza_minuti"], nuove["prima_giornata_lega"] = 10, 4
    assert a.put("/api/regole", json=nuove).status_code == 200
    vecchie = regole_con("Dal client vecchio")                    # non conosce i due campi nuovi
    vecchie.pop("scadenza_minuti", None), vecchie.pop("prima_giornata_lega", None)
    assert a.put("/api/regole", json=vecchie).status_code == 200
    r = a.get("/api/regole").json()
    assert (r["nome_lega"], r["scadenza_minuti"], r["prima_giornata_lega"]) == ("Dal client vecchio", 10, 4)
    assert r["aggiornamenti_vicino_scadenza"] is True
    assert a.put("/api/regole", json=regole_con("Valori sbagliati") | {"scadenza_minuti": -5}).status_code in (400, 422)


def test_due_dispositivi_dello_stesso_utente(mondo):
    a1, _ = nuovo_utente("utentea")
    a2 = cliente()
    assert a2.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD}).status_code == 200
    e1 = etag(a1.get("/api/regole"))
    assert a2.put("/api/regole", json=regole_con("Dal secondo telefono"), headers={"If-Match": etag(a2.get("/api/regole"))}).status_code == 200
    r = a1.put("/api/regole", json=regole_con("Dal primo telefono"), headers={"If-Match": e1})        # il primo non sapeva del cambio
    assert r.status_code == 412
    assert a1.get("/api/regole").json()["nome_lega"] == "Dal secondo telefono"                        # e rilegge quello nuovo
    assert a1.put("/api/regole", json=regole_con("Dal primo telefono"), headers={"If-Match": etag(a1.get("/api/regole"))}).status_code == 200


def test_utenti_diversi_hanno_etag_diversi(mondo):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    a.put("/api/regole", json=regole_con("Lega di A"))
    ea, eb = etag(a.get("/api/regole")), etag(b.get("/api/regole"))
    assert ea != eb
    assert b.put("/api/regole", json=regole_con("Lega di B"), headers={"If-Match": ea}).status_code == 412      # l'ETag di A non apre le scritture di B


def test_scritture_insieme_con_lo_stesso_etag_ne_passa_una_sola(mondo):
    a, _ = nuovo_utente("utentea")
    e = etag(a.get("/api/avvisi"))
    scrivi = lambda i: a.put("/api/avvisi", json={"silenzio_da": i % 24, "cambi": i % 2 == 0}, headers={"If-Match": e}).status_code  # noqa: E731
    with ThreadPoolExecutor(8) as pool:
        esiti = list(pool.map(scrivi, range(1, 9)))
    assert sorted(esiti) == [200] + [412] * 7


def test_l_etag_degli_avvisi_non_cambia_con_le_altre_impostazioni_dello_stesso_file(mondo):
    """«Mostra tutte», primo avvio e backup vivono nel file degli avvisi ma non devono dare un falso 412."""
    a, _ = nuovo_utente("utentea")
    e0 = etag(a.get("/api/avvisi"))
    assert a.put("/api/funzioni", json={"mostra_tutte": True}, headers={"X-Fanta": "1"}).status_code == 200
    assert a.put("/api/primo-avvio", json={"fatti": ["rose"]}, headers={"X-Fanta": "1"}).status_code == 200
    assert a.get("/api/backup").status_code == 200
    assert etag(a.get("/api/avvisi")) == e0
    r = a.put("/api/avvisi", json={"riepilogo": False}, headers={"If-Match": e0})
    assert r.status_code == 200, r.text
    e1 = r.headers["etag"]
    assert e1 != e0 and etag(a.get("/api/avvisi")) == e1
    # un vero cambio degli avvisi in mezzo: 412
    assert a.put("/api/avvisi", json={"cambi": False}).status_code == 200
    assert a.put("/api/avvisi", json={"riepilogo": True}, headers={"If-Match": e1}).status_code == 412
    # gli altri campi del file sono ancora lì
    assert a.get("/api/funzioni").json()["mostra_tutte"] is True


def test_spento_gli_etag_ci_sono_e_nessuno_e_obbligatorio(monkeypatch, tmp_path, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "non-deve-esistere"))
    c = cliente()
    e = etag(c.get("/api/regole"))
    assert c.put("/api/regole", json=regole_con("Come prima")).status_code == 200                        # un client vecchio: senza If-Match
    assert c.put("/api/regole", json=regole_con("Vecchio ETag"), headers={"If-Match": e}).status_code == 412
    assert c.put("/api/avvisi", json={"cambi": False}).status_code == 200
    assert not (tmp_path / "non-deve-esistere").exists()
