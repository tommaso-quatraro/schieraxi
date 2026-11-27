"""Scheda di un giocatore (fanta/scheda.py): l'andamento dei fantavoti lo decide il server (#895), i client lo mostrano.
Solo dati inventati."""
import pytest

from fanta import archivio, fasi, scheda
from fanta.regole import Bonus, Regole


def _voti(*fv):
    return [{"giornata": g, "fv": v} for g, v in enumerate(fv, start=1)]


@pytest.mark.parametrize("fv, atteso", [
    ((), None),                                        # nessuna presenza: niente andamento
    ((6.0, 7.0, None), "pochi_dati"),                  # meno di 4 voti veri
    ((6.0, 6.0, 6.0, 8.0, 8.0, 8.0), "in_crescita"),   # media delle ultime 3 (8) contro tutte (7): +1
    ((8.0, 8.0, 8.0, 6.0, 6.0, 6.0), "in_calo"),
    ((6.0, 6.5, 6.0, 6.5, 6.0, 6.5), "stabile"),
    ((6.0, 6.0, None, 6.0, 7.0, 7.0), "stabile"),      # senza voto non conta: ultime 3 (6,7) contro tutte (6,4), sotto 0,6
    ((5.0, 5.0, 5.0, 8.0, None, 8.0, 8.0), "in_crescita"),
])
def test_andamento_dei_fantavoti(fv, atteso):
    assert scheda.andamento(_voti(*fv)) == atteso


def test_la_scheda_porta_l_andamento(tmp_path):
    """GET /api/giocatore manda `andamento` accanto ai voti: la web e l'iPhone mostrano la parola, non la ricalcolano."""
    from fanta import archivio
    db = archivio.apri(tmp_path / "fanta.sqlite")
    archivio.inserisci(db, "calciatori", [{"id": 7, "nome": "Rossi", "ruolo": "C", "squadra": "INT", "squadra_slug": "inter"}])
    zero = dict.fromkeys(("gol", "assist", "ammonizioni", "espulsioni", "gol_subiti", "rig_segnati", "rig_sbagliati", "rig_parati",
                          "autogol", "subentrato", "sostituito"), 0)
    archivio.inserisci(db, "voti", [{"stagione": "2026-27", "giornata": g, "calciatore_id": 7, "nome": "Rossi", "squadra": "inter", "ruolo": "C",
                                     "voto_red": v, "fv_red": v} | zero for g, v in enumerate((6.0, 6.0, 6.0, 8.0, 8.0, 8.0), start=1)])
    s = scheda.scheda(db, 7, "2026-27", Regole())
    assert [v["fv"] for v in s["voti"]] == [6.0, 6.0, 6.0, 8.0, 8.0, 8.0] and s["andamento"] == "in_crescita"


# ---------------------------------------------------------------- i fantavoti con le regole della lega (26/11/2026)
ST = "2026-27"
# una lega con bonus e malus diversi da quelli di Fantacalcio.it (tra parentesi): gol del difensore 4,5 (3), assist 1,5 (1),
# ammonizione -1 (-0,5), rigore segnato 2 (3), rigore parato 4 (3), gol subito dal portiere -1,5 (-1), porta inviolata 1,5 (1)
LEGA = Regole(bonus=Bonus(gol={"P": 3.0, "D": 4.5, "C": 3.0, "A": 3.0}, assist=1.5, ammonizione=-1.0, rigore_segnato=2.0,
                          rigore_parato=4.0, gol_subito_portiere=-1.5, portiere_imbattuto=1.5))
CAMPI_VOTI = ("gol", "assist", "ammonizioni", "espulsioni", "gol_subiti", "rig_segnati", "rig_sbagliati", "rig_parati", "autogol", "mvp",
              "subentrato", "sostituito")
# id: (nome, ruolo, {giornata: campi della riga dei voti}); i campi che mancano valgono 0. `fv_red` è il fantavoto già pronto di
# Fantacalcio.it, con i bonus classici: la scheda non lo deve usare
GIOCATORI = {
    7: ("Verdi", "D", {1: {"voto_red": 6.0, "fv_red": 6.0}, 2: {"voto_red": 6.0, "fv_red": 6.0}, 3: {"voto_red": None, "fv_red": None},
                       4: {"voto_red": 6.5, "ammonizioni": 1, "fv_red": 6.0}, 5: {"voto_red": 6.0, "fv_red": 6.0},
                       6: {"voto_red": 6.0, "gol": 1, "fv_red": 9.0}, 7: {"voto_red": 5.5, "assist": 1, "fv_red": 6.5}}),
    8: ("Neri", "P", {1: {"voto_red": 6.0, "fv_red": 7.0}, 2: {"voto_red": 6.5, "gol_subiti": 2, "fv_red": 4.5},
                      3: {"voto_red": 7.0, "gol_subiti": 1, "rig_parati": 1, "fv_red": 9.0}, 4: {"voto_red": None, "fv_red": None}}),
    9: ("Bianchi", "A", {1: {"voto_red": 6.5, "rig_segnati": 1, "fv_red": 9.5}, 2: {"voto_red": 5.5, "rig_sbagliati": 1, "fv_red": 4.5},
                         3: {"voto_red": 6.0, "gol": 1, "rig_segnati": 1, "fv_red": 12.0}}),
}


def _giocatori(db, ruoli: dict | None = None) -> None:
    """I giocatori di GIOCATORI nell'archivio; `ruoli` ({id: ruolo}) cambia il ruolo del listone."""
    ruoli = ruoli or {}
    archivio.inserisci(db, "calciatori", [{"id": i, "nome": n, "ruolo": ruoli.get(i, r), "squadra": "GEN", "squadra_slug": "genoa"}
                                          for i, (n, r, _) in GIOCATORI.items()])
    archivio.inserisci(db, "voti", [{"stagione": ST, "giornata": g, "calciatore_id": i, "nome": n, "squadra": "genoa", "ruolo": r}
                                    | dict.fromkeys(CAMPI_VOTI, 0) | campi
                                    for i, (n, r, voti) in GIOCATORI.items() for g, campi in voti.items()])
    db.commit()


@pytest.mark.parametrize("cid, attesi, fantamedia", [
    (7, [6.0, 6.0, None, 5.5, 6.0, 10.5, 7.0], 6.83),    # 6 + 4,5 del gol, non il 9 di Fantacalcio.it; con i bonus classici 6,58
    (8, [7.5, 3.5, 9.5, None], 6.83),                  # porta inviolata +1,5, due gol subiti -3, un gol subito e un rigore parato +2,5
    (9, [8.5, 4.5, 11.0], 8.0),                        # rigore segnato +2, rigore sbagliato -1, gol e rigore +5
])
def test_la_scheda_conta_i_fantavoti_con_i_bonus_della_lega(tmp_path, cid, attesi, fantamedia):
    """Difetto del 26/11/2026: la scheda prendeva i fantavoti già pronti di Fantacalcio.it (`fv_red`), con i bonus classici, mentre
    Formazione, Oggi e Giornate li calcolano con le regole della lega: un difensore che prende 6 e segna faceva 10,5 in Giornate e 9
    nella scheda. Ora pallini, grafico, fantamedia e andamento hanno lo stesso fantavoto delle altre schermate."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db)
    s = scheda.scheda(db, cid, ST, LEGA)
    fv = [v["fv"] for v in s["voti"]]
    assert fv == attesi and s["stagione"]["fantamedia"] == fantamedia
    # lo stesso numero di «fv_preso» in Formazione e Oggi (fasi._fantavoti_presi), giornata per giornata
    for g, atteso in zip(GIOCATORI[cid][2], fv):
        assert fasi._fantavoti_presi(db, LEGA, ST, g, {cid: {"ruolo": GIOCATORI[cid][1]}}).get(cid) == atteso


def test_ultime_cinque_e_andamento_con_i_bonus_della_lega(tmp_path):
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db)
    s = scheda.scheda(db, 7, ST, LEGA)
    assert s["stagione"]["ultime_5_fv"] == [None, 5.5, 6.0, 10.5, 7.0]
    # media delle ultime 3 contro tutte: +1 con i bonus della lega (in crescita), +0,58 con quelli classici (stabile)
    assert s["andamento"] == "in_crescita"
    assert scheda.scheda(db, 7, ST, Regole())["andamento"] == "stabile"


def test_la_scheda_parte_dal_voto_scelto_dalla_lega(tmp_path):
    """Il voto di partenza è quello delle regole (`fonte_voto`), come in Formazione e Giornate."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db)
    db.execute("UPDATE voti SET voto_stat = voto_red + 1 WHERE voto_red IS NOT NULL")
    s = scheda.scheda(db, 7, ST, Regole(fonte_voto="statistico"))
    assert [v["voto"] for v in s["voti"]][:2] == [7.0, 7.0] and [v["fv"] for v in s["voti"]][5] == 10.0     # 7 + 3 del gol


def test_con_un_ruolo_sconosciuto_la_scheda_si_apre_senza_fantavoti(tmp_path, caplog):
    """Un ruolo del listone che non è P, D, C o A non ha bonus nelle regole: come `rendimento`, la scheda salta il calcolo dei
    fantavoti (`fv`, fantamedia e andamento vuoti) invece di rompersi; i voti restano. Il guasto va nel registro."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db, ruoli={7: "X"})
    with caplog.at_level("WARNING", logger="fanta.scheda"):
        s = scheda.scheda(db, 7, ST, LEGA)
    assert [v["voto"] for v in s["voti"]] == [6.0, 6.0, None, 6.5, 6.0, 6.0, 5.5]
    assert all(v["fv"] is None for v in s["voti"]) and s["stagione"]["ultime_5_fv"] == [None] * 5
    assert s["stagione"]["fantamedia"] is None and s["andamento"] is None and s["stagione"]["media_voto"] == 6.0
    assert any("ruolo" in r.getMessage() and r.name == "fanta.scheda" for r in caplog.records)


def _client(tmp_path, monkeypatch, ruoli: dict | None = None):
    from fastapi.testclient import TestClient

    from fanta import consigli, server
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db, ruoli)
    db.close()
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "fanta.sqlite"))
    monkeypatch.setattr(server, "_regole", lambda ctx: LEGA)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda *a, **k: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda *a, **k: (_ for _ in ()).throw(ValueError("niente previsioni nel test")))
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_la_rotta_della_scheda_usa_le_regole_della_lega(tmp_path, monkeypatch):
    """GET /api/giocatore/{id}: la fantamedia e i voti della scheda con le regole della lega di chi chiede."""
    s = _client(tmp_path, monkeypatch).get("/api/giocatore/7").json()
    assert s["stagione"]["fantamedia"] == 6.83 and s["voti"][5]["fv"] == 10.5 and s["andamento"] == "in_crescita"


def test_la_rotta_della_scheda_con_un_ruolo_sconosciuto_non_da_500(tmp_path, monkeypatch):
    r = _client(tmp_path, monkeypatch, ruoli={7: "X"}).get("/api/giocatore/7")
    assert r.status_code == 200 and r.json()["stagione"]["fantamedia"] is None


# ---------------------------------------------------------------- giocatore uscito dal listone, rendimento, gol, prossime partite (27/11/2026)
def test_un_giocatore_uscito_dal_listone_ha_una_frase_per_chi_usa_l_app(tmp_path, monkeypatch):
    """La Rosa tiene anche chi è uscito dal listone (ceduto all'estero): toccandolo la scheda diceva «calciatore 999 non nel
    listone», il testo interno dell'eccezione. Ora 404 con una frase del catalogo, che la web traduce (`err.fuori_listone`)."""
    r = _client(tmp_path, monkeypatch).get("/api/giocatore/999")
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Questo giocatore non è più nel listone di Serie A."
    with pytest.raises(scheda.FuoriDalListone):
        scheda.scheda(archivio.apri(tmp_path / "fanta.sqlite"), 999, ST, LEGA)


def test_la_rosa_dice_chi_e_uscito_dal_listone(tmp_path, monkeypatch):
    """`fuori_listone` di GET /api/rosa lo decide il server (revisione della #985): prima web e iPhone lo deducevano da
    `quotazione` vuota, ma un giocatore del listone può non avere la quotazione (qui Verdi) e non è fuori. Chi non è riconosciuto
    (senza codice) non si sa; senza nessun listone nell'archivio nemmeno: nessuno è «fuori»."""
    from fanta import lega
    c = _client(tmp_path, monkeypatch)
    lega.salva(lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(7, "Verdi", "D", "GEN"), lega.GiocatoreRosa(999, "Partito", "A", "GEN"),
                                               lega.GiocatoreRosa(None, "Sconosciuto", "C", None, riconosciuto="non trovato")])],
                         "Mia"), tmp_path / "rose.json")
    g = {x["nome"]: x for x in c.get("/api/rosa").json()["giocatori"]}
    assert g["Verdi"]["quotazione"] is None and g["Verdi"]["fuori_listone"] is False
    assert g["Partito"]["fuori_listone"] is True
    assert g["Sconosciuto"]["fuori_listone"] is False
    db = archivio.apri(tmp_path / "fanta.sqlite")
    db.execute("DELETE FROM calciatori")
    db.commit()
    db.close()
    assert not any(x["fuori_listone"] for x in c.get("/api/rosa").json()["giocatori"])


def _avanzate(gol, xg, assist=0, xa=0.0):
    return {"minuti": 900, "gol": gol, "xg": xg, "assist": assist, "xa": xa}


@pytest.mark.parametrize("gol, xg, tendenza, testo", [
    (5, 2.0, "cala", "Sta segnando più di quanto crea: è probabile che cali."),           # +3 gol su 10 partite, bonus 3: +0,9
    (1, 4.0, "sblocca", "Crea più di quanto segna: è probabile che si sblocchi."),        # −0,9
    (3, 2.0, "in_linea", "In linea con le occasioni che ha."),                            # +0,3: la soglia non basta
    (2, 3.0, "in_linea", "In linea con le occasioni che ha."),                            # −0,3
])
def test_il_rendimento_dice_cala_sblocca_o_in_linea_con_la_frase(gol, xg, tendenza, testo):
    """«Gol e assist rispetto alle occasioni»: frase e colore li decidevano web e iPhone con la soglia 0,3 sul numero. Ora il
    server manda il codice (`tendenza`) e la frase con la sua chiave, come le altre frasi; i client li mostrano."""
    r = scheda.rendimento(_avanzate(gol, xg), "A", 10, Regole())
    assert r["tendenza"] == tendenza and r["testo"] == testo
    assert r["frase"] == {"chiave": f"rendimento.{tendenza}", "param": {}}


def test_la_soglia_del_rendimento_vale_sul_numero_mostrato():
    """Il numero si mostra con due decimali: +0,304 si legge «+0,30» e non può dire «cala» (il client confrontava già quello)."""
    r = scheda.rendimento(_avanzate(0, 0.0, assist=3, xa=0.0), "A", 9.868, Regole())     # 3 assist × 1 / 9,868 = 0,304
    assert r["sovra_rendimento"] == 0.3 and r["tendenza"] == "in_linea"


def test_la_stagione_ha_i_gol_con_i_rigori_gia_sommati(tmp_path):
    """La tessera «gol (N rig.)» sommava gol e rigori segnati nei client: il server manda il numero pronto."""
    db = archivio.apri(tmp_path / "fanta.sqlite")
    _giocatori(db)
    st = scheda.scheda(db, 9, ST, LEGA)["stagione"]
    assert (st["gol"], st["rig_segnati"], st["gol_con_rigori"]) == (1, 2, 3)


CALENDARIO = {"giornate": [9, 10], "squadre": [
    {"squadra": "genoa", "media": 2.5, "partite": [{"giornata": 9, "avversario": "como", "in_casa": True, "difficolta": 2, "data": None},
                                                    {"giornata": 10, "avversario": "inter", "in_casa": False, "difficolta": 3, "data": None}]},
    {"squadra": "inter", "media": 3.0, "partite": [{"giornata": 9, "avversario": "lazio", "in_casa": False, "difficolta": 3, "data": None}]},
]}


def test_le_prossime_partite_sono_della_squadra_della_previsione_o_del_listone():
    """La web le mostrava solo con la previsione, l'iPhone ripiegava sulla squadra del listone: ora le sceglie il server."""
    genoa, inter = CALENDARIO["squadre"][0]["partite"], CALENDARIO["squadre"][1]["partite"]
    assert scheda.prossime_partite(CALENDARIO, None, {"squadra_slug": "genoa"}) == genoa
    assert scheda.prossime_partite(CALENDARIO, {"squadra": "inter"}, {"squadra_slug": "genoa"}) == inter
    assert scheda.prossime_partite(CALENDARIO, None, {"squadra_slug": "salernitana"}) == []
    assert scheda.prossime_partite(CALENDARIO, None, {"squadra_slug": None}) == []


def test_la_scheda_manda_le_prossime_partite_anche_senza_previsione(tmp_path, monkeypatch):
    from fanta import consigli, gestione
    c = _client(tmp_path, monkeypatch)                            # nel test non c'è la previsione (consigli.previsioni fallisce)
    monkeypatch.setattr(gestione, "calendario", lambda *a, **k: CALENDARIO)
    s = c.get("/api/giocatore/7").json()
    assert "previsione" not in s and s["prossime_partite"] == CALENDARIO["squadre"][0]["partite"]
    # a campionato finito (o senza calendario) nessuna partita, e la scheda si apre lo stesso
    monkeypatch.setattr(gestione, "calendario", lambda *a, **k: (_ for _ in ()).throw(consigli.CampionatoFinito("finito")))
    r = c.get("/api/giocatore/7")
    assert r.status_code == 200 and r.json()["prossime_partite"] == []
