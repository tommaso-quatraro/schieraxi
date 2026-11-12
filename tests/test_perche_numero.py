"""«Perché questo numero» (fanta/perche.py), Diario «atteso contro fatto» e nome unico «Fantavoto atteso»."""
import json
import re

import pandas as pd
import pytest
from test_modello import ST, _dati, _p

from fanta import consigli, diario, modello, perche, server
from fanta.regole import Regole
import codice_web

WEB = server.WEB
RADICE = WEB.parent.parent


# ---------------------------------------------------------------- i pezzi sono quelli veri del modello
def test_il_modello_espone_i_pezzi_senza_cambiare_i_numeri():
    p = _p(_dati())
    par = modello.Parametri()
    # il voto prima della partita + l'effetto della partita = il voto atteso che il modello usava già
    assert (p["voto_base"] + par.beta_voto * (p["gol_squadra"] - p["gol_avversario"]) - p["mu_voto"]).abs().max() < 0.01
    assert (p["fattore"] > 0).all()


def test_i_pezzi_sommano_esattamente_al_fantavoto_atteso():
    p = _p(_dati())
    parti = perche.pezzi(p, Regole())
    assert (parti.sum(axis=1) - p["mu"]).abs().max() < 1e-9
    assert set(parti.columns) == set(perche.PEZZI)
    # il rigorista ha i rigori, gli altri no; il portiere ha la porta
    assert parti.at[1, "rigori"] > 0 and parti.at[3, "rigori"] == 0
    assert parti.at[2, "porta"] != 0 and parti.at[1, "porta"] == 0
    # «altro» (cartellini, autogol, migliore in campo) è piccolo: se fosse grande i pezzi non spiegherebbero il numero
    assert parti["altro"].abs().max() < 0.5


def test_voto_e_pezzi_corrispondono_ai_componenti_del_confronto():
    """Gli stessi pezzi che il confronto tra due giocatori usa già (consigli._componenti): gol, assist, porta."""
    p = _p(_dati())
    parti = perche.pezzi(p, Regole())
    for i in p.index:
        x = p.loc[i]
        c = consigli._componenti(x, Regole())
        f = float(x["fattore"])
        assert parti.at[i, "gol"] * f == pytest.approx(c["gol"], abs=1e-9)
        assert parti.at[i, "assist"] * f == pytest.approx(c["assist"], abs=1e-9)
        assert parti.at[i, "porta"] == pytest.approx(c["porta"], abs=1e-9)


# ---------------------------------------------------------------- i motivi
def _riga(i, **k):
    base = {"id": i, "nome": f"G{i}", "ruolo": "A", "mu": 7.0, "mu_voto": 6.5, "voto_base": 6.5, "fattore": 1.0, "e_gol": 0.30,
            "e_assist": 0.10, "e_rigori": 0.0, "gol_subiti": 0.0, "p_imbattuto": 0.0, "p_voto": 0.9, "stato": "titolare",
            "in_casa": True, "p_gol": 0.26}
    return base | k


def _giornata(**speciale):
    """Cinque attaccanti identici e uno speciale (id 99): il riferimento è la media di chi gioca."""
    righe = [_riga(i) for i in range(1, 6)] + [_riga(99, **speciale)]
    p = pd.DataFrame(righe).set_index("id")
    return p, *perche.calcola(p, Regole())


def test_un_giocatore_come_gli_altri_non_ha_motivi():
    p = pd.DataFrame([_riga(i) for i in range(1, 6)]).set_index("id")
    motivi, medio = perche.calcola(p, Regole())
    assert all(m == [] for m in motivi) and (medio == 7.0).all()


def test_i_motivi_sono_al_massimo_tre_dal_piu_pesante_con_il_segno():
    # più gol attesi, partita favorevole (voto e gol più alti), assist in più
    p, motivi, medio = _giornata(e_gol=0.80, e_assist=0.40, fattore=1.1, voto_base=6.6, mu_voto=6.9, mu=9.0)
    m = motivi.loc[99]
    assert 1 <= len(m) <= perche.MAX_MOTIVI
    effetti = [abs(x["effetto"]) for x in m if x["effetto"] is not None]
    assert effetti == sorted(effetti, reverse=True)
    assert m[0]["chiave"] == "gol" and m[0]["effetto"] > 0.5
    assert "(" in m[0]["testo"] and "% di segnare" in m[0]["testo"]
    assert all(set(x) == {"chiave", "testo", "frase", "effetto"} for x in m)
    assert medio.loc[99] == medio.loc[1]                              # il riferimento è uno solo per ruolo


def test_partita_difficile_in_trasferta_ha_il_segno_meno():
    p, motivi, _ = _giornata(fattore=0.7, in_casa=False, mu_voto=6.1, mu=6.2)
    primo = motivi.loc[99][0]
    assert primo["chiave"] in ("partita", "voti") and primo["effetto"] < 0
    partita = next(x for x in motivi.loc[99] if x["chiave"] == "partita")
    assert partita["testo"] == "partita difficile in trasferta" and partita["effetto"] < 0


def test_dubbio_sul_giocare_e_un_motivo_senza_effetto():
    _, motivi, _ = _giornata(p_voto=0.7)
    gioca = motivi.loc[99][0]
    assert gioca == {"chiave": "gioca", "testo": "gioca il 70%: dubbio", "frase": {"chiave": "perche.gioca_dubbio", "param": {"p": 70}}, "effetto": None}
    _, motivi, _ = _giornata(p_voto=0.0, stato="infortunato")
    assert motivi.loc[99][0]["testo"] == "infortunato: non gioca"
    _, motivi, _ = _giornata(p_voto=0.35)
    assert motivi.loc[99][0]["testo"] == "gioca il 35%: probabile panchina"
    _, motivi, _ = _giornata(p_voto=0.1)
    assert motivi.loc[99][0]["testo"] == "gioca solo il 10%: improbabile"
    _, motivi, _ = _giornata(p_voto=0.95)
    assert all(x["chiave"] != "gioca" for x in motivi.loc[99])            # chi gioca di sicuro non ha bisogno di dirlo


def test_chi_non_gioca_non_ha_motivi_sulla_partita():
    """Collaudo 2/11/2026: un infortunato con «partita favorevole» e «segna più della media»: consigli a vuoto."""
    for stato in ("infortunato", "squalificato"):
        _, motivi, _ = _giornata(p_voto=0.0, stato=stato, e_gol=0.9, fattore=1.4, voto_base=6.9, mu_voto=7.3, mu=9.0)
        assert [(m["chiave"], m["testo"], m["effetto"]) for m in motivi.loc[99]] == [("gioca", f"{stato}: non gioca", None)]


def test_il_dubbio_lascia_posto_a_due_motivi_numerici_al_massimo():
    _, motivi, _ = _giornata(p_voto=0.6, e_gol=0.9, e_assist=0.6, fattore=1.4, voto_base=6.9, mu_voto=7.3, mu=9.0)
    assert len(motivi.loc[99]) == perche.MAX_MOTIVI and motivi.loc[99][0]["chiave"] == "gioca"


def test_portiere_porta_inviolata():
    righe = [_riga(i, ruolo="P", e_gol=0.0, e_assist=0.0, gol_subiti=1.2, p_imbattuto=0.30, mu=5.4) for i in range(1, 6)]
    righe.append(_riga(99, ruolo="P", e_gol=0.0, e_assist=0.0, gol_subiti=0.5, p_imbattuto=0.61, mu=6.3))
    p = pd.DataFrame(righe).set_index("id")
    motivi, _ = perche.calcola(p, Regole())
    porta = next(x for x in motivi.loc[99] if x["chiave"] == "porta")
    assert porta["testo"] == "buone chance di non subire gol (61%)" and porta["effetto"] > 0


def test_la_scheda_del_giocatore_porta_i_motivi_e_il_riferimento():
    p, motivi, medio = _giornata(p_voto=0.7)
    p = p.assign(perche_numero=motivi, fv_atteso_medio_ruolo=medio)
    base = {k: 0 for k in ("e_gol", "e_assist", "e_rigori", "p_imbattuto", "p_gol", "p_assist", "p_giallo", "p_rosso", "quota_titolare",
                           "indice", "difficolta", "gol_squadra", "gol_avversario")}
    riga = {"nome": "X", "ruolo": "A", "squadra": "a", "avversario": "b", "in_casa": True, "p_voto": 0.7, "mu": 7.0, "mu_voto": 6.5,
            "atteso": 4.9, "dubbio": False, "diffidato": False, "data_partita": None, "stato": None, "percentuale": None, "nota": None,
            "perche_numero": [{"chiave": "gioca", "testo": "gioca il 70%: dubbio", "effetto": None}], "fv_atteso_medio_ruolo": 6.9} | base
    s = consigli.scheda_previsione(7, pd.Series(riga))
    assert s["perche_numero"][0]["chiave"] == "gioca" and s["fv_atteso_medio_ruolo"] == 6.9
    # un archivio senza i nuovi campi (o un test con righe finte) non rompe niente
    senza = {k: v for k, v in riga.items() if k not in ("perche_numero", "fv_atteso_medio_ruolo")}
    s = consigli.scheda_previsione(7, pd.Series(senza))
    assert s["perche_numero"] == [] and s["fv_atteso_medio_ruolo"] is None
    assert p["perche_numero"].map(len).max() <= perche.MAX_MOTIVI


def test_previsioni_vere_hanno_i_motivi_per_ogni_giocatore():
    d = _dati()
    prev = modello.previsioni(d, ST, 5, Regole()).set_index("id")
    motivi, medio = perche.calcola(prev, Regole())
    assert len(motivi) == len(prev) == len(medio)
    assert all(len(m) <= perche.MAX_MOTIVI for m in motivi)


# ---------------------------------------------------------------- Diario: atteso contro fatto
def _voce(g, atteso, reale, basso, alto):
    return {"stagione": ST, "giornata": g, "consigliata": {"atteso": atteso, "reale": reale, "intervallo": {"basso": basso, "alto": alto},
                                                           "origine": "mostrata"}}


def test_atteso_contro_fatto_di_una_giornata():
    r = diario.atteso_vs_fatto(_voce(1, 70.0, 66.0, 62.0, 78.0))
    assert r == {"riferimento": "consigliata", "atteso": 70.0, "fatti": 66.0, "scarto": -4.0, "nella_fascia": True,
                 "intervallo": {"basso": 62.0, "alto": 78.0}}
    assert diario.atteso_vs_fatto(_voce(1, 70.0, 58.0, 62.0, 78.0))["nella_fascia"] is False
    assert diario.atteso_vs_fatto({"consigliata": {}}) is None


def test_affidabilita_si_ricalcola_dalle_voci():
    voci = [_voce(g, 70.0, 70.0 + s, 62.0, 78.0) for g, s in enumerate([2, -3, 5, 12, -1, 0, 4, -6, 1, -2], start=1)]   # una fuori (+12)
    a = diario.affidabilita(voci)
    assert a["giornate"] == 10 and a["dentro_fascia"] == 9 and a["percentuale_dentro"] == 90 and a["fascia_dichiarata"] == 80
    assert a["scarto_medio"] == round(sum(abs(s) for s in [2, -3, 5, 12, -1, 0, 4, -6, 1, -2]) / 10, 1)
    assert a["errore_medio"] == round(sum([2, -3, 5, 12, -1, 0, 4, -6, 1, -2]) / 10, 1)
    assert a["punti_medi_attesi"] == 70.0 and a["giudizio"] == "in_linea" and a["pochi_dati"] is False


def test_affidabilita_dice_anche_quando_va_male():
    voci = [_voce(g, 70.0, 55.0, 62.0, 78.0) for g in range(1, 11)]            # sempre sotto la fascia
    a = diario.affidabilita(voci)
    assert a["dentro_fascia"] == 0 and a["percentuale_dentro"] == 0 and a["errore_medio"] == -15.0 and a["scarto_medio"] == 15.0
    assert a["giudizio"] == "sotto_le_attese"
    sopra = diario.affidabilita([_voce(g, 70.0, 90.0, 62.0, 78.0) for g in range(1, 11)])
    assert sopra["giudizio"] == "sopra_le_attese"


def test_affidabilita_con_pochi_dati_non_giudica():
    a = diario.affidabilita([_voce(1, 70.0, 40.0, 62.0, 78.0), _voce(2, 70.0, 41.0, 62.0, 78.0)])
    assert a["giornate"] == 2 and a["pochi_dati"] is True and a["giudizio"] == "pochi_dati" and a["giornate_minime"] == diario.POCHI_DATI
    assert diario.affidabilita([])["giornate"] == 0


def test_l_elenco_del_diario_porta_atteso_contro_fatto_e_affidabilita(tmp_path):
    f = tmp_path / "diario.json"
    f.write_text(json.dumps({"giornate": {f"{ST}/1": {
        "stagione": ST, "giornata": 1, "consigliata": {"modulo": "3-4-3", "atteso": 70.0, "reale": 66.0, "dev_simulata": 4.0, "titolari": []}}}}))
    r = diario.elenco(f)
    voce = r["giornate"][0]
    assert voce["atteso_vs_fatto"]["scarto"] == -4.0 and voce["atteso_vs_fatto"]["intervallo"]["basso"] < 70.0 < voce["atteso_vs_fatto"]["intervallo"]["alto"]
    # una voce scritta prima di #614 ha la consigliata ricostruita: i numeri ci sono, ma non entrano nel giudizio
    assert voce["atteso_vs_fatto"]["riferimento"] == "ricostruita" and voce["consigliata"]["origine"] == "ricostruita"
    assert r["affidabilita"]["giornate"] == 0 and r["affidabilita"]["senza_istantanea"] == 1 and r["affidabilita"]["giudizio"] == "pochi_dati"


# ---------------------------------------------------------------- un solo nome: «Fantavoto atteso»
FILE_UTENTE = [RADICE / "docs" / "GUIDA-UTENTE.md", RADICE / "docs" / "SOTTO-IL-COFANO.md",
               RADICE / "fanta" / "contenuti" / "sotto-il-cofano.json", RADICE / "docs" / "ARCHITETTURA-INFORMAZIONI.md"]


def test_il_numero_firma_ha_un_solo_nome_nei_testi_per_l_utente():
    """«Voto atteso» e «FV atteso» per il giocatore non compaiono più: il numero si chiama «Fantavoto atteso» (in inglese «Expected fantasy
    score»). Il voto in pagella senza bonus si chiama «voto in pagella atteso»."""
    for nome, testo in [("testi.js", codice_web.leggi("testi.js")), *((f.name, f.read_text(encoding="utf-8")) for f in FILE_UTENTE)]:
        if nome == "ARCHITETTURA-INFORMAZIONI.md":                   # la tabella del glossario cita il vecchio nome come «Oggi»
            testo = re.sub(r"^\| «voto atteso».*$", "", testo, flags=re.M)
        assert not re.search(r"(?<!fanta)voto atteso", testo, flags=re.I), nome
        assert not re.search(r"\bFV atteso\b|fantamedia attesa", testo, flags=re.I), nome
        assert not re.search(r"expected score", testo, flags=re.I), nome


def test_il_confronto_non_chiama_voto_atteso_il_voto_in_pagella():
    assert consigli.ETICHETTE_FATTORI["voto"] == "Voto in pagella atteso"


def test_la_definizione_unica_e_nella_guida():
    guida = (RADICE / "docs" / "GUIDA-UTENTE.md").read_text(encoding="utf-8")
    assert "**Fantavoto atteso**" in guida and "se gioca" in guida and "**gioca 65%**" in guida and "sotto l'80%" in guida
    assert "Perché questo numero" in guida and "Quanto ci abbiamo preso" in guida


# ---------------------------------------------------------------- web app
APP = codice_web.app()
