import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fanta.listone import Calciatore  # noqa: E402
from fanta.nomi import Indice  # noqa: E402


def _c(id, nome, ruolo, sq, slug):
    return Calciatore(id, nome, ruolo, "", sq, slug, 10, 10, 100)


@pytest.fixture(autouse=True)
def _senza_pianificatore(monkeypatch):
    """Nei test il pianificatore (aggiornamenti schedulati dentro il servizio) resta spento: niente rete per sbaglio."""
    monkeypatch.setenv("FANTA_PIANIFICATORE", "0")
    monkeypatch.setenv("FANTA_COPIA_SCADENZA", "0")          # e niente copie alla scadenza nei file veri della lega
    monkeypatch.setenv("FANTA_REGISTRO_GIORNATE", "0")       # né registro delle giornate (lo accendono le sue prove)


@pytest.fixture(autouse=True)
def _senza_variabili_del_servizio(monkeypatch):
    """Gli script del server leggono prima il file di root delle variabili (script/server/leggi-ambiente.sh): nei test punta a un
    percorso che non c'e', così su una macchina che ha il file vero le prove non leggono le variabili vere."""
    monkeypatch.setenv("SCHIERAXI_AMBIENTE", "/nessun-percorso/schieraxi/fantacalcio.env")


@pytest.fixture(autouse=True)
def _dns_push_finto(monkeypatch):
    """Le iscrizioni push controllano il nome del servizio: nei test niente rete vera, ogni nome vale un indirizzo pubblico."""
    from fanta import push
    push._cache_dns.clear()
    monkeypatch.setattr(push, "_risolvi_host", lambda host: ["93.184.216.34"])


@pytest.fixture(autouse=True)
def _fonti_accese_nei_test(tmp_path, monkeypatch):
    """Gli interruttori delle fonti (fanta/fonti_attive.py) sono accesi nei test, anche nell'esportazione pubblica dove il predefinito
    e' spento; la scelta dell'amministratore sta in un file temporaneo. Le prove sugli interruttori li cambiano da se'."""
    from fanta import fonti_attive
    for k in fonti_attive.FONTI:
        if k != "foto":
            monkeypatch.setenv(f"FANTA_FONTE_{k.upper()}", "1")
    monkeypatch.setattr(fonti_attive, "FILE", tmp_path / "fonti-finte.json")


@pytest.fixture(autouse=True)
def _uso_nei_test(tmp_path, monkeypatch):
    """Il conteggio d'uso (fanta/uso.py) nei test scrive in una cartella temporanea e parte vuoto."""
    from fanta import uso
    monkeypatch.setattr(uso, "FILE", tmp_path / "uso-finto.json")
    monkeypatch.setattr(uso, "_in_memoria", {})
    monkeypatch.setattr(uso, "_ultima_scrittura", 0.0)


@pytest.fixture(autouse=True)
def _funzioni_neutre_nei_test(tmp_path, monkeypatch):
    """Gli interruttori delle funzioni (fanta/funzioni.py) nei test partono come nel codice privato (tutto acceso), anche
    nell'esportazione pubblica; la scelta dell'amministratore sta in un file temporaneo."""
    from fanta import funzioni
    monkeypatch.setattr(funzioni, "VERSIONE_PUBBLICA", False)
    monkeypatch.setattr(funzioni, "FILE", tmp_path / "funzioni-finte.json")
    for k in funzioni.FUNZIONI:
        monkeypatch.delenv(f"FANTA_FUNZIONE_{k.upper()}", raising=False)


@pytest.fixture
def calciatori():
    return [
        _c(1, "Carnesecchi", "P", "ATA", "atalanta"),
        _c(2, "Sommer", "P", "INT", "inter"),
        _c(3, "Bastoni", "D", "INT", "inter"),
        _c(4, "N'Dicka", "D", "ROM", "roma"),
        _c(5, "Laurienté", "C", "SAS", "sassuolo"),
        _c(6, "Thuram K.", "C", "JUV", "juventus"),
        _c(7, "Thuram", "A", "INT", "inter"),
        _c(8, "Esposito Se.", "A", "INT", "inter"),
        _c(9, "Esposito F.P.", "A", "INT", "inter"),
        _c(10, "Martinez L.", "A", "INT", "inter"),
        _c(11, "Martinez Jo.", "P", "INT", "inter"),
        _c(12, "Barella", "C", "INT", "inter"),
        _c(13, "Dimarco", "D", "INT", "inter"),
        _c(14, "Kean", "A", "FIO", "fiorentina"),
        # due omonimi con lo stesso nome, ruoli diversi
        _c(15, "Rossi", "D", "GEN", "genoa"),
        _c(16, "Rossi", "A", "LEC", "lecce"),
        _c(17, "Pellegrini Lu.", "D", "LAZ", "lazio"),
    ]


@pytest.fixture
def listone_in_archivio(tmp_path, monkeypatch, calciatori):
    """I giocatori finti di `calciatori` nella tabella `calciatori` di un archivio temporaneo (lo stesso percorso di `dati_isolati`),
    e il server che legge quello. Serve alle rotte che accettano solo codici del listone (per esempio i Seguiti)."""
    from fanta import archivio, server
    percorso = tmp_path / "archivio-finto" / "fanta.sqlite"
    db = archivio.apri(percorso)
    db.executemany("INSERT OR REPLACE INTO calciatori(id, nome, ruolo, squadra, squadra_slug, quotazione) VALUES (?, ?, ?, ?, ?, ?)",
                   [(c.id, c.nome, c.ruolo, c.squadra, c.squadra_slug, c.quotazione) for c in calciatori])
    db.commit()
    db.close()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(percorso))
    return {c.id for c in calciatori}


@pytest.fixture
def indice(calciatori):
    return Indice(calciatori)


class Orologio:
    """Il tempo dei limiti di tentativi, che i test fanno scorrere a mano."""
    t = 1000.0


@pytest.fixture(autouse=True)
def _registri_in_cartella_finta(tmp_path, monkeypatch):
    """Il registro degli errori (errori.log) sta accanto ai dati degli account: nei test sempre in una cartella temporanea."""
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "registri-finti"))


def pytest_configure(config):
    config.addinivalue_line("markers", "percorsi_veri: non sostituire i percorsi dei dati personali con quelli finti")
    config.addinivalue_line("markers", "browser: test della web in Chrome senza finestra (tests/browser/LEGGIMI.md)")


DATI_DEL_REPOSITORY = Path(__file__).resolve().parent.parent / "dati"     # sul PC di chi usa l'app c'è l'archivio vero
_dati_all_inizio: dict[str, tuple[int, int]] | None = None
_dati_cambiati: list[str] = []


def _voci_in_dati() -> dict[str, tuple[int, int]]:
    """Ogni voce di `dati/` con dimensione e ora di modifica: un file nuovo (anche `-wal` e `-shm`) o cambiato si vede."""
    if not DATI_DEL_REPOSITORY.is_dir():
        return {}
    voci = {"dati": (0, 0)}
    for p in DATI_DEL_REPOSITORY.rglob("*"):
        try:
            s = p.stat()
        except OSError:                # sparito mentre si guardava
            continue
        voci["dati/" + p.relative_to(DATI_DEL_REPOSITORY).as_posix()] = (0, 0) if p.is_dir() else (s.st_size, s.st_mtime_ns)
    return voci


def pytest_sessionstart(session):
    """Controllo a fine sessione (#582, #934): nessun test crea o cambia file nella `dati/` del repository, nemmeno da un
    sottoprocesso. Qui si annota cosa c'è all'inizio; con pytest-xdist lo fa solo il processo principale, che guarda di nuovo
    quando tutti i test sono finiti."""
    global _dati_all_inizio
    if not hasattr(session.config, "workerinput"):
        _dati_all_inizio = _voci_in_dati()


def pytest_sessionfinish(session, exitstatus):
    if _dati_all_inizio is None:
        return
    adesso = _voci_in_dati()
    _dati_cambiati[:] = sorted(k for k, v in adesso.items() if _dati_all_inizio.get(k) != v)
    if _dati_cambiati and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    if _dati_cambiati:
        terminalreporter.section("file nuovi o cambiati nella dati/ del repository", red=True)
        terminalreporter.write_line("Un test ha scritto qui invece che in una cartella temporanea (fixture dati_isolati o tmp_path): "
                                    + ", ".join(_dati_cambiati), red=True)


# Un test non apre nemmeno in lettura i file di `dati/` (#934): sul PC di chi usa l'app c'è l'archivio vero, e un test che lo
# legge dà esiti diversi da PC a PC (e in WAL lascia `-wal` e `-shm`). Il controllo ascolta gli eventi di Python «open» e
# «sqlite3.connect» di questo processo: l'apertura fallisce (PermissionError) e il test che l'ha chiesta fallisce.
_RADICE_DATI = os.path.normcase(os.path.abspath(DATI_DEL_REPOSITORY))
_aperture_in_dati: list[str] = []


def _percorso_aperto(evento: str, args: tuple) -> str | None:
    if evento == "open":
        file = args[0]
    elif evento == "sqlite3.connect":
        file = args[0]
        if isinstance(file, str) and file.startswith("file:"):
            from urllib.parse import unquote, urlsplit
            file = unquote(urlsplit(file).path)
            if len(file) > 2 and file[0] == "/" and file[2] == ":":      # file:///C:/... su Windows
                file = file[1:]
    else:
        return None
    if isinstance(file, int) or file is None:
        return None
    try:
        file = os.fsdecode(os.fspath(file))
    except TypeError:
        return None
    if not file or file == ":memory:":
        return None
    if evento == "open" and len(args) > 1 and args[1] is None and not os.path.isabs(file):
        return None      # os.open con un nome relativo, forse a una cartella (dir_fd): su Linux shutil.rmtree apre così le sottocartelle
    return os.path.normcase(os.path.abspath(file))


def _spia_dati(evento: str, args: tuple) -> None:
    if evento not in ("open", "sqlite3.connect"):
        return
    file = _percorso_aperto(evento, args)
    if file and (file == _RADICE_DATI or file.startswith(_RADICE_DATI + os.sep)):
        _aperture_in_dati.append(file)
        raise PermissionError(f"un test ha aperto {file}: nei test i dati stanno in una cartella temporanea (#934)")


sys.addaudithook(_spia_dati)


def _dentro_dati(valore) -> bool:
    if not isinstance(valore, Path):
        return False
    s = os.path.normcase(os.path.abspath(valore))
    return s == _RADICE_DATI or s.startswith(_RADICE_DATI + os.sep)


@pytest.fixture(autouse=True)
def _file_di_dati_in_cartella_finta(request, tmp_path, monkeypatch):
    """Ogni percorso di `dati/` scritto in una costante di un modulo di `fanta` (l'archivio `archivio.FILE`, `live.json`,
    `sentinella.json`, le impostazioni degli avvisi...) nei test punta alla stessa voce di una cartella temporanea (#934); così
    anche il canale degli avvisi, che si legge da `<radice>/dati/canale-avvisi.txt`. L'archivio va allo stesso percorso di
    `dati_isolati` e `listone_in_archivio`. Le fixture più specifiche e i singoli test possono poi spostarli altrove."""
    if request.node.get_closest_marker("percorsi_veri"):
        return
    finta = tmp_path / "dati-repository-finta"
    for nome, modulo in list(sys.modules.items()):
        if modulo is None or not (nome == "fanta" or nome.startswith("fanta.")):
            continue
        for attributo, valore in list(vars(modulo).items()):
            if _dentro_dati(valore):
                relativo = Path(os.path.relpath(valore, DATI_DEL_REPOSITORY))
                monkeypatch.setattr(modulo, attributo, finta / relativo)
    from fanta import archivio, notifiche
    monkeypatch.setattr(archivio, "FILE", tmp_path / "archivio-finto" / "fanta.sqlite")
    monkeypatch.setattr(notifiche, "RADICE", tmp_path / "radice-finta")


@pytest.fixture(autouse=True)
def _nessun_file_aperto_in_dati():
    """Fallisce il test che ha aperto un file di `dati/`, anche se il codice ha preso l'errore e proseguito."""
    _aperture_in_dati.clear()
    yield
    aperti = sorted(set(_aperture_in_dati))
    _aperture_in_dati.clear()
    if aperti:
        pytest.fail("Il test ha aperto file della dati/ del repository invece di una cartella temporanea: " + ", ".join(aperti))


@pytest.fixture(autouse=True)
def _dati_personali_in_cartella_finta(request, tmp_path, monkeypatch):
    """Scelte, osservati, diario e affidabilità non devono mai leggere i file veri di `dati/` (scelte importate, giornate vere):
    un test che non indica il file esplicito userebbe i dati dell'utente e darebbe esiti diversi da PC a PC."""
    if request.node.get_closest_marker("percorsi_veri"):      # solo per chi controlla i percorsi di sempre (nessun file viene letto)
        return
    from fanta import affidabilita, diario, indicatori_consiglio, osservati, scelte
    d = tmp_path / "dati-personali-finti"
    for modulo, nome, file in ((scelte, "FILE_SCELTE", "scelte.json"), (osservati, "FILE_OSSERVATI", "osservati.json"),
                               (diario, "FILE", "diario.json"), (affidabilita, "FILE", "affidabilita.json"),
                               (indicatori_consiglio, "FILE", "indicatori-consiglio.json")):
        monkeypatch.setattr(modulo, nome, d / file)
    from fanta import immagini                                # stemmi e maglie: mai nella cartella della lega (anche quella di esempio)
    monkeypatch.setattr(immagini, "CARTELLA", d / "immagini")


@pytest.fixture(autouse=True)
def _consigliate_in_cartella_finta(tmp_path, monkeypatch):
    """Le consigliate già mostrate (`consigli.FILE_CONSIGLIATE`) mai nel file vero di `dati/`: ogni test parte senza, e quella
    ricordata da un test non cambia la consigliata di un altro."""
    from fanta import consigli
    monkeypatch.setattr(consigli, "FILE_CONSIGLIATE", tmp_path / "consigliate-finte.json")


@pytest.fixture
def multiutente(tmp_path, monkeypatch):
    """Modalità multiutente accesa su una cartella temporanea (la vera `dati/` non si tocca), con password veloci da calcolare
    e limiti nuovi (il database dei limiti sta nella cartella temporanea). FANTA_PROXY=1: l'indirizzo di chi chiede si legge da X-Forwarded-For, così i test lo scelgono loro."""
    from fanta import account
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "utenti-prova"))
    monkeypatch.setenv("FANTA_PROXY", "1")
    monkeypatch.delenv("MAX_UTENTI", raising=False)
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 4, "r": 8, "p": 1})
    orologio = Orologio()
    orologio.t = 1000.0
    monkeypatch.setattr(account, "_orologio", lambda: orologio.t)
    yield orologio


@pytest.fixture
def dati_isolati(tmp_path, monkeypatch):
    """Se per un errore una rotta risultasse aperta, il test non deve poter toccare i dati veri né fare cose vere (aggiornamenti,
    avvisi): tutti i file personali vanno in una cartella temporanea e le azioni verso l'esterno sono spente."""
    from fanta import affidabilita, archivio, diario, feedback, immagini, notifiche, osservati, pianificatore, push, scelte, server
    d = tmp_path / "dati-finti"
    monkeypatch.setattr(pianificatore, "file_blocco", lambda: d / "blocco")     # il blocco dell'aggiornamento, non ~/.cache vero
    for modulo, nome, percorso in ((server, "FILE_REGOLE", d / "regole.json"), (server, "FILE_ROSE", d / "rose.json"),
                                   (server, "FILE_MOVIMENTI", d / "movimenti.json"), (server, "FILE_ICONA", d / "icona.json"),
                                   (server, "RADICE", d), (scelte, "FILE_SCELTE", d / "scelte.json"),
                                   (osservati, "FILE_OSSERVATI", d / "osservati.json"), (diario, "FILE", d / "diario.json"),
                                   (affidabilita, "FILE", d / "affidabilita.json"),
                                   (immagini, "CARTELLA", d / "immagini"), (push, "FILE_VAPID", d / "vapid.json"),
                                   (push, "FILE_ISCRIZIONI", d / "push.json"), (notifiche, "FILE_IMPOSTAZIONI", d / "avvisi.json"),
                                   (notifiche, "FILE_STATO", d / "n.json"), (notifiche, "FILE_PROMEMORIA", d / "p.json")):
        monkeypatch.setattr(modulo, nome, percorso)
    try:                                           # nella versione pubblica il modulo delle foto non c'è
        from fanta import foto
        monkeypatch.setattr(foto, "CARTELLA", d / "foto")
    except ImportError:
        pass
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "archivio-finto" / "fanta.sqlite"))     # archivio vuoto, non quello vero
    monkeypatch.setattr(server.aggiorna, "esegui", lambda **k: [])
    monkeypatch.setattr(server, "_scalda", lambda *a, **k: None)
    monkeypatch.setattr(server, "_versione_dati", lambda: None)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a, **k: False)
    monkeypatch.setattr(push, "invia", lambda *a, **k: 0)
    monkeypatch.setattr(feedback, "_canale", lambda: None)        # «Scrivici»: niente avvisi sul canale vero del titolare
    return d


@pytest.fixture(autouse=True)
def _ricerche_gia_contate_azzerate():
    """Le richieste già contate oggi si ricordano in memoria (vedi limiti.conta): ogni test riparte da zero."""
    from fanta import limiti
    limiti._gia_contate.clear()
    yield
    limiti._gia_contate.clear()


NODE_ITALIANO = str(Path(__file__).resolve().parent / "node_italiano.cjs")


@pytest.fixture(autouse=True)
def _node_in_italiano(monkeypatch):
    """I test del codice web girano con Node, che prende navigator.language dalla lingua del sistema (inglese sui server
    di GitHub, italiano sul PC): l'app sceglierebbe l'inglese. Ogni Node lanciato dai test precarica node_italiano.cjs."""
    vero = subprocess.run

    def run(args, *a, **k):
        if isinstance(args, (list, tuple)) and args and os.path.basename(str(args[0])).lower() in ("node", "node.exe"):
            args = [args[0], "--require", NODE_ITALIANO, *args[1:]]
        return vero(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", run)
