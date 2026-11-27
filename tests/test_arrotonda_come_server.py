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
from dataclasses import replace

import pandas as pd
import pytest

import codice_web
from fanta import consigli, diario, frasi, lega, perche_scelta
from fanta import formazione as fz
from fanta.regole import Regole

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


# ---------------------------------------------------------------- i punteggi della Formazione (consigli.py)
# Una rosa inventata (4-3-3 o 4-4-2) e un calcolo che dà ESATTAMENTE 72,25 punti attesi: con `round` di Python la testata
# scriveva «72,2», la frase accanto («varrebbe 72,1 invece di 72,3») e la differenza 72,3.
REGOLE_433 = Regole(moduli=["4-3-3", "4-4-2"], rosa={"P": 2, "D": 6, "C": 5, "A": 5})
A_META = 72.25


def _prev_433() -> pd.DataFrame:
    righe = ([("P1", "P", 0.95, 6.0), ("P2", "P", 0.9, 5.5)] + [(f"D{i}", "D", 0.9, 6.0 + i / 10) for i in range(6)]
             + [(f"C{i}", "C", 0.9, 6.0 + i / 10) for i in range(5)] + [(f"A{i}", "A", 0.9, 6.5 + i / 5) for i in range(5)])
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": p, "mu": mu, "mu_voto": mu - 0.2, "stato": "titolare",
                          "quota_titolare": 0.9} for n, r, p, mu in righe])
    prev.index = range(1, len(righe) + 1)
    return prev


def _squadra(prev: pd.DataFrame) -> lega.Squadra:
    return lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])


@pytest.fixture
def a_meta(monkeypatch):
    """Ogni formazione vale esattamente 72,25 punti attesi; le schede con i soli campi che servono qui."""
    vera = fz.migliore

    def migliore(*a, **k):
        f = vera(*a, **k)
        return replace(f, atteso=A_META, tutte=[replace(x, atteso=A_META) for x in f.tutte])
    monkeypatch.setattr(consigli.fz, "migliore", migliore)
    monkeypatch.setattr(consigli.fz.Valutatore, "statistiche", lambda self, tit, pan: (A_META, 5.0, 64.0, 80.0))
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "p_voto": float(x["p_voto"]), "fv_atteso": float(x["mu"]),
        "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2), "titolarita": consigli.titolarita(x), "perche_numero": []})


def test_i_punteggi_della_formazione_sono_scritti_come_la_frase_accanto(a_meta):
    """In cima, in ogni stile e in ogni modulo; poi con la consigliata tenuta al suo posto (`_con_consigliata`)."""
    prev = _prev_433()
    f = consigli._calcola_formazione(_squadra(prev), prev, 9, True, REGOLE_433, 200)
    assert f["punteggio_atteso"] == 72.3 and frasi._it(A_META) == "72,3"
    assert {x["punteggio_atteso"] for x in f["livelli"]} == {72.3}
    assert {m["punteggio_atteso"] for x in f["livelli"] for m in x["moduli"]} == {72.3}
    rosa = {g.id: g for g in consigli._rosa(_squadra(prev), prev)}
    tit = [rosa[int(g["id"])] for g in f["titolari"]]
    pan = [rosa[int(g["id"])] for g in f["panchina"]]
    tenuta = consigli._con_consigliata(f | {"punteggio_atteso": 0.0, "livelli": []}, tit, pan, A_META, 5.0, A_META,
                                       list(rosa.values()), REGOLE_433)
    assert tenuta["punteggio_atteso"] == 72.3


def test_la_formazione_scelta_a_mano_e_scritta_come_la_sua_differenza(a_meta, monkeypatch):
    """POST /api/formazione/valuta: «72,3 … +0,2 (72,1)», mai «72,2 … +0,2»."""
    prev = _prev_433()
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "punteggio_atteso": 72.1, "moduli": [{"modulo": "4-3-3", "punteggio_atteso": 72.1}]})
    rose = lega.Rose([_squadra(prev)], "Mia")
    v = consigli.valuta(None, REGOLE_433, rose, [1, 5, 6, 7, 8, 11, 12, 13, 16, 17, 18])
    assert (v["modulo"], v["punteggio_atteso"], v["differenza"]) == ("4-3-3", 72.3, 0.2)


def test_il_fantavoto_della_frase_e_quello_della_tabella():
    """«Ha il fantavoto atteso più alto di X (6,3 contro 6,1)» confronta e scrive il fantavoto come la tabella: la scheda manda
    `fv_atteso` = round(mu, 2) (`consigli.scheda_previsione`) e i client lo arrotondano a una cifra. Con mu 6,2504 e 6,2496 la
    tabella scrive 6,3 e 6,3: niente «più alto». E 6,2496 contro 6,14 è «6,3 contro 6,1», non «6,2 contro 6,1»."""
    def g(i, p, mu):
        return fz.Giocatore(i, f"Giocatore {i}", "D", p, mu, 6.0)
    pari = perche_scelta.motivo(g(1, 0.55, 6.2504), g(2, 0.79, 6.2496), 60.0, 60.02)
    assert pari is not None and pari.chiave == "scelta.pari", pari
    piu_alto = perche_scelta.motivo(g(1, 0.55, 6.2496), g(2, 0.79, 6.14), 60.0, 60.02)
    assert piu_alto.chiave == "scelta.fantavoto_piu_alto" and "(6,3 contro 6,1)" in piu_alto, piu_alto


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
