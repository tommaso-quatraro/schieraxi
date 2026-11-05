"""Foto «prova-url» dell'app iOS (`ios/scripts/screenshot.sh`, issue #250).

`simctl openurl` apre i link schieraxi:// come se arrivassero da un'altra app: il simulatore chiedeva «Open in "SchieraXI"?» e
le due foto mostravano la finestra di sistema invece della schermata d'arrivo. Ora lo script, prima dei link, approva lo schema
per chi li apre dal simulatore (CoreSimulatorBridge): la finestra non compare. Simulatore finto: si prova l'ordine dei comandi.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "ios" / "scripts" / "screenshot.sh"
PROGETTO = RADICE / "ios" / "project.yml"
DOMINIO = "com.apple.launchservices.schemeapproval"
CHI_APRE = "com.apple.CoreSimulator.CoreSimulatorBridge"   # il processo che apre i link di «simctl openurl»


def _trova_bash():
    # su Windows `bash` può essere quello di WSL (System32): meglio quello di Git (usr\bin\bash.exe lascia il PATH com'è)
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()


def _testo():
    return SCRIPT.read_text(encoding="utf-8")


def _funzione(testo, nome):
    """Una funzione di screenshot.sh, da «nome() {» alla prima «}» a inizio riga. Vuoto se non c'è."""
    trovata = re.search(rf"^{nome}\(\) \{{\n.*?^\}}\n", testo, re.S | re.M)
    return trovata.group(0) if trovata else ""


def _schema_e_app():
    """Lo schema dei link e il bundle id dell'app come li dichiara ios/project.yml (non si cambiano: SideStore)."""
    progetto = PROGETTO.read_text(encoding="utf-8")
    schema = re.search(r"CFBundleURLSchemes:\s*\n\s*-\s*(\S+)", progetto)
    app = re.search(r"PRODUCT_BUNDLE_IDENTIFIER:\s*(\S+)", progetto)
    assert schema and app, "schema o bundle id non trovati in ios/project.yml"
    return schema.group(1), app.group(1)


def _prova_url(tmp_path, defaults_fallisce=False):
    """Lancia `prova_url` di screenshot.sh con xcrun e sleep finti; torna (comandi in ordine, uscita, attese in secondi)."""
    testo = _testo()
    funzione = _funzione(testo, "prova_url")
    assert funzione, "screenshot.sh non ha la funzione prova_url (le foto prova-url_openurl-*)"
    id_app = re.search(r'^ID_APP="([^"]+)"', testo, re.M)
    assert id_app, "ID_APP non trovato in screenshot.sh"
    uscita = tmp_path / "foto"
    uscita.mkdir()
    registro = tmp_path / "comandi.txt"
    righe = [
        f'ID_APP="{id_app.group(1)}"', f'USCITA="{uscita.as_posix()}"', "ERRORI=0",
        f'REGISTRO="{registro.as_posix()}"', f"DEFAULTS_FALLISCE={1 if defaults_fallisce else 0}",
        # simulatore finto: annota ogni comando; «defaults write» non riesce se gli si dice di fallire
        'xcrun() { echo "$*" >> "$REGISTRO"; [ "$DEFAULTS_FALLISCE" = 1 ] && [ "$4" = defaults ] && return 1; return 0; }',
        'sleep() { echo "sleep $1" >> "$REGISTRO"; }',
        funzione,
        "prova_url UDID",
        'echo "ERRORI=$ERRORI"',
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente)
    assert r.returncode == 0, r.stderr
    comandi = registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []
    attese = sum(float(c.split()[1]) for c in comandi if c.startswith("sleep "))
    return [c for c in comandi if not c.startswith("sleep ")], r.stdout, attese, uscita


def _indice(comandi, inizio):
    trovati = [i for i, c in enumerate(comandi) if c.startswith(inizio)]
    assert trovati, f"manca il comando «{inizio}…» in:\n" + "\n".join(comandi)
    return trovati[0]


def test_lo_script_delle_foto_fa_la_prova_url_sull_iphone():
    testo = _testo()
    assert _funzione(testo, "prova_url"), "screenshot.sh non ha la funzione prova_url"
    assert 'prova_url "$UDID_IPHONE"' in testo


@pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")
def test_lo_schema_e_approvato_prima_di_aprire_i_link(tmp_path):
    """Issue #250: senza approvazione il simulatore chiede «Open in "SchieraXI"?» e la foto mostra la finestra di sistema."""
    schema, app = _schema_e_app()
    comandi, stdout, _, _ = _prova_url(tmp_path)
    approva = f"simctl spawn UDID defaults write {DOMINIO} {CHI_APRE}-->{schema} -string {app}"
    assert approva in comandi, "manca l'approvazione dello schema:\n" + "\n".join(comandi)
    assert comandi.index(approva) < _indice(comandi, "simctl openurl "), "lo schema va approvato PRIMA del primo link"
    assert "ERRORI=0" in stdout


@pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")
def test_lo_schema_approvato_e_quello_dei_link_in_minuscolo(tmp_path):
    """Il simulatore confronta la chiave con lo schema in minuscolo: con le maiuscole la finestra torna."""
    schema, _ = _schema_e_app()
    comandi, _, _, _ = _prova_url(tmp_path)
    approvati = [c for c in comandi if f" {DOMINIO} " in c]
    assert approvati and all(f"{CHI_APRE}-->{schema.lower()} " in c for c in approvati)
    aperti = [c.split()[-1] for c in comandi if c.startswith("simctl openurl ")]
    assert aperti and all(u.startswith(f"{schema}://") for u in aperti)


@pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")
def test_ogni_link_si_fotografa_dopo_averlo_aperto_con_attese_brevi(tmp_path):
    comandi, _, attese, uscita = _prova_url(tmp_path)
    foto_formazione = f"simctl io UDID screenshot {uscita.as_posix()}/prova-url_openurl-formazione.png"
    foto_giocatore = f"simctl io UDID screenshot {uscita.as_posix()}/prova-url_openurl-giocatore.png"
    ordine = [
        _indice(comandi, "simctl openurl UDID schieraxi://formazione"),
        _indice(comandi, foto_formazione),
        _indice(comandi, "simctl openurl UDID schieraxi://giocatore/203"),
        _indice(comandi, foto_giocatore),
    ]
    assert ordine == sorted(ordine), "\n".join(comandi)
    assert attese <= 10, f"attese fisse troppo lunghe: {attese} secondi"


@pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")
def test_se_l_approvazione_non_riesce_e_un_problema_ma_le_foto_si_fanno(tmp_path):
    comandi, stdout, _, uscita = _prova_url(tmp_path, defaults_fallisce=True)
    assert "ERRORI=1" in stdout
    assert "ATTENZIONE" in stdout
    assert any(c.endswith(f"{uscita.as_posix()}/prova-url_openurl-giocatore.png") for c in comandi)
