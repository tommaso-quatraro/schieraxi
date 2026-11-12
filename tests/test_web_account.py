"""Account nella web app: controlli statici (la prova nel browser si fa a mano)."""
import codice_web

APP = codice_web.app()


def test_la_password_resta_dopo_un_errore_di_compilazione():
    assert 'svuotaPassword(scheda, e.status)) $("#ac-pw").value' in APP              # solo se rifiutata (test_ingresso_amico_web.py)
    assert "e.status = 400; throw e; }" in APP                                      # casella non spuntata: errore locale


def test_un_solo_nome_e_niente_maiuscole_da_cambiare():
    """Dal 1/11/2026 (come sull'iPhone) il nome si mostra e basta: niente «Maiuscole del nome» né «Esci da tutti i dispositivi»."""
    assert "esc(a.nome_visualizzato || a.nome_utente)" in APP
    assert "acc-nome-vis" not in APP and "esci-da-tutti" not in APP


def test_web_cambio_password_mostra_subito_il_codice_nuovo():
    """La risposta del cambio password ha il nuovo codice di recupero: si mostra nel riquadro del codice, come «Genera un nuovo codice»."""
    gestore = APP.split('api("/api/account/cambia-password"')[1].split("}));")[0]
    assert 'mostraCodice("#acc-esito-password", r.codice_recupero)' in gestore
    assert 't("account.password_cambiata_codice")' in gestore


def test_web_cambio_password_e_recupero_mandano_le_notifiche_di_questo_dispositivo():
    """Dopo un cambio di password o un recupero restano solo le notifiche del dispositivo che lo fa: il suo indirizzo va al server."""
    for percorso in ('"/api/account/cambia-password"', '"/api/account/recupero"', '"/api/account/recupero-email/conferma"'):
        prima, dopo = APP.split(percorso, 1)
        chiamata = prima[-300:] + dopo.split("\n", 1)[0]
        assert "await endpointPushQui()" in chiamata and "endpoint_push" in chiamata, percorso
    assert "navigator.serviceWorker.getRegistration()" in APP.split("async function endpointPushQui()")[1].split("\n}\n")[0]


def test_la_prima_schermata_ha_solo_accedi_e_registrati():
    assert 'const SCHEDE_ACCESSO = ["accedi", "registra"];' in APP
    assert 'id="accesso-dimenticata"' in APP                  # «Password dimenticata» è un link sotto l'accesso


def test_gli_errori_generici_non_mostrano_codici():
    testi = codice_web.leggi("testi.js")
    assert "{n})" not in testi.split('"comune.errore_server"')[1].split("\n")[0]
    assert '"comune.errore_n": "Errore {n}"' not in testi
