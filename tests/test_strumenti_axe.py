"""axe-core (tests/strumenti/axe): è quello dichiarato nel LEGGIMI e non finisce nell'app né nel sito."""
import hashlib
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CARTELLA = RADICE / "tests" / "strumenti" / "axe"


def test_axe_ha_l_hash_scritto_nel_leggimi():
    testo = (CARTELLA / "LEGGIMI.md").read_text(encoding="utf-8")
    atteso = re.search(r"SHA-256 di `axe\.min\.js`: `([0-9a-f]{64})`", testo).group(1)
    assert hashlib.sha256((CARTELLA / "axe.min.js").read_bytes()).hexdigest() == atteso


def test_axe_non_e_dentro_l_app_ne_nel_sito():
    for cartella in ("fanta", "sito"):
        for file in (RADICE / cartella).rglob("axe*.js"):
            raise AssertionError(f"axe non deve stare nell'app o nel sito: {file}")
