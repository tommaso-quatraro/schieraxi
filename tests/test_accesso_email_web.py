"""Registrati, email facoltativa (issue #207): etichetta breve sopra il campo e spiegazione sotto, come sull'iPhone
(`ModuloAccesso.etichettaEmail` e `aiutoEmailFacoltativa`). Il modulo si legge da `fanta/web/app.js` e si prova con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")


def _testo(chiave: str, lingua: int) -> str:
    return re.findall(rf'^    "{re.escape(chiave)}": "(.*)",$', TESTI, re.M)[lingua]


def _campi() -> dict:
    """Il campo email di «Registrati» (facoltativo e obbligatorio) come lo costruisce app.js; `t` restituisce la chiave tra graffe."""
    blocco = re.search(r"^const campoAccesso = .*?(?=^function campiAccesso\()", APP, re.S | re.M)
    assert blocco, "campoAccesso non trovato in app.js"
    codice = ('const t = k => "{" + k + "}";\n' + blocco.group(0)
              + '\nconsole.log(JSON.stringify({ facoltativa: CAMPO_EMAIL("ac-email", true), obbligatoria: CAMPO_EMAIL("ac-email", false),'
                ' password: campoAccesso("ac-pw", "Password", "password", "required") }));')
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_i_testi_dell_email_facoltativa_sono_quelli_dell_iphone():
    assert _testo("accesso.email_facoltativa", 0) == "Email (facoltativa)"
    assert _testo("accesso.email_facoltativa_aiuto", 0) == "Serve a recuperare la password."
    assert _testo("accesso.email_facoltativa", 1) == "Email (optional)"
    assert _testo("accesso.email_facoltativa_aiuto", 1) == "Used to recover your password."


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_l_etichetta_e_breve_e_la_spiegazione_sta_sotto_il_campo():
    html = _campi()["facoltativa"]
    m = re.fullmatch(r"<label([^>]*)>(.*?)</label>\s*(<[^>]*>.*)", html, re.S)
    assert m, html
    etichetta, aiuto = m.group(2), m.group(3)
    assert "{accesso.email_facoltativa}" in etichetta
    # la spiegazione sta fuori dall'etichetta: altrimenti entrerebbe nel nome del campo letto dai lettori di schermo
    assert "email_facoltativa_aiuto" not in etichetta
    assert re.match(r'<div class="debole piccolo accesso-aiuto" id="ac-email-aiuto">\{accesso\.email_facoltativa_aiuto\}</div>$', aiuto), aiuto
    # ... ma legata al campo
    assert 'aria-describedby="ac-email-aiuto"' in etichetta and 'id="ac-email"' in etichetta


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_senza_spiegazione_il_campo_resta_come_prima():
    for nome in ("obbligatoria", "password"):
        html = _campi()[nome]
        assert "aria-describedby" not in html and "aiuto" not in html, nome
        assert html.startswith("<label") and html.endswith("</label>"), nome
    assert "{accesso.email}" in _campi()["obbligatoria"] and "required" in _campi()["obbligatoria"]


def test_la_spiegazione_ha_il_suo_stile():
    css = (server.WEB / "stile.css").read_text(encoding="utf-8")
    assert re.search(r"\.accesso-aiuto \{[^}]*margin: 4px 0 0;", css)
