"""Registri degli script del server e file delle variabili del servizio (script/server/registri.sh, leggi-ambiente.sh).

Gli script dei cron girano fuori dal recinto del servizio, ma scrivono i loro registri in cartelle che scrive anche il servizio
(dati/ dell'app, ~/.cache). Qui si controlla che:
- la rotazione dei registri usi sempre un file di lavoro nuovo (un file che c'era già con il nome di prima non si tocca);
- un collegamento simbolico al posto di un registro fermi lo script senza scrivere niente (prove saltate dove il sistema non crea
  collegamenti, per esempio Windows senza privilegio: girano in CI su Linux);
- il file delle variabili del servizio si legga prima da un percorso di root fuori dalla cartella dell'app, e gli esempi di systemd
  nel repository non mettano mai un EnvironmentFile dove il servizio scrive.
Case finte in cartelle temporanee, finti python e flock: niente server vero, niente rete."""
import os
import stat
import sys
from pathlib import Path

import pytest

from test_script_server import BASH, SCRIPT, _lancia, _msys, _scrivi, _stub, con_bash

RADICE = Path(__file__).resolve().parent.parent
AMBIENTE_NUOVO = "/etc/schieraxi/fantacalcio.env"

# script dei cron della produzione che scrivono un registro in dati/: nome -> (registro, uscita del finto python)
CON_REGISTRO_IN_DATI = {
    "sentinella.sh": ("sentinella.log", 0),
    "backup-serale.sh": ("backup.log", 1),          # il registro si scrive solo quando la copia non riesce
    "promemoria.sh": ("promemoria.log", 0),
    "aggiorna.sh": ("aggiorna.log", 0),
}


def _collega(bersaglio, collegamento):
    """Un collegamento simbolico, oppure la prova si salta (Windows senza privilegio: gira in CI su Linux)."""
    Path(collegamento).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(bersaglio, collegamento)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"questo sistema non crea collegamenti simbolici ({e}): la prova gira in CI su Linux")


def _file(percorso, testo):
    percorso = Path(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(testo, encoding="utf-8", newline="\n")
    return percorso


def _casa(tmp_path, uscita_python=0):
    """Una casa del server con ~/fantacalcio, gli script del server copiati dentro, un finto python e un finto flock."""
    casa = tmp_path / "casa"
    app = casa / "fantacalcio"
    for f in SCRIPT.glob("*.sh"):
        _scrivi(app, f"script/server/{f.name}", f.read_text(encoding="utf-8").replace("\r\n", "\n"))
    (app / ".venv" / "bin").mkdir(parents=True)
    (app / "dati").mkdir()
    chiamate = tmp_path / "chiamate.txt"
    _stub(app / ".venv" / "bin", "python", f'echo "python $*" >> "{_msys(chiamate)}"\n'
                                           f'echo "uscita del finto python"\nexit {uscita_python}')
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_, "flock", "exit 0")
    _stub(bin_, "logger", f'echo "logger $*" >> "{_msys(tmp_path / "journal.txt")}"')      # il journal finto
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(casa),
           "SCHIERAXI_CANALE": _msys(tmp_path / "nessun-canale"), "SCHIERAXI_AMBIENTE": _msys(tmp_path / "nessun-ambiente")}
    return app, env, chiamate


def _esegui(app, env, nome):
    return _lancia([BASH, (app / "script" / "server" / nome).as_posix()], env=env)


# ---------------------------------------------------------------- rotazione dei registri

@con_bash
@pytest.mark.parametrize("nome", sorted(CON_REGISTRO_IN_DATI))
def test_registri_rotazione_con_un_file_di_lavoro_sempre_nuovo(tmp_path, nome):
    registro, uscita = CON_REGISTRO_IN_DATI[nome]
    app, env, _ = _casa(tmp_path, uscita)
    gia_presente = app / "dati" / f"{registro}.tmp"
    gia_presente.write_text("INTATTO", encoding="utf-8")
    r = _esegui(app, env, nome)
    assert r.returncode == 0, r.stderr
    assert gia_presente.read_text(encoding="utf-8") == "INTATTO"           # il file che c'era non si tocca
    assert "uscita del finto python" in (app / "dati" / registro).read_text(encoding="utf-8")
    assert sorted(p.name for p in (app / "dati").glob(f"{registro}*")) == [registro, f"{registro}.tmp"]   # niente file di lavoro lasciati


@con_bash
def test_registri_backup_dati_rotazione_con_un_file_di_lavoro_sempre_nuovo(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "backup-dati.log.tmp").write_text("INTATTO", encoding="utf-8")
    radice = tmp_path / "app"
    _scrivi(radice, "dati/account.sqlite", "non e' un database")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_, "flock", "exit 0")
    _stub(bin_, "python-finto", "exit 1")                                   # la copia del database non riesce: si scrive il registro
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(tmp_path),
           "FANTA_RADICE": _msys(radice), "FANTA_BACKUP_DIR": _msys(tmp_path / "copie"), "FANTA_CACHE": _msys(cache),
           "FANTA_PYTHON": "python-finto"}
    r = _lancia([BASH, (SCRIPT / "backup-dati.sh").as_posix()], env=env)
    assert r.returncode == 1
    assert "integrità" in (cache / "backup-dati.log").read_text(encoding="utf-8")
    assert (cache / "backup-dati.log.tmp").read_text(encoding="utf-8") == "INTATTO"


@con_bash
def test_registri_ruota_registro_tiene_le_ultime_righe(tmp_path):
    registro = tmp_path / "x.log"
    registro.write_text("".join(f"riga {i}\n" for i in range(10)), encoding="utf-8")
    r = _lancia([BASH, "-c", '. "$1"; ruota_registro "$2" 3', "prova", (SCRIPT / "registri.sh").as_posix(), _msys(registro)])
    assert r.returncode == 0, r.stderr
    assert registro.read_text(encoding="utf-8") == "riga 7\nriga 8\nriga 9\n"
    assert [p.name for p in tmp_path.iterdir()] == ["x.log"]


@con_bash
@pytest.mark.parametrize("gia_presente", ["file", "collegamento"])
def test_registri_ruota_registro_non_usa_un_nome_di_lavoro_gia_presente(tmp_path, gia_presente):
    """Al nome del file di lavoro c'e' gia' qualcosa (un file, o un collegamento verso un altro file): non si scrive li' e il
    registro resta com'era. Su Windows `ln -s` di Git fa una copia: la prova vale comunque come «file gia' presente»."""
    registro = _file(tmp_path / "x.log", "".join(f"riga {i}\n" for i in range(10)))
    bersaglio = _file(tmp_path / "bersaglio.txt", "INTATTO")
    prepara = 'echo INTATTO > "$2.$$"' if gia_presente == "file" else 'ln -s "$3" "$2.$$"'
    r = _lancia([BASH, "-c", '. "$1"; ' + prepara + '; ruota_registro "$2" 3; echo "uscita=$?"', "prova",
                 (SCRIPT / "registri.sh").as_posix(), _msys(registro), _msys(bersaglio)])
    assert "uscita=1" in r.stdout, r.stdout + r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert registro.read_text(encoding="utf-8").count("riga") == 10            # non ruotato


def test_registri_file_di_blocco_aperti_senza_svuotarli():
    """I file di blocco stanno in ~/.cache, che scrive anche il servizio: si aprono in aggiunta (>>), che non svuota un file
    raggiunto attraverso un collegamento."""
    for f in [*SCRIPT.glob("*.sh"), SCRIPT / "prova" / "esporta-archivio-prova.sh"]:     # questo gira con l'utente della produzione
        for riga in f.read_text(encoding="utf-8").splitlines():
            parti = riga.strip().split()
            if len(parti) >= 2 and parti[0] == "exec" and parti[1][:1].isdigit() and not parti[1].endswith(">&-"):
                assert parti[1][1:3] == ">>", f"{f.name}: {riga.strip()}"


@con_bash
def test_registri_blocco_collegato_non_si_svuota(tmp_path):
    app, env, _ = _casa(tmp_path)
    bersaglio = _file(tmp_path / "bersaglio.txt", "INTATTO")
    _collega(bersaglio, tmp_path / "casa" / ".cache" / "fantacalcio" / "blocco-sentinella")
    r = _esegui(app, env, "sentinella.sh")
    assert r.returncode == 0, r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"


# ---------------------------------------------------------------- collegamenti simbolici al posto dei registri

@con_bash
@pytest.mark.parametrize("quale", ["registro", "file di lavoro"])
@pytest.mark.parametrize("nome", sorted(CON_REGISTRO_IN_DATI))
def test_registri_collegati_fermano_lo_script_senza_scrivere(tmp_path, nome, quale):
    registro, uscita = CON_REGISTRO_IN_DATI[nome]
    app, env, chiamate = _casa(tmp_path, uscita)
    bersaglio = _file(tmp_path / "bersaglio.txt", "INTATTO")
    _collega(bersaglio, app / "dati" / (registro if quale == "registro" else f"{registro}.tmp"))
    r = _esegui(app, env, nome)
    assert r.returncode == 1
    assert "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert not chiamate.exists()                                            # non parte niente
    journal = (tmp_path / "journal.txt").read_text(encoding="utf-8")
    assert "-t schieraxi" in journal and "collegamento" in journal          # resta scritto anche se cron butta l'uscita


@con_bash
@pytest.mark.skipif(sys.platform == "win32", reason="permessi POSIX")
def test_registri_permessi_non_seguono_i_collegamenti(tmp_path):
    app, env, _ = _casa(tmp_path)
    bersaglio = tmp_path / "bersaglio.txt"
    bersaglio.write_text("INTATTO", encoding="utf-8")
    bersaglio.chmod(0o644)
    _collega(bersaglio, app / "dati" / "altro.log")
    vero = app / "dati" / "vero.log"
    vero.write_text("x", encoding="utf-8")
    vero.chmod(0o644)
    r = _esegui(app, env, "promemoria.sh")
    assert r.returncode == 0, r.stderr
    assert stat.S_IMODE(bersaglio.stat().st_mode) == 0o644
    assert stat.S_IMODE(vero.stat().st_mode) == 0o600


@con_bash
@pytest.mark.parametrize("nome", ["pubblicazione.log", "pubblicazione.log.tmp"])
def test_registri_aggiorna_app_in_produzione_con_il_registro_collegato_non_scrive(tmp_path, nome):
    app, env, chiamate = _casa(tmp_path)
    bersaglio = tmp_path / "bersaglio.txt"
    bersaglio.write_text("INTATTO", encoding="utf-8")
    _collega(bersaglio, app / "dati" / nome)
    r = _lancia([BASH, (SCRIPT / "aggiorna-app.sh").as_posix()], env={**env, "SCHIERAXI_SRC": _msys(tmp_path / "manca")})
    assert r.returncode == 1
    assert "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"
    assert not (tmp_path / "manca").exists() and not chiamate.exists()


@con_bash
def test_registri_pubblica_sito_con_il_registro_collegato_non_scrive(tmp_path):
    cache = tmp_path / "cache"
    bersaglio = tmp_path / "bersaglio.txt"
    bersaglio.write_text("INTATTO", encoding="utf-8")
    _collega(bersaglio, cache / "pubblica-sito.log")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_, "flock", "exit 0")
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(tmp_path),
           "FANTA_CACHE": _msys(cache), "SCHIERAXI_SRC": _msys(tmp_path / "manca")}
    r = _lancia([BASH, (SCRIPT / "pubblica-sito.sh").as_posix()], env=env)
    assert r.returncode == 1 and "collegamento" in r.stderr
    assert bersaglio.read_text(encoding="utf-8") == "INTATTO"


# ---------------------------------------------------------------- file delle variabili del servizio

def _leggi(tmp_path, nuovo, vecchio):
    """Lancia leggi_ambiente con il file nuovo indicato (SCHIERAXI_AMBIENTE) e il vecchio come argomento; stampa FANTA_X."""
    return _lancia([BASH, "-c", '. "$1"; leggi_ambiente "$2"; printf "%s" "${FANTA_X:-}"', "prova",
                    (SCRIPT / "leggi-ambiente.sh").as_posix(), _msys(vecchio)],
                   env={**os.environ, "SCHIERAXI_AMBIENTE": _msys(nuovo)})


@con_bash
def test_ambiente_del_servizio_si_legge_prima_dal_file_di_root(tmp_path):
    nuovo = _file(tmp_path / "etc" / "fantacalcio.env", "FANTA_X=nuovo\n")
    vecchio = _file(tmp_path / "dati" / "ambiente.env", "FANTA_X=vecchio\n")
    r = _leggi(tmp_path, nuovo, vecchio)
    assert r.returncode == 0, r.stderr
    assert r.stdout == "nuovo" and r.stderr == ""


@con_bash
def test_ambiente_del_servizio_nel_posto_vecchio_vale_ancora_con_un_avviso(tmp_path):
    vecchio = _file(tmp_path / "dati" / "ambiente.env", "FANTA_X=vecchio\n")
    r = _leggi(tmp_path, tmp_path / "etc" / "fantacalcio.env", vecchio)     # il file di root non c'e'
    assert r.returncode == 0, r.stderr
    assert r.stdout == "vecchio"
    assert "fantacalcio.env" in r.stderr                                    # dice dove spostarlo


@con_bash
def test_ambiente_del_servizio_senza_file_non_cambia_niente(tmp_path):
    r = _leggi(tmp_path, tmp_path / "manca.env", tmp_path / "manca-anche.env")
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


def test_ambiente_del_servizio_percorso_predefinito_fuori_dalla_cartella_dell_app():
    testo = (SCRIPT / "leggi-ambiente.sh").read_text(encoding="utf-8")
    assert f'"${{SCHIERAXI_AMBIENTE:-{AMBIENTE_NUOVO}}}"' in testo


def _righe_environmentfile(testo):
    for riga in testo.splitlines():
        chiave, _, valore = riga.strip().partition("=")
        if chiave.strip() == "EnvironmentFile":
            yield valore.strip().lstrip("-")


def test_esempi_di_produzione_senza_file_di_variabili_dove_scrive_il_servizio():
    """systemd legge un EnvironmentFile come root, prima del recinto, e segue i collegamenti simbolici: il file deve stare dove il
    servizio non scrive (di root, sotto /etc), mai nella cartella dell'app, nella casa o in ~/.cache."""
    esempi = [*SCRIPT.glob("*.service"), *SCRIPT.glob("*.conf.esempio")]
    assert SCRIPT / "ambiente.conf.esempio" in esempi                       # il drop-in delle variabili, come esempio
    trovati = []
    for f in esempi:
        for p in _righe_environmentfile(f.read_text(encoding="utf-8")):
            trovati.append(p)
            assert p.startswith("/etc/"), f"{f.name}: {p}"
            assert "/home" not in p and "dati" not in p and ".cache" not in p and "fantacalcio/" not in p, f"{f.name}: {p}"
    assert trovati == [AMBIENTE_NUOVO]


def test_ripristino_mette_le_variabili_nel_file_di_root():
    testo = (RADICE / "docs" / "RIPRISTINO-SERVER.md").read_text(encoding="utf-8")
    assert AMBIENTE_NUOVO in testo
    assert "0640" in testo or "640" in testo
    assert "**`dati/ambiente.env`**" not in testo                           # non e' piu' il posto delle variabili
