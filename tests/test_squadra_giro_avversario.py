from test_squadra_giro import lancia, risposte


def test_rilancio_una_volta_anche_se_nel_mezzo_la_corsa_e_in_corso(tmp_path):
    _, f = lancia(tmp_path, esegui_davvero=True)                       # giro 1: guasto -> rilancio
    assert f.lanciati("gh run rerun") == ["gh run rerun 50 --failed"]
    r = risposte(**{"gh run list --commit testa-b": [{"databaseId": 50, "workflowName": "Controlli", "status": "in_progress",
                    "conclusion": "", "event": "pull_request", "createdAt": "2026-11-06T10:00:00Z"}]})
    lancia(tmp_path, r, esegui_davvero=True)                           # giro 2: il rilancio sta girando
    _, f = lancia(tmp_path, esegui_davvero=True)                       # giro 3: di nuovo guasto
    assert f.lanciati("gh run rerun") == []                            # atteso: non rilancia una seconda volta


def test_non_rilancia_una_corsa_gia_al_secondo_tentativo(tmp_path, capsys):
    r = risposte(**{"gh run view 50 --json attempt": {"attempt": 2}})
    _, f = lancia(tmp_path, r, esegui_davvero=True)
    assert f.lanciati("gh run rerun") == []
    assert "tentativo 2" in capsys.readouterr().out
