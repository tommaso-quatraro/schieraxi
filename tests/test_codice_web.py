"""Il lettore unico del codice della web (tests/codice_web.py): oggi dà esattamente il testo dei file, domani unisce anche i
moduli di `fanta/web/moduli/` (ondata 2, lavoro B0). E nessun altro test legge da solo i file `.js` di `fanta/web/`."""
import re
from pathlib import Path

import pytest

import codice_web

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "fanta" / "web"
TESTS = RADICE / "tests"


def _scrivi(cartella: Path, nome: str, testo: str) -> Path:
    p = cartella / nome
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(testo, encoding="utf-8")
    return p


# ------------------------------------------------------------------------------------------------- oggi: lo stesso testo
def test_oggi_app_e_il_testo_di_app_js():
    assert codice_web.app() == (WEB / "app.js").read_text(encoding="utf-8")
    assert codice_web.moduli() == []


def test_leggi_da_il_testo_del_file_e_per_app_js_il_codice_unito():
    assert codice_web.leggi("testi.js") == (WEB / "testi.js").read_text(encoding="utf-8")
    assert codice_web.leggi("sw.js") == (WEB / "sw.js").read_text(encoding="utf-8")
    assert codice_web.leggi("app.js") == codice_web.app()


def test_script_classici_nell_ordine_della_pagina():
    nomi = [p.name for p in codice_web.script_classici()]
    assert nomi == ["testi.js", "avatar.js", "live.js", "dafare.js", "anteprima.js", "primoavvio.js", "impostazioni.js"]
    assert all(p.parent == WEB for p in codice_web.script_classici())


def test_tutto_e_script_classici_piu_app():
    attesa = "\n".join([*(p.read_text(encoding="utf-8") for p in codice_web.script_classici()), codice_web.app()])
    assert codice_web.tutto() == attesa


def test_tutti_i_file_sono_i_js_della_web_in_ordine_di_nome():
    file = codice_web.tutti_i_file()
    assert list(file) == sorted(p.name for p in WEB.glob("*.js"))
    assert file["app.js"] == (WEB / "app.js").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------- domani: moduli in una cartella finta
def test_moduli_finti_si_uniscono_senza_import_ed_export(tmp_path):
    _scrivi(tmp_path, "app.js", 'import { f } from "./moduli/a.js";\nf();\n')
    _scrivi(tmp_path, "moduli/a.js", 'import { g } from "./b.js";\nexport function f() { return g(); }\n')
    _scrivi(tmp_path, "moduli/b.js", "export const g = () => 1;\nexport async function h() {}\nexport let k = 2;\n")

    assert codice_web.moduli(tmp_path) == [tmp_path / "moduli" / "b.js", tmp_path / "moduli" / "a.js"]
    testo = codice_web.app(tmp_path)
    assert not re.search(r"^\s*import\b", testo, flags=re.M)
    assert not re.search(r"^\s*export\b", testo, flags=re.M)
    assert "function f() { return g(); }" in testo
    assert "const g = () => 1;" in testo and "async function h() {}" in testo and "let k = 2;" in testo
    assert testo.index("const g") < testo.index("function f") < testo.index("f();")      # ordine: b, a, app


def test_import_su_piu_righe_senza_nomi_e_liste_di_export(tmp_path):
    _scrivi(tmp_path, "app.js", 'import {\n  a,\n  b,\n} from "./moduli/a.js";\nimport "./moduli/c.js";\na(b);\n')
    _scrivi(tmp_path, "moduli/a.js", "function a() {}\nconst b = 1;\nexport { a, b };\n")
    _scrivi(tmp_path, "moduli/c.js", "// solo effetti\n")

    assert [p.name for p in codice_web.moduli(tmp_path)] == ["a.js", "c.js"]
    testo = codice_web.app(tmp_path)
    assert "import" not in testo and "export" not in testo and "from" not in testo
    assert testo.endswith("a(b);\n")


def test_un_modulo_importato_due_volte_compare_una_volta(tmp_path):
    _scrivi(tmp_path, "app.js", 'import "./moduli/a.js";\nimport "./moduli/b.js";\n')
    _scrivi(tmp_path, "moduli/a.js", 'import "./comune.js";\nconst A = 1;\n')
    _scrivi(tmp_path, "moduli/b.js", 'import "./comune.js";\nimport "./a.js";\nconst B = 2;\n')
    _scrivi(tmp_path, "moduli/comune.js", "const C = 0;\n")

    assert [p.name for p in codice_web.moduli(tmp_path)] == ["comune.js", "a.js", "b.js"]
    assert codice_web.app(tmp_path).count("const C = 0;") == 1


def test_import_circolari_non_bloccano(tmp_path):
    _scrivi(tmp_path, "app.js", 'import "./moduli/a.js";\n')
    _scrivi(tmp_path, "moduli/a.js", 'import "./b.js";\nconst A = 1;\n')
    _scrivi(tmp_path, "moduli/b.js", 'import "./a.js";\nconst B = 2;\n')

    assert [p.name for p in codice_web.moduli(tmp_path)] == ["b.js", "a.js"]


@pytest.mark.parametrize("percorso", ["https://esempio.invalid/x.js", "../fuori.js", "./moduli/../../fuori.js", "moduli/a.js"])
def test_import_fuori_dalla_web_o_non_relativi_sono_un_errore(tmp_path, percorso):
    web = tmp_path / "web"
    _scrivi(web, "app.js", f'import "{percorso}";\n')
    _scrivi(tmp_path, "fuori.js", "const X = 1;\n")
    _scrivi(web, "moduli/a.js", "const A = 1;\n")
    with pytest.raises(ValueError):
        codice_web.moduli(web)


def test_le_parole_import_ed_export_dentro_il_codice_restano(tmp_path):
    _scrivi(tmp_path, "app.js", 'const t = "export finto";\n  importa();\nawait import("./x.js");\n')
    assert codice_web.app(tmp_path) == 'const t = "export finto";\n  importa();\nawait import("./x.js");\n'
    assert codice_web.moduli(tmp_path) == []


def test_script_classici_di_una_pagina_finta(tmp_path):
    _scrivi(tmp_path, "index.html", '<script src="testi.js"></script>\n<script type="module" src="app.js"></script>\n'
                                    '<script defer src="impostazioni.js"></script>\n<script>var x = 1;</script>\n')
    assert codice_web.script_classici(tmp_path) == [tmp_path / "testi.js", tmp_path / "impostazioni.js"]


# --------------------------------------------------------------------------- nessun altro test legge da solo il codice web
LETTURA = r"\.(?:read_text|read_bytes|open)\("
PERCORSO_JS = r'(?:\bWEB|"web")\s*/\s*(?:"[^"]*"\s*/\s*)*"[^"]*\.js"'
REGOLE = [
    re.compile(PERCORSO_JS + r"\s*\)\s*" + LETTURA),                         # (WEB / "app.js").read_text(...)
    re.compile(r'(?:\bWEB|"web")\s*/\s*[A-Za-z_]\w*\s*\)\s*' + LETTURA),     # (server.WEB / nome).read_text(...)
    re.compile(r'(?:\bWEB|"web")\s*/\s*[A-Za-z_]\w*\s+for\s'),               # [WEB / n for n in (...)]
    re.compile(r'\bWEB\s*\.\s*r?glob\(\s*["\'][^"\']*js'),                   # WEB.glob("*.js")
    re.compile(r'["\'][^"\']*fanta/web/[^"\']*\.js["\']\s*\)\s*' + LETTURA),  # Path("fanta/web/app.js").read_text(...)
    re.compile(r'\bopen\(\s*[^)]*(?:\bWEB\b|"web"|fanta/web/)[^)]*\.js'),    # open(WEB / "app.js")
]


def letture_dirette(testo: str) -> list[int]:
    """Numeri di riga in cui il testo legge da solo un file `.js` di `fanta/web/`, anche passando da un nome
    (`X = WEB / "live.js"` e poi `X.read_text(...)`)."""
    righe = testo.splitlines()
    trovate = {n for n, riga in enumerate(righe, 1) if any(r.search(riga) for r in REGOLE)}
    nomi = set(re.findall(r"^\s*(\w+)\s*=\s*.*" + PERCORSO_JS + r"\s*$", testo, flags=re.M))
    for nome in nomi:
        lettura_nome = re.compile(rf"\b{nome}\s*{LETTURA}|\bopen\(\s*{nome}\b")
        trovate |= {n for n, riga in enumerate(righe, 1) if lettura_nome.search(riga)}
    return sorted(trovate)


@pytest.mark.parametrize("riga", [
    'APP = (server.WEB / "app.js").read_text(encoding="utf-8")',
    '    js = (WEB / "app.js").read_text(encoding="utf-8")',
    'js = (RADICE / "fanta" / "web" / "app.js").read_text(encoding="utf-8")',
    'testi = (Path(server.__file__).parent / "web" / "testi.js").read_text(encoding="utf-8")',
    'sw = (WEB / "sw.js").read_bytes()',
    "    return espandi((server.WEB / nome).read_text(encoding=\"utf-8\"))",
    'FILE_WEB = [server.WEB / n for n in ("app.js", "live.js")]',
    'JS_WEB = "\\n".join(p.read_text(encoding="utf-8") for p in sorted(WEB.glob("*.js")))',
    '    for f in sorted(server.WEB.glob("*.js")):',
    'X = Path("fanta/web/app.js").read_text(encoding="utf-8")',
    'with open(WEB / "app.js", encoding="utf-8") as f:',
    'with (WEB / "moduli" / "oggi.js").open(encoding="utf-8") as f:',
])
def test_il_controllo_trova_le_letture_dirette(riga):
    assert letture_dirette(riga) == [1]


def test_il_controllo_trova_le_letture_da_un_nome():
    testo = 'LIVE_JS = WEB / "live.js"\n\ndef test_x():\n    src = LIVE_JS.read_text(encoding="utf-8")\n'
    assert letture_dirette(testo) == [4]


@pytest.mark.parametrize("riga", [
    'CSS = (WEB / "stile.css").read_text(encoding="utf-8")',
    'html = (WEB / "index.html").read_text(encoding="utf-8")',
    "assert '\"/impostazioni.js\"' in (WEB.parent / \"rotte_account.py\").read_text(encoding=\"utf-8\")",
    'assert "/avatar.js" in (RADICE / "fanta" / "rotte_account.py").read_text(encoding="utf-8")',
    'sw = (SITO / "sw.js").read_text(encoding="utf-8")',
    'r = subprocess.run(["node", "--check", str(WEB / nome)], capture_output=True, text=True)',
    'LIVE_JS = WEB / "live.js"',
    'APP = codice_web.app()',
    'assert c.get("/dafare.js").status_code == 200',
    '(repo / "fanta" / "web" / "sw.js").write_bytes(b"const VERSIONE = 2;\\n")',
])
def test_il_controllo_lascia_stare_il_resto(riga):
    assert letture_dirette(riga) == []


def test_nessun_test_legge_da_solo_il_codice_web():
    """I test leggono i file `.js` di `fanta/web/` solo con `codice_web`: quando `app.js` sarà diviso in moduli, il codice
    da controllare resta in un posto solo."""
    propri = {TESTS / "codice_web.py", Path(__file__).resolve()}
    trovate = [f"{p.relative_to(RADICE).as_posix()}:{n}" for p in sorted(TESTS.rglob("*.py")) if p.resolve() not in propri
               for n in letture_dirette(p.read_text(encoding="utf-8"))]
    assert not trovate, "leggi il codice web con codice_web (tests/codice_web.py): " + ", ".join(trovate)
