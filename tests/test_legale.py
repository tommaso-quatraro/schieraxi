"""Pagine Privacy e Termini: pubbliche (anche con gli account accesi), testi in un solo posto, contatto protetto."""
import re

import pytest
from fastapi.testclient import TestClient

from fanta import server
from fanta import testi_legali as tl
import codice_web


def cliente() -> TestClient:
    return TestClient(server.app, headers={"X-Fanta": "1"})


@pytest.mark.parametrize("percorso", ["/privacy", "/termini"])
def test_pagine_pubbliche_anche_con_gli_account(percorso, multiutente, dati_isolati):
    r = cliente().get(percorso)                                  # nessuna sessione: deve rispondere lo stesso
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "SchieraXI" in r.text and 'lang="it"' in r.text
    assert "<script>" not in r.text                              # la politica di sicurezza non ammette script in linea
    assert cliente().get("/legale.js").status_code == 200


def test_privacy_dice_le_cose_importanti():
    t = tl.pagina("privacy").lower()
    for parola in ("nome utente", "hash", "nessuna pubblicità", "nessun tracciamento", "elimina il mio account", "backup", "14 anni"):
        assert parola in t, parola


def test_privacy_dice_import_per_conto_di_e_copie_delle_rose():
    t = tl.pagina("privacy").lower()
    assert "importare le tue rose al posto tuo" in t and "5 copie" in t and "cancellano insieme al tuo account" in t


@pytest.mark.parametrize("lingua,scambi,vecchie,nuove", [
    ("it", r"scamb", ("Oggi", "Diario"), "(Formazione, Giornate, widget, risultati in diretta)"),
    ("en", r"\btrades?\b", ("Today", "Diary"), "(Lineup, Matchdays, widget, live scores)"),
])
def test_privacy_e_termini_parlano_dell_app_di_oggi(lingua, scambi, vecchie, nuove):
    """L'app non analizza più scambi e non ne salva sul dispositivo; le schermate sono Formazione e Giornate (Oggi e Diario
    non ci sono più): Privacy e Termini usano i nomi che l'utente vede."""
    for quale in ("privacy", "termini"):
        t = tl.pagina(quale, lingua)
        assert not re.search(scambi, t, re.I), (quale, re.search(scambi, t, re.I))
        for nome in vecchie:
            assert not re.search(rf"\b{nome}\b", t), (quale, nome)
    assert nuove in tl.pagina("privacy", lingua)


@pytest.mark.parametrize("lingua,voce,file,frasi", [
    ("it", "Se usi «Scrivici»: il testo del commento", "commenti mandati con «Scrivici»",
     ("la data, la versione e la piattaforma", "solo chi gestisce l'app", "finché non elimini l'account", "«Scarica i tuoi dati»",
      "Non va a terzi", "solo «un commento nuovo», senza testo né nome")),
    ("en", "If you use «Write to us»: the text of the comment", "comments sent with «Write to us»",
     ("the date and the version and platform", "Only whoever runs the app", "until you delete your account", "«Download your data»",
      "does not go to third parties", "only says «a new comment», without the text or your name")),
])
def test_privacy_dice_dei_commenti_di_scrivici(lingua, voce, file, frasi):
    """«Scrivici» (26/11/2026, fanta/feedback.py) salva un dato personale: la Privacy dice cosa si salva, chi lo legge, quanto resta
    (fino all'eliminazione dell'account, ed è nella copia dei dati) e che a terzi (l'avviso esterno, ntfy) arriva solo «un commento nuovo»."""
    t = tl.pagina("privacy", lingua)
    assert voce in t and file in t
    for frase in frasi:
        assert frase in t, frase


# Gestione › Utenti (GET /api/admin/utenti): ogni dato della riga di un account, con le parole che lo nominano nella Privacy
VISTO_NELL_ELENCO = {
    "it": {"nome_utente": "nome utente", "nome_visualizzato": "nome mostrato", "ruolo": "ruolo", "creato": "data di iscrizione",
           "ultimo_accesso": "ultimo accesso", "bloccato_il": "se l'ha bloccato, da quando"},
    "en": {"nome_utente": "username", "nome_visualizzato": "displayed name", "ruolo": "role", "creato": "sign-up date",
           "ultimo_accesso": "last sign-in", "bloccato_il": "if they blocked it, since when"},
}
# i campi della riga che non sono un dato in più: il numero interno e le frasi scritte con i campi qui sopra
CAMPI_DERIVATI = {"id", "bloccato", "dettaglio", "dettaglio_frase", "blocco", "blocco_frase"}
# il resto di Gestione: «Commenti degli utenti» e gli eventi di sicurezza di «Errori recenti»
ALTRO_IN_GESTIONE = {
    "it": ("i commenti mandati con «Scrivici», con il nome, la data, la versione e la piattaforma dell'app",
           "gli ultimi eventi del registro di sicurezza, con il nome utente e l'indirizzo di rete accorciato", "Mai le password"),
    "en": ("the comments sent with «Write to us», with the name, the date and the version and platform of the app",
           "the latest events of the security log, with the username and the shortened network address", "Never passwords"),
}


@pytest.mark.parametrize("lingua", tl.LINGUE)
def test_privacy_dice_tutto_quello_che_vede_chi_gestisce(lingua, multiutente, dati_isolati):
    """La Privacy diceva che nell'elenco degli account chi gestisce vede solo nome, ruolo e data di iscrizione: Gestione mostra
    anche l'ultimo accesso e il blocco (26/11/2026), e i commenti di «Scrivici» e gli eventi di sicurezza. Il paragrafo su chi
    gestisce nomina ogni dato della riga dell'elenco: un campo nuovo nella rotta fa fallire questo test finché la Privacy non lo dice."""
    import contextlib
    from fanta import account
    c = cliente()
    with contextlib.closing(account.apri()) as db:
        codice = account.crea_invito(db, "prova", True)
    assert c.post("/api/account/registra", json={"nome_utente": "capo", "password": "una-password-lunga-9", "invito": codice}).status_code == 200
    riga = c.get("/api/admin/utenti").json()["utenti"][0]
    assert set(riga) - CAMPI_DERIVATI == set(VISTO_NELL_ELENCO[lingua]), set(riga) - CAMPI_DERIVATI
    paragrafo = next(b[1] for b in tl.TESTI[lingua]["privacy"] if b[0] == "p" and ("Chi gestisce l'app, per amministrare" in b[1]
                                                                                   or "Whoever runs the app can technically see" in b[1]))
    for parole in (*VISTO_NELL_ELENCO[lingua].values(), *ALTRO_IN_GESTIONE[lingua]):
        assert parole in paragrafo, parole


AMBIENTE_LEGALE = ("FANTA_CONTATTO", "FANTA_TITOLARE", "FANTA_SORGENTE", "FANTA_BACKUP_GIORNI", "FANTA_REGISTRO_WEB_GIORNI",
                   "FANTA_HOSTING", "FANTA_POSTA_FORNITORE")
# nomi di siti e di file citati nel testo (ntfy.sh, Fantacalcio.it, football-data.co.uk, THIRD-PARTY-NOTICES.md): lì il punto
# fra due lettere è giusto
INDIRIZZI = re.compile(r"https?://\S+|\b[\w.-]+\.(?:it|sh|uk|org|com|net|io|md)\b")


@pytest.mark.parametrize("lingua", tl.LINGUE)
@pytest.mark.parametrize("quale", tl.PAGINE)
def test_niente_parole_attaccate_dopo_i_due_punti_o_il_punto(quale, lingua, monkeypatch):
    """Le frasi lunghe stanno su più righe che Python incolla: se una riga perde lo spazio in fondo, due parole si attaccano
    («li vedi solo tu:gli altri»). Sulla pagina generata, dopo «:» o «.» fra due lettere ci vuole uno spazio."""
    import html
    for v in AMBIENTE_LEGALE:
        monkeypatch.delenv(v, raising=False)
    corpo = tl.pagina(quale, lingua).split("<body", 1)[1]
    testo = INDIRIZZI.sub(" ", html.unescape(re.sub(r"<[^>]+>", " ", corpo)))
    attaccate = [testo[max(0, m.start() - 25):m.end() + 25] for m in re.finditer(r"[a-zà-ù][:.][A-Za-zÀ-ù]", testo)]
    assert not attaccate, attaccate


def test_termini_dicono_che_i_dati_non_sono_ufficiali():
    t = tl.pagina("termini").lower()
    assert "non sono dati ufficiali" in t and "14 anni" in t


def test_contatto_dalla_variabile_e_protetto(monkeypatch):
    monkeypatch.setenv("FANTA_CONTATTO", "aiuto@example.org <script>x</script>")
    t = tl.pagina("privacy")
    assert "aiuto@example.org" in t and "<script>x" not in t and "&lt;script&gt;" in t
    monkeypatch.delenv("FANTA_CONTATTO")
    assert "chi gestisce l'app" in tl.pagina("termini")


def test_senza_contatto_non_si_parla_di_chi_ha_dato_l_invito(monkeypatch):
    """Con la registrazione aperta nessuno ha dato un invito: senza FANTA_CONTATTO il recapito è solo «chi gestisce l'app»."""
    monkeypatch.delenv("FANTA_CONTATTO", raising=False)
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    assert tl.t("contatto_manca", "it") == "chi gestisce l'app" and tl.t("contatto_manca", "en") == "whoever runs the app"
    for lingua in ("it", "en"):
        for quale in ("privacy", "termini"):
            testo = tl.pagina(quale, lingua).lower()
            assert "ti ha dato il codice" not in testo and "gave you the invitation" not in testo, (quale, lingua)


def test_pagina_sconosciuta():
    with pytest.raises(ValueError):
        tl.pagina("altro")


def test_l_app_collega_le_pagine():
    # i link stanno in testi.js (linkLegale/linkLegali); accesso, Lega e Impostazioni li usano
    testi = codice_web.leggi("testi.js")
    assert 'href="/${pagina}${queryLingua()}"' in testi and 'linkLegale("privacy", "legale.privacy")' in testi and 'linkLegale("termini", "legale.termini")' in testi
    app = codice_web.app()
    imp = codice_web.leggi("impostazioni.js")   # dentro l'app: voci di Impostazioni > Informazioni, un posto solo
    assert app.count("linkLegali()") >= 2 and 'id="ac-letto"' in app        # accesso e registrazione
    assert all(f'voceLegale("{p}"' in imp for p in ("privacy", "termini", "crediti")) and "queryLingua()" in imp
    assert 'linkLegale("privacy"' in app                                  # la casella «Ho letto» usa i singoli link


def test_niente_frasi_false_su_ricavi_e_fonti():
    for quale in ("privacy", "termini", "crediti", "elimina"):
        t = tl.pagina(quale).lower()
        assert "senza scopo di lucro" not in t and "fonti pubbliche e gratuite" not in t, quale
        assert "non è richiesta oggi" not in t and "su un piccolo computer privato" not in t, quale


def test_privacy_ha_titolare_basi_destinatari_conservazione_diritti(monkeypatch):
    monkeypatch.setenv("FANTA_TITOLARE", "<TITOLARE>")
    monkeypatch.setenv("FANTA_BACKUP_GIORNI", "30")
    t = tl.pagina("privacy").lower()
    for parola in ("titolare del trattamento", "&lt;titolare&gt;", "interesse legittimo", "eseguire il servizio", "fuori dall'unione europea",
                   "portabilità", "opporti", "garante", "al massimo 30 giorni", "180 giorni"):
        assert parola in t, parola


def test_testo_segue_il_modo_di_iscrizione(monkeypatch):
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "invito")
    assert "facoltativa" in tl.pagina("privacy") and "codice d'invito." in tl.pagina("termini")
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")             # registrazione aperta: nome e password, email facoltativa
    p, tm = tl.pagina("privacy"), tl.pagina("termini")
    assert "facoltativa" in p and "bastano un nome utente e una password" in tm and "codice d'invito." not in tm
    monkeypatch.delenv("FANTA_REGISTRAZIONE")                        # senza la variabile: con l'invito, come prima
    assert "codice d'invito." in tl.pagina("termini") and "bastano un nome utente" not in tl.pagina("termini")
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "email")
    p, tm = tl.pagina("privacy"), tl.pagina("termini")
    assert "richiesto per iscriverti" in p and "un codice d'invito e un indirizzo email" in tm


def test_termini_hanno_la_clausola_sui_file_caricati():
    t = tl.pagina("termini").lower()
    assert "stemma" in t and "garantisci di averne il diritto" in t and "lo togliamo" in t


def test_crediti_con_e_senza_sorgente(monkeypatch):
    monkeypatch.delenv("FANTA_SORGENTE", raising=False)
    assert tl.sorgente() == "" and "<a href=\"https://" not in tl.pagina("crediti")
    monkeypatch.setenv("FANTA_SORGENTE", "https://example.org/schieraxi")
    c = tl.pagina("crediti")
    assert 'href="https://example.org/schieraxi"' in c and "MPL-2.0" in c and "Understat" in c
    for cattivo in ("http://example.org", "javascript:alert(1)", 'https://x.org/"><script>'):
        monkeypatch.setenv("FANTA_SORGENTE", cattivo)
        assert tl.sorgente() == "" and "<script>" not in tl.pagina("crediti")


@pytest.mark.parametrize("percorso", ["/crediti", "/elimina-account"])
def test_nuove_pagine_pubbliche(percorso, multiutente, dati_isolati):
    r = cliente().get(percorso)
    assert r.status_code == 200 and "SchieraXI" in r.text


def test_elimina_account_dice_come_fare():
    t = tl.pagina("elimina").lower()
    assert "elimina il mio account" in t and "impostazioni › il tuo account" in t and "copie di sicurezza" in t   # come nell'app (#827)


def test_stato_ha_il_campo_sorgente(dati_isolati, monkeypatch):
    monkeypatch.setenv("FANTA_SORGENTE", "https://example.org/schieraxi")
    r = cliente().get("/api/stato")
    assert r.status_code == 200 and r.json()["sorgente"] == "https://example.org/schieraxi"
    monkeypatch.delenv("FANTA_SORGENTE")
    assert cliente().get("/api/stato").json()["sorgente"] == ""


def test_privacy_dice_quello_che_l_app_fa_davvero(monkeypatch):
    """Le affermazioni legate al codice: se cambia il codice, cambia anche la pagina (e questo test)."""
    from fanta import account, rotte_account, social
    import inspect
    monkeypatch.setenv("FANTA_HOSTING", "Fornitore Esempio, in Italia")
    monkeypatch.setenv("FANTA_REGISTRO_WEB_GIORNI", "15")
    t = tl.pagina("privacy").lower()
    assert '"scope": "openid email"' in inspect.getsource(social)              # a Google chiediamo solo id ed email
    assert "«openid» ed «email»" in t and "non riceviamo né conserviamo il tuo nome" in t
    assert rotte_account.COOKIE and rotte_account.COOKIE_DISPOSITIVO and "due cookie tecnici" in t
    assert account.NOTO_PER == 60 * 24 * 3600 and "60 giorni" in t
    assert account.DURATA_TOKEN_WIDGET.days == 90 and "widget" in t and "90 giorni" in t
    for parola in ("altri partecipanti", "allenatore", "foto dello schermo", "solo il testo", "lingua", "ntfy.sh",
                   "controlli automatici", "github", "fornitore esempio, in italia", "indirizzo di rete completo", "al massimo 15 giorni",
                   "invito", "avvisi di sicurezza"):
        assert parola in t, parola
    assert "un solo cookie" not in t


def test_privacy_dice_chi_spedisce_le_email(monkeypatch):
    monkeypatch.delenv("FANTA_POSTA_FORNITORE", raising=False)
    assert "il servizio che spedisce le email (se sono attive)" in tl.pagina("privacy")
    assert "the service that sends emails (if active)" in tl.pagina("privacy", "en")
    monkeypatch.setenv("FANTA_POSTA_FORNITORE", "Fornitore <b>Posta</b>, in Germania")
    p = tl.pagina("privacy")
    assert "il servizio che spedisce le email (Fornitore &lt;b&gt;Posta&lt;/b&gt;, in Germania)" in p and "<b>" not in p
    assert "the service that sends emails (Fornitore &lt;b&gt;Posta&lt;/b&gt;, in Germania)" in tl.pagina("privacy", "en")


def test_termini_ed_elimina_parlano_degli_altri_e_di_cosa_resta():
    assert "altri partecipanti" in tl.pagina("termini").lower()
    e = tl.pagina("elimina").lower()
    assert "codice del widget" in e and "collegamento con google" in e and "server web" in e


def test_inglese_senza_frasi_italiane_di_ripiego(monkeypatch):
    for v in ("FANTA_CONTATTO", "FANTA_TITOLARE", "FANTA_BACKUP_GIORNI", "FANTA_HOSTING", "FANTA_REGISTRO_WEB_GIORNI"):
        monkeypatch.delenv(v, raising=False)
    p = tl.pagina("privacy", "en")
    assert "a limited time" in p and "un tempo limitato" not in p and "chi gestisce" not in p and "un fornitore" not in p
    monkeypatch.setenv("FANTA_BACKUP_GIORNI", "30")
    assert "at most 30 days" in tl.pagina("privacy", "en")
