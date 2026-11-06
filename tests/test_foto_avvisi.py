"""Avvisi di sistema nelle foto dell'app iOS (`ios/scripts/avvisi.sh`, issue #393).

Il simulatore, due o tre minuti dopo l'accensione, mostra per pochi secondi «Ready for Apple Intelligence» (un avviso di
sistema, non dell'app) e una foto scattata in quel momento lo porta dentro. Lo manda il servizio di Apple e si vede nel
registro del simulatore. Gli script delle foto, dopo l'accensione, aspettano che l'avviso compaia e sparisca PRIMA di fotografare
(il registro in tempo reale, «log stream», arrivava con 40 secondi di ritardo: non serviva). Qui si provano le funzioni di bash
con un simulatore e un orologio finti.
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

RIGA_AVVISO = ("2026-11-06 05:18:34.770 Df generativeexperiencesd[5393:bdb3] [com.apple.GenerativeModels:cfu] "
               "Posted new Readiness CFU with item: <FLFollowUpItem")


def _bash(tmp_path, corpo, avviso_dopo=None):
    """Esegue `corpo` dopo aver caricato avvisi.sh con `xcrun`, `date +%s` e `sleep` finti.

    Ogni sleep fa passare i secondi che chiede. «log show» risponde con la riga d'avviso solo da `avviso_dopo` secondi
    dall'inizio in poi (None = mai). Torna (processo, chiamate a xcrun, secondi dormiti)."""
    chiamate = tmp_path / "chiamate.txt"
    ora = tmp_path / "ora.txt"
    ora.write_text("1000\n", encoding="utf-8")
    soglia = "-1" if avviso_dopo is None else str(1000 + avviso_dopo)
    righe = [
        f'source "{SCRIPT.as_posix()}"',
        f'ORA="{ora.as_posix()}"; CHIAMATE="{chiamate.as_posix()}"; SOGLIA={soglia}',
        'date() { cat "$ORA"; }',
        'sleep() { echo "sleep $1" >> "$CHIAMATE"; echo $(( $(cat "$ORA") + $1 )) > "$ORA"; }',
        'xcrun() {',
        '  echo "xcrun $*" >> "$CHIAMATE"',
        f'  case "$*" in *"log show"*) [ "$SOGLIA" -ge 0 ] && [ "$(cat "$ORA")" -ge "$SOGLIA" ] && echo "{RIGA_AVVISO}"; return 0 ;; esac',
        '}',
        corpo,
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente)
    righe_chiamate = chiamate.read_text(encoding="utf-8").splitlines() if chiamate.exists() else []
    dormiti = sum(float(c.split()[1]) for c in righe_chiamate if c.startswith("sleep "))
    return r, [c for c in righe_chiamate if c.startswith("xcrun ")], dormiti


def test_gli_script_delle_foto_aspettano_gli_avvisi_prima_di_fotografare():
    assert SCRIPT.exists(), "manca ios/scripts/avvisi.sh"
    for script in (FOTO, WIDGET):
        testo = script.read_text(encoding="utf-8")
        assert 'source "$(dirname "$0")/avvisi.sh"' in testo, f"{script.name} non carica avvisi.sh"
        assert "avvisi_avvia" in testo and "avvisi_attendi" in testo and "avvisi_ferma" in testo, script.name
    # screenshot.sh: l'attesa viene dopo il lancio di prova e prima del primo giro di foto, per iPhone, iPad e foto dal vero
    foto = FOTO.read_text(encoding="utf-8")
    for udid, primo_giro in (("UDID_IPHONE", 'giro "$UDID_IPHONE" iphone_scuro'), ("UDID_IPAD", 'giro "$UDID_IPAD" ipad_scuro_verticale'),
                             ("UDID_VERO", 'giro_vero "$UDID_VERO" "${QUALE}_scuro"')):
        attesa = f'avvisi_attendi "${udid}"'
        assert attesa in foto, attesa
        assert foto.index(attesa) < foto.index(primo_giro), f"{udid}: l'attesa va prima delle foto"
    avvia = re.search(r"^avvia_simulatore\(\) \{\n.*?^\}\n", foto, re.S | re.M)
    spegni = re.search(r"^spegni_simulatore\(\) \{\n.*?^\}\n", foto, re.S | re.M)
    assert avvia and "avvisi_avvia" in avvia.group(0)
    assert spegni and "avvisi_ferma" in spegni.group(0) and spegni.group(0).index("avvisi_ferma") < spegni.group(0).index("shutdown")
    assert "avvisi_riepilogo" in foto


def test_il_registro_interrogato_e_quello_dell_avviso_di_apple_intelligence():
    """Il filtro deve prendere sia l'invito di Apple Intelligence sia la creazione di una notifica del sistema."""
    testo = SCRIPT.read_text(encoding="utf-8")
    assert "Posted new Readiness CFU" in testo
    assert "com.apple.usernotificationsd" in testo and "NotificationsPipeline" in testo
    assert "log show" in testo and "log stream" not in testo.replace("«log stream»", ""), "il registro in diretta arriva in ritardo"


@serve_bash
def test_se_l_avviso_compare_si_aspetta_che_sparisca_e_poi_si_va(tmp_path):
    # l'avviso compare dopo 170 secondi dall'accensione: ogni giro di attesa dura 5 secondi
    r, chiamate, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; echo "VISTO=$AVVISI_VISTO"', avviso_dopo=170)
    assert r.returncode == 0, r.stderr
    assert "VISTO=si" in r.stdout and "avviso visto" in r.stdout
    assert 170 <= dormiti <= 170 + 5 + 12, f"ha dormito {dormiti} secondi"
    # alla fine ha lasciato passare la pausa dell'avviso (12 secondi), non ha aspettato oltre
    assert dormiti >= 170 + 12 - 5
    assert all("UDID1" in c for c in chiamate if "log show" in c)
    assert any("log show" in c and "Posted new Readiness CFU" in c for c in chiamate)


@serve_bash
def test_se_l_avviso_e_gia_passato_quando_si_comincia_a_aspettare_basta_la_pausa(tmp_path):
    r, _, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; sleep 200; avvisi_attendi UDID1 400', avviso_dopo=100)
    assert r.returncode == 0, r.stderr
    assert dormiti == 200 + 12, "la riga d'avviso c'è già: si aspetta solo che sparisca"


@serve_bash
def test_se_l_avviso_non_compare_si_va_avanti_dopo_il_massimo(tmp_path):
    r, _, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 60; echo "VISTO=$AVVISI_VISTO"', avviso_dopo=None)
    assert r.returncode == 0, r.stderr
    assert "VISTO=no" in r.stdout and "ATTENZIONE" in r.stdout
    assert 60 <= dormiti <= 70, "l'attesa ha un tetto"


@serve_bash
def test_l_attesa_guarda_indietro_nel_registro_non_solo_gli_ultimi_secondi(tmp_path):
    # lo stesso simulatore riacceso non ripete l'avviso: se è già nel registro non si aspettano 400 secondi per niente
    r, chiamate, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400', avviso_dopo=0)
    assert r.returncode == 0, r.stderr
    finestre = [int(m.group(1)) for c in chiamate if (m := re.search(r"log show --last (\d+)s", c))]
    assert finestre and finestre[0] >= 3 * 3600, f"finestra troppo corta: {finestre}"
    assert dormiti == 12, "avviso già nel registro: basta la pausa"


@serve_bash
def test_prima_di_spegnere_si_controlla_se_l_avviso_e_comparso_dopo_l_attesa(tmp_path):
    # attesa di 30 secondi senza avviso; l'avviso compare a 100 secondi, quando le foto sono già cominciate
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 30; sleep 120; avvisi_ferma; avvisi_riepilogo', avviso_dopo=100)
    assert r.returncode == 0, r.stderr
    assert "comparso DOPO l'attesa" in r.stdout
    assert "comparsi dopo l'attesa: 1" in r.stdout and "controllare le foto" in r.stdout


@serve_bash
def test_senza_avvisi_tardivi_il_riepilogo_e_pulito(tmp_path):
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; avvisi_ferma; avvisi_riepilogo', avviso_dopo=20)
    assert r.returncode == 0, r.stderr
    assert "aspettati prima delle foto: 1; comparsi dopo l'attesa: 0" in r.stdout
    assert "controllare" not in r.stdout
