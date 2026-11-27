"""Rosa incompleta (collaudo dell'amico nuovo del 27/11): con 9 giocatori la Formazione diceva «Non si riesce a formare una squadra: in
qualche ruolo nessuno gioca questa giornata» con «Riprova» e «Apri La mia lega» attaccati, e il server rispondeva 400 a ogni apertura
(un errore nella console ogni volta).

Ora lo stato d'avvio (`rosa_incompleta` di /api/stato) dice alla web di non chiedere la Formazione, e Oggi manda la frase con la causa
vera (`rosa_incompleta`): la pagina la mostra come uno stato, non come un errore, con «Aggiorna le rose». Se lo stato d'avvio è
vecchio vale quello che dice Oggi. La pagina d'errore ha «Riprova» e «Apri La mia lega» nella stessa fila, staccati. Girano solo
prima della scadenza: conta lo stato della rosa, non la fase della giornata."""
import pytest

TESTO = ("Non si riesce a formare una squadra: secondo le regole della lega, alla rosa di Squadra di prova mancano 1 portiere, "
         "6 difensori, 6 centrocampisti e 4 attaccanti.")
FRASE = {"chiave": "formazione.rosa_incompleta", "param": {"squadra": "Squadra di prova", "n": 17, "elenco": {
    "chiave": "elenco_e", "param": {"parti": [{"chiave": "rose.portieri", "param": {"n": 1}}, {"chiave": "rose.difensori", "param": {"n": 6}},
                                              {"chiave": "rose.centrocampisti", "param": {"n": 6}},
                                              {"chiave": "rose.attaccanti", "param": {"n": 4}}], "sep": ", "}}}}
ERRORE_400 = {"detail": TESTO, "codice": "rosa_incompleta"}


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("conta lo stato della rosa, non la fase della giornata")


def rosa_incompleta(web, stato_dice: bool = True, oggi_dice: bool = True) -> None:
    """Prima di `apri`: il server con una rosa che non basta. `stato_dice`/`oggi_dice`: se /api/stato e /api/oggi lo dicono (uno dei
    due può essere vecchio); la Formazione risponde 400 come il server."""
    stato, oggi = web.registrata("/api/stato"), web.registrata("/api/oggi")
    web.risposta("/api/stato", {**stato, "rosa_incompleta": stato_dice})
    if oggi_dice:
        web.risposta("/api/oggi", {**oggi, "rosa_incompleta": {"testo": TESTO, "frase": FRASE},
                                   "formazione": {**oggi["formazione"], "modulo": "–", "punteggio_atteso": None}})
    web.risposta("/api/formazione", ERRORE_400, stato=400)


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_la_formazione_dice_quanti_mancano_come_uno_stato_senza_chiederla(web, larghezza):
    solo_prima(web)
    rosa_incompleta(web)
    web.apri("/", larghezza=larghezza)
    principale = web.pagina.locator("main")
    assert TESTO in " ".join(web.testo_principale().split()), web.testo_principale()[:400]
    assert "/api/formazione" not in web.richieste, web.richieste
    assert not web.richieste_fallite and not web.errori_console and not web.errori_mostrati(), (
        web.richieste_fallite, web.errori_console, web.errori_mostrati())
    assert principale.get_by_role("button", name="Riprova").count() == 0
    principale.get_by_role("button", name="Aggiorna le rose").click(timeout=10000)
    web.aspetta()
    assert "gruppo=rose" in web.pagina.url, web.pagina.url


def test_in_inglese_la_frase_della_rosa_incompleta_si_traduce(web):
    solo_prima(web)
    rosa_incompleta(web)
    web.memoria({"lingua": "en"})
    web.apri("/")
    testo = " ".join(web.testo_principale().split())
    assert "the Squadra di prova roster is missing 1 goalkeeper, 6 defenders, 6 midfielders and 4 forwards" in testo, testo[:400]


def test_con_lo_stato_d_avvio_vecchio_vale_quello_che_dice_oggi(web):
    """Lo stato d'avvio non lo sa ancora (rose cambiate da un altro dispositivo): la Formazione risponde 400 una volta, ma la pagina
    mostra lo stato che dice Oggi, non un errore con «Riprova»."""
    solo_prima(web)
    rosa_incompleta(web, stato_dice=False)
    web.apri("/")
    assert TESTO in " ".join(web.testo_principale().split()), web.testo_principale()[:400]
    assert not web.errori_mostrati() and "Riprova" not in web.testo_principale(), web.testo_principale()[:300]


def test_con_lo_stato_d_avvio_vecchio_al_contrario_la_formazione_arriva(web):
    """Lo stato d'avvio dice ancora «rosa incompleta» ma la rosa adesso basta (Oggi non lo dice): la Formazione si chiede e si vede."""
    solo_prima(web)
    stato = web.registrata("/api/stato")
    web.risposta("/api/stato", {**stato, "rosa_incompleta": True})
    web.apri("/")
    assert "/api/formazione" in web.richieste and "punti attesi" in web.testo_principale(), web.testo_principale()[:300]
    assert TESTO not in web.testo_principale()


def test_la_pagina_d_errore_ha_riprova_e_la_mia_lega_staccati(web):
    """Un errore della Formazione che parla della rosa: «Riprova» e «Apri La mia lega» stavano uno sopra l'altro, attaccati."""
    solo_prima(web)
    web.risposta("/api/formazione", {"detail": "Squadra non trovata: indica la tua squadra in «La mia squadra»"}, stato=400)
    web.apri("/")
    principale = web.pagina.locator("main")
    riprova, lega = principale.get_by_role("button", name="Riprova"), principale.get_by_role("button", name="Apri La mia lega")
    a, b = riprova.bounding_box(), lega.bounding_box()
    stacco = max(b["y"] - (a["y"] + a["height"]), b["x"] - (a["x"] + a["width"]))
    assert stacco >= 8, (a, b)
