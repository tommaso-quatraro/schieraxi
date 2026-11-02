"""Il buon senso sui consigli di mercato (fanta/buon_senso.py): i casi stupidi non passano, quelli sensati restano. Nomi inventati."""
from datetime import datetime, timedelta

from fanta import buon_senso as bs

OGGI = datetime(2026, 11, 1, 12, 0)


def g(nome="G", ruolo="A", **k):
    base = {"nome": nome, "ruolo": ruolo, "squadra": "como", "p_voto": 0.9, "quota_titolare": 0.9, "p_lungo": 0.9, "stato": "titolare",
            "nota": None, "percentuale": 90.0, "mu": 6.0, "dubbio": False}
    return base | k


def svincolo(x, y, per_giornata, ruolo="A", costo=None, rimborso=0.5, fattibile=True, recenti=None):
    return bs.giudica_svincolo(x, y, per_giornata, ruolo, costo, 500, rimborso, fattibile, recenti, 1, 2)


def test_titolare_utile_non_si_svincola_per_poco():
    """Il caso «svincola il titolare per un titolare di un'altra squadra» da pochi decimi: bocciato."""
    ok, motivo = svincolo(g("Alfa", mu=6.4), g("Beta", mu=6.2), [0.4, 0.4, 0.3, 0.3, 0.4], costo=30)
    assert not ok and "titolare" in motivo


def test_guadagno_piccolo_si_boccia():
    ok, motivo = svincolo(g("Alfa", quota_titolare=0.2, p_lungo=0.2, mu=5.0), g("Beta"), [0.3, 0.2, 0.3, 0.2, 0.3])
    assert not ok and "piccola" in motivo


def test_chi_entra_deve_giocare():
    for y in (g("Beta", p_voto=0.4), g("Beta", quota_titolare=0.3), g("Beta", stato="infortunato"), g("Beta", dubbio=True),
              g("Beta", p_lungo=0.3, stato="possibile", percentuale=50.0)):
        ok, motivo = svincolo(g("Alfa", quota_titolare=0.1, p_lungo=0.1, mu=4.0), y, [1.5] * 5)
        assert not ok and "Beta" in motivo, y


def test_infortunato_lungo_da_sostituire_resta():
    x = g("Alfa", stato="infortunato", nota="rottura del crociato, stop di mesi", p_voto=0.0, mu=6.5)
    ok, motivo = svincolo(x, g("Beta", mu=5.8), [5.8] * 5, costo=40)
    assert ok and "Alfa resta fuori a lungo" in motivo and "titolare fisso" in motivo


def test_infortunato_breve_non_si_sostituisce():
    x = g("Alfa", stato="infortunato", nota="distorsione, rientra tra due settimane", p_voto=0.0, mu=6.5)
    ok, _ = svincolo(x, g("Beta", mu=5.8), [5.0] * 5)
    assert not ok


def test_squalificato_titolare_con_sostituto_valido():
    x = g("Alfa", ruolo="D", stato="squalificato", p_voto=0.0, quota_titolare=0.5, mu=5.0)
    ok, motivo = svincolo(x, g("Beta", ruolo="D", mu=5.6), [3.0, 0.5, 0.5, 0.5, 0.5], ruolo="D")
    assert ok and "squalificato" in motivo


def test_portiere_scoperto():
    x = g("Alfa", ruolo="P", stato="infortunato", nota="fuori fino a fine stagione", p_voto=0.0, quota_titolare=0.0, p_lungo=0.0, mu=0.0)
    ok, motivo = svincolo(x, g("Beta", ruolo="P", mu=5.5), [5.5] * 5, ruolo="P")
    assert ok and "Beta" in motivo


def test_costo_alto_protegge_ma_non_la_riserva():
    ok, motivo = svincolo(g("Alfa", quota_titolare=0.5, p_lungo=0.5, mu=5.0), g("Beta"), [1.0] * 5, costo=60)
    assert not ok and "60 crediti" in motivo
    ok, _ = svincolo(g("Alfa", quota_titolare=0.2, p_lungo=0.2, mu=4.0), g("Beta"), [1.0] * 5, costo=60)
    assert ok


def test_crediti_insufficienti():
    ok, motivo = svincolo(g("Alfa", quota_titolare=0.1, p_lungo=0.1, mu=4.0), g("Beta"), [1.0] * 5, fattibile=False)
    assert not ok and "crediti" in motivo


def test_niente_ripensamenti():
    movimenti = [{"quando": (OGGI - timedelta(days=5)).isoformat(),
                  "svincolati_presi": [{"squadra": "Mia", "giocatori": [{"id": 1}]}],
                  "tagliati": [{"squadra": "Mia", "giocatori": [{"id": 2}]}], "scambi": []},
                 {"quando": (OGGI - timedelta(days=90)).isoformat(), "svincolati_presi": [{"squadra": "Mia", "giocatori": [{"id": 9}]}]}]
    recenti = bs.movimenti_recenti(movimenti, "Mia", OGGI)
    assert recenti == ({1}, {2})
    assert bs.ripensamento(1, 5, recenti) and bs.ripensamento(5, 2, recenti) and bs.ripensamento(9, 5, recenti) is None


def test_scambio_stupido_e_sensato():
    prof = {1: g("Dai", quota_titolare=0.5, p_lungo=0.5, mu=4.0), 2: g("Ricevo"), 3: g("Dai2", stato="infortunato", quota_titolare=0.2, p_lungo=0.0, mu=3.0)}
    buono = {"do": [{"id": 1, "ruolo": "A"}], "ricevo": [{"id": 2, "ruolo": "A"}], "per_giornata_mio": [1.0] * 5}
    assert bs.giudica_scambio(buono, prof)[0]
    piccolo = buono | {"per_giornata_mio": [0.1] * 5}
    assert not bs.giudica_scambio(piccolo, prof)[0]
    infortunato = buono | {"do": [{"id": 3, "ruolo": "A"}]}
    assert not bs.giudica_scambio(infortunato, prof)[0]


def test_chi_manca_da_settimane_non_e_un_titolare_utile():
    """Titolare «sulla carta» ma assente da molte giornate (p_lungo basso): non è protetto, ma il guadagno deve comunque bastare."""
    assente = g("Alfa", quota_titolare=0.8, p_lungo=0.2, p_voto=0.1, mu=6.5)
    ok, _ = svincolo(assente, g("Beta", mu=6.0), [1.0] * 5)
    assert ok
    ok, motivo = svincolo(assente, g("Beta", mu=6.0), [0.2] * 5)
    assert not ok and "piccola" in motivo


def test_scambio_che_da_un_titolare_per_uno_migliore_passa():
    prof = {1: g("Dai", mu=6.0), 2: g("Ricevo", mu=7.5), 3: g("Peggiore", mu=5.0)}
    scambio = {"do": [{"id": 1, "ruolo": "A"}], "ricevo": [{"id": 2, "ruolo": "A"}], "per_giornata_mio": [1.0] * 5}
    assert bs.giudica_scambio(scambio, prof)[0]
    peggiore = scambio | {"ricevo": [{"id": 3, "ruolo": "A"}]}
    assert not bs.giudica_scambio(peggiore, prof)[0]


def test_squadra_senza_articolo_sbagliato():
    """Collaudo del 2/11/2026: «Malen è titolare fisso nel Roma». Ora la squadra va tra parentesi, senza articolo."""
    assert "è titolare fisso (Roma)" in bs.perche_si(None, g("Malen", squadra="roma"))
    assert "non è un titolare fisso (Lazio)" in bs.entra_affidabile(g("Riserva", squadra="lazio", quota_titolare=0.1))
    assert " nel " not in bs.perche_si(None, g("Malen", squadra="juventus"))
