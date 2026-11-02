"""Il workflow dei controlli (.github/workflows/test.yml): i job a valle di un job che può essere saltato.

GitHub salta un job se un job a monte (anche indiretto) è stato saltato, a meno che il suo `if:` non usi `!cancelled()` o `always()`.
Il job «ios» si salta nelle PR che non toccano ios/: «unisci» e «rilascia» devono partire lo stesso (è successo con #33 e #34:
novità rimaste in fanta/novita.d senza versione né release)."""
import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"


def _job() -> dict[str, dict]:
    testo = WORKFLOW.read_text(encoding="utf-8")
    corpo = testo[re.search(r"^jobs:\s*$", testo, re.M).end():]
    teste = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", corpo, re.M))
    job = {}
    for i, m in enumerate(teste):
        blocco = corpo[m.end():teste[i + 1].start() if i + 1 < len(teste) else len(corpo)]
        needs = re.search(r"^    needs:\s*\[?([^\]\n]*)\]?\s*$", blocco, re.M)
        cond = re.search(r"^    if:\s*(>-\s*\n(?:      .*\n?)+|.*)$", blocco, re.M)
        job[m.group(1)] = {"needs": [n.strip() for n in needs.group(1).split(",") if n.strip()] if needs else [],
                           "if": cond.group(1) if cond else "", "uses": "uses:" in blocco.split("steps:")[0]}
    return job


def _a_monte(job: dict, nome: str) -> set[str]:
    visti, da_fare = set(), list(job[nome]["needs"])
    while da_fare:
        n = da_fare.pop()
        if n not in visti:
            visti.add(n)
            da_fare += job[n]["needs"]
    return visti


def test_i_job_a_valle_di_un_job_saltabile_usano_not_cancelled():
    job = _job()
    saltabili = {n for n, j in job.items() if j["if"]}
    assert "ios" in saltabili
    for nome, j in job.items():
        if _a_monte(job, nome) & saltabili:
            assert "!cancelled()" in j["if"] or "always()" in j["if"], f"job «{nome}»: manca !cancelled() nel suo if"


def test_unisci_e_rilascia_ci_sono_e_dipendono_come_previsto():
    job = _job()
    assert "ios" in job["unisci"]["needs"] and job["rilascia"]["needs"] == ["unisci"]
    assert "needs.unisci.result == 'success'" in job["rilascia"]["if"]
    assert "needs.ios.result == 'skipped'" in job["unisci"]["if"]
