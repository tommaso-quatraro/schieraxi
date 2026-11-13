"""Promemoria e spunta «L'ho messa» (#639): il promemoria prima della scadenza tace solo se la formazione è segnata come messa
nell'app della lega. La web salva da sola a ogni tocco: una scelta salvata dalla web ma non segnata riceve il promemoria, con una
frase che chiede proprio questo.

L'app per iPhone di oggi non ha la spunta: per le scelte salvate dall'iPhone (e per quelle di cui non si sa da dove vengono, per
esempio salvate prima di questa versione) il promemoria resta com'era, cioè tace con una scelta salvata. Per saperlo la scelta
salvata ricorda da dove arriva (`da`: «web» o «app»), un campo in più che i client di prima ignorano.
Mai l'orologio vero: `adesso` è un argomento. Dati inventati e cartelle temporanee."""
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fanta import calcolo, consigli, fasi, notifiche, scelte, server
from fanta.regole import Regole

from test_account_http import PASSWORD
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_promemoria_schierato import ALTRI, ROSE, TITOLARI as SCHIERATI, _db
from fanta import lega
from test_server import client  # noqa: F401 (fixture: un solo utente, senza account)

ST = "2026-27"
TITOLARI = list(range(1, 12))
ROSE_TESTO = "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"


# ---------------------------------------------------------------- da dove arriva la scelta salvata
def test_la_scelta_ricorda_da_dove_arriva_solo_se_si_sa(tmp_path):
    f = tmp_path / "scelte.json"
    assert scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="web")["da"] == "web"
    assert scelte.leggi(ST, 9, f)["da"] == "web"
    assert scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="app")["da"] == "app"          # l'ultimo che salva decide
    assert "da" not in scelte.salva(ST, 9, TITOLARI, "4-3-3", f)                       # non si sa: il campo non c'è
    assert "da" not in scelte.salva(ST, 9, TITOLARI, "4-3-3", f, da="altro")           # solo i due valori previsti


def _finti(monkeypatch):
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": giornata or 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (pd.DataFrame(index=[]), 9, False))
    calcolo.cache.clear()
    monkeypatch.setattr(fasi.avvisi, "prima_partita", lambda db, stagione, g: datetime.now() + timedelta(hours=2) if g == 9 else None)


@pytest.fixture
def prova(ambiente, monkeypatch):  # noqa: F811 (la fixture importata arriva come parametro con lo stesso nome)
    _finti(monkeypatch)
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE_TESTO})
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    return a


def _salva(c, **altro):
    return c.post("/api/formazione/valuta", json={"titolari": TITOLARI, "giornata": 9, "salva": True, **altro})


def _scelta(c):
    return c.get("/api/scelta", params={"giornata": 9}).json()


def test_dalla_web_la_scelta_e_della_web(prova):
    """La web ha il cookie della sessione (l'iPhone no): la scelta salvata da lì ha `da: "web"`."""
    assert _salva(prova).status_code == 200
    assert _scelta(prova)["da"] == "web"


def test_dall_app_la_scelta_e_dell_app(prova):
    """L'app nativa manda il token come «Bearer» (la stessa regola delle rotte degli account): `da: "app"`, anche se la stessa
    giornata era stata salvata prima dalla web. La spunta già messa resta finché gli 11 sono gli stessi."""
    _salva(prova, messa=True)
    iphone = TestClient(server.app, headers={"X-Fanta": "1"})
    r = iphone.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD, "nativo": True})
    iphone.headers["Authorization"] = f"Bearer {r.json()['token']}"
    assert _salva(iphone).status_code == 200
    scelta = _scelta(prova)
    assert scelta["da"] == "app" and scelta["messa"] is True


def test_senza_account_la_web_si_riconosce_dalle_intestazioni_del_browser(client, monkeypatch):  # noqa: F811
    """Senza account non c'è il cookie: un browser recente manda `Sec-Fetch-Mode` (l'app nativa no). Senza nessuno dei due
    segni non si sa da dove arriva: il campo non si scrive."""
    _finti(monkeypatch)
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: ST)
    client.post("/api/rose/testo", json={"testo": ROSE_TESTO})
    client.put("/api/mia-squadra", json={"nome": "Mia"})
    r = client.post("/api/formazione/valuta", json={"titolari": TITOLARI, "giornata": 9, "salva": True}, headers={"Sec-Fetch-Mode": "cors"})
    assert r.status_code == 200
    assert _scelta(client)["da"] == "web"
    assert _salva(client).status_code == 200
    assert "da" not in _scelta(client)


# ---------------------------------------------------------------- il promemoria
UN_ORA, QUARTO = datetime(2026, 10, 28, 17, 35), datetime(2026, 10, 28, 18, 20)      # la formazione si chiude alle 18:30
DOMANDA = "Hai messo la formazione nell'app della lega?"
ROSA_12 = lega.Rose([lega.Squadra("Mia", ROSE.squadra("Mia").giocatori + [lega.GiocatoreRosa(12, "Zeta", "A", "COM", 5)])], "Mia")
CON_ZETA = [*SCHIERATI[1:], 12]                                     # Zeta al posto di Castro: sempre un 4-4-2


def _mondo(tmp_path, monkeypatch, stato="titolare"):
    """Castro (1), dieci compagni e Zeta (12) in panchina: un 4-4-2 che si può schierare (come test_promemoria_schierato.py).
    `promemoria(adesso)` fa un giro con il file di stato indicato e le scelte in `tmp_path`; `mandati` raccoglie (titolo, testo)."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-4-2", "punteggio_atteso": 71.2, "titolari": [{"id": 1, "nome": "Castro", "titolarita": "titolare", "dubbio": False}]})
    prev = pd.DataFrame([{"nome": "Castro", "ruolo": "A", "stato": stato, "percentuale": 80.0, "dubbio": False}]
                        + [{"nome": n, "ruolo": r, "stato": "titolare", "percentuale": 90.0, "dubbio": False} for n, r in ALTRI.values()]
                        + [{"nome": "Zeta", "ruolo": "A", "stato": "titolare", "percentuale": 70.0, "dubbio": False}],
                        index=[*SCHIERATI, 12])
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    mandati = []

    def promemoria(adesso, nome="p.json"):
        return notifiche.promemoria(_db(), Regole(), ROSA_12, adesso, tmp_path / nome,
                                    lambda titolo, testo, priorita=3, tag="x", **k: mandati.append((titolo, testo)) or True,
                                    {}, tmp_path / "scelte.json")
    return promemoria, mandati


def _salvata(tmp_path, titolari=SCHIERATI, **altro):
    return scelte.salva(ST, 9, titolari, "4-4-2", tmp_path / "scelte.json", **altro)


def test_scelta_della_web_non_segnata_riceve_il_promemoria_che_chiede_della_spunta(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da="web")
    assert len(promemoria(UN_ORA)) == 1 and len(promemoria(QUARTO)) == 1
    assert [t for t, _ in mandati] == ["SchieraXI · formazione tra un'ora", "SchieraXI · ultimi minuti per la formazione"]
    assert all(DOMANDA in testo and "18:30" in testo for _, testo in mandati)
    assert promemoria(QUARTO) == []                                                  # una volta sola per finestra


def test_scelta_della_web_segnata_come_messa_non_riceve_il_promemoria(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da="web", messa=True)
    assert promemoria(UN_ORA) == [] and promemoria(QUARTO) == [] and mandati == []


def test_se_gli_11_cambiano_la_spunta_cade_e_il_promemoria_riparte(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da="web", messa=True)
    assert promemoria(UN_ORA) == []
    _salvata(tmp_path, list(reversed(SCHIERATI)), da="web")                             # stessi 11: la spunta resta
    assert promemoria(UN_ORA) == []
    _salvata(tmp_path, CON_ZETA, da="web")                                            # un titolare diverso: la spunta cade
    assert len(promemoria(UN_ORA + timedelta(minutes=5))) == 1 and DOMANDA in mandati[0][1]


def test_senza_scelta_il_promemoria_e_quello_di_sempre(tmp_path, monkeypatch):
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    assert len(promemoria(UN_ORA)) == 1
    assert "Consigliato: 4-4-2" in mandati[0][1] and DOMANDA not in mandati[0][1]


@pytest.mark.parametrize("da", ["app", None])
def test_scelta_dell_iphone_o_di_prima_tace_come_oggi(tmp_path, monkeypatch, da):
    """L'iPhone di oggi non ha la spunta (arriverà con il riallineamento, #673): chi salva da lì non riceve promemoria in più.
    Lo stesso per una scelta salvata prima di questa versione, che non dice da dove arriva."""
    promemoria, mandati = _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da=da)
    assert promemoria(UN_ORA) == [] and promemoria(QUARTO) == [] and mandati == []


@pytest.mark.parametrize("messa", [False, True])
def test_scelta_della_web_con_un_titolare_saltato_dice_del_titolare(tmp_path, monkeypatch, messa):
    """Con un titolare diventato indisponibile il promemoria parla di lui, come oggi, con o senza la spunta: un avviso solo."""
    promemoria, mandati = _mondo(tmp_path, monkeypatch, stato="infortunato")
    _salvata(tmp_path, da="web", messa=messa)
    assert len(promemoria(UN_ORA)) == 1 and promemoria(UN_ORA + timedelta(minutes=5)) == []
    assert mandati[0][0] == "SchieraXI · un tuo titolare è a rischio" and "Castro" in mandati[0][1]
