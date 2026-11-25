"""Le fasi della giornata sulla web, ai bordi (#895): la giornata in corso e quella finita mostrano ciò che il server conta e dice.

Ogni caso parte dalla risposta registrata di /api/oggi della sua fase e cambia solo il pezzo che serve (come il collaudo del 25/11):
il voto d'ufficio di una partita rinviata, la frase sotto i punti scelta dal server, la scelta sul rinvio della giornata finita
con il suo titolo, la giornata finita senza voti, chi è rimasto senza voto, la colonna della panchina. Si guarda ciò che si vede.
"""
import copy
import re

import pytest


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def principale(web):
    return web.pagina.locator("main")


def pedina(web, nome: str):
    """La pedina di un titolare sul campo: il suo nome per i lettori di schermo comincia con il nome del giocatore."""
    return principale(web).locator("#campo-formazione").get_by_role("button", name=re.compile("^" + re.escape(nome)))


def oggi_in_corso(web) -> dict:
    return copy.deepcopy(web.registrata("/api/oggi"))


def giocatore(oggi: dict, nome: str) -> dict:
    return next(g for g in oggi["in_corso"]["giocatori"] if g["nome"] == nome)


# ---------------------------------------------------------------- 1. il voto d'ufficio della partita rinviata
def test_il_voto_d_ufficio_della_partita_rinviata_si_vede_sul_campo(web):
    """Il server conta il 6 d'ufficio di Bapepe (partita rinviata) tra i punti fatti: sul campo la pedina ha il 6, non il fantavoto
    atteso, e dice «Voto d'ufficio» (l'etichetta del server), anche per chi usa un lettore di schermo."""
    solo(web, "in-corso")
    o = oggi_in_corso(web)
    bapepe = giocatore(o, "Bapepe")
    assert bapepe["stato"] == "rinviata"
    bapepe.update(fantavoto=6.0, etichetta={"codice": "voto_ufficio", "testo": "Voto d'ufficio", "tono": "positivo"})
    o["rinvio"].update(modo="voto_ufficio", valore=6.0, eccezione=True)
    web.risposta("/api/oggi", o)
    web.apri("/")
    p = pedina(web, "Bapepe")
    assert p.locator(".disco").inner_text().strip() == "6,0"
    visibile = " ".join(p.inner_text().split())
    assert "Voto d'ufficio" in visibile and "Rinviata" not in visibile
    assert p.locator(".solo-lettori").inner_text().strip() == "Bapepe, fantavoto 6,0, Voto d'ufficio"
    assert not web.errori_console
