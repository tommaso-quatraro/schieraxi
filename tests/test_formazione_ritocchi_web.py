"""Formazione e «Da fare» (collaudo del 2/11/2026): «Modifica a mano» lasciata senza cambi, ★ non sul numero più alto,
etichette a capo a 768 px, «Controlla» dei dati vecchi che apre Stato dei dati."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
DAFARE = (WEB / "dafare.js").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def test_modifica_a_mano_senza_cambi_non_resta_la_tua_scelta():
    assert "if (sc.manuale && !sc.manuale.salvata && sc.manuale.uguale) sc.manuale = null;" in APP
    assert "uguale: stessiIds(ids, moduloAuto().titolari)" in APP
    assert "salvata: salva || silenzioso" in APP                        # la scelta salvata resta anche se uguale


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_stella_spiegata_solo_se_un_altro_modulo_ha_di_piu_con_stile_prudente():
    funz = APP[APP.index("function stellaNonMassimo(l)"):APP.index("const stessiIds")]
    codice = ("const esc=x=>String(x); const nomeStile=l=>l.nome; const t=(k,v)=>k+':'+JSON.stringify(v);" + funz
              + "const m=(a,b)=>[{modulo:'3-4-3',punteggio_atteso:a},{modulo:'3-5-2',punteggio_atteso:b}];"
              + "console.log(JSON.stringify([stellaNonMassimo({rischio:0,modulo:'3-4-3',nome:'Equilibrata',moduli:m(72.3,72.4)}),"
              + "stellaNonMassimo({rischio:0,modulo:'3-4-3',nome:'Equilibrata',moduli:m(72.4,72.38)}),"
              + "stellaNonMassimo({rischio:1,modulo:'3-4-3',nome:'Rischiosa',moduli:m(72.3,72.4)})]))")
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    spiegata, pari, rischiosa = json.loads(r.stdout)
    assert "formazione.stella_non_massimo" in spiegata and '"modulo":"3-5-2"' in spiegata and '"consigliato":"3-4-3"' in spiegata
    assert pari == "" and rischiosa == ""                                 # a schermo uguali, o stile rischioso: niente frase
    assert TESTI.count('"formazione.stella_non_massimo"') == 2


def test_etichette_su_una_riga_e_colonne_pari_su_ipad_verticale():
    regola = re.search(r"^\.etichetta \{([^}]*)\}", CSS, re.M).group(1)
    assert "white-space: nowrap" in regola and "text-overflow: ellipsis" in regola and "max-width: 100%" in regola
    assert "@media (max-width: 1023px) { .colonne-campo { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }" in CSS


def test_controlla_dei_dati_vecchi_apre_stato_dei_dati():
    assert 'if (v.id === "dati-vecchi" && typeof apriStatoDati === "function") { vai("impostazioni", "avanzate"); apriStatoDati(); return; }' in DAFARE
