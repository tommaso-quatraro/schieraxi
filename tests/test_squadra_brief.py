"""script/squadra: `brief <issue>` riempie modello-brief.md con l'issue e con le aree di aree.json."""
from __future__ import annotations

import re

from test_squadra_comune import Finto

import brief
import comune

REPO = "https://github.com/esempio/progetto.git"


def issue(etichette=("ios", "P1"), corpo="Cosa si vede: x.\n\nFatto quando: la foto è giusta.\n\nGravità: bassa.\n",
          titolo="iPhone, Rosa: il pulsante Salva va a capo"):
    return {"number": 467, "title": titolo, "body": corpo, "labels": [{"name": e} for e in etichette]}


def finto(i=None):
    return Finto({"gh issue view 467": i or issue(), "git remote get-url origin": REPO + "\n"})


def test_riempie_titolo_fatto_quando_e_aree(capsys):
    assert brief.main(finto(), 467) == 0
    testo = capsys.readouterr().out
    assert "Compito: iPhone, Rosa: il pulsante Salva va a capo. Issue #467." in testo
    assert "la foto è giusta." in testo and "Gravità" not in testo
    assert "Agente: sviluppatore-ios, modello opus." in testo
    tocca = re.search(r"^Puoi toccare: (.*)$", testo, re.M).group(1)
    assert "ios/**" in tocca and "tests/**" in tocca and "fanta/**" not in tocca      # da aree.json
    assert "fanta/**" in re.search(r"^NON toccare: (.*)$", testo, re.M).group(1)
    assert REPO in testo
    assert "{{" not in testo and "<!--" not in testo


def test_ramo_predefinito_dal_titolo():
    assert brief.ramo_predefinito(467, "iPhone, Rosa: il pulsante «Salva» va a capo") == "iphone-rosa-il-pulsante-salva-467"
    assert brief.ramo_predefinito(5, "Perché è così?") == "perche-e-cosi-5"


def test_fatto_quando_come_titolo_di_sezione():
    corpo = "## Cosa\nbla\n\n## Fatto quando\n- prima cosa\n- seconda cosa\n\n## Fuori ambito\nniente\n"
    assert brief.fatto_quando(corpo) == "- prima cosa\n- seconda cosa"
    assert brief.fatto_quando("**Fatto quando:** i test passano.\naltro\n\nPoi") == "i test passano.\naltro"
    assert brief.fatto_quando("niente") is None


def test_opzioni_correggono_agente_modello_ramo_e_tocca(capsys):
    assert brief.main(finto(), 467, agente="sviluppatore-web", modello="sonnet", ramo="mio-ramo",
                      tocca=["fanta/web/app.js", "tests/test_x.py"]) == 0
    testo = capsys.readouterr().out
    assert "Agente: sviluppatore-web, modello sonnet." in testo
    assert "ramo mio-ramo (`git switch -c mio-ramo`)" in testo
    assert "Puoi toccare: `fanta/web/app.js`, `tests/test_x.py`." in testo


def test_senza_area_e_senza_fatto_quando_avvisa_ed_esce_con_3(capsys):
    assert brief.main(finto(issue(etichette=("P2",), corpo="solo testo")), 467) == 3
    cattura = capsys.readouterr()
    assert "<da scrivere" in cattura.out
    assert "etichetta di area" in cattura.err and "Fatto quando" in cattura.err


def test_issue_che_non_esiste_esce_con_1(capsys):
    f = Finto({"gh issue view 467": comune.Risposta(1, "", "Could not resolve to an issue"),
               "git remote get-url origin": REPO})
    assert brief.main(f, 467) == 1
    assert "resolve" in capsys.readouterr().err


def test_modello_pubblico_senza_dati_privati():
    testo = (brief.comune.CARTELLA / "modello-brief.md").read_text(encoding="utf-8")
    assert "~/.claude" not in testo and "C:\\Users" not in testo and "@" not in testo


def test_modello_dice_come_aprire_la_pr():
    testo = (brief.comune.CARTELLA / "modello-brief.md").read_text(encoding="utf-8")
    for parola in ("gh pr create --draft --body-file", "mai `--body`", "prima riga `Aree:", "Closes #{{issue}}",
                   "Parte di #{{issue}}", "## Cosa cambia", "## Perché", "## Come l'ho provato", "## Revisione` vuota"):
        assert parola in testo, parola
