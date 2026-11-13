"""Avviso intelligente prima della scadenza: «cambia la formazione» solo se le ultime probabili cambiano il consiglio.

Orari simulati (la formazione si chiude il 28/10 alle 18:30), archivio in memoria, consigliata e valutazioni finte: il test decide
quanto vale ogni formazione. Le notifiche vere non partono mai (registri in memoria)."""
import json
from datetime import datetime

import pandas as pd
import pytest

from fanta import avvisi_utenti, consigli, lega, notifiche, regole, scelte
from fanta.regole import Regole

from test_avvisi_utenti import mondo, nuovo, registro  # noqa: F401  (fixture)
from test_notifiche import ST, _db

NOMI = {1: "Ferraglia", 2: "Lunardi", 3: "Spadoni", 4: "Moretto", 5: "Calvani", 6: "Brugnoli", 7: "Pellizza", 8: "Sartano",
        9: "Lombrici", 10: "Kerani", 11: "Castoldi", 12: "Bonvicini", 13: "Attanasi", 14: "Rovelli"}
BASE = list(range(1, 12))                         # gli 11 consigliati all'inizio: un 4-3-3 che si può schierare
RUOLI = {1: "P", 2: "D", 3: "D", 4: "D", 5: "D", 6: "C", 7: "C", 8: "C", 9: "A", 10: "A", 11: "A", 12: "A", 13: "A", 14: "A"}
ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, RUOLI[i], "ROM", 10) for i, n in NOMI.items()])], "Mia")
GIORNO = (2026, 10, 28)


def ore(h, m):
    return datetime(*GIORNO, h, m)


class Finto:
    """Il «mondo» del modello: chi è consigliato, quanto vale ogni giocatore, lo stato nelle probabili."""

    def __init__(self, monkeypatch, db):
        self.db, self.titolari, self.modulo, self.calcoli = db, list(BASE), "4-3-3", 0
        self.bonus: dict[int, float] = {}
        self.moduli: dict[frozenset, str] = {}
        self.prev = pd.DataFrame({"nome": list(NOMI.values()), "ruolo": [RUOLI[i] for i in NOMI], "stato": "titolare",
                                  "percentuale": 80.0, "dubbio": False}, index=list(NOMI))
        db.execute("CREATE TABLE aggiornamenti (cosa TEXT PRIMARY KEY, quando TEXT, dettaglio TEXT)")   # come in archivio.py
        db.execute("INSERT INTO aggiornamenti (cosa, quando) VALUES ('probabili', 'v0')")
        monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
        monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
        monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (self.prev, 9, True))
        monkeypatch.setattr(consigli, "formazione", self.formazione)
        monkeypatch.setattr(consigli, "valuta", self.valuta)

    def valore(self, ids) -> float:
        return round(70.0 + sum(self.bonus.get(int(i), 0.0) for i in ids), 1)

    def formazione(self, db, regole, rose, *a, **k):
        self.calcoli += 1
        return {"modulo": self.modulo, "punteggio_atteso": self.valore(self.titolari),
                "titolari": [{"id": i, "nome": NOMI[i]} for i in self.titolari]}

    def valuta(self, db, regole, rose, titolari, *a, **k):
        if any(int(i) not in NOMI for i in titolari):
            raise ValueError("Servono 11 titolari diversi, tutti della rosa")
        return {"modulo": self.moduli.get(frozenset(int(i) for i in titolari), "4-3-3"), "punteggio_atteso": self.valore(titolari)}

    def cambia(self, versione, esce=None, entra=None, stato=None, bonus=None, modulo=None):
        """Nuove probabili: `esce` lascia il posto a `entra` nella consigliata, con lo stato e i valori nuovi."""
        self.db.execute("INSERT OR REPLACE INTO aggiornamenti (cosa, quando) VALUES ('probabili', ?)", (versione,))
        if stato:
            for i, s in stato.items():
                self.prev.at[i, "stato"] = s
        self.bonus |= bonus or {}
        if esce:
            self.moduli.setdefault(frozenset(self.titolari), self.modulo)
            self.titolari = [entra if i == esce else i for i in self.titolari]
        if modulo:
            self.modulo = modulo
            self.moduli[frozenset(self.titolari)] = modulo


@pytest.fixture
def m(monkeypatch):
    return Finto(monkeypatch, _db("2026-10-28 18:30"))


def _cambi_ha_visto(file_cambi, titolari):
    """Quello che l'avviso dei cambi ricorda dopo ogni aggiornamento: la consigliata del momento."""
    file_cambi.write_text(json.dumps({"cambi": {f"{ST}/9": {"titolari": sorted(titolari)}}}), encoding="utf-8")


def _giro(m, tmp_path, quando, opz=None, file_scelte=None):
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo, priorita, tag)) or True   # noqa: E731
    opz = {"avviso_prima": 60} if opz is None else opz
    righe = notifiche.avviso_scadenza(m.db, Regole(), ROSE, quando, tmp_path / "prom.json", manda, opz,
                                      file_scelte or tmp_path / "scelte.json", tmp_path / "cambi.json")
    return righe, mandati


def test_probabili_che_cambiano_a_70_40_e_10_minuti(m, tmp_path):
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    assert _giro(m, tmp_path, ore(16, 0)) == ([], [])                      # lontano dalla scadenza: si ricorda la consigliata
    # 70 minuti prima: Castoldi infortunato, entra Bonvicini. La finestra (60 minuti) non è ancora aperta: diventa il riferimento
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    _cambi_ha_visto(tmp_path / "cambi.json", m.titolari)
    assert _giro(m, tmp_path, ore(17, 20)) == ([], [])
    assert _giro(m, tmp_path, ore(17, 30)) == ([], [])                     # finestra aperta, niente di nuovo
    # 40 minuti prima: Bonvicini parte dalla panchina, conviene Attanasi e un altro modulo
    m.cambia("v2", esce=12, entra=13, stato={12: "panchina"}, bonus={12: -2.0}, modulo="3-4-3")
    righe, mandati = _giro(m, tmp_path, ore(17, 50))
    assert mandati == [("SchieraXI · cambia la formazione consigliata",
                        "Bonvicini parte dalla panchina: metti Attanasi e passa al 3-4-3 (+2,0 punti attesi). La formazione si chiude alle 18:30.",
                        4, "rotating_light")]                              # tag dei cambi: il tocco apre la Formazione
    assert righe == [mandati[0][1]]
    calcoli = m.calcoli
    assert _giro(m, tmp_path, ore(18, 0)) == ([], []) and m.calcoli == calcoli   # dati uguali: niente avviso e niente calcoli
    # 10 minuti prima: Kerani squalificato all'ultimo, entra Rovelli
    m.cambia("v3", esce=10, entra=14, stato={10: "squalificato"}, bonus={10: -3.0})
    righe, mandati = _giro(m, tmp_path, ore(18, 20))
    assert len(mandati) == 1 and mandati[0][1].startswith("Kerani è squalificato: metti Rovelli (+3,0 punti attesi).")
    # un terzo cambio importante: al massimo due avvisi per giornata
    m.cambia("v4", esce=9, entra=12, stato={9: "infortunato", 12: "titolare"}, bonus={9: -4.0, 12: 0.0})
    assert _giro(m, tmp_path, ore(18, 24)) == ([], [])
    assert _giro(m, tmp_path, ore(18, 31)) == ([], [])                     # formazione chiusa


def test_nessun_cambio_nessun_avviso(m, tmp_path):
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    for h, mi in ((16, 0), (17, 25), (17, 35), (18, 0), (18, 15), (18, 25)):
        m.cambia(f"v{h}{mi}")                                              # dati riletti, ma la consigliata non cambia
        assert _giro(m, tmp_path, ore(h, mi)) == ([], [])


def test_cambio_piccolo_sotto_soglia_non_disturba(m, tmp_path):
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    _giro(m, tmp_path, ore(17, 0))
    m.cambia("v1", esce=8, entra=14, bonus={8: -0.6})                       # conviene Rovelli, ma per 0,6 punti
    assert _giro(m, tmp_path, ore(17, 45)) == ([], [])
    m.cambia("v2", bonus={8: -1.4})                                         # ora la differenza è 1,4 punti: vale un avviso
    righe, mandati = _giro(m, tmp_path, ore(18, 0))
    assert len(mandati) == 1 and "Con le ultime probabili conviene Rovelli al posto di Sartano (+1,4 punti attesi)" in mandati[0][1]


def test_con_la_formazione_salvata_si_confronta_quella(m, tmp_path):
    scelte.salva(ST, 9, BASE, "4-3-3", tmp_path / "scelte.json", tipo="consigliata")      # «ho schierato la consigliata»
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    _cambi_ha_visto(tmp_path / "cambi.json", m.titolari)                   # la consigliata è già cambiata prima della finestra...
    assert _giro(m, tmp_path, ore(17, 20)) == ([], [])
    righe, mandati = _giro(m, tmp_path, ore(17, 35))                        # ...ma tu avevi schierato Castoldi: si avvisa
    assert mandati[0][0] == "SchieraXI · cambia la formazione"
    assert mandati[0][1].startswith("Castoldi è infortunato: metti Bonvicini (+2,5 punti attesi).")
    m.cambia("v2")
    assert _giro(m, tmp_path, ore(17, 55)) == ([], [])                     # lo stesso consiglio non si ripete


def test_ore_tranquille_rimandano_l_avviso(m, tmp_path):
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    opz = {"avviso_prima": 90, "silenzio": True, "silenzio_da": 17, "silenzio_a": 18}
    _giro(m, tmp_path, ore(16, 50), opz)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert _giro(m, tmp_path, ore(17, 30), opz) == ([], [])                # nelle ore tranquille niente
    righe, mandati = _giro(m, tmp_path, ore(18, 5), opz)                    # finite: l'avviso parte
    assert len(mandati) == 1 and "Castoldi è infortunato" in mandati[0][1]


def test_valori_dell_impostazione(m, tmp_path):
    """`avviso_prima` si legge e si salva ancora (l'iPhone di oggi lo mostra), ma l'avviso parte un'ora prima per tutti (#676,
    test_avvisi_solo_due.py)."""
    f = tmp_path / "av.json"
    assert notifiche.impostazioni(f)["avviso_prima"] == 60                 # di base: un'ora prima
    assert notifiche.salva_impostazioni({"avviso_prima": 30}, f)["avviso_prima"] == 30
    for strano in (45, True, "x", -30, None):
        assert notifiche.salva_impostazioni({"avviso_prima": strano}, f)["avviso_prima"] == 30   # valori strani: resta quello di prima
    assert notifiche.salva_impostazioni({"cambi": False}, f)["avviso_prima"] == 30              # chi non lo manda non lo azzera


def test_dopo_l_avviso_il_promemoria_della_stessa_finestra_non_fa_il_doppione(m, tmp_path):
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    _giro(m, tmp_path, ore(17, 0))
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert len(_giro(m, tmp_path, ore(17, 35))[1]) == 1
    mandati = []
    manda = lambda *a, **k: mandati.append(a) or True                       # noqa: E731
    opz = {"promemoria_60": True, "promemoria_15": True}
    assert notifiche.promemoria(m.db, Regole(), ROSE, ore(17, 36), tmp_path / "prom.json", manda, opz, tmp_path / "scelte.json") == []
    assert notifiche.promemoria(m.db, Regole(), ROSE, ore(17, 50), tmp_path / "prom.json", manda, opz, tmp_path / "scelte.json") == []
    assert mandati == []
    assert len(notifiche.promemoria(m.db, Regole(), ROSE, ore(18, 20), tmp_path / "prom.json", manda, opz, tmp_path / "scelte.json")) == 1


def _cambi(m, tmp_path, quando, opz, mandati):
    """L'avviso dei cambi (stesso file di stato che legge l'avviso «cambia la formazione»)."""
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo)) or True   # noqa: E731
    return notifiche.cambi(m.db, Regole(), ROSE, quando, tmp_path / "cambi.json", manda, opz,
                           file_scelte=tmp_path / "scelte.json", file_promemoria=tmp_path / "prom.json")


def _avviso(m, tmp_path, quando, opz, mandati):
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo)) or True   # noqa: E731
    return notifiche.avviso_scadenza(m.db, Regole(), ROSE, quando, tmp_path / "prom.json", manda, opz, tmp_path / "scelte.json",
                                     tmp_path / "cambi.json")


def test_vicino_alla_scadenza_parla_solo_l_avviso_nuovo(m, tmp_path):
    opz, mandati = {"cambi": True, "avviso_prima": 60}, []
    _cambi(m, tmp_path, ore(16, 0), opz, mandati)                           # primo controllo: si ricorda lo stato
    _avviso(m, tmp_path, ore(16, 0), opz, mandati)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    righe = _cambi(m, tmp_path, ore(17, 45), opz, mandati)                  # nella finestra parte prima l'avviso nuovo...
    assert len(righe) == 1 and righe[0].startswith("Castoldi è infortunato: metti Bonvicini")
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"]   # ...e quello dei cambi tace
    assert _avviso(m, tmp_path, ore(17, 50), opz, mandati) == []           # il giro dei promemoria non lo ripete
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"]
    assert _cambi(m, tmp_path, ore(18, 0), opz, mandati) == [] and len(mandati) == 1    # e non riparte più tardi


def test_se_i_cambi_sono_appena_partiti_l_avviso_nuovo_non_ripete(m, tmp_path):
    opz, mandati = {}, []
    _cambi(m, tmp_path, ore(16, 0), opz, mandati)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert len(_cambi(m, tmp_path, ore(17, 28), opz, mandati)) == 1        # 62 minuti: finestra non ancora aperta, parlano i cambi
    assert _avviso(m, tmp_path, ore(17, 31), opz, mandati) == []           # 3 minuti dopo, stessa notizia: non si ripete
    assert _avviso(m, tmp_path, ore(17, 50), opz, mandati) == []           # né più tardi
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"]
    m.cambia("v2", esce=10, entra=14, stato={10: "squalificato"}, bonus={10: -3.0})       # una notizia nuova sì
    assert len(_cambi(m, tmp_path, ore(18, 0), opz, mandati)) == 1        # nella finestra parla l'avviso nuovo, i cambi tacciono
    assert "(+3,0 punti attesi)" in mandati[-1][1] and len(mandati) == 2
    assert _avviso(m, tmp_path, ore(18, 5), opz, mandati) == [] and len(mandati) == 2


def test_se_l_avviso_nuovo_non_parte_i_cambi_si_dicono(m, tmp_path):
    """Revisione: negli ultimi 60 minuti i cambi tacevano anche quando l'avviso «cambia la formazione» non partiva (già due
    avvisi, o guadagno sotto un punto): un terzo infortunio non lo diceva nessuno. Un cambio che non tocca la consigliata invece
    non si dice più (#676)."""
    opz, mandati = {}, []
    _cambi(m, tmp_path, ore(16, 0), opz, mandati)
    _avviso(m, tmp_path, ore(16, 0), opz, mandati)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert len(_cambi(m, tmp_path, ore(17, 40), opz, mandati)) == 1 and len(mandati) == 1     # primo avviso nuovo
    m.cambia("v2", esce=10, entra=14, stato={10: "squalificato"}, bonus={10: -3.0})
    assert len(_cambi(m, tmp_path, ore(17, 50), opz, mandati)) == 1 and len(mandati) == 2     # secondo (l'ultimo della giornata)
    # terzo infortunio 5 minuti dopo: l'avviso nuovo ha finito i suoi invii, quindi parla quello dei cambi
    m.cambia("v3", esce=9, entra=13, stato={9: "infortunato"}, bonus={9: -4.0})
    righe = _cambi(m, tmp_path, ore(17, 55), opz, mandati)
    assert righe == ["Lombrici è infortunato: metti Attanasi. La formazione si chiude il 28/10 alle 18:30."]
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"] * 3
    m.cambia("v4", stato={8: "panchina"}, bonus={8: -0.3})                 # la consigliata non cambia: niente
    assert _cambi(m, tmp_path, ore(18, 0), opz, mandati) == [] and len(mandati) == 3


def test_cambi_zittiti_solo_per_la_notizia_che_l_avviso_conosceva(m, tmp_path):
    opz, mandati = {}, []
    _cambi(m, tmp_path, ore(16, 0), opz, mandati)
    _avviso(m, tmp_path, ore(16, 0), opz, mandati)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert len(_avviso(m, tmp_path, ore(17, 40), opz, mandati)) == 1        # l'avviso nuovo parte dal giro dei promemoria
    assert _cambi(m, tmp_path, ore(17, 42), opz, mandati) == [] and len(mandati) == 1   # stessa notizia: i cambi tacciono
    m.cambia("v2", esce=7, entra=13, stato={7: "panchina"}, bonus={7: -0.5})            # 3 minuti dopo, dati nuovi: per meno di un punto
    righe = _cambi(m, tmp_path, ore(17, 45), opz, mandati)
    assert len(righe) == 1 and righe[0].startswith("Pellizza parte dalla panchina: metti Attanasi.")
    assert len(mandati) == 2


def test_piu_utenti_con_leghe_diverse(mondo, registro, monkeypatch):  # noqa: F811
    m = Finto(monkeypatch, mondo.db)
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda db, st, r, adesso=None: 9)
    a = nuovo("amico1", (1, "Ferraglia"))                                     # lega che chiude alla prima partita (18:30)
    b = nuovo("amico2", (2, "Lunardi"))                                  # lega che chiude un'ora prima (17:30)
    regole.salva(Regole(scadenza_minuti=60), b.regole)
    for ctx in (a, b):
        _cambi_ha_visto(ctx.stato_cambi, BASE)
    assert avvisi_utenti.esegui("promemoria", m.db, ore(15, 0)) == ({"amico1": [], "amico2": []}, {})
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    esiti, errori = avvisi_utenti.esegui("promemoria", m.db, ore(17, 0))
    assert errori == {} and esiti["amico1"] == [] and len(esiti["amico2"]) == 1      # solo B è nella sua finestra
    assert [(u, t) for u, t, _ in registro.web] == [(str(b.utente_id), "SchieraXI · cambia la formazione consigliata")]
    esiti, _ = avvisi_utenti.esegui("promemoria", m.db, ore(17, 35))
    assert len(esiti["amico1"]) == 1 and esiti["amico2"] == []             # ora A (55 minuti); per B la formazione è chiusa
    assert [u for u, _, _ in registro.web] == [str(b.utente_id), str(a.utente_id)]   # e niente promemoria doppione per A
    assert registro.ntfy == []                                              # gli utenti non passano mai dal canale del proprietario


def test_rotta_avvisi_legge_e_salva_l_impostazione(dati_isolati):
    from fastapi.testclient import TestClient

    from fanta import server
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/avvisi").json()["impostazioni"]["avviso_prima"] == 60
    assert c.put("/api/avvisi", json={"avviso_prima": 90}).json()["impostazioni"]["avviso_prima"] == 90
    r = c.put("/api/avvisi", json={"avviso_prima": 45})
    assert r.status_code == 422 and "avviso_prima" in json.dumps(r.json().get("campi"))
    assert c.put("/api/avvisi", json={"riepilogo": False}).json()["impostazioni"]["avviso_prima"] == 90   # app vecchie: non lo azzerano
    assert c.put("/api/avvisi", json={"avviso_prima": 0}).json()["impostazioni"]["avviso_prima"] == 0
