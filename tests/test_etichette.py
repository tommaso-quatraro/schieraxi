"""Etichetta di stato del giocatore pronta dal server (fanta/etichette.py): una regola sola, parole del vocabolario comune
(docs/COERENZA-WEB-IPHONE.md), testo nella lingua della richiesta."""
import gzip
import json
import re
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, etichette, fasi, scheda, server
from fanta.regole import Regole

TESTI = (Path(server.__file__).parent / "web" / "testi.js").read_text(encoding="utf-8")

# codice -> (italiano, inglese, tono) attesi: è il contratto per i client
ATTESI = {
    "titolare": ("Probabile titolare", "Likely starter", "positivo"),
    "ballottaggio": ("In ballottaggio", "Contested", "attenzione"),
    "panchina": ("Probabile panchina", "Likely bench", "attenzione"),
    "improbabile": ("Improbabile", "Unlikely", "negativo"),
    "in_dubbio": ("In dubbio · gioca 55%", "Doubtful · plays 55%", "attenzione"),
    "infortunato": ("Infortunato", "Injured", "negativo"),
    "squalificato": ("Squalificato", "Suspended", "negativo"),
    "fuori": ("Fuori", "Out", "negativo"),
    "rinviata": ("Rinviata", "Postponed", "attenzione"),
    "da_giocare": ("Da giocare", "Still to play", "neutro"),
    "in_corso": ("Partita in corso", "Match on", "positivo"),
    "voto_in_arrivo": ("Voto in arrivo", "Grade coming", "neutro"),
    "voto": ("Ha giocato", "Played", "positivo"),
    "senza_voto": ("Senza voto", "No grade", "attenzione"),
    "diffidato": ("Diffidato", "One yellow from a ban", "attenzione"),
}


@pytest.mark.parametrize("codice", sorted(ATTESI))
def test_ogni_codice_in_italiano_e_in_inglese(codice):
    it, en, tono = ATTESI[codice]
    assert etichette.crea(codice, 0.55) == {"codice": codice, "testo": it, "tono": tono}
    assert etichette.crea(codice, 0.55, "en") == {"codice": codice, "testo": en, "tono": tono}
    assert tono in etichette.TONI


def test_nessun_codice_senza_contratto():
    assert set(etichette.CODICI) == set(ATTESI)


def _testo_web(chiave: str) -> tuple[str, str]:
    voci = re.findall(rf'"{re.escape(chiave)}": "([^"]+)"', TESTI)
    assert len(voci) == 2, chiave                      # una in italiano, una in inglese
    return voci[0], voci[1]


def test_stesse_parole_della_web():
    """Il vocabolario è quello di testi.js: se una parola cambia sulla web, questo test lo dice."""
    web = {"titolare": "tit.titolare", "ballottaggio": "tit.ballottaggio", "panchina": "tit.panchina", "improbabile": "tit.improbabile",
           "fuori": "tit.fuori", "voto": "tit.st_fatto", "senza_voto": "tit.st_senza_voto", "voto_in_arrivo": "tit.st_attesa_voti",
           "in_corso": "tit.st_in_corso", "da_giocare": "tit.st_da_giocare", "rinviata": "tit.st_rinviata",
           "infortunato": "oggi.infortunato", "squalificato": "oggi.squalificato", "diffidato": "oggi.diffidato_tipo"}
    for codice, chiave in web.items():
        assert _testo_web(chiave) == etichette.CODICI[codice][:2], codice
    it, en = _testo_web("oggi.dubbio")                 # «In dubbio · gioca {p}» con p = «55%»
    assert (it.replace("{p}", "{p}%"), en.replace("{p}", "{p}%")) == etichette.CODICI["in_dubbio"][:2]


def test_percentuale_come_la_web():
    """Math.round della web: mezzo punto in su (Python arrotonda al pari)."""
    assert etichette.crea("in_dubbio", 0.545)["testo"].endswith("gioca 55%")
    assert etichette.crea("in_dubbio", 0.125)["testo"].endswith("gioca 13%")
    assert etichette.crea("in_dubbio", None)["testo"].endswith("gioca 0%")


# ---------------------------------------------------------------- la regola
def _c(**x):
    return etichette.codice(x)


def test_regola_prima_della_scadenza():
    assert _c(titolarita="titolare", p_voto=0.9) == "titolare"
    assert _c(titolarita="ballottaggio") == "ballottaggio"
    assert _c(titolarita="panchina") == "panchina"
    assert _c(titolarita="improbabile") == "improbabile"
    assert _c(titolarita="titolare", dubbio=True, p_voto=0.85) == "in_dubbio"          # il dubbio delle probabili si dice
    assert _c(titolarita="fuori", stato="infortunato", dubbio=True) == "infortunato"
    assert _c(titolarita="fuori", stato="squalificato") == "squalificato"
    assert _c(titolarita="fuori") == "fuori"
    assert _c(titolarita="fuori", rinvio="senza_voto") == "rinviata"                   # la causa vera: la partita è rinviata
    assert _c(titolarita="titolare", rinvio="aspetta") == "rinviata"
    assert _c(titolarita=None) is None and _c() is None


def test_regola_dopo_la_scadenza():
    base = {"titolarita": None, "stato": "titolare", "dubbio": True}                    # le probabili non contano più
    attesi = {"fatto": "voto", "senza_voto": "senza_voto", "attesa_voti": "voto_in_arrivo", "in_corso": "in_corso",
              "da_giocare": "da_giocare", "rinviata": "rinviata"}
    for stato_partita, codice in attesi.items():
        assert etichette.codice(base | {"stato_partita": stato_partita}) == codice
    # infortunato o squalificato: resta tale finché non escono i voti (titolarita «fuori», fasi.schede_a_giornata_iniziata)
    for sp in ("da_giocare", "in_corso", "attesa_voti"):
        assert _c(stato_partita=sp, titolarita="fuori", stato="infortunato") == "infortunato"
        assert _c(stato_partita=sp, titolarita="fuori", stato="squalificato") == "squalificato"
        assert _c(stato_partita=sp, titolarita="fuori") == "fuori"
    assert _c(stato_partita="senza_voto", titolarita="fuori", stato="infortunato") == "senza_voto"
    assert _c(stato_partita="rinviata", titolarita="fuori", stato="infortunato") == "rinviata"


def test_avvisi_di_oggi():
    assert etichette.di_avviso("dubbio", 0.55)["testo"] == "In dubbio · gioca 55%"
    assert etichette.di_avviso("infortunato")["codice"] == "infortunato"
    assert etichette.di_avviso("diffidato", lingua="en")["testo"] == "One yellow from a ban"
    assert etichette.di_avviso("altro") is None


# ---------------------------------------------------------------- dove arriva
def _riga(**k):
    base = {"nome": "X", "ruolo": "A", "squadra": "a", "avversario": "b", "in_casa": True, "p_voto": 0.9, "mu": 7.0, "mu_voto": 6.5,
            "atteso": 6.3, "dubbio": False, "diffidato": False, "data_partita": None, "stato": "titolare", "percentuale": None,
            "nota": None, "quota_titolare": 0.9, "e_gol": 0.3, "e_assist": 0.1, "e_rigori": 0.0, "p_imbattuto": 0.0, "p_gol": 0.26,
            "p_assist": 0.1, "p_giallo": 0.1, "p_rosso": 0.0, "indice": 50, "difficolta": 3, "gol_squadra": 1.2, "gol_avversario": 1.2}
    return pd.Series(base | k)


def test_ogni_scheda_ha_l_etichetta():
    assert consigli.scheda_previsione(7, _riga())["etichetta"] == {"codice": "titolare", "testo": "Probabile titolare", "tono": "positivo"}
    s = consigli.scheda_previsione(7, _riga(dubbio=True, p_voto=0.553))
    assert s["etichetta"]["testo"] == "In dubbio · gioca 55%"
    assert consigli.scheda_previsione(7, _riga(stato="infortunato", p_voto=0.0))["etichetta"]["codice"] == "infortunato"


def test_dopo_la_scadenza_l_etichetta_segue_la_partita(monkeypatch):
    schede = [consigli.scheda_previsione(1, _riga()), consigli.scheda_previsione(2, _riga(stato="infortunato", p_voto=0.0))]
    monkeypatch.setattr(fasi, "stati_giocatori", lambda *a, **k: {1: "attesa_voti", 2: "attesa_voti"})
    monkeypatch.setattr(fasi, "_fantavoti_presi", lambda *a, **k: {})
    nuove = fasi.schede_a_giornata_iniziata(schede, None, Regole(), "2026-27", 10, None)
    assert nuove[1]["etichetta"]["testo"] == "Voto in arrivo" and nuove[2]["etichetta"]["testo"] == "Infortunato"
    assert schede[0]["etichetta"]["codice"] == "titolare"                      # la scheda in cache non cambia


def test_traduzione_della_risposta_in_inglese():
    corpo = {"titolari": [{"id": 1, "etichetta": etichette.crea("in_dubbio", 0.55)}],
             "in_corso": {"giocatori": [{"id": 2, "etichetta": etichette.crea("voto_in_arrivo")}]}}
    chiaro = json.dumps(corpo).encode()
    nuovo = json.loads(server._riscrivi_note(chiaro, False))
    assert nuovo["titolari"][0]["etichetta"] == {"codice": "in_dubbio", "testo": "Doubtful · plays 55%", "tono": "attenzione"}
    assert nuovo["in_corso"]["giocatori"][0]["etichetta"]["testo"] == "Grade coming"
    assert json.loads(gzip.decompress(server._riscrivi_note(gzip.compress(chiaro), True))) == nuovo
    strano = {"etichetta": {"codice": "nuovo_di_domani", "testo": "Qualcosa"}}            # un codice sconosciuto resta com'è
    assert json.loads(server._riscrivi_note(json.dumps(strano).encode(), False)) == strano


def test_la_rotta_risponde_nella_lingua_chiesta(tmp_path, monkeypatch):
    prev = pd.DataFrame([dict(_riga(dubbio=True, p_voto=0.55))], index=[1])
    monkeypatch.setattr(consigli, "previsioni", lambda *a, **k: (prev, 10, None))
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(scheda, "scheda", lambda *a, **k: {"calciatore": {"ruolo": "A"}, "avanzate": {}, "stagione": {"con_voto": 0}})
    monkeypatch.setattr(scheda, "rendimento", lambda *a, **k: None)
    monkeypatch.setattr(fasi, "iniziata", lambda *a, **k: False)
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/giocatore/1").json()["previsione"]["etichetta"]["testo"] == "In dubbio · gioca 55%"
    assert c.get("/api/giocatore/1?lingua=en").json()["previsione"]["etichetta"]["testo"] == "Doubtful · plays 55%"
    en = c.get("/api/giocatore/1", headers={"Accept-Language": "en-GB,en;q=0.9"}).json()["previsione"]["etichetta"]
    assert en == {"codice": "in_dubbio", "testo": "Doubtful · plays 55%", "tono": "attenzione"}
