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
  Le cartelle temporanee (un percorso che parte da `tmp_path`, `tmpdir`, …) sono ammesse. File illeggibile: avviso.
- `controlla(corpo, bozza, autore, file_con_stato, cartella_tests) -> (problemi, avvisi)`: i quattro insieme; le PR dei bot
  sono esenti anche dalla descrizione.
- `leggi_name_status(testo) -> list[tuple]` e `percorsi(file_con_stato) -> list[str]`: aiuti per l'uscita di git."""
from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

SEZIONI = ("Cosa cambia", "Perché", "Come l'ho provato")
CARTELLA_D = "fanta/novita.d/"
REGISTRO = "fanta/novita.json"
_PAROLE_GITHUB = {"added": "A", "modified": "M", "changed": "M", "removed": "D", "renamed": "R", "copied": "C"}
_LETTURE = {"open", "Path", "PurePath", "PosixPath", "WindowsPath", "read_text", "read_bytes"}

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
    Il testo di una sezione va fino al titolo successivo, di qualunque livello. Titoli ripetuti: vale il primo.
    Un blocco di codice (```) conta come testo, e un «# commento» lì dentro non è un titolo."""
    testo = re.sub(r"^[ \t]*(```|~~~).*?(?:^[ \t]*\1[ \t]*\r?$|\Z)", "[codice]", _senza_commenti(corpo), flags=re.S | re.M)
    teste = list(re.finditer(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t#]*\r?$", testo, re.M))
    sezioni: dict[str, str] = {}
    for i, m in enumerate(teste):
        fine = teste[i + 1].start() if i + 1 < len(teste) else len(testo)
        sezioni.setdefault(_semplice(m.group(1)), testo[m.end():fine])
    return sezioni


def _bot(autore: str) -> bool:
    return (autore or "").endswith("[bot]")


def _soli_documenti(file) -> bool:
    file = list(file)
    return bool(file) and all(f.startswith("docs/") or f.lower().endswith(".md") for f in file)


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
    return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else None


def _nome_novita(testo: str | None) -> bool:
    return bool(testo) and re.search(r"(?:^|/)novita\.d/[^/*?\[]+\.json$", testo) is not None


def _temporaneo(nodo: ast.AST) -> bool:
    while isinstance(nodo, (ast.Attribute, ast.Call)):
        nodo = nodo.value if isinstance(nodo, ast.Attribute) else nodo.func
    return isinstance(nodo, ast.Name) and "tmp" in nodo.id.lower()


def _letture_per_nome(albero: ast.AST) -> list[int]:
    righe = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
            pezzi = _pezzi_div(nodo)
            if _temporaneo(pezzi[0]):
                continue
            for i, p in enumerate(pezzi):
                t = _testo(p)
                if _nome_novita(t) or (t is not None and re.search(r"(?:^|/)novita\.d$", t) and i < len(pezzi) - 1):
                    righe.add(nodo.lineno)
        elif isinstance(nodo, ast.Call):
            f = nodo.func
            nome = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if nome in _LETTURE and any(_nome_novita(_testo(a)) for a in nodo.args):
                righe.add(nodo.lineno)
    # una catena «a / b / c» è anche fatta di catene più corte: una riga sola per lettura
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
