"""Importazione delle rose in due passi nella web app (fanta/web/anteprima.js): anteprima, scelte sui dubbi, conferma.
Le funzioni pure si provano con node; il resto sono controlli statici (la prova nel browser si fa a mano)."""
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from fanta import rotte_account, server

WEB = server.WEB
ANTEPRIMA = (WEB / "anteprima.js").read_text(encoding="utf-8")
APP = (WEB / "app.js").read_text(encoding="utf-8")
PRIMO = (WEB / "primoavvio.js").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

SQUADRE = [
    {"nome": "Rossi", "giocatori": [
        {"testo": "Bastoni", "stato": "sicuro", "id": 1},
        {"testo": "Martinez", "stato": "da_controllare", "id": 10, "alternative": [{"id": 10}, {"id": 11}]},
        {"testo": "Martinez", "stato": "da_controllare", "id": 10, "alternative": [{"id": 10}, {"id": 11}]},
        {"testo": "Esposito", "stato": "da_controllare", "id": None, "alternative": [{"id": 20}, {"id": 21}]},
        {"testo": "Pinco", "stato": "non_trovato", "id": None, "alternative": []},
    ]},
    {"nome": "Verdi", "giocatori": [{"testo": "Martinez", "stato": "da_controllare", "id": 10, "alternative": [{"id": 10}]}]},
]


def _node(espressione: str):
    codice = TESTI + "\nconst esc = x => String(x);\n" + \
        'const NOMI_RUOLO = { P: "Portieri", D: "Difensori", C: "Centrocampisti", A: "Attaccanti" };\n' + \
        'const NOME_RUOLO_1 = { P: "Portiere", D: "Difensore", C: "Centrocampista", A: "Attaccante" };\n' + \
        ANTEPRIMA + f"\nconsole.log(JSON.stringify({espressione}));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_le_correzioni_partono_dalle_proposte_e_dalle_scelte():
    # senza scelte: si confermano le proposte del server (anche una sola volta per nome ripetuto), i dubbi senza proposta restano
    assert _node(f"arCorrezioni({json.dumps(SQUADRE)}, new Map())") == [
        {"squadra": "Rossi", "testo": "Martinez", "id": 10},
        {"squadra": "Verdi", "testo": "Martinez", "id": 10},
    ]
    scelte = 'new Map([["Rossi\\u0000Martinez", "11"], ["Rossi\\u0000Esposito", "21"], ["Rossi\\u0000Pinco", "togli"], ["Verdi\\u0000Martinez", "cerca"]])'
    assert _node(f"arCorrezioni({json.dumps(SQUADRE)}, {scelte})") == [
        {"squadra": "Rossi", "testo": "Martinez", "id": 11},
        {"squadra": "Rossi", "testo": "Esposito", "id": 21},
        {"squadra": "Rossi", "testo": "Pinco", "id": None},
    ]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_tra_le_squadre_da_scegliere_ce_anche_la_tua_che_resta():
    r = {"squadre": [{"nome": "Altra"}, {"nome": "Terza"}], "mia_squadra": "Mia"}
    assert _node(f"nomiMia({json.dumps(r)})") == ["Mia", "Altra", "Terza"]
    assert _node(f"nomiMia({json.dumps({**r, 'mia_squadra': 'Altra'})})") == ["Altra", "Terza"]
    assert _node(f"nomiMia({json.dumps({**r, 'mia_squadra': None})})") == ["Altra", "Terza"]


def test_i_problemi_della_rosa_in_parole_senza_sigle():
    s = {"mancano": {"P": 1, "D": 2}, "in_piu": {"A": 1}, "senza_ruolo": 2}
    assert _node(f"arProblemi({json.dumps(s)})") == ["Manca 1 portiere", "Mancano 2 difensori", "1 attaccante in più", "2 giocatori senza ruolo"]
    r = {"squadre": [{}, {}], "sicuri": 1, "da_controllare": 1, "non_trovati": 0}
    assert _node(f"arRiassunto({json.dumps(r)})") == \
        "2 squadre: 1 giocatore riconosciuto, 1 da controllare. Sistema i dubbi qui sotto, poi conferma."


def test_il_file_e_caricato_prima_dei_suoi_utenti_ed_e_pubblico():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert html.index("anteprima.js") < html.index("primoavvio.js") < html.index("app.js")
    assert '"/anteprima.js"' in (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/anteprima.js" in rotte_account.STATICI
    assert TestClient(server.app).get("/anteprima.js").status_code == 200


def test_si_salva_solo_dopo_l_anteprima_con_le_scelte_e_l_etag():
    # le due parti che importano passano dall'anteprima, non chiamano più direttamente l'importazione
    assert "anteprimaRose(" in APP and "anteprimaRose(" in PRIMO
    assert '"/api/rose/testo"' not in APP.split("const collega = {")[1].split("squadre: () =>")[0]
    assert '"/api/rose/file"' not in PRIMO and '"/api/rose/testo"' not in PRIMO
    for pezzo in ('"/api/rose/anteprima"', "/api/rose/anteprima/file", '"/api/rose/testo"', "/api/rose/file",
                  "ifMatch: st.etag", "senzaRicarica: true", "correzioni", "mia_squadra", "e.status === 412"):
        assert pezzo in ANTEPRIMA, pezzo
    # api(): If-Match preciso, niente ricarica della pagina col 412 se lo chiede chi chiama, ETag letto dalla risposta
    assert "opzioni.ifMatch || etagDi[risorsa]" in APP and "if (!senzaRicarica)" in APP and "if (leggiEtag) leggiEtag(etag)" in APP


def test_niente_dati_dell_utente_senza_esc():
    # i nomi letti dal file arrivano dall'utente: in HTML solo con esc()
    for campo in ("${g.testo}", "${s.nome}<", "${c.nome}", "${g.avviso}", "${g.nome}"):
        assert campo not in ANTEPRIMA, campo
