"""Grafica B della web (spec docs/superpowers/specs/2026-11-05-grafica-web-b-design.md): controlli sul codice."""
import json
import re
import shutil
import subprocess
from pathlib import Path

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
    assert 'testata.giornata", { n: ' in APP and "_lega" in APP[APP.index('testata.giornata", { n: '):][:120]
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


def test_novita_della_testata():
    voce = json.loads(Path(RADICE / "fanta" / "novita.d" / "testata-schede.json").read_text(encoding="utf-8"))
    assert voce["titolo"] and len(voce["voci"]) >= 2


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


def test_piu_etichette_nella_stessa_riga_separate_dal_punto():
    """Spec §8.9: senza la pillola, due etichette vicine («Real Esempio · In ballottaggio») si separano con « · ». Il punto sta in fondo
    all'etichetta prima, attaccato con uno spazio che non va a capo (come i pezzi di un'etichetta lunga), è grigio e i lettori di
    schermo non lo leggono (testo alternativo vuoto)."""
    punto = _corpo(".etichette > .etichetta:not(:last-child)::after")
    assert 'content: "\\a0·" / ""' in punto and "color: var(--testo-2)" in punto
