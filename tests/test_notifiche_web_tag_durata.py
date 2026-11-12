"""Notifiche web (#652): ogni avviso ha un tag suo, così il browser non sostituisce un avviso con il successivo (lo farebbe senza
suono); il tempo di vita dipende dall'avviso: quelli sulla formazione valgono fino alla scadenza, riepilogo e «formazione pronta»
aspettano il telefono per qualche ora. Il servizio delle notifiche è finto (nessuna rete), l'invio passa dal codice vero."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from fanta import consigli, notifiche, push
from fanta.regole import Regole
from test_notifiche import ROSE, _db, _finto

ORA = 3600


@pytest.fixture
def servizio(tmp_path, monkeypatch):
    """Un dispositivo iscritto e il servizio delle notifiche web finto: registra il corpo e il tempo di vita di ogni invio."""
    monkeypatch.setattr(push, "FILE_VAPID", tmp_path / "vapid.json")
    iscrizioni = tmp_path / "push.json"
    push.iscrivi({"endpoint": "https://web.push.example/uno", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}, iscrizioni)
    inviati = []

    def finto(subscription_info, data, vapid_private_key, vapid_claims, ttl, headers, timeout, requests_session=None):
        inviati.append({"corpo": json.loads(data), "ttl": ttl})
    monkeypatch.setattr("pywebpush.webpush", finto)
    return NS(inviati=inviati, manda=notifiche.manda_di(tmp_path / "avvisi.json", iscrizioni, ntfy=False))


def test_due_avvisi_dello_stesso_giro_hanno_tag_web_diversi(servizio):
    """45 minuti prima della scadenza: «cambia la formazione consigliata» e subito dopo «cambi nelle probabili», con lo stesso tag
    di ntfy. Con lo stesso tag web il secondo prendeva il posto del primo sul telefono."""
    assert servizio.manda("SchieraXI · cambia la formazione consigliata", "Metti Bonny", 4, "rotating_light")
    assert servizio.manda("SchieraXI · cambi nelle probabili", "Castro: ora infortunato", 4, "rotating_light")
    primo, secondo = (x["corpo"] for x in servizio.inviati)
    assert primo["tag"] != secondo["tag"]
    # il tocco porta sempre alla Formazione: lo dice `url`, che il service worker (fanta/web/sw.js) usa e che non cambia
    assert (primo["url"], primo["sezione"]) == (secondo["url"], secondo["sezione"]) == ("/?vista=formazione", "formazione")


@pytest.mark.parametrize("adesso, secondi", [(datetime(2026, 10, 28, 17, 35), 55 * 60),      # «tra un'ora»: 55 minuti alla scadenza
                                              (datetime(2026, 10, 28, 18, 20), 10 * 60)])    # «ultimi minuti»: 10 minuti
def test_il_promemoria_vale_fino_alla_scadenza(servizio, monkeypatch, tmp_path, adesso, secondi):
    """Formazione che si chiude alle 18:30: il servizio non consegna il promemoria dopo la chiusura a un telefono rimasto senza rete
    (prima valeva un'ora per tutti: «ultimi minuti» poteva arrivare 50 minuti dopo la scadenza)."""
    _finto(monkeypatch)
    opz = {"cambi": True, "promemoria_60": True, "promemoria_15": True}
    assert notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, adesso, tmp_path / "p.json", servizio.manda, opz)
    assert [x["ttl"] for x in servizio.inviati] == [secondi]


def _registro():
    """Chi manda: registra cosa arriva oltre a titolo, testo, priorità e tag (qui `vale_per`)."""
    inviati = []
    return inviati, lambda titolo, testo, priorita=3, tag="x", **k: inviati.append(k) or True


def test_i_cambi_nelle_probabili_valgono_fino_alla_scadenza(monkeypatch, tmp_path):
    """Due ore e mezza prima della scadenza (18:30) Castro risulta infortunato: l'avviso vale fino alla chiusura della formazione."""
    _finto(monkeypatch)
    prev = pd.DataFrame([{"nome": "Castro", "stato": "titolare", "percentuale": 80.0, "dubbio": False}], index=[1])
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    inviati, manda = _registro()
    db, f, adesso = _db("2026-10-28 18:30"), tmp_path / "n.json", datetime(2026, 10, 28, 16, 0)
    assert notifiche.cambi(db, Regole(), ROSE, adesso, f, manda, {"cambi": True}) == []     # primo controllo: solo memorizza
    prev.loc[1, "stato"] = "infortunato"
    assert notifiche.cambi(db, Regole(), ROSE, adesso, f, manda, {"cambi": True})
    assert inviati and all(k == {"vale_per": timedelta(hours=2, minutes=30)} for k in inviati)


def test_il_cambio_pronto_vale_fino_alla_scadenza(monkeypatch, tmp_path):
    """Castro è infortunato fin dal primo controllo: parte da solo «cambio pronto» (meglio Bonny), due ore e mezza prima della scadenza."""
    from test_cambio_pronto import ROSE as ROSA_CAMBIO, _db as db_cambio, _scena
    _scena(monkeypatch)
    inviati, manda = _registro()
    titoli = []
    registra = lambda titolo, *a, **k: titoli.append(str(titolo)) or manda(titolo, *a, **k)     # noqa: E731
    assert notifiche.cambi(db_cambio(), Regole(), ROSA_CAMBIO, datetime(2026, 10, 28, 16, 0), tmp_path / "n.json", registra,
                           {"cambi": True}, file_scelte=tmp_path / "s.json")
    assert titoli == ["SchieraXI · cambio pronto"] and inviati == [{"vale_per": timedelta(hours=2, minutes=30)}]


def test_cambia_la_formazione_vale_fino_alla_scadenza(monkeypatch, tmp_path):
    """40 minuti prima della scadenza le probabili cambiano la consigliata: l'avviso vale quei 40 minuti."""
    from test_avviso_scadenza import BASE, ROSE as ROSA_14, Finto, _cambi_ha_visto
    m = Finto(monkeypatch, _db("2026-10-28 18:30"))
    inviati, manda = _registro()
    giro = lambda ora: notifiche.avviso_scadenza(m.db, Regole(), ROSA_14, ora, tmp_path / "prom.json", manda,   # noqa: E731
                                                 {"avviso_prima": 60}, tmp_path / "scelte.json", tmp_path / "cambi.json")
    _cambi_ha_visto(tmp_path / "cambi.json", BASE)
    assert giro(datetime(2026, 10, 28, 16, 0)) == []                    # lontano dalla scadenza: si ricorda la consigliata
    m.cambia("v1", esce=11, entra=12, stato={11: "infortunato"}, bonus={11: -2.5})
    assert giro(datetime(2026, 10, 28, 17, 50))
    assert inviati == [{"vale_per": timedelta(minutes=40)}]


def test_il_reparto_scoperto_vale_fino_alla_scadenza(monkeypatch, tmp_path):
    from test_copertura import _base, _con, _db as db_copertura, _scena
    rose, _, _ = _scena(monkeypatch, _con(_base(), "P", 2))
    inviati, manda = _registro()
    assert notifiche.copertura(db_copertura(), Regole(), rose, datetime(2026, 10, 28, 12, 30), tmp_path / "n.json", manda, {})
    assert inviati == [{"vale_per": timedelta(hours=6)}]                 # dalle 12:30 alla chiusura delle 18:30


def test_il_riepilogo_aspetta_il_telefono_per_qualche_ora(servizio):
    """Telefono spento dalle 8 alle 9:10: il riepilogo mandato alle 8 deve arrivare lo stesso (prima scadeva dopo un'ora)."""
    assert servizio.manda("SchieraXI · riepilogo della giornata", "Giornata 8: 70 punti", 3, "bar_chart")
    assert servizio.inviati[0]["ttl"] >= 3 * ORA
