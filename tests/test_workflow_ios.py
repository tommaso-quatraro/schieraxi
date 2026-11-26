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


# --- Issue #264: lo stesso codice iOS già verde non si prova due volte sul Mac ------------------------------------------------
# Una modifica iOS tipica faceva girare gli stessi test sullo stesso codice fino a tre volte (corsa a mano sul ramo, «ios / test»
# della PR, la corsa su main di «prova-main»). I test iOS dipendono solo da ios/ e da ios.yml: se una corsa riuscita ha già
# provato esattamente lo stesso albero (stessi hash git), il Mac non riparte. Il segno «verde» è un artifact di poche righe
# con l'hash nel nome, caricato solo a test riusciti e accettato solo se viene da una corsa di questo repository (mai da un fork).

def _job_ios(nome: str) -> str:
    return _blocco(_blocco(_testo("ios.yml"), "jobs", 0), nome, 2)


def test_ios_guarda_prima_su_linux_se_lo_stesso_albero_e_gia_verde():
    gia = _job_ios("gia-verde")
    assert "runs-on: ubuntu-latest" in gia                       # la domanda costa un Linux, non un Mac
    assert "actions: read" in gia and "write" not in gia         # legge solo l'elenco degli artifact
    # la chiave: albero di ios/ e file di ios.yml del commit provato (github.sha: nelle PR è il commit di unione)
    assert "git/trees/$COMMIT" in gia and '"ios"' in gia
    assert "contents/.github/workflows/ios.yml?ref=$COMMIT" in gia
    assert "COMMIT: ${{ github.sha }}" in gia
    # solo artifact non scaduti di corse di questo repository: un fork non può far saltare i test
    assert "actions/artifacts?name=ios-verde-$chiave" in gia
    assert ".expired == false" in gia and ".workflow_run.head_repository_id ==" in gia
    assert "REPO_ID: ${{ github.repository_id }}" in gia
    # le espressioni stanno nelle variabili d'ambiente, mai dentro i comandi
    for riga in gia.split("run: |", 1)[1].splitlines():
        assert "${{" not in riga, riga


def test_se_la_domanda_fallisce_i_test_girano():
    gia = _job_ios("gia-verde")
    # API che non risponde o chiave strana: «verde» resta false e il Mac parte (meglio un Mac in più che un buco)
    assert "verde=false" in gia
    assert re.search(r"\[0-9a-f\]\{40\}-\[0-9a-f\]\{40\}", gia), "la chiave va controllata (due hash git) prima di usarla"


def test_il_mac_parte_solo_se_il_codice_non_e_gia_verde():
    test = _job_ios("test")
    assert re.search(r"^    needs:\s*gia-verde\s*$", test, re.M)
    cond = re.search(r"^    if:\s*(.+)$", test, re.M).group(1)
    assert "github.event.repository.private == false" in cond
    assert "needs.gia-verde.outputs.verde != 'true'" in cond
    # a mano si può sempre forzare la corsa
    on = _blocco(_testo("ios.yml"), "on", 0)
    assert "forza:" in on and "type: boolean" in on


def test_il_segno_verde_si_carica_solo_dopo_i_test_riusciti():
    test = _job_ios("test")
    passi = test.split("      - ")
    i_test = next(i for i, p in enumerate(passi) if p.startswith("name: Compila ed esegui i test"))
    i_segno = next(i for i, p in enumerate(passi) if "name: ios-verde-${{ needs.gia-verde.outputs.chiave }}" in p)
    assert i_segno > i_test
    segno = passi[i_segno]
    assert "uses: actions/upload-artifact@" in segno
    assert "if: failure()" not in segno and "always()" not in segno     # mai dopo un rosso
    assert "needs.gia-verde.outputs.chiave != ''" in segno
    assert re.search(r"retention-days:\s*3\b", segno)                   # pochi giorni: l'immagine del Mac cambia


def test_i_valori_su_una_riga_di_ios_yml_sono_yaml_valido():
    # «run: printf 'ios.yml: %s'» non è YAML valido (due punti e spazio in un valore senza virgolette): GitHub scarta tutto il
    # workflow e «ios / test» fallisce senza job (lo ha trovato zizmor sulla prima stesura di questa modifica)
    for riga in _testo("ios.yml").splitlines():
        m = re.match(r"^\s*(?:-\s+)?(?:name|run|if):\s*(.+?)\s*$", riga)
        if m and not m.group(1).startswith(('"', "'", "|", ">")):
            assert ": " not in m.group(1).split(" #")[0], riga


def test_il_job_ios_dei_controlli_puo_leggere_gli_artifact():
    ios = _blocco(_testo("test.yml"), "ios", 2)
    assert "actions: read" in ios and "contents: read" in ios
    assert "write" not in ios


# --- Issue #264, seconda parte: compila una volta, unitari prima dell'interfaccia, corsa parziale ----------------------------------

def _passi_test() -> list[str]:
    """I passi del job «test» di ios.yml che cominciano con «name: Compila ed esegui i test», nell'ordine del file."""
    passi = _job_ios("test").split("      - ")
    return [p for p in passi if p.startswith("name: Compila ed esegui i test")]


def _passo(parte: str) -> str:
    trovati = [p for p in _passi_test() if parte in p.splitlines()[0]]
    assert len(trovati) == 1, f"deve esserci un solo passo «{parte}»: {len(trovati)}"
    return trovati[0]


def test_l_interfaccia_gira_solo_se_gli_unitari_sono_verdi():
    unitari, interfaccia = _passo("unitari"), _passo("interfaccia")
    assert "-only-testing:SchieraxiTests" in unitari and "-only-testing:SchieraxiUITests" not in unitari
    assert "-only-testing:SchieraxiUITests" in interfaccia and "-only-testing:SchieraxiTests" not in interfaccia
    ordine = [p.splitlines()[0] for p in _passi_test()]
    assert ordine.index(next(o for o in ordine if "unitari" in o)) < ordine.index(next(o for o in ordine if "interfaccia" in o))
    # nessun passo di test gira dopo un rosso: niente always() né failure() (un passo senza «if» sull'esito salta se uno prima fallisce)
    for p in _passi_test():
        cond = re.search(r"^        if:\s*(.+)$", p, re.M)
        assert not cond or not re.search(r"always\(\)|failure\(\)|cancelled\(\)", cond.group(1)), p.splitlines()[0]
    assert "continue-on-error" not in _job_ios("test")
    assert "set -o pipefail" in unitari and "set -o pipefail" in interfaccia          # il rosso di xcodebuild non si perde nel tee


def test_con_parte_unitari_niente_interfaccia_e_niente_segno_verde():
    on = _blocco(_testo("ios.yml"), "on", 0)
    assert "parte:" in on and "options: [tutti, unitari]" in on and "default: tutti" in on
    assert re.search(r"^        if:\s*inputs\.parte != 'unitari'\s*$", _passo("interfaccia"), re.M)
    passi = _job_ios("test").split("      - ")
    for nome in ("name: Segna lo stesso codice come verde", "name: Carica il segno «verde»"):
        passo = next(p for p in passi if p.startswith(nome))
        cond = re.search(r"^        if:\s*(.+)$", passo, re.M).group(1)
        assert "inputs.parte != 'unitari'" in cond and "needs.gia-verde.outputs.chiave != ''" in cond, nome
    # nelle PR (workflow_call) l'ingresso non esiste: «!= 'unitari'» è vero e girano entrambi i gruppi di test
    assert "parte" not in _blocco(_testo("test.yml"), "ios", 2)


def test_si_compila_una_volta_sola_poi_si_prova_senza_ricompilare():
    test = _job_ios("test")
    assert test.count("xcodebuild build-for-testing") == 1
    assert test.count("xcodebuild test-without-building") == 2
    assert not re.search(r"xcodebuild test\b(?!-)", test), "un «xcodebuild test» compilerebbe di nuovo"
    for p in _passi_test():
        assert "-derivedDataPath build/DerivedData" in p, p.splitlines()[0]          # tutti e tre usano gli stessi prodotti
    assert "build-for-testing" in _passo("1 di 3")
    # il simulatore si accende subito e si aspetta solo prima dei test, mentre si compila
    sim = next(p for p in test.split("      - ") if p.startswith("name: Scegli il simulatore"))
    assert "simctl boot " in sim and "simctl bootstatus" not in sim
    assert "simctl bootstatus" in _passo("unitari")


def test_i_lanci_a_mano_non_si_annullano_mai():
    # cancel-in-progress è ammesso solo se vale per le sole pull request: workflow_dispatch (lanci degli agenti) non si annulla.
    # ios.yml non ha un gruppo suo: nelle PR eredita quello di test.yml, a mano non ne ha.
    assert "concurrency" not in _testo("ios.yml")
    for file in sorted(CARTELLA.glob("*.yml")):
        if "workflow_dispatch" not in _blocco(file.read_text(encoding="utf-8"), "on", 0):
            continue          # solo chiamato da un altro workflow (revisione.yml, dalle sole PR): nessun lancio a mano
        for m in re.finditer(r"cancel-in-progress:\s*(.+)$", file.read_text(encoding="utf-8"), re.M):
            valore = m.group(1).split(" #")[0].strip()
            assert valore != "true", f"{file.name}: annullerebbe anche i lanci a mano"
            assert valore == "false" or "github.event_name == 'pull_request'" in valore, f"{file.name}: {valore}"
