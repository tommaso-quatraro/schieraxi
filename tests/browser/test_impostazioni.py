"""La barra a tre voci e le Impostazioni uniche (#618): Formazione, Giornate, Impostazioni più la ricerca; «Squadra» e «Altro» non
sono più schede e ciò che restava di loro sta in Impostazioni > La mia lega. Un utente normale vede al massimo una decina di
controlli; «Gestione» solo chi gestisce il server. Ogni indirizzo di prima apre la voce giusta, e i valori salvati nel browser da
una versione di prima non rompono niente.

Si guarda ciò che vede chi usa l'app (ruoli, nomi, cosa succede a un tocco), non il sorgente. I test che non dipendono dalla fase
della giornata girano solo prima della scadenza (`solo`).
"""
import json
import re

import pytest

PC = 1440
UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}
AMMINISTRATORE = {**UTENTE, "utente": {**UTENTE["utente"], "ruolo": "amministratore"}}
# Un controllo è ciò che si tocca o si scrive; i pulsanti di un gruppo (il tema, la lingua) contano una volta sola.
CONTROLLI = """() => {
  const visto = e => { const r = (e.matches('input[type=checkbox], input[type=radio]') && e.closest('label')) || e;
    return r.getClientRects().length > 0 && getComputedStyle(r).visibility !== 'hidden'; };
  const tutti = [...document.querySelectorAll('main a[href], main button, main input:not([type=hidden]), main select, main textarea, main summary')]
    .filter(visto);
  const gruppi = new Set(), nomi = [];
  for (const e of tutti) {
    const g = e.closest('[role=group], [role=radiogroup]');
    if (g) { if (gruppi.has(g)) continue; gruppi.add(g); nomi.push(g.getAttribute('aria-label') || 'gruppo'); continue; }
    nomi.push((e.getAttribute('aria-label') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.innerText || e.tagName).trim().split('\\n')[0]);
  }
  return nomi;
}"""


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def titolo(web) -> str:
    return principale(web).get_by_role("heading", level=1).inner_text().strip()


def tocca(web, bersaglio) -> None:
    (web.pagina.locator(bersaglio).first if isinstance(bersaglio, str) else bersaglio).click(timeout=10000)
    web.aspetta()


def barra(web):
    return web.pagina.get_by_role("navigation", name="Sezioni")


def voce(web, nome: str):
    """Una riga di Impostazioni che apre una pagina: un pulsante il cui nome comincia con `nome`."""
    return principale(web).get_by_role("button", name=re.compile(rf"^\s*{re.escape(nome)}"))


def sezione(web, nome: str):
    return principale(web).get_by_role("region", name=nome, exact=True)


def nel_primo_schermo(web, locator) -> bool:
    b = locator.bounding_box()
    return b is not None and 0 <= b["y"] < web.pagina.viewport_size["height"]


def da_utente(web, chi=UTENTE) -> None:
    web.risposta("/api/account/me", chi)


# ---------------------------------------------------------------- la barra
@pytest.mark.parametrize("larghezza", [390, PC])
def test_la_barra_ha_tre_voci_e_la_ricerca(web, larghezza):
    web.apri("/", larghezza=larghezza)
    schede = [" ".join(v.split()) for v in barra(web).get_by_role("link").all_inner_texts()]
    assert schede == ["Formazione", "Giornate", "Impostazioni"], schede
    cerca = web.pagina.get_by_role("button", name="Cerca un giocatore").or_(web.pagina.get_by_role("searchbox", name="Cerca un giocatore"))
    assert cerca.first.is_visible()
    # le impostazioni sono una voce della barra: niente ingranaggio in testata, niente pulsante «Impostazioni» a parte
    assert web.pagina.get_by_role("button", name="Impostazioni", exact=True).count() == 0
    assert not web.scorre_di_lato() and not web.errori_console


def test_impostazioni_si_apre_con_un_tocco_dalla_barra(web):
    solo(web, "prima")
    web.apri("/")
    tocca(web, barra(web).get_by_role("link", name="Impostazioni"))
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith("/?vista=impostazioni")
    assert barra(web).get_by_role("link", name="Impostazioni").get_attribute("aria-current") == "page"
    for nome in ("Avvisi", "La mia lega", "Aspetto"):
        assert sezione(web, nome).is_visible(), nome
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


# ---------------------------------------------------------------- quanti controlli, e chi vede Gestione
def test_un_utente_normale_vede_al_massimo_dieci_controlli(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni")
    controlli = web.pagina.evaluate(CONTROLLI)
    assert len(controlli) <= 10, controlli
    for nome in ("Aggiorna le rose", "La mia squadra", "Regole e scadenza", "Il tuo account", "Informazioni"):
        assert voce(web, nome).is_visible(), nome
    assert voce(web, "Gestione").count() == 0
    assert "Notifiche" not in web.testo_principale()                     # gli avvisi si chiamano «Avvisi», come nella spec
    assert not web.errori_mostrati() and not web.errori_console


def test_gestione_solo_per_chi_gestisce_il_server(web):
    solo(web, "prima")
    da_utente(web, AMMINISTRATORE)
    web.apri("/?vista=impostazioni")
    tocca(web, voce(web, "Gestione"))
    assert titolo(web) == "Gestione"
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=gestione")
    testo = web.testo_principale()
    assert "Stato dei dati" in testo and "Nuovo invito" in testo
    assert principale(web).get_by_role("button", name="Aggiorna i dati").is_visible()   # le frecce della testata stanno qui


@pytest.mark.parametrize("indirizzo", ["/?vista=impostazioni&gruppo=gestione", "/?vista=impostazioni&gruppo=avanzate"])
def test_chi_non_gestisce_il_server_non_apre_gestione_neanche_con_l_indirizzo(web, indirizzo):
    solo(web, "prima")
    da_utente(web)
    web.apri(indirizzo)
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith("/?vista=impostazioni")
    assert "Nuovo invito" not in web.testo_principale() and voce(web, "Gestione").count() == 0
    assert not web.errori_mostrati()


# ---------------------------------------------------------------- gli indirizzi di prima
@pytest.mark.parametrize("vecchio, nuovo, atteso", [
    ("/?vista=squadra", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=altro", "/?vista=impostazioni", None),
    ("/?vista=lega", "/?vista=impostazioni", None),
    ("/?vista=mercato", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=mercato&scheda=osservati", "/?vista=impostazioni", "La mia lega"),
    ("/?vista=scambi", "/?vista=impostazioni", None),
    ("/?vista=altro&voce=movimenti", "/?vista=impostazioni", None),
    ("/?vista=altro&voce=stagione", "/?vista=impostazioni", None),
    ("/?vista=impostazioni&gruppo=avvisi", "/?vista=impostazioni", "Avvisi"),
    ("/?vista=impostazioni&gruppo=aspetto", "/?vista=impostazioni", "Aspetto"),
    ("/?vista=impostazioni&gruppo=sconosciuto", "/?vista=impostazioni", None),
])
def test_un_indirizzo_di_prima_apre_impostazioni(web, vecchio, nuovo, atteso):
    solo(web, "prima")
    web.apri(vecchio)
    assert titolo(web) == "Impostazioni"
    assert web.pagina.url.endswith(nuovo), web.pagina.url
    if atteso:
        assert nel_primo_schermo(web, sezione(web, atteso).get_by_role("heading", name=atteso)), f"{vecchio}: «{atteso}» non si vede"
    assert barra(web).get_by_role("link", name="Impostazioni").get_attribute("aria-current") == "page"
    assert not web.errori_mostrati() and not web.errori_console


@pytest.mark.parametrize("vecchio, nuovo, atteso", [
    ("/?vista=squadra&voce=importa", "/?vista=impostazioni&gruppo=rose", "Aggiorna le rose"),
    ("/?vista=lega&voce=importa", "/?vista=impostazioni&gruppo=rose", "Aggiorna le rose"),
    ("/?vista=squadra&voce=squadre", "/?vista=impostazioni&gruppo=squadre", "Le altre squadre"),
    ("/?vista=altro&voce=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=lega&voce=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=regole", "/?vista=impostazioni&gruppo=regole", "Regole e scadenza"),
    ("/?vista=altro&voce=novita", "/?vista=impostazioni&gruppo=informazioni", "Informazioni"),
    ("/?vista=impostazioni&gruppo=informazioni", "/?vista=impostazioni&gruppo=informazioni", "Informazioni"),
    ("/?vista=impostazioni&gruppo=avanzate", "/?vista=impostazioni&gruppo=gestione", "Gestione"),     # sul server senza account si gestisce
])
def test_un_indirizzo_di_prima_apre_la_sua_pagina(web, vecchio, nuovo, atteso):
    solo(web, "prima")
    web.risposta("/api/novita", [])                                      # Informazioni le chiede: lo scenario registrato non le ha
    web.apri(vecchio)
    assert titolo(web) == atteso
    assert web.pagina.url.endswith(nuovo), web.pagina.url
    assert principale(web).get_by_role("button", name="Impostazioni").is_visible()        # si torna indietro
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


@pytest.mark.parametrize("vecchio", ["/?vista=squadra&rosa=", "/?vista=rosa", "/?vista=squadra&rosa=Squadra%20Demo"])
def test_l_indirizzo_della_mia_rosa_apre_la_mia_squadra(web, vecchio):
    solo(web, "prima")
    mia = web.registrata("/api/rosa")["nome"]
    web.apri(vecchio)
    assert titolo(web) == mia
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadra")
    assert "Portieri" in web.testo_principale()
    assert not web.errori_mostrati() and not web.errori_console


def test_l_indirizzo_della_rosa_di_un_altra_squadra_la_apre(web):
    solo(web, "prima")
    web.apri("/?vista=squadra&rosa=Real%20Esempio")
    assert titolo(web) == "Real Esempio"
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadre&rosa=Real+Esempio")
    tocca(web, principale(web).get_by_role("button", name="Le altre squadre"))
    assert titolo(web) == "Le altre squadre"
    assert not web.errori_mostrati() and not web.errori_console


def test_l_indirizzo_di_un_account_senza_account_apre_impostazioni(web):
    """Sul server senza account la voce «Il tuo account» non c'è: il suo indirizzo apre Impostazioni, senza errori."""
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=account")
    assert titolo(web) == "Impostazioni" and web.pagina.url.endswith("/?vista=impostazioni")
    assert voce(web, "Il tuo account").count() == 0 and not web.errori_mostrati()


def test_con_un_account_l_indirizzo_dell_account_apre_l_account(web):
    solo(web, "prima")
    da_utente(web)
    web.apri("/?vista=impostazioni&gruppo=account")
    assert titolo(web) == "Il tuo account"
    assert principale(web).get_by_role("button", name="Esci").is_visible()


# ---------------------------------------------------------------- valori salvati da versioni di prima
@pytest.mark.parametrize("salvata, atteso", [("squadra", "Formazione"), ("altro", "Formazione"), ("oggi", "Formazione"),
                                             ("mercato", "Formazione"), ("lega", "Formazione"), ("impostazioni", "Formazione"),
                                             ("__proto__", "Formazione"), ("giornate", "Giornate")])
def test_la_schermata_salvata_da_una_versione_di_prima_non_rompe_l_avvio(web, salvata, atteso):
    """L'app si riapre sull'ultima schermata (Formazione o Giornate). Una scheda che non c'è più (Squadra, Altro...) salvata da una
    versione di prima apre la Formazione: si riapre per schierare, non sulle impostazioni."""
    solo(web, "prima")
    web.memoria({"vista": salvata})
    web.apri("/")
    assert titolo(web) == atteso
    assert not web.errori_mostrati() and not web.errori_console


def test_indietro_torna_alle_impostazioni_e_poi_alla_formazione(web):
    solo(web, "prima")
    web.apri("/")
    tocca(web, barra(web).get_by_role("link", name="Impostazioni"))
    tocca(web, voce(web, "Regole e scadenza"))
    assert titolo(web) == "Regole e scadenza"
    web.pagina.go_back()
    web.aspetta()
    assert titolo(web) == "Impostazioni"
    web.pagina.go_back()
    web.aspetta()
    assert titolo(web) == "Formazione"


def test_il_pulsante_impostazioni_di_una_pagina_torna_all_elenco(web):
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=regole")                       # aperta da un indirizzo: niente voce di prima
    tocca(web, principale(web).get_by_role("button", name="Impostazioni"))
    assert titolo(web) == "Impostazioni" and web.pagina.url.endswith("/?vista=impostazioni")


# ---------------------------------------------------------------- La mia lega
def test_la_mia_lega_porta_alla_mia_squadra_e_alle_altre(web):
    solo(web, "prima")
    mia = web.registrata("/api/rosa")["nome"]
    web.apri("/?vista=impostazioni")
    riga = voce(web, "La mia squadra")
    assert mia in riga.inner_text()                                      # la riga dice qual è
    tocca(web, riga)
    assert titolo(web) == mia and web.pagina.url.endswith("/?vista=impostazioni&gruppo=squadra")
    testo = web.testo_principale()
    assert "Portieri" in testo and "Stemma" in testo and "Maglia" in testo
    assert principale(web).get_by_text("Non è la tua squadra?").is_visible()
    tocca(web, principale(web).get_by_role("button", name="Impostazioni"))
    tocca(web, voce(web, "Le altre squadre"))
    assert titolo(web) == "Le altre squadre"
    tocca(web, principale(web).get_by_role("button", name=re.compile(r"^\s*Real Esempio")))
    assert titolo(web) == "Real Esempio"
    assert not web.errori_mostrati() and not web.errori_console and not web.richieste_fallite


def test_senza_le_rose_degli_altri_non_c_e_le_altre_squadre(web):
    solo(web, "prima")
    f = web.registrata("/api/funzioni")
    f["funzioni"]["squadre_altrui"] = False
    web.risposta("/api/funzioni", f)
    web.apri("/?vista=impostazioni")
    assert voce(web, "La mia squadra").is_visible() and voce(web, "Le altre squadre").count() == 0


def test_nuova_stagione_compare_in_la_mia_lega_quando_serve(web):
    solo(web, "prima")
    web.risposta("/api/stagione", {"corrente": "2027-28", "rose": "2026-27", "nuova": True})
    web.apri("/?vista=impostazioni")
    avviso = sezione(web, "La mia lega").get_by_role("button", name=re.compile("Nuova stagione 2027-28"))
    avviso.wait_for(timeout=10000)
    tocca(web, avviso)
    assert web.pagina.get_by_role("dialog").get_by_role("button", name="Archivia e riparti").is_visible()


# ---------------------------------------------------------------- Regole e scadenza
RICONOSCIUTE = {"modifiche": [{"chiave": "crediti_iniziali", "etichetta": "Crediti iniziali", "valore": 500, "riga": "Crediti: 500"},
                              {"chiave": "bonus.assist", "etichetta": "Assist", "valore": 1.5, "riga": "Assist +1,5"}],
                "non_riconosciute": []}


def _scritture(web, rotta: str) -> list[dict]:
    """I corpi delle richieste che scrivono su `rotta` (PUT o POST), man mano che partono."""
    corpi = []
    web.pagina.on("request", lambda r: r.method in ("PUT", "POST") and r.url.split("?")[0].endswith(rotta)
                  and corpi.append(json.loads(r.post_data or "null")))
    return corpi


def test_il_regolamento_incollato_si_salva_con_un_tocco(web):
    solo(web, "prima")
    web.risposta("/api/regole/riconosci", RICONOSCIUTE)
    salvate = _scritture(web, "/api/regole")
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_role("textbox", name="Incolla qui il testo del regolamento").fill("Crediti: 500\nAssist +1,5")
    tocca(web, principale(web).get_by_role("button", name="Riconosci le regole"))
    assert "Crediti iniziali" in web.testo_principale()
    tocca(web, principale(web).get_by_role("button", name="Salva queste regole"))
    assert salvate, "le regole riconosciute non sono state salvate"
    assert salvate[-1]["crediti_iniziali"] == 500 and salvate[-1]["bonus"]["assist"] == 1.5
    assert not web.errori_mostrati()


def test_i_singoli_valori_stanno_dietro_modifica_i_valori(web):
    solo(web, "prima")
    web.apri("/?vista=impostazioni&gruppo=regole")
    punteggi = principale(web).get_by_text("Punteggi", exact=True)
    assert not punteggi.is_visible()
    tocca(web, principale(web).get_by_text("Modifica i valori", exact=True))
    assert punteggi.is_visible()


def test_la_scadenza_si_cambia_e_si_salva_subito(web):
    solo(web, "prima")
    salvate = _scritture(web, "/api/regole")
    web.apri("/?vista=impostazioni&gruppo=regole")
    principale(web).get_by_label("Quando si chiude la formazione?").select_option("30")
    web.aspetta()
    assert salvate and salvate[-1]["scadenza_minuti"] == 30


# ---------------------------------------------------------------- Avvisi
def test_avvisi_un_interruttore_e_le_ore_tranquille_senza_altri_controlli(web):
    solo(web, "prima")
    salvate = _scritture(web, "/api/avvisi")
    web.apri("/?vista=impostazioni")
    avvisi = sezione(web, "Avvisi")
    testo = avvisi.inner_text()
    for tolto in ("Promemoria 15 minuti prima", "Riepilogo a giornata finita", "Reparto della rosa scoperto", "Manda un avviso di prova",
                  "Cambi di formazione e probabili"):
        assert tolto not in testo, tolto
    ore = avvisi.get_by_role("checkbox", name=re.compile("^Ore tranquille"))
    assert "dalle 23 alle 7" in testo                                    # la fascia è già scelta
    ore.check()
    web.aspetta()
    assert salvate and salvate[-1] == {"silenzio": True}                 # solo ciò che si è cambiato: il resto resta com'è


# ---------------------------------------------------------------- Stato dei dati: le etichette del server
def test_stato_dei_dati_usa_le_etichette_del_server(web):
    solo(web, "prima")
    s = web.registrata("/api/stato-dati")
    s["aggiornamenti"] = [{"cosa": "voti", "quando": "2026-10-26T23:55:13", "errori": [], "etichetta": "Voti e bonus dal server"}]
    s["controlli"] = [{"nome": "somma_xg", "esito": "errore", "dettaglio": "Qualcosa non torna", "etichetta": "Gol attesi dal server"}]
    web.risposta("/api/stato-dati", s)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    tocca(web, principale(web).get_by_role("button", name="Apri lo stato dei dati"))
    foglio = web.pagina.get_by_role("dialog")
    foglio.get_by_text("Voti e bonus dal server").wait_for(timeout=10000)
    assert foglio.get_by_text("Gol attesi dal server").is_visible()


# ---------------------------------------------------------------- accesso: gli avvisi non sono errori
def test_nella_schermata_di_accesso_un_avviso_non_e_un_errore(web):
    """Sessione finita: la schermata di accesso lo dice con un avviso (`role="status"`), non con un errore (`role="alert"`)."""
    solo(web, "prima")
    da_utente(web)
    web.risposta("/api/stato", {"detail": "Serve l'accesso", "multiutente": True}, stato=401)
    web.pagina.goto(web.server.indirizzo + "/", wait_until="load")
    accesso = web.pagina.get_by_role("dialog", name=re.compile("Accesso|SchieraXI"))
    accesso.get_by_role("status").filter(has_text=re.compile(r"\w")).first.wait_for(timeout=10000)
    allarmi = [t for t in web.pagina.locator('[role="alert"]').all_inner_texts() if t.strip()]
    assert allarmi == [], allarmi
