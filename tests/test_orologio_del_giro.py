"""Momento libero, pianificatore e avvisi usano l'ora che ricevono (`adesso`), non l'orologio vero (#571, seguito di #565 e #566).

Le date delle prove sono fisse e già passate, e la giornata la calcola davvero `consigli.prossima_giornata` (nessun finto della
giornata). Previsioni, consigliata e valutazione sono finte (il calcolo vero è lungo) ma chiedono la giornata come le vere: senza,
la cercano con l'orologio vero. Se un avviso non passasse la sua giornata (e la sua ora), passati quei giorni non troverebbe più
niente da giocare e tacerebbe: queste prove diventerebbero rosse da sole, con il passare del tempo."""
from datetime import datetime

import pandas as pd

from fanta import consigli, libero, notifiche, pianificatore, regole, scelte
from fanta.regole import Regole

import test_copertura as tc
import test_libero as tl
import test_pianificatore as tp
from test_avviso_scadenza import BASE, Finto, _cambi_ha_visto, _giro, ore
from test_notifiche import ROSE, ST, _db

PROSSIMA_VERA = consigli.prossima_giornata              # prese all'import, prima di ogni finto
GIORNATA_VERA = consigli.giornata_da_giocare


class Calcoli:
    """`consigli.previsioni`, `formazione` e `valuta` finte. Come le vere, senza giornata la cercano con l'orologio vero (e senza
    calendario si fermano). Ricordano con quale giornata e quale ora le chiede l'avviso, in `chieste`."""

    def __init__(self, monkeypatch, prev, formazione=None, valuta=None):
        self.prev, self.chieste = prev, set()
        self._formazione, self._valuta = formazione, valuta
        monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
        monkeypatch.setattr(consigli, "prossima_giornata", PROSSIMA_VERA)     # toglie il finto di chi ha preparato la scena
        monkeypatch.setattr(consigli, "previsioni", self.previsioni)
        monkeypatch.setattr(consigli, "formazione", self.formazione)
        monkeypatch.setattr(consigli, "valuta", self.valuta)

    def _giornata(self, nome, db, r, giornata, adesso=None):
        self.chieste.add((nome, giornata, adesso))
        g = giornata or GIORNATA_VERA(db, consigli.stagione_corrente(), r)
        if g is None:
            raise ValueError(consigli.SENZA_CALENDARIO)
        return g

    def previsioni(self, db, r, giornata=None):
        return self.prev, self._giornata("previsioni", db, r, giornata), True

    def formazione(self, db, r, rose, nome_squadra=None, giornata=None, simulazioni=600, adesso=None):
        self._giornata("formazione", db, r, giornata, adesso)
        return self._formazione(db, r, rose)

    def valuta(self, db, r, rose, titolari, nome_squadra=None, giornata=None, simulazioni=600, adesso=None):
        self._giornata("valuta", db, r, giornata, adesso)
        return self._valuta(db, r, rose, titolari)


def _registro():
    mandati = []
    return mandati, lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo)) or True


# ---------------------------------------------------------------- momento libero e pianificatore
def test_momento_libero_nell_ora_prima_della_scadenza(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: tl.ST)
    # giornata 11: prima partita sabato 7/11 alle 15:00, scadenza 30 minuti prima = 14:30; dalle 13:30 non si installa
    assert libero.motivo(tl._db(), [tl._lega(30)], tl.H(7, 13, 0)) is None
    assert libero.motivo(tl._db(), [tl._lega(30)], tl.H(7, 14, 0)) == "scadenza della formazione alle 14:30"


def test_pianificatore_giro_a_un_ora_dalla_scadenza(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: tp.ST)
    lega = regole.imposta(Regole(), "scadenza_minuti", "10")      # giornata 10: prima partita sabato 7/11 alle 18:30, scadenza 18:20
    stato, letture = {}, []

    def giro(ora):
        return pianificatore.giro(ora, tp._db(), [lega], stato, lambda: letture.append(ora) or True, lambda: None)
    assert giro(tp.H(17, 15)) is None and letture == []
    assert giro(tp.H(17, 20)) == "60" and letture == [tp.H(17, 20)]
    assert stato["fatti"] == [f"{tp.ST}/10/10/60"]


# ---------------------------------------------------------------- avvisi (giornata 9: prima partita mercoledì 28/10 alle 18:30)
def test_cambi(tmp_path, monkeypatch):
    from test_notifiche import ROSE_DUE
    prev = pd.DataFrame([{"nome": "Castro", "stato": "titolare", "percentuale": 85.0, "dubbio": False},
                         {"nome": "Bonny", "stato": "titolare", "percentuale": 70.0, "dubbio": False}], index=[1, 2])
    c = Calcoli(monkeypatch, prev, formazione=lambda *a: {"modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [
        {"id": 1, "nome": "Castro"} if prev.at[1, "stato"] == "titolare" else {"id": 2, "nome": "Bonny"}]})
    mandati, manda = _registro()
    adesso, db, f = datetime(2026, 10, 27, 9, 0), _db("2026-10-28 18:30"), tmp_path / "c.json"
    assert notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda, {}, file_scelte=tmp_path / "s.json") == []   # solo memorizza
    prev.loc[1, "stato"] = "infortunato"               # la consigliata mette Bonny
    assert notifiche.cambi(db, Regole(), ROSE_DUE, adesso, f, manda, {}, file_scelte=tmp_path / "s.json") == [
        "Castro è infortunato: metti Bonny. La formazione si chiude il 28/10 alle 18:30."]
    assert [t for t, _ in mandati] == ["SchieraXI · cambia la formazione consigliata"]
    assert c.chieste == {("previsioni", 9, None), ("formazione", 9, adesso)}


def test_copertura(tmp_path, monkeypatch):
    prev, rose = tc._rosa(tc._con(tc._base(), "P", 2))
    c = Calcoli(monkeypatch, prev)
    mandati, manda = _registro()
    assert notifiche.copertura(tc._db(), Regole(), rose, tc.ADESSO, tmp_path / "n.json", manda, {})
    assert len(mandati) == 1 and "1 portiere disponibile" in mandati[0][1]
    assert c.chieste == {("previsioni", 9, None)}


def test_promemoria_di_un_ora(tmp_path, monkeypatch):
    c = Calcoli(monkeypatch, None, formazione=lambda *a: {
        "modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [{"id": 1, "nome": "Castro", "titolarita": "ballottaggio", "dubbio": False}]})
    mandati, manda = _registro()
    adesso = datetime(2026, 10, 28, 17, 35)                                      # 55 minuti prima
    righe = notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, adesso, tmp_path / "p.json", manda,
                                 {"promemoria_60": True}, tmp_path / "s.json")
    assert len(righe) == 1 and "18:30" in righe[0]
    assert "4-3-3" in righe[0] and "Castro" in righe[0]                         # i dettagli della consigliata ci sono
    assert c.chieste == {("formazione", 9, adesso)}


def test_avviso_cambia_la_formazione_salvata(tmp_path, monkeypatch):
    m = Finto(monkeypatch, _db("2026-10-28 18:30"))
    c = Calcoli(monkeypatch, m.prev, formazione=m.formazione, valuta=m.valuta)
    scelte.salva(ST, 9, BASE, "4-3-3", tmp_path / "scelte.json", tipo="consigliata")       # «ho schierato la consigliata»
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    righe, mandati = _giro(m, tmp_path, ore(17, 50))                         # 40 minuti prima: Castoldi fuori, entra Bonvicini
    assert len(mandati) == 1 and righe == [mandati[0][1]] and mandati[0][0] == "SchieraXI · cambia la formazione"
    assert mandati[0][1].startswith("Castoldi è infortunato: metti Bonvicini (+2,5 punti attesi).")
    assert c.chieste == {("previsioni", 9, None), ("formazione", 9, ore(17, 50)), ("valuta", 9, ore(17, 50))}
