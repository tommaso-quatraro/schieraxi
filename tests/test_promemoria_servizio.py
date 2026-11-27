"""Promemoria della scadenza dentro il servizio, con gli account accesi: il servizio fa il giro ai minuti tondi come il cron di
sempre (`script/server/promemoria.sh`, ogni 10 minuti) con i calcoli che ha già in memoria, e segna l'ora di ogni giro; il comando
`promemoria` del cron, con un segno fresco, non rifà il giro (ricaricherebbe il modello in un processo a parte). Se il servizio è
fermo il segno invecchia e il cron torna a fare il giro come prima. Orologio finto, cartelle temporanee, notifiche finte."""
import json
import logging
from datetime import datetime, timedelta

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


def _gira(segno, da: datetime, a: datetime, giro=None):
    """Fa girare il thread del servizio con l'orologio finto da `da` ad `a`: le ore dei giri fatti e il Fermo."""
    orologio, fatti = [da], []
    fermo = Fermo(orologio, a)

    def giro_finto(db):
        fatti.append(orologio[0])
        return {}, {}
    avvisi_utenti.sorveglia_promemoria(fermo, lambda: DbFinto(), adesso=lambda: orologio[0], file=segno,
                                       giro=giro or giro_finto, ritardo=0)
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


def test_un_giro_in_errore_non_ferma_i_giri_dopo_e_finisce_nel_registro(acceso, caplog):
    volte = []

    def rotto(db):
        volte.append(1)
        raise OSError("disco pieno: cartella-di-amico1")
    with caplog.at_level(logging.WARNING):
        _gira(acceso, datetime(2026, 11, 28, 20, 29, 50), datetime(2026, 11, 28, 20, 41), giro=rotto)
    assert len(volte) == 3                                              # 20:29, 20:30 e 20:40: il thread va avanti
    assert "OSError" in caplog.text and "amico1" not in caplog.text     # il tipo dell'errore, mai il messaggio (può avere dati)


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
def test_il_giro_del_servizio_manda_i_promemoria_e_il_cron_dopo_non_li_rifa(mondo, registro, monkeypatch, capsys):  # noqa: F811
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
    avvisi_utenti.sorveglia_promemoria(fermo, lambda: mondo.db, adesso=lambda: orologio[0], ritardo=0)
    assert sorted(chi for chi, _, _ in registro.web) == sorted([a.cartella.name, b.cartella.name])     # uno a testa
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
