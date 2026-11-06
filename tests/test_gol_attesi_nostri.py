"""Gol attesi «nostri», Fase B del piano 2026-11-06-gol-attesi-nostri: rigori con memoria lunga divisi nella squadra (B1) e
minuti attesi «se prende voto» (B2). Dati inventati: due stagioni, due squadre."""
from dataclasses import replace

import pandas as pd
import pytest

from fanta import modello
from fanta.modello import Parametri
from fanta.regole import Regole

S1, S2 = "2025-26", "2026-27"
GIOCATE = [(S1, g) for g in range(1, 9)] + [(S2, g) for g in range(1, 11)]   # 8 giornate della stagione prima, 10 della nuova
PROSSIMA = (S2, 11)                                                           # la giornata da prevedere
NOSTRI = Parametri(peso_xg=0.0, peso_xa=0.0)                                  # come i nostri: niente xG e xA

# id: (nome, ruolo, squadra). Chi non ha eventi gioca 90' con voto 6 in ogni giornata giocata, tranne la Riserva (mai in campo);
# la Spalla segna un gol su azione ogni 3 giornate, la Punta ogni 2.
GIOCATORI = {1: ("Rigorista", "A", "alfa"), 2: ("Spalla", "A", "alfa"), 3: ("Mediano", "C", "alfa"),
             4: ("Punta", "A", "beta"), 5: ("Regista", "C", "beta"), 6: ("Riserva", "A", "alfa")}
SEMPRE_IN_CAMPO = (1, 2, 3, 4, 5)
GOL_OGNI = {2: 3, 4: 2}


def presenza(voto=6.0, minuti=90, gol=0, rig_segnati=0, rig_sbagliati=0) -> dict:
    """Una presenza: `voto` None = senza voto; `gol` senza i rigori (come nei voti di Fantacalcio.it)."""
    return {"voto": voto, "minuti": minuti, "gol": gol, "rig_segnati": rig_segnati, "rig_sbagliati": rig_sbagliati}


def _data(stagione: str, giornata: int) -> str:
    return f"{stagione[:4]}-09-{giornata:02d} 15:00"


def _dati(eventi: dict | None = None) -> modello.Dati:
    """Alfa e beta si affrontano a ogni giornata. `eventi`: {(id, stagione, giornata): presenza() o None (non gioca)}; vale
    anche per la giornata da prevedere (dati «dal futuro»). Prestazioni come quelle di `nostri.dati`: niente xG né xA."""
    eventi = eventi or {}
    stagioni = [S1, S2]
    partite, voti, prest = [], [], []
    for i, (st, g) in enumerate(GIOCATE + [PROSSIMA]):
        casa, trasf = ("alfa", "beta") if g % 2 else ("beta", "alfa")
        giocata = (st, g) != PROSSIMA
        gol = {"alfa": 0, "beta": 0}
        for cid, (nome, ruolo, sq) in GIOCATORI.items():
            solito = presenza(gol=int(g % GOL_OGNI.get(cid, 99) == 0)) if giocata and cid in SEMPRE_IN_CAMPO else None
            pres = eventi.get((cid, st, g), solito)
            if pres is None:
                continue
            gol[sq] += pres["gol"] + pres["rig_segnati"]
            sub = int(pres["minuti"] < 45)
            voti.append({"stagione": st, "giornata": g, "calciatore_id": cid, "nome": nome, "squadra": sq, "ruolo": ruolo,
                         "voto_red": pres["voto"], "fv_red": pres["voto"], "voto_stat": pres["voto"], "fv_stat": pres["voto"],
                         "voto_ita": pres["voto"], "fv_ita": pres["voto"], "gol": pres["gol"], "gol_subiti": 0, "autogol": 0,
                         "rig_segnati": pres["rig_segnati"], "rig_sbagliati": pres["rig_sbagliati"], "rig_parati": 0,
                         "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0, "subentrato": sub, "sostituito": 0,
                         "data": _data(st, g)})
            prest.append({"understat_partita": i + 1, "squadra": sq, "calciatore_id": cid, "stagione": st, "giornata": g,
                          "data": _data(st, g), "minuti": pres["minuti"], "gol": pres["gol"] + pres["rig_segnati"],
                          "assist": 0, "rigori_segnati": pres["rig_segnati"],
                          "rigori_calciati": pres["rig_segnati"] + pres["rig_sbagliati"], "xg": None, "xa": None})
        partite.append({"id": i + 1, "stagione": st, "giornata": g, "data": _data(st, g), "casa": casa, "trasferta": trasf,
                        "gol_casa": gol[casa] if giocata else None, "gol_trasferta": gol[trasf] if giocata else None,
                        "giocata": int(giocata), "xg_casa": None, "xg_trasferta": None, "understat_id": i + 1})
    calciatori = pd.DataFrame([{"id": cid, "nome": n, "ruolo": r, "squadra": sq.upper(), "squadra_slug": sq, "quotazione": 10}
                               for cid, (n, r, sq) in GIOCATORI.items()])
    d = modello.Dati(stagioni, pd.DataFrame(voti), pd.DataFrame(prest), pd.DataFrame(partite), calciatori)
    for df in (d.voti, d.prestazioni, d.partite):
        df["t"] = df["stagione"].map(stagioni.index) * modello.PASSO_STAGIONE + df["giornata"]
    rig = d.prestazioni.groupby(["understat_partita", "squadra"])["rigori_calciati"].sum().rename("rigori_squadra")
    d.prestazioni = d.prestazioni.join(rig, on=["understat_partita", "squadra"])
    return d


def _par(**accesi) -> Parametri:
    """I parametri dei nostri con gli interruttori dati accesi."""
    return replace(NOSTRI, **accesi)


def _p(d: modello.Dati, par: Parametri) -> pd.DataFrame:
    return modello.previsioni(d, *PROSSIMA, Regole(), par).set_index("id")


def _rigori(cid: int, giornate, stagione: str = S2, **kw) -> dict:
    """Il giocatore segna un rigore in ognuna delle giornate (90', voto 6)."""
    return {(cid, stagione, g): presenza(rig_segnati=1, **kw) for g in giornate}


# ---------------------------------------------------------------- B1: rigori con memoria lunga, divisi nella squadra
def test_rigorista_tiene_la_quota_senza_rigori_recenti():
    # i 4 rigori della squadra nella stagione prima, tutti suoi; poi 10 giornate senza rigori
    d = _dati(_rigori(1, (2, 4, 6, 8), stagione=S1))
    acceso, spento = _p(d, _par(rigori_squadra=True)), _p(d, NOSTRI)
    rigori_partita = modello.forza_squadre(d, *PROSSIMA, _par(rigori_squadra=True)).rigori_partita
    assert rigori_partita == pytest.approx(4 / 36)            # 4 rigori in 18 partite, due squadre
    assert acceso.at[1, "e_rigori"] >= 0.9 * rigori_partita * acceso.at[1, "fattore"]
    assert acceso.at[1, "e_rigori"] > spento.at[1, "e_rigori"]
    assert (acceso.loc[[2, 3, 4, 5], "e_rigori"] == 0).all()   # chi non ne ha mai calciati non ne ha


def test_quote_di_due_rigoristi_sommano_uno():
    # A (1) ne calcia 3, B (2) uno; tutti e due sempre in campo, nella stessa squadra
    d = _dati(_rigori(1, (2, 4, 6)) | _rigori(2, (8,)))
    p = _p(d, _par(rigori_squadra=True))
    pieno = modello.forza_squadre(d, *PROSSIMA, _par(rigori_squadra=True)).rigori_partita * p.loc[[1, 2], "fattore"]
    quote = p.loc[[1, 2], "e_rigori"] / pieno                  # 90' attesi: min(1, minuti/75) vale 1
    assert p.loc[[1, 2], "minuti"].min() >= 75
    assert quote.sum() == pytest.approx(1.0, abs=0.05)
    assert quote[1] > quote[2] > 0
    # spento, le due quote sommano meno di 1 (il «+0,5» e la memoria corta)
    q_spento = _p(d, NOSTRI).loc[[1, 2], "e_rigori"] / pieno
    assert q_spento.sum() < 0.9


def test_compagno_che_non_gioca_piu_non_toglie_la_quota():
    # la Spalla ne calcia 3 a inizio stagione e poi non gioca più (ultime 6 giornate fuori); il Rigorista ne calcia 1 dopo
    fuori = {(2, S2, g): None for g in range(5, 11)}
    d = _dati(_rigori(2, (1, 2, 3)) | fuori | _rigori(1, (8,)))
    p = _p(d, _par(rigori_squadra=True))
    pieno = modello.forza_squadre(d, *PROSSIMA, NOSTRI).rigori_partita * p.at[1, "fattore"]
    assert p.at[1, "e_rigori"] / pieno == pytest.approx(1.0, abs=0.05)


def test_squadra_senza_rigori_quote_zero():
    # rigori solo per alfa: beta non ne ha mai calciati
    d = _dati(_rigori(1, (2, 4, 6)))
    p = _p(d, _par(rigori_squadra=True))
    assert (p.loc[[4, 5], "e_rigori"] == 0).all()
    assert not p[["e_rigori", "e_gol", "mu", "p_gol"]].isna().any().any()


def test_nessun_rigore_nella_storia_niente_nan():
    p = _p(_dati(), _par(rigori_squadra=True))
    assert (p["e_rigori"] == 0).all()
    assert not p[["e_rigori", "mu", "p_gol"]].isna().any().any()


def test_rigori_e_minuti_senza_dati_dal_futuro():
    base = _rigori(1, (2, 4, 6)) | _rigori(2, (8,))
    # nella giornata da prevedere: due rigori della Spalla
    futuro = {(2, *PROSSIMA): presenza(rig_segnati=1, rig_sbagliati=1)}
    a, b = _p(_dati(base), _par(rigori_squadra=True)), _p(_dati(base | futuro), _par(rigori_squadra=True))
    pd.testing.assert_frame_equal(a, b)
