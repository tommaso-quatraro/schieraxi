"""I test iOS che leggono file fuori da `ios/` (issue #308).

Alcuni test iOS leggono file del server (oggi `fanta/frasi.py`; quelli della web no, dal 12/11/2026). Se una pull request cambia
solo uno di quei file, il job `cambi` di test.yml (che guardava solo `ios/`) non faceva partire i test iOS, e il segno «già verde»
di ios.yml (che guardava solo l'albero di `ios/`) li avrebbe saltati comunque: la PR si univa verde e lasciava `main` con un
test iOS rotto. Ora c'è un elenco unico, `ios/Tests/file-esterni.txt`, letto da tutti e due i workflow:

- `cambi`: i test iOS partono anche se la PR tocca un file dell'elenco;
- `gia-verde`: la chiave del segno «verde» comprende anche l'hash di quei file;
- questo file: un test iOS non può leggere un file del repository che non sta nell'elenco.

Una voce che finisce con `/` è una cartella (issue #499): vale ogni file sotto. In `cambi` conta come prefisso; nel `gia-verde`
entra nella chiave con lo sha dell'albero della cartella, quindi cambia se cambia un file qualsiasi lì sotto.

I workflow si leggono come testo (niente PyYAML) e i due passi di shell si provano davvero con un finto `gh`."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
IOS = RADICE / "ios"
ELENCO = IOS / "Tests" / "file-esterni.txt"
ELENCO_NEL_REPO = "ios/Tests/file-esterni.txt"
WORKFLOW = RADICE / ".github" / "workflows"
CARATTERI_VALIDI = re.compile(r"^[A-Za-z0-9_./-]+$")


# --- L'elenco -----------------------------------------------------------------------------------------------------------------

def _voci(testo: str) -> list[str]:
    return [r.strip() for r in testo.splitlines() if r.strip() and not r.lstrip().startswith("#")]


def voce_esiste(voce: str, radice: Path = RADICE) -> bool:
    """Una voce con `/` finale è una cartella, le altre sono file."""
    return (radice / voce).is_dir() if voce.endswith("/") else (radice / voce).is_file()


def coperto(percorso: str, voci: set[str]) -> bool:
    """Il percorso è nell'elenco: come voce, o sotto una voce cartella."""
    return percorso in voci or any(v.endswith("/") and percorso.startswith(v) for v in voci)


def test_l_elenco_esiste_ed_e_scritto_bene():
    voci = _voci(ELENCO.read_text(encoding="utf-8"))
    assert voci, "l'elenco non può essere vuoto: i workflow lo leggerebbero come un errore e farebbero girare sempre il Mac"
    assert len(voci) == len(set(voci)), "voci ripetute"
    for voce in voci:
        # caratteri semplici: i workflow le usano in un indirizzo e in un confronto a parola intera, mai come espressione
        assert CARATTERI_VALIDI.match(voce), f"{voce}: solo lettere, cifre, _ . / -"
        assert not voce.startswith(("/", "ios/")) and ".." not in voce.split("/"), f"{voce}: percorso dalla radice del repository, fuori da ios/"
        assert voce_esiste(voce), (
            f"{voce}: il file (o la cartella, con / finale) non c'è (l'API dei workflow darebbe errore e i test girerebbero sempre)")


def test_nessun_file_della_web_nell_elenco():
    # dal 12/11/2026 la web si rifà per conto suo (spec 2026-11-12-revisione-generale-design) e l'app nativa resta com'è: i test
    # iOS non leggono più il sorgente della web (i testi che servono sono copiati fermi in `TestiWeb`). Una voce di `fanta/web`
    # farebbe partire i Mac a ogni modifica della web e romperebbe i test iOS quando la web toglie una schermata.
    voci = _voci(ELENCO.read_text(encoding="utf-8"))
    assert not [v for v in voci if v.startswith("fanta/web")], (
        "i test iOS non leggono i file della web: copia nel test il dato che serve, invece di leggere fanta/web/")


def test_voce_cartella_valida_se_esiste(tmp_path):
    (tmp_path / "fanta" / "web" / "moduli").mkdir(parents=True)
    (tmp_path / "fanta" / "web" / "app.js").write_text("", encoding="utf-8")
    assert voce_esiste("fanta/web/moduli/", tmp_path)
    assert not voce_esiste("fanta/web/moduli", tmp_path)        # senza / finale è un file: lì c'è una cartella
    assert voce_esiste("fanta/web/app.js", tmp_path)
    assert not voce_esiste("fanta/web/app.js/", tmp_path)       # con / finale è una cartella: lì c'è un file
    assert not voce_esiste("fanta/web/manca/", tmp_path)


def test_un_file_sotto_una_voce_cartella_e_coperto():
    voci = {"fanta/frasi.py", "fanta/web/moduli/"}
    assert coperto("fanta/frasi.py", voci)
    assert coperto("fanta/web/moduli/oggi.js", voci)
    assert coperto("fanta/web/moduli/", voci)
    assert not coperto("fanta/web/moduli", voci)                # il nome della cartella senza / non è un file sotto
    assert not coperto("fanta/web/modulix/a.js", voci)
    assert not coperto("fanta/web/stile.css", voci)


# --- Cosa leggono i test iOS --------------------------------------------------------------------------------------------------

_LETTERALE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_PERCORSO = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+/?$")
_SALE_DI_QUATTRO = re.compile(r"0\s*\.\.<\s*[4-9]\s*\)?\s*\{[^}\n]*deleteLastPathComponent|(?:\.deletingLastPathComponent\(\)\s*){4,}")


def _senza_commento(riga: str) -> str:
    """La riga Swift senza il commento finale (un `//` dentro una stringa, come in un indirizzo, resta)."""
    for m in re.finditer(r"//", riga):
        if riga[:m.start()].count('"') % 2 == 0:
            return riga[:m.start()]
    return riga


def percorsi_esterni(testo: str) -> set[str]:
    """I percorsi del repository FUORI da `ios/` che un file di test Swift nomina fra virgolette (commenti esclusi).

    Un file che non usa `#filePath` non può raggiungere il repository: non conta. Un percorso conta solo se esiste dalla radice del
    repository e non sotto `ios/` (così `docs/...` di `ios/docs` e le parole come `lega/diario` non sono scambiate per file).
    Una cartella nominata (con o senza `/` finale) torna con la `/` finale, come le voci cartella dell'elenco."""
    if "#filePath" not in testo:
        return set()
    trovati = set()
    for riga in testo.splitlines():
        for lett in _LETTERALE.findall(_senza_commento(riga)):
            if _PERCORSO.match(lett) and not lett.startswith("ios/") and (RADICE / lett).exists() and not (IOS / lett).exists():
                trovati.add(lett.rstrip("/") + "/" if (RADICE / lett).is_dir() else lett)
    return trovati


def _test_swift() -> dict[Path, str]:
    return {f: f.read_text(encoding="utf-8") for f in sorted((IOS / "Tests").rglob("*.swift"))}


def test_ogni_file_esterno_letto_dai_test_ios_e_nell_elenco():
    voci = set(_voci(ELENCO.read_text(encoding="utf-8")))
    mancanti = {f.name: sorted(p for p in percorsi_esterni(t) if not coperto(p, voci)) for f, t in _test_swift().items()}
    mancanti = {nome: m for nome, m in mancanti.items() if m}
    assert not mancanti, (
        f"questi test iOS leggono file fuori da ios/ che non stanno in {ELENCO_NEL_REPO}: {mancanti}. "
        "Aggiungili all'elenco (uno per riga): così una PR che li cambia fa partire i test iOS e cambia la chiave del «già verde»."
    )


def test_un_test_ios_che_legge_un_file_fuori_da_ios_e_visto():
    # prova del controllo stesso: percorsi veri del repository nominati in un test che parte da #filePath
    cattivo = '''
        init(file: String = #filePath) throws {
            var url = URL(fileURLWithPath: file)
            for _ in 0..<4 { url.deleteLastPathComponent() }
            url.appendPathComponent("fanta/diario.py")   // fanta/gestione.py nel commento non conta
            let altro = "docs/COERENZA-WEB-IPHONE.md"
            let parola = "schieraxi://lega/diario"
        }'''
    assert percorsi_esterni(cattivo) == {"fanta/diario.py", "docs/COERENZA-WEB-IPHONE.md"}
    assert percorsi_esterni(cattivo.replace("#filePath", "")) == set()           # senza #filePath il repository non si raggiunge
    assert percorsi_esterni('let a = URL(string: "https://esempio.it/fanta/diario.py") // #filePath') == set()


def test_chi_sale_alla_radice_del_repository_nomina_almeno_un_file_dell_elenco():
    # un test che sale di quattro cartelle (fuori da ios/) ma costruisce il percorso con una variabile non sarebbe visto dal
    # controllo sopra: gli si chiede almeno un percorso scritto per esteso, preso dall'elenco
    voci = set(_voci(ELENCO.read_text(encoding="utf-8")))
    sale = {f.name: t for f, t in _test_swift().items() if "#filePath" in t and _SALE_DI_QUATTRO.search(t)}
    assert sale, "il controllo non trova più nessun test che sale alla radice: va aggiornato (o l'elenco non serve più)"
    for nome, testo in sale.items():
        assert any(v.rstrip("/") in testo for v in voci), f"{nome} sale alla radice del repository ma non nomina nessun file dell'elenco"


def test_ogni_voce_dell_elenco_e_letta_da_un_test_ios():
    # una voce che nessun test legge farebbe girare il Mac per niente
    voci = _voci(ELENCO.read_text(encoding="utf-8"))
    usate = set().union(*(percorsi_esterni(t) for t in _test_swift().values()))
    assert not [v for v in voci if v not in usate], "voci che nessun test iOS legge: toglile dall'elenco"


@pytest.mark.parametrize("nome", ['"fanta/web"', '"fanta/web/"'])
def test_una_voce_cartella_e_letta(nome):
    # un test Swift che nomina la cartella (con o senza / finale) la legge: la voce «fanta/web/» conta come usata
    swift = f'''
        init(file: String = #filePath) throws {{
            var url = URL(fileURLWithPath: file)
            for _ in 0..<4 {{ url.deleteLastPathComponent() }}
            let cartella = url.appendingPathComponent({nome})
        }}'''
    assert percorsi_esterni(swift) == {"fanta/web/"}


# --- I workflow ---------------------------------------------------------------------------------------------------------------

def _testo(nome: str) -> str:
    return (WORKFLOW / nome).read_text(encoding="utf-8")


def _blocco(testo: str, chiave: str, rientro: int) -> str:
    m = re.search(rf"^{' ' * rientro}{re.escape(chiave)}:.*$", testo, re.M)
    assert m, f"manca «{chiave}»"
    fine = re.search(rf"^ {{0,{rientro}}}\S", testo[m.end() + 1:], re.M)
    return testo[m.start():m.end() + 1 + fine.start()] if fine else testo[m.start():]


def _comando(file: str, job: str) -> str:
    """Il testo del `run: |` del passo `id: decidi` del job, senza il rientro."""
    blocco = _blocco(_blocco(_testo(file), "jobs", 0), job, 2)
    dopo = blocco[blocco.index("id: decidi"):]
    righe = dopo.split("run: |\n", 1)[1].splitlines()
    corpo = []
    for r in righe:
        if r.strip() and not r.startswith(" " * 10):
            break
        corpo.append(r[10:])
    return "\n".join(corpo) + "\n"


def test_i_due_workflow_leggono_lo_stesso_elenco():
    assert ELENCO_NEL_REPO in _comando("test.yml", "cambi")
    assert ELENCO_NEL_REPO in _comando("ios.yml", "gia-verde")


def test_cambi_fa_partire_ios_anche_per_i_file_dell_elenco():
    cambi = _comando("test.yml", "cambi")
    assert r"^(ios/|\.github/workflows/ios\.yml$)" in cambi                  # il confronto di prima resta
    assert "grep -qxF -f" in cambi                                            # nomi interi, mai espressioni dell'elenco
    assert "previous_filename" in cambi                                       # un file dell'elenco spostato altrove vale lo stesso
    assert "${{" not in cambi


def test_la_chiave_del_gia_verde_comprende_i_file_dell_elenco():
    gia = _comando("ios.yml", "gia-verde")
    assert re.search(r"\[0-9a-f\]\{40\}-\[0-9a-f\]\{40\}-\[0-9a-f\]\{40\}", gia), "la chiave ha tre hash: ios/, ios.yml, file esterni"
    assert "contents/$voce?ref=$COMMIT" in gia
    assert 'select(.path == env.CARTELLA and .type == "dir")' in gia               # la voce cartella non entra nell'espressione
    assert "${{" not in gia
    assert "write" not in _blocco(_blocco(_testo("ios.yml"), "jobs", 0), "gia-verde", 2)      # resta di sola lettura


# --- Prova vera dei due passi, con un finto `gh` ------------------------------------------------------------------------------

def _bash() -> str | None:
    bash = shutil.which("bash")
    if not bash:
        return None
    if sys.platform == "win32" and "git" not in bash.lower():
        return None                  # il bash di WSL non legge i percorsi di Windows
    return bash


pytestmark_bash = pytest.mark.skipif(_bash() is None, reason="serve bash (quello di Git su Windows)")

FINTO_GH = r'''#!/bin/bash
# finto gh: risponde come l'API di GitHub, già filtrata da --jq
args="$*"
case "$args" in
  *"pulls/"*"/files"*|*"compare/"*) cat "$FAKE_FILES" ;;
  *"contents/ios/Tests/file-esterni.txt"*) if [ -f "$FAKE_ELENCO" ]; then cat "$FAKE_ELENCO"; else exit 1; fi ;;
  *"git/trees/"*) echo "$FAKE_ALBERO" ;;
  *"actions/artifacts?name="*)
    nome=${args#*name=}; nome=${nome%%&*}
    if grep -qxF "$nome" "$FAKE_ARTEFATTI"; then echo 4242; else echo ""; fi ;;
  *"contents/"*)
    percorso=${args#*contents/}; percorso=${percorso%%\?*}
    if [ -n "$CARTELLA" ]; then
      # elenco della cartella madre, filtrato da --jq: lo sha dell'albero della sottocartella $CARTELLA (vuoto se non c'è)
      madre=${CARTELLA%/*}; [ "$madre" != "$CARTELLA" ] || madre=""
      if [ "$percorso" != "$madre" ]; then echo "finto gh: madre $percorso, attesa $madre" >&2; exit 1; fi
      awk -v p="$CARTELLA/" '$1 == p { print $2; exit }' "$FAKE_SHAS"
      exit 0
    fi
    # una cartella risponde con una lista: «--jq .sha» dà errore, come nell'API vera
    if awk -v p="${percorso%/}/" '$1 == p { t = 1 } END { exit !t }' "$FAKE_SHAS"; then echo "finto gh: .sha su una cartella" >&2; exit 1; fi
    riga=$(grep -F "$percorso " "$FAKE_SHAS" | head -n 1) || exit 1
    [ -n "$riga" ] || exit 1
    echo "${riga##* }" ;;
  *) echo "finto gh: chiamata non prevista: $args" >&2; exit 1 ;;
esac
'''

ALBERO = "a" * 40
SHA_IOS_YML = "b" * 40
SHA_FRASI = "c" * 40
SHA_TESTI = "d" * 40
ELENCO_DI_PROVA = "# prova\nfanta/frasi.py\n\nfanta/web/testi.js\n"


class Banco:
    """Una cartella con il finto gh e i file che gli servono; `esegui` lancia il passo di shell di un job."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        (tmp / "bin").mkdir()
        (tmp / "bin" / "gh").write_bytes(FINTO_GH.encode())
        (tmp / "bin" / "gh").chmod(0o755)
        self.files = ""
        self.elenco: str | None = ELENCO_DI_PROVA
        self.shas = {"fanta/frasi.py": SHA_FRASI, "fanta/web/testi.js": SHA_TESTI, ".github/workflows/ios.yml": SHA_IOS_YML}
        self.artefatti: list[str] = []

    def _scrivi(self, nome: str, testo: str) -> str:
        (self.tmp / nome).write_bytes(testo.encode())
        return str(self.tmp / nome)

    def esegui(self, file: str, job: str, **extra: str) -> dict[str, str]:
        script = self._scrivi("passo.sh", _comando(file, job))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "FAKE_")) and k != "CARTELLA"}
        env.update(
            PATH=str(self.tmp / "bin") + os.pathsep + os.environ["PATH"],
            GH_TOKEN="finto", GITHUB_REPOSITORY="o/r", GITHUB_SERVER_URL="https://esempio.invalid",
            GITHUB_OUTPUT=self._scrivi("uscita.txt", ""), GITHUB_STEP_SUMMARY=self._scrivi("riepilogo.txt", ""),
            FAKE_FILES=self._scrivi("files.txt", self.files), FAKE_ALBERO=ALBERO, FAKE_ARTEFATTI=self._scrivi("artefatti.txt", "\n".join(self.artefatti) + "\n"),
            FAKE_SHAS=self._scrivi("shas.txt", "".join(f"{p} {s}\n" for p, s in self.shas.items())),
        )
        if self.elenco is not None:
            env["FAKE_ELENCO"] = self._scrivi("elenco.txt", self.elenco)
        env.update(extra)
        subprocess.run([_bash(), "-e", script], env=env, check=True, capture_output=True, text=True, timeout=60)
        uscita = dict(r.split("=", 1) for r in (self.tmp / "uscita.txt").read_text(encoding="utf-8").splitlines() if "=" in r)
        uscita["_riepilogo"] = (self.tmp / "riepilogo.txt").read_text(encoding="utf-8")
        return uscita

    def cambi(self, files: list[str]) -> str:
        self.files = "\n".join(files) + "\n"
        return self.esegui("test.yml", "cambi", EVENTO="pull_request", PR="7", RIF="refs/pull/7/merge", PRIMA="", DOPO="e" * 40)["ios"]

    def gia_verde(self, **extra: str) -> dict[str, str]:
        return self.esegui("ios.yml", "gia-verde", **{"COMMIT": "e" * 40, "REPO_ID": "1", "FORZA": "false", **extra})


@pytest.fixture
def banco(tmp_path):
    return Banco(tmp_path)


@pytestmark_bash
@pytest.mark.parametrize("files, atteso", [
    (["fanta/web/testi.js"], "true"),                         # il caso della #306: un file letto da un test iOS
    (["fanta/frasi.py", "README.md"], "true"),
    (["ios/Sources/Domain/Quando.swift"], "true"),            # come prima
    ([".github/workflows/ios.yml"], "true"),
    ([ELENCO_NEL_REPO], "true"),                              # l'elenco sta in ios/
    (["fanta/web/app.js", "fanta/diario.py", "docs/API.md"], "false"),            # file che nessun test iOS legge
    (["fanta/web/testi.js.bak", "xfanta/frasi.py", "fanta/frasi.pyc"], "false"),  # nomi interi, non pezzi di nome
])
def test_cambi_decide_con_l_elenco(banco, files, atteso):
    assert banco.cambi(files) == atteso


@pytestmark_bash
def test_con_l_elenco_vero_una_modifica_alla_web_non_fa_partire_i_mac(banco):
    banco.elenco = ELENCO.read_text(encoding="utf-8")
    web = ["fanta/web/app.js", "fanta/web/testi.js", "fanta/web/dafare.js", "fanta/web/live.js", "fanta/web/stile.css"]
    assert banco.cambi(web) == "false"
    assert banco.cambi(web + ["ios/Sources/Domain/Quando.swift"]) == "true"      # con un file di ios/ i test partono come prima


@pytestmark_bash
@pytest.mark.parametrize("elenco", [
    None,                                  # elenco illeggibile (l'API non risponde)
    "",                                    # vuoto
    "# solo commenti\n",
    "fanta/frasi.py\nfanta/**/*.js\n",     # riga che non è un nome di file
    "fanta/frasi.py\n$(echo x)\n",
    # fine riga di Windows: il nome non combacerebbe mai (il bash di Git per Windows toglie da solo il \r: lì non si prova)
    pytest.param("fanta/frasi.py\r\n", marks=pytest.mark.skipif(sys.platform == "win32", reason="il bash di Git toglie il CR")),
])
def test_cambi_con_elenco_strano_fa_girare_i_test(banco, elenco):
    banco.elenco = elenco
    assert banco.cambi(["docs/API.md"]) == "true"          # meglio un Mac in più che un buco


@pytestmark_bash
def test_la_chiave_cambia_se_cambia_un_file_dell_elenco(banco):
    prima = banco.gia_verde()
    assert re.fullmatch(r"[0-9a-f]{40}-[0-9a-f]{40}-[0-9a-f]{40}", prima["chiave"]), prima["chiave"]
    assert prima["verde"] == "false"
    assert prima["chiave"] in prima["_riepilogo"], "la chiave deve comparire nel riepilogo della corsa"
    assert "fanta/frasi.py" in prima["_riepilogo"] and "fanta/web/testi.js" in prima["_riepilogo"]
    assert banco.gia_verde()["chiave"] == prima["chiave"]                            # stessa roba, stessa chiave

    banco.shas["fanta/frasi.py"] = "9" * 40                                           # cambia un file esterno
    dopo = banco.gia_verde()
    assert dopo["chiave"] != prima["chiave"]

    banco.shas["fanta/frasi.py"] = SHA_FRASI                                          # e torna com'era
    assert banco.gia_verde()["chiave"] == prima["chiave"]


@pytestmark_bash
def test_un_file_esterno_cambiato_fa_ripartire_i_test(banco):
    chiave = banco.gia_verde()["chiave"]
    banco.artefatti = [f"ios-verde-{chiave}"]                                         # una corsa ha già provato questo codice
    gia = banco.gia_verde()
    assert gia["verde"] == "true" and gia["chiave"] == chiave
    assert "già verde" in gia["_riepilogo"]
    # cambia solo un file esterno: ios/ è uguale, ma la chiave è un'altra e i test girano
    banco.shas["fanta/web/testi.js"] = "8" * 40
    nuova = banco.gia_verde()
    assert nuova["verde"] == "false" and nuova["chiave"] != chiave
    # a mano si può forzare comunque
    banco.shas["fanta/web/testi.js"] = SHA_TESTI
    assert banco.gia_verde(FORZA="true")["verde"] == "false"


@pytestmark_bash
@pytest.mark.parametrize("guasto", ["elenco-illeggibile", "elenco-vuoto", "elenco-strano", "file-mancante"])
def test_ogni_errore_nel_gia_verde_fa_girare_i_test(banco, guasto):
    chiave = banco.gia_verde()["chiave"]
    banco.artefatti = [f"ios-verde-{chiave}"]                      # il segno c'è: solo un errore può impedire di usarlo
    if guasto == "elenco-illeggibile":
        banco.elenco = None
    elif guasto == "elenco-vuoto":
        banco.elenco = "# niente\n"
    elif guasto == "elenco-strano":
        banco.elenco = "fanta/frasi.py\n`ls`\n"
    else:
        del banco.shas["fanta/web/testi.js"]
    gia = banco.gia_verde()
    assert gia["verde"] == "false" and gia["chiave"] == ""


# --- Voci cartella (issue #499) -----------------------------------------------------------------------------------------------

@pytestmark_bash
@pytest.mark.parametrize("elenco, files, atteso", [
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["fanta/web/moduli/oggi.js"], "true"),
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["docs/API.md", "fanta/web/moduli/sotto/a.js"], "true"),
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["fanta/web/stile.css"], "false"),
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["fanta/web/moduli"], "false"),       # un file con il nome della cartella
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["fanta/web/modulix/a.js", "xfanta/web/moduli/a.js"], "false"),  # solo prefisso intero
    (ELENCO_DI_PROVA + "fanta/web/moduli/\n", ["fanta/frasi.py"], "true"),          # le voci file valgono come prima
    ("fanta/web/moduli/\n", ["fanta/web/moduli/oggi.js"], "true"),                  # elenco di sole cartelle
    ("fanta/web/moduli/\n", ["docs/API.md"], "false"),
])
def test_cambi_con_una_cartella_nell_elenco(banco, elenco, files, atteso):
    banco.elenco = elenco
    assert banco.cambi(files) == atteso


@pytestmark_bash
@pytest.mark.parametrize("cartella", ["fanta/web/moduli/", "prove/"])     # sotto un'altra cartella e nella radice
def test_la_chiave_cambia_se_cambia_un_file_della_cartella(banco, cartella):
    banco.elenco = ELENCO_DI_PROVA + cartella + "\n"
    banco.shas[cartella] = "1" * 40                                       # sha dell'albero della cartella
    prima = banco.gia_verde()
    assert re.fullmatch(r"[0-9a-f]{40}-[0-9a-f]{40}-[0-9a-f]{40}", prima["chiave"]), prima["chiave"]
    assert cartella in prima["_riepilogo"]
    assert banco.gia_verde()["chiave"] == prima["chiave"]                 # stessa roba, stessa chiave

    banco.shas[cartella] = "2" * 40                                       # cambia un file lì sotto: cambia l'albero
    assert banco.gia_verde()["chiave"] != prima["chiave"]

    banco.shas[cartella] = "1" * 40
    assert banco.gia_verde()["chiave"] == prima["chiave"]


@pytestmark_bash
def test_una_cartella_che_manca_nel_gia_verde_fa_girare_i_test(banco):
    banco.elenco = ELENCO_DI_PROVA + "fanta/web/moduli/\n"                 # nessuno sha: la cartella non c'è
    chiave_senza = banco.gia_verde()
    assert chiave_senza["verde"] == "false" and chiave_senza["chiave"] == ""
