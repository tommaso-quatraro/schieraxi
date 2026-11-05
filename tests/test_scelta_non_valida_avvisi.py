"""Una scelta salvata che non si può più schierare non conta: vale la consigliata (#321, dopo la #320).

La regola unica della scelta (`scelte.motivo_non_valida`, la stessa di Formazione, Oggi e Diario) vale anche per il promemoria,
l'avviso «cambia la formazione», il «cambio pronto», il riepilogo mandato dopo la giornata e «Da fare». Prima questi leggevano la
scelta così com'era e potevano parlare di una formazione che non vale (un giocatore ceduto, un modulo non ammesso).
Dati finti, file in cartelle temporanee, nessun invio vero."""
# ruff: noqa: F811  (le fixture importate da altri file di test arrivano come parametri con lo stesso nome: è il modo di pytest)
import json
from datetime import datetime

import pandas as pd
import pytest

from fanta import archivio, consigli, lega, notifiche, scelte
from fanta.regole import Regole
from test_avviso_scadenza import BASE, _cambi_ha_visto, m, ore  # noqa: F401  (m = fixture del «mondo» finto dell'avviso)
from test_avviso_scadenza import ROSE as ROSE_AVVISO
from test_da_fare import STAGIONE, mondo, vai  # noqa: F401  (mondo = fixture di «Da fare»)
from test_notifiche import ST, _db

NOMI = {1: "Ferri", 2: "Gallo", 3: "Lenti", 4: "Moro", 5: "Neri", 6: "Orsi", 7: "Pace", 8: "Riva", 9: "Sala", 10: "Tosi",
        11: "Villa", 12: "Zeni", 13: "Bassi", 14: "Conti", 15: "Dini"}
RUOLI = {1: "P", 2: "D", 3: "D", 4: "D", 5: "D", 6: "C", 7: "C", 8: "C", 9: "C", 10: "A", 11: "A", 12: "P", 13: "D", 14: "C",
         15: "A"}
ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, RUOLI[i], "COM", 5) for i, n in NOMI.items()])], "Mia")
TITOLARI = list(range(1, 12))                                   # 4-4-2
CEDUTO = 99                                                     # era in rosa quando l'utente ha salvato, poi è stato ceduto
CON_CEDUTO = TITOLARI[:10] + [CEDUTO]
DUE_PORTIERI = [1, 12, 2, 3, 4, 6, 7, 8, 9, 10, 11]             # Ferri e Zeni insieme: 3-4-2 con due portieri
NON_VALIDE = pytest.mark.parametrize("salvata", [CON_CEDUTO, DUE_PORTIERI], ids=["giocatore-ceduto", "modulo-non-ammesso"])
OPZ = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
CHIUSURA = "2026-10-28 18:30"                                   # la formazione della giornata 9 si chiude alle 18:30


def _registro():
    mandati = []
    return mandati, lambda titolo, testo, priorita=3, tag="x": mandati.append((str(titolo), str(testo))) or True   # noqa: E731


def _prima_della_scadenza(monkeypatch, consigliata=TITOLARI) -> pd.DataFrame:
    """Giornata 9 da giocare: previsioni di tutta la rosa (tutti titolari sicuri) e la consigliata `consigliata`."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    prev = pd.DataFrame([{"nome": NOMI[i], "ruolo": RUOLI[i], "stato": "titolare", "percentuale": 90.0, "dubbio": False,
                          "p_voto": 0.95, "atteso": 6.0} for i in NOMI], index=list(NOMI))
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    panchina = [i for i in NOMI if i not in consigliata]
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-4-2", "punteggio_atteso": 71.2,
        "titolari": [{"id": i, "nome": NOMI[i], "titolarita": "titolare", "dubbio": False} for i in consigliata],
        "panchina": [{"id": i, "nome": NOMI[i]} for i in panchina]})
    return prev


# ---------------------------------------------------------------- la regola: chi si può schierare e quale scelta vale
def test_ruoli_di_chi_si_puo_schierare():
    prev = pd.DataFrame({"ruolo": ["P", "D"]}, index=[1, 6])       # per le previsioni Orsi (6) è un difensore; gli altri senza
    assert scelte.ruoli_schierabili(ROSE, prev) == {1: "P", 6: "D"}  # come la Formazione: chi ha una previsione, con il suo ruolo
    assert scelte.ruoli_schierabili(ROSE) == RUOLI                   # giornata finita, senza previsioni: tutta la rosa, come il Diario
    assert scelte.ruoli_schierabili(lega.Rose([], None)) == {}       # nessuna squadra indicata


def test_la_scelta_che_vale():
    valida = {"titolari": TITOLARI, "tipo": "manuale"}
    assert scelte.che_vale(valida, RUOLI, Regole()) is valida
    assert scelte.che_vale({"titolari": CON_CEDUTO}, RUOLI, Regole()) is None
    assert scelte.che_vale({"titolari": DUE_PORTIERI}, RUOLI, Regole()) is None
    assert scelte.che_vale(valida, RUOLI, Regole(moduli=["4-3-3"])) is None     # la lega ha tolto il 4-4-2
    assert scelte.che_vale(None, RUOLI, Regole()) is None


# ---------------------------------------------------------------- promemoria prima della scadenza
@NON_VALIDE
def test_promemoria_parte_anche_con_la_scelta_non_valida(tmp_path, monkeypatch, salvata):
    """Prima: «hai già schierato» e il promemoria taceva. Ora la scelta non conta: il promemoria parte come senza scelta, ma con la
    frase propria (#331, vedi test_riepilogo_istantanea.py): «quella che hai salvato non è più valida»."""
    _prima_della_scadenza(monkeypatch)
    fs = tmp_path / "scelte.json"
    mandati, manda = _registro()
    scelte.salva(ST, 9, TITOLARI, "4-4-2", fs)
    assert notifiche.promemoria(_db(CHIUSURA), Regole(), ROSE, ore(17, 35), tmp_path / "a.json", manda, OPZ, fs) == []   # a posto
    scelte.salva(ST, 9, salvata, "4-4-2", fs)
    assert len(notifiche.promemoria(_db(CHIUSURA), Regole(), ROSE, ore(17, 35), tmp_path / "b.json", manda, OPZ, fs)) == 1
    assert mandati[0][0] == "SchieraXI · formazione tra un'ora"
    assert mandati[0][1].startswith("La formazione della giornata 9 si chiude tra circa un'ora (scadenza alle 18:30), ma quella che hai salvato non è più valida")


# ---------------------------------------------------------------- avviso «cambia la formazione»
@pytest.mark.parametrize("salvata, regole_lega", [(BASE[:10] + [CEDUTO], Regole()), (BASE, Regole(moduli=["3-4-3", "4-4-2"]))],
                         ids=["giocatore-ceduto", "modulo-tolto-dalla-lega"])
def test_avviso_scadenza_confronta_con_la_consigliata(m, tmp_path, salvata, regole_lega):
    """Prima: con il giocatore ceduto l'avviso non partiva mai (il confronto con la scelta falliva); con il modulo tolto dalla lega
    diceva «cambia la formazione» confrontando una formazione che non vale. Ora è come senza scelta: si confronta la consigliata."""
    fs = tmp_path / "scelte.json"
    scelte.salva(ST, 9, salvata, "4-3-3", fs)
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    mandati, manda = _registro()

    def giro(quando):
        return notifiche.avviso_scadenza(m.db, regole_lega, ROSE_AVVISO, quando, tmp_path / "prom.json", manda, {"avviso_prima": 60},
                                         fs, tmp_path / "cambi.json")
    assert giro(ore(16, 0)) == []                                          # lontano dalla scadenza: si ricorda la consigliata
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert len(giro(ore(17, 35))) == 1
    assert mandati == [("SchieraXI · cambia la formazione consigliata",
                        "Castoldi è infortunato: metti Bonvicini (+2,5 punti attesi). La formazione si chiude alle 18:30.")]


# ---------------------------------------------------------------- «cambio pronto»
def _schede(monkeypatch):
    monkeypatch.setattr(consigli, "scheda_previsione", lambda i, x: {
        "id": int(i), "nome": x["nome"], "ruolo": x["ruolo"], "stato": x["stato"], "dubbio": bool(x["dubbio"]),
        "p_voto": float(x["p_voto"]), "punti_attesi": float(x["atteso"])})


@NON_VALIDE
def test_cambio_pronto_guarda_i_titolari_della_consigliata(tmp_path, monkeypatch, salvata):
    """Tosi (10) è infortunato e la consigliata l'ha già tolto (gioca Dini). Con la scelta valida, che lo tiene, il «cambio pronto»
    lo dice; con una scelta che non vale (prima: «Il tuo Tosi è infortunato. Meglio Dini» su una formazione che non conta) no:
    vale la consigliata, e lì Tosi non c'è."""
    prev = _prima_della_scadenza(monkeypatch, consigliata=[1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 15])
    prev.loc[10, ["stato", "p_voto", "atteso"]] = ["infortunato", 0.0, 1.0]
    _schede(monkeypatch)
    fs, adesso = tmp_path / "scelte.json", datetime(2026, 10, 27, 9, 0)
    mandati, manda = _registro()
    scelte.salva(ST, 9, TITOLARI, "4-4-2", fs)
    notifiche.cambi(_db(CHIUSURA), Regole(), ROSE, adesso, tmp_path / "a.json", manda, file_scelte=fs)
    assert [t for t, _ in mandati] == ["SchieraXI · cambio pronto"] and "Il tuo Tosi è infortunato. Meglio Dini" in mandati[0][1]
    scelte.salva(ST, 9, salvata, "4-4-2", fs)
    notifiche.cambi(_db(CHIUSURA), Regole(), ROSE, adesso, tmp_path / "b.json", manda, file_scelte=fs)
    assert len(mandati) == 1


# ---------------------------------------------------------------- riepilogo dopo la giornata
SCELTA_8 = [1, 3, 4, 5, 6, 8, 9, 10, 13, 14, 15]                 # 4-3-3 (vedi _giornata_8_finita)
CONSIGLIATA_8 = [1, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14]            # 4-4-2


def _giornata_8_finita(tmp_path, monkeypatch):
    """Come `test_notifiche.test_riepilogo_a_giornata_finita`: giornata 8 giocata, voti arrivati, la 9 da giocare.
    Rosa: 1-2 portieri, 3-7 difensori, 8-12 centrocampisti, 13-16 attaccanti."""
    db = archivio.apri(tmp_path / "t.sqlite")
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (1, ?, 8, '2026-10-20 18:00', 'a', 'b', 1)", (ST,))
    db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (2, ?, 9, '2026-10-28 18:30', 'a', 'b', 0)", (ST,))
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    righe = [("P1", "P"), ("P2", "P")] + [(f"D{i}", "D") for i in range(5)] + [(f"C{i}", "C") for i in range(5)] + [(f"A{i}", "A") for i in range(4)]
    prev = pd.DataFrame([{"nome": n, "ruolo": r, "p_voto": 0.9, "mu": 6.5, "mu_voto": 6.0} for n, r in righe], index=range(1, len(righe) + 1))
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, giornata or 9, True))
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], "X", 1) for i in prev.index])], "Mia")
    for i in range(1, 71):
        ruolo = prev.at[i, "ruolo"] if i in prev.index else "C"
        db.execute("INSERT INTO voti (stagione, giornata, calciatore_id, nome, squadra, ruolo, voto_red, gol, gol_subiti, autogol, rig_segnati, rig_sbagliati, "
                   "rig_parati, assist, mvp, ammonizioni, espulsioni, subentrato, sostituito) VALUES (?, 8, ?, 'x', 'a', ?, 6.0, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)",
                   (ST, i, ruolo, 1 if i == 13 else 0))
    return db, rose


@pytest.mark.parametrize("salvata", [SCELTA_8[:10] + [CEDUTO], [1, 2, 3, 4, 5, 8, 9, 10, 13, 14, 15]],
                         ids=["giocatore-ceduto", "modulo-non-ammesso"])
def test_riepilogo_della_consigliata(tmp_path, monkeypatch, salvata):
    """Prima: con il giocatore ceduto niente riepilogo, con due portieri «la tua scelta salvata ha fatto…». Ora vale la consigliata
    (l'ultima vista dall'avviso dei cambi prima della scadenza), come per chi non ha salvato niente."""
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    fs, cambi_visti = tmp_path / "scelte.json", tmp_path / "cambi.json"
    scelte.salva(ST, 8, salvata, "4-3-3", fs)
    cambi_visti.write_text(json.dumps({"cambi": {f"{ST}/8": {"titolari": CONSIGLIATA_8}}}), encoding="utf-8")
    mandati, manda = _registro()
    adesso, opz = datetime(2026, 10, 21, 8, 0), {"riepilogo": True}
    r = notifiche.riepilogo(db, Regole(), rose, adesso, tmp_path / "r.json", manda, opz, cambi_visti, fs)
    assert len(r) == 1 and str(r[0]).startswith("Giornata 8: la formazione consigliata ha fatto circa")
    # senza sapere quale consigliata c'era non si manda niente: mai il riepilogo di una formazione che non vale
    assert notifiche.riepilogo(db, Regole(), rose, adesso, tmp_path / "r2.json", manda, opz, tmp_path / "nessun-cambio.json", fs) == []
    assert len(mandati) == 1


# ---------------------------------------------------------------- «Da fare» di Oggi
# Nel `mondo` di Da fare i titolari consigliati 1-11 sono un 3-5-2, Rossi (5) è in dubbio, Bianchi (6) infortunato.
# Le due scelte qui sotto lasciano fuori Rossi e Bianchi: una ha un giocatore ceduto, l'altra un modulo che la lega ha tolto
# (la consigliata finta del `mondo` non si ricalcola con le regole: conta solo quali titolari guarda Da fare).
DA_FARE_NON_VALIDE = pytest.mark.parametrize("salvata, regole_lega", [
    ([1, 2, 3, 4, 7, 8, 9, 10, 11, 12, CEDUTO], Regole()),
    ([1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 14], Regole(moduli=["4-4-2", "4-3-3"])),
], ids=["giocatore-ceduto", "modulo-tolto-dalla-lega"])


@DA_FARE_NON_VALIDE
def test_da_fare_dubbi_sui_titolari_della_consigliata(mondo, salvata, regole_lega):
    """Prima i dubbi guardavano la scelta che non vale (senza Rossi e Bianchi): nessuna voce. Ora guardano la consigliata."""
    scelte.salva(STAGIONE, 9, salvata, "3-5-2", mondo.ctx.scelte)
    assert [x["id"] for x in vai(mondo, regole=regole_lega) if x["tipo"] == "dubbio"] == ["dubbio:6", "dubbio:5"]


@DA_FARE_NON_VALIDE
def test_da_fare_formazione_da_fare_vicino_alla_scadenza(mondo, salvata, regole_lega):
    """Prima la voce «la formazione si chiude tra…» spariva perché c'era una scelta salvata, anche se non vale."""
    mondo.oggi["ore_mancanti"] = 2.0
    scelte.salva(STAGIONE, 9, salvata, "3-5-2", mondo.ctx.scelte)
    f = [x for x in vai(mondo, regole=regole_lega) if x["tipo"] == "formazione"]
    assert len(f) == 1 and f[0]["priorita"] == 1 and "2 ore" in f[0]["testo"]


@DA_FARE_NON_VALIDE
def test_da_fare_diario_chiede_come_senza_scelta(mondo, salvata, regole_lega):
    """Giornata 8 finita con una scelta che non vale: il Diario conta la consigliata, quindi Da fare chiede se l'hai schierata,
    come per chi non ha salvato niente (prima la scelta salvata bastava a non chiedere)."""
    mondo.db.execute("INSERT INTO partite VALUES (?, 8, '2026-10-20 18:00', 1)", (STAGIONE,))
    scelte.salva(STAGIONE, 8, salvata, "3-5-2", mondo.ctx.scelte)
    assert [x["giornata"] for x in vai(mondo, regole=regole_lega) if x["tipo"] == "diario"] == [8]
