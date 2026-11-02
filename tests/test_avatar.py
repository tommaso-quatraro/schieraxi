"""Avatar illustrati: l'estrazione degli indici è deterministica e uguale tra specifica (docs/AVATAR.md), riferimento Python e generatore web (node).
Il riferimento Python qui sotto è scritto dalla specifica, NON dal codice JavaScript: se i due divergono, uno dei due è sbagliato (e iOS/Android seguono la specifica)."""
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SPEC = (RADICE / "docs" / "AVATAR.md").read_text(encoding="utf-8")
AVATAR_JS = RADICE / "fanta" / "web" / "avatar.js"
NODE = shutil.which("node")

M = 0xFFFFFFFF
ORDINE = ["pelle", "forma", "acconciatura", "colore", "barba", "sopracciglia", "occhi", "bocca", "accessorio", "orecchie"]
PESI = dict(pelle=[20, 26, 24, 12, 8, 6, 4], forma=[50, 25, 25], acconciatura=[10, 16, 8, 5, 7, 6, 12, 7, 8, 5, 9, 7], colore=[24, 22, 18, 10, 8, 6, 4, 8],
            barba=[40, 20, 16, 14, 10], sopracciglia=[40, 30, 30], occhi=[40, 30, 30], bocca=[30, 35, 20, 15], accessorio=[78, 8, 8, 6], orecchie=[70, 30])


def mulberry32(seme):
    a = [seme & M]

    def prossimo():
        a[0] = (a[0] + 0x6D2B79F5) & M
        t = a[0]
        t = ((t ^ (t >> 15)) * (t | 1)) & M
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & M)) & M
        return ((t ^ (t >> 14)) & M) / 4294967296
    return prossimo


FAMIGLIE = {"R": [0, 9], "C": [1, 6, 7, 10, 11], "L": [4, 5, 8], "I": [2, 3]}


PELLE_NEUTRA = 2


def pulisci(tratti):
    o = {}
    if not isinstance(tratti, dict):
        return o
    if type(tratti.get("p")) is int and 0 <= tratti["p"] <= 6:
        o["p"] = tratti["p"]
    if type(tratti.get("c")) is int and 0 <= tratti["c"] <= 7:
        o["c"] = tratti["c"]
    if tratti.get("a") in FAMIGLIE:
        o["a"] = tratti["a"]
    if type(tratti.get("b")) is int and tratti["b"] in (0, 1):
        o["b"] = tratti["b"]
    if o.get("b") == 1 and type(tratti.get("f")) is int and tratti["f"] in (0, 1):
        o["f"] = tratti["f"]
    return o


def scegli_con(u, pesi):
    n = int(u * sum(pesi))
    c = 0
    for j, p in enumerate(pesi):
        c += p
        if n < c:
            return j
    return len(pesi) - 1


def estrai(i, grezzo=False, tratti=None):
    if not (isinstance(i, int) and 0 <= i <= M):
        i = 0
    r = mulberry32((((i * 0x9E3779B1) & M) ^ 0xA5C1D1CE) & M)
    v = {}
    for k in ORDINE:
        v[k] = scegli_con(r(), PESI[k])
    u11, u12 = r(), r()
    tr = pulisci(tratti)
    v["pelle"] = tr.get("p", PELLE_NEUTRA)          # l'estrazione della pelle si fa (l'ordine non cambia) ma senza `p` si scarta
    if "c" in tr:
        v["colore"] = tr["c"]
    if "a" in tr and v["acconciatura"] not in FAMIGLIE[tr["a"]]:
        fam = FAMIGLIE[tr["a"]]
        v["acconciatura"] = fam[scegli_con(u11, [PESI["acconciatura"][x] for x in fam])]
    if tr.get("b") == 0:
        v["barba"] = 0
    elif tr.get("b") == 1 and v["barba"] < 2:
        v["barba"] = [2, 3, 4][scegli_con(u12, [16, 14, 10])]
    if tr.get("f") == 1:
        v["barba"] = 3
    elif tr.get("f") == 0 and v["barba"] == 3:
        v["barba"] = [2, 4][scegli_con(u12, [16, 10])]
    if not grezzo:
        if v["accessorio"] == 2 and v["acconciatura"] in (3, 4, 8):
            v["accessorio"] = 0
        if v["accessorio"] == 1 and v["acconciatura"] == 7:
            v["accessorio"] = 0
    return [v[k] for k in ORDINE]


ORDINE2 = ["espressione", "variante", "guance", "rughe", "naso", "sfondo", "maglia", "colletto", "spalle"]
PESI2 = dict(espressione=[52, 20, 12, 8, 8], variante=[50, 28, 22], guance=[62, 38], rughe=[84, 16], naso=[50, 28, 22],
             sfondo=[28, 24, 18, 16, 14], maglia=[40, 22, 20, 18], colletto=[55, 25, 20], spalle=[60, 40])


def estrai3(i):
    """Le nove estrazioni della versione 3: vengono DOPO le dieci e dopo u11 e u12 (che qui si scartano), mai influenzate dai tratti."""
    if not (isinstance(i, int) and 0 <= i <= M):
        i = 0
    r = mulberry32((((i * 0x9E3779B1) & M) ^ 0xA5C1D1CE) & M)
    for _ in ORDINE:
        r()
    r(), r()
    return [scegli_con(r(), PESI2[k]) for k in ORDINE2]


def vettori():
    return {int(i): [int(x) for x in resto.split()] for i, resto in re.findall(r"^VETTORE (\d+): ([\d ]+)$", SPEC, re.M)}


def test_vettori_di_prova_della_specifica():
    v = vettori()
    assert set(v) == {1, 2, 3, 100, 4567, 7627}
    for i, atteso in v.items():
        assert estrai(i) == atteso, i


def vettori2():
    return [(int(i), json.loads(tr), [int(x) for x in resto.split()])
            for i, tr, resto in re.findall(r"^VETTORE2 (\d+) (\{.*?\}): ([\d ]+)$", SPEC, re.M)]


def test_vettori_di_prova_con_i_tratti():
    v = vettori2()
    assert len(v) == 7
    for i, tratti, atteso in v:
        assert estrai(i, tratti=tratti) == atteso, i
    # senza tratti (o con tratti non validi) è la versione 1
    assert estrai(7627, tratti={"c": 9, "a": "X"}) == estrai(7627) and estrai(5, tratti=None) == estrai(5) and estrai(5, tratti="no") == estrai(5)


def test_i_tratti_rispettano_le_famiglie():
    for i in range(1, 400):
        for fam, membri in FAMIGLIE.items():
            assert estrai(i, tratti={"a": fam})[2] in membri
        assert estrai(i, tratti={"b": 0})[4] == 0
        assert estrai(i, tratti={"b": 1})[4] >= 2
        assert estrai(i, tratti={"c": 6})[3] == 6
        assert estrai(i, tratti={"p": 3})[0] == 3 and estrai(i, tratti={"p": 9})[0] == PELLE_NEUTRA     # `p` valido si usa, non valido si ignora
        assert estrai(i, tratti={"b": 1, "f": 1})[4] == 3
        assert estrai(i, tratti={"b": 1, "f": 0})[4] in (1, 2, 4) and estrai(i, tratti={"f": 1}) == estrai(i)   # `f` senza `b` = 1 non conta


def test_senza_tratti_la_carnagione_e_neutra_e_mai_dal_seme():
    assert all(estrai(i)[0] == PELLE_NEUTRA for i in range(0, 3001))
    assert all(estrai(i, tratti={"c": 4, "a": "L", "b": 1})[0] == PELLE_NEUTRA for i in range(0, 500))
    # le altre estrazioni restano al loro posto: la pelle estratta c'è ancora ma non si usa
    assert estrai(1)[1:] == [0, 10, 0, 3, 1, 0, 1, 0, 1]


def test_regole_di_coerenza_della_specifica():
    trovate = re.findall(r"^COERENZA (\d+): ([\d ]+) -> ([\d ]+)$", SPEC, re.M)
    assert len(trovate) == 2
    for i, grezzo, finale in trovate:
        assert estrai(int(i), grezzo=True) == [int(x) for x in grezzo.split()]
        assert estrai(int(i)) == [int(x) for x in finale.split()]


def test_primi_numeri_di_mulberry32():
    for seme, numeri in re.findall(r"^MULBERRY (\d+): ([\d. ]+)$", SPEC, re.M):
        r = mulberry32(int(seme))
        assert [f"{r():.10f}" for _ in numeri.split()] == numeri.split()


def test_i_pesi_fanno_cento_e_le_combinazioni_sono_tante():
    prodotto = 1
    for k in ORDINE:
        assert sum(PESI[k]) == 100, k
        prodotto *= len(PESI[k])
    assert prodotto >= 10000
    assert f"{prodotto:,}".replace(",", ".") in SPEC


def test_deterministico_e_vari():
    assert estrai(4567) == estrai(4567)
    distinti = {tuple(estrai(i)) for i in range(1, 3001)}
    assert len(distinti) > 2900                      # volti quasi sempre diversi


def test_id_non_valido_vale_zero():
    assert estrai(-5) == estrai(0) == estrai(2 ** 32)


def esegui_node(codice):
    r = subprocess.run([NODE, "-e", f"const A=require({json.dumps(str(AVATAR_JS))});{codice}"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_il_generatore_web_da_gli_stessi_indici_del_riferimento():
    out = esegui_node('const o=[];for(let i=0;i<=3000;i++){const v=A.estrai(i);o.push(A.ORDINE.map(k=>v[k]))}'
                      'for(const i of [4294967295,123456789,7627]){const v=A.estrai(i);o.push(A.ORDINE.map(k=>v[k]))}console.log(JSON.stringify(o));')
    dati = json.loads(out)
    ids = list(range(0, 3001)) + [4294967295, 123456789, 7627]
    for i, indici in zip(ids, dati):
        assert indici == estrai(i), i
    assert json.loads(esegui_node('console.log(JSON.stringify(A.ORDINE))')) == ORDINE
    assert json.loads(esegui_node('console.log(JSON.stringify(A.PESI))')) == PESI


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_il_generatore_web_con_i_tratti_e_uguale_al_riferimento():
    casi = [{"c": 3, "a": "L", "b": 1}, {"a": "R", "b": 0}, {"a": "I"}, {"b": 1}, {"p": 6, "c": 7}, {"c": 9, "a": "X"}, {"a": "C", "b": 1, "p": 2}, {"b": 1, "f": 1}, {"b": 1, "f": 0, "p": 4}, {"f": 1}, {"p": 7}, "x", None]
    out = esegui_node(f'const c={json.dumps(casi)};const o=[];for(let i=0;i<300;i++)for(const t of c){{const v=A.estrai(i,t);o.push(A.ORDINE.map(k=>v[k]))}}console.log(JSON.stringify(o));')
    dati = json.loads(out)
    k = 0
    for i in range(300):
        for t in casi:
            assert dati[k] == estrai(i, tratti=t), (i, t)
            k += 1
    for i, tratti, atteso in vettori2():
        assert json.loads(esegui_node(f'const v=A.estrai({i},{json.dumps(tratti)});console.log(JSON.stringify(A.ORDINE.map(k=>v[k])))')) == atteso
    a = esegui_node('console.log(A.svg(1,{ruolo:"C",c1:"#d11f2f",c2:"#111827",tratti:{c:3,a:"L",b:1}}) === A.svg(1,{ruolo:"C",c1:"#d11f2f",c2:"#111827"}))')
    assert a.strip() == "false"                       # i tratti cambiano il disegno


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_mulberry32_web_uguale_alla_specifica():
    out = json.loads(esegui_node('const r=A.mulberry32(12345);console.log(JSON.stringify([r(),r(),r()]))'))
    r = mulberry32(12345)
    assert out == [r(), r(), r()]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_svg_valido_deterministico_e_sicuro():
    out = esegui_node('const o={};for(const id of [1,2,3,100,4567,7627]){o[id]=[A.svg(id,{ruolo:"C",c1:"#d11f2f",c2:"#111827"}),A.svg(id,{ruolo:"P",c1:"#d11f2f",c2:"#111827"}),A.svg(id)]}'
                      'o.stesso=A.svg(1,{ruolo:"C",c1:"#d11f2f",c2:"#111827"});o.testo=A.svg("1<script>");console.log(JSON.stringify(o));')
    d = json.loads(out)
    assert d["stesso"] == d["1"][0]                  # stesso id e stessi colori: stesso disegno
    assert d["testo"] == json.loads(esegui_node('console.log(JSON.stringify(A.svg(0)))'))   # id non numerico: trattato come 0, nessun testo dell'utente nel disegno
    for i in ("1", "2", "3", "100", "4567", "7627"):
        campo, portiere, senza = d[i]
        for s in d[i]:
            assert "<script" not in s and "onload" not in s and "http://" not in s.replace('xmlns="http://www.w3.org/2000/svg"', "")
            radice = ET.fromstring(s)                # XML ben formato
            assert radice.attrib["viewBox"] == "0 0 100 100" and radice.attrib["aria-hidden"] == "true"
        assert "#d4f34a" in portiere and "#d4f34a" not in campo      # i guanti li hanno solo i portieri
        assert len(campo) < 6000                      # leggero
    assert len({d[i][0] for i in ("1", "2", "3", "100", "4567", "7627")}) == 6           # id diversi, disegni diversi


def vettori3():
    return {int(i): [int(x) for x in resto.split()] for i, resto in re.findall(r"^VETTORE3 (\d+): ([\d ]+)$", SPEC, re.M)}


def test_vettori_della_versione_3_e_pesi():
    v = vettori3()
    assert set(v) == {1, 2, 3, 100, 4567, 7627}
    for i, atteso in v.items():
        assert estrai3(i) == atteso, i
    for k in ORDINE2:
        assert sum(PESI2[k]) == 100, k
    # i vettori vecchi non cambiano: le nuove estrazioni stanno in coda
    assert estrai(1) == [2, 0, 10, 0, 3, 1, 0, 1, 0, 1]


def test_tutte_le_varianti_nuove_compaiono_con_frequenze_vicine_ai_pesi():
    for k_idx, k in enumerate(ORDINE2):
        conteggi = [0] * len(PESI2[k])
        for i in range(1, 3001):
            conteggi[estrai3(i)[k_idx]] += 1
        assert all(c > 0 for c in conteggi), (k, conteggi)
        for c, p in zip(conteggi, PESI2[k]):
            assert abs(c / 3000 * 100 - p) < 4, (k, conteggi)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_il_generatore_web_da_le_stesse_nove_estrazioni_nuove():
    out = esegui_node('const o=[];for(let i=0;i<=3000;i++){const v=A.estrai(i,{c:2,a:"L",b:1});o.push(A.ORDINE2.map(k=>v[k]))}console.log(JSON.stringify(o));')
    dati = json.loads(out)
    for i, indici in enumerate(dati):
        assert indici == estrai3(i), i                     # i tratti non toccano le estrazioni nuove
    assert json.loads(esegui_node('console.log(JSON.stringify(A.ORDINE2))')) == ORDINE2
    assert json.loads(esegui_node('console.log(JSON.stringify(A.PESI2))')) == PESI2
    assert esegui_node('console.log(A.versione)').strip() == "3"


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_svg_versione_3_numero_e_dimensioni():
    out = esegui_node('const o=[];for(let i=1;i<=400;i++)o.push(A.svg(i,{ruolo:i%9?"A":"P",c1:"#d11f2f",c2:"#111827"}));'
                      'o.push(A.svg(5,{c1:"#d11f2f",c2:"#111827",numero:12}),A.svg(5,{c1:"#d11f2f",c2:"#111827"}));'
                      'for(const n of [0,100,-1,1.5,"7","<script>",null])o.push(A.svg(5,{c1:"#d11f2f",c2:"#111827",numero:n}));console.log(JSON.stringify(o));')
    tutti = json.loads(out)
    assert max(len(s) for s in tutti) < 9000                # leggero
    for s in tutti[:60]:
        ET.fromstring(s)                                    # XML ben formato
        assert "<script" not in s and "onload" not in s and "http://" not in s.replace('xmlns="http://www.w3.org/2000/svg"', "")
    con, senza, *non_validi = tutti[400:]
    assert ">12</text>" in con and "<text" not in senza
    assert all("<text" not in s for s in non_validi)         # numero fuori da 1-99 o non intero: nessun testo
    assert len(set(tutti[:400])) > 395


def test_nessuna_regola_per_nome_e_dati_validi_se_ci_sono():
    js = AVATAR_JS.read_text(encoding="utf-8")
    # nessuna regola per nome o nazionalità; i tratti del giocatore sono solo p, c, a, b, f (docs/AVATAR-DIRITTI.md)
    assert not re.search(r"\.nome\b", js) and "nazionalit" not in js.lower()
    # senza tratti la pelle è neutra e fissa: nel generatore la pelle non si sceglie mai dal seme
    assert "v.pelle = tr && tr.p !== undefined ? tr.p : PELLE_NEUTRA" in js
    dati_file = RADICE / "fanta" / "avatar_tratti.json"
    if not dati_file.exists():                      # il progetto pubblico non ha i tratti (docs/AVATAR-DIRITTI.md)
        return
    dati = json.loads(dati_file.read_text(encoding="utf-8"))
    assert all(set(v) <= {"p", "c", "a", "b", "f"} and {"c", "a", "b"} <= set(v) for v in dati["tratti"].values())
