"""Il riepilogo di Oggi a giornata finita con una partita rinviata senza data (#649): chi ha la partita rinviata conta con la regola
della lega («senza voto», voto d'ufficio, «aspetta»). Fino alla #693 c'era anche l'avviso del riepilogo, con gli stessi numeri.
Archivio in una cartella temporanea, dati inventati."""
from dataclasses import replace

import pandas as pd
import pytest

from fanta import archivio, consigli, fasi, lega, scelte
from fanta.regole import Regole

ST = "2026-27"
# id: (nome, ruolo, squadra). Titolari 1-11 (4-4-2), panchina 12-15. «Recupero» gioca atalanta-parma
ROSA = {1: ("Portiere", "P", "inter"), 2: ("Dif2", "D", "inter"), 3: ("Dif3", "D", "milan"), 4: ("Dif4", "D", "roma"),
        5: ("Dif5", "D", "lazio"), 6: ("Cen6", "C", "inter"), 7: ("Cen7", "C", "milan"), 8: ("Cen8", "C", "napoli"),
        9: ("Cen9", "C", "juve"), 10: ("Recupero", "A", "atalanta"), 11: ("Att11", "A", "napoli"),
        12: ("Dif12", "D", "inter"), 13: ("Cen13", "C", "roma"), 14: ("Att14", "A", "juve"), 15: ("Port15", "P", "milan")}
SIGLA = {"inter": "INT", "milan": "MIL", "roma": "ROM", "lazio": "LAZ", "napoli": "NAP", "juve": "JUV", "atalanta": "ATA"}
TITOLARI, PANCHINA = list(range(1, 12)), [12, 13, 14, 15]
# voti: tutti 6 tranne Recupero 8 e la prima riserva Dif12 7,5; il portiere di riserva non gioca. Il portiere titolare prende 7
# (porta inviolata). Con tutti i voti: 7 + 8 × 6 + 8 + 6 = 69; senza Recupero 61, più la prima riserva che può entrare (Dif12,
# panchina libera con cambio di modulo, la regola di base) 68,5, più il voto d'ufficio (6) 67
VOTO = {i: 6.0 for i in range(1, 15)} | {10: 8.0, 12: 7.5, 15: None}
# voti di altri giocatori (non in rosa), come nell'archivio vero: una giornata intera ne ha circa 280
ALTRI = {200 + n: s for n, s in enumerate(["inter", "milan", "roma", "lazio"] * 15)}
LUNEDI_ALTRI = {300 + n: s for n, s in enumerate(["napoli", "juve"] * 10)}


def _archivio(tmp_path, recupero=("2026-10-19 18:00", 1)):
    """Giornata 8 da venerdì a lunedì; atalanta-parma con la data e lo stato di `recupero` (di base giocata nel turno). Giornata 9
    il sabato dopo."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    partite = [(1, 8, "2026-10-17 15:00", "inter", "milan", 1), (2, 8, "2026-10-18 15:00", "roma", "lazio", 1),
               (3, 8, "2026-10-19 20:45", "napoli", "juve", 1), (4, 8, *recupero[:1], "atalanta", "parma", recupero[1]),
               (5, 9, "2026-10-24 15:00", "inter", "roma", 0), (6, 9, "2026-10-25 15:00", "milan", "lazio", 0)]
    archivio.inserisci(db, "partite", [{"id": i, "stagione": ST, "giornata": g, "data": d, "casa": c, "trasferta": t, "gol_casa": None,
                                        "gol_trasferta": None, "giocata": gi, "understat_id": None} for i, g, d, c, t, gi in partite])
    archivio.inserisci(db, "calciatori", [{"id": i, "nome": n, "ruolo": r, "squadra": SIGLA[s], "squadra_slug": s}
                                          for i, (n, r, s) in ROSA.items()])
    return db


BONUS = dict.fromkeys(("gol", "gol_subiti", "autogol", "rig_segnati", "rig_sbagliati", "rig_parati", "assist", "mvp", "ammonizioni",
                       "espulsioni", "subentrato", "sostituito"), 0)        # come le righe vere: bonus e malus a zero, mai vuoti


def _voti(db, miei, altri=None, giornata=8):
    """I voti dei miei giocatori `miei` e di altri giocatori (non in rosa) delle squadre `altri` ({id: squadra})."""
    righe = [{"stagione": ST, "giornata": giornata, "calciatore_id": i, "nome": ROSA[i][0], "squadra": ROSA[i][2], "ruolo": ROSA[i][1],
              "voto_red": VOTO[i]} | BONUS for i in miei]
    righe += [{"stagione": ST, "giornata": giornata, "calciatore_id": i, "nome": f"G{i}", "squadra": s, "ruolo": "C", "voto_red": 6.0}
              | BONUS for i, s in (altri or {}).items()]
    archivio.inserisci(db, "voti", righe)


@pytest.fixture
def mondo(tmp_path, monkeypatch):
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": 0.9, "mu": 6.5, "mu_voto": 6.0} for n, r, _ in ROSA.values()], index=list(ROSA))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, giornata or 9, True))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, r, SIGLA[s]) for i, (n, r, s) in ROSA.items()])], "Mia")
    file_scelte = tmp_path / "scelte.json"
    scelte.salva(ST, 8, TITOLARI, "4-4-2", file_scelte, panchina=PANCHINA)

    def oggi(db, regole=None):
        return fasi.blocco_riepilogo(db, regole or Regole(), rose, ST, 8, file_scelte, None)
    return type("M", (), {"oggi": staticmethod(oggi)})


@pytest.mark.parametrize("modo, punti", [("senza_voto", 68.5), ("voto_ufficio", 67.0)])
def test_recupero_senza_data_oggi_conta_con_la_regola_della_lega(tmp_path, mondo, modo, punti):
    db = _archivio(tmp_path, recupero=(None, 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    assert mondo.oggi(db, replace(Regole(), partite_rinviate=modo))["punti_fatti"] == punti


def test_recupero_senza_data_con_aspetta_oggi_aspetta_il_recupero(tmp_path, mondo):
    db = _archivio(tmp_path, recupero=(None, 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    o = mondo.oggi(db)
    assert o["punti_fatti"] == 61.0 and [p["casa"] for p in o["recuperi"]] == ["atalanta"]
