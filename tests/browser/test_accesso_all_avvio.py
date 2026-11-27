"""All'avvio, con gli account accesi, «chi sono» può rispondere che la sessione non vale più (401): la web allora toglie le copie che
aveva salvato in questo browser (dati, account, copie del service worker), come quando si esce, e mostra l'accesso. I passi
dell'accesso in corso restano (il codice di un link d'invito). Girano solo prima della scadenza: conta l'avvio, non la fase.
"""
import json
from urllib.parse import urlsplit

import pytest

UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
# la risposta del server con gli account a chi non ha una sessione valida (vedi `rotte_account.py`)
SENZA_SESSIONE = {"detail": "Accesso richiesto", "multiutente": True, "registrazione": "invito", "social": [], "email_attiva": True}
COPIE = """async () => ({
  memoria: Object.keys(localStorage).filter(k => k.startsWith('cache:') || ['account', 'archivio-scambi'].includes(k)),
  cache: window.caches ? await caches.keys() : [] })"""


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("conta l'avvio, non la fase della giornata")


def aspetta_accesso(web):
    web.pagina.locator("#accesso-form").wait_for(timeout=10000)


def test_all_avvio_senza_sessione_le_copie_salvate_si_tolgono(web):
    solo_prima(web)
    web.risposta("/api/account/me", UTENTE)
    web.apri("/?vista=formazione")
    assert "punti attesi" in web.testo_principale()
    web.pagina.evaluate("() => caches.open('prova-copie').then(c => c.put('/prova-copia', new Response('dati')))")
    prima = web.pagina.evaluate(COPIE)
    assert "account" in prima["memoria"] and any(k.startswith("cache:") for k in prima["memoria"]) and prima["cache"], prima
    web.risposta("/api/account/me", SENZA_SESSIONE, stato=401)        # da qui la sessione non vale più
    web.pagina.goto(web.server.indirizzo + "/?vista=formazione", wait_until="load")
    aspetta_accesso(web)
    dopo = web.pagina.evaluate(COPIE)
    assert dopo == {"memoria": [], "cache": []}, f"restano copie di chi non è più dentro: {dopo}"
    # riaperta senza rete: nessun dato dell'account
    web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/"), lambda r: r.abort())
    web.pagina.goto(web.server.indirizzo + "/?vista=formazione", wait_until="load")
    web.aspetta()
    assert "punti attesi" not in web.testo_principale(), web.testo_principale()[:300]


def test_all_avvio_senza_sessione_il_codice_d_invito_resta(web):
    solo_prima(web)
    web.memoria({"account": json.dumps(UTENTE["utente"]), "cache:3:u7:oggi": json.dumps({"quando": 0, "dati": {"prova": 1}})})
    web.risposta("/api/account/me", SENZA_SESSIONE, stato=401)
    web.pagina.goto(web.server.indirizzo + "/?invito=PROVA-1234", wait_until="load")
    aspetta_accesso(web)
    assert web.pagina.locator("#ac-invito").input_value() == "PROVA-1234"
    assert web.pagina.evaluate(COPIE)["memoria"] == []


# ---------------------------------------------------------------- registrazione aperta (26/11/2026)
APERTA = {**SENZA_SESSIONE, "registrazione": "aperta"}


def apri_registrati(web, senza_sessione: dict = APERTA, larghezza: int = 390):
    web.risposta("/api/account/me", senza_sessione, stato=401)
    web.pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    aspetta_accesso(web)
    web.pagina.locator("#accesso-schede button[data-s='registra']").click()
    web.pagina.locator("#ac-letto").wait_for(timeout=10000)


def test_registrazione_aperta_la_trappola_non_si_vede_e_non_si_raggiunge(web):
    """Il campo trappola (per i programmi che compilano tutto) non si vede e non si raggiunge con Tab: dalla password il Tab passa
    ai collegamenti di Privacy e Termini, alla casella e al pulsante, mai alla trappola. Nessuna violazione grave di accessibilità."""
    solo_prima(web)
    apri_registrati(web)
    trappola = web.pagina.locator("#ac-sito")
    assert trappola.count() == 1 and not trappola.is_visible()
    web.pagina.locator("#ac-pw").focus()
    toccati = []
    for _ in range(6):
        web.pagina.keyboard.press("Tab")
        toccati.append(web.pagina.evaluate("() => document.activeElement ? (document.activeElement.id || document.activeElement.textContent.trim()) : ''"))
        if toccati[-1] == "accesso-invia":
            break
    assert "ac-sito" not in toccati and "ac-letto" in toccati and toccati[-1] == "accesso-invia", toccati
    # niente regole di accessibilità rotte dalla trappola (il contrasto qui si misura mentre la schermata entra, uguale con l'invito)
    rotte = {v["id"] for v in web.violazioni_gravi()} - {"color-contrast"}
    assert not rotte, rotte


def test_registrazione_aperta_al_completo_lo_dice_e_la_password_resta(web):
    """Posti finiti: il messaggio del server, come errore, e quello che si è scritto resta."""
    solo_prima(web)
    web.risposta("/api/account/registra", {"detail": "Iscrizioni chiuse: siamo al completo."}, stato=403)
    apri_registrati(web)
    web.pagina.locator("#ac-nome").fill("amico")
    web.pagina.locator("#ac-pw").fill("una-password-lunga-9")
    web.pagina.locator("#ac-letto").check()
    web.pagina.locator("#accesso-invia").click()
    errore = web.pagina.locator("#accesso-msg [role=alert]")
    errore.wait_for(timeout=10000)
    assert errore.inner_text().strip() == "Iscrizioni chiuse: siamo al completo."
    assert web.pagina.locator("#ac-pw").input_value() == "una-password-lunga-9"


def test_registrazione_aperta_con_le_email_spente_non_chiede_l_email(web):
    solo_prima(web)
    apri_registrati(web, {**APERTA, "email_attiva": False})
    assert web.pagina.locator("#ac-email").count() == 0 and web.pagina.locator("#ac-invito").count() == 0
    assert web.pagina.locator("#ac-nome").is_visible() and web.pagina.locator("#ac-pw").is_visible()


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_password_dimenticata_ha_il_suo_titolo_al_posto_delle_schede(web, larghezza):
    """Collaudo del 27/11 sera: la pagina non aveva un titolo e in alto c'erano «Accedi» e «Registrati», nessuna delle due scelta.
    Ora al posto delle schede il titolo «Password dimenticata»; «Torna all'accesso» riporta le schede, con «Accedi» scelta."""
    solo_prima(web)
    web.risposta("/api/account/me", SENZA_SESSIONE, stato=401)
    web.pagina.set_viewport_size({"width": larghezza, "height": 844 if larghezza < 600 else 900})
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    aspetta_accesso(web)
    accesso = web.pagina.get_by_role("dialog")
    accesso.get_by_role("link", name="Password dimenticata").click()
    titolo = accesso.get_by_role("heading", name="Password dimenticata")
    titolo.wait_for(timeout=10000)
    assert titolo.is_visible()
    assert accesso.get_by_role("button", name="Accedi", exact=True).count() == 0
    assert accesso.get_by_role("button", name="Registrati", exact=True).count() == 0
    accesso.get_by_role("link", name="Torna all'accesso").click()
    scelta = accesso.get_by_role("button", name="Accedi", exact=True).first
    scelta.wait_for(timeout=10000)
    assert accesso.locator("[aria-pressed='true']").all_inner_texts() == ["Accedi"]
    assert accesso.get_by_role("heading", name="Password dimenticata").count() == 0


def test_registrazione_aperta_password_dimenticata_parte_dal_codice(web):
    """L'email è facoltativa: «Password dimenticata» parte dal codice di recupero, come con l'invito."""
    solo_prima(web)
    web.risposta("/api/account/me", APERTA, stato=401)
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    aspetta_accesso(web)
    web.pagina.locator("#accesso-dimenticata").click()
    web.pagina.locator("#ac-codice").wait_for(timeout=10000)
    assert web.pagina.locator("#accesso-metodi button[data-m='codice'][aria-pressed='true']").count() == 1
