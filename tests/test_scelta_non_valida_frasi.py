"""#331: promemoria e «Da fare» hanno una frase propria quando la scelta salvata non vale più. (Il riepilogo mandato dopo la
giornata, che qui usava l'istantanea del Diario, non è più un avviso dalla #693.)
Dati finti, file in cartelle temporanee, nessun invio vero."""
# ruff: noqa: F811  (le fixture importate da altri file di test arrivano come parametri con lo stesso nome: è il modo di pytest)
from datetime import datetime

import pytest

from fanta import notifiche, scelte
from fanta.frasi import CATALOGO, F, nome_giornata
from fanta.frasi_avvisi import NOTIFICHE
from fanta.regole import Regole
from test_da_fare import STAGIONE, mondo, vai  # noqa: F401  (mondo = fixture di «Da fare»)
from test_notifiche import ST, _db
from test_scelta_non_valida_avvisi import CEDUTO, CHIUSURA, DUE_PORTIERI, OPZ, ROSE, TITOLARI, _prima_della_scadenza, _registro

# ---------------------------------------------------------------- frase propria per la scelta salvata che non vale più
NON_VALIDE_9 = [pytest.param([*TITOLARI[:10], CEDUTO], id="giocatore-ceduto"), pytest.param(DUE_PORTIERI, id="modulo-non-ammesso")]


def _promemoria(tmp_path, monkeypatch, salvata, quando, stato="p.json"):
    _prima_della_scadenza(monkeypatch)
    fs = tmp_path / "scelte.json"
    if salvata:
        scelte.salva(ST, 9, salvata, "4-4-2", fs)
    mandati, manda = _registro()
    r = notifiche.promemoria(_db(CHIUSURA), Regole(), ROSE, quando, tmp_path / stato, manda, OPZ, fs)
    return r, mandati


@pytest.mark.parametrize("salvata", NON_VALIDE_9)
def test_promemoria_un_ora_dice_che_la_formazione_salvata_non_vale(tmp_path, monkeypatch, salvata):
    r, mandati = _promemoria(tmp_path, monkeypatch, salvata, datetime(2026, 10, 28, 17, 35))
    testo = mandati[0][1]
    assert len(r) == 1 and mandati[0][0] == "SchieraXI · formazione tra un'ora"
    assert testo.startswith("Giornata 9 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30), ma quella che hai salvato "
                            "non è più valida: salvane un'altra.")
    assert "Consigliato: 4-4-2, 71,2 punti attesi." in testo                    # il consiglio resta, serve a sceglierne un'altra
    assert "L'hai inserita" not in testo


@pytest.mark.parametrize("salvata", NON_VALIDE_9)
def test_promemoria_ultimi_minuti_dice_che_la_formazione_salvata_non_vale(tmp_path, monkeypatch, salvata):
    r, mandati = _promemoria(tmp_path, monkeypatch, salvata, datetime(2026, 10, 28, 18, 20))
    assert len(r) == 1 and mandati[0][0] == "SchieraXI · ultimi minuti per la formazione"
    assert mandati[0][1] == ("Giornata 9 · 9ª di Serie A: la formazione si chiude alle 18:30 e quella che hai salvato non è più valida. "
                             "Salvane un'altra.")


def test_promemoria_senza_scelta_resta_come_prima(tmp_path, monkeypatch):
    _, mandati = _promemoria(tmp_path, monkeypatch, None, datetime(2026, 10, 28, 17, 35))
    assert mandati[0][1].startswith("Giornata 9 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30).")
    _, mandati = _promemoria(tmp_path, monkeypatch, None, datetime(2026, 10, 28, 18, 20))
    assert mandati[0][1] == "Giornata 9 · 9ª di Serie A: la formazione si chiude alle 18:30. L'hai inserita su Leghe?"


def test_promemoria_con_scelta_valida_non_cambia(tmp_path, monkeypatch):
    """Scelta a posto: nessun promemoria (come prima)."""
    r, mandati = _promemoria(tmp_path, monkeypatch, TITOLARI, datetime(2026, 10, 28, 17, 35))
    assert r == [] and mandati == []


def test_le_frasi_nuove_hanno_italiano_e_inglese():
    for chiave in ("n.non_valida_tra_un_ora", "n.non_valida_ultimi_minuti"):
        it, en = NOTIFICHE[chiave]
        assert "non è più valida" in it and "no longer valid" in en
        f = F(chiave, giornata=nome_giornata(9, 6, avviso=True), ora="18:30")                  # la giornata con i due numeri (#299)
        assert str(f).startswith("Giornata 6 · 9ª di Serie A: ") and f.in_lingua("en").startswith("Matchday 6 · Serie A matchday 9: ")
        assert "{" not in str(f) and "{" not in f.in_lingua("en") and "18:30" in f.in_lingua("en")
    assert "dafare.formazione_non_valida" in CATALOGO


def test_da_fare_formazione_salvata_non_valida_ha_la_sua_frase(mondo):
    """Vicino alla scadenza: con una scelta che non vale la voce dice che quella salvata non è più valida; senza scelta resta
    «non l'hai ancora salvata»."""
    mondo.oggi["ore_mancanti"] = 2.0
    senza = [x for x in vai(mondo) if x["tipo"] == "formazione"]
    assert len(senza) == 1 and senza[0]["frase"]["chiave"] == "dafare.formazione_chiude" and "non l'hai ancora salvata" in senza[0]["testo"]
    scelte.salva(STAGIONE, 9, [1, 2, 3, 4, 7, 8, 9, 10, 11, 12, CEDUTO], "3-5-2", mondo.ctx.scelte)
    voce = [x for x in vai(mondo) if x["tipo"] == "formazione"]
    assert len(voce) == 1 and voce[0]["priorita"] == 1 and voce[0]["azione"] == "Apri la formazione"
    assert voce[0]["testo"] == "La formazione si chiude tra 2 ore e quella che hai salvato non è più valida: salvane un'altra."
    assert voce[0]["frase"] == F("dafare.formazione_non_valida", tempo=F("tempo.ore", n=2)).json()
