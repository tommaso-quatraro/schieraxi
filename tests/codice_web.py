"""Il lettore unico del codice della web app (`fanta/web/*.js`) per i test Python.

I test che controllano il codice JavaScript lo leggono da qui e non con `read_text` sui file: quando `app.js` sarà diviso in
moduli (`fanta/web/moduli/*.js`, ondata 2), `app()` restituirà `app.js` più i moduli e i test non cambieranno.
Oggi `app()` restituisce esattamente il testo di `app.js`. Lo controlla tests/test_codice_web.py, che controlla anche che
nessun altro test legga da solo i file `.js` di `fanta/web/`.

Ogni funzione accetta la cartella della web (`web`) per le prove con una cartella finta.
"""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "fanta" / "web"

# Fine di un import o di un export: `;` facoltativo e un commento facoltativo (`// …` o `/* … */`) sulla stessa riga.
_FINE = r"[ \t]*;?[ \t]*(?://[^\n]*|/\*[^\n]*?\*/[ \t]*)?(?:\r?\n|$)"
# `import { a, b } from "./x.js";` (anche su più righe o rientrato) e `import "./x.js";`, all'inizio della riga.
# `import(` (import dinamico) e parole come `importa` non c'entrano.
_IMPORT = re.compile(r'^[ \t]*import(?:\s+[^;"\'()]*?\s+from)?\s*["\']([^"\']+)["\']' + _FINE, re.M)
# `export function`, `export async function`, `export const`, `export let`, `export var`, `export class`
_EXPORT_DICHIARAZIONE = re.compile(r"^([ \t]*)export\s+(?=(?:async\s+)?function\b|const\b|let\b|var\b|class\b)", re.M)
# `export { a, b };` (anche su più righe): i nomi sono già dichiarati sopra, la riga se ne va
_EXPORT_ELENCO = re.compile(r"^[ \t]*export\s*\{[^}]*\}" + _FINE, re.M)
# quello che resta dopo il taglio e il lettore non sa togliere: `export default`, `export … from`, import con `with {…}`…
_RESTO = re.compile(r"^[ \t]*(?:import\b(?!\s*[(.])|export\b).*$", re.M)
_SCRIPT = re.compile(r"<script\b([^>]*)>", re.I)


def _testo(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _importati(file: Path, web: Path) -> list[Path]:
    """I file importati da `file`, nell'ordine in cui compaiono. Solo percorsi relativi dentro la cartella della web."""
    radice = web.resolve()
    elenco = []
    for percorso in _IMPORT.findall(_testo(file)):
        if not percorso.startswith(("./", "../")):
            raise ValueError(f"{file.name}: import non relativo {percorso!r}")
        dove = (file.parent / percorso).resolve()
        if not dove.is_relative_to(radice):
            raise ValueError(f"{file.name}: import fuori dalla web {percorso!r}")
        elenco.append(dove)
    return elenco


def moduli(web: Path = WEB) -> list[Path]:
    """I file importati da `app.js`, seguendo anche gli import dei moduli: ognuno una volta, prima quelli da cui dipende
    (l'ordine in cui il browser li esegue). Vuota finché `app.js` non importa niente."""
    web = Path(web)
    visti: set[Path] = set()
    ordine: list[Path] = []

    def visita(file: Path) -> None:
        for dove in _importati(file, web):
            if dove not in visti:
                visti.add(dove)
                visita(dove)
                ordine.append(dove)

    app_js = (web / "app.js").resolve()
    visti.add(app_js)
    visita(app_js)
    return [web / p.relative_to(web.resolve()) for p in ordine]


def _senza_import_ed_export(file: Path) -> str:
    testo = _IMPORT.sub("", _testo(file))
    testo = _EXPORT_ELENCO.sub("", testo)
    testo = _EXPORT_DICHIARAZIONE.sub(r"\1", testo)
    resto = _RESTO.search(testo)
    if resto:
        raise ValueError(f"{file.name}: il lettore non sa togliere questa riga: {resto.group(0).strip()!r}")
    return testo


def app(web: Path = WEB) -> str:
    """`app.js` più i moduli (prima i moduli, nell'ordine di `moduli()`), senza le righe `import … from …` e senza la parola
    `export ` in testa alle dichiarazioni. Oggi è esattamente il testo di `app.js`."""
    web = Path(web)
    pezzi = [*moduli(web), web / "app.js"]
    return "\n".join(_senza_import_ed_export(p) for p in pezzi)


def script_classici(web: Path = WEB) -> list[Path]:
    """I `<script src>` di `index.html`, nell'ordine della pagina, senza `app.js` e senza gli script `type="module"`."""
    web = Path(web)
    elenco = []
    for attributi in _SCRIPT.findall(_testo(web / "index.html")):
        src = re.search(r'\bsrc="([^"]+)"', attributi)
        if not src or re.search(r'\btype="module"', attributi) or src.group(1) == "app.js":
            continue
        elenco.append(web / src.group(1))
    return elenco


def tutto(web: Path = WEB) -> str:
    """Gli script classici della pagina più `app()`."""
    return "\n".join([*(_testo(p) for p in script_classici(web)), app(web)])


def leggi(nome: str, web: Path = WEB) -> str:
    """Il testo di un file `.js` della web (`"testi.js"`, `"sw.js"`, …); per `"app.js"` il codice unito di `app()`."""
    web = Path(web)
    if nome == "app.js":
        return app(web)
    return _testo(web / nome)


def tutti_i_file(web: Path = WEB) -> dict[str, str]:
    """Ogni file `.js` della web così com'è, per nome: prima quelli di `fanta/web/` in ordine di nome, poi quelli di
    `fanta/web/moduli/` (`"moduli/oggi.js"`). Per i controlli che passano tutto il codice, file per file."""
    web = Path(web)
    file = sorted(web.glob("*.js")) + sorted((web / "moduli").glob("*.js"))
    return {p.relative_to(web).as_posix(): _testo(p) for p in file}
