"""L'ambiente di prova sullo stesso server (script/server/prova/, piano 2026-11-08-ondata-2, lavoro C1).

Una seconda copia dell'app con dati inventati, accanto alla produzione, con un UTENTE DI SISTEMA SUO (`schieraxi-prova`, casa
`/srv/schieraxi-prova`): niente permessi sui file della produzione, clone del codice suo, dati di calcio da una cartella di scambio
in cui la produzione esporta ogni notte una copia senza gli esiti della sentinella.
Le prove usano due "case" finte in cartelle temporanee, una per utente (produzione installata; prova vuota o preparata), un "GitHub"
locale e finti sudo, curl e flock: niente server vero, niente rete, niente finestre. Controllano soprattutto:
- senza SCHIERAXI_ISTANZA `aggiorna-app.sh` fa quello di sempre (stesse cartelle, servizio, porta, blocco, attesa delle partite);
- la prova scrive solo nella sua casa, non usa mai clone, blocco o dati della produzione, e rifiuta i collegamenti simbolici sui file
  che scrive nella cartella dati (che scrive anche il suo servizio).
Le prove con i collegamenti simbolici si saltano dove il sistema non li crea (Windows senza privilegio): girano in CI su Linux.
Le firme dei commit qui non si provano (servirebbe gpg): lo fanno i test di `test_script_server.py`, con lo stesso script."""
import hashlib
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SERVER = RADICE / "script" / "server"
PROVA = SERVER / "prova"
AGGIORNA = SERVER / "aggiorna-app.sh"
UTENTE_PROVA = "schieraxi-prova"
CASA_PROVA = "/srv/schieraxi-prova"
SCAMBIO = "/srv/schieraxi-scambio"
CHIAVE_PROVA = "/etc/schieraxi-prova/chiavi-firma.asc"          # di root: la prova non la può cambiare


def _trova_bash():
    # su Windows `bash` puo' essere quello di WSL: meglio quello di Git (usr\bin\bash.exe lascia il PATH com'e')
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
con_bash = pytest.mark.skipif(not BASH or not shutil.which("git"), reason="servono bash e git")


# ---------------------------------------------------------------- aiuti

def _scrivi(radice, relativo, testo):
    p = Path(radice) / relativo
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8", newline="\n")
    return p


def _stub(cartella, nome, corpo):
    p = _scrivi(cartella, nome, "#!/bin/bash\n" + corpo + "\n")
    p.chmod(0o755)
    return p


def _istantanea(cartella):
    """(percorso, impronta) di tutto ciò che c'è: per confrontare prima e dopo."""
    out = {}
    cartella = Path(cartella)
    if not cartella.exists():
        return out
    for p in sorted(cartella.rglob("*")):
        rel = p.relative_to(cartella).as_posix()
        out[rel] = hashlib.sha1(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink() else "/"
    return out


def _git(cwd, *args):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _commit(lavoro, messaggio, **file):
    for rel, testo in file.items():
        _scrivi(lavoro, rel, testo)
    _git(lavoro, "add", "-A")
    _git(lavoro, "commit", "-q", "-m", messaggio)
    return _git(lavoro, "rev-parse", "HEAD")


def _lancia(comando, env, timeout=90):
    """subprocess.run con un tempo massimo; un secondo tentativo se bash di Git (Windows, sotto carico) si pianta."""
    for tentativo in (1, 2):
        try:
            return subprocess.run(comando, capture_output=True, text=True, env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            if tentativo == 2:
                raise


def _ambiente(casa, bin_=None, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SCHIERAXI_")}
    env["HOME"] = Path(casa).as_posix()
    if bin_:
        env["PATH"] = f"{bin_}{os.pathsep}{os.environ['PATH']}"
    env.update(extra)
    return env


def _casa_per_bash(casa):
    """Come bash scrive la casa (su Windows Git bash la converte in /c/... o /tmp/...)."""
    return _lancia([BASH, "-c", 'printf %s "$HOME"'], _ambiente(casa)).stdout


def _configurazione(casa, **extra):
    r = _lancia([BASH, AGGIORNA.as_posix(), "--configurazione"], _ambiente(casa, **extra))
    assert r.returncode == 0, r.stderr
    return dict(riga.split("=", 1) for riga in r.stdout.splitlines())


def _archivio_finto(percorso, calciatori=100, controlli=5, wal=True):
    """Un fanta.sqlite inventato: calciatori (dati di calcio) e controlli (esiti della sentinella, parlano degli utenti)."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(percorso)
    if wal:
        db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE calciatori (id INTEGER PRIMARY KEY, nome TEXT)")
    db.execute("CREATE TABLE controlli (stagione TEXT, nome TEXT, esito TEXT, dettaglio TEXT, PRIMARY KEY (stagione, nome))")
    db.executemany("INSERT INTO calciatori VALUES (?, ?)", [(i, f"Giocatore Finto {i}") for i in range(calciatori)])
    db.executemany("INSERT INTO controlli VALUES ('2026-27', ?, 'errore', 'utente 3')", [(f"c{i}",) for i in range(controlli)])
    db.commit()
    db.close()


def _conta(percorso, tabella):
    db = sqlite3.connect(f"{Path(percorso).resolve().as_uri()}?mode=ro", uri=True)
    try:
        return db.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]
    finally:
        db.close()


def _collega(bersaglio, collegamento):
    """Un collegamento simbolico, oppure la prova si salta (Windows senza privilegio: gira in CI su Linux)."""
    Path(collegamento).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(bersaglio, collegamento)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"questo sistema non crea collegamenti simbolici ({e}): la prova gira in CI su Linux")


def _unita(testo):
    """Le righe CHIAVE=valore di un file di systemd, per sezione (una chiave può ripetersi: lista)."""
    sezioni, sezione = {}, None
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith(("#", ";")):
            continue
        if riga.startswith("[") and riga.endswith("]"):
            sezione = sezioni.setdefault(riga[1:-1], {})
            continue
        chiave, _, valore = riga.partition("=")
        sezione.setdefault(chiave.strip(), []).append(valore.strip())
    return sezioni


def _percorsi(valori):
    """Valori di InaccessiblePaths, ReadWritePaths... : più percorsi per riga, il '-' davanti vuol dire «se c'è»."""
    return [p.lstrip("-+") for v in valori for p in v.split()]


# ---------------------------------------------------------------- le due case finte del server

@pytest.fixture
def server(tmp_path):
    """- produzione: casa dell'utente del server con ~/fantacalcio (lega vera, account, archivio in WAL), stato, clone ~/schieraxi-src;
    - prova: casa vuota dell'utente schieraxi-prova (come /srv/schieraxi-prova appena creata);
    - scambio: la cartella in cui la produzione esporta la copia dell'archivio per la prova;
    - un "GitHub" locale con due commit (c1 verificato dalla produzione, c2 più nuovo) e un commit su un ramo che non è main;
    - finti sudo, curl e flock che annotano le chiamate, e un finto Python (crea ambienti, finge pip, dice «partita in corso» a
      momento-libero, passa i file .py al Python vero)."""
    if not BASH or not shutil.which("git"):
        pytest.skip("servono bash e git")

    class S:
        pass
    s = S()
    s.produzione, s.casa_prova, s.scambio = tmp_path / "produzione", tmp_path / "prova", tmp_path / "scambio"
    s.bin, s.github = tmp_path / "bin", tmp_path / "github"
    for d in (s.produzione, s.casa_prova, s.scambio, s.bin, s.github):
        d.mkdir()
    s.chiamate = tmp_path / "chiamate.txt"
    reg = s.chiamate.as_posix()
    _stub(s.bin, "flock", "exit 0")
    _stub(s.bin, "sudo", f'echo "sudo $*" >> "{reg}"')
    _stub(s.bin, "curl", f'echo "curl $*" >> "{reg}"; echo 200')
    python_vero = Path(sys.executable).as_posix()
    s.python = _stub(s.bin, "python-finto", f'''reg="{reg}"
case "$1" in
  -m) case "$2" in
        venv) mkdir -p "$3/bin" && cp "$0" "$3/bin/python" && echo "venv $3" >> "$reg" ;;
        pip) shift 2; echo "pip $*" >> "$reg" ;;
        fanta) echo "fanta $3" >> "$reg"; [ "$3" = momento-libero ] && {{ echo "partita in corso"; exit 3; }} ;;
      esac ;;
  -c) case "$2" in *notifiche.invia*) echo "avviso $3" >> "$reg" ;; *novita.json*) echo "1.0" ;; *) exec "{python_vero}" "$@" ;; esac ;;
  *.py) exec "{python_vero}" "$@" ;;
esac
exit 0''')
    # GitHub finto: le cartelle del server, la lega d'esempio, le cose che il server non installa e i veri file della prova
    file = {"fanta/__init__.py": "V1", "fanta/novita.json": '[{"versione": "1.0"}]', "tests/t.py": "T1",
            "script/server/x.sh": "S1", "requirements.txt": "r1", "requirements-dev.txt": "d1",
            "lega/esempio/regole.json": "REGOLE ESEMPIO", "lega/esempio/rose.json": "ROSE ESEMPIO",
            "lega/esempio/immagini/a.txt": "IMG", "ios/a.txt": "ios1", "sito/index.html": "<html>1", "docs/d.md": "doc1"}
    for f in PROVA.iterdir():
        if f.is_file():
            file[f"script/server/prova/{f.name}"] = f.read_text(encoding="utf-8")
    _git(s.github, "init", "-q", "-b", "main")
    s.c1 = _commit(s.github, "uno", **file)
    s.c2 = _commit(s.github, "due", **{"fanta/__init__.py": "V2"})
    _git(s.github, "switch", "-q", "-c", "altro")
    s.fuori_da_main = _commit(s.github, "fuori da main", **{"fanta/__init__.py": "FUORI"})
    _git(s.github, "switch", "-q", "main")
    # produzione installata alla versione c1, con i SUOI dati (che la prova non deve mai toccare)
    s.app = s.produzione / "fantacalcio"
    s.stato = s.produzione / ".cache" / "fantacalcio"
    for rel, t in {"fanta/__init__.py": "V1", "tests/t.py": "T1", "script/server/x.sh": "S1", "requirements.txt": "r1",
                   "requirements-dev.txt": "d1", "lega/rose.json": "LEGA VERA", "dati/account.sqlite": "ACCOUNT VERI",
                   "dati/ambiente.env": "FANTA_MULTIUTENTE=1\nFANTA_MAIL=smtp\n"}.items():
        _scrivi(s.app, rel, t)
    _archivio_finto(s.app / "dati" / "fanta.sqlite")
    for nome, t in {"ultimo-rilascio": s.c1, "verificato": s.c1, "blocco-pubblicazione": ""}.items():
        _scrivi(s.stato, nome, t)
    (s.app / ".venv" / "bin").mkdir(parents=True)
    shutil.copy(s.python, s.app / ".venv" / "bin" / "python")
    _git(s.produzione, "clone", "-q", s.github.as_posix(), "schieraxi-src")
    # la prova: casa sua, programmi suoi
    s.prova = s.casa_prova / "app"
    s.stato_prova = s.casa_prova / ".cache" / "schieraxi-prova"
    s.clone_prova = s.casa_prova / "schieraxi-src"
    comuni = {"SCHIERAXI_SCAMBIO": s.scambio.as_posix(), "SCHIERAXI_ATTESE_AVVIO": "2"}
    s.env_produzione = _ambiente(s.produzione, s.bin, **comuni)
    s.env_prova = _ambiente(s.casa_prova, s.bin, SCHIERAXI_REPO=s.github.as_posix(), SCHIERAXI_PYTHON=s.python.as_posix(), **comuni)
    s.registro = lambda: s.chiamate.read_text(encoding="utf-8") if s.chiamate.exists() else ""

    def foto_produzione():
        """Tutto ciò che la prova non deve cambiare: la casa intera della produzione (codice, dati, stato, clone). I file di appoggio
        di sqlite (-shm, -wal) li crea o li tocca chiunque legga un archivio WAL (sul server il servizio li tiene sempre aperti):
        l'archivio deve restare identico e il -wal vuoto."""
        wal = s.app / "dati" / "fanta.sqlite-wal"
        assert not wal.exists() or wal.stat().st_size == 0
        return {k: v for k, v in _istantanea(s.produzione).items() if not k.endswith(("fanta.sqlite-shm", "fanta.sqlite-wal"))}
    s.foto_produzione = foto_produzione

    def prova_installata(commit):
        """La prova come la lascia prepara-prova.sh: clone suo, codice di `commit`, ambiente Python, dati suoi, stato suo."""
        _git(s.casa_prova, "clone", "-q", s.github.as_posix(), "schieraxi-src")
        for rel, t in {"fanta/__init__.py": "V1", "tests/t.py": "T1", "script/server/x.sh": "S1", "requirements.txt": "r1",
                       "requirements-dev.txt": "d1", "dati/LEGGIMI": "dati della prova"}.items():
            _scrivi(s.prova, rel, t)
        (s.prova / ".venv" / "bin").mkdir(parents=True)
        shutil.copy(s.python, s.prova / ".venv" / "bin" / "python")
        _scrivi(s.stato_prova, "ultimo-rilascio", commit)
    s.prova_installata = prova_installata

    def esportata(calciatori=80):
        """La copia che la produzione lascia nella cartella di scambio (già senza controlli, non in WAL)."""
        _archivio_finto(s.scambio / "fanta.sqlite", calciatori=calciatori, controlli=0, wal=False)
    s.esportata = esportata
    return s


def _aggiorna_prova(s, *argomenti):
    return _lancia([BASH, AGGIORNA.as_posix(), *argomenti], {**s.env_prova, "SCHIERAXI_ISTANZA": "prova", "SCHIERAXI_SENZA_FIRME": "1"})


# ---------------------------------------------------------------- aggiorna-app.sh: le istanze

@con_bash
@pytest.mark.parametrize("istanza", [None, ""])
def test_senza_istanza_tutto_come_oggi(tmp_path, istanza):
    casa = tmp_path / "casa"
    casa.mkdir()
    c = _configurazione(casa, **({} if istanza is None else {"SCHIERAXI_ISTANZA": istanza}))
    h = _casa_per_bash(casa)
    assert c == {"DEST": f"{h}/fantacalcio", "STATO": f"{h}/.cache/fantacalcio", "SERVIZIO": "fantacalcio", "PORTA": "8000",
                 "ATTENDE_PARTITE": "1", "SRC": f"{h}/schieraxi-src", "BLOCCO": f"{h}/.cache/fantacalcio/blocco-pubblicazione",
                 "CHIAVI": f"{h}/.config/schieraxi/chiavi-firma.asc"}
    assert not any(casa.iterdir())                                  # --configurazione non crea niente


@con_bash
def test_prova_tutto_nelle_sue_cartelle(tmp_path):
    casa = tmp_path / "casa-prova"
    casa.mkdir()
    c = _configurazione(casa, SCHIERAXI_ISTANZA="prova")
    h = _casa_per_bash(casa)
    assert c == {"DEST": f"{h}/app", "STATO": f"{h}/.cache/schieraxi-prova", "SERVIZIO": "schieraxi-prova", "PORTA": "8001",
                 "ATTENDE_PARTITE": "0", "SRC": f"{h}/schieraxi-src", "BLOCCO": f"{h}/.cache/schieraxi-prova/blocco-pubblicazione",
                 "CHIAVI": CHIAVE_PROVA}
    assert not any(casa.iterdir())


@con_bash
def test_la_chiave_delle_firme_della_prova_sta_fuori_dalla_sua_casa(tmp_path):
    """La prova possiede la sua casa: una chiave lì dentro la potrebbe cambiare (e installarsi codice senza firma). La sua chiave
    sta in /etc/schieraxi-prova, di root; si cambia solo con SCHIERAXI_CHIAVI, come per la produzione."""
    casa = tmp_path / "casa-prova"
    casa.mkdir()
    c = _configurazione(casa, SCHIERAXI_ISTANZA="prova")
    assert c["CHIAVI"] == CHIAVE_PROVA and not c["CHIAVI"].startswith(_casa_per_bash(casa))
    assert _configurazione(casa, SCHIERAXI_ISTANZA="prova", SCHIERAXI_CHIAVI="/altra/chiave.asc")["CHIAVI"] == "/altra/chiave.asc"


@con_bash
def test_produzione_usa_lo_stesso_blocco_e_lo_stesso_clone_di_sito_e_controlli(tmp_path):
    """Il blocco va con il clone. La produzione tiene ~/.cache/fantacalcio/blocco-pubblicazione, lo stesso di pubblica-sito.sh (stesso
    clone ~/schieraxi-src: un solo git fetch e una sola verifica delle firme alla volta), di promemoria.sh e di sentinella.sh (non
    controllano l'app mentre si riavvia). Se aggiorna-app.sh cambiasse blocco, due git fetch sullo stesso clone si bloccherebbero
    a vicenda e i controlli darebbero falsi allarmi durante i riavvii."""
    casa = tmp_path / "casa"
    casa.mkdir()
    c = _configurazione(casa)
    h = _casa_per_bash(casa)
    assert c["BLOCCO"] == f"{h}/.cache/fantacalcio/blocco-pubblicazione" and c["SRC"] == f"{h}/schieraxi-src"
    sito = (SERVER / "pubblica-sito.sh").read_text(encoding="utf-8")
    assert 'SRC="${SCHIERAXI_SRC:-$HOME/schieraxi-src}"' in sito
    assert 'STATO="${FANTA_CACHE:-$HOME/.cache/fantacalcio}"' in sito and 'exec 6>"$STATO/blocco-pubblicazione"' in sito
    for nome in ("promemoria.sh", "sentinella.sh"):
        assert 'exec 7>"$HOME/.cache/fantacalcio/blocco-pubblicazione"' in (SERVER / nome).read_text(encoding="utf-8"), nome
    assert 'exec 7>"$BLOCCO"' in AGGIORNA.read_text(encoding="utf-8")


@con_bash
def test_prova_ha_clone_e_blocco_suoi_mai_quelli_della_produzione(server):
    """Con l'utente separato la prova non condivide il clone con la produzione: ne ha uno suo nella sua casa, e quindi anche il suo
    blocco e la sua cartella di verifica delle firme (.git/verifica-firme nel suo clone). Niente in comune, niente da aspettare."""
    prod = _configurazione(server.produzione)
    prova = _configurazione(server.casa_prova, SCHIERAXI_ISTANZA="prova")
    h = _casa_per_bash(server.casa_prova)
    for chiave in ("DEST", "STATO", "SRC", "BLOCCO"):
        assert prova[chiave].startswith(h + "/"), chiave
        assert prova[chiave] != prod[chiave], chiave
    assert prova["SRC"] == f"{h}/schieraxi-src"


@con_bash
@pytest.mark.parametrize("argomenti", [[], ["--prova"], ["--configurazione"]])
def test_prova_non_gira_nella_casa_della_produzione(server, argomenti):
    """Nella casa della produzione la prova userebbe il clone della produzione con un altro blocco: si rifiuta, senza scrivere niente."""
    prima = server.foto_produzione()
    r = _lancia([BASH, AGGIORNA.as_posix(), *argomenti], {**server.env_produzione, "SCHIERAXI_ISTANZA": "prova"})
    assert r.returncode == 2
    assert UTENTE_PROVA in r.stderr
    assert server.foto_produzione() == prima
    assert server.registro() == ""


@con_bash
@pytest.mark.parametrize("argomenti", [[], ["--prova"], ["--configurazione"]])
def test_istanza_sconosciuta_si_ferma(server, argomenti):
    prima = _istantanea(server.produzione)
    r = _lancia([BASH, AGGIORNA.as_posix(), *argomenti], {**server.env_produzione, "SCHIERAXI_ISTANZA": "collaudo"})
    assert r.returncode == 2
    assert "SCHIERAXI_ISTANZA" in r.stderr and "prova" in r.stderr
    assert _istantanea(server.produzione) == prima                 # nessun file scritto, nemmeno blocchi o log
    assert server.registro() == ""


# ---------------------------------------------------------------- aggiorna-app.sh: l'aggiornamento della prova

@con_bash
def test_prova_installa_solo_nelle_sue_cartelle_senza_aspettare_le_partite_e_senza_avvisi(server):
    """Versione nuova (c2) con una partita in corso: la prova la prende dal SUO clone, la installa subito, riavvia SOLO il suo
    servizio, chiede la salute sulla sua porta, non manda avvisi; la casa della produzione (clone compreso) resta identica."""
    s = server
    s.prova_installata(s.c1)
    produzione = s.foto_produzione()
    r = _aggiorna_prova(s)
    assert r.returncode == 0, r.stderr
    assert (s.prova / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V2"
    assert (s.stato_prova / "ultimo-rilascio").read_text(encoding="utf-8").strip() == s.c2
    assert (s.stato_prova / "blocco-pubblicazione").exists()                       # il suo blocco, accanto al suo stato
    assert "installata" in (s.prova / "dati" / "pubblicazione.log").read_text(encoding="utf-8")
    reg = s.registro()
    assert "sudo systemctl restart schieraxi-prova" in reg
    assert "restart fantacalcio" not in reg
    assert "127.0.0.1:8001" in reg and "127.0.0.1:8000" not in reg
    assert "momento-libero" not in reg                             # la prova non aspetta la fine delle partite
    assert "avviso " not in reg                                    # nessun avviso sul canale della produzione
    assert s.foto_produzione() == produzione
    assert not (s.prova / "ios").exists() and not (s.prova / "sito").exists()


@con_bash
def test_prova_non_preparata_non_crea_niente(server):
    r = _aggiorna_prova(server)
    assert r.returncode == 0, r.stderr
    assert "prepara-prova.sh" in r.stderr
    assert not any(server.casa_prova.iterdir())
    assert server.registro() == ""


@con_bash
@pytest.mark.parametrize("nome", ["pubblicazione.log", "pubblicazione.log.tmp"])
def test_prova_con_il_log_collegato_non_scrive_niente(server, tmp_path, nome):
    """La cartella dati la scrive anche il servizio della prova: se al posto del log c'è un collegamento simbolico (verso il codice,
    per esempio), lo script che gira fuori dal recinto non ci scrive e non installa."""
    s = server
    s.prova_installata(s.c1)
    bersaglio = _scrivi(tmp_path, "bersaglio.txt", "INTATTO")
    _collega(bersaglio, s.prova / "dati" / nome)
    r = _aggiorna_prova(s)
    assert r.returncode == 1
    assert "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert (s.prova / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"
    assert "restart" not in s.registro()


@con_bash
def test_in_produzione_la_partita_in_corso_rimanda_ancora(server):
    """Contro-prova: lo stesso finto Python con la produzione rimanda l'installazione (cosi' la prova sopra dimostra che la prova
    salta l'attesa, non che il finto Python non la chiede)."""
    r = _lancia([BASH, AGGIORNA.as_posix()], {**server.env_produzione, "SCHIERAXI_SENZA_FIRME": "1"})
    assert r.returncode == 0, r.stderr
    assert "fanta momento-libero" in server.registro()
    assert "restart" not in server.registro()
    assert (server.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"


# ---------------------------------------------------------------- servizio systemd della prova

def test_unita_della_prova_gira_con_il_suo_utente_e_non_vede_la_produzione():
    testo = (PROVA / "schieraxi-prova.service").read_text(encoding="utf-8")
    u = _unita(testo)
    s = u["Service"]
    app = f"{CASA_PROVA}/app"
    assert s["User"] == [UTENTE_PROVA] and s["Group"] == [UTENTE_PROVA]          # mai l'utente della produzione
    assert "<utente>" not in testo and "/home/" not in testo
    assert s["WorkingDirectory"] == [app]
    assert s["ExecStart"] == [f"{app}/.venv/bin/python -m fanta server --host 127.0.0.1 --porta 8001"]
    assert "EnvironmentFile" not in s                              # le variabili stanno qui, in righe Environment=
    assert "PYTHONDONTWRITEBYTECODE=1" in s["Environment"]
    # recinto: niente /home (la produzione), sola lettura dappertutto tranne i suoi dati, niente chiave, clone, stato e scambio
    assert s["ProtectSystem"] == ["strict"]
    assert s["ProtectHome"] == ["tmpfs"]
    assert _percorsi(s["ReadWritePaths"]) == [f"{app}/dati"]
    invisibili = _percorsi(s["InaccessiblePaths"])
    for p in (CHIAVE_PROVA.rsplit("/", 1)[0], f"{CASA_PROVA}/.cache", f"{CASA_PROVA}/schieraxi-src", SCAMBIO):
        assert p in invisibili, p
    assert s["ProtectProc"] == ["invisible"]                       # i processi degli altri utenti non si vedono
    assert s["PrivateTmp"] == ["yes"] and s["NoNewPrivileges"] == ["yes"]
    assert s["IPAddressDeny"] == ["any"] and s["IPAddressAllow"] == ["localhost"]     # niente collegamenti verso internet
    assert s["UMask"] == ["0077"]
    assert s["MemoryMax"] == ["500M"] and s["CPUWeight"] == ["20"] and s["Nice"] == ["19"]
    codice = "\n".join(r for r in testo.splitlines() if not r.lstrip().startswith("#"))     # i commenti possono citare la produzione
    assert "0.0.0.0" not in codice and "8000" not in codice
    assert u["Install"]["WantedBy"] == ["multi-user.target"]


def test_nessun_file_di_variabili_dove_scrive_la_prova():
    """systemd legge un EnvironmentFile come root, PRIMA del recinto, e segue i collegamenti simbolici: un file nella casa della prova
    (che la prova possiede) o nella cartella di scambio lo potrebbe far puntare al file delle variabili della produzione, con i suoi
    segreti, e poi leggerlo dal proprio ambiente. Nessun EnvironmentFile lì, oggi o domani."""
    for f in PROVA.glob("*.service"):
        for riga in f.read_text(encoding="utf-8").splitlines():
            chiave, _, valore = riga.strip().partition("=")
            if chiave.strip() == "EnvironmentFile":
                for p in _percorsi([valore]):
                    assert not p.startswith((CASA_PROVA, SCAMBIO, "/home")), f"{f.name}: {riga.strip()}"
    assert not (PROVA / "ambiente-prova.env.esempio").exists()     # le variabili stanno solo nel file del servizio


def test_variabili_della_prova_spengono_lavori_posta_e_fonti():
    righe = _unita((PROVA / "schieraxi-prova.service").read_text(encoding="utf-8"))["Service"]["Environment"]
    for r in righe:                      # una variabile per riga, senza virgolette né spazi (nessun dubbio su come le legge systemd)
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*=[^\s'\"$`;\\]*", r), r
    valori = dict(r.split("=", 1) for r in righe)
    assert len(valori) == len(righe), "una variabile scritta due volte"
    attesi = {"FANTA_MULTIUTENTE": "1", "FANTA_REGISTRAZIONE": "invito", "FANTA_MAIL": "spento", "FANTA_PIANIFICATORE": "0",
              "FANTA_REGISTRO_GIORNATE": "0", "FANTA_COPIA_SCADENZA": "0", "FANTA_RISCALDA": "0", "FANTA_LIVE": "0"}
    for k, v in attesi.items():
        assert valori.get(k) == v, k
    # ogni fonte di dati esterna spenta per nome, anche quelle che verranno: una fonte nuova senza la sua riga fa fallire la prova
    sys.path.insert(0, str(RADICE))
    from fanta import fonti_attive
    for fonte in fonti_attive.FONTI:
        assert valori.get(f"FANTA_FONTE_{fonte.upper()}") == "0", fonte
    assert valori.get("FANTA_FONTI_PREDEFINITO", "") != "1"
    # nessun canale di avvisi, niente posta vera, nessun segreto
    for vietata in ("FANTA_CANALE_AVVISI", "FANTA_NTFY_CANALE", "FANTA_RESEND_KEY", "FANTA_GOOGLE_CLIENT_SECRET"):
        assert vietata not in valori
    assert not [k for k in valori if k.startswith("FANTA_SMTP_")]
    # come in produzione dietro nginx: indirizzo vero di chi chiede e https riconosciuto
    assert valori.get("FANTA_PROXY") == "1"


# ---------------------------------------------------------------- copia dell'archivio (copia_archivio.py)

def _modulo_copia():
    spec = importlib.util.spec_from_file_location("copia_archivio_prova", PROVA / "copia_archivio.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _impronta(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def _lavori(cartella):
    return sorted(p.name for p in Path(cartella).iterdir() if ".nuovo" in p.name)


def test_copia_archivio_senza_controlli_e_atomica(tmp_path):
    """Origine in WAL con il servizio acceso (una connessione aperta) e destinazione con il suo archivio aperto: la copia ha i dati
    di calcio e non gli esiti della sentinella, l'origine resta identica, chi legge la destinazione vede l'archivio nuovo e sano."""
    m = _modulo_copia()
    origine = tmp_path / "produzione" / "dati" / "fanta.sqlite"
    destinazione = tmp_path / "prova" / "dati" / "fanta.sqlite"
    _archivio_finto(origine, calciatori=120, controlli=7)
    _archivio_finto(destinazione, calciatori=3, controlli=0)
    servizio = sqlite3.connect(origine)
    servizio.execute("SELECT COUNT(*) FROM calciatori").fetchone()
    lettore_prova = sqlite3.connect(destinazione)
    lettore_prova.execute("SELECT COUNT(*) FROM calciatori").fetchone()
    prima = _impronta(origine)
    try:
        tolti = m.copia(origine, destinazione)
    finally:
        servizio.close()
    assert tolti == 7
    assert lettore_prova.execute("SELECT COUNT(*) FROM calciatori").fetchone()[0] == 120
    lettore_prova.close()
    assert _conta(destinazione, "calciatori") == 120
    assert _conta(destinazione, "controlli") == 0
    assert _conta(origine, "controlli") == 7                     # l'origine non perde niente
    assert _impronta(origine) == prima
    db = sqlite3.connect(destinazione)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"         # l'archivio della prova resta in WAL
    db.close()
    assert _lavori(destinazione.parent) == []


def test_copia_archivio_nuova_senza_wal(tmp_path):
    """La copia nuova (quella nella cartella di scambio) non è in WAL: la prova la legge in sola lettura da una cartella in cui non
    può scrivere, e un archivio WAL lì avrebbe bisogno dei file di appoggio."""
    m = _modulo_copia()
    origine = tmp_path / "o.sqlite"
    _archivio_finto(origine, calciatori=5, controlli=2)
    destinazione = tmp_path / "scambio" / "fanta.sqlite"
    destinazione.parent.mkdir()
    m.copia(origine, destinazione)
    db = sqlite3.connect(destinazione)
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    db.close()
    assert sorted(p.name for p in destinazione.parent.iterdir()) == ["fanta.sqlite"]
    assert _conta(destinazione, "controlli") == 0


@pytest.mark.parametrize("guasto", ["non e' un archivio", None])
def test_copia_archivio_non_riuscita_lascia_la_destinazione_com_era(tmp_path, guasto):
    m = _modulo_copia()
    origine = tmp_path / "produzione" / "fanta.sqlite"
    if guasto is not None:
        _scrivi(origine.parent, origine.name, guasto * 2000)
    destinazione = tmp_path / "prova" / "fanta.sqlite"
    _archivio_finto(destinazione, calciatori=3, controlli=0)
    with pytest.raises(m.CopiaNonRiuscita):
        m.copia(origine, destinazione)
    assert _conta(destinazione, "calciatori") == 3
    assert _lavori(destinazione.parent) == []


@pytest.mark.parametrize("quale", ["fanta.sqlite", "fanta.sqlite-wal", "fanta.sqlite-shm", "fanta.sqlite-journal"])
def test_copia_archivio_rifiuta_un_collegamento_al_posto_della_destinazione(tmp_path, quale):
    """La cartella dati della prova la scrive anche il suo servizio: un collegamento simbolico al posto dell'archivio o dei suoi file
    di appoggio farebbe scrivere la copia (che gira fuori dal recinto) da un'altra parte. Si rifiuta, senza toccare il bersaglio."""
    m = _modulo_copia()
    origine = tmp_path / "o.sqlite"
    _archivio_finto(origine, calciatori=5, controlli=0)
    dati = tmp_path / "dati"
    dati.mkdir()
    if quale != "fanta.sqlite":
        _archivio_finto(dati / "fanta.sqlite", calciatori=3, controlli=0, wal=False)
    bersaglio = _scrivi(tmp_path, "codice.py", "CODICE")
    _collega(bersaglio, dati / quale)
    with pytest.raises(m.CopiaNonRiuscita, match="collegamento"):
        m.copia(origine, dati / "fanta.sqlite")
    assert bersaglio.read_text(encoding="utf-8") == "CODICE"


def test_copia_archivio_rifiuta_una_cartella_collegata(tmp_path):
    m = _modulo_copia()
    origine = tmp_path / "o.sqlite"
    _archivio_finto(origine, calciatori=5, controlli=0)
    altrove = tmp_path / "altrove"
    altrove.mkdir()
    _collega(altrove, tmp_path / "dati")
    with pytest.raises(m.CopiaNonRiuscita, match="collegamento"):
        m.copia(origine, tmp_path / "dati" / "fanta.sqlite")
    assert not any(altrove.iterdir())


def test_copia_archivio_non_scrive_attraverso_un_file_di_lavoro_collegato(tmp_path):
    """Un collegamento piazzato dove andrà il file di lavoro (fanta.sqlite.nuovo) non si segue: si toglie il collegamento (non il
    bersaglio) e il file di lavoro si crea nuovo."""
    m = _modulo_copia()
    origine = tmp_path / "o.sqlite"
    _archivio_finto(origine, calciatori=5, controlli=0)
    dati = tmp_path / "dati"
    bersaglio = _scrivi(tmp_path, "codice.py", "CODICE")
    _collega(bersaglio, dati / "fanta.sqlite.nuovo")
    m.copia(origine, dati / "fanta.sqlite")
    assert bersaglio.read_text(encoding="utf-8") == "CODICE"
    assert _conta(dati / "fanta.sqlite", "calciatori") == 5
    assert _lavori(dati) == []


def test_copia_archivio_da_riga_di_comando(tmp_path):
    origine = tmp_path / "o.sqlite"
    destinazione = tmp_path / "d" / "fanta.sqlite"
    _archivio_finto(origine, calciatori=4, controlli=2)
    destinazione.parent.mkdir()
    r = subprocess.run([sys.executable, str(PROVA / "copia_archivio.py"), str(origine), str(destinazione)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert _conta(destinazione, "calciatori") == 4 and _conta(destinazione, "controlli") == 0
    r = subprocess.run([sys.executable, str(PROVA / "copia_archivio.py"), str(tmp_path / "manca.sqlite"), str(destinazione)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and r.stderr.strip()
    assert _conta(destinazione, "calciatori") == 4


def test_copia_archivio_usa_solo_la_libreria_standard():
    testo = (PROVA / "copia_archivio.py").read_text(encoding="utf-8")
    moduli = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z_][\w]*)", testo, re.M))
    assert moduli <= {"__future__", "os", "sqlite3", "sys", "pathlib"}, moduli


# ---------------------------------------------------------------- esporta-archivio-prova.sh (utente della produzione)

@con_bash
def test_esporta_con_prova_non_scrive_niente(server):
    prima = server.foto_produzione(), _istantanea(server.scambio)
    r = _lancia([BASH, (PROVA / "esporta-archivio-prova.sh").as_posix(), "--prova"], server.env_produzione)
    assert r.returncode == 0, r.stderr
    assert "fanta.sqlite" in r.stdout
    assert (server.foto_produzione(), _istantanea(server.scambio)) == prima


@con_bash
def test_esporta_mette_nello_scambio_i_soli_dati_di_calcio(server):
    produzione = server.foto_produzione()
    r = _lancia([BASH, (PROVA / "esporta-archivio-prova.sh").as_posix()], server.env_produzione)
    assert r.returncode == 0, r.stdout + r.stderr
    copia = server.scambio / "fanta.sqlite"
    assert _conta(copia, "calciatori") == 100 and _conta(copia, "controlli") == 0
    assert _conta(server.app / "dati" / "fanta.sqlite", "controlli") == 5          # la produzione non perde niente
    if os.name != "nt":
        assert copia.stat().st_mode & 0o777 == 0o640                               # il gruppo della prova legge, gli altri no
    # nella casa della produzione cambiano solo il suo log e il suo blocco, in ~/.cache/fantacalcio
    dopo = server.foto_produzione()
    cambiati = {k for k in set(produzione) | set(dopo) if produzione.get(k) != dopo.get(k)}
    assert cambiati <= {".cache/fantacalcio/esporta-archivio-prova.log", ".cache/fantacalcio/blocco-esporta-prova"}, cambiati


@con_bash
def test_esporta_senza_cartella_di_scambio_non_fa_niente(server, tmp_path):
    prima = server.foto_produzione()
    env = {**server.env_produzione, "SCHIERAXI_SCAMBIO": (tmp_path / "manca").as_posix()}
    r = _lancia([BASH, (PROVA / "esporta-archivio-prova.sh").as_posix()], env)
    assert r.returncode == 1 and "scambio" in r.stderr
    assert server.foto_produzione() == prima
    assert not (tmp_path / "manca").exists()


@con_bash
def test_esporta_con_il_log_collegato_non_scrive(server, tmp_path):
    bersaglio = _scrivi(tmp_path, "bersaglio.txt", "INTATTO")
    _collega(bersaglio, server.stato / "esporta-archivio-prova.log")
    r = _lancia([BASH, (PROVA / "esporta-archivio-prova.sh").as_posix()], server.env_produzione)
    assert r.returncode == 1 and "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert not (server.scambio / "fanta.sqlite").exists()


# ---------------------------------------------------------------- copia-archivio-prova.sh (utente della prova)

@con_bash
def test_copia_archivio_prova_con_prova_non_scrive(server):
    server.prova_installata(server.c1)
    server.esportata()
    prima = _istantanea(server.casa_prova)
    r = _lancia([BASH, (PROVA / "copia-archivio-prova.sh").as_posix(), "--prova"], server.env_prova)
    assert r.returncode == 0, r.stderr
    assert "fanta.sqlite" in r.stdout
    assert _istantanea(server.casa_prova) == prima


@con_bash
def test_copia_archivio_prova_prende_la_copia_dallo_scambio(server):
    server.prova_installata(server.c1)
    server.esportata(calciatori=80)
    scambio = _istantanea(server.scambio)
    r = _lancia([BASH, (PROVA / "copia-archivio-prova.sh").as_posix()], server.env_prova)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _conta(server.prova / "dati" / "fanta.sqlite", "calciatori") == 80
    assert "aggiornato" in (server.prova / "dati" / "copia-archivio.log").read_text(encoding="utf-8")
    assert _istantanea(server.scambio) == scambio                                   # la copia della produzione solo letta


@con_bash
def test_copia_archivio_prova_nella_casa_della_produzione_si_ferma(server):
    server.esportata()
    prima = server.foto_produzione()
    r = _lancia([BASH, (PROVA / "copia-archivio-prova.sh").as_posix()], server.env_produzione)
    assert r.returncode == 1 and UTENTE_PROVA in r.stderr
    assert server.foto_produzione() == prima


@con_bash
@pytest.mark.parametrize("nome", ["copia-archivio.log", "copia-archivio.log.tmp"])
def test_copia_archivio_prova_con_il_log_collegato_non_scrive(server, tmp_path, nome):
    server.prova_installata(server.c1)
    server.esportata()
    bersaglio = _scrivi(tmp_path, "bersaglio.txt", "INTATTO")
    _collega(bersaglio, server.prova / "dati" / nome)
    r = _lancia([BASH, (PROVA / "copia-archivio-prova.sh").as_posix()], server.env_prova)
    assert r.returncode == 1 and "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert not (server.prova / "dati" / "fanta.sqlite").exists()


# ---------------------------------------------------------------- prepara-prova.sh (utente della prova)

def _prepara(s, *argomenti, env=None):
    return _lancia([BASH, (PROVA / "prepara-prova.sh").as_posix(), *argomenti], env or s.env_prova, timeout=120)


@con_bash
def test_prepara_prova_con_prova_non_scrive_niente(server):
    server.esportata()
    prima = _istantanea(server.casa_prova), server.foto_produzione()
    r = _prepara(server, "--prova", server.c1)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (_istantanea(server.casa_prova), server.foto_produzione()) == prima
    for parola in (server.c1[:7], "schieraxi-src", "--require-hashes", "dati", "fanta.sqlite", "lega/esempio"):
        assert parola in r.stdout, parola
    assert server.registro() == ""


@con_bash
def test_prepara_prova_mette_codice_verificato_dati_inventati_e_non_tocca_la_produzione(server):
    s = server
    s.esportata(calciatori=80)
    produzione = s.foto_produzione()
    r = _prepara(s, s.c1)
    assert r.returncode == 0, r.stdout + r.stderr
    p = s.prova
    assert (s.clone_prova / ".git").is_dir()                                        # clone suo, non quello della produzione
    assert (p / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"        # la versione data (c1), non la punta di main
    assert (p / "script" / "server" / "prova" / "copia_archivio.py").exists()
    assert (p / "tests" / "t.py").exists() and (p / "requirements.txt").exists()
    assert (p / "lega" / "esempio" / "regole.json").read_text(encoding="utf-8") == "REGOLE ESEMPIO"
    assert not (p / "lega" / "rose.json").exists()                                  # mai la lega vera
    assert not (p / "ios").exists() and not (p / "sito").exists() and not (p / "docs").exists()
    assert (p / ".venv" / "bin" / "python").exists()
    assert "--require-hashes" in s.registro()
    assert not (p / "dati" / "ambiente.env").exists()                               # le variabili stanno nel file del servizio
    assert _conta(p / "dati" / "fanta.sqlite", "calciatori") == 80                 # dalla cartella di scambio
    assert _conta(p / "dati" / "fanta.sqlite", "controlli") == 0
    assert not (p / "dati" / "account.sqlite").exists()                             # nessun utente della produzione
    assert (s.stato_prova / "ultimo-rilascio").read_text(encoding="utf-8").strip() == s.c1
    assert (s.stato_prova / "verificato").read_text(encoding="utf-8").strip() == s.c1
    if os.name != "nt":
        assert (p / "dati").stat().st_mode & 0o077 == 0
    assert s.foto_produzione() == produzione
    assert "restart" not in s.registro()                                            # il servizio lo accende un passo a mano
    # rilanciata non rifà e non cambia niente
    dopo = _istantanea(p), _istantanea(s.stato_prova)
    r = _prepara(s, s.c1)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (_istantanea(p), _istantanea(s.stato_prova)) == dopo


@con_bash
def test_prepara_prova_nella_casa_della_produzione_si_ferma(server):
    prima = server.foto_produzione()
    r = _prepara(server, server.c1, env={**server.env_produzione, "SCHIERAXI_REPO": server.github.as_posix(),
                                          "SCHIERAXI_PYTHON": server.python.as_posix()})
    assert r.returncode == 1 and UTENTE_PROVA in r.stderr
    assert server.foto_produzione() == prima


@con_bash
@pytest.mark.parametrize("versione", [None, "non-una-versione"])
def test_prepara_prova_senza_versione_non_scrive_niente(server, versione):
    r = _prepara(server, *([] if versione is None else [versione]))
    assert r.returncode == 1 and "verificato" in r.stderr
    assert not any(server.casa_prova.iterdir())


@con_bash
def test_prepara_prova_rifiuta_una_versione_fuori_da_main(server):
    server.esportata()
    r = _prepara(server, server.fuori_da_main)
    assert r.returncode == 1 and "main" in r.stderr
    assert not server.prova.exists() and not server.stato_prova.exists()


@con_bash
def test_prepara_prova_senza_la_copia_della_produzione_si_ferma_prima_dello_stato(server):
    r = _prepara(server, server.c1)
    assert r.returncode == 1 and "esporta-archivio-prova.sh" in r.stderr
    assert not (server.prova / "dati" / "fanta.sqlite").exists()
    assert not (server.stato_prova / "ultimo-rilascio").exists()           # lo stato si scrive solo a preparazione finita


# ---------------------------------------------------------------- nginx

def test_nginx_della_prova_non_indicizzato():
    testo = (PROVA / "nginx-prova.conf.esempio").read_text(encoding="utf-8")
    codice = "\n".join(r.split("#", 1)[0].rstrip() for r in testo.splitlines())
    assert codice.count("{") == codice.count("}") > 0
    for riga in (r.strip() for r in codice.splitlines()):
        assert not riga or riga.endswith((";", "{", "}")), riga
    assert re.search(r"^\s*server_name prova\.<dominio>;", codice, re.M)
    assert re.search(r"^\s*proxy_pass http://127\.0\.0\.1:8001;", codice, re.M)
    assert re.search(r'^\s*add_header X-Robots-Tag "noindex, nofollow" always;', codice, re.M)
    assert re.search(r"^\s*proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;", codice, re.M)
    assert re.search(r"^\s*proxy_set_header X-Forwarded-Proto \$scheme;", codice, re.M)
    assert re.search(r"^\s*proxy_set_header Host \$host;", codice, re.M)
    assert re.search(r"^\s*client_max_body_size 12m;", codice, re.M)      # come il tetto delle richieste dell'app
    assert re.search(r"^\s*listen 80;", codice, re.M) and re.search(r"^\s*listen \[::\]:80;", codice, re.M)
    assert "8000" not in codice and "ssl_certificate" not in codice          # il certificato lo aggiunge certbot


# ---------------------------------------------------------------- testi pubblici, sintassi e istruzioni

def _file_della_prova():
    return sorted(p for p in PROVA.iterdir() if p.is_file())


def test_nessun_indirizzo_vero_nei_file_della_prova():
    assert _file_della_prova(), "manca la cartella script/server/prova"
    for f in _file_della_prova():
        t = f.read_text(encoding="utf-8")
        for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", t):
            assert ip == "127.0.0.1", f"{f.name}: indirizzo {ip}"
        for dominio in re.findall(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:it|com|net|org|eu|io|dev|app|cloud)\b", t, re.I):
            assert dominio.lower() in {"example.com", "github.com"}, f"{f.name}: dominio {dominio}"
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t), f"{f.name}: indirizzo email"
        for casa in re.findall(r"/home/([^/\s\"'`]+)", t):
            assert casa in {"<utente>", "$USER"}, f"{f.name}: /home/{casa}"           # segnaposto o variabile della shell
        for vietato in ("Rasp" + "berry", "schieraxi" + ".it"):          # parole a pezzi, come in test_script_server.py
            assert vietato.lower() not in t.lower(), f"{f.name}: {vietato}"


def test_file_della_prova_con_fine_riga_unix_e_sintassi_corretta():
    for f in _file_della_prova():
        assert b"\r" not in f.read_bytes(), f"{f.name}: fine riga di Windows"
    if not BASH:
        pytest.skip("serve bash")
    script = [f for f in _file_della_prova() if f.suffix == ".sh"]
    assert {f.name for f in script} == {"prepara-prova.sh", "copia-archivio-prova.sh", "esporta-archivio-prova.sh"}
    for f in script:
        r = subprocess.run([BASH, "-n", f.as_posix()], capture_output=True, text=True, timeout=20)
        assert r.returncode == 0, f"{f.name}: {r.stderr}"
        t = f.read_text(encoding="utf-8")
        assert "set -u" in t and "PYTHONUTF8=1" in t and "--prova" in t, f.name
        assert not re.search(r"rm -r[f]* [^\n]*fantacalcio", t), f"{f.name}: rm -r sulla produzione"
        for riga in (r for r in t.splitlines() if '>> "$LOG"' in r):         # mai un log scritto senza il controllo dei collegamenti
            assert "[ -L" in t[:t.index(riga)], f"{f.name}: {riga.strip()}"


def _passi(t):
    posizioni = [t.find(f"## 4.{n} ") for n in range(1, 12)]
    assert all(p >= 0 for p in posizioni) and posizioni == sorted(posizioni), posizioni
    return [t[a:b] for a, b in zip(posizioni, posizioni[1:] + [len(t)])]


def test_leggimi_della_prova_ha_tutti_i_passi_in_ordine_con_prova_e_ritorno():
    t = (PROVA / "LEGGIMI.md").read_text(encoding="utf-8")
    passi = _passi(t)
    primo = passi[0]
    for comando in ("free -m", "nproc", "df -h ~", "systemctl show fantacalcio", "systemctl cat fantacalcio", "sudo -l",
                    "ls /etc/nginx/sites-enabled/", "command -v certbot", "readlink -f ~/fantacalcio/.venv/bin/python",
                    "systemctl --version", "stat -c", "/etc/cron.allow"):
        assert comando in primo, comando
    # la prova di sola lettura che un altro utente NON vede la cartella dei dati della produzione dal suo processo
    assert "systemctl show -p MainPID --value fantacalcio" in primo
    assert re.search(r"sudo -u nobody ls /proc/\$pid/cwd/dati", primo)
    assert "700 MB" in primo and "3 GB" in primo and "solo durante il collaudo" in primo
    for n, passo in enumerate(passi[2:10], start=3):
        assert "Prova:" in passo, f"4.{n} senza prova"
        assert "Indietro:" in passo, f"4.{n} senza ritorno indietro"
    utente = passi[2]
    assert f"useradd --system --home-dir {CASA_PROVA}" in utente and "--shell /usr/sbin/nologin" in utente
    assert re.search(rf"sudo -u {UTENTE_PROVA} ls /proc/\$pid/cwd/dati", utente)    # la stessa prova con l'utente vero
    assert "userdel" in utente and "fantacalcio" not in utente.split("Indietro:", 1)[1].split("\n\n", 1)[0]
    for riga in (f"sudo crontab -u {UTENTE_PROVA}", "SCHIERAXI_ISTANZA=prova /bin/bash $HOME/app/script/server/aggiorna-app.sh",
                 "/bin/bash $HOME/app/script/server/prova/copia-archivio-prova.sh",
                 "/bin/bash $HOME/fantacalcio/script/server/prova/esporta-archivio-prova.sh",
                 "prepara-prova.sh --prova", f"/etc/sudoers.d/{UTENTE_PROVA}",
                 f"{UTENTE_PROVA} ALL=(root) NOPASSWD: /usr/bin/systemctl restart {UTENTE_PROVA}",
                 "certbot --nginx -d prova.<dominio>", "minuti che finiscono per 2 o per 7"):
        assert riga in t, riga
    # chiave delle firme di root, fuori dalla casa della prova (che la prova possiede)
    assert f"sudo install -D -o root -g root -m 644 ~/.config/schieraxi/chiavi-firma.asc {CHIAVE_PROVA}" in utente
    assert f"{CASA_PROVA}/.config" not in t
    # il crontab della produzione: copia prima di cambiarlo, e il ritorno la rimette
    crontab = passi[9]
    assert crontab.index("crontab -l > ~/crontab-prima-prova.txt") < crontab.index("crontab -e")
    assert "crontab ~/crontab-prima-prova.txt" in crontab and "crontab ~/crontab-prima-prova.txt" in passi[10]


def test_root_non_installa_file_della_prova():
    """La prova possiede /srv/schieraxi-prova: un file di systemd, di nginx o uno script preso da lì e installato da root lo
    sceglierebbe lei. Root copia solo dalla copia installata in produzione (~/fantacalcio/script/server/prova/) o da file suoi."""
    t = (PROVA / "LEGGIMI.md").read_text(encoding="utf-8")
    copiati = 0
    for riga in t.splitlines():
        parole = riga.split("#", 1)[0].split()
        if parole[:2] != ["sudo", "install"]:
            continue
        posizionali, i = [], 2
        while i < len(parole):
            if parole[i] in ("-o", "-g", "-m"):
                i += 2                                            # opzione con il suo valore
            elif parole[i].startswith("-"):
                i += 1                                            # -d, -D
            else:
                posizionali.append(parole[i])
                i += 1
        if "-d" in parole:
            continue                                              # crea solo una cartella: niente da copiare
        assert len(posizionali) == 2, riga.strip()
        copiati += 1
        assert not posizionali[0].startswith(CASA_PROVA), riga.strip()
    assert copiati >= 4              # servizio, nginx, script di preparazione, chiave delle firme
    for nome in ("schieraxi-prova.service", "nginx-prova.conf.esempio", "prepara-prova.sh"):
        assert f"~/fantacalcio/script/server/prova/{nome}" in t, nome


def test_root_non_lavora_dentro_la_casa_della_prova():
    """Dentro /srv/schieraxi-prova la prova può mettere collegamenti simbolici al posto di cartelle e file (per esempio `app` o una
    destinazione `….da-togliere` che punta alla produzione): un `mv`, `cp`, `rm`, `install` o anche una lettura fatti da root li
    seguirebbero. Ogni comando del LEGGIMI che tocca un percorso DENTRO la casa della prova gira con il suo utente
    (`sudo -u schieraxi-prova …`). Root tocca solo la casa intera: la crea e, nel ritorno indietro, la sposta in
    /srv/schieraxi-prova.da-togliere (una voce di /srv, che è di root: la prova non la può sostituire)."""
    t = (PROVA / "LEGGIMI.md").read_text(encoding="utf-8")
    comandi = [m.group(0).strip() for m in re.finditer(r"\bsudo\b[^`;&|\n]*", t)]
    assert len(comandi) > 20
    dentro = re.compile(re.escape(CASA_PROVA) + r"/")
    di_root = [c for c in comandi if not c.startswith(f"sudo -u {UTENTE_PROVA}") and dentro.search(c)]
    assert di_root == [], di_root
    casa_intera = [c for c in comandi if c.split()[:2] == ["sudo", "mv"] and CASA_PROVA in c]
    assert casa_intera and all(c.split()[2:4] == [CASA_PROVA, f"{CASA_PROVA}.da-togliere"] for c in casa_intera), casa_intera
    assert f"sudo -u {UTENTE_PROVA} mv {CASA_PROVA}/app/lega {CASA_PROVA}/app/lega.vecchia" in t


def test_leggimi_del_server_rimanda_alla_prova():
    t = (SERVER / "LEGGIMI.md").read_text(encoding="utf-8")
    assert "prova/LEGGIMI.md" in t and "SCHIERAXI_ISTANZA" in t and UTENTE_PROVA in t
