"""Scheda del giocatore, «Tutti i numeri»: i numeri della fonte delle statistiche avanzate dicono fino a quando arrivano (#862).

Con la fonte ferma (dal 12/11/2026, #756) «Gol e assist rispetto alle occasioni» e «Statistiche avanzate» mostravano i numeri
dell'ultima partita letta senza una data. Il server manda il giorno (`avanzate.dati_fino_al`) e la web scrive «Dati fino al 9/11.»
(`mercato.dati_fino_al`, la stessa frase dell'iPhone) nei due blocchi. Un server di prima, senza il campo, non scrive niente.
Gli scenari registrati non hanno ancora il campo: lo aggiunge il test alla scheda registrata (`web.risposta`).
"""
import re

from test_formazione_unica import campo, scheda, solo, tocca

GIORNO = "2026-11-09"
FRASE = "Dati fino al 9/11."


def _cognome(nome: str) -> str:
    """Il nome come sta sul campo: senza l'iniziale («Fefo A.» → «Fefo»), come `cognome` di app.js."""
    return re.sub(r"\s+\S{1,3}\.$", "", nome)


def _con_i_due_blocchi(web, giorno: str | None) -> str:
    """Un titolare della consigliata registrata con le statistiche avanzate e il rendimento; la sua scheda risponde con
    `dati_fino_al` = `giorno` (senza il campo se `giorno` è None). Torna il suo cognome."""
    web.risposta("/api/scelta?giornata=9", None)                      # si parte dalla consigliata
    f = web.registrata("/api/formazione")
    titolari = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])["titolari"]
    for i in titolari:
        s = web.registrata(f"/api/giocatore/{i}")
        if (s.get("avanzate") or {}).get("minuti") and s.get("rendimento"):
            s["avanzate"].pop("dati_fino_al", None)
            if giorno:
                s["avanzate"]["dati_fino_al"] = giorno
            web.risposta(f"/api/giocatore/{i}", s)
            return _cognome(f["schede"][str(i)]["nome"])
    raise AssertionError("nello scenario registrato nessun titolare ha statistiche avanzate e rendimento: il test non proverebbe niente")


def _tutti_i_numeri(web, cognome: str) -> str:
    web.apri("/")
    tocca(web, campo(web).filter(has_text=cognome).first)
    tocca(web, scheda(web).get_by_text("Tutti i numeri"))
    return " ".join(scheda(web).inner_text().split())


def test_i_due_blocchi_della_fonte_dicono_fino_a_quando_arrivano_i_dati(web):
    solo(web, "prima")
    testo = _tutti_i_numeri(web, _con_i_due_blocchi(web, GIORNO))
    assert testo.count(FRASE) == 2, testo
    occasioni, stagione, avanzate = (testo.index(t) for t in ("Gol e assist rispetto alle occasioni", "Stagione", "Statistiche avanzate"))
    assert occasioni < testo.index(FRASE) < stagione, "nel blocco «Gol e assist rispetto alle occasioni»"
    assert testo.index(FRASE, avanzate) == testo.index("Statistiche avanzate") + len("Statistiche avanzate") + 1, \
        "subito sotto il titolo «Statistiche avanzate», prima dei numeri"
    assert not web.errori_console, web.errori_console


def test_un_server_senza_la_data_non_scrive_la_riga(web):
    solo(web, "prima")
    testo = _tutti_i_numeri(web, _con_i_due_blocchi(web, None))
    assert "Statistiche avanzate" in testo and "Gol e assist rispetto alle occasioni" in testo
    assert "Dati fino al" not in testo and "undefined" not in testo and "null" not in testo
    assert not web.errori_console, web.errori_console
