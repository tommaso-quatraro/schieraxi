"""Sito di presentazione (cartella sito/): link interni, title, description, lingua, contenuti e grafica sobria.

Dal 5/11/2026 (#355) il sito è formale e diretto, con la grafica «direzione B» della web app: nome una volta, titolo
«La formazione consigliata», un esempio di campo con nomi inventati, «Come funziona» con un esempio di calcolo, domande.
Niente slogan, demo, gradienti, ombre o carte dentro carte. Archivo (SIL OFL 1.1) è servito dai file del sito.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

SITO = Path(__file__).resolve().parent.parent / "sito"
PAGINE = {"index.html": "it", "en/index.html": "en"}
SEZIONI = ["eroe", "come", "iniziare", "domande"]
MENU = ("#come", "#iniziare", "#domande")
FONT = SITO / "font" / "archivo-semistretto.woff2"


class Lettore(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.title = ""
        self._in_title = False
        self.meta = {}
        self.h1 = 0
        self.ids = set()
        self.link = []      # (rel, href, hreflang)
        self.rif = []       # href/src dei tag a, link, img, script
        self.img_senza_alt = 0
        self.script_src = []
        self.jsonld = ""
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            k = a.get("name") or a.get("property")
            if k:
                self.meta[k] = a.get("content", "")
        if tag == "h1":
            self.h1 += 1
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "link":
            self.link.append((a.get("rel"), a.get("href"), a.get("hreflang")))
            if a.get("href"):
                self.rif.append(a["href"])
        if tag == "a" and a.get("href"):
            self.rif.append(a["href"])
        if tag == "img":
            if a.get("alt") is None:
                self.img_senza_alt += 1
            if a.get("src"):
                self.rif.append(a["src"])
        if tag == "script":
            if a.get("src"):
                self.script_src.append(a["src"])
                self.rif.append(a["src"])
            if a.get("type") == "application/ld+json":
                self._in_ld = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self.jsonld += data


def leggi(nome):
    testo = (SITO / nome).read_text(encoding="utf-8")
    p = Lettore()
    p.feed(testo)
    return p, testo


def css():
    return (SITO / "stile.css").read_text(encoding="utf-8")


def principale(testo):
    return testo.split('<main id="principale">', 1)[1].split("</main>", 1)[0]


def sezione(testo, ident):
    return principale(testo).split(f'id="{ident}"', 1)[1].split("</section>", 1)[0]


def senza_tag(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def numero(s):
    """«+0,4» -> 0.4, «7.6» -> 7.6, «90%» -> 0.9 (italiano con la virgola, inglese con il punto)."""
    s = senza_tag(s).replace("×", "").replace("−", "-").replace(",", ".").replace(" ", "")
    return float(s[:-1]) / 100 if s.endswith("%") else float(s)


def risolvi(rif, pagina):
    """Percorso del file a cui punta un link interno (None se esterno)."""
    if re.match(r"^(https?:|mailto:|tel:)", rif):
        return None
    path = rif.split("#")[0].split("?")[0]
    if not path:
        return SITO / pagina
    base = SITO if path.startswith("/") else (SITO / pagina).parent
    dest = base / path.lstrip("/")
    return dest / "index.html" if (path.endswith("/") or dest.is_dir()) else dest


@pytest.mark.parametrize("nome,lingua", PAGINE.items())
def test_lingua_title_description(nome, lingua):
    p, _ = leggi(nome)
    assert p.lang == lingua
    assert 10 < len(p.title.strip()) <= 70
    assert 50 < len(p.meta.get("description", "")) <= 170
    assert p.h1 == 1
    assert p.meta.get("og:title") and p.meta.get("og:image")
    assert p.img_senza_alt == 0
    assert p.script_src == ["/js/tema.js", "/js/principale.js"]


def test_titolo_italiano_richiesto():
    p, _ = leggi("index.html")
    assert p.title.strip() == "SchieraXI – consigli formazione fantacalcio"


@pytest.mark.parametrize("nome", PAGINE)
def test_link_interni_non_rotti(nome):
    p, _ = leggi(nome)
    for rif in p.rif:
        dest = risolvi(rif, nome)
        if dest is None:
            continue
        assert dest.exists(), f"{nome}: link rotto {rif}"
        if "#" in rif and dest.suffix == ".html":
            ancora = rif.split("#")[1]
            altro, _ = leggi(dest.relative_to(SITO).as_posix())
            assert ancora in altro.ids, f"{nome}: ancora mancante {rif}"


@pytest.mark.parametrize("nome", PAGINE)
def test_hreflang_reciproco(nome):
    p, _ = leggi(nome)
    alt = {h: href for rel, href, h in p.link if rel == "alternate" and h}
    assert alt["it"] == "https://schieraxi.it/"
    assert alt["en"] == "https://schieraxi.it/en/"
    assert alt["x-default"] == "https://schieraxi.it/"


@pytest.mark.parametrize("nome", PAGINE)
def test_nessuna_risorsa_esterna_e_niente_store(nome):
    p, testo = leggi(nome)
    for rel, href, _ in p.link:
        if rel in ("stylesheet", "icon", "manifest", "apple-touch-icon", "preload"):
            assert not href.startswith("http"), href
    assert "apps.apple.com" not in testo and "play.google.com" not in testo


def test_jsonld_valido():
    for nome in PAGINE:
        p, _ = leggi(nome)
        dati = json.loads(p.jsonld)
        assert dati["@type"] == "SoftwareApplication"
        assert dati["name"] == "SchieraXI"
        assert "aggregateRating" not in dati and "offers" not in dati
        # l'app per iPhone non è ancora disponibile: oggi c'è solo la web app
        assert dati["operatingSystem"] == "Web"


def _peso(f):
    """Byte serviti: il server è Linux e manda i file con a capo semplice, anche se il checkout su Windows li ha con CRLF."""
    return len(f.read_bytes().replace(bytes((13, 10)), bytes((10,))))


def test_pesi_dei_file():
    """Budget: JS < 60 KB in totale, CSS < 60 KB, ogni pagina HTML < 60 KB, nessuna immagine pesante, il font < 40 KB."""
    assert sum(_peso(f) for f in (SITO / "js").glob("*.js")) < 60_000
    assert _peso(SITO / "stile.css") < 60_000
    for nome in PAGINE:
        assert _peso(SITO / nome) < 60_000
    for img in list(SITO.rglob("*.png")) + list(SITO.rglob("*.svg")) + list(SITO.rglob("*.webp")):
        assert img.stat().st_size < 150_000, img
    assert FONT.stat().st_size < 40_000


def test_nessuna_risorsa_esterna_nei_file_di_codice():
    c = css()
    assert "@import" not in c and not re.search(r"url\(\s*['\"]?https?:", c)
    assert "prefers-reduced-motion" in c and "light-dark" in c
    for f in (SITO / "js").glob("*.js"):
        testo = f.read_text(encoding="utf-8")
        assert not re.search(r"https?://", testo), f"{f.name}: indirizzo esterno nel codice"
        assert not re.search(r"(fetch|XMLHttpRequest|sendBeacon|WebSocket)\(", testo), f"{f.name}: rete"
        assert "innerHTML" not in testo, f"{f.name}: innerHTML"


def test_import_dei_moduli_esistono():
    for f in (SITO / "js").glob("*.js"):
        for rif in re.findall(r"""(?:from\s+|import\()['"](\./[^'"]+)['"]""", f.read_text(encoding="utf-8")):
            assert (f.parent / rif).exists(), f"{f.name}: {rif}"


def test_pagine_con_la_stessa_struttura():
    it, _ = leggi("index.html")
    en, _ = leggi("en/index.html")
    assert it.ids == en.ids
    for nome in PAGINE:
        _, testo = leggi(nome)
        menu = re.search(r'<nav class="menu".*?</nav>', testo, re.S).group(0)
        assert re.findall(r'href="(#[^"]+)"', menu) == list(MENU)


def test_note_legali_e_contatti():
    for nome, nota in (("index.html", "non è affiliato né approvato"), ("en/index.html", "not affiliated with or endorsed")):
        _, testo = leggi(nome)
        assert nota in testo
        assert "contatti@schieraxi.it" in testo
        assert "https://app.schieraxi.it/privacy" in testo and "https://app.schieraxi.it/termini" in testo
        assert "AGPL-3.0" in testo


@pytest.mark.parametrize("nome,stati", [
    ("index.html", ("Disponibile su invito", "In arrivo", "In programma")),
    ("en/index.html", ("Available by invitation", "Coming", "Planned")),
])
def test_stato_reale_delle_app(nome, stati):
    """Web app su invito, iPhone in arrivo, Android in programma: niente promesse («presto», «soon») e niente SideStore."""
    _, testo = leggi(nome)
    dove = sezione(testo, "iniziare")
    righe = re.findall(r"<tr[^>]*>(.*?)</tr>", dove, re.S)
    assert [senza_tag(re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)[0]) for r in righe] == list(stati)
    m = principale(testo).lower()
    for vietato in ("presto", "soon", "sidestore", "testflight"):
        assert vietato not in m, vietato
    assert "invit" in senza_tag(sezione(testo, "eroe")).lower()


@pytest.mark.parametrize("nome", PAGINE)
def test_niente_descrizione_delle_schede_e_niente_cursore(nome):
    p, testo = leggi(nome)
    assert "schede" not in p.ids
    for vietato in ("Quattro schede", "Four tabs", "Oggi, Formazione", "Today, Lineup", 'class="carta r', 'class="carte', "cursore"):
        assert vietato not in testo, vietato
    assert "cursore" not in css()
    for f in (SITO / "js").glob("*.js"):
        assert "cursore" not in f.read_text(encoding="utf-8"), f.name


@pytest.mark.parametrize("nome", PAGINE)
def test_poche_sezioni_essenziali_in_ordine(nome):
    """Prima schermata, come funziona, per iniziare, domande (al massimo 5). Via slogan, demo e colonne «features»."""
    p, testo = leggi(nome)
    main = principale(testo)
    assert re.findall(r'<section[^>]*\sid="([^"]+)"', main) == SEZIONI
    assert len(re.findall(r"<li>", sezione(testo, "iniziare").split("</ol>")[0])) == 3
    assert 1 <= sezione(testo, "domande").count("<details>") <= 5
    for vecchio in ("nome-gioco", "slogan", "Schierali", "Line them up", 'id="demo', "demo-campo", "fv-es", 'class="tre"',
                    "data-sfalsa", 'class="r"', "Prova la demo", "Try the demo", "sez-alt", "<strong>"):
        assert vecchio not in testo, vecchio
    assert "sidestore" not in testo.lower() and 'id="guida-iphone"' not in testo
    # file della demo e degli effetti tolti
    for f in ("demo.js", "logica.js", "effetti.js"):
        assert not (SITO / "js" / f).exists(), f


@pytest.mark.parametrize("nome,titolo", [("index.html", "La formazione consigliata"), ("en/index.html", "The recommended lineup")])
def test_prima_schermata_diretta(nome, titolo):
    """Titolo di un colore solo, una frase su cosa fa, un pulsante per la web app, il link a «Come funziona»."""
    _, testo = leggi(nome)
    eroe = sezione(testo, "eroe")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", eroe, re.S).group(1)
    assert h1 == titolo  # niente span colorati dentro il titolo
    frase = re.search(r'<p class="intro">(.*?)</p>', eroe, re.S).group(1)
    assert ("fantavoto atteso" if nome == "index.html" else "expected fantasy score") in frase
    assert len(frase.split()) <= 32
    assert eroe.count('href="https://app.schieraxi.it"') == 1 and 'href="#come"' in eroe


@pytest.mark.parametrize("nome", PAGINE)
def test_nome_una_volta(nome):
    """Il nome si vede una volta, in cima: niente nome grande, niente nome nel piè di pagina, niente nome nel testo."""
    _, testo = leggi(nome)
    assert testo.count('href="#wm-c"') == 1 and 'href="#wm"' not in testo
    assert re.search(r'<header class="alto">.*?href="#wm-c".*?</header>', testo, re.S)
    assert "SchieraXI" not in senza_tag(principale(testo))
    assert "wm-pie" not in testo and "wm-hero" not in testo


def test_niente_che_si_muove_di_continuo():
    """Nessuna animazione infinita né timer; il sito non ha più entrate animate."""
    c = css()
    assert "infinite" not in c and "animation-timeline" not in c and "@keyframes" not in c
    for f in (SITO / "js").glob("*.js"):
        testo = f.read_text(encoding="utf-8")
        assert "setInterval" not in testo, f.name
    assert "@media (prefers-reduced-motion: reduce)" in c


def test_niente_decorazioni_da_pagina_generata():
    """docs/STILE-SENZA-AI.md: niente gradienti, ombre, sfocature, maiuscole spaziate, frecce nel testo, emoji."""
    c = css()
    for vietato in ("gradient(", "box-shadow", "text-shadow", "drop-shadow", "backdrop-filter", "text-transform: uppercase",
                    "transition: all", "body::before"):
        assert vietato not in c, vietato
    assert not re.search(r"letter-spacing: *\.(0[6-9]|[1-9])", c), "lettere spaziate"
    for nome in list(PAGINE) + ["404.html", "offline.html"]:
        testo = (SITO / nome).read_text(encoding="utf-8")
        for segno in ("→", "←", "✨", "class=\"xi\""):
            assert segno not in testo, (nome, segno)


def _token(nome_var, testo_css):
    m = re.search(rf"--{nome_var}: light-dark\((#[0-9a-fA-F]{{6}}), (#[0-9a-fA-F]{{6}})\)", testo_css)
    assert m, f"--{nome_var} deve avere il valore chiaro e scuro"
    return m.group(1), m.group(2)


def _contrasto(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.mark.parametrize("lato", [0, 1], ids=["chiaro", "scuro"])
def test_contrasti_wcag_aa(lato):
    """Testo e link almeno 4,5:1 sul fondo, in chiaro e in scuro; i nomi bianchi sul campo anche."""
    c = css()
    t = {k: _token(k, c)[lato] for k in ("fondo", "sup", "testo", "sec", "azione", "azione-t", "campo", "campo-t", "disco", "disco-t")}
    for testo, fondo in (("testo", "fondo"), ("sec", "fondo"), ("azione", "fondo"), ("testo", "sup"), ("sec", "sup"),
                         ("azione-t", "azione"), ("campo-t", "campo"), ("disco-t", "disco")):
        assert _contrasto(t[testo], t[fondo]) >= 4.5, (testo, fondo, t[testo], t[fondo])


def test_direzione_b_colori_e_caratteri():
    """Stessi colori e caratteri della direzione B della web app (#354): fondo bianco o quasi nero, verde azione, Archivo."""
    c = css()
    assert _token("fondo", c) == ("#ffffff", "#121513")
    assert _token("testo", c) == ("#10201a", "#e9edea")
    assert _token("azione", c) == ("#0b6b3a", "#4cc98a")
    assert re.search(r'--fn: "Archivo", ', c)
    for nome in PAGINE:
        _, testo = leggi(nome)
        assert re.findall(r'name="theme-color" media="[^"]+" content="([^"]+)"', testo) == ["#ffffff", "#121513"]


def test_archivo_servito_dai_file_del_sito():
    """Archivo (SIL OFL 1.1) sta in sito/font/ con la licenza accanto: nessun font da servizi esterni."""
    assert FONT.read_bytes()[:4] == b"wOF2"
    licenza = (SITO / "font" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in licenza and "Archivo Project Authors" in licenza
    c = css()
    facce = re.findall(r"@font-face \{(.*?)\}", c, re.S)
    assert len(facce) == 1
    f = facce[0]
    assert 'font-family: "Archivo"' in f and 'url("/font/archivo-semistretto.woff2") format("woff2")' in f
    assert "font-display: swap" in f and "unicode-range" in f
    for nome in PAGINE:
        _, testo = leggi(nome)
        assert '<link rel="preload" href="/font/archivo-semistretto.woff2" as="font" type="font/woff2" crossorigin>' in testo
    sw = (SITO / "sw.js").read_text(encoding="utf-8")
    assert "'/font/archivo-semistretto.woff2'" in sw


def test_nome_disegnato_con_font_libero():
    """Il nome viene da Archivo (SIL OFL 1.1): font, licenza e generatore stanno in assets/marchio/wordmark/."""
    cartella = SITO.parent / "assets" / "marchio" / "wordmark"
    assert "SIL Open Font License" in (cartella / "OFL.txt").read_text(encoding="utf-8")
    assert (cartella / "Archivo-sottoinsieme.ttf").is_file() and (cartella / "genera.py").is_file()
    for nome in ("index.html", "en/index.html", "404.html", "offline.html"):
        testo = (SITO / nome).read_text(encoding="utf-8")
        sprite = re.search(r'<svg class="sprite".*?</svg>', testo, re.S).group(0)
        # due versioni (le riscrive genera.py --sito): #wm grande e #wm-c compatta, stesso riquadro
        caselle = re.findall(r'<symbol id="(wm(?:-c)?)" viewBox="([^"]+)"', sprite)
        assert [c[0] for c in caselle] == ["wm", "wm-c"] and caselle[0][1] == caselle[1][1]
        assert "<text" not in testo and "stroke" not in sprite
        # le misure piccole (barra in alto) usano la versione compatta
        assert not re.search(r'class="wm-svg wm-bar"[^>]*>\s*<use href="#wm"', testo)


# ---- esempi: campo e calcolo con nomi e numeri inventati, che tornano ----
def _campo(testo):
    eroe = sezione(testo, "eroe")
    linee = re.findall(r'<ul class="linea"[^>]*>(.*?)</ul>', eroe, re.S)
    giocatori = [re.findall(r'<li class="pedina"><span class="nm">([^<]+)</span><span class="disco n">([^<]+)</span></li>', l) for l in linee]
    panca = re.search(r'<table class="panca".*?<tbody>(.*?)</tbody>', eroe, re.S).group(1)
    righe = re.findall(r'<tr><th scope="row"><span class="ord n">(\d)</span> ([^<]+)</th><td class="p n">([^<]+)</td><td class="fv n">([^<]+)</td></tr>', panca)
    return eroe, giocatori, righe


@pytest.mark.parametrize("nome", PAGINE)
def test_esempio_di_campo(nome):
    """4-3-3 dall'attacco al portiere, panchina in ordine di punti attesi (fantavoto per probabilità di giocare)."""
    _, testo = leggi(nome)
    eroe, giocatori, panca = _campo(testo)
    assert [len(l) for l in giocatori] == [3, 3, 4, 1]
    assert re.search(r'<dd class="n">4-3-3</dd>', eroe)
    assert len(panca) == 3 and [int(r[0]) for r in panca] == [1, 2, 3]
    attesi = [numero(r[2]) * numero(r[3]) for r in panca]
    assert attesi == sorted(attesi, reverse=True)
    for l in giocatori:
        for _, fv in l:
            assert 4 <= numero(fv) <= 10


@pytest.mark.parametrize("nome", PAGINE)
def test_esempio_di_calcolo_torna(nome):
    """Base + voci = fantavoto atteso; fantavoto × probabilità di giocare = punti attesi; lo stesso giocatore è sul campo."""
    _, testo = leggi(nome)
    tab = re.search(r'<table class="calcolo".*?</table>', sezione(testo, "come"), re.S).group(0)
    caption = senza_tag(re.search(r"<caption>(.*?)</caption>", tab, re.S).group(1))
    valori = [numero(v) for v in re.findall(r'<td class="n">(.*?)</td>', tab, re.S)]
    somme = re.findall(r'<tr class="somma">', tab)
    assert len(valori) == 8 and len(somme) == 2
    base, voci, fv, p, punti = valori[0], valori[1:5], valori[5], valori[6], valori[7]
    assert round(base + sum(voci), 1) == fv
    assert round(fv * p, 1) == punti
    _, giocatori, _ = _campo(testo)
    sul_campo = {n: numero(v) for l in giocatori for n, v in l}
    chi = caption.split(":", 1)[1].split(",")[0].strip()
    assert sul_campo[chi] == fv


def test_italiano_e_inglese_allineati():
    """Stessi id, stessi numeri (con la virgola o con il punto), stesse domande, stessi nomi inventati."""
    it, t_it = leggi("index.html")
    en, t_en = leggi("en/index.html")
    assert it.ids == en.ids

    def numeri(t):
        return re.findall(r"\d+(?:[.,]\d+)?", senza_tag(principale(t)).replace(",", "."))
    assert numeri(t_it) == numeri(t_en)
    assert sezione(t_it, "domande").count("<details>") == sezione(t_en, "domande").count("<details>")
    assert _campo(t_it)[1] == [[(n, v.replace(".", ",")) for n, v in l] for l in _campo(t_en)[1]]


# ---- app installabile ----
def _png_dim(path):
    d = path.read_bytes()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(d[16:20], "big"), int.from_bytes(d[20:24], "big")


@pytest.mark.parametrize("nome,lang,scope", [("manifest.webmanifest", "it", "/"), ("en/manifest.webmanifest", "en", "/en/")])
def test_manifest_completo(nome, lang, scope):
    m = json.loads((SITO / nome).read_text(encoding="utf-8"))
    for k in ("name", "short_name", "id", "start_url", "scope", "display", "background_color", "theme_color", "icons", "screenshots", "shortcuts", "lang"):
        assert m.get(k), k
    assert m["lang"] == lang and m["display"] == "standalone" and m["scope"] == scope
    assert m["id"].startswith(scope) and m["start_url"].startswith(scope)
    assert m["theme_color"].startswith("#") and m["background_color"].startswith("#")
    scopi = {(i["sizes"], i.get("purpose", "any")) for i in m["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("192x192", "maskable"), ("512x512", "maskable")} <= scopi
    for i in m["icons"]:
        w, h = _png_dim(SITO / i["src"].lstrip("/"))
        assert f"{w}x{h}" == i["sizes"], i["src"]
    assert {s["form_factor"] for s in m["screenshots"]} == {"wide", "narrow"}
    for s in m["screenshots"]:
        w, h = _png_dim(SITO / s["src"].lstrip("/"))
        assert f"{w}x{h}" == s["sizes"] and s["label"]
    pagina = leggi("index.html" if lang == "it" else "en/index.html")[0]
    for s in m["shortcuts"]:
        assert s["url"].startswith(scope) and s["name"]
        assert s["url"].split("#")[1] in pagina.ids
    # niente slogan né demo
    testo = json.dumps(m, ensure_ascii=False)
    for vietato in ("Schierali", "Line them up", "demo", "Demo"):
        assert vietato not in testo, vietato


def test_pagine_puntano_al_loro_manifest():
    assert 'rel="manifest" href="/manifest.webmanifest"' in leggi("index.html")[1]
    assert 'rel="manifest" href="/en/manifest.webmanifest"' in leggi("en/index.html")[1]
    for nome in PAGINE:
        t = leggi(nome)[1]
        assert t.count('name="theme-color"') == 2 and "prefers-color-scheme: dark" in t
        assert "viewport-fit=cover" in t and 'id="installa"' in t and 'id="ios-hint"' in t and 'id="indietro"' in t


def test_service_worker():
    sw = (SITO / "sw.js").read_text(encoding="utf-8")
    assert not re.search(r"https?://", sw)
    assert "skipWaiting" in sw and "clients.claim" in sw and "no-cache" in sw and "offline.html" in sw
    pre = re.search(r"PRECACHE = \[(.*?)\];", sw, re.S).group(1)
    percorsi = re.findall(r"'(/[^']*)'", pre)
    assert "/offline.html" in percorsi and "/js/installa.js" in percorsi
    for r in percorsi:
        assert risolvi(r, "index.html").exists(), r
    for f in (SITO / "js").glob("*.js"):
        assert f"'/js/{f.name}'" in pre, f.name
    assert "serviceWorker" in (SITO / "js" / "installa.js").read_text(encoding="utf-8")


def test_sw_chiave_senza_query_e_pagine_di_servizio_bilingui():
    sw = (SITO / "sw.js").read_text(encoding="utf-8")
    assert "url.origin + url.pathname" in sw and "ignoreSearch" not in sw
    assert "cache: 'no-cache'" in sw
    for nome in ("404.html", "offline.html"):
        t = (SITO / nome).read_text(encoding="utf-8")
        assert 'lang="en"' in t and 'class="cont ' in t and "contenuto" not in t, nome


@pytest.mark.parametrize("nome", ["index.html", "en/index.html", "404.html", "offline.html"])
def test_pronto_per_csp_stretta(nome):
    """Niente style=, niente script o stili dentro la pagina: la CSP può restare senza unsafe-inline."""
    html = (SITO / nome).read_text(encoding="utf-8")
    assert not re.search(r"<[a-zA-Z][^>]*\sstyle\s*=", html), f"{nome}: attributo style"
    assert "<style" not in html
    for m in re.finditer(r"<script([^>]*)>", html):
        attr = m.group(1)
        assert "src=" in attr or "application/ld+json" in attr, f"{nome}: script dentro la pagina"
    assert not re.search(r"\son[a-z]+\s*=\s*[\"']", html), f"{nome}: gestore di evento nell HTML"


@pytest.mark.parametrize("nome", ["index.html", "en/index.html"])
def test_anteprima_social_con_immagine(nome):
    p, _ = leggi(nome)
    assert p.meta.get("twitter:card") == "summary_large_image"
    assert p.meta.get("twitter:image") == p.meta.get("og:image")
    for k in ("description", "og:description"):
        assert "Schierali" not in p.meta[k] and "Line them up" not in p.meta[k]


def test_tipografia_con_tetto_per_gli_schermi_larghi():
    """Su un monitor ultra-wide il sito non deve «zoomare»: carattere base 16-18 px, titolo massimo ~52 px, contenitore con un tetto."""
    c = css()
    html = re.search(r"\nhtml \{[^}]*\}", c).group(0)
    m = re.search(r"font-size: clamp\(([\d.]+)rem, [^,]+, ([\d.]+)rem\)", html)
    assert m, "il carattere base deve avere un tetto"
    assert float(m.group(1)) == 1 and float(m.group(2)) <= 1.125
    h1 = re.search(r"\nh1 \{ font-size: clamp\(([\d.]+)rem, [^,]+, ([\d.]+)rem\)", c)
    assert h1 and float(h1.group(2)) <= 3.3
    assert float(re.search(r"--max: ([\d.]+)rem", c).group(1)) <= 90
    # ogni dimensione di carattere che usa vw ha un tetto (clamp o min)
    for riga in c.splitlines():
        for fs in re.findall(r"font-size: ([^;}]*vw[^;}]*)", riga):
            assert fs.strip().startswith(("clamp(", "min(")), fs


def test_testata_senza_voci_su_due_righe():
    """Il menu compare quando ci sta su una riga; «Apri la web app» nella barra quando c'è posto accanto al nome."""
    c = css()
    regola_menu = re.search(r"\.menu a \{[^}]*\}", c).group(0)
    assert "white-space: nowrap" in regola_menu
    assert re.search(r"@media \(min-width: 60rem\) \{ \.menu \{ display: flex; \} \}", c)
    assert re.search(r"@media \(min-width: 40rem\) \{ \.tasto-cab \{ display: inline-flex;", c)
    # la testata resta in cima, piena e con un filo sotto: niente vetro sfocato
    alto = re.search(r"\.alto \{[^}]*\}", c).group(0)
    assert "position: sticky" in alto and "border-bottom: 1px solid var(--linea)" in alto and "background: var(--fondo)" in alto
