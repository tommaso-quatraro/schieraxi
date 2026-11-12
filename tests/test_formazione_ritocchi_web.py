"""Formazione e «Da fare» (collaudo del 2/11/2026): «Modifica a mano» lasciata senza cambi, ★ non sul numero più alto,
etichette a capo a 768 px, «Controlla» dei dati vecchi che apre Stato dei dati."""
import json
import shutil
import subprocess


from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
DAFARE = codice_web.leggi("dafare.js")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _node(codice: str):
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_il_nome_sta_nella_testata_non_dentro_oggi():
    """Grafica B (spec §9 e §11): Oggi parte dal suo titolo, come ogni schermata; il nome SchieraXI è quello disegnato della testata
    (letto «SchieraXI» dai lettori di schermo, come il nome della finestra). Il nome con lo slogan dentro Oggi, il suo carattere e i
    suoi testi non ci sono più."""
    assert "marchioOggi" not in APP and "--font-marchio" not in CSS and ".wordmark" not in CSS
    assert '"marchio.slogan"' not in TESTI and '"marchio.nome_voce"' not in TESTI and '"marchio.slogan_voce"' not in TESTI
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<use href="#wm-c"/>' in html[html.index("<header"):html.index("</header>")]


def test_controlla_dei_dati_vecchi_apre_stato_dei_dati():
    assert 'if (v.id === "dati-vecchi" && typeof apriStatoDati === "function") { vai("impostazioni", "gestione"); apriStatoDati(); return; }' in DAFARE
