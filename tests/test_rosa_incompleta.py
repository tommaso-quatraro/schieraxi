"""Rosa incompleta (collaudo dell'amico nuovo del 27/11): con 9 giocatori incollati la Formazione diceva «Non si riesce a formare
una squadra: in qualche ruolo nessuno gioca questa giornata», e il server rispondeva 400 a ogni apertura. La causa vera la sapeva già
l'anteprima: mancano giocatori per le regole della lega.

Ora il server dice la causa vera (`consigli.RosaIncompleta`, frase `formazione.rosa_incompleta`, codice `rosa_incompleta`) quando
con i giocatori riconosciuti della rosa nessun modulo ammesso si riempie; Oggi la manda come stato normale (`rosa_incompleta`, 200) e
lo stato d'avvio lo dice (`rosa_incompleta`), così la web non chiede la Formazione e non riempie la console di 400. Le app già
installate leggono ancora il 400 della Formazione, con la frase giusta. Dati inventati, cartelle temporanee, nessun orologio vero."""
import sqlite3
from dataclasses import replace
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from fanta import archivio, consigli, lega, regole, server
from fanta.consigli import formazione as formazione_vera
from test_fasi import ST, _oggi, ambiente  # noqa: F401  (fixture)

TESTO = ("Non si riesce a formare una squadra: secondo le regole della lega, alla rosa di Real Finzione mancano 1 portiere, "
         "6 difensori, 6 centrocampisti e 4 attaccanti.")


def _rosa_corta() -> lega.Squadra:
    """Come `tests/dati/rose_uno_per_riga.txt`: 2 portieri, 2 difensori, 2 centrocampisti, 2 attaccanti e un non trovato."""
    ruoli = ["P", "P", "D", "D", "C", "C", "A", "A"]
    giocatori = [lega.GiocatoreRosa(100 + i, f"Giocatore {i}", r, "INT") for i, r in enumerate(ruoli)]
    return lega.Squadra("Real Finzione", giocatori + [lega.GiocatoreRosa(None, "D'Ambrosio", None, None, riconosciuto="non trovato")])


def _rosa_piena() -> lega.Squadra:
    ruoli = ["P"] * 3 + ["D"] * 8 + ["C"] * 8 + ["A"] * 6
    return lega.Squadra("Real Finzione", [lega.GiocatoreRosa(200 + i, f"Giocatore {i}", r, "INT") for i, r in enumerate(ruoli)])


# ---------------------------------------------------------------- la frase (funzione pura)
def test_con_la_rosa_corta_la_frase_dice_quanti_mancano_per_ruolo():
    frase = consigli.rosa_incompleta(_rosa_corta(), regole.Regole())
    assert frase == TESTO
    assert frase.chiave == "formazione.rosa_incompleta"
    assert frase.json()["param"]["squadra"] == "Real Finzione" and frase.json()["param"]["n"] == 17


def test_una_rosa_incompleta_che_forma_una_squadra_non_e_un_problema():
    """11 giocatori per un 3-4-3: mancano giocatori per le regole, ma una squadra si forma (la Formazione si calcola come sempre)."""
    ruoli = ["P"] + ["D"] * 3 + ["C"] * 4 + ["A"] * 3
    s = lega.Squadra("Mia", [lega.GiocatoreRosa(i, f"g{i}", r, "INT") for i, r in enumerate(ruoli, 1)])
    assert consigli.rosa_incompleta(s, regole.Regole()) is None
    assert consigli.rosa_incompleta(_rosa_piena(), regole.Regole()) is None


def test_un_giocatore_solo_al_singolare():
    """Con una rosa di un portiere solo nelle regole e nessun portiere: «manca 1 portiere»."""
    r = replace(regole.Regole(), rosa={"P": 1, "D": 8, "C": 8, "A": 6})
    s = lega.Squadra("Mia", [g for g in _rosa_piena().giocatori if g.ruolo != "P"])
    assert consigli.rosa_incompleta(s, r) == ("Non si riesce a formare una squadra: secondo le regole della lega, alla rosa di Mia "
                                              "manca 1 portiere.")


def test_la_formazione_dice_la_causa_vera_con_il_codice(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    rose = lega.Rose([_rosa_corta()], "Real Finzione")
    with pytest.raises(consigli.RosaIncompleta) as e:
        consigli.formazione(sqlite3.connect(":memory:"), regole.Regole(), rose, giornata=10)
    assert str(e.value) == TESTO and e.value.codice == "rosa_incompleta"
    assert isinstance(e.value, consigli.FormazioneImpossibile)          # chi prendeva l'esito impossibile lo prende ancora


# ---------------------------------------------------------------- Oggi: uno stato, non un errore
def test_oggi_manda_la_rosa_incompleta_con_la_frase(ambiente, monkeypatch):  # noqa: F811
    monkeypatch.setattr(consigli, "formazione", formazione_vera)        # quella vera: la rosa si controlla prima del calcolo
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda *a, **k: 10)     # niente orologio vero
    ambiente.rose = lega.Rose([_rosa_corta()], "Real Finzione")
    o = _oggi(ambiente, datetime(2026, 11, 6, 12, 0))
    assert o["rosa_incompleta"]["testo"] == TESTO
    assert o["rosa_incompleta"]["frase"]["chiave"].startswith("formazione.rosa_incompleta")
    assert o["formazione"]["punteggio_atteso"] is None and o["migliori"] == []


def test_oggi_con_la_formazione_niente_rosa_incompleta(ambiente):  # noqa: F811
    assert "rosa_incompleta" not in _oggi(ambiente, datetime(2026, 11, 6, 12, 0))


# ---------------------------------------------------------------- le rotte (server vero, archivio vuoto)
@pytest.fixture
def lega_corta(dati_isolati, tmp_path, monkeypatch):
    regole.salva(regole.Regole(), dati_isolati / "regole.json")
    lega.salva(lega.Rose([_rosa_corta()], "Real Finzione"), dati_isolati / "rose.json")
    percorso = tmp_path / "archivio-finto" / "fanta.sqlite"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    archivio.apri(percorso).close()
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda *a, **k: 10)     # niente orologio vero
    return dati_isolati


def _client():
    return TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)


def test_formazione_risponde_con_la_causa_vera_e_il_codice(lega_corta):
    """Le app già installate leggono il 400 di sempre: con la frase giusta e il nome breve dell'errore. In più la frase con la chiave
    (`frase`), così la web in inglese la traduce (la Formazione di un'altra squadra, o uno stato d'avvio vecchio)."""
    r = _client().get("/api/formazione")
    assert r.status_code == 400, r.text
    corpo = r.json()
    assert corpo["detail"] == TESTO and corpo["codice"] == "rosa_incompleta"
    assert corpo["frase"]["chiave"] == "formazione.rosa_incompleta" and corpo["frase"]["param"]["squadra"] == "Real Finzione"


def test_un_errore_senza_frase_non_cambia(lega_corta):
    """Un messaggio scritto come testo semplice resta `{detail}` come prima: `frase` c'è solo per una frase con la chiave."""
    r = _client().get("/api/formazione", params={"squadra": "Non esiste"})
    assert r.status_code == 400 and set(r.json()) == {"detail"}, r.text


def test_lo_stato_d_avvio_dice_se_la_rosa_non_basta(lega_corta):
    c = _client()
    assert c.get("/api/stato").json()["rosa_incompleta"] is True
    lega.salva(lega.Rose([_rosa_piena()], "Real Finzione"), lega_corta / "rose.json")
    assert c.get("/api/stato").json()["rosa_incompleta"] is False


def test_lo_stato_d_avvio_senza_rose_non_dice_rosa_incompleta(lega_corta):
    (lega_corta / "rose.json").unlink()
    s = _client().get("/api/stato").json()
    assert s["rose_importate"] is False and s["rosa_incompleta"] is False
