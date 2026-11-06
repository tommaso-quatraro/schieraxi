"""Prepara il carattere dei numeri e dei titoli della web app: Archivo semi-stretto (SIL OFL 1.1) in woff2, servito dal server.

Dal file variabile di Google Fonts (`ofl/archivo/Archivo[wdth,wght].ttf` di github.com/google/fonts) tiene:
  - larghezza fissa 87,5 (semi-stretta, la stessa del sito) e peso variabile da 400 a 700;
  - solo le lettere di LETTERE (latino occidentale, virgolette, trattini, puntini, meno tipografico di «−0,4»);
  - le cifre tabellari (`tnum`, da chiedere: il sottoinsieme di norma le toglie) e le maiuscole delle cifre (`lnum`);
  - tutti i nomi del file, compresi il copyright e la licenza (nomi 0, 13 e 14: la OFL chiede che restino).
Scrive `fanta/web/caratteri/archivo.woff2` (accanto c'è `OFL.txt`) e stampa `byte=<n> tnum=<sì|no> licenza=<sì|no>`;
esce con 1 se nel file mancano le cifre tabellari o la licenza.

Strumento per chi rifà il file, non serve per far girare l'app. In un ambiente a parte:
    python -m venv .venv-carattere
    .venv-carattere\\Scripts\\python.exe -m pip install fonttools brotli
    .venv-carattere\\Scripts\\python.exe script\\carattere_web.py <cartella>\\Archivo[wdth,wght].ttf
Opzioni: --uscita PERCORSO (scrive altrove), --controlla FILE.woff2 (solo il controllo, senza scrivere niente).
Dopo: annota nella pull request il commit di google/fonts e lo SHA-256 del file di partenza.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "fanta" / "web" / "caratteri" / "archivo.woff2"
ASSI = {"wdth": 87.5, "wght": (400, 700)}

# Lettere della spec della grafica (docs/superpowers/specs/2026-11-05-grafica-web-b-design.md, §16). La spec nomina anche
# U+201B (virgoletta alta rovesciata) e U+202F (spazio stretto unificatore): Archivo 2.001 non li ha, il browser li prende dal
# carattere di sistema.
LETTERE = [(0x20, 0x7E), (0xA0, 0xFF), (0x131, 0x131), (0x152, 0x153), (0x2009, 0x2009), (0x2013, 0x2014), (0x2018, 0x201A),
           (0x201C, 0x201E), (0x2022, 0x2022), (0x2026, 0x2026), (0x2212, 0x2212)]
OPZIONI_SOTTOINSIEME = ["--flavor=woff2", "--layout-features+=tnum,lnum", "--name-IDs=*"]


def codici() -> list[int]:
    return [c for inizio, fine in LETTERE for c in range(inizio, fine + 1)]


def genera(sorgente: Path, uscita: Path = USCITA) -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(sorgente, recalcTimestamp=False)      # data del file di partenza: stesso file di partenza = stessi byte
    assi = {a.axisTag for a in font["fvar"].axes} if "fvar" in font else set()
    famiglia = font["name"].getDebugName(16) or font["name"].getDebugName(1) or ""
    if not famiglia.startswith("Archivo") or not set(ASSI) <= assi:
        raise ValueError(f"{sorgente.name} non è Archivo variabile con gli assi wdth e wght")
    istanza = instancer.instantiateVariableFont(font, ASSI)
    opzioni = subset.Options()
    opzioni.parse_opts(OPZIONI_SOTTOINSIEME)
    riduttore = subset.Subsetter(options=opzioni)
    riduttore.populate(unicodes=codici())
    riduttore.subset(istanza)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    subset.save_font(istanza, str(uscita), opzioni)


def cifre_tabellari(font) -> bool:
    """Vero se la funzione `tnum` porta le cifre 0-9 a disegni tutti della stessa larghezza (colonne di numeri allineate)."""
    if "GSUB" not in font:
        return False
    gsub = font["GSUB"].table
    indici = {i for r in gsub.FeatureList.FeatureRecord if r.FeatureTag == "tnum" for i in r.Feature.LookupListIndex}
    mappa: dict[str, str] = {}
    for i in sorted(indici):
        lookup = gsub.LookupList.Lookup[i]
        for parte in lookup.SubTable:
            parte = parte.ExtSubTable if lookup.LookupType == 7 else parte
            mappa.update(getattr(parte, "mapping", None) or {})
    cmap = font.getBestCmap()
    if not mappa or any(c not in cmap for c in range(0x30, 0x3A)):
        return False
    larghezze = {font["hmtx"][mappa.get(cmap[c], cmap[c])][0] for c in range(0x30, 0x3A)}
    return len(larghezze) == 1


def controlla(percorso: Path) -> dict:
    """Cosa c'è dentro il file: byte, cifre tabellari, licenza, lettere che mancano, assi rimasti (nome -> (minimo, massimo))."""
    from fontTools.ttLib import TTFont

    font = TTFont(percorso)
    licenza = font["name"].getDebugName(13) or ""
    presenti = set(font.getBestCmap())
    return {"byte": percorso.stat().st_size,
            "tnum": cifre_tabellari(font),
            "licenza": "SIL Open Font License" in licenza and bool(font["name"].getDebugName(0)),
            "mancanti": [f"U+{c:04X}" for c in codici() if c not in presenti],
            "assi": {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes} if "fvar" in font else {}}


def principale(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Archivo semi-stretto in woff2 per la web app.")
    p.add_argument("sorgente", nargs="?", type=Path, help="Archivo[wdth,wght].ttf di google/fonts")
    p.add_argument("--uscita", type=Path, default=USCITA)
    p.add_argument("--controlla", type=Path, help="controlla un woff2 già fatto, senza scrivere niente")
    a = p.parse_args(argv)
    if a.controlla is None and a.sorgente is None:
        p.error("serve il file di partenza oppure --controlla")
    if a.controlla is None:
        try:
            genera(a.sorgente, a.uscita)
        except (OSError, ValueError) as e:
            print(f"Non riesco a preparare il carattere: {e}", file=sys.stderr)
            return 2
    esito = controlla(a.controlla or a.uscita)
    print(f"byte={esito['byte']} tnum={'sì' if esito['tnum'] else 'no'} licenza={'sì' if esito['licenza'] else 'no'}")
    if esito["mancanti"]:
        print("lettere mancanti: " + " ".join(esito["mancanti"]), file=sys.stderr)
    return 0 if esito["tnum"] and esito["licenza"] else 1


if __name__ == "__main__":
    sys.exit(principale(sys.argv[1:]))
