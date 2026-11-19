"""Squalificati dai cartellini nel calcolo (fanta/squalifiche.py, #668): valgono solo quando la giornata non ha una lettura
buona delle probabili; con una lettura buona vince la fonte, e una differenza a giornata cominciata va nel registro dei
controlli. Solo dati inventati e cartelle temporanee."""
import pandas as pd

from fanta import archivio, consigli, controlli, modello
from fanta import squalifiche as sq
from fanta.regole import Regole
from test_modello import ST, _dati

ESPULSO = {3: sq.Stato(True, False)}          # il mediano del beta, espulso nella sua ultima partita


def _p(probabili=None, dai_cartellini=None, d=None):
    return modello.previsioni(d or _dati(), ST, 5, Regole(), probabili=probabili,
                              dai_cartellini=dai_cartellini).set_index("id")


def _riga(cid, squadra, stato, percentuale=90.0):
    return {"calciatore_id": cid, "squadra": squadra, "stato": stato, "percentuale": percentuale, "in_dubbio": 0,
            "diffidato": 0, "nota": None}


# ---------------------------------------------------------------- il modello
def test_senza_probabili_lo_squalificato_dai_cartellini_non_gioca():
    d = _dati()                                       # gli stessi dati: i pezzi ricordati dentro `d` non bastano più
    senza, con = _p(d=d), _p(dai_cartellini=ESPULSO, d=d)
    assert pd.isna(senza.at[3, "stato"]) and senza.at[3, "p_voto"] > 0.5
    assert (con.at[3, "stato"], con.at[3, "p_voto"], con.at[3, "atteso"]) == ("squalificato", 0.0, 0.0)
    for cid in (1, 2):                                                    # gli altri come prima
        assert con.at[cid, "p_voto"] == senza.at[cid, "p_voto"] and pd.isna(con.at[cid, "stato"])


def test_con_le_probabili_della_sua_squadra_vince_la_fonte():
    prob = pd.DataFrame([_riga(3, "beta", "titolare"), _riga(2, "beta", "titolare"), _riga(1, "alfa", "titolare")])
    p = _p(prob, ESPULSO)
    assert p.at[3, "stato"] == "titolare" and p.at[3, "p_voto"] > 0.8


def test_con_una_lettura_buona_la_regola_non_vale_nemmeno_per_le_squadre_assenti():
    """La pagina delle probabili ha solo alfa. La giornata ha una lettura buona: per beta valgono le presenze, come prima, e
    non i cartellini (uno stato senza la fonte, in una giornata con le probabili, farebbe partire avvisi di cambi e
    entrerebbe nella taratura di «gioca N%», che legge lo stato come detto dalla fonte)."""
    p, senza = _p(pd.DataFrame([_riga(1, "alfa", "titolare")]), ESPULSO), _p(pd.DataFrame([_riga(1, "alfa", "titolare")]))
    assert p.at[1, "stato"] == "titolare"
    assert pd.isna(p.at[3, "stato"]) and p.at[3, "p_voto"] == senza.at[3, "p_voto"] > 0.5


def test_diffidato_dai_cartellini_solo_senza_probabili():
    diffidato = {3: sq.Stato(False, True)}
    p = _p(dai_cartellini=diffidato)
    assert bool(p.at[3, "diffidato"]) and pd.isna(p.at[3, "stato"]) and p.at[3, "p_voto"] > 0.5
    prob = pd.DataFrame([_riga(3, "beta", "titolare"), _riga(2, "beta", "titolare")])
    assert not bool(_p(prob, diffidato).at[3, "diffidato"])


# ---------------------------------------------------------------- le previsioni dell'app (consigli)
def _archivio(tmp_path):
    """Il calendario di `_dati` (alfa-beta, giocate le prime 4), il mediano del beta espulso alla 4, le squadre di oggi e
    l'ultimo aggiornamento riuscito del calendario la sera della 4."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    d = _dati()
    archivio.inserisci(db, "partite", [
        {"id": int(p["id"]), "stagione": ST, "giornata": int(p["giornata"]), "data": p["data"], "casa": p["casa"],
         "trasferta": p["trasferta"], "giocata": int(p["giocata"])} for p in d.partite.to_dict("records")])
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": 4, "calciatore_id": 3, "squadra": "beta", "voto_red": 5.0,
                                     "ammonizioni": 0, "espulsioni": 1}])
    archivio.inserisci(db, "calciatori", [{"id": int(c["id"]), "nome": c["nome"], "squadra_slug": c["squadra_slug"]}
                                          for c in d.calciatori.to_dict("records")])
    archivio.segna_passo(db, "calendario", "2026-09-04T20:00:00")
    db.commit()
    return db, d


def _probabili(db, tabella, righe, giornata=5, **extra):
    archivio.inserisci(db, tabella, [{**r, "stagione": ST, "giornata": giornata, "fonte": "fantacalcio", "partita_id": 5,
                                      "rilevato": "2026-09-05T10:00:00", **extra} for r in righe])
    db.commit()


def test_previsioni_senza_lettura_buona_vale_la_regola_con_lettura_buona_vince_la_fonte(tmp_path):
    db, d = _archivio(tmp_path)
    p, _, con_probabili = consigli._calcola_previsioni(db, d, Regole(), ST, 5, None)
    assert not con_probabili
    assert (p.at[3, "stato"], p.at[3, "p_voto"]) == ("squalificato", 0.0)
    # la copia della giornata prima resta solo nella storia: per l'app la giornata è ancora senza probabili
    righe = [_riga(1, "alfa", "titolare"), _riga(2, "beta", "titolare"), _riga(3, "beta", "titolare")]
    _probabili(db, "probabili_storia", righe, copia=1)
    p, _, _ = consigli._calcola_previsioni(db, d, Regole(), ST, 5, None)
    assert p.at[3, "stato"] == "squalificato"
    _probabili(db, "probabili", righe)                                  # una lettura buona: vince la fonte
    p, _, con_probabili = consigli._calcola_previsioni(db, d, Regole(), ST, 5, None)
    assert con_probabili and p.at[3, "stato"] == "titolare" and p.at[3, "p_voto"] > 0.8


def test_numeri_nostri_dal_vivo_con_gli_stessi_squalificati(tmp_path, monkeypatch):
    """I numeri «nostri» (registro_nostri, confronto I4) si fanno come i mostrati: senza probabili l'espulso è squalificato
    anche lì, altrimenti avrebbe p_voto 0 nei mostrati e alto nei nostri e il confronto penalizzerebbe i nostri."""
    from fanta import registro_nostri
    db, d = _archivio(tmp_path)
    monkeypatch.setattr(registro_nostri.consigli, "dati", lambda db: d)
    monkeypatch.setattr(registro_nostri.consigli, "stagione_corrente", lambda: ST)
    nostri = registro_nostri.previsioni_dal_vivo(db, 5)
    assert (nostri.at[3, "stato"], nostri.at[3, "p_voto"]) == ("squalificato", 0.0)
    _probabili(db, "probabili", [_riga(1, "alfa", "titolare"), _riga(2, "beta", "titolare"), _riga(3, "beta", "titolare")])
    nostri = registro_nostri.previsioni_dal_vivo(db, 5)                 # una lettura buona: vince la fonte
    assert nostri.at[3, "stato"] == "titolare" and nostri.at[3, "p_voto"] > 0.8


# ---------------------------------------------------------------- il registro dei controlli
def test_controllo_differenza_fra_cartellini_e_fonte_a_giornata_cominciata(tmp_path):
    """La fonte dà titolare il mediano espulso (solo dai cartellini) e squalificato il 9 (solo della fonte: per esempio una
    quinta ammonizione, che la regola in uso non guarda). Prima che la giornata cominci la lettura può ancora cambiare: niente."""
    db, _ = _archivio(tmp_path)
    _probabili(db, "probabili", [_riga(1, "alfa", "titolare"), _riga(3, "beta", "titolare"), _riga(9, "beta", "squalificato", 0)])
    assert controlli.squalificati_cartellini(db, ST) is None
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata = 5")
    archivio.segna_passo(db, "calendario", "2026-09-05T20:00:00")
    db.commit()
    esito, valore, dettaglio = controlli.squalificati_cartellini(db, ST)
    assert (esito, valore) == ("avviso", 1.0)
    assert "giornata 5" in dettaglio and "Mediano" in dettaglio
    assert controlli.etichetta("squalificati_cartellini") != "Squalificati cartellini"           # ha un nome per chi legge
    assert "squalificati_cartellini" in controlli.CONTROLLI


def test_controllo_solo_squadre_coperte_e_stagione_di_oggi(tmp_path):
    """La lettura copre solo alfa: per il mediano del beta la fonte non dice niente, e non è una differenza. Per una stagione
    passata il controllo non si fa: le squadre del listone sono quelle di oggi."""
    db, _ = _archivio(tmp_path)
    _probabili(db, "probabili", [_riga(1, "alfa", "titolare")])
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata = 5")
    db.commit()
    esito, valore, _ = controlli.squalificati_cartellini(db, ST)
    assert (esito, valore) == ("ok", 0.0)
    # la stagione prima, uguale un anno indietro, con la fonte che dà titolare il mediano espulso alla 4
    vecchia = "2025-26"
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) SELECT id + 100, ?, giornata, "
               "replace(data, '2026-', '2025-'), casa, trasferta, 1 FROM partite WHERE stagione = ?", (vecchia, ST))
    db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, squadra, ammonizioni, espulsioni) "
               "VALUES (?, 4, 3, 'beta', 0, 1)", (vecchia,))
    archivio.inserisci(db, "probabili", [{**_riga(3, "beta", "titolare"), "stagione": vecchia, "giornata": 5,
                                          "fonte": "fantacalcio"}])
    db.commit()
    assert controlli.squalificati_cartellini(db, vecchia) is None


def test_controllo_tutto_uguale_e_ok(tmp_path):
    db, _ = _archivio(tmp_path)
    _probabili(db, "probabili", [_riga(1, "alfa", "titolare"), _riga(3, "beta", "squalificato", 0)])
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata = 5")
    db.commit()
    esito, valore, _ = controlli.squalificati_cartellini(db, ST)
    assert (esito, valore) == ("ok", 0.0)
