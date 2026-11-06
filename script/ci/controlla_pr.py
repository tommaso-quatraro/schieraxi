"""Controlli della PR che prima si facevano a occhio: descrizione, revisione registrata, novità solo della PR, test che
leggono una novità per nome. Bloccanti: se uno trova un problema il job «ambito» è rosso e «unisci» non parte.

Uso (job «ambito» di test.yml):  git diff --name-status HEAD^1 HEAD | python script/ci/controlla_pr.py [cartella dei test]
con le variabili d'ambiente AUTORE (login di chi ha aperto la PR), CORPO (descrizione della PR) e BOZZA («true» se è in
bozza). Il testo della PR arriva solo come variabile d'ambiente: non passa mai dentro un comando.
Esce con 0 se non ci sono problemi (gli avvisi non bloccano), con 1 se ce n'è almeno uno.

Funzioni pure, da importare anche altrove (`script/squadra/pr_pronta.py`) per percorso con importlib. Ognuna restituisce
una coppia `(problemi, avvisi)`: due liste di frasi in italiano; i problemi bloccano, gli avvisi no.
- `descrizione(corpo) -> (problemi, avvisi)`: le sezioni «## Cosa cambia», «## Perché», «## Come l'ho provato» ci sono e
  non sono vuote (i commenti HTML del modello non contano). Senza «Closes #N» né «Parte di #N»: solo un avviso.
- `revisione(corpo, bozza=False, autore="", file=()) -> (problemi, avvisi)`: fuori dalla bozza serve la sezione
  «## Revisione» con almeno una riga «- <chi>: <esito>». Esenti: le PR in bozza, dei bot (login che finisce con «[bot]»)
  e di soli documenti (`file`: i percorsi cambiati; soli documenti = tutti in docs/ o file .md).
- `novita(file_con_stato) -> (problemi, avvisi)`: in `fanta/novita.d/` al massimo un file, solo aggiunto (niente file di
  altre PR modificati, tolti o rinominati); `fanta/novita.json` non si tocca a mano (lo aggiorna il job «rilascia»).
  `file_con_stato`: tuple `(stato, percorso)` o `(stato, vecchio, nuovo)` per i rinominati; lo stato è la lettera di
  `git diff --name-status` (A, M, D, R100, …) o la parola dell'API di GitHub (added, modified, removed, renamed, …).
- `test_per_nome(cartella_tests) -> (problemi, avvisi)`: nessun file .py della cartella (anche nelle sottocartelle) apre
  un file `fanta/novita.d/<nome>.json` per nome: il job «rilascia» lo sposta in novita.json e il test diventa rosso su
  `main`. Si cerca la novità per titolo in novita.d e in novita.json, o si usa una novità finta in tests/dati/.
  Si guarda il codice senza eseguirlo (`ast`). Conta: un percorso `… / "fanta" / "novita.d" / <qualcosa>` o
  `… / "fanta/novita.d" / <qualcosa>`, la stringa (anche f-string) "fanta/novita.d/<nome>.json" in una catena `/` o in
  `open(…)`/`Path(…)`. Solo le letture: scritture e cancellazioni (write_text, mkdir, unlink, `open(…, "w")`…) no.
  Non conta una cartella novita.d di prova (`DATI / "novita.d" / "finta.json"`) né un `glob`. File illeggibile: avviso.
  Limiti noti (non li trova): `os.path.join(…)`, `.joinpath(…)`, la cartella messa prima in una variabile
  (`D = RADICE / "fanta" / "novita.d"` e poi `D / "x.json"`), nomi costruiti con `+`, `%` o `.format`, letture fatte
  da una funzione che riceve il nome come argomento.
- `controlla(corpo, bozza, autore, file_con_stato, cartella_tests) -> (problemi, avvisi)`: i quattro insieme; le PR dei bot
  sono esenti anche dalla descrizione.
- `leggi_name_status(testo) -> list[tuple]` e `percorsi(file_con_stato) -> list[str]`: aiuti per l'uscita di git."""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from pathlib import Path

SEZIONI = ("Cosa cambia", "Perché", "Come l'ho provato")
CARTELLA_D = "fanta/novita.d/"
REGISTRO = "fanta/novita.json"
_PAROLE_GITHUB = {"added": "A", "modified": "M", "changed": "M", "removed": "D", "renamed": "R", "copied": "C"}
_PERCORSI = {"open", "Path", "PurePath", "PosixPath", "WindowsPath"}
_SCRITTURE = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename", "replace", "symlink_to",
              "hardlink_to"}

Esito = tuple[list[str], list[str]]


# ---------------------------------------------------------------- aiuti

def _senza_commenti(corpo: str | None) -> str:
    return re.sub(r"<!--.*?(?:-->|\Z)", "", corpo or "", flags=re.S)


def _semplice(titolo: str) -> str:
    """Titolo di sezione confrontabile: minuscole, apostrofo dritto, senza punteggiatura finale né spazi doppi."""
    t = titolo.replace("’", "'").strip().rstrip(":.").strip().lower()
    return re.sub(r"\s+", " ", t)


def _sezioni(corpo: str | None) -> dict[str, str]:
    """{titolo semplificato: testo} per ogni titolo Markdown («#» … «######») fuori dai commenti HTML.
    Il testo di una sezione va fino al primo titolo di livello uguale o più alto: i sottotitoli («###» sotto un «##») ne
    fanno parte. Titoli ripetuti: vale il primo.
    Un blocco di codice (```) conta come testo, e un «# commento» lì dentro non è un titolo."""
    testo = re.sub(r"^[ \t]*(```|~~~).*?(?:^[ \t]*\1[ \t]*\r?$|\Z)", "[codice]", _senza_commenti(corpo), flags=re.S | re.M)
    teste = list(re.finditer(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t#]*\r?$", testo, re.M))
    sezioni: dict[str, str] = {}
    for i, m in enumerate(teste):
        livello = len(m.group(1))
        fine = next((t.start() for t in teste[i + 1:] if len(t.group(1)) <= livello), len(testo))
        sezioni.setdefault(_semplice(m.group(2)), testo[m.end():fine])
    return sezioni


def _bot(autore: str) -> bool:
    return (autore or "").endswith("[bot]")


def _carica(nome: str):
    """Un altro script di questa cartella, per percorso (in CI tutti e due vengono da _ci-main/script/ci; `python -I` non
    mette la cartella dello script fra quelle degli import)."""
    spec = importlib.util.spec_from_file_location(Path(nome).stem, Path(__file__).with_name(nome))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_soli_documenti = _carica("controlla_ambito.py").solo_documenti      # definizione unica di «soli documenti»


def leggi_name_status(testo: str) -> list[tuple[str, ...]]:
    """Righe di `git diff --name-status` (separate da tabulazioni) in tuple: (stato, percorso) o (stato, vecchio, nuovo)."""
    return [tuple(r.split("\t")) for r in (testo or "").splitlines() if r.strip()]


def percorsi(file_con_stato) -> list[str]:
    """Tutti i percorsi toccati (per un file rinominato, il vecchio e il nuovo)."""
    return [p for voce in file_con_stato for p in voce[1:]]


# ---------------------------------------------------------------- i quattro controlli

def descrizione(corpo: str | None) -> Esito:
    sezioni = _sezioni(corpo)
    problemi = []
    for nome in SEZIONI:
        chiave = _semplice(nome)
        if chiave not in sezioni:
            problemi.append(f"manca la sezione «## {nome}» nella descrizione della PR")
        elif not sezioni[chiave].strip():
            problemi.append(f"la sezione «## {nome}» è vuota: scrivi cosa c'è da sapere")
    avvisi = []
    if not re.search(r"\b(?:closes|fixes|resolves|parte di)\s+#\d+", _senza_commenti(corpo), re.I):
        avvisi.append("nessuna issue collegata: scrivi «Closes #N» (o «Parte di #N»); senza issue solo le correzioni di una riga")
    return problemi, avvisi


def revisione(corpo: str | None, bozza: bool = False, autore: str = "", file=()) -> Esito:
    if bozza or _bot(autore) or _soli_documenti(file):
        return [], []
    sezioni = _sezioni(corpo)
    if "revisione" not in sezioni:
        return ["manca la sezione «## Revisione»: chi ha rivisto il ramo e con che esito, una riga per revisione "
                "(«- revisore: nessun rilievo bloccante»)"], []
    righe = re.findall(r"^[ \t]*[-*][ \t]+([^:\n]*\S[^:\n]*?)[ \t]*:[ \t]*(\S.*)$", sezioni["revisione"], re.M)
    if not righe:
        return ["la sezione «## Revisione» non ha righe «- <chi>: <esito>» (per esempio «- revisore: nessun rilievo bloccante»)"], []
    return [], []


def _stato(voce: tuple[str, ...]) -> str:
    s = voce[0].strip()
    return _PAROLE_GITHUB.get(s.lower(), s[:1].upper())


def novita(file_con_stato) -> Esito:
    problemi, aggiunti = [], []
    for voce in file_con_stato:
        stato, toccati = _stato(voce), voce[1:]
        if REGISTRO in toccati:
            problemi.append(f"{REGISTRO} non si tocca a mano: lo aggiorna il job «rilascia»; la novità va in un file "
                            f"{CARTELLA_D}<nome-breve>.json")
        in_d = [p for p in toccati if p.startswith(CARTELLA_D)]
        if not in_d:
            continue
        if stato == "A" and len(toccati) == 1:
            aggiunti.append(in_d[0])
        else:
            problemi.append(f"{' → '.join(toccati)}: in {CARTELLA_D} si aggiunge solo il file della PR; quelli che ci sono "
                            "già sono di altre PR (li sposta il job «rilascia») e non si modificano, tolgono o rinominano")
    if len(aggiunti) > 1:
        problemi.append(f"in {CARTELLA_D} un solo file per PR, qui sono {len(aggiunti)}: {', '.join(aggiunti)}")
    return problemi, []


def _pezzi_div(nodo: ast.AST) -> list[ast.AST]:
    """Gli operandi di una catena `a / b / c` (percorsi di pathlib), da sinistra a destra."""
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
        return _pezzi_div(nodo.left) + [nodo.right]
    return [nodo]


def _testo(nodo: ast.AST) -> str | None:
    """Il testo di una stringa costante; di una f-string, le parti fisse con «{}» al posto di ogni valore."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in nodo.values)
    return None


def _nome_novita(testo: str | None) -> bool:
    """«fanta/novita.d/<nome>.json» (anche con «{}» di una f-string nel nome), non un glob."""
    return bool(testo) and re.search(r"(?:^|/)fanta/novita\.d/[^/*?\[]+\.json$", testo) is not None


def _cartella_novita(pezzi: list[ast.AST], i: int) -> bool:
    """Il pezzo i della catena è la cartella fanta/novita.d del repository: «fanta/novita.d», oppure «novita.d» subito dopo
    «fanta». Una cartella novita.d di prova (tests/dati/novita.d) non conta."""
    t = _testo(pezzi[i])
    if t is None:
        return False
    if re.search(r"(?:^|/)fanta/novita\.d/?$", t):
        return True
    prima = _testo(pezzi[i - 1]) if i > 0 else None
    return t.strip("/") == "novita.d" and prima is not None and re.search(r"(?:^|/)fanta/?$", prima) is not None


def _modo_scrittura(chiamata: ast.Call) -> bool:
    """open(…, "w"/"a"/"x"/"+"): il modo è il secondo argomento o «mode=»."""
    modo = chiamata.args[1] if len(chiamata.args) > 1 else next((k.value for k in chiamata.keywords if k.arg == "mode"), None)
    t = _testo(modo) if modo is not None else None
    return bool(t) and any(c in t for c in "wax+")


def _scritto(nodo: ast.AST, genitori: dict) -> bool:
    """Il percorso si usa per scrivere o togliere (write_text, mkdir, unlink, open in scrittura…), non per leggere."""
    su = genitori.get(nodo)
    if isinstance(su, ast.Attribute) and su.value is nodo:
        return su.attr in _SCRITTURE
    if isinstance(su, ast.Call) and nodo in su.args and _nome_funzione(su) == "open":
        return _modo_scrittura(su)
    return False


def _nome_funzione(chiamata: ast.Call) -> str:
    f = chiamata.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def _letture_per_nome(albero: ast.AST) -> list[int]:
    genitori = {figlio: nodo for nodo in ast.walk(albero) for figlio in ast.iter_child_nodes(nodo)}
    righe = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
            su = genitori.get(nodo)
            if isinstance(su, ast.BinOp) and isinstance(su.op, ast.Div) and su.left is nodo:
                continue                     # solo la catena intera «a / b / c», non i suoi pezzi
            pezzi = _pezzi_div(nodo)
            per_nome = any(_nome_novita(_testo(p)) or (_cartella_novita(pezzi, i) and i < len(pezzi) - 1)
                           for i, p in enumerate(pezzi))
            if per_nome and not _scritto(nodo, genitori):
                righe.add(nodo.lineno)
        elif isinstance(nodo, ast.Call) and _nome_funzione(nodo) in _PERCORSI:
            if any(_nome_novita(_testo(a)) for a in nodo.args):
                scrive = _modo_scrittura(nodo) if _nome_funzione(nodo) == "open" else _scritto(nodo, genitori)
                if not scrive:
                    righe.add(nodo.lineno)
    return sorted(righe)


def test_per_nome(cartella_tests) -> Esito:
    cartella = Path(cartella_tests)
    problemi, avvisi = [], []
    for file in sorted(cartella.rglob("*.py")):
        nome = file.relative_to(cartella.parent).as_posix() if cartella.parent != cartella else file.name
        try:
            albero = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except (OSError, SyntaxError, ValueError) as e:
            avvisi.append(f"{nome}: non riesco a leggerlo per cercare le novità lette per nome ({e.__class__.__name__})")
            continue
        for riga in _letture_per_nome(albero):
            problemi.append(f"{nome}:{riga} legge una novità di {CARTELLA_D} per nome: dopo il rilascio il file non c'è "
                            "più e il test diventa rosso su main. Cerca la novità per titolo in novita.d e in novita.json, "
                            "o usa una novità finta in tests/dati/")
    return problemi, avvisi


def controlla(corpo: str | None, bozza: bool, autore: str, file_con_stato, cartella_tests) -> Esito:
    problemi, avvisi = [], []
    for p, a in _tutti(corpo, bozza, autore, file_con_stato, cartella_tests).values():
        problemi += p
        avvisi += a
    return problemi, avvisi


def _tutti(corpo, bozza, autore, file_con_stato, cartella_tests) -> dict[str, Esito]:
    file_con_stato = list(file_con_stato)
    return {
        "Descrizione della PR": ([], []) if _bot(autore) else descrizione(corpo),
        "Revisione": revisione(corpo, bozza, autore, percorsi(file_con_stato)),
        "Novità": novita(file_con_stato),
        "Test e novità": test_per_nome(cartella_tests),
    }


# ---------------------------------------------------------------- uscita per GitHub Actions

def _una_riga(testo: str) -> str:
    return " ".join(str(testo).split())


def main(autore: str, corpo: str, bozza: str, name_status: str, cartella_tests) -> int:
    esiti = _tutti(corpo, (bozza or "").strip().lower() == "true", autore, leggi_name_status(name_status), cartella_tests)
    totale = 0
    for titolo, (problemi, avvisi) in esiti.items():
        for p in problemi:
            print(f"::error title={titolo}::{_una_riga(p)}")
        for a in avvisi:
            print(f"::warning title={titolo}::{_una_riga(a)}")
        totale += len(problemi)
    if totale:
        print(f"Controlli della PR: {totale} problemi da sistemare (sopra). Dopo aver corretto la descrizione, i controlli "
              "si rifanno al push successivo o togliendo e rimettendo la bozza.")
        return 1
    print("Controlli della PR: tutto a posto (descrizione, revisione, novità, test).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(os.environ.get("AUTORE", ""), os.environ.get("CORPO", ""), os.environ.get("BOZZA", ""),
                  sys.stdin.read(), sys.argv[1] if len(sys.argv) > 1 else "tests"))
