"""Collaudo automatico dell'ambiente di prova dopo ogni rilascio (script/ci/collaudo_prova.py e
.github/workflows/collaudo-prova.yml, issue #511, piano dell'ondata 2, lavoro C2).

I test non aprono il browser e non toccano server veri: provano la decisione (aspettare, collaudare, saltare, in ritardo), la lettura
del riepilogo di foto.py, la lettura della versione da un server finto su 127.x e le regole di sicurezza del workflow (letto come testo)."""
import importlib.util
import json
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
PERCORSO = RADICE / "script" / "ci" / "collaudo_prova.py"
WORKFLOW = RADICE / ".github" / "workflows" / "collaudo-prova.yml"


def _modulo():
    spec = importlib.util.spec_from_file_location("collaudo_prova_in_prova", PERCORSO)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def cp():
    return _modulo()


def _testo() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job(testo: str) -> dict[str, str]:
    """I job del workflow: nome -> il suo blocco di testo."""
    corpo = testo[re.search(r"^jobs:\s*$", testo, re.M).end():]
    teste = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", corpo, re.M))
    return {m.group(1): corpo[m.end():teste[i + 1].start() if i + 1 < len(teste) else len(corpo)] for i, m in enumerate(teste)}


# =========================== decidi ===========================
def test_decidi_aspetta_se_la_prova_non_ha_ancora_la_versione_nuova(cp):
    assert cp.decidi("v1.442", "1.441", 10, set()) == "aspetta"
    assert cp.decidi("v1.442", None, 40, set()) == "aspetta"          # prova irraggiungibile, ma è presto


def test_decidi_collauda_la_versione_nuova_non_ancora_collaudata(cp):
    assert cp.decidi("v1.442", "1.442", 5, set()) == "collauda"
    assert cp.decidi("v1.442", "1.442", 5, {"1.441"}) == "collauda"


def test_decidi_salta_una_versione_gia_collaudata(cp):
    assert cp.decidi("v1.442", "1.442", 90, {"1.442"}) == "salta"
    assert cp.decidi("v1.442", "1.442", 90, {"v1.442"}) == "salta"    # con o senza «v»


def test_decidi_in_ritardo_oltre_40_minuti_senza_la_versione_nuova(cp):
    assert cp.decidi("v1.442", "1.441", 41, set()) == "in-ritardo"
    assert cp.decidi("v1.442", None, 300, set()) == "in-ritardo"


def test_decidi_prova_piu_avanti_della_release_aspetta(cp):
    """Il rilascio e la release arrivano un attimo dopo il commit: una prova già più avanti non è in ritardo."""
    assert cp.decidi("v1.442", "1.443", 300, set()) == "aspetta"
    assert cp.decidi("v1.99", "1.100", 300, set()) == "aspetta"       # confronto per numeri, non per testo


# =========================== esito ===========================
def test_esito_tutto_a_posto(cp):
    riepilogo = ("oggi 390 chiaro gravi=0 scorrimento-di-lato=no errori-console=0\n"
                 "oggi 1440 scuro gravi=0 scorrimento-di-lato=no errori-console=0\n")
    assert cp.esito(riepilogo) == (True, [])


def test_esito_con_errori_della_console_gravi_scorrimento_e_scene_rotte(cp):
    riepilogo = ("oggi 390 chiaro gravi=0 scorrimento-di-lato=no errori-console=2\n"
                 "rosa 390 scuro gravi=3 scorrimento-di-lato=sì errori-console=0\n"
                 "scheda 1440 chiaro errore=TimeoutError: Timeout 20000ms exceeded at https://prova.esempio.invalid/x\n")
    ok, problemi = cp.esito(riepilogo)
    assert ok is False
    testo = "\n".join(problemi)
    assert "oggi 390 chiaro" in testo and "2 errori della console" in testo
    assert "rosa 390 scuro" in testo and "3 violazioni gravi" in testo and "scorre di lato" in testo
    assert "scheda 1440 chiaro" in testo and "TimeoutError" in testo
    assert "https://" not in testo and "esempio.invalid" not in testo      # l'issue è pubblica: niente indirizzi


def test_esito_riepilogo_vuoto_non_passa(cp):
    ok, problemi = cp.esito("")
    assert ok is False and problemi


def test_maschera_toglie_l_indirizzo_della_prova(cp):
    testo = "errore a prova.esempio.invalid e http://prova.esempio.invalid:8001/api"
    mascherato = cp.maschera(testo, "https://prova.esempio.invalid")
    assert "esempio.invalid" not in mascherato


# =========================== indirizzi e versioni ===========================
def test_indirizzo_solo_https_o_loopback(cp):
    assert cp.indirizzo_valido("https://prova.esempio.invalid")
    assert cp.indirizzo_valido("http://127.0.0.31:8031")
    for sbagliato in ("http://prova.esempio.invalid", "ftp://127.0.0.1", "", "https://", "http://192.0.2.1:80",
                      "http://127.0.0.1.esempio.invalid", "https://a b"):
        assert not cp.indirizzo_valido(sbagliato), sbagliato


def test_versione_solo_numeri_e_punti(cp):
    assert cp.versione_valida("1.442") == "1.442"
    assert cp.versione_valida("v1.442") == "1.442"
    for sbagliata in ("1.442; rm -rf", "", None, "abc", "1..2", "$(x)"):
        assert cp.versione_valida(sbagliata) is None


def test_ultima_release_del_server_e_minuti(cp):
    adesso = datetime(2026, 11, 8, 17, 30, tzinfo=timezone.utc)
    release = [{"tagName": "build-388", "createdAt": "2026-11-08T17:20:00Z", "isDraft": False},
               {"tagName": "v1.442", "createdAt": "2026-11-08T16:50:00Z", "isDraft": False},
               {"tagName": "v1.443", "createdAt": "2026-11-08T17:25:00Z", "isDraft": True},
               {"tagName": "v1.441", "createdAt": "2026-11-08T15:30:00Z", "isDraft": False}]
    assert cp.ultima_release(release, adesso) == ("1.442", 40)
    assert cp.ultima_release([{"tagName": "build-1", "createdAt": "2026-11-08T17:20:00Z", "isDraft": False}], adesso) is None


class _ServerFinto(BaseHTTPRequestHandler):
    """Le tre rotte che servono: accedi (token nativo), stato (con il token), esci."""
    chiamate: list = []

    def _rispondi(self, codice, corpo):
        dati = json.dumps(corpo).encode()
        self.send_response(codice)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dati)))
        self.end_headers()
        self.wfile.write(dati)

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        self.chiamate.append((self.path, corpo, self.headers.get("Authorization")))
        if self.headers.get("X-Fanta") != "1":          # come il server vero: le richieste che cambiano qualcosa la vogliono
            return self._rispondi(403, {"detail": "Richiesta non permessa"})
        if self.path == "/api/account/accedi":
            if corpo.get("password") == "segreto-finto" and corpo.get("nativo") is True:
                return self._rispondi(200, {"token": "tok-finto", "utente": {"nome_utente": corpo["nome_utente"]}})
            return self._rispondi(401, {"detail": "Nome utente o password sbagliati"})
        if self.path == "/api/account/esci":
            return self._rispondi(200, {"ok": True})
        self._rispondi(404, {})

    def do_GET(self):
        self.chiamate.append((self.path, None, self.headers.get("Authorization")))
        if self.path == "/api/stato" and self.headers.get("Authorization") == "Bearer tok-finto":
            return self._rispondi(200, {"versione": "1.442"})
        self._rispondi(401, {})

    def log_message(self, *a):
        pass


@pytest.fixture
def server_finto():
    _ServerFinto.chiamate = []
    s = ThreadingHTTPServer(("127.0.0.83", 0), _ServerFinto)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.83:{s.server_address[1]}"
    s.shutdown()
    s.server_close()


def test_versione_della_prova_con_accesso_ed_uscita(cp, server_finto, capsys):
    assert cp.versione_della_prova(server_finto, "collaudo", "segreto-finto") == "1.442"
    percorsi = [c[0] for c in _ServerFinto.chiamate]
    assert percorsi == ["/api/account/accedi", "/api/stato", "/api/account/esci"]     # la sessione si chiude
    assert _ServerFinto.chiamate[2][2] == "Bearer tok-finto"
    uscita = capsys.readouterr()
    assert "segreto-finto" not in uscita.out + uscita.err and "tok-finto" not in uscita.out + uscita.err


def test_versione_della_prova_con_password_sbagliata_e_none(cp, server_finto, capsys):
    assert cp.versione_della_prova(server_finto, "collaudo", "sbagliata") is None
    uscita = capsys.readouterr()
    assert "sbagliata" not in uscita.out + uscita.err and "401" in uscita.out + uscita.err


def test_versione_della_prova_irraggiungibile_e_none(cp):
    assert cp.versione_della_prova("http://127.0.0.84:1", "collaudo", "x") is None


def test_senza_segreti_non_fa_niente(cp, tmp_path, monkeypatch):
    """Finché il proprietario non crea i segreti la corsa ogni 20 minuti resta verde e non apre issue."""
    uscita = tmp_path / "uscita.txt"
    for nome in ("PROVA_URL", "PROVA_UTENTE", "PROVA_PASSWORD"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    monkeypatch.setattr(cp, "_gh", lambda *a: pytest.fail("senza segreti non si chiede niente a GitHub"))
    assert cp.main(["decidi"]) == 0
    assert "esito=spento" in uscita.read_text(encoding="utf-8")


def test_decidi_scrive_esito_e_versione(cp, tmp_path, monkeypatch):
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    monkeypatch.setenv("PROVA_URL", "https://prova.esempio.invalid")
    monkeypatch.setenv("PROVA_UTENTE", "collaudo")
    monkeypatch.setenv("PROVA_PASSWORD", "segreto-finto")
    adesso = datetime.now(timezone.utc)
    release = [{"tagName": "v1.442", "createdAt": (adesso - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"), "isDraft": False}]
    monkeypatch.setattr(cp, "_gh", lambda *a: json.dumps(release) if a[0] == "release" else json.dumps({"total_count": 0, "artifacts": []}))
    monkeypatch.setattr(cp, "versione_della_prova", lambda url, utente, password: "1.442")
    assert cp.main(["decidi"]) == 0
    righe = uscita.read_text(encoding="utf-8").splitlines()
    assert "esito=collauda" in righe and "versione=1.442" in righe


def test_a_mano_si_collauda_anche_una_versione_gia_collaudata(cp, tmp_path, monkeypatch):
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    monkeypatch.setenv("PROVA_URL", "https://prova.esempio.invalid")
    monkeypatch.setenv("PROVA_UTENTE", "collaudo")
    monkeypatch.setenv("PROVA_PASSWORD", "segreto-finto")
    release = [{"tagName": "v1.442", "createdAt": "2026-11-08T16:50:00Z", "isDraft": False}]
    gia = {"total_count": 1, "artifacts": [{"name": "collaudo-v1.442", "expired": False}]}
    monkeypatch.setattr(cp, "_gh", lambda *a: json.dumps(release) if a[0] == "release" else json.dumps(gia))
    monkeypatch.setattr(cp, "versione_della_prova", lambda url, utente, password: None)       # indirizzo sbagliato
    assert cp.main(["decidi", "--forza"]) == 0
    righe = uscita.read_text(encoding="utf-8").splitlines()
    assert "esito=collauda" in righe and "versione=1.442" in righe


def test_comando_esito_scrive_il_risultato_mascherato(cp, tmp_path, monkeypatch):
    cartella = tmp_path / "collaudo"
    cartella.mkdir()
    (cartella / "riepilogo.txt").write_text("oggi 390 chiaro errore=Error: net::ERR at prova.esempio.invalid\n", encoding="utf-8")
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    monkeypatch.setenv("PROVA_URL", "https://prova.esempio.invalid")
    assert cp.main(["esito", str(cartella)]) == 0
    scritto = uscita.read_text(encoding="utf-8")
    assert "ok=false" in scritto and "esempio.invalid" not in scritto
    assert (cartella / "esito.txt").is_file() and "esempio.invalid" not in (cartella / "esito.txt").read_text(encoding="utf-8")


def test_comando_esito_senza_riepilogo_non_passa(cp, tmp_path, monkeypatch):
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    (tmp_path / "vuota").mkdir()
    assert cp.main(["esito", str(tmp_path / "vuota")]) == 0
    assert "ok=false" in uscita.read_text(encoding="utf-8")


# =========================== workflow ===========================
def test_segreti_solo_in_env_e_permessi_minimi():
    testo = _testo()
    job = _job(testo)
    # in alto nessun permesso di scrittura; issues: write solo nel job che segnala
    intestazione = testo[:re.search(r"^jobs:\s*$", testo, re.M).start()]
    assert re.search(r"^permissions:\s*(\{\}|\n  contents: read\s*$)", intestazione, re.M)
    assert "write" not in intestazione
    for nome, blocco in job.items():
        if nome == "segnala":
            assert "issues: write" in blocco and "secrets." not in blocco      # chi scrive le issue non vede i segreti
        else:
            assert "write" not in blocco, f"job «{nome}»: permessi di scrittura"
        assert "permissions:" in blocco, f"job «{nome}»: permessi non dichiarati"
    # ogni segreto solo come valore di una variabile d'ambiente, mai dentro uno script o un `with:`
    for riga in testo.splitlines():
        if "secrets." in riga and not riga.lstrip().startswith("#"):
            assert re.match(r"^\s+[A-Z_]+: \$\{\{ secrets\.(PROVA_URL|PROVA_UTENTE|PROVA_PASSWORD) \}\}\s*$", riga), riga
    assert "${{ secrets" not in "".join(re.findall(r"run: \|[\s\S]*?(?=\n      - |\n  \w|\Z)", testo))
    # niente pull_request: i segreti non arrivano mai a codice di altri
    eventi = testo[re.search(r"^on:\s*$", testo, re.M).end():re.search(r"^permissions:", testo, re.M).start()]
    assert "pull_request" not in eventi and "schedule:" in eventi and "workflow_dispatch:" in eventi
    assert re.search(r"cron: \"[0-9,]+ \* \* \* \*\"", eventi)
    assert "persist-credentials: false" in testo


def test_ogni_20_minuti_scene_a_390_e_1440_con_accesso_e_solo_misure():
    testo = _testo()
    cron = re.search(r"cron: \"([0-9,]+) \* \* \* \*\"", testo).group(1).split(",")
    assert len(cron) == 3 and all((int(b) - int(a)) == 20 for a, b in zip(cron, cron[1:]))
    assert "--accesso" in testo and "--solo-misure" in testo and "--larghezze 390,1440" in testo
    assert "SCHIERAXI_UTENTE: ${{ secrets.PROVA_UTENTE }}" in testo
    assert "SCHIERAXI_PASSWORD: ${{ secrets.PROVA_PASSWORD }}" in testo
    assert "--require-hashes" in testo and ".github/playwright-requisiti.txt" in testo
    assert "Collaudo della prova: v" in testo and "La prova non si aggiorna" in testo and "--label P1" in testo


def test_nessuna_foto_negli_artifact():
    testo = _testo()
    caricamenti = re.findall(r"uses: actions/upload-artifact@[0-9a-f]{40}[^\n]*\n((?:\s{8,}.*\n?)+)", testo)
    assert caricamenti, "il segno della versione collaudata è un artifact"
    for blocco in caricamenti:
        percorsi = re.search(r"path: \|?\n?((?:.*\n?)+?)(?=\s+[a-z-]+:|\Z)", blocco).group(1)
        file = [p.strip() for p in percorsi.splitlines() if p.strip()]
        assert file and all(f.endswith(("riepilogo.txt", "esito.txt")) for f in file), file
        assert "name: collaudo-v${{ needs.decidi.outputs.versione }}" in blocco
        assert "retention-days: 30" in blocco
    assert ".png" not in testo


def test_collaudo_rosso_rende_rossa_la_corsa():
    """Il comando «giornata» del coordinatore conta come fallita ogni corsa che non finisce con success, skipped o cancelled:
    un collaudo che non passa e una prova che non si aggiorna devono dare una corsa rossa; saltare una versione già collaudata no."""
    blocco = _job(_testo())["segnala"]
    passo = blocco[blocco.index("Corsa rossa"):]
    assert "exit 1" in passo
    condizione = re.search(r"if \[ (.*) \]; then\s*\n\s*echo .*\n\s*exit 1", passo)
    assert condizione, "manca il passo che esce con errore"
    assert '"$OK" = "false"' in condizione.group(1) and '"$DECISIONE" = "in-ritardo"' in condizione.group(1)
    assert "salta" not in condizione.group(1)
