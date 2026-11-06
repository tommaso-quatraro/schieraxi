"""Taratura di «gioca N%» con le probabili formazioni (#379, PR A: solo misura, nessun numero mostrato cambia).
Solo dati inventati: squadre e giocatori finti, archivi in cartelle temporanee."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fanta import archivio, modello, taratura_probabili as tp

RADICE = Path(__file__).resolve().parent.parent
ST = "2026-27"
COLONNE = ["stagione", "giornata", "calciatore_id", "stato", "percentuale", "dubbio", "p_mostrato", "preso"]


# ---------------------------------------------------------------- costruttore del registro finto
def _partita(db, pid, giornata, casa, trasferta, giocata=1):
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (pid, ST, giornata, f"2026-11-{giornata:02d} 15:00", casa, trasferta, giocata))


def _voto(db, giornata, cid, squadra, voto=6.0):
    db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red) VALUES (?, ?, ?, ?, ?, 'C', ?)",
               (ST, giornata, cid, f"finto{cid}", squadra, voto))


def _giornata(db, giornata, righe, con_probabili=1, misurato=True, persa=None):
    """Una giornata del registro: la riga di `registro_giornate` e i giocatori (dizionari con id, squadra, partita, stato,
    percentuale, dubbio, p_voto)."""
    db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili, misurato, persa) "
               "VALUES (?, ?, ?, ?, ?, ?, ?)",
               (ST, giornata, None if persa else f"2026-11-{giornata:02d}T14:50:00", len(righe), con_probabili,
                f"2026-11-{giornata:02d}T23:00:00" if misurato and not persa else None, persa))
    for r in righe:
        db.execute("INSERT INTO registro_giocatori (stagione, giornata, calciatore_id, ruolo, squadra, partita_id, p_voto, mu, stato, "
                   "percentuale, dubbio) VALUES (?, ?, ?, 'C', ?, ?, ?, 6.0, ?, ?, ?)",
                   (ST, giornata, r["id"], r["squadra"], r["partita"], r["p_voto"], r.get("stato"), r.get("percentuale"),
                    int(r.get("dubbio", 0))))


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "a.sqlite")
    yield d
    d.close()


def _due_giornate(db):
    """Giornate 9 e 10, una partita ciascuna (Alfa-Beta). Hanno il voto: 1 e 4 in tutte e due, 2 solo nella 10."""
    for g in (9, 10):
        _partita(db, g, g, "Alfa", "Beta")
        _giornata(db, g, [
            {"id": 1, "squadra": "alfa", "partita": g, "p_voto": 0.922, "stato": "titolare", "percentuale": 90.0},
            {"id": 2, "squadra": "alfa", "partita": g, "p_voto": 0.225, "stato": "panchina", "percentuale": 30.0, "dubbio": 1},
            {"id": 3, "squadra": "beta", "partita": g, "p_voto": 0.02, "stato": "non_citato"},
            {"id": 4, "squadra": "beta", "partita": g, "p_voto": 0.883, "stato": "titolare"},
        ])
        _voto(db, g, 1, "Alfa")
        _voto(db, g, 4, "Beta")
        _voto(db, g, 3, "Beta", None)                 # riga di voto senza voto: non ha giocato
    _voto(db, 10, 2, "Alfa", 6.5)
    db.commit()


# ---------------------------------------------------------------- A1: le righe di taratura
def test_righe_dal_registro(db):
    _due_giornate(db)
    r = tp.righe(db)
    assert list(r.columns) == COLONNE
    assert len(r) == 8
    nona = r[r["giornata"] == 9].set_index("calciatore_id")
    assert nona.loc[1, "stato"] == "titolare" and nona.loc[1, "percentuale"] == 90.0 and nona.loc[1, "p_mostrato"] == 0.922
    assert nona.loc[2, "dubbio"] == 1 and nona.loc[2, "p_mostrato"] == 0.225
    assert math.isnan(nona.loc[4, "percentuale"])                       # percentuale mancante: resta vuota
    assert nona["preso"].to_dict() == {1: 1, 2: 0, 3: 0, 4: 1}
    assert r[r["giornata"] == 10].set_index("calciatore_id")["preso"].to_dict() == {1: 1, 2: 1, 3: 0, 4: 1}
    assert tp.giornate(r) == [(ST, 9), (ST, 10)]


def test_righe_ignorano_le_probabili_di_dopo(db):
    _due_giornate(db)
    prima = tp.righe(db)
    for tabella in ("probabili", "probabili_storia"):           # letture di dopo la scadenza che dicono altro
        for g in (9, 10):
            db.execute(f"INSERT INTO {tabella} (stagione, giornata, fonte, calciatore_id, squadra, partita_id, stato, percentuale, "
                       "in_dubbio, rilevato) VALUES (?, ?, 'fantacalcio', 2, 'alfa', ?, 'titolare', 99, 0, '2026-11-30 10:00')",
                       (ST, g, g))
    db.commit()
    pd.testing.assert_frame_equal(tp.righe(db), prima)


def test_righe_solo_partite_giocate_con_i_voti(db):
    _due_giornate(db)
    _partita(db, 91, 9, "Gamma", "Delta", giocata=0)                   # rinviata
    _partita(db, 92, 9, "Epsilon", "Zeta")                             # giocata, ma Zeta non ha ancora i voti
    db.execute("DELETE FROM registro_giornate WHERE giornata = 9")
    db.execute("DELETE FROM registro_giocatori WHERE giornata = 9")
    _giornata(db, 9, [
        {"id": 1, "squadra": "alfa", "partita": 9, "p_voto": 0.922, "stato": "titolare", "percentuale": 90.0},
        {"id": 11, "squadra": "gamma", "partita": 91, "p_voto": 0.9, "stato": "titolare", "percentuale": 90.0},
        {"id": 12, "squadra": "epsilon", "partita": 92, "p_voto": 0.9, "stato": "titolare", "percentuale": 90.0},
    ])
    _voto(db, 9, 12, "Epsilon")
    db.commit()
    assert sorted(tp.righe(db).query("giornata == 9")["calciatore_id"]) == [1]


def test_squadre_senza_probabili_fuori(db):
    _due_giornate(db)
    db.execute("INSERT INTO registro_giocatori (stagione, giornata, calciatore_id, ruolo, squadra, partita_id, p_voto, mu, stato) "
               "VALUES (?, 9, 5, 'C', 'beta', 9, 0.7, 6.0, NULL)", (ST,))           # squadra senza probabili: stato vuoto
    for g, campi in ((11, {}), (12, {"con_probabili": 0}), (13, {"misurato": False}), (14, {"persa": "servizio fermo"})):
        _partita(db, g, g, "Alfa", "Beta")
        _giornata(db, g, [{"id": 1, "squadra": "alfa", "partita": g, "p_voto": 0.9, "stato": "titolare", "percentuale": 90.0}],
                  **campi)
        _voto(db, g, 1, "Alfa")
        _voto(db, g, 4, "Beta")
    db.commit()
    r = tp.righe(db)
    assert 5 not in set(r["calciatore_id"])
    assert tp.giornate(r) == [(ST, 9), (ST, 10), (ST, 11)]           # niente giornate senza probabili, non misurate o perse


def test_righe_con_valori_rovinati_non_si_fermano(db):
    _due_giornate(db)
    db.execute("UPDATE registro_giocatori SET percentuale = 'tanto' WHERE calciatore_id = 1 AND giornata = 9")
    db.execute("UPDATE registro_giocatori SET percentuale = 250 WHERE calciatore_id = 1 AND giornata = 10")
    db.execute("UPDATE registro_giocatori SET p_voto = NULL WHERE calciatore_id = 4 AND giornata = 9")
    db.commit()
    r = tp.righe(db).set_index(["giornata", "calciatore_id"])
    assert math.isnan(r.loc[(9, 1), "percentuale"]) and math.isnan(r.loc[(10, 1), "percentuale"])   # fuori scala: mancante
    assert (9, 4) not in r.index                                       # senza il numero mostrato non si confronta


def test_righe_archivio_vuoto(db):
    r = tp.righe(db)
    assert list(r.columns) == COLONNE and r.empty and tp.giornate(r) == []


@pytest.mark.parametrize("n, taratura, prova", [(4, 2, 2), (5, 3, 2), (8, 4, 4), (20, 12, 8)])
def test_dividi(n, taratura, prova):
    gg = [(ST, g) for g in range(1, n + 1)]
    t, p = tp.dividi(gg)
    assert (len(t), len(p)) == (taratura, prova)
    assert t + p == gg                                                 # la prova è la parte più recente


# ---------------------------------------------------------------- A2: la formula tarata e la stima
TARATURA = {"titolare": [-1.0, 4.0], "panchina": [-2.5, 3.0], "dubbio": -0.5, "non_citato": 0.03}


def _sigma(z):
    return 1 / (1 + math.exp(-z))


def test_senza_taratura_numeri_di_oggi():
    casi = [(("titolare", 90.0, False), 0.9216), (("panchina", 30.0, True), 0.225), (("non_citato", None, False), 0.02),
            (("titolare", None, False), 0.8832), (("titolare", float("nan"), False), 0.8832), (("panchina", None, False), 0.2),
            (("infortunato", 90.0, False), 0.0), (("squalificato", None, True), 0.0), (("titolare", 50.0, True), 0.576),
            (("non_convocato", None, False), 0.02), (("non_convocato", None, True), 0.015), ((None, None, False), 0.02)]
    for (stato, perc, dubbio), atteso in casi:
        assert modello._p_da_probabili(stato, perc, dubbio) == pytest.approx(atteso, abs=1e-12)
        assert modello._p_da_probabili(stato, perc, dubbio, None) == pytest.approx(atteso, abs=1e-12)


def test_con_la_taratura_la_curva_logistica():
    p = modello._p_da_probabili
    assert p("titolare", 70.0, False, TARATURA) == pytest.approx(_sigma(-1 + 4 * 0.7))
    assert p("titolare", 70.0, True, TARATURA) == pytest.approx(_sigma(-1 + 4 * 0.7 - 0.5))
    assert p("panchina", 30.0, False, TARATURA) == pytest.approx(_sigma(-2.5 + 3 * 0.3))
    assert p("non_citato", None, False, TARATURA) == 0.03
    assert p("infortunato", 90.0, False, TARATURA) == 0.0 and p("squalificato", None, False, TARATURA) == 0.0
    assert p("non_convocato", None, False, TARATURA) == 0.02                # gli altri stati restano come oggi


def test_percentuale_mancante_vale_80_e_20():
    p = modello._p_da_probabili
    assert p("titolare", None, False, TARATURA) == pytest.approx(_sigma(-1 + 4 * 0.8))
    assert p("titolare", float("nan"), False, TARATURA) == pytest.approx(_sigma(-1 + 4 * 0.8))
    assert p("panchina", None, False, TARATURA) == pytest.approx(_sigma(-2.5 + 3 * 0.2))
    r = pd.DataFrame({"stato": ["titolare", "titolare", "panchina", "panchina"], "percentuale": [np.nan, 80.0, np.nan, 20.0],
                      "dubbio": 0, "preso": [1, 0, 0, 1]})
    m = tp.colonne_regressione(r)
    assert m[0].tolist() == m[1].tolist() and m[2].tolist() == m[3].tolist()   # mancante = 80 per i titolari, 20 in panchina


def _righe_curva(n, seme, tit=(-1.0, 4.0), pan=(-2.5, 3.0), dubbio=-0.5, non_citato=0.03):
    """Righe finte: titolari e panchinari che giocano secondo una curva logistica nota, più qualche non citato."""
    rng = np.random.default_rng(seme)
    stato = rng.choice(["titolare", "panchina", "non_citato"], size=n, p=[0.5, 0.35, 0.15])
    perc = np.where(stato == "titolare", rng.uniform(40, 100, n), rng.uniform(0, 70, n))
    perc = np.where(stato == "non_citato", np.nan, np.round(perc))
    dub = ((rng.random(n) < 0.15) & (stato != "non_citato")).astype(int)
    q = perc / 100
    z = np.where(stato == "titolare", tit[0] + tit[1] * q, pan[0] + pan[1] * q) + dubbio * dub
    p = np.where(stato == "non_citato", non_citato, 1 / (1 + np.exp(-np.nan_to_num(z))))
    return pd.DataFrame({"stato": stato, "percentuale": perc, "dubbio": dub, "preso": (rng.random(n) < p).astype(int)})


def test_stima_ritrova_la_curva():
    t = tp.stima(_righe_curva(5000, seme=11))
    assert t["titolare"][0] == pytest.approx(-1.0, abs=0.3) and t["titolare"][1] == pytest.approx(4.0, abs=0.3)
    assert t["panchina"][0] == pytest.approx(-2.5, abs=0.3) and t["panchina"][1] == pytest.approx(3.0, abs=0.3)
    assert t["dubbio"] == pytest.approx(-0.5, abs=0.3)
    assert 0 < t["non_citato"] <= 0.10
    assert all(v == round(v, 4) for v in [*t["titolare"], *t["panchina"], t["dubbio"], t["non_citato"]])
    assert tp.coerente(t)


def test_non_citato_tirato_verso_due_su_cento():
    r = pd.DataFrame({"stato": ["non_citato"] * 50 + ["titolare"] * 10 + ["panchina"] * 10, "percentuale": [np.nan] * 50 + [80.0] * 20,
                      "dubbio": 0, "preso": [1] * 5 + [0] * 45 + [1, 0] * 10})
    assert tp.stima(r)["non_citato"] == round((5 + 0.02 * 50) / (50 + 50), 4)


def test_dati_degeneri_scartati():
    r = _righe_curva(2000, seme=3)
    r.loc[r["stato"] == "titolare", "preso"] = 1                        # tutti i titolari in campo
    t = tp.stima(r)
    assert all(math.isfinite(v) for v in [*t["titolare"], *t["panchina"], t["dubbio"], t["non_citato"]])
    assert not tp.coerente(t)


def test_coerente():
    assert tp.coerente(TARATURA)
    assert not tp.coerente({**TARATURA, "titolare": [-1.0, -0.5]})              # più percentuale, meno probabilità
    assert not tp.coerente({**TARATURA, "dubbio": 0.4})                       # in dubbio gioca di più
    assert not tp.coerente({**TARATURA, "panchina": [2.0, 3.0]})              # panchina sopra il titolare
    assert not tp.coerente({**TARATURA, "titolare": [-1.0, 1.0]})             # titolare al 100% sotto 0,85
    assert not tp.coerente({**TARATURA, "titolare": [2.0, 4.0]})              # titolare al 100% sopra 0,99
    assert not tp.coerente({**TARATURA, "non_citato": 0.2})
    assert not tp.coerente({**TARATURA, "dubbio": float("nan")})
    assert not tp.coerente({"titolare": [1.0]}) and not tp.coerente(None) and not tp.coerente({**TARATURA, "panchina": "x"})


def test_regressione_spostata_stessi_pesi():
    """La regressione di `prove/calibra_p_voto.py` ora sta in `taratura_probabili`: stessi pesi di prima su una tabella finta."""
    spec = importlib.util.spec_from_file_location("calibra_p_voto", RADICE / "prove" / "calibra_p_voto.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rng = np.random.default_rng(7)
    n = 400
    t = pd.DataFrame({v: rng.random(n) for v in m.VARIABILI})
    t["portiere"] = (rng.random(n) < 0.15).astype(float)
    t["portiere_x_p_storico"] = t["portiere"] * t["p_storico"]
    z = -1.5 + 2 * t["p_storico"] + 1.0 * t["p_ultima"]
    t["preso"] = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    prima = [-1.906426, 2.188313, 0.343917, 0.476296, 1.015456, 0.003217, -0.258796]       # pesi calcolati prima dello spostamento
    assert np.round(m.stima(t), 6).tolist() == prima
    X = np.column_stack([np.ones(n), t[m.VARIABILI].to_numpy(float)])
    assert np.round(tp.regressione_logistica(X, t["preso"].to_numpy(float)), 6).tolist() == prima
    assert m.stima.__code__.co_names.count("regressione_logistica") == 1   # un solo corpo della regressione
