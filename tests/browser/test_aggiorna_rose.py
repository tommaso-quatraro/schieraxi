"""Impostazioni › Aggiorna le rose, dal collaudo del 26/11: l'interruttore «Togli le squadre che non sono nel file» si vede e vale
anche per il file (prima stava solo dentro «Incolla il testo», chiuso), il pulsante del testo si chiama come nella guida
(«Controlla le rose») e dopo «Conferma e salva» il fuoco va sul titolo dell'esito, non si perde in fondo alla pagina.
Anteprima e salvataggio rispondono dal browser (il server finto non li ha). Gira solo prima della scadenza: la fase non conta."""
import json
from urllib.parse import parse_qs, urlsplit

import pytest

SOMMER = {"testo": "Sommer", "riga": 0, "stato": "sicuro", "metodo": "esatto", "id": 2, "nome": "Sommer", "ruolo": "P",
          "squadra": "INT", "costo": 10, "avviso": "", "avviso_frase": None, "alternative": []}
NESSUNA = {"prima_importazione": False, "nessuna_differenza": True, "scambi": [], "svincolati_presi": [], "tagliati": [],
           "crediti": [], "squadre_nuove": [], "squadre_tolte": ["Altra"], "testo": "Nessuna differenza."}
ANTEPRIMA = {"squadre": [{"nome": "Mia", "nuova": False, "crediti_residui": None, "sicuri": 1, "da_controllare": 0, "non_trovati": 0,
                          "totale": 1, "attesi": 25, "ruoli": {"P": 1, "D": 0, "C": 0, "A": 0},
                          "mancano": {"P": 2, "D": 8, "C": 8, "A": 6}, "in_piu": {}, "senza_ruolo": 0, "completa": False,
                          "avvisi": [], "giocatori": [SOMMER]}],
             "avvisi": [], "avvisi_frasi": [], "mia_squadra": "Mia", "totale_squadre": 1, "sicuri": 1, "da_controllare": 0,
             "non_trovati": 0, "differenze": NESSUNA, "riepilogo": "Nessuna differenza."}
ESITO = {"squadre_importate": ["Mia"], "totale_squadre": 1, "mia_squadra": "Mia", "differenze": NESSUNA, "riepilogo": "Nessuna differenza.",
         "avvisi": ["Mia: mancano 2 portieri, 8 difensori, 8 centrocampisti e 6 attaccanti."], "avvisi_frasi": [None]}


def rispondi(web, percorso: str, corpo: dict, chieste: list) -> None:
    def rotta(route):
        chieste.append(route.request.url)
        route.fulfill(status=200, content_type="application/json; charset=utf-8", body=json.dumps(corpo),
                      headers={"ETag": '"rose-1"'})
    web.pagina.route(lambda u: urlsplit(u).path == percorso, rotta)


def test_interruttore_anche_per_il_file_e_fuoco_sull_esito(web, tmp_path):
    if web.fase != "prima":
        pytest.skip("conta la pagina delle rose, non la fase della giornata")
    chieste: list[str] = []
    rispondi(web, "/api/rose/anteprima/file", ANTEPRIMA, chieste)
    rispondi(web, "/api/rose/file", ESITO, chieste)
    web.apri("/?vista=impostazioni&gruppo=rose")
    p = web.pagina
    interruttore = p.get_by_label("Togli le squadre che non sono nel file")
    assert interruttore.is_visible()                                   # senza aprire «Incolla il testo delle rose»
    interruttore.check()
    file = tmp_path / "rose.csv"
    file.write_text("Mia\nSommer\n", encoding="utf-8")
    with p.expect_file_chooser() as scelta:
        p.get_by_role("button", name="Scegli il file (Excel o CSV)").click()
    scelta.value.set_files(str(file))
    p.get_by_role("button", name="Conferma e salva").click()
    p.get_by_role("heading", name="Cosa è cambiato").wait_for(timeout=10000)
    assert p.evaluate("document.activeElement.textContent.trim()") == "Cosa è cambiato"
    assert len(chieste) == 2 and all(parse_qs(urlsplit(u).query).get("sostituisci_tutto") == ["true"] for u in chieste), chieste


def test_il_pulsante_del_testo_si_chiama_come_nella_guida(web):
    if web.fase != "prima":
        pytest.skip("conta la pagina delle rose, non la fase della giornata")
    web.apri("/?vista=impostazioni&gruppo=rose")
    p = web.pagina
    p.get_by_text("Incolla il testo delle rose").click()
    assert p.get_by_role("button", name="Controlla le rose").is_visible()
