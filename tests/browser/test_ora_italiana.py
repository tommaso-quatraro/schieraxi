"""Date e conto alla rovescia sempre nell'ora italiana, anche con il browser su un altro fuso (#776).

Il server scrive le date in ora italiana senza fuso («2026-10-27 18:20», docs/API.md) e l'iPhone le legge così. La web le leggeva
con il fuso del browser: a New York la scadenza delle 18:20 italiane diventava le 18:20 di New York (conto alla rovescia sbagliato
di 5 o 6 ore), a Tokyo la formazione risultava già chiusa. Qui la stessa scheda si apre con il browser su altri fusi.
"""
import pytest

ALTRI_FUSI = ("America/New_York", "Asia/Tokyo")
TUTTI_I_FUSI = ("Europe/Rome", *ALTRI_FUSI)


def solo(web, *fasi):
    if web.fase not in fasi:
        pytest.skip(f"vale per la fase: {', '.join(fasi)}")


def pagina_intera(w) -> str:
    """Il testo che si vede in tutta la pagina (anche la riga di stato sotto il titolo), con gli spazi normali."""
    return " ".join(w.pagina.evaluate("() => document.body.innerText").replace("\u00a0", " ").split())


def vista(w, nome: str) -> str:
    w.apri(f"/?vista={nome}")
    assert not w.errori_console, w.errori_console
    return pagina_intera(w)


def formazione(w) -> str:
    return vista(w, "formazione")


@pytest.mark.parametrize("fuso", ALTRI_FUSI)
def test_la_formazione_si_legge_uguale_in_ogni_fuso(web, fuso):
    """Scadenza, conto alla rovescia, orari delle partite: in ogni fase la pagina dice le stesse cose che in Italia."""
    italia = formazione(web)
    altrove = formazione(web.con_fuso(fuso))
    assert altrove == italia


@pytest.mark.parametrize("fuso", ALTRI_FUSI)
def test_la_data_dei_dati_si_legge_uguale_in_ogni_fuso(web, fuso):
    """La riga di stato sotto il titolo (Giornate) dice di quando sono i dati (\u00abdati del 26 ott 23:55\u00bb): l'ora italiana."""
    italia = vista(web, "giornate")
    assert "dati del" in italia, italia[:300]
    assert vista(web.con_fuso(fuso), "giornate") == italia


@pytest.mark.parametrize("fuso", TUTTI_I_FUSI)
def test_scadenza_e_conto_alla_rovescia_in_ora_italiana(web, fuso):
    """Alle 15:10 italiane del 27/10 la formazione si chiude alle 18:20: «oggi 18:20», «fra 3 h 10 min». A Tokyo sono già le 23:10
    e le 18:20 italiane cadono il giorno dopo: resta comunque «oggi», il giorno italiano."""
    solo(web, "prima")
    testo = formazione(web.con_fuso(fuso))
    assert "Si chiude oggi 18:20" in testo and "fra 3 h 10 min" in testo, testo[:400]


# a cavallo del cambio dell'ora: adesso e scadenza in ora italiana, e gli istanti UTC fatti a mano
CAMBI_DELL_ORA = {
    # sabato 24/10/2026 20:00 (legale, 18:00 UTC) -> domenica 25/10 14:30 (solare, 13:30 UTC): 19 h 30 min, non 18 h 30
    "ottobre": ("2026-10-24T20:00:00", "2026-10-25 14:30", "Si chiude domani 14:30", "fra 19 h 30 min"),
    # sabato 27/3/2027 20:00 (solare, 19:00 UTC) -> domenica 28/3 14:30 (legale, 12:30 UTC): 17 h 30 min, non 18 h 30
    "marzo": ("2027-03-27T20:00:00", "2027-03-28 14:30", "Si chiude domani 14:30", "fra 17 h 30 min"),
}


@pytest.mark.parametrize("cambio", list(CAMBI_DELL_ORA))
@pytest.mark.parametrize("fuso", TUTTI_I_FUSI)
def test_il_conto_alla_rovescia_regge_al_cambio_dell_ora(web, fuso, cambio):
    solo(web, "prima")
    adesso, scadenza, chiude, manca = CAMBI_DELL_ORA[cambio]
    w = web.con_fuso(fuso)
    oggi = w.registrata("/api/oggi") | {"scadenza": scadenza}
    w.risposta("/api/oggi", oggi)
    w.orologio(adesso)
    testo = formazione(w)
    assert chiude in testo and manca in testo, testo[:400]
