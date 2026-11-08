"""«Da fare» in Oggi e primo avvio guidato nella web app: controlli statici (la prova nel browser si fa a mano a 390 e 1024 px)."""
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
DAFARE = codice_web.leggi("dafare.js")
PRIMO = codice_web.leggi("primoavvio.js")


def test_i_file_sono_caricati_prima_di_app_e_serviti_anche_senza_accesso():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert html.index("dafare.js") < html.index("primoavvio.js") < html.index("app.js")
    sw = codice_web.leggi("sw.js")
    assert '"/dafare.js"' in sw and '"/primoavvio.js"' in sw
    c = TestClient(server.app)
    assert c.get("/dafare.js").status_code == 200 and c.get("/primoavvio.js").status_code == 200


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node")
@pytest.mark.parametrize("nome", ["dafare.js", "primoavvio.js"])
def test_la_sintassi_e_valida(nome):
    r = subprocess.run(["node", "--check", str(WEB / nome)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_oggi_mostra_la_card_e_ne_collega_i_pulsanti():
    assert "${cardDaFare(o.da_fare)}" in APP and "collegaDaFare(o.da_fare)" in APP
    # dal 1/11/2026 la configurazione guidata si riprende solo dalla riga di «Da fare» (niente voce in Impostazioni)
    IMP = codice_web.leggi("impostazioni.js")
    assert "primoAvvioSeServe()" in APP and "apri-primo-avvio" not in APP and "apri-primo-avvio" not in IMP
    assert 'v.tipo === "primo_avvio"' in DAFARE and "apriPrimoAvvio()" in DAFARE


def test_i_testi_del_server_passano_da_esc():
    for dato in ("v.testo", "v.azione"):
        assert f"esc({dato}" in DAFARE or "esc(testoDi(v" in DAFARE, dato          # il testo può passare dalla traduzione (testoDi), sempre dentro esc()
    corpo_riga = DAFARE[DAFARE.index("function dfRiga"):DAFARE.index("function cardDaFare")]
    assert "${v." not in corpo_riga.replace("${esc(", "")
    # nel primo avvio ogni dato dinamico (nomi di squadre, passi) è protetto
    assert "esc(s.nome)" in PRIMO and "esc(PA_NOMI[p])" in PRIMO and "esc(e.message || e)" in PRIMO


def test_un_solo_percorso_breve_e_saltabile():
    assert 'const PA_PASSI = ["rose", "squadra", "tempi"]' in PRIMO      # breve: rose, squadra, tempi della lega (2/11/2026)
    assert not (WEB / "onboarding.js").exists() and "onboarding.js" not in (WEB / "index.html").read_text(encoding="utf-8")
    # chi ha già finito (o saltato) la vecchia procedura non la ripassa
    assert 'o.stato === "completato" || o.stato === "saltato"' in PRIMO
    assert 'id="pa-salta"' in PRIMO
    assert "/api/primo-avvio" in PRIMO and "apriPrimoAvvio" in DAFARE


def test_bersagli_di_tocco_da_44_px():
    for selettore in (".df-azione", ".pa-passo"):
        regola = re.search(re.escape(selettore) + r" \{([^}]*)\}", CSS)
        assert regola and "min-height: 44px" in regola.group(1), selettore


def test_senza_rose_e_un_benvenuto_non_un_errore():
    assert "if (o.senza_rose)" in APP and "data-importa-rose" in APP
    assert "const erroreVista = e => senzaRose(e) ? cartaSenzaRose()" in APP     # Formazione, Mercato, Scambi: stato vuoto
    assert "nessuna rosa" in APP and ".benvenuto" in CSS


def test_il_benvenuto_sta_a_sinistra_con_il_titolo():
    """#455: sul PC «Benvenuto in SchieraXI» stava in mezzo alla pagina (x 410-1030 a 1440 px) e il titolo «Oggi» a sinistra.
    Resta stretto (620 px) ma parte dal bordo sinistro del titolo, come le altre carte."""
    regole = re.findall(r"([^{}]*\.benvenuto[^{}]*)\{([^}]*)\}", CSS)
    assert regole
    for selettore, corpo in regole:
        assert "auto" not in re.sub(r"\s+", "", corpo).replace("width:100%", ""), selettore     # niente margini automatici
        assert "justify-self: center" not in corpo and "margin: 0 auto" not in corpo, selettore
    assert any("max-width: 620px" in corpo for _, corpo in regole)
