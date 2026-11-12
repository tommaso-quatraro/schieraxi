"""Diario, web (#614, revisione di #642): la frase sulle giornate che non hanno un verdetto la scrive il server (`nota` di
`scelte_tue` e di `precisione.confronto`, `diario.nota_confronto`) e la web la mostra così com'è, tradotta con `nota_frase`.
Prima la web decideva da sola: con le giornate segnate ma senza la consigliata di allora diceva «Non sappiamo ancora cosa hai
schierato», nascondeva «Le tue scelte» o diceva «Finora hai schierato gli stessi undici del consiglio» anche con cinque giornate
diverse lasciate fuori. Si provano le funzioni vere di `app.js`, con node, sulle risposte vere del server."""
import html
import json
import re
import shutil
import subprocess

import pytest

from fanta import diario, precisione

import codice_web

APP = codice_web.app()
TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
ST = "2026-27"
NON_SAPPIAMO = {"it": "Non sappiamo ancora cosa hai schierato", "en": "We don't know yet what you fielded"}


def _funzione(nome: str) -> str:
    inizio = APP.index(f"function {nome}(")
    return APP[inizio:APP.index("\n}\n", inizio) + 3]


def _riga(prefisso: str) -> str:
    return next(r for r in APP.splitlines() if r.startswith(prefisso)) + "\n"


def _voce(g, tue, mostrata=True):
    """Una voce del Diario con la tua formazione: titolari 1-11 nella consigliata, i tuoi `tue`."""
    riga = lambda ids, r: {"reale": r, "atteso": 70.0, "titolari": [{"id": i, "nome": f"G{i}", "ruolo": "C"} for i in ids]}  # noqa: E731
    return {"stagione": ST, "giornata": g, "giornata_lega": g, "schierata": riga(tue, 66.0) | {"tipo": "manuale"},
            "consigliata": riga(range(1, 12), 70.0) | {"origine": "mostrata" if mostrata else "ricostruita"}, "giocatori": []}


UGUALI, DIVERSI = list(range(1, 12)), list(range(2, 13))
# le tre situazioni della revisione: solo giornate senza la consigliata di allora; una sola confrontabile, con gli stessi titolari,
# e cinque diverse lasciate fuori; una con un verdetto e una lasciata fuori
CASI = {"tutte_fuori": [_voce(g, DIVERSI, mostrata=False) for g in (1, 2, 3)],
        "una_uguale": [_voce(6, UGUALI)] + [_voce(g, DIVERSI, mostrata=False) for g in range(1, 6)],
        "verdetto": [_voce(2, DIVERSI), _voce(1, DIVERSI, mostrata=False)]}


def _node(codice: str, lingua: str):
    if NODE is None:
        pytest.skip("serve node")
    prova = (TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _riga("const num = ") + _riga("const virgola = ") + _riga("const alPercento = ")
             + _riga("const elidiOrdinali = ") + _funzione("esc") + _funzione("nomeGiornata") + _funzione("cartaPrecisione")
             + _funzione("cartaScelteTue") + codice)
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo(h: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", h))


def _frase_confronto(carta: str) -> str:
    """La frase della terza voce di «Quanto ci abbiamo preso» (consigliata contro la tua)."""
    return _testo(carta.split('class="qp-voce"')[3].split('class="qp-frase">', 1)[1].split("</div>", 1)[0]).strip()


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_le_due_carte_mostrano_la_frase_del_server(lingua):
    risposte = {nome: {"precisione": precisione.riassunto(voci), "scelte_tue": diario.scelte_tue(voci)} for nome, voci in CASI.items()}
    carte = _node(f"""
    const r = {json.dumps(risposte)};
    console.log(JSON.stringify(Object.fromEntries(Object.entries(r).map(([k, d]) => [k, [cartaPrecisione(d.precisione), cartaScelteTue(d.scelte_tue, x => num(x, 1))]]))));
    """, lingua)
    attese = {"it": {"tutte_fuori": "3 giornate non entrano nel confronto: la consigliata di allora non era stata salvata.",
                     "una_uguale": "Hai schierato gli stessi undici della consigliata in tutte le giornate in cui era stata salvata. "
                                   "5 giornate non entrano nel confronto: la consigliata di allora non era stata salvata.",
                     "verdetto": "1 giornata non entra nel confronto: la consigliata di allora non era stata salvata."},
              "en": {"tutte_fuori": "3 matchdays are left out of the comparison: the recommended lineup of the time had not been saved.",
                     "una_uguale": "You fielded the same eleven as the recommended lineup in every matchday where it had been saved. "
                                   "5 matchdays are left out of the comparison: the recommended lineup of the time had not been saved.",
                     "verdetto": "1 matchday is left out of the comparison: the recommended lineup of the time had not been saved."}}[lingua]
    for nome, (qp, st) in carte.items():
        assert attese[nome] in _testo(qp) and attese[nome] in _testo(st), nome            # la stessa frase nei due riquadri
        assert NON_SAPPIAMO[lingua] not in _testo(qp), nome
        assert "frase.diario" not in qp + st and "undefined" not in qp + st and "null" not in qp + st, nome
        if lingua == "it":
            assert attese[nome] == risposte[nome]["scelte_tue"]["nota"]                  # in italiano: il testo del server, uguale
    assert _frase_confronto(carte["tutte_fuori"][0]) == attese["tutte_fuori"]          # senza verdetto la frase è solo quella
    assert "scelte-tue" in carte["una_uguale"][1]                                       # «Le tue scelte» non sparisce più
    # nell'andamento, una giornata senza la consigliata di allora ha i tuoi punti ma non la differenza (il server manda null):
    # «(0,0)» direbbe che hai fatto quanto la consigliata
    andamento = _testo(carte["verdetto"][0].split('class="qp-giornate"', 1)[1])
    assert andamento.count("(") == 1 and ("(+4,0)" if lingua == "it" else "(+4.0)") in andamento    # consigliata meno tua


def test_senza_niente_di_schierato_resta_la_frase_di_prima_e_niente_scelte():
    voci = [{"stagione": ST, "giornata": 1, "schierata": None, "consigliata": {"reale": 70.0, "atteso": 70.0, "titolari": [], "origine": "mostrata"}}]
    qp, st = _node(f"""
    console.log(JSON.stringify([cartaPrecisione({json.dumps(precisione.riassunto(voci))}), cartaScelteTue({json.dumps(diario.scelte_tue(voci))}, x => num(x, 1))]));
    """, "it")
    assert NON_SAPPIAMO["it"] in _testo(qp) and st == ""


def test_un_server_di_prima_senza_la_frase_non_rompe_le_carte():
    """Un server che non manda `nota`: «Le tue scelte» senza giornate non si mostra, il confronto dice la frase di sempre."""
    qp, st = _node("""
    const p = {giornate: 1, confronto: {giornate: 0}, per_giornata: []};
    console.log(JSON.stringify([cartaPrecisione(p), cartaScelteTue({giornate: 0, pochi_dati: true, per_giornata: []}, x => num(x, 1))]));
    """, "it")
    assert NON_SAPPIAMO["it"] in _testo(qp) and st == ""
