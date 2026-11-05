"""Il carattere dei numeri (Archivo, SIL OFL 1.1) servito dal nostro server: piccolo, con la licenza, pubblico, offline."""
import importlib.util
import json
import re

import pytest
from fastapi.testclient import TestClient

from fanta import rotte_account, server

WEB = server.WEB
RADICE = WEB.parent.parent


@pytest.fixture
def client():
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_woff2_piccolo_con_la_licenza_accanto():
    f = WEB / "caratteri" / "archivo.woff2"
    assert f.read_bytes()[:4] == b"wOF2" and f.stat().st_size <= 80_000
    ofl = (WEB / "caratteri" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in ofl and "The Archivo Project Authors" in ofl


def test_il_server_lo_da_con_il_tipo_giusto_anche_prima_dell_accesso(client):
    r = client.get("/caratteri/archivo.woff2")
    assert r.status_code == 200 and r.headers["content-type"].startswith("font/woff2")
    assert rotte_account._pubblico("/caratteri/archivo.woff2") and rotte_account._pubblico("/caratteri/OFL.txt")


def test_con_gli_account_accesi_risponde_senza_sessione(multiutente, dati_isolati):
    """La pagina d'accesso lo chiede prima di avere una sessione: niente 401, e la licenza si legge anche da lì."""
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    r = c.get("/caratteri/archivo.woff2")
    assert r.status_code == 200 and r.headers["content-type"].startswith("font/woff2")
    assert r.content[:4] == b"wOF2"
    licenza = c.get("/caratteri/OFL.txt")
    assert licenza.status_code == 200 and "SIL OPEN FONT LICENSE" in licenza.text
    assert c.get("/api/oggi").status_code == 401          # il prefisso apre solo i caratteri, non il resto


def test_il_carattere_sta_nella_scocca_offline():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/caratteri/archivo.woff2" in json.loads(re.search(r"const FILE = (\[.*?\]);", sw).group(1))


def test_crediti_e_avvisi_citano_archivo(client):
    for lingua in ("it", "en"):
        pagina = client.get(f"/crediti?lingua={lingua}").text
        assert "Archivo" in pagina and "SIL Open Font License 1.1" in pagina, lingua
    avvisi = (RADICE / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "fanta/web/caratteri/" in avvisi


def test_dentro_il_file_ci_sono_cifre_tabellari_lettere_e_licenza():
    """Controllo con fontTools (strumento di chi genera il file, non serve all'app: senza, il test si salta)."""
    pytest.importorskip("fontTools")
    pytest.importorskip("brotli")
    spec = importlib.util.spec_from_file_location("carattere_web", RADICE / "script" / "carattere_web.py")
    carattere_web = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(carattere_web)
    esito = carattere_web.controlla(WEB / "caratteri" / "archivo.woff2")
    assert esito["tnum"] and esito["licenza"], esito
    assert esito["mancanti"] == [], "lettere della spec che il file non ha"
    assert esito["assi"] == {"wght": (400.0, 700.0)}, "larghezza fissa (semi-stretto), peso variabile da 400 a 700"
