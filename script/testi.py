#!/usr/bin/env python3
"""Catalogo unico dei testi dell'interfaccia: da qui nascono i testi della web e dell'iPhone.

La fonte è `fanta/testi/<prefisso>.json`, un file per prefisso della chiave (`oggi.json` ha solo chiavi `oggi.*`; il prefisso ha
solo lettere minuscole e cifre):

  {"oggi.tua_formazione": {"it": "La tua formazione", "en": "Your line-up", "nota": "facoltativa, per chi scrive"}}

Ogni voce ha italiano (`it`) e inglese (`en`) con gli stessi segnaposto `{nome}`; i plurali sono coppie `x.one` / `x.other`.
Dal catalogo si generano:
  - il blocco dei dati di `fanta/web/testi.js` (l'oggetto TESTI, fra le due righe-segno `// <catalogo> …` e `// </catalogo>`),
    una chiave per riga, file in ordine alfabetico e chiavi nell'ordine del file; il resto di `testi.js` è scritto a mano;
  - i file Swift di `ios/Sources/Support/Catalogo/` (solo italiano), per le sole chiavi che l'iPhone elenca in
    `ios/testi/<prefisso>.txt` (una chiave per riga, `#` = commento): `Catalogo.swift` e `Catalogo+<Prefisso>.swift`.
    `oggi.tua_formazione` diventa `Catalogo.Oggi.tuaFormazione`; con segnaposto una funzione con un parametro `String` per
    segnaposto, in ordine alfabetico (`{giorni}`, `{ore}` → `giorniOre(giorni:ore:)`); la coppia `x.one` / `x.other` diventa
    `x(_ n: Int)` (`.one` se n == 1). Nell'elenco dell'iPhone un plurale si scrive con la base (`oggi.titolari`) o con la coppia.

Uso:
  python script/testi.py --scrivi      rigenera testi.js e i file Swift dal catalogo
  python script/testi.py --controlla   controlla il catalogo e che i file generati siano aggiornati

Uscite: 0 tutto a posto; 1 catalogo con errori o file diversi da quelli generati; 2 uso sbagliato.
Solo libreria standard. Un conflitto su un file generato si risolve unendo il catalogo e rigenerando con --scrivi.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

RADICE = Path(__file__).resolve().parent.parent
CATALOGO = Path("fanta") / "testi"
TESTI_JS = Path("fanta") / "web" / "testi.js"
ELENCHI_IOS = Path("ios") / "testi"
CARTELLA_SWIFT = Path("ios") / "Sources" / "Support" / "Catalogo"
SEGNO_INIZIO = "// <catalogo> generato da script/testi.py: non modificare a mano"
SEGNO_FINE = "// </catalogo>"
TESTA_SWIFT = "// Generato da script/testi.py: non modificare a mano."
RIFAI = "Lancia: python script/testi.py --scrivi"

_CHIAVE = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+")
_PREFISSO = re.compile(r"[a-z0-9]+")
_SEGNAPOSTO = re.compile(r"\{(\w+)\}")
_CAMPI = ("it", "en", "nota")
_PLURALE = (".one", ".other")
# Caratteri che chiudono una riga per alcuni lettori (str.splitlines, Swift): nei testi generati vanno scritti con l'escape,
# così ogni chiave resta su una riga sola. Quelli sotto lo spazio li scrive già con l'escape json.dumps.
_A_CAPO_UNICODE = {"\x85": "\\u0085", " ": "\\u2028", " ": "\\u2029"}
_PAROLE_SWIFT = frozenset("""
    associatedtype class deinit enum extension fileprivate func import init inout internal let open operator private
    precedencegroup protocol public rethrows static struct subscript typealias var break case catch continue default defer do
    else fallthrough for guard if in repeat return switch throw where while Any as await false is nil self Self super throws
    true try _
""".split())


class Voce(NamedTuple):
    it: str
    en: str
    nota: str | None = None


class ErroreCatalogo(ValueError):
    """Catalogo o elenco dell'iPhone sbagliato: `errori` ha un problema per riga, ognuno con la chiave o il file."""

    def __init__(self, errori: list[str]):
        self.errori = list(errori)
        super().__init__("\n".join(self.errori))


# ---------------------------------------------------------------- catalogo

def _segnaposto(testo: str) -> list[str]:
    return sorted(_SEGNAPOSTO.findall(testo))


class _Oggetto(list):
    """Un oggetto JSON letto come elenco di coppie (chiave, valore), così le chiavi ripetute non spariscono."""


def _leggi_file(percorso: Path, errori: list[str]) -> list[tuple[str, object]]:
    """Le coppie chiave-voce del file, nell'ordine, anche le chiavi ripetute (json.loads terrebbe solo l'ultima)."""
    try:
        coppie = json.loads(percorso.read_text(encoding="utf-8-sig"), object_pairs_hook=_Oggetto)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        errori.append(f"{percorso.name}: non si legge come JSON ({e})")
        return []
    if not isinstance(coppie, _Oggetto):
        errori.append(f"{percorso.name}: deve essere un oggetto {{\"chiave\": {{\"it\": …, \"en\": …}}}}")
        return []
    return coppie


def _voce(chiave: str, dati: object, errori: list[str]) -> Voce | None:
    if not isinstance(dati, _Oggetto):
        errori.append(f"{chiave}: la voce deve essere un oggetto con \"it\" e \"en\"")
        return None
    campi = dict(dati)
    sconosciuti = sorted(set(campi) - set(_CAMPI))
    if sconosciuti:
        errori.append(f"{chiave}: campi sconosciuti {', '.join(sconosciuti)} (ammessi: it, en, nota)")
    giusta = True
    for lingua in ("it", "en"):
        if not isinstance(campi.get(lingua), str) or not campi[lingua].strip():
            errori.append(f"{chiave}: manca il testo «{lingua}» (o è vuoto)")
            giusta = False
    nota = campi.get("nota")
    if nota is not None and (not isinstance(nota, str) or not nota.strip()):
        errori.append(f"{chiave}: «nota» deve essere un testo")
        giusta = False
    if not giusta:
        return None
    if _segnaposto(campi["it"]) != _segnaposto(campi["en"]):
        errori.append(f"{chiave}: segnaposto diversi fra italiano {_segnaposto(campi['it'])} e inglese {_segnaposto(campi['en'])}")
    return Voce(campi["it"], campi["en"], nota)


def carica_catalogo(cartella: Path) -> dict[str, dict[str, Voce]]:
    """Prefisso → chiave → Voce, con i file in ordine alfabetico e le chiavi nell'ordine del file.
    Solleva ErroreCatalogo con tutti i problemi trovati (chiave nel file sbagliato o in due file, lingua mancante o vuota,
    segnaposto diversi fra le lingue, plurale senza la sua coppia, chiave ripetuta)."""
    cartella = Path(cartella)
    file = sorted(cartella.glob("*.json"), key=lambda p: p.stem)
    if not file:
        raise ErroreCatalogo([f"{cartella}: cartella del catalogo mancante o senza file .json"])
    errori: list[str] = []
    catalogo: dict[str, dict[str, Voce]] = {}
    dove: dict[str, str] = {}
    for percorso in file:
        prefisso = percorso.stem
        if not _PREFISSO.fullmatch(prefisso):            # «a_b» e «aB» darebbero lo stesso nome Swift (Catalogo+AB.swift)
            errori.append(f"{percorso.name}: nome del file non valido, il prefisso usa solo lettere minuscole e cifre (a-z, 0-9)")
            continue
        voci: dict[str, Voce] = {}
        for chiave, dati in _leggi_file(percorso, errori):
            if not _CHIAVE.fullmatch(chiave):
                errori.append(f"{percorso.name}: chiave «{chiave}» non valida (lettere, cifre e _ separati da punti)")
                continue
            giusto = chiave.split(".", 1)[0] + ".json"
            if giusto != percorso.name:
                errori.append(f"{chiave}: chiave nel file sbagliato ({percorso.name}): va in {giusto}")
            if chiave in voci:
                errori.append(f"{chiave}: chiave ripetuta in {percorso.name}")
                continue
            if chiave in dove:
                errori.append(f"{chiave}: chiave in due file ({dove[chiave]} e {percorso.name})")
                continue
            dove[chiave] = percorso.name
            voce = _voce(chiave, dati, errori)
            if voce is not None:
                voci[chiave] = voce
        catalogo[prefisso] = voci
    for chiave in sorted(dove):
        for mia, altra in (_PLURALE, _PLURALE[::-1]):
            if chiave.endswith(mia) and chiave[: -len(mia)] + altra not in dove:
                errori.append(f"{chiave[: -len(mia)]}: plurale incompleto, c'è {chiave} ma manca {chiave[: -len(mia)] + altra}")
    if errori:
        raise ErroreCatalogo(errori)
    return catalogo


# ---------------------------------------------------------------- testi.js

def _stringa_js(testo: str) -> str:
    s = json.dumps(testo, ensure_ascii=False)
    for carattere, escape in _A_CAPO_UNICODE.items():
        s = s.replace(carattere, escape)
    return s


def blocco_testi_js(catalogo: dict[str, dict[str, Voce]]) -> str:
    """L'istruzione `const TESTI = { it: {…}, en: {…} };`: una chiave per riga, una riga vuota fra un file e l'altro.
    Ogni riga finisce con a capo (anche l'ultima)."""
    righe = ["const TESTI = {"]
    for lingua in ("it", "en"):
        righe.append(f"  {lingua}: {{")
        gruppi = [voci for _, voci in sorted(catalogo.items()) if voci]
        for i, voci in enumerate(gruppi):
            if i:
                righe.append("")
            righe += [f"    {_stringa_js(chiave)}: {_stringa_js(getattr(voce, lingua))}," for chiave, voce in voci.items()]
        righe.append("  },")
    righe.append("};")
    return "\n".join(righe) + "\n"


def _dividi_testi_js(testo: str) -> tuple[str, str, str]:
    """(prima, blocco, dopo): `prima` finisce con la riga-segno d'inizio, `dopo` comincia con quella di fine."""
    righe = testo.replace("\r\n", "\n").split("\n")
    inizi = [i for i, r in enumerate(righe) if r == SEGNO_INIZIO]
    fini = [i for i, r in enumerate(righe) if r == SEGNO_FINE]
    if len(inizi) != 1 or len(fini) != 1 or fini[0] < inizi[0]:
        raise ErroreCatalogo([f"{TESTI_JS.as_posix()}: servono le due righe-segno, una volta ciascuna e in quest'ordine: "
                              f"«{SEGNO_INIZIO}» e «{SEGNO_FINE}»"])
    i, j = inizi[0], fini[0]
    blocco = "".join(r + "\n" for r in righe[i + 1:j])
    return "\n".join(righe[: i + 1]) + "\n", blocco, "\n".join(righe[j:])


# ---------------------------------------------------------------- iPhone

def chiavi_ios(cartella: Path) -> dict[str, list[str]]:
    """Prefisso → chiavi elencate in `ios/testi/<prefisso>.txt`, nell'ordine; cartella assente = nessuna chiave."""
    cartella = Path(cartella)
    if not cartella.is_dir():
        return {}
    elenco = {}
    for percorso in sorted(cartella.glob("*.txt"), key=lambda p: p.stem):
        righe = (r.split("#", 1)[0].strip() for r in percorso.read_text(encoding="utf-8-sig").splitlines())
        elenco[percorso.stem] = [r for r in righe if r]
    return elenco


def _base_plurale(chiave: str, voci: dict[str, Voce]) -> str | None:
    """La base del plurale se `chiave` è `x`, `x.one` o `x.other` di una coppia del catalogo."""
    for fine in ("",) + _PLURALE:
        if chiave.endswith(fine):
            base = chiave[: len(chiave) - len(fine)]
            if all(base + p in voci for p in _PLURALE):
                return base
    return None


def _voce_ios(chiave: str, voci: dict[str, Voce]) -> tuple[str, bool] | None:
    """(chiave, è un plurale) per una riga dell'elenco dell'iPhone: `x.one` / `x.other` / `x` di una coppia danno la base
    del plurale; altrimenti la chiave semplice. None se il catalogo non ha né l'una né l'altro."""
    if chiave.endswith(_PLURALE) or chiave not in voci:
        base = _base_plurale(chiave, voci)
        if base is not None:
            return base, True
    return (chiave, False) if chiave in voci else None


def errori_ios(catalogo: dict[str, dict[str, Voce]], chiavi: dict[str, list[str]]) -> list[str]:
    """Problemi degli elenchi dell'iPhone: chiave che il catalogo non ha, chiave nell'elenco di un altro prefisso."""
    errori = []
    for prefisso, elenco in chiavi.items():
        for chiave in elenco:
            giusto = chiave.split(".", 1)[0]
            if giusto != prefisso:
                errori.append(f"ios/testi/{prefisso}.txt: «{chiave}» va in ios/testi/{giusto}.txt")
            elif _voce_ios(chiave, catalogo.get(giusto, {})) is None:
                errori.append(f"ios/testi/{prefisso}.txt: «{chiave}» non c'è nel catalogo (fanta/testi/{giusto}.json)")
    return errori


def _cammello(pezzi: list[str], maiuscola: bool) -> str:
    pezzi = [p for p in pezzi if p]
    testo = "".join(p[:1].upper() + p[1:] for p in pezzi)
    return testo if maiuscola else testo[:1].lower() + testo[1:]


def _identificatore(nome: str) -> str:
    """Un nome valido in Swift: cifra iniziale con `_` davanti, parola riservata tra apici inversi."""
    if nome[:1].isdigit():
        return "_" + nome
    return f"`{nome}`" if nome in _PAROLE_SWIFT else nome


def nome_tipo_swift(prefisso: str) -> str:
    return _identificatore(_cammello(prefisso.split("_"), maiuscola=True))


def nome_file_swift(prefisso: str) -> str:
    return f"Catalogo+{_cammello(prefisso.split('_'), maiuscola=True)}.swift"


def _nome_membro(chiave: str) -> str:
    return _identificatore(_cammello(re.split(r"[._]", chiave.partition(".")[2]), maiuscola=False))


def _stringa_swift(testo: str, parametri: dict[str, str]) -> str:
    """Il letterale Swift del testo: escape di `\\`, `"` e dei caratteri invisibili; ogni `{x}` diventa `\\(x)`."""
    def pezzo(s: str) -> str:
        fuori = []
        for c in s:
            if c in "\\\"":
                fuori.append("\\" + c)
            elif c in "\n\r\t\0":
                fuori.append({"\n": "\\n", "\r": "\\r", "\t": "\\t", "\0": "\\0"}[c])
            elif ord(c) < 0x20 or ord(c) == 0x7F or c in _A_CAPO_UNICODE:
                fuori.append(f"\\u{{{ord(c):X}}}")
            else:
                fuori.append(c)
        return "".join(fuori)

    parti = _SEGNAPOSTO.split(testo)              # testo, nome, testo, nome, …, testo
    return '"' + "".join(pezzo(p) if i % 2 == 0 else f"\\({parametri[p]})" for i, p in enumerate(parti)) + '"'


def _ordine_segnaposto(nome: str) -> tuple:
    return (0, int(nome), "") if nome.isdigit() else (1, 0, nome)


def _membro(chiave: str, plurale: bool, voci: dict[str, Voce]) -> tuple[str, str]:
    """(nome Swift, dichiarazione rientrata) per una chiave semplice o per la base di un plurale."""
    if not plurale:
        testo = voci[chiave].it
        nomi = sorted(set(_SEGNAPOSTO.findall(testo)), key=_ordine_segnaposto)
        nome = _nome_membro(chiave)
        commento = f"        /// `{chiave}`"
        if not nomi:
            return nome, f"{commento}\n        static let {nome} = {_stringa_swift(testo, {})}"
        parametri = {n: _identificatore(n) for n in nomi}
        firma = ", ".join(f"{parametri[n]}: String" for n in nomi)
        return nome, (f"{commento}\n        static func {nome}({firma}) -> String {{\n"
                      f"            {_stringa_swift(testo, parametri)}\n        }}")
    base = chiave
    uno, altri = voci[base + ".one"].it, voci[base + ".other"].it
    nomi = sorted((set(_SEGNAPOSTO.findall(uno)) | set(_SEGNAPOSTO.findall(altri))) - {"n"}, key=_ordine_segnaposto)
    parametri = {"n": "n"} | {n: _identificatore(n) for n in nomi}
    firma = ", ".join(["_ n: Int"] + [f"{parametri[n]}: String" for n in nomi])
    nome = _nome_membro(base)
    return nome, (f"        /// `{base}.one`, `{base}.other`\n"
                  f"        static func {nome}({firma}) -> String {{\n"
                  f"            n == 1 ? {_stringa_swift(uno, parametri)} : {_stringa_swift(altri, parametri)}\n        }}")


def swift(catalogo: dict[str, dict[str, Voce]], chiavi: dict[str, list[str]]) -> dict[str, str]:
    """Nome del file → testo dei file Swift per le chiavi elencate dall'iPhone (nessuna chiave: nessun file).
    Solleva ErroreCatalogo se un elenco ha chiavi sbagliate o due chiavi danno lo stesso nome Swift."""
    errori = errori_ios(catalogo, chiavi)
    if errori:
        raise ErroreCatalogo(errori)
    file = {}
    for prefisso, elenco in sorted(chiavi.items()):
        voci = catalogo[prefisso] if elenco else {}
        membri: dict[str, tuple[str, str]] = {}            # nome Swift → (chiave, dichiarazione)
        viste: dict[str, bool] = {}                         # chiave o base del plurale → è un plurale
        for chiave in elenco:
            unica, plurale = _voce_ios(chiave, voci)
            if unica in viste:
                if viste[unica] != plurale:                 # «oggi.x» e la coppia «oggi.x.one» / «oggi.x.other»
                    errori.append(f"ios/testi/{prefisso}.txt: «{unica}» e il plurale «{unica}.one» / «{unica}.other» darebbero "
                                  "lo stesso nome Swift: l'iPhone ne può elencare uno solo")
                continue                                    # la stessa voce scritta due volte (o la coppia del plurale)
            viste[unica] = plurale
            if plurale and "." not in unica:
                errori.append(f"ios/testi/{prefisso}.txt: «{unica}.one» / «{unica}.other» è un plurale senza nome dopo il "
                              f"prefisso e in Swift non ha un nome: rinomina la coppia nel catalogo (per esempio «{unica}.cose.one»)")
                continue
            nome, dichiarazione = _membro(unica, plurale, voci)
            if nome.strip("`") in ("", "_"):
                errori.append(f"ios/testi/{prefisso}.txt: «{unica}» non dà un nome Swift valido")
                continue
            if nome in membri:
                errori.append(f"ios/testi/{prefisso}.txt: «{membri[nome][0]}» e «{unica}» danno lo stesso nome Swift «{nome}»")
                continue
            membri[nome] = (unica, dichiarazione)
        if not membri:
            continue
        file[nome_file_swift(prefisso)] = (
            f"{TESTA_SWIFT}\n"
            f"// Testi da fanta/testi/{prefisso}.json, chiavi elencate in ios/testi/{prefisso}.txt.\n\n"
            f"extension Catalogo {{\n    enum {nome_tipo_swift(prefisso)} {{\n"
            + "\n\n".join(d for _, d in membri.values())
            + "\n    }\n}\n"
        )
    if errori:
        raise ErroreCatalogo(errori)
    if file:
        file["Catalogo.swift"] = (
            f"{TESTA_SWIFT}\n"
            "// I testi vengono dal catalogo fanta/testi/ (lo stesso della web); l'iPhone usa le chiavi elencate in ios/testi/.\n\n"
            "/// I testi dell'interfaccia in italiano, dal catalogo comune con la web (per esempio `Catalogo.Oggi.tuaFormazione`).\n"
            "enum Catalogo {}\n"
        )
    return file


# ---------------------------------------------------------------- comando

def _leggi(percorso: Path) -> str | None:
    try:
        return percorso.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except OSError:
        return None


def _scrivi(percorso: Path, testo: str) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with open(percorso, "w", encoding="utf-8", newline="\n") as f:
        f.write(testo)


def _swift_generati(cartella: Path) -> dict[str, str]:
    """I file Swift della cartella scritti da questo programma (riconosciuti dalla prima riga), per nome."""
    if not cartella.is_dir():
        return {}
    presenti = {p.name: _leggi(p) for p in sorted(cartella.glob("*.swift"))}
    return {n: t for n, t in presenti.items() if t is not None and t.startswith(TESTA_SWIFT)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    gruppo = ap.add_mutually_exclusive_group(required=True)
    gruppo.add_argument("--scrivi", action="store_true", help="rigenera testi.js e i file Swift dal catalogo")
    gruppo.add_argument("--controlla", action="store_true", help="controlla il catalogo e che i file generati siano aggiornati")
    ap.add_argument("--radice", default=str(RADICE), help="cartella del repository (per i test)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")       # console Windows con pagina di codici stretta
    radice = Path(a.radice)

    try:
        catalogo = carica_catalogo(radice / CATALOGO)
        attesi_swift = swift(catalogo, chiavi_ios(radice / ELENCHI_IOS))
        testo_js = _leggi(radice / TESTI_JS)
        if testo_js is None:
            raise ErroreCatalogo([f"{TESTI_JS.as_posix()}: file mancante o illeggibile"])
        prima, blocco, dopo = _dividi_testi_js(testo_js)
    except ErroreCatalogo as e:
        print("Testi da correggere:")
        for riga in e.errori:
            print(f"  - {riga}")
        return 1
    nuovo_blocco = blocco_testi_js(catalogo)
    cartella = radice / CARTELLA_SWIFT
    presenti = _swift_generati(cartella)

    if a.scrivi:
        cambiati = []
        if blocco != nuovo_blocco:
            _scrivi(radice / TESTI_JS, prima + nuovo_blocco + dopo)
            cambiati.append(TESTI_JS.as_posix())
        for nome, testo in attesi_swift.items():
            if presenti.get(nome) != testo:
                _scrivi(cartella / nome, testo)
                cambiati.append((CARTELLA_SWIFT / nome).as_posix())
        for nome in sorted(set(presenti) - set(attesi_swift)):
            (cartella / nome).unlink()
            cambiati.append(f"{(CARTELLA_SWIFT / nome).as_posix()} (tolto: nessuna chiave elencata)")
        print("Scritti: " + ", ".join(cambiati) + "." if cambiati else "Niente da cambiare: i file generati sono aggiornati.")
        return 0

    diversi = []
    if blocco != nuovo_blocco:
        diversi.append(f"{TESTI_JS.as_posix()}: il blocco fra le righe-segno non è quello del catalogo (cambiato a mano?)")
    for nome, testo in attesi_swift.items():
        if nome not in presenti:
            diversi.append(f"{(CARTELLA_SWIFT / nome).as_posix()}: manca")
        elif presenti[nome] != testo:
            diversi.append(f"{(CARTELLA_SWIFT / nome).as_posix()}: non è quello del catalogo")
    for nome in sorted(set(presenti) - set(attesi_swift)):
        diversi.append(f"{(CARTELLA_SWIFT / nome).as_posix()}: in più (nessuna chiave elencata in ios/testi/)")
    if diversi:
        print("File generati non aggiornati (i testi si scrivono in fanta/testi/, non nei file generati):")
        for riga in diversi:
            print(f"  - {riga}")
        print(RIFAI)
        return 1
    print("Testi a posto: catalogo valido e file generati aggiornati.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
