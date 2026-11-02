"""Sito di presentazione (cartella sito/): link interni, title, description, lingua."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

SITO = Path(__file__).resolve().parent.parent / "sito"
PAGINE = {"index.html": "it", "en/index.html": "en"}


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
        if rel in ("stylesheet", "icon", "manifest", "apple-touch-icon"):
            assert not href.startswith("http"), href
    assert "apps.apple.com" not in testo and "play.google.com" not in testo


def test_jsonld_valido():
    for nome in PAGINE:
        p, _ = leggi(nome)
        dati = json.loads(p.jsonld)
        assert dati["@type"] == "SoftwareApplication"
        assert dati["name"] == "SchieraXI"
        assert "aggregateRating" not in dati and "offers" not in dati


def _peso(f):
    """Byte serviti: il server è Linux e manda i file con a capo semplice, anche se il checkout su Windows li ha con CRLF."""
    return len(f.read_bytes().replace(bytes((13, 10)), bytes((10,))))


def test_pesi_dei_file():
    """Budget: JS < 60 KB in totale, CSS < 60 KB, ogni pagina HTML < 60 KB, nessuna immagine pesante."""
    assert sum(_peso(f) for f in (SITO / "js").glob("*.js")) < 60_000
    assert _peso(SITO / "stile.css") < 60_000
    for nome in PAGINE:
        assert _peso(SITO / nome) < 60_000
    for img in list(SITO.rglob("*.png")) + list(SITO.rglob("*.svg")) + list(SITO.rglob("*.webp")):
        assert img.stat().st_size < 150_000, img


def test_nessuna_risorsa_esterna_nei_file_di_codice():
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    assert "@import" not in css and not re.search(r"url\(\s*['\"]?https?:", css)
    assert "prefers-reduced-motion" in css and "prefers-reduced-data" in css and "light-dark" in css
    for f in (SITO / "js").glob("*.js"):
        testo = f.read_text(encoding="utf-8")
        assert not re.search(r"https?://", testo), f"{f.name}: indirizzo esterno nel codice"
        assert not re.search(r"(fetch|XMLHttpRequest|sendBeacon|WebSocket)\(", testo), f"{f.name}: rete"
        for riga in testo.splitlines():  # innerHTML solo con testo fisso (il guscio del giocatore), mai con dati
            if "innerHTML" in riga:
                assert "${" not in riga and "+" not in riga.split("innerHTML", 1)[1], riga


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
        for ancora in ("#cosa", "#demo", "#come", "#domande", "#fantavoto"):
            assert f'href="{ancora}"' in testo
        assert 'id="demo-app"' in testo and 'role="status"' in testo and "<legend>" in testo


def test_note_legali_e_contatti():
    for nome, nota in (("index.html", "non è affiliato né approvato"), ("en/index.html", "not affiliated with or endorsed")):
        _, testo = leggi(nome)
        assert nota in testo
        assert "contatti@schieraxi.it" in testo
        assert "https://app.schieraxi.it/privacy" in testo and "https://app.schieraxi.it/termini" in testo
        assert "presto" in testo or "soon" in testo


@pytest.mark.skipif(shutil.which("node") is None, reason="serve Node per provare la formula della demo")
def test_formula_della_demo():
    prova = """
    import * as L from %r;
    const out = {};
    for (const m of Object.keys(L.MODULI)) {
      const l = L.migliori(m);
      const ids = L.tutti(l);
      out[m] = { n: ids.length, uniq: new Set(ids).size, modulo: L.trovaModulo(l), t: L.totale(ids),
                 panca: L.panchina(l).length, pos: Object.values(L.posizioni(m)).flat().length };
    }
    out.rosa = L.ROSA.length;
    out.consigliato = L.moduloConsigliato();
    console.log(JSON.stringify(out));
    """ % (SITO / "js" / "logica.js").as_uri()
    r = subprocess.run(["node", "--input-type=module", "-e", prova], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    dati = json.loads(r.stdout)
    assert dati["rosa"] == 16
    for m in ("4-4-2", "3-5-2", "4-3-3"):
        d = dati[m]
        assert d["n"] == 11 and d["uniq"] == 11 and d["modulo"] == m and d["pos"] == 11 and d["panca"] == 5
        assert 40 < d["t"] < 90
    # il modulo consigliato è quello con più punti attesi
    assert dati[dati["consigliato"]]["t"] == max(dati[m]["t"] for m in ("4-4-2", "3-5-2", "4-3-3"))


# ---- contenuti: scopo e informazioni, non struttura dell'app ----
@pytest.mark.parametrize("nome", PAGINE)
def test_niente_descrizione_delle_schede_e_niente_cursore(nome):
    p, testo = leggi(nome)
    assert "schede" not in p.ids
    for vietato in ("Quattro schede", "Four tabs", "Oggi, Formazione", "Today, Lineup", 'class="carta r', 'class="carte', "cursore"):
        assert vietato not in testo, vietato
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    assert "cursore" not in css
    for f in (SITO / "js").glob("*.js"):
        assert "cursore" not in f.read_text(encoding="utf-8"), f.name


@pytest.mark.parametrize("nome", PAGINE)
def test_poche_sezioni_essenziali_in_ordine(nome):
    """Meno ma meglio: prima schermata, cosa fa, fantavoto atteso, demo, come iniziare, domande (al massimo 5)."""
    p, testo = leggi(nome)
    main = testo.split('<main id="principale">', 1)[1].split("</main>", 1)[0]
    assert re.findall(r'<section[^>]*\sid="([^"]+)"', main) == ["eroe", "cosa", "fantavoto", "demo", "come", "domande"]
    assert len(re.findall(r'<li class="r">', main.split('id="cosa"')[1].split("</section>")[0])) == 3
    assert len(re.findall(r'<li class="r">', main.split('id="come"')[1].split("</section>")[0])) == 3
    domande = main.split('id="domande"')[1]
    assert 1 <= domande.count("<details>") <= 5
    for i in ("demo-campo", "d-dett", "d-tot", "d-conf", "d-reset", "fv-es", "guida-iphone", "scarica"):
        assert i in p.ids, i
    # via le cose secondarie: schede di lato, contatori, confronti, scambi tra squadre, giornate e stili
    for vecchio in ("carta-lato", "data-conta", "storia-campo", 'name="giornata"', 'name="stile"', 'id="scambio"', "barra-cta", "avanzamento", "blob", "data-tilt", "data-magnete"):
        assert vecchio not in testo, vecchio


def test_niente_che_si_muove_di_continuo():
    """Ogni movimento parte una volta (all'apertura, allo scorrimento o a un tocco): niente animazioni infinite né timer."""
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    assert "infinite" not in css and "animation-timeline" not in css
    for f in (SITO / "js").glob("*.js"):
        assert "setInterval" not in f.read_text(encoding="utf-8"), f.name
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_gioco_di_parole_del_nome():
    for nome, aria, slogan, _pron in (
        ("index.html", "SchieraXI, schiera undici", "Schierali. Schiera gli <span", None),
        ("en/index.html", "SchieraXI, line up eleven", "Line them up. Line up the <span", None),
    ):
        p, testo = leggi(nome)
        assert f'aria-label="{aria}"' in testo and 'class="nome-gioco"' in testo
        assert slogan in testo and not re.search(r"(?i)schièra|OON-dee|si legge schi|is read |pronounc", testo)
        assert "SchieraXI" in p.meta["og:image:alt"]
        # nome disegnato in tracciati (nessun font da scaricare): apertura «Schierali» -> «SchieraXI»
        assert "wm-hero" in testo and "wm-L" in testo and "wm-X1" in testo and "wm-X2" in testo
        assert "wm-I" in testo and "wm-Id" in testo
        assert testo.count('<symbol id="wm') == 2 and 'href="#wm-c"' in testo
        assert "<text" not in testo and "stroke" not in re.search(r'<svg class="sprite".*?</svg>', testo, re.S).group(0)


def test_nome_disegnato_con_font_libero():
    """Il nome viene da Archivo (SIL OFL 1.1): font, licenza e generatore stanno in assets/marchio/wordmark/."""
    cartella = SITO.parent / "assets" / "marchio" / "wordmark"
    assert "SIL Open Font License" in (cartella / "OFL.txt").read_text(encoding="utf-8")
    assert (cartella / "Archivo-sottoinsieme.ttf").is_file() and (cartella / "genera.py").is_file()
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    assert "@font-face" not in css  # niente font scaricati dal sito: solo tracciati
    for nome in ("index.html", "en/index.html", "404.html", "offline.html"):
        testo = (SITO / nome).read_text(encoding="utf-8")
        sprite = re.search(r'<svg class="sprite".*?</svg>', testo, re.S).group(0)
        # due versioni: #wm grande (I con il taglio) e #wm-c compatta (I piena), stesso riquadro
        caselle = re.findall(r'<symbol id="(wm(?:-c)?)" viewBox="([^"]+)"', sprite)
        assert [c[0] for c in caselle] == ["wm", "wm-c"] and caselle[0][1] == caselle[1][1]
        # le misure piccole (barra in alto, piè di pagina) usano la versione compatta
        assert not re.search(r'class="wm-svg wm-(bar|pie)"[^>]*>\s*<use href="#wm"', testo)


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
    for s in m["shortcuts"]:
        assert s["url"].startswith(scope) and s["name"]


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
    for nome in PAGINE:
        assert _ids_output_animati(leggi(nome)[1])


def _ids_output_animati(testo):
    """Gli output che si animano non devono annunciare ogni cifra."""
    return all('aria-live="off"' in t for t in re.findall(r"<output[^>]*>", testo))


# ---- demo: modulo e cambi ----
@pytest.mark.skipif(shutil.which("node") is None, reason="serve Node")
def test_demo_panchina_in_ordine_e_dubbi_fuori():
    prova = """
    import * as L from %r;
    const m = L.moduloConsigliato();
    const l = L.migliori(m);
    const panca = L.panchina(l).map((id) => L.atteso(L.ROSA.find((g) => g.id === id)));
    console.log(JSON.stringify({ m, titolari: L.tutti(l), panca }));
    """ % (SITO / "js" / "logica.js").as_uri()
    r = subprocess.run(["node", "--input-type=module", "-e", prova], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["m"] in ("4-4-2", "3-5-2", "4-3-3")
    assert d["panca"] == sorted(d["panca"], reverse=True), "la panchina va in ordine di punti attesi"
    assert "pernoli" not in d["titolari"], "un 7,9 che gioca col 55% vale meno di un 6,7 sicuro"


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



def test_tipografia_con_tetto_per_gli_schermi_larghi():
    """Su un monitor ultra-wide il sito non deve «zoomare»: carattere base 16-18 px, titolo massimo ~58 px, contenitore con un tetto."""
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    html = re.search(r"\nhtml \{[^}]*\}", css).group(0)
    m = re.search(r"font-size: clamp\(([\d.]+)rem, [^,]+, ([\d.]+)rem\)", html)
    assert m, "il carattere base deve avere un tetto"
    assert float(m.group(1)) == 1 and float(m.group(2)) <= 1.125
    h1 = re.search(r"\nh1 \{ font-size: clamp\(([\d.]+)rem, [^,]+, ([\d.]+)rem\)", css)
    assert h1 and float(h1.group(2)) <= 3.3
    assert float(re.search(r"--max: ([\d.]+)rem", css).group(1)) <= 90
    # ogni dimensione di carattere che usa vw ha un tetto (clamp o min)
    for riga in css.splitlines():
        for fs in re.findall(r"font-size: ([^;}]*vw[^;}]*)", riga):
            assert fs.strip().startswith(("clamp(", "min(")), fs
    # oltre i 1700 px le decorazioni laterali riempiono ciò che il contenitore lascia libero
    assert "@media (min-width: 1700px)" in css and "body::before" in css


@pytest.mark.parametrize("nome", PAGINE)
def test_fantavoto_atteso_in_evidenza(nome):
    """La prima schermata nomina il fantavoto atteso; la sezione dedicata mostra «fantavoto atteso se gioca» con accanto la probabilità di giocare."""
    _, testo = leggi(nome)
    eroe = testo.split('id="eroe"', 1)[1].split("</section>", 1)[0]
    assert ("<strong>fantavoto atteso</strong>" if nome == "index.html" else "<strong>expected rating</strong>") in eroe
    assert eroe.count('class="pt') == 14 and 'class="pt cap' in eroe
    frase = "Fantavoto atteso se gioca" if nome == "index.html" else "Expected rating if he plays"
    assert frase in testo
    for classe in ('class="fv-pg"', 'id="fv-num"', 'class="fv-es'):
        assert classe in testo, classe
    assert re.search(r'<a href="#fantavoto">', testo), "il menu porta alla sezione del fantavoto"


def test_menu_senza_voce_corrente_in_cima():
    """Tornando in cima alla pagina il menu non deve restare evidenziato sull'ultima sezione vista."""
    js = (SITO / "js" / "effetti.js").read_text(encoding="utf-8")
    assert "getElementById('eroe')" in js and "io.observe(eroe)" in js


def test_testata_senza_voci_su_due_righe():
    """Fra 900 e 1150 px il menu, il nome e i pulsanti stanno su una riga: voci mai spezzate,
    «Apri la web app» nella barra solo da 72rem, «Installa» solo icona finché manca spazio."""
    css = (SITO / "stile.css").read_text(encoding="utf-8")
    regola_menu = re.search(r"\.menu a \{[^}]*\}", css).group(0)
    assert "white-space: nowrap" in regola_menu
    assert re.search(r"@media \(min-width: 72rem\) \{ body\.dopo-eroe \.tasto\.tasto-cab \{ display: inline-flex; \} \}", css)
    assert not re.search(r"@media \(min-width: 56rem\) \{ body\.dopo-eroe \.tasto\.tasto-cab", css)
    assert re.search(r"@media \(max-width: 84\.99rem\) \{\s*#installa \{", css)
