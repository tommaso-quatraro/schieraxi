"""script/squadra: `giornata` (H2) dice se una giornata è passata senza errori. Dati finti, niente `gh` vero, niente orologio vero."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from test_squadra_comune import Finto

import comune
import giornata

DAL = comune.data("2026-11-15T13:50:00+01:00")      # scadenza: 10 minuti prima della prima partita
AL = comune.data("2026-11-17T20:45:00+01:00")       # due giorni dopo l'inizio dell'ultima partita
ADESSO = comune.data("2026-11-18T09:00:00+01:00")


def giri_regolari(dal=DAL, al=AL, ogni=timedelta(minutes=20), rotte=None) -> list[dict]:
    """Un giro ogni 20 minuti per tutta la finestra, senza rotture, con l'ora locale e il fuso come li scrive H1."""
    voci, t = [], dal
    while t <= al:
        voci.append({"quando": t.isoformat(timespec="seconds"), "rotte": [], "inviato": False})
        t += ogni
    return voci


def corsa(n: int, quando: str, esito: str = "success") -> dict:
    return {"databaseId": n, "createdAt": quando, "conclusion": esito, "url": f"https://github.com/x/y/actions/runs/{n}"}


def issue(n: int, titolo: str, creata: str, chiusa: str | None = None, etichette=()) -> dict:
    return {"number": n, "title": titolo, "createdAt": creata, "closedAt": chiusa, "labels": list(etichette),
            "url": f"https://github.com/x/y/issues/{n}"}


MAIN_VERDI = [corsa(1, "2026-11-15T14:00:00Z"), corsa(2, "2026-11-16T10:00:00Z", "skipped")]
COLLAUDI_GH = [corsa(10, "2026-11-15T13:04:00Z"), corsa(11, "2026-11-16T13:04:00Z")]      # come li dà `gh run list`
# dopo la raccolta: la corsa più recente riuscita ha l'esito del job «Collaudo delle schermate» (letto con `gh run view`)
COLLAUDI_VERDI = [COLLAUDI_GH[0], dict(COLLAUDI_GH[1], collaudo="success")]


def lavori(collaudo: str = "success") -> dict:
    """Risposta di `gh run view <id> --json jobs` per una corsa di «Collaudo della prova»."""
    return {"jobs": [{"name": "Serve un collaudo?", "conclusion": "success"},
                     {"name": giornata.JOB_COLLAUDO, "conclusion": collaudo},
                     {"name": "Apre o chiude le issue", "conclusion": "success"}]}


def giudica(issue_=(), main=None, collaudi=None, giri="regolari"):
    return giornata.verdetto(DAL, AL, list(issue_), MAIN_VERDI if main is None else main,
                             COLLAUDI_VERDI if collaudi is None else collaudi,
                             giri_regolari() if giri == "regolari" else giri)


def test_giornata_pulita_e_verde():
    v = giudica()
    assert v.ok is True and v.motivi == []


def test_issue_p1_o_dall_utente_nella_finestra():
    v = giudica([issue(40, "Formazione sbagliata", "2026-11-16T08:00:00Z", etichette=["P1", "web"])])
    assert v.ok is False and any("#40" in m for m in v.motivi)
    v = giudica([issue(41, "Non vedo la squadra", "2026-11-16T08:00:00Z", "2026-11-16T09:00:00Z", ["dall-utente"])])
    assert v.ok is False and any("#41" in m for m in v.motivi)
    assert giudica([issue(42, "Idea", "2026-11-16T08:00:00Z", etichette=["P3"])]).ok is True


def test_issue_prima_della_finestra_non_conta():
    # P1 nata prima della scadenza (e un'altra dopo la fine): non è «nuova» nella finestra
    v = giudica([issue(40, "Vecchio guasto", "2026-11-15T12:00:00Z", etichette=["P1"]),
                 issue(43, "Dopo", "2026-11-17T20:00:00Z", etichette=["dall-utente"])])
    assert v.ok is True, v.motivi


def test_main_rosso_aperto_prima_e_ancora_aperto_rende_rossa():
    v = giudica([issue(50, "CI: main rosso", "2026-11-14T08:00:00Z")])
    assert v.ok is False and any("#50" in m for m in v.motivi)
    # chiusa durante la finestra: rossa lo stesso (lo è stata per un pezzo)
    assert giudica([issue(51, "CI: main rosso", "2026-11-14T08:00:00Z", "2026-11-15T14:00:00Z")]).ok is False
    # chiusa prima della scadenza: non conta
    assert giudica([issue(52, "CI: main rosso", "2026-11-14T08:00:00Z", "2026-11-15T12:00:00Z")]).ok is True


def test_collaudo_rosso_aperto_prima_rende_rossa():
    v = giudica([issue(60, "Collaudo della prova: v1.450 non passa", "2026-11-10T08:00:00Z")])
    assert v.ok is False and any("#60" in m for m in v.motivi)
    v = giudica([issue(61, "La prova non si aggiorna", "2026-11-17T19:00:00Z")])
    assert v.ok is False and any("#61" in m for m in v.motivi)


def test_issue_di_lavoro_col_titolo_simile_non_conta():
    # I titoli rossi sono quelli esatti dei workflow: un'issue di lavoro che comincia allo stesso modo non è un allarme
    # (#549 «Collaudo della prova: almeno una volta al giorno…» era aperta il 9/11).
    simili = [issue(549, "Collaudo della prova: almeno una volta al giorno anche senza versione nuova", "2026-11-14T08:00:00Z"),
              issue(70, "CI: main rosso, idea per avvisare prima", "2026-11-14T08:00:00Z"),
              issue(71, "La prova non si aggiorna da sola: script nuovo", "2026-11-14T08:00:00Z"),
              issue(72, "Collaudo della prova: v1.450 non passa (vecchia)", "2026-11-14T08:00:00Z")]
    v = giudica(simili)
    assert v.ok is True, v.motivi
    assert giornata.titolo_rosso("Collaudo della prova: v1.450.2 non passa")
    assert not giornata.titolo_rosso("Collaudo della prova: vecchio non passa")


def test_corsa_annullata_non_conta():
    assert giudica(main=MAIN_VERDI + [corsa(3, "2026-11-16T11:00:00Z", "cancelled")]).ok is True


def test_corsa_di_main_fallita_o_startup_failure():
    for esito in ("failure", "startup_failure", "timed_out", "", None):
        v = giudica(main=MAIN_VERDI + [corsa(4, "2026-11-16T11:00:00Z", esito)])
        assert v.ok is False and any("runs/4" in m for m in v.motivi), esito


def test_collaudo_fallito():
    v = giudica(collaudi=COLLAUDI_VERDI + [corsa(12, "2026-11-17T13:04:00Z", "failure")])
    assert v.ok is False and any("runs/12" in m for m in v.motivi)


def test_nessun_collaudo_nella_finestra():
    v = giudica(collaudi=[corsa(9, "2026-11-14T13:04:00Z")])      # solo prima della finestra
    assert v.ok is False and any("non è stata collaudata" in m for m in v.motivi)


def test_giro_con_rotture_nella_finestra():
    giri = giri_regolari()
    giri[30]["rotte"] = ["punti_diversi"]
    v = giudica(giri=giri)
    assert v.ok is False and any("punti_diversi" in m for m in v.motivi)


def test_giri_fuori_dalla_finestra_non_contano():
    # il file di stato intero porta anche i giri di altri giorni: una rottura del giorno prima non sporca questa giornata
    giri = [{"quando": "2026-11-14T20:00:00+01:00", "rotte": ["punti_diversi"], "inviato": True}] + giri_regolari()
    assert giudica(giri=giri).ok is True


def test_sentinella_ferma_piu_di_due_ore():
    giri = [g for g in giri_regolari() if not "2026-11-16T03:00:00+01:00" <= g["quando"] <= "2026-11-16T05:20:00+01:00"]
    v = giudica(giri=giri)
    assert v.ok is False and any("non ha girato" in m for m in v.motivi)
    # buco all'inizio (fra la scadenza e il primo giro) e alla fine (fra l'ultimo giro e la fine)
    assert giudica(giri=giri_regolari(dal=DAL + timedelta(hours=3))).ok is False
    assert giudica(giri=giri_regolari(al=AL - timedelta(hours=3))).ok is False
    assert giudica(giri=[]).ok is False
    # 2 ore esatte di buco vanno ancora bene
    assert giudica(giri=giri_regolari(ogni=timedelta(hours=2))).ok is True


def test_senza_sentinella_non_e_verde():
    v = giudica(giri=None)
    assert v.ok is False and any("manca la storia della sentinella" in m for m in v.motivi)


def test_confronto_fra_ora_locale_e_utc():
    al = comune.data("2026-11-17T19:45:00Z")
    giri = giri_regolari(al=al)
    giri.append({"quando": "2026-11-17T20:30:00+01:00", "rotte": ["consiglio_vuoto"], "inviato": True})   # = 19:30Z
    v = giornata.verdetto(DAL, al, [], MAIN_VERDI, COLLAUDI_VERDI, giri)
    assert v.ok is False and any("consiglio_vuoto" in m for m in v.motivi)


# --- raccolta con gh (finto) e riga di comando ---

def risposte(main=MAIN_VERDI, collaudi=COLLAUDI_GH, issue_=(), job="success") -> dict:
    gh_issue = [dict(i, labels=[{"name": e} for e in i["labels"]]) for i in issue_]
    return {"gh run list --workflow test.yml": main, "gh run list --workflow collaudo-prova.yml": collaudi,
            "gh issue list": gh_issue, "gh run view": lavori(job)}


def test_raccolta_usa_limit_e_created():
    finto = Finto(risposte())
    dati = giornata.raccogli(finto, DAL, AL)
    assert dati["corse_main"] == MAIN_VERDI and dati["corse_collaudo"] == COLLAUDI_VERDI
    corse = finto.lanciati("gh run list")
    assert len(corse) == 2
    for c in corse:
        assert "--limit 1000" in c and "--branch main" in c
        assert "--created 2026-11-15T12:50:00Z..2026-11-17T19:45:00Z" in c
    ricerche = finto.lanciati("gh issue list")
    assert len(ricerche) == 4                        # le issue nuove e una ricerca per ciascuno dei tre titoli
    for r in ricerche:
        assert "--limit 1000" in r and "--state all" in r
    assert any("created:2026-11-15T12:50:00Z..2026-11-17T19:45:00Z" in r for r in ricerche)
    for titolo in giornata.TITOLI_ROSSI:
        assert any(f'"{titolo}" in:title created:<=2026-11-17T19:45:00Z' in r for r in ricerche)


def test_raccolta_tagliata_si_ferma():
    tante = [corsa(i, "2026-11-16T10:00:00Z") for i in range(1000)]
    with pytest.raises(comune.ErroreComando, match="1000"):
        giornata.raccogli(Finto(risposte(main=tante)), DAL, AL)


def test_raccolta_toglie_doppioni_e_legge_le_etichette():
    i = issue(50, "CI: main rosso", "2026-11-16T08:00:00Z", etichette=["P1", "ci"])
    dati = giornata.raccogli(Finto(risposte(issue_=[i])), DAL, AL)
    assert dati["issue"] == [i]                     # trovata da due ricerche, contata una volta, etichette come nomi


def cli(finto, argomenti: list[str]) -> int:
    """La riga di comando vera (argparse di squadra.py), con l'orologio fermo a ADESSO."""
    import squadra
    args = squadra.parser().parse_args(["giornata", *argomenti])
    return giornata.da_riga(args, finto, adesso=ADESSO)


@pytest.fixture
def con_sentinella(tmp_path) -> list[str]:
    file = tmp_path / "giri.json"
    file.write_text(json.dumps(giri_regolari()), encoding="utf-8")
    return ["--dal", DAL.isoformat(), "--al", AL.isoformat(), "--sentinella", str(file)]


def test_collaudo_spento_non_vale(con_sentinella, capsys):
    # segreti mancanti o versione già collaudata: la corsa è «success», ma il job del collaudo è saltato
    finto = Finto(risposte(job="skipped"))
    assert cli(finto, con_sentinella) == 1
    assert "la prova non è stata collaudata davvero nella finestra (collaudo saltato o spento)" in capsys.readouterr().out
    assert len(finto.lanciati("gh run view")) == 2                  # lette tutte e due le corse riuscite, nessuna basta


def test_solo_corse_annullate_non_vale(con_sentinella, capsys):
    annullate = [corsa(10, "2026-11-15T13:04:00Z", "cancelled"), corsa(11, "2026-11-16T13:04:00Z", "cancelled")]
    finto = Finto(risposte(collaudi=annullate))
    assert cli(finto, con_sentinella) == 1
    assert "collaudo saltato o spento" in capsys.readouterr().out
    assert finto.lanciati("gh run view") == []                       # si leggono i job solo delle corse riuscite


def test_basta_un_collaudo_vero(con_sentinella, capsys):
    corse = COLLAUDI_GH + [corsa(12, "2026-11-17T13:04:00Z")]
    finto = Finto(dict(risposte(collaudi=corse), **{"gh run view 12": lavori("skipped"), "gh run view 11": lavori("success")}))
    assert cli(finto, con_sentinella) == 0, capsys.readouterr().out
    # dalla più recente, ci si ferma alla prima con il collaudo riuscito: la 10 non si legge
    assert finto.lanciati("gh run view") == ["gh run view 12 --json jobs", "gh run view 11 --json jobs"]


def test_nome_del_job_e_quello_del_workflow():
    from test_squadra_comune import RADICE
    flusso = (RADICE / ".github" / "workflows" / "collaudo-prova.yml").read_text(encoding="utf-8")
    assert f"    name: {giornata.JOB_COLLAUDO}\n" in flusso


def test_risposta_vuota_di_gh_esce_3(capsys):
    finto = Finto(dict(risposte(), **{"gh issue list": ""}))
    assert cli(finto, ["--dal", DAL.isoformat(), "--al", AL.isoformat()]) == 3
    assert "vuota" in capsys.readouterr().err


def test_comando_verde_esce_0_e_rosso_esce_1(tmp_path, capsys):
    file = tmp_path / "giri.json"
    file.write_text(json.dumps(giri_regolari()), encoding="utf-8")
    argomenti = ["--dal", DAL.isoformat(), "--al", AL.isoformat(), "--sentinella", str(file)]
    assert cli(Finto(risposte()), argomenti) == 0
    assert "senza errori" in capsys.readouterr().out
    assert cli(Finto(risposte()), argomenti[:4]) == 1          # senza --sentinella
    assert "manca la storia della sentinella" in capsys.readouterr().out


def test_file_della_sentinella_intero_o_rovinato(tmp_path, capsys):
    file = tmp_path / "sentinella.json"
    file.write_text(json.dumps({"rotte": {}, "giri": giri_regolari()}), encoding="utf-8")   # il file di stato intero
    argomenti = ["--dal", DAL.isoformat(), "--al", AL.isoformat(), "--sentinella", str(file)]
    assert cli(Finto(risposte()), argomenti) == 0
    file.write_text("{non json", encoding="utf-8")
    assert cli(Finto(risposte()), argomenti) == 3
    assert "sentinella" in capsys.readouterr().err


def test_al_nel_futuro_rifiutato(capsys):
    finto = Finto({})
    argomenti = ["--dal", DAL.isoformat(), "--al", (ADESSO + timedelta(minutes=1)).isoformat()]
    assert cli(finto, argomenti) == 2
    assert "futuro" in capsys.readouterr().err and finto.chiamate == []


def test_date_senza_fuso_rifiutate(capsys):
    finto = Finto({})
    assert cli(finto, ["--dal", "2026-11-15T13:50:00", "--al", AL.isoformat()]) == 2
    assert cli(finto, ["--dal", DAL.isoformat(), "--al", "domani"]) == 2
    assert cli(finto, ["--dal", AL.isoformat(), "--al", DAL.isoformat()]) == 2   # rovesciate
    assert "fuso" in capsys.readouterr().err and finto.chiamate == []


def test_errore_di_gh_esce_3(capsys):
    finto = Finto({"gh": comune.Risposta(1, "", "HTTP 502")})
    assert cli(finto, ["--dal", DAL.isoformat(), "--al", AL.isoformat()]) == 3
    assert "HTTP 502" in capsys.readouterr().err
