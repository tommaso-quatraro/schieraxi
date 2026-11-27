"""La Formazione aperta resta vera: si rilegge da sola quando serve, una volta per evento e mai a ciclo.

Difetto trovato il 27/11/2026: passata la scadenza la testa diceva «Formazione chiusa» (già 30 secondi prima, per un
arrotondamento), ma modulo, «L'ho messa» e «Sostituisci» restavano attivi, la giornata non passava a «in corso» e i punti non
arrivavano; tornando sull'app si cercava solo una versione nuova. Ora la Formazione si rilegge quando il conto arriva a zero
(qualche secondo dopo, per dare tempo al server, come l'iPhone) e quando la pagina torna in primo piano con i dati vecchi o con
la scadenza passata.

L'orologio della pagina qui è comandato dal test (`clock.install`): parte dal momento scelto e si porta avanti con
`clock.fast_forward` (i timer scaduti partono una volta) o `clock.set_system_time` (cambia l'ora senza far partire i timer).
"""
import pytest

from test_formazione_unica import principale, solo, sostituti_dal_server

SCADENZA = "2026-10-27T18:20:00"            # la scadenza della giornata nello scenario registrato «prima» (/api/oggi)

# L'app torna in primo piano: la pagina diventa nascosta e poi visibile (come in test_web_installata.py).
TORNA_IN_PRIMO_PIANO = """() => new Promise(fatto => {
  for (const v of ['hidden', 'visible']) {
    Object.defineProperty(document, 'visibilityState', { value: v, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  }
  setTimeout(fatto, 0);
})"""


def _ms(web, quando: str) -> float:
    """«2026-10-27T18:20:00», ora italiana (il fuso del browser), in millisecondi dal 1970."""
    return web.pagina.evaluate("(s) => new Date(s).getTime()", quando)


def _orologio(web, quando: str) -> None:
    """Prima di `apri`: l'orologio della pagina parte da `quando` e da lì lo porta avanti il test."""
    web.pagina.clock.install(time=_ms(web, quando) / 1000)


def _letture(web) -> int:
    return web.richieste.count("/api/formazione")


def _torna_in_primo_piano(web) -> None:
    web.pagina.evaluate(TORNA_IN_PRIMO_PIANO)
    web.aspetta()


def _avanti(web, ms: int) -> None:
    web.pagina.clock.fast_forward(ms)
    web.aspetta()


def _testa(web) -> str:
    return " ".join(principale(web).locator(".tg-scadenza").inner_text().split())


@pytest.fixture(autouse=True)
def _sostituisci_risponde(request):
    if "web" in request.fixturenames:
        sostituti_dal_server(request.getfixturevalue("web"))


def test_a_pochi_secondi_dalla_scadenza_la_testa_non_dice_ancora_chiusa(web):
    """25 secondi prima della scadenza la testa diceva già «Formazione chiusa» (i minuti arrotondati a zero), mentre la formazione
    si poteva ancora cambiare: chiusa solo da quando la scadenza è passata."""
    solo(web, "prima")
    web.orologio("2026-10-27T18:19:35")
    web.apri("/")
    assert "Formazione chiusa" not in _testa(web), _testa(web)
    assert "fra 1 min" in _testa(web), _testa(web)


def test_alla_scadenza_la_formazione_si_rilegge_una_volta_e_non_si_cambia_piu(web):
    solo(web, "prima")
    _orologio(web, "2026-10-27T18:18:00")                          # due minuti alla scadenza
    web.risposta("/api/scelta?giornata=9", None)
    web.apri("/")
    assert principale(web).get_by_label("Modulo").is_enabled()
    lette = _letture(web)
    f = web.registrata("/api/formazione")
    web.risposta("/api/formazione", {**f, "iniziata": True})       # passata la scadenza il server la dice chiusa
    _avanti(web, 2 * 60_000 + 10_000)
    assert _letture(web) == lette + 1, "alla scadenza la Formazione non si è riletta (una volta)"
    assert principale(web).get_by_label("Modulo").count() == 0, "passata la scadenza il modulo si cambia ancora"
    assert principale(web).get_by_role("checkbox", name="L'ho messa").count() == 0
    for _ in range(3):                                              # niente letture a ciclo
        _avanti(web, 60_000)
    assert _letture(web) == lette + 1
    assert not web.errori_mostrati() and not web.errori_console


def test_se_dopo_la_scadenza_il_server_la_dice_ancora_aperta_non_si_rilegge_a_ciclo(web):
    """L'orologio del telefono avanti di qualche secondo: riletta alla scadenza, il server la dice ancora aperta. Una lettura per
    la scadenza, non una ogni 30 secondi (se poi un salvataggio arriva tardi, il server risponde «formazione chiusa» e la pagina
    si rilegge)."""
    solo(web, "prima")
    _orologio(web, "2026-10-27T18:18:00")
    web.apri("/")
    lette = _letture(web)
    _avanti(web, 2 * 60_000 + 10_000)
    assert _letture(web) == lette + 1
    for _ in range(4):
        _avanti(web, 60_000)
    assert _letture(web) == lette + 1, "dopo la scadenza la Formazione si rilegge a ciclo"
    assert "Formazione chiusa" in _testa(web)


def test_tornando_in_primo_piano_con_i_dati_vecchi_la_formazione_si_rilegge_una_volta(web):
    solo(web, "prima")
    _orologio(web, "2026-10-27T15:10:00")
    web.apri("/")
    lette = _letture(web)
    _torna_in_primo_piano(web)
    assert _letture(web) == lette, "appena letta, tornando in primo piano la Formazione si è riletta"
    _avanti(web, 15 * 60_000)                                       # un quarto d'ora con l'app in un'altra scheda
    assert _letture(web) == lette
    _torna_in_primo_piano(web)
    assert _letture(web) == lette + 1, "con i dati di un quarto d'ora fa, tornando in primo piano la Formazione non si è riletta"
    _torna_in_primo_piano(web)
    _torna_in_primo_piano(web)
    assert _letture(web) == lette + 1, "a dati appena riletti, ogni ritorno in primo piano rilegge"
    assert not web.errori_mostrati() and not web.errori_console


def test_tornando_in_primo_piano_a_scadenza_passata_la_formazione_si_rilegge(web):
    """Con il telefono in tasca i timer della pagina si fermano: tornando sull'app dopo la scadenza, la Formazione si rilegge
    subito (anche se i dati sono di pochi minuti fa) e una volta sola."""
    solo(web, "prima")
    _orologio(web, "2026-10-27T18:18:00")
    web.apri("/")
    lette = _letture(web)
    web.pagina.clock.set_system_time(_ms(web, "2026-10-27T18:21:00") / 1000)     # l'ora cambia, i timer non partono
    _torna_in_primo_piano(web)
    assert _letture(web) == lette + 1, "tornando in primo piano dopo la scadenza la Formazione non si è riletta"
    _avanti(web, 3 * 60_000)
    _torna_in_primo_piano(web)
    assert _letture(web) == lette + 1, "dopo la rilettura la pagina ha riletto ancora (timer della scadenza vecchio o ritorno)"
