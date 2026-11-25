"""La scheda del giocatore, «Tutti i numeri» > «Prossime partite» (#882): la difficoltà di ogni partita si legge anche a parole
nella sua casella («Facile» … «Molto dura», le parole della pillola della partita), non solo dal colore, e la parola resta dentro
la casella anche sul telefono. Le partite e la difficoltà sono quelle del calendario registrato per la squadra del giocatore.
"""
import pytest

# le parole della difficoltà (`diff.1`…`diff.5` del catalogo), le stesse della pillola «Questa partita»
DIFFICOLTA = {1: "Facile", 2: "Abbordabile", 3: "Normale", 4: "Dura", 5: "Molto dura"}

# per ogni casella delle prossime partite: le righe del testo e se la scritta esce dalla casella; poi se la fila esce dalla scheda
CASELLE = """() => {
  const fila = document.querySelector('[role="dialog"] .prossime');
  if (!fila) return null;
  return {
    caselle: [...fila.children].map(c => ({ righe: c.innerText.split('\\n').map(r => r.trim()).filter(Boolean),
                                            esce: c.scrollWidth > c.clientWidth + 1 })),
    filaEsce: fila.scrollWidth > fila.clientWidth + 1,
  };
}"""


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_nelle_prossime_partite_la_difficolta_si_legge_anche_a_parole(web, larghezza):
    if web.fase != "prima":
        pytest.skip("vale per la fase: prima")
    web.apri("/", larghezza=larghezza)
    pedina = web.pagina.locator("main #campo-formazione").get_by_role("button").first
    id_giocatore = pedina.get_attribute("data-giocatore")
    pedina.click(timeout=10000)
    web.aspetta()
    scheda = web.pagina.get_by_role("dialog")
    scheda.get_by_text("Tutti i numeri").click(timeout=10000)
    web.aspetta()
    scheda.get_by_role("heading", name="Prossime partite").wait_for(timeout=10000)

    squadra = web.registrata(f"/api/giocatore/{id_giocatore}")["previsione"]["squadra"]
    partite = next(s for s in web.registrata("/api/calendario")["squadre"] if s["squadra"] == squadra)["partite"]
    assert partite, "nel calendario registrato la squadra non ha partite: il test non proverebbe niente"

    visto = web.pagina.evaluate(CASELLE)
    assert visto, "nella scheda non ci sono le prossime partite"
    assert [c["righe"][-1] for c in visto["caselle"]] == [DIFFICOLTA[p["difficolta"]] for p in partite]
    assert not [c for c in visto["caselle"] if c["esce"]], "una parola esce dalla sua casella"
    assert not visto["filaEsce"], "le caselle escono dalla scheda"
