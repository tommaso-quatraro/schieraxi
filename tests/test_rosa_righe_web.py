"""Collaudo del 2/11/2026 (giro 5), regressioni sulle righe dei giocatori del web:
- la Rosa scriveva sempre «vs JUV», anche per una partita in trasferta (la Formazione diceva «NAP @ JUV»);
- a partita iniziata la Rosa mostrava ancora «gioca 24%» accanto a «Voto in arrivo»;
- la scheda a partita finita senza voto diceva «Voto in arrivo» due volte (pillola in testa e numero grande);
- la legenda del campo aveva «6,8» anche in inglese."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _pezzo(inizio: str, fine: str) -> str:
    return APP[APP.index(inizio):APP.index(fine)]


def _esegui(chiamata: str, lingua: str = "it"):
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    codice = "\n".join([
        testi,
        f"LINGUA = '{lingua}';",
        re.search(r"^const SIGLE = \{.*?\};$", APP, re.M | re.S).group(0),
        _pezzo("function esc(x)", "// Numero con il segno"),
        _pezzo("const STATO_PARTITA =", "function pillTitolarita"),
        _pezzo("const CODICI_PARTITA_INIZIATA", "function pedina"),
        re.search(r"^const vsAt = .*$", APP, re.M).group(0),
        "const quando = s => 'sab 31 20:45';",
        _pezzo("function valoreRosa", "// ---------------------------------------------------------------- navigazione"),
        f"console.log(JSON.stringify({chiamata}));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def test_riga_della_rosa_casa_e_trasferta_con_la_data():
    riga = _pezzo("async function vistaRosa", "const NOME_IMMAGINE")
    assert "vsAt(p)" in riga and "quando(p.data_partita)" in riga
    assert 't("scambio.vs"' not in APP                                      # «vs» fisso: sbagliato in trasferta


@pytest.mark.skipif(not NODE, reason="serve node")
def test_vs_e_chiocciola():
    fuori, casa = _esegui('[vsAt({in_casa: false, avversario: "juventus"}), vsAt({in_casa: true, avversario: "lazio"})]')
    assert fuori.startswith('<span aria-hidden="true">@ JUV</span>') and casa.startswith('<span aria-hidden="true">vs LAZ</span>')


@pytest.mark.skipif(not NODE, reason="serve node")
def test_valore_della_rosa_prima_e_dopo_la_partita():
    prima, attesa, fatto, nessuna = _esegui("""[
      valoreRosa({fv_atteso: 5.7, p_voto: 0.24}, {id: 1}),
      valoreRosa({fv_atteso: 5.7, p_voto: 0.24, stato_partita: "attesa_voti", etichetta: {codice: "voto_in_arrivo", testo: "Voto in arrivo", tono: "neutro"}}, {id: 1}),
      valoreRosa({fv_atteso: 5.7, p_voto: 0.9, stato_partita: "fatto", fv_preso: 7.5, etichetta: {codice: "voto", testo: "Ha giocato", tono: "positivo"}}, {id: 1}),
      valoreRosa(null, {id: 1})]""")
    # grafica B (spec §8.4, C8): «gioca N%» e il fantavoto atteso in due colonne, nello stesso ordine di ogni riga dei giocatori
    assert _testo(prima) == "gioca 24% 5,7"
    assert '<span class="pv-g basso">gioca 24%</span>' in prima           # sotto il 70% arancio e in grassetto
    assert _testo(attesa) == "–" and "gioca" not in attesa                  # a partita iniziata mai «gioca N%»
    assert _testo(fatto) == "fantavoto 7,5"
    assert _testo(nessuna) == "non gioca" and "fantavoto" not in nessuna and "%" not in nessuna


def test_scheda_niente_stato_doppio_a_partita_finita():
    scheda = _pezzo("async function apriGiocatore", "async function osservatiIds")
    assert "const statoInGrande = finitaP && !(votoGiornata && votoGiornata.fv != null)" in scheda
    assert "${pr && !statoInGrande ? pillTitolarita(pr) : \"\"}" in scheda


@pytest.mark.skipif(not NODE, reason="serve node")
def test_legenda_del_campo_nella_lingua_scelta():
    assert '<b class="fv-esempio">${num(6.8)}</b>' in APP and '<b class="fv-esempio">6,8</b>' not in APP
    assert _esegui("num(6.8)", "en") == "6.8" and _esegui("num(6.8)", "it") == "6,8"
