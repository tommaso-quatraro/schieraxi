"""Gol attesi «nostri», Fasi B e C del piano 2026-11-06-gol-attesi-nostri: rigori con memoria lunga divisi nella squadra (B1),
minuti attesi «se prende voto» (B2), livello recente del campionato nella forza delle squadre (C1) e medie del ruolo pesate (C2).
Dati inventati: due stagioni, due squadre."""
from dataclasses import replace

import pandas as pd
import pytest

from fanta import consigli, modello
from fanta.modello import Parametri
from fanta.regole import Regole

S1, S2 = "2025-26", "2026-27"
GIOCATE = [(S1, g) for g in range(1, 9)] + [(S2, g) for g in range(1, 11)]   # 8 giornate della stagione prima, 10 della nuova
PROSSIMA = (S2, 11)                                                           # la giornata da prevedere
# come i nostri prima delle correzioni: niente xG e xA, la quota dei rigori di prima, le medie del ruolo senza pesi e nessun
# livello (in produzione fino a #613); accesa, la quota di squadra qui è quella dei nostri, senza i rigori messi in conto a un
# rigorista sconosciuto
NOSTRI = Parametri(peso_xg=0.0, peso_xa=0.0, rigori_squadra=False, rigori_di_un_altro=0.0, medie_ruolo_pesate=False,
                   k_livello=None)

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


def _dati(eventi: dict | None = None, giocate=GIOCATE, prossima=PROSSIMA) -> modello.Dati:
    """Alfa e beta si affrontano a ogni giornata. `eventi`: {(id, stagione, giornata): presenza() o None (non gioca)}; vale
    anche per la giornata da prevedere (dati «dal futuro»). Prestazioni come quelle di `nostri.dati`: niente xG né xA."""
    eventi = eventi or {}
    stagioni = [S1, S2]
    partite, voti, prest = [], [], []
    for i, (st, g) in enumerate(list(giocate) + [prossima]):
        casa, trasf = ("alfa", "beta") if g % 2 else ("beta", "alfa")
        giocata = (st, g) != prossima
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
    base = _rigori(1, (2, 4, 6)) | _rigori(2, (8,)) | _riserva_a_meta()
    # nella giornata da prevedere: due rigori della Spalla, il Rigorista 10' con voto, la Riserva 90' senza voto
    futuro = {(2, *PROSSIMA): presenza(rig_segnati=1, rig_sbagliati=1), (1, *PROSSIMA): presenza(minuti=10),
              (6, *PROSSIMA): presenza(voto=None, minuti=90)}
    tutti = _par(rigori_squadra=True, minuti_con_voto=True)
    a, b = _p(_dati(base), tutti), _p(_dati(base | futuro), tutti)
    pd.testing.assert_frame_equal(a, b)


def test_il_rigorista_e_uno_solo_per_squadra():
    """Revisione di #613. Ogni quota è «se gioca lui», con i compagni pesati per le loro presenze: A (1) ha calciato 3 rigori ma
    da sei giornate non gioca, B (2) ne ha calciati 2 e gioca sempre, e tutti e due hanno la quota sopra la metà. Normalizzare le
    quote dentro la squadra toglie rigori attesi (misura nella pull request): si tiene la quota e si segna il primo della squadra."""
    eventi = _rigori(1, (1, 2, 3)) | _rigori(2, (6, 8)) | {(1, S2, g): None for g in range(5, 11)}
    d = _dati(eventi)
    p = _p(d, Parametri())
    assert p.at[1, "quota_rigori"] >= 0.5 and p.at[2, "quota_rigori"] >= 0.5
    assert p["primo_rigorista"].tolist().count(True) == 1 and bool(p.at[2, "primo_rigorista"])       # in beta nessuno ne ha calciati
    assert consigli.rigorista(p.loc[2]) and not consigli.rigorista(p.loc[1])


def _riga(i: int, squadra: str, quota: float, p_voto: float = 0.9, stato: str | None = None) -> tuple:
    """Una riga di `modello._pezzi` con i soli campi che servono a scegliere il primo rigorista."""
    return {"id": i, "squadra": squadra, "p_voto": p_voto}, {"quota_rigori": quota, "stato": stato}, ()


def _primi(righe: list) -> list[int]:
    modello._segna_primo_rigorista(righe)
    return [prima["id"] for prima, dopo, _ in righe if dopo["primo_rigorista"]]


def test_il_primo_rigorista_e_il_migliore_fra_chi_puo_giocare():
    righe = [_riga(1, "alfa", 0.8, stato="squalificato"), _riga(2, "alfa", 0.55), _riga(3, "alfa", 0.2), _riga(4, "beta", 0.0),
             _riga(5, "gamma", 0.6, stato="infortunato"), _riga(6, "gamma", 0.6, stato="titolare"), _riga(7, "gamma", 0.6)]
    assert _primi(righe) == [2, 6]              # a pari merito il primo dell'elenco; in beta nessuno ne ha calciati
    assert all(dopo["primo_rigorista"] is (prima["id"] in (2, 6)) for prima, dopo, _ in righe)       # scritto in ogni riga


def test_il_primo_rigorista_guarda_anche_quanto_gioca():
    """#638: vinceva la quota dei rigori «se gioca» più alta, anche di chi parte dalla panchina o non è convocato. Ora vince chi
    con più probabilità calcia il prossimo rigore: «gioca» per quota."""
    # 0,25 × 0,8 = 0,20 contro 0,9 × 0,55 = 0,495: il titolare, non la riserva con la quota più alta
    assert _primi([_riga(1, "alfa", 0.8, 0.25, "panchina"), _riga(2, "alfa", 0.55, 0.9, "titolare")]) == [2]
    # 0,02 × 0,9 = 0,018 contro 0,9 × 0,3 = 0,27: chi non gioca quasi mai non è il primo
    assert _primi([_riga(3, "beta", 0.9, 0.02, "non_citato"), _riga(4, "beta", 0.3, 0.9, "titolare")]) == [4]
    # 0,6 × 0,9 = 0,54 contro 0,95 × 0,5 = 0,475: la quota conta ancora, non vince per forza chi gioca di più
    assert _primi([_riga(5, "gamma", 0.9, 0.6), _riga(6, "gamma", 0.5, 0.95)]) == [5]
    # chi non può giocare (probabilità zero) non è il primo, anche da solo
    assert _primi([_riga(7, "delta", 0.9, 0.0)]) == []


def test_la_frase_rigorista_va_al_titolare_non_a_chi_ha_la_quota_piu_alta():
    """#638, dalle previsioni alla frase. A (1) ha calciato tutti i rigori della stagione prima e i primi 4 della nuova, poi da sei
    giornate non gioca (non è infortunato né squalificato); B (2) ha calciato l'ultimo e gioca sempre. Tutti e due hanno la quota
    «se gioca» sopra la metà, e quella di A è la più alta: la frase «rigorista» andava ad A, che non gioca."""
    eventi = (_rigori(1, range(1, 9), stagione=S1) | _rigori(1, (1, 2, 3, 4)) | {(1, S2, g): None for g in range(5, 11)}
              | _rigori(2, (8,)))
    p = _p(_dati(eventi), Parametri())
    assert p.at[1, "quota_rigori"] > p.at[2, "quota_rigori"] >= consigli.QUOTA_RIGORISTA
    assert p.at[1, "p_voto"] < 0.3 and p.at[2, "p_voto"] > 0.8
    assert p.index[p["primo_rigorista"].astype(bool)].tolist() == [2]
    assert consigli.rigorista(p.loc[2]) and not consigli.rigorista(p.loc[1])
    assert "rigorista" in consigli.motivi(p.loc[2]) and "rigorista" not in consigli.motivi(p.loc[1])


def test_se_il_compagno_che_gioca_calcia_meno_della_meta_la_frase_non_l_ha_nessuno():
    """La frase si toglie più spesso di quanto si sposta, ed è quello che dice la voce di novità. Chi di solito calcia i rigori
    parte dalla panchina (quota 0,70, gioca 30%) e il compagno che gioca ne calcia meno della metà (0,40, gioca 90%): il primo è
    il compagno (0,36 contro 0,21), ma «rigorista» non lo ha nessuno dei due."""
    righe = [_riga(1, "alfa", 0.70, 0.30, "panchina"), _riga(2, "alfa", 0.40, 0.90, "titolare")]
    assert _primi(righe) == [2]
    assert [consigli.rigorista(prima | dopo) for prima, dopo, _ in righe] == [False, False]


def test_chi_non_gioca_quasi_mai_non_e_il_primo_rigorista_nemmeno_da_solo():
    """Revisione della pull request di #638 («un giocatore che gioca quasi mai non è il primo»). Chi gioca meno del 20% non è il
    primo nemmeno se è l'unico della squadra ad aver calciato rigori: non aveva nessuno con cui confrontarsi, e teneva la frase."""
    assert _primi([_riga(1, "alfa", 0.9, 0.02, "non_citato")]) == []
    # se un compagno gioca, il primo è lui anche con «gioca» per quota più basso: 0,9 × 0,1 = 0,09 contro 0,15 × 0,9 = 0,135
    assert _primi([_riga(2, "beta", 0.9, 0.15, "panchina"), _riga(3, "beta", 0.1, 0.9, "titolare")]) == [3]


def test_il_confine_di_chi_non_gioca_quasi_mai_e_quello_di_improbabile():
    """Un confine solo: chi la scheda chiama «improbabile» (`consigli.titolarita`, meno del 20%) non è il primo; dal 20% in su sì."""
    for gioca in (0.0, 0.02, 0.1, 0.199, 0.2, 0.3, 0.9):
        improbabile = consigli.titolarita({"stato": None, "p_voto": gioca, "quota_titolare": 0.5}) == "improbabile"
        assert (_primi([_riga(1, "alfa", 0.9, gioca)]) == []) is improbabile, gioca


def test_il_non_convocato_non_ha_la_frase_rigorista_anche_se_e_l_unico_che_li_calcia():
    """Dalle previsioni alla frase. Il Rigorista (1) ha calciato tutti i rigori di alfa, ma le probabili di alfa non lo citano:
    «gioca» 2%. La scheda diceva insieme «non tra i convocati previsti» e «rigorista»."""
    probabili = pd.DataFrame([{"calciatore_id": cid, "squadra": sq, "stato": "titolare", "percentuale": 90.0, "nota": None,
                               "in_dubbio": 0, "diffidato": 0} for cid, sq in ((2, "alfa"), (3, "alfa"), (4, "beta"), (5, "beta"))])
    d = _dati(_rigori(1, (2, 4, 6, 8)))
    p = modello.previsioni(d, *PROSSIMA, Regole(), Parametri(), probabili=probabili, giocatori=d.calciatori).set_index("id")
    assert p.at[1, "stato"] == "non_citato" and p.at[1, "quota_rigori"] >= consigli.QUOTA_RIGORISTA
    assert consigli.titolarita(p.loc[1]) == "improbabile"
    assert not p["primo_rigorista"].any()                 # in alfa non ne ha mai calciati nessun altro: il primo non c'è
    assert not consigli.rigorista(p.loc[1])
    motivi = consigli.motivi(p.loc[1])
    assert "non tra i convocati previsti" in motivi and "rigorista" not in motivi


# ---------------------------------------------------------------- B2: minuti attesi «se prende voto»
def _riserva_a_meta() -> dict:
    """La Riserva nelle giornate 3-10 della nuova stagione: 4 presenze con voto a 90' (un gol nella 5ª) e 4 senza voto a 10',
    alternate."""
    return {(6, S2, g): presenza(minuti=90, gol=int(g == 5)) if g % 2 else presenza(voto=None, minuti=10)
            for g in range(3, 11)}


def test_minuti_attesi_solo_dalle_presenze_con_voto():
    d = _dati(_riserva_a_meta())
    acceso, spento = _p(d, _par(minuti_con_voto=True)), _p(d, NOSTRI)
    assert acceso.at[6, "minuti"] > spento.at[6, "minuti"]
    assert acceso.at[6, "minuti"] > 80
    assert acceso.at[6, "e_gol"] > spento.at[6, "e_gol"]


def test_solo_presenze_senza_voto_minuti_di_partenza():
    # la Riserva è entrata 3 volte per pochi minuti, sempre senza voto: è come chi non ha presenze
    d = _dati({(6, S2, g): presenza(voto=None, minuti=10) for g in (8, 9, 10)})
    p = _p(d, _par(rigori_squadra=True, minuti_con_voto=True))
    assert p.at[6, "minuti"] == pytest.approx(82 * 0.7 + 25 * 0.3)     # 64,9: la formula di chi non ha presenze
    assert not p.loc[6, ["e_gol", "e_assist", "e_rigori", "mu", "p_gol", "minuti"]].isna().any()


# ---------------------------------------------------------------- C1: forza delle squadre con il livello recente del campionato
LUNGA = [(S2, g) for g in range(1, 26)]          # 25 giornate della nuova stagione
DOPO_LUNGA = (S2, 26)


def _salto(prima: int, dopo: int) -> modello.Dati:
    """20 giornate in cui la Spalla (alfa) e la Punta (beta) segnano `prima` gol a testa, poi 5 con `dopo` (gli altri mai): le
    partite finiscono `prima`-`prima`, poi `dopo`-`dopo`."""
    eventi = {(cid, S2, g): presenza(gol=prima if g <= 20 else dopo) for g in range(1, 26) for cid in (2, 4)}
    return _dati(eventi, LUNGA, DOPO_LUNGA)


def test_livello_segue_i_gol_recenti():
    d = _salto(1, 2)                                  # 2 gol a partita, poi 4
    acceso = _par(decadimento_base=0.9)
    f_acceso, f_spento = modello.forza_squadre(d, *DOPO_LUNGA, acceso), modello.forza_squadre(d, *DOPO_LUNGA, NOSTRI)
    # gol a squadra a partita: base (memoria 0,98) = (4,71 × 2 + 14,72 × 1) / 19,43 = 1,242;
    # recente (memoria 0,9) = (3,686 × 2 + 4,668 × 1) / 8,354 = 1,441; livello = 1,441 / 1,242
    assert f_acceso.livello == pytest.approx(1.160, abs=0.002)
    assert sum(f_acceso.gol_attesi("alfa", "beta")) == pytest.approx(1.160 * sum(f_spento.gol_attesi("alfa", "beta")),
                                                                     rel=0.003)
    # spento: livello 1 e i numeri di oggi (base × attacco × difesa × campo)
    assert f_spento.livello == 1.0
    a, dif = f_spento.attacco, f_spento.difesa
    assert f_spento.gol_attesi("alfa", "beta")[0] == f_spento.base * a["alfa"] * dif["beta"] * f_spento.casa
    # il livello arriva ai gol del giocatore
    p_acceso = modello.previsioni(d, *DOPO_LUNGA, Regole(), acceso).set_index("id")
    p_spento = modello.previsioni(d, *DOPO_LUNGA, Regole(), NOSTRI).set_index("id")
    assert p_acceso.at[2, "e_gol"] == pytest.approx(1.160 * p_spento.at[2, "e_gol"], rel=0.01)


@pytest.mark.parametrize("prima, dopo, atteso", [(1, 10, 1.25), (3, 0, 0.8)])
def test_livello_limitato(prima, dopo, atteso):
    # 2 gol a partita e poi 20 (livello 1,56 senza limite); 6 a partita e poi nessuno (0,74)
    assert modello.forza_squadre(_salto(prima, dopo), *DOPO_LUNGA, _par(decadimento_base=0.9)).livello == atteso


def test_livello_senza_dati_dal_futuro():
    par = _par(decadimento_base=0.9)
    oggi = modello.forza_squadre(_salto(1, 2), *DOPO_LUNGA, par)
    futuro = _salto(1, 2)
    # la giornata da prevedere già «giocata» 9-9, e una partita dopo, 9-9 anche lei
    riga = futuro.partite["giornata"] == DOPO_LUNGA[1]
    futuro.partite.loc[riga, ["gol_casa", "gol_trasferta", "giocata"]] = [9, 9, 1]
    dopo = futuro.partite[riga].assign(id=999, giornata=27, data=_data(S2, 27), t=futuro.partite["t"].max() + 1)
    futuro.partite = pd.concat([futuro.partite, dopo], ignore_index=True)
    assert modello.forza_squadre(futuro, *DOPO_LUNGA, par) == oggi


# ---------------------------------------------------------------- C2: medie del ruolo pesate come i giocatori
def test_medie_del_ruolo_seguono_la_stagione():
    # attaccanti sempre in campo 90' (Rigorista, Spalla, Punta). Stagione prima: solo 2 gol del Rigorista (3ª e 6ª) in 24
    # presenze, 0,083 a 90'. Stagione nuova come al solito: Spalla 3ª, 6ª, 9ª e Punta 2ª, 4ª, ..., 10ª, 8 gol in 30, 0,267.
    eventi = {(cid, S1, g): presenza(gol=int(cid == 1 and g in (3, 6))) for cid in (1, 2, 4) for g in range(1, 9)}
    d = _dati(eventi)
    acceso, spento = (modello.previsioni(d, *PROSSIMA, Regole(), par, giocatori=d.calciatori).set_index("id")
                      for par in (_par(medie_ruolo_pesate=True), NOSTRI))
    # la Riserva non ha mai giocato: parte dalla media del ruolo. Senza pesi 10 gol / 54 presenze da 90' = 0,185;
    # con i pesi dei giocatori (0,92 a giornata, metà per la stagione prima) 5,416 / 19,624 = 0,276
    assert acceso.at[6, "e_gol"] / spento.at[6, "e_gol"] == pytest.approx(0.2760 / 0.1852, rel=0.005)
    # sale anche chi ha giocato, ma meno: accanto alle sue presenze la media del ruolo vale 16 presenze da 90' fittizie
    assert 1 < acceso.at[4, "e_gol"] / spento.at[4, "e_gol"] < acceso.at[6, "e_gol"] / spento.at[6, "e_gol"]
