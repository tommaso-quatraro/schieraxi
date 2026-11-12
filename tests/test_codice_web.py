"""Il lettore unico del codice della web (tests/codice_web.py): oggi dà esattamente il testo dei file, domani unisce anche i
moduli di `fanta/web/moduli/` (ondata 2, lavoro B0). E nessun altro test legge da solo i file `.js` di `fanta/web/`."""
import ast
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
    """Senza la cartella dei moduli: esattamente il testo di app.js. Con i moduli (dopo B1): ogni modulo sta in
    fanta/web/moduli/, il suo codice è in app() e non resta nessuna riga import o export."""
    testo_app = (WEB / "app.js").read_text(encoding="utf-8")
    moduli = codice_web.moduli()
    if not (WEB / "moduli").exists():
        assert moduli == []
        assert codice_web.app() == testo_app
        return
    unito = codice_web.app()
    assert not re.search(r"^\s*(import|export)\b", unito, flags=re.M)
    for p in [*moduli, WEB / "app.js"]:
        assert p == WEB / "app.js" or p.is_relative_to(WEB / "moduli"), p
        righe = [r for r in p.read_text(encoding="utf-8").splitlines() if r.strip() and not re.match(r"\s*(import|export)\b", r)]
        assert all(r in unito for r in righe), p.name


def test_leggi_da_il_testo_del_file_e_per_app_js_il_codice_unito():
    assert codice_web.leggi("testi.js") == (WEB / "testi.js").read_text(encoding="utf-8")
    assert codice_web.leggi("sw.js") == (WEB / "sw.js").read_text(encoding="utf-8")
    assert codice_web.leggi("app.js") == codice_web.app()


def test_script_classici_nell_ordine_della_pagina():
    nomi = [p.name for p in codice_web.script_classici()]
    assert nomi == ["testi.js", "avatar.js", "dafare.js", "anteprima.js", "primoavvio.js", "impostazioni.js"]
    assert all(p.parent == WEB for p in codice_web.script_classici())


def test_tutto_e_script_classici_piu_app():
    attesa = "\n".join([*(p.read_text(encoding="utf-8") for p in codice_web.script_classici()), codice_web.app()])
    assert codice_web.tutto() == attesa


def test_tutti_i_file_sono_i_js_della_web_in_ordine_di_nome():
    file = codice_web.tutti_i_file()
    principali = [n for n in file if "/" not in n]
    assert principali == sorted(p.name for p in WEB.glob("*.js"))
    assert list(file) == principali + sorted(n for n in file if "/" in n)          # i moduli (dopo B1) vengono dopo
    assert all(n.startswith("moduli/") for n in file if "/" in n)
    assert file["app.js"] == (WEB / "app.js").read_text(encoding="utf-8")


def test_tutti_i_file_comprende_i_moduli(tmp_path):
    _scrivi(tmp_path, "app.js", 'import "./moduli/b.js";\n')
    _scrivi(tmp_path, "testi.js", "const T = 1;\n")
    _scrivi(tmp_path, "moduli/b.js", "const B = 1;\n")
    _scrivi(tmp_path, "moduli/a.js", "export const A = 1;\n")
    file = codice_web.tutti_i_file(tmp_path)
    assert list(file) == ["app.js", "testi.js", "moduli/a.js", "moduli/b.js"]
    assert file["moduli/a.js"] == "export const A = 1;\n"                       # così com'è


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


@pytest.mark.parametrize("riga", [
    'import { f } from "./moduli/a.js";   // utilità',
    'import { f } from "./moduli/a.js"; /* utilità */',
    "import { f } from './moduli/a.js'",
    '  import { f } from "./moduli/a.js";',
    '\timport "./moduli/a.js"; // solo effetti',
])
def test_import_con_commento_o_rientrati_si_riconoscono(tmp_path, riga):
    _scrivi(tmp_path, "app.js", f"{riga}\nf();\n")
    _scrivi(tmp_path, "moduli/a.js", "  export function f() {}  // in un blocco rientrato\n")
    assert codice_web.moduli(tmp_path) == [tmp_path / "moduli" / "a.js"]
    testo = codice_web.app(tmp_path)
    assert not re.search(r"^\s*(import|export)\b", testo, flags=re.M), testo
    assert "  function f() {}" in testo and testo.endswith("f();\n")


@pytest.mark.parametrize("modulo", [
    "export default function f() {}\n",
    'export { f } from "./c.js";\n',
    'export * from "./c.js";\n',
    'export * as c from "./c.js";\n',
    "  export default 1;\n",
    'import dati from "./dati.json" with { type: "json" };\n',
    'import { f }\n  from "./c.js" assert { type: "js" };\n',
])
def test_import_ed_export_che_il_lettore_non_sa_togliere_sono_un_errore(tmp_path, modulo):
    _scrivi(tmp_path, "app.js", 'import "./moduli/a.js";\n')
    _scrivi(tmp_path, "moduli/a.js", modulo)
    _scrivi(tmp_path, "moduli/c.js", "export function f() {}\n")
    _scrivi(tmp_path, "moduli/dati.json", "{}\n")
    with pytest.raises(ValueError, match="a.js"):
        codice_web.app(tmp_path)


def test_script_classici_di_una_pagina_finta(tmp_path):
    _scrivi(tmp_path, "index.html", '<script src="testi.js"></script>\n<script type="module" src="app.js"></script>\n'
                                    '<script defer src="impostazioni.js"></script>\n<script>var x = 1;</script>\n')
    assert codice_web.script_classici(tmp_path) == [tmp_path / "testi.js", tmp_path / "impostazioni.js"]


# --------------------------------------------------------------------------- nessun altro test legge da solo il codice web
# Il controllo legge l'albero del codice Python (ast), non le righe: vede anche le virgolette semplici, `Path(WEB, "app.js")`,
# `WEB.joinpath(...)`, le letture spezzate su più righe e i percorsi messi in una lista, in un nome o in un ciclo.
_METODI_DI_LETTURA = {"read_text", "read_bytes", "open"}
_COSTRUTTORI_DI_PERCORSI = {"Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath"}
_CHE_PASSANO_LA_LISTA = {"sorted", "list", "tuple", "set", "reversed", "iter", "enumerate"}


def _nomina_la_web(nodo: ast.AST) -> bool:
    """L'espressione nomina la cartella della web: `WEB`, `server.WEB`, la stringa "web" o "fanta/web…"."""
    for x in ast.walk(nodo):
        if isinstance(x, ast.Name) and x.id == "WEB" or isinstance(x, ast.Attribute) and x.attr == "WEB":
            return True
        if isinstance(x, ast.Constant) and isinstance(x.value, str):
            v = x.value.replace("\\", "/")
            if v == "web" or v.startswith(("fanta/web", "./fanta/web")):
                return True
    return False


def _forse_js(nodo: ast.AST) -> bool:
    """L'ultimo pezzo del percorso è un file .js, o non si sa (un nome, una f-string...)."""
    if isinstance(nodo, ast.Constant):
        return isinstance(nodo.value, str) and nodo.value.endswith(".js")
    return True


def _percorso_web(nodo: ast.AST) -> bool:
    """Un percorso (o un elenco di percorsi da glob) di un file .js della web."""
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
        return _nomina_la_web(nodo.left) and _forse_js(nodo.right)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        v = nodo.value.replace("\\", "/")
        return "fanta/web/" in v and v.endswith(".js")
    if not isinstance(nodo, ast.Call) or not nodo.args:
        return False
    f = nodo.func
    nome = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
    if nome in _COSTRUTTORI_DI_PERCORSI:
        if len(nodo.args) == 1:
            return _percorso_web(nodo.args[0])
        return any(_nomina_la_web(a) for a in nodo.args[:-1]) and _forse_js(nodo.args[-1])
    if nome == "joinpath" and isinstance(f, ast.Attribute):
        return _nomina_la_web(f.value) and _forse_js(nodo.args[-1])
    if nome in ("glob", "rglob") and isinstance(f, ast.Attribute):
        schema = nodo.args[0]
        return _nomina_la_web(f.value) and (not isinstance(schema, ast.Constant) or bool(re.search(r"(\.js|\*)$", str(schema.value))))
    return False


def _da_percorsi_web(nodo: ast.AST, nomi: set[str]) -> bool:
    """L'espressione dà uno o più percorsi .js della web: il percorso stesso, un nome che lo contiene, una lista, sorted(...)..."""
    if _percorso_web(nodo):
        return True
    if isinstance(nodo, ast.Name):
        return nodo.id in nomi
    if isinstance(nodo, (ast.List, ast.Tuple, ast.Set)):
        return any(_da_percorsi_web(e, nomi) for e in nodo.elts)
    if isinstance(nodo, ast.Starred):
        return _da_percorsi_web(nodo.value, nomi)
    if isinstance(nodo, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return _da_percorsi_web(nodo.elt, nomi)
    if isinstance(nodo, ast.Subscript):
        return _da_percorsi_web(nodo.value, nomi)
    if isinstance(nodo, ast.IfExp):
        return _da_percorsi_web(nodo.body, nomi) or _da_percorsi_web(nodo.orelse, nomi)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        return _da_percorsi_web(nodo.left, nomi) or _da_percorsi_web(nodo.right, nomi)
    if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in _CHE_PASSANO_LA_LISTA and nodo.args:
        return _da_percorsi_web(nodo.args[0], nomi)
    return False


def _nomi_in(bersaglio: ast.AST) -> set[str]:
    return {x.id for x in ast.walk(bersaglio) if isinstance(x, ast.Name)}


def letture_dirette(testo: str) -> list[int]:
    """Numeri di riga in cui il codice Python legge da solo un file `.js` di `fanta/web/`, anche passando da un nome, da una
    lista o da un ciclo (`for f in FILE: f.read_text()`). I nomi valgono per tutto il file, senza guardare le funzioni:
    nel dubbio il controllo chiede di passare da codice_web."""
    albero = ast.parse(testo)
    nomi: set[str] = set()
    while True:                                                      # i nomi che contengono percorsi .js della web
        prima = len(nomi)
        for n in ast.walk(albero):
            if isinstance(n, ast.Assign) and _da_percorsi_web(n.value, nomi):
                for t in n.targets:
                    nomi |= _nomi_in(t)
            elif isinstance(n, (ast.AnnAssign, ast.NamedExpr)) and n.value is not None and _da_percorsi_web(n.value, nomi):
                nomi |= _nomi_in(n.target)
            elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)) and _da_percorsi_web(n.iter, nomi):
                nomi |= _nomi_in(n.target)
        if len(nomi) == prima:
            break
    righe = set()
    for n in ast.walk(albero):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr in _METODI_DI_LETTURA and _da_percorsi_web(f.value, nomi):
            righe.add(n.lineno)                                      # (WEB / "app.js").read_text(), f.open()
        elif (isinstance(f, ast.Name) and f.id == "open" or isinstance(f, ast.Attribute) and f.attr == "open") \
                and n.args and _da_percorsi_web(n.args[0], nomi):
            righe.add(n.lineno)                                      # open(WEB / "app.js"), io.open(...)
    return sorted(righe)


@pytest.mark.parametrize("codice", [
    'APP = (server.WEB / "app.js").read_text(encoding="utf-8")',
    "APP = (server.WEB / 'app.js').read_text(encoding='utf-8')",
    'js = (RADICE / "fanta" / "web" / "app.js").read_text(encoding="utf-8")',
    'testi = (Path(server.__file__).parent / "web" / "testi.js").read_text(encoding="utf-8")',
    'sw = (WEB / "sw.js").read_bytes()',
    "x = espandi((server.WEB / nome).read_text(encoding=\"utf-8\"))",
    'x = Path(WEB, "app.js").read_text(encoding="utf-8")',
    'x = Path(RADICE, "fanta", "web", "app.js").read_text()',
    'x = WEB.joinpath("app.js").read_text()',
    'x = server.WEB.joinpath("moduli", "oggi.js").read_text()',
    'X = Path("fanta/web/app.js").read_text(encoding="utf-8")',
    'X = Path("fanta\\\\web\\\\app.js").read_text(encoding="utf-8")',
    'f = open(WEB / "app.js", encoding="utf-8")',
    'f = open("fanta/web/app.js")',
    'f = io.open(WEB / "app.js")',
    'f = (WEB / "moduli" / "oggi.js").open(encoding="utf-8")',
    'JS = "\\n".join(p.read_text(encoding="utf-8") for p in sorted(WEB.glob("*.js")))',
])
def test_il_controllo_trova_le_letture_dirette(codice):
    assert letture_dirette(codice) == [1]


@pytest.mark.parametrize("codice, righe", [
    ('APP = (\n    WEB\n    / "app.js"\n).read_text(\n    encoding="utf-8")\n', [1]),                             # spezzata su più righe
    ('LIVE_JS = WEB / "live.js"\n\ndef test_x():\n    src = LIVE_JS.read_text(encoding="utf-8")\n', [4]),        # da un nome
    ('FILE = [WEB / "testi.js", RADICE / "docs" / "A.md"]\n\ndef test_x():\n    for f in FILE:\n'                # lista in un ciclo
     '        testo = f.read_text(encoding="utf-8")\n', [5]),
    ('FILE_WEB = [server.WEB / n for n in ("app.js", "live.js")]\n'
     'CODICE = "\\n".join(f.read_text(encoding="utf-8") for f in FILE_WEB)\n', [2]),
    ('for f in sorted(server.WEB.glob("*.js")):\n    assert "x" not in f.read_text(encoding="utf-8")\n', [2]),
    ('NOMI = ["app.js", "testi.js"]\nfor n in NOMI:\n    t = (WEB / n).read_text()\n', [3]),
    ('PERCORSI = {"a": WEB / "app.js"}\n', []),                                                            # un dizionario non letto
])
def test_il_controllo_trova_le_letture_su_piu_righe(codice, righe):
    assert letture_dirette(codice) == righe


@pytest.mark.parametrize("codice", [
    'CSS = (WEB / "stile.css").read_text(encoding="utf-8")',
    'html = (WEB / "index.html").read_text(encoding="utf-8")',
    "assert '\"/impostazioni.js\"' in (WEB.parent / \"rotte_account.py\").read_text(encoding=\"utf-8\")",
    'assert "/avatar.js" in (RADICE / "fanta" / "rotte_account.py").read_text(encoding="utf-8")',
    'sw = (SITO / "sw.js").read_text(encoding="utf-8")',
    'm = json.loads((Path(server.__file__).parent / "web" / "manifest.webmanifest").read_text(encoding="utf-8"))',
    'r = subprocess.run(["node", "--check", str(WEB / nome)], capture_output=True, text=True)',
    'LIVE_JS = WEB / "live.js"\nr = subprocess.run([NODE, "-e", f"require({json.dumps(str(LIVE_JS))})"])',
    'for p in server.WEB.parent.glob("*.py"):\n    t = p.read_text(encoding="utf-8")',
    'for p in WEB.glob("*.json"):\n    t = p.read_text(encoding="utf-8")',
    'APP = codice_web.app()',
    'assert c.get("/dafare.js").status_code == 200',
    'assert html.index("anteprima.js") < html.index("app.js")',
    'file = ["fanta/web/app.js", "docs/API.md"]\nassert pr.novita(file) == []',
    '(repo / "fanta" / "web" / "sw.js").write_bytes(b"const VERSIONE = 2;\\n")',
    'assert r.content == (server.WEB / "icone" / "viola-180.png").read_bytes()',
])
def test_il_controllo_lascia_stare_il_resto(codice):
    assert letture_dirette(codice) == []


def test_nessun_test_legge_da_solo_il_codice_web():
    """I test leggono i file `.js` di `fanta/web/` solo con `codice_web`: quando `app.js` sarà diviso in moduli, il codice
    da controllare resta in un posto solo."""
    propri = {TESTS / "codice_web.py", Path(__file__).resolve()}
    trovate = [f"{p.relative_to(RADICE).as_posix()}:{n}" for p in sorted(TESTS.rglob("*.py")) if p.resolve() not in propri
               for n in letture_dirette(p.read_text(encoding="utf-8"))]
    assert not trovate, "leggi il codice web con codice_web (tests/codice_web.py): " + ", ".join(trovate)
