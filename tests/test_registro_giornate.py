"""Registro delle giornate (L1 di #165): numeri mostrati prima della prima partita, misura a giornata finita, medie e avviso.
Solo dati inventati: squadre e giocatori finti, archivio in una cartella temporanea."""
import json
import sqlite3
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd
import pytest

from fanta import archivio, calcolo, consigli, registro_giornate as rg, registro_nostri, stato_dati
from fanta.regole import Regole

ST = "2026-27"
ORA = lambda giorno, ora, minuto=0: datetime(2026, 11, giorno, ora, minuto)  # noqa: E731


@pytest.fixture(autouse=True)
def _tentativi_azzerati():
    """I motivi dei salvataggi non riusciti si ricordano in memoria: ogni prova riparte da zero."""
    rg._tentativi.clear()
    yield
    rg._tentativi.clear()


def _partita(db, id_, giornata, data, casa, trasferta, giocata=0):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (id_, ST, giornata, data, casa, trasferta, giocata))


def _voto(db, giornata, cid, squadra, ruolo, voto, **altro):
    campi = {"stagione": ST, "giornata": giornata, "calciatore_id": cid, "nome": f"finto{cid}", "squadra": squadra, "ruolo": ruolo,
             "voto_red": voto, "gol": 0, "gol_subiti": 0, "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0,
             "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0} | altro
    db.execute(f"INSERT INTO voti ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})", tuple(campi.values()))


def _prev(righe):
    """Come la tabella di `consigli.previsioni`: una riga per giocatore, indice = id."""
    base = {"nome": "Finto", "squadra": "alfa", "mu_voto": 6.0, "e_gol": 0.1, "e_assist": 0.05, "minuti": 80.0, "stato": None,
            "percentuale": float("nan"), "dubbio": False}
    return pd.DataFrame([base | r for r in righe]).set_index("id")


@pytest.fixture
def giornata10(tmp_path, monkeypatch):
    """Giornata 10: due partite sabato alle 18:30 e 20:45 e un anticipo giovedì (già giocato sabato). Voti finti delle giornate 8 e 9."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    db = archivio.apri(tmp_path / "a.sqlite")
    _partita(db, 1, 10, "2026-11-07 18:30", "Alfa", "Beta")
    _partita(db, 2, 10, "2026-11-07 20:45", "Gamma", "Delta")
    _partita(db, 3, 10, "2026-11-05 20:45", "Epsilon", "Zeta", giocata=1)
    _voto(db, 8, 101, "Alfa", "P", 6.0)                       # imbattuto: 6 + 1 = 7
    _voto(db, 9, 101, "Alfa", "P", 6.5, gol_subiti=1)          # 6,5 - 1 = 5,5  -> fantamedia 6,25
    _voto(db, 9, 102, "Gamma", "D", 6.0, assist=1)             # 7
    _voto(db, 9, 103, "Epsilon", "A", None)                    # senza voto: non conta
    db.commit()
    return db


PREV_10 = [
    {"id": 101, "ruolo": "P", "squadra": "alfa", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.95, "mu": 5.8,
     "stato": "titolare", "percentuale": 95.0},
    {"id": 102, "ruolo": "D", "squadra": "gamma", "partita": 2, "data_partita": "2026-11-07 20:45", "p_voto": 0.42, "mu": 6.4,
     "dubbio": True},
    {"id": 103, "ruolo": "A", "squadra": "epsilon", "partita": 3, "data_partita": "2026-11-05 20:45", "p_voto": 0.9, "mu": 7.5},
]


# ---------------------------------------------------------------- compito 1: tabelle e salvataggio
def test_archivio_vecchio_riceve_le_tabelle_senza_perdere_niente(tmp_path):
    vecchio = sqlite3.connect(tmp_path / "v.sqlite")
    vecchio.execute("CREATE TABLE calciatori (id INTEGER PRIMARY KEY, nome TEXT)")
    vecchio.execute("INSERT INTO calciatori VALUES (7, 'Giocatore Finto')")
    vecchio.commit()
    vecchio.close()
    db = archivio.apri(tmp_path / "v.sqlite")
    tabelle = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"registro_giocatori", "registro_giornate"} <= tabelle
    assert db.execute("SELECT nome FROM calciatori WHERE id = 7").fetchone()[0] == "Giocatore Finto"


def test_salva_i_numeri_mostrati_una_volta_sola(giornata10):
    db = giornata10
    adesso = ORA(7, 18, 22)
    assert rg.salva(db, ST, 10, _prev(PREV_10), True, adesso) == 2           # l'anticipo è già giocato: non si salva
    righe = {r["calciatore_id"]: dict(r) for r in db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = 10", (ST,))}
    assert set(righe) == {101, 102}
    assert righe[101]["p_voto"] == 0.95 and righe[101]["mu"] == 5.8 and righe[101]["fantamedia"] == 6.25
    assert righe[101]["stato"] == "titolare" and righe[101]["percentuale"] == 95.0 and righe[101]["partita_id"] == 1
    assert righe[102]["fantamedia"] == 7.0 and righe[102]["percentuale"] is None and righe[102]["dubbio"] == 1
    assert "nome" not in righe[101]                                            # solo numeri e id: niente nomi nel registro
    g = dict(db.execute("SELECT * FROM registro_giornate WHERE stagione = ? AND giornata = 10", (ST,)).fetchone())
    assert g["giocatori"] == 2 and g["con_probabili"] == 1 and g["salvato"] == "2026-11-07T18:22:00" and g["misurato"] is None
    altri = _prev([{**PREV_10[0], "p_voto": 0.1}])
    assert rg.salva(db, ST, 10, altri, True, ORA(7, 18, 25)) == 0              # già salvata: resta quella di prima
    assert db.execute("SELECT p_voto FROM registro_giocatori WHERE calciatore_id = 101").fetchone()[0] == 0.95


def test_fantamedia_solo_con_le_giornate_di_prima(giornata10):
    db = giornata10
    _voto(db, 10, 101, "Alfa", "P", 9.0)                                       # la giornata stessa non conta
    assert rg.fantamedie(db, ST, 10, Regole()) == {101: 6.25, 102: 7.0}


def test_salva_solo_negli_ultimi_dieci_minuti_prima_della_prima_partita(giornata10, tmp_path, monkeypatch):
    chiamate = []

    def previsioni(db, regole, giornata):
        chiamate.append((regole, giornata))
        return _prev(PREV_10), giornata, True

    db = giornata10
    assert rg.salva_se_serve(db, ORA(7, 18, 19), previsioni) == 0 and chiamate == []
    assert rg.salva_se_serve(db, ORA(7, 18, 20), previsioni) == 2
    assert chiamate == [(Regole(), 10)]                                        # regole classiche, mai quelle di una lega
    assert rg.salva_se_serve(db, ORA(7, 18, 21), previsioni) == 0 and len(chiamate) == 1
    # servizio fermo per tutta la finestra: dopo l'inizio non si salva più niente
    db.execute("DELETE FROM registro_giornate")
    db.execute("DELETE FROM registro_giocatori")
    assert rg.salva_se_serve(db, ORA(7, 18, 30), previsioni) == 0 and len(chiamate) == 1


# ---------------------------------------------------------------- compito 2: misura a giornata finita
def _gioca(db, *partite):
    db.executemany("UPDATE partite SET giocata = 1 WHERE id = ?", [(p,) for p in partite])


@pytest.fixture
def finita(giornata10):
    """Giornata 10 salvata con cinque giocatori, una partita rinviata a dicembre, poi giocata con i voti (numeri da fare a mano)."""
    db = giornata10
    _partita(db, 4, 10, "2026-12-20 15:00", "Eta", "Theta")                    # rinviata: fuori dal turno
    prev = _prev([
        {**PREV_10[0]},                                                         # P, p 0,95, mu 5,8, fantamedia 6,25
        {**PREV_10[1]},                                                         # D, p 0,42, mu 6,4, fantamedia 7
        {"id": 104, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.15, "mu": 6.3},   # senza fantamedia
        {"id": 105, "ruolo": "C", "partita": 1, "data_partita": "2026-11-07 18:30", "p_voto": 0.05, "mu": 6.0},
        {"id": 106, "ruolo": "A", "partita": 4, "data_partita": "2026-12-20 15:00", "p_voto": 0.9, "mu": 7.0},    # partita rinviata
    ])
    assert rg.salva(db, ST, 10, prev, True, ORA(7, 18, 22)) == 5
    _gioca(db, 1, 2)
    _voto(db, 10, 101, "Alfa", "P", 6.0, gol_subiti=2)                         # 4
    _voto(db, 10, 102, "Gamma", "D", 7.0, gol=1)                               # 10
    _voto(db, 10, 104, "Alfa", "C", 5.5)                                       # 5,5
    _voto(db, 10, 900, "Beta", "C", 6.0)                                       # altre squadre: fuori dal registro
    _voto(db, 10, 901, "Delta", "C", 6.0)
    db.commit()
    return db


def test_misura_errore_brier_e_fasce_a_mano(finita):
    m = rg.misura_giornata(finita, ST, 10)
    assert m["voti"] == 3 and m["presenze"] == 4                               # il rinviato non conta
    assert m["sq_modello"] == pytest.approx(1.8 ** 2 + 3.6 ** 2 + 0.8 ** 2)     # (5,8-4)² + (6,4-10)² + (6,3-5,5)²
    assert m["brier_somma"] == pytest.approx(0.05 ** 2 + 0.58 ** 2 + 0.85 ** 2 + 0.05 ** 2)
    fasce = m["fasce"]
    assert len(fasce) == 10 and fasce[9] == [1, 0.95, 1] and fasce[4] == [1, 0.42, 1]
    assert fasce[1] == [1, 0.15, 1] and fasce[0] == [1, 0.05, 0] and fasce[5] == [0, 0, 0]


def test_senza_fantamedia_vale_sei(finita):
    m = rg.misura_giornata(finita, ST, 10)
    assert m["sq_fantamedia"] == pytest.approx(2.25 ** 2 + 3.0 ** 2 + 0.5 ** 2)  # (6,25-4)² + (7-10)² + (6-5,5)²


def test_partita_rinviata_non_tiene_aperta_la_giornata(finita):
    assert rg.da_misurare(finita, ORA(8, 22, 35)) == [(ST, 10)]


def test_si_misura_solo_a_giornata_finita_e_con_i_voti(finita):
    db = finita
    # ultima partita del turno sabato 20:45, finita 22:35: si misura dopo 24 ore
    assert rg.da_misurare(db, ORA(8, 22, 34)) == []
    assert rg.da_misurare(db, ORA(8, 22, 35)) == [(ST, 10)]
    db.execute("DELETE FROM voti WHERE squadra = 'Delta'")                     # una squadra senza voti: si aspetta fino a 72 ore
    assert rg.da_misurare(db, ORA(8, 22, 35)) == []
    assert rg.da_misurare(db, ORA(10, 22, 35)) == [(ST, 10)]
    m = rg.misura_giornata(db, ST, 10)
    assert m["presenze"] == 3 and m["voti"] == 2                               # la partita senza voti non conta
    db.execute("UPDATE partite SET giocata = 0 WHERE id = 2")                  # turno non finito: mai
    assert rg.da_misurare(db, ORA(20, 12)) == []


def _rosa_intera(db, delta: float):
    """25 giocatori (3 P, 8 D, 8 C, 6 A) che giocano di sicuro, nelle partite 1 e 2: fantavoto vero = atteso + `delta`."""
    righe, n = [], 200
    for ruolo, quanti in (("P", 3), ("D", 8), ("C", 8), ("A", 6)):
        for k in range(quanti):
            n += 1
            partita, squadra = (1, "Alfa") if k % 2 else (2, "Gamma")
            righe.append({"id": n, "ruolo": ruolo, "partita": partita, "data_partita": "2026-11-07 18:30", "p_voto": 1.0,
                          "mu": 6.0 + k / 10, "mu_voto": 6.0 + k / 10})
            # i portieri prendono un gol: niente bonus d'imbattibilità, fantavoto = voto - 1
            _voto(db, 10, n, squadra, ruolo, 6.0 + k / 10 + delta + (1 if ruolo == "P" else 0), gol_subiti=1 if ruolo == "P" else 0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    assert rg.salva(db, ST, 10, _prev(righe), True, ORA(7, 18, 22)) == 25
    _gioca(db, 1, 2)
    db.commit()


def test_fascia_su_rose_estratte_a_sorte_e_ripetibile(giornata10):
    db = giornata10
    _rosa_intera(db, 0.0)
    m = rg.misura_giornata(db, ST, 10)
    assert m["fascia_casi"] == 20 and m["fascia_dentro"] == 20                 # punti veri vicini agli attesi: sempre dentro
    assert rg.misura_giornata(db, ST, 10) == m                                 # stesso seme, stessi numeri


def test_fascia_mancata_se_i_punti_veri_sono_lontani(giornata10):
    db = giornata10
    _rosa_intera(db, 3.0)                                                      # 3 punti in più a testa: 33 sopra gli attesi
    m = rg.misura_giornata(db, ST, 10)
    assert m["fascia_casi"] == 20 and m["fascia_dentro"] == 0


# ---------------------------------------------------------------- compito 3: medie, soglie, avviso
def _fasce(**per_fascia):
    f = [[0, 0.0, 0] for _ in range(10)]
    for k, v in per_fascia.items():
        f[int(k[1:])] = v
    return f


R1 = {"voti": 2, "sq_modello": 2.0, "sq_fantamedia": 4.0, "presenze": 4, "brier_somma": 0.4,
      "fasce": _fasce(f9=[2, 1.9, 2], f1=[2, 0.3, 0]), "fascia_casi": 10, "fascia_dentro": 8}
R2 = {"voti": 2, "sq_modello": 2.0, "sq_fantamedia": 2.25, "presenze": 4, "brier_somma": 0.4,
      "fasce": _fasce(f9=[2, 1.8, 1], f1=[2, 0.4, 1]), "fascia_casi": 10, "fascia_dentro": 9}


def test_medie_sommano_le_giornate_della_finestra():
    m = rg.medie([R1, R2])
    assert m["giornate"] == 2 and m["voti"] == 4 and m["fascia_casi"] == 20
    assert m["errore_modello"] == 1.0 and m["errore_fantamedia"] == 1.25        # radice di 4/4 e di 6,25/4
    assert m["i1"] == -0.2                                                      # 1 / 1,25 - 1
    assert m["brier"] == 0.1                                                    # 0,8 / 8
    assert m["calibrazione"] == 0.125                                           # (4 × |0,925 - 0,75| + 4 × |0,175 - 0,25|) / 8
    assert m["copertura"] == 0.85                                               # 17 su 20
    assert rg.medie([])["giornate"] == 0 and rg.medie([])["i1"] is None


def test_nessun_verdetto_prima_di_otto_giornate():
    sette = rg.medie([R1] * 7)
    assert not sette["verdetto"] and sette["regge"] == {"I1": None, "I2": None, "I3": None} and sette["fuori"] == []
    otto = rg.medie([R1] * 8)
    assert otto["verdetto"] and otto["calibrazione"] == 0.1                     # (16 × 0,05 + 16 × 0,15) / 32
    assert otto["regge"] == {"I1": True, "I2": False, "I3": True} and otto["fuori"] == ["I2"]


BUONA = {"voti": 100, "sq_modello": 100.0, "sq_fantamedia": 150.0, "presenze": 100, "brier_somma": 10.0,
         "fasce": _fasce(f9=[50, 47.5, 47], f1=[50, 7.5, 8]), "fascia_casi": 20, "fascia_dentro": 16}
CATTIVA = {**BUONA, "sq_modello": 2000.0}                                       # una sola basta a far uscire I1 dalla soglia


@pytest.fixture
def otto_buone(tmp_path):
    db = archivio.apri(tmp_path / "r.sqlite")
    inviati = []
    esito = {"riesce": True}

    def manda(titolo, testo):
        if esito["riesce"]:
            inviati.append((titolo, testo))
        return esito["riesce"]

    def passo(g, m):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 100, 1)",
                   (ST, g, f"2026-11-{g:02d}T12:00:00"))
        rg.registra_misura(db, ST, g, m, ORA(g, 12))
        return rg.avvisa(db, manda)

    for g in range(1, 9):
        assert passo(g, BUONA) is False
    return db, passo, inviati, esito


def test_avviso_dopo_due_giornate_fuori_soglia_una_volta_sola(otto_buone):
    db, passo, inviati, _ = otto_buone
    assert passo(9, CATTIVA) is False and inviati == []                         # fuori la prima volta: si aspetta
    assert passo(10, CATTIVA) is True and len(inviati) == 1                     # fuori due giornate di fila: un avviso
    assert "I1" in inviati[0][1] and "I2" not in inviati[0][1]
    assert passo(11, CATTIVA) is False and len(inviati) == 1                    # resta fuori: niente raffiche
    for g in range(12, 20):                                                    # rientra quando le cattive escono dalla finestra
        assert passo(g, BUONA) is False
    assert db.execute("SELECT fuori FROM registro_giornate WHERE giornata = 19").fetchone()[0] == "[]"
    assert passo(20, CATTIVA) is False and passo(21, CATTIVA) is True and len(inviati) == 2   # esce di nuovo: nuovo avviso


def test_avviso_non_mandato_si_riprova(otto_buone):
    db, passo, inviati, esito = otto_buone
    passo(9, CATTIVA)
    esito["riesce"] = False                                                     # canale mancante o rete giù
    assert passo(10, CATTIVA) is False and inviati == []
    esito["riesce"] = True
    assert rg.avvisa(db, lambda t, x: inviati.append((t, x)) or True) is True and len(inviati) == 1
    assert rg.avvisa(db, lambda t, x: inviati.append((t, x)) or True) is False and len(inviati) == 1


@pytest.fixture
def ntfy_finto(tmp_path, monkeypatch):
    """Un servizio ntfy finto su 127.0.0.1 (porta scelta dal sistema): raccoglie gli avvisi mandati da `sentinella.manda_ntfy`.
    Il canale del proprietario sta in un file temporaneo, che all'inizio non c'è."""
    ricevuti = []

    class Gestore(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - nome imposto da http.server
            ricevuti.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    canale = tmp_path / "canale"
    monkeypatch.setenv("SCHIERAXI_CANALE", str(canale))
    monkeypatch.setenv("SENTINELLA_NTFY_URL", f"http://127.0.0.1:{server.server_port}/")
    yield canale, ricevuti
    server.shutdown()
    server.server_close()


def test_giro_salva_misura_e_avvisa_il_proprietario(giornata10, ntfy_finto, monkeypatch):
    """Tutto il giro con l'invio vero (servizio finto): 8 giornate buone e la 9ª fuori soglia già misurate; la 10ª si salva
    negli ultimi dieci minuti, si misura un giorno dopo la fine ed è la seconda fuori soglia di fila: un avviso solo."""
    canale, ricevuti = ntfy_finto
    db = giornata10
    for g in range(1, 10):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 100, 1)",
                   (ST, g, f"2026-09-{g:02d}T12:00:00"))
        rg.registra_misura(db, ST, g, BUONA if g < 9 else CATTIVA, datetime(2026, 9, g, 12))
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata: (_prev(PREV_10), giornata, True))
    monkeypatch.setattr(registro_nostri, "previsioni_dal_vivo", lambda db, giornata: _prev(PREV_10))   # anche i numeri nostri
    rg.giro(ORA(7, 18, 21), db)                                                 # dieci minuti prima: salva
    assert db.execute("SELECT giocatori FROM registro_giornate WHERE giornata = 10").fetchone()[0] == 2 and ricevuti == []
    _gioca(db, 1, 2)
    _voto(db, 10, 101, "Alfa", "P", 6.0)
    _voto(db, 10, 102, "Gamma", "D", 6.0)
    _voto(db, 10, 900, "Beta", "C", 6.0)
    _voto(db, 10, 901, "Delta", "C", 6.0)
    db.commit()
    rg.giro(ORA(8, 22, 35), db)                                                 # misurata, ma il canale non c'è: resta da mandare
    riga = db.execute("SELECT misurato, fuori, da_avvisare FROM registro_giornate WHERE giornata = 10").fetchone()
    assert riga[0] is not None and riga[1] == '["I1"]' and riga[2] == '["I1"]' and ricevuti == []
    canale.write_text("canale-finto\n", encoding="utf-8")
    rg.giro(ORA(8, 22, 36), db)                                                 # canale pronto: parte
    assert len(ricevuti) == 1 and ricevuti[0]["topic"] == "canale-finto" and ricevuti[0]["title"] == "SchieraXI: statistiche"
    assert "I1" in ricevuti[0]["message"] and "finto" not in ricevuti[0]["message"]  # niente nomi di giocatori
    rg.giro(ORA(8, 22, 37), db)
    assert len(ricevuti) == 1                                                   # una volta sola


def test_testo_avviso_solo_numeri():
    titolo, testo = rg.testo_avviso(["I1", "I3"], {**rg.medie([CATTIVA] * 8), "copertura": 0.65})
    assert titolo == "SchieraXI: statistiche"
    assert "I1" in testo and "I3" in testo and "I2" not in testo and "65%" in testo and "ultime 8 giornate" in testo


# ---------------------------------------------------------------- giornata persa: se ne accorge qualcuno
def _canale():
    """Un `manda` finto che all'inizio non riesce (rete giù): raccoglie gli avvisi partiti."""
    inviati, esito = [], {"riesce": False}

    def manda(titolo, testo):
        if esito["riesce"]:
            inviati.append((titolo, testo))
        return esito["riesce"]
    return manda, inviati, esito


def test_previsioni_sempre_in_errore_giornata_persa_e_un_avviso(giornata10, monkeypatch, caplog):
    def rotte(db, regole, giornata):
        raise ValueError("dati segreti di un giocatore")

    monkeypatch.setattr(consigli, "previsioni", rotte)
    manda, inviati, esito = _canale()
    db = giornata10
    with caplog.at_level("WARNING"):
        for minuto in (20, 25, 29):                                             # tutti i controlli della finestra vanno in errore
            rg.giro(ORA(7, 18, minuto), db, manda)
    assert "ValueError" in caplog.text and "dati segreti" not in caplog.text
    assert "test_registro_giornate.py:" in caplog.text                          # dove: file e riga, senza il messaggio
    assert db.execute("SELECT COUNT(*) FROM registro_giornate").fetchone()[0] == 0   # prima dell'inizio non è ancora persa
    with caplog.at_level("WARNING"):
        rg.giro(ORA(7, 18, 30), db, manda)                                      # la prima partita è iniziata: persa
    riga = dict(db.execute("SELECT * FROM registro_giornate WHERE stagione = ? AND giornata = 10", (ST,)).fetchone())
    assert riga["salvato"] is None and riga["giocatori"] == 0 and "ValueError" in riga["persa"]
    assert "persa" in caplog.text and inviati == []                             # l'invio non è riuscito: si riprova
    esito["riesce"] = True
    for minuto in (31, 32, 33):
        rg.giro(ORA(7, 18, minuto), db, manda)
    assert len(inviati) == 1                                                    # un avviso solo
    titolo, testo = inviati[0]
    assert titolo.startswith("SchieraXI") and "giornata 10" in testo and "ValueError" in testo and "segreti" not in testo
    ultima = stato_dati.riepilogo(db, ST)["registro"]["per_giornata"][0]       # e Stato dei dati la mostra
    assert ultima["giornata"] == 10 and "ValueError" in ultima["persa"] and ultima["salvato"] is None
    _gioca(db, 1, 2)
    assert rg.da_misurare(db, ORA(10, 12)) == []                                # una giornata persa non si misura


@pytest.mark.parametrize("previsioni, frase", [
    (lambda db, r, g: (_prev(PREV_10).rename(columns={"p_voto": "p_gioca"}), g, True), "p_voto"),     # colonna cambiata nel modello
    (lambda db, r, g: (_prev(PREV_10), 11, True), "giornata 11"),                                       # previsioni di un'altra giornata
    (lambda db, r, g: (_prev([{**x, "mu": float("nan")} for x in PREV_10]), g, True), "fantavoto atteso"),
])
def test_zero_righe_dice_il_motivo_e_la_giornata_diventa_persa(giornata10, caplog, previsioni, frase):
    db = giornata10
    with caplog.at_level("WARNING"):
        assert rg.salva_se_serve(db, ORA(7, 18, 22), previsioni) == 0
    assert "giornata 10" in caplog.text and frase in caplog.text
    assert rg.segna_perse(db, ORA(7, 18, 30)) == [(ST, 10)]
    assert frase in db.execute("SELECT persa FROM registro_giornate WHERE giornata = 10").fetchone()[0]


def test_giornata_persa_col_servizio_fermo(giornata10):
    """Nessun controllo nella finestra (servizio fermo): la giornata è persa se il registro era già partito, una volta sola.
    Le giornate prima della prima registrata (registro appena acceso) e quelle non iniziate non contano."""
    db = giornata10
    _partita(db, 8, 8, "2026-10-24 18:30", "Alfa", "Gamma", giocata=1)
    _partita(db, 9, 9, "2026-10-31 18:30", "Beta", "Delta", giocata=1)
    _partita(db, 11, 11, "2026-11-14 18:30", "Gamma", "Alfa")
    assert rg.segna_perse(db, ORA(7, 18, 31)) == []                             # registro mai partito: niente
    db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, 9, ?, 600, 1)",
               (ST, "2026-10-31T18:20:00"))
    assert rg.segna_perse(db, ORA(7, 18, 29)) == []                             # la 10 non è ancora iniziata
    assert rg.segna_perse(db, ORA(7, 18, 31)) == [(ST, 10)]
    assert "nessun tentativo" in db.execute("SELECT persa FROM registro_giornate WHERE giornata = 10").fetchone()[0]
    assert rg.segna_perse(db, ORA(7, 18, 32)) == []                             # una volta sola
    assert [g for (g,) in db.execute("SELECT giornata FROM registro_giornate ORDER BY giornata")] == [9, 10]


def test_salvata_dopo_un_errore_non_e_persa(giornata10):
    db = giornata10

    def rotte(db, regole, giornata):
        raise RuntimeError("rete")

    with pytest.raises(RuntimeError):
        rg.salva_se_serve(db, ORA(7, 18, 20), rotte)
    assert rg.salva_se_serve(db, ORA(7, 18, 21), lambda db, r, g: (_prev(PREV_10), g, True)) == 2
    assert rg.segna_perse(db, ORA(7, 18, 31)) == []


# ---------------------------------------------------------------- il salvataggio con le previsioni VERE del modello
SQUADRE = ("alfa", "beta", "gamma", "delta")
TURNI = ((("alfa", "beta"), ("gamma", "delta")), (("alfa", "gamma"), ("beta", "delta")), (("alfa", "delta"), ("beta", "gamma")),
         (("beta", "alfa"), ("delta", "gamma")), (("gamma", "alfa"), ("delta", "beta")))
RUOLI_SQUADRA = ("P", "D", "D", "C", "C", "A")


@pytest.fixture
def campionato_finto(tmp_path, monkeypatch):
    """Un campionato inventato in un archivio temporaneo: 4 squadre da 6 giocatori, giornate 1-4 giocate con i voti, la 5 sabato
    7/11 alle 18:30 e alle 20:45 con le probabili formazioni. Nessun dato vero, nessuna sostituzione delle previsioni."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    calcolo.cache.clear()                                    # le previsioni in cache di altre prove non contano
    db = archivio.apri(tmp_path / "campionato.sqlite")
    giocatori = [(100 * (s + 1) + k, squadra, ruolo) for s, squadra in enumerate(SQUADRE) for k, ruolo in enumerate(RUOLI_SQUADRA)]
    archivio.inserisci(db, "calciatori", [{"id": i, "nome": f"Finto {i}", "ruolo": r, "squadra": sq[:3].upper(), "squadra_slug": sq,
                                           "quotazione": 10} for i, sq, r in giocatori])
    for g, turno in enumerate(TURNI, start=1):
        giocata = g <= 4
        for k, (casa, trasferta) in enumerate(turno):
            data = f"2026-10-{3 + 7 * (g - 1):02d} 15:00" if giocata else f"2026-11-07 {('18:30', '20:45')[k]}"
            archivio.inserisci(db, "partite", [{"id": 10 * g + k, "stagione": ST, "giornata": g, "data": data, "casa": casa,
                                                "trasferta": trasferta, "gol_casa": 1 + g % 2 if giocata else None,
                                                "gol_trasferta": 1 if giocata else None, "giocata": int(giocata), "understat_id": None}])
        if giocata:
            for i, sq, r in giocatori:
                _voto(db, g, i, sq, r, 6.0 + (i % 3) / 2, gol=int(r == "A" and g % 2 == 1))
    archivio.inserisci(db, "probabili", [{"stagione": ST, "giornata": 5, "fonte": "fantacalcio", "calciatore_id": i, "squadra": sq,
                                          "partita_id": None, "stato": "titolare", "percentuale": 80.0, "in_dubbio": 0, "diffidato": 0,
                                          "nota": None, "rilevato": "2026-11-07T17:00:00"} for i, sq, _ in giocatori])
    db.commit()
    yield db, {i for i, _, _ in giocatori}
    calcolo.cache.clear()


def test_salva_con_le_previsioni_vere_del_modello(campionato_finto, caplog):
    """Se il modello cambia il nome di una colonna, il registro non deve salvare righe vuote in silenzio."""
    db, ids = campionato_finto
    with caplog.at_level("WARNING"):
        assert rg.salva_se_serve(db, ORA(7, 18, 22)) == len(ids)
    assert "mancano" not in caplog.text
    righe = [dict(r) for r in db.execute("SELECT * FROM registro_giocatori WHERE stagione = ? AND giornata = 5", (ST,))]
    assert {r["calciatore_id"] for r in righe} == ids
    for r in righe:
        assert {k for k, v in r.items() if v is None} == set(), r                # ogni colonna ha un valore
        assert r["ruolo"] in "PDCA" and r["squadra"] in SQUADRE and r["partita_id"] in (50, 51)
        assert 0 < r["p_voto"] <= 1 and 2 < r["mu"] < 15 and 4 < r["mu_voto"] < 9
        assert r["e_gol"] >= 0 and r["e_assist"] >= 0 and 0 < r["minuti"] <= 95
        assert r["stato"] == "titolare" and r["percentuale"] == 80.0 and r["dubbio"] == 0 and r["fantamedia"] > 5
    g = dict(db.execute("SELECT * FROM registro_giornate WHERE stagione = ? AND giornata = 5", (ST,)).fetchone())
    assert g["giocatori"] == len(ids) and g["con_probabili"] == 1 and g["persa"] is None
