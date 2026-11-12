"""Errori a tutta pagina nella web app: pulsante «Riprova» e attesa indicata quando il server dice «troppe richieste» (429)."""
import re

import codice_web

JS = codice_web.app()


def test_errore_a_tutta_pagina_ha_il_pulsante_riprova():
    assert "const erroreVista" in JS and "data-riprova" in JS
    assert 'ev.target.closest("[data-riprova]")' in JS                       # un solo gestore globale: ricarica la sezione aperta
    # le sezioni che si caricano per intero usano la versione col pulsante (scritta da pagina(), sotto il titolo della schermata)
    assert len(re.findall(r"pagina\(erroreVista\(e\)", JS)) >= 2
    assert "contenuto.innerHTML = erroreVista(e)" not in JS


def test_errore_429_dice_quanto_aspettare():
    assert "const attesaDa" in JS
    assert "e.status === 429 && e.riprova" in JS
    assert "const errore = e => `<div class=\"errore\" role=\"alert\">${esc(e.message || e)}${attesaDa(e)}</div>`;" in JS
