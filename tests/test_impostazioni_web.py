"""Impostazioni ripulite: controlli statici su app.js, impostazioni.js, index.html, stile.css. Decisioni del 1/11/2026: poche voci,
ogni cosa in un posto solo, niente strumenti tecnici per l'utente normale. Dal 12/11/2026 (#618) Impostazioni è una scheda della
barra con una pagina sola: barra, sezioni, pagine e indirizzi si provano nel browser (tests/browser/test_impostazioni.py)."""
import re

from fanta import server
from testi_it import espandi
import codice_web

WEB = server.WEB
APP = espandi(codice_web.app())
IMP = espandi(codice_web.leggi("impostazioni.js"))
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
SW = codice_web.leggi("sw.js")


def test_script_delle_impostazioni_caricato_dopo_l_app_e_in_copia():
    assert HTML.index('src="app.js"') < HTML.index('src="impostazioni.js"')
    assert "/impostazioni.js" in SW
    assert '"/impostazioni.js"' in (WEB.parent / "rotte_account.py").read_text(encoding="utf-8")


def test_niente_strumenti_tecnici_per_l_utente():
    """Tolti: collegamento e indirizzo del server, widget con il codice, copia di sicurezza, installazione, icone, Sotto il cofano."""
    for vecchio in ("collegamento", "col-indirizzo", "col-copia", "token-widget", "widget-collega", "backup-dati", "installa-bottone",
                    "icona-app", "apri-cofano", "apri-primo-avvio", "copia-indirizzo", "imp-novita"):
        assert vecchio not in IMP, vecchio
    for funzione in ("function backupDati", "function iconaApp", "function vistaCofano", "function collegaWidget", "function tabAsta"):
        assert funzione not in APP and funzione not in IMP, funzione
    assert '"/api/sotto-il-cofano"' not in APP and '"/api/icona"' not in APP
    assert 'api("/api/backup/ripristina"' not in APP and "/api/backup/ripristina" not in IMP      # il ripristino non torna
    assert "Copia di sicurezza" not in APP and "backup-ripristina" not in APP and "backup-file" not in APP


def test_scarica_i_tuoi_dati_nell_account_solo_scarico():
    """Portabilità (GDPR art. 20): una voce sola in Il tuo account che scarica il file JSON dei propri dati, senza ripristino."""
    acc = APP[APP.index("function schedaAccount()"):APP.index("function schedaAmministratore()")]
    assert "<summary>Scarica i tuoi dati</summary>" in acc and 'id="acc-scarica-dati"' in acc
    assert acc.index("Scarica i tuoi dati") < acc.index("Elimina l'account")              # prima di eliminare, non dopo
    assert re.search(r'class="bottone secondario" id="acc-scarica-dati" type="button"', acc)    # .bottone: min-height 46px
    assert re.search(r"\.bottone \{[^}]*min-height: 46px", CSS)
    assert 'addEventListener("click", () => scaricaIMieiDati())' in APP
    f = APP[APP.index("async function scaricaIMieiDati()"):APP.index("function schedaAmministratore()")]
    assert 'api("/api/backup")' in f and "ripristina" not in f and 'type="file"' not in f
    assert "schieraxi-i-miei-dati-" in f
    testi = codice_web.leggi("testi.js")
    assert '"account.dati_titolo": "Scarica i tuoi dati"' in testi and '"account.dati_titolo": "Download your data"' in testi


def test_account_un_solo_nome_e_solo_le_voci_utili():
    acc = APP[APP.index("function schedaAccount()"):APP.index("function schedaAmministratore()")]
    assert "esc(a.nome_visualizzato || a.nome_utente)" in acc                   # un solo nome mostrato
    for vecchio in ("acc-esci-tutti", "acc-nome-vis", "acc-nome-salva", "acc-esporta", "Esci da tutti"):
        assert vecchio not in acc and vecchio not in APP, vecchio
    for resta in ('id="acc-email"', 'id="acc-accessi"', 'id="acc-cambia"', 'id="acc-elimina"', 'id="acc-esci"'):
        assert resta in acc, resta
    assert "scheda-admin" not in acc                                            # l'amministrazione sta in Gestione
    assert "schedaAmministratore()" in IMP and "collegaAmministratore();" in IMP


def test_informazioni_privacy_termini_crediti_e_versione():
    info = IMP[IMP.index("function paginaInformazioni()"):IMP.index("function paginaGestione()")]
    pos = [info.index(x) for x in ('"privacy"', '"termini"', '"crediti"', "Versione")]
    assert pos == sorted(pos)
    assert 'rel="noopener"' in IMP and "queryLingua()" in IMP


def test_testi_senza_gergo_per_l_utente():
    testo = " ".join(re.findall(r">([^<>$`]+)<", IMP) + re.findall(r'avviso\("([^"]+)"', IMP))        # solo quello che si legge
    for parola in ("token", "Tailscale", "ntfy", "ALTAppGroups", "POST", "202", "403", "/api", "server"):
        assert parola not in testo, parola


def test_bersagli_da_44_px():
    assert re.search(r"\.capo-pagina \.imp-torna \{ min-height: 44px", CSS)                  # «‹ Impostazioni» delle pagine interne
    assert re.search(r"\.bottone-icona \{ width: 44px; height: 44px", CSS)
