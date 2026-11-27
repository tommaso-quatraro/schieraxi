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
    assert json.loads(r.stdout) == [" Riprova tra 2 secondi.", " Riprova tra 5 minuti.", " Riprova tra circa 5 ore.", "", ""]


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node")
def test_l_errore_con_l_attesa_sono_due_frasi_come_sull_iphone():
    """Revisione della #968: con il punto in fondo ai messaggi del server l'attesa diventava «Il server è molto occupato: riprova
    fra qualche secondo. (riprova tra 10 secondi)». Ora come l'iPhone (`ErroreApi.errorDescription`): la frase del server senza
    l'invito a riprovare, poi una frase a sé «Riprova tra 10 secondi.». Senza attesa il messaggio resta intero."""
    testi = codice_web.leggi("testi.js")
    inizio = APP.index("function esc(")
    codice = testi + APP[inizio:APP.index("\n}", inizio) + 2] + "\n" \
        + APP[APP.index("const attesaTesto"):APP.index("// Errore a tutta pagina")] + """
const e = (stato, riprova, message) => ({ status: stato, riprova, message });
console.log(JSON.stringify([errore(e(429, 10, "Il server è molto occupato: riprova fra qualche secondo.")),
  errore(e(429, 10, "Hai fatto troppe richieste in quest'ora. Riprova tra 20 minuti.")), errore(e(500, 0, "Guasto: riprova."))]));
"""
    r = subprocess.run(["node", "-"], input=codice, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [
        '<div class="errore" role="alert">Il server è molto occupato. Riprova tra 10 secondi.</div>',
        '<div class="errore" role="alert">Hai fatto troppe richieste in quest&#39;ora. Riprova tra 20 minuti.</div>',
        '<div class="errore" role="alert">Guasto: riprova.</div>']


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
