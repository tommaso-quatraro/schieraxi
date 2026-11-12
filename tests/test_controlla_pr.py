"""Controlli della PR (script/ci/controlla_pr.py): descrizione, revisione registrata, novità solo della PR, test che leggono
una novità per nome. Corpi di PR inventati sul modello di quelle vere, senza dati privati."""
import importlib.util
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("controlla_pr", RADICE / "script" / "ci" / "controlla_pr.py")
pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr)

MODELLO = (RADICE / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")

BUONO = """Closes #440. Parte di #167.

Aree: fanta/web, tests

## Cosa cambia
- La riga del giocatore dice «gioca» come sull'iPhone.

## Perché
Le due app dicevano due cose diverse.

## Come l'ho provato
- `pytest -q tests/test_etichette_web.py`: rosso prima, verde dopo.

## Revisione
- revisore: nessun rilievo bloccante
- /code-review: due rilievi minori, chiusi nel commit abc1234
"""


# ---------------------------------------------------------------- descrizione

def test_descrizione_completa_senza_problemi_ne_avvisi():
    assert pr.descrizione(BUONO) == ([], [])


def test_il_modello_vuoto_non_basta():
    problemi, _ = pr.descrizione(MODELLO)
    testo = "\n".join(problemi)
    for sezione in ("Cosa cambia", "Perché", "Come l'ho provato"):
        assert sezione in testo


def test_sezione_mancante_o_vuota_o_solo_commento():
    senza_perche = BUONO.replace("## Perché\nLe due app dicevano due cose diverse.\n", "")
    problemi, _ = pr.descrizione(senza_perche)
    assert len(problemi) == 1 and "Perché" in problemi[0]
    vuota = BUONO.replace("Le due app dicevano due cose diverse.", "  \n")
    assert any("Perché" in p for p in pr.descrizione(vuota)[0])
    commento = BUONO.replace("Le due app dicevano due cose diverse.", "<!-- perché serve -->")
    assert any("Perché" in p for p in pr.descrizione(commento)[0])


def test_titoli_scritti_in_modo_diverso_valgono():
    corpo = "### cosa cambia\nx\n## PERCHÉ\ny\n## Come l’ho provato:\nz\nCloses #3"
    assert pr.descrizione(corpo) == ([], [])


def test_una_sezione_comprende_i_suoi_sottotitoli():
    """«## Cosa cambia» con dei «###» sotto non è vuota: finisce al primo titolo di livello uguale o più alto."""
    corpo = BUONO.replace("## Cosa cambia\n- La riga del giocatore dice «gioca» come sull'iPhone.\n",
                          "## Cosa cambia\n### Web\n- riga nuova\n### iPhone\n- riga nuova\n")
    assert pr.descrizione(corpo) == ([], [])
    corpo = BUONO.replace("## Revisione\n", "## Revisione\n### Revisore\n")
    assert pr.revisione(corpo, bozza=False, autore="persona", file=["fanta/server.py"]) == ([], [])
    # un titolo più alto chiude la sezione: «# Altro» dopo «## Perché» vuoto la lascia vuota
    corpo = BUONO.replace("Le due app dicevano due cose diverse.\n", "# Altro\ntesto fuori\n")
    assert any("Perché" in p for p in pr.descrizione(corpo)[0])


def test_un_commento_dentro_un_blocco_di_codice_non_e_un_titolo():
    corpo = BUONO.replace("## Revisione", "```sh\n# Revisione\npytest -q\n```\n\n## Revisione")
    assert pr.descrizione(corpo) == ([], [])
    assert pr.revisione(corpo, bozza=False, autore="persona", file=["fanta/server.py"]) == ([], [])
    corpo = BUONO.replace("Le due app dicevano due cose diverse.", "```\n# solo codice\n```")
    assert pr.descrizione(corpo) == ([], [])


def test_issue_mancante_e_solo_un_avviso():
    corpo = BUONO.replace("Closes #440. Parte di #167.", "")
    problemi, avvisi = pr.descrizione(corpo)
    assert problemi == [] and len(avvisi) == 1 and "Closes #N" in avvisi[0]
    assert pr.descrizione(BUONO.replace("Closes #440.", ""))[1] == []          # «Parte di #N» basta
    assert pr.descrizione(corpo.replace("Aree:", "Closes #\nAree:"))[1] != []     # «Closes #» del modello senza numero


def test_corpo_vuoto_o_none():
    assert len(pr.descrizione("")[0]) == 3
    assert len(pr.descrizione(None)[0]) == 3


# ---------------------------------------------------------------- revisione

def test_revisione_registrata():
    assert pr.revisione(BUONO, bozza=False, autore="persona", file=["fanta/web/app.js"]) == ([], [])


def test_revisione_obbligatoria_fuori_dalla_bozza():
    senza = BUONO.split("## Revisione")[0]
    problemi, _ = pr.revisione(senza, bozza=False, autore="persona", file=["fanta/web/app.js"])
    assert len(problemi) == 1 and "## Revisione" in problemi[0]
    assert pr.revisione(senza, bozza=True, autore="persona", file=["fanta/web/app.js"]) == ([], [])


def test_revisione_vuota_o_senza_righe_chi_esito():
    for sezione in ("## Revisione\n", "## Revisione\n<!-- - revisore: esito -->\n", "## Revisione\nfatta\n",
                    "## Revisione\n- revisore:\n", "## Revisione\n- : ok\n"):
        corpo = BUONO.split("## Revisione")[0] + sezione
        problemi, _ = pr.revisione(corpo, bozza=False, autore="persona", file=["fanta/server.py"])
        assert problemi, sezione


def test_il_modello_ha_la_sezione_revisione_con_un_esempio_che_vale():
    assert "## Revisione" in MODELLO
    esempio = MODELLO.split("## Revisione", 1)[1].split("-->", 1)[0].split("Esempio:", 1)[1]
    corpo = BUONO.split("## Revisione")[0] + "## Revisione\n" + esempio
    assert pr.revisione(corpo, bozza=False, autore="persona", file=["fanta/server.py"]) == ([], [])


def test_revisione_dal_modello_vuoto_non_basta():
    problemi, _ = pr.revisione(MODELLO, bozza=False, autore="persona", file=["fanta/server.py"])
    assert problemi


def test_revisione_esenti_bot_e_soli_documenti():
    senza = BUONO.split("## Revisione")[0]
    assert pr.revisione(senza, bozza=False, autore="dependabot[bot]", file=["requirements.txt"]) == ([], [])
    assert pr.revisione(senza, bozza=False, autore="persona", file=["docs/A.md", "MAPPA.md"]) == ([], [])
    assert pr.revisione(senza, bozza=False, autore="persona", file=["docs/A.md", "fanta/server.py"])[0]


@pytest.mark.parametrize("file", [".claude/skills/revisione-pr/SKILL.md", ".claude/agents/revisore.md",
                                  ".github/PULL_REQUEST_TEMPLATE.md", "CLAUDE.md", "ios/CLAUDE.md"])
def test_regole_della_revisione_e_della_ci_non_sono_soli_documenti(file):
    senza = BUONO.split("## Revisione")[0]
    assert pr.revisione(senza, bozza=False, autore="persona", file=["docs/A.md", file])[0]


def test_soli_documenti_ha_una_definizione_sola():
    """La definizione sta in controlla_ambito.py; controlla_pr.py la prende da lì (in CI tutti e due da _ci-main)."""
    sorgente = (RADICE / "script" / "ci" / "controlla_pr.py").read_text(encoding="utf-8")
    assert "def _soli_documenti" not in sorgente and "def solo_documenti" not in sorgente
    assert "controlla_ambito.py" in sorgente


def test_revisione_con_un_altra_sezione_dopo():
    corpo = BUONO + "\n## Foto da fare: oggi\n- revisore: questa riga non è nella revisione\n"
    assert pr.revisione(corpo, bozza=False, autore="persona", file=["ios/A.swift"]) == ([], [])
    corpo = BUONO.split("## Revisione")[0] + "## Revisione\n\n## Altro\n- revisore: fuori\n"
    assert pr.revisione(corpo, bozza=False, autore="persona", file=["ios/A.swift"])[0]


# ---------------------------------------------------------------- novità

def test_novita_un_file_aggiunto_va_bene():
    assert pr.novita([("A", "fanta/novita.d/riga-nuova.json"), ("M", "fanta/web/app.js")]) == ([], [])
    assert pr.novita([("M", "fanta/web/app.js")]) == ([], [])


def test_novita_due_file_aggiunti():
    problemi, _ = pr.novita([("A", "fanta/novita.d/uno.json"), ("A", "fanta/novita.d/due.json")])
    assert len(problemi) == 1 and "uno.json" in problemi[0] and "due.json" in problemi[0]


@pytest.mark.parametrize("voce", [
    ("M", "fanta/novita.d/di-un-altra.json"),
    ("D", "fanta/novita.d/di-un-altra.json"),
    ("R100", "fanta/novita.d/di-un-altra.json", "fanta/novita.d/mia.json"),
    ("R090", "fanta/web/x.json", "fanta/novita.d/mia.json"),
])
def test_novita_file_di_altre_pr_modificati_tolti_o_rinominati(voce):
    problemi, _ = pr.novita([voce])
    assert len(problemi) == 1 and "fanta/novita.d/" in problemi[0]


def test_novita_json_non_si_tocca_a_mano():
    problemi, _ = pr.novita([("M", "fanta/novita.json")])
    assert len(problemi) == 1 and "fanta/novita.json" in problemi[0]


def test_novita_con_gli_stati_di_github():
    """`pr-pronta` prende i file dall'API di GitHub (added, modified, removed, renamed)."""
    assert pr.novita([("added", "fanta/novita.d/mia.json")]) == ([], [])
    assert pr.novita([("removed", "fanta/novita.d/altra.json")])[0]
    assert pr.novita([("renamed", "fanta/novita.d/altra.json", "fanta/novita.d/mia.json")])[0]


def test_leggi_name_status():
    testo = "A\tfanta/novita.d/mia.json\nM\tfanta/web/app.js\nR100\tdocs/a.md\tdocs/b.md\n\n"
    assert pr.leggi_name_status(testo) == [("A", "fanta/novita.d/mia.json"), ("M", "fanta/web/app.js"),
                                           ("R100", "docs/a.md", "docs/b.md")]
    assert pr.percorsi(pr.leggi_name_status(testo)) == ["fanta/novita.d/mia.json", "fanta/web/app.js", "docs/a.md", "docs/b.md"]


# ---------------------------------------------------------------- test che leggono una novità per nome

ND = "novita." + "d"            # scritto a pezzi: questo file non deve sembrare un test che legge una novità per nome


def _scrivi(cartella, nome, testo):
    (cartella / nome).write_text(testo, encoding="utf-8")


@pytest.mark.parametrize("riga", [
    f'voce = json.loads((RADICE / "fanta" / "{ND}" / "riga-nuova.json").read_text())',
    f'voce = json.loads((RADICE / "fanta/{ND}/riga-nuova.json").read_text())',
    f'percorso = RADICE / "fanta" / "{ND}" / nome_del_file',
    f'voce = open("fanta/{ND}/riga-nuova.json").read()',
    f'voce = Path("fanta/{ND}/riga-nuova.json").read_text()',
    f'voce = (RADICE / "fanta/{ND}" / nome).read_text()',
    f'voce = (RADICE / f"fanta/{ND}/riga-nuova.json").read_text()',
    f'voce = (RADICE / f"fanta/{ND}/{{nome}}.json").read_text()',
    f'voce = json.loads((tmp_path / "fanta" / "{ND}" / "x.json").read_text())',
])
def test_per_nome_trova_le_letture(tmp_path, riga):
    _scrivi(tmp_path, "test_x.py", f"from pathlib import Path\n\n\ndef test_a():\n    {riga}\n")
    problemi, _ = pr.test_per_nome(tmp_path)
    assert len(problemi) == 1 and "test_x.py:5" in problemi[0]


@pytest.mark.parametrize("riga", [
    f'tutte = sorted((RADICE / "fanta" / "{ND}").glob("*.json"))',
    f'(tmp_path / "fanta" / "{ND}" / "finta.json").write_text("{{}}")',
    f'file = ["fanta/web/app.js", "fanta/{ND}/x.json"]',
    'voce = json.loads((RADICE / "fanta" / "novita.json").read_text())',
    'voce = json.loads((RADICE / "tests" / "dati" / "novita-finta.json").read_text())',
    # il rimedio consigliato: una novità finta in una cartella di prova, anche se la cartella si chiama novita.d
    f'voce = json.loads((DATI / "{ND}" / "finta.json").read_text())',
    f'voce = json.loads((RADICE / "tests" / "dati" / "{ND}" / "finta.json").read_text())',
    # scritture e cancellazioni non sono letture
    f'(RADICE / "fanta" / "{ND}" / "finta.json").write_text("{{}}")',
    f'(repo / "fanta" / "{ND}" / "finta.json").write_bytes(b"{{}}")',
    f'(repo / "fanta/{ND}/finta.json").unlink()',
    f'open(RADICE / "fanta" / "{ND}" / "finta.json", "w")',
    f'open("fanta/{ND}/finta.json", mode="a")',
])
def test_per_nome_lascia_stare_il_resto(tmp_path, riga):
    _scrivi(tmp_path, "test_x.py", f"from pathlib import Path\n\n\ndef test_a(tmp_path):\n    {riga}\n")
    assert pr.test_per_nome(tmp_path) == ([], [])


def test_per_nome_guarda_anche_le_sottocartelle_e_avvisa_dei_file_illeggibili(tmp_path):
    (tmp_path / "strumenti").mkdir()
    _scrivi(tmp_path / "strumenti", "aiuto.py", f'X = open("fanta/{ND}/a.json")\n')
    _scrivi(tmp_path, "test_rotto.py", "def (:\n")
    problemi, avvisi = pr.test_per_nome(tmp_path)
    assert len(problemi) == 1 and "aiuto.py" in problemi[0]
    assert len(avvisi) == 1 and "test_rotto.py" in avvisi[0]


def test_nessun_test_del_repository_legge_una_novita_per_nome():
    problemi, _ = pr.test_per_nome(RADICE / "tests")
    assert problemi == []


# ---------------------------------------------------------------- base della PR (#620)

def test_base_main_va_bene_e_base_sconosciuta_non_dice_niente():
    assert pr.base("main") == ([], [])
    assert pr.base("") == ([], []) and pr.base(None) == ([], [])      # variabile non passata (workflow di prima)


@pytest.mark.parametrize("ramo", ["web-nel-browser-619", "Main", "main2", "release"])
def test_base_diversa_da_main_e_un_problema(ramo):
    problemi, avvisi = pr.base(ramo)
    assert len(problemi) == 1 and avvisi == []
    assert f"«{ramo}»" in problemi[0] and "main" in problemi[0] and "--base main" in problemi[0]


def test_controlla_e_main_guardano_la_base(tmp_path, capsys):
    problemi, _ = pr.controlla(BUONO, bozza=False, autore="persona", file_con_stato=[("M", "fanta/web/app.js")],
                               cartella_tests=tmp_path, ramo_base="altro-ramo")
    assert len(problemi) == 1 and "«altro-ramo»" in problemi[0]
    # anche i bot: una PR impilata non si unisce su main in nessun caso
    assert pr.controlla("", bozza=False, autore="dependabot[bot]", file_con_stato=[("M", "requirements.txt")],
                        cartella_tests=tmp_path, ramo_base="altro-ramo")[0]
    assert pr.main("persona", BUONO, "false", "M\tfanta/web/app.js\n", tmp_path, base="altro-ramo") == 1
    assert "::error title=Base della PR::" in capsys.readouterr().out
    assert pr.main("persona", BUONO, "false", "M\tfanta/web/app.js\n", tmp_path, base="main") == 0


def test_il_job_ambito_passa_la_base_a_controlla_pr():
    testo = (RADICE / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    ambito = testo[testo.index("\n  ambito:\n"):testo.index("\n  versione:\n")]
    passo = ambito[ambito.index("- name: Descrizione, revisione, novità e test della PR"):]
    passo = passo[:passo.index("run:")]
    assert "BASE: ${{ github.base_ref }}" in passo


# ---------------------------------------------------------------- tutto insieme e uscita

def test_controlla_mette_insieme_i_quattro_controlli(tmp_path):
    problemi, avvisi = pr.controlla(BUONO, bozza=False, autore="persona",
                                    file_con_stato=[("A", "fanta/novita.d/a.json")], cartella_tests=tmp_path)
    assert (problemi, avvisi) == ([], [])
    problemi, _ = pr.controlla("", bozza=False, autore="persona",
                               file_con_stato=[("M", "fanta/novita.json")], cartella_tests=tmp_path)
    assert len(problemi) == 5          # tre sezioni, la revisione, novita.json


def test_controlla_esenta_i_bot_da_descrizione_e_revisione(tmp_path):
    assert pr.controlla("", bozza=False, autore="dependabot[bot]", file_con_stato=[("M", "requirements.txt")],
                        cartella_tests=tmp_path) == ([], [])


def test_main_codici_e_messaggi(tmp_path, capsys):
    assert pr.main("persona", BUONO, "false", "M\tfanta/web/app.js\n", tmp_path) == 0
    assert "Controlli della PR: tutto a posto" in capsys.readouterr().out
    assert pr.main("persona", "", "true", "M\tfanta/web/app.js\n", tmp_path) == 1
    uscita = capsys.readouterr().out
    assert "::error title=Descrizione della PR::" in uscita and "## Revisione" not in uscita     # in bozza non serve
    pr.main("persona", BUONO.replace("Closes #440. Parte di #167.", ""), "false", "M\tfanta/web/app.js\n", tmp_path)
    assert "::warning title=Descrizione della PR::" in capsys.readouterr().out
