"""Sentinella del ritorno di Understat (script/ci/sentinella_understat.py e .github/workflows/sentinella-understat.yml, issue #756).

Niente rete vera: le risposte arrivano da un server finto su 127.x. Si provano la decisione «dati veri o pagina», la richiesta unica
(nessun nuovo tentativo), il commento sull'issue scritto una volta sola e le regole del workflow (letto come testo)."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
PERCORSO = RADICE / "script" / "ci" / "sentinella_understat.py"
WORKFLOW = RADICE / ".github" / "workflows" / "sentinella-understat.yml"

PAGINA_FERMA = ("<!DOCTYPE html><html><head><title>Understat.com</title></head>"
                "<body><h1>We will come back soon</h1></body></html>")
DATI_FINTI = {
    "dates": [{"id": "1", "datetime": "2026-08-23 18:30:00", "isResult": False,
               "h": {"title": "Squadra Uno"}, "a": {"title": "Squadra Due"},
               "goals": {"h": None, "a": None}, "xG": {"h": None, "a": None}}],
    "players": [], "teams": {},
}


@pytest.fixture(scope="module")
def su():
    spec = importlib.util.spec_from_file_location("sentinella_understat_in_prova", PERCORSO)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


# =========================== dati veri o pagina ===========================
def test_la_pagina_di_manutenzione_non_sono_dati(su):
    assert su.dati_veri(PAGINA_FERMA.encode()) is False


def test_i_dati_della_lega_sono_dati_veri(su):
    assert su.dati_veri(json.dumps(DATI_FINTI).encode()) is True


@pytest.mark.parametrize("contenuto", [b"", b"{}", b"[]", b'{"dates": []}', b'{"error": "no"}', b"non json",
                                       b'{"dates": [{"id": "1"}]}', b'{"dates": "x"}'])
def test_risposte_strane_non_sono_dati_veri(su, contenuto):
    # un falso «è tornato» zittirebbe la sentinella per sempre: si accetta solo una lega leggibile con almeno una partita
    assert su.dati_veri(contenuto) is False


# =========================== una sola richiesta ===========================
class _Finto(BaseHTTPRequestHandler):
    codice = 200
    corpo = b""
    posizione = ""
    chiamate: list = []

    def do_GET(self):
        type(self).chiamate.append((self.path, dict(self.headers)))
        self.send_response(type(self).codice)
        if type(self).posizione:
            self.send_header("Location", type(self).posizione)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(type(self).corpo)

    def log_message(self, *a):
        pass


@pytest.fixture()
def finto():
    _Finto.chiamate = []
    s = ThreadingHTTPServer(("127.0.0.84", 0), _Finto)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.84:{s.server_address[1]}/getLeagueData/Serie_A/2026"
    s.shutdown()
    s.server_close()


@pytest.mark.parametrize("codice,corpo,esito", [
    (200, json.dumps(DATI_FINTI).encode(), "tornato"),
    (200, PAGINA_FERMA.encode(), "fermo"),
    (503, PAGINA_FERMA.encode(), "fermo"),
    (429, b"", "fermo"),
    (500, json.dumps(DATI_FINTI).encode(), "fermo"),
])
def test_controlla_fa_una_sola_richiesta(su, finto, codice, corpo, esito):
    _Finto.codice, _Finto.corpo = codice, corpo
    assert su.controlla(finto) == esito
    assert len(_Finto.chiamate) == 1                       # nessun nuovo tentativo, nemmeno su 429 e 5xx
    percorso, intestazioni = _Finto.chiamate[0]
    assert percorso == "/getLeagueData/Serie_A/2026"
    assert intestazioni.get("X-Requested-With") == "XMLHttpRequest"      # come il lettore fanta/fonti/understat.py
    assert intestazioni.get("User-Agent", "").startswith("SchieraXI/")


def test_un_reindirizzamento_non_si_segue(su, finto):
    # un 302 (o un ciclo di reindirizzamenti) farebbe più di una richiesta: vale «fermo», come un codice diverso da 200
    _Finto.codice, _Finto.corpo = 302, b""
    _Finto.posizione = "/getLeagueData/Serie_A/2026"
    try:
        assert su.controlla(finto) == "fermo"
    finally:
        _Finto.posizione = ""
    assert len(_Finto.chiamate) == 1


def test_lo_script_lanciato_come_nel_workflow_trova_il_lettore(finto, tmp_path):
    # come in GitHub Actions: un processo a sé, lanciato per percorso, con solo script/ci nel percorso dei moduli
    _Finto.codice, _Finto.corpo = 200, json.dumps(DATI_FINTI).encode()
    uscita = tmp_path / "uscita.txt"
    ambiente = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "GITHUB_OUTPUT")}
    ambiente["GITHUB_OUTPUT"] = str(uscita)
    r = subprocess.run([sys.executable, str(PERCORSO), "controlla", finto], cwd=tmp_path, env=ambiente,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert uscita.read_text(encoding="utf-8") == "esito=tornato\n"
    assert len(_Finto.chiamate) == 1


def test_controlla_senza_risposta_tace(su):
    # porta chiusa: nessuna eccezione, nessuna corsa rossa
    assert su.controlla("http://127.0.0.85:9/getLeagueData/Serie_A/2026") == "fermo"


def test_indirizzo_predefinito_e_quello_del_lettore(su):
    from fanta.fonti import understat as us
    assert su.indirizzo(2026) == us.url_lega(2026)
    assert su.TIMEOUT <= 30


# =========================== commento una volta sola ===========================
def _commento(testo, autore="github-actions"):
    return {"author": {"login": autore}, "body": testo}


def test_primo_ritorno_commenta(su):
    assert su.azioni("OPEN", []) == ["commenta"]
    assert su.azioni("OPEN", [_commento("altro")]) == ["commenta"]


def test_issue_chiusa_si_riapre(su):
    assert su.azioni("CLOSED", []) == ["commenta", "riapri"]


def test_gia_avvisato_non_fa_niente(su):
    gia = [_commento("Understat è tornato\n\n" + su.SEGNO)]
    assert su.azioni("OPEN", gia) == []
    assert su.azioni("CLOSED", gia) == []                  # chiusa dopo la riaccensione: non si riapre ogni giorno
    assert su.gia_avvisato([_commento(su.SEGNO, "github-actions[bot]")]) is True


def test_il_segno_scritto_da_altri_non_conta(su):
    # repository pubblico: chiunque può commentare l'issue, anche copiando il segno
    assert su.gia_avvisato([_commento(su.SEGNO, "qualcuno")]) is False
    assert su.gia_avvisato([{"author": None, "body": su.SEGNO}]) is False


def test_avvisa_scrive_il_commento_e_riapre(su):
    comandi = []
    su.avvisa("CLOSED", [], comandi.append, corsa="https://example.invalid/corsa")
    assert [c[:3] for c in comandi] == [["gh", "issue", "comment"], ["gh", "issue", "reopen"]]
    assert all(str(su.ISSUE) in c for c in comandi)
    testo = comandi[0][comandi[0].index("--body") + 1]
    assert testo.startswith("Understat è tornato: riaccendere la fonte") and su.SEGNO in testo


def test_avvisa_gia_avvisato_non_chiama_gh(su):
    comandi = []
    su.avvisa("CLOSED", [_commento(su.SEGNO)], comandi.append, corsa="")
    assert comandi == []


# =========================== il workflow ===========================
def _testo() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job(testo: str) -> dict[str, str]:
    corpo = testo[re.search(r"^jobs:\s*$", testo, re.M).end():]
    teste = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", corpo, re.M))
    return {m.group(1): corpo[m.end():teste[i + 1].start() if i + 1 < len(teste) else len(corpo)] for i, m in enumerate(teste)}


def test_workflow_una_volta_al_giorno_e_niente_lanci_a_mano():
    testo = _testo()
    inizio = testo[:testo.index("\njobs:")]
    cron = re.findall(r'cron:\s*"([^"]+)"', inizio)
    assert len(cron) == 1 and re.fullmatch(r"\d{1,2} \d{1,2} \* \* \*", cron[0]), cron    # un minuto e un'ora fissi
    assert "workflow_dispatch" not in inizio and "pull_request" not in inizio and "push:" not in inizio
    assert re.search(r"^permissions: \{\}$", testo, re.M)


def test_workflow_permessi_minimi_per_job():
    job = _job(_testo())
    assert set(job) == {"controlla", "avvisa"}
    assert "issues: write" not in job["controlla"] and "issues: write" in job["avvisa"]
    assert "requirements.txt" in job["controlla"] and "requirements" not in job["avvisa"]   # librerie solo dove non si scrive
    assert "needs.controlla.outputs.esito == 'tornato'" in job["avvisa"]
    for blocco in job.values():
        assert "persist-credentials: false" in blocco
        assert "timeout-minutes:" in blocco


def test_workflow_niente_espressioni_dentro_run():
    # i valori passano da variabili d'ambiente, mai dentro il testo dello script
    testo = _testo()
    blocchi = re.findall(r"^( *)run: \|\n((?:\1  .*\n|[ \t]*\n)+)", testo, re.M)
    for _, corpo in blocchi:
        assert "${{" not in corpo, corpo
    righe = re.findall(r"^\s*run: (?!\|)(.*)$", testo, re.M)
    assert righe or blocchi
    for riga in righe:
        assert "${{" not in riga, riga
