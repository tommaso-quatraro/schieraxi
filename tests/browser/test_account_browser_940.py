"""Account sulla web, collaudo del 26/11 (#940): cosa vede chi entra, esce, elimina l'account o gestisce gli inviti.

- «Elimina l'account»: prima la password (con quella sbagliata nessun «Sei sicuro?»), poi la conferma; dopo, la pagina d'accesso
  dice che l'account non c'è più.
- Sessione finita mentre si usa l'app: un solo messaggio, quello della pagina d'accesso (prima anche «Accesso richiesto»).
- «Troppi tentativi»: la frase una volta sola e il conto che scende davvero, nel pulsante (come l'iPhone).
- Registrati: le regole del nome utente sotto il campo, prima di sbagliare.
- La pagina d'accesso non scrive errori nella console.
- Gestione › Nuovo invito: anche per un gruppo di amici, con il numero di persone.
Le risposte del server sono finte (nomi inventati); si guarda ciò che succede a un tocco, non il sorgente.
"""
import json
import re
from urllib.parse import urlsplit

from test_impostazioni import (AMMINISTRATORE, REGISTRO, UTENTE, carta_con, da_utente, principale, server_che_cambia, solo, titolo,
                               tocca)

SENZA_SESSIONE = {"detail": "Accesso richiesto", "multiutente": True, "registrazione": "invito", "social": [], "email_attiva": True}
NESSUNO = {k: v for k, v in SENZA_SESSIONE.items() if k != "detail"} | {"utente": None}
SESSIONE_FINITA = "La sessione è finita: accedi di nuovo."


def json_risposta(route, corpo, stato: int = 200, intestazioni: dict | None = None) -> None:
    route.fulfill(status=stato, content_type="application/json; charset=utf-8", body=json.dumps(corpo, ensure_ascii=False),
                  headers=intestazioni or {})


def accesso(web):
    return web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI"))


# ---------------------------------------------------------------- Elimina l'account
def apri_elimina(web, controllo: tuple[int, dict]) -> dict[str, list]:
    """Il tuo account con «Elimina l'account» aperto e la password scritta. «Chi sono» risponde con l'utente finché l'account c'è,
    poi come il server vero a chi non è dentro. Restituisce le richieste arrivate e le domande del browser."""
    stato = {"eliminato": False, "richieste": [], "domande": []}

    def chi_sono(route):
        if stato["eliminato"]:
            json_risposta(route, NESSUNO if "anche_senza_accesso" in route.request.url else SENZA_SESSIONE,
                          200 if "anche_senza_accesso" in route.request.url else 401)
        else:
            json_risposta(route, UTENTE)

    def controlla(route):
        stato["richieste"].append(("controlla", json.loads(route.request.post_data or "{}")))
        json_risposta(route, controllo[1], controllo[0])

    def elimina(route):
        stato["richieste"].append(("elimina", json.loads(route.request.post_data or "{}")))
        stato["eliminato"] = True
        json_risposta(route, {"ok": True})

    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/me", chi_sono)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/elimina/controlla", controlla)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/elimina", elimina)
    web.apri("/?vista=impostazioni&gruppo=account")
    tocca(web, principale(web).get_by_text("Elimina l'account", exact=True))
    principale(web).get_by_label("La tua password").last.fill("Password-Finta-1")
    return stato


def test_elimina_con_la_password_sbagliata_non_chiede_conferma(web):
    solo(web, "prima")
    stato = apri_elimina(web, (403, {"detail": "La password non è giusta"}))
    web.pagina.on("dialog", lambda d: (stato["domande"].append(d.message), d.dismiss()))
    principale(web).get_by_role("button", name="Elimina il mio account").click(timeout=10000)
    web.pagina.locator("#avviso").filter(has_text="La password non è giusta").wait_for(timeout=10000)
    web.aspetta()
    assert stato["domande"] == [], f"la conferma è arrivata prima del controllo della password: {stato['domande']}"
    assert stato["richieste"] == [("controlla", {"password": "Password-Finta-1"})], stato["richieste"]
    assert titolo(web) == "Il tuo account"


def test_elimina_annullato_dopo_il_controllo_non_elimina(web):
    solo(web, "prima")
    stato = apri_elimina(web, (200, {"ok": True}))
    web.pagina.on("dialog", lambda d: (stato["domande"].append(d.message), d.dismiss()))
    principale(web).get_by_role("button", name="Elimina il mio account").click(timeout=10000)
    web.aspetta()
    assert stato["domande"] == ["Elimino il tuo account e TUTTI i tuoi dati? Non si può annullare."], stato["domande"]
    assert [r[0] for r in stato["richieste"]] == ["controlla"], stato["richieste"]
    assert titolo(web) == "Il tuo account"


def test_elimina_riuscito_lo_dice_la_pagina_d_accesso(web):
    """Dopo l'eliminazione la pagina d'accesso non resta muta: un avviso (`role="status"`, non un errore) dice che l'account e i dati
    non ci sono più. Una volta sola: ricaricata la pagina, l'accesso torna quello di sempre."""
    solo(web, "prima")
    stato = apri_elimina(web, (200, {"ok": True}))
    web.pagina.on("dialog", lambda d: (stato["domande"].append(d.message), d.accept()))
    with web.pagina.expect_navigation(wait_until="load"):
        principale(web).get_by_role("button", name="Elimina il mio account").click(timeout=10000)
    accesso(web).get_by_role("status").filter(has_text="Il tuo account e tutti i tuoi dati sono stati eliminati.").wait_for(timeout=10000)
    assert [r[0] for r in stato["richieste"]] == ["controlla", "elimina"], stato["richieste"]
    assert [t for t in web.pagina.locator('[role="alert"]').all_inner_texts() if t.strip()] == []
    web.pagina.reload(wait_until="load")
    accesso(web).get_by_role("button", name="Accedi").first.wait_for(timeout=10000)
    assert "eliminati" not in accesso(web).inner_text()


# ---------------------------------------------------------------- sessione finita
def test_sessione_finita_un_solo_messaggio(web):
    """La sessione finisce mentre si usa l'app (chiusa da un altro dispositivo, scaduta): la richiesta dopo riceve 401 e si apre
    la pagina d'accesso con «La sessione è finita: accedi di nuovo.». Prima arrivava anche l'avviso «Accesso richiesto» del server."""
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), lambda route: json_risposta(route, SENZA_SESSIONE, 401))
    tocca(web, principale(web).get_by_text("Scarica i tuoi dati", exact=True))
    principale(web).get_by_role("button", name="Scarica il file").click(timeout=10000)
    accesso(web).get_by_role("status").filter(has_text=SESSIONE_FINITA).wait_for(timeout=10000)
    web.pagina.wait_for_timeout(600)
    avvisi = [t for t in web.pagina.locator("#avviso:visible").all_inner_texts() if t.strip()]
    assert avvisi == [], f"oltre alla pagina d'accesso è comparso un altro messaggio: {avvisi}"
    assert "Accesso richiesto" not in web.pagina.locator("body").inner_text()


# ---------------------------------------------------------------- troppi tentativi
def apri_accesso(web, me: dict | None = None):
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/me",
                     lambda route: json_risposta(route, me or NESSUNO, 200) if "anche_senza_accesso" in route.request.url
                     else json_risposta(route, SENZA_SESSIONE, 401))
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    web.pagina.locator("#accesso-form").wait_for(timeout=10000)


def test_troppi_tentativi_la_frase_una_volta_e_il_conto_scende(web):
    solo(web, "prima")
    apri_accesso(web)
    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/accedi", lambda route: json_risposta(
        route, {"detail": "Troppi tentativi: riprova più tardi", "riprova_tra": 3}, 429, {"Retry-After": "3"}))
    web.pagina.locator("#ac-nome").fill("amico")
    web.pagina.locator("#ac-pw").fill("Password-Finta-1")
    web.pagina.locator("#accesso-invia").click()
    messaggio = accesso(web).get_by_role("alert")
    messaggio.filter(has_text="Troppi tentativi").wait_for(timeout=10000)
    assert " ".join(messaggio.inner_text().split()) == "Troppi tentativi.", messaggio.inner_text()
    invia = web.pagina.locator("#accesso-invia")
    primo = invia.inner_text().strip()
    assert invia.is_disabled() and re.fullmatch(r"Riprova tra [23] secondi", primo), primo
    web.pagina.wait_for_function("() => /Riprova tra 1 secondo$/.test(document.querySelector('#accesso-invia').innerText.trim())",
                                 timeout=5000)
    # a zero il pulsante torna quello di prima e la frase dell'attesa se ne va
    web.pagina.wait_for_function("() => document.querySelector('#accesso-invia').innerText.trim() === 'Accedi'", timeout=5000)
    assert invia.is_enabled()
    assert "Troppi tentativi" not in accesso(web).inner_text()
    assert web.pagina.locator("#ac-pw").input_value() == "Password-Finta-1", "un'attesa non fa perdere quello che hai scritto"


# ---------------------------------------------------------------- nome utente
REGOLE_NOME = ("Da 3 a 32 caratteri: lettere senza accenti, numeri, punto, trattino o trattino basso. "
               "Comincia con una lettera o un numero.")


def test_registrati_mostra_le_regole_del_nome_prima_dell_errore(web):
    solo(web, "prima")
    apri_accesso(web)
    assert REGOLE_NOME not in accesso(web).inner_text(), "per entrare le regole non servono"
    web.pagina.locator("#accesso-schede button[data-s='registra']").click()
    web.pagina.locator("#ac-letto").wait_for(timeout=10000)
    nome = web.pagina.get_by_label("Nome utente", exact=True)
    aiuto = nome.get_attribute("aria-describedby")
    assert aiuto and web.pagina.locator(f"#{aiuto}").inner_text().strip() == REGOLE_NOME
    sotto = web.pagina.locator(f"#{aiuto}").bounding_box()
    assert sotto["y"] > nome.bounding_box()["y"], "le regole stanno sotto il campo"


# ---------------------------------------------------------------- console pulita
def test_la_pagina_d_accesso_non_scrive_errori_nella_console(web):
    solo(web, "prima")
    apri_accesso(web)
    web.aspetta()
    assert web.errori_console == [], web.errori_console
    assert web.richieste_fallite == [], web.richieste_fallite


# ---------------------------------------------------------------- invito per un gruppo
CREATO = {"codice": "PROVA-PROVA-PROVA-PROVA", "etichetta": "Lega", "valido_giorni": 7, "usi_max": 12, "id": 3,
          "avviso": None, "avviso_frase": None}


def gestione_con_inviti(web, max_usi: int = 30, creato: dict | None = None) -> list[dict]:
    """Gestione di chi gestisce il server; GET /api/admin/inviti dice il tetto delle persone (`max_usi`, come il server dal #940).
    Restituisce i corpi dei POST /api/admin/inviti mandati."""
    da_utente(web, AMMINISTRATORE)
    mandati: list[dict] = []
    server_che_cambia(web, "/api/admin/utenti", [{"utenti": [], "massimo": 30, "avviso": None, "avviso_frase": None}])
    server_che_cambia(web, "/api/admin/inviti", [{"inviti": [], "max_usi": max_usi}], {"POST": creato or CREATO, "DELETE": {"ok": True}})
    web.risposta("/api/admin/registro", REGISTRO)
    web.pagina.on("request", lambda r: r.method == "POST" and urlsplit(r.url).path == "/api/admin/inviti"
                  and mandati.append(json.loads(r.post_data or "{}")))
    web.apri("/?vista=impostazioni&gruppo=gestione")
    return mandati


def test_nuovo_invito_per_un_gruppo_di_amici(web):
    """Il link di gruppo per la chat degli amici (#940): in Nuovo invito si scrive quante persone (fino a 30) e il server crea un
    invito solo con tanti posti. L'esito dice per quante persone vale e che il link va nella chat."""
    solo(web, "prima")
    mandati = gestione_con_inviti(web)
    carta = carta_con(web, "Amministrazione")
    carta.get_by_label("Etichetta").fill("Lega")
    persone = carta.get_by_label("Quante persone", exact=False)
    assert persone.input_value() == "1"
    persone.fill("12")
    tocca(web, carta.get_by_role("button", name="Crea l'invito"))
    carta.get_by_text("PROVA-PROVA-PROVA-PROVA", exact=False).first.wait_for(timeout=10000)
    assert mandati == [{"etichetta": "Lega", "amministratore": False, "usi": 12}], mandati
    testo = " ".join(carta.inner_text().split())
    assert "Invito per «Lega», valido 7 giorni, per 12 persone." in testo, testo
    assert "nella chat" in testo, testo
    assert not web.errori_console and not web.richieste_fallite


def test_nuovo_invito_con_un_numero_che_non_va_non_parte(web):
    solo(web, "prima")
    mandati = gestione_con_inviti(web)
    carta = carta_con(web, "Amministrazione")
    carta.get_by_label("Etichetta").fill("Lega")
    carta.get_by_label("Quante persone", exact=False).fill("40")
    tocca(web, carta.get_by_role("button", name="Crea l'invito"))
    web.pagina.locator("#avviso").filter(has_text="da 1 a 30").wait_for(timeout=5000)
    assert mandati == []


def test_il_tetto_delle_persone_arriva_dal_server(web):
    """La web non ha una sua copia del tetto: con un server che ne ammette 12 la spiegazione dice «Da 1 a 12», il «+» si ferma a
    12 e 13 non parte."""
    solo(web, "prima")
    mandati = gestione_con_inviti(web, max_usi=12)
    carta = carta_con(web, "Amministrazione")
    carta.get_by_text("Da 1 a 12:", exact=False).wait_for(timeout=5000)
    persone = carta.get_by_label("Quante persone", exact=False)
    persone.fill("11")
    piu = carta.get_by_role("button", name="Aumenta")
    piu.click()
    piu.click()
    assert persone.input_value() == "12"
    carta.get_by_label("Etichetta").fill("Lega")
    persone.fill("13")
    tocca(web, carta.get_by_role("button", name="Crea l'invito"))
    web.pagina.locator("#avviso").filter(has_text="da 1 a 12").wait_for(timeout=5000)
    assert mandati == []


# ---------------------------------------------------------------- doppio tocco su «Elimina il mio account»
def test_elimina_un_tocco_solo_fino_alla_fine(web):
    """Il pulsante resta spento per tutto il percorso (controllo, domanda, eliminazione): un secondo tocco mentre il server
    risponde non manda un secondo controllo né una seconda domanda. Annullata la domanda, torna acceso."""
    solo(web, "prima")
    da_utente(web)
    in_attesa, controlli, domande = [], [], []

    def controlla(route):
        controlli.append(1)
        in_attesa.append(route)                                   # risponde il test, quando vuole

    web.pagina.route(lambda u: urlsplit(u).path == "/api/account/elimina/controlla", controlla)
    web.apri("/?vista=impostazioni&gruppo=account")
    tocca(web, principale(web).get_by_text("Elimina l'account", exact=True))
    principale(web).get_by_label("La tua password").last.fill("Password-Finta-1")
    web.pagina.on("dialog", lambda d: (domande.append(d.message), d.dismiss()))
    pulsante = principale(web).get_by_role("button", name="Elimina il mio account")
    pulsante.click(timeout=10000)
    web.pagina.wait_for_function("() => document.querySelector('#acc-elimina').disabled", timeout=5000)
    web.pagina.evaluate("() => document.querySelector('#acc-elimina').click()")          # il secondo tocco
    assert len(controlli) == 1 and len(in_attesa) == 1, controlli
    json_risposta(in_attesa[0], {"ok": True})
    web.pagina.wait_for_function("() => !document.querySelector('#acc-elimina').disabled", timeout=5000)
    assert len(domande) == 1 and len(controlli) == 1, (domande, controlli)
