"""Il job «browser» di test.yml e i test di tests/browser/ (issue #619): la web provata in Chrome vero nelle pull request.

Questi test girano nella suite normale, senza browser: leggono il workflow come testo (niente PyYAML) e provano le parti di
tests/browser/conftest.py che non aprono Chrome."""
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RADICE = Path(__file__).resolve().parent.parent
TEST_YML = RADICE / ".github" / "workflows" / "test.yml"
REQUISITI = RADICE / ".github" / "browser-requisiti.txt"


def _job(nome: str) -> str:
    testo = TEST_YML.read_text(encoding="utf-8")
    corpo = testo[re.search(r"^jobs:\s*$", testo, re.M).end():]
    m = re.search(rf"^  {re.escape(nome)}:\s*$", corpo, re.M)
    assert m, f"manca il job «{nome}»"
    fine = re.search(r"^  [A-Za-z0-9_-]+:\s*$", corpo[m.end():], re.M)
    return corpo[m.start():m.end() + fine.start()] if fine else corpo[m.start():]


def _senza_commenti(blocco: str) -> str:
    return "\n".join(r for r in blocco.splitlines() if not r.lstrip().startswith("#"))


def _filtro() -> re.Pattern:
    """L'espressione del passo «Tocca la web?» (grep -E), come espressione di Python: le due sintassi qui coincidono."""
    m = re.search(r"grep -qE '([^']+)'", _job("browser"))
    assert m, "il passo «Tocca la web?» sceglie i file con grep -qE '...'"
    return re.compile(m.group(1))


def test_il_job_browser_blocca_l_unione():
    """Una schermata rotta non si unisce: «unisci» aspetta «browser» e lo vuole riuscito. Il job parte in ogni pull
    request (se la PR non tocca la web salta i passi e resta verde), quindi «riuscito» vale per tutte."""
    unisci = _senza_commenti(_job("unisci"))
    needs = re.search(r"^    needs:\s*\[([^\]]*)\]", unisci, re.M).group(1)
    assert "browser" in [n.strip() for n in needs.split(",")]
    assert "needs.browser.result == 'success'" in unisci
    assert not re.search(r"^    if:.*draft", _job("browser"), re.M), "se saltasse in bozza o altrove, «unisci» non partirebbe più"


def test_il_job_browser_gira_nelle_pr_e_a_mano_su_un_ramo_non_su_main():
    cond = re.search(r"^    if:\s*(.+)$", _job("browser"), re.M).group(1)
    assert "github.event_name == 'pull_request'" in cond
    assert "github.event_name == 'workflow_dispatch' && github.ref != 'refs/heads/main'" in cond


@pytest.mark.parametrize("file, serve", [
    ("fanta/web/app.js", True), ("fanta/web/stile.css", True), ("fanta/testi/it.json", True),
    ("tests/browser/test_prima_schermata.py", True), ("tests/strumenti/axe/axe.min.js", True),
    ("ios/fotografie/vero-prima.json", True), (".github/workflows/test.yml", True), (".github/browser-requisiti.txt", True),
    ("script/ci/server_finto.py", True),                     # il server finto su cui i test aprono la web
    ("fanta/server.py", False), ("fanta/webapp.py", False), ("docs/API.md", False), ("tests/test_server.py", False),
    ("ios/Sources/App.swift", False), (".github/workflows/test.yml.bak", False), ("script/ci/controlla_pr.py", False),
    ("script/ci/server_finto.py.bak", False),
])
def test_il_job_browser_parte_solo_se_la_pr_tocca_la_web(file, serve):
    assert bool(_filtro().search(file)) is serve, file


def test_un_file_spostato_fuori_dalla_web_conta():
    """Con le rinomine git stampa solo il percorso nuovo: spostare fanta/web/a.js in altro/a.js non farebbe partire i test."""
    assert "git diff --name-only --no-renames HEAD^1 HEAD | grep -qE" in _job("browser")


def test_il_job_browser_ha_permessi_minimi_e_niente_testo_della_pr():
    j = _job("browser")
    assert re.search(r"^    permissions:\s*\n      contents: read\s*\n    steps:", j, re.M)
    assert "persist-credentials: false" in j and "secrets." not in j
    assert "github.event.pull_request" not in j and "head_ref" not in j
    for comando in re.findall(r"run: (?:\|\n((?:          .*\n)+)|(.+))", j):
        assert "${{" not in "".join(comando), "un'espressione dentro un comando"


def test_il_job_browser_installa_l_ambiente_fissato_e_non_salta_i_test():
    j = _senza_commenti(_job("browser"))
    assert '-m pip install -q --require-hashes --only-binary=:all: -r .github/browser-requisiti.txt' in j
    assert 'BROWSER_OBBLIGATORIO: "1"' in j                # senza Playwright o Chrome: rosso, non un verde finto
    assert re.search(r"-m pytest .*-m browser --confcutdir tests/browser tests/browser", j)
    assert re.search(r"^    timeout-minutes: ([1-9]|10)\s*$", j, re.M)
    # i passi che costano si saltano quando la PR non tocca la web; il job resta verde (pronto per i «needs» di «unisci»)
    assert j.count("if: steps.decidi.outputs.serve == 'true'") == 3


def _librerie(testo: str) -> dict[str, tuple[str, set[str]]]:
    """{nome minuscolo: (versione, hash)} di un file di requisiti con «nome==versione [; condizione] \\» e righe --hash."""
    voci = {}
    for m in re.finditer(r"^([A-Za-z0-9_.-]+)==(\S+)(?: ;[^\\\n]*)? \\\n((?:\s+--hash=sha256:[0-9a-f]{64}(?: \\)?\n?)+)",
                         testo, re.M):
        voci[m.group(1).lower()] = (m.group(2), set(re.findall(r"sha256:([0-9a-f]{64})", m.group(3))))
    return voci


def test_requisiti_del_browser_fissati_e_uguali_agli_altri_ambienti():
    requisiti = REQUISITI.read_text(encoding="utf-8")
    voci = _librerie(requisiti)
    assert len(voci) == len(re.findall(r"^[A-Za-z0-9_.-]+==", requisiti, re.M)), "ogni libreria con i suoi hash"
    assert {"playwright", "pytest", "greenlet", "pyee", "pluggy"} <= set(voci)
    # Playwright come nell'ambiente della regressione visiva; pytest come nei requisiti dei test
    playwright = _librerie((RADICE / ".github" / "playwright-requisiti.txt").read_text(encoding="utf-8"))
    sviluppo = _librerie((RADICE / "requirements-dev.txt").read_text(encoding="utf-8"))
    for nome, (versione, hash_) in voci.items():
        altro = playwright.get(nome) or sviluppo.get(nome)
        assert altro, f"{nome}: non è né in playwright-requisiti.txt né in requirements-dev.txt"
        assert versione == altro[0] and hash_ <= altro[1], f"{nome}: versione o hash diversi dagli altri requisiti"
    assert "pillow" not in voci                              # le immagini qui non si confrontano


# ---------------------------------------------------------------- tests/browser/conftest.py senza browser
@pytest.fixture(scope="module")
def appoggio():
    spec = importlib.util.spec_from_file_location("conftest_browser_in_prova", RADICE / "tests" / "browser" / "conftest.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo          # le dataclass con `from __future__ import annotations` cercano qui il loro modulo
    spec.loader.exec_module(modulo)          # Playwright si importa solo nella fixture «chrome»: qui non serve
    return modulo


def test_le_tre_fasi_hanno_uno_scenario_registrato(appoggio):
    assert list(appoggio.FASI) == ["prima", "in-corso", "finita"]
    for file in appoggio.FASI.values():
        dati = json.loads((appoggio.SCENARI / file).read_text(encoding="utf-8"))
        assert dati["adesso"] and dati["risposte"], file


def test_lo_scenario_completo_aggiunge_solo_le_rotte_che_mancano(appoggio, tmp_path, monkeypatch):
    registrati = tmp_path / "registrati"
    registrati.mkdir()
    risposte = {"/api/oggi": {"giornata": 9}, "/api/avatar": {"versione": 3, "tratti": {"7": [1, 2]}}}
    (registrati / "vero-prima.json").write_text(json.dumps({"adesso": "2026-10-27T15:10:00", "risposte": risposte}),
                                                encoding="utf-8")
    (registrati / "vero-finita.json").write_text(json.dumps({"adesso": "2026-10-26T09:35:00",
                                                             "risposte": {"/api/oggi": {}}}), encoding="utf-8")
    monkeypatch.setattr(appoggio, "SCENARI", registrati)
    monkeypatch.setattr(appoggio, "RISPOSTE_IN_PIU", {"/api/avatar": {"versione": 3, "tratti": {}}})
    prima = json.loads(appoggio.scenario_completo("prima", tmp_path).read_text(encoding="utf-8"))
    assert prima["risposte"] == risposte                     # la registrazione vince
    finita = json.loads(appoggio.scenario_completo("finita", tmp_path).read_text(encoding="utf-8"))
    assert finita["risposte"] == {"/api/oggi": {}, "/api/avatar": {"versione": 3, "tratti": {}}}
    assert finita["adesso"] == "2026-10-26T09:35:00"
    assert json.loads((registrati / "vero-finita.json").read_text(encoding="utf-8"))["risposte"] == {"/api/oggi": {}}


def test_una_richiesta_annullata_non_e_fallita(appoggio):
    w = appoggio.Web(pagina=None, server=appoggio.ServerFase("prima", "http://127.0.0.30:8000", "2026-10-27T15:10:00"))
    for guasto in ("net::ERR_ABORTED", "net::ERR_CONNECTION_REFUSED", None):
        appoggio._richiesta_non_arrivata(w, SimpleNamespace(method="GET", url="http://127.0.0.30:8000/api/oggi?x=1",
                                                            failure=guasto))
    assert w.richieste_fallite == ["GET /api/oggi?x=1: net::ERR_CONNECTION_REFUSED", "GET /api/oggi?x=1: non arrivata"]
    assert appoggio._breve("https://esempio.invalid/a.png") == "https://esempio.invalid/a.png"


class _Prova:
    """Un test raccolto da pytest, finto: dove sta e i suoi segni."""
    def __init__(self, percorso: Path, segni=()):
        self.path, self.segni, self.aggiunti = percorso, set(segni), []

    def get_closest_marker(self, nome):
        return nome if nome in self.segni or any(s.name == nome for s in self.aggiunti) else None

    def add_marker(self, segno):
        self.aggiunti.append(segno)


@pytest.mark.parametrize("scelta, saltati", [("", True), ("not lento", True), ("browser", False)])
def test_i_test_del_browser_girano_solo_con_m_browser(appoggio, scelta, saltati):
    del_browser = _Prova(RADICE / "tests" / "browser" / "test_x.py")           # senza segno: lo mette conftest.py
    altrove = _Prova(RADICE / "tests" / "test_server.py")
    segnato_altrove = _Prova(RADICE / "tests" / "test_y.py", {"browser"})
    config = SimpleNamespace(getoption=lambda nome: scelta if nome == "markexpr" else None)
    appoggio.pytest_collection_modifyitems(config, [del_browser, altrove, segnato_altrove])
    assert altrove.aggiunti == []
    assert [s.name for s in del_browser.aggiunti] == (["browser", "skip"] if saltati else ["browser"])
    assert [s.name for s in segnato_altrove.aggiunti] == (["skip"] if saltati else [])
    if saltati:
        assert "-m browser" in del_browser.aggiunti[1].kwargs["reason"]


def test_il_segno_si_mette_prima_della_scelta_di_m(appoggio):
    """La scelta di `-m browser` la fa un hook di pytest sugli stessi test: il segno va messo prima, o il test sparisce."""
    assert getattr(appoggio.pytest_collection_modifyitems, "pytest_impl", {}).get("tryfirst") is True
