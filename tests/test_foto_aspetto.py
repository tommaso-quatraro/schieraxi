"""Foto «scuro» e «chiaro» dell'app iOS (`ios/scripts/screenshot.sh`, #845): ogni schermata riceve dall'argomento di lancio
l'aspetto del suo giro (`-DEMO_ASPETTO scuro|chiaro`), anche dove il tema dell'app resta «Automatico» (`impostazioni-aspetto`)
e fuori dalle schede (l'accesso).

Nella corsa 44739068749 `iphone_scuro_accesso-rete.png` e `iphone_scuro_impostazioni-aspetto.png` sono uscite chiare. Erano le
prime foto dopo l'accensione: il simulatore era ancora chiaro anche se `simctl ui appearance` rileggeva «dark», e a quelle due
schermate non arrivava `-tema scuro` (l'accesso perché il tema dell'app valeva solo dentro le schede, Aspetto apposta). Le stesse
schermate, scattate più tardi nella stessa corsa, erano scure. Il ripiego `-AppleInterfaceStyle Dark` era passato anche a loro e non è servito.
Qui i comandi del Mac sono finti (xcrun, python3, sleep, sips, stat): nessun simulatore."""
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_foto_avvisi import BASH, serve_bash

RADICE = Path(__file__).resolve().parent.parent
FOTO = RADICE / "ios" / "scripts" / "screenshot.sh"
ASPETTO_DEL_GIRO = {"dark": "scuro", "light": "chiaro"}


def _foto(tmp_path, schermate):
    """Lancia screenshot.sh con `SCHERMATE` sull'iPhone (tutti i giri) e i comandi del Mac finti. Torna (processo, foto chieste
    all'app): per ogni `simctl launch` di una schermata, l'aspetto dato al simulatore in quel momento e gli argomenti."""
    registro = tmp_path / "comandi.txt"
    aspetto = tmp_path / "aspetto.txt"
    righe = [
        f'REGISTRO="{registro.as_posix()}"; ASPETTO="{aspetto.as_posix()}"; export REGISTRO ASPETTO',
        'xcrun() {',
        '  echo "xcrun $*" >> "$REGISTRO"',
        '  case "$*" in',
        '    "simctl ui "*" appearance") cat "$ASPETTO" 2>/dev/null ;;',
        '    "simctl ui "*" appearance "*) echo "${*##* }" > "$ASPETTO" ;;',
        '    *"launchctl list"*) echo "UIKitApplication:it.schieraxi.app" ;;',
        '  esac',
        '  return 0',
        '}',
        # python3 -I <script> <udid> <file> <attesa>: la scelta del simulatore e la foto a schermo fermo
        'python3() {',
        '  case "$2" in',
        '    *scegli_simulatore.py) printf "UDID-FINTO\\tiPhone finto\\tiOS 26\\n" ;;',
        '    *schermo_fermo.py) : > "$4" ;;',
        '  esac',
        '  return 0',
        '}',
        'sleep() { :; }',
        'sips() { :; }',
        'stat() { echo 999999; }',
        'export -f xcrun python3 sleep sips stat',
        f'SCHERMATE="{schermate}" DISPOSITIVI=iphone AVVISI_ATTESA_MAX=0 "$BASH" "{FOTO.as_posix()}" '
        f'"{(tmp_path / "Schieraxi.app").as_posix()}" "{(tmp_path / "foto").as_posix()}"',
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "BASH": Path(BASH).as_posix(),
                "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=120, env=ambiente,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    comandi = registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []
    lanci, ui = [], None
    for c in comandi:
        m = re.fullmatch(r"xcrun simctl ui \S+ appearance (dark|light)", c)
        if m:
            ui = m.group(1)
        elif c.startswith("xcrun simctl launch ") and ("-DEMO_SCHERMATA" in c or "-DEMO_ACCESSO" in c):
            lanci.append((ui, c.split()))
    return r, lanci


def _valore(argomenti, nome):
    return argomenti[argomenti.index(nome) + 1] if nome in argomenti[:-1] else None


def _schermata(argomenti):
    accesso = _valore(argomenti, "-DEMO_ACCESSO")
    return f"accesso-{accesso}" if accesso else _valore(argomenti, "-DEMO_SCHERMATA")


@pytest.fixture(scope="module")
def corsa(tmp_path_factory):
    """Una corsa sola per i test del file, con le schermate e l'ordine della corsa 44739068749 (le due che uscivano chiare in
    testa al primo giro)."""
    if not BASH:
        pytest.skip("serve bash")
    return _foto(tmp_path_factory.mktemp("foto-aspetto"), "accesso-rete impostazioni-aspetto formazione")


@serve_bash
def test_ogni_foto_riceve_l_aspetto_del_suo_giro_anche_accesso_e_aspetto(corsa):
    r, lanci = corsa
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    viste = {(ui, _schermata(a)) for ui, a in lanci}
    for ui in ("dark", "light"):
        for s in ("accesso-rete", "impostazioni-aspetto"):
            assert (ui, s) in viste, f"manca la foto {s} con il simulatore {ui}"
    sbagliate = [f"{_schermata(a)} ({ui}): -DEMO_ASPETTO {_valore(a, '-DEMO_ASPETTO')}"
                 for ui, a in lanci if _valore(a, "-DEMO_ASPETTO") != ASPETTO_DEL_GIRO[ui]]
    assert not sbagliate, "l'app deve sapere l'aspetto del giro anche se il simulatore non l'ha ancora preso: " + "; ".join(sbagliate)


@serve_bash
def test_la_foto_di_aspetto_lascia_il_tema_su_automatico(corsa):
    r, lanci = corsa
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    aspetto = [a for _, a in lanci if _schermata(a) == "impostazioni-aspetto"]
    assert aspetto, "nessuna foto di impostazioni-aspetto"
    assert all("-tema" not in a for a in aspetto), "il selettore del tema deve restare su «Automatico»"
    assert all(_valore(a, "-tema") in ("scuro", "chiaro") for _, a in lanci if _schermata(a) == "formazione")
