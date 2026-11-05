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
from fanta.regole import Regole

ADESSO = datetime(2026, 11, 3, 12, 0)
STAGIONE = "2026-27"
# i ruoli della rosa del `mondo`: i titolari 1-11 sono un 3-5-2 che si può schierare, in panchina tre centrocampisti
RUOLI = {1: "P", 2: "D", 3: "D", 4: "D", 5: "C", 6: "C", 7: "C", 8: "C", 9: "C", 10: "A", 11: "A", 12: "C", 13: "C", 14: "C"}


def _x(i, nome, ruolo="C", stato=None, dubbio=False, p_voto=0.9, atteso=6.0):
    return {"id": i, "nome": nome, "ruolo": ruolo, "stato": stato, "dubbio": dubbio, "p_voto": p_voto, "punti_attesi": atteso}


@pytest.fixture
def mondo(tmp_path, monkeypatch):
    """Una rosa di 14, titolari 1-11 (il 5 in dubbio, il 6 infortunato), panchina 12-14, tutto in cache finta.
    `sistema` è la formazione consigliata (titolari e panchina, in ordine): un test la cambia per dire cosa farebbe il sistema."""
    schede = {i: _x(i, f"g{i}", RUOLI[i]) for i in range(1, 15)}
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.55)
    schede[6] = _x(6, "Bianchi", stato="infortunato", p_voto=0.0)
    schede[12] = _x(12, "Riserva", atteso=4.5)
    schede[13] = _x(13, "Fuori", stato="squalificato", atteso=9.0)
    sistema = NS(titolari=list(range(1, 12)), panchina=[12, 13, 14])
    prev = pd.DataFrame({"ruolo": [RUOLI[i] for i in range(1, 15)]}, index=list(range(1, 15)))
    monkeypatch.setattr(da_fare.consigli, "stagione_corrente", lambda: STAGIONE)
    monkeypatch.setattr(da_fare.consigli, "previsioni", lambda db, r, giornata=None: (prev, 9, True))
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    monkeypatch.setattr(da_fare.consigli, "formazione", lambda db, r, ro: {"titolari": [{"id": i} for i in sistema.titolari],
                                                                          "panchina": [{"id": i} for i in sistema.panchina]})
    monkeypatch.setattr(da_fare.consigli, "mercato", lambda *a, **k: {"proposte": []})
    monkeypatch.setattr(da_fare.consigli, "proposte_scambi", lambda *a, **k: (None, []))
    rose = NS(mia_squadra="Mia", squadra=lambda n: NS(giocatori=[NS(id=i, ruolo=RUOLI[i]) for i in range(1, 15)]))
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INTEGER, data TEXT, giocata INTEGER)")
    db.execute("CREATE TABLE aggiornamenti (cosa TEXT, quando TEXT, dettaglio TEXT)")
    db.execute("INSERT INTO aggiornamenti VALUES ('aggiornamento', ?, '')", (ADESSO.isoformat(),))
    rose_file = tmp_path / "rose.json"
    rose_file.write_text("{}")
    ctx = NS(utente_id=None, rose=rose_file, scelte=tmp_path / "scelte.json", diario=tmp_path / "diario.json",
             impostazioni_avvisi=tmp_path / "imp.json")
    oggi = {"giornata": 9, "ore_mancanti": 30.0, "iniziata": False}
    return NS(db=db, rose=rose, ctx=ctx, oggi=oggi, tmp=tmp_path, sistema=sistema)


def vai(m, **k):
    return da_fare.costruisci(m.db, k.pop("regole", Regole()), m.rose, k.pop("oggi", m.oggi), k.pop("ctx", m.ctx), adesso=ADESSO, **k)


def la_consigliata_cambia(m, *cambi):
    """Hai salvato i titolari 1-11; la formazione consigliata invece toglie `esce` (va in panchina) e schiera `entra`."""
    scelte.salva(STAGIONE, 9, list(range(1, 12)), "4-4-2", m.ctx.scelte)
    for esce, entra in cambi:
        m.sistema.titolari = [entra if i == esce else i for i in m.sistema.titolari]
        m.sistema.panchina = [esce if i == entra else i for i in m.sistema.panchina]


def test_dubbi_e_infortuni_con_alternativa(mondo):
    la_consigliata_cambia(mondo, (6, 14), (5, 12))
    v = vai(mondo)
    d = [x for x in v if x["tipo"] == "dubbio"]
    assert [x["id"] for x in d] == ["dubbio:6", "dubbio:5"]                 # prima chi è fuori
    assert d[0]["priorita"] == 1 and d[1]["priorita"] == 2
    assert d[0]["alternativa"]["id"] == 14                                  # il 13 è squalificato: non si propone
    # un sostituto per volta: il 14 va già al posto dell'infortunato, per il 5 resta il 12
    assert d[1]["alternativa"]["id"] == 12 and "Meglio Riserva" in d[1]["testo"] and "55%" in d[1]["testo"]
    assert d[1]["destinazione"] == {"scheda": "formazione", "sezione": None, "link": "schieraxi://giocatore/5", "giocatore": 5}
    assert all(x["azione"] == "Sostituisci" for x in d)
    assert all(x["azione"] and x["testo"] for x in v)


def test_titolare_in_dubbio_tenuto_dalla_consigliata_niente_cambio(mondo):
    """#266: la consigliata tiene Rossi (55%) titolare e la riserva in panchina, quindi Formazione e confronto dicono «Schiera Rossi».
    Da fare non deve scrivere «Meglio Riserva» né avere «Sostituisci»: dice chi entra se lui non gioca."""
    mondo.sistema.titolari, mondo.sistema.panchina = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14], [12, 13, 6]     # l'infortunato non c'è
    v = vai(mondo)
    d = [x for x in v if x["tipo"] == "dubbio"]
    assert [x["id"] for x in d] == ["dubbio:5"]
    assert "Meglio" not in d[0]["testo"] and "alternativa" not in d[0]
    assert d[0]["testo"] == "Rossi è in dubbio (55% di giocare) ma resta titolare: se non gioca entra Riserva dalla panchina."
    assert d[0]["frase"] == {"chiave": "dafare.dubbio_incerto_tiene", "param": {"nome": "Rossi", "p": 55, "riserva": "Riserva"}}
    assert d[0]["riserva"] == {"id": 12, "nome": "Riserva"} and d[0]["giocatore"] == {"id": 5, "nome": "Rossi"}
    assert d[0]["priorita"] == 2 and d[0]["azione"] == "Apri la formazione"
    assert d[0]["destinazione"] == {"scheda": "formazione", "sezione": None, "link": "schieraxi://formazione"}


def test_titolare_tolto_dalla_consigliata_il_cambio_resta(mondo):
    """#266: hai salvato Rossi titolare, ma la consigliata lo mette in panchina e schiera la riserva: il cambio si propone."""
    la_consigliata_cambia(mondo, (5, 12))
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")
    assert d["testo"] == "Rossi è in dubbio (55% di giocare). Meglio Riserva."
    assert d["alternativa"]["id"] == 12 and d["azione"] == "Sostituisci" and "riserva" not in d


def test_tutti_e_due_titolari_nella_consigliata_decidono_i_punti(mondo, monkeypatch):
    """Stessa regola di `consigliato` del confronto: se la consigliata schiera tutti e due (tu hai salvato solo Rossi), conta chi ha
    più punti attesi da solo."""
    scelte.salva(STAGIONE, 9, [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12], "4-4-2", mondo.ctx.scelte)
    mondo.sistema.titolari = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14]          # schiera anche il 14 (6,0 punti attesi)
    mondo.sistema.panchina = [12, 13, 6]
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")               # Rossi ne ha 6,0 anche lui: a pari punti resta lui
    assert "Meglio" not in d["testo"] and d["azione"] == "Apri la formazione"
    schede = {i: da_fare.consigli.scheda_previsione(i, None) for i in range(1, 15)}
    schede[5] = schede[5] | {"punti_attesi": 3.3}
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")
    assert d["alternativa"]["id"] == 14 and "Meglio g14" in d["testo"] and d["azione"] == "Sostituisci"


def test_tenuto_senza_sostituzioni_o_senza_riserva_niente_panchina(mondo):
    """Senza sostituzioni nella lega (o senza una riserva dello stesso ruolo in panchina) nessuno entra al suo posto: la frase non lo dice."""
    mondo.sistema.titolari, mondo.sistema.panchina = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14], [12, 13, 6]
    senza_cambi = NS(panchina=NS(max_sostituzioni=0))
    d = next(x for x in vai(mondo, regole=senza_cambi) if x["id"] == "dubbio:5")
    assert d["testo"] == "Rossi è in dubbio (55% di giocare)." and d["azione"] == "Apri la formazione" and "riserva" not in d
    mondo.sistema.panchina = [13, 6]                                         # in panchina solo uno squalificato e l'infortunato
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")
    assert d["testo"] == "Rossi è in dubbio (55% di giocare)." and "riserva" not in d


def test_il_cambio_da_fare_non_resta_fuori_dal_tetto(mondo, monkeypatch):
    """Quattro titolari in dubbio, uno solo da cambiare: le voci che non chiedono niente («resta titolare») non lo spingono oltre
    il tetto di 3 dubbi."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    for i in (2, 3, 4):
        schede[i] = _x(i, f"g{i}", dubbio=True, p_voto=0.5)
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.55)
    schede[12] = _x(12, "Riserva", atteso=4.5)
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    la_consigliata_cambia(mondo, (5, 12))
    d = [x for x in vai(mondo) if x["tipo"] == "dubbio"]
    assert len(d) == da_fare.MAX_DUBBI and d[0]["id"] == "dubbio:5" and d[0]["azione"] == "Sostituisci"


def test_mai_lo_stesso_sostituto_per_due(mondo, monkeypatch):
    """Due titolari in dubbio nello stesso ruolo e una sola riserva: il sostituto va a chi rischia di più, l'altro resta senza."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.6)
    schede[7] = _x(7, "Verdi", dubbio=True, p_voto=0.4)
    for i in (12, 13):
        schede[i] = _x(i, f"g{i}", ruolo="D")
    schede[14] = _x(14, "Unica", atteso=7.0)
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    d = {x["id"]: x for x in vai(mondo) if x["tipo"] == "dubbio"}             # la consigliata li tiene tutti e due
    assert d["dubbio:7"]["riserva"]["id"] == 14 and "riserva" not in d["dubbio:5"] and "alternativa" not in d["dubbio:5"]
    la_consigliata_cambia(mondo, (7, 14))                                     # la consigliata toglie Verdi
    d = {x["id"]: x for x in vai(mondo) if x["tipo"] == "dubbio"}
    assert d["dubbio:7"]["alternativa"]["id"] == 14 and "alternativa" not in d["dubbio:5"] and "riserva" not in d["dubbio:5"]
    assert d["dubbio:7"]["azione"] == "Sostituisci" and d["dubbio:5"]["azione"] == "Apri la formazione"     # nessun sostituto: nessun cambio


def test_nome_con_il_punto_non_raddoppia_il_punto(mondo, monkeypatch):
    """«Adams A.» finisce già col punto: la frase non deve chiudersi con due punti («Meglio Adams A..»)."""
    schede = {i: _x(i, f"g{i}") for i in range(1, 15)}
    schede[5] = _x(5, "Rossi", dubbio=True, p_voto=0.55)
    schede[14] = _x(14, "Adams A.", atteso=7.0)
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])
    la_consigliata_cambia(mondo, (5, 14))
    testo = [x for x in vai(mondo) if x["id"] == "dubbio:5"][0]["testo"]
    assert "Meglio Adams A." in testo and ".." not in testo


def _etichettati(monkeypatch, **cambi):
    """Schede con la titolarità come le manda il server (consigli.titolarita): `cambi` = {id: scheda}."""
    schede = {i: _x(i, f"g{i}") | {"titolarita": "titolare"} for i in range(1, 15)}
    schede[12] = _x(12, "Riserva", atteso=4.5) | {"titolarita": "titolare"}
    schede |= {int(k[1:]): v for k, v in cambi.items()}
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione", lambda i, x: schede[i])


def test_chi_non_e_in_dubbio_non_si_chiama_in_dubbio(mondo, monkeypatch):
    """#282: un titolare al 2% che le probabili NON danno in dubbio è «Improbabile» in Formazione, Oggi e scheda: Da fare lo chiama
    con la stessa parola, mai «in dubbio»."""
    _etichettati(monkeypatch, g5=_x(5, "Lerri", p_voto=0.02) | {"titolarita": "improbabile"})
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")
    assert "dubbio" not in d["testo"]
    assert d["testo"] == "Lerri (improbabile, gioca 2%) resta titolare: se non gioca entra Riserva dalla panchina."
    assert d["frase"] == {"chiave": "dafare.incerto_tiene",
                          "param": {"nome": "Lerri", "stato": {"chiave": "etichetta.improbabile", "param": {}}, "p": 2, "riserva": "Riserva"}}
    la_consigliata_cambia(mondo, (5, 12))
    d = next(x for x in vai(mondo) if x["id"] == "dubbio:5")
    assert d["testo"] == "Lerri: improbabile, gioca 2%. Meglio Riserva." and d["azione"] == "Sostituisci"


def test_probabile_panchina_e_ballottaggio_con_le_parole_della_formazione(mondo, monkeypatch):
    """#282: Merlo (30%) e Fiorini (40%) sono «Probabile panchina» in Formazione; un 60% senza dubbio è «In ballottaggio»."""
    _etichettati(monkeypatch, g5=_x(5, "Merlo", p_voto=0.3) | {"titolarita": "panchina"},
                 g7=_x(7, "Fiorini", p_voto=0.6) | {"titolarita": "ballottaggio"})
    senza_cambi = NS(panchina=NS(max_sostituzioni=0))
    d = {x["id"]: x["testo"] for x in vai(mondo, regole=senza_cambi) if x["tipo"] == "dubbio"}
    assert d["dubbio:5"] == "Merlo: probabile panchina, gioca 30%."
    assert d["dubbio:7"] == "Fiorini: in ballottaggio, gioca 60%."


def test_chi_e_davvero_in_dubbio_resta_in_dubbio(mondo, monkeypatch):
    """Le probabili lo danno in dubbio: l'etichetta è «In dubbio · gioca 55%» e la frase di Da fare resta «è in dubbio»."""
    _etichettati(monkeypatch, g5=_x(5, "Rossi", dubbio=True, p_voto=0.55) | {"titolarita": "ballottaggio"})
    d = next(x for x in vai(mondo, regole=NS(panchina=NS(max_sostituzioni=0))) if x["id"] == "dubbio:5")
    assert d["testo"] == "Rossi è in dubbio (55% di giocare)." and d["frase"]["chiave"] == "dafare.dubbio_incerto"


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


def test_rose_da_aggiornare_solo_dopo_la_sosta(mondo):
    """#334: una giornata giocata con le rose ferme da giorni non basta più (era rumore ogni settimana): serve un momento di
    mercato della lega, qui la sosta fra la 8 e la 9. Le altre prove in tests/test_promemoria_rose.py."""
    vecchio = (ADESSO - timedelta(days=6)).timestamp()
    os.utime(mondo.ctx.rose, (vecchio, vecchio))
    mondo.db.execute("INSERT INTO partite VALUES (?, 8, ?, 1)", (STAGIONE, (ADESSO - timedelta(days=2)).isoformat(sep=" ")[:16]))
    mondo.db.execute("INSERT INTO partite VALUES (?, 9, ?, 0)", (STAGIONE, (ADESSO + timedelta(days=3)).isoformat(sep=" ")[:16]))
    assert not [x for x in vai(mondo) if x["tipo"] == "rose"]                # nessuna sosta: niente promemoria
    mondo.db.execute("UPDATE partite SET data = ? WHERE giornata = 9", ((ADESSO + timedelta(days=9)).isoformat(sep=" ")[:16],))
    r = [x for x in vai(mondo) if x["tipo"] == "rose"]                       # 11 giorni fra la 8 e la 9: sosta
    assert len(r) == 1 and r[0]["giorni"] == 6 and r[0]["destinazione"]["link"] == "schieraxi://lega/rose"
    assert r[0]["frase"] == {"chiave": "dafare.rose_mercato", "param": {"giornata": {"chiave": "giornata.lega", "param": {"n": 9, "a": 9}}}}
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
    # una sola voce, l'ultima giornata finita: le vecchie non si accumulano («la giornata 6 è finita», «la 7 è finita»...)
    assert [x["giornata"] for x in d] == [8] and d[0]["azione"] == "Ho schierato la consigliata"
    scelte.salva(STAGIONE, 8, list(range(1, 12)), "4-4-2", mondo.ctx.scelte, tipo="consigliata")
    assert [x["giornata"] for x in vai(mondo) if x["tipo"] == "diario"] == []      # la 7 non torna fuori


def test_diario_una_voce_anche_con_tante_giornate_finite(mondo):
    for g in (5, 6, 7, 8, 9):
        mondo.db.execute("INSERT INTO partite VALUES (?, ?, '2026-10-20 18:00', 1)", (STAGIONE, g))
    assert [x["giornata"] for x in vai(mondo) if x["tipo"] == "diario"] == [9]


def test_diario_solo_giornate_chiuse_dopo_la_nascita_dell_account(mondo):
    """Un amico appena entrato non ha mai avuto una consigliata da schierare: niente domande sulle giornate chiuse prima di lui."""
    mondo.db.execute("INSERT INTO partite VALUES (?, 7, '2026-10-20 18:00', 1)", (STAGIONE,))
    mondo.db.execute("INSERT INTO partite VALUES (?, 8, '2026-10-27 18:00', 1)", (STAGIONE,))
    mondo.db.execute("INSERT INTO partite VALUES (?, 8, '2026-10-28 20:45', 1)", (STAGIONE,))
    regole = NS(prima_giornata_lega=1, scadenza_minuti=10)

    def diario(dal):
        return [x["giornata"] for x in da_fare.costruisci(mondo.db, regole, mondo.rose, mondo.oggi, mondo.ctx, adesso=ADESSO, dal=dal)
                if x["tipo"] == "diario"]
    assert diario(None) == [8]                                            # senza account (o data ignota): come sempre
    assert diario(datetime(2026, 10, 1)) == [8]                           # account vecchio
    assert diario(datetime(2026, 10, 24)) == [8]                          # nato tra la 7 e la 8
    assert diario(datetime(2026, 10, 27, 17, 50)) == []                   # alla scadenza della 8 (10 minuti prima): già chiusa
    assert diario(datetime(2026, 10, 27, 17, 49)) == [8]                  # un minuto prima: poteva ancora schierarla
    assert diario(ADESSO) == []                                           # entrato oggi


def test_ora_locale_della_nascita_dell_account():
    assert server._ora_locale(None) is None and server._ora_locale("non una data") is None
    assert server._ora_locale("2026-11-02T08:43:45") == datetime(2026, 11, 2, 8, 43, 45)
    d = server._ora_locale("2026-11-02T08:43:45+00:00")
    assert d.tzinfo is None and d == datetime(2026, 11, 2, 8, 43, 45, tzinfo=__import__("datetime").timezone.utc).astimezone().replace(tzinfo=None)


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


def test_primo_avvio_passo_dei_tempi_della_lega(client):
    """Il passo «tempi» (scadenza e prima giornata) del web: il server lo conosce e lo ricorda."""
    assert "tempi" in client.get("/api/primo-avvio").json()["passi"]
    r = client.put("/api/primo-avvio", json={"fatti": ["rose", "squadra", "tempi"]}).json()["primo_avvio"]
    assert r["fatti"] == ["rose", "squadra", "tempi"]


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
    dubbio = next(x for x in voci if x["id"] == "dubbio:5")                 # la consigliata lo tiene: chi entra se non gioca
    assert dubbio["frase"] == {"chiave": "dafare.dubbio_incerto_tiene", "param": {"nome": "Rossi", "p": 55, "riserva": "Riserva"}}
    formazione = next(x for x in voci if x["tipo"] == "formazione")
    assert formazione["frase"]["param"]["tempo"] == {"chiave": "tempo.ore", "param": {"n": 2}}
    la_consigliata_cambia(mondo, (6, 14), (5, 12))                          # la consigliata li cambia: si propone il cambio
    voci = vai(mondo)
    dubbio = next(x for x in voci if x["id"] == "dubbio:5")
    assert dubbio["frase"] == {"chiave": "dafare.dubbio_incerto_alt", "param": {"nome": "Rossi", "p": 55, "alt": "Riserva"}}      # il 14 va all'infortunato
    for x in voci:
        assert frasi.da_json(x["frase"]) == x["testo"] and frasi.da_json(x["azione_frase"]) == x["azione"], x["id"]


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
