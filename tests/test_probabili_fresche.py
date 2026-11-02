"""Oggi: quanto sono fresche le probabili formazioni (testo semplice, plurali giusti, avviso se vecchie vicino alla scadenza)."""
from datetime import datetime

from fanta.gestione import _eta_testo, freschezza_probabili

ADESSO = datetime(2026, 10, 31, 15, 0)


def test_eta_con_plurali_giusti():
    assert _eta_testo(0) == "meno di un minuto fa"
    assert _eta_testo(1) == "1 minuto fa"
    assert _eta_testo(2) == "2 minuti fa"
    assert _eta_testo(60) == "1 ora fa"
    assert _eta_testo(180) == "3 ore fa"
    assert _eta_testo(60 * 72) == "3 giorni fa"


def test_testo_con_l_ora_della_rilevazione():
    f = freschezza_probabili("2026-10-31T13:05:44", ADESSO, 30)
    assert f["testo"] == "Probabili aggiornate alle 13:05"
    assert f["aggiornate_il"] == "2026-10-31 13:05" and f["minuti_fa"] == 114
    assert f["eta"] == "1 ora fa" and not f["vecchie"] and f["avviso"] is None


def test_ieri_e_giorni_prima():
    assert freschezza_probabili("2026-10-30T22:10:00", ADESSO, None)["testo"] == "Probabili aggiornate ieri alle 22:10"
    assert freschezza_probabili("2026-10-28T09:00:00", ADESSO, None)["testo"] == "Probabili aggiornate il 28/10 alle 09:00"


def test_avviso_solo_se_vecchie_e_partita_vicina():
    vecchie = freschezza_probabili("2026-10-31T08:00:00", ADESSO, 1.0)
    assert vecchie["vecchie"] and "7 ore fa" in vecchie["avviso"] and "tra 1 ora" in vecchie["avviso"]
    assert freschezza_probabili("2026-10-31T08:00:00", ADESSO, 3.0)["avviso"].count("tra 3 ore") == 1
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, 40)["vecchie"]       # la partita è lontana
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, -2)["vecchie"]       # già iniziata
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, None)["vecchie"]
    assert not freschezza_probabili("2026-10-31T10:00:00", ADESSO, 2)["vecchie"]        # 5 ore: ancora fresche


def test_senza_ora_nessun_campo():
    assert freschezza_probabili(None, ADESSO, 2) is None
    assert freschezza_probabili("boh", ADESSO, 2) is None
