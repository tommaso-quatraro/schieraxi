"""Messaggi di attesa (429): il testo del server, «circa N ore» sopra l'ora, e il contatore degli scambi che non mente."""
import json
import shutil
import subprocess

import pytest

from fanta import limiti
import codice_web

APP = codice_web.app()


def test_la_durata_sopra_l_ora_e_in_ore():
    assert limiti._durata(30) == "1 min" and limiti._durata(25 * 60) == "25 min" and limiti._durata(3600) == "60 min"
    assert limiti._durata(3601) == "circa 1 ora" and limiti._durata(5 * 3600 + 700) == "circa 5 ore"


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node")
def test_attesa_testo():
    testi = codice_web.leggi("testi.js")
    codice = testi + APP[APP.index("const attesaTesto"):APP.index("const errore =")] + """
const e = (riprova, message) => ({ status: 429, riprova, message });
console.log(JSON.stringify([attesaDa(e(2, "Aspetta")), attesaDa(e(300, "Aspetta")), attesaDa(e(5 * 3600, "Aspetta")),
  attesaDa(e(5 * 3600, "Si azzera tra circa 5 ore.")), attesaDa({ status: 500, riprova: 3, message: "x" })]));
"""
    r = subprocess.run(["node", "-"], input=codice, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [" (riprova tra 2 secondi)", " (riprova tra 5 minuti)", " (riprova tra circa 5 ore)", "", ""]


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node")
def test_un_secondo_e_la_frase_senza_l_invito_a_riprovare():
    """Il pulsante dell'accesso conta fino a «1 secondo» (non «1 secondi»); sopra, la frase del server senza l'invito a riprovare,
    che il pulsante già dice (#940, come l'iPhone): mai «Troppi tentativi: riprova più tardi (riprova tra 24 secondi)»."""
    testi = codice_web.leggi("testi.js")
    codice = testi + APP[APP.index("const attesaTesto"):APP.index("const errore =")] + """
console.log(JSON.stringify([attesaTesto(1), attesaTesto(2), senzaInvitoARiprovare("Troppi tentativi: riprova più tardi."),
  senzaInvitoARiprovare("Troppi tentativi sbagliati: aspetta prima di riprovare."),
  senzaInvitoARiprovare("Troppi tentativi in questo momento: riprova tra qualche secondo."),
  senzaInvitoARiprovare("Per oggi le iscrizioni sono chiuse: riprova domani."), senzaInvitoARiprovare("Too many attempts: try again later."),
  senzaInvitoARiprovare("Riprova tra poco."), senzaInvitoARiprovare("Calma"),
  senzaInvitoARiprovare("Troppi tentativi: riprova più tardi")]));
"""
    r = subprocess.run(["node", "-"], input=codice, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["1 secondo", "2 secondi", "Troppi tentativi.", "Troppi tentativi sbagliati.",
                                    "Troppi tentativi in questo momento.", "Per oggi le iscrizioni sono chiuse.", "Too many attempts.",
                                    "", "Calma.", "Troppi tentativi."]          # l'ultimo: un server di prima, senza il punto
