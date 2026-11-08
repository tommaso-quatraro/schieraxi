"""Accesso con Google nella web app: controlli statici (il giro vero è provato con un browser e un server di prova)."""
import codice_web

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
SW = codice_web.leggi("sw.js")


def test_il_pulsante_compare_solo_se_il_server_ha_google():
    assert 'socialPronto() && SCHEDE_ACCESSO.includes(scheda)' in APP
    assert "const socialPronto = () => Array.isArray(stato.social) && stato.social.includes(\"google\");" in APP
    assert 'stato.social = dati && Array.isArray(dati.social) ? dati.social : [];' in APP


def test_il_segreto_resta_nella_scheda_e_il_codice_si_toglie_dall_indirizzo():
    assert 'sessionStorage.setItem("social"' in APP and 'localStorage.setItem("social"' not in APP
    assert 'history.replaceState(null, "", "/")' in APP
    assert 'r.url.startsWith("https://accounts.google.com/")' in APP
    assert 'url.searchParams.has("social")' in SW                      # il ritorno non finisce nella cache del service worker


def test_i_valori_dell_utente_passano_da_esc():
    assert 'value="${esc(r.nome_suggerito || "")}"' in APP
    assert 'esc(g.email || t("social.google_account"))' in APP


def test_ogni_testo_social_c_e_in_italiano_e_in_inglese():
    usati = {k for k in __import__("re").findall(r't\("(social\.[a-z_]+)"', APP)}
    assert usati
    for lingua in ("it", "en"):
        blocco = TESTI.split("  en: {")[1] if lingua == "en" else TESTI.split("  en: {")[0]
        for k in usati | {"social.email_gia_usata", "social.ultimo_accesso", "social.serve_riconferma"}:
            assert f'"{k}":' in blocco, (lingua, k)


def test_nessun_identificativo_google_nel_codice_web():
    assert "googleusercontent" not in APP and "client_secret" not in APP
