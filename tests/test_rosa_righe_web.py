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

import codice_web

APP = codice_web.app()
NODE = shutil.which("node")


def _pezzo(inizio: str, fine: str) -> str:
    return APP[APP.index(inizio):APP.index(fine)]


def _esegui(chiamata: str, lingua: str = "it"):
    testi = codice_web.leggi("testi.js")
    codice = "\n".join([
        testi,
        f"LINGUA = '{lingua}';",
        re.search(r"^const SIGLE = \{.*?\};$", APP, re.M | re.S).group(0),
        _pezzo("function esc(x)", "// Numero con il segno"),
        _pezzo("const STATO_PARTITA =", "// Le regole riconosciute"),
        _pezzo("// Lo stato di un giocatore, dal codice", "// Il nome del club"),
        _pezzo("const SOGLIA_GIOCA", "// Il nome per i lettori di schermo viene"),
        re.search(r"^const nomeClub = .*$", APP, re.M).group(0),
        re.search(r"^const vsAt = .*$", APP, re.M).group(0),
        re.search(r"^const partitaRiga = .*$", APP, re.M).group(0),
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
def test_i_lettori_di_schermo_sentono_la_partita_in_frase():
    """#453: dopo «MIL» il lettore di schermo diceva «GEN fuori» (vietato dal vocabolario): ora «in trasferta contro Genoa»."""
    voce = lambda html: re.search(r'<span class="solo-lettori">(.*?)</span>', html).group(1)  # noqa: E731
    fuori, casa, doppio = _esegui('[vsAt({in_casa: false, avversario: "genoa"}), vsAt({in_casa: true, avversario: "lazio"}),'
                                  ' partitaRiga({squadra: "milan", in_casa: false, avversario: "genoa"})]')
    assert voce(fuori) == "in trasferta contro Genoa" and voce(casa) == "in casa contro Lazio"
    assert _testo(doppio) == "MIL @ GEN in trasferta contro Genoa"          # «@ GEN» si vede, la frase si sente
    assert voce(_esegui('vsAt({in_casa: false, avversario: "genoa"})', "en")) == "away against Genoa"


@pytest.mark.skipif(not NODE, reason="serve node")
def test_valore_della_rosa_prima_e_dopo_la_partita():
    prima, medio, sicuro, infortunato, attesa, fatto, nessuna = _esegui("""[
      valoreRosa({fv_atteso: 5.7, p_voto: 0.24}, {id: 1}),
      valoreRosa({fv_atteso: 6.0, p_voto: 0.794}, {id: 1}),
      valoreRosa({fv_atteso: 6.1, p_voto: 0.796}, {id: 1}),
      valoreRosa({fv_atteso: 6.4, p_voto: 0, stato: "infortunato", etichetta: {codice: "infortunato", testo: "Infortunato", tono: "negativo"}}, {id: 1}),
      valoreRosa({fv_atteso: 5.7, p_voto: 0.24, stato_partita: "attesa_voti", etichetta: {codice: "voto_in_arrivo", testo: "Voto in arrivo", tono: "neutro"}}, {id: 1}),
      valoreRosa({fv_atteso: 5.7, p_voto: 0.9, stato_partita: "fatto", fv_preso: 7.5, etichetta: {codice: "voto", testo: "Ha giocato", tono: "positivo"}}, {id: 1}),
      valoreRosa(null, {id: 1})]""")
    # grafica B (spec §8.4, C8): «gioca N%» e il fantavoto atteso in due colonne, nello stesso ordine di ogni riga dei giocatori.
    # Dal 12/11/2026 (#616) «gioca N%» c'è solo sotto l'80%: rosso sotto 50, arancio fra 50 e 79, deciso sul numero che si legge
    assert _testo(prima) == "gioca 24% Fantavoto atteso 5,7"             # il nome del numero per i soli lettori di schermo
    assert '<span class="pv-g basso">gioca 24%</span>' in prima
    assert '<span class="pv-g medio">gioca 79%</span>' in medio
    assert _testo(sicuro) == "Fantavoto atteso 6,1" and "gioca" not in sicuro          # 79,6% si legge 80%: non è sotto l'80%
    assert _testo(infortunato) == "Fantavoto atteso 6,4" and "gioca" not in infortunato   # non gioca di sicuro: lo dice la parola
    assert _testo(attesa) == "–" and "gioca" not in attesa                  # a partita iniziata mai «gioca N%»
    assert _testo(fatto) == "fantavoto 7,5"
    assert _testo(nessuna) == "non gioca" and "fantavoto" not in nessuna and "%" not in nessuna
