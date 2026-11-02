"""«Da fare» di Oggi (fanta/da_fare.py), il campo piccolo `primo_avvio` e il suo contratto."""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import calcolo, da_fare, notifiche, scelte, server, stato_utente

ADESSO = datetime(2026, 11, 3, 12, 0)
STAGIONE = "2026-27"


def _x(i, nome, ruolo="C", stato=None, dubbio=False, p_voto=0.9, atteso=6.0):
    return {"id": i, "nome": nome, "ruolo": ruolo, "stato": stato, "dubbio": dubbio, "p_voto": p_voto, "punti_attesi": atteso}


@pytest.fixture
def mondo(tmp_path, monkeypatch):
    """Una rosa di 14, titolari 1-11 (il 5 in dubbio, il 6 infortunato), panchina 12-14, tutto in cache finta."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.55)
    schede[6] = _x(6, "Bianchi", stato="infortunato", p_voto=0.0)
    schede[12] = _x(12, "Riserva", atteso=4.5)
    schede[13] = _x(13, "Fuori", stato="squalificato", atteso=9.0)
    monkeypatch.setattr(da_fare.consigli, "stagione_corrente", lambda: STAGIONE)
    monkeypatch.setattr(da_fare.consigli, "previsioni", lambda db, r: (pd.DataFrame(index=list(range(1, 15))), 9, True))
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda db, r, ro: {"titolari": [{"id": i} for i in range(1, 12)]})
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": []})
    monkeypatch.setattr(da_fare.consigli, "proposte_scambi", lambda *a, **k: (None, []))
    rose = NS(mia_squadra="Mia", squadra=lambda n: NS(giocatori=[NS(id=i) for i in range(1, 15)]))
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INTEGER, data TEXT, giocata INTEGER)")
    db.execute("CREATE TABLE aggiornamenti (cosa TEXT, quando TEXT, dettaglio TEXT)")
    db.execute("INSERT INTO aggiornamenti VALUES ('aggiornamento', ?, '')", (ADESSO.isoformat(),))
    rose_file = tmp_path / "rose.json"
    rose_file.write_text("{}")
    ctx = NS(utente_id=None, rose=rose_file, scelte=tmp_path / "scelte.json", diario=tmp_path / "diario.json",
             impostazioni_avvisi=tmp_path / "imp.json")
    oggi = {"giornata": 9, "ore_mancanti": 30.0, "iniziata": False}
    return NS(db=db, rose=rose, ctx=ctx, oggi=oggi, tmp=tmp_path)


def vai(m, **k):
    return da_fare.costruisci(m.db, object(), m.rose, k.pop("oggi", m.oggi), k.pop("ctx", m.ctx), adesso=ADESSO, **k)


def test_dubbi_e_infortuni_con_alternativa(mondo):
    v = vai(mondo)
    d = [x for x in v if x["tipo"] == "dubbio"]
    assert [x["id"] for x in d] == ["dubbio:6", "dubbio:5"]                 # prima chi è fuori
    assert d[0]["priorita"] == 1 and d[1]["priorita"] == 2
    assert d[0]["alternativa"]["id"] == 14                                  # il 13 è squalificato: non si propone
    assert "Meglio g14" in d[1]["testo"] and "55%" in d[1]["testo"]
    assert d[1]["destinazione"] == {"scheda": "formazione", "sezione": None, "link": "schieraxi://giocatore/5", "giocatore": 5}
    assert all(x["azione"] and x["testo"] for x in v)


def test_nome_con_il_punto_non_raddoppia_il_punto(mondo, monkeypatch):
    """«Adams A.» finisce già col punto: la frase non deve chiudersi con due punti («Meglio Adams A..»)."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.55)
    schede[14] = _x(14, "Adams A.", atteso=7.0)
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    testo = [x for x in vai(mondo) if x["id"] == "dubbio:5"][0]["testo"]
    assert "Meglio Adams A." in testo and ".." not in testo


def test_dopo_la_scadenza_niente_dubbi_ne_formazione(mondo):
    assert vai(mondo, oggi={"giornata": 9, "ore_mancanti": -1.0, "iniziata": True}) == []


def test_formazione_non_salvata_vicino_alla_scadenza(mondo):
    mondo.oggi["ore_mancanti"] = 2.0
    f = [x for x in vai(mondo) if x["tipo"] == "formazione"]
    assert len(f) == 1 and f[0]["priorita"] == 1 and "2 ore" in f[0]["testo"]
    mondo.oggi["ore_mancanti"] = 8.0
    assert [x for x in vai(mondo) if x["tipo"] == "formazione"][0]["priorita"] == 2
    mondo.oggi["ore_mancanti"] = 20.0
    assert not [x for x in vai(mondo) if x["tipo"] == "formazione"]          # ancora presto
    mondo.oggi["ore_mancanti"] = 2.0
    scelte.salva(STAGIONE, 9, list(range(1, 12)), "4-4-2", mondo.ctx.scelte)
    assert not [x for x in vai(mondo) if x["tipo"] == "formazione"]          # salvata: sparisce
    scelte.salva_automatica(STAGIONE, 9, list(range(1, 12)), "4-4-2", mondo.ctx.scelte)


def test_la_scelta_salvata_con_un_infortunato_si_segnala(mondo):
    scelte.salva(STAGIONE, 9, [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12], "4-4-2", mondo.ctx.scelte)
    ids = [x["id"] for x in vai(mondo) if x["tipo"] == "dubbio"]
    assert ids == ["dubbio:6"]                                               # il 5 non è nella scelta: nessun dubbio su di lui


def test_svincolato_e_scambio_solo_sopra_soglia(mondo, monkeypatch):
    prop = lambda g, fattibile=True, esce=7: {"proposte": [{"esce": {"id": esce, "nome": "Rossi"}, "entra": {"id": 40, "nome": "Nuovo"},
                                                             "guadagno": g, "fattibile": fattibile, "motivo": "Nuovo è titolare fisso nel Como"}]}
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(3.25))
    s = [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    assert len(s) == 1 and "3,2" in s[0]["testo"] and "titolare fisso nel Como" in s[0]["testo"] and s[0]["motivo"]
    assert s[0]["destinazione"]["link"] == "schieraxi://giocatore/40"
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(1.0))
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(3.0, fattibile=False))
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(3.0, esce=5))     # il 5 è già in un «dubbio»: un solo consiglio su di lui
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": [prop(3.0)["proposte"][0] | {"sensato": False}]})
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]            # bocciato dal buon senso del mercato
    monkeypatch.setattr(da_fare.consigli, "proposte_scambi", lambda *a, **k: (None, [
        {"altra": "Lupi", "do": [{"nome": "A"}], "ricevo": [{"nome": "B"}, {"nome": "C"}], "guadagno_mio": 2.5, "per_giornata_mio": [1.0, 1.0, 1.0]}]))
    sc = [x for x in vai(mondo) if x["tipo"] == "scambio"]
    assert sc and "Lupi" in sc[0]["testo"] and sc[0]["destinazione"]["link"] == "schieraxi://scambi"


def test_al_massimo_tre_consigli_e_le_altre_voci_restano(mondo, monkeypatch):
    """(g) dubbi, coperture, svincolati e scambi insieme non superano buon_senso.MAX_CONSIGLI; formazione e diario non contano."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    for i in (1, 2, 3):
        schede[i] = _x(i, f"g{i}", stato="squalificato", p_voto=0.0)
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": [
        {"esce": {"id": 9, "nome": "Nove"}, "entra": {"id": 50, "nome": "Nuovo"}, "guadagno": 5.0, "fattibile": True, "sensato": True}]})
    mondo.oggi["ore_mancanti"] = 2.0
    v = vai(mondo)
    assert sum(x["tipo"] in da_fare.CONSIGLI for x in v) == da_fare.buon_senso.MAX_CONSIGLI
    assert [x["tipo"] for x in v if x["tipo"] in da_fare.CONSIGLI] == ["dubbio"] * 3    # i più importanti prima
    assert [x for x in v if x["tipo"] == "formazione"]                                   # non è un consiglio: resta


def test_ripensamento_sui_movimenti_recenti(mondo, monkeypatch):
    """(f) chi ho preso da poco non si propone in uscita; chi ho lasciato libero da poco non si ripropone."""
    mondo.ctx.movimenti = mondo.tmp / "movimenti.json"
    mondo.ctx.movimenti.write_text(json.dumps([{"quando": (ADESSO - timedelta(days=3)).isoformat(),
                                                 "svincolati_presi": [{"squadra": "Mia", "giocatori": [{"id": 7, "nome": "Rossi"}]}],
                                                 "tagliati": [{"squadra": "Mia", "giocatori": [{"id": 41, "nome": "Vecchio"}]}], "scambi": []}]))
    prop = lambda esce, entra: {"proposte": [{"esce": {"id": esce, "nome": "X"}, "entra": {"id": entra, "nome": "Y"}, "guadagno": 4.0, "fattibile": True}]}
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(7, 40))
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(8, 41))
    assert not [x for x in vai(mondo) if x["tipo"] == "svincolato"]
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: prop(8, 40))
    assert [x for x in vai(mondo) if x["tipo"] == "svincolato"]


def test_niente_calcoli_nuovi_se_la_cache_e_vuota(mondo, monkeypatch):
    def nessuna_cache(*a, **k):
        assert calcolo.solo_cache.get()                                     # le parti facoltative girano in «solo cache»
        raise calcolo.InCalcolo()
    monkeypatch.setattr(da_fare.consigli, "mercato", nessuna_cache)
    monkeypatch.setattr(da_fare.consigli, "proposte_scambi", nessuna_cache)
    assert not [x for x in vai(mondo) if x["tipo"] in ("svincolato", "scambio")]


def test_rose_vecchie_solo_dopo_una_giornata(mondo):
    vecchio = (ADESSO - timedelta(days=6)).timestamp()
    os.utime(mondo.ctx.rose, (vecchio, vecchio))
    assert not [x for x in vai(mondo) if x["tipo"] == "rose"]                # nessuna giornata giocata: va bene così
    mondo.db.execute("INSERT INTO partite VALUES (?, 8, ?, 1)", (STAGIONE, (ADESSO - timedelta(days=2)).isoformat(sep=" ")[:16]))
    r = [x for x in vai(mondo) if x["tipo"] == "rose"]
    assert len(r) == 1 and r[0]["giorni"] == 6 and r[0]["destinazione"]["link"] == "schieraxi://lega/rose"
    fresco = (ADESSO - timedelta(days=1)).timestamp()
    os.utime(mondo.ctx.rose, (fresco, fresco))
    assert not [x for x in vai(mondo) if x["tipo"] == "rose"]


def test_certificato_lo_decide_il_client(mondo):
    assert not [x for x in vai(mondo) if x["tipo"] == "certificato"]
    assert not [x for x in vai(mondo, certificato_giorni=20) if x["tipo"] == "certificato"]
    c = [x for x in vai(mondo, certificato_giorni=1) if x["tipo"] == "certificato"]
    assert c[0]["priorita"] == 1 and c[0]["destinazione"]["link"] == "schieraxi://impostazioni/installazione"
    assert [x for x in vai(mondo, certificato_giorni=-2) if x["tipo"] == "certificato"][0]["priorita"] == 1


def test_diario_da_compilare(mondo):
    for g in (7, 8):
        mondo.db.execute("INSERT INTO partite VALUES (?, ?, '2026-10-20 18:00', 1)", (STAGIONE, g))
    d = [x for x in vai(mondo) if x["tipo"] == "diario"]
    assert [x["giornata"] for x in d] == [8, 7] and d[0]["azione"] == "Ho schierato la consigliata"
    scelte.salva(STAGIONE, 8, list(range(1, 12)), "4-4-2", mondo.ctx.scelte, tipo="consigliata")
    assert [x["giornata"] for x in vai(mondo) if x["tipo"] == "diario"] == [7]


def test_niente_promemoria_della_copia_di_sicurezza(mondo):
    """Dal 1/11/2026 la copia di sicurezza non si scarica più dalle app: nessuna voce «backup», nemmeno dopo mesi."""
    vecchio = (ADESSO - timedelta(days=400)).timestamp()
    os.utime(mondo.ctx.rose, (vecchio, vecchio))
    mondo.ctx.utente_id = 7
    assert not [x for x in vai(mondo) if x["tipo"] == "backup"]


def test_dati_vecchi_solo_per_chi_gestisce_il_server(mondo):
    mondo.db.execute("UPDATE aggiornamenti SET quando = ?", ((ADESSO - timedelta(days=5)).isoformat(),))
    assert [x for x in vai(mondo) if x["tipo"] == "server"]                  # app di sempre = proprietario
    mondo.ctx.utente_id = 7
    assert not [x for x in vai(mondo) if x["tipo"] == "server"]              # utente normale: non può farci niente
    assert [x for x in vai(mondo, amministratore=True) if x["tipo"] == "server"]


def test_passi_saltati_tornano_in_da_fare(mondo):
    stato_utente.scrivi_primo_avvio(mondo.ctx.impostazioni_avvisi, fatti=["rose"], saltati=["stemma", "widget"])
    p = [x for x in vai(mondo) if x["tipo"] == "primo_avvio"]
    assert p and "2 passi" in p[0]["testo"] and p[0]["saltati"] == ["stemma", "widget"]
    stato_utente.scrivi_primo_avvio(mondo.ctx.impostazioni_avvisi, chiuso=True)
    assert not [x for x in vai(mondo) if x["tipo"] == "primo_avvio"]


def test_ordine_tetto_e_nessun_errore(mondo, monkeypatch):
    mondo.oggi["ore_mancanti"] = 2.0
    v = vai(mondo, certificato_giorni=0)
    assert [x["priorita"] for x in v] == sorted(x["priorita"] for x in v) and len(v) <= da_fare.MAX_VOCI
    assert len({x["id"] for x in v}) == len(v)
    monkeypatch.setattr(da_fare.consigli, "previsioni", lambda *a: (_ for _ in ()).throw(RuntimeError("rotto")))
    assert [x for x in vai(mondo) if x["tipo"] == "formazione"]              # un controllo rotto non butta giù gli altri
    assert json.dumps(v)                                                     # tutto serializzabile


# ---------------------------------------------------------------- primo avvio (HTTP e file)
@pytest.fixture
def client(dati_isolati):
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_primo_avvio_http(client):
    r = client.get("/api/primo-avvio").json()
    assert r["primo_avvio"] is None and "rose" in r["passi"]
    r = client.put("/api/primo-avvio", json={"fatti": ["rose", "rose", "squadra"], "saltati": ["stemma", "rose"]}).json()["primo_avvio"]
    assert r["fatti"] == ["rose", "squadra"] and r["saltati"] == ["stemma"] and r["chiuso"] is False
    r = client.put("/api/primo-avvio", json={"chiuso": True}).json()["primo_avvio"]      # solo i campi mandati
    assert r["chiuso"] is True and r["fatti"] == ["rose", "squadra"]
    assert client.get("/api/primo-avvio").json()["primo_avvio"]["chiuso"] is True


@pytest.mark.parametrize("corpo", [
    {"fatti": ["inventato"]}, {"fatti": ["rose"] * 13}, {"saltati": [1]}, {"saltati": "rose"}, {"chiuso": "forse"}, {"fatti": [["rose"]]},
    {"fatti": ["../../etc/passwd"]}, {"fatti": ["x" * 100000]},
])
def test_primo_avvio_rifiuta_input_strani(client, corpo):
    r = client.put("/api/primo-avvio", json=corpo)
    assert r.status_code in (400, 422), r.text
    assert client.get("/api/primo-avvio").json()["primo_avvio"] is None      # non si è salvato niente


def test_primo_avvio_richiede_l_intestazione_e_non_e_ereditato(client):
    assert TestClient(server.app).put("/api/primo-avvio", json={"chiuso": True}).status_code == 403
    assert client.put("/api/primo-avvio", content=b"x" * 5000, headers={"Content-Type": "application/json"}).status_code == 422


def test_gli_avvisi_non_cancellano_il_primo_avvio(client):
    client.put("/api/primo-avvio", json={"saltati": ["widget"]})
    client.get("/api/backup")                                                # segna il backup
    assert client.put("/api/avvisi", json={"silenzio": True}).status_code == 200
    assert client.get("/api/primo-avvio").json()["primo_avvio"]["saltati"] == ["widget"]
    assert stato_utente.leggi_backup_il(notifiche.FILE_IMPOSTAZIONI) is not None
    corpo = client.get("/api/avvisi").json()["impostazioni"]
    assert "primo_avvio" not in corpo and "backup_il" not in corpo and corpo["silenzio"] is True   # le app vecchie non vedono altro


def test_file_rovinato_o_ripristinato_da_un_backup_malevolo(client):
    notifiche.FILE_IMPOSTAZIONI.parent.mkdir(parents=True, exist_ok=True)
    notifiche.FILE_IMPOSTAZIONI.write_text(json.dumps({"primo_avvio": {"fatti": ["rose", {"a": 1}, "<script>"], "saltati": 5, "chiuso": "si",
                                                                         "aggiornato": "y" * 5000}, "backup_il": 12}))
    p = client.get("/api/primo-avvio").json()["primo_avvio"]
    assert p == {"fatti": ["rose"], "saltati": [], "chiuso": False, "aggiornato": "y" * stato_utente.MAX_TESTO}
    assert stato_utente.leggi_backup_il(notifiche.FILE_IMPOSTAZIONI) is None
    notifiche.FILE_IMPOSTAZIONI.write_text("[1,2")
    assert client.get("/api/primo-avvio").json()["primo_avvio"] is None


def test_certificato_giorni_ha_un_tetto(client):
    assert client.get("/api/oggi", params={"certificato_giorni": 10 ** 9}).status_code == 422
    assert client.get("/api/oggi", params={"certificato_giorni": "abc"}).status_code == 422


# ---------------------------------------------------------------- senza rose: Oggi è un benvenuto, non un errore
def test_senza_rose_le_voci_sono_benvenuto_e_primo_avvio(tmp_path):
    imp = tmp_path / "imp.json"
    v = da_fare.senza_rose(imp)
    assert [x["tipo"] for x in v] == ["rose", "primo_avvio"] and v[0]["azione"] == "Importa le rose" and v[0]["priorita"] == 1
    stato_utente.scrivi_primo_avvio(imp, saltati=["stemma"])
    assert [x["tipo"] for x in da_fare.senza_rose(imp)] == ["rose"]          # già iniziato: niente invito doppio


def test_oggi_senza_rose_risponde_200(client):
    r = client.get("/api/oggi")
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["senza_rose"] is True and c["avvisi"] == [] and c["migliori"] == [] and "formazione" in c and "partite" in c
    assert c["da_fare"][0]["tipo"] == "rose" and c["da_fare"][0]["destinazione"]["scheda"] == "lega"
    assert client.get("/api/formazione").status_code == 409                    # le altre rotte restano com'erano


# ---------------------------------------------------------------- frasi traducibili (fanta/frasi.py)
def test_ogni_voce_ha_la_frase_per_tradurla(mondo):
    """Accanto a `testo` e `azione` (italiano, come sempre) c'è l'oggetto con chiave e parametri: ricostruito dà lo stesso testo."""
    from fanta import frasi
    voci = vai(mondo, oggi=dict(mondo.oggi, ore_mancanti=2.5), certificato_giorni=1, amministratore=True)
    assert {"dubbio", "formazione", "certificato"} <= {x["tipo"] for x in voci}
    for x in voci:
        assert frasi.da_json(x["frase"]) == x["testo"], x["id"]
        assert frasi.da_json(x["azione_frase"]) == x["azione"], x["id"]
    dubbio = next(x for x in voci if x["id"] == "dubbio:5")
    assert dubbio["frase"] == {"chiave": "dafare.dubbio_incerto_alt", "param": {"nome": "Rossi", "p": 55, "alt": "g14"}}
    formazione = next(x for x in voci if x["tipo"] == "formazione")
    assert formazione["frase"]["param"]["tempo"] == {"chiave": "tempo.ore", "param": {"n": 2}}


def test_svincolato_e_scambio_portano_motivo_e_guadagno_come_frasi(mondo, monkeypatch):
    from fanta import frasi
    motivo = frasi.F("senso.si_titolare_fisso_sq", nome="Nuovo", squadra="Como")
    proposta = {"esce": {"id": 7, "nome": "Rossi"}, "entra": {"id": 40, "nome": "Nuovo"}, "guadagno": 3.25, "breve": 2.84, "giornate": [1, 2, 3],
                "fattibile": True, "motivo": str(motivo), "motivo_frase": motivo.json()}       # come dopo un giro di JSON: il motivo è solo testo
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": [proposta]})
    s = next(x for x in vai(mondo) if x["tipo"] == "svincolato")
    assert s["testo"] == "Nuovo (libero) al posto di Rossi: Nuovo è titolare fisso (Como), circa 2,8 punti in più nelle prossime 3 giornate."
    assert s["frase"]["chiave"] == "dafare.svincolato_motivo"
    assert s["frase"]["param"]["motivo"] == motivo.json()
    assert s["frase"]["param"]["guadagno"] == {"chiave": "dafare.guadagno_breve", "param": {"punti": "2.8", "n": 3}}
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": []})
    monkeypatch.setattr(da_fare.consigli, "proposte_scambi", lambda *a, **k: (None, [
        {"altra": "Lupi", "do": [{"nome": "A"}], "ricevo": [{"nome": "B"}, {"nome": "C"}], "guadagno_mio": 2.5, "per_giornata_mio": [1.0, 1.0, 1.0]}]))
    sc = next(x for x in vai(mondo) if x["tipo"] == "scambio")
    assert sc["testo"] == "Con Lupi ti conviene scambiare: dai A, ricevi B, C, circa 2,5 punti in più."
    assert sc["frase"] == {"chiave": "dafare.scambio", "param": {"altra": "Lupi", "do": "A", "ricevo": "B, C",
                                                                 "guadagno": {"chiave": "dafare.guadagno_stagione", "param": {"punti": "2.5"}}}}
