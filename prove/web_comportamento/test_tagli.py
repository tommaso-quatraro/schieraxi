"""La web senza le funzioni tolte il 12/11/2026 (#615): niente voci morte nei menu, gli indirizzi di prima aprono la schermata
più vicina che resta, e le schermate che restano non mostrano più stili, legenda, confronto, diretta e banner.

Si guarda ciò che vede chi usa l'app (testi, pulsanti, cosa succede a un tocco), non il sorgente.
"""
import re

import pytest

from web_di_prova import PC, risposta_registrata

ROTTE_TOLTE = ("/api/live", "/api/mercato", "/api/osservati", "/api/scambi", "/api/confronto", "/api/classifica", "/api/movimenti")
NOVITA = [{"versione": "9.2", "data": "2026-11-12T10:00:00", "titolo": "Una novità di prova", "voci": ["Una cosa cambiata"]},
          {"versione": "9.1", "data": "2026-11-11", "titolo": "La novità di ieri", "voci": ["Un'altra cosa"]}]


def _voci_del_menu(s) -> list[str]:
    return [v.strip() for v in s.pagina.locator(".lega-menu .nome").all_inner_texts()]


def test_squadra_e_altro_hanno_solo_le_voci_che_restano(apri):
    s = apri("/?vista=squadra")
    assert _voci_del_menu(s) == ["Squadre e rose", "Aggiorna le rose"]
    s.vai("/?vista=altro")
    assert _voci_del_menu(s) == ["Diario delle giornate", "Regole"]


@pytest.mark.parametrize("vecchio, titolo, nuovo", [
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
def test_un_indirizzo_di_una_pagina_tolta_apre_il_menu_della_sua_scheda(apri, vecchio, titolo, nuovo):
    s = apri(vecchio)
    assert s.titolo() == titolo
    assert s.pagina.locator(".lega-menu").is_visible()                # al telefono: il menu, non una pagina vuota
    assert s.pagina.url.endswith(nuovo)                               # l'indirizzo non resta quello della pagina tolta


def test_l_indirizzo_delle_novita_apre_informazioni_con_le_ultime_versioni(apri):
    s = apri("/?vista=altro&voce=novita", risposte={"/api/novita": NOVITA})
    assert s.titolo() == "Impostazioni"
    assert s.pagina.locator("#imp-titolo").inner_text().strip() == "Informazioni"
    testo = s.testo("#imp-pagina")
    assert "Una novità di prova" in testo and "Versione 9.2" in testo and "Una cosa cambiata" in testo
    assert "La novità di ieri" in testo and "Privacy" in testo          # le pagine legali restano sopra
    assert s.pagina.url.endswith("/?vista=impostazioni&gruppo=informazioni")


def test_formazione_ha_un_solo_stile_e_niente_legenda_confronto_e_immagine(apri):
    s = apri("/?vista=formazione")
    assert s.pagina.locator(".campo .pedina").count() == 11
    testo = s.testo()
    for tolto in ("Stile", "Equilibrata", "Molto sicura", "Rischiosa", "Ho capito", "Cosa vuol dire", "Condividi", "indice"):
        assert tolto not in testo, tolto
    bottoni = [b.strip() for b in s.pagina.locator("#contenuto button").all_inner_texts()]
    assert "⇄" not in bottoni and "Altro" not in bottoni
    assert s.pagina.get_by_role("button", name="Copia il testo").is_visible()         # non più dentro «Altro»
    assert s.pagina.locator("[data-modulo]").count() >= 3                             # il modulo si sceglie ancora


def test_i_volti_non_hanno_piu_il_numero_dell_indice(apri):
    s = apri("/?vista=formazione")
    volti = s.pagina.locator("#contenuto .riga-gioc .avatar-anello")
    assert volti.count() >= 11
    assert [t for t in volti.all_inner_texts() if t.strip()] == []


@pytest.mark.parametrize("fase", ["prima", "in-corso", "finita"])
def test_oggi_non_ha_partite_del_turno_diretta_e_banner_delle_novita(apri, fase):
    s = apri("/?vista=oggi", fase=fase, misura=PC)
    testo = s.testo()
    assert "Partite del turno" not in testo and "Novità della versione" not in testo
    assert s.chieste("/api/live") == []
    colonne = s.pagina.locator(".colonne-oggi > .col")
    assert all(t.strip() for t in colonne.all_inner_texts()), "una colonna di Oggi è vuota"
    assert "Da fare" in testo or "Tutto a posto" in testo


def test_oggi_sul_pc_non_lascia_a_destra_la_sola_riga_tutto_a_posto(apri):
    """A giornata finita, senza elenchi di giocatori e senza cose da fare, a destra restava una colonna con la sola riga
    «Tutto a posto»: Oggi resta su una colonna. Con una partita rinviata o una cosa da fare la colonna di destra c'è."""
    s = apri("/?vista=oggi", fase="finita", misura=PC)
    assert s.pagina.locator(".colonne-oggi > .col").count() == 1 and "Tutto a posto" in s.testo(".colonne-oggi > .col")
    s = apri("/?vista=oggi", fase="in-corso", misura=PC)
    colonne = s.pagina.locator(".colonne-oggi > .col")
    assert colonne.count() == 2 and "Da fare" in colonne.nth(1).inner_text() and "Punti fatti finora" in colonne.nth(0).inner_text()


def test_la_scheda_del_giocatore_non_ha_confronta_e_segui(apri):
    s = apri("/?vista=formazione")
    nome = s.pagina.locator(".campo .pedina .nome").first.inner_text().strip()
    s.tocca(".campo .pedina")
    scheda = s.pagina.locator("#foglio-contenuto")
    assert nome in scheda.locator("h2").first.inner_text()
    bottoni = " | ".join(scheda.locator("button").all_inner_texts())
    assert not re.search(r"Confronta|Segui|Osserva|★|☆", bottoni), bottoni
    assert "Fantavoto atteso" in scheda.inner_text()


def test_un_tocco_su_un_ballottaggio_apre_la_scheda_dell_altro(apri):
    # nei dati registrati c'è una scelta salvata a mano, e con quella i ballottaggi non si mostrano: qui niente di salvato
    s = apri("/?vista=formazione", risposte={"/api/scelta?giornata=9": None})
    alternative = s.pagina.locator(".alternative-li .alt")
    assert alternative.count() >= 1
    cognome = alternative.first.inner_text().split()[0]
    s.tocca(alternative.first)
    assert cognome in s.pagina.locator("#foglio-contenuto h2").first.inner_text()


def test_la_dimensione_del_testo_non_si_sceglie_piu_e_quella_salvata_non_vale(apri):
    s = apri("/?vista=impostazioni&gruppo=aspetto", memoria={"testo": "1.25"})
    testo = s.testo("#imp-pagina")
    assert "Tema" in testo and "Dimensione del testo" not in testo and "Molto grande" not in testo
    assert s.pagina.evaluate("document.documentElement.style.zoom") in ("", "normal")
    assert s.pagina.evaluate("localStorage.getItem('testo')") is None


def test_da_fare_non_propone_cambi_di_mercato_ne_scambi(apri):
    da_fare = [
        {"id": "svincolato:1", "tipo": "svincolato", "testo": "Prendi Esempio al posto di Prova", "priorita": 3, "azione": "Vedi",
         "destinazione": {"scheda": "mercato", "sezione": None, "giocatore": 1}},
        {"id": "scambio:x", "tipo": "scambio", "testo": "Uno scambio possibile con Atletico Prova", "priorita": 3, "azione": "Apri",
         "destinazione": {"scheda": "scambi", "sezione": None}},
        {"id": "rose-vecchie", "tipo": "rose", "testo": "Le rose non si aggiornano da 20 giorni", "priorita": 2,
         "azione": "Aggiorna le rose", "destinazione": {"scheda": "lega", "sezione": "rose"}},
    ]
    s = apri("/?vista=oggi", risposte={"/api/oggi": {**risposta_registrata("/api/oggi"), "da_fare": da_fare}})
    carta = s.testo(".df-carta")
    assert "Le rose non si aggiornano" in carta and "Prendi Esempio" not in carta and "scambio possibile" not in carta
    assert s.pagina.locator(".df-conto").inner_text().strip() == "1"
    s.tocca(".df-azione")
    assert s.titolo() == "Squadra" and s.pagina.locator("#lega-titolo").inner_text().strip() == "Aggiorna le rose"


def test_nuova_stagione_non_e_una_voce_di_menu_e_compare_come_avviso_quando_serve(apri):
    s = apri("/?vista=altro")
    assert "Nuova stagione" not in s.testo()
    s = apri("/?vista=altro", risposte={"/api/stagione": {"corrente": "2027-28", "rose": "2026-27", "nuova": True}})
    s.pagina.locator("#banner-stagione").wait_for(timeout=10000)
    assert "Nuova stagione 2027-28" in s.testo()
    assert "Nuova stagione" not in " ".join(_voci_del_menu(s))
    s.tocca("#banner-stagione")
    assert s.pagina.locator("#foglio-contenuto").get_by_role("button", name="Archivia e riparti").is_visible()


def test_girando_per_l_app_non_si_chiedono_le_rotte_delle_funzioni_tolte(apri):
    s = apri("/?vista=oggi", misura=PC)
    for indirizzo in ("/?vista=formazione", "/?vista=squadra", "/?vista=squadra&rosa=", "/?vista=altro", "/?vista=altro&voce=diario",
                      "/?vista=impostazioni", "/?vista=mercato", "/?vista=scambi"):
        s.vai(indirizzo)
    s.vai("/?vista=formazione")
    s.tocca(".campo .pedina")
    assert sorted({r.split("?")[0] for r in s.chieste(*ROTTE_TOLTE)}) == []


def test_le_novita_mostrano_le_ultime_dieci_versioni_e_le_altre_a_richiesta(apri):
    """Le versioni sono centinaia: in Informazioni si vedono le ultime dieci, le altre con un pulsante."""
    tante = [{"versione": f"9.{n}", "data": "2026-11-12", "titolo": f"Novità numero {n}", "voci": [f"Cosa {n}"]} for n in range(12, 0, -1)]
    s = apri("/?vista=impostazioni&gruppo=informazioni", risposte={"/api/novita": tante})
    assert s.pagina.locator("#novita-elenco .novita-titolo").count() == 10
    s.tocca(s.pagina.get_by_role("button", name="Mostra le 2 versioni precedenti"))
    assert s.pagina.locator("#novita-elenco .novita-titolo").count() == 12
    assert s.pagina.get_by_role("button", name="Mostra le 2 versioni precedenti").count() == 0


# ---------------------------------------------------------------- errori nell'area principale: role="alert" (patto con i test del browser)

SCHERMATE = ["/?vista=oggi", "/?vista=formazione", "/?vista=squadra", "/?vista=squadra&rosa=", "/?vista=altro", "/?vista=altro&voce=diario",
             "/?vista=altro&voce=regole", "/?vista=impostazioni", "/?vista=impostazioni&gruppo=informazioni"]


@pytest.mark.parametrize("rotta, indirizzo", [("/api/oggi", "/?vista=oggi"), ("/api/formazione", "/?vista=formazione"),
                                              ("/api/regole", "/?vista=altro&voce=regole"), ("/api/rosa", "/?vista=squadra&rosa=")])
def test_una_schermata_che_non_si_apre_lo_dice_con_un_avviso_di_errore(apri, rotta, indirizzo):
    """La web cattura i suoi errori e non scrive in console: un errore mostrato nell'area principale ha `role="alert"`, così chi
    usa un lettore di schermo lo sente e i test del browser vedono una schermata che si rompe."""
    s = apri(indirizzo, risposte={rotta: ...})
    errori = s.pagina.locator('#contenuto [role="alert"]')
    assert errori.count() == 1 and errori.first.is_visible() and errori.first.inner_text().strip()


@pytest.mark.parametrize("fase", ["prima", "in-corso", "finita"])
def test_le_schermate_sane_non_hanno_avvisi_di_errore(apri, fase):
    """`role="alert"` solo sugli errori veri: avvisi, stati vuoti e promemoria non lo hanno."""
    s = apri("/", fase=fase, risposte={"/api/novita": NOVITA})
    for indirizzo in SCHERMATE:
        s.vai(indirizzo)
        assert s.pagina.locator('#contenuto [role="alert"]').count() == 0, indirizzo
