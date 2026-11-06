"""Stato dei dati: calibrazione delle probabili e riepilogo."""
import sqlite3

from fanta import archivio, stato_dati

ST = "2026-27"


def test_calibrazione_confronta_probabili_e_chi_ha_giocato(tmp_path):
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (1, ?, 1, '2026-09-01 18:00', 'a', 'b', 1)", (ST,))
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (2, ?, 2, '2026-09-08 18:00', 'a', 'b', 0)", (ST,))
    giocatori = [(1, "titolare", 95, 1), (2, "titolare", 95, 1), (3, "titolare", 95, 0), (4, "panchina", 30, 0), (5, "panchina", 30, 1)]
    for i, stato, perc, ha_giocato in giocatori:
        db.execute("INSERT INTO probabili (stagione, giornata, fonte, calciatore_id, squadra, partita_id, stato, percentuale, in_dubbio, diffidato) "
                   "VALUES (?, 1, 'fantacalcio', ?, 'a', 1, ?, ?, 0, 0)", (ST, i, stato, perc))
        if ha_giocato:
            db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red) VALUES (?, 1, ?, 'x', 'a', 'C', 6.0)", (ST, i))
    db.execute("INSERT INTO probabili (stagione, giornata, fonte, calciatore_id, squadra, partita_id, stato, percentuale, in_dubbio, diffidato) "
               "VALUES (?, 2, 'fantacalcio', 9, 'a', 2, 'titolare', 95, 0, 0)", (ST,))      # giornata non ancora giocata: non conta
    c = stato_dati.calibrazione(db, ST)
    assert c["giornate"] == 1
    tit = next(g for g in c["gruppi"] if g["gruppo"] == "Titolare 90-100%")
    assert tit["n"] == 3 and tit["osservato"] == round(2 / 3, 3) and tit["indicativo"]
    pan = next(g for g in c["gruppi"] if g["gruppo"] == "Panchina 20-49%")
    assert pan["n"] == 2 and pan["osservato"] == 0.5
    vuoto = next(g for g in c["gruppi"] if g["gruppo"] == "Titolare sotto 50%")
    assert vuoto["n"] == 0 and vuoto["osservato"] is None
    r = stato_dati.riepilogo(db, ST)
    assert r["partite"] == {"totali": 2, "giocate": 1} and r["probabili"][0]["giornata"] == 1 and r["calibrazione"]["giornate"] == 1


def test_stato_dati_ha_il_registro_delle_giornate(tmp_path):
    from datetime import datetime
    from fanta import registro_giornate
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in (9, 10):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 600, 1)",
                   (ST, g, f"2026-11-0{g - 8}T18:20:00"))
    misura = {"voti": 2, "sq_modello": 2.0, "sq_fantamedia": 2.25, "presenze": 4, "brier_somma": 0.4,
              "fasce": [[2, 0.3, 0]] + [[0, 0.0, 0]] * 8 + [[2, 1.9, 2]], "fascia_casi": 20, "fascia_dentro": 16}
    registro_giornate.registra_misura(db, ST, 9, misura, datetime(2026, 11, 3, 12))
    r = stato_dati.riepilogo(db, ST)["registro"]
    assert r["finestra"] == 8 and r["soglie"]["I1"] == -0.03 and r["soglie"]["I3_minimo"] == 0.72
    assert r["giornate"] == 1 and not r["verdetto"] and r["regge"] == {"I1": None, "I2": None, "I3": None}
    assert r["errore_modello"] == 1.0 and r["errore_fantamedia"] == 1.061 and r["copertura"] == 0.8 and r["brier"] == 0.1
    assert [(g["giornata"], g["misurato"] is not None) for g in r["per_giornata"]] == [(10, False), (9, True)]
    nona = r["per_giornata"][1]
    assert nona["errore_modello"] == 1.0 and nona["giocatori"] == 600 and nona["con_probabili"] is True and nona["fuori"] == []
    assert r["per_giornata"][0]["errore_modello"] is None                     # salvata, giornata non ancora finita


def test_stato_dati_ha_il_registro_dei_numeri_nostri(tmp_path):
    from fanta import nostri
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, misurato, voti, sq_nostri, sq_mostrati, rose, punti_nostri, "
               "punti_mostrati, fasce, fasce_mostrati, avvisato) VALUES (?, 9, ?, '2026-11-03T12:00:00', 200, 121.0, 100.0, 20, "
               "1300.0, 1302.0, ?, ?, 0)", (ST, nostri.VERSIONE, "[[100, 5.0, 6]]", "[[100, 5.0, 5]]"))
    r = stato_dati.riepilogo(db, ST)["registro_nostri"]
    assert r["versione"] == nostri.VERSIONE and r["finestra"] == 8 and r["soglie"]["errore"] == 0.01
    assert r["giornate"] == 1 and not r["verdetto"] and r["errore_pct"] == 0.1 and r["punti"] == -0.1
    assert r["scarto_gol"] == 0.01 and r["regge"] == {"errore": None, "punti": None, "gol": None}
    assert [g["giornata"] for g in r["per_giornata"]] == [9]


def test_stato_dati_resta_in_piedi_se_il_registro_dei_nostri_va_in_errore(tmp_path, monkeypatch, caplog):
    from fanta import registro_nostri

    def rotto(db):
        raise sqlite3.OperationalError("dettaglio interno")

    monkeypatch.setattr(registro_nostri, "riepilogo", rotto)
    db = archivio.apri(tmp_path / "t.sqlite")
    with caplog.at_level("WARNING"):
        r = stato_dati.riepilogo(db, ST)
    assert r["registro_nostri"] is None and r["registro"]["giornate"] == 0      # il resto della pagina c'è
    assert "OperationalError" in caplog.text and "dettaglio interno" not in caplog.text


def test_stato_dati_ha_la_taratura_di_gioca(tmp_path):
    """Campo `calibrazione.taratura`: lo stato della taratura di «gioca N%» con le probabili (`taratura_probabili.riepilogo`)."""
    db = archivio.apri(tmp_path / "t.sqlite")
    c = stato_dati.riepilogo(db, ST)["calibrazione"]
    assert c["taratura"] == {"stato": "in_attesa", "giornate": 0, "minimo": 4, "versione": None, "dal": None, "prova": None,
                             "motivo": None}
    assert c["giornate"] == 0 and len(c["gruppi"]) == 7 and c["fattori"] == {}                # il resto come prima


def test_stato_dati_resta_in_piedi_se_la_taratura_va_in_errore(tmp_path, monkeypatch, caplog):
    from fanta import taratura_probabili

    def rotto(db):
        raise sqlite3.OperationalError("dettaglio interno")

    monkeypatch.setattr(taratura_probabili, "riepilogo", rotto)
    db = archivio.apri(tmp_path / "t.sqlite")
    with caplog.at_level("WARNING"):
        r = stato_dati.riepilogo(db, ST)
    assert r["calibrazione"]["taratura"] is None and r["calibrazione"]["giornate"] == 0       # il resto della pagina c'è
    assert "OperationalError" in caplog.text and "dettaglio interno" not in caplog.text


def test_fattori_automatici_solo_con_abbastanza_dati():
    base = {"giornate": 3, "gruppi": [{"gruppo": "Titolare 90-100%", "n": 120, "osservato": 0.60, "previsto": 0.95, "indicativo": False},
                                      {"gruppo": "Panchina 20-49%", "n": 10, "osservato": 0.1, "previsto": 0.3, "indicativo": True},
                                      {"gruppo": "Titolare 70-89%", "n": 90, "osservato": 0.8, "previsto": 0.8, "indicativo": False}]}
    f = stato_dati.fattori_da(base)
    assert f["Titolare 90-100%"] == 0.85                      # troppo lontano: si ferma al -15%
    assert "Panchina 20-49%" not in f                        # pochi giocatori: niente correzione
    assert f["Titolare 70-89%"] == 1.0
    assert stato_dati.fattori_da({**base, "giornate": 2}) == {}   # poche giornate


def test_modello_applica_la_correzione():
    import pandas as pd
    from fanta import modello
    from tests.test_modello import _dati
    prob = pd.DataFrame([{"calciatore_id": 2, "stato": "titolare", "percentuale": 95.0, "in_dubbio": 0, "nota": None}])
    d = _dati()
    senza = modello.previsioni(d, "2026-27", 5, modello.Regole(), probabili=prob).set_index("id")
    con = modello.previsioni(d, "2026-27", 5, modello.Regole(), probabili=prob, fattori_probabili={"Titolare 90-100%": 0.85}).set_index("id")
    assert con.at[2, "p_voto"] == round(senza.at[2, "p_voto"] * 0.85, 3)
    assert modello.gruppo_probabili("titolare", 95) == "Titolare 90-100%" and modello.gruppo_probabili("panchina", 10) == "Panchina sotto 20%"


def test_affidabilita_si_rifa_solo_con_una_giornata_nuova(tmp_path, monkeypatch):
    import pandas as pd
    from fanta import affidabilita, archivio, consigli
    from fanta.regole import Regole
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in (1, 2):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2026-09-01 18:00', 'a', 'b', 1)", (g, ST, g))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    chiamate = []

    def finta(d, regole, par, giornate, rose=None, simulazioni=0, scrivi=None):
        chiamate.append(list(giornate))
        return pd.DataFrame([{"stagione": s, "giornata": g, "errore_modello": 1.0, "errore_fantamedia": 1.2, "brier": 0.1, "n": 50,
                              "quadratico_modello": 1.0, "quadratico_fantamedia": 1.44, "punti_modello": 70.0, "punti_fantamedia": 66.0, "punti_perfetta": 85.0}
                             for s, g in giornate])
    monkeypatch.setattr(affidabilita.verifica, "verifica", finta)
    f = tmp_path / "a.json"
    assert affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) is True
    assert affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) is False          # nessuna giornata nuova
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (3, ?, 3, '2026-09-08 18:00', 'a', 'b', 1)", (ST,))
    assert affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) is True           # è finita la 3
    r = affidabilita.carica(f)
    assert r["ultima"] == f"{ST}/3" and r["sintesi"]["errore_modello"] == 1.0 and r["sintesi"]["errore_fantamedia"] == 1.2 and r["sintesi"]["punti_modello"] == 70.0
    assert len(chiamate) == 2 and affidabilita.carica(tmp_path / "non-esiste.json") == {}
