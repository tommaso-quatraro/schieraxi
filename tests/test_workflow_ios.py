"""I Mac di GitHub (piano Free: pochi lavori macOS insieme) partono solo quando servono.

- Il job «ios» di test.yml parte solo se la PR tocca ios/ (o il suo workflow) e la PR non è in bozza.
- Per questo test.yml deve ripartire quando la bozza diventa pronta (`ready_for_review`): senza, `gh pr ready` non
  rilancia i controlli e «unisci» non parte finché non arriva un altro push (è successo con #69).
- Su una PR un push nuovo annulla le corse vecchie della stessa PR; su main nessuna corsa si annulla (build e foto).
I workflow si leggono come testo (niente PyYAML nelle dipendenze)."""
import re
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _testo(nome: str) -> str:
    return (CARTELLA / nome).read_text(encoding="utf-8")


def _blocco(testo: str, chiave: str, rientro: int) -> str:
    """Il blocco YAML che inizia con `chiave:` al rientro dato, fino alla riga successiva con rientro uguale o minore."""
    m = re.search(rf"^{' ' * rientro}{re.escape(chiave)}:.*$", testo, re.M)
    assert m, f"manca «{chiave}»"
    fine = re.search(rf"^ {{0,{rientro}}}\S", testo[m.end() + 1:], re.M)
    return testo[m.start():m.end() + 1 + fine.start()] if fine else testo[m.start():]


def _concurrency_annulla_solo_sulle_pr(blocco: str) -> None:
    annulla = re.search(r"cancel-in-progress:\s*(.+)$", blocco, re.M).group(1).strip()
    assert annulla != "true", "cancel-in-progress: true annullerebbe anche le corse su main"
    assert "github.event_name == 'pull_request'" in annulla, annulla


def test_controlli_ripartono_quando_la_bozza_diventa_pronta():
    pr = _blocco(_blocco(_testo("test.yml"), "on", 0), "pull_request", 2)
    tipi = re.search(r"^    types:\s*\[([^\]]*)\]", pr, re.M)
    assert tipi, "pull_request senza types: i tipi predefiniti non comprendono ready_for_review"
    assert {t.strip() for t in tipi.group(1).split(",")} >= {"opened", "synchronize", "reopened", "ready_for_review"}


def test_job_ios_solo_se_tocca_ios_e_non_in_bozza():
    ios = _blocco(_testo("test.yml"), "ios", 2)
    cond = re.search(r"^    if:\s*(.+)$", ios, re.M).group(1)
    assert "needs.cambi.outputs.ios == 'true'" in cond
    assert "!github.event.pull_request.draft" in cond
    cambi = _blocco(_testo("test.yml"), "cambi", 2)
    assert r"^(ios/|\.github/workflows/ios\.yml$)" in cambi


def test_unisci_non_resta_bloccato_quando_ios_e_saltato():
    unisci = _blocco(_testo("test.yml"), "unisci", 2)
    assert "!cancelled()" in unisci and "!github.event.pull_request.draft" in unisci
    assert "needs.ios.result == 'skipped' && needs.cambi.outputs.ios == 'false'" in unisci


def test_controlli_annullano_le_corse_vecchie_solo_sulle_pr():
    _concurrency_annulla_solo_sulle_pr(_blocco(_testo("test.yml"), "concurrency", 0))


def test_screenshot_niente_mac_sulle_bozze_e_corse_di_main_mai_annullate():
    testo = _testo("screenshot.yml")
    pr = _blocco(_blocco(testo, "on", 0), "pull_request", 2)
    assert '"ios/**"' in pr and '".github/workflows/screenshot.yml"' in pr
    quando = _blocco(testo, "quando", 2)
    assert "github.event.pull_request.draft" in quando and '"$BOZZA" = "true"' in quando
    concorrenza = _blocco(testo, "concurrency", 0)
    _concurrency_annulla_solo_sulle_pr(concorrenza)
    # fuori dalle PR il gruppo è unico per corsa: le corse a mano e su main restano in fila, mai annullate
    assert "github.run_id" in concorrenza
    # mettere un'altra etichetta (P2, ios...) non deve annullare la corsa di foto della stessa PR
    assert "github.event.label.name" in concorrenza


def test_ipa_mai_sulle_pr_e_mai_annullata():
    testo = _testo("ipa.yml")
    assert not re.search(r"^  pull_request", _blocco(testo, "on", 0), re.M)
    assert re.search(r"cancel-in-progress:\s*false", _blocco(testo, "concurrency", 0))


def test_bozza_pronta_non_fa_girare_due_volte_i_job_pesanti():
    # ready_for_review fa partire una corsa nuova della stessa PR: stesso gruppo (numero della PR) con annullamento,
    # quindi la corsa della bozza ancora in corso si ferma; e nella bozza il Mac (job «ios») non è mai partito.
    testo = _testo("test.yml")
    concorrenza = _blocco(testo, "concurrency", 0)
    assert "group: controlli-${{ github.event.pull_request.number || github.run_id }}" in concorrenza
    _concurrency_annulla_solo_sulle_pr(concorrenza)
    assert "!github.event.pull_request.draft" in re.search(r"^    if:\s*(.+)$", _blocco(testo, "ios", 2), re.M).group(1)
    # gli altri workflow che girano sulle PR non reagiscono a ready_for_review (niente seconda corsa delle foto)
    assert "ready_for_review" not in _testo("screenshot.yml")


def test_push_su_main_ognuno_nel_suo_gruppo():
    # con cancel-in-progress false GitHub tiene comunque UNA sola corsa in attesa per gruppo e annulla le altre in attesa:
    # ogni push su main ha un gruppo suo (run_id), le PR uno per numero
    concorrenza = _blocco(_testo("test.yml"), "concurrency", 0)
    assert "github.event.pull_request.number || github.run_id" in concorrenza
    assert "github.ref" not in concorrenza


def test_foto_dal_vero_mai_annullate_da_un_push():
    # solo l'etichetta «screenshot» (foto a ogni push) sta nel gruppo della PR; «screenshot-vero» parte solo all'etichetta
    # e un push dopo non deve annullarla
    concorrenza = _blocco(_testo("screenshot.yml"), "concurrency", 0)
    assert "github.event.label.name == 'screenshot'" in concorrenza
    assert "startsWith(github.event.label.name, 'screenshot')" not in concorrenza
    assert "contains(github.event.pull_request.labels.*.name, 'screenshot')" in concorrenza
