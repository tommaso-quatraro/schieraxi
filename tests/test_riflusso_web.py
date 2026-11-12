"""Pagina strettissima (issue #235, WCAG 2.2 1.4.10 «Reflow»): con lo zoom del browser al 200% un telefono vede 160-195 px.
Prima testata, barra, righe dei giocatori, partite e campo restavano disposti come a 390 px: il titolo spariva, la barra
tagliava «Altro», i nomi andavano a capo una lettera per riga e le sigle delle partite uscivano dalla carta.
Ora sotto i 320 px di larghezza utile la pagina si dispone in una colonna. La misura è il body come contenitore (`pagina`),
non @media: così conta anche il testo «Molto grande» dell'app, che ingrandisce la pagina con `zoom` e le @media non lo vedono.
La prova vera è nel browser (larghezze 160, 195 e 320 px); qui si controlla che le regole ci siano."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
NODE = shutil.which("node")
STRETTA = "@container pagina (max-width: 319.98px) {"
SENZA_COMMENTI = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _blocco(apertura):
    i = CSS.index(apertura) + len(apertura)
    livello, j = 1, i
    while livello:
        livello += {"{": 1, "}": -1}.get(CSS[j], 0)
        j += 1
    return CSS[i:j - 1]


def _regola(blocco, selettore):
    corpo = re.search(r"(?:^|\n)\s*" + re.escape(selettore) + r" \{([^}]*)\}", blocco)
    assert corpo, selettore
    return corpo.group(1)


def test_il_body_e_il_contenitore_della_pagina():
    assert re.search(r"\nbody \{ container: pagina / inline-size; \}", CSS)
    assert CSS.count(STRETTA) == 1


def test_testata_che_scorre_via_sopra_il_titolo_e_barra_con_le_sole_icone():
    """Grafica B: al telefono i pulsanti della testata stanno nell'angolo, accanto al titolo della schermata. Sotto i 320 px non
    c'è posto per tutti e due: i pulsanti vanno su una riga loro, sopra il titolo, e scorrono via con la pagina (con lo zoom una
    testata fissa copriva un quarto dello schermo); il titolo prende tutta la riga."""
    b = _blocco(STRETTA)
    testata = _regola(b, ".testata")
    assert "position: relative" in testata and "justify-content: flex-end" in testata
    posto = " ".join(_corpi(".capo-pagina", b))                    # dal 12/11/2026 (#618) in testata c'è solo la lente
    assert posto.count("--posto-bottoni: 0px") >= 1
    assert "padding-right: var(--posto-bottoni)" in " ".join(_corpi("#titolo-pagina"))   # niente posto lasciato ai pulsanti accanto al titolo
    etichette = _regola(b, ".scheda > span")                                       # il nome della scheda resta ai lettori di schermo
    assert "clip: rect(0 0 0 0)" in etichette and "width: 1px" in etichette and "display: none" not in etichette


def test_righe_dei_giocatori_impilate_e_partite_su_due_righe():
    b = _blocco(STRETTA)
    # grafica B (spec §8.4): volto e numeri sopra, nome, partita ed etichette sotto a tutta larghezza
    assert 'grid-template-areas: "volto fv" "volto gioca" "testo testo"' in _regola(b, ".voce-g")
    assert "flex-wrap: wrap" in _regola(b, ".riga")
    # scheda del giocatore: le cifre (fantavoto atteso | gioca N%) una sotto l'altra, il filo sopra invece che in mezzo
    assert "grid-template-columns: minmax(0, 1fr)" in _regola(b, ".cifre-oggi")
    seconda = _regola(b, ".cifre-oggi > .cifra + .cifra")
    assert "border-left: 0" in seconda and "border-top: 1px solid var(--filo)" in seconda


def test_formazione_il_campo_va_a_capo():
    b = _blocco(STRETTA)
    assert "flex-wrap: wrap" in _regola(b, ".linea")
    assert "flex: 0 1 64px" in _regola(b, ".pedina")                                # due pedine per fila
    # cognome intero, mai «Zosaba Nd…»: dal #265 vale a ogni larghezza (tests/test_testo_intero_web.py), non solo qui


def test_squadra_rose_e_calendario_non_si_tagliano():
    """La mia squadra (Impostazioni, #618): stemma e maglia uno sotto l'altro; i controlli a segmenti vanno su due righe invece
    di sovrapporsi."""
    b = _blocco(STRETTA)
    assert "grid-template-columns: 1fr" in _regola(b, ".immagini-squadra")
    assert "flex-wrap: wrap" in _regola(b, ".segmenti")


def test_scheda_del_giocatore_in_colonna():
    """Il foglio che si apre toccando un giocatore: a 160 px il volto grande accanto al nome spingeva il nome fuori e il foglio
    scorreva di lato."""
    b = _blocco(STRETTA)
    assert "grid-template-columns: 1fr" in _regola(b, ".intestazione-scheda")
    assert "padding-left: 8px" in _regola(b, ".foglio-corpo")
    # dentro la scheda: probabilità (segna, assist…), «Perché questo numero», prossime partite e forma andavano oltre la carta
    assert "repeat(2, minmax(0, 1fr))" in _regola(b, ".stat-fila, .stat-fila.quattro, .statistiche")
    assert "grid-template-columns: 1fr" in _regola(b, ".perche-voce")
    assert "repeat(3, minmax(0, 1fr))" in _regola(b, ".prossime")
    # la forma (5 pallini da 40 px) accanto ad «Andamento» non stava già a 320 px: va a capo a ogni larghezza
    assert re.search(r"\n\.pallini \{[^}]*flex-wrap: wrap", CSS) and ".pallini {" not in b


def test_le_query_senza_nome_restano_dentro_i_loro_contenitori():
    """Il body è un contenitore: una @container senza nome su un elemento che non sta in .df-carta o in li.con-confronto
    risponderebbe alla larghezza della pagina. Le due che ci sono toccano solo i loro elementi."""
    for m in re.finditer(r"@container \(([^)]*)\) \{", CSS):
        selettori = re.findall(r"(?:^|\n)\s*([^{}\n]+?) \{", _blocco(m.group(0)))
        assert selettori, m.group(0)
        for s in selettori:
            assert all(p.strip().startswith((".con-confronto ", ".df-")) for p in s.split(",")), s


def _corpi(selettore, testo=SENZA_COMMENTI):
    """I corpi di tutte le regole (anche dentro le @media e le @container) il cui elenco di selettori contiene proprio `selettore`."""
    return [corpo for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", testo) if selettore in [s.strip() for s in sel.split(",")]]


def test_titolo_nome_della_squadra_e_data_dei_dati_vanno_a_capo():
    """Issue #286: nella testata «Real Es…» a 320 px, «Real Esempi…» a 390 px con il testo «Grande» e un nome di 25 caratteri
    tagliato anche a 390 px; «dati del 26 …» lo stesso. Con la grafica B nome e data stanno nella riga di stato sotto il titolo
    della schermata (il titolo della rosa è il nome di una squadra). Mai «…» (CLAUDE.md): vanno a capo, a ogni larghezza, e una
    parola più lunga della riga si spezza invece di uscire."""
    for selettore in ("#titolo-pagina", ".stato-pagina"):
        corpi = " ".join(_corpi(selettore))
        assert corpi, selettore
        assert "ellipsis" not in corpi and "nowrap" not in corpi, selettore
        assert "overflow-wrap: anywhere" in corpi, selettore


def test_lo_stemma_nella_riga_di_stato_lascia_posto_al_nome():
    """A 320 px lo stemma della testata (42 px più lo spazio) lasciava al nome della squadra 74 px e la testata, ferma in alto,
    cresceva a 117 px. Ora lo stemma sta nella riga di stato, alto quanto il testo (20 px), e la riga va a capo intorno a lui."""
    corpo = " ".join(_corpi(".stemma-stato"))
    assert "height: 20px" in corpo and "width: 20px" in corpo and "vertical-align" in corpo
    assert ".stemma-testata" not in CSS


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_il_conto_alla_rovescia_non_lascia_l_unita_da_sola():
    """Issue #286: a 390 px «1 giorno 8» su una riga e «h» da sola sotto (a 320 px anche «1», «giorno» e «8 h» su tre righe). Il
    numero e la sua unità stanno insieme con uno spazio che non va a capo: si va a capo solo tra «1 giorno» e «8 h». Qui testoConto
    di app.js (dal 12/11/2026 «Si chiude…» e «fra…», in testa alla Formazione), eseguito con node e l'orologio fermo."""
    inizio, fine = "function parseData(s)", "// ETag e If-Match"
    codice = "\n".join([
        TESTI,
        "const FERMO = Date.parse('2026-10-26T09:35:00Z'), DataVera = Date;",
        "globalThis.Date = class extends DataVera { constructor(...a) { super(...(a.length ? a : [FERMO])); } static now() { return FERMO; } };",
        APP[APP.index(inizio):APP.index(fine)],
        APP[APP.index("const scadenzaDi = "):APP.index("// Account nuovo, senza rose")],
        "const minuti = [32 * 60 + 5, 2 * 1440 + 14 * 60, 3 * 60 + 10, 45, -5], fuori = {};",
        "for (const L of ['it', 'en']) { LINGUA = L; fuori[L] = minuti.map(m => testoConto({ giornata: 9, scadenza: new DataVera(FERMO + m * 60000).toISOString() }).manca); }",
        "LINGUA = 'it'; fuori.chiusa = testoConto({ giornata: 9, scadenza: new DataVera(FERMO - 300000).toISOString() }).chiude;",
        "console.log(JSON.stringify(fuori));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    fuori = json.loads(r.stdout.strip().splitlines()[-1])
    nb = " "
    assert fuori["it"] == [f"fra 1{nb}giorno 8{nb}h", f"fra 2{nb}giorni 14{nb}h", f"fra 3{nb}h 10{nb}min", f"fra 45{nb}min", ""]
    assert fuori["en"] == [f"in 1{nb}day 8{nb}h", f"in 2{nb}days 14{nb}h", f"in 3{nb}h 10{nb}min", f"in 45{nb}min", ""]
    assert fuori["chiusa"] == "Formazione chiusa"                       # scadenza passata: niente conto


def test_le_impostazioni_non_scorrono_di_lato():
    """Issue #288: Notifiche a 320 px con il testo «Molto grande» scorreva di lato (337 px contro 320): la griglia delle Impostazioni
    aveva una colonna larga quanto il contenuto più lungo. Dal 12/11/2026 (#618) la pagina è una colonna che non supera la pagina
    (`min-width: 0`), e le due colonne di sezioni arrivano solo da 768 px."""
    assert "min-width: 0" in _regola(CSS, ".imp-griglia")
    assert re.search(r"@media \(min-width: 768px\) \{\s*\.imp-griglia \{ columns: 2;", CSS)


def test_le_righe_delle_regole_vanno_a_capo_sotto_i_320_px():
    """Regole e Notifiche a 320 px con il testo «Molto grande»: accanto al −/+ o al menu il nome della regola restava largo ~60 px,
    una parola per riga. Sotto i 320 px utili il controllo va sotto il nome quando non c'è posto."""
    b = _blocco(STRETTA)
    assert "flex-wrap: wrap" in _regola(b, ".riga-regola")
    assert "max-width: 100%" in _regola(b, ".riga-regola > select.scelta-corta")


def test_accesso_e_primo_avvio_nella_pagina_strettissima():
    """PR 12 della grafica B: con lo zoom al 200% il nome disegnato dell'accesso (192 px) si stringe invece di far scorrere la
    pagina di lato, e i tre passi del primo avvio vanno uno sotto l'altro (affiancati erano larghi 60 px l'uno)."""
    assert "max-width: 100%" in _regola(CSS, ".accesso-titolo .wm")
    stretta = _blocco(STRETTA)
    assert "flex-direction: column" in _regola(stretta, ".pa-passi")
    assert "border-top: 1px solid var(--filo)" in _regola(stretta, ".pa-passi li + li")
    # la casella da 44 px con il margine di −9 px usciva di 1 px dalla pagina (riempimento di 8 px): Impostazioni > Avanzate a 195 px
    assert "margin-right: -8px" in _regola(stretta, ".interruttore input[type=\"checkbox\"]")
