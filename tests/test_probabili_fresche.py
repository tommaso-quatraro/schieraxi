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


def test_apostrofo_davanti_all_8_e_all_11():
    """«l'8/10», «l'11/10» (si legge «l'otto», «l'undici»), mai «il 8/10» o «il 11/10» (#859). Le altre date restano: «il 1/10»
    (il primo), «il 18/10». La web e l'iPhone mostrano il testo del server: la frase giusta si scrive qui."""
    def testo(rilevato):
        return freschezza_probabili(rilevato, ADESSO, None)["testo"]
    assert testo("2026-10-08T09:00:00") == "Probabili aggiornate l'8/10 alle 09:00"
    assert testo("2026-10-11T21:30:00") == "Probabili aggiornate l'11/10 alle 21:30"
    assert testo("2026-10-01T09:00:00") == "Probabili aggiornate il 1/10 alle 09:00"
    assert testo("2026-10-18T09:00:00") == "Probabili aggiornate il 18/10 alle 09:00"
    f = freschezza_probabili("2026-10-08T09:00:00", ADESSO, None)["frase"]
    assert f == {"chiave": "probabili.data", "param": {"giorno": 8, "mese": 10, "ora": "09:00"}}       # i numeri restano com'erano


def test_avviso_solo_se_vecchie_e_partita_vicina():
    vecchie = freschezza_probabili("2026-10-31T08:00:00", ADESSO, 1.0)
    assert vecchie["vecchie"] and vecchie["avviso"]
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, 40)["vecchie"]       # la partita è lontana
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, -2)["vecchie"]       # già iniziata
    assert not freschezza_probabili("2026-10-31T08:00:00", ADESSO, None)["vecchie"]
    assert not freschezza_probabili("2026-10-31T10:00:00", ADESSO, 2)["vecchie"]        # 5 ore: ancora fresche


def test_avviso_non_ripete_quando_sono_state_lette_ne_quando_si_chiude():
    """#923: nella Formazione l'avviso sta sotto «Probabili aggiornate alle 08:00 (7 ore fa)», e la testata dice già «Si chiude
    oggi 18:00 fra 3 h»: l'avviso dice solo cosa fare, senza un altro «7 ore fa» né le ore alla scadenza (prima «Le ho lette 7 ore
    fa e la formazione si chiude tra 3 ore: …», con «tra» mentre la testata dice «fra»)."""
    f = freschezza_probabili("2026-10-31T08:00:00", ADESSO, 3.0)
    assert f["avviso"] == "Le probabili potrebbero essere cambiate: ricontrollale prima che si chiuda la formazione."
    assert f["eta"] not in f["avviso"] and "ore" not in f["avviso"]
    # i parametri restano per le pagine web in inglese rimaste in memoria: il loro testi.js traduce ancora con «{eta}» e «{tempo}»
    assert f["avviso_frase"] == {"chiave": "probabili.vecchie",
                                 "param": {"eta": {"chiave": "tempo.ore_fa", "param": {"n": 7}}, "tempo": {"chiave": "tempo.ore", "param": {"n": 3}}}}


def test_senza_ora_nessun_campo():
    assert freschezza_probabili(None, ADESSO, 2) is None
    assert freschezza_probabili("boh", ADESSO, 2) is None
