"""Volti illustrati nell'interfaccia: niente più foto di default, il generatore è caricato e messo in cache, l'avatar ha il nome per gli screen reader."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fanta import server
import codice_web

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "fanta" / "web"


@pytest.fixture
def client():
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_foto_spente_di_default(client, monkeypatch):
    foto = pytest.importorskip("fanta.foto")               # nella versione pubblica le foto non ci sono
    monkeypatch.delenv("FANTA_FOTO", raising=False)
    assert foto.attive() is False
    assert client.get("/api/foto-disponibili").json() == {"attive": False, "ids": []}
    assert client.get("/api/foto/1").status_code == 404


def test_foto_si_riaccendono_con_la_variabile(client, monkeypatch, tmp_path):
    foto = pytest.importorskip("fanta.foto")
    monkeypatch.setenv("FANTA_FOTO", "1")
    monkeypatch.setattr(foto, "CARTELLA", tmp_path)
    assert foto.attive() is True
    r = client.get("/api/foto-disponibili").json()
    assert r["attive"] is True and r["ids"] == []


@pytest.mark.parametrize("valore", ["", "0", "true", "yes", "on", " 2", "si"])
def test_interruttore_foto_acceso_solo_con_uno(monkeypatch, valore):
    foto = pytest.importorskip("fanta.foto")
    monkeypatch.setenv("FANTA_FOTO", valore)
    assert foto.attive() is False                                   # solo «1» le accende: ogni altro valore le lascia spente


def test_l_app_parte_anche_senza_il_modulo_delle_foto():
    """Come nella versione pubblica: senza fanta/foto.py e fanta/rotte_foto.py il server si importa, non ci sono rotte /api/foto*, lo stato dei dati dice zero foto."""
    import subprocess
    import sys
    codice = ("import sys, json; sys.path.insert(0, %r); sys.modules['fanta.foto'] = None; sys.modules['fanta.rotte_foto'] = None\n"
              "from fanta import server, stato_dati, __main__ as m\n"
              "import importlib.util\n"
              "rotte = [r.path for r in server.app.routes if getattr(r, 'path', '').startswith('/api/foto')]\n"
              "print(json.dumps([rotte, stato_dati.foto is None, importlib.util.find_spec('fanta.foto') is None]))\n") % str(RADICE)
    r = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True, timeout=120, cwd=str(RADICE))
    assert r.returncode == 0, r.stderr[-600:]
    assert r.stdout.strip().splitlines()[-1] == "[[], true, true]"


def test_il_generatore_e_caricato_prima_di_app_e_dal_service_worker():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert html.index('src="avatar.js"') < html.index('src="app.js"')
    assert '"/avatar.js"' in codice_web.leggi("sw.js")
    assert "/avatar.js" in (RADICE / "fanta" / "rotte_account.py").read_text(encoding="utf-8")      # visibile anche prima dell'accesso


def test_l_interfaccia_usa_i_volti_e_niente_interruttore_foto():
    js = codice_web.app()
    assert "AvatarSchieraxi.svg(" in js
    assert 'role="img" aria-label="${esc(x.nome' in js                      # nome del giocatore, sempre escapato
    assert "Foto dei giocatori" not in js and 'seg("foto"' not in js
    assert "ritaglio senza sfondo" not in js and "iniziali(" not in js
    assert re.search(r"if \(r\.attive\)", js)                                # le foto solo se il server le attiva
    assert "caricaSvg(svgAvatar(" in js                                      # anche l'immagine da condividere ha i volti


def test_animazione_calma_con_riduci_movimento():
    css = (WEB / "stile.css").read_text(encoding="utf-8")
    assert "@keyframes avatar-entra" in css and "@keyframes avatar-dissolvi" in css
    assert css.count("avatar-dissolvi .25s") >= 2                            # sistema e interruttore dell'app
