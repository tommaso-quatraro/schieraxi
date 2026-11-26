"""«Scrivici» (26/11/2026): in Impostazioni chi ha l'account scrive un commento e lo manda a chi gestisce il server; in Gestione chi
gestisce legge «Commenti degli utenti» (il più recente in alto, chi, quando, da dove, il testo intero) e li segna come letti.

Si guarda ciò che vede chi usa l'app e cosa parte verso il server, non il sorgente. Valgono per una fase sola (`prima`): la
giornata non c'entra."""
import json
import re

import pytest

UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
AMMINISTRATORE = {**UTENTE, "utente": {**UTENTE["utente"], "ruolo": "amministratore"}}
TESTO = "La pagina delle giornate\nnon si apre dopo le 22.\nGrazie!"
COMMENTI = {"da_leggere": 1, "commenti": [
    {"id": 2, "testo": "Si può avere <b>la classifica</b>?\nAnche in grassetto", "quando": "2026-11-26T20:45:00+00:00",
     "utente": "Amico di prova", "piattaforma": "ios", "versione": "2.1", "schermata": None, "letto": False},
    {"id": 1, "testo": "Tutto bene, grazie", "quando": "2026-11-25T09:05:00+00:00", "utente": "Altro amico",
     "piattaforma": "web", "versione": "1.572", "schermata": None, "letto": True}]}


def solo_prima(web):
    if web.fase != "prima":
        pytest.skip("vale per la fase: prima")


def principale(web):
    return web.pagina.locator("main")


def voce(web, nome: str):
    return principale(web).get_by_role("button", name=re.compile(rf"^\s*{re.escape(nome)}"))


def tocca(web, bersaglio) -> None:
    bersaglio.click(timeout=10000)
    web.aspetta()


def invii(web, stato: int = 200, corpo=None) -> list[dict]:
    """Da qui POST /api/feedback risponde `stato` con `corpo`; restituisce i corpi mandati dalla pagina."""
    mandati = []

    def risponde(route):
        mandati.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=stato, content_type="application/json; charset=utf-8",
                      body=json.dumps(corpo if corpo is not None else {"ok": True, "id": 3}, ensure_ascii=False))

    web.pagina.route("**/api/feedback", risponde)
    return mandati


# ---------------------------------------------------------------- chi scrive
def test_scrivici_manda_il_commento_e_ringrazia(web):
    solo_prima(web)
    web.risposta("/api/account/me", UTENTE)
    mandati = invii(web)
    web.apri("/?vista=impostazioni")
    tocca(web, voce(web, "Scrivici"))
    assert principale(web).get_by_role("heading", level=1).inner_text().strip() == "Scrivici"
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=scrivici")
    campo = principale(web).get_by_role("textbox", name="Il tuo commento")
    invia = principale(web).get_by_role("button", name="Invia")
    assert invia.is_disabled()                                       # niente da mandare
    campo.fill("   ")
    assert invia.is_disabled()
    campo.fill(TESTO)
    assert invia.is_enabled()
    tocca(web, invia)
    assert len(mandati) == 1 and mandati[0]["testo"] == TESTO
    assert mandati[0].get("versione") == web.registrata("/api/stato")["versione"]
    assert principale(web).get_by_role("status").filter(has_text="Grazie, l'abbiamo ricevuto.").is_visible()
    assert campo.input_value() == "" and invia.is_disabled()
    assert not web.errori_console


def test_se_non_parte_lo_dice_e_il_testo_resta(web):
    solo_prima(web)
    web.risposta("/api/account/me", UTENTE)
    frase = "Hai raggiunto il limite di commenti di oggi (5). Si azzera tra 3 min."
    invii(web, 429, {"detail": frase, "riprova_tra": 180})
    web.apri("/?vista=impostazioni&gruppo=scrivici")
    campo = principale(web).get_by_role("textbox", name="Il tuo commento")
    campo.fill("Un'idea per la formazione")
    tocca(web, principale(web).get_by_role("button", name="Invia"))
    assert principale(web).get_by_role("alert").filter(has_text=frase).is_visible()
    assert campo.input_value() == "Un'idea per la formazione"
    assert "Grazie" not in web.testo_principale()


def test_senza_account_niente_scrivici(web):
    """Sul server senza account c'è solo chi lo gestisce, sul suo computer: non avrebbe a chi scrivere."""
    solo_prima(web)
    web.apri("/?vista=impostazioni")
    assert voce(web, "Informazioni").is_visible()
    assert voce(web, "Scrivici").count() == 0


# ---------------------------------------------------------------- chi gestisce
def test_gestione_mostra_i_commenti_e_li_segna_letti(web):
    solo_prima(web)
    web.risposta("/api/account/me", AMMINISTRATORE)
    web.risposta("/api/admin/feedback", COMMENTI)
    segnati = []

    def letto(route):
        segnati.append(route.request.url)
        route.fulfill(status=200, content_type="application/json", body='{"ok": true}')

    web.pagina.route(re.compile(r".*/api/admin/feedback/\d+/letto$"), letto)
    web.apri("/?vista=impostazioni&gruppo=gestione", larghezza=1440)
    carta = principale(web).locator("section, .carta").filter(has=web.pagina.get_by_role("heading", name="Commenti degli utenti"))
    assert carta.first.is_visible()
    testo = carta.first.inner_text()
    assert "1 da leggere" in testo
    # il più recente in alto, con chi, quando (ora italiana) e da dove
    assert testo.index("Si può avere") < testo.index("Tutto bene")
    assert "Amico di prova" in testo and "26 nov" in testo and "21:45" in testo and "dall'iPhone" in testo and "2.1" in testo
    # il testo dell'utente è testo: niente grassetto vero, i segni restano come li ha scritti, e va a capo dove è andato a capo lui
    assert carta.first.locator("b").count() == 0 and "<b>la classifica</b>" in testo
    assert "?\nAnche in grassetto" in testo
    segna = carta.first.get_by_role("button", name=re.compile("Segna come letto"))
    assert segna.count() == 1                                        # quello già letto non ha il pulsante
    tocca(web, segna)
    assert len(segnati) == 1 and segnati[0].endswith("/api/admin/feedback/2/letto")
    assert carta.first.get_by_role("button", name=re.compile("Segna come letto")).count() == 0
    # le altre schede di Gestione (utenti, inviti, errori) non sono nello scenario registrato: il loro 404 non c'entra
    altri = re.compile(r"\(/api/admin/(utenti|inviti|registro)\)$")
    assert not [e for e in web.errori_console if not altri.search(e)] and not web.scorre_di_lato()


def test_gestione_senza_commenti_lo_dice(web):
    solo_prima(web)
    web.risposta("/api/account/me", AMMINISTRATORE)
    web.risposta("/api/admin/feedback", {"da_leggere": 0, "commenti": []})
    web.apri("/?vista=impostazioni&gruppo=gestione")
    assert "Ancora nessun commento." in web.testo_principale()
