"""L'ambiente di prova sullo stesso server (script/server/prova/, piano 2026-11-08-ondata-2, lavoro C1).

Una seconda copia dell'app con dati inventati, accanto alla produzione. Le prove usano una "casa" finta in una cartella temporanea
(produzione installata, clone di un "GitHub" locale, finti sudo, curl e flock): niente server vero, niente rete, niente finestre.
Controllano soprattutto due cose:
- senza SCHIERAXI_ISTANZA `aggiorna-app.sh` fa quello di sempre (stesse cartelle, servizio, porta, attesa delle partite);
- l'ambiente di prova scrive solo nelle sue cartelle e il suo servizio non vede i dati della produzione.
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


def _istantanea(cartella):
    """(percorso, impronta) di tutto ciò che c'è: per confrontare prima e dopo."""
    out = {}
    cartella = Path(cartella)
    if not cartella.exists():
        return out
    for p in sorted(cartella.rglob("*")):
        rel = p.relative_to(cartella).as_posix()
        out[rel] = hashlib.sha1(p.read_bytes()).hexdigest() if p.is_file() else "/"
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
    """Come bash scrive la casa (su Windows Git bash la converte in /c/...)."""
    r = _lancia([BASH, "-c", 'printf %s "$HOME"'], _ambiente(casa))
    return r.stdout


def _archivio_finto(percorso, calciatori=100, controlli=5, wal=True):
    """Un dati/fanta.sqlite inventato: calciatori (dati di calcio) e controlli (esiti della sentinella, parlano degli utenti)."""
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
    db = sqlite3.connect(percorso)
    try:
        return db.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]
    finally:
        db.close()


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
    """Valori di InaccessiblePaths, BindPaths... : più percorsi per riga, il '-' davanti vuol dire «se c'è»."""
    return [p.lstrip("-+") for v in valori for p in v.split()]


# ---------------------------------------------------------------- casa finta del server

@pytest.fixture
def casa(tmp_path):
    """Casa finta: produzione installata in ~/fantacalcio (lega vera, account, archivio), clone ~/schieraxi-src di un "GitHub" locale
    con due commit (c1 verificato dalla produzione, c2 più nuovo), finti sudo, curl e flock che annotano le chiamate e un finto Python
    dell'app (crea ambienti, finge pip, dice «partita in corso» a momento-libero, passa i file .py al Python vero)."""
    if not BASH or not shutil.which("git"):
        pytest.skip("servono bash e git")

    class C:
        pass
    c = C()
    c.casa = tmp_path / "casa"
    c.bin = tmp_path / "bin"
    c.lavoro = tmp_path / "github"
    for d in (c.casa, c.bin, c.lavoro):
        d.mkdir()
    c.chiamate = tmp_path / "chiamate.txt"
    reg = c.chiamate.as_posix()
    _stub(c.bin, "flock", "exit 0")
    _stub(c.bin, "sudo", f'echo "sudo $*" >> "{reg}"')
    _stub(c.bin, "curl", f'echo "curl $*" >> "{reg}"; echo 200')
    # GitHub finto: le cartelle del server, la lega d'esempio, le cose che il server non installa e i veri file della prova
    file = {"fanta/__init__.py": "V1", "fanta/novita.json": '[{"versione": "1.0"}]', "tests/t.py": "T1",
            "script/server/x.sh": "S1", "requirements.txt": "r1", "requirements-dev.txt": "d1",
            "lega/esempio/regole.json": "REGOLE ESEMPIO", "lega/esempio/rose.json": "ROSE ESEMPIO",
            "lega/esempio/immagini/a.txt": "IMG", "ios/a.txt": "ios1", "sito/index.html": "<html>1", "docs/d.md": "doc1"}
    for f in PROVA.iterdir():
        if f.is_file():
            file[f"script/server/prova/{f.name}"] = f.read_text(encoding="utf-8")
    _git(c.lavoro, "init", "-q", "-b", "main")
    c.c1 = _commit(c.lavoro, "uno", **file)
    c.c2 = _commit(c.lavoro, "due", **{"fanta/__init__.py": "V2"})
    _git(c.casa, "clone", "-q", c.lavoro.as_posix(), "schieraxi-src")
    # produzione installata alla versione c1, con i SUOI dati (che la prova non deve mai toccare)
    c.app = c.casa / "fantacalcio"
    c.stato = c.casa / ".cache" / "fantacalcio"
    for rel, t in {"fanta/__init__.py": "V1", "tests/t.py": "T1", "script/server/x.sh": "S1", "requirements.txt": "r1",
                   "requirements-dev.txt": "d1", "lega/rose.json": "LEGA VERA", "dati/account.sqlite": "ACCOUNT VERI",
                   "dati/ambiente.env": "FANTA_MULTIUTENTE=1\nFANTA_MAIL=smtp\n"}.items():
        _scrivi(c.app, rel, t)
    _archivio_finto(c.app / "dati" / "fanta.sqlite")
    for nome, t in {"ultimo-rilascio": c.c1, "verificato": c.c1, "blocco-pubblicazione": ""}.items():
        _scrivi(c.stato, nome, t)
    python_vero = Path(sys.executable).as_posix()
    _stub(c.app / ".venv" / "bin", "python", f'''reg="{reg}"
case "$1" in
  -m) case "$2" in
        venv) mkdir -p "$3/bin" && cp "$0" "$3/bin/python" && echo "venv $3" >> "$reg" ;;
        pip) shift 2; echo "pip $*" >> "$reg" ;;
        fanta) echo "fanta $3" >> "$reg"; [ "$3" = momento-libero ] && {{ echo "partita in corso"; exit 3; }} ;;
      esac ;;
  -c) case "$2" in *notifiche.invia*) echo "avviso $3" >> "$reg" ;; *novita.json*) echo "1.0" ;; esac ;;
  *.py) exec "{python_vero}" "$@" ;;
esac
exit 0''')
    c.prova = c.casa / "schieraxi-prova"
    c.stato_prova = c.casa / ".cache" / "schieraxi-prova"
    c.env = _ambiente(c.casa, c.bin, SCHIERAXI_ATTESE_AVVIO="2")
    c.registro = lambda: c.chiamate.read_text(encoding="utf-8") if c.chiamate.exists() else ""

    def produzione():
        """Tutto ciò che la prova non deve cambiare. I file di appoggio di sqlite (-shm, -wal) li crea o li tocca chiunque legga un
        archivio WAL (sul server il servizio li tiene sempre aperti): l'archivio deve restare identico e il -wal vuoto."""
        wal = c.app / "dati" / "fanta.sqlite-wal"
        assert not wal.exists() or wal.stat().st_size == 0
        app = {k: v for k, v in _istantanea(c.app).items() if not k.endswith(("fanta.sqlite-shm", "fanta.sqlite-wal"))}
        return app, _istantanea(c.stato)
    c.produzione = produzione
    return c


def _prova_installata(c, commit):
    """La prova come la lascia prepara-prova.sh: codice di `commit`, ambiente Python, dati suoi, stato suo."""
    for rel, t in {"fanta/__init__.py": "V1", "tests/t.py": "T1", "script/server/x.sh": "S1", "requirements.txt": "r1",
                   "requirements-dev.txt": "d1", "dati/ambiente.env": "FANTA_MULTIUTENTE=1\n"}.items():
        _scrivi(c.prova, rel, t)
    (c.prova / ".venv" / "bin").mkdir(parents=True)
    shutil.copy(c.app / ".venv" / "bin" / "python", c.prova / ".venv" / "bin" / "python")
    _scrivi(c.stato_prova, "ultimo-rilascio", commit)


# ---------------------------------------------------------------- aggiorna-app.sh: le istanze

@con_bash
@pytest.mark.parametrize("istanza", [None, ""])
def test_senza_istanza_tutto_come_oggi(tmp_path, istanza):
    casa = tmp_path / "casa"
    casa.mkdir()
    extra = {} if istanza is None else {"SCHIERAXI_ISTANZA": istanza}
    r = _lancia([BASH, AGGIORNA.as_posix(), "--configurazione"], _ambiente(casa, **extra))
    assert r.returncode == 0, r.stderr
    h = _casa_per_bash(casa)
    assert r.stdout.splitlines() == [f"DEST={h}/fantacalcio", f"STATO={h}/.cache/fantacalcio", "SERVIZIO=fantacalcio",
                                     "PORTA=8000", "ATTENDE_PARTITE=1"]
    assert not any(casa.iterdir())                                  # --configurazione non crea niente


@con_bash
def test_prova_tutto_nelle_sue_cartelle(tmp_path):
    casa = tmp_path / "casa"
    casa.mkdir()
    r = _lancia([BASH, AGGIORNA.as_posix(), "--configurazione"], _ambiente(casa, SCHIERAXI_ISTANZA="prova"))
    assert r.returncode == 0, r.stderr
    h = _casa_per_bash(casa)
    assert r.stdout.splitlines() == [f"DEST={h}/schieraxi-prova", f"STATO={h}/.cache/schieraxi-prova", "SERVIZIO=schieraxi-prova",
                                     "PORTA=8001", "ATTENDE_PARTITE=0"]
    assert not any(casa.iterdir())


@con_bash
@pytest.mark.parametrize("argomenti", [[], ["--prova"], ["--configurazione"]])
def test_istanza_sconosciuta_si_ferma(casa, argomenti):
    prima = _istantanea(casa.casa)
    r = _lancia([BASH, AGGIORNA.as_posix(), *argomenti], {**casa.env, "SCHIERAXI_ISTANZA": "collaudo"})
    assert r.returncode == 2
    assert "SCHIERAXI_ISTANZA" in r.stderr and "prova" in r.stderr
    assert _istantanea(casa.casa) == prima                          # nessun file scritto, nemmeno blocchi o log
    assert casa.registro() == ""                                    # niente sudo, curl, Python


@con_bash
def test_prova_installa_solo_nelle_sue_cartelle_senza_aspettare_le_partite_e_senza_avvisi(casa):
    """Versione nuova (c2) con una partita in corso: la prova la installa subito, riavvia SOLO il suo servizio, chiede la salute
    sulla sua porta, non manda avvisi; la produzione (cartella, stato, servizio) resta identica."""
    _prova_installata(casa, casa.c1)
    produzione = casa.produzione()
    r = _lancia([BASH, AGGIORNA.as_posix()], {**casa.env, "SCHIERAXI_ISTANZA": "prova", "SCHIERAXI_SENZA_FIRME": "1"})
    assert r.returncode == 0, r.stderr
    assert (casa.prova / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V2"
    assert (casa.stato_prova / "ultimo-rilascio").read_text(encoding="utf-8").strip() == casa.c2
    assert "installata" in (casa.prova / "dati" / "pubblicazione.log").read_text(encoding="utf-8")
    reg = casa.registro()
    assert "sudo systemctl restart schieraxi-prova" in reg
    assert "restart fantacalcio" not in reg
    assert "127.0.0.1:8001" in reg and "127.0.0.1:8000" not in reg
    assert "momento-libero" not in reg                             # la prova non aspetta la fine delle partite
    assert "avviso " not in reg                                    # nessun avviso sul canale della produzione
    assert casa.produzione() == produzione
    assert not (casa.prova / "ios").exists() and not (casa.prova / "sito").exists()


@con_bash
def test_prova_non_preparata_non_crea_niente(casa):
    produzione = casa.produzione()
    r = _lancia([BASH, AGGIORNA.as_posix()], {**casa.env, "SCHIERAXI_ISTANZA": "prova", "SCHIERAXI_SENZA_FIRME": "1"})
    assert r.returncode == 0, r.stderr
    assert "prepara-prova.sh" in r.stderr
    assert not casa.prova.exists() and not casa.stato_prova.exists()
    assert casa.produzione() == produzione
    assert casa.registro() == ""


@con_bash
def test_in_produzione_la_partita_in_corso_rimanda_ancora(casa):
    """Controllo di contrasto: lo stesso finto Python con la produzione rimanda l'installazione (cosi' la prova sopra dimostra che
    la prova salta l'attesa, non che il finto Python non la chiede)."""
    r = _lancia([BASH, AGGIORNA.as_posix()], {**casa.env, "SCHIERAXI_SENZA_FIRME": "1"})
    assert r.returncode == 0, r.stderr
    assert "fanta momento-libero" in casa.registro()
    assert "restart" not in casa.registro()
    assert (casa.app / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"


# ---------------------------------------------------------------- servizio systemd della prova

def test_unita_della_prova_non_vede_i_dati_della_produzione():
    testo = (PROVA / "schieraxi-prova.service").read_text(encoding="utf-8")
    u = _unita(testo)
    s = u["Service"]
    casa_prova = "/home/<utente>/schieraxi-prova"
    assert s["User"] == ["<utente>"]
    assert s["WorkingDirectory"] == [casa_prova]
    assert s["ExecStart"] == [f"{casa_prova}/.venv/bin/python -m fanta server --host 127.0.0.1 --porta 8001"]
    assert s["EnvironmentFile"] == [f"{casa_prova}/dati/ambiente.env"]          # senza '-': se manca, il servizio non parte
    ambiente = s["Environment"]
    for v in ("FANTA_MULTIUTENTE=1", "PYTHONDONTWRITEBYTECODE=1"):
        assert v in ambiente
    # chiuso nella sua cartella: tutta /home vuota tranne la cartella della prova (sola lettura) e i suoi dati (scrittura)
    assert s["ProtectSystem"] == ["strict"]
    assert s["ProtectHome"] == ["tmpfs"]
    assert _percorsi(s["BindReadOnlyPaths"]) == [casa_prova]
    assert _percorsi(s["BindPaths"]) == [f"{casa_prova}/dati"]
    assert _percorsi(s["ReadWritePaths"]) == [f"{casa_prova}/dati"]
    # seconda rete, se qualcuno rimette ProtectHome=read-only: i dati della produzione, le chiavi e le copie restano invisibili
    invisibili = _percorsi(s["InaccessiblePaths"])
    for p in ("/home/<utente>/fantacalcio", "/home/<utente>/.config", "/home/<utente>/.ssh", "/home/<utente>/backup-dati"):
        assert p in invisibili
    for chiave in ("BindReadOnlyPaths", "BindPaths", "ReadWritePaths"):
        assert all(p == casa_prova or p.startswith(casa_prova + "/") for p in _percorsi(s[chiave])), chiave
    assert s["PrivateTmp"] == ["yes"] and s["NoNewPrivileges"] == ["yes"]
    assert s["MemoryMax"] == ["500M"] and s["CPUWeight"] == ["20"] and s["Nice"] == ["19"]
    assert "0.0.0.0" not in testo and "8000" not in testo
    assert u["Install"]["WantedBy"] == ["multi-user.target"]


def test_ambiente_della_prova_spegne_lavori_posta_e_fonti():
    testo = (PROVA / "ambiente-prova.env.esempio").read_text(encoding="utf-8")
    righe = [r for r in testo.splitlines() if r.strip() and not r.lstrip().startswith("#")]
    for r in righe:                      # le legge anche leggi-ambiente.sh: solo FANTA_* (o MAX_UTENTI), una per riga
        assert re.fullmatch(r"(FANTA_[A-Z0-9_]+|MAX_UTENTI)=[^\s'\"$`;]*", r), r
    valori = dict(r.split("=", 1) for r in righe)
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


# ---------------------------------------------------------------- copia dell'archivio

def _modulo_copia():
    spec = importlib.util.spec_from_file_location("copia_archivio_prova", PROVA / "copia_archivio.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _impronta(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def test_copia_archivio_senza_controlli_e_atomica(tmp_path):
    """Produzione in WAL con il servizio acceso (una connessione aperta) e prova con il suo archivio aperto: la copia ha i dati di
    calcio e non gli esiti della sentinella, la produzione resta identica, chi legge la prova vede l'archivio nuovo e sano."""
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
    assert _conta(origine, "controlli") == 7                     # la produzione non perde niente
    assert _impronta(origine) == prima
    db = sqlite3.connect(destinazione)
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.close()
    assert sorted(p.name for p in destinazione.parent.iterdir() if ".nuovo" in p.name) == []


@pytest.mark.parametrize("guasto", ["non e' un archivio", None])
def test_copia_archivio_non_riuscita_lascia_la_prova_com_era(tmp_path, guasto):
    m = _modulo_copia()
    origine = tmp_path / "produzione" / "fanta.sqlite"
    if guasto is not None:
        _scrivi(origine.parent, origine.name, guasto * 2000)
    destinazione = tmp_path / "prova" / "fanta.sqlite"
    _archivio_finto(destinazione, calciatori=3, controlli=0)
    with pytest.raises(m.CopiaNonRiuscita):
        m.copia(origine, destinazione)
    assert _conta(destinazione, "calciatori") == 3
    assert sorted(p.name for p in destinazione.parent.iterdir() if ".nuovo" in p.name) == []


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
    assert "fanta" not in moduli


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


# ---------------------------------------------------------------- testi pubblici e sintassi

def _file_della_prova():
    return sorted(p for p in PROVA.iterdir() if p.is_file())


def test_nessun_indirizzo_vero_nei_file_della_prova():
    assert _file_della_prova(), "manca la cartella script/server/prova"
    for f in _file_della_prova():
        t = f.read_text(encoding="utf-8")
        for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", t):
            assert ip == "127.0.0.1", f"{f.name}: indirizzo {ip}"
        for dominio in re.findall(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:it|com|net|org|eu|io|dev|app|cloud)\b", t, re.I):
            assert dominio.lower() in {"example.com"}, f"{f.name}: dominio {dominio}"
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
    assert {f.name for f in script} == {"prepara-prova.sh", "copia-archivio-prova.sh"}
    for f in script:
        r = subprocess.run([BASH, "-n", f.as_posix()], capture_output=True, text=True, timeout=20)
        assert r.returncode == 0, f"{f.name}: {r.stderr}"
        t = f.read_text(encoding="utf-8")
        assert "set -u" in t and "PYTHONUTF8=1" in t and "--prova" in t, f.name
        assert not re.search(r"rm -r[f]* [^\n]*fantacalcio", t), f"{f.name}: rm -r sulla produzione"


def test_leggimi_della_prova_ha_tutti_i_passi_in_ordine_con_prova_e_ritorno():
    t = (PROVA / "LEGGIMI.md").read_text(encoding="utf-8")
    posizioni = [t.find(f"## 4.{n}") for n in range(1, 10)]
    assert all(p >= 0 for p in posizioni) and posizioni == sorted(posizioni), posizioni
    primo = t[posizioni[0]:posizioni[1]]
    for comando in ("free -m", "nproc", "df -h ~", "systemctl show fantacalcio", "systemctl cat fantacalcio", "sudo -l",
                    "ls /etc/nginx/sites-enabled/", "command -v certbot", "readlink -f ~/fantacalcio/.venv/bin/python",
                    "systemctl --version"):
        assert comando in primo, comando
    assert "700 MB" in primo and "3 GB" in primo and "solo durante il collaudo" in primo
    for n in range(3, 9):
        passo = t[posizioni[n - 1]:posizioni[n]]
        assert "Prova:" in passo, f"4.{n} senza prova"
        assert "Indietro:" in passo, f"4.{n} senza ritorno indietro"
    for riga in ("SCHIERAXI_ISTANZA=prova /bin/bash $HOME/schieraxi-prova/script/server/aggiorna-app.sh",
                 "/bin/bash $HOME/schieraxi-prova/script/server/prova/copia-archivio-prova.sh",
                 "prepara-prova.sh --prova", "/etc/sudoers.d/schieraxi-prova", "certbot --nginx -d prova.<dominio>"):
        assert riga in t, riga


def test_leggimi_del_server_rimanda_alla_prova():
    t = (SERVER / "LEGGIMI.md").read_text(encoding="utf-8")
    assert "prova/LEGGIMI.md" in t and "SCHIERAXI_ISTANZA" in t


# ---------------------------------------------------------------- prepara-prova.sh

@con_bash
def test_prepara_prova_con_prova_non_scrive_niente(casa):
    prima = _istantanea(casa.casa)
    r = _lancia([BASH, (PROVA / "prepara-prova.sh").as_posix(), "--prova"], casa.env)
    assert r.returncode == 0, r.stderr
    assert _istantanea(casa.casa) == prima
    out = r.stdout
    assert casa.c1[:7] in out and casa.c2[:7] not in out             # il codice verificato dalla produzione, non la punta
    for parola in ("schieraxi-prova", "--require-hashes", "ambiente.env", "fanta.sqlite", "lega/esempio"):
        assert parola in out, parola
    assert "pip" not in casa.registro() and "venv" not in casa.registro()


@con_bash
def test_prepara_prova_mette_codice_verificato_dati_inventati_e_non_tocca_la_produzione(casa):
    produzione = casa.produzione()
    r = _lancia([BASH, (PROVA / "prepara-prova.sh").as_posix()], casa.env, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    p = casa.prova
    assert (p / "fanta" / "__init__.py").read_text(encoding="utf-8") == "V1"       # c1, quello verificato dalla produzione
    assert (p / "script" / "server" / "prova" / "copia_archivio.py").exists()
    assert (p / "tests" / "t.py").exists() and (p / "requirements.txt").exists()
    assert (p / "lega" / "esempio" / "regole.json").read_text(encoding="utf-8") == "REGOLE ESEMPIO"
    assert not (p / "lega" / "rose.json").exists()                                  # mai la lega vera
    assert not (p / "ios").exists() and not (p / "sito").exists() and not (p / "docs").exists()
    assert (p / ".venv" / "bin" / "python").exists()
    assert "--require-hashes" in casa.registro()
    assert (p / "dati" / "ambiente.env").read_text(encoding="utf-8") == \
        (PROVA / "ambiente-prova.env.esempio").read_text(encoding="utf-8")
    assert _conta(p / "dati" / "fanta.sqlite", "calciatori") == 100
    assert _conta(p / "dati" / "fanta.sqlite", "controlli") == 0
    assert not (p / "dati" / "account.sqlite").exists()                             # nessun utente della produzione
    assert (casa.stato_prova / "ultimo-rilascio").read_text(encoding="utf-8").strip() == casa.c1
    assert (casa.stato_prova / "verificato").read_text(encoding="utf-8").strip() == casa.c1
    if os.name != "nt":
        assert (p / "dati" / "ambiente.env").stat().st_mode & 0o077 == 0
        assert (p / "dati").stat().st_mode & 0o077 == 0
    assert casa.produzione() == produzione
    assert "restart" not in casa.registro()                                         # il servizio lo accende il passo 4.4, a mano
    # rilanciata non rifà e non cambia niente
    dopo = _istantanea(p), _istantanea(casa.stato_prova)
    r = _lancia([BASH, (PROVA / "prepara-prova.sh").as_posix()], casa.env, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (_istantanea(p), _istantanea(casa.stato_prova)) == dopo
    assert casa.produzione() == produzione


@con_bash
def test_prepara_prova_senza_versione_verificata_non_fa_niente(casa):
    (casa.stato / "verificato").unlink()
    (casa.stato / "ultimo-rilascio").unlink()
    prima = _istantanea(casa.casa)
    r = _lancia([BASH, (PROVA / "prepara-prova.sh").as_posix()], casa.env)
    assert r.returncode == 1
    assert _istantanea(casa.casa) == prima


@con_bash
def test_copia_archivio_prova_con_prova_non_scrive(casa):
    _prova_installata(casa, casa.c1)
    prima = _istantanea(casa.casa)
    r = _lancia([BASH, (PROVA / "copia-archivio-prova.sh").as_posix(), "--prova"], casa.env)
    assert r.returncode == 0, r.stderr
    assert "fanta.sqlite" in r.stdout
    assert _istantanea(casa.casa) == prima
