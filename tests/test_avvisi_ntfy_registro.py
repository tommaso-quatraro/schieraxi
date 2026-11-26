"""Un avviso che ntfy non prende lascia una riga nel registro (26/11/2026). Prima un promemoria non partito su ntfy spariva senza
traccia in `promemoria.log`, mentre le notifiche web la lasciano in `push.log`. La riga dice il tipo di avviso (il tag) e il
motivo (codice della risposta o tipo d'errore): mai il canale, che fa da password, né titolo e testo, che hanno i nomi dei
calciatori. Nelle ore tranquille non parte niente e non si scrive niente."""
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import requests

from fanta import notifiche

RADICE = Path(__file__).resolve().parent.parent
CANALE = "canale-segreto-di-prova"
TITOLO = "SchieraXI · hai messo la formazione?"
TESTO = "Rossi è infortunato: controlla la formazione che hai salvato."


def _righe_ntfy(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING and "ntfy" in r.getMessage()]


def _senza_dati(riga: str) -> None:
    for segreto in (CANALE, "Rossi", "hai messo"):
        assert segreto not in riga, riga


def test_ntfy_che_non_risponde_lascia_una_riga_senza_dati(monkeypatch, caplog):
    def rotto(*a, **k):
        raise requests.ConnectionError(f"https://ntfy.sh/{CANALE} non raggiungibile")
    monkeypatch.setattr(notifiche, "canale", lambda: CANALE)
    monkeypatch.setattr(notifiche.requests, "post", rotto)
    with caplog.at_level(logging.WARNING):
        assert notifiche._invia_ntfy(TITOLO, TESTO, 4, "alarm_clock") is False
    righe = _righe_ntfy(caplog)
    assert len(righe) == 1, caplog.text
    assert "alarm_clock" in righe[0] and "ConnectionError" in righe[0], righe[0]
    _senza_dati(righe[0])


def test_ntfy_che_rifiuta_lascia_una_riga_con_il_codice(monkeypatch, caplog):
    class Rifiutata:
        ok = False
        status_code = 429

    monkeypatch.setattr(notifiche, "canale", lambda: CANALE)
    monkeypatch.setattr(notifiche.requests, "post", lambda *a, **k: Rifiutata())
    with caplog.at_level(logging.WARNING):
        assert notifiche._invia_ntfy(TITOLO, TESTO, 4, "alarm_clock") is False
    righe = _righe_ntfy(caplog)
    assert len(righe) == 1 and "429" in righe[0], caplog.text
    _senza_dati(righe[0])


def test_ntfy_che_prende_l_avviso_non_scrive_niente(monkeypatch, caplog):
    class Presa:
        ok = True
        status_code = 200

    monkeypatch.setattr(notifiche, "canale", lambda: CANALE)
    monkeypatch.setattr(notifiche.requests, "post", lambda *a, **k: Presa())
    with caplog.at_level(logging.WARNING):
        assert notifiche._invia_ntfy(TITOLO, TESTO, 4, "alarm_clock") is True
    assert _righe_ntfy(caplog) == []


def test_nelle_ore_tranquille_non_parte_niente_e_non_si_scrive_niente(monkeypatch, tmp_path, caplog):
    chiamate = []
    monkeypatch.setattr(notifiche, "canale", lambda: CANALE)
    monkeypatch.setattr(notifiche.requests, "post", lambda *a, **k: chiamate.append(a) or None)
    monkeypatch.setattr(notifiche, "in_silenzio", lambda *a, **k: True)
    with caplog.at_level(logging.WARNING):
        assert notifiche.invia(TITOLO, TESTO, 4, "alarm_clock", file_impostazioni=tmp_path / "av.json",
                               file_iscrizioni=tmp_path / "push.json") is False
    assert chiamate == [] and _righe_ntfy(caplog) == []


def test_la_riga_arriva_dove_la_legge_promemoria_sh():
    """Il comando del giro dei promemoria non configura i registri: la riga deve arrivare lo stesso sull'uscita degli errori, che
    `script/server/promemoria.sh` raccoglie in `dati/promemoria.log` (`2>&1`)."""
    codice = textwrap.dedent(f"""
        import requests
        from fanta import notifiche

        def rotto(*a, **k):
            raise requests.Timeout("lento")

        notifiche.canale = lambda: {CANALE!r}
        notifiche.requests.post = rotto
        notifiche._invia_ntfy({TITOLO!r}, {TESTO!r}, 4, "alarm_clock")
    """)
    r = subprocess.run([sys.executable, "-c", codice], cwd=RADICE, capture_output=True, text=True, encoding="utf-8",
                       timeout=120, env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stderr
    righe = [riga for riga in r.stderr.splitlines() if "ntfy" in riga]
    assert len(righe) == 1 and "Timeout" in righe[0], r.stderr
    _senza_dati(righe[0])
