"""Gli avvisi trovano la giornata da giocare con l'ora del giro (`adesso`), non con l'orologio vero (#566).

Qui la giornata la calcola davvero `consigli.prossima_giornata` (il finto delle altre prove è tolto) e le date sono fisse e già
passate: la giornata 9 si gioca il 28 e il 29/10/2026. Se un avviso chiedesse la giornata all'orologio vero, dopo quei giorni non
troverebbe più niente da giocare e tacerebbe: queste prove diventerebbero rosse da sole, con il passare del tempo."""
from datetime import datetime

from fanta import avvisi_utenti, consigli, notifiche
from fanta.regole import Regole

import test_copertura as tc
from test_avvisi_utenti import ADESSO, mondo, nuovo, registro  # noqa: F401  (mondo e registro = fixture)
from test_avviso_scadenza import BASE, Finto, _cambi_ha_visto, _giro, ore
from test_notifiche import ROSE, _db, _finto

PROSSIMA_VERA = consigli.prossima_giornata          # presa all'import, prima di ogni finto


def _giornata_vera(monkeypatch):
    """Toglie il finto di `prossima_giornata` messo dalla preparazione della prova: da qui la giornata si calcola davvero."""
    assert PROSSIMA_VERA.__module__ == "fanta.consigli" and PROSSIMA_VERA.__name__ == "prossima_giornata"
    monkeypatch.setattr(consigli, "prossima_giornata", PROSSIMA_VERA)


def test_la_giornata_si_calcola_davvero_con_l_ora_data():
    db = _db("2026-10-28 18:30")
    assert consigli.giornata_da_giocare(db, tc.ST, Regole(), ADESSO) == 9
    assert consigli.giornata_da_giocare(db, tc.ST, Regole(), datetime(2026, 11, 30, 12, 0)) is None   # a fine novembre è finita


def test_cambi(mondo, registro, monkeypatch):  # noqa: F811
    _giornata_vera(monkeypatch)
    nuovo("amico1", (1, "Castro"))
    avvisi_utenti.esegui("cambi", mondo.db, ADESSO)                    # primo controllo: solo memorizza
    mondo.prev.loc[1, ["stato", "percentuale"]] = ["panchina", 30.0]
    esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, ADESSO)
    assert errori == {} and esiti["amico1"]
    assert [testo for _, _, testo in registro.web] == [
        "Castro parte dalla panchina: con la tua rosa non si forma più una squadra. La formazione si chiude il 28/10 alle 18:30."]


def test_copertura(tmp_path, monkeypatch):
    rose, mandati, manda = tc._scena(monkeypatch, tc._con(tc._base(), "P", 2))
    _giornata_vera(monkeypatch)
    assert notifiche.copertura(tc._db(), Regole(), rose, tc.ADESSO, tmp_path / "n.json", manda, {})
    assert len(mandati) == 1 and "1 portiere disponibile" in mandati[0][1]


def test_promemoria(tmp_path, monkeypatch):
    _finto(monkeypatch)
    _giornata_vera(monkeypatch)
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x", **k: mandati.append(testo) or True    # noqa: E731
    opz = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
    righe = notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "p.json", manda, opz)
    assert len(righe) == 1 and mandati == righe and "18:30" in righe[0]                 # 55 minuti prima: quello dell'ora


def test_avviso_cambia_la_formazione(tmp_path, monkeypatch):
    m = Finto(monkeypatch, _db("2026-10-28 18:30"))
    _giornata_vera(monkeypatch)
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    assert _giro(m, tmp_path, ore(16, 0)) == ([], [])                      # lontano dalla scadenza: si ricorda la consigliata
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    righe, mandati = _giro(m, tmp_path, ore(17, 50))                        # 40 minuti prima: Castoldi fuori, entra Bonvicini
    assert len(mandati) == 1 and righe == [mandati[0][1]]
    assert mandati[0][1].startswith("Castoldi è infortunato: metti Bonvicini")
