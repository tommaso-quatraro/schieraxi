"""Immagine da condividere (Formazione > «Condividi come immagine», issue #307): il fantavoto sotto ogni volto ha un decimale
(«5,6»), come in tutta la web. Il server manda `fv_atteso` con due decimali (servono ai calcoli): prima l'immagine li scriveva
tutti («5,62») accanto alla pedina della schermata che diceva «5,6».
La prova disegna davvero con la funzione dell'app, su una tela finta che registra i testi."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _riga(nome: str) -> str:
    m = re.search(rf"^const {nome} = .*$", APP, re.M)
    assert m, nome
    return m.group(0)


def _testi_scritti(lingua: str, titolari: list[dict]) -> list[str]:
    """Esegue `condividiImmagine` con la tela finta e restituisce i testi scritti, nell'ordine."""
    inizio = APP.index("async function condividiImmagine(")
    corpo = APP[inizio:APP.index("// Diario > «Quanto ci abbiamo preso»")]
    schede = {str(i + 1): {**x, "id": i + 1, "ruolo": x.get("ruolo", "C")} for i, x in enumerate(titolari)}
    f = {"squadra": "Squadra Esempio", "giornata": 9, "giornata_lega": 9, "schede": schede}
    m = {"modulo": "4-4-2", "punteggio_atteso": 64.1, "titolari": list(map(int, schede)), "panchina": []}
    codice = f"""
let LINGUA = {json.dumps(lingua)};
{_riga("num")}
{_riga("virgola")}
const t = (k, p) => k + (p ? JSON.stringify(p) : "");
const nomeGiornata = (a, b) => "G" + (a || b);
const cognome = x => x.cognome, svgAvatar = () => "<svg></svg>", caricaSvg = async () => null;
const apriFoglio = () => {{}}, avviso = () => {{}};
const scritti = [];
const tela = new Proxy({{}}, {{
  get: (_, k) => k === "fillText" ? s => scritti.push(String(s))
    : k === "createLinearGradient" ? () => ({{ addColorStop() {{}} }})
    : k === "measureText" ? s => ({{ width: String(s).length * 10 }}) : () => {{}},
  set: () => true }});
const document = {{ createElement: () => ({{ getContext: () => tela, toBlob: fine => fine(null) }}) }};
{corpo}
(async () => {{ await condividiImmagine({json.dumps(f)}, {json.dumps(m)}); console.log(JSON.stringify(scritti)); }})();
"""
    r = subprocess.run([NODE, "-e", codice], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


GIOCATORI = [{"cognome": "Rossi", "fv_atteso": 5.62}, {"cognome": "Bianchi", "fv_atteso": 6.07}, {"cognome": "Verdi", "fv_atteso": 7},
             {"cognome": "Neri", "fv_atteso": 8.49}, {"cognome": "Gialli", "fv_atteso": 6.3}]


@pytest.mark.skipif(NODE is None, reason="node non installato")
@pytest.mark.parametrize("lingua, virgola", [("it", ","), ("en", ".")])
def test_fantavoto_sotto_i_volti_con_un_decimale_come_nel_resto_della_web(lingua, virgola):
    scritti = _testi_scritti(lingua, GIOCATORI)
    attesi = [f"5{virgola}6", f"6{virgola}1", f"7{virgola}0", f"8{virgola}5", f"6{virgola}3"]        # stesso arrotondamento di `num`
    assert [s for s in scritti if re.fullmatch(r"\d+[.,]\d+", s)] == attesi, scritti
    assert not any(re.search(r"\d[.,]\d\d", s) for s in scritti), scritti                                  # mai due decimali


def test_fantavoto_dell_immagine_usa_la_funzione_dei_numeri_della_web():
    """Una sola funzione di formato: `num`, la stessa di pedine, elenchi e schede."""
    corpo = APP[APP.index("async function condividiImmagine("):APP.index("// Diario > «Quanto ci abbiamo preso»")]
    assert "num(x.fv_atteso)" in corpo
    assert "virgola(x.fv_atteso)" not in corpo
