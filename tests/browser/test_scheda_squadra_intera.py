"""Scheda del giocatore: sotto il nome la squadra di Serie A è scritta per intero, per ogni giocatore (collaudo del 27/11 sera).

Dalla Formazione la scheda si apre con i dati già in pagina e scriveva «Milan»; da altrove (la rosa di un'altra squadra, la ricerca)
aspetta la scheda del server (`/api/giocatore`), e scriveva la sigla del listone («Attaccante · INT»). Il server manda tutte e due
(`calciatore.squadra` è la sigla, `calciatore.squadra_slug` il nome nell'indirizzo del listone): la web scrive il nome per intero.
La scheda registrata del giocatore la dà il test (`web.risposta`), con un giocatore della rosa registrata."""
from test_formazione_unica import principale, scheda, solo, tocca


def test_la_scheda_di_un_giocatore_di_un_altra_squadra_scrive_la_squadra_per_intero(web):
    solo(web, "prima")
    rosa = web.registrata("/api/rosa?squadra=Real%20Esempio")
    g = next(x for x in rosa["giocatori"] if x.get("id") and x.get("ruolo") == "A")
    s = web.registrata("/api/giocatore/2115")
    s["calciatore"] |= {"id": g["id"], "nome": g["nome"], "ruolo": "A", "squadra": "INT", "squadra_slug": "inter"}
    s["previsione"] = None
    web.risposta(f"/api/giocatore/{g['id']}", s)
    web.apri("/?vista=impostazioni&gruppo=squadre&rosa=Real%20Esempio")
    tocca(web, principale(web).locator(f"[data-giocatore='{g['id']}']").first)
    foglio = scheda(web)
    foglio.get_by_role("heading", name=g["nome"]).wait_for(timeout=10000)
    testo = " ".join(foglio.inner_text().split())
    assert "Attaccante · Inter" in testo, testo[:300]
    assert "INT" not in testo, testo[:300]
    assert not web.errori_console, web.errori_console
