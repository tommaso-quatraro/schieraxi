"""Avvisi sul telefono: cambi delle probabili e promemoria prima della scadenza."""
import json
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import consigli, lega, notifiche
from fanta.regole import Regole

ST = "2026-27"


def _stato(nome, stato, perc=None, dubbio=False):
    return {"nome": nome, "stato": stato, "perc": perc, "dubbio": dubbio}


def test_confronta_segnala_solo_cio_che_conta():
    prima = {"1": _stato("Castro", "titolare", 80), "2": _stato("Bonny", "panchina", 40), "3": _stato("Atta", "infortunato"),
             "4": _stato("Vicario", "titolare", 90), "5": _stato("Rowe", "titolare", 85), "6": _stato("Maldini", "titolare", 70),
             "7": _stato("Politano", "titolare", 80), "8": _stato("Kaiki", "titolare", 80)}
    dopo = {"1": _stato("Castro", "panchina", 40), "2": _stato("Bonny", "titolare", 80), "3": _stato("Atta", "titolare", 60),
            "4": _stato("Vicario", "infortunato"), "5": _stato("Rowe", "titolare", 50), "6": _stato("Maldini", "titolare", 75),
            "7": _stato("Politano", "titolare", 80, dubbio=True), "8": _stato("Kaiki", "non_citato")}
    righe = notifiche.confronta(prima, dopo)
    testo = "\n".join(righe)
    assert "Castro: dalla formazione titolare alla panchina" in testo
    assert "Bonny: ora titolare" in testo
    assert "Atta: torna disponibile" in testo
    assert "Vicario: ora infortunato" in testo
    assert "Rowe: ora in ballottaggio per partire titolare" in testo           # 85 -> 50: sotto la soglia, a parole
    assert "Politano: ora in dubbio" in testo
    assert "Kaiki: non è più tra i convocati previsti" in testo
    assert "Maldini" not in testo                         # +5 punti percentuali: non vale un avviso
    assert "%" not in testo                               # all'utente una sola percentuale, «gioca N%»: mai quella delle probabili
    risalita = notifiche.confronta({"1": _stato("Rowe", "titolare", 50)}, {"1": _stato("Rowe", "titolare", 85)})
    assert risalita == ["Rowe: ora probabile titolare"]
    assert notifiche.confronta({"1": _stato("Rowe", "titolare", 95)}, {"1": _stato("Rowe", "titolare", 65)}) == []   # resta sopra: niente
    assert notifiche.confronta({}, dopo) == []             # senza stato precedente non c'è niente da confrontare


def _db(data_prima_partita):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, data_prima_partita, 0), (ST, 9, "2026-10-29 20:45", 0)])
    return db


def _finto(monkeypatch, titolari=("Castro",), dubbi=()):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [{"id": i + 1, "nome": n, "titolarita": "ballottaggio" if n in dubbi else "titolare",
                                                                  "dubbio": False} for i, n in enumerate(titolari)]})


ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10)])], "Mia")


def test_promemoria_un_ora_e_un_quarto_d_ora_una_volta_sola(tmp_path, monkeypatch):
    _finto(monkeypatch, titolari=("Castro", "Bonny"), dubbi=("Castro",))
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo, priorita)) or True    # noqa: E731
    f, db = tmp_path / "n.json", _db("2026-10-28 18:30")
    opz = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 12, 0), f, manda, opz) == []        # troppo presto
    assert len(notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 35), f, manda, opz)) == 1  # 55 minuti
    assert "4-3-3" in mandati[0][1] and "Castro" in mandati[0][1] and "18:30" in mandati[0][1]
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 17, 45), f, manda, opz) == []      # già mandato
    assert len(notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 18, 20), f, manda, opz)) == 1  # 10 minuti
    assert mandati[1][2] == 4                                                                                  # priorità alta
    assert notifiche.promemoria(db, Regole(), ROSE, datetime(2026, 10, 28, 18, 40), f, manda, opz) == []      # formazione già chiusa


ROSE_DUE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10), lega.GiocatoreRosa(2, "Bonny", "A", "PAR", 8)])], "Mia")


def _consigliata_che_toglie_chi_non_gioca(monkeypatch, prev, impossibile=False):
    """La consigliata finta: Castro se gioca, altrimenti Bonny (con `impossibile` nessuna squadra senza Castro)."""
    def formazione(*a, **k):
        if prev.at[1, "stato"] in notifiche.MOTIVI_FUORI:
            if impossibile:
                raise ValueError("nessun attaccante disponibile")
            return {"modulo": "4-3-3", "punteggio_atteso": 70.0, "titolari": [{"id": 2, "nome": "Bonny"}]}
        return {"modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [{"id": 1, "nome": "Castro"}]}
    monkeypatch.setattr(consigli, "formazione", formazione)


def _due(monkeypatch):
    _finto(monkeypatch)
    prev = pd.DataFrame([{"nome": "Castro", "stato": "titolare", "percentuale": 80.0, "dubbio": False},
                         {"nome": "Bonny", "stato": "titolare", "percentuale": 70.0, "dubbio": False}], index=[1, 2])
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    return prev


def test_cambi_la_prima_volta_non_avvisa_poi_si(tmp_path, monkeypatch):
    """Il primo controllo ricorda la consigliata; l'avviso parte quando la cambia un titolare che non gioca più (#676)."""
    prev = _due(monkeypatch)
    _consigliata_che_toglie_chi_non_gioca(monkeypatch, prev)
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append(testo) or True    # noqa: E731
    f, db, adesso = tmp_path / "n.json", _db("2026-10-28 18:30"), datetime(2026, 10, 27, 9, 0)
    assert notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda) == [] and mandati == []         # primo controllo: solo memorizza
    assert notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda) == [] and mandati == []         # nessun cambio
    prev.loc[1, ["stato", "percentuale"]] = ["panchina", 30.0]
    righe = notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda)
    assert righe and righe[0].startswith("Castro parte dalla panchina: metti Bonny.") and len(mandati) == 1
    assert notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda) == [] and len(mandati) == 1     # già comunicato
    assert notifiche.cambi(db, Regole(), ROSE_DUE, datetime(2026, 10, 28, 19, 0), f, manda) == []    # giornata già iniziata


def test_impostazioni_e_stato_rovinato(tmp_path):
    f = tmp_path / "i.json"
    assert notifiche.impostazioni(f) == {"cambi": True, "promemoria_60": True, "promemoria_15": True, "riepilogo": True, "app_nativa": False,
                                         "silenzio": False, "copertura": True, "silenzio_da": 23, "silenzio_a": 7, "avviso_prima": 60,
                                         "lingua": "it"}
    assert notifiche.salva_impostazioni({"cambi": False}, f)["cambi"] is False
    assert notifiche.impostazioni(f)["promemoria_60"] is True
    f.write_text("rotto", encoding="utf-8")
    assert notifiche.impostazioni(f)["cambi"] is True


def test_notifiche_impostazioni_con_numeri_non_finiti_valgono_quelle_predefinite(tmp_path):
    """1e999 nel JSON diventa un numero infinito: le ore e i minuti tornano ai valori di base, e si può salvare sopra."""
    f = tmp_path / "i.json"
    f.write_text('{"silenzio": true, "silenzio_da": 1e999, "silenzio_a": -1e999, "avviso_prima": 1e999}', encoding="utf-8")
    opz = notifiche.impostazioni(f)
    assert (opz["silenzio_da"], opz["silenzio_a"], opz["avviso_prima"]) == (23, 7, 60)
    assert notifiche.ore_tranquille_spente(f) is False
    assert notifiche.salva_impostazioni({"cambi": False}, f)["silenzio_da"] == 23


def test_se_l_invio_fallisce_si_riprova_al_giro_dopo(tmp_path, monkeypatch):
    _finto(monkeypatch)
    esito = {"ok": False}
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append(testo) or esito["ok"]    # noqa: E731
    opz = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
    f, db = tmp_path / "p.json", _db("2026-10-28 18:30")
    adesso = datetime(2026, 10, 28, 17, 35)
    assert notifiche.promemoria(db, Regole(), ROSE, adesso, f, manda, opz) == []
    esito["ok"] = True
    assert len(notifiche.promemoria(db, Regole(), ROSE, adesso, f, manda, opz)) == 1 and len(mandati) == 2

    prev = _due(monkeypatch)
    _consigliata_che_toglie_chi_non_gioca(monkeypatch, prev)
    c, presto = tmp_path / "c.json", datetime(2026, 10, 27, 9, 0)
    notifiche.cambi(db, Regole(), ROSE_DUE, presto, c, manda, opz)                  # primo controllo
    prev.loc[1, "stato"] = "infortunato"
    esito["ok"] = False
    assert notifiche.cambi(db, Regole(), ROSE_DUE, presto, c, manda, opz) == []      # invio fallito
    esito["ok"] = True
    assert notifiche.cambi(db, Regole(), ROSE_DUE, presto, c, manda, opz)            # ritentato: il cambio non è andato perso
    assert notifiche.cambi(db, Regole(), ROSE_DUE, presto, c, manda, opz) == []      # ora è comunicato


def test_cambi_senza_formazione_possibile_avvisa_lo_stesso(tmp_path, monkeypatch):
    prev = _due(monkeypatch)
    _consigliata_che_toglie_chi_non_gioca(monkeypatch, prev, impossibile=True)
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append(testo) or True    # noqa: E731
    f, db, adesso = tmp_path / "c.json", _db("2026-10-28 18:30"), datetime(2026, 10, 27, 9, 0)
    notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda)
    prev.loc[1, "stato"] = "infortunato"
    righe = notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda)
    assert len(righe) == 1 and righe[0].startswith("Castro è infortunato: con la tua rosa non si forma più una squadra.")
    assert len(mandati) == 1


def test_non_torna_disponibile_se_sparisce_dalle_probabili():
    prima = {"1": _stato("Atta", "infortunato")}
    assert notifiche.confronta(prima, {"1": _stato("Atta", "non_citato")}) == []


def test_partita_rinviata_con_vecchia_data_non_chiude_la_giornata():
    from fanta import avvisi
    db = _db("2026-10-28 18:30")
    db.execute("INSERT INTO partite VALUES (?,?,?,?)", (ST, 9, "2026-09-20 18:00", 0))
    assert avvisi.prima_partita(db, ST, 9) == datetime(2026, 10, 28, 18, 30)


def test_diffidato_e_squalificato_vengono_segnalati():
    prima = {"1": _stato("Politano", "titolare", 85), "2": _stato("Rowe", "titolare", 80)}
    dopo = {"1": {**_stato("Politano", "titolare", 85), "diffidato": True}, "2": _stato("Rowe", "squalificato")}
    righe = notifiche.confronta(prima, dopo)
    assert any("Politano: diffidato" in r for r in righe) and "Rowe: ora squalificato" in righe
    assert notifiche.confronta(dopo, dopo) == []                      # già diffidato: niente di nuovo


def test_riepilogo_a_giornata_finita(tmp_path, monkeypatch):
    from fanta import archivio, scelte
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (1, ?, 8, '2026-10-20 18:00', 'a', 'b', 1)", (ST,))
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (2, ?, 9, '2026-10-28 18:30', 'a', 'b', 0)", (ST,))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    # la prossima giornata (la 9) la calcola davvero prossima_giornata, con l'ora del riepilogo e non con l'orologio vero (#566)
    righe = [("P1", "P"), ("P2", "P")] + [(f"D{i}", "D") for i in range(5)] + [(f"C{i}", "C") for i in range(5)] + [(f"A{i}", "A") for i in range(4)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": 0.9, "mu": 6.5, "mu_voto": 6.0} for n, r in righe], index=range(1, len(righe) + 1))
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, giornata or 9, True))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])], "Mia")
    # voti di 70 giocatori delle due squadre (la giornata è arrivata): i nostri hanno voto 6, l'attaccante A0 (id 13) ha segnato
    for i in range(1, 71):
        ruolo = prev.at[i, "ruolo"] if i in prev.index else "C"
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, gol_subiti, autogol, rig_segnati, rig_sbagliati, "
                   "rig_parati, assist, mvp, ammonizioni, espulsioni, subentrato, sostituito) VALUES (?, 8, ?, 'x', ?, ?, 6.0, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)",
                   (ST, i, "ab"[i % 2], ruolo, 1 if i == 13 else 0))
    titolari = [1, 3, 4, 5, 6, 8, 9, 10, 13, 14, 15]
    scelte.salva(ST, 8, titolari, "4-3-3", tmp_path / "scelte.json")
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo)) or True    # noqa: E731
    adesso = datetime(2026, 10, 21, 8, 0)
    opz = {"riepilogo": True}
    f = tmp_path / "r.json"
    r = notifiche.riepilogo(db, Regole(), rose, adesso, f, manda, opz, tmp_path / "nessun-cambi.json", tmp_path / "scelte.json")
    assert len(r) == 1 and "Giornata 8 · 8ª di Serie A: la tua scelta salvata ha fatto circa" in r[0] and "A0 " in r[0]
    assert "Prossima: Giornata 9 · 9ª di Serie A. La formazione si chiude" in r[0]
    assert mandati[0][0] == "SchieraXI · riepilogo della giornata"
    assert notifiche.riepilogo(db, Regole(), rose, adesso, f, manda, opz, tmp_path / "nessun-cambi.json", tmp_path / "scelte.json") == []   # una volta sola
    assert len(mandati) == 1
    # senza sapere cosa avevi schierato non si manda niente; e se l'opzione è spenta nemmeno
    (tmp_path / "scelte.json").unlink()
    assert notifiche.riepilogo(db, Regole(), rose, adesso, tmp_path / "r2.json", manda, opz, tmp_path / "nessun-cambi.json", tmp_path / "scelte.json") == []
    scelte.salva(ST, 8, titolari, "4-3-3", tmp_path / "scelte.json")
    assert notifiche.riepilogo(db, Regole(), rose, adesso, tmp_path / "r3.json", manda, {"riepilogo": False}, tmp_path / "nessun-cambi.json", tmp_path / "scelte.json") == []
    assert notifiche.riepilogo(db, Regole(), rose, datetime(2026, 11, 20), tmp_path / "r4.json", manda, opz, tmp_path / "nessun-cambi.json", tmp_path / "scelte.json") == []   # troppo tardi


def _regole_modificatore() -> Regole:
    r = Regole()
    r.modificatore_difesa.attivo, r.modificatore_difesa.min_difensori = True, 4
    r.modificatore_difesa.soglie = [[6.0, 1.0], [6.5, 3.0], [7.0, 6.0]]
    return r


def _regole_ufficio() -> Regole:
    from fanta.regole import imposta
    r = imposta(Regole(), "panchina.max_sostituzioni", "0")
    r.voto_senza_sostituto = 6.0
    return r


@pytest.mark.parametrize("regole, voto, senza_voto, massimo", [
    # modificatore della difesa (portiere 7 con l'imbattibilità, attaccante 13 9 con il gol, gli altri 6): la tua 3-4-3 fa 70,
    # niente modificatore con tre difensori; il massimo è una difesa a quattro con il +1, 71. Senza le regole della lega sarebbe 70
    (_regole_modificatore(), 6.0, (), "71,0"),
    # voto d'ufficio 6 a chi non ha voto né sostituto: i tuoi due attaccanti senza voto valgono più di quelli con il 5 e la tua fa
    # 61; il conto del massimo con chi ha preso voto dà 59, ma il massimo non sta sotto quello che hai fatto
    (_regole_ufficio(), 5.0, (14, 15), "61,0"),
])
def test_riepilogo_il_massimo_con_le_regole_della_lega_e_mai_sotto_i_tuoi_punti(tmp_path, monkeypatch, regole, voto, senza_voto, massimo):
    from fanta import archivio, scelte
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (1, ?, 8, '2026-10-20 18:00', 'a', 'b', 1)", (ST,))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    righe = [("P1", "P"), ("P2", "P")] + [(f"D{i}", "D") for i in range(5)] + [(f"C{i}", "C") for i in range(5)] + [(f"A{i}", "A") for i in range(4)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": 0.9, "mu": 6.5, "mu_voto": 6.0} for n, r in righe], index=range(1, len(righe) + 1))
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, giornata or 9, True))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])], "Mia")
    for i in (i for i in range(1, 71) if i not in senza_voto):       # l'attaccante 13 segna: fantavoto voto + 3
        ruolo = prev.at[i, "ruolo"] if i in prev.index else "C"
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, gol_subiti, autogol, rig_segnati, rig_sbagliati, "
                   "rig_parati, assist, mvp, ammonizioni, espulsioni, subentrato, sostituito) VALUES (?, 8, ?, 'x', ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)",
                   (ST, i, "ab"[i % 2], ruolo, voto, 1 if i == 13 else 0))         # voti delle due squadre che hanno giocato
    scelte.salva(ST, 8, [1, 3, 4, 5, 8, 9, 10, 11, 13, 14, 15], "3-4-3", tmp_path / "scelte.json")
    manda = lambda titolo, testo, priorita=3, tag="x": True    # noqa: E731
    r = notifiche.riepilogo(db, regole, rose, datetime(2026, 10, 21, 8, 0), tmp_path / "r.json", manda, {"riepilogo": True},
                            tmp_path / "nessun-cambi.json", tmp_path / "scelte.json")
    assert len(r) == 1 and f"Il massimo possibile con la tua rosa era {massimo}." in r[0]


def test_gli_osservati_si_aggiungono_una_volta_e_si_tolgono(tmp_path):
    """(I giocatori seguiti non mandano più avvisi, #676: restano l'elenco e le sue regole.)"""
    from fanta import osservati
    fo = tmp_path / "oss.json"
    assert osservati.aggiungi(77, fo) == [77] and osservati.aggiungi(77, fo) == [77] and osservati.leggi(fo) == [77]
    assert osservati.togli(77, fo) == [] and osservati.leggi(tmp_path / "non-esiste.json") == []


def test_notifiche_web_chiavi_iscrizioni_e_invio(tmp_path, monkeypatch):
    from fanta import push
    k = push.chiavi(tmp_path / "v.json")
    assert k == push.chiavi(tmp_path / "v.json") and k["pubblica"].startswith("B") and len(k["pubblica"]) == 87        # la stessa a ogni richiesta
    f = tmp_path / "p.json"
    sub = {"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}
    assert push.iscrivi(sub, f) == [sub] and push.iscrivi(sub, f) == [sub]                                             # niente doppioni
    with pytest.raises(ValueError):
        push.iscrivi({"endpoint": "http://non-sicuro", "keys": {"p256dh": "x", "auth": "y"}}, f)
    mandate = []

    class Risposta:
        status_code = 410

    class Scaduta(Exception):
        response = Risposta()

    corpi = []

    monkeypatch.setattr(push, "_risolvi_host", lambda host: ["93.184.216.34"])

    def finto(subscription_info, data, vapid_private_key, vapid_claims, ttl, headers, timeout, requests_session=None):
        mandate.append((subscription_info["endpoint"], json.loads(data)["title"], headers["Urgency"], vapid_claims["sub"]))
        corpi.append(json.loads(data))
    monkeypatch.setattr("pywebpush.webpush", finto)
    assert push.invia("Titolo", "Testo", 4, percorso=f, file_chiavi=tmp_path / "v.json") == 1
    assert mandate == [("https://web.push.apple.com/abc", "Titolo", "high", push.CONTATTO)]
    # il service worker della web (fanta/web/sw.js) usa title/body/tag/url (il tag è diverso per ogni avviso, #652:
    # tests/test_notifiche_web_tag_durata.py); `sezione` e `priorita` viaggiano nel messaggio
    assert {k: v for k, v in corpi[0].items() if k != "tag"} == {"title": "Titolo", "body": "Testo", "url": "/", "sezione": "lega",
                                                                 "priorita": 4}
    assert push.invia("Cambi", "x", 4, "rotating_light", percorso=f, file_chiavi=tmp_path / "v.json") == 1
    assert corpi[1]["sezione"] == "formazione"
    assert corpi[1]["url"] == "/?vista=formazione"                       # il tocco sulla notifica web apre la Formazione
    import pywebpush

    def scaduto(**k):
        raise pywebpush.WebPushException("gone", response=Risposta())
    monkeypatch.setattr("pywebpush.webpush", lambda **k: scaduto(**k))
    assert push.invia("T", "x", percorso=f, file_chiavi=tmp_path / "v.json") == 0 and push.iscrizioni(f) == []         # iscrizione scaduta: tolta
    assert push.invia("T", "x", percorso=f, file_chiavi=tmp_path / "v.json") == 0                                      # nessun dispositivo: niente


def test_invia_usa_le_notifiche_web_e_poi_ntfy(monkeypatch):
    from fanta import push
    chiamate = []
    monkeypatch.setattr(push, "iscrizioni", lambda *a: [{"endpoint": "x"}])
    monkeypatch.setattr(push, "invia", lambda *a, **k: chiamate.append("web") or 1)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a: chiamate.append("ntfy") or True)
    assert notifiche.invia("t", "x") is True and chiamate == ["web"]
    chiamate.clear()
    monkeypatch.setattr(push, "invia", lambda *a, **k: chiamate.append("web") or 0)           # a nessuno è arrivata: ripiega su ntfy
    assert notifiche.invia("t", "x") is True and chiamate == ["web", "ntfy"]


def test_con_l_app_nativa_l_avviso_va_anche_su_ntfy_e_il_tocco_apre_l_app(monkeypatch, tmp_path):
    from fanta import push
    monkeypatch.setattr(notifiche, "FILE_IMPOSTAZIONI", tmp_path / "av.json")
    notifiche.salva_impostazioni({"app_nativa": True})
    chiamate = []
    monkeypatch.setattr(push, "iscrizioni", lambda *a: [{"endpoint": "x"}])
    monkeypatch.setattr(push, "invia", lambda *a, **k: chiamate.append("web") or 1)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a: chiamate.append(a[4]) or True)
    assert notifiche.invia("t", "x", 3, "alarm_clock") is True
    assert chiamate == ["web", "schieraxi://formazione"]                      # le web non si tolgono; ntfy in più con il tocco verso l'app
    chiamate.clear()
    notifiche.invia("t", "x", 3, "bar_chart")
    notifiche.invia("t", "x", 3, "warning")
    assert [c for c in chiamate if c != "web"] == ["schieraxi://oggi", "schieraxi://lega"]


def test_osservato_lasciato_libero_avvisa(tmp_path):
    from fanta import osservati
    f = tmp_path / "oss.json"
    osservati.aggiungi(7, f)
    diff = {"tagliati": [{"squadra": "Real Esempio", "giocatori": [{"id": 7, "nome": "Bonny", "ruolo": "A"}, {"id": 9, "nome": "Altro", "ruolo": "D"}]}]}
    mandati = []
    righe = notifiche.osservati_liberi(diff, f, lambda t, x, p=3, tag="x": mandati.append((t, x, tag)) or True, {"cambi": True})
    assert righe == ["Bonny (A): lasciato libero da Real Esempio"]                       # solo l'osservato, non l'altro
    assert mandati[0][2] == "unlock" and "Altro" not in mandati[0][1]
    assert notifiche.osservati_liberi(diff, f, lambda *a: True, {"cambi": False}) == []   # avvisi sui cambi spenti
    assert notifiche.osservati_liberi({"tagliati": []}, f, lambda *a: True, {"cambi": True}) == []


def test_ntfy_manda_il_collegamento_solo_se_richiesto(monkeypatch):
    inviati = []

    class Risposta:
        ok = True

    monkeypatch.setattr(notifiche, "canale", lambda: "canale-prova")
    monkeypatch.setattr(notifiche.requests, "post", lambda url, json=None, timeout=0: inviati.append(json) or Risposta())
    notifiche._invia_ntfy("t", "x", 3, "soccer")
    notifiche._invia_ntfy("t", "x", 3, "soccer", "schieraxi://oggi")
    assert "click" not in inviati[0] and inviati[1]["click"] == "schieraxi://oggi"


def test_le_giornate_a_due_cifre_non_vengono_cancellate():
    from fanta.percorsi import chiavi_vecchie
    chiavi = [f"2026-27/{g}" for g in (5, 6, 7, 8, 9, 10)]
    assert chiavi_vecchie(chiavi, 6) == []                               # sei giornate: si tengono tutte
    assert chiavi_vecchie(chiavi + ["2026-27/11"], 6) == ["2026-27/5"]    # la più vecchia è la 5, non la 10
    assert chiavi_vecchie(["2025-26/38", "2026-27/1"], 1) == ["2025-26/38"]


def test_salute_avvisa_se_molti_passi_dell_aggiornamento_falliscono(tmp_path):
    from fanta import archivio, salute
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO aggiornamenti (cosa, quando, dettaglio) VALUES ('aggiornamento', ?, ?)", ("2026-10-28T08:00:00", json.dumps(["a", "b", "c"])))
    mandati = []
    p = salute.controlla(db, datetime(2026, 10, 28, 9, 0), tmp_path / "s.json", lambda t, x, pr=3, tag="x": mandati.append(x) or True, lambda: True)
    assert len(p) == 1 and "3 errori" in p[0] and len(mandati) == 1


def test_il_contatto_e_accettato_dalla_firma_vapid(tmp_path):
    """La libreria rifiuta un contatto che non sia un mailto: (e la notifica web falliva in silenzio): qui si firma davvero."""
    from py_vapid import Vapid
    from fanta import push
    v = Vapid.from_raw(push.chiavi(tmp_path / "v.json")["privata"].encode())
    intestazioni = v.sign({"sub": push.CONTATTO, "aud": "https://web.push.apple.com"})
    assert "Authorization" in intestazioni and push.CONTATTO.startswith("mailto:")


def test_ore_tranquille_a_cavallo_della_mezzanotte_e_nello_stesso_giorno():
    notte = {"silenzio": True, "silenzio_da": 23, "silenzio_a": 7}
    ora = lambda h, m=0: datetime(2026, 10, 29, h, m)      # noqa: E731
    assert [notifiche.in_silenzio(ora(h), notte) for h in (22, 23, 0, 6, 7, 12)] == [False, True, True, True, False, False]
    giorno = {"silenzio": True, "silenzio_da": 9, "silenzio_a": 13}
    assert [notifiche.in_silenzio(ora(h), giorno) for h in (8, 9, 12, 13)] == [False, True, True, False]
    assert notifiche.in_silenzio(ora(2), {**notte, "silenzio": False}) is False                 # fascia spenta
    assert notifiche.in_silenzio(ora(2), {"silenzio": True, "silenzio_da": 5, "silenzio_a": 5}) is False     # inizio = fine: niente fascia


def test_ore_tranquille_si_salvano_e_valori_strani_tornano_a_quelli_di_prima(tmp_path):
    f = tmp_path / "i.json"
    o = notifiche.salva_impostazioni({"silenzio": True, "silenzio_da": 22, "silenzio_a": 6}, f)
    assert (o["silenzio"], o["silenzio_da"], o["silenzio_a"]) == (True, 22, 6)
    o = notifiche.salva_impostazioni({"silenzio_da": 99, "silenzio_a": "boh"}, f)
    assert (o["silenzio_da"], o["silenzio_a"]) == (22, 6)
    assert notifiche.salva_impostazioni({"cambi": False}, f)["silenzio_da"] == 22            # chi non le manda non le azzera


def test_nelle_ore_tranquille_non_parte_niente_ma_la_prova_si(monkeypatch, tmp_path):
    from fanta import push
    monkeypatch.setattr(notifiche, "FILE_IMPOSTAZIONI", tmp_path / "av.json")
    monkeypatch.setattr(notifiche, "datetime", type("D", (), {"now": staticmethod(lambda: datetime(2026, 10, 29, 2, 0))}))
    chiamate = []
    monkeypatch.setattr(push, "iscrizioni", lambda *a: [{"endpoint": "x"}])
    monkeypatch.setattr(push, "invia", lambda *a, **k: chiamate.append("web") or 1)
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a: chiamate.append("ntfy") or True)
    notifiche.salva_impostazioni({"silenzio": True})
    assert notifiche.invia("t", "x") is False and chiamate == []                  # le 2 di notte: niente
    assert notifiche.invia("t", "x", ignora_silenzio=True) is True and chiamate == ["web"]
    notifiche.salva_impostazioni({"silenzio": False})
    assert notifiche.invia("t", "x") is True


def test_iscrizione_push_rifiuta_indirizzi_interni_e_forme_strane(tmp_path, monkeypatch):
    from fanta import push
    k = {"p256dh": "P" * 40, "auth": "A" * 20}
    brutti = ("https://127.0.0.1/x", "https://192.168.1.5/x", "https://[::1]/x", "https://localhost/x", "https://pi/x", "https://nas.local/x",
              "https://utente:pw@fcm.googleapis.com/x", "https://fcm.googleapis.com:8443/x", "http://fcm.googleapis.com/x",
              "https://169.254.169.254/x", "https://0x7f.1/x", "https://127.1/x", "https://[::ffff:7f00:1]/x", "https://localhost./x",
              "https://2130706433/x", "https://0177.0.0.1/x", "https://host.123/x", "https://a.b.0x7f/x", "https://miosito.internal/x")
    for ep in brutti:
        with pytest.raises(ValueError):
            push.iscrivi({"endpoint": ep, "keys": k}, tmp_path / "p.json")
        assert not push.indirizzo_consentito(ep), ep
    assert push.iscrivi({"endpoint": "https://ntfy.sh/up123", "keys": k}, tmp_path / "p.json")
    # un nome che porta anche a una rete privata si rifiuta subito, anche se scritto bene
    push._cache_dns.clear()
    monkeypatch.setattr(push, "_risolvi_host", lambda host: ["93.184.216.34", "10.0.0.7"])
    with pytest.raises(ValueError):
        push.iscrivi({"endpoint": "https://misto.example.org/x", "keys": k}, tmp_path / "p2.json")


def test_invia_ignora_iscrizioni_salvate_non_valide_e_logga_senza_segreti(tmp_path, monkeypatch):
    from fanta import push
    monkeypatch.setattr(push, "FILE_ISCRIZIONI", tmp_path / "p.json")
    k = {"p256dh": "P" * 40, "auth": "A" * 20}
    (tmp_path / "p.json").write_text(json.dumps([{"endpoint": "https://nas.local/SEGRETO1", "keys": k},
                                                  {"endpoint": "https://push.example.org/fcm/SEGRETO2", "keys": k}]), encoding="utf-8")
    chiamate = []

    def rete_rotta(**kw):
        chiamate.append(kw)
        raise ConnectionError("Max retries exceeded with url: /fcm/SEGRETO2 (Caused by NewConnectionError)")
    monkeypatch.setattr("pywebpush.webpush", rete_rotta)
    assert push.invia("T", "x", percorso=tmp_path / "p.json", file_chiavi=tmp_path / "v.json") == 0
    assert len(chiamate) == 1                                          # quella interna non e' stata nemmeno tentata
    log = (tmp_path / "push.log").read_text(encoding="utf-8")
    assert "SEGRETO" not in log and "ignorata" in log and "ConnectionError" in log and "push.example.org" in log
    assert len(push.iscrizioni(tmp_path / "p.json")) == 2              # niente cancellato


def test_rebinding_la_connessione_usa_l_indirizzo_gia_controllato(monkeypatch):
    from fanta import push, scarica_immagine
    risposte = iter([["93.184.216.34"], ["10.0.0.7"], ["10.0.0.7"]])
    chiamate = []

    def risolvi(host):
        chiamate.append(host)
        return next(risposte)
    monkeypatch.setattr(push, "_risolvi_host", risolvi)
    ep = "https://push.example.org/fcm/abc"
    assert push.indirizzo_consentito(ep)                              # 1a risoluzione: pubblica

    class Risp:
        status, headers = 201, {}

        def read(self, n):
            return b""

    visti = []

    class Conn:
        def __init__(self, host, ip, porta, timeout):
            visti.append((host, ip, porta))

        def request(self, *a, **k):
            pass

        def getresponse(self):
            return Risp()

        def close(self):
            pass
    monkeypatch.setattr(scarica_immagine, "_Connessione", Conn)
    r = push.SessioneFissata().post(ep, data=b"x", headers={}, timeout=5)
    assert r.status_code == 201 and r.ok
    assert visti == [("push.example.org", "93.184.216.34", 443)] and len(chiamate) == 1       # niente seconda risoluzione
    push._cache_dns.clear()                                            # scaduta la memoria: la nuova risoluzione e' privata
    with pytest.raises(ValueError):
        push.SessioneFissata().post(ep, data=b"x", headers={}, timeout=5)
    assert len(visti) == 1                                             # e non ci si collega


