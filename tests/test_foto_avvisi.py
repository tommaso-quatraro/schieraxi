"""Avvisi di sistema nelle foto dell'app iOS (`ios/scripts/avvisi.sh`, issue #393).

Il simulatore, due o tre minuti dopo l'accensione, mostra per pochi secondi «Ready for Apple Intelligence» (un avviso di
sistema, non dell'app) e una foto scattata in quel momento lo porta dentro. Lo manda il servizio di Apple, lo si vede nel
registro del simulatore: gli script delle foto ascoltano quel registro, e se un avviso è comparso durante lo scatto aspettano
che sparisca e rifanno la foto. Qui si provano le funzioni di bash con un orologio finto.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "ios" / "scripts" / "avvisi.sh"
FOTO = RADICE / "ios" / "scripts" / "screenshot.sh"
WIDGET = RADICE / "ios" / "scripts" / "screenshot_widget.sh"


def _trova_bash():
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
serve_bash = pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")


def _bash(tmp_path, corpo, stdin=""):
    """Esegue `corpo` dopo aver caricato avvisi.sh, con `date +%s` e `sleep` finti: l'ora sta in $ORA, le attese in $ATTESE."""
    flag = tmp_path / "flag.txt"
    ora = tmp_path / "ora.txt"
    attese = tmp_path / "attese.txt"
    ora.write_text("1000\n", encoding="utf-8")
    righe = [
        f'source "{SCRIPT.as_posix()}"',
        f'AVVISI_FLAG="{flag.as_posix()}"',
        f'date() {{ cat "{ora.as_posix()}"; }}',
        f'sleep() {{ echo "$1" >> "{attese.as_posix()}"; }}',
        corpo,
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], input=stdin, capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=ambiente)
    return r, flag, attese


def _attese(percorso):
    return [float(x) for x in percorso.read_text(encoding="utf-8").split()] if percorso.exists() else []


def test_gli_script_delle_foto_usano_gli_avvisi():
    assert SCRIPT.exists(), "manca ios/scripts/avvisi.sh"
    for script in (FOTO, WIDGET):
        testo = script.read_text(encoding="utf-8")
        assert "avvisi.sh" in testo, f"{script.name} non carica avvisi.sh"
        assert "avvisi_avvia" in testo and "avvisi_comparsi" in testo, f"{script.name} non controlla gli avvisi"


def test_il_registro_ascoltato_e_quello_dell_avviso_di_apple_intelligence():
    """Il filtro deve prendere sia l'invito di Apple Intelligence sia la creazione di una notifica del sistema."""
    testo = SCRIPT.read_text(encoding="utf-8")
    assert "Posted new Readiness CFU" in testo
    assert "com.apple.usernotificationsd" in testo and "NotificationsPipeline" in testo


@serve_bash
def test_senza_avvisi_niente_da_rifare(tmp_path):
    r, _, attese = _bash(tmp_path, 'echo 0 > "$AVVISI_FLAG"; avvisi_comparsi 990 && echo SI || echo NO; avvisi_aspetta')
    assert r.stdout.split() == ["NO"], r.stderr
    assert _attese(attese) == []


@serve_bash
def test_il_registro_annota_l_ora_solo_per_le_righe_con_la_data(tmp_path):
    righe = (
        "Filtering the log data using \"subsystem == ...\"\n"
        "getpwuid_r did not find a match for uid 501\n"
        "Timestamp               Ty Process[PID:TID]\n"
    )
    r, flag, _ = _bash(tmp_path, 'echo 0 > "$AVVISI_FLAG"; avvisi_registra; cat "$AVVISI_FLAG"', stdin=righe)
    assert r.stdout.split() == ["0"], "le righe di intestazione non sono avvisi"
    riga = "2026-11-06 00:35:12.002 Df generativeexperiencesd[3906:bcac] [com.apple.GenerativeModels:cfu] Posted new Readiness CFU\n"
    r, _, _ = _bash(tmp_path, 'echo 0 > "$AVVISI_FLAG"; avvisi_registra; cat "$AVVISI_FLAG"', stdin=righe + riga)
    assert r.stdout.split() == ["1000"], r.stderr


@serve_bash
@pytest.mark.parametrize("inizio, atteso", [
    (1000, "SI"),   # l'avviso è comparso durante lo scatto
    (1005, "SI"),   # comparso 5 secondi prima dell'inizio: sullo schermo c'è ancora
    (1009, "SI"),
    (1011, "NO"),   # sparito da un pezzo
])
def test_la_foto_e_da_rifare_se_l_avviso_era_ancora_sullo_schermo(tmp_path, inizio, atteso):
    r, _, _ = _bash(tmp_path, f'echo 1000 > "$AVVISI_FLAG"; avvisi_comparsi {inizio} && echo SI || echo NO')
    assert r.stdout.split() == [atteso], r.stderr


@serve_bash
def test_si_aspetta_che_l_avviso_sparisca(tmp_path):
    # avviso alle 1000, ora 1003, l'avviso resta 10 secondi: mancano 7 secondi
    (tmp_path / "ora.txt").write_text("1003\n", encoding="utf-8")
    r, _, attese = _bash(tmp_path, 'echo 1000 > "$AVVISI_FLAG"; date() { echo 1003; }; avvisi_aspetta')
    assert r.returncode == 0, r.stderr
    assert _attese(attese) == [7.0]


@serve_bash
def test_se_l_avviso_e_gia_sparito_non_si_aspetta(tmp_path):
    r, _, attese = _bash(tmp_path, 'echo 900 > "$AVVISI_FLAG"; avvisi_aspetta')
    assert r.returncode == 0, r.stderr
    assert _attese(attese) == []


@serve_bash
def test_un_file_di_stato_rovinato_vale_come_nessun_avviso(tmp_path):
    r, _, attese = _bash(tmp_path, 'printf "" > "$AVVISI_FLAG"; avvisi_comparsi 0 && echo SI || echo NO; avvisi_aspetta')
    assert r.stdout.split() == ["NO"], r.stderr
    assert _attese(attese) == []


def test_lo_script_delle_foto_rifa_la_foto_se_l_avviso_e_comparso():
    testo = FOTO.read_text(encoding="utf-8")
    scatta = re.search(r"^scatta\(\) \{\n.*?^\}\n", testo, re.S | re.M)
    assert scatta, "funzione scatta non trovata in screenshot.sh"
    corpo = scatta.group(0)
    assert corpo.count("schermo_fermo.py") == 2, "la foto va rifatta (due scatti nel codice) se compare un avviso"
    assert "avvisi_comparsi" in corpo and "avvisi_aspetta" in corpo
    assert corpo.index("avvisi_comparsi") < corpo.rindex("schermo_fermo.py")
    # il simulatore ascolta gli avvisi appena acceso e smette quando si spegne
    avvia = re.search(r"^avvia_simulatore\(\) \{\n.*?^\}\n", testo, re.S | re.M)
    spegni = re.search(r"^spegni_simulatore\(\) \{\n.*?^\}\n", testo, re.S | re.M)
    assert avvia and "avvisi_avvia" in avvia.group(0)
    assert spegni and "avvisi_ferma" in spegni.group(0)
