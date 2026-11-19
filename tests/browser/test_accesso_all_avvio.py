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
    web.risposta("/api/account/me", SENZA_SESSIONE, stato=401)        # la sessione è stata chiusa da un altro dispositivo
    web.pagina.goto(web.server.indirizzo + "/?vista=formazione", wait_until="load")
    aspetta_accesso(web)
    dopo = web.pagina.evaluate(COPIE)
    assert dopo == {"memoria": [], "cache": []}, f"restano copie di chi non è più dentro: {dopo}"
    # riaperta senza rete, la web non ha più niente dell'account da mostrare
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
