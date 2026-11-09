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
@pytest.fixture(scope="module")
def riga():
    """Le righe del riepilogo come le scrive davvero prove/foto_web/foto.py: se cambia il formato, questi test lo vedono."""
    spec = importlib.util.spec_from_file_location("foto_web_per_collaudo", RADICE / "prove" / "foto_web" / "foto.py")
    foto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foto)
    return foto.riga_riepilogo


def test_esito_tutto_a_posto(cp, riga):
    riepilogo = riga("oggi", 390, "chiaro", 0, False, 0) + "\n" + riga("oggi", 1440, "scuro", 0, False, 0) + "\n"
    assert cp.esito(riepilogo) == (True, [])


def test_esito_con_errori_della_console_gravi_scorrimento_e_scene_rotte(cp, riga):
    # la riga di una scena che non si apre la scrive fotografa() senza una funzione apposta: qui come la scrive lei
    riepilogo = (riga("oggi", 390, "chiaro", 0, False, 2) + "\n" + riga("rosa", 390, "scuro", 3, True, 0) + "\n"
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


@pytest.mark.parametrize("chiave", ["gravi", "scorrimento-di-lato", "errori-console"])
def test_esito_chiave_mancante_e_un_problema(cp, riga, chiave):
    """Una misura che manca non vale «zero errori»: se foto.py cambia formato, il collaudo non passa invece di tacere."""
    buona = riga("oggi", 390, "chiaro", 0, False, 0)
    monca = " ".join(p for p in buona.split() if not p.startswith(chiave + "="))
    assert monca != buona
    ok, problemi = cp.esito(monca + "\n")
    assert ok is False and any(chiave in p for p in problemi), problemi


def test_nessun_testo_fra_i_job_contiene_la_parola_dell_utente(cp, riga, tmp_path, monkeypatch):
    """GitHub scarta le uscite di un job che contengono un segreto: «collaudo» è il nome dell'account (PROVA_UTENTE). Nessun
    testo che passa fra i job (esito, dettaglio) può contenerlo, sennò l'issue P1 resta senza dettagli."""
    casi = ["", riga("oggi", 390, "chiaro", 2, True, 3) + "\n", "scheda 390 chiaro errore=Error: x\n",
            " ".join(riga("oggi", 390, "chiaro", 0, False, 0).split()[:4]) + "\n"]
    for riepilogo in casi:
        assert all("collaudo" not in p.lower() for p in cp.esito(riepilogo)[1]), riepilogo
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    (tmp_path / "vuota").mkdir()
    cp.main(["esito", str(tmp_path / "vuota")])                  # le misure non sono partite
    assert "collaudo" not in uscita.read_text(encoding="utf-8").lower()
    assert "collaudo" not in " ".join(cp.ESITI)                   # i valori di «esito» del job decidi


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


def test_artifact_solo_se_il_collaudo_e_partito(cp, riga, tmp_path, monkeypatch):
    """Senza riepilogo (Playwright non si installa, prova spenta) la versione non è stata collaudata: niente artifact
    «collaudo-v<N>», così la corsa dopo riprova. Lo dice l'uscita `fatto`, usata nell'`if:` del caricamento."""
    for nome, riepilogo, atteso in (("vuota", None, "fatto=false"), ("misurata", riga("oggi", 390, "chiaro", 0, False, 0), "fatto=true")):
        cartella = tmp_path / nome
        cartella.mkdir()
        if riepilogo is not None:
            (cartella / "riepilogo.txt").write_text(riepilogo + "\n", encoding="utf-8")
        uscita = tmp_path / f"uscita-{nome}.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
        cp.main(["esito", str(cartella)])
        assert atteso in uscita.read_text(encoding="utf-8").splitlines()
    blocco = _job(_testo())["collauda"]
    caricamento = blocco[blocco.index("uses: actions/upload-artifact@") - 300:]
    assert re.search(r"if: \$\{\{[^}]*steps\.esito\.outputs\.fatto == 'true'[^}]*\}\}", caricamento)


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
    script = PERCORSO.read_text(encoding="utf-8")                   # i testi delle issue li scrive «segnala» (#549)
    assert "Collaudo della prova: v" in script and "La prova non si aggiorna" in script and '"--label", "P1"' in script


def test_nessuna_foto_negli_artifact():
    testo = _testo()
    caricamenti = re.findall(r"uses: actions/upload-artifact@[0-9a-f]{40}[^\n]*\n((?:\s{8,}.*\n?)+)", testo)
    assert caricamenti, "il segno della versione collaudata è un artifact"
    for blocco in caricamenti:
        percorsi = re.search(r"path: \|?\n?((?:.*\n?)+?)(?=\s+[a-z-]+:|\Z)", blocco).group(1)
        file = [p.strip() for p in percorsi.splitlines() if p.strip()]
        # solo esito.txt, già mascherato: riepilogo.txt può avere l'indirizzo della prova (errori di Playwright) e gli
        # artifact di un repository pubblico li scarica chiunque
        assert file and all(f.endswith("/esito.txt") for f in file), file
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


# =========================== collaudo quotidiano (issue #549) ===========================
# La misura «giornata senza errori» chiede almeno un collaudo vero al giorno: una versione già collaudata si collauda di nuovo
# quando l'ultimo collaudo ha più di 20 ore, e un collaudo ripetuto che non passa commenta l'issue già aperta.
ADESSO = datetime(2026, 11, 9, 5, 4, tzinfo=timezone.utc)


def _iso(quando: datetime) -> str:
    return quando.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_decidi_salta_una_versione_appena_collaudata(cp):
    assert cp.decidi("v1.442", "1.442", 90, {"1.442"}, ore_dal_collaudo=1) == "salta"
    assert cp.decidi("v1.442", "1.442", 90, {"1.442"}, ore_dal_collaudo=19.9) == "salta"


def test_decidi_collauda_di_nuovo_dopo_20_ore(cp):
    assert cp.decidi("v1.442", "1.442", 2000, {"1.442"}, ore_dal_collaudo=21) == "collauda"
    assert cp.decidi("v1.442", "1.442", 2000, {"1.442"}, ore_dal_collaudo=20.1) == "collauda"


def test_decidi_collauda_una_versione_mai_collaudata(cp):
    assert cp.decidi("v1.442", "1.442", 2000, set(), ore_dal_collaudo=None) == "collauda"


def test_decidi_dopo_20_ore_non_collauda_una_prova_senza_la_versione_nuova(cp):
    """Il collaudo quotidiano vale per la versione in vigore sulla prova: una prova indietro resta «in ritardo»."""
    assert cp.decidi("v1.442", "1.441", 2000, {"1.442"}, ore_dal_collaudo=30) == "in-ritardo"


def _artifact(quando: datetime, scaduto=False) -> dict:
    return {"name": "collaudo-v1.442", "created_at": _iso(quando), "expired": scaduto}


def test_ore_dall_ultimo_collaudo_dal_segno_piu_recente(cp, monkeypatch):
    chiesti = []
    segni = {"total_count": 3, "artifacts": [_artifact(ADESSO - timedelta(hours=30)), _artifact(ADESSO - timedelta(hours=2)),
                                             _artifact(ADESSO - timedelta(minutes=30), scaduto=True)]}
    monkeypatch.setattr(cp, "_gh", lambda *a: chiesti.append(a) or json.dumps(segni))
    assert cp.ore_dall_ultimo_collaudo("1.442", ADESSO) == pytest.approx(2)
    assert "name=collaudo-v1.442" in " ".join(chiesti[0])


def test_ore_dall_ultimo_collaudo_senza_segni_e_none(cp, monkeypatch):
    soli_scaduti = {"total_count": 1, "artifacts": [_artifact(ADESSO - timedelta(hours=1), scaduto=True)]}
    for risposta in ({"total_count": 0, "artifacts": []}, soli_scaduti):
        monkeypatch.setattr(cp, "_gh", lambda *a, r=risposta: json.dumps(r))
        assert cp.ore_dall_ultimo_collaudo("1.442", ADESSO) is None


@pytest.mark.parametrize("ore_fa, atteso", [(1, "salta"), (21, "collauda"), (None, "collauda")])
def test_comando_decidi_ripete_il_collaudo_dopo_20_ore(cp, tmp_path, monkeypatch, ore_fa, atteso):
    uscita = tmp_path / "uscita.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(uscita))
    monkeypatch.setenv("PROVA_URL", "https://prova.esempio.invalid")
    monkeypatch.setenv("PROVA_UTENTE", "utente-finto")
    monkeypatch.setenv("PROVA_PASSWORD", "segreto-finto")
    monkeypatch.setattr(cp, "_adesso", lambda: ADESSO)
    release = [{"tagName": "v1.442", "createdAt": _iso(ADESSO - timedelta(hours=40)), "isDraft": False}]
    segni = [] if ore_fa is None else [_artifact(ADESSO - timedelta(hours=ore_fa))]
    monkeypatch.setattr(cp, "_gh", lambda *a: json.dumps(release) if a[0] == "release"
                        else json.dumps({"total_count": len(segni), "artifacts": segni}))
    monkeypatch.setattr(cp, "versione_della_prova", lambda url, utente, password: "1.442")
    assert cp.main(["decidi"]) == 0
    righe = uscita.read_text(encoding="utf-8").splitlines()
    assert f"esito={atteso}" in righe and "versione=1.442" in righe


# --------------------------- issue del collaudo (job «segnala») ---------------------------
class _GitHubFinto:
    """Le issue aperte e le chiamate a `gh issue ...`, come le farebbe il job «segnala»."""

    def __init__(self, aperte):
        self.aperte = list(aperte)
        self.chiamate = []

    def __call__(self, *argomenti):
        self.chiamate.append(argomenti)
        if argomenti[:2] == ("issue", "list"):
            return json.dumps(self.aperte)
        return ""

    def fatte(self, azione):
        return [c for c in self.chiamate if c[:2] == ("issue", azione)]


def _segnala(cp, monkeypatch, aperte, **ambiente):
    gh = _GitHubFinto(aperte)
    monkeypatch.setattr(cp, "_gh", gh)
    valori = {"DECISIONE": "collauda", "VERSIONE": "1.442", "PROVA": "1.442", "MINUTI": "30", "OK": "false",
              "DETTAGLIO": "oggi 390 chiaro: 2 errori della console; rosa 390 scuro: la pagina scorre di lato",
              "CORSA": "https://github.invalid/corsa/1"}
    valori.update(ambiente)
    for nome, valore in valori.items():
        monkeypatch.setenv(nome, valore)
    assert cp.main(["segnala"]) == 0
    return gh


def test_segnala_collaudo_rosso_apre_una_issue_p1(cp, monkeypatch):
    gh = _segnala(cp, monkeypatch, [{"number": 7, "title": "Collaudo della prova: v1.441 non passa"}])
    (crea,) = gh.fatte("create")
    assert crea[crea.index("--title") + 1] == "Collaudo della prova: v1.442 non passa"
    assert "P1" in crea and "ci" in crea
    corpo = crea[crea.index("--body") + 1]
    assert "- oggi 390 chiaro: 2 errori della console\n- rosa 390 scuro" in corpo and "https://github.invalid/corsa/1" in corpo
    assert not gh.fatte("comment") and not gh.fatte("close")        # l'issue di un'altra versione resta com'è


def test_segnala_collaudo_ripetuto_rosso_commenta_l_issue_della_versione(cp, monkeypatch):
    """Il collaudo quotidiano rifà la stessa versione: una sola issue per versione, i giri dopo la commentano."""
    gh = _segnala(cp, monkeypatch, [{"number": 3, "title": "La prova non si aggiorna"},
                                    {"number": 12, "title": "Collaudo della prova: v1.442 non passa"}])
    assert not gh.fatte("create")
    (commento,) = [c for c in gh.fatte("comment") if c[2] == "12"]
    assert "Ancora non passa" in commento[commento.index("--body") + 1]


def test_segnala_collaudo_che_passa_chiude_le_issue_del_collaudo(cp, monkeypatch):
    gh = _segnala(cp, monkeypatch, [{"number": 7, "title": "Collaudo della prova: v1.441 non passa"},
                                    {"number": 12, "title": "Collaudo della prova: v1.442 non passa"},
                                    {"number": 549, "title": "Collaudo della prova: almeno una volta al giorno"}], OK="true")
    assert sorted(c[2] for c in gh.fatte("close")) == ["12", "7"]
    assert not gh.fatte("create")


def test_segnala_collaudo_non_concluso_non_tocca_le_issue(cp, monkeypatch):
    gh = _segnala(cp, monkeypatch, [{"number": 12, "title": "Collaudo della prova: v1.442 non passa"}], OK="", DETTAGLIO="")
    assert not gh.fatte("create") and not gh.fatte("comment") and not gh.fatte("close")


def test_segnala_prova_in_ritardo_una_sola_issue(cp, monkeypatch):
    gh = _segnala(cp, monkeypatch, [], DECISIONE="in-ritardo", PROVA="1.441", OK="", DETTAGLIO="", MINUTI="55")
    (crea,) = gh.fatte("create")
    assert crea[crea.index("--title") + 1] == "La prova non si aggiorna" and "P2" in crea
    assert "1.441" in crea[crea.index("--body") + 1] and "55 minuti" in crea[crea.index("--body") + 1]
    gh = _segnala(cp, monkeypatch, [{"number": 3, "title": "La prova non si aggiorna"}],
                  DECISIONE="in-ritardo", PROVA="1.441", OK="", DETTAGLIO="")
    assert not gh.fatte("create") and not gh.fatte("comment")


def test_segnala_prova_aggiornata_chiude_il_ritardo(cp, monkeypatch):
    gh = _segnala(cp, monkeypatch, [{"number": 3, "title": "La prova non si aggiorna"}], DECISIONE="salta", OK="", DETTAGLIO="")
    assert [c[2] for c in gh.fatte("close")] == ["3"]


def test_segnala_versione_strana_non_finisce_nei_titoli(cp, monkeypatch):
    gh = _GitHubFinto([])
    monkeypatch.setattr(cp, "_gh", gh)
    for nome, valore in {"DECISIONE": "collauda", "VERSIONE": "1.442; rm -rf", "OK": "false", "DETTAGLIO": "x"}.items():
        monkeypatch.setenv(nome, valore)
    assert cp.main(["segnala"]) == 1
    assert not gh.fatte("create")


# --------------------------- workflow ---------------------------
def test_un_orario_fisso_al_giorno_oltre_a_quello_frequente():
    """GitHub fa partire di rado le corse «ogni 20 minuti»: un orario fisso quotidiano, poco affollato (4-6 UTC), in più."""
    testo = _testo()
    eventi = testo[:re.search(r"^permissions:", testo, re.M).start()]
    crons = re.findall(r"cron: \"([^\"]+)\"", eventi)
    assert any(re.fullmatch(r"[0-9,]+ \* \* \* \*", c) for c in crons), crons
    quotidiani = [c for c in crons if re.fullmatch(r"\d{1,2} \d{1,2} \* \* \*", c)]
    assert quotidiani, crons
    minuto, ora = (int(x) for x in quotidiani[0].split()[:2])
    assert 4 <= ora <= 6 and minuto not in (0, 30)                  # all'ora tonda GitHub è più affollato


def test_segnala_usa_lo_script_senza_segreti():
    blocco = _job(_testo())["segnala"]
    assert "collaudo_prova.py segnala" in blocco
    assert "secrets." not in blocco and "persist-credentials: false" in blocco
    assert "contents: read" in blocco and "issues: write" in blocco
