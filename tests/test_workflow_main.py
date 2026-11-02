"""Controlli su `main` dopo ogni unione (issue #183, docs/decisioni/0008).

Il job «unisci» unisce col token di GitHub, e i push fatti con quel token non fanno partire i workflow: senza un lancio esplicito
nessun controllo girava mai sul nuovo `main`, e due PR verdi ognuna da sola potevano romperlo insieme senza che nessuno se ne
accorgesse. Ora: «prova-main» lancia `test.yml` su `main` (workflow_dispatch parte anche col token di GitHub) e «main-rosso»
apre o aggiorna un'issue P1 se la corsa su `main` fallisce.
I workflow si leggono come testo (niente PyYAML nelle dipendenze)."""
import re
from pathlib import Path

TEST_YML = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"


def _testo() -> str:
    return TEST_YML.read_text(encoding="utf-8")


def _job(nome: str) -> str:
    """Il blocco di un job di test.yml (dalla riga `  nome:` alla riga del job successivo)."""
    testo = _testo()
    corpo = testo[re.search(r"^jobs:\s*$", testo, re.M).end():]
    m = re.search(rf"^  {re.escape(nome)}:\s*$", corpo, re.M)
    assert m, f"manca il job «{nome}»"
    fine = re.search(r"^  [A-Za-z0-9_-]+:\s*$", corpo[m.end():], re.M)
    return corpo[m.start():m.end() + fine.start()] if fine else corpo[m.start():]


def _permessi(blocco: str) -> dict[str, str]:
    m = re.search(r"^    permissions:\s*\n((?:      \S.*\n)+)", blocco, re.M)
    assert m, "il job non dichiara i suoi permessi"
    return {k: v for k, v in re.findall(r"^      ([a-z-]+):\s*(\w+)", m.group(1), re.M)}


def _comandi(blocco: str) -> str:
    """Il testo dei soli comandi (`run:`) e dei valori dei passi, senza i commenti."""
    return "\n".join(r for r in blocco.splitlines() if not r.lstrip().startswith("#"))


def test_i_controlli_si_possono_lanciare_a_mano_e_non_con_eventi_pericolosi():
    on = re.search(r"^on:\s*\n((?:  .*\n|\n)+)", _testo(), re.M).group(1)
    assert re.search(r"^  workflow_dispatch:", on, re.M)
    assert re.search(r"^  push:", on, re.M) and "branches: [main]" in on
    assert "pull_request" + "_target" not in _testo()      # scritto spezzato: il controllo dei residui lo cerca come parola


def test_prova_main_lancia_i_controlli_su_main_solo_dopo_un_unione_riuscita():
    j = _job("prova-main")
    cond = re.search(r"^    if:\s*(.+)$", j, re.M).group(1)
    assert "needs.unisci.result == 'success'" in cond and "github.event_name == 'pull_request'" in cond
    assert "!cancelled()" in cond          # «ios» può essere saltato a monte: senza, anche questo job salterebbe
    needs = re.search(r"^    needs:\s*\[([^\]]*)\]", j, re.M).group(1)
    assert "unisci" in needs and "rilascia" in needs      # si prova il main finale, col commit di versione del bot
    assert "gh workflow run test.yml --ref main" in _comandi(j)
    # permesso minimo: solo lanciare un workflow (niente contents, niente issues)
    assert _permessi(j) == {"actions": "write"}


def test_prova_main_non_gira_sulle_corse_su_main_e_non_ricomincia_da_solo():
    # la corsa lanciata su main è un workflow_dispatch: prova-main è legato agli eventi pull_request, quindi niente giro continuo
    assert "github.event_name == 'pull_request'" in _job("prova-main")
    assert "github.event_name == 'pull_request'" in _job("unisci") and "github.event_name == 'pull_request'" in _job("rilascia")


def test_main_rosso_apre_un_issue_p1_con_permesso_minimo():
    j = _job("main-rosso")
    cond = re.search(r"^    if:\s*(.+)$", j, re.M).group(1)
    assert "github.event_name != 'pull_request'" in cond          # solo corse su main: le PR hanno già il loro esito
    assert "github.ref == 'refs/heads/main'" in cond              # una corsa lanciata a mano su un ramo non apre issue
    assert "contains(needs.*.result, 'failure')" in cond
    assert "!cancelled()" in cond or "always()" in cond
    needs = re.search(r"^    needs:\s*\[([^\]]*)\]", j, re.M).group(1)
    for lavoro in ("test", "script-server", "cambi", "ios", "pip-audit"):
        assert lavoro in [n.strip() for n in needs.split(",")], lavoro
    comandi = _comandi(j)
    assert "gh issue create" in comandi and "P1" in comandi and "gh issue comment" in comandi
    assert _permessi(j) == {"issues": "write"}


def test_main_rosso_non_mette_testo_non_fidato_nei_comandi():
    # solo dati nostri (esiti dei job, commit, indirizzo della corsa), sempre passati per variabili d'ambiente
    comandi = _comandi(_job("main-rosso"))
    run = comandi[comandi.index("run:"):]
    assert "${{" not in run
    for non_fidato in ("pull_request.title", "pull_request.body", "head_ref", "issue.title", "issue.body", "head_commit.message"):
        assert non_fidato not in _job("main-rosso")


def test_corsa_su_main_confronta_ios_con_l_ultima_corsa_riuscita():
    # una corsa lanciata a mano o da «prova-main» non ha «event.before»: ios/ si confronta con l'ultima corsa riuscita su main
    # (e con main per un ramo); se non si sa, i test iOS girano comunque (meglio un Mac in più che un buco)
    j = _job("cambi")
    assert "workflow_dispatch" in j
    assert "actions: read" in _comandi(j)
    assert "status=success" in j and 'select(.event == "push" or .event == "workflow_dispatch")' in j
    assert 'file="ios/"' in j


def test_i_job_di_main_non_cambiano_i_permessi_degli_altri():
    # il permesso di scrittura sulle issue e sulle azioni sta solo nei job che ne hanno bisogno
    testo = _testo()
    assert re.match(r"(?s).*?^permissions:\s*\n  contents: read\s*\n", testo, re.M)
    for nome in ("test", "script-server", "pip-audit", "versione", "ambito"):
        assert "issues: write" not in _job(nome) and "actions: write" not in _job(nome)
    assert testo.count("issues: write") == 1
    assert testo.count("actions: write") == 2      # rilascia (lancia ipa.yml) e prova-main (lancia test.yml)
