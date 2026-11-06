"""script/squadra: `pr-pronta <PR>` toglie la bozza solo se tutto torna; altrimenti stampa ogni motivo ed esce con 1."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_squadra_comune import Finto

import comune
import pr_pronta

CORPO = "## Cosa cambia\nx\n## Perché\ny\n## Come l'ho provato\nz\n## Revisione\n- revisore: nessun rilievo bloccante\n"


def controlli_finti(problemi=()):
    chiamate = []

    def controlla(corpo, bozza, autore, file_con_stato, cartella_tests):
        chiamate.append({"corpo": corpo, "bozza": bozza, "autore": autore, "file": list(file_con_stato),
                         "tests": cartella_tests})
        return list(problemi), ["avviso finto"]
    return SimpleNamespace(controlla=controlla, chiamate=chiamate)


def pr(mergeable="MERGEABLE", bozza=True, corpo=CORPO, stato="OPEN", dietro=False):
    return {"number": 7, "state": stato, "isDraft": bozza, "mergeable": mergeable, "headRefOid": "t1",
            "mergeStateStatus": "BEHIND" if dietro else "CLEAN", "body": corpo, "author": {"login": "persona"}}


def risposte(p=None, file=None, corse=None, **extra):
    r = {
        "gh pr view 7": p or pr(),
        "gh api repos/{owner}/{repo}/pulls/7/files": file if file is not None else
        [{"filename": "fanta/server.py", "status": "modified"}, {"filename": "fanta/novita.d/x.json", "status": "added"}],
        "gh run list --commit t1": corse if corse is not None else
        [{"databaseId": 1, "workflowName": "Controlli", "status": "completed", "conclusion": "success",
          "event": "pull_request", "createdAt": "2026-11-06T10:00:00Z"}],
        "gh api repos/{owner}/{repo}/compare/main...t1": "0\n",
        "git fetch origin refs/pull/7/head": "",
        "gh pr ready 7": "",
    }
    r.update(extra)
    return r


def lancia(r, problemi=(), coerenza=(), **kw):
    f = Finto(r)
    c = controlli_finti(problemi)
    codice = pr_pronta.main(f, 7, controlli_pr=c, controlla_coerenza=lambda esegui, testa, file: list(coerenza), **kw)
    return codice, f, c


def test_tutto_a_posto_in_prova_non_tocca_la_bozza(capsys):
    codice, f, c = lancia(risposte())
    assert codice == 0 and not f.lanciati("gh pr ready")
    assert "PROVA" in capsys.readouterr().out
    assert c.chiamate[0]["bozza"] is False                 # la revisione si controlla come se fosse già pronta
    assert ("added", "fanta/novita.d/x.json") in c.chiamate[0]["file"]


def test_tutto_a_posto_con_esegui_toglie_la_bozza():
    codice, f, _ = lancia(risposte(), esegui_davvero=True)
    assert codice == 0 and f.lanciati("gh pr ready") == ["gh pr ready 7"]


@pytest.mark.parametrize("valore,parola", [("CONFLICTING", "conflitto"), ("UNKNOWN", "non l'ha ancora calcolato"),
                                          ("", "MERGEABLE"), ("mergeable", "MERGEABLE")])
def test_mergeable_deve_essere_esattamente_mergeable(valore, parola, capsys):
    codice, f, _ = lancia(risposte(pr(mergeable=valore)), esegui_davvero=True)
    assert codice == 1 and not f.lanciati("gh pr ready")
    assert parola in capsys.readouterr().out


@pytest.mark.parametrize("corse,parola", [
    ([], "nessuna corsa"),
    ([{"databaseId": 1, "workflowName": "Controlli", "status": "in_progress", "conclusion": "", "event": "pull_request",
       "createdAt": "2026-11-06T10:00:00Z"}], "in corso"),
    ([{"databaseId": 1, "workflowName": "Controlli", "status": "completed", "conclusion": "cancelled",
       "event": "pull_request", "createdAt": "2026-11-06T10:00:00Z"}], "infrastruttura"),
])
def test_controlli_non_verdi(corse, parola, capsys):
    assert lancia(risposte(corse=corse))[0] == 1
    assert parola in capsys.readouterr().out


def test_controllo_rosso_vero(capsys):
    r = risposte(corse=[{"databaseId": 1, "workflowName": "Controlli", "status": "completed", "conclusion": "failure",
                         "event": "pull_request", "createdAt": "2026-11-06T10:00:00Z"}],
                 **{"gh run view 1": {"jobs": [{"conclusion": "failure", "steps": [{"conclusion": "failure"}]}]}})
    assert lancia(r)[0] == 1
    assert "rosso" in capsys.readouterr().out


def test_problemi_di_descrizione_revisione_e_novita(capsys):
    codice, f, _ = lancia(risposte(), problemi=["manca la sezione «## Revisione»", "due file in novita.d"], esegui_davvero=True)
    assert codice == 1 and not f.lanciati("gh pr ready")
    uscita = capsys.readouterr().out
    assert "## Revisione" in uscita and "novita.d" in uscita


def test_coerenza_diversa(capsys):
    assert lancia(risposte(), coerenza=["il documento non è quello generato"])[0] == 1
    assert "non è quello generato" in capsys.readouterr().out


def test_ios_senza_foto_da_fare(capsys):
    file = [{"filename": "ios/Sources/Presentation/Oggi/OggiView.swift", "status": "modified"}]
    assert lancia(risposte(file=file))[0] == 1
    assert "Foto da fare" in capsys.readouterr().out
    assert lancia(risposte(p=pr(corpo=CORPO + "\nFoto da fare: oggi oggi-fondo\n"), file=file))[0] == 0


def test_foto_nel_commento_html_non_conta():
    file = [{"filename": "ios/Sources/A.swift", "status": "modified"}]
    assert lancia(risposte(p=pr(corpo=CORPO + "\n<!-- Foto da fare: oggi -->\n"), file=file))[0] == 1


def test_tutti_i_motivi_insieme(capsys):
    lancia(risposte(pr(mergeable="CONFLICTING"), corse=[]), problemi=["descrizione vuota"])
    uscita = capsys.readouterr().out
    assert "conflitto" in uscita and "nessuna corsa" in uscita and "descrizione vuota" in uscita


def test_pr_gia_unita_o_chiusa(capsys):
    assert lancia(risposte(pr(stato="MERGED")))[0] == 1
    assert "MERGED" in capsys.readouterr().out


def test_gia_fuori_dalla_bozza_non_chiama_ready():
    codice, f, _ = lancia(risposte(pr(bozza=False)), esegui_davvero=True)
    assert codice == 0 and not f.lanciati("gh pr ready")


def test_errore_di_gh_esce_con_3():
    assert lancia({"gh pr view 7": comune.Risposta(1, "", "HTTP 502")})[0] == 3


def test_controlli_di_t2_o_t3_mancanti_rifiutano(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pr_pronta.comune, "RADICE", tmp_path)       # un main senza script/ci/controlla_pr.py né coerenza.py
    f = Finto(risposte())
    assert pr_pronta.main(f, 7, esegui_davvero=True) == 1
    assert "non disponibile su questo main" in capsys.readouterr().out
    assert not f.lanciati("gh pr ready")


def test_coerenza_usa_sempre_lo_script_di_main_e_mai_quello_della_pr(tmp_path, monkeypatch):
    (tmp_path / "script").mkdir()
    (tmp_path / "script" / "coerenza.py").write_text("# main\n", encoding="utf-8")
    monkeypatch.setattr(pr_pronta.comune, "RADICE", tmp_path)
    viste = {}

    class Registra(Finto):
        def __call__(self, argomenti):
            if argomenti[0] == sys.executable:          # che cosa c'è nella cartella temporanea mentre lo script gira
                radice = Path(argomenti[argomenti.index("--radice") + 1])
                viste["file"] = sorted(x.relative_to(radice).as_posix() for x in radice.rglob("*") if x.is_file())
            return super().__call__(argomenti)

    r = {
        "git ls-tree -r --name-only t1 -- docs/coerenza docs/COERENZA-WEB-IPHONE.md":
            "docs/coerenza/vocabolario.json\ndocs/COERENZA-WEB-IPHONE.md\n",
        "git show t1:script/coerenza.py": "import os\nos.system('qualcosa di brutto')\n",
        "git show t1:docs/coerenza/vocabolario.json": "{}",
        "git show t1:docs/COERENZA-WEB-IPHONE.md": "# x\n",
        sys.executable: comune.Risposta(1, "riga doppia: id 3\n", ""),
    }
    f = Registra(r)
    problemi = pr_pronta.coerenza_vera(f, "t1", ["script/coerenza.py", "docs/coerenza/vocabolario.json"])
    assert problemi and "riga doppia" in problemi[0]
    assert not f.lanciati("git show t1:script/")                       # lo script della PR non si legge nemmeno
    [comando] = [c for c in f.chiamate if c[0] == sys.executable]
    assert comando[1] == str(tmp_path / "script" / "coerenza.py") and comando[2] == "--controlla"
    assert viste["file"] == ["docs/COERENZA-WEB-IPHONE.md", "docs/coerenza/vocabolario.json"]
    assert pr_pronta.coerenza_vera(f, "t1", ["fanta/server.py"]) == []          # la PR non tocca la coerenza


def test_nessun_file_della_pr_viene_eseguito(tmp_path, monkeypatch):
    """Tutto il comando: i soli programmi lanciati sono gh, git e lo script di coerenza di main."""
    (tmp_path / "script").mkdir()
    (tmp_path / "script" / "coerenza.py").write_text("# main\n", encoding="utf-8")
    monkeypatch.setattr(pr_pronta.comune, "RADICE", tmp_path)
    file = [{"filename": "script/coerenza.py", "status": "modified"}, {"filename": "tests/test_x.py", "status": "added"},
            {"filename": "docs/coerenza/vocabolario.json", "status": "modified"}]
    r = risposte(file=file, **{
        "git ls-tree -r --name-only t1 -- docs/coerenza docs/COERENZA-WEB-IPHONE.md": "docs/coerenza/vocabolario.json\n",
        "git show t1:docs/coerenza/vocabolario.json": "{}",
        "git show t1:tests/test_x.py": "import os\nos.system('x')\n",
        sys.executable: "",
    })
    f = Finto(r)
    pr_pronta.main(f, 7, controlli_pr=controlli_finti())
    for c in f.chiamate:
        assert c[0] in ("gh", "git") or (c[0] == sys.executable and c[1] == str(tmp_path / "script" / "coerenza.py")), c


def test_ramo_indietro_secondo_compare(capsys):
    r = risposte(**{"gh api repos/{owner}/{repo}/compare/main...t1": "3\n"})
    assert lancia(r)[0] == 1
    uscita = capsys.readouterr().out
    assert "3 commit" in uscita and "git merge origin/main" in uscita
