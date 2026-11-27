"""Un numero con i decimali si scrive uguale dappertutto: frasi del server, differenze del diario, perché della scelta, web (`num` e
`segno` di app.js, provati con node) e iPhone (`Formato.decimali`, provato con gli stessi casi in
ios/Tests/SchieraxiTests/ArrotondaComeIlServerTests.swift).

La regola è quella di `frasi.arrotonda`: il valore vero del numero in memoria, con il mezzo lontano dallo zero, come `toFixed` della
web. 6,35 in memoria è 6,3499…: «6,3» (l'iPhone scriveva «6,4»). 6,25 è proprio 6,25: «6,3» (le frasi del server scrivevano «6,2»,
come `round` di Python, e la tabella accanto «6,3»). Mai «−0,0»."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web
from fanta import diario, frasi, perche_scelta

# (numero, come si scrive con una cifra): gli stessi casi del test dell'iPhone
CASI = [(6.35, "6,3"), (5.55, "5,5"), (7.05, "7,0"), (8.45, "8,4"), (6.05, "6,0"), (0.15, "0,1"), (9.95, "9,9"),
        (6.25, "6,3"), (6.75, "6,8"), (1.05, "1,1"),
        (-0.25, "-0,3"), (-0.35, "-0,3"), (-6.35, "-6,3"), (-0.05, "-0,1"),
        (-0.04, "0,0"), (-0.0, "0,0"), (0.04, "0,0")]
# tutti i numeri con due decimali fra −20 e 20: il fantavoto atteso arriva dal server così
TUTTI = [k / 100 for k in range(-2000, 2001)]
NODE = shutil.which("node")


def _meno(testo: str) -> str:
    """Il server scrive il meno tipografico «−»; `num` della web il trattino di `toFixed`."""
    return testo.replace("-", "−")


# ---------------------------------------------------------------- il server
@pytest.mark.parametrize("x, scritto", CASI)
def test_le_frasi_del_server_scrivono_il_numero_con_la_regola(x, scritto):
    assert frasi._it(x) == _meno(scritto)
    assert frasi._it(x, "en") == _meno(scritto).replace(",", ".")
    assert frasi.arrotonda(x) == float(scritto.replace(",", "."))


def test_la_regola_con_piu_cifre_e_i_numeri_strani():
    assert [frasi.arrotonda(x, 2) for x in (2.675, 1.005, 0.125, -0.125)] == [2.67, 1.0, 0.13, -0.13]
    assert [frasi.arrotonda(x, 0) for x in (0.5, 2.5, -2.5)] == [1.0, 3.0, -3.0]
    assert frasi.arrotonda(1e300) == 1e300 and frasi.arrotonda(7) == 7.0          # numeri enormi e interi: niente errori
    assert frasi._it(float("nan")) == "nan" and frasi._it(float("inf")) == "inf"   # come prima: non si arrotondano


def test_la_differenza_della_frase_e_quella_dei_numeri_scritti():
    """«72,3 invece di 72,1 (+0,2)»: 72,25 si scrive 72,3 anche nella differenza (con `round` di Python era 72,2 e «+0,1»)."""
    assert frasi._it(72.25) == "72,3" and frasi._it(frasi.differenza(72.25, 72.1)) == "+0,2"
    assert frasi._it(frasi.differenza(6.35, 7.5)) == "−1,2"          # 6,3 − 7,5


def test_il_punteggio_della_formazione_e_scritto_come_la_frase_accanto():
    """`punteggio_atteso` di ogni modulo (testata della Formazione) con la regola delle frasi che nominano lo stesso numero
    («varrebbe 72,1 invece di 72,3», `differenza`): con `round` di Python 72,25 era «72,2» in testata e «72,3» nella frase."""
    from types import SimpleNamespace

    from fanta import consigli
    modulo = SimpleNamespace(modulo="3-4-3", atteso=72.25, dev=5.0, titolari=[], panchina=[])
    assert consigli._moduli([modulo], None)[0]["punteggio_atteso"] == 72.3
    assert frasi._it(72.25) == "72,3"


def test_diario_e_perche_della_scelta_contano_sui_numeri_scritti():
    """Le differenze del diario (`_letto`) e i confronti del perché della scelta (`_uno`: mai «72,1 invece di 72,1», #659) partono
    dai numeri come li scrive la frase."""
    for x in TUTTI:
        scritto = frasi._it(x)
        assert frasi._it(diario._letto(x)) == scritto, x
        assert frasi._it(perche_scelta._uno(x)) == scritto, x


# ---------------------------------------------------------------- la web (node)
def _web(chiamata: str, lingua: str = "it"):
    app = codice_web.app()
    righe = [re.search(rf"^const {nome} = .*$", app, re.M).group(0) for nome in ("num", "segno")]
    codice = "\n".join([codice_web.leggi("testi.js"), f"LINGUA = {json.dumps(lingua)};", *righe,
                        f"console.log(JSON.stringify({chiamata}));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="serve node")
def test_la_web_scrive_i_casi_come_il_server_e_l_iphone():
    numeri = json.dumps([x for x, _ in CASI])
    assert _web(f"{numeri}.map(x => num(x))") == [s for _, s in CASI]
    assert _web(f"{numeri}.map(x => num(x))", lingua="en") == [s.replace(",", ".") for _, s in CASI]
    assert _web("[num(-0.004, 2), num(-0.4, 0), num(null)]") == ["0,00", "0", "–"]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_la_web_scrive_come_le_frasi_del_server_tutti_i_numeri_con_due_decimali():
    """`num` e `segno` della web contro le frasi del server, su ogni numero con due decimali fra −20 e 20."""
    web = _web(f"{json.dumps(TUTTI)}.map(x => [num(x), segno(x)])")
    diversi = [(x, n, s) for x, (n, s) in zip(TUTTI, web)
               if _meno(n) != frasi._it(x) or s != frasi._it(frasi.ConSegno(x))]
    assert not diversi, diversi[:10]
