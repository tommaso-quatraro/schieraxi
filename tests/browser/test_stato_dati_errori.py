"""Stato dei dati dopo un «Aggiorna i dati» non riuscito (collaudo della web in inglese del 27/11/2026): sotto ogni riga una frase
semplice del server con la sua chiave (`errori_frasi`, fanta/stato_dati.py), che la web traduce; mai il messaggio tecnico
(«ProxyError: HTTPSConnectionPool…»), che resta nel registro del server. In italiano la web mostra il testo del server com'è
(l'iPhone legge lo stesso campo `errori`). La risposta qui sotto ha la forma che scrive `stato_dati.riepilogo`
(tests/test_aggiorna_senza_rete.py la prova sul server)."""
import pytest


def _giorno(chiave_giorno: str, n: int) -> dict:
    return {"chiave": "data.giorno_mese", "param": {"giorno": {"chiave": f"giorno.{chiave_giorno}", "param": {}}, "n": n,
                                                     "mese": {"chiave": "mese.nov", "param": {}}}}


LISTONE = {"cosa": "listone", "quando": None, "etichetta": "Listone e quotazioni",
           "etichetta_frase": {"chiave": "aggiornamento.listone", "param": {}},
           "errori": ["Non riuscito ven 27 nov alle 11:31: Fantacalcio.it non risponde."],
           "errori_frasi": [{"chiave": "aggiornamento.non_riuscito", "param": {
               "quando": _giorno("ven", 27), "ora": "11:31",
               "motivo": {"chiave": "aggiornamento.motivo_rete", "param": {"fonte": "Fantacalcio.it"}}}}]}
UNDERSTAT = {"cosa": "understat", "quando": "2026-11-20T08:03:00", "etichetta": "Statistiche avanzate",
             "etichetta_frase": {"chiave": "aggiornamento.understat", "param": {}},
             "errori": ["Fermo da 3 giorni, non riesce da mar 24 nov alle 08:03: il dettaglio è nel registro del server."],
             "errori_frasi": [{"chiave": "aggiornamento.fermo", "param": {
                 "durata": {"chiave": "tempo.giorni", "param": {"n": 3}}, "quando": _giorno("mar", 24), "ora": "08:03",
                 "motivo": {"chiave": "aggiornamento.motivo_registro", "param": {}}}}]}
GENERALE = {"cosa": "aggiornamento", "quando": "2026-11-26T23:55:13", "etichetta": "Aggiornamento generale",
            "etichetta_frase": {"chiave": "aggiornamento.aggiornamento", "param": {}},
            "errori": ["Non riusciti: Listone e quotazioni, Statistiche avanzate."],
            "errori_frasi": [{"chiave": "aggiornamento.non_riusciti", "param": {"n": 2, "passi": {"chiave": "elenco", "param": {
                "parti": [{"chiave": "aggiornamento.listone", "param": {}}, {"chiave": "aggiornamento.understat", "param": {}}],
                "sep": ", "}}}}]}


def _stato_dei_dati(web, lingua: str) -> str:
    if web.fase != "prima":
        pytest.skip("una fase basta: Stato dei dati non dipende dal momento della giornata")
    if lingua == "en":
        web.memoria({"lingua": "en"})
    s = web.registrata("/api/stato-dati")
    s["aggiornamenti"] = [GENERALE, LISTONE, UNDERSTAT]
    web.risposta("/api/stato-dati", s)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    web.pagina.locator("main").get_by_role("button", name="Open the data status" if lingua == "en" else "Apri lo stato dei dati") \
        .click(timeout=10000)
    foglio = web.pagina.get_by_role("dialog")
    foglio.get_by_text("Statistiche avanzate" if lingua == "it" else "Advanced statistics", exact=True).wait_for(timeout=10000)
    web.aspetta()
    return " ".join(foglio.inner_text().split())


def test_in_inglese_le_righe_d_errore_sono_tradotte(web):
    testo = _stato_dei_dati(web, "en")
    for atteso in ("Failed: Player list and prices, Advanced statistics.",
                   "Failed on Fri 27 Nov at 11:31: Fantacalcio.it is not responding.",
                   "Stuck for 3 days, failing since Tue 24 Nov at 08:03: the details are in the server log."):
        assert atteso in testo, (atteso, testo[:600])
    assert "Non riuscit" not in testo and "registro" not in testo, testo[:600]


def test_in_italiano_le_righe_d_errore_sono_quelle_del_server(web):
    testo = _stato_dei_dati(web, "it")
    for e in (*GENERALE["errori"], *LISTONE["errori"], *UNDERSTAT["errori"]):
        assert e in testo, (e, testo[:600])
