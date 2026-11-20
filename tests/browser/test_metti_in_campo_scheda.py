"""«Metti in campo» dalla scheda di un giocatore in panchina o non schierato (#643).

Il contrario di «Sostituisci»: dalla scheda di chi non è fra gli 11, «Metti in campo» chiede al server chi può lasciargli il
posto (`POST /api/formazione/metti-in-campo`: stesso ruolo o un altro modulo ammesso dalla lega, con la differenza dei punti
attesi della formazione) e un tocco fa il cambio, che si salva come «Sostituisci». Gli scenari registrati non hanno ancora la
rotta nuova: la sua risposta la dà il test (`web.risposta`), costruita sulla formazione registrata. Il pulsante c'è esattamente
quando «Sostituisci» si può usare per quella formazione (anche per la prossima giornata, a giornata finita o per chi entra a
giornata iniziata), e per gli stessi giocatori che «Sostituisci» propone: non per chi gioca un anticipo già cominciato;
infortunati e squalificati sì, con il loro stato scritto (decisioni del coordinatore sulla #783).
"""
import json
import re
from urllib.parse import urlsplit

import pytest

from test_formazione_unica import (_aspetta, campo, nomi_sul_campo, principale, scheda, scritture, server_con_etag, solo, stato,
                                   tocca)

ROTTA = "/api/formazione/metti-in-campo"
NON_GIOCANO = ("infortunato", "squalificato")


def cognome(nome: str) -> str:
    """Il nome come sta sul campo: senza l'iniziale («Rossi L.» → «Rossi»), come `cognome` di app.js."""
    return re.sub(r"\s+\S{1,3}\.$", "", nome)


def _codice(x) -> str | None:
    return (x.get("etichetta") or {}).get("codice")


def _consigliato(f) -> dict:
    return next(m for m in f["moduli"] if m["modulo"] == f["modulo"])


def _panchinaro(f, ruolo="D") -> dict:
    """Una riserva di movimento della consigliata registrata che gioca (non infortunata né squalificata)."""
    return next(f["schede"][str(i)] for i in _consigliato(f)["panchina"]
                if f["schede"][str(i)]["ruolo"] == ruolo and _codice(f["schede"][str(i)]) not in NON_GIOCANO)


def _titolare(f, ruolo) -> dict:
    return next(f["schede"][str(i)] for i in _consigliato(f)["titolari"] if f["schede"][str(i)]["ruolo"] == ruolo)


def _riga_panchina(web, nome):
    return principale(web).locator("#panchina").get_by_role("listitem").filter(has_text=nome).first.get_by_role("button")


def _risposta(f, entra, uscite) -> dict:
    """La risposta della rotta come la dà il server: `uscite` = [(chi esce, modulo dopo, differenza della formazione)]."""
    adesso = _consigliato(f)["punteggio_atteso"]
    return {"giornata": f["giornata"], "entra": entra["id"], "punteggio_atteso": adesso,
            "uscite": [{"esce": x["id"], "modulo": modulo, "cambia_modulo": modulo != f["modulo"],
                        "punteggio_atteso": round(adesso + d, 1), "differenza": d} for x, modulo, d in uscite]}


def _prepara(web, scelta_vuota=True):
    """Si parte dalla consigliata registrata (4-3-3): entra una riserva difensore; può uscire un difensore (stesso modulo) o un
    attaccante (5-3-2). Torna (formazione, chi entra, il difensore, l'attaccante)."""
    if scelta_vuota:
        web.risposta("/api/scelta?giornata=9", None)
    f = web.registrata("/api/formazione")
    assert f["modulo"] == "4-3-3", "lo scenario registrato è cambiato: rivedi il test"
    entra, difensore, attaccante = _panchinaro(f), _titolare(f, "D"), _titolare(f, "A")
    web.risposta(ROTTA, _risposta(f, entra, [(difensore, "4-3-3", 0.4), (attaccante, "5-3-2", -1.2)]))
    return f, entra, difensore, attaccante


def _scelte(web):
    return scheda(web).get_by_role("listitem")


def test_dalla_scheda_di_un_panchinaro_metti_in_campo_fa_il_cambio_e_lo_salva(web):
    solo(web, "prima")
    f, entra, difensore, attaccante = _prepara(web)
    web.apri("/")
    assert stato(web) == "È la consigliata."
    prima = nomi_sul_campo(web)
    scritte = scritture(web)
    tocca(web, _riga_panchina(web, entra["nome"]))
    assert entra["nome"] in scheda(web).get_by_role("heading").first.inner_text()
    assert scheda(web).get_by_role("button", name="Sostituisci").count() == 0
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    # chi può lasciargli il posto, con la differenza dei punti attesi della formazione; il cambio di modulo si legge nella riga
    assert entra["nome"] in scheda(web).get_by_role("heading").first.inner_text()
    righe = [" ".join(t.split()) for t in _scelte(web).all_inner_texts()]
    assert len(righe) == 2 and difensore["nome"] in righe[0] and attaccante["nome"] in righe[1], righe
    assert "+0,4" in righe[0] and "5-3-2" not in righe[0]
    assert "−1,2" in righe[1] and "5-3-2" in righe[1]
    chiesta = [c for m, p, c in scritte if p == ROTTA]
    assert len(chiesta) == 1 and chiesta[0]["entra"] == entra["id"] and chiesta[0]["giornata"] == 9
    assert sorted(chiesta[0]["titolari"]) == sorted(_consigliato(f)["titolari"])
    tocca(web, _scelte(web).first.get_by_role("button"))
    dopo = nomi_sul_campo(web)
    assert set(prima) - set(dopo) == {difensore["nome"]} and set(dopo) - set(prima) == {entra["nome"]}, (prima, dopo)
    assert stato(web).startswith("L'hai cambiata tu: 1 titolare diverso dalla consigliata")
    # come dopo «Sostituisci», il fuoco è sul campo, su chi è entrato (mai nel vuoto)
    assert web.pagina.evaluate("() => !!document.activeElement.closest('#campo-formazione')")
    assert cognome(entra["nome"]) in web.pagina.evaluate("() => document.activeElement.innerText")
    salvate = [c for m, p, c in scritte if p == "/api/formazione/valuta"]
    assert len(salvate) == 1 and salvate[0]["salva"] is True
    assert entra["id"] in salvate[0]["titolari"] and difensore["id"] not in salvate[0]["titolari"]
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


def test_con_un_cambio_di_modulo_il_campo_e_il_menu_passano_al_modulo_nuovo(web):
    solo(web, "prima")
    f, entra, difensore, attaccante = _prepara(web)
    valutata = web.registrata("/api/formazione/valuta")
    web.risposta("/api/formazione/valuta", {**valutata, "modulo": "5-3-2"})
    web.apri("/")
    scritte = scritture(web)
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    tocca(web, _scelte(web).filter(has_text=attaccante["nome"]).first.get_by_role("button"))
    linee = principale(web).locator("#campo-formazione .linea")
    assert [linee.nth(k).get_by_role("button").count() for k in range(4)] == [1, 5, 3, 2]
    assert principale(web).get_by_label("Modulo").input_value() == "5-3-2"
    assert stato(web).startswith("L'hai cambiata tu")
    salvate = [c for m, p, c in scritte if p == "/api/formazione/valuta"]
    assert len(salvate) == 1 and entra["id"] in salvate[0]["titolari"] and attaccante["id"] not in salvate[0]["titolari"]


def test_fra_chi_esce_chi_gioca_meno_dell_80_per_cento_lo_dice(web):
    """Come fra i sostituti: sotto il nome «gioca N%» per chi gioca meno dell'80%."""
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    f = web.registrata("/api/formazione")
    letto = lambda x: int(x["p_voto"] * 100 + 0.5)                             # noqa: E731 («gioca N%» come si legge)
    titolari = [f["schede"][str(i)] for i in _consigliato(f)["titolari"] if f["schede"][str(i)]["ruolo"] != "P"]
    incerto = next(x for x in titolari if letto(x) < 80)
    sicuro = next(x for x in titolari if letto(x) >= 80)
    entra = _panchinaro(f, incerto["ruolo"])
    web.risposta(ROTTA, _risposta(f, entra, [(incerto, f["modulo"], 0.8), (sicuro, "4-4-2", -0.3)]))
    web.apri("/")
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    riga = lambda x: " ".join(_scelte(web).filter(has_text=x["nome"]).first.inner_text().split())   # noqa: E731
    assert f"gioca {letto(incerto)}%" in riga(incerto), riga(incerto)
    assert not re.search(r"gioca \d+%", riga(sicuro)), riga(sicuro)


def test_se_il_server_non_risponde_la_scheda_lo_dice_e_non_cambia_niente(web):
    solo(web, "prima")
    f, entra, _, _ = _prepara(web)
    web.risposta(ROTTA, {"detail": "Errore del server"}, stato=500)
    web.apri("/")
    prima = nomi_sul_campo(web)
    scritte = scritture(web)
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    assert scheda(web).get_by_role("alert").count() == 1
    assert nomi_sul_campo(web) == prima and stato(web) == "È la consigliata."
    assert not [p for m, p, c in scritte if p == "/api/formazione/valuta"]


def test_se_intanto_e_cominciato_il_suo_anticipo_la_scheda_dice_la_frase_del_server(web):
    """Revisione della #783: la pagina non sa ancora che la sua partita è cominciata (niente `bloccati`), il server sì e risponde
    400 `giocatore_bloccato` con la frase del salvataggio. La scheda dice quella frase, come informazione e non come guasto, al
    posto di «Nessun titolare può lasciargli il posto.»; niente si salva."""
    solo(web, "prima")
    f, entra, _, _ = _prepara(web)
    frase = f"{entra['nome']} gioca in una partita già cominciata: non si può più spostare."
    web.risposta(ROTTA, {"detail": frase, "codice": "giocatore_bloccato"}, stato=400)
    web.apri("/")
    prima = nomi_sul_campo(web)
    scritte = scritture(web)
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    testo = " ".join(scheda(web).inner_text().split())
    assert frase in testo and "Nessun titolare" not in testo, testo
    assert scheda(web).get_by_role("alert").count() == 0 and scheda(web).get_by_role("status").filter(has_text=frase).count() == 1
    assert nomi_sul_campo(web) == prima and not [p for m, p, c in scritte if p == "/api/formazione/valuta"]


def test_se_la_scheda_si_chiude_prima_della_risposta_l_elenco_non_si_riapre(web):
    """La risposta del server arriva dopo (rete lenta, «sto calcolando»): se nel frattempo la scheda è stata chiusa, resta chiusa."""
    solo(web, "prima")
    f, entra, difensore, _ = _prepara(web)
    tenute = []
    web.pagina.route(lambda u: urlsplit(u).path == ROTTA, lambda r: tenute.append(r))   # in sospeso finché il test non la dà
    web.apri("/")
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    assert len(tenute) == 1 and "Chi esce per" in scheda(web).get_by_role("heading").first.inner_text()
    web.pagina.keyboard.press("Escape")
    web.aspetta()
    assert scheda(web).count() == 0
    tenute[0].fulfill(status=200, content_type="application/json", body=json.dumps(_risposta(f, entra, [(difensore, "4-3-3", 0.4)])))
    web.pagina.wait_for_load_state("networkidle")
    web.aspetta()
    assert scheda(web).count() == 0, scheda(web).inner_text()


def test_se_il_salvataggio_trova_la_scelta_cambiata_altrove_la_pagina_rilegge_e_lo_dice(web):
    """412: il salvataggio dopo «Metti in campo» porta If-Match, come quello di «Sostituisci». Se nel frattempo un altro
    dispositivo ha salvato un'altra formazione, il server lo rifiuta: la pagina rilegge, mostra ciò che è salvato (non il cambio
    non riuscito) e l'avviso dice di controllare e rifare la modifica."""
    solo(web, "prima")
    f, entra, difensore, _ = _prepara(web, scelta_vuota=False)
    srv = server_con_etag(web, None)
    web.apri("/")
    altro = next(m for m in f["moduli"] if m["modulo"] != f["modulo"])
    srv["cambia"]({"titolari": altro["titolari"], "modulo": altro["modulo"], "salvata": "2026-10-27T15:09:00", "tipo": "manuale"})
    tocca(web, _riga_panchina(web, entra["nome"]))
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    tocca(web, _scelte(web).filter(has_text=difensore["nome"]).first.get_by_role("button"))
    _aspetta(web.pagina.get_by_role("status").filter(has_text="cambiati da un altro dispositivo").first, testo="controlla e rifai la modifica")
    web.aspetta()
    assert srv["if_match"] == ['"v0"'], srv["if_match"]                 # il salvataggio è partito con l'ETag letto all'apertura
    assert principale(web).get_by_label("Modulo").input_value() == altro["modulo"]
    salvati = {f["schede"][str(i)]["nome"] for i in altro["titolari"]}                # i nomi che sente un lettore di schermo
    assert set(nomi_sul_campo(web)) == salvati and stato(web).startswith("L'hai cambiata tu")
    assert sorted(srv["scelta"]["titolari"]) == sorted(altro["titolari"])          # niente scritto sopra l'altro dispositivo
    assert not web.errori_mostrati()


@pytest.mark.parametrize("tema", ["chiaro", "scuro"])
def test_la_scheda_del_panchinaro_e_l_elenco_di_chi_esce_non_hanno_violazioni_gravi(web, tema):
    solo(web, "prima")
    _, entra, _, _ = _prepara(web)
    web.apri("/", tema=tema)
    tocca(web, _riga_panchina(web, entra["nome"]))
    gravi = web.violazioni_gravi()
    assert not gravi, f"scheda, {tema}: {[(v['id'], v['nodi'][:2]) for v in gravi]}"
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    gravi = web.violazioni_gravi()
    assert not gravi, f"chi esce, {tema}: {[(v['id'], v['nodi'][:2]) for v in gravi]}"
    assert not web.scorre_di_lato()


# ---------------------------------------------------------------- dove c'è «Sostituisci» c'è anche «Metti in campo»
def test_i_titolari_hanno_sostituisci_e_non_metti_in_campo(web):
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    tocca(web, campo(web).first)
    assert scheda(web).get_by_role("button", name="Sostituisci").is_visible()
    assert scheda(web).get_by_role("button", name="Metti in campo").count() == 0


def test_infortunati_e_squalificati_si_mettono_in_campo_e_il_loro_stato_si_legge(web):
    """Come fra i sostituti di «Sostituisci», che li propone con il loro stato nella riga: qui il pulsante c'è, e lo stato si
    legge nella scheda e in cima all'elenco di chi esce."""
    solo(web, "prima")
    web.risposta("/api/scelta?giornata=9", None)
    f = web.registrata("/api/formazione")
    fuori = next(x for x in f["schede"].values() if _codice(x) in NON_GIOCANO)
    parola = fuori["etichetta"]["testo"]
    web.risposta(ROTTA, _risposta(f, fuori, [(_titolare(f, fuori["ruolo"]), f["modulo"], -4.1)]))
    web.apri("/")
    principale(web).get_by_text("Infortunati e squalificati", exact=False).first.click()
    tocca(web, principale(web).get_by_role("listitem").filter(has_text=fuori["nome"]).first.get_by_role("button"))
    assert fuori["nome"] in scheda(web).get_by_role("heading").first.inner_text() and parola in scheda(web).inner_text()
    tocca(web, scheda(web).get_by_role("button", name="Metti in campo"))
    assert "Chi esce per" in scheda(web).get_by_role("heading").first.inner_text()
    assert parola in scheda(web).locator("#entra-stato").inner_text()
    assert "−4,1" in _scelte(web).first.inner_text()


def test_a_giornata_finita_c_e_per_la_prossima_come_sostituisci(web):
    """A giornata finita sotto il riepilogo c'è la formazione della prossima, che si può cambiare: «Sostituisci» per i titolari
    e «Metti in campo» per gli altri."""
    solo(web, "finita")
    web.apri("/")
    f = web.registrata("/api/formazione")
    tocca(web, campo(web).first)
    assert scheda(web).get_by_role("button", name="Sostituisci").is_visible()
    web.pagina.keyboard.press("Escape")
    web.aspetta()
    tocca(web, _riga_panchina(web, _panchinaro(f)["nome"]))
    assert scheda(web).get_by_role("button", name="Metti in campo").is_visible()


def test_chi_entra_a_giornata_iniziata_prepara_la_prossima_anche_con_metti_in_campo(web):
    """Entrato a partite cominciate, senza una formazione per la giornata in corso: la Formazione è quella della prossima, ancora
    aperta (`senza_formazione` di /api/oggi). Lì «Sostituisci» c'è, quindi anche «Metti in campo»."""
    solo(web, "in-corso")
    f = web.registrata("/api/formazione")
    web.risposta("/api/oggi", {**web.registrata("/api/oggi"), "senza_formazione": True})
    web.risposta("/api/formazione", {**f, "iniziata": False})
    web.apri("/")
    tocca(web, campo(web).first)
    assert scheda(web).get_by_role("button", name="Sostituisci").is_visible()
    web.pagina.keyboard.press("Escape")
    web.aspetta()
    tocca(web, principale(web).locator("#panchina").get_by_role("listitem").nth(2).get_by_role("button"))
    assert scheda(web).get_by_role("button", name="Metti in campo").is_visible()


# ---------------------------------------------------------------- quando il pulsante non c'è
def test_chi_gioca_un_anticipo_gia_cominciato_non_si_mette_in_campo_e_la_scheda_dice_perche(web):
    solo(web, "prima")
    f, entra, _, _ = _prepara(web)
    web.risposta("/api/formazione", {**f, "bloccati": [entra["id"]]})
    web.apri("/")
    tocca(web, _riga_panchina(web, entra["nome"]))
    assert scheda(web).get_by_role("button", name="Metti in campo").count() == 0
    assert "non si può più spostare" in scheda(web).inner_text()


def test_a_giornata_in_corso_il_pulsante_non_c_e(web):
    """La formazione è chiusa: come «Sostituisci», niente «Metti in campo»."""
    solo(web, "in-corso")
    web.apri("/")
    panchina = principale(web).locator("#panchina").get_by_role("listitem")
    assert panchina.count() >= 3
    for k in range(3):
        tocca(web, panchina.nth(k).get_by_role("button"))
        assert scheda(web).get_by_role("heading").first.is_visible()
        assert scheda(web).get_by_role("button", name="Metti in campo").count() == 0, panchina.nth(k).inner_text()
        web.pagina.keyboard.press("Escape")
        web.aspetta()
