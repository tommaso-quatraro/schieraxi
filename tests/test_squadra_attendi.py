"""script/squadra: `attendi <PR>` guarda solo l'ultima corsa del commit in testa e esce con un codice che dice cosa fare."""
from __future__ import annotations

import json

from test_squadra_comune import Finto, Sequenza

import attendi
import comune


def pr(stato="OPEN", mergeable="MERGEABLE", bozza=False, testa="t1", dirty=False):
    return {"state": stato, "mergeable": mergeable, "mergeStateStatus": "DIRTY" if dirty else "CLEAN",
            "headRefOid": testa, "isDraft": bozza}


def corsa(id_, wf="Controlli", stato="completed", esito="success", quando="2026-11-06T10:00:00Z", evento="pull_request"):
    return {"databaseId": id_, "workflowName": wf, "status": stato, "conclusion": esito, "event": evento, "createdAt": quando}


class Orologio:
    def __init__(self):
        self.t = 0.0
        self.pause = []

    def __call__(self):
        return self.t

    def dorme(self, s):
        self.pause.append(s)
        self.t += s


def lancia(risposte, **kw):
    o = Orologio()
    finto = Finto(risposte)
    codice = attendi.main(finto, 5, intervallo=kw.pop("intervallo", 60), massimo=kw.pop("massimo", 600),
                          dorme=o.dorme, orologio=o, **kw)
    return codice, finto, o


def test_unita_esce_con_0():
    codice, _, o = lancia({"gh pr view 5": pr(stato="MERGED")})
    assert codice == 0 and o.pause == []


def test_conflitto_esce_con_2():
    assert lancia({"gh pr view 5": pr(mergeable="CONFLICTING")})[0] == 2
    assert lancia({"gh pr view 5": pr(dirty=True)})[0] == 2


def test_rosso_vero_esce_con_3():
    risposte = {
        "gh pr view 5": pr(),
        "gh run list --commit t1": [corsa(1, esito="failure")],
        "gh run view 1": {"jobs": [{"name": "test", "conclusion": "failure",
                                    "steps": [{"name": "pytest", "conclusion": "failure"}]}]},
    }
    assert lancia(risposte)[0] == 3


def test_guasto_infrastruttura_esce_con_4():
    senza_passi = {"gh pr view 5": pr(), "gh run list --commit t1": [corsa(1, esito="failure")],
                   "gh run view 1": {"jobs": [{"name": "ios", "conclusion": "failure", "steps": []}]}}
    assert lancia(senza_passi)[0] == 4
    avvio = {"gh pr view 5": pr(), "gh run list --commit t1": [corsa(1, esito="startup_failure")]}
    assert lancia(avvio)[0] == 4
    annullata = {"gh pr view 5": pr(), "gh run list --commit t1": [corsa(1, esito="cancelled")]}
    assert lancia(annullata)[0] == 4


def test_tempo_scaduto_esce_con_5():
    risposte = {"gh pr view 5": pr(), "gh run list --commit t1": [corsa(1, stato="in_progress", esito="")]}
    codice, _, o = lancia(risposte, intervallo=60, massimo=180)
    assert codice == 5 and o.pause == [60, 60, 60]


def test_verde_in_bozza_esce_con_6():
    assert lancia({"gh pr view 5": pr(bozza=True), "gh run list --commit t1": [corsa(1)]})[0] == 6


def test_guarda_solo_l_ultima_corsa_di_ogni_workflow():
    # la corsa vecchia rossa è stata rilanciata ed è verde: non conta
    risposte = {"gh pr view 5": Sequenza(pr(), pr(stato="MERGED")),
                "gh run list --commit t1": [corsa(1, esito="failure", quando="2026-11-06T10:00:00Z"),
                                            corsa(2, esito="success", quando="2026-11-06T10:30:00Z")]}
    codice, finto, _ = lancia(risposte)
    assert codice == 0 and not finto.lanciati("gh run view")


def test_stampa_solo_quando_cambia_qualcosa(capsys):
    in_corso = [corsa(1, stato="in_progress", esito="")]
    risposte = {"gh pr view 5": Sequenza(pr(), pr(), pr(), pr(), pr(stato="MERGED")),
                "gh run list --commit t1": Sequenza(in_corso, in_corso, in_corso, [corsa(1)])}
    assert lancia(risposte)[0] == 0
    righe = [r for r in capsys.readouterr().out.splitlines() if r.strip()]
    assert len(righe) == 3, righe       # in corso, verde in attesa dell'unione, unita


def test_testa_nuova_cambia_il_commit_guardato():
    risposte = {"gh pr view 5": Sequenza(pr(testa="t1"), pr(testa="t2"), pr(stato="MERGED")),
                "gh run list --commit t1": [corsa(1, stato="in_progress", esito="")],
                "gh run list --commit t2": [corsa(2, stato="in_progress", esito="")]}
    codice, finto, _ = lancia(risposte)
    assert codice == 0 and finto.lanciati("gh run list --commit t2")


def test_chiusa_senza_unione_esce_con_1():
    assert lancia({"gh pr view 5": pr(stato="CLOSED")})[0] == 1


def test_errore_di_gh_esce_con_1():
    assert lancia({"gh pr view 5": comune.Risposta(1, "", "HTTP 502")})[0] == 1


def test_json(capsys):
    lancia({"gh pr view 5": pr(stato="MERGED")}, json_=True)
    dati = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert dati["codice"] == 0 and dati["pr"] == 5
