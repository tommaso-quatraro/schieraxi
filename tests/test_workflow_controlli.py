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


CARTELLA_WORKFLOW = WORKFLOW.parent


def _azioni_non_fissate(testo: str) -> list[str]:
    """Le righe `uses:` che prendono un'azione di altri senza l'hash del commit (40 cifre esadecimali).
    Un tag (`@v4`) o un ramo si possono spostare: chi controlla l'azione cambierebbe il codice che gira nei nostri job."""
    righe = []
    for riga in testo.splitlines():
        m = re.match(r"^\s*(?:-\s+)?uses:\s*([^\s#]+)", riga)
        if m and not m.group(1).startswith("./") and not re.fullmatch(r"[^@]+@[0-9a-f]{40}", m.group(1)):
            righe.append(riga.strip())
    return righe


def test_il_controllo_delle_azioni_riconosce_tag_e_rami():
    finto = ("    steps:\n      - uses: actions/checkout@v7\n      - uses: org/azione@main\n"
             "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1\n"
             "    uses: ./.github/workflows/ios.yml\n")
    assert _azioni_non_fissate(finto) == ["- uses: actions/checkout@v7", "- uses: org/azione@main"]


def test_ogni_azione_esterna_e_fissata_per_hash():
    # lo controlla anche zizmor (job «zizmor»), che però per ora segnala soltanto: questa regola blocca già adesso
    for file in sorted(CARTELLA_WORKFLOW.glob("*.y*ml")):
        assert _azioni_non_fissate(file.read_text(encoding="utf-8")) == [], f"{file.name}: azione non fissata per hash"


def test_solo_azioni_di_github():
    # Impostazione del repository (Settings > Actions > General): sono permesse solo le azioni di GitHub (proprietari
    # «actions» e «github»). Un'azione di altri fa fallire l'avvio di tutto il workflow, «unisci» compreso (PR #109).
    for file in sorted(CARTELLA_WORKFLOW.glob("*.y*ml")):
        for riga in file.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*(?:-\s+)?uses:\s*([^\s#]+)", riga)
            if m and not m.group(1).startswith("./"):
                assert m.group(1).split("/")[0] in ("actions", "github"), f"{file.name}: {m.group(1)} non è di GitHub"


def test_zizmor_e_fissato_e_non_blocca_ancora_l_unione():
    job = _job()
    assert "zizmor" in job and "zizmor" not in job["unisci"]["needs"]
    testo = WORKFLOW.read_text(encoding="utf-8")
    assert "--require-hashes" in testo and ".github/zizmor-requisiti.txt" in testo
    requisiti = (CARTELLA_WORKFLOW.parent / "zizmor-requisiti.txt").read_text(encoding="utf-8")
    assert re.search(r"^zizmor==\d+\.\d+\.\d+ \\$", requisiti, re.M), "versione di zizmor fissata"
    assert len(re.findall(r"--hash=sha256:[0-9a-f]{64}", requisiti)) >= 2, "hash dei file di zizmor"


def _requisiti_fissati(nome: str) -> str:
    """Un file .github/<nome>-requisiti.txt con una sola libreria a versione fissa e gli hash dei suoi file."""
    requisiti = (CARTELLA_WORKFLOW.parent / f"{nome}-requisiti.txt").read_text(encoding="utf-8")
    assert re.search(rf"^{nome}==\d+\.\d+\.\d+ \\$", requisiti, re.M), f"versione di {nome} fissata"
    assert len(re.findall(r"--hash=sha256:[0-9a-f]{64}", requisiti)) >= 2, f"hash dei file di {nome}"
    return requisiti


def test_ruff_controlla_il_codice_con_versione_e_hash_fissati():
    """ruff (solo controllo, niente riformattazione) gira nel job «test», quindi blocca l'unione; si installa a parte
    con versione e hash fissati, solo file binari."""
    _requisiti_fissati("ruff")
    testo = WORKFLOW.read_text(encoding="utf-8")
    blocco_test = testo[testo.index("\n  test:"):testo.index("\n  script-server:")]
    assert "--require-hashes --only-binary=:all: -r .github/ruff-requisiti.txt" in blocco_test
    assert re.search(r"ruff\" check (--output-format=github )?fanta tests script prove", blocco_test)
    assert "ruff format" not in testo and "--fix" not in testo
    config = (CARTELLA_WORKFLOW.parent.parent / "ruff.toml").read_text(encoding="utf-8")
    assert re.search(r'^select = \[.*"E9".*"F".*\]', config, re.M)
