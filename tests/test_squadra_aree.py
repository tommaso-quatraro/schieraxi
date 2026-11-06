"""script/squadra/aree.py: file → area → gruppo del tetto (aree.json)."""
from __future__ import annotations

import pytest
import test_squadra_comune  # noqa: F401  (mette script/squadra nel percorso)

import aree


@pytest.mark.parametrize("file,area", [
    ("fanta/web/app.js", "web"),
    ("fanta/server.py", "server"),
    ("fanta/novita.d/x.json", "server"),
    ("script/server/aggiorna.sh", "server"),
    ("requirements.txt", "server"),
    ("requirements-dev.in", "server"),
    ("ios/Sources/Presentation/Oggi/OggiView.swift", "ios"),
    ("ios/README.md", "ios"),                       # il primo percorso che corrisponde vince
    ("sito/index.html", "sito"),
    (".github/workflows/test.yml", "ci"),
    ("script/ci/controlla_ambito.py", "ci"),
    ("script/controlli/x.py", "ci"),
    ("script/squadra/stato.py", "ci"),
    ("docs/API.md", "docs"),
    ("MAPPA.md", "docs"),
    ("tests/test_rose_csv.py", "test"),
    ("prove/qualcosa.py", "altro"),
    ("docs/sotto/cartella/immagine.png", "docs"),
])
def test_area_di_un_file(file, area):
    assert aree.area_di(file) == area


def test_md_fuori_dalla_radice_non_e_docs_per_forza():
    # «*.md» vale solo nella radice: un .md in fanta/ resta del server
    assert aree.area_di("fanta/LEGGIMI.md") == "server"


def test_gruppo_ios_vince_su_web():
    assert aree.gruppo_di(["ios/Sources/A.swift", "fanta/web/app.js"]) == "ios"


def test_gruppo_server_web_per_server_e_web():
    assert aree.gruppo_di(["fanta/server.py", "fanta/web/app.js", "tests/test_x.py"]) == "server-web"
    assert aree.gruppo_di(["sito/index.html"]) == "server-web"
    assert aree.gruppo_di([".github/workflows/test.yml"]) == "server-web"


def test_soli_documenti_e_test_non_hanno_tetto():
    assert aree.gruppo_di(["docs/API.md", "MAPPA.md"]) is None
    assert aree.gruppo_di(["tests/test_x.py", "docs/a.md"]) is None
    assert aree.gruppo_di([]) is None


def test_tetti_dei_gruppi():
    assert aree.tetto("server-web") == 4
    assert aree.tetto("ios") == 3


def test_percorsi_per_le_etichette_di_una_issue():
    tocca, non_tocca = aree.percorsi_per_etichette(["ios", "P1"])
    assert "ios/**" in tocca
    assert "tests/**" in tocca and "docs/**" in tocca     # le aree neutre si possono sempre toccare
    assert "fanta/**" in non_tocca and "ios/**" not in non_tocca


def test_percorsi_senza_etichette_di_area():
    assert aree.percorsi_per_etichette(["P2"]) == ([], [])


def test_agente_per_le_etichette():
    assert aree.agente_per_etichette(["ios"]) == "sviluppatore-ios"
    assert aree.agente_per_etichette(["web", "server"]) == "sviluppatore-web"
    assert aree.agente_per_etichette(["P3"]) is None


def test_aree_json_coerente():
    dati = aree.carica()
    nomi = [a["nome"] for a in dati["aree"]]
    assert len(nomi) == len(set(nomi))
    for g in dati["gruppi"].values():
        assert set(g["aree"]) <= set(nomi)
    assert set(dati["neutre"]) <= set(nomi)
