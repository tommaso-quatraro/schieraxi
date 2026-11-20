"""Oggi con la giornata da preparare senza data (#552): il server lo dice con una frase sua (`senza_data` = {testo, frase}, chiave
`giornata.senza_data`), e web e iPhone la mostrano così com'è al posto di «Si chiude …». Prima ogni client scriveva un testo suo
(«Calendario non disponibile» sulla web, «Data da definire» sull'iPhone). Il campo c'è solo in quel caso; a campionato finito vale
`campionato_finito`, che ha la precedenza. Archivio inventato in una cartella temporanea, orari fissati."""
from datetime import datetime

from fanta import archivio, frasi
from test_campionato_finito import _ultima_giornata_giocata
from test_fasi import ST, _giornata_finita, _oggi, ambiente  # noqa: F401  (fixture)

FRASE = {"chiave": "giornata.senza_data", "param": {}}


def _senza_date(a, giornata):
    """Le partite di `giornata` ancora senza data nel calendario (le date di Serie A non sono uscite), e qualcuna in più: una giornata
    senza date resta quella da giocare con almeno 5 partite da giocare (consigli.prossima_giornata)."""
    a.db.execute("UPDATE partite SET data = NULL WHERE stagione = ? AND giornata = ?", (ST, giornata))
    altre = [("como", "pisa"), ("parma", "lecce"), ("genoa", "cagliari")]
    archivio.inserisci(a.db, "partite", [{"id": 100 * giornata + n, "stagione": ST, "giornata": giornata, "data": None, "casa": c,
                                          "trasferta": t, "gol_casa": None, "gol_trasferta": None, "giocata": 0, "understat_id": None}
                                         for n, (c, t) in enumerate(altre)])
    a.db.commit()


def test_la_frase_ha_la_sua_chiave_nel_catalogo():
    assert frasi.CATALOGO["giornata.senza_data"] == "Data da definire"


def test_prima_della_scadenza_con_la_giornata_senza_data_la_frase_del_server(ambiente):  # noqa: F811
    _senza_date(ambiente, 10)
    o = _oggi(ambiente, datetime(2026, 11, 5, 12, 0))
    assert o["giornata"] == 10 and o["scadenza"] is None and o["inizio"] is None
    assert o["senza_data"] == {"testo": "Data da definire", "frase": FRASE}


def test_con_la_data_niente_campo(ambiente):  # noqa: F811
    o = _oggi(ambiente, datetime(2026, 11, 5, 12, 0))
    assert o["scadenza"] == "2026-11-07 15:00" and "senza_data" not in o


def test_a_giornata_finita_vale_la_data_della_prossima(ambiente):  # noqa: F811
    """Fase «finita»: la formazione mostrata è quella della prossima (la 11). Senza le sue date la frase; con le date niente."""
    _giornata_finita(ambiente)
    o = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))
    assert o["fase"] == "finita" and o["prossima"]["scadenza"] and "senza_data" not in o
    _senza_date(ambiente, 11)
    o = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))
    assert o["fase"] == "finita" and o["prossima"]["giornata"] == 11 and o["prossima"]["scadenza"] is None
    assert o["senza_data"]["frase"] == FRASE


def test_a_giornata_in_corso_niente_campo(ambiente):  # noqa: F811
    """Dopo la scadenza la giornata una data ce l'ha: niente frase, nemmeno per chi è entrato a giornata iniziata."""
    adesso = datetime(2026, 11, 8, 21, 30)
    assert "senza_data" not in _oggi(ambiente, adesso)
    assert "senza_data" not in _oggi(ambiente, adesso, dal=datetime(2026, 11, 8, 18, 0))


def test_a_campionato_finito_vale_campionato_finito(ambiente):  # noqa: F811
    _ultima_giornata_giocata(ambiente)
    o = _oggi(ambiente, datetime(2026, 11, 18, 10, 0))
    assert o["campionato_finito"] and o["scadenza"] is None and "senza_data" not in o
