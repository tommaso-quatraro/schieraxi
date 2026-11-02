"""Blocca le dipendenze Python: scrive requirements.txt e requirements-dev.txt con versioni fisse e hash.

Uso (dalla radice del repository, con la .venv del progetto):
    .venv\\Scripts\\python.exe script\\blocca_dipendenze.py                     riscrive i due file tenendo le versioni che ci sono già
    .venv\\Scripts\\python.exe script\\blocca_dipendenze.py --versioni FILE     prende le versioni da FILE (uscita di `pip freeze`,
                                                                             per esempio quella del server di produzione)
    .venv\\Scripts\\python.exe script\\blocca_dipendenze.py --aggiorna          prende le versioni della .venv (per aggiornare)
    .venv\\Scripts\\python.exe script\\blocca_dipendenze.py --controlla         esce con 1 se i file non sono quelli che scriverebbe

Da dove vengono i dati (niente librerie in più: solo `packaging`, che c'è già con pytest):
- elenco: `requirements.in` (app) e `requirements-dev.in` (test), senza versioni, scritti a mano;
- versioni, in quest'ordine: `requirements-vincoli.in`; il file di --versioni; i requirements*.txt di adesso (salvo --aggiorna);
  la .venv che lancia lo script. Un vincolo con il marcatore `python_version < "X.Y"` aggiunge una seconda versione solo per i
  Python più vecchi (oggi parte della CI usa ancora 3.11): il server e lo sviluppo restano sulla versione principale;
- dipendenze: i metadati della versione installata (o di PyPI se nella .venv c'è un'altra versione), con i marcatori valutati per
  tutti i posti dove gira l'app (Python 3.11-3.13, Linux x86_64 e ARM64, Windows): si prende l'unione;
- hash: tutti i file pubblicati su PyPI per quella versione (wheel di ogni sistema e sorgente), come `pip-compile --generate-hashes`.

PyPI si interroga con calma (una richiesta ogni 0,3 secondi, risposte salvate in una cache nella cartella temporanea).
Se risponde «troppe richieste» lo script si ferma e lo dice. Dopo: `pip install --require-hashes -r requirements.txt -r requirements-dev.txt`.
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import Tag, compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

RADICE = Path(__file__).resolve().parent.parent
FILE_APP, FILE_DEV, FILE_VINCOLI = RADICE / "requirements.in", RADICE / "requirements-dev.in", RADICE / "requirements-vincoli.in"
USCITA_APP, USCITA_DEV = RADICE / "requirements.txt", RADICE / "requirements-dev.txt"
CACHE = Path(os.environ.get("BLOCCA_CACHE", Path(tempfile.gettempdir()) / "schieraxi-pypi"))
PAUSA = 0.3

# (python, sys_platform, platform_machine): i posti dove l'app gira o si prova
OBIETTIVI = [("3.12", "linux", "x86_64"), ("3.12", "linux", "aarch64"), ("3.12", "win32", "AMD64"), ("3.13", "linux", "x86_64"),
             ("3.13", "win32", "AMD64"), ("3.11", "linux", "x86_64"), ("3.11", "linux", "aarch64"), ("3.11", "win32", "AMD64")]
# la versione più vecchia in uso per ogni Python: 3.11.2 è quella di Debian 12, 3.12.3 quella di Ubuntu 24.04
PIENA = {"3.11": "3.11.2", "3.12": "3.12.3", "3.13": "3.13.0"}
VECCHI = re.compile(r'^python_version\s*<\s*"(\d+\.\d+)"$')


def ambiente(py: str, piattaforma: str, macchina: str, extra: str = "") -> dict[str, str]:
    win = piattaforma == "win32"
    return {"python_version": py, "python_full_version": PIENA[py], "sys_platform": piattaforma, "platform_machine": macchina,
            "platform_system": "Windows" if win else "Linux", "os_name": "nt" if win else "posix",
            "implementation_name": "cpython", "platform_python_implementation": "CPython", "platform_release": "",
            "platform_version": "", "implementation_version": PIENA[py], "extra": extra}


def posti(marcatore: str) -> list[tuple[str, str, str]]:
    return [o for o in OBIETTIVI if not marcatore or Marker(marcatore).evaluate(ambiente(*o))]


def serve(marcatore: Marker | None, extras: set[str], dove: list[tuple[str, str, str]]) -> bool:
    """La dipendenza serve in almeno uno dei posti (con uno degli extra chiesti, o senza)?"""
    if marcatore is None:
        return True
    return any(marcatore.evaluate(ambiente(*o, extra=e)) for o in dove for e in (extras | {""}))


def leggi_elenco(percorso: Path) -> list[Requirement]:
    out = []
    if percorso.exists():
        for riga in percorso.read_text(encoding="utf-8").splitlines():
            riga = riga.split("#", 1)[0].strip()
            if riga:
                out.append(Requirement(riga))
    return out


def leggi_freeze(percorso: Path) -> dict[str, str]:
    """nome -> versione da un'uscita di `pip freeze` (righe nome==versione; le altre si ignorano)."""
    out = {}
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.split("#", 1)[0].strip()
        if "==" in riga and not riga.startswith("-"):
            nome, _, versione = riga.partition("==")
            out[canonicalize_name(nome.strip())] = versione.split(";")[0].split()[0].strip()
    return out


def leggi_blocco(*percorsi: Path) -> dict[str, str]:
    """Versioni principali dei requirements*.txt di adesso (quelle senza marcatore o con python_version >=)."""
    out = {}
    for p in percorsi:
        if not p.exists():
            continue
        testo = p.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\\\n", " ")
        for riga in testo.splitlines():
            riga = riga.split("#", 1)[0].strip()
            if "==" not in riga:
                continue
            req, _, marc = riga.split(" --hash")[0].partition(";")
            nome, _, versione = req.partition("==")
            if not marc.strip() or ">=" in marc:
                out[canonicalize_name(nome.strip())] = versione.strip()
    return out


def leggi_vincoli() -> dict[str, list[tuple[str, str]]]:
    """nome -> [(versione, marcatore)]: senza marcatore la versione vale ovunque; con `python_version < "X.Y"` vale solo lì."""
    out: dict[str, list[tuple[str, str]]] = {}
    for r in leggi_elenco(FILE_VINCOLI):
        if len(r.specifier) != 1 or next(iter(r.specifier)).operator != "==":
            raise SystemExit(f"{FILE_VINCOLI.name}: solo righe nome==versione [; python_version < \"X.Y\"] ({r})")
        marc = str(r.marker) if r.marker else ""
        if marc and not VECCHI.match(marc):
            raise SystemExit(f"{FILE_VINCOLI.name}: come marcatore solo python_version < \"X.Y\" ({r})")
        out.setdefault(canonicalize_name(r.name), []).append((next(iter(r.specifier)).version, marc))
    return out


def pypi(nome: str, versione: str) -> dict:
    """Metadati di PyPI per una versione (dalla cache se ci sono già)."""
    f = CACHE / f"{canonicalize_name(nome)}-{versione}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    time.sleep(PAUSA)
    url = f"https://pypi.org/pypi/{canonicalize_name(nome)}/{versione}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "schieraxi-blocca-dipendenze"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            dati = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            sys.exit("PyPI risponde «troppe richieste» (429): mi fermo. Riprova più tardi (la cache tiene quanto già scaricato).")
        raise SystemExit(f"PyPI: {nome} {versione} non trovato ({e.code})") from None
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dati), encoding="utf-8")
    return dati


def etichette(py: str, piattaforma: str, macchina: str) -> set[Tag]:
    v = tuple(int(x) for x in py.split("."))
    if piattaforma == "win32":
        piatt = ["win_amd64"]
    else:   # glibc di Debian 12 (2.36) e di Ubuntu 24.04 (2.39): basta fino a 2.36
        piatt = [f"manylinux_2_{n}_{macchina}" for n in range(36, 4, -1)] + [f"manylinux2014_{macchina}", f"manylinux2010_{macchina}",
                                                                            f"manylinux1_{macchina}", f"linux_{macchina}"]
    return set(cpython_tags(v, platforms=piatt)) | set(compatible_tags(v, platforms=piatt))


class Risolutore:
    def __init__(self, fonti: list[dict[str, str]]):
        self.fonti, self.vincoli = fonti, leggi_vincoli()
        self.avvisi: list[str] = []
        self.errori: list[str] = []

    def varianti(self, nome: str) -> list[tuple[str, str]]:
        """[(versione, marcatore)] di un pacchetto: la principale e, se c'è un vincolo per i Python vecchi, quella."""
        vincoli = self.vincoli.get(nome, [])
        ovunque = [v for v, m in vincoli if not m]
        if ovunque:
            return [(ovunque[0], "")]
        principale = next((f[nome] for f in self.fonti if nome in f), None)
        if principale is None:
            try:
                principale = md.version(nome)
            except md.PackageNotFoundError:
                raise SystemExit(f"{nome}: nessuna versione (né in --versioni, né nei requirements*.txt, né nella .venv)") from None
        out = []
        for v, m in vincoli:          # python_version < "X.Y": la principale vale da X.Y in su
            out.append((v, m))
            principale_m = m.replace("<", ">=")
            if (principale, principale_m) not in out:
                out.append((principale, principale_m))
        return sorted(out or [(principale, "")], key=lambda x: x[1])

    def risolvi(self, radici: list[Requirement]) -> dict[str, dict]:
        """Chiusura delle dipendenze: nome canonico -> {nome, varianti, via}."""
        scelti: dict[str, dict] = {}
        extras_visti: dict[str, set[str]] = {}
        coda = [(r, "") for r in radici]
        while coda:
            req, da = coda.pop(0)
            nome = canonicalize_name(req.name)
            nuovi_extra = set(req.extras) - extras_visti.get(nome, set())
            if nome in scelti:
                if da:
                    scelti[nome]["via"].add(da)
                for v, _ in scelti[nome]["varianti"]:
                    if v not in req.specifier:
                        self.errori.append(f"{nome} {v} non rispetta «{req}» (chiesto da {da or 'elenco'})")
                if not nuovi_extra:
                    continue
            varianti = self.varianti(nome)
            if nome not in scelti:
                scelti[nome] = {"varianti": varianti, "via": {da} if da else set(), "nome": nome}
                for v, m in varianti:
                    if v not in req.specifier:
                        self.errori.append(f"{nome} {v} non rispetta «{req}» (chiesto da {da or 'elenco'})")
                    self.controlla_file(nome, v, m)
            extras_visti.setdefault(nome, set()).update(req.extras)
            for v, m in varianti:
                try:
                    locale = md.version(nome) == v
                except md.PackageNotFoundError:
                    locale = False
                dipendenze = md.requires(nome) if locale else pypi(nome, v)["info"].get("requires_dist")
                for testo in dipendenze or []:
                    dip = Requirement(testo)
                    if serve(dip.marker, extras_visti[nome], posti(m)):
                        coda.append((dip, nome))
        return scelti

    def controlla_file(self, nome: str, versione: str, marcatore: str) -> None:
        dati = pypi(nome, versione)
        info, file = dati["info"], dati["urls"]
        if not file:
            self.errori.append(f"{nome} {versione}: nessun file su PyPI")
            return
        if info.get("yanked"):
            self.avvisi.append(f"{nome} {versione} è stata ritirata da PyPI ({info.get('yanked_reason') or 'senza motivo'})")
        dove = posti(marcatore)
        rp = info.get("requires_python")
        if rp:
            for py in sorted({o[0] for o in dove}):
                if Version(PIENA[py]) not in SpecifierSet(rp):
                    self.errori.append(f"{nome} {versione} richiede Python {rp}: non va con {PIENA[py]} "
                                       f"(aggiungi in {FILE_VINCOLI.name} una versione con python_version < \"...\")")
        sorgente = any(f["packagetype"] == "sdist" for f in file)
        for o in dove:
            ok = etichette(*o)
            if not any(f["filename"].endswith(".whl") and parse_wheel_filename(f["filename"])[3] & ok for f in file):
                msg = f"{nome} {versione}: nessuna wheel per Python {o[0]} {o[1]} {o[2]}"
                if sorgente:
                    self.avvisi.append(msg + ": pip la compila dal sorgente")
                else:
                    self.errori.append(msg + " e nessun sorgente")


def hash_di(nome: str, versione: str) -> list[str]:
    return sorted(f["digests"]["sha256"] for f in pypi(nome, versione)["urls"])


def scrivi(pacchetti: dict[str, dict], titolo: str, comando: str) -> str:
    righe = ["# File generato da script/blocca_dipendenze.py: NON modificarlo a mano.",
             f"# {titolo}",
             "# Rigenerarlo: .venv\\Scripts\\python.exe script\\blocca_dipendenze.py (opzioni: vedi lo script)",
             f"# Installazione: {comando}",
             "#"]
    for nome in sorted(pacchetti):
        p = pacchetti[nome]
        for versione, marcatore in p["varianti"]:
            hs = hash_di(nome, versione)
            righe.append(f"{nome}=={versione}" + (f" ; {marcatore}" if marcatore else "") + " \\")
            righe += [f"    --hash=sha256:{h} \\" for h in hs[:-1]] + [f"    --hash=sha256:{hs[-1]}"]
        via = sorted(v for v in p["via"] if v)
        righe.append("    # via " + ", ".join(via) if via else "    # elenco")
    return "\n".join(righe) + "\n"


def calcola(versioni: Path | None = None, aggiorna: bool = False) -> tuple[str, str, list[str]]:
    fonti = []
    if versioni:
        fonti.append(leggi_freeze(versioni))
    if not aggiorna:
        fonti.append(leggi_blocco(USCITA_APP, USCITA_DEV))
    r = Risolutore(fonti)
    app = r.risolvi(leggi_elenco(FILE_APP))
    tutto = r.risolvi(leggi_elenco(FILE_APP) + leggi_elenco(FILE_DEV))
    dev = {n: p for n, p in tutto.items() if n not in app}
    if r.errori:
        raise SystemExit("Non scrivo niente:\n- " + "\n- ".join(dict.fromkeys(r.errori)))
    testo_app = scrivi(app, "Librerie dell'app (elenco in requirements.in).",
                       "pip install --require-hashes -r requirements.txt")
    testo_dev = scrivi(dev, "Librerie in più per i test (elenco in requirements-dev.in): si installa INSIEME a requirements.txt.",
                       "pip install --require-hashes -r requirements.txt -r requirements-dev.txt")
    return testo_app, testo_dev, list(dict.fromkeys(r.avvisi))


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--controlla", action="store_true", help="non scrive: esce con 1 se i file sono diversi")
    a.add_argument("--versioni", type=Path, help="uscita di `pip freeze` da cui prendere le versioni (per esempio quella del server)")
    a.add_argument("--aggiorna", action="store_true", help="ignora le versioni dei requirements*.txt di adesso")
    arg = a.parse_args(argv)
    testo_app, testo_dev, avvisi = calcola(arg.versioni, arg.aggiorna)
    for x in avvisi:
        print("Avviso:", x)
    if arg.controlla:
        diversi = [f.name for f, t in ((USCITA_APP, testo_app), (USCITA_DEV, testo_dev))
                   if not f.exists() or f.read_text(encoding="utf-8").replace("\r\n", "\n") != t]
        if diversi:
            print("Da rigenerare:", ", ".join(diversi))
            return 1
        print("requirements*.txt aggiornati")
        return 0
    for f, t in ((USCITA_APP, testo_app), (USCITA_DEV, testo_dev)):
        f.write_text(t, encoding="utf-8", newline="\n")
        print(f"Scritto {f.name}: {len(re.findall(r'^[a-z0-9].*==', t, re.M))} righe di versione")
    return 0


if __name__ == "__main__":
    sys.exit(main())
