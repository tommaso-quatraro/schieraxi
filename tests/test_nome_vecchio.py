"""Il nome dell'app è «SchieraXI»: i nomi usati in passato non devono comparire da nessuna parte (testi, codice, nomi di file).
Il numero «undici» in italiano («i tuoi undici», «undici punti») resta. I nomi non si scrivono in chiaro in questo file: si compongono a pezzi,
così il controllo non trova se stesso. Le eventuali eccezioni sono scritte qui sotto, con il motivo."""
import re
import subprocess
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
AREE = ("",)                                  # tutto il repository
ECCEZIONI: dict[str, str] = {}                # percorso: motivo (nessuna al momento)
ECCEZIONI_PREFISSO: tuple[str, ...] = ()
_A = "fanta" + "claude"
_B = "und" + "ici"
_C = "titolar" + "xi"
VECCHIO = re.compile(rf"(?i:{_A}|{_C})|{_B.capitalize()}|{_B.upper()}|it\.{_B}|{_B}(?:[/-]|_(?!titolari)|://)|[.-]{_B}|_{_B}(?!_titolari)|{_B}1")
# il numero in minuscolo usato come nome: tra tag o virgolette, o dopo una preposizione (il numero ha sempre un contesto come «gli undici»)
NOME_MINUSCOLO = re.compile(rf'(>|"){_B}(<|")|\b(?:in|di|a|su|con) {_B}\b(?! punti)')


CARTELLE_DA_SALTARE = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", "dati"}


def _elenco():
    """I file del progetto: da git se c'è; altrimenti (copia senza .git, per esempio l'esportazione pubblica) si percorrono le cartelle."""
    try:
        r = subprocess.run(["git", "ls-files"], cwd=RADICE, capture_output=True, text=True, check=True)
        if (RADICE / ".git").exists():
            return r.stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(p.relative_to(RADICE).as_posix() for p in RADICE.rglob("*")
                  if p.is_file() and not CARTELLE_DA_SALTARE & set(p.relative_to(RADICE).parts))


def _file():
    nomi = _elenco()
    for n in nomi:
        if n.startswith(AREE) and n not in ECCEZIONI and not n.startswith(ECCEZIONI_PREFISSO):
            yield n


def test_nessun_file_ha_il_nome_vecchio():
    assert not [n for n in _file() if re.search(rf"(?i){_A}|{_C}|{_B}", n)]


def test_senza_git_si_percorrono_le_cartelle(tmp_path, monkeypatch):
    """Nella copia esportata non c'è .git: il controllo non deve rompersi."""
    (tmp_path / "fanta").mkdir()
    (tmp_path / "fanta" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "fanta" / "__pycache__").mkdir()
    (tmp_path / "fanta" / "__pycache__" / "a.pyc").write_bytes(b"x")
    monkeypatch.setitem(globals(), "RADICE", tmp_path)
    assert list(_file()) == ["fanta/a.py"]
