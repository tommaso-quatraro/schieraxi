"""Grafica B della web (spec docs/superpowers/specs/2026-11-05-grafica-web-b-design.md): controlli sul codice."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server, testi_legali

WEB = server.WEB
RADICE = WEB.parent.parent
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
APP = (WEB / "app.js").read_text(encoding="utf-8")
IMP = (WEB / "impostazioni.js").read_text(encoding="utf-8")
SW = (WEB / "sw.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _funzione(testo, nome):
    """Il corpo di una funzione di primo livello («function nome(» o «async function nome(») fino alla graffa che la chiude."""
    i = re.search(rf"\n(?:async )?function {nome}\(", testo).start()
    return testo[i:testo.index("\n}\n", i)]


# ---------------------------------------------------------------- 4.1 testata unica e schede come collegamenti

def test_una_sola_nav_nella_testata_con_le_schede_come_collegamenti():
    assert HTML.count("<nav") == 1 and HTML.index("<nav") < HTML.index("</header>")
    for v in ("oggi", "formazione", "squadra", "altro"):
        assert f'<a class="scheda" data-vista="{v}" href="/?vista={v}"' in HTML


def test_testata_senza_h1_e_nome_disegnato_uguale_al_sito():
    testata = HTML[HTML.index("<header"):HTML.index("</header>")]
    assert "<h1" not in testata
    simbolo = lambda t: re.search(r'<symbol id="wm-c".*?</symbol>', t, re.S).group(0)
    assert simbolo(HTML) == simbolo((RADICE / "sito" / "index.html").read_text(encoding="utf-8"))
    assert '<a class="marchio" href="/?vista=oggi"' in testata and '<use href="#wm-c"/>' in testata


def test_ricerca_sempre_aperta_sul_pc_e_che_funziona_subito():
    assert re.search(r'<input type="search" id="campo-cerca"[^>]*data-t-aria="shell.cerca"', HTML)
    assert '<kbd aria-hidden="true">/</kbd>' in HTML
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*#bottone-cerca \{ display: none; \}", CSS)
    assert re.search(r'function apriRicerca\(testo = ""\)', APP)
    assert re.search(r'\$\("#campo-cerca"\)\.addEventListener\("(?:input|keydown)"', APP)


def test_pagina_larga_al_massimo_1240_px_senza_griglia_di_carte():
    assert re.search(r"\nmain \{[^}]*max-width: 1240px", CSS)
    assert not re.search(r"main \{[^}]*grid-template-columns: repeat\(", CSS)


def test_indietro_del_browser_torna_alla_schermata_di_prima():
    corpo = _funzione(APP, "vai")
    assert "history.pushState" in corpo and "daCronologia" in corpo
    assert 'addEventListener("popstate"' in APP


def test_niente_pillola_verticale_ne_lente_sul_pc():
    assert "translateY(-50%)" not in CSS and ".lente" not in CSS and "--lato" not in CSS
    assert 'class="lente"' not in HTML


def test_le_colonne_ferme_stanno_sotto_la_testata_ferma():
    """Da 900 px la testata resta ferma in alto: le colonne ferme (Oggi, campo, Impostazioni, filtri) partono sotto di lei
    (`--alto-ferma`); sotto i 900 px la testata scorre via e le colonne stanno a un filo dal bordo."""
    assert re.search(r"\n:root \{[^}]*--alto-ferma: 0px", CSS)
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*--alto-ferma: var\(--alto-testata, 56px\)", CSS)
    assert "top: 76px" not in CSS
    assert CSS.count("top: calc(var(--alto-ferma) + 16px)") >= 4


@pytest.mark.skipif(not NODE, reason="serve node")
def test_clic_su_una_scheda_ctrl_cmd_maiusc_e_clic_centrale_li_decide_il_browser():
    """Clic normale: l'app cambia schermata da sola. Ctrl, ⌘, Maiusc, Alt o un tasto diverso dal sinistro: il browser apre il
    collegamento dove vuole chi clicca (altra scheda, altra finestra), così si confrontano due schermate."""
    corpo = re.search(r"\nconst clicSemplice = [^\n]*\n", APP).group(0)
    codice = corpo + """
    const casi = [{ button: 0 }, { button: 0, ctrlKey: true }, { button: 0, metaKey: true }, { button: 0, shiftKey: true },
                  { button: 0, altKey: true }, { button: 1 }];
    console.log(JSON.stringify(casi.map(clicSemplice)));
    """
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [True, False, False, False, False, False]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_indirizzo_di_ogni_schermata():
    """L'indirizzo che va nella cronologia: le schede, le pagine di Squadra con la loro sezione, le Impostazioni con il gruppo.
    Sono gli stessi indirizzi che l'app sa già aprire all'avvio (`?vista=`, `&scheda=`, `&gruppo=`)."""
    corpo = re.search(r"\nconst indirizzoVista = [^\n]*\n", APP).group(0)
    codice = corpo + """
    console.log(JSON.stringify([indirizzoVista("oggi"), indirizzoVista("formazione"), indirizzoVista("mercato", null, "osservati"),
      indirizzoVista("impostazioni", "avvisi"), indirizzoVista("impostazioni"), indirizzoVista("scambi", "x", "y")]));
    """
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["/?vista=oggi", "/?vista=formazione", "/?vista=mercato&scheda=osservati",
                                    "/?vista=impostazioni&gruppo=avvisi", "/?vista=impostazioni", "/?vista=scambi"]


@pytest.mark.skipif(not NODE, reason="serve node")
def test_un_indirizzo_strano_porta_a_oggi():
    """`?vista=` arriva dall'indirizzo (anche con Indietro): un nome che non è una schermata non deve trovare niente, nemmeno
    le proprietà di ogni oggetto JavaScript («__proto__», «constructor»), che prima rompevano la pagina."""
    pezzo = APP[APP.index("const VISTE = "):APP.index("const SCHEDA_DI = ")]
    riga = re.search(r"\nconst SCHEDA_DI = [^\n]*\n", APP).group(0)
    codice = pezzo + riga + """
    console.log(JSON.stringify(["oggi", "mercato", "scambi", "lega", "__proto__", "constructor", "toString", "x", null].map(SCHEDA_DI)));
    """
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["oggi", "squadra", "altro", "altro", None, None, None, None, None]


def test_indietro_con_la_formazione_non_salvata_resta_nella_formazione():
    """Spec §15.6: Indietro chiede come un clic su una scheda; se si resta, l'indirizzo torna quello della Formazione.
    Indietro chiude anche il foglio aperto, come un cambio di scheda; il foglio non scrive nella cronologia."""
    corpo = _funzione(APP, "vai")
    resta = corpo[:corpo.index("return;")]
    assert "lasciaFormazione()" in resta and "opz.daCronologia" in resta and 'indirizzoVista("formazione")' in resta
    gestore = APP[APP.index('addEventListener("popstate"'):][:800]
    assert "chiudiFoglio()" in gestore and "daCronologia: true" in gestore
    assert "history.pushState" not in _funzione(APP, "apriFoglio")


def test_la_ricerca_dalla_testata_non_perde_le_lettere():
    """Il campo della testata passa il testo alla ricerca e il campo della ricerca prende subito il focus: con un'attesa le
    lettere scritte nel frattempo andavano perse (il resto della pagina è bloccato mentre il foglio è aperto)."""
    corpo = _funzione(APP, "apriRicerca")
    assert "campo.value = testo" in corpo and "campo.focus(" in corpo
    assert "setTimeout(() => campo.focus()" not in corpo
    blocca = _funzione(APP, "bloccaSfondo")
    assert "contains(document.activeElement)" in blocca            # il focus già dentro il foglio non va spostato sulla ✕


# ---------------------------------------------------------------- 4.2 titolo della schermata e riga di stato

def test_ogni_schermata_ha_il_suo_titolo_h1_e_la_riga_di_stato():
    corpo = _funzione(APP, "pagina")
    assert 'class="capo-pagina"' in corpo and '<h1 id="titolo-pagina"' in corpo and 'class="stato-pagina"' in corpo
    assert 't("nav." + ' in corpo and "opz.titolo" in corpo
    assert "nomeGiornata(i.prossima_giornata_lega, i.prossima_giornata)" in _funzione(APP, "caricaInfo")   # giornata della lega (#306)
    for nome in ("vistaNovita", "vistaRosa"):                  # pagine dentro Altro e Squadra: il loro titolo, non quello della scheda
        assert "titolo:" in _funzione(APP, nome), nome


def test_pagina_e_l_unico_punto_che_scrive_le_schermate():
    """Spec §10: Mercato, Scambi, Regole, il caricamento e il componente a pannelli (Squadra, Altro, Impostazioni) passano da
    `pagina()`, così ogni schermata ha il titolo in cima. Impostazioni ha il suo titolo e niente riga di stato."""
    for nome in ("vistaMercato", "vistaScambi", "vistaRegole", "caricamento"):
        corpo = _funzione(APP, nome)
        assert "pagina(" in corpo and "contenuto.innerHTML =" not in corpo, nome
    assert "pagina(" in _funzione(IMP, "montaPannelli") and "contenuto.innerHTML" not in _funzione(IMP, "montaPannelli")
    assert 'titolo: t("shell.impostazioni"), stato: false' in IMP
    assert "opz.stato === false" in _funzione(APP, "pagina")


def test_titolo_e_riga_di_stato_dai_dati_scritti_senza_html():
    """Il nome della squadra arriva dall'utente: titolo e riga di stato passano da `esc` (niente HTML dall'utente)."""
    corpo = _funzione(APP, "pagina")
    assert "esc(titolo)" in corpo
    riga = _funzione(APP, "rigaStato")
    assert "esc(" in riga and "stato.rigaStato" in riga and 'class="stemma-stato"' in riga
    info = _funzione(APP, "caricaInfo")
    assert "stato.rigaStato" in info and "aggiornaRigaStato()" in info
    assert "aggiornaRigaStato()" in _funzione(APP, "caricaSquadre")         # lo stemma arriva dopo: la riga si riscrive


def test_il_banner_della_nuova_stagione_va_sotto_il_titolo():
    corpo = _funzione(APP, "bannerNuovaStagione")
    assert '$(".capo-pagina", contenuto)' in corpo and ".after(c)" in corpo


@pytest.mark.skipif(not NODE, reason="serve node")
def test_riga_di_stato_giornata_squadra_e_dati():
    """«Giornata 11 · Real Esempio · dati del 26 ott 23:55», con lo stemma da 20 px se c'è; senza server: «Server non raggiungibile»."""
    corpo = _funzione(APP, "rigaStato")
    codice = "\n".join([
        "const t = k => k === 'testata.offline' ? 'Server non raggiungibile' : k;",
        "const esc = x => String(x ?? '').replace(/[&<>\"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', \"'\": '&#39;' }[c]));",
        "const urlImg = (nome, tipo) => `/img?${nome}&${tipo}`;",
        "let mia = null; const miaSquadra = () => mia; const stato = {};",
        corpo,
        "}",
        "const esiti = [];",
        "stato.rigaStato = { giornata: 'Giornata 11', squadra: 'Real <b>Esempio</b>', dati: 'dati del 26 ott 23:55' }; esiti.push(rigaStato());",
        "mia = { nome: 'Real', immagini: { stemma: true } }; esiti.push(rigaStato());",
        "stato.rigaStato = { offline: true }; mia = null; esiti.push(rigaStato());",
        "stato.rigaStato = null; esiti.push(rigaStato());",
        "console.log(JSON.stringify(esiti));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    senza, con, offline, vuota = json.loads(r.stdout)
    testo = lambda h: re.sub(r"<[^>]+>", "", h)
    assert testo(senza) == "Giornata 11 · Real &lt;b&gt;Esempio&lt;/b&gt; · dati del 26 ott 23:55"
    assert "<b>" not in senza and "<img" not in senza
    assert con.startswith('<img class="stemma-stato" src="/img?Real&amp;stemma" alt="" width="20" height="20">')
    assert testo(offline) == "Server non raggiungibile" and vuota == ""


# ---------------------------------------------------------------- 4.3 carattere dei numeri e dei titoli, scala nuova

def test_numeri_e_titoli_in_archivo_dal_nostro_server_con_ripiego():
    assert re.search(r'@font-face \{[^}]*font-family: "Archivo";[^}]*src: url\("caratteri/archivo\.woff2"\) format\("woff2"\);[^}]*font-display: swap;', CSS)
    assert re.search(r'--font-numeri: "Archivo", [^;]*system-ui', CSS)
    assert '<link rel="preload" href="caratteri/archivo.woff2" as="font" type="font/woff2" crossorigin>' in HTML
    assert re.search(r"#titolo-pagina \{[^}]*font-family: var\(--font-numeri\)", CSS)


def test_scala_della_grafica_b():
    for valore in ("--t-eroe: 56px", "--t-titolo: 32px", "--t-card: 17px", "--t-valore: 20px", "--t-corpo: 15px",
                   "--t-sec: 13px", "--t-eti: 12px"):
        assert valore in CSS, valore
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*--t-eroe: 72px", CSS)


def test_numeri_grandi_e_valori_in_archivo_con_le_cifre_in_colonna():
    for selettore in (".grande", ".enorme", ".voce .valore b", ".partita .pt"):
        corpo = re.search(r"\n" + re.escape(selettore) + r" \{([^}]*)\}", CSS)
        assert corpo and "font-family: var(--font-numeri)" in corpo.group(1), selettore
        assert "font-variant-numeric: tabular-nums" in corpo.group(1), selettore          # cifre in colonna anche con il ripiego


# ---------------------------------------------------------------- colori nuovi anche fuori dall'app (dalla revisione della PR 3)

def test_pagine_legali_e_pagina_senza_rete_con_i_colori_nuovi():
    for quale in ("privacy", "termini"):
        pagina = testi_legali.pagina(quale)
        assert '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff">' in pagina, quale
        assert '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#121513">' in pagina, quale
        assert "#07100b" not in pagina, quale
    senza_rete = re.search(r"const PAGINA_SENZA_RETE = `(.*?)`;", SW, re.S).group(1)
    for vecchio in ("#07100b", "#eaf3ee", "#b9c9c0"):
        assert vecchio not in senza_rete, vecchio
    assert "background:#121513;color:#e9edea" in senza_rete
    assert "color:#bccdc2" in senza_rete                                    # il grigio dei testi secondari (--testo-2 scuro)
    assert "background:#3ddc97;color:#04301c" in senza_rete                 # il pulsante come --azione / --azione-testo


def test_differenza_ammessa_del_colore_delle_azioni_scritta():
    doc = (RADICE / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    ammesse = doc[doc.index("## Differenze ammesse"):doc.index("## Differenze di oggi")]
    riga = next((r for r in ammesse.splitlines() if "Colore delle azioni" in r), "")
    assert "#0B6B3A" in riga and "#526600" in riga, riga


def test_guida_indietro_del_browser():
    guida = (RADICE / "docs" / "GUIDA-UTENTE.md").read_text(encoding="utf-8")
    assert "Indietro del browser torna alla schermata di prima" in guida


def _voce_di_novita(file, titolo):
    """La voce delle novità di una PR: prima del rilascio sta in `fanta/novita.d/<file>`, dopo il job `rilascia` la sposta in
    `fanta/novita.json` (con il numero di versione) e toglie il file. Il test deve passare in tutti e due i momenti: leggendo solo il
    file, `main` diventava rosso appena la PR era rilasciata (successo con la PR 4, versione 1.419)."""
    percorso = RADICE / "fanta" / "novita.d" / file
    if percorso.exists():
        voce = json.loads(percorso.read_text(encoding="utf-8"))
        assert voce["titolo"] == titolo, voce["titolo"]
        return voce
    rilasciate = json.loads((RADICE / "fanta" / "novita.json").read_text(encoding="utf-8"))
    voce = next((v for v in rilasciate if v.get("titolo") == titolo), None)
    assert voce, f"manca la novità «{titolo}» sia in novita.d sia in novita.json"
    return voce


def test_novita_della_testata():
    voce = _voce_di_novita("testata-schede.json", "Nuova testata: schede in alto sugli schermi larghi e titolo in ogni schermata")
    assert len(voce["voci"]) >= 2


# ---------------------------------------------------------------- PR 5: sezioni, pulsanti, etichette, avvisi
SENZA_COMMENTI = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
# (selettori, corpo) di ogni regola di stile.css, anche dentro le @media
REGOLE = [([s.strip() for s in sel.split(",")], corpo) for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", SENZA_COMMENTI)]
JS_WEB = "\n".join(p.read_text(encoding="utf-8") for p in sorted(WEB.glob("*.js"))) + HTML
# le classi che stanno insieme a «carta» sugli stessi elementi («carta hero», «imp-elenco carta», «carta vuoto»...); di un
# attributo scritto con `${…}` si legge la parte fissa
CON_LA_CARTA = sorted({c for attr in re.findall(r'class="([^"]*)"', JS_WEB) if re.search(r"(?<![\w-])carta(?![\w-])", attr)
                       for c in attr.split("${")[0].split() if c != "carta"} | {"con-maglia"})
SEZIONE = ("carta", *CON_LA_CARTA)
BLOCCHI_AMMESSI = ("scambio", "accesso-corpo")      # spec §8.3: la proposta di uno scambio; piano, PR 5: il modulo d'accesso


def _soggetto(selettore):
    """L'elemento a cui la regola dà lo stile: l'ultimo pezzo del selettore, senza ciò che sta tra parentesi (`:has(...)`, `:not(...)`)."""
    ultimo = re.split(r"\s+|>|\+|~", selettore.strip())[-1]
    return re.sub(r"\([^()]*\)", "", ultimo)


def _ha_classe(pezzo, nome):
    return re.search(rf"\.{re.escape(nome)}(?![\w-])", pezzo) is not None


def _proprieta(corpo, *nomi):
    """[(nome, valore)] delle proprietà scritte nel corpo di una regola (solo i nomi dati, così `border` non prende `border-left`)."""
    return [(n, v.strip()) for n, v in re.findall(r"(?<![\w-])([\w-]+)\s*:\s*([^;]+)", corpo) if n in nomi]


def _regole_per(classi, ammesse=()):
    """(selettore, corpo) delle regole che danno lo stile a un elemento con una delle classi (anche nelle @media), pseudo-elementi esclusi."""
    for selettori, corpo in REGOLE:
        for s in selettori:
            soggetto = _soggetto(s)
            if "::" not in soggetto and any(_ha_classe(soggetto, c) for c in classi) and not any(_ha_classe(soggetto, a) for a in ammesse):
                yield s, corpo


def _scatole(classi, ammesse=()):
    """Regole che danno un fondo, un bordo intorno, un'ombra o angoli tondi a un elemento con una delle classi."""
    return [f"{s} {{ {nome}: {valore} }}" for s, corpo in _regole_per(classi, ammesse)
            for nome, valore in _proprieta(corpo, "background", "background-color", "border", "border-color", "border-radius", "box-shadow")
            if valore not in ("none", "0", "transparent")]


def test_la_carta_e_una_sezione_senza_scatola():
    regola = re.search(r"\n\.carta \{([^}]*)\}", CSS).group(1)
    assert "background: none" in regola and "border: 0" in regola and "border-radius" not in regola
    assert re.search(r"\.carta h2 \{[^}]*border-bottom: 2px solid var\(--testo\)", CSS)
    assert "--r-card: 12px" in CSS and ".col > * { animation: entra" not in CSS   # raggio del campo; niente entrata delle colonne


def test_nessuna_regola_rimette_il_riquadro_a_una_sezione():
    """Spec §4.1 e §8.3: niente scatole, lo spazio e i fili fanno i gruppi. In nessuna larghezza, densità o tema una regola dà di
    nuovo fondo, bordo, ombra o angoli tondi a una sezione, nemmeno con la classe che le sta accanto («carta proposta-r»,
    «carta vuoto»...). Restano un blocco solo la proposta di uno scambio e il modulo d'accesso."""
    assert {"hero", "proposta-r", "vuoto", "regola-sez", "imp-elenco"} <= set(CON_LA_CARTA)
    assert not _scatole(SEZIONE, BLOCCHI_AMMESSI)


def test_le_sezioni_stanno_sul_filo_del_titolo_della_pagina():
    """La distinta ha un bordo sinistro solo: il contenuto delle sezioni parte dove parte il titolo della pagina (nessun rientro a
    destra o a sinistra), a ogni larghezza e anche con la densità compatta e la pagina strettissima."""
    rientri = []
    for s, corpo in _regole_per(SEZIONE, BLOCCHI_AMMESSI):
        for _, valore in _proprieta(corpo, "padding"):
            v = valore.split()
            destra, sinistra = (v[0], v[0]) if len(v) == 1 else (v[1], v[3] if len(v) == 4 else v[1])
            if destra != "0" or sinistra != "0":
                rientri.append(f"{s} {{ padding: {valore} }}")
        rientri += [f"{s} {{ {n}: {v} }}" for n, v in _proprieta(corpo, "padding-left", "padding-inline") if v != "0"]
    assert not rientri, rientri


def test_tra_una_sezione_e_l_altra_lo_spazio():
    """Spec §7.4: 24 px tra una sezione e l'altra al telefono, 32 px da 900 px."""
    regola = re.search(r"\n\.carta \{([^}]*)\}", CSS).group(1)
    assert "margin-bottom: 24px" in regola
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*\n  \.carta \{ margin-bottom: 32px; \}", CSS)


def test_il_filo_del_titolo_sta_sotto_tutta_la_riga_se_il_titolo_ha_qualcosa_accanto():
    """Nel Diario (la stagione) e nelle Novità («Nuovo») il titolo della sezione sta in una riga con qualcosa a destra: il filo
    spesso va sotto tutta la riga, non solo sotto le parole del titolo (visto nelle foto del Diario a 390 e 1440 px)."""
    assert '<div class="carta" id="${idVoceDiario(g)}"><div class="riga"><h2' in APP
    assert '<div class="carta"><div class="riga"><h2' in APP
    assert "border-bottom: 2px solid var(--testo)" in _corpo(".carta > .riga:first-child:has(> h2)")
    titolo = _corpo(".carta > .riga:first-child > h2")
    assert "border-bottom: 0" in titolo and "padding-bottom: 0" in titolo


def test_dentro_le_sezioni_numeri_e_colonne_senza_riquadri():
    """Spec §8.6 e §9 (scheda): i numeri stanno senza scatola, separati da un filo. Le cifre affiancate della scheda (probabilità,
    statistiche), le due colonne del Diario e l'effetto di ogni motivo del «Perché questo numero» erano riquadri o pillole dentro la
    carta; tolta la carta restavano le sole scatole della pagina."""
    for selettore in (".stat-fila > div", ".statistiche div", ".diario-col", ".perche-effetto"):
        corpo = _corpo(selettore)
        scatola = [f"{n}: {v}" for n, v in _proprieta(corpo, "background", "border", "border-radius", "box-shadow")
                   if v not in ("none", "0", "transparent")]
        assert not scatola, (selettore, scatola)
    for selettore in (".stat-fila > div", ".statistiche div", ".diario-col"):
        assert "border-top: 1px solid var(--filo)" in _corpo(selettore), selettore


def test_la_proposta_di_scambio_resta_un_blocco_con_il_filo():
    """Spec §8.3: l'unico posto dove un riquadro raggruppa davvero qualcosa che si muove insieme (chi dai, chi ricevi, il verdetto)."""
    regola = re.search(r"\n\.carta\.scambio \{([^}]*)\}", CSS).group(1)
    assert "border: 1px solid var(--filo)" in regola and "border-radius: var(--r-card)" in regola and "padding: 16px" in regola
    assert 'class="carta scambio"' in APP


# ---------------------------------------------------------------- 5.2 pulsanti, controlli di scelta, focus e passaggio del mouse

def _corpo(selettore):
    """Il corpo della regola scritta proprio con questo selettore (fuori dalle @media: la prima che si trova)."""
    m = re.search(r"\n" + re.escape(selettore) + r" \{([^}]*)\}", SENZA_COMMENTI)
    assert m, f"manca la regola {selettore}"
    return m.group(1)


def test_pulsanti_piatti_scelta_con_bordo_e_niente_pressione():
    assert re.search(r"\.bottone \{[^}]*border-radius: var\(--r-in\)", CSS) and "--r-in: 8px" in CSS
    assert re.search(r"\.azione-testo \{[^}]*min-height: 44px;[^}]*min-width: 44px;[^}]*color: var\(--azione\)", CSS)
    assert re.search(r"\.chip\.attiva \{[^}]*border: 2px solid var\(--testo\)", CSS)    # il lime chiaro da solo è 2,8:1
    assert "scale(.95)" not in CSS and "scale(.985)" not in CSS


def test_focus_nel_colore_del_testo_e_riga_sotto_il_mouse():
    assert re.search(r"\n:focus-visible \{ outline: 2px solid var\(--testo\); outline-offset: 2px; \}", CSS)
    assert re.search(r"\.campo :focus-visible \{[^}]*outline-color: #fff", CSS)            # sul campo verde il focus è bianco
    assert re.search(r"\.voce:hover \{[^}]*background: var\(--superficie\)", CSS)


def test_toccare_non_rimpicciolisce_niente():
    """Spec §7.6 e §11: via la pressione che rimpiccioliva righe e pulsanti. Nessuna regola `:active` sposta o scala, e i pulsanti
    non animano più `transform` (resta il cambio di colore). Senza pressione non serve nemmeno la sua versione calma."""
    premuti = [f"{s} {{ transform: {v} }}" for selettori, corpo in REGOLE for s in selettori if ":active" in s
               for _, v in _proprieta(corpo, "transform") if v != "none"]
    assert not premuti, premuti
    assert "transform" not in dict(_proprieta(_corpo("button"), "transition")).get("transition", "")
    assert not any(":active" in s for selettori, _ in REGOLE for s in selettori if "data-calmo" in s)


def test_il_focus_ha_un_colore_solo_e_si_vede_su_ogni_fondo():
    """Spec §14 e C11: il bordo del focus è sempre del colore del testo (bianco sul campo verde), almeno 3:1 con ogni fondo su cui
    può stare, in chiaro e in scuro (WCAG 2.2, 1.4.11). Prima c'erano anche un focus blu e uno verde delle azioni: in chiaro il
    verde bosco intorno al lime della scelta stava sotto 3:1 con il lime."""
    from tests.test_design_web import _colore, _contrasto_rgb, _temi
    altri = [f"{s} {{ {n}: {v} }}" for selettori, corpo in REGOLE for s in selettori if "focus" in s
             for n, v in _proprieta(corpo, "outline", "outline-color", "border-color")
             if v not in ("none", "0") and "var(--testo)" not in v and "#fff" not in v]
    assert not altri, altri
    for tema, v in _temi().items():
        testo = _colore(v["--testo"])[0]
        for fondo in ("--sfondo", "--superficie", "--solido"):           # il bordo sta fuori dalla voce (stacco di 2 px): sul fondo
            assert _contrasto_rgb(testo, _colore(v[fondo])[0]) >= 3, (tema, fondo)
        assert _contrasto_rgb((255, 255, 255), _colore(v["--campo"])[0]) >= 3, tema


def test_la_scelta_si_riconosce_anche_senza_il_colore():
    """Spec §7.1 e §8.8: il lime chiaro sta a 2,8:1 dal bianco e da solo non dice «scelto» (WCAG 1.4.11). La voce scelta dei moduli,
    degli stili e dei controlli segmentati ha anche un bordo di 2 px del colore del testo e la scritta in grassetto (più
    `aria-pressed`). Il bordo in più non sposta le voci vicine: il chip scelto toglie con il margine il pixel che aggiunge."""
    base, scelto = _corpo(".chip"), _corpo(".chip.attiva")
    assert "border: 1px solid var(--bordo-campo)" in base and "background: none" in base
    assert all(x in scelto for x in ("background: var(--capitano)", "border: 2px solid var(--testo)", "margin: -1px",
                                     "color: var(--capitano-testo)", "font-weight: 650"))
    segmento = _corpo(".segmenti button.attivo")
    assert all(x in segmento for x in ("background: var(--capitano)", "box-shadow: inset 0 0 0 2px var(--testo)",
                                       "color: var(--capitano-testo)", "font-weight: 650"))
    striscia = _corpo(".segmenti")
    assert "border: 1px solid var(--bordo-campo)" in striscia and "border-radius: var(--r-in)" in striscia
    assert re.search(r"\.segmenti button \+ button \{[^}]*border-left: 1px solid var\(--filo\)", SENZA_COMMENTI)   # voci separate da un filo


def test_la_scelta_si_riconosce_anche_con_il_contrasto_elevato_di_windows():
    """Revisione di accessibilità della #405: con i colori forzati (contrasto elevato di Windows) il browser toglie il fondo lime e le
    ombre, quindi il bordo della voce scelta di un controllo segmentato (un'ombra interna) spariva e la scelta non si vedeva più. Lì la
    voce scelta ha un contorno vero nel colore di sistema della selezione. Moduli e stili hanno un bordo vero, che resta."""
    assert re.search(r"@media \(forced-colors: active\) \{\s*\.segmenti button\.attivo \{ outline: 2px solid Highlight; "
                     r"outline-offset: -2px; \}\s*\}", SENZA_COMMENTI)
    assert "border: 2px solid var(--testo)" in _corpo(".chip.attiva")


def test_il_focus_della_voce_scelta_sta_dentro_la_striscia_che_scorre():
    """Revisione di accessibilità della #405: nella striscia dei moduli e degli stili (che scorre di lato e taglia ciò che esce) la voce
    scelta sporge di 1 px (bordo di 2 px e margine di −1 px) e il focus sta 2 + 2 px più in là: 5 px, con 4 px di spazio il contorno
    veniva tagliato. Lo spazio intorno alle voci basta per tutto il contorno; il margine negativo uguale tiene le voci allineate."""
    fuoco = re.search(r"\n:focus-visible \{ outline: (\d+)px solid var\(--testo\); outline-offset: (\d+)px; \}", SENZA_COMMENTI)
    sporge = -int(re.search(r"margin: (-\d+)px", _corpo(".chip.attiva")).group(1))
    serve = int(fuoco.group(1)) + int(fuoco.group(2)) + sporge
    striscia = _corpo(".chips.scorri")
    spazio = int(re.search(r"(?<![\w-])padding: (\d+)px;", striscia).group(1))
    assert spazio >= serve, (spazio, serve)
    assert f"margin: {2 - (spazio - 4)}px -{spazio}px {4 - (spazio - 4)}px" in striscia     # stesso ingombro di prima, voci allineate


def test_pulsante_secondario_da_solo_con_il_bordo_nella_riga_solo_testo():
    """Spec §8.7: un pulsante pieno per schermata (fondo `--azione`); il secondario da solo ha il bordo dei controlli e la scritta del
    testo, quello nella riga (`.azione-testo`) è solo testo del colore delle azioni, con l'area da 44 px. Mai tre contorni in fila."""
    secondario = _corpo(".bottone.secondario")
    assert all(x in secondario for x in ("background: none", "border-color: var(--bordo-campo)", "color: var(--testo)"))
    testo = _corpo(".azione-testo")
    assert "background: none" in testo and "border: 0" in testo
    assert re.search(r"\.bottone:hover:not\(:disabled\) \{ background: var\(--azione-2\); \}", SENZA_COMMENTI)
    assert "filter: brightness" not in SENZA_COMMENTI                                   # il passaggio del mouse cambia il fondo, non la luce


# ---------------------------------------------------------------- 5.3 etichette come testo colorato

def test_etichette_senza_fondo_ne_bordo_tranne_le_due_pillole():
    regola = re.search(r"\n\.etichetta \{([^}]*)\}", CSS).group(1)
    assert "background: none" in regola and "border: 0" in regola and "font-size: var(--t-sec)" in regola
    assert re.search(r"\.pedina \.gioca\.basso[^{]*\{[^}]*border-radius", CSS)        # «⚠ gioca 45%» resta una pillola


def test_nessuna_regola_rimette_la_pillola_alle_etichette():
    """Spec §8.9: le etichette dei giocatori sono testo nel colore del loro tono (verde, arancio, rosso, grigio per il neutro), senza
    fondo, bordo né angoli, in ogni variante e in ogni posto (righe, scheda, confronto, Oggi in corso). Le parole e i toni restano
    quelli del server, gli stessi dell'iPhone (che le mostra come pillole: differenza ammessa)."""
    assert not _scatole(["etichetta"])
    for classe, colore in ((".etichetta", "--eti-verde"), (".etichetta.arancio", "--eti-arancio"), (".etichetta.rossa", "--eti-rosso"),
                           (".etichetta.neutra", "--testo-2"), (".tono", "--eti-verde"), (".tono.arancio", "--eti-arancio"),
                           (".tono.rossa", "--eti-rosso"), (".tono.neutra", "--testo-2")):
        assert f"color: var({colore})" in _corpo(classe), classe


def test_differenza_ammessa_delle_etichette_scritta():
    """Spec §13: le etichette diventano testo colorato sulla web e restano pillole sull'iPhone; la differenza (parole e toni uguali) si
    scrive in «Differenze ammesse» nella PR che la introduce, questa."""
    doc = (RADICE / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    ammesse = doc[doc.index("## Differenze ammesse"):doc.index("## Differenze di oggi")]
    riga = next((r for r in ammesse.splitlines() if "Etichette dei giocatori" in r), "")
    assert "testo colorato" in riga and "pillole" in riga and "toni" in riga, riga


def test_piu_etichette_nella_stessa_riga_separate_dal_punto():
    """Spec §8.9: senza la pillola, due etichette vicine («Real Esempio · In ballottaggio») si separano con « · ». Il punto sta in fondo
    all'etichetta prima, attaccato con uno spazio che non va a capo (come i pezzi di un'etichetta lunga), è grigio e i lettori di
    schermo non lo leggono (testo alternativo vuoto)."""
    punto = _corpo(".etichette > .etichetta:not(:last-child)::after")
    assert 'content: "\\a0·" / ""' in punto and "color: var(--testo-2)" in punto


# ---------------------------------------------------------------- 5.4 avvisi, errori, stati vuoti, messaggio che passa
AVVISI = ("errore", "attenzione", "verdetto", "nota-incerto", "banner-novita", "vuoto")


def test_avvisi_con_filo_a_sinistra_nel_colore_del_significato():
    assert re.search(r"\n\.errore \{[^}]*border-left: 3px solid var\(--rosso\)", CSS)
    assert re.search(r"\n\.attenzione \{[^}]*border-left: 3px solid var\(--arancio\)", CSS)


def test_avvisi_ed_errori_senza_riquadro_con_il_testo_pieno():
    """Spec §8.12-8.13: un avviso è una riga con il filo di 3 px a sinistra nel colore del significato (rosso errore, arancio dubbio,
    verde per il verdetto buono di uno scambio) e il testo nel colore del testo: l'errore non è più tutto rosso su un fondo rosa.
    Niente fondo, bordo intorno né angoli, in nessuna variante; lo stato vuoto è una riga grigia allineata a sinistra. Il filo si vede
    sul fondo della pagina (almeno 3:1) in chiaro e in scuro, ma non è l'unico segno: la frase dice già cosa succede."""
    from tests.test_design_web import _colore, _contrasto_rgb, _temi
    assert not _scatole(AVVISI)
    assert "color: var(--testo)" in _corpo(".errore") and "color: var(--rosso)" not in _corpo(".errore")
    for classe, colore in ((".verdetto.ok", "--verde"), (".verdetto.attenzione-lieve", "--arancio"), (".verdetto.no", "--rosso"),
                           (".nota-incerto", "--arancio")):
        assert f"border-left-color: var({colore})" in _corpo(classe) or f"border-left: 3px solid var({colore})" in _corpo(classe), classe
    vuoto = _corpo(".vuoto")
    assert "color: var(--testo-2)" in vuoto and "text-align: center" not in vuoto
    for tema, v in _temi().items():
        for colore in ("--rosso", "--arancio", "--verde"):
            assert _contrasto_rgb(_colore(v[colore])[0], _colore(v["--sfondo"])[0]) >= 3, (tema, colore)


def test_il_messaggio_che_passa_e_pieno_e_si_stacca_dalla_pagina():
    """Spec §8.13: il messaggio che passa resta (in basso a sinistra sul PC), pieno, senza vetro. Con le superfici piene il «vetro» ha
    il colore della pagina: nello scuro il messaggio non si staccava dal fondo. Ora ha i colori del testo e della pagina scambiati
    (la scritta almeno 4,5:1), senza ombra né l'anello verde che si allargava; l'errore non ha più l'anello rosso intorno."""
    from tests.test_design_web import _colore, _contrasto_rgb, _temi
    corpo = _corpo(".avviso")
    assert all(x in corpo for x in ("background: var(--testo)", "color: var(--sfondo)", "border: 0", "box-shadow: none",
                                    "border-radius: var(--r-in)"))
    for tema, v in _temi().items():
        assert _contrasto_rgb(_colore(v["--sfondo"])[0], _colore(v["--testo"])[0]) >= 4.5, tema
    assert "anello" not in _corpo(".avviso:not([hidden])")
    assert "anello-rosso" not in SENZA_COMMENTI


def test_novita_della_versione_una_riga_con_il_filo():
    """Spec §9 (Oggi): il banner delle novità diventa una riga con il filo sopra e sotto («Novità della versione 1.402»), alta 44 px."""
    corpo = _corpo(".banner-novita")
    assert all(x in corpo for x in ("border: 0", "border-top: 1px solid var(--filo)", "border-bottom: 1px solid var(--filo)",
                                    "min-height: 44px", "background: none"))


def test_novita_delle_sezioni():
    voce = _voce_di_novita("sezioni-pulsanti.json", "Meno riquadri: sezioni con un titolo e righe")
    assert len(voce["voci"]) >= 2


# ---------------------------------------------------------------- PR 6: riga del giocatore e colonne di numeri
def _esegui_righe(chiamata, lingua="it"):
    """Le funzioni delle righe dei giocatori (da «pezzi grafici riusati» a «navigazione» di app.js) girate con node, con i testi veri
    e pochi sostituti: volto vuoto, una data fissa, nessuna memoria del browser."""
    testi = (WEB / "testi.js").read_text(encoding="utf-8")
    pezzo = lambda a, b: APP[APP.index(a):APP.index(b)]
    codice = "\n".join([
        testi,
        f"LINGUA = '{lingua}';",
        "const stato = {}; globalThis.document = { addEventListener() {} };",
        "const AvatarSchieraxi = { svg: () => '<svg></svg>' }; const quando = () => 'sab 31 20:45';",
        "const cognome = x => x.nome;",
        pezzo("function esc(x)", "const menoMovimento"),
        re.search(r"^const ruoloSigla = .*$", APP, re.M).group(0),
        re.search(r"^const SIGLE = \{.*?\};$", APP, re.M | re.S).group(0),
        re.search(r"^const TITOLARITA = \{.*?\};$", APP, re.M | re.S).group(0),
        pezzo("// ---------------------------------------------------------------- pezzi grafici riusati",
              "// ---------------------------------------------------------------- navigazione"),
        f"console.log(JSON.stringify({chiamata}));",
    ])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo_riga(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


GIOCATORE = {"id": 7, "nome": "Rossi L.", "ruolo": "D", "squadra": "napoli", "avversario": "lazio", "in_casa": True,
             "data_partita": "2026-10-31 20:45", "p_voto": 0.85, "fv_atteso": 6.8, "indice": 57,
             "etichetta": {"codice": "titolare", "testo": "Probabile titolare", "tono": "positivo"}}


def test_riga_del_giocatore_con_pochi_segni_e_gioca_intero():
    """Spec §8.4: niente quadratino colorato del ruolo, niente barra della probabilità, niente pallino della difficoltà; la lettera
    del ruolo grigia, la lineetta del club davanti alla partita e «gioca N%» scritto intero."""
    corpo = _funzione(APP, "voceGiocatore")
    assert "badgeRuolo(" not in corpo and "barra-p" not in corpo and 'class="diff' not in corpo
    assert 'class="ruolo-l"' in corpo and "lineetta(x.squadra)" in corpo and "numeriRiga(x" in corpo
    assert 't("giocatore.gioca"' in _funzione(APP, "numeriRiga")
    assert ".barra-p" not in CSS                                # la barra della probabilità non c'è più da nessuna parte


@pytest.mark.skipif(not NODE, reason="serve node")
def test_riga_del_giocatore_prima_e_dopo_la_partita():
    g = json.dumps(GIOCATORE)
    prima, dubbio, fatto, corso = _esegui_righe(f"""[
      voceGiocatore({g}),
      voceGiocatore({{...{g}, p_voto: 0.55}}),
      voceGiocatore({{...{g}, stato_partita: "fatto", fv_preso: 7, etichetta: {{codice: "voto", testo: "Ha giocato", tono: "positivo"}}}}),
      voceGiocatore({{...{g}, stato_partita: "in_corso", etichetta: {{codice: "in_corso", testo: "Partita in corso", tono: "positivo"}}}})]""")
    testo = _testo_riga(prima)
    assert testo.startswith("57 D Rossi L. NAP vs LAZ")                     # indice sul volto, lettera del ruolo, nome, partita
    assert "sab 31 20:45" in testo and "Probabile titolare" in testo and testo.endswith("gioca 85% Fantavoto atteso 6,8")
    assert '<span class="pv-g">gioca 85%</span>' in prima                   # grigio sopra il 70%...
    assert '<span class="pv-g basso">gioca 55%</span>' in dubbio            # ...arancio e in grassetto sotto
    gioca = re.compile(r"gioca \d")                                          # «data-giocatore» non conta
    assert "7,0" in _testo_riga(fatto) and not gioca.search(fatto)          # a partita finita il fantavoto preso, mai «gioca N%»
    assert _testo_riga(fatto).endswith("fantavoto 7,0")
    assert not gioca.search(corso) and _testo_riga(corso).endswith("Partita in corso –")    # in corso «–», nascosto ai lettori
    assert '<b class="debole" aria-hidden="true">–</b>' in corso
    for html in (prima, fatto):
        assert "conic-gradient" not in html and "avatar-anello alto" not in html and 'class="ruolo ' not in html


@pytest.mark.skipif(not NODE, reason="serve node")
def test_il_fantavoto_atteso_ha_il_suo_nome_per_i_lettori_di_schermo():
    """I nomi delle colonne sono nascosti ai lettori di schermo: senza un nome il numero si sentiva da solo («gioca 85%, 6,8»).
    Dentro la colonna del numero c'è «Fantavoto atteso» per i soli lettori; il fantavoto preso ha già «fantavoto» scritto accanto."""
    g = json.dumps(GIOCATORE)
    riga, rosa, scelta = _esegui_righe(f"[voceGiocatore({g}), valoreRosa({g}, {{id: 7}}), numeriRiga({{p_voto: 0.5, fv_atteso: 6}})]")
    en = _esegui_righe(f"voceGiocatore({g})", "en")
    for html in (riga, rosa, scelta):
        assert re.search(r'<span class="valore"><span class="solo-lettori">Fantavoto atteso </span><b[^>]*>\d,\d</b></span>', html), html
    assert _testo_riga(en).endswith("plays 85% Expected fantasy score 6.8")
    sostituzione = _funzione(APP, "mostraFormazione")
    sostituzione = sostituzione[sostituzione.index("function apriSostituzione"):]
    assert '<span class="valore">${nomeFvAtteso()}<b>' in sostituzione                  # anche la sostituzione


@pytest.mark.skipif(not NODE, reason="serve node")
def test_partita_rinviata_nella_riga_come_prima_della_partita():
    """Partita rinviata (#284, #313): nella riga l'etichetta «Rinviata», poi «gioca N%» e il fantavoto atteso, come prima della
    partita e come `RigaGiocatore.numero`/`sottoNumero` dell'iPhone; mai il «–» delle partite cominciate. Anche con un server
    vecchio senza `etichetta` (solo `stato_partita`)."""
    g = dict(GIOCATORE, p_voto=0.5, fv_atteso=6.0)
    nuova = dict(g, stato_partita="rinviata", etichetta={"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"})
    vecchia = {k: v for k, v in dict(g, stato_partita="rinviata", titolarita=None).items() if k != "etichetta"}
    for x in (nuova, vecchia):
        testo = _testo_riga(_esegui_righe(f"voceGiocatore({json.dumps(x)})"))
        assert testo.endswith("Rinviata gioca 50% Fantavoto atteso 6,0"), testo
        assert "–" not in testo


def test_la_griglia_della_riga_e_dell_intestazione_ha_lo_stesso_carattere():
    """Le colonne dei numeri sono in `ch`, che dipende dal carattere dell'elemento con la griglia: con il 12 px dato alla griglia
    dell'intestazione le sue colonne erano più strette di quelle delle righe (15 px) e «Partita» stava 6-7 px fuori posto. Nessuna
    regola dà un carattere alla griglia (`.voce-g`): il 12 px dei nomi delle colonne sta sui loro pezzi."""
    for selettori, corpo in REGOLE:
        for s in selettori:
            if _ha_classe(_soggetto(s), "voce-g"):
                assert not re.search(r"(?<![\w-])font(?:-size)?\s*:", corpo), f"{s} {{ {corpo} }}"
    assert "font-size: var(--t-eti)" in _corpo(".intestazione-colonne > .voce-g > span")


@pytest.mark.skipif(not NODE, reason="serve node")
def test_la_riga_della_partita_va_a_capo_tra_i_pezzi():
    """A 390 px «INT vs COM · dom 8 18:00 · Real Esempio» andava a capo dentro il nome della squadra («Real» sopra, «Esempio» sotto).
    Ogni pezzo è un blocco intero, con il «·» attaccato al pezzo prima: si va a capo tra i pezzi."""
    riga = _esegui_righe(f"voceGiocatore({json.dumps(GIOCATORE)}, null, false, false, 'Real Esempio')")
    assert '<span class="nb">Real Esempio</span>' in riga
    assert re.search(r'<span class="nb">NAP <span aria-hidden="true">vs LAZ</span>.*? · sab 31 20:45 ·</span> <span class="nb">', riga)
    assert re.search(r"\.voce-g \.dettaglio \.nb \{[^}]*display: inline-block; max-width: 100%", CSS)


@pytest.mark.skipif(not NODE, reason="serve node")
def test_lineetta_nei_colori_sociali_e_grigia_se_il_club_manca():
    """Il primo colore del club; il secondo nel tema in cui il primo sparisce sul fondo (il bianco della Juventus sul fondo
    chiaro, il verde scuro del Venezia su quello scuro). `--c` per il tema chiaro, `--c-scuro` per lo scuro."""
    napoli, juve, venezia, ignoto, finto = _esegui_righe(
        '[lineetta("napoli"), lineetta("juventus"), lineetta("venezia"), lineetta("nessuno"), lineetta("constructor")]')
    assert napoli == '<i class="lineetta" style="--c:#3d8fd1;--c-scuro:#3d8fd1" aria-hidden="true"></i>'
    assert juve == '<i class="lineetta" style="--c:#111827;--c-scuro:#f3f4f6" aria-hidden="true"></i>'
    assert venezia == '<i class="lineetta" style="--c:#0b3d2e;--c-scuro:#f08a1a" aria-hidden="true"></i>'
    assert ignoto == finto == '<i class="lineetta" style="--c:#6b7280;--c-scuro:#6b7280" aria-hidden="true"></i>'
    corpo = _corpo(".lineetta")
    assert "width: 3px" in corpo and "background: var(--c-scuro)" in corpo
    assert ':root[data-tema="chiaro"] .lineetta { background: var(--c); }' in CSS


@pytest.mark.skipif(not NODE, reason="serve node")
def test_intestazione_delle_colonne():
    con, senza, ferma = _esegui_righe("[intestazioneColonne(), intestazioneColonne({ partita: false }), "
                                      "intestazioneColonne({ ferma: true, azione: true })]")
    en = _esegui_righe("intestazioneColonne()", "en")
    assert 'class="intestazione-colonne" aria-hidden="true"' in con
    assert _testo_riga(con) == "Partita Fantavoto atteso" and _testo_riga(senza) == "Fantavoto atteso"
    assert 'class="intestazione-colonne ferma posto-azione"' in ferma
    assert _testo_riga(en) == "Match Expected fantasy score"


def test_intestazione_delle_colonne_nascosta_ai_lettori_e_colonne_pari():
    assert 'aria-hidden="true"' in _funzione(APP, "intestazioneColonne")
    assert re.search(r"--col-gioca: \d+(?:\.\d+)?ch", CSS) and re.search(r"--col-fv: \d+(?:\.\d+)?ch", CSS)
    assert ".avatar-anello.alto" not in CSS and "conic-gradient" not in _corpo(".avatar-anello")   # niente anello colorato per l'indice


def test_l_indice_resta_un_numero_neutro_sul_volto():
    """Spec §8.4: l'indice (0-100) resta come numero piccolo sul volto, nei colori del testo e della pagina (mai sotto i 12 px)."""
    badge = _corpo(".badge-indice")
    assert "background: var(--sfondo)" in badge and "color: var(--testo)" in badge and "font-size: var(--t-eti)" in badge
    assert not re.search(r"\.badge-indice \{[^}]*color: #fff", CSS)          # il bianco serviva sul pallino colorato


def test_le_colonne_dei_numeri_stanno_nello_stesso_posto_in_ogni_riga():
    """Spec C8: «gioca N%» e il fantavoto atteso nelle stesse colonne, larghe uguali, in ogni riga e nell'intestazione; sotto i 680 px
    di riga i due numeri uno sopra l'altro (come l'iPhone), da 680 px una riga sola con la colonna «Partita»."""
    base = _corpo(".voce-g")
    assert "grid-template-areas:" in base and "var(--col-gioca)" in base
    larga = re.search(r"@container riga \(min-width: 680px\) \{(.*?)\n\}", CSS, re.S)
    assert larga, "manca la riga larga"
    assert re.search(r"\.voce-g \{[^}]*var\(--col-gioca\) var\(--col-fv\)", larga.group(1))
    assert re.search(r"\.voce-g > \.testo-g \{ display: contents; \}", larga.group(1))
    assert "container: riga / inline-size" in _corpo(".riga-gioc, .intestazione-colonne")
    assert '<ul class="elenco posto-azione">${fuori.map' in APP         # «Fuori» lascia il posto del ⇄: colonne come Titolari e Panchina


def test_formazione_titolari_panchina_e_fuori_in_una_colonna_sul_pc():
    """A 1440 px Titolari e Panchina stavano in due colonne strette (`columns: 2`): i numeri non si confrontavano e la riga non
    poteva stare su una linea. Ora stanno uno sotto l'altro nella colonna larga, con le colonne allineate."""
    assert not re.search(r"\.colonne-campo > \.col:nth-child\(2\)[^{]*\{[^}]*columns: 2", CSS)


def test_il_campo_che_scorre_con_la_pagina_tiene_dentro_le_sue_linee():
    """Tra 768 e 1399 px, con il campo più alto della finestra, `controllaFerme` lo fa scorrere con la pagina (`.non-ferma`,
    position: static): area, cerchio e metà campo, che stanno in posizione assoluta, si misuravano sulla pagina e attraversavano
    la colonna accanto (si vedeva nel tema scuro, foto della PR 6 a 1024 px). Il campo resta il loro riferimento."""
    assert re.search(r"\n\.campo\.non-ferma \{ position: relative !important; \}", CSS)


def test_azione_della_riga_scritta_senza_cerchio():
    """Spec C9 e §8.7: «⇄» e «✎» sono icone da 44 px nel colore delle azioni, nella riga a destra, senza il cerchio a contorno."""
    mini = _corpo(".confronta-mini")
    assert "width: 44px; height: 44px" in mini and "border: 0" in mini and "color: var(--azione)" in mini
    assert "border-radius: 50%" not in mini


def test_nome_del_giocatore_nelle_righe_a_15_px_e_numero_a_20():
    assert "font-size: var(--t-corpo)" in _corpo(".voce-g .nome") and "font-weight: 650" in _corpo(".voce-g .nome")
    assert "font-size: var(--t-valore)" in _corpo(".voce .valore b")


def test_la_frase_sotto_i_titolari_parla_del_numero_sul_volto():
    """Senza l'anello colorato la frase che spiega l'indice non può più parlare di un anello (in italiano e in inglese)."""
    testi = (WEB / "testi.js").read_text(encoding="utf-8")
    frasi = re.findall(r'"formazione\.numero_sulla_maglia": "([^"]+)"', testi)
    assert len(frasi) == 2 and all("anello" not in f and "ring" not in f for f in frasi), frasi
    assert "il numero sul volto è l'indice" in frasi[0] and "the number on the face is the index" in frasi[1]


def test_differenza_ammessa_della_lineetta_scritta():
    doc = (RADICE / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    ammesse = doc[doc.index("## Differenze ammesse"):doc.index("## Differenze di oggi")]
    riga = next((r for r in ammesse.splitlines() if "Sigla della squadra nelle righe" in r), "")
    assert "lineetta" in riga and "colori sociali" in riga, riga


def test_novita_della_riga_del_giocatore():
    voce = _voce_di_novita("riga-giocatore.json", "Righe dei giocatori più basse, numeri in colonna")
    assert len(voce["voci"]) >= 2


# ---------------------------------------------------------------- PR 7: Oggi come distinta
DAFARE = (WEB / "dafare.js").read_text(encoding="utf-8")
# «14 giorni», il pezzo più largo del conto alla rovescia (numero e unità non vanno a capo, #286), in em del carattere: misurato il
# 6/11/2026 in Chrome a 600 di peso (senza la spaziatura stretta delle lettere, quindi con margine). Il carattere di sistema (Segoe UI)
# è il più largo dei due: se Archivo non arriva vale lui. E le forme più lunghe di una riga, «1 giorno 8 h» e «23 h 59 min», in
# Archivo con la spaziatura delle lettere (-0,02 em): 4,49 em.
LARGHEZZA_14_GIORNI = {"archivo": 3.56, "sistema": 3.94}
LARGHEZZA_RIGA_ARCHIVO = 4.49


def test_oggi_senza_nome_e_slogan_e_con_due_colonne_5_7():
    assert "marchioOggi(" not in APP and ".slogan-oggi" not in CSS
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*\.colonne-oggi[^{]*\{ grid-template-columns: minmax\(0, 5fr\) minmax\(0, 7fr\)", CSS)


def test_sul_pc_largo_la_colonna_di_destra_di_oggi_in_due():
    """Scelta della PR 7 (#415): da 1400 px la colonna di destra di Oggi (~672 px) si divide in due, migliori e avvisi | partite del
    turno, invece della colonna sola disegnata nella spec §9. Una colonna sola non arriva ai 680 px della riga larga dei giocatori e
    manda le partite sotto il primo schermo; in due tutto sta in vista. Le sezioni non si spezzano tra le due colonne."""
    blocco = re.search(r"@media \(min-width: 1400px\) \{(.*?)\n\}", CSS, re.S).group(1)
    assert re.search(r"main \.colonne-oggi > \.col:nth-child\(2\) \{ display: block; columns: 2;", blocco)
    assert "main .colonne-oggi > .col:nth-child(2) > * { break-inside: avoid; }" in blocco


def test_da_fare_con_l_azione_scritta_nella_riga():
    corpo = _funzione(DAFARE, "dfRiga")
    assert 'class="azione-testo df-azione"' in corpo and "bottone secondario" not in corpo


def test_maglia_piccola_dritta_senza_ombra():
    regola = re.search(r"\.maglia-hero \{([^}]*)\}", CSS).group(1)
    assert "height: 72px" in regola and "rotate" not in regola and "drop-shadow" not in regola


def test_conto_alla_rovescia_grande_senza_riquadro_e_sempre_intero():
    """Spec §9 e issue #384: il conto alla rovescia è il numero eroe (56 px, 72 px da 900 px) senza riquadro, e non si taglia mai.
    La maglia sta nella sua colonna accanto (niente posizione assoluta sopra il testo) e il numero si rimpicciolisce con la colonna
    che gli resta: con il pezzo più largo («14 giorni») e il carattere più largo ci sta sempre, con o senza maglia, a ogni larghezza.
    Prima accanto alla maglia il numero scendeva alla misura dei titoli e la maglia, larga 150 px, copriva il testo."""
    corpo = _funzione(APP, "mostraOggi")
    assert 'class="conto-oggi${' in corpo and "carta hero conto" not in APP and 'class="enorme" id="conto"' in corpo
    assert not _scatole(["conto-oggi", "conto-testo"])
    assert "container-type: inline-size" in _corpo(".conto-testo")
    k = float(re.search(r"font-size: min\(var\(--t-eroe\), (\d+(?:\.\d+)?)cqi\)", _corpo(".conto-testo .enorme")).group(1))
    assert k * max(LARGHEZZA_14_GIORNI.values()) <= 100, k             # mai tagliato
    assert k * LARGHEZZA_RIGA_ARCHIVO <= 100, k                         # «15 h 41 min» su una riga sola, non «15 h» sopra e «41 min» sotto
    assert "grid-template-columns: minmax(0, 1fr) auto" in _corpo(".conto-oggi.con-maglia")
    maglia = _corpo(".maglia-hero")
    assert "position: absolute" not in maglia and "animation" not in maglia      # dritta e ferma: si muove solo ciò che risponde a un gesto
    assert ".con-maglia .enorme" not in CSS and "padding-right: 132px" not in CSS


def test_oggi_nell_ordine_della_distinta():
    """Spec §9 e piano, PR 7: a sinistra (al telefono prima) il conto alla rovescia, le cifre della formazione con «Apri la formazione»
    subito sotto (nel primo schermo), poi Partita rinviata e Da fare; a destra I tuoi migliori, Da controllare, Indisponibili (chiuso),
    Diffidati e Partite del turno. Le probabili stanno con la formazione, come sull'iPhone."""
    corpo = _funzione(APP, "mostraOggi")
    sinistra, destra = corpo.split('</div><div class="col">')
    ordine = ['id="conto"', 'id="oggi-punti"', 't("oggi.apri_formazione")', 'id="probabili-fresche"', "${cardRinvio(o.rinvio)}",
              "${cardDaFare(o.da_fare)}"]
    posti = [sinistra.index(x) for x in ordine]
    assert posti == sorted(posti), ordine
    ordine = ['t("oggi.tuoi_migliori_della")', 't("oggi.da_controllare")', 't("oggi.indisponibili"', 't("oggi.diffidati")',
              't("oggi.partite_del_turno")']
    posti = [destra.index(x) for x in ordine]
    assert posti == sorted(posti), ordine
    assert '<details><summary>${t("oggi.indisponibili"' in destra and "<details open" not in destra      # Indisponibili chiuso


def test_cifre_affiancate_separate_da_un_filo():
    """Spec §8.6: le cifre stanno senza scatola, affiancate e separate da un filo verticale («La tua formazione 4-4-2 | Punti attesi
    65,5»); lo stesso a giornata in corso (punti finora | a fine giornata) e a giornata finita (punti fatti | attesi)."""
    for nome in ("mostraOggi", "cardInCorso", "cardRiepilogo"):
        assert 'class="cifre-oggi"' in _funzione(APP, nome), nome
    assert "display: grid" in _corpo(".cifre-oggi")
    assert "border-left: 1px solid var(--filo)" in _corpo(".cifre-oggi > .cifra + .cifra")
    assert not _scatole(["cifre-oggi", "cifra"])
    assert 'style="text-align:right"' not in _funzione(APP, "mostraOggi")


def test_un_solo_pulsante_pieno_in_oggi():
    """Spec §4.5 e §8.7: un solo pulsante pieno per schermata («Apri la formazione»); le azioni di Da fare sono testo nella riga, anche
    quella urgente (lo dice la parola «Urgente»), mai tre «Sostituisci» a contorno in fila."""
    assert _funzione(APP, "mostraOggi").count('class="bottone') == 1
    assert 'class="bottone' not in DAFARE


def test_contatore_di_da_fare_un_numero_grigio():
    """Piano, PR 7: il contatore di «Da fare» è un numero grigio accanto al titolo, non più il pallino lime."""
    assert '<h2>${t("df.da_fare")} <span class="df-conto">${valide.length}</span></h2>' in DAFARE
    conto = _corpo(".df-conto")
    assert "color: var(--testo-2)" in conto and "font-family: var(--font-numeri)" in conto
    assert not _scatole(["df-conto"]) and "--capitano" not in conto


def test_azione_di_da_fare_a_destra_e_sotto_il_testo_se_stretta():
    """Spec C9: l'azione sta nella riga, a destra. Nella colonna stretta (telefono, sinistra del PC) va sotto il testo, sempre a destra."""
    stretta = re.search(r"@container \(max-width: 520px\) \{(.*?)\n\}", CSS, re.S).group(1)
    assert ".df-azione { justify-self: end; }" in stretta
    assert "min-height: 44px" in _corpo(".df-azione")


def test_righe_degli_avvisi_con_la_lettera_del_ruolo_e_l_etichetta_scritta():
    """Spec §8.4, §8.9 e §11: in Da controllare, Indisponibili, Diffidati e nella giornata in corso niente quadratino colorato del
    ruolo né pallino della gravità: la lettera grigia del ruolo, come nelle righe dei giocatori, e la gravità nel colore
    dell'etichetta scritta (le parole dicono già tutto)."""
    corpo = _funzione(APP, "rigaAvviso") + _funzione(APP, "cardInCorso") + _funzione(APP, "mostraOggi")
    assert "badgeRuolo(" not in corpo and "pallino-stato" not in corpo and ".pallino-stato" not in CSS
    assert 'class="ruolo-l"' in _funzione(APP, "rigaAvviso") and 'class="ruolo-l"' in _funzione(APP, "cardInCorso")
    assert "inFormazione.map(rigaAvviso)" in corpo and "indisponibili.map(rigaAvviso)" in corpo and "altri.map(rigaAvviso)" in corpo


@pytest.mark.skipif(not NODE, reason="serve node")
def test_riga_di_da_controllare_con_le_parole_del_server():
    from tests.test_oggi_fasi_web import _esegui as _esegui_oggi
    a = {"id": 3, "nome": "Rossi <b>", "ruolo": "D", "squadra": "inter", "tipo": "dubbio", "p_voto": 0.55, "nota": "affaticato",
         "in_formazione": True, "etichetta": {"codice": "dubbio", "testo": "In dubbio · gioca 55%", "tono": "attenzione"}}
    h = _esegui_oggi(f"rigaAvviso({json.dumps(a)})")
    assert '<span class="ruolo-l">D</span>' in h and "Rossi &lt;b&gt;" in h and 'data-giocatore="3"' in h
    assert '<span class="etichetta arancio">In dubbio · gioca 55%</span>' in h and "affaticato" in h
    senza = {k: v for k, v in a.items() if k != "etichetta"}
    assert '<span class="etichetta rossa">Infortunato</span>' in _esegui_oggi(f"rigaAvviso({json.dumps(senza | {'tipo': 'infortunato'})})")
    assert '<span class="etichetta arancio">In dubbio · gioca 55%</span>' in _esegui_oggi(f"rigaAvviso({json.dumps(senza)})")
    assert '<span class="etichetta neutra">Diffidato</span>' in _esegui_oggi(f"rigaAvviso({json.dumps(senza | {'tipo': 'diffidato'})})")


def test_differenze_di_oggi_scritte_al_posto_giusto():
    """Spec §13. Solo l'aspetto è una differenza ammessa (maglia piccola, azioni di Da fare scritte, lettera del ruolo ed etichetta
    scritta). Nome e slogan in cima e ordine delle sezioni sono contenuto: sulla web non ci sono più e l'ordine è cambiato, l'iPhone
    deve seguire (issue #416), quindi stanno in «Differenze di oggi» con il numero dell'issue, non tra quelle ammesse."""
    doc = (RADICE / "docs" / "COERENZA-WEB-IPHONE.md").read_text(encoding="utf-8")
    ammesse = doc[doc.index("## Differenze ammesse"):doc.index("## Differenze di oggi")]
    riga = next((r for r in ammesse.splitlines() if r.startswith("- **Oggi")), "")
    assert "maglia" in riga and "Da fare" in riga and "lettera grigia del ruolo" in riga, riga
    assert "slogan" not in riga and "ordine" not in riga, riga
    di_oggi = doc[doc.index("## Differenze di oggi"):]
    riga = next((r for r in di_oggi.splitlines() if r.startswith("|") and "slogan" in r), "")
    assert "Oggi" in riga and "#416" in riga and "I tuoi migliori" in riga and "Apri la formazione" in riga, riga
    guida = (RADICE / "docs" / "GUIDA-UTENTE.md").read_text(encoding="utf-8")
    oggi = guida[guida.index("### Oggi"):guida.index("### Formazione")]
    assert "motto" not in oggi and "slogan" not in oggi


def test_novita_di_oggi():
    voce = _voce_di_novita("oggi-distinta.json", "Oggi più ordinata")
    assert voce["voci"] and all("PC" not in v and "cqi" not in v for v in voce["voci"])
    k = re.search(r"font-size: min\(var\(--t-eroe\), (\d+)cqi\)", _corpo(".conto-testo .enorme")).group(1)
    for riga in voce.get("tecnico", []):                         # dopo il rilascio in novita.json può non esserci
        for scritto in re.findall(r"(\d+)cqi", riga):
            assert scritto == k, (scritto, k)                    # la nota tecnica dice il numero vero del CSS
