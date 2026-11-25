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


# ---------------------------------------------------------------- 3. la frase sotto i punti la sceglie il server
def test_la_frase_sotto_i_punti_e_quella_del_server(web):
    """I titolari hanno già il voto e resta Bapepe con la partita rinviata: sotto i punti la frase del server (il recupero), non
    «Hanno giocato tutti: mancano solo i voti ufficiali.» che la web sceglieva da sola a ogni `ancora_da_giocare` zero."""
    solo(web, "in-corso")
    o = oggi_in_corso(web)
    frase = "Hanno giocato tutti tranne Bapepe, che aspetta il recupero."
    o["in_corso"].update(ancora_da_giocare=0, situazione=frase,
                         situazione_frase={"chiave": "in_corso.recupero", "param": {"n": 1, "nomi": "Bapepe"}})
    web.risposta("/api/oggi", o)
    web.apri("/")
    testo = web.testo_principale()
    assert frase in testo and "mancano solo i voti ufficiali" not in testo
    assert not web.errori_console


# ---------------------------------------------------------------- 2. la scelta sul rinvio della giornata finita, con il suo titolo
RINVIO_FINITA = {"stagione": "2026-27", "modo": "aspetta", "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6.0,
                 "predefinito": "aspetta", "eccezione": False, "partite": [{"casa": "udinese", "trasferta": "milan", "data": "2026-11-18 20:45"}],
                 "miei": [{"id": 4312, "nome": "Bapepe", "ruolo": "P", "squadra": "milan"}]}


def test_a_giornata_finita_la_scelta_sul_rinvio_sta_con_la_sua_giornata_e_ha_un_titolo(web):
    """Il menu «per questa giornata i loro giocatori…» finiva in fondo, sotto la panchina della giornata dopo, senza titolo né la
    partita e i giocatori. Ora sta in testa, con la giornata finita: un titolo con la giornata, la partita, i miei giocatori."""
    solo(web, "finita")
    o = copy.deepcopy(web.registrata("/api/oggi"))
    r = o["riepilogo"]
    r.update(recuperi=[RINVIO_FINITA["partite"][0]], rinvio=RINVIO_FINITA | {"giornata": r["giornata"], "giornata_lega": r["giornata_lega"]})
    web.risposta("/api/oggi", o)
    web.apri("/")
    titolo = principale(web).get_by_role("heading", name=re.compile("partita rinviata"))
    assert titolo.count() == 1
    assert titolo.inner_text().strip() == f"Giornata {r['giornata_lega']} · {r['giornata']}ª di Serie A: partita rinviata"
    riquadro = principale(web).locator(".fz-testa .rinvio")
    testo = " ".join(riquadro.inner_text().split())
    assert "UDI vs MIL" in testo and "I tuoi giocatori coinvolti: Bapepe" in testo
    menu = riquadro.get_by_label("Per questa giornata i loro giocatori")
    assert menu.count() == 1 and principale(web).locator("select.rinvio-modo").count() == 1      # uno solo, non anche in fondo
    # sta sopra il campo e la panchina della giornata dopo
    y = lambda sel: principale(web).locator(sel).first.bounding_box()["y"]
    assert y(".fz-testa .rinvio") < y("#campo-formazione") and y(".fz-testa .rinvio") < y("#panchina")
    assert not web.errori_console
