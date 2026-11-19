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


RIGA_ECO = ("2026-11-19 22:37:01.837 Df log[7199:0] [com.apple.log:] log run noninteractively, parent: 3640 (launchd_sim), "
            "args: 'log' 'show' '--last' '12s' '--style' 'compact' '--predicate' 'eventMessage CONTAINS Posted new Readiness CFU'")


RIGA_ALTRA = ("2026-11-06 05:00:00.000 Df SpringBoard[5284:8bf4] [com.apple.usernotificationsd:NotificationsPipeline] "
              "[create, [id=1111-2222, time=2026-11-06 05:00:00, bundle=com.example.altra], Time elapsed=0.057 sec]: Running step")


def _bash(tmp_path, corpo, avviso_dopo=None, eventi=None, altre=()):
    """Esegue `corpo` dopo aver caricato avvisi.sh con `xcrun`, `date +%s` e `sleep` finti.

    Ogni sleep fa passare i secondi che chiede. «log show» risponde, secondo il filtro e la finestra chiesti (`--last Ns`):
    - con la riga dell'invito di Apple Intelligence per ogni istante di `eventi` (secondi dall'inizio; `avviso_dopo` ne è
      la scorciatoia per uno solo; nessuno = mai);
    - con la riga di una notifica qualunque (`[create,`) per ogni istante di `altre`, ma SOLO se il filtro la chiede.
    Torna (processo, chiamate a xcrun, secondi dormiti)."""
    if eventi is None:
        eventi = [] if avviso_dopo is None else [avviso_dopo]
    chiamate = tmp_path / "chiamate.txt"
    ora = tmp_path / "ora.txt"
    ora.write_text("1000\n", encoding="utf-8")
    eventi_txt = " ".join(str(1000 + t) for t in eventi)
    altre_txt = " ".join(str(1000 + t) for t in altre)
    righe = [
        f'source "{SCRIPT.as_posix()}"',
        f'ORA="{ora.as_posix()}"; CHIAMATE="{chiamate.as_posix()}"; EVENTI="{eventi_txt}"; ALTRE="{altre_txt}"',
        'date() { cat "$ORA"; }',
        'sleep() { echo "sleep $1" >> "$CHIAMATE"; echo $(( $(cat "$ORA") + $1 )) > "$ORA"; }',
        'xcrun() {',
        '  echo "xcrun $*" >> "$CHIAMATE"',
        '  case "$*" in *"screenshot"*) [ "${FALLISCE_FOTO:-0}" = 1 ] && return 1; return 0 ;; esac',
        '  case "$*" in *"log show"*) ;; *) return 0 ;; esac',
        # le righe di comando delle letture di prima (processo «log»): contano solo se il filtro non chiede il processo
        '  case "$*" in *generativeexperiencesd*) ;; *) n=$(grep -c "log show" "$CHIAMATE"); i=1; '
        f'while [ "$i" -lt "$n" ]; do echo "{RIGA_ECO}"; i=$((i + 1)); done ;; esac',
        '  finestra=$(echo "$*" | sed -n "s/.*--last \\([0-9]*\\)s.*/\\1/p"); ora=$(cat "$ORA")',
        f'  for t in $EVENTI; do [ "$t" -le "$ora" ] && [ "$t" -ge $((ora - finestra)) ] && echo "{RIGA_AVVISO}"; done',
        f'  case "$*" in *"[create,"*) for t in $ALTRE; do [ "$t" -le "$ora" ] && [ "$t" -ge $((ora - finestra)) ] && echo "{RIGA_ALTRA}"; done ;; esac',
        '  return 0',
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
    """Il filtro prende solo l'invito di Apple Intelligence: un'altra notifica di sistema non deve chiudere l'attesa."""
    testo = SCRIPT.read_text(encoding="utf-8")
    filtro = re.search(r"^AVVISI_FILTRO='([^']*)'", testo, re.M)
    assert filtro, "AVVISI_FILTRO non trovato"
    assert filtro.group(1) == 'process == "generativeexperiencesd" AND eventMessage CONTAINS "Posted new Readiness CFU"',         "solo l'invito di Apple Intelligence, scritto dal suo servizio, chiude l'attesa"
    assert "[create," not in filtro.group(1), "una notifica qualunque non è l'avviso"
    assert "log show" in testo and "log stream" not in testo.replace("«log stream»", ""), "il registro in diretta arriva in ritardo"


@serve_bash
def test_se_l_avviso_compare_si_aspetta_che_sparisca_e_poi_si_va(tmp_path):
    # l'avviso compare dopo 170 secondi dall'accensione: ogni giro di attesa dura 5 secondi
    r, chiamate, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; echo "VISTO=$AVVISI_VISTO"', avviso_dopo=170)
    assert r.returncode == 0, r.stderr
    assert "VISTO=si" in r.stdout and "avviso visto" in r.stdout
    assert 170 <= dormiti <= 170 + 5 + 20, f"ha dormito {dormiti} secondi"
    # alla fine ha lasciato passare la pausa dell'avviso (20 secondi), non ha aspettato oltre
    assert dormiti >= 170 + 20 - 5
    assert all("UDID1" in c for c in chiamate if "log show" in c)
    assert any("log show" in c and "Posted new Readiness CFU" in c for c in chiamate)


@serve_bash
def test_se_l_avviso_e_gia_passato_quando_si_comincia_a_aspettare_basta_la_pausa(tmp_path):
    r, _, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; sleep 200; avvisi_attendi UDID1 400', avviso_dopo=100)
    assert r.returncode == 0, r.stderr
    assert dormiti == 200 + 20, "la riga d'avviso c'è già: si aspetta solo che sparisca"


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
    assert dormiti == 20, "avviso già nel registro: basta la pausa"


@serve_bash
def test_un_altra_notifica_non_chiude_l_attesa(tmp_path):
    # una notifica qualunque a 50 secondi, l'invito di Apple a 170: l'attesa deve arrivare fino all'invito
    r, _, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; echo "VISTO=$AVVISI_VISTO"',
                          eventi=[170], altre=[50])
    assert r.returncode == 0, r.stderr
    assert "VISTO=si" in r.stdout
    assert dormiti >= 170, f"l'altra notifica ha chiuso l'attesa dopo {dormiti} secondi"


@serve_bash
def test_prima_di_spegnere_si_controlla_se_l_avviso_e_comparso_dopo_l_attesa(tmp_path):
    # attesa di 30 secondi senza avviso; l'avviso compare a 100 secondi, quando le foto sono già cominciate
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 30; sleep 120; avvisi_ferma; avvisi_riepilogo', avviso_dopo=100)
    assert r.returncode == 0, r.stderr
    assert "comparso DOPO l'attesa" in r.stdout
    assert "comparsi dopo l'attesa: 1" in r.stdout and "controllare le foto" in r.stdout


@serve_bash
def test_il_controllo_finale_c_e_anche_se_l_avviso_e_stato_visto_durante_l_attesa(tmp_path):
    # primo invito a 20 secondi (visto e aspettato), un secondo a 100 quando le foto sono già cominciate: va segnalato
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; sleep 120; avvisi_ferma; avvisi_riepilogo',
                    eventi=[20, 100])
    assert r.returncode == 0, r.stderr
    assert "comparso DOPO l'attesa" in r.stdout
    assert "aspettati prima delle foto: 1; comparsi dopo l'attesa: 1" in r.stdout


@serve_bash
def test_il_controllo_finale_ignora_un_altra_notifica_e_l_invito_gia_aspettato(tmp_path):
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; sleep 120; avvisi_ferma; avvisi_riepilogo',
                    eventi=[20], altre=[100])
    assert r.returncode == 0, r.stderr
    assert "comparso DOPO l'attesa" not in r.stdout
    assert "comparsi dopo l'attesa: 0" in r.stdout


@serve_bash
def test_senza_avvisi_tardivi_il_riepilogo_e_pulito(tmp_path):
    r, _, _ = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 400; avvisi_ferma; avvisi_riepilogo', avviso_dopo=20)
    assert r.returncode == 0, r.stderr
    assert "aspettati prima delle foto: 1; comparsi dopo l'attesa: 0" in r.stdout
    assert "controllare" not in r.stdout


# #601. Su iOS 26.5 l'invito può tornare mentre si fotografa (corsa 43131154860, sopra la foto accesso-account): ogni foto si
# controlla dopo lo scatto e si rifà se l'avviso può esserci sopra. E il filtro deve prendere solo il servizio di Apple: il
# processo «log show» scrive nel registro la propria riga di comando, che contiene lo stesso testo (corsa 44629200541: ogni
# lettura ritrovava quelle di prima, l'attesa iniziale finiva su una riga falsa e ogni foto si rifaceva due volte).

def test_il_filtro_prende_solo_il_servizio_di_apple():
    filtro = re.search(r"^AVVISI_FILTRO='([^']*)'", SCRIPT.read_text(encoding="utf-8"), re.M).group(1)
    assert 'process == "generativeexperiencesd"' in filtro, "la riga di comando di «log show» contiene lo stesso testo"


@serve_bash
def test_le_righe_di_comando_di_log_show_non_chiudono_l_attesa(tmp_path):
    r, _, dormiti = _bash(tmp_path, 'avvisi_avvia UDID1; avvisi_attendi UDID1 60; echo "VISTO=$AVVISI_VISTO"')
    assert r.returncode == 0, r.stderr
    assert "VISTO=no" in r.stdout, "una lettura del registro ha scambiato la riga di comando di quella prima per l'avviso"
    assert dormiti >= 60


@serve_bash
def test_senza_avviso_nessuna_foto_si_rifa_anche_con_tante_letture(tmp_path):
    corpo = ('for n in 1 2 3 4 5 6; do inizio=$(date +%s); sleep 4; avvisi_rifai UDID1 /tmp/f$n.png "$inizio"; done; '
             'avvisi_riepilogo')
    r, chiamate, dormiti = _bash(tmp_path, corpo)
    assert r.returncode == 0, r.stderr
    assert "foto rifatte per l'avviso: 0" in r.stdout
    assert not [c for c in chiamate if "screenshot" in c]
    assert dormiti == 6 * 4


@serve_bash
def test_avviso_durante_la_foto_la_fa_rifare_una_volta(tmp_path):
    # foto cominciata a 100, invito a 103 (stesso secondo del controllo): una sola foto rifatta dopo la pausa, non due
    corpo = 'sleep 100; inizio=$(date +%s); sleep 3; avvisi_rifai UDID1 /tmp/f.png "$inizio"; echo "ESITO=$?"; avvisi_riepilogo'
    r, chiamate, dormiti = _bash(tmp_path, corpo, eventi=[103])
    assert r.returncode == 0, r.stderr
    assert "ESITO=0" in r.stdout
    assert len([c for c in chiamate if "screenshot /tmp/f.png" in c]) == 1
    assert dormiti == 100 + 3 + 20, "prima di rifare la foto si aspetta che il banner sparisca"
    assert "foto rifatte per l'avviso: 1" in r.stdout and "controllare" not in r.stdout


@serve_bash
def test_avviso_poco_prima_della_foto_la_fa_rifare(tmp_path):
    # invito a 90, foto da 100 a 102: SpringBoard mostra il banner circa 9 secondi dopo, quindi può essere sopra
    r, chiamate, _ = _bash(tmp_path, 'sleep 100; inizio=$(date +%s); sleep 2; avvisi_rifai UDID1 /tmp/f.png "$inizio"',
                           eventi=[90])
    assert r.returncode == 0, r.stderr
    assert any("screenshot /tmp/f.png" in c for c in chiamate)


@serve_bash
def test_avviso_vecchio_o_altra_notifica_non_fanno_rifare_la_foto(tmp_path):
    r, chiamate, dormiti = _bash(tmp_path, 'sleep 100; inizio=$(date +%s); sleep 2; avvisi_rifai UDID1 /tmp/f.png "$inizio"',
                                 eventi=[50], altre=[101])
    assert r.returncode == 0, r.stderr
    assert not [c for c in chiamate if "screenshot" in c]
    assert dormiti == 102


@serve_bash
def test_se_l_avviso_resta_dopo_due_rifacimenti_lo_dice_nel_riepilogo(tmp_path):
    eventi = list(range(100, 400, 5))   # un invito ogni 5 secondi: nessuna foto pulita
    corpo = ('sleep 100; inizio=$(date +%s); sleep 2; avvisi_rifai UDID1 /tmp/iphone_formazione.png "$inizio"; '
             'echo "ESITO=$?"; avvisi_riepilogo')
    r, chiamate, _ = _bash(tmp_path, corpo, eventi=eventi)
    assert r.returncode == 0, r.stderr
    assert "ESITO=1" in r.stdout
    assert len([c for c in chiamate if "screenshot" in c]) == 2, "al massimo due rifacimenti"
    assert "foto rifatte per l'avviso: 2" in r.stdout
    assert "controllare le foto" in r.stdout and "iphone_formazione.png" in r.stdout


@serve_bash
def test_se_la_foto_rifatta_non_riesce_lo_dice_nel_riepilogo(tmp_path):
    corpo = ('FALLISCE_FOTO=1; sleep 100; inizio=$(date +%s); sleep 2; avvisi_rifai UDID1 /tmp/f.png "$inizio"; '
             'echo "ESITO=$?"; avvisi_riepilogo')
    r, _, _ = _bash(tmp_path, corpo, eventi=[101])
    assert r.returncode == 0, r.stderr
    assert "ESITO=1" in r.stdout and "non riuscita" in r.stdout
    assert "foto rifatte per l'avviso: 0" in r.stdout and "controllare le foto" in r.stdout


@serve_bash
def test_avvisi_foto_scatta_controlla_e_rifa(tmp_path):
    r, chiamate, _ = _bash(tmp_path, 'sleep 100; avvisi_foto UDID1 /tmp/home.png; echo "ESITO=$?"', eventi=[95])
    assert r.returncode == 0, r.stderr
    assert "ESITO=0" in r.stdout
    assert len([c for c in chiamate if "screenshot /tmp/home.png" in c]) == 2, "foto, avviso visto, foto rifatta"


def test_le_foto_si_controllano_dopo_lo_scatto_e_prima_di_girarle_o_ridimensionarle():
    """scatta() dell'app e dei widget: avvisi_rifai dopo la foto, prima del controllo della foto quasi nera e di «sips»; le
    foto semplici di screenshot.sh (avvio, home, prova-url) passano da avvisi_foto."""
    for script, prima in ((FOTO, "schermo_fermo.py"), (WIDGET, 'simctl io "$udid" screenshot')):
        corpo = re.search(r"^scatta\(\) \{\n.*?^\}\n", script.read_text(encoding="utf-8"), re.S | re.M).group(0)
        assert 'avvisi_rifai "$udid" "$file" "$inizio"' in corpo, script.name
        i = corpo.index("avvisi_rifai")
        assert corpo.index(prima) < i < corpo.index("stat -f%z") < corpo.index("sips"), script.name
    foto = FOTO.read_text(encoding="utf-8")
    assert not re.search(r'simctl io "\$(UDID_IPHONE|UDID_IPAD|udid)" screenshot "\$USCITA/(avvio|home|prova-url)', foto)
    assert foto.count("avvisi_foto ") >= 5
