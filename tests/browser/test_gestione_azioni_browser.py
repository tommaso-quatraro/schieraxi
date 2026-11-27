"""Gestione, le azioni di chi gestisce il server (revisione del 27/11): l'invito da amministratore chiede conferma e la spunta si
toglie dopo ogni invito; «Crea l'invito», «Genera il codice» e «Aggiorna i dati» restano spenti finché non arriva la risposta (un
doppio tocco non fa due richieste); dopo un invito creato o annullato e dopo un codice «Errori recenti» si rilegge; il registro non
si legge da solo a ogni caricamento; un registro che il server non legge è un errore che lo dice.
Le risposte del server sono finte (nomi inventati); si guarda ciò che succede a un tocco, non il sorgente."""
import json
from urllib.parse import urlsplit

from test_gestione_utenti_browser import GESTIONE, IO, LUCA, Rileggibili, Server, apri_gestione, conferma
from test_impostazioni import AMMINISTRATORE, da_utente, principale, solo, stato_aggiornamento

CODICE = "ABCDE-FGHJK-LMNPQ-RSTUV"
APERTO = {"id": 5, "etichetta": "Marco", "ruolo": "utente", "creato": "2026-11-25T10:00:00+00:00", "scade": "2026-12-02T10:00:00+00:00",
          "usi": 0, "usi_max": 1, "stato": "attivo", "dettaglio": "Creato mer 25 nov, scade mer 2 dic.", "dettaglio_frase": None}


def manda(route, corpo, stato: int = 200) -> None:
    route.fulfill(status=stato, content_type="application/json; charset=utf-8", body=json.dumps(corpo, ensure_ascii=False))


class Azioni:
    """Inviti e codici: le richieste che cambiano qualcosa arrivano qui (`corpi`). Con `trattieni` restano senza risposta in `ferme`
    finché il test non le sblocca (`sblocca`)."""

    def __init__(self, web, aperti: list[dict] | None = None, trattieni: bool = False):
        self.aperti, self.trattieni, self.corpi, self.ferme = list(aperti or []), trattieni, [], []
        web.pagina.route(lambda u: urlsplit(u).path.startswith("/api/admin/inviti"), self._inviti)
        web.pagina.route(lambda u: urlsplit(u).path == "/api/admin/reset-password", self._reset)

    def _risposta(self, route):
        percorso = urlsplit(route.request.url).path
        if percorso == "/api/admin/reset-password":
            return {"codice": CODICE, "valido_ore": 24}
        if route.request.method == "DELETE":
            return {"ok": True}
        corpo = route.request.post_data_json
        return {"codice": CODICE, "etichetta": corpo["etichetta"], "valido_giorni": 7, "usi_max": corpo["usi"], "id": 6,
                "avviso": None, "avviso_frase": None}

    def _arriva(self, route):
        self.corpi.append((route.request.method, urlsplit(route.request.url).path, route.request.post_data_json))
        if self.trattieni:
            self.ferme.append(route)
        else:
            manda(route, self._risposta(route))

    def _inviti(self, route):
        if route.request.method == "GET":
            manda(route, {"inviti": self.aperti, "max_usi": 30})
        else:
            self._arriva(route)

    def _reset(self, route):
        self._arriva(route)

    def sblocca(self):
        while self.ferme:
            route = self.ferme.pop(0)
            manda(route, self._risposta(route))


def gestione(web, aperti=None, trattieni=False):
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    Server(web, [IO, LUCA])
    letti = Rileggibili(web, [])
    azioni = Azioni(web, aperti, trattieni)                # registrate dopo: rispondono loro
    web.apri(GESTIONE, larghezza=1440)
    principale(web).get_by_role("button", name="Crea l'invito").wait_for(timeout=10000)
    return azioni, letti


def spunta(web):
    return principale(web).get_by_label("Il nuovo account sarà amministratore")


def crea_invito(web, etichetta: str) -> None:
    principale(web).get_by_label("Etichetta").fill(etichetta)
    principale(web).get_by_role("button", name="Crea l'invito").click(timeout=10000)
    web.aspetta()


def doppio_tocco(web, pulsante, arrivate) -> None:
    """Due tocchi di fila sullo stesso pulsante, prima che la pagina possa ridisegnare qualcosa; poi si lascia alle richieste partite
    il tempo di arrivare alle rotte del test (`arrivate()` dice quante sono), qualche giro anche dopo la prima."""
    pulsante.evaluate("b => { b.click(); b.click(); }")
    for _ in range(40):
        if arrivate():
            break
        web.pagina.evaluate("() => new Promise(fatto => setTimeout(fatto, 25))")
    for _ in range(8):
        web.pagina.evaluate("() => new Promise(fatto => setTimeout(fatto, 25))")


# ---------------------------------------------------------------- invito da amministratore
def test_l_invito_da_amministratore_chiede_conferma_e_la_spunta_si_toglie(web):
    """La spunta «amministratore» restava accesa dopo «Crea l'invito»: anche l'invito dopo dava i poteri di chi gestisce il server.
    Ora con la spunta accesa la pagina chiede conferma (con una frase che dice cosa potrà fare), e dopo l'invito la spunta è spenta."""
    azioni, _ = gestione(web)
    domande = conferma(web, True)
    spunta(web).check()
    crea_invito(web, "Marco")
    principale(web).get_by_text(CODICE).first.wait_for(timeout=10000)
    assert [c for _, _, c in azioni.corpi] == [{"etichetta": "Marco", "amministratore": True, "usi": 1}]
    assert len(domande) == 1 and "amministratore" in domande[0] and "Confermi?" in domande[0], domande
    assert not spunta(web).is_checked()
    crea_invito(web, "Sara")
    assert [c["amministratore"] for _, _, c in azioni.corpi] == [True, False]
    assert len(domande) == 1, domande                          # senza la spunta nessuna domanda
    assert not web.errori_console, web.errori_console


def test_con_la_spunta_amministratore_le_persone_restano_una(web):
    """Collaudo del 27/11 sera: con la spunta e «Quante persone» a 3 la pagina chiedeva conferma e poi il server rispondeva «Un invito
    da amministratore si può usare una volta sola». Ora con la spunta il numero torna a 1 e non si cambia (campo e pulsanti spenti),
    e la frase sotto dice perché; senza la spunta torna libero."""
    azioni, _ = gestione(web)
    conferma(web, True)
    posti = principale(web).get_by_label("Quante persone")
    riga = principale(web).locator(".riga-regola", has=web.pagina.get_by_label("Quante persone"))
    piu = riga.get_by_role("button", name="Aumenta")
    posti.fill("3")
    spunta(web).check()
    assert posti.input_value() == "1" and posti.is_disabled()
    assert piu.is_disabled() and riga.get_by_role("button", name="Diminuisci").is_disabled()
    assert "Un invito da amministratore vale per una persona sola." in riga.inner_text()
    spunta(web).uncheck()
    assert posti.is_enabled() and piu.is_enabled()
    assert "Un invito da amministratore" not in riga.inner_text()
    piu.click()
    assert posti.input_value() == "2"
    spunta(web).check()
    crea_invito(web, "Vice")
    principale(web).get_by_text(CODICE).first.wait_for(timeout=10000)
    assert [c for _, _, c in azioni.corpi] == [{"etichetta": "Vice", "amministratore": True, "usi": 1}]
    assert not spunta(web).is_checked() and posti.is_enabled() and piu.is_enabled()    # dopo l'invito la spunta è tolta: di nuovo libero
    assert not web.errori_console, web.errori_console


def test_un_invito_da_amministratore_si_riconosce_negli_inviti_aperti(web):
    """Collaudo del 27/11 sera: negli inviti aperti un invito da amministratore era uguale a quello di un amico, anche se il server
    manda il ruolo. Ora la riga lo dice con le parole di «Utenti»: «Vice (amministratore)»."""
    da_amministratore = APERTO | {"id": 7, "etichetta": "Vice", "ruolo": "amministratore"}
    gestione(web, aperti=[da_amministratore, APERTO])
    elenco = principale(web).get_by_role("list", name="Inviti aperti")
    elenco.wait_for(timeout=10000)
    righe = [" ".join(r.split()) for r in elenco.get_by_role("listitem").all_inner_texts()]
    assert len(righe) == 2, righe
    assert righe[0].startswith("Vice (amministratore)"), righe
    assert "amministratore" not in righe[1], righe


def test_senza_conferma_l_invito_da_amministratore_non_parte(web):
    azioni, _ = gestione(web)
    domande = conferma(web, False)
    spunta(web).check()
    crea_invito(web, "Marco")
    assert len(domande) == 1 and azioni.corpi == []
    assert principale(web).get_by_text(CODICE).count() == 0


# ---------------------------------------------------------------- un doppio tocco, una richiesta
def test_un_doppio_tocco_su_crea_l_invito_crea_un_invito_solo(web):
    azioni, _ = gestione(web, trattieni=True)
    principale(web).get_by_label("Etichetta").fill("Marco")
    pulsante = principale(web).get_by_role("button", name="Crea l'invito")
    doppio_tocco(web, pulsante, lambda: len(azioni.corpi))
    assert len(azioni.corpi) == 1, azioni.corpi
    assert pulsante.is_disabled()                              # spento finché non arriva la risposta
    azioni.sblocca()
    principale(web).get_by_text(CODICE).first.wait_for(timeout=10000)
    web.aspetta()
    assert pulsante.is_enabled() and len(azioni.corpi) == 1


def test_un_doppio_tocco_su_genera_il_codice_fa_una_richiesta_sola(web):
    azioni, _ = gestione(web, trattieni=True)
    principale(web).get_by_label("Nome utente").fill("luca")
    pulsante = principale(web).get_by_role("button", name="Genera il codice")
    doppio_tocco(web, pulsante, lambda: len(azioni.corpi))
    assert len(azioni.corpi) == 1, azioni.corpi
    assert pulsante.is_disabled()
    azioni.sblocca()
    principale(web).get_by_text(CODICE).first.wait_for(timeout=10000)
    web.aspetta()
    assert pulsante.is_enabled() and len(azioni.corpi) == 1


def test_un_codice_rifiutato_riaccende_il_pulsante(web):
    """Il server rifiuta il codice (l'account di un altro amministratore): la sua frase in un avviso e il pulsante di nuovo acceso."""
    gestione(web)
    frase = "Per un altro amministratore il codice non si crea dalla web: la password si cambia con il suo codice di recupero."
    web.pagina.route(lambda u: urlsplit(u).path == "/api/admin/reset-password", lambda r: manda(r, {"detail": frase}, 403))
    principale(web).get_by_label("Nome utente").fill("vice")
    pulsante = principale(web).get_by_role("button", name="Genera il codice")
    pulsante.click(timeout=10000)
    web.pagina.get_by_role("status").filter(has_text=frase).first.wait_for(timeout=10000)
    assert pulsante.is_enabled()


def test_un_doppio_tocco_su_aggiorna_i_dati_fa_una_richiesta_sola(web):
    solo(web, "prima")
    stato_aggiornamento(web, False)
    gestione(web)
    ferme = []
    web.pagina.route(lambda u: urlsplit(u).path == "/api/aggiorna", lambda r: ferme.append(r))
    pulsante = principale(web).get_by_role("button", name="Aggiorna i dati")
    doppio_tocco(web, pulsante, lambda: len(ferme))
    assert len(ferme) == 1, [r.request.method for r in ferme]
    assert pulsante.is_disabled()
    manda(ferme.pop(), {"avviato": False, "messaggio": "Aggiornamento già in corso"})
    web.pagina.get_by_role("status").filter(has_text="Aggiornamento già in corso").first.wait_for(timeout=10000)
    assert pulsante.is_enabled() and not ferme


# ---------------------------------------------------------------- «Errori recenti» si rilegge
def test_dopo_un_invito_un_annullamento_e_un_codice_il_registro_si_rilegge(web):
    """Dopo blocca, sblocca ed elimina «Errori recenti» si rileggeva, dopo un invito creato o annullato e dopo un codice no:
    l'evento appena scritto dal server non compariva."""
    _, letti = gestione(web, aperti=[APERTO])
    conferma(web, True)
    prima = letti.letture["registro"]
    crea_invito(web, "Sara")
    assert letti.letture["registro"] == prima + 1, letti.letture
    principale(web).get_by_role("button", name="Annulla l'invito per Marco").click(timeout=10000)
    web.aspetta()
    assert letti.letture["registro"] == prima + 2, letti.letture
    principale(web).get_by_label("Nome utente").fill("luca")
    principale(web).get_by_role("button", name="Genera il codice").click(timeout=10000)
    principale(web).get_by_text(CODICE).first.wait_for(timeout=10000)
    web.aspetta()
    assert letti.letture["registro"] == prima + 3, letti.letture


# ---------------------------------------------------------------- il registro, per chi usa un lettore di schermo
def test_il_registro_non_si_legge_da_solo_a_ogni_caricamento(web):
    """Il registro (fino a 60 eventi) stava in una regione che il lettore di schermo legge da sola a ogni caricamento. Ora no:
    gli esiti delle azioni li dice l'avviso (`role="status"`)."""
    _, letti = gestione(web)
    letti.eventi = [{"quando": "2026-11-26T18:41:00+00:00", "tipo": "account_bloccato", "nome": "luca", "ip": ""}]
    principale(web).get_by_role("button", name="Aggiorna", exact=True).click(timeout=10000)
    scheda = principale(web).locator("#scheda-errori")
    scheda.get_by_text("Account bloccato").wait_for(timeout=10000)
    da_soli = scheda.evaluate("s => [...s.querySelectorAll('[aria-live], [role=status], [role=log], [role=alert]')].map(e => e.outerHTML.slice(0, 80))")
    assert da_soli == [], da_soli
    assert web.pagina.get_by_role("status").count() >= 1           # l'avviso delle azioni c'è


def test_un_registro_che_il_server_non_legge_e_un_errore(web):
    """Il server non legge un file del registro (503 con la sua frase): «Errori recenti» lo dice come errore, non «Nessun evento»."""
    frase = "Non riesco a leggere il registro del server (sicurezza.log): controlla i permessi del file sul server."
    apri_gestione(web, [IO, LUCA], larghezza=1440)
    web.risposta("/api/admin/registro", {"detail": frase}, 503)
    principale(web).get_by_role("button", name="Aggiorna", exact=True).click(timeout=10000)
    errore = principale(web).locator("#scheda-errori").get_by_role("alert")
    errore.wait_for(timeout=10000)
    assert errore.inner_text().strip() == frase
    assert "Nessun evento" not in principale(web).locator("#scheda-errori").inner_text()
