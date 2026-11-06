"""script/squadra: `giro` fa la procedura del coordinatore e stampa solo ciò che è cambiato dal giro prima."""
from __future__ import annotations

import copy
import json

from test_squadra_comune import Finto
from test_squadra_stato import ADESSO, risposte_stato

import comune
import giro

SW = 'const VERSIONE = "fanta-230";\n'


def risposte(**extra):
    r = copy.deepcopy(risposte_stato())
    r.update({
        "gh run list --status waiting": [],
        "gh run list --status pending": [],
        "git ls-remote --heads origin": "testa-a\trefs/heads/a\ntesta-b\trefs/heads/b\n",
        "gh run list --commit testa-b": [{"databaseId": 50, "workflowName": "Controlli", "status": "completed",
                                          "conclusion": "failure", "event": "pull_request", "createdAt": "2026-11-06T10:00:00Z"}],
        "gh run view 50": {"jobs": [{"name": "test", "conclusion": "failure", "steps": []}]},     # guasto d'infrastruttura
        "gh run view 50 --json attempt": {"attempt": 1},
        "gh run rerun": "",
        "gh run cancel": "",
    })
    for c in r["gh run list --status in_progress"] + r["gh run list --status queued"]:
        c["headSha"] = {"a": "testa-a", "b": "testa-b"}.get(c["headBranch"], "x")
    for p in r["gh pr list --state open"]:
        p["headRefOid"] = {20: "testa-a", 21: "testa-b", 22: "testa-c"}[p["number"]]
    r.update(extra)
    return r


def lancia(tmp_path, r=None, url=None, **kw):
    f = Finto(r or risposte())
    pagine = {}
    if url:
        pagine[url.rstrip("/") + "/sw.js"] = SW

    def leggi_url(indirizzo):
        if indirizzo not in pagine:
            raise OSError("non raggiungibile")
        return pagine[indirizzo]

    codice = giro.main(f, stato_file=tmp_path / "giro.json", url=url, leggi_url=leggi_url, adesso=ADESSO, **kw)
    return codice, f


def test_primo_giro_stampa_tutto_ed_esce_con_10(tmp_path, capsys):
    codice, _ = lancia(tmp_path)
    assert codice == 10
    testo = capsys.readouterr().out
    assert "#21" in testo and "conflitto" in testo.lower()
    assert "guasto d'infrastruttura" in testo and "--esegui" in testo


def test_due_giri_uguali_non_stampano_niente(tmp_path, capsys):
    lancia(tmp_path)
    capsys.readouterr()
    codice, _ = lancia(tmp_path)
    assert codice == 0
    assert capsys.readouterr().out == ""


def test_con_tutto_dice_nessun_cambiamento(tmp_path, capsys):
    lancia(tmp_path)
    capsys.readouterr()
    assert lancia(tmp_path, tutto=True)[0] == 0
    testo = capsys.readouterr().out
    assert "Nessun cambiamento" in testo and "#21" in testo


def test_due_giri_diversi_stampano_solo_il_cambiamento(tmp_path, capsys):
    lancia(tmp_path)
    capsys.readouterr()
    r = risposte()
    r["gh pr list --state open"] = [p for p in r["gh pr list --state open"] if p["number"] != 20]
    r["gh pr list --state open"][0]["statusCheckRollup"] = []
    codice, _ = lancia(tmp_path, r)
    assert codice == 10
    righe = capsys.readouterr().out.splitlines()
    assert any(r.startswith("- ") and "#20" in r for r in righe)          # sparita (unita o chiusa)
    assert not any("#22" in r for r in righe)                            # non è cambiata: non si ripete


def test_di_default_non_rilancia_ne_annulla(tmp_path):
    _, f = lancia(tmp_path)
    assert not f.lanciati("gh run rerun") and not f.lanciati("gh run cancel")
    assert not f.lanciati("git worktree remove")


def test_con_esegui_rilancia_una_volta_sola(tmp_path):
    _, f = lancia(tmp_path, esegui_davvero=True)
    assert f.lanciati("gh run rerun") == ["gh run rerun 50 --failed"]
    _, f = lancia(tmp_path, esegui_davvero=True)
    assert f.lanciati("gh run rerun") == []
    assert not f.lanciati("git worktree remove")                          # pulisci resta sempre prova


def test_annulla_le_superate_solo_con_esegui(tmp_path):
    r = risposte(**{"gh run list --status queued": [
        {"databaseId": 3, "workflowName": "iOS", "status": "queued", "event": "pull_request", "headBranch": "b",
         "headSha": "vecchio", "conclusion": "", "createdAt": "2026-11-06T11:30:00Z"}]})
    _, f = lancia(tmp_path, copy.deepcopy(r))
    assert not f.lanciati("gh run cancel")
    _, f = lancia(tmp_path, copy.deepcopy(r), esegui_davvero=True)
    assert f.lanciati("gh run cancel") == ["gh run cancel 3"]


def test_versione_in_produzione_solo_se_c_e_l_indirizzo(tmp_path, capsys):
    lancia(tmp_path / "a")
    assert "produzione" not in capsys.readouterr().out.lower()
    lancia(tmp_path / "b", url="https://server.example")
    testo = capsys.readouterr().out
    assert "produzione: fanta-230" in testo.lower() and "server.example" not in testo     # l'indirizzo non si stampa


def test_produzione_non_raggiungibile_lo_dice(tmp_path, capsys):
    f = Finto(risposte())
    giro.main(f, stato_file=tmp_path / "g.json", url="https://server.example", adesso=ADESSO,
              leggi_url=lambda u: (_ for _ in ()).throw(OSError("rete giù")))
    assert "non raggiungibile" in capsys.readouterr().out


def test_stato_salvato_fuori_da_git(tmp_path):
    lancia(tmp_path)
    assert json.loads((tmp_path / "giro.json").read_text(encoding="utf-8"))["voci"]


def test_cartella_predefinita_ignorata_da_git(tmp_path, monkeypatch):
    cartella = tmp_path / ".superpowers" / "squadra"
    monkeypatch.setattr(giro, "CARTELLA_STATO", cartella)
    giro.prepara_cartella()
    assert (cartella / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_errore_di_gh_esce_con_1(tmp_path, capsys):
    r = risposte()
    r["gh pr list --state open"] = comune.Risposta(1, "", "non autenticato")
    assert lancia(tmp_path, r)[0] == 1
    assert "non autenticato" in capsys.readouterr().err
