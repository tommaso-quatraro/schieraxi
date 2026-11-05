"""Gli script del server (script/server/).

Il server può avere la lingua it_IT (Latin-1), quindi ogni script che lancia Python deve forzare UTF-8, altrimenti gli accenti nei testi
degli avvisi diventano "Ã¨". Le prove con cartelle finte (una "casa" in una cartella temporanea, un repository locale al posto di GitHub,
finti `sudo`, `curl` e `flock`) controllano che l'aggiornamento automatico non tocchi mai lega/ e dati/, che installi solo se cambiano
le cartelle del server e che con --prova non scriva niente.
Il "GitHub" finto firma i commit con una chiave gpg di prova (generata una volta per sessione) e il server finto ha quella chiave
come fidata: così ogni prova passa anche dalla verifica delle firme (script/server/verifica-firme.sh)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "script" / "server"


def _trova_bash():
    # su Windows `bash` puo' essere quello di WSL (System32): meglio quello di Git
    # (usr\bin\bash.exe lascia il PATH com'e'; bin\bash.exe lo rimette in ordine e non vedrebbe i finti comandi delle prove)
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
con_bash = pytest.mark.skipif(not BASH or not shutil.which("git"), reason="servono bash e git")


# ---------------------------------------------------------------- controlli sul testo

def test_gli_script_che_usano_python_forzano_utf8():
    senza = [s.name for s in SCRIPT.glob("*.sh") if ".venv/bin/python" in s.read_text(encoding="utf-8") and "PYTHONUTF8=1" not in s.read_text(encoding="utf-8")]
    assert not senza, f"manca 'export PYTHONUTF8=1' in: {senza}"


def test_gli_script_periodici_leggono_l_ambiente_del_servizio_e_restano_prudenti():
    """aggiorna, promemoria e backup leggono dati/ambiente.env se c'è (per FANTA_MULTIUTENTE=1 come il servizio), non lo richiedono,
    hanno set -u e il lucchetto flock, e non cancellano dati (rm solo dei file temporanei dello script)."""
    for nome in ("aggiorna.sh", "promemoria.sh", "backup-serale.sh", "sentinella.sh"):
        t = (SCRIPT / nome).read_text(encoding="utf-8")
        assert '. script/server/leggi-ambiente.sh; leggi_ambiente dati/ambiente.env' in t, nome          # letto riga per riga, mai eseguito
        assert "set -u" in t and "flock -n" in t and "PYTHONUTF8=1" in t, nome
        assert t.index("ambiente.env") > t.index("cd \"$HOME/fantacalcio\""), nome        # si legge dalla cartella dell'app
        assert "rm -r" not in t and "rm -f dati" not in t, nome


def test_niente_dispositivo_ne_utente_fisso_negli_script_del_server():
    # parole a pezzi: nel repository pubblico non devono comparire per intero (la scansione dell'esportazione le blocca)
    for f in [*SCRIPT.glob("*.sh"), SCRIPT / "fantacalcio.service"]:
        t = f.read_text(encoding="utf-8")
        assert "\r" not in t, f"{f.name}: fine riga di Windows"
        for vietato in ("Rasp" + "berry", "/home" + "/pi", "script/pi", "BACKUP-PI", "Pi-hole", "Homebridge"):
            assert vietato not in t, f"{f.name}: {vietato}"
    assert "<utente>" in (SCRIPT / "fantacalcio.service").read_text(encoding="utf-8")
    assert "User=pi" not in (SCRIPT / "fantacalcio.service").read_text(encoding="utf-8")


def test_gli_script_dei_cron_del_server_ci_sono_e_script_pi_non_esiste_piu():
    """La crontab del server punta a script/server/: se uno di questi file sparisce, i cron si fermano in silenzio."""
    assert {f.name for f in SCRIPT.glob("*.sh")} >= {"aggiorna-app.sh", "aggiorna.sh", "backup-dati.sh", "backup-serale.sh",
                                                     "controllo-salute.sh", "promemoria.sh", "leggi-ambiente.sh", "pubblica-sito.sh", "sentinella.sh"}
    assert not (RADICE / "script" / "pi").exists()          # i vecchi rimandi sono stati tolti (il server non fa piu' da server)


def test_il_controllo_di_salute_usa_le_rotte_giuste():
    t = (SCRIPT / "controllo-salute.sh").read_text(encoding="utf-8")
    assert "/api/account/me" in t and "/api/salute" in t and "multiutente" in t
    assert "/api/stato" not in t.replace("# /api/stato chiede", "")        # con gli account accesi /api/stato chiede l'accesso


@con_bash
def test_tutti_gli_script_hanno_sintassi_corretta():
    for f in SCRIPT.glob("*.sh"):
        r = subprocess.run([BASH, "-n", str(f)], capture_output=True, text=True, timeout=20)
        assert r.returncode == 0, f"{f.name}: {r.stderr}"


# ---------------------------------------------------------------- _lancia: bash che si pianta

def test_lancia_riprova_se_il_comando_si_pianta_e_ripristina(tmp_path, monkeypatch):
    """Il primo tentativo si pianta (resta a dormire), viene fermato, si ripristina e il secondo riesce."""
    monkeypatch.setattr(sys.modules[__name__], "TIMEOUT_PRIMO_TENTATIVO", 3)       # il secondo ha il tempo normale: Python sotto carico parte piano
    segno, registro = tmp_path / "segno", tmp_path / "ripristini"
    codice = ("import pathlib,sys,time\ns=pathlib.Path(sys.argv[1])\n"
              "if not s.exists():\n    s.write_text('x'); time.sleep(60)\nprint('ok')")
    r = _lancia([sys.executable, "-c", codice, str(segno)], ripristina=lambda: registro.write_text("fatto"))
    assert r.returncode == 0 and r.stdout.strip() == "ok"
    assert registro.read_text() == "fatto"


def test_lancia_dopo_l_ultimo_tentativo_fallisce_con_i_processi_vivi():
    with pytest.raises(AssertionError, match="si e' piantato 2 volte"):
        _lancia([sys.executable, "-c", "import time; time.sleep(60)"], timeout=1)


def test_lancia_non_nasconde_gli_errori_dello_script():
    r = _lancia([sys.executable, "-c", "import sys; print('no', file=sys.stderr); sys.exit(3)"], timeout=30)
    assert r.returncode == 3 and "no" in r.stderr


# ---------------------------------------------------------------- ambiente finto

def _msys(p):
    """Percorso per bash: su Windows 'C:/x' diventa '/c/x' (tar prenderebbe 'C:' per un computer remoto)."""
    t = Path(p).as_posix()
    return f"/{t[0].lower()}{t[2:]}" if sys.platform == "win32" and t[1:2] == ":" else t


def _rimuovi(cartella):
    """rmtree che toglie anche i file di sola lettura di git (su Windows altrimenti restano)."""
    def _forza(funzione, percorso, _):
        try:
            os.chmod(percorso, 0o700)
            funzione(percorso)
        except OSError:
            pass
    shutil.rmtree(cartella, onerror=_forza)


def _processi_vivi():
    """Elenco breve dei processi bash/git/gpg vivi con il loro padre e il tempo di CPU: serve solo a capire, in un messaggio d'errore,
    se uno script bloccato era FERMO (CPU a zero) o solo lento. Su Windows usa PowerShell; altrove ps."""
    try:
        if sys.platform == "win32":
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(bash|sh|git|gpg|gpg-agent|dirmngr|curl|tar|sleep|flock)(\\.exe)?$' } | "
                   "ForEach-Object { '{0} padre={1} {2} cpu={3:N1}s' -f $_.ProcessId, $_.ParentProcessId, $_.Name, (($_.KernelModeTime + $_.UserModeTime) / 1e7) }"]
        else:
            cmd = ["ps", "-eo", "pid,ppid,etime,time,comm"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip().splitlines()
        return "\n".join(out[:40])
    except Exception as e:                      # pragma: no cover - solo diagnostica
        return f"(elenco processi non disponibile: {e})"


def _uccidi_albero(p):
    """Ferma il processo e i suoi figli (su Windows `taskkill /T`: bash lancia git, gpg, tar... che senza questo restano vivi)."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=30)
        p.kill()
    except Exception:                           # pragma: no cover
        pass
    try:
        p.wait(timeout=15)          # non si aspetta la fine dei tubi: un figlio sfuggito (su Windows bash non sempre lascia risalire i figli) li terrebbe aperti
    except Exception:                           # pragma: no cover
        pass


TIMEOUT_SCRIPT = 90          # secondi: oltre, uno script che di solito ne dura 1-5 e' bloccato
# Solo per le prove che vogliono un PRIMO giro piantato apposta: il suo tempo, piu' corto per non aspettare 90 secondi. I giri dopo
# sono normali e hanno sempre TIMEOUT_SCRIPT: con 20 secondi anche per loro, sul PC carico bash non arrivava in fondo (5/11/2026).
TIMEOUT_PRIMO_TENTATIVO = None


def _lancia(comando, env=None, timeout=None, tentativi=2, ripristina=None):
    """Come subprocess.run(capture_output=True, text=True), ma se il comando non finisce entro `timeout` secondi lo ferma (con i figli),
    chiama `ripristina()` (rimette com'erano i file che lo script potrebbe aver toccato) e riprova, al massimo `tentativi` volte.
    Su Windows, sotto carico, bash di Git ogni tanto si pianta: gli script qui durano 1-5 secondi, quindi 90 secondi vuol dire «bloccato».
    Se non riesce neanche all'ultimo tentativo, il messaggio dice cosa stava girando (fermo o lento)."""
    rapporto = []
    timeout = timeout or TIMEOUT_SCRIPT
    for n in range(1, tentativi + 1):
        limite = TIMEOUT_PRIMO_TENTATIVO if n == 1 and TIMEOUT_PRIMO_TENTATIVO else timeout
        p = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            out, err = p.communicate(timeout=limite)
            return subprocess.CompletedProcess(comando, p.returncode, out, err)
        except subprocess.TimeoutExpired:
            rapporto.append(f"tentativo {n}: nessuna fine dopo {limite}s. Processi vivi:\n{_processi_vivi()}")
            _uccidi_albero(p)
            if ripristina:
                ripristina()
    raise AssertionError(f"{' '.join(str(c) for c in comando[:3])} ... si e' piantato {tentativi} volte di fila\n" + "\n".join(rapporto))


# repository di prova che firmano i commit: cartella -> (cartella gpg, impronta della chiave)
_FIRMATARI: dict[str, tuple[Path, str]] = {}


def _git(cwd, *args, firma=True):
    firmatario = _FIRMATARI.get(str(cwd)) if firma else None
    opzioni, env = ["-c", "commit.gpgsign=false"], None
    if firmatario:
        # cartella gpg con percorso relativo: il git di Windows passerebbe a gpg un "C:/..." che gpg non capisce
        opzioni = ["-c", "commit.gpgsign=true", "-c", f"user.signingkey={firmatario[1]}", "-c", "gpg.program=gpg"]
        env = {**os.environ, "GNUPGHOME": os.path.relpath(firmatario[0], cwd).replace("\\", "/")}
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *opzioni, *args],
                       cwd=cwd, capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _gpg(casa, *args):
    """gpg con la cartella `casa` (lanciato da bash, dalla cartella di sopra: percorso relativo, va bene anche su Windows)."""
    casa = Path(casa)
    return subprocess.run([BASH, "-c", 'cd "$1" && shift && GNUPGHOME="$0" gpg --batch "$@"', casa.name, _msys(casa.parent), *args],
                          capture_output=True, text=True, timeout=120)


@pytest.fixture(scope="session")
def chiavi_di_prova():
    """Due chiavi gpg senza password (la fidata e un'altra), in una cartella dal percorso corto (il socket di gpg-agent ha un limite)."""
    if not BASH or not shutil.which("git"):
        pytest.skip("servono bash e git")
    casa = Path(tempfile.mkdtemp(prefix="sxg"))
    casa.chmod(0o700)
    impronte = []
    for nome in ("Fidata", "Estranea"):
        r = _gpg(casa, "--passphrase", "", "--quick-gen-key", f"{nome} <{nome.lower()}@example.invalid>", "ed25519", "sign", "never")
        if r.returncode != 0:
            shutil.rmtree(casa, ignore_errors=True)
            pytest.skip(f"gpg non riesce a creare una chiave di prova: {r.stderr[-300:]}")
        elenco = _gpg(casa, "--list-secret-keys", "--with-colons", f"{nome.lower()}@example.invalid").stdout
        impronte.append(next(r.split(":")[9] for r in elenco.splitlines() if r.startswith("fpr")))
    pubblica = _gpg(casa, "--armor", "--export", impronte[0]).stdout
    assert "BEGIN PGP PUBLIC KEY BLOCK" in pubblica
    yield {"casa": casa, "fidata": impronte[0], "estranea": impronte[1], "pubblica": pubblica}
    subprocess.run([BASH, "-c", 'cd "$1" && GNUPGHOME="$0" gpgconf --kill all', casa.name, _msys(casa.parent)], capture_output=True, timeout=30)
    shutil.rmtree(casa, ignore_errors=True)


def _scrivi(radice, relativo, testo):
    p = Path(radice) / relativo
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8", newline="\n")


def _commit(lavoro, messaggio, _firma=True, **file):
    """Commit nel finto GitHub: firmato con la chiave fidata se il repository ha un firmatario (salvo _firma=False)."""
    for rel, testo in file.items():
        _scrivi(lavoro, rel, testo)
    _git(lavoro, "add", "-A")
    _git(lavoro, "commit", "-q", "-m", messaggio, firma=_firma)
    return _git(lavoro, "rev-parse", "HEAD")


def _stub(cartella, nome, corpo):
    p = Path(cartella) / nome
    p.write_text("#!/bin/bash\n" + corpo + "\n", encoding="utf-8", newline="\n")
    p.chmod(0o755)


def _istantanea(cartella):
    """Elenco di (percorso, impronta) di tutto ciò che c'è: per confrontare prima e dopo."""
    out = {}
    for p in sorted(Path(cartella).rglob("*")):
        if p.is_file():
            out[p.relative_to(cartella).as_posix()] = hashlib.sha1(p.read_bytes()).hexdigest()
        else:
            out[p.relative_to(cartella).as_posix() + "/"] = ""
    return out


@pytest.fixture
def server(tmp_path, chiavi_di_prova):
    """Un 'server' finto: casa con ~/fantacalcio (lega e dati veri), il clone ~/schieraxi-src di un repository locale
    (commit firmati con la chiave di prova, che il server ha fra le fidate), e finti sudo/curl/flock nel PATH.
    Restituisce un oggetto con ciò che serve alle prove."""
    class S:
        pass
    s = S()
    s.casa = tmp_path / "casa"
    # il finto GitHub sta accanto alla cartella gpg (percorso corto: il git di Windows trova gpg-agent solo cosi)
    s.lavoro = Path(tempfile.mkdtemp(prefix="sxl", dir=chiavi_di_prova["casa"].parent))
    s.bin = tmp_path / "bin"
    for d in (s.casa, s.bin):
        d.mkdir()
    s.app = s.casa / "fantacalcio"
    s.stato = s.casa / ".cache" / "fantacalcio"
    s.chiamate = tmp_path / "chiamate.txt"
    s.codice_curl = tmp_path / "codice-curl.txt"
    s.codice_curl.write_text("200", encoding="utf-8")
    _stub(s.bin, "flock", "exit 0")
    _stub(s.bin, "sudo", f'echo "sudo $*" >> "{s.chiamate.as_posix()}"')
    _stub(s.bin, "curl", f'cat "{s.codice_curl.as_posix()}"')
    # repository "GitHub": storia con tutte le cartelle, commit firmati
    _git(s.lavoro, "init", "-q", "-b", "main")
    _FIRMATARI[str(s.lavoro)] = (chiavi_di_prova["casa"], chiavi_di_prova["fidata"])
    s.chiavi_prova = chiavi_di_prova
    s.chiave = s.casa / ".config" / "schieraxi" / "chiavi-firma.asc"          # la chiave fidata sul server, fuori dal repository
    _scrivi(s.chiave.parent, s.chiave.name, chiavi_di_prova["pubblica"])
    s.c1 = _commit(s.lavoro, "uno", **{
        "fanta/__init__.py": "V1", "tests/t.py": "T1", "script/server/x.sh": "S1", "requirements.txt": "r1", "requirements-dev.txt": "d1",
        "ios/a.txt": "ios1", "sito/index.html": "<html>1", "docs/d.md": "doc1", "CLAUDE.md": "CLAUDE REPO",
        "lega/rose.json": "LEGA DAL REPO", "fanta/avatar_tratti.json": "TRATTI REPO"})
    _git(s.casa, "clone", "-q", s.lavoro.as_posix(), "schieraxi-src")
    # il server: installato alla versione c1, con i SUOI file di lega e dati
    for rel, t in {"fanta/__init__.py": "V1", "fanta/avatar_tratti.json": "TRATTI SERVER", "tests/t.py": "T1", "script/server/x.sh": "S1",
                   "requirements.txt": "r1", "requirements-dev.txt": "d1", "CLAUDE.md": "CLAUDE VECCHIO",
                   "lega/rose.json": "LEGA DEL SERVER", "lega/regole.json": "REGOLE DEL SERVER", "dati/account.sqlite": "DB",
                   "dati/ambiente.env": "FANTA_MULTIUTENTE=1"}.items():
        _scrivi(s.app, rel, t)
    _scrivi(s.stato, "ultimo-rilascio", s.c1)
    # finto Python dell'app: crea ambienti (-m venv copia se stesso), finge pip (esito in esito-pip.txt) e annota gli avvisi
    s.esito_pip = tmp_path / "esito-pip.txt"
    s.esito_pip.write_text("0", encoding="utf-8")
    s.esito_libero = tmp_path / "esito-libero.txt"           # finto «python -m fanta momento-libero»: codice di uscita (0 = libero)
    s.esito_libero.write_text("0", encoding="utf-8")
    (s.app / ".venv" / "bin").mkdir(parents=True)
    _scrivi(s.app / ".venv", "QUALE", "vecchia")
    _stub(s.app / ".venv" / "bin", "python", f'''reg="{s.chiamate.as_posix()}"
case "$1" in
  -m) case "$2" in
        venv) mkdir -p "$3/bin" && cp "$0" "$3/bin/python" && echo "venv $3" >> "$reg" ;;
        pip) shift 2; echo "pip $* (con $0)" >> "$reg"; exit "$(cat "{s.esito_pip.as_posix()}")" ;;
        fanta) [ "$3" = momento-libero ] && {{ echo "momento-libero FANTA_MULTIUTENTE=${{FANTA_MULTIUTENTE:-}}" >> "$reg"; echo "partita in corso: juventus-napoli (inizio 20:45)"; exit "$(cat "{s.esito_libero.as_posix()}")"; }} ;;
      esac ;;
  -c) case "$2" in *notifiche.invia*) echo "avviso $3 | $4" >> "$reg" ;; esac ;;
esac
exit 0''')
    s.env = {**os.environ, "HOME": s.casa.as_posix(), "PATH": f"{s.bin}{os.pathsep}{os.environ['PATH']}",
             "SCHIERAXI_ATTESE_AVVIO": "2", "SCHIERAXI_PAUSA_DOPO_RITORNO": "0"}

    foto = tmp_path / "foto"

    def esegui(script, *args, **extra):
        # prima di ogni esecuzione una copia di ciò che lo script può toccare (casa e registro delle chiamate): se bash si pianta
        # (vedi _lancia) si rimette tutto com'era e si rilancia, cosi' la prova resta quella di sempre e non dipende da un blocco casuale
        if foto.exists():
            _rimuovi(foto)
        shutil.copytree(s.casa, foto)
        chiamate_prima = s.chiamate.read_bytes() if s.chiamate.exists() else None

        def ripristina():
            _rimuovi(s.casa)
            shutil.copytree(foto, s.casa)
            if chiamate_prima is None:
                s.chiamate.unlink(missing_ok=True)
            else:
                s.chiamate.write_bytes(chiamate_prima)
        return _lancia([BASH, (SCRIPT / script).as_posix(), *args], env={**s.env, **extra}, ripristina=ripristina)
    s.esegui = esegui
    s.riavvii = lambda: s.chiamate.read_text(encoding="utf-8").count("restart") if s.chiamate.exists() else 0
    s.ultimo = lambda: (s.stato / "ultimo-rilascio").read_text(encoding="utf-8").strip()
    s.log = lambda: (s.app / "dati" / "pubblicazione.log").read_text(encoding="utf-8") if (s.app / "dati" / "pubblicazione.log").exists() else ""
    s.avvisi = lambda: [r for r in (s.chiamate.read_text(encoding="utf-8") if s.chiamate.exists() else "").splitlines() if r.startswith("avviso ")]
    yield s
    _FIRMATARI.pop(str(s.lavoro), None)
    shutil.rmtree(s.lavoro, ignore_errors=True)


def _lega_e_dati_intatti(s):
    assert (s.app / "lega" / "rose.json").read_text(encoding="utf-8") == "LEGA DEL SERVER"
    assert (s.app / "lega" / "regole.json").read_text(encoding="utf-8") == "REGOLE DEL SERVER"
    assert (s.app / "dati" / "account.sqlite").read_text(encoding="utf-8") == "DB"
    assert (s.app / "dati" / "ambiente.env").read_text(encoding="utf-8") == "FANTA_MULTIUTENTE=1"
    assert (s.app / "CLAUDE.md").read_text(encoding="utf-8") == "CLAUDE VECCHIO"          # CLAUDE.md non si installa piu'
    assert (s.app / "fanta" / "avatar_tratti.json").read_text(encoding="utf-8") == "TRATTI SERVER"


# ---------------------------------------------------------------- aggiorna-app.sh

@con_bash
def test_modifiche_a_ios_sito_docs_non_installano_ne_riavviano(server):
    s = server
    c2 = _commit(s.lavoro, "solo ios sito docs", **{"ios/a.txt": "ios2"}, **{"sito/index.html": "<html>2"}, **{"docs/d.md": "doc2"})
    prima = _istantanea(s.app)
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 0
    assert s.ultimo() == c2                                   # visto, ma niente installazione
    dopo = _istantanea(s.app)
    assert {k: v for k, v in dopo.items() if k != "dati/pubblicazione.log"} == {k: v for k, v in prima.items() if k != "dati/pubblicazione.log"}
    _lega_e_dati_intatti(s)


@con_bash
def test_se_cambia_il_codice_installa_riavvia_e_non_tocca_lega_e_dati(server):
    s = server
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"}, **{"ios/a.txt": "ios2"}, **{"lega/rose.json": "LEGA DAL REPO 2"},
                 **{"CLAUDE.md": "CLAUDE REPO 2"}, **{"fanta/avatar_tratti.json": "TRATTI REPO 2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 1
    assert s.ultimo() == c2
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V2"
    assert not (s.app / "ios").exists() and not (s.app / "sito").exists() and not (s.app / "docs").exists()
    _lega_e_dati_intatti(s)
    assert "installata" in (s.app / "dati" / "pubblicazione.log").read_text(encoding="utf-8")


@con_bash
def test_se_bash_si_pianta_la_prova_riparte_da_zero_e_riesce(server, monkeypatch):
    """Il primo giro si pianta a meta' (finto `flock` che dorme dopo aver sporcato dati/): viene fermato, tutto torna com'era, il secondo giro
    fa l'installazione normale come se il primo non ci fosse stato."""
    s = server
    monkeypatch.setattr(sys.modules[__name__], "TIMEOUT_PRIMO_TENTATIVO", 20)      # solo il giro che si pianta; il secondo ha i 90 di sempre
    segno = s.chiamate.parent / "primo-giro-fatto"          # fuori da casa: il ripristino non deve cancellarlo
    _stub(s.bin, "flock", f'[ -e "{segno.as_posix()}" ] && exit 0\n: > "{segno.as_posix()}"; : > "{(s.app / "dati" / "sporco").as_posix()}"; echo "sudo blocco" >> "{s.chiamate.as_posix()}"; sleep 60')
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert not (s.app / "dati" / "sporco").exists()          # il giro bloccato e' stato annullato
    assert "blocco" not in s.chiamate.read_text(encoding="utf-8")
    assert s.riavvii() == 1 and s.ultimo() == c2
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V2"


@con_bash
def test_se_il_server_non_ha_il_file_dei_tratti_usa_quello_del_repository(server):
    s = server
    (s.app / "fanta" / "avatar_tratti.json").unlink()
    _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert (s.app / "fanta" / "avatar_tratti.json").read_text(encoding="utf-8") == "TRATTI REPO"


@con_bash
def test_se_il_file_dei_tratti_esce_dal_repository_sul_server_resta(server):
    s = server
    (s.lavoro / "fanta" / "avatar_tratti.json").unlink()
    _commit(s.lavoro, "senza tratti", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert s.riavvii() == 1
    _lega_e_dati_intatti(s)


@con_bash
def test_versione_di_prima_sconosciuta_conta_come_cambiato(server):
    """Repository nuovo (storia diversa): con le firme spente a mano installa tutto come «cambiato»."""
    s = server
    s.chiave.unlink()
    _scrivi(s.stato, "ultimo-rilascio", "0" * 40)               # storia diversa (repository nuovo)
    _commit(s.lavoro, "solo docs", **{"docs/d.md": "doc2"})
    assert s.esegui("aggiorna-app.sh", SCHIERAXI_SENZA_FIRME="1").returncode == 0
    assert s.riavvii() == 1
    _lega_e_dati_intatti(s)


# ---------------------------------------------------------------- firme (verifica-firme.sh) e librerie con hash

def _non_installata(s, nuovo):
    assert s.riavvii() == 0 and s.ultimo() == s.c1
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == nuovo          # non si riprova a ogni giro
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    _lega_e_dati_intatti(s)


@con_bash
def test_commit_senza_firma_non_si_installa(server):
    s = server
    c2 = _commit(s.lavoro, "spinto a mano, senza firma", _firma=False, **{"fanta/__init__.py": "MALIGNO"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 1, r.stderr
    assert f"il commit {c2[:7]} non ha una firma valida" in s.log()
    _non_installata(s, c2)
    assert not (s.stato / "verificato").exists()
    assert not list((s.casa / "schieraxi-src" / ".git").glob("verifica-firme*"))          # portachiavi usa e getta tolto
    # al giro dopo, stessa versione: niente da fare (nessun avviso ripetuto)
    assert s.esegui("aggiorna-app.sh").returncode == 0 and s.riavvii() == 0


@con_bash
def test_commit_senza_firma_nascosto_sotto_uno_firmato_non_si_installa(server):
    """Un commit firmato sopra uno spinto senza firma non «lava» quello di sotto: si controlla tutta la linea."""
    s = server
    c2 = _commit(s.lavoro, "senza firma", _firma=False, **{"fanta/__init__.py": "MALIGNO"})
    c3 = _commit(s.lavoro, "firmato sopra", **{"docs/d.md": "doc2"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert f"il commit {c2[:7]} non ha una firma valida" in s.log()
    _non_installata(s, c3)


@con_bash
def test_firma_di_una_chiave_non_fidata_non_si_installa(server):
    s = server
    _FIRMATARI[str(s.lavoro)] = (s.chiavi_prova["casa"], s.chiavi_prova["estranea"])
    c2 = _commit(s.lavoro, "firmato da un altro", **{"fanta/__init__.py": "MALIGNO"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert "non ha una firma valida" in s.log()
    _non_installata(s, c2)


@con_bash
def test_storia_riscritta_non_si_installa_anche_se_firmata(server):
    """Force-push di main su una versione firmata ma che non discende da quella verificata (per esempio una vecchia)."""
    s = server
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 0 and s.ultimo() == c2
    assert (s.stato / "verificato").read_text(encoding="utf-8").strip() == c2
    _git(s.lavoro, "reset", "-q", "--hard", s.c1)
    c3 = _commit(s.lavoro, "storia nuova", **{"fanta/__init__.py": "V3"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert "storia riscritta" in s.log()
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c3
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V2" and s.riavvii() == 1


@con_bash
def test_repository_nuovo_si_rifiuta_finche_non_si_usa_fidati(server):
    """Passaggio a un repository nuovo: la versione installata non c'è nella storia. Si rifiuta; dopo --fidati si installa."""
    s = server
    _scrivi(s.stato, "ultimo-rilascio", "0" * 40)
    c2 = _commit(s.lavoro, "repository nuovo", _firma=False, **{"fanta/__init__.py": "V2"})       # il primo push: senza firma
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert "non trovo la versione di partenza" in s.log() and s.riavvii() == 0
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    # un commit che non è di main non si accetta
    r = s.esegui("aggiorna-app.sh", "--fidati", "0" * 40)
    assert r.returncode == 1 and "non e' un commit di origin/main" in r.stdout
    r = s.esegui("aggiorna-app.sh", "--fidati", "origin/main")
    assert r.returncode == 0 and "fidato a mano" in r.stdout, r.stdout + r.stderr
    assert (s.stato / "verificato").read_text(encoding="utf-8").strip() == c2
    assert not (s.stato / "rifiutato").exists() and s.riavvii() == 0          # --fidati non installa
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert s.riavvii() == 1 and s.ultimo() == c2
    # da qui in poi servono di nuovo le firme
    c3 = _commit(s.lavoro, "senza firma", _firma=False, **{"fanta/__init__.py": "V3"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c3


@con_bash
def test_fidati_senza_commit_spiega_l_uso(server):
    r = server.esegui("aggiorna-app.sh", "--fidati")
    assert r.returncode == 2 and "uso:" in r.stdout


@con_bash
def test_senza_chiave_fidata_non_installa_e_avvisa_una_volta(server):
    """Se la chiave sparisce la verifica NON si spegne: niente installazione, una riga nel log e un solo avviso; torna la chiave, si installa."""
    s = server
    s.chiave.unlink()
    c2 = _commit(s.lavoro, "firmato", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert s.riavvii() == 0 and s.ultimo() == s.c1
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    assert f"versione {c2[:7]} NON installata: manca la chiave fidata" in s.log()
    assert not (s.stato / "rifiutato").exists()                  # non e' un rifiuto: con la chiave si riprova
    assert len(s.avvisi()) == 1 and "aggiornamenti fermi" in s.avvisi()[0]
    _lega_e_dati_intatti(s)
    # giri dopo: niente avvisi ne' righe nuove per la stessa versione; una versione nuova scrive una riga ma non riavvisa
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert s.log().count("manca la chiave fidata") == 1 and len(s.avvisi()) == 1
    c3 = _commit(s.lavoro, "firmato 2", **{"fanta/__init__.py": "V3"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert f"versione {c3[:7]} NON installata: manca la chiave fidata" in s.log() and len(s.avvisi()) == 1
    # --prova lo dice e non scrive
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 1 and "manca la chiave fidata" in r.stdout
    # la chiave torna: si installa (firme controllate) e lo stato si pulisce
    _scrivi(s.chiave.parent, s.chiave.name, s.chiavi_prova["pubblica"])
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert s.ultimo() == c3 and s.riavvii() == 1 and not (s.stato / "senza-chiave").exists()


@con_bash
def test_senza_chiave_si_installa_solo_con_l_interruttore_esplicito(server):
    s = server
    s.chiave.unlink()
    c2 = _commit(s.lavoro, "senza firma", _firma=False, **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh", SCHIERAXI_SENZA_FIRME="0").returncode == 1 and s.riavvii() == 0
    assert s.esegui("aggiorna-app.sh", SCHIERAXI_SENZA_FIRME="1").returncode == 0
    assert s.ultimo() == c2 and s.riavvii() == 1
    assert "verifica delle firme SPENTA a mano (SCHIERAXI_SENZA_FIRME=1)" in s.log()


@con_bash
def test_con_la_chiave_l_interruttore_non_salta_le_firme(server):
    s = server
    c2 = _commit(s.lavoro, "senza firma", _firma=False, **{"fanta/__init__.py": "MALIGNO"})
    assert s.esegui("aggiorna-app.sh", SCHIERAXI_SENZA_FIRME="1").returncode == 1
    assert f"il commit {c2[:7]} non ha una firma valida" in s.log()
    _non_installata(s, c2)


@con_bash
def test_chiave_fidata_illeggibile_non_installa(server):
    s = server
    s.chiave.write_text("non e' una chiave", encoding="utf-8")
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert "non si legge" in s.log()
    _non_installata(s, c2)


@con_bash
def test_prova_dice_se_le_firme_sono_a_posto_e_non_scrive(server):
    s = server
    _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    prima = _istantanea(s.stato)
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 0 and "firme a posto" in r.stdout and "installerei" in r.stdout
    c3 = _commit(s.lavoro, "senza firma", _firma=False, **{"fanta/__init__.py": "V3"})
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 1 and f"il commit {c3[:7]} non ha una firma valida" in r.stdout
    assert _istantanea(s.stato) == prima and s.riavvii() == 0


def _venv(s, nome=".venv"):
    p = s.app / nome / "QUALE"
    return p.read_text(encoding="utf-8") if p.exists() else ("nuova" if (s.app / nome / "bin" / "python").exists() else None)


@con_bash
def test_librerie_cambiate_ambiente_nuovo_con_gli_hash_poi_scambio(server):
    s = server
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2 --hash=sha256:abc"})
    assert s.esegui("aggiorna-app.sh").returncode == 0
    chiamate = s.chiamate.read_text(encoding="utf-8")
    assert "venv " in chiamate and ".venv.nuova" in chiamate
    assert "pip install -q --require-hashes -r" in chiamate and ".venv.nuova/bin/python" in chiamate
    assert _venv(s) == "nuova" and _venv(s, ".venv.precedente") == "vecchia" and _venv(s, ".venv.nuova") is None
    assert s.riavvii() == 1 and s.ultimo() == c2


@con_bash
def test_senza_cambi_di_librerie_l_ambiente_resta_quello(server):
    s = server
    _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert _venv(s) == "vecchia" and "venv " not in s.chiamate.read_text(encoding="utf-8")


@con_bash
def test_errore_passeggero_di_pip_riprova_e_alla_terza_volta_rinuncia(server):
    s = server
    s.esito_pip.write_text("1", encoding="utf-8")
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    for giro in (1, 2):
        assert s.esegui("aggiorna-app.sh").returncode == 1
        assert not (s.stato / "rifiutato").exists()                          # si riprova al giro dopo
        assert (s.stato / "librerie-fallite").read_text(encoding="utf-8").split() == [c2, str(giro)]
        assert _venv(s) == "vecchia" and _venv(s, ".venv.nuova") is None       # l'ambiente in uso non e' mai toccato
        assert (s.app / "requirements.txt").read_text(encoding="utf-8") == "r1"
        assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    assert len(s.avvisi()) == 1 and "rimandato" in s.avvisi()[0]                # un solo avviso per i tentativi
    assert s.esegui("aggiorna-app.sh").returncode == 1
    assert "per la 3a volta" in s.log()
    _non_installata(s, c2)
    assert len(s.avvisi()) == 2 and "annullato" in s.avvisi()[1]
    assert not (s.stato / "librerie-fallite").exists()


@con_bash
def test_errore_passeggero_di_pip_poi_l_installazione_riesce(server):
    s = server
    s.esito_pip.write_text("1", encoding="utf-8")
    c2 = _commit(s.lavoro, "librerie", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    assert s.esegui("aggiorna-app.sh").returncode == 1
    s.esito_pip.write_text("0", encoding="utf-8")
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert s.ultimo() == c2 and _venv(s) == "nuova" and s.riavvii() == 1
    assert not (s.stato / "librerie-fallite").exists()


@con_bash
def test_servizio_che_non_risponde_torna_anche_alle_librerie_di_prima(server):
    s = server
    c2 = _commit(s.lavoro, "librerie rotte", **{"requirements.txt": "r2", "fanta/__init__.py": "V2"})
    s.codice_curl.write_text("500", encoding="utf-8")
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert _venv(s) == "vecchia" and _venv(s, ".venv.precedente") is None and _venv(s, ".venv.scartata") is None
    assert (s.app / "requirements.txt").read_text(encoding="utf-8") == "r1" and s.riavvii() == 2


def test_la_chiave_di_github_nel_repository_e_quella_attesa(tmp_path):
    """Copia di riferimento della chiave con cui GitHub firma i commit che crea (web-flow, dal 16/1/2024)."""
    testo = (SCRIPT / "chiavi" / "github-web-flow.asc").read_text(encoding="utf-8")
    assert testo.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----") and "PRIVATE" not in testo
    leggimi = (SCRIPT / "LEGGIMI.md").read_text(encoding="utf-8")
    assert "968479A1AFF927E37D1A566BB5690EEEBB952194" in leggimi
    if BASH and shutil.which("git"):
        casa = tmp_path / "g"
        casa.mkdir(mode=0o700)
        r = subprocess.run([BASH, "-c", 'GNUPGHOME="$1" gpg --batch --no-autostart --show-keys --with-colons "$0" 2>/dev/null',
                            _msys(SCRIPT / "chiavi" / "github-web-flow.asc"), _msys(casa)], capture_output=True, text=True, timeout=60)
        impronte = [r.split(":")[9] for r in r.stdout.splitlines() if r.startswith("fpr")]
        if impronte:
            assert impronte == ["968479A1AFF927E37D1A566BB5690EEEBB952194"]


@con_bash
def test_prova_non_scrive_niente(server):
    s = server
    _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    prima_app, prima_stato = _istantanea(s.app), _istantanea(s.stato)
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 0, r.stderr
    assert "installerei" in r.stdout and "fanta" in r.stdout
    assert s.riavvii() == 0
    assert _istantanea(s.app) == prima_app and _istantanea(s.stato) == prima_stato


@con_bash
def test_prova_dice_che_non_installerebbe_se_cambia_solo_il_sito(server):
    s = server
    _commit(s.lavoro, "sito", **{"sito/index.html": "<html>2"})
    prima_stato = _istantanea(s.stato)
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 0 and "non installo" in r.stdout
    assert _istantanea(s.stato) == prima_stato and s.riavvii() == 0


@con_bash
def test_servizio_che_non_risponde_torna_alla_versione_di_prima(server):
    s = server
    c2 = _commit(s.lavoro, "rotta", **{"fanta/__init__.py": "V2"})
    s.codice_curl.write_text("500", encoding="utf-8")
    assert s.esegui("aggiorna-app.sh").returncode == 0
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2
    assert s.ultimo() == s.c1
    assert s.riavvii() == 2                                       # riavvio con la nuova + riavvio dopo il ritorno
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    _lega_e_dati_intatti(s)


@con_bash
def test_senza_novita_non_fa_niente(server):
    s = server
    prima = _istantanea(s.app)
    assert s.esegui("aggiorna-app.sh").returncode == 0
    senza_log = lambda d: {k: v for k, v in d.items() if k != "dati/pubblicazione.log"}
    assert senza_log(_istantanea(s.app)) == senza_log(prima) and s.riavvii() == 0




# ---------------------------------------------------------------- backup-dati.sh e pubblica-sito.sh

@con_bash
def test_backup_dati_copia_lega_e_dati_senza_chiavi_e_non_modifica_l_originale(tmp_path):
    app = tmp_path / "app"
    for rel, t in {"lega/rose.json": "ROSE", "dati/scelte.json": "SCELTE", "dati/push.json": "ISCRIZIONI", "dati/vapid.json": "CHIAVE",
                   "dati/utenti/u/x.json": "U"}.items():
        _scrivi(app, rel, t)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_, "flock", "exit 0")
    prima = _istantanea(app)
    dest = tmp_path / "copie"
    r = _lancia([BASH, (SCRIPT / "backup-dati.sh").as_posix()],
                env={**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "FANTA_RADICE": _msys(app),
                     "FANTA_BACKUP_DIR": _msys(dest), "FANTA_CACHE": _msys(tmp_path / "cache"), "FANTA_PYTHON": sys.executable},
                ripristina=lambda: [shutil.rmtree(d, ignore_errors=True) for d in (dest, tmp_path / "cache")])
    assert r.returncode == 0, r.stderr
    assert _istantanea(app) == prima
    pacchetti = list(dest.glob("dati-*.tar.gz"))
    assert len(pacchetti) == 1
    with tarfile.open(pacchetti[0]) as t:
        nomi = t.getnames()
    assert any(n.endswith("lega/rose.json") for n in nomi) and any(n.endswith("dati/scelte.json") for n in nomi)
    assert not any(n.endswith("push.json") or n.endswith("vapid.json") for n in nomi)


def _lancia_backup_dati(tmp_path, app):
    """backup-dati.sh su una cartella finta. PYTHONPATH: il pacchetto `fanta` viene da questo repository (sul server sta nella
    cartella dell'app, da cui lo script parte)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    _stub(bin_, "flock", "exit 0")
    dest, cache = tmp_path / "copie", tmp_path / "cache"
    r = _lancia([BASH, (SCRIPT / "backup-dati.sh").as_posix()],
                env={**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "FANTA_RADICE": _msys(app),
                     "FANTA_BACKUP_DIR": _msys(dest), "FANTA_CACHE": _msys(cache), "FANTA_PYTHON": sys.executable,
                     "PYTHONPATH": str(RADICE)},
                ripristina=lambda: [shutil.rmtree(d, ignore_errors=True) for d in (dest, cache)])
    return r, dest, cache


@con_bash
def test_backup_dati_salva_il_registro_delle_giornate_a_servizio_acceso_e_non_l_archivio(tmp_path):
    """Il registro delle giornate (#343) non si ricostruisce: va nella copia, preso in modo coerente mentre il servizio tiene aperto
    l'archivio (dati confermati ancora nel file -wal). L'archivio intero invece resta fuori (si rifà con `aggiorna`)."""
    import contextlib
    import sqlite3
    from fanta import archivio, registro_copia
    app = tmp_path / "app"
    _scrivi(app, "dati/scelte.json", "SCELTE")
    servizio = archivio.apri(app / "dati" / "fanta.sqlite")
    try:
        servizio.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) "
                         "VALUES ('2026-27', 9, '2026-10-25T14:50:00', 1, 1)")
        servizio.execute("INSERT INTO registro_giocatori (stagione, giornata, calciatore_id, ruolo, p_voto, mu) "
                         "VALUES ('2026-27', 9, 101, 'A', 0.873, 6.734)")
        servizio.commit()
        r, dest, _ = _lancia_backup_dati(tmp_path, app)
    finally:
        servizio.close()
    assert r.returncode == 0, r.stderr
    pacchetti = list(dest.glob("dati-*.tar.gz"))
    assert len(pacchetti) == 1
    with tarfile.open(pacchetti[0]) as t:
        nomi = t.getnames()
        assert not any("fanta.sqlite" in n for n in nomi)
        registro = [n for n in nomi if n.endswith("dati/registro-giornate.json")]
        assert len(registro) == 1, nomi
        estratto = tmp_path / "registro-giornate.json"
        estratto.write_bytes(t.extractfile(registro[0]).read())
    nuovo = tmp_path / "rifatto" / "fanta.sqlite"
    assert registro_copia.importa(estratto, nuovo) == \
        {"registro_giornate": (1, 0), "registro_giocatori": (1, 0)}
    with contextlib.closing(sqlite3.connect(nuovo)) as db:
        assert db.execute("SELECT stagione, giornata, calciatore_id, ruolo, p_voto, mu FROM registro_giocatori").fetchall() == \
            [("2026-27", 9, 101, "A", 0.873, 6.734)]


@con_bash
def test_backup_dati_senza_registro_leggibile_non_salva_la_copia_e_lo_scrive_nel_log(tmp_path):
    """Archivio illeggibile: niente copia di quella notte (e niente rotazione, così restano le copie vecchie con il registro buono)."""
    app = tmp_path / "app"
    _scrivi(app, "dati/scelte.json", "SCELTE")
    (app / "dati" / "fanta.sqlite").write_bytes(b"non sono un database " * 300)
    r, dest, cache = _lancia_backup_dati(tmp_path, app)
    assert r.returncode == 1
    assert not list(dest.glob("dati-*.tar.gz"))
    assert "registro delle giornate" in (cache / "backup-dati.log").read_text(encoding="utf-8")


@con_bash
def test_pubblica_sito_copia_solo_sito_aggiorna_toglie_i_file_spariti(server, tmp_path):
    s = server
    _commit(s.lavoro, "sito", **{"sito/CNAME": "esempio.it"}, **{"sito/vecchio.html": "vecchio"})
    sito = tmp_path / "www"
    _scrivi(sito, ".git/HEAD", "vecchia copia")
    _scrivi(sito, "stantio.html", "da togliere")
    _scrivi(sito, ".well-known/acme/x", "certbot")
    extra = {"SCHIERAXI_SITO_DIR": sito.as_posix(), "FANTA_CACHE": (tmp_path / "c").as_posix()}
    r = s.esegui("pubblica-sito.sh", **extra)
    assert r.returncode == 0, r.stderr
    assert (sito / "index.html").read_text(encoding="utf-8") == "<html>1"
    assert not (sito / "CNAME").exists() and not (sito / "stantio.html").exists()
    assert not (sito / ".git").exists()                            # la vecchia copia git esce dalla cartella servita...
    assert (tmp_path / "c" / "sito-vecchio-git" / "HEAD").exists()           # ...ma resta al sicuro per tornare indietro
    assert (sito / ".well-known" / "acme" / "x").read_text(encoding="utf-8") == "certbot"          # file che non vengono da sito/ restano
    assert not (sito / "fanta").exists() and not (sito / "ios").exists()
    # seconda volta: sito/ non e' cambiato, non riscrive
    (sito / "index.html").write_text("TOCCATO", encoding="utf-8")
    assert s.esegui("pubblica-sito.sh", **extra).returncode == 0
    assert (sito / "index.html").read_text(encoding="utf-8") == "TOCCATO"
    # se sito/ cambia, aggiorna
    _commit(s.lavoro, "sito 2", **{"sito/index.html": "<html>2"}, **{"sito/vecchio.html": "x"})
    assert s.esegui("pubblica-sito.sh", **extra).returncode == 0
    assert (sito / "index.html").read_text(encoding="utf-8") == "<html>2"


@con_bash
@pytest.mark.skipif(sys.platform == "win32", reason="i link simbolici su Windows chiedono privilegi")
def test_pubblica_sito_con_link_simbolico_sposta_il_link(server, tmp_path):
    s = server
    vecchia = tmp_path / "www-vecchia"
    vecchia.mkdir()
    (vecchia / "index.html").write_text("vecchio", encoding="utf-8")
    link = tmp_path / "www"
    link.symlink_to(vecchia)
    r = s.esegui("pubblica-sito.sh", SCHIERAXI_SITO_DIR=link.as_posix(), FANTA_CACHE=(tmp_path / "c").as_posix())
    assert r.returncode == 0, r.stderr
    assert link.is_symlink() and (link / "index.html").read_text(encoding="utf-8") == "<html>1"
    assert (vecchia / "index.html").read_text(encoding="utf-8") == "vecchio"          # la cartella di prima non e' toccata


# ---------------------------------------------------------------- permessi, fetch fallito, cartelle mancanti

def _modo(p):
    return os.stat(p).st_mode & 0o777


@con_bash
@pytest.mark.skipif(sys.platform == "win32", reason="i permessi (stat -c %a) esistono solo su Linux/macOS")
def test_pubblica_sito_lascia_cartelle_755_e_file_644_anche_con_umask_stretta(server, tmp_path):
    """Con umask 077 (cron) la copia diventava 700/600 e nginx dava 403."""
    s = server
    _commit(s.lavoro, "sito con cartelle", **{"sito/css/stile.css": "a{}", "sito/img/logo.svg": "<svg/>"})
    sito = tmp_path / "www"
    sito.mkdir()
    sito.chmod(0o755)
    env = {**s.env, "SCHIERAXI_SITO_DIR": sito.as_posix(), "FANTA_CACHE": (tmp_path / "c").as_posix()}
    r = subprocess.run([BASH, "-c", 'umask 077; exec /bin/bash "$0"', (SCRIPT / "pubblica-sito.sh").as_posix()],
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    stat = subprocess.run(["stat", "-c", "%a %n", str(sito), str(sito / "css"), str(sito / "index.html"), str(sito / "css" / "stile.css")],
                          capture_output=True, text=True).stdout.split("\n")
    assert [riga.split()[0] for riga in stat if riga] == ["755", "755", "644", "644"], stat
    # con il link simbolico: cartella nuova leggibile da tutti
    vecchia = tmp_path / "www-vecchia"
    (vecchia / ".well-known").mkdir(parents=True)
    (vecchia / ".well-known" / "t").write_text("c", encoding="utf-8")
    link = tmp_path / "www2"
    link.symlink_to(vecchia)
    env["SCHIERAXI_SITO_DIR"] = link.as_posix()
    env["FANTA_CACHE"] = (tmp_path / "c2").as_posix()
    r = subprocess.run([BASH, "-c", 'umask 077; exec /bin/bash "$0"', (SCRIPT / "pubblica-sito.sh").as_posix()],
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    nuova = link.resolve()
    assert nuova != vecchia.resolve()
    assert _modo(nuova) == 0o755 and _modo(nuova / "index.html") == 0o644 and _modo(nuova / "css") == 0o755
    assert (nuova / ".well-known" / "t").exists()


@con_bash
def test_fetch_fallito_non_installa_e_scrive_nel_log(server, tmp_path):
    s = server
    _git(s.casa / "schieraxi-src", "remote", "set-url", "origin", (tmp_path / "non-esiste").as_posix())
    prima = {k: v for k, v in _istantanea(s.app).items() if k != "dati/pubblicazione.log"}
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0
    assert "git fetch non riuscito" in (s.app / "dati" / "pubblicazione.log").read_text(encoding="utf-8")
    assert s.riavvii() == 0 and s.ultimo() == s.c1
    assert {k: v for k, v in _istantanea(s.app).items() if k != "dati/pubblicazione.log"} == prima


@con_bash
def test_cartella_del_server_mancante_nel_repository_non_installa(server):
    s = server
    (s.lavoro / "tests" / "t.py").unlink()
    c2 = _commit(s.lavoro, "senza tests", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 1
    assert "non contiene: tests" in (s.app / "dati" / "pubblicazione.log").read_text(encoding="utf-8")
    assert s.riavvii() == 0 and s.ultimo() == s.c1
    assert (s.stato / "rifiutato").read_text(encoding="utf-8").strip() == c2          # non si riprova a ogni giro
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    _lega_e_dati_intatti(s)


@con_bash
def test_prova_con_un_clone_nuovo_indicato_da_ambiente(server, tmp_path):
    s = server
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    nuovo = tmp_path / "clone-nuovo"
    _git(tmp_path, "clone", "-q", s.lavoro.as_posix(), nuovo.as_posix())
    prima_stato = _istantanea(s.stato)
    r = s.esegui("aggiorna-app.sh", "--prova", SCHIERAXI_SRC=nuovo.as_posix())
    assert r.returncode == 0 and "installerei" in r.stdout and c2[:7] in r.stdout
    assert _istantanea(s.stato) == prima_stato


# ---------------------------------------------------------------- controllo-salute.sh con un finto server

_PYTHON3 = True
con_python3 = pytest.mark.skipif(not _PYTHON3, reason="serve python3 nella shell (sul server e su GitHub c'e')")


class _Finto:
    def __init__(self, rotte):
        self.rotte, self.posts = rotte, []
        finto = self

        class H(BaseHTTPRequestHandler):
            def _r(self):
                codice, corpo = finto.rotte.get(self.path.split("?")[0], (502, ""))
                dati = (corpo if isinstance(corpo, str) else json.dumps(corpo)).encode()
                self.send_response(codice)
                self.send_header("Content-Length", str(len(dati)))
                self.end_headers()
                self.wfile.write(dati)

            def do_GET(self):
                self._r()

            def do_POST(self):
                finto.posts.append((self.path, self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()))
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def chiudi(self):
        self.server.shutdown()
        self.server.server_close()


def _controllo(tmp_path, rotte, invio=False):
    f = _Finto(rotte)
    try:
        casa = tmp_path / "casa-c"
        (casa / ".config" / "schieraxi").mkdir(parents=True, exist_ok=True)
        (casa / ".config" / "schieraxi" / "canale").write_text("canale-segreto-xyz", encoding="utf-8")
        env = {**os.environ, "HOME": _msys(casa), "CONTROLLO_URL": f.url, "CONTROLLO_DIR": _msys(tmp_path / "stato-c"),
               "CONTROLLO_SENZA_CERTIFICATO": "1", "CONTROLLO_PAUSA": "0"}
        if sys.platform == "win32":          # su Windows `python3` non c'e': si usa il Python delle prove
            (tmp_path / "bin3").mkdir(exist_ok=True)
            _stub(tmp_path / "bin3", "python3", f'exec "{_msys(sys.executable)}" "$@"')
            env["PATH"] = f"{tmp_path / 'bin3'}{os.pathsep}{env['PATH']}"
        if invio:
            env["CONTROLLO_NTFY_URL"] = f.url + "/ntfy"
        else:
            env["CONTROLLO_SENZA_INVIO"] = "1"
        r = _lancia([BASH, (SCRIPT / "controllo-salute.sh").as_posix()], env=env,
                    ripristina=lambda: shutil.rmtree(tmp_path / "stato-c", ignore_errors=True))
        return r, f
    finally:
        f.chiudi()


ME_OK = (200, {"multiutente": True, "utente": None})


@con_bash
def test_controllo_con_gateway_che_da_502_non_dice_app_aperta(tmp_path):
    r, _ = _controllo(tmp_path, {})          # ogni rotta risponde 502
    assert r.returncode == 0, r.stderr
    assert "aperta senza accesso" not in r.stdout
    assert (tmp_path / "stato-c" / "fallimenti").read_text(encoding="utf-8").strip() == "1"          # solo «non raggiungibile»


@con_bash
@pytest.mark.parametrize("codice", [502, 503, 429])
def test_formazione_con_errori_di_gateway_non_e_app_aperta(tmp_path, codice):
    r, _ = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (codice, "x"), "/api/salute": (429, "")})
    assert "aperta senza accesso" not in r.stdout


@con_bash
def test_formazione_200_senza_login_e_app_aperta(tmp_path):
    r, _ = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (200, "{}"), "/api/salute": (429, "")})
    assert "aperta senza accesso" in r.stdout


@con_bash
def test_account_me_200_senza_multiutente_e_app_aperta(tmp_path):
    r, _ = _controllo(tmp_path, {"/api/account/me": (200, {"multiutente": False}), "/api/formazione": (401, "x"), "/api/salute": (429, "")})
    assert "aperta senza accesso" in r.stdout


@con_bash
def test_app_chiusa_correttamente_non_da_allarmi_di_sicurezza(tmp_path):
    r, _ = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (401, "x"), "/api/salute": (429, "")})
    assert "aperta senza accesso" not in r.stdout and "database" not in r.stdout


@con_bash
def test_salute_503_o_ok_false_da_allarme_sui_dati(tmp_path):
    r, _ = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (401, "x"),
                                 "/api/salute": (503, {"ok": False, "ultimo_aggiornamento": None})})
    assert "SchieraXI: dati" in r.stdout and "non si legge" in r.stdout


@con_bash
@con_python3
def test_salute_con_ultimo_aggiornamento_null_da_allarme(tmp_path):
    r, _ = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (401, "x"),
                                 "/api/salute": (200, {"ok": True, "ultimo_aggiornamento": None})})
    assert "Nessun aggiornamento" in r.stdout


@con_bash
@con_python3
def test_il_canale_ntfy_viaggia_nel_corpo_e_non_negli_argomenti(tmp_path):
    r, f = _controllo(tmp_path, {"/api/account/me": ME_OK, "/api/formazione": (200, "{}"), "/api/salute": (429, "")}, invio=True)
    assert r.returncode == 0, r.stderr
    assert f.posts and "canale-segreto-xyz" in f.posts[0][1] and f.posts[0][0] == "/ntfy"
    t = (SCRIPT / "controllo-salute.sh").read_text(encoding="utf-8")
    assert "--data-binary @-" in t and '-d "$json"' not in t


# ---------------------------------------------------------------- comandi di rete bloccati

def _git_che_si_pianta(s):
    reale = shutil.which("git", path=os.environ["PATH"])
    _stub(s.bin, "git", f'[ "$1" = fetch ] && exec sleep 60\nexec "{Path(reale).as_posix()}" "$@"')


def test_aggiorna_app_con_fetch_bloccato_si_ferma_e_lo_scrive(server):
    s = server
    _git_che_si_pianta(s)
    r = s.esegui("aggiorna-app.sh", SCHIERAXI_TIMEOUT_GIT="2")
    assert r.returncode == 0
    assert "git fetch interrotto dopo 2s" in s.log()
    assert s.riavvii() == 0 and s.ultimo() == s.c1


def test_pubblica_sito_con_fetch_bloccato_si_ferma_e_lo_scrive(server, tmp_path):
    s = server
    _git_che_si_pianta(s)
    r = s.esegui("pubblica-sito.sh", SCHIERAXI_TIMEOUT_GIT="1", SCHIERAXI_PAUSA_FETCH="0", SCHIERAXI_SITO_DIR=(tmp_path / "sito").as_posix(),
                 FANTA_CACHE=(tmp_path / "c").as_posix())
    assert r.returncode == 0
    assert "git fetch interrotto dopo 1s" in (tmp_path / "c" / "pubblica-sito.log").read_text(encoding="utf-8")


def test_promemoria_avvisa_una_volta_dopo_tre_salti_per_il_blocco(server):
    s = server
    salta = 'for a in "$@"; do [ "$a" = -s ] && exit 1; done; exit 0'
    _stub(s.bin, "flock", salta)
    for n in range(1, 5):
        r = s.esegui("promemoria.sh", SCHIERAXI_ATTESA_BLOCCO="1")
        assert r.returncode == 0
        assert len(s.avvisi()) == (0 if n < 3 else 1)
    _stub(s.bin, "flock", "exit 0")
    s.esegui("promemoria.sh")
    assert not (s.stato / "salute-saltata").exists()
    _stub(s.bin, "flock", salta)
    for _ in range(3):
        s.esegui("promemoria.sh", SCHIERAXI_ATTESA_BLOCCO="1")
    assert len(s.avvisi()) == 2


# ---------------------------------------------------------------- niente installazione durante le partite (fanta/libero.py)

@con_bash
def test_partita_in_corso_rimanda_l_installazione_e_lo_scrive_una_volta(server):
    s = server
    s.esito_libero.write_text("3", encoding="utf-8")
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    for _ in range(2):
        r = s.esegui("aggiorna-app.sh")
        assert r.returncode == 0, r.stderr
    assert s.riavvii() == 0 and s.ultimo() == s.c1
    assert (s.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    assert s.log().count("rimandata: partite in corso (partita in corso: juventus-napoli") == 1      # una riga sola per versione
    assert "momento-libero FANTA_MULTIUTENTE=1" in s.chiamate.read_text(encoding="utf-8")          # con le variabili del servizio
    s.esito_libero.write_text("0", encoding="utf-8")                                                # partita finita
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 1 and s.ultimo() == c2 and "fine del rimando" in s.log()
    assert not (s.stato / "rimandata").exists()
    _lega_e_dati_intatti(s)


@con_bash
def test_controllo_guasto_o_comando_che_non_esiste_ancora_si_installa(server):
    s = server
    s.esito_libero.write_text("2", encoding="utf-8")                  # argparse: comando sconosciuto nella versione installata
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 1 and s.ultimo() == c2


@con_bash
def test_emergenza_con_il_file_installa_subito_e_il_file_sparisce(server):
    s = server
    s.esito_libero.write_text("3", encoding="utf-8")
    (s.stato / "installa-subito").write_text("", encoding="utf-8")
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 1 and s.ultimo() == c2 and "forzata" in s.log()
    assert not (s.stato / "installa-subito").exists()


@con_bash
def test_emergenza_con_la_variabile(server):
    s = server
    s.esito_libero.write_text("3", encoding="utf-8")
    c2 = _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh", SCHIERAXI_INSTALLA_SUBITO="1")
    assert r.returncode == 0, r.stderr
    assert s.riavvii() == 1 and s.ultimo() == c2


@con_bash
def test_in_prova_dice_che_rimanderebbe(server):
    s = server
    s.esito_libero.write_text("3", encoding="utf-8")
    _commit(s.lavoro, "codice", **{"fanta/__init__.py": "V2"})
    r = s.esegui("aggiorna-app.sh", "--prova")
    assert r.returncode == 0, r.stderr
    assert "[prova] rimanderei" in r.stdout and s.riavvii() == 0 and s.ultimo() == s.c1
