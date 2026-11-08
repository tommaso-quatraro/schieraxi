"""Ricerca giocatori: l'elenco intero si scarica una volta e si filtra sul dispositivo; la regola dei nomi del browser è quella del server."""
import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fanta import archivio, listone, nomi, server
import codice_web

RADICE = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
NOMI = ["Çalhanoğlu H.", "N'Dicka E.", "Lautaro Martínez", "Di Lorenzo G.", "Esposito Se.", "Østigård L.", "Łukasz", "O’Neill-Smith", "  Rossi   M. ", "Müller", "Ðorđe", "Saelemaekers A."]


@pytest.fixture
def client(monkeypatch):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(archivio.SCHEMA)
    db.executemany("INSERT INTO calciatori(id,nome,ruolo,squadra,quotazione) VALUES(?,?,?,?,?)",
                   [(1, "Martinez L.", "A", "Inter", 30), (2, "Martini G.", "C", "Roma", 5), (3, "Amartin Z.", "D", "Milan", 9), (4, "Rossi M.", "P", "Lazio", 3)])
    monkeypatch.setattr(server, "_db", lambda: type("C", (), {"execute": lambda s, *a: db.execute(*a), "close": lambda s: None})())
    monkeypatch.setattr(listone, "nomi_completi", lambda: {})
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_elenco_intero_per_la_ricerca_sul_dispositivo(client):
    r = client.get("/api/giocatori?tutti=1").json()
    assert {x["id"] for x in r} == {1, 2, 3, 4}
    assert set(r[0]) == {"id", "nome", "ruolo", "squadra", "quotazione"}


def test_la_ricerca_sul_server_resta_come_prima(client):
    r = client.get("/api/giocatori?q=martin").json()
    assert [x["id"] for x in r] == [1, 2, 3]                  # prima chi inizia con la ricerca (per quotazione), poi gli altri
    assert client.get("/api/giocatori?q=martin&limite=1").json()[0]["id"] == 1
    assert client.get("/api/giocatori").json() == []


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_la_normalizzazione_del_browser_e_quella_del_server():
    js = codice_web.app()
    riga = re.search(r"^const LETTERE_SPECIALI = .*?\n.*?\n.*?(?=\nlet listoneCerca)", js, re.S | re.M).group(0)
    codice = riga + f"\nconsole.log(JSON.stringify({json.dumps(NOMI, ensure_ascii=False)}.map(normNome)));"
    out = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [nomi.normalizza(n) for n in NOMI]


def test_app_non_fa_una_richiesta_per_tasto():
    js = codice_web.app()
    assert js.count("/api/giocatori?q=") == 1                 # solo il ripiego, con annullamento della richiesta precedente
    assert "abortoCerca.abort()" in js and "api/giocatori?tutti=1" in js


def test_si_cerca_anche_per_nome_proprio(client, monkeypatch):
    """«Lautaro» trova «Martinez L.» se il nome per esteso è noto; il campo `nome_completo` c'è solo per chi lo ha."""
    monkeypatch.setattr(listone, "nomi_completi", lambda: {1: "Lautaro Martínez", 4: "Mario Rossi"})
    r = client.get("/api/giocatori?q=lautaro").json()
    assert [x["id"] for x in r] == [1] and r[0]["nome_completo"] == "Lautaro Martínez"
    assert [x["id"] for x in client.get("/api/giocatori?q=mario").json()] == [4]
    tutti = {x["id"]: x for x in client.get("/api/giocatori?tutti=1").json()}
    assert tutti[1]["nome_completo"] == "Lautaro Martínez" and "nome_completo" not in tutti[2]


def test_nomi_completi_dall_archivio(tmp_path):
    f = tmp_path / "fanta.sqlite"
    db = sqlite3.connect(f)
    db.executescript(archivio.SCHEMA)
    db.executemany("INSERT INTO understat_giocatori(id, nome, calciatore_id, abbinamento) VALUES(?,?,?,?)",
                   [(1, "Lautaro Martínez", 10, "squadra"), (2, "Tizio Incerto", 11, "squadra_simile"), (3, "Senza Codice", None, None),
                    (4, "Trasferito Altrove", 12, "altra_squadra")])
    db.commit()
    db.close()
    assert listone.nomi_completi(f) == {10: "Lautaro Martínez", 12: "Trasferito Altrove"}
    assert listone.nomi_completi(tmp_path / "manca.sqlite") == {}


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_la_ricerca_sul_dispositivo_usa_il_nome_completo():
    js = codice_web.app()
    pezzo = re.search(r"^const LETTERE_SPECIALI = .*?\n.*?\n.*?(?=\nlet listoneCerca)", js, re.S | re.M).group(0)
    filtra = re.search(r"^function filtraListone\(.*?^}", js, re.S | re.M).group(0)
    lista = [{"id": 1, "nome": "Martinez L.", "nome_completo": "Lautaro Martínez", "quotazione": 30},
             {"id": 2, "nome": "Valenti", "nome_completo": "Lautaro Valenti", "quotazione": 5},
             {"id": 3, "nome": "Lautarelli", "quotazione": 1}, {"id": 4, "nome": "Rossi", "quotazione": 9}]
    codice = (pezzo + "\n" + filtra + f"\nconst l = {json.dumps(lista)}.map(x => ({{ ...x, n: normNome(x.nome), nc: x.nome_completo ? normNome(x.nome_completo) : '' }}));"
              "\nconsole.log(JSON.stringify(filtraListone('lautaro', 10, l)));")
    out = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert [x["id"] for x in r] == [1, 2] and "nc" not in r[0] and "n" not in r[0]      # prima chi vale di più
