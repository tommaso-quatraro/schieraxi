"""#651: le chiavi della consigliata «tenuta» cambiano con l'orologio (scadenza passata, anticipo cominciato), ma il riscaldamento
ripartiva solo quando cambiavano i dati: il widget, che legge solo la cache, riceveva 202 fino al giro dei risultati. Ora il valore
che il riscaldamento confronta comprende anche giornata, scadenza passata e anticipi cominciati delle leghe attive. Ore fissate,
calendario e rosa inventati (quelli di test_anticipi_consigliata: anticipo mercoledì 20:45, formazione chiusa sabato alle 15:00)."""
from datetime import datetime, timedelta

import pytest

from fanta import calcolo, riscaldamento, server
from fanta.regole import Regole
from test_anticipi_consigliata import (GIOVEDI, MARTEDI, MERCOLEDI_PRIMA, SOLO_442, _formazione, _prev,  # noqa: F401  (fixture)
                                       _schede_semplici, mondo)

SABATO_PRIMA = datetime(2026, 11, 7, 14, 30)
SABATO_DOPO = datetime(2026, 11, 7, 15, 1)
UN_ORA_PRIMA = Regole(moduli=["4-4-2"], scadenza_minuti=60)          # un'altra lega: si chiude alle 14:00


def _widget(mondo) -> dict:  # noqa: F811  (lo stato della fixture)
    """La consigliata come la chiede il token del widget: solo dalla cache, mai un calcolo."""
    gettone = calcolo.solo_cache.set(True)
    try:
        return _formazione(mondo)
    finally:
        calcolo.solo_cache.reset(gettone)


def test_lo_stato_delle_giornate_cambia_con_l_anticipo_e_con_la_scadenza(mondo):  # noqa: F811  (fixture)
    stato = lambda adesso, leghe=(SOLO_442,): riscaldamento.stato_giornate(mondo["db"], leghe, adesso)  # noqa: E731
    assert stato(MARTEDI) == stato(MERCOLEDI_PRIMA)                    # niente di nuovo: nessun giro in più
    assert stato(GIOVEDI) != stato(MERCOLEDI_PRIMA)                    # l'anticipo di mercoledì è cominciato
    assert stato(SABATO_PRIMA) == stato(GIOVEDI)
    assert stato(SABATO_DOPO) != stato(SABATO_PRIMA)                   # formazione chiusa
    assert stato(SABATO_DOPO + timedelta(hours=3)) == stato(SABATO_DOPO)     # dopo la scadenza le altre partite non cambiano niente
    due = (SOLO_442, UN_ORA_PRIMA)                                     # ogni lega con la sua scadenza
    assert stato(datetime(2026, 11, 7, 14, 1), due) != stato(datetime(2026, 11, 7, 13, 59), due)
    assert stato(datetime(2026, 11, 7, 14, 1), due) != stato(SABATO_DOPO, due)


class _SenzaChiudere:
    """La connessione dell'archivio finto: il server chiude la sua dopo ogni lettura, questa deve restare aperta per il test."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, nome):
        return getattr(self._db, nome)

    def close(self):
        pass


def test_il_server_fa_ripartire_il_riscaldamento_anche_senza_dati_nuovi(mondo, monkeypatch):  # noqa: F811  (fixture)
    """Il valore che il riscaldamento del servizio confronta ogni minuto cambia quando comincia l'anticipo e quando passa la scadenza,
    con la stessa versione dei dati; prima era la sola versione dei dati."""
    monkeypatch.setattr(server, "_db", lambda: _SenzaChiudere(mondo["db"]))
    monkeypatch.setattr(server, "_versione_dati", lambda: "stessi-dati")
    monkeypatch.setattr(server, "_leghe_attive", lambda: [SOLO_442])
    visti = []
    for adesso in (MARTEDI, MERCOLEDI_PRIMA, GIOVEDI, SABATO_PRIMA, SABATO_DOPO):
        mondo["adesso"] = adesso
        visti.append(server._da_sorvegliare())
    assert all(v[0] == "stessi-dati" for v in visti)
    assert visti[0] == visti[1] != visti[2] == visti[3] != visti[4]
    monkeypatch.setattr(server, "_leghe_attive", lambda: 1 / 0)       # leghe illeggibili: resta la versione dei dati, come prima
    assert server._da_sorvegliare() == ("stessi-dati", None)


@pytest.mark.parametrize("cambio, adesso", [("anticipo", GIOVEDI), ("scadenza", SABATO_DOPO)])
def test_dopo_il_giro_del_riscaldamento_il_widget_trova_la_consigliata_tenuta(mondo, cambio, adesso):  # noqa: F811  (fixture)
    """La consigliata mostrata martedì resta dopo un ritocco delle probabili (tenuta). Quando comincia l'anticipo o passa la scadenza
    la sua chiave cambia: il widget non la trova finché il riscaldamento non riparte; dopo il giro la trova."""
    _formazione(mondo)                                                 # mostrata (e ricordata) martedì
    _formazione(mondo, _prev({8: {"mu": 6.4}}))                        # ritocco: resta quella di prima
    assert _widget(mondo)
    prima = riscaldamento.stato_giornate(mondo["db"], [SOLO_442], mondo["adesso"])
    mondo["adesso"] = adesso
    with pytest.raises(calcolo.InCalcolo):
        _widget(mondo)
    assert riscaldamento.stato_giornate(mondo["db"], [SOLO_442], adesso) != prima    # il riscaldamento riparte...
    _formazione(mondo)                                                 # ...e prepara la consigliata (come scalda_contesto)
    assert _widget(mondo)["titolari"]
