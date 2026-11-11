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


def test_la_prima_schermata_ha_solo_accedi_e_registrati():
    assert 'const SCHEDE_ACCESSO = ["accedi", "registra"];' in APP
    assert 'id="accesso-dimenticata"' in APP                  # «Password dimenticata» è un link sotto l'accesso


def test_gli_errori_generici_non_mostrano_codici():
    testi = codice_web.leggi("testi.js")
    assert "{n})" not in testi.split('"comune.errore_server"')[1].split("\n")[0]
    assert '"comune.errore_n": "Errore {n}"' not in testi
