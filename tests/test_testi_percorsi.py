"""Nessun testo che l'utente vede indica le schede di prima. Con la barra a tre voci (Formazione, Giornate, Impostazioni: web
#675, iPhone #710) le schede «Lega», «Squadra» e «Altro» non ci sono più: rose, regole, account e stato dei dati stanno in
Impostazioni. Un percorso come «Lega > Account» in un avviso, in un'email o in una pagina manda l'utente a cercare una cosa che non
trova.

Si leggono i testi, non le righe: il catalogo comune (`fanta/testi/`), le stringhe del server (con `ast`, così i commenti restano
fuori), i contenuti (`fanta/contenuti/`), le stringhe dell'app per iPhone e dei widget fuori dai commenti, la guida per l'utente e
la versione leggibile di «Sotto il cofano». Le novità già uscite (`fanta/novita.json`) no: raccontano com'era l'app quel giorno."""
import ast
import json
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# «Lega > Regole», «Altro › Regole», «League > Rules»: il nome di una scheda tolta seguito da una freccia
PERCORSO_VECCHIO = re.compile(r"(?<!\w)(Lega|Squadra|Altro|League|Team|More)\s*(>|›|→|&gt;|&rsaquo;)")
DOCUMENTI = ("docs/GUIDA-UTENTE.md", "docs/SOTTO-IL-COFANO.md")


def voci_catalogo(cartella: Path = RADICE / "fanta" / "testi"):
    for f in sorted(cartella.glob("*.json")):
        for chiave, voce in json.loads(f.read_text(encoding="utf-8")).items():
            for lingua in ("it", "en"):
                if isinstance(voce, dict) and isinstance(voce.get(lingua), str):
                    yield f"{f.name}:{chiave}:{lingua}", voce[lingua]


def stringhe_python(cartella: Path = RADICE / "fanta"):
    for f in sorted(cartella.rglob("*.py")):
        albero = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                yield f"{f.relative_to(RADICE).as_posix()}:{nodo.lineno}", nodo.value


def _stringhe_json(x, dove: str):
    if isinstance(x, str):
        yield dove, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _stringhe_json(v, f"{dove}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _stringhe_json(v, f"{dove}[{i}]")


def stringhe_contenuti(cartella: Path = RADICE / "fanta" / "contenuti"):
    for f in sorted(cartella.glob("*.json")):
        yield from _stringhe_json(json.loads(f.read_text(encoding="utf-8")), f.name)


_LETTERALE_SWIFT = re.compile(r'"""(.*?)"""|"((?:[^"\\\n]|\\.)*)"|(//[^\n]*)|(/\*.*?\*/)', re.S)


def letterali_swift(codice: str):
    """Le stringhe di un sorgente Swift, saltando i commenti (`//`, `///`, `/* */`): un «//» dentro una stringa resta stringa."""
    for m in _LETTERALE_SWIFT.finditer(codice):
        testo = m.group(1) if m.group(1) is not None else m.group(2)
        if testo is not None:
            yield codice.count("\n", 0, m.start()) + 1, testo


def stringhe_swift(cartelle=(RADICE / "ios" / "Sources", RADICE / "ios" / "WidgetSources")):
    for cartella in cartelle:
        for f in sorted(cartella.rglob("*.swift")):
            for riga, testo in letterali_swift(f.read_text(encoding="utf-8")):
                yield f"{f.relative_to(RADICE).as_posix()}:{riga}", testo


def righe_documenti():
    for nome in DOCUMENTI:
        for n, riga in enumerate((RADICE / nome).read_text(encoding="utf-8").splitlines(), 1):
            yield f"{nome}:{n}", riga


def percorsi_vecchi(testi) -> list[str]:
    """Una riga per testo sbagliato: dove sta e il pezzo intorno alla freccia."""
    trovati = []
    for dove, testo in testi:
        if m := PERCORSO_VECCHIO.search(testo):
            pezzo = " ".join(testo[max(0, m.start() - 60):m.end() + 40].split())
            trovati.append(f"{dove}: «…{pezzo}…»")
    return trovati


def test_il_catalogo_non_indica_le_schede_di_prima():
    trovati = percorsi_vecchi(voci_catalogo())
    assert not trovati, "\n".join(trovati)


def test_il_server_non_indica_le_schede_di_prima():
    """Errori, avvisi sul telefono, email, descrizioni delle rotte: tutto ciò che il server scrive."""
    trovati = percorsi_vecchi(stringhe_python()) + percorsi_vecchi(stringhe_contenuti())
    assert not trovati, "\n".join(trovati)


def test_l_iphone_e_i_widget_non_indicano_le_schede_di_prima():
    trovati = percorsi_vecchi(stringhe_swift())
    assert not trovati, "\n".join(trovati)


def test_guida_e_sotto_il_cofano_non_indicano_le_schede_di_prima():
    trovati = percorsi_vecchi(righe_documenti())
    assert not trovati, "\n".join(trovati)


def test_il_controllo_vede_le_frecce_e_salta_i_commenti_swift():
    for buono in ("Lega > Account", "Altro › Regole", "Squadra >Seguiti", "League > Rules", "in Lega &gt; Crediti"):
        assert PERCORSO_VECCHIO.search(buono), buono
    for giusto in ("Impostazioni > Il tuo account", "Impostazioni › Regole e scadenza", "La mia squadra", "Lega Serie A", "Squadra salvata"):
        assert not PERCORSO_VECCHIO.search(giusto), giusto
    codice = ('/// Altro › Regole nel commento\nlet a = "Vai in Squadra > Seguiti" // Lega > Account\n'
              'let b = "http://esempio" /* Altro > Diario */\nlet c = """\nLega › Crediti\n"""\n')
    assert [t for _, t in letterali_swift(codice)] == ["Vai in Squadra > Seguiti", "http://esempio", "\nLega › Crediti\n"]
    assert len(percorsi_vecchi(("x", t) for _, t in letterali_swift(codice))) == 2
