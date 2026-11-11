"""Anticipi già cominciati (#368, L5 di #166). Un anticipo (da 36 ore a 7 giorni prima del gruppo principale, turno.py) non fissa la
scadenza: la formazione resta aperta, ma nella lega i giocatori di quella partita non si possono più spostare. Nella consigliata
restano dove erano nella consigliata già mostrata (titolari, stesso posto in panchina, fuori); gli altri si spostano come sempre.
Rosa, squadre e numeri inventati."""
import json
import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from fanta import consigli, lega
from fanta.regole import Regole

SIM = 200
GIORNATA = 9
ST = "2026-27"
ANTICIPO = "ANT"          # la squadra di Serie A che gioca l'anticipo
# (id, ruolo, fantavoto atteso se gioca). Tutti giocano al 95%. Con il 4-4-2 e la panchina di sempre (7 posti, libera) la consigliata
# è: titolari 1, 4-7, 12-15, 20-21; panchina 8, 22, 16, 2, 9, 17, 23 (il 9 al quinto posto); fuori 3, 10, 11, 18, 19, 24, 25.
ROSA = ([(1, "P", 6.5), (2, "P", 5.0), (3, "P", 4.5)]
        + [(4, "D", 6.6), (5, "D", 6.5), (6, "D", 6.4), (7, "D", 6.3), (8, "D", 6.25), (9, "D", 5.0), (10, "D", 4.8), (11, "D", 4.6)]
        + [(12, "C", 7.0), (13, "C", 6.9), (14, "C", 6.8), (15, "C", 6.7), (16, "C", 5.2), (17, "C", 5.0), (18, "C", 4.8), (19, "C", 4.6)]
        + [(20, "A", 8.0), (21, "A", 7.8), (22, "A", 6.0), (23, "A", 5.0), (24, "A", 4.8), (25, "A", 4.6)])
# chi gioca l'anticipo: un titolare (7), uno in panchina (9, quinto posto) e uno fuori (25)
DELL_ANTICIPO = {7, 9, 25}
TITOLARI = {1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21}
PANCHINA = [8, 22, 16, 2, 9, 17, 23]
SOLO_442 = Regole(moduli=["4-4-2"])
GIU_E_INFORTUNATO = {7: {"mu": 3.0}, 13: {"stato": "infortunato", "p_voto": 0.0}}


@pytest.fixture(autouse=True)
def _schede_semplici(monkeypatch):
    """Le schede dei giocatori qui non contano: bastano id, nome, ruolo, punti attesi e titolarità."""
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "punti_attesi": round(float(x["p_voto"] * x["mu"]), 2),
        "titolarita": consigli.titolarita(x)})


def _prev(cambi: dict | None = None) -> pd.DataFrame:
    """Previsioni inventate della rosa, con la squadra di Serie A; `cambi` = {id: {colonna: valore}} per i ritocchi."""
    righe = {i: {"nome": f"Giocatore {i}", "ruolo": r, "squadra": ANTICIPO if i in DELL_ANTICIPO else f"S{i % 4}", "p_voto": 0.95,
                 "mu": mu, "mu_voto": 6.0, "stato": "titolare", "quota_titolare": 0.9} for i, r, mu in ROSA}
    for i, c in (cambi or {}).items():
        righe[int(i)].update(c)
    return pd.DataFrame.from_dict(righe, orient="index")


def _squadra() -> lega.Squadra:
    return lega.Squadra("Squadra Prova", [lega.GiocatoreRosa(i, f"Giocatore {i}", r, "AAA", 1) for i, r, _ in ROSA])


def _migliore(prev, regole=SOLO_442) -> dict:
    return consigli._calcola_formazione(_squadra(), prev, GIORNATA, True, regole, SIM)


def _ricordata(f: dict) -> dict:
    return {"titolari": [g["id"] for g in f["titolari"]], "panchina": [g["id"] for g in f["panchina"]]}


def _tit(f: dict) -> set[int]:
    return {g["id"] for g in f["titolari"]}


def _pan(f: dict) -> list[int]:
    return [g["id"] for g in f["panchina"]]


def _stabile(nuove, iniziate, regole=SOLO_442) -> tuple[dict, dict]:
    """(migliore con i dati nuovi, consigliata da mostrare) partendo dalla consigliata di sempre."""
    prima = _migliore(_prev(), regole)
    assert _tit(prima) == TITOLARI and _pan(prima) == PANCHINA            # il punto di partenza scritto sopra
    migliore = _migliore(nuove, regole)
    return migliore, consigli.stabile(migliore, _ricordata(prima), nuove, _squadra(), regole, SIM, iniziate=iniziate)


def test_titolare_dell_anticipo_resta_titolare_e_gli_altri_si_spostano():
    """Il 7 (anticipo) crolla e il 13 si infortuna: senza anticipo esce anche il 7; con l'anticipo cominciato il 7 resta e il 13
    lascia il posto al 16 come sempre."""
    nuove = _prev(GIU_E_INFORTUNATO)
    migliore, f = _stabile(nuove, {ANTICIPO})
    assert 7 not in _tit(migliore)                                         # da sola la migliore lo toglierebbe
    assert _tit(f) == {1, 4, 5, 6, 7, 12, 14, 15, 16, 20, 21}
    assert _pan(f)[4] == 9 and 25 not in _pan(f) and len(_pan(f)) == 7


def test_in_panchina_resta_in_panchina_allo_stesso_posto():
    """Il 9 (anticipo, quinto in panchina) diventa il difensore migliore: senza anticipo sarebbe titolare."""
    nuove = _prev({9: {"mu": 9.0}})
    migliore, f = _stabile(nuove, {ANTICIPO})
    assert 9 in _tit(migliore)
    assert _tit(f) == TITOLARI
    assert _pan(f) == [8, 22, 16, 2, 9, 17, 23]          # gli altri posti: la panchina di sempre fra chi si può ancora spostare


def test_fuori_resta_fuori():
    nuove = _prev({25: {"mu": 12.0}})
    migliore, f = _stabile(nuove, {ANTICIPO})
    assert 25 in _tit(migliore)
    assert _tit(f) == TITOLARI and 25 not in _pan(f)
    assert 25 in {g["id"] for g in f["fuori"]}


def test_titolare_dell_anticipo_diventato_improbabile_resta():
    """Un titolare diventato improbabile di solito fa cambiare la consigliata (#335); se la sua partita è già cominciata no."""
    nuove = _prev({7: {"stato": "non_citato", "p_voto": 0.1}})
    migliore, f = _stabile(nuove, {ANTICIPO})
    assert 7 not in _tit(migliore)
    assert _tit(f) == TITOLARI


@pytest.mark.parametrize("iniziate", [(), {"ALTRA"}])
def test_senza_anticipi_della_rosa_nulla_cambia(iniziate):
    """Nessun anticipo cominciato, o cominciato ma senza giocatori della rosa: come prima, vale la migliore."""
    nuove = _prev(GIU_E_INFORTUNATO)
    migliore, f = _stabile(nuove, iniziate)
    assert f is migliore and 7 not in _tit(f)


def test_nessun_modulo_ne_stile_sposta_chi_gioca_l_anticipo():
    """Web e iPhone fanno scorrere i moduli e gli stili: in nessuno il 7 esce, il 9 lascia il suo posto o il 25 entra."""
    regole = Regole(moduli=["4-4-2", "3-4-3"])
    nuove = _prev({25: {"mu": 12.0}, 13: {"stato": "infortunato", "p_voto": 0.0}})
    migliore, f = _stabile(nuove, {ANTICIPO}, regole)
    assert 25 in _tit(migliore)
    formazioni = [(m["titolari"], m["panchina"]) for x in [f, *f["livelli"]] for m in x["moduli"]]
    formazioni.append(([g["id"] for g in f["titolari"]], _pan(f)))
    assert len(formazioni) > 3
    for titolari, panchina in formazioni:
        assert 7 in titolari and 25 not in titolari and 25 not in panchina and panchina.index(9) == 4
    assert 13 not in _tit(f)


def test_anche_con_la_consigliata_a_posto_gli_altri_moduli_non_lo_spostano():
    """Dati uguali: la consigliata (4-4-2) tiene già il 7, ma il miglior 3-4-3 lo lascerebbe fuori. Nemmeno quello può farlo."""
    regole = Regole(moduli=["4-4-2", "3-4-3"])
    migliore, f = _stabile(_prev(), {ANTICIPO}, regole)
    tre = next(m for m in migliore["moduli"] if m["modulo"] == "3-4-3")
    assert _tit(migliore) == TITOLARI and 7 not in tre["titolari"]
    assert _tit(f) == TITOLARI and f["modulo"] == "4-4-2"
    for x in [f, *f["livelli"]]:
        for m in x["moduli"]:
            assert 7 in m["titolari"] and m["panchina"].index(9) == 4


def test_panchina_con_i_posti_per_ruolo():
    """Panchina a posti fissi (2 P, 3 D, 3 C, 3 A, come la lega d'esempio): il 9 tiene il suo posto e uno dei 3 posti dei
    difensori; gli altri due vanno ai migliori difensori rimasti."""
    from fanta.regole import Panchina
    regole = Regole(moduli=["4-4-2"], panchina=Panchina(numero=11, tipo="per_ruolo", max_sostituzioni=5, cambio_modulo=False,
                                                        posti={"P": 2, "D": 3, "C": 3, "A": 3}))
    prima = _migliore(_prev(), regole)
    assert _pan(prima) == [2, 3, 8, 9, 10, 16, 17, 18, 22, 23, 24]
    nuove = _prev({9: {"mu": 9.0}, 10: {"mu": 3.0}})                       # il 10 scende: il suo posto va all'11
    f = consigli.stabile(_migliore(nuove, regole), _ricordata(prima), nuove, _squadra(), regole, SIM, iniziate={ANTICIPO})
    assert _tit(f) == TITOLARI
    assert _pan(f) == [2, 3, 8, 9, 11, 16, 17, 18, 22, 23, 24]


# ---------------------------------------------------------------- consigli.formazione: l'orario dell'anticipo
MARTEDI = datetime(2026, 11, 3, 12, 0)
MERCOLEDI_PRIMA = datetime(2026, 11, 4, 20, 0)          # l'anticipo comincia alle 20:45
GIOVEDI = datetime(2026, 11, 5, 12, 0)                  # anticipo giocato; la formazione si chiude sabato alle 15:00
CALENDARIO = ([("2026-11-04 20:45", ANTICIPO, "BBB")]
              + [(d, f"C{k}", f"T{k}") for k, d in enumerate(["2026-11-07 15:00", "2026-11-07 18:00", "2026-11-07 20:45",
                                                               "2026-11-08 12:30", "2026-11-08 15:00", "2026-11-08 15:00",
                                                               "2026-11-08 18:00", "2026-11-08 20:45", "2026-11-09 20:45"])])


@pytest.fixture
def mondo(monkeypatch, tmp_path):
    """La giornata 9 con un anticipo il mercoledì e il resto da sabato a lunedì; previsioni e ora le cambia il test."""
    monkeypatch.setattr(consigli, "FILE_CONSIGLIATE", tmp_path / "consigliate.json")
    stato = {"prev": _prev(), "versione": "v1", "adesso": MARTEDI}
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: GIORNATA)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (stato["prev"], GIORNATA, True))
    monkeypatch.setattr(consigli, "_versione", lambda db: stato["versione"])
    monkeypatch.setattr(consigli, "_adesso", lambda: stato["adesso"])
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?,?,0)", [(ST, GIORNATA, d, c, t) for d, c, t in CALENDARIO])
    stato["db"] = db
    consigli._cache.clear()
    yield stato
    consigli._cache.clear()


def _formazione(mondo, prev=None) -> dict:
    if prev is not None:                                   # dati nuovi: come un aggiornamento vero, cambia anche la versione
        mondo["prev"], mondo["versione"] = prev, mondo["versione"] + "+"
    return consigli.formazione(mondo["db"], SOLO_442, lega.Rose([_squadra()], "Squadra Prova"))


def test_dopo_l_inizio_dell_anticipo_i_suoi_giocatori_restano_anche_dopo_un_riavvio(mondo):
    prima = _formazione(mondo)
    assert _tit(prima) == TITOLARI and _pan(prima) == PANCHINA
    mondo["adesso"] = GIOVEDI
    dopo = _formazione(mondo, _prev(GIU_E_INFORTUNATO))
    assert _tit(dopo) == {1, 4, 5, 6, 7, 12, 14, 15, 16, 20, 21} and _pan(dopo)[4] == 9
    ricordata = next(iter(json.loads(consigli.FILE_CONSIGLIATE.read_text(encoding="utf-8")).values()))
    assert set(ricordata["titolari"]) == _tit(dopo) and ricordata["panchina"] == _pan(dopo)
    consigli._cache.clear()                                   # riavvio del servizio: la memoria si svuota, il file resta
    assert _tit(_formazione(mondo)) == _tit(dopo)


def test_con_gli_stessi_titolari_la_panchina_non_si_riordina_attorno_a_lui(mondo):
    """Il 9 (anticipo) sale ma non abbastanza per giocare: da solo passerebbe dal quinto al terzo posto in panchina."""
    _formazione(mondo)
    mondo["adesso"] = GIOVEDI
    nuove = _prev({9: {"mu": 5.5}})
    assert _pan(_migliore(nuove))[2] == 9 and _tit(_migliore(nuove)) == TITOLARI
    dopo = _formazione(mondo, nuove)
    assert _tit(dopo) == TITOLARI and _pan(dopo) == PANCHINA


def test_prima_che_l_anticipo_cominci_si_sposta_come_sempre(mondo):
    _formazione(mondo)
    mondo["adesso"] = MERCOLEDI_PRIMA
    assert 7 not in _tit(_formazione(mondo, _prev(GIU_E_INFORTUNATO)))


# ---------------------------------------------------------------- l'ora data, non l'orologio vero (#571)
# Gli avvisi chiedono la consigliata con l'ora del loro giro (`adesso`): nella risposta giornata, scadenza passata e anticipi
# cominciati si contano da lì. Ricordarla, cioè cambiare quella che l'app mostra, si può invece solo se lo permette anche l'ora
# vera: un giro partito prima della scadenza o di un anticipo non cambia mai la consigliata già fissata (#335, #368).
# Qui l'orologio vero è `mondo["adesso"]`, messo di proposito in un altro momento.
PROSSIMA_VERA = consigli.prossima_giornata              # presa all'import, prima di ogni finto
DOPO_LA_STAGIONE = datetime(2027, 3, 1, 12, 0)          # per l'orologio vero la formazione della giornata 9 è chiusa da mesi
GIRO_DI_SABATO = datetime(2026, 11, 7, 14, 59)          # un giro degli avvisi partito un minuto prima della scadenza (15:00)...
SABATO_DOPO = datetime(2026, 11, 7, 15, 1)              # ...che arriva a questa squadra quando la formazione è già chiusa
SQUADRA = lega.Rose([_squadra()], "Squadra Prova")
COL_7_FERMO = {1, 4, 5, 6, 7, 12, 14, 15, 16, 20, 21}    # anticipo giocato: il 7 resta, il 13 infortunato lascia il posto al 16


def _dati_nuovi(mondo):
    mondo["prev"], mondo["versione"] = _prev(GIU_E_INFORTUNATO), mondo["versione"] + "+"


def _app(mondo) -> set[int]:
    """I titolari della consigliata che l'app mostra adesso (ora vera)."""
    return _tit(consigli.formazione(mondo["db"], SOLO_442, SQUADRA))


def test_con_l_ora_data_la_formazione_e_ancora_aperta(mondo):
    assert _tit(consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MARTEDI)) == TITOLARI
    mondo["adesso"] = DOPO_LA_STAGIONE
    _dati_nuovi(mondo)
    # alle 20 di mercoledì la formazione è aperta e l'anticipo non è cominciato: nella risposta il 7 esce come sempre...
    assert 7 not in _tit(consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MERCOLEDI_PRIMA))
    assert _app(mondo) == TITOLARI                         # ...ma per l'ora vera è chiusa: quella mostrata resta


def test_con_l_ora_data_l_anticipo_e_gia_cominciato(mondo):
    consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MARTEDI)
    _dati_nuovi(mondo)                                     # per l'orologio vero è ancora martedì: nessun anticipo cominciato
    assert _tit(consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=GIOVEDI)) == COL_7_FERMO


def test_valuta_confronta_con_la_consigliata_dell_ora_data(mondo):
    consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MARTEDI)
    mondo["adesso"] = DOPO_LA_STAGIONE
    _dati_nuovi(mondo)
    chiusa = consigli.formazione(mondo["db"], SOLO_442, SQUADRA)["punteggio_atteso"]      # orologio vero: resta quella di martedì
    aperta = consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MERCOLEDI_PRIMA)["punteggio_atteso"]
    v = consigli.valuta(mondo["db"], SOLO_442, SQUADRA, sorted(TITOLARI), adesso=MERCOLEDI_PRIMA)
    assert aperta > chiusa and v["consigliata"] == aperta
    assert _app(mondo) == TITOLARI                         # risposte con l'ora data: quella mostrata non cambia


def test_un_giro_partito_prima_della_scadenza_non_cambia_la_consigliata_fissata(mondo):
    """Revisione di #576: il giro fissa la sua ora all'inizio; se arriva a una squadra dopo la scadenza, la consigliata già fissata
    (quella che l'app mostra a formazione chiusa) resta la stessa."""
    assert _app(mondo) == TITOLARI                         # martedì: mostrata
    mondo["adesso"] = SABATO_DOPO
    _dati_nuovi(mondo)
    assert _app(mondo) == TITOLARI                         # dopo la scadenza: fissata
    consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=GIRO_DI_SABATO)
    assert _app(mondo) == TITOLARI


def test_un_giro_partito_prima_dell_anticipo_non_sposta_chi_lo_gioca(mondo):
    assert _app(mondo) == TITOLARI                         # martedì: mostrata
    mondo["adesso"] = GIOVEDI                              # per l'ora vera l'anticipo è giocato
    _dati_nuovi(mondo)
    assert 7 not in _tit(consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MERCOLEDI_PRIMA))   # giro partito prima
    assert _app(mondo) == COL_7_FERMO                      # il 7 resta dove era nella consigliata mostrata


def test_senza_giornata_la_si_cerca_con_l_ora_data(mondo, monkeypatch):
    def previsioni(db, regole, giornata=None):             # come la vera: senza giornata la cerca con l'orologio vero
        giornata = giornata or consigli.giornata_da_giocare(db, ST, regole)
        if giornata is None:
            raise ValueError(consigli.SENZA_CALENDARIO)
        return mondo["prev"], giornata, True
    monkeypatch.setattr(consigli, "prossima_giornata", PROSSIMA_VERA)
    monkeypatch.setattr(consigli, "previsioni", previsioni)
    mondo["adesso"] = DOPO_LA_STAGIONE                     # per l'orologio vero non c'è più nessuna giornata da giocare
    assert consigli.formazione(mondo["db"], SOLO_442, SQUADRA, adesso=MARTEDI)["giornata"] == 9
    assert consigli.valuta(mondo["db"], SOLO_442, SQUADRA, sorted(TITOLARI), adesso=MARTEDI)["giornata"] == 9
