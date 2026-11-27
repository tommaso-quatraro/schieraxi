"""Giornate: chi non ha una previsione ricostruita per la giornata (mai sceso in campo prima: alla prima giornata le neopromosse e
chi arriva dall'estero, spesso il portiere di riserva, #447) entra nei punti con il suo voto vero, e da adesso anche nella tabella
degli 11 (`giocatori`), con il voto vero e il fantavoto atteso vuoto. Prima il suo «preso» era «–», la somma della tabella non
tornava con i punti e niente lo spiegava. Nella misura di «Quanto ci abbiamo preso» resta fuori: senza un atteso rifatto non c'è
niente da confrontare. Dati finti: le fixture del Diario di test_diario.py (tutti prendono 6, l'attaccante 25 prende 9)."""
import pytest

from fanta import diario, precisione
from fanta.regole import Regole

from test_diario import RISERVA, ST, _salva, _senza_previsione, finto, vero  # noqa: F401  (fixture del Diario con dati finti)


def _voto_della_riserva(v, voto: float) -> None:
    """Il voto del portiere 2 nella giornata 2: la sua prima partita."""
    voti = v.dati.voti
    voti.loc[(voti["giornata"] == 2) & (voti["calciatore_id"] == 2), "voto_red"] = voto


def _giornata_2(file) -> dict:
    return next(v for v in diario.elenco(file)["giornate"] if v["giornata"] == 2)


@pytest.fixture
def riserva(vero, monkeypatch):  # noqa: F811 (fixture importata)
    """Il portiere 2 non ha una previsione ricostruita per la giornata 2 e prende 7; schierato a mano con RISERVA."""
    _senza_previsione(monkeypatch, 2)
    _voto_della_riserva(vero, 7.0)
    _salva(vero, 2, "manuale", RISERVA)
    return vero


def test_chi_non_ha_previsione_sta_nella_tabella_con_il_suo_voto(riserva):
    """Il portiere senza previsione prende 7 e i punti sono 70: la tabella lo mostra con 7 e senza atteso, e la somma dei voti
    degli 11 fa 70 (prima 63, con il suo «preso» a «–» e nessuna frase che spiegasse i 7 punti in più)."""
    v = _giornata_2(riserva.file)
    numeri = {g["id"]: g for g in v["giocatori"]}
    assert numeri[2] == {"id": 2, "p_voto": None, "fv_atteso": None, "fv": 7.0}
    s = v["schierata"]
    assert s["reale"] == 70.0 and sum(numeri[t["id"]]["fv"] for t in s["titolari"]) == 70.0
    assert v["spiegazione_punti"] is None                       # i conti tornano con i voti della tabella: niente da spiegare
    fa = v["fatti_e_attesi"]
    assert 2 not in [r["id"] for r in fa["meglio"] + fa["peggio"]]          # senza un atteso non si dice meglio o peggio
    assert len(v["giocatori"]) == 25                                        # tutta la rosa, lui compreso


def test_con_l_atteso_mostrato_prima_della_scadenza_entra_nella_frase_come_nella_tabella(riserva):
    """Se la consigliata di allora mostrava un atteso anche per lui, la tabella scrive quello (web e iPhone prendono prima
    l'istantanea) e la frase su chi ha fatto meglio o peggio lo usa allo stesso modo: 5,5 atteso, 7 preso, +1,5. Solo senza
    nessun atteso resta fuori dalla frase. «Quanto ci abbiamo preso» invece lo lascia fuori comunque."""
    v = _giornata_2(riserva.file)
    v["istantanea"] = {"titolari": [{"id": 2, "nome": "G2", "ruolo": "P", "p_voto": 0.9, "fv_atteso": 5.5}]}
    fa = diario.fatti_e_attesi(v)
    assert (2, 5.5, 7.0, 1.5) in [(r["id"], r["atteso"], r["preso"], r["differenza"]) for r in fa["meglio"]]
    assert precisione.numeri_giornata(v)[0] == []                  # l'istantanea qui ha solo lui: nessun numero mostrato misurato


def test_chi_non_ha_previsione_e_non_gioca_e_senza_voto(vero, monkeypatch):  # noqa: F811 (fixture importata)
    _senza_previsione(monkeypatch, 2)
    voti = vero.dati.voti
    vero.dati.voti = voti[~((voti["giornata"] == 2) & (voti["calciatore_id"] == 2))].copy()
    _salva(vero, 2, "manuale", RISERVA)
    assert {g["id"]: g for g in _giornata_2(vero.file)["giocatori"]}[2] == {"id": 2, "p_voto": None, "fv_atteso": None, "fv": None}


def test_la_precisione_lascia_fuori_chi_non_ha_previsione(riserva):
    """«Quanto ci abbiamo preso» confronta l'atteso con il fantavoto preso: chi non ha un atteso rifatto non entra nei numeri
    ricostruiti e, per scelta esplicita, nemmeno in quelli mostrati prima della scadenza (come prima di averlo in tabella)."""
    v = _giornata_2(riserva.file)
    v["istantanea"] = {"titolari": [{"id": i, "p_voto": 0.9, "fv_atteso": 6.0} for i in RISERVA]}     # anche il 2 con i suoi numeri
    mostrati, ricostruiti = precisione.numeri_giornata(v)
    assert (len(mostrati), len(ricostruiti)) == (10, 24)


def test_voto_corretto_di_chi_non_ha_previsione_rifa_tabella_e_punti(riserva):
    """La correzione dei giorni dopo: il portiere senza previsione passa da 7 a 8. Prima la voce teneva 70 punti (i voti dei
    giocatori della tabella non erano cambiati); ora la tabella e i punti dicono 8 e 71."""
    diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte)
    _voto_della_riserva(riserva, 8.0)
    assert diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte) == 1
    v = _giornata_2(riserva.file)
    assert v["schierata"]["reale"] == 71.0 and {g["id"]: g for g in v["giocatori"]}[2]["fv"] == 8.0


def test_una_voce_di_prima_lo_prende_quando_se_ne_rifanno_i_punti(riserva):
    """Una voce scritta prima di questa versione non ha il portiere senza previsione nella tabella. Quando cambiano i voti della
    giornata (qui il 25, da 9 a 10) se ne rifanno i punti e la tabella lo prende, con il suo 7."""
    diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte)
    d = diario.carica(riserva.file)
    voce = d["giornate"][f"{ST}/2"]
    voce["giocatori"] = [g for g in voce["giocatori"] if g["id"] != 2]           # come le voci di prima
    diario._scrivi(riserva.file, voci={f"{ST}/2": voce})
    voti = riserva.dati.voti
    voti.loc[(voti["giornata"] == 2) & (voti["calciatore_id"] == 25), "voto_red"] = 10.0
    assert diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte) == 1
    v = _giornata_2(riserva.file)
    numeri = {g["id"]: g for g in v["giocatori"]}
    assert numeri[2]["fv"] == 7.0 and numeri[25]["fv"] == 10.0 and v["schierata"]["reale"] == 71.0


def test_voti_cambiati_di_altri_giocatori_non_rifanno_la_voce(riserva, monkeypatch):
    """Cambia il voto di uno che non è nella rosa: i voti della tabella, lui compreso, sono gli stessi e la voce prende solo
    l'impronta nuova, senza rifare i punti."""
    import pandas as pd
    diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte)
    riserva.dati.voti = pd.concat([riserva.dati.voti, pd.DataFrame([{"stagione": ST, "giornata": 2, "calciatore_id": 99, "voto_red": 5.0,
                                                                     "data": "2026-09-02 18:00"}])], ignore_index=True)
    monkeypatch.setattr(diario, "rifai_i_punti", lambda *a, **k: pytest.fail("i voti della tabella non sono cambiati"))
    assert diario.aggiorna(riserva.db, Regole(), riserva.rose, riserva.file, simulazioni=50, file_scelte=riserva.scelte) == 1
    assert _giornata_2(riserva.file)["schierata"]["reale"] == 70.0
