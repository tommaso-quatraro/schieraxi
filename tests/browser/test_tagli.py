"""La web senza le funzioni tolte il 12/11/2026 (#615): niente voci morte nei menu, gli indirizzi di prima aprono la schermata
più vicina che resta, e le schermate che restano non mostrano più stili, legenda, confronto, diretta e banner.

Si guarda ciò che vede chi usa l'app (testi, pulsanti, cosa succede a un tocco), non il sorgente. Dove un ruolo o un'etichetta
non bastano (le pedine del campo, i volti) si usa la classe di oggi: quei test si riscrivono con la schermata.
I test che non dipendono dalla fase della giornata girano solo prima della scadenza (`solo`).
"""
import re
from urllib.parse import urlsplit

import pytest

ROTTE_TOLTE = ("/api/live", "/api/mercato", "/api/osservati", "/api/scambi", "/api/confronto", "/api/classifica", "/api/movimenti")
NOVITA = [{"versione": "9.2", "data": "2026-11-12T10:00:00", "titolo": "Una novità di prova", "voci": ["Una cosa cambiata"]},
          {"versione": "9.1", "data": "2026-11-11", "titolo": "La novità di ieri", "voci": ["Un'altra cosa"]}]
PC = 1440


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def titolo(web) -> str:
    return principale(web).get_by_role("heading", level=1).inner_text().strip()


def tocca(web, bersaglio) -> None:
    """Un tocco su un elemento (selettore CSS o locator di Playwright), poi si aspetta che la pagina sia ferma."""
    (web.pagina.locator(bersaglio).first if isinstance(bersaglio, str) else bersaglio).click(timeout=10000)
    web.aspetta()


def voci_del_menu(web) -> list[str]:
    """Il testo delle voci del menu di Squadra o di Altro, una per pulsante (nome e spiegazione)."""
    return [" ".join(v.split()) for v in principale(web).get_by_role("navigation").get_by_role("button").all_inner_texts()]


def avvisi_di_errore(web):
    return principale(web).locator('[role="alert"]')


def test_squadra_e_altro_hanno_solo_le_voci_che_restano(web):
    solo(web, "prima")
    web.apri("/?vista=squadra")
    voci = voci_del_menu(web)
    assert len(voci) == 2 and voci[0].startswith("Squadre e rose") and voci[1].startswith("Aggiorna le rose"), voci
    web.apri("/?vista=altro")
    voci = voci_del_menu(web)
    assert len(voci) == 2 and voci[0].startswith("Diario delle giornate") and voci[1].startswith("Regole"), voci


@pytest.mark.parametrize("vecchio, atteso, nuovo", [
    ("/?vista=mercato", "Squadra", "/?vista=squadra"),                          # Cambi consigliati
    ("/?vista=mercato&scheda=osservati", "Squadra", "/?vista=squadra"),         # Seguiti
    ("/?vista=mercato&scheda=giocatori", "Squadra", "/?vista=squadra"),         # Elenco dei giocatori
    ("/?vista=mercato&scheda=calendario", "Squadra", "/?vista=squadra"),
    ("/?vista=squadra&voce=consigli", "Squadra", "/?vista=squadra"),
    ("/?vista=scambi", "Altro", "/?vista=altro"),
    ("/?vista=altro&voce=movimenti", "Altro", "/?vista=altro"),
    ("/?vista=altro&voce=crediti", "Altro", "/?vista=altro"),
    ("/?vista=altro&voce=stagione", "Altro", "/?vista=altro"),
])
def test_un_indirizzo_di_una_pagina_tolta_apre_il_menu_della_sua_scheda(web, vecchio, atteso, nuovo):
    solo(web, "prima")
    web.apri(vecchio)
    assert titolo(web) == atteso
    assert principale(web).get_by_role("navigation").is_visible()       # al telefono: il menu, non una pagina vuota
    assert web.pagina.url.endswith(nuovo)                               # l'indirizzo non resta quello della pagina tolta
    assert not web.errori_mostrati()


def test_l_indirizzo_delle_novita_apre_informazioni_con_le_ultime_versioni(web):
    solo(web, "prima")
    web.risposta("/api/novita", NOVITA)
    web.apri("/?vista=altro&voce=novita")
    assert titolo(web) == "Impostazioni"
    assert principale(web).get_by_role("heading", name="Informazioni", exact=True).is_visible()
    testo = web.testo_principale()
    assert "Una novità di prova" in testo and "Versione 9.2" in testo and "Una cosa cambiata" in testo
    assert "La novità di ieri" in testo and "Privacy" in testo          # le pagine legali restano sopra
    assert web.pagina.url.endswith("/?vista=impostazioni&gruppo=informazioni")


def test_le_novita_mostrano_le_ultime_dieci_versioni_e_le_altre_a_richiesta(web):
    """Le versioni sono centinaia: in Informazioni si vedono le ultime dieci, le altre con un pulsante."""
    solo(web, "prima")
    tante = [{"versione": f"9.{n}", "data": "2026-11-12", "titolo": f"Novità numero {n}", "voci": [f"Cosa {n}"]} for n in range(12, 0, -1)]
    web.risposta("/api/novita", tante)
    web.apri("/?vista=impostazioni&gruppo=informazioni")
    versioni = principale(web).get_by_role("heading", name=re.compile(r"^Novità numero \d+$"))
    assert versioni.count() == 10
    tocca(web, principale(web).get_by_role("button", name="Mostra le 2 versioni precedenti"))
    assert versioni.count() == 12
    assert principale(web).get_by_role("button", name="Mostra le 2 versioni precedenti").count() == 0


def test_formazione_ha_un_solo_stile_e_niente_legenda_confronto_e_immagine(web):
    solo(web, "prima")
    web.apri("/?vista=formazione")
    assert principale(web).locator(".campo .pedina").count() == 11
    testo = web.testo_principale()
    for tolto in ("Stile", "Equilibrata", "Molto sicura", "Rischiosa", "Ho capito", "Cosa vuol dire", "Condividi", "indice"):
        assert tolto not in testo, tolto
    bottoni = [b.strip() for b in principale(web).get_by_role("button").all_inner_texts()]
    assert "⇄" not in bottoni and "Altro" not in bottoni
    assert principale(web).get_by_role("button", name="Copia il testo").is_visible()         # non più dentro «Altro»
    assert principale(web).get_by_role("button", name=re.compile(r"^\d-\d-\d")).count() >= 3   # il modulo si sceglie ancora


def test_i_volti_non_hanno_piu_il_numero_dell_indice(web):
    solo(web, "prima")
    web.apri("/?vista=formazione")
    volti = principale(web).locator(".riga-gioc .avatar-anello")
    assert volti.count() >= 11
    assert [t for t in volti.all_inner_texts() if t.strip()] == []


def test_oggi_non_ha_partite_del_turno_diretta_e_banner_delle_novita(web):
    web.apri("/?vista=oggi", larghezza=PC)
    testo = web.testo_principale()
    assert "Partite del turno" not in testo and "Novità della versione" not in testo
    assert [r for r in web.richieste if r.startswith("/api/live")] == []
    colonne = principale(web).locator(".colonne-oggi > .col")
    assert all(t.strip() for t in colonne.all_inner_texts()), "una colonna di Oggi è vuota"
    assert "Da fare" in testo or "Tutto a posto" in testo


def test_oggi_sul_pc_non_lascia_a_destra_la_sola_riga_tutto_a_posto(web):
    """A giornata finita, senza elenchi di giocatori e senza cose da fare, a destra restava una colonna con la sola riga
    «Tutto a posto»: Oggi resta su una colonna. Con una partita rinviata o una cosa da fare la colonna di destra c'è."""
    solo(web, "in-corso", "finita")
    web.apri("/?vista=oggi", larghezza=PC)
    colonne = principale(web).locator(".colonne-oggi > .col")
    if web.fase == "finita":
        assert colonne.count() == 1 and "Tutto a posto" in colonne.first.inner_text()
    else:
        assert colonne.count() == 2 and "Da fare" in colonne.nth(1).inner_text() and "Punti fatti finora" in colonne.nth(0).inner_text()


def test_la_scheda_del_giocatore_non_ha_confronta_e_segui(web):
    solo(web, "prima")
    web.apri("/?vista=formazione")
    nome = principale(web).locator(".campo .pedina .nome").first.inner_text().strip()
    tocca(web, ".campo .pedina")
    scheda = web.pagina.get_by_role("dialog")
    assert nome in scheda.get_by_role("heading").first.inner_text()
    bottoni = " | ".join(scheda.get_by_role("button").all_inner_texts())
    assert not re.search(r"Confronta|Segui|Osserva|★|☆", bottoni), bottoni
    assert "Fantavoto atteso" in scheda.inner_text()


def test_un_tocco_su_un_ballottaggio_apre_la_scheda_dell_altro(web):
    solo(web, "prima")
    # nei dati registrati c'è una scelta salvata a mano, e con quella i ballottaggi non si mostrano: qui niente di salvato
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/?vista=formazione")
    alternative = principale(web).locator(".alternative-li").get_by_role("button")
    assert alternative.count() >= 1
    cognome = alternative.first.inner_text().split()[0]
    tocca(web, alternative.first)
    assert cognome in web.pagina.get_by_role("dialog").get_by_role("heading").first.inner_text()


def test_la_dimensione_del_testo_non_si_sceglie_piu_e_quella_salvata_non_vale(web):
    solo(web, "prima")
    web.memoria({"testo": "1.25"})
    web.apri("/?vista=impostazioni&gruppo=aspetto")
    testo = web.testo_principale()
    assert "Tema" in testo and "Dimensione del testo" not in testo and "Molto grande" not in testo
    assert web.pagina.evaluate("document.documentElement.style.zoom") in ("", "normal")
    assert web.pagina.evaluate("localStorage.getItem('testo')") is None


def _oggi_con_da_fare(web, da_fare: list[dict]) -> None:
    web.risposta("/api/oggi", {**web.registrata("/api/oggi"), "da_fare": da_fare})
    web.apri("/?vista=oggi")


def test_da_fare_non_propone_cambi_di_mercato_ne_scambi(web):
    solo(web, "prima")
    _oggi_con_da_fare(web, [
        {"id": "svincolato:1", "tipo": "svincolato", "testo": "Prendi Esempio al posto di Prova", "priorita": 3, "azione": "Vedi",
         "destinazione": {"scheda": "mercato", "sezione": None, "giocatore": 1}},
        {"id": "scambio:x", "tipo": "scambio", "testo": "Uno scambio possibile con Atletico Prova", "priorita": 3, "azione": "Apri",
         "destinazione": {"scheda": "scambi", "sezione": None}},
        {"id": "rose-vecchie", "tipo": "rose", "testo": "Le rose non si aggiornano da 20 giorni", "priorita": 2,
         "azione": "Aggiorna le rose", "destinazione": {"scheda": "lega", "sezione": "rose"}},
    ])
    testo = web.testo_principale()
    assert "Le rose non si aggiornano" in testo and "Prendi Esempio" not in testo and "scambio possibile" not in testo
    assert principale(web).get_by_role("heading", name=re.compile(r"^Da fare\s*1$")).is_visible()
    tocca(web, principale(web).get_by_role("button", name="Aggiorna le rose"))
    assert titolo(web) == "Squadra" and principale(web).get_by_role("heading", name="Aggiorna le rose", exact=True).is_visible()


def test_il_reparto_scoperto_resta_in_da_fare_e_porta_alla_rosa(web):
    """Difetto visto in revisione: la riga «Non hai nessun portiere disponibile» (priorità alta, la stessa dell'avviso sul
    telefono) spariva con i consigli di mercato, e Oggi diceva «Tutto a posto, Mister». Resta, e il suo pulsante porta alla rosa
    della propria squadra («Cerca un rimpiazzo» apriva Cambi consigliati, che sulla web non c'è più)."""
    solo(web, "prima")
    _oggi_con_da_fare(web, [
        {"id": "copertura:P", "tipo": "copertura", "testo": "Non hai nessun portiere disponibile per la prossima giornata.",
         "priorita": 1, "azione": "Cerca un rimpiazzo", "destinazione": {"scheda": "mercato", "sezione": None, "link": "schieraxi://mercato"},
         "reparto": "P", "livello": "scoperto", "disponibili": 0, "minimo": 1},
    ])
    testo = web.testo_principale()
    assert "Non hai nessun portiere disponibile" in testo and "Tutto a posto" not in testo
    assert principale(web).get_by_role("button", name="Cerca un rimpiazzo").count() == 0
    tocca(web, principale(web).get_by_role("button", name="Vedi la rosa"))
    assert titolo(web) == web.registrata("/api/rosa")["nome"] and "Portieri" in web.testo_principale()      # la rosa della mia squadra
    assert "vista=squadra" in web.pagina.url and "rosa=" in web.pagina.url
    assert not web.errori_mostrati() and not web.errori_console


def test_nuova_stagione_non_e_una_voce_di_menu(web):
    solo(web, "prima")
    web.apri("/?vista=altro")
    assert "Nuova stagione" not in web.testo_principale()


def test_nuova_stagione_compare_come_avviso_quando_serve(web):
    solo(web, "prima")
    web.risposta("/api/stagione", {"corrente": "2027-28", "rose": "2026-27", "nuova": True})
    web.apri("/?vista=altro")
    avviso = principale(web).get_by_role("button", name=re.compile("Nuova stagione 2027-28"))
    avviso.wait_for(timeout=10000)
    assert not any("Nuova stagione" in v for v in voci_del_menu(web))
    tocca(web, avviso)
    assert web.pagina.get_by_role("dialog").get_by_role("button", name="Archivia e riparti").is_visible()


def test_girando_per_l_app_non_si_chiedono_le_rotte_delle_funzioni_tolte(web):
    web.apri("/?vista=oggi", larghezza=PC)
    for indirizzo in ("/?vista=formazione", "/?vista=squadra", "/?vista=squadra&rosa=", "/?vista=altro", "/?vista=altro&voce=diario",
                      "/?vista=impostazioni", "/?vista=mercato", "/?vista=scambi"):
        web.apri(indirizzo, larghezza=PC)
    web.apri("/?vista=formazione", larghezza=PC)
    tocca(web, ".campo .pedina")
    assert sorted({r.split("?")[0] for r in web.richieste if r.startswith(ROTTE_TOLTE)}) == []


# ---------------------------------------------------------------- i patti: errori con role="alert", caricamento con aria-busy

SCHERMATE = ["/?vista=oggi", "/?vista=formazione", "/?vista=squadra", "/?vista=squadra&rosa=", "/?vista=altro", "/?vista=altro&voce=diario",
             "/?vista=altro&voce=regole", "/?vista=impostazioni", "/?vista=impostazioni&gruppo=informazioni"]


@pytest.mark.parametrize("rotta, indirizzo", [("/api/oggi", "/?vista=oggi"), ("/api/formazione", "/?vista=formazione"),
                                              ("/api/regole", "/?vista=altro&voce=regole"), ("/api/rosa", "/?vista=squadra&rosa=")])
def test_una_schermata_che_non_si_apre_lo_dice_con_un_avviso_di_errore(web, rotta, indirizzo):
    """La web cattura i suoi errori e non scrive in console: un errore mostrato nell'area principale ha `role="alert"`, così chi
    usa un lettore di schermo lo sente e i test del browser vedono una schermata che si rompe. E non resta «in caricamento»."""
    solo(web, "prima")
    web.risposta(rotta, {"detail": "rotta non registrata"}, stato=404)
    web.apri(indirizzo)
    assert avvisi_di_errore(web).count() == 1 and avvisi_di_errore(web).first.is_visible()
    assert web.errori_mostrati() and not web.in_caricamento()
    assert principale(web).get_attribute("aria-busy") != "true"


def test_le_schermate_sane_non_hanno_avvisi_di_errore(web):
    """`role="alert"` solo sugli errori veri: avvisi, stati vuoti e promemoria non lo hanno. E nessuna resta «in caricamento»."""
    web.risposta("/api/novita", NOVITA)
    for indirizzo in SCHERMATE:
        web.apri(indirizzo)
        assert avvisi_di_errore(web).count() == 0 and not web.errori_mostrati(), indirizzo
        assert not web.in_caricamento() and principale(web).locator('[aria-busy="true"]').count() == 0, indirizzo
        assert principale(web).get_attribute("aria-busy") != "true", indirizzo


def test_mentre_una_schermata_carica_l_area_principale_lo_dice(web):
    """Patto dei test del browser (tests/browser/LEGGIMI.md): finché una schermata carica, `<main>` ha aria-busy="true"; quando
    ha finito non più. Qui la risposta della Formazione si tiene ferma finché il test non la lascia passare."""
    solo(web, "prima")
    ferme = []
    web.pagina.route(lambda indirizzo: urlsplit(indirizzo).path == "/api/formazione", lambda richiesta: ferme.append(richiesta))
    web.pagina.goto(web.server.indirizzo + "/?vista=formazione", wait_until="load")
    web.pagina.locator('main[aria-busy="true"]').wait_for(state="attached", timeout=5000)
    assert ferme, "la Formazione non ha chiesto /api/formazione"
    for richiesta in ferme:
        richiesta.continue_()
    web.aspetta()
    assert principale(web).get_attribute("aria-busy") != "true" and not web.in_caricamento()
    assert principale(web).locator(".campo .pedina").count() == 11


# ---------------------------------------------------------------- riconoscimento delle rose: avvisi con role="status", errori con role="alert"

ANTEPRIMA = {
    "squadre": [{"nome": "Atletico Prova", "nuova": False, "totale": 2, "attesi": 2, "mancano": {}, "in_piu": {}, "senza_ruolo": 0,
                 "crediti_residui": None, "avvisi": [],
                 "giocatori": [{"testo": "Rossi", "stato": "sicuro", "id": 1, "nome": "Rossi"},
                               {"testo": "Bianki", "stato": "da_controllare", "id": 2, "nome": "Bianchi",
                                "alternative": [{"id": 2, "nome": "Bianchi", "ruolo": "D", "squadra": "COM"}]}]}],
    "avvisi": [], "avvisi_frasi": [], "mia_squadra": "Atletico Prova", "sicuri": 1, "da_controllare": 1, "non_trovati": 0, "differenze": None,
}
# Le regioni role="status" dell'area principale man mano che entrano nella pagina, con il testo che avevano in quel momento: un
# lettore di schermo legge ciò che viene scritto in una regione che c'è già, non la regione che nasce con il suo testo.
OSSERVA_REGIONI = """() => {
  window.regioniNate = [];
  new MutationObserver(cambi => { for (const c of cambi) for (const n of c.addedNodes) {
    if (n.nodeType !== 1) continue;
    for (const e of [n, ...n.querySelectorAll('[role=status]')]) if (e.matches('[role=status]')) window.regioniNate.push(e.innerText.trim());
  } }).observe(document.querySelector('main'), { childList: true, subtree: true });
}"""
IN_UNA_REGIONE = """(testo) => [...document.querySelectorAll('main [role=status]')].some(e => e.innerText.includes(testo))"""


def _apri_il_riconoscimento(web):
    web.risposta("/api/rose/anteprima", ANTEPRIMA)
    web.apri("/?vista=squadra&voce=importa")
    principale(web).locator("summary", has_text="Incolla il testo delle rose").click()
    principale(web).get_by_placeholder("Incolla qui il testo delle rose").fill("Atletico Prova\nRossi\nBianki")
    principale(web).get_by_role("button", name="Controlla il testo").click()
    principale(web).get_by_role("heading", name="Controlla prima di salvare").wait_for(timeout=10000)
    web.aspetta()
    web.pagina.evaluate(OSSERVA_REGIONI)


def test_nel_riconoscimento_delle_rose_l_avviso_di_una_ricerca_a_meta_viene_letto(web):
    """«Lo cerco io» senza scegliere un risultato: l'avviso si scrive in una regione `role="status"` che c'è già (un lettore di
    schermo lo legge), e non è un errore."""
    solo(web, "prima")
    _apri_il_riconoscimento(web)
    principale(web).get_by_label("Chi è «Bianki» (Atletico Prova)?").select_option("cerca")
    web.aspetta()
    tocca(web, principale(web).get_by_role("button", name="Conferma e salva"))
    avviso = principale(web).get_by_text("non hai ancora scelto il giocatore")
    avviso.wait_for(timeout=5000)
    assert web.pagina.evaluate(IN_UNA_REGIONE, "non hai ancora scelto il giocatore")
    assert not any("non hai ancora scelto" in t for t in web.pagina.evaluate("window.regioniNate")), "la regione è nata con il suo testo"
    assert avvisi_di_errore(web).count() == 0 and not web.errori_mostrati()


def test_nel_riconoscimento_delle_rose_l_avviso_delle_rose_cambiate_viene_letto(web):
    """Rose cambiate nel frattempo (il server rifiuta il salvataggio): l'anteprima si rifà e l'avviso arriva in una regione
    `role="status"` già in pagina, non insieme a lei."""
    solo(web, "prima")
    _apri_il_riconoscimento(web)
    web.risposta("/api/rose/testo", {"detail": "Le rose sono cambiate nel frattempo"}, stato=412)
    principale(web).get_by_role("button", name="Conferma e salva").click()
    avviso = principale(web).get_by_text("Nel frattempo le rose sono cambiate")
    avviso.wait_for(timeout=10000)
    web.aspetta()
    assert web.pagina.evaluate(IN_UNA_REGIONE, "Nel frattempo le rose sono cambiate")
    assert not any("Nel frattempo" in t for t in web.pagina.evaluate("window.regioniNate")), "la regione è nata con il suo testo"
    assert avvisi_di_errore(web).count() == 0 and not web.errori_mostrati()


def test_nel_riconoscimento_delle_rose_un_salvataggio_fallito_e_un_errore(web):
    solo(web, "prima")
    _apri_il_riconoscimento(web)
    web.risposta("/api/rose/testo", {"detail": "Non sono riuscito a salvare le rose"}, stato=500)
    tocca(web, principale(web).get_by_role("button", name="Conferma e salva"))
    assert avvisi_di_errore(web).count() == 1 and "Non sono riuscito a salvare le rose" in avvisi_di_errore(web).first.inner_text()
    assert web.errori_mostrati()
