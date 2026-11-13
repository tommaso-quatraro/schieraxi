"""Giornate: i numeri e le frasi di ogni giornata finita li calcola il server, la web e l'iPhone li mostrano.

#672: `fatti_e_attesi` = di quanto i punti fatti della formazione che conta (la tua, la copia alla scadenza o la consigliata)
sono stati sopra o sotto quelli attesi, e chi dei suoi titolari ha fatto meglio o peggio del previsto, con la frase già scritta.
#674: `consigliata_di_allora` = perché la consigliata mostrata prima della scadenza c'è, non c'è o non si può più valutare, con la
frase per la giornata (`nota_consigliata`) e quella sulle giornate fuori dal confronto (`nota` di «Le tue scelte» e dei Dettagli).
Dati finti: le fixture del Diario di test_diario.py (tutti prendono 6, l'attaccante 25 prende 9; fantavoto atteso 5,5 + id × 0,05).
"""
import pytest

from fanta import diario, precisione
from fanta.regole import Regole

from test_diario import (CON_IL_25, MOSTRATI, ST, _formazione_finta, _mostrata, _salva, _scelta, _scelte, _voce,  # noqa: F401
                         finto, vero)

ROSA = list(range(1, 26))


def _in_elenco(file, voce):
    """La voce come la legge l'app (`GET /api/diario`): scritta nel file del Diario e riletta con `diario.elenco`."""
    diario._scrivi(file, voci={f"{voce['stagione']}/{voce['giornata']}": voce})
    return next(v for v in diario.elenco(file)["giornate"] if v["giornata"] == voce["giornata"])


def _calcola(f, scelta=None, **k):
    return diario.calcola_giornata(f.dati, ST, 1, k.pop("regole", Regole()), None, ROSA, scelta, simulazioni=50, **k)


def _chi(elenco):
    return [(g["id"], g["differenza"]) for g in elenco]


# ---------------------------------------------------------------- #672: fatti meno attesi, e chi ha fatto meglio o peggio
def test_differenza_e_chi_ha_fatto_meglio_o_peggio_della_tua_formazione(finto):  # noqa: F811 (fixture importata)
    v = _in_elenco(finto.file, _calcola(finto, _scelta(CON_IL_25)))
    fa, s = v["fatti_e_attesi"], v["schierata"]
    assert fa["formazione"] == "schierata"
    assert (fa["fatti"], fa["atteso"]) == (s["reale"], s["atteso"]) and s["reale"] == 69.0
    assert fa["differenza"] == round(s["reale"] - s["atteso"], 1)
    # fantavoto atteso come lo scrive la pagina (una cifra): 25 → 6,8 (preso 9), 1 → 5,5, 4 → 5,7; 20 e 21 → 6,5 (presi 6)
    assert _chi(fa["meglio"]) == [(25, 2.2), (1, 0.5)]
    assert _chi(fa["peggio"]) == [(20, -0.5), (21, -0.5)]
    assert fa["meglio"][0] == {"id": 25, "nome": "G25", "ruolo": "A", "atteso": 6.75, "preso": 9.0, "differenza": 2.2}
    assert fa["testo"] == "Meglio del previsto: G25 (+2,2) e G1 (+0,5). Peggio: G20 (−0,5) e G21 (−0,5)."
    assert fa["frase"]["chiave"] == "diario.meglio_peggio"
    assert fa["frase"]["param"]["meglio"]["param"]["parti"][0] == {"chiave": "diario.scarto_giocatore", "param": {"nome": "G25", "d": "+2.2"}}


def test_chi_non_ha_preso_voto_non_e_fra_meglio_e_peggio(finto):  # noqa: F811 (fixture importata)
    voti = finto.dati.voti
    finto.dati.voti = voti[~((voti["giornata"] == 1) & (voti["calciatore_id"] == 25))].copy()       # il 25 non ha giocato
    fa = _in_elenco(finto.file, _calcola(finto, _scelta(CON_IL_25)))["fatti_e_attesi"]
    assert 25 not in [g["id"] for g in fa["meglio"] + fa["peggio"]]
    assert _chi(fa["meglio"]) == [(1, 0.5), (4, 0.3)]


def test_il_fantavoto_atteso_e_quello_mostrato_prima_della_scadenza(finto):  # noqa: F811 (fixture importata)
    """Con la consigliata di allora salvata con i suoi numeri (istantanea), l'atteso di un giocatore è quello che l'app mostrava,
    come nella tabella della pagina."""
    f = _formazione_finta(ids=CON_IL_25)
    for t in f["titolari"]:
        t |= {"p_voto": 0.9, "fv_atteso": 8.5 if t["id"] == 25 else 6.0}
    diario.salva_istantanea(f, ST, finto.file)
    ist = diario.carica(finto.file)["istantanee"][f"{ST}/1"]
    fa = _in_elenco(finto.file, _calcola(finto, _scelta(CON_IL_25), istantanea=ist))["fatti_e_attesi"]
    assert _chi(fa["meglio"]) == [(25, 0.5)] and fa["meglio"][0]["atteso"] == 8.5
    assert fa["peggio"] == [] and fa["testo"] == "Meglio del previsto: G25 (+0,5)." and fa["frase"]["chiave"] == "diario.meglio"


def _voce_a_mano(numeri, mostrati=None):
    """Una voce con la consigliata e i numeri per giocatore scelti dal test: {id: (fantavoto atteso, preso o None)}."""
    tit = [{"id": i, "nome": f"G{i}", "ruolo": "C"} for i in numeri]
    voce = {"stagione": ST, "giornata": 3, "schierata": None, "automatica": None,
            "consigliata": {"modulo": "4-4-2", "atteso": 70.0, "reale": 68.5, "titolari": tit, "origine": "ricostruita"},
            "giocatori": [{"id": i, "p_voto": 0.9, "fv_atteso": a, "fv": p} for i, (a, p) in numeri.items()]}
    if mostrati:
        voce["istantanea"] = {"titolari": [{"id": i, "nome": f"G{i}", "ruolo": "C", "fv_atteso": a} for i, a in mostrati.items()]}
    return voce


def test_le_differenze_sono_quelle_dei_numeri_come_li_scrive_la_pagina():
    """La pagina scrive i fantavoti con una cifra, il mezzo all'insù (6,25 → «6,3»): la differenza è quella dei due numeri scritti,
    non quella degli arrotondamenti di Python (che darebbe 6,2 e «−0,2»)."""
    fa = diario.fatti_e_attesi(_voce_a_mano({1: (6.25, 6.0), 2: (5.55, 6.0), 3: (6.0, 6.0)}))
    assert fa["formazione"] == "consigliata" and (fa["fatti"], fa["atteso"], fa["differenza"]) == (68.5, 70.0, -1.5)
    assert _chi(fa["peggio"]) == [(1, -0.3)] and _chi(fa["meglio"]) == [(2, 0.5)]          # 5,55 è 5,549…: «5,5»
    assert fa["testo"] == "Meglio del previsto: G2 (+0,5). Peggio: G1 (−0,3)."


def test_al_massimo_due_per_parte_dalla_differenza_piu_grande():
    fa = diario.fatti_e_attesi(_voce_a_mano({1: (6.0, 4.0), 2: (6.0, 5.5), 3: (6.0, 3.0), 4: (6.0, 7.0), 5: (6.0, 10.0), 6: (6.0, 8.0)}))
    assert _chi(fa["meglio"]) == [(5, 4.0), (6, 2.0)] and _chi(fa["peggio"]) == [(3, -3.0), (1, -2.0)]


def test_tutti_come_previsto_niente_frase():
    fa = diario.fatti_e_attesi(_voce_a_mano({1: (6.0, 6.0), 2: (6.0, None)}))
    assert (fa["meglio"], fa["peggio"], fa["testo"], fa["frase"]) == ([], [], None, None)
    assert diario.fatti_e_attesi(_voce_a_mano({1: (6.0, 4.0)}))["testo"] == "Peggio del previsto: G1 (−2,0)."


def test_senza_punti_niente_fatti_e_attesi():
    voce = _voce_a_mano({1: (6.0, 6.0)})
    voce["consigliata"]["atteso"] = None
    assert diario.fatti_e_attesi(voce) is None


def test_la_formazione_che_conta_anche_dopo_la_correzione_a_mano(vero):  # noqa: F811 (fixture importata)
    """Senza una scelta tua contano i punti della copia fatta alla scadenza; dopo «Non è quello che ho schierato» quelli della
    formazione corretta, con i suoi giocatori."""
    _scelte.salva_automatica(ST, 1, MOSTRATI, "3-4-3", vero.scelte)
    diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte)
    voci = {v["giornata"]: v for v in diario.elenco(vero.file)["giornate"]}
    assert voci[1]["fatti_e_attesi"]["formazione"] == "automatica" and voci[1]["fatti_e_attesi"]["fatti"] == 66.0
    assert voci[2]["fatti_e_attesi"]["formazione"] == "consigliata"
    assert voci[2]["fatti_e_attesi"]["fatti"] == voci[2]["consigliata"]["reale"]
    _salva(vero, 1, "manuale", CON_IL_25)
    fa = next(v for v in diario.elenco(vero.file)["giornate"] if v["giornata"] == 1)["fatti_e_attesi"]
    assert fa["formazione"] == "schierata" and fa["fatti"] == 69.0
    assert fa["meglio"][0]["id"] == 25                                                  # il 25 c'è solo nella formazione corretta


# ---------------------------------------------------------------- #674: la consigliata di allora salvata ma non valutabile
CEDUTO = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 99]          # il 99 era nella consigliata di allora e non è più in rosa
NON_SALVATA = "quella mostrata prima della scadenza non era stata salvata"
FUORI_ROSA = "in quella mostrata prima della scadenza c'è chi non è più nella tua rosa"


def test_consigliata_salvata_con_un_giocatore_ceduto(finto):  # noqa: F811 (fixture importata)
    """La consigliata di allora c'è, ma dentro c'è chi poi è stato ceduto: non entra nel confronto, e la frase lo dice com'è
    (prima diceva «non era stata salvata», e l'iPhone sulla stessa giornata scriveva «Ricostruita oggi»)."""
    v = _in_elenco(finto.file, _calcola(finto, _scelta(MOSTRATI), istantanea=_mostrata(finto, ids=CEDUTO)))
    assert v["consigliata"]["origine"] == "ricostruita" and v["consigliata_di_allora"] == "fuori_rosa"
    assert v["nota_consigliata"] == f"Qui il confronto con la consigliata non c'è: {FUORI_ROSA}."
    assert v["nota_consigliata_frase"] == {"chiave": "diario.senza_confronto", "param": {"perche": {"chiave": "diario.allora_fuori_rosa", "param": {}}}}
    nota = "1 giornata non entra nel confronto: nella consigliata di allora c'è chi non è più nella tua rosa."
    st, cf = diario.scelte_tue([v]), precisione.riassunto([v])["confronto"]
    assert st["nota"] == cf["nota"] == nota
    assert st["nota_frase"] == cf["nota_frase"] == {"chiave": "diario.confronto_fuori_rosa", "param": {"n": 1}}
    assert (st["senza_istantanea"], cf["senza_istantanea"]) == (1, 1)                  # i conti di sempre: fuori dal confronto


def test_senza_la_tua_formazione_la_consigliata_e_rifatta_e_lo_dice(finto):  # noqa: F811 (fixture importata)
    v = _in_elenco(finto.file, _calcola(finto, istantanea=_mostrata(finto, ids=CEDUTO)))
    assert v["nota_consigliata"] == f"Questa è rifatta con i dati di allora: {FUORI_ROSA}."
    assert v["nota_consigliata_frase"]["chiave"] == "diario.rifatta"
    senza = _in_elenco(finto.file, _calcola(finto) | {"giornata": 2})
    assert senza["consigliata_di_allora"] == "non_salvata"
    assert senza["nota_consigliata"] == f"Questa è rifatta con i dati di allora: {NON_SALVATA}."


def test_consigliata_non_salvata_e_mostrata(finto):  # noqa: F811 (fixture importata)
    senza = _in_elenco(finto.file, _calcola(finto, _scelta(MOSTRATI)))
    assert senza["consigliata_di_allora"] == "non_salvata"
    assert senza["nota_consigliata"] == f"Qui il confronto con la consigliata non c'è: {NON_SALVATA}."
    mostrata = _in_elenco(finto.file, _calcola(finto, _scelta(CON_IL_25), istantanea=_mostrata(finto)))
    assert mostrata["consigliata_di_allora"] == "mostrata"
    assert (mostrata["nota_consigliata"], mostrata["nota_consigliata_frase"]) == (None, None)


def test_con_la_copia_alla_scadenza_nessuna_nota(finto):  # noqa: F811 (fixture importata)
    v = _in_elenco(finto.file, _calcola(finto, automatica=_scelta(MOSTRATI)))
    assert v["automatica"] and v["consigliata_di_allora"] == "non_salvata"
    assert (v["nota_consigliata"], v["nota_consigliata_frase"]) == (None, None)


def test_consigliata_di_allora_con_un_modulo_che_la_lega_non_ammette_piu(finto):  # noqa: F811 (fixture importata)
    """Tutti ancora in rosa, ma il suo modulo (3-4-3) la lega non lo ammette più: la frase non dà la colpa alla rosa."""
    solo_442 = Regole(moduli=["4-4-2"])
    tua = [1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 25]
    v = _in_elenco(finto.file, _calcola(finto, _scelta(tua), istantanea=_mostrata(finto), regole=solo_442))
    assert v["consigliata"]["origine"] == "ricostruita" and v["consigliata_di_allora"] == "non_valutabile"
    assert v["nota_consigliata"] == ("Qui il confronto con la consigliata non c'è: quella mostrata prima della scadenza non si può più "
                                     "valutare con la rosa e le regole di oggi.")


def test_voce_calcolata_prima_senza_il_motivo(finto):  # noqa: F811 (fixture importata)
    """Una voce scritta prima di questo campo, con la consigliata di allora salvata ma rifatta: il server non sa più perché, e lo
    dice senza indovinare."""
    voce = _calcola(finto, _scelta(MOSTRATI), istantanea=_mostrata(finto, ids=CEDUTO))
    voce.pop("consigliata_di_allora")
    v = _in_elenco(finto.file, voce)
    assert v["consigliata_di_allora"] == "non_valutabile"
    assert "non si può più valutare con la rosa e le regole di oggi" in v["nota_consigliata"]


def _fuori(g, motivo, tue=(1, 2, 9)):
    """Una giornata con la tua formazione fuori dal confronto, per il motivo dato (scritto nella voce, come fa il server)."""
    v = _voce(g, list(tue), [1, 2, 3], 66.0, 69.0)
    v["consigliata"]["origine"] = "ricostruita"
    v["consigliata_di_allora"] = motivo
    return v


def _nota(voci):
    st, cf = diario.scelte_tue(voci), precisione.riassunto(voci)["confronto"]
    assert (st["nota"], st["nota_frase"]) == (cf["nota"], cf["nota_frase"])
    return st["nota"], (st["nota_frase"] or {}).get("chiave")


@pytest.mark.parametrize("motivi, testo, chiave", [
    (["fuori_rosa", "fuori_rosa"], "2 giornate non entrano nel confronto: nella consigliata di allora c'è chi non è più nella tua rosa.",
     "diario.confronto_fuori_rosa"),
    (["fuori_rosa", "non_valutabile"], "2 giornate non entrano nel confronto: la consigliata di allora non si può più valutare con la "
     "rosa e le regole di oggi.", "diario.confronto_non_valutabili"),
    (["non_salvata", "non_salvata"], "2 giornate non entrano nel confronto: la consigliata di allora non era stata salvata.",
     "diario.confronto_fuori"),
    (["non_salvata", "fuori_rosa"], "1 giornata non entra nel confronto: la consigliata di allora non era stata salvata. "
     "1 giornata non entra nel confronto: nella consigliata di allora c'è chi non è più nella tua rosa.", "elenco"),
])
def test_la_frase_sulle_giornate_fuori_dice_perche(motivi, testo, chiave):
    assert _nota([_fuori(g, m) for g, m in enumerate(motivi, 1)]) == (testo, chiave)


def test_con_gli_stessi_titolari_nelle_altre_la_frase_non_dice_che_era_salvata_solo_li():
    stessa = _voce(3, [1, 2, 3], [1, 2, 3], 70.0, 70.0)
    assert _nota([stessa, _fuori(1, "fuori_rosa")]) == (
        "Hai schierato gli stessi undici della consigliata in tutte le giornate che si possono confrontare. "
        "1 giornata non entra nel confronto: nella consigliata di allora c'è chi non è più nella tua rosa.",
        "diario.confronto_stessa_confrontabili")
    assert _nota([stessa, _fuori(1, "non_salvata")])[1] == "diario.confronto_stessa_fuori"          # come prima
