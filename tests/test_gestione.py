"""Gestione: difficoltà delle partite, indice 0-100, mercato (svincolati che migliorano la squadra)."""
import pandas as pd
import pytest

from fanta import consigli, gestione, lega, scambi
from fanta.regole import Regole

REGOLE = Regole(moduli=["4-4-2"], rosa={"P": 2, "D": 5, "C": 5, "A": 3})


def test_difficolta_a_soglie():
    assert [consigli.difficolta(x) for x in (1.5, 0.5, 0.0, -0.5, -1.5)] == [1, 2, 3, 4, 5]


def test_indice_e_per_ruolo_e_ignora_chi_non_gioca():
    p = pd.DataFrame({"ruolo": ["A", "A", "A", "D", "D"], "p_voto": [0.9, 0.9, 0.05, 0.9, 0.9],
                      "atteso": [7.0, 5.0, 6.0, 5.0, 4.0]}, index=[1, 2, 3, 4, 5])
    i = consigli._indice(p)
    assert i[1] == 100 and i[2] == 50           # tra i due attaccanti che giocano
    assert i[4] == 100                          # i difensori si confrontano con i difensori
    assert i[3] == 50                           # chi non gioca ha un indice, ma non entra nel confronto


def test_titolarita_a_parole():
    x = pd.Series({"stato": "titolare", "p_voto": 0.9, "quota_titolare": 0.9})
    assert consigli.titolarita(x) == "titolare"
    assert consigli.titolarita(x.where(x.index != "p_voto", 0.55)) == "ballottaggio"
    assert consigli.titolarita(x.where(x.index != "stato", "infortunato")) == "fuori"
    # le probabili lo danno titolare e gioca al 93%: «titolare», anche se finora è partito spesso dalla panchina (era «ballottaggio»)
    assert consigli.titolarita(pd.Series({"stato": "titolare", "p_voto": 0.93, "quota_titolare": 0.4})) == "titolare"
    # senza probabili conta ancora quanto parte titolare di solito
    assert consigli.titolarita(pd.Series({"stato": None, "p_voto": 0.93, "quota_titolare": 0.4})) == "ballottaggio"


def _giocatore(**k):
    base = {"stato": None, "percentuale": None, "nota": None, "e_rigori": 0.0, "ruolo": "A", "p_imbattuto": 0.0, "e_gol": 0.68,
            "gol_squadra": 2.0, "gol_avversario": 0.8}
    return pd.Series(base | k)


def test_motivi_senza_percentuali_sul_giocare():
    """Collaudo 2/11/2026: «parte dalla panchina (25%)» accanto a «gioca 19%», due percentuali con due significati. L'unica
    percentuale sul giocare è «gioca N%» (p_voto): quella delle probabili diventa parole."""
    assert consigli.motivi(_giocatore(stato="panchina", percentuale=25.0))[0] == "parte dalla panchina"
    assert consigli.motivi(_giocatore(stato="titolare", percentuale=85.0))[0] == "titolare"
    assert consigli.motivi(_giocatore(stato="titolare", percentuale=55.0))[0] == "titolare in ballottaggio"
    assert consigli.motivi(_giocatore(stato="titolare"))[0] == "titolare"
    for stato in ("titolare", "panchina"):
        for perc in (25.0, 55.0, 60.0, 85.0):
            m = consigli.motivi(_giocatore(stato=stato, percentuale=perc))
            assert not any(f"{perc:.0f}%" in x for x in m), m


def test_rigorista_e_chi_calcia_piu_della_meta_dei_rigori_della_squadra():
    """#613: la frase «rigorista» guardava i rigori attesi a partita (soglia 0,15), che nessuno raggiungeva mai: una squadra ne
    calcia circa 0,14 a partita. Ora guarda la quota dei rigori della squadra che va al giocatore, se gioca."""
    assert "rigorista" in consigli.motivi(_giocatore(stato="titolare", quota_rigori=0.8, e_rigori=0.10))
    assert "rigorista" in consigli.motivi(_giocatore(quota_rigori=0.5, e_rigori=0.06))
    assert "rigorista" not in consigli.motivi(_giocatore(quota_rigori=0.45, e_rigori=0.30))      # ne calcia meno della metà
    assert "rigorista" not in consigli.motivi(_giocatore(e_rigori=0.30))                         # previsione senza la quota
    assert consigli.motivi(_giocatore(stato="squalificato", quota_rigori=0.9)) == ["squalificato"]


def test_infortunato_niente_consigli_sulla_partita():
    """Collaudo 2/11/2026: un infortunato aveva ancora «gol atteso 68%» e «partita favorevole» (oggi «49% di segnare»)."""
    for stato in ("infortunato", "squalificato"):
        assert consigli.motivi(_giocatore(stato=stato, e_rigori=0.3)) == [stato]
        assert consigli.motivi(_giocatore(stato=stato, nota="Lesione muscolare")) == [stato, "Lesione muscolare"]
    m = consigli.motivi(_giocatore(stato="titolare", percentuale=90.0))
    assert "49% di segnare" in m and "partita favorevole" in m           # chi gioca li tiene


def test_mercato_propone_lo_svincolato_che_migliora(monkeypatch):
    tab = {1: ("P", 0.9, 6), 2: ("D", 0.9, 6), 3: ("D", 0.9, 6), 4: ("D", 0.9, 6), 5: ("D", 0.9, 6),
           6: ("C", 0.9, 5), 7: ("C", 0.9, 5), 8: ("C", 0.9, 5), 9: ("C", 0.9, 5), 10: ("A", 0.9, 8), 11: ("A", 0.9, 8),
           21: ("P", 0.9, 6), 22: ("D", 0.9, 6),
           40: ("C", 0.9, 9),    # svincolato molto forte
           41: ("C", 0.2, 9)}    # svincolato forte ma che non gioca: non deve contare
    info = pd.DataFrame([{"id": i, "nome": f"g{i}", "ruolo": r, "squadra": "X", "quotazione": 10}
                         for i, (r, _, _) in tab.items()]).set_index("id")
    v = scambi.Valori([1, 2], 10, [tab, tab], info)
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: v)
    rose = lega.Rose([lega.Squadra("A", [lega.GiocatoreRosa(i, f"g{i}", tab[i][0], "X", costo=5) for i in range(1, 12)], crediti_residui=4),
                      lega.Squadra("B", [lega.GiocatoreRosa(i, f"g{i}", tab[i][0], "X") for i in (21, 22)])], "A")
    m = gestione.mercato(None, REGOLE, rose)
    assert m["svincolati"] == 2
    # con 4 crediti + 2 di rimborso non ci si può permettere lo svincolato da 10: non viene proposto
    assert m["crediti_residui"] == 4 and m["proposte"] == []
    rose.squadre[0].crediti_residui = 20
    ricco = gestione.mercato(None, REGOLE, rose)["proposte"][0]
    assert ricco["entra"]["id"] == 40 and ricco["rimborso"] == 2 and ricco["crediti_dopo"] == 20 + 2 - 10 and ricco["fattibile"] is True
    rose.squadre[0].crediti_residui = None                       # crediti non inseriti: nessun limite
    senza_limite = gestione.mercato(None, REGOLE, rose)
    primo = senza_limite["proposte"][0]
    assert primo["fattibile"] is None and primo["entra"]["id"] == 40 and primo["esce"]["ruolo"] == "C" and primo["guadagno"] > 0
    assert all(p["entra"]["id"] != 41 for p in senza_limite["proposte"])
    with pytest.raises(ValueError):
        gestione.mercato(None, REGOLE, rose, "inesistente")


def test_confronto_scompone_la_differenza_in_cause_e_somma_giusta():
    from fanta import consigli
    base = {"nome": "x", "ruolo": "A", "e_rigori": 0.0, "gol_subiti": 0.0, "p_imbattuto": 0.0}
    a = pd.Series({**base, "p_voto": 0.9, "mu": 7.0, "mu_voto": 6.0, "e_gol": 0.3, "e_assist": 0.1})
    b = pd.Series({**base, "p_voto": 0.5, "mu": 6.5, "mu_voto": 6.2, "e_gol": 0.1, "e_assist": 0.1})
    s = consigli.spiega(a, b, REGOLE)
    assert sum(f["effetto"] for f in s["fattori"]) == pytest.approx(s["differenza"], abs=0.01)
    assert s["differenza"] == pytest.approx(0.9 * 7.0 - 0.5 * 6.5, abs=0.001)
    giocare = next(f for f in s["fattori"] if f["chiave"] == "giocare")
    assert giocare["effetto"] > 0 and giocare["percentuale"]
    assert "gioca di più" in consigli._frase_perche("A", "B", s, 3.05)
    assert "alla pari" in consigli._frase_perche("A", "B", {"differenza": 0.05, "fattori": []}, 0.05)


def test_confronto_in_formazione_spiega_titolare_e_panchinaro(monkeypatch):
    from fanta import consigli
    righe = [("A1", "A", 0.9, 7.0), ("A2", "A", 0.8, 6.5), ("P1", "P", 0.9, 6.0)] + [(f"D{i}", "D", 0.9, 6.0) for i in range(4)] \
        + [(f"C{i}", "C", 0.9, 6.0) for i in range(3)] + [("A3", "A", 0.9, 6.8), ("A4", "A", 0.5, 6.6)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": p, "mu": mu, "mu_voto": mu - 0.2} for n, r, p, mu in righe])
    prev.index = range(1, len(righe) + 1)
    schede = {str(i): {"nome": prev.at[i, "nome"]} for i in prev.index}
    titolari = [i for i in prev.index if prev.at[i, "nome"] not in ("A2", "A4")]
    f = {"modulo": "4-3-3", "moduli": [{"modulo": "4-3-3", "titolari": titolari, "panchina": [2, 3 + 8 + 2 - 1]}], "schede": schede}
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: f)
    regole = Regole(moduli=["4-3-3"], rosa={"P": 1, "D": 4, "C": 3, "A": 4})
    r = consigli._in_formazione(None, regole, object(), None, None, "4-3-3", 1, 2, prev)       # A1 titolare, A2 in panchina
    assert r["posto_a"] == "titolare" and r["posto_b"].startswith("panchina")
    assert r["differenza"] is not None and "Il sistema schiera A1 come titolare" in r["testo"]
    r2 = consigli._in_formazione(None, regole, object(), None, None, "4-3-3", 4, 2, prev)      # attaccante e difensore: ruoli diversi
    assert "ruoli diversi" in r2["testo"]
    r3 = consigli._in_formazione(None, regole, object(), None, None, "4-3-3", 1, 99, prev)     # uno non è in rosa
    assert r3 is None


def test_i_tuoi_migliori_in_ordine_di_fantavoto_atteso():
    """#457: Oggi mostrava 8,3 · 6,5 · 6,6. I tre si scelgono per punti attesi, poi si ordinano per il numero sullo schermo."""
    tit = [{"id": 1, "fv_atteso": 8.3, "punti_attesi": 7.5}, {"id": 2, "fv_atteso": 6.5, "punti_attesi": 5.9},
           {"id": 3, "fv_atteso": 6.6, "punti_attesi": 5.4}, {"id": 4, "fv_atteso": 9.0, "punti_attesi": 2.7}]   # 4 gioca poco: fuori
    assert [g["id"] for g in gestione.migliori_della_giornata(tit)] == [1, 3, 2]      # 8,3 · 6,6 · 6,5
    pari = [{"id": 1, "fv_atteso": 6.5, "punti_attesi": 5.0}, {"id": 2, "fv_atteso": 6.5, "punti_attesi": 5.8}]
    assert [g["id"] for g in gestione.migliori_della_giornata(pari)] == [2, 1]        # a pari fantavoto, più punti attesi
    assert gestione.migliori_della_giornata([]) == []


@pytest.mark.parametrize("p, gioca, non_gioca", [(0.845, 85, 15), (0.3447, 35, 65)])
def test_confronto_le_percentuali_tornano_con_gioca_n(monkeypatch, p, gioca, non_gioca):
    """#452: accanto al giocatore la web scrive «gioca 85%» (Math.round di 0,845); la frase del Confronto deve dire 15%, non 16%.
    La web parte da `p_voto` arrotondato a 3 decimali (scheda): 0,3447 → 0,345 → «gioca 35%», quindi 65%, non 66%."""
    from fanta import consigli
    righe = [("A1", "A", p, 7.0), ("A2", "A", 0.8, 6.5), ("P1", "P", 0.9, 6.0)] + [(f"D{i}", "D", 0.9, 6.0) for i in range(4)] \
        + [(f"C{i}", "C", 0.9, 6.0) for i in range(3)] + [("A3", "A", 0.9, 6.8), ("A4", "A", 0.5, 6.6)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": p, "mu": mu, "mu_voto": mu - 0.2} for n, r, p, mu in righe])
    prev.index = range(1, len(righe) + 1)
    schede = {str(i): {"nome": prev.at[i, "nome"]} for i in prev.index}
    titolari = [i for i in prev.index if prev.at[i, "nome"] not in ("A2", "A4")]
    f = {"modulo": "4-3-3", "moduli": [{"modulo": "4-3-3", "titolari": titolari, "panchina": [2, 12]}], "schede": schede}
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: f)
    regole = Regole(moduli=["4-3-3"], rosa={"P": 1, "D": 4, "C": 3, "A": 4})
    r = consigli._in_formazione(None, regole, object(), None, None, "4-3-3", 1, 2, prev)
    assert f"Se A1 non prende voto ({non_gioca}% di probabilità)" in r["testo"]
    s = {"differenza": 1.0, "fattori": [{"chiave": "giocare", "a": p, "b": 0.125, "effetto": 1.0}]}
    assert f"gioca di più ({gioca}% contro 13%" in consigli._frase_perche("A1", "A4", s, 1.0)


def _prev_433():
    righe = [("P1", "P", 0.95, 6.0), ("P2", "P", 0.9, 5.5)] + [(f"D{i}", "D", 0.9, 6.0 + i / 10) for i in range(6)] \
        + [(f"C{i}", "C", 0.9, 6.0 + i / 10) for i in range(5)] + [(f"A{i}", "A", 0.9, 6.5 + i / 5) for i in range(5)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": p, "mu": mu, "mu_voto": mu - 0.2} for n, r, p, mu in righe])
    prev.index = range(1, len(righe) + 1)
    return prev


def test_valuta_formazione_scelta_a_mano(monkeypatch):
    prev = _prev_433()
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    regole = Regole(moduli=["4-3-3", "4-4-2"], rosa={"P": 2, "D": 6, "C": 5, "A": 5})
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])], "Mia")
    def consigliata(db, regole, rose, nome=None, giornata=None, simulazioni=600, adesso=None):
        from fanta import formazione as fz
        lista = [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]),
                              float(prev.at[i, "mu_voto"])) for i in prev.index]
        m = fz.migliore(lista, regole, simulazioni)
        return {"punteggio_atteso": round(m.atteso, 1), "moduli": [{"modulo": x.modulo, "punteggio_atteso": round(x.atteso, 1)} for x in m.tutte]}
    monkeypatch.setattr(consigli, "formazione", consigliata)
    migliori = [1, 5, 6, 7, 8, 11, 12, 13, 16, 17, 18]
    r = consigli.valuta(None, regole, rose, migliori)
    assert r["modulo"] == "4-3-3" and len(r["panchina"]) > 0
    assert r["differenza"] == pytest.approx(0, abs=0.5)                 # sono quasi i titolari consigliati
    r2 = consigli.valuta(None, regole, rose, [2, 3, 4, 5, 6, 9, 10, 11, 14, 15, 16])      # portiere, difensori, centrocampisti e attaccanti peggiori
    assert r2["punteggio_atteso"] < r["punteggio_atteso"] and r2["differenza"] < 0
    with pytest.raises(ValueError):
        consigli.valuta(None, regole, rose, migliori[:10])              # ne servono 11
    with pytest.raises(ValueError):
        consigli.valuta(None, regole, rose, [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13])    # senza portiere
    with pytest.raises(ValueError):
        consigli.valuta(None, regole, rose, migliori[:10] + [999])    # uno non è in rosa


def test_valuta_la_differenza_torna_con_i_numeri_scritti(monkeypatch):
    """#392: sotto «60,0 punti attesi» la riga «−4,1 rispetto alla consigliata con lo stesso modulo (64,1)»: la differenza è quella
    dei due numeri scritti (60,05 − 64,1 = −4,05 darebbe «−4,0», che con 60,0 e 64,1 non torna)."""
    from fanta import formazione as fz
    prev = _prev_433()
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {"punteggio_atteso": 64.1, "moduli": [{"modulo": "4-3-3", "punteggio_atteso": 64.1}]})
    monkeypatch.setattr(fz.Valutatore, "statistiche", lambda self, *a, **k: (60.05, 8.0))
    regole = Regole(moduli=["4-3-3"], rosa={"P": 2, "D": 6, "C": 5, "A": 5})
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])], "Mia")
    r = consigli.valuta(None, regole, rose, [1, 5, 6, 7, 8, 11, 12, 13, 16, 17, 18])
    assert (r["punteggio_atteso"], r["consigliata_stesso_modulo"], r["differenza"]) == (60.0, 64.1, -4.1)


def test_oggi_dice_quali_squadre_hanno_miei_titolari(monkeypatch):
    """Campo nuovo e facoltativo `miei_titolari` {squadra: [giocatori]}: serve a evidenziare le partite nei risultati in diretta."""
    import sqlite3
    from types import SimpleNamespace as NS
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole: (pd.DataFrame(index=[]), 10, True))
    tit = [{"id": 1, "nome": "A", "ruolo": "P", "squadra": "inter", "punti_attesi": 6.0},
           {"id": 2, "nome": "B", "ruolo": "D", "squadra": "inter", "punti_attesi": 5.0},
           {"id": 3, "nome": "C", "ruolo": "A", "squadra": "milan", "punti_attesi": 7.0}]
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {"titolari": tit, "modulo": "3-4-3", "punteggio_atteso": 60.0, "squadra": "X"})
    rose = NS(mia_squadra="X", squadra=lambda n: NS(giocatori=[]))
    o = gestione.oggi(db, Regole(), rose)
    assert {k: [g["id"] for g in v] for k, v in o["miei_titolari"].items()} == {"inter": [1, 2], "milan": [3]}


def test_la_mia_scelta_si_salva_e_si_cancella(tmp_path):
    from fanta import scelte
    f = tmp_path / "scelte.json"
    assert scelte.leggi("2026-27", 9, f) is None
    scelte.salva("2026-27", 9, [1, 2, 3], "4-3-3", f)
    assert scelte.leggi("2026-27", 9, f)["titolari"] == [1, 2, 3]
    scelte.cancella("2026-27", 9, f)
    assert scelte.leggi("2026-27", 9, f) is None
    f.write_text("rotto", encoding="utf-8")
    assert scelte.leggi("2026-27", 9, f) is None


def test_testo_formazione():
    f = {"giornata": 9, "giornata_lega": 9, "schede": {"1": {"nome": "Vicario", "ruolo": "P"}, "2": {"nome": "Bastoni", "ruolo": "D"},
                                                       "3": {"nome": "Bonny", "ruolo": "A"}, "4": {"nome": "Bijlow", "ruolo": "P"}}}
    assert consigli.testo_formazione(f, "1-1-0", [1, 2, 3], [4]) == "Giornata 9 · 9ª di Serie A · 1-1-0\nP: Vicario\nD: Bastoni\nC: \nA: Bonny\nPanchina: 1) Bijlow"


def test_oggi_mostra_la_scelta_salvata_dall_utente(monkeypatch, tmp_path):
    """Se l'utente ha salvato la sua formazione per la giornata, Oggi la mostra (modulo, punti, titolari) con `tua_scelta`."""
    import sqlite3
    from types import SimpleNamespace as NS
    from fanta import scelte
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 10, True))
    sch = {str(i): {"id": i, "nome": f"g{i}", "ruolo": "A", "squadra": "inter", "punti_attesi": float(i)} for i in range(1, 15)}
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {"titolari": [sch[str(i)] for i in range(1, 12)], "modulo": "5-3-2",
                                                                 "punteggio_atteso": 71.9, "squadra": "X", "schede": sch})
    monkeypatch.setattr(consigli, "valuta", lambda db, regole, rose, tit, nome=None, giornata=None: {"modulo": "4-4-2", "punteggio_atteso": 71.7})
    rose = NS(mia_squadra="X", squadra=lambda n: NS(giocatori=[]))
    f = tmp_path / "scelte.json"
    o = gestione.oggi(db, Regole(), rose, file_scelte=f)
    assert o["formazione"]["modulo"] == "5-3-2" and o["formazione"]["tua_scelta"] is False        # nessuna scelta: la consigliata
    scelte.salva("2026-27", 10, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12], "4-4-2", f)
    o = gestione.oggi(db, Regole(), rose, file_scelte=f)
    assert (o["formazione"]["modulo"], o["formazione"]["punteggio_atteso"], o["formazione"]["tua_scelta"]) == ("4-4-2", 71.7, True)
    assert sum(len(v) for v in o["miei_titolari"].values()) == 11 and 12 in [g["id"] for g in o["miei_titolari"]["inter"]]
    scelte.cancella("2026-27", 10, f)
    assert gestione.oggi(db, Regole(), rose, file_scelte=f)["formazione"]["tua_scelta"] is False


def _mercato_con_profili(monkeypatch, profili_extra, **k):
    """Mercato su dati finti con i profili per il buon senso (buon_senso.py): 11 titolari sicuri, uno svincolato che vale molto di più."""
    tab = {i: ("C", 0.9, 5) for i in range(1, 12)} | {21: ("P", 0.9, 6), 22: ("D", 0.9, 6), 40: ("C", 0.9, 9)}
    info = pd.DataFrame([{"id": i, "nome": f"g{i}", "ruolo": r, "squadra": "X", "quotazione": 10}
                         for i, (r, _, _) in tab.items()]).set_index("id")
    monkeypatch.setattr(consigli, "valori_scambi", lambda db, regole: scambi.Valori([1, 2], 10, [tab, tab], info))
    base = {"ruolo": "C", "squadra": "como", "p_voto": 0.95, "quota_titolare": 0.95, "p_lungo": 0.95, "stato": "titolare",
            "nota": None, "percentuale": 90.0, "mu": 9.5, "dubbio": False}     # i miei titolari valgono più dello svincolato: protetti
    prof = {i: base | {"nome": f"g{i}"} for i in range(1, 12)} | {40: base | {"nome": "g40", "mu": 9.0}}
    for i, extra in profili_extra.items():
        prof[i] = prof[i] | extra
    monkeypatch.setattr(gestione, "_profili", lambda db, regole: prof)
    rose = lega.Rose([lega.Squadra("A", [lega.GiocatoreRosa(i, f"g{i}", "C", "X", costo=5) for i in range(1, 12)], crediti_residui=50),
                      lega.Squadra("B", [lega.GiocatoreRosa(i, f"g{i}", tab[i][0], "X") for i in (21, 22)])], "A")
    return gestione.mercato(None, REGOLE, rose, **k)


def test_mercato_buon_senso_boccia_i_cambi_stupidi(monkeypatch):
    """Chi entra non è un titolare fisso (gioca poco): il cambio, anche se vale molto sulla carta, non si consiglia e finisce tra le scartate."""
    m = _mercato_con_profili(monkeypatch, {40: {"quota_titolare": 0.3, "p_lungo": 0.3, "p_voto": 0.5}})
    assert m["proposte"] == [] and m["scartate"] and all(not t["sensato"] and t["motivo"] for t in m["scartate"])
    # senza la protezione dei miei titolari, il motivo è proprio che chi entra non gioca
    m = _mercato_con_profili(monkeypatch, {i: {"mu": 4.0, "quota_titolare": 0.3, "p_lungo": 0.3} for i in range(1, 12)}
                             | {40: {"quota_titolare": 0.3, "p_lungo": 0.3, "p_voto": 0.5}})
    assert m["proposte"] == [] and "g40" in m["scartate"][0]["motivo"]


def test_mercato_buon_senso_tiene_i_cambi_sensati(monkeypatch):
    """Un titolare fuori per mesi si sostituisce con un titolare fisso: il consiglio resta e spiega il perché."""
    m = _mercato_con_profili(monkeypatch, {3: {"stato": "infortunato", "nota": "crociato, fuori per mesi", "p_voto": 0.0, "quota_titolare": 0.9}})
    primo = m["proposte"][0]
    assert primo["esce"]["id"] == 3 and primo["entra"]["id"] == 40 and primo["sensato"] is True
    assert "fuori a lungo" in primo["motivo"] and "titolare fisso" in primo["motivo"]


def test_mercato_senza_buon_senso_per_il_tasso_dei_crediti(monkeypatch):
    """Per stimare quanto valgono i crediti contano i numeri: senza buon senso le proposte sono quelle di sempre."""
    flop = {40: {"quota_titolare": 0.3, "p_lungo": 0.3, "p_voto": 0.5}}
    assert _mercato_con_profili(monkeypatch, flop)["proposte"] == []
    m = _mercato_con_profili(monkeypatch, flop, con_buon_senso=False)
    assert m["proposte"] and m["scartate"] == []
