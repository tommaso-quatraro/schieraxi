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

CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
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
    posto = " ".join(_corpi(".capo-pagina", b) + _corpi("body:has(#bottone-aggiorna:not([hidden])) .capo-pagina", b))
    assert posto.count("--posto-bottoni: 0px") >= 1 and len(_corpi("body:has(#bottone-aggiorna:not([hidden])) .capo-pagina", b)) == 1
    assert "padding-right: var(--posto-bottoni)" in " ".join(_corpi("#titolo-pagina"))   # niente posto lasciato ai pulsanti accanto al titolo
    etichette = _regola(b, ".scheda > span")                                       # il nome della scheda resta ai lettori di schermo
    assert "clip: rect(0 0 0 0)" in etichette and "width: 1px" in etichette and "display: none" not in etichette


def test_righe_dei_giocatori_impilate_e_partite_su_due_righe():
    b = _blocco(STRETTA)
    # grafica B (spec §8.4): volto e numeri sopra, nome, partita ed etichette sotto a tutta larghezza
    assert 'grid-template-areas: "volto fv" "volto gioca" "testo testo"' in _regola(b, ".voce-g")
    assert '"testo testo" "fv gioca"' in _regola(b, ".con-confronto .voce-g")                          # con ⇄ in alto: i numeri sotto il nome
    assert "padding-right: 0" in _regola(b, ".elenco li.con-confronto .voce-g, .elenco.posto-azione .voce-g")   # niente colonna vuota per ⇄
    assert "top:" in _regola(b, ".elenco li.con-confronto .confronta-mini")
    assert "grid-column: 1 / 3" in _regola(b, ".partita .ora")                                          # ora sopra, squadre sotto
    assert "grid-row: 2" in _regola(b, ".partita .sq.casa")
    assert "flex-wrap: wrap" in _regola(b, ".riga")
    # Oggi a giornata in corso: il fantavoto preso o lo stato («In dubbio · gioca 40%») va sotto il nome, non fuori dalla carta
    assert "grid-row: 2" in _regola(b, ".avviso-riga > :nth-child(3)")
    # Oggi: le cifre della formazione (modulo | punti attesi, con la fascia) una sotto l'altra, il filo sopra invece che in mezzo
    assert "grid-template-columns: minmax(0, 1fr)" in _regola(b, ".cifre-oggi")
    seconda = _regola(b, ".cifre-oggi > .cifra + .cifra")
    assert "border-left: 0" in seconda and "border-top: 1px solid var(--filo)" in seconda


def test_formazione_chip_e_campo_vanno_a_capo():
    b = _blocco(STRETTA)
    chips = _regola(b, ".chips.scorri")
    assert "flex-wrap: wrap" in chips and "mask-image: none" in chips                  # tutti i moduli e gli stili in vista, senza scorrere di lato
    assert "flex-wrap: wrap" in _regola(b, ".linea")
    assert "flex: 0 1 64px" in _regola(b, ".pedina")                                # due pedine per fila
    # cognome intero, mai «Zosaba Nd…»: dal #265 vale a ogni larghezza (tests/test_testo_intero_web.py), non solo qui
    assert "grid-template-columns: 1fr" in _regola(b, ".legenda-campo li")


def test_squadra_rose_e_calendario_non_si_tagliano():
    """Sotto Squadra: la riga della tua squadra e stemma/maglia vanno a capo; le sezioni di Mercato vanno su due righe invece di
    sovrapporsi; il calendario è una tabella (due dimensioni, ammessa da WCAG): scorre di lato dentro il suo riquadro, che si
    raggiunge anche con la tastiera, invece di restare tagliato dalla carta."""
    b = _blocco(STRETTA)
    assert "flex-wrap: wrap" in _regola(b, ".mia-riga")
    assert "grid-template-columns: 1fr" in _regola(b, ".immagini-squadra")
    assert "flex-wrap: wrap" in _regola(b, ".segmenti, .segmenti.scorri")
    app = (server.WEB / "app.js").read_text(encoding="utf-8")
    assert '<div class="scorri-tabella" role="region" tabindex="0" aria-label="${t("mercato.calendario_difficolta")}"><table class="tabella-cal">' in app
    assert re.search(r"\n\.scorri-tabella \{[^}]*overflow-x: auto", CSS)


def test_scheda_e_confronto_del_giocatore_in_colonna():
    """Il foglio che si apre toccando un giocatore (scheda, ⇄ confronto): a 160 px il volto grande accanto al nome spingeva il
    nome fuori e il foglio scorreva di lato."""
    b = _blocco(STRETTA)
    assert "grid-template-columns: 1fr" in _regola(b, ".intestazione-scheda")
    assert "grid-template-columns: 1fr" in _regola(b, ".duello")
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
    """Issue #286: a 390 px, nella carta con la maglia, «1 giorno 8» su una riga e «h» da sola sotto (a 320 px anche «1», «giorno» e
    «8 h» su tre righe). Il numero e la sua unità stanno insieme con uno spazio che non va a capo: si va a capo solo tra «1 giorno»
    e «8 h». Qui testoConto di app.js, eseguito con node e l'orologio fermo."""
    inizio, fine = "function parseData(s)", "// ETag e If-Match"
    codice = "\n".join([
        TESTI,
        "const FERMO = Date.parse('2026-10-26T09:35:00Z'), DataVera = Date;",
        "globalThis.Date = class extends DataVera { constructor(...a) { super(...(a.length ? a : [FERMO])); } static now() { return FERMO; } };",
        APP[APP.index(inizio):APP.index(fine)],
        APP[APP.index("function testoConto(o)"):APP.index("function vistaOggi()")],
        "const minuti = [32 * 60 + 5, 2 * 1440 + 14 * 60, 3 * 60 + 10, 45], fuori = {};",
        "for (const L of ['it', 'en']) { LINGUA = L; fuori[L] = minuti.map(m => testoConto({ giornata: 9, scadenza: new DataVera(FERMO + m * 60000).toISOString() }).grande); }",
        "console.log(JSON.stringify(fuori));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    fuori = json.loads(r.stdout.strip().splitlines()[-1])
    nb = " "
    assert fuori["it"] == [f"1{nb}giorno 8{nb}h", f"2{nb}giorni 14{nb}h", f"3{nb}h 10{nb}min", f"45{nb}min"]
    assert fuori["en"] == [f"1{nb}day 8{nb}h", f"2{nb}days 14{nb}h", f"3{nb}h 10{nb}min", f"45{nb}min"]


def test_la_maglia_lascia_posto_al_conto_alla_rovescia_sui_telefoni_stretti():
    """«14 giorni» non va mai a capo (#286): accanto alla maglia a 320 px veniva tagliato («20 h 22 mi…», #384). Con la grafica B la
    maglia ha la sua colonna e il numero si misura sulla colonna che resta (`cqi`), quindi non si taglia mai (lo controlla
    tests/test_grafica_b_web.py; misurato anche in Chrome da 320 a 1440 px, PR #415). Qui il prezzo: accanto alla maglia più larga
    che il CSS ammette (`max-width`, una divisa larga), dal telefono più stretto (320 px) al PC il conto resta più grande del titolo
    della schermata (32 px), così resta la cosa audace della pagina. Sotto i 260 px la maglia (solo decorazione) non si mostra."""
    k = float(re.search(r"font-size: min\(var\(--t-eroe\), (\d+(?:\.\d+)?)cqi\)", _regola(CSS, ".conto-testo .enorme")).group(1))
    maglia = _regola(CSS, ".maglia-hero")
    assert "height: 72px" in maglia
    larga = int(re.search(r"max-width: (\d+)px", maglia).group(1))
    spazio = int(re.search(r"column-gap: (\d+)px", _regola(CSS, ".conto-oggi")).group(1))
    # colonna del conto alle larghezze di main: telefono 320 e 390 px (16 px per lato), iPad 768 px (24 per lato, due colonne
    # uguali con 20 px in mezzo), PC 900 e 1024 px (32 per lato, colonne 5:7 con 20 px in mezzo)
    colonne = {320: 320 - 32, 390: 390 - 32, 768: (768 - 48 - 20) / 2, 900: (900 - 64 - 20) * 5 / 12, 1024: (1024 - 64 - 20) * 5 / 12}
    for pagina, colonna in colonne.items():
        assert k * (colonna - larga - spazio) / 100 > 32, pagina
    senza = _blocco("@container pagina (max-width: 259.98px) {")
    assert "display: none" in _regola(senza, ".maglia-hero")
    assert "grid-template-columns: minmax(0, 1fr)" in _regola(senza, ".conto-oggi.con-maglia")
    sotto_360 = _blocco("@container pagina (max-width: 359.98px) {")                       # la regola dei 132 px a destra non serve più
    assert ".maglia-hero" not in sotto_360 and ".conto-oggi" not in sotto_360               # (sotto i 360 px resta solo il Diario, PR 11)


def test_cambi_consigliati_in_colonna_sotto_i_320_px_e_nomi_mai_tagliati():
    """Issue #287: a 320 px con il testo «Grande» e «Molto grande» la carta del cambio restava su tre colonne: il nome tagliato
    («Ram…») e la colonna del testo larga ~80 px, una parola per riga. Sotto i 320 px utili volto e guadagno stanno sopra, nome e
    dettagli sotto a tutta larghezza, come le righe dei giocatori. A ogni larghezza il nome lungo va a capo invece dei puntini."""
    b = _blocco(STRETTA)
    assert "grid-template-columns: auto minmax(0, 1fr)" in _regola(b, ".proposta-r")
    testo = _regola(b, ".proposta-r > .pr-testo")
    assert "grid-row: 2" in testo and "grid-column: 1 / -1" in testo
    assert "grid-row: 1" in _regola(b, ".proposta-r > .pr-num")
    nome = " ".join(_corpi(".proposta-r button.nome-g"))
    assert "ellipsis" not in nome and "nowrap" not in nome and "overflow-wrap: break-word" in nome


def test_le_impostazioni_non_scorrono_di_lato():
    """Issue #288: Notifiche a 320 px con il testo «Molto grande» scorreva di lato (337 px contro 320): la griglia `.imp` aveva una
    colonna `auto`, larga quanto il contenuto più lungo (261 px su 240). Con `minmax(0, 1fr)` resta larga quanto la pagina."""
    assert "grid-template-columns: minmax(0, 1fr)" in _regola(CSS, ".imp")


def test_le_righe_delle_regole_vanno_a_capo_sotto_i_320_px():
    """Regole e Notifiche a 320 px con il testo «Molto grande»: accanto al −/+ o al menu il nome della regola restava largo ~60 px,
    una parola per riga. Sotto i 320 px utili il controllo va sotto il nome quando non c'è posto."""
    b = _blocco(STRETTA)
    assert "flex-wrap: wrap" in _regola(b, ".riga-regola")
    assert "max-width: 100%" in _regola(b, ".riga-regola > select.scelta-corta")
