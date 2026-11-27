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
    # cosa mostra l'errore con l'attesa (la frase del server e poi «Riprova tra 10 secondi.») lo prova, eseguendo il codice,
    # tests/test_web_attese.py::test_l_errore_con_l_attesa_sono_due_frasi_come_sull_iphone (revisione della #968)
