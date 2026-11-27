"""Tablet e larghezze di mezzo (collaudo del 27/11/2026 a 768 e 1024 px e intorno ai 1200): le regole che si misurano nel browser.

- La lineetta colorata della squadra resta sulla riga della partita, anche nella panchina stretta accanto al pannello
  affiancato (da 1200 px con una scheda aperta la pagina si stringe).
- Nella riga sotto il nome il «·» fra due pezzi non resta in fondo a una riga e non ne comincia una.
- I grafici della scheda («Voto e fantavoto per giornata») e di Stato dei dati (affidabilità) si allargano con lo schermo senza
  ingrandire le scritte e senza crescere in altezza; i punti sui bordi restano interi.
- Giornate > Dettagli: nessun riquadro da solo con una colonna vuota accanto.
- Sul campo i nomi e le parole sotto il disco hanno sotto il fondo del campo: le linee non li attraversano.
- In inglese «expected 5.3» fra i sostituti sta su una riga.

L'aspetto si guarda nelle foto (skill `collaudo`); qui le misure che lo tengono fermo.
"""
import pytest

from test_formazione_unica import campo, principale, scheda, solo, sostituti_dal_server, tocca

LARGHEZZE = [390, 768, 1024, 1200, 1210, 1440]

# Le lineette che stanno su una riga da sole: il primo carattere di testo che le segue (lettori di schermo esclusi) non sta
# sulla stessa riga della lineetta.
LINEETTE_SOLE = """() => [...document.querySelectorAll('.dettaglio .lineetta')].filter(l => l.getClientRects().length).map(l => {
  const r = l.getBoundingClientRect(), d = l.closest('.dettaglio');
  const giro = document.createTreeWalker(d, NodeFilter.SHOW_TEXT);
  let n, primo = null;
  while ((n = giro.nextNode())) {
    if (!(l.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING) || n.parentElement.closest('.solo-lettori')) continue;
    if (n.textContent.trim()) { primo = n; break; }
  }
  if (!primo) return null;
  const k = primo.textContent.search(/\\S/), c = document.createRange();
  c.setStart(primo, k); c.setEnd(primo, k + 1);
  const t = c.getClientRects()[0];
  return t.top < r.bottom && t.bottom > r.top ? null : (d.closest('.voce-g')?.querySelector('.nome-t')?.innerText || '?');
}).filter(Boolean)"""

# Le righe della partita (sotto il nome) che cominciano o finiscono con un «·» che si vede: i caratteri dentro il riquadro della
# riga, raggruppati per riga.
PUNTINI_AI_BORDI = """() => { const fuori = [];
  for (const d of document.querySelectorAll('.voce-g .dettaglio')) {
    if (!d.getClientRects().length) continue;
    const box = d.getBoundingClientRect(), righe = {};
    const giro = document.createTreeWalker(d, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = giro.nextNode())) {
      if (n.parentElement.closest('.solo-lettori')) continue;
      for (let i = 0; i < n.textContent.length; i++) {
        if (!n.textContent[i].trim()) continue;
        const c = document.createRange(); c.setStart(n, i); c.setEnd(n, i + 1);
        const r = c.getClientRects()[0];
        if (!r || r.right <= box.left + 0.5 || r.left >= box.right - 0.5) continue;     // fuori dal riquadro: non si vede
        (righe[Math.round(r.top)] = righe[Math.round(r.top)] || []).push([r.left, n.textContent[i]]);
      }
    }
    for (const riga of Object.values(righe)) {
      const testo = riga.sort((a, b) => a[0] - b[0]).map(x => x[1]).join('');
      if (testo.startsWith('·') || testo.endsWith('·')) fuori.push(testo);
    }
  }
  return fuori; }"""

# Un grafico della scheda o del foglio: altezza, quanto è grande il suo testo sullo schermo (corpo del testo per la scala del
# disegno) rispetto alla legenda sotto, e i punti che escono dal riquadro.
MISURA_GRAFICO = """(scelta) => { const s = document.querySelector(scelta);
  if (!s || !s.getClientRects().length) return null;
  const r = s.getBoundingClientRect(), vb = s.viewBox.baseVal, scala = vb && vb.width ? r.width / vb.width : 1;
  const testo = s.querySelector('text'), legenda = s.nextElementSibling;
  const fuori = [...s.querySelectorAll('circle')].map(c => c.getBoundingClientRect())
    .filter(c => c.left < r.left - 0.5 || c.right > r.right + 0.5 || c.top < r.top - 0.5 || c.bottom > r.bottom + 0.5).length;
  return {larghezza: r.width, altezza: r.height, scala, fuori,
    scritta: testo ? parseFloat(getComputedStyle(testo).fontSize) * scala : null,
    legenda: legenda ? parseFloat(getComputedStyle(legenda).fontSize) : null}; }"""


def apri_scheda(web, larghezza: int) -> None:
    """La Formazione con la scheda del primo titolare aperta: un foglio fino a 1199 px, il pannello affiancato da 1200."""
    web.apri("/", larghezza=larghezza)
    tocca(web, campo(web).first)
    assert scheda(web).is_visible()


@pytest.mark.parametrize("larghezza", LARGHEZZE)
def test_la_lineetta_della_squadra_resta_sulla_riga_della_partita(web, larghezza):
    """A 1200-1215 px con la scheda nel pannello la panchina è stretta: «FRO vs PAR · domani 15:00» andava a capo intero e la
    lineetta restava da sola sulla riga sopra. E nessuna riga della partita comincia o finisce con «·»."""
    solo(web, "prima")
    apri_scheda(web, larghezza)
    assert web.pagina.locator("#panchina .lineetta").count() > 0, "la panchina non ha più le righe con la lineetta: rivedi il test"
    assert web.pagina.evaluate(LINEETTE_SOLE) == [], f"{larghezza} px: lineetta da sola su una riga"
    assert web.pagina.evaluate(PUNTINI_AI_BORDI) == [], f"{larghezza} px: «·» a inizio o fine riga"
    assert not web.errori_console


@pytest.mark.parametrize("larghezza", [390, 768, 1024, 1440])
def test_nella_rosa_il_puntino_non_resta_appeso_a_fine_riga(web, larghezza):
    """La mia squadra a 768 e 1024 px: «domani 15:00 ·» e a capo «costo 2 · quotazione 1». Il «·» va con il pezzo che segue e a
    inizio riga non si vede; la lineetta resta con la partita."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=squadra", larghezza=larghezza)
    righe = principale(web).locator(".voce-g .dettaglio")
    assert righe.count() > 10, "la rosa non ha le righe dei giocatori: rivedi il test"
    assert web.pagina.evaluate(PUNTINI_AI_BORDI) == [], f"{larghezza} px: «·» a inizio o fine riga"
    assert web.pagina.evaluate(LINEETTE_SOLE) == [], f"{larghezza} px: lineetta da sola su una riga"
    # i pezzi ci sono tutti, separati dal «·», come prima (lo legge anche chi usa un lettore di schermo)
    testo = " ".join(righe.first.inner_text().split())
    assert " · costo " in testo and " · quotazione " in testo, testo
    assert not web.errori_console


@pytest.mark.parametrize("larghezza", [390, 768, 1024, 1440])
def test_il_grafico_dei_voti_si_allarga_senza_ingrandire_le_scritte(web, larghezza):
    """«Tutti i numeri» > «Voto e fantavoto per giornata»: era disegnato per 320 px e stirato fino a 680, con le etichette grandi il
    doppio del testo intorno e 260 px di altezza. Ora prende la larghezza del foglio con le scritte grandi come la legenda."""
    solo(web, "prima")
    apri_scheda(web, larghezza)
    tocca(web, scheda(web).get_by_text("Tutti i numeri", exact=True))
    g = web.pagina.evaluate(MISURA_GRAFICO, "#foglio-contenuto svg.grafico")
    assert g, "nella scheda del primo titolare non c'è il grafico dei voti: rivedi il test"
    assert g["altezza"] <= 170, g
    assert g["scritta"] <= g["legenda"] * 1.1, g          # le etichette delle giornate come il testo piccolo intorno
    assert g["fuori"] == 0, g                              # i punti sui bordi interi
    largo = web.pagina.evaluate("() => document.querySelector('#foglio-contenuto').getBoundingClientRect().width")
    assert g["larghezza"] >= largo - 2, (g, largo)          # si allarga con il foglio
    assert not web.errori_console


@pytest.mark.parametrize("larghezza", [390, 768, 1024, 1440])
def test_il_grafico_di_stato_dei_dati_non_cresce_in_altezza(web, larghezza):
    """Gestione > Stato dei dati, «Quanto è affidabile il modello»: il grafico disegnato per 300 px arrivava a 250 px di altezza
    a 768 px, con le linee spesse il doppio."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=gestione", larghezza=larghezza)
    tocca(web, web.pagina.locator("#apri-stato-dati"))
    g = web.pagina.evaluate(MISURA_GRAFICO, "#affidabilita svg")
    assert g, "Stato dei dati non ha il grafico dell'affidabilità: rivedi il test"
    assert g["altezza"] <= 170, g
    assert abs(g["scala"] - 1) < 0.02, g                    # disegnato alla sua larghezza: le linee restano di 2 px
    assert not web.errori_console


@pytest.mark.parametrize("larghezza", [390, 600, 768, 1024, 1440])
def test_nei_dettagli_delle_giornate_nessun_riquadro_resta_da_solo(web, larghezza):
    """Giornate > Dettagli a 768 e 1024 px: il terzo riquadro stava da solo a sinistra, con una colonna vuota accanto. Ogni
    riquadro ha un vicino sulla sua riga oppure prende tutta la larghezza."""
    solo(web, "prima")
    web.apri("/?vista=giornate", larghezza=larghezza)
    tocca(web, principale(web).locator(".gn-dettagli > summary"))
    riquadri = web.pagina.evaluate("""() => { const g = document.querySelector('.qp-griglia'), l = g.getBoundingClientRect();
      return {larga: l.width, voci: [...g.children].map(v => { const r = v.getBoundingClientRect(); return [Math.round(r.top), r.width]; })}; }""")
    assert len(riquadri["voci"]) >= 3, riquadri
    righe = {}
    for alto, largo in riquadri["voci"]:
        righe.setdefault(alto, []).append(largo)
    soli = [larghi for larghi in righe.values() if len(larghi) == 1 and larghi[0] < riquadri["larga"] - 2]
    assert not soli, f"{larghezza} px: un riquadro da solo con una colonna vuota accanto: {riquadri}"


@pytest.mark.parametrize("tema", ["chiaro", "scuro"])
def test_sul_campo_i_nomi_hanno_sotto_il_fondo_del_campo(web, tema):
    """A 768 px «Zosaba Ndorti» passava sopra la linea laterale e a giornata in corso il cerchio di centrocampo attraversava
    «Roghecebe». Il nome e le parole sotto il disco hanno sotto il colore del campo, che copre la linea."""
    web.apri("/", larghezza=768, tema=tema)
    sotto = web.pagina.evaluate("""() => { const fondo = getComputedStyle(document.querySelector('#campo-formazione')).backgroundColor;
      return [...document.querySelectorAll('#campo-formazione .pedina .nome, #campo-formazione .pedina .gioca.parola')]
        .map(e => [e.innerText, getComputedStyle(e).backgroundColor, fondo]); }""")
    assert len(sotto) >= 11, sotto
    diversi = [(testo, colore) for testo, colore, fondo in sotto if colore != fondo]
    assert not diversi, f"{web.fase}: senza il fondo del campo sotto: {diversi}"


@pytest.mark.parametrize("larghezza", [390, 768, 1024])
def test_in_inglese_expected_sta_su_una_riga_fra_i_sostituti(web, larghezza):
    """«Sostituisci» in inglese («Instead of …»): «expected 5.3» andava su due righe anche a 1024 px."""
    solo(web, "prima")
    web.memoria({"lingua": "en"})
    sostituti_dal_server(web)
    apri_scheda(web, larghezza)
    tocca(web, scheda(web).get_by_role("button", name="Replace"))
    righe = web.pagina.evaluate("""() => [...document.querySelectorAll('#foglio-contenuto [data-sostituzione] .pv-g')].map(p => {
      const c = document.createRange(); c.selectNodeContents(p);
      return [p.innerText, new Set([...c.getClientRects()].map(r => Math.round(r.top))).size]; })""")
    assert righe and all(testo.startswith("expected ") for testo, _ in righe), righe
    assert all(n == 1 for _, n in righe), f"{larghezza} px: {righe}"
    assert not web.errori_console
