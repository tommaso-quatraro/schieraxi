"""La schermata «Formazione» unica (#616): risponde a «chi schiero» nel primo schermo del telefono, nelle tre fasi della giornata.

Al posto di Oggi e Formazione: testa con giornata e scadenza (o i punti, a giornata in corso e finita), al massimo due decisioni,
il modulo come menu, il campo con gli 11, lo stato della scelta con «Copia per l'app della lega» e la spunta «L'ho messa». Il
salvataggio è automatico. Si guarda ciò che vede e fa chi usa l'app; il server finto non salva niente, quindi dove serve la
memoria (la spunta che resta dopo una ricarica) il test tiene lui la scelta salvata e risponde al posto del server.
"""
import json
from urllib.parse import urlsplit

import pytest

PC = 1440
ETICHETTE_TOLTE = ("Probabile titolare", "In ballottaggio", "Probabile panchina", "Improbabile")


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def campo(web):
    """Il campo con gli 11: ogni titolare è un pulsante."""
    return principale(web).locator("#campo-formazione").get_by_role("button")


def nomi_sul_campo(web) -> list[str]:
    """I cognomi sul campo, dal nome che sente un lettore di schermo («Rossi, fantavoto atteso 6,8…»)."""
    return [t.split("\n")[-1].split(",")[0].strip() for t in campo(web).all_inner_texts()]


def stato(web) -> str:
    """La riga dello stato della scelta, sotto il campo."""
    return " ".join(principale(web).locator("#stato-scelta").inner_text().split())


def tocca(web, bersaglio) -> None:
    bersaglio.click(timeout=10000)
    web.aspetta()


def scheda(web):
    return web.pagina.get_by_role("dialog")


def scritture(web) -> list[tuple[str, str, dict | None]]:
    """Le richieste che scrivono, raccolte da qui in poi: (metodo, percorso con la query, corpo JSON)."""
    viste = []

    def nota(r):
        parti = urlsplit(r.url)
        if r.method != "GET" and parti.path.startswith("/api/"):
            viste.append((r.method, parti.path + ("?" + parti.query if parti.query else ""), json.loads(r.post_data) if r.post_data else None))

    web.pagina.on("request", nota)
    return viste


# ---------------------------------------------------------------- gli 11 nel primo schermo
def test_i_nomi_degli_11_stanno_nel_primo_schermo_del_telefono(web):
    """A 390×844 px, in tutte e tre le fasi: ogni titolare (numero e cognome) sta sopra la barra in basso, senza scorrere."""
    web.apri("/", larghezza=390)
    assert campo(web).count() == 11, f"{web.fase}: sul campo non ci sono 11 titolari"
    barra = web.pagina.get_by_role("navigation", name="Sezioni").bounding_box()
    fuori = [nome for nome, b in zip(nomi_sul_campo(web), [p.bounding_box() for p in campo(web).all()])
             if b["y"] < 0 or b["y"] + b["height"] > barra["y"]]
    assert not fuori, f"{web.fase}: fuori dal primo schermo: {', '.join(fuori)}"
    assert web.pagina.evaluate("window.scrollY") == 0
    assert not web.scorre_di_lato() and not web.errori_mostrati() and not web.errori_console


def test_il_vecchio_indirizzo_di_oggi_apre_la_formazione(web):
    web.apri("/?vista=oggi")
    assert principale(web).get_by_role("heading", level=1).inner_text().strip() == "Formazione"
    assert web.pagina.url.endswith("/?vista=formazione")
    assert campo(web).count() == 11
    schede = [" ".join(v.split()) for v in web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link").all_inner_texts()]
    assert schede == ["Formazione", "Squadra", "Altro"]


# ---------------------------------------------------------------- il giocatore: due numeri, e parole solo se servono
def test_gioca_si_vede_solo_sotto_l_80_per_cento_e_niente_etichette_di_titolarita(web):
    solo(web, "prima")
    web.apri("/")
    f = web.registrata("/api/formazione")
    titolari = web.registrata("/api/scelta?giornata=9")["titolari"]
    attesi = {f["schede"][str(i)]["nome"].split()[0] for i in titolari if int(f["schede"][str(i)]["p_voto"] * 100 + 0.5) < 80}
    assert attesi, "nello scenario registrato nessun titolare è sotto l'80%: il test non proverebbe niente"
    con_gioca = {t.split("\n")[-1].split(",")[0].split()[0] for t in campo(web).all_inner_texts() if "gioca" in t.split("\n")[-1]}
    assert con_gioca == attesi
    testo = web.testo_principale()
    for tolta in ETICHETTE_TOLTE:
        assert tolta not in testo, tolta
    assert "vs " not in " ".join(campo(web).all_inner_texts())        # l'avversario non sta più sul campo: è nella scheda


def test_un_tocco_su_un_titolare_apre_la_scheda_con_sostituisci(web):
    solo(web, "prima")
    web.apri("/")
    nome = nomi_sul_campo(web)[0]
    tocca(web, campo(web).first)
    assert nome.split()[0] in scheda(web).get_by_role("heading").first.inner_text()
    testo = scheda(web).inner_text()
    assert "Fantavoto atteso" in testo and "se gioca" in testo and "Ultimi voti" in testo
    assert scheda(web).get_by_role("button", name="Sostituisci").is_visible()
    assert scheda(web).get_by_text("Tutti i numeri").is_visible()
    for tolta in ETICHETTE_TOLTE + ("Confronta", "quotazione"):
        assert tolta not in testo, tolta


# ---------------------------------------------------------------- salvataggio automatico e stato della scelta
def test_dopo_una_sostituzione_lo_stato_dice_che_l_hai_cambiata_tu_ed_e_salvata(web):
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)                       # niente di salvato: si parte dalla consigliata
    web.apri("/")
    assert stato(web) == "È la consigliata."
    prima = nomi_sul_campo(web)
    scritte = scritture(web)
    tocca(web, campo(web).nth(3))
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    assert "Al posto di" in scheda(web).get_by_role("heading").first.inner_text()
    tocca(web, scheda(web).get_by_role("listitem").first.get_by_role("button"))
    dopo = nomi_sul_campo(web)
    assert len(dopo) == 11 and len(set(dopo) - set(prima)) == 1 and len(set(prima) - set(dopo)) == 1, (prima, dopo)
    assert stato(web).startswith("L'hai cambiata tu: 1 titolare diverso dalla consigliata")
    salvate = [(m, p, c) for m, p, c in scritte if p == "/api/formazione/valuta"]
    assert len(salvate) == 1 and salvate[0][2]["salva"] is True and len(set(salvate[0][2]["titolari"])) == 11
    assert not web.errori_mostrati() and not web.errori_console


def test_torna_alla_consigliata_toglie_la_scelta_salvata(web):
    solo(web, "prima")
    web.apri("/")                                                     # nello scenario registrato c'è una scelta fatta a mano
    assert stato(web).startswith("L'hai cambiata tu")
    scritte = scritture(web)
    tocca(web, principale(web).get_by_role("button", name="Torna alla consigliata"))
    assert stato(web) == "È la consigliata."
    assert [(m, p) for m, p, _ in scritte] == [("DELETE", "/api/scelta?giornata=9")]
    assert principale(web).get_by_role("button", name="Torna alla consigliata").count() == 0


def test_il_modulo_e_un_menu_e_un_altro_modulo_si_salva(web):
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    f = web.registrata("/api/formazione")
    menu = principale(web).get_by_label("Modulo")
    assert menu.locator("option").count() == len(f["moduli"]) >= 3
    altro = next(m for m in f["moduli"] if m["modulo"] != f["modulo"])
    scritte = scritture(web)
    menu.select_option(altro["modulo"])
    web.aspetta()
    assert stato(web).startswith("L'hai cambiata tu")
    assert scritte[-1][1] == "/api/formazione/valuta" and scritte[-1][2]["salva"] is True
    assert sorted(scritte[-1][2]["titolari"]) == sorted(altro["titolari"])
    assert principale(web).get_by_label("Modulo").input_value() == altro["modulo"]
    principale(web).get_by_label("Modulo").select_option(f["modulo"])          # il modulo consigliato: si torna alla consigliata
    web.aspetta()
    assert stato(web) == "È la consigliata." and scritte[-1][:2] == ("DELETE", "/api/scelta?giornata=9")


def test_la_spunta_l_ho_messa_resta_dopo_una_ricarica(web):
    """La spunta si salva sul server (campo `messa` della scelta) e torna con la scelta: qui il test fa la parte del server."""
    solo(web, "prima")
    salvata = {"scelta": None}

    def scelta(route):
        if route.request.method == "DELETE":
            salvata["scelta"] = None
            return route.fulfill(status=200, content_type="application/json", body='{"ok": true}')
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(salvata["scelta"]))

    def valuta(route):
        corpo = json.loads(route.request.post_data)
        if corpo.get("salva"):
            salvata["scelta"] = {"titolari": corpo["titolari"], "modulo": "4-3-3", "salvata": "2026-10-27T15:10:00", "tipo": "manuale",
                                 **({"messa": True, "messa_il": "2026-10-27T15:10:00"} if corpo.get("messa") else {})}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(web.registrata("/api/formazione/valuta")))

    web.pagina.route(lambda u: urlsplit(u).path == "/api/scelta", scelta)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/formazione/valuta", valuta)
    web.apri("/")
    casella = principale(web).get_by_role("checkbox", name="L'ho messa")
    assert not casella.is_checked()
    casella.check()
    web.aspetta()
    assert salvata["scelta"] and salvata["scelta"]["messa"] is True and len(salvata["scelta"]["titolari"]) == 11
    web.pagina.evaluate("localStorage.clear()")                       # niente copia sul telefono: dopo la ricarica vale ciò che dice il server
    web.apri("/")
    casella = principale(web).get_by_role("checkbox", name="L'ho messa")
    assert casella.is_checked() and stato(web) == "È la consigliata."
    casella.uncheck()                                                 # tolta su una formazione che è ancora la consigliata: non resta fissata
    web.aspetta()
    assert salvata["scelta"] is None
    web.pagina.evaluate("localStorage.clear()")
    web.apri("/")
    assert not principale(web).get_by_role("checkbox", name="L'ho messa").is_checked()
    assert not web.errori_mostrati() and not web.errori_console


def test_copia_per_l_app_della_lega_sta_sotto_il_campo(web):
    solo(web, "prima", "finita")
    web.apri("/")
    assert principale(web).get_by_role("button", name="Copia per l'app della lega").is_visible()
    assert principale(web).get_by_role("checkbox", name="L'ho messa").is_visible()


# ---------------------------------------------------------------- le decisioni in cima: al massimo due, solo con un'azione
def _con_da_fare(web, da_fare: list[dict]) -> None:
    web.risposta("/api/oggi", {**web.registrata("/api/oggi"), "da_fare": da_fare})
    web.apri("/")


def _decisioni(web):
    return principale(web).get_by_role("list", name="Da fare").get_by_role("listitem")


def test_al_massimo_due_decisioni_e_solo_quelle_con_un_azione(web):
    solo(web, "prima")
    f = web.registrata("/api/formazione")
    titolari = web.registrata("/api/scelta?giornata=9")["titolari"]
    esce = next(f["schede"][str(i)] for i in titolari if f["schede"][str(i)]["ruolo"] == "C")
    entra = next(x for x in f["schede"].values() if x["ruolo"] == "C" and x["id"] not in titolari)
    _con_da_fare(web, [
        {"id": f"dubbio:{esce['id']}", "tipo": "dubbio", "testo": f"{esce['nome']} è in dubbio (45% di giocare). Meglio {entra['nome']}.", "priorita": 2,
         "azione": "Sostituisci", "destinazione": {"scheda": "formazione", "sezione": None, "giocatore": esce["id"]},
         "giocatore": {"id": esce["id"], "nome": esce["nome"]},
         "alternativa": {"id": entra["id"], "nome": entra["nome"], "ruolo": "C", "punti_attesi": esce["punti_attesi"] + 0.9}},
        {"id": "dubbio:1", "tipo": "dubbio", "testo": "Esempio è in dubbio (55% di giocare) ma resta titolare: se non gioca entra Prova dalla panchina.",
         "priorita": 2, "azione": "Apri la formazione", "destinazione": {"scheda": "formazione", "sezione": None}},
        {"id": "formazione:9", "tipo": "formazione", "testo": "La formazione si chiude tra 3 ore e non l'hai ancora salvata.", "priorita": 2,
         "azione": "Apri la formazione", "destinazione": {"scheda": "formazione", "sezione": None}},
        {"id": "rose-vecchie", "tipo": "rose", "testo": "È il momento di aste e scambi nella lega: se le rose sono cambiate, aggiornale.", "priorita": 2,
         "azione": "Aggiorna le rose", "destinazione": {"scheda": "lega", "sezione": "rose"}},
        {"id": "diario:8", "tipo": "diario", "testo": "Giornata 5: è finita, dimmi se hai schierato la consigliata.", "priorita": 3,
         "azione": "Ho schierato la consigliata", "destinazione": {"scheda": "lega", "sezione": "diario", "giornata": 8}, "giornata": 8},
    ])
    righe = [" ".join(r.split()) for r in _decisioni(web).all_inner_texts()]
    assert len(righe) == 2, righe
    assert righe[0].startswith(f"{esce['nome']} è in dubbio") and "+0,9 punti" in righe[0] and righe[0].endswith("Sostituisci")
    assert righe[1].endswith("Aggiorna le rose")
    testo = web.testo_principale()
    assert "resta titolare" not in testo and "non l'hai ancora salvata" not in testo and "dimmi se hai schierato" not in testo
    # il pulsante della decisione fa il cambio, che si salva da solo; la decisione fatta sparisce
    scritte = scritture(web)
    tocca(web, _decisioni(web).first.get_by_role("button", name="Sostituisci"))
    assert scritte[-1][1] == "/api/formazione/valuta" and scritte[-1][2]["salva"] is True
    assert entra["id"] in scritte[-1][2]["titolari"] and esce["id"] not in scritte[-1][2]["titolari"]
    assert _decisioni(web).count() == 1 and "Sostituisci" not in " ".join(_decisioni(web).all_inner_texts())
    assert entra["nome"].split()[0] in " ".join(nomi_sul_campo(web))


def test_senza_decisioni_non_c_e_nessun_elenco_di_cose_da_fare(web):
    solo(web, "prima")
    _con_da_fare(web, [{"id": "dubbio:1", "tipo": "dubbio", "testo": "Esempio (in ballottaggio, gioca 66%) resta titolare: se non gioca entra Prova dalla panchina.",
                        "priorita": 2, "azione": "Apri la formazione", "destinazione": {"scheda": "formazione", "sezione": None}}])
    assert principale(web).get_by_role("list", name="Da fare").count() == 0
    assert "Tutto a posto" not in web.testo_principale() and "resta titolare" not in web.testo_principale()


def test_la_consigliata_cambiata_si_prende_con_un_tocco(web):
    solo(web, "prima")
    _con_da_fare(web, [{"id": "consigliata:9", "tipo": "formazione", "priorita": 2, "azione": "Apri la formazione",
                        "testo": "La consigliata è cambiata da quando l'hai salvata: rivedila. Ora schiera Prova al posto di Esempio.",
                        "destinazione": {"scheda": "formazione", "sezione": None}}])
    scritte = scritture(web)
    tocca(web, _decisioni(web).first.get_by_role("button", name="Usa la consigliata"))
    assert [(m, p) for m, p, _ in scritte] == [("DELETE", "/api/scelta?giornata=9")]
    assert stato(web) == "È la consigliata." and principale(web).get_by_role("list", name="Da fare").count() == 0


# ---------------------------------------------------------------- le altre due fasi: la stessa schermata con la testa diversa
def test_a_giornata_in_corso_la_testa_ha_i_punti_e_la_formazione_non_si_cambia(web):
    solo(web, "in-corso")
    web.apri("/")
    oggi = web.registrata("/api/oggi")
    testo = web.testo_principale()
    assert "in corso" in testo and "punti finora" in testo and f"{oggi['in_corso']['punti_fatti']:.1f}".replace(".", ",") in testo
    assert principale(web).get_by_label("Modulo").count() == 0
    assert principale(web).get_by_role("checkbox", name="L'ho messa").count() == 0
    assert "la formazione è chiusa" in stato(web)
    tocca(web, campo(web).first)
    assert scheda(web).get_by_role("heading").first.is_visible()
    assert scheda(web).get_by_role("button", name="Sostituisci").count() == 0


def test_a_giornata_finita_c_e_com_e_andata_e_sotto_la_formazione_della_prossima(web):
    solo(web, "finita")
    web.apri("/")
    riepilogo = web.registrata("/api/oggi")["riepilogo"]
    testo = web.testo_principale()
    assert "finita" in testo and f"{riepilogo['punti_fatti']:.1f}".replace(".", ",") in testo and "attesi" in testo
    assert "Si chiude" in testo and principale(web).get_by_label("Modulo").count() == 1        # la prossima si può già preparare
    tocca(web, principale(web).get_by_role("button", name="Com'è andata"))
    assert scheda(web).get_by_role("heading").first.is_visible()
    assert not web.errori_console


# ---------------------------------------------------------------- tablet e PC
@pytest.mark.parametrize("larghezza", [768, 1024, PC])
def test_su_tablet_e_pc_il_campo_sta_a_sinistra_e_la_panchina_a_destra(web, larghezza):
    solo(web, "prima")
    web.apri("/", larghezza=larghezza)
    c = principale(web).locator("#campo-formazione").bounding_box()
    p = principale(web).get_by_role("heading", name="Panchina").bounding_box()
    assert c["x"] + c["width"] <= p["x"], "la panchina non sta a destra del campo"
    assert p["y"] < 600, "la panchina non comincia nel primo schermo"
    assert not web.scorre_di_lato()


def test_sul_pc_la_scheda_si_apre_nel_pannello_a_fianco(web):
    solo(web, "prima")
    web.apri("/", larghezza=PC)
    tocca(web, campo(web).first)
    pannello = scheda(web).bounding_box()
    c = principale(web).locator("#campo-formazione").bounding_box()
    assert pannello["x"] >= c["x"] + c["width"], "il pannello copre il campo"
    assert scheda(web).get_attribute("aria-modal") != "true"
    tocca(web, campo(web).nth(1))                                     # la pagina accanto resta attiva: un altro giocatore cambia il pannello
    assert nomi_sul_campo(web)[1].split()[0] in scheda(web).get_by_role("heading").first.inner_text()
