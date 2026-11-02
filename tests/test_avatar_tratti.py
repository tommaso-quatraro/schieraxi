"""Tratti grossolani per gli avatar (contratto versione 3): file di dati, lettura prudente, API e estrattore (su immagini finte, mai foto vere)."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from fanta import archivio, avatar, server

RADICE = Path(__file__).resolve().parent.parent


def carica_script():
    spec = importlib.util.spec_from_file_location("avatar_tratti", RADICE / "script" / "avatar_tratti.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_il_file_dei_tratti_e_valido_e_leggero():
    file = RADICE / "fanta" / "avatar_tratti.json"
    if not file.exists():
        pytest.skip("il progetto pubblico non ha i tratti dei giocatori (docs/AVATAR-DIRITTI.md)")
    grezzo = json.loads(file.read_text(encoding="utf-8"))
    assert grezzo["versione"] == 3 and len(grezzo["tratti"]) >= 300
    for k, v in grezzo["tratti"].items():
        assert k.isdigit() and {"c", "a", "b"} <= set(v) <= {"p", "c", "a", "b", "f"}, (k, v)
        assert 0 <= v["c"] <= 7 and v["a"] in "RCLI" and v["b"] in (0, 1)
        assert 1 <= v["p"] <= 6 and ("f" in v) == (v["b"] == 1)                 # carnagione 1-6 (grana grossa); `f` solo con la barba
        assert v.get("f", 0) in (0, 1)
    assert file.stat().st_size < 60000
    assert len(avatar.tutti()) == len(grezzo["tratti"])


def test_lettura_prudente(tmp_path, monkeypatch):
    f = tmp_path / "t.json"
    monkeypatch.setattr(avatar, "FILE", f)
    avatar.tutti.cache_clear()
    assert avatar.tutti() == {} and avatar.di(5) is None                      # file mancante
    f.write_text("non e' json", encoding="utf-8")
    avatar.tutti.cache_clear()
    assert avatar.tutti() == {}
    f.write_text(json.dumps({"versione": 2, "tratti": {"1": {"p": 2, "c": 9, "a": "L", "b": 1, "x": 1}, "2": {"c": "a"}, "x": {"c": 1}, "3": {"c": 6, "b": True}, "4": {"p": 9, "f": 1, "b": 0}, "5": {"p": 3, "b": 1, "f": 1}}}), encoding="utf-8")
    avatar.tutti.cache_clear()
    assert avatar.tutti() == {1: {"p": 2, "a": "L", "b": 1}, 3: {"c": 6}, 4: {"b": 0}, 5: {"p": 3, "b": 1, "f": 1}}    # campi non validi scartati; `f` solo con la barba
    assert avatar.di("1") == {"p": 2, "a": "L", "b": 1} and avatar.di("zz") is None and avatar.di(None) is None
    avatar.tutti.cache_clear()


@pytest.fixture
def client(monkeypatch):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(archivio.SCHEMA)
    db.executemany("INSERT INTO calciatori(id,nome,ruolo,squadra,quotazione) VALUES(?,?,?,?,?)", [(1, "Martinez L.", "A", "Inter", 30), (2, "Rossi M.", "P", "Lazio", 3)])
    monkeypatch.setattr(server, "_db", lambda: type("C", (), {"execute": lambda s, *a: db.execute(*a), "close": lambda s: None})())
    monkeypatch.setattr(avatar, "tutti", lambda: {1: {"p": 3, "c": 2, "a": "C", "b": 0}})
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_api_avatar_e_campo_avatar_nei_giocatori(client):
    r = client.get("/api/avatar").json()
    assert r == {"versione": 3, "tratti": {"1": {"p": 3, "c": 2, "a": "C", "b": 0}}}
    tutti = {x["id"]: x for x in client.get("/api/giocatori?tutti=1").json()}
    assert tutti[1]["avatar"] == {"p": 3, "c": 2, "a": "C", "b": 0} and "avatar" not in tutti[2]      # solo chi ce l'ha
    assert client.get("/api/giocatori?q=martinez").json()[0]["avatar"]["a"] == "C"
    assert set(tutti[2]) == {"id", "nome", "ruolo", "squadra", "quotazione"}                          # il resto non cambia


def test_il_web_usa_i_tratti_e_senza_di_loro_va_di_seme():
    js = (RADICE / "fanta" / "web" / "app.js").read_text(encoding="utf-8")
    assert "stato.tratti[idAvatar(x)]" in js and 'api("/api/avatar")' in js and "x.avatar ||" in js
    assert "catch { stato.tratti = null; }" in js                              # se non arrivano: tutto dal seme


def disegna_testa(sfondo_testa, capelli=None, barba=None, larghi=0, lunghi=False):
    """Ritaglio finto 200x200: testa ovale, capelli in alto, spalle in basso, sfondo trasparente."""
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((72 - larghi, 12, 128 + larghi, 100), fill=sfondo_testa + (255,))
    if capelli:
        d.pieslice((72 - larghi, 12, 128 + larghi, 70), 180, 360, fill=capelli + (255,))
        d.rectangle((72 - larghi, 40, 128 + larghi, 44), fill=capelli + (255,)) if larghi else None
    if barba:
        d.chord((74, 50, 126, 104), 0, 180, fill=barba + (255,))
    if lunghi and capelli:
        d.rectangle((64, 60, 74, 100), fill=capelli + (255,))
        d.rectangle((126, 60, 136, 100), fill=capelli + (255,))
    d.rectangle((50, 150, 150, 200), fill=(30, 60, 140, 255))
    return im
