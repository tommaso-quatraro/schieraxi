"""Altro come distinta (grafica B, PR 11; spec §9 «Squadra e Altro», §4, §8, §11): Scambi, Diario, Regole, Movimenti, Crediti,
Nuova stagione e Novità. Controlli su app.js e stile.css e prove con node del codice vero di app.js (foto e axe nella pull request).
Comportamento invariato: «Ho schierato la consigliata» e «Correggi a mano» del Diario fanno quello di prima (test_diario_stagione_web)."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server
import codice_web

APP = codice_web.app()
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _funzione(nome: str) -> str:
    i = re.search(rf"\n(?:async )?function {nome}\(", APP).start()
    return APP[i:APP.index("\n}\n", i) + 3]


def _regole(selettore: str) -> list[str]:
    """I corpi di tutte le regole (anche dentro @media e @container) il cui elenco di selettori contiene proprio `selettore`."""
    corpi = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        selettori = [s.strip() for s in re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S).split(",")]
        if selettore in selettori:
            corpi.append(m.group(2))
    return corpi


def _blocco(intestazione: str) -> str:
    """Tutti i blocchi CSS che iniziano con `intestazione` (per esempio «@media (min-width: 1100px) {»), uniti."""
    pezzi, da = [], 0
    while (i := CSS.find("\n" + intestazione, da)) != -1:
        livello, j = 0, i
        for j in range(CSS.index("{", i), len(CSS)):
            livello += {"{": 1, "}": -1}.get(CSS[j], 0)
            if livello == 0:
                break
        pezzi.append(CSS[i:j])
        da = j
    return "\n".join(pezzi)


def _senza_fondo(selettore: str) -> None:
    for corpo in _regole(selettore):
        for nome, valore in re.findall(r"(background(?:-color)?)\s*:\s*([^;]+)", corpo):
            assert valore.strip() in ("none", "transparent"), f"{selettore} {{ {nome}: {valore} }}"


def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- compito 11.1 del piano

def test_numeri_di_altro_nel_carattere_dei_numeri_e_regole_da_44_px():
    for selettore in (r"\.qp-num", r"\.tg-numero"):                       # Diario, i punti in testa alla Formazione
        assert re.search(selettore + r" \{[^}]*font-family: var\(--font-numeri\)", CSS), selettore
    assert re.search(r"\.stepper button \{ width: 44px", CSS)              # i «−/+» delle regole restano da 44 px
    assert not re.search(r"\.riga-regola\.evidenzia \{[^}]*color-mix\(in srgb, var\(--verde\)", CSS)   # evidenziata con --superficie, non tinta


# ---------------------------------------------------------------- Diario: righe per giornata, numeri in colonna

def _diario(diario: dict) -> dict[str, str]:
    from tests.test_diario_stagione_web import _carte, _esegui
    return _carte(_esegui(diario, "await apriDiario(); risultato = stato();")["html"])


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_diario_le_due_azioni_in_una_riga_e_un_solo_pulsante_pieno():
    """Spec §4.5 e §8.7: un solo pulsante pieno per schermata. Nel Diario «Ho schierato la consigliata» è pieno solo nella giornata
    più recente da salvare; nelle altre è un pulsante con il bordo. Accanto, nella stessa riga, «Ho schierato un'altra formazione»
    (prima stavano in due righe una sotto l'altra). Parole e comportamento uguali (decisione dell'utente)."""
    from tests.test_diario_stagione_web import ORA, PRIMA, _voce
    carte = _diario({"giornate": [_voce(ORA, 10), _voce(ORA, 9), _voce(PRIMA, 10, schierata_da=21, modificabile=False)]})
    riga = r'<div class="pulsanti azioni-diario"><button class="{classe}" data-schierata="[^"]+">Ho schierato la consigliata</button>' \
           r'<button class="bottone secondario" data-correggi="[^"]+">Ho schierato un\'altra formazione</button></div>'
    assert re.search(riga.format(classe="bottone"), carte[f"{ORA} 7"]), carte[f"{ORA} 7"]
    assert re.search(riga.format(classe="bottone secondario"), carte[f"{ORA} 6"]), carte[f"{ORA} 6"]
    assert sum(c.count('class="bottone"') for c in carte.values()) == 1
    assert "data-schierata" not in carte[f"{PRIMA} 10"] and "data-correggi" not in carte[f"{PRIMA} 10"]


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_diario_correggi_a_mano_resta_nella_sua_riga_quando_la_formazione_c_e():
    from tests.test_diario_stagione_web import ORA, _voce
    carta = _diario({"giornate": [_voce(ORA, 10, schierata_da=1)]})[f"{ORA} 7"]
    assert re.search(r'<div class="pulsanti azioni-diario"><button class="bottone secondario" data-correggi="[^"]+">Correggi a mano</button></div>', carta)
    assert "data-schierata" not in carta


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_diario_punti_fatti_e_attesi_in_due_colonne():
    """«numeri in colonna» (spec §9): il fantavoto fatto e «attesi N» stanno in due celle loro, della stessa larghezza in ogni riga e in
    ogni giornata, con le cifre del carattere dei numeri; come sull'iPhone il numero fatto sopra e «attesi» accanto (a destra)."""
    from tests.test_diario_stagione_web import ORA, _voce
    carta = _diario({"giornate": [_voce(ORA, 10, schierata_da=1)]})[f"{ORA} 7"]
    assert '<div class="diario-punti"><span>La tua (4-4-2)</span><b class="dp-fatti">66,0</b><span class="dp-attesi">attesi 67,5</span></div>' in carta
    assert '<b class="dp-fatti">70,5</b><span class="dp-attesi">attesi 68,0</span>' in carta
    griglia = "".join(_regole(".diario-punti"))
    # «attesi 100,0» / «expected 100.0» a 12 px stanno in 6,5em della riga (97 px): più stretta di prima (7,5em), il nome ha più posto
    assert "display: grid" in griglia and "grid-template-columns: minmax(0, 1fr) 4.2em 6.5em" in griglia
    assert "font-family: var(--font-numeri)" in "".join(_regole(".dp-fatti")) and "text-align: right" in "".join(_regole(".dp-fatti"))
    # sotto i 360 px di pagina (revisione della #434: tra 320 e 360 px al nome restavano ~77 px, «La tua, la consigliata (4-3-3)» su 3-4
    # righe) il nome della formazione sta sopra e i due numeri sotto, a destra
    sotto_360 = _blocco("@container pagina (max-width: 359.98px) {")
    assert re.search(r"\.diario-punti \{ grid-template-columns: minmax\(0, 1fr\) auto;", sotto_360)
    assert re.search(r"\.diario-punti > span:first-child \{ grid-column: 1 / -1; \}", sotto_360)
    assert ".diario-punti" not in _blocco("@container pagina (max-width: 319.98px) {")      # una regola sola, non due soglie


def test_diario_giocatori_cambiati_senza_fondo_e_formazione_sola_su_due_colonne():
    _senza_fondo(".diario-lista li.diario-diverso")
    corpo = "".join(_regole(".diario-lista li.diario-diverso"))
    assert "font-weight: 700" in corpo and "border-left-color: var(--arancio)" in corpo     # non solo il colore: grassetto e filo
    assert re.search(r"@media \(min-width: 560px\) \{[^@]*\.diario-conf\.una \.diario-lista \{ columns: 2", CSS)


def test_quanto_ci_abbiamo_preso_con_le_tendine_piccole():
    corpo = "".join(_regole(".qp-dettagli > summary"))
    assert "font-size: var(--t-sec)" in corpo                              # «Tutte le fasce» non è un titolo di sezione (era 17 px)
    assert "border-top: 1px solid var(--filo)" in "".join(_regole(".qp-voce"))


# ---------------------------------------------------------------- ruolo: lettera grigia, niente quadratino colorato (spec §8.4, §11)

@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_ruolo_come_lettera_grigia_negli_scambi_nel_diario_e_nella_ricerca():
    riga = re.search(r"^const badgeRuolo = .*$", APP, re.M).group(0)
    codice = "\n".join([
        re.search(r"^const NOMI_RUOLO = .*$", APP, re.M).group(0).replace("t(", "((k) => k)("),
        "const LINGUA = 'it'; const t = k => k;",
        APP[APP.index("function esc(x)"):APP.index("const perc =")],
        re.search(r"^const ruoloSigla = .*$", APP, re.M).group(0), riga,
        "console.log(JSON.stringify([badgeRuolo('D', true), badgeRuolo('A')]))"])
    piccolo, grande = _node(codice)
    for html in (piccolo, grande):
        assert 'class="ruolo-l' in html and 'class="ruolo ' not in html and "style=" not in html, html
    assert ">D<" in piccolo and ">A<" in grande
    assert not re.search(r"\.ruolo\.[PDCA] \{", CSS)                        # i quadratini colorati non servono più


# ---------------------------------------------------------------- Scambi

def test_le_fasce_non_escono_dalla_pagina_strettissima():
    """Zoom al 200% su un telefono da 390 px (195 px): le fasce del modificatore uscivano di 2 px. Sotto i 320 px vanno a capo."""
    stretta = _blocco("@container pagina (max-width: 319.98px) {")
    assert re.search(r"\.fascia \.coppia \{[^}]*flex-wrap: wrap", stretta)


# ---------------------------------------------------------------- Regole: righe con «−/+» a destra, due colonne sul PC

def test_regole_su_due_colonne_dal_1100_px_e_righe_mai_troppo_larghe():
    """Sul PC a sinistra nome della lega e «Importa da Leghe», a destra le sezioni con i «−/+»: si vede l'anteprima del testo
    riconosciuto accanto ai valori che cambia. Sotto i 1100 px una colonna, larga al massimo 720 px (il «−/+» resta vicino al nome)."""
    corpo = _funzione("vistaRegole")
    assert '<div class="regole-testa">' in corpo and '<div class="regole-sezioni">' in corpo
    testa, sezioni = corpo.index('<div class="regole-testa">'), corpo.index('<div class="regole-sezioni">')
    assert '<div class="regole-colonne">' in corpo and testa < corpo.index('id="riconosci-regole"') < sezioni
    dettagli = [m.start() for m in re.finditer(r'<details class="carta regola-sez"', corpo)]
    assert len(dettagli) == 7 and min(dettagli) > sezioni
    assert sezioni < corpo.index('<div class="salva-fisso" hidden>')          # «Salva» galleggia sopra la colonna delle regole
    assert "max-width: 720px" in "".join(_regole(".regole-colonne"))
    largo = _blocco("@media (min-width: 1100px) {")
    assert re.search(r"\.regole-colonne \{ display: grid; grid-template-columns: minmax\(0, 5fr\) minmax\(0, 7fr\);[^}]*max-width: none", largo)


def test_regole_righe_con_il_filo_e_prova_senza_riquadro():
    righe = "".join(_regole(".riga-regola"))
    assert "border-top: 1px solid var(--filo)" in righe and "border-radius" not in righe
    for selettore in (".prova-difesa",):
        for corpo in _regole(selettore):
            assert not re.search(r"(?<![-\w])(background|border|border-radius):\s*(?!none|0)", corpo), corpo
    assert "font-family: var(--font-numeri)" in "".join(_regole(".stepper input"))
    evidenzia = "".join(_regole(".riga-regola.evidenzia"))
    assert "var(--superficie)" in evidenzia and "var(--azione)" in evidenzia     # fondo e linea a sinistra, come la voce aperta del menu
    assert "box-shadow" not in "".join(_regole(".salva-fisso .bottone"))       # niente ombra (spec §7.5): pieno, come il messaggio che passa


def test_segni_visibili_anche_con_il_contrasto_elevato():
    """Contrasto elevato di Windows: il browser toglie fondi e ombre. I moduli scelti nelle Regole e la regola appena
    cambiata dall'importazione prendono un contorno vero."""
    forzati = _blocco("@media (forced-colors: active) {")
    for selettore in ("#moduli .chip.attiva", ".riga-regola.evidenzia"):
        assert re.search(re.escape(selettore) + r"[^{]*\{[^}]*outline: 2px solid Highlight", forzati), selettore


# ---------------------------------------------------------------- Movimenti, Crediti, Novità

def test_movimenti_con_il_segno_colorato_senza_quadratino():
    for selettore in (".icona-mov", ".icona-mov.su", ".icona-mov.giu", ".movimento.ok .icona-mov"):
        _senza_fondo(selettore)
    assert "border-top: 1px solid var(--filo)" in "".join(_regole(".movimento + .movimento"))
