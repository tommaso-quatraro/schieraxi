"""script/squadra: `brief <issue>` riempie modello-brief.md con l'issue e con le aree di aree.json."""
from __future__ import annotations

import argparse
import re

import pytest
from test_squadra_comune import Finto

import brief
import comune

REPO = "https://github.com/esempio/progetto.git"
API = "gh api repos/{owner}/{repo}/issues/467"


def issue(etichette=("ios", "P1"), corpo="Cosa si vede: x.\n\nFatto quando: la foto è giusta.\n\nGravità: bassa.\n",
          titolo="iPhone, Rosa: il pulsante Salva va a capo", autore="proprietario", associazione="OWNER"):
    """Come la restituisce l'API REST di GitHub (gh api repos/{owner}/{repo}/issues/N)."""
    return {"number": 467, "title": titolo, "body": corpo, "labels": [{"name": e} for e in etichette],
            "user": {"login": autore}, "author_association": associazione}


def finto(i=None):
    return Finto({API: i or issue(), "git remote get-url origin": REPO + "\n"})


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
    f = Finto({API: comune.Risposta(1, "", "HTTP 404: Not Found"), "git remote get-url origin": REPO})
    assert brief.main(f, 467) == 1
    assert "404" in capsys.readouterr().err


@pytest.mark.parametrize("associazione", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_issue_del_proprietario_o_dei_collaboratori_si_accetta(capsys, associazione):
    assert brief.main(finto(issue(associazione=associazione)), 467) == 0
    testo = capsys.readouterr().out
    assert testo.startswith("Compito: ") and "autore esterno" not in testo


@pytest.mark.parametrize("associazione", ["CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE", "MANNEQUIN",
                                          "owner", "", None, "assente"])
def test_issue_di_un_autore_esterno_si_rifiuta(capsys, associazione):
    i = issue(autore="sconosciuto", associazione=associazione)
    if associazione == "assente":
        del i["author_association"]
    assert brief.main(finto(i), 467) == 1
    cattura = capsys.readouterr()
    assert cattura.out == "", "nessun brief per un'issue esterna"
    assert "sconosciuto" in cattura.err and "esterno" in cattura.err and "--accetta-esterna" in cattura.err


def test_issue_esterna_accettata_apposta_lo_scrive_in_testa(capsys):
    assert brief.main(finto(issue(autore="sconosciuto", associazione="NONE")), 467, accetta_esterna=True) == 0
    testo = capsys.readouterr().out
    prima = testo.splitlines()[0]
    assert prima.startswith("issue di un autore esterno: requisiti da verificare") and "sconosciuto" in prima
    assert "Compito: iPhone, Rosa: il pulsante Salva va a capo. Issue #467." in testo


def test_l_opzione_accetta_esterna_c_e_nella_riga_di_comando(capsys):
    p = argparse.ArgumentParser()
    brief.opzioni(p)
    assert p.parse_args(["467"]).accetta_esterna is False
    args = p.parse_args(["467", "--accetta-esterna"])
    assert args.accetta_esterna is True
    assert brief.da_riga(args, finto(issue(autore="sconosciuto", associazione="NONE"))) == 0
    assert capsys.readouterr().out.startswith("issue di un autore esterno")


def test_modello_pubblico_senza_dati_privati():
    testo = (brief.comune.CARTELLA / "modello-brief.md").read_text(encoding="utf-8")
    assert "~/.claude" not in testo and "C:\\Users" not in testo and "@" not in testo


def test_modello_dice_come_aprire_la_pr():
    testo = (brief.comune.CARTELLA / "modello-brief.md").read_text(encoding="utf-8")
    for parola in ("gh pr create --draft --body-file", "mai `--body`", "prima riga `Aree:", "Closes #{{issue}}",
                   "Parte di #{{issue}}", "## Cosa cambia", "## Perché", "## Come l'ho provato", "## Revisione` vuota"):
        assert parola in testo, parola
