"""Numeri con il segno nel web (collaudo del 1/11/2026): stesso formato ovunque.
Prima negli scambi c'erano due decimali e il trattino («Tu +23,00 · loro -26,27») accanto a «−26,3» nella spiegazione;
in Stato dei dati i pulsanti delle fonti erano pulsanti di sistema alti 22 px; nella scheda giocatore le sigle xG e xA."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _funzione(nome):
    riga = re.search(rf"^const {nome} = .*$", APP, re.M)
    assert riga, nome
    return riga.group(0)


@pytest.mark.skipif(NODE is None, reason="node non installato")
@pytest.mark.parametrize("lingua", ["it", "en"])
def test_segno_meno_tipografico_e_niente_segno_sullo_zero(lingua):
    codice = (f'let LINGUA="{lingua}";' + _funzione("num") + _funzione("segno")
              + "console.log(JSON.stringify([segno(1.234), segno(-0.44), segno(0), segno(0.04), segno(-0.04), segno(-26.27, 1),"
              + " segno(2.345, 2), segno(null), segno(NaN)]))")
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    dec = "," if lingua == "it" else "."
    attesi = ["+1,2", "−0,4", "0,0", "0,0", "0,0", "−26,3", "+2,35", "–", "–"]
    assert json.loads(r.stdout) == [x.replace(",", dec) for x in attesi]


def test_scambi_un_decimale_come_nella_spiegazione():
    assert "${segno(x, 1)}</span>`;" in _funzione("segnoSc")


def test_pulsanti_delle_fonti_sono_bottoni_dell_app():
    assert '<button class="bottone secondario piccolo" data-fonte=' in APP
    assert '<button class="secondario' not in APP


def test_scheda_giocatore_senza_sigle_xg_xa_nella_riga_del_rendimento():
    riga = re.search(r'"mercato.rendimento_riga": "([^"]+)"', TESTI).group(1)
    assert "xG" not in riga and "xA" not in riga and "gol attesi" in riga


# ---------------------------------------------------------------- collaudo di regressione del 2/11/2026
def test_diario_scarto_dalla_fascia_arrotondato():
    """Prima: «Previsti tra 67,5 e 83,2: più del previsto (+1,7999999999999972)» (sottrazione nel client senza arrotondare)."""
    assert "const meno = x => segno(x, 1);" in APP


def test_rosa_data_dell_aggiornamento_in_italiano():
    """Prima: «Rose aggiornate il 2026-11-02»."""
    assert '(r.aggiornato || "").slice(0, 10)' not in APP
    assert 'fData(parseData(r.aggiornato), { day: "numeric", month: "long", year: "numeric" })' in APP


def test_selettore_degli_scambi_nascosto_resta_nascosto():
    """`.segmenti { display: flex }` vinceva su [hidden]: con una sola funzione compariva un selettore con un solo pulsante."""
    css = (WEB / "stile.css").read_text(encoding="utf-8")
    assert ".segmenti[hidden]" in css


def test_notifiche_senza_service_worker_non_restano_vuote():
    """Se il service worker non arriva mai, il blocco delle notifiche non resta vuoto ad aspettare."""
    corpo = APP[APP.index("async function notificheWeb("):APP.index("const ORE_24")]
    assert "Promise.race([navigator.serviceWorker.ready" in corpo and 't("avv.notifiche_dell_app")' in corpo
