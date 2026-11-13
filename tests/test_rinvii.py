"""Partite rinviate (fanta/rinvii.py): la regola della lega e l'eccezione per una giornata nelle regole, quali partite sono
rinviate, cosa cambia nelle previsioni (aspetta / senza voto / voto d'ufficio), la giornata in corso, la rotta e il riquadro di Oggi.
Solo dati finti e cartelle temporanee."""
import json
from dataclasses import asdict, replace
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import archivio, consigli, fasi, perche, regole as R, rinvii
from fanta.regole import Regole
import codice_web

ST = "2026-27"


# ---------------------------------------------------------------- regole
def test_predefinito_aspetta_e_regole_vecchie_si_leggono(tmp_path):
    r = Regole()
    assert (r.partite_rinviate, r.voto_ufficio_rinviate, r.rinvii_giornate) == ("aspetta", 6.0, {})
    vecchio = asdict(Regole())
    for k in ("partite_rinviate", "voto_ufficio_rinviate", "rinvii_giornate"):
        vecchio.pop(k)
    f = tmp_path / "regole.json"
    f.write_text(json.dumps(vecchio), encoding="utf-8")            # un file di prima: valgono i predefiniti
    assert R.carica(f).partite_rinviate == "aspetta"
    nuove = replace(Regole(), partite_rinviate="voto_ufficio", voto_ufficio_rinviate=5.5, rinvii_giornate={f"{ST}/12": "senza_voto"})
    R.salva(nuove, f)
    assert R.carica(f) == nuove
    assert R.da_dict(asdict(nuove) | {"voto_ufficio_rinviate": 6}).voto_ufficio_rinviate == 6.0      # 6 senza decimali va bene


@pytest.mark.parametrize("cambio, frase", [
    ({"partite_rinviate": "boh"}, "partite_rinviate"),
    ({"partite_rinviate": 3}, "partite_rinviate deve essere un testo"),
    ({"voto_ufficio_rinviate": 11}, "tra 0 e 10"),
    ({"voto_ufficio_rinviate": "sei"}, "voto_ufficio_rinviate deve essere un numero"),
    ({"rinvii_giornate": {"2026-27/39": "aspetta"}}, "non è del tipo"),
    ({"rinvii_giornate": {"giornata 12": "aspetta"}}, "non è del tipo"),
    ({"rinvii_giornate": {"2026-27/12": "rinvia"}}, "deve essere una di"),
    ({"rinvii_giornate": ["2026-27/12"]}, "rinvii_giornate deve essere"),
    ({"rinvii_giornate": {f"2026-27/{g}": "aspetta" for g in range(1, 39)} | {f"2025-26/{g}": "aspetta" for g in range(1, 39)}
      | {"2024-25/1": "aspetta"}}, "al massimo"),
])
def test_valori_sbagliati_rifiutati(cambio, frase):
    with pytest.raises(ValueError, match=frase):
        R.da_dict(asdict(Regole()) | cambio)


def test_regola_della_giornata_ed_eccezione():
    r = Regole()
    assert rinvii.regola(r, ST, 12) == {"modo": "aspetta", "valore": None, "predefinito": "aspetta", "eccezione": False}
    r = rinvii.con_eccezione(r, ST, 12, "voto_ufficio")
    assert r.rinvii_giornate == {f"{ST}/12": "voto_ufficio"}
    assert rinvii.regola(r, ST, 12) == {"modo": "voto_ufficio", "valore": 6.0, "predefinito": "aspetta", "eccezione": True}
    assert rinvii.regola(r, ST, 13)["modo"] == "aspetta"                     # solo quella giornata
    assert rinvii.regola(r, "2027-28", 12)["modo"] == "aspetta"              # e solo quella stagione
    assert rinvii.con_eccezione(r, ST, 12, None).rinvii_giornate == {}       # tolta
    assert rinvii.con_eccezione(r, ST, 12, "aspetta").rinvii_giornate == {}  # uguale alla regola della lega: non serve
    vecchie = replace(r, rinvii_giornate={"2025-26/3": "senza_voto", f"{ST}/12": "voto_ufficio"})
    assert rinvii.con_eccezione(vecchie, ST, 14, "senza_voto").rinvii_giornate == {f"{ST}/12": "voto_ufficio", f"{ST}/14": "senza_voto"}
    with pytest.raises(ValueError):
        rinvii.con_eccezione(r, ST, 12, "rinvia")


# ---------------------------------------------------------------- quali partite sono rinviate
def test_partite_rinviate_dal_calendario():
    turno = [{"id": i, "data": f"2026-11-0{7 + i % 3} 15:00", "giocata": 0} for i in range(8)]
    recupero = {"id": 8, "data": "2026-12-10 20:45", "giocata": 0}            # rinviata a dicembre
    vecchia = {"id": 9, "data": "2026-10-31 15:00", "giocata": 0}             # data vecchia mai aggiornata
    senza_data = {"id": 10, "data": None, "giocata": 0}
    recuperata = {"id": 11, "data": "2026-12-10 20:45", "giocata": 1}         # già recuperata: i suoi voti valgono
    assert [p["id"] for p in rinvii.rinviate(turno + [recupero, vecchia, senza_data, recuperata])] == [8, 9, 10]
    assert rinvii.rinviate(turno) == []
    assert [p["id"] for p in rinvii.fuori_turno(turno + [recupero, recuperata])] == [8, 11]      # per il Diario: anche recuperate
    assert rinvii.rinviate([{"data": None, "giocata": 0}] * 10) == []        # calendario senza date: nessuna


# ---------------------------------------------------------------- previsioni
def _prev():
    righe = [{"id": 1, "partita": 100, "nome": "Gioca", "ruolo": "A", "p_voto": 0.9, "mu": 7.5, "mu_voto": 6.4, "atteso": 6.75,
              "quota_titolare": 0.9, "e_gol": 0.4, "p_gol": 0.35, "p_imbattuto": 0.0, "data_partita": "2026-11-08 15:00"},
             {"id": 2, "partita": 200, "nome": "Rinviato", "ruolo": "A", "p_voto": 0.8, "mu": 8.0, "mu_voto": 6.5, "atteso": 6.4,
              "quota_titolare": 0.8, "e_gol": 0.5, "p_gol": 0.4, "p_imbattuto": 0.0, "data_partita": "2026-12-10 20:45"},
             {"id": 3, "partita": 200, "nome": "Portiere", "ruolo": "P", "p_voto": 0.95, "mu": 5.0, "mu_voto": 6.0, "atteso": 4.75,
              "quota_titolare": 1.0, "e_gol": 0.0, "p_gol": 0.0, "p_imbattuto": 0.3, "data_partita": "2026-12-10 20:45"}]
    p = pd.DataFrame(righe).set_index("id")
    p["perche_numero"] = pd.Series([[{"chiave": "gol", "testo": "segna", "effetto": 0.8}]] * 3, index=p.index, dtype=object)
    return p


@pytest.mark.parametrize("modo, p2, mu2, atteso3", [("aspetta", 0.8, 8.0, 4.75), ("senza_voto", 0.0, 8.0, 0.0),
                                                     ("voto_ufficio", 1.0, 6.0, 6.0)])
def test_applica_le_tre_regole(modo, p2, mu2, atteso3):
    r = rinvii.regola(replace(Regole(), partite_rinviate=modo), ST, 10)
    prima = _prev()
    p = rinvii.applica(prima, {200}, r)
    assert prima.at[2, "p_voto"] == 0.8                                       # le previsioni di partenza non cambiano
    assert p.at[1, "rinvio"] is None and p.at[1, "p_voto"] == 0.9            # chi gioca: come sempre
    assert (p.at[2, "rinvio"], p.at[2, "p_voto"], p.at[2, "mu"]) == (modo, p2, mu2)
    assert p.at[3, "atteso"] == pytest.approx(atteso3)
    if modo == "voto_ufficio":
        assert p.at[2, "e_gol"] == 0 and p.at[3, "p_imbattuto"] == 0 and p.at[3, "mu_voto"] == 6.0
    motivi = rinvii.perche(p, r, perche.MAX_MOTIVI)
    assert motivi.at[1] == prima.at[1, "perche_numero"]
    assert motivi.at[2][0]["chiave"] == "rinvio" and motivi.at[2][0]["effetto"] is None
    assert len(motivi.at[2]) == (2 if modo == "aspetta" else 1)              # aspettando valgono anche gli altri motivi


def test_frasi():
    assert rinvii.frase("aspetta", None, "2026-12-10 20:45") == "partita rinviata: conta il voto del recupero (gio 10 dic)"
    assert rinvii.frase("aspetta", None, None) == "partita rinviata: conta il voto del recupero (data da definire)"
    assert rinvii.frase("senza_voto", None) == "partita rinviata: in questa giornata non prende voto"
    assert rinvii.frase("voto_ufficio", 5.5) == "partita rinviata: voto d'ufficio 5,5"


def test_previsioni_di_consigli_con_la_regola(tmp_path, monkeypatch):
    """`_calcola_previsioni`: la regola (con l'eccezione della giornata) arriva fino a scheda, motivi e titolarità."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    partite = pd.DataFrame([{"id": 100 + i, "stagione": ST, "giornata": 10, "data": f"2026-11-0{7 + i % 3} 15:00", "giocata": 0}
                            for i in range(9)] + [{"id": 200, "stagione": ST, "giornata": 10, "data": "2026-12-10 20:45", "giocata": 0}])
    base = _prev().reset_index()
    for k, v in {"squadra": "inter", "avversario": "roma", "in_casa": True, "e_assist": 0.1, "e_rigori": 0.0, "p_assist": 0.1,
                 "p_giallo": 0.1, "p_rosso": 0.01, "gol_squadra": 1.5, "gol_avversario": 1.0, "dubbio": False,
                 "diffidato": False, "stato": None, "percentuale": None, "nota": None}.items():
        base[k] = v
    base = base.drop(columns="perche_numero")
    monkeypatch.setattr(consigli.modello, "previsioni", lambda *a, **k: base.copy())
    monkeypatch.setattr(consigli.perche, "calcola", lambda p, regole: (pd.Series([[]] * len(p), index=p.index, dtype=object),
                                                                       pd.Series(6.0, index=p.index)))
    d = NS(partite=partite, calciatori=None)
    regole = rinvii.con_eccezione(Regole(), ST, 10, "senza_voto")
    p, _, _ = consigli._calcola_previsioni(db, d, regole, ST, 10, None)
    s = consigli.scheda_previsione(2, p.loc[2])
    assert (s["rinvio"], s["p_voto"], s["titolarita"]) == ("senza_voto", 0.0, "fuori")
    assert s["motivi"] == ["partita rinviata: in questa giornata non prende voto"]
    assert consigli.scheda_previsione(1, p.loc[1])["rinvio"] is None
    p, _, _ = consigli._calcola_previsioni(db, d, Regole(), ST, 10, None)                      # aspetta: numeri di sempre
    s = consigli.scheda_previsione(2, p.loc[2])
    assert (s["rinvio"], s["p_voto"], s["fv_atteso"]) == ("aspetta", 0.8, 8.0)
    assert s["motivi"][0] == "partita rinviata: conta il voto del recupero (gio 10 dic)"
    assert s["perche_numero"][0]["chiave"] == "rinvio"


# ---------------------------------------------------------------- giornata in corso
TIT = [{"id": 1, "nome": "P", "ruolo": "P", "squadra": "inter"}] + \
      [{"id": i, "nome": f"D{i}", "ruolo": "D", "squadra": "inter"} for i in range(2, 6)] + \
      [{"id": i, "nome": f"C{i}", "ruolo": "C", "squadra": "inter"} for i in range(6, 10)] + \
      [{"id": 10, "nome": "Rinviato", "ruolo": "A", "squadra": "roma"}, {"id": 11, "nome": "A11", "ruolo": "A", "squadra": "inter"}]
PANC = [{"id": 12, "nome": "Riserva", "ruolo": "A", "squadra": "inter"}]
PARTITE = [{"casa": "inter", "trasferta": "milan", "stato": "finita"}, {"casa": "roma", "trasferta": "lazio", "stato": "rinviata"}]
VOTI = {i: {"voto_red": 6.0} for i in list(range(1, 10)) + [11, 12]}


@pytest.mark.parametrize("modo, fatti, stato_cambio, entra", [("aspetta", 61.0, None, None),        # portiere 7 + 9 da 6
                                                               ("senza_voto", 67.0, True, 12),       # + la riserva
                                                               ("voto_ufficio", 67.0, None, None)])  # + il 6 d'ufficio
def test_andamento_con_la_partita_rinviata(modo, fatti, stato_cambio, entra):
    regole = replace(Regole(), partite_rinviate=modo)
    a = fasi.andamento(TIT, PANC, PARTITE, VOTI, {"inter", "milan"}, {10: 6.0}, set(), regole,
                       {10: (0.8, 7.5, 6.3)}, rinvii.regola(regole, ST, 10))
    assert a["punti_fatti"] == fatti
    g10 = next(g for g in a["giocatori"] if g["id"] == 10)
    assert g10["stato"] == "rinviata"
    assert g10["a_punteggio"] is (modo != "senza_voto")
    assert g10["fantavoto"] == (6.0 if modo == "voto_ufficio" else None)
    cambi = [s for s in a["sostituzioni"] if s["esce"]["id"] == 10]
    if stato_cambio is None:
        assert cambi == []
    else:
        assert cambi[0]["certa"] is stato_cambio and cambi[0]["entra"]["id"] == entra
    if modo == "aspetta":                                     # il recupero conta: i suoi punti attesi restano
        assert a["punti_attesi_restanti"] == pytest.approx(0.8 * 7.5 + 0.2 * 6.0, abs=0.6)    # se poi non gioca entra la riserva
    else:
        assert a["punti_attesi_restanti"] == 0.0


# ---------------------------------------------------------------- giornata finita con un recupero da giocare
def _db_giornata(tmp_path, recupero_giocato=False, data_recupero="2026-11-30 20:45"):
    from datetime import datetime as dt
    db = archivio.apri(tmp_path / "f.sqlite")
    righe = [(1, "2026-11-07 15:00", "inter", "milan", 1), (2, "2026-11-08 15:00", "roma", "lazio", 1),
             (3, "2026-11-09 20:45", "napoli", "juve", 1), (4, data_recupero, "atalanta", "parma", int(recupero_giocato))]
    archivio.inserisci(db, "partite", [{"id": i, "stagione": ST, "giornata": 9, "data": d, "casa": c, "trasferta": t_,
                                        "gol_casa": None, "gol_trasferta": None, "giocata": g, "understat_id": None}
                                       for i, d, c, t_, g in righe])
    return db, dt.fromisoformat("2026-11-09 20:45") + fasi.DURATA_PARTITA


@pytest.mark.parametrize("data_recupero", ["2026-11-30 20:45", None, "2026-10-31 15:00"])     # recupero, da definire, data vecchia
def test_la_partita_rinviata_non_tiene_aperta_la_giornata(tmp_path, data_recupero):
    db, fine = _db_giornata(tmp_path, data_recupero=data_recupero)
    assert fasi.fine_giornata(db, ST, 9) == fine
    assert fasi.recuperi_mancanti(db, ST, 9) == [{"casa": "atalanta", "trasferta": "parma", "data": data_recupero}]


def test_giornata_aperta_se_manca_una_partita_del_turno_e_recupero_giocato(tmp_path):
    db, fine = _db_giornata(tmp_path, recupero_giocato=True)
    assert fasi.fine_giornata(db, ST, 9) == fine and fasi.recuperi_mancanti(db, ST, 9) == []
    db.execute("UPDATE partite SET giocata = 0 WHERE id = 3")           # il posticipo del lunedì non è finito
    assert fasi.fine_giornata(db, ST, 9) is None


SIGLE = {"inter": "INT", "roma": "ROM", "atalanta": "ATA"}


# 9 voti da 6 e il portiere con 7 (porta inviolata) = 61; la riserva (7,5) entra solo con «senza voto»; il voto d'ufficio vale 6
@pytest.mark.parametrize("modo, punti, recuperi", [("aspetta", 61.0, 1), ("senza_voto", 68.5, 0), ("voto_ufficio", 67.0, 0)])
def test_riepilogo_con_il_recupero_da_giocare(tmp_path, modo, punti, recuperi):
    """Rose vere con le sigle, come le importa l'utente («ATA»), mentre calendario e voti usano il nome lungo («atalanta»): la
    squadra di ogni giocatore viene dall'archivio. Prima il riepilogo non trovava la partita rinviata di Rinviato e faceva entrare
    la riserva anche con «aspetta» o con il voto d'ufficio (#649); il test sostituiva `_info_rosa` e non lo vedeva."""
    from fanta import lega, scelte
    db, _ = _db_giornata(tmp_path)
    tit = [dict(g, squadra="atalanta") if g["id"] == 10 else g for g in TIT]        # Rinviato gioca la partita rinviata
    giocatori = tit + PANC
    archivio.inserisci(db, "calciatori", [{"id": g["id"], "nome": g["nome"], "ruolo": g["ruolo"], "squadra": SIGLE[g["squadra"]],
                                           "squadra_slug": g["squadra"]} for g in giocatori])
    voto = lambda i, sq, v=6.0: {"stagione": ST, "giornata": 9, "calciatore_id": i, "nome": f"G{i}", "squadra": sq, "ruolo": "C",   # noqa: E731
                                 "voto_red": v, "gol": 0}
    righe = [voto(g["id"], g["squadra"], 7.5 if g["id"] == 12 else 6.0) | {"ruolo": g["ruolo"]} for g in giocatori if g["id"] in VOTI]
    righe += [voto(100 + n, sq) for n, sq in enumerate(("milan", "roma", "lazio", "napoli", "juve"))]   # tutte le partite giocate
    archivio.inserisci(db, "voti", righe)
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(g["id"], g["nome"], g["ruolo"], SIGLE[g["squadra"]]) for g in giocatori])],
                     "Mia")
    scelte.salva(ST, 9, [g["id"] for g in tit], "4-4-2", tmp_path / "scelte.json", panchina=[12])
    r = fasi.blocco_riepilogo(db, replace(Regole(), partite_rinviate=modo), rose, ST, 9, tmp_path / "scelte.json", None)
    assert r["formazione_di"] == "tua" and r["punti_fatti"] == punti and len(r["recuperi"]) == recuperi
    if recuperi:
        assert r["recuperi"][0]["casa"] == "atalanta"


def test_riepilogo_ha_il_menu_per_decidere_la_giornata(tmp_path, monkeypatch):
    db, _ = _db_giornata(tmp_path)
    monkeypatch.setattr(fasi, "_info_rosa", lambda rose, prev: {g["id"]: g for g in TIT + PANC})
    monkeypatch.setattr(fasi, "schierata", lambda *a, **k: None)
    monkeypatch.setattr(fasi.diario, "carica", lambda f=None: {"giornate": {f"{ST}/9": {"consigliata": {"reale": 70, "atteso": 68}}}})
    r = fasi.blocco_riepilogo(db, Regole(), None, ST, 9, None, "diario.json")
    assert r["rinvio"]["modo"] == "aspetta" and r["rinvio"]["giornata"] == 9 and r["rinvio"]["modi"][0] == "aspetta"
    assert len(r["recuperi"]) == 1
    db.execute("UPDATE partite SET giocata = 1")                         # recupero giocato: niente menu
    assert fasi.blocco_riepilogo(db, Regole(), None, ST, 9, None, "diario.json")["rinvio"] is None


# ---------------------------------------------------------------- Diario: giornata chiusa dal turno se la regola non aspetta
@pytest.mark.parametrize("modo, chiusa", [("aspetta", False), ("senza_voto", True), ("voto_ufficio", True)])
def test_giornate_chiuse_per_la_lega(tmp_path, modo, chiusa):
    db, _ = _db_giornata(tmp_path)
    regole = replace(Regole(), partite_rinviate=modo)
    assert (9 in rinvii.giornate_chiuse(db, ST, regole)) is chiusa
    assert (9 in rinvii.giornate_chiuse(db, ST, rinvii.con_eccezione(Regole(), ST, 9, modo))) is chiusa     # anche per eccezione
    db.execute("UPDATE partite SET giocata = 0 WHERE id = 3")             # manca una partita del turno: mai chiusa
    assert 9 not in rinvii.giornate_chiuse(db, ST, regole)
    assert rinvii.ha_fuori_turno(db, ST, 9)


def test_diario_scrive_la_giornata_con_il_recupero_da_giocare(tmp_path, monkeypatch):
    """`_db_giornata` con «senza voto»: la voce della giornata 9 c'è subito, senza aspettare il recupero; con «aspetta» no."""
    from fanta import diario, lega
    db, _ = _db_giornata(tmp_path)
    partite = pd.read_sql_query("SELECT id, stagione, giornata, data, giocata FROM partite", db)
    voti = pd.DataFrame([{"stagione": ST, "giornata": 9, "calciatore_id": i, "voto_red": 6.0} for i in range(1, 21)])
    monkeypatch.setattr(consigli, "dati", lambda db_: NS(partite=partite, voti=voti))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(diario, "previsioni", lambda d, stagione, giornata, regole, par: pd.DataFrame([
        {"id": i, "nome": f"G{i}", "ruolo": RUOLI_D[i - 1], "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.0, "atteso": 5.4,
         "partita": 4 if i > 20 else 1} for i in range(1, 26)]))
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI_D[i - 1], "INT") for i in range(1, 26)])], "Mia")
    f = tmp_path / "diario.json"
    assert diario.aggiorna(db, Regole(), rose, f, simulazioni=30) == 0                  # aspetta: si aspetta il recupero
    assert diario.aggiorna(db, replace(Regole(), partite_rinviate="senza_voto"), rose, f, simulazioni=30) == 1
    voce = diario.carica(f)["giornate"][f"{ST}/9"]
    # senza voto: chi ha la partita rinviata conta zero e lascia il posto alle riserve (tutte da 6): 11 voti da 6
    assert voce["consigliata"]["reale"] == 66.0
    assert {g["id"] for g in voce["giocatori"]} >= {21, 25}                        # i numeri del modello ci sono anche per loro


# ---------------------------------------------------------------- Oggi: blocco e rotta
def test_blocco_di_oggi():
    partite = [{"casa": "inter", "trasferta": "milan", "data": "2026-11-08 15:00", "stato": "da_giocare"},
               {"casa": "roma", "trasferta": "lazio", "data": "2026-12-10 20:45", "stato": "rinviata"}]
    mie = [{"id": 1, "nome": "Uno", "ruolo": "A", "squadra": "roma"}, {"id": 2, "nome": "Due", "ruolo": "D", "squadra": "inter"}]
    regole = replace(Regole(), prima_giornata_lega=4)
    b = rinvii.blocco_oggi(regole, ST, 10, partite, mie)
    assert b["modo"] == "aspetta" and b["giornata"] == 10 and b["giornata_lega"] == 7 and b["voto_ufficio"] == 6.0
    assert b["partite"] == [{"casa": "roma", "trasferta": "lazio", "data": "2026-12-10 20:45"}]
    assert [g["id"] for g in b["miei"]] == [1] and b["modi"] == ["aspetta", "senza_voto", "voto_ufficio"]
    assert rinvii.blocco_oggi(regole, ST, 10, partite[:1], mie) is None
    assert rinvii.blocco_oggi(regole, ST, None, partite, mie) is None


# ---------------------------------------------------------------- Diario (giornata finita, partita recuperata settimane dopo)
RUOLI_D = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori; gli attaccanti 21-25 giocano la partita rinviata


@pytest.mark.parametrize("modo, reale", [("aspetta", 11 * 6 + 3), ("voto_ufficio", 11 * 6), ("senza_voto", None)])
def test_diario_con_la_partita_rinviata(monkeypatch, modo, reale):
    from fanta import diario
    partite = pd.DataFrame([{"id": 1, "stagione": ST, "giornata": 1, "data": "2026-09-01 18:00", "giocata": 1},
                            {"id": 3, "stagione": ST, "giornata": 1, "data": "2026-09-01 20:45", "giocata": 1},
                            {"id": 4, "stagione": ST, "giornata": 1, "data": "2026-09-02 18:00", "giocata": 1},
                            {"id": 2, "stagione": ST, "giornata": 1, "data": "2026-10-20 20:45", "giocata": 1}])     # recupero
    voti = pd.DataFrame([{"stagione": ST, "giornata": 1, "calciatore_id": i, "voto_red": 9.0 if i == 25 else 6.0} for i in range(1, 26)])
    dati = NS(partite=partite, voti=voti)
    monkeypatch.setattr(diario, "previsioni", lambda d, stagione, giornata, regole, par: pd.DataFrame([
        {"id": i, "nome": f"G{i}", "ruolo": RUOLI_D[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0, "atteso": 5.0,
         "partita": 2 if i > 20 else 1} for i in range(1, 26)]))
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    regole = replace(Regole(), partite_rinviate=modo)
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]               # 3-4-3 con due attaccanti della partita rinviata
    v = diario.calcola_giornata(dati, ST, 1, regole, None, list(range(1, 26)), {"titolari": scelti, "panchina": [2, 22]},
                                simulazioni=50)
    if reale is not None:
        assert v["schierata"]["reale"] == reale                      # aspetta: il 9 del recupero; d'ufficio: 6 per tutti
    else:
        assert v["schierata"]["reale"] == 9 * 6          # 21 e 25 senza voto e in panchina nessuno può entrare (22 ha la stessa partita)
    numeri = {g["id"]: g for g in v["giocatori"]}
    assert numeri[25]["fv"] == 9.0 and numeri[25]["fv_atteso"] == pytest.approx(6.75)     # «Quanto ci abbiamo preso»: il modello
    base = diario.impronta_regole(Regole())
    assert v["regole"] == (base if modo == "aspetta" else diario.impronta_regole(regole, ST, 1, True))
    assert (diario.impronta_regole(regole, ST, 1, True) == base) is (modo == "aspetta")
    assert diario.impronta_regole(regole, ST, 1, False) == base        # giornata senza partite fuori dal turno: nessun ricalcolo
    assert diario.impronta_regole(Regole(), ST, 1, True) == base       # predefinito: le voci di prima restano


@pytest.mark.parametrize("modo", ["aspetta", "voto_ufficio", "senza_voto"])
def test_diario_chi_ha_giocato_un_anticipo_di_settimane_tiene_il_suo_voto(monkeypatch, modo):
    """Coordinatore, #695: la partita 2 della giornata 1 è giocata il 10 agosto, tre settimane prima del turno (1-2 settembre), che
    comincia prima della giornata 2 (8 settembre): è un anticipo lontano (Supercoppa, coppe), non una partita rinviata. Chi l'ha
    giocata tiene il suo voto con qualunque regola dei rinvii (prima: senza voto o voto d'ufficio)."""
    from fanta import diario
    partite = pd.DataFrame([{"id": 2, "stagione": ST, "giornata": 1, "data": "2026-08-10 20:45", "giocata": 1},     # anticipo
                            {"id": 1, "stagione": ST, "giornata": 1, "data": "2026-09-01 18:00", "giocata": 1},
                            {"id": 3, "stagione": ST, "giornata": 1, "data": "2026-09-01 20:45", "giocata": 1},
                            {"id": 4, "stagione": ST, "giornata": 1, "data": "2026-09-02 18:00", "giocata": 1},
                            {"id": 5, "stagione": ST, "giornata": 2, "data": "2026-09-08 18:00", "giocata": 0}])
    assert rinvii.id_fuori_turno(partite, ST, 1) == set()
    voti = pd.DataFrame([{"stagione": ST, "giornata": 1, "calciatore_id": i, "voto_red": 9.0 if i == 25 else 6.0} for i in range(1, 26)])
    monkeypatch.setattr(diario, "previsioni", lambda d, stagione, giornata, regole, par: pd.DataFrame([
        {"id": i, "nome": f"G{i}", "ruolo": RUOLI_D[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0, "atteso": 5.0,
         "partita": 2 if i > 20 else 1} for i in range(1, 26)]))
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    v = diario.calcola_giornata(NS(partite=partite, voti=voti), ST, 1, replace(Regole(), partite_rinviate=modo), None,
                                list(range(1, 26)), {"titolari": scelti, "panchina": [2, 22]}, simulazioni=50)
    assert v["schierata"]["reale"] == 11 * 6 + 3                     # il 9 del 25, che ha giocato l'anticipo


def test_diario_chi_non_ha_previsione_e_ha_la_partita_rinviata_prende_il_voto_d_ufficio(monkeypatch):
    """Revisione di #461: il portiere di riserva senza previsione (#447) gioca con la Roma, partita rinviata e recuperata dopo;
    con la regola «voto d'ufficio» la lega gli dà il voto fisso, come agli altri della stessa partita. La partita si trova dal club."""
    from fanta import diario
    partite = pd.DataFrame([{"id": 1, "stagione": ST, "giornata": 1, "data": "2026-09-01 18:00", "giocata": 1, "casa": "inter", "trasferta": "milan"},
                            {"id": 3, "stagione": ST, "giornata": 1, "data": "2026-09-01 20:45", "giocata": 1, "casa": "napoli", "trasferta": "como"},
                            {"id": 4, "stagione": ST, "giornata": 1, "data": "2026-09-02 18:00", "giocata": 1, "casa": "genoa", "trasferta": "parma"},
                            {"id": 2, "stagione": ST, "giornata": 1, "data": "2026-10-20 20:45", "giocata": 1, "casa": "roma", "trasferta": "lazio"}])
    voti = pd.DataFrame([{"stagione": ST, "giornata": 1, "calciatore_id": i, "voto_red": 6.0} for i in range(1, 26)])
    calciatori = pd.DataFrame([{"id": i, "squadra_slug": "roma" if i == 2 or i > 20 else "inter"} for i in range(1, 26)])
    dati = NS(partite=partite, voti=voti, calciatori=calciatori)
    monkeypatch.setattr(diario, "previsioni", lambda d, stagione, giornata, regole, par: pd.DataFrame([
        {"id": i, "nome": f"G{i}", "ruolo": RUOLI_D[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0, "atteso": 5.0,
         "partita": 2 if i > 20 else 1} for i in range(1, 26) if i != 2]))             # il portiere 2 non ha una previsione
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    regole = replace(Regole(), partite_rinviate="voto_ufficio", voto_ufficio_rinviate=6.5)
    rosa = {i: (f"G{i}", RUOLI_D[i - 1]) for i in range(1, 26)}
    scelti = [2, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]               # il portiere 2 e due attaccanti della stessa partita
    v = diario.calcola_giornata(dati, ST, 1, regole, None, list(range(1, 26)), {"titolari": scelti}, simulazioni=50,
                                giocatori_rosa=rosa)
    assert v["schierata"]["reale"] == 8 * 6 + 3 * 6.5               # 2, 21 e 25: il voto d'ufficio, non il 6 del recupero


# ---------------------------------------------------------------- rotte (account finti, cartelle temporanee)
from test_etag import mondo  # noqa: E402,F401 (fixture: account e dati isolati)
from test_limiti import ambiente, nuovo_utente  # noqa: E402,F401


def test_rotta_eccezione_della_giornata(mondo):
    a, _ = nuovo_utente("utentea")
    r = a.put("/api/regole/rinvio", json={"giornata": 12, "modo": "voto_ufficio"})
    assert r.status_code == 200, r.text
    assert r.json() == {"stagione": ST, "giornata": 12, "modo": "voto_ufficio", "valore": 6.0, "predefinito": "aspetta",
                        "eccezione": True}
    assert a.get("/api/regole").json()["rinvii_giornate"] == {f"{ST}/12": "voto_ufficio"}
    vecchio = a.get("/api/regole").json()                                    # un client vecchio rimanda le regole senza i campi nuovi
    for k in ("partite_rinviate", "voto_ufficio_rinviate", "rinvii_giornate"):
        vecchio.pop(k)
    assert a.put("/api/regole", json=vecchio).status_code == 200
    assert a.get("/api/regole").json()["rinvii_giornate"] == {f"{ST}/12": "voto_ufficio"}    # non si perdono
    r = a.put("/api/regole/rinvio", json={"giornata": 12, "modo": None})
    assert r.json()["eccezione"] is False and a.get("/api/regole").json()["rinvii_giornate"] == {}
    for sbagliato in ({"giornata": 0, "modo": "aspetta"}, {"giornata": 39}, {"giornata": 12, "modo": "rinvia"},
                      {"giornata": 12, "stagione": "../x"}, {"modo": "aspetta"}):
        assert a.put("/api/regole/rinvio", json=sbagliato).status_code in (400, 422), sbagliato
    a.put("/api/regole/rinvio", json={"giornata": 12, "modo": "senza_voto"})
    r = a.put("/api/regole/rinvio", json={"giornata": 12, "modo": "voto_ufficio", "stagione": "2019-20"})
    assert r.status_code == 400 and "stagione in corso" in r.json()["detail"]
    assert a.get("/api/regole").json()["rinvii_giornate"] == {f"{ST}/12": "senza_voto"}        # una stagione sbagliata non cancella
    a.put("/api/regole/rinvio", json={"giornata": 12, "modo": None})
    etag = a.get("/api/regole").headers["etag"]
    a.put("/api/regole", json=a.get("/api/regole").json() | {"nome_lega": "Cambiata altrove"})
    assert a.put("/api/regole/rinvio", json={"giornata": 12, "modo": "senza_voto"}, headers={"If-Match": etag}).status_code == 412


# ---------------------------------------------------------------- web
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402


APP = codice_web.app()


def test_web_regole_e_risorsa():
    assert 'if (p === "/api/regole" || p === "/api/regole/rinvio") return "regole";' in APP     # stesso ETag delle regole
    assert 'r.partite_rinviate !== undefined ?' in APP                          # server vecchio: niente sezione
    assert 'nuove.partite_rinviate = $("#rinvio-modo .attivo").dataset.valore;' in APP
    assert "cardRinvio(o.rinvio)" in APP and "collegaRinvio();" in APP


@pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")
def test_web_riquadro_del_rinvio():
    inizio, fine = APP.index("const MODI_RINVIO"), APP.index("function collegaRinvio(")
    num = re.search(r"^const num = .*$", APP, re.M).group(0)
    testi = codice_web.leggi("testi.js")
    stub = """const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const sigla = s => esc((s || "").slice(0, 3).toUpperCase());
const parseData = s => s ? new Date(String(s).replace(" ", "T")) : null; const quando = s => "QUANDO(" + s + ")";"""
    rv = {"stagione": ST, "giornata": 12, "modo": "voto_ufficio", "valore": 5.5, "voto_ufficio": 5.5, "predefinito": "aspetta",
          "eccezione": True, "modi": ["aspetta", "senza_voto", "voto_ufficio"],
          "partite": [{"casa": "roma", "trasferta": "lazio", "data": "2026-12-10 20:45"}, {"casa": "como", "trasferta": "milan", "data": None}],
          "miei": [{"id": 1, "nome": "Rossi <b>", "ruolo": "A", "squadra": "roma"}]}
    codice = f"""{testi}\n{num}\n{stub}\n{APP[inizio:fine]}
console.log(JSON.stringify([cardRinvio({json.dumps(rv)}), cardRinvio(null), cardRinvio({{"partite": []}})]));"""
    r = subprocess.run([shutil.which("node"), "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    html, vuoto, vuoto2 = json.loads(r.stdout)
    assert vuoto == vuoto2 == ""
    assert "Partite rinviate" in html and "ROM vs LAZ" in html and "ROM–LAZ" not in html and "recupero QUANDO(2026-12-10 20:45)" in html
    assert "recupero da definire" in html
    assert "Rossi &lt;b&gt;" in html and "<b>" not in html.replace("<b>ROM", "").replace("<b>COM", "")    # nome con HTML: escapato
    assert '<option value="voto_ufficio" selected>' in html and "voto d&#39;ufficio" not in html
    assert "prendono il voto d'ufficio (5,5)" in html
    assert "Di solito la tua lega: aspettano il recupero" in html
    # i recuperi che mancano e il menu del rinvio a giornata finita: tests/test_etichette_coerenti_web.py e tests/browser/
