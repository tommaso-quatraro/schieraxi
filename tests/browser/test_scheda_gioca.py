"""La scheda del giocatore dice quanto è probabile che giochi una volta sola (#923).

Nelle foto del 26/11 il 62% compariva tre volte: il numero accanto al fantavoto atteso («gioca 62%»), la pillola «In dubbio» e,
in «Perché questo numero», la riga «gioca il 62%: dubbio». La regola delle schermate (skill `ui-schieraxi`, «Il giocatore»):
accanto al numero al massimo un'altra informazione, quanto è probabile che giochi. Resta quella, con la parola dello stato sotto;
fra i motivi del numero la riga «gioca» non c'è più (non cambia il fantavoto «se gioca»), gli altri motivi sì.
"""
import re

import pytest

from test_formazione_unica import principale, scheda, solo, tocca


def _con_motivo_gioca(f: dict) -> dict:
    """Un giocatore della formazione registrata con il motivo «gioca N%» fra i motivi del numero (in dubbio, non infortunato)."""
    for x in f["schede"].values():
        motivi = x.get("perche_numero") or []
        if any(m.get("chiave") == "gioca" and re.search(r"\d+%", m.get("testo", "")) for m in motivi) \
                and any(m.get("chiave") != "gioca" for m in motivi):
            return x
    raise AssertionError("nella formazione registrata nessuno ha il motivo «gioca N%»: il test non proverebbe niente")


@pytest.mark.parametrize("larghezza", [390, 1440])
def test_la_percentuale_di_gioco_compare_una_volta_sola(web, larghezza):
    solo(web, "prima")
    f = web.registrata("/api/formazione")
    x = _con_motivo_gioca(f)
    gioca = next(m["testo"] for m in x["perche_numero"] if m["chiave"] == "gioca")
    percento = re.search(r"\d+%", gioca).group(0)
    altri = [m["testo"] for m in x["perche_numero"] if m["chiave"] != "gioca"]
    # che si apra dal campo o dalla panchina: la riga del giocatore è un pulsante con il suo numero
    web.apri("/", larghezza=larghezza)
    tocca(web, principale(web).locator(f'[data-giocatore="{x["id"]}"]').first)
    s = scheda(web)
    s.get_by_role("heading", name="Perché questo numero").wait_for(timeout=10000)
    testo = " ".join(s.inner_text().split())
    assert testo.count(percento) == 1, (percento, testo[:600])
    assert gioca not in testo, testo[:600]
    for motivo in altri:                                           # gli altri motivi del numero restano
        assert motivo in testo, (motivo, testo[:600])
