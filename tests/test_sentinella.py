"""La sentinella (fanta/sentinella.py): rifà in sola lettura le risposte dell'app per ogni utente e controlla le invarianti.

Un «mondo» coerente (giornata 10 della stagione 2026-27, come le date vere del 31/10-2/11/2026) non deve rompere niente; ogni prova
poi guasta una cosa sola e controlla che si rompa l'invariante giusta. In fondo: avvisi una volta sola, tabella `controlli`,
copia su file dei risultati in diretta e il giro completo con gli account."""
import copy
import json
import math
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

import numpy as np
import pytest

from fanta import archivio, consigli, controlli, lega, live, regole, sentinella
from fanta.sentinella import Rottura

ST = "2026-27"
PRIMA = datetime(2026, 10, 30, 12, 0)          # venerdì: la formazione si chiude sabato alle 15
G9 = [("2026-10-24 15:00", "a", "b"), ("2026-10-24 18:00", "c", "d"), ("2026-10-24 20:45", "e", "f"), ("2026-10-25 12:30", "g", "h"),
      ("2026-10-25 15:00", "i", "l"), ("2026-10-25 15:00", "m", "n"), ("2026-10-25 18:00", "o", "p"), ("2026-10-25 20:45", "q", "r"),
      ("2026-10-26 18:30", "s", "t"), ("2026-10-26 20:45", "u", "v")]
G10 = [("2026-10-31 15:00", "a", "c"), ("2026-10-31 18:00", "b", "d"), ("2026-10-31 20:45", "e", "g"), ("2026-11-01 12:30", "f", "h"),
       ("2026-11-01 15:00", "i", "m"), ("2026-11-01 15:00", "l", "n"), ("2026-11-01 18:00", "o", "q"), ("2026-11-01 20:45", "p", "r"),
       ("2026-11-02 18:30", "s", "u"), ("2026-11-02 20:45", "t", "v")]
RUOLI = {i: "P" if i <= 3 else "D" if i <= 11 else "C" if i <= 19 else "A" for i in range(1, 26)}
TIT = [1, 4, 5, 6, 7, 12, 13, 14, 20, 21, 22]            # 4-3-3
PAN = [2, 8, 15, 23]
REGOLE = regole.Regole()
ROSA = set(RUOLI)


def _scheda(i):
    return {"id": i, "nome": f"g{i}", "ruolo": RUOLI[i], "squadra": "a", "punti_attesi": 6.0, "p_voto": 0.9, "fv_atteso": 6.5,
            "percentuale": 90.0, "data_partita": "2026-10-31 15:00", "difficolta": 3, "indice": 50, "stato": "titolare"}


def _mondo():
    intervallo = {"basso": 64.0, "alto": 80.0, "confidenza": 0.8, "indicativo": False}
    modulo = {"modulo": "4-3-3", "punteggio_atteso": 72.4, "intervallo": intervallo, "titolari": list(TIT), "panchina": list(PAN)}
    form = {"squadra": "Mia", "giornata": 10, "giornata_lega": 10, "modulo": "4-3-3", "punteggio_atteso": 72.4, "intervallo": intervallo,
            "titolari": [_scheda(i) for i in TIT], "panchina": [_scheda(i) for i in PAN], "moduli": [copy.deepcopy(modulo)],
            "livelli": [{"stile": -1, "modulo": "4-3-3", "punteggio_atteso": 72.0, "moduli": [modulo | {"punteggio_atteso": 72.0}]},
                        {"stile": 0, "modulo": "4-3-3", "punteggio_atteso": 72.4, "moduli": [copy.deepcopy(modulo)]}],
            "stile_consigliato": 0, "schede": {str(i): _scheda(i) for i in RUOLI}}
    oggi = {"giornata": 10, "giornata_lega": 10, "inizio": "2026-10-31 15:00", "scadenza": "2026-10-31 15:00", "minuti_scadenza": 0,
            "ore_mancanti": 27.0, "iniziata": False, "con_probabili": True, "probabili": None,
            "formazione": {"modulo": "4-3-3", "punteggio_atteso": 72.4, "squadra": "Mia", "dev": 6.4, "intervallo": intervallo,
                           "tua_scelta": False},
            "avvisi": [], "migliori": [_scheda(20)], "miei_titolari": {"a": [{"id": i, "nome": f"g{i}", "ruolo": RUOLI[i]} for i in TIT]},
            "partite": [{"data": d, "casa": c, "trasferta": t, "giocata": False, "stato": "da_giocare"} for d, c, t in G10],
            "fase": "prima", "in_corso": None, "riepilogo": None, "prossima": None}
    wid = {"giornata": 10, "giornata_lega": 10, "prima_partita": "2026-10-31 15:00", "scadenza": "2026-10-31 15:00", "ore_mancanti": 27.0,
           "formazione": {"modulo": "4-3-3", "punti_attesi": 72.4, "intervallo": intervallo,
                          "titolari": [{"id": i, "nome": f"g{i}", "ruolo": RUOLI[i], "punti_attesi": 6.0, "p_voto": 0.9} for i in TIT],
                          "panchina": list(PAN)},
           "rosa": [{"id": i, "nome": f"g{i}", "ruolo": RUOLI[i], "titolare": i in TIT, "percentuale": 90.0} for i in RUOLI],
           "dati": {"ultimo_aggiornamento": "2026-10-30T10:00:00"}}
    diario = {"giornate": [{"stagione": ST, "giornata": 9, "consigliata": {"atteso": 70.0, "reale": 68.0}, "istantanea": None}],
              "precisione": {"gioca": {"gruppi": [{"da": 90, "a": 100, "detto": 95, "giocato": 90}]}}}
    vivo = {"aggiornato_il": None, "fonte": None, "in_corso": 0,
            "partite": [{"casa": c, "trasferta": t, "data": d, "stato": "da_giocare", "minuto": None, "gol_casa": None, "gol_trasferta": None,
                         "eventi": []} for d, c, t in G10]}
    return {"oggi": oggi, "formazione": form, "widget": wid, "diario": diario, "live": vivo}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    d = archivio.apri(tmp_path / "fanta.sqlite")
    righe = [(9, x, True) for x in G9] + [(10, x, False) for x in G10]
    archivio.inserisci(d, "partite", [{"id": n, "stagione": ST, "giornata": g, "data": dt, "casa": c, "trasferta": t,
                                       "gol_casa": 1 if gi else None, "gol_trasferta": 0 if gi else None, "giocata": int(gi),
                                       "understat_id": None} for n, (g, (dt, c, t), gi) in enumerate(righe)])
    squadre = sorted({s for _, c, t in G9 for s in (c, t)})
    archivio.inserisci(d, "voti", [{"stagione": ST, "giornata": 9, "calciatore_id": n, "squadra": s, "voto_red": 6.0}
                                   for n, s in enumerate(squadre)])
    d.commit()
    return d


def _rotte(r, db, adesso=PRIMA, scelta=None):
    return sentinella.controlla_utente("utente 3", r, REGOLE, ROSA, scelta, db, ST, adesso)


def _nomi(rotture):
    return {x.invariante for x in rotture}


def test_un_mondo_coerente_non_rompe_niente(db):
    assert _rotte(_mondo(), db) == []
    assert sentinella.controlla_comuni(db, ST, PRIMA, _mondo()["live"]) == []


def _guasta(percorso, valore):
    def f(r):
        x = r
        for k in percorso[:-1]:
            x = x[k]
        x[percorso[-1]] = valore(x[percorso[-1]]) if callable(valore) else valore
    return f


@pytest.mark.parametrize("guasto, attesa", [
    (_guasta(["widget", "formazione", "punti_attesi"], 70.0), "punti_diversi"),
    (_guasta(["widget", "formazione", "modulo"], "3-4-3"), "punti_diversi"),
    (_guasta(["oggi", "formazione", "punteggio_atteso"], math.nan), "json_non_valido"),
    (_guasta(["formazione", "titolari", 0, "p_voto"], np.int64(1)), "json_non_valido"),
    (_guasta(["formazione", "titolari", 0, "percentuale"], 150.0), "fuori_intervallo"),
    (_guasta(["formazione", "titolari", 0, "p_voto"], 1.2), "fuori_intervallo"),
    (_guasta(["diario", "precisione", "gioca", "gruppi", 0, "giocato"], 140), "fuori_intervallo"),
    (_guasta(["oggi", "formazione", "intervallo"], {"basso": 80.0, "alto": 60.0, "confidenza": 0.8}), "fuori_intervallo"),
    (_guasta(["widget", "scadenza"], "2026-10-31T15:00"), "data_non_valida"),
    (_guasta(["widget", "dati", "ultimo_aggiornamento"], "2026-10-30 10:00+01:00"), "data_non_valida"),
    (_guasta(["formazione", "titolari", 0, "punti_attesi"], None), "numero_mancante"),
    (_guasta(["widget", "formazione", "punti_attesi"], None), "numero_mancante"),
    (_guasta(["formazione", "moduli", 0, "titolari"], TIT[:10] + [TIT[0]]), "formazione_non_valida"),
    (_guasta(["formazione", "moduli", 0, "titolari"], TIT[:-1] + [2]), "formazione_non_valida"),    # due portieri
    (_guasta(["formazione", "moduli", 0, "titolari"], TIT[:-1] + [99]), "formazione_non_valida"),   # uno fuori rosa
    (_guasta(["widget", "formazione", "panchina"], [TIT[0]] + PAN[1:]), "formazione_non_valida"),
    (_guasta(["widget", "rosa", 0, "titolare"], False), "formazione_non_valida"),
    (_guasta(["widget", "giornata"], 11), "giornata_diversa"),
    (_guasta(["formazione", "giornata"], 11), "giornata_diversa"),
    (_guasta(["oggi", "iniziata"], True), "fase_incoerente"),
    (_guasta(["oggi", "fase"], "finita"), "fase_incoerente"),
    (_guasta(["oggi", "ore_mancanti"], 5.0), "fase_incoerente"),
    (_guasta(["oggi", "scadenza"], "2026-10-31 14:00"), "fase_incoerente"),
    (_guasta(["diario", "giornate"], lambda v: v + [{"stagione": ST, "giornata": 10, "consigliata": {"atteso": 70.0}}]), "diario_incoerente"),
    (_guasta(["diario", "giornate"], lambda v: v + copy.deepcopy(v)), "diario_incoerente"),
    (_guasta(["diario", "giornate"], []), "diario_mancante"),
    (_guasta(["widget", "osservati"], [{"nota": "x" * 21000}]), "widget_troppo_grande"),
])
def test_ogni_guasto_rompe_l_invariante_giusta(db, guasto, attesa):
    r = _mondo()
    guasto(r)
    assert attesa in _nomi(_rotte(r, db))


def test_un_altro_portiere_della_rosa_va_bene(db):
    r = _mondo()
    r["formazione"]["moduli"][0]["titolari"] = [3] + TIT[1:]
    assert _rotte(r, db) == []


def test_modulo_non_ammesso_e_ruoli_che_non_tornano(db):
    r = _mondo()
    r["formazione"]["moduli"][0]["titolari"] = [1, 4, 5, 12, 13, 14, 15, 16, 17, 20, 21]     # 2-7-2
    r["formazione"]["moduli"][0]["modulo"] = "2-7-2"
    assert any("non ammesso" in x.dettaglio for x in _rotte(r, db))
    r = _mondo()
    r["formazione"]["modulo"] = "3-4-3"
    r["oggi"]["formazione"]["modulo"] = r["widget"]["formazione"]["modulo"] = "3-4-3"
    assert any("i ruoli dicono 4-3-3" in x.dettaglio for x in _rotte(r, db))


def test_la_scelta_salvata_deve_vedersi_ovunque(db):
    scelta = {"titolari": [1, 4, 5, 6, 9, 12, 13, 14, 20, 21, 22], "modulo": "4-3-3", "tipo": "manuale"}
    r = _mondo()
    assert "scelta_non_mostrata" in _nomi(_rotte(r, db, scelta=scelta))        # Oggi e widget mostrano la consigliata
    r["oggi"]["formazione"]["tua_scelta"] = True
    r["oggi"]["miei_titolari"] = {"a": [{"id": i} for i in scelta["titolari"]]}
    r["oggi"]["migliori"] = []
    r["widget"]["formazione"] |= {"tua_scelta": True, "consigliata": {"modulo": "4-3-3", "punti_attesi": 72.4},
                                  "titolari": [{"id": i, "ruolo": RUOLI[i]} for i in scelta["titolari"]]}
    for x in r["widget"]["rosa"]:
        x["titolare"] = x["id"] in scelta["titolari"]
    assert _rotte(r, db, scelta=scelta) == []
    r["widget"]["formazione"]["consigliata"]["punti_attesi"] = 71.0
    assert _nomi(_rotte(r, db, scelta=scelta)) == {"punti_diversi"}


def test_scelta_che_non_vale_piu_e_solo_un_avviso(db):
    scelta = {"titolari": [99] + TIT[1:], "modulo": "4-3-3"}
    assert _nomi(_rotte(_mondo(), db, scelta=scelta)) == {"scelta_ignorata"}
    assert sentinella.INVARIANTI["scelta_ignorata"][0] == "avviso"


def test_fase_prima_con_una_partita_gia_finita_e_partite_ferme(db):
    r = _mondo()
    r["oggi"]["partite"][0]["stato"] = "finita"
    assert "fase_incoerente" in _nomi(_rotte(r, db))
    sabato_sera = datetime(2026, 10, 31, 18, 0)
    r = _mondo()
    r["oggi"] |= {"iniziata": True, "fase": "in_corso", "ore_mancanti": -3.0, "in_corso": {
        "giornata": 10, "formazione_di": "consigliata", "punti_fatti": 0, "punti_attesi_restanti": 72.4, "punti_previsti": 72.4,
        "giocatori": [{"id": 1, "titolare": True, "stato": "da_giocare", "data": "2026-10-31 15:00"}]}}
    nomi = _nomi(_rotte(r, db, adesso=sabato_sera))
    assert {"stato_partita_incoerente", "giocatore_fermo"} <= nomi        # «da_giocare» 3 ore dopo il calcio d'inizio


def test_oggi_e_live_devono_dire_lo_stesso_stato(db):
    r = _mondo()
    r["live"]["partite"][0]["stato"] = "secondo_tempo"
    assert "stato_partita_incoerente" in _nomi(_rotte(r, db))
    r = _mondo()
    r["oggi"]["partite"][0]["stato"] = "rinviata"                         # recupero: Oggi lo sa dal turno, Live no
    assert "stato_partita_incoerente" not in _nomi(_rotte(r, db))


def test_in_corso_numeri_e_formazione_schierata(db):
    sabato_sera = datetime(2026, 10, 31, 16, 0)
    r = _mondo()
    r["oggi"] |= {"iniziata": True, "fase": "in_corso", "ore_mancanti": -1.0}
    r["oggi"]["partite"][0]["stato"] = "in_corso"
    r["live"]["partite"][0]["stato"] = "primo_tempo"
    assert _nomi(_rotte(r, db, adesso=sabato_sera)) == {"fase_incoerente"}              # manca il blocco in_corso
    r["oggi"]["in_corso"] = {"giornata": 10, "formazione_di": "consigliata", "punti_fatti": 6.0, "punti_attesi_restanti": 60.0,
                             "punti_previsti": 70.0, "giocatori": []}
    assert _nomi(_rotte(r, db, adesso=sabato_sera)) == {"punti_diversi"}                # 6 + 60 non fa 70
    r["oggi"]["in_corso"]["punti_previsti"] = 66.0
    assert _rotte(r, db, adesso=sabato_sera) == []


# ---------------------------------------------------------------- comuni
def test_partita_iniziata_da_tre_ore_senza_punteggio(db):
    sera = datetime(2026, 10, 31, 18, 5)
    vivo = _mondo()["live"]
    nomi = _nomi(sentinella.controlla_comuni(db, ST, sera, vivo))
    assert {"punteggio_mancante", "stato_partita_incoerente"} <= nomi
    vivo["partite"][0] |= {"stato": "finita", "gol_casa": 2, "gol_trasferta": 1}
    assert sentinella.controlla_comuni(db, ST, sera, vivo) == []
    vivo["partite"][0]["stato"] = "secondo_tempo"                       # «in gioco» 4 ore dopo: il raccoglitore l'ha persa
    assert "stato_partita_incoerente" in _nomi(sentinella.controlla_comuni(db, ST, datetime(2026, 10, 31, 19, 10), vivo))


def test_risultati_e_voti_che_non_arrivano(db):
    martedi = datetime(2026, 11, 3, 12, 0)
    nomi = _nomi(sentinella.controlla_comuni(db, ST, martedi, None))
    assert "risultati_fermi" in nomi                                    # g10 finita da più di 12 ore, non «giocata»
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata = 10")
    rr = sentinella.controlla_comuni(db, ST, martedi, None)
    assert "risultati_fermi" not in _nomi(rr)
    voti = [x for x in rr if x.invariante == "voti_mancanti"]
    assert voti and voti[0].giornata == 10 and "squadre senza voti" in voti[0].dettaglio


def test_giornata_che_salta_avanti(db, monkeypatch):
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, stagione, adesso=None: 10)
    giovedi_prima = datetime(2026, 10, 24, 10, 0)                       # la 9 non è ancora cominciata
    db.execute("UPDATE partite SET giocata = 0, gol_casa = NULL, gol_trasferta = NULL WHERE giornata = 9")
    assert "giornata_incoerente" in _nomi(sentinella.controlla_comuni(db, ST, giovedi_prima, None))


# ---------------------------------------------------------------- avvisi: una volta sola, niente nomi
def _esito(*rotture, controllati=("utente 3",)):
    return {"rotture": list(rotture), "controllati": list(controllati), "rimandati": 0, "secondi": 1.0, "stagione": ST}


def test_si_avvisa_alla_seconda_volta_e_poi_mai_piu():
    r = Rottura("punti_diversi", "utente 3", 10, "widget 70.0 contro oggi 72.4")
    stato, ora = {}, PRIMA
    stato, da = sentinella.aggiorna_stato(stato, _esito(r), ora)
    assert da == []                                                      # una sola volta: potrebbe essere un aggiornamento a metà
    stato, da = sentinella.aggiorna_stato(stato, _esito(r), ora + timedelta(hours=1))
    assert da == [r]
    sentinella.segna_avvisate(stato, da)
    for h in range(2, 6):
        stato, da = sentinella.aggiorna_stato(stato, _esito(r), ora + timedelta(hours=h))
        assert da == []
    # torna a posto e si rompe di nuovo dopo poco: niente raffica
    stato, _ = sentinella.aggiorna_stato(stato, _esito(), ora + timedelta(hours=6))
    for h in (7, 8):
        stato, da = sentinella.aggiorna_stato(stato, _esito(r), ora + timedelta(hours=h))
        assert da == []
    # a posto per più di un giorno: la prossima rottura è di nuovo «la prima volta»
    stato, _ = sentinella.aggiorna_stato(stato, _esito(), ora + timedelta(hours=9))
    stato, _ = sentinella.aggiorna_stato(stato, _esito(), ora + timedelta(hours=40))
    assert stato["aperte"] == {}
    stato, _ = sentinella.aggiorna_stato(stato, _esito(r), ora + timedelta(hours=41))
    stato, da = sentinella.aggiorna_stato(stato, _esito(r), ora + timedelta(hours=42))
    assert da == [r]


def test_chi_non_e_stato_controllato_non_conta_come_a_posto():
    r = Rottura("scelta_non_mostrata", "utente 7", 10, "x")
    stato, _ = sentinella.aggiorna_stato({}, _esito(r, controllati=["utente 7"]), PRIMA)
    stato, _ = sentinella.aggiorna_stato(stato, _esito(controllati=["utente 3"]), PRIMA + timedelta(hours=1))   # 7 rimandato
    assert stato["aperte"]["scelta_non_mostrata|utente 7|10"]["volte"] == 1
    stato, da = sentinella.aggiorna_stato(stato, _esito(r, controllati=["utente 7"]), PRIMA + timedelta(hours=2))
    assert da == [r]


def test_il_testo_dell_avviso_non_ha_nomi_ne_dettagli():
    rr = [Rottura("punti_diversi", f"utente {i}", 10, "Mia Squadra di Mario: Lautaro 6.5") for i in range(1, 6)] + \
         [Rottura("punteggio_mancante", None, 10, "inter-milan senza punteggio")] + \
         [Rottura(k, "utente 1", 10, "segreto") for k in list(sentinella.INVARIANTI)[:8]]
    titolo, testo = sentinella.testo_avviso(rr)
    assert "SchieraXI" in titolo
    for vietato in ("Mia", "Mario", "Lautaro", "milan", "segreto", "6.5"):
        assert vietato not in testo
    assert "punti_diversi · giornata 10 · utente 1, utente 2, utente 3 e altri 2" in sentinella.testo_avviso(rr[:5])[1]
    assert len(testo.splitlines()) <= 1 + sentinella.MAX_RIGHE_AVVISO


def test_giro_manda_un_solo_messaggio_e_se_l_invio_fallisce_riprova(tmp_path, monkeypatch):
    r = Rottura("risposta_in_errore", "utente 2", 10, "widget: KeyError")
    monkeypatch.setattr(sentinella, "esegui", lambda db, adesso, minuti, stato: _esito(r, controllati=["utente 2"]))
    mandati, riesce = [], [False]

    def manda(titolo, testo):
        mandati.append(testo)
        return riesce[0]
    stato = tmp_path / "sentinella.json"
    giro = lambda h: sentinella.giro(manda=manda, file_stato=stato, adesso=PRIMA + timedelta(hours=h), scrivi=lambda s: None,
                                     db_percorso=tmp_path / "fanta.sqlite")
    giro(0)
    assert mandati == []
    giro(1)
    assert len(mandati) == 1                                    # tentato, ma la rete non c'era
    riesce[0] = True
    giro(2)
    assert len(mandati) == 2                                    # riprovato e riuscito
    giro(3)
    assert len(mandati) == 2
    assert "utente 2" in mandati[-1] and "KeyError" not in mandati[-1]
    # senza invio (prova a mano): niente messaggi e il file di stato non cambia
    prima = stato.read_text(encoding="utf-8")
    sentinella.giro(manda=None, file_stato=stato, adesso=PRIMA + timedelta(hours=4), scrivi=lambda s: None,
                    db_percorso=tmp_path / "fanta.sqlite")
    assert stato.read_text(encoding="utf-8") == prima


def test_canale_dal_file_come_gli_script(tmp_path, monkeypatch):
    f = tmp_path / "canale"
    f.write_text(" segreto-123 \n", encoding="utf-8")
    monkeypatch.setenv("SCHIERAXI_CANALE", str(f))
    assert sentinella.canale() == "segreto-123"
    monkeypatch.setenv("SCHIERAXI_CANALE", str(tmp_path / "manca"))
    assert sentinella.canale() is None
    assert sentinella.manda_ntfy("t", "x") is False             # senza canale non parte niente


# ---------------------------------------------------------------- tabella `controlli` («Stato dei dati»)
def test_registra_scrive_una_riga_per_invariante_e_controlli_esegui_non_la_cancella(db):
    rr = [Rottura("punti_diversi", "utente 3", 10, "widget 70.0 contro oggi 72.4"),
          Rottura("voti_mancanti", None, 9, "2 squadre senza voti: a, b")]
    db.execute("INSERT INTO controlli VALUES (?, 'sentinella_tolta', 'errore', 1, 'vecchia', 'ieri')", (ST,))
    sentinella.registra(db, _esito(*rr), quando="2026-10-30T12:00:00")
    controlli.esegui(db, "2026-10-30T12:05:00")
    righe = {r["nome"]: r for r in controlli.leggi(db, ST)}
    assert "sentinella_tolta" not in righe
    assert righe["sentinella_punti_diversi"]["esito"] == "errore"
    assert righe["sentinella_punti_diversi"]["dettaglio"] == "utente 3 · g10: widget 70.0 contro oggi 72.4"
    assert righe["sentinella_voti_mancanti"]["esito"] == "avviso"
    assert righe["sentinella_json_non_valido"]["esito"] == "ok"
    assert righe["sentinella"]["esito"] == "errore" and "1 utenti controllati" in righe["sentinella"]["dettaglio"]
    assert {f"sentinella_{k}" for k in sentinella.INVARIANTI} <= set(righe)
    assert "partite_per_giornata" in righe                    # i controlli di sempre restano


def test_dettaglio_lungo_tagliato(db):
    rr = [Rottura("punti_diversi", f"utente {i}", 10, "x" * 40) for i in range(50)]
    sentinella.registra(db, _esito(*rr))
    riga = next(r for r in controlli.leggi(db, ST) if r["nome"] == "sentinella_punti_diversi")
    assert len(riga["dettaglio"]) <= sentinella.MAX_DETTAGLIO and "(50 in tutto)" in riga["dettaglio"]


# ---------------------------------------------------------------- copia su file dei risultati in diretta (la scrive il servizio)
def test_la_sentinella_legge_la_copia_su_file_della_diretta(tmp_path):
    f = tmp_path / "live.json"
    p = {"casa": "a", "trasferta": "c", "data": "2026-10-31 15:00", "stato": "secondo_tempo", "minuto": "60'", "gol_casa": 1,
         "gol_trasferta": 0, "eventi": []}
    f.write_text(json.dumps({"aggiornato_il": "2026-10-31 16:00:00", "fonte": "espn", "partite": [p]}), encoding="utf-8")
    r = sentinella.leggi_live(f)
    corpo = live.risposta(r, [{"casa": "a", "trasferta": "c", "data": "2026-10-31 15:00", "giocata": 0, "gol_casa": None,
                               "gol_trasferta": None}])
    assert corpo["partite"][0]["gol_casa"] == 1 and corpo["fonte"] == "espn" and corpo["in_corso"] == 1
    f.write_text(json.dumps({"partite": {"a|c": p}}), encoding="utf-8")            # anche in un dizionario
    assert list(sentinella.leggi_live(f).istantanea()["partite"]) == [("a", "c")]
    assert sentinella.leggi_live(f).scarica("https://esempio") == ""             # fermo: non chiede niente a nessuno
    f.write_text("{rovinato", encoding="utf-8")
    assert sentinella.leggi_live(f) is None
    assert sentinella.leggi_live(tmp_path / "manca.json") is None


# ---------------------------------------------------------------- le risposte vere e il giro completo
def test_risposte_utente_non_usa_la_rotta_che_scrive_e_classifica_gli_errori(monkeypatch):
    from fanta import server
    m = _mondo()
    m["oggi"]["formazione"]["punteggio_atteso"] = math.nan
    monkeypatch.setattr(server, "formazione", lambda *a, **k: pytest.fail("la rotta salva la copia automatica: non va chiamata"))
    monkeypatch.setattr(server, "_regole", lambda ctx: REGOLE)
    monkeypatch.setattr(server, "_rose", lambda ctx: None)
    monkeypatch.setattr(server, "oggi", lambda request, cert, ctx: m["oggi"])
    monkeypatch.setattr(consigli, "formazione", lambda db, r, rose: (_ for _ in ()).throw(ValueError("in un reparto nessuno gioca")))
    monkeypatch.setattr(server, "leggi_diario", lambda ctx: (_ for _ in ()).throw(KeyError("x")))
    monkeypatch.setattr(server, "widget", lambda request, ctx: server.JSONResponse(m["widget"]))
    monkeypatch.setattr(server, "risultati_live", lambda request: server.JSONResponse(m["live"]))
    monkeypatch.setattr(server, "leggi_scelta", lambda g, response, ctx: None)
    corpi, errori, scelta = sentinella.risposte_utente(NS(), None)
    assert set(corpi) == {"oggi", "widget", "live", "scelta"} and scelta is None
    assert errori == {"formazione": ("ValueError", "rifiutata"), "diario": ("KeyError", "errore"), "oggi:json": ("ValueError", "json")}


def _contesto(tmp_path, nome, con_squadra=True):
    c = tmp_path / nome
    c.mkdir()
    regole.salva(REGOLE, c / "regole.json")
    squadra = lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"g{i}", RUOLI[i], "a") for i in RUOLI])
    altra = lega.Squadra("Altra", [lega.GiocatoreRosa(100 + i, f"x{i}", RUOLI[i], "b") for i in RUOLI])
    lega.salva(lega.Rose([squadra, altra], "Mia" if con_squadra else None), c / "rose.json")
    return NS(regole=c / "regole.json", rose=c / "rose.json")


def test_esegui_un_utente_alla_volta_con_il_tempo_contato(db, tmp_path, monkeypatch):
    m = _mondo()
    risposte = {"utente 1": ({k: v for k, v in m.items()}, {}, None),
                "utente 2": ({"live": m["live"]}, {"oggi": ("KeyError", "errore"), "widget": ("ValueError", "rifiutata")}, None),
                "utente 4": ({"live": m["live"]}, {"oggi": ("ValueError", "rifiutata")}, None)}
    ctx = {u: _contesto(tmp_path, u.replace(" ", ""), con_squadra=u != "utente 4") for u in risposte}
    chi = {str(c.rose): u for u, c in ctx.items()}
    monkeypatch.setattr(sentinella, "risposte_utente", lambda c, db: copy.deepcopy(risposte[chi[str(c.rose)]]))
    monkeypatch.setattr(sentinella, "_prepara_live", lambda: None)
    esito = sentinella.esegui(db, PRIMA, contesti=list(ctx.items()))
    per = {(r.utente, r.invariante) for r in esito["rotture"]}
    assert ("utente 2", "risposta_in_errore") in per and ("utente 2", "risposta_rifiutata") in per
    assert not any(u == "utente 1" for u, _ in per)                      # il mondo coerente
    assert not any(u == "utente 4" for u, _ in per)                      # senza la sua squadra il rifiuto è giusto
    assert esito["controllati"] == ["utente 1", "utente 2", "utente 4"] and esito["rimandati"] == 0
    # tempo finito: almeno uno si controlla, gli altri al giro dopo (prima chi è stato controllato meno di recente)
    esito = sentinella.esegui(db, PRIMA, minuti=0, contesti=list(ctx.items()),
                              stato={"utenti": {"utente 1": "2026-10-30T11:00:00", "utente 2": "2026-10-30T10:00:00"}})
    assert esito["controllati"] == ["utente 4"] and esito["rimandati"] == 2


def test_con_gli_account_si_controlla_chi_ha_le_rose(multiutente, tmp_path):
    from fanta import account
    from fanta.contesto import Contesto
    adb = account.apri()
    ids = [account.registra(adb, f"utente{n}", "una password lunga 123", account.crea_invito(adb, "x"))[0].id for n in (1, 2)]
    adb.close()
    c = Contesto.per_utente(ids[1])
    c.rose.parent.mkdir(parents=True, exist_ok=True)
    c.rose.write_text("{}", encoding="utf-8")
    assert [(e, x.utente_id) for e, x in sentinella._contesti()] == [(f"utente {ids[1]}", ids[1])]
