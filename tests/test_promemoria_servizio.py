"""Promemoria della scadenza dentro il servizio, con gli account accesi: il servizio fa il giro ai minuti tondi come il cron di
sempre (`script/server/promemoria.sh`, ogni 10 minuti) con i calcoli che ha già in memoria, e segna l'ora di ogni giro; il comando
`promemoria` del cron, con un segno fresco, non rifà il giro (ricaricherebbe il modello in un processo a parte). Se il servizio è
fermo il segno invecchia e il cron torna a fare il giro come prima. Orologio finto, cartelle temporanee, notifiche finte."""
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from fanta import __main__ as cli
from fanta import avvisi_utenti

from test_avvisi_utenti import UN_ORA_PRIMA, mondo, nuovo, registro  # noqa: F401  (mondo e registro sono fixture)


class Fermo:
    """Al posto di threading.Event: `wait` fa avanzare l'orologio finto invece di aspettare, e ferma il giro a `fine`."""

    def __init__(self, orologio: list, fine: datetime):
        self.orologio, self.fine, self.attese = orologio, fine, []

    def is_set(self) -> bool:
        return self.orologio[0] >= self.fine

    def wait(self, secondi: float) -> bool:
        self.attese.append(secondi)
        self.orologio[0] += timedelta(seconds=secondi)
        return self.is_set()


@pytest.fixture
def acceso(monkeypatch, tmp_path):
    """Account e pianificatore accesi (conftest lo spegne in tutte le prove), cartella degli account temporanea."""
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setenv("FANTA_PIANIFICATORE", "1")
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "utenti"))
    return tmp_path / "segno.json"


def _gira(segno, da: datetime, a: datetime, guasti=()):
    """Fa girare il thread del servizio con l'orologio finto da `da` ad `a`: le ore dei giri fatti e il Fermo. Nei minuti di
    `guasti` («HH:MM») il giro finto va in errore, come con il database degli account bloccato."""
    orologio, fatti = [da], []
    fermo = Fermo(orologio, a)
    fermo.ricevuti = []

    def giro_finto(db, fermo_del_giro):
        fatti.append(orologio[0])
        fermo.ricevuti.append(fermo_del_giro)
        if orologio[0].strftime("%H:%M") in guasti:
            raise sqlite3.OperationalError("database is locked: cartella-di-amico1")
        return {}, {}
    avvisi_utenti.sorveglia_promemoria(fermo, lambda: DbFinto(), adesso=lambda: orologio[0], file=segno, giro=giro_finto, ritardo=0)
    return fatti, fermo


class DbFinto:
    chiuso = False

    def close(self):
        self.chiuso = True


def _segno(file) -> datetime:
    return datetime.fromisoformat(json.loads(file.read_text(encoding="utf-8"))["giro"])


# ---------------------------------------------------------------- il giro del servizio
def test_il_servizio_fa_il_giro_subito_e_poi_ai_minuti_tondi_come_il_cron(acceso):
    fatti, fermo = _gira(acceso, datetime(2026, 11, 28, 20, 27, 10), datetime(2026, 11, 28, 20, 51))
    # all'avvio subito (il turno delle 20:20 non era ancora fatto da lui), poi alle 20:30, 20:40 e 20:50: gli orari del cron
    assert [f.strftime("%H:%M") for f in fatti] == ["20:27", "20:30", "20:40", "20:50"]
    assert all(f.second == 0 for f in fatti[1:])                        # pochi istanti dopo il minuto tondo, non un minuto dopo
    assert max(fermo.attese) <= 60                                      # si riguarda l'ora almeno ogni minuto (cambi d'ora, sospensioni)
    assert _segno(acceso) == datetime(2026, 11, 28, 20, 50)             # il segno ha l'ora dell'ultimo giro (al secondo)
    assert all(f is fermo for f in fermo.ricevuti)                      # il giro sa quando il servizio si chiude (fra un utente e l'altro)


def test_un_giro_in_errore_non_lascia_il_segno_e_il_cron_subentra(acceso, caplog):
    """Il segno vuol dire «giro riuscito». Se il giro va in errore (qui sempre, dalle 20:30) il segno resta quello dell'ultimo
    giro riuscito e il cron rifà il giro appena è vecchio: i promemoria di quell'ora non si perdono."""
    acceso.write_text(json.dumps({"giro": "2026-11-28T20:20:00"}), encoding="utf-8")       # l'ultimo giro riuscito
    guasti = [f"20:{m}" for m in range(30, 42)]
    with caplog.at_level(logging.WARNING):
        fatti, _ = _gira(acceso, datetime(2026, 11, 28, 20, 30, 0, 500000), datetime(2026, 11, 28, 20, 41), guasti=guasti)
    assert _segno(acceso) == datetime(2026, 11, 28, 20, 20)
    fare, riga = avvisi_utenti.promemoria_dal_cron(datetime(2026, 11, 28, 20, 40, 3), acceso)
    assert fare is True and "20 minuti" in riga                          # alle 20:40 lo fa il cron, e lo scrive
    assert len(fatti) == 11                                             # il servizio riprova ogni minuto, dalle 20:30 alle 20:40
    assert "OperationalError" in caplog.text and "amico1" not in caplog.text     # il tipo dell'errore, mai il messaggio (dati)


def test_senza_nessun_giro_riuscito_il_cron_fa_ogni_giro(acceso):
    sempre = [f"{h}:{m:02d}" for h in (19, 20) for m in range(60)]
    _gira(acceso, datetime(2026, 11, 28, 19, 59, 50), datetime(2026, 11, 28, 20, 51), guasti=sempre)
    assert not acceso.exists()
    assert avvisi_utenti.promemoria_dal_cron(datetime(2026, 11, 28, 20, 10, 3), acceso) == (True, "")


def test_dopo_un_giro_in_errore_si_riprova_al_minuto_dopo_non_al_turno_dopo(acceso):
    fatti, _ = _gira(acceso, datetime(2026, 11, 28, 20, 30, 0, 500000), datetime(2026, 11, 28, 20, 39, 30), guasti=["20:30"])
    assert [f.strftime("%H:%M") for f in fatti] == ["20:30", "20:31"]   # riuscito alle 20:31: fino alle 20:40 niente altri giri
    assert _segno(acceso) == datetime(2026, 11, 28, 20, 31)


def test_con_il_pianificatore_spento_niente_giri_e_il_segno_sparisce(acceso, monkeypatch):
    """FANTA_PIANIFICATORE=0 (come nell'ambiente di prova) spegne anche questo: il giro torna tutto al cron, che non dice niente."""
    acceso.write_text(json.dumps({"giro": "2026-11-28T20:20:00"}), encoding="utf-8")
    monkeypatch.setenv("FANTA_PIANIFICATORE", "0")
    fatti, _ = _gira(acceso, datetime(2026, 11, 28, 20, 27), datetime(2026, 11, 28, 20, 51))
    assert fatti == [] and not acceso.exists()
    assert avvisi_utenti.promemoria_dal_cron(datetime(2026, 11, 28, 20, 30), acceso) == (True, "")


def test_senza_account_il_servizio_non_fa_i_promemoria(acceso, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE")
    fatti, _ = _gira(acceso, datetime(2026, 11, 28, 20, 27), datetime(2026, 11, 28, 20, 51))
    assert fatti == [] and not acceso.exists()


# ---------------------------------------------------------------- il cron
@pytest.mark.parametrize("eta,fa,riga", [
    (None, True, False),                                    # nessun segno: il servizio non fa i promemoria, il cron come sempre
    (timedelta(minutes=10), False, False),                  # il giro di 10 minuti fa (il cron gira negli stessi minuti)
    (timedelta(minutes=14, seconds=59), False, False),
    (timedelta(minutes=15), True, True),                    # il servizio ha saltato un giro: lo fa il cron, e lo scrive
    (timedelta(hours=3), True, True),                       # servizio fermo
    (timedelta(minutes=-50), True, False),                  # segno «nel futuro» (l'ora legale è tornata indietro): lo fa il cron
])
def test_il_cron_rifa_il_giro_solo_se_il_servizio_non_lo_fa_da_un_quarto_d_ora(tmp_path, eta, fa, riga):
    adesso, segno = datetime(2026, 11, 28, 20, 30, 2), tmp_path / "segno.json"
    if eta is not None:
        segno.write_text(json.dumps({"giro": (adesso - eta).isoformat(timespec="seconds")}), encoding="utf-8")
    fare, testo = avvisi_utenti.promemoria_dal_cron(adesso, segno)
    assert fare is fa and bool(testo) is riga
    if riga:
        assert f"{int(eta.total_seconds() // 60)} minuti" in testo


def test_segno_rovinato_vale_come_nessun_segno(tmp_path):
    segno = tmp_path / "segno.json"
    for contenuto in ("{rotto", "[]", json.dumps({"giro": "ieri"}), json.dumps({"giro": 5})):
        segno.write_text(contenuto, encoding="utf-8")
        assert avvisi_utenti.promemoria_dal_cron(datetime(2026, 11, 28, 20, 30), segno) == (True, "")


# ---------------------------------------------------------------- dal servizio al cron, con gli avvisi veri
def test_il_giro_del_servizio_manda_i_promemoria_e_il_cron_dopo_non_li_rifa(mondo, registro, monkeypatch, capsys,  # noqa: F811
                                                                            caplog):
    from fanta import archivio, pianificatore

    class UnOraPrima(datetime):
        @classmethod
        def now(cls, tz=None):
            return UN_ORA_PRIMA
    monkeypatch.setattr(avvisi_utenti, "datetime", UnOraPrima)
    monkeypatch.setattr(pianificatore, "acceso", lambda: True)
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    orologio = [UN_ORA_PRIMA]
    fermo = Fermo(orologio, UN_ORA_PRIMA + timedelta(seconds=1))      # un giro solo: il thread si ferma alla prima attesa
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        avvisi_utenti.sorveglia_promemoria(fermo, lambda: mondo.db, adesso=lambda: orologio[0], ritardo=0)
    assert sorted(chi for chi, _, _ in registro.web) == sorted([a.cartella.name, b.cartella.name])     # uno a testa
    # nel registro del servizio quanti ne sono partiti, come le righe del cron: il numero dell'utente, mai il nome
    assert f"Promemoria: utente {a.utente_id}, 1 avvisi" in caplog.text and f"Promemoria: utente {b.utente_id}, 1 avvisi" in caplog.text
    assert "amico" not in caplog.text and "Castro" not in caplog.text
    chiamate = []
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f: chiamate.append(f))
    monkeypatch.setattr(archivio, "apri", lambda *x: mondo.db)
    cli.cmd_promemoria(None)                                # il cron, negli stessi minuti
    assert chiamate == [] and capsys.readouterr().out == ""
    assert len(registro.web) == 2


def test_il_cron_con_il_segno_vecchio_fa_il_giro_e_lo_dice(mondo, registro, monkeypatch, capsys):  # noqa: F811
    from fanta import percorsi

    class UnOraPrima(datetime):
        @classmethod
        def now(cls, tz=None):
            return UN_ORA_PRIMA
    monkeypatch.setattr(avvisi_utenti, "datetime", UnOraPrima)
    segno = percorsi.cartella_account() / avvisi_utenti.FILE_SEGNO
    segno.parent.mkdir(parents=True, exist_ok=True)
    segno.write_text(json.dumps({"giro": (UN_ORA_PRIMA - timedelta(minutes=40)).isoformat()}), encoding="utf-8")
    chiamate = []
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f: chiamate.append(f))
    cli.cmd_promemoria(None)
    assert chiamate == ["promemoria"] and "40 minuti" in capsys.readouterr().out


# ---------------------------------------------------------------- riavvio del servizio a metà giro (un'installazione alle 19:40)
def test_il_giro_si_ferma_fra_un_utente_e_l_altro_quando_il_servizio_si_chiude(tmp_path, monkeypatch, caplog):
    """Chi è a metà finisce (invio e stato «mandato»), chi viene dopo non comincia: lo serve il servizio nuovo, senza doppioni."""
    fermo = threading.Event()
    attivi = [SimpleNamespace(utente=SimpleNamespace(id=i, nome_utente=nome),
                              ctx=SimpleNamespace(regole=None, stato_promemoria=tmp_path / f"{nome}-promemoria.json"))
              for i, nome in ((1, "anna"), (2, "bruno"), (3, "carla"))]
    monkeypatch.setattr(avvisi_utenti.regole, "carica", lambda percorso: None)

    def promemoria(a, db, r, adesso):
        if a.utente.nome_utente == "anna":
            fermo.set()                       # la chiusura arriva mentre il servizio manda il promemoria ad anna
        return ["mandato"]
    monkeypatch.setitem(avvisi_utenti._LAVORI, "promemoria", promemoria)
    with caplog.at_level(logging.WARNING):
        esiti, errori = avvisi_utenti.esegui("promemoria", None, UN_ORA_PRIMA, attivi=attivi, fermo=fermo)
    assert esiti == {"anna": ["mandato"]} and errori == {}
    assert "2 utenti al prossimo giro" in caplog.text


def test_alla_chiusura_il_servizio_aspetta_la_fine_del_giro_dei_promemoria(dati_isolati, monkeypatch):
    from fastapi.testclient import TestClient
    from fanta import server
    monkeypatch.setattr(server.riscaldamento, "attivo", lambda: False)
    monkeypatch.setenv("FANTA_LIVE", "0")
    finito = threading.Event()

    def giro_in_corso(fermo, apri_db):
        fermo.wait()                          # la chiusura arriva mentre il giro lavora per un utente
        time.sleep(0.5)                       # che finisce: invio e stato «mandato»
        finito.set()
    monkeypatch.setattr(server.avvisi_utenti, "sorveglia_promemoria", giro_in_corso)
    with TestClient(server.app):
        pass
    assert finito.is_set()                    # chiuso solo dopo: il servizio nuovo non rimanda lo stesso promemoria
