"""La sentinella nell'ora prima della scadenza della formazione (fanta/sentinella.py, `giro`): il giro del cron diventa leggero.
Lì il servizio rifà probabili, consigliate e promemoria per tutti, e la sentinella in un processo a parte rifarebbe a freddo Oggi,
Formazione e widget di ogni utente. Nel giro leggero si ricontrolla solo chi ha una rottura aperta (così una rottura vista al giro
prima si conferma e si avvisa come sempre), più i controlli comuni; gli altri utenti passano al giro dopo. Il giro entra lo stesso
nella storia (nessun buco per la «giornata senza errori»). A mano (`--senza-invio`) il giro è sempre completo.
Archivio con il calendario inventato di test_sentinella (giornata 10: prima partita sabato 31/10 alle 15:00), orologio passato."""
import copy
import json
import sqlite3
from datetime import datetime

import pytest

from fanta import sentinella

from test_sentinella import PRIMA, REGOLE, ST, _contesto, _mondo, db  # noqa: F401  (db è una fixture)

SABATO = datetime(2026, 10, 31, 14, 37)      # 23 minuti alla scadenza: la formazione si chiude alle 15:00 (scadenza 0 minuti prima)


def _stato(file):
    """Il file di stato di un giro fa: una rottura aperta per l'utente 3, una già risolta per il 4, una comune (di tutti)."""
    file.write_text(json.dumps({"ultimo_giro": "2026-10-31T13:37:00", "utenti": {}, "aperte": {
        "punti_diversi|utente 3|10": {"volte": 1, "avvisata": False, "ultima": "2026-10-31T13:37:00"},
        "scelta_ignorata|utente 4|10": {"volte": 0, "avvisata": True, "risolta": True, "ultima": "2026-10-31T10:37:00"},
        "punteggio_mancante|-|10": {"volte": 1, "avvisata": False, "ultima": "2026-10-31T13:37:00"}}}), encoding="utf-8")


def _giro(tmp_path, monkeypatch, adesso, manda=lambda t, x: True, nome="sentinella.json"):
    """Un giro con `esegui` finto (dice con quali argomenti è stato chiamato) e le regole della lega di test_sentinella."""
    chiamate, righe = [], []

    def esegui(_db, _adesso, _minuti, _stato, solo=None):
        chiamate.append(solo)
        return {"rotture": [], "controllati": sorted(solo) if solo is not None else ["utente 3", "utente 4"],
                "rimandati": 0, "secondi": 1.0, "stagione": ST}
    monkeypatch.setattr(sentinella, "esegui", esegui)
    file = tmp_path / nome                                       # uno nuovo per giro: ogni giro aggiorna le rotture aperte
    _stato(file)
    sentinella.giro(manda=manda, file_stato=file, adesso=adesso, scrivi=righe.append, db_percorso=tmp_path / "fanta.sqlite",
                    leghe=lambda: [REGOLE])
    return chiamate[0], righe, file


@pytest.mark.usefixtures("db")
def test_nell_ora_prima_della_scadenza_si_ricontrolla_solo_chi_ha_una_rottura_aperta(tmp_path, monkeypatch):
    solo, righe, file = _giro(tmp_path, monkeypatch, SABATO)
    assert solo == {"utente 3"}                                   # non il 4 (rottura già risolta), non «tutti» (sono controlli comuni)
    assert "giro leggero" in righe[0] and "15:00" in righe[0]
    assert len(json.loads(file.read_text(encoding="utf-8"))["giri"]) == 1        # il giro entra nella storia come gli altri
    riga = sqlite3.connect(tmp_path / "fanta.sqlite").execute(
        "SELECT dettaglio FROM controlli WHERE nome = 'sentinella'").fetchone()[0]
    assert "giro leggero" in riga and "15:00" in riga               # «Stato dei dati» dice perché ha controllato meno utenti


@pytest.mark.usefixtures("db")
def test_un_ora_prima_della_scadenza_e_gia_leggero_un_minuto_prima_no(tmp_path, monkeypatch):
    assert _giro(tmp_path, monkeypatch, datetime(2026, 10, 31, 14, 0), nome="a.json")[0] == {"utente 3"}
    assert _giro(tmp_path, monkeypatch, datetime(2026, 10, 31, 13, 59), nome="b.json")[0] is None       # giro completo


@pytest.mark.usefixtures("db")
def test_dopo_la_scadenza_e_nelle_altre_ore_il_giro_e_completo(tmp_path, monkeypatch):
    assert _giro(tmp_path, monkeypatch, PRIMA, nome="a.json")[0] is None                                 # venerdì
    assert _giro(tmp_path, monkeypatch, datetime(2026, 10, 31, 15, 37), nome="b.json")[0] is None       # partite in corso


@pytest.mark.usefixtures("db")
def test_a_mano_il_giro_e_sempre_completo(tmp_path, monkeypatch):
    solo, righe, _ = _giro(tmp_path, monkeypatch, SABATO, manda=None)
    assert solo is None and not any("giro leggero" in r for r in righe)


def test_giro_leggero_controlla_solo_gli_utenti_indicati_e_rimanda_gli_altri(db, tmp_path, monkeypatch):  # noqa: F811
    m = _mondo()
    ctx = {u: _contesto(tmp_path, u.replace(" ", "")) for u in ("utente 1", "utente 2", "utente 3")}
    visti = []

    def risposte(c, db):
        visti.append(c.rose)
        return copy.deepcopy(({k: v for k, v in m.items()}, {}, None))
    monkeypatch.setattr(sentinella, "risposte_utente", risposte)
    monkeypatch.setattr(sentinella, "_prepara_live", lambda: None)
    esito = sentinella.esegui(db, PRIMA, contesti=list(ctx.items()), solo={"utente 2"})
    assert esito["controllati"] == ["utente 2"] and esito["rimandati"] == 2 and visti == [ctx["utente 2"].rose]
    esito = sentinella.esegui(db, PRIMA, contesti=list(ctx.items()), solo=set())       # nessuna rottura aperta: solo i comuni
    assert esito["controllati"] == [] and esito["rimandati"] == 3 and len(visti) == 1
