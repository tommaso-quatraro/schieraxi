"""Etichette dei giocatori sempre intere nel web (issue #230), come sull'iPhone (PR #228): un'etichetta che non ci sta su una riga
va a capo invece di finire con i puntini («In dubb…», «Probabile titol…» a 320 px e con il testo grande). Prima si va a capo tra i
pezzi separati da «·» («In dubbio ·» sopra, «gioca 62%» sotto), poi tra le parole; il testo non si accorcia e non si rimpicciolisce.
Dalla grafica B l'etichetta è testo colorato senza capsula (spec §8.9); va a capo allo stesso modo.
Le funzioni di app.js si provano con node; il CSS si legge da stile.css. La prova nel browser (320-1440 px, chiaro e scuro, testo
grande) è nel collaudo della pull request."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")
# la classe .etichetta delle pillole, non .etichetta-riga, .etichetta-campo o .df-etichetta
CLASSE = re.compile(r"\.etichetta(?![\w-])")


def _pezzo(inizio: str, fine: str) -> str:
    return APP[APP.index(inizio):APP.index(fine)]


def _esegui(chiamata: str):
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    codice = "\n".join([
        testi,
        "LINGUA = 'it';",
        _pezzo("function esc(x)", "const sigla ="),
        re.search(r"^const TITOLARITA = \{.*?\};$", APP, re.M | re.S).group(0),
        _pezzo("const STATO_PARTITA =", "// Il tocco sul fantavoto atteso"),
        f"console.log(JSON.stringify({chiamata}));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _regole():
    """(selettori, corpo) di ogni regola di stile.css, anche dentro le @media; i commenti non contano."""
    senza_commenti = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    return [([s.strip() for s in sel.split(",")], corpo) for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", senza_commenti)]


def _regola(selettore: str) -> str:
    corpi = [corpo for sel, corpo in _regole() if selettore in sel]
    assert corpi, f"manca la regola {selettore} in stile.css"
    return " ".join(corpi)


@pytest.mark.skipif(not NODE, reason="serve node")
def test_il_testo_va_a_capo_prima_tra_i_pezzi_separati_dal_punto():
    pezzi, semplice, tre = _esegui('[testoEtichetta("In dubbio · gioca 62%"), testoEtichetta("Probabile titolare"), testoEtichetta("A · B · C")]')
    # il «·» resta in fondo alla prima riga, come sull'iPhone, attaccato alla parola prima con uno spazio che non va a capo (in una
    # riga strettissima «In dubbio» si divide, ma il «·» non resta mai da solo); lo spazio fra i pezzi è il punto dove si va a capo
    assert pezzi == '<span class="pezzo">In dubbio&nbsp;·</span> <span class="pezzo">gioca 62%</span>'
    assert semplice == "Probabile titolare"                                   # senza «·»: il testo com'è
    assert tre == '<span class="pezzo">A&nbsp;·</span> <span class="pezzo">B&nbsp;·</span> <span class="pezzo">C</span>'
    assert [_testo(h).replace("&nbsp;", " ") for h in (pezzi, semplice, tre)] == ["In dubbio · gioca 62%", "Probabile titolare", "A · B · C"]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_il_testo_del_server_resta_protetto():
    assert _esegui('[testoEtichetta("<b>x</b> · y"), testoEtichetta("<i>")]') == [
        '<span class="pezzo">&lt;b&gt;x&lt;/b&gt;&nbsp;·</span> <span class="pezzo">y</span>', "&lt;i&gt;"]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_la_pillola_del_server_usa_i_pezzi():
    """L'etichetta del server («In dubbio · gioca 55%») arriva intera nella pillola, divisa nei due pezzi."""
    html = _esegui('pillTitolarita({etichetta: {codice: "dubbio", testo: "In dubbio · gioca 55%", tono: "attenzione"}})')
    assert html == '<span class="etichetta arancio"><span class="pezzo">In dubbio&nbsp;·</span> <span class="pezzo">gioca 55%</span></span>'
    # anche i motivi sotto il nome (note lunghe) passano dallo stesso testo
    assert "testoEtichetta(traduciFrase(m.frase, m.testo))" in _pezzo("function etichetteGiocatore(x)", "const nomeClub")


def test_nessuna_pillola_finisce_con_i_puntini():
    for selettori, corpo in _regole():
        if any(CLASSE.search(s) for s in selettori):
            assert "ellipsis" not in corpo and "nowrap" not in corpo, f"{selettori}: un'etichetta non si taglia mai"
            assert not re.search(r"overflow(-x)?\s*:\s*hidden", corpo), f"{selettori}: un'etichetta non si taglia mai"


def test_la_pillola_va_a_capo_dentro_la_riga():
    base = _regola(".etichetta")
    assert "display: inline-block" in base          # un blocco: non si spezza a metà riga di un testo, va a capo al suo interno
    assert "max-width: 100%" in base                 # mai più larga della riga in cui sta
    assert "overflow-wrap: break-word" in base       # ultima scelta: una parola più larga della riga va a capo anche lei
    # grafica B (spec §8.9): l'etichetta è testo colorato, senza capsula né angoli; il testo intero resta la regola
    assert "border-radius" not in base and "999" not in base and "r-pill" not in base
    pezzo = _regola(".etichetta .pezzo")
    assert "display: inline-block" in pezzo and "max-width: 100%" in pezzo


def test_riga_stretta_della_formazione_numeri_sotto_il_nome():
    """Telefono piccolo (320 px) o con il testo «Grande» o «Molto grande»: la colonna del nome di una riga della Formazione (accanto
    ai numeri e al pulsante ⇄) restava larga 10-75 px e le etichette si leggevano a pezzi, a volte una lettera per riga. Come l'iPhone
    con il testo molto grande (RigaGiocatore): fantavoto atteso e «gioca N%» vanno sotto il nome, che con le etichette ha tutta la
    larghezza."""
    # grafica B (spec §8.4): ogni riga di un giocatore è un contenitore («riga»), le righe della Formazione comprese
    assert "container: riga / inline-size" in _regola(".riga-gioc")
    assert 'class="riga-gioc${conConfronto ? " con-confronto" : ""}"' in APP
    blocco = re.search(r"@container riga \(max-width:\s*(\d+)px\)\s*\{\s*(\.con-confronto \.voce-g\b.*?)\n\}", CSS, re.S)
    assert blocco, "manca la riga stretta della Formazione (@container) in stile.css"
    soglia, corpo = int(blocco.group(1)), blocco.group(2)
    # quando la colonna del nome scenderebbe sotto i 90 px circa: la riga è larga circa 255 px a 320 px con il testo «Grande»
    # (scatta) e 288 px a 320 px con il testo normale (resta com'è)
    assert 260 <= soglia < 290
    aree = re.search(r"\.con-confronto \.voce-g \{[^}]*grid-template-areas:\s*([^;]+);", corpo).group(1)
    righe = re.findall(r'"([^"]+)"', aree)
    assert len(righe) == 2 and righe[0].split()[0] == "volto" and "testo" in righe[0] and "gioca" not in righe[0]
    assert {"fv", "gioca"} <= set(righe[1].split())              # i numeri sotto il nome: il nome ha tutta la larghezza
    assert re.search(r"\.con-confronto \.voce-g > \.valore, \.con-confronto \.voce-g > \.pv-g \{[^}]*justify-self: start", corpo)
