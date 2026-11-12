"""#651: le chiavi della consigliata «tenuta» cambiano con l'orologio (scadenza passata, anticipo cominciato), ma il riscaldamento
ripartiva solo quando cambiavano i dati: il widget, che legge solo la cache, riceveva 202 fino al giro dei risultati. Ora il valore
che il riscaldamento confronta comprende anche giornata, scadenza passata e anticipi cominciati delle leghe attive. Ore fissate,
calendario e rosa inventati (quelli di test_anticipi_consigliata: anticipo mercoledì 20:45, formazione chiusa sabato alle 15:00)."""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

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


def _server_sull_archivio_finto(mondo, monkeypatch, regole_di=lambda ctx: SOLO_442) -> None:  # noqa: F811  (lo stato della fixture)
    """Il server legge l'archivio finto e due utenti attivi (7 e 8); `regole_di` dà le regole di ciascuno. Nessun guasto già scritto."""
    monkeypatch.setattr(server, "_db", lambda: _SenzaChiudere(mondo["db"]))
    monkeypatch.setattr(server, "_versione_dati", lambda: "stessi-dati")
    monkeypatch.setattr(riscaldamento, "contesti_da_scaldare", lambda locale, adesso=None: [NS(utente_id=7), NS(utente_id=8)])
    monkeypatch.setattr(server, "_regole", regole_di)
    monkeypatch.setattr(server, "_guasti_visti", frozenset())


def test_il_server_fa_ripartire_il_riscaldamento_anche_senza_dati_nuovi(mondo, monkeypatch):  # noqa: F811  (fixture)
    """Il valore che il riscaldamento del servizio confronta ogni minuto cambia quando comincia l'anticipo e quando passa la scadenza,
    con la stessa versione dei dati; prima era la sola versione dei dati."""
    _server_sull_archivio_finto(mondo, monkeypatch)
    visti = []
    for adesso in (MARTEDI, MERCOLEDI_PRIMA, GIOVEDI, SABATO_PRIMA, SABATO_DOPO):
        mondo["adesso"] = adesso
        visti.append(server._da_sorvegliare())
    assert all(v[0] == "stessi-dati" for v in visti)
    assert visti[0] == visti[1] != visti[2] == visti[3] != visti[4]


def _righe(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("Riscaldamento:")]


def test_regole_illeggibili_di_un_utente_si_vedono_nel_registro(mondo, monkeypatch, caplog):  # noqa: F811  (fixture)
    """Guasti visibili: se le regole di un utente non si leggono, le altre leghe contano lo stesso e nel registro c'è una riga con
    il tipo dell'errore e il numero dell'utente (mai il nome né il testo dell'errore), una volta finché dura, non a ogni minuto."""
    def regole_di(ctx):
        if ctx.utente_id == 8:
            raise ValueError("testo rovinato del file")
        return SOLO_442
    _server_sull_archivio_finto(mondo, monkeypatch, regole_di)
    mondo["adesso"] = GIOVEDI
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        v = server._da_sorvegliare()
        server._da_sorvegliare()
    assert v == ("stessi-dati", riscaldamento.stato_giornate(mondo["db"], [SOLO_442], GIOVEDI))
    righe = _righe(caplog)
    assert len(righe) == 1 and "utente 8" in righe[0] and "ValueError" in righe[0] and "rovinato" not in righe[0]


def test_senza_utenti_o_calendario_resta_la_versione_dei_dati_e_si_scrive_nel_registro(mondo, monkeypatch, caplog):  # noqa: F811
    _server_sull_archivio_finto(mondo, monkeypatch)
    monkeypatch.setattr(riscaldamento, "contesti_da_scaldare", lambda locale, adesso=None: 1 / 0)    # database degli account illeggibile
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        assert server._da_sorvegliare() == ("stessi-dati", None)
    assert len(_righe(caplog)) == 1 and "ZeroDivisionError" in _righe(caplog)[0]


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
