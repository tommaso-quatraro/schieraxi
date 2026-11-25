"""Il primo avvio (`primoavvio.js`), passo «I tempi della lega»: due menu (quando si chiude la formazione, da quale giornata di Serie A
è partita la lega) che partono dai valori più comuni e si riempiono con le regole lette dal server. «Salva» scrive le regole con i
due valori dei menu: se la lettura non è riuscita, o non è ancora tornata, i valori di partenza andavano sopra quelli veri (#801).
Gira solo prima della scadenza: conta la guida, non la fase della giornata.
"""
import json
import re
from urllib.parse import urlsplit

import pytest

# rose e mia squadra le dà lo scenario registrato: la guida segna da sola i primi due passi e si apre sui tempi
ALL_INIZIO = {"primo_avvio": {"fatti": ["server", "accesso"], "saltati": [], "chiuso": False}}


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("conta la guida, non la fase della giornata")


def guida_sui_tempi(web, prima_lettura: str) -> tuple[list[dict], list]:
    """Apre la guida sul passo dei tempi. La prima lettura delle regole non arriva («rete») o resta in sospeso finché il test non
    la dà («tenuta»); le altre rispondono con le regole registrate. Restituisce le regole salvate (PUT) e le letture tenute."""
    registrate = web.registrata("/api/regole")
    salvate, tenute, letture = [], [], []

    def regole(route):
        if route.request.method == "PUT":
            salvate.append(json.loads(route.request.post_data))
            route.fulfill(status=200, content_type="application/json", body=json.dumps(registrate))
            return
        letture.append(1)
        if len(letture) == 1 and prima_lettura == "rete":
            route.abort()
        elif len(letture) == 1 and prima_lettura == "tenuta":
            tenute.append(route)
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(registrate))

    primo = dict(ALL_INIZIO["primo_avvio"])

    def primo_avvio(route):                                  # il server salva i passi fatti e li rimanda
        if route.request.method == "PUT":
            primo.update(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"primo_avvio": primo}))

    web.pagina.route(lambda u: urlsplit(u).path == "/api/primo-avvio", primo_avvio)
    web.apri("/")
    web.pagina.route(lambda u: urlsplit(u).path == "/api/regole", regole)
    web.pagina.evaluate("apriPrimoAvvio()")                  # come «Importa le rose» o la voce della guida in Da fare
    guida(web).get_by_role("heading", name="I tempi della lega").wait_for(timeout=10000)
    return salvate, tenute


def salvataggio(richiesta) -> bool:
    return richiesta.method == "PUT" and urlsplit(richiesta.url).path == "/api/regole"


def menu_vale(web, menu, valore) -> None:
    """Aspetta che il menu mostri `valore` (la rilettura delle regole arriva dopo l'avviso)."""
    from playwright.sync_api import expect                 # qui: la suite normale raccoglie questo file senza Playwright
    expect(menu).to_have_value(str(valore), timeout=10000)


def guida(web):
    return web.pagina.get_by_role("dialog")


def scadenza(web):
    return guida(web).get_by_label("Quando si chiude la formazione?")


def prima_giornata(web):
    return guida(web).get_by_label(re.compile("^Da quale giornata di Serie A"))


def test_le_giornate_della_prima_giornata_con_l_apostrofo(web):
    """Come in Regole e scadenza: «Dall'8ª» e «Dall'11ª», non «Dalla 8ª» (#842)."""
    solo_prima(web)
    guida_sui_tempi(web, "subito")
    voci = prima_giornata(web).locator("option").all_inner_texts()
    assert len(voci) == 38
    assert voci[7] == "Dall'8ª" and voci[10] == "Dall'11ª" and voci[1] == "Dalla 2ª", voci[:12]


def test_i_tempi_non_si_salvano_se_le_regole_non_si_sono_lette(web):
    """La lettura delle regole non arriva: «Salva» non scrive i valori di partenza sopra quelli veri, lo dice e rilegge; i menu
    passano ai valori salvati e «Salva» li scrive al tocco dopo."""
    solo_prima(web)
    registrate = web.registrata("/api/regole")
    salvate, _ = guida_sui_tempi(web, "rete")
    guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    guida(web).get_by_role("alert").filter(has_text="non ho salvato niente").wait_for(timeout=10000)
    web.aspetta()
    assert salvate == [], f"salvati i valori di partenza dei menu: {salvate}"
    menu_vale(web, scadenza(web), registrate["scadenza_minuti"])
    menu_vale(web, prima_giornata(web), registrate["prima_giornata_lega"])
    with web.pagina.expect_request(salvataggio):
        guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    web.aspetta()
    assert [(s["scadenza_minuti"], s["prima_giornata_lega"]) for s in salvate] == \
        [(registrate["scadenza_minuti"], registrate["prima_giornata_lega"])]


def test_i_tempi_aspettano_la_lettura_in_corso(web):
    """«Salva» toccato prima che la lettura delle regole torni (rete lenta): aspetta la lettura e scrive i valori veri."""
    solo_prima(web)
    registrate = web.registrata("/api/regole")
    salvate, tenute = guida_sui_tempi(web, "tenuta")
    assert len(tenute) == 1
    guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    web.aspetta()
    assert salvate == [], f"salvati i valori di partenza dei menu prima della lettura: {salvate}"
    with web.pagina.expect_request(salvataggio):
        tenute[0].fulfill(status=200, content_type="application/json", body=json.dumps(registrate))
    web.aspetta()
    assert [(s["scadenza_minuti"], s["prima_giornata_lega"]) for s in salvate] == \
        [(registrate["scadenza_minuti"], registrate["prima_giornata_lega"])]


def test_una_scelta_fatta_prima_della_lettura_resta(web):
    """Con la lettura ancora in volo si cambia la scadenza e si tocca «Salva»: quando la lettura torna non rimette il valore salvato
    sopra la scelta. Si salva la scadenza scelta e, per l'altra domanda, il valore letto."""
    solo_prima(web)
    registrate = web.registrata("/api/regole")
    assert registrate["scadenza_minuti"] != 30, "la prova vuole una scadenza diversa da quella scelta"
    salvate, tenute = guida_sui_tempi(web, "tenuta")
    scadenza(web).select_option("30")
    guida(web).get_by_role("button", name="Salva", exact=True).click(timeout=10000)
    with web.pagina.expect_request(salvataggio):
        tenute[0].fulfill(status=200, content_type="application/json", body=json.dumps(registrate))
    web.aspetta()
    assert [(s["scadenza_minuti"], s["prima_giornata_lega"]) for s in salvate] == [(30, registrate["prima_giornata_lega"])]


@pytest.mark.parametrize("squadre", ["non-lette", "lette-vuote"])
def test_la_guida_si_apre_da_sola_solo_con_le_squadre_lette_davvero(web, squadre):
    """#874: la guida parte da sola solo a chi non ha rose. Se all'avvio l'elenco delle squadre non arriva (server che riparte: 502),
    l'elenco vuoto non vuol dire che le rose non ci sono: la guida non si apre su «Importa le rose» e non salva i primi due passi
    come fatti. Prima si apriva anche a chi le rose le aveva. Con l'elenco letto davvero, e vuoto, si apre come sempre."""
    solo_prima(web)
    salvati, primo = [], {"fatti": [], "saltati": [], "chiuso": False}

    def primo_avvio(route):                                  # mai cominciato; il server salva i passi e li rimanda
        if route.request.method == "PUT":
            salvati.append(json.loads(route.request.post_data))
            primo.update(salvati[-1])
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"primo_avvio": primo if salvati else None}))

    web.pagina.route(lambda u: urlsplit(u).path == "/api/primo-avvio", primo_avvio)
    if squadre == "non-lette":
        web.risposta("/api/squadre", {"detail": "Il server non risponde"}, stato=502)
    else:
        web.risposta("/api/squadre", [])
    web.apri("/")
    if squadre == "lette-vuote":
        guida(web).wait_for(timeout=10000)
        assert [s.get("fatti") for s in salvati] == [["server", "accesso"]], salvati
        return
    web.aspetta()
    assert guida(web).count() == 0, "la guida del primo avvio si è aperta senza aver letto le squadre"
    assert salvati == [], f"salvato lo stato del primo avvio senza aver letto le squadre: {salvati}"
