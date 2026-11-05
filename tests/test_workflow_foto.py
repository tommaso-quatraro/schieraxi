"""Foto iOS più veloci (issue #264, .github/workflows/screenshot.yml).

- Le foto dei widget (circa 20 minuti) si fanno solo quando servono: se si chiedono, nella corsa «completo», o se sono cambiati
  i file che l'anteprima dei widget compila (ios/project.yml, target AnteprimaWidget). Se non si sa, si fanno.
- App e widget su due Mac che partono insieme solo nelle corse lunghe («completo» o «tutti»); nelle altre i widget seguono
  l'app sullo stesso Mac e sullo stesso simulatore, già acceso (una corsa veloce su due Mac non si accorciava, PR #271).
- Fino a 2 corse di foto insieme (prima una), e solo se ci sono abbastanza Mac liberi: mai più di 5 job Mac nel repository.
I passi bash del job «quando» si provano davvero, con `gh` e `sleep` finti. I workflow si leggono come testo (niente PyYAML)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
WORKFLOW = RADICE / ".github" / "workflows" / "screenshot.yml"


def _testo() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _blocco(testo: str, chiave: str, rientro: int) -> str:
    m = re.search(rf"^{' ' * rientro}{re.escape(chiave)}:.*$", testo, re.M)
    assert m, f"manca «{chiave}»"
    fine = re.search(rf"^ {{0,{rientro}}}\S", testo[m.end() + 1:], re.M)
    return testo[m.start():m.end() + 1 + fine.start()] if fine else testo[m.start():]


def _job(nome: str) -> str:
    return _blocco(_blocco(_testo(), "jobs", 0), nome, 2)


def _passo(job: str, nome: str) -> str:
    m = re.search(rf"^      - name: {re.escape(nome)}\s*$", job, re.M)
    assert m, f"manca il passo «{nome}»"
    fine = re.search(r"^      - ", job[m.end():], re.M)
    return job[m.start():m.end() + fine.start()] if fine else job[m.start():]


def _comandi(passo: str) -> str:
    """Il testo di «run: |» senza il rientro."""
    m = re.search(r"^(\s+)run: \|\s*\n", passo, re.M)
    assert m, "il passo non ha «run: |»"
    rientro = len(m.group(1)) + 2
    righe = []
    for riga in passo[m.end():].splitlines():
        if riga.strip() and len(riga) - len(riga.lstrip()) < rientro:
            break
        righe.append(riga[rientro:])
    return "\n".join(righe) + "\n"


def _file_widget() -> str:
    m = re.search(r"^\s+FILE_WIDGET: '([^']+)'\s*$", _testo(), re.M)
    assert m, "manca FILE_WIDGET (i file che cambiano le foto dei widget)"
    return m.group(1)


# ------------------------------------------------------------------------------------------------- struttura dei job

def test_app_e_widget_in_due_job_mac_che_partono_insieme_solo_nelle_corse_lunghe():
    # corsa veloce misurata (#271): sul Mac a parte i widget riaccendevano da zero il simulatore (8,9 min) e la corsa non si
    # accorciava; quindi due Mac solo con «completo» o «tutti», altrimenti i widget seguono l'app sullo stesso simulatore
    app, widget = _job("screenshot"), _job("widget")
    for job in (app, widget):
        assert re.search(r"^    needs:\s*quando\s*$", job, re.M)          # nessuno aspetta l'altro
        assert "runs-on: macos-26" in job
        assert "github.event.repository.private == false" in job
    assert "scripts/screenshot.sh" in app and "name: screenshot-app" in app
    assert "-scheme AnteprimaWidget" in widget and "scripts/screenshot_widget.sh" in widget
    assert "name: screenshot-widget" in widget                          # stesso nome di prima per chi guarda le foto
    assert "needs.quando.outputs.parallelo == 'true'" in re.search(r"^    if:\s*(.+)$", widget, re.M).group(1)
    # nello stesso job: compila, scatta e carica i widget dopo l'app, solo quando servono e non c'è il job a parte
    stesso = "needs.quando.outputs.widget == 'true' && needs.quando.outputs.parallelo != 'true'"
    for nome in ("Compila l'anteprima dei widget per il simulatore (senza firma)", "Scatta le fotografie dei widget",
                 "Carica le fotografie dei widget"):
        passo = _passo(app, nome)
        assert stesso in passo, nome
    assert "always()" in _passo(app, "Scatta le fotografie dei widget")     # come prima: anche se le foto dell'app falliscono
    assert app.index("Scatta le fotografie dell'app") < app.index("Scatta le fotografie dei widget")


def test_il_job_dei_widget_parte_solo_quando_servono():
    cond = re.search(r"^    if:\s*(.+)$", _job("widget"), re.M).group(1)
    assert "needs.quando.outputs.widget == 'true'" in cond
    assert "needs.quando.outputs.serve == 'true'" in cond
    quando = _job("quando")
    assert "widget: ${{ steps.widget.outputs.widget }}" in quando
    assert "parallelo: ${{ steps.widget.outputs.parallelo }}" in quando
    entrate = _blocco(_blocco(_blocco(_testo(), "on", 0), "workflow_dispatch", 2), "inputs", 4)
    widget = _blocco(entrate, "widget", 6)
    assert re.search(r"options:\s*\[auto, si, no\]", widget) and re.search(r"default:\s*auto", widget)


def test_i_file_dei_widget_coprono_tutto_quello_che_compila_l_anteprima():
    # se il target AnteprimaWidget compila un file nuovo, deve finire anche in FILE_WIDGET (altrimenti le foto non ripartono)
    progetto = (RADICE / "ios" / "project.yml").read_text(encoding="utf-8")
    anteprima = _blocco(_blocco(progetto, "targets", 0), "AnteprimaWidget", 2)
    percorsi = re.findall(r"^      - path:\s*(\S+)\s*$", anteprima, re.M)
    assert percorsi, "nessun sorgente per AnteprimaWidget in ios/project.yml"
    schema = re.compile(_file_widget())
    for p in percorsi:
        esempio = f"ios/{p}" if p.endswith(".swift") else f"ios/{p}/Esempio.swift"
        assert schema.search(esempio), f"{esempio} non fa ripartire le foto dei widget"
    for altro in ("ios/project.yml", "ios/scripts/screenshot_widget.sh", ".github/workflows/screenshot.yml"):
        assert schema.search(altro), altro
    for no in ("ios/Sources/Views/OggiView.swift", "ios/Sources/Domain/Modelli2.swift", "fanta/web/app.js", "ios/scripts/screenshot.sh"):
        assert not schema.search(no), no


# ------------------------------------------------------------------------------------------ bash vero, gh finto

def _trova_bash():
    for c in (r"C:\Program Files\Git\usr\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if Path(c).exists():
            return c
    return shutil.which("bash")


BASH = _trova_bash()
serve_bash = pytest.mark.skipif(not BASH, reason="serve bash (c'è su GitHub e con Git per Windows)")

GH_FINTO = r'''
gh() {
  echo "gh $*" >> "$CHIAMATE"
  [ "${GH_ROTTO:-}" = 1 ] && return 1
  case "$*" in
    *pulls/*/files*) printf '%s\n' "$FILE_PR" ;;
    *artifacts?name=screenshot-widget*) printf '%s\n' "$BASE" ;;
    *compare/*) printf '%s\n' "$FILE_CONFRONTO" ;;
    *workflows/screenshot.yml/runs*)
      # la k-esima domanda riceve il k-esimo valore di PRIMA (poi sempre l'ultimo)
      k=$(grep -c 'screenshot.yml/runs' "$CHIAMATE"); v=$(printf '%s\n' $PRIMA | sed -n "${k}p")
      [ -n "$v" ] || v=$(printf '%s\n' $PRIMA | tail -n 1)
      echo "$v" ;;
    *status=queued*) printf '%s\n' $IN_CODA ;;
    *status=in_progress*) printf '%s\n' $IN_CORSO ;;
    *actions/runs/*/jobs*) tutto="$*"; corsa=${tutto#*actions/runs/}; corsa=${corsa%%/*}; v="MAC_$corsa"; echo "${!v:-0}" ;;
    *) echo "gh finto: chiamata inattesa $*" >&2; return 1 ;;
  esac
}
sleep() { echo "sleep $*" >> "$CHIAMATE"; [ "$(grep -c '^sleep' "$CHIAMATE")" -ge 4 ] && { echo "TROPPA ATTESA"; exit 7; }; return 0; }
'''


def _esegui(tmp_path, comandi: str, **env) -> tuple[dict, str, str, int]:
    uscita = tmp_path / "output.txt"
    chiamate = tmp_path / "chiamate.txt"
    uscita.write_text("", encoding="utf-8")
    chiamate.write_text("", encoding="utf-8")
    prova = tmp_path / "passo.sh"
    prova.write_text("set -e\n" + GH_FINTO + comandi, encoding="utf-8", newline="\n")
    ambiente = {**os.environ, "PATH": str(Path(BASH).parent) + os.pathsep + os.environ.get("PATH", ""),
                "GITHUB_OUTPUT": uscita.as_posix(), "CHIAMATE": chiamate.as_posix(), "GITHUB_REPOSITORY": "esempio/repo",
                "FILE_WIDGET": _file_widget(), "COMMIT": "c" * 40}
    ambiente.update({k: str(v) for k, v in env.items()})
    r = subprocess.run([BASH, prova.as_posix()], capture_output=True, text=True, encoding="utf-8", timeout=60, env=ambiente)
    usciti = dict(r.split("=", 1) for r in uscita.read_text(encoding="utf-8").splitlines() if "=" in r)
    return usciti, chiamate.read_text(encoding="utf-8"), r.stdout + r.stderr, r.returncode


def _widget(tmp_path, **env):
    passo = _passo(_job("quando"), "Servono le foto dei widget?")
    base = dict(EVENTO="workflow_dispatch", RIF="main", SCATTI="veloce", DISPOSITIVI="iphone", RICHIESTA="auto",
                ETICHETTA_NUOVA="", PR="", FILE_PR="", BASE="", FILE_CONFRONTO="")
    base.update(env)
    usciti, chiamate, testo, codice = _esegui(tmp_path, _comandi(passo), **base)
    assert codice == 0, testo
    return usciti, chiamate


@serve_bash
@pytest.mark.parametrize("env, atteso", [
    (dict(SCATTI="completo"), "true"),                      # la corsa completa su main le fa sempre
    (dict(RICHIESTA="si"), "true"),
    (dict(RICHIESTA="no", SCATTI="completo"), "false"),     # chi le esclude a mano ha l'ultima parola
    (dict(SCATTI="vero"), "false"),                         # le foto dal vero non hanno widget
    (dict(DISPOSITIVI="ipad"), "false"),                    # come prima: con solo iPad niente widget
    (dict(EVENTO="pull_request", ETICHETTA_NUOVA="screenshot-vero", FILE_PR="ios/WidgetSources/A.swift"), "false"),
])
def test_widget_secondo_la_richiesta(tmp_path, env, atteso):
    usciti, chiamate = _widget(tmp_path, **env)
    assert usciti["widget"] == atteso
    assert "compare" not in chiamate


@serve_bash
def test_widget_su_main_solo_se_sono_cambiati_i_loro_file_dall_ultima_foto_dei_widget(tmp_path):
    base = "b" * 40
    usciti, chiamate = _widget(tmp_path, BASE=base, FILE_CONFRONTO="ios/Sources/Views/OggiView.swift\nfanta/web/app.js")
    assert usciti["widget"] == "false" and usciti["mac"] == "1"
    assert f"compare/{base}...{'c' * 40}" in chiamate
    usciti, _ = _widget(tmp_path, BASE=base, FILE_CONFRONTO="ios/Sources/Views/OggiView.swift\nios/WidgetSources/Cruscotto.swift")
    assert usciti["widget"] == "true" and usciti["parallelo"] == "false" and usciti["mac"] == "1"   # veloce: stesso Mac


@serve_bash
def test_widget_su_un_ramo_senza_foto_dei_widget_si_confronta_con_main(tmp_path):
    usciti, chiamate = _widget(tmp_path, RIF="foto-prova", FILE_CONFRONTO="ios/AnteprimaWidget/Galleria.swift")
    assert usciti["widget"] == "true"
    assert f"compare/main...{'c' * 40}" in chiamate


@serve_bash
@pytest.mark.parametrize("env", [dict(), dict(GH_ROTTO="1"), dict(BASE="b" * 40, FILE_CONFRONTO="\n".join(f"f{i}" for i in range(300)))])
def test_widget_se_non_si_sa_si_fanno(tmp_path, env):
    # su main senza foto dei widget precedenti, API che non risponde, confronto troppo lungo: meglio un Mac in più che un buco
    usciti, _ = _widget(tmp_path, **env)
    assert usciti["widget"] == "true"


@serve_bash
def test_widget_nelle_pr_con_l_etichetta_guardano_i_file_della_pr(tmp_path):
    usciti, chiamate = _widget(tmp_path, EVENTO="pull_request", PR="12", RIF="12/merge", FILE_PR="ios/Sources/Views/OggiView.swift")
    assert usciti["widget"] == "false" and "pulls/12/files" in chiamate
    usciti, _ = _widget(tmp_path, EVENTO="pull_request", PR="12", RIF="12/merge", FILE_PR="ios/project.yml")
    assert usciti["widget"] == "true"


@serve_bash
@serve_bash
@pytest.mark.parametrize("env, parallelo, mac", [
    (dict(SCATTI="veloce", RICHIESTA="si"), "false", "1"),                       # widget dopo l'app, stesso Mac
    (dict(SCATTI="veloce", RICHIESTA="no"), "false", "1"),
    (dict(SCATTI="completo"), "true", "2"),                                      # corsa lunga: due Mac insieme
    (dict(SCATTI="veloce", DISPOSITIVI="tutti", RICHIESTA="si"), "true", "2"),
    (dict(SCATTI="veloce", DISPOSITIVI="tutti", RICHIESTA="no"), "false", "1"),  # senza widget niente secondo Mac
    (dict(SCATTI="completo", RICHIESTA="no"), "false", "1"),
    (dict(SCATTI="collaudo", RICHIESTA="si"), "false", "2"),                     # app con i widget + accessibilità
    (dict(SCATTI="collaudo", RICHIESTA="no"), "false", "2"),
    (dict(SCATTI="vero"), "false", "1"),
])
def test_mac_che_servono_alla_corsa(tmp_path, env, parallelo, mac):
    usciti, _ = _widget(tmp_path, **env)
    assert (usciti["parallelo"], usciti["mac"]) == (parallelo, mac)


def _fila(tmp_path, **env):
    passo = _passo(_job("quando"), "In fila, al massimo 2 corse di foto e mai più di 5 job Mac")
    base = dict(QUESTA="500", MAC="2", PRIMA="0", IN_CODA="", IN_CORSO="")
    base.update(env)
    return _esegui(tmp_path, _comandi(passo), **base)


@serve_bash
def test_fila_parte_subito_con_posto_e_mac_liberi(tmp_path):
    _, chiamate, testo, codice = _fila(tmp_path, PRIMA="1", IN_CORSO="400 500", MAC_400="3", MAC_500="9")
    assert codice == 0 and "Tocca a questa corsa" in testo
    assert "runs/500/jobs" not in chiamate          # i job di questa corsa non contano


@serve_bash
def test_fila_aspetta_se_ci_sono_gia_due_corse_di_foto(tmp_path):
    _, chiamate, testo, codice = _fila(tmp_path, PRIMA="2 2 1")
    assert codice == 0 and "Tocca a questa corsa" in testo
    assert chiamate.count("sleep") == 2


@serve_bash
def test_fila_aspetta_se_i_mac_liberi_non_bastano(tmp_path):
    # 4 job Mac occupati (3 in corso, 1 in coda) + 2 di questa corsa = 6 > 5: si aspetta, senza scadenza propria
    _, _, testo, codice = _fila(tmp_path, IN_CORSO="400", IN_CODA="401", MAC_400="3", MAC_401="1")
    assert codice == 7 and "TROPPA ATTESA" in testo and "Tocca a questa corsa" not in testo
    _, _, testo, codice = _fila(tmp_path, IN_CORSO="400", MAC_400="3")
    assert codice == 0 and "Tocca a questa corsa" in testo


@serve_bash
def test_fila_se_gh_non_risponde_aspetta(tmp_path):
    _, _, testo, codice = _fila(tmp_path, GH_ROTTO="1")
    assert codice == 7 and "Tocca a questa corsa" not in testo


def test_i_comandi_del_job_quando_non_hanno_espressioni():
    for nome in ("Servono le foto dei widget?", "In fila, al massimo 2 corse di foto e mai più di 5 job Mac"):
        assert "${{" not in _comandi(_passo(_job("quando"), nome)), nome
