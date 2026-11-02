"""Lettori delle fonti, provati su estratti delle pagine vere (tests/dati) e su dati costruiti a mano."""
from pathlib import Path

import pytest

from fanta import squadre
from fanta.fonti import fantacalcio as fc
from fanta.fonti import understat as us
from fanta.listone import Calciatore

DATI = Path(__file__).parent / "dati"
SLUG = {"atalanta", "bologna", "cagliari", "como", "fiorentina", "frosinone", "genoa", "inter", "juventus", "lazio",
        "lecce", "milan", "monza", "napoli", "parma", "roma", "sassuolo", "torino", "udinese", "venezia", "verona"}

def _leggi(nome):
    return (DATI / nome).read_text(encoding="utf-8")

# ---------- Fantacalcio.it ----------
def test_calendario_solo_la_giornata_chiesta():
    partite = fc.leggi_calendario(_leggi("calendario_1.html"), 1, "2026-27")
    assert len(partite) == 10                         # il riquadro di un'altra giornata è scartato
    p = partite[0]
    assert (p["id"], p["casa"], p["trasferta"], p["gol_casa"], p["gol_trasferta"], p["giocata"]) == \
        (17959, "inter", "monza", 4, 1, 1)
    assert p["data"] == "2026-08-22 18:30"
    assert fc.leggi_calendario(_leggi("calendario_1.html"), 2, "2026-27") == []

def test_calendario_giornata_ripetuta_nella_pagina():
    html = _leggi("calendario_1.html").replace("<ul class='match-list'>", "<ul class='match-list'>" * 1)
    doppia = html.replace("</ul></body>", html.split("<ul class='match-list'>", 1)[1].rsplit("</ul>", 1)[0] + "</ul></body>")
    assert len(fc.leggi_calendario(doppia, 1, "2026-27")) == 10

def test_voti():
    righe = fc.leggi_voti(_leggi("voti_8.html"), 8)
    assert righe and all(r["ruolo"] in "PDCA" for r in righe)          # niente allenatori
    per_nome = {r["nome"]: r for r in righe}
    k = per_nome["Bomberovic"]
    assert (k["calciatore_id"], k["squadra"], k["gol"], k["assist"], k["voto_red"], k["fv_red"]) == \
        (9435, "atalanta", 2, 1, 8.5, 15.5)
    assert k["sostituito"] == 1
    e = per_nome["Regista D.S."]
    assert e["ammonizioni"] == 1 and e["rig_segnati"] == 1
    assert any(r["voto_red"] is None and r["subentrato"] for r in righe)   # senza voto ("55") = None

def test_voti_giornata_sbagliata():
    with pytest.raises(ValueError):
        fc.leggi_voti(_leggi("voti_8.html"), 7)

def test_probabili():
    giornata, righe = fc.leggi_probabili(_leggi("probabili.html"))
    assert giornata == 9
    per_id = {r["calciatore_id"]: r for r in righe}
    titolari = [r for r in righe if r["stato"] == "titolare"]
    assert len(titolari) == 22 and {r["squadra"] for r in titolari} == {"sassuolo", "lazio"}
    assert per_id[4236]["percentuale"] == 75 and per_id[4236]["stato"] == "titolare"      # portiere del Sassuolo
    assert per_id[9672]["stato"] == "infortunato" and "quadricipite" in per_id[9672]["nota"]
    dubbio = per_id[9038]
    assert (dubbio["stato"], dubbio["in_dubbio"], dubbio["percentuale"]) == ("panchina", 1, 25)
    assert all(r["partita_id"] == 18042 for r in righe)

# ---------- squadre ----------
@pytest.mark.parametrize("nome,atteso", [
    ("AC Milan", "milan"), ("Parma Calcio 1913", "parma"), ("Inter", "inter"), ("Hellas Verona", "verona"),
    ("Verona", "verona"), ("Roma", "roma"), ("Internazionale", "inter"), ("Pisa", None),
])
def test_slug_squadre(nome, atteso):
    assert squadre.slug(nome, SLUG) == atteso

# ---------- Understat ----------
def _c(id, nome, ruolo, slug):
    return Calciatore(id, nome, ruolo, "", slug[:3].upper(), slug, 10, 10, 100)

@pytest.mark.parametrize("fc_nome,us_nome,positivo", [
    ("Martinez L.", "Lautaro Martínez", True),
    ("Martinez Jo.", "Josep Martínez", True),
    ("Martinez Jo.", "Lautaro Martínez", False),
    ("Esposito F.P.", "Francesco Pio Esposito", True),
    ("Hojlund", "Rasmus Højlund", True),
    ("Delprato", "Enrico Del Prato", True),
    ("Floriani Mussolini", "Romano Floriani", True),
    ("Kevin Carlos", "Kevin Omoruyi", False),       # stesso giocatore, ma lo riconosce solo l'elenco dei soprannomi
    ("N'Dicka", "Evan Ndicka", True),
    ("Ederson D.S.", "Ederson", True),
    ("Traorè Hj.", "Hamed Junior Traore", True),
    ("Rossi A.", "Nicolo Rossi", False),
    ("Barella", "Nicolò Bastoni", False),
])
def test_punteggio_nomi(fc_nome, us_nome, positivo):
    p = us.punteggio(fc_nome, us_nome)
    assert (p >= 2) == positivo, p

def test_abbina_uno_a_uno_nella_squadra():
    calciatori = [_c(1, "Martinez L.", "A", "inter"), _c(2, "Martinez Jo.", "P", "inter"),
                  _c(3, "Thuram", "A", "inter"), _c(4, "Thuram K.", "C", "juventus"), _c(5, "Konè M.", "C", "roma"),
                  _c(6, "Rossi A.", "D", "inter")]
    giocatori = [{"understat_giocatore": 10, "nome": "Lautaro Martínez", "squadre": "Inter"},
                 {"understat_giocatore": 11, "nome": "Josep Martínez", "squadre": "Inter"},
                 {"understat_giocatore": 12, "nome": "Marcus Thuram", "squadre": "Inter"},
                 {"understat_giocatore": 13, "nome": "Khéphren Thuram", "squadre": "Juventus"},
                 {"understat_giocatore": 14, "nome": "Kouadio Kone", "squadre": "Roma"},
                 {"understat_giocatore": 15, "nome": "Mario Rossi", "squadre": "Inter"}]
    e = us.abbina(giocatori, calciatori, lambda n: squadre.slug(n, SLUG))
    # Kouadio Kone = Konè M. grazie ai soprannomi; "Mario Rossi" NON è "Rossi A." (iniziale diversa)
    assert {k: v[0] for k, v in e.items()} == {10: 1, 11: 2, 12: 3, 13: 4, 14: 5}

def test_abbina_soprannome():
    calciatori = [_c(1, "Kevin Carlos", "A", "cagliari"), _c(2, "Valdepenas", "D", "fiorentina")]
    giocatori = [{"understat_giocatore": 10, "nome": "Kevin Omoruyi", "squadre": "Cagliari"},
                 {"understat_giocatore": 11, "nome": "Valde", "squadre": "Fiorentina"}]
    assert {k: v[0] for k, v in us.abbina(giocatori, calciatori, lambda n: squadre.slug(n, SLUG)).items()} == {10: 1, 11: 2}

def test_abbina_trasferito():
    calciatori = [_c(1, "Malen", "A", "roma")]
    giocatori = [{"understat_giocatore": 10, "nome": "Donyell Malen", "squadre": "Aston Villa"}]
    assert us.abbina(giocatori, calciatori, lambda n: squadre.slug(n, SLUG)) == {10: (1, "altra_squadra")}

def test_leggi_partita_rigori_e_punizioni():
    dati = {
        "rosters": {"h": {"1": {"player_id": "7", "time": "90", "goals": "1", "own_goals": "0", "shots": "3",
                                "xG": "1.2", "xA": "0.1", "assists": "0", "key_passes": "1", "position": "FW",
                                "yellow_card": "1", "red_card": "0", "roster_in": "0", "roster_out": "0"},
                          "2": {"player_id": "8", "time": "0", "goals": "0", "shots": "0", "xG": "0", "xA": "0",
                                "assists": "0", "key_passes": "0"}},
                    "a": {"3": {"player_id": "9", "time": "20", "goals": "0", "own_goals": "0", "shots": "1",
                                "xG": "0.05", "xA": "0", "assists": "0", "key_passes": "0", "position": "Sub",
                                "yellow_card": "0", "red_card": "0", "roster_in": "77", "roster_out": "0"}}},
        "shots": {"h": [{"player_id": "7", "situation": "Penalty", "result": "Goal"},
                        {"player_id": "7", "situation": "Penalty", "result": "SavedShot"},
                        {"player_id": "7", "situation": "DirectFreekick", "result": "MissedShots"}],
                  "a": [{"player_id": "9", "situation": "OpenPlay", "result": "MissedShots"}]},
    }
    righe = {r["understat_giocatore"]: r for r in us.leggi_partita(dati, 500, "inter", "roma")}
    assert set(righe) == {7, 9}                      # chi ha 0 minuti non c'è
    assert (righe[7]["rigori_calciati"], righe[7]["rigori_segnati"], righe[7]["punizioni"], righe[7]["gialli"]) == (2, 1, 1, 1)
    assert righe[7]["squadra"] == "inter" and righe[9]["squadra"] == "roma"
    assert righe[9]["entrato"] == 1 and righe[7]["entrato"] == 0

def test_calendario_altra_stagione_scartata():
    assert fc.leggi_calendario(_leggi("calendario_1.html"), 1, "2027-28") == []

def test_voti_stagione_passata_hanno_il_codice():
    righe = fc.leggi_voti(_leggi("voti_2025-26_38.html"), 38)
    assert righe and all(isinstance(r["calciatore_id"], int) for r in righe)
