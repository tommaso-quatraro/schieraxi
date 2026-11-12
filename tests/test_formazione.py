"""Sostituzioni, modificatore difesa, fantavoto con le regole della lega e scelta della formazione."""
import pytest

from fanta import formazione as fz
from fanta.punteggio import fantavoto, modificatore_difesa
from fanta.regole import Regole, imposta


def G(id, ruolo, p=1.0, mu=6.0, voto=6.0):
    return fz.Giocatore(id, f"g{id}", ruolo, p, mu, voto)


TITOLARI_433 = [G(1, "P"), G(2, "D"), G(3, "D"), G(4, "D"), G(5, "D"), G(6, "C"), G(7, "C"), G(8, "C"),
                G(9, "A"), G(10, "A"), G(11, "A")]


def _gioca(*assenti, ids=range(1, 30)):
    return {i: i not in assenti for i in ids}


def test_sostituzione_in_ordine_di_panchina():
    panchina = [G(20, "D"), G(21, "A"), G(22, "A")]
    va, scoperti = fz.chi_va_a_punteggio(TITOLARI_433, panchina, _gioca(9), Regole())
    ids = {g.id for g in va}
    # esce un attaccante, entra il difensore: 5-3-2 è un modulo ammesso
    assert 9 not in ids and 20 in ids and scoperti == 0 and len(ids) == 11
    # panchina libera: entra il primo della panchina che si può far entrare, anche di altro ruolo
    va, _ = fz.chi_va_a_punteggio(TITOLARI_433, [G(20, "C"), G(21, "A")], _gioca(9), Regole())
    assert 20 in {g.id for g in va} and 21 not in {g.id for g in va}
    # se il primo non ha giocato si passa al successivo
    va, _ = fz.chi_va_a_punteggio(TITOLARI_433, [G(20, "C"), G(21, "A")], _gioca(9, 20), Regole())
    assert 21 in {g.id for g in va}


def test_cambio_modulo_ammesso_e_non():
    r = Regole()  # libera, cambio modulo, moduli standard
    # manca un attaccante, in panchina solo un centrocampista: 4-4-2 è ammesso
    va, _ = fz.chi_va_a_punteggio(TITOLARI_433, [G(20, "C")], _gioca(9), r)
    assert 20 in {g.id for g in va}
    # manca un difensore, in panchina solo un attaccante: 3-3-4 non è ammesso
    va, scoperti = fz.chi_va_a_punteggio(TITOLARI_433, [G(21, "A")], _gioca(2), r)
    assert 21 not in {g.id for g in va} and scoperti == 1
    # senza cambio modulo nemmeno il centrocampista entra
    r2 = imposta(r, "panchina.cambio_modulo", "false")
    va, scoperti = fz.chi_va_a_punteggio(TITOLARI_433, [G(20, "C")], _gioca(9), r2)
    assert 20 not in {g.id for g in va} and scoperti == 1


def test_portiere_solo_con_portiere():
    va, scoperti = fz.chi_va_a_punteggio(TITOLARI_433, [G(20, "D"), G(21, "P")], _gioca(1), Regole())
    assert 21 in {g.id for g in va} and 20 not in {g.id for g in va}


def test_massimo_sostituzioni():
    panchina = [G(20, "D"), G(21, "C"), G(22, "A"), G(23, "A")]
    r = imposta(Regole(), "panchina.max_sostituzioni", "3")
    va, scoperti = fz.chi_va_a_punteggio(TITOLARI_433, panchina, _gioca(2, 6, 9, 10), r)
    assert scoperti == 1 and len(va) == 10


def test_panchina_per_ruolo_prima_lo_stesso_ruolo():
    r = imposta(Regole(), "panchina.tipo", '"per_ruolo"')
    panchina = [G(20, "C"), G(21, "A")]   # il C viene prima, ma per ruolo entra l'A
    va, _ = fz.chi_va_a_punteggio(TITOLARI_433, panchina, _gioca(9), r)
    assert 21 in {g.id for g in va} and 20 not in {g.id for g in va}


def test_voto_d_ufficio_e_modificatore():
    r = imposta(Regole(), "voto_senza_sostituto", "4")
    r = imposta(r, "modificatore_difesa.attivo", "true")
    fv = {g.id: 6.0 for g in TITOLARI_433}
    voto = {g.id: 7.0 for g in TITOLARI_433}
    # nessuno assente: 11 x 6 + modificatore (media 7 -> +6 con le soglie predefinite)
    assert fz.punteggio(TITOLARI_433, [], _gioca(), fv, voto, r) == pytest.approx(66 + 6)
    # un attaccante senza sostituto: 10 x 6 + 4 d'ufficio + 6
    assert fz.punteggio(TITOLARI_433, [], _gioca(9), fv, voto, r) == pytest.approx(60 + 4 + 6)
    # con 3 difensori in campo il modificatore non vale
    assert modificatore_difesa(7, [7, 7, 7], r) == 0


def test_fantavoto_con_regole_della_lega():
    r = imposta(Regole(), "bonus.gol.D", "4.5")
    riga = {"voto_red": 6.5, "gol": 1, "rig_segnati": 1, "assist": 1, "ammonizioni": 1, "gol_subiti": 0}
    assert fantavoto(riga, "D", r) == pytest.approx(6.5 + 4.5 + 3 + 1 - 0.5)
    assert fantavoto(riga, "A", r) == pytest.approx(6.5 + 3 + 3 + 1 - 0.5)
    portiere = {"voto_red": 6, "gol_subiti": 2}
    assert fantavoto(portiere, "P", r) == pytest.approx(6 - 2)
    assert fantavoto({"voto_red": 6, "gol_subiti": 0}, "P", r) == pytest.approx(7)
    assert fantavoto({"voto_red": None}, "A", r) is None


def test_migliore_sceglie_chi_gioca_e_il_modulo():
    rosa = ([G(1, "P", 0.95, 6), G(2, "P", 0.1, 6)]
            + [G(10 + i, "D", 0.9, 6) for i in range(5)]
            + [G(20 + i, "C", 0.9, 6.5) for i in range(5)]
            + [G(30, "A", 0.9, 9), G(31, "A", 0.9, 8.5), G(32, "A", 0.9, 8), G(33, "A", 0.0, 12)])
    f = fz.migliore(rosa, Regole(), simulazioni=400)
    ids = {g.id for g in f.titolari}
    assert 1 in ids and 2 not in ids                 # gioca il portiere titolare
    assert {30, 31, 32} <= ids and 33 not in ids      # l'attaccante fortissimo ma infortunato resta fuori
    assert f.modulo in ("3-4-3", "4-3-3")
    assert len(f.titolari) == 11 and len(f.panchina) <= 7


def test_titolare_in_dubbio_con_il_cambio_pronto():
    """Chi gioca di rado ma vale molto si può schierare se il suo sostituto è il primo in panchina (sotto il 20% solo se metterci
    il sostituto costa almeno 0,3 punti attesi: vedi i test «nessun titolare che non gioca»)."""
    rosa = ([G(1, "P", 0.95, 6)] + [G(10 + i, "D", 0.9, 6) for i in range(4)]
            + [G(20 + i, "C", 0.9, 6.5) for i in range(4)]
            + [G(30, "A", 0.9, 9), G(31, "A", 0.9, 8.5), G(32, "A", 0.9, 8), G(33, "A", 0.05, 12)])
    f = fz.migliore(rosa, Regole(), simulazioni=600)
    if 33 in {g.id for g in f.titolari}:
        assert f.panchina[0].id == 32


# ---------------------------------------------------------------- nessun titolare che non gioca (#329)
# Rosa con un solo modulo possibile (4-3-3: 4 difensori, 3 centrocampisti, 4 attaccanti) e tutti sicuri tranne due attaccanti per
# il terzo posto: X (gioca poco ma fa tanti punti) e Y (gioca di più). Il posto vale, in media, con X titolare e Y in panchina
# pX·M + (1 - pX)·pY·m; con Y titolare e X in panchina pY·m + (1 - pY)·pX·M. La differenza è pX·pY·(M - m): la ricerca
# sceglie X (quando giocano tutti e due, X fa di più) e lo scambio con Y costa proprio pX·pY·(M - m) punti attesi.
X, Y = 40, 41


def _rosa_terzo_attaccante(p_x, mu_x, p_y, mu_y):
    return ([G(1, "P", 1, 6)] + [G(10 + i, "D", 1, 6) for i in range(4)] + [G(20 + i, "C", 1, 6.5) for i in range(3)]
            + [G(30, "A", 1, 8), G(31, "A", 1, 8), G(X, "A", p_x, mu_x), G(Y, "A", p_y, mu_y)])


def _titolari(f):
    return {g.id for g in f.titolari}


@pytest.mark.parametrize("stile", fz.LIVELLI_RISCHIO, ids=lambda s: s[1])
def test_titolare_improbabile_lascia_il_posto_al_compagno_che_gioca(stile):
    """X al 15% e Y al 60%: lo scambio costa 0,15 x 0,6 x 2 = 0,18 punti attesi (meno di 0,3), quindi gioca Y, con ogni stile."""
    _, _, peso, inclinazione, _ = stile
    f = fz.migliore(_rosa_terzo_attaccante(0.15, 8, 0.6, 6), Regole(), peso=peso, inclinazione=inclinazione)
    assert Y in _titolari(f) and X not in _titolari(f)
    assert [g.id for g in f.panchina] == [X]                        # X non sparisce: va in panchina


def test_compagno_proprio_al_50_per_cento_basta():
    """Y gioca al 50% (il minimo): costo 0,15 x 0,5 x 2 = 0,15 punti attesi, si scambia."""
    f = fz.migliore(_rosa_terzo_attaccante(0.15, 8, 0.5, 6), Regole())
    assert Y in _titolari(f) and X not in _titolari(f)


def test_titolare_improbabile_resta_se_lo_scambio_costa_troppo():
    """X al 15% che fa 14 quando gioca, Y al 60% che fa 6: lo scambio costerebbe 0,15 x 0,6 x 8 = 0,72 punti attesi."""
    f = fz.migliore(_rosa_terzo_attaccante(0.15, 14, 0.6, 6), Regole())
    assert X in _titolari(f) and Y not in _titolari(f)


def test_titolare_improbabile_resta_senza_un_compagno_al_50_per_cento():
    """Y gioca solo al 40%: nessun compagno di ruolo abbastanza sicuro, resta la scelta della ricerca (X)."""
    f = fz.migliore(_rosa_terzo_attaccante(0.15, 8, 0.4, 6), Regole())
    assert X in _titolari(f) and Y not in _titolari(f)


def test_titolare_al_20_per_cento_non_e_improbabile():
    """X gioca proprio al 20%: non è sotto la soglia, resta anche se lo scambio costerebbe poco (0,2 x 0,6 x 2 = 0,24)."""
    f = fz.migliore(_rosa_terzo_attaccante(0.2, 8, 0.6, 6), Regole())
    assert X in _titolari(f) and Y not in _titolari(f)


def _confronto_x_y(monkeypatch, *rosa_param):
    """Il Confronto (⇄) tra X e Y nella formazione vera calcolata da consigli (`_calcola_formazione`) su `_rosa_terzo_attaccante`."""
    import pandas as pd

    from fanta import consigli
    from fanta.lega import GiocatoreRosa, Squadra
    rosa = _rosa_terzo_attaccante(*rosa_param)
    prev = pd.DataFrame([{"nome": g.nome, "ruolo": g.ruolo, "p_voto": g.p, "mu": g.mu, "mu_voto": g.mu_voto} for g in rosa],
                        index=[g.id for g in rosa])
    squadra = Squadra("Prova", [GiocatoreRosa(g.id, g.nome, g.ruolo, None) for g in rosa])
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {"id": int(i), "nome": x["nome"]})
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: consigli._calcola_formazione(squadra, prev, 10, True, Regole(), 600))
    return consigli._in_formazione(None, Regole(), object(), None, 10, None, X, Y, prev)


def test_confronto_dice_che_il_titolare_improbabile_quasi_certamente_non_gioca(monkeypatch):
    """#341: Y (60%) è titolare al posto di X (15%) per la regola sopra, e invertirli varrebbe di più. Il Confronto dice il motivo
    vero (X quasi certamente non gioca), non «con il modulo 4-3-3 (non il migliore) la scelta non è la più conveniente»."""
    r = _confronto_x_y(monkeypatch, 0.15, 8, 0.6, 6)
    assert (r["posto_a"], r["posto_b"]) == ("panchina 1", "titolare")
    assert r["differenza"] < -0.04                                  # invertirli varrebbe di più: è il caso della issue
    assert r["frase"]["chiave"] == "confronto.titolare_che_gioca"
    assert "g40 quasi certamente non gioca (15% di giocare)" in r["testo"] and "g41, che gioca 60%" in r["testo"]
    assert "non il migliore" not in r["testo"]


def test_confronto_senza_improbabile_resta_come_prima(monkeypatch):
    """X al 15% che fa poco (4) quando gioca: Y è titolare perché vale di più anche da solo, e il Confronto lo dice come prima."""
    r = _confronto_x_y(monkeypatch, 0.15, 4, 0.6, 6)
    assert r["posto_b"] == "titolare" and r["differenza"] > 0.04
    assert r["frase"]["param"]["esito"]["chiave"] == "confronto.esito_meglio"


def _confronto_con_punti(monkeypatch, attuale, invertita, *rosa_param):
    """Il Confronto tra X e Y con i punti attesi della formazione fissati: `attuale` (com'è) e `invertita` (i due scambiati)."""
    import pandas as pd

    from fanta import consigli
    from fanta.lega import GiocatoreRosa, Squadra
    rosa = _rosa_terzo_attaccante(*rosa_param)
    prev = pd.DataFrame([{"nome": g.nome, "ruolo": g.ruolo, "p_voto": g.p, "mu": g.mu, "mu_voto": g.mu_voto} for g in rosa],
                        index=[g.id for g in rosa])
    squadra = Squadra("Prova", [GiocatoreRosa(g.id, g.nome, g.ruolo, None) for g in rosa])
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {"id": int(i), "nome": x["nome"]})
    f = consigli._calcola_formazione(squadra, prev, 10, True, Regole(), 600)        # prima, con le simulazioni vere
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: f)
    punti = iter([attuale, invertita])
    monkeypatch.setattr(fz.Valutatore, "atteso", lambda self, *a, **k: next(punti))
    return consigli._in_formazione(None, Regole(), object(), None, 10, None, X, Y, prev)


@pytest.mark.parametrize("attuale", [72.74, 72.66])
def test_confronto_la_differenza_torna_con_i_numeri_scritti(monkeypatch, attuale):
    """#392: «vale 72,7 punti attesi; con i due invertiti 72,1 (−0,6)»: la differenza è quella dei due numeri scritti (72,66 − 72,14
    = 0,52 darebbe «0,5») e il meno è quello tipografico, non il trattino."""
    r = _confronto_con_punti(monkeypatch, attuale, 72.14, 0.15, 4, 0.6, 6)
    assert r["posto_b"] == "titolare"
    assert "Con g41 titolare la formazione vale 72,7 punti attesi; con i due invertiti 72,1 (−0,6)." in r["testo"]
    assert r["frase"]["param"]["esito"]["param"]["d"] == "-0.6"


def test_confronto_invertirli_varrebbe_di_piu_con_il_piu_davanti(monkeypatch):
    """Invertendoli si guadagna: la differenza è positiva e si scrive «+0,6» (60,6 − 60,0), non «0,5» (60,56 − 60,04 = 0,52)."""
    r = _confronto_con_punti(monkeypatch, 60.04, 60.56, 0.3, 4, 0.6, 6)
    assert r["posto_b"] == "titolare" and r["frase"]["param"]["esito"]["chiave"] == "confronto.esito_peggio"
    assert "Invertendoli la formazione varrebbe 60,6 invece di 60,0 (+0,6):" in r["testo"]


def test_panchina_a_posti_fissi_per_ruolo():
    from fanta.formazione import Giocatore, _panchina
    from fanta.regole import Regole
    rosa = [Giocatore(i, f"g{i}", r, 0.9, 6.0 + i / 100, 6.0) for i, r in enumerate(
        ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6, 1)]
    r = Regole()
    r.panchina.numero, r.panchina.posti, r.panchina.tipo = 11, {"P": 2, "D": 3, "C": 3, "A": 3}, "per_ruolo"
    titolari = [g for g in rosa if g.id in (1, 4, 5, 6, 7, 12, 13, 14, 20, 21, 22)]
    panchina = _panchina(rosa, titolari, r)
    assert len(panchina) == 11
    assert [sum(1 for g in panchina if g.ruolo == k) for k in "PDCA"] == [2, 3, 3, 3]
    assert [g.ruolo for g in panchina] == sorted((g.ruolo for g in panchina), key="PDCA".index)   # in ordine di ruolo
    r.panchina.posti = None
    assert len(_panchina(rosa, titolari, r)) == 11 and r.problemi() == []


# ---------------------------------------------------------------- ordine della panchina (#612)
# Una riserva entra solo se ha preso voto: a quel punto conta quanto vale se gioca (il fantavoto atteso), non «gioca N% x fantavoto».
def _rosa_due_riserve():
    """4-4-2 obbligato (tutti i titolari sicuri tranne un difensore) e due difensori di riserva: SICURO gioca quasi sempre e vale
    poco, FORTE gioca meno ma vale di più. Per «gioca N% x fantavoto» SICURO sta davanti (5,7 contro 4,2); per fantavoto atteso FORTE."""
    return ([G(1, "P", 1, 6), G(2, "P", 0.5, 5)] + [G(10 + i, "D", 1, 6.5) for i in range(3)] + [G(13, "D", 0.5, 6.5)]
            + [G(SICURO, "D", 0.95, 6.0), G(FORTE, "D", 0.6, 7.0)]
            + [G(20 + i, "C", 1, 7) for i in range(4)] + [G(24, "C", 0.9, 5.5), G(25, "C", 0.4, 6.5)]
            + [G(30, "A", 1, 8), G(31, "A", 1, 8), G(32, "A", 0.3, 7.5), G(33, "A", 0.9, 6.2)])


SICURO, FORTE = 14, 15


def _titolari_442(rosa):
    return [g for g in rosa if g.id in (1, 10, 11, 12, 13, 20, 21, 22, 23, 30, 31)]


def test_panchina_per_ruolo_dentro_il_ruolo_in_ordine_di_fantavoto_atteso():
    rosa = _rosa_due_riserve()
    r = imposta(Regole(), "panchina.tipo", '"per_ruolo"')
    panchina = fz._panchina(rosa, _titolari_442(rosa), r)
    assert [g.ruolo for g in panchina] == sorted((g.ruolo for g in panchina), key="PDCA".index)   # tra i ruoli: P, D, C, A
    for ruolo in "PDCA":
        mu = [g.mu for g in panchina if g.ruolo == ruolo]
        assert mu == sorted(mu, reverse=True), ruolo                                              # dentro il ruolo: chi vale di più
    assert [g.id for g in panchina if g.ruolo == "D"] == [FORTE, SICURO]


def test_panchina_a_posti_fissi_dentro_il_ruolo_in_ordine_di_fantavoto_atteso():
    rosa = _rosa_due_riserve()
    r = Regole()
    r.panchina.numero, r.panchina.posti, r.panchina.tipo = 7, {"P": 1, "D": 2, "C": 2, "A": 2}, "per_ruolo"
    panchina = fz._panchina(rosa, _titolari_442(rosa), r)
    assert [g.id for g in panchina] == [2, FORTE, SICURO, 25, 24, 32, 33]


def test_panchina_libera_in_ordine_di_fantavoto_atteso():
    """Panchina libera: entra il primo con voto che può entrare, di qualunque ruolo. Davanti chi vale di più quando gioca."""
    rosa = _rosa_due_riserve()
    panchina = fz._panchina(rosa, _titolari_442(rosa), Regole())
    mu = [g.mu for g in panchina]
    assert len(panchina) == 7 and mu == sorted(mu, reverse=True)


def test_chi_sta_in_panchina_resta_scelto_per_gioca_per_fantavoto():
    """L'ordine cambia, la scelta di CHI va in panchina no: con un solo posto per i difensori ci va chi ha più «gioca N% x fantavoto»."""
    rosa = _rosa_due_riserve()
    r = Regole()
    r.panchina.numero, r.panchina.posti, r.panchina.tipo = 4, {"P": 1, "D": 1, "C": 1, "A": 1}, "per_ruolo"
    assert [g.id for g in fz._panchina(rosa, _titolari_442(rosa), r)] == [2, SICURO, 24, 33]


@pytest.mark.parametrize("tipo", ["per_ruolo", "libera"])
def test_la_panchina_in_ordine_di_fantavoto_atteso_vale_di_piu(tipo):
    """Stessi titolari e stesse riserve: con FORTE davanti a SICURO i punti attesi salgono (quando hanno voto tutti e due entra
    quello che vale di più; quando ne ha uno solo entra lui comunque)."""
    rosa = _rosa_due_riserve()
    r = imposta(Regole(), "panchina.tipo", f'"{tipo}"')
    titolari = _titolari_442(rosa)
    panchina = fz._panchina(rosa, titolari, r)
    per_valore = sorted(panchina, key=lambda g: (fz.ORDINE_RUOLO[g.ruolo], -g.valore) if tipo == "per_ruolo" else -g.valore)
    assert [g.id for g in per_valore] != [g.id for g in panchina]
    val = fz.Valutatore(rosa, r, 600)
    assert val.atteso(titolari, panchina) > val.atteso(titolari, per_valore) + 0.05


def _due_attaccanti_stessi_punti():
    """Formazioni uguali tranne un attaccante: A gioca sempre e fa 6; B gioca una volta su due e quando gioca fa 12 (stessa media)."""
    base = [G(1, "P", 1, 6)] + [G(10 + i, "D", 1, 6) for i in range(4)] + [G(20 + i, "C", 1, 6.5) for i in range(3)] + [G(30, "A", 1, 8), G(31, "A", 1, 8)]
    a, b = G(32, "A", 1.0, 6.0), G(33, "A", 0.5, 12.0)
    return base, a, b


def test_livelli_di_rischio_sicura_o_rischiosa():
    base, a, b = _due_attaccanti_stessi_punti()
    r = Regole()
    val = fz.Valutatore(base + [a, b], r, 3000)
    (ma, da, bruttaa, eccezionalea), (mb, db, bruttab, eccezionaleb) = val.statistiche(base + [a], []), val.statistiche(base + [b], [])
    assert ma == pytest.approx(mb, abs=0.4) and db > da                          # stessa media, B oscilla di più
    sicura, rischiosa = fz.LIVELLI_RISCHIO[0][2], fz.LIVELLI_RISCHIO[-1][2]
    assert val.scelta(base + [a], [], sicura) > val.scelta(base + [b], [], sicura)
    assert val.scelta(base + [b], [], rischiosa) > val.scelta(base + [a], [], rischiosa)
    assert bruttaa <= ma <= eccezionalea and bruttab <= mb <= eccezionaleb


def test_spareggio_a_parita_vince_la_formazione_piu_sicura():
    """Se uno è appena meglio in media (+0,1) ma gioca una volta su due, con il peso di base si schiera quello che gioca sempre."""
    base, a, _ = _due_attaccanti_stessi_punti()
    b = G(33, "A", 0.5, 12.2)
    val = fz.Valutatore(base + [a, b], Regole(), 3000)
    assert val.atteso(base + [b], []) > val.atteso(base + [a], []) - 0.3
    assert val.scelta(base + [a], [], fz.PESO_BASE) > val.scelta(base + [b], [], fz.PESO_BASE)


# ---------------------------------------------------------------- Valutatore vettoriale = punteggio una simulazione alla volta
def _rosa_casuale(rng, n_per_ruolo=(3, 7, 7, 5)):
    rosa, i = [], 1
    for ruolo, n in zip("PDCA", n_per_ruolo):
        for _ in range(n):
            rosa.append(G(i, ruolo, p=float(rng.uniform(0.3, 0.98)), mu=float(rng.uniform(4, 9)), voto=float(rng.uniform(5.3, 7))))
            i += 1
    return rosa


@pytest.mark.parametrize("assetto", [
    dict(),
    dict(tipo="per_ruolo"),
    dict(tipo="per_ruolo", cambio_modulo=False),
    dict(cambio_modulo=False, max_sostituzioni=1),
    dict(max_sostituzioni=5, numero=9, voto=4.0),
    dict(tipo="per_ruolo", max_sostituzioni=2, voto=4.0, difesa=True),
    dict(difesa=True, voto=3.0),
])
def test_valutatore_vettoriale_uguale_al_calcolo_semplice(assetto):
    import numpy as np
    r = Regole()
    r.panchina.tipo = assetto.get("tipo", "libera")
    r.panchina.cambio_modulo = assetto.get("cambio_modulo", True)
    r.panchina.max_sostituzioni = assetto.get("max_sostituzioni", 3)
    r.panchina.numero = assetto.get("numero", 7)
    r.voto_senza_sostituto = assetto.get("voto")
    r.modificatore_difesa.attivo = assetto.get("difesa", True)
    rng = np.random.default_rng(3)
    for _ in range(2):
        rosa = _rosa_casuale(rng)
        val = fz.Valutatore(rosa, r, 120)
        for peso in (fz.PESO_BASE, (1.5, 0.0), (0.0, 0.5)):
            f = fz.migliore(rosa, r, 120, peso=peso, valutatore=val)
            for x in f.tutte:
                vett = val._punti(x.titolari, x.panchina)
                lento = val._punti_lenti(x.titolari, x.panchina)
                assert vett == pytest.approx(lento, abs=1e-9)


def test_un_giocatore_ripetuto_nella_rosa_non_gioca_due_volte():
    """Una rosa importata con lo stesso giocatore due volte (riga doppia nel file, due nomi abbinati allo stesso codice):
    prima il migliore poteva comparire due volte tra i titolari."""
    rosa = [G(1, "P", 0.95), G(2, "P", 0.5, 5)] + [G(10 + i, "D", 0.9) for i in range(8)] + [G(20 + i, "C", 0.9) for i in range(8)]
    rosa += [G(30 + i, "A", 0.5) for i in range(5)] + [G(99, "A", 0.95, 10, 7)]
    rosa.append(rosa[-1])
    f = fz.migliore(rosa, Regole())
    ids = [g.id for g in f.titolari + f.panchina]
    assert len(ids) == len(set(ids)) and len(f.titolari) == 11


# ---------------------------------------------------------------- calcolo veloce identico a quello semplice
def _formazione_casuale(rng, rosa, n_panchina):
    """Titolari con un portiere (modulo qualsiasi) e una panchina casuale, in ordine casuale."""
    per = {r: [g for g in rosa if g.ruolo == r] for r in "PDCA"}
    d, c = int(rng.integers(3, 6)), int(rng.integers(3, 6))
    a = 10 - d - c
    if a < 1:
        d, c, a = 4, 4, 2
    titolari = [per["P"][int(rng.integers(len(per["P"])))]]
    for r, n in (("D", d), ("C", c), ("A", a)):
        titolari += [per[r][i] for i in rng.choice(len(per[r]), n, replace=False)]
    ids = {t.id for t in titolari}
    resto = [g for g in rosa if g.id not in ids]
    panchina = [resto[i] for i in rng.permutation(len(resto))[:n_panchina]]
    return titolari, panchina


@pytest.mark.parametrize("cambio_modulo", [False, True])
@pytest.mark.parametrize("seme", range(6))
def test_sostituzioni_per_insiemi_uguali_a_una_simulazione_alla_volta(seme, cambio_modulo):
    """Il calcolo per insiemi di simulazioni dà, simulazione per simulazione, le stesse riserve in campo di `chi_va_a_punteggio`."""
    import numpy as np
    rng = np.random.default_rng(100 + seme)
    r = Regole()
    r.panchina.cambio_modulo = cambio_modulo
    r.panchina.tipo = ["libera", "per_ruolo"][seme % 2]
    rosa = _rosa_casuale(rng, (3, 8, 8, 6))
    val = fz.Valutatore(rosa, r, 200, seme=seme)
    calcola = val._sostituzioni_cambio_modulo if cambio_modulo else val._sostituzioni_stesso_ruolo
    for _ in range(25):
        r.panchina.max_sostituzioni = int(rng.integers(0, 6))
        titolari, panchina = _formazione_casuale(rng, rosa, int(rng.integers(1, 12)))
        ct = [val.indice[g.id] for g in titolari]
        cb = [val.indice[g.id] for g in panchina]
        entra = calcola(titolari, panchina, ct, cb)
        for s in range(200):
            gioca = {g.id: bool(val.gioca[s, val.indice[g.id]]) for g in rosa}
            va, _ = fz.chi_va_a_punteggio(titolari, panchina, gioca, r)
            attesi = {g.id for g in va} - {t.id for t in titolari}
            assert {panchina[j].id for j in np.flatnonzero(entra[:, s])} == attesi


def test_percentili_identici_a_numpy():
    import numpy as np
    rng = np.random.default_rng(5)
    for n in (2, 3, 7, 11, 120, 599, 600, 601):
        for _ in range(300):
            x = rng.normal(60, 9, n)
            if n % 2:
                x = np.round(x, 1)                    # valori ripetuti
            attesi = np.percentile(x, (10, 90))
            assert fz._percentili_10_90(x) == (attesi[0], attesi[1])


def _difesa_con_ordinamento(val, titolari, panchina, ct, cb, gt, entrati):
    """Il modificatore difesa calcolato come prima (ordinando i voti di ogni simulazione): riferimento per il calcolo veloce."""
    import numpy as np
    m = val.regole.modificatore_difesa
    ip = next(i for i, t in enumerate(titolari) if t.ruolo == "P")
    voto_p = np.where(gt[:, ip], val.voti[:, ct[ip]], 0.0)
    ha_p = gt[:, ip].copy()
    for j, b in enumerate(panchina):
        if b.ruolo == "P":
            voto_p = np.where(entrati[:, j], val.voti[:, cb[j]], voto_p)
            ha_p |= entrati[:, j]
    dt = [i for i, t in enumerate(titolari) if t.ruolo == "D"]
    db = [j for j, b in enumerate(panchina) if b.ruolo == "D"]
    in_campo = np.concatenate([gt[:, dt], entrati[:, db]], axis=1)
    v = np.where(in_campo, val.voti[:, [ct[i] for i in dt] + [cb[j] for j in db]], -np.inf)
    v.sort(axis=1)
    migliori = v[:, -3:]
    somma = np.where(np.isfinite(migliori), migliori, 0.0).sum(axis=1)
    media = (voto_p + somma) / 4
    bonus = np.zeros(len(gt))
    for soglia, valore in sorted(m.soglie):
        bonus = np.where(media >= soglia, valore, bonus)
    return np.where(ha_p & (in_campo.sum(axis=1) >= m.min_difensori), bonus, 0.0)


@pytest.mark.parametrize("cambio_modulo", [False, True])
def test_modificatore_difesa_veloce_identico_bit_per_bit(cambio_modulo):
    import numpy as np
    rng = np.random.default_rng(11)
    r = Regole()
    r.panchina.cambio_modulo = cambio_modulo
    r.modificatore_difesa.attivo = True
    rosa = _rosa_casuale(rng, (3, 8, 8, 6))
    val = fz.Valutatore(rosa, r, 300)
    for _ in range(40):
        titolari, panchina = _formazione_casuale(rng, rosa, int(rng.integers(1, 12)))
        ct = [val.indice[g.id] for g in titolari]
        cb = [val.indice[g.id] for g in panchina]
        gt = val.gioca[:, ct]
        entrati = rng.random((300, len(cb))) < 0.3           # qui conta solo il calcolo del modificatore: chi entra è a caso
        veloce = val._difesa(titolari, panchina, ct, cb, val._gioca_g[ct], entrati.T)
        assert np.array_equal(veloce, _difesa_con_ordinamento(val, titolari, panchina, ct, cb, gt, entrati))
