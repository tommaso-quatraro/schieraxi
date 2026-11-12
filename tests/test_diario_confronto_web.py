"""Giro di collaudo 6 (2/11/2026): Diario, Confronto e «Quanto ci abbiamo preso» sulla web.
- Confronto: il titolo «Chi schierare? Giornata N» usava il numero di Serie A (10) invece di quello della lega (7).
- «Quanto ci abbiamo preso»: «chi davamo al 83%» (italiano sbagliato); l'iPhone scrive già «all'83%» (Precisione.alPercento).
- Diario: i punti senza decimale quando sono tondi («48 attesi 61,2», «tra 54,9 e 76»): sempre una cifra decimale."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _funzione(nome):
    riga = re.search(rf"^const {nome} = .*$", APP, re.M)
    assert riga, nome
    return riga.group(0)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_al_percento_con_l_apostrofo_come_sull_iphone():
    codice = (_funzione("alPercento")
              + "console.log(JSON.stringify([83, 98, 8, 11, 1, 18, 80, 100, 0, 40].map(alPercento)))")
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["all'83%", "al 98%", "all'8%", "all'11%", "all'1%", "al 18%", "all'80%", "al 100%", "al 0%", "al 40%"]


def test_frase_gioca_ricostruita_usa_al_percento():
    it = re.search(r'"diario.qp_gioca_ric": "([^"]+)"', TESTI).group(1)
    assert "chi davamo {al} ha giocato" in it and "al {p}%" not in it
    assert "alPercento(" in APP


def test_quanto_ci_abbiamo_preso_senza_carte_dentro_la_carta():
    """docs/STILE-SENZA-AI.md, pavimento 7: dentro una carta righe e spazio, mai un'altra carta. I quattro numeri di «Quanto ci
    abbiamo preso» erano riquadri con fondo, bordo e angoli tondi dentro la carta."""
    css = (WEB / "stile.css").read_text(encoding="utf-8")
    regola = re.search(r"^\.qp-voce \{([^}]*)\}", css, re.M).group(1)
    assert "background" not in regola and "border-radius" not in regola and "border:" not in regola
    assert "border-top" in regola
