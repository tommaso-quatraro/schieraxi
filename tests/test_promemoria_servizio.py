"""Promemoria della scadenza dentro il servizio, con gli account accesi: il servizio fa il giro ai minuti tondi come il cron di
sempre (`script/server/promemoria.sh`, ogni 10 minuti) con i calcoli che ha già in memoria, e segna l'ora di ogni giro; il comando
`promemoria` del cron, se il servizio ha fatto il giro dello stesso turno, non lo rifà (ricaricherebbe il modello in un processo a
parte). Se il servizio salta un turno (fermo, bloccato, in errore) il giro lo fa il cron, in tempo per le finestre dei promemoria.
Orologio finto, cartelle temporanee, notifiche finte."""
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from fanta import __main__ as cli
from fanta import avvisi_utenti, notifiche

from test_avvisi_utenti import UN_ORA_PRIMA, mondo, nuovo, registro  # noqa: F401  (mondo e registro sono fixture)
from test_notifiche import _db


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


def _scrivi_segno(file, giro: datetime) -> None:
    """Il segno come lo scrive il servizio alla fine di un giro riuscito: l'ora d'inizio del giro, al secondo."""
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"giro": giro.isoformat(timespec="seconds")}), encoding="utf-8")


class Cron:
    """L'orologio del comando `promemoria` del cron: `dormi` fa avanzare l'ora invece di aspettare. `servizio`: {quando: inizio del
    giro}, il servizio vivo che scrive il segno alla fine del suo giro, quando l'orologio passa `quando`."""

    def __init__(self, ora: datetime, segno, servizio: dict | None = None):
        self.ora, self.segno, self.servizio, self.attese = ora, segno, dict(servizio or {}), []

    def __call__(self) -> datetime:
        return self.ora

    def dormi(self, secondi: float) -> None:
        self.attese.append(secondi)
        self.ora += timedelta(seconds=secondi)
        for quando in [q for q in self.servizio if q <= self.ora]:
            _scrivi_segno(self.segno, self.servizio.pop(quando))


def _orologio_finto(orologio: list) -> type:
    """Al posto di `datetime` in avvisi_utenti: `now()` è `orologio[0]` (l'ora del cron e quella di ogni utente nel giro)."""
    class Finto(datetime):
        @classmethod
        def now(cls, tz=None):
            return orologio[0]
    return Finto


def _cron_con_orologio(monkeypatch, orologio: list) -> None:
    """Il comando `promemoria` del cron con l'orologio finto: l'attesa del giro del servizio fa avanzare l'ora invece di aspettare."""
    vero = avvisi_utenti.promemoria_dal_cron

    def dormi(secondi: float) -> None:
        orologio[0] += timedelta(seconds=secondi)
    monkeypatch.setattr(avvisi_utenti, "promemoria_dal_cron", lambda: vero(dormi=dormi))


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
    fare, riga = avvisi_utenti.promemoria_dal_cron(lambda: datetime(2026, 11, 28, 20, 40, 3), acceso)
    assert fare is True and "20 minuti" in riga                          # alle 20:40 lo fa il cron, e lo scrive
    assert len(fatti) == 11                                             # il servizio riprova ogni minuto, dalle 20:30 alle 20:40
    assert "OperationalError" in caplog.text and "amico1" not in caplog.text     # il tipo dell'errore, mai il messaggio (dati)


def test_senza_nessun_giro_riuscito_il_cron_fa_ogni_giro(acceso):
    sempre = [f"{h}:{m:02d}" for h in (19, 20) for m in range(60)]
    _gira(acceso, datetime(2026, 11, 28, 19, 59, 50), datetime(2026, 11, 28, 20, 51), guasti=sempre)
    assert not acceso.exists()
    assert avvisi_utenti.promemoria_dal_cron(lambda: datetime(2026, 11, 28, 20, 10, 3), acceso) == (True, "")


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
    assert avvisi_utenti.promemoria_dal_cron(lambda: datetime(2026, 11, 28, 20, 30), acceso) == (True, "")


def test_senza_account_il_servizio_non_fa_i_promemoria(acceso, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE")
    fatti, _ = _gira(acceso, datetime(2026, 11, 28, 20, 27), datetime(2026, 11, 28, 20, 51))
    assert fatti == [] and not acceso.exists()


# ---------------------------------------------------------------- il cron
ORA_CRON = datetime(2026, 11, 28, 20, 30, 2)                 # il cron delle 20:30, partito da un paio di secondi


@pytest.mark.parametrize("adesso,giro,fa,minuti,attesa", [
    (ORA_CRON, None, True, None, 0),                        # nessun segno: il servizio non fa i promemoria, il cron come sempre
    (ORA_CRON, (20, 30, 0), False, None, 0),                # il servizio ha già finito il giro di questo turno
    (datetime(2026, 11, 28, 20, 37), (20, 33, 5), False, None, 0),      # il giro di un servizio appena riavviato vale per il turno
    # segno del turno prima e nessun segno nuovo fino a un minuto e mezzo dopo il minuto tondo: il servizio ha saltato il turno
    (ORA_CRON, (20, 20, 0), True, 11, 88),
    (datetime(2026, 11, 28, 20, 34), (20, 20, 0), True, 14, 0),         # cron in ritardo, oltre l'attesa: subito
    (ORA_CRON, (20, 19, 59), True, 10, 0),                  # il servizio ha già saltato il turno delle 20:20: subito
    (ORA_CRON, (17, 30, 0), True, 180, 0),                  # servizio fermo da ore
    (ORA_CRON, (21, 20, 0), True, None, 0),                 # segno «nel futuro» (l'ora legale è tornata indietro): lo fa il cron
])
def test_il_cron_rifa_il_giro_solo_se_il_servizio_salta_il_turno(tmp_path, adesso, giro, fa, minuti, attesa):
    """Il servizio gira negli stessi minuti tondi del cron e scrive il segno alla fine del giro: un segno più vecchio del turno in
    corso vuol dire turno non fatto (ancora, o mai). Del turno prima: il cron aspetta il giro del servizio; più vecchio: subito."""
    segno = tmp_path / "segno.json"
    if giro is not None:
        _scrivi_segno(segno, datetime(2026, 11, 28, *giro))
    cron = Cron(adesso, segno)
    fare, riga = avvisi_utenti.promemoria_dal_cron(cron, segno, dormi=cron.dormi)
    assert fare is fa and bool(riga) is (minuti is not None)
    if minuti is not None:
        assert f"il servizio non fa il giro da {minuti} minuti, lo fa il cron" in riga
    assert sum(cron.attese) == pytest.approx(attesa)


@pytest.mark.parametrize("finisce,inizio", [
    ((20, 30, 20), (20, 30, 0, 500000)),                    # il giro delle 20:30 dura 20 secondi
    ((20, 31, 5), (20, 31, 0, 500000)),                     # il giro delle 20:30 in errore, riprovato e riuscito al minuto dopo
])
def test_servizio_vivo_il_cron_aspetta_la_fine_del_suo_giro_e_non_lo_rifa(tmp_path, finisce, inizio):
    """Alle 20:30 il servizio e il cron partono insieme, e il servizio scrive il segno solo alla fine del giro, con l'ora d'inizio.
    Il cron, che trova ancora il segno delle 20:20, lo aspetta e appena lo vede esce senza fare il giro: niente giro doppio né
    modello ricaricato. Esce subito, non dopo tutta l'attesa: in promemoria.sh dopo viene il controllo di salute."""
    segno = tmp_path / "segno.json"
    _scrivi_segno(segno, datetime(2026, 11, 28, 20, 20))
    finisce = datetime(2026, 11, 28, *finisce)
    cron = Cron(datetime(2026, 11, 28, 20, 30, 1, 500000), segno, servizio={finisce: datetime(2026, 11, 28, *inizio)})
    assert avvisi_utenti.promemoria_dal_cron(cron, segno, dormi=cron.dormi) == (False, "")
    assert finisce <= cron.ora <= finisce + timedelta(seconds=10)


def test_segno_rovinato_vale_come_nessun_segno(tmp_path):
    segno = tmp_path / "segno.json"
    for contenuto in ("{rotto", "[]", json.dumps({"giro": "ieri"}), json.dumps({"giro": 5})):
        segno.write_text(contenuto, encoding="utf-8")
        assert avvisi_utenti.promemoria_dal_cron(lambda: datetime(2026, 11, 28, 20, 30), segno) == (True, "")


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
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f, *resto: chiamate.append(f))
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
    monkeypatch.setattr(cli, "_avvisi_per_utente", lambda f, *resto: chiamate.append(f))
    cli.cmd_promemoria(None)
    assert chiamate == ["promemoria"] and "40 minuti" in capsys.readouterr().out


# ---------------------------------------------------------------- servizio fermo fra due giri: il cron subentra al turno dopo
def test_servizio_fermo_dopo_il_giro_delle_20_20_il_promemoria_delle_20_43_arriva(mondo, registro, monkeypatch,  # noqa: F811
                                                                                  capsys):
    """Il buco lasciato dalla #988. Il servizio fa il giro delle 20:20 e si ferma alle 20:25 (systemd non lo riavvia); la formazione
    si chiude alle 20:43. Con il segno «fresco» per 15 minuti il cron delle 20:30 non faceva niente e quello delle 20:40, a 3 minuti
    dalla chiusura, era fuori dalla finestra del quarto d'ora prima (da 4 a 20 minuti): il promemoria non partiva. Il cron delle
    20:30 deve accorgersi che il servizio ha saltato quel turno e fare il giro lui, quando mancano ancora più di 4 minuti."""
    from fanta import archivio, pianificatore
    orologio = [datetime(2026, 10, 28, 20, 20, 0, 500000)]
    monkeypatch.setattr(avvisi_utenti, "datetime", _orologio_finto(orologio))
    monkeypatch.setattr(pianificatore, "acceso", lambda: True)

    def apri(*x):
        return _db("2026-10-28 20:43")      # la formazione si chiude alle 20:43; un archivio nuovo a ogni giro (il giro lo chiude)
    monkeypatch.setattr(archivio, "apri", apri)
    a = nuovo("amico1", (1, "Castro"))
    avvisi_utenti.sorveglia_promemoria(Fermo(orologio, datetime(2026, 10, 28, 20, 25)), apri, adesso=lambda: orologio[0], ritardo=0)
    assert registro.web == []                # alle 20:20 mancano 23 minuti: troppo presto per il quarto d'ora prima
    _cron_con_orologio(monkeypatch, orologio)
    for ora in ((20, 30, 2), (20, 40, 2)):   # il cron, ogni 10 minuti
        orologio[0] = datetime(2026, 10, 28, *ora)
        cli.cmd_promemoria(None)
    assert [chi for chi, _, _ in registro.web] == [a.cartella.name]                  # il quarto d'ora prima, una volta sola
    assert "il servizio non fa il giro da 11 minuti, lo fa il cron" in capsys.readouterr().out
    _, da, a_minuti, _ = next(f for f in notifiche.FINESTRE if f[0] == "15")
    assert (da, a_minuti) == (4, 20)         # la finestra di cui parla questa prova


def test_servizio_lento_il_cron_fa_il_giro_anche_lui_ma_nessuno_riceve_doppioni(mondo, registro, monkeypatch,  # noqa: F811
                                                                                capsys):
    """Il giro del servizio delle 17:30 manda i promemoria dell'ora prima ma dura più dell'attesa del cron (il segno non è ancora
    scritto): il cron fa il giro anche lui. Lo stato «già mandato» di ogni utente, letto dentro il suo blocco (`blocco_avvisi`, che
    tests/test_avvisi_processi.py prova fra due processi veri), ferma i doppioni."""
    from fanta import archivio, percorsi
    orologio = [datetime(2026, 10, 28, 17, 30, 0, 500000)]
    monkeypatch.setattr(avvisi_utenti, "datetime", _orologio_finto(orologio))
    monkeypatch.setattr(archivio, "apri", lambda *x: _db("2026-10-28 18:30"))
    nuovo("amico1", (1, "Castro"))
    nuovo("amico2", (2, "Bonny"))
    _scrivi_segno(percorsi.cartella_account() / avvisi_utenti.FILE_SEGNO, datetime(2026, 10, 28, 17, 20))   # il turno prima
    avvisi_utenti.esegui("promemoria", _db("2026-10-28 18:30"))            # il servizio alle 17:30: invii fatti, giro non finito
    assert len(registro.web) == 2
    _cron_con_orologio(monkeypatch, orologio)
    orologio[0] = datetime(2026, 10, 28, 17, 30, 2)
    cli.cmd_promemoria(None)
    assert "lo fa il cron" in capsys.readouterr().out       # nessun segno delle 17:30 entro un minuto e mezzo: il giro lo fa il cron
    assert len(registro.web) == 2                           # e non rimanda niente


def test_il_tempo_passato_ad_aspettare_il_servizio_si_toglie_dal_giro_del_cron(acceso, monkeypatch):
    """promemoria.sh ferma il comando dopo FANTA_MAX_SECONDI_GIRO_PROMEMORIA secondi da quando parte: il giro del cron che prima ha
    aspettato il servizio ha meno tempo, così si ferma ancora fra un utente e l'altro e non a metà di un invio."""
    from fanta import archivio

    def aspetta_il_servizio(*a, **k):
        time.sleep(0.3)
        return True, "promemoria: il servizio non fa il giro da 11 minuti, lo fa il cron"
    monkeypatch.setattr(avvisi_utenti, "promemoria_dal_cron", aspetta_il_servizio)
    monkeypatch.setattr(archivio, "apri", lambda *x: DbFinto())
    giri = []
    monkeypatch.setattr(avvisi_utenti, "esegui", lambda funzione, db, **k: giri.append((funzione, k.get("max_secondi"))) or ({}, {}))
    cli.cmd_promemoria(None)
    [(funzione, max_secondi)] = giri
    assert funzione == "promemoria" and max_secondi is not None
    assert max_secondi <= avvisi_utenti.secondi_del_giro("promemoria") - 0.3


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
