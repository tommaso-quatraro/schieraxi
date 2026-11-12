"""La schermata «Formazione» unica (#616): risponde a «chi schiero» nel primo schermo del telefono, nelle tre fasi della giornata.

Al posto di Oggi e Formazione: testa con giornata e scadenza (o i punti, a giornata in corso e finita), al massimo due decisioni,
il modulo come menu, il campo con gli 11, lo stato della scelta con «Copia per l'app della lega» e la spunta «L'ho messa». Il
salvataggio è automatico. Si guarda ciò che vede e fa chi usa l'app; il server finto non salva niente, quindi dove serve la
memoria (la spunta che resta dopo una ricarica) il test tiene lui la scelta salvata e risponde al posto del server.
"""
import json
import re
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
    assert schede == ["Formazione", "Giornate", "Impostazioni"]                # Giornate (#617) e Impostazioni (#618) dal 12/11/2026


def test_un_account_senza_rose_vede_il_benvenuto_e_nessuna_richiesta_fallisce(web):
    """Chi è appena entrato non ha rose: la Formazione dà il benvenuto e non chiede la formazione, che il server rifiuterebbe
    (409): un rifiuto, anche se la pagina lo regge, resta scritto fra gli errori del browser."""
    solo(web, "prima")
    web.risposta("/api/stato", {**web.registrata("/api/stato"), "rose_importate": False, "mia_squadra": None})
    web.risposta("/api/oggi", {**web.registrata("/api/oggi"), "senza_rose": True, "da_fare": []})
    web.risposta("/api/formazione", {"detail": "Nessuna rosa importata: importa le rose della tua lega."}, stato=409)
    web.apri("/")
    assert "Benvenuto in SchieraXI" in web.testo_principale()
    assert principale(web).get_by_role("button", name="Importa le rose").is_visible()
    assert "/api/formazione" not in web.richieste
    assert not web.richieste_fallite and not web.errori_console and not web.errori_mostrati()


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


def test_la_nota_che_spiega_lo_stato_si_legge_nella_riga_e_nella_scheda(web):
    """«In dubbio» da solo non dice perché: sotto c'è la nota delle probabili, nella riga della panchina e nella scheda."""
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    f = web.registrata("/api/formazione")
    panchina = [f["schede"][str(i)] for i in next(m for m in f["moduli"] if m["modulo"] == f["modulo"])["panchina"]]
    incerto = next((x for x in panchina if (x.get("etichetta") or {}).get("codice") == "in_dubbio" and x.get("nota")), None)
    assert incerto, "nello scenario registrato nessuna riserva è in dubbio con una nota: il test non proverebbe niente"
    riga = principale(web).get_by_role("listitem").filter(has_text=incerto["nome"]).first
    testo = " ".join(riga.inner_text().split())
    assert "In dubbio" in testo and incerto["nota"] in testo
    tocca(web, riga.get_by_role("button"))
    assert incerto["nota"] in " ".join(scheda(web).inner_text().split())


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
    # quanto vale la differenza si dice con il suo nome: «(−0,1 punti attesi)», non un numero da solo
    assert re.fullmatch(r"L'hai cambiata tu: 1 titolare diverso dalla consigliata \([+−]?\d+,\d punti attesi\)\. Torna alla consigliata", stato(web)), stato(web)
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
    casella.uncheck()                                                 # tolta: la scelta resta (si toglie solo con «Torna alla consigliata»)
    web.aspetta()
    assert salvata["scelta"] and len(salvata["scelta"]["titolari"]) == 11 and "messa" not in salvata["scelta"]
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
    assert righe[0].startswith(f"{esce['nome']} è in dubbio") and "+0,9 punti attesi." in righe[0] and righe[0].endswith("Sostituisci")
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
    assert principale(web).get_by_role("heading", level=1).inner_text().strip() == "Giornate"       # una pagina, non più un foglio (#617)
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


def test_fra_i_sostituti_chi_gioca_meno_dell_80_per_cento_lo_dice(web):
    """Il numero grande di un sostituto sono i punti attesi in più o in meno: se è basso perché gioca poco, la riga lo dice."""
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    f = web.registrata("/api/formazione")
    consigliato = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])
    fermi = ("infortunato", "squalificato", "fuori")
    riserve = [x for x in f["schede"].values() if x["id"] not in consigliato["titolari"] and (x.get("etichetta") or {}).get("codice") not in fermi]
    letto = lambda x: int(x["p_voto"] * 100 + 0.5)                             # noqa: E731 («gioca N%» come si legge)
    incerta, sicura = next((a, b) for a in riserve for b in riserve if a["ruolo"] == b["ruolo"] and letto(a) < 80 <= letto(b))
    titolare = next(f["schede"][str(i)] for i in consigliato["titolari"] if f["schede"][str(i)]["ruolo"] == incerta["ruolo"])
    tocca(web, campo(web).filter(has_text=titolare["nome"]).first)
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    riga = lambda x: " ".join(scheda(web).get_by_role("listitem").filter(has_text=x["nome"]).first.inner_text().split())   # noqa: E731
    assert f"gioca {letto(incerta)}%" in riga(incerta), riga(incerta)
    assert "gioca" not in riga(sicura), riga(sicura)


def test_sul_pc_cambiando_modulo_l_elenco_dei_sostituti_aperto_si_chiude(web):
    """Con il pannello a fianco la pagina resta attiva: i candidati aperti erano quelli della formazione di prima."""
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/", larghezza=PC)
    f = web.registrata("/api/formazione")
    tocca(web, campo(web).nth(3))
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    assert "Al posto di" in scheda(web).get_by_role("heading").first.inner_text()
    principale(web).get_by_label("Modulo").select_option(next(m["modulo"] for m in f["moduli"] if m["modulo"] != f["modulo"]))
    web.aspetta()
    assert scheda(web).count() == 0
    assert stato(web).startswith("L'hai cambiata tu")


# ---------------------------------------------------------------- quando il cambio non si può fare
def _con_due_fermi(web):
    """La consigliata con due giocatori di un anticipo già cominciato (campo `bloccati`): un titolare e una riserva. Torna il
    titolare fermo, la riserva ferma e un titolare libero dello stesso ruolo della riserva."""
    f = web.registrata("/api/formazione")
    consigliato = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])
    titolari = [f["schede"][str(i)] for i in consigliato["titolari"]]
    riserva = next(x for x in (f["schede"][str(i)] for i in consigliato["panchina"]) if x["ruolo"] != "P")
    libero = next(x for x in titolari if x["ruolo"] == riserva["ruolo"])
    titolare = next(x for x in titolari if x["id"] != libero["id"] and x["ruolo"] != "P")
    web.risposta("/api/formazione", {**f, "bloccati": [titolare["id"], riserva["id"]]})
    web.risposta("/api/scelta?giornata=9", None)
    return titolare, riserva, libero


def test_chi_gioca_una_partita_gia_cominciata_non_si_sostituisce_e_la_scheda_dice_perche(web):
    solo(web, "prima")
    titolare, riserva, libero = _con_due_fermi(web)
    web.apri("/")
    tocca(web, campo(web).filter(has_text=titolare["nome"]).first)
    assert titolare["nome"] in scheda(web).get_by_role("heading").first.inner_text()
    assert scheda(web).get_by_role("button", name="Sostituisci").count() == 0
    assert "non si può più spostare" in scheda(web).inner_text()
    web.pagina.keyboard.press("Escape")
    # un compagno libero si sostituisce, ma la riserva ferma non è fra chi può entrare
    tocca(web, campo(web).filter(has_text=libero["nome"]).first)
    assert "non si può più spostare" not in scheda(web).inner_text()
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    assert "Al posto di" in scheda(web).get_by_role("heading").first.inner_text()
    assert riserva["nome"] not in scheda(web).inner_text()


def test_se_il_server_rifiuta_il_ritorno_alla_consigliata_la_formazione_resta_e_un_avviso_lo_dice(web):
    solo(web, "prima")
    web.apri("/")                                                     # nello scenario registrato c'è una scelta fatta a mano
    prima, stato_prima = nomi_sul_campo(web), stato(web)
    web.risposta("/api/scelta?giornata=9", {"detail": "Esempio E. gioca in una partita già cominciata: non si può più spostare.",
                                            "codice": "giocatore_bloccato"}, stato=400)
    tocca(web, principale(web).get_by_role("button", name="Torna alla consigliata"))
    avviso = web.pagina.get_by_role("status").filter(has_text="non si può più spostare")
    assert avviso.count() == 1 and avviso.first.is_visible()
    assert nomi_sul_campo(web) == prima and stato(web) == stato_prima
    assert principale(web).get_by_role("button", name="Torna alla consigliata").is_visible()
    assert not web.errori_mostrati()


def test_se_la_scadenza_passa_con_la_pagina_aperta_il_cambio_non_si_fa_e_la_schermata_si_rilegge(web):
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    prima = nomi_sul_campo(web)
    web.risposta("/api/formazione/valuta", {"detail": "La giornata è già iniziata: la formazione non si può più cambiare.",
                                            "codice": "formazione_chiusa"}, stato=409)
    lette = web.richieste.count("/api/formazione")
    tocca(web, campo(web).nth(3))
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    tocca(web, scheda(web).get_by_role("listitem").first.get_by_role("button"))
    avviso = web.pagina.get_by_role("status").filter(has_text="non si può più cambiare")
    assert avviso.count() == 1 and avviso.first.is_visible()
    assert nomi_sul_campo(web) == prima and stato(web) == "È la consigliata."
    assert web.richieste.count("/api/formazione") == lette + 1, "dopo il rifiuto la formazione non è stata riletta dal server"


def test_a_giornata_finita_con_un_recupero_che_manca_lo_dice_e_si_sceglie_cosa_vale(web):
    solo(web, "finita")
    oggi = web.registrata("/api/oggi")
    giornata = oggi["riepilogo"]["giornata"]
    rinvio = {"giornata": giornata, "stagione": "2026-27", "modo": "aspetta", "modi": ["aspetta", "senza_voto", "voto_ufficio"],
              "voto_ufficio": 6, "predefinito": "aspetta", "eccezione": False}
    web.risposta("/api/oggi", {**oggi, "riepilogo": {**oggi["riepilogo"], "rinvio": rinvio,
                                                     "recuperi": [{"casa": "udinese", "trasferta": "milan", "data": None}]}})
    web.risposta("/api/regole/rinvio", {"ok": True})
    web.apri("/")
    assert "Manca il recupero di UDI vs MIL" in web.testo_principale()
    scritte = scritture(web)
    principale(web).get_by_label("Per questa giornata i loro giocatori").select_option("senza_voto")
    web.aspetta()
    assert scritte == [("PUT", "/api/regole/rinvio", {"giornata": giornata, "modo": "senza_voto", "stagione": "2026-27"})]
    assert not web.errori_mostrati() and not web.errori_console


# ---------------------------------------------------------------- accessibilità della scheda e dei sostituti
@pytest.mark.parametrize("tema", ["chiaro", "scuro"])
def test_la_scheda_e_l_elenco_dei_sostituti_non_hanno_violazioni_gravi(web, tema):
    solo(web, "prima")
    web.apri("/", tema=tema)
    tocca(web, campo(web).nth(3))
    gravi = web.violazioni_gravi()
    assert not gravi, f"scheda, {tema}: {[(v['id'], v['nodi'][:2]) for v in gravi]}"
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    gravi = web.violazioni_gravi()
    assert not gravi, f"sostituti, {tema}: {[(v['id'], v['nodi'][:2]) for v in gravi]}"
    assert not web.scorre_di_lato()


# ---------------------------------------------------------------- revisione della #637: ciò che si salva è ciò che si vede
# Il server finto non salva: dove serve, il test fa la parte del server e tiene lui la scelta della giornata.
RITARDA = """(() => { const vera = window.fetch;
  window.fetch = (u, o) => { let ms = 0;
    try { const p = new URL(u, location.href).pathname; ms = (JSON.parse(sessionStorage.getItem("ritardi") || "null") || {})[p] || 0; } catch (e) {}
    return ms ? new Promise(ok => setTimeout(ok, ms)).then(() => vera(u, o)) : vera(u, o); }; })()"""


def server_con_memoria(web, iniziale):
    """La scelta della giornata tenuta in memoria come farebbe il server: la spunta e `era_consigliata` restano finché gli 11 sono
    gli stessi. `mem["oggi"]`: un'altra risposta di /api/oggi; `mem["rifiuto"]`: (stato, corpo) con cui rifiutare un salvataggio."""
    mem = {"scelta": iniziale, "oggi": None, "rifiuto": None}
    js = "application/json"

    def scelta(route):
        if route.request.method == "DELETE":
            mem["scelta"] = None
            return route.fulfill(status=200, content_type=js, body='{"ok": true}')
        return route.fulfill(status=200, content_type=js, body=json.dumps(mem["scelta"]))

    def valuta(route):
        corpo = json.loads(route.request.post_data)
        if corpo.get("salva") and mem["rifiuto"]:
            return route.fulfill(status=mem["rifiuto"][0], content_type=js, body=json.dumps(mem["rifiuto"][1]))
        if corpo.get("salva"):
            prima = mem["scelta"] or {}
            stessi = sorted(prima.get("titolari") or []) == sorted(corpo["titolari"])
            nuova = {"titolari": corpo["titolari"], "modulo": "4-3-3", "salvata": "2026-10-27T15:10:00", "tipo": "manuale"}
            if stessi and prima.get("era_consigliata"):
                nuova["era_consigliata"] = True
            if corpo.get("messa") is True or (corpo.get("messa") is None and stessi and prima.get("messa")):
                nuova.update(messa=True, messa_il="2026-10-27T15:10:00")
            mem["scelta"] = nuova
        route.fulfill(status=200, content_type=js, body=json.dumps(web.registrata("/api/formazione/valuta")))

    web.pagina.route(lambda u: urlsplit(u).path == "/api/scelta", scelta)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/formazione/valuta", valuta)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/oggi",
                     lambda r: r.fulfill(status=200, content_type=js, body=json.dumps(mem["oggi"] or web.registrata("/api/oggi"))))
    return mem


def _ritardi(web, ritardi: dict) -> None:
    web.pagina.evaluate("(r) => sessionStorage.setItem('ritardi', JSON.stringify(r))", ritardi)


def _aspetta(locatore, **cosa):
    """Attese di Playwright su un elemento: `attivo=True`, `testo="…"`."""
    from playwright.sync_api import expect
    if "attivo" in cosa:
        (expect(locatore).to_be_enabled if cosa["attivo"] else expect(locatore).to_be_disabled)(timeout=10000)
    if "testo" in cosa:
        expect(locatore).to_contain_text(cosa["testo"], timeout=10000)


def _altro_modulo(web):
    f = web.registrata("/api/formazione")
    return next(m for m in f["moduli"] if m["modulo"] != f["modulo"])


def _ha_il_fuoco(locatore) -> bool:
    return locatore.evaluate("e => e === document.activeElement")


def test_la_copia_mostrata_subito_si_legge_ma_non_si_cambia_finche_non_arrivano_i_dati(web):
    """All'apertura compare subito la copia tenuta sul telefono. Un tocco lì salvava sul server, ma i dati nuovi in arrivo
    ridisegnavano la pagina senza il cambio: la copia è di sola lettura, con i comandi al loro posto ma spenti."""
    solo(web, "prima")
    web.pagina.add_init_script(RITARDA)
    mem = server_con_memoria(web, None)
    web.apri("/")
    assert stato(web) == "È la consigliata."
    mem["oggi"] = {**web.registrata("/api/oggi"), "ore_mancanti": web.registrata("/api/oggi")["ore_mancanti"] - 0.1}   # passano sei minuti
    _ritardi(web, {"/api/formazione": 1500})
    scritte = scritture(web)
    web.pagina.goto(web.server.indirizzo + "/", wait_until="commit")
    web.pagina.wait_for_selector("#campo-formazione")
    menu, casella = principale(web).get_by_label("Modulo"), principale(web).get_by_role("checkbox", name="L'ho messa")
    assert menu.is_visible() and casella.is_visible(), "i comandi restano al loro posto"
    assert menu.is_disabled() and casella.is_disabled(), "sulla copia i comandi che scrivono sono spenti"
    campo(web).nth(3).click()                                          # la scheda si apre, ma da lì non si sostituisce
    assert scheda(web).get_by_role("button", name="Sostituisci").is_disabled()
    web.pagina.keyboard.press("Escape")
    _aspetta(menu, attivo=True)                                        # arrivano i dati nuovi
    assert principale(web).get_by_role("checkbox", name="L'ho messa").is_enabled() and not scritte
    altro = _altro_modulo(web)
    _ritardi(web, {})
    principale(web).get_by_label("Modulo").select_option(altro["modulo"])
    web.aspetta()
    assert stato(web).startswith("L'hai cambiata tu") and sorted(mem["scelta"]["titolari"]) == sorted(altro["titolari"])


def _apri_sulla_copia_senza_rete(web) -> dict:
    """Riapre la pagina con la copia già sul telefono e /api/oggi che non arriva, come con la rete caduta. Restituisce
    l'interruttore: `caduta["si"] = False` e la rete è tornata."""
    web.apri("/")
    caduta = {"si": True}
    web.pagina.route(lambda u: urlsplit(u).path == "/api/oggi", lambda r: r.abort() if caduta["si"] else r.fallback())
    web.pagina.goto(web.server.indirizzo + "/", wait_until="commit")
    web.pagina.wait_for_selector("#campo-formazione")
    _aspetta(principale(web).get_by_text("Non riesco a collegarmi"), testo="questi sono gli ultimi dati salvati")
    return caduta


def _la_rete_torna(web) -> None:
    """Il browser segnala che la rete è tornata (evento `online` vero: la scheda va fuori linea e ci torna)."""
    web.pagina.context.set_offline(True)
    web.pagina.context.set_offline(False)


def test_se_i_dati_nuovi_non_arrivano_la_copia_dice_perche_non_si_cambia_e_ha_riprova(web):
    """Rete caduta all'apertura: resta la copia tenuta sul telefono con i comandi spenti. La nota diceva solo «questi sono gli
    ultimi dati salvati»: ora dice anche perché non si può cambiare niente, e c'è «Riprova»."""
    solo(web, "prima")
    mem = server_con_memoria(web, None)
    caduta = _apri_sulla_copia_senza_rete(web)
    menu, casella = principale(web).get_by_label("Modulo"), principale(web).get_by_role("checkbox", name="L'ho messa")
    assert campo(web).count() == 11 and menu.is_disabled() and casella.is_disabled()
    assert "la formazione non si può cambiare" in " ".join(web.testo_principale().split())
    riprova = principale(web).get_by_role("button", name="Riprova")
    assert riprova.count() == 1 and riprova.is_visible()
    assert not web.scorre_di_lato()
    caduta["si"] = False
    tocca(web, riprova)
    assert principale(web).get_by_label("Modulo").is_enabled() and principale(web).get_by_role("checkbox", name="L'ho messa").is_enabled()
    assert "Non riesco a collegarmi" not in web.testo_principale() and principale(web).get_by_role("button", name="Riprova").count() == 0
    assert not web.pagina.evaluate("() => !document.activeElement || document.activeElement === document.body"), "dopo «Riprova» il fuoco è nel vuoto"
    altro = _altro_modulo(web)
    principale(web).get_by_label("Modulo").select_option(altro["modulo"])
    web.aspetta()
    assert stato(web).startswith("L'hai cambiata tu") and sorted(mem["scelta"]["titolari"]) == sorted(altro["titolari"])


def test_quando_la_rete_torna_la_copia_si_aggiorna_da_sola_e_i_comandi_si_riaccendono(web):
    solo(web, "prima")
    server_con_memoria(web, None)
    caduta = _apri_sulla_copia_senza_rete(web)
    assert principale(web).get_by_label("Modulo").is_disabled()
    caduta["si"] = False
    _la_rete_torna(web)                                                # nessun tocco: la pagina riprova da sola
    _aspetta(principale(web).get_by_label("Modulo"), attivo=True)
    web.aspetta()
    assert principale(web).get_by_role("checkbox", name="L'ho messa").is_enabled()
    assert "Non riesco a collegarmi" not in web.testo_principale() and principale(web).get_by_role("button", name="Riprova").count() == 0
    assert stato(web) == "È la consigliata." and not web.errori_mostrati()


def test_al_ritorno_della_rete_la_copia_riprova_una_volta_sola(web):
    """Il browser dice che la rete è tornata ma il server ancora non si raggiunge: una riprova, non una serie. Resta «Riprova»."""
    solo(web, "prima")
    server_con_memoria(web, None)
    _apri_sulla_copia_senza_rete(web)
    chieste = web.richieste.count("/api/oggi")
    with web.pagina.expect_request(lambda r: urlsplit(r.url).path == "/api/oggi", timeout=10000):
        _la_rete_torna(web)
    web.aspetta()
    assert web.richieste.count("/api/oggi") == chieste + 1
    _la_rete_torna(web)
    web.aspetta()
    assert web.richieste.count("/api/oggi") == chieste + 1, "al secondo segnale la pagina ha riprovato ancora"
    assert principale(web).get_by_label("Modulo").is_disabled()
    assert principale(web).get_by_role("button", name="Riprova").is_visible() and "Non riesco a collegarmi" in web.testo_principale()


def test_un_salvataggio_che_torna_dopo_che_la_schermata_si_e_ridisegnata_si_rilegge(web):
    """Mai una scelta salvata che la pagina non mostra: se la risposta arriva quando la schermata è già stata ridisegnata (qui
    un tocco sulla scheda «Formazione» a salvataggio in volo), si rilegge dal server."""
    solo(web, "prima")
    web.pagina.add_init_script(RITARDA)
    mem = server_con_memoria(web, None)
    web.apri("/")
    altro = _altro_modulo(web)
    _ritardi(web, {"/api/formazione/valuta": 1500})
    lette = web.richieste.count("/api/formazione")
    principale(web).get_by_label("Modulo").select_option(altro["modulo"])
    web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Formazione").click()
    _aspetta(principale(web).locator("#stato-scelta"), testo="L'hai cambiata tu")
    web.aspetta()
    assert sorted(mem["scelta"]["titolari"]) == sorted(altro["titolari"])
    assert principale(web).get_by_label("Modulo").input_value() == altro["modulo"]
    assert web.richieste.count("/api/formazione") >= lette + 2, "la schermata non è stata riletta dopo il salvataggio"
    assert not web.errori_mostrati() and not web.errori_console


def _trattieni_i_salvataggi(web) -> list:
    """Da qui i salvataggi restano in volo finché il test non li lascia andare (`.fallback()`: risponde il server del test) o
    non li fa fallire (`.abort()`). Restituisce l'elenco di quelli fermi."""
    fermi = []

    def ferma(route):
        if json.loads(route.request.post_data).get("salva"):
            fermi.append(route)
        else:
            route.fallback()

    web.pagina.route(lambda u: urlsplit(u).path == "/api/formazione/valuta", ferma)
    return fermi


def _rileggi_a_salvataggio_in_volo(web, mem=None):
    """Un altro modulo (il salvataggio resta in volo), poi un tocco sulla scheda «Formazione»: la pagina si rilegge dal server,
    che del cambio non sa ancora niente. Con `mem` i dati riletti sono diversi dalla copia sul telefono (passano sei minuti): la
    pagina si ridisegna da capo. Restituisce i salvataggi fermi e il modulo scelto."""
    altro = _altro_modulo(web)
    fermi = _trattieni_i_salvataggi(web)
    principale(web).get_by_label("Modulo").select_option(altro["modulo"])
    if mem:
        mem["oggi"] = {**web.registrata("/api/oggi"), "ore_mancanti": web.registrata("/api/oggi")["ore_mancanti"] - 0.1}
    with web.pagina.expect_response(lambda r: urlsplit(r.url).path == "/api/scelta"):
        web.pagina.get_by_role("navigation", name="Sezioni").get_by_role("link", name="Formazione").click()
    from playwright.sync_api import expect
    expect(principale(web).get_by_text("aggiorno…")).to_have_count(0, timeout=10000)     # i dati riletti sono in pagina
    assert stato(web) == "È la consigliata." and len(fermi) == 1
    return fermi, altro


@pytest.mark.parametrize("dati_riletti", ["uguali alla copia", "diversi dalla copia"])
def test_a_salvataggio_in_volo_la_pagina_riletta_resta_spenta_e_il_cambio_non_si_perde(web, dati_riletti):
    """Difetto visto in revisione: la pagina riletta a salvataggio in volo mostrava ancora «È la consigliata.» con i comandi
    accesi; la spunta messa lì partiva dopo il primo salvataggio con gli 11 di prima, e il cambio di modulo era perso. Finché
    una scrittura sulla scelta è in corso i comandi restano spenti, anche dopo una rilettura."""
    solo(web, "prima")
    mem = server_con_memoria(web, None)
    web.apri("/")
    scritte = scritture(web)
    fermi, altro = _rileggi_a_salvataggio_in_volo(web, mem if dati_riletti == "diversi dalla copia" else None)
    menu, casella = principale(web).get_by_label("Modulo"), principale(web).get_by_role("checkbox", name="L'ho messa")
    spenti = menu.is_disabled() and casella.is_disabled()
    if casella.is_enabled():
        casella.check()                                                # il secondo salvataggio, che scriveva sopra il primo
    while fermi:
        fermi.pop(0).fallback()                                        # il salvataggio arriva al server
        web.aspetta()
    assert sorted(mem["scelta"]["titolari"]) == sorted(altro["titolari"]), "il cambio di modulo è andato perso"
    assert spenti, "a salvataggio in volo la pagina riletta aveva i comandi accesi"
    assert len(scritte) == 1, scritte
    assert principale(web).get_by_label("Modulo").input_value() == altro["modulo"] and stato(web).startswith("L'hai cambiata tu")
    assert principale(web).get_by_label("Modulo").is_enabled() and principale(web).get_by_role("checkbox", name="L'ho messa").is_enabled()
    assert not web.errori_mostrati() and not web.errori_console


def test_se_il_salvataggio_in_volo_non_riesce_la_pagina_riletta_lo_dice_e_si_riaccende(web):
    """Il salvataggio partito dalla schermata di prima fallisce (rete caduta) quando la pagina è già stata riletta: un avviso lo
    dice, in pagina resta ciò che è salvato e i comandi tornano accesi."""
    solo(web, "prima")
    mem = server_con_memoria(web, None)
    web.apri("/")
    fermi, _ = _rileggi_a_salvataggio_in_volo(web)
    assert principale(web).get_by_label("Modulo").is_disabled()
    fermi.pop(0).abort()
    avviso = web.pagina.get_by_role("status").filter(has_text="Non riesco a collegarmi")
    _aspetta(avviso.first, testo="Non riesco a collegarmi")
    _aspetta(principale(web).get_by_label("Modulo"), attivo=True)
    web.aspetta()
    assert principale(web).get_by_role("checkbox", name="L'ho messa").is_enabled()
    assert stato(web) == "È la consigliata." and mem["scelta"] is None
    assert principale(web).get_by_label("Modulo").input_value() == web.registrata("/api/formazione")["modulo"]
    assert not web.errori_mostrati()


def test_togliere_la_spunta_non_cancella_una_scelta_salvata_altrove(web):
    """Gli 11 salvati (per esempio dall'iPhone) sono quelli della consigliata: mettere e togliere la spunta non cancella la
    scelta. Una scelta salvata non cambia mai da sola: si toglie solo con «Torna alla consigliata»."""
    solo(web, "prima")
    f = web.registrata("/api/formazione")
    c = next(m for m in f["moduli"] if m["modulo"] == f["modulo"])
    mem = server_con_memoria(web, {"titolari": c["titolari"], "modulo": c["modulo"], "salvata": "2026-10-27T09:00:00", "tipo": "manuale",
                                   "era_consigliata": True})
    web.apri("/")
    assert stato(web) == "È la consigliata."
    scritte = scritture(web)
    casella = principale(web).get_by_role("checkbox", name="L'ho messa")
    casella.check()
    web.aspetta()
    assert mem["scelta"]["messa"] is True
    principale(web).get_by_role("checkbox", name="L'ho messa").uncheck()
    web.aspetta()
    assert mem["scelta"] and sorted(mem["scelta"]["titolari"]) == sorted(c["titolari"]) and "messa" not in mem["scelta"]
    assert mem["scelta"].get("era_consigliata") is True
    assert [(m, p, corpo["messa"]) for m, p, corpo in scritte] == [("POST", "/api/formazione/valuta", True), ("POST", "/api/formazione/valuta", False)]
    assert not principale(web).get_by_role("checkbox", name="L'ho messa").is_checked() and stato(web) == "È la consigliata."


@pytest.mark.parametrize("rotta", ["/api/scelta", "/api/formazione/valuta"])
def test_se_la_scelta_salvata_non_si_legge_la_pagina_lo_dice_e_non_fa_cambiare_niente(web, rotta):
    """La scelta (o i suoi punti) non arriva: prima la pagina mostrava la consigliata con i comandi attivi, e un cambio di modulo
    sovrascriveva la scelta non letta. Ora c'è un errore con «Riprova» e i comandi che scrivono sono spenti."""
    solo(web, "prima")
    guasto = {"acceso": True}

    def rompi(route):
        if guasto["acceso"]:
            return route.fulfill(status=500, content_type="application/json", body='{"detail": "Errore interno"}')
        route.fallback()

    web.pagina.route(lambda u: urlsplit(u).path == rotta, rompi)
    web.apri("/")                                                     # nello scenario registrato c'è una scelta fatta a mano
    assert campo(web).count() == 11 and web.errori_mostrati(), "manca l'errore che dice che la scelta non è stata letta"
    assert principale(web).locator("#stato-scelta").count() == 0       # niente «È la consigliata.»: non si sa
    assert principale(web).get_by_label("Modulo").is_disabled()
    assert principale(web).get_by_role("checkbox", name="L'ho messa").is_disabled()
    assert principale(web).get_by_role("button", name="Copia per l'app della lega").is_disabled()   # non si copia una formazione che forse non è la tua
    scritte = scritture(web)
    campo(web).nth(3).click()
    assert scheda(web).get_by_role("button", name="Sostituisci").is_disabled()
    web.pagina.keyboard.press("Escape")
    assert not scritte
    guasto["acceso"] = False
    tocca(web, principale(web).get_by_role("button", name="Riprova"))
    assert stato(web).startswith("L'hai cambiata tu") and not web.errori_mostrati()
    assert principale(web).get_by_label("Modulo").is_enabled()


@pytest.mark.parametrize("rifiuto, frase", [
    (None, "Non riesco a collegarmi"),
    ((400, {"detail": "La formazione non è valida: controlla i titolari.", "codice": "formazione_non_valida"}), "La formazione non è valida"),
])
def test_un_salvataggio_non_riuscito_lascia_la_formazione_com_era_e_lo_dice(web, rifiuto, frase):
    """Rete caduta o rifiuto del server su una sostituzione: un avviso dice cosa è successo e in pagina resta ciò che è salvato."""
    solo(web, "prima")
    mem = server_con_memoria(web, None)
    web.apri("/")
    prima = nomi_sul_campo(web)
    if rifiuto:
        mem["rifiuto"] = rifiuto
    else:
        web.pagina.route(lambda u: urlsplit(u).path == "/api/formazione/valuta", lambda r: r.abort())
    tocca(web, campo(web).nth(3))
    tocca(web, scheda(web).get_by_role("button", name="Sostituisci"))
    tocca(web, scheda(web).get_by_role("listitem").first.get_by_role("button"))
    avviso = web.pagina.get_by_role("status").filter(has_text=frase)
    assert avviso.count() == 1 and avviso.first.is_visible()
    assert nomi_sul_campo(web) == prima and stato(web) == "È la consigliata." and mem["scelta"] is None
    assert principale(web).get_by_label("Modulo").input_value() == web.registrata("/api/formazione")["modulo"]
    assert not web.errori_mostrati()


CONFLITTO = {"detail": "Questi dati sono stati cambiati da un altro dispositivo. Ho ricaricato la versione nuova: controlla e rifai la modifica."}


def server_con_etag(web, iniziale):
    """Fa la parte del server vero sulla scelta della giornata, ETag compreso: ogni lettura dà l'ETag di adesso; una scrittura
    con un If-Match vecchio è rifiutata (412), una senza If-Match è accettata, anche sopra ciò che ha salvato un altro
    dispositivo. `srv["cambia"](scelta)`: un altro dispositivo salva; `srv["if_match"]`: l'If-Match di ogni scrittura arrivata;
    con `srv["trattieni"]` le letture restano in volo in `srv["ferme"]` finché il test non risponde con `srv["leggi"](route)`."""
    srv = {"scelta": iniziale, "versione": 0, "if_match": [], "trattieni": False, "ferme": []}
    js = "application/json"

    def etag() -> str:
        return f'"v{srv["versione"]}"'

    def cambia(nuova) -> None:
        srv["scelta"], srv["versione"] = nuova, srv["versione"] + 1

    def rifiutata(route) -> bool:
        voluto = route.request.headers.get("if-match")
        srv["if_match"].append(voluto)
        if voluto is None or voluto == etag():
            return False
        route.fulfill(status=412, content_type=js, headers={"ETag": etag()}, body=json.dumps(CONFLITTO))
        return True

    def leggi(route) -> None:
        route.fulfill(status=200, content_type=js, headers={"ETag": etag()}, body=json.dumps(srv["scelta"]))

    def scelta(route):
        if route.request.method == "DELETE":
            if not rifiutata(route):
                cambia(None)
                route.fulfill(status=200, content_type=js, headers={"ETag": etag()}, body='{"ok": true}')
        elif srv["trattieni"]:
            srv["ferme"].append(route)
        else:
            leggi(route)

    def valuta(route):
        corpo = json.loads(route.request.post_data)
        if not corpo.get("salva"):
            return route.fallback()
        if not rifiutata(route):
            cambia({"titolari": corpo["titolari"], "modulo": "4-3-3", "salvata": "2026-10-27T15:10:00", "tipo": "manuale",
                    **({"messa": True, "messa_il": "2026-10-27T15:10:00"} if corpo.get("messa") else {})})
            route.fulfill(status=200, content_type=js, headers={"ETag": etag()}, body=json.dumps(web.registrata("/api/formazione/valuta")))

    srv["cambia"], srv["leggi"] = cambia, leggi
    web.pagina.route(lambda u: urlsplit(u).path == "/api/scelta", scelta)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/formazione/valuta", valuta)
    return srv


def _comandi_accesi(web) -> list[str]:
    """I comandi che scrivono sulla scelta e che in questo momento si possono usare."""
    comandi = {"menu del modulo": principale(web).get_by_label("Modulo"), "spunta": principale(web).get_by_role("checkbox", name="L'ho messa"),
               "torna alla consigliata": principale(web).get_by_role("button", name="Torna alla consigliata")}
    return [nome for nome, c in comandi.items() if c.count() and c.is_enabled()]


@pytest.mark.parametrize("comando", ["la spunta", "torna alla consigliata"])
def test_dopo_un_412_i_comandi_restano_spenti_finche_la_pagina_non_ha_riletto_e_la_modifica_rifatta_ha_if_match(web, comando):
    """412: nel frattempo un altro dispositivo ha salvato una formazione diversa. Difetto visto in revisione: l'avviso diceva
    «ho ricaricato» ma la ricarica arrivava 2,5 secondi dopo; intanto i comandi erano accesi, la spunta restava segnata, e una
    modifica rifatta subito partiva senza If-Match e scriveva sopra la formazione dell'altro dispositivo. Ora i comandi si
    spengono subito, la pagina rilegge, e solo allora l'avviso dice di rifare la modifica."""
    solo(web, "prima")
    f = web.registrata("/api/formazione")
    altro = _altro_modulo(web)
    terzo = next(m for m in f["moduli"] if m["modulo"] not in (f["modulo"], altro["modulo"]))
    mia = {"titolari": altro["titolari"], "modulo": altro["modulo"], "salvata": "2026-10-27T09:00:00", "tipo": "manuale"}
    srv = server_con_etag(web, mia if comando == "torna alla consigliata" else None)
    web.apri("/")
    srv["cambia"]({"titolari": terzo["titolari"], "modulo": terzo["modulo"], "salvata": "2026-10-27T15:09:00", "tipo": "manuale"})   # dall'altro dispositivo
    srv["trattieni"] = True                                            # la rilettura resta in volo: si guarda la pagina nel frattempo
    tocco = (principale(web).get_by_role("checkbox", name="L'ho messa") if comando == "la spunta"
             else principale(web).get_by_role("button", name="Torna alla consigliata"))
    with web.pagina.expect_request(lambda r: r.method == "GET" and urlsplit(r.url).path == "/api/scelta", timeout=10000):
        tocco.click()
    avviso = web.pagina.get_by_role("status").filter(has_text="cambiati da un altro dispositivo")
    _aspetta(avviso.first, testo="Sto ricaricando")
    assert "rifai la modifica" not in avviso.first.inner_text(), "l'avviso dice di rifare la modifica prima che la pagina abbia riletto"
    assert not _comandi_accesi(web), "dopo il 412 ci sono comandi accesi prima della rilettura"
    srv["trattieni"] = False
    for lettura in srv["ferme"]:
        srv["leggi"](lettura)
    _aspetta(avviso.first, testo="controlla e rifai la modifica")
    web.aspetta()
    assert stato(web).startswith("L'hai cambiata tu") and principale(web).get_by_label("Modulo").input_value() == terzo["modulo"]
    casella = principale(web).get_by_role("checkbox", name="L'ho messa")
    assert not casella.is_checked() and casella.is_enabled()           # in pagina c'è ciò che è salvato, non il tocco non riuscito
    assert _ha_il_fuoco(casella if comando == "la spunta" else principale(web).get_by_role("button", name="Torna alla consigliata")), "il fuoco non è tornato sul comando"
    if comando == "la spunta":                                         # la modifica rifatta: parte con l'ETag appena riletto
        casella.check()
        web.aspetta()
        assert sorted(srv["scelta"]["titolari"]) == sorted(terzo["titolari"]) and srv["scelta"]["messa"] is True
    else:
        tocca(web, principale(web).get_by_role("button", name="Torna alla consigliata"))
        assert srv["scelta"] is None and stato(web) == "È la consigliata."
    assert srv["if_match"] == ['"v0"', '"v1"'], srv["if_match"]        # la prima rifiutata, la seconda con l'ETag riletto
    assert not web.errori_mostrati()


def test_un_412_su_altri_dati_non_toglie_l_if_match_alle_scritture_sulla_scelta(web):
    """Nessuna scrittura sulla scelta parte senza If-Match. Un 412 su un'altra cosa (qui la regola sul rinvio, cambiata da un
    altro dispositivo) faceva dimenticare tutti gli ETag: fino alla ricarica, 2,5 secondi dopo, un tocco sulla spunta partiva
    senza If-Match e avrebbe scritto sopra una formazione salvata altrove."""
    solo(web, "prima")
    srv = server_con_etag(web, None)
    oggi = web.registrata("/api/oggi")
    web.risposta("/api/oggi", {**oggi, "rinvio": {"giornata": oggi["giornata"], "stagione": "2026-27", "modo": "aspetta",
                                                  "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6, "predefinito": "aspetta",
                                                  "eccezione": False, "partite": [{"casa": "udinese", "trasferta": "milan", "data": None}]}})
    web.risposta("/api/regole/rinvio", CONFLITTO, stato=412)
    web.apri("/")
    principale(web).get_by_label("Per questa giornata i loro giocatori").select_option("senza_voto")
    _aspetta(web.pagina.get_by_role("status").filter(has_text="cambiati da un altro dispositivo").first, testo="cambiati da un altro dispositivo")
    with web.pagina.expect_request(lambda r: r.method == "POST" and urlsplit(r.url).path == "/api/formazione/valuta", timeout=10000):
        principale(web).get_by_role("checkbox", name="L'ho messa").click()
    web.aspetta()
    assert srv["if_match"] == ['"v0"'], srv["if_match"]


# ---------------------------------------------------------------- tastiera: dopo un comando il fuoco non si perde
def test_da_tastiera_il_menu_del_modulo_tiene_il_fuoco_dopo_ogni_scelta(web):
    solo(web, "prima")
    server_con_memoria(web, None)
    web.apri("/", larghezza=PC)
    scritte = scritture(web)
    principale(web).get_by_label("Modulo").focus()
    web.pagina.keyboard.press("ArrowDown")
    web.aspetta()
    assert len(scritte) == 1 and _ha_il_fuoco(principale(web).get_by_label("Modulo")), "dopo la prima freccia il fuoco non è sul menu"
    primo = principale(web).get_by_label("Modulo").input_value()
    web.pagina.keyboard.press("ArrowDown")
    web.aspetta()
    assert len(scritte) == 2 and principale(web).get_by_label("Modulo").input_value() != primo
    assert _ha_il_fuoco(principale(web).get_by_label("Modulo"))


def test_da_tastiera_spunta_torna_alla_consigliata_e_sostituisci_non_lasciano_il_fuoco_nel_vuoto(web):
    solo(web, "prima")
    server_con_memoria(web, None)
    web.apri("/")
    nel_vuoto = "() => !document.activeElement || document.activeElement === document.body"
    casella = principale(web).get_by_role("checkbox", name="L'ho messa")
    casella.focus()
    web.pagina.keyboard.press("Space")
    web.aspetta()
    assert _ha_il_fuoco(principale(web).get_by_role("checkbox", name="L'ho messa")) and principale(web).get_by_role("checkbox", name="L'ho messa").is_checked()
    # una sostituzione, tutta da tastiera: dopo, il fuoco è sul campo, su chi è entrato
    prima = nomi_sul_campo(web)
    campo(web).nth(3).focus()
    web.pagina.keyboard.press("Enter")
    web.aspetta()
    scheda(web).get_by_role("button", name="Sostituisci").focus()
    web.pagina.keyboard.press("Enter")
    web.aspetta()
    scheda(web).get_by_role("listitem").first.get_by_role("button").focus()
    web.pagina.keyboard.press("Enter")
    web.aspetta()
    entrato = (set(nomi_sul_campo(web)) - set(prima)).pop()
    assert not web.pagina.evaluate(nel_vuoto)
    assert entrato in web.pagina.evaluate("() => document.activeElement.innerText") and web.pagina.evaluate("() => !!document.activeElement.closest('#campo-formazione')")
    # «Torna alla consigliata» sparisce dopo l'uso: il fuoco passa al comando accanto, non al vuoto
    torna = principale(web).get_by_role("button", name="Torna alla consigliata")
    torna.focus()
    web.pagina.keyboard.press("Enter")
    web.aspetta()
    assert stato(web) == "È la consigliata." and not web.pagina.evaluate(nel_vuoto)
    assert web.pagina.evaluate("() => !!document.activeElement.closest('main') && ['BUTTON', 'SELECT', 'INPUT'].includes(document.activeElement.tagName)")


# ---------------------------------------------------------------- le decisioni: prima le urgenti, poi quelle con un'azione
def _scoperto(ruolo: str, testo: str, priorita: int = 1) -> dict:
    return {"id": f"copertura:{ruolo}", "tipo": "copertura", "priorita": priorita, "testo": testo,
            "azione": "Cerca un rimpiazzo", "destinazione": {"scheda": "mercato", "sezione": None}}


def _rose_da_aggiornare(priorita: int = 2) -> dict:
    return {"id": "rose-vecchie", "tipo": "rose", "testo": "È il momento di aste e scambi nella lega: se le rose sono cambiate, aggiornale.",
            "priorita": priorita, "azione": "Aggiorna le rose", "destinazione": {"scheda": "lega", "sezione": "rose"}}


def _dati_fermi() -> dict:
    return {"id": "dati-vecchi", "tipo": "server", "testo": "I dati non si aggiornano da 3 giorni.", "priorita": 2,
            "azione": "Controlla", "destinazione": {"scheda": "impostazioni", "sezione": "avanzate"}}


def _cambio_da_fare(web, priorita: int = 2) -> dict:
    """Un titolare in dubbio con un compagno di ruolo da mettere al suo posto: la decisione con «Sostituisci»."""
    f = web.registrata("/api/formazione")
    titolari = web.registrata("/api/scelta?giornata=9")["titolari"]
    esce = next(f["schede"][str(i)] for i in titolari if f["schede"][str(i)]["ruolo"] == "C")
    entra = next(x for x in f["schede"].values() if x["ruolo"] == "C" and x["id"] not in titolari)
    return {"id": f"dubbio:{esce['id']}", "tipo": "dubbio", "testo": f"{esce['nome']} è in dubbio (45% di giocare). Meglio {entra['nome']}.",
            "priorita": priorita, "azione": "Sostituisci", "destinazione": {"scheda": "formazione", "sezione": None, "giocatore": esce["id"]},
            "giocatore": {"id": esce["id"], "nome": esce["nome"]},
            "alternativa": {"id": entra["id"], "nome": entra["nome"], "ruolo": "C", "punti_attesi": esce["punti_attesi"] + 0.9}}


NESSUN_PORTIERE = "Non hai nessun portiere disponibile per questa giornata."
# Per ogni caso: le righe del server, e per le due decisioni attese un pezzo del testo e il pulsante con cui la riga finisce.
CASI_DECISIONI = {
    # due reparti scoperti e le rose: il reparto scoperto prende un posto solo, e quello urgente sta in cima
    "due reparti scoperti urgenti e le rose": (
        lambda web: [_scoperto("P", NESSUN_PORTIERE), _scoperto("D", "In difesa hai solo 2 giocatori disponibili."), _rose_da_aggiornare()],
        [("nessun portiere", "Vedi la rosa"), ("aste e scambi", "Aggiorna le rose")]),
    # «nessun portiere» è urgente, il cambio e le rose no: restava nascosto dietro a tutti e due
    "nessun portiere urgente, un cambio e le rose non urgenti": (
        lambda web: [_scoperto("P", NESSUN_PORTIERE), _cambio_da_fare(web), _rose_da_aggiornare()],
        [("nessun portiere", "Vedi la rosa"), ("è in dubbio", "Sostituisci")]),
    # conta l'urgenza, non il posto nella lista del server
    "due righe non urgenti e, in fondo, nessun portiere urgente": (
        lambda web: [_rose_da_aggiornare(), _dati_fermi(), _scoperto("P", NESSUN_PORTIERE)],
        [("nessun portiere", "Vedi la rosa"), ("aste e scambi", "Aggiorna le rose")]),
    # fra le urgenti prima quelle con un'azione: con due di loro il reparto scoperto non si vede
    "due righe urgenti con un'azione e nessun portiere urgente": (
        lambda web: [_scoperto("P", NESSUN_PORTIERE), _cambio_da_fare(web, priorita=1), _rose_da_aggiornare(priorita=1)],
        [("è in dubbio", "Sostituisci"), ("aste e scambi", "Aggiorna le rose")]),
    # niente di urgente: prima le righe con un'azione, il reparto senza ricambi solo se avanza un posto
    "niente di urgente": (
        lambda web: [_scoperto("D", "In difesa hai solo 3 giocatori disponibili.", priorita=2), _cambio_da_fare(web), _rose_da_aggiornare()],
        [("è in dubbio", "Sostituisci"), ("aste e scambi", "Aggiorna le rose")]),
}


@pytest.mark.parametrize("caso", list(CASI_DECISIONI))
def test_le_decisioni_urgenti_stanno_in_cima_e_il_reparto_scoperto_prende_un_posto_solo(web, caso):
    """Prima le righe urgenti (fra loro prima quelle con un'azione), poi le non urgenti con un'azione, poi il resto: al massimo due,
    e al massimo una sul reparto scoperto. Un «nessun portiere» urgente restava nascosto da due righe meno importanti."""
    solo(web, "prima")
    voci, attese = CASI_DECISIONI[caso]
    _con_da_fare(web, voci(web))
    righe = [" ".join(r.split()) for r in _decisioni(web).all_inner_texts()]
    assert len(righe) == len(attese), righe
    for riga, (pezzo, pulsante) in zip(righe, attese):
        assert pezzo in riga and riga.endswith(pulsante), righe
    assert sum("Vedi la rosa" in r for r in righe) <= 1 and "In difesa" not in web.testo_principale()
