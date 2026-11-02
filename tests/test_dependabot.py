"""Dependabot: solo le azioni di GitHub, una volta alla settimana, raggruppate, con 7 giorni di attesa; mai unite da sole.

Niente `pip`: con `requirements.in` accanto, Dependabot tratta `requirements.txt` come uscita di pip-compile e lo rigenera
con pip-compile (PipCompileFileMatcher di dependabot-core), non con script/blocca_dipendenze.py: perderebbe le versioni per
Python < 3.12 (requirements-vincoli.in), le dipendenze di tutte le piattaforme e l'intestazione (test_dipendenze_bloccate.py)."""
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DEPENDABOT = (RADICE / ".github" / "dependabot.yml").read_text(encoding="utf-8")


def _senza_commenti(testo: str) -> str:
    return "\n".join(r.split("#")[0].rstrip() for r in testo.splitlines() if r.split("#")[0].strip())


def test_solo_azioni_di_github_settimanali_raggruppate_con_attesa():
    testo = _senza_commenti(DEPENDABOT)
    assert re.findall(r"package-ecosystem:\s*(\S+)", testo) == ["github-actions"]
    assert re.search(r"interval:\s*weekly", testo)
    assert re.search(r"groups:\s*\n\s+\S+:\s*\n\s+patterns:\s*\[\"\*\"\]", testo)
    assert re.search(r"cooldown:\s*\n\s+default-days:\s*7\b", testo)


def test_unisci_esclude_dependabot():
    testo = (RADICE / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    unisci = testo[testo.index("\n  unisci:\n"):testo.index("\n  rilascia:\n")]
    condizione = unisci.split("    if: >-")[1].split("    runs-on:")[0]
    assert "github.event.pull_request.user.login != 'dependabot[bot]'" in condizione
