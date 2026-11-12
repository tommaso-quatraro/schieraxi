"""Collaudo del 2/11/2026 (giro 5) su Notifiche, Account, Informazioni e primo avvio del web:
- «Dalle/Alle» delle ore tranquille restava visibile con l'interruttore spento (`.riga { display: flex }` batteva `hidden`);
- dopo un rifiuto (stessa ora di inizio e fine) le tendine mostravano la fascia rifiutata, non quella salvata;
- «Genera un nuovo codice» con il campo della password vuoto rispondeva «La password attuale non è giusta»;
- dopo i tempi della lega nel primo avvio la testata restava su «Giornata 10» (Serie A) fino a ricaricare la pagina;
- Informazioni non aveva il codice sorgente (AGPL), che l'iPhone mostra."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

WEB = server.WEB
APP = codice_web.app()
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
IMP = codice_web.leggi("impostazioni.js")
PRIMO = codice_web.leggi("primoavvio.js")
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def test_hidden_vince_sulle_classi_con_display():
    assert re.search(r"^\[hidden\] \{ display: none !important; \}$", CSS, re.M)


# Dal 12/11/2026 (#618) le ore tranquille sono un interruttore con la fascia già scelta (niente «Dalle/Alle» sulla web): che un
# rifiuto del server lasci l'interruttore com'era lo prova tests/browser/test_impostazioni.py.


def test_nuovo_codice_di_recupero_chiede_la_password_prima():
    corpo = APP[APP.index('if ($("#acc-nuovo-codice"))'):APP.index('$("#acc-elimina")')]
    assert corpo.index('if (!valore("#acc-pw-codice")) { avviso(t("account.email_serve_password")); return; }') < corpo.index('api("/api/account/codice-recupero"')


def test_testata_dopo_i_tempi_della_lega():
    corpo = PRIMO[PRIMO.index("async function paTempiSalva"):PRIMO.index("const PA_SCHERMATE")]
    assert corpo.index("caricaInfo();") > corpo.index('api("/api/regole", { method: "PUT"')


def test_codice_sorgente_nelle_informazioni_nelle_due_lingue():
    assert '"info.sorgente": "Codice sorgente"' in TESTI and '"info.sorgente": "Source code"' in TESTI
    assert "${voceSorgente()}</ul>" in IMP


@pytest.mark.skipif(not NODE, reason="serve node")
def test_voce_del_codice_sorgente_solo_con_un_indirizzo_https():
    pezzo = IMP[IMP.index("const voceSorgente"):IMP.index("function paginaInformazioni")]
    codice = "\n".join([
        "const t = k => k; const esc = s => String(s).replace(/[&<>\"']/g, c => '&#' + c.charCodeAt(0) + ';'); const stato = {};",
        pezzo,
        "const casi = ['https://github.com/esempio/app', 'http://chiaro.example', 'javascript:alert(1)', 'https://x.example/\"><b>', null, 42];",
        "console.log(JSON.stringify(casi.map(s => { stato.info = { sorgente: s }; return voceSorgente(); })));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr

    buono, *altri = json.loads(r.stdout)
    assert 'href="https://github.com/esempio/app"' in buono and 'rel="noopener"' in buono and "info.sorgente" in buono
    assert altri == ["", "", "", "", ""]
