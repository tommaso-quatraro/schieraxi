"""Etichette dei giocatori uguali in tutte le schermate (#281, #282, #284): «Da controllare» di Oggi e il widget usano la stessa
etichetta di Formazione e scheda (`etichette.di_giocatore`), la data del recupero di una partita rinviata ha la forma del
vocabolario («mer 18 nov»). Dati inventati, archivio in una cartella temporanea, nessuna rete."""
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import archivio, consigli, da_fare, etichette, frasi, gestione, lega, rinvii, server, widget
from fanta.regole import Regole

ST = "2026-27"
NODE = shutil.which("node")
TESTI_JS = (server.WEB / "testi.js").read_text(encoding="utf-8")


def _riga(i, nome, ruolo, squadra, p_voto, stato="titolare", dubbio=False, quota=0.9):
    """Una riga delle previsioni con tutte le colonne che usa `consigli.scheda_previsione` (la stessa della Formazione)."""
    return {"id": i, "nome": nome, "ruolo": ruolo, "squadra": squadra, "avversario": "roma", "in_casa": True, "p_voto": p_voto,
            "mu": 6.5, "mu_voto": 6.0, "atteso": 6.5 * p_voto, "e_gol": 0.1, "e_assist": 0.1, "e_rigori": 0.0, "p_imbattuto": 0.3,
            "p_gol": 0.1, "p_assist": 0.1, "p_giallo": 0.1, "p_rosso": 0.01, "quota_titolare": quota, "indice": 50, "difficolta": 3,
            "dubbio": dubbio, "diffidato": False, "data_partita": "2026-11-07 15:00", "gol_squadra": 1.2, "gol_avversario": 1.2,
            "stato": stato, "percentuale": 50.0, "nota": None}


# id: nome, ruolo, p_voto, stato delle probabili, in dubbio per le probabili. Tutti titolari della formazione.
ROSA = {1: ("Portiere", "P", 0.95, "titolare", False), 2: ("Rossi", "D", 0.85, "titolare", True),
        3: ("Dif3", "D", 0.9, "titolare", False), 4: ("Dif4", "D", 0.9, "titolare", False), 5: ("Dif5", "D", 0.9, "titolare", False),
        6: ("Fiorini", "C", 0.40, "panchina", False), 7: ("Cen7", "C", 0.9, "titolare", False), 8: ("Cen8", "C", 0.9, "titolare", False),
        9: ("Merlo", "C", 0.30, "panchina", False), 10: ("Lerri", "A", 0.02, "panchina", False), 11: ("Att11", "A", 0.9, "titolare", False)}


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    db = archivio.apri(tmp_path / "fanta.sqlite")
    archivio.inserisci(db, "partite", [{"id": 1, "stagione": ST, "giornata": 10, "data": "2026-11-07 15:00", "casa": "inter",
                                        "trasferta": "roma", "gol_casa": None, "gol_trasferta": None, "giocata": 0, "understat_id": None}])
    prev = pd.DataFrame([_riga(i, n, r, "inter", p, st, d) for i, (n, r, p, st, d) in ROSA.items()]).set_index("id")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 10, True))
    schede = {i: consigli.scheda_previsione(i, prev.loc[i]) for i in ROSA}
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "titolari": [schede[i] for i in ROSA], "panchina": [], "modulo": "4-4-2", "punteggio_atteso": 60.0, "squadra": "Mia"})
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, r, "inter", 1) for i, (n, r, *_) in ROSA.items()])], "Mia")
    return NS(db=db, rose=rose, tmp=tmp_path, prev=prev, schede=schede)


def _oggi(a):
    return gestione.oggi(a.db, Regole(), a.rose, adesso=datetime(2026, 11, 6, 12, 0), file_scelte=a.tmp / "scelte.json",
                         file_diario=a.tmp / "diario.json")


def test_da_controllare_usa_l_etichetta_della_formazione(ambiente):
    """#282: Lerri (2%) è «Improbabile», Merlo (30%) e Fiorini (40%) «Probabile panchina» in Formazione e nella scheda: Oggi li
    chiama allo stesso modo, non «In dubbio». Solo chi le probabili danno in dubbio (Rossi) è «In dubbio · gioca 85%»."""
    avvisi = {a["id"]: a for a in _oggi(ambiente)["avvisi"]}
    assert set(avvisi) == {2, 6, 9, 10}
    for i, a in avvisi.items():
        assert a["tipo"] == "dubbio" and a["in_formazione"]                     # il tipo non cambia: i client vecchi lo usano
        assert a["etichetta"] == ambiente.schede[i]["etichetta"], a["nome"]       # la stessa etichetta della Formazione
    assert avvisi[10]["etichetta"] == {"codice": "improbabile", "testo": "Improbabile", "tono": "negativo"}
    assert avvisi[9]["etichetta"]["testo"] == avvisi[6]["etichetta"]["testo"] == "Probabile panchina"
    assert avvisi[2]["etichetta"] == {"codice": "in_dubbio", "testo": "In dubbio · gioca 85%", "tono": "attenzione"}


def test_il_widget_manda_l_etichetta_degli_avvisi(monkeypatch):
    """Il widget scriveva «In dubbio · gioca 2%» dal `tipo`: ora ha la stessa `etichetta` di Oggi (campo facoltativo)."""
    et = {"codice": "improbabile", "testo": "Improbabile", "tono": "negativo"}
    s = {"id": 10, "nome": "Lerri", "ruolo": "A", "squadra": "inter", "avversario": "roma", "in_casa": True, "data_partita": None,
         "stato": "panchina", "percentuale": 50.0, "dubbio": False, "diffidato": False, "punti_attesi": 0.1, "p_voto": 0.02,
         "rigori_attesi": 0.0}
    monkeypatch.setattr(widget.gestione, "oggi", lambda *a, **k: {
        "giornata": 10, "inizio": "2026-11-07 15:00", "ore_mancanti": 3.0, "iniziata": False, "con_probabili": True, "partite": [],
        "avvisi": [{"id": 10, "nome": "Lerri", "ruolo": "A", "squadra": "inter", "tipo": "dubbio", "p_voto": 0.02, "nota": None,
                    "in_formazione": True, "etichetta": et}]})
    monkeypatch.setattr(widget.consigli, "formazione", lambda *a, **k: {"squadra": "X", "modulo": "4-4-2", "punteggio_atteso": 60.0,
                                                                         "schede": {"10": s}, "titolari": [s], "panchina": []})
    monkeypatch.setattr(widget.consigli, "previsioni", lambda *a, **k: (pd.DataFrame(index=[10]), 10, True))
    monkeypatch.setattr(widget.consigli, "scheda_previsione", lambda i, x: s)
    monkeypatch.setattr(widget.consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(widget.consigli, "proposte_scambi", lambda *a, **k: (None, []))
    monkeypatch.setattr(widget.consigli, "mercato", lambda *a, **k: {"proposte": []})
    monkeypatch.setattr(widget.avatar, "tutti", lambda: {})
    monkeypatch.setattr(widget.diario, "elenco", lambda *a, **k: {"giornate": []})
    monkeypatch.setattr(widget.osservati, "leggi", lambda *a, **k: [])
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE aggiornamenti (quando TEXT, cosa TEXT, dettaglio TEXT)")
    squadra = NS(nome="X", crediti_residui=1, giocatori=[NS(id=10)])
    c = widget.costruisci(db, object(), NS(mia_squadra="X", squadra=lambda n: squadra), None, None)
    assert c["avvisi"][0]["etichetta"] == et and c["avvisi"][0]["tipo"] == "dubbio"


def test_parole_delle_etichette_in_frase_uguali_a_quelle_della_formazione():
    """Da fare scrive la stessa parola dell'etichetta, in minuscolo: se cambia in etichette.py deve cambiare anche nella frase."""
    for c in ("ballottaggio", "panchina", "improbabile"):
        assert frasi.CATALOGO["etichetta." + c] == etichette.CODICI[c][0].lower()
    assert frasi.CATALOGO["etichetta.rinviata"] == "partita " + etichette.CODICI["rinviata"][0].lower()
    assert all("etichetta." + c in frasi.CATALOGO for c in da_fare.IN_FRASE)


# ---------------------------------------------------------------- #284: la data del recupero come nel resto dell'app
def test_data_del_recupero_con_giorno_e_mese():
    f = rinvii.frase("aspetta", None, "2026-11-18 18:30")
    assert f == "partita rinviata: conta il voto del recupero (mer 18 nov)"
    assert "18/11" not in f
    assert rinvii.frase("aspetta", None, "2026-12-07") == "partita rinviata: conta il voto del recupero (lun 7 dic)"
    assert rinvii.frase("aspetta", None, None) == "partita rinviata: conta il voto del recupero (data da definire)"
    d = frasi.di(f)["param"]["data"]                                          # la data è una frase: si traduce anche in inglese
    assert d == {"chiave": "data.giorno_mese", "param": {"giorno": {"chiave": "giorno.mer", "param": {}}, "n": 18,
                                                          "mese": {"chiave": "mese.nov", "param": {}}}}


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_data_del_recupero_in_inglese():
    f = rinvii.frase("aspetta", None, "2026-11-18 18:30")
    codice = f"{TESTI_JS}\nLINGUA = \"en\";\nconsole.log(JSON.stringify(traduciFrase({json.dumps(frasi.di(f))}, {json.dumps(str(f))})));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == "postponed match: the grade from the make-up game counts (Wed 18 Nov)"
