"""Pagine Privacy e Termini: pubbliche (anche con gli account accesi), testi in un solo posto, contatto protetto."""
import pytest
from fastapi.testclient import TestClient

from fanta import server
from fanta import testi_legali as tl


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


def test_termini_dicono_che_i_dati_non_sono_ufficiali():
    t = tl.pagina("termini").lower()
    assert "non sono dati ufficiali" in t and "14 anni" in t


def test_contatto_dalla_variabile_e_protetto(monkeypatch):
    monkeypatch.setenv("FANTA_CONTATTO", "aiuto@example.org <script>x</script>")
    t = tl.pagina("privacy")
    assert "aiuto@example.org" in t and "<script>x" not in t and "&lt;script&gt;" in t
    monkeypatch.delenv("FANTA_CONTATTO")
    assert "chi gestisce l'app" in tl.pagina("termini")


def test_pagina_sconosciuta():
    with pytest.raises(ValueError):
        tl.pagina("altro")


def test_l_app_collega_le_pagine():
    # i link stanno in testi.js (linkLegale/linkLegali); accesso, Lega e Impostazioni li usano
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    assert 'href="/${pagina}${queryLingua()}"' in testi and 'linkLegale("privacy", "legale.privacy")' in testi and 'linkLegale("termini", "legale.termini")' in testi
    app = (server.WEB / "app.js").read_text(encoding="utf-8")
    imp = (server.WEB / "impostazioni.js").read_text(encoding="utf-8")   # dentro l'app: voci di Impostazioni > Informazioni, un posto solo
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
    monkeypatch.setenv("FANTA_REGISTRAZIONE", "aperta")
    p, tm = tl.pagina("privacy"), tl.pagina("termini")
    assert "richiesto per iscriverti" in p and "serve un indirizzo email" in tm


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
    assert "elimina il mio account" in t and "impostazioni &gt; il tuo account" in t and "copie di sicurezza" in t


def test_stato_ha_il_campo_sorgente(monkeypatch):
    monkeypatch.setenv("FANTA_SORGENTE", "https://example.org/schieraxi")
    r = cliente().get("/api/stato")
    assert r.status_code == 200 and r.json()["sorgente"] == "https://example.org/schieraxi"
    monkeypatch.delenv("FANTA_SORGENTE")
    assert cliente().get("/api/stato").json()["sorgente"] == ""
