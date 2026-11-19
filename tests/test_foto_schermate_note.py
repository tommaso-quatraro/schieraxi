"""Foto a mano (`SCHERMATE` di `ios/scripts/screenshot.sh`, input `schermate` di screenshot.yml): un nome che non è nell'elenco
delle schermate ferma lo script subito, con un errore che lo nomina, prima di accendere il simulatore.

Prima passava all'app così com'era e la demo, che non lo conosce, si apriva sulla Formazione: nella #710 la scena
«impostazioni-avanzate» (rinominata «impostazioni-gestione», ma ancora nel foto.json di main) ha dato tre foto della Formazione
senza che niente lo dicesse. Qui i comandi del Mac sono finti (xcrun, python3, sleep): nessun simulatore."""
import os
import subprocess
from pathlib import Path

from test_foto_avvisi import BASH, serve_bash

RADICE = Path(__file__).resolve().parent.parent
FOTO = RADICE / "ios" / "scripts" / "screenshot.sh"


def _foto(tmp_path, schermate):
    """Lancia screenshot.sh con `SCHERMATE` e i comandi del Mac finti; torna (processo, comandi del Mac chiamati). Il primo
    comando dopo la scelta delle schermate (python3, che sceglie il simulatore) annota e ferma lo script: basta sapere se ci arriva."""
    registro = tmp_path / "comandi.txt"
    righe = [
        f'REGISTRO="{registro.as_posix()}"; export REGISTRO',
        'xcrun() { echo "xcrun $*" >> "$REGISTRO"; return 1; }',
        'python3() { echo "python3 $*" >> "$REGISTRO"; kill -TERM $$; }',
        'sleep() { :; }',
        'export -f xcrun python3 sleep',
        f'SCHERMATE="{schermate}" DISPOSITIVI=iphone "$BASH" "{FOTO.as_posix()}" "{(tmp_path / "Schieraxi.app").as_posix()}" '
        f'"{(tmp_path / "foto").as_posix()}"',
    ]
    prova = tmp_path / "prova.sh"
    prova.write_text("\n".join(righe) + "\n", encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "BASH": Path(BASH).as_posix(),
                "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", "")}
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=120, env=ambiente,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r, registro.read_text(encoding="utf-8").splitlines() if registro.exists() else []


@serve_bash
def test_una_schermata_che_non_esiste_ferma_le_foto_prima_del_simulatore(tmp_path):
    r, comandi = _foto(tmp_path, "impostazioni impostazioni-avanzate")
    assert r.returncode == 2, r.stdout + r.stderr
    riga = next((riga for riga in r.stdout.splitlines() if "Schermate sconosciute:" in riga), "")
    assert riga.split("Schermate sconosciute:")[-1].split(".")[0].split() == ["impostazioni-avanzate"], r.stdout
    assert comandi == [], "nessun simulatore acceso per foto che sarebbero sbagliate"


@serve_bash
def test_le_schermate_dell_elenco_passano(tmp_path):
    r, comandi = _foto(tmp_path, "impostazioni-gestione")
    assert "Schermate sconosciute" not in r.stdout
    assert any(c.startswith(("xcrun", "python3")) for c in comandi), "con un nome giusto si va avanti verso il simulatore"
