"""Il perché della scelta in una riga (#356, L3 di #166): per i titolari che sembrano una scelta storta (meno punti attesi di un
escluso dello stesso ruolo) e per gli incerti con la riserva sicura, il motivo vero della scelta, con il conto del Confronto.
Rose e numeri inventati."""
import json
import shutil

import pandas as pd
import pytest

from fanta import consigli, lega, perche_scelta
from fanta import formazione as fz
from fanta.regole import Regole
import codice_web

SOLO_442 = Regole(moduli=["4-4-2"])
GIORNATA = 9
CON_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node non installato")

# 25 giocatori inventati: (id, ruolo, gioca, fantavoto atteso se gioca).
# Difesa: 7 gioca il 60% ma se gioca fa 7,5 (4,5 punti attesi da solo); 8 gioca il 95% e fa 5,2 (4,94): 8 ha più punti attesi,
# ma con 7 titolare e 8 primo in panchina la formazione vale di più (se 7 non gioca entra 8). Scelta che sembra storta.
# Attacco: 21 gioca il 45% (incerto), la sua riserva 22 il 90%: 21 ha comunque più punti attesi di tutti gli esclusi.
ROSA = ([(1, "P", 0.95, 6.5), (2, "P", 0.95, 5.0), (3, "P", 0.95, 4.5)]
        + [(4, "D", 0.95, 6.6), (5, "D", 0.95, 6.5), (6, "D", 0.95, 6.4), (7, "D", 0.6, 7.5), (8, "D", 0.95, 5.2),
           (9, "D", 0.95, 4.5), (10, "D", 0.95, 4.5), (11, "D", 0.95, 4.5)]
        + [(12, "C", 0.95, 7.0), (13, "C", 0.95, 6.9), (14, "C", 0.95, 6.8), (15, "C", 0.95, 6.7), (16, "C", 0.95, 4.0),
           (17, "C", 0.95, 4.0), (18, "C", 0.95, 4.0), (19, "C", 0.95, 4.0)]
        + [(20, "A", 0.95, 8.0), (21, "A", 0.45, 9.0), (22, "A", 0.9, 4.4), (23, "A", 0.95, 4.0), (24, "A", 0.95, 4.0),
           (25, "A", 0.95, 4.0)])


def G(i, ruolo="D", p=0.9, mu=6.0):
    return fz.Giocatore(i, f"Giocatore {i}", ruolo, p, mu, 6.0)


def _prev(cambi: dict | None = None) -> pd.DataFrame:
    righe = {i: {"nome": f"Giocatore {i}", "ruolo": r, "p_voto": p, "mu": mu, "mu_voto": 6.0, "stato": "titolare",
                 "quota_titolare": 0.9} for i, r, p, mu in ROSA}
    for i, c in (cambi or {}).items():
        righe[int(i)].update(c)
    return pd.DataFrame.from_dict(righe, orient="index")


def _squadra() -> lega.Squadra:
    return lega.Squadra("Squadra Prova", [lega.GiocatoreRosa(i, f"Giocatore {i}", r, "AAA", 1) for i, r, _, _ in ROSA])


@pytest.fixture(autouse=True)
def _schede_semplici(monkeypatch):
    """Le schede qui bastano con id, nome, ruolo, «gioca», punti attesi, titolarità e un «perché questo numero» vuoto."""
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "p_voto": float(x["p_voto"]), "fv_atteso": float(x["mu"]),
        "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2), "titolarita": consigli.titolarita(x), "perche_numero": []})


def _migliore(prev, sim=600) -> dict:
    return consigli._calcola_formazione(_squadra(), prev, GIORNATA, True, SOLO_442, sim)


def _scelta(f: dict) -> list[dict]:
    """Le righe del modulo della consigliata."""
    return next(m for m in f["moduli"] if m["modulo"] == f["modulo"])["perche_scelta"]


def _motivo(chiave, effetto):
    return {"chiave": chiave, "testo": chiave, "frase": None, "effetto": effetto}


# ------------------------------------------------------------------ il motivo, in ordine
T, Y = G(1, p=0.8, mu=6.5), G(2, p=0.9, mu=5.8)


@pytest.mark.parametrize("t, y, attuale, invertita, extra, chiave", [
    # 1. l'altro quasi certamente non gioca e scambiarli varrebbe di più: la regola dei titolari che giocano (#341)
    (G(1, p=0.9), G(2, p=0.1, mu=9.0), 60.0, 60.3, {}, "scelta.titolare_che_gioca"),
    # ...anche quando il titolare gioca poco ma non è «improbabile» (dalla revisione di #612 basta il 20%, non più il 50%)
    (G(1, p=0.22), G(2, p=0.04, mu=9.0), 60.0, 60.05, {}, "scelta.titolare_che_gioca"),
    # ...ma se con il titolare la formazione vale di più, si dice quello (come il Confronto)
    (G(1, p=0.9), G(2, p=0.1, mu=9.0), 60.3, 60.0, {}, "scelta.piu_punti"),
    # 2. titolare incerto con la riserva sicura: la nota che c'era già (con lui la formazione vale di più o lo stesso)
    (G(1, p=0.4), G(2, p=0.9), 60.5, 60.0, {"riserva": G(2, p=0.9)}, "scelta.incerto"),
    (G(1, p=0.4), G(2, p=0.9), 60.0, 60.02, {"riserva": G(2, p=0.9)}, "scelta.incerto"),
    # 3. con lui la formazione fa più punti attesi
    (T, Y, 64.09, 63.98, {}, "scelta.piu_punti"),
    # a schermo gli stessi punti (60,4 e 60,4): è un pari anche se la differenza supera quella del Confronto
    (G(1, p=0.9), G(2, p=0.8), 60.44, 60.39, {}, "scelta.piu_sicuro"),
    # 4. a pari punti gioca più sicuro
    (G(1, p=0.9), G(2, p=0.8), 60.0, 60.02, {}, "scelta.piu_sicuro"),
    # 5. a pari punti, meno sicuro ma con il fantavoto atteso più alto
    (G(1, p=0.55, mu=6.06), G(2, p=0.79, mu=5.89), 60.56, 60.54, {}, "scelta.fantavoto_piu_alto"),
    # 6. altrimenti il primo motivo proprio a favore del suo «perché questo numero» («gioca» e «partita» non lo sono)
    (G(1, p=0.9, mu=6.05), G(2, p=0.92, mu=6.05), 63.1, 63.1,
     {"perche_numero": [_motivo("gioca", None), _motivo("partita", 0.3), _motivo("rigori", 0.2)]}, "scelta.motivo"),
    # 7. nessun motivo proprio a favore (uno contro non vale): la formazione vale lo stesso con l'uno o con l'altro
    (G(1, p=0.9, mu=6.05), G(2, p=0.92, mu=6.05), 63.1, 63.1,
     {"perche_numero": [_motivo("partita", 0.3), _motivo("voti", -0.4)]}, "scelta.pari"),
    # scambiarli varrebbe di più: con la consigliata tenuta (#335) è per quello, sotto 1 punto (anche per un incerto)
    (T, Y, 60.0, 60.4, {"tenuta": True}, "scelta.stabile"),
    (T, Y, 60.0, 60.4, {"tenuta": True, "perche_numero": [_motivo("gol", 0.5)]}, "scelta.stabile"),
    (G(1, p=0.4), G(2, p=0.9), 60.0, 60.5, {"riserva": G(2, p=0.9), "tenuta": True}, "scelta.stabile"),
])
def test_il_motivo_della_scelta_in_ordine(t, y, attuale, invertita, extra, chiave):
    f = perche_scelta.motivo(t, y, attuale, invertita, **extra)
    assert f is not None and f.chiave == chiave, f


@pytest.mark.parametrize("t, y, attuale, invertita, extra", [
    (T, Y, 60.0, 60.4, {}),
    (T, Y, 60.0, 60.4, {"perche_numero": [_motivo("voti", -0.3)]}),
    # un motivo proprio a favore non basta: il Confronto dice che scambiarli varrebbe di più («esito_peggio»)
    (T, Y, 60.0, 60.4, {"perche_numero": [_motivo("gol", 0.5)]}),
    (T, Y, 60.0, 61.2, {"tenuta": True, "perche_numero": [_motivo("gol", 0.5)]}),       # tenuta, ma il cambio vale 1 punto o più
    # nemmeno la nota dell'incerto («insieme valgono di più») quando non è vero
    (G(1, p=0.4), G(2, p=0.9), 60.0, 60.5, {"riserva": G(2, p=0.9)}),
    # lo stesso numero a schermo non cambia il verdetto del Confronto: oltre 0,04 a sfavore, scambiarli varrebbe di più
    (G(1, p=0.9), G(2, p=0.8), 60.39, 60.44, {}),
])
def test_senza_un_motivo_vero_nessuna_riga(t, y, attuale, invertita, extra):
    """Scambiarli varrebbe di più e non è la consigliata tenuta: nessuna riga, meglio niente che una scusa."""
    assert perche_scelta.motivo(t, y, attuale, invertita, **extra) is None


def test_le_righe_in_italiano():
    tit, riserva = G(1, p=0.4), G(2, p=0.92)
    assert perche_scelta.motivo(tit, riserva, 60.5, 60.0, riserva=riserva) == (
        "Titolare anche se incerto (gioca 40%): se non gioca, in panchina c'è Giocatore 2 che gioca quasi di sicuro, "
        "e insieme valgono di più.")
    assert perche_scelta.senza_riserva(tit) == (
        "Titolare anche se incerto (gioca 40%): in panchina nessuno del suo ruolo gioca quasi di sicuro.")
    assert perche_scelta.motivo(T, Y, 64.09, 63.98) == (
        "Preferito a Giocatore 2: con lui la formazione fa più punti attesi (64,1 contro 64,0).")
    assert perche_scelta.motivo(G(1, p=0.9), G(2, p=0.8), 60.0, 60.02) == "A pari punti gioca più sicuro di Giocatore 2 (90% contro 80%)."
    assert perche_scelta.motivo(G(1, p=0.55, mu=6.06), G(2, p=0.79, mu=5.89), 60.56, 60.54) == (
        "A pari punti ha il fantavoto atteso più alto di Giocatore 2 (6,1 contro 5,9).")
    assert perche_scelta.motivo(G(1, p=0.9), G(2, p=0.1), 60.0, 60.3) == (
        "Titolare al posto di Giocatore 2, che quasi certamente non gioca (10% di giocare).")
    assert perche_scelta.motivo(T, Y, 60.0, 60.4, tenuta=True) == (
        "Con Giocatore 2 al suo posto la formazione farebbe 60,4 invece di 60,0: per meno di 1 punto la consigliata già mostrata non cambia.")


def test_le_percentuali_sono_quelle_di_gioca_n():
    """#452: la web scrive «gioca 35%» per 0,345 (Math.round); le righe del perché dicono lo stesso numero."""
    tit, riserva = G(1, p=0.345), G(2, p=0.92)
    assert "(gioca 35%)" in perche_scelta.motivo(tit, riserva, 60.5, 60.0, riserva=riserva)
    # la web parte da `p_voto` arrotondato a 3 decimali (la scheda): 0,3447 → 0,345 → «gioca 35%»
    assert "(gioca 35%)" in perche_scelta.motivo(G(1, p=0.3447), riserva, 60.5, 60.0, riserva=riserva)
    assert perche_scelta.motivo(G(1, p=0.9), G(2, p=0.125), 60.0, 60.3) == (
        "Titolare al posto di Giocatore 2, che quasi certamente non gioca (13% di giocare).")
    assert perche_scelta.motivo(G(1, p=0.905), G(2, p=0.8), 60.0, 60.02) == "A pari punti gioca più sicuro di Giocatore 2 (91% contro 80%)."


def test_la_consigliata_tenuta_cambia_da_un_punto():
    # il testo dice «per meno di 1 punto»: è la soglia della consigliata stabile
    assert consigli.SOGLIA_CAMBIO_PUNTI == perche_scelta.SOGLIA_TENUTA == 1


# ------------------------------------------------------------------ chi ha la riga
def test_una_riga_solo_per_le_scelte_storte_e_per_gli_incerti():
    f = _migliore(_prev())
    righe = _scelta(f)
    assert [(r["titolare"], r["altro"]) for r in righe] == [(7, 8), (21, 22)]
    assert [r["frase"]["chiave"] for r in righe] == ["scelta.piu_punti", "scelta.incerto"]
    for r in righe:                       # testo italiano del server e, accanto, come tradurlo (fanta/frasi.py)
        assert isinstance(r["testo"], str) and r["testo"] and set(r) == {"titolare", "altro", "testo", "frase"}
    json.dumps(f)                         # tutto si scrive nella risposta


def test_la_riga_dell_incerto_nomina_la_prima_riserva_sicura_della_panchina():
    """Revisione di #612: la panchina è in ordine di fantavoto atteso. L'attaccante 23 (gioca 70%, fa 7,0) sta davanti a 22 (90%,
    4,4): la riga dell'incerto 21 nomina 22, la prima riserva del ruolo che gioca quasi di sicuro, e non sparisce."""
    f = _migliore(_prev({23: {"p_voto": 0.7, "mu": 7.0}, 9: {"mu": 3.0}}))
    attaccanti = [i for i in [g["id"] for g in f["panchina"]] if i in (22, 23)]
    assert 21 in [g["id"] for g in f["titolari"]] and attaccanti == [23, 22]
    riga = next(r for r in _scelta(f) if r["titolare"] == 21)
    assert (riga["altro"], riga["frase"]["chiave"]) == (22, "scelta.incerto")
    assert "in panchina c'è Giocatore 22 che gioca quasi di sicuro" in riga["testo"]


def test_l_incerto_senza_una_riserva_sicura_ha_la_riga_che_lo_dice():
    """La riserva dell'attaccante incerto 21 gioca solo il 70%: nessun escluso ha più punti attesi di lui (niente scelta storta),
    ma chi legge deve sapere che dietro non c'è nessuno di sicuro. La riga non nomina nessuno (`altro` = None)."""
    f = _migliore(_prev({22: {"p_voto": 0.7, "mu": 5.5}}))
    assert 21 in [g["id"] for g in f["titolari"]] and 22 in [g["id"] for g in f["panchina"]]
    m = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])
    assert {"titolare": 21, "riserva": None} in m["incerti"]
    riga = next(r for r in _scelta(f) if r["titolare"] == 21)
    assert (riga["altro"], riga["frase"]["chiave"]) == (None, "scelta.incerto_senza_riserva")
    assert riga["testo"] == "Titolare anche se incerto (gioca 45%): in panchina nessuno del suo ruolo gioca quasi di sicuro."
    json.dumps(f)


def test_l_incerto_senza_riserva_sicura_ma_con_un_escluso_piu_forte_tiene_il_motivo_di_prima():
    """Se un escluso ha più punti attesi (scelta che sembra storta) la riga resta quella del confronto con lui."""
    f = _migliore(_prev({22: {"p_voto": 0.7, "mu": 6.0}}))
    riga = next(r for r in _scelta(f) if r["titolare"] == 21)
    assert (riga["altro"], riga["frase"]["chiave"]) == (22, "scelta.piu_punti")


def test_schede_senza_punti_attesi_usano_gioca_per_fantavoto():
    """Schede ridotte (solo id e nome, come in alcuni test del Confronto): le righe si calcolano lo stesso, con i punti attesi
    «gioca» per fantavoto atteso."""
    f = _migliore(_prev(), sim=200)
    m = next(x for x in f["moduli"] if x["modulo"] == f["modulo"])
    rosa = consigli._rosa(_squadra(), _prev())
    schede = {k: {"id": v["id"], "nome": v["nome"]} for k, v in f["schede"].items()}
    righe = perche_scelta.del_modulo(m, schede, rosa, SOLO_442, fz.Valutatore(rosa, SOLO_442, 200))
    assert [(r["titolare"], r["altro"]) for r in righe] == [(7, 8), (21, 22)]


def test_ogni_modulo_e_ogni_stile_hanno_le_righe():
    f = _migliore(_prev(), sim=200)
    moduli = f["moduli"] + [m for liv in f["livelli"] for m in liv["moduli"]]
    assert moduli and all(isinstance(m.get("perche_scelta"), list) for m in moduli)


def test_il_conto_e_quello_del_confronto(monkeypatch):
    """Una regola sola: la riga dice quello che dice il Confronto tra i due (stessi punti attesi, stesso esito)."""
    prev = _prev()
    f = _migliore(prev)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: f)
    confronto = consigli._in_formazione(None, SOLO_442, None, None, GIORNATA, None, 7, 8, prev)
    riga = next(r for r in _scelta(f) if r["titolare"] == 7)
    assert confronto["frase"]["param"]["esito"]["chiave"] == "confronto.esito_meglio"
    assert riga["frase"]["chiave"] == "scelta.piu_punti"
    # stessi punti attesi (il Confronto li arrotonda a 2 cifre, la riga a 1)
    assert float(riga["frase"]["param"]["attuale"]) == pytest.approx(confronto["attuale"], abs=0.051)
    assert float(riga["frase"]["param"]["invertita"]) == pytest.approx(confronto["invertita"], abs=0.051)
    assert confronto["attuale"] - confronto["invertita"] > 0.5


# l'esito del Confronto (`consigli._in_formazione`) che ogni riga può accompagnare: la riga non dice mai il contrario
CON_IL_CONFRONTO = {
    "scelta.titolare_che_gioca": {"confronto.titolare_che_gioca"},
    "scelta.piu_punti": {"confronto.esito_meglio"},
    "scelta.stabile": {"confronto.esito_peggio"},
    **{k: {"confronto.esito_meglio", "confronto.esito_pari"}
       for k in ("scelta.incerto", "scelta.piu_sicuro", "scelta.fantavoto_piu_alto", "scelta.motivo", "scelta.pari")},
}


def _esito(confronto: dict) -> str:
    frase = confronto["frase"]
    return frase["param"]["esito"]["chiave"] if frase["chiave"] == "confronto.principale" else frase["chiave"]


@pytest.mark.parametrize("tenuta", [False, True])
def test_ogni_riga_di_ogni_stile_e_modulo_dice_quello_che_dice_il_confronto(monkeypatch, tenuta):
    """Una regola sola, su tutti gli stili e tutti i moduli: per ogni riga il Confronto tra i due (stesso stile, stesso modulo) ha
    un esito compatibile e, dove la riga scrive i punti, gli stessi punti. Ogni scheda ha un motivo proprio a favore: è il caso
    della revisione, con lo stile «Molto sicura» uscivano righe «Preferito a X: …» dove il Confronto dice che scambiarli varrebbe
    di più."""
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "p_voto": float(x["p_voto"]), "fv_atteso": float(x["mu"]),
        "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2), "titolarita": consigli.titolarita(x),
        "perche_numero": [_motivo("gol", 0.4)]})
    prev = _prev()
    f = _migliore(prev)
    if tenuta:                            # la consigliata già mostrata, tenuta con i dati nuovi (#335)
        nuove = _prev({8: {"mu": 7.8}, 4: {"mu": 7.1}, 5: {"mu": 7.1}, 6: {"mu": 7.3}})
        ricordata = {"titolari": [g["id"] for g in f["titolari"]], "panchina": [g["id"] for g in f["panchina"]]}
        prev, f = nuove, consigli.stabile(_migliore(nuove), ricordata, nuove, _squadra(), SOLO_442, 600)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: f)
    viste = set()
    for liv in f["livelli"]:
        for m in liv["moduli"]:
            for r in m["perche_scelta"]:
                if r["altro"] is None:        # la riga non nomina nessuno (incerto senza riserva sicura): niente da confrontare
                    continue
                c = consigli._in_formazione(None, SOLO_442, None, None, GIORNATA, m["modulo"], r["titolare"], r["altro"], prev,
                                            liv["rischio"])
                chiave = r["frase"]["chiave"]
                assert _esito(c) in CON_IL_CONFRONTO[chiave], (liv["rischio"], m["modulo"], str(r["testo"]), c["testo"])
                param = r["frase"]["param"]
                if "attuale" in param:
                    assert float(param["attuale"]) == pytest.approx(c["attuale"], abs=0.051)
                    assert float(param["invertita"]) == pytest.approx(c["invertita"], abs=0.051)
                viste.add(chiave)
    assert {"scelta.piu_punti", "scelta.incerto"} <= viste
    assert ("scelta.stabile" in viste) == tenuta


def test_la_consigliata_tenuta_ha_le_sue_righe():
    """Consigliata stabile (#335): tenuta quella di prima, le sue righe dicono perché non è cambiata."""
    prima = _migliore(_prev(), sim=200)
    # il difensore 8 ora fa più di tutti i titolari della difesa, ma cambiarli vale meno di 1 punto in tutto
    nuove = _prev({8: {"mu": 7.8}, 4: {"mu": 7.1}, 5: {"mu": 7.1}, 6: {"mu": 7.3}})
    migliore = _migliore(nuove, sim=200)
    tit_prima = [g["id"] for g in prima["titolari"]]
    assert {g["id"] for g in migliore["titolari"]} != set(tit_prima)
    ricordata = {"titolari": tit_prima, "panchina": [g["id"] for g in prima["panchina"]]}
    f = consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, 200)
    assert {g["id"] for g in f["titolari"]} == set(tit_prima)              # tenuta
    righe = {r["titolare"]: r["frase"]["chiave"] for r in _scelta(f)}
    assert righe.get(7) == "scelta.stabile"
    assert all(isinstance(m.get("perche_scelta"), list) for liv in f["livelli"] for m in liv["moduli"])
    # dopo la scadenza la consigliata resta e basta: niente «per meno di 1 punto non cambia»
    chiusa = consigli.stabile(migliore, ricordata, nuove, _squadra(), SOLO_442, 200, chiusa=True)
    assert "scelta.stabile" not in {r["frase"]["chiave"] for r in _scelta(chiusa)}


# ------------------------------------------------------------------ web: la nota sotto il campo
APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
