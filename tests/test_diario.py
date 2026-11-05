"""Diario delle giornate: formazione schierata contro consigliata, con dati finti (il modello vero non serve qui)."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import archivio, consigli, diario, lega
from fanta.regole import Regole

ST = "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25


@pytest.fixture
def finto(monkeypatch, tmp_path):
    """Due giornate finite; tutti prendono 6, tranne l'ultimo attaccante (id 25) che prende 9."""
    partite = pd.DataFrame([{"id": g, "stagione": ST, "giornata": g, "giocata": 1} for g in (1, 2)])
    voti = pd.DataFrame([{"stagione": ST, "giornata": g, "calciatore_id": i, "ruolo": RUOLI[i - 1], "voto_red": 9.0 if i == 25 else 6.0}
                         for g in (1, 2) for i in range(1, 26)])
    dati = SimpleNamespace(partite=partite, voti=voti)

    def previsioni(d, stagione, giornata, regole, par):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0,
                              "partita": giornata} for i in range(1, 26)])
    monkeypatch.setattr(diario, "previsioni", previsioni)
    monkeypatch.setattr(diario, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "dati", lambda db: dati)
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)
    db = archivio.apri(tmp_path / "t.sqlite")
    for g in (1, 2):
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, '2026-09-01 18:00', 'a', 'b', 1)", (g, ST, g))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"G{i}", RUOLI[i - 1], "INT") for i in range(1, 26)])], "Mia")
    return SimpleNamespace(dati=dati, db=db, rose=rose, file=tmp_path / "diario.json")


def _scelta(ids):
    return {"titolari": ids, "modulo": "3-4-3"}


def test_giornata_senza_la_tua_scelta_ha_solo_la_consigliata(finto):
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    assert v["schierata"] is None
    c = v["consigliata"]
    assert len(c["titolari"]) == 11 and c["modulo"] in Regole().moduli and c["reale"] > 50


def test_con_la_tua_scelta_si_confrontano_punti_attesi_e_fatti(finto):
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]          # 3-4-3 con l'attaccante che ha preso 9
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), _scelta(scelti), simulazioni=50)
    s = v["schierata"]
    assert s["modulo"] == "3-4-3" and [t["id"] for t in s["titolari"]] == scelti
    assert s["reale"] == 11 * 6 + 3          # dieci da 6 e l'attaccante da 9 (modificatore difesa spento di default)
    assert 55 < s["atteso"] < 70


def test_scelta_con_un_giocatore_fuori_rosa_non_conta(finto):
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 99]
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), _scelta(scelti), simulazioni=50)
    assert v["schierata"] is None and v["consigliata"]


def test_la_panchina_schierata_conta_per_le_sostituzioni(finto):
    v = finto.dati.voti
    finto.dati.voti = v[~((v["giornata"] == 1) & (v["calciatore_id"] == 20))].copy()      # l'attaccante 20 non prende voto
    finto.dati.voti.loc[finto.dati.voti["calciatore_id"] == 22, "voto_red"] = 10.0          # il suo sostituto «vero» (22) prende 10
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    sistema = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), _scelta(scelti), simulazioni=50)
    propria = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)),
                                      {**_scelta(scelti), "panchina": [22, 24, 99]}, simulazioni=50)
    assert propria["schierata"]["reale"] == sistema["schierata"]["reale"] + 4          # entra 22 (10) e non 24 (6)


def test_rosa_troppo_piccola_o_giornata_non_giocata_non_ha_voce(finto):
    assert diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, [1, 2, 3], None, simulazioni=50) is None
    finto.dati.partite["giocata"] = 0
    assert diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), None, simulazioni=50) is None


def test_aggiorna_fa_solo_le_giornate_nuove_e_rifa_quelle_senza_scelta(finto, monkeypatch):
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 0
    assert set(diario.carica(finto.file)["giornate"]) == {f"{ST}/1", f"{ST}/2"}
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    monkeypatch.setattr(diario.scelte, "leggi", lambda st, g, *a, **k: _scelta(scelti) if g == 2 else None)
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 1          # la 2 ora ha la tua scelta
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 0
    e = diario.elenco(finto.file)
    assert [v["giornata"] for v in e["giornate"]] == [2, 1]
    assert e["sintesi"]["giornate"] == 1 and e["sintesi"]["meglio_tua"] + e["sintesi"]["meglio_consigliata"] <= 1


def test_senza_la_mia_squadra_non_fa_niente(finto):
    assert diario.aggiorna(finto.db, Regole(), None, finto.file) == 0
    assert diario.aggiorna(finto.db, Regole(), lega.Rose([lega.Squadra("Mia", [])], None), finto.file) == 0
    assert not finto.file.exists()


def test_file_mancante_o_rovinato(tmp_path):
    assert diario.carica(tmp_path / "no.json") == {"giornate": {}}
    (tmp_path / "x.json").write_text("{rotto")
    assert diario.elenco(tmp_path / "x.json") == {"giornate": [], "sintesi": {"giornate": 0},
                                                  "scelte_tue": {"giornate": 0, "pochi_dati": True, "per_giornata": []},
                                                  "affidabilita": {"giornate": 0, "giudizio": "pochi_dati", "pochi_dati": True,
                                                                   "giornate_minime": diario.POCHI_DATI}}


def _voce(g, tue, loro, punti_tua, punti_loro):
    riga = lambda ids, r: {"reale": r, "atteso": 60.0, "titolari": [{"id": i, "nome": f"G{i}", "ruolo": "A"} for i in ids]}    # noqa: E731
    return {"stagione": ST, "giornata": g, "schierata": riga(tue, punti_tua), "consigliata": riga(loro, punti_loro)}


def test_scelte_tue_chi_aveva_ragione():
    voci = [_voce(4, [1, 2, 3], [1, 2, 3], 70, 70),             # stessi undici: non conta
            _voce(3, [1, 2, 9], [1, 2, 3], 62.5, 66.0),         # meglio la consigliata
            _voce(2, [1, 7, 3], [1, 2, 3], 71.0, 66.0),         # meglio tu
            _voce(1, [1, 2, 8], [1, 2, 3], 60.0, 60.0),         # pari
            {"stagione": ST, "giornata": 0, "schierata": None, "consigliata": {"reale": 1, "titolari": []}}]
    s = diario.scelte_tue(voci)
    assert s["giornate"] == 3 and (s["meglio_tua"], s["meglio_consigliata"], s["pari"]) == (1, 1, 1)
    assert s["punti_differenza"] == 1.5 and s["percentuale_tua"] == 33 and s["pochi_dati"] is True
    g3 = s["per_giornata"][0]
    assert g3["giornata"] == 3 and g3["hai_scelto"] == ["G9"] and g3["consigliava"] == ["G3"] and g3["esito"] == "consigliata"
    assert g3["differenza"] == -3.5


def test_scelte_tue_con_abbastanza_giornate():
    voci = [_voce(g, [1, 2, 9], [1, 2, 3], 70, 60) for g in range(1, 9)]
    s = diario.scelte_tue(voci)
    assert s["giornate"] == 8 and s["pochi_dati"] is False and s["percentuale_tua"] == 100 and s["punti_differenza"] == 80.0


# ---------------------------------------------------------------- «Ho schierato la consigliata» e copia automatica
from fanta import scelte as _scelte                      # noqa: E402
_LEGGI_VERO = _scelte.leggi


@pytest.fixture
def vero(finto, monkeypatch, tmp_path):
    """Come `finto`, ma con il file delle scelte vero (in una cartella temporanea) e la rosa nei file del server."""
    monkeypatch.setattr(diario.scelte, "leggi", _LEGGI_VERO)
    monkeypatch.setattr(diario.scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(diario, "FILE", finto.file)
    finto.scelte = tmp_path / "scelte.json"
    return finto


def _salva(v, giornata, tipo, titolari=None):
    return diario.salva_schierata(v.db, Regole(), v.rose, giornata, tipo, titolari, v.file, v.scelte, simulazioni=50)


def test_ho_schierato_la_consigliata_rifa_solo_quella_giornata(vero):
    voce = _salva(vero, 1, "consigliata")
    assert voce["schierata"]["tipo"] == "consigliata"
    assert [t["id"] for t in voce["schierata"]["titolari"]] == [t["id"] for t in voce["consigliata"]["titolari"]]
    assert voce["schierata"]["reale"] == voce["consigliata"]["reale"]
    assert set(diario.carica(vero.file)["giornate"]) == {f"{ST}/1"}              # la giornata 2 non è stata toccata né calcolata
    salvata = _LEGGI_VERO(ST, 1, vero.scelte)
    assert salvata["tipo"] == "consigliata" and salvata["titolari"] == [t["id"] for t in voce["consigliata"]["titolari"]]
    assert diario.elenco(vero.file)["sintesi"]["giornate"] == 1


def test_ho_schierato_a_mano(vero):
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    voce = _salva(vero, 2, "manuale", scelti)
    assert voce["schierata"]["tipo"] == "manuale" and voce["schierata"]["reale"] == 11 * 6 + 3
    assert _LEGGI_VERO(ST, 2, vero.scelte)["modulo"] == "3-4-3"


@pytest.mark.parametrize("giornata, tipo, titolari, messaggio", [
    (9, "consigliata", None, "già finite"),                                          # giornata non finita
    (1, "manuale", [1, 4, 5], "11 titolari"),
    (1, "manuale", [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 99], "non sono nella tua rosa"),
    (1, "manuale", [1, 1, 5, 6, 12, 13, 14, 15, 20, 21, 25], "11 titolari"),
    (1, "boh", None, "consigliata"),
])
def test_schierata_non_valida(vero, giornata, tipo, titolari, messaggio):
    with pytest.raises(diario.SchierataNonValida, match=messaggio):
        _salva(vero, giornata, tipo, titolari)
    assert not vero.scelte.exists()                                                  # niente è stato salvato


def test_la_copia_automatica_non_e_una_scelta_dell_utente(vero):
    assert _scelte.salva_automatica(ST, 1, list(range(1, 12)), "4-4-2", vero.scelte) is True
    assert _scelte.salva_automatica(ST, 1, list(range(1, 12)), "4-4-2", vero.scelte) is False          # uguale: non riscrive
    assert _scelte.salva_automatica(ST, 1, list(range(2, 13)), "4-4-2", vero.scelte) is True           # cambiata prima della scadenza
    assert _LEGGI_VERO(ST, 1, vero.scelte) is None                                    # per l'app non è la «mia scelta»
    assert _LEGGI_VERO(ST, 1, vero.scelte, anche_automatica=True)["tipo"] == "automatica"
    _scelte.salva(ST, 1, list(range(1, 12)), "4-4-2", vero.scelte)                    # l'utente sceglie
    assert _scelte.salva_automatica(ST, 1, list(range(2, 13)), "4-4-2", vero.scelte) is False          # mai sopra una scelta vera
    assert _LEGGI_VERO(ST, 1, vero.scelte)["tipo"] == "manuale"


def test_il_diario_distingue_automatica_e_schierata(vero):
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    _scelte.salva_automatica(ST, 1, scelti, "3-4-3", vero.scelte)
    assert diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte) == 2
    v = diario.carica(vero.file)["giornate"][f"{ST}/1"]
    assert v["schierata"] is None and v["automatica"]["reale"] == 11 * 6 + 3
    assert diario.carica(vero.file)["giornate"][f"{ST}/2"]["automatica"] is None
    assert diario.elenco(vero.file)["sintesi"] == {"giornate": 0}                      # la copia automatica non entra nelle statistiche di ciò che hai schierato
    assert diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte) == 0


def test_voci_vecchie_hanno_i_campi_nuovi(tmp_path):
    f = tmp_path / "d.json"
    f.write_text('{"giornate": {"2026-27/1": {"stagione": "2026-27", "giornata": 1, "consigliata": {"reale": 1, "atteso": 1}, '
                 '"schierata": {"modulo": "3-4-3", "atteso": 1, "reale": 2, "titolari": []}}}}', encoding="utf-8")
    v = diario.elenco(f)["giornate"][0]
    assert v["schierata"]["tipo"] == "manuale" and v["automatica"] is None


def test_rotta_diario_schierata(vero, monkeypatch, tmp_path):
    import dataclasses
    import json
    from fastapi.testclient import TestClient
    from fanta import server
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    (tmp_path / "regole.json").write_text(json.dumps(dataclasses.asdict(Regole())), encoding="utf-8")
    lega.salva(vero.rose, tmp_path / "rose.json")
    vero.db.commit()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "t.sqlite"))          # la rotta chiude la connessione: ne serve una nuova ogni volta
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    r = c.post("/api/diario/schierata", json={"giornata": 1, "tipo": "consigliata"})
    assert r.status_code == 200, r.text
    assert r.json()["schierata"]["tipo"] == "consigliata"
    g = c.get("/api/diario").json()["giornate"]
    assert g[0]["schierata"]["tipo"] == "consigliata" and "automatica" in g[0]
    assert c.post("/api/diario/schierata", json={"giornata": 7, "tipo": "consigliata"}).status_code == 400
    assert "motivo_vuoto" not in c.get("/api/diario").json()                                  # con almeno una voce il campo non c'è
    assert c.post("/api/diario/schierata", json={"giornata": 1, "tipo": "manuale", "titolari": [1]}).status_code == 400
    assert c.get("/api/scelta", params={"giornata": 1}).json()["tipo"] == "consigliata"
    assert TestClient(server.app).post("/api/diario/schierata", json={"giornata": 1, "tipo": "consigliata"}).status_code == 403   # senza X-Fanta


PRIMA = "2025-26"          # la stagione scorsa: nel diario resta con le sue voci


def _diario_con_la_stagione_scorsa(vero):
    """Nel diario una voce della stagione scorsa con lo stesso numero di giornata (1) di una giornata finita di quest'anno."""
    riga = {"modulo": "3-4-3", "atteso": 60.0, "reale": 58.0, "titolari": [{"id": i, "nome": f"G{i}", "ruolo": "A"} for i in range(30, 41)]}
    vecchia = {"stagione": PRIMA, "giornata": 1, "consigliata": riga, "schierata": None}
    vero.file.write_text(json.dumps({"giornate": {f"{PRIMA}/1": vecchia}}), encoding="utf-8")


def test_ho_schierato_su_una_giornata_della_stagione_scorsa_non_tocca_quella_in_corso(vero):
    """Issue #176: il diario mostra anche la stagione scorsa; dire «ho schierato» su quella voce non deve scrivere sulla giornata
    con lo stesso numero della stagione in corso."""
    _diario_con_la_stagione_scorsa(vero)
    tuoi = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    _salva(vero, 1, "manuale", tuoi)                                                  # quest'anno, giornata 1: i tuoi undici
    prima = diario.carica(vero.file)["giornate"]
    with pytest.raises(diario.SchierataNonValida, match="stagione in corso"):
        diario.salva_schierata(vero.db, Regole(), vero.rose, 1, "consigliata", None, vero.file, vero.scelte, simulazioni=50, stagione=PRIMA)
    assert _LEGGI_VERO(ST, 1, vero.scelte)["titolari"] == tuoi and _LEGGI_VERO(ST, 1, vero.scelte)["tipo"] == "manuale"
    assert diario.carica(vero.file)["giornate"] == prima                             # né la voce di quest'anno né quella vecchia cambiano
    voce = diario.salva_schierata(vero.db, Regole(), vero.rose, 2, "consigliata", None, vero.file, vero.scelte, simulazioni=50, stagione=ST)
    assert voce["stagione"] == ST and voce["schierata"]["tipo"] == "consigliata"     # la stagione in corso, detta esplicitamente, va


def test_rotta_diario_schierata_con_la_stagione(vero, monkeypatch, tmp_path):
    import dataclasses
    from fastapi.testclient import TestClient
    from fanta import server
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    (tmp_path / "regole.json").write_text(json.dumps(dataclasses.asdict(Regole())), encoding="utf-8")
    lega.salva(vero.rose, tmp_path / "rose.json")
    vero.db.commit()
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "t.sqlite"))
    _diario_con_la_stagione_scorsa(vero)
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    tuoi = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    assert c.post("/api/diario/schierata", json={"giornata": 1, "tipo": "manuale", "titolari": tuoi}).status_code == 200   # client vecchio: stagione in corso
    r = c.post("/api/diario/schierata", json={"giornata": 1, "tipo": "consigliata", "stagione": PRIMA})
    assert r.status_code == 400 and "stagione in corso" in r.json()["detail"]
    assert c.get("/api/scelta", params={"giornata": 1}).json()["titolari"] == tuoi     # la scelta di quest'anno è rimasta la tua
    voci = {(v["stagione"], v["giornata"]): v for v in c.get("/api/diario").json()["giornate"]}
    assert voci[(ST, 1)]["schierata"]["tipo"] == "manuale" and voci[(PRIMA, 1)]["schierata"] is None
    assert voci[(ST, 1)]["modificabile"] is True and voci[(PRIMA, 1)]["modificabile"] is False      # i client nascondono i pulsanti sulle voci vecchie
    r = c.post("/api/diario/schierata", json={"giornata": 2, "tipo": "consigliata", "stagione": ST})
    assert r.status_code == 200 and r.json()["stagione"] == ST
    assert c.post("/api/diario/schierata", json={"giornata": 2, "tipo": "consigliata", "stagione": "boh"}).status_code == 422


def test_aprendo_la_formazione_si_tiene_la_copia_automatica_fino_alla_scadenza(vero, monkeypatch, tmp_path):
    import dataclasses
    import json
    from datetime import datetime, timedelta
    from fastapi.testclient import TestClient
    from fanta import server
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    (tmp_path / "regole.json").write_text(json.dumps(dataclasses.asdict(Regole())), encoding="utf-8")
    lega.salva(vero.rose, tmp_path / "rose.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(tmp_path / "t.sqlite"))
    formazione = {"giornata": 3, "modulo": "3-4-3", "titolari": [{"id": i} for i in range(1, 12)]}
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: dict(formazione))
    prima = {"quando": datetime.now() + timedelta(hours=5)}
    monkeypatch.setattr(server.avvisi_pronta, "prima_partita", lambda db, st, g: prima["quando"])
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/formazione").status_code == 200
    auto = _LEGGI_VERO(ST, 3, vero.scelte, anche_automatica=True)
    assert auto["tipo"] == "automatica" and auto["titolari"] == list(range(1, 12))
    assert c.get("/api/scelta", params={"giornata": 3}).json() is None                      # non è una scelta dell'utente
    formazione["titolari"] = [{"id": i} for i in range(2, 13)]
    c.get("/api/formazione")
    assert _LEGGI_VERO(ST, 3, vero.scelte, anche_automatica=True)["titolari"] == list(range(2, 13))   # si aggiorna finché è aperta
    prima["quando"] = datetime.now() - timedelta(minutes=1)                                  # scaduta: la copia resta quella di prima
    formazione["titolari"] = [{"id": i} for i in range(3, 14)]
    assert c.get("/api/formazione").status_code == 200
    assert _LEGGI_VERO(ST, 3, vero.scelte, anche_automatica=True)["titolari"] == list(range(2, 13))
    ist = diario.carica(vero.file).get("istantanee", {}).get(f"{ST}/3")                      # anche l'istantanea si è congelata alla scadenza
    assert ist and [t["id"] for t in ist["titolari"]] == list(range(2, 13))


# ---- istantanea: la consigliata di allora ----
def _formazione_finta(giornata=1, ids=range(1, 12)):
    pers = lambda i: {"id": i, "nome": f"G{i}", "ruolo": (RUOLI + ["A"] * 99)[i - 1], "punti_attesi": 6.1}      # noqa: E731
    return {"giornata": giornata, "modulo": "3-4-3", "punteggio_atteso": 71.46, "titolari": [pers(i) for i in ids],
            "panchina": [pers(i) for i in (12, 13, 14)],
            "livelli": [{"rischio": -1, "nome": "Sicura"}, {"rischio": 0, "nome": "Equilibrata"}]}


def test_istantanea_salvata_aggiornata_e_poco_pesante(tmp_path):
    f = tmp_path / "diario.json"
    assert diario.salva_istantanea(_formazione_finta(), ST, f) is True
    assert diario.salva_istantanea(_formazione_finta(), ST, f) is False                 # uguale: non riscrive
    assert diario.salva_istantanea(_formazione_finta(ids=range(2, 13)), ST, f) is True    # cambiata prima della scadenza: una sola per giornata
    ist = diario.carica(f)["istantanee"]
    assert list(ist) == [f"{ST}/1"]
    v = ist[f"{ST}/1"]
    assert v["stile"] == "Equilibrata" and v["atteso"] == 71.5 and v["modulo"] == "3-4-3" and "calcolata" in v
    assert [t["id"] for t in v["titolari"]] == list(range(2, 13)) and len(v["panchina"]) == 3
    assert len(json.dumps(v)) < 2500                                                    # al massimo un paio di KB
    assert diario.salva_istantanea({"giornata": 1, "titolari": []}, ST, f) is False      # formazione incompleta: niente


def test_istantanee_tenute_al_massimo(tmp_path):
    f = tmp_path / "diario.json"
    for g in range(1, diario.MAX_ISTANTANEE + 6):
        diario.salva_istantanea(_formazione_finta(giornata=g), ST, f)
    ist = diario.carica(f)["istantanee"]
    assert len(ist) == diario.MAX_ISTANTANEE and f"{ST}/1" not in ist


def test_elenco_ha_sempre_istantanea_anche_null(finto, tmp_path):
    f = tmp_path / "diario.json"
    diario.aggiorna(finto.db, Regole(), finto.rose, f, simulazioni=50)
    diario.salva_istantanea(_formazione_finta(giornata=2), ST, f)                       # l'aggiornamento non cancella le istantanee
    voci = {v["giornata"]: v for v in diario.elenco(f)["giornate"]}
    assert voci[1]["istantanea"] is None and voci[2]["istantanea"]["modulo"] == "3-4-3"
    diario.aggiorna(finto.db, Regole(), finto.rose, f, simulazioni=50)
    assert diario.carica(f)["istantanee"]


def test_ho_schierato_la_consigliata_usa_l_istantanea(vero):
    diario.salva_istantanea(_formazione_finta(giornata=1, ids=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]), ST, vero.file)
    voce = _salva(vero, 1, "consigliata")
    assert sorted(t["id"] for t in voce["schierata"]["titolari"]) == [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    assert diario.carica(vero.file)["istantanee"]                                       # salvare la voce non cancella l'istantanea


def test_cambio_regole_rifa_le_giornate_calcolate(finto):
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    assert all(v["regole"] == diario.impronta_regole(Regole()) for v in diario.carica(finto.file)["giornate"].values())
    nuove = Regole()
    nuove.bonus.rigore_sbagliato = -3.0
    assert diario.impronta_regole(nuove) != diario.impronta_regole(Regole())
    assert diario.aggiorna(finto.db, nuove, finto.rose, finto.file, simulazioni=50) == 2          # regole cambiate: si rifanno
    assert diario.aggiorna(finto.db, nuove, finto.rose, finto.file, simulazioni=50) == 0          # e poi restano ferme
    assert diario.impronta_regole(Regole(nome_lega="altro", scadenza_minuti=30)) == diario.impronta_regole(Regole())      # il resto non conta


def test_voci_senza_impronta_si_rifanno_ma_la_schierata_senza_scelta_resta(finto, monkeypatch):
    scelti = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 25]
    monkeypatch.setattr(diario.scelte, "leggi", lambda st, g, *a, **k: _scelta(scelti) if g == 1 else None)
    diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50)
    d = diario.carica(finto.file)
    for v in d["giornate"].values():
        v.pop("regole")
    finto.file.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(diario.scelte, "leggi", lambda *a, **k: None)          # la scelta della 1 non c'è più
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 1          # solo la 2, che non ha schierata
    assert diario.carica(finto.file)["giornate"][f"{ST}/1"]["schierata"] is not None


def test_istantanea_con_giocatore_non_piu_in_rosa_ripiega_sulla_ricostruzione(vero):
    diario.salva_istantanea(_formazione_finta(giornata=1, ids=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 99]), ST, vero.file)
    voce = _salva(vero, 1, "consigliata")
    assert 99 not in [t["id"] for t in voce["schierata"]["titolari"]]


def test_motivo_del_diario_vuoto(vero):
    """Il diario vuoto dice perché: niente squadra, nessuna giornata finita, oppure tutto a posto e da calcolare."""
    assert diario.motivo_vuoto(vero.db, Regole(), vero.rose) == "calcolo"
    assert diario.motivo_vuoto(vero.db, Regole(), None) == "squadra"
    assert diario.motivo_vuoto(vero.db, Regole(prima_giornata_lega=99), vero.rose) == "giornate"


# ---- corsa fra il cron e l'app: un «Ho schierato» non si perde ----
def test_il_cron_non_cancella_una_schierata_arrivata_mentre_calcolava(vero, monkeypatch):
    """Il cron legge il diario, calcola a lungo; intanto l'app registra «Ho schierato» per la stessa giornata. Quando il cron
    scrive, la voce con la schierata resta (e riceve solo i numeri per giocatore che le mancavano)."""
    calcola_vera = diario.calcola_giornata
    fatto = {}

    def calcola_lenta(d, stagione, giornata, *a, **k):
        voce = calcola_vera(d, stagione, giornata, *a, **k)
        if giornata == 1 and not fatto:                   # «nel frattempo» il server salva la schierata della giornata 1
            fatto["in_corso"] = True
            fatto["voce"] = _salva(vero, 1, "consigliata")
        return voce
    monkeypatch.setattr(diario, "calcola_giornata", calcola_lenta)
    diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=tmp_scelte_vuote(vero))
    v = diario.carica(vero.file)["giornate"][f"{ST}/1"]
    assert v["schierata"] and v["schierata"]["tipo"] == "consigliata"
    assert v["schierata"] == fatto["voce"]["schierata"] and v["giocatori"]


def tmp_scelte_vuote(v):
    """Un file di scelte vuoto: il cron non sa ancora della scelta (l'ha letta prima che arrivasse)."""
    f = v.scelte.with_name("scelte-vuote.json")
    f.write_text("{}", encoding="utf-8")
    return f


def test_una_voce_senza_schierata_non_sostituisce_quella_con_la_schierata(tmp_path):
    f = tmp_path / "diario.json"
    con = {"stagione": ST, "giornata": 3, "consigliata": {"reale": 70}, "schierata": {"reale": 66, "titolari": []}}
    diario._scrivi(f, voci={f"{ST}/3": con})
    diario._scrivi(f, voci={f"{ST}/3": {"stagione": ST, "giornata": 3, "consigliata": {"reale": 71}, "schierata": None,
                                        "giocatori": [{"id": 1, "p_voto": 0.9, "fv_atteso": 6.0, "fv": None}]}})
    v = diario.carica(f)["giornate"][f"{ST}/3"]
    assert v["schierata"]["reale"] == 66 and v["consigliata"]["reale"] == 70 and len(v["giocatori"]) == 1
    nuova = {**con, "schierata": {"reale": 80, "titolari": []}}                 # una correzione (con la schierata) passa sempre
    diario._scrivi(f, voci={f"{ST}/3": nuova})
    assert diario.carica(f)["giornate"][f"{ST}/3"]["schierata"]["reale"] == 80


def test_scadenza_passata_non_comincia_nuove_giornate(finto):
    import time
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50, scadenza=time.monotonic() - 1) == 0
    assert not finto.file.exists()


# ---- numeri per giocatore, per «Quanto ci abbiamo preso» (precisione.py) ----
def test_la_voce_ha_i_numeri_di_ogni_giocatore(finto):
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), None, simulazioni=50)
    g = {x["id"]: x for x in v["giocatori"]}
    assert len(g) == 25 and g[25] == {"id": 25, "p_voto": 0.9, "fv_atteso": 6.75, "fv": 9.0} and g[1]["fv"] == 6.0
    assert len(json.dumps(v["giocatori"])) < 25 * 70                       # circa 60 byte a giocatore


def test_le_voci_vecchie_si_completano_senza_rifare_le_simulazioni(finto, monkeypatch):
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    d = json.loads(finto.file.read_text(encoding="utf-8"))
    for v in d["giornate"].values():
        v.pop("giocatori")                                                  # come le voci scritte prima di questa versione
    finto.file.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(diario.fz, "migliore", lambda *a, **k: pytest.fail("non deve rifare le simulazioni"))
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    dopo = diario.carica(finto.file)["giornate"]
    assert all(len(v["giocatori"]) == 25 for v in dopo.values())
    assert {k: v["consigliata"] for k, v in dopo.items()} == {k: v["consigliata"] for k, v in d["giornate"].items()}
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 0          # poi non lo rifà


def test_l_istantanea_ricorda_i_numeri_mostrati(tmp_path):
    f = tmp_path / "diario.json"
    form = _formazione_finta()
    form["titolari"][0] |= {"p_voto": 0.8512, "fv_atteso": 6.789}
    form["titolari"][1] |= {"p_voto": True, "fv_atteso": float("nan")}       # valori strani: si ignorano
    diario.salva_istantanea(form, ST, f)
    t = diario.carica(f)["istantanee"][f"{ST}/1"]["titolari"]
    assert t[0]["p_voto"] == 0.851 and t[0]["fv_atteso"] == 6.79 and "p_voto" not in t[1] and "fv_atteso" not in t[1]
