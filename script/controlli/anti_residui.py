#!/usr/bin/env python3
"""Controllo dei residui nel repository: dati personali, nomi vecchi, indirizzi della rete privata, segreti.

Uso (dalla cartella del repository):
    python script/controlli/anti_residui.py --albero          tutti i file tracciati (la usa la CI)
    python script/controlli/anti_residui.py --staged          solo cio' che e' in preparazione (la usa l'hook pre-commit)
    python script/controlli/anti_residui.py --storia          tutti i commit: autori, messaggi, righe aggiunte
    python script/controlli/anti_residui.py --file PERCORSO   file scelti

Parole vietate PRIVATE (i nomi veri): un file fuori da git, una parola per riga, # per i commenti. Di default
%USERPROFILE%\\Backup-privati\\parole-vietate.txt, oppure il percorso scritto in SCHIERAXI_NOMI_VIETATI.
Il controllo non stampa mai le parole private: dice solo in quale file e riga compaiono.
Esce con 1 se trova qualcosa, con 0 se e' pulito. Non usa la rete e non modifica nulla.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent

# Questi due file contengono le regole stesse: non si controllano per il contenuto (si controllano per il nome).
ESENTI = {"script/controlli/anti_residui.py", "script/controlli/test_anti_residui.py"}

# ---- nomi vecchi dell'app: si costruiscono a pezzi, cosi' non compaiono in chiaro nel repository ----
_NOME_A = "fanta" + "claude"
_NOME_B = "und" + "ici"
_NOME_C = "titolar" + "xi"
NOME_VECCHIO = re.compile(
    rf"(?i:{_NOME_A}|{_NOME_C})|it\.{_NOME_B}|{_NOME_B.capitalize()}|{_NOME_B.upper()}|{_NOME_B}[_.:/-]|[_.-]{_NOME_B}|{_NOME_B}1")
# Falsi allarmi: il numero (gli undici titolari), non il nome vecchio dell'app
FALSI_ALLARMI = [re.compile(rf"chiede_{_NOME_B}_titolari"), re.compile(rf"{_NOME_B}_titolari"),
                 re.compile(rf"stessi {_NOME_B}:")]

# ---- regole sulle righe ----
REGOLE_RIGA: list[tuple[str, re.Pattern]] = [
    ("percorso di una cartella del PC", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]")),
    ("email personale", re.compile("quatra" + "ro@|tommaso" + "quatraro", re.I)),
    ("nome utente personale", re.compile("thebest" + "ofmario", re.I)),
    ("runner propri o pull_request_target", re.compile(r"self-hosted|RUNNER_(?:TEST_|PRIVILEGIATO_)?JSON|pull_request_target")),
    ("token GitHub", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}")),
    ("chiave privata", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("chiave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chiave Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("token Slack", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}")),
    ("chiave tipo sk-", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("apiKey nell'indirizzo", re.compile(r"[?&]api_?[Kk]ey=[A-Za-z0-9]{16,}")),
    ("canale ntfy", re.compile(r"ntfy\.sh/[A-Za-z0-9_-]{6,}")),
    ("Authorization con valore lungo", re.compile(r"Bearer\s+[A-Za-z0-9._-]{30,}")),
]
TSNET = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.ts\.net", re.I)
INFRASTRUTTURA = re.compile("tail" + "scale|tail" + "net|/home/pi\\b|rasp" + "berry", re.I)
# Eccezioni SCRITTE: file che nominano l'infrastruttura per spiegare o per provare che non compare nei testi dell'app
ECCEZIONI_INFRASTRUTTURA = {
    "README.md": "il server e' nominato come esempio di computer piccolo per chi installa l'app (hardware generico)",
    "tests/test_testi_web.py": "prova che nei testi dell'app non compaia piu' la rete privata",
    "tests/test_scambi_web.py": "prova che nei testi degli scambi non compaia piu' la rete privata",
    "tests/test_limiti.py": "prova che il messaggio di limite non consigli la rete privata",
    "tests/test_impostazioni_web.py": "elenco di parole tecniche vietate nei testi dell'app",
}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.([A-Za-z]{2,})")
ESTENSIONI_FINTE = {"png", "jpg", "jpeg", "webp", "svg", "gif", "json", "js", "py", "swift", "kt", "html", "css", "txt", "ico"}
# indirizzi pubblici di servizio, ammessi ovunque: il committer dei commit fatti da GitHub (unioni, modifiche dal web),
# il contatto di GitHub citato nei documenti e la firma «Co-Authored-By» dei commit scritti con Claude Code
INDIRIZZI_DI_SERVIZIO = {"noreply@github.com", "support@github.com", "noreply@anthropic.com"}
EMAIL_AMMESSA = re.compile(r"noreply\.github\.com$|^(?:" + "|".join(re.escape(x) for x in sorted(INDIRIZZI_DI_SERVIZIO)) + r")$", re.I)     # indirizzi ammessi come autore o committer

ESTENSIONI_BINARIE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".jar", ".zip", ".gz", ".ttf", ".woff", ".woff2",
                      ".sqlite", ".db", ".pdf", ".icns", ".ipa", ".apk", ".keystore"}


def parole_private(percorso: Path | None = None) -> list[tuple[str, re.Pattern]]:
    """Le parole dell'elenco privato (fuori da git). Se il file manca il controllo gira lo stesso, senza di esse."""
    if percorso is None:
        scelto = os.environ.get("SCHIERAXI_NOMI_VIETATI")
        percorso = Path(scelto) if scelto else Path(os.environ.get("USERPROFILE") or str(Path.home())) / "Backup-privati" / "parole-vietate.txt"
    if not percorso.is_file():
        return []
    parole = []
    for riga in percorso.read_text(encoding="utf-8", errors="replace").splitlines():
        parola = riga.strip()
        if parola and not parola.startswith("#") and len(parola) >= 3:
            parole.append(("parola dell'elenco privato", regola_parola(parola)))
    return parole


# tra le parole di un nome: spazio, o le sue forme negli indirizzi e nei nomi di file («%20», «+», «-», «_»), o niente
SEPARATORE = r"(?:\s+|%20|\+|-|_)?"


def regola_parola(parola: str) -> re.Pattern:
    """La parola (senza badare alle maiuscole) anche scritta in un indirizzo o in un nome di file: «Mario Rossi» trova
    anche «mario%20rossi», «Mario+Rossi», «mario-rossi», «mario_rossi», «MarioRossi»."""
    pezzi = [re.escape(p) for p in re.split(r"[\s_+-]+|%20", parola) if p]
    return re.compile(SEPARATORE.join(pezzi), re.I)


def nome_vecchio_in(testo: str) -> bool:
    for falso in FALSI_ALLARMI:
        testo = falso.sub("", testo)
    return bool(NOME_VECCHIO.search(testo))


def scansiona_riga(rel: str, riga: str, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    trovati = []
    for etichetta, regola in [*REGOLE_RIGA, *parole]:
        if regola.search(riga):
            trovati.append(etichetta)
    if nome_vecchio_in(riga):
        trovati.append("nome vecchio dell'app")
    if rel not in ECCEZIONI_INFRASTRUTTURA and INFRASTRUTTURA.search(riga):
        trovati.append("infrastruttura personale (rete privata o dispositivo)")
    for m in TSNET.finditer(riga):
        if "example" not in m.group(0).lower():
            trovati.append("indirizzo *.ts.net vero")
    for m in EMAIL.finditer(riga):
        indirizzo = m.group(0).lower()
        if m.group(1).lower() in ESTENSIONI_FINTE or "noreply.github.com" in indirizzo or indirizzo in INDIRIZZI_DI_SERVIZIO:
            continue
        if re.search(r"\.(invalid|example|test)$|@example\.(com|org|net)$|tuodominio\.it$|@x\.it$|@schieraxi\.it$", indirizzo):
            continue                    # indirizzi di prova (RFC 2606), segnaposto e il contatto pubblico del progetto
        if rel.startswith(("tests/", "Tests/")):
            continue                    # fixture dei test: inventate per costruzione (i nomi veri li copre l'elenco privato)
        trovati.append("email non ammessa (non noreply, non di prova)")
    return trovati


def scansiona_nome(rel: str, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    """Il nome di un file o di una cartella non deve contenere nomi vecchi o parole private."""
    trovati = []
    for etichetta, regola in parole:
        if regola.search(rel):
            trovati.append(f"{rel}: {etichetta} nel nome del file")
    if nome_vecchio_in(rel):
        trovati.append(f"{rel}: nome vecchio dell'app nel nome del file")
    return trovati


def scansiona_testo(rel: str, testo: bytes, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    """Problemi di un file (testo) con numero di riga. I file binari e i due file di questo controllo si saltano."""
    if rel in ESENTI or b"\x00" in testo:
        return []
    problemi = []
    for n, riga in enumerate(testo.decode("utf-8", errors="replace").splitlines(), 1):
        for voce in sorted(set(scansiona_riga(rel, riga, parole))):
            problemi.append(f"{rel}:{n}: {voce}")
    return problemi


def file_da_cartella(radice: Path) -> list[str]:
    """Tutti i file della cartella (senza .git), per quando il repository non e' un repository git."""
    risultato = []
    for p in sorted(radice.rglob("*")):
        if not p.is_file() or ".git" in p.relative_to(radice).parts:
            continue
        risultato.append(p.relative_to(radice).as_posix())
    return risultato


def git(radice: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(radice), *args], capture_output=True)


def controlla_albero(radice: Path, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    r = git(radice, "ls-files", "-z")
    elenco = [p for p in r.stdout.decode("utf-8", errors="replace").split("\0") if p] if r.returncode == 0 else file_da_cartella(radice)
    problemi = []
    for rel in elenco:
        problemi += scansiona_nome(rel, parole)
        p = radice / rel
        if p.suffix.lower() in ESTENSIONI_BINARIE or not p.is_file():
            continue
        problemi += scansiona_testo(rel, p.read_bytes(), parole)
    return problemi


def controlla_staged(radice: Path, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    r = git(radice, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    if r.returncode:
        raise SystemExit("non sono in un repository git: " + r.stderr.decode("utf-8", errors="replace").strip())
    problemi = []
    for rel in [p for p in r.stdout.decode("utf-8", errors="replace").split("\0") if p]:
        problemi += scansiona_nome(rel, parole)
        if Path(rel).suffix.lower() in ESTENSIONI_BINARIE:
            continue
        blob = git(radice, "show", f":{rel}")                  # il contenuto che va davvero nel commit
        if blob.returncode == 0:
            problemi += scansiona_testo(rel, blob.stdout, parole)
    return problemi


def controlla_storia(radice: Path, parole: list[tuple[str, re.Pattern]]) -> list[str]:
    problemi = []
    # messaggio INTERO (oggetto e corpo), autori e committer di ogni commit
    r = git(radice, "log", "--all", "--format=%h%x09%an%x09%ae%x09%cn%x09%ce%x09%B%x00")
    if r.returncode:
        raise SystemExit("storia non leggibile: " + r.stderr.decode("utf-8", errors="replace").strip())
    for blocco in r.stdout.decode("utf-8", errors="replace").split("\0"):
        blocco = blocco.lstrip("\n")
        if not blocco.strip():
            continue
        h, an, ae, cn, ce, messaggio = (blocco.split("\t", 5) + [""] * 6)[:6]
        for nome, mail in (("autore", ae), ("committer", ce)):
            if mail and not EMAIL_AMMESSA.search(mail):
                problemi.append(f"commit {h}: email del {nome} non ammessa")
        voci = set(scansiona_riga("", f"{an} {cn}", parole))
        for riga in messaggio.splitlines():
            voci |= set(scansiona_riga("", riga, parole))
        for voce in sorted(voci):
            problemi.append(f"commit {h}: {voce} (nome o messaggio)")
    r = git(radice, "log", "--all", "-p", "--no-color", "--format=@@@COMMIT %h")
    file_corrente, commit = "", ""
    for riga in r.stdout.decode("utf-8", errors="replace").splitlines():
        if riga.startswith("@@@COMMIT "):
            commit = riga.split(" ", 1)[1]
        elif riga.startswith("+++ b/"):
            file_corrente = riga[6:]
        elif riga.startswith("+") and not riga.startswith("+++"):
            if file_corrente in ESENTI:
                continue
            for voce in sorted(set(scansiona_riga(file_corrente, riga[1:], parole))):
                problemi.append(f"commit {commit} {file_corrente}: {voce}")
            if file_corrente and nome_vecchio_in(file_corrente):
                problemi.append(f"commit {commit} {file_corrente}: nome vecchio dell'app nel nome del file")
    return problemi


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    gruppo = a.add_mutually_exclusive_group()
    gruppo.add_argument("--albero", action="store_true", help="tutti i file tracciati (predefinito)")
    gruppo.add_argument("--staged", action="store_true", help="solo il contenuto in preparazione per il commit")
    gruppo.add_argument("--storia", action="store_true", help="tutti i commit: autori, messaggi e righe aggiunte")
    gruppo.add_argument("--file", nargs="+", metavar="PERCORSO", help="file scelti")
    a.add_argument("--radice", type=Path, default=RADICE, help="cartella del repository (predefinito: questo repository)")
    a.add_argument("--parole", type=Path, help="file delle parole private (predefinito: quello fuori da git)")
    arg = a.parse_args(argv)

    radice = arg.radice.resolve()
    parole = parole_private(arg.parole)
    if arg.staged:
        problemi = controlla_staged(radice, parole)
    elif arg.storia:
        problemi = controlla_storia(radice, parole)
    elif arg.file:
        problemi = []
        for rel in arg.file:
            p = radice / rel
            problemi += scansiona_nome(rel, parole)
            if p.is_file() and p.suffix.lower() not in ESTENSIONI_BINARIE:
                problemi += scansiona_testo(rel, p.read_bytes(), parole)
    else:
        problemi = controlla_albero(radice, parole)

    nota = f" (con {len(parole)} parole private)" if parole else " (nessun elenco privato: solo le regole generiche)"
    if not problemi:
        print("Controllo dei residui: pulito" + nota)
        return 0
    print(f"Controllo dei residui: {len(problemi)} problemi" + nota)
    for x in problemi[:80]:
        print("  !", x)
    if len(problemi) > 80:
        print(f"  ... altri {len(problemi) - 80}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:      # errore imprevisto: meglio uscire con errore che far passare il controllo
        print("ERRORE nel controllo dei residui:", e, file=sys.stderr)
        sys.exit(2)
