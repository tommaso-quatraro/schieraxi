"""Gestione › Utenti (26/11/2026): chi gestisce il server vede gli account con iscrizione, ultimo accesso e blocco (le frasi del
server) e, per gli altri, «Blocca» (o «Sblocca») ed «Elimina», ognuno dopo una conferma che dice il nome. Il proprio account non ha
pulsanti. Le risposte del server sono finte (nomi inventati); si guarda ciò che succede a un tocco, non il sorgente."""
import json
import re
from urllib.parse import urlsplit

import pytest

from test_impostazioni import AMMINISTRATORE, da_utente, principale, solo

GESTIONE = "/?vista=impostazioni&gruppo=gestione"


def utente(numero: int, nome: str, visto: str, ruolo: str = "utente", bloccato: bool = False) -> dict:
    return {"id": numero, "nome_utente": nome, "nome_visualizzato": visto, "ruolo": ruolo, "creato": "2026-10-01T10:00:00+00:00",
            "ultimo_accesso": "2026-11-24T18:00:00+00:00", "bloccato": bloccato, "bloccato_il": "2026-11-25T09:00:00+00:00" if bloccato else None,
            "dettaglio": "Iscrizione gio 1 ott, ultimo accesso mar 24 nov.", "dettaglio_frase": None,
            "blocco": "Bloccato mer 25 nov: non può entrare." if bloccato else None, "blocco_frase": None}


IO = utente(7, "amico", "Amico di prova", "amministratore")          # lo stesso numero di AMMINISTRATORE (/api/account/me)
LUCA = utente(8, "luca", "Luca")
SARA = utente(9, "sara", "Sara", bloccato=True)
REGISTRO = {"contatori": {"richieste": 10, "rifiutate": 0, "errori": 0, "senza_accesso": 0, "tempo_medio_ms": 12, "tempo_max_ms": 40,
                          "piu_lente": []}, "errori": [], "sicurezza": []}


class Server:
    """Le rotte di Gestione con gli account: l'elenco che si può cambiare fra una lettura e l'altra e le azioni arrivate
    («POST /api/admin/utenti/8/blocca»)."""

    def __init__(self, web, utenti: list[dict]):
        self.utenti, self.azioni = list(utenti), []
        web.risposta("/api/admin/inviti", {"inviti": []})
        web.risposta("/api/admin/registro", REGISTRO)
        web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/admin/utenti"), self._rispondi)

    def _rispondi(self, route):
        richiesta, percorso = route.request, urlsplit(route.request.url).path
        if richiesta.method == "GET" and percorso == "/api/admin/utenti":
            corpo = {"utenti": self.utenti, "massimo": 30, "avviso": None, "avviso_frase": None}
        else:
            self.azioni.append(f"{richiesta.method} {percorso}")
            corpo = {"ok": True, "sessioni_chiuse": 1} if percorso.endswith("/blocca") else {"ok": True}
        route.fulfill(status=200, content_type="application/json; charset=utf-8", body=json.dumps(corpo, ensure_ascii=False))


def elenco(web):
    return principale(web).get_by_role("list", name="Utenti", exact=True)


def riga(web, nome: str):
    return elenco(web).get_by_role("listitem").filter(has_text=nome)


def conferma(web, accetta: bool) -> list[str]:
    """Da qui le domande del browser (confirm) si accettano o si rifiutano; torna l'elenco dei loro testi."""
    domande = []

    def rispondi(dialogo):
        domande.append(dialogo.message)
        dialogo.accept() if accetta else dialogo.dismiss()

    web.pagina.on("dialog", rispondi)
    return domande


def apri_gestione(web, utenti: list[dict], larghezza: int = 390) -> Server:
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    server = Server(web, utenti)
    web.apri(GESTIONE, larghezza=larghezza)
    elenco(web).wait_for(timeout=10000)
    return server


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_l_elenco_dice_chi_c_e_e_chi_e_bloccato(web, larghezza):
    apri_gestione(web, [IO, LUCA, SARA], larghezza)
    assert elenco(web).get_by_role("listitem").count() == 3
    assert "Iscrizione gio 1 ott, ultimo accesso mar 24 nov." in riga(web, "Luca").inner_text()
    assert "Bloccato mer 25 nov: non può entrare." in riga(web, "Sara").inner_text()
    assert "Bloccato" not in riga(web, "Luca").inner_text()
    mia = riga(web, "Amico di prova")
    assert "Sei tu" in mia.inner_text() and mia.get_by_role("button").count() == 0      # il proprio account: niente pulsanti
    assert riga(web, "Luca").get_by_role("button", name="Blocca Luca").is_visible()
    assert riga(web, "Luca").get_by_role("button", name="Elimina Luca").is_visible()
    assert riga(web, "Sara").get_by_role("button", name="Sblocca Sara").is_visible()
    assert "3 utenti su 30 al massimo" in principale(web).inner_text()
    assert not web.scorre_di_lato() and not web.errori_console and not web.errori_mostrati()
    assert web.violazioni_gravi() == []


def test_blocca_chiede_conferma_e_rilegge_l_elenco(web):
    server = apri_gestione(web, [IO, LUCA])
    domande = conferma(web, True)
    server.utenti = [IO, utente(8, "luca", "Luca", bloccato=True)]          # il server, dopo il blocco
    riga(web, "Luca").get_by_role("button", name="Blocca Luca").click(timeout=10000)
    riga(web, "Luca").get_by_role("button", name="Sblocca Luca").wait_for(timeout=10000)
    web.aspetta()
    assert server.azioni == ["POST /api/admin/utenti/8/blocca"]
    assert len(domande) == 1 and "«Luca»" in domande[0] and "non potrà più entrare" in domande[0], domande
    assert "Bloccato mer 25 nov: non può entrare." in riga(web, "Luca").inner_text()
    assert not web.errori_console


def test_senza_conferma_non_succede_niente(web):
    server = apri_gestione(web, [IO, LUCA, SARA])
    domande = conferma(web, False)
    riga(web, "Luca").get_by_role("button", name="Blocca Luca").click(timeout=10000)
    riga(web, "Luca").get_by_role("button", name="Elimina Luca").click(timeout=10000)
    riga(web, "Sara").get_by_role("button", name="Sblocca Sara").click(timeout=10000)
    web.aspetta()
    assert len(domande) == 3 and server.azioni == []
    assert elenco(web).get_by_role("listitem").count() == 3


def test_elimina_chiede_conferma_e_toglie_la_riga(web):
    server = apri_gestione(web, [IO, LUCA])
    domande = conferma(web, True)
    server.utenti = [IO]
    riga(web, "Luca").get_by_role("button", name="Elimina Luca").click(timeout=10000)
    web.pagina.wait_for_function("() => !document.querySelector('main').innerText.includes('Luca')", timeout=10000)
    web.aspetta()
    assert server.azioni == ["DELETE /api/admin/utenti/8"]
    assert len(domande) == 1 and "«Luca»" in domande[0] and re.search("non si può annullare", domande[0], re.I), domande
    assert elenco(web).get_by_role("listitem").count() == 1


COMMENTO_LUCA = {"id": 3, "utente": "Luca", "quando": "2026-11-25T18:00:00+00:00", "piattaforma": "web", "versione": "1.590",
                 "testo": "Il commento di prova di Luca", "letto": None}
COMMENTO_SARA = {**COMMENTO_LUCA, "id": 4, "utente": "Sara", "testo": "Il commento di prova di Sara"}


class Rileggibili:
    """«Commenti degli utenti» ed «Errori recenti» come li dà il server in quel momento: il test cambia `commenti` ed `eventi` (gli
    eventi di sicurezza) dopo un'azione e conta le letture."""

    def __init__(self, web, commenti: list[dict]):
        self.commenti, self.eventi, self.letture = list(commenti), [], {"feedback": 0, "registro": 0}
        web.pagina.route(lambda u: urlsplit(u).path == "/api/admin/feedback", self._feedback)
        web.pagina.route(lambda u: urlsplit(u).path == "/api/admin/registro", self._registro)

    def _manda(self, route, corpo):
        route.fulfill(status=200, content_type="application/json; charset=utf-8", body=json.dumps(corpo, ensure_ascii=False))

    def _feedback(self, route):
        self.letture["feedback"] += 1
        self._manda(route, {"commenti": self.commenti, "da_leggere": sum(1 for c in self.commenti if not c["letto"])})

    def _registro(self, route):
        self.letture["registro"] += 1
        self._manda(route, {**REGISTRO, "sicurezza": self.eventi})


@pytest.mark.parametrize("azione, nome, dopo, tipo, evento", [
    ("Elimina", "Luca", [IO, SARA], "account_eliminato", "Account eliminato"),
    ("Blocca", "Luca", [IO, utente(8, "luca", "Luca", bloccato=True), SARA], "account_bloccato", "Account bloccato"),
    ("Sblocca", "Sara", [IO, LUCA, utente(9, "sara", "Sara")], "account_sbloccato", "Account sbloccato"),
])
def test_dopo_un_azione_commenti_ed_eventi_si_rileggono(web, azione, nome, dopo, tipo, evento):
    """Collaudo d'insieme del 26/11: dopo «Elimina» il commento dell'account eliminato restava in «Commenti degli utenti» e gli
    eventi di sicurezza erano quelli di prima. Dopo blocca, sblocca ed elimina la pagina rilegge utenti, commenti e registro."""
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    server = Server(web, [IO, LUCA, SARA])
    letti = Rileggibili(web, [COMMENTO_LUCA, COMMENTO_SARA])
    web.apri(GESTIONE, larghezza=1440)
    elenco(web).wait_for(timeout=10000)
    commenti = principale(web).locator("#scheda-commenti")
    commenti.get_by_text("Il commento di prova di Luca").wait_for(timeout=10000)
    conferma(web, True)
    server.utenti = dopo
    letti.eventi = [{"quando": "2026-11-26T18:41:00+00:00", "tipo": tipo, "nome": nome.lower(), "ip": ""}]
    if azione == "Elimina":
        letti.commenti = [COMMENTO_SARA]                    # il server toglie i commenti con l'account
    riga(web, nome).get_by_role("button", name=f"{azione} {nome}").click(timeout=10000)
    registro = principale(web).locator("#adm-registro")
    try:
        registro.get_by_text(evento).wait_for(timeout=10000)
    except Exception:                        # noqa: BLE001 - si dice cosa manca
        pytest.fail(f"dopo «{azione}» gli eventi di sicurezza non si sono riletti: {registro.inner_text()[:300]!r}")
    web.aspetta()
    assert letti.letture["feedback"] >= 2 and letti.letture["registro"] >= 2, letti.letture
    if azione == "Elimina":
        assert commenti.get_by_text("Il commento di prova di Luca").count() == 0, commenti.inner_text()[:300]
    assert commenti.get_by_text("Il commento di prova di Sara").is_visible()
    assert not web.errori_console, web.errori_console


def test_sblocca_chiede_conferma(web):
    server = apri_gestione(web, [IO, SARA])
    domande = conferma(web, True)
    server.utenti = [IO, utente(9, "sara", "Sara")]
    riga(web, "Sara").get_by_role("button", name="Sblocca Sara").click(timeout=10000)
    riga(web, "Sara").get_by_role("button", name="Blocca Sara").wait_for(timeout=10000)
    assert server.azioni == ["POST /api/admin/utenti/9/sblocca"]
    assert len(domande) == 1 and "«Sara»" in domande[0], domande


def test_gli_altri_amministratori_non_hanno_pulsanti(web):
    """Revisione della #933: un altro amministratore si gestisce solo sul server, dalla riga di comando: sulla sua riga niente
    «Blocca» né «Elimina», anche se è bloccato (niente «Sblocca»)."""
    vice, vice_bloccato = utente(10, "vice", "Vice", "amministratore"), utente(11, "terzo", "Terzo", "amministratore", bloccato=True)
    apri_gestione(web, [IO, vice, vice_bloccato, LUCA])
    for nome in ("Vice", "Terzo"):
        assert riga(web, nome).get_by_role("button").count() == 0, nome
    assert "Bloccato mer 25 nov: non può entrare." in riga(web, "Terzo").inner_text()
    assert riga(web, "Luca").get_by_role("button").count() == 2


def test_un_nome_con_html_si_legge_come_testo(web):
    """Il nome viene dall'utente: nell'elenco, nel nome del pulsante e nella conferma si legge com'è scritto, mai come HTML."""
    strano = utente(12, "strano", '<img src=x onerror="window.violato=1"><b>Strano</b>')
    server = apri_gestione(web, [IO, strano])
    domande = conferma(web, False)
    testo = riga(web, "Strano").inner_text()
    assert '<img src=x onerror="window.violato=1"><b>Strano</b>' in testo
    assert elenco(web).locator("img, b").count() == 0
    pulsante = elenco(web).get_by_role("button", name=re.compile("^Blocca <img"))
    assert pulsante.count() == 1
    pulsante.click(timeout=10000)
    web.aspetta()
    assert len(domande) == 1 and '«<img src=x onerror="window.violato=1"><b>Strano</b>»' in domande[0], domande
    assert server.azioni == [] and not web.pagina.evaluate("() => window.violato === 1")
    assert not web.errori_console
