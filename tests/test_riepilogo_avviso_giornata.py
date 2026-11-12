"""Avviso di fine giornata (#649): parte solo quando ogni squadra che ha giocato ha i voti, per ogni giornata finita per la lega
(anche con una partita rinviata, non solo la più alta) e conta chi ha la partita rinviata con la regola della lega, come il
riepilogo di Oggi. Archivio in una cartella temporanea, dati inventati, nessuna notifica vera."""
import re
from dataclasses import replace
from datetime import datetime

import pandas as pd
import pytest

from fanta import archivio, consigli, fasi, lega, notifiche, scelte
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
LUNEDI = [8, 9, 11, 14]                           # napoli-juve, l'ultima partita del turno
# voti di altri giocatori (non in rosa), come nell'archivio vero: una giornata intera ne ha circa 280
ALTRI = {200 + n: s for n, s in enumerate(["inter", "milan", "roma", "lazio"] * 15)}
LUNEDI_ALTRI = {300 + n: s for n, s in enumerate(["napoli", "juve"] * 10)}
ATALANTA_PARMA = {400 + n: s for n, s in enumerate(["atalanta", "parma"] * 10)}      # solo quando la loro partita è giocata
TURNO_FINITO = datetime(2026, 10, 20, 8, 0)       # il martedì mattina, giro delle 8


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


def _voti(db, miei, altri=None):
    """I voti dei miei giocatori `miei` e di altri giocatori (non in rosa) delle squadre `altri` ({id: squadra})."""
    righe = [{"stagione": ST, "giornata": 8, "calciatore_id": i, "nome": ROSA[i][0], "squadra": ROSA[i][2], "ruolo": ROSA[i][1],
              "voto_red": VOTO[i]} | BONUS for i in miei]
    righe += [{"stagione": ST, "giornata": 8, "calciatore_id": i, "nome": f"G{i}", "squadra": s, "ruolo": "C", "voto_red": 6.0} | BONUS
              for i, s in (altri or {}).items()]
    archivio.inserisci(db, "voti", righe)


@pytest.fixture
def mondo(tmp_path, monkeypatch):
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": 0.9, "mu": 6.5, "mu_voto": 6.0} for n, r, _ in ROSA.values()], index=list(ROSA))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, giornata or 9, True))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, r, SIGLA[s]) for i, (n, r, s) in ROSA.items()])], "Mia")
    file_scelte = tmp_path / "scelte.json"
    scelte.salva(ST, 8, TITOLARI, "4-4-2", file_scelte, panchina=PANCHINA)
    mandati = []

    def riepilogo(db, adesso, regole=None):
        manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append(testo) or True       # noqa: E731
        return notifiche.riepilogo(db, regole or Regole(), rose, adesso, tmp_path / "riepilogo.json", manda, {"riepilogo": True},
                                   tmp_path / "cambi.json", file_scelte, tmp_path / "diario.json")

    def oggi(db, regole=None):
        return fasi.blocco_riepilogo(db, regole or Regole(), rose, ST, 8, file_scelte, None)
    return type("M", (), {"riepilogo": staticmethod(riepilogo), "oggi": staticmethod(oggi), "mandati": mandati,
                          "stato": tmp_path / "riepilogo.json"})


def _punti(testo: str) -> str:
    return re.search(r"circa (\d+,\d) punti", testo).group(1)


def test_l_avviso_aspetta_i_voti_dell_ultima_partita(tmp_path, mondo):
    """Il giro delle 8 trova napoli-juve giocata ma senza voti (gli altri ci sono, ben più di 60 righe). Prima partiva un riepilogo
    con Cen8, Cen9 e Att11 «senza voto» e le riserve al loro posto, una volta sola e mai corretto."""
    db = _archivio(tmp_path)
    _voti(db, [i for i in VOTO if i not in LUNEDI], ALTRI | ATALANTA_PARMA)
    assert mondo.riepilogo(db, TURNO_FINITO) == [] and mondo.mandati == []
    _voti(db, LUNEDI, LUNEDI_ALTRI)                                    # i voti del lunedì arrivano al giro dopo
    r = mondo.riepilogo(db, datetime(2026, 10, 20, 13, 0))
    assert len(r) == 1 and _punti(r[0]) == "69,0" and "Senza voto" not in r[0]
    assert mondo.riepilogo(db, datetime(2026, 10, 20, 17, 0)) == [] and len(mondo.mandati) == 1      # una volta sola


@pytest.mark.parametrize("modo, punti", [("senza_voto", "68,5"), ("voto_ufficio", "67,0")])
def test_con_un_recupero_in_calendario_l_avviso_parte_a_turno_finito(tmp_path, mondo, modo, punti):
    """atalanta-parma rinviata al 12 novembre: per la lega («senza voto» o voto d'ufficio) la giornata è finita con il turno. Prima
    l'avviso aspettava che fossero giocate tutte le partite con una data, e poi guardava solo la giornata più alta: non partiva mai."""
    db = _archivio(tmp_path, recupero=("2026-11-12 20:45", 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    r = mondo.riepilogo(db, TURNO_FINITO, replace(Regole(), partite_rinviate=modo))
    assert len(r) == 1 and _punti(r[0]) == punti


def test_con_aspetta_l_avviso_parte_dopo_il_recupero_anche_se_le_giornate_dopo_sono_gia_finite(tmp_path, mondo):
    db = _archivio(tmp_path, recupero=("2026-11-12 20:45", 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    assert mondo.riepilogo(db, TURNO_FINITO) == []                     # la lega aspetta il recupero: i punti possono cambiare
    db.execute("UPDATE partite SET giocata = 1 WHERE giornata = 9")      # intanto la giornata 9 è finita e riepilogata
    mondo.stato.write_text('{"riepilogo": ["2026-27/9"]}', encoding="utf-8")
    db.execute("UPDATE partite SET giocata = 1 WHERE id = 4")            # giocato il recupero, con i suoi voti
    _voti(db, [10], ATALANTA_PARMA)
    r = mondo.riepilogo(db, datetime(2026, 11, 13, 8, 0))
    assert len(r) == 1 and r[0].startswith("Giornata 8") and _punti(r[0]) == "69,0"


@pytest.mark.parametrize("modo, punti", [("senza_voto", 68.5), ("voto_ufficio", 67.0)])
def test_recupero_senza_data_avviso_e_oggi_danno_lo_stesso_numero(tmp_path, mondo, modo, punti):
    db = _archivio(tmp_path, recupero=(None, 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    regole = replace(Regole(), partite_rinviate=modo)
    r = mondo.riepilogo(db, TURNO_FINITO, regole)
    assert mondo.oggi(db, regole)["punti_fatti"] == punti
    assert len(r) == 1 and _punti(r[0]) == f"{punti:.1f}".replace(".", ",")


def test_recupero_senza_data_con_aspetta_niente_avviso_e_oggi_aspetta_il_recupero(tmp_path, mondo):
    """Prima l'avviso partiva e contava la riserva al posto di Recupero (68,5), mentre Oggi diceva 61 con il recupero da giocare."""
    db = _archivio(tmp_path, recupero=(None, 0))
    _voti(db, [i for i in VOTO if i != 10], ALTRI | LUNEDI_ALTRI)
    assert mondo.riepilogo(db, TURNO_FINITO) == []
    o = mondo.oggi(db)
    assert o["punti_fatti"] == 61.0 and [p["casa"] for p in o["recuperi"]] == ["atalanta"]
