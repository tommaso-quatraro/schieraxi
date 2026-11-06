"""Taratura di «gioca N%» con le probabili formazioni (#379): la misura (PR A) e il passaggio (PR B: accensione, ritorno indietro,
spegnimento a mano, il modello che usa la riga attiva). Solo dati inventati: squadre e giocatori finti, archivi in cartelle temporanee."""
import importlib.util
import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fanta import archivio, modello, taratura_probabili as tp

RADICE = Path(__file__).resolve().parent.parent
ST = "2026-27"
COLONNE = ["stagione", "giornata", "calciatore_id", "stato", "percentuale", "dubbio", "p_mostrato", "preso"]


@pytest.fixture(autouse=True)
def avvisi(monkeypatch):
    """Nessun avviso vero dai test: il canale del proprietario è finto e tiene da parte titolo e testo di ogni avviso."""
    from fanta import sentinella
    mandati = []

    def finto(titolo, testo):
        mandati.append((titolo, testo))
        return True

    monkeypatch.setattr(sentinella, "manda_ntfy", finto)
    return mandati


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


# ---------------------------------------------------------------- A3: la prova e il comando (solo misura)
SQUADRE = [f"Squadra{k:02d}" for k in range(20)]
ADESSO = datetime(2026, 12, 1, 13, 0)


def _gioca_vera(stato, perc, dubbio):
    """La curva «vera» di A2: titolari σ(−1 + 4q), panchinari σ(−2,5 + 3q), in dubbio −0,5; chi non è citato 3 volte su 100."""
    if stato == "non_citato":
        return 0.03
    if stato == "infortunato":
        return 0.0
    q = (perc if perc is not None else (80 if stato == "titolare" else 20)) / 100
    a, b = (-1.0, 4.0) if stato == "titolare" else (-2.5, 3.0)
    return _sigma(a + b * q - 0.5 * dubbio)


def _gioca_partenza(stato, perc, dubbio):
    return modello._p_da_probabili(stato, perc, bool(dubbio))


def _genera(db, giornate, gioca=_gioca_vera, seme=1):
    """Giornate finte complete: 10 partite, 20 squadre da 24 giocatori (11 titolari, 7 in panchina, 5 non citati, 1 infortunato).
    Chi gioca lo decide `gioca`; il «gioca N%» mostrato è sempre la formula di partenza."""
    rng = np.random.default_rng(seme)
    for g in giornate:
        righe = []
        for s, nome in enumerate(SQUADRE):
            pid = 1000 * g + s // 2
            if s % 2 == 0:
                _partita(db, pid, g, nome, SQUADRE[s + 1])
            stati = ["titolare"] * 11 + ["panchina"] * 7 + ["non_citato"] * 5 + ["infortunato"]
            in_campo = False
            for j, stato in enumerate(stati):
                perc = None
                if stato == "titolare":
                    perc = None if rng.random() < 0.1 else float(rng.choice(np.arange(45, 101, 5)))
                elif stato == "panchina":
                    perc = float(rng.integers(5, 70))
                dubbio = int(stato in ("titolare", "panchina") and rng.random() < 0.12)
                cid = 100 * s + j
                righe.append({"id": cid, "squadra": nome.lower(), "partita": pid, "stato": stato, "percentuale": perc, "dubbio": dubbio,
                              "p_voto": round(_gioca_partenza(stato, perc, dubbio), 3)})
                if rng.random() < gioca(stato, perc, dubbio):
                    _voto(db, g, cid, nome)
                    in_campo = True
            if not in_campo:
                _voto(db, g, 100 * s + 99, nome)                     # almeno un voto per squadra: la partita conta
        _giornata(db, g, righe)
    db.commit()


def _tabella(db):
    return [dict(r) for r in db.execute("SELECT * FROM taratura_probabili ORDER BY versione")]


def _m(brier, per, calibrazione=0.02):
    return {"casi": 1500, "brier": brier, "calibrazione": calibrazione, "per_giornata": [[ST, 10 + i, b] for i, b in enumerate(per)]}


@pytest.mark.parametrize("nuova, attuale, mostrati, t, atteso", [
    (_m(0.090, [0.09] * 3), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (True, "migliora")),
    (_m(0.0997, [0.0997] * 3), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (False, "non_migliora")),     # solo lo 0,3%
    (_m(0.090, [0.09] * 3), _m(0.100, [0.1] * 3), _m(0.0902, [0.0902] * 3), TARATURA, (False, "non_migliora")),   # non batte i mostrati
    (_m(0.0867, [0.05, 0.105, 0.105]), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (False, "non_migliora")),  # 1 su 3
    (_m(0.0917, [0.08, 0.09, 0.105]), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (True, "migliora")),        # 2 su 3
    (_m(0.090, [0.09] * 4), _m(0.100, [0.1, 0.1, 0.08, 0.08]), _m(0.100, [0.1] * 4), TARATURA, (False, "non_migliora")),  # 2 su 4
    (_m(0.090, [0.09] * 3, 0.06), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (False, "fuori_soglia")),
    (_m(0.160, [0.16] * 3), _m(0.180, [0.18] * 3), _m(0.180, [0.18] * 3), TARATURA, (False, "fuori_soglia")),
    (_m(0.090, [0.09] * 3), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), {**TARATURA, "dubbio": 0.4}, (False, "incoerente")),
    (_m(None, []), _m(0.100, [0.1] * 3), _m(0.100, [0.1] * 3), TARATURA, (False, "non_migliora")),               # nessun caso
])
def test_verdetto(nuova, attuale, mostrati, t, atteso):
    assert tp.verdetto(nuova, attuale, mostrati, t) == atteso


def test_prova_attesa_sotto_quattro_giornate(db):
    _genera(db, [1, 2, 3])
    _genera(db, [4], seme=2)
    db.execute("UPDATE registro_giornate SET con_probabili = 0 WHERE giornata = 4")      # giornata senza probabili: non conta
    db.commit()
    assert tp.prova(db, None) is None
    assert tp.esegui(db, ADESSO) == "taratura-probabili: in attesa: 3 giornate su 4"
    assert _tabella(db) == []


def test_archivio_vuoto_in_attesa(db):
    assert tp.esegui(db, ADESSO) == "taratura-probabili: in attesa: 0 giornate su 4"
    assert _tabella(db) == []


def test_prova_curva_vera_batte_i_valori_di_partenza(db):
    _genera(db, range(1, 7))
    riga = tp.esegui(db, ADESSO)
    assert riga.startswith("taratura-probabili: versione 1 pronta (poche_giornate)"), riga       # passa, ma 6 giornate su 8
    [t] = _tabella(db)
    assert t["stato"] == "pronta" and t["motivo"] == "poche_giornate" and t["avvisato"] == 0 and t["creata"] == "2026-12-01T13:00:00"
    assert json.loads(t["taratura"]) == [[ST, 1], [ST, 2], [ST, 3]] and json.loads(t["prova"]) == [[ST, 4], [ST, 5], [ST, 6]]
    c = json.loads(t["coefficienti"])
    assert tp.coerente(c)
    for stato, perc, vero in (("titolare", 70.0, _sigma(-1 + 4 * 0.7)), ("panchina", 30.0, _sigma(-2.5 + 3 * 0.3))):
        assert modello._p_da_probabili(stato, perc, False, c) == pytest.approx(vero, abs=0.05)     # ritrova la curva vera
    m = json.loads(t["misura"])
    assert m["nuova"]["brier"] < m["attuale"]["brier"] and m["nuova"]["brier"] < m["mostrati"]["brier"]
    assert m["nuova"]["casi"] == 3 * 20 * 24 and [g[:2] for g in m["nuova"]["per_giornata"]] == [[ST, 4], [ST, 5], [ST, 6]]
    assert m["nuova"]["calibrazione"] <= 0.05


def test_prova_dati_dai_valori_di_partenza_non_migliora(db):
    _genera(db, range(1, 7), gioca=_gioca_partenza, seme=5)
    riga = tp.esegui(db, ADESSO)
    [t] = _tabella(db)
    assert t["stato"] == "scartata" and riga.startswith("taratura-probabili: versione 1 scartata ("), riga
    m = json.loads(t["misura"])
    assert m["nuova"]["brier"] > m["attuale"]["brier"] * (1 - tp.SOGLIA_BRIER)      # con i dati della formula di oggi non migliora


def test_esegui_non_riscrive_senza_giornate_nuove(db):
    _genera(db, range(1, 5))
    assert "versione 1" in tp.esegui(db, ADESSO)
    assert tp.esegui(db, ADESSO) == "taratura-probabili: niente di nuovo (versione 1, pronta)"   # due volte = una volta
    assert len(_tabella(db)) == 1
    _genera(db, [5], seme=9)
    assert "versione 2" in tp.esegui(db, ADESSO)
    assert [json.loads(t["prova"])[-1] for t in _tabella(db)] == [[ST, 4], [ST, 5]]


def test_ultima_riga_rovinata_si_rifa(db):
    _genera(db, range(1, 5))
    db.execute("INSERT INTO taratura_probabili (creata, stato, prova) VALUES ('2026-11-30T08:00:00', 'pronta', '{rotto')")
    db.commit()
    assert "versione 2 pronta" in tp.esegui(db, ADESSO)


def test_poche_righe_in_attesa(db):
    _genera(db, range(1, 5))
    db.execute("DELETE FROM registro_giocatori WHERE stato = 'panchina' AND calciatore_id % 100 > 2")   # pochi panchinari
    db.commit()
    assert tp.prova(db, None) is None
    assert tp.esegui(db, ADESSO).startswith("taratura-probabili: in attesa: poche righe")
    assert _tabella(db) == []


def _istantanea(db):
    tabelle = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'taratura_probabili' "
                                        "ORDER BY name")]
    return {t: [tuple(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tabelle}


def test_esegui_non_cambia_le_previsioni(db, monkeypatch):
    """Solo misura: le previsioni della giornata dopo sono identiche, nessuna tabella che il modello legge cambia, nemmeno
    `aggiornamenti` (la versione dei dati di `consigli._versione`, che fa ricalcolare le previsioni), e la correzione per gruppi
    resta quella."""
    from fanta import consigli, stato_dati
    from fanta.regole import Regole
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    _genera(db, range(1, 7))
    db.execute("UPDATE partite SET gol_casa = 1 + id % 2, gol_trasferta = 1 + id % 3 WHERE giocata = 1")
    for s, nome in enumerate(SQUADRE):                                 # giornata 7 da giocare, con le probabili di due squadre
        for j in range(24):
            db.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug, quotazione) VALUES (?, ?, ?, ?, ?, 10)",
                       (100 * s + j, f"Finto {s} {j}", "PDCA"[j % 4], nome, nome))
        if s % 2 == 0:
            _partita(db, 7000 + s // 2, 7, nome, SQUADRE[s + 1], giocata=0)
    for j in range(24):
        db.execute("INSERT INTO probabili (stagione, giornata, fonte, calciatore_id, squadra, partita_id, stato, percentuale, in_dubbio, "
                   "diffidato) VALUES (?, 7, 'fantacalcio', ?, 'Squadra00', 7000, ?, ?, 0, 0)",
                   (ST, j, "titolare" if j < 11 else "panchina", 90.0 if j < 11 else 20.0))
    archivio.segna(db, "voti", "2026-11-30T21:00:00")
    db.commit()

    def previsioni():
        return consigli._calcola_previsioni(db, modello.carica(db), Regole(), ST, 7, None)[0]

    prev, tabelle, versione, fattori = previsioni(), _istantanea(db), consigli._versione(db), stato_dati.fattori(db, ST)
    assert "pronta" in tp.esegui(db, ADESSO)
    pd.testing.assert_frame_equal(previsioni(), prev)
    assert _istantanea(db) == tabelle
    assert consigli._versione(db) == versione and stato_dati.fattori(db, ST) == fattori


# ---------------------------------------------------------------- il comando da terminale
def _comando(monkeypatch, file, *argv):
    from fanta import __main__ as principale
    monkeypatch.setattr(archivio, "FILE", file)
    principale.main(["taratura-probabili", *argv])


def _archivio_con(tmp_path, giornate):
    file = tmp_path / "fanta.sqlite"
    d = archivio.apri(file)
    _genera(d, giornate)
    d.close()
    return file


def _versioni(file):
    d = archivio.apri(file)
    try:
        return _tabella(d)
    finally:
        d.close()


def test_comando_una_riga_per_il_log(tmp_path, monkeypatch, capsys):
    file = _archivio_con(tmp_path, range(1, 5))
    _comando(monkeypatch, file)
    out = capsys.readouterr().out
    assert out.startswith("taratura-probabili: versione 1 pronta (poche_giornate): Brier ") and out.count("\n") == 1
    _comando(monkeypatch, file)
    assert capsys.readouterr().out == "taratura-probabili: niente di nuovo (versione 1, pronta)\n"
    assert len(_versioni(file)) == 1


def test_comando_prova_stampa_e_non_scrive_niente(tmp_path, monkeypatch, capsys):
    file = _archivio_con(tmp_path, range(1, 7))
    _comando(monkeypatch, file, "--prova")
    out = capsys.readouterr().out
    assert "Giornate: 6; taratura 2026-27 g1, 2026-27 g2, 2026-27 g3; prova 2026-27 g4, 2026-27 g5, 2026-27 g6" in out
    assert "adesso (numeri di partenza): 1440 casi, Brier " in out and "nuova: 1440 casi" in out and "mostrati: 1440 casi" in out
    assert "Coefficienti: {" in out and "Verdetto: passa (migliora); nessuna riga scritta" in out and "Secondi: " in out
    assert _versioni(file) == []


def test_comando_prova_in_attesa(tmp_path, monkeypatch, capsys):
    _comando(monkeypatch, _archivio_con(tmp_path, [1, 2]), "--prova")
    assert capsys.readouterr().out.startswith("taratura-probabili: in attesa: 2 giornate su 4\nSecondi: ")


def test_comando_archivio_rovinato_una_riga_senza_traccia(tmp_path, monkeypatch, capsys):
    file = tmp_path / "fanta.sqlite"
    file.write_bytes(b"non sono un database " * 300)
    with pytest.raises(SystemExit) as uscita:
        _comando(monkeypatch, file)
    assert uscita.value.code == 1
    assert capsys.readouterr().err == "taratura-probabili: non riuscita (DatabaseError)\n"


def test_comando_errore_imprevisto_senza_dati_nel_log(tmp_path, monkeypatch, capsys):
    def rotto(db, adesso):
        raise RuntimeError("giocatore 123 Mario Finto")

    monkeypatch.setattr(tp, "esegui", rotto)
    with pytest.raises(SystemExit) as uscita:
        _comando(monkeypatch, tmp_path / "fanta.sqlite")
    assert uscita.value.code == 1
    err = capsys.readouterr().err
    assert err == "taratura-probabili: non riuscita (RuntimeError)\n" and "Finto" not in err      # mai il messaggio: può avere dati


def test_comando_prova_mostra_la_traccia_intera(tmp_path, monkeypatch, capsys):
    """Con --prova lo lancia una persona a mano: un errore mostra tutta la traccia (anche per ValueError, che il comando di solito
    riduce a una riga)."""
    def rotto(db):
        raise ValueError("numeri strani nella prova")

    monkeypatch.setattr(tp, "rapporto", rotto)
    with pytest.raises(SystemExit) as uscita:
        _comando(monkeypatch, tmp_path / "fanta.sqlite", "--prova")
    assert uscita.value.code == 1
    err = capsys.readouterr().err
    assert "Traceback" in err and "in rotto" in err and "ValueError: numeri strani nella prova" in err


def _singolare(X, y):
    raise np.linalg.LinAlgError("sistema singolare")


def _stima_infinita(r):
    return {"titolare": [math.inf, -math.inf], "panchina": [-2.0, 3.0], "dubbio": -0.5, "non_citato": 0.03}


@pytest.mark.parametrize("dove, finta", [("regressione_logistica", _singolare), ("stima", _stima_infinita)])
def test_coefficienti_non_finiti_scartata_incoerente(db, monkeypatch, dove, finta):
    """Coefficienti non finiti (sistema singolare, numeri infiniti): riga «scartata» per «incoerente» subito, senza misurarli
    (prima la misura si fermava con un errore a ogni giro)."""
    _genera(db, range(1, 5))
    monkeypatch.setattr(tp, dove, finta)
    riga = tp.esegui(db, ADESSO)
    [t] = _tabella(db)
    assert t["stato"] == "scartata" and t["motivo"] == "incoerente"
    assert riga.startswith("taratura-probabili: versione 1 scartata (incoerente): coefficienti non finiti"), riga
    m = json.loads(t["misura"])
    assert m["nuova"] is None and m["attuale"]["brier"] > 0 and m["mostrati"]["brier"] > 0
    json.loads(t["coefficienti"])                                       # JSON valido anche con NaN e infiniti
    assert "Verdetto: non passa (incoerente); nessuna riga scritta" in tp.rapporto(db)


def test_due_giri_insieme_una_riga_sola(tmp_path, monkeypatch):
    """Il comando lanciato a mano mentre gira quello di aggiorna.sh: il controllo «niente di nuovo» e la scrittura stanno nella
    stessa transazione, quindi il secondo giro aspetta il primo e non scrive un doppione."""
    import threading
    file = _archivio_con(tmp_path, range(1, 5))
    vera, esiti, secondo = tp._prova, {}, []

    def altro_giro():
        d = archivio.apri(file)
        try:
            esiti["secondo"] = tp.esegui(d, ADESSO)
        finally:
            d.close()

    def prova_lenta(r, attuale):
        if not secondo:                                  # il primo giro, a metà del lavoro, fa partire il secondo
            secondo.append(threading.Thread(target=altro_giro))
            secondo[0].start()
            secondo[0].join(2)                           # con il blocco il secondo resta fermo ad aspettare: si va avanti
        return vera(r, attuale)

    monkeypatch.setattr(tp, "_prova", prova_lenta)
    d = archivio.apri(file)
    try:
        esiti["primo"] = tp.esegui(d, ADESSO)
    finally:
        d.close()
    secondo[0].join(60)
    assert esiti["primo"].startswith("taratura-probabili: versione 1 pronta")
    assert esiti["secondo"] == "taratura-probabili: niente di nuovo (versione 1, pronta)"
    assert len(_versioni(file)) == 1


# ---------------------------------------------------------------- aggiorna.sh: ultimo passo, non ferma mai lo script
AGGIORNA = RADICE / "script" / "server" / "aggiorna.sh"


def test_aggiorna_sh_lancia_la_taratura_per_ultima_con_priorita_bassa_e_tempo_massimo():
    t = AGGIORNA.read_text(encoding="utf-8")
    riga = next(r for r in t.splitlines() if "taratura-probabili" in r and not r.lstrip().startswith("#"))
    assert riga.startswith("nice -n 15 timeout 300 .venv/bin/python -m fanta taratura-probabili >> \"$LOG\" 2>&1 || ")
    assert t.index(riga) > t.index("fanta foto") and t.index(riga) > t.index("fanta avviso") and t.index(riga) < t.index("tail -n 2000")


# ---------------------------------------------------------------- B1: accensione, ritorno indietro, spegnimento
PRIMA = ADESSO - timedelta(days=7)          # giro senza giornate da giocare in calendario: lontano da ogni scadenza


def _prossima(db, giornata, quando):
    """Le 10 partite di una giornata ancora da giocare, tutte alla stessa ora."""
    for s in range(0, len(SQUADRE), 2):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, 0)",
                   (1000 * giornata + s // 2, ST, giornata, quando.strftime("%Y-%m-%d %H:%M"), SQUADRE[s], SQUADRE[s + 1]))
    db.commit()


def _segnato(db):
    """L'ora della riga della taratura in `aggiornamenti` (quella che fa ricalcolare le previsioni), None se non c'è."""
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = ?", (tp.CHIAVE,)).fetchone()
    return r[0] if r else None


def _stati(db):
    return [(t["versione"], t["stato"], t["motivo"]) for t in _tabella(db)]


def _v(x, cifre):
    return f"{x:.{cifre}f}".replace(".", ",")


def test_attiva_quando_supera(db):
    _genera(db, range(1, 9))
    riga = tp.esegui(db, ADESSO)
    assert riga.startswith("taratura-probabili: versione 1 attiva (migliora): Brier "), riga
    [t] = _tabella(db)
    assert t["stato"] == "attiva" and json.loads(t["prova"]) == [[ST, g] for g in range(5, 9)]
    c = tp.attiva(db)
    assert c == json.loads(t["coefficienti"]) and tp.coerente(c)
    assert _segnato(db) == "2026-12-01T13:00:00"


def test_pronta_sotto_otto_giornate(db):
    _genera(db, range(1, 7))
    assert tp.esegui(db, ADESSO).startswith("taratura-probabili: versione 1 pronta (poche_giornate): ")
    assert tp.attiva(db) is None and _segnato(db) is None
    # una «pronta» si rifà a ogni giro, ma con le stesse giornate e lo stesso esito non scrive doppioni
    assert tp.esegui(db, ADESSO) == "taratura-probabili: niente di nuovo (versione 1, pronta)"
    assert _stati(db) == [(1, "pronta", "poche_giornate")]


def test_la_pronta_della_sola_misura_si_accende_senza_giornate_nuove(db, monkeypatch):
    """Una riga «pronta» scritta quando il comando misurava soltanto, con già 8 giornate, si accende al primo giro dopo
    l'aggiornamento, senza aspettare una giornata nuova."""
    _genera(db, range(1, 9))
    monkeypatch.setattr(tp, "ATTIVAZIONE", False)
    assert tp.esegui(db, ADESSO).startswith("taratura-probabili: versione 1 pronta (migliora)")
    monkeypatch.setattr(tp, "ATTIVAZIONE", True)
    assert tp.esegui(db, ADESSO).startswith("taratura-probabili: versione 2 attiva (migliora)")
    assert tp.attiva(db) is not None


def test_vicina_la_scadenza(db):
    _genera(db, range(1, 5))
    assert not tp.vicina_la_scadenza(db, ADESSO)                              # niente da giocare in calendario
    _prossima(db, 5, ADESSO + timedelta(hours=30))
    assert not tp.vicina_la_scadenza(db, ADESSO)                              # prima partita fra 30 ore
    assert tp.vicina_la_scadenza(db, ADESSO + timedelta(hours=7))             # fra 23 ore
    assert not tp.vicina_la_scadenza(db, ADESSO + timedelta(hours=31))        # già cominciata


def test_vicina_la_scadenza_con_il_turno_infrasettimanale(db):
    """La giornata in corso ha ancora partite da giocare e la dopo comincia entro 24 ore: anche questa è la vigilia."""
    _genera(db, range(1, 5))
    _prossima(db, 5, ADESSO - timedelta(hours=2))
    _prossima(db, 6, ADESSO + timedelta(hours=20))
    assert tp.vicina_la_scadenza(db, ADESSO)


def test_niente_cambi_nelle_24_ore_prima(db):
    _genera(db, range(1, 9))
    _prossima(db, 9, ADESSO + timedelta(hours=20))
    riga = tp.esegui(db, ADESSO)
    assert riga.startswith("taratura-probabili: versione 1 rimandata (scadenza_vicina)"), riga
    assert _stati(db) == [(1, "rimandata", "scadenza_vicina")]
    assert tp.attiva(db) is None and _segnato(db) is None
    # ancora nelle 24 ore, stesse giornate: la riga rimandata si aggiorna, niente «niente di nuovo» e niente doppioni
    riga = tp.esegui(db, ADESSO + timedelta(hours=4))
    assert riga.startswith("taratura-probabili: versione 1 rimandata (scadenza_vicina)"), riga
    assert _stati(db) == [(1, "rimandata", "scadenza_vicina")] and _tabella(db)[0]["creata"] == "2026-12-01T17:00:00"
    # primo giro fuori dalle 24 ore (la giornata è cominciata): la prova non era consumata, si accende
    dopo = ADESSO + timedelta(hours=21)
    assert tp.esegui(db, dopo).startswith("taratura-probabili: versione 2 attiva (migliora)")
    assert tp.attiva(db) is not None and _segnato(db) == dopo.isoformat(timespec="seconds")


def test_nelle_24_ore_senza_cambi_la_misura_si_scrive(db):
    """Nelle 24 ore si rimanda solo un cambio della riga attiva: una prova che non accende niente si scrive come sempre."""
    _genera(db, range(1, 7), gioca=_gioca_partenza, seme=5)
    _prossima(db, 7, ADESSO + timedelta(hours=20))
    assert " scartata " in tp.esegui(db, ADESSO)


def test_torna_indietro_se_peggiora(db, avvisi):
    _genera(db, range(1, 9))
    assert " attiva " in tp.esegui(db, PRIMA)
    v1 = tp.attiva(db)
    _genera(db, [9], gioca=_gioca_partenza, seme=21)
    riga = tp.esegui(db, PRIMA + timedelta(days=1))
    assert "ritirata" not in riga and tp.attiva(db) == v1                 # una giornata sola: troppo presto per giudicare
    _genera(db, [10], gioca=_gioca_partenza, seme=22)
    riga = tp.esegui(db, ADESSO)
    assert riga.startswith("taratura-probabili: versione 1 ritirata (peggiorata)"), riga
    assert tp.attiva(db) is None and _segnato(db) == "2026-12-01T13:00:00"
    t = _tabella(db)[0]
    assert (t["stato"], t["motivo"]) == ("ritirata", "peggiorata")
    r = json.loads(t["misura"])["ritorno"]
    assert r["giornate"] == [[ST, 9], [ST, 10]]
    assert r["attiva"]["brier"] >= r["partenza"]["brier"] * (1 + tp.SOGLIA_BRIER)
    assert avvisi[-1] == ("SchieraXI: «gioca N%»",
                          "Tornato ai valori di partenza: la versione 1 sbagliava di più nelle ultime 2 giornate.")


def test_ritorno_rimandato_non_si_perde(db):
    _genera(db, range(1, 9))
    tp.esegui(db, PRIMA)
    v1 = tp.attiva(db)
    assert v1 is not None
    _genera(db, [9, 10], gioca=_gioca_partenza, seme=21)
    _prossima(db, 11, ADESSO + timedelta(hours=20))
    riga = tp.esegui(db, ADESSO)                                            # nelle 24 ore: rimandata, la attiva resta
    assert riga.startswith("taratura-probabili: versione 2 rimandata (scadenza_vicina)"), riga
    assert tp.attiva(db) == v1 and _segnato(db) == PRIMA.isoformat(timespec="seconds")
    riga = tp.esegui(db, ADESSO + timedelta(hours=4))                       # ancora nelle 24 ore, stesse giornate
    assert riga.startswith("taratura-probabili: versione 2 rimandata (scadenza_vicina)"), riga
    assert tp.attiva(db) == v1
    dopo = ADESSO + timedelta(hours=21)                                     # fuori dalle 24 ore: il ritorno non si è perso
    riga = tp.esegui(db, dopo)
    assert riga.startswith("taratura-probabili: versione 1 ritirata (peggiorata)"), riga
    assert tp.attiva(db) is None and _segnato(db) == dopo.isoformat(timespec="seconds")


def test_attiva_e_segna_nella_stessa_transazione(db, monkeypatch):
    _genera(db, range(1, 9))
    vera = archivio.segna

    def rotta(*a, **k):
        raise sqlite3.OperationalError("disco pieno")

    monkeypatch.setattr(archivio, "segna", rotta)
    with pytest.raises(sqlite3.OperationalError):
        tp.esegui(db, ADESSO)
    assert _tabella(db) == [] and tp.attiva(db) is None and _segnato(db) is None    # niente a metà
    monkeypatch.setattr(archivio, "segna", vera)
    adesso = datetime(2026, 12, 1, 13, 0, 7, 654321)
    assert " attiva " in tp.esegui(db, adesso)
    assert _segnato(db) == "2026-12-01T13:00:07"                           # l'ora di adesso, al secondo


def test_segna_solo_quando_cambia_la_attiva(db, tmp_path):
    _genera(db, range(1, 7), gioca=_gioca_partenza, seme=5)
    assert " scartata " in tp.esegui(db, PRIMA)
    assert _segnato(db) is None                                  # una prova che non accende niente non fa ricalcolare
    d = archivio.apri(tmp_path / "b.sqlite")
    try:
        _genera(d, range(1, 9))
        assert " attiva " in tp.esegui(d, PRIMA)
        v1 = tp.attiva(d)
        assert _segnato(d) == PRIMA.isoformat(timespec="seconds")
        assert "niente di nuovo" in tp.esegui(d, ADESSO)
        _genera(d, [9], seme=8)
        riga = tp.esegui(d, ADESSO)                              # una giornata in più: prova nuova contro la attiva, che resta
        assert " attiva " not in riga and tp.attiva(d) == v1, riga
        assert _segnato(d) == PRIMA.isoformat(timespec="seconds")
    finally:
        d.close()


def test_spegni_e_riaccendi(db, avvisi):
    _genera(db, range(1, 9))
    tp.esegui(db, PRIMA)
    assert [a[1].split(":")[0] for a in avvisi] == ["Versione 1 attiva"]
    _prossima(db, 9, ADESSO + timedelta(hours=20))              # nelle 24 ore prima: --spegni vale lo stesso, subito
    assert tp.spegni(db, ADESSO) == ("taratura-probabili: spenta a mano: la versione 1 non è più attiva, tornano i numeri di "
                                     "partenza")
    assert tp.attiva(db) is None and _segnato(db) == "2026-12-01T13:00:00"
    assert _stati(db) == [(1, "ritirata", "spenta_a_mano"), (2, "spenta", "spenta_a_mano")]
    assert tp.spegni(db, ADESSO) == "taratura-probabili: già spenta a mano"
    dopo = ADESSO + timedelta(hours=21)
    assert tp.esegui(db, dopo) == "taratura-probabili: spenta a mano (versione 2): non fa niente finché non si riaccende"
    assert len(_tabella(db)) == 2 and tp.attiva(db) is None
    assert len(avvisi) == 1                                     # chi l'ha spenta lo sa già: nessun avviso
    assert tp.accendi(db, dopo) == "taratura-probabili: riaccesa: al prossimo giro la prova riparte da capo"
    assert tp.accendi(db, dopo) == "taratura-probabili: non è spenta: niente da fare"
    assert tp.attiva(db) is None                                # riaccendere non accende niente da solo
    assert tp.esegui(db, dopo).startswith("taratura-probabili: versione 4 attiva (migliora)")
    assert _stati(db)[2:] == [(3, "riaccesa", None), (4, "attiva", "migliora")]
    assert [a[1].split(":")[0] for a in avvisi] == ["Versione 1 attiva", "Versione 4 attiva"]


def test_spegni_senza_attiva_non_ricalcola(db):
    _genera(db, range(1, 7))
    tp.esegui(db, ADESSO)
    assert tp.spegni(db, ADESSO) == "taratura-probabili: spenta a mano: nessuna versione era attiva"
    assert _segnato(db) is None and [s for _, s, _ in _stati(db)] == ["pronta", "spenta"]


def test_avviso_una_volta_senza_nomi(db):
    _genera(db, range(1, 9))
    mandati, parte = [], [False]

    def manda(titolo, testo):
        mandati.append((titolo, testo))
        return parte[0]

    tp.esegui(db, ADESSO, manda)
    assert len(mandati) == 1 and _tabella(db)[0]["avvisato"] == 0          # non è partito: si riprova al giro dopo
    parte[0] = True
    assert tp.esegui(db, ADESSO + timedelta(hours=4), manda).startswith("taratura-probabili: niente di nuovo")
    assert len(mandati) == 2 and _tabella(db)[0]["avvisato"] == 1
    tp.esegui(db, ADESSO + timedelta(hours=8), manda)
    assert len(mandati) == 2                                                # una volta sola
    m = json.loads(_tabella(db)[0]["misura"])
    assert mandati[-1] == ("SchieraXI: «gioca N%»",
                           f"Versione 1 attiva: Brier {_v(m['nuova']['brier'], 3)} invece di {_v(m['attuale']['brier'], 3)}, "
                           f"calibrazione {_v(100 * m['nuova']['calibrazione'], 1)} punti, su 4 giornate di prova.")
    testo = " ".join(mandati[-1]).lower()
    assert "finto" not in testo and "squadra" not in testo


@pytest.mark.parametrize("coefficienti", ["{rotto", "[1, 2]", "null", json.dumps({**TARATURA, "dubbio": 0.4})])
def test_json_rovinato_valori_di_partenza(db, coefficienti, caplog):
    db.execute("INSERT INTO taratura_probabili (creata, stato, coefficienti) VALUES ('2026-11-30T08:00:00', 'attiva', ?)",
               (coefficienti,))
    db.commit()
    with caplog.at_level("WARNING"):
        assert tp.attiva(db) is None
    assert "rotto" not in caplog.text and "0.4" not in caplog.text            # nel log il tipo d'errore, mai il contenuto


def test_tabella_assente_valori_di_partenza(db):
    db.execute("DROP TABLE taratura_probabili")
    db.commit()
    assert tp.attiva(db) is None


def test_comando_spegni_e_accendi(tmp_path, monkeypatch, capsys):
    file = _archivio_con(tmp_path, range(1, 9))
    _comando(monkeypatch, file)
    assert capsys.readouterr().out.startswith("taratura-probabili: versione 1 attiva (migliora)")
    _comando(monkeypatch, file, "--spegni")
    assert capsys.readouterr().out.startswith("taratura-probabili: spenta a mano: la versione 1 non è più attiva")
    _comando(monkeypatch, file, "--accendi")
    assert capsys.readouterr().out.startswith("taratura-probabili: riaccesa")
    assert [t["stato"] for t in _versioni(file)] == ["ritirata", "spenta", "riaccesa"]


@pytest.mark.parametrize("opzioni", [("--spegni", "--prova"), ("--spegni", "--accendi"), ("--accendi", "--prova")])
def test_comando_una_opzione_alla_volta(tmp_path, monkeypatch, opzioni):
    with pytest.raises(SystemExit) as uscita:
        _comando(monkeypatch, tmp_path / "fanta.sqlite", *opzioni)
    assert uscita.value.code == 2
