"""Pagina strettissima (issue #235, WCAG 2.2 1.4.10 «Reflow»): con lo zoom del browser al 200% un telefono vede 160-195 px.
Prima testata, barra, righe dei giocatori, partite e campo restavano disposti come a 390 px: il titolo spariva, la barra
tagliava «Altro», i nomi andavano a capo una lettera per riga e le sigle delle partite uscivano dalla carta.
Ora sotto i 320 px di larghezza utile la pagina si dispone in una colonna. La misura è il body come contenitore (`pagina`),
non @media: così conta anche il testo «Molto grande» dell'app, che ingrandisce la pagina con `zoom` e le @media non lo vedono.
La prova vera è nel browser (larghezze 160, 195 e 320 px); qui si controlla che le regole ci siano."""
import re

from fanta import server

CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
STRETTA = "@container pagina (max-width: 319.98px) {"


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


def test_testata_su_due_righe_che_scorre_via_e_barra_con_le_sole_icone():
    b = _blocco(STRETTA)
    testata = _regola(b, ".testata")
    assert "flex-wrap: wrap" in testata and "position: relative" in testata        # con lo zoom una testata fissa copriva un quarto dello schermo
    assert "white-space: normal" in _regola(b, ".testo-testata .titolo, .testo-testata .sottotitolo, .sottotitolo > span")
    etichette = _regola(b, ".schede button > span")                                 # il nome della scheda resta ai lettori di schermo
    assert "clip: rect(0 0 0 0)" in etichette and "width: 1px" in etichette and "display: none" not in etichette


def test_righe_dei_giocatori_impilate_e_partite_su_due_righe():
    b = _blocco(STRETTA)
    assert "grid-column: 1 / -1" in _regola(b, ".voce:has(> .avatar-anello) > :nth-child(2)")           # nome, partita e etichette a tutta larghezza
    assert "padding-right: 0" in _regola(b, ".elenco li.con-confronto .voce")                          # niente colonna vuota per ⇄
    assert "top:" in _regola(b, ".elenco li.con-confronto .confronta-mini")
    assert "grid-column: 1 / 3" in _regola(b, ".partita .ora")                                          # ora sopra, squadre sotto
    assert "grid-row: 2" in _regola(b, ".partita .sq.casa")
    assert "flex-wrap: wrap" in _regola(b, ".riga")
    # Oggi a giornata in corso: il fantavoto preso o lo stato («In dubbio · gioca 40%») va sotto il nome, non fuori dalla carta
    assert "grid-row: 2" in _regola(b, ".avviso-riga > :nth-child(3):not(.pallino-stato)")


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
