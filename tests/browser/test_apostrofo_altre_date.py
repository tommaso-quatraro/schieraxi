"""L'apostrofo davanti all'8 e all'11 nelle altre date che la web scrive dopo un articolo (#859, seguito della #852): «dall'8
ottobre 2026», «Rose aggiornate l'11 novembre 2026», «fino all'11/01/2027», mai «dal 8» o «il 11» (si legge «dall'otto», «l'undici»).
Le altre date restano («dal 18 ottobre 2026», «il 1 novembre 2026»: il primo).

Le frasi sono del catalogo e le compone la web (`account.dal`, `scambio.rose_aggiornate`, `sd.dal`, `sd.coppe_spiega`); la riga
della taratura (`sd.tar_attiva_dal`) la prova `tests/test_stato_dati_taratura_web.py`, la frase delle probabili la scrive il server
(`tests/test_probabili_fresche.py`). L'iPhone prova le stesse forme nei suoi test (`ModuloAccessoTests`, `SquadreComeLaWebTests`,
`TaraturaProbabiliTests`).
"""
import re

import pytest

UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente"}}


def _solo_prima(web):
    if web.fase != "prima":
        pytest.skip("una fase basta: la data non dipende dal momento della giornata")


def _testo(testo: str) -> str:
    return " ".join(testo.split())


@pytest.mark.parametrize(("creato", "atteso"), [("2026-10-08T10:00:00", "Utente · dall'8 ottobre 2026"),
                                                ("2026-10-11T10:00:00", "Utente · dall'11 ottobre 2026"),
                                                ("2026-10-18T10:00:00", "Utente · dal 18 ottobre 2026"),
                                                ("2026-10-01T10:00:00", "Utente · dal 1 ottobre 2026")])
def test_l_account_dice_da_quando_con_l_apostrofo(web, creato, atteso):
    _solo_prima(web)
    web.risposta("/api/account/me", {**UTENTE, "utente": {**UTENTE["utente"], "creato": creato}})
    web.apri("/?vista=impostazioni&gruppo=account")
    testo = _testo(web.testo_principale())
    assert atteso in testo, testo[:300]


@pytest.mark.parametrize(("aggiornato", "atteso"), [("2026-11-08T19:19:33", "Rose aggiornate l'8 novembre 2026"),
                                                    ("2026-11-11T09:00:00", "Rose aggiornate l'11 novembre 2026"),
                                                    ("2026-11-01T09:00:00", "Rose aggiornate il 1 novembre 2026")])
def test_la_rosa_dice_quando_e_aggiornata_con_l_apostrofo(web, aggiornato, atteso):
    _solo_prima(web)
    rosa = web.registrata("/api/rosa")
    rosa["aggiornato"] = aggiornato
    web.risposta("/api/rosa", rosa)
    web.apri("/?vista=impostazioni&gruppo=squadra")
    testo = _testo(web.testo_principale())
    assert atteso in testo, testo[-300:]


# La data breve del browser (`fData(d, {})`): «08/10/2026» in Chrome, con lo zero; «l'08/10» si legge comunque «l'otto».
@pytest.mark.parametrize(("uso_dal", "coppe_fino", "attesi"), [
    ("2026-10-08", "2027-01-11", [r"ultime 4 settimane \(dall'0?8/10/2026\)", r"Inserite fino all'11/0?1/2027"]),
    ("2026-10-11", "2027-01-08", [r"ultime 4 settimane \(dall'11/10/2026\)", r"Inserite fino all'0?8/0?1/2027"]),
    ("2026-10-18", "2027-01-28", [r"ultime 4 settimane \(dal 18/10/2026\)", r"Inserite fino al 28/0?1/2027"])])
def test_lo_stato_dei_dati_mette_l_apostrofo_davanti_alle_date(web, uso_dal, coppe_fino, attesi):
    _solo_prima(web)
    web.risposta("/api/account/me", {**UTENTE, "utente": {**UTENTE["utente"], "ruolo": "amministratore"}})
    dati = web.registrata("/api/stato-dati")
    dati["uso"]["dal"], dati["coppe_fino"] = uso_dal, coppe_fino
    web.risposta("/api/stato-dati", dati)
    web.apri("/?vista=impostazioni&gruppo=gestione")
    web.pagina.get_by_role("button", name="Apri lo stato dei dati").click(timeout=10000)
    foglio = web.pagina.get_by_role("dialog")
    foglio.get_by_role("heading", name="Stato dei dati").wait_for(timeout=10000)
    web.aspetta()
    testo = _testo(foglio.inner_text())
    for atteso in attesi:
        assert re.search(atteso, testo), (atteso, re.findall(r"[^.]*(?:settimane|Inserite)[^.]*", testo))
