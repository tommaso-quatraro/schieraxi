"""Foto «scuro» e «chiaro» dei widget (`ios/scripts/screenshot_widget.sh`, #890): l'app di anteprima riceve dall'argomento di
lancio l'aspetto del suo giro (`-ASPETTO scuro|chiaro`) e lo usa qualunque cosa dica il simulatore.

Nella corsa 45529400800 `ipad_scuro_verticale_oggi_pieni.png` e `ipad_scuro_verticale_formazione_pieni.png` sono uscite chiare:
erano le prime foto dopo l'accensione dell'iPad e il simulatore non aveva ancora preso il tema chiesto con `simctl ui appearance
dark` (la terza dello stesso giro, `dubbi`, era scura). Lo stesso difetto delle foto dell'app, che ricevono `-DEMO_ASPETTO` (#852).
Qui i comandi del Mac sono finti (xcrun, python3, sleep, sips, stat, open, osascript): nessun simulatore."""
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_foto_avvisi import BASH, serve_bash

RADICE = Path(__file__).resolve().parent.parent
WIDGET = RADICE / "ios" / "scripts" / "screenshot_widget.sh"
ASPETTO_DEL_GIRO = {"dark": "scuro", "light": "chiaro"}


def _foto(tmp_path):
    """Lancia screenshot_widget.sh (iPhone e iPad, tutti i giri) con i comandi del Mac finti. Torna (processo, lanci): per ogni
    `simctl launch` di una foto, il simulatore a cui va, l'aspetto dato al simulatore in quel momento e gli argomenti."""
    registro = tmp_path / "comandi.txt"
    righe = [
        f'REGISTRO="{registro.as_posix()}"; export REGISTRO',
        'xcrun() {',
        '  echo "xcrun $*" >> "$REGISTRO"',
        '  case "$*" in',
        '    *"launchctl list"*) echo "UIKitApplication:it.schieraxi.app.anteprima" ;;',
        # la foto: un file vuoto con il nome chiesto (l'ultimo argomento)
        '    "simctl io "*" screenshot "*) for f; do :; done; : > "$f" ;;',
        '  esac',
        '  return 0',
        '}',
        # python3 -I <script> <iphone|ipad>: la scelta del simulatore
        'python3() { case "$2" in *scegli_simulatore.py) printf "UDID-%s\\tSimulatore finto\\tiOS 26\\n" "$3" ;; esac; return 0; }',
        'sleep() { :; }',
        'sips() { :; }',
        'stat() { echo 999999; }',
        'open() { :; }',
        'osascript() { :; }',
        'export -f xcrun python3 sleep sips stat open osascript',
        f'AVVISI_ATTESA_MAX=0 "$BASH" "{WIDGET.as_posix()}" "{(tmp_path / "AnteprimaWidget.app").as_posix()}" '
        f'"{(tmp_path / "foto").as_posix()}"',
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "BASH": Path(BASH).as_posix(),
                "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=300, env=ambiente,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    comandi = registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []
    lanci, ui = [], None
    for c in comandi:
        m = re.fullmatch(r"xcrun simctl ui \S+ appearance (dark|light)", c)
        if m:
            ui = m.group(1)
        elif c.startswith("xcrun simctl launch ") and " -DATI " in c:
            argomenti = c.split()
            lanci.append((argomenti[3], ui, argomenti))
    return r, lanci


def _valore(argomenti, nome):
    return argomenti[argomenti.index(nome) + 1] if nome in argomenti[:-1] else None


@pytest.fixture(scope="module")
def corsa(tmp_path_factory):
    """Una corsa sola per i test del file."""
    if not BASH:
        pytest.skip("serve bash")
    return _foto(tmp_path_factory.mktemp("foto-widget-aspetto"))


@serve_bash
def test_ogni_widget_riceve_l_aspetto_del_suo_giro(corsa):
    r, lanci = corsa
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert {ui for _, ui, _ in lanci} == {"dark", "light"}, "servono foto con il simulatore scuro e con il simulatore chiaro"
    sbagliate = [f"{_valore(a, '-GALLERIA')} {_valore(a, '-DATI')} ({ui}): -ASPETTO {_valore(a, '-ASPETTO')}"
                 for _, ui, a in lanci if _valore(a, "-ASPETTO") != ASPETTO_DEL_GIRO[ui]]
    assert not sbagliate, (f"l'anteprima deve sapere l'aspetto del giro anche se il simulatore non l'ha ancora preso ({len(sbagliate)} "
                           f"foto su {len(lanci)}): " + "; ".join(sbagliate[:6]))


@serve_bash
def test_le_prime_foto_dopo_l_accensione_sono_scure_anche_sull_ipad(corsa):
    """Il caso della corsa 45529400800: i primi widget fotografati dopo l'accensione di ogni simulatore."""
    r, lanci = corsa
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    for simulatore in ("UDID-iphone", "UDID-ipad"):
        primi = [a for udid, _, a in lanci if udid == simulatore][:3]
        assert len(primi) == 3, f"{simulatore}: mancano le foto"
        assert [_valore(a, "-ASPETTO") for a in primi] == ["scuro"] * 3, f"{simulatore}: " + "; ".join(" ".join(a) for a in primi)
