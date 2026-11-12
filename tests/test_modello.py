"""Modello: niente dati dal futuro, regole della lega rispettate, probabili formazioni usate."""
from dataclasses import replace

import pandas as pd
import pytest

from fanta import modello
from fanta.regole import Regole, imposta

ST = "2026-27"
NAN = float("nan")


def _dati(voti_extra=()):
    """Due squadre (alfa, beta) che si affrontano ogni giornata, 4 giornate giocate e la 5 da giocare."""
    partite, voti, prest = [], [], []
    for g in range(1, 6):
        casa, trasf = ("alfa", "beta") if g % 2 else ("beta", "alfa")
        giocata = int(g <= 4)
        partite.append({"id": g, "stagione": ST, "giornata": g, "data": f"2026-09-{g:02d} 15:00", "casa": casa,
                        "trasferta": trasf, "gol_casa": 1 if giocata else None, "gol_trasferta": 1 if giocata else None,
                        "giocata": giocata, "xg_casa": 1.2 if giocata else None, "xg_trasferta": 1.0 if giocata else None,
                        "understat_id": 100 + g})
        if not giocata:
            continue
        for cid, nome, ruolo, sq, gol, rig in ((1, "Bomber", "A", "alfa", 1, 1), (2, "Portiere", "P", "beta", 0, 0),
                                               (3, "Mediano", "C", "beta", 0, 0)):
            voti.append({"stagione": ST, "giornata": g, "calciatore_id": cid, "nome": nome, "squadra": sq,
                         "ruolo": ruolo, "voto_red": 6.5 if gol else 6.0, "fv_red": 0, "voto_stat": 6, "fv_stat": 0,
                         "voto_ita": 6, "fv_ita": 0, "gol": gol, "gol_subiti": 1 if ruolo == "P" else 0, "autogol": 0,
                         "rig_segnati": rig, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0,
                         "ammonizioni": 0, "espulsioni": 0, "subentrato": 0, "sostituito": 0,
                         "data": f"2026-09-{g:02d} 15:00"})
            prest.append({"understat_partita": 100 + g, "understat_giocatore": cid, "squadra": sq, "posizione": "",
                          "minuti": 90, "gol": gol + rig, "autogol": 0, "tiri": 3, "xg": 0.8 + 0.76 * rig, "xa": 0.1,
                          "assist": 0, "passaggi_chiave": 1, "xg_chain": 0, "xg_buildup": 0, "gialli": 0, "rossi": 0,
                          "rigori_calciati": rig, "rigori_segnati": rig, "punizioni": 0, "entrato": 0, "uscito": 0,
                          "stagione": ST, "giornata": g, "calciatore_id": cid, "data": f"2026-09-{g:02d} 15:00"})
    voti += list(voti_extra)
    d = modello.Dati([ST], pd.DataFrame(voti), pd.DataFrame(prest), pd.DataFrame(partite),
                     pd.DataFrame([{"id": 1, "nome": "Bomber", "ruolo": "A", "squadra": "ALF", "squadra_slug": "alfa", "quotazione": 30},
                                   {"id": 2, "nome": "Portiere", "ruolo": "P", "squadra": "BET", "squadra_slug": "beta", "quotazione": 10},
                                   {"id": 3, "nome": "Mediano", "ruolo": "C", "squadra": "BET", "squadra_slug": "beta", "quotazione": 5}]))
    for df in (d.voti, d.prestazioni, d.partite):
        df["t"] = df["giornata"]
    rig = d.prestazioni.groupby(["understat_partita", "squadra"])["rigori_calciati"].sum().rename("rigori_squadra")
    d.prestazioni = d.prestazioni.join(rig, on=["understat_partita", "squadra"])
    return d


def _p(d, giornata=5, regole=None, probabili=None):
    return modello.previsioni(d, ST, giornata, regole or Regole(), probabili=probabili).set_index("id")


def test_niente_dati_dal_futuro():
    # un voto "dal futuro" (giornata 5, quella da prevedere) non deve cambiare nulla
    futuro = {"stagione": ST, "giornata": 5, "calciatore_id": 1, "nome": "Bomber", "squadra": "alfa", "ruolo": "A",
              "voto_red": 10.0, "fv_red": 0, "voto_stat": 10, "fv_stat": 0, "voto_ita": 10, "fv_ita": 0, "gol": 5,
              "gol_subiti": 0, "autogol": 0, "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 3,
              "mvp": 0, "ammonizioni": 0, "espulsioni": 0, "subentrato": 0, "sostituito": 0,
              "data": "2026-09-05 15:00"}
    a, b = _p(_dati()), _p(_dati([futuro]))
    assert a.at[1, "mu"] == pytest.approx(b.at[1, "mu"])


def test_bomber_e_rigorista():
    p = _p(_dati())
    assert p.at[1, "e_gol"] > p.at[3, "e_gol"]
    assert p.at[1, "e_rigori"] > 0 and p.at[3, "e_rigori"] == 0
    assert p.at[1, "mu"] > p.at[3, "mu"]


def test_regole_della_lega_cambiano_il_fantavoto_atteso():
    d = _dati()
    base = _p(d)
    piu_gol = _p(d, regole=imposta(Regole(), "bonus.gol.A", "6"))
    assert piu_gol.at[1, "mu"] > base.at[1, "mu"]
    assert piu_gol.at[3, "mu"] == pytest.approx(base.at[3, "mu"])     # il centrocampista non cambia


def test_portiere_gol_subiti_e_imbattibilita():
    p = _p(_dati())
    assert 0 < p.at[2, "p_imbattuto"] < 1 and p.at[2, "gol_subiti"] > 0
    meno_malus = _p(_dati(), regole=imposta(Regole(), "bonus.gol_subito_portiere", "0"))
    assert meno_malus.at[2, "mu"] > p.at[2, "mu"]


def test_probabili_formazioni():
    prob = pd.DataFrame([
        {"calciatore_id": 1, "stato": "infortunato", "percentuale": 0.0, "in_dubbio": 0, "nota": "ko"},
        {"calciatore_id": 2, "stato": "titolare", "percentuale": 90.0, "in_dubbio": 0, "nota": None},
    ])
    p = _p(_dati(), probabili=prob)
    assert p.at[1, "p_voto"] == 0
    assert p.at[2, "p_voto"] > 0.8
    assert p.at[3, "p_voto"] < 0.05          # non citato nelle probabili


def test_probabili_senza_percentuale():
    """La pagina delle probabili a volte non ha la barra della percentuale: nel database è NULL e pandas la legge come NaN.
    Prima p_voto diventava NaN (titolare trattato come se non giocasse mai, e la risposta all'app falliva con un NaN nel JSON)."""
    prob = pd.DataFrame([
        {"calciatore_id": 2, "stato": "titolare", "percentuale": float("nan"), "in_dubbio": 0, "nota": None},
        {"calciatore_id": 3, "stato": "panchina", "percentuale": float("nan"), "in_dubbio": 0, "nota": None},
        {"calciatore_id": 1, "stato": "titolare", "percentuale": 90.0, "in_dubbio": 0, "nota": None},
    ])
    p = _p(_dati(), probabili=prob)
    assert p["p_voto"].notna().all() and p["atteso"].notna().all()
    assert p.at[2, "p_voto"] == pytest.approx(modello._p_da_probabili("titolare", None, False), abs=1e-3)
    assert p.at[3, "p_voto"] == pytest.approx(modello._p_da_probabili("panchina", None, False), abs=1e-3)


def test_recupero_giocato_dopo_non_e_usato():
    """Una partita della giornata 2 recuperata dopo l'inizio della 5 non deve entrare nella previsione della 5."""
    d = _dati()
    d.partite.loc[d.partite["giornata"] == 2, "data"] = "2026-10-30 15:00"
    for df in (d.voti, d.prestazioni):
        df.loc[df["giornata"] == 2, "data"] = "2026-10-30 15:00"
    con, senza = _p(d), _p(_dati())
    assert con.at[1, "presenze_pesate"] < senza.at[1, "presenze_pesate"]


def _con_la_giornata_6(d, giocata_la_5: bool, voti_della_5=()):
    """`_dati` con la giornata 5 giocata (1-1) o no, questi voti della 5 (nessuno: non ancora arrivati) e la 6 da giocare."""
    p = d.partite
    if giocata_la_5:
        p.loc[p["giornata"] == 5, ["gol_casa", "gol_trasferta", "giocata"]] = [1, 1, 1]
    sesta = {"id": 6, "stagione": ST, "giornata": 6, "data": "2026-09-06 15:00", "casa": "alfa", "trasferta": "beta",
             "gol_casa": NAN, "gol_trasferta": NAN, "giocata": 0, "xg_casa": NAN, "xg_trasferta": NAN, "understat_id": 106, "t": 6}
    d.partite = pd.concat([p, pd.DataFrame([sesta])], ignore_index=True)
    if voti_della_5:
        d.voti = pd.concat([d.voti, pd.DataFrame(list(voti_della_5))], ignore_index=True)
    return d


def _voto_della_5(cid, nome, ruolo, squadra):
    return {"stagione": ST, "giornata": 5, "calciatore_id": cid, "nome": nome, "squadra": squadra, "ruolo": ruolo, "voto_red": 6.0,
            "fv_red": 0, "voto_stat": 6, "fv_stat": 0, "voto_ita": 6, "fv_ita": 0, "gol": 0, "gol_subiti": 0, "autogol": 0,
            "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0, "ammonizioni": 0, "espulsioni": 0,
            "subentrato": 0, "sostituito": 0, "data": "2026-09-05 15:00", "t": 5}


def test_partita_giocata_senza_voti_non_e_un_assenza():
    """#658: il calendario dà la partita per giocata prima che escano i voti (o il passo dei voti non riesce). Le presenze recenti la
    contavano, la più pesante, come un'assenza di tutti i giocatori delle due squadre: «gioca N%» crollava fino all'arrivo dei voti.
    Ora una squadra senza nessun voto in quella giornata non la conta: lo stesso «gioca N%» di prima della partita."""
    prima = _p(_con_la_giornata_6(_dati(), giocata_la_5=False), giornata=6)
    senza_voti = _p(_con_la_giornata_6(_dati(), giocata_la_5=True), giornata=6)
    for cid in (1, 2, 3):
        assert senza_voti.at[cid, "p_voto"] == prima.at[cid, "p_voto"], cid
        assert senza_voti.at[cid, "presenze_pesate"] == prima.at[cid, "presenze_pesate"], cid
    # con i voti arrivati per una squadra sola: per quella conta (il Bomber è rimasto fuori), per l'altra no
    meta = _p(_con_la_giornata_6(_dati(), True, [_voto_della_5(9, "Riserva", "A", "alfa")]), giornata=6)
    assert meta.at[1, "p_voto"] < prima.at[1, "p_voto"] - 0.05
    assert (meta.at[2, "p_voto"], meta.at[3, "p_voto"]) == (prima.at[2, "p_voto"], prima.at[3, "p_voto"])


def test_forza_squadre_senza_quote():
    """Chi ha segnato di più e subito meno ha più gol attesi; il fattore campo c'è; i gol attesi sono sempre positivi."""
    d = _dati()
    d.partite.loc[d.partite["casa"] == "alfa", ["gol_casa", "xg_casa"]] = 3
    d.partite.loc[d.partite["trasferta"] == "alfa", ["gol_trasferta", "xg_trasferta"]] = 3
    f = modello.forza_squadre(d, ST, 5, modello.Parametri())
    assert f.attacco["alfa"] > f.attacco["beta"] and f.difesa["alfa"] < f.difesa["beta"]
    lc, lt = f.gol_attesi("alfa", "beta")
    assert lc > lt > 0
    assert not hasattr(modello.Parametri(), "peso_quote")


def test_forza_squadre_senza_partite():
    d = _dati()
    f = modello.forza_squadre(d, ST, 1, modello.Parametri())
    assert f.attacco == {} and f.gol_attesi("alfa", "beta")[0] > 0


def test_senza_nessun_xg_le_previsioni_ci_sono_lo_stesso():
    """Understat non ha dato nessun xG (colonne tutte vuote, come su un'installazione nuova): il modello usa i gol veri
    e non si ferma con un errore 500."""
    d = _dati()
    d = modello.Dati(d.stagioni, d.voti, d.prestazioni.assign(xg=None, xa=None),
                     d.partite.assign(xg_casa=None, xg_trasferta=None), d.calciatori, d.quotazioni, d.extra)
    p = _p(d)
    assert len(p) == 3
    assert p["mu"].notna().all()


def test_pezzi_condivisi_fra_leghe_stessi_numeri():
    """Una lega con bonus diversi riusa i pezzi gia' calcolati per un'altra (stessa fonte del voto): numeri identici a un calcolo da zero."""
    altre = imposta(imposta(Regole(), "bonus.gol.A", "4.5"), "bonus.gol_subito_portiere", "-0.5")
    prob = pd.DataFrame([{"calciatore_id": 1, "squadra": "alfa", "stato": "titolare", "percentuale": 80.0, "nota": None,
                          "in_dubbio": 0, "diffidato": 0}])
    for probabili in (None, prob):
        d = _dati()
        _p(d, probabili=probabili)                                    # prima lega: calcola e ricorda
        assert d._pezzi
        condivise = _p(d, regole=altre, probabili=probabili)          # seconda lega: riusa
        da_zero = _p(_dati(), regole=altre, probabili=probabili)
        pd.testing.assert_frame_equal(condivise, da_zero, check_exact=True)
    d = _dati()
    for g in range(1, 6):                                          # il ricordo ha un tetto
        for par in (modello.Parametri(), modello.Parametri(k_voto=10.0), modello.Parametri(k_voto=30.0), modello.Parametri(k_90=8.0)):
            modello.previsioni(d, ST, g, Regole(), par)
    assert len(d._pezzi) <= modello.MAX_PEZZI


# ---------------------------------------------------------------- rigori dalla quota di squadra (#613)
def test_rigori_dalla_quota_di_squadra_anche_in_produzione():
    """La quota dei rigori è quella «di squadra» a memoria lunga (prima un termine fisso la schiacciava: i rigori attesi erano
    un quarto dei veri), e la previsione la riporta: serve alla frase «rigorista»."""
    assert modello.Parametri().rigori_squadra
    p = _p(_dati())
    # il Bomber ha calciato tutti e 4 i rigori della sua squadra (pesati 0,98 a giornata): 3,81 / (3,81 + 0,5 di un rigorista che
    # ancora non si conosce)
    lungo = sum(0.98 ** k for k in range(1, 5))
    assert p.at[1, "quota_rigori"] == pytest.approx(lungo / (lungo + 0.5), abs=1e-3) and p.at[3, "quota_rigori"] == 0.0
    rigori_partita = modello.forza_squadre(_dati(), ST, 5, modello.Parametri()).rigori_partita
    assert p.at[1, "e_rigori"] == pytest.approx(p.at[1, "quota_rigori"] * rigori_partita * p.at[1, "fattore"], abs=2e-3)
    tutta =modello.previsioni(_dati(), ST, 5, Regole(), modello.Parametri(rigori_di_un_altro=0.0)).set_index("id")
    assert tutta.at[1, "quota_rigori"] == 1.0                    # senza quel termine tutta la quota è sua


# ---------------------------------------------------------------- partite senza statistiche (#613)
def _senza_statistiche(d, giornate):
    """Gli stessi dati come se la fonte delle statistiche per partita si fosse fermata prima di queste giornate."""
    via = d.prestazioni["giornata"].isin(giornate)
    partite = d.partite.copy()
    partite.loc[partite["giornata"].isin(giornate), ["xg_casa", "xg_trasferta"]] = None
    return modello.Dati(d.stagioni, d.voti, d.prestazioni[~via].copy(), partite, d.calciatori, d.quotazioni, d.extra)


def _con_tre_gol_nelle_ultime(d):
    """Nelle giornate 3 e 4 il Bomber segna 3 gol su azione (nei voti) invece di 1; le statistiche non lo sanno."""
    d.voti.loc[(d.voti["calciatore_id"] == 1) & (d.voti["giornata"] >= 3), "gol"] = 3
    return d


def test_partita_senza_statistiche_si_usano_le_righe_ricostruite_dai_voti():
    """La fonte delle statistiche si ferma dopo la giornata 2. Senza ripiego il modello ignora le giornate 3 e 4 (i 3 gol a
    partita del Bomber non contano); con le righe ricostruite dai voti i suoi gol attesi salgono."""
    fermo = _senza_statistiche(_con_tre_gol_nelle_ultime(_dati()), (3, 4))
    senza = _p(fermo)
    ricostruiti = modello.con_prestazioni_dai_voti(fermo)
    con = _p(ricostruiti)
    assert con.at[1, "e_gol"] > senza.at[1, "e_gol"] + 0.1
    assert con.at[1, "e_rigori"] > 0 and con.at[1, "minuti"] == pytest.approx(90.0)
    nuove = ricostruiti.prestazioni[ricostruiti.prestazioni["giornata"] >= 3]
    assert len(nuove) == 6 and set(nuove["understat_partita"]) == {-3, -4}             # le partite 3 e 4, 3 giocatori l'una
    bomber = nuove[nuove["calciatore_id"] == 1].iloc[0]
    assert (bomber["minuti"], bomber["gol"], bomber["rigori_calciati"], bomber["rigori_squadra"]) == (90, 4, 1, 1)
    # al posto degli xG i gol su azione veri, riportati alla scala della fonte (che ne conta di più dei gol), più i rigori
    assert modello.XG_PER_GOL == 1.2 and bomber["xg"] == pytest.approx(3 * 1.2 + modello.XG_RIGORE) and bomber["xa"] == 0
    assert modello.XA_PER_ASSIST == 1.2 and (nuove["xa"] == 1.2 * nuove["assist"]).all()


def test_con_le_statistiche_le_righe_ricostruite_non_si_aggiungono():
    d = _dati()
    stessi = modello.con_prestazioni_dai_voti(d)
    assert len(stessi.prestazioni) == len(d.prestazioni)
    pd.testing.assert_frame_equal(_p(stessi), _p(_dati()))


def test_le_righe_ricostruite_non_raddoppiano_se_la_funzione_gira_due_volte():
    """#638: richiamata sui dati che ha già completato, aggiungeva un'altra volta le stesse righe. Riconosceva le partite
    coperte dall'identificativo della fonte, e le righe ricostruite hanno quello della partita cambiato di segno."""
    una = modello.con_prestazioni_dai_voti(_senza_statistiche(_dati(), (3, 4)))
    due = modello.con_prestazioni_dai_voti(una)
    assert len(una.prestazioni) == 12          # giornate 1 e 2 dalla fonte, 3 e 4 ricostruite: 3 giocatori a partita
    pd.testing.assert_frame_equal(due.prestazioni, una.prestazioni)


def test_le_righe_ricostruite_si_aggiungono_solo_per_le_partite_che_mancano_ancora():
    """Alla prima chiamata i voti della giornata 4 non ci sono ancora; quando arrivano si ricostruisce solo quella."""
    d = _senza_statistiche(_dati(), (3, 4))
    voti_della_4 = d.voti[d.voti["giornata"] == 4]
    d.voti = d.voti[d.voti["giornata"] < 4].copy()
    prima = modello.con_prestazioni_dai_voti(d)
    assert sorted(prima.prestazioni["understat_partita"]) == [-3] * 3 + [101] * 3 + [102] * 3
    prima.voti = pd.concat([prima.voti, voti_della_4], ignore_index=True)
    poi = modello.con_prestazioni_dai_voti(prima)
    assert sorted(poi.prestazioni["understat_partita"]) == [-4] * 3 + [-3] * 3 + [101] * 3 + [102] * 3


def test_partita_senza_statistiche_e_senza_voti_resta_fuori():
    """Una partita giocata di cui non sono ancora arrivati né statistiche né voti: non c'è niente da ricostruire."""
    d = _senza_statistiche(_dati(), (4,))
    d.voti = d.voti[d.voti["giornata"] < 4].copy()
    assert modello.con_prestazioni_dai_voti(d).prestazioni["giornata"].max() == 3


def test_carica_mette_le_righe_ricostruite(tmp_path):
    """Dall'archivio: una partita giocata con i voti ma senza statistiche arriva al modello con le righe ricostruite."""
    from fanta import archivio
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, gol_casa, gol_trasferta, giocata) "
               "VALUES (7, ?, 1, '2026-09-01 15:00', 'alfa', 'beta', 2, 0, 1)", (ST,))
    for cid, sq, gol, sub in ((1, "alfa", 2, 0), (2, "beta", 0, 1)):
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, rig_segnati, "
                   "rig_sbagliati, assist, subentrato, sostituito) VALUES (?, 1, ?, ?, ?, 'A', 6.5, ?, 0, 0, 0, ?, 0)",
                   (ST, cid, f"g{cid}", sq, gol, sub))
    p = modello.carica(db).prestazioni
    db.close()
    assert sorted(zip(p["calciatore_id"], p["squadra"], p["minuti"], p["gol"], p["understat_partita"])) == [
        (1, "alfa", 90.0, 2, -7), (2, "beta", 19.0, 0, -7)]


def _archivio_senza_statistiche(percorso, giocate: int):
    """Un archivio come quello di chi ha acceso solo i voti (la fonte delle statistiche per partita è spenta di default): tabella
    `prestazioni` vuota, `giocate` giornate con i voti, 4 squadre con 4 giocatori per ruolo (16 per ruolo in tutto, tutti con la
    quotazione) sempre in campo 90 minuti."""
    from fanta import archivio
    db = archivio.apri(percorso)
    squadre = ("alfa", "beta", "gamma", "delta")
    rosa = [(100 * s + 10 * r + k, f"{sq}-{ruolo}{k}", ruolo, sq)
            for s, sq in enumerate(squadre, 1) for r, ruolo in enumerate("PDCA") for k in range(4)]
    for cid, nome, ruolo, sq in rosa:
        db.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug, quotazione) VALUES (?, ?, ?, ?, ?, ?)",
                   (cid, nome, ruolo, sq[:3].upper(), sq, 5 + cid % 23))
        db.execute("INSERT INTO quotazioni (stagione, calciatore_id, nome, ruolo, squadra, qi) VALUES (?, ?, ?, ?, ?, ?)",
                   (ST, cid, nome, ruolo, sq, 5 + cid % 23))
    for g in range(1, giocate + 2):
        coppie = (("alfa", "beta"), ("gamma", "delta")) if g % 2 else (("alfa", "gamma"), ("beta", "delta"))
        for k, (casa, trasf) in enumerate(coppie):
            fatta = g <= giocate
            db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, gol_casa, gol_trasferta, giocata) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (10 * g + k, ST, g, f"2026-09-{g:02d} 1{5 + k}:00", casa, trasf,
                                                              (g + k) % 3 if fatta else None, g % 2 if fatta else None, int(fatta)))
            if not fatta:
                continue
            for cid, nome, ruolo, sq in rosa:
                if sq in (casa, trasf):
                    db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, gol_subiti, "
                               "autogol, rig_segnati, rig_sbagliati, rig_parati, assist, mvp, ammonizioni, espulsioni, subentrato, "
                               "sostituito) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, 0, 0, 0, 0, 0)",
                               (ST, g, cid, nome, sq, ruolo, 5.5 + (cid + g) % 3 * 0.5, int(ruolo == "A" and (cid + g) % 4 == 0),
                                int(ruolo == "C" and (cid + g) % 5 == 0)))
    db.commit()
    return db


@pytest.mark.parametrize("giocate", [3, 4, 6])
def test_senza_nessuna_statistica_per_partita_le_previsioni_ci_sono(tmp_path, giocate):
    """D57, regressione della #613: con la tabella `prestazioni` vuota le righe ricostruite dai voti si univano a una tabella letta da
    SQLite con le colonne senza tipo; con pandas 3 restavano testo e dalla quarta giornata (ruoli con 15 giocatori che hanno almeno 3
    partite pesate) le previsioni si fermavano con un errore: Oggi, Formazione, widget e avvisi in errore per chi installa da zero."""
    db = _archivio_senza_statistiche(tmp_path / "t.sqlite", giocate)
    assert db.execute("SELECT COUNT(*) FROM prestazioni").fetchone()[0] == 0
    d = modello.carica(db)
    db.close()
    p = modello.previsioni(d, ST, giocate + 1, Regole(), giocatori=d.calciatori)
    assert len(p) == 64 and p["mu"].notna().all() and p["atteso"].notna().all()
    assert p["minuti"].min() > 80                                     # i minuti vengono dalle righe ricostruite (sempre 90)
    assert len(d.prestazioni) == 64 * giocate and (d.prestazioni["understat_partita"] < 0).all()     # tutti, ogni giornata
    for c in ("minuti", "gol", "assist", "rigori_calciati", "rigori_segnati", "rigori_squadra", "xg", "xa", "t"):
        assert pd.api.types.is_numeric_dtype(d.prestazioni[c]), c


# ---------------------------------------------------------------- livello dei gol della stagione (#613)
# I gol attesi delle squadre partono da `base`, che ha la memoria lunga e, dove ci sono, gli xG della fonte (più alti dei gol
# veri). Il livello li riporta ai gol veri della stagione in corso, tirati verso `base` con K giornate fittizie. Vale per i gol
# delle squadre (gol subiti e porta inviolata dei portieri), non per gol e assist dei giocatori.
def _dati_con_risultato(gol: int) -> modello.Dati:
    """Le 4 giornate giocate finite `gol`-`gol` (xG della fonte come in `_dati`: 1,2 in casa e 1,0 fuori)."""
    d = _dati()
    giocate = d.partite["giocata"] == 1
    d.partite.loc[giocate, ["gol_casa", "gol_trasferta"]] = gol
    return d


def test_livello_della_stagione_tirato_verso_uno_con_le_giornate_fittizie():
    d = _dati_con_risultato(2)
    par = modello.Parametri(k_livello=5.0)
    acceso, spento = modello.forza_squadre(d, ST, 5, par), modello.forza_squadre(d, ST, 5, replace(par, k_livello=None))
    # 4 partite = 8 squadre-partita con 16 gol; il campionato ha 2 squadre, quindi 5 giornate fittizie = 10 squadre-partita
    atteso = (16 + 10 * spento.base) / (8 + 10) / spento.base
    assert 1 < atteso < 2 / spento.base                                 # verso i gol veri della stagione, non fino in fondo
    assert acceso.livello_stagione == pytest.approx(atteso) and spento.livello_stagione == 1.0
    for a, b in zip(acceso.gol_attesi("alfa", "beta"), spento.gol_attesi("alfa", "beta")):
        assert a == pytest.approx(b * atteso)
    # il resto della forza delle squadre è quello di prima
    assert (acceso.base, acceso.casa, acceso.attacco, acceso.difesa, acceso.livello) == (
        spento.base, spento.casa, spento.attacco, spento.difesa, spento.livello)
    # più giornate fittizie: più vicino a 1
    lento = modello.forza_squadre(d, ST, 5, replace(par, k_livello=20.0)).livello_stagione
    assert 1 < lento < atteso


def test_livello_della_stagione_sotto_uno_se_si_segna_meno_degli_xg():
    """Risultati 1-1 con 1,2 e 1,0 xG: i gol attesi di base stanno sopra i gol veri (misto di xG e gol), il livello li abbassa."""
    f = modello.forza_squadre(_dati(), ST, 5, modello.Parametri(k_livello=5.0))
    assert f.base > 1 and f.livello_stagione == pytest.approx((8 + 10 * f.base) / 18 / f.base) and f.livello_stagione < 1


@pytest.mark.parametrize("gol, atteso", [(9, modello.LIVELLO_MAX), (0, modello.LIVELLO_MIN)])
def test_livello_della_stagione_limitato(gol, atteso):
    assert modello.forza_squadre(_dati_con_risultato(gol), ST, 5, modello.Parametri(k_livello=1.0)).livello_stagione == atteso


def test_livello_della_stagione_senza_partite_e_senza_dati_dal_futuro():
    par = modello.Parametri(k_livello=5.0)
    assert modello.forza_squadre(_dati(), ST, 1, par).livello_stagione == 1.0          # nessuna partita giocata prima
    oggi = modello.forza_squadre(_dati_con_risultato(3), ST, 4, par)
    futuro = _dati_con_risultato(3)
    futuro.partite.loc[futuro.partite["giornata"] >= 4, ["gol_casa", "gol_trasferta", "giocata"]] = [9, 9, 1]
    assert modello.forza_squadre(futuro, ST, 4, par) == oggi


def test_il_livello_della_stagione_vale_per_le_squadre_non_per_gol_e_assist_dei_giocatori():
    """Applicato una volta sola: i gol attesi delle due squadre salgono (e con loro i gol subiti attesi del portiere), ma la
    «partita rispetto al solito» dei giocatori resta com'era, quindi gol, assist e rigori attesi non cambiano."""
    d = _dati_con_risultato(3)
    acceso, spento = (modello.previsioni(d, ST, 5, Regole(), modello.Parametri(k_livello=k)).set_index("id") for k in (5.0, None))
    livello = modello.forza_squadre(d, ST, 5, modello.Parametri(k_livello=5.0)).livello_stagione
    assert livello > 1.2
    for c in ("gol_squadra", "gol_avversario"):
        assert (acceso[c] / spento[c]).tolist() == pytest.approx([livello] * len(acceso), abs=0.01)
    for c in ("fattore", "e_gol", "e_assist", "e_rigori", "p_voto", "minuti"):
        assert acceso[c].tolist() == spento[c].tolist(), c
    assert acceso.at[2, "mu"] < spento.at[2, "mu"] - 0.1                # il portiere (id 2) subisce più gol attesi
    assert acceso.at[2, "p_imbattuto"] < spento.at[2, "p_imbattuto"]


def test_in_produzione_livello_della_stagione_e_medie_del_ruolo_pesate():
    par = modello.Parametri()
    assert par.k_livello == 5.0 and par.medie_ruolo_pesate and par.decadimento_base is None

