"""«Quanto ci abbiamo preso» (fanta/precisione.py): numeri per l'utente dal suo diario e riassunto anonimo per il sito. Dati finti."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import archivio, consigli, diario, precisione, server
from fanta.regole import Regole

ST = "2026-27"


def _voce(g, giocatori, atteso=70.0, reale=72.0, tua=None, istantanea=None, basso=62.0, alto=78.0):
    v = {"stagione": ST, "giornata": g, "giornata_lega": g - 3,
         "consigliata": {"atteso": atteso, "reale": reale, "intervallo": {"basso": basso, "alto": alto}, "titolari": []},
         "schierata": None if tua is None else {"atteso": atteso, "reale": tua, "titolari": [], "tipo": "manuale"},
         "giocatori": giocatori, "istantanea": istantanea}
    return v


def _g(i, p, atteso, fv):
    return {"id": i, "p_voto": p, "fv_atteso": atteso, "fv": fv}


def test_fantavoto_e_gioca_dai_numeri_ricostruiti():
    gioc = [_g(1, 0.95, 6.0, 7.0), _g(2, 0.95, 6.0, 5.5), _g(3, 0.95, 6.0, None), _g(4, 0.8, 6.0, 6.0), _g(5, 0.1, 5.0, None)]
    r = precisione.riassunto([_voce(4, gioc), _voce(5, gioc)])
    assert r["giornate"] == 2 and r["pochi_dati"] is True and r["giornate_minime"] == diario.POCHI_DATI
    assert r["fonti"] == {"mostrati": 0, "ricostruiti": 2}
    fv = r["fantavoto"]                        # scarti 1, 0,5, 0 ripetuti: media 0,5; tutti entro un punto
    assert fv == {"errore_medio": 0.5, "scostamento": 0.2, "entro_un_punto": 100, "voti": 6}
    gruppi = {g["da"]: g for g in r["gioca"]["gruppi"]}
    assert gruppi[90]["giocatori"] == 6 and gruppi[90]["detto"] == 95 and gruppi[90]["giocato"] == 67 and gruppi[90]["pochi"] is True
    assert gruppi[70]["giocato"] == 100 and gruppi[0]["giocato"] == 0 and 40 not in gruppi          # fasce vuote: non ci sono
    assert r["gioca"]["gruppi"][r["gioca"]["principale"]]["da"] == 90                                # la fascia alta con più casi
    assert r["gioca"]["fonte"] == "ricostruiti" and r["gioca"]["giornate"] == 2
    assert [x["giornata"] for x in r["per_giornata"]] == [4, 5]                                       # dalla più vecchia
    assert r["per_giornata"][0]["errore_fantavoto"] == 0.5 and r["per_giornata"][0]["giornata_lega"] == 1


def test_i_numeri_mostrati_allora_vincono_su_quelli_ricostruiti():
    gioc = [_g(1, 0.5, 6.0, 8.0), _g(2, 0.5, 6.0, None)]
    ist = {"titolari": [{"id": 1, "nome": "A", "ruolo": "A", "p_voto": 0.9, "fv_atteso": 7.0}], "panchina": [{"id": 9, "p_voto": 0.9, "fv_atteso": 6}]}
    r = precisione.riassunto([_voce(4, gioc, istantanea=ist)])
    assert r["fonti"] == {"mostrati": 1, "ricostruiti": 0} and r["per_giornata"][0]["fonte"] == "mostrati"
    assert r["fantavoto"]["errore_medio"] == 1.0                                        # il 9 non ha un fantavoto vero: fuori
    # «gioca N%»: con meno di 3 giornate mostrate si usano i ricostruiti (senza probabili) e la fonte lo dice
    assert r["gioca"]["fonte"] == "ricostruiti" and r["gioca"]["giocatori"] == 2 and r["gioca"]["gruppi"][0]["detto"] == 50
    tre = precisione.riassunto([_voce(g, gioc, istantanea=ist) for g in (4, 5, 6)] + [_voce(7, gioc)])
    assert tre["gioca"]["fonte"] == "mostrati" and tre["gioca"]["giornate"] == 3 and tre["gioca"]["giocatori"] == 3
    assert [g["detto"] for g in tre["gioca"]["gruppi"]] == [90]                          # solo quello che l'app ha detto davvero
    # istantanea vecchia senza numeri: si torna ai ricostruiti
    vecchia = {"titolari": [{"id": 1, "nome": "A", "ruolo": "A"}], "panchina": []}
    assert precisione.riassunto([_voce(4, gioc, istantanea=vecchia)])["fonti"] == {"mostrati": 0, "ricostruiti": 1}


def test_consigliata_contro_la_tua_e_squadra():
    voci = [_voce(4, [], reale=70, tua=65), _voce(5, [], reale=60, tua=66.5), _voce(6, [], reale=70, tua=70), _voce(7, [], reale=80)]
    r = precisione.riassunto(voci)
    assert r["confronto"] == {"giornate": 3, "meglio_consigliata": 1, "meglio_tua": 1, "pari": 1, "punti": -1.5,
                              "media_consigliata": 66.7, "media_tua": 67.2}
    assert [x["differenza"] for x in r["per_giornata"]] == [5.0, -6.5, 0.0, None]
    assert r["squadra"]["giornate"] == 4 and r["squadra"]["con_fascia"] == 4 and r["squadra"]["dentro_fascia"] == 2      # 60 e 80 fuori da 62-78
    assert r["fantavoto"] is None and r["gioca"] is None and r["fonti"] == {"mostrati": 0, "ricostruiti": 0}


def test_brutti_numeri_si_vedono_lo_stesso():
    """Onestà: se diciamo 95% e giocano in 6 su 10, il numero esce così com'è, nella fascia in evidenza."""
    gioc = [_g(i, 0.95, 6.0, 6.0 if i <= 6 else None) for i in range(1, 11)]
    r = precisione.riassunto([_voce(g, gioc, reale=50.0) for g in range(1, 11)])
    p = r["gioca"]["gruppi"][r["gioca"]["principale"]]
    assert (p["detto"], p["giocato"]) == (95, 60) and r["pochi_dati"] is False
    assert r["squadra"]["dentro_fascia"] == 0 and r["squadra"]["punti_medi_fatti"] == 50.0


def test_vuoto_e_voci_rovinate():
    assert precisione.riassunto([])["giornate"] == 0
    r = precisione.riassunto([{"giornata": 1}, "x", _voce(4, [{"id": 1}, "x", {"id": 2, "p_voto": "a", "fv_atteso": 6, "fv": 6}])])
    assert r["giornate"] == 1 and r["fantavoto"] is None


def test_aggregato_utenti_solo_con_abbastanza_utenti():
    un_diario = [_voce(4, [], reale=70, tua=65), _voce(5, [], reale=60, tua=62)]
    assert precisione.aggregato_utenti([un_diario] * 4) is None
    assert precisione.aggregato_utenti([un_diario] * 4 + [[_voce(4, [])]]) is None          # senza schierata non conta
    a = precisione.aggregato_utenti([un_diario] * 5)
    assert a == {"utenti_almeno": 5, "meglio_consigliata": 50, "meglio_tua": 50, "pari": 0, "punti_per_giornata": 1.5}
    assert precisione.aggregato_utenti([un_diario] * 37)["utenti_almeno"] == 25                     # a scaglioni, mai il numero esatto


@pytest.fixture
def finto(monkeypatch, tmp_path):
    """Due giornate finite con giocatori finti (nomi riconoscibili, per controllare che non escano nel riassunto pubblico)."""
    partite = pd.DataFrame([{"id": g, "stagione": ST, "giornata": g, "giocata": 1} for g in (1, 2)])
    voti = pd.DataFrame([{"stagione": ST, "giornata": g, "calciatore_id": i, "voto_red": 7.0} for g in (1, 2) for i in range(1, 21)])
    dati = SimpleNamespace(partite=partite, voti=voti)

    def previsioni(d, stagione, giornata, regole, par):
        return pd.DataFrame([{"id": i, "nome": f"NomeSegreto{i}", "ruolo": "C", "p_voto": 0.9 if i <= 20 else 0.2, "mu": 6.5,
                              "mu_voto": 6.0, "partita": giornata} for i in range(1, 31)])
    monkeypatch.setattr(diario, "previsioni", previsioni)
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db: dati)
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in (1, 2):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2026-09-01 18:00', 'a', 'b', 1)", (g, ST, g))
    return db


def test_riassunto_pubblico_senza_dati_personali(finto):
    diari = [[_voce(4, [], reale=70, tua=65)]] * 5
    r = precisione.pubblico(finto, diari)
    assert r["giornate"] == 2 and r["stagione"] == ST and r["pochi_dati"] is True
    assert r["fantavoto"] == {"errore_medio": 0.5, "scostamento": 0.5, "entro_un_punto": 100, "voti": 40}
    assert {g["da"]: g["giocato"] for g in r["gioca"]["gruppi"]} == {0: 0, 90: 100}
    assert r["formazioni"]["utenti_almeno"] == 5 and r["gioca"]["fonte"] == "ricostruiti"
    testo = json.dumps(r)
    assert "NomeSegreto" not in testo and '"id"' not in testo and "Mia" not in testo
    assert precisione.pubblico(finto, [])["formazioni"] is None


def test_comando_pubblico_scrive_il_file(finto, monkeypatch, tmp_path):
    from fanta.__main__ import main
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: finto)
    monkeypatch.setattr(diario, "FILE", tmp_path / "diario.json")
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    dove = tmp_path / "pubblico.json"
    main(["affidabilita", "--pubblico", "--file", str(dove)])
    r = json.loads(dove.read_text(encoding="utf-8"))
    assert r["giornate"] == 2 and r["formazioni"] is None and r["fantavoto"]["voti"] == 40


def test_la_rotta_del_diario_ha_la_precisione():
    rotta = next(r for r in server.app.routes if getattr(r, "path", "") == "/api/diario")
    import inspect
    assert "precisione.riassunto" in inspect.getsource(rotta.endpoint)


APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")


def _funzione(nome: str) -> str:
    inizio = APP.index(f"function {nome}(")
    return APP[inizio:APP.index("\n}\n", inizio) + 3]


def test_web_usa_il_campo_del_server_senza_innerhtml():
    assert "cartaPrecisione(d.precisione)" in APP
    corpo = _funzione("cartaPrecisione")
    assert "innerHTML" not in corpo and ".nome" not in corpo        # solo numeri dal server, niente testo libero


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node non installato")
@pytest.mark.parametrize("lingua", ["it", "en"])
def test_web_disegna_la_carta_senza_buchi(lingua):
    """La carta con numeri veri (anche brutti), con pochi dati e vuota: niente «undefined», «NaN» o chiavi non tradotte."""
    import subprocess
    gioc = [_g(i, 0.95, 6.0, 6.0 if i <= 6 else None) for i in range(1, 11)]
    pieno = precisione.riassunto([_voce(g, gioc, reale=60.0 + g, tua=55.0) for g in range(4, 14)])
    poco = precisione.riassunto([_voce(4, [], reale=70.0)])
    al_percento = next(r for r in APP.splitlines() if r.startswith("const alPercento = "))
    prova = (TESTI + "\nconst virgola = x => (LINGUA === 'it' ? String(x).replace('.', ',') : String(x));\n" + al_percento + "\n"
             + _funzione("cartaPrecisione") + f"""
    LINGUA = "{lingua}";
    console.log(JSON.stringify([cartaPrecisione({json.dumps(pieno)}), cartaPrecisione({json.dumps(poco)}), cartaPrecisione({{"giornate": 0}})]));
    """)
    r = subprocess.run(["node", "-"], input=prova, capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    pieno_html, poco_html, vuoto = json.loads(r.stdout)
    for html in (pieno_html, poco_html):
        assert "undefined" not in html and "NaN" not in html and "diario.qp" not in html and "null" not in html
    assert vuoto == ""
    assert "<svg" in pieno_html and ("10 su 10" in pieno_html or "10 of 10" in pieno_html)            # la consigliata ha sempre fatto meglio
    assert ("6 su 10" in pieno_html) if lingua == "it" else ("6 of 10" in pieno_html)                # diciamo 95%, giocano 6 su 10: si vede
    assert "qp-pochi" in poco_html and "qp-pochi" not in pieno_html
    assert ("senza le probabili" in pieno_html) if lingua == "it" else ("without the predicted" in pieno_html)   # numeri ricostruiti: lo dice


def test_cron_per_utente_errori_con_id_e_tempo_finito(monkeypatch, tmp_path, capsys):
    """Un utente rotto non ferma gli altri e nel registro c'è solo il suo numero e il tipo di errore; finito il tempo, gli altri
    restano al giro dopo (prima chi ha il diario più vecchio)."""
    import time
    from fanta import __main__ as comandi, account, contesto
    cartelle = {i: tmp_path / str(i) for i in (1, 2, 3)}
    for _i, c in cartelle.items():
        c.mkdir()
        (c / "rose.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(account, "apri", lambda *a, **k: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(account, "elenco", lambda db: [{"id": i, "nome_utente": f"segreto{i}"} for i in cartelle])
    monkeypatch.setattr(contesto, "cartella_utente", lambda i: cartelle[int(i)])
    monkeypatch.setattr(comandi.lega, "carica", lambda p: None)
    fatti = []

    def aggiorna(db, regole, rose, percorso, file_scelte=None, scadenza=None):
        fatti.append(percorso.parent.name)
        if percorso.parent.name == "2":
            raise ValueError("file rovinato di segreto2")
        return 1
    monkeypatch.setattr(diario, "aggiorna", aggiorna)
    voci, n, saltati, errori = comandi._diario_per_utente(None, scadenza=time.monotonic() + 60)
    assert (voci, n, saltati, errori) == (2, 2, 0, [(2, "ValueError")]) and sorted(fatti) == ["1", "2", "3"]
    fatti.clear()
    assert comandi._diario_per_utente(None, scadenza=time.monotonic() - 1) == (0, 0, 3, []) and fatti == []


def test_regole_classiche_nel_pubblico(finto, monkeypatch):
    viste = []
    vera = diario._previsti_e_veri
    monkeypatch.setattr(diario, "_previsti_e_veri", lambda d, st, g, regole, par: (viste.append(regole), vera(d, st, g, regole, par))[1])
    precisione.pubblico(finto)
    assert viste and all(r == Regole() for r in viste)
