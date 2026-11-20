"""Le misure di `verifica` (#614): avversari onesti (numero fisso per ruolo, fantamedia tirata verso il ruolo), massimo possibile
con le regole della lega, punti su rose estratte a sorte con l'intervallo a gruppi di giornata. Dati inventati."""
import itertools
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fanta import formazione as fz
from fanta import verifica
from fanta.modello import Parametri
from fanta.regole import Regole, imposta

S1, S2 = "2025-26", "2026-27"
RUOLI = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6          # 25 giocatori, id da 1 a 25


def _voto(st, g, i, voto, ruolo=None):
    """Un voto; i giocatori con l'id dispari sono della squadra «aa», gli altri di «bb» (l'unica partita della giornata)."""
    return {"stagione": st, "giornata": g, "calciatore_id": i, "ruolo": ruolo or RUOLI[i - 1], "voto_red": voto,
            "squadra": "aa" if i % 2 else "bb"}


def _dati(voti):
    """Una partita per giornata (aa-bb), una a settimana; ogni voto ha la data della sua partita (come `modello.carica`)."""
    partite = pd.DataFrame([{"id": 100 * k + g, "stagione": st, "giornata": g, "data": f"{st[:4]}-10-{7 * g:02d} 15:00",
                             "casa": "aa", "trasferta": "bb", "giocata": 1}
                            for k, st in enumerate((S1, S2)) for g in range(1, 7)])
    voti = pd.DataFrame(voti)
    if len(voti):
        voti = voti.merge(partite[["stagione", "giornata", "data"]], on=["stagione", "giornata"], how="left")
    return SimpleNamespace(stagioni=[S1, S2], partite=partite, voti=voti)


@pytest.fixture
def finto(monkeypatch):
    """Il fantavoto è il voto; le previsioni danno a tutti i 25 giocatori 0,9 di giocare e un fantavoto atteso che cresce con l'id."""
    def previsioni(d, stagione, giornata, regole, par, oracolo=None):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": RUOLI[i - 1], "p_voto": 0.9, "mu": 5.5 + i * 0.05, "mu_voto": 6.0,
                              "partita": 100 * (stagione == S2) + giornata} for i in range(1, 26)])
    monkeypatch.setattr(verifica, "previsioni", previsioni)
    monkeypatch.setattr(verifica, "fantavoto", lambda r, ruolo, regole: float(r["voto_red"]))


# ---------------------------------------------------------------- avversari onesti
def test_avversari_numero_fisso_per_ruolo_e_fantamedia_tirata(finto):
    # difensori: il 4 ha preso 8 e 8 la stagione scorsa e 5 in questa; il 5 un solo 6; il 6 non ha mai giocato
    d = _dati([_voto(S1, 1, 4, 8.0), _voto(S1, 2, 4, 8.0), _voto(S2, 1, 4, 5.0), _voto(S2, 1, 5, 6.0),
               _voto(S2, 1, 20, 7.0), _voto(S2, 3, 4, 10.0)])                       # l'ultimo è dopo la giornata 2: non conta
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    assert ruolo == {"D": pytest.approx(27 / 4), "A": pytest.approx(7.0)}             # media di tutti i voti del ruolo, di prima
    k = verifica.PRESENZE_FITTIZIE
    assert tirata[4] == pytest.approx((21 + k * 6.75) / (3 + k))                      # tutta la storia, tirata verso il ruolo
    assert tirata[5] == pytest.approx((6 + k * 6.75) / (1 + k))
    assert 6 not in tirata.index                                                      # senza voti: chi chiama usa la media del ruolo
    # la fantamedia di prima (solo la stagione in corso) resta quella: serve a S2 e si stampa per confronto
    assert verifica._fantamedia(d, S2, 2, Regole()).to_dict() == {4: 5.0, 5: 6.0, 20: 7.0}


def test_gli_avversari_non_vedono_i_voti_della_giornata_stessa(finto):
    """La giornata da prevedere non è fra i dati dell'avversario: i suoi voti sono la risposta. Con «fino alla giornata
    compresa» il 6 (mai visto prima) avrebbe una fantamedia e il ruolo dei centrocampisti un voto in più."""
    d = _dati([_voto(S2, 1, 4, 6.0), _voto(S2, 2, 4, 10.0), _voto(S2, 2, 6, 9.0), _voto(S2, 2, 12, 9.0)])
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    assert ruolo == {"D": 6.0} and list(tirata.index) == [4] and tirata[4] == pytest.approx(6.0)


def test_gli_avversari_non_vedono_un_recupero_giocato_dopo(finto):
    """Un recupero della giornata 3 giocato il 29/11, dopo l'inizio della giornata 5 (22/11): il modello per la giornata 5 non lo
    vede (filtra per data), e nemmeno la fantamedia di confronto. Prima la fantamedia filtrava per numero di giornata e contava
    il 12 del recupero (#832, sonda del revisore)."""
    partite = pd.DataFrame([{"id": 1, "stagione": S2, "giornata": 3, "data": "2026-11-29 15:00", "giocata": 1},   # recupero
                            {"id": 2, "stagione": S2, "giornata": 4, "data": "2026-11-08 15:00", "giocata": 1},
                            {"id": 3, "stagione": S2, "giornata": 5, "data": "2026-11-22 15:00", "giocata": 1}])
    voti = pd.DataFrame([{**_voto(S2, 4, 7, 6.0, "A"), "data": "2026-11-08 15:00"},
                         {**_voto(S2, 3, 7, 12.0, "A"), "data": "2026-11-29 15:00"}])
    d = SimpleNamespace(stagioni=[S2], partite=partite, voti=voti)
    tirata, ruolo = verifica.avversari(d, S2, 5, Regole())
    assert ruolo == {"A": 6.0} and tirata.to_dict() == {7: pytest.approx(6.0)}
    assert verifica._fantamedia(d, S2, 5, Regole()).to_dict() == {7: 6.0}
    # per la giornata 6 (dopo il recupero) il voto del recupero c'è
    partite.loc[3] = {"id": 4, "stagione": S2, "giornata": 6, "data": "2026-12-06 15:00", "giocata": 1}
    assert verifica._fantamedia(d, S2, 6, Regole()).to_dict() == {7: 9.0}


def test_la_formazione_da_fantamedia_si_sceglie_con_la_fantamedia_tirata(finto, monkeypatch):
    """Sulle rose della lega la formazione «da fantamedia» (l'avversario dei punti) si sceglie con la fantamedia tirata verso il
    ruolo, chi non ha voti con la media del ruolo: non con la fantamedia della sola stagione (6 a chi non ha voti)."""
    voti = [_voto(S1, g, i, 4.0 + (i % 5)) for g in range(1, 7) for i in range(1, 26) if i % 4]     # chi ha l'id multiplo di 4 mai
    voti += [_voto(S2, 1, i, 9.0 - (i % 5)) for i in range(1, 26) if i % 4]                          # in questa stagione al contrario
    voti += [_voto(S2, 2, i, 6.0) for i in range(1, 26)]
    d = _dati(voti)
    scelte, vera = [], fz.migliore
    monkeypatch.setattr(fz, "migliore", lambda rosa, *a, **k: scelte.append({g.id: g.mu for g in rosa}) or vera(rosa, *a, **k))
    verifica.verifica_giornata(d, S2, 2, Regole(), Parametri(), rose=[list(range(1, 26))], simulazioni=20)
    tirata, ruolo = verifica.avversari(d, S2, 2, Regole())
    attese = {i: float(tirata[i]) if i in tirata.index else ruolo[RUOLI[i - 1]] for i in range(1, 26)}
    assert len(scelte) == 2 and scelte[1] == pytest.approx(attese)                   # la seconda scelta è quella «da fantamedia»
    assert scelte[1] != pytest.approx({i: verifica._fantamedia(d, S2, 2, Regole()).get(i, 6.0) for i in range(1, 26)})


def test_verifica_misura_il_modello_contro_gli_avversari_onesti(finto):
    voti = [_voto(S1, g, i, 6.0 + (i % 3) * 0.5) for g in range(1, 7) for i in range(1, 26)]
    voti += [_voto(S2, g, i, 6.0 + (i % 3) * 0.5) for g in range(1, 3) for i in range(1, 26)]
    d = _dati(voti)
    e = verifica.verifica_giornata(d, S2, 2, Regole(), Parametri())
    # ognuno prende sempre lo stesso voto: la fantamedia tirata sbaglia poco, il numero fisso per ruolo di più, e con sette
    # presenze la fantamedia della sola stagione (una presenza) è uguale al voto vero
    assert 0 < e.quadratico_fantamedia < e.quadratico_ruolo
    assert e.quadratico_fantamedia_stagione == pytest.approx(0.0)
    assert e.errore_ruolo > e.errore_fantamedia > 0
    t = verifica.verifica(d, Regole(), Parametri(), [(S2, 2)], scrivi=None)
    assert {"quadratico_ruolo", "quadratico_fantamedia_stagione", "errore_ruolo"} <= set(t.columns)


def test_una_partita_giocata_ancora_senza_voti_non_conta(monkeypatch):
    """Due partite della giornata 5, tutte e due giocate per il calendario, ma i voti della seconda non sono ancora arrivati: i
    suoi giocatori non contano come «non hanno giocato». Prima entravano nel punteggio di Brier (0,41 invece di 0,01) e nelle
    rose, con zero punti (#832, sonda del revisore)."""
    ruolo = lambda i: RUOLI[(i - 1) % 25]                                        # noqa: E731
    squadra = lambda i: ("aa" if i % 2 else "ab") if i <= 25 else ("ba" if i % 2 else "bb")   # noqa: E731

    def previsioni(d, stagione, giornata, regole, par, oracolo=None):
        return pd.DataFrame([{"id": i, "nome": f"G{i}", "ruolo": ruolo(i), "p_voto": 0.9, "mu": 5.5 + (i % 25) * 0.05, "mu_voto": 6.0,
                              "partita": 1 if i <= 25 else 2} for i in range(1, 51)])
    monkeypatch.setattr(verifica, "previsioni", previsioni)
    monkeypatch.setattr(verifica, "fantavoto", lambda r, ru, regole: float(r["voto_red"]))
    partite = pd.DataFrame([{"id": 1, "stagione": S2, "giornata": 5, "data": "2026-10-04 15:00", "casa": "aa", "trasferta": "ab", "giocata": 1},
                            {"id": 2, "stagione": S2, "giornata": 5, "data": "2026-10-04 18:00", "casa": "ba", "trasferta": "bb", "giocata": 1}])
    prima = [{"stagione": S2, "giornata": 4, "calciatore_id": i, "ruolo": ruolo(i), "voto_red": 6.0, "squadra": squadra(i),
              "data": "2026-09-27 15:00"} for i in range(1, 51)]
    g5 = [{"stagione": S2, "giornata": 5, "calciatore_id": i, "ruolo": ruolo(i), "voto_red": 6.5, "squadra": squadra(i),
           "data": partite.at[0 if i <= 25 else 1, "data"]} for i in range(1, 51)]
    rosa = [1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21, 22, 29, 30, 31, 32, 37, 38, 39, 40, 46, 47, 48]
    esiti = {}
    for nome, voti5 in (("tutti", g5), ("senza la seconda", g5[:25])):
        d = SimpleNamespace(stagioni=[S2], partite=partite, voti=pd.DataFrame(prima + voti5))
        esiti[nome] = verifica.verifica_giornata(d, S2, 5, Regole(), Parametri(), rose=[rosa], simulazioni=30)
    assert esiti["tutti"].n == 50 and esiti["tutti"].brier == pytest.approx(0.01) and esiti["tutti"].formazioni is not None
    senza = esiti["senza la seconda"]
    assert senza.n == 25 and senza.brier == pytest.approx(0.01)
    assert senza.formazioni is None              # della rosa restano 14 giocatori: troppo pochi per un confronto, si salta


# ---------------------------------------------------------------- massimo possibile
def _rosa():
    return [fz.Giocatore(i, f"G{i}", RUOLI[i - 1], 0.9, 6.0, 6.0) for i in range(1, 26)]


def _con_modificatore():
    r = Regole()
    r.modificatore_difesa.attivo, r.modificatore_difesa.min_difensori = True, 4
    r.modificatore_difesa.soglie = [[6.0, 1.0], [6.5, 3.0], [7.0, 6.0]]
    return r


def test_massimo_possibile_conta_il_modificatore_della_difesa():
    """Tutti prendono fantavoto e voto 6 tranne quattro difensori con voto 7,5: senza modificatore il massimo è 66; con il
    modificatore conviene schierare 4 difensori (media di portiere e tre migliori 7,1: +6)."""
    fv = {i: 6.0 for i in range(1, 26)}
    voto = dict(fv) | {4: 7.5, 5: 7.5, 6: 7.5, 7: 7.5}
    assert verifica._perfetta(_rosa(), fv, Regole(), voto) == 66.0
    assert verifica._perfetta(_rosa(), fv, _con_modificatore()) == 66.0             # senza i voti resta il conto di prima
    assert verifica._perfetta(_rosa(), fv, _con_modificatore(), voto) == 72.0


def test_massimo_possibile_sceglie_i_difensori_per_fantavoto_e_modificatore_insieme():
    """Il difensore con il fantavoto più alto (9, per un gol) ha il voto basso: il massimo tiene lui e i tre con il voto alto."""
    fv = {i: 6.0 for i in range(1, 26)} | {4: 9.0}
    voto = {i: 6.0 for i in range(1, 26)} | {4: 5.0, 5: 7.5, 6: 7.5, 7: 7.5, 1: 7.5}
    assert verifica._perfetta(_rosa(), fv, _con_modificatore(), voto) == 66.0 + 3.0 + 6.0


@pytest.mark.parametrize("seme", range(6))
def test_il_massimo_possibile_non_e_mai_sotto_una_formazione_schierata(seme):
    """Con il modificatore della difesa e il cambio di modulo: nessuna formazione di giocatori con voto fa più del massimo."""
    rng = np.random.default_rng(seme)
    r = imposta(_con_modificatore(), "panchina.max_sostituzioni", "0")
    rosa = _rosa()
    con_voto = [g for g in rosa if rng.random() < 0.8]
    fv = {g.id: float(np.round(rng.normal(6.3, 1.5) * 2) / 2) for g in con_voto}
    voto = {g.id: float(np.round(rng.normal(6.1, 0.6) * 2) / 2) for g in con_voto}
    gioca = {g.id: g.id in fv for g in rosa}
    massimo = verifica._perfetta(rosa, fv, r, voto)
    per_ruolo = {ru: [g for g in con_voto if g.ruolo == ru] for ru in "PDCA"}
    for modulo in r.moduli:
        d, c, a = (int(x) for x in modulo.split("-"))
        if any(len(per_ruolo[ru]) < n for ru, n in zip("PDCA", (1, d, c, a))):
            continue
        for _ in range(40):
            tit = [per_ruolo[ru][k] for ru, n in zip("PDCA", (1, d, c, a)) for k in rng.choice(len(per_ruolo[ru]), n, replace=False)]
            punti = fz.punteggio(tit, [], gioca, {g.id: fv.get(g.id, 0.0) for g in rosa}, {g.id: voto.get(g.id, 0.0) for g in rosa}, r)
            assert punti <= massimo + 1e-9, (modulo, punti, massimo)
    # ed è raggiunto da una formazione vera (forza bruta sui difensori del modulo migliore)
    migliori = []
    for modulo in r.moduli:
        d, c, a = (int(x) for x in modulo.split("-"))
        if any(len(per_ruolo[ru]) < n for ru, n in zip("PDCA", (1, d, c, a))):
            continue
        centro = sorted(per_ruolo["C"], key=lambda g: -fv[g.id])[:c] + sorted(per_ruolo["A"], key=lambda g: -fv[g.id])[:a]
        for p in per_ruolo["P"]:
            for dif in itertools.combinations(per_ruolo["D"], d):
                migliori.append(fz.punteggio([p, *dif, *centro], [], gioca, {g.id: fv.get(g.id, 0.0) for g in rosa},
                                             {g.id: voto.get(g.id, 0.0) for g in rosa}, r))
    assert massimo == pytest.approx(max(migliori))


def test_nella_verifica_il_massimo_non_sta_sotto_la_consigliata(finto):
    """Con il voto d'ufficio una formazione con un buco può fare più punti di undici giocatori con voto: il massimo mostrato non
    sta comunque sotto i punti delle formazioni valutate."""
    r = _con_modificatore()
    voti = [_voto(S2, g, i, 6.0 + (i % 4) * 0.5) for g in (1, 2) for i in range(1, 26)]
    e = verifica.verifica_giornata(_dati(voti), S2, 2, r, Parametri(), rose=[list(range(1, 26))], simulazioni=30)
    assert e.formazioni["perfetta"] >= max(e.formazioni["modello"], e.formazioni["fantamedia"])


def test_con_il_voto_d_ufficio_il_massimo_sale_alla_formazione_con_i_buchi(finto):
    """Il caso in cui il conto del massimo (solo chi ha preso voto) sta davvero sotto una formazione: voto d'ufficio 6 a chi non
    ha voto né sostituto, niente cambi, e gli undici con il voto hanno preso tutti 3. Le formazioni scelte prima (fantavoto atteso
    più alto, id alti) hanno molti buchi e fanno più di 33: il massimo mostrato è il loro, sulle rose della lega e su quelle a sorte."""
    r = imposta(Regole(), "panchina.max_sostituzioni", "0")
    r.voto_senza_sostituto = 6.0
    con_voto = [1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21]                                # un 4-4-2 con voto, gli id bassi
    voti = [_voto(S2, 1, i, 6.0) for i in range(1, 26)] + [_voto(S2, 2, i, 3.0) for i in con_voto]
    e = verifica.verifica_giornata(_dati(voti), S2, 2, r, Parametri(), rose=[list(range(1, 26))], simulazioni=30,
                                   sintetiche=2, sorte=True)
    assert verifica._perfetta(_rosa(), {i: 3.0 for i in con_voto}, r) == 33.0
    f = e.formazioni
    assert max(f["modello"], f["fantamedia"]) > 33.0
    assert f["perfetta"] == pytest.approx(max(f["modello"], f["fantamedia"]))
    assert e.sorte and all(massimo == pytest.approx(max(reale, semplice)) and massimo > 33.0 for reale, semplice, massimo in e.sorte)


# ---------------------------------------------------------------- punti su rose a sorte
def test_punti_su_rose_a_sorte_con_intervallo_a_gruppi_di_giornata(finto):
    voti = [_voto(st, g, i, 5.0 + (i * g) % 4) for st in (S1, S2) for g in range(1, 7) for i in range(1, 26)]
    d = _dati(voti)
    giornate = [(S2, g) for g in range(2, 7)]
    t = verifica.verifica(d, Regole(), Parametri(), giornate, simulazioni=30, scrivi=None, sintetiche=4)
    assert (t["sorte_casi"] == 4).all() and {"sorte_modello", "sorte_fantamedia", "sorte_perfetta", "sorte_differenza"} <= set(t.columns)
    assert (t["sorte_perfetta"] >= t[["sorte_modello", "sorte_fantamedia"]].max(axis=1) - 1e-9).all()
    r = verifica.riepilogo_sorte(t)[S2]
    assert r["casi"] == 20 and r["giornate"] == 5
    assert r["differenza"] == pytest.approx(r["modello"] - r["fantamedia"])
    assert r["basso"] <= r["differenza"] <= r["alto"]
    # senza rose a sorte la verifica è quella di sempre e il riepilogo è vuoto
    senza = verifica.verifica(d, Regole(), Parametri(), giornate, simulazioni=30, scrivi=None)
    assert "sorte_casi" not in senza.columns and verifica.riepilogo_sorte(senza) == {}


def test_le_rose_a_sorte_si_riusano_nello_stesso_giro_con_le_stesse_regole(finto, monkeypatch):
    """La prova di ogni utente (#832): le rose a sorte non dipendono dalle rose della lega, quindi con le stesse regole si
    calcolano una volta sola nel giro (`memo`), con gli stessi numeri; con regole diverse si rifanno."""
    voti = [_voto(st, g, i, 5.0 + (i * g) % 4) for st in (S1, S2) for g in range(1, 7) for i in range(1, 26)]
    d = _dati(voti)
    giornate = [(S2, g) for g in range(2, 5)]
    conta = []
    vera = verifica._casi_sintetici
    monkeypatch.setattr(verifica, "_casi_sintetici", lambda *a, **k: conta.append(1) or vera(*a, **k))
    prova = lambda rose, regole=None, memo=None: verifica.verifica(                                       # noqa: E731
        d, regole or Regole(), Parametri(), giornate, rose=rose, simulazioni=30, scrivi=None, sintetiche=3, memo=memo)
    senza = prova([list(range(1, 26))])
    memo: dict = {}
    primo = prova([list(range(1, 26))], memo=memo)
    secondo = prova([list(range(1, 24))], memo=memo)                     # un altro utente, altre rose, stesse regole
    assert len(conta) == 6                                               # 3 giornate senza memo, 3 con: il secondo le riusa
    pd.testing.assert_frame_equal(senza, primo)
    sorte = [c for c in primo.columns if c.startswith("sorte_")]
    pd.testing.assert_frame_equal(primo[sorte], secondo[sorte])
    prova([list(range(1, 26))], imposta(Regole(), "bonus.gol.A", "4"), memo=memo)
    assert len(conta) == 9                                               # regole diverse: si rifanno


# ---------------------------------------------------------------- affidabilità («Quanto è affidabile il modello»)
def _partita_db(db, pid, st, g, data, casa="a", trasferta="b", giocata=1, con_voti=None):
    """Una partita nell'archivio e un voto per ciascuna squadra di `con_voti` (di norma tutte e due, se è giocata)."""
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (pid, st, g, data, casa, trasferta, giocata))
    for k, sq in enumerate((casa, trasferta) if con_voti is None and giocata else con_voti or ()):
        _voto_db(db, st, g, 10 * pid + k, sq)
    db.commit()


def _voto_db(db, st, g, calciatore, squadra, voto=6.0):
    db.execute("INSERT OR REPLACE INTO voti (stagione, giornata, calciatore_id, squadra, ruolo, voto_red) VALUES (?, ?, ?, ?, 'C', ?)",
               (st, g, calciatore, squadra, voto))
    db.commit()


def test_affidabilita_porta_gli_avversari_onesti_e_le_rose_a_sorte(finto, monkeypatch, tmp_path):
    from fanta import affidabilita, archivio, consigli
    voti = [_voto(st, g, i, 5.0 + (i * g) % 4) for st in (S1, S2) for g in range(1, 7) for i in range(1, 26)]
    d = _dati(voti)
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(1, 7):
        _partita_db(db, 100 + g, S2, g, "2026-09-01 18:00")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: S2)
    monkeypatch.setattr(consigli, "dati", lambda db: d)
    monkeypatch.setattr(verifica, "ROSE_A_SORTE", 3)
    r = affidabilita.calcola(db, Regole(), None, simulazioni=30)
    s = r["sintesi"]
    assert s["giornate"] == 6 and {"errore_modello", "errore_fantamedia", "errore_ruolo", "errore_fantamedia_stagione"} <= set(s)
    assert s["rose_a_sorte"]["casi"] == 18 and s["rose_a_sorte"]["basso"] <= s["rose_a_sorte"]["differenza"] <= s["rose_a_sorte"]["alto"]
    assert "sorte_modello" in r["righe"][0]
    import json
    json.dumps(r)                              # tutto si scrive nel file dell'affidabilità


def test_d_estate_la_prova_non_si_rifa_a_ogni_giro(monkeypatch, tmp_path):
    """D'estate la stagione in corso non ha giornate finite e la prova usa le ultime della precedente: si rifà solo quando ne
    finisce una nuova. Prima la chiave guardava solo la stagione in corso e la prova (con 20 rose a sorte in più per giornata)
    ripartiva a ogni giro del cron (revisione di #642)."""
    from fanta import affidabilita, archivio, consigli
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(30, 39):
        _partita_db(db, g, S2, g, "2027-05-01 18:00")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2027-28")
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    prove = []

    def finta(d, regole, par, giornate, **k):
        prove.append(list(giornate))
        return pd.DataFrame([{"stagione": s, "giornata": g, "quadratico_modello": 2.0, "quadratico_fantamedia": 2.1} for s, g in giornate])
    monkeypatch.setattr(verifica, "verifica", finta)
    f = tmp_path / "affidabilita.json"
    assert [affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) for _ in range(3)] == [True, False, False]
    assert len(prove) == 1 and prove[0][-1] == (S2, 38) and affidabilita.carica(f)["ultima"] == f"{S2}/38"
    # finisce la prima giornata della stagione nuova: si rifà, una volta
    _partita_db(db, 99, "2027-28", 1, "2027-08-22 18:00")
    assert [affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) for _ in range(2)] == [True, False]
    assert len(prove) == 2 and prove[1][-1] == ("2027-28", 1)


def test_la_giornata_e_conclusa_solo_con_i_voti_di_tutte_e_due_le_squadre(monkeypatch, tmp_path):
    """Una giornata entra nella prova solo con tutte le partite giocate e i voti di tutte e due le squadre di ognuna (la regola
    di `fasi.voti_arrivati`). Prima bastava «giocata» e una partita senza voti contava i suoi giocatori come «non hanno giocato»
    (#832)."""
    from fanta import affidabilita, archivio
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in (1, 2, 3):
        _partita_db(db, 10 * g, S2, g, f"2026-09-0{g} 15:00")
        _partita_db(db, 10 * g + 1, S2, g, f"2026-09-0{g} 18:00", "c", "d", con_voti=() if g == 3 else None)
    assert affidabilita.giornate_concluse(db, S2) == [1, 2]
    _voto_db(db, S2, 3, 900, "c")                                    # arrivano i voti di una squadra sola: non basta
    assert affidabilita.giornate_concluse(db, S2) == [1, 2]
    _voto_db(db, S2, 3, 901, "d")
    assert affidabilita.giornate_concluse(db, S2) == [1, 2, 3]
    # la colonna del voto è quella della lega: con il voto statistico la redazione non basta
    statistico = imposta(Regole(), "fonte_voto", "statistico")
    assert affidabilita.giornate_concluse(db, S2, statistico) == []


def test_la_prova_si_rifa_quando_cambiano_le_giornate_o_i_voti(monkeypatch, tmp_path):
    """La prova si rifaceva solo quando cambiava l'ultima giornata: un recupero giocato dopo, i voti di una partita arrivati tardi
    o un voto corretto restavano fuori fino alla giornata dopo (#832, sonda del revisore). Ora la chiave è l'impronta delle
    giornate della prova e dei loro voti; `ultima` resta quella di sempre."""
    from fanta import affidabilita, archivio, consigli
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(1, 7):
        _partita_db(db, 10 * g, S2, g, f"2026-09-{g:02d} 15:00")
    _partita_db(db, 31, S2, 3, "2026-09-03 18:00", "c", "d", giocata=0)          # giornata 3: una partita rinviata
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: S2)
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    prove = []

    def finta(d, regole, par, giornate, **k):
        prove.append([g for _, g in giornate])
        return pd.DataFrame([{"stagione": s, "giornata": g, "quadratico_modello": 2.0, "quadratico_fantamedia": 2.1} for s, g in giornate])
    monkeypatch.setattr(verifica, "verifica", finta)
    f = tmp_path / "affidabilita.json"
    rifai = lambda: affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f)      # noqa: E731
    assert [rifai(), rifai()] == [True, False] and prove == [[1, 2, 4, 5, 6]]
    # il recupero della 3 si gioca e arrivano i suoi voti: l'ultima giornata resta la 6, ma la prova si rifà
    db.execute("UPDATE partite SET giocata = 1 WHERE id = 31")
    _voto_db(db, S2, 3, 900, "c")
    _voto_db(db, S2, 3, 901, "d")
    assert [rifai(), rifai()] == [True, False] and prove[-1] == [1, 2, 3, 4, 5, 6]
    assert affidabilita.carica(f)["ultima"] == f"{S2}/6"
    # un voto corretto nei giorni dopo
    _voto_db(db, S2, 5, 50, "a", voto=7.5)
    assert [rifai(), rifai()] == [True, False] and len(prove) == 3
    # la giornata 7 è giocata, ma i voti di una squadra mancano: non entra, e la prova non si rifà
    _partita_db(db, 70, S2, 7, "2026-09-07 15:00", con_voti=("a",))
    assert rifai() is False and len(prove) == 3
    _voto_db(db, S2, 7, 701, "b")
    assert rifai() is True and prove[-1][-1] == 7 and affidabilita.carica(f)["ultima"] == f"{S2}/7"


def test_il_giorno_del_rilascio_la_prova_si_rifa_una_volta(monkeypatch, tmp_path):
    """Un file scritto prima di #832 non ha l'impronta: al primo giro la prova si rifà, poi resta."""
    import json
    from fanta import affidabilita, archivio, consigli
    db = archivio.apri(tmp_path / "a.sqlite")
    for g in range(1, 5):
        _partita_db(db, 10 * g, S2, g, f"2026-09-{g:02d} 15:00")
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: S2)
    monkeypatch.setattr(consigli, "dati", lambda db: None)
    monkeypatch.setattr(verifica, "verifica", lambda d, regole, par, giornate, **k: pd.DataFrame(
        [{"stagione": s, "giornata": g, "quadratico_modello": 2.0} for s, g in giornate]))
    f = tmp_path / "affidabilita.json"
    f.write_text(json.dumps({"ultima": f"{S2}/4", "righe": [{"giornata": 4}]}), encoding="utf-8")
    assert [affidabilita.aggiorna_se_serve(db, Regole(), None, percorso=f) for _ in range(2)] == [True, False]
    assert affidabilita.carica(f)["impronta"]


# ---------------------------------------------------------------- il comando su un archivio vuoto
def test_riepilogo_senza_giornate_verificate_lo_dice():
    righe = []
    verifica.stampa_riepilogo(pd.DataFrame(), scrivi=righe.append)
    assert len(righe) == 1 and righe[0].startswith("Nessuna giornata verificata")


def test_verifica_su_un_archivio_vuoto_esce_con_un_messaggio(monkeypatch, tmp_path):
    """`python -m fanta verifica` con l'archivio vuoto: prima una traccia (KeyError 'stagione'), ora un messaggio e l'uscita."""
    from fanta import __main__ as cli
    from fanta import archivio
    vuoto = archivio.apri(tmp_path / "vuoto.sqlite")
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vuoto)
    with pytest.raises(SystemExit) as uscita:
        cli.main(["verifica"])
    assert isinstance(uscita.value.code, str) and "nessuna giornata giocata" in uscita.value.code

